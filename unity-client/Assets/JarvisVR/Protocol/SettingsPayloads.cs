using System.Collections.Generic;
using Newtonsoft.Json;

namespace JarvisVR.Protocol
{
    // ---------------------------------------------------------------------------------------------
    // v1.1 Settings payloads (docs/PROTOCOL.md §5.15). Lets the user view/change the LLM
    // provider / model / API key from the in-headset Settings panel at any time.
    //
    // SECURITY: the API key travels ONLY on client.settings_update.llm.api_key, is sent only when
    // setting/replacing, is never logged, and is NEVER returned by the server (server.settings
    // exposes a `key_set` boolean only). Self-contained; shared-protocol will publish canonical
    // C# bindings to reconcile with later.
    // ---------------------------------------------------------------------------------------------

    /// <summary>§5.15 client.settings_get — request current settings + provider catalog.</summary>
    public class SettingsGet
    {
        // "llm" for just the LLM section; omit or "all" for everything.
        [JsonProperty("section", NullValueHandling = NullValueHandling.Ignore)] public string Section;

        public SettingsGet() { }
        public SettingsGet(string section) { Section = section; }
    }

    /// <summary>§5.15 client.settings_update — change configuration (LLM here).</summary>
    public class ClientSettingsUpdate
    {
        [JsonProperty("llm", NullValueHandling = NullValueHandling.Ignore)] public LlmConfigUpdate Llm;
    }

    /// <summary>The LLM block of client.settings_update.</summary>
    public class LlmConfigUpdate
    {
        [JsonProperty("provider")] public string Provider;
        [JsonProperty("model")] public string Model;
        // base_url for openai-compatible / local / custom providers; null otherwise.
        [JsonProperty("base_url", NullValueHandling = NullValueHandling.Ignore)] public string BaseUrl;
        // OPTIONAL: send only to set/replace the key; omit to keep the existing one.
        [JsonProperty("api_key", NullValueHandling = NullValueHandling.Ignore)] public string ApiKey;
    }

    /// <summary>§5.15 server.settings — current config + catalog (reply to get/update, or pushed).</summary>
    public class ServerSettings
    {
        [JsonProperty("llm", NullValueHandling = NullValueHandling.Ignore)] public LlmSettings Llm;
    }

    public class LlmSettings
    {
        [JsonProperty("current")] public LlmCurrent Current;
        [JsonProperty("providers")] public List<ProviderInfo> Providers;
    }

    public class LlmCurrent
    {
        [JsonProperty("provider")] public string Provider;
        [JsonProperty("model")] public string Model;
        [JsonProperty("base_url")] public string BaseUrl;
        // boolean only — the actual key is never returned.
        [JsonProperty("key_set")] public bool KeySet;
    }

    public class ProviderInfo
    {
        [JsonProperty("id")] public string Id;
        [JsonProperty("name")] public string Name;
        [JsonProperty("default_model")] public string DefaultModel;
        [JsonProperty("models")] public List<string> Models;
        [JsonProperty("needs_key")] public bool NeedsKey;
        [JsonProperty("needs_base_url")] public bool NeedsBaseUrl;
        [JsonProperty("key_set")] public bool KeySet;
        [JsonProperty("capabilities", NullValueHandling = NullValueHandling.Ignore)] public ProviderCapabilities Capabilities;
    }

    public class ProviderCapabilities
    {
        [JsonProperty("tools")] public bool Tools;
        [JsonProperty("vision")] public bool Vision;
    }
}
