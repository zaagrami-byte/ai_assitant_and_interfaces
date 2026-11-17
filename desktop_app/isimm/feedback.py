import os
from pathlib import Path
import sqlite3
import time
from .config import ROOT


class Feedback:
    def __init__(self, days, directory=ROOT / "local"):
        self.days = max(0, days)
        directory = Path(directory)
        directory.mkdir(mode=0o700, exist_ok=True)
        path = directory / "suggestions.sqlite"
        handle = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(handle)
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA secure_delete=ON")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS suggestion (created REAL, content TEXT)"
        )
        self.prune()

    def prune(self):
        with self.db:
            self.db.execute(
                "DELETE FROM suggestion WHERE created <= ?",
                (time.time() - self.days * 86400,),
            )

    def add(self, text, consent=False):
        self.prune()
        if not self.days or not consent or not text.strip():
            return False
        with self.db:
            self.db.execute(
                "INSERT INTO suggestion VALUES (?,?)",
                (time.time(), text.strip()[:1000]),
            )
        return True
