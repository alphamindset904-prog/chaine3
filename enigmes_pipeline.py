#!/usr/bin/env python3
"""Shorts « Énigmes » (≈ 60-80 s) : un paradoxe / une énigme de logique expliquée en pictogrammes roses.
Écriture du script (LLM) -> vérification de l'exactitude (2e appel LLM) -> voix -> animation -> sons -> YouTube.

Usage local :  python enigmes_pipeline.py --demo      (script intégré, sans clé d'API ; DRY_RUN forcé)"""
import array
import datetime
import json
import math
import os
import random
import re
import subprocess
import sys
import wave
from pathlib import Path

import enigmes
import pipeline as p
import shorts_pipeline as sp
from pipeline import log

ROOT = Path(__file__).resolve().parent
WV, HV, FPS = enigmes.WV, enigmes.HV, enigmes.FPS

SYSTEM_PROMPT = """Tu es scénariste de Shorts YouTube en français sur les paradoxes, énigmes de logique, probabilités et
illusions de raisonnement. Le principe : une question qui piège l'intuition, la mauvaise réponse que tout le monde donne,
puis la vraie réponse expliquée simplement avec des pictogrammes. Ton : direct, curieux, tutoiement, phrases courtes.
RÈGLES ABSOLUES : l'énoncé et la solution doivent être mathématiquement et logiquement EXACTS ; n'invente aucune
statistique, étude ou citation ; si le sujet est un paradoxe encore débattu (ex. Newcomb), présente honnêtement les
deux camps au lieu d'affirmer une seule réponse ; pas de conseil médical, financier ou de pari. Tu réponds uniquement
par un objet JSON valide."""

USER_PROMPT = """Écris le scénario d'un Short vertical d'environ 70 secondes sur : « {theme} » (forme : {angle}).

STRUCTURE QUI RETIENT LE SPECTATEUR (dans cet ordre, 9 à 12 séquences) :
1. ACCROCHE (0-4 s) : pose l'énoncé en une phrase choc, ou « Cette question piège 90 % des gens » seulement si c'est vrai
   pour ce problème — sinon une formule du type « Tu as le droit à un seul essai. ». Montre immédiatement l'objet.
2. L'énoncé complet, simple, avec les chiffres exacts (chaque objet apparaît quand on le nomme).
3. « Réfléchis. » : laisse la réponse intuitive se former, puis dis-la (« La plupart répondent … »).
4. Premier rebondissement : un fait qui fissure l'intuition.
5. L'explication, avec UNE image du quotidien et des pictogrammes qui bougent.
6. La vraie réponse, en toutes lettres, avec le calcul en grand (champ "big").
7. Un chiffre ou un cas extrême qui rend la réponse évidente (ex. 100 portes au lieu de 3).
8. Dernière séquence : une question ouverte qui pousse à commenter (« Et toi, tu aurais répondu quoi ? »).

CHAQUE SÉQUENCE = 1 phrase de narration (8 à 20 mots) + des pictogrammes.
Pictogrammes ("icon") : door, door_open, box, money, button, cookie, fork, brain, bulb, person, people, question, clock,
dice, orb, apple, heart, check, cross, scale, coin, arrow, goat, lock, key.
Champs d'un pictogramme : "icon", "label" (sous l'objet, 1-3 mots, optionnel), "tag" (au-dessus, ex. "A", optionnel),
"value" (texte dans money/coin, ex. "1 000e", ou chiffre 1-6 pour dice), "at" (UN mot exact de la narration au moment
duquel l'objet apparaît), "then" ({{"icon": ..., "at": mot}} = l'objet se transforme quand ce mot est dit, ex. door -> door_open),
"dim_at" (mot à partir duquel l'objet s'éteint, pour l'éliminer), "hl" (true = label en rose), "tilt" (scale, -1 à 1).
Champs de séquence : "items" (0 à 6 pictogrammes), "top" (question ou énoncé en haut, 3 à 12 mots, optionnel),
"big" (texte géant : chiffre, fraction, mot-clé, 1 à 6 mots) avec "big_at" (mot) et "big_hl" (true = rose).

CONTRAINTES :
- Narration totale : 140 à 190 mots. Écris les nombres comme on les dit (« mille euros », « deux tiers »).
- "at", "big_at", "then.at", "dim_at" = un mot qui existe tel quel dans la narration de CETTE séquence.
- Évite d'avoir la même disposition deux séquences de suite. Pas d'emoji. Le texte à l'écran doit se comprendre sans le son.
- Dans "label", "top", "big" : français correct, accents compris.
- Fournis aussi "solution" : la bonne réponse en une phrase, et "verif" : le calcul ou le raisonnement qui la justifie.

FORMAT JSON EXACT :
{{"title": "titre accrocheur (max 60 caractères)", "description": "1 à 2 phrases", "tags": ["8 à 12 mots-clés"],
 "solution": "...", "verif": "...",
 "beats": [{{"narration": "...", "top": "...", "big": "...", "big_at": "mot", "items": [{{"icon": "door", "tag": "A", "at": "mot"}}]}}]}}"""

CHECK_PROMPT = """Voici le scénario d'un Short sur « {theme} ». Vérifie rigoureusement qu'il est exact : énoncé cohérent,
nombres justes, solution correcte, aucune affirmation fausse ou invérifiable, et que chaque pictogramme illustre bien
ce qui est dit. Résous toi-même le problème avant de juger.
Réponds uniquement par {{"ok": true|false, "probleme": "description précise de l'erreur, sinon vide"}}.

SCÉNARIO :
{script}"""


def normalize(data):
    beats = []
    for b in data.get("beats", []):
        narr = str(b.get("narration", "")).strip()
        if not narr:
            continue
        nb = {"narration": narr, "items": []}
        for k, lim in (("top", 90), ("big", 40)):
            v = str(b.get(k, "") or "").strip()
            if v:
                nb[k] = v[:lim]
        if nb.get("big"):
            nb["big_at"] = str(b.get("big_at", "") or "").strip()
            nb["big_hl"] = bool(b.get("big_hl"))
        for it in (b.get("items") or [])[:6]:
            if not isinstance(it, dict):
                continue
            icon = str(it.get("icon", "")).strip().lower()
            if icon not in enigmes.ICONS:
                continue
            ni = {"icon": icon}
            for k, lim in (("label", 22), ("tag", 4), ("value", 12), ("at", 24), ("dim_at", 24)):
                v = str(it.get(k, "") or "").strip()
                if v:
                    ni[k] = v[:lim]
            if it.get("hl"):
                ni["hl"] = True
            if it.get("spin"):
                ni["spin"] = True
            try:
                ni["tilt"] = max(-1.0, min(1.0, float(it.get("tilt", 0) or 0)))
            except (TypeError, ValueError):
                pass
            th = it.get("then")
            if isinstance(th, dict) and str(th.get("icon", "")).lower() in enigmes.ICONS:
                ni["then"] = {"icon": str(th["icon"]).lower(), "at": str(th.get("at", "") or "")[:24]}
            nb["items"].append(ni)
        beats.append(nb)
    return beats


def generate(theme, angle, cfg):
    best, feedback = None, ""
    for attempt in range(4):
        user = USER_PROMPT.format(theme=theme, angle=angle)
        if feedback:
            user += f"\n\nATTENTION, ta version précédente contenait cette erreur à corriger : {feedback}"
        data = p.llm_json(SYSTEM_PROMPT, user, cfg)
        beats = normalize(data)
        words = sum(len(b["narration"].split()) for b in beats)
        log(f"Énigme : {len(beats)} séquences, {words} mots")
        if len(beats) < 7 or not data.get("title"):
            feedback = "trop peu de séquences ou titre manquant."
            continue
        data["beats"] = beats
        if not (115 <= words <= 215):
            feedback = f"narration de {words} mots ; vise 140 à 190."
            if best is None:
                best = data
            continue
        if cfg.get("enigmes_verify", True):
            try:
                chk = p.llm_json("Tu es un relecteur scientifique impitoyable. Réponds uniquement en JSON.",
                                 CHECK_PROMPT.format(theme=theme, script=json.dumps(
                                     {"solution": data.get("solution"), "verif": data.get("verif"),
                                      "beats": beats}, ensure_ascii=False)), cfg)
            except RuntimeError as e:
                log("Vérification indisponible :", e)
                return data
            if chk.get("ok"):
                log("Vérification : script validé.")
                return data
            feedback = str(chk.get("probleme", "erreur non précisée"))[:400]
            log("Vérification : refusé ->", feedback)
            continue
        return data
    raise RuntimeError("Aucun script valide après 4 essais (voir la dernière erreur de vérification ci-dessus).")


# ----------------------------------------------------------------------------
# Sons (pop à chaque apparition, tic de transition) : synthèse pure Python
# ----------------------------------------------------------------------------
SR = 44100


def pop_samples(freq=620, ms=110, vol=.35):
    n = int(SR * ms / 1000)
    return [int(32767 * vol * math.sin(2 * math.pi * (freq + 380 * (1 - i / n)) * i / SR) * math.exp(-5.5 * i / n))
            for i in range(n)]


def make_sfx(cues, dur, dest):
    buf = array.array("i", [0]) * int(SR * dur + SR)
    pops = {f: pop_samples(f) for f in (520, 640, 780)}
    rnd = random.Random(5)
    for c in sorted(cues):
        start = int(c * SR)
        for i, v in enumerate(pops[rnd.choice((520, 640, 780))]):
            if start + i < len(buf):
                buf[start + i] += v
    out = array.array("h", [max(-32767, min(32767, v)) for v in buf[:int(SR * dur)]])
    with wave.open(str(dest), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(out.tobytes())


def synth_or_silence(text, mp3, cfg):
    """Voix edge-tts ; avec ENIGMES_NO_TTS=1 (test hors ligne) une piste silencieuse à la durée de lecture estimée."""
    if os.getenv("ENIGMES_NO_TTS") == "1":
        secs = max(2.0, len(text.split()) / 2.9)
        p.ff("-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=mono", "-t", f"{secs:.2f}", "-c:a", "libmp3lame", mp3)
        return
    p.synth(text, mp3, cfg)


def build(beats, dest, cfg):
    gap = float(cfg.get("short_gap", 0.4))
    segs, wavs, cues_all, offset = [], [], [], 0.0
    for i, b in enumerate(beats):
        mp3 = p.WORK / f"a{i}.mp3"
        scfg = dict(cfg)
        scfg["voice_rate"] = cfg.get("voice_rate_enigmes", cfg.get("voice_rate_short", cfg.get("voice_rate", "+0%")))
        synth_or_silence(b["narration"], mp3, scfg)
        speech = p.duration(mp3)
        frames = math.ceil(max(speech + gap, 3.0) * FPS)
        total = frames / FPS
        wav = p.WORK / f"a{i}.wav"
        p.ff("-i", mp3, "-af", f"apad=whole_dur={total:.4f}", "-t", f"{total:.4f}", "-ar", SR, "-ac", 2, wav)
        seg = p.WORK / f"v{i}.mp4"
        rend = enigmes.BeatRenderer(b, total, speech, cfg, last=(i == len(beats) - 1))
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
        cues_all += [offset + c for c in rend.cues]
        offset += total
        log(f"Séquence {i + 1}/{len(beats)} prête ({total:.1f}s)")

    def concat(files, out):
        lst = p.WORK / (out.stem + ".txt")
        lst.write_text("".join(f"file '{f.resolve()}'\n" for f in files))
        p.ff("-f", "concat", "-safe", 0, "-i", lst, "-c", "copy", out)

    vid, voice = p.WORK / "video_only.mp4", p.WORK / "voice_all.wav"
    amb, sfx = p.WORK / "ambient.wav", p.WORK / "sfx.wav"
    concat(segs, vid)
    concat(wavs, voice)
    total_dur = p.duration(voice)
    sp.make_ambient(total_dur, amb)
    make_sfx(cues_all, total_dur, sfx)
    p.ff("-i", vid, "-i", voice, "-i", amb, "-i", sfx, "-filter_complex",
         "[1:a]volume=1.0[v];[2:a]volume=0.2[m];[3:a]volume=0.55,aformat=channel_layouts=stereo[s];"
         "[v][m][s]amix=inputs=3:duration=first:dropout_transition=0,volume=1.9[a]",
         "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest",
         "-movflags", "+faststart", dest)
    log(f"Short final : {p.duration(dest):.1f}s")


DEMO = {
    "title": "Monty Hall : change de porte ?", "description": "Le paradoxe des trois portes, expliqué en 1 minute.",
    "tags": ["monty hall", "paradoxe", "probabilités", "logique", "maths", "énigme", "culture générale", "intuition"],
    "solution": "Changer de porte donne 2 chances sur 3.",
    "beats": [
        {"narration": "Trois portes. Derrière l'une, cent euros. Derrière les autres, rien.",
         "top": "Une seule porte cache le gain", "big": "100e", "big_at": "cent",
         "items": [{"icon": "door", "tag": "A", "at": "Trois"}, {"icon": "door", "tag": "B", "at": "Trois"},
                   {"icon": "door", "tag": "C", "at": "Trois"}]},
        {"narration": "Tu choisis la porte A. Une chance sur trois d'avoir gagné.",
         "items": [{"icon": "door", "tag": "A", "label": "ton choix", "hl": True, "at": "porte"},
                   {"icon": "door", "tag": "B"}, {"icon": "door", "tag": "C"}], "big": "1/3", "big_at": "trois"},
        {"narration": "Le présentateur sait où est le gain. Il ouvre la porte C : elle est vide.",
         "items": [{"icon": "door", "tag": "A", "hl": True}, {"icon": "door", "tag": "B"},
                   {"icon": "door", "tag": "C", "then": {"icon": "door_open", "at": "ouvre"}}]},
        {"narration": "Il te propose de changer. Tu changes, ou tu restes ?",
         "top": "Tu changes ou tu restes ?", "items": [{"icon": "door", "tag": "A", "at": "changer"},
                                                       {"icon": "arrow", "at": "changes"},
                                                       {"icon": "door", "tag": "B", "at": "restes"}]},
        {"narration": "Presque tout le monde répond : peu importe, c'est du cinquante cinquante.",
         "items": [{"icon": "scale", "tilt": 0, "at": "cinquante"}], "big": "50 / 50 ?", "big_at": "cinquante"},
        {"narration": "Faux. Ta porte A n'avait toujours qu'une chance sur trois.",
         "items": [{"icon": "door", "tag": "A", "label": "1/3", "at": "Faux"}, {"icon": "cross", "at": "Faux"}]},
        {"narration": "Et les deux autres portes, ensemble, avaient deux chances sur trois.",
         "items": [{"icon": "door", "tag": "B", "at": "autres"}, {"icon": "door", "tag": "C", "at": "ensemble"}],
         "big": "2/3", "big_at": "deux", "big_hl": True},
        {"narration": "Le présentateur en a éliminé une. Tout ce poids passe sur la porte B.",
         "items": [{"icon": "door", "tag": "B", "label": "2/3", "hl": True, "at": "porte"},
                   {"icon": "door_open", "tag": "C", "at": "éliminé", "dim_at": "éliminé"}]},
        {"narration": "Imagine cent portes. Tu en choisis une, et il en ouvre quatre-vingt-dix-huit vides.",
         "items": [{"icon": "door", "at": "cent"}, {"icon": "door", "at": "portes"}, {"icon": "door_open", "at": "ouvre"}],
         "big": "98", "big_at": "quatre-vingt-dix-huit"},
        {"narration": "Tu changerais, non ? Changer de porte double tes chances de gagner. Et toi, tu aurais fait quoi ?",
         "top": "Et toi, tu aurais fait quoi ?", "items": [{"icon": "brain", "at": "toi"}], "big": "Changer", "big_at": "Changer", "big_hl": True},
    ],
}


def main():
    demo = "--demo" in sys.argv
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    dry = demo or os.getenv("DRY_RUN", "").lower() == "true"
    privacy = os.getenv("PRIVACY") or "public"

    topics = [l.strip() for l in (ROOT / "topics_enigmes.txt").read_text(encoding="utf-8").splitlines()
              if l.strip() and not l.startswith("#")]
    pub_file = ROOT / "enigmes_published.txt"
    rows = [l.strip() for l in pub_file.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.startswith("#")] if pub_file.exists() else []
    done = [r.split(" | ", 1)[1] if " | " in r else r for r in rows]
    todo = [t for t in topics if t not in done]
    line = (os.getenv("TOPIC_OVERRIDE") or "").strip() or (todo[0] if todo else "")
    if demo:
        line = "le paradoxe de Monty Hall | trois portes"
    if not line:
        log("Tous les thèmes d'énigmes sont publiés. Ajoute des lignes dans topics_enigmes.txt.")
        return
    theme, _, angle = [x.strip() for x in line.partition("|")]
    angle = angle or "une question qui piège l'intuition"
    log(f"Énigme : {theme} | {angle} (n°{len(done) + 1}) | dry_run={dry} | visibilité={privacy}")

    for d in (p.WORK, p.OUT):
        d.mkdir(exist_ok=True)
        for f in d.glob("*"):
            f.unlink()

    if demo:
        data = dict(DEMO)
        data["beats"] = normalize(DEMO)
    else:
        data = generate(theme, angle, cfg)
    video = p.OUT / "enigme.mp4"
    build(data["beats"], video, cfg)
    thumb = p.OUT / "thumbnail.jpg"
    p.ff("-ss", 2.5, "-i", video, "-frames:v", 1, "-q:v", 3, thumb)

    title = data["title"].strip()
    if len(title) + 8 <= 100 and "#shorts" not in title.lower():
        title += " #Shorts"
    tags = [str(t)[:30] for t in data.get("tags", [])][:12] + ["shorts", "paradoxe", "logique"]
    desc = data.get("description", "").strip()
    if data.get("solution"):
        desc += f"\n\nRéponse : {data['solution']}"
    desc += "\n\n#Shorts " + " ".join(cfg.get("hashtags_enigmes", ["#paradoxe", "#logique", "#maths", "#énigme"]))
    desc += "\n\nShort réalisé avec l'aide d'outils d'IA (écriture, voix, animation)."
    (p.OUT / "meta.json").write_text(json.dumps({"title": title, "description": desc, "tags": tags, "theme": line,
                                                 "script": data["beats"]}, ensure_ascii=False, indent=2), encoding="utf-8")
    if dry:
        log("Mode test : rien n'est publié. Récupère la vidéo dans les « Artifacts » du run.")
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
