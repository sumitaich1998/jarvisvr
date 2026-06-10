# JarvisVR Client — Tests

Unity Test Framework (UTF) + NUnit tests for the testable logic of the unity-client. **EditMode**
covers pure logic (protocol, DTOs, util, layout, framing, helpers); **PlayMode** covers a little
MonoBehaviour wiring (spawn-on-message, orchestration plan, presence state).

> These were authored without a Unity toolchain present, so they're optimized for correctness
> against the UTF/NUnit APIs. **Coverage is measured on a real machine**, not here (see below).

## Run them

1. Open the project in **Unity 2022.3 LTS**.
2. **Window → General → Test Runner**.
3. **EditMode** tab → *Run All* (fast, no play). **PlayMode** tab → *Run All* (enters play mode).

CLI / CI (batch mode):

```bash
Unity -batchmode -projectPath unity-client -runTests -testPlatform EditMode \
      -testResults results-editmode.xml -quit
Unity -batchmode -projectPath unity-client -runTests -testPlatform PlayMode \
      -testResults results-playmode.xml -quit
```

## Measure coverage (on a real machine)

Coverage isn't measurable in this authoring environment. On a real install:

1. **Window → Package Manager → Code Coverage** (install the package).
2. **Window → Analysis → Code Coverage** → enable, set *Assemblies Included* to `JarvisVR` and
   `JarvisVR.Protocol` (exclude the `*.Tests.*` and `JarvisVR.Meta*` assemblies).
3. Run the Test Runner with **Coverage** enabled (or `-enableCodeCoverage
   -coverageOptions "generateHtmlReport;assemblyFilters:+JarvisVR,+JarvisVR.Protocol"` in batch
   mode). Open the generated HTML report under `CodeCoverage/`.

## Assembly setup

- `EditMode/JarvisVR.Tests.EditMode.asmdef` — `includePlatforms: ["Editor"]`, references the runtime
  asmdefs (`JarvisVR`, `JarvisVR.Protocol`) + `UnityEngine.TestRunner` / `UnityEditor.TestRunner`,
  `precompiledReferences: ["nunit.framework.dll", "Newtonsoft.Json.dll"]`,
  `defineConstraints: ["UNITY_INCLUDE_TESTS"]`, `autoReferenced: false`.
- `PlayMode/JarvisVR.Tests.PlayMode.asmdef` — same, but `includePlatforms: []` (runs in play / on
  device). (Modern UTF marks a test assembly by referencing the TestRunner assemblies + nunit;
  the older `optionalUnityReferences: ["TestAssemblies"]` flag isn't needed.)

Tests use internal seams exposed via `[assembly: InternalsVisibleTo("JarvisVR.Tests.EditMode" /
"…PlayMode")]` (see `Assets/JarvisVR/AssemblyInfo.cs`). Meta-SDK code is define-gated and **not**
required by any test.

## What's covered (by area)

| Area | Tests |
| --- | --- |
| Protocol envelope/serializer | `EnvelopeSerializerTests` (build, round-trip, null/`reply_to` omission, `TryDeserialize`, `PayloadAs`) |
| Router | `MessageRouterTests` (dispatch, multi-handler, off, unknown→`OnUnhandled`, null-safety) |
| All DTOs round-trip | `ProtocolRoundTripTests` (v1 + perception + settings + orchestration + trace + authoring + barge_in + heartbeat + error; MissingMember/extra-keys tolerance) |
| Util | `ProtocolMathTests`, `ColorUtilTests` |
| Holograms | `WidgetCatalogTests` (all 33), `LayoutArrangerTests` (arc/grid/stack/free), `AnchorServiceTests`, `BillboardTests`, `HologramPersistenceTests` (save→restore) |
| Net | `ReconnectBackoffTests` (`NextReconnectDelay`) |
| Perception | `VisionFramingTests` (`/vision` length-prefixed codec round-trip) |
| Shell | `SettingsControllerTests` (payload rules), `StudioHelperTests` (name sanitize / cycle), `OrchestrationHelperTests` (state/kind/role mapping) |
| Input | `VrKeyboardTests` (text-buffer logic) |
| PlayMode wiring | `HologramManagerPlayTests` (spawn/update/destroy on message), `OrchestrationControllerPlayTests` (plan→nodes/edges, status→state, trace_event), `JarvisPresencePlayTests` (thinking/speech state) |

## Testability refactors made to runtime code (minimal, additive)

- `AssemblyInfo.cs` — `InternalsVisibleTo` the test assemblies (new file).
- `MessageTypes`/`Payloads` — added `client.barge_in` constant + `BargePayload` (§5.14 was unimplemented).
- `JarvisConnection` — `public bool autoConnectOnStart` (tests exercise the Router without a socket);
  extracted pure `internal static NextReconnectDelay(...)` (behavior-preserving).
- `Billboard` — extracted pure `internal static TryFaceRotation(...)` (LateUpdate calls it).
- `VisionStreamer.BuildBinaryFrame` — `private` → `internal static`.
- `OrchestrationController` — `StateColor/KindColor/KindCode/Prettify/IsActiveState` → `internal static`;
  added read-only `internal` accessors (`NodeCount/EdgeCount/HasNode/NodeState/TraceCountFor`).
- `StudioController` — `Sanitize/Cycle` → `internal static`.
- `SettingsController` — extracted `internal ClientSettingsUpdate BuildUpdatePayload()`; a few state
  fields made `internal` so tests can seed the form.
- `JarvisPresence` — read-only `internal` accessors (`CurrentTarget/StatusText/CaptionText`).

No behavior changed; only visibility + additive members.

> Some MonoBehaviour-creating tests set `LogAssert.ignoreFailingMessages = true` so unrelated
> TMP/shader log noise in a bare test project doesn't fail them. `VrKeyboardTests` self-`Ignore`s if
> the editor reports a native `TouchScreenKeyboard` (so the on-panel fallback path is what's tested).
