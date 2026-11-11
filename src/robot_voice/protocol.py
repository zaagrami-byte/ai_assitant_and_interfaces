"""Authenticated, bounded message contract for the robot voice bridge.

This module validates messages only. It does not execute ROS actions or publish velocity.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

MAX_MESSAGE_BYTES = 4096
MAX_CLOCK_SKEW_SECONDS = 10
ALLOWED_TYPES = {"INTENT", "ACTION_RESULT", "STATUS"}
ALLOWED_ACTIONS = {
    "cancel_navigation",
    "navigate_to_named_location",
    "get_robot_status",
}


class ProtocolError(ValueError):
    """Raised when a voice-bridge message is invalid or unauthenticated."""


@dataclass(frozen=True)
class VoiceMessage:
    version: int
    message_id: str
    timestamp: int
    sequence: int
    type: str
    payload: dict[str, Any]


class ReplayGuard:
    """Small in-memory replay guard; persist/coordinate it for multi-process use."""

    def __init__(self, capacity: int = 2048) -> None:
        self._seen: set[str] = set()
        self._order: deque[str] = deque(maxlen=capacity)

    def accept(self, message_id: str) -> None:
        if message_id in self._seen:
            raise ProtocolError("replayed message")
        if len(self._order) == self._order.maxlen:
            oldest = self._order[0]
            self._seen.discard(oldest)
        self._order.append(message_id)
        self._seen.add(message_id)


def canonical_bytes(message: dict[str, Any]) -> bytes:
    unsigned = {key: value for key, value in message.items() if key != "mac"}
    return json.dumps(
        unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sign_message(message: dict[str, Any], secret: bytes) -> str:
    if not secret:
        raise ProtocolError("empty HMAC secret")
    return hmac.new(secret, canonical_bytes(message), hashlib.sha256).hexdigest()


def validate_message(
    raw: bytes,
    secret: bytes,
    replay_guard: ReplayGuard,
    *,
    now: int | None = None,
) -> VoiceMessage:
    if not secret:
        raise ProtocolError("HMAC secret is not configured")
    if len(raw) > MAX_MESSAGE_BYTES:
        raise ProtocolError("message too large")
    try:
        obj = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError("invalid JSON") from exc
    if not isinstance(obj, dict):
        raise ProtocolError("message must be a JSON object")

    required = {"version", "message_id", "timestamp", "sequence", "type", "payload", "mac"}
    if set(obj) != required:
        raise ProtocolError("unexpected or missing message fields")
    supplied_mac = obj.get("mac")
    if not isinstance(supplied_mac, str):
        raise ProtocolError("missing message authentication code")
    expected_mac = sign_message(obj, secret)
    if not hmac.compare_digest(supplied_mac, expected_mac):
        raise ProtocolError("authentication failed")

    version = obj["version"]
    message_id = obj["message_id"]
    timestamp = obj["timestamp"]
    sequence = obj["sequence"]
    message_type = obj["type"]
    payload = obj["payload"]
    if version != 1:
        raise ProtocolError("unsupported protocol version")
    if not isinstance(message_id, str) or not (1 <= len(message_id) <= 128):
        raise ProtocolError("invalid message_id")
    if isinstance(timestamp, bool) or not isinstance(timestamp, int):
        raise ProtocolError("invalid timestamp")
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
        raise ProtocolError("invalid sequence")
    if message_type not in ALLOWED_TYPES:
        raise ProtocolError("message type not allowed")
    if not isinstance(payload, dict):
        raise ProtocolError("payload must be an object")

    current_time = int(time.time()) if now is None else now
    if abs(current_time - timestamp) > MAX_CLOCK_SKEW_SECONDS:
        raise ProtocolError("message timestamp outside freshness window")

    if message_type == "INTENT":
        if set(payload) - {"action", "destination"}:
            raise ProtocolError("unexpected intent fields")
        action = payload.get("action")
        if action not in ALLOWED_ACTIONS:
            raise ProtocolError("action not allowlisted")
        if action == "navigate_to_named_location":
            destination = payload.get("destination")
            if not isinstance(destination, str) or not (1 <= len(destination) <= 80):
                raise ProtocolError("invalid destination")
        elif "destination" in payload:
            raise ProtocolError("destination not valid for this action")

    replay_guard.accept(message_id)
    return VoiceMessage(
        version=version,
        message_id=message_id,
        timestamp=timestamp,
        sequence=sequence,
        type=message_type,
        payload=payload,
    )


def load_hmac_secret() -> bytes:
    """Load the deployment secret from the environment; never use a default."""
    value = os.environ.get("ROBOT_VOICE_HMAC_KEY")
    if not value:
        raise ProtocolError("ROBOT_VOICE_HMAC_KEY is not set")
    return value.encode("utf-8")
