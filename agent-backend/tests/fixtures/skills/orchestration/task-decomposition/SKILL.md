---
name: task-decomposition
description: >-
  Break a user goal into a small DAG of independent sub-tasks and decide which
  specialist should own each. Use when a request bundles multiple intents
  (e.g. "what's this AND the weather AND start a timer").
license: MIT
compatibility: Requires JarvisVR agent-backend with orchestration enabled
metadata:
  agent: jarvis
  category: orchestration
  version: "1.0"
  author: jarvisvr
allowed-tools: []
---

# Task decomposition

1. Identify the distinct intents in the goal (perception, research, productivity, …).
2. Emit one sub-task per intent; mark dependencies (e.g. presentation depends on data).
3. Prefer independent siblings that can run in parallel over deep chains.
