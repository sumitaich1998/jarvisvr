"""Pipeline state machine with Mock engines + synthetic audio frames."""

from __future__ import annotations

from jarvis_voice.pipeline import PipelineCallbacks, PipelineState, VoicePipeline
from jarvis_voice.stt import MockSTT, Transcriber, TranscriptResult
from jarvis_voice.tts import MockTTS

from conftest import FakeWake, fast_config


def _record_events():
    events = []
    cb = PipelineCallbacks(
        on_state_change=lambda s: events.append(("state", s)),
        on_wake=lambda: events.append(("wake",)),
        on_partial=lambda t: events.append(("partial", t)),
        on_transcript=lambda r: events.append(("transcript", r.text)),
        on_utterance_empty=lambda: events.append(("empty",)),
        on_speak_start=lambda t: events.append(("speak_start", t)),
        on_speak_end=lambda t: events.append(("speak_end", t)),
    )
    return events, cb


def test_wake_to_transcript_happy_path(config, loud, quiet):
    events, cb = _record_events()
    pipe = VoicePipeline(FakeWake(), MockSTT(config), MockTTS(config), config, cb)

    assert pipe.state is PipelineState.LISTENING

    # First frame trips the (fake) wake word -> recording.
    pipe.process_frame(quiet)
    assert pipe.state is PipelineState.RECORDING
    assert ("wake",) in events

    # Voice the utterance, then go silent long enough to endpoint.
    for _ in range(4):
        pipe.process_frame(loud)
    for _ in range(config.frames_for_ms(config.silence_ms) + 2):
        pipe.process_frame(quiet)

    assert pipe.state is PipelineState.LISTENING
    transcripts = [e for e in events if e[0] == "transcript"]
    assert transcripts, "expected a final transcript"
    assert transcripts[-1][1] == config.mock_transcript


def test_streaming_partials_emitted(config, loud, quiet):
    events, cb = _record_events()
    pipe = VoicePipeline(FakeWake(), MockSTT(config), MockTTS(config), config, cb)
    pipe.process_frame(quiet)  # wake
    for _ in range(6):
        pipe.process_frame(loud)
    for _ in range(config.frames_for_ms(config.silence_ms) + 2):
        pipe.process_frame(quiet)
    partials = [e for e in events if e[0] == "partial"]
    assert partials, "MockSTT should emit interim partials while recording"


def test_no_speech_after_wake_emits_empty():
    cfg = fast_config(mock_transcript="")  # mock returns empty -> utterance_empty
    events, cb = _record_events()
    quiet = b"\x00\x00" * cfg.samples_per_frame
    pipe = VoicePipeline(FakeWake(), MockSTT(cfg), MockTTS(cfg), cfg, cb)

    pipe.process_frame(quiet)  # wake
    assert pipe.state is PipelineState.RECORDING
    for _ in range(cfg.frames_for_ms(cfg.wake_grace_ms) + 1):
        pipe.process_frame(quiet)

    assert pipe.state is PipelineState.LISTENING
    assert ("empty",) in events
    assert not [e for e in events if e[0] == "transcript"]


def test_max_utterance_endpoints():
    events, cb = _record_events()
    cfg = fast_config(max_utterance_ms=120)  # ~4 frames
    loud_f = b"\x40\x40" * cfg.samples_per_frame
    pipe = VoicePipeline(FakeWake(), MockSTT(cfg), MockTTS(cfg), cfg, cb)
    pipe.process_frame(loud_f)  # wake
    for _ in range(cfg.frames_for_ms(cfg.max_utterance_ms) + 1):
        pipe.process_frame(loud_f)
    assert pipe.state is PipelineState.LISTENING


def test_speak_path_invokes_tts(config):
    spoken = []

    class RecordingTTS(MockTTS):
        def speak(self, text):
            spoken.append(text)

    events, cb = _record_events()
    pipe = VoicePipeline(FakeWake(), MockSTT(config), RecordingTTS(config), config, cb)
    pipe.speak("Here is the weather in Tokyo.")
    assert spoken == ["Here is the weather in Tokyo."]
    assert ("speak_start", "Here is the weather in Tokyo.") in events
    assert ("speak_end", "Here is the weather in Tokyo.") in events


def test_synthesize_returns_wav(config):
    pipe = VoicePipeline(FakeWake(), MockSTT(config), MockTTS(config), config)
    wav = pipe.synthesize("hello")
    assert wav[:4] == b"RIFF"


def test_simulate_utterance(config):
    events, cb = _record_events()
    pipe = VoicePipeline(FakeWake(), MockSTT(config), MockTTS(config), config, cb)
    result = pipe.simulate_utterance("turn on the lights")
    assert isinstance(result, TranscriptResult)
    assert result.text == "turn on the lights"
    assert ("transcript", "turn on the lights") in events


def test_callback_exceptions_do_not_crash(config, loud, quiet):
    def boom(_):
        raise RuntimeError("callback blew up")

    cb = PipelineCallbacks(on_transcript=boom)
    pipe = VoicePipeline(FakeWake(), MockSTT(config), MockTTS(config), config, cb)
    pipe.process_frame(quiet)  # wake
    for _ in range(4):
        pipe.process_frame(loud)
    for _ in range(config.frames_for_ms(config.silence_ms) + 2):
        pipe.process_frame(quiet)
    # Should have returned to LISTENING despite the throwing callback.
    assert pipe.state is PipelineState.LISTENING
