/**
 * JarvisVR holographic widget types.
 *
 * Hand-written from `holo-tools/registry.json` (the single source of truth) and
 * `docs/PROTOCOL.md` §5.6 (The Holographic Object). Keep this file in sync with
 * the registry whenever a widget or prop changes.
 *
 * Used by `shared-protocol/` and `infra/` for type-safe construction of
 * `holo.spawn` / `holo.update` payloads and `client.interaction` events.
 */

/* ------------------------------------------------------------------ */
/* Protocol primitives (PROTOCOL.md §5.6, ARCHITECTURE.md §5)          */
/* ------------------------------------------------------------------ */

export type Anchor = "world" | "head" | "hand_left" | "hand_right" | "surface";

export type Interaction =
  | "tap"
  | "grab"
  | "release"
  | "drag"
  | "slider"
  | "toggle"
  | "resize"
  | "dwell";

export type WidgetCategory =
  | "information"
  | "data"
  | "media"
  | "container"
  | "primitive"
  | "control"
  | "utility"
  | "productivity";

/** Right-handed, meters, Unity convention (Y up). */
export type Vec3 = [number, number, number];
/** Quaternion [x, y, z, w]. */
export type Quat = [number, number, number, number];

export interface Transform {
  anchor: Anchor;
  position: Vec3;
  rotation: Quat;
  scale: Vec3;
  /** If true, always face the user. */
  billboard?: boolean;
}

/* ------------------------------------------------------------------ */
/* Per-widget props (mirrors registry.json props_schema)              */
/* ------------------------------------------------------------------ */

export type WeatherCondition =
  | "clear"
  | "partly_cloudy"
  | "clouds"
  | "rain"
  | "snow"
  | "storm"
  | "fog"
  | "wind";

export interface WeatherForecastEntry {
  day: string;
  high_c: number;
  low_c: number;
  condition: WeatherCondition;
}

export interface WeatherOrbProps {
  city: string;
  temp_c: number;
  condition: WeatherCondition;
  humidity_pct?: number;
  wind_kph?: number;
  unit?: "c" | "f";
  forecast?: WeatherForecastEntry[];
}

export type ChartType = "bar" | "line" | "scatter" | "pie" | "surface";

export interface ChartSeries {
  name: string;
  values: number[];
  /** Hex color (#RRGGBB or #RRGGBBAA). */
  color?: string;
}

export interface Chart3DProps {
  chart_type: ChartType;
  title?: string;
  labels?: string[];
  series: ChartSeries[];
  x_axis_label?: string;
  y_axis_label?: string;
  z_axis_label?: string;
  show_legend?: boolean;
}

export type ModelFormat = "glb" | "gltf" | "obj" | "fbx";

export interface ModelViewerProps {
  model_url: string;
  name?: string;
  format?: ModelFormat;
  auto_rotate?: boolean;
  animation?: string;
  scale_factor?: number;
}

export type PanelBackground = "glass" | "solid" | "none";

export interface PanelSection {
  heading: string;
  text: string;
}

export interface PanelProps {
  title: string;
  body?: string;
  sections?: PanelSection[];
  width_m?: number;
  height_m?: number;
  background?: PanelBackground;
  scrollable?: boolean;
}

export type TextAlign = "left" | "center" | "right";
export type TextWeight = "regular" | "bold";

export interface TextLabelProps {
  text: string;
  font_size_m?: number;
  /** Hex color (#RRGGBB or #RRGGBBAA). */
  color?: string;
  align?: TextAlign;
  weight?: TextWeight;
}

export type ButtonStyle = "primary" | "secondary" | "danger" | "ghost";

export interface ButtonProps {
  label: string;
  icon?: string;
  style?: ButtonStyle;
  action_id?: string;
  enabled?: boolean;
}

export type TimerState = "idle" | "running" | "paused" | "completed";
export type TimerMode = "countdown" | "stopwatch";

export interface TimerProps {
  label?: string;
  duration_ms: number;
  remaining_ms: number;
  state: TimerState;
  mode?: TimerMode;
}

export type MediaType = "audio" | "video";
export type MediaState = "playing" | "paused" | "stopped" | "buffering";

export interface MediaPlayerProps {
  title?: string;
  source_url: string;
  media_type: MediaType;
  poster_url?: string;
  state?: MediaState;
  position_ms?: number;
  duration_ms?: number;
  /** 0.0 - 1.0 */
  volume?: number;
  loop?: boolean;
}

export type MapStyle = "streets" | "satellite" | "terrain" | "dark";

export interface LatLon {
  lat: number;
  lon: number;
}

export interface MapMarker extends LatLon {
  label?: string;
  color?: string;
}

export interface Map3DProps {
  center: LatLon;
  zoom?: number;
  style?: MapStyle;
  pitch_deg?: number;
  markers?: MapMarker[];
}

export type DeviceType =
  | "light"
  | "thermostat"
  | "lock"
  | "plug"
  | "speaker"
  | "blind"
  | "sensor"
  | "camera";

export interface DeviceState {
  on?: boolean;
  /** Generic 0-100 level (brightness, volume, blind position). */
  level?: number;
  temperature_c?: number;
  locked?: boolean;
  /** Device-specific keys are allowed. */
  [key: string]: unknown;
}

export interface SmartHomeDevice {
  id: string;
  name: string;
  type: DeviceType;
  state: DeviceState;
  unit?: string;
}

export interface SmartHomePanelProps {
  room?: string;
  devices: SmartHomeDevice[];
}

export type TodoPriority = "low" | "medium" | "high";

export interface TodoItem {
  id: string;
  text: string;
  done?: boolean;
  priority?: TodoPriority;
}

export interface TodoListProps {
  title?: string;
  items: TodoItem[];
}

export type ImageBoardLayout = "grid" | "carousel" | "stack";

export interface BoardImage {
  url: string;
  caption?: string;
  alt?: string;
}

export interface ImageBoardProps {
  title?: string;
  images: BoardImage[];
  layout?: ImageBoardLayout;
  columns?: number;
}

/* ------------------------------------------------------------------ */
/* v1.1 perception widgets (PROTOCOL.md §8.5)                          */
/* ------------------------------------------------------------------ */

export interface VisionAnnotationProps {
  label: string;
  confidence?: number;
  detail?: string;
  leader_line?: boolean;
  target_object_id?: string;
  target_position?: Vec3;
  color?: string;
  icon?: string;
}

export interface BoundingBox3DProps {
  label: string;
  confidence?: number;
  /** [width, height, depth] in meters. */
  size: Vec3;
  color?: string;
  filled?: boolean;
  target_object_id?: string;
}

export type CaptionSpeaker = "user" | "other" | "jarvis" | "unknown";

export interface LiveCaptionProps {
  /** Caption lines, newest last. */
  lines: string[];
  speaker?: CaptionSpeaker;
  max_lines?: number;
  language?: string;
  translated?: boolean;
}

export type PassthroughCamera = "rgb_center" | "rgb_left" | "rgb_right";

export interface VisionFeedProps {
  title?: string;
  source?: PassthroughCamera;
  frozen?: boolean;
  fps?: number;
  frame_url?: string;
  show_detections?: boolean;
}

export interface SceneLabelProps {
  text: string;
  icon?: string;
  color?: string;
  pin?: boolean;
}

/* ------------------------------------------------------------------ */
/* v1.1 feature widgets (FEATURES.md §3)                              */
/* ------------------------------------------------------------------ */

export type TimeFormat = "12h" | "24h";
export type ClockStyle = "analog" | "digital";

export interface ClockProps {
  timezone?: string;
  format?: TimeFormat;
  style?: ClockStyle;
  show_seconds?: boolean;
  show_date?: boolean;
  label?: string;
}

export interface WorldClockZone {
  label: string;
  timezone: string;
  format?: TimeFormat;
}

export interface WorldClockProps {
  zones: WorldClockZone[];
  style?: "list" | "row";
}

export type CalendarView = "day" | "week" | "month" | "agenda";

export interface CalendarEvent {
  id: string;
  title: string;
  start: string;
  end?: string;
  location?: string;
  color?: string;
  all_day?: boolean;
}

export interface CalendarProps {
  title?: string;
  view?: CalendarView;
  date?: string;
  events: CalendarEvent[];
}

export interface StockSymbol {
  symbol: string;
  price: number;
  change_pct?: number;
  currency?: string;
}

export interface StocksTickerProps {
  title?: string;
  symbols: StockSymbol[];
  scroll?: boolean;
}

export interface NewsArticle {
  id: string;
  headline: string;
  source?: string;
  summary?: string;
  url?: string;
  image_url?: string;
  published_at?: string;
}

export interface NewsFeedProps {
  title?: string;
  category?: string;
  articles: NewsArticle[];
}

export type TranslatorMode = "text" | "conversation" | "sign";

export interface TranslatorProps {
  source_lang: string;
  target_lang: string;
  source_text?: string;
  translated_text?: string;
  mode?: TranslatorMode;
  listening?: boolean;
}

export interface RecipeCardProps {
  title: string;
  servings?: number;
  prep_min?: number;
  cook_min?: number;
  ingredients: string[];
  steps: string[];
  image_url?: string;
  current_step?: number;
}

export type WhiteboardBackground = "white" | "dark" | "grid";

export interface WhiteboardStroke {
  /** 2D points [x, y] in board space (0-1). */
  points: Array<[number, number]>;
  color?: string;
  width?: number;
}

export interface WhiteboardProps {
  title?: string;
  width_m?: number;
  height_m?: number;
  background?: WhiteboardBackground;
  strokes?: WhiteboardStroke[];
  editable?: boolean;
}

export type StickyColor = "yellow" | "pink" | "blue" | "green" | "orange";

export interface StickyNoteProps {
  text: string;
  color?: StickyColor;
  pinned?: boolean;
  author?: string;
}

export interface CodeViewerProps {
  code: string;
  language?: string;
  title?: string;
  theme?: "dark" | "light";
  wrap?: boolean;
  highlight_lines?: number[];
}

export type DocType = "pdf" | "markdown" | "text" | "docx";

export interface DocumentViewerProps {
  url: string;
  title?: string;
  doc_type?: DocType;
  page?: number;
  page_count?: number;
}

export interface WebPanelProps {
  url: string;
  title?: string;
  width_m?: number;
  height_m?: number;
  interactive?: boolean;
  scroll_y?: number;
}

export type AvatarState = "idle" | "listening" | "thinking" | "speaking";
export type AvatarEmotion = "neutral" | "happy" | "concerned" | "alert";
export type AvatarStyle = "orb" | "face" | "ring";

export interface AvatarProps {
  name?: string;
  state?: AvatarState;
  emotion?: AvatarEmotion;
  style?: AvatarStyle;
  speaking_text?: string;
}

export type NavStyle = "arrow" | "beam" | "path";

export interface NavigationArrowProps {
  target_label?: string;
  /** Unit direction vector to the destination. */
  direction: Vec3;
  distance_m?: number;
  eta_min?: number;
  color?: string;
  style?: NavStyle;
}

export interface HealthRing {
  label: string;
  value: number;
  goal: number;
  unit?: string;
  color?: string;
}

export interface HealthRingProps {
  title?: string;
  rings: HealthRing[];
}

export type VisualizerStyle = "bars" | "wave" | "particles" | "sphere";

export interface MusicVisualizerProps {
  track?: string;
  artist?: string;
  style?: VisualizerStyle;
  /** Spectrum bins, each 0.0-1.0. */
  amplitude?: number[];
  color?: string;
  playing?: boolean;
}

export interface GraphNode {
  id: string;
  label?: string;
  group?: string;
  size?: number;
  color?: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  weight?: number;
  label?: string;
}

export type GraphLayout = "force" | "radial" | "grid";

export interface Graph3DProps {
  title?: string;
  nodes: GraphNode[];
  edges?: GraphEdge[];
  layout?: GraphLayout;
  directed?: boolean;
}

export interface DataTableColumn {
  key: string;
  label?: string;
  type?: "string" | "number" | "bool";
}

export interface DataTableProps {
  title?: string;
  columns: DataTableColumn[];
  /** Each row maps a column key to a value. */
  rows: Array<Record<string, unknown>>;
  sortable?: boolean;
  page?: number;
}

export type MeasureUnit = "m" | "cm" | "ft" | "in";
export type MeasureMode = "distance" | "area" | "angle";

export interface MeasuringTapeProps {
  /** World-space points [x, y, z] in meters. */
  points: Vec3[];
  unit?: MeasureUnit;
  distance_m?: number;
  mode?: MeasureMode;
  label?: string;
}

export type PomodoroPhase = "focus" | "short_break" | "long_break" | "idle";
export type PomodoroState = "running" | "paused" | "idle";

export interface PomodoroProps {
  phase: PomodoroPhase;
  remaining_ms: number;
  focus_ms?: number;
  break_ms?: number;
  completed_sessions?: number;
  state?: PomodoroState;
  task?: string;
}

export type ImageGenStatus = "queued" | "generating" | "done" | "error";

export interface GeneratedImage {
  url: string;
  seed?: number;
}

export interface ImageGenViewerProps {
  prompt: string;
  status?: ImageGenStatus;
  images?: GeneratedImage[];
  progress?: number;
  model?: string;
  error?: string;
}

export type GlobeStyle = "earth" | "night" | "political" | "topographic";

export interface GlobeMarker {
  lat: number;
  lon: number;
  label?: string;
  color?: string;
}

export interface GlobeArc {
  from_lat: number;
  from_lon: number;
  to_lat: number;
  to_lon: number;
  color?: string;
}

export interface VolumetricGlobeProps {
  style?: GlobeStyle;
  markers?: GlobeMarker[];
  arcs?: GlobeArc[];
  rotation_speed?: number;
  auto_rotate?: boolean;
  highlight_country?: string;
}

export interface LauncherApp {
  id: string;
  name: string;
  icon?: string;
  color?: string;
  badge?: number;
}

export type LauncherLayout = "grid" | "ring" | "shelf";

export interface SystemLauncherProps {
  title?: string;
  apps: LauncherApp[];
  columns?: number;
  layout?: LauncherLayout;
}

export type ToastSeverity = "info" | "success" | "warning" | "error";

export interface ToastAction {
  id: string;
  label: string;
}

export interface NotificationToastProps {
  title: string;
  body?: string;
  severity?: ToastSeverity;
  icon?: string;
  source?: string;
  actions?: ToastAction[];
  auto_dismiss_ms?: number;
}

export type SettingType = "toggle" | "slider" | "select" | "button";

export interface SettingItem {
  id: string;
  label: string;
  type: SettingType;
  value?: boolean | number | string;
  options?: string[];
  min?: number;
  max?: number;
  unit?: string;
}

export interface SettingsSection {
  title: string;
  settings: SettingItem[];
}

export interface SettingsPanelProps {
  title?: string;
  sections: SettingsSection[];
}

/* ------------------------------------------------------------------ */
/* Widget type registry (keep in sync with registry.json widget_type) */
/* ------------------------------------------------------------------ */

export const WIDGET_TYPES = [
  // v1.0
  "weather_orb",
  "chart_3d",
  "model_viewer",
  "panel",
  "text_label",
  "button",
  "timer",
  "media_player",
  "map_3d",
  "smart_home_panel",
  "todo_list",
  "image_board",
  // v1.1 perception
  "vision_annotation",
  "bounding_box_3d",
  "live_caption",
  "vision_feed",
  "scene_label",
  // v1.1 features
  "clock",
  "world_clock",
  "calendar",
  "stocks_ticker",
  "news_feed",
  "translator",
  "recipe_card",
  "whiteboard",
  "sticky_note",
  "code_viewer",
  "document_viewer",
  "web_panel",
  "avatar",
  "navigation_arrow",
  "health_ring",
  "music_visualizer",
  "graph_3d",
  "data_table",
  "measuring_tape",
  "pomodoro",
  "image_gen_viewer",
  "volumetric_globe",
  "system_launcher",
  "notification_toast",
  "settings_panel",
] as const;

export type WidgetType = (typeof WIDGET_TYPES)[number];

/** Map from widget_type to its props interface. */
export interface WidgetPropsMap {
  // v1.0
  weather_orb: WeatherOrbProps;
  chart_3d: Chart3DProps;
  model_viewer: ModelViewerProps;
  panel: PanelProps;
  text_label: TextLabelProps;
  button: ButtonProps;
  timer: TimerProps;
  media_player: MediaPlayerProps;
  map_3d: Map3DProps;
  smart_home_panel: SmartHomePanelProps;
  todo_list: TodoListProps;
  image_board: ImageBoardProps;
  // v1.1 perception
  vision_annotation: VisionAnnotationProps;
  bounding_box_3d: BoundingBox3DProps;
  live_caption: LiveCaptionProps;
  vision_feed: VisionFeedProps;
  scene_label: SceneLabelProps;
  // v1.1 features
  clock: ClockProps;
  world_clock: WorldClockProps;
  calendar: CalendarProps;
  stocks_ticker: StocksTickerProps;
  news_feed: NewsFeedProps;
  translator: TranslatorProps;
  recipe_card: RecipeCardProps;
  whiteboard: WhiteboardProps;
  sticky_note: StickyNoteProps;
  code_viewer: CodeViewerProps;
  document_viewer: DocumentViewerProps;
  web_panel: WebPanelProps;
  avatar: AvatarProps;
  navigation_arrow: NavigationArrowProps;
  health_ring: HealthRingProps;
  music_visualizer: MusicVisualizerProps;
  graph_3d: Graph3DProps;
  data_table: DataTableProps;
  measuring_tape: MeasuringTapeProps;
  pomodoro: PomodoroProps;
  image_gen_viewer: ImageGenViewerProps;
  volumetric_globe: VolumetricGlobeProps;
  system_launcher: SystemLauncherProps;
  notification_toast: NotificationToastProps;
  settings_panel: SettingsPanelProps;
}

/** Convenience alias: props for a given widget_type. */
export type PropsFor<T extends WidgetType> = WidgetPropsMap[T];

/** Unity prefab id per widget_type (mirrors registry.json prefab_id). */
export const PREFAB_IDS: Record<WidgetType, string> = {
  // v1.0
  weather_orb: "Holo_WeatherOrb",
  chart_3d: "Holo_Chart3D",
  model_viewer: "Holo_ModelViewer",
  panel: "Holo_Panel",
  text_label: "Holo_TextLabel",
  button: "Holo_Button",
  timer: "Holo_Timer",
  media_player: "Holo_MediaPlayer",
  map_3d: "Holo_Map3D",
  smart_home_panel: "Holo_SmartHomePanel",
  todo_list: "Holo_TodoList",
  image_board: "Holo_ImageBoard",
  // v1.1 perception
  vision_annotation: "Holo_VisionAnnotation",
  bounding_box_3d: "Holo_BoundingBox3D",
  live_caption: "Holo_LiveCaption",
  vision_feed: "Holo_VisionFeed",
  scene_label: "Holo_SceneLabel",
  // v1.1 features
  clock: "Holo_Clock",
  world_clock: "Holo_WorldClock",
  calendar: "Holo_Calendar",
  stocks_ticker: "Holo_StocksTicker",
  news_feed: "Holo_NewsFeed",
  translator: "Holo_Translator",
  recipe_card: "Holo_RecipeCard",
  whiteboard: "Holo_Whiteboard",
  sticky_note: "Holo_StickyNote",
  code_viewer: "Holo_CodeViewer",
  document_viewer: "Holo_DocumentViewer",
  web_panel: "Holo_WebPanel",
  avatar: "Holo_Avatar",
  navigation_arrow: "Holo_NavigationArrow",
  health_ring: "Holo_HealthRing",
  music_visualizer: "Holo_MusicVisualizer",
  graph_3d: "Holo_Graph3D",
  data_table: "Holo_DataTable",
  measuring_tape: "Holo_MeasuringTape",
  pomodoro: "Holo_Pomodoro",
  image_gen_viewer: "Holo_ImageGenViewer",
  volumetric_globe: "Holo_VolumetricGlobe",
  system_launcher: "Holo_SystemLauncher",
  notification_toast: "Holo_NotificationToast",
  settings_panel: "Holo_SettingsPanel",
};

/* ------------------------------------------------------------------ */
/* The Holographic Object (PROTOCOL.md §5.6)                          */
/* ------------------------------------------------------------------ */

export interface HoloObject<T extends WidgetType = WidgetType> {
  /** Server-assigned, stable for the object's lifetime. */
  object_id?: string;
  widget_type: T;
  transform: Transform;
  props: WidgetPropsMap[T];
  interactable?: boolean;
  /** Subset of the widget's supported interactions. */
  interactions?: Interaction[];
  /** 0 = persists until destroyed. */
  ttl_ms?: number;
}

/** Discriminated union over every concrete widget type. */
export type AnyHoloObject = { [K in WidgetType]: HoloObject<K> }[WidgetType];

/** Partial patch for `holo.update` (PROTOCOL.md §5.8). */
export interface HoloObjectPatch {
  object_id: string;
  transform?: Partial<Transform>;
  props?: Partial<WidgetPropsMap[WidgetType]>;
}

/* ------------------------------------------------------------------ */
/* Interaction events (PROTOCOL.md §5.11)                             */
/* ------------------------------------------------------------------ */

export interface ClientInteraction<T extends WidgetType = WidgetType> {
  object_id: string;
  widget_type: T;
  action: Interaction;
  /** Optional sub-element id within the widget (see registry events[].element). */
  element?: string;
  value?: Record<string, unknown>;
  hand?: "left" | "right";
}
