// VS-2 automation tests of the UMG HUD root and the common widgets (docs/game-design/visual/06-tasks/hud.csv):
//   Unmatched.S08.Hud.Root.Tree     HB-06  BuildDefaultTree of UUmHudRoot and UUmGameHud: every BindWidget, nothing takes
//                                          the mouse, ApplyLayout places the slots, a -S08SlateHud block stays collapsed;
//                                          the generated WBPs (when present) are children of the C++ bases.
//   Unmatched.S08.Hud.Root.Layout   HB-06  FUmHudLayout: class L / S and the hand corridor at 1920x1080 100 %,
//                                          1280x720 100 % (1706.7 su), 1920x1080 150 % (1280x720 su) and 1280x720 150 %
//                                          (1137.8x640 su); the 04 §1.6 rects; FIELD of the real Marmoreal / Sarpedon
//                                          bench states through the K1 camera vs the 04 §1.6 measurement (+-15 px);
//                                          overlapField = 0 on both boards in every class; the toast / subtitle stack.
//   Unmatched.S08.Hud.Root.Flag     HB-06  -S08SlateHud: none / whole / block list, unknown keys, ARTLOOK hudImpl=.
//   Unmatched.S08.Hud.Button.Tree   HB-11  UUmButton BuildDefaultTree + WBP_UmButton.
//   Unmatched.S08.Hud.Button.States HB-11  6 states x 3 variants: skin, text colour (>= 4.5 : 1), disabled by colour not
//                                          opacity, motion (hover 1.06 / 150 ms, press 0.96 / 80 ms, pulse 1.1 -> 1.0 / 200
//                                          ms, reduced = colour only), why.* after 300 ms of hover.
//   Unmatched.S09.HudPress.Umg      HB-11  synthetic clicks on UUmButton through NativeOnMouseButtonDown / Up, n = 24,
//                                          holds 0 and 50 ms, a HUD rebuild between press and release: 0 lost; a
//                                          disabled / busy button answers Refused with its why.*.
//   Unmatched.S08.Hud.IconSize      HB-23  the export picked for su x DPI x UI scale (18 / 36 / 48 / 64), the widget path.
//   Unmatched.S08.Hud.Theme.Skins   HB-10  the 29 9-slice skins in DA_UmHudTheme: x1 + x2 textures, margins > 0, x2 at
//                                          >= 1.5 px per su.
// Headless: node tools/s08/run-ue-tests.cjs "Unmatched.S08.Hud+Unmatched.S09.HudPress.Umg" <abs log>
#if WITH_AUTOMATION_TESTS

#include "../S08ArtLook.h"
#include "../S08AnimatedIconWidget.h"
#include "../S08BoardArt.h"
#include "../S08BoardModel.h"
#include "../S08Contracts.h"
#include "../S08HudTokens.generated.h"
#include "../S08IconMotion.h"
#include "UmButton.h"
#include "UmGameHud.h"
#include "UmHudLayout.h"
#include "UmHudRoot.h"
#include "UmHudTheme.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/GridPanel.h"
#include "Components/Image.h"
#include "Components/SizeBox.h"
#include "Components/TextBlock.h"
#include "Components/WidgetSwitcher.h"
#include "Dom/JsonObject.h"
#include "Engine/Engine.h"
#include "Engine/Texture2D.h"
#include "Engine/World.h"
#include "Input/Events.h"
#include "InputCoreTypes.h"
#include "Layout/Geometry.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

// Named namespace (not anonymous): unity builds merge test files.
namespace UmHudTest {
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

bool Near(double A, double B, double Tol = 0.51) { return FMath::Abs(A - B) <= Tol; }

FString BoxText(const FBox2D& B) {
  return B.bIsValid ? FString::Printf(TEXT("(%.2f,%.2f,%.2f,%.2f)"), B.Min.X, B.Min.Y, B.Max.X - B.Min.X, B.Max.Y - B.Min.Y)
                    : FString(TEXT("none"));
}

bool RectIs(FAutomationTestBase& T, const FUmHudLayout& L, EUmHudBlock B, float X, float Y, float W, float H,
            const FString& What) {
  const FBox2D& R = L.Rect(B);
  const bool bOk = R.bIsValid && Near(R.Min.X, X) && Near(R.Min.Y, Y) && Near(R.Max.X - R.Min.X, W) &&
                   Near(R.Max.Y - R.Min.Y, H);
  T.TestTrue(FString::Printf(TEXT("%s %s = (%.0f,%.0f,%.0f,%.0f), got %s"), *What, UmHudLayout::BlockName(B), X, Y, W, H,
                             *BoxText(R)),
             bOk);
  return bOk;
}

/** sRGB relative luminance contrast of two theme colours (alpha ignored: the bodies are opaque). */
double Contrast(const FLinearColor& A, const FLinearColor& B) {
  auto Lum = [](const FLinearColor& C) { return 0.2126 * C.R + 0.7152 * C.G + 0.0722 * C.B; };  // linear = WCAG
  const double La = Lum(A) + 0.05;
  const double Lb = Lum(B) + 0.05;
  return La > Lb ? La / Lb : Lb / La;
}

/** A Config/Bench game state (the -Bench fixture): board + fighters. */
bool LoadBenchBoard(const TCHAR* File, FS08BoardModel& OutBoard) {
  FString Text;
  if (!FFileHelper::LoadFileToString(Text, *FPaths::Combine(FPaths::ProjectConfigDir(), TEXT("Bench"), File))) return false;
  TSharedPtr<FJsonObject> Root;
  FString Problem;
  if (!FS08Contracts::TryParseJsonObject(Text, Root, Problem) || !Root.IsValid()) return false;
  FString Body;
  const TSharedPtr<FJsonObject>* Raw = nullptr;
  if (!Root->TryGetStringField(TEXT("raw"), Body)) {
    if (!Root->TryGetObjectField(TEXT("raw"), Raw) || !Raw->IsValid()) return false;
    const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Body);
    FJsonSerializer::Serialize(Raw->ToSharedRef(), Writer);
  }
  FS08Snapshot Snapshot;
  FString RawState;
  FS08GraphQLError Error;
  return FS08Contracts::ParseGameStateQuery(Body, Snapshot, RawState, Error) && OutBoard.Decode(Snapshot.BoardState);
}

/** FIELD (px) of a board at the K1 overview of SetupCameraForBoard (the map canvas fit x 1.25) on a window. */
FBox2D BoardFieldPx(const FS08BoardModel& Board, const FVector2D& WindowPx) {
  const FVector2D Half = S08BoardHalfExtentUU(Board);
  const float Distance = S08K1OverviewDistanceUU(S08K1FitDistanceUU(Half), 1.25f);
  const float Pitch = FMath::DegreesToRadians(55.0f);
  UmHudField::FView View;
  View.Location = FVector(0.0, Distance * FMath::Cos(Pitch), Distance * FMath::Sin(Pitch));
  View.Rotation = FRotator(-55.0f, -90.0f, 0.0f);
  View.HFovDeg = 35.0f;
  View.ViewportPx = WindowPx;
  TArray<FVector> Centres;
  for (int32 Y = 0; Y < Board.Height; ++Y) {
    for (int32 X = 0; X < Board.Width; ++X) {
      if (Board.IsBoardSpace(X, Y)) Centres.Add(Board.CellToWorld(X, Y));
    }
  }
  return UmHudField::CellsEnvelopePx(View, Centres, Board.LayoutFrame.SpaceRadiusUU());
}

FPointerEvent LeftEvent(const FVector2D& At, bool bDown) {
  TSet<FKey> Pressed;
  if (bDown) Pressed.Add(EKeys::LeftMouseButton);
  return FPointerEvent(0, At, At, Pressed, EKeys::LeftMouseButton, 0.0f, FModifierKeysState());
}
}  // namespace UmHudTest

// ------------------------------------------------------------------------------------------------ HB-06 root

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHudRootTreeTest,
    "Unmatched.S08.Hud.Root.Tree UUmHudRoot / UUmGameHud default trees, every BindWidget, no hit test, layout placement",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHudRootTreeTest::RunTest(const FString&) {
  using namespace UmHudTest;
  FWorld W(TEXT("UmHudRootTree"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  UUmHudRoot* Root = CreateWidget<UUmHudRoot>(W.World, UUmHudRoot::StaticClass());
  if (!TestNotNull(TEXT("root"), Root)) return false;
  FString Missing;
  TestTrue(TEXT("root: code default tree"), Root->UsesCodeDefaultTree());
  TestTrue(FString::Printf(TEXT("root: Screens, Modals, Reconnect bound (missing %s)"), *Missing), Root->HasAllParts(&Missing));
  TestTrue(TEXT("root takes no mouse"), Root->GetVisibility() == ESlateVisibility::SelfHitTestInvisible);
  UUmGameHud* Game = Root->EnsureGameHud();
  if (!TestNotNull(TEXT("GAME screen"), Game)) return false;
  TestTrue(TEXT("GAME is the active screen"), Root->Screens && Root->Screens->GetActiveWidget() == Game);
  TestTrue(TEXT("the same GAME screen on the second call"), Root->EnsureGameHud() == Game);
  TestTrue(FString::Printf(TEXT("GAME: Canvas + 18 slots bound (missing %s)"), *Missing), Game->HasAllParts(&Missing));
  TestEqual(TEXT("18 slots (04 §4.2)"), UmGameSlotCount, 18);
  for (int32 I = 0; I < UmGameSlotCount; ++I) {
    const EUmGameSlot Slot = static_cast<EUmGameSlot>(I);
    USizeBox* Box = Game->GetSlot(Slot);
    if (!TestNotNull(FString::Printf(TEXT("slot %s"), UmGameHudSlots::SlotName(Slot)), Box)) continue;
    TestTrue(FString::Printf(TEXT("empty slot %s takes no mouse"), UmGameHudSlots::SlotName(Slot)), Box->GetVisibility() == ESlateVisibility::HitTestInvisible);
  }
  // ApplyLayout: the slots at the 04 §1.6 rects; a -S08SlateHud block collapsed; LOG has no rect in S
  const FUmHudLayout L = FUmHudLayout::Compute(FVector2D(1920.0, 1080.0), 1.0f, nullptr);
  Game->ApplyLayout(L, {FName(TEXT("hand"))});
  auto SlotAt = [&](EUmGameSlot Slot, float X, float Y, float W2, float H) {
    USizeBox* Box = Game->GetSlot(Slot);
    const UCanvasPanelSlot* CS = Box ? Cast<UCanvasPanelSlot>(Box->Slot) : nullptr;
    const bool bOk = CS && Near(CS->GetPosition().X, X) && Near(CS->GetPosition().Y, Y) && Near(CS->GetSize().X, W2) &&
                     Near(CS->GetSize().Y, H);
    TestTrue(FString::Printf(TEXT("slot %s at (%.0f,%.0f,%.0f,%.0f)"), UmGameHudSlots::SlotName(Slot), X, Y, W2, H), bOk);
  };
  SlotAt(EUmGameSlot::Top, 24.0f, 24.0f, 252.0f, 44.0f);
  SlotAt(EUmGameSlot::PanelOpp, 1556.0f, 24.0f, 340.0f, 136.0f);
  SlotAt(EUmGameSlot::Actions, 1552.0f, 984.0f, 344.0f, 72.0f);
  SlotAt(EUmGameSlot::Decks, 1608.0f, 920.0f, 288.0f, 56.0f);
  TestTrue(TEXT("-S08SlateHud=hand: the hand slot stays collapsed"), Game->GetSlot(EUmGameSlot::Hand)->GetVisibility() == ESlateVisibility::Collapsed);
  const FUmHudLayout S = FUmHudLayout::Compute(FVector2D(1280.0, 720.0), 1.5f, nullptr);
  Game->ApplyLayout(S, {});
  TestTrue(TEXT("class S: no LOG column (ВР-H07)"), Game->GetSlot(EUmGameSlot::Log)->GetVisibility() == ESlateVisibility::Collapsed);
  TestTrue(TEXT("class S: the hand slot back"), Game->GetSlot(EUmGameSlot::Hand)->GetVisibility() == ESlateVisibility::HitTestInvisible);
  Game->ApplyLayout(S, {}, /*bAllSlate=*/true);
  TestTrue(TEXT("whole Slate: every slot collapsed"), Game->GetSlot(EUmGameSlot::Top)->GetVisibility() == ESlateVisibility::Collapsed);
  TArray<FString> Lines;
  Game->SetScreenState(TEXT("combat"));
  Game->CollectShotLines(Lines, FIntPoint(1920, 1080));
  TestTrue(TEXT("SHOT widget id=UI-SCR-GAME line"),
           Lines.Num() == 1 && Lines[0].StartsWith(TEXT("SHOT widget id=UI-SCR-GAME impl=umg state=combat fighter=none "
                                                       "bbox=0,0,1920,1080 geom=painted")));
  // the generated WBPs are children of the bases (tools/s08/hud_contract/ue_author_um_hud.py)
  const TPair<const TCHAR*, UClass*> Wbps[] = {{UUmHudRoot::WidgetBlueprintPath, UUmHudRoot::StaticClass()},
                                              {UUmGameHud::WidgetBlueprintPath, UUmGameHud::StaticClass()},
                                              {UUmButton::WidgetBlueprintPath, UUmButton::StaticClass()}};
  for (const auto& P : Wbps) {
    const FString Package(P.Key);
    if (!FPackageName::DoesPackageExist(Package)) {
      AddWarning(FString::Printf(TEXT("%s not authored yet (ue_author_um_hud.py) - the code default tree is used"), P.Key));
      continue;
    }
    UClass* Class = LoadClass<UUserWidget>(nullptr, *(Package + TEXT(".") + FPackageName::GetShortName(Package) + TEXT("_C")));
    TestTrue(FString::Printf(TEXT("%s is a child of %s"), P.Key, *P.Value->GetName()), Class && Class->IsChildOf(P.Value));
    if (Class && Class->IsChildOf(UUmHudRoot::StaticClass())) {
      UUmHudRoot* FromWbp = CreateWidget<UUmHudRoot>(W.World, Class);
      TestTrue(TEXT("WBP_UmHudRoot: every part bound"), FromWbp && FromWbp->HasAllParts(&Missing));
    }
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHudRootLayoutTest,
    "Unmatched.S08.Hud.Root.Layout class L or S, hand corridor at four canvases, 04 rects, FIELD of both boards, overlap 0",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHudRootLayoutTest::RunTest(const FString&) {
  using namespace UmHudTest;
  // ---- the four canvases of the card (window / (DPI x UI scale)) ----
  struct FCase {
    const TCHAR* Name;
    FVector2D Window;
    float PxPerSu;
    bool bS;
    float HandLeft;
    float HandRight;
  };
  const FCase Cases[] = {
      {TEXT("1920x1080 100 %"), FVector2D(1920.0, 1080.0), 1.0f, false, 376.0f, 1540.0f},
      {TEXT("1280x720 100 % (1706.7x960 su)"), FVector2D(1280.0, 720.0), 0.75f, false, 376.0f, 1326.67f},
      {TEXT("1920x1080 150 % (1280x720 su)"), FVector2D(1920.0, 1080.0), 1.5f, true, 268.0f, 1040.0f},
      {TEXT("1280x720 150 % (1137.8x640 su)"), FVector2D(1280.0, 720.0), 1.125f, true, 268.0f, 897.78f},
  };
  for (const FCase& C : Cases) {
    const FUmHudLayout L = FUmHudLayout::Compute(C.Window / C.PxPerSu, C.PxPerSu, nullptr);
    TestTrue(FString::Printf(TEXT("%s: class %s"), C.Name, C.bS ? TEXT("S") : TEXT("L")), L.bClassS == C.bS);
    TestTrue(FString::Printf(TEXT("%s: hand corridor %.2f..%.2f = %.2f..%.2f"), C.Name, L.HandLeftSu, L.HandRightSu,
                             C.HandLeft, C.HandRight),
             Near(L.HandLeftSu, C.HandLeft, 0.02) && Near(L.HandRightSu, C.HandRight, 0.02));
    TestEqual(FString::Printf(TEXT("%s: margin"), C.Name), L.MarginSu, C.bS ? 16.0f : 24.0f);
    // the buttons keep 32 su from the edge (04 §1): ACTIONS
    const FBox2D& A = L.Rect(EUmHudBlock::Actions);
    TestTrue(FString::Printf(TEXT("%s: ACTIONS inside the canvas"), C.Name),
             A.Min.X >= 0.0 && A.Max.X <= L.CanvasSu.X + 0.01 && A.Max.Y <= L.CanvasSu.Y + 0.01);
  }
  // ---- 04 §1.6 rects: L 1080p, L 720p (the "720p" column), S 1280x720 su ----
  {
    const FUmHudLayout L = FUmHudLayout::Compute(FVector2D(1920.0, 1080.0), 1.0f, nullptr);
    const FString W = TEXT("1080p");
    RectIs(*this, L, EUmHudBlock::Top, 24, 24, 252, 44, W);
    RectIs(*this, L, EUmHudBlock::Status, 520, 24, 880, 48, W);
    RectIs(*this, L, EUmHudBlock::Banner, 750, 144, 420, 64, W);
    RectIs(*this, L, EUmHudBlock::SourceSlot, 24, 84, 190, 264, W);
    // VS-3 HB-30 / HB-31 (HB-29 delta 04): the own ribbon with the timer row (56 su), the buttons under it at x 32
    RectIs(*this, L, EUmHudBlock::CombatL, 24, 360, 230, 379, W);
    RectIs(*this, L, EUmHudBlock::CombatR, 1666, 360, 230, 351, W);
    RectIs(*this, L, EUmHudBlock::Defend, 32, 747, 230, 104, W);
    RectIs(*this, L, EUmHudBlock::Log, 24, 712, 300, 200, W);
    RectIs(*this, L, EUmHudBlock::PanelLoc, 24, 920, 340, 136, W);
    RectIs(*this, L, EUmHudBlock::PanelOpp, 1556, 24, 340, 136, W);
    RectIs(*this, L, EUmHudBlock::OppHand, 1596, 168, 300, 92, W);
    RectIs(*this, L, EUmHudBlock::Decks, 1608, 920, 288, 56, W);
    // VS-3 HB-28 (HB-26 delta 04): the top under OPP-HAND + 8, the bottom over DECKS - 8
    RectIs(*this, L, EUmHudBlock::DeckPanel, 1516, 268, 380, 644, W);
    RectIs(*this, L, EUmHudBlock::Actions, 1552, 984, 344, 72, W);
    // VS-3 HB-27 (ВР-VS2-HB26-09): the RU chips 156 / 124 su, the EN chips 144 / 136 su
    const FVector2D Deck = L.DeckChipCentreSu();
    const FVector2D Discard = L.DiscardChipCentreSu();
    TestTrue(FString::Printf(TEXT("1080p: card flights end on the deck / discard chips (%.1f,%.1f) (%.1f,%.1f)"), Deck.X, Deck.Y,
                             Discard.X, Discard.Y),
             Near(Deck.X, 1686.0) && Near(Deck.Y, 948.0) && Near(Discard.X, 1834.0) && Near(Discard.Y, 948.0));
    const FBox2D En1 = UmHudLayout::DeckChipRect(L.Rect(EUmHudBlock::Decks), false, true, 1);
    TestTrue(TEXT("1080p: the EN discard chip 1760..1896"), Near(En1.Min.X, 1760.0) && Near(En1.Max.X, 1896.0));
    TestEqual(TEXT("1080p: the deck panel covers no block shown with it"), L.DeckPanelBlocksPx2, 0.0);
  }
  {
    const FUmHudLayout L = FUmHudLayout::Compute(FVector2D(1280.0, 720.0) / 0.75f, 0.75f, nullptr);
    const FString W = TEXT("720p");
    TestFalse(TEXT("720p: the 720p column (not tall)"), L.bTall);
    RectIs(*this, L, EUmHudBlock::Status, 0.5f * (1706.667f - 720.0f), 24, 720, 48, W);
    RectIs(*this, L, EUmHudBlock::CombatR, 1452.67f, 360, 230, 351, W);
    RectIs(*this, L, EUmHudBlock::Defend, 32, 112, 230, 104, W);  // HB-29: at the top left (PANEL-LOC from y 800)
    RectIs(*this, L, EUmHudBlock::Log, 24, 688, 300, 104, W);
    RectIs(*this, L, EUmHudBlock::PanelLoc, 24, 800, 340, 136, W);
    RectIs(*this, L, EUmHudBlock::PanelOpp, 1342.67f, 24, 340, 136, W);
    RectIs(*this, L, EUmHudBlock::Decks, 1394.67f, 800, 288, 56, W);
    RectIs(*this, L, EUmHudBlock::DeckPanel, 1346.67f, 268, 336, 524, W);  // ВР-VS2-HB26-08: 336 su
    TestEqual(TEXT("720p: the deck panel covers no block shown with it"), L.DeckPanelBlocksPx2, 0.0);
    RectIs(*this, L, EUmHudBlock::Actions, 1338.67f, 864, 344, 72, W);
  }
  {
    const FUmHudLayout L = FUmHudLayout::Compute(FVector2D(1280.0, 720.0), 1.5f, nullptr);
    const FString W = TEXT("S 1280x720 su");
    RectIs(*this, L, EUmHudBlock::Top, 16, 16, 236, 40, W);
    RectIs(*this, L, EUmHudBlock::PanelLoc, 16, 608, 240, 96, W);
    RectIs(*this, L, EUmHudBlock::PanelOpp, 1024, 16, 240, 96, W);
    RectIs(*this, L, EUmHudBlock::SourceSlot, 16, 64, 120, 166, W);
    RectIs(*this, L, EUmHudBlock::CombatL, 16, 240, 150, 280, W);  // HB-29: ribbon 40 + the timer row 28
    RectIs(*this, L, EUmHudBlock::CombatR, 1114, 240, 150, 252, W);
    RectIs(*this, L, EUmHudBlock::Defend, 32, 112, 150, 88, W);
    RectIs(*this, L, EUmHudBlock::Decks, 1128, 600, 136, 48, W);
    RectIs(*this, L, EUmHudBlock::Actions, 1048, 656, 216, 48, W);
    RectIs(*this, L, EUmHudBlock::DeckPanel, 964, 120, 300, 472, W);  // HB-26: PANEL-OPP bottom + 8
    // VS-2 open item 3: STATUS (two lines, 78 su) and the panel never meet; OPP-HAND is the transient overlap
    TestEqual(TEXT("S: the deck panel covers no block shown with it (STATUS two lines included)"), L.DeckPanelBlocksPx2, 0.0);
    TestTrue(TEXT("S: the read-only panel over OPP-HAND is measured"), L.DeckPanelTransientPx2 > 0.0);
    TestTrue(TEXT("S: the HUD-LAYOUT line carries the deck panel gate"),
             L.TraceLine().Contains(TEXT("deckpanel=(964.0,120,300,472) deckpanelBlocks=0")));
    const FUmHudLayout S720 = FUmHudLayout::Compute(FVector2D(1280.0 / 1.125, 640.0), 1.125f, nullptr);
    RectIs(*this, S720, EUmHudBlock::DeckPanel, 821.78f, 120, 300, 392, TEXT("S 1138x640 su"));
    TestEqual(TEXT("720p 150 %: STATUS at two lines stays over the deck panel header"), S720.DeckPanelBlocksPx2, 0.0);
    RectIs(*this, L, EUmHudBlock::Status, 340, 16, 600, 48, W);  // VS-2 HB-15: one-line capsule 48 su
    RectIs(*this, L, EUmHudBlock::Banner, 430, 72, 420, 64, W);  // VS-2 HB-16 (ВР-VS2-45): under STATUS
    TestFalse(TEXT("S: no LOG rect"), L.HasRect(EUmHudBlock::Log));
  }
  // ---- FIELD: the real bench states through the K1 camera vs the 04 §1.6 measurement (+-15 px at 1080p) ----
  struct FBoard {
    const TCHAR* Name;
    const TCHAR* Fixture;
    FBox2D Measured;
  };
  // ВР-VS2-09: the cells' envelope on the K1 bench frames (overlaid 2026-10-06: Marmoreal ENV-MAPS p7 concept-flag,
  // Sarpedon p10 packaged) - the 04 §1.6 hand measurement (410,255)-(1440,850) / (380,250)-(1490,860) is off by 56 px
  // at the left of Marmoreal and 51 px at the right of Sarpedon (it ends inside the purple / red cells).
  const FBoard Boards[] = {
      {TEXT("Marmoreal original"), TEXT("S08BenchMarmoreal.json"), FBox2D(FVector2D(466.0, 258.0), FVector2D(1461.0, 857.0))},
      {TEXT("Sarpedon original"), TEXT("S08BenchSarpedon.json"), FBox2D(FVector2D(377.0, 258.0), FVector2D(1541.0, 866.0))},
  };
  for (const FBoard& B : Boards) {
    FS08BoardModel Board;
    if (!TestTrue(FString::Printf(TEXT("%s: bench state"), B.Name), LoadBenchBoard(B.Fixture, Board))) continue;
    TestTrue(FString::Printf(TEXT("%s: a topology board"), B.Name), Board.bHasTopology);
    const FBox2D Px = BoardFieldPx(Board, FVector2D(1920.0, 1080.0));
    AddInfo(FString::Printf(TEXT("%s FIELD 1080p = (%.1f,%.1f)-(%.1f,%.1f), measured (%.0f,%.0f)-(%.0f,%.0f)"), B.Name,
                            Px.Min.X, Px.Min.Y, Px.Max.X, Px.Max.Y, B.Measured.Min.X, B.Measured.Min.Y, B.Measured.Max.X,
                            B.Measured.Max.Y));
    TestTrue(FString::Printf(TEXT("%s: FIELD within 15 px of the frame (ВР-VS2-09)"), B.Name),
             Px.bIsValid && Near(Px.Min.X, B.Measured.Min.X, 15.0) && Near(Px.Min.Y, B.Measured.Min.Y, 15.0) &&
                 Near(Px.Max.X, B.Measured.Max.X, 15.0) && Near(Px.Max.Y, B.Measured.Max.Y, 15.0));
    // the same FIELD scales with the window (720p): the projection is resolution-free in NDC
    const FBox2D Px720 = BoardFieldPx(Board, FVector2D(1280.0, 720.0));
    TestTrue(FString::Printf(TEXT("%s: FIELD at 720p = 2/3 of 1080p"), B.Name),
             Near(Px720.Min.X, Px.Min.X * 2.0 / 3.0, 0.01) && Near(Px720.Max.Y, Px.Max.Y * 2.0 / 3.0, 0.01));
    for (const FCase& C : Cases) {
      const FBox2D Win = BoardFieldPx(Board, C.Window);
      const FBox2D Su(Win.Min / C.PxPerSu, Win.Max / C.PxPerSu);
      const FUmHudLayout L = FUmHudLayout::Compute(C.Window / C.PxPerSu, C.PxPerSu, &Su);
      TestTrue(FString::Printf(TEXT("%s %s: overlapField %.0f = 0 (%s)"), B.Name, C.Name, L.OverlapFieldPx2,
                               *L.TraceLine()),
               L.OverlapFieldPx2 <= 0.0);
      TestTrue(FString::Printf(TEXT("%s %s: hand visible %.0f su in 48..208"), B.Name, C.Name, L.HandVisibleSu),
               L.HandVisibleSu >= 48.0f && L.HandVisibleSu <= 208.0f);
      TestTrue(FString::Printf(TEXT("%s %s: the hand caption starts under FIELD"), B.Name, C.Name),
               L.Rect(EUmHudBlock::HandCaption).Min.Y >= Su.Max.Y);
      // VS-2 HB-16 (ВР-VS2-45): the banner crosses neither the cells nor the one-line STATUS in any class
      const FBox2D Banner = L.Rect(EUmHudBlock::Banner);
      TestTrue(FString::Printf(TEXT("%s %s: banner y %.0f..%.0f over FIELD %.1f, under STATUS %.0f"), B.Name, C.Name,
                               Banner.Min.Y, Banner.Max.Y, Su.Min.Y, L.Rect(EUmHudBlock::Status).Max.Y),
               Banner.Max.Y <= Su.Min.Y && Banner.Min.Y >= L.Rect(EUmHudBlock::Status).Max.Y);
    }
  }
  // ---- the measured FIELD itself (04 §1.6) in the layout: overlap 0, hand 200 su on Marmoreal 1080p ----
  {
    const FBox2D Field(FVector2D(410.0, 255.0), FVector2D(1440.0, 850.0));
    const FUmHudLayout L = FUmHudLayout::Compute(FVector2D(1920.0, 1080.0), 1.0f, &Field);
    TestEqual(TEXT("Marmoreal measured: overlapField 0"), L.OverlapFieldPx2, 0.0);
    TestEqual(TEXT("Marmoreal measured: the hand shows 1080 - 880 = 200 su"), L.HandVisibleSu, 200.0f);
    TestTrue(TEXT("HUD-LAYOUT line"), L.TraceLine(FIntPoint(1920, 1080)).StartsWith(
                                          TEXT("HUD-LAYOUT class=L canvas=1920x1080 scale=1.000 field=(410,255,1030,595) "
                                               "overlapField=0 window=1920x1080")));
    // ВР-H06: the stack over the hand; a figure under it sends the whole stack to the top strip (y 216)
    bool bTop = true;
    const FBox2D Sub = L.StackRect(EUmHudBlock::Sub, 400.0f, 48.0f, 500.0f, 40.0f, {}, bTop);
    const FBox2D Toast = L.StackRect(EUmHudBlock::Toast, 400.0f, 48.0f, 500.0f, 40.0f, {}, bTop);
    TestFalse(TEXT("stack: bottom without figures"), bTop);
    TestTrue(TEXT("stack: the subtitle right over the hand caption"),
             Near(Sub.Max.Y, L.Rect(EUmHudBlock::HandCaption).Min.Y - 8.0) && Near(Sub.Min.X, 710.0));
    TestTrue(TEXT("stack: the toasts over the subtitle"), Near(Toast.Max.Y, Sub.Min.Y - 8.0));
    const TArray<FBox2D> Figure = {FBox2D(FVector2D(900.0, Sub.Min.Y + 4.0), FVector2D(960.0, Sub.Min.Y + 60.0))};
    const FBox2D SubTop = L.StackRect(EUmHudBlock::Sub, 400.0f, 48.0f, 500.0f, 40.0f, Figure, bTop);
    const FBox2D ToastTop = L.StackRect(EUmHudBlock::Toast, 400.0f, 48.0f, 500.0f, 40.0f, Figure, bTop);
    TestTrue(TEXT("stack: a figure under the subtitle -> the top strip"), bTop);
    TestTrue(TEXT("stack top: toasts at y 216, the subtitle under them"),
             Near(ToastTop.Min.Y, 216.0) && Near(SubTop.Min.Y, 216.0 + 48.0 + 8.0));
    const FBox2D SubHigh = L.StackRect(EUmHudBlock::Sub, 0.0f, 0.0f, 500.0f, 40.0f, {}, bTop, 700.0f);
    TestTrue(TEXT("stack: over a taller Slate hand panel (top 700)"), Near(SubHigh.Max.Y, 692.0));
    TestTrue(TEXT("edge room: 410 - 8 - 24 = 378 left, 1920 - 24 - 1448 = 448 right"),
             Near(L.EdgeRoomSu(true), 378.0) && Near(L.EdgeRoomSu(false), 448.0));
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHudRootFlagTest,
    "Unmatched.S08.Hud.Root.Flag -S08SlateHud none / whole / block list, unknown keys, ARTLOOK hudImpl",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHudRootFlagTest::RunTest(const FString&) {
  using namespace S08ArtLook;
  const FS08SlateHudBlocks None = ParseSlateHud(TEXT("-Bench -S09Markers"));
  TestTrue(TEXT("no flag: the UMG root, nothing on Slate"), None.UmgRoot() && !None.bAll && None.Blocks.Num() == 0);
  TestEqual(TEXT("no flag: hudImpl=umg"), None.ImplField(), FString(TEXT("umg")));
  TestFalse(TEXT("no flag: hand is UMG"), None.IsSlate(TEXT("hand")));
  const FS08SlateHudBlocks All = ParseSlateHud(TEXT("-Bench -S08SlateHud -S09Markers"));
  TestTrue(TEXT("-S08SlateHud: the whole HUD"), All.bAll && !All.UmgRoot() && All.IsSlate(TEXT("top")));
  TestEqual(TEXT("-S08SlateHud: hudImpl=slate"), All.ImplField(), FString(TEXT("slate")));
  const FS08SlateHudBlocks Empty = ParseSlateHud(TEXT("-S08SlateHud= -Bench"));
  TestTrue(TEXT("-S08SlateHud= (empty): the whole HUD"), Empty.bAll);
  const FS08SlateHudBlocks List = ParseSlateHud(TEXT("-ArtPreview -S08SlateHud=Hand, decks,hand,banner -S09Markers"));
  TestTrue(TEXT("list: the root stays"), List.UmgRoot() && !List.bAll);
  TestEqual(TEXT("list: lower case, no duplicates, in order"), List.ImplField(), FString(TEXT("slate:hand")));
  const FS08SlateHudBlocks List2 = ParseSlateHud(TEXT("-S08SlateHud=hand,decks,banner"));
  TestEqual(TEXT("list: hudImpl=slate:hand,decks,banner"), List2.ImplField(), FString(TEXT("slate:hand,decks,banner")));
  TestTrue(TEXT("list: hand / decks / banner on Slate, top on UMG"),
           List2.IsSlate(TEXT("hand")) && List2.IsSlate(TEXT("decks")) && List2.IsSlate(TEXT("banner")) &&
               !List2.IsSlate(TEXT("top")));
  const FS08SlateHudBlocks World = ParseSlateHud(TEXT("-S08SlateHud=tag,plate,damage,inspect,mystery"));
  TestTrue(TEXT("world layer and screen keys known, one unknown kept"),
           World.Unknown.Num() == 1 && World.Unknown[0] == FName(TEXT("mystery")) && World.IsSlate(TEXT("mystery")));
  TestFalse(TEXT("-S08SlateHudX is another flag"), ParseSlateHud(TEXT("-S08SlateHudX")).bAll);
  // VS-3: + combatcenter (ВР-VS3-50) and the SC-01 screen keys boot ... aborted (ВР-SC04)
  TestEqual(TEXT("31 known keys (04 §4.2 + combatcenter + the screens of ВР-SC04)"), static_cast<int32>(UE_ARRAY_COUNT(SlateHudKeys)), 31);
  SetSlateHudOverrideForTest(TEXT("hand,toast"));
  TestTrue(TEXT("override: ARTLOOK hudImpl=slate:hand,toast"), TraceLine().Contains(TEXT(" hudImpl=slate:hand,toast")));
  SetSlateHudOverrideForTest(TEXT("*"));
  TestTrue(TEXT("override: ARTLOOK hudImpl=slate"), TraceLine().Contains(TEXT(" hudImpl=slate")));
  ResetSlateHudOverrideForTest();
  return true;
}

// ------------------------------------------------------------------------------------------------ HB-11 button

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHudButtonTreeTest,
    "Unmatched.S08.Hud.Button.Tree UUmButton default tree: Box, Body, Content, Icon, Label, KeyChip, FocusRing",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHudButtonTreeTest::RunTest(const FString&) {
  using namespace UmHudTest;
  FWorld W(TEXT("UmHudButtonTree"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  UUmButton* Button = CreateWidget<UUmButton>(W.World, UUmButton::StaticClass());
  if (!TestNotNull(TEXT("button"), Button)) return false;
  FString Missing;
  TestTrue(TEXT("code default tree"), Button->UsesCodeDefaultTree());
  TestTrue(FString::Printf(TEXT("every part bound (missing %s)"), *Missing), Button->HasAllParts(&Missing));
  TestFalse(TEXT("never takes the keyboard (HUD-RULES П7)"), Button->NativeSupportsKeyboardFocus());
  TestTrue(TEXT("the label does not take the press"), Button->Content->GetVisibility() == ESlateVisibility::HitTestInvisible);
  const FString Package(UUmButton::WidgetBlueprintPath);
  if (FPackageName::DoesPackageExist(Package)) {
    UClass* Class = LoadClass<UUmButton>(nullptr, *(Package + TEXT(".") + FPackageName::GetShortName(Package) + TEXT("_C")));
    UUmButton* FromWbp = Class ? CreateWidget<UUmButton>(W.World, Class) : nullptr;
    TestTrue(TEXT("WBP_UmButton: a UUmButton with every part"), FromWbp && FromWbp->HasAllParts(&Missing));
  } else {
    AddWarning(TEXT("WBP_UmButton not authored yet (ue_author_um_hud.py)"));
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHudButtonStatesTest,
    "Unmatched.S08.Hud.Button.States 6 states x 3 variants: skin, text contrast, motion, reduced motion, why after 300 ms",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHudButtonStatesTest::RunTest(const FString&) {
  using namespace UmHudTest;
  FWorld W(TEXT("UmHudButtonStates"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  double Clock = 100.0;
  const EUmButtonState States[] = {EUmButtonState::Normal,   EUmButtonState::Hover, EUmButtonState::Pressed,
                                   EUmButtonState::Disabled, EUmButtonState::Focus, EUmButtonState::Selected};
  const EUmButtonVariant Variants[] = {EUmButtonVariant::Normal, EUmButtonVariant::Primary, EUmButtonVariant::Disc};
  // the body colour of each look (02 §4.3; the primary hover / pressed / disabled bodies are the HB-08 derived colours
  // of the accepted package, read from its verification.json palette - ВР-VS2-HB08-01 / -02)
  TMap<FString, FLinearColor> Derived;
  {
    FString Text;
    const FString Path = FPaths::ConvertRelativePathToFull(
        FPaths::Combine(FPaths::ProjectDir(), TEXT("../../art/imagegen/hud-skins-v1-codex/verification.json")));
    TSharedPtr<FJsonObject> Root;
    const TSharedPtr<FJsonObject>* Palette = nullptr;
    const TSharedPtr<FJsonObject>* Tokens = nullptr;
    if (FFileHelper::LoadFileToString(Text, *Path) &&
        FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) && Root.IsValid() &&
        Root->TryGetObjectField(TEXT("palette"), Palette) && (*Palette)->TryGetObjectField(TEXT("tokens"), Tokens)) {
      for (const TCHAR* Key : {TEXT("primary.hover"), TEXT("primary.pressed"), TEXT("primary.disabled")}) {
        FString Hex;
        if ((*Tokens)->TryGetStringField(Key, Hex)) Derived.Add(Key, FLinearColor::FromSRGBColor(FColor::FromHex(Hex)));
      }
    }
    TestEqual(TEXT("HB-08 derived primary colours read"), Derived.Num(), 3);
  }
  auto BodyColor = [&Theme, &Derived](EUmButtonVariant V, EUmButtonState S) -> FLinearColor {
    if (V == EUmButtonVariant::Primary) {
      const TCHAR* Key = S == EUmButtonState::Hover      ? TEXT("primary.hover")
                         : S == EUmButtonState::Pressed  ? TEXT("primary.pressed")
                         : S == EUmButtonState::Disabled ? TEXT("primary.disabled")
                                                         : nullptr;
      if (Key && Derived.Contains(Key)) return Derived[Key];
      return Theme.Color(TEXT("turn.flash.yellow"));
    }
    const FName Under = UmButton::DiscUnderlayToken(S);
    if (V == EUmButtonVariant::Disc) return Under.IsNone() ? Theme.Color(TEXT("panel.bg")) : Theme.Color(Under);
    switch (S) {
      case EUmButtonState::Hover: return Theme.Color(TEXT("panel.bg.hover"));
      case EUmButtonState::Pressed: return Theme.Color(TEXT("panel.bg.pressed"));
      case EUmButtonState::Selected: return Theme.Color(TEXT("state.pending"));
      default: return Theme.Color(TEXT("panel.bg"));
    }
  };
  for (const EUmButtonVariant V : Variants) {
    for (const EUmButtonState S : States) {
      UUmButton* B = CreateWidget<UUmButton>(W.World, UUmButton::StaticClass());
      if (!B) continue;
      B->SetClockForTest([&Clock]() { return Clock; });
      FUmButtonModel M;
      M.Variant = V;
      M.Label = FText::FromString(TEXT("Конец хода"));
      M.IconName = V == EUmButtonVariant::Disc ? FName(TEXT("action-maneuver")) : NAME_None;
      M.bEnabled = S != EUmButtonState::Disabled;
      M.Reason = S == EUmButtonState::Disabled ? FS09Reason::Make(TEXT("why.not.your.turn")) : FS09Reason();
      M.bSelected = S == EUmButtonState::Selected;
      M.bFocused = S == EUmButtonState::Focus;
      B->ApplyModel(M);
      B->SetPreviewPointer(S == EUmButtonState::Hover, S == EUmButtonState::Pressed);
      const EUmButtonState Want = V == EUmButtonVariant::Primary && S == EUmButtonState::Selected ? EUmButtonState::Normal : S;
      const FString What = FString::Printf(TEXT("%s.%s"), UmButtonVariantName(V), UmButtonStateName(S));
      TestEqual(What + TEXT(": state"), FString(UmButtonStateName(B->GetState())), FString(UmButtonStateName(Want)));
      const FName Skin = UmButton::SkinKey(V, Want);
      TestTrue(What + TEXT(": skin in the theme"), V == EUmButtonVariant::Disc || Theme.Skin(Skin) != nullptr);
      const FLinearColor Text = Theme.Color(UmButton::TextColorToken(V, Want));
      const double Ratio = Contrast(Text, BodyColor(V, Want));
      TestTrue(FString::Printf(TEXT("%s: text %.2f : 1 >= 4.5"), *What, Ratio), Ratio >= 4.5);
      TestTrue(What + TEXT(": text colour on the label"), B->Label->GetColorAndOpacity().GetSpecifiedColor().Equals(Text));
      TestEqual(What + TEXT(": the label is never dimmed by opacity"), B->Label->GetRenderOpacity(), 1.0f);
      TestTrue(What + TEXT(": focus ring"), (B->FocusRing->GetVisibility() != ESlateVisibility::Collapsed) == (S == EUmButtonState::Focus));
      if (S == EUmButtonState::Disabled && V == EUmButtonVariant::Disc) {
        TestTrue(What + TEXT(": the disc at state.disabled.opacity"),
                 FMath::IsNearlyEqual(B->Icon->GetRenderOpacity(), Theme.Alpha(TEXT("state.disabled.opacity"))));
      }
      TestTrue(What + TEXT(": DescribeState"), B->DescribeState().StartsWith(FString::Printf(TEXT("variant=%s state=%s"),
                                                                                              UmButtonVariantName(V),
                                                                                              UmButtonStateName(Want))));
    }
  }
  // motion: the disc hover 1.06 over hover.ms (150), the press 0.96 over icon.press.ms (80)
  UUmButton* Disc = CreateWidget<UUmButton>(W.World, UUmButton::StaticClass());
  Disc->SetClockForTest([&Clock]() { return Clock; });
  Disc->SetReducedMotionForTest(false);
  FUmButtonModel DM;
  DM.Variant = EUmButtonVariant::Disc;
  DM.Label = FText::FromString(TEXT("МАНЁВР"));
  DM.IconName = TEXT("action-maneuver");
  Disc->ApplyModel(DM);
  Disc->SimulateHover(true);
  Clock += 0.075;
  Disc->TickForTest();
  TestTrue(FString::Printf(TEXT("disc hover half way %.4f ~ 1.03"), Disc->GetIconScale()), Near(Disc->GetIconScale(), 1.03, 0.002));
  Clock += 0.1;
  Disc->TickForTest();
  TestTrue(TEXT("disc hover 1.06 after 150 ms"), Near(Disc->GetIconScale(), 1.06, 1e-4));
  // selected: the glyph pulse 1.1 -> 1.0 over 200 ms
  DM.bSelected = true;
  Disc->SimulateHover(false);
  Clock += 1.0;
  Disc->TickForTest();
  Disc->ApplyModel(DM);
  Disc->TickForTest();
  const float PulseStart = Disc->Icon->GetRenderTransform().Scale.X;
  Clock += 0.2;
  Disc->TickForTest();
  TestTrue(FString::Printf(TEXT("selected: pulse 1.1 at the start (%.3f), 1.0 after 200 ms (%.3f)"), PulseStart,
                           Disc->Icon->GetRenderTransform().Scale.X),
           Near(PulseStart, 1.1, 0.01) && Near(Disc->Icon->GetRenderTransform().Scale.X, 1.0, 1e-3));
  // reduced motion: colour only
  UUmButton* Reduced = CreateWidget<UUmButton>(W.World, UUmButton::StaticClass());
  Reduced->SetClockForTest([&Clock]() { return Clock; });
  Reduced->SetReducedMotionForTest(true);
  DM.bSelected = false;
  Reduced->ApplyModel(DM);
  Reduced->SimulateHover(true);
  Clock += 0.2;
  Reduced->TickForTest();
  TestTrue(TEXT("reduced motion: no hover scale"), Near(Reduced->GetIconScale(), 1.0, 1e-6));
  TestTrue(TEXT("reduced motion: the hover colour still"), Reduced->GetState() == EUmButtonState::Hover);
  // why.* after 300 ms of hover over a disabled button (not before), gone on leave
  UUmButton* Off = CreateWidget<UUmButton>(W.World, UUmButton::StaticClass());
  Off->SetClockForTest([&Clock]() { return Clock; });
  FUmButtonModel OM;
  OM.Label = FText::FromString(TEXT("Без защиты"));
  OM.bEnabled = false;
  OM.Reason = FS09Reason::Make(TEXT("why.deadline.passed"));
  Off->ApplyModel(OM);
  Off->SimulateHover(true);
  Clock += 0.25;
  Off->TickForTest();
  TestFalse(TEXT("why: not before 300 ms"), Off->IsWhyShown());
  Clock += 0.06;
  Off->TickForTest();
  TestTrue(TEXT("why: shown after 300 ms"), Off->IsWhyShown());
  TestFalse(TEXT("why: a text"), Off->GetWhyText().IsEmpty());
  Off->SimulateHover(false);
  TestFalse(TEXT("why: gone on leave"), Off->IsWhyShown());
  // busy: "Отправлено…" (hud.btn.sent), never silent
  OM.bEnabled = true;
  OM.Reason.Reset();
  OM.bBusy = true;
  Off->ApplyModel(OM);
  TestTrue(TEXT("busy state"), Off->GetState() == EUmButtonState::Busy);
  TestFalse(TEXT("busy label from ST_Hud"), Off->Label->GetText().ToString().StartsWith(TEXT("?")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHudPressUmgTest,
    "Unmatched.S09.HudPress.Umg synthetic clicks on UUmButton n 24, holds 0 and 50 ms, a rebuild in between, 0 lost",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHudPressUmgTest::RunTest(const FString&) {
  using namespace UmHudTest;
  FWorld W(TEXT("UmHudPressUmg"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  TSharedPtr<FS09HudPressArbiter> Arbiter = MakeShared<FS09HudPressArbiter>();
  uint64 Frame = 1000;
  Arbiter->SetFrameClock([&Frame]() { return Frame; });
  UUmButton* Button = CreateWidget<UUmButton>(W.World, UUmButton::StaticClass());
  if (!TestNotNull(TEXT("button"), Button)) return false;
  int32 Acts = 0, Refused = 0;
  FName LastWhy;
  Button->SetPress(TEXT("hud.end.turn"), Arbiter, FS09OnHudPressOutcome::CreateLambda([&](const FS09HudPressOutcome& O) {
    if (O.Result == ES09HudPressResult::Act) ++Acts;
    if (O.Result == ES09HudPressResult::Refused) {
      ++Refused;
      LastWhy = O.Reason.Key;
    }
  }));
  FUmButtonModel M;
  M.Variant = EUmButtonVariant::Primary;
  M.Label = FText::FromString(TEXT("Конец хода"));
  Button->ApplyModel(M);
  const FGeometry Geo = FGeometry::MakeRoot(FVector2D(160.0, 48.0), FSlateLayoutTransform());
  const FVector2D Centre(80.0, 24.0);
  const int32 N = 24;
  for (int32 I = 0; I < N; ++I) {
    // holds of 0 ms (press and release in one frame) and 50 ms (3 frames at 60 fps)
    const int32 HoldFrames = (I % 2) ? 3 : 0;
    Button->NativeOnMouseButtonDown(Geo, LeftEvent(Centre, true));
    for (int32 F = 0; F < HoldFrames; ++F) {
      ++Frame;
      // the combat countdown / a snapshot re-applies the model while the button is held (the Slate HUD rebuilt here)
      Arbiter->NoteRebuild();
      FUmButtonModel Again = M;
      Again.KeyHint = FText::AsNumber(F);
      Button->ApplyModel(Again);
    }
    Button->NativeOnMouseButtonUp(Geo, LeftEvent(Centre, false));
    ++Frame;
  }
  TestEqual(TEXT("every click answered with the action: 0 lost"), Acts, N);
  TestEqual(TEXT("no refusal on an enabled button"), Refused, 0);
  // a drag away cancels (MS-R-34), the next click still counts
  Button->NativeOnMouseButtonDown(Geo, LeftEvent(Centre, true));
  Button->NativeOnMouseButtonUp(Geo, LeftEvent(FVector2D(400.0, 300.0), false));
  TestEqual(TEXT("drag away: no action"), Acts, N);
  // disabled: the press is answered with its why.* (CUE-004 by the owner), never silently
  M.bEnabled = false;
  M.Reason = FS09Reason::Make(TEXT("why.actions.remaining"));
  Button->ApplyModel(M);
  for (int32 I = 0; I < N; ++I) {
    Button->NativeOnMouseButtonDown(Geo, LeftEvent(Centre, true));
    Frame += (I % 2) ? 3 : 0;
    Button->NativeOnMouseButtonUp(Geo, LeftEvent(Centre, false));
    ++Frame;
  }
  TestEqual(TEXT("disabled: every press refused (0 silent)"), Refused, N);
  TestTrue(TEXT("disabled: with its reason"), LastWhy == FName(TEXT("why.actions.remaining")));
  M.bEnabled = true;
  M.Reason.Reset();
  M.bBusy = true;
  Button->ApplyModel(M);
  Button->NativeOnMouseButtonDown(Geo, LeftEvent(Centre, true));
  Button->NativeOnMouseButtonUp(Geo, LeftEvent(Centre, false));
  TestTrue(TEXT("busy: refused with why.syncing"), LastWhy == FName(TEXT("why.syncing")));
  TestEqual(TEXT("busy: one more refusal"), Refused, N + 1);
  return true;
}

// ------------------------------------------------------------------------------------------------ HB-23 icon size

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHudIconSizeTest,
    "Unmatched.S08.Hud.IconSize 24 su at 720p 18, 24 su at 150 percent 36, 32 su at 150 percent 48, 64 su at 1080p 64",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHudIconSizeTest::RunTest(const FString&) {
  using namespace UmHudTest;
  TestEqual(TEXT("24 su at 720p (DPI 0.75) -> 18"), S08IconMotion::ExportSizePx(24.0f, 0.75f), 18);
  TestEqual(TEXT("24 su at 1080p 150 % -> 36"), S08IconMotion::ExportSizePx(24.0f, 1.5f), 36);
  TestEqual(TEXT("32 su at 1080p 150 % -> 48"), S08IconMotion::ExportSizePx(32.0f, 1.5f), 48);
  TestEqual(TEXT("64 su at 1080p -> 64"), S08IconMotion::ExportSizePx(64.0f, 1.0f), 64);
  TestEqual(TEXT("24 su at 1080p -> 24"), S08IconMotion::ExportSizePx(24.0f, 1.0f), 24);
  TestEqual(TEXT("24 su at 720p 150 % (1.125) -> 32 (27 px, the next export up)"), S08IconMotion::ExportSizePx(24.0f, 1.125f), 32);
  TestEqual(TEXT("48 su at 720p -> 36"), S08IconMotion::ExportSizePx(48.0f, 0.75f), 36);
  bool bClamped = false;
  TestEqual(TEXT("64 su at 150 % -> 64 (no bigger export)"), S08IconMotion::ExportSizePx(64.0f, 1.5f, &bClamped), 64);
  TestTrue(TEXT("... and flagged clamped"), bClamped);
  TestTrue(TEXT("-S08IconLegacy: the old size rule"), S08IconMotion::IconSizeLegacy(TEXT("-S08IconLegacy")));
  TestFalse(TEXT("no flag: the display size rule"), S08IconMotion::IconSizeLegacy(TEXT("-Bench")));
  // the widget path: the texture follows the forced px per su
  FWorld W(TEXT("UmHudIconSize"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  US08AnimatedIconWidget* Icon = CreateWidget<US08AnimatedIconWidget>(W.World, US08AnimatedIconWidget::StaticClass());
  if (!TestNotNull(TEXT("icon widget"), Icon)) return false;
  if (!TestTrue(TEXT("action-attack in the contract"), Icon->SetIcon(TEXT("action-attack"), 24.0f, 24))) return false;
  const struct {
    float Su;
    float PxPerSu;
    int32 Want;
  } Cases[] = {{24.0f, 0.75f, 18}, {24.0f, 1.5f, 36}, {32.0f, 1.5f, 48}, {64.0f, 1.0f, 64}};
  for (const auto& C : Cases) {
    Icon->SetPxPerSuOverrideForTest(C.PxPerSu);
    Icon->SetDisplaySizeSu(C.Su);
    TestEqual(FString::Printf(TEXT("widget: %.0f su x %.3f -> T_IV3_*_%d"), C.Su, C.PxPerSu, C.Want), Icon->GetTexturePx(), C.Want);
    TestTrue(FString::Printf(TEXT("widget: %.0f su drawn at %.0f su"), C.Su, C.Su), Near(Icon->GetCanvasSizeSu().X, C.Su, 0.01));
    UTexture2D* Tex = Icon->GetLayerTexture(0, 0);
    if (Tex) {
      TestTrue(FString::Printf(TEXT("widget: the loaded texture %s is the %d px export"), *Tex->GetName(), C.Want),
               Tex->GetName().EndsWith(FString::Printf(TEXT("_%d"), C.Want)));
#if WITH_EDITORONLY_DATA
      TestEqual(FString::Printf(TEXT("widget: %s source is %d px (no downscale of a master)"), *Tex->GetName(), C.Want),
                static_cast<int32>(Tex->Source.GetSizeY()), C.Want);
#endif
    } else {
      AddWarning(TEXT("T_IV3 textures not in this checkout - the texture size is not checked"));
    }
  }
  return true;
}

// ------------------------------------------------------------------------------------------------ HB-10 skins

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHudThemeSkinsTest,
    "Unmatched.S08.Hud.Theme.Skins 29 9-slice skins: x1 and x2 textures, margins over 0, x2 from 150 percent",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHudThemeSkinsTest::RunTest(const FString&) {
  bool bFallback = true;
  const UUmHudTheme* Theme = UUmHudTheme::LoadOrFallback(UUmHudTheme::AssetPath, bFallback);
  if (!TestFalse(TEXT("DA_UmHudTheme exists"), bFallback) || !Theme) return false;
  TestEqual(TEXT("29 x2 skins"), Theme->SkinsX2.Num(), S08HudTokens::kNumSkins);
  int32 Textures = 0;
  for (int32 I = 0; I < S08HudTokens::kNumSkins; ++I) {
    const FName Key(S08HudTokens::kSkins[I].Name);
    const FSlateBrush* X1 = Theme->Skins.Find(Key);
    const FSlateBrush* X2 = Theme->SkinsX2.Find(Key);
    if (!TestTrue(FString::Printf(TEXT("%s: x1 and x2"), *Key.ToString()), X1 && X2)) continue;
    const UTexture2D* T1 = Cast<UTexture2D>(X1->GetResourceObject());
    const UTexture2D* T2 = Cast<UTexture2D>(X2->GetResourceObject());
    if (!TestTrue(FString::Printf(TEXT("%s: textures (HB-10 import)"), *Key.ToString()), T1 && T2)) continue;
    ++Textures;
    TestTrue(FString::Printf(TEXT("%s: x1 named T_Skin_*"), *Key.ToString()), T1->GetName().StartsWith(TEXT("T_Skin_")));
    TestTrue(FString::Printf(TEXT("%s: x2 named T_Skin_*_x2"), *Key.ToString()), T2->GetName() == T1->GetName() + TEXT("_x2"));
#if WITH_EDITORONLY_DATA
    const FVector2D S1(T1->Source.GetSizeX(), T1->Source.GetSizeY());
    const FVector2D S2(T2->Source.GetSizeX(), T2->Source.GetSizeY());
    TestTrue(FString::Printf(TEXT("%s: x2 = twice the x1 pixels (%s / %s)"), *Key.ToString(), *S1.ToString(), *S2.ToString()),
             FMath::Abs(S2.X - 2.0 * S1.X) <= 2.0 && FMath::Abs(S2.Y - 2.0 * S1.Y) <= 2.0);
    TestTrue(FString::Printf(TEXT("%s: image size = the x1 pixels in su"), *Key.ToString()),
             X1->ImageSize.Equals(S1) && X2->ImageSize.Equals(S1));
#endif
    if (X1->DrawAs == ESlateBrushDrawType::Box) {
      TestTrue(FString::Printf(TEXT("%s: margins > 0 (x1 %.3f,%.3f,%.3f,%.3f)"), *Key.ToString(), X1->Margin.Left,
                               X1->Margin.Top, X1->Margin.Right, X1->Margin.Bottom),
               X1->Margin.Left > 0.0f && X1->Margin.Top > 0.0f && X1->Margin.Right > 0.0f && X1->Margin.Bottom > 0.0f &&
                   X2->Margin.Left > 0.0f && X2->Margin.Top > 0.0f && X2->Margin.Right > 0.0f && X2->Margin.Bottom > 0.0f);
      TestTrue(FString::Printf(TEXT("%s: margins inside the image"), *Key.ToString()),
               X1->Margin.Left + X1->Margin.Right < 1.0f && X1->Margin.Top + X1->Margin.Bottom < 1.0f);
    } else {
      TestTrue(FString::Printf(TEXT("%s: stretch 'none' = DrawAs Image (the checkbox)"), *Key.ToString()),
               X1->DrawAs == ESlateBrushDrawType::Image && Key.ToString().StartsWith(TEXT("check.")));
    }
    TestTrue(FString::Printf(TEXT("%s: x2 at 150 %%, x1 at 100 %%"), *Key.ToString()),
             Theme->SkinFor(Key, 1.5f) == X2 && Theme->SkinFor(Key, 1.0f) == X1 && Theme->SkinFor(Key, 0.75f) == X1);
  }
  TestEqual(TEXT("all 29 from the HB-08 package"), Textures, S08HudTokens::kNumSkins);
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
