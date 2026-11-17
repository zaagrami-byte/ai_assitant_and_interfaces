"""Mémoire du dialogue et choix du registre écrit. Le TTS garde ses langues natives."""

import json
import re
import sys
from uuid import uuid4

from .knowledge import normalize, TOPIC_CHANGE, REFERENCE


def recent_messages(history):
    """Trois échanges complets, avec une borne de taille pour le contexte Ollama."""
    messages = []
    for m in history[-6:]:
        if m["role"] == "user" and TOPIC_CHANGE.search(normalize(m["content"])):
            messages.clear()
        messages.append({"role": m["role"], "content": m["content"][:650]})
    return messages


def followup_context(history, question):
    """Pour une relance, conserver la chaîne jusqu’à la demande qui ouvre son sujet."""
    if REFERENCE.search(normalize(question)):
        for index in range(len(history) - 1, -1, -1):
            message = history[index]
            if message["role"] == "user" and not REFERENCE.search(
                normalize(message["content"])
            ):
                return history[index:]
    return history


DARJA = re.compile(
    r"\b(?:شنو[اةه]?|شنوة|شنية|شنيا|شكون|كيفاش|علاش|نحب|نج[يم]م?|تنجم|نجم|نلقى|وين|برشا|فماش|فما|متاع\w*|بالتونسي|توانسة|chnowa|chnoua|chneya|kifech|kifesh|najjem|najem|nheb|n7eb|win nal9a|bel tounsi|b[ei]tounsi|derja|darija|tounsi)\b"
)


def reply_locale(question, detected, history):
    text = normalize(question)
    if "الفصحى" in text or "بالفصحى" in text:
        return "ar"
    if DARJA.search(text):
        return "ar-TN"
    arabic_letters = len(re.findall(r"[ء-ي]", text))
    if (
        detected in ("ar", "ar-TN")
        or arabic_letters > sum(c.isalpha() for c in text) / 2
    ):
        if detected == "ar-TN":
            return detected
        if "الفصحى" not in text and "فصحى" not in text:
            for msg in reversed(history):
                if msg["role"] == "user":
                    if DARJA.search(normalize(msg["content"])):
                        return "ar-TN"
                    if (
                        not re.search(r"[ء-ي]", msg["content"])
                        or "فصحى" in msg["content"]
                    ):
                        break
        return "ar"
    return "en" if detected == "en" else "fr"


def comparison_reference(messages):
    """Résoudre « le second » quand l'étudiant vient de nommer les deux termes."""
    users = [m["content"] for m in messages if m["role"] == "user"]
    if len(users) < 2:
        return None
    current = normalize(users[-1])
    if not re.search(
        r"\b(?:la seconde|le second|la deuxieme|le deuxieme|the second|the latter|الثانية|الثاني)\b",
        current,
    ):
        return None
    match = re.search(
        r"\b(?:entre|between|بين)\s+.{1,60}?\s+(?:et |and |و\s*)(.{1,60})",
        users[-2],
        re.I,
    )
    if not match:
        return None
    term = re.split(
        r"[?.!؟,،]|\s+(?:en informatique|في|in computing)\s*", match[1], maxsplit=1
    )[0].strip()
    return term if 0 < len(term.split()) <= 6 else None


class DialogueTrace:
    def __init__(self, enabled=False):
        self.enabled = enabled
        self.turn = None

    def begin(self):
        if self.enabled:
            self.turn = uuid4().hex[:12]

    def log(self, stage, **data):
        if self.enabled:
            print(
                json.dumps(
                    {"dialogue": stage, "turn": self.turn, **data}, ensure_ascii=False
                ),
                file=sys.stderr,
                flush=True,
            )
