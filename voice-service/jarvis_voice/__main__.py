"""``jarvis-voice`` command-line interface.

Subcommands:

* ``demo``     — local loop: mic → wake → STT → print (mock-friendly; falls back
                 to an interactive "type to simulate speech" REPL with no mic).
* ``ambient``  — local demo of continuous ambient listening + sound events (v1.1).
* ``bridge``   — connect to the agent-backend and act as the voice front-end.
* ``say TEXT`` — TTS smoke test (optionally ``--out file.wav``).
* ``selftest`` — headless end-to-end check using the configured/fallback engines.
* ``devices``  — list audio devices (diagnostics).

Run ``python -m jarvis_voice ...`` or the installed ``jarvis-voice`` script.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from typing import List, Optional

from . import __version__, audio, protocol
from .config import Config
from .pipeline import PipelineCallbacks, PipelineState, build_pipeline
from .stt import TranscriptResult

log = logging.getLogger("jarvis_voice")


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _banner(config: Config) -> None:
    print(f"JarvisVR voice-service v{__version__}")
    print(f"  config: {config.summary()}")


# --------------------------------------------------------------------------- #
# say
# --------------------------------------------------------------------------- #
def cmd_say(config: Config, args: argparse.Namespace) -> int:
    from .tts import create_speaker

    speaker = create_speaker(config)
    text = args.text
    print(f"[tts={speaker.name}] speaking: {text!r}")
    if args.out:
        wav = speaker.synthesize(text)
        with open(args.out, "wb") as fh:
            fh.write(wav)
        print(f"wrote {len(wav)} bytes of WAV → {args.out}")
        if not args.no_play:
            speaker.speak(text)
    else:
        speaker.speak(text)
    return 0


# --------------------------------------------------------------------------- #
# devices
# --------------------------------------------------------------------------- #
def cmd_devices(config: Config, args: argparse.Namespace) -> int:
    print("audio backend available:", audio.audio_io_available())
    print(audio.list_devices())
    return 0


# --------------------------------------------------------------------------- #
# demo
# --------------------------------------------------------------------------- #
def cmd_demo(config: Config, args: argparse.Namespace) -> int:
    callbacks = PipelineCallbacks(
        on_state_change=lambda s: log.debug("state: %s", s.value),
        on_wake=lambda: print("  [wake] 👂 listening…"),
        on_partial=lambda t: print(f"  … {t}", end="\r", flush=True),
        on_transcript=lambda r: print(f"  📝 transcript: {r.text!r} (conf={r.confidence:.2f})"),
        on_utterance_empty=lambda: print("  (no speech detected)"),
        on_speak_start=lambda t: None,
    )
    pipeline = build_pipeline(config, callbacks)
    _banner(config)
    print(
        f"engines → wake={pipeline.wake.name} stt={pipeline.stt.name} tts={pipeline.tts.name}"
    )

    use_mic = audio.audio_io_available() and not args.simulate
    if use_mic:
        print('\nListening. Say "Jarvis …". Press Ctrl+C to quit.\n')
        from .audio import AudioUnavailable, MicStream

        try:
            with MicStream(
                sample_rate=config.sample_rate,
                frame_samples=config.samples_per_frame,
                input_device=config.input_device,
            ) as mic:
                pipeline.run(mic)
        except AudioUnavailable as exc:
            print(f"(mic unavailable: {exc}) — switching to simulate mode\n")
            use_mic = False
        except KeyboardInterrupt:
            print("\nbye.")
            return 0

    if not use_mic:
        print("\n[simulate] No mic loop. Type what you'd say to Jarvis (after the wake word).")
        print("           Each line is treated as a recognized utterance. Ctrl+C/empty to quit.\n")
        try:
            while True:
                try:
                    line = input("you> ").strip()
                except EOFError:
                    break
                if not line:
                    break
                result = pipeline.simulate_utterance(line)
                # Demonstrate the "mouth": acknowledge via TTS.
                pipeline.speak(f"You said: {result.text}")
        except KeyboardInterrupt:
            print()
    print("bye.")
    return 0


# --------------------------------------------------------------------------- #
# ambient (continuous listening + sound events)
# --------------------------------------------------------------------------- #
def cmd_ambient(config: Config, args: argparse.Namespace) -> int:
    from .ambient import AmbientCallbacks, build_ambient

    def on_scene(sc) -> None:
        sounds = ", ".join(f"{s['label']}:{s['confidence']:.2f}" for s in sc.sounds) or "—"
        if sc.ambient_transcript:
            body = f"[{sc.speaker}] {sc.ambient_transcript!r}"
        else:
            body = "(no speech)"
        print(f"  🎧 scene {sc.window_ms}ms {sc.loudness_db:6.1f} dBFS  sounds=[{sounds}]  {body}")

    def on_event(ev) -> None:
        print(f"  🔔 event: {ev.label}  (conf={ev.confidence:.2f}, {ev.loudness_db:.1f} dBFS)")

    ambient = build_ambient(config, AmbientCallbacks(on_audio_scene=on_scene, on_audio_event=on_event))
    _banner(config)
    print(f"ambient engines → stt={ambient.transcriber.name} sound_events={ambient.sounds.name}")

    use_mic = audio.audio_io_available() and not args.simulate
    if use_mic:
        print("\nAmbient listening on. Talk near the mic (no wake word). Ctrl+C to quit.\n")
        from .audio import AudioUnavailable, MicStream

        try:
            with MicStream(
                sample_rate=config.sample_rate,
                frame_samples=config.samples_per_frame,
                input_device=config.input_device,
            ) as mic:
                ambient.run(mic)
        except AudioUnavailable as exc:
            print(f"(mic unavailable: {exc}) — switching to simulate mode\n")
            use_mic = False
        except KeyboardInterrupt:
            print("\nbye.")
            return 0

    if not use_mic:
        print("\n[simulate] Generating synthetic room audio (no mic)…\n")
        # Vary the heuristic labels so the demo shows different sound events.
        try:
            ambient.sounds.set_canned(["doorbell", "music", "speech", "alarm"])
        except Exception:
            pass
        loud = audio.tone(300.0, config.frame_ms, sample_rate=config.sample_rate, amplitude=0.6)
        quiet = audio.silence(config.frame_ms, config.sample_rate)
        wpf = config.frames_for_ms(config.ambient_window_ms)
        for _ in range(3):  # a few windows of "someone talking, then quiet"
            for _ in range(max(1, wpf // 2)):
                ambient.process_frame(loud)
            for _ in range(wpf - wpf // 2 + 1):
                ambient.process_frame(quiet)
        print("\nType overheard speech to simulate a scene (empty/Ctrl+C to quit).\n")
        try:
            while True:
                try:
                    line = input("room> ").strip()
                except EOFError:
                    break
                if not line:
                    break
                ambient.simulate_scene(
                    transcript=line,
                    speaker=config.ambient_speaker,
                    sounds=[{"label": "speech", "confidence": 0.8}],
                    loudness_db=-26.0,
                )
        except KeyboardInterrupt:
            print()
    print("bye.")
    return 0


# --------------------------------------------------------------------------- #
# bridge
# --------------------------------------------------------------------------- #
def cmd_bridge(config: Config, args: argparse.Namespace) -> int:
    from .bridge import build_bridge

    _banner(config)
    print(f"bridging to {config.backend_url} …  (Ctrl+C to quit)")
    bridge = build_bridge(config, with_capture=not args.no_mic)

    try:
        asyncio.run(bridge.connect_and_run(max_retries=args.max_retries))
    except KeyboardInterrupt:
        print("\nbye.")
    return 0


# --------------------------------------------------------------------------- #
# selftest
# --------------------------------------------------------------------------- #
def cmd_selftest(config: Config, args: argparse.Namespace) -> int:
    print("=" * 60)
    print(f"JarvisVR voice-service selftest (v{__version__})")
    print("=" * 60)
    ok = True

    # 1) Protocol envelope round-trip.
    try:
        env = protocol.voice_transcript("hello jarvis", 0.91, session="S")
        parsed = protocol.Envelope.from_json(env.to_json())
        assert parsed.type == protocol.USER_VOICE_TRANSCRIPT
        assert parsed.text == "hello jarvis"
        assert parsed.is_version_compatible()
        print("[ok] protocol envelope build/parse")
    except Exception as exc:
        ok = False
        print(f"[FAIL] protocol: {exc}")

    # 2) Engine factories (fall back to mock/energy headless).
    pipeline = build_pipeline(config)
    print(
        f"[ok] engines selected: wake={pipeline.wake.name} "
        f"stt={pipeline.stt.name} tts={pipeline.tts.name}"
    )

    # 3) Mock pipeline turn via synthetic audio frames (wake → record → STT).
    transcripts: List[TranscriptResult] = []
    wakes: List[bool] = []
    pipeline.cb = PipelineCallbacks(
        on_wake=lambda: wakes.append(True),
        on_transcript=lambda r: transcripts.append(r),
    )
    try:
        loud = audio.tone(300.0, config.frame_ms, sample_rate=config.sample_rate, amplitude=0.6)
        quiet = audio.silence(config.frame_ms, config.sample_rate)
        # Enough loud frames to trip the wake (energy) + voice the utterance,
        # then enough quiet frames to endpoint on silence.
        frames = [loud] * 8 + [quiet] * (config.frames_for_ms(config.silence_ms) + 3)
        for fr in frames:
            pipeline.process_frame(fr)
        # With the energy fallback the wake fires; with a real wake model it may
        # not on a synthetic tone, so drive a deterministic path too.
        if not transcripts:
            pipeline.simulate_utterance(config.mock_transcript)
        assert transcripts, "no transcript produced"
        print(f"[ok] pipeline produced transcript: {transcripts[-1].text!r}")
    except Exception as exc:
        ok = False
        print(f"[FAIL] pipeline: {exc}")

    # 4) TTS synthesize → valid WAV.
    try:
        wav = pipeline.synthesize("Jarvis online.")
        pcm, sr, ch = audio.wav_to_pcm16(wav)
        assert len(pcm) > 0 and sr > 0 and ch >= 1
        print(f"[ok] tts synthesize → {len(wav)} byte WAV ({sr} Hz, {ch}ch)")
    except Exception as exc:
        ok = False
        print(f"[FAIL] tts: {exc}")

    # 5) Bridge envelope mapping (hello advertises mic+speaker+ambient_audio).
    try:
        hello = protocol.client_hello(mic=True, speaker=True, ambient_audio=True)
        caps = hello.payload["capabilities"]
        assert caps["mic"] is True and caps["speaker"] is True
        assert caps["ambient_audio"] is True
        print("[ok] bridge hello advertises mic+speaker+ambient_audio")
    except Exception as exc:
        ok = False
        print(f"[FAIL] bridge: {exc}")

    # 6) Sound-event detection (heuristic fallback).
    try:
        from .sound_events import create_sound_event_detector

        det = create_sound_event_detector(config)
        win = audio.tone(300.0, config.sound_event_window_ms, sample_rate=config.sample_rate, amplitude=0.6)
        sil = audio.silence(config.sound_event_window_ms, config.sample_rate)
        events = det.analyze(win)
        assert events, "no event on loud audio"
        assert det.analyze(sil) == [], "event on silence"
        e = events[0]
        print(f"[ok] sound events: {det.name} → {e.label!r} (conf={e.confidence:.2f}, {e.loudness_db:.1f} dBFS)")
    except Exception as exc:
        ok = False
        print(f"[FAIL] sound events: {exc}")

    # 7) Continuous ambient listening → audio scene.
    try:
        from .ambient import build_ambient

        amb = build_ambient(config)
        spcm = audio.tone(300.0, config.ambient_window_ms, sample_rate=config.sample_rate, amplitude=0.6)
        scene = amb.analyze_window(spcm)
        assert scene.window_ms == config.ambient_window_ms
        assert scene.loudness_db < 0
        assert scene.sounds or scene.ambient_transcript
        print(
            f"[ok] ambient scene: speaker={scene.speaker} sounds={len(scene.sounds)} "
            f"transcript={scene.ambient_transcript!r}"
        )
    except Exception as exc:
        ok = False
        print(f"[FAIL] ambient: {exc}")

    # 8) Barge-in interrupts TTS when the user speaks over it.
    try:
        bp = build_pipeline(config)
        fired: List[bool] = []
        bp.cb = PipelineCallbacks(on_barge_in=lambda: fired.append(True))
        bp._speaking = True  # simulate TTS playing
        loud_frame = audio.tone(300.0, config.frame_ms, sample_rate=config.sample_rate, amplitude=0.6)
        for _ in range(config.barge_in_min_frames + 2):
            bp.process_frame(loud_frame)
        assert fired, "barge-in did not fire"
        assert not bp.is_speaking()
        print("[ok] barge-in interrupts TTS on user speech")
    except Exception as exc:
        ok = False
        print(f"[FAIL] barge-in: {exc}")

    # 9) v1.1 perception envelope build/parse.
    try:
        sc_env = protocol.audio_scene(
            "overheard chatter", "other", [{"label": "music", "confidence": 0.6}], -30.0, 4000
        )
        ev_env = protocol.audio_event("doorbell", 0.82, -22.0)
        req = protocol.Envelope.from_json(
            protocol.Envelope.build(
                protocol.PERCEPTION_REQUEST, {"stream": "ambient_audio", "action": "start"}
            ).to_json()
        )
        assert protocol.PROTOCOL_VERSION == "1.1.0"
        assert protocol.Envelope.from_json(sc_env.to_json()).type == protocol.PERCEPTION_AUDIO_SCENE
        assert protocol.Envelope.from_json(ev_env.to_json()).payload["label"] == "doorbell"
        assert req.payload["stream"] == "ambient_audio"
        print("[ok] protocol v1.1 perception build/parse (audio_scene/event/request)")
    except Exception as exc:
        ok = False
        print(f"[FAIL] perception protocol: {exc}")

    print("-" * 60)
    print("RESULT:", "PASS ✅" if ok else "FAIL ❌")
    print("audio backend available:", audio.audio_io_available())
    return 0 if ok else 1


# --------------------------------------------------------------------------- #
# arg parsing
# --------------------------------------------------------------------------- #
def _add_common_overrides(parser: argparse.ArgumentParser, *, suppress: bool) -> None:
    """Engine/backend overrides. Added to the root parser (with real defaults)
    and to each subparser (with SUPPRESS) so they work either side of the
    subcommand, e.g. both ``jarvis-voice --tts mock say hi`` and
    ``jarvis-voice say hi --tts mock``.
    """
    default = argparse.SUPPRESS if suppress else None
    parser.add_argument(
        "--wake", default=default, help="override JARVIS_WAKE (auto|openwakeword|porcupine|energy)"
    )
    parser.add_argument(
        "--stt", default=default, help="override JARVIS_STT (auto|faster-whisper|vosk|mock)"
    )
    parser.add_argument(
        "--tts", default=default, help="override JARVIS_TTS (auto|piper|pyttsx3|mock)"
    )
    parser.add_argument("--backend", default=default, help="override JARVIS_BACKEND_URL")
    parser.add_argument(
        "--ambient", default=default, help="override JARVIS_AMBIENT (auto|on|off)"
    )
    parser.add_argument(
        "--sound-events", default=default, help="override JARVIS_SOUND_EVENTS (auto|yamnet|heuristic|off)"
    )
    parser.add_argument(
        "--language", default=default, help="set STT+TTS language (multi-language hook)"
    )
    parser.add_argument(
        "--log-level", default=default, help="override JARVIS_LOG_LEVEL (DEBUG/INFO/…)"
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="jarvis-voice",
        description="JarvisVR voice service — wake word + STT + TTS.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    _add_common_overrides(p, suppress=False)

    sub = p.add_subparsers(dest="command", required=True)

    sp_demo = sub.add_parser("demo", help="local mic → wake → STT loop (mock-friendly)")
    sp_demo.add_argument("--simulate", action="store_true", help="force the typed REPL (no mic)")
    _add_common_overrides(sp_demo, suppress=True)
    sp_demo.set_defaults(func=cmd_demo)

    sp_ambient = sub.add_parser(
        "ambient", help="continuous ambient listening + sound events (mock-friendly)"
    )
    sp_ambient.add_argument(
        "--simulate", action="store_true", help="force synthetic audio + REPL (no mic)"
    )
    _add_common_overrides(sp_ambient, suppress=True)
    sp_ambient.set_defaults(func=cmd_ambient)

    sp_bridge = sub.add_parser("bridge", help="connect to the agent-backend WebSocket")
    sp_bridge.add_argument("--no-mic", action="store_true", help="speak-only (don't capture mic)")
    sp_bridge.add_argument(
        "--max-retries", type=int, default=0, help="0 = retry forever (default)"
    )
    _add_common_overrides(sp_bridge, suppress=True)
    sp_bridge.set_defaults(func=cmd_bridge)

    sp_say = sub.add_parser("say", help="speak TEXT via TTS")
    sp_say.add_argument("text", help="text to speak")
    sp_say.add_argument("--out", help="also write synthesized WAV to this path")
    sp_say.add_argument("--no-play", action="store_true", help="with --out, don't also play")
    _add_common_overrides(sp_say, suppress=True)
    sp_say.set_defaults(func=cmd_say)

    sp_self = sub.add_parser("selftest", help="headless end-to-end check (mocks)")
    _add_common_overrides(sp_self, suppress=True)
    sp_self.set_defaults(func=cmd_selftest)

    sp_dev = sub.add_parser("devices", help="list audio devices")
    sp_dev.set_defaults(func=cmd_devices)

    return p


def _apply_overrides(config: Config, args: argparse.Namespace) -> Config:
    if args.wake:
        config.wake_engine = args.wake.lower()
    if args.stt:
        config.stt_engine = args.stt.lower()
    if args.tts:
        config.tts_engine = args.tts.lower()
    if args.backend:
        config.backend_url = args.backend
    if getattr(args, "ambient", None):
        config.ambient_mode = args.ambient.lower()
    if getattr(args, "sound_events", None):
        config.sound_events_engine = args.sound_events.lower()
    if getattr(args, "language", None):
        config.stt_language = args.language
        config.tts_language = args.language
    if args.log_level:
        config.log_level = args.log_level.upper()
    return config


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    config = Config.from_env()
    config = _apply_overrides(config, args)
    _setup_logging(config.log_level)

    try:
        return int(args.func(config, args) or 0)
    except KeyboardInterrupt:  # pragma: no cover - interactive
        print("\nbye.")
        return 130


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
