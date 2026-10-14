"""Шаг 7a: конфиг съёмки и сверки UE look-dev (ue_hero_lookdev.py review/verify --config) из шаблона — чужого героя или своего прошлого.

Механика, которую агенты 7a пилота писали руками (write_review_config.py Achilles «из конфига Angel»,
make_review_config_r4.py «r4 = r3 на модели r3»):
  1. перенацелить имена шаблона на героя (пути /Game/PipelineCandidates/<Key>/…, MI_/T_/SK_ имена, content-key);
  2. run_dir — прогон ue-import; concept — виды концепт-пакета art/imagegen/concept-<ck>-codex/<ck>-<view>.png;
     concept_zones — <lookdev-run>/reports/measure-report.json; verify.clips_reference —
     <clips-run>/reports/ue-measure-clips.json; verify.height_uu — --height-uu (верх меша в UE, ue-import-report);
  3. скаляры MI тела verify.instances.figure_instance.scalars — из ue.figure_parameters профиля импорта
     (--import-profile); verify.expect.triangles — сумма checks.triangles_as_h21.measured тела и оружия
     ld-fbx-report (без подставки SM_*), если дан --lookdev-run;
  4. зоны, ворота, сторона камеры и заметки героя — --set / --set-json / --drop (debug_calibration и т. п.);
     якорь экспозиции из шаблона чужого героя не наследуется: без --set anchor_zone=<зона героя из zones> — отказ
     (ревью 2026-10-14, R-09; шаблон — свой прошлый конфиг: якорь остаётся как был);
  5. проверить, что имя героя-шаблона нигде не осталось (кроме --allow-leftover), и записать.

    python tools/tripo-pipeline/ue7a/write_review_config.py --template <…ASSET-ANGEL-001/20261014-h2ld-ldc-ue/review-config.json> \
        --asset-dir art/pipeline-candidates/ASSET-ACHILLES-001 --run-dir <asset-dir>/20261014-h2ld-ue-import-r3 \
        --height-uu 54.9931 --lookdev-run <asset-dir>/20261014-h2-lookdev-r2 --clips-run <asset-dir>/20261014-h2anim \
        --import-profile <asset-dir>/build-profiles/achilles-h2ld-lookdev-ue-import-r3.json \
        --set side_camera=+X --set-json 'zones=["wool_coarse","linen"]' --set anchor_zone=wool_coarse \
        --drop debug_calibration --set note=… \
        --out <asset-dir>/20261014-h2ld-ldc-ue/review-config.json

Код выхода: 0 — записан (или напечатан с --dry-run), 2 — ошибка входа или остались имена шаблона.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ue7a as c  # noqa: E402


class ConfigError(Exception):
    pass


def template_identity(cfg: dict) -> tuple[str, str | None]:
    """(Key, content-key) шаблона: Key из hero / verify.hero_root, content-key из пути концепта."""
    key = cfg.get("hero")
    if not key:
        m = re.search(r"/Game/PipelineCandidates/([A-Za-z0-9]+)", ((cfg.get("verify") or {}).get("hero_root") or ""))
        key = m.group(1) if m else None
    if not key:
        raise ConfigError("шаблон: не определить героя (hero / verify.hero_root)")
    ck = None
    m = re.search(r"concept-([a-z0-9-]+)-codex/", json.dumps(cfg.get("concept") or {}))
    if m:
        ck = m.group(1)
    return key, ck


def check_anchor_zone(cfg: dict, tpl: dict, key: str, t_key: str, sets=(), set_jsons=()) -> None:
    """R-09 (ревью 2026-10-14): шаблон чужого героя несёт его якорь экспозиции (anchor_zone), а ue_hero_lookdev без ключа
    брал «linen» Medusa. Конфиг из чужого шаблона — только с явным --set anchor_zone=<зона героя> из его zones."""
    explicit = any(s.partition("=")[0].strip() == "anchor_zone" for s in [*sets, *set_jsons])
    zones = list(cfg.get("zones") or [])
    if not explicit:
        raise ConfigError(f"anchor_zone: шаблон героя {t_key!r} несёт свой якорь экспозиции "
                          f"{tpl.get('anchor_zone')!r} — задайте --set anchor_zone=<зона {key}>"
                          + (f" (одна из zones: {', '.join(map(str, zones))})" if zones else ""))
    if zones and cfg.get("anchor_zone") not in zones:
        raise ConfigError(f"anchor_zone {cfg.get('anchor_zone')!r} не из zones героя {key}: {zones}")


def figure_triangles(fbx_report: dict) -> int | None:
    meas = (((fbx_report.get("checks") or {}).get("triangles_as_h21") or {}).get("measured")) or {}
    vals = [v for k, v in meas.items() if not k.startswith("SM_")]
    return sum(vals) if vals else None


def build(tpl: dict, *, repo: Path, key: str, content_key: str, asset_id: str | None, run_dir: str,
          height_uu: float | None = None, lookdev_run: str | None = None, clips_run: str | None = None,
          import_profile: str | None = None, template_aid: str | None = None, sets=(), set_jsons=(), drops=(),
          allow_leftover=()) -> dict:
    t_key, t_ck = template_identity(tpl)
    same = t_key == key
    cfg = json.loads(json.dumps(tpl))
    if not same:
        cfg = c.retarget(cfg, c.name_pairs(t_key, key, t_ck, content_key, template_aid, asset_id))
    cfg["hero"] = key
    rd = c.resolve(run_dir, repo)
    if not rd.is_dir():
        raise ConfigError(f"нет прогона ue-import {run_dir}")
    cfg["run_dir"] = c.rel(rd, repo)
    concept = {v: f"art/imagegen/concept-{content_key}-codex/{content_key}-{v}.png" for v in ("front", "side", "back")}
    if any((repo / p).is_file() for p in concept.values()):
        cfg["concept"] = concept
    v = cfg.setdefault("verify", {})
    paths = c.hero_paths(key)
    v.update({"skeleton": paths["skeleton"], "folder": paths["stage"], "hero_root": paths["root"],
              "clips_folder": paths["clips"]})
    if height_uu is not None:
        v["height_uu"] = height_uu
    if lookdev_run:
        ld = c.resolve(lookdev_run, repo)
        mr = ld / "reports" / "measure-report.json"
        if not mr.is_file():
            raise ConfigError(f"нет {mr}")
        cfg["concept_zones"] = c.rel(mr, repo)
        fr = ld / "reports" / "ld-fbx-report.json"
        if fr.is_file():
            tris = figure_triangles(c.load_json(fr))
            if tris:
                v.setdefault("expect", {})["triangles"] = tris
    if clips_run:
        cm = c.resolve(clips_run, repo) / "reports" / "ue-measure-clips.json"
        v["clips_reference"] = c.rel(cm, repo) if cm.resolve().is_relative_to(repo.resolve()) else cm.as_posix()
    if import_profile:
        prof = c.load_json(c.resolve(import_profile, repo))
        fp = (prof.get("ue") or {}).get("figure_parameters") or {}
        if not fp:
            raise ConfigError(f"{import_profile}: нет ue.figure_parameters")
        fi = v.setdefault("instances", {}).setdefault("figure_instance", {})
        fi["scalars"] = dict(fp)
    c.apply_sets(cfg, sets, set_jsons, drops)
    if not same:
        check_anchor_zone(cfg, tpl, key, t_key, sets, set_jsons)
        bad = c.leftovers(cfg, t_key, allow_leftover)
        if bad:
            raise ConfigError(f"остались имена шаблона {t_key!r} ({len(bad)}): {bad[:5]} — --set или --allow-leftover")
    return cfg


def main(argv=None) -> int:
    c.utf8_streams()
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--template", required=True, help="review-config.json героя-шаблона или свой прошлый")
    ap.add_argument("--asset-dir", required=True, help="art/pipeline-candidates/<ASSET_ID> (asset-card.yaml)")
    ap.add_argument("--key", default=None, help="KEY героя (по умолчанию из asset-card.yaml)")
    ap.add_argument("--content-key", default=None, help="content-key (по умолчанию CONTENT_KEY заявки)")
    ap.add_argument("--run-dir", required=True, help="прогон ue-import (run_dir)")
    ap.add_argument("--height-uu", type=float, default=None, help="verify.height_uu (верх меша в UE)")
    ap.add_argument("--lookdev-run", default=None, help="прогон look-dev: concept_zones и треугольники")
    ap.add_argument("--clips-run", default=None, help="прогон h2anim: verify.clips_reference")
    ap.add_argument("--import-profile", default=None, help="профиль импорта: скаляры MI тела")
    ap.add_argument("--template-asset-id", default=None, help="ASSET_ID шаблона (для замены, если он в путях)")
    ap.add_argument("--set", action="append", default=[], dest="sets", help="путь=текст, повторяемый")
    ap.add_argument("--set-json", action="append", default=[], dest="set_jsons", help="путь=<json>, повторяемый")
    ap.add_argument("--drop", action="append", default=[], help="удалить ключ по пути, повторяемый")
    ap.add_argument("--allow-leftover", action="append", default=[], help="подстрока строки, где имя шаблона допустимо")
    ap.add_argument("--out", default=None)
    ap.add_argument("--repo", default=str(c.REPO))
    ap.add_argument("--dry-run", action="store_true")
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    repo = Path(a.repo)
    try:
        adir = c.resolve(a.asset_dir, repo)
        card = c.asset_card_fields(adir)
        key, ck = a.key or card.get("KEY"), a.content_key or card.get("CONTENT_KEY")
        if not key or not ck:
            raise ConfigError("нет --key/--content-key и KEY/CONTENT_KEY в asset-card.yaml")
        tpl = c.load_json(c.resolve(a.template, repo))
        t_aid = a.template_asset_id
        if t_aid is None:
            m = re.search(r"(ASSET-[A-Z0-9-]+-\d{3})", tpl.get("run_dir") or "")
            t_aid = m.group(1) if m else None
        cfg = build(tpl, repo=repo, key=key, content_key=ck, asset_id=adir.name, run_dir=a.run_dir,
                    height_uu=a.height_uu, lookdev_run=a.lookdev_run, clips_run=a.clips_run,
                    import_profile=a.import_profile, template_aid=t_aid, sets=a.sets, set_jsons=a.set_jsons,
                    drops=a.drop, allow_leftover=a.allow_leftover)
    except (ConfigError, ValueError, OSError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if a.dry_run or not a.out:
        print(json.dumps(cfg, ensure_ascii=False, indent=1))
        return 0
    c.write_json(c.resolve(a.out, repo), cfg, indent=1)
    print("wrote", a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
