# AI Assistant and Interfaces

Modular voice-assistant layer for the ISIMM administrative reception robot.

## Status

This repository currently contains the architecture baseline. Hardware integration and runtime modules are not yet implemented or validated.

## Target deployment

- **Pi 4 (2 GB):** microphone/speaker I/O, wake-word detection, VAD, lightweight local command recognition, local stop-command handling.
- **PC (optional):** Whisper STT fallback, Ollama/Qwen LLM, Piper TTS, orchestration of allowed assistant tools.
- **Pi 4 (8 GB):** ROS 2 Jazzy, Nav2, localization/mapping and the voice-to-robot bridge.
- **Arduino / motor controller:** low-level motor control and independent watchdog.

## Safety boundary

The assistant must never publish to `/cmd_vel`, control motor PWM, or bypass the ROS safety chain. It may request whitelisted high-level actions through a dedicated interface. The physical emergency stop and motor watchdog remain independent of voice, network, Linux, and AI availability.

A spoken "stop" is an operational stop request (for example, cancel the current navigation goal). It is **not** a safety-rated emergency stop.

## Documentation

- [Target architecture and migration plan](docs/ARCHITECTURE.md)
- [Example deployment configuration](config/voice.example.yaml)

## Current implementation status

| Component | Status |
|---|---|
| Architecture and safety contracts | Documented |
| Pi audio service | Not implemented |
| Wake-word and VAD pipeline | Not implemented |
| Local command recognizer | Not implemented |
| PC STT/LLM/TTS service | Not implemented |
| Authenticated Pi-to-ROS bridge | Not implemented |
| Automated tests and hardware validation | Not implemented |

Do not deploy this repository on the robot as an operational control system until the implementation, security review, and hardware tests are complete.
