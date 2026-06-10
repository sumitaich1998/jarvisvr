using System;
using System.Text;
using NUnit.Framework;
using Newtonsoft.Json.Linq;
using JarvisVR.Protocol;
using JarvisVR.Perception;

namespace JarvisVR.Tests.EditMode
{
    /// <summary>Verifies the §8.2 /vision binary framing: [4-byte BE len][JSON header][jpeg bytes].</summary>
    public class VisionFramingTests
    {
        private static VisionFrame Header() => new VisionFrame
        {
            FrameId = "F1",
            Camera = CameraIds.RgbCenter,
            Format = "jpeg",
            Width = 640,
            Height = 480,
            Quality = 70,
            Transport = VisionTransports.Binary,
            Seq = 42,
            TsCapture = 1733397600000,
            Pose = new PosePayload { Position = new[] { 0f, 1.6f, 0f }, Rotation = new[] { 0f, 0f, 0f, 1f } },
        };

        [Test]
        public void BuildBinaryFrame_HasBigEndianLengthPrefix_HeaderAndPayload()
        {
            var header = Header();
            var jpeg = new byte[] { 0xFF, 0xD8, 0xFF, 0xE0, 1, 2, 3, 0xFF, 0xD9 };

            byte[] frame = VisionStreamer.BuildBinaryFrame(header, jpeg);

            // 4-byte big-endian header length
            int headerLen = (frame[0] << 24) | (frame[1] << 16) | (frame[2] << 8) | frame[3];
            Assert.Greater(headerLen, 0);
            Assert.AreEqual(4 + headerLen + jpeg.Length, frame.Length, "total = 4 + headerLen + jpeg");

            // header JSON parses and carries the frame fields
            string headerJson = Encoding.UTF8.GetString(frame, 4, headerLen);
            var jo = JObject.Parse(headerJson);
            Assert.AreEqual("F1", (string)jo["frame_id"]);
            Assert.AreEqual(640, (int)jo["width"]);
            Assert.AreEqual("binary", (string)jo["transport"]);
            Assert.IsNull(jo["data"], "binary frames carry no inline base64 data");

            // trailing bytes are exactly the jpeg payload
            var tail = new byte[jpeg.Length];
            Buffer.BlockCopy(frame, 4 + headerLen, tail, 0, tail.Length);
            CollectionAssert.AreEqual(jpeg, tail);
        }

        [Test]
        public void BuildBinaryFrame_HeaderDeserializesBackToVisionFrame()
        {
            var header = Header();
            byte[] frame = VisionStreamer.BuildBinaryFrame(header, new byte[] { 9, 9, 9 });

            int headerLen = (frame[0] << 24) | (frame[1] << 16) | (frame[2] << 8) | frame[3];
            string headerJson = Encoding.UTF8.GetString(frame, 4, headerLen);
            var decoded = Newtonsoft.Json.JsonConvert.DeserializeObject<VisionFrame>(headerJson, EnvelopeSerializer.Settings);

            Assert.AreEqual("F1", decoded.FrameId);
            Assert.AreEqual(640, decoded.Width);
            Assert.AreEqual(42, decoded.Seq);
            Assert.AreEqual(VisionTransports.Binary, decoded.Transport);
            Assert.AreEqual(1.6f, decoded.Pose.Position[1], 1e-4f);
        }

        [Test]
        public void BuildBinaryFrame_EmptyJpeg_StillValid()
        {
            byte[] frame = VisionStreamer.BuildBinaryFrame(Header(), Array.Empty<byte>());
            int headerLen = (frame[0] << 24) | (frame[1] << 16) | (frame[2] << 8) | frame[3];
            Assert.AreEqual(4 + headerLen, frame.Length);
        }
    }
}
