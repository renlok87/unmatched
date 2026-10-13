"""Prepare clip acceptance r1 of ASSET-ACHILLES-001 (animation-vfx-sfx.md §10.3): frames/ copies + filled prompt
(from evidence/acceptance-anim-prompts/<Clip>/acceptor-prompt.md of stage 6) + run-acceptor.ps1 copy.
Adapted from the Ancient Leshen stage-7a task of the same name."""
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

REPO = Path("C:/Users/ren/WebstormProjects/unmached/unmached")
A = REPO / "art/pipeline-candidates/ASSET-ACHILLES-001"
RUN = A / "20261014-h2anim"
E_REL = "art/pipeline-candidates/ASSET-ACHILLES-001/evidence/acceptance-anim/20261014-r1"
E = REPO / E_REL
SPEC = json.loads((A / "build-profiles/achilles-h2anim.json").read_text(encoding="utf-8"))
CARRIER_NOTE = (
    "- UE-кадры (`*-ue-editor.jpg`, лист `Achilles-H2Anim-ue-sheet.jpg`) сняты инструментом `h2anim_ue.py frames` "
    "на меше-носителе `/Game/PipelineCandidates/Achilles/Rig/SK_Achilles` (геометрия H2 без look-dev материалов, "
    "поэтому фигура серая — так снимаются все герои библиотеки D-11) на подставке `SM_Achilles_H2LD_Base` (её MI по "
    "умолчанию — команда P1, поэтому борт подставки жёлтый); цвет и материал в этой приёмке не оцениваются. Свет — "
    "закреплённый cobble-probe rev 5 (`--light-pinned ASSET-HARPY-001/20260929-h3ld-ue/review/b3.2/review-b3.2.json`), "
    "High, редактор: это диагностические кадры, не K1/K2. Крупные планы Blender лежат и в "
    "{{E}}/<клип>/frames/ (копии файлов из preview/closeups-blender/).\n")


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


clips = sys.argv[1:] or list(SPEC["clips"])
for clip in clips:
    c = SPEC["clips"][clip]
    fdir = E / clip / "frames"
    fdir.mkdir(parents=True, exist_ok=True)
    src = [RUN / "preview" / ("Achilles-%s-blender-sheet.jpg" % clip)]
    src += sorted((RUN / "preview/closeups-blender").glob("Achilles-%s-*.jpg" % clip))
    for f in c["key_frames"]:
        for v in ("front", "q34"):
            src.append(RUN / "preview/ue" / ("Achilles-%s-f%02d-%s-ue-editor.jpg" % (clip, f, v)))
    if clip == "LungeAttack":
        src += sorted((RUN / "preview/ue").glob("Achilles-LungeAttack-f*-closeup-ue-editor.jpg"))
    src.append(RUN / "preview" / "Achilles-H2Anim-ue-sheet.jpg")
    files = []
    for s in src:
        if not s.is_file():
            raise SystemExit("missing frame " + str(s))
        shutil.copy2(s, fdir / s.name)
        files.append(s.name)
    tpl = (A / "evidence/acceptance-anim-prompts" / clip / "acceptor-prompt.md").read_text(encoding="utf-8")
    tpl = re.sub(r"<!--.*?-->\n\n", "", tpl, count=1, flags=re.S)
    if "<!--" in tpl:
        raise SystemExit("template comment not removed for " + clip)
    for path, want in re.findall(r'"path": "([^"]+)", "sha256": "([0-9a-f]{64})"', tpl):
        got = sha(REPO / path)
        if got != want:
            raise SystemExit("%s: sha256 of %s changed: %s != %s" % (clip, path, got, want))
    marker = "- Контакт:" if "- Контакт:" in tpl else "- Клип:"
    tpl = tpl.replace(marker, CARRIER_NOTE + marker, 1)
    out = (tpl.replace("{{E}}", E_REL).replace("{{DATE}}", "2026-10-14").replace("{{CYCLE}}", "r1")
           .replace("{{PREVIOUS_CARD_JSON}}", "null")
           .replace("{{FRAMES_FILES_JSON}}", json.dumps(files, ensure_ascii=False)))
    if "{{" in out:
        raise SystemExit("placeholder left in %s: %s" % (clip, re.findall(r"\{\{[A-Z_]+\}\}", out)))
    (E / clip / "acceptor-prompt.md").write_text(out, encoding="utf-8", newline="\n")
    print(clip, len(files), "frames", sum((fdir / f).stat().st_size for f in files) // 1024, "KiB")
shutil.copy2(A / "evidence/acceptance-anim-prompts/run-acceptor.ps1", E / "run-acceptor.ps1")
