using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Networking;
using TMPro;
using Newtonsoft.Json.Linq;

namespace JarvisVR.Holograms.Widgets
{
    /// <summary>
    /// widget_type "image_board". A grid of image tiles. URLs are loaded best-effort via
    /// UnityWebRequestTexture; until a texture arrives a colored placeholder is shown.
    /// Props: { title, images:[url,...], columns }. Tiles are tappable ("image_0", ...).
    /// </summary>
    public class ImageBoardWidget : HoloWidget
    {
        private TextMeshPro _title;
        private Transform _grid;
        private readonly List<GameObject> _tiles = new List<GameObject>();

        protected override void Build()
        {
            _title = CreateText("title", "", 0.04f, new Color(0.9f, 0.85f, 1f), new Vector3(0f, 0.26f, 0f),
                align: TextAlignmentOptions.Center, size: new Vector2(0.6f, 0.06f));
            _grid = new GameObject("grid").transform;
            _grid.SetParent(transform, false);
        }

        protected override void ApplyProps(JObject props)
        {
            _title.text = GetString("title", "Images");

            foreach (var t in _tiles) if (t != null) Destroy(t);
            _tiles.Clear();
            StopAllCoroutines();

            var images = GetArray("images");
            if (images == null || images.Count == 0) return;

            int cols = Mathf.Max(1, GetInt("columns", Mathf.CeilToInt(Mathf.Sqrt(images.Count))));
            float tile = 0.16f, gap = 0.02f, step = tile + gap;
            int rows = Mathf.CeilToInt(images.Count / (float)cols);
            float x0 = -(cols - 1) * step * 0.5f;
            float y0 = (rows - 1) * step * 0.5f;

            for (int i = 0; i < images.Count; i++)
            {
                int r = i / cols, c = i % cols;
                var pos = new Vector3(x0 + c * step, y0 - r * step, 0f);
                var quad = CreatePrimitive(PrimitiveType.Quad, $"image_{i}", pos, new Vector3(tile, tile, 1f),
                    Placeholder(i), _grid, keepCollider: true);
                _tiles.Add(quad.gameObject);

                string url = images[i]?.ToString();
                if (!string.IsNullOrEmpty(url)) StartCoroutine(LoadTexture(url, quad.GetComponent<Renderer>()));
            }
        }

        private IEnumerator LoadTexture(string url, Renderer target)
        {
            if (target == null) yield break;
            using (var req = UnityWebRequestTexture.GetTexture(url))
            {
                yield return req.SendWebRequest();
#if UNITY_2020_1_OR_NEWER
                bool ok = req.result == UnityWebRequest.Result.Success;
#else
                bool ok = !req.isNetworkError && !req.isHttpError;
#endif
                if (ok && target != null)
                {
                    var tex = DownloadHandlerTexture.GetContent(req);
                    if (tex != null) target.material.mainTexture = tex;
                }
            }
        }

        private static Color Placeholder(int i)
        {
            float h = (i * 0.13f) % 1f;
            return Color.HSVToRGB(h, 0.35f, 0.55f);
        }
    }
}
