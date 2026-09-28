#!/usr/bin/env python3
"""Validate docs/art-pipeline/asset-registry.json.

Read-only: never writes, never calls network or paid services.

Checks
  * structure: required keys, enum values (status/stage/owner/root/kind/expect)
  * unique ids, parent references (registry id or 06 assetKey)
  * manifest06Row exists in docs/game-design/06-asset-manifest.csv
  * backlog ids exist in docs/game-design/14-sprint-backlog.csv
  * contentKey exists in 05 contentKey or 06 stableContentKey
  * every path object: expect=exists -> must exist; expect=planned -> info only
  * sha256 (when given) matches the file on disk
  * status "художественно принято" requires existing acceptanceEvidence
  * every acceptanceEvidence entry is an act in the main checkout:
    root "repo", kind "file", expect "exists",
    path docs/game-design/evidence/(ART|GD)-NNN/.../*.md, and the file carries
    an explicit decision line "Решение: принято" (bold allowed, see
    DECISION_ACCEPTED_RE); "Решение: не принят…" or any other wording fails
  * a child record (parent = registry id) is not above its parent in the
    status order не начато < предложено < измерено < технически импортировано
    < художественно принято; layers may never claim artistic acceptance
  * git tracking state of every existing path (tracked / untracked / ignored),
    reported so evidence that lives only in gitignored folders is visible

Usage
  python tools/tripo-pipeline/validate_registry.py
  python tools/tripo-pipeline/validate_registry.py --registry <path> \
      --art-worktree C:/Users/ren/.codex/worktrees/art-foundation/unmached --json

Exit code 0 when there are no errors (warnings allowed), 1 otherwise.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = REPO_ROOT / "docs" / "art-pipeline" / "asset-registry.json"
DEFAULT_ART_WORKTREE = Path("C:/Users/ren/.codex/worktrees/art-foundation/unmached")

# Ordered: a child record may not be further along than its parent.
STATUS_ORDER = ["не начато", "предложено", "измерено", "технически импортировано", "художественно принято"]
STATUS_RANK = {s: i for i, s in enumerate(STATUS_ORDER)}
STATUSES = set(STATUS_ORDER)
ACCEPTED = "художественно принято"
# Artistic acceptance acts live only in the backlog evidence folders of ART-* / GD-* tasks.
ACCEPTANCE_PATH_RE = re.compile(r"^docs/game-design/evidence/(?:ART|GD)-\d{3}/(?:[^/]+/)*[^/]+\.md$")
# Explicit decision line, e.g. "**Решение: принято**", "**Решение:** принято.", "Решение: художественно принято".
# The accepted word must directly follow the colon, so "Решение: не принят", "Решение: доработать"
# and "Решение: FBX v2 принят как технический кандидат" do not count.
DECISION_ACCEPTED_RE = re.compile(
    r"^[ \t>]*(?:\*\*)?Решение(?:\*\*)?[ \t]*[:：][ \t]*(?:\*\*)?[ \t]*(?:художественно[ \t]+)?принят[оа]?(?![а-яёА-ЯЁ])",
    re.IGNORECASE | re.MULTILINE,
)
STAGES = {
    "planned", "reference-images", "blockout", "tripo-source", "blender-candidate",
    "ue-editor-import", "ue-editor-frames", "live-packaged-probe",
}
OWNERS = {"art-chat", "pipeline", "shared", "user-untracked"}
ROOTS = {"repo", "art-worktree"}
KINDS = {"file", "ue-asset"}
EXPECTS = {"exists", "planned"}
ASSET_REQUIRED = [
    "id", "name", "category", "contentKey", "manifest06Row", "backlog", "parent", "instances",
    "status", "stage", "ownership", "sourceImages", "source3d", "layers", "manifest06",
    "nextStep", "blocker", "doneCriteria", "acceptanceEvidence", "evidence", "plannedPaths",
]
UE_SUFFIXES = (".uasset", ".umap")


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.infos: list[str] = []
        self.path_rows: list[dict] = []

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def info(self, msg: str) -> None:
        self.infos.append(msg)


class GitState:
    """Caches tracked/ignored lookups per checkout with a few git calls."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.ok = (root / ".git").exists()
        self.tracked: set[str] = set()
        if self.ok:
            out = subprocess.run(
                ["git", "-C", str(root), "ls-files", "-z"],
                capture_output=True, check=False,
            )
            if out.returncode == 0:
                self.tracked = {p for p in out.stdout.decode("utf-8", "replace").split("\0") if p}
            else:
                self.ok = False

    def state(self, rel: str) -> str:
        if not self.ok:
            return "unknown"
        rel = rel.rstrip("/")
        if rel in self.tracked:
            return "tracked"
        prefix = rel + "/"
        if any(p.startswith(prefix) for p in self.tracked):
            return "tracked"
        res = subprocess.run(
            ["git", "-C", str(self.root), "check-ignore", "-q", "--no-index", rel],
            capture_output=True, check=False,
        )
        return "ignored" if res.returncode == 0 else "untracked"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_csv_column(path: Path, column: str) -> set[str]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return {row[column].strip() for row in csv.DictReader(fh) if row.get(column)}


def resolve(ref: dict, roots: dict[str, Path | None]) -> tuple[Path | None, str | None]:
    """Return (absolute path candidate, relative path inside checkout)."""
    root = roots.get(ref.get("root"))
    if root is None:
        return None, None
    raw = ref["path"]
    if ref.get("kind") == "ue-asset":
        rel = "unreal/Unmatched/Content/" + raw[len("/Game/"):]
        base = root / rel
        for suffix in UE_SUFFIXES:
            cand = Path(str(base) + suffix)
            if cand.exists():
                return cand, rel + suffix
        return base, rel
    return root / raw, raw


def check_path(ref: object, where: str, roots: dict, git: dict, rep: Report) -> None:
    if not isinstance(ref, dict):
        rep.error(f"{where}: path entry must be an object, got {type(ref).__name__}")
        return
    for key in ("path", "root", "kind", "expect", "role"):
        if key not in ref:
            rep.error(f"{where}: path entry missing '{key}'")
            return
    if ref["root"] not in ROOTS:
        rep.error(f"{where}: unknown root '{ref['root']}'")
        return
    if ref["kind"] not in KINDS:
        rep.error(f"{where}: unknown kind '{ref['kind']}'")
        return
    if ref["expect"] not in EXPECTS:
        rep.error(f"{where}: unknown expect '{ref['expect']}'")
        return
    if ref["kind"] == "ue-asset" and not ref["path"].startswith("/Game/"):
        rep.error(f"{where}: ue-asset path must start with /Game/: {ref['path']}")
        return
    if ref["kind"] == "file" and (ref["path"].startswith("/") or ":" in ref["path"]):
        rep.error(f"{where}: file path must be relative to its root: {ref['path']}")
        return
    if roots.get(ref["root"]) is None:
        rep.warn(f"{where}: root '{ref['root']}' unavailable, skipped {ref['path']}")
        rep.path_rows.append({"where": where, "root": ref["root"], "path": ref["path"], "result": "skipped"})
        return

    abs_path, rel = resolve(ref, roots)
    exists = abs_path is not None and abs_path.exists()
    tracking = git[ref["root"]].state(rel) if exists else "-"
    row = {"where": where, "root": ref["root"], "path": ref["path"], "exists": exists, "git": tracking}

    if ref["expect"] == "exists":
        if not exists:
            rep.error(f"{where}: missing {ref['root']}:{ref['path']}")
            row["result"] = "MISSING"
        else:
            row["result"] = "ok"
            if tracking == "ignored":
                rep.info(f"{where}: {ref['root']}:{ref['path']} exists but is gitignored (not in repo history)")
            elif tracking == "untracked":
                rep.info(f"{where}: {ref['root']}:{ref['path']} exists but is untracked (uncommitted)")
    else:
        row["result"] = "planned-present" if exists else "planned-absent"
        if exists:
            rep.info(f"{where}: planned path now exists: {ref['root']}:{ref['path']}")

    expected_sha = ref.get("sha256")
    if expected_sha and exists and abs_path.is_file():
        actual = sha256_of(abs_path)
        row["sha256"] = "match" if actual == expected_sha else "MISMATCH"
        if actual != expected_sha:
            rep.error(f"{where}: sha256 mismatch for {ref['path']}: registry {expected_sha[:12]}…, disk {actual[:12]}…")
    elif expected_sha and exists and not abs_path.is_file():
        rep.error(f"{where}: sha256 given for a directory: {ref['path']}")
    rep.path_rows.append(row)


def check_acceptance_act(ref: object, where: str, roots: dict, rep: Report) -> bool:
    """acceptanceEvidence entry must be an ART/GD act in the main checkout with an explicit
    "Решение: принято" line. Returns True only for a valid, existing act."""
    if not isinstance(ref, dict):
        return False  # already reported by check_path
    ok = True
    if ref.get("root") != "repo":
        rep.error(f"{where}: acceptance act must live in the main checkout (root 'repo'), got root '{ref.get('root')}'")
        ok = False
    if ref.get("kind") != "file":
        rep.error(f"{where}: acceptance act must be kind 'file', got '{ref.get('kind')}'")
        ok = False
    if ref.get("expect") != "exists":
        rep.error(f"{where}: acceptance act must be expect 'exists', got '{ref.get('expect')}'")
        ok = False
    path = str(ref.get("path", ""))
    segments = path.split("/")
    if "\\" in path or any(s in ("", ".", "..") for s in segments) or not ACCEPTANCE_PATH_RE.match(path):
        rep.error(f"{where}: acceptance act must be docs/game-design/evidence/(ART|GD)-NNN/…/*.md, got '{path}'")
        ok = False
    if not ok:
        return False
    root = roots.get("repo")
    act = root / path if root is not None else None
    if act is None or not act.is_file():
        return False  # missing file already reported by check_path
    text = act.read_text(encoding="utf-8", errors="replace")
    if not DECISION_ACCEPTED_RE.search(text):
        rep.error(f"{where}: {path} has no explicit decision line «Решение: принято» "
                  "(«не принят», «доработать» и технические решения не считаются)")
        return False
    return True


def validate(registry: dict, roots: dict, git: dict, rep: Report) -> None:
    for key in ("schemaVersion", "snapshotDate", "baseline", "vocabularies", "assets"):
        if key not in registry:
            rep.error(f"top-level key missing: {key}")
    if registry.get("schemaVersion") != 1:
        rep.error(f"unsupported schemaVersion {registry.get('schemaVersion')}")

    gd = REPO_ROOT / "docs" / "game-design"
    manifest_keys = load_csv_column(gd / "06-asset-manifest.csv", "assetKey")
    stable_keys = load_csv_column(gd / "06-asset-manifest.csv", "stableContentKey")
    content_keys = load_csv_column(gd / "05-content-matrix.csv", "contentKey")
    backlog_ids = load_csv_column(gd / "14-sprint-backlog.csv", "id")

    for i, dep in enumerate(registry.get("sharedDependencies", [])):
        for j, ref in enumerate(dep.get("paths", [])):
            check_path(ref, f"sharedDependencies[{dep.get('id', i)}].paths[{j}]", roots, git, rep)

    assets = registry.get("assets", [])
    ids = [a.get("id") for a in assets]
    dup = {x for x in ids if ids.count(x) > 1}
    for d in sorted(dup):
        rep.error(f"duplicate asset id: {d}")
    id_set = set(ids)
    status_by_id = {a.get("id"): a.get("status") for a in assets if isinstance(a, dict)}

    for a in assets:
        aid = a.get("id", "<no id>")
        missing = [k for k in ASSET_REQUIRED if k not in a]
        if missing:
            rep.error(f"{aid}: missing keys {missing}")
            continue
        if a["status"] not in STATUSES:
            rep.error(f"{aid}: unknown status '{a['status']}'")
        if a["stage"] not in STAGES:
            rep.error(f"{aid}: unknown stage '{a['stage']}'")
        own = a["ownership"]
        for k in ("existingFiles", "nextCandidates", "acceptance"):
            if own.get(k) not in OWNERS:
                rep.error(f"{aid}: ownership.{k} '{own.get(k)}' not in {sorted(OWNERS)}")
        if a["manifest06Row"] and a["manifest06Row"] not in manifest_keys:
            rep.error(f"{aid}: manifest06Row '{a['manifest06Row']}' not found in 06-asset-manifest.csv")
        for b in a["backlog"]:
            if b not in backlog_ids:
                rep.error(f"{aid}: backlog id '{b}' not found in 14-sprint-backlog.csv")
        ck = a["contentKey"]
        if ck is not None and ck not in content_keys and ck not in stable_keys:
            rep.error(f"{aid}: contentKey '{ck}' not in 05 contentKey nor 06 stableContentKey")
        parent = a["parent"]
        if parent is not None and parent not in id_set and parent not in manifest_keys:
            rep.error(f"{aid}: parent '{parent}' is neither a registry id nor a 06 assetKey")
        if parent is not None and parent == aid:
            rep.error(f"{aid}: parent refers to the record itself")
        elif parent in status_by_id:
            ps, cs = status_by_id[parent], a["status"]
            if ps in STATUS_RANK and cs in STATUS_RANK and STATUS_RANK[cs] > STATUS_RANK[ps]:
                rep.error(f"{aid}: status '{cs}' is above its parent {parent} ('{ps}'); "
                          "a child record may not be further along than its parent")
        if not isinstance(a["instances"], int) or a["instances"] < 1:
            rep.error(f"{aid}: instances must be a positive integer")
        for k in ("nextStep", "blocker", "doneCriteria"):
            if not str(a[k]).strip():
                rep.error(f"{aid}: empty {k}")
        m06 = a["manifest06"]
        for k in ("verificationStatusIn06", "drift", "proposedChange"):
            if k not in m06:
                rep.error(f"{aid}: manifest06.{k} missing")

        si = a["sourceImages"]
        if si.get("selectionManifest"):
            check_path(si["selectionManifest"], f"{aid}.sourceImages.selectionManifest", roots, git, rep)
        for j, ref in enumerate(si.get("recommended", [])):
            check_path(ref, f"{aid}.sourceImages.recommended[{j}]", roots, git, rep)
        for j, ref in enumerate(si.get("excludedCandidates", [])):
            check_path(ref, f"{aid}.sourceImages.excludedCandidates[{j}]", roots, git, rep)
        for j, ref in enumerate(a["source3d"]):
            check_path(ref, f"{aid}.source3d[{j}]", roots, git, rep)
        for j, layer in enumerate(a["layers"]):
            lname = layer.get("layer", j)
            if layer.get("status") not in STATUSES:
                rep.error(f"{aid}.layers[{lname}]: unknown status '{layer.get('status')}'")
            if layer.get("stage") not in STAGES:
                rep.error(f"{aid}.layers[{lname}]: unknown stage '{layer.get('stage')}'")
            if layer.get("owner") not in OWNERS:
                rep.error(f"{aid}.layers[{lname}]: unknown owner '{layer.get('owner')}'")
            if layer.get("status") == "художественно принято":
                rep.error(f"{aid}.layers[{lname}]: layer claims artistic acceptance; record it on the asset with acceptanceEvidence")
            for k, ref in enumerate(layer.get("paths", [])):
                check_path(ref, f"{aid}.layers[{lname}].paths[{k}]", roots, git, rep)
        for j, ref in enumerate(a["evidence"]):
            check_path(ref, f"{aid}.evidence[{j}]", roots, git, rep)
        valid_acts = 0
        for j, ref in enumerate(a["acceptanceEvidence"]):
            check_path(ref, f"{aid}.acceptanceEvidence[{j}]", roots, git, rep)
            if check_acceptance_act(ref, f"{aid}.acceptanceEvidence[{j}]", roots, rep):
                valid_acts += 1
        for j, ref in enumerate(a["plannedPaths"]):
            if isinstance(ref, dict) and ref.get("expect") != "planned":
                rep.error(f"{aid}.plannedPaths[{j}]: expect must be 'planned'")
            check_path(ref, f"{aid}.plannedPaths[{j}]", roots, git, rep)

        if a["status"] == ACCEPTED:
            if not valid_acts:
                rep.error(f"{aid}: status 'художественно принято' requires acceptanceEvidence: an existing "
                          "docs/game-design/evidence/(ART|GD)-NNN/…/*.md act with «Решение: принято»")
        elif a["acceptanceEvidence"]:
            rep.warn(f"{aid}: acceptanceEvidence present but status is '{a['status']}'")
        if a["status"] in ("технически импортировано", "художественно принято"):
            has_ue = any(
                isinstance(r, dict) and r.get("kind") == "ue-asset" and r.get("expect") == "exists"
                for layer in a["layers"] for r in layer.get("paths", [])
            ) or any(isinstance(r, dict) and r.get("kind") == "ue-asset" for r in a["source3d"])
            has_report = any(
                isinstance(r, dict) and "report" in (r.get("path", "") + r.get("role", "")).lower()
                for layer in a["layers"] for r in layer.get("paths", [])
            ) or any(
                isinstance(r, dict) and "report" in (r.get("path", "") + r.get("role", "")).lower()
                for r in a["evidence"] + a["source3d"]
            ) or any(
                isinstance(r, dict) and ("review" in r.get("path", "") or "acceptance" in r.get("path", ""))
                for r in a["evidence"]
            )
            if not (has_ue or has_report) and a["parent"] is None:
                rep.warn(f"{aid}: status '{a['status']}' without a UE asset path or import report reference")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    ap.add_argument("--art-worktree", type=Path, default=DEFAULT_ART_WORKTREE,
                    help="Art-chat worktree root; if absent, its paths are skipped with a warning")
    ap.add_argument("--json", action="store_true", help="print machine-readable result")
    ap.add_argument("--paths", action="store_true", help="print one line per checked path")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    art = args.art_worktree if args.art_worktree and args.art_worktree.exists() else None
    roots = {"repo": REPO_ROOT, "art-worktree": art}
    git = {"repo": GitState(REPO_ROOT)}
    git["art-worktree"] = GitState(art) if art else GitState(Path("__missing__"))

    rep = Report()
    if art is None:
        rep.warn(f"art worktree not found at {args.art_worktree}; art-worktree paths skipped")
    validate(registry, roots, git, rep)

    assets = registry.get("assets", [])
    by_status: dict[str, int] = {}
    for a in assets:
        by_status[a.get("status", "?")] = by_status.get(a.get("status", "?"), 0) + 1
    counts = {
        "assets": len(assets),
        "byStatus": by_status,
        "pathsChecked": len(rep.path_rows),
        "pathsOk": sum(1 for r in rep.path_rows if r.get("result") == "ok"),
        "pathsMissing": sum(1 for r in rep.path_rows if r.get("result") == "MISSING"),
        "plannedAbsent": sum(1 for r in rep.path_rows if r.get("result") == "planned-absent"),
        "plannedPresent": sum(1 for r in rep.path_rows if r.get("result") == "planned-present"),
        "sha256Checked": sum(1 for r in rep.path_rows if "sha256" in r),
        "sha256Mismatch": sum(1 for r in rep.path_rows if r.get("sha256") == "MISMATCH"),
        "gitignoredExisting": sum(1 for r in rep.path_rows if r.get("git") == "ignored"),
        "untrackedExisting": sum(1 for r in rep.path_rows if r.get("git") == "untracked"),
        "skipped": sum(1 for r in rep.path_rows if r.get("result") == "skipped"),
    }

    if args.json:
        print(json.dumps({"ok": not rep.errors, "counts": counts, "errors": rep.errors,
                          "warnings": rep.warnings, "infos": rep.infos,
                          "paths": rep.path_rows if args.paths else None},
                         ensure_ascii=False, indent=2))
    else:
        print(f"registry: {args.registry}")
        print(f"repo root: {REPO_ROOT}")
        print(f"art worktree: {art if art else 'MISSING (skipped)'}")
        if args.paths:
            for r in rep.path_rows:
                print(f"  [{r.get('result'):>15}] git={r.get('git', '-'):<9} sha={r.get('sha256', '-'):<8} "
                      f"{r['root']}:{r['path']}")
        print("counts: " + json.dumps(counts, ensure_ascii=False))
        for m in rep.infos:
            print(f"INFO  {m}")
        for m in rep.warnings:
            print(f"WARN  {m}")
        for m in rep.errors:
            print(f"ERROR {m}")
        print("RESULT: " + ("PASS" if not rep.errors else f"FAIL ({len(rep.errors)} errors)"))
    return 0 if not rep.errors else 1


if __name__ == "__main__":
    sys.exit(main())
