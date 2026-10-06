"""AN-31 (VP-07, VP-72): the harpy base-digit assets - the unlit disc material M_UM_BaseDigit and the digit font.

    python tools/art/hero/base_digit_import.py            # import + build + verify (saved), report to C:/tmp/an31

Assets (the C++ side is AS08FighterActor's BaseDigitDisc / BaseDigitText, S08HeroesV2::HarpyNumber):
  /Game/UM/Materials/v2/M_UM_BaseDigit          Unlit, opaque, one VectorParameter "Color" (default card.navy
                                                #061623); the runtime MID sets the color (FLinearColor::FromSRGBColor).
  /Game/UM/Fonts/F_UM_RobotoBoldCondensed       UFontFace - the engine's Slate Roboto-BoldCondensed.ttf payload.
  /Game/UM/Fonts/F_UM_RobotoBoldCondensed_Offline
                                                UFont whose composite default typeface is that face, glyphs 0-9.

VP-AN32 (recorded): UE 5.8 has no offline font importer any more (FontImportSubsystem removed), so the "_Offline"
font is a runtime-cached composite over the imported TTF payload - self-contained in the pak, rasterized on demand;
the asset keeps the card's name. Roboto is Apache 2.0 (unreal/Unmatched/Licenses/THIRD_PARTY_NOTICES.txt).
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
    res = de010.run_editor(UE_SCRIPT, {"out": str(work / "base-digit-import.json"),
                                       "fonts": FONTS, "materials": MATERIALS}, work, "base-digit-import")
    de010.write(work / "base-digit-import.json", res)
    print("ok:", {k: res.get(k) for k in ("material", "font_face", "font")})
    return 0 if all(res.get(k, {}).get("ok") for k in ("material", "font_face", "font")) else 1


if __name__ == "__main__":
    sys.exit(main())
