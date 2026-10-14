"""Шаг 7a: профиль UE-импорта героя (skeletal-adopt, h2-lookdev/1) из шаблона — чужого героя или своей прошлой ревизии.

Механика, которую агенты 7a пилота писали руками (write_import_profile.py Achilles «из шаблона Angel r3»,
make_profile_r4.py «rev 4 = rev 3 на модели r3»):
  1. перенацелить имена шаблона на героя (ASSET_ID, content-key, Key) — кроме derived_from и history;
  2. входы прогона look-dev: candidate.dir / bake_profile / bake_profile_id, extra_reports (rig/textures report
     прогона bake), fbx и textures по Key;
  3. пересчитать из отчётов: TeamDyeGain/TeamDyeCeiling по LDV-13 (ld-team-accent-report team_dye_gain.
     accent_Y_p50_p95), expectations.triangles (ld-fbx-report checks.triangles_as_h21.measured), след подставки
     meshes.base.footprint_m (rig-report expected_ue_bounds_uu_at_import_scale_1.base: ширина X, Y и верх Z, м),
     sha256 LUT и TeamAccent;
  4. точечные значения героя — --set путь=текст / --set-json путь=<json> / --drop путь (оружие, оси, сокеты, заметки);
  5. проверить, что имя героя-шаблона нигде не осталось (кроме --allow-leftover), и записать.

    python tools/tripo-pipeline/ue7a/write_import_profile.py --template <…>/angel-h2ld-lookdev-ue-import-r3.json \
        --asset-dir art/pipeline-candidates/ASSET-ACHILLES-001 --key Achilles \
        --lookdev-run <asset-dir>/20261014-h2-lookdev-r2 --lookdev-profile <asset-dir>/build-profiles/achilles-h2-lookdev-r2.json \
        --bake-run <asset-dir>/20261014-h2-bake-r2 --profile-id achilles-h2ld-lookdev-ue-import/1 \
        --set meshes.weapon.object=SK_Achilles_H2_Spear --set candidate.figure_top_part=tripo_part_6 \
        --status-note-file note.txt --out <asset-dir>/build-profiles/achilles-h2ld-lookdev-ue-import.json
    … новая ревизия своего профиля: --template <свой rev N> --previous <свой rev N> --previous-run <прогон ue-import rev N>
      --rev-note " Rev N+1 (…): …"      (status_note шаблона сохраняется, к нему дописывается rev-note)

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

TEX_KEYS = ("BC", "N", "ORM", "TeamMask", "MatID", "Edge")


class ProfileError(Exception):
    pass


def template_identity(tpl: dict) -> tuple[str, str | None, str | None]:
    """(Key, content-key, ASSET_ID) шаблона: Key из ue.target_skeleton / ue.skeletal_asset, content-key из profile_id."""
    ue = tpl.get("ue") or {}
    m = re.search(r"/Game/PipelineCandidates/([A-Za-z0-9]+)/", ue.get("target_skeleton") or "") \
        or re.match(r"SK_([A-Za-z0-9]+)_", ue.get("skeletal_asset") or "")
    if not m:
        raise ProfileError("шаблон: не определить Key (ue.target_skeleton / ue.skeletal_asset)")
    pid = tpl.get("profile_id") or ""
    ck = pid.split("-h2ld-")[0] if "-h2ld-" in pid else None
    return m.group(1), ck, tpl.get("asset_id")


def footprint_m(bounds: dict) -> list:
    lo, hi = bounds["min"], bounds["max"]
    return [round((hi[0] - lo[0]) / 100.0, 5), round((hi[1] - lo[1]) / 100.0, 5), round(hi[2] / 100.0, 5)]


def consistency(p: dict, tris: dict, prepare_report: Path | None) -> list[str]:
    """Значения героя, которые шаблон мог оставить чужими: объекты meshes.* есть в отчёте FBX look-dev; верх части
    figure_top_part / scale.top_part в prepare-report bake = scale.figure_height_m (± 1 мм)."""
    out = []
    for role, m in (p.get("meshes") or {}).items():
        obj = (m or {}).get("object")
        if obj and obj not in tris:
            out.append(f"meshes.{role}.object {obj!r} нет среди объектов FBX look-dev {sorted(tris)}")
    if prepare_report is not None and prepare_report.is_file():
        parts = (c.load_json(prepare_report).get("parts") or {})
        h = (p.get("scale") or {}).get("figure_height_m")
        for path, name in (("candidate.figure_top_part", (p.get("candidate") or {}).get("figure_top_part")),
                           ("scale.top_part", (p.get("scale") or {}).get("top_part"))):
            if not name:
                continue
            fb = (parts.get(name) or {}).get("final_bounds_m")
            if fb is None:
                out.append(f"{path} {name!r} нет в {prepare_report.name}")
            elif h is not None and abs(fb[1][2] - h) > 0.001:
                out.append(f"{path} {name!r}: верх {fb[1][2]} м != scale.figure_height_m {h}")
    return out


def build(tpl: dict, *, repo: Path, key: str, asset_id: str, content_key: str, lookdev_run: str,
          lookdev_profile: str | None, bake_run: str | None, profile_id: str, lut: str | None = None,
          status_note: str | None = None, rev_note: str = "", previous: str | None = None,
          previous_run: str | None = None, template_rel: str | None = None, extra_figure_params: dict | None = None,
          sets=(), set_jsons=(), drops=(), allow_leftover=()) -> dict:
    t_key, t_ck, t_aid = template_identity(tpl)
    same = t_key == key
    keep = (lambda s: False)
    p = json.loads(json.dumps(tpl))
    hist, derived = p.pop("history", None), p.pop("derived_from", [])
    if not same:
        p = c.retarget(p, c.name_pairs(t_key, key, t_ck, content_key, t_aid, asset_id), keep)
    p["profile_id"] = profile_id
    p["asset_id"] = asset_id
    p["status"] = "proposed"
    if status_note is not None:
        p["status_note"] = status_note
    elif not same:
        raise ProfileError("шаблон чужого героя: нужен --status-note-file (заметка шаблона описывает его героя)")
    if rev_note:
        p["status_note"] = (p.get("status_note") or "") + rev_note
    ld = c.resolve(lookdev_run, repo)
    if not ld.is_dir():
        raise ProfileError(f"нет прогона look-dev {lookdev_run}")
    ld_rel = c.rel(ld, repo)
    cand = p.setdefault("candidate", {})
    cand["dir"] = ld_rel
    if lookdev_profile:
        lp = c.resolve(lookdev_profile, repo)
        cand["bake_profile"] = c.rel(lp, repo)
        cand["bake_profile_id"] = c.load_json(lp).get("profile_id")
    if bake_run:
        bk = Path(bake_run).name
        cand.setdefault("extra_reports", {}).update({"run_manifest": "reports/run-manifest.json",
                                                    "source_rig_report": f"../{bk}/reports/rig-report.json",
                                                    "source_textures_report": f"../{bk}/reports/textures-report.json"})
    cand["fbx"] = {"skeletal": f"export/SK_{key}_H2LD.fbx", "base": f"export/SM_{key}_H2LD_Base.fbx"}
    cand["textures"] = {k: f"textures/T_{key}_H2LD_2K_{k}.png" for k in TEX_KEYS}
    lib = cand.setdefault("library_inputs", {})
    lut_path = c.resolve(lut, repo) if lut else ld / "textures" / f"T_UM_MatLUT_{key}.dds"
    ta_path = ld / "textures" / f"T_{key}_H2LD_TeamAccent_2K.png"
    for name, path in (("LUT", lut_path), ("TeamAccent", ta_path)):
        if not path.is_file():
            raise ProfileError(f"нет {name}: {path}")
        lib.setdefault(name, {}).update({"path": c.rel(path, repo), "sha256": c.sha256(path)})
    reports = ld / "reports"
    ta = (c.load_json(reports / "ld-team-accent-report.json").get("team_dye_gain") or {})
    if "accent_Y_p50_p95" not in ta:
        raise ProfileError("ld-team-accent-report.json: нет team_dye_gain.accent_Y_p50_p95")
    gain, ceil = c.team_dye(*ta["accent_Y_p50_p95"])
    ue = p.setdefault("ue", {})
    ue["figure_parameters"] = dict({"TeamDye": 1.0, "TeamDyeGain": gain, "TeamDyeCeiling": ceil}, **(extra_figure_params or {}))
    ue["figure_parameters_note"] = (
        "team-accent.md rule LDV-13, one MI for both teams: TeamDyeGain = 0.8 / Y_p50 (%.5f) = %.3f, TeamDyeCeiling = "
        "0.9 / Y_p95 (%.5f) = %.4f (%s/ld-team-accent-report.json team_dye_gain.accent_Y_p50_p95)"
        % (ta["accent_Y_p50_p95"][0], gain, ta["accent_Y_p50_p95"][1], ceil, c.rel(reports, repo))
        + ("; extra: " + json.dumps(extra_figure_params) if extra_figure_params else ""))
    fbx = c.load_json(reports / "ld-fbx-report.json")
    tris = (((fbx.get("checks") or {}).get("triangles_as_h21") or {}).get("measured"))
    if not isinstance(tris, dict) or not tris:
        raise ProfileError("ld-fbx-report.json: нет checks.triangles_as_h21.measured")
    p.setdefault("expectations", {})["triangles"] = tris
    if bake_run:
        rig = c.load_json(c.resolve(bake_run, repo) / "reports" / "rig-report.json")
        base = (rig.get("expected_ue_bounds_uu_at_import_scale_1") or {}).get("base")
        if base:
            p.setdefault("meshes", {}).setdefault("base", {})["footprint_m"] = footprint_m(base)
            p["meshes"]["base"]["footprint_note"] = (
                "rig-report expected_ue_bounds_uu_at_import_scale_1.base %s .. %s uu (%s/reports/rig-report.json): "
                "X and Y widths, Z = base top" % (base["min"], base["max"], c.rel(c.resolve(bake_run, repo), repo)))
    c.apply_sets(p, sets, set_jsons, drops)
    problems = consistency(p, tris, c.resolve(bake_run, repo) / "reports" / "prepare-report.json" if bake_run else None)
    if problems:
        raise ProfileError("; ".join(problems) + " — поправить --set")
    src = [f"{template_rel} (template; tools/tripo-pipeline/ue7a/write_import_profile.py)"] if template_rel else []
    p["derived_from"] = src + (list(derived) if same else [])
    if previous:
        prev = c.resolve(previous, repo)
        p["history"] = {"previous": {"path": c.rel(prev, repo), "sha256": c.sha256(prev), "run": previous_run}}
    elif same and hist:
        p["history"] = hist
    if not same:
        bad = [ln for ln in c.leftovers({k: v for k, v in p.items() if k not in ("derived_from", "history")}, t_key,
                                        allow_leftover)]
        if bad:
            raise ProfileError(f"остались имена шаблона {t_key!r} ({len(bad)}): {bad[:5]} — --set или --allow-leftover")
    return p


def main(argv=None) -> int:
    c.utf8_streams()
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--template", required=True, help="профиль-шаблон (*-h2ld-lookdev-ue-import*.json)")
    ap.add_argument("--asset-dir", required=True, help="art/pipeline-candidates/<ASSET_ID> (asset-card.yaml)")
    ap.add_argument("--key", default=None, help="KEY героя (по умолчанию из asset-card.yaml)")
    ap.add_argument("--content-key", default=None, help="content-key (по умолчанию CONTENT_KEY заявки)")
    ap.add_argument("--lookdev-run", required=True, help="прогон look-dev (candidate.dir)")
    ap.add_argument("--lookdev-profile", default=None, help="профиль look-dev этого прогона (bake_profile)")
    ap.add_argument("--bake-run", default=None, help="прогон h2-bake (rig-report: след подставки, extra_reports)")
    ap.add_argument("--lut", default=None, help="LUT (по умолчанию <lookdev-run>/textures/T_UM_MatLUT_<Key>.dds)")
    ap.add_argument("--profile-id", required=True, help="<content-key>-h2ld-lookdev-ue-import/<N>")
    ap.add_argument("--status-note-file", default=None, help="status_note героя (обязателен для чужого шаблона)")
    ap.add_argument("--rev-note", default="", help="дописать к status_note (новая ревизия своего профиля)")
    ap.add_argument("--previous", default=None, help="прошлая ревизия профиля → history.previous (sha256 считается)")
    ap.add_argument("--previous-run", default=None, help="прогон ue-import прошлой ревизии (history.previous.run)")
    ap.add_argument("--extra-figure-params", default=None, help="JSON: доп. скаляры ue.figure_parameters")
    ap.add_argument("--set", action="append", default=[], dest="sets", help="путь=текст (a.b.0.c), повторяемый")
    ap.add_argument("--set-json", action="append", default=[], dest="set_jsons", help="путь=<json>, повторяемый")
    ap.add_argument("--drop", action="append", default=[], help="удалить ключ по пути, повторяемый")
    ap.add_argument("--allow-leftover", action="append", default=[], help="подстрока строки, где имя шаблона допустимо")
    ap.add_argument("--out", default=None, help="куда писать (без --out и с --dry-run — в stdout)")
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
        key = a.key or card.get("KEY")
        ck = a.content_key or card.get("CONTENT_KEY")
        if not key or not ck:
            raise ProfileError("нет --key/--content-key и KEY/CONTENT_KEY в asset-card.yaml")
        c.hero_paths(key)
        tpl_path = c.resolve(a.template, repo)
        prof = build(c.load_json(tpl_path), repo=repo, key=key, asset_id=adir.name, content_key=ck,
                     lookdev_run=a.lookdev_run, lookdev_profile=a.lookdev_profile, bake_run=a.bake_run,
                     profile_id=a.profile_id, lut=a.lut,
                     status_note=Path(a.status_note_file).read_text(encoding="utf-8").strip() if a.status_note_file else None,
                     rev_note=a.rev_note, previous=a.previous, previous_run=a.previous_run,
                     template_rel=c.rel(tpl_path, repo),
                     extra_figure_params=json.loads(a.extra_figure_params) if a.extra_figure_params else None,
                     sets=a.sets, set_jsons=a.set_jsons, drops=a.drop, allow_leftover=a.allow_leftover)
    except (ProfileError, ValueError, OSError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if a.dry_run or not a.out:
        print(json.dumps(prof, ensure_ascii=False, indent=2))
        return 0
    c.write_json(c.resolve(a.out, repo), prof, indent=2)
    print("wrote", a.out, "TeamDyeGain", prof["ue"]["figure_parameters"]["TeamDyeGain"],
          "TeamDyeCeiling", prof["ue"]["figure_parameters"]["TeamDyeCeiling"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
