"""Приёмка листов 1c пачкой (приёмщик «Opus xhigh», второй — «Opus high», через Workflow): предпроверка пакета, промпт по рубрике §11, аргументы workflow, приём карточки validate_card.

С 2026-10-20 Sol и Codex отключены (пользователь отменил подписку ChatGPT; AGENTS.md «AI tools and side models»):
`codex exec` больше не запускается. Команды прежней полосы Sol (accept, all, probe) и `--acceptor sol` падают с кодом 2
и причиной; `--acceptor zcode` («Z-Code GLM-5.3-Flash») — тоже код 2: снят с приёмки 2026-10-21, калибровка не
пройдена (tools/art/acceptance/side_models.py, ZCODE_GONE). По умолчанию — Opus-путь.

concept-sheet.md §11 (рубрика 1c), acceptance-and-blender.md §8.3 (вызов Opus). На фигуру из списка «своих»
(--owned, по умолчанию <work>/sheet-acceptance-owned.json: JSON-список [{"asset_id": "ASSET-BEOWULF-001", "key":
"beowulf", "package": "art/imagegen/concept-beowulf-codex", "status": "claimed"}, …]; берутся только строки
status "claimed"; без файла prepare/prepare-second одной фигуры строят такую строку из <key> сами, C8) в
каталоге <asset-dir>/evidence/acceptance-concept/<YYYYMMDD>-sheet-r<N>/ (нет — создаётся, C8):
  1. preflight — выбранные записи 1c и их копии, ссылки, полный manifest-sha256, UTF-8 без BOM/«????», повтор
     check_concept_views.py --sheet совпадает с checks-report.json пакета, G-CHECKS без FAIL;
  2. prepare — константы карточки (acceptor «Opus xhigh», session_id workflow:acceptor-<ASSET_ID>-r<N>), рубрика §11
     дословно, список изображений (агент открывает их инструментом Read), acceptor-prompt.md; ASCII-аргументы
     workflow second-acceptor для первого приёмщика: <каталог приёмки>/acceptor-args.json и сводный
     <work>/acceptor-args-<YYYYMMDD>.json;
  3. Workflow({name: "second-acceptor", args: <содержимое acceptor-args>}) запускает оркестратор (Claude Code);
  4. finish <вывод workflow> — card.json без строк "null" (finish_second.second_card), validate_card.py --check-files
     (0 или 3 = нужен второй приёмщик), сверка acceptor, G-CHECKS, accepted_object/frames с константами и хэшей пакета
     с prepare, запись в журнал --log. Невалидная карточка уходит в card-invalid-<k>.json: повтор — новый запуск
     workflow по тем же аргументам;
  5. prepare-second (код 3, C10) — промпт второго приёмщика «Opus high» acceptor-prompt-2.md (те же константы и
     файлы, свежий контекст; профиль «Opus high», session_id workflow:acceptor2-<ASSET_ID>-r<N>), ASCII-аргументы
     workflow second-acceptor с effort high: <каталог приёмки>/second-acceptor-args.json и сводный
     <work>/second-acceptor-args-<YYYYMMDD>.json (C34); пакет не изменился с первой приёмки. Вывод workflow →
     finish_second.py (пара «Opus xhigh» + «Opus high» — два профиля, решение пользователя 2026-10-21).
Пакет во время приёмки не меняется (хэши prepare и finish). Был C:/tmp/concept-wave/sheet_acceptance.py.

    python tools/art/pipeline_batch/sheet_acceptance.py prepare <key> <cycle> --work <dir> --date YYYY-MM-DD
    python tools/art/pipeline_batch/sheet_acceptance.py finish <workflow-output.json> --work <dir>
    python tools/art/pipeline_batch/sheet_acceptance.py prepare-second <key> <cycle> --work <dir> --date YYYY-MM-DD
    общие: [--owned <json>] [--log <jsonl>] [--acceptor opus] [--executor-session-id <id запускающего>]
           [--user-quote "дословная цитата задачи"]…

--executor-session-id — фактическая сессия запускающего (concept-sheet.md §11, F40, C9: субагент —
claude-code:<uuid>/agent:<name>); без флага — прежнее launcher:stage-1c-sheet-<YYYYMMDD> и предупреждение.
Траты: нет — приёмщики «Opus xhigh» и «Opus high» не тратят квот сервисов, строки журнала трат нет
(07-prompt-templates.md §3.4).
Код выхода: 0 — команда выполнена (итог каждой фигуры — в журнале), 1 — finish: хотя бы одна карточка не принята,
2 — ошибка входа или отключённый приёмщик (Sol 2026-10-20, Z-Code 2026-10-21).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _batch as b  # noqa: E402
from finish_second import results_of, second_card  # noqa: E402

DELEGATION = ("Делегирование пользователя (2026-10-06, дословно): «Не знаю. Делай сам, меня это не касается. Все решения "
              "принимай».")
SCHEMA = "tools/art/acceptance/asset-acceptance-2.output-concept.schema.json"
LOCK = threading.Lock()
SOL_COMMANDS = ("accept", "all", "probe")  # полоса Sol (codex exec), отключена 2026-10-20


def default_row(key: str) -> dict:
    """Строка «своей» фигуры без файла --owned (C8): ASSET_ID и пакет — по правилу этапа 0 из content-key."""
    return {"asset_id": b.asset_id(key), "key": key, "package": f"art/imagegen/concept-{key}-codex", "status": "claimed"}


def first_label(aid: str, cycle: int) -> str:
    """label workflow первого приёмщика (acceptance-and-blender.md §8.3): acceptor-<ASSET_ID>-r<N>."""
    return f"acceptor-{aid}-r{cycle}"


def second_label(aid: str, cycle: int) -> str:
    """label workflow второго приёмщика (acceptance-and-blender.md §8.3): acceptor2-<ASSET_ID>-r<N>."""
    return f"acceptor2-{aid}-r{cycle}"


def limit_line(limit) -> str:
    """Строка промпта о `verification.json#limit_reached` (concept-sheet.md §5.5 п.5) — только когда список не пуст
    (C13); «<вид>: <пункты>; …»."""
    if not limit:
        return ""
    parts = []
    for x in limit if isinstance(limit, list) else [limit]:
        if isinstance(x, dict):
            items = x.get("failed_items", x.get("items", []))
            items = ", ".join(str(i) for i in items) if isinstance(items, list) else str(items)
            parts.append(f"{x.get('view', '?')}: {items}")
        else:
            parts.append(str(x))
    return ("Генератор исчерпал генерации запуска; проваленные пункты CHECKLIST: " + "; ".join(parts)
            + "; оцени их по рубрике, без автоматического снижения из-за записи исполнителя.\n")


def workflow_args(items: list, kind: str = "concept", first: bool = False) -> dict:
    """Аргументы workflow second-acceptor: items + строгая выходная схема вида без description/title (ASCII, C34)."""
    b.side_models()  # кладёт tools/art/acceptance в sys.path
    import _output_schema  # noqa: E402

    return _output_schema.workflow_args(kind, items, first)


def write_ascii_json(p, obj) -> None:
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=True, indent=2) + "\n", encoding="ascii")


def read(p) -> str:
    return Path(p).read_text(encoding="utf-8-sig")


def data(p):
    return json.loads(read(p))


def write(p, x) -> None:
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(x if isinstance(x, str) else json.dumps(x, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def merge_batch_args(batch: Path, item: dict, first: bool) -> None:
    """Сводный файл аргументов пачки: элемент того же каталога приёмки заменяется (C34)."""
    with LOCK:
        items = json.loads(batch.read_text(encoding="ascii"))["items"] if batch.is_file() else []
        items = [i for i in items if i.get("evidence") != item["evidence"]] + [item]
        write_ascii_json(batch, workflow_args(items, first=first))


class Sheet:
    def __init__(self, a):
        self.a = a
        self.repo = Path(a.repo)
        self.work = Path(a.work)
        self.date = a.date
        self.d8 = a.date.replace("-", "")
        self.log = Path(a.log) if a.log else self.work / "acceptance-log-1c.jsonl"
        # C9: фактический id запускающего (§11, F40); без флага — прежняя строка (обратная совместимость)
        self.executor_session_id = getattr(a, "executor_session_id", None) or f"launcher:stage-1c-sheet-{self.d8}"

    def rel(self, p) -> str:
        return b.rel(p, self.repo)

    def ev_dir(self, aid: str, cycle: int) -> Path:
        return self.repo / "art/pipeline-candidates" / aid / "evidence/acceptance-concept" / f"{self.d8}-sheet-r{cycle}"

    def package_hashes(self, p: Path) -> dict:
        return {self.rel(f): b.sha256(f) for f in p.rglob("*") if f.is_file()}

    # ---------------------------------------------------------------------------------------------- 1. preflight
    def preflight(self, row: dict, cycle: int, tag: str = ""):
        aid, key = row["asset_id"], row["key"]
        p, e = self.repo / row["package"], self.ev_dir(aid, cycle)
        if not (self.repo / "art/pipeline-candidates" / aid).is_dir():
            raise RuntimeError(f"нет каталога ассета art/pipeline-candidates/{aid}")
        e.mkdir(parents=True, exist_ok=True)  # C8: каталог цикла создаётся здесь, заранее его заводить не нужно
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
        actual = {f.resolve() for f in p.rglob("*") if f.is_file() and f != p / "manifest-sha256.json"}
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
        hashes = self.package_hashes(p)
        if tag and (e / "launcher-preflight.json").is_file() \
                and data(e / "launcher-preflight.json").get("package_hashes") != hashes:
            raise RuntimeError("пакет изменился после первой приёмки: второй приёмщик судил бы другие файлы")
        write(e / f"launcher-preflight{tag}.json", dict(selected_records=True, manifest=True, utf8=True, recheck_exit=0,
                                                        recheck_same=True, package_hashes=hashes))
        return p, e, card, cardtext, gens, old

    # ------------------------------------------------------------------------------------------------- 2. prompt
    def prepare(self, row: dict, cycle: int, second: bool = False):
        """Промпт приёмщика (изображения — инструментом Read) и аргументы workflow second-acceptor.
        second=False — первый приёмщик «Opus xhigh» (acceptor-prompt.md, acceptor-args.json, effort xhigh);
        second=True — второй «Opus high», после первой карточки (acceptor-prompt-2.md, second-acceptor-args.json,
        effort high; C10)."""
        if second:
            e0 = self.ev_dir(row["asset_id"], cycle)
            if not (e0 / "card.json").is_file():
                raise RuntimeError(f"нет первой карточки {self.rel(e0 / 'card.json')}: второй приёмщик — после неё")
            if (e0 / "card-2.json").exists():
                raise RuntimeError(f"карточка второго приёмщика уже есть: {self.rel(e0 / 'card-2.json')}")
        p, e, card, cardtext, gens, checks = self.preflight(row, cycle, "-2" if second else "")
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
        sm = b.side_models()
        profile = sm.SECOND if second else sm.FIRST
        label = second_label(aid, cycle) if second else first_label(aid, cycle)
        session = "workflow:" + label
        if second:
            who = (f"Ты — второй независимый приёмщик «{profile}», не исполнитель; первую карточку (card.json) ты не "
                   "видишь и не открываешь.")
        else:
            who = f"Ты — отдельный приёмщик «{profile}», не исполнитель."
        how_images = ("Открой каждый файл как картинку инструментом Read, каждый целиком: к этому промпту "
                      "изображения не приложены. Список изображений:")
        session_line = (f"acceptor.session_id — ровно {session}. Пункт item в rework_fix_list и known_issues — только "
                        "S, C, Q, P или G-CHECKS; пустое необязательное поле — JSON null, не строка \"null\".")
        constants = dict(schema="unmatched.concept-acceptance/1", kind="concept", asset_id=aid, clip=None,
                         cycle=f"r{cycle}", date=self.date, previous_card=prev,
                         accepted_object=[dict(path=self.rel(f), sha256=b.sha256(f)) for f in views],
                         frames=dict(dir=self.rel(p), files=[f"sheet-{key}.png"] + [f.name for f in views]
                                     + ["checks-report.json"]),
                         reports=[self.rel(p / f) for f in ("checks-report.json", "generation-records.json",
                                                            "verification.json")],
                         acceptor=dict(profile=profile, session_id=session),
                         executor_session_id=self.executor_session_id,
                         decided_by="delegated (ВР-реестр 2026-10-06)")
        rubric = read(self.repo / b.SKILL)
        rubric = rubric[rubric.index("## 11."):rubric.index("## 12.")]
        quotes = "".join(f"Задача пользователя (дословно): «{q}».\n" for q in self.a.user_quote)
        limit = limit_line(data(p / "verification.json").get("limit_reached", []))
        prompt = f"""# Приёмка 1c sheet {aid}, цикл r{cycle}
{DELEGATION}
{quotes}Траты на приёмке: нет. {who} Файлы не правишь, ничего не генерируешь, не запускаешь validate_card.py, Blender, git, Unreal, Tripo, SYNTX, Gemini, браузер или других агентов.
Твоя единственная выдача — JSON-карточка (структурный вывод). Её сохраняет запускающий. Текстовые файлы открывай инструментом Read (UTF-8). Если кириллица всё равно пришла кракозябрами — это сбой окружения: не оценивай по догадкам, верни карточку, где verdict_reason начинается со слов «СБОЙ ОКРУЖЕНИЯ: кириллица не читается» (concept-sheet.md §11, RA-03). Не читай посторонние карточки, чаты или пакеты.
Ты — приёмщик этапа 1 скилла 3d-model-pipeline (концепт-лист). Объект: 1c виды {key}-front/side/back.png и лист sheet-{key}.png пакета {self.rel(p)}.
{how_images}
{json.dumps([self.rel(f) for f in images], ensure_ascii=False, indent=2)}
Эталон качества: {qref}. Для 1c — утверждённый дизайн {self.rel(p / 'design' / f'{key}-front.png')} и ортопроекции 1b {self.rel(orthodirs[0])}. ortho_right — дополнительный вид того же черновика; SIDE_VIEW заявки задаёт сторону принимаемого side.
Прочитай {self.rel(p / 'checks-report.json')}, {self.rel(p / 'generation-records.json')}, {self.rel(p / 'verification.json')}, {self.rel(p / 'palette.json')}, {self.rel(card)} и {self.rel(orthodirs[0] / 'ortho-framing.json')}. Предыдущая карточка: {prev}; на r2 проверь закрытие её списка, а баллы ставь заново.
Выдержка карточки ассета (DESCRIPTION_EN, ANCHORS_EN, PALETTE, ANATOMY, WEAPON_HAND, SIDE_VIEW):
{cardtext}
Рубрика: concept-sheet.md §11, полный раздел:
{rubric}
Применяй рубрику 1c, четыре числовых измерения S,C,Q,P. C здесь оценивается по согласованности всех трёх видов; фиксированный C 1.5 относится только к 1a.
T- или A-поза = S 0. Балл по якорям, шаг 0.5; обоснование с именами файлов из frames.files. G-CHECKS единственный гейт: checks-report.json#summary.FAIL = {checks['summary']['FAIL']}; source строго {self.rel(p / 'checks-report.json')}. WARN не гейт, учитывай их в C.
rework_fix_list — только измерения <2 и G-CHECKS при FAIL; пункт item, frame (имя вида из frames.files), fix (одна английская строка для CORRECTION), tool (Gemini 1c CORRECTION | Tripo 1b черновик | Gemini 1a). При не-pass список должен покрывать каждое измерение ниже 2 и FAIL гейта. При pass [] и замечания в known_issues. known_issues.item только S,C,Q,P,G-CHECKS.
Причину, уже присутствующую в орто, направляй tool Tripo 1b черновик; ошибку в самом approved design — Gemini 1a. Для поверхностной детали, рамки или ракурса одного вида — Gemini 1c CORRECTION. Укажи конкретный дефектный вид, не назначай слепую перегенерацию.
score half-up: sum(S,C,Q,P)/8*10. Гейт FAIL, любое значение <1 или score <8 => return_to_stage_1, иначе pass; r4 без pass => escalate_user. При не-pass заполни verdict_reason.
Заполни все поля таблицы Карточка §11; обязательные константы (скопировать без изменения):
{json.dumps(constants, ensure_ascii=False, indent=2)}
При pass status_note содержит «художественно принято, по делегированию (docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md)».
В строгой схеме необязательные поля представлены null. {session_line}
{limit}Верни только JSON карточки по {SCHEMA}.
"""
        if "{{" in prompt:
            raise RuntimeError("незаполненный плейсхолдер")
        tag = "-2" if second else ""
        write(e / f"acceptor-prompt{tag}.md", prompt)
        write(e / f"launcher-inputs{tag}.json", dict(images=[self.rel(f) for f in images], constants=constants))
        item = dict(asset=aid, evidence=self.rel(e), label=label, prompt=self.rel(e / f"acceptor-prompt{tag}.md"))
        name = "second-acceptor-args" if second else "acceptor-args"
        write_ascii_json(e / f"{name}.json", workflow_args([item], first=not second))
        merge_batch_args(self.work / f"{name}-{self.d8}.json", item, first=not second)
        return e, p, prompt, images

    # ------------------------------------------------------------------------------------------------- 4. finish
    def append(self, row, cycle, score, verdict, validate_exit, card, notes="") -> dict:
        rec = dict(asset_id=row["asset_id"], cycle=f"r{cycle}", score=score, verdict=verdict, validate_exit=validate_exit,
                   card_path=self.rel(card) if card else None, notes=notes)
        with LOCK:
            self.log.parent.mkdir(parents=True, exist_ok=True)
            with self.log.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec

    def finish(self, item: dict) -> dict:
        """Карточка первого приёмщика из вывода workflow → card.json + validate_card --check-files + сверки (п.4)."""
        e = self.repo / item["evidence"]
        m = re.search(r"-sheet-r(\d+)$", e.name)
        cycle = int(m[1]) if m else 0
        row = {"asset_id": item.get("asset") or e.parents[2].name}  # <aid>/evidence/acceptance-concept/<цикл>
        out = e / "card.json"
        try:
            if not m:
                raise RuntimeError(f"каталог приёмки не <YYYYMMDD>-sheet-r<N>: {item['evidence']}")
            if out.exists():
                raise RuntimeError(f"карточка уже есть: {self.rel(out)}")
            if not (e / "launcher-inputs.json").is_file() or not (e / "launcher-preflight.json").is_file():
                raise RuntimeError("нет launcher-inputs.json / launcher-preflight.json: сначала prepare")
            const = data(e / "launcher-inputs.json")["constants"]
            obj = second_card(item["card"])
            if obj.get("acceptor") != const["acceptor"]:
                raise RuntimeError(f"acceptor {obj.get('acceptor')} ≠ константе {const['acceptor']}")
            if obj.get("accepted_object") != const["accepted_object"] or obj.get("frames") != const["frames"]:
                raise RuntimeError("объект или кадры отличаются от §11")
            p = self.repo / const["frames"]["dir"]
            if data(e / "launcher-preflight.json")["package_hashes"] != self.package_hashes(p):
                raise RuntimeError("пакет изменился после prepare: приёмщик судил другие файлы")
            write(out, obj)
            val = b.run([sys.executable, "-X", "utf8", "tools/art/acceptance/validate_card.py", self.rel(out),
                         "--print-verdict", "--check-files"], self.repo)
            write(e / "validate.txt", val.stdout + val.stderr)
            if val.returncode not in (0, 3):
                k = 1
                while (e / f"card-invalid-{k}.json").exists():
                    k += 1
                out.rename(e / f"card-invalid-{k}.json")
                rec = self.append(row, cycle, obj.get("score"), "card_invalid", val.returncode, e / f"card-invalid-{k}.json",
                                  "карточка невалидна: повтор workflow по acceptor-args.json; "
                                  + ((val.stdout + val.stderr).strip().splitlines() or [""])[-1])
                print("INVALID", json.dumps(rec, ensure_ascii=False), flush=True)
                return rec
            expected = "PASS" if data(p / "checks-report.json")["summary"]["FAIL"] == 0 else "FAIL"
            if obj["gates"]["G-CHECKS"]["status"] != expected:
                raise RuntimeError("гейт G-CHECKS противоречит отчёту")
            notes = ""
            if val.returncode == 3:
                notes = ("нужен второй приёмщик: prepare-second → Workflow second-acceptor (Opus high, effort high, "
                         "свежий контекст) → finish_second.py")
                write(e / "note.md", notes + "\n")
            elif obj["verdict"] == "return_to_stage_1" and (p / "README.md").is_file() \
                    and "unstability.ai" in read(p / "README.md").lower():
                notes = "нужна доработка — виды лицензированной фигуры делаются вне Gemini (unstability.ai)"
                write(e / "note.md", notes + "\n\n" + json.dumps(obj["rework_fix_list"], ensure_ascii=False,
                                                                 indent=2) + "\n")
            rec = self.append(row, cycle, obj["score"], obj["verdict"], val.returncode, out, notes)
            print("DONE", json.dumps(rec, ensure_ascii=False), flush=True)
            return rec
        except Exception as exc:  # noqa: BLE001 - фигура блокируется, пачка идёт дальше
            if e.is_dir():
                write(e / "launcher-error.txt", str(exc) + "\n")
            rec = self.append(row, cycle, None, "launcher_blocked", None, None, str(exc))
            print("BLOCKED", json.dumps(rec, ensure_ascii=False), flush=True)
            return rec


def main(argv=None) -> int:
    b.utf8_streams()
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("command", choices=("prepare", "finish", "prepare-second") + SOL_COMMANDS)
    ap.add_argument("key", nargs="?", help="content-key (prepare/prepare-second) или вывод workflow (finish)")
    ap.add_argument("cycle", nargs="?", type=int, help="номер цикла N (prepare/prepare-second)")
    ap.add_argument("--work", required=True, help="рабочий каталог пачки (журнал, перепроверки, аргументы workflow)")
    ap.add_argument("--owned", default=None,
                    help="JSON-список своих фигур [{asset_id, key, package, status: \"claimed\"}] (по умолчанию "
                         "<work>/sheet-acceptance-owned.json; для одной фигуры можно без файла)")
    ap.add_argument("--log", default=None, help="журнал приёмок (по умолчанию <work>/acceptance-log-1c.jsonl)")
    ap.add_argument("--date", default=dt.date.today().isoformat(), help="дата цикла YYYY-MM-DD (<YYYYMMDD>-sheet-rN)")
    ap.add_argument("--acceptor", default="opus", choices=("opus", "zcode", "sol"),
                    help="приёмщик: opus — «Opus xhigh» через Workflow (по умолчанию; prepare-second — «Opus "
                         "high»); zcode — снят с приёмки 2026-10-21; sol — отключён 2026-10-20")
    ap.add_argument("--executor-session-id", default=None,
                    help="фактическая сессия запускающего для executor_session_id карточки (§11, F40; "
                         "субагент — claude-code:<uuid>/agent:<name>)")
    ap.add_argument("--user-quote", action="append", default=[], help="дословная цитата задачи пользователя (в промпт)")
    ap.add_argument("--repo", default=str(b.REPO))
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    sm = b.side_models()
    if a.command in SOL_COMMANDS or a.acceptor == "sol":
        print(f"ERROR: {a.command}: {sm.SOL_GONE}. Opus-путь: prepare <key> <N> → Workflow second-acceptor по "
              "<каталог приёмки>/acceptor-args.json → finish <вывод workflow>.", file=sys.stderr)
        return 2
    if a.acceptor == "zcode":
        print(f"ERROR: {a.command}: {sm.ZCODE_GONE}.", file=sys.stderr)
        return 2
    s = Sheet(a)
    if a.command == "finish":
        if not a.key:
            print("ERROR: finish: нужен файл вывода workflow", file=sys.stderr)
            return 2
        try:
            res = results_of(json.loads(Path(a.key).read_text(encoding="utf-8-sig")))
        except (OSError, ValueError, KeyError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        recs = [s.finish(r) for r in res]
        return 0 if all(r["verdict"] not in ("card_invalid", "launcher_blocked") for r in recs) else 1
    if not a.executor_session_id:
        print(f"WARN: --executor-session-id не задан: executor_session_id = {s.executor_session_id} (§11 ждёт "
              "фактический id запускающего, F40)", file=sys.stderr)
    owned = Path(a.owned) if a.owned else Path(a.work) / "sheet-acceptance-owned.json"
    try:
        if not owned.is_file() and not a.owned and a.key:
            rows = [default_row(a.key)]  # C8: одна фигура без файла своих
        else:
            rows = [r for r in data(owned) if r.get("status") == "claimed"]
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    row = next((r for r in rows if r["key"] == a.key), None)
    if row is None or not a.cycle:
        print(f"ERROR: {a.command}: нужен ключ из своих фигур и номер цикла ({a.key!r}, {a.cycle!r})", file=sys.stderr)
        return 2
    second = a.command == "prepare-second"
    try:
        e, _p, prompt, images = s.prepare(row, a.cycle, second=second)
    except (RuntimeError, OSError, KeyError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    name = "second-acceptor-args" if second else "acceptor-args"
    tag = "-2" if second else ""
    out = {"evidence": s.rel(e), "images": len(images), "prompt_chars": len(prompt),
           "prompt": s.rel(e / f"acceptor-prompt{tag}.md"), "args": s.rel(e / f"{name}.json"),
           "batch_args": (Path(a.work) / f"{name}-{s.d8}.json").as_posix()}
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
