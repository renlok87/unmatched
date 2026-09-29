"""QA-010 checklist generator (markdown + json), stdlib only.

Rows come from the normative sources (line numbers as of 2026-09-28):
  10-acceptance-tests.md QA-010 стр. 124-135 (Then 132, states 133, evidence 135)
  03-art-direction.md §3 К-1..К-3 стр. 67-125 (C-9 стр. 28, §6 стр. 186-198)
  17-art-production-spec.md §2.7 (стр. 523-548), AD-AC-27..33, §11.10
  02-ux-ui-spec.md стр. 864 (контраст иконок), стр. 894 (UI-ICON-ACTION 24/32/48)
Automatic rows read result JSON written by qa010.py subcommands, and only
from results measured on the row's config frame (frames.K*.path; see _refs /
_bind): a `k: K1` label alone binds nothing. С-9 on a proxy layer mask never
gets a normative status. Manual rows stay «открыто» until the config records
a reviewer answer. The generator never writes «принято»: acceptance
belongs to the reviewer + independent viewer (QA-010 стр. 129) and, for
GD-058, to the author.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import VERSION
from .layers import proxy_regions, proxy_status, spec_kind

MANUAL_OK = {"да", "yes", "есть", "pass"}
MANUAL_NO = {"нет", "no", "fail"}

ITEMS = [
    # id, frame, text, source, norm_status, kind, auto_type
    ("K1.cells_all", "K1", "Различимы все клетки, включая дальнюю строку",
     "10 QA-010 стр. 132; 17 AD-AC-27", "НОРМАТИВ", "manual+auto", "project"),
    ("K1.multizone", "K1", "Различимы мультизонные клетки",
     "10 QA-010 стр. 132; 17 AD-AC-28, AD-OPEN-21", "НОРМАТИВ (на живой доске мультизон нет — ОТКРЫТО)", "manual", None),
    ("K1.hero_helper", "K1", "Различимы герои и помощники",
     "10 QA-010 стр. 132", "НОРМАТИВ", "manual", None),
    ("K1.teams_gray", "K1", "Своя/чужая команда различимы, кольца С-11 — в т.ч. в градациях серого",
     "10 QA-010 стр. 132; 03 С-11; 17 AD-AC-31", "НОРМАТИВ", "manual+derived", "derive"),
    ("K1.selected", "K1", "Видно, какая фигурка выделена",
     "10 QA-010 стр. 132", "НОРМАТИВ", "manual", None),
    ("K1.zones_deut", "K1", "Зоны различимы не только цветом (цвет+глиф+буква), проверка симуляцией deuteranopia",
     "10 QA-010 стр. 132; 15 ACC-020; 17 AD-AC-29", "НОРМАТИВ (способ кодирования — ПРЕДЛОЖЕНИЕ, AD-CNF-10)",
     "manual+derived", "derive"),
    ("K1.c9", "K1", "Игровой слой ярче декора (С-9); +0.3..+0.7 EV и «насыщеннее» — предложение",
     "10 QA-010 стр. 132; 03 С-9 стр. 28; 17 AD-AC-33, §11.10", "НОРМАТИВ «ярче»; диапазон — ПРЕДЛОЖЕНИЕ", "auto", "c9"),
    ("K2.cobble_borders", "K2", "Различимы булыжник и границы клетки",
     "10 QA-010 стр. 132; 03 стр. 107", "НОРМАТИВ", "manual", None),
    ("K2.face_weapon", "K2", "Различимы лицо и оружие фигурки",
     "10 QA-010 стр. 132; 17 стр. 847", "НОРМАТИВ (модель зума K-2 открыта, AD-OPEN-08; 1,6× — Given QA-010)", "manual", None),
    ("K2.plate", "K2", "Плашка фигурки не перекрывает кликабельные клетки текущего выбора",
     "03 §3 К-2 стр. 107; 17 §2.7", "ПРЕДЛОЖЕНИЕ", "auto", "plate"),
    ("K3.attack_result", "K3", "Различимы атакующий, цель и результат (на фигурке и в HUD)",
     "10 QA-010 стр. 132; 03 стр. 123", "НОРМАТИВ", "manual", None),
    ("K3.icon_sizes", "K3", "Пиктограмма цели читается при 24/32/48 px, контраст с фоном",
     "02 стр. 864, 894; 17 стр. 1200, 1229; GD-058 акт 2026-09-28", "ПРЕДЛОЖЕНИЕ (≥3:1)", "auto", "icon"),
    ("ALL.highlight_shapes", "K1/K3", "Подсветки хода/атаки/выбора различимы формой и иконкой, не только цветом",
     "10 QA-010 стр. 133; 03 §6; 17 AD-AC-32", "НОРМАТИВ", "manual+derived", "derive"),
    ("ALL.derived_evidence", "K1..K3", "Приложены скриншоты в градациях серого и deuteranopia",
     "10 QA-010 стр. 135; 17 стр. 548", "НОРМАТИВ (доказательство)", "auto", "derive"),
    ("ALL.luma_recorded", "K1..K3", "Luma p50/p90 кадров записаны (эталон для Q-303)",
     "17 §11.10; 03 Q-303", "ПРЕДЛОЖЕНИЕ (порога нет)", "auto", "luma"),
    ("ALL.viewer", "K1..K3", "Проверку выполнили проверяющий и независимый зритель (не автор вида)",
     "10 QA-010 стр. 129; stage-3 E5", "НОРМАТИВ", "viewer", None),
    ("ALL.provenance", "K1..K3", "Кадры K1–K3 — packaged-live (редакторные кадры — только диагностика)",
     "stage-3 инвариант (classify_evidence, T0)", "ПРАВИЛО ЭТАПА 3", "provenance", None),
    ("ALL.render_reference", "K1..K3",
     "Кадры K1–K3 сняты на эталоне рендера: DX12/SM6 + Lumen, High (sg.* = 2), SP 100, экспозиция и "
     "единицы света профиля — строка RENDER в SHOT-блоке кадра (qa010 render)",
     "решение пользователя 2026-09-28 (W4-A); docs/art-pipeline/render-reference.json",
     "РЕШЕНИЕ ПОЛЬЗОВАТЕЛЯ", "render", None),
]

DEFAULT_ELEMENTS = [
    ("K1", "facade", "Фасад на дальней стороне, приглушён", "03 §3 стр. 73; 17 §2.7"),
    ("K1", "lantern", "Фонарь (тёплый акцент)", "03 С-6; 17 §2.7"),
    ("K1", "tray_darkness", "Поднос с рваным краем, за ним тьма (С-10)", "03 С-10 стр. 29; 17 AD-AC-35"),
    ("K1", "fog", "Экспоненциальный туман", "03 С-10; 17 §2.7"),
    ("K1", "vignette", "Виньетка", "03 С-10; 17 стр. 515"),
    ("K1", "zone_pictograms", "Пиктограммы зон по краю подноса", "03 §3 стр. 77; 02 UI-ICON-ZONE"),
    ("K1", "hud", "HUD: оппонент сверху, рука снизу", "03 §3 стр. 84; 17 §2.7"),
    ("K1", "shadow_casters_1", "Счётчик источников с тенью = 1", "03 С-8; 09 TASK-043 стр. 410"),
    ("K1", "six_fighters", "6 фигурок (Medusa + 3 гарпии, Arthur + Merlin) или 6 копий принятой Medusa", "14 GD-058; D-03"),
    ("K2", "facade_hidden", "Фасад скрыт/прозрачен при зуме", "03 §4.4; 17 §2.7"),
    ("K2", "plate", "Плашка фигурки: имя, HP, статус", "03 §3 стр. 105; GD-058 акт 2026-09-28"),
    ("K2", "base_profile", "Подставка с номером/профилем команды", "03 стр. 107; 04 §3.8"),
    ("K3", "poses", "Позы LungeAttack / HitReact (D-11); без клипов — «постановка»", "03 §3 К-3; 17 §2.7; stage-3 B6"),
    ("K3", "inspector_2d", "Инспектор карты с 2D-артом (D-09), не прячет цель", "03 стр. 123; 17 §2.7"),
    ("K3", "target_frame_icon", "Рамка-прицел + пиктограмма цели", "03 §6 стр. 193"),
    ("K3", "damage_result", "Число урона на фигурке и итог в HUD", "03 стр. 123; ART-003 акт 2026-09-28"),
]


def provenance_hint(path: Optional[str]) -> str:
    """Path-convention hint only; the authoritative class comes from
    tools/art/classify_evidence.py (stage-3 T0) and should be put in config."""
    if not path:
        return "unknown"
    p = path.replace("\\", "/")
    if re.search(r"(?:^|[-_/.])(?:ue-)?editor(?:[-_/.]|$)", p.lower()) or "-blender-" in p.lower():
        return "editor-or-blender (hint)"
    if re.search(r"/live-[^/]+/(run|combat)-\d{8}-\d{6}/", p) or re.search(r"/(run|combat)-\d{8}-\d{6}/", p):
        return "packaged-live (hint)"
    return "unknown"


def _load(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _norm(p: str) -> str:
    return re.sub(r"^(\./)+", "", str(p).replace("\\", "/").lower())


def _same_file(a: str, b: str) -> bool:
    """Paths may be relative to different roots; evidence basenames repeat,
    so compare the longer normalized path's suffix, not the basename."""
    na, nb = _norm(a), _norm(b)
    return na == nb or na.endswith("/" + nb) or nb.endswith("/" + na)


KEYS = ("K1", "K2", "K3")
MISMATCH = "нет данных: результат по другому кадру"


def _base(p: Optional[str]) -> str:
    return _norm(p or "").rsplit("/", 1)[-1]


def _parent(p: Optional[str]) -> str:
    n = _norm(p or "")
    return n.rsplit("/", 1)[0] if "/" in n else ""


def _short(p: Optional[str], parts: int = 3) -> str:
    n = str(p or "?").replace("\\", "/")
    return "/".join(n.split("/")[-parts:])


def _under_dir(path: str, d: str) -> bool:
    """path lies in directory d (suffix-tolerant like _same_file)."""
    if not d or d == ".":
        return False
    parts = _norm(path).split("/")[:-1]
    return any(_same_file("/".join(parts[:i]), d) for i in range(len(parts), 0, -1))


def _k_keys(label: str) -> list[str]:
    return list(KEYS) if label == "K1..K3" else [k for k in KEYS if k in str(label)]


def _refs(cmd: str, r: dict) -> list[dict]:
    """Frames a result was measured on. ref: {path?, shot?, trace?, matches_shot?}.
    c9/icon/luma/derive carry the frame path; plate/project carry the SHOT
    name + trace and, when run with --frame, the frame path."""
    if cmd in ("c9", "icon"):
        fr = r.get("frame") or {}
        ref = {"path": fr.get("path")}
        t = r.get("trace")
        if isinstance(t, dict) and t.get("shot"):
            ref["shot"] = t["shot"]
            ref["matches_shot"] = t.get("shot_matches_frame", _norm(t["shot"]) == _base(fr.get("path")))
        return [ref]
    if cmd == "luma":
        return [{"path": f.get("path")} for f in r.get("frames", [])]
    if cmd == "derive":
        return [{"path": e.get("input")} for e in r.get("entries", [])]
    fr = r.get("frame") or {}
    shots = r.get("shots") if cmd == "project" else [r]
    out = []
    for sh in shots or []:
        ref = {"shot": sh.get("shot"), "trace": r.get("trace"), "_shot": sh}
        if fr.get("path"):
            ref["path"] = fr["path"]
            ref["matches_shot"] = fr.get("matches_shot", _norm(sh.get("shot") or "") == _base(fr["path"]))
        out.append(ref)
    return out


def _bind(ref: dict, kpath: str) -> tuple[bool, str]:
    """Is the result measured on the config frame kpath? -> (ok, why-not)."""
    if ref.get("path"):
        if not _same_file(ref["path"], kpath):
            return False, f"кадр {_short(ref['path'])} ≠ {_short(kpath)}"
        if ref.get("matches_shot") is False:
            return False, f"SHOT-блок трассы {ref.get('shot')} не от кадра {_base(ref['path'])}"
        return True, ""
    shot, trace = ref.get("shot"), ref.get("trace")
    if shot and trace:
        if _norm(shot) != _base(kpath):
            return False, f"SHOT {shot} ≠ {_short(kpath)}"
        if not _under_dir(kpath, _parent(trace)):
            return False, f"трасса {_short(trace)} не из каталога кадра {_short(kpath)}"
        return True, ""
    return False, "в результате нет пути кадра (нужен --frame)"


def _bound_to(cmd: str, r: dict, frames: dict, keys: list[str]) -> dict:
    """-> {K: [refs bound to frames[K].path]} for the given keys."""
    out: dict = {}
    for k in keys:
        kp = frames.get(k, {}).get("path")
        if kp:
            hits = [ref for ref in _refs(cmd, r) if _bind(ref, kp)[0]]
            if hits:
                out[k] = hits
    return out


def _mismatch_detail(cmd: str, rs: list, kpath: str) -> str:
    parts = []
    for r in rs:
        why = sorted({_bind(ref, kpath)[1] for ref in _refs(cmd, r)}) or ["нет кадров"]
        parts.append(f"{Path(r.get('_path', '?')).name}: {'; '.join(why)}")
    return " | ".join(parts)


def _c9_proxies(r: dict) -> list[dict]:
    """Proxy layer masks of a c9 result (new layer_basis or 1.0.0 fields)."""
    found = []
    lb = r.get("layer_basis")
    if isinstance(lb, dict) and lb.get("proxy"):
        found += lb.get("proxy_regions") or []
    items = []
    for g in r.get("game_region") or []:
        items.append(("game", g.get("spec", ""), g.get("kind") or spec_kind(g.get("spec", "")),
                      bool(g.get("proxy")), g.get("note", "")))
    d = r.get("decor_region") or {}
    dspec = str(d.get("spec", ""))
    kinds = d.get("kinds") or re.findall(r"=\s*([a-z][a-z-]*)(?=:|;|$)", dspec)
    for kd in kinds:
        items.append(("decor", dspec, kd, False, ""))
    found += proxy_regions(items)
    if d.get("proxy") and not any(f["layer"] == "decor" for f in found):
        found.append({"layer": "decor", "spec": dspec, "kind": "", "why": d.get("note") or "decor_region.proxy"})
    uniq = {}
    for f in found:
        uniq.setdefault((f["layer"], f["spec"]), f)
    return list(uniq.values())


def _auto_status(kind: str, frame_key: str, results: dict, frames: dict) -> tuple[str, str]:
    """-> (status, detail). Every automatic value must come from a result
    measured on the config frame of its row (frames.K*.path)."""
    keys = _k_keys(frame_key)
    if kind == "derive":
        man = results.get("derive")
        if not man:
            return "нет данных", "нет манифеста derive"
        inputs = [e["input"] for e in man.get("entries", [])]
        missing = [k for k in keys if frames.get(k, {}).get("path")
                   and not any(_same_file(frames[k]["path"], i) for i in inputs)]
        absent = [k for k in keys if not frames.get(k, {}).get("path")]
        if missing or absent:
            return "измерено: неполно", f"нет производных для {', '.join(missing + absent)}"
        return "измерено: есть", f"серый + deuteranopia для {', '.join(keys)}"
    if kind == "luma":
        found, extra = {}, []
        for x in results.get("luma", []):
            for fr in x.get("frames", []):
                ks = [k for k in keys if frames.get(k, {}).get("path") and _same_file(frames[k]["path"], fr["path"])]
                if ks:
                    found[ks[0]] = fr
                else:
                    extra.append(_short(fr.get("path")))
        if not found:
            if extra:
                return MISMATCH, "кадры luma не совпадают с K1–K3 конфига: " + ", ".join(extra)
            return "нет данных", "нет результата luma"
        parts = [f"{k}: p50 {found[k].get('stats', {}).get('luma_p50')} / p90 {found[k].get('stats', {}).get('luma_p90')}"
                 for k in keys if k in found]
        missing = [k for k in keys if k not in found]
        if missing:
            parts.append("нет для " + ", ".join(missing))
        if extra:
            parts.append("вне K1–K3 (не учтены): " + ", ".join(extra))
        return ("измерено" if not missing else "измерено: неполно"), "; ".join(parts)
    candidates = [r for r in results.get(kind, []) if r.get("_k") in (frame_key, "K1..K3")]
    if not candidates:
        return "нет данных", f"нет результата {kind}"
    kpath = frames.get(frame_key, {}).get("path")
    if not kpath:
        return "нет данных: в конфиге нет кадра", f"frames.{frame_key}.path не задан — результат {kind} не к чему привязать"
    if kind == "project":
        shots = [ref["_shot"] for r in candidates for ref in _refs(kind, r) if _bind(ref, kpath)[0]]
        if not shots:
            return MISMATCH, _mismatch_detail(kind, candidates, kpath)
        ok = [s for s in shots if s.get("projection", {}).get("ok") and s.get("cells_in_frame")]
        if not ok:
            return "нет данных", "нет валидированной проекции"
        cf = ok[-1]["cells_in_frame"]
        return ("измерено (вспомогательно)",
                f"клеток полностью в кадре {cf['full']}/{cf['total']} (частично {cf['partial']}); "
                f"остаток проекции {ok[-1]['projection']['residual_max_px_used_camera']} px; различимость — ручная")
    bound = [r for r in candidates if any(_bind(ref, kpath)[0] for ref in _refs(kind, r))]
    if not bound:
        return MISMATCH, _mismatch_detail(kind, candidates, kpath)
    r = bound[-1]
    st = r.get("status")
    if st == "requires_new_trace":
        return "нет данных: требуется новая трасса", r.get("reason", "")
    if st != "measured":
        return "нет данных", r.get("reason", st or "?")
    if kind == "c9":
        dev = r["delta_ev"]["used"]
        dch = r["verdicts"]["more_saturated"]["value"]
        proxies = _c9_proxies(r)
        if proxies:
            on = r.get("result_on_proxy") or {"normative": r.get("result_normative"),
                                              "proposed": r.get("result_proposed")}
            return (proxy_status(proxies),
                    f"измерено на прокси (не норматив): «ярче» {on.get('normative')}, предложено "
                    f"{on.get('proposed')}; ΔEV={dev:+.3f}; ΔC*={dch:+.2f}; прокси: "
                    + "; ".join(f"{x['layer']} {x['spec']} — {x['why']}" for x in proxies))
        return (f"измерено: {r['result_normative']} (норматив) / {r['result_proposed']} (предложено)",
                f"ΔEV={dev:+.3f}; ΔC*={dch:+.2f}; декор={r.get('decor_region', {}).get('spec', '?')}")
    if kind == "plate":
        return (f"измерено: {r['result']} (предложенный порог)",
                f"клеток проверено {r['checked_cells']['count']}, нарушений {len(r['violations'])}")
    if kind == "icon":
        parts = [f"{s['size_px']}px: {s['contrast_ratio']}:1{' ↑' if s['upscaled'] else ''}" for s in r["sizes"]]
        return f"измерено: {r['result']} (предложенный порог)", "; ".join(parts)
    return "измерено", ""


def _provenance(frames: dict, results: dict) -> tuple[str, str]:
    """Config frames must be packaged-live (classified, not a path hint), and
    every result listed in the config must be measured on one of them."""
    bad, desc = [], []
    for k in KEYS:
        f = frames.get(k, {})
        prov = f.get("provenance") or provenance_hint(f.get("path"))
        desc.append(f"{k}: {prov}")
        if not prov.startswith("packaged-live"):
            bad.append(k)
        elif prov.endswith("(hint)"):
            bad.append(f"{k} (только подсказка по пути)")
    loose = []
    for cmd, rs in results.items():
        for r in ([rs] if cmd == "derive" else rs):
            label = r.get("_k", "K1..K3")
            if _bound_to(cmd, r, frames, _k_keys(label)):
                continue
            refs = _refs(cmd, r)
            where = ", ".join(sorted({_short(ref.get("path") or f"{ref.get('shot')} @ {ref.get('trace')}")
                                      for ref in refs})) or "кадр не указан"
            hints = sorted({provenance_hint(ref.get("path") or ref.get("trace")) for ref in refs}) or ["unknown"]
            loose.append(f"{Path(r.get('_path', '?')).name} ({label}) снят не на кадре конфига: {where} "
                         f"[{', '.join(hints)}]")
    if loose:
        bad.append("результаты по другим кадрам")
        desc.append("результаты по другим кадрам: " + " | ".join(loose))
    status = "ок" if not bad else "не годится для приёмки: " + ", ".join(bad)
    return status, "; ".join(desc)


def _render_reference(frames: dict, results: dict) -> tuple[str, str]:
    """W4-A: every config frame K1..K3 needs a `qa010 render` result bound to
    it (same PNG / SHOT block) whose fingerprint equals the reference. A frame
    without a RENDER line (every pre-W4 frame) or off the reference (DX11, SM5
    fallback, sg.* != High, SP != 100, legacy light units) is not an
    acceptance frame."""
    renders = results.get("render", [])
    present = [k for k in KEYS if frames.get(k, {}).get("path")]
    if not present:
        return "открыто", "в конфиге нет кадров K1..K3"
    bad, desc = [], []
    for k in present:
        bound = [r for r in renders if _bound_to("render", r, frames, [k])]
        if not bound:
            bad.append(f"{k} (нет результата qa010 render по этому кадру)")
            continue
        r = bound[-1]
        if r.get("reference"):
            fp = r.get("fingerprint") or {}
            desc.append(f"{k}: эталон ({fp.get('rhi')}/{fp.get('featureLevel')}, gi={fp.get('gi')}, "
                        f"preset={fp.get('preset')}, SP {fp.get('screenPct')})")
        elif not r.get("fingerprint"):
            bad.append(f"{k} (в SHOT-блоке нет строки RENDER)")
        else:
            bad.append(f"{k} (не эталон: " + "; ".join((r.get("reasons") or [])[:4]) + ")")
    status = "ок" if not bad else "не годится для приёмки: " + ", ".join(bad)
    return status, "; ".join(desc)


def build_checklist(config: dict, base_dir: Path) -> dict:
    frames = config.get("frames", {})
    results: dict[str, list] = {}
    for item in config.get("results", []):
        p = Path(item["path"])
        if not p.is_absolute():
            p = base_dir / p
        data = _load(p)
        data["_k"] = item.get("k", "K1..K3")
        data["_path"] = str(p)
        cmd = data.get("command")
        if cmd == "derive":
            results["derive"] = data
        elif cmd:
            results.setdefault(cmd, []).append(data)
    manual = config.get("manual", {})
    viewer = config.get("viewer", {})
    rows = []
    for item_id, frame, text, source, norm, kind, auto in ITEMS:
        auto_status, auto_detail = ("—", "")
        if auto:
            auto_status, auto_detail = _auto_status(auto, frame, results, frames)
        m = manual.get(item_id, {})
        if kind == "viewer":
            vk = viewer.get("kind")
            if vk == "human":
                status = "указан: человек"
            elif vk:
                status = "суррогат (агент) — до ответа пользователя"
            else:
                status = "открыто"
            detail = viewer.get("note", "")
        elif kind == "provenance":
            status, detail = _provenance(frames, results)
        elif kind == "render":
            status, detail = _render_reference(frames, results)
        elif kind == "auto":
            status, detail = auto_status, auto_detail
        else:
            ans = str(m.get("status", "")).strip().lower()
            if ans in MANUAL_OK:
                status = "ручная: да"
            elif ans in MANUAL_NO:
                status = "ручная: нет"
            else:
                status = "открыто (ручная проверка)"
            detail = m.get("note", "")
            if auto:
                detail = (detail + " | " if detail else "") + f"авто: {auto_status} {auto_detail}".strip()
        rows.append({"id": item_id, "frame": frame, "criterion": text, "source": source,
                     "norm_status": norm, "kind": kind, "status": status, "detail": detail})
    given = {(e.get("frame"), e.get("id")): e for e in config.get("elements", [])}
    elements = []
    for frame, eid, text, source in DEFAULT_ELEMENTS:
        e = given.pop((frame, eid), {})
        elements.append({"frame": frame, "id": eid, "element": text, "source": source,
                         "status": e.get("status", "не указано"), "reason": e.get("reason", ""),
                         "norm": e.get("norm", "")})
    for (frame, eid), e in given.items():
        elements.append({"frame": frame, "id": eid, "element": e.get("element", eid),
                         "source": e.get("source", ""), "status": e.get("status", "не указано"),
                         "reason": e.get("reason", ""), "norm": e.get("norm", "")})
    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return {
        "command": "checklist",
        "tool": VERSION,
        "generated_utc": config.get("generated_utc") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "title": config.get("title", "QA-010 чек-лист"),
        "run": config.get("run", {}),
        "frames": {k: {**v, "provenance_used": v.get("provenance") or provenance_hint(v.get("path"))}
                   for k, v in frames.items()},
        "viewer": viewer,
        "rows": rows,
        "elements": elements,
        "status_counts": counts,
        "verdict": ("Не является приёмкой: инструмент фиксирует измерения и открытые пункты. "
                    "Решение QA-010 — проверяющий + независимый зритель (10 стр. 129); GD-058 — автор."),
    }


def _md_escape(s: str) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def render_markdown(cl: dict) -> str:
    out = [f"# {cl['title']}", ""]
    out.append(f"Сгенерировано: {cl['generated_utc']} · {cl['tool']}")
    out.append("")
    out.append(f"**{cl['verdict']}**")
    out.append("")
    run = cl.get("run") or {}
    if run:
        out.append("## Прогон")
        out.append("")
        for k, v in run.items():
            out.append(f"- {k}: {v}")
        out.append("")
    out.append("## Кадры")
    out.append("")
    out.append("| Кадр | Файл | Происхождение |")
    out.append("|---|---|---|")
    for k in ("K1", "K2", "K3"):
        f = cl["frames"].get(k)
        if f:
            out.append(f"| {k} | `{_md_escape(f.get('path', ''))}` | {_md_escape(f['provenance_used'])} |")
        else:
            out.append(f"| {k} | — | нет кадра |")
    out.append("")
    out.append("## Признаки K-1..K-3 (QA-010)")
    out.append("")
    out.append("| ID | Кадр | Признак | Статус нормы | Источник | Результат | Детали |")
    out.append("|---|---|---|---|---|---|---|")
    for r in cl["rows"]:
        out.append("| " + " | ".join(_md_escape(x) for x in (
            r["id"], r["frame"], r["criterion"], r["norm_status"], r["source"], r["status"], r["detail"])) + " |")
    out.append("")
    out.append("## Элементы кадра: есть / отложено")
    out.append("")
    out.append("| Кадр | Элемент | Статус | Причина / норма | Источник |")
    out.append("|---|---|---|---|---|")
    for e in cl["elements"]:
        reason = "; ".join(x for x in (e["reason"], e["norm"]) if x)
        out.append("| " + " | ".join(_md_escape(x) for x in (
            e["frame"], e["element"], e["status"], reason, e["source"])) + " |")
    out.append("")
    out.append("## Сводка статусов")
    out.append("")
    for k, v in sorted(cl["status_counts"].items()):
        out.append(f"- {k}: {v}")
    out.append("")
    return "\n".join(out)
