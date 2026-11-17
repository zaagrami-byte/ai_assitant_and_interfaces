# Dialogue étudiant et recherche documentaire

## D’où venait la répétition

Le chemin vocal est `Whisper.transcribe → Session.run → Ollama.stream → Speech.say`. La transcription acceptée, ou sa correction à l’écran, arrive dans le dernier message utilisateur de la requête de génération. Un silence, une transcription incertaine ou une formule de fin suivent les branches d’attente, de répétition ou de départ. Le seul audio mis en cache correspond au message de bienvenue.

L’ancien moteur recherchait des mots isolés tels que « temps » dans la question, puis ajoutait les fiches correspondant aux anciennes questions. Dès qu’une fiche correspondait, le modèle devait renvoyer un identifiant sous schéma JSON. Le gestionnaire prononçait le texte intégral de la fiche sélectionnée. Une révision de deux matières et une demande d’horaire aboutissaient ainsi au même texte. Une relance demandant l’année de l’arrêté pouvait déclencher la présentation générale de l’institut.

## Comportement actuel

- Chaque réponse part de la question courante. La mémoire en RAM contient au plus trois paires question/réponse, avec un maximum de 650 caractères par ancien message. La question courante est envoyée entière. Une annonce explicite de changement de sujet coupe l’historique. Une nouvelle conversation démarre vide.
- Une demande d’explication, de conseil ou de rédaction utilise la génération conversationnelle. Une relance peut récupérer le sujet de l’échange précédent. Lorsqu’un étudiant compare deux notions puis demande un exemple de la seconde, le gestionnaire peut reprendre le terme exact qu’il a nommé. Le prompt précise le sens des termes informatiques français ambigus « pile » et « file » lorsqu’ils apparaissent dans ce contexte.
- Pour une répartition simple d’une durée explicite, Qwen propose les activités et leurs poids relatifs. Python calcule les minutes entières pour que leur somme corresponde au temps disponible. Les durées composées ou ambiguës passent par le dialogue ordinaire.
- Le français, l’anglais et l’arabe standard ont des consignes distinctes. Des marqueurs de derja en écriture arabe ou latine peuvent corriger l’étiquette de Whisper. Une relance en arabe peut conserver le registre tunisien. Le texte tunisien emprunte le canal vocal arabe existant. La voix Piper locale a une prononciation jordanienne.
- Les demandes institutionnelles reçoivent au plus trois fiches en contexte. Les phrases-clés multilingues ont plus de poids qu’un mot isolé. Une relance peut récupérer les fiches du sujet précédent. Le modèle rédige la réponse, puis une deuxième requête locale vérifie ses affirmations contre les documents. Un contrôle supplémentaire compare les nombres et les domaines cités avec les sources vérifiées. Une réponse rejetée entraîne une indication de lacune documentaire avant toute lecture.
- L’écran affiche les références vérifiées consultées. Le lecteur reçoit les phrases au fil de la génération pour une réponse libre, et après le contrôle pour une réponse institutionnelle. Un problème de serveur ou de chargement emprunte le chemin d’erreur de l’application.

## Modèles et coût sur l’ASUS

La configuration du poste est `ISIMM_LLM=auto` par défaut. L’application interroge les modèles installés et résidents sur `127.0.0.1:11434`. Elle privilégie `qwen3.5:4b` (Q4_K_M) si au moins 4 400 Mio de VRAM et 2,8 Gio de RAM sont disponibles. Le modèle `qwen3.5:2b` (Q8_0) prend le relais selon les ressources, la lenteur à chaud et les écarts de langue observés. Le serveur du projet limite l’exécution à un seul modèle et une requête à la fois. Les deux modèles étaient déjà installés.

| Paramètre | Génération | Vérification documentaire |
| --- | --- | --- |
| API | Ollama local, `/api/chat` en streaming | Même modèle résident |
| Contexte | 2 048 tokens | 2 048 tokens |
| Maximum produit | 180 tokens | 12 tokens |
| Température | 0,25 | 0 |
| Raisonnement exposé | `think=false` | `think=false` |
| Maintien en mémoire | 90 secondes | 90 secondes |

Sur un tour vocal de contrôle, le mode automatique a effectivement chargé **Qwen 2B**. Whisper small sur CPU a transcrit « Quels sont les départements de l'institut ? » et Piper a joué la réponse. La mesure fin de parole → premier son était de **12,56 s**, dont 5,25 s jusqu’au texte, 5,93 s jusqu’au premier token avec chargement du modèle, 0,79 s pour finir et vérifier la réponse, et 0,58 s jusqu’au son. Le maximum échantillonné du système entier était de 6,36 Gio de RAM et 3 718 Mio de VRAM. Ce tour utilisait une question sonore synthétique injectée dans le traitement audio et une sortie PortAudio réelle. Le tableau de comparaison ci-dessous chronomètre uniquement le dialogue textuel.

## Alimenter le RAG

`Library.retrieve(question, history)` fournit des enregistrements nommés avec `id`, `status`, `text`, et éventuellement `translations`, `source` et `reference`. L’index actuel est lexical et reste en RAM. Pour enrichir l’accueil, ajouter à `knowledge/` les extraits datés et validés par l’établissement, leurs traductions, leurs mots-clés et expressions. Un horaire doit préciser la promotion et la semaine concernées. Marquer une information indisponible ou en attente avec `unavailable` ou `to_confirm`. Un document vérifié exige une source. Le moteur de recherche est injectable dans `Ollama` pour permettre ultérieurement un index sémantique conservant ce contrat. Les faits institutionnels existants n’ont pas été actualisés lors de la correction.

## Reproduire le diagnostic

Pour voir un tour réel, lancer la borne avec le diagnostic activé.

```bash
ISIMM_DIALOGUE_DEBUG=true ./lancer.sh
```

La sortie d’erreur contient des lignes JSON regroupées par `turn`. `stt` contient le texte reconnu et sa langue, `reviewed_transcript` une éventuelle correction, `retrieval` le registre et les identifiants retenus, `ollama_request.body` le corps HTTP complet, `ollama_raw.content` le texte brut reçu pour chaque phase, et `tts_final` le texte normalisé de chaque fragment envoyé en synthèse avec sa langue. Le message de bienvenue précède les tours de questions. Le diagnostic est désactivé par défaut. Une redirection de stderr enregistre les paroles et l’historique inclus dans les prompts.

Pour rejouer les transcriptions synthétiques sans utiliser le microphone, démarrer le serveur du projet, puis lancer dans un autre terminal les commandes suivantes.

```bash
.venv/bin/python -m scripts.evaluate_dialogue --model qwen3.5:2b
.venv/bin/python -m scripts.evaluate_dialogue --model qwen3.5:4b
ISIMM_TEST_LLM=1 ISIMM_TEST_DIALOGUE=1 QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -v
```

Le script accepte aussi `--trace` et `--model auto`. Le test de corpus utilise le 4B par défaut et accepte `ISIMM_TEST_MODEL=qwen3.5:2b`. La suite sans ces variables couvre le transport HTTP simulé, la correction de transcription, le texte réellement remis au TTS, la mémoire, la recherche, la langue, le rejet des faits non étayés et le calcul des durées.


## Comparaison mesurée

Le premier passage comprend 20 transcriptions dans huit conversations. Les deux modèles corrigés ont rejoué ces mêmes échanges, puis sept autres cas indépendants. Les 27 transcriptions couvrent 15 conversations avec 12 interventions après la première question, dont des relances et des changements de sujet. Chaque conversation repart à vide. Les transcriptions sont synthétiques et le serveur Ollama est réel.

| Modèle | Questions | Tous les indices thématiques attendus présents | Réponses textuellement distinctes | Durée médiane jusqu’au texte complet |
| --- | ---: | ---: | ---: | ---: |
| 2B avant | 20 | 9/20 | 13/20 | 0,43 s |
| 2B après | 20 | 16/20 | 20/20 | 1,18 s |
| 2B après | 27 | 22/27 | 27/27 | 1,22 s |
| 4B après | 20 | 20/20 | 20/20 | 1,78 s |
| 4B après | 27 | 27/27 | 27/27 | 1,84 s |

Les 20 premières lignes permettent la comparaison à modèle et questions identiques. Les durées incluent le routage, la génération et la vérification éventuelle, ainsi que le chargement s’il a lieu. Elles excluent la transcription et la synthèse. Ollama 0.40.16 a affiché `llamacpp`, un contexte de 2 048 et 100 % GPU pour les deux modèles. La taille résidente affichée était de 2,3 GB pour le 2B et 3,1 GB pour le 4B. Les nombres de réponses distinctes mesurent la répétition à l’identique. Les indices thématiques sont des expressions attendues dans le texte, avec leurs limites linguistiques. Le test vérifie aussi le total d’une répartition explicite et recherche certaines inventions d’horaire ou de pièces exigées.

Chaque question, sa réponse complète, sa durée et les indices absents sont disponibles pour inspection. [Résultats avant et après](dialogue-evaluation.json)

En français, l’ancienne réponse à la question de révision était « Aucun emploi du temps daté n’est disponible dans la base. » Le 4B a désormais proposé des séances, puis réparti les 30 minutes de la relance en 15 minutes pour la première matière, 6 de pause et 9 pour la seconde. Pour les départements, le 4B a répondu « Il y en a trois. » au comptage et « L’arrêté a été publié en 2022. » à la question sur l’année. En darja, il a illustré la file par une queue où la première personne arrivée est servie en premier.

La suite complète utilise le 4B pour le test de qualité. Le passage supplémentaire sur le 2B a obtenu 22/27, sous le seuil fixé à 85 %. Il a notamment produit trois étiquettes anglaises pour une répartition demandée en français et mal compris « la seconde » en tunisien malgré la présence du référent dans le prompt. Les deux modèles peuvent mélanger arabe standard et registres régionaux. Les motifs automatiques ne mesurent ni la justesse de chaque analogie ni le naturel de la prononciation. Le vérificateur documentaire partage le modèle générateur et peut se tromper sur une affirmation qualitative. Les résultats du corpus concernent ces échanges et cette exécution.
