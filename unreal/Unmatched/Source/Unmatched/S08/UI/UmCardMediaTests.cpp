// VS-1 CP-02 automation tests of UI/UmCardMedia.h and the CP-02 rollback flags of S08ArtLook.h:
//   Registry  the shipped Config/Cards/S08CardMedia.json: 27 card keys x RU/EN, 2 backs, 4 portraits, uv = src / pad,
//             power-of-two pads, ВР-CP07 object paths, lookups by key; a broken document is refused as a whole.
//   Flags     -S08PortraitLegacy / -S08CardArtLegacy parsed from the real command line and traced in ARTLOOK.
//   Assets    the imported textures (gitignored Content, ENV-U3; a warning when the import script has not run here):
//             PAD_TO_POWER_OF_TWO, padding #061623 alpha 0, simple-average mips, trilinear, TEXTUREGROUP_UI, sRGB, BC7,
//             never stream, clamp; built size = registry pad. With a renderer (no -nullrhi, e.g. -RenderOffScreen) also
//             the real platform data: GetSizeX/Y = pad and GetNumMips() > 1.
//   UnrealEditor-Cmd.exe Unmatched.uproject
//     -ExecCmds="Automation RunTests Unmatched.S08.CardMedia; Quit" -unattended -nosplash -nullrhi
#if WITH_AUTOMATION_TESTS

#include "UmCardMedia.h"

#include "../S08ArtLook.h"
#include "../S08HudTokens.generated.h"
#include "Engine/Texture2D.h"
#include "Misc/App.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#if WITH_EDITOR
#include "TextureCompiler.h"
#endif

namespace UmCardMediaTest {
const TCHAR* const MvpCards[] = {
    TEXT("medusa:a-momentary-glance"), TEXT("medusa:clutching-claws"), TEXT("medusa:dash"), TEXT("medusa:feint"),
    TEXT("medusa:gaze-of-stone"), TEXT("medusa:hiss-and-slither"), TEXT("medusa:regroup"), TEXT("medusa:second-shot"),
    TEXT("medusa:snipe"), TEXT("medusa:the-hounds-of-mighty-zeus"), TEXT("medusa:winged-frenzy"),
    TEXT("king-arthur:aid-the-chosen-one"), TEXT("king-arthur:bewilderment"), TEXT("king-arthur:command-the-storms"),
    TEXT("king-arthur:divine-intervention"), TEXT("king-arthur:excalibur"), TEXT("king-arthur:feint"),
    TEXT("king-arthur:momentous-shift"), TEXT("king-arthur:noble-sacrifice"), TEXT("king-arthur:prophecy"),
    TEXT("king-arthur:regroup"), TEXT("king-arthur:restless-spirits"), TEXT("king-arthur:skirmish"),
    TEXT("king-arthur:swift-strike"), TEXT("king-arthur:the-aid-of-morgana"), TEXT("king-arthur:the-holy-grail"),
    TEXT("king-arthur:the-lady-of-the-lake")};

/** The run's command line plus Extra while in scope. */
struct FCommandLineScope {
  FString Saved;
  explicit FCommandLineScope(const TCHAR* Extra) : Saved(FCommandLine::Get()) {
    FCommandLine::Set(*(Saved + TEXT(" ") + Extra));
  }
  ~FCommandLineScope() { FCommandLine::Set(*Saved); }
};
}  // namespace UmCardMediaTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmCardMediaRegistryTest,
    "Unmatched.S08.CardMedia.Registry shipped key registry: 27 cards x RU/EN, 2 backs, 4 portraits, uv = src / pad",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmCardMediaRegistryTest::RunTest(const FString&) {
  using namespace UmCardMediaTest;
  FString Text;
  if (!TestTrue(TEXT("registry file readable"), FFileHelper::LoadFileToString(Text, *UmCardMedia::RegistryPath()))) {
    return false;
  }
  TArray<FUmCardMediaEntry> Entries;
  TArray<FString> Errors;
  if (!TestTrue(FString::Printf(TEXT("registry parses (%s)"), *FString::Join(Errors, TEXT("; "))),
                UmCardMedia::Parse(Text, Entries, Errors))) {
    return false;
  }
  int32 Cards = 0, Backs = 0, Portraits = 0;
  for (const FUmCardMediaEntry& E : Entries) {
    Cards += E.Kind == TEXT("card") ? 1 : 0;
    Backs += E.Kind == TEXT("back") ? 1 : 0;
    Portraits += E.Kind == TEXT("portrait") ? 1 : 0;
    TestTrue(E.Key + TEXT(": uv = src / pad"),
             FMath::IsNearlyEqual(E.Uv.X, double(E.Src.X) / E.Pad.X, 1e-5) &&
                 FMath::IsNearlyEqual(E.Uv.Y, double(E.Src.Y) / E.Pad.Y, 1e-5));
    TestTrue(E.Key + TEXT(": pad is the next power of two"),
             E.Pad.X == int32(FMath::RoundUpToPowerOfTwo(uint32(E.Src.X))) && E.Pad.Y == int32(FMath::RoundUpToPowerOfTwo(uint32(E.Src.Y))));
    TestEqual(E.Key + TEXT(": sha256 hex"), E.Sha256.Len(), 64);
  }
  TestEqual(TEXT("54 card entries (27 keys x RU / EN)"), Cards, 54);
  TestEqual(TEXT("2 backs"), Backs, 2);
  TestEqual(TEXT("4 portraits"), Portraits, 4);

  UmCardMedia::ResetForTest();
  for (const TCHAR* Key : MvpCards) {
    FString Hero, Card;
    FString(Key).Split(TEXT(":"), &Hero, &Card);
    const FUmCardMediaEntry* Ru = UmCardMedia::FindCard(Hero, Card, TEXT("ru"));
    const FUmCardMediaEntry* En = UmCardMedia::FindCard(Hero, Card, TEXT("en"));
    if (!TestTrue(FString(Key) + TEXT(": RU and EN entries"), Ru && En)) continue;
    TestTrue(FString(Key) + TEXT(": RU scan 287x398"), Ru->Src == FIntPoint(287, 398));
    TestTrue(FString(Key) + TEXT(": RU pad 512x512"), Ru->Pad == FIntPoint(512, 512));
    TestTrue(FString(Key) + TEXT(": EN scan 250x349"), En->Src == FIntPoint(250, 349));
    TestTrue(FString(Key) + TEXT(": EN pad 256x512"), En->Pad == FIntPoint(256, 512));
    const FString Name = UmCardMedia::CardAssetName(Hero, Card, TEXT("ru"));
    TestEqual(FString(Key) + TEXT(": ВР-CP07 path"), Ru->ObjectPath,
              FString::Printf(TEXT("/Game/S08/UI/Cards/%s/%s.%s"), *Hero.Replace(TEXT("-"), TEXT("_")), *Name, *Name));
  }
  const FUmCardMediaEntry* BackA = UmCardMedia::FindBack(TEXT("king-arthur"));
  const FUmCardMediaEntry* BackM = UmCardMedia::FindBack(TEXT("medusa"));
  if (TestTrue(TEXT("both backs"), BackA && BackM)) {
    TestTrue(TEXT("back 768x1051 -> 1024x2048"), BackA->Pad == FIntPoint(1024, 2048));
    TestEqual(TEXT("back path"), BackM->ObjectPath, FString(TEXT("/Game/S08/UI/CardBacks/T_CardBack_medusa.T_CardBack_medusa")));
  }
  const FUmCardMediaEntry* Arthur = UmCardMedia::FindPortrait(TEXT("king-arthur"));
  const FUmCardMediaEntry* Medusa = UmCardMedia::FindPortrait(TEXT("medusa"));
  const FUmCardMediaEntry* Merlin = UmCardMedia::FindPortrait(TEXT("king-arthur"), TEXT("merlin"));
  const FUmCardMediaEntry* Harpies = UmCardMedia::FindPortrait(TEXT("medusa"), TEXT("harpies"));
  if (TestTrue(TEXT("four portraits by key"), Arthur && Medusa && Merlin && Harpies)) {
    TestTrue(TEXT("King Arthur 800 -> 1024"), Arthur->Pad == FIntPoint(1024, 1024));
    TestTrue(TEXT("Medusa 402 -> 512"), Medusa->Pad == FIntPoint(512, 512));
    TestTrue(TEXT("Merlin 128 (no pad)"), Merlin->Pad == FIntPoint(128, 128));
    TestTrue(TEXT("discs (ВР-CP01 start or CP-07)"), Arthur->bHasDisc && Medusa->bHasDisc && Merlin->bHasDisc && Harpies->bHasDisc);
    TestEqual(TEXT("Harpies portrait path"), Harpies->ObjectPath,
              FString(TEXT("/Game/S08/UI/Portraits/T_Portrait_medusa_harpies.T_Portrait_medusa_harpies")));
  }
  TestNull(TEXT("unknown key -> none (INT-018 fallback)"), UmCardMedia::FindCard(TEXT("medusa"), TEXT("nope"), TEXT("ru")));

  // A broken document is refused as a whole (never half-loaded).
  TArray<FUmCardMediaEntry> Bad;
  TArray<FString> BadErrors;
  TestFalse(TEXT("wrong schema refused"), UmCardMedia::Parse(TEXT("{\"schema\":\"x\",\"entries\":[]}"), Bad, BadErrors));
  BadErrors.Reset();
  const FString BadUv = FString(TEXT("{\"schema\":\"")) + UmCardMedia::Schema +
                        TEXT("\",\"entries\":[{\"key\":\"medusa:dash\",\"kind\":\"card\",\"lang\":\"ru\",\"object\":"
                             "\"/Game/S08/UI/Cards/medusa/T.T\",\"src\":[287,398],\"pad\":[512,512],\"uv\":[0.5,0.5],"
                             "\"sha256\":\"x\"}]}");
  TestFalse(TEXT("uv != src / pad refused"), UmCardMedia::Parse(BadUv, Bad, BadErrors));
  TestEqual(TEXT("nothing half-loaded"), Bad.Num(), 0);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmCardMediaFlagsTest,
    "Unmatched.S08.CardMedia.Flags S08PortraitLegacy and S08CardArtLegacy parsed and traced in ARTLOOK",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmCardMediaFlagsTest::RunTest(const FString&) {
  using namespace UmCardMediaTest;
  TestTrue(TEXT("rule: no flag -> media"), S08ArtLook::DecideCardMedia(false));
  TestFalse(TEXT("rule: flag -> legacy"), S08ArtLook::DecideCardMedia(true));
  TestEqual(TEXT("field default"), S08ArtLook::CardMediaField(TEXT("")), FString(TEXT("portraits=avatar cards=art")));
  TestEqual(TEXT("field portraits rollback"), S08ArtLook::CardMediaField(TEXT("-S08PortraitLegacy")),
            FString(TEXT("portraits=legacy(-S08PortraitLegacy) cards=art")));
  TestEqual(TEXT("field both rollbacks"), S08ArtLook::CardMediaField(TEXT("-S08CardArtLegacy -S08PortraitLegacy")),
            FString(TEXT("portraits=legacy(-S08PortraitLegacy) cards=legacy(-S08CardArtLegacy)")));
  const bool bBaseLegacy = FParse::Param(FCommandLine::Get(), S08ArtLook::PortraitLegacyFlagName) ||
                           FParse::Param(FCommandLine::Get(), S08ArtLook::CardArtLegacyFlagName);
  if (bBaseLegacy) {
    AddWarning(TEXT("the run was started with a CP-02 rollback flag: the no-flag default is not checked"));
  } else {
    TestTrue(TEXT("default: avatars"), S08ArtLook::PortraitAvatars());
    TestTrue(TEXT("default: card art"), S08ArtLook::CardArt());
    TestTrue(TEXT("ARTLOOK carries portraits= and cards="),
             S08ArtLook::TraceLine().Contains(TEXT(" portraits=avatar cards=art")));
  }
  {
    FCommandLineScope Scope(TEXT("-S08PortraitLegacy -S08CardArtLegacy"));
    TestFalse(TEXT("-S08PortraitLegacy: no avatars"), S08ArtLook::PortraitAvatars());
    TestFalse(TEXT("-S08CardArtLegacy: no card art"), S08ArtLook::CardArt());
    TestTrue(TEXT("ARTLOOK traces both rollbacks"),
             S08ArtLook::TraceLine().Contains(TEXT(" portraits=legacy(-S08PortraitLegacy) cards=legacy(-S08CardArtLegacy)")));
  }
  TestTrue(TEXT("probe flag parsed"), UmCardMedia::ProbeRequested(TEXT("-ArtPreviewCardMediaProbe")));
  TestFalse(TEXT("probe off by default"), UmCardMedia::ProbeRequested(TEXT("")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmCardMediaAssetsTest,
    "Unmatched.S08.CardMedia.Assets imported textures match the CP-02 import contract (out of git)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmCardMediaAssetsTest::RunTest(const FString&) {
  UmCardMedia::ResetForTest();
  const TArray<FUmCardMediaEntry>& R = UmCardMedia::Registry();
  if (!TestTrue(TEXT("registry loaded"), R.Num() > 0)) return false;
  int32 Checked = 0, Missing = 0, PlatformChecked = 0;
  for (const FUmCardMediaEntry& E : R) {
    const FString Id = E.Key + (E.Lang.IsEmpty() ? FString() : TEXT(".") + E.Lang);
    if (!FPackageName::DoesPackageExist(FPackageName::ObjectPathToPackageName(E.ObjectPath))) {
      ++Missing;
      continue;
    }
    UTexture2D* T = LoadObject<UTexture2D>(nullptr, *E.ObjectPath);
    if (!TestNotNull(Id + TEXT(": loads as Texture2D"), T)) continue;
    ++Checked;
#if WITH_EDITOR
    FTextureCompilingManager::Get().FinishCompilation({static_cast<UTexture*>(T)});
#endif
#if WITH_EDITORONLY_DATA
    // panel.bg #061623 with alpha 0, from the token header (G-TOKENS: no colour literal in S08/UI)
    const FColor PadColor(S08HudTokens::Color_PanelBg.R, S08HudTokens::Color_PanelBg.G, S08HudTokens::Color_PanelBg.B, 0);
    TestTrue(Id + TEXT(": PAD_TO_POWER_OF_TWO, padding #061623 a0"),
             T->PowerOfTwoMode == ETexturePowerOfTwoSetting::PadToPowerOfTwo && T->PaddingColor == PadColor);
    TestTrue(Id + TEXT(": simple-average mips"), T->MipGenSettings == TMGS_SimpleAverage);
#endif
    TestTrue(Id + TEXT(": trilinear, UI group, sRGB, BC7, never stream"),
             T->Filter == TF_Trilinear && T->LODGroup == TEXTUREGROUP_UI && T->SRGB &&
                 T->CompressionSettings == TC_BC7 && T->NeverStream);
    TestTrue(Id + TEXT(": clamp"), T->AddressX == TA_Clamp && T->AddressY == TA_Clamp);
    if (FApp::CanEverRender()) {
      // A rendering run caches the platform data on load: the real built mip 0 and mip chain.
      TestTrue(Id + FString::Printf(TEXT(": platform size %dx%d = registry pad %s"), T->GetSizeX(), T->GetSizeY(),
                                    *E.Pad.ToString()),
               FIntPoint(T->GetSizeX(), T->GetSizeY()) == E.Pad);
      TestTrue(Id + FString::Printf(TEXT(": mip chain %d (> 1)"), T->GetNumMips()), T->GetNumMips() > 1);
      ++PlatformChecked;
    } else {
      // -nullrhi (the run-ue-tests.cjs default) never builds platform data (UTexture::CachePlatformData needs
      // FApp::CanEverRender): the size the build settings give (UTexture::Blueprint_GetBuiltTextureSize, called
      // through reflection - UTexture is MinimalAPI) must be the pad; the mip chain follows from TMGS_SimpleAverage.
      struct {
        FVector3f ReturnValue = FVector3f::ZeroVector;
      } Params;
      if (UFunction* Fn = T->FindFunction(TEXT("Blueprint_GetBuiltTextureSize"))) T->ProcessEvent(Fn, &Params);
      const FIntPoint Built(FMath::RoundToInt(Params.ReturnValue.X), FMath::RoundToInt(Params.ReturnValue.Y));
      TestTrue(Id + FString::Printf(TEXT(": built size %s = registry pad %s"), *Built.ToString(), *E.Pad.ToString()),
               Built == E.Pad);
    }
  }
  if (Missing) {
    AddWarning(FString::Printf(TEXT("%d of %d registry textures not imported in this checkout - run "
                                    "tools/art/cards/ue_import_card_media.py (Content is gitignored, ENV-U3)"),
                               Missing, R.Num()));
  }
  AddInfo(FString::Printf(TEXT("checked %d imported textures (%d with built platform data: size and mip count)"), Checked,
                          PlatformChecked));
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
