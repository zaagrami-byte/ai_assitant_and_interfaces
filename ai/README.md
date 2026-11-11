# ai — Assistant vocal (PC)

Pipeline local : **micro du robot → VAD → Whisper → Qwen (outils) → Piper → haut-parleur du robot**.

```
python main.py --text --no-ros     # développement sans micro ni robot
python main.py --voice             # voix via le réseau (simulation par défaut)
python main.py --voice --live      # mouvements réels
```

| Dossier | Contenu |
|---|---|
| `assistant/` | Boucle LLM/outils, registre à liste blanche, prompt, mémoire courte, boucle vocale |
| `tools/` | 7 outils : état, pose, destinations, navigation, arrêt |
| `ros2_interface/` | Contrat `RobotInterface`, pont ROS 2, client Nav2 |
| `audio/` | Serveur audio TCP, VAD, protocole (lien vers `robot_audio/protocol.py`) |
| `speech/` | faster-whisper, Piper |
| `knowledge/` | `locations.yaml`, `isimm_knowledge.yaml` |
| `config/` | `assistant.yaml` (la `.env` prime) |
| `scripts/` | Sondes : outils, audio, parole, relevé de position |
| `tests/` | Tests sans ROS ni matériel |

Règles : voir [`docs/AI_ROBOT_BOUNDARY.md`](../docs/AI_ROBOT_BOUNDARY.md) et [`docs/ai-assistant.md`](../docs/ai-assistant.md).
Installation : [`docs/setup-pc.md`](../docs/setup-pc.md).
