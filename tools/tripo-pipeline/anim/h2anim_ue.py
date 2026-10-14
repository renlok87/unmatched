"""H2Anim в живом UnrealEditor (волна 5c): канонический скелет героя, импорт клипов, замеры, контактный лист.

    python tools/tripo-pipeline/anim/h2anim_ue.py state
    python tools/tripo-pipeline/anim/h2anim_ue.py skeleton <spec.json> [--refresh-preview]
    python tools/tripo-pipeline/anim/h2anim_ue.py import   <spec.json> [--clips=Idle,...]
    python tools/tripo-pipeline/anim/h2anim_ue.py measure  <spec.json>
    python tools/tripo-pipeline/anim/h2anim_ue.py frames   <spec.json> [--base=/Game/.../SM_*_Base | --no-base] [--clips=Idle]
    python tools/tripo-pipeline/anim/h2anim_ue.py sheet    <spec.json>   (лист UE из уже снятых кадров, без редактора)

Живой редактор (MCP 127.0.0.1:8123 + консоль редактора, review/ue_live.py); шаги строго последовательно.
  skeleton  review/ue_py/canonical_skeleton.py: /Game/PipelineCandidates/<Hero>/Rig/SK_<Hero>_Skeleton из
            SK_<Hero>_H2.fbx спеки (носитель SK_<Hero> рядом); идемпотентно — существующий скелет не трогается.
            Носитель (меш превью клипов, ue.mesh_for_preview) — F145: его sha исходного FBX (метка пакета
            UM_SourceFbxSha256) сверяется с target.sk_fbx спеки; другой sha, другой файл источника с другим sha или
            пропавший источник → review/ue_py/preview_mesh.py refresh: переимпорт носителя на СУЩЕСТВУЮЩИЙ скелет
            (скелет и его опорная поза не меняются, сохраняется только носитель) + метка sha. Тот же путь без метки
            считается текущим (перезапись FBX на месте так не видна) — --refresh-preview переимпортирует принудительно.
            sha FBX и решение — в reports/ue-canonical-skeleton.json (preview_mesh). frames и measure отказывают, пока
            носитель не текущий;
  import    review/ue_py/import_clips.py (явная FbxFactory, bForceRootLock, uniform_scale по умолчанию импортёра,
            существующий клип удаляется и импортируется заново) — клипы <run>/export/AM_<Hero>_<Clip>.fbx на
            канонический скелет в ue.clips_folder спеки (…/<Hero>/H2Anim). CLI tripo_pipeline клипы не импортирует
            (стадия ue-import импортирует только меши), поэтому импорт клипов идёт этим путём;
  measure   review/ue_py/measure_clips.py (кость 0 и root по кадрам, длительность, пик, сокеты Weapon/Head) с мешем
            ue.mesh_for_preview спеки;
  frames    контактный лист ключевых поз в редакторе: уровень /Game/ArtTests/P17ControlScene/L_P17ControlScene,
            свет cobble-probe (как review/h2_ue_review.py, в памяти), High (sg.*=2), фигура — ue.mesh_for_preview,
            поза кадра — control_scene_ue.py pose (single-node, время кадра), виды: спереди и 3/4. Ничего не
            сохраняется; отказ при несохранённом открытом уровне; в конце — исходный уровень и настройки.
            Подставка (F96): --base <пакет>; без флага — ue.base спеки, иначе /Game/PipelineCandidates/<Hero>/H2LD/
            Meshes/SM_<Hero>_H2LD_Base (импорт 7a); нет такого ассета — отказ с подсказкой; --no-base — кадры без
            подставки (как MVP). Камера (F136): MVP 200 uu / высота 31 uu, если фигура (bounds носителя от низа
            подставки до верха, +6 % роста) входит в кадр 16:9 (гориз. FOV вьюпорта ~35°); выше — камера отходит и
            центрирует фигуру (report camera.mode fit). Прогрев (F153): bThrottleCPUWhenNotForeground выключается в
            памяти на время съёмки (фоновый/скрытый редактор иначе не сводит Lumen/TSR), ждём сходимости (3 разности
            подряд ≤ 1,0) не меньше прежних 19 разностей и не больше 39; не сошлось — settle.status not_settled (WARN).
            --clips=A,B и --frames=3,4,5 сужают набор; --closeup: крупный план (камера в --eye-dist uu от фигуры
            на высоте --eye-z, FOV 35, кадр 1920×1080 на позу) — кадры *-closeup-ue-editor.jpg и отчёт
            reports/ue-frames-closeup.json, общий лист не пересобирается (anim-v2 fix: f03–f05 Arthur LungeAttack).
            Длинные захваты — по одному клипу (--clips=X): лист собирается из кадров на диске, когда сняты все
            клипы; кадр с imported_fbx_sha256, не совпадающим с текущим FBX клипа, или с preview_fbx_sha256, не
            совпадающим с target спеки (кадр снят на старом носителе), считается устаревшим.
Отчёты — <run>/reports/ue-*.json, кадры — <run>/preview/ue/. Кадры редактора — диагностика, не приёмка K1/K2.
"""
import argparse
import base64
import hashlib
import io
import json
import math
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
REVIEW = HERE.parent / "review"
sys.path.insert(0, str(REVIEW))
from ue_live import Ue  # noqa: E402

UE_PY = REVIEW / "ue_py"
LEVEL = "/Game/ArtTests/P17ControlScene/L_P17ControlScene"
PROFILES_JSON = REPO / "unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json"
KEY_LABEL = "ART005 cool scene key - proposed"
FILL_LABEL = "ART005 neutral readability fill - review only"
EXPOSURE_LABEL = "P17 exposure EV100 1.3 - fixed"
KEY_ROTATION = [-55.0, 30.0, 0.0]
PREFIX = "W5c H2Anim "
L_FIG, L_BASE, L_SKY, L_CAM = (PREFIX + "figure - temporary", PREFIX + "base - temporary",
                               PREFIX + "sky - temporary", PREFIX + "camera FOV35 - temporary")
CELL = [0.0, 50.0, 0.0]
SG = ("sg.ViewDistanceQuality", "sg.AntiAliasingQuality", "sg.ShadowQuality", "sg.GlobalIlluminationQuality",
      "sg.ReflectionQuality", "sg.PostProcessQuality", "sg.TextureQuality", "sg.EffectsQuality", "sg.FoliageQuality",
      "sg.ShadingQuality")
SHOW_FLAGS_OFF = ("Grid", "BillboardSprites", "Volumes")
NOANN = {"gridSpacing": 0, "gridExtent": 0, "gridHeight": 0, "maxLabelDistance": 0, "classFilter": None, "maxLabels": 0}
SIDECAR_SCHEMA = "unmatched.evidence-frame/1"
FOREIGN_PREFIXES = ("LDv2",)
WATCH_CLASSES = ("SkyLight", "CameraActor", "DirectionalLight")
PREVIEW_TAG = "UM_SourceFbxSha256"  # package metadata of the carrier: sha256 of its source FBX (F145)
# F153: frame-to-frame mean abs difference (8-bit levels) of a settled editor viewport is 0.3-0.8; a viewport that does
# not converge (background-throttled editor) stays at 1.7-2.6 for minutes. Converged = 3 differences in a row <= 1.0.
SETTLE_THRESHOLD = 1.0
WARMUP_MIN_DIFFS, WARMUP_MAX_DIFFS = 19, 39  # 19 = the length of the warm-up before the convergence rule
THROTTLE_REF = {"refPath": "/Script/UnrealEd.Default__EditorPerformanceSettings"}
# F136: the level viewport renders ~35.1 deg HORIZONTAL whatever the camera FOV (h2_ue_review.py NARROW note); a 16:9
# crop of it shows z in [31 - 200 t, 31 + 200 t] at the MVP eye, t = tan(17.55 deg) * min(9/16, h/w) (about -4.6..66.6)
H_FOV_DEG = 35.1
MVP_EYE = (200.0, 31.0)  # (distance, height) of the MVP front / q34 frames
FRAME_PAD = 0.06         # share of the figure height kept free above the top and below the base bottom


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _same_path(a, b):
    return os.path.normcase(os.path.abspath(str(a))) == os.path.normcase(os.path.abspath(str(b)))


def spec_target(spec):
    """(abs path of the spec's SK_<Hero>_H2.fbx, its sha256); a pinned target.sha256 must match the file."""
    fbx = (REPO / spec["target"]["sk_fbx"]).resolve()
    if not fbx.is_file():
        raise SystemExit("spec target FBX is missing: %s" % fbx)
    digest = sha256_file(fbx)
    pinned = spec["target"].get("sha256")
    if pinned and pinned != digest:
        raise SystemExit("spec target %s has sha256 %s but the spec pins %s: update target.sha256 of the spec for the "
                         "reworked model first" % (spec["target"]["sk_fbx"], digest[:12], pinned[:12]))
    return fbx, digest


def carrier_of(spec):
    """The carrier canonical_skeleton.py creates next to the skeleton: <folder>/SK_<Hero> of ue.skeleton."""
    return spec["ue"]["skeleton"][:-len("_Skeleton")]


def preview_decision(state, fbx, sha, force=False, sha_of=sha256_file):
    """F145: is the preview mesh (state = ue_py/preview_mesh.py state) the spec's target FBX?
    current True (sha stamp equal, or the recorded source file has the target sha), False (stamp or recorded source
    differs, source gone, mesh missing) or None (same source path but no stamp: assumed current, an in-place overwrite
    of the FBX is not visible); refresh = current is False or force."""
    rec = {"want_fbx": Path(fbx).as_posix(), "want_sha256": sha, "recorded_sha256": state.get("sha_stamp"),
           "recorded_source_files": state.get("source_files") or []}
    srcs = rec["recorded_source_files"]
    if not state.get("exists"):
        cur, how = False, "preview mesh %s is missing" % state.get("mesh")
    elif rec["recorded_sha256"]:
        cur = rec["recorded_sha256"] == sha
        how = "sha stamp %s the target FBX" % ("equals" if cur else "differs from")
    elif any(_same_path(s, fbx) for s in srcs):
        cur, how = None, ("same source path as the target, no sha stamp (an FBX overwritten in place would go "
                          "unnoticed; --refresh-preview re-imports and stamps)")
    else:
        found = [s for s in srcs if Path(s).is_file()]
        if found:
            cur = any(sha_of(s) == sha for s in found)
            how = "recorded source %s has %s sha256" % (found[0], "the target" if cur else "another")
        else:
            cur, how = False, "recorded source %s is gone: the preview mesh cannot be proven current" % (srcs or "-")
    return dict(rec, current=cur, refresh=bool(force) or cur is False,
                reason=("--refresh-preview; " if force else "") + how)


def preview_state(ue, spec, out, mesh=None):
    """ue_py/preview_mesh.py state of the preview mesh (its "before" block: exists, source files, sha stamp, bounds)."""
    return task(ue, "preview_mesh.py", out, op="state", mesh=mesh or spec["ue"]["mesh_for_preview"],
                skeleton=spec["ue"]["skeleton"])["before"]


def preview_check(ue, spec, out):
    """frames / measure: refuse a carrier that is not the spec's model (F145); other preview meshes (an imported H2
    mesh of older heroes) are read and recorded only."""
    fbx, sha = spec_target(spec)
    mesh = spec["ue"]["mesh_for_preview"]
    st = preview_state(ue, spec, out)
    dec = preview_decision(st, fbx, sha)
    carrier = mesh == carrier_of(spec)
    if carrier and dec["refresh"]:
        raise SystemExit("preview mesh %s is not the spec's model (%s): run `python tools/tripo-pipeline/anim/"
                         "h2anim_ue.py skeleton %s` first (re-imports it onto the canonical skeleton)"
                         % (mesh, dec["reason"], spec["_path"]))
    return {"mesh": mesh, "carrier": carrier, "enforced": carrier, "state": st, "decision": dec,
            "target_fbx": spec["target"]["sk_fbx"], "target_sha256": sha,
            "fbx_sha256_of_frames": sha if (carrier and dec["current"] is not False) else None}


def converged(diffs, threshold=SETTLE_THRESHOLD):
    return len(diffs) >= 3 and max(diffs[-3:]) <= threshold


def mean_abs_diff(a, b):
    import numpy as np
    return round(float(np.abs(np.asarray(a, np.int16) - np.asarray(b, np.int16)).mean()), 4)


def warm_up(grab_fn, min_diffs=WARMUP_MIN_DIFFS, max_diffs=WARMUP_MAX_DIFFS, threshold=SETTLE_THRESHOLD, pause_s=1.5,
            sleep=time.sleep):
    """F153: grab until the viewport converged (at least min_diffs differences, at most max_diffs)."""
    prev, diffs = None, []
    while len(diffs) < max_diffs:
        im = grab_fn()
        if prev is not None:
            diffs.append(mean_abs_diff(im, prev))
            if len(diffs) >= min_diffs and converged(diffs, threshold):
                break
        prev = im
        sleep(pause_s)
    return diffs, converged(diffs, threshold)


def throttle(ue, value=None):
    """EditorPerformanceSettings.bThrottleCPUWhenNotForeground through the MCP object toolset, in memory only (not
    saved; ue_h5cb1.py, look-dev C C2: a background editor does not converge its Lumen/TSR frames)."""
    def get():
        r = ue.call("object", "get_properties", {"instance": THROTTLE_REF, "properties": ["bThrottleCPUWhenNotForeground"]},
                    record=False)
        return json.loads(r) if isinstance(r, str) and r[:1] in "[{" else r
    rec = {"before": get()}
    if value is not None:
        ue.call("object", "set_properties", {"instance": THROTTLE_REF,
                                             "values": json.dumps({"bThrottleCPUWhenNotForeground": bool(value)})},
                record=False)
    rec["after"] = get()
    return rec


def throttle_was_on(rec):
    return "true" in json.dumps((rec or {}).get("before")).lower()


def half_tan_v(w, h, h_fov_deg=H_FOV_DEG):
    """tan of half the vertical view angle of the 16:9 crop of a w x h viewport capture."""
    return math.tan(math.radians(h_fov_deg / 2.0)) * min(9.0 / 16.0, h / float(w))


def frame_camera(top_z, bottom_z, tan_v, mvp=MVP_EYE, pad=FRAME_PAD):
    """F136: front / q34 eye (distance from the cell, height) of the clip frames. The MVP eye whenever the figure (base
    bottom z 0 .. top of the preview mesh bounds, + pad of its height at both ends) fits the 16:9 frame of the MVP eye
    (frames stay comparable with the MVP frames); otherwise the camera backs off (never closer than the MVP) and centres
    the figure. top_z None (no bounds) -> MVP."""
    d0, z0 = mvp
    res = {"mvp_eye_dist_uu": d0, "mvp_eye_z_uu": z0, "half_tan_v": round(tan_v, 5),
           "mvp_visible_z_uu": [round(z0 - d0 * tan_v, 2), round(z0 + d0 * tan_v, 2)], "figure_top_z_uu": top_z,
           "figure_bottom_z_uu": bottom_z, "pad_share": pad}
    if top_z is None:
        return dict(res, mode="mvp", eye_dist_uu=d0, eye_z_uu=z0, note="no preview-mesh bounds: MVP eye")
    lo0 = min(0.0, bottom_z if bottom_z is not None else 0.0)
    h = max(top_z - lo0, 1.0)
    lo, hi = lo0 - pad * h, top_z + pad * h
    res["needed_z_uu"] = [round(lo, 2), round(hi, 2)]
    if lo >= z0 - d0 * tan_v and hi <= z0 + d0 * tan_v:
        return dict(res, mode="mvp", eye_dist_uu=d0, eye_z_uu=z0)
    return dict(res, mode="fit", eye_dist_uu=round(max(d0, (hi - lo) / 2.0 / tan_v), 2), eye_z_uu=round((hi + lo) / 2.0, 2))


def resolve_base(spec, base=None, no_base=False, exists=None):
    """F96: the base mesh of the clip frames: --base, else spec ue.base, else the stage-7a import's
    <hero root>/H2LD/Meshes/SM_<Hero>_H2LD_Base; exists(path) False -> refusal with the way out; --no-base -> None."""
    if no_base:
        return None, "none (--no-base)"
    if base:
        return base, "--base"
    cand, src = spec["ue"].get("base"), "spec ue.base"
    if not cand:
        root = spec["ue"]["skeleton"].rsplit("/Rig/", 1)[0]
        cand, src = "%s/H2LD/Meshes/SM_%s_H2LD_Base" % (root, spec["ue_hero"]), "<hero root>/H2LD/Meshes/SM_<Hero>_H2LD_Base"
    if exists is not None and not exists(cand):
        raise SystemExit("frames: no base mesh %s (%s; the stage-7a H2LD import brings it). Pass --base /Game/.../SM_<Hero>"
                         "_*_Base, or --no-base for frames without a base (the MVP look)" % (cand, src))
    return cand, src


def load_spec(path):
    p = Path(path).resolve()
    spec = json.loads(p.read_text(encoding="utf-8"))
    spec["_path"] = p.relative_to(REPO).as_posix()
    return spec


def run_dir(spec):
    return REPO / spec["run_dir"]


def task(ue, script, out, timeout=900, **kw):
    return ue.run_task(str(UE_PY / script), str(out), timeout=timeout, **kw)


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8",
                    newline="\n")


def editor_state(ue):
    tmp = REPO / "art/pipeline-candidates/_h2anim_editor_state.json"
    try:
        data = ue.py_file(str(UE_PY / "editor_state.py"), str(tmp), timeout=120, args=tmp.as_posix())
    finally:
        if tmp.exists():
            tmp.unlink()
    return data


def cmd_state(_a):
    ue = Ue()
    print(json.dumps(editor_state(ue), indent=1))


def cmd_skeleton(a):
    spec = load_spec(a.spec)
    ue = Ue()
    folder = spec["ue"]["skeleton"].rsplit("/", 1)[0]
    mesh_name = spec["ue"]["skeleton"].rsplit("/", 1)[1][:-len("_Skeleton")]
    out = run_dir(spec) / "reports/ue-canonical-skeleton.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    fbx, sha = spec_target(spec)
    fbx_ue = str(fbx).replace("\\", "/")
    before = editor_state(ue)
    res = task(ue, "canonical_skeleton.py", out, fbx=fbx_ue, folder=folder, mesh_name=mesh_name, fbx_sha256=sha)
    # F145: the carrier (pose mesh of the clip previews) follows the spec's model; a new carrier was just stamped
    carrier = "%s/%s" % (folder, mesh_name)
    tmp = out.with_name("_preview_task.json")
    pv = {"mesh": carrier, "target_fbx": spec["target"]["sk_fbx"], "fbx_sha256": sha,
          "mesh_for_preview": spec["ue"]["mesh_for_preview"],
          "mesh_for_preview_is_carrier": spec["ue"]["mesh_for_preview"] == carrier}
    pv["state_before"] = preview_state(ue, spec, tmp, mesh=carrier)
    pv["decision"] = preview_decision(pv["state_before"], fbx, sha,
                                      force=bool(getattr(a, "refresh_preview", False)) and not res.get("created"))
    pv["refresh"] = None
    if pv["decision"]["refresh"]:
        r = task(ue, "preview_mesh.py", tmp, op="refresh", mesh=carrier, skeleton=spec["ue"]["skeleton"], fbx=fbx_ue,
                 fbx_sha256=sha)
        pv["refresh"] = {k: r.get(k) for k in ("imported", "ref_pose_equal", "skeleton_dirty_after_import", "saved",
                                               "dirty_before", "dirty_after_import", "dirty_after_save")}
        pv["state_after"] = r["after"]
        pv["decision_after"] = preview_decision(r["after"], fbx, sha)
        if pv["decision_after"]["current"] is not True:
            write(out, dict(res, preview_mesh=pv))
            raise SystemExit("preview mesh %s still not current after the re-import: %s"
                             % (carrier, pv["decision_after"]["reason"]))
    pv["current"] = (pv.get("decision_after") or pv["decision"])["current"]
    if tmp.exists():
        tmp.unlink()
    after = editor_state(ue)
    res.update({"spec": spec["_path"], "target_sk_fbx": spec["target"]["sk_fbx"],
                "target_sha256": spec["target"]["sha256"], "target_fbx_sha256_now": sha, "preview_mesh": pv,
                "dirty_content_before": before["dirty_content"],
                "dirty_content_after": after["dirty_content"], "tool": "tools/tripo-pipeline/anim/h2anim_ue.py skeleton"})
    write(out, res)
    print("skeleton", res["skeleton"], "created" if res.get("created") else "exists", "bones", len(res["bones_in_order"]),
          "bone0", res["bone0"], "dirty after", after["dirty_content"])
    print("preview mesh", carrier, "re-imported" if pv["refresh"] else "kept", "| current:", pv["current"], "|",
          (pv.get("decision_after") or pv["decision"])["reason"], "| fbx sha256", sha[:12])


def cmd_import(a):
    spec = load_spec(a.spec)
    ue = Ue()
    names = a.clips.split(",") if a.clips else list(spec["clips"])
    run = run_dir(spec)
    clips = [{"fbx": str((run / "export" / ("AM_%s_%s.fbx" % (spec["ue_hero"], n))).resolve()).replace("\\", "/"),
              "folder": spec["ue"]["clips_folder"], "name": "AM_%s_%s" % (spec["ue_hero"], n),
              "skeleton": spec["ue"]["skeleton"], "uniform_scale": None, "force_root_lock": True} for n in names]
    out = run / "reports/ue-import-clips.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    prev_rep = json.loads(out.read_text(encoding="utf-8")) if out.exists() else None
    before = editor_state(ue)
    res = task(ue, "import_clips.py", out, clips=clips)
    after = editor_state(ue)
    res.update({"spec": spec["_path"], "dirty_content_before": before["dirty_content"],
                "dirty_content_after": after["dirty_content"],
                "fbx_sha256": {c["name"]: hashlib.sha256(Path(c["fbx"]).read_bytes()).hexdigest() for c in clips},
                "tool": "tools/tripo-pipeline/anim/h2anim_ue.py import -> review/ue_py/import_clips.py",
                "why_not_cli": "tripo_pipeline 0.8.0 ue-import imports meshes only (no clip stage); clips go through "
                               "the reviewed import_clips.py task (explicit FbxFactory, bForceRootLock)"})
    if prev_rep and a.clips:
        # частичный импорт (--clips): записи остальных клипов прошлого отчёта сохраняются
        done = {x["name"] for x in res["clips"]}
        res["clips"] = sorted([c for c in prev_rep.get("clips", []) if c["name"] not in done] + res["clips"],
                              key=lambda c: c["name"])
        res["fbx_sha256"] = dict(prev_rep.get("fbx_sha256") or {}, **res["fbx_sha256"])
    write(out, res)
    for c in res["clips"]:
        print(c["name"], "legacy", c["legacy_fbx_import"], "root_lock", c["force_root_lock_ok"], c["imported_object_paths"])
    print("cvar unchanged", res["cvar_unchanged"], "dirty after", after["dirty_content"])


def cmd_measure(a):
    spec = load_spec(a.spec)
    ue = Ue()
    run = run_dir(spec)
    clips = []
    heights = []
    for n, c in spec["clips"].items():
        rep = json.loads((REPO / "docs/art-pipeline/animation-library/validation-h2anim" /
                          ("AM_%s_%s.validation.json" % (spec["ue_hero"], n))).read_text(encoding="utf-8"))
        heights.append(rep["reference_height"] * 100.0)
        k = int(c["frames"])
        clips.append({"anim": "%s/AM_%s_%s" % (spec["ue"]["clips_folder"], spec["ue_hero"], n),
                      "mesh": spec["ue"]["mesh_for_preview"], "source_duration_s": round(k / 24.0, 6),
                      "source_frames": k + 1, "sample_frames": sorted(set(c.get("key_frames", [0, k // 2, k])))})
    out = run / "reports/ue-measure-clips.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = run / "reports/_preview_task.json"
    preview = preview_check(ue, spec, tmp)  # F145: never measure on a carrier of an older model
    if tmp.exists():
        tmp.unlink()
    res = task(ue, "measure_clips.py", out, clips=clips, height_uu=round(max(heights), 3), min_pose_change=0.02)
    res.update({"spec": spec["_path"], "preview_mesh": preview,
                "tool": "tools/tripo-pipeline/anim/h2anim_ue.py measure -> review/ue_py/measure_clips.py"})
    write(out, res)
    for c in res["clips"]:
        b0 = c.get("track_" + c["bone0"], {})
        print(c["anim"].rsplit("/", 1)[1], "len", c["length_s"], "frames", c["num_frames"], "fps", c["frame_rate"],
              "bone0", c["bone0"], "b0 delta", b0.get("max_abs_delta_uu_xyz"), "peak", c["peak_bone_displacement"]["share_of_height"],
              "scale", c["translation_scale_ratio_median"], c["component_scale_ratio_frame0_vs_reference"],
              "f0 off", c["component_max_offset_frame0_vs_reference_uu"])


def cvar_value(ue, name):
    raw = ue.call("app", "SearchCVars", {"name": name}, record=False)
    data = json.loads(raw) if isinstance(raw, str) else raw
    return (data.get(name) or {}).get("value")


def grab(ue, eye, rot):
    from PIL import Image
    xform = {"location": dict(zip("xyz", eye)), "rotation": dict(zip(("pitch", "yaw", "roll"), rot)),
             "scale": {"x": 1, "y": 1, "z": 1}}
    res = ue.call("app", "CaptureViewport", {"captureTransform": xform, "annotations": NOANN, "bShowUI": False},
                  record=False)
    v = res["value"] if isinstance(res, dict) and "value" in res else res
    img = v["image"] if isinstance(v, dict) and "image" in v else res["images"][0]
    return Image.open(io.BytesIO(base64.b64decode(img["data"]))).convert("RGB")


def cmd_frames(a):
    from PIL import Image
    spec = load_spec(a.spec)
    run = run_dir(spec)
    out = run / "preview/ue"
    out.mkdir(parents=True, exist_ok=True)
    tmp = out / "_task.json"
    ue = Ue()
    profiles = json.loads(PROFILES_JSON.read_text(encoding="utf-8"))["lightProfiles"]
    if "cobble-probe" in profiles:
        light, light_source = profiles["cobble-probe"], "cobble-probe (S08ArtBoardProfiles.json)"
    elif a.light_pinned:
        # 2026-10-04 (real boards only, ND-5): cobble-probe left S08ArtBoardProfiles.json; the same light is the data
        # recorded in a review report of ue_hero_lookdev.py (its config key light_profile_pinned does the same)
        pinned = Path(a.light_pinned).resolve()
        light = json.loads(pinned.read_text(encoding="utf-8"))["light_profile"]["data"]
        light_source = "%s light_profile.data (pinned: cobble-probe removed from S08ArtBoardProfiles.json by ND-5)" % pinned
    else:
        raise SystemExit("light profile cobble-probe is not in %s (removed by ND-5, 2026-10-04): pass --light-pinned "
                         "<ue_hero_lookdev review report with light_profile.data>" % PROFILES_JSON)
    mesh = spec["ue"]["mesh_for_preview"]
    original = ue.call("scene", "get_current_level", record=False)
    if ue.call("asset", "is_dirty", {"asset_path": original}, record=False):
        raise SystemExit("open level %s has unsaved changes; refusing to switch levels" % original)
    if original.split(".")[0] == LEVEL:
        raise SystemExit("the review level itself is open; open another level first")
    if ue.call("asset", "is_dirty", {"asset_path": LEVEL}, record=False):
        raise SystemExit("the review level has unsaved changes in memory (someone else is using it)")
    preview = preview_check(ue, spec, tmp)  # F145: refuse frames of a carrier that is not the spec's model
    base, base_source = resolve_base(spec, a.base, a.no_base,
                                     exists=lambda p: bool(ue.call("asset", "exists", {"path": p}, record=False)))
    state_before = editor_state(ue)
    sg_before = {n: cvar_value(ue, n) for n in SG}
    report = {"schema": "unmatched.h2anim-ue-frames/1", "spec": spec["_path"], "mesh": mesh, "base": base,
              "base_source": base_source, "preview_mesh": preview,
              "level": LEVEL, "original_level": original, "light_profile": light_source,
              "kind": "EDITOR frames (live UnrealEditor via MCP CaptureViewport); diagnostic, not K1/K2 acceptance, no "
                      "RENDER fingerprint", "scalability_before": sg_before, "frames": {},
              "dirty_content_before": state_before["dirty_content"]}
    only_clips = a.clips.split(",") if a.clips else None
    only_frames = [int(x) for x in a.frames.split(",")] if a.frames else None
    tag = "-closeup" if a.closeup else ""
    shots = {}
    imp_rep = run / "reports/ue-import-clips.json"
    imp_sha = (json.loads(imp_rep.read_text(encoding="utf-8")).get("fbx_sha256") or {}) if imp_rep.exists() else {}
    preview_sha = preview["fbx_sha256_of_frames"]
    thr = None
    try:
        # F153: a background / hidden editor throttles its CPU and never converges Lumen + TSR (warm-up 1.7-2.6 for
        # minutes); off in memory for the capture, restored in the finally block
        thr = throttle(ue, False)
        report["throttle_cpu_when_not_foreground"] = thr
        ue.call("scene", "load_level", {"level_path": LEVEL})
        time.sleep(3.0)
        # чужие временные акторы в review-уровне (look-dev «LDv2 *», чужие «… - temporary») — отказ: кадр был бы
        # загрязнён (коллизия 2026-09-30 с look-dev C); свои (PREFIX) остаются от прерванного прогона и пересоздаются
        at_load = task(ue, "actor_labels.py", tmp)["actors"]
        foreign = [x for x, _c in at_load if x.startswith(FOREIGN_PREFIXES) or
                   ("temporary" in x and not x.startswith(PREFIX))]
        report["foreign_actors_in_review_level"] = foreign
        report["lights_cameras_at_load"] = [a for a in at_load if a[1] in WATCH_CLASSES]
        if foreign:
            raise SystemExit("review level holds another task's temporary actors: %s" % foreign[:8])
        base_spec = ({"label": L_BASE, "kind": "static", "asset": base, "location": CELL, "yaw": 90.0}
                     if base else None)
        report["setup"] = task(ue, "h2_review_ue.py", tmp, op="setup", level=LEVEL, hide_label_prefixes=["P17 "],
                               keep_labels=[EXPOSURE_LABEL],
                               lights={"off": [FILL_LABEL],
                                       "key": {"label": KEY_LABEL, "intensity_lux": light["directional"]["intensity"],
                                               "shadow_distance_uu": light["directional"]["shadow"]["distanceUU"],
                                               "cascades": light["directional"]["shadow"]["cascades"],
                                               "contact_shadow_length": light["directional"]["shadow"]["contactShadowLength"],
                                               "rotation_pitch_yaw_roll": KEY_ROTATION}},
                               sky={"label": L_SKY, "cubemap": light["sky"]["cubemap"], "intensity": light["sky"]["intensity"],
                                    "lower_hemisphere_is_black": light["sky"]["lowerHemisphereIsBlack"],
                                    "color_linear": light["sky"]["colorLinear"]},
                               figure={"label": L_FIG, "kind": "skeletal", "asset": mesh, "location": CELL, "yaw": 90.0},
                               base=base_spec)
        for n in SG:
            ue.console("%s 2" % n)
        for flag in SHOW_FLAGS_OFF:
            ue.console("ShowFlag.%s 0" % flag)
        report["scalability_during"] = {n: cvar_value(ue, n) for n in SG}
        time.sleep(6.0)
        if a.closeup:
            cam = {"mode": "closeup", "eye_dist_uu": a.eye_dist, "eye_z_uu": a.eye_z}
        else:
            # F136: the eye from the figure's height and the 16:9 crop of this viewport (MVP eye when it fits)
            w, h = grab(ue, [CELL[0], CELL[1] + MVP_EYE[0], MVP_EYE[1]], [0.0, -90.0, 0.0]).size
            st = preview["state"]
            cam = dict(frame_camera(st.get("top_z"), st.get("bottom_z"), half_tan_v(w, h)), viewport_px=[w, h])
        report["camera"] = cam
        report["closeup"] = {"eye_dist_uu": cam["eye_dist_uu"], "eye_z_uu": cam["eye_z_uu"]} if a.closeup else None
        dist, ez = cam["eye_dist_uu"], cam["eye_z_uu"]
        views = {"front": {"eye": [CELL[0], CELL[1] + dist, ez], "rot": [0.0, -90.0, 0.0], "yaw": 90.0},
                 "q34": {"eye": [CELL[0], CELL[1] + dist, ez], "rot": [0.0, -90.0, 0.0], "yaw": 45.0}}
        v0 = views["front"]
        task(ue, "control_scene_ue.py", tmp, op="camera", label=L_CAM, location=v0["eye"], rotation=v0["rot"], fov=35.0)
        warm, ok = warm_up(lambda: grab(ue, v0["eye"], v0["rot"]))
        report["warmup_mean_abs_diff"] = warm
        report["settle"] = {"threshold": SETTLE_THRESHOLD, "warmup_converged": ok,
                            "status": "settled" if ok else "not_settled", "unsettled_frames": []}
        if not ok:
            print("WARN not_settled: warm-up did not converge (last %s > %.1f); frames are diagnostic only"
                  % (warm[-3:], SETTLE_THRESHOLD), flush=True)
        for clip, c in spec["clips"].items():
            if only_clips and clip not in only_clips:
                continue
            anim = "%s/AM_%s_%s" % (spec["ue"]["clips_folder"], spec["ue_hero"], clip)
            for f in (only_frames or c.get("key_frames", [0, int(c["frames"]) // 2, int(c["frames"])])):
                t = f / 24.0
                task(ue, "control_scene_ue.py", tmp, op="pose", label=L_FIG, anim=anim, time=t)
                for vname, view in views.items():
                    task(ue, "control_scene_ue.py", tmp, op="set", changes=[{"label": L_FIG, "yaw": view["yaw"]}]
                         + ([{"label": L_BASE, "yaw": view["yaw"]}] if base else []))
                    task(ue, "control_scene_ue.py", tmp, op="camera", label=L_CAM, location=view["eye"],
                         rotation=view["rot"], fov=35.0)
                    time.sleep(0.6)
                    im0 = grab(ue, view["eye"], view["rot"])
                    time.sleep(0.5)
                    im = grab(ue, view["eye"], view["rot"])
                    settle = mean_abs_diff(im, im0)
                    w, h = im.size
                    ch = round(w * 9 / 16)
                    box = (0, (h - ch) // 2, w, (h - ch) // 2 + ch) if ch <= h else \
                        ((w - round(h * 16 / 9)) // 2, 0, (w + round(h * 16 / 9)) // 2, h)
                    frame = im.crop(box).resize((1920, 1080), Image.LANCZOS)
                    name = "%s-%s-f%02d-%s%s-ue-editor.jpg" % (spec["ue_hero"], clip, f, vname, tag)
                    path = out / name
                    frame.save(path, quality=88, optimize=True)
                    digest = hashlib.sha256(path.read_bytes()).hexdigest()
                    side = {"schema": SIDECAR_SCHEMA, "class": "editor-mcp-viewport", "frameSha256": digest,
                            "frame": name, "label": "EDITOR frame (W5c H2Anim pose, Cobble light, High), diagnostic; "
                                                    "not K1/K2 acceptance, no RENDER fingerprint",
                            "anim": anim, "imported_fbx_sha256": imp_sha.get(anim.rsplit("/", 1)[1]), "frame_index": f, "time_s": round(t, 5), "view": vname,
                            "camera": {"eye": view["eye"], "rot": view["rot"], "fov": 35.0, "mode": cam["mode"]},
                            "figure_yaw": view["yaw"], "preview_mesh": mesh, "preview_fbx_sha256": preview_sha,
                            "base": base, "settle_mean_abs_diff": settle}
                    path.with_name(path.stem + ".evidence.json").write_text(json.dumps(side, indent=1, sort_keys=True)
                                                                           + "\n", encoding="utf-8", newline="\n")
                    shots[(clip, f, vname)] = frame
                    report["frames"][name] = {"sha256": digest, "anim": anim, "frame": f, "view": vname,
                                              "clip": clip, "imported_fbx_sha256": imp_sha.get(anim.rsplit("/", 1)[1]),
                                              "preview_fbx_sha256": preview_sha, "settle_mean_abs_diff": settle}
                    if settle > SETTLE_THRESHOLD:
                        report["settle"]["unsettled_frames"].append(name)
                        report["settle"]["status"] = "not_settled"
                    print(" ", name, digest[:12], "settle", settle, flush=True)
        # повторная проверка после захвата: за время захвата в уровне не появилось чужих акторов (параллельная задача
        # в общем редакторе без блокировки) — иначе кадры этого прогона помечаются загрязнёнными и удаляются
        known = {a[0] for a in at_load}
        added = [a for a in task(ue, "actor_labels.py", tmp)["actors"] if a[0] not in known and not a[0].startswith(PREFIX)]
        report["foreign_actors_added_during_capture"] = added
        if added:
            for name in list(report["frames"]):
                for f in (out / name, (out / name).with_name(Path(name).stem + ".evidence.json")):
                    if f.exists():
                        f.unlink()
            report["frames"] = {}
            raise SystemExit("foreign actors appeared during the capture, frames discarded: %s" % added[:8])
        # лист собирается после записи отчёта из кадров на диске (build_sheet): и для полного прогона, и после
        # поклиповых прогонов (--clips=X), когда кадры всех клипов уже сняты
        raise _SkipSheet()
    except _SkipSheet:
        report["sheet"] = None
    finally:
        try:
            report["cleanup"] = task(ue, "control_scene_ue.py", tmp, op="cleanup", labels=[L_FIG, L_BASE, L_SKY, L_CAM])
        except Exception as exc:  # noqa: BLE001
            report["cleanup_error"] = str(exc)
        try:
            for n, v in sg_before.items():
                if v is not None:
                    ue.console("%s %s" % (n, v))
            for flag in SHOW_FLAGS_OFF:
                ue.console("ShowFlag.%s 2" % flag)
            report["scalability_after"] = {n: cvar_value(ue, n) for n in SG}
        except Exception as exc:  # noqa: BLE001
            report["console_error"] = str(exc)
        if thr is not None:
            try:
                report["throttle_restored"] = throttle(ue, throttle_was_on(thr))
            except Exception as exc:  # noqa: BLE001
                report["throttle_error"] = str(exc)
        ue.call("scene", "load_level", {"level_path": original.split(".")[0]})
        time.sleep(2.0)
        report["restored_level"] = ue.call("scene", "get_current_level", record=False)
        report["restored_level_dirty"] = ue.call("asset", "is_dirty", {"asset_path": report["restored_level"]}, record=False)
        report["review_level_dirty_after_reload"] = ue.call("asset", "is_dirty", {"asset_path": LEVEL}, record=False)
        report["dirty_content_after"] = editor_state(ue)["dirty_content"]
        if tmp.exists():
            tmp.unlink()
        rep_path = run / ("reports/ue-frames%s.json" % tag)
        if (only_clips or only_frames) and rep_path.exists():
            # частичный прогон: кадры прошлого отчёта сохраняются, эти — заменяются
            prev = json.loads(rep_path.read_text(encoding="utf-8"))
            report["frames"] = dict(prev.get("frames") or {}, **report["frames"])
            if report.get("sheet") is None and prev.get("sheet"):
                report["sheet"] = prev["sheet"]
        if not a.closeup:
            sheet = build_sheet(spec, run, report["frames"])
            report["sheet"] = sheet
            if sheet is None:
                print("sheet: not all key frames captured yet (other clips pending); previous sheet dropped")
        write(rep_path, report)
        print("restored:", report["restored_level"], "dirty:", report["restored_level_dirty"],
              "dirty content after:", report["dirty_content_after"])
        if report.get("settle"):
            print("settle:", report["settle"]["status"], "| camera:", (report.get("camera") or {}).get("mode"),
                  "| base:", base)


def build_sheet(spec, run, frames):
    """Лист UE: строка = клип, ячейки = ключевые кадры (виды front и q34) из preview/ue/*-ue-editor.jpg отчёта.
    Кадр берётся, только если он записан в отчёте и его sha совпадает с файлом, а импортированный FBX кадра совпадает
    с текущим FBX клипа и FBX носителя кадра (preview_fbx_sha256, F145) — с target спеки (иначе кадр устарел).
    None — если кадров не хватает."""
    from PIL import Image, ImageDraw, ImageFont
    out = run / "preview/ue"
    target = REPO / spec["target"]["sk_fbx"]
    cur_preview = sha256_file(target) if target.is_file() else None
    cells = []
    for clip, c in spec["clips"].items():
        fbx = run / "export" / ("AM_%s_%s.fbx" % (spec["ue_hero"], clip))
        cur = hashlib.sha256(fbx.read_bytes()).hexdigest() if fbx.exists() else None
        row = []
        for f in c.get("key_frames", [0, int(c["frames"]) // 2, int(c["frames"])]):
            for vname in ("front", "q34"):
                name = "%s-%s-f%02d-%s-ue-editor.jpg" % (spec["ue_hero"], clip, f, vname)
                rec = frames.get(name)
                path = out / name
                if rec is None or not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != rec["sha256"]:
                    return None
                if rec.get("imported_fbx_sha256") not in (None, cur):
                    return None
                if rec.get("preview_fbx_sha256") not in (None, cur_preview):
                    return None
                row.append((clip, f, vname, path))
        cells.append((clip, row))
    cw, chh = 300, 420
    ncol = max(len(r) for _, r in cells)
    sheet = Image.new("RGB", (cw * ncol, 60 + (chh + 30) * len(cells)), (12, 12, 12))
    d = ImageDraw.Draw(sheet)
    try:
        fnt = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 20)
        big = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 26)
    except OSError:
        fnt = big = ImageFont.load_default()
    d.text((10, 12), "%s H2Anim · UE редактор (DX12/SM6 + Lumen, High, свет Cobble) · кадры диагностики, не приёмка"
           % spec["hero"], fill=(235, 210, 120), font=big)
    for r, (clip, row) in enumerate(cells):
        y = 60 + r * (chh + 30)
        for ci, (_c, f, vname, path) in enumerate(row):
            im = Image.open(path).convert("RGB")
            crop = im.crop((1920 // 2 - 380, 40, 1920 // 2 + 380, 1080))
            crop.thumbnail((cw, chh))
            sheet.paste(crop, (ci * cw + (cw - crop.width) // 2, y + 30))
            d.text((ci * cw + 6, y + 4), "%s f%02d %s" % (clip, f, vname), fill=(220, 220, 220), font=fnt)
    sp = run / "preview" / ("%s-H2Anim-ue-sheet.jpg" % spec["ue_hero"])
    sheet.save(sp, quality=88, optimize=True)
    return {"path": sp.relative_to(REPO).as_posix(), "sha256": hashlib.sha256(sp.read_bytes()).hexdigest()}


def cmd_sheet(a):
    spec = load_spec(a.spec)
    run = run_dir(spec)
    rep_path = run / "reports/ue-frames.json"
    report = json.loads(rep_path.read_text(encoding="utf-8"))
    report["sheet"] = build_sheet(spec, run, report.get("frames") or {})
    write(rep_path, report)
    print("sheet", report["sheet"])


class _SkipSheet(Exception):
    pass


def main():
    for stream in (sys.stdout, sys.stderr):  # RB-11/F47: UTF-8 even in a cp1251 pipe (agents' Bash tool)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("state")
    for name in ("skeleton", "import", "measure", "frames", "sheet"):
        p = sub.add_parser(name)
        p.add_argument("spec")
        if name == "skeleton":
            p.add_argument("--refresh-preview", action="store_true",
                           help="re-import the preview mesh (carrier SK_<Hero>) from the spec's target FBX even when it "
                                "looks current, and stamp its sha (F145); without the flag it is re-imported only when "
                                "its source sha differs from the target")
        if name == "import":
            p.add_argument("--clips")
        if name == "frames":
            base = p.add_mutually_exclusive_group()
            base.add_argument("--base", help="base static mesh (default: spec ue.base, else <hero root>/H2LD/Meshes/"
                                             "SM_<Hero>_H2LD_Base of the stage-7a import; F96)")
            base.add_argument("--no-base", action="store_true", help="frames without a base (the MVP look)")
            p.add_argument("--clips")
            p.add_argument("--frames")
            p.add_argument("--closeup", action="store_true")
            p.add_argument("--eye-dist", type=float, default=100.0)
            p.add_argument("--eye-z", type=float, default=40.0)
            p.add_argument("--light-pinned", help="review report json with light_profile.data (cobble-probe removed by ND-5)")
    a = ap.parse_args()
    {"state": cmd_state, "skeleton": cmd_skeleton, "import": cmd_import, "measure": cmd_measure,
     "frames": cmd_frames, "sheet": cmd_sheet}[a.cmd](a)


if __name__ == "__main__":
    main()
