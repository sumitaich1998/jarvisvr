using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;
using JarvisVR.Shell;

namespace JarvisVR.Tests.EditMode
{
    /// <summary>Tests the on-panel keyboard's text-buffer logic (shift/back/clear/space/newline/done/
    /// cancel). Uses the fallback panel; self-ignores if the editor exposes a native TouchScreenKeyboard
    /// (then a different code path runs). TMP/shader log noise is ignored so it can't fail the test.</summary>
    public class VrKeyboardTests
    {
        private GameObject _go;
        private VrKeyboard _kb;

        [SetUp]
        public void SetUp()
        {
            if (TouchScreenKeyboard.isSupported)
                Assert.Ignore("Native TouchScreenKeyboard is supported here; the on-panel fallback path is not exercised.");
            LogAssert.ignoreFailingMessages = true; // bare test project may log TMP/shader warnings
            _go = new GameObject("kb");
            _kb = _go.AddComponent<VrKeyboard>();
        }

        [TearDown]
        public void TearDown()
        {
            if (_go != null) Object.DestroyImmediate(_go);
            LogAssert.ignoreFailingMessages = false;
        }

        [Test]
        public void Typing_WithShiftBackspaceSpace_ProducesExpectedString()
        {
            string result = null;
            _kb.Open("", false, "label", s => result = s);

            _kb.PressKey("h");
            _kb.PressKey("i");
            _kb.PressKey("shift");
            _kb.PressKey("a");     // uppercased → "hiA"
            _kb.PressKey("back");  // → "hi"
            _kb.PressKey("space"); // → "hi "
            _kb.PressKey("done");

            Assert.AreEqual("hi ", result);
            Assert.IsFalse(_kb.IsOpen, "done closes the keyboard");
        }

        [Test]
        public void Newline_And_Clear()
        {
            string result = null;
            _kb.Open("x", false, "l", s => result = s);
            _kb.PressKey("newline"); // "x\n"
            _kb.PressKey("y");       // "x\ny"
            _kb.PressKey("clear");   // ""
            _kb.PressKey("z");
            _kb.PressKey("done");
            Assert.AreEqual("z", result);
        }

        [Test]
        public void Cancel_DoesNotSubmit()
        {
            string result = "unset";
            bool canceled = false;
            _kb.Open("hello", false, "l", s => result = s, () => canceled = true);
            _kb.PressKey("cancel");
            Assert.IsTrue(canceled);
            Assert.AreEqual("unset", result, "cancel must not invoke onSubmit");
        }

        [Test]
        public void InitialText_IsEditable()
        {
            string result = null;
            _kb.Open("seed", false, "l", s => result = s);
            _kb.PressKey("back"); // "see"
            _kb.PressKey("done");
            Assert.AreEqual("see", result);
        }
    }
}
