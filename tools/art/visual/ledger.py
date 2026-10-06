"""Credits ledger of the visual chat: docs/game-design/visual/credits-ledger.json (schema 07-prompt-templates.md 4.2).

  python tools/art/visual/ledger.py add --task EN-03 --template T-SYNTX-UPSCALE --service SYNTX
      --model "magnific/precision_v2 2x" --units "1 upscale 2x" --quoted 12 --before 173.771 --after 161.771
      [--service-task-id ID] [--seed N] --prompt-file docs/game-design/visual/06-tasks/prompts/EN-03.syntx.txt
      --result scraped-data/derived/env-u16-marmoreal-codex/marmoreal-extended-2x.png [--status ok|failed|refunded]
      [--note TEXT] [--date ISO]
  python tools/art/visual/ledger.py add --task IC-36 --template T-CODEX-2D --service Codex --model "Codex app"
      --image-gen 8 --prompt-file docs/game-design/visual/06-tasks/prompts/IC-36.codex.md
      --result art/imagegen/hud-icons-vr44-codex/
  python tools/art/visual/ledger.py terms --service SYNTX --model "Magnific Precision v2" --url URL [--checked DATE]
  python tools/art/visual/ledger.py check [--balance B --next-cost X --next-kind image|video|upscale]

Rules (07 4.1-4.3, 05 5.1-5.3): a row right after every spend, before the next one; no spend without a task card;
balance_before is always a fresh get-balance (a gap to the previous balance_after is somebody else's spend, e.g. the
audio chat - not ours, not written); cost = balance_before - balance_after; a difference to quoted above 0.5 goes to
note; Codex: one row per package, units "пакет, N генераций image_gen", cost and balances null. Writes happen under
a lock file, through a temp file and os.replace, JSON indent 2, ensure_ascii False; totals are recomputed on every
write.

check verifies totals against the rows and the limits: ВР-04 (SYNTX <= 300 tokens until 2026-10-28, stop when the
balance before a run is below 20, Tripo <= 3000 credits, no purchases), ВР-PL10 (visual SYNTX cap 54 without a new
decision), ВР-PR04 (one run: image 8, video 10, upscale 12), ВР-05 (providerTerms row before the first spend of a
model). With --balance/--next-cost it is the pre-flight check before a SYNTX run. Exit code 1 on any error.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from visual_common import (  # noqa: E402
    LEDGER_REL,
    TEMPLATE_ID_RE,
    TEMPLATES_REL,
    VisualError,
    load_cards,
    repo_root,
    utf8_console,
)

SCHEMA = "unmatched.visual-credits-ledger/1"
SERVICES = {"syntx": "SYNTX", "tripo": "Tripo", "codex": "Codex"}
STATUSES = ("ok", "failed", "refunded")
ENTRY_KEYS = ("date", "service", "model", "template", "task_id", "units", "quoted", "cost", "balance_before",
              "balance_after", "service_task_id", "seed", "prompt_file", "result_path", "status", "note")
NOTE_DELTA = 0.5          # 07 4.2: |cost - quoted| above this goes to note
EPS = 0.0005
DEFAULT_LIMITS = {        # used only when the ledger file lacks a value (the file is the source)
    "syntx_tokens": 300, "syntx_until": "2026-10-28", "stop_balance": 20, "visual_cap": 54,
    "per_run": {"image": 8, "video": 10, "upscale": 12}, "tripo_credits": 3000,
}


# ---------------------------------------------------------------- io

def ledger_path(root: Path, override: Path | None) -> Path:
    return Path(override) if override else root / LEDGER_REL


def read_ledger(path: Path) -> tuple[dict, str]:
    if not path.is_file():
        raise VisualError(f"ledger not found: {path.as_posix()}")
    raw = path.read_bytes().decode("utf-8")
    nl = "\r\n" if "\r\n" in raw else "\n"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise VisualError(f"ledger is not valid JSON: {path.as_posix()}: {e}") from e
    if data.get("schema") != SCHEMA:
        raise VisualError(f"ledger schema is {data.get('schema')!r}, expected {SCHEMA!r}")
    return data, nl


class LedgerLock:
    """Exclusive lock file next to the ledger (<ledger>.lock), created with O_EXCL; waits up to timeout seconds."""

    def __init__(self, path: Path, timeout: float = 30.0):
        self.lock = Path(str(path) + ".lock")
        self.timeout = timeout
        self.fd = None

    def __enter__(self):
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                self.fd = os.open(self.lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self.fd, f"pid {os.getpid()} {dt.datetime.now().isoformat(timespec='seconds')}\n".encode())
                return self
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise VisualError(f"ledger lock is busy for {self.timeout:g} s: {self.lock.as_posix()} "
                                      "(another writer is running; delete the lock only if no writer is alive)")
                time.sleep(0.1)

    def __exit__(self, *exc):
        if self.fd is not None:
            os.close(self.fd)
        try:
            os.unlink(self.lock)
        except FileNotFoundError:
            pass


def write_ledger(path: Path, data: dict, nl: str) -> None:
    text = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").replace("\n", nl)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


# ---------------------------------------------------------------- model

def limits_of(data: dict) -> dict:
    lim = data.get("limits") or {}
    sx = lim.get("syntx") or {}
    tr = lim.get("tripo") or {}
    per_run = dict(DEFAULT_LIMITS["per_run"])
    per_run.update({k: v for k, v in (sx.get("perRun") or {}).items() if k in per_run})
    return {
        "syntx_tokens": sx.get("tokens", DEFAULT_LIMITS["syntx_tokens"]),
        "syntx_until": sx.get("until", DEFAULT_LIMITS["syntx_until"]),
        "stop_balance": sx.get("stopBalance", DEFAULT_LIMITS["stop_balance"]),
        "visual_cap": sx.get("visualCap", DEFAULT_LIMITS["visual_cap"]),
        "per_run": per_run,
        "tripo_credits": tr.get("credits", DEFAULT_LIMITS["tripo_credits"]),
        "tripo_until": tr.get("until", DEFAULT_LIMITS["syntx_until"]),
    }


def compute_totals(entries: list[dict]) -> dict:
    def spent(service):
        return round(sum(e["cost"] for e in entries if e.get("service") == service
                         and isinstance(e.get("cost"), (int, float))), 3)
    return {"syntx_spent": spent("SYNTX"), "tripo_spent": spent("Tripo"),
            "codex_packages": sum(1 for e in entries if e.get("service") == "Codex")}


def run_kind(template: str) -> str | None:
    if template == "T-SYNTX-UPSCALE":
        return "upscale"
    if template.startswith("T-SYNTX-VID"):
        return "video"
    if template.startswith("T-SYNTX-IMG"):
        return "image"
    return None


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def terms_cover(terms: list[dict], service: str, model: str) -> bool:
    m = _norm(model)
    for t in terms:
        if t.get("service") != service:
            continue
        names = [_norm(t.get("model", "")), _norm(t.get("ledgerModel", ""))]
        if any(n and (n in m or m in n) for n in names):
            return True
    return False


def _date_part(iso: str) -> str:
    return (iso or "")[:10]


def check_ledger(data: dict, cards: dict | None, templates_md: str | None,
                 preflight: dict | None = None) -> tuple[list[str], list[str]]:
    """(errors, warnings) of the whole ledger, plus the pre-flight of the next SYNTX run when given."""
    errors: list[str] = []
    warnings: list[str] = []
    lim = limits_of(data)
    entries = data.get("entries")
    if not isinstance(entries, list):
        return ["'entries' is not a list"], warnings
    terms = data.get("providerTerms") or []
    seen_ids = set()
    for n, e in enumerate(entries, 1):
        tag = f"entry {n} ({e.get('task_id', '?')} {e.get('service', '?')} {e.get('date', '?')})"
        missing = [k for k in ENTRY_KEYS if k not in e]
        if missing:
            errors.append(f"{tag}: missing fields {', '.join(missing)}")
            continue
        svc = e["service"]
        if svc not in SERVICES.values():
            errors.append(f"{tag}: unknown service {svc!r}")
        if e["status"] not in STATUSES:
            errors.append(f"{tag}: status {e['status']!r} not in {STATUSES}")
        if not e["task_id"]:
            errors.append(f"{tag}: task_id is empty (no spend without a card, 07 4.2)")
        elif cards is not None and e["task_id"] not in cards:
            errors.append(f"{tag}: task_id {e['task_id']} is not a card in 06-tasks")
        if not TEMPLATE_ID_RE.match(e["template"] or ""):
            errors.append(f"{tag}: template {e['template']!r} is not a template id")
        elif templates_md is not None and e["template"] not in templates_md:
            errors.append(f"{tag}: template {e['template']} is not described in {TEMPLATES_REL}")
        if e["service_task_id"]:
            if e["service_task_id"] in seen_ids:
                errors.append(f"{tag}: service_task_id {e['service_task_id']} appears twice")
            seen_ids.add(e["service_task_id"])
        if e["seed"] is not None and not isinstance(e["seed"], int):
            errors.append(f"{tag}: seed must be an integer or null")
        if svc == "Codex":
            for k in ("quoted", "cost", "balance_before", "balance_after"):
                if e[k] is not None:
                    errors.append(f"{tag}: Codex rows keep {k} null (subscription, 07 4.2)")
            if not re.search(r"пакет", e["units"] or ""):
                warnings.append(f"{tag}: Codex units should read 'пакет, N генераций image_gen'")
            continue
        if svc not in ("SYNTX", "Tripo"):
            continue
        b0, b1, cost = e["balance_before"], e["balance_after"], e["cost"]
        if not all(isinstance(v, (int, float)) for v in (b0, b1, cost)):
            errors.append(f"{tag}: balance_before, balance_after and cost must be numbers")
            continue
        if abs(round(b0 - b1, 3) - cost) > EPS:
            errors.append(f"{tag}: cost {cost} != balance_before - balance_after = {round(b0 - b1, 3)}")
        q = e["quoted"]
        if not isinstance(q, (int, float)):
            errors.append(f"{tag}: quoted (price before the run) must be a number")
        elif abs(cost - q) > NOTE_DELTA and not e["note"]:
            errors.append(f"{tag}: cost {cost} differs from quoted {q} by more than {NOTE_DELTA} without a note")
        if svc == "SYNTX":
            if b0 < lim["stop_balance"]:
                errors.append(f"{tag}: the run started at balance {b0} < stop balance {lim['stop_balance']} (ВР-04)")
            kind = run_kind(e["template"])
            cap = lim["per_run"].get(kind) if kind else None
            price = q if isinstance(q, (int, float)) else cost
            if cap is not None and price > cap:
                warnings.append(f"{tag}: one {kind} run at {price} is above the ВР-PR04 cap {cap}; "
                                "allowed only by a line in the card's budget")
            if _date_part(e["date"]) > lim["syntx_until"] and cost > 0:
                errors.append(f"{tag}: SYNTX spend after {lim['syntx_until']} needs a new decision (ВР-04)")
        if cost > 0 and not terms_cover(terms, svc, e["model"]):
            errors.append(f"{tag}: no providerTerms row for {svc} {e['model']!r} (ВР-05: before the first spend)")

    totals = compute_totals(entries)
    stored = data.get("totals") or {}
    for k, v in totals.items():
        if stored.get(k) != v:
            errors.append(f"totals.{k} = {stored.get(k)!r}, rows give {v!r}")

    sx_window = round(sum(e["cost"] for e in entries if e.get("service") == "SYNTX"
                          and isinstance(e.get("cost"), (int, float))
                          and _date_part(e.get("date", "")) <= lim["syntx_until"]), 3)
    if totals["syntx_spent"] > lim["visual_cap"] + EPS:
        errors.append(f"SYNTX spent {totals['syntx_spent']} > visual cap {lim['visual_cap']} (ВР-PL10: new decision first)")
    if sx_window > lim["syntx_tokens"] + EPS:
        errors.append(f"SYNTX spent {sx_window} until {lim['syntx_until']} > {lim['syntx_tokens']} (ВР-04)")
    if totals["tripo_spent"] > lim["tripo_credits"] + EPS:
        errors.append(f"Tripo spent {totals['tripo_spent']} > {lim['tripo_credits']} credits (ВР-04)")
    if totals["tripo_spent"] > 0:
        warnings.append(f"Tripo spent {totals['tripo_spent']}: the roster after MVP is out of scope (ВР-18)")

    if preflight:
        b, x, kind = preflight["balance"], preflight["next_cost"], preflight.get("next_kind")
        today = preflight.get("today") or dt.date.today().isoformat()
        if b < lim["stop_balance"]:
            errors.append(f"pre-flight: balance {b} < stop balance {lim['stop_balance']}: do not run (ВР-04)")
        elif b - x < lim["stop_balance"]:
            warnings.append(f"pre-flight: balance after the run would be {round(b - x, 3)} < {lim['stop_balance']} "
                            "(for a planned chain this is plan B, ВР-PL10)")
        if kind:
            cap = lim["per_run"].get(kind)
            if cap is None:
                errors.append(f"pre-flight: unknown run kind {kind!r}")
            elif x > cap:
                errors.append(f"pre-flight: price {x} > ВР-PR04 cap {cap} for one {kind} run: cancel the run")
        if totals["syntx_spent"] + x > lim["visual_cap"] + EPS:
            errors.append(f"pre-flight: spent {totals['syntx_spent']} + {x} > visual cap {lim['visual_cap']} (ВР-PL10)")
        if sx_window + x > lim["syntx_tokens"] + EPS:
            errors.append(f"pre-flight: spent {sx_window} + {x} > {lim['syntx_tokens']} (ВР-04)")
        if today > lim["syntx_until"]:
            errors.append(f"pre-flight: today {today} is after {lim['syntx_until']} (ВР-04 window closed)")
    return errors, warnings


# ---------------------------------------------------------------- commands

def _num(s: str | None) -> float | None:
    if s is None:
        return None
    try:
        v = float(str(s).replace(",", "."))
    except ValueError as e:
        raise VisualError(f"not a number: {s!r}") from e
    return int(v) if v.is_integer() and "." not in str(s) and "," not in str(s) else v


def _repo_path(root: Path, s: str | None) -> str:
    if not s:
        return ""
    p = s.replace("\\", "/")
    try:
        return Path(p).resolve().relative_to(root.resolve()).as_posix() if Path(p).is_absolute() else p
    except ValueError:
        return p


def make_entry(a, root: Path) -> dict:
    svc = SERVICES.get((a.service or "").strip().lower())
    if not svc:
        raise VisualError(f"--service must be one of {', '.join(SERVICES.values())}")
    if a.status not in STATUSES:
        raise VisualError(f"--status must be one of {STATUSES}")
    if not TEMPLATE_ID_RE.match(a.template or ""):
        raise VisualError(f"--template {a.template!r} is not a template id (T-...)")
    quoted, before, after = _num(a.quoted), _num(a.before), _num(a.after)
    units = a.units
    note = a.note or ""
    if svc == "Codex":
        if any(v is not None for v in (quoted, before, after)):
            raise VisualError("Codex rows keep quoted, cost and balances null (subscription, 07 4.2)")
        if not units:
            if a.image_gen is None:
                raise VisualError("Codex row needs --units or --image-gen N (units 'пакет, N генераций image_gen')")
            units = f"пакет, {a.image_gen} генераций image_gen"
        cost = None
    else:
        if before is None or after is None:
            raise VisualError(f"{svc} row needs --before and --after (fresh get-balance before and after the run)")
        if quoted is None:
            raise VisualError(f"{svc} row needs --quoted (price from get-model-info / the UI before the run)")
        if not units:
            raise VisualError(f"{svc} row needs --units (e.g. '1 upscale 2x')")
        cost = round(before - after, 3)
        if abs(cost - quoted) > NOTE_DELTA:
            auto = f"cost {cost} differs from quoted {quoted} by {round(abs(cost - quoted), 3)} (> {NOTE_DELTA})"
            note = f"{note}; {auto}" if note else auto
    seed = None
    if a.seed not in (None, "", "null"):
        try:
            seed = int(a.seed)
        except ValueError as e:
            raise VisualError(f"--seed must be an integer or null, got {a.seed!r}") from e
    date = a.date or dt.datetime.now().astimezone().isoformat(timespec="seconds")
    return {
        "date": date, "service": svc, "model": a.model, "template": a.template, "task_id": a.task,
        "units": units, "quoted": quoted, "cost": cost, "balance_before": before, "balance_after": after,
        "service_task_id": a.service_task_id or None, "seed": seed,
        "prompt_file": _repo_path(root, a.prompt_file), "result_path": _repo_path(root, a.result),
        "status": a.status, "note": note,
    }


def cmd_add(a, root: Path) -> int:
    cards = load_cards(root)
    if a.task not in cards:
        raise VisualError(f"--task {a.task!r} is not a card in 06-tasks (no spend without a card, 07 4.2)")
    md = (root / TEMPLATES_REL).read_text(encoding="utf-8") if (root / TEMPLATES_REL).is_file() else None
    if md is not None and a.template not in md:
        raise VisualError(f"--template {a.template} is not described in {TEMPLATES_REL}")
    entry = make_entry(a, root)
    if entry["prompt_file"] and not (root / entry["prompt_file"]).exists():
        print(f"ledger: WARNING: prompt file not found: {entry['prompt_file']}", file=sys.stderr)
    path = ledger_path(root, a.ledger)
    with LedgerLock(path, a.lock_timeout):
        data, nl = read_ledger(path)
        entries = data.setdefault("entries", [])
        sid = entry["service_task_id"]
        if sid and any(e.get("service_task_id") == sid for e in entries):
            raise VisualError(f"service_task_id {sid} is already in the ledger")
        entries.append(entry)
        data["totals"] = compute_totals(entries)
        if str(data.get("status", "")).startswith("пустой"):
            data["status"] = f"ведётся с {entry['date'][:10]}"
        write_ledger(path, data, nl)
    errors, warnings = check_ledger(data, cards, md)
    for w in warnings + errors:  # the spend is recorded anyway: a spend is never hidden
        print(f"ledger: WARNING after add: {w}", file=sys.stderr)
    t = data["totals"]
    print(f"ledger: added {entry['service']} {entry['task_id']} cost={entry['cost']}; totals syntx_spent="
          f"{t['syntx_spent']} tripo_spent={t['tripo_spent']} codex_packages={t['codex_packages']}")
    return 0


def cmd_terms(a, root: Path) -> int:
    svc = SERVICES.get((a.service or "").strip().lower())
    if not svc:
        raise VisualError(f"--service must be one of {', '.join(SERVICES.values())}")
    row = {"service": svc, "model": a.model, "url": a.url, "checked": a.checked or dt.date.today().isoformat()}
    if a.ledger_model:
        row["ledgerModel"] = a.ledger_model
    path = ledger_path(root, a.ledger)
    with LedgerLock(path, a.lock_timeout):
        data, nl = read_ledger(path)
        terms = data.setdefault("providerTerms", [])
        if any(t.get("service") == svc and t.get("model") == a.model and t.get("url") == a.url for t in terms):
            raise VisualError(f"providerTerms already has {svc} {a.model!r} {a.url}")
        terms.append(row)
        write_ledger(path, data, nl)
    print(f"ledger: providerTerms + {svc} {a.model!r} checked {row['checked']}")
    return 0


def cmd_check(a, root: Path) -> int:
    data, _ = read_ledger(ledger_path(root, a.ledger))
    cards = load_cards(root)
    md = (root / TEMPLATES_REL).read_text(encoding="utf-8") if (root / TEMPLATES_REL).is_file() else None
    pre = None
    given = [v is not None for v in (a.balance, a.next_cost)]
    if any(given) and not all(given):
        raise VisualError("pre-flight needs both --balance and --next-cost")
    if all(given):
        pre = {"balance": _num(a.balance), "next_cost": _num(a.next_cost), "next_kind": a.next_kind,
               "today": a.today}
    errors, warnings = check_ledger(data, cards, md, pre)
    t = compute_totals(data.get("entries") or [])
    lim = limits_of(data)
    print(f"ledger: {len(data.get('entries') or [])} rows; syntx_spent={t['syntx_spent']} of visual cap "
          f"{lim['visual_cap']} (ВР-PL10) and {lim['syntx_tokens']} until {lim['syntx_until']} (ВР-04); "
          f"tripo_spent={t['tripo_spent']} of {lim['tripo_credits']}; codex_packages={t['codex_packages']}")
    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    print("ledger: check " + ("FAILED" if errors else "OK"))
    return 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", type=Path, help=argparse.SUPPRESS)
    ap.add_argument("--ledger", type=Path, help=f"ledger file (default {LEDGER_REL})")
    ap.add_argument("--lock-timeout", type=float, default=30.0, help="seconds to wait for the lock file")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ad = sub.add_parser("add", help="append one spend row")
    ad.add_argument("--task", required=True, help="card id from 06-tasks")
    ad.add_argument("--template", required=True, help="template id of 07, e.g. T-SYNTX-UPSCALE")
    ad.add_argument("--service", required=True, help="SYNTX, Tripo or Codex")
    ad.add_argument("--model", required=True)
    ad.add_argument("--units")
    ad.add_argument("--image-gen", type=int, help="Codex: number of image_gen generations in the package")
    ad.add_argument("--quoted", help="price before the run")
    ad.add_argument("--before", help="fresh balance before the run")
    ad.add_argument("--after", help="fresh balance after the run")
    ad.add_argument("--service-task-id")
    ad.add_argument("--seed")
    ad.add_argument("--prompt-file")
    ad.add_argument("--result")
    ad.add_argument("--status", default="ok", choices=STATUSES)
    ad.add_argument("--note")
    ad.add_argument("--date", help="ISO timestamp (default now, local offset)")

    te = sub.add_parser("terms", help="append a providerTerms row (ВР-05)")
    te.add_argument("--service", required=True)
    te.add_argument("--model", required=True)
    te.add_argument("--url", required=True)
    te.add_argument("--checked", help="ISO date (default today)")
    te.add_argument("--ledger-model", help="model string as written in the rows, if it differs")

    ch = sub.add_parser("check", help="verify totals and limits; with --balance/--next-cost also the next run")
    ch.add_argument("--balance", help="fresh get-balance before the next run")
    ch.add_argument("--next-cost", help="quoted price of the next run (or the planned chain)")
    ch.add_argument("--next-kind", choices=("image", "video", "upscale"))
    ch.add_argument("--today", help=argparse.SUPPRESS)

    a = ap.parse_args(argv)
    utf8_console()
    root = (a.root or repo_root()).resolve()
    try:
        return {"add": cmd_add, "terms": cmd_terms, "check": cmd_check}[a.cmd](a, root)
    except VisualError as e:
        print(f"ledger: ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
