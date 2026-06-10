"""Shared pytest fixtures/helpers for the agent-backend test suite."""

from __future__ import annotations

from pathlib import Path

import pytest

from jarvis_backend.agent import Agent
from jarvis_backend.agent.llm import MockLLM
from jarvis_backend.config import Config


def make_config(tmp_path: Path, **overrides) -> Config:
    """A self-contained config: mock LLM, fallback catalog, temp data dir."""
    params = dict(
        host="127.0.0.1",
        port=0,
        ws_path="/jarvis",
        llm_provider="mock",
        holo_registry_path=None,  # force built-in fallback catalog
        data_dir=Path(tmp_path),
        weather_api_key=None,
    )
    params.update(overrides)
    return Config(**params)


def build_mock_agent(tmp_path: Path) -> Agent:
    return Agent.build(make_config(tmp_path), MockLLM())


@pytest.fixture
def config(tmp_path: Path) -> Config:
    return make_config(tmp_path)


@pytest.fixture
def agent(tmp_path: Path) -> Agent:
    return build_mock_agent(tmp_path)
