"""Worker vocal GUI : audio Raspberry Pi -> PC -> assistant -> Piper -> Raspberry Pi.

Ce worker garde le pipeline audio distribué du dépôt principal et expose des
événements compatibles avec l'interface PySide6 importée depuis AssistantISIMM.
"""
from __future__ import annotations

import logging
import queue
import sys
import threading
import time
from pathlib import Path


def _bootstrap_ai():
    root = Path(__file__).resolve().parents[2]
    ai_root = root / "ai"
    if str(ai_root) not in sys.path:
        sys.path.insert(0, str(ai_root))
    return ai_root


def voice_worker(cfg, commands, events, stop, approvals, talk_gate):
    """Cible multiprocessing appelée par desktop_app.isimm.gui."""
    ai_root = _bootstrap_ai()

    def emit(name, value):
        events.put((name, value))

    server = robot = None
    try:
        from main import build_assistant, connect_robot
        from logsetup import setup_logging
        from settings import load_settings
        from audio.server import AudioServer
        from audio.vad import UtteranceSegmenter
        from speech.stt import WhisperSTT
        from speech.tts import PiperTTS
        import webrtcvad

        settings = load_settings()
        # L'application fusionnée utilise explicitement le modèle retenu.
        if settings.ollama_model != "qwen2.5:3b":
            from dataclasses import replace
            settings = replace(settings, ollama_model="qwen2.5:3b")
        setup_logging(settings.log_level, settings.log_dir)
        emit("model", "Initialisation des moteurs sur le PC…")

        robot = connect_robot(settings)
        assistant, llm, _ = build_assistant(settings, robot)
        llm.check()

        stt = WhisperSTT(settings)
        stt.load()
        tts = PiperTTS(settings)
        tts.load()

        vad = webrtcvad.Vad(settings.vad_mode)
        segmenter = UtteranceSegmenter(
            is_speech=lambda frame: vad.is_speech(frame, settings.audio_sample_rate),
            sample_rate=settings.audio_sample_rate,
            frame_ms=settings.vad_frame_ms,
            start_window_ms=settings.vad_start_window_ms,
            start_ratio=settings.vad_start_ratio,
            end_silence_ms=settings.vad_end_silence_ms,
            end_ratio=settings.vad_end_ratio,
            max_utterance_s=settings.vad_max_utterance_s,
            min_utterance_ms=settings.vad_min_utterance_ms,
        )
        server = AudioServer(settings)
        server.start()
        emit("model", f"Ollama {settings.ollama_model} · Faster-Whisper · Piper prêts")
        emit("notice", f"En attente du Raspberry Pi sur le port audio {settings.audio_port}.")

        active = False
        history_count = 0
        while not stop.is_set():
            try:
                command = commands.get(timeout=0.02)
                if command == "quit":
                    break
                if command == "prepare":
                    continue
                if command == "start":
                    if not server.connected:
                        emit("notice", "Raspberry Pi non connecté. Vérifiez AUDIO_PC_HOST et le réseau.")
                        emit("done", True)
                        continue
                    server.clear_mic()
                    segmenter.reset()
                    active = True
                    emit("state", "GREETING")
                    welcome = "Bienvenue à l’ISIMM ! Quelle est votre question ?"
                    server.play(tts.synthesize(welcome))
                    emit("answer", welcome)
                    emit("state", "LISTENING")
                    emit("mic", True)
            except queue.Empty:
                pass

            if not active:
                # Vide les anciennes trames pendant l'attente pour éviter une question obsolète.
                server.read_mic(timeout=0.01)
                continue

            if not server.connected:
                active = False
                emit("mic", False)
                emit("notice", "Connexion audio Raspberry Pi perdue.")
                emit("done", True)
                continue

            frame = server.read_mic(timeout=0.05)
            if frame is None:
                continue
            utterance = segmenter.feed(frame)
            if utterance is None:
                continue

            endpoint = time.monotonic()
            emit("state", "TRANSCRIBING")
            emit("mic", False)
            started = time.monotonic()
            try:
                text = stt.transcribe(utterance)
            except Exception as exc:
                logging.exception("STT failure")
                emit("notice", f"Transcription indisponible : {type(exc).__name__}")
                emit("state", "LISTENING")
                emit("mic", True)
                continue
            stt_elapsed = time.monotonic() - started
            if not text.strip():
                emit("notice", "Je n'ai pas compris. Pouvez-vous répéter ?")
                server.play(tts.synthesize("Pouvez-vous répéter votre question ?"))
                emit("state", "LISTENING")
                emit("mic", True)
                continue

            emit("transcript", {
                "text": text,
                "lang": "fr",
                "seconds": stt_elapsed,
                "uncertain": False,
            })
            emit("state", "THINKING")
            llm_started = time.monotonic()
            try:
                answer = assistant.handle(text)
            except Exception as exc:
                logging.exception("Assistant failure")
                answer = "Je rencontre un problème technique. Veuillez réessayer."
                emit("notice", f"Assistant : {type(exc).__name__}")
            llm_elapsed = time.monotonic() - llm_started
            emit("answer", answer)
            emit("state", "SPEAKING")
            sound_started = time.monotonic()
            try:
                server.play(tts.synthesize(answer))
            except Exception as exc:
                logging.exception("TTS/audio transport failure")
                emit("notice", f"Lecture audio impossible : {type(exc).__name__}")
            total = time.monotonic() - endpoint
            emit("timing", {
                "endpoint_stt": stt_elapsed,
                "stt_token": llm_elapsed,
                "token_sound": max(0.0, time.monotonic() - sound_started),
                "perceived": total,
            })
            history_count += 1
            emit("state", "LISTENING")
            emit("mic", True)

    except Exception as exc:
        logging.exception("Distributed voice worker failed")
        emit("state", "ERROR")
        emit("notice", f"Initialisation audio/IA impossible : {type(exc).__name__}: {exc}"[:240])
        emit("done", True)
    finally:
        if server is not None:
            try:
                server.stop()
            except Exception:
                logging.exception("Audio server shutdown failed")
        if robot is not None:
            try:
                robot.close()
            except Exception:
                logging.exception("ROS bridge shutdown failed")
        emit("mic", False)
