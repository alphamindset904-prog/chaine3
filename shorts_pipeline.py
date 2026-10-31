#!/usr/bin/env python3
"""Shorts verticaux « Jour Un » (≈ 50 s) : une métaphore visuelle par séquence, un Short tous les 2 jours."""
import datetime
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

import pipeline as p
import shorts
from pipeline import log

ROOT = Path(__file__).resolve().parent
WV, HV, FPS = shorts.WV, shorts.HV, shorts.FPS

SYSTEM_PROMPT = """Tu es scénariste de Shorts motivationnels visuels en français pour YouTube.
Chaque Short est une suite de métaphores animées simples, avec peu de texte, un ton sobre, intense et bienveillant,
à la 2e personne (tutoiement). RÈGLES : n'invente aucune statistique, étude ou citation de personne réelle ;
pas de promesses irréalistes ; pas de conseil médical ou financier précis. Tu réponds uniquement par un objet JSON valide."""

USER_PROMPT = """Écris le scénario d'un Short vertical d'environ 50 secondes sur le thème : « {theme} » (forme : {angle}).
Le Short est une suite de 6 à 8 séquences. Chaque séquence = 1 métaphore visuelle animée + 2 courtes lignes de texte
(a puis b) + 1 phrase lue à voix haute.

Métaphores disponibles ("kind") :
- chart : courbe rouge qui chute puis remonte en vert (a = situation difficile, b = renversement).
- traffic : feu rouge puis vert, voiture qui démarre (patience, bon moment).
- sliders : 6 curseurs étiquetés, un monte à fond ("labels" : 6 mots courts ; "highlight" : index 0 à 5 du curseur qui monte).
- acrostic : un mot épelé lettre par lettre ("word" : 5 à 10 lettres MAJUSCULES sans accent ; "items" : un mot français par lettre, commençant par cette lettre).
- bars : barres qui grandissent (progrès, régularité).
- battery : batterie qui se vide puis se recharge (énergie, repos).
- hourglass : sablier (le temps qui passe).
- counter : compteur qui monte ("from" et "to" : entiers, par ex. 1 et 365).
- text : texte seul (réservé à la dernière séquence).

CONTRAINTES :
- Narration totale : 100 à 125 mots ; une phrase courte par séquence (10 à 22 mots).
- "a" : 2 à 6 mots (affiché en blanc). "b" : 2 à 8 mots (affiché en lumineux) = la chute ou le renversement de "a".
- Pas deux séquences consécutives avec le même kind ; au moins 4 kinds différents.
- Première séquence : accroche immédiate. Dernière séquence : kind "text", a = un rappel, b = une invitation à revenir demain.
- Le texte doit se comprendre sans le son. Pas d'emoji.

FORMAT JSON EXACT :
{{"title": "titre accrocheur (max 60 caractères)", "description": "1 à 2 phrases", "tags": ["8 à 12 mots-clés"],
 "beats": [{{"kind": "chart", "a": "...", "b": "...", "narration": "..."}}]}}"""

ANGLES_HINT = ""


def normalize(data):
    beats = []
    prev = None
    for b in data.get("beats", []):
        kind = str(b.get("kind", "text")).lower().strip()
        narr = str(b.get("narration", "")).strip()
        if kind not in shorts.KINDS or not narr:
            continue
        par = {"kind": kind, "a": str(b.get("a", "") or "").strip()[:60], "b": str(b.get("b", "") or "").strip()[:70],
               "narration": narr, "seed": len(beats) + 3}
        if kind == "sliders":
            labels = [str(x)[:14] for x in (b.get("labels") or [])][:6]
            labels += ["Joie", "Calme", "Confiance", "Respect", "Patience", "Ego"][len(labels):]
            try:
                hi = int(b.get("highlight", 5))
            except (TypeError, ValueError):
                hi = 5
            par.update({"labels": labels, "highlight": max(0, min(5, hi))})
        elif kind == "acrostic":
            word = re.sub(r"[^A-Z]", "", str(b.get("word", "")).upper())[:10] or "ACTION"
            items = [str(x).strip() for x in (b.get("items") or [])]
            items = [(items[i] if i < len(items) and items[i] else word[i]) for i in range(len(word))]
            par.update({"word": word, "items": items})
        elif kind == "counter":
            try:
                a, c = int(b.get("from", 1)), int(b.get("to", 365))
            except (TypeError, ValueError):
                a, c = 1, 365
            par.update({"from": a, "to": c if c != a else a + 1})
        if kind == prev and kind != "text":
            continue
        prev = kind
        beats.append(par)
    if beats and beats[-1]["kind"] != "text":
        beats.append({"kind": "text", "a": "Reviens demain.", "b": "Un jour de plus.", "seed": 1,
                      "narration": "Reviens demain. Un jour de plus, un pas de plus."})
    for bt in beats[:-1]:
        if bt["kind"] == "text":
            bt["kind"] = "chart"
    return beats


def generate(theme, angle, cfg):
    best = None
    for attempt in range(3):
        data = p.llm_json(SYSTEM_PROMPT, USER_PROMPT.format(theme=theme, angle=angle), cfg)
        beats = normalize(data)
        words = sum(len(b["narration"].split()) for b in beats)
        log(f"Short : {len(beats)} séquences, {words} mots")
        if len(beats) >= 5 and data.get("title"):
            data["beats"] = beats
            if best is None or abs(words - 112) < abs(best[1] - 112):
                best = (data, words)
            if 85 <= words <= 140:
                break
    if best is None:
        raise RuntimeError("Scénario inutilisable après 3 essais.")
    return best[0]


def make_ambient(dur, dest):
    p.ff("-f", "lavfi", "-i", f"sine=frequency=110:duration={dur:.2f}",
         "-f", "lavfi", "-i", f"sine=frequency=165:duration={dur:.2f}",
         "-f", "lavfi", "-i", f"sine=frequency=220.5:duration={dur:.2f}",
         "-filter_complex",
         f"[0][1][2]amix=inputs=3:duration=first,tremolo=f=0.2:d=0.6,lowpass=f=500,"
         f"afade=t=in:d=2,afade=t=out:st={max(dur - 2.5, 0):.2f}:d=2.5[a]",
         "-map", "[a]", "-ar", 44100, "-ac", 2, dest)


def build(beats, pal_idx, dest, cfg):
    gap = float(cfg.get("short_gap", 0.45))
    segs, wavs = [], []
    for i, b in enumerate(beats):
        mp3 = p.WORK / f"a{i}.mp3"
        scfg = dict(cfg)
        scfg["voice_rate"] = cfg.get("voice_rate_short", cfg.get("voice_rate", "+0%"))
        p.synth(b["narration"], mp3, scfg)
        frames = math.ceil(max(p.duration(mp3) + gap, 4.2) * FPS)
        total = frames / FPS
        wav = p.WORK / f"a{i}.wav"
        p.ff("-i", mp3, "-af", f"apad=whole_dur={total:.4f}", "-t", f"{total:.4f}", "-ar", 44100, "-ac", 2, wav)
        seg = p.WORK / f"v{i}.mp4"
        rend = shorts.BeatRenderer(b, total, pal_idx, cfg, last=(i == len(beats) - 1))
        proc = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{WV}x{HV}",
             "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
             "-pix_fmt", "yuv420p", str(seg)], stdin=subprocess.PIPE)
        for n in range(frames):
            proc.stdin.write(rend.frame(n / FPS).tobytes())
        proc.stdin.close()
        if proc.wait() != 0:
            raise RuntimeError(f"ffmpeg a échoué sur la séquence {i + 1}")
        segs.append(seg)
        wavs.append(wav)
        log(f"Séquence {i + 1}/{len(beats)} prête ({total:.1f}s, {b['kind']})")

    def concat(files, out):
        lst = p.WORK / (out.stem + ".txt")
        lst.write_text("".join(f"file '{f.resolve()}'\n" for f in files))
        p.ff("-f", "concat", "-safe", 0, "-i", lst, "-c", "copy", out)

    vid, voice, amb = p.WORK / "video_only.mp4", p.WORK / "voice_all.wav", p.WORK / "ambient.wav"
    concat(segs, vid)
    concat(wavs, voice)
    make_ambient(p.duration(voice), amb)
    p.ff("-i", vid, "-i", voice, "-i", amb, "-filter_complex",
         "[1:a]volume=1.0[v];[2:a]volume=0.22[m];[v][m]amix=inputs=2:duration=first:dropout_transition=0,volume=1.9[a]",
         "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest",
         "-movflags", "+faststart", dest)
    log(f"Short final : {p.duration(dest):.1f}s")


def main():
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    dry = os.getenv("DRY_RUN", "").lower() == "true"
    privacy = os.getenv("PRIVACY") or "public"

    topics = [l.strip() for l in (ROOT / "topics_shorts.txt").read_text(encoding="utf-8").splitlines()
              if l.strip() and not l.startswith("#")]
    pub_file = ROOT / "shorts_published.txt"
    rows = [l.strip() for l in pub_file.read_text(encoding="utf-8").splitlines() if l.strip()] if pub_file.exists() else []
    done = [r.split(" | ", 1)[1] if " | " in r else r for r in rows]
    todo = [t for t in topics if t not in done]
    line = (os.getenv("TOPIC_OVERRIDE") or "").strip() or (todo[0] if todo else "")
    if not line:
        log("Tous les thèmes de Shorts sont publiés. Ajoute des lignes dans topics_shorts.txt.")
        return
    theme, _, angle = [x.strip() for x in line.partition("|")]
    angle = angle or "un contraste qui fait réfléchir"
    pal_idx = len(done) % len(shorts.PALETTES)
    log(f"Short : {theme} | {angle} (n°{len(done) + 1}) | dry_run={dry} | visibilité={privacy}")

    for d in (p.WORK, p.OUT):
        d.mkdir(exist_ok=True)
        for f in d.glob("*"):
            f.unlink()

    data = generate(theme, angle, cfg)
    video = p.OUT / "short.mp4"
    build(data["beats"], pal_idx, video, cfg)
    thumb = p.OUT / "thumbnail.jpg"
    p.ff("-ss", 3, "-i", video, "-frames:v", 1, "-q:v", 3, thumb)

    title = data["title"].strip()
    if len(title) + 8 <= 100 and "#shorts" not in title.lower():
        title += " #Shorts"
    tags = [str(t)[:30] for t in data.get("tags", [])][:12] + ["shorts"]
    desc = data.get("description", "").strip() + "\n\n#Shorts " + " ".join(cfg.get("hashtags", []))
    desc += "\n\nShort réalisé avec l'aide d'outils d'IA (écriture, voix, animation)."
    (p.OUT / "meta.json").write_text(json.dumps({"title": title, "description": desc, "tags": tags, "theme": line},
                                                ensure_ascii=False, indent=2), encoding="utf-8")
    if dry:
        log("Mode test : rien n'est publié. Récupère le Short dans les « Artifacts » du run.")
        return
    p.upload(video, thumb, title, desc, tags, privacy, cfg)
    with pub_file.open("a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.utcnow().strftime('%Y-%m-%d')} | {line}\n")
    log("Terminé.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        log("ERREUR :", exc)
        sys.exit(1)
