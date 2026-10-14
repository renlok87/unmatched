"""Шаг 7a.2: параллельные приёмщики клипов (Sol 6.1 xhigh, codex exec) по каталогу цикла prep_acceptance.py + validate_card.

Замена run-acceptor.ps1, который этап 6 должен был оставить рядом с заготовками, а исполнитель 7a писал руками
(находка C51 фигуры-проверки Beowulf 2026-10-14). Вход — каталог цикла <E> = <asset-dir>/evidence/acceptance-anim/
<YYYYMMDD>-rN (prep_acceptance.py): в <E>/<Clip>/ лежат acceptor-prompt.md и frames/. На клип:
  1. промпт: без незаполненных {{…}}; константа `executor_session_id "…"` — фактический id исполнителя клипов
     (--executor-session-id, RA-21; C32/C55: заготовка этапа 6 несла выдуманный «agent:stage6-<key>» вместо имени
     агента). Отличается — промпт переписывается на месте (запись в acceptor-launch.json); не дан — WARNING;
  2. изображения: каждый файл <E>/<Clip>/frames/ (*.jpg, *.png) и каждый существующий файл .png/.jpg, путь которого
     (от корня репо) назван в промпте вне frames/ — образец библиотеки (art/animation-refs/…/contact-sheet-2fps.png),
     лист концепта приёмки модели, вид концепта, эталон качества: ровно то, что run-acceptor.ps1 пилота и Beowulf
     собирали руками; --image — ещё файлы, --no-prompt-images — только frames/;
  3. codex exec --ignore-user-config -m gpt-6.1-sol -c model_reasoning_effort="xhigh" -c windows.sandbox="unelevated"
     -s read-only --output-schema tools/art/acceptance/asset-acceptance-2.output-anim.schema.json -o card.json --json
     (acceptance-and-blender.md §8.4), промпт — stdin UTF-8; события — acceptor-events.jsonl, stderr —
     acceptor-stderr.txt; сбой песочницы (helper_unknown_error) — environment_failure, карточка не в счёт;
  4. acceptor.session_id "codex:pending" → "codex:<thread_id>" из thread.started (как sheet_acceptance.py); проверка
     card.executor_session_id = константе промпта;
  5. validate_card.py <card> --print-verdict --check-files → validator-output.txt; код 0 — карточка верна, 3 — pass
     8,0–8,4: нужен второй приёмщик (.claude/workflows/second-acceptor.js, acceptance-and-blender.md §8.5), 1 — нет.
Клипы идут параллельно (--workers, по умолчанию все). Итог — <E>/acceptors-run.json и таблица в stdout.

    python tools/tripo-pipeline/ue7a/run_clip_acceptors.py --evidence <asset-dir>/evidence/acceptance-anim/20261014-r1 \
        --executor-session-id "claude-code:<uuid>/agent:<имя агента этапа 6>" [--clips Idle,LungeAttack] [--dry-run]
    … --validate-only                 # только validate_card по готовым карточкам (без Codex)
    … --tag=-b [--force]              # повтор: card-b.json и т. д.; --force — перезаписать карточку

Траты: каждая приёмка — сессия Codex (квота ChatGPT, RC-12); кредиты Tripo/SYNTX не расходуются.
Код выхода: 0 — все карточки верны (validate 0 или 3), 1 — есть неверная карточка / нет карточки / сбой окружения /
таймаут / чужой executor_session_id, 2 — ошибка входа (нет каталога, промпта, кадров, codex.exe; карточка уже есть).
"""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ue7a as c  # noqa: E402

SCHEMA = "tools/art/acceptance/asset-acceptance-2.output-anim.schema.json"
VALIDATE = "tools/art/acceptance/validate_card.py"
EXEC_RE = re.compile(r'executor_session_id "([^"]*)"')
IMG_RE = re.compile(r'(?<![\w./-])((?:art|docs|tools|unreal)/[^\s"\'`,;()\[\]{}<>]+?\.(?:png|jpe?g))(?![\w-])', re.I)
FRAME_EXT = (".jpg", ".jpeg", ".png")
SESSION_RE = re.compile(r"^[a-z][a-z0-9-]*:\S+$")
SECOND = ".claude/workflows/second-acceptor.js (acceptance-and-blender.md §8.5)"


class InputError(Exception):
    pass


def now() -> str:
    return dt.datetime.now().astimezone().replace(microsecond=0).isoformat()


def default_exe() -> str | None:
    """Новейший codex.exe приложения Codex (тот, что прошёл пробу exec, concept-sheet.md §5.2)."""
    base = Path(os.environ.get("LOCALAPPDATA", "")) / "OpenAI" / "Codex" / "bin"
    exes = sorted(base.glob("*/codex.exe"), key=lambda p: p.stat().st_mtime, reverse=True) if base.is_dir() else []
    return str(exes[0]) if exes else None


def prompt_path(cdir: Path, tag: str) -> Path:
    p = cdir / f"acceptor-prompt{tag}.md"
    return p if p.is_file() or not tag else cdir / "acceptor-prompt.md"


def executor_fix(text: str, want: str | None) -> tuple[str, dict]:
    """(текст, запись) — константа executor_session_id промпта, при --executor-session-id переписанная на факт."""
    found = EXEC_RE.findall(text)
    if len(found) != 1:
        raise InputError(f"в промпте {len(found)} констант executor_session_id \"…\" (нужна одна)")
    rec = {"prompt": found[0], "given": want, "rewritten": False}
    if want and want != found[0]:
        text = text.replace(f'executor_session_id "{found[0]}"', f'executor_session_id "{want}"')
        rec["rewritten"] = True
    rec["used"] = want or found[0]
    return text, rec


def prompt_images(text: str, repo: Path, frames_dir: Path, have: set) -> list[Path]:
    """Существующие .png/.jpg, названные в промпте путём от корня репо, кроме кадров каталога frames/ (по имени)."""
    out, seen = [], set()
    fd = frames_dir.resolve()
    for m in IMG_RE.finditer(text):
        p = (repo / m.group(1)).resolve()
        if p in seen or not p.is_file() or p.parent == fd or p.name in have:
            continue
        seen.add(p)
        out.append(p)
    return out


def codex_args(exe: str, repo: Path, card: Path, images: list, model: str, effort: str) -> list:
    cmd = [sys.executable, exe] if exe.lower().endswith(".py") else [exe]
    cmd += ["exec", "--ignore-user-config", "-m", model, "-c", f'model_reasoning_effort="{effort}"', "-c",
            'windows.sandbox="unelevated"', "-s", "read-only", "-C", str(repo), "--skip-git-repo-check",
            "--output-schema", str(repo / SCHEMA), "-o", str(card), "--json"]
    for img in images:
        cmd += ["-i", str(img)]
    return cmd + ["--", "-"]


def events(path: Path) -> list:
    out = []
    if path.is_file():
        for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def env_failures(evs: list) -> list:
    """Сбой песочницы (не попытка приёмки): команды с helper_unknown_error / Failed to create unified exec process."""
    bad = []
    for x in evs:
        it = x.get("item") or {}
        out = it.get("aggregated_output", "") or ""
        if it.get("type") == "command_execution" and it.get("status") == "failed" and (
                "helper_unknown_error" in out or out.startswith("Failed to create unified exec process")):
            bad.append(x)
    return bad


def run_validate(card: Path, repo: Path) -> tuple[int, str, str]:
    """validate_card.py --print-verdict --check-files → (код, stdout, stderr)."""
    p = subprocess.run([sys.executable, "-X", "utf8", str(repo / VALIDATE), str(card), "--print-verdict",
                        "--check-files"], cwd=repo, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return p.returncode, p.stdout, p.stderr


def run_codex(cmd: list, prompt: str, cwd: Path, ev: Path, err: Path, timeout: int) -> tuple[int | None, int]:
    """codex exec с промптом на stdin; (код | None при таймауте, pid)."""
    with ev.open("wb") as out, err.open("wb") as er:
        proc = subprocess.Popen(cmd, cwd=cwd, stdin=subprocess.PIPE, stdout=out, stderr=er,
                                env=dict(os.environ, PYTHONIOENCODING="utf-8"),
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            proc.communicate(prompt.encode("utf-8"), timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            return None, proc.pid
    return proc.returncode, proc.pid


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


def plan_clip(e: Path, clip: str, a, repo: Path) -> dict:
    cdir = e / clip
    pp = prompt_path(cdir, a.tag)
    if not pp.is_file():
        raise InputError(f"{clip}: нет промпта {pp} (prep_acceptance.py)")
    text = pp.read_text(encoding="utf-8-sig")
    nl = "\r\n" if b"\r\n" in pp.read_bytes() else "\n"  # переписанный промпт — с концами строк файла
    left = sorted(set(re.findall(r"\{\{[A-Z_0-9]+\}\}", text)))
    if left:
        raise InputError(f"{clip}: в промпте не заполнены {left} (prep_acceptance.py)")
    text, exe_rec = executor_fix(text, a.executor_session_id)
    card = cdir / f"card{a.tag}.json"
    if a.validate_only:
        if not card.is_file():
            raise InputError(f"{clip}: --validate-only, а карточки {card.name} нет")
        return {"clip": clip, "dir": cdir, "prompt": pp, "text": text, "executor": exe_rec, "card": card, "images": [],
                "nl": nl}
    if card.exists() and not a.force:
        raise InputError(f"{clip}: карточка {card.name} уже есть — --tag <суффикс> для нового запуска или --force")
    fdir = cdir / "frames"
    frames = sorted(p for p in fdir.iterdir() if p.suffix.lower() in FRAME_EXT) if fdir.is_dir() else []
    if not frames:
        raise InputError(f"{clip}: нет кадров в {fdir} (prep_acceptance.py)")
    images = list(frames)
    if not a.no_prompt_images:
        images += prompt_images(text, repo, fdir, {p.name for p in frames})
    for x in a.image:
        p = c.resolve(x, repo)
        if not p.is_file():
            raise InputError(f"--image: нет файла {x}")
        if p.resolve() not in {i.resolve() for i in images}:
            images.append(p)
    return {"clip": clip, "dir": cdir, "prompt": pp, "text": text, "executor": exe_rec, "card": card, "images": images,
            "nl": nl}


def accept_clip(p: dict, a, repo: Path) -> dict:
    cdir, card, tag = p["dir"], p["card"], a.tag
    rec = {"clip": p["clip"], "card": c.rel(card, repo) if card.resolve().is_relative_to(repo.resolve()) else
           card.as_posix(), "executor_session_id": p["executor"], "images": len(p["images"]), "started": now()}
    t0 = time.time()
    if not a.validate_only:
        if p["executor"]["rewritten"]:
            p["prompt"].write_text(p["text"], encoding="utf-8", newline=p["nl"])
        if card.exists():
            card.unlink()  # --force
        ev, err = cdir / f"acceptor-events{tag}.jsonl", cdir / f"acceptor-stderr{tag}.txt"
        cmd = codex_args(a.exe, repo, card, p["images"], a.model, a.effort)
        code, pid = run_codex(cmd, p["text"], repo, ev, err, a.timeout)
        evs = events(ev)
        thread = next((x.get("thread_id") for x in evs if x.get("type") == "thread.started"), None)
        launch = {"schema": "unmatched.clip-acceptor-launch/1", "clip": p["clip"], "pid": pid,
                  "parent_pid": os.getpid(), "exit_code": code, "elapsed_s": round(time.time() - t0, 1),
                  "model": a.model, "effort": a.effort, "exe": a.exe, "thread_id": thread,
                  "prompt": p["prompt"].name, "executor_session_id": p["executor"],
                  "images": [i.as_posix() for i in p["images"]], "argv": cmd}
        fails = env_failures(evs)
        status = None
        if code is None:
            status = "timeout"
        elif fails:
            status = "environment_failure"
            write_json(cdir / f"environment-failure{tag}.json", fails)
            if card.exists():
                card.replace(cdir / f"card-environment-failure{tag}.json")
        elif not card.is_file():
            status = "no_card"
        if status:
            launch["status"] = status
            write_json(cdir / f"acceptor-launch{tag}.json", launch)
            rec.update(status=status, elapsed_s=launch["elapsed_s"], thread_id=thread)
            return rec
        obj = json.loads(card.read_text(encoding="utf-8-sig"))
        acc = obj.get("acceptor") or {}
        if acc.get("session_id") == "codex:pending" and thread:
            acc["session_id"] = "codex:" + thread
            card.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
            launch["session_id_filled"] = {"before": "codex:pending", "after": acc["session_id"]}
        write_json(cdir / f"acceptor-launch{tag}.json", launch)
        rec["thread_id"] = thread
    obj = json.loads(card.read_text(encoding="utf-8-sig"))
    rec.update(score=obj.get("score"), verdict=obj.get("verdict"),
               acceptor_session=(obj.get("acceptor") or {}).get("session_id"))
    if obj.get("executor_session_id") != p["executor"]["used"]:
        rec.update(status="executor_mismatch", card_executor=obj.get("executor_session_id"),
                   elapsed_s=round(time.time() - t0, 1))
        return rec
    vcode, vout, verr = run_validate(card, repo)
    (cdir / f"validator-output{tag}.txt").write_text(verr + vout, encoding="utf-8", newline="\n")
    rec.update(validate_exit=vcode, computed_verdict=(vout.strip().splitlines() or [None])[-1],
               status={0: "valid", 3: "needs_second_acceptor"}.get(vcode, "invalid"),
               elapsed_s=round(time.time() - t0, 1))
    return rec


def main(argv=None) -> int:
    c.utf8_streams()
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--evidence", required=True, help="каталог цикла prep_acceptance.py (<asset-dir>/evidence/"
                                                      "acceptance-anim/<YYYYMMDD>-rN)")
    ap.add_argument("--clips", default=None, help="клипы через запятую (по умолчанию все подкаталоги с промптом)")
    ap.add_argument("--executor-session-id", default=None,
                    help="фактический id исполнителя клипов (claude-code:<uuid>/agent:<имя>, RA-21; C32/C55)")
    ap.add_argument("--image", action="append", default=[], help="ещё изображение приёмщику (повторяемый)")
    ap.add_argument("--no-prompt-images", action="store_true", help="только frames/, без изображений из промпта")
    ap.add_argument("--workers", type=int, default=0, help="параллельных приёмщиков (0 = по числу клипов)")
    ap.add_argument("--exe", default=None, help="codex.exe (по умолчанию новейший в %%LOCALAPPDATA%%/OpenAI/Codex/bin)")
    ap.add_argument("--model", default="gpt-6.1-sol")
    ap.add_argument("--effort", default="xhigh")
    ap.add_argument("--timeout", type=int, default=3600, help="секунд на одного приёмщика")
    ap.add_argument("--tag", default="", help="суффикс файлов повтора: card<tag>.json, acceptor-events<tag>.jsonl …")
    ap.add_argument("--force", action="store_true", help="перезаписать существующую карточку")
    ap.add_argument("--validate-only", action="store_true", help="только validate_card по готовым карточкам")
    ap.add_argument("--dry-run", action="store_true", help="план: изображения и id исполнителя, ничего не запускать")
    ap.add_argument("--repo", default=str(c.REPO))
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    repo = Path(a.repo)
    e = c.resolve(a.evidence, repo)
    try:
        if not e.is_dir():
            raise InputError(f"нет каталога цикла {e}")
        if a.executor_session_id and (not SESSION_RE.match(a.executor_session_id)
                                      or a.executor_session_id == "codex:pending"):
            raise InputError(f"--executor-session-id {a.executor_session_id!r}: нужен id вида "
                             "claude-code:<uuid>/agent:<имя> (RA-21)")
        clips = ([x.strip() for x in a.clips.split(",") if x.strip()] if a.clips else
                 sorted(d.name for d in e.iterdir() if d.is_dir() and prompt_path(d, a.tag).is_file()))
        if not clips:
            raise InputError(f"в {e} нет клипов с acceptor-prompt.md")
        plans = [plan_clip(e, clip, a, repo) for clip in clips]
        if not a.validate_only and not a.dry_run:
            a.exe = a.exe or default_exe()
            if not a.exe or not Path(a.exe).is_file():
                raise InputError("нет codex.exe (--exe)")
    except (InputError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if not a.executor_session_id:
        for p in plans:
            print(f"WARNING: {p['clip']}: executor_session_id из промпта {p['executor']['prompt']!r} — проверь, что это "
                  "фактический id исполнителя клипов (C32/C55), иначе --executor-session-id", file=sys.stderr)
    if a.dry_run:
        print(json.dumps({"dry_run": True, "evidence": e.as_posix(), "model": a.model, "effort": a.effort,
                          "clips": {p["clip"]: {"prompt": p["prompt"].name, "executor_session_id": p["executor"],
                                                "card": p["card"].name,
                                                "images": [i.as_posix() for i in p["images"]]} for p in plans}},
                         ensure_ascii=False, indent=1))
        return 0
    started = now()
    workers = a.workers or len(plans)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        results = list(pool.map(lambda p: accept_clip(p, a, repo), plans))
    summary = {"schema": "unmatched.clip-acceptors-run/1", "evidence": e.as_posix(), "started": started,
               "finished": now(), "mode": "validate-only" if a.validate_only else "codex",
               "model": a.model, "effort": a.effort, "exe": a.exe, "tag": a.tag,
               "executor_session_id": a.executor_session_id, "clips": {r["clip"]: r for r in results}}
    write_json(e / f"acceptors-run{a.tag}.json", summary)
    for r in results:
        print("%-12s %-22s score %-5s verdict %-16s validate %s" % (
            r["clip"], r["status"], r.get("score"), r.get("verdict"), r.get("validate_exit")))
    if any(r["status"] == "needs_second_acceptor" for r in results):
        print(f"NEED-SECOND: pass 8,0–8,4 — второй приёмщик Opus xhigh: {SECOND}")
    return 0 if all(r["status"] in ("valid", "needs_second_acceptor") for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
