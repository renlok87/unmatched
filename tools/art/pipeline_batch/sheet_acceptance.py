"""Приёмка листов 1c пачкой (Sol-приёмщик Codex): предпроверка пакета, промпт по рубрике §11, запуск codex exec, проверка карточки validate_card.

concept-sheet.md §11 (рубрика 1c), acceptance-and-blender.md §8.4 (команда приёмщика). На фигуру из списка «своих»
(--owned: [{asset_id, key, package, status: "claimed"}, …]) в каталоге
<asset-dir>/evidence/acceptance-concept/<YYYYMMDD>-sheet-r<N>/ (создаёт тот, кто взял фигуру):
  1. preflight — выбранные записи 1c и их копии, ссылки, полный manifest-sha256, UTF-8 без BOM/«????», повтор
     check_concept_views.py --sheet совпадает с checks-report.json пакета, G-CHECKS без FAIL;
  2. prompt — константы карточки, рубрика §11 дословно, изображения отдельными -i;
  3. accept — codex exec (--ignore-user-config, read-only, --output-schema), session_id из thread.started,
     validate_card.py --check-files (0 или 3 = нужен второй приёмщик), запись в журнал --log.
Пакет во время приёмки не меняется (хэши до/после). Был C:/tmp/concept-wave/sheet_acceptance.py.

    python tools/art/pipeline_batch/sheet_acceptance.py prepare <key> <cycle> --work <dir> --date YYYY-MM-DD   # без Codex
    python tools/art/pipeline_batch/sheet_acceptance.py probe --work <dir>
    python tools/art/pipeline_batch/sheet_acceptance.py accept <key> <cycle> --work <dir> --date YYYY-MM-DD
    python tools/art/pipeline_batch/sheet_acceptance.py all --work <dir> --date YYYY-MM-DD [--workers 3]
    общие: [--owned <json>] [--log <jsonl>] [--exe <codex.exe>] [--model gpt-6.1-sol] [--effort xhigh]
           [--user-quote "дословная цитата задачи"]…

Траты: каждая приёмка — сессия Codex (квота ChatGPT, RC-12): строку журнала трат пишет оркестратор.
Код выхода: 0 — команда выполнена (итог каждой фигуры — в журнале), 1 — проба не прошла, 2 — ошибка входа.
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
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _batch as b  # noqa: E402

DELEGATION = ("Делегирование пользователя (2026-10-06, дословно): «Не знаю. Делай сам, меня это не касается. Все решения "
              "принимай».")
SCHEMA = "tools/art/acceptance/asset-acceptance-2.output-concept.schema.json"
LOCK = threading.Lock()


def read(p) -> str:
    return Path(p).read_text(encoding="utf-8-sig")


def data(p):
    return json.loads(read(p))


def write(p, x) -> None:
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(x if isinstance(x, str) else json.dumps(x, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def psq(s) -> str:
    """Строка PowerShell в одинарных кавычках."""
    return "'" + str(s).replace("'", "''") + "'"


def events(p) -> list:
    out = []
    if Path(p).exists():
        for line in read(p).splitlines():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def base_args(repo: Path, out: Path, images: list, model: str, effort: str, schema: bool = True) -> list:
    a = ["exec", "--ignore-user-config", "-m", model, "-c", f'model_reasoning_effort="{effort}"', "-c",
         'windows.sandbox="unelevated"', "-s", "read-only", "-C", str(repo), "--skip-git-repo-check"]
    if schema:
        a += ["--output-schema", str(repo / SCHEMA)]
    a += ["-o", str(out), "--json"]
    for img in images:
        a += ["-i", str(img)]
    return a + ["--", "-"]


def env_failures(evs: list) -> list:
    """Сбой песочницы (не попытка приёмки): команды с helper_unknown_error / Failed to create unified exec process."""
    bad = []
    for x in evs:
        it = x.get("item") or {}
        out = it.get("aggregated_output", "")
        if it.get("type") == "command_execution" and it.get("status") == "failed" and (
                "helper_unknown_error" in out or out.startswith("Failed to create unified exec process")):
            bad.append(x)
    return bad


class Sheet:
    def __init__(self, a):
        self.a = a
        self.repo = Path(a.repo)
        self.work = Path(a.work)
        self.date = a.date
        self.d8 = a.date.replace("-", "")
        self.log = Path(a.log) if a.log else self.work / "acceptance-log-1c.jsonl"
        self.exe = a.exe

    def rel(self, p) -> str:
        return b.rel(p, self.repo)

    def ev_dir(self, aid: str, cycle: int) -> Path:
        return self.repo / "art/pipeline-candidates" / aid / "evidence/acceptance-concept" / f"{self.d8}-sheet-r{cycle}"

    def run_cli(self, prompt: str, args: list, folder: Path, tag: str):
        folder = Path(folder)
        pp, script = folder / f"{tag}-prompt.md", folder / f"{tag}.ps1"
        ev, err, pout = folder / f"{tag}-events.jsonl", folder / f"{tag}-stderr.txt", folder / f"{tag}-process.json"
        write(pp, prompt)
        body = ("$OutputEncoding = [Text.UTF8Encoding]::new($false)\n[Console]::OutputEncoding = "
                "[Text.UTF8Encoding]::new($false)\n$env:PYTHONIOENCODING='utf-8'\n")
        body += "$argsForCodex = @(\n" + ",\n".join(psq(x) for x in args) + "\n)\n"
        body += (f"Get-Content {psq(pp)} -Raw -Encoding UTF8 | & {psq(self.exe)} @argsForCodex 2> {psq(err)} | "
                 f"Out-File -Encoding utf8 {psq(ev)}\nexit $LASTEXITCODE\n")
        write(script, body)
        started = time.time()
        with (folder / f"{tag}-runner.txt").open("w", encoding="utf-8") as stream:
            proc = subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
                                    cwd=self.repo, env=b.utf8_env(), stdout=stream, stderr=subprocess.STDOUT,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            write(pout, dict(pid=proc.pid, parent_pid=os.getpid(), executable="powershell", script=str(script),
                             codex_executable=str(self.exe), args=args, started=started))
            code = proc.wait()
        info = data(pout)
        info.update(exit_code=code, finished=time.time())
        write(pout, info)
        return code, ev, err

    # ---------------------------------------------------------------------------------------------- 1. preflight
    def preflight(self, row: dict, cycle: int):
        aid, key = row["asset_id"], row["key"]
        p, e = self.repo / row["package"], self.ev_dir(aid, cycle)
        if not e.is_dir():
            raise RuntimeError(f"нет взятого каталога приёмки {self.rel(e)}")
        card = self.repo / "art/pipeline-candidates" / aid / "asset-card.yaml"
        cardtext = read(card)
        gens, prompts = data(p / "generation-records.json"), data(p / "prompts/concept-prompts.json")
        for view in ("front", "side", "back"):
            sel = [g for g in gens if g.get("stage") == "1c" and g.get("view") == view and g.get("selected")]
            if len(sel) != 1:
                raise RuntimeError(f"{view}: выбранных записей 1c {len(sel)}")
            g = sel[0]
            if not prompts.get(g["prompt_key"]):
                raise RuntimeError(f"{view}: нет точного промпта {g['prompt_key']}")
            if not (b.sha256(self.repo / g["saved_path"]) == g["sha256"] == b.sha256(p / f"{key}-{view}.png")):
                raise RuntimeError(f"{view}: копия выбранного вида не совпадает")
            for ref in g["references"]:
                if b.sha256(self.repo / ref["path"]) != ref["sha256"]:
                    raise RuntimeError(f"{view}: изменилась ссылка {ref['path']}")
        for g in (g for g in gens if g.get("stage") == "1c"):
            if not (p / "checks" / f"{g['view']}-g{g['attempt']}" / "checks-report.json").is_file():
                raise RuntimeError(f"нет отчёта проверки кандидата {g['view']}-g{g['attempt']}")
        m = data(p / "manifest-sha256.json")
        m = m.get("files", m)
        if isinstance(m, list):
            m = {x["path"]: x for x in m}
        listed = set()
        for name, item in m.items():
            if not isinstance(item, dict) or "sha256" not in item:
                continue
            f = self.repo / name if name.startswith("art/") else p / name
            if not (f.is_file() and b.sha256(f) == item["sha256"] and f.stat().st_size == item["bytes"]):
                raise RuntimeError("manifest mismatch " + name)
            listed.add(f.resolve())
        actual = {f.resolve() for f in p.rglob("*") if f.is_file() and f.name != "manifest-sha256.json"}
        if listed != actual:
            raise RuntimeError("manifest coverage mismatch")
        bad = [self.rel(f) for f in p.rglob("*") if f.suffix in (".md", ".json") and (
            f.read_bytes()[:3] == b"\xef\xbb\xbf" or "????" in read(f) or "\ufffd" in read(f))]
        if bad:
            raise RuntimeError("invalid UTF-8 " + str(bad))
        role = re.search(r"^ROLE:\s*(\S+)", cardtext, re.M)[1]
        dest = self.work / "sheet-rechecks" / aid / f"r{cycle}"
        chk = b.run([sys.executable, "-X", "utf8", "tools/art/concept/check_concept_views.py", "--set", self.rel(p), "--key",
                     key, "--views", "front,side,back", "--role", role, "--palette", self.rel(p / "palette.json"),
                     "--sheet", "--out", str(dest)], self.repo)
        write(dest / "launcher-check.txt", chk.stdout + chk.stderr)
        old, new = data(p / "checks-report.json"), data(dest / "checks-report.json")

        def comparable(x):
            return [i["sha256"] for i in x["inputs"]], x["checks"], x["summary"], x["verdict"], x.get("frame")

        if comparable(old) != comparable(new):
            raise RuntimeError("повтор check_concept_views расходится с checks-report.json пакета")
        if chk.returncode != 0:
            raise RuntimeError("G-CHECKS FAIL до приёмки")
        write(e / "launcher-preflight.json", dict(selected_records=True, manifest=True, utf8=True, recheck_exit=0,
                                                  recheck_same=True, package_hashes={self.rel(f): b.sha256(f) for f in
                                                                                     p.rglob("*") if f.is_file()}))
        return p, e, card, cardtext, gens, old

    # ------------------------------------------------------------------------------------------------- 2. prompt
    def prepare(self, row: dict, cycle: int):
        p, e, card, cardtext, gens, checks = self.preflight(row, cycle)
        aid, key = row["asset_id"], row["key"]
        orthodirs = list((self.repo / "art/pipeline-candidates" / aid).glob("*-draft-tripo/orthos"))
        if len(orthodirs) != 1:
            raise RuntimeError(f"каталогов орто черновика {len(orthodirs)}, нужен один")
        orthos = sorted(orthodirs[0].glob("*.png"))
        qref = re.search(r"^\s+-\s+(art/[^\r\n]+\.png)\s*$", cardtext, re.M)[1]
        views = [p / f"{key}-{v}.png" for v in ("front", "side", "back")]
        images = views + [p / f"sheet-{key}.png", p / "design" / f"{key}-front.png"] + orthos + [self.repo / qref]
        missing = [str(f) for f in images if not f.is_file()]
        if missing:
            raise RuntimeError(f"нет изображений {missing}")
        prev = (self.rel(e.parent / f"{self.d8}-sheet-r{cycle - 1}" / "card.json") if cycle > 1 else None)
        constants = dict(schema="unmatched.concept-acceptance/1", kind="concept", asset_id=aid, clip=None,
                         cycle=f"r{cycle}", date=self.date, previous_card=prev,
                         accepted_object=[dict(path=self.rel(f), sha256=b.sha256(f)) for f in views],
                         frames=dict(dir=self.rel(p), files=[f"sheet-{key}.png"] + [f.name for f in views]
                                     + ["checks-report.json"]),
                         reports=[self.rel(p / f) for f in ("checks-report.json", "generation-records.json",
                                                            "verification.json")],
                         acceptor=dict(profile="Sol 6.1 xhigh", session_id="codex:pending"),
                         executor_session_id=f"launcher:stage-1c-sheet-{self.d8}",
                         decided_by="delegated (ВР-реестр 2026-10-06)")
        rubric = read(self.repo / b.SKILL)
        rubric = rubric[rubric.index("## 11."):rubric.index("## 12.")]
        quotes = "".join(f"Задача пользователя (дословно): «{q}».\n" for q in self.a.user_quote)
        limit = json.dumps(data(p / "verification.json").get("limit_reached", []), ensure_ascii=False)
        prompt = f"""# Приёмка 1c sheet {aid}, цикл r{cycle}
{DELEGATION}
{quotes}Траты на приёмке: нет. Ты — отдельный приёмщик «Sol 6.1 xhigh», не исполнитель. Файлы не правишь, ничего не генерируешь, не запускаешь validate_card.py, Blender, git, Unreal, Tripo, SYNTX, браузер или других агентов.
Твоя единственная выдача — JSON-карточка. Её сохраняет CLI. Читай тексты в UTF-8: PowerShell Get-Content -Raw -Encoding UTF8. Если вывод консоли повреждён, используй Python с ensure_ascii=True. Не читай посторонние карточки, чаты или пакеты.
Ты — приёмщик этапа 1 скилла 3d-model-pipeline (концепт-лист). Объект: 1c виды {key}-front/side/back.png и лист sheet-{key}.png пакета {self.rel(p)}.
Открой каждый файл как картинку: все изображения переданы отдельными -i. Порядок приложенных изображений:
{json.dumps([self.rel(f) for f in images], ensure_ascii=False, indent=2)}
Эталон качества: {qref}. Для 1c — утверждённый дизайн {self.rel(p / 'design' / f'{key}-front.png')} и ортопроекции 1b {self.rel(orthodirs[0])}. ortho_right — дополнительный вид того же черновика; SIDE_VIEW заявки задаёт сторону принимаемого side.
Прочитай {self.rel(p / 'checks-report.json')}, {self.rel(p / 'generation-records.json')}, {self.rel(p / 'verification.json')}, {self.rel(p / 'palette.json')}, {self.rel(card)} и {self.rel(orthodirs[0] / 'ortho-framing.json')}. Предыдущая карточка: {prev}; на r2 проверь закрытие её списка, а баллы ставь заново.
Выдержка карточки ассета (DESCRIPTION_EN, ANCHORS_EN, PALETTE, ANATOMY, WEAPON_HAND, SIDE_VIEW):
{cardtext}
Рубрика: concept-sheet.md §11, полный раздел:
{rubric}
Применяй рубрику 1c, четыре числовых измерения S,C,Q,P. C здесь оценивается по согласованности всех трёх видов; фиксированный C 1.5 относится только к 1a.
T- или A-поза = S 0. Балл по якорям, шаг 0.5; обоснование с именами файлов из frames.files. G-CHECKS единственный гейт: checks-report.json#summary.FAIL = {checks['summary']['FAIL']}; source строго {self.rel(p / 'checks-report.json')}. WARN не гейт, учитывай их в C.
rework_fix_list — только измерения <2 и G-CHECKS при FAIL; пункт item, frame (имя вида из frames.files), fix (одна английская строка для CORRECTION), tool (Codex 1c CORRECTION | Tripo 1b черновик | Codex 1a). При не-pass список должен покрывать каждое измерение ниже 2 и FAIL гейта. При pass [] и замечания в known_issues. known_issues.item только S,C,Q,P,G-CHECKS.
Причину, уже присутствующую в орто, направляй tool Tripo 1b черновик; ошибку в самом approved design — Codex 1a. Для поверхностной детали, рамки или ракурса одного вида — Codex 1c CORRECTION. Укажи конкретный дефектный вид, не назначай слепую перегенерацию.
score half-up: sum(S,C,Q,P)/8*10. Гейт FAIL, любое значение <1 или score <8 => return_to_stage_1, иначе pass; r4 без pass => escalate_user. При не-pass заполни verdict_reason.
Заполни все поля таблицы Карточка §11; обязательные константы (скопировать без изменения):
{json.dumps(constants, ensure_ascii=False, indent=2)}
При pass status_note содержит «художественно принято, по делегированию (docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md)».
В строгой схеме необязательные поля представлены null. Acceptor session_id codex:pending запускающий заменит на thread_id; другой правки не будет.
Codex исчерпал генерации запуска; проваленные пункты CHECKLIST: {limit}; оцени их по рубрике, без автоматического снижения из-за записи исполнителя.
Верни только JSON карточки по {SCHEMA}.
"""
        if "{{" in prompt:
            raise RuntimeError("незаполненный плейсхолдер")
        write(e / "acceptor-prompt.md", prompt)
        write(e / "launcher-inputs.json", dict(images=[self.rel(f) for f in images], constants=constants))
        return e, p, prompt, images

    # ------------------------------------------------------------------------------------------------- 3. accept
    def append(self, row, cycle, score, verdict, validate_exit, card, notes="") -> dict:
        rec = dict(asset_id=row["asset_id"], cycle=f"r{cycle}", score=score, verdict=verdict, validate_exit=validate_exit,
                   card_path=self.rel(card) if card else None, notes=notes)
        with LOCK:
            self.log.parent.mkdir(parents=True, exist_ok=True)
            with self.log.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec

    def accept(self, row: dict, cycle: int = 1) -> dict:
        e = self.ev_dir(row["asset_id"], cycle)
        out = e / "card.json"
        try:
            e, p, prompt, images = self.prepare(row, cycle)
            if out.exists():
                raise RuntimeError("карточка уже есть")
            print("START", row["asset_id"], f"r{cycle}", len(images), "images", flush=True)
            args = base_args(self.repo, out, images, self.a.model, self.a.effort)
            for attempt in (1, 2):
                code, evfile, errfile = self.run_cli(prompt, args, e, f"acceptor-{attempt}")
                ev = events(evfile)
                fails = env_failures(ev)
                if fails:
                    write(e / "environment-failure.json", fails)
                    if out.exists():
                        out.rename(e / f"card-environment-failure-{attempt}.json")
                    raise RuntimeError("сбой окружения песочницы, не попытка приёмки")
                if not out.exists():
                    if attempt == 1:
                        errors = read(evfile) + (Path(errfile).read_text(encoding="utf-16", errors="replace")
                                                 if Path(errfile).is_file() else "")
                        if re.search(r"output_schema|json_schema|response_format", errors, re.I):
                            args = base_args(self.repo, out, images, self.a.model, self.a.effort, schema=False)
                        continue
                    raise RuntimeError(f"приёмщик недоступен после повтора; exit {code}")
                obj = data(out)
                thread = next(x["thread_id"] for x in ev if x.get("type") == "thread.started")
                if obj["acceptor"]["session_id"] != "codex:pending":
                    raise RuntimeError("неожиданный acceptor.session_id")
                obj["acceptor"]["session_id"] = "codex:" + thread
                write(out, obj)
                write(e / f"launcher-session-id-{attempt}.json",
                      dict(change="acceptor.session_id only", before="codex:pending", after="codex:" + thread))
                val = b.run([sys.executable, "-X", "utf8", "tools/art/acceptance/validate_card.py", self.rel(out),
                             "--print-verdict", "--check-files"], self.repo)
                write(e / f"validate-{attempt}.txt", val.stdout + val.stderr)
                if val.returncode in (0, 3):
                    expected = "PASS" if data(p / "checks-report.json")["summary"]["FAIL"] == 0 else "FAIL"
                    if obj["gates"]["G-CHECKS"]["status"] != expected:
                        raise RuntimeError("гейт G-CHECKS противоречит отчёту")
                    const = data(e / "launcher-inputs.json")["constants"]
                    if obj["accepted_object"] != const["accepted_object"] or obj["frames"] != const["frames"]:
                        raise RuntimeError("объект или кадры отличаются от §11")
                    before = data(e / "launcher-preflight.json")["package_hashes"]
                    if before != {self.rel(f): b.sha256(f) for f in p.rglob("*") if f.is_file()}:
                        raise RuntimeError("пакет изменился во время приёмки только для чтения")
                    notes = ""
                    if val.returncode == 3:
                        notes = "нужен второй приёмщик (Opus xhigh)"
                        write(e / "note.md", notes + "\n")
                    elif obj["verdict"] == "return_to_stage_1" and (p / "README.md").is_file() \
                            and "unstability.ai" in read(p / "README.md").lower():
                        notes = "нужна доработка — виды лицензированной фигуры делаются вне Codex"
                        write(e / "note.md", notes + "\n\n" + json.dumps(obj["rework_fix_list"], ensure_ascii=False,
                                                                         indent=2) + "\n")
                    rec = self.append(row, cycle, obj["score"], obj["verdict"], val.returncode, out, notes)
                    print("DONE", json.dumps(rec, ensure_ascii=False), flush=True)
                    return rec
                if attempt == 1:
                    out.rename(e / "card-invalid-attempt1.json")
                    prompt += ("\nПредыдущая попытка невалидна. Повтори оценку в новом контексте с теми же входами. "
                               "Вывод валидатора:\n" + val.stdout + val.stderr)
                else:
                    raise RuntimeError("два невалидных ответа подряд")
        except Exception as exc:  # noqa: BLE001 - фигура блокируется, пачка идёт дальше
            write(e / "launcher-error.txt", str(exc) + "\n")
            rec = self.append(row, cycle, None, "launcher_blocked", None, out if out.exists() else None, str(exc))
            print("BLOCKED", json.dumps(rec, ensure_ascii=False), flush=True)
            return rec

    def probe(self) -> bool:
        args = ["exec", "--ignore-user-config", "-m", self.a.model, "-c", 'model_reasoning_effort="low"', "-c",
                'windows.sandbox="unelevated"', "-s", "read-only", "--skip-git-repo-check", "-C", str(self.repo), "--json",
                "--", "-"]
        self.work.mkdir(parents=True, exist_ok=True)
        code, ev, _err = self.run_cli("Run exactly one shell command: Get-Content -TotalCount 1 AGENTS.md . Reply with its "
                                      "output only.", args, self.work, "sheet-acceptor-probe")
        ok = any((x.get("item") or {}).get("type") == "command_execution" and x["item"].get("exit_code") == 0
                 for x in events(ev))
        print(json.dumps(dict(probe_ok=ok, exit=code, exe=str(self.exe))))
        return ok


def default_exe() -> str | None:
    base = Path(os.environ.get("LOCALAPPDATA", "")) / "OpenAI" / "Codex" / "bin"
    exes = sorted(base.glob("*/codex.exe"), key=lambda p: p.stat().st_mtime, reverse=True) if base.is_dir() else []
    return str(exes[0]) if exes else None


def main(argv=None) -> int:
    b.utf8_streams()
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("command", choices=("prepare", "probe", "accept", "all"))
    ap.add_argument("key", nargs="?", help="content-key (prepare/accept)")
    ap.add_argument("cycle", nargs="?", type=int, help="номер цикла N (prepare/accept)")
    ap.add_argument("--work", required=True, help="рабочий каталог пачки (журнал, перепроверки, проба)")
    ap.add_argument("--owned", default=None, help="список своих фигур (по умолчанию <work>/sheet-acceptance-owned.json)")
    ap.add_argument("--log", default=None, help="журнал приёмок (по умолчанию <work>/acceptance-log-1c.jsonl)")
    ap.add_argument("--date", default=dt.date.today().isoformat(), help="дата цикла YYYY-MM-DD (<YYYYMMDD>-sheet-rN)")
    ap.add_argument("--exe", default=None)
    ap.add_argument("--model", default="gpt-6.1-sol")
    ap.add_argument("--effort", default="xhigh")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--user-quote", action="append", default=[], help="дословная цитата задачи пользователя (в промпт)")
    ap.add_argument("--repo", default=str(b.REPO))
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    a.exe = a.exe or default_exe()
    if a.command != "prepare" and not a.exe:
        print("ERROR: нет codex.exe (--exe)", file=sys.stderr)
        return 2
    s = Sheet(a)
    if a.command == "probe":
        return 0 if s.probe() else 1
    owned = Path(a.owned) if a.owned else Path(a.work) / "sheet-acceptance-owned.json"
    try:
        rows = [r for r in data(owned) if r.get("status") == "claimed"]
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if a.command == "all":
        with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
            results = list(pool.map(s.accept, rows))
        write(Path(a.work) / f"sheet-acceptance-results-{s.d8}.json", results)
        return 0
    row = next((r for r in rows if r["key"] == a.key), None)
    if row is None or not a.cycle:
        print(f"ERROR: {a.command}: нужен ключ из своих фигур и номер цикла ({a.key!r}, {a.cycle!r})", file=sys.stderr)
        return 2
    if a.command == "prepare":
        try:
            e, _p, prompt, images = s.prepare(row, a.cycle)
        except (RuntimeError, OSError, KeyError, ValueError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        print(json.dumps({"evidence": s.rel(e), "images": len(images), "prompt_chars": len(prompt)}, ensure_ascii=False))
        return 0
    s.accept(row, a.cycle)
    return 0


if __name__ == "__main__":
    sys.exit(main())
