"""Манифест библиотеки анимаций: сборка (build) и проверка (check).

python tools/tripo-pipeline/anim/clip_manifest.py build   # пересобрать clip-manifest.json
python tools/tripo-pipeline/anim/clip_manifest.py check   # схема + файлы + sha256 + правила статусов

build собирает записи функциями slot()/medusa_draft()/tripo_test()/bvh_fixture()/glb_fixture() ниже
(16 слотов брифа 18 §4: 4 клипа D-11 x 4 персонажа; 15 безусловных, HAR-HitReact условен до
AD-CNF-30 — бриф 18, стр. 10) и тестовые файлы, подставляет измеренные fps/длительности и результаты
из docs/art-pipeline/animation-library/validation/*.validation.json и считает sha256.
Статусы не повышаются автоматически: сборка никогда не пишет technically_imported
или artistically_accepted для production-слотов без явной правки кода записи.
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
        "skeleton": {"contract_key": "UM_HUMANOID_17_v1", "version": "p16-2026-09-28"},
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
    clips = [slot(c, k) for c in CHARS for k in TARGETS]
    clips += [medusa_draft(k) for k in TARGETS] + [tripo_test(), bvh_fixture(), glb_fixture()]
    m = {"schema": "unmatched.animation-clip-manifest/1", "revision": "p16-2026-09-28",
         "rig_contract": "docs/art-pipeline/rig/rig-contract.json",
         "notes": ["16 production-слотов = 4 клипа D-11 x 4 персонажа (бриф 18 §4): 15 безусловных, HAR-HitReact условен до AD-CNF-30 (required_mvp=false); ни один не заполнен",
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
