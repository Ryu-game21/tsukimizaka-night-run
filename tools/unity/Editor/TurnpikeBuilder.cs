// メニュー「Turnpike > シーンを作る」で、箱根ターンパイクのシーンを自動で組み立てる（URP 用）。
// - 地形: 国土地理院の標高（12km 四方）＋遠景（富士山〜相模湾、約50km）。地面・木・草はプロジェクトにある素材を自動で探して使う
//   （Asset Store の Terrain Sample Asset Pack など。名前に grass / rock / cliff / dirt / tree / pine / fir などを含むもの）。
//   見つからなければスクリプトで作った素材を使う。
// - 道路: 舗装（凹凸の法線マップつき）・白線・黄色のセンターライン・路肩・W 形のガードレールと支柱・反射板・カーブの矢印板
// - 光: 空（Procedural Skybox）・太陽の影・霧・ポストプロセス（ACES・ブルーム・色調・周辺減光・少しのモーションブラー）
// - 車: Assets/Turnpike/Car/gt3rs.glb（glTFast が入っていれば本物のモデル、なければ箱の車）
// 何度でも押し直せる（Generated フォルダとシーンを上書き）。
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

public static class TurnpikeBuilder
{
    const string ROOT = "Assets/Turnpike", GEN = ROOT + "/Generated";
    static float[,] roadDist;          // 地形と同じ範囲の格子での「道の中心線からの距離」（m、遠い所は 999）
    static int distRes;

    [MenuItem("Turnpike/シーンを作る (Build Scene)")]
    public static void Build()
    {
        var json = AssetDatabase.LoadAssetAtPath<TextAsset>(ROOT + "/Data/road.json");
        var hb = AssetDatabase.LoadAssetAtPath<TextAsset>(ROOT + "/Data/heights.bytes");
        var fb = AssetDatabase.LoadAssetAtPath<TextAsset>(ROOT + "/Data/far.bytes");
        if (!json || !hb) { EditorUtility.DisplayDialog("Turnpike", "Assets/Turnpike/Data に road.json と heights.bytes が見つかりません。", "OK"); return; }
        if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
        var road = TPRoadData.Load(json);
        Directory.CreateDirectory(GEN);

        try
        {
            Progress("シーンを準備しています…", 0.02f);
            var scene = EditorSceneManager.NewScene(NewSceneSetup.DefaultGameObjects, NewSceneMode.Single);
            SetupPipeline();

            Progress("地形を作っています…", 0.08f);
            var ter = BuildTerrain(road, hb.bytes);
            Progress("森と草を植えています…", 0.4f);
            PlantTrees(road, ter);
            PlantGrass(road, ter);
            if (fb && road.far != null && road.far.res > 0) { Progress("遠くの山（富士山）を作っています…", 0.55f); BuildFarTerrain(road, fb.bytes); }

            Progress("道路を作っています…", 0.65f);
            BuildRoad(road);
            BuildChevrons(road);
            BuildGate(road, road.start, "Start", new Color(0.92f, 0.92f, 0.92f));
            BuildGate(road, road.fin, "Finish", new Color(1f, 0.8f, 0.15f));
            BuildSea(road);

            Progress("車・カメラ・光を整えています…", 0.85f);
            var car = BuildCar();
            var race = new GameObject("Race").AddComponent<TPRace>();
            race.roadJson = json; race.car = car;
            int i0 = Mathf.Max(0, road.start - 8);
            car.transform.SetPositionAndRotation(road.Surface(i0, -road.hw * 0.4f) + Vector3.up * 0.6f, Quaternion.LookRotation(road.Forward(i0)));
            SetupLightAndCamera(car);

            EditorSceneManager.SaveScene(scene, ROOT + "/Turnpike.unity");
            AssetDatabase.SaveAssets();
            Debug.Log("Turnpike: シーンを作りました（Assets/Turnpike/Turnpike.unity）。再生ボタンで走れます。" + road.credit);
        }
        finally { EditorUtility.ClearProgressBar(); roadDist = null; }
    }

    static void Progress(string msg, float t) => EditorUtility.DisplayProgressBar("Turnpike", msg, t);

    // ---------- URP の設定（影の距離・HDR・MSAA） ----------
    static void SetupPipeline()
    {
        var rp = (QualitySettings.renderPipeline ? QualitySettings.renderPipeline : GraphicsSettings.defaultRenderPipeline) as UniversalRenderPipelineAsset;
        if (!rp) { Debug.LogWarning("Turnpike: URP ではないプロジェクトです。見た目の一部（影・ポストプロセス）が効きません。"); return; }
        rp.shadowDistance = 320f; rp.shadowCascadeCount = 4; rp.supportsHDR = true; rp.msaaSampleCount = 4;
        EditorUtility.SetDirty(rp);
    }

    // ---------- 地形（国土地理院の標高） ----------
    static Terrain BuildTerrain(TPRoadData road, byte[] hb)
    {
        var t = road.terrain; int res = t.res;
        var td = new TerrainData();
        td.heightmapResolution = res;
        td.size = new Vector3(t.size, t.hmax - t.hmin, t.size);
        td.SetHeights(0, 0, ReadHeights(hb, res));

        distRes = 2048; td.alphamapResolution = distRes;
        BuildRoadDistance(road, t.x0, t.z0, t.size, distRes);

        // 地面の素材: 草地・森の地面 / 岩・崖 / 土（路肩）
        var lGrass = FindLayer(new[] { "grass", "meadow", "moss", "forest" }) ?? MakeLayer("grass", NoiseTex(512, new Color(0.22f, 0.32f, 0.15f), new Color(0.12f, 0.2f, 0.09f), 7), 18);
        var lRock = FindLayer(new[] { "cliff", "rock", "stone" }) ?? MakeLayer("rock", NoiseTex(512, new Color(0.46f, 0.43f, 0.37f), new Color(0.3f, 0.28f, 0.25f), 11), 14);
        var lDirt = FindLayer(new[] { "dirt", "soil", "mud", "gravel", "ground" }) ?? MakeLayer("dirt", NoiseTex(512, new Color(0.38f, 0.32f, 0.24f), new Color(0.25f, 0.21f, 0.16f), 13), 10);
        td.terrainLayers = new[] { lGrass, lRock, lDirt };
        var a = new float[distRes, distRes, 3];
        for (int j = 0; j < distRes; j++)
            for (int i = 0; i < distRes; i++)
            {
                float u = (i + 0.5f) / distRes, v = (j + 0.5f) / distRes;
                float s = td.GetSteepness(u, v), h = td.GetInterpolatedHeight(u, v) + t.hmin;
                float rock = Mathf.Clamp01((s - 30f) / 12f);
                float dirt = Mathf.Clamp01(1f - (roadDist[j, i] - 9f) / 6f) * (1f - rock) + (h < 4f ? 1f : 0f);
                dirt = Mathf.Clamp01(dirt + Mathf.PerlinNoise(i * 0.05f, j * 0.05f) * 0.25f * (1f - rock) - 0.1f);
                float grass = Mathf.Max(0f, 1f - rock - dirt);
                float sum = Mathf.Max(1e-4f, grass + rock + dirt);
                a[j, i, 0] = grass / sum; a[j, i, 1] = rock / sum; a[j, i, 2] = dirt / sum;
            }
        td.SetAlphamaps(0, 0, a);
        SaveAsset(td, GEN + "/TerrainData.asset");

        var go = Terrain.CreateTerrainGameObject(td);
        go.name = "Terrain"; go.transform.position = new Vector3(t.x0, t.hmin, t.z0);
        var ter = go.GetComponent<Terrain>();
        ter.heightmapPixelError = 2f; ter.basemapDistance = 1500f; ter.drawInstanced = true;
        ter.treeDistance = 1600f; ter.treeBillboardDistance = 300f; ter.treeCrossFadeLength = 30f; ter.treeMaximumFullLODCount = 400;
        ter.detailObjectDistance = 140f; ter.detailObjectDensity = 1f;
        return ter;
    }

    static float[,] ReadHeights(byte[] hb, int res)
    {
        var h = new float[res, res];
        for (int j = 0; j < res; j++)
            for (int i = 0; i < res; i++) { int o = (j * res + i) * 2; h[j, i] = (hb[o] | (hb[o + 1] << 8)) / 65535f; }
        return h;
    }

    static void BuildRoadDistance(TPRoadData road, float x0, float z0, float size, int n)
    {
        roadDist = new float[n, n];
        for (int j = 0; j < n; j++) for (int i = 0; i < n; i++) roadDist[j, i] = 999f;
        float cell = size / n; int R = Mathf.CeilToInt(75f / cell);
        for (int k = 0; k < road.Count; k++)
        {
            float px = road.x[k], pz = road.z[k];
            int ci = Mathf.FloorToInt((px - x0) / cell), cj = Mathf.FloorToInt((pz - z0) / cell);
            for (int dj = -R; dj <= R; dj++)
                for (int di = -R; di <= R; di++)
                {
                    int i = ci + di, j = cj + dj; if (i < 0 || j < 0 || i >= n || j >= n) continue;
                    float cx = x0 + (i + 0.5f) * cell - px, cz = z0 + (j + 0.5f) * cell - pz, d = Mathf.Sqrt(cx * cx + cz * cz);
                    if (d < roadDist[j, i]) roadDist[j, i] = d;
                }
        }
    }

    static float DistAt(float u, float v)
    {
        int i = Mathf.Clamp((int)(u * distRes), 0, distRes - 1), j = Mathf.Clamp((int)(v * distRes), 0, distRes - 1);
        return roadDist[j, i];
    }

    // ---------- 森（地形の木） ----------
    static void PlantTrees(TPRoadData road, Terrain ter)
    {
        var td = ter.terrainData;
        var prefabs = FindPrefabs(new[] { "tree", "pine", "fir", "conifer", "spruce", "cedar", "sugi", "hinoki", "larch" }, new[] { "dead", "stump", "log", "bush", "branch", "leaf", "fallen" }, 6);
        if (prefabs.Count == 0) { prefabs.Add(MakeConifer("conifer_a", 1f)); prefabs.Add(MakeConifer("conifer_b", 1.25f)); }
        else Debug.Log("Turnpike: 木の素材 " + string.Join(", ", prefabs.ConvertAll(p => p.name)));
        td.treePrototypes = prefabs.ConvertAll(p => new TreePrototype { prefab = p }).ToArray();
        var rnd = new System.Random(3); var list = new List<TreeInstance>();
        var t = road.terrain;
        for (int k = 0; k < 220000 && list.Count < 60000; k++)
        {
            int ri = rnd.Next(road.Count);
            float side = rnd.NextDouble() < 0.5 ? -1f : 1f, off = 12f + (float)(rnd.NextDouble() * rnd.NextDouble()) * 650f;
            Vector3 p = road.Point(ri) + road.Right(ri) * side * off + road.Forward(ri) * (float)(rnd.NextDouble() * 60 - 30);
            float u = (p.x - t.x0) / t.size, v = (p.z - t.z0) / t.size;
            if (u <= 0 || v <= 0 || u >= 1 || v >= 1) continue;
            if (DistAt(u, v) < 12.5f) continue;                            // 道とガードレールの近くには植えない
            float s = td.GetSteepness(u, v), h = td.GetInterpolatedHeight(u, v) + t.hmin;
            if (s > 44f || h < 5f) continue;
            if (h > 900f && rnd.NextDouble() < 0.55) continue;             // 尾根の上は木がまばら（笹原）
            float sc = 0.8f + (float)rnd.NextDouble() * 0.6f;
            list.Add(new TreeInstance
            {
                position = new Vector3(u, 0, v), prototypeIndex = rnd.Next(prefabs.Count), widthScale = sc, heightScale = sc * (0.9f + (float)rnd.NextDouble() * 0.3f),
                rotation = (float)(rnd.NextDouble() * Mathf.PI * 2), color = Color.Lerp(new Color(0.85f, 0.9f, 0.85f), Color.white, (float)rnd.NextDouble()), lightmapColor = Color.white
            });
        }
        td.SetTreeInstances(list.ToArray(), true);
    }

    // ---------- 草（素材があるときだけ） ----------
    static void PlantGrass(TPRoadData road, Terrain ter)
    {
        var grass = FindPrefabs(new[] { "grass" }, new[] { "dry", "dead" }, 2);
        var td = ter.terrainData;
        if (grass.Count == 0) return;
        Debug.Log("Turnpike: 草の素材 " + string.Join(", ", grass.ConvertAll(p => p.name)));
        td.detailPrototypes = grass.ConvertAll(g => new DetailPrototype
        {
            prototype = g, usePrototypeMesh = true, renderMode = DetailRenderMode.VertexLit, useInstancing = true,
            minWidth = 0.8f, maxWidth = 1.3f, minHeight = 0.7f, maxHeight = 1.3f, noiseSpread = 0.3f
        }).ToArray();
        int dr = 2048; td.SetDetailResolution(dr, 32);
        for (int l = 0; l < grass.Count; l++)
        {
            var layer = new int[dr, dr];
            for (int j = 0; j < dr; j++)
                for (int i = 0; i < dr; i++)
                {
                    float u = (i + 0.5f) / dr, v = (j + 0.5f) / dr, d = DistAt(u, v);
                    if (d < 9.5f || d > 70f) continue;
                    if (td.GetSteepness(u, v) > 32f) continue;
                    float n = Mathf.PerlinNoise(i * 0.08f + l * 31f, j * 0.08f);
                    layer[j, i] = Mathf.RoundToInt(n * 8f * Mathf.Clamp01(1.4f - d / 70f));
                }
            td.SetDetailLayer(0, 0, l, layer);
        }
    }

    // ---------- 遠景（富士山〜相模湾） ----------
    static void BuildFarTerrain(TPRoadData road, byte[] fb)
    {
        var f = road.far; var t = road.terrain;
        var td = new TerrainData();
        td.heightmapResolution = f.res;
        td.size = new Vector3(f.sizeX, f.hmax - f.hmin, f.sizeZ);
        td.SetHeights(0, 0, ReadHeights(fb, f.res));
        // 近景の地形がある所は穴をあける（重なってちらつかないように）
        int hr = f.res - 1; var solid = new bool[hr, hr];
        float cx = f.sizeX / hr, cz = f.sizeZ / hr;
        for (int j = 0; j < hr; j++)
            for (int i = 0; i < hr; i++)
            {
                float x0 = f.x0 + i * cx, z0 = f.z0 + j * cz;
                bool inside = x0 > t.x0 && x0 + cx < t.x0 + t.size && z0 > t.z0 && z0 + cz < t.z0 + t.size;
                solid[j, i] = !inside;
            }
        td.SetHoles(0, 0, solid);
        var forest = MakeLayer("far_forest", NoiseTex(128, new Color(0.17f, 0.25f, 0.14f), new Color(0.11f, 0.17f, 0.09f), 21), 200);
        var lava = MakeLayer("far_rock", NoiseTex(128, new Color(0.36f, 0.31f, 0.29f), new Color(0.25f, 0.22f, 0.21f), 23), 200);
        var snow = MakeLayer("far_snow", NoiseTex(128, new Color(0.93f, 0.95f, 0.98f), new Color(0.82f, 0.85f, 0.9f), 25), 200);
        td.terrainLayers = new[] { forest, lava, snow };
        int ar = 512; td.alphamapResolution = ar; var a = new float[ar, ar, 3];
        for (int j = 0; j < ar; j++)
            for (int i = 0; i < ar; i++)
            {
                float u = (i + 0.5f) / ar, v = (j + 0.5f) / ar, h = td.GetInterpolatedHeight(u, v) + f.hmin;
                float sn = Mathf.Clamp01((h - 3150f) / 250f), lv = Mathf.Clamp01((h - 2300f) / 400f) * (1f - sn);
                a[j, i, 0] = 1f - sn - lv; a[j, i, 1] = lv; a[j, i, 2] = sn;
            }
        td.SetAlphamaps(0, 0, a);
        SaveAsset(td, GEN + "/FarTerrainData.asset");
        var go = Terrain.CreateTerrainGameObject(td); go.name = "FarTerrain";
        go.transform.position = new Vector3(f.x0, f.hmin, f.z0);
        var ter = go.GetComponent<Terrain>();
        ter.heightmapPixelError = 12f; ter.basemapDistance = 100000f; ter.shadowCastingMode = ShadowCastingMode.Off; ter.drawInstanced = true;
        Object.DestroyImmediate(go.GetComponent<TerrainCollider>());
    }

    // ---------- 道路・路肩・ガードレール ----------
    static void BuildRoad(TPRoadData road)
    {
        int n = road.Count; float hw = road.hw, rail = hw + 2.2f;
        var parent = new GameObject("Road");

        // 路面と路肩
        var rv = new Vector3[n * 2]; var ruv = new Vector2[n * 2];
        var sv = new Vector3[n * 4]; var suv = new Vector2[n * 4];
        float dist = 0f;
        for (int i = 0; i < n; i++)
        {
            if (i > 0) dist += Vector3.Distance(road.Point(i), road.Point(i - 1));
            rv[i * 2] = road.Surface(i, -hw); rv[i * 2 + 1] = road.Surface(i, hw);
            ruv[i * 2] = new Vector2(0, dist / 12f); ruv[i * 2 + 1] = new Vector2(1, dist / 12f);
            sv[i * 4] = road.Surface(i, -rail - 0.6f) - Vector3.up * 0.05f; sv[i * 4 + 1] = road.Surface(i, -hw) - Vector3.up * 0.015f;
            sv[i * 4 + 2] = road.Surface(i, hw) - Vector3.up * 0.015f; sv[i * 4 + 3] = road.Surface(i, rail + 0.6f) - Vector3.up * 0.05f;
            suv[i * 4] = new Vector2(0, dist / 4f); suv[i * 4 + 1] = new Vector2(0.8f, dist / 4f); suv[i * 4 + 2] = new Vector2(0.8f, dist / 4f); suv[i * 4 + 3] = new Vector2(0, dist / 4f);
        }
        var surf = NewMesh("road", rv, ruv, Strip(n, 2, 0));
        var st = new List<int>(Strip(n, 4, 0)); st.AddRange(Strip(n, 4, 2));
        var sh = NewMesh("shoulder", sv, suv, st.ToArray());
        RoadTextures(out var albedo, out var normal);
        MeshObj("Surface", surf, Mat("road", albedo, Color.white, 0.32f, 0f, normal), parent, true);
        var shTex = SaveTex(NoiseTex(256, new Color(0.4f, 0.38f, 0.34f), new Color(0.26f, 0.25f, 0.22f), 3), "tex_shoulder", false);
        MeshObj("Shoulder", sh, Mat("shoulder", shTex, Color.white, 0.08f), parent, true);

        // W 形ガードレール（断面を道に沿って押し出す、内向きと外向きの両面）
        Vector2[] prof = { new Vector2(0f, 0.43f), new Vector2(0.05f, 0.5f), new Vector2(0.0f, 0.58f), new Vector2(0.05f, 0.66f), new Vector2(0f, 0.74f), new Vector2(0.05f, 0.8f) };
        var gv = new List<Vector3>(); var gt = new List<int>(); var guv = new List<Vector2>();
        foreach (float side in new[] { -1f, 1f })
            for (int face = 0; face < 2; face++)
            {
                int b0 = gv.Count; float d2 = 0f;
                for (int i = 0; i < n; i++)
                {
                    if (i > 0) d2 += Vector3.Distance(road.Point(i), road.Point(i - 1));
                    Vector3 cen = road.Surface(i, side * rail), rr = road.Right(i) * side;
                    for (int q = 0; q < prof.Length; q++) { gv.Add(cen + rr * (prof[q].x - 0.08f) + Vector3.up * prof[q].y); guv.Add(new Vector2(q / (float)(prof.Length - 1), d2 / 4f)); }
                }
                int m = prof.Length;
                bool flip = (side > 0) ^ (face == 1);
                for (int i = 0; i < n - 1; i++)
                    for (int q = 0; q < m - 1; q++)
                    {
                        int a = b0 + i * m + q, b = a + 1, c = a + m, d = c + 1;
                        if (flip) gt.AddRange(new[] { a, c, b, b, c, d }); else gt.AddRange(new[] { a, b, c, c, b, d });
                    }
            }
        var railMesh = NewMesh("rails", gv.ToArray(), guv.ToArray(), gt.ToArray());
        MeshObj("Guardrail", railMesh, Mat("rail", SaveTex(NoiseTex(64, new Color(0.8f, 0.82f, 0.84f), new Color(0.66f, 0.68f, 0.7f), 5), "tex_rail", false), Color.white, 0.62f, 0.75f), parent, false);

        // 当たり判定用の見えない壁
        var w = new Vector3[n * 4];
        for (int i = 0; i < n; i++)
        {
            Vector3 L = road.Surface(i, -rail), R = road.Surface(i, rail);
            w[i * 4] = L - Vector3.up; w[i * 4 + 1] = L + Vector3.up * 1.6f; w[i * 4 + 2] = R - Vector3.up; w[i * 4 + 3] = R + Vector3.up * 1.6f;
        }
        var wt = new List<int>(Strip(n, 4, 0)); wt.AddRange(Strip(n, 4, 2));
        var wall = new GameObject("GuardrailCollider"); wall.transform.SetParent(parent.transform);
        wall.AddComponent<MeshCollider>().sharedMesh = NewMesh("railWalls", w, null, wt.ToArray());

        // 支柱（4m おき）と反射板（12m おき）を1つのメッシュに
        var pv = new List<Vector3>(); var pt = new List<int>(); var dv = new List<Vector3>(); var dt = new List<int>();
        for (int i = 0; i < n; i++)
            foreach (float side in new[] { -1f, 1f })
            {
                Vector3 cen = road.Surface(i, side * (rail + 0.1f)), fw = road.Forward(i), rr = road.Right(i);
                AddBox(pv, pt, cen + Vector3.up * 0.4f, fw, rr, new Vector3(0.1f, 0.95f, 0.15f));
                if (i % 3 == 0) AddBox(dv, dt, cen + Vector3.up * 0.98f - rr * side * 0.02f, fw, rr, new Vector3(0.09f, 0.09f, 0.04f));
            }
        MeshObj("Posts", NewMesh("posts", pv.ToArray(), null, pt.ToArray()), Mat("post", null, new Color(0.62f, 0.64f, 0.67f), 0.5f, 0.7f), parent, false);
        var refl = Mat("reflector", null, new Color(1f, 0.55f, 0.1f), 0.8f);
        refl.EnableKeyword("_EMISSION"); refl.SetColor("_EmissionColor", new Color(0.6f, 0.25f, 0.02f));
        MeshObj("Reflectors", NewMesh("reflectors", dv.ToArray(), null, dt.ToArray()), refl, parent, false);
    }

    // ---------- カーブの矢印板（半径 150m より急なカーブの外側） ----------
    static void BuildChevrons(TPRoadData road)
    {
        int n = road.Count; float rail = road.hw + 2.2f;
        var v = new List<Vector3>(); var uv = new List<Vector2>(); var tr = new List<int>();
        for (int i = 10; i < n - 10; i += 4)
        {
            Vector3 fa = road.Forward(i - 10), fb = road.Forward(i + 10);
            float ang = Vector3.SignedAngle(fa, fb, Vector3.up) * Mathf.Deg2Rad; if (Mathf.Abs(ang) < 1e-3f) continue;
            float R = 80f / Mathf.Abs(ang); if (R > 150f) continue;
            float outS = ang > 0 ? -1f : 1f;                         // 右カーブ（ang>0）なら左側が外側
            Vector3 cen = road.Surface(i, outS * (rail + 0.9f)) + Vector3.up * 1.5f, rr = road.Right(i);
            Vector3 hx = rr * 0.6f, hy = Vector3.up * 0.6f; int b0 = v.Count;
            v.Add(cen - hx - hy); v.Add(cen + hx - hy); v.Add(cen - hx + hy); v.Add(cen + hx + hy);
            float u0 = ang > 0 ? 1f : 0f, u1 = 1f - u0;              // テクスチャの矢印は左向き。右カーブでは左右反転
            uv.Add(new Vector2(u0, 0)); uv.Add(new Vector2(u1, 0)); uv.Add(new Vector2(u0, 1)); uv.Add(new Vector2(u1, 1));
            tr.AddRange(new[] { b0, b0 + 2, b0 + 1, b0 + 1, b0 + 2, b0 + 3 });   // 運転手の方を向く面
        }
        if (v.Count == 0) return;
        var tex = new Texture2D(128, 128);
        for (int y = 0; y < 128; y++)
            for (int x = 0; x < 128; x++)
            {
                bool border = x < 5 || y < 5 || x > 122 || y > 122;
                float px = x % 64, py = Mathf.Abs(y - 64f);
                bool arrow = px - py * 0.75f > 6f && px - py * 0.75f < 34f;
                tex.SetPixel(x, y, border || arrow ? new Color(0.06f, 0.06f, 0.06f) : new Color(0.98f, 0.76f, 0.05f));
            }
        tex.Apply();
        var m = Mat("chevron", SaveTex(tex, "tex_chevron", false), Color.white, 0.4f);
        m.EnableKeyword("_EMISSION"); m.SetColor("_EmissionColor", new Color(0.15f, 0.1f, 0f));
        MeshObj("Chevrons", NewMesh("chevrons", v.ToArray(), uv.ToArray(), tr.ToArray()), m, null, false);
    }

    // ---------- スタート・ゴールのゲート ----------
    static void BuildGate(TPRoadData road, int i, string name, Color col)
    {
        var g = new GameObject(name); g.transform.position = road.Point(i); g.transform.rotation = Quaternion.LookRotation(road.Forward(i));
        var m = Mat("gate_" + name, null, col, 0.4f, 0.3f);
        float x = road.hw + 1.6f;
        foreach (float s in new[] { -1f, 1f })
        {
            var p = GameObject.CreatePrimitive(PrimitiveType.Cube); p.transform.SetParent(g.transform, false);
            p.transform.localPosition = new Vector3(s * x, 3.6f, 0); p.transform.localScale = new Vector3(0.4f, 7.2f, 0.4f);
            p.GetComponent<MeshRenderer>().sharedMaterial = m;
        }
        var b = GameObject.CreatePrimitive(PrimitiveType.Cube); b.transform.SetParent(g.transform, false);
        b.transform.localPosition = new Vector3(0, 7.4f, 0); b.transform.localScale = new Vector3(x * 2 + 0.4f, 1.3f, 0.3f);
        b.GetComponent<MeshRenderer>().sharedMaterial = m;
        var line = GameObject.CreatePrimitive(PrimitiveType.Quad); Object.DestroyImmediate(line.GetComponent<Collider>());
        line.transform.SetParent(g.transform, false); line.transform.localPosition = new Vector3(0, 0.02f, 0);
        line.transform.localRotation = Quaternion.Euler(90f, 0, 0); line.transform.localScale = new Vector3(road.hw * 2, 1.6f, 1);
        var chk = new Texture2D(32, 4) { filterMode = FilterMode.Point };
        for (int yy = 0; yy < 4; yy++) for (int xx = 0; xx < 32; xx++) chk.SetPixel(xx, yy, (xx + yy) % 2 == 0 ? Color.white : new Color(0.08f, 0.08f, 0.08f));
        chk.Apply();
        line.GetComponent<MeshRenderer>().sharedMaterial = Mat("check_" + name, SaveTex(chk, "tex_check_" + name, false), Color.white, 0.3f);
    }

    // ---------- 海（相模湾） ----------
    static void BuildSea(TPRoadData road)
    {
        var sea = GameObject.CreatePrimitive(PrimitiveType.Plane); sea.name = "Sea";
        Object.DestroyImmediate(sea.GetComponent<Collider>());
        var t = road.terrain;
        sea.transform.position = new Vector3(t.x0 + t.size / 2, 0f, t.z0 + t.size / 2);
        sea.transform.localScale = new Vector3(9000f, 1, 9000f);
        sea.GetComponent<MeshRenderer>().sharedMaterial = Mat("sea", null, new Color(0.08f, 0.24f, 0.36f), 0.93f);
        sea.GetComponent<MeshRenderer>().shadowCastingMode = ShadowCastingMode.Off;
    }

    // ---------- 車（本物のモデルがあればそれ、なければ箱） ----------
    static TPCar BuildCar()
    {
        var car = new GameObject("Car");
        car.AddComponent<Rigidbody>().mass = 1400f;
        var tc = car.AddComponent<TPCar>();
        var model = AssetDatabase.LoadAssetAtPath<GameObject>(ROOT + "/Car/gt3rs.glb");
        string[] nm = { "FL", "FR", "RL", "RR" };
        var wheelsVis = new Transform[4];
        if (model)
        {
            var inst = (GameObject)PrefabUtility.InstantiatePrefab(model, car.transform);
            inst.transform.localPosition = Vector3.zero; inst.transform.localRotation = Quaternion.identity;
            foreach (var col in inst.GetComponentsInChildren<Collider>()) Object.DestroyImmediate(col);
            for (int i = 0; i < 4; i++) wheelsVis[i] = FindDeep(inst.transform, "Wheel_" + nm[i]);
            var box = car.AddComponent<BoxCollider>(); box.center = new Vector3(0, 0.72f, 0.05f); box.size = new Vector3(1.85f, 0.95f, 4.45f);
            tc.visualEuler = Vector3.zero;
            Debug.Log("Turnpike: 車のモデル（Porsche GT3 RS by Black Snow, CC BY 4.0）を使いました。");
        }
        else
        {
            Debug.LogWarning("Turnpike: Car/gt3rs.glb が読めません（glTFast が入っていない？）。箱の車で作ります。");
            var body = GameObject.CreatePrimitive(PrimitiveType.Cube); body.name = "Body"; body.transform.SetParent(car.transform, false);
            body.transform.localPosition = new Vector3(0, 0.62f, 0); body.transform.localScale = new Vector3(1.85f, 0.5f, 4.4f);
            body.GetComponent<MeshRenderer>().sharedMaterial = Mat("car_body", null, new Color(0.75f, 0.08f, 0.1f), 0.75f);
        }
        Vector3[] pos = { new Vector3(-0.77f, 0.39f, 1.23f), new Vector3(0.77f, 0.39f, 1.23f), new Vector3(-0.77f, 0.39f, -1.23f), new Vector3(0.77f, 0.39f, -1.23f) };
        var tyre = Mat("car_tyre", null, new Color(0.06f, 0.06f, 0.06f), 0.2f);
        for (int i = 0; i < 4; i++)
        {
            Vector3 p = wheelsVis[i] ? car.transform.InverseTransformPoint(wheelsVis[i].position) : pos[i];
            var wgo = new GameObject("WheelCollider_" + nm[i]); wgo.transform.SetParent(car.transform, false);
            wgo.transform.localPosition = p + Vector3.up * 0.07f;
            var wc = wgo.AddComponent<WheelCollider>(); wc.radius = model ? 0.39f : 0.34f; wc.suspensionDistance = 0.16f;
            if (!wheelsVis[i])
            {
                var vis = GameObject.CreatePrimitive(PrimitiveType.Cylinder); vis.name = "Tyre_" + nm[i];
                Object.DestroyImmediate(vis.GetComponent<Collider>());
                vis.transform.SetParent(car.transform, false); vis.transform.localPosition = pos[i];
                vis.transform.localRotation = Quaternion.Euler(0, 0, 90); vis.transform.localScale = new Vector3(0.68f, 0.13f, 0.68f);
                vis.GetComponent<MeshRenderer>().sharedMaterial = tyre;
                wheelsVis[i] = vis.transform;
            }
            tc.wheels[i] = wc; tc.visuals[i] = wheelsVis[i];
        }
        return tc;
    }

    static Transform FindDeep(Transform t, string name)
    {
        if (t.name == name) return t;
        foreach (Transform c in t) { var r = FindDeep(c, name); if (r) return r; }
        return null;
    }

    // ---------- 光・空・霧・カメラ・ポストプロセス ----------
    static void SetupLightAndCamera(TPCar car)
    {
        var sun = Object.FindFirstObjectByType<Light>();
        if (sun)
        {
            sun.transform.rotation = Quaternion.Euler(34f, -48f, 0f); sun.intensity = 2.2f; sun.color = new Color(1f, 0.95f, 0.87f);
            sun.shadows = LightShadows.Soft; sun.shadowStrength = 0.85f; RenderSettings.sun = sun;
        }
        var sky = new Material(Shader.Find("Skybox/Procedural")) { name = "sky" };
        sky.SetFloat("_SunSize", 0.035f); sky.SetFloat("_SunSizeConvergence", 6f); sky.SetFloat("_AtmosphereThickness", 0.9f);
        sky.SetColor("_SkyTint", new Color(0.46f, 0.55f, 0.66f)); sky.SetColor("_GroundColor", new Color(0.35f, 0.38f, 0.4f)); sky.SetFloat("_Exposure", 1.25f);
        SaveAsset(sky, GEN + "/mat_sky.mat");
        RenderSettings.skybox = sky; RenderSettings.ambientMode = AmbientMode.Skybox; RenderSettings.ambientIntensity = 1.1f;
        RenderSettings.defaultReflectionMode = DefaultReflectionMode.Skybox;
        RenderSettings.fog = true; RenderSettings.fogMode = FogMode.Exponential; RenderSettings.fogDensity = 0.000075f;
        RenderSettings.fogColor = new Color(0.68f, 0.76f, 0.85f);
        DynamicGI.UpdateEnvironment();

        var cam = Camera.main;
        if (cam)
        {
            cam.farClipPlane = 60000f; cam.nearClipPlane = 0.25f; cam.fieldOfView = 58f; cam.allowHDR = true;
            var follow = cam.gameObject.AddComponent<TPCamera>(); follow.target = car.transform;
            cam.transform.position = car.transform.position - car.transform.forward * 7f + Vector3.up * 2.4f;
            cam.transform.LookAt(car.transform);
            var cd = cam.GetUniversalAdditionalCameraData();
            cd.renderPostProcessing = true; cd.antialiasing = AntialiasingMode.SubpixelMorphologicalAntiAliasing; cd.antialiasingQuality = AntialiasingQuality.High;
            cd.renderShadows = true; cd.stopNaN = true;   // 万一の NaN が画面に広がらないように
        }

        var prof = ScriptableObject.CreateInstance<VolumeProfile>();
        SaveAsset(prof, GEN + "/PostProfile.asset");
        var tm = prof.Add<Tonemapping>(true); tm.mode.Override(TonemappingMode.ACES);
        var bl = prof.Add<Bloom>(true); bl.threshold.Override(1.05f); bl.intensity.Override(0.35f); bl.scatter.Override(0.65f); bl.clamp.Override(20f);
        var ca = prof.Add<ColorAdjustments>(true); ca.postExposure.Override(0.25f); ca.contrast.Override(12f); ca.saturation.Override(8f);
        var wb = prof.Add<WhiteBalance>(true); wb.temperature.Override(4f);
        var vg = prof.Add<Vignette>(true); vg.intensity.Override(0.22f); vg.smoothness.Override(0.45f);
        var mb = prof.Add<MotionBlur>(true); mb.intensity.Override(0.18f); mb.quality.Override(MotionBlurQuality.Medium);
        foreach (var c in prof.components) AssetDatabase.AddObjectToAsset(c, prof);
        EditorUtility.SetDirty(prof);
        var vol = new GameObject("PostProcess").AddComponent<Volume>(); vol.isGlobal = true; vol.sharedProfile = prof;
    }

    // ---------- 素材を探す ----------
    static TerrainLayer FindLayer(string[] words)
    {
        foreach (var g in AssetDatabase.FindAssets("t:TerrainLayer"))
        {
            string p = AssetDatabase.GUIDToAssetPath(g); if (p.StartsWith(ROOT)) continue;
            string n = Path.GetFileNameWithoutExtension(p).ToLowerInvariant();
            foreach (var w in words) if (n.Contains(w)) { Debug.Log("Turnpike: 地面の素材 " + p); return AssetDatabase.LoadAssetAtPath<TerrainLayer>(p); }
        }
        return null;
    }

    static List<GameObject> FindPrefabs(string[] words, string[] not, int max)
    {
        var res = new List<GameObject>();
        foreach (var g in AssetDatabase.FindAssets("t:Prefab"))
        {
            string p = AssetDatabase.GUIDToAssetPath(g); if (p.StartsWith(ROOT)) continue;
            string n = Path.GetFileNameWithoutExtension(p).ToLowerInvariant(); bool ok = false;
            foreach (var w in words) if (n.Contains(w)) ok = true;
            foreach (var w in not) if (n.Contains(w)) ok = false;
            if (!ok) continue;
            var go = AssetDatabase.LoadAssetAtPath<GameObject>(p);
            if (go && go.GetComponentInChildren<MeshRenderer>()) res.Add(go);
            if (res.Count >= max) break;
        }
        return res;
    }

    // スクリプトで作る針葉樹（素材がないとき）: 幹＋5段の円すい
    static GameObject MakeConifer(string name, float k)
    {
        var v = new List<Vector3>(); var trunk = new List<int>(); var leaf = new List<int>();
        void Cone(float y0, float y1, float r, List<int> t, int seg)
        {
            int b = v.Count;
            for (int i = 0; i < seg; i++) { float a = i * Mathf.PI * 2 / seg; v.Add(new Vector3(Mathf.Cos(a) * r, y0, Mathf.Sin(a) * r)); }
            v.Add(new Vector3(0, y1, 0)); int top = v.Count - 1;
            for (int i = 0; i < seg; i++) { t.Add(b + i); t.Add(top); t.Add(b + (i + 1) % seg); }
        }
        Cone(0f, 7f * k, 0.28f * k, trunk, 7);
        for (int l = 0; l < 5; l++) { float y = (2.2f + l * 2.3f) * k; Cone(y, y + 4.2f * k, (2.6f - l * 0.42f) * k, leaf, 9); }
        var m = new Mesh { name = name }; m.SetVertices(v); m.subMeshCount = 2; m.SetTriangles(trunk, 0); m.SetTriangles(leaf, 1);
        m.RecalculateNormals(); m.RecalculateBounds();
        SaveAsset(m, GEN + "/" + name + ".asset");
        var go = new GameObject(name);
        go.AddComponent<MeshFilter>().sharedMesh = m;
        var bark = Mat("bark", null, new Color(0.25f, 0.18f, 0.12f), 0.1f);
        var needles = Mat("needles", null, new Color(0.11f, 0.2f, 0.1f), 0.05f);
        go.AddComponent<MeshRenderer>().sharedMaterials = new[] { bark, needles };
        var prefab = PrefabUtility.SaveAsPrefabAsset(go, GEN + "/" + name + ".prefab");
        Object.DestroyImmediate(go);
        return prefab;
    }

    // ---------- メッシュの小道具 ----------
    static Mesh NewMesh(string name, Vector3[] v, Vector2[] uv, int[] tri)
    {
        var m = new Mesh { name = name, indexFormat = IndexFormat.UInt32 };
        m.vertices = v; if (uv != null) m.uv = uv; m.triangles = tri;
        m.RecalculateNormals(); if (uv != null) m.RecalculateTangents(); m.RecalculateBounds();
        SaveAsset(m, GEN + "/" + name + ".asset");
        return m;
    }

    // 箱を足す（外向きの面だけ。両面にすると法線が打ち消し合って NaN になり、ブルームで白く爆発する）
    static void AddBox(List<Vector3> v, List<int> t, Vector3 c, Vector3 f, Vector3 r, Vector3 size)
    {
        Vector3 hx = r * size.x / 2, hy = Vector3.up * size.y / 2, hz = f * size.z / 2;
        int[] q = { 0, 2, 3, 1, 4, 5, 7, 6, 0, 1, 5, 4, 2, 6, 7, 3, 0, 4, 6, 2, 1, 3, 7, 5 };
        Vector3 P(int i) => c + ((i & 1) == 0 ? -hx : hx) + ((i & 2) == 0 ? -hy : hy) + ((i & 4) == 0 ? -hz : hz);
        for (int k = 0; k < 24; k += 4)
        {
            Vector3 p0 = P(q[k]), p1 = P(q[k + 1]), p2 = P(q[k + 2]), p3 = P(q[k + 3]);
            Vector3 fc = (p0 + p1 + p2 + p3) / 4f;
            bool flip = Vector3.Dot(Vector3.Cross(p1 - p0, p2 - p0), fc - c) < 0f;   // 時計回り＝外向きにそろえる
            int b = v.Count; v.Add(p0); v.Add(p1); v.Add(p2); v.Add(p3);            // 面ごとに頂点を分ける（角がくっきり）
            if (flip) { t.Add(b); t.Add(b + 2); t.Add(b + 1); t.Add(b); t.Add(b + 3); t.Add(b + 2); }
            else { t.Add(b); t.Add(b + 1); t.Add(b + 2); t.Add(b); t.Add(b + 2); t.Add(b + 3); }
        }
    }

    // 2列（または4列のうち隣り合う2列）の頂点を帯の三角形にする。上から見て時計回り＝表
    static int[] Strip(int n, int stride, int col)
    {
        var t = new int[(n - 1) * 6]; int k = 0;
        for (int i = 0; i < n - 1; i++)
        {
            int a = i * stride + col, b = a + 1, c = a + stride, d = c + 1;
            t[k++] = a; t[k++] = c; t[k++] = b; t[k++] = b; t[k++] = c; t[k++] = d;
        }
        return t;
    }

    static GameObject MeshObj(string name, Mesh m, Material mat, GameObject parent, bool collider)
    {
        var go = new GameObject(name); if (parent) go.transform.SetParent(parent.transform); go.isStatic = true;
        go.AddComponent<MeshFilter>().sharedMesh = m; go.AddComponent<MeshRenderer>().sharedMaterial = mat;
        if (collider) go.AddComponent<MeshCollider>().sharedMesh = m;
        return go;
    }

    // ---------- 材質とテクスチャ ----------
    static Material Mat(string name, Texture2D tex, Color col, float smooth, float metal = 0f, Texture2D normal = null)
    {
        var sh = Shader.Find("Universal Render Pipeline/Lit");
        if (!sh) sh = Shader.Find("Standard");
        var m = new Material(sh) { name = name };
        if (tex) m.mainTexture = tex;
        m.color = col;
        if (m.HasProperty("_Smoothness")) m.SetFloat("_Smoothness", smooth);
        if (m.HasProperty("_Glossiness")) m.SetFloat("_Glossiness", smooth);
        if (m.HasProperty("_Metallic")) m.SetFloat("_Metallic", metal);
        if (normal && m.HasProperty("_BumpMap")) { m.SetTexture("_BumpMap", normal); m.EnableKeyword("_NORMALMAP"); if (m.HasProperty("_BumpScale")) m.SetFloat("_BumpScale", 0.8f); }
        SaveAsset(m, GEN + "/mat_" + name + ".mat");
        return m;
    }

    static TerrainLayer MakeLayer(string name, Texture2D tex, float tile)
    {
        var l = new TerrainLayer { diffuseTexture = SaveTex(tex, "tex_" + name, false), tileSize = new Vector2(tile, tile) };
        SaveAsset(l, GEN + "/layer_" + name + ".terrainlayer");
        return l;
    }

    static void SaveAsset(Object o, string path)
    {
        AssetDatabase.DeleteAsset(path);
        AssetDatabase.CreateAsset(o, path);
    }

    static Texture2D SaveTex(Texture2D t, string name, bool normalMap)
    {
        string path = GEN + "/" + name + ".png";
        File.WriteAllBytes(path, t.EncodeToPNG());
        AssetDatabase.ImportAsset(path);
        var imp = (TextureImporter)AssetImporter.GetAtPath(path);
        imp.wrapMode = TextureWrapMode.Repeat; imp.mipmapEnabled = true; imp.anisoLevel = 8;
        if (normalMap) imp.textureType = TextureImporterType.NormalMap;
        if (t.filterMode == FilterMode.Point) imp.filterMode = FilterMode.Point;
        imp.SaveAndReimport();
        return AssetDatabase.LoadAssetAtPath<Texture2D>(path);
    }

    static Texture2D NoiseTex(int s, Color a, Color b, int seed)
    {
        var t = new Texture2D(s, s); var r = new System.Random(seed); float k = 256f / s;
        for (int y = 0; y < s; y++)
            for (int x = 0; x < s; x++)
            {
                float n = Mathf.PerlinNoise(x * 0.04f * k + seed, y * 0.04f * k) * 0.45f + Mathf.PerlinNoise(x * 0.17f * k, y * 0.17f * k + seed) * 0.25f + (float)r.NextDouble() * 0.3f;
                t.SetPixel(x, y, Color.Lerp(a, b, n));
            }
        t.Apply(); return t;
    }

    // 舗装（骨材のざらつき・タイヤの通る所が少し黒い・白線・黄色の2本線）と、その凹凸の法線マップ
    static void RoadTextures(out Texture2D albedo, out Texture2D normal)
    {
        int w = 512, h = 1024; var col = new Texture2D(w, h); var hgt = new float[w, h]; var r = new System.Random(5);
        for (int y = 0; y < h; y++)
            for (int x = 0; x < w; x++)
            {
                float g = (float)r.NextDouble(), u = x / (float)w;
                hgt[x, y] = g * 0.6f + Mathf.PerlinNoise(x * 0.3f, y * 0.3f) * 0.4f;
                float v = 0.2f + g * 0.1f + Mathf.PerlinNoise(x * 0.02f, y * 0.01f) * 0.06f;
                float track = Mathf.Exp(-Mathf.Pow((u - 0.2f) / 0.05f, 2)) + Mathf.Exp(-Mathf.Pow((u - 0.33f) / 0.05f, 2)) + Mathf.Exp(-Mathf.Pow((u - 0.67f) / 0.05f, 2)) + Mathf.Exp(-Mathf.Pow((u - 0.8f) / 0.05f, 2));
                v *= 1f - 0.18f * track;
                Color c = new Color(v, v, v * 1.04f);
                if ((x >= 18 && x < 31) || (x >= w - 31 && x < w - 18)) { c = new Color(0.85f, 0.85f, 0.82f) * (0.9f + g * 0.1f); hgt[x, y] += 0.3f; }
                if ((x >= w / 2 - 13 && x < w / 2 - 4) || (x >= w / 2 + 4 && x < w / 2 + 13)) { c = new Color(0.93f, 0.66f, 0.14f) * (0.9f + g * 0.1f); hgt[x, y] += 0.3f; }
                col.SetPixel(x, y, c);
            }
        col.Apply();
        var nm = new Texture2D(w, h, TextureFormat.RGBA32, true, true);
        for (int y = 0; y < h; y++)
            for (int x = 0; x < w; x++)
            {
                float dx = hgt[(x + 1) % w, y] - hgt[(x - 1 + w) % w, y], dy = hgt[x, (y + 1) % h] - hgt[x, (y - 1 + h) % h];
                var n = new Vector3(-dx * 1.6f, -dy * 1.6f, 1f).normalized;
                nm.SetPixel(x, y, new Color(n.x * 0.5f + 0.5f, n.y * 0.5f + 0.5f, n.z * 0.5f + 0.5f, 1f));
            }
        nm.Apply();
        albedo = SaveTex(col, "tex_road", false);
        normal = SaveTex(nm, "tex_road_n", true);
    }
}
