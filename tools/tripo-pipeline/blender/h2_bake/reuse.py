"""Stage ledger, stage fingerprints and --reuse-from of the H2 bake driver (plain Python, no bpy; h2-bake 0.7.0, W1-d
2026-10-14: RC-07, RC-08). Driver: run_h2_bake.py.

Stage ledger work/stages.json (not in git, like the rest of work/): every h2 stage that finishes records its
fingerprint, its outputs (run-relative path -> bytes) and its wall time; a stage that starts drops its own record and
the records of every later stage (their inputs are about to change). The manifest stage copies the fingerprints to
reports/run-manifest.json#stages.

Fingerprint of a stage (STAGE_INPUTS): sha256 of each profile block / sub-key the stage reads (`profile`), sha256 of the
code it runs (`code`: its h2_bake modules, candidate_build and anim helpers; __init__.py = VERSION only, not code), of
the other input files (`files`: rig contract, FBX preset, files named in the preview block) and the Blender version.
Outputs of the earlier stages are inputs too: they are covered by the chain (a stage is reused only when every earlier
stage is reused).

--reuse-from <old run> (new, empty run directory; `--stages all`): walking ORDER, a stage is reused while its
profile blocks, input files and Blender version equal those of the old run, its code too (or --reuse-allow-code-drift:
then the drift is listed and the full determinism repeat is required) and the old run finished it. From the first
stage that differs everything is recomputed; `manifest` always is. Old-run evidence: work/stages.json, or for a run
made before the ledger (h2-bake <= 0.6.1) reports/run-manifest.json (its profile file must still have the recorded
sha256; module sha256 = the code at the manifest stage; anim helpers, rig contract and preview files were not
recorded there, so rig and later stages of such a run are never reused).
Reused stages: files owned by the stage (OWNERS) are hard-linked from the old run (copy when a link is impossible),
JSON reports are copied with the run path rewritten and a top-level `reused_from`; work/params/* are not carried;
files no stage owns are copied (listed). Before any stage runs, its own files that are hard links are unlinked
(unshare) so that no write reaches the old run; after it, a changed hard-linked file of another stage stops the run."""

import fnmatch
import hashlib
import json
import os
import shutil
import time
from pathlib import Path

LEDGER = "work/stages.json"
LEDGER_SCHEMA = "unmatched.h2-bake-stages/1"
RUN_SCHEMA = "unmatched.h2-bake-run/1"
ORDER = ("prepare", "retopo", "close", "uv", "bake", "aux", "textures", "rig", "probes", "seams", "preview", "compose",
         "manifest")
REUSABLE = ORDER[:-1]  # manifest: always recomputed (it hashes the outputs of this run)
PKG = "tools/tripo-pipeline/blender/h2_bake/"
CB = "tools/tripo-pipeline/blender/candidate_build/"
ANIM = "tools/tripo-pipeline/anim/"
CONTRACT = "docs/art-pipeline/rig/rig-contract.json"
BLENDER_COMMON = (PKG + "blender_entry.py", PKG + "bl_util.py", PKG + "profile.py")

# profile: top-level keys or dotted sub-keys the stage reads; code: files it runs; files: other inputs ("@exports.fbx_preset"
# = the path in that key, "@preview" = every existing repo file named in the preview block); blender: runs Blender.
STAGE_INPUTS = {
    "prepare": {"profile": ("schema", "asset_id", "expected_part_count", "sources", "parts", "scale", "prepare", "orientation"),
                "code": BLENDER_COMMON + (PKG + "st_prepare.py",), "blender": True},
    "retopo": {"profile": ("parts", "orientation", "retopo"),
               "code": BLENDER_COMMON + (PKG + "st_retopo.py", CB + "closure.py"), "blender": True},
    "close": {"profile": ("parts", "closure"),
              "code": BLENDER_COMMON + (PKG + "st_close.py", PKG + "raycam.py", CB + "closure.py"), "blender": True},
    "uv": {"profile": ("parts", "closure", "uv", "textures.team_mask.base_band"),
           "code": BLENDER_COMMON + (PKG + "st_uv.py", PKG + "charts.py"), "blender": True},
    "bake": {"profile": ("parts", "bake"), "code": BLENDER_COMMON + (PKG + "st_bake.py",), "blender": True},
    "aux": {"profile": ("parts", "bake"), "code": BLENDER_COMMON + (PKG + "st_aux.py", PKG + "st_bake.py"), "blender": True},
    "textures": {"profile": ("parts", "textures"),
                 "code": (PKG + "profile.py", PKG + "textures.py", PKG + "materials.py"), "blender": False},
    "rig": {"profile": ("parts", "retopo", "textures.prefix", "rig", "sockets", "exports", "meshes", "materials"),
            "code": BLENDER_COMMON + (PKG + "st_rig.py", CB + "core.py", CB + "measure.py"),
            "files": (CONTRACT, "@exports.fbx_preset"), "blender": True},
    "probes": {"profile": ("asset_id", "exports", "rig"),
               "code": (PKG + "profile.py", PKG + "run_h2_bake.py", PKG + "fbx_authored.py", ANIM + "rig_deform_probe.py",
                        ANIM + "overlay_bones.py", ANIM + "validate_clip.py"),
               "files": (CONTRACT,), "blender": True},
    "seams": {"profile": ("parts", "meshes", "rig", "closure", "seams", "preview.k2", "textures.prefix"),
              "code": BLENDER_COMMON + (PKG + "st_seams.py", PKG + "st_close.py", PKG + "raycam.py", CB + "closure.py"),
              "blender": True},
    "preview": {"profile": ("parts", "scale", "meshes", "rig", "textures", "preview"),
                "code": BLENDER_COMMON + (PKG + "st_preview.py", PKG + "st_seams.py", PKG + "framing.py"),
                "files": ("@preview",), "blender": True},
    "compose": {"profile": ("sources", "meshes", "textures", "seams", "preview"), "code": (PKG + "profile.py", PKG + "compose.py"),
                "files": ("@preview",), "blender": False},
}
# top-level keys no stage reads (notes and bookkeeping): a change there recomputes nothing. Any other key that no stage
# lists is treated as read by prepare (a new key recomputes everything until it is mapped).
METADATA_KEYS = ("profile_id", "profile_version", "status", "status_note", "note", "parts_note", "history",
                 "proposed_budget", "axes")
# stage that owns each run-relative path: first match wins (fnmatch: `*` crosses `/`); None = never carried over
OWNERS = (
    ("work/stages.json", None), ("work/timings.json", None), ("reports/run-manifest.json", "manifest"),
    ("reports/determinism-report.json", None),
    ("work/hp.blend*", "prepare"), ("reports/prepare-report.json", "prepare"),
    ("work/lp.blend*", "retopo"), ("reports/retopo-report.json", "retopo"),
    ("work/lp_closed.blend*", "close"), ("reports/close-report.json", "close"),
    ("work/uv/position*.npy", "aux"), ("work/uv/metal_mask.npy", "textures"),
    ("work/lp_uv.blend*", "uv"), ("work/uv/*", "uv"), ("preview/uv-layout-1024.png", "uv"), ("reports/uv-report.json", "uv"),
    ("work/bake/AO_EX*", "aux"), ("work/bake/AO_CTRL*", "aux"), ("work/bake/aux-timing.json", "aux"),
    ("reports/aux-report.json", "aux"),
    ("work/bake/*", "bake"), ("reports/bake-report.json", "bake"),
    ("textures/*", "textures"), ("reports/textures-report.json", "textures"),
    ("work/rig/*", "rig"), ("work/sk_authored.blend*", "rig"), ("export/*", "rig"), ("reports/rig-report.json", "rig"),
    ("work/deform/*", "probes"), ("work/probe-fbx-authored.blend*", "probes"), ("reports/deform/*", "probes"),
    ("reports/validate-skeletal-mesh-v2.json", "probes"), ("reports/probes-report.json", "probes"),
    ("logs/probe-*.log", "probes"), ("logs/validate-skeletal-mesh.log", "probes"),
    ("work/seams_raw/*", "seams"), ("reports/seams-report.json", "seams"),
    ("work/preview_raw/*", "preview"), ("reports/preview-report.json", "preview"),
    ("preview/*.jpg", "compose"), ("reports/compose-report.json", "compose"),
    ("reports/decimation-curve.json", "curve"),
)
DONE_MARKERS = {"prepare": ("reports/prepare-report.json",), "retopo": ("reports/retopo-report.json",),
                "close": ("reports/close-report.json",), "uv": ("reports/uv-report.json",),
                "bake": ("reports/bake-report.json",), "aux": ("reports/aux-report.json",),
                "textures": ("reports/textures-report.json",), "rig": ("reports/rig-report.json",),
                "probes": ("reports/probes-report.json",), "seams": ("reports/seams-report.json",),
                "preview": ("reports/preview-report.json",), "compose": ("reports/compose-report.json",)}


class ReuseError(RuntimeError):
    pass


# ------------------------------------------------------------------ basics
def sha256(path):
    d = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            d.update(chunk)
    return d.hexdigest()


def sha_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def owner(rel):
    """Stage that owns the run-relative posix path: a stage name, None (never carried), or "" (no stage owns it)."""
    for stage in ORDER + ("curve",):
        if rel in ("work/params/%s.json" % stage, "logs/%s.log" % stage):
            return stage
    for pattern, stage in OWNERS:
        if fnmatch.fnmatchcase(rel, pattern):
            return stage
    return ""


def run_files(run_dir):
    run_dir = Path(run_dir)
    if not run_dir.is_dir():
        return {}
    return {p.relative_to(run_dir).as_posix(): p for p in sorted(run_dir.rglob("*")) if p.is_file()}


def select(profile, key):
    node = profile
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def unmapped_keys(profile):
    listed = {k.split(".")[0] for spec in STAGE_INPUTS.values() for k in spec["profile"]}
    return sorted(k for k in profile if k not in listed and k not in METADATA_KEYS)


def profile_keys(stage, profile):
    keys = list(STAGE_INPUTS[stage]["profile"])
    if stage == "prepare":
        keys += unmapped_keys(profile)
    return keys


def preview_files(profile, repo):
    """Repo-relative paths of existing files named anywhere in the preview block (concepts, frame.checks_report, ...)."""
    found = set()

    def walk(node):
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
        elif isinstance(node, str) and ("/" in node or "\\" in node) and len(node) < 400:
            p = Path(node) if Path(node).is_absolute() else Path(repo) / node
            try:
                if p.is_file():
                    found.add(node.replace("\\", "/"))
            except OSError:
                pass

    walk(profile.get("preview"))
    return sorted(found)


def input_files(stage, profile, repo):
    out = []
    for f in STAGE_INPUTS[stage].get("files", ()):
        if f == "@exports.fbx_preset":
            out.append(profile["exports"]["fbx_preset"])
        elif f == "@preview":
            out += preview_files(profile, repo)
        else:
            out.append(f)
    return out


def fingerprint(stage, profile, repo, blender_version, code_sha=None, file_sha=None):
    """Fingerprint of `stage` for `profile`. code_sha / file_sha: rel path -> sha256 or None (unknown); default: hash the
    files of this checkout (a missing file -> None)."""
    repo = Path(repo)

    def here(rel):
        p = Path(rel) if Path(rel).is_absolute() else repo / rel
        return sha256(p) if p.is_file() else None

    code_sha = code_sha or here
    file_sha = file_sha or here
    spec = STAGE_INPUTS[stage]
    return {"profile": {k: sha_json(select(profile, k)) for k in profile_keys(stage, profile)},
            "code": {c: code_sha(c) for c in spec["code"]},
            "files": {f: file_sha(f) for f in input_files(stage, profile, repo)},
            "blender": blender_version if spec.get("blender") else None}


def chain(fps):
    """sha256 over the fingerprints of the stages in order (manifest record)."""
    out, acc = {}, ""
    for stage in REUSABLE:
        if stage in fps:
            acc = sha_json([acc, fps[stage]])
            out[stage] = acc
    return out


def differences(new, old):
    """-> (changes, code_drift): what differs between two fingerprints of one stage. changes block reuse; code_drift
    blocks it unless --reuse-allow-code-drift."""
    changes, drift = [], []
    for k, v in new["profile"].items():
        if old["profile"].get(k, "<absent>") != v:
            changes.append("profile %s" % k)
    for k in old["profile"]:
        if k not in new["profile"]:
            changes.append("profile %s (no longer read)" % k)
    for f, v in new["files"].items():
        o = old["files"].get(f)
        if o is None:
            changes.append("file %s not recorded in the old run" % f)
        elif o != v:
            changes.append("file %s" % f)
    for f in old["files"]:
        if f not in new["files"]:
            changes.append("file %s no longer an input" % f)
    if new.get("blender") != old.get("blender"):
        changes.append("blender %s -> %s" % (old.get("blender"), new.get("blender")))
    for c, v in new["code"].items():
        o = old["code"].get(c)
        if o != v:
            drift.append(c.rsplit("/", 1)[-1] + ("" if o else " (not recorded in the old run)"))
    return changes, drift


# ------------------------------------------------------------------ ledger
def load_ledger(run_dir):
    path = Path(run_dir) / LEDGER
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != LEDGER_SCHEMA:
        raise ReuseError("%s: schema %r" % (path, data.get("schema")))
    return data


def save_ledger(run_dir, data):
    path = Path(run_dir) / LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def new_ledger():
    return {"schema": LEDGER_SCHEMA, "stages": {}}


def invalidate_from(run_dir, stage):
    """A stage starts: drop its record and the records of every later stage."""
    if stage not in ORDER:
        return
    data = load_ledger(run_dir) or new_ledger()
    later = ORDER[ORDER.index(stage):]
    data["stages"] = {k: v for k, v in data["stages"].items() if k not in later}
    save_ledger(run_dir, data)


def stage_outputs(run_dir, stage):
    return {rel: p.stat().st_size for rel, p in run_files(run_dir).items() if owner(rel) == stage}


def record(run_dir, stage, fp, profile_path, profile_sha, seconds, reused_from=None, extra=None):
    data = load_ledger(run_dir) or new_ledger()
    entry = {"status": "ok", "fingerprint": fp, "profile": {"path": profile_path, "sha256": profile_sha},
             "outputs": stage_outputs(run_dir, stage), "seconds": seconds,
             "finished": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "reused_from": reused_from}
    if extra:
        entry.update(extra)
    data["stages"][stage] = entry
    save_ledger(run_dir, data)


# ------------------------------------------------------------------ hard-link safety
def snapshot_links(run_dir):
    """{rel: (size, mtime_ns)} of the files of the run that are hard links (st_nlink > 1)."""
    out = {}
    for rel, p in run_files(run_dir).items():
        st = p.stat()
        if st.st_nlink > 1:
            out[rel] = (st.st_size, st.st_mtime_ns)
    return out


def unshare(run_dir, stage):
    """Unlink the files of `stage` that are hard links before the stage writes them (np.save / PIL open the existing
    file and would write into the old run). -> number of links removed."""
    n = 0
    for rel, p in run_files(run_dir).items():
        if owner(rel) == stage and p.stat().st_nlink > 1:
            p.unlink()
            n += 1
    return n


def check_links(run_dir, before, stage):
    """After a stage: a hard-linked file of another stage changed in place = the ownership map misses an output."""
    changed = []
    for rel, (size, mtime) in before.items():
        p = Path(run_dir) / rel
        if p.is_file():
            st = p.stat()
            if st.st_nlink > 1 and (st.st_size, st.st_mtime_ns) != (size, mtime):
                changed.append(rel)
    if changed:
        raise ReuseError("stage %s wrote into hard-linked files of another stage: %s — the old run shares them and is "
                         "modified; add the paths to reuse.OWNERS" % (stage, changed))


# ------------------------------------------------------------------ old run evidence
def source_records(source, repo, profile_loader):
    """-> (kind, {stage: {"fingerprint": fp, "done": bool, "why": str}}) of the old run: its ledger, or for a run older
    than the ledger its run-manifest.json."""
    source = Path(source)
    ledger = load_ledger(source)
    if ledger is not None:
        out = {}
        for stage in REUSABLE:
            e = ledger["stages"].get(stage)
            if not e or e.get("status") != "ok":
                out[stage] = {"fingerprint": None, "done": False, "why": "no ok record in work/stages.json"}
                continue
            missing = [rel for rel, size in e.get("outputs", {}).items()
                       if not (source / rel).is_file() or (source / rel).stat().st_size != size]
            out[stage] = {"fingerprint": e["fingerprint"], "done": not missing,
                          "why": "outputs missing or resized since the record: %s" % missing[:5] if missing else "",
                          "reused_from": e.get("reused_from")}
        return "ledger", out
    mpath = source / "reports" / "run-manifest.json"
    if not mpath.is_file():
        raise ReuseError("%s has neither work/stages.json nor reports/run-manifest.json: nothing to reuse from" % source)
    m = json.loads(mpath.read_text(encoding="utf-8"))
    if m.get("schema") != RUN_SCHEMA:
        raise ReuseError("%s: not an h2 bake run (schema %r)" % (mpath, m.get("schema")))
    ppath = Path(m["profile"]["path"])
    ppath = ppath if ppath.is_absolute() else Path(repo) / ppath
    if not ppath.is_file() or sha256(ppath) != m["profile"]["sha256"]:
        raise ReuseError("old run %s: its profile %s is missing or changed since the run (sha256 %s): the blocks it "
                         "was built from are unknown" % (source, m["profile"]["path"], m["profile"]["sha256"][:12]))
    old_profile = profile_loader(ppath)
    code = {PKG + k: v for k, v in (m.get("modules") or {}).items()}
    deps = dict(m.get("read_only_dependencies") or {})
    code.update(deps)
    outputs = m.get("outputs") or {}
    out = {}
    for stage in REUSABLE:
        fp = fingerprint(stage, old_profile, repo, m.get("blender"), code_sha=lambda c: code.get(c),
                         file_sha=lambda f: deps.get(f))
        missing = [r for r in DONE_MARKERS[stage] if not (source / r).is_file()]
        why = ""
        if missing:
            why = "no %s" % ", ".join(missing)
        else:
            for r in DONE_MARKERS[stage]:
                try:
                    if json.loads((source / r).read_text(encoding="utf-8")).get("passed") is False:
                        why = "%s: passed false" % r
                except ValueError:
                    why = "%s unreadable" % r
        if not why:  # outputs recorded by the manifest must still be the same bytes
            bad = [rel for rel, v in outputs.items() if owner(rel) == stage
                   and (not (source / rel).is_file() or sha256(source / rel) != v["sha256"])]
            if bad:
                why = "outputs changed since run-manifest.json: %s" % bad[:5]
        out[stage] = {"fingerprint": fp, "done": not why, "why": why}
    return "run-manifest.json (run older than the stage ledger)", out


# ------------------------------------------------------------------ plan and apply
def plan(source, profile, repo, blender_version, profile_loader, allow_code_drift=False):
    """-> {"source", "evidence", "stages": [{stage, action: reuse|recompute, changes, code_drift, why}], "reused",
    "recomputed", "code_drift"}."""
    kind, old = source_records(source, repo, profile_loader)
    rows, reused, drift_all, broken = [], [], {}, None
    for stage in ORDER:
        if stage == "manifest":
            rows.append({"stage": stage, "action": "recompute", "why": "always (hashes the outputs of this run)"})
            continue
        new_fp = fingerprint(stage, profile, repo, blender_version)
        rec = old.get(stage) or {}
        row = {"stage": stage}
        if broken:
            row.update(action="recompute", why="after %s" % broken)
        elif not rec.get("done"):
            row.update(action="recompute", why="old run: %s" % (rec.get("why") or "stage not finished"))
        else:
            changes, drift = differences(new_fp, rec["fingerprint"])
            row.update(changes=changes, code_drift=drift)
            if changes:
                row.update(action="recompute", why="changed: %s" % "; ".join(changes))
            elif drift and not allow_code_drift:
                row.update(action="recompute", why="code changed: %s (--reuse-allow-code-drift reuses it)" % ", ".join(drift))
            else:
                row.update(action="reuse", why="unchanged" + (" (code drift allowed: %s)" % ", ".join(drift) if drift else ""))
                if drift:
                    drift_all[stage] = drift
        row["fingerprint"] = new_fp
        if row["action"] == "reuse":  # the ledger of the new run keeps the provenance of the reused outputs
            row["old_fingerprint"] = rec["fingerprint"]
            reused.append(stage)
        elif broken is None:
            broken = stage
        rows.append(row)
    return {"source": str(Path(source).resolve()), "evidence": kind, "stages": rows, "reused": reused,
            "recomputed": [r["stage"] for r in rows if r["action"] == "recompute"], "code_drift": drift_all,
            "first_recomputed": broken}


def _rel(path, repo):
    try:
        return Path(path).resolve().relative_to(Path(repo).resolve()).as_posix()
    except ValueError:
        return Path(path).resolve().as_posix()


def run_tokens(run_dir, repo):
    r = Path(run_dir).resolve()
    pairs = []
    try:
        pairs.append(("rel", r.relative_to(Path(repo).resolve()).as_posix()))
    except ValueError:
        pass
    pairs += [("posix", r.as_posix()), ("win", str(r)), ("json", json.dumps(str(r))[1:-1])]
    return dict(pairs)


def copy_report(src, dst, old_run, new_run, repo, info):
    """JSON report of a reused stage: the old run path -> the new one (every spelling), top-level reused_from."""
    text = Path(src).read_text(encoding="utf-8")
    old_t, new_t = run_tokens(old_run, repo), run_tokens(new_run, repo)
    for kind in sorted(old_t, key=lambda k: len(old_t[k]), reverse=True):
        new = new_t.get(kind) or new_t["posix"]
        text = text.replace(old_t[kind], new)
    data = json.loads(text)
    if isinstance(data, dict):
        data["reused_from"] = info
    lines = text.splitlines()
    indent = len(lines[1]) - len(lines[1].lstrip(" ")) if len(lines) > 1 and lines[1].startswith(" ") else 2
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(data, indent=indent, ensure_ascii=False) + "\n", encoding="utf-8")


def link_or_copy(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(src, dst)
        return "link"
    except OSError:
        shutil.copy2(src, dst)
        return "copy"


def apply(p, run_dir, repo):
    """Carry the files of the reused stages of plan `p` into the empty run_dir. -> summary."""
    source, run_dir = Path(p["source"]), Path(run_dir)
    reused = set(p["reused"])
    counts = {"link": 0, "copy": 0, "report": 0, "unowned_copied": 0, "skipped": 0}
    unowned, sizes = [], {"linked_bytes": 0, "copied_bytes": 0}
    src_rel = _rel(source, repo)
    for rel, path in run_files(source).items():
        st = owner(rel)
        dst = run_dir / rel
        if st in reused:
            if rel.startswith("work/params/"):
                counts["skipped"] += 1
            elif rel.startswith("reports/") and rel.endswith(".json"):
                copy_report(path, dst, source, run_dir, repo, {"run": src_rel, "stage": st, "sha256": sha256(path)})
                counts["report"] += 1
            else:
                how = link_or_copy(path, dst)
                counts[how] += 1
                sizes["linked_bytes" if how == "link" else "copied_bytes"] += path.stat().st_size
        elif st == "":  # no stage writes it (Medusa's work/h2-baseline, notes): a copy cannot reach the old run
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dst)
            counts["unowned_copied"] += 1
            unowned.append(rel)
            sizes["copied_bytes"] += path.stat().st_size
        else:
            counts["skipped"] += 1
    return dict(counts, **sizes, unowned=unowned)


def print_plan(p, out):
    out("[h2-bake] reuse from %s (evidence: %s)" % (p["source"], p["evidence"]))
    for r in p["stages"]:
        out("[h2-bake]   %-9s %-9s %s" % (r["stage"], r["action"], r.get("why", "")))
    if p["code_drift"]:
        out("[h2-bake]   code drift in reused stages: %s — the full determinism repeat is required" % p["code_drift"])
