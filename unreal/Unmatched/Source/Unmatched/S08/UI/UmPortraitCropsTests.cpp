// VS-2 CP-09...CP-12 tests (docs/game-design/visual/06-tasks/cards-portraits.csv CP-09, CP-10, CP-11, CP-12):
//   Unmatched.S08.Hud.Portrait.Crops      the registry discs are the accepted CP-07 crops (variant B of
//                                         art/imagegen/portrait-crop-v1-codex/portrait-crops.json); the scale of every
//                                         show (32...160 su) at 720p / 1080p / 1080p 150 % / 1440p 150 % / 2160p 150 %:
//                                         <= 1.6 always (ВР-CP04), King Arthur <= 1.0 and the sidekicks <= 1.25 up to
//                                         1.5 px per su, Medusa capped at 2160p 150 % (capped=1); the baked hero-colour
//                                         ring of the sidekick avatars outside the circle (ВР-CP02).
//   Unmatched.S08.Hud.Portrait.Sidekicks  the harpy number = the seat order of the server (sidekicks[]), per owner (a
//                                         mirror match is 1-3 on each side), kept when one falls; the panel's mini
//                                         portraits: Merlin and the harpies in their circles, the badges 1-3 (card.navy
//                                         14 su + mark.keyline, the digit card.cream as text), fallen = saturation 0,
//                                         the PORTRAIT lines (id, n=1..3), -S08PortraitLegacy -> the digit, no badge.
// Headless: node tools/s08/run-ue-tests.cjs "Unmatched.S08.Hud.Portrait" <abs log>
#if WITH_AUTOMATION_TESTS

#include "UmCardMedia.h"
#include "UmHudPanels.h"
#include "UmHudPlayerPanel.h"
#include "UmHudTheme.h"
#include "UmPortrait.h"
#include "../S08BoardModel.h"
#include "../S08TurnPortraitWidget.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Image.h"
#include "Components/TextBlock.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Misc/AutomationTest.h"

namespace UmPortraitCropsTest {
struct FWorld {
  UWorld* World = nullptr;
  explicit FWorld(const TCHAR* Name) {
    World = UWorld::CreateWorld(EWorldType::Game, false, FName(Name));
    if (World) GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
  }
  ~FWorld() {
    if (!World) return;
    GEngine->DestroyWorldContext(World);
    World->DestroyWorld(false);
  }
};

TSharedPtr<FJsonValue> FighterJson(const TCHAR* Id, const TCHAR* Owner, const TCHAR* Name, bool bHero, int32 Hp,
                                   const TCHAR* Slug, bool bDefeated = false) {
  TSharedRef<FJsonObject> O = MakeShared<FJsonObject>();
  O->SetStringField(TEXT("id"), Id);
  O->SetStringField(TEXT("ownerId"), Owner);
  O->SetStringField(TEXT("name"), Name);
  O->SetStringField(TEXT("type"), bHero ? TEXT("HERO") : TEXT("MINION"));
  O->SetNumberField(TEXT("health"), Hp);
  O->SetNumberField(TEXT("maxHealth"), bHero ? 16 : 1);
  O->SetNumberField(TEXT("movement"), 3);
  O->SetBoolField(TEXT("isDefeated"), bDefeated);
  O->SetStringField(TEXT("attackType"), TEXT("melee"));
  O->SetStringField(TEXT("heroSlug"), Slug);
  TSharedRef<FJsonObject> Pos = MakeShared<FJsonObject>();
  Pos->SetNumberField(TEXT("x"), 1);
  Pos->SetNumberField(TEXT("y"), 1);
  O->SetObjectField(TEXT("position"), Pos);
  return MakeShared<FJsonValueObject>(O);
}

/** The rounded-box images of 14 su with a 1 su mark.keyline outline - the harpy badges. */
int32 CountBadges(const UUserWidget& W) {
  int32 N = 0;
  const FLinearColor Keyline = UUmHudTheme::Get().Color(TEXT("mark.keyline"));
  if (!W.WidgetTree) return 0;
  W.WidgetTree->ForEachWidget([&N, &Keyline](UWidget* X) {
    const UImage* I = Cast<UImage>(X);
    if (!I) return;
    const FSlateBrush& B = I->GetBrush();
    if (B.DrawAs == ESlateBrushDrawType::RoundedBox && FMath::IsNearlyEqual(B.ImageSize.X, UmPortrait::BadgeSu) &&
        FMath::IsNearlyEqual(B.OutlineSettings.Width, UmPortrait::BadgeKeylineSu) &&
        B.OutlineSettings.Color.GetSpecifiedColor().Equals(Keyline, 1e-3f)) {
      ++N;
    }
  });
  return N;
}
}  // namespace UmPortraitCropsTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmPortraitCropsTest, "Unmatched.S08.Hud.Portrait.Crops",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmPortraitCropsTest::RunTest(const FString&) {
  // the accepted CP-07 crops (portrait-crops.json, variant B, 165c3be7) - the registry discs (cx, cy, d)
  struct FCrop {
    const TCHAR* Key;
    FVector Disc;
    float SrcPx;
  };
  const FCrop Crops[] = {{TEXT("king-arthur"), FVector(0.49, 0.39, 0.54), 432.0f},
                         {TEXT("medusa"), FVector(0.44, 0.29, 0.50), 201.0f},
                         {TEXT("king-arthur/merlin"), FVector(0.50, 0.48, 0.69), 88.32f},
                         {TEXT("medusa/harpies"), FVector(0.50, 0.48, 0.69), 88.32f}};
  for (const FCrop& C : Crops) {
    const FUmCardMediaEntry* E = UmPortrait::Find(FName(C.Key));
    if (!TestNotNull(*FString::Printf(TEXT("registry %s"), C.Key), E)) continue;
    TestTrue(*FString::Printf(TEXT("%s: disc = CP-07 B (%.2f, %.2f, %.2f)"), C.Key, E->Disc.X, E->Disc.Y, E->Disc.Z),
             E->bHasDisc && E->Disc.Equals(C.Disc, 1e-6));
    TestTrue(*FString::Printf(TEXT("%s: source circle %.2f px"), C.Key, UmPortrait::SourceCirclePx(*E)),
             FMath::IsNearlyEqual(UmPortrait::SourceCirclePx(*E), C.SrcPx, 1e-3f));
    if (UmPortrait::IsSidekickKey(FName(C.Key))) {
      // ВР-CP02: the baked hero-colour ring (radius 50...64 of the 64 px half) stays outside the circle
      const double Far = (FMath::Max(FMath::Abs(E->Disc.X - 0.5), FMath::Abs(E->Disc.Y - 0.5)) + 0.5 * E->Disc.Z) * 128.0;
      TestTrue(*FString::Printf(TEXT("%s: circle reaches %.2f px < 50 px of the ring"), C.Key, Far), Far < 50.0);
    }
  }
  // the shows (su) of 02 §6.4 / 04 §1.4-§1.10 and the px per su of the frames: 720p, 1080p, 1080p 150 %, 1440p 150 %,
  // 2160p 150 %
  const float HeroShows[] = {32.0f, 64.0f, 80.0f, 120.0f, 160.0f};
  const float SidekickShows[] = {32.0f, 40.0f};
  const float Scales[] = {720.0f / 1080.0f, 1.0f, 1.5f, 2.0f, 3.0f};
  for (const FCrop& C : Crops) {
    const bool bSidekick = UmPortrait::IsSidekickKey(FName(C.Key));
    const bool bArthur = FCString::Strcmp(C.Key, TEXT("king-arthur")) == 0;
    const TArrayView<const float> Shows = bSidekick ? TArrayView<const float>(SidekickShows) : TArrayView<const float>(HeroShows);
    for (const float Show : Shows) {
      for (const float Pps : Scales) {
        const float Su = UmPortrait::CappedSu(Show, C.SrcPx, Pps);
        const float Scale = Su * Pps / C.SrcPx;
        TestTrue(*FString::Printf(TEXT("%s %.0f su at %.3f px/su: scale %.3f <= 1.6 (ВР-CP04)"), C.Key, Show, Pps, Scale),
                 Su <= Show + 1e-3f && Scale <= UmPortrait::CapScale + 1e-4f);
        if (Pps <= 1.5f + 1e-3f) {
          // the acceptance frames (720p / 1080p 100 % and 150 %): the card numbers hold without the cap
          const float Bound = bArthur ? 1.0f : bSidekick ? 1.25f : 1.6f;
          TestTrue(*FString::Printf(TEXT("%s %.0f su at %.3f px/su: %.3f <= %.2f, not capped"), C.Key, Show, Pps, Scale, Bound),
                   Scale <= Bound + 1e-4f && FMath::IsNearlyEqual(Su, Show));
        }
      }
    }
  }
  // 2160p 150 %: Medusa's 120 / 160 su are capped to 1.6 x 201 / 3 = 107.2 su (CP-11: capped=1 in the trace); King
  // Arthur's 160 su is 1.11x and the sidekicks' ROOM 40 su 1.36x - under the cap (ВР-VS2-64)
  TestTrue(TEXT("Medusa 160 su at 2160p 150 %: 107.2 su"), FMath::IsNearlyEqual(UmPortrait::CappedSu(160.0f, 201.0f, 3.0f), 107.2f, 1e-3f));
  TestTrue(TEXT("Medusa 120 su at 2160p 150 %: capped"), UmPortrait::CappedSu(120.0f, 201.0f, 3.0f) < 120.0f);
  TestEqual(TEXT("King Arthur 160 su at 2160p 150 %: no cap"), UmPortrait::CappedSu(160.0f, 432.0f, 3.0f), 160.0f);
  TestEqual(TEXT("harpies 40 su at 2160p 150 %: no cap"), UmPortrait::CappedSu(40.0f, 88.32f, 3.0f), 40.0f);
  const FString Capped = UmPortrait::TraceLine(TEXT("medusa"), TEXT("/Game/x"), 107.2f, 3.0f, 201.0f, TEXT("loading"),
                                               TEXT("own"), EUmPortraitState::Avatar, 160.0f);
  TestTrue(*FString::Printf(TEXT("trace capped=1 scale=1.600 (%s)"), *Capped),
           Capped.Contains(TEXT("capped=1")) && Capped.Contains(TEXT("scale=1.600")));
  const FString Plain = UmPortrait::TraceLine(TEXT("king-arthur"), TEXT("/Game/x"), 160.0f, 1.0f, 432.0f, TEXT("loading"),
                                              TEXT("own"), EUmPortraitState::Avatar, 160.0f);
  TestTrue(*FString::Printf(TEXT("trace capped=0, no n (%s)"), *Plain), Plain.Contains(TEXT("capped=0")) && !Plain.Contains(TEXT(" n=")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmPortraitSidekicksTest, "Unmatched.S08.Hud.Portrait.Sidekicks",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmPortraitSidekicksTest::RunTest(const FString&) {
  using namespace UmPortraitCropsTest;
  // ---- the number: the server's seat order (sidekicks[]), per owner; a defeated harpy stays in the array ----
  TArray<TSharedPtr<FJsonValue>> Arr = {
      FighterJson(TEXT("f-0-hero"), TEXT("p0"), TEXT("Medusa"), true, 16, TEXT("medusa")),
      FighterJson(TEXT("f-0-sk0"), TEXT("p0"), TEXT("Harpies"), false, 1, TEXT("medusa")),
      FighterJson(TEXT("f-0-sk1"), TEXT("p0"), TEXT("Harpies"), false, 0, TEXT("medusa"), true),
      FighterJson(TEXT("f-0-sk2"), TEXT("p0"), TEXT("Harpies"), false, 1, TEXT("medusa")),
      FighterJson(TEXT("f-1-hero"), TEXT("p1"), TEXT("Medusa"), true, 16, TEXT("medusa")),
      FighterJson(TEXT("f-1-sk0"), TEXT("p1"), TEXT("Harpies"), false, 1, TEXT("medusa")),
      FighterJson(TEXT("f-1-sk1"), TEXT("p1"), TEXT("Harpies"), false, 1, TEXT("medusa")),
      FighterJson(TEXT("f-1-sk2"), TEXT("p1"), TEXT("Harpies"), false, 1, TEXT("medusa")),
  };
  TArray<FS08BoardFighter> Fighters;
  TestTrue(TEXT("decode"), FS08BoardModel::DecodeFighters(MakeShared<FJsonValueArray>(Arr), Fighters));
  TMap<FString, FString> Label;
  for (const FS08BoardFighter& F : Fighters) Label.Add(F.Id, F.Label);
  for (const TCHAR* Seat : {TEXT("0"), TEXT("1")}) {
    for (int32 I = 0; I < 3; ++I) {
      const FString Id = FString::Printf(TEXT("f-%s-sk%d"), Seat, I);
      TestEqual(*FString::Printf(TEXT("mirror match: %s is Harpies %d"), *Id, I + 1), Label.FindRef(Id),
                FString::Printf(TEXT("Harpies %d"), I + 1));
    }
  }
  TestEqual(TEXT("a hero keeps its name"), Label.FindRef(TEXT("f-1-hero")), FString(TEXT("Medusa")));
  // the panel reads the same label (the tag and the stand too): numbers 1..3, the defeated one is 2
  UmHudPanel::FSideMemory Memory;
  auto Fallen = [&Fighters](const FString& Id) {
    const FS08BoardFighter* F = Fighters.FindByPredicate([&Id](const FS08BoardFighter& X) { return X.Id == Id; });
    return F && (F->bDefeated || F->Health <= 0);
  };
  FUmPlayerPanelModel M = UmHudPanel::Gather(EUmPanelSide::Own, TEXT("p0"), TEXT("Medusa"), Fighters, true, false, false, Fallen, Memory);
  if (!TestEqual(TEXT("three harpies"), M.Sidekicks.Num(), 3)) return false;
  for (int32 I = 0; I < 3; ++I) {
    TestEqual(*FString::Printf(TEXT("panel number %d = label digit"), I + 1), M.Sidekicks[I].Number,
              UmHudPanel::SidekickNumber(Label.FindRef(M.Sidekicks[I].Id)));
    TestEqual(TEXT("seat order"), M.Sidekicks[I].Id, FString::Printf(TEXT("f-0-sk%d"), I));
  }
  TestTrue(TEXT("harpy 2 fallen"), M.Sidekicks[1].bFallen && !M.Sidekicks[0].bFallen && !M.Sidekicks[2].bFallen);

  // ---- the panel's mini portraits ----
  FWorld W(TEXT("UmPortraitSidekicks"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  UUmHudPlayerPanel* P = CreateWidget<UUmHudPlayerPanel>(W.World, UUmHudPlayerPanel::StaticClass());
  if (!TestNotNull(TEXT("panel"), P)) return false;
  P->Setup(EUmPanelSide::Own, FS08TurnHudLook(), FLinearColor::Green);
  P->Portrait->SetPortraitLegacyForTest(0);
  M.bClassS = false;
  M.PxPerSu = 1.5f;
  P->ApplyModel(M);
  const TArray<FUmPortraitShown>& Minis = P->GetMiniPortraits();
  if (!TestEqual(TEXT("three mini portraits"), Minis.Num(), 3)) return false;
  for (int32 I = 0; I < 3; ++I) {
    TestTrue(*FString::Printf(TEXT("harpy %d: the avatar (%s)"), I + 1, *Minis[I].Tex),
             Minis[I].IsAvatar() && Minis[I].Tex.Contains(TEXT("T_Portrait_medusa_harpies")));
    TestEqual(TEXT("key medusa/harpies"), Minis[I].Key, FName(TEXT("medusa/harpies")));
    TestEqual(TEXT("number"), Minis[I].Number, I + 1);
    TestEqual(TEXT("32 su"), Minis[I].Su, UmHudPanel::SidekickSu);
  }
  TestTrue(TEXT("harpy 2 fallen: saturation 0"), Minis[1].State == EUmPortraitState::Fallen && Minis[0].State == EUmPortraitState::Avatar);
  TestEqual(TEXT("three badges with the keyline"), CountBadges(*P), 3);
  TArray<FString> Lines;
  P->CollectPortraitLines(Lines);
  if (TestEqual(TEXT("three PORTRAIT lines"), Lines.Num(), 3)) {
    for (int32 I = 0; I < 3; ++I) {
      TestTrue(*FString::Printf(TEXT("line %d (%s)"), I + 1, *Lines[I]),
               Lines[I].StartsWith(TEXT("PORTRAIT id=medusa/harpies tex=/Game/S08/UI/Portraits/")) &&
                   Lines[I].Contains(TEXT("show=panel side=own")) && Lines[I].EndsWith(FString::Printf(TEXT(" n=%d"), I + 1)) &&
                   Lines[I].Contains(TEXT("scale=0.543")));  // 32 su x 1.5 / 88.32 px
    }
  }
  // class S: no mini portraits, no lines (the tooltip)
  M.bClassS = true;
  P->ApplyModel(M);
  Lines.Reset();
  P->CollectPortraitLines(Lines);
  TestEqual(TEXT("class S: no PORTRAIT lines"), Lines.Num(), 0);
  // -S08PortraitLegacy: the fallback circle is the digit, no badge on top of it
  P->Portrait->SetPortraitLegacyForTest(1);
  M.bClassS = false;
  M.PxPerSu = 1.0f;
  P->ApplyModel(M);
  TestTrue(TEXT("legacy: tex=legacy"), P->GetMiniPortraits().Num() == 3 && P->GetMiniPortraits()[0].Tex == TEXT("legacy"));
  TestEqual(TEXT("legacy: no badge"), CountBadges(*P), 0);
  int32 Digits = 0;
  P->WidgetTree->ForEachWidget([&Digits](UWidget* X) {
    if (const UTextBlock* T = Cast<UTextBlock>(X)) Digits += T->GetText().ToString() == TEXT("2") ? 1 : 0;
  });
  TestTrue(TEXT("legacy: the digit 2 in the circle"), Digits >= 1);

  // ---- Merlin: one named sidekick, no number ----
  TArray<FS08BoardFighter> Arthur;
  {
    TArray<TSharedPtr<FJsonValue>> A = {FighterJson(TEXT("f-0-hero"), TEXT("p0"), TEXT("King Arthur"), true, 18, TEXT("king-arthur")),
                                        FighterJson(TEXT("f-0-sk0"), TEXT("p0"), TEXT("Merlin"), false, 7, TEXT("king-arthur"))};
    FS08BoardModel::DecodeFighters(MakeShared<FJsonValueArray>(A), Arthur);
  }
  UmHudPanel::FSideMemory ArthurMemory;
  FUmPlayerPanelModel K = UmHudPanel::Gather(EUmPanelSide::Opp, TEXT("p0"), FString(), Arthur, false, false, false,
                                             [](const FString&) { return false; }, ArthurMemory);
  UUmHudPlayerPanel* Q = CreateWidget<UUmHudPlayerPanel>(W.World, UUmHudPlayerPanel::StaticClass());
  if (!TestNotNull(TEXT("opp panel"), Q)) return false;
  Q->Setup(EUmPanelSide::Opp, FS08TurnHudLook(), FLinearColor::Red);
  Q->Portrait->SetPortraitLegacyForTest(0);
  Q->ApplyModel(K);
  Lines.Reset();
  Q->CollectPortraitLines(Lines);
  TestTrue(*FString::Printf(TEXT("Merlin line (%s)"), Lines.Num() ? *Lines[0] : TEXT("-")),
           Lines.Num() == 1 && Lines[0].StartsWith(TEXT("PORTRAIT id=king-arthur/merlin tex=/Game/S08/UI/Portraits/T_Portrait_king_arthur_merlin")) &&
               Lines[0].Contains(TEXT("side=opp")) && !Lines[0].Contains(TEXT(" n=")) && Lines[0].Contains(TEXT("scale=0.362")));
  TestEqual(TEXT("Merlin: no badge"), CountBadges(*Q), 0);
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
