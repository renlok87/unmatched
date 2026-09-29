"""Валидация тестового клипа (FBX/BVH/GLB) или скелетного меша против контракта рига. Только чтение.

ТОЛЬКО headless (`blender -b`): скрипт вызывает read_factory_settings и завершает
процесс через os._exit. В живом Blender (MCP :9876/:9877) первое выгружает аддон MCP,
второе убивает весь процесс. Поэтому без `-b` скрипт бросает RuntimeError и ничего не
делает: аддон MCP (ловит только Exception) вернёт её клиенту как ошибку, Text Editor
покажет отчёт, процесс останется жив. SystemExit/sys.exit/os._exit для guard не годятся:
в живом Blender они завершают весь процесс (SystemExit — BaseException, мимо except
Exception аддона). Остальные SystemExit ниже достижимы только после guard, то есть в -b.

Запуск (headless Blender 5.2):
  "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup \
      --python tools/tripo-pipeline/anim/validate_clip.py -- <clip.fbx|bvh|glb> [опции]

Опции (key=value):
  --contract=docs/art-pipeline/rig/rig-contract.json
  --skeleton=UM_HUMANOID_17_v2       ключ skeletons (по умолчанию contract.default_skeleton);
                                     UM_HUMANOID_17_v1 закрыт: WARN только для старых файлов по sha256
  --character=Medusa|Arthur|Merlin|Harpy  персонаж скелета: его кость оружия (weapon.L/weapon.R/нет)
  --kind=clip|skeletal-mesh          skeletal-mesh: только арматура, кости, оружие и ref-поза (без action)
  --clip-role=idle|oneshot|terminal  граница клипа: кадр 0 и последний = rest (terminal — только кадр 0);
                                     по умолчанию idle при --loop=true, иначе oneshot
  --expect-fps=24                    ожидаемый FPS (по умолчанию из контракта)
  --expect-duration=2.333            ожидаемая длительность, с (опционально)
  --duration-tol=0.05                допуск длительности, с (по умолчанию из контракта)
  --loop=true|false                  проверять шов цикла (первый ≈ последний кадр)
  --root-policy=in_place|root_motion|any
  --min-pose-change=0.02             доля высоты: мин. пиковый сдвиг сустава за клип
  --pose-change-mode=warn|fail       что давать ниже порога (по умолчанию из контракта: warn
                                     до калибровки порога по визуальному просмотру)
  --retarget-map=<ключ retarget_maps> сравнить скелет через карту (для внешних клипов)
  --bvh-up=Y|Z                       ось «вверх» BVH: Y — стандарт mocap, Z — BVH из Blender
  --out=<report.json>                куда записать отчёт

Проверки: импорт; одна арматура; версия скелета (v1 закрыт); имя объекта арматуры (= кость 0 UE);
соответствие имён и иерархии скелету контракта; кость оружия по стороне; направление ref-позы
(UM_FBX_v1: лицо +X) и ось root; для клипа — действие, fps, длительность, движение костей,
неподвижность/смещение root (объект арматуры = кость 0 UE и pose-кость root), граница клипа
(кадр 0 / последний = rest), видимое изменение позы (пиковый сдвиг голов и хвостов костей / рост),
шов цикла, масштаб костей, правдоподобие длин костей.
Рост — габарит только скиненных мешей (с модификатором Armature); служебные объекты
импортёра glTF (коллекция glTF_not_exported) исключаются.
Правила v2 без Blender — в rig_rules.py (юнит-тесты tests/test_rig_rules.py).
Код выхода: 0 — нет FAIL, 1 — есть FAIL, 2 — ошибка запуска. Статус «pass»
означает техническое соответствие, а не художественную приёмку.
"""
import json
import math
import os
import sys

import bpy
from mathutils import Vector

if not bpy.app.background:
    # RuntimeError, не SystemExit: SystemExit в живом Blender завершает весь процесс.
    raise RuntimeError("validate_clip.py: только headless (blender -b)")

GLTF_HELPER_COLLECTION = "glTF_not_exported"

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
import rig_rules  # noqa: E402  (чистый Python, рядом со скриптом)

LEFT_JOINTS = ("arm_upper.L", "leg_upper.L")
RIGHT_JOINTS = ("arm_upper.R", "leg_upper.R")


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if not argv:
        print(__doc__)
        sys.exit(2)
    src = argv[0]
    opts = {}
    for a in argv[1:]:
        if a.startswith("--") and "=" in a:
            k, v = a[2:].split("=", 1)
            opts[k] = v
    return src, opts


def load_clip(path, bvh_up="Y"):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ext = os.path.splitext(path)[1].lower()
    if ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path, use_anim=True)
    elif ext == ".bvh":
        # Стандартный mocap-BVH: Y-up (forward -Z). BVH из Blender-экспорта: Z-up (forward Y).
        fwd, up = ("-Z", "Y") if bvh_up.upper() == "Y" else ("Y", "Z")
        bpy.ops.import_anim.bvh(filepath=path, update_scene_fps=True,
                                update_scene_duration=True, axis_forward=fwd, axis_up=up)
    elif ext in (".glb", ".gltf"):
        # bone_heuristic="BLENDER" (по умолчанию) при масштабе объекта арматуры 0.01 завышает
        # длины костей в 100 раз (хвосты улетают, измерено 2026-09-28); TEMPERANCE даёт длины
        # в мировом масштабе. Форма костей (Icosphere в glTF_not_exported) не нужна.
        bpy.ops.import_scene.gltf(filepath=path, bone_heuristic="TEMPERANCE", disable_bone_shape=True)
    else:
        raise SystemExit(f"unsupported clip format: {ext}")


def check(report, name, status, **kw):
    report["checks"].append({"check": name, "status": status, **kw})


def verdict(report, name, result):
    status, detail = result
    check(report, name, status, **detail)


def quat_angle_deg(q1, q2):
    d = abs(q1.dot(q2))
    return math.degrees(2 * math.acos(min(1.0, d)))


def main():
    src, opts = parse_args()
    contract_path = opts.get("contract", os.path.join(REPO, "docs/art-pipeline/rig/rig-contract.json"))
    with open(contract_path, encoding="utf-8") as f:
        contract = json.load(f)
    sk_key, skel = rig_rules.skeleton_entry(contract, opts.get("skeleton"))
    character = opts.get("character")
    rig_rules.character_entry(skel, character)  # KeyError на неизвестного персонажа до импорта
    kind = opts.get("kind", "clip").lower()
    if kind not in ("clip", "skeletal-mesh"):
        raise SystemExit(f"--kind: clip|skeletal-mesh, получено {kind}")
    clip_rules = contract.get("clips", {})
    exp_fps = float(opts.get("expect-fps", clip_rules.get("fps", 24)))
    dur_tol = float(opts.get("duration-tol", clip_rules.get("duration_tolerance_s", 0.05)))
    min_change = float(opts.get("min-pose-change", clip_rules.get("min_visible_pose_change_of_height", 0.02)))
    pose_mode = opts.get("pose-change-mode", clip_rules.get("visible_pose_change_mode", "warn")).lower()
    if pose_mode not in ("warn", "fail"):
        raise SystemExit(f"--pose-change-mode: warn|fail, получено {pose_mode}")
    seam_tol = clip_rules.get("loop_seam_tolerance_of_height", 0.005)
    rm_tol = contract.get("root_motion", {}).get("in_place_tolerance_of_height", 0.005)
    root_policy = opts.get("root-policy", contract.get("root_motion", {}).get("policy_default", "in_place"))
    loop = opts.get("loop", "").lower() in ("1", "true", "yes")
    role = rig_rules.default_role(loop, opts.get("clip-role"))

    clip_abs = os.path.abspath(src)
    clip_rel = os.path.relpath(clip_abs, REPO) if clip_abs.lower().startswith(REPO.lower()) else clip_abs
    report = {"schema": "unmatched.clip-validation/2", "clip": clip_rel.replace("\\", "/"),
              "clip_bytes": os.path.getsize(src), "clip_sha256": rig_rules.sha256_file(src),
              "contract": os.path.relpath(contract_path, REPO).replace("\\", "/"),
              "contract_revision": contract.get("revision"), "skeleton": sk_key, "character": character,
              "kind": kind, "clip_role": role if kind == "clip" else None,
              "blender": bpy.app.version_string, "checks": [], "bones": {}}
    try:
        load_clip(src, opts.get("bvh-up", "Y"))
    except Exception as exc:  # noqa: BLE001 — отчёт об ошибке импорта
        check(report, "import", "fail", detail=str(exc))
        return finish(report, opts)
    check(report, "import", "pass")
    sc = bpy.context.scene
    arms = [o for o in sc.objects if o.type == "ARMATURE"]
    if len(arms) != 1:
        check(report, "single_armature", "fail", value=len(arms))
        return finish(report, opts)
    arm = arms[0]
    check(report, "single_armature", "pass", value=arm.name)
    ext = os.path.splitext(src)[1].lower()
    external = ext == ".bvh" or bool(opts.get("retarget-map"))
    verdict(report, "skeleton_version", rig_rules.skeleton_version_verdict(sk_key, skel, report["clip_sha256"]))
    # Имя объекта арматуры = имя кости 0 в UE (legacy FBX) и носителя root motion.
    verdict(report, "armature_object_name",
            rig_rules.armature_name_verdict(arm.name, skel.get("armature_object", {}), external))

    # --- скелет против контракта -------------------------------------------------
    names = {b.name: (b.parent.name if b.parent else None) for b in arm.data.bones}
    report["bone_count"] = len(names)
    required, optional = rig_rules.expected_bones(skel, character)
    if opts.get("retarget-map"):
        rmap = {k: v for k, v in contract["retarget_maps"][opts["retarget-map"]].items()
                if isinstance(v, str) and k not in ("status", "note")}
        mapped = {src_b: dst for src_b, dst in rmap.items() if src_b in names}
        covered = sorted(set(mapped.values()) & set(required))
        weapon_like = set(rig_rules.weapon_bones(skel)) | set(skel.get("weapon_legacy_names", ["weapon"]))
        missing = sorted(set(required) - set(covered) - weapon_like)
        check(report, "skeleton_via_retarget_map", "pass" if not missing else "fail",
              map=opts["retarget-map"], covered=len(covered), missing=missing,
              source_bones=len(names))
    else:
        verdict(report, "skeleton_contract", rig_rules.skeleton_contract_verdict(names, required, optional))
        verdict(report, "weapon_side", rig_rules.weapon_verdict(names, skel, character))

    # --- ref-поза: направление лица и ось root -----------------------------------
    ref_pose = skel.get("ref_pose")
    mw0 = arm.matrix_world
    left = [tuple(mw0 @ arm.data.bones[n].head_local) for n in LEFT_JOINTS if n in arm.data.bones]
    right = [tuple(mw0 @ arm.data.bones[n].head_local) for n in RIGHT_JOINTS if n in arm.data.bones]
    if ref_pose is None:
        check(report, "ref_pose_facing", "info", note="в скелете нет ref_pose (контракт v1)")
    elif not left or not right:
        check(report, "ref_pose_facing", "info" if external else "fail",
              note="нет пар суставов .L/.R для направления", left=len(left), right=len(right))
    else:
        yaw = rig_rules.facing_yaw_deg(left, right)
        verdict(report, "ref_pose_facing", rig_rules.facing_verdict(yaw, ref_pose, external))
        if "root" in arm.data.bones:
            x_axis = tuple((mw0.to_3x3() @ arm.data.bones["root"].matrix_local.to_3x3()).col[0])
            verdict(report, "ref_pose_root_axis", rig_rules.root_axis_verdict(x_axis, ref_pose, external))

    if kind == "skeletal-mesh":
        return finish(report, opts)

    act = arm.animation_data.action if arm.animation_data else None
    if act is None:
        check(report, "action", "fail", detail="у арматуры нет действия")
        return finish(report, opts)
    check(report, "action", "pass", value=act.name, actions_in_file=len(bpy.data.actions))

    fps = sc.render.fps / sc.render.fps_base
    report["fps"] = round(fps, 4)
    check(report, "fps", "pass" if abs(fps - exp_fps) < 1e-3 else "fail", value=round(fps, 4), expected=exp_fps)
    f0, f1 = act.frame_range
    f0i, f1i = int(round(f0)), int(round(f1))
    duration = (f1 - f0) / fps
    report.update({"frame_start": f0, "frame_end": f1, "frames": f1i - f0i + 1, "duration_s": round(duration, 4)})
    if "expect-duration" in opts:
        exp_d = float(opts["expect-duration"])
        check(report, "duration", "pass" if abs(duration - exp_d) <= dur_tol else "fail",
              value=round(duration, 4), expected=exp_d, tol=dur_tol)
    else:
        check(report, "duration", "info", value=round(duration, 4), note="ожидание не задано")
    if f1i - f0i < 1:
        check(report, "frame_count", "fail", value=f1i - f0i + 1)
        return finish(report, opts)

    # --- выборка кадров ------------------------------------------------------------
    frames = list(range(f0i, f1i + 1))
    rest_pts = ([arm.matrix_world @ b.head_local for b in arm.data.bones]
                + [arm.matrix_world @ b.tail_local for b in arm.data.bones])
    zs = [p.z for p in rest_pts]
    # Рост — только по скиненным мешам этой арматуры; служебные меши импортёра glTF
    # (Icosphere в glTF_not_exported) и нескиненные объекты не учитываются.
    meshes = [o for o in sc.objects if o.type == "MESH"
              and not any(c.name == GLTF_HELPER_COLLECTION for c in o.users_collection)
              and any(m.type == "ARMATURE" and m.object == arm for m in o.modifiers)]
    report["reference_meshes"] = sorted(o.name for o in meshes)
    if meshes:
        pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
        height = max(p.z for p in pts) - min(p.z for p in pts)
    else:
        height = max(zs) - min(zs)
    height = max(height, 1e-6)
    report["reference_height"] = round(height, 5)
    report["reference_height_source"] = "skinned_mesh_bbox" if meshes else "bone_heads_tails"
    # Длины костей задаёт эвристика импортёра (в FBX/glTF длины нет); хвост длиннее роста —
    # признак сбоя эвристики, тогда сдвиги по хвостам недостоверны.
    bone_len_max = max((arm.matrix_world @ b.tail_local - arm.matrix_world @ b.head_local).length
                       for b in arm.data.bones) / height
    check(report, "bone_length_plausible", "pass" if bone_len_max <= 1.0 else "warn",
          max_bone_length_of_height=round(bone_len_max, 4), max=1.0)
    # rest-поза в порядке pose.bones (голова и хвост), в пространстве арматуры
    rest_local = ([arm.data.bones[pb.name].head_local.copy() for pb in arm.pose.bones]
                  + [arm.data.bones[pb.name].tail_local.copy() for pb in arm.pose.bones])
    first = {}
    rot_max = {pb.name: 0.0 for pb in arm.pose.bones}
    loc_max = {pb.name: 0.0 for pb in arm.pose.bones}
    scale_dev = 0.0
    pose_change = []
    obj_path = []
    root_path = []
    first_heads = None
    last_heads = None
    boundary = {}
    for fr in frames:
        sc.frame_set(fr)
        mw = arm.matrix_world
        obj_path.append(mw.translation.copy())
        if "root" in arm.pose.bones:
            root_path.append(mw @ arm.pose.bones["root"].head)
        # головы и хвосты костей в мире: хвост ловит поворот концевых костей
        heads = [mw @ pb.head for pb in arm.pose.bones] + [mw @ pb.tail for pb in arm.pose.bones]
        if fr in (frames[0], frames[-1]):
            # граница клипа: поза против rest в мире этого же кадра (движение объекта не входит)
            rest_now = [mw @ p for p in rest_local]
            boundary[fr] = max((h - r).length for h, r in zip(heads, rest_now)) / height
        if first_heads is None:
            first_heads = heads
        last_heads = heads
        shifts = [(h - h0).length / height for h, h0 in zip(heads, first_heads)]
        pose_change.append((max(shifts), sum(shifts) / len(shifts)))
        for pb in arm.pose.bones:
            q = pb.matrix_basis.to_quaternion()
            t = pb.matrix_basis.to_translation()
            s = pb.matrix_basis.to_scale()
            scale_dev = max(scale_dev, max(abs(x - 1.0) for x in s))
            if pb.name not in first:
                first[pb.name] = (q, t)
            q0, t0 = first[pb.name]
            rot_max[pb.name] = max(rot_max[pb.name], quat_angle_deg(q, q0))
            loc_max[pb.name] = max(loc_max[pb.name], (t - t0).length)
    moving = {n: round(v, 3) for n, v in rot_max.items() if v > 0.5}
    report["bones"] = {n: {"max_rot_deg": round(rot_max[n], 3), "max_loc": round(loc_max[n], 5)}
                       for n in rot_max}
    check(report, "bones_move", "pass" if moving else "fail", moving_bones=len(moving),
          top=sorted(moving.items(), key=lambda kv: -kv[1])[:8])
    check(report, "bone_scale_unit", "pass" if scale_dev < 1e-3 else "warn", max_deviation=round(scale_dev, 5))
    verdict(report, "clip_boundary_rest",
            rig_rules.boundary_verdict(role, boundary[frames[0]], boundary[frames[-1]],
                                       skel.get("clip_boundaries", {}), external))

    # --- root ---------------------------------------------------------------------
    def path_stats(path):
        d_end = (path[-1] - path[0])
        exc = max((p - path[0]).length for p in path)
        return {"end_delta": [round(x, 5) for x in d_end], "end_delta_of_height": round(d_end.length / height, 5),
                "max_excursion_of_height": round(exc / height, 5)}
    obj_st = path_stats(obj_path)
    report["root_object"] = obj_st
    if root_path:
        report["root_bone"] = path_stats(root_path)
    rb = report.get("root_bone", {"end_delta_of_height": 0, "max_excursion_of_height": 0})
    if root_policy == "in_place":
        ok = (obj_st["max_excursion_of_height"] <= rm_tol and rb["max_excursion_of_height"] <= rm_tol)
        check(report, "root_in_place", "pass" if ok else "fail", object=obj_st, root_bone=rb, tol_of_height=rm_tol)
    elif root_policy == "root_motion":
        moved = obj_st["end_delta_of_height"] > rm_tol
        check(report, "root_motion_on_object", "pass" if moved and rb["max_excursion_of_height"] <= rm_tol else "fail",
              object=obj_st, root_bone=rb,
              note="root motion должен быть на объекте арматуры (кость 0 UE), pose-кость root неподвижна")
    else:
        check(report, "root", "info", object=obj_st, root_bone=rb)

    # --- видимое изменение позы и шов цикла ---------------------------------------
    peak_max = max(p[0] for p in pose_change)
    peak_mean = max(p[1] for p in pose_change)
    peak_i = [p[0] for p in pose_change].index(peak_max)
    check(report, "visible_pose_change", "pass" if peak_max >= min_change else pose_mode,
          peak_max_joint_shift_of_height=round(peak_max, 5),
          peak_mean_joint_shift_of_height=round(peak_mean, 5), min=min_change, mode=pose_mode,
          peak_frame=frames[peak_i],
          note="макс. сдвиг головы/хвоста кости относительно первого кадра, доля высоты фигуры; "
               "порог — предложение, до калибровки по визуальному просмотру ниже порога = WARN")
    seam = sum((a - b).length for a, b in zip(last_heads, first_heads)) / len(first_heads) / height
    if loop:
        check(report, "loop_seam", "pass" if seam <= seam_tol else "fail",
              first_last_shift_of_height=round(seam, 5), tol=seam_tol)
    else:
        check(report, "loop_seam", "info", first_last_shift_of_height=round(seam, 5))
    return finish(report, opts)


def finish(report, opts):
    fails = [c["check"] for c in report["checks"] if c["status"] == "fail"]
    warns = [c["check"] for c in report["checks"] if c["status"] == "warn"]
    report["result"] = "fail" if fails else "pass"
    report["fails"], report["warnings"] = fails, warns
    out = opts.get("out")
    if out:
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
    print("CLIP_VALIDATION", report["result"].upper(), os.path.basename(report["clip"]),
          "fps", report.get("fps"), "dur", report.get("duration_s"), "fails", fails, "warns", warns)
    sys.stdout.flush()
    os._exit(1 if fails else 0)


try:
    main()
except (KeyError, ValueError) as exc:  # неверные опции (скелет, персонаж, роль) — ошибка запуска, код 2
    print("CLIP_VALIDATION ERROR", exc)
    sys.stdout.flush()
    os._exit(2)
