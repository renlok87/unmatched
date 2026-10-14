"""Scratch: clip acceptance r2 of ASSET-ACHILLES-001 (animation-vfx-sfx.md 10.3) after model r3 (copy of the Leshen
C:/tmp/leshen-r3-clips/prep_r2.py). frames/ = the r1 card's file list taken from the r3 clip run (same frames and views,
model r3) + the r2 prompt built from the filled r1 prompt of the same clip (cycle, paths, accepted_object, previous_card,
executor, previous-card section, the closed armhole item dropped from the known limits; nothing else changes) +
run-acceptor.ps1 copy.
    python prep_r2.py [Clip ...]
"""
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

REPO = Path("C:/Users/ren/WebstormProjects/unmached/unmached")
A_REL = "art/pipeline-candidates/ASSET-ACHILLES-001"
A = REPO / A_REL
RUN_REL = A_REL + "/20261014-h2anim-r3"
RUN = REPO / RUN_REL
R1_REL = A_REL + "/evidence/acceptance-anim/20261014-r1"
R1 = REPO / R1_REL
E_REL = A_REL + "/evidence/acceptance-anim/20261014-r2"
E = REPO / E_REL
SPEC_REL = A_REL + "/build-profiles/achilles-h2anim-r3.json"
SPEC = json.loads((REPO / SPEC_REL).read_text(encoding="utf-8"))
ARMHOLE = ("; у правой подмышки сзади кромка плаща (стык частей рука/плащ, вырез плаща по кирасе этапа 3) при выносе "
           "правой руки вперёд открывается рваной полоской (LungeAttack к.4–10, DeathSettle к.7–21; виды сзади-справа "
           "-q34b/-right) — это кромка модели, а не растяжение клипом (skin_stretch: видимых рваных рёбер 0); виды "
           "front/q34 её не показывают")
PREV_OLD = ("- Предыдущая карточка: null (null на r1). Если она есть — по каждому пункту её\n"
            "  rework_fix_list запиши в rationale своего измерения только «r<N> п.<k>: закрыт» или «r<N> п.<k>: не "
            "закрыт» с кадром;\n"
            "  баллы ставь заново по свежим кадрам. Отчётам исполнителя в свободной форме не верь: статус пункта — "
            "только по кадру.\n")
PREV = {
    "DeathSettle": ("- Предыдущая карточка: {card} (цикл r1, verdict rework_blender, score {score}). Баллы ставь заново по "
                    "свежим кадрам r2.\n"
                    "  Пункты rework_fix_list r1 — статус проверь сам по свежим кадрам и запиши в rationale своего "
                    "измерения только «r1 п.1: закрыт» или «r1 п.1: не закрыт» с кадром:\n"
                    "  1. D, Achilles-DeathSettle-f21-q34b.jpg: рваная кромка за правой подмышкой — r3: закрыта стыками "
                    "весов.\n"
                    "  Отчётам исполнителя в свободной форме не верь: статус пункта — только по кадру.\n"),
    "_other": ("- Предыдущая карточка: {card} (цикл r1, verdict pass, score {score}, rework_fix_list пуст). FBX клипа "
               "пересобран на модели r3 (веса стыков руки с плащом и кирасой у правой подмышки, bake 20261014-h2-bake-r3; "
               "ключи клипа те же), поэтому приёмка повторяется. Баллы ставь заново по свежим кадрам r2.\n"),
}
Q34B = {
    "LungeAttack": ("-f07-q34b.jpg (кромка плаща у правой подмышки — известный предел, см. ниже)",
                    "-f07-q34b.jpg (кромка у правой подмышки сзади)"),
    "DeathSettle": ("-f21-q34b.jpg (кромка плаща у правой подмышки — известный предел)",
                    "-f21-q34b.jpg (кромка у правой подмышки сзади — пункт r1 п.1)"),
}
LUNGE_WARN = ("- WARN контактов: limb_body_R до 7 пар правой руки с кирасой (spine) на к.11–13 (возврат, мягкое касание; "
              "rest 0); skin_stretch — рёбра только в закрытых местах (видимых рваных рёбер 0): подол плаща у щиколоток и "
              "щиколотки при сгибе колен.")
LUNGE_WARN_NEW = ("- WARN контактов: skin_stretch — рёбра только в закрытых местах (видимых рваных рёбер 0): подол плаща у "
                  "щиколоток и щиколотки при сгибе колен (limb_body_R на модели r3 — pass).")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def sub(text, old, new, count=None):
    n = text.count(old)
    if n == 0 or (count is not None and n != count):
        raise SystemExit("replace %r: %d hits" % (old[:80], n))
    return text.replace(old, new)


def source(name):
    if name.endswith("-blender-sheet.jpg") or name.endswith("-H2Anim-ue-sheet.jpg"):
        return RUN / "preview" / name
    if name.endswith("-ue-editor.jpg"):
        return RUN / "preview/ue" / name
    return RUN / "preview/closeups-blender" / name


clips = sys.argv[1:] or list(SPEC["clips"])
for clip in clips:
    r1_card = json.loads((R1 / clip / "card.json").read_text(encoding="utf-8"))
    files = r1_card["frames"]["files"]
    fdir = E / clip / "frames"
    fdir.mkdir(parents=True, exist_ok=True)
    for name in files:
        s = source(name)
        if not s.is_file():
            raise SystemExit("missing frame " + str(s))
        shutil.copy2(s, fdir / name)
    t = (R1 / clip / "acceptor-prompt.md").read_text(encoding="utf-8")
    t = sub(t, "AM_Achilles_%s, цикл r1" % clip, "AM_Achilles_%s, цикл r2" % clip, 1)
    t = sub(t, R1_REL, E_REL)
    t = sub(t, A_REL + "/20261014-h2anim/", RUN_REL + "/")
    t = sub(t, A_REL + "/build-profiles/achilles-h2anim.json", SPEC_REL)
    t = sub(t, "(геометрия H2 без look-dev материалов,",
            "(геометрия H2 модели r3 — bake 20261014-h2-bake-r3, носитель переимпортирован из неё — без look-dev "
            "материалов,", 1)
    t = sub(t, 'cycle "r1", previous_card null,',
            'cycle "r2", previous_card "%s/%s/card.json",' % (R1_REL, clip), 1)
    old_ao = re.search(r"accepted_object (\[.*?\]),?\n", t).group(1)
    fbx_rel = RUN_REL + "/export/AM_Achilles_%s.fbx" % clip
    new_ao = json.dumps([{"path": fbx_rel, "sha256": sha(REPO / fbx_rel)},
                         {"path": SPEC_REL, "sha256": sha(REPO / SPEC_REL)}], ensure_ascii=False)
    t = sub(t, old_ao, new_ao, 1)
    t = sub(t, "agent:stage6-achilles", "agent:stage5r3-achilles", 1)
    t = sub(t, ARMHOLE, "", 1)
    if clip in Q34B:
        t = sub(t, Q34B[clip][0], Q34B[clip][1], 1)
    if clip == "LungeAttack":
        t = sub(t, LUNGE_WARN, LUNGE_WARN_NEW, 1)
    card_rel = R1_REL + "/%s/card.json" % clip
    prev_new = PREV.get(clip, PREV["_other"]).format(card=card_rel, score=str(r1_card["score"]).replace(".", ","))
    t = sub(t, PREV_OLD, prev_new, 1)
    t = sub(t, "(чат, git log, отчёты исполнителя в свободной форме, другие\n  карточки этого цикла).",
            "(чат, git log, отчёты исполнителя в свободной форме, другие\n  карточки этого цикла, кроме предыдущей "
            "карточки r1 этого клипа).", 1)
    if "20261014-h2anim/" in t or "stage6-achilles" in t or "{{" in t or "подмышки сзади кромка плаща" in t \
            or "20261014-r1/" + clip + "/frames" in t:
        raise SystemExit("leftover r1 reference in " + clip)
    (E / clip / "acceptor-prompt.md").write_text(t, encoding="utf-8", newline="\n")
    print(clip, len(files), "frames", new_ao[:90])
shutil.copy2(R1 / "run-acceptor.ps1", E / "run-acceptor.ps1")
