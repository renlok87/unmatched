#!/usr/bin/env python3
"""Контракт FS08CueDispatcher без движка: валидатор таблицы, эталонная модель и гейт трассы.

Спецификация: docs/unreal/contracts/cue-dispatcher/CUE-DISPATCHER.md.
Данные: docs/unreal/contracts/cue-dispatcher/cue-table.json (+ cue-table.schema.json).
Фикстуры без мира: docs/unreal/contracts/cue-dispatcher/fixtures/*.json.

Команды (из корня репозитория):
  python tools/s08/cue_contract/cue_contract.py validate-table [--table P]   схема + семантика + сверка с 07; missing-report
  python tools/s08/cue_contract/cue_contract.py run-fixtures [--dir D]       эталонная модель против expect_trace и гейт
  python tools/s08/cue_contract/cue_contract.py check-trace <log> [--table P] [--min-ms-cue N]
                                                                           гейт трассы `CUE fx … result=` и `MS-CUE move …`
                                                                           (move-selection 04 §9, MS-AT-28) реального лога

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


def _num(text):
    parts = text.strip().split()
    return int(parts[0]) if parts and parts[0].isdigit() else None


# ----------------------------------------------------------------------------- CUE-007: расписание перемещения
MOVE_PARAM_KEYS = ("duration_per_step_ms", "cap_subject_ms", "cap_seq_ms", "min_step_ms", "overlap", "place_ms")
SPEED_MUL = {"fast": 0.5, "normal": 1.0, "slow": 1.5}
MS_CUE_SOURCES = ("trail", "canonical", "straight")
MS_CUE_KINDS = ("move", "place")


def move_params(row):
    """Параметры расписания (move-selection 04 §6.3) из строки CUE с duration_per_step_ms (CUE-007)."""
    return {k: row[k] for k in MOVE_PARAM_KEYS}


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


def validate_table(table, schema=None, csv07=CSV07, rig_contract=RIG_CONTRACT):
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
        dur = c["duration_ms"] or 0
        if c["blocks_input"] and dur > MAX_BLOCKING_MS and c["on_new_event"] != "none":
            errors.append("%s: блокирует ввод %d мс > %d (P3) и не терминальный" % (cid, dur, MAX_BLOCKING_MS))
        for ch, key in (("vfx", "system"), ("sfx", "sound"), ("clip", "sequence")):
            a = c.get(ch)
            if not a:
                continue
            path = a.get(key)
            if a["status"] == "present" and not path:
                errors.append("%s: %s.status present без пути %s" % (cid, ch, key))
            if a["status"] == "missing" and path:
                errors.append("%s: %s.status missing, но путь задан" % (cid, ch))
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
    def _asset(self, cid, channel):
        row = self.rows[cid]
        spec = row.get(channel)
        if not spec:
            return "none"
        key = {"vfx": "system", "sfx": "sound", "clip": "sequence"}[channel]
        path = self.present.get(cid, {}).get(channel) or spec.get(key)
        if not path or path in self.unloadable:
            return "missing"
        return short_name(path)

    def _duration(self, row, event):
        if row.get("duration_per_step_ms"):
            # CUE-007: расписание 04 §6.3 — по всем перемещениям seq (seq_moves + order) или по одному этому
            moves = event.get("seq_moves") or [{"kind": event.get("move_kind", "move"), "steps": int(event.get("steps", 1))}]
            dur = int(round(move_schedule(moves, move_params(row))[int(event.get("order", 0))]["ms"]))
        else:
            dur = row["duration_ms"] or 0
        rm = row["reduced_motion"]
        reduced = self.reduced and rm["mode"] != "keep"
        if reduced:
            dur = 0 if rm["mode"] == "snap" else min(dur, rm["max_ms"])
        return dur, reduced

    def _done(self, inst, t, cut):
        self.lines.append("CUE fx done id=%s subject=%s seq=%s t=%d ms=%d cut=%s"
                          % (inst["id"], inst["subject"], inst["seq"], t, t - inst["start"], cut))

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
            if (self.recovered_seq is not None and seq <= self.recovered_seq) or (
                    self.high_water is not None and seq < self.high_water):
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
        vfx, clip = self._asset(cid, "vfx"), self._asset(cid, "clip")
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
                    act.append({"subject": subject, "seq": seq_tok, "end": t + dur})
                    self.sfx_last[cid] = t
        mat = (row.get("material") or {}).get("cpd_param", "none")
        v = row.get("vfx")
        socket = v["socket"] if v and v["attach"] == "socket" else "-"
        result = "fallback" if "missing" in (vfx, sfx, clip) else "spawned"
        self.lines.append(head + " vfx=%s sfx=%s clip=%s mat=%s socket=%s reduced=%d result=%s"
                          % (vfx, sfx, clip, mat, socket, int(reduced), result))
        inst = {"id": cid, "subject": subject, "seq": seq_tok, "start": t, "end": t + dur, "order": len(self.lines)}
        if dur == 0:
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
            row = rows[cid]
            rm = row["reduced_motion"]
            if inst["reduced"] and rm["mode"] == "shorten" and ms > rm["max_ms"]:
                errors.append(("G4", "строка %d: сокращённая анимация %d мс > %d" % (n, ms, rm["max_ms"])))
            if inst["reduced"] and rm["mode"] == "snap" and ms != 0:
                errors.append(("G4", "строка %d: snap длится %d мс" % (n, ms)))
            if row["blocks_input"] and ms > MAX_BLOCKING_MS and row["on_new_event"] != "none":
                errors.append(("G5", "строка %d: блокирующий CUE %s длился %d мс" % (n, cid, ms)))
            inst["end"] = t
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
    for code, text in errors:
        print("GATE", code, text)
    print("CUE_TRACE", "PASS" if not errors else "FAIL", json.dumps(summary))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
