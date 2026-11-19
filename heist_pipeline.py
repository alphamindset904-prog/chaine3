#!/usr/bin/env python3
"""Short YouTube quotidien : histoire de braquage animée (≈ 45-55 s), pensée pour la rétention.

Gemini invente l'histoire du jour (jamais la même grâce à l'historique) -> voix off (edge-tts) -> animation dessinée
par le programme (heist.py) avec sous-titres mot à mot, bruitages et boucle finale -> upload YouTube.
"""
import datetime
import json
import math
import os
import random
import subprocess
import sys
from pathlib import Path

import heist
import pipeline as p
from pipeline import log

ROOT = Path(__file__).resolve().parent
PUB = ROOT / "heist_published.txt"
OW, OH, FPS = heist.OW, heist.OH, heist.FPS

GENRES = [
    "une banque de quartier", "un musée et un diamant célèbre", "un casino de luxe", "un train de nuit transportant de l'or",
    "un convoi blindé", "une bijouterie", "une réserve d'or sous une ville", "une galerie d'art et un faux tableau",
    "un coffre-fort d'hôtel", "un cinéma qui cache un coffre", "une banque de campagne très mal gardée",
    "une vente aux enchères", "un transporteur de fonds", "une mairie et ses archives en or", "une tour de verre en plein centre",
]
TWISTS = [
    "le butin n'était pas ce qu'ils croyaient", "le gardien était dans la combine depuis le début",
    "le cerveau du plan est le dernier qu'on soupçonne", "ils ont volé... la mauvaise chose",
    "la police a tout prévu, sauf un détail minuscule", "le plan parfait échoue à cause d'un détail absurde",
    "celui qui les poursuit a le même secret qu'eux", "le braquage était un test et personne ne le savait",
    "ils s'échappent grâce à l'idée la plus idiote", "le coffre était déjà vide : quelqu'un est passé avant eux",
]

CAST = """PERSONNAGES RÉCURRENTS DE LA SÉRIE (les spectateurs les connaissent : utilise-les !) :
- Le Renard (actor "fox") : braqueur culte, cerveau élégant et malicieux. Ne blesse jamais personne. Laisse toujours une carte de visite avec un renard dessiné. Phrase fétiche : « Rien n'est impossible, juste mal rangé. »
- Biscuit (actor "biscuit") : son acolyte gourmand et maladroit, grignote pendant les braquages, appuie toujours sur le mauvais bouton, mais sauve parfois la mise par accident.
- L'Inspecteur Mouchoir (actor "detective") : détective brillant, toujours enrhumé (« Atchoum... c'est lui ! »), arrive souvent une minute trop tard, rêve d'arrêter le Renard.
Chaque épisode reste compréhensible seul, mais les héros gardent leur caractère, leurs phrases fétiches, et tu peux faire un petit clin d'œil à un épisode passé."""

SYSTEM_PROMPT = """Tu es scénariste de Shorts YouTube français d'animation : des histoires de braquage FICTIVES, rapides,
malignes et drôles, qui retiennent le spectateur jusqu'à la dernière seconde. Ton punchy, phrases courtes, présent de narration.
RÈGLES STRICTES : histoire 100 % inventée (aucune personne réelle, aucune marque, aucun fait présenté comme vrai) ;
aucune arme décrite ni montrée, aucune violence, aucun blessé, rien de choquant ; aucune méthode réelle ni technique
exploitable (le « comment » reste vague et cartoon) ; les personnages ont des surnoms rigolos. Tu réponds uniquement par un objet JSON valide."""

USER_PROMPT = """Écris le scénario d'un Short vertical de 45 à 55 secondes.
Épisode n°{episode} de la série. Cadre : {genre}. Retournement de fin : {twist}.
Score actuel du duel : {score}.

{cast}
Histoires déjà publiées (ne les répète pas, change aussi les surnoms) :
{history}

STRUCTURE QUI RETIENT (obligatoire) :
1. beat 1 = ACCROCHE : une phrase choc de 8 à 12 mots qui annonce le résultat impossible et nomme un héros (ex. « Le Renard a vidé une banque en gardant la porte ouverte. »). Pas d'introduction, pas de « bonjour ».
2. beat 2 : une promesse de curiosité (« mais personne ne sait comment... » / « et le plus fou, c'est la fin »).
3. beats 3-6 : le plan, les personnages (surnoms), la tension qui monte, chaque beat finit sur une mini-question ou un « mais ».
4. beats 7-9 : le grain de sable, la poursuite ou l'alarme, puis la révélation.
5. dernier beat : un twist qui change le sens de tout, et une dernière phrase INACHEVÉE ou qui se raccorde directement à la toute première (le Short boucle). Pas de conclusion, pas d'appel à s'abonner.

CONTRAINTES :
- 9 à 11 beats ; narration TOTALE de 115 à 140 mots ; chaque beat 8 à 18 mots ; vocabulaire simple ; pas d'emoji ; chiffres écrits comme on les dit.
- "scene" parmi : street_night (rue de nuit), bank_front (façade de banque), bank_inside (intérieur de banque), vault (salle du coffre), hideout (planque : plan sur la table), chase (poursuite en voiture, sans acteurs), police_hq (commissariat), museum (musée, vitrine de diamant), beach (plage : la fuite réussie), jail (prison).
- "actors" : 0 à 3 personnages parmi fox (Le Renard), biscuit (Biscuit), detective (Inspecteur Mouchoir) — au moins deux de ces trois héros doivent apparaître dans l'épisode —, thief (braqueur masqué), boss (le cerveau), guard (gardien), cop (policier), banker (banquier), civilian (passant), prisoner (prisonnier). Mets [] pour la scène chase.
- "action" parmi : idle, walk, run, sneak, hands_up, point, carry, celebrate, talk.
- "fx" parmi : none, alarm, siren, money, flash, lights_off, shake (un effet fort tous les 2 beats environ, jamais deux fois le même à la suite).
- "loot" : true si des sacs d'argent doivent apparaître dans l'image.
- Change de "scene" à presque chaque beat ; la 1re scène est street_night ou bank_front.
- Le texte doit être lisible à l'écran sans le son.

FORMAT JSON EXACT :
{{"title": "titre qui donne envie de cliquer (max 60 caractères, sans #)", "premise": "résumé en 1 phrase",
 "description": "1 à 2 phrases d'accroche", "outcome": "renard" (le Renard s'en sort), "mouchoir" (le détective gagne) ou "egalite", "tags": ["8 à 12 mots-clés"],
 "beats": [{{"scene": "street_night", "actors": ["thief", "thief"], "action": "sneak", "fx": "none", "loot": false, "narration": "..."}}]}}"""


def normalize(data):
    beats, last_fx = [], None
    for b in data.get("beats", []):
        narr = " ".join(str(b.get("narration", "")).split())
        if not narr:
            continue
        scene = str(b.get("scene", "")).strip().lower()
        if scene not in heist.SCENES:
            scene = "street_night" if not beats else "hideout"
        actors = [str(a).lower().strip() for a in (b.get("actors") or [])]
        actors = [a for a in actors if a in heist.KINDS][:3]
        if scene == "chase":
            actors = []
        elif not actors:
            actors = ["thief"]
        action = str(b.get("action", "idle")).lower().strip()
        if action not in heist.ACTIONS:
            action = "idle"
        fx = str(b.get("fx", "none")).lower().strip()
        if fx not in heist.FXS or fx == last_fx:
            fx = "none"
        last_fx = fx if fx != "none" else last_fx
        beats.append({"scene": scene, "actors": actors, "action": action, "fx": fx,
                      "loot": bool(b.get("loot")), "narration": narr})
    if beats:
        beats[0]["fx"] = "flash"                                  # coup d'œil dès la 1re image
        if beats[0]["scene"] not in ("street_night", "bank_front"):
            beats[0]["scene"] = "bank_front"
    return beats[:12]


def generate(cfg, history, episode=1, score="0 – 0"):
    hist = "\n".join(f"- {h}" for h in history[-40:]) or "- (aucune)"
    best = None
    feedback = ""
    rnd = random.Random()
    for attempt in range(4):
        genre, twist = rnd.choice(GENRES), rnd.choice(TWISTS)
        data = p.llm_json(SYSTEM_PROMPT, USER_PROMPT.format(genre=genre, twist=twist, history=hist, episode=episode, score=score, cast=CAST) + feedback, cfg)
        beats = normalize(data)
        words = sum(len(b["narration"].split()) for b in beats)
        title = str(data.get("title", "")).strip()
        log(f"Histoire : {len(beats)} beats, {words} mots — {title}")
        dup = any(title.lower() == h.split(" — ")[0].lower() for h in history)
        if len(beats) >= 7 and title and not dup:
            data["beats"] = beats
            if best is None or abs(words - 128) < abs(best[1] - 128):
                best = (data, words)
            if 100 <= words <= 150:
                break
            feedback = (f"\n\nATTENTION : ta version précédente faisait {words} mots de narration. "
                        "Il en faut entre 115 et 140.")
    if best is None:
        raise RuntimeError("Histoire inutilisable après 4 essais.")
    return best[0]


def fake_tts(text, path):
    """Test local sans réseau : silence de la bonne durée (≈ 0,36 s par mot)."""
    p.ff("-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", f"{max(1.2, len(text.split()) * .36):.2f}", path)


def build(beats, dest, cfg, thumb):
    voice = cfg.get("heist_voice", cfg.get("voice", "fr-FR-HenriNeural"))
    rate = cfg.get("heist_voice_rate", "+8%")
    gap = float(cfg.get("heist_gap", .15))
    plan = []
    for i, b in enumerate(beats):
        mp3 = p.WORK / f"a{i}.mp3"
        bounds = None
        if os.getenv("HEIST_FAKE_TTS"):
            fake_tts(b["narration"], mp3)
        else:
            try:
                bounds = heist.synth_words(p.to_speech(b["narration"]), mp3, voice, rate)
            except Exception as e:  # noqa: BLE001
                log("edge-tts indisponible, repli sur gTTS :", e)
                p.synth(b["narration"], mp3, {"voice": voice, "voice_rate": rate})
        d = p.duration(mp3)
        total = math.ceil(max(d + (0 if i == len(beats) - 1 else gap), 2.0) * FPS) / FPS
        plan.append((b, mp3, d, total, bounds))
    gtotal = sum(x[3] for x in plan)
    log(f"Durée prévue : {gtotal:.1f}s")

    segs, wavs, events, t0, seen = [], [], [], 0.0, set()
    for i, (b, mp3, d, total, bounds) in enumerate(plan):
        wav = p.WORK / f"a{i}.wav"
        p.ff("-i", mp3, "-af", f"apad=whole_dur={total:.4f}", "-t", f"{total:.4f}", "-ar", 44100, "-ac", 2, wav)
        new = {a for a in b["actors"] if a in heist.NAMES} - seen
        seen |= new
        beat = heist.Beat(b, total, i, bounds, new)
        seg = p.WORK / f"v{i}.mp4"
        proc = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OW}x{OH}",
             "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
             "-pix_fmt", "yuv420p", str(seg)], stdin=subprocess.PIPE)
        for n in range(int(round(total * FPS))):
            proc.stdin.write(beat.frame(n / FPS, t0 + n / FPS, gtotal).tobytes())
            if i == 0 and n == int(1.3 * FPS):
                beat.frame(n / FPS, t0 + n / FPS, gtotal).save(thumb, "JPEG", quality=90)
        proc.stdin.close()
        if proc.wait() != 0:
            raise RuntimeError(f"ffmpeg a échoué sur le beat {i + 1}")
        segs.append(seg)
        wavs.append(wav)
        if i:
            events.append((t0, "cut"))
        if b["fx"] != "none":
            events.append((t0 + .05, b["fx"]))
        t0 += total
        log(f"Beat {i + 1}/{len(plan)} prêt ({total:.1f}s, {b['scene']}, {b['fx']})")

    def concat(files, out):
        lst = p.WORK / (out.stem + ".txt")
        lst.write_text("".join(f"file '{f.resolve()}'\n" for f in files))
        p.ff("-f", "concat", "-safe", 0, "-i", lst, "-c", "copy", out)

    vid, voc, bed = p.WORK / "video_only.mp4", p.WORK / "voice_all.wav", p.WORK / "bed.wav"
    concat(segs, vid)
    concat(wavs, voc)
    heist.make_bed(gtotal, events, bed)
    p.ff("-i", vid, "-i", voc, "-i", bed, "-filter_complex",
         "[1:a]aresample=44100[v];[2:a]aresample=44100,volume=.8[m];"
         "[v][m]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]",
         "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-ar", 44100,
         "-movflags", "+faststart", dest)
    log(f"Short final : {p.duration(dest):.1f}s")


def read_history():
    if not PUB.exists():
        return []
    out = []
    for l in PUB.read_text(encoding="utf-8").splitlines():
        parts = [x.strip() for x in l.split(" | ")]
        if len(parts) >= 2:
            out.append(parts[1] + (" — " + parts[2] if len(parts) > 2 else ""))
    return out


def read_score():
    r = m = 0
    if PUB.exists():
        for l in PUB.read_text(encoding="utf-8").splitlines():
            o = l.split(" | ")[-1].strip() if l.count(" | ") >= 3 else ""
            r += o == "renard"
            m += o == "mouchoir"
    return r, m


def main():
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    dry = os.getenv("DRY_RUN", "").lower() == "true"
    privacy = os.getenv("PRIVACY") or "public"
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    if PUB.exists() and not dry and not os.getenv("FORCE"):
        last = (PUB.read_text(encoding="utf-8").strip().splitlines() or [""])[-1].split(" | ")[0].strip()
        if last == today:
            log(f"Un Short a déjà été publié aujourd'hui ({today}) : rien à faire.")
            return
    history = read_history()
    log(f"Short braquage n°{len(history) + 1} | dry_run={dry} | visibilité={privacy}")

    for d in (p.WORK, p.OUT):
        d.mkdir(exist_ok=True)
        for f in d.glob("*"):
            f.unlink()

    sr, sm = read_score()
    score = f"Renard {sr} – Mouchoir {sm}"
    data = generate(cfg, history, len(history) + 1, score)
    video, thumb = p.OUT / "short.mp4", p.OUT / "thumbnail.jpg"
    build(data["beats"], video, cfg, thumb)
    outcome = str(data.get("outcome", "")).lower().strip()
    outcome = outcome if outcome in ("renard", "mouchoir") else "egalite"

    title = data["title"].strip().rstrip(".")
    if len(title) + 8 <= 100:
        title += " #Shorts"
    tags = [str(t)[:30] for t in data.get("tags", [])][:12] + ["shorts", "braquage", "histoire"]
    desc = data.get("description", "").strip() + "\n\n" + " ".join(["#Shorts"] + cfg.get("heist_hashtags", ["#braquage", "#histoire", "#animation"]))
    desc += f"\n\nSérie : Le Renard contre l'Inspecteur Mouchoir. Épisode {len(history) + 1}."
    desc += "\n\nHistoire fictive, inventée par une IA. Toute ressemblance avec des faits réels serait fortuite."
    premise = " ".join(str(data.get("premise", "")).split())[:160]
    (p.OUT / "meta.json").write_text(json.dumps({"title": title, "description": desc, "tags": tags, "premise": premise},
                                                ensure_ascii=False, indent=2), encoding="utf-8")
    if dry:
        log("Mode test : rien n'est publié. Récupère le Short dans les « Artifacts » du run.")
        return
    p.upload(video, thumb, title, desc, tags, privacy, {**cfg, "category_id": cfg.get("heist_category_id", "24")})
    with PUB.open("a", encoding="utf-8") as f:
        f.write(f"{today} | {data['title'].strip()} | {premise} | {outcome}\n")
    log("Terminé.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        log("ERREUR :", exc)
        sys.exit(1)
