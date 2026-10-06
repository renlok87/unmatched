// VS-2 A2, IC-44 / IC-45: the team chip textures of the tag and the plate (UmTeamChip.h).
#include "UmTeamChip.h"

#include "../S08IconMotion.h"
#include "Engine/Texture2D.h"
#include "Misc/Parse.h"
#include "UObject/UObjectGlobals.h"

namespace UmTeamChip {

bool LegacyRequested(const TCHAR* CommandLine) {
  return CommandLine && FParse::Param(CommandLine, LegacyFlagName);
}

int32 TexturePx(float Su, float PxPerSu) {
  return S08IconMotion::ExportSizePx(Su, PxPerSu);
}

FString TexturePath(int32 Slot, int32 Px, bool bLegacy) {
  if (bLegacy) {
    return Slot == 0 ? TEXT("/Game/ArtTests/ARTMarkers/Textures/T_UI_TeamShape_Circle_12")
                     : TEXT("/Game/ArtTests/ARTMarkers/Textures/T_UI_TeamShape_Hex_12");
  }
  return S08IconMotion::TextureObjectPath(Slot == 0 ? TEXT("team-chip-p1") : TEXT("team-chip-p2"), 0, Px);
}

FString ArtLookField(const TCHAR* CommandLine) {
  return LegacyRequested(CommandLine) ? FString::Printf(TEXT("chips=legacy(-%s)"), LegacyFlagName)
                                      : FString(TEXT("chips=v3"));
}

FString FUmTeamChipBrushes::TraceFields() const {
  return FString::Printf(TEXT("chips=%s su=%.0f px=%d"),
                         bLegacy ? *FString::Printf(TEXT("legacy(-%s)"), LegacyFlagName) : TEXT("v3"), Su, Px);
}

FUmTeamChipBrushes Load(float Su, float PxPerSu, const TCHAR* CommandLine) {
  FUmTeamChipBrushes Out;
  Out.bLegacy = LegacyRequested(CommandLine);
  Out.Su = Out.bLegacy ? LegacySu : FMath::Max(Su, 1.0f);
  Out.Px = Out.bLegacy ? static_cast<int32>(LegacySu) : TexturePx(Out.Su, PxPerSu);
  Out.bReady = true;
  for (int32 Slot = 0; Slot < 2; ++Slot) {
    UTexture2D* Chip = LoadObject<UTexture2D>(nullptr, *TexturePath(Slot, Out.Px, Out.bLegacy));
    if (!Chip) {
      Out.bReady = false;
      break;
    }
    Out.Textures.Add(Chip);
    FSlateBrush& Brush = Out.Brushes[Slot];
    Brush.SetResourceObject(Chip);
    Brush.ImageSize = FVector2D(Out.Su, Out.Su);
    Brush.DrawAs = ESlateBrushDrawType::Image;
    Brush.Tiling = ESlateBrushTileType::NoTile;
  }
  return Out;
}

}  // namespace UmTeamChip
