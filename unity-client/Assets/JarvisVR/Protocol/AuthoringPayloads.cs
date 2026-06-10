using System.Collections.Generic;
using Newtonsoft.Json;

namespace JarvisVR.Protocol
{
    // ---------------------------------------------------------------------------------------------
    // v1.3 In-headset authoring payloads (docs/PROTOCOL.md §10.2). Compose your own agents & skills.
    // The server validates (agentskills.io rules), persists, hot-reloads, and refuses to overwrite
    // built-ins. Additive + optional. Self-contained; shared-protocol will publish C# bindings.
    // ---------------------------------------------------------------------------------------------

    /// <summary>§10.2 client.author_list — request the authorable catalog. Empty payload.</summary>
    public class AuthorList { }

    /// <summary>§10.2 server.authoring — agents + skills catalog with pickable categories/tools.</summary>
    public class ServerAuthoring
    {
        [JsonProperty("agents", NullValueHandling = NullValueHandling.Ignore)] public List<AuthoringAgent> Agents;
        [JsonProperty("skills", NullValueHandling = NullValueHandling.Ignore)] public List<AuthoringSkill> Skills;
        [JsonProperty("categories", NullValueHandling = NullValueHandling.Ignore)] public List<string> Categories;
        [JsonProperty("tools", NullValueHandling = NullValueHandling.Ignore)] public List<string> Tools;
    }

    public class AuthoringAgent
    {
        [JsonProperty("role")] public string Role;
        [JsonProperty("name", NullValueHandling = NullValueHandling.Ignore)] public string Name;
        [JsonProperty("source", NullValueHandling = NullValueHandling.Ignore)] public string Source; // builtin | user
        [JsonProperty("persona", NullValueHandling = NullValueHandling.Ignore)] public string Persona;
        [JsonProperty("skills", NullValueHandling = NullValueHandling.Ignore)] public List<string> Skills;
        [JsonProperty("tools", NullValueHandling = NullValueHandling.Ignore)] public List<string> Tools;

        public bool IsUser => Source == AuthoringSources.User;
    }

    public class AuthoringSkill
    {
        [JsonProperty("name")] public string Name;
        [JsonProperty("agent", NullValueHandling = NullValueHandling.Ignore)] public string Agent;
        [JsonProperty("category", NullValueHandling = NullValueHandling.Ignore)] public string Category;
        [JsonProperty("source", NullValueHandling = NullValueHandling.Ignore)] public string Source; // builtin | user
        [JsonProperty("description", NullValueHandling = NullValueHandling.Ignore)] public string Description;
        // present on detailed responses / when editing
        [JsonProperty("body", NullValueHandling = NullValueHandling.Ignore)] public string Body;
        [JsonProperty("allowed_tools", NullValueHandling = NullValueHandling.Ignore)] public List<string> AllowedTools;

        public bool IsUser => Source == AuthoringSources.User;
    }

    /// <summary>§10.2 client.author_skill — create/update/delete a Skill (SKILL.md).</summary>
    public class AuthorSkill
    {
        [JsonProperty("op")] public string Op; // create | update | delete
        [JsonProperty("name")] public string Name;
        [JsonProperty("category", NullValueHandling = NullValueHandling.Ignore)] public string Category;
        [JsonProperty("agent", NullValueHandling = NullValueHandling.Ignore)] public string Agent;
        [JsonProperty("description", NullValueHandling = NullValueHandling.Ignore)] public string Description;
        [JsonProperty("body", NullValueHandling = NullValueHandling.Ignore)] public string Body;
        [JsonProperty("allowed_tools", NullValueHandling = NullValueHandling.Ignore)] public List<string> AllowedTools;
        [JsonProperty("license", NullValueHandling = NullValueHandling.Ignore)] public string License;
        [JsonProperty("compatibility", NullValueHandling = NullValueHandling.Ignore)] public string Compatibility;
    }

    /// <summary>§10.2 client.author_agent — create/update/delete an agent (role).</summary>
    public class AuthorAgent
    {
        [JsonProperty("op")] public string Op; // create | update | delete
        [JsonProperty("role")] public string Role;
        [JsonProperty("name", NullValueHandling = NullValueHandling.Ignore)] public string Name;
        [JsonProperty("persona", NullValueHandling = NullValueHandling.Ignore)] public string Persona;
        [JsonProperty("tools", NullValueHandling = NullValueHandling.Ignore)] public List<string> Tools;
        [JsonProperty("skills", NullValueHandling = NullValueHandling.Ignore)] public List<string> Skills;
    }
}
