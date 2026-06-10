using NUnit.Framework;
using UnityEngine;
using JarvisVR.Shell;

namespace JarvisVR.Tests.EditMode
{
    /// <summary>Tests SettingsController.BuildUpdatePayload — the §5.15 rules: api_key only when a new
    /// key was typed; base_url only when relevant. Component is created without Awake (EditMode), so
    /// no UI is built; we seed the internal form fields directly (InternalsVisibleTo).</summary>
    public class SettingsControllerTests
    {
        private GameObject _go;
        private SettingsController _settings;

        [SetUp]
        public void SetUp()
        {
            _go = new GameObject("settings");
            _settings = _go.AddComponent<SettingsController>(); // Awake not invoked in EditMode
            _settings._providerId = "openai";
            _settings._model = "gpt-4o";
        }

        [TearDown]
        public void TearDown() { if (_go != null) Object.DestroyImmediate(_go); }

        [Test]
        public void Build_NoTypedKey_OmitsApiKey()
        {
            var p = _settings.BuildUpdatePayload();
            Assert.AreEqual("openai", p.Llm.Provider);
            Assert.AreEqual("gpt-4o", p.Llm.Model);
            Assert.IsNull(p.Llm.ApiKey, "no new key typed → api_key omitted (keeps existing)");
            Assert.IsNull(p.Llm.BaseUrl, "no base url needed → omitted");
        }

        [Test]
        public void Build_WithTypedKey_IncludesApiKey()
        {
            _settings._pendingApiKey = "sk-newsecret";
            var p = _settings.BuildUpdatePayload();
            Assert.AreEqual("sk-newsecret", p.Llm.ApiKey);
        }

        [Test]
        public void Build_WithBaseUrl_IncludesBaseUrl()
        {
            _settings._baseUrl = "http://localhost:11434";
            var p = _settings.BuildUpdatePayload();
            Assert.AreEqual("http://localhost:11434", p.Llm.BaseUrl);
        }

        [Test]
        public void Build_ManualMode_SendsBaseUrlEvenIfEmpty()
        {
            _settings._manual = true;
            _settings._baseUrl = "";
            var p = _settings.BuildUpdatePayload();
            Assert.IsNotNull(p.Llm.BaseUrl, "manual mode sends base_url (possibly empty) rather than omitting");
            Assert.AreEqual("", p.Llm.BaseUrl);
        }
    }
}
