#!/usr/bin/env python3
"""Контракт FS08CueDispatcher без движка: валидатор таблицы, эталонная модель и гейт трассы.

Спецификация: docs/unreal/contracts/cue-dispatcher/CUE-DISPATCHER.md.
Данные: docs/unreal/contracts/cue-dispatcher/cue-table.json (+ cue-table.schema.json).
Фикстуры без мира: docs/unreal/contracts/cue-dispatcher/fixtures/*.json.

Команды (из корня репозитория):
  python tools/s08/cue_contract/cue_contract.py validate-table [--table P]   схема + семантика + сверка с 07; missing-report
  python tools/s08/cue_contract/cue_contract.py run-fixtures [--dir D]       эталонная модель против expect_trace и гейт
  python tools/s08/cue_contract/cue_contract.py check-trace <log> [--table P] [--min-ms-cue N] [--min-combat N]
                                                             [--min-death N]
                                                                           гейт трассы `CUE fx … result=`, `MS-CUE move …`
                                                                           (move-selection 04 §9, MS-AT-28), постановки боя
                                                                           `CUE combat …` (DE-018, C1-C6) и смерти
                                                                           `CUE death …` / `RESULT screen …` (DE-019, DS1-DS5)
                                                                           реального лога

Эталонная модель — исполняемая форма спецификации для фикстур (C++-тесты GD-044 портируют те же
фикстуры), не код движка. Только stdlib + jsonschema (есть в системном Python).
Код выхода: 0 — ошибок нет, 1 — есть ошибки, 2 — ошибка запуска.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CONTRACT_DIR = REPO / "docs/unreal/contracts/cue-dispatcher"
TABLE = CONTRACT_DIR / "cue-table.json"
SCHEMA = CONTRACT_DIR / "cue-table.schema.json"
FIXTURE_SCHEMA = CONTRACT_DIR / "cue-fixture.schema.json"
FIXTURES = CONTRACT_DIR / "fixtures"
CSV07 = REPO / "docs/game-design/07-animation-vfx-audio.csv"
RIG_CONTRACT = REPO / "docs/art-pipeline/rig/rig-contract.json"
CONTENT_DIR = REPO / "unreal/Unmatched/Content"  # /Game/… → Content/….uasset (проверка путей клипов)

RESULTS_PRESENTED = ("spawned", "fallback")
RESULTS = RESULTS_PRESENTED + ("duplicate", "stale")
CUTS = ("0", "replace", "jump", "interrupt", "reconnect")
ACTOR_SOCKETS = ("Root", "Base")
MAX_BLOCKING_MS = 1000  # P3: блокировка ввода анимацией ≤ 1 с (08 §6.1), кроме терминального CUE


# ----------------------------------------------------------------------------- таблица
def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def short_name(soft_path):
    """/Game/FX/NS_Hit.NS_Hit -> NS_Hit (токен трассы без пробелов)."""
    return soft_path.rsplit(".", 1)[-1]


def rows_by_id(table):
    return {c["id"]: c for c in table["cues"]}


def content_file(soft_path, content_dir=CONTENT_DIR):
    """/Game/A/B.B -> <Content>/A/B.uasset."""
    return Path(content_dir) / (soft_path[len("/Game/"):].rsplit(".", 1)[0] + ".uasset")


def fighter_clip(spec, subject):
    """Путь клипа из clip.sequence_by_fighter для субъекта трассы (merlin → Merlin, arthur → KingArthur)."""
    s = re.sub(r"[^a-z]", "", (subject or "").lower())
    if len(s) < 3:
        return None
    for key, path in (spec.get("sequence_by_fighter") or {}).items():
        k = key.lower()
        if s == k or k.endswith(s) or s.startswith(k):
            return path
    return None


def _num(text):
    parts = text.strip().split()
    return int(parts[0]) if parts and parts[0].isdigit() else None


# ----------------------------------------------------------------------------- CUE-007: расписание перемещения
MOVE_PARAM_KEYS = ("duration_per_step_ms", "cap_subject_ms", "cap_seq_ms", "min_step_ms", "overlap", "place_ms")
MOVE_POSE_KEYS = ("hop_height_rel", "travel_lean_deg", "lean_in_ms", "start_turn_ms", "turn_ms", "settle_ms", "ease_ends")
SPEED_MUL = {"fast": 0.5, "normal": 1.0, "slow": 1.5}
MS_CUE_SOURCES = ("trail", "canonical", "straight")
MS_CUE_KINDS = ("move", "place")


def move_params(row):
    """Параметры расписания (move-selection 04 §6.3) из строки CUE с duration_per_step_ms (CUE-007)."""
    return {k: row[k] for k in MOVE_PARAM_KEYS}


def move_pose(row):
    """Поза фигуры на перемещении (04 §6.3, DE-021 по 01 F-02) из строки CUE-007; C++ FS08MoveAnimParams — те же значения."""
    return {k: row["pose"][k] for k in MOVE_POSE_KEYS}


def move_schedule(moves, params, mul=1.0, reduced=False):
    """Расписание перемещений одного seq (move-selection 04 §6.3) — зеркало C++ FS08MoveCueSchedule::Compute.

    moves — [{"kind": "move"|"place", "steps": n}] в порядке order_in_seq. Возвращает [{"start", "step", "steps",
    "ms", "snapped"}], мс от старта первого. Базовый шаг и потолки масштабируются множителем скорости mul,
    min_step_ms — нет; seq сжимается коэффициентом k, чтобы с перекрытием уложиться в cap_seq_ms; старты — от
    фактических длительностей; кто всё равно кончается позже потолка (+1 мс), снапается вместе с концом последнего
    анимированного. reduced или mul None (скорость «нет») — все snap в 0."""
    steps = [1 if m.get("kind", "move") == "place" else max(1, int(m.get("steps", 1))) for m in moves]
    if reduced or mul is None:
        return [{"start": 0.0, "step": 0.0, "steps": n, "ms": 0.0, "snapped": True} for n in steps]
    base = params["duration_per_step_ms"] * mul
    cap_f = params["cap_subject_ms"] * mul
    cap_m = params["cap_seq_ms"] * mul
    lead = 1.0 - params["overlap"]
    dur = [params["place_ms"] * mul if m.get("kind", "move") == "place" else min(n * base, cap_f)
           for m, n in zip(moves, steps)]
    total = sum(lead * d for d in dur[:-1]) + (dur[-1] if dur else 0.0)
    k = min(1.0, cap_m / total) if total > 0 else 1.0
    out, start = [], 0.0
    for d, n in zip(dur, steps):
        step = max(d * k / n, params["min_step_ms"])
        out.append({"start": start, "step": step, "steps": n, "ms": step * n, "snapped": False})
        start += lead * step * n
    j = next((i for i, e in enumerate(out) if e["start"] + e["ms"] > cap_m + 1.0), len(out))
    snap_at = out[j - 1]["start"] + out[j - 1]["ms"] if j > 0 else 0.0
    for e in out[j:]:
        e.update(start=snap_at, step=0.0, ms=0.0, snapped=True)
    return out


def validate_table(table, schema=None, csv07=CSV07, rig_contract=RIG_CONTRACT, content_dir=CONTENT_DIR):
    """Список ошибок таблицы: JSON Schema, затем семантика и сверка с 07."""
    import jsonschema

    errors = []
    schema = schema or load_json(SCHEMA)
    for e in jsonschema.Draft202012Validator(schema).iter_errors(table):
        errors.append("schema: %s: %s" % ("/".join(str(p) for p in e.absolute_path), e.message))
    if errors:
        return errors
    rows = {}
    for c in table["cues"]:
        if c["id"] in rows:
            errors.append("%s: повтор id" % c["id"])
        rows[c["id"]] = c
    ref = {}
    if csv07:
        with open(csv07, encoding="utf-8") as f:
            ref = {r["cueId"]: r for r in csv.DictReader(f)}
    if ref and set(ref) != set(rows):
        errors.append("набор CUE не совпадает с 07: нет %s, лишние %s" % (sorted(set(ref) - set(rows)), sorted(set(rows) - set(ref))))
    sockets = set(ACTOR_SOCKETS)
    if rig_contract and Path(rig_contract).exists():
        rc = load_json(rig_contract)
        sockets |= {s["name"] for s in rc.get("ue_import", {}).get("sockets_v2", rc.get("ue_import", {}).get("sockets", []))}
    for cid, c in rows.items():
        r = ref.get(cid)
        if r:
            want = _num(r["durationMs"])
            if c.get("duration_per_step_ms"):
                if c["duration_ms"] is not None or not r["durationMs"].strip().startswith("%d*" % c["duration_per_step_ms"]):
                    errors.append("%s: длительность на шаг %s не совпадает с 07 «%s»" % (cid, c["duration_per_step_ms"], r["durationMs"][:20]))
            elif c["duration_ms"] != want:
                errors.append("%s: duration_ms %s, в 07 %s" % (cid, c["duration_ms"], want))
            if c["feedback_delay_ms"] != (_num(r["feedbackDelayMs"]) or 0):
                errors.append("%s: feedback_delay_ms %s, в 07 %s" % (cid, c["feedback_delay_ms"], r["feedbackDelayMs"]))
            if c["blocks_input"] != r["blocksInput"].strip().lower().startswith("yes"):
                errors.append("%s: blocks_input не совпадает с 07" % cid)
        if c.get("duration_per_step_ms"):
            # CUE-007: потолки расписания 04 §6.3 согласованы между собой (наличие полей — схема)
            p = move_params(c)
            if p["cap_subject_ms"] < p["duration_per_step_ms"]:
                errors.append("%s: cap_subject_ms %s < duration_per_step_ms %s" % (cid, p["cap_subject_ms"], p["duration_per_step_ms"]))
            if p["cap_seq_ms"] < p["cap_subject_ms"]:
                errors.append("%s: cap_seq_ms %s < cap_subject_ms %s" % (cid, p["cap_seq_ms"], p["cap_subject_ms"]))
            if p["min_step_ms"] > p["duration_per_step_ms"]:
                errors.append("%s: min_step_ms %s > duration_per_step_ms %s" % (cid, p["min_step_ms"], p["duration_per_step_ms"]))
            if p["place_ms"] < p["min_step_ms"]:
                errors.append("%s: place_ms %s < min_step_ms %s" % (cid, p["place_ms"], p["min_step_ms"]))
            for name in ("path", "order_in_seq"):
                if name not in c["params"]:
                    errors.append("%s: params.%s не описан" % (cid, name))
            # DE-021 (01 F-02): поза хода — вход наклона, разворот и доворот укладываются в одно ребро (C++ режет по ребру)
            pose = c["pose"]
            for name in ("lean_in_ms", "start_turn_ms", "turn_ms"):
                if pose[name] > p["duration_per_step_ms"]:
                    errors.append("%s: pose.%s %s > duration_per_step_ms %s" % (cid, name, pose[name], p["duration_per_step_ms"]))
        dur = c["duration_ms"] or 0
        if c["blocks_input"] and dur > MAX_BLOCKING_MS and c["on_new_event"] != "none":
            errors.append("%s: блокирует ввод %d мс > %d (P3) и не терминальный" % (cid, dur, MAX_BLOCKING_MS))
        for ch, key in (("vfx", "system"), ("sfx", "sound"), ("clip", "sequence")):
            a = c.get(ch)
            if not a:
                continue
            path = a.get(key) or a.get("sequence_by_fighter")
            if a["status"] == "present" and not path:
                errors.append("%s: %s.status present без пути %s" % (cid, ch, key))
            if a["status"] == "missing" and path:
                errors.append("%s: %s.status missing, но путь задан" % (cid, ch))
            if content_dir and Path(content_dir).is_dir():
                for fighter, soft in (a.get("sequence_by_fighter") or {}).items():
                    if not content_file(soft, content_dir).is_file():
                        errors.append("%s: %s.sequence_by_fighter.%s: нет ассета %s" % (cid, ch, fighter, soft))
        v = c.get("vfx")
        if v and v["attach"] == "socket" and v["socket"] not in sockets:
            errors.append("%s: сокет %s не из контракта рига (%s)" % (cid, v["socket"], sorted(sockets)))
        if (c.get("clip") or (v and v["attach"] == "socket")) and c["subject"] != "fighter":
            errors.append("%s: клип или сокет требуют subject=fighter" % cid)
        for other in c["interrupted_by"]:
            if other not in rows:
                errors.append("%s: interrupted_by %s нет в таблице" % (cid, other))
        if c["on_new_event"] == "interrupt" and not c["interrupted_by"]:
            errors.append("%s: on_new_event interrupt без interrupted_by" % cid)
        if c["source"] == "local" and c["on_reconnect"] != "skip":
            errors.append("%s: локальный CUE не ставится в очередь" % cid)
    return errors


def missing_report(table):
    """Строки «CUE / канал / причина» для каждого отсутствующего ассета (ART-010 missing-report)."""
    out = []
    for c in table["cues"]:
        for ch in ("vfx", "sfx", "clip"):
            a = c.get(ch)
            if a and a["status"] == "missing":
                out.append((c["id"], ch, a["missing_reason"]))
    return out


# ----------------------------------------------------------------------------- эталонная модель
class ReferenceDispatcher:
    """Исполняемая спецификация FS08CueDispatcher (CUE-DISPATCHER.md §3). Детерминирована, без мира."""

    def __init__(self, table, assets_present=None, assets_unloadable=()):
        self.rows = rows_by_id(table)
        self.present = assets_present or {}
        self.unloadable = set(assets_unloadable)
        self.lines = []
        self.seen = set()
        self.high_water = None
        self.recovered_seq = None
        self.reduced = False
        self.disconnected = False
        self.active = []  # {"id","subject","seq","start","end"}
        self.sfx_active = {}  # id -> [{"subject","seq","end"}]
        self.sfx_last = {}
        self.now = 0

    # -- helpers
    def _asset(self, cid, channel, subject=None):
        row = self.rows[cid]
        spec = row.get(channel)
        if not spec:
            return "none"
        key = {"vfx": "system", "sfx": "sound", "clip": "sequence"}[channel]
        path = self.present.get(cid, {}).get(channel) or spec.get(key)
        if not path and channel == "clip":
            path = fighter_clip(spec, subject)
        if not path or path in self.unloadable:
            return "missing"
        return short_name(path)

    def _duration(self, row, event):
        if event.get("duration_ms") is not None:
            dur = int(event["duration_ms"])  # DE-018: показ с длиной постановки (скорость анимации)
        elif row.get("duration_per_step_ms"):
            # CUE-007: расписание 04 §6.3 — по всем перемещениям seq (seq_moves + order) или по одному этому
            moves = event.get("seq_moves") or [{"kind": event.get("move_kind", "move"), "steps": int(event.get("steps", 1))}]
            dur = int(round(move_schedule(moves, move_params(row))[int(event.get("order", 0))]["ms"]))
        elif event.get("duration_ms") is None:
            dur = row["duration_ms"] or 0
        rm = row["reduced_motion"]
        reduced = self.reduced and rm["mode"] != "keep"
        if reduced:
            dur = 0 if rm["mode"] == "snap" else min(dur, rm["max_ms"])
        return dur, reduced

    def _done(self, inst, t, cut):
        line = ("CUE fx done id=%s subject=%s seq=%s t=%d ms=%d cut=%s"
                % (inst["id"], inst["subject"], inst["seq"], t, t - inst["start"], cut))
        if inst.get("hold"):
            # DE-018 (§4 D12): пропускаемое удержание внутри показа; G5 меряет блокировку как ms − hold
            line += " hold=%d" % min(inst["hold"], t - inst["start"])
        self.lines.append(line)

    def _flush(self, t):
        due = sorted((i for i in self.active if i["end"] <= t), key=lambda i: (i["end"], i["order"]))
        for inst in due:
            self._done(inst, inst["end"], "0")
            self.active.remove(inst)
        for cid in list(self.sfx_active):
            self.sfx_active[cid] = [s for s in self.sfx_active[cid] if s["end"] > t]

    def _cut(self, pred, t, cut):
        for inst in sorted((i for i in self.active if pred(i)), key=lambda i: i["order"]):
            self._done(inst, t, cut)
            self.active.remove(inst)

    # -- API
    def feed(self, event):
        t = int(event["t"])
        if t < self.now:
            raise ValueError("время событий должно не убывать: %d < %d" % (t, self.now))
        self.now = t
        self._flush(t)
        kind = event["kind"]
        if kind == "advance":
            return
        if kind == "combat":
            # DE-018: строка постановки боя (CUE-DISPATCHER.md §5) — порядок полей как в событии
            extra = "".join(" %s=%s" % (k, v) for k, v in (event.get("fields") or {}).items())
            self.lines.append("CUE combat seq=%d stage=%s t=%d%s" % (int(event["seq"]), event["stage"], t, extra))
            return
        if kind == "settings":
            self.reduced = bool(event["reduced_motion"])
            self.lines.append("CUE settings reduced_motion=%d t=%d" % (int(self.reduced), t))
            return
        if kind == "reconnect":
            r = int(event["recovered_seq"])
            self.lines.append("CUE reconnect recovered_seq=%d t=%d" % (r, t))
            self._cut(lambda i: True, t, "reconnect")
            self.sfx_active.clear()
            self.recovered_seq = r
            self.high_water = r if self.high_water is None else max(self.high_water, r)
            self.disconnected = False
            return
        if kind != "cue":
            raise ValueError("unknown event kind %s" % kind)
        cid = event["id"]
        row = self.rows[cid]
        subject = event.get("subject") or row["subject"]
        seq = event.get("seq")
        seq_tok = "-" if seq is None else str(int(seq))
        head = "CUE fx id=%s subject=%s seq=%s t=%d" % (cid, subject, seq_tok, t)
        if row["source"] == "server":
            if seq is None:
                raise ValueError("%s: серверному CUE нужен seq" % cid)
            key = (cid, subject, int(seq))
            if key in self.seen:
                self.lines.append(head + " result=duplicate")
                return
            self.seen.add(key)
            # staged: CUE постановки (контакт DE-018, падение DE-019) идёт с seq своего боя после более новых
            # снапшотов — D3 к нему не применяется, D2 и D4 применяются (прогон C G-LIVE, 2026-10-05)
            if (self.recovered_seq is not None and seq <= self.recovered_seq) or (
                    not event.get("staged") and self.high_water is not None and seq < self.high_water):
                self.lines.append(head + " result=stale")
                return
            self.high_water = seq if self.high_water is None else max(self.high_water, seq)
        elif row["trigger"] == "net.disconnected":
            if self.disconnected:
                self.lines.append(head + " result=duplicate")
                return
            self.disconnected = True
        # прерывания и замена
        self._cut(lambda i: cid in self.rows[i["id"]]["interrupted_by"], t, "interrupt")
        if row["on_new_event"] != "cascade":
            cut = "jump" if row["on_new_event"] == "jump_to_final" else "replace"
            per_cue = row["replace_scope"] == "cue"
            self._cut(lambda i: i["id"] == cid and (per_cue or i["subject"] == subject), t, cut)
        dur, reduced = self._duration(row, event)
        vfx, clip = self._asset(cid, "vfx"), self._asset(cid, "clip", subject)
        sfx = self._asset(cid, "sfx")
        if sfx not in ("none", "missing"):
            conc = row["sfx"]["concurrency"]
            last = self.sfx_last.get(cid)
            if last is not None and conc["retrigger_ms"] and t - last < conc["retrigger_ms"]:
                sfx = "throttled"
            else:
                act = self.sfx_active.setdefault(cid, [])
                if conc["max_count"] and len(act) >= conc["max_count"]:
                    if conc["resolution"] == "PreventNew":
                        sfx = "limited"
                    else:
                        old = act.pop(0)
                        self.lines.append("CUE sfx stop id=%s subject=%s seq=%s t=%d reason=concurrency"
                                          % (cid, old["subject"], old["seq"], t))
                if sfx != "limited":
                    act.append({"subject": subject, "seq": seq_tok, "end": t + dur + int(event.get("hold_ms", 0))})
                    self.sfx_last[cid] = t
        mat = (row.get("material") or {}).get("cpd_param", "none")
        v = row.get("vfx")
        socket = v["socket"] if v and v["attach"] == "socket" else "-"
        result = "fallback" if "missing" in (vfx, sfx, clip) else "spawned"
        self.lines.append(head + " vfx=%s sfx=%s clip=%s mat=%s socket=%s reduced=%d result=%s"
                          % (vfx, sfx, clip, mat, socket, int(reduced), result))
        hold = max(0, int(event.get("hold_ms", 0)))
        inst = {"id": cid, "subject": subject, "seq": seq_tok, "start": t, "end": t + dur + hold, "order": len(self.lines),
                "hold": hold}
        if dur + hold == 0:
            self._done(inst, t, "0")
        else:
            self.active.append(inst)

    def finish(self):
        self._flush(float("inf"))
        return self.lines


def run_reference(table, fixture):
    d = ReferenceDispatcher(table, fixture.get("assets_present"), fixture.get("assets_unloadable", ()))
    for e in fixture["events"]:
        d.feed(e)
    return d.finish()


# ----------------------------------------------------------------------------- гейт трассы
LINE_RE = re.compile(r"(CUE (?:fx done|fx|sfx stop|reconnect|settings)\b.*)$")


def parse_line(raw):
    m = LINE_RE.search(raw.rstrip("\r\n"))
    if not m:
        return None
    text = m.group(1)
    words = text.split()
    kind = " ".join(words[:3]) if text.startswith(("CUE fx done", "CUE sfx stop")) else " ".join(words[:2])
    fields = {}
    for w in words[len(kind.split()):]:
        if "=" in w:
            k, v = w.split("=", 1)
            fields[k] = v
    return kind, fields


MS_CUE_RE = re.compile(r"(MS-CUE move\b.*)$")
MS_CUE_NEED = ("seq", "fighter", "order", "of", "kind", "steps", "source", "start", "ms", "snapped")
MS_CUE_INTS = ("seq", "order", "of", "steps", "start", "ms", "snapped")


def parse_ms_cue(raw):
    """Поля строки `MS-CUE move k=v …` (префикс лога и хвост без `=` игнорируются) или None."""
    m = MS_CUE_RE.search(raw.rstrip("\r\n"))
    if not m:
        return None
    fields = {}
    for w in m.group(1).split()[2:]:
        if "=" in w:
            k, v = w.split("=", 1)
            fields[k] = v
    return fields


def _int_or_none(text):
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


def check_ms_cue(lines, table):
    """Гейт трасс `MS-CUE move` (move-selection 04 §4.6, §9; MS-AT-28). Набор — строки одного seq подряд, их
    ровно `of`. Коды: M1 формат и поля; M2 набор (прерван, не завершён, order не 0..of-1, повтор бойца);
    M3 шаги, вид и путь (place и straight — 1 шаг; в пути steps+1 клеток); M4 start/ms/snapped не по расписанию
    04 §6.3 с потолками CUE-007 из таблицы (±1 мс; необязательные speed=fast|normal|slow|none, reduced=0|1)."""
    row = rows_by_id(table).get("CUE-007")
    params = move_params(row) if row and row.get("duration_per_step_ms") else None
    errors, sets, current, count = [], [], None, 0
    sources = {s: 0 for s in MS_CUE_SOURCES}
    for n, raw in enumerate(lines, 1):
        f = parse_ms_cue(raw)
        if f is None:
            continue
        count += 1
        missing = [k for k in MS_CUE_NEED if k not in f]
        nums = {k: _int_or_none(f.get(k)) for k in MS_CUE_INTS}
        speed = f.get("speed", "normal")
        if (missing or any(v is None for v in nums.values()) or f["source"] not in MS_CUE_SOURCES
                or f["kind"] not in MS_CUE_KINDS or nums["of"] < 1 or nums["snapped"] not in (0, 1)
                or (speed not in SPEED_MUL and speed != "none")):
            errors.append(("M1", "строка %d: формат MS-CUE (нет полей %s или неверное значение)" % (n, missing)))
            continue
        sources[f["source"]] += 1
        if current and (current["seq"] != nums["seq"] or current["of"] != nums["of"]):
            errors.append(("M2", "строка %d: набор seq %d прерван: %d из %d строк"
                           % (n, current["seq"], len(current["items"]), current["of"])))
            current = None
        if current is None:
            current = {"seq": nums["seq"], "of": nums["of"], "items": []}
        current["items"].append((n, f, nums))
        if len(current["items"]) == current["of"]:
            sets.append(current)
            current = None
    if current:
        errors.append(("M2", "набор seq %d не завершён: %d из %d строк" % (current["seq"], len(current["items"]), current["of"])))
    for s in sets:
        items = sorted(s["items"], key=lambda x: x[2]["order"])
        if [x[2]["order"] for x in items] != list(range(s["of"])):
            errors.append(("M2", "seq %d: order %s, ожидалось 0..%d" % (s["seq"], [x[2]["order"] for x in items], s["of"] - 1)))
            continue
        fighters = [x[1]["fighter"] for x in items]
        if len(set(fighters)) != len(fighters):
            errors.append(("M2", "seq %d: боец повторён %s" % (s["seq"], fighters)))
            continue
        bad = False
        for n, f, nums in items:
            cells = f["path"].split(">") if f.get("path") else None
            if nums["steps"] < 1 or ((f["kind"] == "place" or f["source"] == "straight") and nums["steps"] != 1):
                errors.append(("M3", "строка %d: steps=%d при kind=%s source=%s" % (n, nums["steps"], f["kind"], f["source"])))
                bad = True
            elif cells is not None and len(cells) != nums["steps"] + 1:
                errors.append(("M3", "строка %d: в пути %d клеток при steps=%d" % (n, len(cells), nums["steps"])))
                bad = True
        if bad or params is None:
            continue
        speed = items[0][1].get("speed", "normal")
        mul = None if speed == "none" else SPEED_MUL[speed]
        sched = move_schedule([{"kind": f["kind"], "steps": nums["steps"]} for _, f, nums in items], params, mul,
                              items[0][1].get("reduced") == "1")
        for (n, f, nums), e in zip(items, sched):
            if abs(nums["start"] - e["start"]) > 1 or abs(nums["ms"] - e["ms"]) > 1 or bool(nums["snapped"]) != e["snapped"]:
                errors.append(("M4", "строка %d: start=%d ms=%d snapped=%d, по 04 §6.3 start=%.1f ms=%.1f snapped=%d"
                               % (n, nums["start"], nums["ms"], nums["snapped"], e["start"], e["ms"], int(e["snapped"]))))
    return errors, {"ms_cue": count, "ms_cue_sets": len(sets), "ms_cue_sources": sources}


def check_trace(lines, table):
    """Ошибки гейта (код: текст) и сводка. Коды: G1 формат, G2 один показ на тройку, G3 нет старого после
    реконнекта, G4 done и длительности, G5 блокировка ввода, G6 одновременность звука, G7 частота звука,
    G8 fallback, G9 время монотонно; M1..M4 — трассы `MS-CUE move` (check_ms_cue)."""
    rows = rows_by_id(table)
    errors = []
    presented = {}
    open_inst = {}
    starts = []
    recovered = None
    last_t = None
    summary = {"presented": 0, "spawned": 0, "fallback": 0, "duplicate": 0, "stale": 0, "done": 0, "unique_triples": 0}
    need = ("id", "subject", "seq", "t", "vfx", "sfx", "clip", "mat", "socket", "reduced", "result")
    stops = []
    for n, raw in enumerate(lines, 1):
        p = parse_line(raw)
        if p is None:
            continue
        kind, f = p
        t = int(f["t"]) if f.get("t", "").lstrip("-").isdigit() else None
        if t is None:
            errors.append(("G1", "строка %d: нет t" % n))
            continue
        if last_t is not None and t < last_t:
            errors.append(("G9", "строка %d: время %d < %d" % (n, t, last_t)))
        last_t = t
        if kind == "CUE reconnect":
            recovered = int(f["recovered_seq"])
            continue
        if kind == "CUE settings":
            continue
        cid = f.get("id")
        if cid not in rows:
            errors.append(("G1", "строка %d: неизвестный id %s" % (n, cid)))
            continue
        key = (cid, f.get("subject"), f.get("seq"))
        if kind == "CUE sfx stop":
            stops.append((t, cid, key))
            continue
        if kind == "CUE fx done":
            inst = open_inst.pop(key, None)
            if inst is None:
                errors.append(("G4", "строка %d: done без показа %s" % (n, key)))
                continue
            summary["done"] += 1
            ms = int(f.get("ms", "-1"))
            if ms != t - inst["t"] or f.get("cut") not in CUTS:
                errors.append(("G4", "строка %d: ms/cut не согласованы %s" % (n, key)))
            # DE-018 (§4 D12): удержание постановки боя пропускается кликом и ввод не блокирует
            hold = int(f["hold"]) if f.get("hold", "").isdigit() else 0
            if hold > ms:
                errors.append(("G4", "строка %d: hold %d > ms %d" % (n, hold, ms)))
            anim = ms - hold
            row = rows[cid]
            rm = row["reduced_motion"]
            if inst["reduced"] and rm["mode"] == "shorten" and anim > rm["max_ms"]:
                errors.append(("G4", "строка %d: сокращённая анимация %d мс > %d" % (n, anim, rm["max_ms"])))
            if inst["reduced"] and rm["mode"] == "snap" and anim != 0:
                errors.append(("G4", "строка %d: snap длится %d мс" % (n, anim)))
            if row["blocks_input"] and anim > MAX_BLOCKING_MS and row["on_new_event"] != "none":
                errors.append(("G5", "строка %d: блокирующий CUE %s длился %d мс" % (n, cid, anim)))
            inst["end"] = t
            inst["hold"] = hold
            continue
        # CUE fx
        res = f.get("result")
        if res not in RESULTS:
            errors.append(("G1", "строка %d: result=%s" % (n, res)))
            continue
        summary[res] += 1
        if res not in RESULTS_PRESENTED:
            continue
        missing_fields = [k for k in need if k not in f]
        if missing_fields:
            errors.append(("G1", "строка %d: нет полей %s" % (n, missing_fields)))
            continue
        summary["presented"] += 1
        if key[2] != "-":
            presented[key] = presented.get(key, 0) + 1
            if presented[key] > 1:
                errors.append(("G2", "строка %d: повторный показ %s" % (n, key)))
            if recovered is not None and int(key[2]) <= recovered:
                errors.append(("G3", "строка %d: показ seq %s ≤ recovered_seq %d после реконнекта" % (n, key[2], recovered)))
        has_missing = "missing" in (f["vfx"], f["sfx"], f["clip"])
        if (res == "fallback") != has_missing:
            errors.append(("G8", "строка %d: result=%s при vfx/sfx/clip=%s/%s/%s" % (n, res, f["vfx"], f["sfx"], f["clip"])))
        inst = {"t": t, "reduced": f["reduced"] == "1", "sfx": f["sfx"], "end": None, "cid": cid, "key": key}
        if key in open_inst:
            errors.append(("G4", "строка %d: новый показ до done предыдущего %s" % (n, key)))
        open_inst[key] = inst
        starts.append(inst)
    for key, inst in open_inst.items():
        errors.append(("G4", "показ без done: %s" % (key,)))
    summary["unique_triples"] = len(presented)
    # G6/G7: звук
    by_cue = {}
    for inst in starts:
        if inst["sfx"] in ("none", "missing", "throttled", "limited"):
            continue
        by_cue.setdefault(inst["cid"], []).append(inst)
    for cid, insts in by_cue.items():
        conc = (rows[cid].get("sfx") or {}).get("concurrency", {})
        for a, b in zip(insts, insts[1:]):
            if conc.get("retrigger_ms") and b["t"] - a["t"] < conc["retrigger_ms"]:
                errors.append(("G7", "%s: звук через %d мс < %d" % (cid, b["t"] - a["t"], conc["retrigger_ms"])))
        if conc.get("max_count"):
            for inst in insts:
                stopped = {k for (st, c, k) in stops if c == cid and st <= inst["t"]}
                playing = [o for o in insts if o is not inst and o["t"] <= inst["t"] and o["key"] not in stopped
                           and (o["end"] is None or o["end"] > inst["t"])]
                if len(playing) + 1 > conc["max_count"]:
                    errors.append(("G6", "%s: %d звуков одновременно > %d (t=%d)" % (cid, len(playing) + 1, conc["max_count"], inst["t"])))
    ms_errors, ms_summary = check_ms_cue(lines, table)
    errors.extend(ms_errors)
    summary.update(ms_summary)
    c_errors, c_summary = check_combat(lines, starts)
    errors.extend(c_errors)
    summary.update(c_summary)
    d_errors, d_summary = check_death(lines)
    errors.extend(d_errors)
    summary.update(d_summary)
    return errors, summary


# ----------------------------------------------------------------------------- постановка боя (DE-018)
COMBAT_RE = re.compile(r"(CUE combat\b.*)$")
COMBAT_STAGES = ("start", "read", "effect", "slam", "pause", "lunge", "contact", "hit", "minus", "hp", "fall", "end",
                 "skip")
COMBAT_RANK = {"start": 0, "read": 1, "effect": 2, "slam": 3, "pause": 4, "lunge": 5, "contact": 6, "hit": 7,
               "minus": 8, "hp": 9, "fall": 10, "end": 11}
COMBAT_START_NEED = ("attacker", "target", "text", "lines", "damage", "lethal", "shown", "speed", "flip", "contact",
                     "src", "a", "d", "outcome")
COMBAT_MS = {  # 01 F-01 / F-03 / F-04 / F-09 при скорости ×1 (CUE-DISPATCHER.md §3.1)
    "declare": 600, "read": 1000, "effect_step": 600, "effect_highlight": 400, "pause": 300,
    "minus": 60, "hp": 80, "fall": 450, "tint": 450, "tint_lethal": 550, "minus_life": 900,
}


def parse_combat(raw):
    m = COMBAT_RE.search(raw.rstrip("\r\n"))
    if not m:
        return None
    fields = {}
    for w in m.group(1).split()[2:]:
        if "=" in w:
            k, v = w.split("=", 1)
            fields[k] = v
    return fields


def check_combat(lines, cue_starts=()):
    """Гейт постановки боя `CUE combat …` (DE-018, CUE-DISPATCHER.md §6): C1 формат; C2 одна постановка на seq;
    C3 порядок этапов и время; C4 удержания (чтение только при тексте эффекта, 600 на строку, пауза 300, слэм после
    удержаний, выпад после паузы, контакт = выпад + кадр контакта); C5 от кадра контакта: HitReact и заливка в кадре
    контакта, «−N» +60, HP +80, падение +450, CUE-011 из кадра контакта, без урона — ни удара, ни «−N»; C6 итог
    = CUE-008 + (конец − раскрытие). Прерванная постановка (cut≠0) проверяется только по C1–C3."""
    errors = []
    by_seq = {}
    order = []
    for n, raw in enumerate(lines, 1):
        f = parse_combat(raw)
        if f is None:
            continue
        seq, stage = f.get("seq"), f.get("stage")
        t = _int_or_none(f.get("t"))
        if seq is None or stage not in COMBAT_STAGES or t is None:
            errors.append(("C1", "строка %d: CUE combat без seq/stage/t или неизвестный этап %s" % (n, stage)))
            continue
        f["_n"], f["_t"] = n, t
        if seq not in by_seq:
            by_seq[seq] = []
            order.append(seq)
        by_seq[seq].append(f)
    fx = {}
    done = {}
    for inst in cue_starts:
        fx.setdefault(inst["key"], inst)
    for raw in lines:
        p = parse_line(raw)
        if p and p[0] == "CUE fx done":
            f = p[1]
            done[(f.get("id"), f.get("subject"), f.get("seq"))] = f
    summary = {"combat_sets": 0, "combat_cut": 0, "combat_skipped": 0, "combat_totals": []}
    for seq in order:
        rows = by_seq[seq]
        starts = [r for r in rows if r["stage"] == "start"]
        ends = [r for r in rows if r["stage"] == "end"]
        if len(starts) != 1 or len(ends) > 1:
            errors.append(("C2", "seq %s: постановок %d, концов %d (повтор seq не даёт второй показ)" % (seq, len(starts), len(ends))))
            continue
        st = starts[0]
        missing = [k for k in COMBAT_START_NEED if k not in st]
        if missing:
            errors.append(("C1", "seq %s: в start нет полей %s" % (seq, missing)))
            continue
        if rows[0] is not st:
            errors.append(("C3", "seq %s: этап до start" % seq))
        summary["combat_sets"] += 1
        last_t, last_rank = None, -1
        for r in rows:
            if last_t is not None and r["_t"] < last_t:
                errors.append(("C3", "строка %d: время этапа %d < %d" % (r["_n"], r["_t"], last_t)))
            last_t = r["_t"]
            if r["stage"] == "skip":
                continue
            rank = COMBAT_RANK[r["stage"]]
            if rank < last_rank:
                errors.append(("C3", "строка %d: этап %s после этапа ранга %d" % (r["_n"], r["stage"], last_rank)))
            last_rank = max(last_rank, rank)
        if not ends:
            errors.append(("C2", "seq %s: постановка без end" % seq))
            continue
        end = ends[0]
        if end.get("skipped") == "1":
            summary["combat_skipped"] += 1
        if end.get("cut", "0") != "0":
            summary["combat_cut"] += 1
            continue
        stages = {}
        for r in rows:
            stages.setdefault(r["stage"], []).append(r)
        one = lambda name: (stages.get(name) or [None])[0]
        speed = float(st["speed"])
        scale = (lambda ms: 0 if speed <= 0 else int(round(ms * speed)))
        text, n_lines = st["text"] == "1", int(st["lines"])
        damage, lethal, shown = int(st["damage"]), st["lethal"] == "1", st["shown"] == "1"
        present = damage > 0 and not shown
        # C4: удержания и стыки
        read = one("read")
        if text != (read is not None):
            errors.append(("C4", "seq %s: удержание чтения %s при text=%s" % (seq, "есть" if read else "нет", st["text"])))
        read_ms = int(read["ms"]) if read else 0
        if read and not (read_ms == COMBAT_MS["read"] or (read.get("skipped") == "1" and 0 <= read_ms <= COMBAT_MS["read"])):
            errors.append(("C4", "seq %s: чтение %d мс ≠ %d" % (seq, read_ms, COMBAT_MS["read"])))
        effects = stages.get("effect", [])
        if len(effects) != n_lines:
            errors.append(("C4", "seq %s: строк эффекта %d ≠ lines=%d" % (seq, len(effects), n_lines)))
        step = scale(COMBAT_MS["effect_highlight"]) + COMBAT_MS["effect_step"] - COMBAT_MS["effect_highlight"]
        eff_ms = 0
        for e in effects:
            ms = int(e["ms"])
            eff_ms += ms
            if not (ms == step or (e.get("skipped") == "1" and 0 <= ms <= step)):
                errors.append(("C4", "строка %d: строка эффекта %d мс ≠ %d" % (e["_n"], ms, step)))
        slam, pause, lunge, contact = one("slam"), one("pause"), one("lunge"), one("contact")
        if not (slam and pause and lunge and contact):
            errors.append(("C4", "seq %s: нет slam/pause/lunge/contact" % seq))
            continue
        if slam["_t"] != st["_t"] + int(st["flip"]) + read_ms + eff_ms:
            errors.append(("C4", "seq %s: слэм t=%d ≠ раскрытие + переворот + удержания %d" % (
                seq, slam["_t"], st["_t"] + int(st["flip"]) + read_ms + eff_ms)))
        d10 = done.get(("CUE-010", "scene", seq))
        if d10 is not None:
            hold = int(d10.get("hold", "0") or 0)
            if hold != read_ms + eff_ms:
                errors.append(("C4", "seq %s: hold CUE-010 %d ≠ удержания %d" % (seq, hold, read_ms + eff_ms)))
            if pause["_t"] - int(pause["ms"]) != int(d10["t"]):
                errors.append(("C4", "seq %s: пауза «счёт» не от конца слэма (CUE-010 done t=%s)" % (seq, d10["t"])))
        pause_ms = int(pause["ms"])
        if not (pause_ms == COMBAT_MS["pause"] or (pause.get("skipped") == "1" and 0 <= pause_ms <= COMBAT_MS["pause"])):
            errors.append(("C4", "seq %s: пауза «счёт» %d мс ≠ %d" % (seq, pause_ms, COMBAT_MS["pause"])))
        if lunge["_t"] != pause["_t"]:
            errors.append(("C4", "seq %s: выпад не в конце паузы" % seq))
        # DE-025 (SD-49): play rate LungeAttack = 1 / скорость, при «Нет» клипа нет (0); поле rate= — с DE-025
        if "rate" in lunge:
            want_rate = 0.0 if speed <= 0 else 1.0 / speed
            if abs(float(lunge["rate"]) - want_rate) > 0.006:
                errors.append(("C4", "seq %s: play rate выпада %s ≠ 1/скорость %.2f" % (seq, lunge["rate"], want_rate)))
        if contact["_t"] != lunge["_t"] + int(st["contact"]) or contact.get("offset") != st["contact"]:
            errors.append(("C4", "seq %s: контакт t=%d ≠ выпад + %s" % (seq, contact["_t"], st["contact"])))
        # C5: от кадра контакта
        ct = contact["_t"]
        hit, minus, hp, fall = one("hit"), one("minus"), one("hp"), one("fall")
        if (st["outcome"] == "win") != (damage > 0):
            errors.append(("C5", "seq %s: outcome=%s при damage=%d" % (seq, st["outcome"], damage)))
        if present:
            tint = COMBAT_MS["tint_lethal"] if lethal else COMBAT_MS["tint"]
            if not hit or hit["_t"] != ct or int(hit.get("tint", -1)) != tint:
                errors.append(("C5", "seq %s: HitReact и заливка %d мс не в кадре контакта" % (seq, tint)))
            if not minus or minus["_t"] - ct != COMBAT_MS["minus"]:
                errors.append(("C5", "seq %s: «−N» не через %d мс после контакта" % (seq, COMBAT_MS["minus"])))
            # F-04 / DE-025: «−N» живёт 900 × скорость («Нет» — как «Быстро», 450)
            want_life = int(round(COMBAT_MS["minus_life"] * (speed if speed > 0 else 0.5)))
            if minus and "life" in minus and int(minus["life"]) != want_life:
                errors.append(("C5", "seq %s: «−N» живёт %s мс ≠ %d" % (seq, minus["life"], want_life)))
            if not hp or hp["_t"] - ct != COMBAT_MS["hp"]:
                errors.append(("C5", "seq %s: HP не через %d мс после контакта" % (seq, COMBAT_MS["hp"])))
            if lethal and (not fall or fall["_t"] - ct != COMBAT_MS["fall"]):
                errors.append(("C5", "seq %s: падение не через %d мс после контакта" % (seq, COMBAT_MS["fall"])))
            if not lethal and fall:
                errors.append(("C5", "seq %s: падение при нелетальном ударе" % seq))
            d11 = fx.get(("CUE-011", st["target"], seq))
            if d11 is None or d11["t"] != ct:
                errors.append(("C5", "seq %s: CUE-011 не из кадра контакта" % seq))
            elif d11.get("end") is not None and d11["end"] > end["_t"]:
                errors.append(("C5", "seq %s: CUE-011 кончился после конца постановки" % seq))
        elif hit or minus or hp or fall:
            errors.append(("C5", "seq %s: удар/«−N»/HP без показанного урона (damage=%d shown=%s)" % (seq, damage, st["shown"])))
        tail = int(contact.get("window", "0"))
        if present:
            tail = max(tail, COMBAT_MS["hp"], COMBAT_MS["fall"] if lethal else 0)
        if end["_t"] - ct != tail:
            errors.append(("C5", "seq %s: конец через %d мс после контакта ≠ %d" % (seq, end["_t"] - ct, tail)))
        # C6: итог шкалы F-01
        total = scale(COMBAT_MS["declare"]) + end["_t"] - st["_t"]
        if int(end.get("total", "-1")) != total:
            errors.append(("C6", "seq %s: total=%s ≠ %d" % (seq, end.get("total"), total)))
        summary["combat_totals"].append(total)
    return errors, summary


# ----------------------------------------------------------------------------- смерть и экран результата (DE-019)
DEATH_RE = re.compile(r"(CUE death\b.*)$")
RESULT_SCREEN_RE = re.compile(r"(RESULT screen\b.*)$")
DEATH_STAGES = ("fall", "mark", "dissolve", "gone")
DEATH_FALL_NEED = ("fighter", "hero", "staged", "settle", "still", "dissolve", "style", "gone")
RESULT_NEED = ("seq", "t", "due", "gameOver", "heroGone", "wait")
DEATH_MS = {  # 01 F-09 при скорости ×1 (CUE-DISPATCHER.md §3.1): от кадра контакта
    "fall": 450, "settle": 875, "mark": 1100, "still_hero": 300, "still_sidekick": 0,
    "dissolve_hero": 500, "dissolve_sidekick": 400, "result_after_gone": 1000, "max_wait": 10000,
    "frame_tolerance": 100,  # падение смерти против этапа fall постановки и экран против due: кадр-два на 30 FPS
}


def _fields(text, skip):
    out = {}
    for w in text.split()[skip:]:
        if "=" in w:
            k, v = w.split("=", 1)
            out[k] = v
    return out


def check_death(lines):
    """Гейт смерти `CUE death …` и экрана результата `RESULT screen …` (DE-019, CUE-DISPATCHER.md §6): DS1 формат;
    DS2 одна смерть на (seq, боец) и все её этапы; DS3 этапы F-09 от падения (метка +650 = контакт + 1100,
    растворение = падение + оседание + неподвижно, исчезновение = + растворение; v2-фигура: оседание 875, неподвижно
    300 у героя и 0 у помощника, растворение 500 / 400 или 0 со style=none); DS4 падение постановки (`staged=1`) —
    в кадр этапа `fall` её `CUE combat` (≤ 100 мс); DS5 экран результата не раньше исчезновения героя + 1000 мс
    (без смерти героя — сразу после GAME_OVER), due по правилу, показ не позже due + 100 мс."""
    errors = []
    deaths = {}
    order = []
    screens = []
    combat_fall = {}
    combat_contact = {}
    for n, raw in enumerate(lines, 1):
        line = raw.rstrip("\r\n")
        cf = parse_combat(line)
        if cf is not None and cf.get("stage") in ("fall", "contact"):
            t = _int_or_none(cf.get("t"))
            if t is not None and cf.get("stage") == "fall":
                combat_fall[(cf.get("seq"), cf.get("target"))] = t
            elif t is not None:
                combat_contact[cf.get("seq")] = t
            continue
        m = DEATH_RE.search(line)
        if m:
            f = _fields(m.group(1), 2)
            seq, stage, fighter = f.get("seq"), f.get("stage"), f.get("fighter")
            t = _int_or_none(f.get("t"))
            if seq is None or stage not in DEATH_STAGES or t is None or not fighter:
                errors.append(("DS1", "строка %d: CUE death без seq/stage/t/fighter или неизвестный этап %s" % (n, stage)))
                continue
            f["_n"], f["_t"] = n, t
            key = (seq, fighter)
            if key not in deaths:
                deaths[key] = []
                order.append(key)
            deaths[key].append(f)
            continue
        m = RESULT_SCREEN_RE.search(line)
        if m:
            f = _fields(m.group(1), 2)
            missing = [k for k in RESULT_NEED if k not in f]
            if missing:
                errors.append(("DS1", "строка %d: RESULT screen без полей %s" % (n, missing)))
                continue
            f["_n"] = n
            screens.append(f)
    summary = {"death_sets": 0, "death_heroes": 0, "result_screens": len(screens), "hit_to_screen": []}
    hero_gone = []  # (fall_t, gone_t, seq)
    for key in order:
        rows = deaths[key]
        seq, fighter = key
        falls = [r for r in rows if r["stage"] == "fall"]
        if len(falls) != 1:
            errors.append(("DS2", "%s/%s: падений %d (одна смерть на бойца)" % (seq, fighter, len(falls))))
            continue
        fall = falls[0]
        missing = [k for k in DEATH_FALL_NEED if k not in fall]
        if missing:
            errors.append(("DS1", "%s/%s: в fall нет полей %s" % (seq, fighter, missing)))
            continue
        if rows[0] is not fall:
            errors.append(("DS2", "%s/%s: этап до fall" % (seq, fighter)))
        by = {}
        for r in rows:
            by.setdefault(r["stage"], []).append(r)
        if any(len(v) > 1 for v in by.values()):
            errors.append(("DS2", "%s/%s: этап повторён" % (seq, fighter)))
        if "mark" not in by or "gone" not in by:
            errors.append(("DS2", "%s/%s: нет mark или gone" % (seq, fighter)))
            continue
        summary["death_sets"] += 1
        ft = fall["_t"]
        hero = fall["hero"] == "1"
        settle, still, dissolve = int(fall["settle"]), int(fall["still"]), int(fall["dissolve"])
        gone_t = ft + settle + still + dissolve
        if int(fall["gone"]) != gone_t:
            errors.append(("DS3", "%s/%s: gone=%s ≠ падение + %d" % (seq, fighter, fall["gone"], settle + still + dissolve)))
        mark = by["mark"][0]
        if mark["_t"] - ft != DEATH_MS["mark"] - DEATH_MS["fall"]:
            errors.append(("DS3", "%s/%s: метка через %d мс после падения ≠ %d" % (
                seq, fighter, mark["_t"] - ft, DEATH_MS["mark"] - DEATH_MS["fall"])))
        if by["gone"][0]["_t"] != gone_t:
            errors.append(("DS3", "%s/%s: исчезновение t=%d ≠ %d" % (seq, fighter, by["gone"][0]["_t"], gone_t)))
        if (dissolve > 0) != ("dissolve" in by):
            errors.append(("DS3", "%s/%s: строка dissolve %s при dissolve=%d" % (
                seq, fighter, "есть" if "dissolve" in by else "нет", dissolve)))
        elif dissolve > 0 and by["dissolve"][0]["_t"] != ft + settle + still:
            errors.append(("DS3", "%s/%s: растворение не после оседания и неподвижности" % (seq, fighter)))
        if (dissolve == 0) != (fall["style"] == "none"):
            errors.append(("DS3", "%s/%s: style=%s при dissolve=%d" % (seq, fighter, fall["style"], dissolve)))
        if settle > 0:  # v2-фигура с клипом DeathSettle: таблица F-09
            want_still = DEATH_MS["still_hero"] if hero else DEATH_MS["still_sidekick"]
            want_dissolve = DEATH_MS["dissolve_hero"] if hero else DEATH_MS["dissolve_sidekick"]
            if settle != DEATH_MS["settle"] or still != want_still or dissolve not in (0, want_dissolve):
                errors.append(("DS3", "%s/%s: план %d/%d/%d ≠ F-09 %d/%d/%d (%s)" % (
                    seq, fighter, settle, still, dissolve, DEATH_MS["settle"], want_still, want_dissolve,
                    "герой" if hero else "помощник")))
        if fall["staged"] == "1":
            cft = combat_fall.get((seq, fighter))
            if cft is None:
                errors.append(("DS4", "%s/%s: staged=1 без этапа fall постановки" % (seq, fighter)))
            elif not 0 <= ft - cft <= DEATH_MS["frame_tolerance"]:
                errors.append(("DS4", "%s/%s: падение через %d мс после этапа fall постановки" % (seq, fighter, ft - cft)))
        if hero:
            summary["death_heroes"] += 1
            hero_gone.append((ft, gone_t, seq, fall["staged"] == "1"))
    prev_screen_t = None
    for sc in screens:
        t, due, go = int(sc["t"]), int(sc["due"]), int(sc["gameOver"])
        lo = prev_screen_t if prev_screen_t is not None else -1
        own = [h for h in hero_gone if lo < h[0] <= t]
        if own:
            gone = max(h[1] for h in own)
            want = min(max(go, gone + DEATH_MS["result_after_gone"]), go + DEATH_MS["max_wait"])
            if sc["heroGone"] != str(gone):
                errors.append(("DS5", "строка %d: heroGone=%s ≠ исчезновение героя %d" % (sc["_n"], sc["heroGone"], gone)))
            last = max(own, key=lambda h: h[1])
            if last[3] and last[2] in combat_contact:
                summary["hit_to_screen"].append(t - combat_contact[last[2]])
        else:
            want = go
        if due != want:
            errors.append(("DS5", "строка %d: due=%d ≠ %d (GAME_OVER %d, исчезновение героя + %d)" % (
                sc["_n"], due, want, go, DEATH_MS["result_after_gone"])))
        if not 0 <= t - due <= DEATH_MS["frame_tolerance"]:
            errors.append(("DS5", "строка %d: экран t=%d не в кадр due=%d" % (sc["_n"], t, due)))
        if int(sc["wait"]) != t - go:
            errors.append(("DS5", "строка %d: wait=%s ≠ t − gameOver" % (sc["_n"], sc["wait"])))
        prev_screen_t = t
    return errors, summary


# ----------------------------------------------------------------------------- фикстуры
def run_fixtures(table, fixture_dir=FIXTURES, schema_path=FIXTURE_SCHEMA):
    import jsonschema

    schema = load_json(schema_path)
    results = []
    for path in sorted(Path(fixture_dir).glob("*.json")):
        fx = load_json(path)
        errs = ["schema: " + e.message for e in jsonschema.Draft202012Validator(schema).iter_errors(fx)]
        ok = not errs
        detail = {}
        if ok and fx["kind"] == "scenario":
            got = run_reference(table, fx)
            if got != fx["expect_trace"]:
                ok = False
                diff = [(i, a, b) for i, (a, b) in enumerate(zip(got, fx["expect_trace"])) if a != b][:3]
                detail["trace_mismatch"] = {"got_len": len(got), "want_len": len(fx["expect_trace"]), "first": diff}
            gate_errors, summary = check_trace(fx["expect_trace"], table)
            if gate_errors:
                ok = False
                detail["gate_errors"] = gate_errors
            want = fx.get("expect_summary", {})
            bad = {k: (summary.get(k), v) for k, v in want.items() if summary.get(k) != v}
            if bad:
                ok = False
                detail["summary_mismatch"] = bad
        elif ok and fx["kind"] == "negative-trace":
            gate_errors, _ = check_trace(fx["trace"], table)
            codes = sorted({c for c, _ in gate_errors})
            if codes != sorted(fx["expect_error_codes"]):
                ok = False
                detail["codes"] = {"got": codes, "want": sorted(fx["expect_error_codes"]), "errors": gate_errors}
        results.append({"fixture": path.name, "ok": ok, "errors": errs, **detail})
    return results


# ----------------------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate-table")
    v.add_argument("--table", default=str(TABLE))
    r = sub.add_parser("run-fixtures")
    r.add_argument("--table", default=str(TABLE))
    r.add_argument("--dir", default=str(FIXTURES))
    c = sub.add_parser("check-trace")
    c.add_argument("log")
    c.add_argument("--table", default=str(TABLE))
    c.add_argument("--min-ms-cue", type=int, default=0,
                   help="M5: не меньше N строк `MS-CUE move` (живой прогон MS-AT-28/32)")
    c.add_argument("--min-combat", type=int, default=0,
                   help="C7: не меньше N завершённых постановок боя `CUE combat` (живой бой DE-018/DE-031)")
    c.add_argument("--min-death", type=int, default=0,
                   help="DS6: не меньше N смертей `CUE death` (живая партия до GAME_OVER, DE-019/DE-031)")
    a = ap.parse_args(argv)
    table = load_json(a.table)
    if a.cmd == "validate-table":
        errors = validate_table(table)
        for e in errors:
            print("ERROR", e)
        miss = missing_report(table)
        print("MISSING_REPORT %d" % len(miss))
        for cid, ch, why in miss:
            print("  %s %-4s %s" % (cid, ch, why))
        print("CUE_TABLE", "PASS" if not errors else "FAIL", "cues", len(table["cues"]))
        return 0 if not errors else 1
    if a.cmd == "run-fixtures":
        res = run_fixtures(table, a.dir)
        for x in res:
            print("FIXTURE", "OK " if x["ok"] else "BAD", x["fixture"], "" if x["ok"] else json.dumps(
                {k: v for k, v in x.items() if k not in ("fixture", "ok")}, ensure_ascii=False))
        bad = sum(1 for x in res if not x["ok"])
        print("CUE_FIXTURES", "PASS" if not bad and res else "FAIL", "fixtures", len(res), "bad", bad)
        return 0 if not bad and res else 1
    lines = Path(a.log).read_text(encoding="utf-8", errors="replace").splitlines()
    errors, summary = check_trace(lines, table)
    if summary["ms_cue"] < a.min_ms_cue:
        errors.append(("M5", "строк MS-CUE %d < %d" % (summary["ms_cue"], a.min_ms_cue)))
    if summary["combat_sets"] < a.min_combat:
        errors.append(("C7", "постановок боя %d < %d" % (summary["combat_sets"], a.min_combat)))
    if summary["death_sets"] < a.min_death:
        errors.append(("DS6", "смертей %d < %d" % (summary["death_sets"], a.min_death)))
    for code, text in errors:
        print("GATE", code, text)
    print("CUE_TRACE", "PASS" if not errors else "FAIL", json.dumps(summary))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
