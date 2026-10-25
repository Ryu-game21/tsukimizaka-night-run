// メニュー「Turnpike > シーンを作る」で、地形・道路・ガードレール・スタート/ゴール・海・車・カメラを自動で並べたシーンを作る。
// できたシーンは Assets/Turnpike/Turnpike.unity。作り直したいときはもう一度メニューを押せば上書きされる。
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

public static class TurnpikeBuilder
{
    const string ROOT = "Assets/Turnpike", GEN = ROOT + "/Generated";

    [MenuItem("Turnpike/シーンを作る (Build Scene)")]
    public static void Build()
    {
        var json = AssetDatabase.LoadAssetAtPath<TextAsset>(ROOT + "/Data/road.json");
        var hb = AssetDatabase.LoadAssetAtPath<TextAsset>(ROOT + "/Data/heights.bytes");
        if (!json || !hb) { EditorUtility.DisplayDialog("Turnpike", "Assets/Turnpike/Data に road.json と heights.bytes が見つかりません。", "OK"); return; }
        if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;   // 今開いているシーンの保存を先に確認
        var road = TPRoadData.Load(json);
        Directory.CreateDirectory(GEN);

        try
        {
            EditorUtility.DisplayProgressBar("Turnpike", "シーンを準備しています…", 0.05f);
            var scene = EditorSceneManager.NewScene(NewSceneSetup.DefaultGameObjects, NewSceneMode.Single);

            EditorUtility.DisplayProgressBar("Turnpike", "地形を作っています…", 0.15f);
            BuildTerrain(road, hb.bytes);

            EditorUtility.DisplayProgressBar("Turnpike", "道路を作っています…", 0.6f);
            BuildRoad(road);
            BuildGate(road, road.start, "Start", new Color(0.9f, 0.9f, 0.9f));
            BuildGate(road, road.fin, "Finish", new Color(1f, 0.82f, 0.2f));
            BuildSea(road);

            EditorUtility.DisplayProgressBar("Turnpike", "車とカメラを置いています…", 0.85f);
            var car = BuildCar();
            var race = new GameObject("Race").AddComponent<TPRace>();
            race.roadJson = json; race.car = car;
            int i0 = Mathf.Max(0, road.start - 8);
            car.transform.SetPositionAndRotation(road.Surface(i0, -road.hw * 0.4f) + Vector3.up * 0.6f, Quaternion.LookRotation(road.Forward(i0)));

            var cam = Camera.main;
            if (cam)
            {
                cam.farClipPlane = 20000f; cam.nearClipPlane = 0.2f; cam.fieldOfView = 62f;
                var follow = cam.gameObject.AddComponent<TPCamera>(); follow.target = car.transform;
                cam.transform.position = car.transform.position - car.transform.forward * 7f + Vector3.up * 2.5f;
                cam.transform.LookAt(car.transform);
            }
            var sun = Object.FindFirstObjectByType<Light>();
            if (sun) { sun.transform.rotation = Quaternion.Euler(42f, -35f, 0f); sun.intensity = 1.3f; sun.shadows = LightShadows.Soft; }
            RenderSettings.fog = true; RenderSettings.fogMode = FogMode.Exponential; RenderSettings.fogDensity = 0.00012f;
            RenderSettings.fogColor = new Color(0.72f, 0.8f, 0.88f);

            EditorSceneManager.SaveScene(scene, ROOT + "/Turnpike.unity");
            AssetDatabase.SaveAssets();
            Debug.Log("Turnpike: シーンを作りました（Assets/Turnpike/Turnpike.unity）。再生ボタンで走れます。" + road.credit);
        }
        finally { EditorUtility.ClearProgressBar(); }
    }

    // ---------- 地形（国土地理院の標高） ----------
    static void BuildTerrain(TPRoadData road, byte[] hb)
    {
        var t = road.terrain; int res = t.res;
        var td = new TerrainData();
        td.heightmapResolution = res;                                   // 解像度を先に決める（あとで size を入れる）
        td.size = new Vector3(t.size, t.hmax - t.hmin, t.size);
        var h = new float[res, res];
        for (int j = 0; j < res; j++)
            for (int i = 0; i < res; i++) { int o = (j * res + i) * 2; h[j, i] = (hb[o] | (hb[o + 1] << 8)) / 65535f; }
        td.SetHeights(0, 0, h);

        // 色: 森の緑と、急な斜面の土・岩
        var grass = SaveTex(NoiseTex(256, new Color(0.20f, 0.31f, 0.16f), new Color(0.13f, 0.22f, 0.11f), 7), "tex_grass");
        var rock = SaveTex(NoiseTex(256, new Color(0.47f, 0.43f, 0.36f), new Color(0.32f, 0.30f, 0.26f), 11), "tex_rock");
        var lg = new TerrainLayer { diffuseTexture = grass, tileSize = new Vector2(24, 24) };
        var lr = new TerrainLayer { diffuseTexture = rock, tileSize = new Vector2(16, 16) };
        AssetDatabase.CreateAsset(lg, GEN + "/layer_grass.terrainlayer");
        AssetDatabase.CreateAsset(lr, GEN + "/layer_rock.terrainlayer");
        td.terrainLayers = new[] { lg, lr };
        int ar = 1024; td.alphamapResolution = ar;
        var a = new float[ar, ar, 2];
        for (int j = 0; j < ar; j++)
            for (int i = 0; i < ar; i++)
            {
                float s = td.GetSteepness((i + 0.5f) / ar, (j + 0.5f) / ar);
                float k = Mathf.Clamp01((s - 28f) / 14f);
                a[j, i, 0] = 1f - k; a[j, i, 1] = k;
            }
        td.SetAlphamaps(0, 0, a);
        AssetDatabase.CreateAsset(td, GEN + "/TerrainData.asset");

        var go = Terrain.CreateTerrainGameObject(td);
        go.name = "Terrain";
        go.transform.position = new Vector3(t.x0, t.hmin, t.z0);
        var ter = go.GetComponent<Terrain>();
        ter.heightmapPixelError = 3f; ter.basemapDistance = 3000f; ter.drawInstanced = true;
    }

    // ---------- 道路・路肩・ガードレール ----------
    static void BuildRoad(TPRoadData road)
    {
        int n = road.Count; float hw = road.hw, rail = hw + 2.2f;
        var parent = new GameObject("Road");

        // 路面: 進行方向に 14m ごとにくり返す模様（白い外側線と黄色のセンターライン）
        var surf = new Mesh { name = "road" }; surf.indexFormat = IndexFormat.UInt32;
        var sh = new Mesh { name = "shoulder" }; sh.indexFormat = IndexFormat.UInt32;
        var rv = new Vector3[n * 2]; var ruv = new Vector2[n * 2];
        var sv = new Vector3[n * 4]; var suv = new Vector2[n * 4];
        float dist = 0f;
        for (int i = 0; i < n; i++)
        {
            if (i > 0) dist += Vector3.Distance(road.Point(i), road.Point(i - 1));
            rv[i * 2] = road.Surface(i, -hw); rv[i * 2 + 1] = road.Surface(i, hw);
            ruv[i * 2] = new Vector2(0, dist / 14f); ruv[i * 2 + 1] = new Vector2(1, dist / 14f);
            sv[i * 4] = road.Surface(i, -rail - 0.4f) - Vector3.up * 0.04f; sv[i * 4 + 1] = road.Surface(i, -hw) - Vector3.up * 0.02f;
            sv[i * 4 + 2] = road.Surface(i, hw) - Vector3.up * 0.02f; sv[i * 4 + 3] = road.Surface(i, rail + 0.4f) - Vector3.up * 0.04f;
            for (int q = 0; q < 4; q++) suv[i * 4 + q] = new Vector2(q * 0.3f, dist / 6f);
        }
        surf.vertices = rv; surf.uv = ruv; surf.triangles = Strip(n, 2, 0); surf.RecalculateNormals(); surf.RecalculateBounds();
        var stri = new System.Collections.Generic.List<int>(Strip(n, 4, 0)); stri.AddRange(Strip(n, 4, 2));
        sh.vertices = sv; sh.uv = suv; sh.triangles = stri.ToArray(); sh.RecalculateNormals(); sh.RecalculateBounds();
        AssetDatabase.CreateAsset(surf, GEN + "/road.asset"); AssetDatabase.CreateAsset(sh, GEN + "/shoulder.asset");
        var roadTex = SaveTex(RoadTex(), "tex_road");
        MeshObj("Surface", surf, Mat("road", roadTex, Color.white, 0.18f), parent, true);
        MeshObj("Shoulder", sh, Mat("shoulder", SaveTex(NoiseTex(64, new Color(0.36f, 0.34f, 0.3f), new Color(0.27f, 0.25f, 0.22f), 3), "tex_shoulder"), Color.white, 0.05f), parent, true);

        // ガードレール（見た目）と、少し高い見えない壁（当たり判定）
        var railM = new Mesh { name = "rails" }; railM.indexFormat = IndexFormat.UInt32;
        var wallM = new Mesh { name = "railWalls" }; wallM.indexFormat = IndexFormat.UInt32;
        var v = new Vector3[n * 4]; var w = new Vector3[n * 4];
        for (int i = 0; i < n; i++)
        {
            Vector3 L = road.Surface(i, -rail), R = road.Surface(i, rail);
            v[i * 4] = L + Vector3.up * 0.45f; v[i * 4 + 1] = L + Vector3.up * 0.85f; v[i * 4 + 2] = R + Vector3.up * 0.45f; v[i * 4 + 3] = R + Vector3.up * 0.85f;
            w[i * 4] = L - Vector3.up * 1f; w[i * 4 + 1] = L + Vector3.up * 1.6f; w[i * 4 + 2] = R - Vector3.up * 1f; w[i * 4 + 3] = R + Vector3.up * 1.6f;
        }
        var rt = new System.Collections.Generic.List<int>();
        for (int i = 0; i < n - 1; i++)
            for (int side = 0; side < 2; side++)
            {
                int a = i * 4 + side * 2, b = a + 1, c = a + 4, d = a + 5;
                rt.AddRange(new[] { a, b, c, c, b, d, a, c, b, b, c, d });   // 両面
            }
        // 見た目のレールは表と裏で頂点を分ける（同じ頂点を両面で使うと法線が打ち消し合って真っ黒になる）
        var v2 = new Vector3[n * 8]; System.Array.Copy(v, 0, v2, 0, n * 4); System.Array.Copy(v, 0, v2, n * 4, n * 4);
        var rt2 = new System.Collections.Generic.List<int>();
        for (int i = 0; i < n - 1; i++)
            for (int side = 0; side < 2; side++)
            {
                int a = i * 4 + side * 2, b = a + 1, c = a + 4, d = a + 5, o = n * 4;
                rt2.AddRange(new[] { a, b, c, c, b, d, o + a, o + c, o + b, o + b, o + c, o + d });
            }
        railM.vertices = v2; railM.triangles = rt2.ToArray(); railM.RecalculateNormals();
        wallM.vertices = w; wallM.triangles = rt.ToArray(); wallM.RecalculateNormals();
        AssetDatabase.CreateAsset(railM, GEN + "/rails.asset"); AssetDatabase.CreateAsset(wallM, GEN + "/railWalls.asset");
        MeshObj("Guardrail", railM, Mat("rail", null, new Color(0.78f, 0.8f, 0.84f), 0.5f), parent, false);
        var wall = new GameObject("GuardrailCollider"); wall.transform.SetParent(parent.transform);
        wall.AddComponent<MeshCollider>().sharedMesh = wallM;

        // 支柱（8m おき）
        var postMat = Mat("post", null, new Color(0.45f, 0.47f, 0.52f), 0.3f);
        var posts = new GameObject("Posts"); posts.transform.SetParent(parent.transform);
        for (int i = 0; i < n; i += 2)
            foreach (float s in new[] { -1f, 1f })
            {
                var p = GameObject.CreatePrimitive(PrimitiveType.Cube); Object.DestroyImmediate(p.GetComponent<Collider>());
                p.transform.SetParent(posts.transform);
                p.transform.position = road.Surface(i, s * (rail + 0.1f)) + Vector3.up * 0.42f;
                p.transform.rotation = Quaternion.LookRotation(road.Forward(i)); p.transform.localScale = new Vector3(0.12f, 0.9f, 0.12f);
                p.GetComponent<MeshRenderer>().sharedMaterial = postMat; p.isStatic = true;
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
        var go = new GameObject(name); go.transform.SetParent(parent.transform); go.isStatic = true;
        go.AddComponent<MeshFilter>().sharedMesh = m; go.AddComponent<MeshRenderer>().sharedMaterial = mat;
        if (collider) go.AddComponent<MeshCollider>().sharedMesh = m;
        return go;
    }

    // ---------- スタート・ゴールのゲート ----------
    static void BuildGate(TPRoadData road, int i, string name, Color col)
    {
        var g = new GameObject(name); g.transform.position = road.Point(i); g.transform.rotation = Quaternion.LookRotation(road.Forward(i));
        var m = Mat("gate_" + name, null, col, 0.3f);
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
        // 路面の白黒のライン
        var line = GameObject.CreatePrimitive(PrimitiveType.Quad); Object.DestroyImmediate(line.GetComponent<Collider>());
        line.transform.SetParent(g.transform, false); line.transform.localPosition = new Vector3(0, 0.03f, 0);
        line.transform.localRotation = Quaternion.Euler(90f, 0, 0); line.transform.localScale = new Vector3(road.hw * 2, 1.6f, 1);
        var chk = new Texture2D(32, 4) { filterMode = FilterMode.Point };
        for (int yy = 0; yy < 4; yy++) for (int xx = 0; xx < 32; xx++) chk.SetPixel(xx, yy, (xx + yy) % 2 == 0 ? Color.white : new Color(0.08f, 0.08f, 0.08f));
        chk.Apply();
        line.GetComponent<MeshRenderer>().sharedMaterial = Mat("check_" + name, SaveTex(chk, "tex_check_" + name), Color.white, 0.2f);
    }

    // ---------- 海（相模湾） ----------
    static void BuildSea(TPRoadData road)
    {
        var sea = GameObject.CreatePrimitive(PrimitiveType.Plane); sea.name = "Sea";
        Object.DestroyImmediate(sea.GetComponent<Collider>());
        var t = road.terrain;
        sea.transform.position = new Vector3(t.x0 + t.size / 2, 0f, t.z0 + t.size / 2);
        sea.transform.localScale = new Vector3(t.size / 10f * 1.6f, 1, t.size / 10f * 1.6f);
        sea.GetComponent<MeshRenderer>().sharedMaterial = Mat("sea", null, new Color(0.16f, 0.36f, 0.52f), 0.85f);
    }

    // ---------- 仮の車 ----------
    static TPCar BuildCar()
    {
        var car = new GameObject("Car");
        var rb = car.AddComponent<Rigidbody>(); rb.mass = 1400f;
        var body = GameObject.CreatePrimitive(PrimitiveType.Cube); body.name = "Body"; body.transform.SetParent(car.transform, false);
        body.transform.localPosition = new Vector3(0, 0.62f, 0); body.transform.localScale = new Vector3(1.85f, 0.5f, 4.4f);
        body.GetComponent<MeshRenderer>().sharedMaterial = Mat("car_body", null, new Color(0.75f, 0.08f, 0.1f), 0.75f);
        var cabin = GameObject.CreatePrimitive(PrimitiveType.Cube); cabin.name = "Cabin"; cabin.transform.SetParent(car.transform, false);
        Object.DestroyImmediate(cabin.GetComponent<Collider>());
        cabin.transform.localPosition = new Vector3(0, 1.08f, -0.25f); cabin.transform.localScale = new Vector3(1.5f, 0.45f, 2.1f);
        cabin.GetComponent<MeshRenderer>().sharedMaterial = Mat("car_glass", null, new Color(0.08f, 0.1f, 0.13f), 0.9f);
        var tc = car.AddComponent<TPCar>();
        var tyre = Mat("car_tyre", null, new Color(0.06f, 0.06f, 0.06f), 0.2f);
        Vector3[] pos = { new Vector3(-0.8f, 0.45f, 1.35f), new Vector3(0.8f, 0.45f, 1.35f), new Vector3(-0.8f, 0.45f, -1.3f), new Vector3(0.8f, 0.45f, -1.3f) };
        string[] nm = { "FL", "FR", "RL", "RR" };
        for (int i = 0; i < 4; i++)
        {
            var wgo = new GameObject("Wheel_" + nm[i]); wgo.transform.SetParent(car.transform, false); wgo.transform.localPosition = pos[i];
            var wc = wgo.AddComponent<WheelCollider>(); wc.radius = 0.34f; wc.suspensionDistance = 0.18f;
            var vis = GameObject.CreatePrimitive(PrimitiveType.Cylinder); vis.name = "Tyre_" + nm[i];
            Object.DestroyImmediate(vis.GetComponent<Collider>());
            vis.transform.SetParent(car.transform, false); vis.transform.localPosition = pos[i];
            vis.transform.localRotation = Quaternion.Euler(0, 0, 90); vis.transform.localScale = new Vector3(0.68f, 0.13f, 0.68f);
            vis.GetComponent<MeshRenderer>().sharedMaterial = tyre;
            tc.wheels[i] = wc; tc.visuals[i] = vis.transform;
        }
        return tc;
    }

    // ---------- 材質とテクスチャ ----------
    static Material Mat(string name, Texture2D tex, Color col, float smooth)
    {
        string path = GEN + "/mat_" + name + ".mat";
        var sh = Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard");
        var m = new Material(sh) { name = name };
        if (tex) m.mainTexture = tex;
        m.color = col;
        if (m.HasProperty("_Smoothness")) m.SetFloat("_Smoothness", smooth);
        if (m.HasProperty("_Glossiness")) m.SetFloat("_Glossiness", smooth);
        AssetDatabase.DeleteAsset(path); AssetDatabase.CreateAsset(m, path);
        return m;
    }

    static Texture2D SaveTex(Texture2D t, string name)
    {
        string path = GEN + "/" + name + ".png";
        File.WriteAllBytes(path, t.EncodeToPNG());
        AssetDatabase.ImportAsset(path);
        var imp = (TextureImporter)AssetImporter.GetAtPath(path);
        imp.wrapMode = TextureWrapMode.Repeat; imp.mipmapEnabled = true; imp.anisoLevel = 8;
        if (t.filterMode == FilterMode.Point) imp.filterMode = FilterMode.Point;
        imp.SaveAndReimport();
        return AssetDatabase.LoadAssetAtPath<Texture2D>(path);
    }

    static Texture2D NoiseTex(int s, Color a, Color b, int seed)
    {
        var t = new Texture2D(s, s); var r = new System.Random(seed);
        for (int y = 0; y < s; y++)
            for (int x = 0; x < s; x++)
            {
                float n = Mathf.PerlinNoise(x * 0.05f + seed, y * 0.05f) * 0.6f + (float)r.NextDouble() * 0.4f;
                t.SetPixel(x, y, Color.Lerp(a, b, n));
            }
        t.Apply(); return t;
    }

    static Texture2D RoadTex()
    {
        int w = 256, h = 512; var t = new Texture2D(w, h); var r = new System.Random(5);
        for (int y = 0; y < h; y++)
            for (int x = 0; x < w; x++)
            {
                float v = 0.17f + (float)r.NextDouble() * 0.12f;
                Color c = new Color(v, v, v * 1.05f);
                if ((x >= 9 && x < 16) || (x >= w - 16 && x < w - 9)) c = new Color(0.86f, 0.86f, 0.83f);           // 外側線
                if ((x >= w / 2 - 7 && x < w / 2 - 2) || (x >= w / 2 + 2 && x < w / 2 + 7)) c = new Color(0.92f, 0.65f, 0.16f); // 黄色の2本線
                t.SetPixel(x, y, c);
            }
        t.Apply(); return t;
    }
}
