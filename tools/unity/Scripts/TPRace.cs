// タイム計測: スタートラインを越えたら計測開始、ゴールラインで止める。ゴールの4秒後にスタートの手前へ戻る。
// R キーでいつでもスタートへ戻る。道から大きく落ちたときも戻す。ベストタイムは PlayerPrefs に保存。
using UnityEngine;
#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

public class TPRace : MonoBehaviour
{
    public TextAsset roadJson;
    public TPCar car;

    TPRoadData road;
    int idx;
    enum S { Ready, Run, Done }
    S s;
    float t0, last = -1f, best = -1f, doneAt;
    GUIStyle big, small;

    void Start()
    {
        road = TPRoadData.Load(roadJson);
        best = PlayerPrefs.GetFloat("tp_best", -1f);
        Respawn();
    }

    public void Respawn()
    {
        int i = Mathf.Max(0, road.start - 8);                      // スタートの約30m手前
        Vector3 p = road.Surface(i, -road.hw * 0.4f) + Vector3.up * 0.6f;
        car.Place(p, Quaternion.LookRotation(road.Forward(i), Vector3.up));
        idx = i; s = S.Ready;
    }

    void Update()
    {
        bool r;
#if ENABLE_INPUT_SYSTEM
        r = Keyboard.current != null && Keyboard.current.rKey.wasPressedThisFrame;
#else
        r = Input.GetKeyDown(KeyCode.R);
#endif
        if (r) { Respawn(); return; }

        int prev = idx;
        idx = road.Nearest(car.transform.position, idx, 25);
        if (car.transform.position.y < road.y[idx] - 25f) { Respawn(); return; }   // 道から落ちた

        if (s == S.Ready && prev < road.start && idx >= road.start) { s = S.Run; t0 = Time.time; }
        if (s == S.Run && prev < road.fin && idx >= road.fin)
        {
            last = Time.time - t0; s = S.Done; doneAt = Time.time;
            if (best < 0f || last < best) { best = last; PlayerPrefs.SetFloat("tp_best", best); PlayerPrefs.Save(); }
        }
        if (s == S.Done && Time.time - doneAt > 4f) Respawn();
        car.controllable = s != S.Done || Time.time - doneAt < 0.5f;
    }

    static string Fmt(float t) => t < 0f ? "-:--.---" : $"{(int)(t / 60f)}:{t % 60f:00.000}";

    void OnGUI()
    {
        if (big == null)
        {
            big = new GUIStyle(GUI.skin.label) { fontSize = 40, fontStyle = FontStyle.Bold };
            small = new GUIStyle(GUI.skin.label) { fontSize = 20 };
            big.normal.textColor = small.normal.textColor = Color.white;
        }
        // 画面の高さ 720 を基準に文字を拡大・縮小
        float k = Screen.height / 720f; GUI.matrix = Matrix4x4.Scale(new Vector3(k, k, 1f));
        float W = Screen.width / k, H = Screen.height / k;
        float t = s == S.Run ? Time.time - t0 : s == S.Done ? last : 0f;
        GUI.Label(new Rect(24, 16, 600, 50), Fmt(t), big);
        GUI.Label(new Rect(24, 60, 600, 30), $"ベスト {Fmt(best)}　　前回 {Fmt(last)}", small);
        float left = Mathf.Max(0, road.fin - idx) * 4f;
        string st = s == S.Ready ? "スタートラインを越えると計測開始" : s == S.Run ? $"ゴールまで {left / 1000f:0.0} km" : "ゴール！";
        GUI.Label(new Rect(24, 88, 600, 30), st, small);
        GUI.Label(new Rect(W - 220, H - 70, 200, 50), $"{car.Kmh:0} km/h", big);
        GUI.Label(new Rect(24, H - 34, 900, 30), "W/↑ アクセル  S/↓ ブレーキ  A/D ハンドル  Space サイド  C 視点  R スタートへ", small);
    }
}
