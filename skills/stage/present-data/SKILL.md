---
name: present-data
description: >-
  Choose the right visualization for a dataset and render it — table, chart,
  network graph, or globe — then place it well. Use when an agent has structured
  data to show, for "chart this", "show it as a table", "graph these
  relationships", or comparisons. Triggers: chart, graph, table, visualize, plot,
  compare, breakdown, show the data, trend.
license: MIT
compatibility: >-
  Requires JarvisVR agent-backend stage runtime. Widget props validated against
  holo-tools/registry.json.
metadata:
  agent: stage-agent
  category: stage
  version: "1.0"
  author: jarvisvr
allowed-tools: show_data_table show_chart show_graph show_panel arrange_holograms
---
# Present Data

Pick the visualization that best fits the data's shape and the user's question,
build valid props, and place it comfortably.

## Choosing the widget

| Data shape / intent | Widget | Tool |
| ------------------- | ------ | ---- |
| Rows × columns, look up values | `data_table` | `show_data_table` |
| Trend / comparison of series | `chart_3d` (`line`/`bar`) | `show_chart` |
| Distribution / parts of whole | `chart_3d` (`pie`/`scatter`) | `show_chart` |
| Entities + relationships | `graph_3d` | `show_graph` |
| Geographic points / flows | `volumetric_globe` / `map_3d` | `show_globe` / `show_map` |
| Short prose / KPIs | `panel` | `show_panel` |

## Steps

1. **Inspect the data** (types, cardinality) and the user's question.
2. **Select** from the table above; prefer the simplest that answers it.
3. **Build props** to schema (e.g. `chart_3d` requires `chart_type` + `series`;
   `data_table` requires `columns` + `rows`).
4. **Render**, then place via `arrange_holograms` (charts/tables read best
   `world`/`surface` at ~1.2 m).
5. **Narrate the takeaway** in `agent.speech` — the headline, not every number.

## Output

`chart_3d` (`show_chart`, props per registry.json):

```json
{ "widget_type": "chart_3d",
  "props": { "chart_type": "bar", "title": "Quarterly Revenue",
             "labels": ["Q1","Q2","Q3","Q4"],
             "series": [ { "name": "FY2026", "values": [14,20,15,26], "color": "#4FC3F7" } ],
             "y_axis_label": "Revenue ($M)", "show_legend": true } }
```

`data_table` (`show_data_table`):

```json
{ "widget_type": "data_table",
  "props": { "title": "Devices",
             "columns": [ { "key": "name", "label": "Name", "type": "string" },
                          { "key": "watts", "label": "Watts", "type": "number" } ],
             "rows": [ { "name": "Ceiling Light", "watts": 12 }, { "name": "Heater", "watts": 0 } ],
             "sortable": true } }
```

## Edge cases

- **Tiny data (1–2 numbers)** → a `panel`/`text_label`, not a chart.
- **Too many series/rows** → aggregate or paginate; keep it legible.
- **Categorical vs continuous** → bar for categories, line for time series.
- **Selection events** (`select_point`, `select_row`) → drill down or explain.
- **Raw source, not data** → that's `research-agent`; you visualize what it
  returns.
