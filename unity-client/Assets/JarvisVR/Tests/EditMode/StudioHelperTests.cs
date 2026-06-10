using System.Collections.Generic;
using NUnit.Framework;
using JarvisVR.Shell;

namespace JarvisVR.Tests.EditMode
{
    /// <summary>Tests StudioController's pure helpers: agentskills.io name sanitization + dropdown cycling.</summary>
    public class StudioHelperTests
    {
        [TestCase("Track Habit!", "track-habit")]
        [TestCase("my_skill", "my-skill")]
        [TestCase("ABC-123", "abc-123")]
        [TestCase("  hello world  ", "hello-world")]
        [TestCase("a/b\\c.d", "abcd")]      // path-traversal-ish chars stripped
        [TestCase("", "")]
        public void Sanitize_AppliesNameRules(string input, string expected)
        {
            Assert.AreEqual(expected, StudioController.Sanitize(input));
        }

        [Test]
        public void Cycle_WrapsForwardAndBackward()
        {
            var list = new List<string> { "a", "b", "c" };
            Assert.AreEqual("b", StudioController.Cycle(list, "a", 1));
            Assert.AreEqual("a", StudioController.Cycle(list, "c", 1));   // wrap
            Assert.AreEqual("c", StudioController.Cycle(list, "a", -1));  // wrap back
        }

        [Test]
        public void Cycle_UnknownCurrent_StartsFromFirst()
        {
            var list = new List<string> { "x", "y" };
            // IndexOf(missing) = -1 → Mathf.Max(0,-1)=0, then +1 → "y"
            Assert.AreEqual("y", StudioController.Cycle(list, "missing", 1));
        }

        [Test]
        public void Cycle_NullOrEmptyList_ReturnsCurrent()
        {
            Assert.AreEqual("z", StudioController.Cycle(null, "z", 1));
            Assert.AreEqual("z", StudioController.Cycle(new List<string>(), "z", 1));
        }
    }
}
