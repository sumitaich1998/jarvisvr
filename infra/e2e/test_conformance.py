"""Pytest wrapper: run the scripted conversation against the mock and assert
full protocol conformance."""

from __future__ import annotations

import asyncio

from harness import (
    MT,
    run_barge_in_conformance,
    run_conformance,
    run_multimodal_conformance,
    run_settings_conformance,
)


def test_scripted_conversation_is_conformant(mock_backend_url):
    report = asyncio.run(run_conformance(mock_backend_url))

    # Every received frame must have validated against the shared-protocol schemas.
    assert not report.violations, "conformance violations:\n" + "\n".join(report.violations)

    # And the scripted flow must actually have exercised the protocol.
    assert report.received > 0
    assert report.sent > 0
    seen = set(report.seen_types)
    for expected in (MT.SERVER_HELLO_ACK, MT.SERVER_HEARTBEAT, MT.AGENT_SPEECH, MT.HOLO_SPAWN, MT.HOLO_UPDATE):
        assert expected in seen, f"expected to receive a {expected} message; saw {sorted(seen)}"


def test_strict_props_run_also_conformant(mock_backend_url):
    # With no holo-tools registry present, strict-props changes nothing; when a
    # registry lands, this guards props-schema conformance too.
    report = asyncio.run(run_conformance(mock_backend_url, strict_props=True))
    assert not report.violations, "strict-props violations:\n" + "\n".join(report.violations)


def test_multimodal_vision_turn_is_conformant(mock_backend_url):
    report = asyncio.run(run_multimodal_conformance(mock_backend_url))
    assert not report.violations, "multimodal violations:\n" + "\n".join(report.violations)

    assert report.received > 0
    seen = set(report.seen_types)
    for expected in (
        MT.SERVER_HELLO_ACK,
        MT.PERCEPTION_REQUEST,
        MT.AGENT_OBSERVATION,
        MT.HOLO_SPAWN,
        MT.AGENT_SPEECH,
    ):
        assert expected in seen, f"expected to receive a {expected} message; saw {sorted(seen)}"


def test_multimodal_strict_props_also_conformant(mock_backend_url):
    # vision_annotation is in the registry now; strict props must still pass.
    report = asyncio.run(run_multimodal_conformance(mock_backend_url, strict_props=True))
    assert not report.violations, "multimodal strict-props violations:\n" + "\n".join(report.violations)


def test_barge_in_is_conformant(mock_backend_url):
    # §5.14: a user turn followed by client.barge_in must be handled gracefully —
    # no protocol violation, no server.error, and the connection stays responsive.
    report = asyncio.run(run_barge_in_conformance(mock_backend_url))
    assert not report.violations, "barge_in violations:\n" + "\n".join(report.violations)

    seen = set(report.seen_types)
    assert MT.SERVER_HELLO_ACK in seen
    # The heartbeat round-trip after the barge_in proves the backend stayed alive.
    assert MT.SERVER_HEARTBEAT in seen, f"expected liveness after barge_in; saw {sorted(seen)}"


def test_settings_is_conformant(mock_backend_url):
    # §5.15: settings_get returns a conformant catalog; settings_update changes
    # the provider/model and reports key_set:true; and no api_key ever leaks.
    report = asyncio.run(run_settings_conformance(mock_backend_url))
    assert not report.violations, "settings violations:\n" + "\n".join(report.violations)

    seen = set(report.seen_types)
    assert MT.SERVER_SETTINGS in seen, f"expected a server.settings; saw {sorted(seen)}"
