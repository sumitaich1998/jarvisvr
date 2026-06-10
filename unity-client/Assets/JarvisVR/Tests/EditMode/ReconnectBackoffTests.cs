using NUnit.Framework;
using JarvisVR.Net;

namespace JarvisVR.Tests.EditMode
{
    public class ReconnectBackoffTests
    {
        [Test]
        public void FirstDelay_UsesInitial()
        {
            Assert.AreEqual(1f, JarvisConnection.NextReconnectDelay(0f, 1f, 30f, 2f), 1e-4f);
        }

        [Test]
        public void FirstDelay_ClampedToMinimum()
        {
            // very small initial is floored at 0.1
            Assert.AreEqual(0.1f, JarvisConnection.NextReconnectDelay(0f, 0.01f, 30f, 2f), 1e-4f);
        }

        [Test]
        public void SubsequentDelays_GrowGeometrically()
        {
            Assert.AreEqual(2f, JarvisConnection.NextReconnectDelay(1f, 1f, 30f, 2f), 1e-4f);
            Assert.AreEqual(4f, JarvisConnection.NextReconnectDelay(2f, 1f, 30f, 2f), 1e-4f);
            Assert.AreEqual(8f, JarvisConnection.NextReconnectDelay(4f, 1f, 30f, 2f), 1e-4f);
        }

        [Test]
        public void Delay_IsCappedAtMax()
        {
            Assert.AreEqual(30f, JarvisConnection.NextReconnectDelay(16f, 1f, 30f, 2f), 1e-4f);
            Assert.AreEqual(30f, JarvisConnection.NextReconnectDelay(30f, 1f, 30f, 2f), 1e-4f);
        }

        [Test]
        public void Multiplier_BelowOne_IsClampedToOne()
        {
            // mult < 1 would otherwise shrink the delay; clamp keeps it monotonic
            Assert.AreEqual(2f, JarvisConnection.NextReconnectDelay(2f, 1f, 30f, 0.5f), 1e-4f);
        }

        [Test]
        public void FullSequence_ReachesAndHoldsCap()
        {
            float d = 0f;
            float[] expected = { 1f, 2f, 4f, 8f, 16f, 30f, 30f };
            for (int i = 0; i < expected.Length; i++)
            {
                d = JarvisConnection.NextReconnectDelay(d, 1f, 30f, 2f);
                Assert.AreEqual(expected[i], d, 1e-4f, $"step {i}");
            }
        }
    }
}
