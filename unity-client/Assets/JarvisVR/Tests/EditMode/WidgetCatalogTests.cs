using System;
using System.Linq;
using NUnit.Framework;
using JarvisVR.Protocol;
using JarvisVR.Holograms;

namespace JarvisVR.Tests.EditMode
{
    public class WidgetCatalogTests
    {
        // All 33 widget_type ids the client renders procedurally.
        private static readonly string[] AllTypes =
        {
            // v1 (12)
            WidgetTypes.WeatherOrb, WidgetTypes.Timer, WidgetTypes.Panel, WidgetTypes.Chart3D,
            WidgetTypes.ModelViewer, WidgetTypes.MediaPlayer, WidgetTypes.Map3D, WidgetTypes.SmartHomePanel,
            WidgetTypes.TextLabel, WidgetTypes.Button, WidgetTypes.TodoList, WidgetTypes.ImageBoard,
            // v1.1 perception (5)
            WidgetTypes.VisionAnnotation, WidgetTypes.BoundingBox3D, WidgetTypes.LiveCaption,
            WidgetTypes.VisionFeed, WidgetTypes.SceneLabel,
            // v1.1 feature (16)
            WidgetTypes.Clock, WidgetTypes.WorldClock, WidgetTypes.Calendar, WidgetTypes.StickyNote,
            WidgetTypes.NavigationArrow, WidgetTypes.MeasuringTape, WidgetTypes.SystemLauncher,
            WidgetTypes.NotificationToast, WidgetTypes.SettingsPanel, WidgetTypes.MusicVisualizer,
            WidgetTypes.DataTable, WidgetTypes.Pomodoro, WidgetTypes.HealthRing, WidgetTypes.StocksTicker,
            WidgetTypes.CodeViewer, WidgetTypes.Graph3D,
        };

        [Test]
        public void Catalog_Has_AllThirtyThreeTypes()
        {
            Assert.AreEqual(33, AllTypes.Distinct().Count(), "the test list itself must have 33 unique ids");
            Assert.AreEqual(33, KnownCount(), "WidgetCatalog should map exactly 33 types");
        }

        [TestCaseSource(nameof(AllTypes))]
        public void TryResolve_KnownType_ReturnsHoloWidgetSubclass(string widgetType)
        {
            Assert.IsTrue(WidgetCatalog.Has(widgetType), $"Has({widgetType}) should be true");
            Assert.IsTrue(WidgetCatalog.TryResolve(widgetType, out Type t), $"TryResolve({widgetType}) should be true");
            Assert.IsNotNull(t);
            Assert.IsTrue(typeof(HoloWidget).IsAssignableFrom(t), $"{t} must derive from HoloWidget");
            Assert.IsFalse(t.IsAbstract, $"{t} must be concrete");
        }

        [Test]
        public void TryResolve_UnknownType_ReturnsFalse()
        {
            Assert.IsFalse(WidgetCatalog.TryResolve("totally_unknown_widget", out var t));
            Assert.IsNull(t);
            Assert.IsFalse(WidgetCatalog.Has("totally_unknown_widget"));
        }

        [Test]
        public void TryResolve_NullOrEmpty_ReturnsFalse()
        {
            Assert.IsFalse(WidgetCatalog.TryResolve(null, out _));
            Assert.IsFalse(WidgetCatalog.TryResolve("", out _));
        }

        private static int KnownCount()
        {
            int n = 0;
            foreach (var _ in WidgetCatalog.KnownTypes) n++;
            return n;
        }
    }
}
