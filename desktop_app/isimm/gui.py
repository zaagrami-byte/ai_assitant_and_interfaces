import json
import sys
import multiprocessing as mp
import queue
import threading
import time

from PySide6.QtCore import Qt, QTimer, QProcess
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .feedback import Feedback
from .resources import resources
from .state import Machine


STATES = {
    "IDLE": "En veille",
    "GAZE_DETECTION": "En attente du regard",
    "MANUAL_ACTIVATION": "Activation manuelle",
    "GREETING": "Bienvenue",
    "LISTENING": "À votre écoute",
    "TRANSCRIBING": "Transcription en cours",
    "THINKING": "Recherche de la réponse",
    "SPEAKING": "Réponse vocale",
    "END_CONVERSATION": "Échange terminé",
    "COOLDOWN": "Pause entre deux échanges",
    "ERROR": "Intervention requise",
}


def label(text="", kind=""):
    widget = QLabel(text)
    widget.setProperty("kind", kind)
    widget.setWordWrap(kind != "brand")
    widget.setTextFormat(Qt.PlainText)
    return widget


def button(text, slot, primary=False):
    w = QPushButton(text)
    w.setProperty("primary", primary)
    w.clicked.connect(slot)
    return w


def bar():
    result = QProgressBar()
    result.setRange(0, 100)
    result.setTextVisible(False)
    result.setFixedHeight(6)
    return result


def card():
    w = QFrame()
    w.setObjectName("card")
    layout = QVBoxLayout(w)
    layout.setContentsMargins(20, 18, 20, 18)
    layout.setSpacing(10)
    return w, layout


def voice_process(*args):
    from .distributed_worker import voice_worker

    voice_worker(*args)


class Window(QMainWindow):
    def __init__(self, cfg, demo=False):
        super().__init__()
        self.cfg = cfg
        self.machine = Machine()
        if demo:
            self.cfg.camera = ""
        self.ctx = mp.get_context("spawn")
        self.camera = self.voice = None
        self.active = self.busy = False
        self.ready_at = 0.0
        self.feedback = Feedback(cfg.feedback_days)
        self.metrics = queue.Queue(1)
        self.metric_thread = None
        self.peak_ram = self.peak_vram = 0
        self.last_metrics = 0.0
        self.free_ram = 0.0
        self.deadline = 0.0
        self.setWindowTitle("ISIMM · Accueil étudiant")
        self.resize(1040, 720)
        base = QWidget()
        self.setCentralWidget(base)
        layout = QVBoxLayout(base)
        layout.setContentsMargins(28, 22, 28, 20)
        layout.setSpacing(14)
        top = QHBoxLayout()
        top.addWidget(label("ISIMM   /   Accueil étudiant", "brand"))
        top.addStretch()
        self.settings_btn = button("Paramètres", self.settings)
        top.addWidget(self.settings_btn)
        layout.addLayout(top)
        layout.addWidget(label("Assistant vocal", "title"))
        self.state_label = label("En veille", "state")
        layout.addWidget(self.state_label)
        grid = QGridLayout()
        grid.setColumnStretch(0, 5)
        grid.setColumnStretch(1, 6)
        left, v = card()
        v.addWidget(label("Caméra et activation", "section"))
        self.video = label("Caméra en veille")
        self.video.setObjectName("video")
        from PySide6.QtWidgets import QSizePolicy

        self.video.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.video.setMinimumSize(210, 140)
        self.video.setAlignment(Qt.AlignCenter)
        v.addWidget(self.video, 1)
        self.gaze = label("Regard · 0 / 5 s")
        self.gaze_bar = bar()
        v.addWidget(self.gaze)
        v.addWidget(self.gaze_bar)
        self.mic_label = label("Micro fermé")
        self.mic_bar = bar()
        v.addWidget(self.mic_label)
        v.addWidget(self.mic_bar)
        self.filter = label("Réduction de bruit en veille", "muted")
        v.addWidget(self.filter)
        right, r = card()
        r.addWidget(label("Conversation", "section"))
        r.addWidget(label("Votre question", "muted"))
        self.question = QPlainTextEdit()
        self.question.setReadOnly(True)
        self.question.setPlaceholderText("La transcription apparaîtra ici.")
        r.addWidget(self.question, 1)
        self.language = label("Langue et transcription · —", "muted")
        r.addWidget(self.language)
        r.addWidget(label("Réponse de l’assistant", "muted"))
        self.answer = QPlainTextEdit()
        self.answer.setReadOnly(True)
        self.answer.setPlaceholderText("La réponse apparaîtra ici.")
        r.addWidget(self.answer, 2)
        self.sources = label("", "muted")
        r.addWidget(self.sources)
        grid.addWidget(left, 0, 0)
        grid.addWidget(right, 0, 1)
        layout.addLayout(grid, 1)
        self.notice = label(
            "Le regard active l’accueil après cinq secondes. Vous pouvez aussi utiliser Parler."
        )
        self.model = label("Moteurs en veille", "muted")
        self.timing = label("", "muted")
        self.hardware = label("", "muted")
        for w in (self.notice, self.model, self.timing, self.hardware):
            layout.addWidget(w)
        actions = QHBoxLayout()
        self.start_btn = button("Démarrer", self.start, True)
        self.talk = button("Parler", lambda: self.activate(True), True)
        self.hold = QPushButton("Maintenir pour parler")
        self.hold.setVisible(False)
        self.hold.pressed.connect(lambda: self.talk_gate.set())
        self.hold.released.connect(lambda: self.talk_gate.clear())
        self.end = button("Terminer", self.end_session)
        self.stop_btn = button("Arrêter", self.shutdown)
        self.suggest = button("Suggestion", self.suggestion)
        for w in (self.start_btn, self.talk, self.hold, self.end, self.stop_btn):
            actions.addWidget(w)
        actions.addStretch()
        actions.addWidget(self.suggest)
        layout.addLayout(actions)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(50)
        self.pruner = QTimer(self)
        self.pruner.timeout.connect(self.feedback.prune)
        self.pruner.start(60000)
        self.controls()

    def controls(self):
        self.start_btn.setEnabled(not self.active)
        self.settings_btn.setEnabled(not self.active)
        self.talk.setEnabled(
            self.active and not self.busy and time.monotonic() >= self.ready_at
        )
        self.end.setEnabled(self.busy)
        self.stop_btn.setEnabled(self.active)
        self.suggest.setEnabled(self.cfg.feedback_days > 0)

    def settings(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Paramètres de la session")
        form = QFormLayout(dlg)
        camera = QLineEdit(self.cfg.camera)
        camera.setPlaceholderText("Vide pour le mode sans caméra")
        mic = QComboBox()
        mic.setEditable(True)
        mic.addItem("", "")
        mic.setEditText(self.cfg.mic)
        discovery = QProcess(dlg)

        def show_inputs(code, status):
            if code != 0:
                return
            try:
                devices = json.loads(bytes(discovery.readAllStandardOutput()))
            except (ValueError, UnicodeDecodeError):
                return
            current = mic.currentText()
            for index, name in devices:
                mic.addItem(f"{index} · {name}", index)
            found = mic.findData(current)
            if found >= 0:
                mic.setCurrentIndex(found)
            else:
                mic.setEditText(current)

        discovery.finished.connect(show_inputs)
        discovery.start(sys.executable, ["-m", "isimm.devices"])
        QTimer.singleShot(3500, discovery.kill)

        def combo(values, current):
            w = QComboBox()
            w.addItems(values)
            w.setCurrentText(current)
            return w

        stt = combo(["small", "base"], self.cfg.stt if self.cfg.stt in ("small", "base") else "small")
        llm = combo(["qwen2.5:3b"], "qwen2.5:3b")
        voice = combo(["piper"], "piper")
        cloudvoice = combo(
            ["ar-TN-ReemNeural", "ar-TN-HediNeural"], self.cfg.azure_voice
        )

        def number(value, low, high):
            w = QDoubleSpinBox()
            w.setRange(low, high)
            w.setSingleStep(0.05)
            w.setValue(value)
            return w

        volume = number(self.cfg.volume, 0, 1)
        speed = number(self.cfg.speed, 0.6, 1.6)
        denoise = QCheckBox("DeepFilterNet")
        denoise.setChecked(self.cfg.denoise)
        hold = QCheckBox("Maintenir le bouton pendant la question")
        hold.setChecked(self.cfg.push_to_talk)
        review = QCheckBox("Confirmer ou corriger le texte avant la réponse")
        review.setChecked(self.cfg.review_text)
        azure = QCheckBox("Autoriser les demandes de lecture Azure")
        azure.setChecked(self.cfg.azure)
        for name, w in [
            ("Flux IP", camera),
            ("Microphone (vide = défaut)", mic),
            ("Réduction de bruit", denoise),
            ("Tour de parole", hold),
            ("Transcription", review),
            ("Reconnaissance", stt),
            ("Modèle Ollama", llm),
            ("Voix française", voice),
            ("Vitesse", speed),
            ("Volume", volume),
            ("Voix tunisienne en ligne", azure),
            ("Voix Azure", cloudvoice),
        ]:
            form.addRow(name, w)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)
        if dlg.exec():
            self.cfg.push_to_talk = hold.isChecked()
            self.cfg.review_text = review.isChecked()
            self.cfg.camera = camera.text().strip()
            self.cfg.mic = (
                mic.currentData()
                if mic.currentText() == mic.itemText(mic.currentIndex())
                else mic.currentText().strip()
            )
            self.cfg.stt, self.cfg.llm, self.cfg.voice = (
                stt.currentText(),
                llm.currentText(),
                voice.currentText(),
            )
            self.cfg.volume, self.cfg.speed = volume.value(), speed.value()
            self.cfg.denoise, self.cfg.azure, self.cfg.azure_voice = (
                denoise.isChecked(),
                azure.isChecked(),
                cloudvoice.currentText(),
            )

        if discovery.state() != QProcess.NotRunning:
            discovery.kill()
            discovery.waitForFinished(150)
        dlg.deleteLater()

    def start(self):
        if self.active:
            return
        msg = (
            "La caméra estime le regard. Le microphone écoute uniquement après l’invitation. "
            "Les images, les sons et le texte de l’échange restent temporaires. "
            "Évitez de communiquer des renseignements personnels. "
        )
        if self.cfg.dialogue_debug:
            msg += "Diagnostic actif : la console locale affiche vos paroles, les requêtes et les réponses. "
        msg += (
            "La voix Azure demandera votre accord avant chaque envoi de texte."
            if self.cfg.azure
            else "Le traitement vocal est local."
        )
        if (
            QMessageBox.question(
                self,
                "Conditions de la démonstration",
                msg + "\n\nDémarrer la session ?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            != QMessageBox.Yes
        ):
            return
        self.events = self.ctx.Queue()
        self.frames = self.ctx.Queue(1)
        self.armed, self.cam_stop = self.ctx.Event(), self.ctx.Event()
        self.armed.set()
        self.active = True
        self.ready_at = 0
        if self.cfg.camera:
            from .vision import camera_worker

            self.camera = self.ctx.Process(
                target=camera_worker,
                args=(self.cfg, self.frames, self.events, self.cam_stop, self.armed),
                daemon=True,
            )
            self.camera.start()
            self.video.setText("Connexion au smartphone…")
        else:
            self.video.setText("Mode sans caméra")
        if self.free_ram > 2.8:
            self.create_voice_worker()
            self.commands.put("prepare")
        self.notice.setText("Regardez la caméra ou appuyez sur Parler.")
        self.wait_state()
        self.controls()

    def move(self, state):
        if self.machine.move(state):
            self.state_label.setText(STATES[state])

    def wait_state(self):
        self.move("GAZE_DETECTION" if self.cfg.camera else "IDLE")

    def activate(self, manual):
        if not self.active or self.busy or time.monotonic() < self.ready_at:
            return
        self.armed.clear()
        self.clear_exchange()
        self.busy = True
        self.move("MANUAL_ACTIVATION" if manual else "GREETING")
        if not self.voice or not self.voice.is_alive():
            self.create_voice_worker()
        self.deadline = time.monotonic() + 60
        self.cancel.clear()
        self.commands.put("start")
        self.controls()

    def create_voice_worker(self):
        self.voice_events, self.commands, self.approvals = (
            self.ctx.Queue() for _ in range(3)
        )
        self.cancel = self.ctx.Event()
        self.talk_gate = self.ctx.Event()
        self.voice = self.ctx.Process(
            target=voice_process,
            args=(
                self.cfg,
                self.commands,
                self.voice_events,
                self.cancel,
                self.approvals,
                self.talk_gate,
            ),
            daemon=True,
        )
        self.voice.start()

    def clear_exchange(self):
        self.question.clear()
        self.answer.clear()
        self.sources.clear()
        self.language.setText("Langue et transcription · —")
        self.timing.clear()

    def finish(self):
        self.clear_exchange()
        self.busy = False
        self.hold.hide()
        self.mic_label.setText("Micro fermé")
        self.mic_bar.setValue(0)
        self.ready_at = time.monotonic() + self.cfg.cooldown
        self.move("END_CONVERSATION")
        self.move("COOLDOWN")
        self.controls()

    def end_session(self):
        if self.voice:
            self.cancel.set()
            self.commands.put("quit")
            self.voice.join(0.12)
            if self.voice.is_alive():
                self.voice.terminate()
                self.voice.join(0.25)
            self.voice = None
        self.finish()

    def shutdown(self):
        if not self.active:
            return
        self.active = False
        self.armed.clear()
        self.cam_stop.set()
        if self.voice:
            self.cancel.set()
            self.commands.put("quit")
        for worker in (self.voice, self.camera):
            if worker:
                worker.join(0.12)
                if worker.is_alive():
                    worker.terminate()
                    worker.join(0.3)
        self.voice = self.camera = None
        self.busy = False
        self.clear_exchange()
        self.move("IDLE")
        self.hold.hide()
        self.video.setText("Caméra en veille")
        self.mic_label.setText("Micro fermé")
        self.gaze.setText("Regard · 0 / 5 s")
        self.model.setText("Moteurs en veille")
        self.filter.setText("Réduction de bruit en veille")
        self.gaze_bar.setValue(0)
        self.mic_bar.setValue(0)
        self.notice.setText("Session arrêtée.")
        self.controls()

    def handle(self, key, v):
        if key == "gaze":
            if self.armed.is_set():
                self.activate(False)
                self.notice.setText(f"Activation par regard · {v:.1f} s")
        elif key == "state":
            self.move(v)
            self.deadline = time.monotonic() + (195 if v == "THINKING" else 90)
        elif key == "notice":
            self.notice.setText(v)
        elif key == "model":
            self.model.setText(v)
        elif key == "hold":
            self.hold.setVisible(v)
            if v:
                self.notice.setText(
                    "Maintenez le bouton et parlez lorsque le micro est ouvert."
                )
        elif key == "filter":
            self.filter.setText(v)
        elif key == "mic":
            self.mic_label.setText("Micro ouvert" if v else "Micro fermé")
        elif key == "level":
            self.mic_bar.setValue(min(100, int(v[0] * 500)))
            if v[0] > 0:
                self.mic_label.setText(
                    "Micro ouvert · parole détectée"
                    if v[1]
                    else "Micro ouvert · écoute"
                )
        elif key == "transcript":
            self.question.setPlainText(v["text"])
            self.answer.clear()
            self.language.setText(
                f"Langue estimée · {v['lang']}    /    {v['seconds']:.2f} s"
            )
            if v["uncertain"]:
                self.notice.setText(
                    "Transcription incertaine · répétez votre question."
                )
        elif key == "sources":
            self.sources.setText(" · ".join(dict.fromkeys(v)))
        elif key == "answer":
            self.answer.setPlainText(v)
        elif key == "timing":
            self.timing.setText(
                f"Fin de parole → texte {v['endpoint_stt']:.1f} s   ·   Premier token {v['stt_token']:.1f} s   ·   Texte → voix {v['token_sound']:.1f} s   ·   Total {v['perceived']:.1f} s"
            )
        elif key == "review":
            request_id, text = v
            dlg = QInputDialog(self)
            dlg.setWindowTitle("Vérifier votre question")
            dlg.setLabelText("Corrigez le texte si nécessaire ou choisissez Répéter.")
            dlg.setTextValue(text)
            dlg.setOkButtonText("Envoyer à l’assistant")
            dlg.setCancelButtonText("Répéter")
            QTimer.singleShot(23000, dlg.reject)
            self.approvals.put(
                (request_id, dlg.textValue().strip()[:600] if dlg.exec() else "")
            )
            dlg.deleteLater()
        elif key == "consent":
            request_id, sentence = v
            box = QMessageBox(
                QMessageBox.Question,
                "Lecture en ligne facultative",
                "Autoriser l’envoi à Microsoft Azure de cette phrase pour la lire ?\n\n"
                + sentence,
                QMessageBox.Yes | QMessageBox.No,
                self,
            )
            box.setDefaultButton(QMessageBox.No)
            QTimer.singleShot(23000, box.reject)
            self.approvals.put((request_id, box.exec() == QMessageBox.Yes))
            box.deleteLater()
        elif key == "done":
            self.finish()

    def poll(self):
        now = time.monotonic()
        if now - self.last_metrics > 3 and not (
            self.metric_thread and self.metric_thread.is_alive()
        ):
            self.last_metrics = now

            def sample():
                if self.metrics.empty():
                    self.metrics.put(resources(0.12))

            self.metric_thread = threading.Thread(target=sample, daemon=True)
            self.metric_thread.start()
        try:
            m = self.metrics.get_nowait()
            self.free_ram = m["available"]
            self.peak_ram = max(self.peak_ram, m["ram"])
            self.peak_vram = max(self.peak_vram, m["vram"])
            self.hardware.setText(
                f"CPU {m['cpu']:.0f}%   ·   RAM système {m['ram']:.1f}/{m['ram_total']:.1f} Gio   ·   VRAM {m['vram']}/{m['vram_total']} Mio"
                if m["vram_total"]
                else f"CPU {m['cpu']:.0f}%   ·   RAM {m['ram']:.1f} Gio   ·   GPU indisponible"
            )
        except queue.Empty:
            pass
        if not self.active:
            return
        for event_queue in (
            [self.events, self.voice_events] if self.voice else [self.events]
        ):
            for _ in range(128):
                try:
                    self.handle(*event_queue.get_nowait())
                except queue.Empty:
                    break
        if self.busy and now > self.deadline:
            self.notice.setText(
                "Le moteur a dépassé le délai de réponse. Réessayez après la pause."
            )
            self.end_session()
        if self.busy and self.voice and not self.voice.is_alive():
            self.notice.setText(
                "Le moteur vocal s’est arrêté. Vous pouvez relancer un échange."
            )
            self.end_session()
        if not self.busy and not self.armed.is_set() and now >= self.ready_at:
            self.armed.set()
            self.wait_state()
            self.controls()
        try:
            data, look, p = self.frames.get_nowait()
            if data:
                pix = QPixmap()
                pix.loadFromData(data)
                self.video.setPixmap(
                    pix.scaled(
                        self.video.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                )
            else:
                self.video.setText(look)
            self.gaze.setText(f"{look} · {p * 5:.1f} / 5 s")
            self.gaze_bar.setValue(int(100 * p))
        except queue.Empty:
            pass

    def suggestion(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Suggestion d’amélioration")
        form = QVBoxLayout(dlg)
        form.addWidget(
            label("Quelle amélioration proposez-vous ? Évitez les noms et coordonnées.")
        )
        edit = QPlainTextEdit()
        form.addWidget(edit)
        check = QCheckBox(
            f"J’accepte la conservation locale de ma suggestion pendant {self.cfg.feedback_days} jours."
        )
        form.addWidget(check)
        btn = button("Enregistrer", dlg.accept)
        btn.setEnabled(False)
        check.toggled.connect(btn.setEnabled)
        form.addWidget(btn)
        if dlg.exec() and self.feedback.add(edit.toPlainText(), check.isChecked()):
            self.notice.setText(
                "Suggestion enregistrée. Merci pour votre contribution."
            )

        dlg.deleteLater()

    def closeEvent(self, event):
        self.shutdown()
        self.feedback.db.close()
        super().closeEvent(event)


STYLE = """
QMainWindow, QDialog { background: #f4f6f4; }
QWidget { font-family: 'Inter','Noto Sans',sans-serif; font-size: 14px; color: #173b38; }
QLabel[kind="brand"] { color:#216e61; font-weight:700; letter-spacing:1px; }
QLabel[kind="title"] { font-size:32px; font-weight:700; }
QLabel[kind="state"] { color:#23695f; font-size:17px; }
QLabel[kind="section"] { font-size:17px; font-weight:600; }
QLabel[kind="muted"] { color:#526b67; font-size:12px; }
QFrame#card { background:white; border:1px solid #d3dfda; border-radius:12px; }
QLabel#video { background:#193c39; color:#d1e6de; border-radius:8px; }
QPlainTextEdit, QLineEdit, QComboBox, QDoubleSpinBox { background:#f7f9f7; border:1px solid #d2ded9; border-radius:6px; padding:6px; }
QProgressBar { border:none; background:#dfe9e4; border-radius:3px; }
QProgressBar::chunk { background:#33997b; border-radius:3px; }
QPushButton { background:white; padding:8px 15px; border:1px solid #bccec5; border-radius:7px; }
QPushButton[primary="true"] { background:#176d5c; color:white; border-color:#176d5c; }
QPushButton:disabled { background:#e7ece9; color:#72847c; border-color:#d6e0da; }
QPushButton:focus { border:2px solid #bd801c; }
"""
