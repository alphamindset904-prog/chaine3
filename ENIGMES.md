# Format « Énigmes » (Shorts paradoxes / logique)

Nouveau format dans le même dépôt, même chaîne (secrets `YT3_*`), même clé d'écriture (`GEMINI_API_KEY` / `GITHUB_TOKEN`).

## Fichiers ajoutés (rien d'existant n'est modifié)
- `enigmes.py` : moteur d'animation (25 pictogrammes roses sur fond sombre, apparition synchronisée sur les mots).
- `enigmes_pipeline.py` : script (LLM) -> vérification d'exactitude (2e appel LLM) -> voix -> animation -> sons -> YouTube.
- `topics_enigmes.txt` : 365 paradoxes/énigmes réels, un par jour pendant un an, dans l'ordre. `enigmes_published.txt` : historique.
- `.github/workflows/publish-enigmes.yml` : tous les jours à 17:00 UTC (modifie la ligne `cron`).

## Installation
1. Copie ces fichiers dans le dépôt (en gardant `.github/workflows/`), commit, push.
2. Actions -> « Publier l'énigme » -> Run workflow, `dry_run` coché. Télécharge l'artifact `enigme-test`.
3. Si la vidéo te plaît : relance avec `dry_run` décoché et visibilité `unlisted`, puis laisse tourner en automatique.

## Réglages (config.json, facultatifs)
`voice_rate_enigmes` (vitesse de voix, ex. "+5%"), `enigmes_verify` (false pour couper la vérification),
`hashtags_enigmes`.

## Test local sans clé
`ENIGMES_NO_TTS=1 python enigmes_pipeline.py --demo` fabrique un Short de démonstration (Monty Hall, voix muette).
