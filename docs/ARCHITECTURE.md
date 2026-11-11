# ISIMM Robot — Voice Architecture

## Objectives

- Keep routine commands local and responsive.
- Keep microphone audio local until wake phrase detection.
- Use the PC for expensive recognition and language generation when available.
- Degrade gracefully when the PC or Wi-Fi is unavailable.
- Keep navigation and motor safety independent from AI.

Sub-second response is an initial measurement target for a small local command set, not a guarantee. LLM answers and remote fallback will usually take longer.

## Hardware allocation

### Pi 4 — 2 GB: audio endpoint
- ALSA capture/playback.
- openWakeWord wake phrase detection.
- WebRTC VAD and bounded utterance buffering.
- Small grammar-constrained recognizer (Vosk is a candidate).
- Prerecorded local acknowledgements and stop-command handling.
- No Nav2, Whisper, Ollama, or camera inference on this board.

### PC: optional compute
- faster-whisper STT fallback.
- Ollama/Qwen intent and dialogue processing.
- Piper TTS.
- Strictly allowlisted tool orchestration.
- Stream short TTS segments when supported.

The PC is an accelerator, not a safety dependency. Local commands and operational stop requests must still work when it is offline.

### Pi 4 — 8 GB: robot and ROS
- ROS 2 Jazzy, Nav2, localization and LiDAR integration.
- Dedicated voice bridge for typed high-level requests.
- Navigation goal cancellation and status reporting.
- Existing velocity and motor safety chain remains authoritative.

## Runtime state machine

```text
IDLE
  └─ wake phrase → LISTENING
       ├─ local stop phrase → STOP_REQUEST → IDLE
       ├─ local command → LOCAL_ACTION → SPEAKING → IDLE
       ├─ no local match + PC online → REMOTE_STT → REMOTE_INTENT
       │      → ALLOWLIST_CHECK → ACTION/ANSWER → SPEAKING → IDLE
       ├─ no local match + PC offline → OFFLINE_PROMPT → IDLE
       └─ timeout/cancel → IDLE

SPEAKING
  └─ barge-in → stop playback → LISTENING
```

Only the audio endpoint owns microphone capture. Do not stream raw audio while IDLE.

## Audio pipeline

1. Capture mono PCM; 16 kHz is the initial target, subject to microphone compatibility.
2. Run wake-word detection locally.
3. After wake, run VAD and collect a bounded utterance.
4. Try local grammar recognition.
5. If confidence is insufficient, send only that utterance to the PC.
6. PC runs STT and structured intent extraction.
7. Validate the result against a strict schema and allowlist.
8. Execute only approved high-level tools.
9. Return response text/audio; stream TTS chunks when possible.

An LLM response is never an executable command. Deterministic validation decides whether an intent is permitted.

## Safety boundary

Separate commands into three classes:

- **Local UI/audio:** repeat, volume, help, cancel speech.
- **Operational robot requests:** cancel the active Nav2 goal, request a named destination, query robot status.
- **Safety functions:** physical E-stop, motor power isolation, motor-controller watchdog. These remain independent of voice and AI.

A spoken "stop" may request cancellation of the active navigation goal. It is not a safety-rated emergency stop. Voice must never reset/rearm E-stop.

Preserve the established command path:

```text
Nav2 /cmd_vel_nav
  → velocity_smoother
  → cmd_vel_mux (AUTO / MANUAL / ESTOP)
  → Collision Monitor
  → safety_node
  → motor_controller
  → Arduino watchdog
  → motor driver

Physical E-stop remains independent and dominant.
```

The AI service must never publish `/cmd_vel`, `/cmd_vel_nav`, motor PWM, or motor direction signals.

## Network protocol and security

Use a small versioned message contract with fields:
- `version`, `message_id`, `timestamp`, `sequence`, `type`, `payload`.
- Message types: WAKE, UTTERANCE, INTENT, ACTION_RESULT, STATUS.

Requirements:
- Explicit peer allowlist.
- HMAC-SHA256 authentication with a per-deployment secret stored outside Git.
- Timestamp freshness and replay protection using message IDs/sequences.
- Maximum message size and strict schema validation.
- Timeouts, rate limiting, and fail-closed behavior.
- Never log secrets or commit them.

Prefer TLS/mTLS for request/response services. If UDP is used for a small stop-request datagram, authenticate it, prevent replay, rate-limit it, and bound payload parsing. UDP delivery is not guaranteed; the physical stop path must never depend on it.

## Recognition strategy

Start with one language and a deliberately small command grammar. Validate the actual microphone, accent, room acoustics, and motor noise before expanding language coverage.

Do not assume model size, RAM use, or latency from generic estimates. Benchmark the exact Vosk model on the 2 GB Pi. Keep local recognition narrow; route open-ended questions to the PC fallback.

## Latency instrumentation

Record monotonic timestamps for wake detection, VAD start/end, local recognition, request send/receive, STT completion, LLM first token/completion, first TTS audio ready, first audio played, and action accepted/completed.

Report p50, p95, and worst-case latency separately for local commands, PC fallback, and PC-offline operation. Optimize time-to-first-audible-response, not only token generation speed.

## Failure behavior

| Failure | Required behavior |
|---|---|
| PC unreachable | Wake word, local commands and local stop request remain available |
| Wi-Fi lost | No remote request; no unsafe queued action replay |
| Wake false positive | Timeout/discard; no robot tool call |
| Low STT confidence | Ask to repeat; do not guess a destination |
| Invalid/unknown tool | Reject |
| Audio playback failure | Robot control remains independent |
| Voice bridge unavailable | No robot action |
| Audio service crash | ROS/Nav2 and motor safety continue |

## Migration plan

### Phase 0 — Baseline and inventory
- Record Pi OS, audio devices, microphone/speaker model, PC hardware, ROS topics/actions and network topology.
- Save a known-good robot software snapshot.
- Verify physical E-stop and Arduino watchdog independently.

### Phase 1 — Audio endpoint only
- Implement capture/playback on the 2 GB Pi.
- Add wake word, VAD, bounded utterance buffering and local prerecorded prompts.
- Measure false/missed wake rates in quiet and noisy conditions.
- No ROS connection yet.

### Phase 2 — Local commands
- Add grammar-limited recognition.
- Implement help/repeat/cancel and operational stop request.
- Measure accuracy and latency on target hardware.
- Do not expose navigation actions until the bridge is reviewed.

### Phase 3 — PC fallback
- Add authenticated request/response API for utterance STT, intent extraction and TTS.
- Add timeouts and PC-unavailable behavior.
- Verify that only the utterance is sent after wake.

### Phase 4 — ROS bridge
- Implement a separate ROS 2 node on the 8 GB Pi.
- Accept only typed, authenticated, allowlisted requests.
- Map navigation requests to existing Nav2 actions; map stop to active-goal cancellation.
- Confirm AI cannot publish velocity commands or reset E-stop.

### Phase 5 — Integrated validation
- Test with wheels lifted, then at low speed in a controlled area.
- Test Wi-Fi loss, PC shutdown, process crash, malformed/replayed messages, false wake, barge-in and motor noise.
- Verify physical E-stop and watchdog under every software failure.
- Enable normal operation only after review of logs and test results.

## Acceptance criteria

- No raw microphone streaming while IDLE.
- Local stop request works with PC disconnected.
- Invalid and unauthenticated messages are rejected.
- Replayed messages are rejected.
- AI has no direct motor/velocity command path.
- Nav2 and safety remain operational when AI services stop.
- Latency is measured on target hardware.
- Physical E-stop and watchdog are independently verified.
