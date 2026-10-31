# Chaîne 3 — installation (animation motivationnelle, 1 vidéo par jour)

## 1. Nouveau dépôt GitHub (privé)
Crée un dépôt, par exemple `chaine3`, et envoie ces fichiers : `pipeline.py`, `anim.py`, `config.json`,
`topics.txt`, `requirements.txt`, `SETUP.md`, `published.txt`, `.gitignore`.
Puis crée à la main `.github/workflows/publish.yml` (colle le contenu du fichier `publish.yml`).
Réglage obligatoire : **Settings → Actions → General → Workflow permissions → Read and write permissions**.

## 2. Jeton YouTube de la chaîne 3 (avec l'AUTRE adresse mail)
Dans OAuth Playground (`developers.google.com/oauthplayground`), roue dentée ⚙ → « Use your own OAuth credentials »
(Client ID / Secret habituels), scope `https://www.googleapis.com/auth/youtube.upload`, puis **connecte-toi avec
la nouvelle adresse mail** et choisis la chaîne 3. « Exchange authorization code for tokens » → copie le Refresh token.
Si Google refuse la nouvelle adresse : dans Google Cloud → Google Auth Platform → Audience, passe l'application
en « En production » (ou ajoute cette adresse comme utilisateur de test).

## 3. Secrets GitHub (Settings → Secrets and variables → Actions)
`YT3_CLIENT_ID`, `YT3_CLIENT_SECRET`, `YT3_REFRESH_TOKEN`, `GEMINI_API_KEY` (la même clé gratuite que la chaîne 2).

## 4. Test
Actions → **Publier la vidéo du jour** → Run workflow (laisse `dry_run` coché). Durée : environ 8 à 12 min.
Télécharge l'artifact `video-test`, regarde la vidéo. Puis relance avec `dry_run` décoché et `unlisted`.

## Personnaliser
`config.json` : nom de chaîne affiché en filigrane (`channel_name`), voix (`fr-FR-DeniseNeural` pour une voix féminine).
`topics.txt` : 365 thèmes, un par jour. Planning : ligne `cron` de `publish.yml` (heure en UTC).
