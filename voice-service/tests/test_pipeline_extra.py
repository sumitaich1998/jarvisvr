"""Coverage for the remaining VoicePipeline branches + build_pipeline."""

from __future__ import annotations

import threading

from jarvis_voice import audio
from jarvis_voice.pipeline import (
    PipelineCallbacks,
    PipelineState,
    VoicePipeline,
    build_pipeline,
)
from jarvis_voice.stt import MockSTT, Transcriber, TranscriptResult
from jarvis_voice.tts import MockTTS

from conftest import FakeWake, fast_config


class DummySTT(Transcriber):
    name = "dummy"

    def final(self, pcm=None):
        return TranscriptResult("dummy", 1.0, True)


def _pipe(cfg=None, stt=None, cb=None):
    cfg = cfg or fast_config()
    return VoicePipeline(FakeWake(armed=False), stt or MockSTT(cfg), MockTTS(cfg), cfg, cb)


def test_set_state_noop_when_same():
    pipe = _pipe()
    pipe._set_state(pipe.state)  # same -> no callback, no change
    assert pipe.state is PipelineState.LISTENING


def test_barge_check_quiet_resets_run():
    cfg = fast_config()
    pipe = _pipe(cfg)
    pipe._speaking = True
    pipe._barge_run = 2
    pipe.process_frame(audio.silence(cfg.frame_ms))  # quiet -> run resets to 0
    assert pipe._barge_run == 0
    assert pipe.is_speaking() is True


def test_trigger_barge_in_idempotent():
    fired = []
    pipe = _pipe(cb=PipelineCallbacks(on_barge_in=lambda: fired.append(1)))
    pipe._speaking = True
    pipe._trigger_barge_in()
    pipe._trigger_barge_in()  # already requested -> early return
    assert fired == [1]


def test_run_breaks_on_preset_stop():
    cfg = fast_config()
    pipe = _pipe(cfg)
    stop = threading.Event()
    stop.set()
    pipe.run([audio.silence(cfg.frame_ms)] * 3, stop=stop)  # breaks immediately
    assert pipe.state is PipelineState.LISTENING


def test_run_consumes_source_default_stop():
    cfg = fast_config()
    pipe = _pipe(cfg)
    pipe.run([audio.silence(cfg.frame_ms)] * 2)  # uses internal stop event
    assert pipe.state is PipelineState.LISTENING


def test_stop_sets_event():
    pipe = _pipe()
    pipe.stop()
    assert pipe._stop.is_set()


def test_speak_empty_is_noop():
    pipe = _pipe()
    pipe.speak("")  # early return, no on_speak_start


def test_set_language_forwards_to_engines():
    pipe = _pipe()
    pipe.set_language("es")  # MockSTT/MockTTS accept the hook without error


def test_simulate_utterance_empty_emits_empty():
    events = []
    pipe = _pipe(cb=PipelineCallbacks(
        on_transcript=lambda r: events.append(("t", r.text)),
        on_utterance_empty=lambda: events.append(("empty",)),
    ))
    pipe.simulate_utterance("")
    assert ("empty",) in events
    assert not [e for e in events if e[0] == "t"]


def test_simulate_utterance_non_mock_stt():
    cfg = fast_config()
    got = []
    pipe = VoicePipeline(
        FakeWake(armed=False), DummySTT(), MockTTS(cfg), cfg,
        PipelineCallbacks(on_transcript=lambda r: got.append(r.text)),
    )
    result = pipe.simulate_utterance("hello there")
    assert result.text == "hello there"
    assert got == ["hello there"]


def test_close_closes_engines():
    pipe = _pipe()
    pipe.close()  # iterates wake/stt/tts close() without error


def test_synthesize_returns_wav():
    assert _pipe().synthesize("hi")[:4] == b"RIFF"


def test_build_pipeline_headless():
    pipe = build_pipeline(fast_config())
    assert pipe.wake.name == "energy"
    assert pipe.stt.name == "mock"
    assert pipe.tts.name == "mock"
