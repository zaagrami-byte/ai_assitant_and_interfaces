from collections import deque
import queue
import time
from typing import Protocol

import numpy as np
import onnxruntime as ort
from scipy.signal import firwin, lfilter

from .denoise import DeepFilter


class EchoControl(Protocol):
    """Point d'intégration AEC. La première version utilise le semi-duplex."""

    def process(self, microphone: np.ndarray, playback: np.ndarray) -> np.ndarray: ...


class Silero:
    def __init__(self, path):
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = opts.inter_op_num_threads = 1
        self.session = ort.InferenceSession(
            str(path), opts, providers=["CPUExecutionProvider"]
        )
        self.reset()

    def reset(self):
        self.state = np.zeros((2, 1, 128), np.float32)
        self.context = np.zeros(64, np.float32)

    def __call__(self, frame):
        data = np.concatenate((self.context, frame))
        prob, self.state = self.session.run(
            None,
            {
                "input": data[None, :],
                "state": self.state,
                "sr": np.array(16000, np.int64),
            },
        )
        self.context = frame[-64:].copy()
        return float(prob.item())


class Frontend:
    """Blocs de 32 ms, une seule décimation de 48 vers 16 kHz, FIR à état."""

    def __init__(self, enhancement=None):
        self.enhancement = enhancement
        self.taps = firwin(97, 7450, fs=48000).astype("float32")
        self.delay = np.zeros(96, np.float32)

    def process(self, frame):
        if self.enhancement:
            frame = self.enhancement.process(frame)
        out, self.delay = lfilter(self.taps, [np.float32(1)], frame, zi=self.delay)
        return np.ascontiguousarray(out[::3], dtype="float32")


class Turn:
    def __init__(self, threshold):
        self.threshold = threshold
        self.pre = deque(maxlen=10)
        self.frames = []
        self.streak = self.quiet = self.voiced = 0

    def push(self, frame, probability):
        active = probability >= self.threshold
        if not self.frames:
            self.pre.append(frame)
            self.streak = self.streak + 1 if active else 0
            if self.streak >= 3:
                self.frames.extend(self.pre)
                self.voiced = self.streak
        else:
            self.frames.append(frame)
            self.voiced += int(active)
            self.quiet = 0 if probability >= self.threshold * 0.7 else self.quiet + 1
        return self.quiet >= 28 or len(self.frames) >= 625

    def samples(self):
        if self.voiced < 6:
            return None
        end = len(self.frames) - max(0, self.quiet - 5)
        return np.concatenate(self.frames[:end])


class Microphone:
    def __init__(self, config, emit, talk_gate=None):
        self.cfg, self.emit = config, emit
        self.talk_gate = talk_gate
        self.vad = None
        self.enhancer = None
        self.last_speech = None

    def listen(self, stop):
        import sounddevice as sd

        if self.vad is None:
            self.emit("model", "Chargement de Silero VAD")
            self.vad = Silero(self.cfg.models / "silero.onnx")
        self.vad.reset()
        self.emit("model", "Silero VAD · prêt")
        if self.cfg.denoise and self.enhancer is None:
            try:
                self.enhancer = DeepFilter(self.cfg.models / "deepfilter.so")
            except (OSError, ValueError, RuntimeError):
                self.emit("notice", "DeepFilterNet indisponible. Capture directe.")
        frontend = Frontend(self.enhancer)
        turn = Turn(self.cfg.vad)
        chunks = queue.Queue(maxsize=12)
        lost = []

        def callback(data, frames, timing, status):
            if status or chunks.full():
                if not lost:
                    lost.append(True)
                return
            chunks.put_nowait(data[:, 0].copy())

        device = self.cfg.mic or None
        if device and device.isdigit():
            device = int(device)
        try:
            if self.talk_gate is not None:
                self.talk_gate.clear()
                self.emit("hold", True)
                deadline = time.monotonic() + 16
                while not self.talk_gate.wait(0.05):
                    if stop.is_set() or time.monotonic() >= deadline:
                        return None
            with sd.InputStream(
                samplerate=48000,
                channels=1,
                dtype="float32",
                device=device,
                blocksize=1536,
                callback=callback,
            ):
                self.emit("mic", True)
                self.emit(
                    "filter",
                    "DeepFilterNet · 48 kHz" if self.enhancer else "Capture directe",
                )
                started = last = time.monotonic()
                while not stop.is_set():
                    now = time.monotonic()
                    if self.talk_gate is not None and not self.talk_gate.is_set():
                        return turn.samples()
                    if lost or now - last > 2:
                        raise RuntimeError(
                            "Microphone interrompu. Vérifiez la source audio."
                        )
                    if now - started > 30 or (not turn.frames and now - started > 9):
                        return None
                    try:
                        raw = chunks.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    last = time.monotonic()
                    frame = frontend.process(raw)
                    p = self.vad(frame)
                    if p >= self.cfg.vad * 0.7:
                        self.last_speech = last
                    self.emit(
                        "level", (float(np.sqrt(np.mean(raw**2))), p >= self.cfg.vad)
                    )
                    if turn.push(frame, p):
                        return turn.samples()
        except sd.PortAudioError as exc:
            raise RuntimeError(
                "Microphone inaccessible. Sélectionnez une entrée 48 kHz."
            ) from exc
        finally:
            if self.talk_gate is not None:
                self.emit("hold", False)
            self.emit("mic", False)
            self.emit("level", (0.0, False))
            if self.enhancer:
                # Purger les trames résiduelles entre étudiants. Le plugin conserve son worker.
                silence = np.zeros(1536, np.float32)
                for _ in range(12):
                    self.enhancer.process(silence)
        return None

    def close(self):
        if self.enhancer:
            self.enhancer.close()
            self.enhancer = None
