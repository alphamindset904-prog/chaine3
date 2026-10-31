#!/usr/bin/env python3
"""Chaîne YouTube n°3 : vidéo d'animation motivationnelle quotidienne (≈ 2 min 30).

Thème du jour -> scénario en scènes (Gemini / GitHub Models, gratuits) -> voix off (edge-tts)
-> animation dessinée par le programme (Pillow + ffmpeg) -> miniature -> upload YouTube.
"""
import asyncio
import json
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import requests
from PIL import Image, ImageDraw

import anim

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "work"
OUT = ROOT / "out"
W, H, FPS = anim.W, anim.H, anim.FPS

def log(*a):
    print(*a, flush=True)


def ff(*args):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *map(str, args)], check=True)


def duration(path):
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]
    )
    return float(out.decode().strip())


def to_speech(text):
    t = re.sub(r"N°\s*(\d+)", r"Numéro \1", text)
    return t.replace("«", "").replace("»", "").replace('"', "")



GH_URL = "https://models.github.ai/inference/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"


def _extract_json(txt):
    txt = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", txt.strip())
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", txt, re.S)
        if not m:
            raise
        return json.loads(m.group(0))


def _providers(cfg):
    """Liste ordonnée des façons d'appeler un modèle d'écriture (gratuites)."""
    out = []
    gem = os.getenv("GEMINI_API_KEY")
    if gem:
        h = {"Authorization": f"Bearer {gem}", "Content-Type": "application/json"}
        for m in cfg.get("gemini_models", ["gemini-flash-latest", "gemini-flash-lite-latest"]):
            out.append(("Gemini", GEMINI_URL, h, m))
    tok = os.getenv("MODELS_TOKEN") or os.getenv("GITHUB_TOKEN")
    if tok:
        simple = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}
        full = {**simple, "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        for m in cfg["llm_models"]:
            out.append(("GitHub Models (simple)", GH_URL, simple, m))
            out.append(("GitHub Models (complet)", GH_URL, full, m))
    return out


def llm_json(system, user, cfg):
    providers = _providers(cfg)
    if not providers:
        raise RuntimeError("Aucun accès à un modèle d'écriture (GITHUB_TOKEN et GEMINI_API_KEY absents).")
    last = None
    for pi, (label, url, headers, model) in enumerate(providers):
        is_gemini = label == "Gemini"
        max_tok = 8192 if is_gemini else 3500
        effort = is_gemini  # limite la « réflexion » interne qui consomme des jetons
        for attempt in range(4):
            payload = {
                "model": model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "temperature": 0.8,
                "max_tokens": max_tok,
            }
            if effort:
                payload["reasoning_effort"] = "low"
            try:
                r = requests.post(url, headers=headers, json=payload, timeout=240)
            except requests.RequestException as e:
                last = f"{label} {model} : erreur réseau {str(e)[:150]}"
                log(last)
                break
            if r.status_code == 429 and pi < len(providers) - 1:
                log(f"{label} {model} : limite atteinte, essai du modèle suivant")
                break
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", "30") or 30)
                log(f"{label} {model} : limite atteinte, pause {min(wait, 90)}s")
                time.sleep(min(wait, 90))
                continue
            if r.status_code >= 500:
                last = f"{label} {model} : HTTP {r.status_code}"
                log(last)
                time.sleep(8)
                continue
            if r.status_code == 400 and effort:
                log(f"{label} {model} : réglage de réflexion refusé, nouvel essai sans")
                effort = False
                continue
            try:
                if r.status_code != 200:
                    raise ValueError("statut inattendu")
                choice = r.json()["choices"][0]
                txt = choice["message"]["content"]
                if choice.get("finish_reason") == "length":
                    max_tok = min(max_tok * 2, 32000)
                    log(f"{label} {model} : réponse coupée, nouvel essai avec {max_tok} jetons")
                    last = "réponse coupée (trop longue)"
                    continue
                data = _extract_json(txt)
                log(f"Script écrit via {label} ({model})")
                return data
            except Exception:  # noqa: BLE001
                last = (f"{label} {model} : HTTP {r.status_code} {r.headers.get('content-type', '')} "
                        f"{r.text[:250]!r}")
                log(last)
                break
    raise RuntimeError(f"Génération du script impossible. Dernière erreur : {last}")



SITUATIONS = [
    "un étudiant qui remet tout au lendemain",
    "un salarié épuisé par sa routine",
    "un jeune entrepreneur qui doute de lui",
    "un sportif qui a perdu sa motivation",
    "un parent qui n'a plus de temps pour lui",
    "un artiste bloqué devant sa page blanche",
    "quelqu'un qui veut changer de vie mais n'ose pas",
    "un adolescent qui se compare aux autres",
]

SYSTEM_PROMPT = """Tu es scénariste de vidéos d'animation motivationnelles en français pour YouTube.
Le héros est un petit personnage anonyme (« toi »). Son ombre rouge est la voix du doute et de la facilité.
Style : narration à la 2e personne (tutoiement), phrases courtes, ton sobre, intense, sans cliché creux.
RÈGLES : n'invente aucune statistique, étude scientifique ou citation de personne réelle. Pas de promesses
irréalistes. Pas de conseil médical ou financier précis. Tu réponds uniquement par un objet JSON valide."""

USER_PROMPT = """Écris le scénario d'une vidéo d'animation de 2 min 30 sur le thème : « {theme} » (angle : {angle}).
Le personnage est, par exemple, {situation} (reste universel, sans nom).

TRAME (adapte-la, ne la recopie pas mot à mot) :
1. Ouverture sombre : le personnage est bloqué (pose "sleep", "sit" ou "hunch"), l'ombre le rabaisse (texte rouge).
2. Prise de conscience : ce n'est pas ce qu'il EST, c'est ce qu'il RÉPÈTE.
3. Il commence petit : montage jour par jour (champ "day" croissant : 1, 3, 17, 47, 90...), "band": true à partir de là.
4. L'ombre revient avec le doute ; il continue malgré tout.
5. Sommet / lever de soleil (pose "summit"), puis dernière scène = carte titre (pose "title").

CONTRAINTES :
- 14 à 16 scènes. Narration totale : 360 à 420 mots, c'est impératif (chaque scène : 2 à 3 phrases, 20 à 35 mots).
- Varie les poses : au moins 6 poses différentes parmi sleep, sit, hunch, stand, walk, run, punch, climb, work, summit.
- "pose" autorisées : sleep, sit, hunch, stand, walk, run, punch, climb, work, summit, title.
  (Le décor est choisi automatiquement pour sleep/sit/work/punch/climb/summit/run/walk. Pour stand et hunch,
  tu peux ajouter "bg" : void, bedroom, street, mountain ou mirror.)
- "shadow" : "none", "right" (l'ombre apparaît à droite) ou "mirror" (seulement avec pose "stand" et bg "mirror").
- "text" : texte affiché à l'écran, 2 à 9 mots, percutant (peut être vide). "text_style" : white, red ou big.
- Dernière scène : {{"pose": "title", "title_word": "UN MOT EN MAJUSCULES", "tagline": "...", "punchline": "...", "narration": "..."}}.
- Pas d'emoji. Aucune mention de chaîne YouTube dans les scènes.

FORMAT JSON EXACT :
{{"title": "titre accrocheur (max 70 caractères)", "thumb_text": "3 à 5 mots percutants", "description": "2 à 3 phrases", "tags": ["10 à 15 mots-clés"],
 "scenes": [{{"pose": "sleep", "bg": "void", "shadow": "right", "day": null, "band": false, "text": "Tu es paresseux.", "text_style": "red", "narration": "..."}}]}}"""


def normalize(data):
    scenes = []
    for sc in data.get("scenes", []):
        narr = str(sc.get("narration", "")).strip()
        pose = str(sc.get("pose", "stand")).lower().strip()
        if not narr:
            continue
        if pose not in anim.POSES:
            pose = "stand"
        shadow = str(sc.get("shadow", "none")).lower()
        if shadow not in ("none", "right", "mirror"):
            shadow = "none"
        try:
            day = int(sc.get("day")) if sc.get("day") not in (None, "", 0) else None
        except (TypeError, ValueError):
            day = None
        style = str(sc.get("text_style", "white")).lower()
        scenes.append({
            "pose": pose, "bg": str(sc.get("bg", "void")).lower(), "shadow": shadow, "day": day,
            "band": bool(sc.get("band")), "text": str(sc.get("text", "") or "").strip()[:90],
            "text_style": style if style in ("white", "red", "big") else "white", "narration": narr,
            "title_word": str(sc.get("title_word", "") or "").upper()[:24],
            "tagline": str(sc.get("tagline", "") or ""), "punchline": str(sc.get("punchline", "") or ""),
        })
    for s in scenes[:-1]:
        if s["pose"] == "title":
            s["pose"] = "stand"
    if scenes and scenes[-1]["pose"] != "title":
        scenes.append({"pose": "title", "bg": "void", "shadow": "none", "day": None, "band": False, "text": "",
                       "text_style": "white", "narration": str(data.get("closing", "") or "Jour un, ou un jour. Tu décides."),
                       "title_word": str(data.get("title_word", "") or "DISCIPLINE").upper()[:24],
                       "tagline": "", "punchline": ""})
    last = scenes[-1] if scenes else None
    if last and not last["title_word"]:
        last["title_word"] = str(data.get("title_word", "") or "À TOI DE JOUER").upper()[:24]
    return scenes


def generate_script(theme, angle, index, cfg):
    situation = SITUATIONS[index % len(SITUATIONS)]
    base = USER_PROMPT.format(theme=theme, angle=angle, situation=situation)
    feedback, best = "", None
    for attempt in range(4):
        data = llm_json(SYSTEM_PROMPT, base + feedback, cfg)
        scenes = normalize(data)
        words = sum(len(s["narration"].split()) for s in scenes)
        log(f"Script : {len(scenes)} scènes, {words} mots")
        if len(scenes) >= 8 and data.get("title"):
            data["scenes"] = scenes
            if best is None or abs(words - 360) < abs(best[1] - 360):
                best = (data, words)
            if 300 <= words <= 470:
                break
            feedback = (f"\n\nATTENTION : ta version précédente ne faisait que {words} mots de narration. "
                        "Il en faut entre 360 et 420 : développe chaque scène (3 phrases de 20 à 35 mots).")
    if best is None:
        raise RuntimeError("Script inutilisable après 4 essais.")
    return best[0]


def make_thumbnail(text, dest, cfg):
    sc = {"pose": "stand", "bg": "void", "shadow": "right", "band": True, "day": None, "text": "", "text_style": "white"}
    img = anim.SceneRenderer(sc, 6, cfg).frame(2.0)
    d = ImageDraw.Draw(img)
    text = text.upper()
    for size in range(130, 50, -4):
        f = anim.font("bold", size, cfg.get("font_bold", ""))
        lines = anim._wrap(d, text, f, 780)
        lh = int(size * 1.15)
        if len(lines) * lh <= 310 and all(d.textlength(l, font=f) <= 780 for l in lines):
            break
    y = 36
    for i, ln in enumerate(lines):
        d.text((46, y), ln, font=f, fill=(255, 236, 0) if i % 2 == 0 else (255, 255, 255),
               stroke_width=6, stroke_fill=(0, 0, 0))
        y += lh
    img.save(dest, "JPEG", quality=88)


def build_video(scenes, dest, cfg):
    gap = float(cfg["pause_between_blocks"])
    segs, wavs = [], []
    for i, s in enumerate(scenes):
        mp3 = WORK / f"a{i}.mp3"
        synth(s["narration"], mp3, cfg)
        frames = math.ceil((duration(mp3) + gap) * FPS)
        total = frames / FPS
        wav = WORK / f"a{i}.wav"
        ff("-i", mp3, "-af", f"apad=whole_dur={total:.4f}", "-t", f"{total:.4f}", "-ar", 44100, "-ac", 2, wav)
        seg = WORK / f"v{i}.mp4"
        rend = anim.SceneRenderer(s, total, cfg)
        proc = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
             "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
             "-pix_fmt", "yuv420p", str(seg)], stdin=subprocess.PIPE)
        for n in range(frames):
            proc.stdin.write(rend.frame(n / FPS).tobytes())
        proc.stdin.close()
        if proc.wait() != 0:
            raise RuntimeError(f"ffmpeg a échoué sur la scène {i + 1}")
        segs.append(seg)
        wavs.append(wav)
        log(f"Scène {i + 1}/{len(scenes)} prête ({total:.1f}s, {s['pose']})")

    def concat(files, out):
        lst = WORK / (out.stem + ".txt")
        lst.write_text("".join(f"file '{f.resolve()}'\n" for f in files))
        ff("-f", "concat", "-safe", 0, "-i", lst, "-c", "copy", out)

    vid, aud = WORK / "video_only.mp4", WORK / "audio_all.wav"
    concat(segs, vid)
    concat(wavs, aud)
    ff("-i", vid, "-i", aud, "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", dest)
    log(f"Vidéo finale : {duration(dest):.1f}s")


def synth(text, path, cfg):
    speech = to_speech(text)
    last = None
    for attempt in range(3):
        try:
            import edge_tts
            asyncio.run(edge_tts.Communicate(speech, cfg["voice"], rate=cfg["voice_rate"]).save(str(path)))
            if path.exists() and path.stat().st_size > 1000:
                return
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(4 * (attempt + 1))
    log("edge-tts indisponible, repli sur gTTS :", last)
    from gtts import gTTS
    gTTS(speech, lang="fr").save(str(path))


# ----------------------------------------------------------------------------
# YouTube
# ----------------------------------------------------------------------------
def upload(video, thumb, title, description, tags, privacy, cfg):
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    creds = Credentials(
        None,
        refresh_token=os.environ["YT3_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT3_CLIENT_ID"],
        client_secret=os.environ["YT3_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:4900],
            "tags": tags,
            "categoryId": str(cfg.get("category_id", "27")),
            "defaultLanguage": "fr",
            "defaultAudioLanguage": "fr",
        },
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }
    req = yt.videos().insert(
        part="snippet,status", body=body,
        media_body=MediaFileUpload(str(video), chunksize=8 * 1024 * 1024, resumable=True),
    )
    resp, retries = None, 0
    while resp is None:
        try:
            status, resp = req.next_chunk()
            if status:
                log(f"Upload {int(status.progress() * 100)}%")
        except HttpError as e:
            if e.resp.status in (500, 502, 503, 504) and retries < 6:
                retries += 1
                time.sleep(5 * retries)
            else:
                raise
    vid = resp["id"]
    log("Vidéo publiée :", f"https://youtu.be/{vid}", f"({privacy})")
    try:
        yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(thumb))).execute()
    except Exception as e:  # noqa: BLE001
        log("Miniature non appliquée (chaîne non vérifiée ?) :", e)
    return vid



# ----------------------------------------------------------------------------
# Programme principal
# ----------------------------------------------------------------------------
def main():
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    dry = os.getenv("DRY_RUN", "").lower() == "true"
    privacy = os.getenv("PRIVACY") or "public"

    topics = [l.strip() for l in (ROOT / "topics.txt").read_text(encoding="utf-8").splitlines()
              if l.strip() and not l.startswith("#")]
    pub_file = ROOT / "published.txt"
    done = [l.strip() for l in pub_file.read_text(encoding="utf-8").splitlines() if l.strip()] if pub_file.exists() else []
    todo = [t for t in topics if t not in done]
    line = (os.getenv("TOPIC_OVERRIDE") or "").strip() or (todo[0] if todo else "")
    if not line:
        log("Tous les thèmes sont publiés. Ajoute des lignes dans topics.txt.")
        return
    theme, _, angle = [p.strip() for p in line.partition("|")]
    angle = angle or "le combat contre soi-même"
    log(f"Thème : {theme} | angle : {angle} (vidéo n°{len(done) + 1}) | dry_run={dry} | visibilité={privacy}")

    for d in (WORK, OUT):
        d.mkdir(exist_ok=True)
        for f in d.glob("*"):
            f.unlink()

    data = generate_script(theme, angle, len(done), cfg)
    build_video(data["scenes"], OUT / "video.mp4", cfg)
    make_thumbnail(data.get("thumb_text") or data["title"], OUT / "thumbnail.jpg", cfg)

    tags = [str(t)[:30] for t in data.get("tags", [])][:15]
    desc = data.get("description", "").strip() + "\n\n" + " ".join(cfg.get("hashtags", []))
    desc += "\n\nVidéo d'animation réalisée avec l'aide d'outils d'IA (écriture, voix)."
    (OUT / "meta.json").write_text(json.dumps({"title": data["title"], "description": desc, "tags": tags, "theme": line},
                                              ensure_ascii=False, indent=2), encoding="utf-8")
    if dry:
        log("Mode test : rien n'est publié. Récupère la vidéo dans les « Artifacts » du run.")
        return
    upload(OUT / "video.mp4", OUT / "thumbnail.jpg", data["title"], desc, tags, privacy, cfg)
    with pub_file.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    log("Terminé.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        log("ERREUR :", exc)
        sys.exit(1)
