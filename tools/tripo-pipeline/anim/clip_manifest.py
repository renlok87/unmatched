"""Манифест библиотеки анимаций: сборка (build) и проверка (check).

python tools/tripo-pipeline/anim/clip_manifest.py build   # пересобрать clip-manifest.json
python tools/tripo-pipeline/anim/clip_manifest.py check   # схема + файлы + sha256 + правила статусов

build собирает записи функциями slot()/medusa_draft()/tripo_test()/bvh_fixture()/glb_fixture() ниже
(16 слотов брифа 18 §4: 4 клипа D-11 x 4 персонажа; 15 безусловных, HAR-HitReact условен до
AD-CNF-30 — бриф 18, стр. 10) и тестовые файлы, подставляет измеренные fps/длительности и результаты
из docs/art-pipeline/animation-library/validation/*.validation.json и считает sha256.

Волна 5c (H2Anim, 2026-09-29): production-слоты переведены на UM_HUMANOID_17_v2 и заполняются кандидатами
H2Anim функцией h2anim() — клип <run>/export/AM_<UEHero>_<Clip>.fbx спеки героя (build-profiles/*-h2anim.json,
anim/clip_author.py), отчёт validate_clip v2 (validation-h2anim/), контакты (reports/contact-<Clip>.json) и
UE-импорт (reports/ue-import-clips.json). Статус technically_imported ставится только кодом h2anim() и только если
все три свидетельства есть и сходятся (validate PASS, контакты PASS, импорт legacy FbxFactory + bForceRootLock с тем же
sha256 FBX); иначе measured (validate PASS) или draft_test. artistically_accepted сборка не пишет никогда.
v1-черновики AM_Medusa_* остаются тестовыми записями.
"""
import hashlib
import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
LIB = os.path.join(REPO, "docs/art-pipeline/animation-library")
MANIFEST = os.path.join(LIB, "clip-manifest.json")
SCHEMA = os.path.join(LIB, "clip-manifest.schema.json")
VAL = os.path.join(LIB, "validation")
RUN = "art/pipeline-candidates/ASSET-MEDUSA-001/tripo-rig-20260928-p16"
FIX = RUN + "/fixtures"
# Слоты, обязательность которых условна (бриф 18, стр. 10: «HAR-HitReact (JOB-07) условен до решения AD-CNF-30»).
CONDITIONAL = {"HAR-HitReact": "условно до AD-CNF-30 (бриф 18, стр. 10; Т2№7): при HP 1 HitReact почти недостижим, автор может сократить набор Harpy до смерть+idle"}

# Целевые длительности — ПРЕДЛОЖЕНИЕ брифа 18 (Таблица 4) / 04 §111; CUE — 07-animation-vfx-audio.csv.
TARGETS = {
    "Idle": {"cue": ["state:Idle", "CUE-017"], "duration": "2-3 (loop)", "status": "proposal", "loop": True},
    "LungeAttack": {"cue": ["CUE-008"], "duration": 0.6, "status": "proposal", "loop": False},
    "HitReact": {"cue": ["CUE-011"], "duration": "0.4 (04) vs 0.9 (CUE-011)", "status": "open", "loop": False},
    "DeathSettle": {"cue": ["CUE-013"], "duration": "0.9 (04), <=0.95 (CUE-013)", "status": "open", "loop": False},
}
CHARS = {"Medusa": ("MED", "ASSET-MEDUSA-001"), "Harpy": ("HAR", "ASSET-HARPY-001"),
         "Arthur": ("ARTH", "ASSET-KING-ARTHUR-001"), "Merlin": ("MER", "ASSET-MERLIN-001")}
# волна 5c: спека H2Anim героя (ue_hero = имя героя в путях UE и в файлах клипов)
H2ANIM = {"Medusa": "art/pipeline-candidates/ASSET-MEDUSA-001/build-profiles/medusa-h2anim.json",
          "Arthur": "art/pipeline-candidates/ASSET-KING-ARTHUR-001/build-profiles/king-arthur-h2anim.json",
          "Merlin": "art/pipeline-candidates/ASSET-MERLIN-001/build-profiles/merlin-h2anim.json",
          "Harpy": "art/pipeline-candidates/ASSET-HARPY-001/build-profiles/harpy-h2anim.json"}
VAL2 = os.path.join(LIB, "validation-h2anim")
V2_KEY = "UM_HUMANOID_17_v2"
NO_LICENSE = {"terms": "нет файла", "commercial_use": "n/a"}
OWN = {"holder": "проект Unmatched", "terms": "собственная работа (Blender-скрипт репозитория)",
       "commercial_use": "yes"}
TRIPO_LIC = {"holder": "пользователь (платный план Tripo Studio)",
             "terms": "Tripo Studio, приватность «Приватный»; права на результат по платному плану — по docs/research/2026-09-27-animation-audit/services.md, не перепроверено юристом",
             "commercial_use": "unverified",
             "evidence": "docs/research/2026-09-27-animation-audit/services.md"}


def sha(path):
    h = hashlib.sha256()
    with open(os.path.join(REPO, path), "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def file_entry(path, fmt):
    ex = os.path.exists(os.path.join(REPO, path))
    e = {"path": path, "exists": ex, "format": fmt}
    if ex:
        e["sha256"] = sha(path)
    return e


def val(name):
    p = os.path.join(VAL, name + ".validation.json")
    if not os.path.exists(p):
        return None, {"result": "not_run"}
    with open(p, encoding="utf-8") as f:
        r = json.load(f)
    return r, {"result": r["result"], "report": os.path.relpath(p, REPO).replace("\\", "/"),
               "fails": r["fails"], "warnings": r.get("warnings", []), "date": "2026-09-28"}


def load_json(rel):
    p = os.path.join(REPO, rel)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def contract_revision():
    return load_json("docs/art-pipeline/rig/rig-contract.json")["revision"]


def h2anim(char, clip):
    """Production-слот, заполненный кандидатом H2Anim (волна 5c), или None, если спеки/клипа нет."""
    spec = load_json(H2ANIM[char])
    if not spec or clip not in spec["clips"]:
        return None
    pre, asset = CHARS[char]
    t = TARGETS[clip]
    hero = spec["ue_hero"]
    c = spec["clips"][clip]
    fbx = "%s/export/AM_%s_%s.fbx" % (spec["run_dir"], hero, clip)
    if not os.path.exists(os.path.join(REPO, fbx)):
        return None
    cid = f"{pre}-{clip}"
    vrel = "docs/art-pipeline/animation-library/validation-h2anim/AM_%s_%s.validation.json" % (hero, clip)
    rep_v = load_json(vrel)
    fbx_sha = sha(fbx)
    if rep_v is None:
        v = {"result": "not_run"}
    else:
        v = {"result": rep_v["result"], "report": vrel, "fails": rep_v["fails"],
             "warnings": rep_v.get("warnings", []), "date": "2026-09-29"}
        if rep_v.get("clip_sha256") != fbx_sha:
            v = {"result": "not_run"}  # отчёт от другой версии файла
    contact = load_json("%s/reports/contact-%s.json" % (spec["run_dir"], clip))
    contact_ok = bool(contact) and contact.get("result") == "pass"
    contact_warn = sorted(k["check"] for k in (contact or {}).get("checks", []) if k["status"] == "warn")
    imp = load_json("%s/reports/ue-import-clips.json" % spec["run_dir"]) or {}
    name = "AM_%s_%s" % (hero, clip)
    rec = next((x for x in imp.get("clips", []) if x.get("name") == name), None)
    imported = bool(rec) and rec.get("legacy_fbx_import") and rec.get("force_root_lock_ok") and \
        (imp.get("fbx_sha256") or {}).get(name) == fbx_sha and rec.get("skeleton") == spec["ue"]["skeleton"]
    if v["result"] == "pass" and contact_ok and imported:
        status = "technically_imported"
    elif v["result"] == "pass":
        status = "measured"
    else:
        status = "draft_test"
    target_path = "%s/%s" % (spec["ue"]["clips_folder"], name)
    note = ("кандидат H2Anim волны 5c на rest %s (%s): шаблон дельт %s + авторский слой по видео-референсу %s; "
            "контакты (clip_contact_check): %s%s; UE: %s на канонический скелет %s; художественно не принят"
            % (spec["target"].get("rest_generation"), spec["target"]["sk_fbx"],
               (c.get("template") or {}).get("file", "нет"), c.get("reference"),
               "PASS" if contact_ok else ("FAIL" if contact else "не проверены"),
               (" (WARN: %s)" % ", ".join(contact_warn)) if contact_warn else "",
               "импортирован" if imported else "не импортирован", spec["ue"]["skeleton"]))
    if spec["target"].get("rebake_on"):
        note += "; ПЕРЕЗАПЕЧЬ НА %s" % spec["target"]["rebake_on"]
    if cid in CONDITIONAL:
        note += "; " + CONDITIONAL[cid]
    dur = {"target": t["duration"], "target_status": t["status"], "measured": rep_v and rep_v.get("duration_s")}
    if clip in ("HitReact", "DeathSettle"):
        dur["target"] = {"HitReact": "0.4 (предложение волны 5c, 04) vs 0.9 (CUE-011)",
                         "DeathSettle": "0.875-0.9 (предложение волны 5c, 04), <=0.95 (CUE-013)"}[clip]
        dur["target_status"] = "open"
    return {
        "id": cid, "character": char, "asset_id": asset, "clip": clip, "role": "production",
        "required_mvp": cid not in CONDITIONAL, "cue": t["cue"],
        "source": {"type": "blender_keyframed",
                   "tool": "Blender 5.2.2, tools/tripo-pipeline/anim/clip_author.py (дельты в осях арматуры, IK стоп)",
                   "reference": H2ANIM[char], "files": [file_entry(fbx, "fbx")]},
        "license": OWN,
        "fps": {"target": 24, "measured": rep_v and rep_v.get("fps")},
        "duration_s": dur,
        "loop": t["loop"], "root_motion": "in_place",
        "skeleton": {"contract_key": V2_KEY, "version": contract_revision()},
        "ue": {"target_path": target_path, "status": "technically_imported" if imported else "proposed",
               "evidence": "%s/reports/ue-import-clips.json" % spec["run_dir"]},
        "status": status, "validation": v, "notes": note,
    }


def slot(char, clip):
    pre, asset = CHARS[char]
    t = TARGETS[clip]
    cid = f"{pre}-{clip}"
    note = "слот брифа 18; производственного клипа нет"
    if cid in CONDITIONAL:
        note += "; " + CONDITIONAL[cid]
    return {
        "id": cid, "character": char, "asset_id": asset, "clip": clip, "role": "production",
        "required_mvp": cid not in CONDITIONAL, "cue": t["cue"], "source": {"type": "none"}, "license": NO_LICENSE,
        "fps": {"target": 24, "measured": None},
        "duration_s": {"target": t["duration"], "target_status": t["status"], "measured": None},
        "loop": t["loop"], "root_motion": "in_place",
        "skeleton": {"contract_key": V2_KEY, "version": contract_revision()},
        "ue": {"target_path": f"/Game/PipelineCandidates/{asset}/Animation/AM_{char}_{clip}", "status": "proposed"},
        "status": "proposed", "validation": {"result": "not_run"},
        "notes": note,
    }


def medusa_draft(clip):
    rep, v = val(f"AM_Medusa_{clip}")
    t = TARGETS[clip]
    fbx = f"blender/ASSET-MEDUSA-001/export/AM_Medusa_{clip}.fbx"
    return {
        "id": f"MED-{clip}-draft", "character": "Medusa", "asset_id": "ASSET-MEDUSA-001", "clip": clip,
        "role": "test", "required_mvp": False, "cue": t["cue"],
        "source": {"type": "blender_keyframed", "tool": "Blender 5.2.2",
                   "reference": "blender/ASSET-MEDUSA-001/build_segmented_medusa.py#actions_for",
                   "files": [file_entry(fbx, "fbx")]},
        "license": OWN,
        "fps": {"target": 24, "measured": rep and rep.get("fps")},
        "duration_s": {"target": t["duration"], "target_status": t["status"],
                       "measured": rep and rep.get("duration_s")},
        "loop": t["loop"], "root_motion": "in_place",
        "skeleton": {"contract_key": "UM_HUMANOID_17_v1", "version": "p16-2026-09-28"},
        "ue": {"target_path": f"/Game/ART004/Medusa/Animation/AM_Medusa_{clip}", "status": "technically_imported",
               "evidence": "blender/ASSET-MEDUSA-001/ue-import-result.json"},
        "status": "draft_test", "validation": v,
        "notes": "черновой клип ART-004 (2-3 кости); только тестовый файл пайплайна, художественно не принят; работа над анимациями остановлена до пайплайна с видео-референсами",
    }


def tripo_test():
    rep, v = val("tripo-preset-stoya-otdyh-d562")
    return {
        "id": "MED-Idle-tripo-preset-test", "character": "Medusa", "asset_id": "ASSET-MEDUSA-001", "clip": "Idle",
        "role": "test", "required_mvp": False, "cue": ["state:Idle"],
        "source": {"type": "tripo_preset", "tool": "Tripo Studio, пресет «стоя_отдых», Animate in place",
                   "task_id": "d562f057-1455-4663-8cd8-bb738175111d",
                   "reference": RUN + "/README.md",
                   "files": [file_entry(RUN + "/source/d562f057-ue5-forced-anim-preset-stoya-otdyh-inplace-fbx-blender.zip", "fbx"),
                             file_entry(FIX + "/tripo-preset-stoya-otdyh-d562/tripo_convert_93b4445d-b871-4057-a0d7-1317f45a1548.fbx", "fbx")]},
        "license": TRIPO_LIC,
        "fps": {"target": 24, "measured": rep and rep.get("fps")},
        "duration_s": {"target": "2-3 (loop)", "target_status": "proposal", "measured": rep and rep.get("duration_s")},
        "loop": True, "root_motion": "in_place",
        "skeleton": {"contract_key": "UM_HUMANOID_17_v1", "version": "p16-2026-09-28",
                     "retarget_map": "tripo_ue5_mannequin_to_um17"},
        "ue": {"status": "proposed"},
        "status": "rejected", "validation": v,
        "notes": "технические проверки валидатора проходят, но риг под клипом сломан (принудительный авториг Tripo на позе миниатюры): голова, лук и плащ разрываются; длительность 17,6 с вместо 2-3 с",
    }


def bvh_fixture():
    rep, v = val("bvh-roundtrip-AM_Medusa_LungeAttack")
    return {
        "id": "MED-LungeAttack-bvh-fixture", "character": "Medusa", "asset_id": "ASSET-MEDUSA-001",
        "clip": "LungeAttack", "role": "test", "required_mvp": False, "cue": ["CUE-008"],
        "source": {"type": "blender_keyframed", "tool": "Blender 5.2.2 export_anim.bvh (Z-up)",
                   "reference": "docs/art-pipeline/animation-library/VALIDATION.md",
                   "files": [file_entry(FIX + "/AM_Medusa_LungeAttack.bvh", "bvh")]},
        "license": OWN,
        "fps": {"target": 24, "measured": rep and rep.get("fps")},
        "duration_s": {"target": 0.6, "target_status": "proposal", "measured": rep and rep.get("duration_s")},
        "loop": False, "root_motion": "in_place",
        "skeleton": {"contract_key": "UM_HUMANOID_17_v1", "version": "p16-2026-09-28"},
        "ue": {"status": "proposed"},
        "status": "draft_test", "validation": v,
        "notes": "BVH-фикстура для проверки ветки BVH валидатора (round-trip из FBX, make_fixtures.py bvh); не клип для игры",
    }


def glb_fixture():
    rep, v = val("glb-roundtrip-AM_Medusa_LungeAttack")
    return {
        "id": "MED-LungeAttack-glb-fixture", "character": "Medusa", "asset_id": "ASSET-MEDUSA-001",
        "clip": "LungeAttack", "role": "test", "required_mvp": False, "cue": ["CUE-008"],
        "source": {"type": "blender_keyframed", "tool": "Blender 5.2.2 export_scene.gltf (GLB, без картинок и материалов)",
                   "reference": "tools/tripo-pipeline/anim/make_fixtures.py",
                   "files": [file_entry(FIX + "/AM_Medusa_LungeAttack.glb", "glb")]},
        "license": OWN,
        "fps": {"target": 24, "measured": rep and rep.get("fps")},
        "duration_s": {"target": 0.6, "target_status": "proposal", "measured": rep and rep.get("duration_s")},
        "loop": False, "root_motion": "in_place",
        "skeleton": {"contract_key": "UM_HUMANOID_17_v1", "version": "p16-2026-09-28"},
        "ue": {"status": "proposed"},
        "status": "draft_test", "validation": v,
        "notes": "GLB-фикстура ветки GLB валидатора (round-trip из FBX, make_fixtures.py glb); run_p16_validation.py сверяет рост и пик сдвига с FBX; не клип для игры",
    }


def build():
    clips = [h2anim(c, k) or slot(c, k) for c in CHARS for k in TARGETS]
    clips += [medusa_draft(k) for k in TARGETS] + [tripo_test(), bvh_fixture(), glb_fixture()]
    filled = sum(1 for c in clips if c["role"] == "production" and c["source"]["type"] != "none")
    m = {"schema": "unmatched.animation-clip-manifest/1", "revision": "h2anim-2026-09-29",
         "rig_contract": "docs/art-pipeline/rig/rig-contract.json",
         "notes": ["16 production-слотов = 4 клипа D-11 x 4 персонажа (бриф 18 §4): 15 безусловных, HAR-HitReact условен до AD-CNF-30 (required_mvp=false); заполнено кандидатами H2Anim (волна 5c, UM_HUMANOID_17_v2): %d" % filled,
                   "production-слоты — контракт v2 (v1 закрыт для новых клипов, RIG-CONTRACT §0 п.2); черновики AM_Medusa_* v1 — тестовые записи",
                   "длительности — ПРЕДЛОЖЕНИЕ/ОТКРЫТО (AD-OPEN-46); FPS 24 измерен на S05/ART004",
                   "test-записи не могут стать artistically_accepted (правило схемы)"],
         "clips": clips}
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("MANIFEST_BUILT", len(clips), "clips")


def check():
    import jsonschema  # pip-пакет; есть в системном Python
    with open(SCHEMA, encoding="utf-8") as f:
        schema = json.load(f)
    with open(MANIFEST, encoding="utf-8") as f:
        m = json.load(f)
    errors = [e.message for e in jsonschema.Draft202012Validator(schema).iter_errors(m)]
    ids = [c["id"] for c in m["clips"]]
    if len(ids) != len(set(ids)):
        errors.append("duplicate ids")
    for c in m["clips"]:
        for fe in c["source"].get("files", []):
            p = os.path.join(REPO, fe["path"])
            if fe["exists"] != os.path.exists(p):
                errors.append(f"{c['id']}: exists mismatch {fe['path']}")
            elif fe["exists"] and fe.get("sha256") != sha(fe["path"]):
                errors.append(f"{c['id']}: sha256 mismatch {fe['path']}")
        rep = c["validation"].get("report")
        if rep and not os.path.exists(os.path.join(REPO, rep)):
            errors.append(f"{c['id']}: missing report {rep}")
        if c["status"] in ("measured", "technically_imported", "artistically_accepted") and c["validation"]["result"] != "pass":
            errors.append(f"{c['id']}: status {c['status']} requires validation pass")
    prod = [c for c in m["clips"] if c["role"] == "production"]
    print("MANIFEST_CHECK", "PASS" if not errors else "FAIL", "clips", len(m["clips"]), "production", len(prod))
    for e in errors:
        print("  -", e)
    return 0 if not errors else 1


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "build":
        build()
        sys.exit(check())
    sys.exit(check())
