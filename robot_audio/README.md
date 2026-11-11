# robot_audio — Client audio du robot (Raspberry Pi)

Aucun modèle IA, **bibliothèque standard uniquement**. Le micro (`arecord`) est envoyé au PC, la voix (`aplay`) est reçue du PC.

```bash
python3 -m robot_audio                  # service
python3 -m robot_audio --list-devices   # arecord -l / aplay -l
python3 -m robot_audio --test-mic       # niveau du micro (crête / RMS)
python3 -m robot_audio --test-speaker   # bip 440 Hz
```

Configuration par variables `AUDIO_*` (voir `/etc/isimm/audio.env`) : `AUDIO_PC_HOST` (obligatoire), `AUDIO_PORT` (5005), `AUDIO_CAPTURE_DEVICE`, `AUDIO_PLAYBACK_DEVICE`, `AUDIO_MIC_RATE` (16000), `AUDIO_FRAME_MS` (20), `AUDIO_MUTE_TAIL_MS` (400), `AUDIO_PING_INTERVAL_S`, `AUDIO_PEER_TIMEOUT_S`, `AUDIO_ROBOT_ID`.

Reconnexion automatique avec backoff (1 → 5 s), heartbeat, micro coupé pendant que le robot parle.
Protocole : [`docs/architecture.md`](../docs/architecture.md#protocole-audio-robot--pc).
