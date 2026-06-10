"""Final branch mop-up: setup-wizard chmod/mask, widget schema default,
extract_city edges, and a couple of llm/tracer details."""

from __future__ import annotations

import os
from pathlib import Path

from jarvis_backend import setup_wizard as W
from jarvis_backend.agent.llm import extract_city
from jarvis_backend.agent.tools import widget_tools as WT
from jarvis_backend.agent.tools.base import ToolRegistry
from jarvis_backend.catalog import WidgetCatalog


# --- setup_wizard edges -----------------------------------------------------


def test_mask_secret_none():
    assert W.mask_secret(None) == "(none)"
    assert W.mask_secret("") == "(none)"


def test_update_env_file_chmod_oserror_is_swallowed(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise OSError("no chmod here")

    monkeypatch.setattr(W.os, "chmod", boom)
    env = tmp_path / ".env"
    W.update_env_file(env, {"JARVIS_LLM": "mock"})  # must not raise
    assert "JARVIS_LLM=mock" in env.read_text()


# --- widget_tools: non-object schema -> default params ----------------------


def test_register_widget_tools_non_object_schema(tmp_path):
    cat = WidgetCatalog({"widgets": {"thingy": {"prefab_id": "T", "props_schema": {"type": "string"}}}})
    reg = ToolRegistry()
    WT.register_widget_tools(reg, cat)
    params = reg.get("show_thingy").parameters
    assert params == {"type": "object", "properties": {}}


# --- extract_city edges -----------------------------------------------------


def test_extract_city_empty_candidate_defaults():
    # candidate collapses to empty after stop-trail removal -> default city
    assert extract_city("weather in please") == "San Francisco"
    assert extract_city("just chatting") == "San Francisco"
