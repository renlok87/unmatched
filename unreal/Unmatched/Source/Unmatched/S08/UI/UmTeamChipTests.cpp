// VS-2 A2, IC-44 / IC-45 automation tests (UmTeamChip.h):
//   Unmatched.S08.Hud.TeamChip  the v3 chip export by su x DPI x UI scale (24 su: 18 / 24 / 32 / 36 / 48 at DPI 0.75 /
//                               1.0 / 1.333 / 150 % / 2.0; the 12 su boxes of the tag and plate: 18 at 100 %), the
//                               v3 textures exist at every export (exact size, no mips), the brushes carry the su and
//                               the texture, -S08IconLegacy restores the mvp-v1 12 px chips, ARTLOOK chips= field.
// Headless:
//   UnrealEditor-Cmd.exe Unmatched.uproject -ExecCmds="Automation RunTests Unmatched.S08.Hud.TeamChip; Quit"
//     -unattended -nosplash -nullrhi
#if WITH_AUTOMATION_TESTS

#include "UmTeamChip.h"
#include "../S08ArtHudStyle.h"
#include "../S08ArtLook.h"
#include "Engine/Texture2D.h"
#include "Misc/AutomationTest.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmTeamChipTest, "Unmatched.S08.Hud.TeamChip",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FUmTeamChipTest::RunTest(const FString& Parameters) {
  // ВР-78: the HUD chip is 24 su; the export is the smallest >= su x px per su (02 §3.2 ВР-62, §5.3).
  TestEqual(TEXT("24 su at 720p (0.75)"), UmTeamChip::TexturePx(UmTeamChip::HudSu, 0.75f), 18);
  TestEqual(TEXT("24 su at 1080p"), UmTeamChip::TexturePx(UmTeamChip::HudSu, 1.0f), 24);
  TestEqual(TEXT("24 su at 1440p (1.333)"), UmTeamChip::TexturePx(UmTeamChip::HudSu, 4.0f / 3.0f), 32);
  TestEqual(TEXT("24 su at 150 %"), UmTeamChip::TexturePx(UmTeamChip::HudSu, 1.5f), 36);
  TestEqual(TEXT("24 su at 2160p (2.0)"), UmTeamChip::TexturePx(UmTeamChip::HudSu, 2.0f), 48);
  TestEqual(TEXT("12 su box (tag / plate before H12) at 100 %"), UmTeamChip::TexturePx(FS08ArtHudTagStyle().ChipSu, 1.0f), 18);
  TestEqual(TEXT("tag and plate chip boxes agree"), FS08ArtHudTagStyle().ChipSu, FS08ArtHudPlateStyle().TeamShapeSu);

  TestEqual(TEXT("v3 P1 path"), UmTeamChip::TexturePath(0, 24, false),
            FString(TEXT("/Game/S08/UI/IconsV3/T_IV3_team_chip_p1_24.T_IV3_team_chip_p1_24")));
  TestEqual(TEXT("v3 P2 path"), UmTeamChip::TexturePath(1, 36, false),
            FString(TEXT("/Game/S08/UI/IconsV3/T_IV3_team_chip_p2_36.T_IV3_team_chip_p2_36")));
  TestEqual(TEXT("legacy P1 path"), UmTeamChip::TexturePath(0, 12, true),
            FString(TEXT("/Game/ArtTests/ARTMarkers/Textures/T_UI_TeamShape_Circle_12")));
  TestEqual(TEXT("legacy P2 path"), UmTeamChip::TexturePath(1, 12, true),
            FString(TEXT("/Game/ArtTests/ARTMarkers/Textures/T_UI_TeamShape_Hex_12")));

  // every v3 export the picker can return is imported at its exact size without mips (tools/art/icons_v3_import.py)
  for (const int32 Px : {18, 24, 32, 36, 48, 64}) {
    for (int32 Slot = 0; Slot < 2; ++Slot) {
      const FString Path = UmTeamChip::TexturePath(Slot, Px, false);
      UTexture2D* Tex = LoadObject<UTexture2D>(nullptr, *Path);
      if (!TestNotNull(*FString::Printf(TEXT("texture %s"), *Path), Tex)) continue;
      const FIntPoint Imported = Tex->GetImportedSize();
      TestEqual(*FString::Printf(TEXT("%s width"), *Path), Imported.X, Px);
      TestEqual(*FString::Printf(TEXT("%s height"), *Path), Imported.Y, Px);
#if WITH_EDITORONLY_DATA
      TestEqual(*FString::Printf(TEXT("%s no mips"), *Path), static_cast<int32>(Tex->MipGenSettings),
                static_cast<int32>(TMGS_NoMipmaps));
#endif
    }
  }

  // default: v3, the carrier's su on the brush, the export texture behind it
  const UmTeamChip::FUmTeamChipBrushes V3 = UmTeamChip::Load(UmTeamChip::HudSu, 1.5f, TEXT(""));
  TestTrue(TEXT("v3 ready"), V3.bReady);
  TestFalse(TEXT("v3 not legacy"), V3.bLegacy);
  TestEqual(TEXT("v3 px at 150 %"), V3.Px, 36);
  TestEqual(TEXT("v3 trace"), V3.TraceFields(), FString(TEXT("chips=v3 su=24 px=36")));
  for (int32 Slot = 0; Slot < 2; ++Slot) {
    TestTrue(TEXT("brush ImageSize = su"), V3.Brushes[Slot].ImageSize.Equals(FVector2D(24.0, 24.0)));
    const UTexture2D* Tex = Cast<UTexture2D>(V3.Brushes[Slot].GetResourceObject());
    TestTrue(*FString::Printf(TEXT("brush %d texture"), Slot),
             Tex && Tex->GetName() == (Slot == 0 ? TEXT("T_IV3_team_chip_p1_36") : TEXT("T_IV3_team_chip_p2_36")));
  }
  TestEqual(TEXT("two textures kept"), V3.Textures.Num(), 2);

  // -S08IconLegacy: the mvp-v1 chips at 12 su
  const UmTeamChip::FUmTeamChipBrushes Old = UmTeamChip::Load(UmTeamChip::HudSu, 1.5f, TEXT(" -S08IconLegacy"));
  TestTrue(TEXT("legacy ready"), Old.bReady);
  TestTrue(TEXT("legacy flag"), Old.bLegacy);
  TestTrue(TEXT("legacy brush 12 su"), Old.Brushes[0].ImageSize.Equals(FVector2D(12.0, 12.0)));
  const UTexture2D* OldTex = Cast<UTexture2D>(Old.Brushes[1].GetResourceObject());
  TestTrue(TEXT("legacy P2 = mvp-v1 hexagon"), OldTex && OldTex->GetName() == TEXT("T_UI_TeamShape_Hex_12"));
  TestEqual(TEXT("legacy trace"), Old.TraceFields(), FString(TEXT("chips=legacy(-S08IconLegacy) su=12 px=12")));

  TestEqual(TEXT("ARTLOOK chips default"), UmTeamChip::ArtLookField(TEXT("")), FString(TEXT("chips=v3")));
  TestEqual(TEXT("ARTLOOK chips rollback"), UmTeamChip::ArtLookField(TEXT(" -S08IconLegacy")),
            FString(TEXT("chips=legacy(-S08IconLegacy)")));
  TestTrue(TEXT("ARTLOOK line carries chips="), S08ArtLook::TraceLine().Contains(TEXT(" chips=")));
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
