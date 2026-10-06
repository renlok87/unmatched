"""AN-31 (ВР-07, ВР-72, ВР-Z1R-03): the harpy base-digit assets - the offline digit font and the two unlit materials.

    python tools/art/hero/base_digit_import.py            # import + build + verify (saved), report to C:/tmp/an31

Assets (the C++ side is AS08FighterActor's BaseDigitDisc / BaseDigitText, S08HeroesV2::HarpyNumber / BaseDigitPlacement):
  /Game/UM/Fonts/F_UM_RobotoBoldCondensed_Offline
                    OFFLINE font (texture page, distance-field alpha, em 32 px x16 supersampled) of the digits 0-9,
                    Roboto Bold Condensed (font.card, Apache 2.0) from the engine's Slate/Fonts TTF. UTextRenderComponent
                    draws only offline fonts: the first Z-1 build used a runtime UFont over a FontFace, which the text
                    render proxy skips - no digit was ever drawn (Z-1 review D1). UTrueTypeFontFactory exists in UE 5.8;
                    its options are filled by the editor-only C++ helper US08BaseDigitAuthoringLibrary (the options struct
                    is not Python-visible) after the TTF is made visible to GDI for this editor process only.
  /Game/UM/Materials/v2/M_UM_BaseDigit      Unlit opaque disc, EyeAdaptationInverse(VectorParameter "Color").
  /Game/UM/Materials/v2/M_UM_BaseDigitText  Unlit masked digit, EyeAdaptationInverse(VectorParameter "Color"), opacity
                                            mask = FontSampleParameter "Font".A (clip 0.5).
  /Game/UM/Fonts/F_UM_RobotoBoldCondensed   the FontFace of the first build - kept as the imported source face, unused
                                            at runtime.
The editor of THIS checkout must be built (the C++ helper). Roboto is Apache 2.0 (unreal/Unmatched/Licenses/
THIRD_PARTY_NOTICES.txt).
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "tools" / "art" / "de010"))
import de010  # noqa: E402

UE_SCRIPT = HERE / "base_digit_import_ue.py"
FONTS = "/Game/UM/Fonts"
MATERIALS = "/Game/UM/Materials/v2"


def main() -> int:
    work = Path("C:/tmp/an31")
    work.mkdir(parents=True, exist_ok=True)
    res = de010.run_editor(UE_SCRIPT, {"out": str(work / "base-digit-import.json"), "fonts": FONTS,
                                       "materials": MATERIALS, "height": 32}, work, "base-digit-import")
    de010.write(work / "base-digit-import.json", res)
    print("ok:", {k: res.get(k, {}).get("ok") for k in ("gdi", "font", "material", "text_material")})
    return 0 if all(res.get(k, {}).get("ok") for k in ("gdi", "font", "material", "text_material")) else 1


if __name__ == "__main__":
    sys.exit(main())
