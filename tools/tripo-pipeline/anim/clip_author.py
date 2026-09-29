"""Авторинг клипов H2Anim (волна 5c): шаблон дельт + авторский слой + IK стоп -> FBX UM_FBX_v1. Только headless.

ТОЛЬКО headless (`blender -b`): вызывается read_factory_settings (в живом Blender выгружает аддон MCP
:9876/:9877). Без `-b` скрипт бросает RuntimeError и ничего не делает.

  "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup \
      --python tools/tripo-pipeline/anim/clip_author.py -- <spec.json> [--clips=Idle,LungeAttack] [--check-only]

Спека героя (art/pipeline-candidates/<ASSET>/build-profiles/<hero>-h2anim.json, схема unmatched.h2anim-spec/1):
цель (SK_*_H2.fbx + подставка, sha256 зафиксирован), кости оружия и мешей, клипы: число интервалов N (кадры 0..N,
24 fps), роль (idle/oneshot/terminal), шаблон (черновик AM_Medusa_* — только дельты и тайминг), ключи авторского
слоя, волны, сдвиг hips, IK стоп и (опционально) вторая кисть на оружии. --check-only: только сверить sha цели.

Метод (план волны 5c, anim-v2-plan.json):
  * поза задаётся ДЕЛЬТАМИ поворота в осях арматуры цели (лицо +X, +Y — левая сторона, Z вверх): кость b
    поворачивается вокруг своей головы на D_b относительно уже повёрнутого родителя. В мире арматуры
    W_b = W_parent · D_b; ключ pose-кости = Rr_b⁻¹ · D_b · Rr_b (Rr_b — поворот rest-кости в арматуре), т. е.
    результат не зависит от roll и осей костей героя и заново запекается на любом rest (H3 Harpy, H2LD);
  * шаблон черновика: W = R_pose · R_rest⁻¹ по кадрам, D = W_parent⁻¹ · W, сопряжение Rz(+90°) из кадра
    прод-Medusa (лицо −Y) в кадр v2 (+X), при mirror — отражение XZ (x,y,z,w) -> (−x,y,−z,w) и обмен L/R;
    время нормируется на длину клипа цели; итог D = D_автор · D_шаблон;
  * IK стоп: аналитическая двухзвенная IK (leg_upper, leg_lower) к rest-позиции головы foot (цель стоит на
    месте), плоскость колена = rest-полюс (не поворачивается с тазом); поворот foot в мире = rest (подошва
    на месте). Вес IK по кадрам (ik_feet.weight) смешивает IK с FK (падение в DeathSettle);
  * hand_follow: двухзвенная IK руки к точке хвата на кости оружия другой руки (двуручный хват, grip_bone)
    или, без grip_bone, «hand_pin»: кисть держит rest-позицию + hand_offset и rest-поворот · hand_world (посох-опора
    Merlin стоит на подставке, пока корпус дышит и оседает); mode "weapon_tip": острие оружия (вершина меша
    оружия, самая дальняя вдоль оси кости оружия) ставится в tip_target (оси арматуры, см; опора на меч о верх
    подставки), поворот кисти и оружия — из FK; mode "anchor": кисть у точки anchor_offset кости anchor_bone
    (натяжение тетивы к щеке); вес по кадрам (weight);
  * кадр 0 = rest (все роли), последний = rest у idle/oneshot (ключи-нули добавляются автоматически);
    объект арматуры и pose-кость root не ключуются (in place);
  * экспорт: сцена импортированного SK_*_H2.fbx уже в кадре UM_FBX_v1 (лицо +X, числа в см), поэтому
    поворот +90° повторно НЕ применяется; объекту арматуры возвращается масштаб 1 (импорт даёт 0,01), экспорт
    пресетом UM_FBX_v1 (FBX_SCALE_UNITS, оси −Y/Z, bake_anim, без leaf-костей), UnitScaleFactor := 1.0,
    make_fbx_deterministic. После экспорта клип импортируется обратно и rest сверяется с SK покостно (≤1e-4 см
    в матрицах арматуры); ключи — с посчитанной позой (≤1e-3).
Отчёты: <run>/reports/author-<Clip>.json и author-summary.json. Статус максимум «технически импортировано».
"""
import hashlib
import json
import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

if not bpy.app.background:
    raise RuntimeError("clip_author.py: только headless (blender -b)")

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools/tripo-pipeline/blender"))
import clip_curves as cc  # noqa: E402
from candidate_build.core import make_fbx_deterministic, patch_fbx_units  # noqa: E402

SPEC_SCHEMA = "unmatched.h2anim-spec/1"
REPORT_SCHEMA = "unmatched.h2anim-author/1"
PRESET = REPO / "blender/_tools/presets/UM_FBX_v1.json"
ROLES = ("idle", "oneshot", "terminal")
LEGS = (("leg_upper.L", "leg_lower.L", "foot.L"), ("leg_upper.R", "leg_lower.R", "foot.R"))
ARMS = {"L": ("arm_upper.L", "arm_lower.L", "hand.L"), "R": ("arm_upper.R", "arm_lower.R", "hand.R")}
RZ90 = Matrix.Rotation(math.radians(90.0), 3, "Z")
MIRROR = Matrix.Diagonal((1.0, -1.0, 1.0))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path):
    p = Path(path).resolve()
    try:
        return p.relative_to(REPO).as_posix()
    except ValueError:
        return p.as_posix()


def r(v, nd=5):
    return round(float(v), nd)


def rv(v, nd=5):
    return [round(float(x), nd) for x in v]


def swap_lr(name):
    if name.endswith(".L"):
        return name[:-2] + ".R"
    if name.endswith(".R"):
        return name[:-2] + ".L"
    return name


# ------------------------------------------------------------------------------------------------ сцена
def import_fbx(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(path), use_anim=True)
    arms = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
    if len(arms) != 1:
        raise RuntimeError("%s: expected one armature, found %d" % (path, len(arms)))
    return arms[0]


def order(arm):
    """Кости в порядке родитель -> потомок."""
    out = []

    def walk(b):
        out.append(b.name)
        for c in b.children:
            walk(c)
    for b in arm.data.bones:
        if b.parent is None:
            walk(b)
    return out


def rest_frames(arm):
    """{кость: (Rr 3x3, head Vector)} в пространстве арматуры."""
    return {b.name: (b.matrix_local.to_3x3().normalized(), b.matrix_local.translation.copy()) for b in arm.data.bones}


# ------------------------------------------------------------------------------------------------ шаблон
def template_deltas(tpl, bones_needed):
    """Дельты черновика по кадрам: {кость: [Quaternion D_b в кадре v2]}, число кадров, (f0, f1).
    Черновик прод-Medusa: лицо −Y, без поворота UM_FBX_v1; сопряжение Rz(+90°) переводит дельты в кадр +X."""
    arm = import_fbx(REPO / tpl["file"])
    sc = bpy.context.scene
    act = arm.animation_data.action if arm.animation_data else None
    if act is None:
        raise RuntimeError("template %s has no action" % tpl["file"])
    f0, f1 = [int(round(x)) for x in act.frame_range]
    rest = rest_frames(arm)
    names = order(arm)
    parent = {b.name: (b.parent.name if b.parent else None) for b in arm.data.bones}
    out = {n: [] for n in bones_needed}
    for fr in range(f0, f1 + 1):
        sc.frame_set(fr)
        W = {}
        for n in names:
            pm = arm.pose.bones[n].matrix.to_3x3().normalized()
            W[n] = pm @ rest[n][0].inverted()
        for n in bones_needed:
            src = n if n in W else ("weapon" if n.startswith("weapon") and "weapon" in W else None)
            if src is None:
                out[n].append(Quaternion())
                continue
            p = parent[src]
            D = (W[p].inverted() @ W[src]) if p else W[src]
            D = RZ90 @ D @ RZ90.inverted()
            out[n].append(D.to_quaternion())
    return out, (f0, f1)


def template_sampler(tpl, frames):
    """(кадр цели -> {кость цели: Quaternion}). mirror: отражение XZ и обмен L/R (лук слева -> меч справа)."""
    src_bones = tpl["bones"]
    mirror = bool(tpl.get("mirror", False))
    need = sorted({swap_lr(b) if mirror else b for b in src_bones})
    data, (f0, f1) = template_deltas(tpl, need)
    weight = float(tpl.get("weight", 1.0))
    per_bone = {b: float(w) for b, w in (tpl.get("bone_weights") or {}).items()}
    n_src = f1 - f0

    def sample(frame):
        t = frame / float(frames) * n_src
        i = min(int(math.floor(t)), n_src - 1) if n_src > 0 else 0
        a = t - i
        res = {}
        for sb in need:
            seq = data[sb]
            q = seq[i].slerp(seq[min(i + 1, len(seq) - 1)], a) if n_src > 0 else seq[0]
            if mirror:
                q = Quaternion((q.w, -q.x, q.y, -q.z))
            tb = swap_lr(sb) if mirror else sb
            w = weight * per_bone.get(tb, 1.0)
            res[tb] = Quaternion().slerp(q, w)
        return res
    return sample, {"file": tpl["file"], "sha256": sha256(REPO / tpl["file"]), "frames": [f0, f1],
                    "bones": need, "mirror": mirror, "weight": weight, "bone_weights": per_bone}


# ------------------------------------------------------------------------------------------------ IK
def rot_between_frames(d0, n0, d1, n1):
    """Поворот, переводящий ортонормированный базис (d0, n0) в (d1, n1)."""
    b0 = Matrix((d0, n0, d0.cross(n0))).transposed()
    b1 = Matrix((d1, n1, d1.cross(n1))).transposed()
    return b1 @ b0.transposed()


def two_bone(hip, target, l1, l2, pole_dir):
    """Колено двухзвенной цепи: (knee, reached). pole_dir — направление полюса (не обязательно ⟂)."""
    d_vec = target - hip
    d = d_vec.length
    reach = d
    d = min(max(d, abs(l1 - l2) + 1e-6), l1 + l2 - 1e-6)
    u = d_vec.normalized()
    v = pole_dir - u * pole_dir.dot(u)
    if v.length < 1e-9:
        v = u.orthogonal()
    v.normalize()
    a = (l1 * l1 - l2 * l2 + d * d) / (2 * d)
    h = math.sqrt(max(l1 * l1 - a * a, 0.0))
    return hip + u * a + v * h, abs(reach - d) < 1e-4


class Chain:
    """Двухзвенная цепь (upper, lower, end) в rest: длины, полюс, базисы костей для поворота."""

    def __init__(self, rest, upper, lower, end, default_pole=(1.0, 0.0, 0.0)):
        self.upper, self.lower, self.end = upper, lower, end
        self.h0 = rest[upper][1]
        self.k0 = rest[lower][1]
        self.a0 = rest[end][1]
        self.l1 = (self.k0 - self.h0).length
        self.l2 = (self.a0 - self.k0).length
        line = (self.a0 - self.h0).normalized()
        off = self.k0 - self.h0
        self.pole0 = (off - line * off.dot(line))
        # Полюс: в rest — фактическое смещение колена/локтя от линии (кадр 0 воспроизводит rest точно), при сжатии
        # цепи на 3 % длины — плавно к default_pole (вперёд для ног, назад для рук), ⟂ линии. Колено почти прямой
        # ноги (Medusa: 0,1 мм позади линии, Merlin R: 2,8 мм вбок-назад) иначе гнулось бы назад.
        fwd = Vector(default_pole)
        self.pole_default = (fwd - line * fwd.dot(line)).normalized()
        self.d_rest = (self.a0 - self.h0).length
        if self.pole0.length < 1e-6:
            self.pole0 = self.pole_default.copy()
        self.pole0.normalize()
        self.pole_from_rest = self.pole0.dot(self.pole_default) > 0.0
        self.n0 = (self.k0 - self.h0).normalized().cross(self.pole0).normalized()

    def pole_at(self, hip, target, W=None):
        """Полюс для текущей длины цепи в осях арматуры (W — поворот родителя цепи или None)."""
        t = min(max((self.d_rest - (target - hip).length) / (0.03 * (self.l1 + self.l2)), 0.0), 1.0)
        t = t * t * (3 - 2 * t)
        p = self.pole0.lerp(self.pole_default, t)
        if p.length < 1e-6:
            p = self.pole_default
        p = p.normalized()
        return (W @ p) if W is not None else p

    def solve(self, hip, target, pole):
        knee, reached = two_bone(hip, target, self.l1, self.l2, pole)
        d_up = (knee - hip).normalized()
        n = d_up.cross(pole - d_up * pole.dot(d_up)).normalized()
        d0_up = (self.k0 - self.h0).normalized()
        w_up = rot_between_frames(d0_up, self.n0, d_up, n)
        d0_lo = (self.a0 - self.k0).normalized()
        n0_lo = d0_lo.cross(self.pole0 - d0_lo * self.pole0.dot(d0_lo))
        n0_lo = n0_lo.normalized() if n0_lo.length > 1e-9 else self.n0
        if n0_lo.dot(self.n0) < 0.0:
            n0_lo = -n0_lo
        d_lo = (target - knee).normalized() if reached else (w_up @ d0_lo)
        n_lo = d_lo.cross(pole - d_lo * pole.dot(d_lo))
        n_lo = n_lo.normalized() if n_lo.length > 1e-9 else n
        if n_lo.dot(n) < 0.0:
            # ось сгиба звена 2 — та же, что у звена 1: полюс с большой составляющей вдоль линии плечо–цель
            # (лучник: локоть назад, цель — щека впереди) иначе переворачивает нормаль и крутит предплечье на 180°
            n_lo = -n_lo
        w_lo = rot_between_frames(d0_lo, n0_lo, d_lo, n_lo)
        return w_up, w_lo, knee, reached


# ------------------------------------------------------------------------------------------------ поза
class Poser:
    def __init__(self, arm, spec):
        self.arm = arm
        self.rest = rest_frames(arm)
        self.names = order(arm)
        self.parent = {b.name: (b.parent.name if b.parent else None) for b in arm.data.bones}
        self.legs = [Chain(self.rest, *leg) for leg in LEGS if all(b in self.rest for b in leg)]
        self.arms = {s: Chain(self.rest, *c, default_pole=(-1.0, 0.0, 0.0)) for s, c in ARMS.items()
                     if all(b in self.rest for b in c)}
        self.tip_rest = None  # острие оружия в rest (оси арматуры, см): задаётся author_clip по мешу оружия

    def fk(self, D, hips_off):
        """W (мировые дельты) и позиции голов по дельтам D."""
        W, head = {}, {}
        for n in self.names:
            p = self.parent[n]
            d = D.get(n, Matrix.Identity(3))
            if p is None:
                W[n] = d
                head[n] = self.rest[n][1].copy()
            else:
                W[n] = W[p] @ d
                head[n] = head[p] + W[p] @ (self.rest[n][1] - self.rest[p][1])
            if n == "hips":
                head[n] = head[n] + hips_off
        return W, head

    def pose(self, D, hips_off, ik_w, feet_target_off, foot_world, follow):
        """Итоговые локальные дельты после IK. Возвращает (D, W, head, ik_info)."""
        W, head = self.fk(D, hips_off)
        info = {}
        if any(w > 0.0 for w in ik_w.values()):
            for ch in self.legs:
                side = ch.upper[-1]
                w_side = ik_w.get(side, 0.0)
                if w_side <= 0.0:
                    continue
                hip = head[ch.upper]
                target = ch.a0 + feet_target_off.get(side, Vector())
                # колено смотрит по rest-полюсу: стопы стоят, поэтому плоскость ноги не крутится вслед за тазом
                # (иначе голень проворачивается относительно стопы и смешанные вершины щиколотки уходят вниз)
                pole = ch.pole_at(hip, target)
                w_up, w_lo, knee, reached = ch.solve(hip, target, pole)
                wf = foot_world.get(side, Matrix.Identity(3))
                wp = W[self.parent[ch.upper]]
                d_up_ik = wp.inverted() @ w_up
                d_lo_ik = w_up.inverted() @ w_lo
                d_ft_ik = w_lo.inverted() @ wf
                for bone, dik in ((ch.upper, d_up_ik), (ch.lower, d_lo_ik), (ch.end, d_ft_ik)):
                    dfk = D.get(bone, Matrix.Identity(3)).to_quaternion()
                    D[bone] = dfk.slerp(dik.to_quaternion(), w_side).to_matrix() if w_side < 1.0 else dik
                info[side] = {"reached": reached}
            W, head = self.fk(D, hips_off)
        for follow in (follow or []):
            if follow["weight"] <= 0.0:
                continue
            ch = self.arms[follow["side"]]
            grip_bone = follow.get("grip_bone")
            mode = follow.get("mode")
            extra = {}
            wpp = W[self.parent[ch.upper]]
            sh = head[ch.upper]

            def pole_for(target, ch=ch, sh=sh, wpp=wpp, follow=follow):
                # полюс локтя: явный (оси арматуры, "pole") или rest/по умолчанию (назад в осях родителя)
                if follow.get("pole") is not None:
                    return follow["pole"]
                return ch.pole_at(sh, target, wpp)
            if grip_bone:
                # точка хвата и поворот кисти заданы в rest относительно кости оружия другой руки
                g_rest = self.rest[grip_bone][1]
                target = head[grip_bone] + W[grip_bone] @ (ch.a0 - g_rest)
                wh = W[grip_bone]  # кисть повторяет поворот оружия (хват не проворачивается)
            elif mode == "weapon_tip":
                # острие оружия этой руки упирается в точку tip_target (оси арматуры, см): поворот оружия в мире —
                # из FK (ключи/aim), позиция кисти выводится из точки острия, рука доводится IK
                wb, hb = follow["weapon_bone"], ch.end
                if self.tip_rest is None:
                    raise RuntimeError("hand_follow weapon_tip: spec has no weapon mesh (meshes.weapon)")
                w0, h0 = self.rest[wb][1], self.rest[hb][1]
                ww = W[wb]  # направление оружия в мире — из FK (aim), сохраняется
                wh = W[hb]
                tip_t = follow["tip_target"] + follow.get("offset", Vector())
                target = tip_t - ww @ (self.tip_rest - w0) - wh @ (w0 - h0)
                if (follow.get("hand_rot") or "forearm") == "forearm":
                    # кисть продолжает IK-предплечье (как в rest: D кисти = 1), оружие поворачивается в кулаке
                    # (D оружия = кисть^-1 * ww): без излома запястья, который рвёт скин у кисти/локтя
                    for _it in range(6):
                        _u, w_lo_i, _e, _ok = ch.solve(sh, target, pole_for(target))
                        wh = w_lo_i
                        target = tip_t - ww @ (self.tip_rest - w0) - wh @ (w0 - h0)
                    extra[wb] = wh.inverted() @ ww
            elif mode == "anchor":
                # кисть у точки anchor_offset кости anchor_bone: offset_space "bone" (по умолчанию) — смещение в
                # осях rest-арматуры, поворачивается вместе с костью (тетива к щеке); "world" — смещение в осях
                # арматуры без поворота (лук вперёд к цели от плеча)
                ab = follow["anchor_bone"]
                off = follow["anchor_offset"]
                off_w = off if follow.get("offset_space") == "world" else W[ab] @ off
                target = head[ab] + off_w + follow.get("offset", Vector())
                wh = W[ch.end]
            else:
                # hand_pin: кисть держит rest-позицию (+ смещение hand_offset) и rest-поворот — посох-опора
                # остаётся на подставке, пока корпус движется
                target = ch.a0 + follow.get("offset", Vector())
                wh = follow.get("rot", Matrix.Identity(3))
            w_up, w_lo, _elbow, reached = ch.solve(sh, target, pole_for(target))
            if mode != "weapon_tip" and follow.get("hand_rot") == "forearm":
                wh = w_lo  # кисть без излома запястья относительно IK-предплечья
            keep = follow.get("keep_weapon_world")
            if keep and keep not in extra:
                # оружие кисти сохраняет FK-поворот в мире (aim), поворачиваясь в кулаке
                extra[keep] = wh.inverted() @ W[keep]
            wt = follow["weight"]
            for bone, dik in ((ch.upper, wpp.inverted() @ w_up), (ch.lower, w_up.inverted() @ w_lo),
                              (ch.end, w_lo.inverted() @ wh)):
                dfk = D.get(bone, Matrix.Identity(3)).to_quaternion()
                D[bone] = dfk.slerp(dik.to_quaternion(), wt).to_matrix()
            for bone, dik in extra.items():
                dfk = D.get(bone, Matrix.Identity(3)).to_quaternion()
                D[bone] = dfk.slerp(dik.to_quaternion(), wt).to_matrix()
            info["follow_" + follow["side"]] = {"reached": reached,
                                                "reach_deficit_cm": r((target - sh).length - ch.l1 - ch.l2, 3),
                                                "target": target.copy()}
            W, head = self.fk(D, hips_off)
        return D, W, head, info

    def basis(self, n, D, hips_off):
        Rr = self.rest[n][0]
        rot = (Rr.inverted() @ D.get(n, Matrix.Identity(3)) @ Rr).to_quaternion()
        loc = Rr.inverted() @ hips_off if n == "hips" else Vector()
        return rot, loc


def euler_m(xyz):
    return Euler([math.radians(v) for v in xyz], "XYZ").to_matrix()


def q_log(q):
    ang = 2.0 * math.acos(max(-1.0, min(1.0, q.w)))
    if ang < 1e-9:
        return Vector((0.0, 0.0, 0.0))
    axis = Vector((q.x, q.y, q.z)).normalized()
    return axis * (ang / 2.0)


def q_exp(v):
    a = v.length
    if a < 1e-9:
        return Quaternion()
    return Quaternion(v.normalized(), 2.0 * a)


def squad_channel(keys, frame, loop=False, period=None):
    """Кватернионный сплайн (SQUAD, Shoemake) по ключам [(кадр, Quaternion)]: для больших поворотов (вынос лука,
    натяжение), где покомпонентная интерполяция Эйлера уходит в обход. Вне ключей — удержание крайнего."""
    ks = sorted(keys, key=lambda x: x[0])
    if loop:
        ks = [k for k in ks if k[0] < period]
        frame = frame % period
    qs = [ks[0][1].copy()]
    for _f, q in ks[1:]:
        q = q.copy()
        if q.dot(qs[-1]) < 0:
            q.negate()
        qs.append(q)
    fs = [k[0] for k in ks]
    n = len(qs)
    if n == 1:
        return qs[0]

    def inner(i):
        if not loop and (i == 0 or i == n - 1):
            return qs[i]
        qp, qn = qs[i - 1], qs[(i + 1) % n]
        qi_inv = qs[i].inverted()
        return qs[i] @ q_exp(-(q_log(qi_inv @ qn) + q_log(qi_inv @ qp)) / 4.0)
    if not loop and frame <= fs[0]:
        return qs[0]
    if not loop and frame >= fs[-1]:
        return qs[-1]
    segs = [(i, i + 1, fs[i], fs[i + 1]) for i in range(n - 1)]
    if loop:
        segs.append((n - 1, 0, fs[-1], fs[0] + period))
    for i, j, a, b in segs:
        fr = frame if frame >= a else frame + (period or 0)
        if a <= fr <= b:
            t = (fr - a) / float(b - a)
            q1 = qs[j] if qs[j].dot(qs[i]) >= 0 else -qs[j]
            s1 = inner(j)
            if s1.dot(q1) < 0:
                s1 = -s1
            return qs[i].slerp(q1, t).slerp(inner(i).slerp(s1, t), 2 * t * (1 - t))
    return qs[0]


def clip_frames_eval(spec, clip_name, clip, poser, template):
    """Дельты всех кадров клипа: [(D, hips_off, ik_w, feet_off, foot_world, follow)] и журнал ключей aim."""
    N = int(clip["frames"])
    role = clip["role"]
    loop = role == "idle"
    period = N if loop else None
    chans = cc.channels_from_keys(clip.get("keys") or [])
    hips_ch = cc.with_boundary(_hips_channel(clip), N, role)
    feet_ch = {s: cc.with_boundary(_side_channel(clip, "feet_offset", s), N, role) for s in ("L", "R")}
    footrot_ch = {s: cc.with_boundary(_side_channel(clip, "foot_world", s), N, role) for s in ("L", "R")}
    waves = clip.get("waves") or []
    scale = {b: float(v) for b, v in (spec.get("amplitude_scale") or {}).items()}
    scale.update({b: float(v) for b, v in (clip.get("amplitude_scale") or {}).items()})
    ik = clip.get("ik_feet", {"weight": [[0, 1.0]]})
    follow_cfgs = clip.get("hand_follow", spec.get("hand_follow"))
    if isinstance(follow_cfgs, dict):
        follow_cfgs = [follow_cfgs]
    follow_cfgs = follow_cfgs or []
    # каналы hand_offset / hand_world ключей — по стороне руки каждого hand_follow (кроме двуручного grip_bone)
    hand_chs = {c["side"]: (cc.with_boundary(_side_channel(clip, "hand_offset", c["side"]), N, role),
                            cc.with_boundary(_side_channel(clip, "hand_world", c["side"]), N, role))
                for c in follow_cfgs if not c.get("grip_bone")}
    aims = [(int(k["f"]), b, a) for k in clip.get("keys") or [] for b, a in (k.get("aim") or {}).items()]
    for b in list(chans) + [w["bone"] for w in waves] + [a[1] for a in aims]:
        if b not in poser.rest:
            raise RuntimeError("%s: bone %s is not in the target armature" % (clip_name, b))
    for b, _v in scale.items():
        if b not in poser.rest:
            raise RuntimeError("%s: amplitude_scale bone %s is not in the target armature" % (clip_name, b))
    tcache = {}

    def tq_at(f):
        if not template:
            return {}
        if f not in tcache:
            tcache[f] = template(f)
        return tcache[f]

    def wave_e(b, f):
        e = [0.0, 0.0, 0.0]
        for w in waves:
            if w["bone"] == b:
                e["xyz".index(w["axis"])] += cc.wave(f, N, float(w["amp"]), int(w.get("cycles", 1)),
                                                     float(w.get("phase", 0.0)), w.get("shape", "sin"))
        return e

    def chan_e(b, f, bounded):
        if b not in bounded:
            return [0.0, 0.0, 0.0]
        return [cc.eval_channel(bounded[b][a], f, loop, period) for a in range(3)]

    quat_bones = set(clip.get("quat_bones") or []) | {a[1] for a in aims}

    def deltas(f, bounded):
        D = {}
        tq = tq_at(f)
        for b in poser.names:
            if b in quat_bones and b in bounded:
                ax = bounded[b]
                frames_b = sorted({ff for ff, _v in ax[0]})
                vals = {a_i: dict(ax[a_i]) for a_i in range(3)}
                keys_q = [(ff, euler_m([vals[0][ff], vals[1][ff], vals[2][ff]]).to_quaternion()) for ff in frames_b]
                m = squad_channel(keys_q, f, loop, period).to_matrix()
                if b in tq:
                    m = m @ tq[b].to_matrix()
                D[b] = m
                continue
            sc_b = scale.get(b, 1.0)
            ce = chan_e(b, f, bounded)
            we = wave_e(b, f)
            e = [c * sc_b + w for c, w in zip(ce, we)]
            m = euler_m(e)
            if b in tq:
                m = m @ tq[b].to_matrix()
            if any(abs(v) > 1e-9 for v in e) or b in tq:
                D[b] = m
        return D

    # ключи aim: направление (и, если задано, второй вектор) кости в осях арматуры в кадре ключа ->
    # эквивалентный ключ Эйлера канала (родители раньше детей, чтобы W родителя уже учитывал его aim)
    rank = {n: i for i, n in enumerate(poser.names)}
    aim_log = []
    for f, b, a in sorted(aims, key=lambda x: (rank[x[1]], x[0])):
        bounded = {k: cc.with_boundary(ax, N, role) for k, ax in chans.items()}
        W, _head = poser.fk(deltas(f, bounded), Vector())
        p = poser.parent[b]
        Wp = W[p] if p else Matrix.Identity(3)
        Rr = poser.rest[b][0]
        v_from = Vector(a["from"]) if a.get("from") else (Rr @ Vector((0.0, 1.0, 0.0)))
        v_from.normalize()
        v_to = Vector(a["to"]).normalized()
        if a.get("from2") and a.get("to2"):
            f2 = Vector(a["from2"])
            t2 = Vector(a["to2"])
            n_from = (f2 - v_from * f2.dot(v_from)).normalized()
            n_to = (t2 - v_to * t2.dot(v_to)).normalized()
            Wb = rot_between_frames(v_from, n_from, v_to, n_to)
        else:
            cur = Wp @ v_from
            Wb = cur.rotation_difference(v_to).to_matrix() @ Wp
        if a.get("twist"):
            Wb = Matrix.Rotation(math.radians(float(a["twist"])), 3, v_to) @ Wb
        Db = Wp.inverted() @ Wb
        tq = tq_at(f)
        if b in tq:
            Db = Db @ tq[b].to_matrix().inverted()
        prev = chan_e(b, f, bounded)
        e = [math.degrees(x) for x in Db.to_euler("XYZ", Euler([math.radians(v) for v in prev], "XYZ"))]
        we = wave_e(b, f)
        sc_b = scale.get(b, 1.0) or 1.0
        val = [(ei - wi) / sc_b for ei, wi in zip(e, we)]
        ch = chans.setdefault(b, [[], [], []])
        for ax in range(3):
            ch[ax] = [(ff, vv) for ff, vv in ch[ax] if ff != f] + [(f, val[ax])]
        aim_log.append({"f": f, "bone": b, "euler_deg": [round(v, 3) for v in val], "to": list(a["to"])})
    bounded = {k: cc.with_boundary(ax, N, role) for k, ax in chans.items()}
    for b in quat_bones:
        if any(w["bone"] == b for w in waves) or scale.get(b, 1.0) != 1.0:
            raise RuntimeError("%s: bone %s is quaternion-interpolated (aim/quat_bones): no waves or amplitude_scale"
                               % (clip_name, b))
        axes = bounded.get(b)
        if axes and not (set(f for f, _ in axes[0]) == set(f for f, _ in axes[1]) == set(f for f, _ in axes[2])):
            raise RuntimeError("%s: bone %s: quaternion keys need all three axes at every key" % (clip_name, b))
    out = []
    for f in range(N + 1):
        D = deltas(f, bounded)
        hips_off = Vector([cc.eval_channel(hips_ch[a], f, loop, period) for a in range(3)])
        feet_off = {s: Vector([cc.eval_channel(feet_ch[s][a], f, loop, period) for a in range(3)])
                    for s in ("L", "R")}
        foot_world = {s: euler_m([cc.eval_channel(footrot_ch[s][a], f, loop, period) for a in range(3)])
                      for s in ("L", "R")}
        ik_w = {s: (cc.weight_curve(ik.get("weight_" + s, ik.get("weight")), f) if ik.get("enabled", True) else 0.0)
                for s in ("L", "R")}
        follow = []
        for fcfg in follow_cfgs:
            fo = {"side": fcfg["side"], "grip_bone": fcfg.get("grip_bone"),
                  "weight": cc.weight_curve(fcfg.get("weight"), f), "mode": fcfg.get("mode"),
                  "hand_rot": fcfg.get("hand_rot"), "keep_weapon_world": fcfg.get("keep_weapon_world"),
                  "pole": Vector(fcfg["pole"]).normalized() if fcfg.get("pole") else None}
            if fo["mode"] == "weapon_tip":
                fo["weapon_bone"] = fcfg.get("weapon_bone") or spec["weapon"]["bone"]
                fo["tip_target"] = Vector(fcfg["tip_target"])
            elif fo["mode"] == "anchor":
                fo["anchor_bone"] = fcfg["anchor_bone"]
                fo["anchor_offset"] = Vector(fcfg["anchor_offset"])
                fo["offset_space"] = fcfg.get("offset_space", "bone")
            elif fo["mode"] not in (None, "hand_pin"):
                raise RuntimeError("%s: hand_follow.mode must be hand_pin, weapon_tip or anchor" % clip_name)
            if not fcfg.get("grip_bone"):
                och, rch = hand_chs[fcfg["side"]]
                fo["offset"] = Vector([cc.eval_channel(och[a], f, loop, period) for a in range(3)])
                fo["rot"] = euler_m([cc.eval_channel(rch[a], f, loop, period) for a in range(3)])
            follow.append(fo)
        out.append((D, hips_off, ik_w, feet_off, foot_world, follow))
    return out, aim_log


def _hips_channel(clip):
    axes = [[], [], []]
    for k in clip.get("keys") or []:
        if "hips_loc" in k:
            for a in range(3):
                axes[a].append((int(k["f"]), float(k["hips_loc"][a])))
    return axes


def _side_channel(clip, field, side):
    axes = [[], [], []]
    for k in clip.get("keys") or []:
        v = (k.get(field) or {}).get(side)
        if v is not None:
            for a in range(3):
                axes[a].append((int(k["f"]), float(v[a])))
    return axes


# ------------------------------------------------------------------------------------------------ экспорт
def export_clip(arm, meshes, path, preset):
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    for o in [arm] + meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = arm
    restore = make_fbx_deterministic()
    try:
        bpy.ops.export_scene.fbx(
            filepath=str(path), use_selection=True, object_types={"ARMATURE", "MESH"},
            apply_unit_scale=bool(preset["apply_unit_scale"]), apply_scale_options=preset["apply_scale_options"],
            axis_forward=preset["axis_forward"], axis_up=preset["axis_up"],
            use_triangles=bool(preset["use_triangles"]), mesh_smooth_type=preset["mesh_smooth_type"],
            add_leaf_bones=bool(preset["add_leaf_bones"]), primary_bone_axis=preset["primary_bone_axis"],
            secondary_bone_axis=preset["secondary_bone_axis"], bake_anim=True,
            bake_anim_use_all_bones=bool(preset["bake_anim_use_all_bones"]),
            bake_anim_use_nla_strips=bool(preset["bake_anim_use_nla_strips"]),
            bake_anim_use_all_actions=bool(preset["bake_anim_use_all_actions"]),
            bake_anim_force_startend_keying=bool(preset["bake_anim_force_startend_keying"]),
            bake_anim_step=1.0, bake_anim_simplify_factor=0.0,
            use_custom_props=False, path_mode="STRIP", embed_textures=False)
    finally:
        restore()
    patch_fbx_units(path, float(preset["patch_fbx_unit_scale_to"]))


def readback(path, sk_rest, expected):
    """Импорт клипа обратно: rest против SK (матрицы арматуры, см) и ключи против посчитанных поз."""
    arm = import_fbx(path)
    sc = bpy.context.scene
    rest = {b.name: b.matrix_local.copy() for b in arm.data.bones}
    rest_diff = max(max(abs(a - b) for ra, rb in zip(rest[n], sk_rest[n]) for a, b in zip(ra, rb)) for n in sk_rest)
    missing = sorted(set(sk_rest) - set(rest))
    act = arm.animation_data.action if arm.animation_data else None
    f0, f1 = [int(round(x)) for x in act.frame_range] if act else (0, -1)
    pose_diff = 0.0
    for fr, heads in expected.items():
        sc.frame_set(f0 + fr)
        for n, h in heads.items():
            pose_diff = max(pose_diff, (arm.pose.bones[n].head - h).length)
    return {"rest_max_abs_diff_cm": r(rest_diff, 8), "rest_ok": rest_diff <= 1e-4 and not missing,
            "missing_bones": missing, "frame_range": [f0, f1], "fps": sc.render.fps,
            "pose_heads_max_diff_cm": r(pose_diff, 6), "pose_ok": pose_diff <= 1e-3,
            "armature_object": arm.name, "armature_scale": rv(arm.scale, 6)}


# ------------------------------------------------------------------------------------------------ main
def author_clip(spec, clip_name, preset, run_dir):
    clip = spec["clips"][clip_name]
    role = clip["role"]
    if role not in ROLES:
        raise RuntimeError("%s: role must be one of %s" % (clip_name, ROLES))
    N = int(clip["frames"])
    template, tinfo = None, None
    if clip.get("template"):
        template, tinfo = template_sampler(clip["template"], N)
    target = REPO / spec["target"]["sk_fbx"]
    arm = import_fbx(target)
    if arm.name != "SKEL_UM_Humanoid":
        raise RuntimeError("target armature object must be SKEL_UM_Humanoid, got %s" % arm.name)
    sc = bpy.context.scene
    sc.render.fps, sc.render.fps_base = int(spec.get("fps", 24)), 1.0
    sc.frame_start, sc.frame_end = 0, N
    fps = sc.render.fps
    sk_rest = {b.name: b.matrix_local.copy() for b in arm.data.bones}
    # импорт FBX см -> объект арматуры 0,01; экспорт UM_FBX_v1 ждёт масштаб 1 и числа в см (как у бейка)
    arm.scale = (1.0, 1.0, 1.0)
    bpy.context.view_layer.update()
    meshes = [o for o in sc.objects if o.type == "MESH"]
    poser = Poser(arm, spec)
    tip_info = None
    wname = (spec.get("meshes") or {}).get("weapon")
    if wname and wname in sc.objects and (spec.get("weapon") or {}).get("bone") in poser.rest:
        # острие = вершина меша оружия, самая дальняя вдоль оси кости оружия от её головы (как clip_contact_check)
        wobj = sc.objects[wname]
        to_arm = arm.matrix_world.inverted() @ wobj.matrix_world
        wb = arm.data.bones[spec["weapon"]["bone"]]
        ax = (wb.tail_local - wb.head_local).normalized()
        poser.tip_rest = max((to_arm @ v.co for v in wobj.data.vertices), key=lambda p: (p - wb.head_local).dot(ax))
        tip_info = {"bone": wb.name, "tip_rest_cm": rv(poser.tip_rest, 4)}
    frames, aim_log = clip_frames_eval(spec, clip_name, clip, poser, template)
    act = bpy.data.actions.new("AM_%s_%s" % (spec["ue_hero"], clip_name))
    arm.animation_data_create()
    arm.animation_data.action = act
    pbs = arm.pose.bones
    for pb in pbs:
        pb.rotation_mode = "QUATERNION"
    prev_q = {}
    expected = {}
    ik_log = []
    for f, (D, hips_off, ik_w, feet_off, foot_world, follow) in enumerate(frames):
        D, W, head, info = poser.pose(D, hips_off, ik_w, feet_off, foot_world, follow)
        entry = {"f": f, "ik_weight": {k: r(v, 3) for k, v in ik_w.items()},
                 **{k: v["reached"] for k, v in info.items()}}
        for k, v in info.items():
            if "reach_deficit_cm" in v:
                entry[k + "_reach_deficit_cm"] = v["reach_deficit_cm"]
        if poser.tip_rest is not None:
            wb = spec["weapon"]["bone"]
            entry["weapon_tip_cm"] = rv(head[wb] + W[wb] @ (poser.tip_rest - poser.rest[wb][1]), 3)
        for fo in follow:
            k = "follow_" + fo["side"]
            entry[k + "_weight"] = r(fo["weight"], 3)
            if k in info:
                # кисть против цели IK этого кадра (вес 1 — точность IK, вес < 1 — смешение с FK)
                entry[k + "_hand_to_target_cm"] = r((head[poser.arms[fo["side"]].end] - info[k]["target"]).length, 3)
        ik_log.append(entry)
        for n in poser.names:
            if n == "root":
                continue
            q, loc = poser.basis(n, D, hips_off)
            if n in prev_q:
                q.make_compatible(prev_q[n])
            prev_q[n] = q
            pb = pbs[n]
            pb.rotation_quaternion = q
            pb.location = loc
            pb.keyframe_insert("rotation_quaternion", frame=f)
            if n == "hips":
                pb.keyframe_insert("location", frame=f)
        if f in (0, N // 2, N):
            expected[f] = {n: head[n].copy() for n in poser.names}
    for fc in (act.fcurves if hasattr(act, "fcurves") else []):
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
    fbx = run_dir / "export" / ("AM_%s_%s.fbx" % (spec["ue_hero"], clip_name))
    export_clip(arm, meshes, fbx, preset)
    rb = readback(fbx, sk_rest, expected)
    report = {"schema": REPORT_SCHEMA, "clip": clip_name, "hero": spec["hero"], "character": spec["character"],
              "spec": spec["_path"], "spec_sha256": spec["_sha256"],
              "target": {"sk_fbx": spec["target"]["sk_fbx"], "sha256": sha256(target),
                         "rest_generation": spec["target"].get("rest_generation")},
              "tool": "tools/tripo-pipeline/anim/clip_author.py", "tool_sha256": sha256(__file__),
              "curves_sha256": sha256(HERE / "clip_curves.py"),
              "blender": bpy.app.version_string, "fps": fps, "frames": N + 1, "intervals": N,
              "duration_s": r(N / float(fps), 4), "role": role, "loop": role == "idle",
              "template": tinfo, "reference": clip.get("reference"),
              "ik_feet": clip.get("ik_feet", {"weight": [[0, 1.0]]}),
              "hand_follow": clip.get("hand_follow", spec.get("hand_follow")),
              "ik_unreached_frames": [x["f"] for x in ik_log if any(v is False for k, v in x.items()
                                                                     if k not in ("f", "ik_weight"))],
              "weapon_tip": tip_info,
              "ik_log": ik_log, "aim_keys": aim_log,
              "fbx": {"path": rel(fbx), "sha256": sha256(fbx), "bytes": fbx.stat().st_size},
              "export": {"preset": rel(PRESET), "preset_sha256": sha256(PRESET), "rotation_applied": False,
                         "note": "сцена SK_*_H2.fbx уже в кадре UM_FBX_v1 (+X); масштаб объекта арматуры 1, UnitScaleFactor 1.0"},
              "readback": rb, "passed": rb["rest_ok"] and rb["pose_ok"] and rb["fps"] == 24}
    out = run_dir / "reports" / ("author-%s.json" % clip_name)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("CLIP_AUTHOR", "OK" if report["passed"] else "FAIL", clip_name, rel(fbx), "rest", rb["rest_max_abs_diff_cm"],
          "pose", rb["pose_heads_max_diff_cm"], "unreached", report["ik_unreached_frames"][:6])
    return report


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if not argv:
        print(__doc__)
        os._exit(2)
    spec_path = Path(argv[0]).resolve()
    opts = dict(a[2:].split("=", 1) for a in argv[1:] if a.startswith("--") and "=" in a)
    flags = {a[2:] for a in argv[1:] if a.startswith("--") and "=" not in a}
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if spec.get("schema") != SPEC_SCHEMA:
        raise RuntimeError("spec schema must be %s" % SPEC_SCHEMA)
    spec["_path"], spec["_sha256"] = rel(spec_path), sha256(spec_path)
    target = REPO / spec["target"]["sk_fbx"]
    got = sha256(target)
    pinned = spec["target"].get("sha256")
    if pinned and got != pinned:
        print("CLIP_AUTHOR TARGET_CHANGED", rel(target), "pinned", pinned, "now", got)
        os._exit(3)
    if "check-only" in flags:
        print("CLIP_AUTHOR TARGET_OK", rel(target), got)
        os._exit(0)
    preset = json.loads(PRESET.read_text(encoding="utf-8"))
    run_dir = REPO / spec["run_dir"]
    names = opts["clips"].split(",") if "clips" in opts else list(spec["clips"])
    reports = {}
    for name in names:
        reports[name] = author_clip(spec, name, preset, run_dir)
    summ = run_dir / "reports" / "author-summary.json"
    old = json.loads(summ.read_text(encoding="utf-8")) if summ.exists() else {"clips": {}}
    old["clips"].update({n: {"passed": rep["passed"], "fbx": rep["fbx"], "duration_s": rep["duration_s"],
                             "target_sha256": rep["target"]["sha256"]} for n, rep in reports.items()})
    old.update({"schema": REPORT_SCHEMA + "-summary", "spec": spec["_path"], "spec_sha256": spec["_sha256"]})
    summ.write_text(json.dumps(old, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    sys.stdout.flush()
    os._exit(0 if all(rep["passed"] for rep in reports.values()) else 1)


try:
    main()
except Exception as exc:  # noqa: BLE001 - код 2 = ошибка запуска/спеки
    import traceback
    traceback.print_exc()
    print("CLIP_AUTHOR ERROR", exc)
    sys.stdout.flush()
    os._exit(2)
