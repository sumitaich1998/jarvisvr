using NUnit.Framework;
using UnityEngine;
using JarvisVR.Util;

namespace JarvisVR.Tests.EditMode
{
    public class ColorUtilTests
    {
        private static readonly Color Fallback = new Color(0.123f, 0.456f, 0.789f);

        private static void AssertColor(Color expected, Color actual, float tol = 0.01f)
        {
            Assert.AreEqual(expected.r, actual.r, tol);
            Assert.AreEqual(expected.g, actual.g, tol);
            Assert.AreEqual(expected.b, actual.b, tol);
        }

        [Test]
        public void Parse_HexWithHash()
        {
            AssertColor(Color.red, ColorUtil.Parse("#ff0000", Fallback));
            AssertColor(Color.blue, ColorUtil.Parse("#0000ff", Fallback));
        }

        [Test]
        public void Parse_HexWithoutHash()
        {
            AssertColor(Color.green, ColorUtil.Parse("00ff00", Fallback));
        }

        [Test]
        public void Parse_NamedColor()
        {
            AssertColor(Color.red, ColorUtil.Parse("red", Fallback));
        }

        [Test]
        public void Parse_EmptyOrNull_ReturnsFallback()
        {
            AssertColor(Fallback, ColorUtil.Parse("", Fallback));
            AssertColor(Fallback, ColorUtil.Parse(null, Fallback));
        }

        [Test]
        public void Parse_Garbage_ReturnsFallback()
        {
            AssertColor(Fallback, ColorUtil.Parse("not-a-color!!", Fallback));
        }

        [Test]
        public void Temperature_ColdIsBluer_HotIsRedder()
        {
            var cold = ColorUtil.Temperature(-10f);
            var hot = ColorUtil.Temperature(40f);
            Assert.Greater(cold.b, cold.r, "cold should be bluer than red");
            Assert.Greater(hot.r, hot.b, "hot should be redder than blue");
        }

        [Test]
        public void Temperature_ClampsBeyondRange()
        {
            // values past the [-10,40] range clamp to the endpoints
            AssertColor(ColorUtil.Temperature(-10f), ColorUtil.Temperature(-50f));
            AssertColor(ColorUtil.Temperature(40f), ColorUtil.Temperature(100f));
        }
    }
}
