from dataclasses import dataclass
import ctypes.util
import time

from .resources import resources


@dataclass
class Transcript:
    text: str
    lang: str
    seconds: float
    uncertain: bool


class Whisper:
    def __init__(self, cfg, emit):
        self.cfg, self.emit = cfg, emit
        self.engine = None
        self.profile = None

    def candidates(self):
        info = resources()
        size = self.cfg.stt
        if size == "auto":
            size = "small" if info["available"] >= 1.7 else "base"
        if size not in ("small", "base"):
            raise ValueError("Modèle STT inconnu")
        # CTranslate2 nécessite aussi les bibliothèques utilisateur de CUDA.
        if (
            info["vram_free"] >= 3000
            and ctypes.util.find_library("cublas")
            and ctypes.util.find_library("cudnn")
        ):
            yield size, "cuda", "int8_float16"
        yield size, "cpu", "int8"
        if size != "base":
            yield "base", "cpu", "int8"

    def transcribe(self, audio):
        from faster_whisper import WhisperModel

        started = time.monotonic()
        profiles = list(self.candidates()) if not self.engine else [self.profile]
        if ("base", "cpu", "int8") not in profiles:
            profiles.append(("base", "cpu", "int8"))
        for size, device, precision in profiles:
            profile = size, device, precision
            try:
                if self.engine is None or self.profile != profile:
                    path = self.cfg.models / size
                    if not path.is_dir():
                        raise FileNotFoundError(str(path))
                    self.emit("model", f"Chargement Whisper {size} · {device}")
                    self.engine = WhisperModel(
                        str(path),
                        device=device,
                        compute_type=precision,
                        cpu_threads=4,
                        local_files_only=True,
                    )
                    self.profile = profile
                    self.emit("model", f"Whisper {size} · {device} · prêt")
                segments, info = self.engine.transcribe(
                    audio,
                    beam_size=2,
                    temperature=0,
                    condition_on_previous_text=False,
                    vad_filter=False,
                )
                segments = list(segments)
                text = " ".join(s.text.strip() for s in segments).strip()
                weak = (
                    not text
                    or info.language_probability < 0.45
                    or info.language not in ("fr", "en", "ar")
                    or any(
                        s.avg_logprob < -1.05
                        or s.no_speech_prob > 0.65
                        or s.compression_ratio > 2.5
                        for s in segments
                    )
                )
                return Transcript(text, info.language, time.monotonic() - started, weak)
            except (OSError, RuntimeError, MemoryError, ValueError):
                self.engine = self.profile = None
        raise RuntimeError("Whisper indisponible. Installez les poids base ou small.")
