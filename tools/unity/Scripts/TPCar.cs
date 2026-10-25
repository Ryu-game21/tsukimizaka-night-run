// 仮の車（箱の車体＋WheelCollider 4輪）。後輪駆動、速度に応じてハンドルが切れにくくなる、簡単なダウンフォースとスタビライザー。
// 操作: W/↑ アクセル、S/↓ ブレーキ（止まっていればバック）、A/D または ←/→ ハンドル、Space サイドブレーキ。ゲームパッドも可。
using UnityEngine;
#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

[RequireComponent(typeof(Rigidbody))]
public class TPCar : MonoBehaviour
{
    public WheelCollider[] wheels = new WheelCollider[4];   // 左前・右前・左後・右後
    public Transform[] visuals = new Transform[4];
    public float maxTorque = 3000f;      // 後輪1本あたりの最大トルク（N·m）
    public float maxBrake = 4500f;
    public float maxSteer = 32f;         // 低速での最大舵角（度）
    public float topSpeedKmh = 270f;
    public float downforce = 2.5f;       // 速度の2乗にかける下向きの力
    public float antiRoll = 9000f;
    public bool controllable = true;

    Rigidbody rb;
    float steer;

    public float Kmh => rb ? Vel.magnitude * 3.6f : 0f;
    Vector3 Vel
    {
#if UNITY_6000_0_OR_NEWER
        get => rb.linearVelocity;
#else
        get => rb.velocity;
#endif
    }

    void Awake()
    {
        rb = GetComponent<Rigidbody>();
        rb.mass = 1400f;
        rb.centerOfMass = new Vector3(0f, 0.25f, 0.05f);
        rb.interpolation = RigidbodyInterpolation.Interpolate;
        foreach (var w in wheels)
        {
            if (!w) continue;
            w.mass = 20f; w.radius = 0.34f; w.suspensionDistance = 0.18f; w.wheelDampingRate = 0.5f;
            var sp = w.suspensionSpring; sp.spring = 42000f; sp.damper = 4200f; sp.targetPosition = 0.5f; w.suspensionSpring = sp;
            var f = w.forwardFriction; f.stiffness = 1.7f; w.forwardFriction = f;
            var s = w.sidewaysFriction; s.stiffness = 2.0f; w.sidewaysFriction = s;
        }
    }

    void ReadInput(out float thr, out float brk, out float str, out bool hand)
    {
        thr = brk = str = 0f; hand = false;
#if ENABLE_INPUT_SYSTEM
        var k = Keyboard.current;
        if (k != null)
        {
            if (k.wKey.isPressed || k.upArrowKey.isPressed) thr = 1f;
            if (k.sKey.isPressed || k.downArrowKey.isPressed) brk = 1f;
            if (k.aKey.isPressed || k.leftArrowKey.isPressed) str -= 1f;
            if (k.dKey.isPressed || k.rightArrowKey.isPressed) str += 1f;
            hand = k.spaceKey.isPressed;
        }
        var g = Gamepad.current;
        if (g != null)
        {
            thr = Mathf.Max(thr, g.rightTrigger.ReadValue());
            brk = Mathf.Max(brk, g.leftTrigger.ReadValue());
            float gx = g.leftStick.ReadValue().x; if (Mathf.Abs(gx) > Mathf.Abs(str)) str = gx;
            hand |= g.buttonSouth.isPressed;
        }
#else
        if (Input.GetKey(KeyCode.W) || Input.GetKey(KeyCode.UpArrow)) thr = 1f;
        if (Input.GetKey(KeyCode.S) || Input.GetKey(KeyCode.DownArrow)) brk = 1f;
        if (Input.GetKey(KeyCode.A) || Input.GetKey(KeyCode.LeftArrow)) str -= 1f;
        if (Input.GetKey(KeyCode.D) || Input.GetKey(KeyCode.RightArrow)) str += 1f;
        hand = Input.GetKey(KeyCode.Space);
#endif
    }

    void FixedUpdate()
    {
        float thr = 0f, brk = 0f, str = 0f; bool hand = false;
        if (controllable) ReadInput(out thr, out brk, out str, out hand);
        float kmh = Kmh;
        float fwdSpeed = Vector3.Dot(Vel, transform.forward);

        // ハンドル: 速いほど切れ角を小さく、ゆっくり戻す
        float lim = maxSteer * Mathf.Lerp(1f, 0.22f, Mathf.Clamp01(kmh / 220f));
        steer = Mathf.MoveTowards(steer, str * lim, Time.fixedDeltaTime * 120f);
        wheels[0].steerAngle = wheels[1].steerAngle = steer;

        // アクセル・ブレーキ・バック
        float drive = 0f, brake = 0f;
        if (brk > 0f && fwdSpeed > 1f) brake = brk * maxBrake;
        else if (brk > 0f) drive = -brk * maxTorque * 0.5f;                       // 止まっていればバック
        if (thr > 0f) drive = thr * maxTorque * Mathf.Clamp01(1f - kmh / topSpeedKmh) * (fwdSpeed < -1f ? 0f : 1f);
        if (thr > 0f && fwdSpeed < -1f) brake = maxBrake;
        for (int i = 0; i < 4; i++) wheels[i].brakeTorque = brake;
        wheels[2].motorTorque = wheels[3].motorTorque = drive;
        wheels[0].motorTorque = wheels[1].motorTorque = 0f;
        if (hand) { wheels[2].brakeTorque = wheels[3].brakeTorque = maxBrake * 1.5f; }

        // ダウンフォースとスタビライザー（横転しにくく）
        rb.AddForce(-transform.up * downforce * Vel.sqrMagnitude);
        AntiRoll(wheels[0], wheels[1]); AntiRoll(wheels[2], wheels[3]);
    }

    void AntiRoll(WheelCollider l, WheelCollider r)
    {
        float tl = 1f, tr = 1f;
        bool gl = l.GetGroundHit(out var hl), gr = r.GetGroundHit(out var hr);
        if (gl) tl = (-l.transform.InverseTransformPoint(hl.point).y - l.radius) / l.suspensionDistance;
        if (gr) tr = (-r.transform.InverseTransformPoint(hr.point).y - r.radius) / r.suspensionDistance;
        float f = (tl - tr) * antiRoll;
        if (gl) rb.AddForceAtPosition(l.transform.up * -f, l.transform.position);
        if (gr) rb.AddForceAtPosition(r.transform.up * f, r.transform.position);
    }

    void Update()
    {
        for (int i = 0; i < 4; i++)
        {
            if (!wheels[i] || !visuals[i]) continue;
            wheels[i].GetWorldPose(out var p, out var q);
            visuals[i].SetPositionAndRotation(p, q * Quaternion.Euler(0f, 0f, 90f));   // 円柱を横向きに
        }
    }

    // その場に置き直す（止めて向きをそろえる）
    public void Place(Vector3 pos, Quaternion rot)
    {
#if UNITY_6000_0_OR_NEWER
        rb.linearVelocity = Vector3.zero;
#else
        rb.velocity = Vector3.zero;
#endif
        rb.angularVelocity = Vector3.zero;
        rb.position = pos; rb.rotation = rot;
        transform.SetPositionAndRotation(pos, rot);
        steer = 0f;
        foreach (var w in wheels) if (w) { w.motorTorque = 0f; w.brakeTorque = maxBrake; }
    }
}
