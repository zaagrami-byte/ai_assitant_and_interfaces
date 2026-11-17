from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Settings:
    camera: str = ""
    mic: str = ""
    denoise: bool = True
    push_to_talk: bool = False
    review_text: bool = False
    dialogue_debug: bool = False
    stt: str = "auto"
    llm: str = "auto"
    voice: str = "ff_siwis"
    speed: float = 1.0
    volume: float = 0.8
    min_face: float = 0.075
    yaw: float = 0.16
    iris: float = 0.20
    pitch: float = 0.50
    vad: float = 0.62
    cooldown: float = 12
    azure: bool = False
    azure_voice: str = "ar-TN-ReemNeural"
    feedback_days: int = 7
    models: Path = ROOT / "models"

    @classmethod
    def load(cls):
        load_dotenv(ROOT / ".env")
        cfg = cls()
        for key, default in vars(cfg).copy().items():
            value = os.getenv("ISIMM_" + key.upper())
            if value is not None:
                if isinstance(default, bool):
                    value = value.lower() in ("1", "true", "yes", "oui")
                else:
                    value = type(default)(value)
                setattr(cfg, key, value)
        return cfg
