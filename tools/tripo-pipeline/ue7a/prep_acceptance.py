"""Шаг 7a.2: каталог приёмки клипов цикла rN — копии кадров в <E>/<Clip>/frames/, заполненный промпт приёмщика и run-acceptor.ps1.

Источник промпта — заготовка этапа 6 `<asset-dir>/evidence/acceptance-anim-prompts/<Clip>/acceptor-prompt.md` с
плейсхолдерами {{E}}, {{DATE}}, {{CYCLE}}, {{PREVIOUS_CARD_JSON}}, {{FRAMES_FILES_JSON}}, {{KNOWN_LIMITS}} и служебным
комментарием <!-- … --> (удаляется). Пары `"path": …, "sha256": …` промпта сверяются с текущими файлами: перепечённый
клип без --refresh-sha — ошибка (не приёмка устаревшего объекта). Перед строкой «- Контакт:» / «- Клип:» / «- Отчёты:»
вставляется заметка о меше-носителе UE-кадров (своя — --carrier-note-file, {E} подставляется).
Пилот 2026-10-14: prep_acceptance.py (Leshen, Achilles r1) и prep_acceptance_r2.py (Achilles r2) — evidence/stage7a.

Известные пределы фигуры (F141, F156; animation-vfx-sfx.md §10.5): один список на фигуру —
`<asset-dir>/evidence/acceptance-anim-prompts/known-limits.md` (свой файл — --known-limits). Текст файла (комментарии
<!-- … --> убираются; пустой файл = «нет») подставляется вместо {{KNOWN_LIMITS}} во все заготовки героя; правка списка
(в т. ч. закрытые поздним фиксом пункты) — только в этом файле. Заготовка с {{KNOWN_LIMITS}} без файла — ошибка;
заготовка без плейсхолдера (пилот: блок вписан текстом) работает как раньше, с WARNING, если файл есть.

Кадры (ДС-8, RC-22/F97; ревью 2026-10-14, R-03): копия в frames/ — не больше 1200 px по длинной стороне (--max-px),
JPEG качество 92 (PNG остаётся PNG), имена прежние; кадр не больше предела копируется байт в байт, оригиналы в <run>
не трогаются. Листы шире предела (UE-лист до 4200 × 1860, Blender-лист 1680 × 2520) тоже уменьшаются целиком, а не
режутся на части: лист — обзор движения, детали — в покадровых UE-кадрах и крупных планах того же клипа; лист остаётся
одним файлом с прежним именем, и циклы r2+ (имена из frames.files прошлой карточки) находят те же имена. --max-px 0 —
копия как есть (прежнее поведение).

Кадры r1 (animation-vfx-sfx.md §10.3), из <run>/preview: `<Key>-<Clip>-blender-sheet.jpg`,
closeups-blender/`<Key>-<Clip>-*.jpg`, ue/`<Key>-<Clip>-fNN-<view>-ue-editor.jpg` по key_frames спеки и --ue-views,
у LungeAttack ещё ue/`<Key>-LungeAttack-f*-closeup-ue-editor.jpg`, и `<Key>-H2Anim-ue-sheet.jpg`.
Цикл r2+ (--previous <каталог прошлого цикла>): список кадров — frames.files карточки прошлого цикла (те же кадры,
снятые с нового прогона --run), previous_card = <prev>/<Clip>/card.json; правки текста — --replace OLD=NEW.

    python tools/tripo-pipeline/ue7a/prep_acceptance.py --asset-dir art/pipeline-candidates/ASSET-ACHILLES-001 \
        --key Achilles --run <asset-dir>/20261014-h2anim --spec <asset-dir>/build-profiles/achilles-h2anim.json \
        --date 2026-10-14 --cycle r1 [--clips LungeAttack,Idle] [--known-limits FILE] [--max-px 1200] [--dry-run]
    … --cycle r2 --previous <asset-dir>/evidence/acceptance-anim/20261014-r1 --run <…-h2anim-r3> \
        --replace "<asset-dir>/20261014-h2anim/=<asset-dir>/20261014-h2anim-r3/" --refresh-sha

Код выхода: 0 — готово (или план в --dry-run), 2 — нет кадра/заготовки/списка пределов, плейсхолдер не заполнен, sha
расходится, кадр не читается как картинка.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ue7a as c  # noqa: E402

MARKERS = ("- Контакт:", "- Клип:", "- Отчёты:")
PAIR_RE = re.compile(r'"path": "([^"]+)", "sha256": "([0-9a-f]{64})"')
LIGHT_PINNED = "ASSET-HARPY-001/20260929-h3ld-ue/review/b3.2/review-b3.2.json"
KNOWN_LIMITS = "{{KNOWN_LIMITS}}"
KNOWN_LIMITS_FILE = "known-limits.md"
REVIEW_PX, JPEG_QUALITY = 1200, 92  # ДС-8 (HANDBOOK §8 «JPEG 1200 px q92»), как у capture_acceptance_set.py


class PrepError(Exception):
    pass


def default_carrier_note(key: str, stage: str = "H2LD", light: str = LIGHT_PINNED) -> str:
    p = c.hero_paths(key, stage)
    return (f"- UE-кадры (`*-ue-editor.jpg`, лист `{key}-H2Anim-ue-sheet.jpg`) сняты инструментом `h2anim_ue.py frames` "
            f"на меше-носителе `{p['carrier']}` (геометрия H2 без look-dev материалов, поэтому фигура серая — так "
            f"снимаются все герои библиотеки D-11) на подставке `SM_{key}_{stage}_Base`; цвет и материал в этой "
            f"приёмке не оцениваются. Свет — закреплённый cobble-probe rev 5 (`--light-pinned {light}`), High, "
            "редактор: это диагностические кадры, не K1/K2. Крупные планы Blender лежат и в {E}/<клип>/frames/ "
            "(копии файлов из preview/closeups-blender/).\n")


def frame_sources_r1(run: Path, key: str, clip: str, key_frames, ue_views=("front", "q34")) -> list[Path]:
    pv = run / "preview"
    src = [pv / f"{key}-{clip}-blender-sheet.jpg"]
    src += sorted((pv / "closeups-blender").glob(f"{key}-{clip}-*.jpg"))
    for f in key_frames:
        for v in ue_views:
            src.append(pv / "ue" / f"{key}-{clip}-f{int(f):02d}-{v}-ue-editor.jpg")
    if clip == "LungeAttack":
        src += sorted((pv / "ue").glob(f"{key}-LungeAttack-f*-closeup-ue-editor.jpg"))
    src.append(pv / f"{key}-H2Anim-ue-sheet.jpg")
    return src


def frame_source_by_name(run: Path, name: str) -> Path:
    """Где лежит кадр с этим именем в прогоне (r2+: имена из карточки прошлого цикла)."""
    pv = run / "preview"
    if name.endswith("-blender-sheet.jpg") or name.endswith("-H2Anim-ue-sheet.jpg"):
        return pv / name
    if name.endswith("-ue-editor.jpg"):
        return pv / "ue" / name
    return pv / "closeups-blender" / name


def read_known_limits(path: Path) -> str | None:
    """Текст списка известных пределов фигуры без комментариев <!-- … --> (пустой — «нет»); None — файла нет."""
    if not path.is_file():
        return None
    text = re.sub(r"<!--.*?-->", "", path.read_text(encoding="utf-8-sig"), flags=re.S).strip()
    return text or "нет"


def copy_frame(src: Path, dst: Path, max_px: int = REVIEW_PX) -> dict:
    """Копия кадра приёмщику: не больше max_px по длинной стороне (LANCZOS; .jpg/.jpeg — JPEG q92, иначе тот же формат),
    имя прежнее. Кадр не больше предела или max_px <= 0 — копия байт в байт. Оригинал не меняется."""
    if not max_px or max_px <= 0:
        shutil.copy2(src, dst)
        return {"name": dst.name, "resized": False}
    from PIL import Image

    with Image.open(src) as im:
        w, h = im.size
        if max(w, h) > max_px:
            k = max_px / max(w, h)
            size = (max(1, round(w * k)), max(1, round(h * k)))
            if dst.suffix.lower() in (".jpg", ".jpeg"):
                im.convert("RGB").resize(size, Image.LANCZOS).save(dst, "JPEG", quality=JPEG_QUALITY, subsampling=0,
                                                                   optimize=True)
            else:
                im.resize(size, Image.LANCZOS).save(dst, optimize=True)
            return {"name": dst.name, "resized": True, "px": list(size), "source_px": [w, h]}
    shutil.copy2(src, dst)
    return {"name": dst.name, "resized": False, "px": [w, h]}


def fill_prompt(tpl: str, *, e_rel: str, date: str, cycle: str, previous_card: str | None, files: list,
                note: str, replaces=(), refresh_sha: bool = False, repo: Path = c.REPO,
                known_limits: str | None = None) -> tuple[str, list]:
    """Заготовка → промпт цикла. Возвращает (текст, [пересчитанные пары path/sha]).
    known_limits — текст списка известных пределов (read_known_limits) для {{KNOWN_LIMITS}}."""
    tpl = re.sub(r"<!--.*?-->\s*\n", "", tpl, count=1, flags=re.S)
    if "<!--" in tpl:
        raise PrepError("служебный комментарий заготовки не удалён")
    if KNOWN_LIMITS in tpl:
        if known_limits is None:
            raise PrepError(f"заготовка ждёт {KNOWN_LIMITS}, а списка известных пределов нет: этап 6 пишет "
                            f"<asset-dir>/evidence/acceptance-anim-prompts/{KNOWN_LIMITS_FILE} (animation-vfx-sfx.md "
                            "§10.5; свой файл — --known-limits)")
        tpl = tpl.replace(KNOWN_LIMITS, known_limits)
    for r in replaces:
        old, sep, new = r.partition("=")
        if not sep or old not in tpl:
            raise PrepError(f"--replace {r!r}: нет {old!r} в заготовке")
        tpl = tpl.replace(old, new)
    refreshed = []
    for path, want in PAIR_RE.findall(tpl):
        p = Path(repo) / path
        if not p.is_file():
            raise PrepError(f"accepted_object: нет файла {path}")
        got = c.sha256(p)
        if got != want:
            if not refresh_sha:
                raise PrepError(f"sha256 {path} изменился ({want[:8]} → {got[:8]}): клип перепечён — --refresh-sha")
            tpl = tpl.replace(f'"path": "{path}", "sha256": "{want}"', f'"path": "{path}", "sha256": "{got}"')
            refreshed.append({"path": path, "old": want, "new": got})
    out = (tpl.replace("{{E}}", e_rel).replace("{{DATE}}", date).replace("{{CYCLE}}", cycle)
           .replace("{{PREVIOUS_CARD_JSON}}", json.dumps(previous_card) if previous_card else "null")
           .replace("{{FRAMES_FILES_JSON}}", json.dumps(files, ensure_ascii=False)))
    left = re.findall(r"\{\{[A-Z_0-9]+\}\}", out)
    if left:
        raise PrepError(f"не заполнены плейсхолдеры {sorted(set(left))}")
    marker = next((m for m in MARKERS if m in out), None)
    if marker is None:
        raise PrepError(f"нет строки-якоря для заметки о носителе ({', '.join(MARKERS)})")
    return out.replace(marker, note.replace("{E}", e_rel) + marker, 1), refreshed


def main(argv=None) -> int:
    c.utf8_streams()
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--asset-dir", required=True, help="art/pipeline-candidates/<ASSET_ID>")
    ap.add_argument("--key", required=True, help="KEY героя (префикс имён кадров)")
    ap.add_argument("--run", required=True, help="прогон h2anim, с которого сняты кадры (<run>/preview)")
    ap.add_argument("--spec", default=None, help="спека h2anim (клипы и key_frames; для r1 обязательна)")
    ap.add_argument("--date", required=True, help="дата цикла YYYY-MM-DD")
    ap.add_argument("--cycle", required=True, help="r1, r2, …")
    ap.add_argument("--evidence", default=None,
                    help="каталог цикла (по умолчанию <asset-dir>/evidence/acceptance-anim/<YYYYMMDD>-<cycle>)")
    ap.add_argument("--prompts", default=None, help="заготовки этапа 6 (<asset-dir>/evidence/acceptance-anim-prompts)")
    ap.add_argument("--previous", default=None, help="каталог прошлого цикла (r2+): кадры и previous_card оттуда")
    ap.add_argument("--clips", default=None, help="клипы через запятую (по умолчанию все клипы спеки / прошлого цикла)")
    ap.add_argument("--ue-views", default="front,q34", help="виды UE-кадров на key_frame (front,q34)")
    ap.add_argument("--stage", default="H2LD")
    ap.add_argument("--carrier-note-file", default=None, help="своя заметка о носителе ({E} подставляется)")
    ap.add_argument("--light-pinned", default=LIGHT_PINNED, help="отчёт закреплённого света для заметки")
    ap.add_argument("--replace", action="append", default=[], help="OLD=NEW в заготовке (повторяемый)")
    ap.add_argument("--refresh-sha", action="store_true", help="пересчитать sha256 пар path/sha (клип перепечён)")
    ap.add_argument("--known-limits", default=None,
                    help=f"список известных пределов фигуры для {KNOWN_LIMITS} (по умолчанию <prompts>/{KNOWN_LIMITS_FILE})")
    ap.add_argument("--max-px", type=int, default=REVIEW_PX,
                    help=f"длинная сторона копий кадров, px (по умолчанию {REVIEW_PX}, JPEG q{JPEG_QUALITY}; 0 — копия как есть)")
    ap.add_argument("--repo", default=str(c.REPO))
    ap.add_argument("--dry-run", action="store_true", help="план: кадры и недостающие файлы, ничего не писать")
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    repo = Path(a.repo)
    adir = c.resolve(a.asset_dir, repo)
    run = c.resolve(a.run, repo)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", a.date) or not re.fullmatch(r"r\d+", a.cycle):
        print("ERROR: --date YYYY-MM-DD и --cycle rN", file=sys.stderr)
        return 2
    ev = c.resolve(a.evidence, repo) if a.evidence else adir / "evidence/acceptance-anim" / f"{a.date.replace('-', '')}-{a.cycle}"
    prompts = c.resolve(a.prompts, repo) if a.prompts else adir / "evidence/acceptance-anim-prompts"
    prev = c.resolve(a.previous, repo) if a.previous else None
    try:
        e_rel = c.rel(ev, repo) if ev.resolve().is_relative_to(repo.resolve()) else ev.as_posix()
        spec = c.load_json(c.resolve(a.spec, repo)) if a.spec else None
        if spec is None and prev is None:
            raise PrepError("для r1 нужна --spec (клипы и key_frames)")
        clips = ([x.strip() for x in a.clips.split(",") if x.strip()] if a.clips
                 else list((spec or {}).get("clips") or sorted(p.name for p in prev.iterdir() if (p / "card.json").is_file())))
        note = (Path(a.carrier_note_file).read_text(encoding="utf-8") if a.carrier_note_file
                else default_carrier_note(a.key, a.stage, a.light_pinned))
        kl_path = c.resolve(a.known_limits, repo) if a.known_limits else prompts / KNOWN_LIMITS_FILE
        if a.known_limits and not kl_path.is_file():
            raise PrepError(f"--known-limits: нет файла {kl_path}")
        known_limits = read_known_limits(kl_path)
        plan, problems = {}, []
        for clip in clips:
            if prev is not None:
                card = c.load_json(prev / clip / "card.json")
                names = list(card["frames"]["files"])
                srcs = [frame_source_by_name(run, n) for n in names]
                prev_card = c.rel(prev / clip / "card.json", repo)
            else:
                kf = ((spec.get("clips") or {}).get(clip) or {}).get("key_frames")
                if kf is None:
                    raise PrepError(f"{clip}: нет key_frames в спеке")
                srcs = frame_sources_r1(run, a.key, clip, kf, tuple(a.ue_views.split(",")))
                prev_card = None
            tpl_path = prompts / clip / "acceptor-prompt.md"
            if not tpl_path.is_file():
                problems.append(f"{clip}: нет заготовки {tpl_path}")
            elif known_limits is None and KNOWN_LIMITS in tpl_path.read_text(encoding="utf-8"):
                problems.append(f"{clip}: заготовка ждёт {KNOWN_LIMITS}, нет {kl_path}")
            problems += [f"{clip}: нет кадра {s}" for s in srcs if not s.is_file()]
            plan[clip] = {"frames": [s.as_posix() for s in srcs], "template": tpl_path.as_posix(), "previous_card": prev_card}
        if a.dry_run:
            print(json.dumps({"dry_run": True, "evidence": e_rel, "max_px": a.max_px,
                              "known_limits": kl_path.as_posix() if known_limits is not None else None,
                              "plan": plan, "problems": problems}, ensure_ascii=False, indent=1))
            return 0
        if problems:
            raise PrepError("; ".join(problems[:12]))
        for clip, p in plan.items():
            tpl = Path(p["template"]).read_text(encoding="utf-8")
            if known_limits is not None and KNOWN_LIMITS not in tpl:
                print(f"WARNING: {clip}: есть {kl_path.name}, а в заготовке нет {KNOWN_LIMITS} — список не подставлен "
                      "(блок пределов — текстом заготовки)", file=sys.stderr)
            fdir = ev / clip / "frames"
            fdir.mkdir(parents=True, exist_ok=True)
            files, resized = [], 0
            for s in map(Path, p["frames"]):
                try:
                    rec = copy_frame(s, fdir / s.name, a.max_px)
                except OSError as exc:  # PIL.UnidentifiedImageError — тоже OSError
                    raise PrepError(f"{clip}: кадр {s} не читается как картинка ({exc})") from exc
                resized += rec["resized"]
                files.append(s.name)
            text, refreshed = fill_prompt(tpl, e_rel=e_rel, date=a.date, cycle=a.cycle,
                                          previous_card=p["previous_card"], files=files, note=note,
                                          replaces=a.replace, refresh_sha=a.refresh_sha, repo=repo,
                                          known_limits=known_limits)
            (ev / clip / "acceptor-prompt.md").write_text(text, encoding="utf-8", newline="\n")
            size = sum((fdir / f).stat().st_size for f in files) // 1024
            print(clip, len(files), "frames", size, "KiB", "resized %d to <= %d px" % (resized, a.max_px) if resized
                  else "", ("sha refreshed %d" % len(refreshed)) if refreshed else "")
        ps1 = (prev / "run-acceptor.ps1") if prev is not None and (prev / "run-acceptor.ps1").is_file() \
            else prompts / "run-acceptor.ps1"
        if ps1.is_file():
            shutil.copy2(ps1, ev / "run-acceptor.ps1")
        else:
            print(f"WARNING: нет {ps1} — run-acceptor.ps1 не скопирован", file=sys.stderr)
    except (PrepError, OSError, KeyError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
