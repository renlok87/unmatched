"""ENV-MAPS P8.1 (track A): run the whole concept-scene chain headless (no UE, no GPU).

  python -B tools/art/concept_scene/run_scene.py [--steps geom,export,layout,ao,bake,manifest] [--refit]

  geom      ship prep (Blender, only when <work>/ship_raw.npz is missing), ship fit, island, fort, palisade, piles
            (system Python) -> <work>/<Mesh>.pre.npz
  export    cs_blender.py export (headless Blender 5.2, factory startup): MeshBuilder -> UM_FBX_v1 FBX in
            art/pipeline-candidates/ASSET-ENV-S-*/20261002-v1/export/, Smart UV atlas for the imported / procedural
            props, read-back reports, final NPZ (the exported UVs) -> <work>/<Mesh>.npz
  layout    scene_layout.py -> unreal/Unmatched/Config/ArtBoards/EnvLayouts/sarpedon.scene.layout.json
  ao        cs_blender.py ao (Cycles CPU) -> <work>/ao/<Mesh>_AO.png
  bake      bake_albedo.py -> scraped-data/derived/concept-scene/sarpedon/ (gitignored): T_Env_S_<Name>_{BC,N,ORM}.png
            and T_Env_S_AlbedoC0.png
  manifest  tools/art/concept_scene/manifest.sarpedon.json (the track A / B interface)

Locks: none needed (CPU only, no UE / UBT / GPU); Blender runs are separate processes that exit on their own.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import cs_common as CS  # noqa: E402

# name -> (run key, FBX stem, slot, unwrap, sharpDeg, smoothFaces, atlas px, AO px)
MESHES = {
    "Island": ("island", "SM_Env_S_Island", "MI_Env_S_Island", False, 40.0, "npz", 4096, 2048),
    "Ship": ("ship", "SM_Env_S_Ship", "MI_Env_S_Ship", True, 35.0, "all", 4096, 2048),
    "Fort": ("fort", "SM_Env_S_Fort", "MI_Env_S_Fort", True, 30.0, "all", 2048, 1024),
    "Palisade": ("props", "SM_Env_S_Palisade", "MI_Env_S_Palisade", True, 50.0, "all", 2048, 1024),
    "Piles": ("props", "SM_Env_S_Piles", "MI_Env_S_Piles", True, 50.0, "all", 2048, 1024),
    "Banner": ("props", "SM_Env_S_Banner", "MI_EnvCP_Banner", False, None, "all", 0, 0),  # not baked (P7c material)
}


def blender(args, log: Path):
    cmd = [str(CS.BLENDER), "-b", "--factory-startup", "-t", "6", "--python-exit-code", "1", "--python", *args]
    t0 = time.time()
    with open(log, "w", encoding="utf-8") as fh:
        r = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, cwd=str(CS.REPO))
    if r.returncode != 0:
        raise SystemExit(f"blender failed ({r.returncode}): {' '.join(args)} - see {log}")
    return round(time.time() - t0, 1)


def py(script, *args):
    r = subprocess.run([sys.executable, "-B", str(HERE / script), *args], cwd=str(CS.REPO))
    if r.returncode != 0:
        raise SystemExit(f"{script} failed ({r.returncode})")


def step_geom(a):
    if not (CS.WORK / "ship_raw.npz").is_file():
        blender([str(HERE / "ship_build.py"), "--", "prep"], CS.WORK / "logs" / "ship_prep.log")
    py("ship_build.py", "fit", *(["--refit"] if a.refit else []))
    py("island_build.py", "--overlay")
    py("fort_build.py")
    py("palisade_build.py")
    py("piles_build.py")
    py("banner_build.py")
    ms = [CS.Mesh.load(CS.WORK / f"SM_Env_S_{n}.pre.npz") for n in ("Island", "Ship", "Fort", "Palisade", "Piles")]
    px = CS.overlay_meshes(ms, CS.WORK / "overlays" / "scene-silhouette-c0.png", scale=1.0, alpha=0.45,
                           crop=(-384.0, -216.0, 2304.0, 1296.0))
    print("OVERLAY scene-silhouette-c0.png C0 px per mesh (island, ship, fort, palisade, piles):", px)


def export_job():
    jobs = []
    for key, (run, stem, slot, unwrap, sharp, smooth, atlas, _ao) in MESHES.items():
        rd = CS.RUNS[run]
        (rd / "export").mkdir(parents=True, exist_ok=True)
        (rd / "reports" / "fbx-readback").mkdir(parents=True, exist_ok=True)
        jobs.append({"npz": str(CS.WORK / f"{stem}.pre.npz"), "fbx": str(rd / "export" / f"{stem}.fbx"),
                     "final": str(CS.WORK / f"{stem}.npz"), "slots": [slot], "unwrap": unwrap,
                     "unwrapAngleDeg": 60.0, "unwrapMargin": 4.0 / max(atlas, 1024),
                     "sharpDeg": sharp, "smoothFaces": smooth,
                     "readback": str(rd / "reports" / "fbx-readback" / f"{stem}.json")})
    return {"meshes": jobs, "report": str(CS.WORK / "export-report.json")}


def step_export(a):
    (CS.WORK / "logs").mkdir(parents=True, exist_ok=True)
    job = CS.WORK / "export-job.json"
    CS.dump_json(job, export_job())
    sec = blender([str(HERE / "cs_blender.py"), "--", "export", str(job)], CS.WORK / "logs" / "export.log")
    rep = CS.load_json(CS.WORK / "export-report.json")
    # UV0 overlap of the exported atlases (texel centres covered twice at 1024 px) + the final mesh digest
    for e in rep["exports"]:
        m = CS.Mesh.load(CS.WORK / f"{e['name']}.npz")
        ov, cov = CS.uv_overlap_share(m.UV, 1024, mask=None if e["name"] != "SM_Env_S_Banner" else
                                      (m.UV[..., 1] <= 1.0).all(1))
        e["uv0"]["overlapShare1k"] = round(ov, 6)
        e["uv0"]["coveredTexels1k"] = cov
        e["finalMeshDigest"] = m.digest()
    CS.dump_json(CS.WORK / "export-report.json", rep)
    # git-side build reports per run (exports + read-backs)
    by_run = {}
    for e in rep["exports"]:
        run = next(v[0] for v in MESHES.values() if v[1] == e["name"])
        by_run.setdefault(run, []).append(e)
    for run, ex in by_run.items():
        CS.dump_json(CS.RUNS[run] / "reports" / "build-report.json",
                     {"schema": "unmatched.concept-scene.build-report/1",
                      "status": "технически экспортировано (UM_FBX_v1, headless Blender 5.2; no UE import yet)",
                      "generator": {CS.rel(p): CS.text_sha256_lf(p) for p in sorted(HERE.glob("*.py"))
                                    if p.name in ("cs_common.py", "cs_geom.py", "cs_blender.py", "island_build.py",
                                                  "ship_build.py", "fort_build.py", "palisade_build.py",
                                                  "piles_build.py", "banner_build.py", "run_scene.py")},
                      "params": CS.rel(CS.PARAMS_PATH), "paramsSha256": CS.text_sha256_lf(CS.PARAMS_PATH),
                      "exports": ex})
    print(f"EXPORT {len(rep['exports'])} meshes in {sec} s")


def step_ao(a):
    jobs = []
    for key, (run, stem, slot, unwrap, sharp, smooth, atlas, ao) in MESHES.items():
        if not atlas:
            continue
        jobs.append({"final": str(CS.WORK / f"{stem}.npz"), "ao": str(CS.WORK / "ao" / f"{stem}_AO.png"),
                     "size": [ao, ao]})
    P = CS.params()["bake"]
    job = {"meshes": jobs, "samples": P["aoSamples"], "distanceUU": P["aoDistanceUU"], "threads": 6, "marginPx": 8,
           "report": str(CS.WORK / "ao-report.json")}
    CS.dump_json(CS.WORK / "ao-job.json", job)
    sec = blender([str(HERE / "cs_blender.py"), "--", "ao", str(CS.WORK / "ao-job.json")], CS.WORK / "logs" / "ao.log")
    print(f"AO {len(jobs)} meshes in {sec} s")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--steps", default="geom,export,layout,ao,bake,manifest")
    ap.add_argument("--refit", action="store_true")
    a = ap.parse_args(argv)
    (CS.WORK / "logs").mkdir(parents=True, exist_ok=True)
    for s in [x.strip() for x in a.steps.split(",") if x.strip()]:
        t0 = time.time()
        if s == "geom":
            step_geom(a)
        elif s == "export":
            step_export(a)
        elif s == "layout":
            py("scene_layout.py")
        elif s == "ao":
            step_ao(a)
        elif s == "bake":
            py("bake_albedo.py")
        elif s == "manifest":
            py("bake_albedo.py", "--manifest-only")
        else:
            raise SystemExit(f"unknown step {s}")
        print(f"STEP {s} {time.time() - t0:.1f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
