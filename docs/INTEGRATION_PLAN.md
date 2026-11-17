# Integration plan — AssistantISIMM desktop + distributed robot

## Target topology
- PC: desktop application and Qt UI, IP camera and vision, French-only assistant, Ollama/Qwen 2.5:3b, STT, Piper TTS, ROS 2 Jazzy/Nav2 client and robot bridge.
- Raspberry Pi: microphone capture and speaker playback only; transports PCM to/from PC.
- Robot safety remains independent: motor controller watchdog and physical E-stop. AI must not publish directly to /cmd_vel.

## Ownership decisions
- Keep the colleague's desktop UI and vision implementation as the presentation/vision baseline.
- Keep the distributed audio transport, audio protocol, Raspberry Pi client, VAD and audio server from the integration branch.
- Keep the branch assistant, prompt, YAML knowledge, tool registry, ROS 2/Nav2 bridge and navigation safety logic.
- Keep Piper as the only initial TTS engine.
- French only for the first usable release.
- Do not add DeepFilterNet, Silero VAD, Kokoro, RAG or automatic model switching to the MVP. Evaluate only after a reproducible benchmark shows a measurable benefit.

## Important integration work (not yet complete)
1. Refactor the desktop GUI's current local voice worker into a UI/controller adapter that calls the branch Assistant and remote AudioServer. Keep UI updates on Qt's main thread.
2. Run the PC camera/vision worker independently of Raspberry Pi audio. Keep the IP camera URL in desktop settings.
3. Use branch Faster-Whisper and Piper on PC. Add transcription confidence/uncertainty handling from desktop_app/isimm/stt.py without importing the colleague's LLM/dialogue implementation.
4. Configure Ollama model to qwen2.5:3b and warm it before the first interaction; retain branch tool calling and YAML prompt.
5. Secure the TCP audio transport before deployment on untrusted networks (TLS or authenticated encryption; HELLO/version validation alone is not authentication).
6. Split spoken navigation cancellation from emergency stop. Spoken “stop” cancels an active Nav2 goal; physical E-stop and watchdog remain the safety-rated stop path.
7. Add integration tests and measure endpoint-to-first-audio latency, STT accuracy on real French speech, and navigation safety behavior.

## Current status
This commit imports the colleague's original desktop UI, vision, and supporting desktop package under desktop_app/ without replacing the distributed runtime. This is a preservation/import step, not a completed working integration. The next step is the GUI-to-Assistant adapter and end-to-end test.
