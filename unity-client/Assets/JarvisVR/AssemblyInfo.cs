using System.Runtime.CompilerServices;

// Expose internal testability seams (pure helpers + read-only accessors) to the test assemblies.
// Public API stays unchanged; see Assets/JarvisVR/Tests/README.md for the list of seams.
[assembly: InternalsVisibleTo("JarvisVR.Tests.EditMode")]
[assembly: InternalsVisibleTo("JarvisVR.Tests.PlayMode")]
