#!/usr/bin/env python3
"""ENV-MAPS P3 live: package/build record + strict sidecars (<frame>.evidence.json, schema
unmatched.evidence-frame/1) for every published PNG of the given run dirs; extends manifest.json.
Usage: python sidecars.py <evidence-root> <run-dir> [<run-dir> ...]"""
import json, sys
from pathlib import Path

WT = Path(r"C:\tmp\wt-envmaps")
sys.path.insert(0, str(WT / "tools" / "art"))
import art004_live_k2 as L  # noqa: E402

root = Path(sys.argv[1]).resolve()
pkg_path = root / "package-record.json"
inner = L.sha256_file(L.STAGED_INNER_EXE)
bins = L.sha256_file(L.BIN_EXE)
paks = {p.name: L.sha256_file(p) for p in sorted((L.STAGE_ROOT / "Unmatched" / "Content" / "Paks").glob("*")) if p.is_file()}
pkg = {"schema": "unmatched.envmaps-p3-package-record/1",
       "label": "ENV-MAPS P3 package (worktree feat/env-original-maps, HEAD 9f1c66c4)",
       "result": "Succeeded",
       "flags": "Build.bat Unmatched Win64 Development -NoXGE -MaxParallelActions=6 (no -NoLiveCoding); "
                "tools/s08/package-client.ps1 -SkipBuild",
       "withLiveCodingValues": ["WITH_LIVE_CODING=1"],
       "log": "C:/tmp/envmaps-research/p3/package/{build-g.out.log,build-g.ubt.log,uat.log} (outside git): "
              "'Result: Succeeded', 'BUILD SUCCESSFUL', cook 'Success - 0 error(s), 0 warning(s)'",
       "exe": {"binariesSha256": bins, "stagedInnerSha256": inner,
               "stagedRootStubSha256": L.sha256_file(L.STAGED_ROOT_EXE)},
       "paks": paks,
       "note": "inner staged exe == Binaries/Win64 exe; the staged root exe is a launcher stub"}
assert bins == inner, (bins, inner)
L.write_json(pkg_path, pkg)
for rd in sys.argv[2:]:
    run_dir = Path(rd).resolve()
    rec = json.loads((run_dir / "run-record.json").read_text(encoding="utf-8"))
    status = json.loads((run_dir / "art-preview-status.json").read_text(encoding="utf-8-sig")) if (run_dir / "art-preview-status.json").is_file() else {}
    board = "c121b47f8d6eb28daccb76d05" if "marmoreal" in str(run_dir) else "c7fa64a26c29a0835f2383e63"
    for png in sorted(run_dir.rglob("*.png")):
        side = {"schema": L.SIDECAR_SCHEMA, "class": "packaged-live",
                "frame": png.relative_to(run_dir).as_posix(), "frameSha256": L.sha256_file(png),
                "build": {"label": pkg["label"], "result": pkg["result"], "flags": pkg["flags"], "log": pkg["log"],
                          "withLiveCoding": pkg["withLiveCodingValues"], "exeSha256": bins,
                          "stagedInnerExeSha256": inner, "buildRecord": L.rel(pkg_path), "packageRecord": L.rel(pkg_path)},
                "run": {"boardId": status.get("boardId", board), "roomStatus": rec["roomStatus"], "zoom": 0,
                        "clientFps": 30, "cleanupLine": rec["cleanupLine"],
                        "demo": "tools/s08/run-phase2-demo.ps1" if rec["kind"] == "phase2" else "tools/s09/run-combat-demo.ps1"},
                "status": "измерено (packaged-live кадр оригинальной карты с окружением; художественная приёмка не выполнялась)"}
        L.write_json(png.with_name(png.stem + ".evidence.json"), side)
    man = run_dir / "manifest.json"
    doc = json.loads(man.read_text(encoding="utf-8-sig"))
    listed = {e["name"].replace("\\", "/"): e for e in doc["files"]}
    for f in sorted(run_dir.rglob("*")):
        if f.is_file() and f.name != "manifest.json":
            name = f.relative_to(run_dir).as_posix()
            entry = {"name": name, "bytes": f.stat().st_size, "sha256": L.sha256_file(f)}
            if name in listed:
                listed[name].update(entry)
            else:
                doc["files"].append(entry)
    man.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("sidecars", run_dir.name, len(list(run_dir.rglob("*.evidence.json"))))
