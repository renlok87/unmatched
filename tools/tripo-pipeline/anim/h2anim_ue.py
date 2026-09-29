"""H2Anim в живом UnrealEditor (волна 5c): канонический скелет героя, импорт клипов, замеры, контактный лист.

    python tools/tripo-pipeline/anim/h2anim_ue.py state
    python tools/tripo-pipeline/anim/h2anim_ue.py skeleton <spec.json>
    python tools/tripo-pipeline/anim/h2anim_ue.py import   <spec.json> [--clips=Idle,...]
    python tools/tripo-pipeline/anim/h2anim_ue.py measure  <spec.json>
    python tools/tripo-pipeline/anim/h2anim_ue.py frames   <spec.json> [--base=/Game/.../SM_*_Base] [--clips=Idle]
    python tools/tripo-pipeline/anim/h2anim_ue.py sheet    <spec.json>   (лист UE из уже снятых кадров, без редактора)

Живой редактор (MCP 127.0.0.1:8123 + консоль редактора, review/ue_live.py); шаги строго последовательно.
  skeleton  review/ue_py/canonical_skeleton.py: /Game/PipelineCandidates/<Hero>/Rig/SK_<Hero>_Skeleton из
            SK_<Hero>_H2.fbx спеки (носитель SK_<Hero> рядом); идемпотентно — существующий скелет не трогается;
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
            --clips=A,B и --frames=3,4,5 сужают набор; --closeup: крупный план (камера в --eye-dist uu от фигуры
            на высоте --eye-z, FOV 35, кадр 1920×1080 на позу) — кадры *-closeup-ue-editor.jpg и отчёт
            reports/ue-frames-closeup.json, общий лист не пересобирается (anim-v2 fix: f03–f05 Arthur LungeAttack).
            Длинные захваты — по одному клипу (--clips=X): лист собирается из кадров на диске, когда сняты все
            клипы; кадр с imported_fbx_sha256, не совпадающим с текущим FBX клипа, считается устаревшим.
Отчёты — <run>/reports/ue-*.json, кадры — <run>/preview/ue/. Кадры редактора — диагностика, не приёмка K1/K2.
"""
import argparse
import base64
import hashlib
import io
import json
import math
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
    before = editor_state(ue)
    res = task(ue, "canonical_skeleton.py", out, fbx=str((REPO / spec["target"]["sk_fbx"]).resolve()).replace("\\", "/"),
               folder=folder, mesh_name=mesh_name)
    after = editor_state(ue)
    res.update({"spec": spec["_path"], "target_sk_fbx": spec["target"]["sk_fbx"],
                "target_sha256": spec["target"]["sha256"], "dirty_content_before": before["dirty_content"],
                "dirty_content_after": after["dirty_content"], "tool": "tools/tripo-pipeline/anim/h2anim_ue.py skeleton"})
    write(out, res)
    print("skeleton", res["skeleton"], "created" if res.get("created") else "exists", "bones", len(res["bones_in_order"]),
          "bone0", res["bone0"], "dirty after", after["dirty_content"])


def cmd_import(a):
    spec = load_spec(a.spec)
    ue = Ue()
    names = a.clips.split(",") if a.clips else list(spec["clips"])
    run = run_dir(spec)
    clips = [{"fbx": str((run / "export" / ("AM_%s_%s.fbx" % (spec["ue_hero"], n))).resolve()).replace("\\", "/"),
              "folder": spec["ue"]["clips_folder"], "name": "AM_%s_%s" % (spec["ue_hero"], n),
              "skeleton": spec["ue"]["skeleton"], "uniform_scale": None, "force_root_lock": True} for n in names]
    out = run / "reports/ue-import-clips.json"
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
    res = task(ue, "measure_clips.py", out, clips=clips, height_uu=round(max(heights), 3), min_pose_change=0.02)
    res.update({"spec": spec["_path"], "tool": "tools/tripo-pipeline/anim/h2anim_ue.py measure -> review/ue_py/measure_clips.py"})
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
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    spec = load_spec(a.spec)
    run = run_dir(spec)
    out = run / "preview/ue"
    out.mkdir(parents=True, exist_ok=True)
    tmp = out / "_task.json"
    ue = Ue()
    light = json.loads(PROFILES_JSON.read_text(encoding="utf-8"))["lightProfiles"]["cobble-probe"]
    mesh = spec["ue"]["mesh_for_preview"]
    original = ue.call("scene", "get_current_level", record=False)
    if ue.call("asset", "is_dirty", {"asset_path": original}, record=False):
        raise SystemExit("open level %s has unsaved changes; refusing to switch levels" % original)
    if original.split(".")[0] == LEVEL:
        raise SystemExit("the review level itself is open; open another level first")
    if ue.call("asset", "is_dirty", {"asset_path": LEVEL}, record=False):
        raise SystemExit("the review level has unsaved changes in memory (someone else is using it)")
    state_before = editor_state(ue)
    sg_before = {n: cvar_value(ue, n) for n in SG}
    report = {"schema": "unmatched.h2anim-ue-frames/1", "spec": spec["_path"], "mesh": mesh, "base": a.base,
              "level": LEVEL, "original_level": original, "light_profile": "cobble-probe (S08ArtBoardProfiles.json)",
              "kind": "EDITOR frames (live UnrealEditor via MCP CaptureViewport); diagnostic, not K1/K2 acceptance, no "
                      "RENDER fingerprint", "scalability_before": sg_before, "frames": {},
              "dirty_content_before": state_before["dirty_content"]}
    dist, ez = (a.eye_dist, a.eye_z) if a.closeup else (200.0, 31.0)
    views = {"front": {"eye": [CELL[0], CELL[1] + dist, ez], "rot": [0.0, -90.0, 0.0], "yaw": 90.0},
             "q34": {"eye": [CELL[0], CELL[1] + dist, ez], "rot": [0.0, -90.0, 0.0], "yaw": 45.0}}
    only_clips = a.clips.split(",") if a.clips else None
    only_frames = [int(x) for x in a.frames.split(",")] if a.frames else None
    tag = "-closeup" if a.closeup else ""
    report["closeup"] = {"eye_dist_uu": dist, "eye_z_uu": ez} if a.closeup else None
    shots = {}
    imp_rep = run / "reports/ue-import-clips.json"
    imp_sha = (json.loads(imp_rep.read_text(encoding="utf-8")).get("fbx_sha256") or {}) if imp_rep.exists() else {}
    try:
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
        base_spec = ({"label": L_BASE, "kind": "static", "asset": a.base, "location": CELL, "yaw": 90.0}
                     if a.base else None)
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
        v0 = views["front"]
        task(ue, "control_scene_ue.py", tmp, op="camera", label=L_CAM, location=v0["eye"], rotation=v0["rot"], fov=35.0)
        prev = None
        warm = []
        for _ in range(20):
            im = grab(ue, v0["eye"], v0["rot"])
            if prev is not None:
                warm.append(round(float(np.abs(np.asarray(im, np.int16) - np.asarray(prev, np.int16)).mean()), 4))
                if warm[-1] < 0.05 and len(warm) >= 3:
                    break
            prev = im
            time.sleep(1.5)
        report["warmup_mean_abs_diff"] = warm
        for clip, c in spec["clips"].items():
            if only_clips and clip not in only_clips:
                continue
            anim = "%s/AM_%s_%s" % (spec["ue"]["clips_folder"], spec["ue_hero"], clip)
            for f in (only_frames or c.get("key_frames", [0, int(c["frames"]) // 2, int(c["frames"])])):
                t = f / 24.0
                task(ue, "control_scene_ue.py", tmp, op="pose", label=L_FIG, anim=anim, time=t)
                for vname, view in views.items():
                    task(ue, "control_scene_ue.py", tmp, op="set", changes=[{"label": L_FIG, "yaw": view["yaw"]}]
                         + ([{"label": L_BASE, "yaw": view["yaw"]}] if a.base else []))
                    task(ue, "control_scene_ue.py", tmp, op="camera", label=L_CAM, location=view["eye"],
                         rotation=view["rot"], fov=35.0)
                    time.sleep(0.6)
                    grab(ue, view["eye"], view["rot"])
                    time.sleep(0.5)
                    im = grab(ue, view["eye"], view["rot"])
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
                            "camera": {"eye": view["eye"], "rot": view["rot"], "fov": 35.0}, "figure_yaw": view["yaw"]}
                    path.with_name(path.stem + ".evidence.json").write_text(json.dumps(side, indent=1, sort_keys=True)
                                                                           + "\n", encoding="utf-8", newline="\n")
                    shots[(clip, f, vname)] = frame
                    report["frames"][name] = {"sha256": digest, "anim": anim, "frame": f, "view": vname,
                                              "clip": clip, "imported_fbx_sha256": imp_sha.get(anim.rsplit("/", 1)[1])}
                    print(" ", name, digest[:12], flush=True)
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


def build_sheet(spec, run, frames):
    """Лист UE: строка = клип, ячейки = ключевые кадры (виды front и q34) из preview/ue/*-ue-editor.jpg отчёта.
    Кадр берётся, только если он записан в отчёте и его sha совпадает с файлом, а импортированный FBX кадра совпадает
    с текущим FBX клипа (иначе кадр устарел). None — если кадров не хватает."""
    from PIL import Image, ImageDraw, ImageFont
    out = run / "preview/ue"
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
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("state")
    for name in ("skeleton", "import", "measure", "frames", "sheet"):
        p = sub.add_parser(name)
        p.add_argument("spec")
        if name == "import":
            p.add_argument("--clips")
        if name == "frames":
            p.add_argument("--base")
            p.add_argument("--clips")
            p.add_argument("--frames")
            p.add_argument("--closeup", action="store_true")
            p.add_argument("--eye-dist", type=float, default=100.0)
            p.add_argument("--eye-z", type=float, default=40.0)
    a = ap.parse_args()
    {"state": cmd_state, "skeleton": cmd_skeleton, "import": cmd_import, "measure": cmd_measure,
     "frames": cmd_frames, "sheet": cmd_sheet}[a.cmd](a)


if __name__ == "__main__":
    main()
