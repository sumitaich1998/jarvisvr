using UnityEngine;

namespace JarvisVR.Holograms
{
    /// <summary>
    /// Runtime material factory so widgets can be built procedurally without art assets.
    /// Prefers URP/Lit, then Built-in Standard, then an unlit fallback so it renders in any
    /// pipeline. NOTE: for device builds, ensure the chosen shader is included in the build
    /// (Project Settings &gt; Graphics &gt; Always Included Shaders) — see Assets/JarvisVR/SETUP.md.
    /// </summary>
    public static class HoloMaterials
    {
        private static Shader _litShader;
        private static Shader _unlitShader;

        private static Shader Lit()
        {
            if (_litShader != null) return _litShader;
            _litShader = Shader.Find("Universal Render Pipeline/Lit")
                         ?? Shader.Find("Standard")
                         ?? Shader.Find("Sprites/Default");
            return _litShader;
        }

        private static Shader Unlit()
        {
            if (_unlitShader != null) return _unlitShader;
            _unlitShader = Shader.Find("Universal Render Pipeline/Unlit")
                           ?? Shader.Find("Unlit/Color")
                           ?? Lit();
            return _unlitShader;
        }

        public static Material Solid(Color color)
        {
            var m = new Material(Lit());
            SetColor(m, color);
            if (m.HasProperty("_EmissionColor"))
            {
                m.EnableKeyword("_EMISSION");
                m.SetColor("_EmissionColor", color * 0.5f);
            }
            return m;
        }

        public static Material Transparent(Color color)
        {
            var m = new Material(Lit());
            SetColor(m, color);
            // URP transparent surface
            if (m.HasProperty("_Surface")) m.SetFloat("_Surface", 1f);
            if (m.HasProperty("_Blend")) m.SetFloat("_Blend", 0f);
            m.SetOverrideTag("RenderType", "Transparent");
            m.SetInt("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.SrcAlpha);
            m.SetInt("_DstBlend", (int)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
            m.SetInt("_ZWrite", 0);
            m.DisableKeyword("_ALPHATEST_ON");
            m.EnableKeyword("_ALPHABLEND_ON");
            m.renderQueue = (int)UnityEngine.Rendering.RenderQueue.Transparent;
            return m;
        }

        private static void SetColor(Material m, Color color)
        {
            if (m.HasProperty("_BaseColor")) m.SetColor("_BaseColor", color);
            if (m.HasProperty("_Color")) m.SetColor("_Color", color);
        }

        /// <summary>Set the albedo color on a material regardless of pipeline property name.</summary>
        public static void SetAlbedo(Material m, Color color) => SetColor(m, color);

        /// <summary>Read the albedo color on a material regardless of pipeline property name.</summary>
        public static Color GetAlbedo(Material m, Color fallback)
        {
            if (m.HasProperty("_BaseColor")) return m.GetColor("_BaseColor");
            if (m.HasProperty("_Color")) return m.GetColor("_Color");
            return fallback;
        }
    }
}
