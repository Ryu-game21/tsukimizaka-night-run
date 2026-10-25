// 箱根ターンパイクの道路データ（Data/road.json）。座標は Unity 座標（x=東, y=上, z=北, 原点=スタートライン）、メートル。
// 道の形: © OpenStreetMap contributors (ODbL) / 標高: 国土地理院
using System;
using UnityEngine;

[Serializable]
public class TPTerrainInfo
{
    public float x0, z0, size, hmin, hmax;   // 地形の南西の角・一辺の長さ・高さの範囲
    public int res;                          // 高さ画像の解像度（res x res）
}

[Serializable]
public class TPFarInfo
{
    public float x0, z0, sizeX, sizeZ, hmin, hmax;   // 遠景の地形（富士山・相模湾）
    public int res;
}

[Serializable]
public class TPRoadData
{
    public string id;
    public float[] x, y, z;      // 道の中心線（4m 間隔、スタート手前の直線とゴール後の直線を含む）
    public float[] bankR;        // バンク: 進行方向の右へ 1m 行くごとの高さの変化
    public int[] bridge;         // 1 = 橋
    public float hw;             // 道の半幅（m）
    public int start, fin;       // スタートライン・ゴールラインの点の番号
    public TPTerrainInfo terrain;
    public TPFarInfo far;
    public string credit;

    public static TPRoadData Load(TextAsset json) => JsonUtility.FromJson<TPRoadData>(json.text);

    public int Count => x.Length;
    public Vector3 Point(int i) => new Vector3(x[i], y[i], z[i]);

    // 進行方向（水平）
    public Vector3 Forward(int i)
    {
        int a = Mathf.Max(0, i - 1), b = Mathf.Min(Count - 1, i + 1);
        Vector3 d = Point(b) - Point(a); d.y = 0;
        return d.sqrMagnitude > 1e-6f ? d.normalized : Vector3.forward;
    }

    // 進行方向の右
    public Vector3 Right(int i) => Vector3.Cross(Vector3.up, Forward(i));

    // 道の上の点（右へ off メートル、バンク込み）
    public Vector3 Surface(int i, float off) => Point(i) + Right(i) * off + Vector3.up * (bankR[i] * off);

    // pos に一番近い点を、前回の番号 from の前後 win 個から探す
    public int Nearest(Vector3 pos, int from, int win)
    {
        int best = Mathf.Clamp(from, 0, Count - 1); float bd = float.MaxValue;
        for (int k = Mathf.Max(0, from - win); k <= Mathf.Min(Count - 1, from + win); k++)
        {
            float dx = x[k] - pos.x, dz = z[k] - pos.z, d = dx * dx + dz * dz;
            if (d < bd) { bd = d; best = k; }
        }
        return best;
    }
}
