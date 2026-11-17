import os
import re
import urllib.request
from xml.sax.saxutils import escape
import numpy as np


def spoken(text):
    text = re.sub(r"```[\s\S]*?(?:```|$)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"https?://\S+|[*_`#>|]", " ", text)
    return " ".join(text.split())


class Speech:
    def __init__(self, cfg, emit, consent=lambda text: False):
        self.cfg, self.emit, self.consent = cfg, emit, consent
        self.welcome = None
        self.kokoro = self.piper = self.piper_lang = None

    def render(self, text, lang):
        if lang == "ar" and self.cfg.azure and self.consent(text):
            try:
                yield self.azure(text)
                return
            except (OSError, ValueError, KeyError):
                self.emit("notice", "Voix Azure indisponible. Repli local.")
        if lang in ("fr", "en") and not (lang == "fr" and self.cfg.voice == "piper"):
            try:
                if self.kokoro is None:
                    import onnxruntime as ort
                    from kokoro_onnx import Kokoro

                    self.emit("model", "Chargement de Kokoro INT8")
                    opts = ort.SessionOptions()
                    opts.intra_op_num_threads = 3
                    session = ort.InferenceSession(
                        str(self.cfg.models / "kokoro-v1.0.int8.onnx"),
                        opts,
                        providers=["CPUExecutionProvider"],
                    )
                    self.kokoro = Kokoro.from_session(
                        session, str(self.cfg.models / "voices-v1.0.bin")
                    )
                    self.emit("model", "Kokoro INT8 · prêt")
                voice = self.cfg.voice if lang == "fr" else "af_heart"
                yield self.kokoro.create(
                    text,
                    voice=voice,
                    speed=self.cfg.speed,
                    lang="fr-fr" if lang == "fr" else "en-us",
                )
                return
            except Exception:
                self.emit("notice", "Kokoro indisponible. Utilisation de Piper.")
        from piper import PiperVoice, SynthesisConfig

        stem = {"ar": "ar_JO-kareem", "fr": "fr_FR-siwis", "en": "en_US-lessac"}.get(
            lang, "fr_FR-siwis"
        )
        if self.piper_lang != stem:
            self.emit("model", "Piper · " + stem)
            self.piper = PiperVoice.load(str(self.cfg.models / (stem + "-medium.onnx")))
            self.piper_lang = stem
        for chunk in self.piper.synthesize(
            text, syn_config=SynthesisConfig(length_scale=1 / self.cfg.speed)
        ):
            yield chunk.audio_float_array, chunk.sample_rate

    def prepare(self, greeting):
        self.welcome = (greeting, list(self.render(greeting, "fr")))

    def azure(self, text):
        region = os.environ["AZURE_SPEECH_REGION"]
        voice = self.cfg.azure_voice
        if not re.fullmatch("[a-z0-9-]+", region) or voice not in (
            "ar-TN-HediNeural",
            "ar-TN-ReemNeural",
        ):
            raise ValueError("Paramètres Azure invalides")
        xml = f'<speak version="1.0" xml:lang="ar-TN"><voice name="{voice}"><prosody rate="{self.cfg.speed}">{escape(text)}</prosody></voice></speak>'
        req = urllib.request.Request(
            f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1",
            xml.encode(),
            {
                "Content-Type": "application/ssml+xml",
                "Ocp-Apim-Subscription-Key": os.environ["AZURE_SPEECH_KEY"],
                "X-Microsoft-OutputFormat": "raw-24khz-16bit-mono-pcm",
            },
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            return np.frombuffer(resp.read(), "<i2").astype("float32") / 32768, 24000

    def say(self, text, lang, stop, first_sound=lambda: None):
        import sounddevice as sd

        clean = spoken(text)
        if not clean or stop.is_set():
            return
        source = (
            self.welcome[1]
            if self.welcome and clean == self.welcome[0]
            else self.render(clean, lang)
        )
        for samples, rate in source:
            if stop.is_set():
                return
            samples = np.clip(
                np.asarray(samples, dtype="float32") * self.cfg.volume, -1.0, 1.0
            )
            with sd.OutputStream(
                samplerate=rate, channels=1, dtype="float32"
            ) as stream:
                for offset in range(0, len(samples), max(1, rate // 25)):
                    if stop.is_set():
                        stream.abort()
                        return
                    stream.write(samples[offset : offset + rate // 25])
                    if offset == 0:
                        first_sound()
