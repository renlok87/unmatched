"""Правила контракта рига v2 без Blender (чистый Python, stdlib).

Их вызывает validate_clip.py (headless Blender) и проверяют юнит-тесты
tools/tripo-pipeline/tests/test_rig_rules.py. Каждая функция получает уже измеренные
числа или имена и возвращает вердикт (status, detail). status: pass | warn | fail | info.

Контракт: docs/art-pipeline/rig/rig-contract.json (schema unmatched.rig-contract/2).
Статусы проверок — техническое соответствие, не художественная приёмка.
"""
import hashlib
import math

ROLES = ("idle", "oneshot", "terminal")
STATUSES = ("pass", "warn", "fail", "info")


# ----------------------------------------------------------------------------- контракт
def skeleton_entry(contract, key=None):
    """(key, skeleton dict). По умолчанию contract.default_skeleton, иначе UM_HUMANOID_17_v1."""
    key = key or contract.get("default_skeleton") or "UM_HUMANOID_17_v1"
    skels = contract.get("skeletons", {})
    if key not in skels:
        raise KeyError("skeleton %s is not in the contract (%s)" % (key, ", ".join(sorted(skels))))
    return key, skels[key]


def character_entry(skel, character):
    """Запись персонажа скелета или None, если персонаж не задан. KeyError — неизвестный персонаж."""
    if not character:
        return None
    chars = skel.get("characters") or {}
    if character not in chars:
        raise KeyError("character %s is not in skeleton characters (%s)" % (character, ", ".join(sorted(chars)) or "none"))
    return chars[character]


def weapon_bones(skel):
    """{имя: {parent, ...}} боковых костей оружия (v2); пусто для v1."""
    return dict(skel.get("weapon_bones") or {})


def expected_bones(skel, character=None):
    """(required {name: parent}, optional {name: parent}) для скелета и, если задан, персонажа.

    v1: все кости обязательны (weapon с одним именем). v2: базовые кости обязательны, боковые кости
    оружия опциональны; при заданном персонаже его weapon_bone становится обязательным, чужая — лишней.
    """
    required, optional = {}, {}
    wb = weapon_bones(skel)
    for b in skel["bones"]:
        if b["name"] in wb or b.get("optional"):
            optional[b["name"]] = b["parent"]
        else:
            required[b["name"]] = b["parent"]
    ch = character_entry(skel, character)
    if ch is not None and wb:
        want = ch.get("weapon_bone")
        for name in list(optional):
            if name in wb:
                parent = optional.pop(name)
                if name == want:
                    required[name] = parent
    return required, optional


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ----------------------------------------------------------------------------- вердикты
def skeleton_version_verdict(skel_key, skel, clip_sha256):
    """v1 закрыт для новых клипов: WARN только для перечисленных по sha256 старых файлов, иначе FAIL."""
    if not skel.get("closed_for_new_clips"):
        return "pass", {"skeleton": skel_key}
    allowed = {e["sha256"]: e["path"] for e in skel.get("grandfathered_files", [])}
    if clip_sha256 in allowed:
        return "warn", {"skeleton": skel_key, "grandfathered": allowed[clip_sha256],
                        "note": "старый тестовый файл, допущен по sha256; новые клипы — только %s"
                                % skel.get("superseded_by", "новый скелет")}
    return "fail", {"skeleton": skel_key, "sha256": clip_sha256,
                    "note": "скелет закрыт для новых клипов; нужен %s" % skel.get("superseded_by", "новый скелет")}


def armature_name_verdict(name, rule, external=False):
    """Имя объекта арматуры = кость 0 в UE. external — BVH или клип с картой ретаргета (имя задаётся при перекладке)."""
    want = (rule or {}).get("name")
    if external:
        return "info", {"value": name, "expected": want, "note": "BVH/внешний скелет: имя задаётся при перекладке в контракт"}
    if not want:
        return "info", {"value": name, "note": "в контракте нет armature_object.name"}
    if name == want:
        return "pass", {"value": name}
    if name in rule.get("legacy_names", []):
        policy = rule.get("legacy_policy", "warn")
        return policy, {"value": name, "expected": want,
                        "note": "старое имя (кость 0 не совпадёт с общим скелетом); политика контракта: %s" % policy}
    return "fail", {"value": name, "expected": want}


def skeleton_contract_verdict(bones, required, optional):
    """bones: {name: parent} клипа. Нет обязательной кости или неверный родитель — FAIL; лишние — WARN."""
    missing = sorted(set(required) - set(bones))
    parent_bad = sorted(n for n in required if n in bones and bones[n] != required[n])
    parent_bad += sorted(n for n in optional if n in bones and bones[n] != optional[n])
    extra = sorted(set(bones) - set(required) - set(optional))
    if missing or parent_bad:
        status = "fail"
    elif extra:
        status = "warn"
    else:
        status = "pass"
    return status, {"missing": missing, "extra": extra, "parent_mismatch": parent_bad}


def weapon_verdict(bones, skel, character=None):
    """Кость оружия по стороне (v2): weapon.L под hand.L, weapon.R под hand.R, у персонажа только своя.

    Одно имя `weapon` (v1) в v2 — FAIL: меш с weapon под hand.R не сливается со скелетом, где weapon
    под hand.L (USkeleton::MergeBonesToBoneTree сверяет цепочку родителей).
    """
    wb = weapon_bones(skel)
    if not wb:
        return "info", {"note": "в скелете нет weapon_bones (контракт v1): сторона оружия не проверяется"}
    legacy = [n for n in skel.get("weapon_legacy_names", ["weapon"]) if n in bones]
    present = sorted(n for n in bones if n in wb)
    detail = {"present": present, "legacy_present": legacy}
    problems = []
    if legacy:
        problems.append("старое имя кости оружия %s: в v2 только %s" % (legacy, "/".join(sorted(wb))))
    if len(present) > 1:
        problems.append("у героя может быть только одна кость оружия, найдено %s" % present)
    for n in present:
        if bones[n] != wb[n]["parent"]:
            problems.append("%s: родитель %s, ожидается %s" % (n, bones[n], wb[n]["parent"]))
    ch = character_entry(skel, character)
    if ch is not None:
        want = ch.get("weapon_bone")
        detail["character"] = character
        detail["expected"] = want
        if want is None and present:
            problems.append("у %s нет оружия, а в клипе %s" % (character, present))
        elif want is not None and present != [want]:
            problems.append("у %s ожидается %s, в клипе %s" % (character, want, present or "нет"))
    if problems:
        detail["problems"] = problems
        return "fail", detail
    return "pass", detail


def _mean(points):
    n = float(len(points))
    return tuple(sum(p[i] for p in points) / n for i in range(3))


def facing_yaw_deg(left_points, right_points):
    """Направление «лицом» по анатомии: боковой вектор (среднее .L − среднее .R) в плоскости XY,
    вперёд = боковой × Z (при .L = +X и лице −Y это даёт −Y). Угол от +X, градусы, (−180, 180]."""
    if not left_points or not right_points:
        raise ValueError("need left and right joints")
    lx, ly, _ = _mean(left_points)
    rx, ry, _ = _mean(right_points)
    sx, sy = lx - rx, ly - ry
    if math.hypot(sx, sy) < 1e-9:
        raise ValueError("left and right joints coincide in XY")
    # (sx, sy, 0) x (0, 0, 1) = (sy, -sx, 0)
    return math.degrees(math.atan2(-sx, sy))


def yaw_delta_deg(a, b):
    """a − b, приведённое к (−180, 180]."""
    d = (a - b) % 360.0
    return d - 360.0 if d > 180.0 else d


def facing_verdict(yaw_deg, ref_pose, external=False):
    """Ref-поза по UM_FBX_v1: в FBX, открытом в Blender, лицо +X (yaw 0). Черновики без поворота — −Y (yaw −90)."""
    expected = float(ref_pose.get("expected_facing_yaw_deg", 0.0))
    tol = float(ref_pose.get("facing_tolerance_deg", 10.0))
    detail = {"facing_yaw_deg": round(yaw_deg, 3), "expected": expected, "tol_deg": tol,
              "delta_deg": round(yaw_delta_deg(yaw_deg, expected), 3)}
    if external:
        detail["note"] = "BVH/внешний скелет: ось приводится при перекладке"
        return "info", detail
    return ("pass" if abs(detail["delta_deg"]) <= tol else "fail"), detail


def root_axis_verdict(root_x_axis, ref_pose, external=False):
    """Вторичная проверка поворота ref-позы: ось X pose-кости root (жёсткий поворот UM_FBX_v1 с roll)."""
    want = ref_pose.get("root_bone_x_axis_yaw_deg")
    x, y = root_x_axis[0], root_x_axis[1]
    if want is None or math.hypot(x, y) < 1e-6:
        return "info", {"root_x_axis": [round(v, 4) for v in root_x_axis], "note": "ось X root вертикальна или ожидание не задано"}
    yaw = math.degrees(math.atan2(y, x))
    delta = yaw_delta_deg(yaw, float(want))
    detail = {"root_x_axis_yaw_deg": round(yaw, 3), "expected": want, "delta_deg": round(delta, 3)}
    if external:
        return "info", detail
    tol = float(ref_pose.get("facing_tolerance_deg", 10.0))
    return ("pass" if abs(delta) <= tol else "warn"), detail


def default_role(loop, role=None):
    if role:
        role = role.lower()
        if role not in ROLES:
            raise ValueError("clip role must be one of %s, got %s" % (ROLES, role))
        return role
    return "idle" if loop else "oneshot"


def boundary_verdict(role, first_shift, last_shift, rules, external=False):
    """Кадр 0 и последний кадр против rest-позы (доля роста). idle/oneshot: оба = rest;
    terminal (DeathSettle): только кадр 0, финальная поза удерживается."""
    tol = float(rules.get("tolerance_of_height", 0.005))
    detail = {"role": role, "first_vs_rest_of_height": round(first_shift, 5),
              "last_vs_rest_of_height": round(last_shift, 5), "tol_of_height": tol}
    if external:
        detail["note"] = "внешний клип: rest-поза другого скелета, граница проверяется после перекладки"
        return "info", detail
    bad = []
    if first_shift > tol:
        bad.append("first")
    if role in ("idle", "oneshot") and last_shift > tol:
        bad.append("last")
    if bad:
        detail["not_rest"] = bad
        return "fail", detail
    return "pass", detail


# ----------------------------------------------------------------------------- UE и IK
def ue_clip_import_problems(settings, contract, root_policy="in_place"):
    """Проверка измеренных настроек AnimSequence после импорта в UE против contract.ue_import.clip_import.

    settings: {"force_root_lock": bool, "enable_root_motion": bool, "factory": str}. Возвращает список проблем.
    """
    rule = contract.get("ue_import", {}).get("clip_import", {})
    problems = []
    if not rule:
        return ["в контракте нет ue_import.clip_import"]
    pol = rule.get("by_root_policy", {}).get(root_policy)
    if pol is None:
        return ["нет правила для root policy %s" % root_policy]
    for key in ("force_root_lock", "enable_root_motion"):
        if key not in settings:
            problems.append("%s не измерено" % key)
        elif bool(settings[key]) != bool(pol[key]):
            problems.append("%s=%s, ожидается %s" % (key, settings[key], pol[key]))
    want_factory = rule.get("factory")
    if want_factory and settings.get("factory") != want_factory:
        problems.append("factory=%s, ожидается %s" % (settings.get("factory"), want_factory))
    return problems


def _ancestors(parents, name):
    seen = []
    cur = parents.get(name)
    while cur is not None:
        seen.append(cur)
        cur = parents.get(cur)
    return seen


def ik_chain_problems(skel):
    """Самосогласованность ik_chains: кости есть в скелете, start — сам end или его предок, цели — концы цепочек."""
    ik = skel.get("ik_chains")
    if not ik:
        return ["нет ik_chains"]
    parents = {b["name"]: b["parent"] for b in skel["bones"]}
    problems = []
    if ik.get("retarget_root") not in parents:
        problems.append("retarget_root %s не кость скелета" % ik.get("retarget_root"))
    names = set()
    for ch in ik.get("chains", []):
        nm = ch.get("name")
        if nm in names:
            problems.append("повтор имени цепочки %s" % nm)
        names.add(nm)
        s, e = ch.get("start"), ch.get("end")
        for b in (s, e):
            if b not in parents:
                problems.append("%s: кость %s не в скелете" % (nm, b))
        if s in parents and e in parents and s != e and s not in _ancestors(parents, e):
            problems.append("%s: %s не предок %s" % (nm, s, e))
        goal = ch.get("goal")
        if goal is not None and goal != e:
            problems.append("%s: цель %s не конец цепочки %s" % (nm, goal, e))
    return problems
