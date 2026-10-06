"""VO generation from 04-vo-script.md through SYNTX ElevenLabs v3 (cards AUC-V01..V09).

    python tools/audio/vo_batch.py lines [--fighter ARTHUR]                     # parsed script, one line per row
    python tools/audio/vo_batch.py run --voices voices.json --out <dir> [--ids ID ...] [--fighter F] [--takes 2]
                                       [--lanes 3] [--chat <uuid>]

voices.json maps a fighter (or "FIGHTER:label" for casting) to {"voice_id": ..., "settings": {...}}. Each line is one
request; the generation text is the direction tags + the EN text (tags only for wordless efforts). Files:
<out>/<label>/VO_<ID>_t<k>.mp3 + run.json per request (tools/audio/syntx_audio.cjs). Spends go to the ledger
separately (tools/audio/ledger.py), one entry per batch.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "docs/game-design/audio/04-vo-script.md"
NODE = REPO / "tools/audio/syntx_audio.cjs"
CHAT = "419ed456-fc88-4394-8772-aee6ac51437b"
VO_CHATS = ["a7cabbe8-ace4-4b98-b687-ad449cab9552", "c3809b84-27fe-47fb-b207-d1b923e5cabc",
            "f8ffb644-4012-48ff-85df-d13f1bc299a9"]
# Wordless efforts: ElevenLabs v3 returns no audio for a tag alone, so the generation text carries the sound itself
# (no subtitle: the script line stays without EN text).
EFFORT_SOUND = {
    "ARTHUR-HURT-01": "Hngh!", "ARTHUR-HURT-02": "Hhah!", "ARTHUR-HURT-03": "Ahhh...", "ARTHUR-DEATH-01": "Aaarrgh!",
    "MERLIN-HURT-01": "Ah!", "MERLIN-HURT-02": "Hmph!", "MERLIN-DEATH-01": "Ohhh...",
    "MEDUSA-HURT-01": "Hsss-ah!", "MEDUSA-HURT-02": "Hah!", "MEDUSA-HURT-03": "Grrah!",
    "MEDUSA-DEATH-01": "Hsssssss... ahh...",
}
ROW = re.compile(r"^\| ((?:ARTHUR|MERLIN|MEDUSA)-[A-Z-]+-\d\d) \| (.*?) \| (.*?) \| (.*?) \|$")


def lines() -> list[dict]:
    out = []
    for raw in SCRIPT.read_text(encoding="utf-8").splitlines():
        m = ROW.match(raw.strip())
        if not m:
            continue
        lid, en, ru, direction = m.groups()
        en = "" if en.strip() == "—" else en.strip()
        tags = " ".join(re.findall(r"\[[^\]]+\]", direction))
        out.append({"id": lid, "fighter": lid.split("-")[0], "en": en, "ru": "" if ru.strip() == "—" else ru.strip(),
                    "tags": tags, "text": (tags + " " + (en or EFFORT_SOUND.get(lid, ""))).strip()})
    return out


def run_one(job: dict, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    done = out_dir / job["names"][0] / "run.json"
    if done.exists() and json.loads(done.read_text(encoding="utf-8")).get("files"):
        return {"name": job["names"][0], "ok": True, "out": "skip: already generated"}
    jf = out_dir / f"{job['names'][0]}.job.json"
    jf.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
    res = subprocess.run(["node", str(NODE), "run", str(jf), str(out_dir / job["names"][0])], capture_output=True,
                         text=True, encoding="utf-8", errors="replace")
    tail = (res.stdout or res.stderr).strip().splitlines()
    return {"name": job["names"][0], "ok": res.returncode == 0, "out": tail[-1] if tail else ""}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    ls = sub.add_parser("lines")
    ls.add_argument("--fighter")
    rn = sub.add_parser("run")
    rn.add_argument("--voices", required=True)
    rn.add_argument("--out", required=True)
    rn.add_argument("--ids", nargs="*")
    rn.add_argument("--fighter")
    rn.add_argument("--labels", nargs="*", help="voices.json keys to use (casting); default: the fighter itself")
    rn.add_argument("--takes", type=int, default=1)
    rn.add_argument("--lanes", type=int, default=3)
    rn.add_argument("--chats", nargs="*", default=VO_CHATS, help="one chat per lane: a SYNTX chat runs one generation at a time")
    args = ap.parse_args(argv)

    all_lines = lines()
    if args.cmd == "lines":
        for ln in all_lines:
            if not args.fighter or ln["fighter"] == args.fighter:
                print(json.dumps(ln, ensure_ascii=False))
        return 0

    voices = json.loads(Path(args.voices).read_text(encoding="utf-8"))
    sel = [ln for ln in all_lines if (not args.ids or ln["id"] in args.ids)
           and (not args.fighter or ln["fighter"] == args.fighter)]
    jobs = []
    for ln in sel:
        labels = args.labels or [ln["fighter"]]
        for label in labels:
            if not label.startswith(ln["fighter"]):
                continue
            v = voices[label]
            for k in range(1, args.takes + 1):
                name = f"VO_{ln['id'].replace('-', '_')}_t{k}"
                jobs.append((label, {"card": "AUC-V", "ai_name": "elevenlabs", "chat_uuid": None,
                                     "prompt": ln["text"],
                                     "settings": {"model_type": "eleven_v3", "mode": "text_to_speech",
                                                  "voice_id": v["voice_id"], **v.get("settings", {})},
                                     "names": [name]}))
    out = Path(args.out)
    lanes = min(args.lanes, len(args.chats))
    buckets = [[] for _ in range(lanes)]
    for i, (label, job) in enumerate(jobs):
        job["chat_uuid"] = args.chats[i % lanes]
        buckets[i % lanes].append((label, job))

    def lane(bucket):
        return [run_one(job, out / label.replace(":", "_")) for label, job in bucket]

    with ThreadPoolExecutor(max_workers=lanes) as pool:
        results = [r for rs in pool.map(lane, buckets) for r in rs]
    for r in results:
        print(json.dumps(r, ensure_ascii=False))
    print(json.dumps({"requests": len(jobs), "ok": sum(r["ok"] for r in results)}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
