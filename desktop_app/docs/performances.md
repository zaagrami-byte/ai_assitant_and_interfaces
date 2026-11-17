# Mesures sur l’ASUS V16

Essais du 16 novembre 2026, sous Ubuntu 26.04.1 LTS avec Cinnamon. L’ASUS dispose d’un Intel Core 5 210H, 8 cœurs et 12 processeurs logiques, de 7,4 Gio de RAM utilisable et de 4 Gio de swap. Le diagnostic initial hors bac à sable a mesuré une RTX 3050 Laptop avec 6 144 Mio de VRAM, dont 16 Mio occupés, et environ 2,3 Gio de RAM disponible. Le pilote NVIDIA 595.99.02 annonce CUDA 13.2. Les bibliothèques cuBLAS et cuDNN sont absentes du cache de l’éditeur de liens du système. Les essais Faster-Whisper utilisent CTranslate2 en INT8 sur CPU. Ollama utilise ses propres bibliothèques CUDA.

## Activation et capture réelles

| Essai | Mesure |
| --- | --- |
| Flux MJPEG du smartphone, modèle Face Landmarker réel | 124 images traitées en 12 s, premier aperçu en 1,54 s. |
| Regard avec repère du visage corrigé pour l’inclinaison | 200 images en 18 s, premier aperçu en 0,99 s, une activation après **5,04 s**, dont 180 images classées « Regard vers la caméra ». |
| Microphone réel, DeepFilterNet et Silero | 3,008 s à 48 kHz, RMS 0,00844, zéro débordement PortAudio et zéro trame au-dessus du seuil de parole pendant cette prise. Deux avertissements internes de sous-alimentation du filtre ont été observés. |
| Bruit synthétique stationnaire, contrôle du filtre | Sur 100 blocs de 32 ms, RMS d’entrée 0,01957 et RMS de sortie 0,00246 sur le dernier bloc, soit environ 18 dB d’atténuation. |

Le premier essai de décodage du smartphone a rencontré une connexion refusée. Une fois la diffusion revenue, le même chemin MJPEG a fourni les images. Le test d’intégration provoque également une coupure et vérifie la reconnexion sur une source locale contrôlée. La détection de regard repose sur la géométrie apparente de la tête et des iris. Une seule activation observée ne permet pas d’estimer un taux de faux positifs sur un campus.

## Transcription en direct et avec amélioration audio

Chaque ligne ci-dessous est la moyenne non pondérée de trois questions synthétiques, une par langue (français, anglais, arabe). WER et CER sont exprimés en pourcentage. La latence STT commence à l’entrée du décodeur. L’ordre des essais inclut le premier chargement dans certaines moyennes. Les comparaisons direct/filtré d’une même ligne de corpus utilisent le même signal source.

| Modèle CPU INT8 | Scène | Filtre | WER | CER | STT moyen |
| --- | --- | --- | ---: | ---: | ---: |
| base | Calme | Direct | 47,4 % | 13,5 % | 1,48 s |
| base | Calme | DeepFilterNet | 41,8 % | 14,7 % | 1,24 s |
| base | Ventilation + harmoniques | Direct | 36,2 % | 9,8 % | 1,30 s |
| base | Ventilation + harmoniques | DeepFilterNet | 25,9 % | 11,6 % | 1,39 s |
| small | Calme | Direct | 5,6 % | 1,2 % | 3,98 s |
| small | Calme | DeepFilterNet | 16,7 % | 3,7 % | 3,84 s |
| small | Ventilation + harmoniques | Direct | 5,6 % | 1,2 % | 3,93 s |
| small | Ventilation + harmoniques | DeepFilterNet | 5,6 % | 1,2 % | 3,57 s |

Sur les trois questions bruitées avec amélioration, `small` a obtenu respectivement 0 %, 0 % et 16,7 % de WER en français, anglais et arabe. Sur la phrase tunisienne synthétique, il a obtenu 71,4 %. La génération de la phrase mixte par une voix monolingue a épelé des caractères arabes. Cette entrée a été rejetée comme incertaine. Elle ne permet pas de juger la transcription d’un vrai étudiant bilingue. Sur « Quel horaire ? », la transcription synthétique a confondu « horaire » avec « horreur » sans marquer le résultat incertain. Le mode de vérification à l’écran permet de corriger ce type d’erreur avant d’interroger Ollama.

Sur trois fenêtres synthétiques de silence et trois de bruit sans question, aucun tour accepté avec `base`, en capture directe comme filtrée. Les sons de ventilation et de musique sont des signaux générés. Les étudiants réels, la réverbération et un morceau de musique diffusé dans le hall restent à évaluer.

## Synthèse sur CPU

| Backend et langue | Premier rendu | Deuxième rendu | Durée de son au deuxième rendu |
| --- | ---: | ---: | ---: |
| Kokoro INT8, ff_siwis, français | 3,83 s | 2,43 s | 2,11 s |
| Piper, siwis, français | 0,91 s | 0,12 s | 1,97 s |
| Piper, kareem, arabe jordanien | 1,21 s | 0,17 s | 2,16 s |

Le chronomètre de cette sonde mesure la synthèse en mémoire. Le tour complet ci-dessous mesure aussi la lecture sur le périphérique par défaut de Cinnamon. Le niveau de naturalité, la clarté pour des étudiants et la qualité de la prononciation tunisienne nécessitent des auditeurs. Les voix Azure sont intégrées derrière une confirmation explicite du texte. Aucun compte Azure ni échantillon vocal étudiant n’a été utilisé pendant ces essais.

Les mesures ci-dessous décrivent la première version de la borne. Le dialogue actuel dispose d’une évaluation distincte. [Mesures du dialogue corrigé](dialogue.md)

## Mesures de tour complet

Question synthétique injectée en trames de 32 ms en temps réel et sortie réelle par PortAudio. Le premier son correspond au premier bloc écrit sur le périphérique. Le délai acoustique de propagation jusqu’à l’oreille est hors mesure. Le total commence à la dernière trame de parole estimée et inclut l’attente de fin de phrase. La mémoire indiquée est le maximum **du système entier**, échantillonné environ toutes les demi-secondes. Les applications déjà ouvertes influencent ces valeurs.

| Whisper small / LLM / voix | Fin parole → texte | Texte → premier token | Validation de la fiche | Fiche → sortie audio | Total | Pic RAM / VRAM |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen 2B / Kokoro | 5,22 s | 0,18 s | 0,24 s | 7,07 s | 12,70 s | 6,41 Gio / 3000 Mio |
| Qwen 2B / Piper | 5,09 s | 0,16 s | 0,27 s | 0,49 s | 6,01 s | 5,70 Gio / 3000 Mio |
| Qwen 4B / Kokoro | 5,21 s | 0,33 s | 0,25 s | 6,91 s | 12,70 s | 5,76 Gio / 3708 Mio |

Chaque essai a généré son propre signal avec la voix du profil. Les premières transcriptions incluent le chargement de Whisper. Ces observations unitaires décrivent les conditions de la mesure. La voix de synthèse et Qwen étaient déjà en mémoire lors de la réponse. Un essai antérieur avec Whisper base, Qwen 2B à recharger et Piper a donné 3,52 s jusqu’au texte et 9,92 s jusqu’à la sortie audio, avant le passage à la sélection contrainte des fiches.

## Réponses des modèles Ollama avant la correction du dialogue

Les deux modèles ont été installés et exécutés, un seul à la fois, avec un contexte de 2 048 tokens, trois tours d’historique au maximum et un budget de réponse de 160 tokens. La question française porte sur les départements, la question anglaise sur un examen dont l’horaire manque, et la question arabe à nouveau sur les départements.

| Modèle | Quantification installée | Premier token FR au rechargement | Premier token EN / AR à chaud | Fiche prête EN / AR |
| --- | --- | ---: | ---: | ---: |
| qwen3.5:2b | Q8_0 | 5,08 s | 0,12 / 0,15 s | 0,37 / 0,38 s |
| qwen3.5:4b | Q4_K_M | 7,15 s | 0,22 / 0,23 s | 0,47 / 0,47 s |

Lors du tout premier échauffement CUDA, le 2B a dépassé 45 s. Après adaptation du délai, la requête suivante a produit son premier token en 47,34 s. Le premier chargement observé du 4B a pris 23,08 s jusqu’au token. Les chiffres du tableau concernent la version finale avec les bibliothèques déjà initialisées sur le poste.

Les premiers essais en génération libre ont montré trois défauts. Le 2B pouvait répondre en français à une question anglaise ou répéter un département en arabe. Le 4B pouvait ajouter une affirmation institutionnelle absente de la source puis perdre la date dans une relance. La version testée lors de cette première campagne fournit les fiches dans la langue détectée et contraint la sélection à un identifiant documentaire. La voix lit ensuite la fiche retenue. Les deux modèles ont produit la liste exacte des trois départements en français et en arabe. Pour la question anglaise, ils ont sélectionné la fiche signalant l’absence d’horaire d’examen. Le test réel sur deux tours a aussi retrouvé avril 2022 à la relance sur l’arrêté.

## Voix concurrentes

Avec deux voix synthétiques distinctes en fond (voix anglaise et arabe), les six fenêtres sans question, trois en direct et trois avec DeepFilterNet, n’ont fourni aucune transcription acceptée. Un autre essai superposant deux décalages d’une même voix anglaise a produit une transcription acceptée sur trois fenêtres filtrées. Sur les trois questions qui se chevauchent avec les deux voix distinctes, le WER moyen de `base` est monté à 75,1 % en direct et 154,8 % avec le filtre. Le WER peut dépasser 100 % lorsque le décodeur ajoute des mots. Avec le fond atténué simulant davantage de distance, ces valeurs sont descendues à 30,7 % et 47,4 %. Le bouton maintenu et la proximité du microphone sont donc importants en présence de conversations.

## Choix pour l’accueil

Sur cet ASUS, **Whisper small INT8 sur CPU, Qwen 2B sur GPU et Piper** offrent le meilleur compromis mesuré pour un accueil réactif et multilingue. Pour donner la priorité à l’écoute de la voix française Kokoro, conserver **ff_siwis**, puis comparer les deux voix avec les étudiants. Le passage de Piper à Kokoro a ajouté environ 6,6 s entre la disponibilité de la fiche et le premier bloc audio sur les tours 2B avec Whisper small. Le modèle 4B a aussi exécuté tout le circuit sur les 6 Gio de VRAM.

Le réglage initial de l’application conserve Kokoro en français et la sélection automatique des modèles. En automatique, le 4B est envisagé à partir de 4 400 Mio de VRAM disponible ou réutilisable et de 2,8 Gio de RAM disponible. Le 2B est privilégié lorsque la mémoire est plus contrainte. La sélection tient aussi compte des délais à chaud et des changements de langue observés. Le profil STT peut descendre à base sous pression mémoire. Les seuils sont des marges d’exploitation, pas une mesure de capacité maximale.

## Validation et limites

Les **25 tests automatisés** ont été exécutés ensemble avec les options matérielles activées. Ils couvrent la stabilité du regard, sa perte, plusieurs visages, la rotation, les coupures MJPEG et la reconnexion, les tours et les pauses, les erreurs de micro et d’Ollama, le choix CPU sous faible mémoire, la confidentialité du feedback et l’arrêt du worker depuis le bouton de l’interface. Le test matériel de l’interface a observé successivement la salutation, l’état d’écoute et l’ouverture du microphone réel, puis a terminé l’échange. La sélection sous faible mémoire et le serveur indisponible sont testés par injection. Aucun test n’a provoqué de saturation volontaire de la RAM du bureau.

Les essais STT et TTS sur données synthétiques ont utilisé des fichiers de modèles locaux. L’accès Internet du poste n’a pas été coupé au niveau système. Une démonstration en amphithéâtre, des questions naturelles de plusieurs étudiants tunisiens, une évaluation subjective des voix et une mesure acoustique avec un micro étalon restent des validations de terrain. Aucun résultat de ces essais humains n’est présumé. Le bouton de correction peut être activé pour les sessions où la transcription doit être validée avant toute réponse.
