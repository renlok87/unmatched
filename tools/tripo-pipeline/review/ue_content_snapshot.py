"""Snapshot of protected content folders in the LIVE editor + on disk (before/after evidence).

    python tools/tripo-pipeline/review/ue_content_snapshot.py <out.json> [--compare <before.json>]

For every folder in FOLDERS: MCP AssetTools.find_assets (recursive) and is_dirty per asset, plus
SHA-256/size of every file under the matching unreal/Unmatched/Content/<dir>. The editor state
(dirty packages, current level, Interchange cvars) comes from ue_py/editor_state.py run through
the editor console. With --compare, prints and stores the difference against an earlier snapshot
(new/removed/changed assets and files) and exits 1 if a PROTECTED folder changed.
Read only: nothing is loaded for editing, saved or deleted.
"""

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from ue_live import Ue  # noqa: E402

REPO = HERE.parents[2]
CONTENT = REPO / "unreal/Unmatched/Content"
PROTECTED = ("/Game/ART004", "/Game/ArtPreview")
FOLDERS = PROTECTED + ("/Game/PipelineCandidates",)


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def disk(folder):
    root = CONTENT / folder[len("/Game/"):]
    files = {}
    if root.is_dir():
        for p in sorted(root.rglob("*")):
            if p.is_file():
                files[p.relative_to(CONTENT).as_posix()] = {"sha256": sha(p), "bytes": p.stat().st_size}
    return files


def take(ue, out_json):
    data = {"taken_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
            "tool": "tools/tripo-pipeline/review/ue_content_snapshot.py", "folders": {}}
    for folder in FOLDERS:
        assets = sorted(ue.call("asset", "find_assets", {"folder_path": folder, "name": "", "recursive": True},
                                record=False) or [])
        dirty = sorted(a for a in assets if ue.call("asset", "is_dirty", {"asset_path": a}, record=False))
        data["folders"][folder] = {"assets": assets, "count": len(assets), "dirty": dirty, "disk_files": disk(folder)}
    state_json = Path(out_json).resolve().with_suffix(".editor-state.tmp.json").as_posix()
    data["editor"] = ue.py_file(str(HERE / "ue_py" / "editor_state.py"), state_json, timeout=120, args=state_json)
    os.remove(state_json)
    return data


def diff(before, after):
    out = {}
    for folder in FOLDERS:
        b, a = before["folders"].get(folder, {}), after["folders"].get(folder, {})
        ba, aa = set(b.get("assets", [])), set(a.get("assets", []))
        bf, af = b.get("disk_files", {}), a.get("disk_files", {})
        out[folder] = {
            "assets_added": sorted(aa - ba), "assets_removed": sorted(ba - aa),
            "files_added": sorted(set(af) - set(bf)), "files_removed": sorted(set(bf) - set(af)),
            "files_changed": sorted(k for k in set(af) & set(bf) if af[k]["sha256"] != bf[k]["sha256"]),
            "dirty_after": a.get("dirty", []),
        }
        out[folder]["unchanged"] = not any(v for k, v in out[folder].items())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--compare")
    args = ap.parse_args()
    ue = Ue()
    data = take(ue, args.out)
    rc = 0
    if args.compare:
        before = json.loads(Path(args.compare).read_text(encoding="utf-8"))
        data["compare"] = {"against": Path(args.compare).name, "diff": diff(before, data)}
        data["compare"]["protected_unchanged"] = all(data["compare"]["diff"][f]["unchanged"] for f in PROTECTED)
        rc = 0 if data["compare"]["protected_unchanged"] else 1
    Path(args.out).write_text(json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8",
                              newline="\n")
    summary = {f: data["folders"][f]["count"] for f in FOLDERS}
    summary["editor_dirty"] = {"maps": data["editor"]["dirty_maps"], "content": data["editor"]["dirty_content"]}
    if args.compare:
        summary["protected_unchanged"] = data["compare"]["protected_unchanged"]
        summary["pipeline_candidates_added"] = data["compare"]["diff"]["/Game/PipelineCandidates"]["assets_added"]
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return rc


if __name__ == "__main__":
    sys.exit(main())
