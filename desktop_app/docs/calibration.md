# Calibrer la borne

## Caméra du smartphone

1. Relier le téléphone et le PC au même réseau. Démarrer la diffusion dans l’application IP Camera et relever l’URL du flux. Sur l’appareil utilisé ici, la racine HTTP est une page de contrôle et le flux MJPEG se trouve sous `/video`.
2. Placer le téléphone à hauteur des yeux, orienté vers un seul emplacement d’accueil. Stabiliser le support, éclairer le visage de face et vérifier le cadrage dans l’aperçu. Le cadre doit entourer le visage même quand la personne détourne les yeux.
3. Faire regarder l’objectif dix fois pendant six secondes à plusieurs distances, avec et sans lunettes. Relever le temps jusqu’à l’invitation et les activations manquées. Refaire la série en regardant de côté. La progression se fige lors d’une brève perte, puis repart de zéro après 350 ms. Plusieurs visages ou un changement brusque de position interrompent la preuve de stabilité.
4. Ajuster `ISIMM_YAW` (écart horizontal du nez, en largeur de visage), `ISIMM_PITCH` (position verticale nominale du nez dans le visage) et `ISIMM_IRIS` (écart horizontal de l’iris en largeur d’œil). Diminuer les tolérances horizontales pour écarter les regards latéraux. Modifier une valeur à la fois et rejouer les séries.
5. Couper le Wi-Fi du téléphone puis le rétablir. Vérifier le message de reconnexion, la reprise de l’aperçu et la remise à zéro de la progression. L’activation manuelle reste accessible.

Le repérage des iris et de la tête donne une approximation de l’attention visuelle. Il n’associe aucune identité au visage ni à la voix. La latence du téléphone s’ajoute aux cinq secondes observées par le PC. La pause entre sessions vaut douze secondes par défaut.

## Microphone et bruit

Dans les réglages de Cinnamon, choisir l’entrée physique et contrôler son niveau. L’ASUS expose notamment un micro numérique et un micro stéréo. Le nom et l’index PortAudio peuvent différer des identifiants PipeWire. Inspecter les entrées avec `bash scripts/diagnostic.sh`. L’entrée doit accepter la capture mono à 48 kHz via PortAudio ou le périphérique par défaut de PipeWire. Choisir une sortie réellement audible dans Cinnamon.

Placer le micro près de l’étudiant et éloigner les haut-parleurs. Pendant un tour d’essai, vérifier **Micro ouvert**, la jauge et l’indication de parole. Des pics écrêtés imposent de diminuer le gain d’entrée. Un signal très faible impose de rapprocher le micro ou de relever ce gain. Le contrôle du volume dans l’application agit sur la sortie.

Les blocs de 1 536 échantillons traversent DeepFilterNet avec une limite d’atténuation de 18 dB, puis un filtre anti-repliement avec décimation par trois. Silero consomme 512 échantillons à 16 kHz et conserve son contexte pendant le tour. Trois blocs consécutifs au-dessus du seuil déclenchent la parole. Le pré-roll préserve les débuts de mots. Une pause d’environ 0,90 s termine la question. La fenêtre initiale dure neuf secondes et la parole est bornée à vingt secondes. Le bouton maintenu borne aussi la capture au relâchement.

Comparer `ISIMM_DENOISE=true` et `false` au même placement. Régler `ISIMM_VAD` autour de 0,62. Monter le seuil réduit certains départs parasites mais peut écarter une voix basse. Un environnement avec plusieurs voix intelligibles requiert un essai avec le bouton maintenu, puis avec une entrée directionnelle. Le filtre atténue surtout le bruit acoustique. Des conversations voisines peuvent constituer une parole valide pour le VAD.

## Protocole reproductible

Le corpus de `tests/corpus.json` contient des questions françaises, anglaises, arabes, tunisiennes et mixtes. Le banc génère les phrases en mémoire. Pour une évaluation humaine, obtenir des enregistrements de référence consentis, les conserver hors du projet et les fournir avec `--wav-dir`. Nommer les fichiers selon les identifiants du corpus, par exemple `fr.wav`, `ar.wav` ou `mix.wav`. L’application d’accueil n’enregistre aucun fichier audio.

```bash
.venv/bin/python -m scripts.evaluate --model base --ids fr en ar tn mix short long \
  --scenes quiet fan_music two_background overlap near_far pause noise_only silence
.venv/bin/python -m scripts.evaluate --model small --ids fr en ar --scenes quiet fan_music
.venv/bin/python -m scripts.evaluate --model base --ids tn mix --wav-dir /chemin/vers/references
```

| Condition | Observation à consigner |
| --- | --- |
| Étudiant seul | WER, CER, langue estimée, répétitions demandées. |
| Ventilateur et musique | Mêmes phrases avec et sans amélioration. Le banc utilise un bruit ensemencé et deux harmoniques. Ajouter de la vraie musique pour le test sur site. |
| Deux étudiants au fond | Compter les tours acceptés lorsqu’aucune question ne s’adresse à l’accueil. Tester aussi la veille, où le micro est fermé. |
| Voix simultanées et voix de proximité | Comparer question acceptée, texte et source du son. Refaire avec le bouton maintenu. |
| Silence, phrases courtes, longues et interrompues | Examiner les mots coupés, les délais d’endpoint et les rejets injustifiés. |
| Haut-parleur actif et micro physiquement connecté | Vérifier l’indicateur **Micro fermé** pendant toute lecture, y compris l’invitation. Tester **Terminer** en pleine réponse. |
| Perte d’un périphérique ou du serveur | Débrancher l’entrée, couper le flux, arrêter le serveur local et vérifier l’arrêt possible ainsi que le prochain lancement. |

WER = nombre minimal d’insertions, substitutions et suppressions de mots divisé par le nombre de mots de référence. CER applique la même formule aux caractères. La normalisation harmonise la casse, les accents et la ponctuation. Les erreurs se mesurent aussi sur les phrases rejetées. `false_turn` compte un fond ou un silence transcrit et accepté pendant une fenêtre ouverte.

Pour le TTS, faire écouter à l’aveugle les mêmes phrases à plusieurs étudiants. Noter naturalité, clarté et prononciation de « ISIMM », « scolarité » et « mathématiques » sur une échelle de 1 à 5. Consigner séparément le temps de génération. Pour l’arabe, juger distinctement intelligibilité et adéquation au dialecte tunisien. Aucune note subjective n’est attribuée par le logiciel.

En mode **Paramètres → Transcription**, la borne présente chaque question à l’écran pendant 23 secondes au maximum. L’étudiant peut la valider, la modifier ou la répéter. Sur le smartphone testé, la mesure du regard utilise désormais les axes du visage et le rapport largeur/hauteur de l’image. Le seuil de proximité est réglable avec `ISIMM_MIN_FACE`, exprimé en fraction du petit côté de l’image.
