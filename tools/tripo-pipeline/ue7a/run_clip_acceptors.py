"""Шаг 7a.2: приёмщики клипов «Opus xhigh» и второй «Opus high» (Workflow second-acceptor) по каталогу цикла prep_acceptance.py + validate_card.

С 2026-10-20 Sol и Codex отключены (пользователь отменил подписку ChatGPT; AGENTS.md «AI tools and side models»):
`codex exec` больше не запускается, `--acceptor sol` падает с кодом 2 и причиной; `--acceptor zcode`
(«Z-Code GLM-5.3-Flash») — тоже код 2: снят с приёмки 2026-10-21, калибровка не пройдена
(tools/art/acceptance/side_models.py, ZCODE_GONE). По умолчанию — Opus-путь в два шага: подготовка (без --finish) и
приём карточек (--finish).

Замена run-acceptor.ps1, который этап 6 должен был оставить рядом с заготовками, а исполнитель 7a писал руками
(находка C51 фигуры-проверки Beowulf 2026-10-14). Вход — каталог цикла <E> = <asset-dir>/evidence/acceptance-anim/
<YYYYMMDD>-rN (prep_acceptance.py): в <E>/<Clip>/ лежат acceptor-prompt.md и frames/. На клип:
  1. промпт: константа `executor_session_id "…"` — фактический id исполнителя клипов (--executor-session-id, RA-21;
     C32/C55: заготовка этапа 6 несла выдуманный «agent:stage6-<key>» вместо имени агента); константа
     `acceptor {"profile": …, "session_id": …}` (заготовки до 2026-10-20 несли «Sol 6.1 xhigh» / «codex:pending») —
     «Opus xhigh» / «workflow:acceptor-<ASSET_ID>-<Clip>-r<N>[<tag>]»; после них — ни одного незаполненного {{…}}.
     Отличается — промпт переписывается на месте (запись в acceptor-launch.json); id исполнителя не дан — WARNING;
  2. изображения: каждый файл <E>/<Clip>/frames/ (*.jpg, *.png) и каждый существующий файл .png/.jpg, путь которого
     (от корня репо) назван в промпте вне frames/ — образец библиотеки (art/animation-refs/…/contact-sheet-2fps.png),
     лист концепта приёмки модели, вид концепта, эталон качества; --image — ещё файлы, --no-prompt-images — только
     frames/. Список дописывается в конец промпта блоком «## Изображения приёмщику» (агент открывает их инструментом
     Read; прежде они шли в codex отдельными -i);
  3. подготовка пишет <E>/acceptor-args<tag>.json — ASCII-аргументы Workflow({name: "second-acceptor", args: …}) для
     первого приёмщика (kind anim, по элементу на клип, строгая схема …output-anim без description/title).
     Workflow запускает оркестратор (Claude Code), его вывод сохраняет в файл;
  4. --finish <вывод workflow> (голый список, {"result": [...]} или один элемент): card<tag>.json без строк "null";
     acceptor карточки = константе промпта, executor_session_id = константе промпта;
  5. validate_card.py <card> --print-verdict --check-files → validator-output.txt; код 0 — карточка верна, 3 — pass
     8,0–8,4: нужен второй приёмщик (шаг 6), 1 — нет;
  6. --second (код 3 у клипа; acceptance-and-blender.md §8.5) — второй приёмщик «Opus high» (решение пользователя
     2026-10-21): из acceptor-prompt.md клипа — acceptor-prompt-2.md с константой acceptor «Opus high» /
     «workflow:acceptor2-<ASSET_ID>-<Clip>-r<N>» и тем же блоком изображений, затем <E>/second-acceptor-args.json —
     аргументы того же workflow с effort high (свежий контекст). Нужна первая карточка card.json клипа; вывод workflow
     → tools/art/pipeline_batch/finish_second.py (card-2.json и пара validate_card --second без --same-profile-ok).
Итог --finish и --validate-only — <E>/acceptors-run<tag>.json и таблица в stdout.

    python tools/tripo-pipeline/ue7a/run_clip_acceptors.py --evidence <asset-dir>/evidence/acceptance-anim/20261014-r1 \\
        --executor-session-id "claude-code:<uuid>/agent:<имя агента этапа 6>" [--clips Idle,LungeAttack] [--dry-run]
    … --finish <вывод workflow.json>  # карточки первого приёмщика → card.json + validate_card
    … --validate-only                 # только validate_card по готовым карточкам
    … --tag=-b [--force]              # повтор: card-b.json и т. д.; --force — перезаписать карточку
    … --second --clips Idle           # второй приёмщик «Opus high» → second-acceptor-args.json → finish_second.py

Траты: нет — приёмщики «Opus xhigh» и «Opus high» не тратят квот сервисов (строки журнала трат нет).
Код выхода: 0 — подготовка сделана / все карточки верны (validate 0 или 3), 1 — есть неверная карточка / нет карточки
клипа в выводе workflow / чужой acceptor или executor_session_id, 2 — ошибка входа (нет каталога, промпта, кадров;
карточка уже есть; у --second нет первой карточки; отключённый приёмщик Sol или Z-Code).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ue7a as c  # noqa: E402

sys.path.insert(0, str(c.REPO / "tools/art/acceptance"))
sys.path.insert(0, str(c.REPO / "tools/art/pipeline_batch"))
import _output_schema  # noqa: E402
import side_models as sm  # noqa: E402
from finish_second import results_of, second_card  # noqa: E402

VALIDATE = "tools/art/acceptance/validate_card.py"
EXEC_RE = re.compile(r'executor_session_id "([^"]*)"')
ACC_RE = re.compile(r'acceptor \{"profile": "([^"]*)", "session_id": "([^"]*)"\}')
IMG_RE = re.compile(r'(?<![\w./-])((?:art|docs|tools|unreal)/[^\s"\'`,;()\[\]{}<>]+?\.(?:png|jpe?g))(?![\w-])', re.I)
FRAME_EXT = (".jpg", ".jpeg", ".png")
SESSION_RE = re.compile(r"^[a-z][a-z0-9-]*:\S+$")
SECOND = ".claude/workflows/second-acceptor.js (acceptance-and-blender.md §8.5)"
IMAGES_HEAD = "## Изображения приёмщику"


class InputError(Exception):
    pass


def now() -> str:
    return dt.datetime.now().astimezone().replace(microsecond=0).isoformat()


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


def acceptor_fix(text: str, want: dict) -> tuple[str, dict]:
    """(текст, запись) — константа acceptor {"profile", "session_id"} промпта, переписанная на want (Opus, workflow:…).
    Константы нет — промпт не меняется (профиль и сессию задаёт и задание агента workflow); больше одной — ошибка."""
    found = ACC_RE.findall(text)
    if len(found) > 1:
        raise InputError(f"в промпте {len(found)} констант acceptor {{…}} (нужна одна)")
    rec = {"prompt": dict(zip(("profile", "session_id"), found[0])) if found else None, "used": want,
           "rewritten": False}
    if found and rec["prompt"] != want:
        text = ACC_RE.sub(lambda _m: 'acceptor {"profile": "%s", "session_id": "%s"}'
                          % (want["profile"], want["session_id"]), text)
        rec["rewritten"] = True
    return text, rec


def with_images(text: str, images: list, repo: Path) -> str:
    """Промпт с блоком «## Изображения приёмщику» в конце (прежний блок заменяется). Текст — с концами строк \\n
    (read_text), при записи они становятся концами строк файла."""
    i = text.find(IMAGES_HEAD)
    body = (text[:i] if i >= 0 else text).rstrip("\n")
    paths = [c.rel(p, repo) if p.resolve().is_relative_to(repo.resolve()) else p.as_posix() for p in images]
    lines = [IMAGES_HEAD, "Открой каждый файл как картинку инструментом Read, каждый целиком (к промпту изображения не "
                          "приложены):"] + [f"- {x}" for x in paths]
    return body + "\n\n" + "\n".join(lines) + "\n"


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


def run_validate(card: Path, repo: Path) -> tuple[int, str, str]:
    """validate_card.py --print-verdict --check-files → (код, stdout, stderr)."""
    p = subprocess.run([sys.executable, "-X", "utf8", str(repo / VALIDATE), str(card), "--print-verdict",
                        "--check-files"], cwd=repo, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return p.returncode, p.stdout, p.stderr


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


def asset_of(e: Path) -> str:
    """ASSET_ID каталога цикла <asset-dir>/evidence/acceptance-anim/<YYYYMMDD>-rN."""
    return e.parents[2].name


def plan_clip(e: Path, clip: str, a, repo: Path) -> dict:
    """План клипа. a.second — второй приёмщик «Opus high»: промпт-источник тот же (acceptor-prompt.md), пишется
    acceptor-prompt-2.md, карточка — card-2.json (finish_second.py)."""
    cdir = e / clip
    second = bool(getattr(a, "second", False))
    pp = prompt_path(cdir, a.tag)
    if not pp.is_file():
        raise InputError(f"{clip}: нет промпта {pp} (prep_acceptance.py)")
    text = pp.read_text(encoding="utf-8-sig")
    nl = "\r\n" if b"\r\n" in pp.read_bytes() else "\n"  # переписанный промпт — с концами строк файла
    label = _output_schema.default_label(asset_of(e), c.rel(cdir, repo) if cdir.resolve().is_relative_to(
        repo.resolve()) else cdir.as_posix(), "acceptor2" if second else "acceptor") + a.tag
    want = {"profile": sm.SECOND if second else sm.FIRST, "session_id": "workflow:" + label}
    text, acc_rec = acceptor_fix(text, want)
    left = sorted(set(re.findall(r"\{\{[A-Z_0-9]+\}\}", text)))
    if left:
        raise InputError(f"{clip}: в промпте не заполнены {left} (prep_acceptance.py)")
    text, exe_rec = executor_fix(text, a.executor_session_id)
    card = cdir / ("card-2.json" if second else f"card{a.tag}.json")
    plan = {"clip": clip, "dir": cdir, "prompt": pp, "out_prompt": cdir / "acceptor-prompt-2.md" if second else pp,
            "text": text, "executor": exe_rec, "acceptor": acc_rec, "label": label, "card": card, "images": [],
            "nl": nl}
    if a.validate_only:
        if not card.is_file():
            raise InputError(f"{clip}: --validate-only, а карточки {card.name} нет")
        return plan
    if second and not (cdir / "card.json").is_file():
        raise InputError(f"{clip}: --second, а первой карточки card.json нет — второй приёмщик идёт после неё")
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
    plan["images"] = images
    plan["text"] = with_images(text, images, repo)
    return plan


def check_card(p: dict, repo: Path, rec: dict, t0: float) -> dict:
    """executor_session_id карточки = константе промпта, затем validate_card --check-files."""
    card = p["card"]
    obj = json.loads(card.read_text(encoding="utf-8-sig"))
    rec.update(score=obj.get("score"), verdict=obj.get("verdict"),
               acceptor_session=(obj.get("acceptor") or {}).get("session_id"))
    if obj.get("executor_session_id") != p["executor"]["used"]:
        rec.update(status="executor_mismatch", card_executor=obj.get("executor_session_id"),
                   elapsed_s=round(time.time() - t0, 1))
        return rec
    vcode, vout, verr = run_validate(card, repo)
    (p["dir"] / f"validator-output{p['tag']}.txt").write_text(verr + vout, encoding="utf-8", newline="\n")
    rec.update(validate_exit=vcode, computed_verdict=(vout.strip().splitlines() or [None])[-1],
               status={0: "valid", 3: "needs_second_acceptor"}.get(vcode, "invalid"),
               elapsed_s=round(time.time() - t0, 1))
    return rec


def card_rec(p: dict, repo: Path) -> dict:
    card = p["card"]
    return {"clip": p["clip"], "card": c.rel(card, repo) if card.resolve().is_relative_to(repo.resolve()) else
            card.as_posix(), "executor_session_id": p["executor"], "images": len(p["images"]), "started": now()}


def finish_clip(p: dict, card_obj: dict | None, workflow_out: str, repo: Path) -> dict:
    """Карточка клипа из вывода workflow → card<tag>.json, acceptor-launch<tag>.json и проверка (шаги 4–5)."""
    rec, t0 = card_rec(p, repo), time.time()
    if card_obj is None:
        rec.update(status="no_card", elapsed_s=0.0)
        return rec
    obj = second_card(card_obj)
    launch = {"schema": "unmatched.clip-acceptor-launch/2", "clip": p["clip"], "acceptor": p["acceptor"],
              "label": p["label"], "workflow_output": workflow_out, "prompt": p["prompt"].name,
              "executor_session_id": p["executor"]}
    if obj.get("acceptor") != p["acceptor"]["used"]:
        launch["status"] = "acceptor_mismatch"
        write_json(p["dir"] / f"acceptor-launch{p['tag']}.json", launch)
        rec.update(status="acceptor_mismatch", card_acceptor=obj.get("acceptor"), elapsed_s=0.0)
        return rec
    p["card"].write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    write_json(p["dir"] / f"acceptor-launch{p['tag']}.json", launch)
    return check_card(p, repo, rec, t0)


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
    ap.add_argument("--acceptor", default="opus", choices=("opus", "zcode", "sol"),
                    help="приёмщик: opus — «Opus xhigh» через Workflow (по умолчанию; --second — «Opus high»); "
                         "zcode — снят с приёмки 2026-10-21; sol — отключён 2026-10-20")
    ap.add_argument("--second", action="store_true",
                    help="второй приёмщик «Opus high» (код 3): acceptor-prompt-2.md и <E>/second-acceptor-args.json "
                         "(effort high); вывод workflow — finish_second.py")
    ap.add_argument("--finish", default=None, help="вывод Workflow second-acceptor: карточки → card<tag>.json")
    ap.add_argument("--tag", default="", help="суффикс файлов повтора: card<tag>.json, acceptor-args<tag>.json …")
    ap.add_argument("--force", action="store_true", help="перезаписать существующую карточку")
    ap.add_argument("--validate-only", action="store_true", help="только validate_card по готовым карточкам")
    ap.add_argument("--dry-run", action="store_true", help="план: изображения и id исполнителя, ничего не писать")
    ap.add_argument("--repo", default=str(c.REPO))
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    if a.acceptor == "sol":
        print(f"ERROR: {sm.SOL_GONE}. Opus-путь: без --finish — аргументы Workflow second-acceptor "
              "(<E>/acceptor-args.json), затем --finish <вывод workflow>.", file=sys.stderr)
        return 2
    if a.acceptor == "zcode":
        print(f"ERROR: {sm.ZCODE_GONE}.", file=sys.stderr)
        return 2
    if a.second and (a.finish or a.validate_only or a.tag):
        print("ERROR: --second — только подготовка второго приёмщика, без --finish, --validate-only и --tag: вывод "
              "workflow принимает tools/art/pipeline_batch/finish_second.py (card-2.json и пара --second)",
              file=sys.stderr)
        return 2
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
        for p in plans:
            p["tag"] = a.tag
        results = None
        if a.finish:
            results = results_of(json.loads(c.resolve(a.finish, repo).read_text(encoding="utf-8-sig")))
    except (InputError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if not a.executor_session_id:
        for p in plans:
            print(f"WARNING: {p['clip']}: executor_session_id из промпта {p['executor']['prompt']!r} — проверь, что это "
                  "фактический id исполнителя клипов (C32/C55), иначе --executor-session-id", file=sys.stderr)
    if a.dry_run:
        acceptor = sm.SECOND if a.second else sm.FIRST
        print(json.dumps({"dry_run": True, "evidence": e.as_posix(), "acceptor": acceptor,
                          "clips": {p["clip"]: {"prompt": p["prompt"].name, "executor_session_id": p["executor"],
                                                "acceptor": p["acceptor"], "label": p["label"],
                                                "card": p["card"].name,
                                                "images": [i.as_posix() for i in p["images"]]} for p in plans}},
                         ensure_ascii=False, indent=1))
        return 0
    if not a.validate_only and results is None:  # подготовка Opus-пути: промпты и аргументы workflow
        items = []
        for p in plans:
            out = p["out_prompt"]
            if not out.is_file() or p["text"] != out.read_text(encoding="utf-8-sig"):
                out.write_text(p["text"], encoding="utf-8", newline=p["nl"])
            items.append({"asset": asset_of(e), "evidence": c.rel(p["dir"], repo), "label": p["label"],
                          "prompt": c.rel(out, repo)})
        args_file = e / ("second-acceptor-args.json" if a.second else f"acceptor-args{a.tag}.json")
        args_file.write_text(json.dumps(_output_schema.workflow_args("anim", items, first=not a.second),
                                        ensure_ascii=True, indent=2) + "\n", encoding="ascii", newline="\n")
        for p in plans:
            print("%-12s %-40s images %d" % (p["clip"], p["label"], len(p["images"])))
        then = "tools/art/pipeline_batch/finish_second.py <файл>" if a.second else "--finish <файл>"
        print(f"NEXT: Workflow({{name: \"second-acceptor\", args: <{c.rel(args_file, repo)}>}}) → вывод в файл → "
              f"{then}")
        return 0
    started = now()
    if a.validate_only:
        res = [check_card(p, repo, card_rec(p, repo), time.time()) for p in plans]
    else:
        by_dir = {c.resolve(r["evidence"], repo).resolve(): r["card"] for r in results}
        res = [finish_clip(p, by_dir.get(p["dir"].resolve()), a.finish, repo) for p in plans]
    summary = {"schema": "unmatched.clip-acceptors-run/2", "evidence": e.as_posix(), "started": started,
               "finished": now(), "mode": "validate-only" if a.validate_only else "workflow",
               "acceptor": sm.FIRST, "workflow_output": a.finish, "tag": a.tag,
               "executor_session_id": a.executor_session_id, "clips": {r["clip"]: r for r in res}}
    write_json(e / f"acceptors-run{a.tag}.json", summary)
    for r in res:
        print("%-12s %-22s score %-5s verdict %-16s validate %s" % (
            r["clip"], r["status"], r.get("score"), r.get("verdict"), r.get("validate_exit")))
    need = [r["clip"] for r in res if r["status"] == "needs_second_acceptor"]
    if need:
        print(f"NEED-SECOND: pass 8,0–8,4 — второй приёмщик «{sm.SECOND}» (effort high, свежий контекст): "
              f"--second --clips {','.join(need)} → {SECOND} по <E>/second-acceptor-args.json → finish_second.py")
    return 0 if all(r["status"] in ("valid", "needs_second_acceptor") for r in res) else 1


if __name__ == "__main__":
    sys.exit(main())
