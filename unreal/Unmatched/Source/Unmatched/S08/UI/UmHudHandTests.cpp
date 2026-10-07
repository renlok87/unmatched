// VS-3 automation tests of HAND (docs/game-design/visual/06-tasks/hud.csv HB-24, HB-25; 04-hud-spec.md §2.6, §1.6, §7.4):
//   Unmatched.S08.Hud.Hand.Tree      HB-24  BuildDefaultTree, every BindWidget, the hand only hears the pointer, the WBP
//                                           WBP_UI_HUD_HAND is a child of the base, the GAME slot takes it.
//   Unmatched.S08.Hud.Hand.Layout    HB-24  3 / 5 / 7 / 9 / 10 cards x L (1920 x 1080, 1707 x 960) and S (1280 x 720,
//                                           1138 x 640) on both boards' FIELD: the step, the corridor, the visible height,
//                                           nothing at rest crosses FIELD; HB-22 numbers (5 cards Marmoreal 1080p: x 567,
//                                           top 907, caption 885; hover 529.5 / 744 / 225 x 312; 720p 150 % 9 cards 63.72 su
//                                           - ВР-VS2-HB22-09); the widget places its cards there; lowered = 48 su.
//   Unmatched.S08.Hud.Hand.Input     HB-24  two copies = two widgets (UI-INP-007), the press id hand.<instance>, the
//                                           keys 1-9 by position, a reorder keeps the widgets, the strips of the hover,
//                                           the raised preview keeps the hover, the wheel, the double click, the right
//                                           button; the gather of an attack step (banner why, type without a why).
//   Unmatched.S08.Hud.Hand.Discard   HB-25  the limit discard: every card a candidate, n of 9 marked 16 su down with
//                                           card-drop, a second click unmarks, SHOT state=discard.
//   Unmatched.S08.Hud.Hand.Boost     HB-25  the maneuver boost into SLOT face down with "+N" and the BOOST ribbon; King
//                                           Arthur's attack boost beside COMBAT-L with the chip right-aligned; the rest
//                                           why.boost.no.value; class S rects; the 32 su chip under 1 px per su.
//   Unmatched.S08.Hud.Hand.Budget    HB-24  0 new widgets after the warm-up (draws and plays of 30 snapshots); ApplyModel
//                                           of 9 cards <= 0.15 ms p95 (the budget of the card).
//   Unmatched.S09.HudPress.UmgHand   HB-24  synthetic clicks on the hand's cards n 24, holds 0 and 3 frames with a snapshot
//                                           applied in between: 0 lost; an unplayable card with a why is refused, one
//                                           without a why goes on to the owner.
// Headless: node tools/s08/run-ue-tests.cjs "Unmatched.S08.Hud.Hand+Unmatched.S09.HudPress.UmgHand" <abs log>
#if WITH_AUTOMATION_TESTS

#include "../../S09/S09ManeuverUi.h"
#include "../S08BoardModel.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/SizeBox.h"
#include "Components/TextBlock.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "HAL/PlatformTime.h"
#include "InputCoreTypes.h"
#include "Layout/Geometry.h"
#include "Misc/AutomationTest.h"
#include "Misc/PackageName.h"
#include "UmCardGallery.h"
#include "UmGameHud.h"
#include "UmHudHand.h"
#include "UmHudLayout.h"
#include "UmText.h"

// Named namespace (not anonymous): unity builds merge test files.
namespace UmHandTest {
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

bool Near(double A, double B, double Tol = 0.01) { return FMath::Abs(A - B) <= Tol; }

/** The live K1 FIELD at 1080p 100 % (VS-2 traces), scaled with the window like the K1 camera. */
FBox2D Field(bool bSarpedon, const FVector2D& CanvasSu, float PxPerSu) {
  const FBox2D At1080 = bSarpedon ? FBox2D(FVector2D(466.0, 258.0), FVector2D(1461.0, 857.0))
                                  : FBox2D(FVector2D(377.0, 257.0), FVector2D(1542.0, 866.0));
  const double K = CanvasSu.X * PxPerSu / 1920.0;
  const FVector2D Off(0.0, 0.5 * (CanvasSu.Y * PxPerSu - 1080.0 * K));
  return FBox2D((At1080.Min * K + Off) / PxPerSu, (At1080.Max * K + Off) / PxPerSu);
}

struct FHandCanvas {
  const TCHAR* Name;
  FVector2D Su;
  float Px;
};
const FHandCanvas Canvases[] = {{TEXT("1080p100"), FVector2D(1920.0, 1080.0), 1.0f},
                            {TEXT("720p100"), FVector2D(1280.0 / 0.75, 960.0), 0.75f},
                            {TEXT("1080p150"), FVector2D(1280.0, 720.0), 1.5f},
                            {TEXT("720p150"), FVector2D(1280.0 / 1.125, 640.0), 1.125f}};

FUmHandFrame Frame(const FHandCanvas& C, bool bSarpedon) {
  const FBox2D F = Field(bSarpedon, C.Su, C.Px);
  return FUmHandFrame::FromLayout(FUmHudLayout::Compute(C.Su, C.Px, &F), 1.0f);
}

FS09CardView Card(const TCHAR* Hero, const TCHAR* Name, int32 Copy = 0) {
  for (const FS09CardView& C : UmCardGallery::LoadDeck(Hero)) {
    if (C.Name == Name) {
      FS09CardView Out = C;
      Out.InstanceId = FString::Printf(TEXT("card::%s-%d"), *UmCardWidget::Slug(Name), Copy);
      return Out;
    }
  }
  FS09CardView None;
  None.Name = Name;
  None.InstanceId = FString::Printf(TEXT("card::%s-%d"), *UmCardWidget::Slug(Name), Copy);
  return None;
}

/** The HB-22 test hand (9 different Medusa cards) or its first N. */
TArray<FS09CardView> TestHand(int32 N = 9) {
  const TCHAR* Names[] = {TEXT("Gaze of Stone"), TEXT("Snipe"), TEXT("Clutching Claws"), TEXT("Dash"), TEXT("Hiss and Slither"),
                          TEXT("Regroup"), TEXT("Second Shot"), TEXT("A Momentary Glance"), TEXT("Winged Frenzy")};
  TArray<FS09CardView> Out;
  for (int32 I = 0; I < N; ++I) Out.Add(Card(TEXT("medusa"), Names[I % 9], I / 9));
  return Out;
}

FUmHandModel Model(const TArray<FS09CardView>& Cards, const TCHAR* Hero = TEXT("medusa")) {
  FUmHandModel M;
  M.HeroSlug = Hero;
  for (const FS09CardView& C : Cards) {
    FUmHandCardModel H;
    H.Card = C;
    M.Cards.Add(H);
  }
  return M;
}

UUmHudHand* Make(UWorld* World, const FUmHandFrame& F, double ClockMs = 0.0) {
  UUmHudHand* H = CreateWidget<UUmHudHand>(World, UUmHudHand::StaticClass());
  if (!H) return nullptr;
  H->SetClockOverrideMs(ClockMs);
  H->SetReducedForTest(0);
  H->SetLegacyForTest(0);
  H->SetSyncLoad(true);
  H->SetFrame(F);
  return H;
}

void At(UUmHudHand* H, double Ms) {
  H->SetClockOverrideMs(Ms);
  H->Step();
}

FPointerEvent Left(const FVector2D& P, bool bDown) {
  TSet<FKey> Pressed;
  if (bDown) Pressed.Add(EKeys::LeftMouseButton);
  return FPointerEvent(0, P, P, Pressed, EKeys::LeftMouseButton, 0.0f, FModifierKeysState());
}

FPointerEvent Right(const FVector2D& P, bool bDown) {
  TSet<FKey> Pressed;
  if (bDown) Pressed.Add(EKeys::RightMouseButton);
  return FPointerEvent(0, P, P, Pressed, EKeys::RightMouseButton, 0.0f, FModifierKeysState());
}

FVector2D SlotPos(UUmCardWidget* W) {
  const UCanvasPanelSlot* S = W ? Cast<UCanvasPanelSlot>(W->Slot) : nullptr;
  return S ? S->GetPosition() : FVector2D(-1.0, -1.0);
}
}  // namespace UmHandTest

// ------------------------------------------------------------------------------------------------ HB-24

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHandTreeTest,
    "Unmatched.S08.Hud.Hand.Tree UUmHudHand default tree, every BindWidget, the GAME slot, WBP_UI_HUD_HAND",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHandTreeTest::RunTest(const FString&) {
  using namespace UmHandTest;
  FWorld W(TEXT("UmHandTree"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  UUmHudHand* H = Make(W.World, Frame(Canvases[0], false));
  if (!TestNotNull(TEXT("hand"), H)) return false;
  FString Missing;
  TestTrue(TEXT("code default tree"), H->UsesCodeDefaultTree());
  TestTrue(FString::Printf(TEXT("every BindWidget (missing: %s)"), *Missing), H->HasAllParts(&Missing));
  TestNotNull(TEXT("CountPlate"), H->CountPlate.Get());
  TestNotNull(TEXT("WhyPlate"), H->WhyPlate.Get());
  TestNotNull(TEXT("BoostRibbon"), H->BoostRibbon.Get());
  TestEqual(TEXT("the hand only hears the pointer"), H->GetVisibility(), ESlateVisibility::SelfHitTestInvisible);
  TestEqual(TEXT("the row too"), H->Row->GetVisibility(), ESlateVisibility::SelfHitTestInvisible);
  TestEqual(TEXT("the caption never takes it"), H->CountPlate->GetVisibility(), ESlateVisibility::HitTestInvisible);
  H->ApplyModel(Model(TestHand(5)));
  TestEqual(TEXT("pool warmed to 10"), H->PoolSize(), UmHudHand::PoolWarm);
  UUmCardWidget* C = H->FindCard(TEXT("card::gaze-of-stone-0"));
  TestNotNull(TEXT("a card widget per instance"), C);
  if (C) {
    TestEqual(TEXT("the card takes the pointer"), C->GetVisibility(), ESlateVisibility::Visible);
    TestEqual(TEXT("its drawn card too (the raised preview)"), C->Card->GetVisibility(), ESlateVisibility::Visible);
  }
  // the GAME screen slot takes the block
  UUmGameHud* Game = CreateWidget<UUmGameHud>(W.World, UUmGameHud::StaticClass());
  TestTrue(TEXT("GAME slot Hand takes the hand"), Game && Game->SetBlock(EUmGameSlot::Hand, H));
  // the generated WBP (tools/s08/hud_contract/ue_author_um_hud.py)
  if (FPackageName::DoesPackageExist(UUmHudHand::WidgetBlueprintPath)) {
    UClass* Wbp = UUmHudHand::WidgetClass();
    TestTrue(TEXT("WBP_UI_HUD_HAND is a child of UUmHudHand"), Wbp && Wbp != UUmHudHand::StaticClass() && Wbp->IsChildOf(UUmHudHand::StaticClass()));
    UUmHudHand* FromWbp = Wbp ? CreateWidget<UUmHudHand>(W.World, Wbp) : nullptr;
    TestTrue(TEXT("the WBP has every BindWidget"), FromWbp && FromWbp->HasAllParts() && !FromWbp->UsesCodeDefaultTree());
  } else {
    AddWarning(TEXT("WBP_UI_HUD_HAND not generated in this checkout (the code tree is tested)"));
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHandLayoutTest,
    "Unmatched.S08.Hud.Hand.Layout row and fan 3 5 7 9 10 cards x L and S on both FIELDs, HB-22 numbers, lowered 48 su",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHandLayoutTest::RunTest(const FString&) {
  using namespace UmHandTest;
  for (const FHandCanvas& C : Canvases) {
    for (const bool bSarpedon : {false, true}) {
      const FUmHandFrame F = Frame(C, bSarpedon);
      const FString Tag = FString::Printf(TEXT("%s %s"), C.Name, bSarpedon ? TEXT("sarpedon") : TEXT("marmoreal"));
      const float CardW = F.bClassS ? 120.0f : 150.0f;
      const float CardH = F.bClassS ? 166.0f : 208.0f;
      const float Nominal = F.bClassS ? 128.0f : 158.0f;
      const float Corridor = F.CorridorRightSu - F.CorridorLeftSu;
      TestEqual(Tag + TEXT(": class S below 1500 su"), F.bClassS, C.Su.X < 1500.0);
      const float WantVisible = FMath::Clamp(static_cast<float>(C.Su.Y) - (F.FieldBottomSu + 8.0f + 22.0f), 48.0f, CardH);
      TestTrue(FString::Printf(TEXT("%s: visible %.1f = clamp(H - FIELD - 30, 48, %.0f) %.1f"), *Tag, F.VisibleSu, CardH, WantVisible),
               Near(F.VisibleSu, WantVisible, 0.01));
      for (const int32 N : {3, 5, 7, 9, 10}) {
        const UmHudHand::FRow R = UmHudHand::Row(N, F);
        const FString T = FString::Printf(TEXT("%s n=%d"), *Tag, N);
        TestEqual(T + TEXT(": one rect per card"), R.CardPos.Num(), N);
        TestTrue(FString::Printf(TEXT("%s: inside the corridor %.1f..%.1f (row %.1f..%.1f)"), *T, F.CorridorLeftSu, F.CorridorRightSu,
                                 R.LeftSu, R.RightSu),
                 R.LeftSu >= F.CorridorLeftSu - 0.01f && R.RightSu <= F.CorridorRightSu + 0.01f);
        const float Full = CardW + Nominal * (N - 1);
        if (Full <= Corridor) {
          TestTrue(T + TEXT(": a row with the nominal step, centred"),
                   !R.bFan && Near(R.StepSu, Nominal) && Near(R.LeftSu - F.CorridorLeftSu, F.CorridorRightSu - R.RightSu, 0.01));
        } else {
          TestTrue(FString::Printf(TEXT("%s: a fan over the corridor, step %.2f"), *T, R.StepSu),
                   R.bFan && Near(R.StepSu, (Corridor - CardW) / (N - 1), 0.01));
          // 04 §2.6 / §7.4: >= 72 su - except where the corridor cannot hold it (ВР-VS2-HB22-09: 720p 150 %, 9+ cards)
          const bool bAllowedBelow = FCString::Strcmp(C.Name, TEXT("720p150")) == 0 && N >= 9;
          TestTrue(FString::Printf(TEXT("%s: step %.2f >= 72 (below allowed: %d)"), *T, R.StepSu, bAllowedBelow ? 1 : 0),
                   R.StepSu >= 72.0f - 0.01f || bAllowedBelow);
          TestEqual(T + TEXT(": below72 flag"), R.bBelowMin, R.StepSu < 72.0f - 1.0e-3f);
        }
        // at rest the cards and the caption stay off FIELD (overlapField 0)
        const float CaptionTop = R.CardTopSu - 22.0f;
        TestTrue(FString::Printf(TEXT("%s: caption top %.1f >= FIELD bottom %.1f + 8"), *T, CaptionTop, F.FieldBottomSu),
                 CaptionTop >= F.FieldBottomSu + 8.0f - 0.01f);
        TestTrue(T + TEXT(": card top = H - visible"), Near(R.CardTopSu, C.Su.Y - F.VisibleSu, 0.01));
      }
      // the selected raise never reaches FIELD; the lowered row keeps 48 su
      const float Raise = UmHudHand::SelectedRaiseFor(F);
      TestTrue(FString::Printf(TEXT("%s: raise %.1f <= 32, top - raise >= FIELD"), *Tag, Raise),
               Raise <= 32.0f && (C.Su.Y - F.VisibleSu - Raise) >= F.FieldBottomSu - 0.01f);
      TestTrue(Tag + TEXT(": lowered keeps 48 su"), Near(F.VisibleSu - UmHudHand::LowerDropSu(F), 48.0, 0.01));
      // hover 225 x 312 on every canvas (ВР-VS2-HB22-03), bottom 24 su over the canvas bottom
      const FBox2D Hover = UmHudHand::HoverRect(UmHudHand::Row(5, F).CardPos[2], F);
      TestTrue(FString::Printf(TEXT("%s: hover %.1f x %.1f, bottom %.1f"), *Tag, Hover.GetSize().X, Hover.GetSize().Y, Hover.Max.Y),
               Near(Hover.GetSize().X, 225.0, 0.01) && Near(Hover.GetSize().Y, 312.0, 0.8) && Near(Hover.Max.Y, C.Su.Y - 24.0, 0.01));
      // the boost slots (04 §1.6, ВР-VS2-HB22-11)
      const FBox2D Slot = UmHudHand::BoostRect(EUmHandBoostSlot::Slot, F);
      const FBox2D Combat = UmHudHand::BoostRect(EUmHandBoostSlot::Combat, F);
      if (F.bClassS) {
        TestTrue(Tag + TEXT(": S slot (16, 64, 120, 166)"), Slot.Min.Equals(FVector2D(16.0, 64.0)) && Slot.GetSize().Equals(FVector2D(120.0, 166.0)));
        TestTrue(Tag + TEXT(": S attack boost (48, 240, 150, 208)"), Combat.Min.Equals(FVector2D(48.0, 240.0)) && Combat.GetSize().Equals(FVector2D(150.0, 208.0)));
      } else {
        TestTrue(Tag + TEXT(": L slot (24, 84, 190, 264)"), Slot.Min.Equals(FVector2D(24.0, 84.0)) && Slot.GetSize().Equals(FVector2D(190.0, 264.0)));
        TestTrue(Tag + TEXT(": L attack boost (64, 360, 230, 319)"), Combat.Min.Equals(FVector2D(64.0, 360.0)) && Combat.GetSize().Equals(FVector2D(230.0, 319.0)));
      }
    }
  }
  // HB-22 numbers: Marmoreal 1080p 100 % with its mask FIELD (the last protected row 876 px)
  {
    const FBox2D F22(FVector2D(377.0, 257.0), FVector2D(1542.0, 877.0));
    const FUmHandFrame F = FUmHandFrame::FromLayout(FUmHudLayout::Compute(FVector2D(1920.0, 1080.0), 1.0f, &F22));
    const UmHudHand::FRow R = UmHudHand::Row(5, F);
    TestTrue(FString::Printf(TEXT("HB-22 5 cards: x 567 / 725 / 1199, top 907 (%.1f, %.1f, %.1f, %.1f)"), R.CardPos[0].X,
                             R.CardPos[1].X, R.CardPos[4].X, R.CardTopSu),
             Near(R.CardPos[0].X, 567.0) && Near(R.CardPos[1].X, 725.0) && Near(R.CardPos[4].X, 1199.0) && Near(R.CardTopSu, 907.0));
    const FBox2D Hover = UmHudHand::HoverRect(R.CardPos[0], F);
    TestTrue(FString::Printf(TEXT("HB-22 hover [529.5, 744, 225, 312] (%.1f, %.1f)"), Hover.Min.X, Hover.Min.Y),
             Near(Hover.Min.X, 529.5) && Near(Hover.Min.Y, 744.0));
    TestTrue(TEXT("HB-22 9 cards fan 126.75"), Near(UmHudHand::Row(9, F).StepSu, 126.75));
    TestTrue(FString::Printf(TEXT("HB-22 raise 30 at the protected row (%.1f)"), UmHudHand::SelectedRaiseFor(F)),
             Near(UmHudHand::SelectedRaiseFor(F), 30.0));
  }
  {
    // 720p 150 %: the corridor 268 .. W - 240 (897.78); 9 cards 63.72 su (ВР-VS2-HB22-09), 5 cards 127.44
    const FBox2D F22(FVector2D(300.0, 150.0), FVector2D(800.0, 520.0));
    const FUmHandFrame F = FUmHandFrame::FromLayout(FUmHudLayout::Compute(FVector2D(1280.0 / 1.125, 640.0), 1.125f, &F22));
    TestTrue(FString::Printf(TEXT("720p 150 %%: corridor 268..897.78 (%.2f..%.2f)"), F.CorridorLeftSu, F.CorridorRightSu),
             Near(F.CorridorLeftSu, 268.0) && Near(F.CorridorRightSu, 897.78, 0.01));
    TestTrue(TEXT("720p 150 % 9 cards 63.72"), Near(UmHudHand::Row(9, F).StepSu, 63.722, 0.01) && UmHudHand::Row(9, F).bBelowMin);
    TestTrue(TEXT("720p 150 % 5 cards 127.44"), Near(UmHudHand::Row(5, F).StepSu, 127.444, 0.01));
    TestTrue(TEXT("720p 150 % 3 cards centred at 394.89"), Near(UmHudHand::Row(3, F).CardPos[0].X, 394.889, 0.01));
  }
  // the widget places its cards on the row and lowers it to 48 su in 150 ms
  FWorld W(TEXT("UmHandLayout"));
  const FUmHandFrame F = Frame(Canvases[0], false);
  UUmHudHand* H = Make(W.World, F);
  if (!TestNotNull(TEXT("hand"), H)) return false;
  FUmHandModel M = Model(TestHand(9));
  H->ApplyModel(M);
  At(H, 1000.0);
  const UmHudHand::FRow R = UmHudHand::Row(9, F);
  for (int32 I = 0; I < 9; ++I) {
    UUmCardWidget* C = H->FindCard(M.Cards[I].Card.InstanceId);
    TestTrue(FString::Printf(TEXT("card %d at its rest slot"), I), C && SlotPos(C).Equals(R.CardPos[I] - F.SlotSu.Min, 0.01));
  }
  TestEqual(TEXT("caption «Рука 9/7»"), H->CountText->GetText().ToString(), UmHudHand::Caption(9, 7).ToString());
  TestTrue(TEXT("caption shown"), H->IsCaptionShown());
  M.bLowered = true;
  H->ApplyModel(M);
  At(H, 1075.0);
  TestTrue(FString::Printf(TEXT("75 ms: going down (%.1f)"), H->GetLowerNowSu()), H->GetLowerNowSu() > 1.0f && H->GetLowerNowSu() < UmHudHand::LowerDropSu(F));
  At(H, 1150.0);
  TestTrue(TEXT("150 ms: 48 su visible"), Near(F.VisibleSu - H->GetLowerNowSu(), 48.0));
  UUmCardWidget* First = H->FindCard(M.Cards[0].Card.InstanceId);
  TestTrue(TEXT("the card moves down with its hit rect"), First && Near(First->GetRenderTransform().Translation.Y, UmHudHand::LowerDropSu(F)));
  TestFalse(TEXT("lowered: the caption hides (ВР-VS2-HB22-10)"), H->IsCaptionShown());
  TestEqual(TEXT("SHOT state=lowered"), H->StateName(), FString(TEXT("lowered")));
  H->SetHoverIndex(2);
  At(H, 1400.0);
  UUmCardWidget* Third = H->FindCard(M.Cards[2].Card.InstanceId);
  TestTrue(TEXT("lowered: no preview (SD-26)"), Third && Near(Third->GetScale(), 1.0) && Near(Third->GetOwnerOffset().Y, 0.0));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHandInputTest,
    "Unmatched.S08.Hud.Hand.Input instance ids, keys 1-9, reorder, hover strips, preview keeps the hover, wheel, double click, inspector",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHandInputTest::RunTest(const FString&) {
  using namespace UmHandTest;
  FWorld W(TEXT("UmHandInput"));
  const FUmHandFrame F = Frame(Canvases[0], false);
  UUmHudHand* H = Make(W.World, F);
  if (!TestNotNull(TEXT("hand"), H)) return false;
  TSharedPtr<FS09HudPressArbiter> Arbiter = MakeShared<FS09HudPressArbiter>();
  uint64 Frames = 100;
  Arbiter->SetFrameClock([&Frames]() { return Frames; });
  TArray<FString> Pressed, Played, Inspected;
  H->SetInput(Arbiter, [&Pressed](const FS09HudPressOutcome& O, const FString& Id) {
        if (O.Result == ES09HudPressResult::Act) Pressed.Add(Id);
      },
      [&Inspected](const FString& Id) { Inspected.Add(Id); }, [&Played](const FString& Id) { Played.Add(Id); });
  // the run I hand of Marmoreal: two copies of Gaze of Stone
  const TArray<FS09CardView> Run = {Card(TEXT("medusa"), TEXT("Gaze of Stone"), 0), Card(TEXT("medusa"), TEXT("Gaze of Stone"), 1),
                                    Card(TEXT("medusa"), TEXT("Snipe")), Card(TEXT("medusa"), TEXT("Clutching Claws")),
                                    Card(TEXT("medusa"), TEXT("Dash"))};
  FUmHandModel M = Model(Run);
  H->ApplyModel(M);
  At(H, 500.0);
  UUmCardWidget* G0 = H->FindCard(Run[0].InstanceId);
  UUmCardWidget* G1 = H->FindCard(Run[1].InstanceId);
  TestTrue(TEXT("two copies = two widgets (UI-INP-007)"), G0 && G1 && G0 != G1);
  TestTrue(TEXT("press ids by instance"), G0 && G1 && G0->GetPressId() == FName(*(TEXT("hand.") + Run[0].InstanceId)) &&
                                              G1->GetPressId() == FName(*(TEXT("hand.") + Run[1].InstanceId)));
  TestEqual(TEXT("key 2 = the second copy"), UmHudHand::KeyTarget(M, 2), Run[1].InstanceId);
  TestEqual(TEXT("key 9 = none"), UmHudHand::KeyTarget(M, 9), FString());
  // a click on the second copy reaches the owner with its instance id
  const FGeometry Geo = FGeometry::MakeRoot(FVector2D(150.0, 208.0), FSlateLayoutTransform());
  G1->NativeOnMouseButtonDown(Geo, Left(FVector2D(75.0, 40.0), true));
  G1->NativeOnMouseButtonUp(Geo, Left(FVector2D(75.0, 40.0), false));
  TestTrue(TEXT("the press -> hand.<second copy>"), Pressed.Num() == 1 && Pressed[0] == Run[1].InstanceId);
  G1->NativeOnMouseButtonDoubleClick(Geo, Left(FVector2D(75.0, 40.0), true));
  G1->NativeOnMouseButtonUp(Geo, Left(FVector2D(75.0, 40.0), false));
  TestTrue(TEXT("double click = play (UI-INP-003), no second press"), Played.Num() == 1 && Played[0] == Run[1].InstanceId && Pressed.Num() == 1);
  G1->NativeOnMouseButtonDown(Geo, Right(FVector2D(75.0, 40.0), true));
  G1->NativeOnMouseButtonUp(Geo, Right(FVector2D(75.0, 40.0), false));
  TestTrue(TEXT("right button = the inspector"), Inspected.Num() == 1 && Inspected[0] == Run[1].InstanceId);
  // the first copy is played: the second keeps its widget, its index moves (the pool, no recreation)
  const int32 CreatedBefore = H->CreatedCount();
  FUmHandModel M2 = Model({Run[1], Run[2], Run[3], Run[4]});
  H->ApplyModel(M2);
  TestTrue(TEXT("the same widget for the same instance"), H->FindCard(Run[1].InstanceId) == G1 && H->IndexOf(Run[1].InstanceId) == 0);
  TestEqual(TEXT("no widget made"), H->CreatedCount(), CreatedBefore);
  TestEqual(TEXT("key 1 = the second copy now"), UmHudHand::KeyTarget(M2, 1), Run[1].InstanceId);
  At(H, 2000.0);
  // the hover by the strips of the row (5 cards: x 567 + 158 k)
  H->ApplyModel(M);
  At(H, 3000.0);
  const UmHudHand::FRow R = H->GetRow();
  const float Y = static_cast<float>(F.CanvasSu.Y) - 40.0f;
  H->HoverAtSu(FVector2D(R.CardPos[2].X + 10.0, Y));
  TestEqual(TEXT("strip 2"), H->GetHoverIndex(), 2);
  H->HoverAtSu(FVector2D(R.CardPos[2].X + 155.0, Y));
  TestEqual(TEXT("the 8 su gap belongs to the left card"), H->GetHoverIndex(), 2);
  H->HoverAtSu(FVector2D(R.CardPos[3].X + 2.0, Y));
  TestEqual(TEXT("strip 3 (the raised neighbour never takes it)"), H->GetHoverIndex(), 3);
  At(H, 3150.0);
  UUmCardWidget* C3 = H->FindCard(M.Cards[3].Card.InstanceId);
  const FBox2D Hover = UmHudHand::HoverRect(R.CardPos[3], F);
  TestTrue(FString::Printf(TEXT("150 ms: the preview 1.5 with its bottom 24 su over the edge (offset %.1f)"), C3 ? C3->GetOwnerOffset().Y : 0.0),
           C3 && Near(C3->GetScale(), 1.5) && Near(C3->GetOwnerOffset().Y, Hover.Max.Y - (R.CardPos[3].Y + 208.0), 0.05));
  TestEqual(TEXT("SHOT state=hover"), H->StateName(), FString(TEXT("hover")));
  H->HoverAtSu(FVector2D(Hover.GetCenter().X, Hover.Min.Y + 20.0));
  TestEqual(TEXT("up on the raised preview: still hovered"), H->GetHoverIndex(), 3);
  H->HoverAtSu(FVector2D(Hover.Max.X + 400.0, Hover.Min.Y + 20.0));
  TestEqual(TEXT("off the preview and the row: none"), H->GetHoverIndex(), INDEX_NONE);
  TestTrue(TEXT("wheel forward from none -> the first card"), H->WheelStep(true) && H->GetHoverIndex() == 0);
  TestTrue(TEXT("wheel forward -> the next"), H->WheelStep(true) && H->GetHoverIndex() == 1);
  TestTrue(TEXT("wheel back"), H->WheelStep(false) && H->GetHoverIndex() == 0);
  H->ClearHover();
  // the attack step: Medusa attacks - the Harpy card shows why.banner.mismatch, a defense card is dimmed without a why
  FS09CommandUi Ui;
  Ui.Mode = ES09CommandMode::AttackDraft;
  Ui.AttackAttackerId = TEXT("f-medusa");
  Ui.AttackCardId = Run[0].InstanceId;
  TArray<FS08BoardFighter> Fighters;
  FS08BoardFighter Medusa;
  Medusa.Id = TEXT("f-medusa");
  Medusa.Name = TEXT("Medusa");
  Medusa.bIsHero = true;
  Fighters.Add(Medusa);
  FS09PlayerPanel Own;
  Own.Cards = {Run[0], Run[3], Card(TEXT("medusa"), TEXT("Hiss and Slither"))};
  Own.HandMaxSize = 7;
  UmHudHand::FGatherIn In;
  In.Own = &Own;
  In.Ui = &Ui;
  In.Fighters = &Fighters;
  In.HeroSlug = TEXT("medusa");
  const FUmHandModel A = UmHudHand::Gather(In);
  TestTrue(TEXT("the attack card selected"), A.Cards.Num() == 3 && A.Cards[0].bSelected && A.Cards[0].bPlayable);
  TestTrue(TEXT("Clutching Claws: why.banner.mismatch {Harpy}"), !A.Cards[1].bPlayable && A.Cards[1].Reason.Key == FName(TEXT("why.banner.mismatch")) &&
                                                                   A.Cards[1].Reason.Args.FindRef(TEXT("bannerName")) == TEXT("Harpy"));
  TestTrue(TEXT("Hiss and Slither (defense): dimmed, no exact why (ВР-VS3-19)"), !A.Cards[2].bPlayable && !A.Cards[2].Reason.IsSet());
  H->ApplyModel(A);
  H->SetHoverIndex(1);
  At(H, 4000.0);
  TestTrue(TEXT("tooltip «Только для Harpy» over the hovered card"), H->IsTooltipShown() && H->GetTooltipText().ToString().Contains(TEXT("Harpy")));
  H->SetHoverIndex(2);
  TestFalse(TEXT("no tooltip without an exact key"), H->IsTooltipShown());
  // the unplayable card without a why goes on to the owner (the game logic answers)
  Pressed.Reset();
  UUmCardWidget* Hiss = H->FindCard(A.Cards[2].Card.InstanceId);
  if (Hiss) {
    Hiss->NativeOnMouseButtonDown(Geo, Left(FVector2D(75.0, 40.0), true));
    Hiss->NativeOnMouseButtonUp(Geo, Left(FVector2D(75.0, 40.0), false));
  }
  TestEqual(TEXT("the press of a type mismatch reaches the owner"), Pressed.Num(), 1);
  return true;
}

// VS-3 frames step (ВР-VS3-69): the live client showed the CP-16 unplayable look stuck at the first step of its tween -
// the owner steps the running card tweens (StepAnimating: NativeTick and the game mode), no other call in between.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHandAnimateTest,
    "Unmatched.S08.Hud.Hand.Animate the owner steps the running card tweens - unplayable 0.6 after 150 ms, the hover 1.5",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHandAnimateTest::RunTest(const FString&) {
  using namespace UmHandTest;
  FWorld W(TEXT("UmHandAnimate"));
  const FUmHandFrame F = Frame(Canvases[0], false);
  UUmHudHand* H = Make(W.World, F);
  if (!TestNotNull(TEXT("hand"), H)) return false;
  const TArray<FS09CardView> Run = TestHand(5);
  FUmHandModel M = Model(Run);
  H->ApplyModel(M);
  At(H, 500.0);
  // the defense step: card 2 becomes unplayable at 500 ms; only StepAnimating runs afterwards
  M.Cards[2].bPlayable = false;
  H->ApplyModel(M);
  UUmCardWidget* C2 = H->FindCard(Run[2].InstanceId);
  if (!TestNotNull(TEXT("card 2"), C2)) return false;
  H->SetClockOverrideMs(575.0);
  H->StepAnimating();
  TestTrue(FString::Printf(TEXT("75 ms: half way (%.3f)"), C2->GetDesaturation()), Near(C2->GetDesaturation(), 0.3, 0.02));
  H->SetClockOverrideMs(700.0);
  H->StepAnimating();
  TestTrue(FString::Printf(TEXT("200 ms: the unplayable look 0.6 / 0.7 (%.3f / %.3f)"), C2->GetDesaturation(), C2->GetFaceOpacity()),
           Near(C2->GetDesaturation(), 0.6) && Near(C2->GetFaceOpacity(), 0.7));
  TestFalse(TEXT("the tween is over"), C2->IsAnimating());
  // the hover: the preview scale 1.5 by StepAnimating alone
  H->HoverAtSu(H->RestRectSu(1).GetCenter());
  TestEqual(TEXT("hover card 1"), H->GetHoverIndex(), 1);
  H->SetClockOverrideMs(900.0);
  H->StepAnimating();
  UUmCardWidget* C1 = H->FindCard(Run[1].InstanceId);
  TestTrue(FString::Printf(TEXT("the preview 1.5 (%.3f)"), C1 ? C1->GetScale() : 0.0f), C1 && Near(C1->GetScale(), 1.5));
  // ВР-VS3-72: the painted rect takes the raised preview (225 x 312, its bottom 24 su over the canvas bottom), the row
  // rect does not
  const FBox2D Row = H->DrawnRectSu();
  const FBox2D Paint = H->PaintedRectSu();
  const FBox2D Hover = UmHudHand::HoverRect(H->RestRectSu(1).Min, F);
  TestTrue(FString::Printf(TEXT("painted top %.1f = the preview top %.1f (row top %.1f)"), Paint.Min.Y, Hover.Min.Y, Row.Min.Y),
           Paint.bIsValid && Near(Paint.Min.Y, Hover.Min.Y, 1.0) && Row.Min.Y > Hover.Min.Y + 50.0);
  return true;
}

// ------------------------------------------------------------------------------------------------ HB-25

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHandDiscardTest,
    "Unmatched.S08.Hud.Hand.Discard limit discard - every card a candidate, n of 9 marked, unmark, SHOT state=discard",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHandDiscardTest::RunTest(const FString&) {
  using namespace UmHandTest;
  FWorld W(TEXT("UmHandDiscard"));
  const TArray<FS09CardView> Nine = TestHand(9);
  FS09PlayerPanel Own;
  Own.Cards = Nine;
  Own.HandCount = 9;
  Own.HandMaxSize = 7;
  FS09CommandUi Ui;
  Ui.Mode = ES09CommandMode::DiscardDraft;
  Ui.PendingDiscard.Id = TEXT("discard-1");
  Ui.PendingDiscard.Count = 2;
  UmHudHand::FGatherIn In;
  In.Own = &Own;
  In.Ui = &Ui;
  In.HeroSlug = TEXT("medusa");
  FUmHandModel M = UmHudHand::Gather(In);
  TestEqual(TEXT("mode discard"), M.Mode, EUmHandMode::Discard);
  bool bAllCandidates = true;
  for (const FUmHandCardModel& C : M.Cards) bAllCandidates &= C.bCandidate && !C.bMarked;
  TestTrue(TEXT("every card a candidate"), bAllCandidates);
  const FUmHandFrame F = Frame(Canvases[0], false);
  UUmHudHand* H = Make(W.World, F);
  if (!TestNotNull(TEXT("hand"), H)) return false;
  H->ApplyModel(M);
  At(H, 500.0);
  UUmCardWidget* C7 = H->FindCard(Nine[7].InstanceId);
  TestTrue(TEXT("candidate frame card.frame.warning"), C7 && C7->GetFrameKey() == FName(TEXT("card.frame.warning")));
  TestEqual(TEXT("SHOT state=discard"), H->StateName(), FString(TEXT("discard")));
  TestEqual(TEXT("«Рука 9/7»"), H->CountText->GetText().ToString(), UmHudHand::Caption(9, 7).ToString());
  // mark two (the click toggles the selection - the command state, as the game mode does)
  Ui.DiscardSelection = {Nine[7].InstanceId, Nine[8].InstanceId};
  M = UmHudHand::Gather(In);
  H->ApplyModel(M);
  At(H, 650.0);
  UUmCardWidget* C8 = H->FindCard(Nine[8].InstanceId);
  TestTrue(TEXT("marked: 16 su down"), C7 && C8 && C7->IsMarked() && C8->IsMarked() && Near(C7->GetShiftSu(), 16.0));
  At(H, 680.0);
  TestTrue(TEXT("marked: card-drop shown"), C7 && Near(C7->GetDropOpacity(), 1.0));
  int32 Marked = 0;
  for (const FUmHandCardModel& C : M.Cards) Marked += C.bMarked ? 1 : 0;
  TestEqual(TEXT("2 of 9 marked"), Marked, 2);
  TArray<FString> Lines;
  H->CollectShotLines(Lines);
  TestTrue(TEXT("SHOT line marked=2 mode=discard"), Lines.Num() > 0 && Lines[0].Contains(TEXT("marked=2")) && Lines[0].Contains(TEXT("mode=discard")));
  // the second click unmarks
  Ui.DiscardSelection = {Nine[7].InstanceId};
  H->ApplyModel(UmHudHand::Gather(In));
  At(H, 900.0);
  TestTrue(TEXT("unmarked: back up, still a candidate"), C8 && !C8->IsMarked() && Near(C8->GetShiftSu(), 0.0) &&
                                                            C8->GetFrameKey() == FName(TEXT("card.frame.warning")));
  // DISCARD_CARDS of an effect: the same picture
  FS09CommandUi Effect;
  Effect.Mode = ES09CommandMode::PendingChoice;
  Effect.bHasPendingChoice = true;
  Effect.PendingChoice.Type = TEXT("DISCARD_CARDS");
  Effect.PendingChoice.bHasValue = true;
  Effect.PendingChoice.Value = 1;
  Effect.PendingCardIds = {Nine[0].InstanceId};
  In.Ui = &Effect;
  const FUmHandModel E = UmHudHand::Gather(In);
  TestTrue(TEXT("DISCARD_CARDS: discard mode, the pick marked"), E.Mode == EUmHandMode::Discard && E.Cards[0].bMarked && E.Cards[1].bCandidate);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHandBoostTest,
    "Unmatched.S08.Hud.Hand.Boost maneuver boost into SLOT face down plus N, King Arthur attack boost beside COMBAT-L, why.boost.no.value",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHandBoostTest::RunTest(const FString&) {
  using namespace UmHandTest;
  FWorld W(TEXT("UmHandBoost"));
  // ---- the maneuver: Medusa boosts with Dash (+1)
  const TArray<FS09CardView> Run = {Card(TEXT("medusa"), TEXT("Gaze of Stone"), 0), Card(TEXT("medusa"), TEXT("Gaze of Stone"), 1),
                                    Card(TEXT("medusa"), TEXT("Snipe")), Card(TEXT("medusa"), TEXT("Clutching Claws")),
                                    Card(TEXT("medusa"), TEXT("Dash"))};
  FS09CardView NoBoost = Card(TEXT("medusa"), TEXT("Regroup"));
  NoBoost.InstanceId = TEXT("card::no-boost");
  NoBoost.bHasBoostValue = false;
  NoBoost.BoostValue = 0;
  FS09PlayerPanel Own;
  Own.Cards = Run;
  Own.Cards.Add(NoBoost);
  Own.HandMaxSize = 7;
  FS09CommandUi Ui;
  Ui.Mode = ES09CommandMode::ManeuverDraft;
  UmHudHand::FGatherIn In;
  In.Own = &Own;
  In.Ui = &Ui;
  In.HeroSlug = TEXT("medusa");
  FUmHandModel M = UmHudHand::Gather(In);
  TestEqual(TEXT("maneuver: boost mode"), M.Mode, EUmHandMode::Boost);
  TestTrue(TEXT("a printed BOOST > 0 is a candidate"), M.Cards[4].bPlayable);
  TestTrue(TEXT("no BOOST: why.boost.no.value"), !M.Cards[5].bPlayable && M.Cards[5].Reason.Key == FName(TEXT("why.boost.no.value")));
  const FUmHandFrame F = Frame(Canvases[0], false);
  UUmHudHand* H = Make(W.World, F);
  if (!TestNotNull(TEXT("hand"), H)) return false;
  H->ApplyModel(M);
  At(H, 500.0);
  Ui.BoostCardId = Run[4].InstanceId;
  M = UmHudHand::Gather(In);
  TestTrue(TEXT("Dash placed"), M.Cards[4].bBoostPlaced);
  H->ApplyModel(M);
  UUmCardWidget* Dash = H->FindCard(Run[4].InstanceId);
  At(H, 575.0);
  TestTrue(TEXT("75 ms: on its way and turning"), Dash && Dash->GetOwnerOffset().Size() > 1.0 && Dash->IsFlipping());
  At(H, 1000.0);
  const FBox2D Slot = UmHudHand::BoostRect(EUmHandBoostSlot::Slot, F);
  TestTrue(TEXT("in SLOT (24, 84) at 190 x 264"), Dash && SlotPos(Dash).Equals(Slot.Min - F.SlotSu.Min, 0.01) &&
                                                     Dash->GetState().Show == EUmCardShow::Slot && Near(Dash->GetOwnerOffset().Size(), 0.0));
  TestTrue(TEXT("face down, chip +1 (the own face kept, CP-18)"), Dash && Dash->IsFaceDown() && Dash->GetChipText() == TEXT("+1") &&
                                                                     Near(Dash->GetChipOpacity(), 1.0) && Dash->GetCard().Name == TEXT("Dash"));
  TestTrue(TEXT("the BOOST ribbon under it"), H->BoostRibbon && H->BoostRibbon->GetVisibility() != ESlateVisibility::Collapsed);
  TestEqual(TEXT("the hand lost it: «Рука 5/7»"), H->CountText->GetText().ToString(), UmHudHand::Caption(5, 7).ToString());
  TestEqual(TEXT("the row closed up: 5 cards"), H->GetRow().CardPos.Num(), 5);
  // cleared: back into the hand, face up
  Ui.BoostCardId.Reset();
  H->ApplyModel(UmHudHand::Gather(In));
  At(H, 1500.0);
  TestTrue(TEXT("cleared: back in the row, face up, no chip"), Dash && !Dash->IsFaceDown() && Dash->GetBoost() == UmCardWidget::NoBoostChip &&
                                                                  Dash->GetState().Show == EUmCardShow::Hand);
  // ---- King Arthur attacks with Swift Strike and boosts with Noble Sacrifice (+3)
  const TArray<FS09CardView> Ka = {Card(TEXT("king-arthur"), TEXT("The Holy Grail")), Card(TEXT("king-arthur"), TEXT("Noble Sacrifice")),
                                   Card(TEXT("king-arthur"), TEXT("Swift Strike"))};
  FS09PlayerPanel KaOwn;
  KaOwn.Cards = Ka;
  KaOwn.HandMaxSize = 7;
  FS09CommandUi Atk;
  Atk.Mode = ES09CommandMode::AttackDraft;
  Atk.AttackAttackerId = TEXT("f-arthur");
  Atk.AttackTargetId = TEXT("f-medusa");
  Atk.AttackCardId = Ka[2].InstanceId;
  Atk.OpenAttackAbilityPrompt();
  Atk.AttackAbilityBoostCardId = Ka[1].InstanceId;
  UmHudHand::FGatherIn KaIn;
  KaIn.Own = &KaOwn;
  KaIn.Ui = &Atk;
  KaIn.HeroSlug = TEXT("king-arthur");
  const FUmHandModel K = UmHudHand::Gather(KaIn);
  TestTrue(TEXT("ability prompt: boost mode beside COMBAT-L"), K.Mode == EUmHandMode::Boost && K.BoostSlot == EUmHandBoostSlot::Combat);
  TestTrue(TEXT("Swift Strike selected, Noble Sacrifice placed"), K.Cards[2].bSelected && !K.Cards[2].bBoostPlaced && K.Cards[1].bBoostPlaced);
  UUmHudHand* KH = Make(W.World, F);
  KH->ApplyModel(K);
  At(KH, 1000.0);
  UUmCardWidget* Noble = KH->FindCard(Ka[1].InstanceId);
  const FBox2D Combat = UmHudHand::BoostRect(EUmHandBoostSlot::Combat, F);
  TestTrue(TEXT("beside COMBAT-L (64, 360) at 230 x 319"), Noble && SlotPos(Noble).Equals(Combat.Min - F.SlotSu.Min, 0.01) &&
                                                             Noble->GetState().Show == EUmCardShow::Combat);
  TestTrue(TEXT("chip +3 right-aligned over the top edge (ВР-VS2-HB22-11)"), Noble && Noble->GetChipText() == TEXT("+3") && Noble->IsChipRightAbove());
  TestEqual(TEXT("«Рука 2/7» (the attack card is still in the hand)"), KH->CountText->GetText().ToString(), UmHudHand::Caption(2, 7).ToString());
  TestTrue(TEXT("no ribbon for the attack boost"), KH->BoostRibbon && KH->BoostRibbon->GetVisibility() == ESlateVisibility::Collapsed);
  // ---- class S: the S rects; the chip 32 su under 1 px per su (IC-34 П-2)
  const FUmHandFrame S = Frame(Canvases[3], false);
  UUmHudHand* SH = Make(W.World, S);
  SH->ApplyModel(K);
  At(SH, 1000.0);
  UUmCardWidget* SNoble = SH->FindCard(Ka[1].InstanceId);
  TestTrue(TEXT("S: (48, 240) at 150 x 208"), SNoble && SlotPos(SNoble).Equals(FVector2D(48.0, 240.0) - S.SlotSu.Min, 0.01) &&
                                                 SNoble->GetState().Show == EUmCardShow::ClassSCombat);
  const FUmHandFrame Small = Frame(Canvases[1], false);  // 720p 100 %: 0.75 px per su
  UUmHudHand* LH = Make(W.World, Small);
  LH->ApplyModel(K);
  At(LH, 1000.0);
  UUmCardWidget* LNoble = LH->FindCard(Ka[1].InstanceId);
  TestTrue(FString::Printf(TEXT("0.75 px per su: chip 32 su = 24 px >= 21 (%.0f)"), LNoble ? LNoble->GetChipSu() : 0.0f),
           LNoble && Near(LNoble->GetChipSu(), 32.0));
  TestTrue(TEXT("1.0 px per su: chip 24 su"), Noble && Near(Noble->GetChipSu(), 24.0));
  TestTrue(TEXT("ChipSuFor"), Near(UmCardWidget::ChipSuFor(0.75f), 32.0) && Near(UmCardWidget::ChipSuFor(1.0f), 24.0) &&
                                  Near(UmCardWidget::ChipSuFor(1.5f), 24.0));
  // the BOOST_CHOICE of an effect in combat: beside COMBAT-L too
  FS09CommandUi Choice;
  Choice.Mode = ES09CommandMode::PendingChoice;
  Choice.bHasPendingChoice = true;
  Choice.PendingChoice.Type = TEXT("BOOST_CHOICE");
  Choice.Combat.bPresent = true;
  Choice.PendingCardIds = {Ka[0].InstanceId};
  KaIn.Ui = &Choice;
  const FUmHandModel C = UmHudHand::Gather(KaIn);
  TestTrue(TEXT("BOOST_CHOICE in combat: placed beside COMBAT-L"), C.Mode == EUmHandMode::Boost && C.BoostSlot == EUmHandBoostSlot::Combat &&
                                                                        C.Cards[0].bBoostPlaced);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHandBudgetTest,
    "Unmatched.S08.Hud.Hand.Budget 0 new widgets after the warm-up, ApplyModel of 9 cards p95 <= 0.15 ms",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHandBudgetTest::RunTest(const FString&) {
  using namespace UmHandTest;
  FWorld W(TEXT("UmHandBudget"));
  const FUmHandFrame F = Frame(Canvases[0], true);
  UUmHudHand* H = Make(W.World, F);
  if (!TestNotNull(TEXT("hand"), H)) return false;
  // warm-up: the textures of the deck and the pool of 10
  TArray<FS09CardView> Deck = UmCardGallery::LoadDeck(TEXT("medusa"));
  for (int32 I = 0; I < Deck.Num(); ++I) Deck[I].InstanceId = FString::Printf(TEXT("card::%d"), I);
  FUmHandModel M = Model(TArray<FS09CardView>(Deck.GetData(), FMath::Min(9, Deck.Num())));
  H->ApplyModel(M);
  At(H, 2000.0);
  const int32 Warm = H->CreatedCount();
  // 30 snapshots: a draw, a play, a selection, a lowering - instance ids come and go
  double Ms = 2000.0;
  int32 Next = 9;
  for (int32 S = 0; S < 30; ++S) {
    FUmHandModel N = M;
    N.Cards.RemoveAt(0);
    FUmHandCardModel Drawn;
    Drawn.Card = Deck[Next % Deck.Num()];
    Drawn.Card.InstanceId = FString::Printf(TEXT("card::%d"), Next++);
    N.Cards.Add(Drawn);
    N.Cards[S % N.Cards.Num()].bSelected = true;
    N.bLowered = (S % 5) == 0;
    H->ApplyModel(N);
    Ms += 700.0;  // the leaving card is back in the pool
    At(H, Ms);
    M = N;
    for (FUmHandCardModel& C : M.Cards) C.bSelected = false;
  }
  TestEqual(FString::Printf(TEXT("0 new widgets after the warm-up (%d)"), Warm), H->CreatedCount(), Warm);
  // the cost of a snapshot with 9 cards (alternating selections - real work every call)
  TArray<double> Costs;
  for (int32 I = 0; I < 200; ++I) {
    FUmHandModel N = M;
    N.Cards[I % N.Cards.Num()].bSelected = true;
    const double T0 = FPlatformTime::Seconds();
    H->ApplyModel(N);
    Costs.Add((FPlatformTime::Seconds() - T0) * 1000.0);
  }
  Costs.Sort();
  const double P95 = Costs[FMath::Clamp(FMath::CeilToInt(0.95 * Costs.Num()) - 1, 0, Costs.Num() - 1)];
  AddInfo(FString::Printf(TEXT("HUD-HAND budget applyModel9 p50=%.4f p95=%.4f max=%.4f ms"), Costs[Costs.Num() / 2], P95, Costs.Last()));
  TestTrue(FString::Printf(TEXT("ApplyModel 9 cards p95 %.4f ms <= 0.15"), P95), P95 <= 0.15);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHandPressTest,
    "Unmatched.S09.HudPress.UmgHand synthetic clicks on the hand's cards n 24, holds 0 and 3 frames, a snapshot in between, 0 lost",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHandPressTest::RunTest(const FString&) {
  using namespace UmHandTest;
  FWorld W(TEXT("UmHandPress"));
  TSharedPtr<FS09HudPressArbiter> Arbiter = MakeShared<FS09HudPressArbiter>();
  uint64 Frames = 5000;
  Arbiter->SetFrameClock([&Frames]() { return Frames; });
  UUmHudHand* H = Make(W.World, Frame(Canvases[2], false));
  if (!TestNotNull(TEXT("hand"), H)) return false;
  int32 Acts = 0, Refused = 0;
  TArray<FString> Ids;
  FName LastWhy;
  H->SetInput(Arbiter, [&](const FS09HudPressOutcome& O, const FString& Id) {
        if (O.Result == ES09HudPressResult::Act) {
          ++Acts;
          Ids.Add(Id);
        }
        if (O.Result == ES09HudPressResult::Refused) {
          ++Refused;
          LastWhy = O.Reason.Key;
        }
      },
      nullptr, nullptr);
  FUmHandModel M = Model(TestHand(7));
  H->ApplyModel(M);
  At(H, 500.0);
  const FGeometry Geo = FGeometry::MakeRoot(FVector2D(120.0, 166.0), FSlateLayoutTransform());
  const FVector2D Centre(60.0, 40.0);
  const int32 N = 24;
  for (int32 I = 0; I < N; ++I) {
    const int32 K = I % 7;
    UUmCardWidget* C = H->FindCard(M.Cards[K].Card.InstanceId);
    if (!C) continue;
    C->NativeOnMouseButtonDown(Geo, Left(Centre, true));
    const int32 Hold = (I % 2) ? 3 : 0;
    for (int32 Fr = 0; Fr < Hold; ++Fr) {
      ++Frames;
      // a snapshot lands while the card is held: another card selected, the pool keeps every widget
      FUmHandModel S = M;
      S.Cards[(K + 1) % 7].bSelected = true;
      H->ApplyModel(S);
    }
    C->NativeOnMouseButtonUp(Geo, Left(Centre, false));
    ++Frames;
  }
  TestEqual(TEXT("every click answered: 0 lost"), Acts, N);
  TestEqual(TEXT("no refusal"), Refused, 0);
  TestTrue(TEXT("each act names its card"), Ids.Num() == N && Ids[0] == M.Cards[0].Card.InstanceId && Ids[8] == M.Cards[1].Card.InstanceId);
  // an unplayable card with an exact why is refused with it (CUE-004), never silent
  FUmHandModel U = M;
  U.Cards[3].bPlayable = false;
  U.Cards[3].Reason = FS09Reason::Make(TEXT("why.boost.no.value"));
  H->ApplyModel(U);
  UUmCardWidget* C3 = H->FindCard(U.Cards[3].Card.InstanceId);
  for (int32 I = 0; I < N; ++I) {
    C3->NativeOnMouseButtonDown(Geo, Left(Centre, true));
    Frames += (I % 2) ? 3 : 0;
    C3->NativeOnMouseButtonUp(Geo, Left(Centre, false));
    ++Frames;
  }
  TestEqual(TEXT("unplayable with a why: refused every time"), Refused, N);
  TestTrue(TEXT("with its why"), LastWhy == FName(TEXT("why.boost.no.value")));
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
