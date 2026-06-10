using System;
using System.Collections.Generic;
using JarvisVR.Holograms.Widgets;
using JarvisVR.Protocol;

namespace JarvisVR.Holograms
{
    /// <summary>
    /// Built-in <c>widget_type</c> → procedural widget-behaviour map. Used by
    /// <see cref="HologramManager"/> when the <see cref="WidgetRegistry"/> has no prefab override,
    /// so the catalog described in PROTOCOL.md / holo-tools renders out of the box (primitives +
    /// TextMeshPro, no external art). Mirrors holo-tools/registry.json — reconcile later if needed.
    /// </summary>
    public static class WidgetCatalog
    {
        private static readonly Dictionary<string, Type> Map = new Dictionary<string, Type>
        {
            { WidgetTypes.WeatherOrb,     typeof(WeatherOrbWidget) },
            { WidgetTypes.Timer,          typeof(TimerWidget) },
            { WidgetTypes.Panel,          typeof(PanelWidget) },
            { WidgetTypes.Chart3D,        typeof(Chart3DWidget) },
            { WidgetTypes.ModelViewer,    typeof(ModelViewerWidget) },
            { WidgetTypes.MediaPlayer,    typeof(MediaPlayerWidget) },
            { WidgetTypes.Map3D,          typeof(Map3DWidget) },
            { WidgetTypes.SmartHomePanel, typeof(SmartHomePanelWidget) },
            { WidgetTypes.TextLabel,      typeof(TextLabelWidget) },
            { WidgetTypes.Button,         typeof(ButtonWidget) },
            { WidgetTypes.TodoList,       typeof(TodoListWidget) },
            { WidgetTypes.ImageBoard,     typeof(ImageBoardWidget) },

            // v1.1 perception widgets (§8.5)
            { WidgetTypes.VisionAnnotation, typeof(VisionAnnotationWidget) },
            { WidgetTypes.BoundingBox3D,    typeof(BoundingBox3DWidget) },
            { WidgetTypes.LiveCaption,      typeof(LiveCaptionWidget) },
            { WidgetTypes.VisionFeed,       typeof(VisionFeedWidget) },
            { WidgetTypes.SceneLabel,       typeof(SceneLabelWidget) },

            // v1.1 P1 feature widgets (FEATURES §3)
            { WidgetTypes.Clock,            typeof(ClockWidget) },
            { WidgetTypes.WorldClock,       typeof(WorldClockWidget) },
            { WidgetTypes.Calendar,         typeof(CalendarWidget) },
            { WidgetTypes.StickyNote,       typeof(StickyNoteWidget) },
            { WidgetTypes.NavigationArrow,  typeof(NavigationArrowWidget) },
            { WidgetTypes.MeasuringTape,    typeof(MeasuringTapeWidget) },
            { WidgetTypes.SystemLauncher,   typeof(SystemLauncherWidget) },
            { WidgetTypes.NotificationToast, typeof(NotificationToastWidget) },
            { WidgetTypes.SettingsPanel,    typeof(SettingsPanelWidget) },
            { WidgetTypes.MusicVisualizer,  typeof(MusicVisualizerWidget) },
            { WidgetTypes.DataTable,        typeof(DataTableWidget) },
            { WidgetTypes.Pomodoro,         typeof(PomodoroWidget) },
            { WidgetTypes.HealthRing,       typeof(HealthRingWidget) },
            { WidgetTypes.StocksTicker,     typeof(StocksTickerWidget) },
            { WidgetTypes.CodeViewer,       typeof(CodeViewerWidget) },
            { WidgetTypes.Graph3D,          typeof(Graph3DWidget) },
        };

        public static bool TryResolve(string widgetType, out Type type)
        {
            type = null;
            return !string.IsNullOrEmpty(widgetType) && Map.TryGetValue(widgetType, out type);
        }

        public static bool Has(string widgetType) => widgetType != null && Map.ContainsKey(widgetType);

        public static IEnumerable<string> KnownTypes => Map.Keys;
    }
}
