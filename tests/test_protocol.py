import json
import unittest

from robot_voice.protocol import (
    ProtocolError,
    ReplayGuard,
    sign_message,
    validate_message,
)


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.secret = b"test-only-secret"
        self.guard = ReplayGuard()

    def make_raw(self, *, action="get_robot_status", message_id="m-1", timestamp=1000):
        message = {
            "version": 1,
            "message_id": message_id,
            "timestamp": timestamp,
            "sequence": 1,
            "type": "INTENT",
            "payload": {"action": action},
        }
        message["mac"] = sign_message(message, self.secret)
        return json.dumps(message).encode()

    def test_valid_allowlisted_intent(self):
        result = validate_message(
            self.make_raw(), self.secret, self.guard, now=1000
        )
        self.assertEqual(result.payload["action"], "get_robot_status")

    def test_rejects_invalid_mac(self):
        raw = json.loads(self.make_raw())
        raw["mac"] = "0" * 64
        with self.assertRaises(ProtocolError):
            validate_message(json.dumps(raw).encode(), self.secret, self.guard, now=1000)

    def test_rejects_non_allowlisted_action(self):
        raw = self.make_raw(action="run_shell")
        with self.assertRaises(ProtocolError):
            validate_message(raw, self.secret, self.guard, now=1000)

    def test_rejects_replay(self):
        raw = self.make_raw()
        validate_message(raw, self.secret, self.guard, now=1000)
        with self.assertRaises(ProtocolError):
            validate_message(raw, self.secret, self.guard, now=1000)

    def test_rejects_stale_message(self):
        with self.assertRaises(ProtocolError):
            validate_message(self.make_raw(), self.secret, self.guard, now=2000)


if __name__ == "__main__":
    unittest.main()
