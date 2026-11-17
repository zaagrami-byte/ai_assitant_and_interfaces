import logging
import queue
import re
import time
from .audio import Microphone
from .stt import Whisper
from .llm import Ollama
from .tts import Speech, spoken
from .dialogue import DialogueTrace, recent_messages, reply_locale


from .state import State


WELCOME = "Bienvenue à l’ISIMM ! Quelle est votre question ?"
REPEAT = {
    "fr": "Pouvez-vous répéter votre question, un peu plus près du micro ?",
    "en": "Could you repeat your question a little closer to the microphone?",
    "ar": "هل يمكنك إعادة السؤال بالقرب من الميكروفون؟",
}
BYE = {
    "fr": "Au revoir et bonne journée !",
    "en": "Goodbye! Have a nice day.",
    "ar": "إلى اللقاء، ويوم سعيد.",
}


def finished(text):
    clean = re.sub(r"[^\w\s]", " ", text.casefold())
    return " ".join(clean.split()) in {
        "au revoir",
        "merci au revoir",
        "merci beaucoup",
        "merci",
        "thank you",
        "thanks",
        "شكرا",
        "يعيشك",
        "à bientôt",
        "goodbye",
        "bye",
        "bye bye",
        "مع السلامة",
        "إلى اللقاء",
        "يعيشك بالسلامة",
        "بالسلامة",
    }


class Session:
    """Un seul propriétaire des moteurs. Le micro est fermé avant chaque inférence."""

    def __init__(self, mic, stt, llm, tts, emit, review=None, trace=None):
        self.trace = trace or DialogueTrace()
        self.review = review
        self.mic, self.stt, self.llm, self.tts, self.emit = mic, stt, llm, tts, emit

    def state(self, value):
        self.emit("state", value.value)

    def run(self, stop):
        history = []
        try:
            self.state(State.GREETING)
            self.tts.say(WELCOME, "fr", stop)
            retries = 0
            while not stop.is_set():
                if stop.wait(0.18):
                    break
                self.state(State.LISTENING)
                audio = self.mic.listen(stop)
                if audio is None or stop.is_set():
                    break
                endpoint = self.mic.last_speech or time.monotonic()
                self.state(State.TRANSCRIBING)
                item = self.stt.transcribe(audio)
                del audio
                if stop.is_set():
                    break
                decoded = time.monotonic()
                self.trace.begin()
                self.trace.log("stt", **vars(item))
                self.emit("transcript", vars(item).copy())
                lang = item.lang if item.lang in REPEAT else "fr"
                if self.review and item.text:
                    reviewed = self.review(item.text)
                    item.uncertain = not bool(reviewed)
                    if reviewed:
                        item.text = reviewed
                        self.trace.log("reviewed_transcript", text=reviewed)
                        self.emit("transcript", vars(item).copy())
                locale = reply_locale(item.text, lang, history)
                voice_lang = locale.split("-")[0]
                if item.uncertain:
                    retries += 1
                    if retries > 2:
                        break
                    self.state(State.SPEAKING)
                    self.trace.log(
                        "tts_final", text=spoken(REPEAT[lang]), language=lang
                    )
                    self.tts.say(REPEAT[lang], lang, stop)
                    continue
                if finished(item.text):
                    self.state(State.SPEAKING)
                    self.trace.log("tts_final", text=spoken(BYE[lang]), language=lang)
                    self.tts.say(BYE[lang], lang, stop)
                    break
                retries = 0
                self.state(State.THINKING)
                pending = answer = ""
                first = sound = None

                def played():
                    nonlocal sound
                    if sound is None:
                        sound = time.monotonic()

                for token in self.llm.stream(item.text, lang, history, stop):
                    if stop.is_set():
                        return
                    if first is None:
                        first = time.monotonic()
                    pending += token
                    answer += token
                    self.emit("answer", answer)
                    # N'envoyer au TTS que les phrases terminées hors bloc de code.
                    match = re.search(r"[.!?؟。](?=\s)", pending)
                    if match and pending[: match.end()].count("```") % 2 == 0:
                        self.state(State.SPEAKING)
                        chunk = pending[: match.end()]
                        self.trace.log(
                            "tts_final", text=spoken(chunk), language=voice_lang
                        )
                        self.tts.say(chunk, voice_lang, stop, played)
                        pending = pending[match.end() :]
                if pending.strip() and not stop.is_set():
                    self.state(State.SPEAKING)
                    self.trace.log(
                        "tts_final", text=spoken(pending), language=voice_lang
                    )
                    self.tts.say(pending, voice_lang, stop, played)
                if sound and first:
                    raw_token = getattr(self.llm, "first_token_at", None)
                    token_at = raw_token if isinstance(raw_token, float) else first
                    self.emit(
                        "timing",
                        dict(
                            endpoint_stt=decoded - endpoint,
                            stt_token=token_at - decoded,
                            grounding=first - token_at,
                            token_sound=sound - first,
                            perceived=sound - endpoint,
                        ),
                    )
                history.extend(
                    [
                        {"role": "user", "content": item.text},
                        {"role": "assistant", "content": answer},
                    ]
                )
                history = recent_messages(history)
        except Exception:
            self.state(State.ERROR)
            raise
        finally:
            self.state(State.END_CONVERSATION)


def voice_worker(cfg, commands, events, stop, approvals, talk_gate):
    def emit(name, value):
        events.put((name, value))

    def ask(kind, text):
        request_id = time.monotonic_ns()
        emit(kind, (request_id, text))
        deadline = time.monotonic() + 25
        while not stop.is_set() and time.monotonic() < deadline:
            try:
                approved_id, answer = approvals.get(timeout=0.1)
                if approved_id == request_id:
                    return answer
            except queue.Empty:
                continue
        return False

    trace = DialogueTrace(cfg.dialogue_debug)
    session = Session(
        Microphone(cfg, emit, talk_gate if cfg.push_to_talk else None),
        Whisper(cfg, emit),
        Ollama(cfg, emit, trace=trace),
        Speech(cfg, emit, lambda text: ask("consent", text)),
        emit,
        trace=trace,
        review=(lambda text: ask("review", text)) if cfg.review_text else None,
    )
    while True:
        command = commands.get()
        if command == "quit":
            break
        if command == "prepare":
            try:
                from .resources import resources

                if resources()["available"] > 2.1:
                    session.tts.prepare(WELCOME)
                    emit("model", "Voix française prête")
            except Exception:
                emit("notice", "Préchargement différé au prochain échange.")
            continue
        try:
            session.run(stop)
        except Exception as exc:
            logging.warning("Échec du moteur %s", type(exc).__name__)
            emit(
                "notice",
                str(exc)[:240]
                if isinstance(exc, RuntimeError)
                else "Moteur indisponible · " + type(exc).__name__,
            )
        finally:
            emit("done", True)
    session.mic.close()
