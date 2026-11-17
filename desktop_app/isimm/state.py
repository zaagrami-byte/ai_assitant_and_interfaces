from enum import Enum


class State(str, Enum):
    IDLE = "IDLE"
    GAZE_DETECTION = "GAZE_DETECTION"
    MANUAL_ACTIVATION = "MANUAL_ACTIVATION"
    GREETING = "GREETING"
    LISTENING = "LISTENING"
    TRANSCRIBING = "TRANSCRIBING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    END_CONVERSATION = "END_CONVERSATION"
    COOLDOWN = "COOLDOWN"
    ERROR = "ERROR"


class Machine:
    """Les événements des workers sont appliqués uniquement par la boucle Qt."""

    transitions = {
        State.IDLE: {State.GAZE_DETECTION, State.MANUAL_ACTIVATION},
        State.GAZE_DETECTION: {State.MANUAL_ACTIVATION, State.GREETING},
        State.MANUAL_ACTIVATION: {State.GREETING},
        State.GREETING: {State.LISTENING},
        State.LISTENING: {State.TRANSCRIBING},
        State.TRANSCRIBING: {State.THINKING, State.SPEAKING},
        State.THINKING: {State.SPEAKING},
        State.SPEAKING: {State.LISTENING},
        State.ERROR: {State.END_CONVERSATION},
        State.END_CONVERSATION: {State.COOLDOWN},
        State.COOLDOWN: {State.GAZE_DETECTION},
    }

    def __init__(self):
        self.state = State.IDLE

    def move(self, target):
        target = State(target)
        universal = target in (State.IDLE, State.END_CONVERSATION, State.ERROR)
        if (
            self.state != target
            and not universal
            and target not in self.transitions[self.state]
        ):
            return False
        self.state = target
        return True
