// VS-3 (the VS-2 review, docs/game-design/evidence/VISUAL/VS-2/README.md «Ревью VS-2», remark for VS-3): the portraits
// never vanish. Before, BuildTurnHudWidgets built the old Slate portrait column only by the flag (-S08SlateHud[=panels])
// and BuildUmHud handed the portraits to the UMG panels only after UUmHudRoot::Create; when the root failed without the
// flag (trace 'HUD-ROOT impl=umg created=0') nobody built them. Now the game mode builds the Slate column in that case
// too (AS08FlowGameMode::BuildTurnPortraitFallback, trace 'HUD-TURN config portraits=1 reason=umg-root-failed ...').
//   Wanted  the column is built when the art look is on and either the panels block is on Slate or the UMG root did
//           not come up (decision ВР-VS3-01).
//   Build   the column of before (the opponent above, mine below; left-bottom, 24 su from the edges, 8 su apart) on a
//           Slate canvas - the same code for both cases.
#pragma once

#include "CoreMinimal.h"
#include "Templates/SharedPointer.h"

class SConstraintCanvas;
class SVerticalBox;
class US08TurnPortraitWidget;
class UWorld;
struct FS08TurnHudLook;

namespace UmSlatePortraits {
/** Left / bottom gap of the column and the gap between the two portraits (su). */
inline constexpr float EdgeSu = 24.0f;
inline constexpr float GapSu = 8.0f;

/** World-free rule (ВР-VS3-01): the Slate portrait column is needed with the art look when the panels are on Slate or
 *  the UMG HUD root was not created. */
constexpr bool Wanted(bool bArtLook, bool bPanelsOnSlate, bool bUmgRootCreated) {
  return bArtLook && (bPanelsOnSlate || !bUmgRootCreated);
}

struct UNMATCHED_API FColumn {
  US08TurnPortraitWidget* Opponent = nullptr;
  US08TurnPortraitWidget* Own = nullptr;
  TSharedPtr<SVerticalBox> Column;
  bool IsValid() const { return Opponent && Own && Column.IsValid(); }
};

/** Creates the two portraits (collapsed until the live match HUD shows them) and adds the column to Canvas. False
 *  (nothing added) when a portrait cannot be created. */
UNMATCHED_API bool Build(UWorld* World, const TSharedRef<SConstraintCanvas>& Canvas, const FS08TurnHudLook& Look,
                         FColumn& Out);
}  // namespace UmSlatePortraits
