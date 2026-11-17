# Assistant vocal ISIMM

Application de bureau pour l’accueil des étudiants à Monastir. Le smartphone fournit les images, le PC écoute et les modèles s’exécutent sur l’ASUS. Le bouton **Parler** permet d’engager un échange sans caméra.

## Démarrer sur cet ASUS

Pour ouvrir la borne avec son serveur local, lancer dans un terminal Cinnamon :

```bash
cd ~/Desktop/AssistantISIMM
./lancer.sh
```

Le lanceur réutilise le serveur local déjà présent, ou démarre un serveur qu’il ferme à la sortie. Pour séparer les deux processus pendant un diagnostic, ouvrir un terminal pour le serveur.

```bash
cd ~/Desktop/AssistantISIMM
scripts/ollama-local serve
```

Si le serveur écoute déjà sur le port 11434, passer directement à l’application dans un second terminal.

```bash
cd ~/Desktop/AssistantISIMM
.venv/bin/python -m isimm
```

Choisir **Paramètres** avant de démarrer pour sélectionner le micro, la voix ou le modèle. **Démarrer** affiche les conditions, puis active l’accueil. Regarder la caméra cinq secondes ou appuyer sur **Parler**, attendre que l’indicateur affiche **Micro ouvert**, puis poser la question. Dire « au revoir » ou choisir **Terminer** pour effacer l’échange. **Arrêter** ferme les périphériques et décharge les moteurs de l’application. Ollama garde au plus un modèle pendant 90 secondes après sa dernière utilisation. Pour arrêter aussi le serveur lancé dans un terminal, utiliser Ctrl+C dans ce terminal.

Pour une démonstration vocale sans caméra, lancer `.venv/bin/python -m isimm --sans-camera`. Ce mode utilise le vrai micro, les modèles locaux et la sortie audio du bureau. Dans un hall animé, activer **Paramètres → Tour de parole → Maintenir le bouton pendant la question**. On peut alors délimiter chaque question à la main.

## Installation sur Ubuntu Cinnamon x86-64

Prévoir PipeWire ou PulseAudio, PortAudio, les bibliothèques graphiques de Qt, curl, zstd et un interpréteur capable de créer un venv. L’installation initiale télécharge les dépendances et les poids. Dans une session utilisateur Cinnamon avec accès au son et au réseau, exécuter les commandes suivantes depuis le projet.

```bash
bash scripts/diagnostic.sh
bash scripts/install.sh
.venv/bin/python scripts/assets.py audio camera kokoro fr_FR ar_JO en_US base small
bash scripts/install-ollama.sh
scripts/ollama-local serve
```

Dans un autre terminal, installer les modèles dans le magasin du projet.

```bash
scripts/ollama-local pull qwen3.5:2b
scripts/ollama-local pull qwen3.5:4b
cp -n .env.example .env
.venv/bin/python -m isimm
```

Le script d’installation place CPython 3.11, uv et les paquets dans le projet. Pour une machine où `python3 -m venv` échoue, installer le paquet Ubuntu `python3-venv` correspondant à la version de Python du système. Si PortAudio manque, le paquet est `libportaudio2`. Un échec du plugin Qt xcb se diagnostique avec `QT_DEBUG_PLUGINS=1 .venv/bin/python -m isimm` et la bibliothèque manquante indiquée dans la sortie. Sur l’ASUS, le pilote NVIDIA existant suffit à Ollama. L’application peut exécuter Whisper INT8 sur CPU indépendamment du GPU.

Configurer `ISIMM_CAMERA` dans `.env` avec l’URL de flux livrée par l’application du téléphone, par exemple `http://192.168.1.10:8080/video`. Les réglages de la fenêtre s’appliquent au lancement courant. Le fichier `.env` permet de les retrouver après redémarrage.

## Architecture

| Composant | Responsabilité |
| --- | --- |
| `isimm/vision.py` | Acquisition OpenCV avec délais de connexion et de lecture, dernière image, MediaPipe Face Landmarker, regard et temporisation monotone. |
| `isimm/audio.py`, `denoise.py` | Entrée PortAudio mono, hôte DeepFilterNet LADSPA, décimation FIR continue, Silero ONNX, fenêtre de parole et bouton maintenu. |
| `isimm/stt.py` | Faster-Whisper local, détection de langue, repli CPU/base, décision de répétition. |
| `isimm/llm.py`, `knowledge.py` | Recherche documentaire ciblée, historique de trois échanges, génération et vérification via Ollama en streaming sur 127.0.0.1. |
| `isimm/tts.py` | Normalisation, Kokoro INT8, Piper, lecture par phrases, Azure sur consentement. |
| `isimm/conversation.py` | Séquence des tours, fin sur silence ou salutation, mesures des étapes de réponse. |
| `isimm/gui.py` | Interface Qt, arbitrage entre regard et bouton, processus de vision et de voix, interruption, cooldown et surveillance. |
| `isimm/feedback.py` | Suggestions volontaires dans une base SQLite privée. |
| `scripts/`, `tests/` | Diagnostic, acquisition des modèles, sondes, corpus multilingue, mesures et tests. |

Le processus vocal possède le micro, le décodeur, le client Ollama et le lecteur. Il ouvre la capture après la lecture de l’invitation. La capture ferme avant la transcription. La boucle Qt peut arrêter le processus même lorsqu’une bibliothèque native attend. Le processus vidéo continue à alimenter l’aperçu avec une file bornée. Les états et les transitions autorisées sont définis dans `isimm/state.py`. L’activation par regard et l’activation manuelle partagent le même verrou logique dans la boucle Qt.

Les adaptateurs sont injectés dans `Session`. Un micro directionnel USB apparaît dans le sélecteur d’entrée. Un futur adaptateur de beamforming peut implémenter `listen(stop)`. La signature `EchoControl` documente les deux flux à fournir à un futur AEC. Le fonctionnement actuel est semi-duplex.

## Connaissances et confidentialité

Ajouter dans `knowledge/` un fichier JSON contenant des fiches sur le modèle de `campus.json`. Donner à chaque fiche un identifiant, des mots-clés français, anglais ou arabes, un texte court, un statut et la référence du document. Une fiche `verified` exige une source. Utiliser `to_confirm` pour une information en attente de validation et `unavailable` pour une information manquante. Pour les horaires, indiquer la semaine, la promotion et la date du document. La recherche classe les documents pour la question actuelle et reprend le sujet précédent lorsqu’une relance le nécessite. Les fiches alimentent le prompt de génération. Les réponses portant sur un fait local passent par un contrôle avant lecture. Un adaptateur de recherche peut être injecté dans `Ollama` via `library.retrieve(question, history)`. La fiche sur les départements s’appuie sur l’article 8 du JORT. [JORT du 26 avril 2022, article 8](https://lake.jort.tn/journal-officiel/fr/2022/046.pdf)

Par défaut, les sons, images, transcriptions et réponses restent en mémoire. Activer `ISIMM_DIALOGUE_DEBUG=true` affiche le texte des échanges sur la sortie d’erreur. Une redirection de cette sortie conserve les échanges sur disque. La fin de l’échange efface le texte de la fenêtre et l’historique. Les journaux applicatifs signalent le type d’erreur sur la console. En fonctionnement normal, les seules données étudiantes écrites par l’application sont les suggestions expressément acceptées. La base `local/suggestions.sqlite` est créée avec des permissions utilisateur. La purge s’effectue au lancement puis chaque minute de fonctionnement. `ISIMM_FEEDBACK_DAYS=0` désactive le recueil et purge les anciennes suggestions au lancement.

Pour essayer Azure, renseigner la région et la clé dans le fichier privé `.env`, choisir une voix tunisienne et activer l’option en ligne. Avant la synthèse, la fenêtre présente **le texte exact** qui serait envoyé. Un refus ou l’expiration de la demande conserve la lecture locale en arabe. L’exploitant doit valider les conditions applicables avant une démonstration publique. L’arabe de la voix locale Piper est jordanien. La version courante propose Reem et Hedi pour Azure. [Catalogue vocal Microsoft](https://learn.microsoft.com/azure/ai-services/speech-service/language-support?tabs=tts)

## Vérification et mise au point

```bash
.venv/bin/python -m unittest discover -v
.venv/bin/python -m scripts.probe camera
.venv/bin/python -m scripts.probe microphone
.venv/bin/python -m scripts.probe tts
.venv/bin/python -m scripts.probe llm --model qwen3.5:2b
.venv/bin/python -m scripts.evaluate --model base --ids fr en ar
```

Voir [le diagnostic conversationnel, les paramètres et les essais avant/après](docs/dialogue.md), [le guide de calibration et d’essais](docs/calibration.md) et [les résultats sur l’ASUS](docs/performances.md).

Pour rejouer les essais matériels et la mesure d’un tour complet avec une question générée et un son effectivement joué :

```bash
ISIMM_TEST_CAMERA=1 ISIMM_TEST_VOICE=1 ISIMM_TEST_LLM=1 QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -v
.venv/bin/python -m scripts.probe camera --duration 18
ISIMM_STT=small ISIMM_LLM=qwen3.5:2b ISIMM_VOLUME=0.2 .venv/bin/python -m scripts.benchmark_turn
```
# AssistantISIMM
