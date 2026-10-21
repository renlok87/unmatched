"""Take a Tripo Studio prop export into its map-kit run, write the ledger rows, env_kit params and the prop status.

    python tools/mapkits/tripo_intake.py check <cost> --balance <studio balance>
    python tools/mapkits/tripo_intake.py log <map> <key> <task_uuid> <op> <quoted> <before> <after> [--units ...]
        # op: generate | texture-2k | pbr | smart-uv | retry ; one ledger row right after each Studio operation
    python tools/mapkits/tripo_intake.py intake <map> <key> <task_uuid> <downloaded.glb> [--date YYYYMMDD] [--move]
        # GLB -> <run>/source/<ID>.glb, sha256 into reports/tripo-run.json, target into scripts/env-kit-params.json

Run folder: art/pipeline-candidates/ASSET-MAPKIT-<MAP>-001/<date>-smartmesh (one per map and day), the layout
tools/art/env_kit/run_env_kit.py reads (source/<ID>.glb, reports/tripo-run.json, scripts/env-kit-params.json). Card of
the ledger: EN-26..EN-29 (docs/game-design/visual/06-tasks/env.csv). Game size: real height x 0.3, trees and
buildings taller than 5 m x 0.15 (NOTES MK-03).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "mapkits"))
import mapkit  # noqa: E402

CARDS = {"baskerville-manor": "EN-26", "soho": "EN-27", "heorot": "EN-28", "sherwood-forest": "EN-29"}
ABBR = {"baskerville-manor": "BSK", "soho": "SOHO", "heorot": "HEO", "sherwood-forest": "SHW"}
BOARD = {"baskerville-manor": "Baskerville", "soho": "Soho", "heorot": "Heorot", "sherwood-forest": "Sherwood"}
MODEL = "Tripo Studio H3.1"
UE_CONTRACT = {"folders": "/Game/EnvKit/<board>/ (flat, the fixed env-kit contract)", "mesh": "SM_Env_<Name>", "textures": {"BC": "sRGB, TC_Default", "N": "sRGB off, TC_Normalmap, flip_green false (PNG is DirectX already)", "ORM": "sRGB off, TC_Masks"}, "material_instance": "MI_Env_<Name>", "fbx_material_slot": "M_Env_<Name> (slot 0; the MI is assigned to it in UE)", "import": "legacy FBX, import_uniform_scale 1.0, import_materials false, import_textures false, collision none (decor, not interactive), build_nanite false"}
LEDGER = [sys.executable, str(ROOT / "tools" / "art" / "visual" / "ledger.py")]


def asset_id(m: str, key: str) -> str:
    return f"MK-{ABBR[m]}-{key.upper()}"


def ue_name(m: str, key: str) -> str:
    return BOARD[m] + "".join(w.capitalize() for w in key.split("-"))


def target_uu(p: dict) -> float:
    h = p["sizeM"][2]
    return round(h * (0.15 if h > 5.0 else 0.3) * 100, 1)


def run_dir(m: str, date: str) -> Path:
    return ROOT / "art" / "pipeline-candidates" / f"ASSET-MAPKIT-{m.upper()}-001" / f"{date}-smartmesh"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _json(p: Path, default: dict) -> dict:
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else default


def _write(p: Path, d: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def check(cost: float, balance: float) -> int:
    return subprocess.call(LEDGER + ["check", "--service", "tripo", "--next-cost", str(cost), "--balance", str(balance),
                                     "--model", MODEL])


OPS = {"generate": ("", "этап 2 пропа: Smart Mesh P2.0"), "texture-2k": ("#texture-2k", "этап 2 пропа: текстура 2K, Удалить освещение"),
       "texture-4k": ("#texture-4k", "этап 2 пропа: текстура 4K (P0), Удалить освещение"),
       "pbr": ("#pbr", "этап 2 пропа: PBR"), "smart-uv": ("#smart-uv", "этап 2 пропа: Smart UV"),
       "retry": ("#retry", "этап 2 пропа: бесплатный повтор"), "multiview": ("", "этап 2 пропа: multi-view H3.1 (сравнение маршрута)")}


def log(m: str, key: str, task: str, op: str, quoted: float, before: float, after: float, units: str | None,
        note: str | None, status: str) -> int:
    p = mapkit.prop(m, key)
    suffix, default_note = OPS[op]
    cmd = LEDGER + ["add", "--task", CARDS[m], "--template", "T-TRIPO-PART", "--service", "Tripo", "--model", MODEL,
                    "--units", units or f"{op}: {p['nameEn']} ({asset_id(m, key)})", "--quoted", str(quoted),
                    "--before", str(before), "--after", str(after), "--service-task-id", task + suffix,
                    "--result", f"art/pipeline-candidates/ASSET-MAPKIT-{m.upper()}-001/", "--status", status,
                    "--note", (note or default_note) + f"; map kit {m}/{key}"]
    rc = subprocess.call(cmd)
    if rc == 0:
        st = mapkit.load_status(m)
        e = st["props"].setdefault(key, {"stage": "listed"})
        t = e.setdefault("tripo", {})
        t["taskId"] = task
        ops = t.setdefault("ops", [])
        ops.append({"op": op, "quoted": quoted, "before": before, "after": after, "status": status})
        t["credits"] = round(sum(o["before"] - o["after"] for o in ops if o["status"] == "ok"), 1)
        if e.get("stage") in ("listed", "views"):
            e["stage"] = "tripo"
        mapkit.save_status(m, st)
    return rc


def intake(m: str, key: str, task: str, glb: Path, date: str, move: bool) -> dict:
    sys.path.insert(0, str(ROOT / "tools" / "tripo-pipeline"))
    from tripo_pipeline import inspect_glb  # noqa: E402
    p = mapkit.prop(m, key)
    aid = asset_id(m, key)
    run = run_dir(m, date)
    src = run / "source" / f"{aid}.glb"
    src.parent.mkdir(parents=True, exist_ok=True)
    (shutil.move if move else shutil.copy2)(str(glb), str(src))
    b = src.read_bytes()
    if b[:4] != b"glTF":
        sys.exit(f"ERROR {src} is not a GLB")
    g = inspect_glb(src)
    st = mapkit.load_status(m)
    e = st["props"].setdefault(key, {"stage": "tripo"})
    views = e.get("views") or {}
    refs = {}
    for name in ("front", "side"):
        if views.get(name):
            refs[name if name == "front" else views.get("slot", "side")] = sha256(ROOT / views[name])
    tr = _json(run / "reports" / "tripo-run.json",
               {"schema": "unmatched.tripo-run/1", "asset": f"ASSET-MAPKIT-{m.upper()}-001", "runId": run.name,
                "date": date, "chain": "Smart Mesh P2.0 (multi-view slots) -> Texture 2K Remove Lighting -> PBR",
                "purpose": f"map kit {m}: props for a future board (asset preparation, NOTES MK-02)", "assets": {}})
    tr["assets"][aid] = {"key": key, "tripoTask": task, "source": f"source/{aid}.glb", "sha256": sha256(src),
                         "bytes": len(b), "meshes": g["mesh_count"], "triangles": g["triangles"],
                         "materials": g["materials"], "images": g["images"],
                         "refs": {"front": views.get("front"), views.get("slot", "side"): views.get("side")},
                         "refsSha256": refs, "credits": (e.get("tripo") or {}).get("ops", [])}
    _write(run / "reports" / "tripo-run.json", tr)
    par = _json(run / "scripts" / "env-kit-params.json", {
        "schema": "unmatched.env-kit.params/1",
        "_purpose": f"tools/art/env_kit params of map kit {m}, run {run.name}: Tripo Smart Mesh props (NOTES MK-05); "
                    "target = real height x 0.3, > 5 m x 0.15 (MK-03).",
        "run_dir": str(run.relative_to(ROOT)).replace("\\", "/"),
        "scratch_dir": f"C:/tmp/mapkits/{m}/{run.name}",
        "refs_dir": f"C:/tmp/mapkits/{m}/{run.name}/refs",
        "fbx_preset": "blender/_tools/presets/UM_FBX_v1.json", "texture_size": 2048, "uv_raster_size": 1024,
        "normal_padding_px_source": 32, "bake_ao": False, "max_triangles": 12000, "isolated_gap_uu": 0.5,
        "orientation": {"raster_px": 192, "apply_min_iou_gain": 0.05}, "ue": UE_CONTRACT, "assets": {}})
    par["assets"][aid] = {"name": ue_name(m, key), "board": BOARD[m],
                          "target": {"dimension": "height", "uu": target_uu(p)},
                          "yaw_deg": 0, "_yaw": "Smart Mesh keeps the FRONT slot as glTF +Z; orientation_check needs 4 refs, we have 2"}
    _write(run / "scripts" / "env-kit-params.json", par)
    # refs for orientation_check: <refs_dir>/<ID>/{front,left|back}.png
    rd = Path(par["refs_dir"]) / aid
    rd.mkdir(parents=True, exist_ok=True)
    for slot, path in (("front", views.get("front")), (views.get("slot", "left"), views.get("side"))):
        if path:
            shutil.copy2(ROOT / path, rd / f"{slot}.png")
    e["tripo"] = {**(e.get("tripo") or {}), "taskId": task, "route": "smart-mesh-p2", "glb": str(src.relative_to(ROOT)).replace("\\", "/"),
                  "run": str(run.relative_to(ROOT)).replace("\\", "/"), "assetId": aid, "triangles": g["triangles"]}
    if e.get("stage") in ("listed", "views"):
        e["stage"] = "tripo"
    mapkit.save_status(m, st)
    return {"asset": aid, "glb": str(src), "triangles": g["triangles"], "meshes": g["mesh_count"],
            "images": g["images"], "target_uu": target_uu(p)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("check"); a.add_argument("cost", type=float); a.add_argument("--balance", type=float, required=True)
    a = sub.add_parser("log")
    for n in ("map", "key", "task", "op"):
        a.add_argument(n)
    for n in ("quoted", "before", "after"):
        a.add_argument(n, type=float)
    a.add_argument("--units"); a.add_argument("--note"); a.add_argument("--status", default="ok", choices=["ok", "failed", "refunded"])
    a = sub.add_parser("intake")
    for n in ("map", "key", "task"):
        a.add_argument(n)
    a.add_argument("glb", type=Path); a.add_argument("--date", default=dt.date.today().strftime("%Y%m%d"))
    a.add_argument("--move", action="store_true")
    args = ap.parse_args()
    if args.cmd == "check":
        sys.exit(check(args.cost, args.balance))
    if args.cmd == "log":
        if args.op not in OPS:
            sys.exit(f"ERROR op {args.op!r} not in {sorted(OPS)}")
        sys.exit(log(args.map, args.key, args.task, args.op, args.quoted, args.before, args.after, args.units,
                     args.note, args.status))
    print(json.dumps(intake(args.map, args.key, args.task, args.glb, args.date, args.move), ensure_ascii=False))


if __name__ == "__main__":
    main()
