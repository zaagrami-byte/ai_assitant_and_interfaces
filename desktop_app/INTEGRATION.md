# Interface desktop + moteur vocal distribué

## Lancement
Depuis la racine du dépôt, après installation des dépendances PC et configuration ROS 2 Jazzy :

```bash
source /opt/ros/jazzy/setup.bash
python -m pip install -r desktop_app/requirements.txt
python -m pip install -r ai/requirements.txt
python -m desktop_app.isimm
```

Le worker ajoute automatiquement le répertoire `ai/` au chemin Python pour réutiliser le runtime du dépôt.

## Configuration PC
- `desktop_app/.env`: `ISIMM_CAMERA` = URL du flux IP (la caméra est connectée au PC).
- `ai/config/assistant.yaml`: `llm.model: qwen2.5:3b`, modèle Whisper, chemin Piper, paramètres VAD et ROS.
- `ai/.env`: `AUDIO_HOST=0.0.0.0`, `AUDIO_PORT=5005`, `OLLAMA_HOST=http://localhost:11434`.

## Configuration Raspberry Pi
Dans `/etc/isimm/audio.env`, configurer `AUDIO_PC_HOST` avec l'adresse IP du PC, le port 5005 et les périphériques ALSA. Le Pi exécute uniquement `python3 -m robot_audio`.

## Limites de cette première intégration
- L'interface graphique et le worker caméra du collègue sont conservés.
- Le worker vocal de l'interface appelle le serveur audio distribué, Faster-Whisper, l'Assistant/tool registry, Ollama et Piper du dépôt principal. Le traitement du microphone reste sur le Pi ; le flux caméra IP est capturé par le PC.
- Le traitement LLM attend encore la réponse complète de `Assistant.handle()`. Le transport Piper/TCP est progressif par phrases, mais le LLM→TTS n'est pas encore du vrai streaming.
- Le protocole TCP audio actuel ne chiffre ni n'authentifie le flux. Utiliser uniquement un réseau robot isolé jusqu'à l'ajout d'une authentification cryptographique ou TLS intégrée. Le paramètre `stop_mode: cancel` évite qu'une commande vocale ordinaire déclenche l'E-stop matériel ; l'E-stop physique et le watchdog restent indépendants.
- Cette étape est une intégration de code ; elle n'a pas encore été exécutée sur le PC, la caméra IP ou le robot physique.
