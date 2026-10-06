// VS-2 A2, IC-44 / IC-45 (docs/game-design/visual/06-tasks/icons.csv; 02-visual-design.md §5.5, ВР-78; HUD-AND-ICONS
// §1.7, HI-02): the team chip of the screen tag and the fighter plate - the v3 `team-chip-p1` (circle) and
// `team-chip-p2` (hexagon) textures of art/imagegen/hud-icons-v3 (white body, tinted by the chip colour as before,
// И-5), replacing the mvp-v1 12 px chips T_UI_TeamShape_Circle_12 / _Hex_12.
//
//   size      the chip is drawn at the su of its carrier (Brush.ImageSize = su). The texture is the smallest v3 export
//             >= su x DPI x UI scale (S08IconMotion::ExportSizePx: 18 / 24 / 32 / 36 / 48 / 64, no mips, И-9).
//             ВР-78 puts the chip at 24 su in the HUD (HudSu); the tag and the plate keep their 12 su boxes until
//             their own steps (HB-45 tag, HB-46 plate, H12), so until then the 12 su box shows the 18 px export
//             (ВР-VS2-16).
//   rollback  -S08IconLegacy (the flag of the other v3 rollbacks, RD-1 / HB-23): the mvp-v1 12 px chips at 12 su.
//   trace     "HUD team chips ready=.. chips=v3|legacy(-S08IconLegacy) su=.. px=.." and the ARTLOOK field
//             chips=v3|legacy(-S08IconLegacy).
#pragma once

#include "CoreMinimal.h"
#include "Styling/SlateBrush.h"

class UTexture2D;

namespace UmTeamChip {

/** ВР-78: the team chip in the HUD (tag, combat edge ribbon) is 24 su. */
inline constexpr float HudSu = 24.0f;
/** The mvp-v1 chips (rollback): exact 12 px textures shown at 12 su. */
inline constexpr float LegacySu = 12.0f;
inline const TCHAR* const LegacyFlagName = TEXT("S08IconLegacy");

/** True with -S08IconLegacy on this command line. */
UNMATCHED_API bool LegacyRequested(const TCHAR* CommandLine);
/** The v3 export for a chip of Su at PxPerSu (DPI x UI scale): the smallest of 18..64 that covers it. */
UNMATCHED_API int32 TexturePx(float Su, float PxPerSu);
/** Object path of the chip of Slot (0 = P1 circle, 1 = P2 hexagon): v3 T_IV3_team_chip_p<n>_<Px>, or mvp-v1. */
UNMATCHED_API FString TexturePath(int32 Slot, int32 Px, bool bLegacy);
/** The ARTLOOK field: "chips=v3" or "chips=legacy(-S08IconLegacy)". */
UNMATCHED_API FString ArtLookField(const TCHAR* CommandLine);

/** The two chip brushes of one HUD build. */
struct UNMATCHED_API FUmTeamChipBrushes {
  bool bReady = false;   // both textures loaded
  bool bLegacy = false;
  float Su = 0.0f;       // Brush.ImageSize
  int32 Px = 0;          // texture size
  FSlateBrush Brushes[2];
  TArray<UTexture2D*> Textures;  // the caller keeps them referenced (AS08FlowGameMode::ArtHudAssets)
  /** "chips=v3 su=12 px=18" / "chips=legacy(-S08IconLegacy) su=12 px=12". */
  FString TraceFields() const;
};

/** Loads both chips for a carrier of Su (v3 by default, mvp-v1 with -S08IconLegacy on CommandLine). */
UNMATCHED_API FUmTeamChipBrushes Load(float Su, float PxPerSu, const TCHAR* CommandLine);

}  // namespace UmTeamChip
