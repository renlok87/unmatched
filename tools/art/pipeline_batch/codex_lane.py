"""Полоса пакета по claim-файлам: берёт задания из списка, гоняет команду генератора и завершает задание по ответу, а не по выходу процесса (RC-11).

С 2026-10-20 Codex отключён (пользователь отменил подписку ChatGPT; AGENTS.md «AI tools and side models»): полоса
больше не ищет и не запускает codex.exe. Без явной команды (--exe и --codex-args-json) и с codex.exe в --exe она
падает с кодом 2 и причиной. 1a/1c рисует Gemini через Computer Use (скилл 3d-model-pipeline §0) — пачкой это не
скриптуется. Механика claim/STOP/-o/429 осталась для заглушек тестов и для будущей полосы Z-Code (headless
`zcode.cjs` — после `zcode login zai` пользователя; до этого `tools/art/acceptance/side_models.py zcode-probe`).
Ниже — описание механики времён Codex.

Был C:/tmp/concept-wave/run-claim-loop.ps1 (полосы 1a/1c, concept-sheet.md §13). Несколько полос делят один список
и каталог логов: задание берёт та полоса, которой удалось создать `<logs>/<id>.claim` (O_EXCL), id = имя файла
задания без расширения. Полоса крутится, пока нет STOP-файла (--stop-file, по умолчанию <logs>/STOP), и раз в
--idle-sleep с перечитывает список (новые задания можно дописывать на ходу); --once — выйти, когда брать нечего.

Готовность (RC-11): процесс генератора после ответа висит до 23 мин (хуки пользователя держат канал), поэтому
задание считается выполненным, когда файл `-o` (`<logs>/<id>-last.txt`) не пуст И в stderr/stdout есть строка
«tokens used». Через --grace с после этого полоса гасит СВОЁ дерево процессов — по PID запущенного codex
(psutil: дети рекурсивно, затем сам процесс; без psutil — taskkill /PID <pid> /T /F), никогда по имени. Обычный выход
процесса — тоже конец задания. --timeout с (0 — нет) — аварийный предел на задание.

Файлы задания в <logs>: <id>.claim, <id>.out, <id>.err (байты как есть), <id>-last.txt (-o), <id>.done
(«<exit> <reason>»: exit | done-killed | timeout | rate-limited); журнал полосы <logs>/<name>.log
(START/END/RATE-LIMIT/RELEASE/LANE STOP).

Лимит Codex (429, C4 проверочного прогона 2026-10-14): процесс вышел с кодом ≠ 0 без ответа, а в хвосте stderr/stdout
«exceeded retry limit», «429 Too Many Requests», «status: 429» или «usage limit» — это не результат задания. Полоса
копирует файлы попытки в <logs>/attempts/<id>/a<N>/ и через --retry-pause с запускает задание заново, не больше
--retry-429 раз (claim остаётся у неё; STOP во время паузы снимает claim — задание возьмёт следующая полоса).
Повторы кончились — .done «<exit> rate-limited», claim остаётся. Перезапуск вручную — --release <id>[,<id>…]: файлы
попытки уходят в attempts/<id>/manual-<время>/, claim и .done снимаются; запущенная полоса возьмёт задание сама.

    python tools/art/pipeline_batch/codex_lane.py --tasks <tasks.txt> --name d1 --logs <dir> [--stop-file <path>] \
        --exe <генератор> --codex-args-json '[...]' [--grace 10] [--poll 2] [--idle-sleep 60] [--timeout 0] [--once] \
        [--retry-429 3] [--retry-pause 120]
    python tools/art/pipeline_batch/codex_lane.py --tasks t.txt --name d1 --logs L --dry-run   # команды, без claim
    python tools/art/pipeline_batch/codex_lane.py --tasks t.txt --name d1 --logs L --release <id>   # снять claim

Команда: <exe> <--codex-args-json…> -o <last> - (stdin — файл задания). До 2026-10-20 по умолчанию шёл
`codex.exe exec -C <repo> -s workspace-write -c windows.sandbox="unelevated" --skip-git-repo-check`; этой команды больше
нет. --codex-home задаёт CODEX_HOME процесса (наследие RC-11). Код выхода: 0 — полоса остановлена, 2 — ошибка входа
(в том числе Codex: отключён).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _batch as b  # noqa: E402

DONE_MARK = "tokens used"
_MARKS = (DONE_MARK.encode("utf-8"), DONE_MARK.encode("utf-16-le"))
TAIL_BYTES = 1 << 16
# Отказ по лимиту Codex (C4). Только узкие фразы ошибки CLI: хвост stderr несёт и эхо промпта задания (там бывают
# «retry», хэши с цифрами 429), поэтому голые «429» и «retry» не ищутся.
RATE_LIMIT_RE = re.compile(r"exceeded retry limit|429 Too Many Requests|status:? ?429\b|usage limit", re.I)
ATTEMPT_SUFFIXES = (".out", ".err", "-last.txt", ".done")


def is_codex(exe: str | None) -> bool:
    """codex.exe / codex (CLI Codex) — отключён 2026-10-20."""
    return bool(exe) and Path(exe).stem.lower() == "codex"


def task_ids(tasks_file: Path) -> list[tuple[str, Path]]:
    lines = [ln.strip() for ln in tasks_file.read_text(encoding="utf-8-sig").splitlines()]
    return [(Path(ln).stem, Path(ln)) for ln in lines if ln and not ln.startswith("#")]


def claim(logs: Path, task_id: str) -> bool:
    try:
        fd = os.open(logs / f"{task_id}.claim", os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    os.close(fd)
    return True


def _tail(path: Path) -> bytes:
    try:
        with open(path, "rb") as fh:
            fh.seek(0, 2)
            n = fh.tell()
            fh.seek(max(0, n - TAIL_BYTES))
            return fh.read()
    except OSError:
        return b""


def answered(last: Path, logs: list[Path]) -> bool:
    """Задание отвечено: -o не пуст и в хвосте stderr/stdout есть «tokens used» (UTF-8 или UTF-16-LE)."""
    try:
        if last.stat().st_size == 0:
            return False
    except OSError:
        return False
    return any(m in _tail(p) for p in logs for m in _MARKS)


def rate_limited(logs: list[Path]) -> bool:
    """В хвосте stderr/stdout — отказ по лимиту Codex (429, «exceeded retry limit», «usage limit»); UTF-8 или UTF-16-LE."""
    for p in logs:
        raw = _tail(p)
        for enc in ("utf-8", "utf-16-le"):
            if RATE_LIMIT_RE.search(raw.decode(enc, errors="replace")):
                return True
    return False


def archive_attempt(logs: Path, task_id: str, tag: str) -> Path:
    """Копии файлов попытки (out, err, -o, done) в <logs>/attempts/<id>/<tag>/ — следующая попытка их перезапишет."""
    dest = logs / "attempts" / task_id / tag
    dest.mkdir(parents=True, exist_ok=True)
    for suf in ATTEMPT_SUFFIXES:
        src = logs / f"{task_id}{suf}"
        if src.is_file():
            shutil.copy2(src, dest / src.name)
    return dest


def release(logs: Path, task_id: str) -> dict:
    """Ручной перезапуск задания: файлы попытки — в attempts/<id>/manual-<время>/, claim и .done снимаются."""
    claim_f, done_f = logs / f"{task_id}.claim", logs / f"{task_id}.done"
    if not claim_f.exists() and not done_f.exists():
        return {"id": task_id, "released": False, "note": "нет claim и .done"}
    dest = archive_attempt(logs, task_id, "manual-" + dt.datetime.now().strftime("%Y%m%dT%H%M%S"))
    for f in (done_f, claim_f):  # claim последним: полоса не возьмёт задание с незакрытым .done
        if f.exists():
            f.unlink()
    return {"id": task_id, "released": True, "archive": dest.as_posix()}


def kill_tree(pid: int) -> list[int]:
    """Погасить дерево процессов, корень — pid (дети рекурсивно, потом корень). Возвращает погашенные PID."""
    try:
        import psutil
    except ImportError:
        psutil = None
    if psutil is not None:
        try:
            root = psutil.Process(pid)
        except psutil.NoSuchProcess:
            return []
        procs = root.children(recursive=True) + [root]
        for p in procs:
            try:
                p.kill()
            except psutil.NoSuchProcess:
                pass
        psutil.wait_procs(procs, timeout=10)
        return [p.pid for p in procs]
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    else:
        try:
            os.kill(pid, 9)
        except OSError:
            pass
    return [pid]


def _now() -> str:
    return dt.datetime.now().replace(microsecond=0).isoformat()


class Lane:
    def __init__(self, a):
        self.a = a
        self.repo = Path(a.repo)
        self.logs = Path(a.logs)
        self.stop = Path(a.stop_file) if a.stop_file else self.logs / "STOP"
        self.journal = self.logs / f"{a.name}.log"
        self.args = json.loads(a.codex_args_json)
        if not isinstance(self.args, list):
            raise ValueError("ожидается JSON-список аргументов")

    def log(self, line: str) -> None:
        with open(self.journal, "a", encoding="utf-8") as fh:
            fh.write(f"{_now()} {line}\n")

    def command(self, task_id: str) -> list[str]:
        return [self.a.exe, *self.args, "-o", str(self.logs / f"{task_id}-last.txt"), "-"]

    def env(self) -> dict:
        env = b.utf8_env()
        if self.a.codex_home:
            env["CODEX_HOME"] = str(self.a.codex_home)
        return env

    def run_task(self, task_id: str, task: Path) -> tuple[int | None, str]:
        """Задание с повтором при отказе по лимиту Codex (C4); .done пишется один раз, по последней попытке."""
        retries = max(0, int(getattr(self.a, "retry_429", 0) or 0))
        attempt = 0
        while True:
            attempt += 1
            code, reason = self.run_once(task_id, task)
            if reason != "exit" or code in (0, None) or not rate_limited(
                    [self.logs / f"{task_id}.err", self.logs / f"{task_id}.out"]):
                break
            if answered(self.logs / f"{task_id}-last.txt", [self.logs / f"{task_id}.err", self.logs / f"{task_id}.out"]):
                break
            dest = archive_attempt(self.logs, task_id, f"a{attempt}")
            if attempt > retries:
                reason = "rate-limited"
                self.log(f"RATE-LIMIT {task_id} attempt={attempt} exit={code} give-up copy={dest.as_posix()}")
                break
            pause = float(getattr(self.a, "retry_pause", 0) or 0)
            self.log(f"RATE-LIMIT {task_id} attempt={attempt} exit={code} retry-in={int(pause)}s copy={dest.as_posix()}")
            if not self.wait(pause):
                (self.logs / f"{task_id}.claim").unlink(missing_ok=True)
                self.log(f"RELEASE {task_id} stop-file during the 429 pause: the claim is free for the next lane")
                return code, "released"
        (self.logs / f"{task_id}.done").write_text(f"{code} {reason}\n", encoding="utf-8")
        return code, reason

    def wait(self, seconds: float) -> bool:
        """Пауза с проверкой STOP раз в секунду (и в конце); False — появился STOP."""
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if self.stopped():
                return False
            time.sleep(min(1.0, max(0.0, end - time.monotonic())))
        return not self.stopped()

    def run_once(self, task_id: str, task: Path) -> tuple[int | None, str]:
        last, out, err = (self.logs / f"{task_id}-last.txt", self.logs / f"{task_id}.out", self.logs / f"{task_id}.err")
        start = time.monotonic()
        self.log(f"START {task_id}")
        if not task.is_file():
            self.log(f"END {task_id} exit=None reason=missing-task sec=0")
            return None, "missing-task"
        if last.exists():  # -o прежней попытки: иначе «ответ» нашёлся бы в старом файле
            last.unlink()
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        with open(task, "rb") as fin, open(out, "wb") as fo, open(err, "wb") as fe:
            p = subprocess.Popen(self.command(task_id), stdin=fin, stdout=fo, stderr=fe, cwd=self.repo, env=self.env(),
                                 creationflags=flags)
            self.log(f"PID {task_id} {p.pid}")
            done_at, reason = None, "exit"
            while True:
                if p.poll() is not None:
                    break
                now = time.monotonic()
                if answered(last, [err, out]):
                    done_at = done_at if done_at is not None else now
                    if now - done_at >= self.a.grace:
                        killed = kill_tree(p.pid)
                        reason = "done-killed"
                        self.log(f"KILL {task_id} pid={p.pid} tree={killed} after answer +{int(now - done_at)}s")
                        break
                if self.a.timeout and now - start > self.a.timeout:
                    kill_tree(p.pid)
                    reason = "timeout"
                    break
                time.sleep(self.a.poll)
            code = p.wait()
        sec = int(time.monotonic() - start)
        self.log(f"END {task_id} exit={code} reason={reason} sec={sec}")
        return code, reason

    def stopped(self) -> bool:
        return self.stop.exists()

    def loop(self) -> list[dict]:
        self.logs.mkdir(parents=True, exist_ok=True)
        results = []
        while not self.stopped():
            did = False
            for task_id, task in task_ids(Path(self.a.tasks)):
                if self.stopped():
                    break
                if not claim(self.logs, task_id):
                    continue
                did = True
                code, reason = self.run_task(task_id, task)
                results.append({"id": task_id, "exit": code, "reason": reason})
            if not did:
                if self.a.once:
                    break
                for _ in range(int(self.a.idle_sleep)):
                    if self.stopped():
                        break
                    time.sleep(1)
        self.log("LANE STOP")
        return results


def main(argv=None) -> int:
    b.utf8_streams()
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--tasks", required=True, help="список файлов заданий (по строке; # — комментарий)")
    ap.add_argument("--name", required=True, help="имя полосы (журнал <logs>/<name>.log)")
    ap.add_argument("--logs", required=True, help="каталог логов и claim-файлов (общий у полос одной волны)")
    ap.add_argument("--stop-file", default=None, help="STOP-файл (по умолчанию <logs>/STOP)")
    ap.add_argument("--repo", default=str(b.REPO), help="рабочий каталог процесса генератора")
    ap.add_argument("--exe", default=None, help="исполняемый файл генератора (codex.exe отключён 2026-10-20)")
    ap.add_argument("--codex-args-json", default=None, help="аргументы генератора (JSON-список; -o и - добавляются)")
    ap.add_argument("--codex-home", default=None, help="CODEX_HOME процесса (профиль без hooks/plugins, RC-11)")
    ap.add_argument("--grace", type=float, default=10.0, help="с после ответа до гашения дерева (10)")
    ap.add_argument("--poll", type=float, default=2.0, help="опрос процесса и файлов, с (2)")
    ap.add_argument("--idle-sleep", type=float, default=60.0, help="пауза, когда брать нечего, с (60)")
    ap.add_argument("--timeout", type=float, default=0.0, help="предел на задание, с (0 — нет)")
    ap.add_argument("--once", action="store_true", help="выйти, когда свободных заданий нет")
    ap.add_argument("--retry-429", type=int, default=3,
                    help="повторов задания после отказа по лимиту Codex (429; 0 — без повтора), по умолчанию 3")
    ap.add_argument("--retry-pause", type=float, default=120.0, help="пауза перед повтором после 429, с (120)")
    ap.add_argument("--release", default=None,
                    help="id заданий через запятую: файлы попытки в attempts/, снять claim и .done (перезапуск) и выйти")
    ap.add_argument("--dry-run", action="store_true", help="напечатать команды свободных заданий, ничего не брать")
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    if a.release:
        logs = Path(a.logs)
        for task_id in (x.strip() for x in a.release.split(",") if x.strip()):
            print(json.dumps(release(logs, task_id), ensure_ascii=False))
        return 0
    if is_codex(a.exe) or not (a.exe and a.codex_args_json):
        print(f"ERROR: {b.side_models().CODEX_GONE}. Полоса без явной команды генератора (--exe и "
              "--codex-args-json) не запускается.", file=sys.stderr)
        return 2
    tasks = Path(a.tasks)
    if not tasks.is_file():
        print(f"ERROR: нет списка заданий {tasks}", file=sys.stderr)
        return 2
    try:
        lane = Lane(a)
    except ValueError as exc:
        print(f"ERROR: --codex-args-json: {exc}", file=sys.stderr)
        return 2
    if a.dry_run:
        free = [(i, t) for i, t in task_ids(tasks) if not (Path(a.logs) / f"{i}.claim").exists()]
        for i, t in free:
            print(json.dumps({"id": i, "task": t.as_posix(), "exists": t.is_file(), "cmd": lane.command(i)},
                             ensure_ascii=False))
        print(f"free {len(free)}, stop-file {lane.stop.as_posix()} {'EXISTS' if lane.stopped() else 'absent'}")
        return 0
    res = lane.loop()
    print(json.dumps({"lane": a.name, "tasks": res}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
