// 車を追いかけるカメラ。C キーで「後ろから」と「ボンネットの上」を切り替え。
using UnityEngine;
#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

public class TPCamera : MonoBehaviour
{
    public Transform target;
    public float back = 6.8f, up = 2.3f, smooth = 6f;
    bool hood;
    Vector3 vel;

    void LateUpdate()
    {
        if (!target) return;
        bool toggle;
#if ENABLE_INPUT_SYSTEM
        toggle = Keyboard.current != null && Keyboard.current.cKey.wasPressedThisFrame;
#else
        toggle = Input.GetKeyDown(KeyCode.C);
#endif
        if (toggle) hood = !hood;

        Vector3 fwd = target.forward; fwd.y = 0f;
        if (fwd.sqrMagnitude < 1e-4f) fwd = Vector3.forward;
        fwd.Normalize();
        if (hood)
        {
            transform.position = target.position + target.up * 1.25f + target.forward * 0.6f;
            transform.rotation = Quaternion.LookRotation(target.forward, Vector3.up);
            return;
        }
        Vector3 want = target.position - fwd * back + Vector3.up * up;
        transform.position = Vector3.SmoothDamp(transform.position, want, ref vel, 1f / smooth);
        transform.rotation = Quaternion.LookRotation(target.position + fwd * 6f + Vector3.up * 0.8f - transform.position, Vector3.up);
    }
}
