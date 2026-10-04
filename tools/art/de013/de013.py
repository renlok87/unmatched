"""DE-013 (W-25 art, 07 A04): the licensed sound list for the CUE sync points - a list only, no downloads, no purchases.

    python tools/art/de013/de013.py check      # validate the list against the rules below and the CUE table
    python tools/art/de013/de013.py table      # print the role -> primary source table (for CREDITS-audio.md)

The list lives in docs/art-pipeline/audio/de013-sound-list.json, the human-readable credits in
docs/art-pipeline/CREDITS-audio.md. The importer (ART-010 / DE-032, GD-049) takes the files from here; until then
every CUE keeps sfx.status = missing in docs/unreal/contracts/cue-dispatcher/cue-table.json.

Rules checked (07 A04 exit criterion "every sound has a licence and a source", backlog DE-013 acceptance):
- every sound names a primary source and every source has a licence, a licence URL and an http(s) source URL;
- no source and no sound comes from Unmatched: Digital Edition (EULA, SD-51);
- a paid source, or one on Fab (added through the user's Epic account), is acquisition = "user" (purchases are the
  user's); the primary source of every sound is a free download;
- a licence that needs attribution (CC BY, JDSherbert) has attribution_required = true and an attribution text;
- the six roles of the deliverable are present; cues exist in the CUE table and the sound class matches it;
- timing limits from 01 / SD-51: one step per 280 ms edge (length <= 280), stings 2-3 s, ui click <= 250 ms;
- every sound id and source id appears in CREDITS-audio.md.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
LIST_PATH = REPO / "docs/art-pipeline/audio/de013-sound-list.json"
CUE_TABLE_PATH = REPO / "docs/unreal/contracts/cue-dispatcher/cue-table.json"
CREDITS_PATH = REPO / "docs/art-pipeline/CREDITS-audio.md"

SCHEMA = "de013-sound-list/1"
# Deliverable of DE-013 (07-sprint-backlog.csv): ui click, hit, step (one per edge), own-turn chime, win / lose stings.
REQUIRED_ROLES = {
    "SND-UI-CLICK": "CUE-002",
    "SND-UI-CONFIRM": "CUE-003",
    "SND-HIT": "CUE-011",
    "SND-STEP": "CUE-007",
    "SND-TURN-CHIME": "CUE-015",
    "SND-STING-WIN": "CUE-016",
    "SND-STING-LOSE": "CUE-016",
}
EDGE_MS = 280  # 01 F-02: constant time per edge (CUE-007)
STING_MS = (2000, 3000)  # SD-51 p. 5: result sting ~2-3 s
UI_CLICK_MAX_MS = 250  # CUE-002 / CUE-003 duration
ACQUISITIONS = {"free_download", "user"}
# Anything pointing at the DE game, its store pages or our DE captures is forbidden as a sound source.
DE_PATTERNS = re.compile(
    r"unmatched|restoration\s*games|digital\s*edition|steampowered|de-live|de-footage|\bDE\b", re.IGNORECASE
)
ATTRIBUTION_LICENSES = re.compile(r"CC\s*BY(?![-\s]*NC)|JDSherbert|attribution|кредит", re.IGNORECASE)
USER_STORES = re.compile(r"fab\.com", re.IGNORECASE)  # Fab items are added through the user's Epic account


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def cue_classes(cue_table: dict) -> dict[str, str | None]:
    return {c["id"]: (c.get("sfx") or {}).get("sound_class") for c in cue_table["cues"]}


def check(data: dict, cue_table: dict, credits_text: str | None) -> list[str]:
    errors: list[str] = []
    if data.get("schema") != SCHEMA:
        errors.append(f"schema: expected {SCHEMA}, got {data.get('schema')!r}")
    if data.get("task") != "DE-013":
        errors.append("task: expected DE-013")
    if data.get("supplements") != "ART-010":
        errors.append("supplements: DE-013 supplements ART-010 and must say so")

    sources: dict[str, dict] = {}
    for src in data.get("sources", []):
        sid = src.get("id") or "<no id>"
        if sid in sources:
            errors.append(f"source {sid}: duplicate id")
        sources[sid] = src
        for field in ("title", "author", "url", "license", "license_url", "license_checked", "cost", "acquisition"):
            if not str(src.get(field) or "").strip():
                errors.append(f"source {sid}: {field} is empty")
        for field in ("url", "license_url"):
            if src.get(field) and not re.match(r"https?://", src[field]):
                errors.append(f"source {sid}: {field} is not an http(s) URL")
        blob = " ".join(str(src.get(k) or "") for k in ("title", "author", "url"))
        if DE_PATTERNS.search(blob):
            errors.append(f"source {sid}: looks like a Digital Edition source (EULA: DE sounds are forbidden)")
        if src.get("acquisition") not in ACQUISITIONS:
            errors.append(f"source {sid}: acquisition must be one of {sorted(ACQUISITIONS)}")
        paid = str(src.get("cost") or "").strip().lower() != "free"
        if (paid or USER_STORES.search(str(src.get("url") or ""))) and src.get("acquisition") != "user":
            errors.append(f"source {sid}: paid or Fab source must be acquisition = user (purchases are the user's)")
        if not isinstance(src.get("attribution_required"), bool):
            errors.append(f"source {sid}: attribution_required must be true or false")
        if ATTRIBUTION_LICENSES.search(str(src.get("license") or "")) and src.get("attribution_required") is not True:
            errors.append(f"source {sid}: licence needs attribution but attribution_required is not true")
        if src.get("attribution_required") and not str(src.get("attribution_text") or "").strip():
            errors.append(f"source {sid}: attribution_required without attribution_text")
        if not isinstance(src.get("no_ai_training"), bool):
            errors.append(f"source {sid}: no_ai_training must be true or false")

    classes = cue_classes(cue_table)
    seen: dict[str, dict] = {}
    for snd in data.get("sounds", []):
        nid = snd.get("id") or "<no id>"
        if nid in seen:
            errors.append(f"sound {nid}: duplicate id")
        seen[nid] = snd
        for field in ("role", "sync_point", "per_event", "character", "listen_check"):
            if not str(snd.get(field) or "").strip():
                errors.append(f"sound {nid}: {field} is empty")
        primary = snd.get("primary") or {}
        if primary.get("source") not in sources:
            errors.append(f"sound {nid}: primary source {primary.get('source')!r} is not in sources")
        elif sources[primary["source"]].get("acquisition") != "free_download":
            errors.append(f"sound {nid}: primary source must be a free download (no purchase in DE-013)")
        if not str(primary.get("file_hint") or "").strip():
            errors.append(f"sound {nid}: primary file_hint is empty")
        for alt in snd.get("alternatives", []):
            if alt.get("source") not in sources:
                errors.append(f"sound {nid}: alternative source {alt.get('source')!r} is not in sources")
        if DE_PATTERNS.search(json.dumps(primary, ensure_ascii=False)):
            errors.append(f"sound {nid}: primary refers to Digital Edition material")
        cues = snd.get("cues") or []
        if not cues:
            errors.append(f"sound {nid}: no cues")
        for cue in cues:
            if cue not in classes:
                errors.append(f"sound {nid}: {cue} is not in the CUE table")
            elif classes[cue] != snd.get("sound_class"):
                errors.append(f"sound {nid}: sound_class {snd.get('sound_class')!r} != CUE table {classes[cue]!r} ({cue})")
        length = snd.get("length_ms")
        if not (isinstance(length, list) and len(length) == 2 and all(isinstance(v, int) for v in length)
                and 0 < length[0] <= length[1]):
            errors.append(f"sound {nid}: length_ms must be [min, max] in ms")
            length = None
        if not isinstance(snd.get("acquired"), bool):
            errors.append(f"sound {nid}: acquired must be true or false")
        if length:
            if "CUE-007" in cues and length[1] > EDGE_MS:
                errors.append(f"sound {nid}: a step longer than one edge ({length[1]} > {EDGE_MS} ms)")
            if "CUE-016" in cues and (length[0] < STING_MS[0] or length[1] > STING_MS[1]):
                errors.append(f"sound {nid}: a result sting must stay within {STING_MS[0]}-{STING_MS[1]} ms")
            if set(cues) & {"CUE-002", "CUE-003"} and length[1] > UI_CLICK_MAX_MS:
                errors.append(f"sound {nid}: a ui click longer than {UI_CLICK_MAX_MS} ms")

    for rid, cue in REQUIRED_ROLES.items():
        if rid not in seen:
            errors.append(f"required role {rid} ({cue}) is missing")
        elif cue not in (seen[rid].get("cues") or []):
            errors.append(f"required role {rid}: must cover {cue}")

    if credits_text is not None:
        for key in list(seen) + list(sources):
            if key not in credits_text:
                errors.append(f"CREDITS-audio.md does not mention {key}")
    return errors


def table(data: dict) -> str:
    sources = {s["id"]: s for s in data["sources"]}
    rows = ["| Звук | CUE | Основной источник | Лицензия | Файлы (подсказка) |", "|---|---|---|---|---|"]
    for snd in data["sounds"]:
        src = sources[snd["primary"]["source"]]
        rows.append(
            f"| `{snd['id']}` | {', '.join(snd['cues'])} | {src['title']} ({src['author']}) | {src['license']} "
            f"| {snd['primary']['file_hint']} |"
        )
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["check", "table"])
    parser.add_argument("--list", type=Path, default=LIST_PATH)
    args = parser.parse_args(argv)
    data = load_json(args.list)
    if args.command == "table":
        sys.stdout.reconfigure(encoding="utf-8")
        print(table(data))
        return 0
    credits = CREDITS_PATH.read_text(encoding="utf-8") if CREDITS_PATH.exists() else ""
    errors = check(data, load_json(CUE_TABLE_PATH), credits)
    sys.stdout.reconfigure(encoding="utf-8")
    for err in errors:
        print(f"FAIL {err}")
    print(f"de013 check: {len(data.get('sounds', []))} sounds, {len(data.get('sources', []))} sources, "
          f"{len(errors)} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
