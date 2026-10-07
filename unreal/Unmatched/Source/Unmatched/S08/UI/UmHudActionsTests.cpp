// VS-4 automation tests of ACTIONS (docs/game-design/visual/06-tasks/hud.csv HB-43; 04-hud-spec.md §2.11, §2.14, §3.1,
// §7.1; the accepted mockup HB-42, ВР-VS2-HB42-03...13):
//   Unmatched.S08.Hud.Actions.Tree      BuildDefaultTree of UUmHudActions: every BindWidget, the cells are WBP_UmButton
//                                       (or the native button), WBP_UI_HUD_ACTIONS (when present) is a child of the base.
//   Unmatched.S08.Hud.Actions.States    Decide: 2 / 1 / 0 actions, the opponent's turn, the maneuver / attack / scheme
//                                       modes, the hand-limit discard, a command in flight, the combat window, no playable
//                                       scheme - which button is enabled / selected / primary and its why.*; never two
//                                       primaries, КОНЕЦ ХОДА primary only with an open end of turn; the widget: the
//                                       cells 78 / 78 / 78 / 86 x 72 su with 8 su gaps (344 su) in L, 4 x 48 in S, the
//                                       disc 48 / 40 su, the HB-08 skins, the disabled disc at 0.4 with text.secondary,
//                                       no caption in S; the tooltip (L: only a disabled cell, S: the caption) 8 su over
//                                       the row inside the canvas margin; the SHOT line; same model = no work; budget.
//   Unmatched.S08.Hud.Actions.KeyHints  UI-ACC-017: auto (first match only) / on / off, the -S08KeyHints flag, the chips
//                                       M A G E 20 x 20 su 2 su in the cell's corner in L, in the tooltip in S.
//   Unmatched.S09.HudPress.UmgActions   synthetic clicks on the four cells n 24 each, holds 0 and 50 ms, a re-apply in
//                                       between: 0 lost; a disabled cell answers Refused with its why.*.
// Headless: node tools/s08/run-ue-tests.cjs "Unmatched.S08.Hud.Actions+Unmatched.S09.HudPress.UmgActions" <abs log>
#if WITH_AUTOMATION_TESTS

#include "../../S09/S09HudPress.h"
#include "../S08AnimatedIconWidget.h"
#include "../S08UserSettings.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/TextBlock.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "HAL/PlatformTime.h"
#include "Input/Events.h"
#include "InputCoreTypes.h"
#include "Internationalization/Internationalization.h"
#include "Internationalization/TextLocalizationManager.h"
#include "Layout/Geometry.h"
#include "Misc/AutomationTest.h"
#include "UmButton.h"
#include "UmGameHud.h"
#include "UmHudActions.h"
#include "UmHudTheme.h"
#include "UmText.h"

// Named namespace (not anonymous): unity builds merge test files.
namespace UmActionsTest {
/** The tooltip sizes below are measured on the EN strings: the test runs in "en" without the game localization preview
 *  that an earlier test may have left on (restored at the end). */
struct FEn {
  FInternationalization::FCultureStateSnapshot Snapshot;
  FEn() {
    FInternationalization::Get().BackupCultureState(Snapshot);
#if WITH_EDITOR  // the preview API exists only WITH_EDITOR (the game target trap)
    FTextLocalizationManager::Get().DisableGameLocalizationPreview();
    FTextLocalizationManager::Get().WaitForAsyncTasks();  // the preview reload ends before the culture switch
#endif
    FInternationalization::Get().SetCurrentLanguageAndLocale(TEXT("en"));
    FTextLocalizationManager::Get().WaitForAsyncTasks();
  }
  ~FEn() {
    FInternationalization::Get().RestoreCultureState(Snapshot);
    FTextLocalizationManager::Get().WaitForAsyncTasks();
  }
};

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

FPointerEvent Left(const FVector2D& At, bool bDown) {
  TSet<FKey> Pressed;
  if (bDown) Pressed.Add(EKeys::LeftMouseButton);
  return FPointerEvent(0, At, At, Pressed, EKeys::LeftMouseButton, 0.0f, FModifierKeysState());
}

FUmActionsInput Own(int32 Actions) {
  FUmActionsInput In;
  In.bShow = true;
  In.bViewerTurn = true;
  In.ActionsRemaining = Actions;
  if (Actions > 0) In.EndTurn = FS09Reason::Make(TEXT("why.actions.remaining")).Arg(TEXT("n"), Actions);
  if (Actions == 0) In.BeginRefusal = FS09Reason::Make(TEXT("why.no.actions"));
  return In;
}

const FUmButtonModel& B(const FUmActionsModel& M, EUmActionKey K) { return M.Buttons[static_cast<int32>(K)]; }

int32 Primaries(const FUmActionsModel& M) {
  int32 N = 0;
  for (const FUmButtonModel& X : M.Buttons) N += X.bEnabled && X.bDiscPrimary ? 1 : 0;
  return N;
}

FUmActionsFrame Frame(bool bClassS) {
  FUmActionsFrame F;
  F.bClassS = bClassS;
  F.PxPerSu = 1.0f;
  F.CanvasSu = bClassS ? FVector2D(1280.0, 720.0) : FVector2D(1920.0, 1080.0);
  F.MarginSu = bClassS ? 16.0f : 24.0f;
  F.RectSu = bClassS ? FBox2D(FVector2D(1048.0, 656.0), FVector2D(1264.0, 704.0)) : FBox2D(FVector2D(1552.0, 984.0), FVector2D(1896.0, 1056.0));
  return F;
}
}  // namespace UmActionsTest

// ------------------------------------------------------------------------------------------------ tree

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHudActionsTreeTest,
    "Unmatched.S08.Hud.Actions.Tree UUmHudActions default tree and WBP_UI_HUD_ACTIONS",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHudActionsTreeTest::RunTest(const FString&) {
  using namespace UmActionsTest;
  FWorld W(TEXT("UmHudActionsTree"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  UUmHudActions* A = CreateWidget<UUmHudActions>(W.World, UUmHudActions::StaticClass());
  if (!TestNotNull(TEXT("actions"), A)) return false;
  FString Missing;
  TestTrue(FString::Printf(TEXT("every part bound (missing: %s)"), *Missing), A->HasAllParts(&Missing));
  TestTrue(TEXT("the code default tree"), A->UsesCodeDefaultTree());
  for (int32 I = 0; I < UmActionCount; ++I) {
    const UUmButton* Btn = A->GetButton(static_cast<EUmActionKey>(I));
    TestNotNull(FString::Printf(TEXT("cell %d is a UUmButton"), I), Btn);
  }
  TestEqual(TEXT("nothing before the first model"), A->GetVisibility(), ESlateVisibility::Collapsed);
  if (UClass* Wbp = UmGameHudSlots::WbpOrNative(UUmHudActions::StaticClass(), UUmHudActions::WidgetBlueprintPath)) {
    TestTrue(TEXT("WBP_UI_HUD_ACTIONS (or the native class) is a UUmHudActions"), Wbp->IsChildOf(UUmHudActions::StaticClass()));
    UUmHudActions* FromWbp = CreateWidget<UUmHudActions>(W.World, Wbp);
    FString WbpMissing;
    TestTrue(FString::Printf(TEXT("the WBP tree has every part (missing: %s)"), *WbpMissing),
             FromWbp && FromWbp->HasAllParts(&WbpMissing));
  }
  return true;
}

// ------------------------------------------------------------------------------------------------ states

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHudActionsStatesTest,
    "Unmatched.S08.Hud.Actions.States 2 1 0 actions, opponent, modes, discard, busy, combat; cells, skins, tooltip, SHOT, budget",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHudActionsStatesTest::RunTest(const FString&) {
  using namespace UmActionsTest;
  using K = EUmActionKey;
  const FEn En;
  // ---- Decide (ВР-VS2-HB42-05) ----
  for (const int32 N : {2, 1}) {
    const FUmActionsModel M = UmHudActions::Decide(Own(N));
    TestEqual(FString::Printf(TEXT("own-%d: state own"), N), M.State, FString(TEXT("own")));
    for (const K Key : {K::Maneuver, K::Attack, K::Scheme}) {
      TestTrue(FString::Printf(TEXT("own-%d: %s available"), N, UmHudActions::KeyName(Key)), B(M, Key).bEnabled);
    }
    TestFalse(FString::Printf(TEXT("own-%d: end disabled"), N), B(M, K::EndTurn).bEnabled);
    TestTrue(FString::Printf(TEXT("own-%d: why.actions.remaining {n}=%d"), N, N),
             B(M, K::EndTurn).Reason.Key == FName(TEXT("why.actions.remaining")) &&
                 B(M, K::EndTurn).Reason.Args.FindRef(TEXT("n")) == FString::FromInt(N));
    TestEqual(FString::Printf(TEXT("own-%d: no primary"), N), Primaries(M), 0);
  }
  {
    const FUmActionsModel M = UmHudActions::Decide(Own(0));
    for (const K Key : {K::Maneuver, K::Attack, K::Scheme}) {
      TestTrue(FString::Printf(TEXT("own-0: %s disabled with why.no.actions"), UmHudActions::KeyName(Key)),
               !B(M, Key).bEnabled && B(M, Key).Reason.Key == FName(TEXT("why.no.actions")));
    }
    TestTrue(TEXT("own-0: end is the primary cell"), B(M, K::EndTurn).bEnabled && B(M, K::EndTurn).bDiscPrimary);
    TestEqual(TEXT("own-0: exactly one primary"), Primaries(M), 1);
  }
  {
    FUmActionsInput In = Own(2);
    In.bViewerTurn = false;
    const FUmActionsModel M = UmHudActions::Decide(In);
    TestEqual(TEXT("opp: state"), M.State, FString(TEXT("opp")));
    for (const FUmButtonModel& X : M.Buttons) {
      TestTrue(TEXT("opp: every cell disabled with why.not.your.turn"), !X.bEnabled && X.Reason.Key == FName(TEXT("why.not.your.turn")));
    }
    TestEqual(TEXT("opp: no primary"), Primaries(M), 0);
  }
  {
    FUmActionsInput In = Own(2);
    In.Mode = ES09CommandMode::ManeuverDraft;
    In.EndTurn = FS09Reason::Make(TEXT("why.draft.open"));
    const FUmActionsModel M = UmHudActions::Decide(In);
    TestEqual(TEXT("mode=maneuver: state"), M.State, FString(TEXT("mode=maneuver")));
    TestTrue(TEXT("mode=maneuver: МАНЁВР selected"), B(M, K::Maneuver).bSelected && B(M, K::Maneuver).bEnabled);
    for (const K Key : {K::Attack, K::Scheme, K::EndTurn}) {
      TestTrue(FString::Printf(TEXT("mode=maneuver: %s why.draft.open"), UmHudActions::KeyName(Key)),
               !B(M, Key).bEnabled && B(M, Key).Reason.Key == FName(TEXT("why.draft.open")));
    }
    FUmActionsInput Pending = Own(1);
    Pending.bManeuverPending = true;
    TestEqual(TEXT("a server-side pending maneuver is the same mode"), UmHudActions::Decide(Pending).State, FString(TEXT("mode=maneuver")));
  }
  {
    FUmActionsInput In = Own(2);
    In.Mode = ES09CommandMode::AttackDraft;
    const FUmActionsModel M = UmHudActions::Decide(In);
    TestEqual(TEXT("mode=attack: state"), M.State, FString(TEXT("mode=attack")));
    TestTrue(TEXT("mode=attack: АТАКА selected"), B(M, K::Attack).bSelected);
    TestTrue(TEXT("mode=attack: МАНЁВР, СХЕМА available (the mode switch)"), B(M, K::Maneuver).bEnabled && B(M, K::Scheme).bEnabled &&
                                                                               !B(M, K::Maneuver).bSelected && !B(M, K::Scheme).bSelected);
    TestFalse(TEXT("mode=attack: end disabled"), B(M, K::EndTurn).bEnabled);
    In = Own(1);
    In.Mode = ES09CommandMode::SchemeChoice;
    const FUmActionsModel S = UmHudActions::Decide(In);
    TestEqual(TEXT("mode=scheme: state"), S.State, FString(TEXT("mode=scheme")));
    TestTrue(TEXT("mode=scheme: СХЕМА selected, the other two available"),
             B(S, K::Scheme).bSelected && B(S, K::Maneuver).bEnabled && B(S, K::Attack).bEnabled);
  }
  {
    FUmActionsInput In = Own(0);
    In.Mode = ES09CommandMode::DiscardDraft;
    In.EndTurn = FS09Reason::Make(TEXT("why.discard.count")).Arg(TEXT("need"), 1).Arg(TEXT("have"), 0);
    const FUmActionsModel M = UmHudActions::Decide(In);
    TestTrue(TEXT("discard: the actions why.no.actions"), !B(M, K::Attack).bEnabled && B(M, K::Attack).Reason.Key == FName(TEXT("why.no.actions")));
    TestTrue(TEXT("discard: end why.discard.count, not primary"),
             !B(M, K::EndTurn).bEnabled && !B(M, K::EndTurn).bDiscPrimary && B(M, K::EndTurn).Reason.Key == FName(TEXT("why.discard.count")));
    TestEqual(TEXT("discard: the why text formats need / have"), UmHudActions::WhyText(B(M, K::EndTurn).Reason).ToString().Contains(TEXT("1")), true);
  }
  {
    FUmActionsInput In = Own(0);
    In.Busy = FS09Reason::Make(TEXT("why.syncing"));
    In.EndTurn = In.Busy;
    const FUmActionsModel M = UmHudActions::Decide(In);
    for (const FUmButtonModel& X : M.Buttons) TestTrue(TEXT("in flight: all why.syncing"), !X.bEnabled && X.Reason.Key == FName(TEXT("why.syncing")));
    FUmActionsInput C = Own(1);
    C.bCombat = true;
    C.EndTurn = FS09Reason::Make(TEXT("why.wait.defender"));
    const FUmActionsModel CM = UmHudActions::Decide(C);
    TestTrue(TEXT("combat: the actions why.wait.defender"), !B(CM, K::Maneuver).bEnabled && B(CM, K::Maneuver).Reason.Key == FName(TEXT("why.wait.defender")));
    FUmActionsInput NS = Own(2);
    NS.bNoScheme = true;
    const FUmActionsModel NM = UmHudActions::Decide(NS);
    TestTrue(TEXT("no playable scheme: СХЕМА why.scheme.none, the others available"),
             !B(NM, K::Scheme).bEnabled && B(NM, K::Scheme).Reason.Key == FName(TEXT("why.scheme.none")) && B(NM, K::Attack).bEnabled);
  }
  // ---- the widget ----
  FWorld W(TEXT("UmHudActionsStates"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  UUmHudActions* A = CreateWidget<UUmHudActions>(W.World, UUmHudActions::StaticClass());
  if (!TestNotNull(TEXT("actions"), A)) return false;
  double Clock = 10.0;
  A->SetClockForTest([&Clock]() { return Clock; });
  A->SetFrame(Frame(false));
  A->ApplyModel(UmHudActions::Decide(Own(2)));
  TestEqual(TEXT("shown"), A->GetVisibility(), ESlateVisibility::SelfHitTestInvisible);
  const float Widths[] = {78.0f, 78.0f, 78.0f, 86.0f};
  float X = 1552.0f;
  for (int32 I = 0; I < UmActionCount; ++I) {
    const FBox2D C = A->CellRectSu(static_cast<K>(I));
    TestTrue(FString::Printf(TEXT("L cell %d at x %.0f, %.0f x 72"), I, X, Widths[I]),
             Near(C.Min.X, X, 0.01) && Near(C.Min.Y, 984.0, 0.01) && Near(C.GetSize().X, Widths[I], 0.01) && Near(C.GetSize().Y, 72.0, 0.01));
    X += Widths[I] + 8.0f;
    const UUmButton* Btn = A->GetButton(static_cast<K>(I));
    TestTrue(FString::Printf(TEXT("L cell %d: disc 48 su"), I), Btn && Btn->GetModel().DiscSu == 48.0f && Btn->GetModel().Variant == EUmButtonVariant::Disc);
    TestFalse(FString::Printf(TEXT("L cell %d: the caption shown"), I), Btn && Btn->GetModel().Label.IsEmpty());
  }
  TestTrue(TEXT("L row 344 su"), Near(X - 8.0f - 1552.0f, 344.0, 0.01));
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  {
    const UUmButton* End = A->GetButton(K::EndTurn);
    TestEqual(TEXT("end disabled: Btn_Disabled skin"), UmButton::SkinKeyFor(End->GetModel(), End->GetState()), FName(TEXT("btn.disabled")));
    TestTrue(TEXT("end disabled: the disc at 0.4"), Near(End->Icon->GetRenderOpacity(), Theme.Alpha(TEXT("state.disabled.opacity")), 1e-3));
    TestTrue(TEXT("end disabled: caption text.secondary, opacity 1"),
             End->Label->GetColorAndOpacity().GetSpecifiedColor().Equals(Theme.Color(TEXT("text.secondary"))) &&
                 End->Label->GetRenderOpacity() == 1.0f);
    const UUmButton* Man = A->GetButton(K::Maneuver);
    TestEqual(TEXT("maneuver available: Btn_Normal"), UmButton::SkinKeyFor(Man->GetModel(), Man->GetState()), FName(TEXT("btn.normal")));
  }
  A->ApplyModel(UmHudActions::Decide(Own(0)));
  {
    const UUmButton* End = A->GetButton(K::EndTurn);
    TestEqual(TEXT("own-0: end BtnPrimary_Normal"), UmButton::SkinKeyFor(End->GetModel(), End->GetState()), FName(TEXT("btn.primary.normal")));
    TestTrue(TEXT("own-0: end caption card.navy"), End->Label->GetColorAndOpacity().GetSpecifiedColor().Equals(Theme.Color(TEXT("card.navy"))));
    TestTrue(TEXT("own-0: the end disc at full opacity"), Near(End->Icon->GetRenderOpacity(), 1.0, 1e-3));
  }
  {
    FUmActionsInput In = Own(2);
    In.Mode = ES09CommandMode::AttackDraft;
    A->ApplyModel(UmHudActions::Decide(In));
    const UUmButton* Att = A->GetButton(K::Attack);
    TestEqual(TEXT("mode=attack: Btn_Selected"), UmButton::SkinKeyFor(Att->GetModel(), Att->GetState()), FName(TEXT("btn.selected")));
    TestTrue(TEXT("mode=attack: caption card.glyph"), Att->Label->GetColorAndOpacity().GetSpecifiedColor().Equals(Theme.Color(TEXT("card.glyph"))));
  }
  // the tooltip, class L: a disabled cell after 300 ms of hover, nothing over an enabled one
  A->ApplyModel(UmHudActions::Decide(Own(2)));
  A->SimulatePointer(static_cast<int32>(K::EndTurn));
  Clock += 0.25;
  A->TickForTest();
  TestEqual(TEXT("L: no tooltip before 300 ms"), A->GetTipKey(), K::Num);
  Clock += 0.06;
  A->TickForTest();
  TestEqual(TEXT("L: the end's why after 300 ms"), A->GetTipKey(), K::EndTurn);
  const FBox2D Tip = A->TipRectSu();
  TestTrue(FString::Printf(TEXT("L: the tooltip bottom 8 su over the row (%.1f)"), Tip.Max.Y), Near(Tip.Max.Y, 984.0 - 8.0, 0.01));
  TestTrue(TEXT("L: one line 44 su"), Near(Tip.GetSize().Y, 44.0, 0.01));
  TestTrue(TEXT("L: right edge on the cell's, inside the margin"), Tip.Max.X <= 1920.0 - 24.0 + 0.01 && Tip.Max.X >= 1896.0 - 0.01);
  TestTrue(TEXT("L: width <= 360 su"), Tip.GetSize().X <= 360.0 + 0.01);
  TestTrue(TEXT("L: the why text"), A->GetTipText().ToString().Contains(TEXT("2")));
  A->SimulatePointer(static_cast<int32>(K::Maneuver));
  Clock += 0.5;
  A->TickForTest();
  TestEqual(TEXT("L: no tooltip over an enabled cell"), A->GetTipKey(), K::Num);
  // class S: 48 su squares, the disc 40, no caption; the caption tooltip on hover
  A->SimulatePointer(INDEX_NONE);
  A->SetFrame(Frame(true));
  for (int32 I = 0; I < UmActionCount; ++I) {
    const FBox2D C = A->CellRectSu(static_cast<K>(I));
    TestTrue(FString::Printf(TEXT("S cell %d 48 x 48 at x %.0f"), I, 1048.0 + 56.0 * I),
             Near(C.Min.X, 1048.0 + 56.0 * I, 0.01) && Near(C.GetSize().X, 48.0, 0.01) && Near(C.GetSize().Y, 48.0, 0.01));
    const UUmButton* Btn = A->GetButton(static_cast<K>(I));
    TestTrue(FString::Printf(TEXT("S cell %d: disc 40, no caption, no chip"), I),
             Btn && Btn->GetModel().DiscSu == 40.0f && Btn->GetModel().Label.IsEmpty() && Btn->GetModel().KeyHint.IsEmpty());
  }
  A->SimulatePointer(static_cast<int32>(K::Maneuver));
  Clock += 0.31;
  A->TickForTest();
  TestEqual(TEXT("S: the caption tooltip over an enabled cell"), A->GetTipKey(), K::Maneuver);
  TestTrue(TEXT("S: the caption in caps"), A->GetTipText().ToString().StartsWith(UmHudActions::Caption(K::Maneuver).ToString().ToUpper()));
  TestTrue(TEXT("S: one line"), Near(A->TipRectSu().GetSize().Y, 44.0, 0.01));
  A->SimulatePointer(static_cast<int32>(K::EndTurn));
  Clock += 0.31;
  A->TickForTest();
  TestTrue(TEXT("S: a disabled cell - caption + why, two lines (68 su)"), A->GetTipKey() == K::EndTurn && Near(A->TipRectSu().GetSize().Y, 68.0, 0.01));
  TestTrue(TEXT("S: width <= 300 su"), A->TipRectSu().GetSize().X <= 300.0 + 0.01);
  TestTrue(TEXT("S: right edge inside the 16 su margin"), A->TipRectSu().Max.X <= 1280.0 - 16.0 + 0.01);
  // the SHOT line
  TArray<FString> Lines;
  A->CollectShotLines(Lines);
  TestEqual(TEXT("one SHOT line"), Lines.Num(), 1);
  if (Lines.Num()) {
    TestTrue(FString::Printf(TEXT("SHOT: %s"), *Lines[0]), Lines[0].StartsWith(TEXT("SHOT widget id=UI-HUD-ACTIONS impl=umg state=own ")) &&
                                                              Lines[0].Contains(TEXT(" class=S ")) && Lines[0].Contains(TEXT("end:disabled:why.actions.remaining")) &&
                                                              Lines[0].Contains(TEXT("tip=end")));
  }
  // same model = no work; the budget of a refresh (Decide + ApplyModel) and of the tooltip step (<= 0.03 ms p95)
  const int32 Before = A->GetApplyCount();
  A->ApplyModel(UmHudActions::Decide(Own(2)));
  TestEqual(TEXT("same model: no work"), A->GetApplyCount(), Before);
  TArray<double> Ms;
  for (int32 I = 0; I < 200; ++I) {
    const double T0 = FPlatformTime::Seconds();
    A->ApplyModel(UmHudActions::Decide(Own(I % 2 ? 2 : 1)));
    A->TickForTest();
    Ms.Add((FPlatformTime::Seconds() - T0) * 1000.0);
  }
  Ms.Sort();
  const double P95 = Ms[FMath::Min(Ms.Num() - 1, FMath::FloorToInt(Ms.Num() * 0.95))];
  AddInfo(FString::Printf(TEXT("ACTIONS refresh (a changed model) p95 %.4f ms, median %.4f ms"), P95, Ms[Ms.Num() / 2]));
  TArray<double> Tick;
  for (int32 I = 0; I < 200; ++I) {
    const double T0 = FPlatformTime::Seconds();
    A->ApplyModel(UmHudActions::Decide(Own(2)));  // the per-frame path: same model
    A->TickForTest();
    Tick.Add((FPlatformTime::Seconds() - T0) * 1000.0);
  }
  Tick.Sort();
  const double TickP95 = Tick[FMath::FloorToInt(Tick.Num() * 0.95)];
  TestTrue(FString::Printf(TEXT("budget: the per-frame step p95 %.4f ms <= 0.03"), TickP95), TickP95 <= 0.03);
  return true;
}

// ------------------------------------------------------------------------------------------------ key hints

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHudActionsKeyHintsTest,
    "Unmatched.S08.Hud.Actions.KeyHints UI-ACC-017 auto on off, the flag, the chips in L and in the S tooltip",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHudActionsKeyHintsTest::RunTest(const FString&) {
  using namespace UmActionsTest;
  using K = EUmActionKey;
  TestTrue(TEXT("auto: shown in the first match"), US08UserSettings::KeyHintsShown(TEXT("auto"), 0));
  TestFalse(TEXT("auto: hidden after a finished match"), US08UserSettings::KeyHintsShown(TEXT("auto"), 1));
  TestTrue(TEXT("on: always"), US08UserSettings::KeyHintsShown(TEXT("on"), 5));
  TestFalse(TEXT("off: never"), US08UserSettings::KeyHintsShown(TEXT("off"), 0));
  TestEqual(TEXT("unknown reads as auto"), US08UserSettings::NormalizeKeyHintsMode(TEXT("maybe")), FString(TEXT("auto")));
  TestEqual(TEXT("-S08KeyHints=off wins"), US08UserSettings::ResolveKeyHintsMode(TEXT("on"), TEXT("-S08KeyHints=off")), FString(TEXT("off")));
  TestEqual(TEXT("-S08KeyHints=ON (any case)"), US08UserSettings::ResolveKeyHintsMode(TEXT("auto"), TEXT("-S08KeyHints=ON")), FString(TEXT("on")));
  TestEqual(TEXT("a bad flag keeps the saved mode"), US08UserSettings::ResolveKeyHintsMode(TEXT("off"), TEXT("-S08KeyHints=x")), FString(TEXT("off")));
  {
    US08UserSettings* Probe = NewObject<US08UserSettings>();
    FString Error;
    TestTrue(TEXT("s08.Settings keyHints=on"), Probe->ApplySetting(TEXT("keyHints"), TEXT("on"), Error) && Probe->KeyHintsMode == TEXT("on"));
    TestFalse(TEXT("s08.Settings keyHints=2 refused"), Probe->ApplySetting(TEXT("keyHints"), TEXT("2"), Error));
    TestEqual(TEXT("DescribeKeyHints"), Probe->DescribeKeyHints(), FString(TEXT("keyHints=on completedMatches=0")));
  }
  // the chips: M A G E (hud.key.*) on the cells in class L, none on the cells in S (the tooltip carries it)
  FUmActionsInput In = Own(2);
  In.bKeyHints = true;
  const FUmActionsModel M = UmHudActions::Decide(In);
  const TCHAR* Letters[] = {TEXT("hud.key.maneuver"), TEXT("hud.key.attack"), TEXT("hud.key.scheme"), TEXT("hud.key.end_turn")};
  for (int32 I = 0; I < UmActionCount; ++I) {
    TestTrue(FString::Printf(TEXT("chip %d = %s"), I, Letters[I]),
             M.Buttons[I].KeyHint.ToString() == UmText::Get(EUmTable::Hud, Letters[I]).ToString() && !M.Buttons[I].KeyHint.IsEmpty());
    TestFalse(FString::Printf(TEXT("the letter never in the caption %d"), I),
              M.Buttons[I].Label.ToString().Contains(TEXT("(")) || M.Buttons[I].Label.ToString().EndsWith(M.Buttons[I].KeyHint.ToString() + TEXT(")")));
  }
  TestTrue(TEXT("no chips without key hints"), UmHudActions::Decide(Own(2)).Buttons[0].KeyHint.IsEmpty());
  FWorld W(TEXT("UmHudActionsKeys"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  UUmHudActions* A = CreateWidget<UUmHudActions>(W.World, UUmHudActions::StaticClass());
  if (!TestNotNull(TEXT("actions"), A)) return false;
  double Clock = 5.0;
  A->SetClockForTest([&Clock]() { return Clock; });
  A->SetFrame(Frame(false));
  A->ApplyModel(M);
  for (int32 I = 0; I < UmActionCount; ++I) {
    const UUmButton* Btn = A->GetButton(static_cast<K>(I));
    TestTrue(FString::Printf(TEXT("L cell %d: the chip shown"), I), Btn && Btn->KeyChip && Btn->KeyChip->GetVisibility() != ESlateVisibility::Collapsed);
  }
  A->SetFrame(Frame(true));
  for (int32 I = 0; I < UmActionCount; ++I) {
    const UUmButton* Btn = A->GetButton(static_cast<K>(I));
    TestTrue(FString::Printf(TEXT("S cell %d: no chip on the disc"), I), Btn && Btn->KeyChip && Btn->KeyChip->GetVisibility() == ESlateVisibility::Collapsed);
  }
  A->SimulatePointer(static_cast<int32>(K::Maneuver));
  Clock += 0.31;
  A->TickForTest();
  TestTrue(TEXT("S: the tooltip carries the chip"), A->TipKey && A->TipKey->GetVisibility() != ESlateVisibility::Collapsed &&
                                                      A->TipKeyText->GetText().ToString() == M.Buttons[0].KeyHint.ToString());
  return true;
}

// ------------------------------------------------------------------------------------------------ presses

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHudPressUmgActionsTest,
    "Unmatched.S09.HudPress.UmgActions synthetic clicks on the four action cells n 24 each, holds 0 and 50 ms, 0 lost",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHudPressUmgActionsTest::RunTest(const FString&) {
  using namespace UmActionsTest;
  using K = EUmActionKey;
  FWorld W(TEXT("UmHudPressUmgActions"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  TSharedPtr<FS09HudPressArbiter> Arbiter = MakeShared<FS09HudPressArbiter>();
  uint64 FrameNo = 2000;
  Arbiter->SetFrameClock([&FrameNo]() { return FrameNo; });
  UUmHudActions* A = CreateWidget<UUmHudActions>(W.World, UUmHudActions::StaticClass());
  if (!TestNotNull(TEXT("actions"), A)) return false;
  int32 Acts[UmActionCount] = {0, 0, 0, 0};
  int32 Refused[UmActionCount] = {0, 0, 0, 0};
  FName LastWhy;
  A->SetInput(Arbiter, [&](const FS09HudPressOutcome& O, K Key) {
    if (O.Result == ES09HudPressResult::Act) ++Acts[static_cast<int32>(Key)];
    if (O.Result == ES09HudPressResult::Refused) {
      ++Refused[static_cast<int32>(Key)];
      LastWhy = O.Reason.Key;
    }
  });
  A->SetFrame(Frame(false));
  A->ApplyModel(UmHudActions::Decide(Own(0)));  // the actions disabled, the end primary
  const FGeometry Geo = FGeometry::MakeRoot(FVector2D(86.0, 72.0), FSlateLayoutTransform());
  const FVector2D Centre(43.0, 36.0);
  const int32 N = 24;
  for (int32 I = 0; I < N; ++I) {
    UUmButton* End = A->GetButton(K::EndTurn);
    const int32 Hold = (I % 2) ? 3 : 0;
    End->NativeOnMouseButtonDown(Geo, Left(Centre, true));
    for (int32 F = 0; F < Hold; ++F) {
      ++FrameNo;
      Arbiter->NoteRebuild();
      A->ApplyModel(UmHudActions::Decide(Own(0)));  // a snapshot re-applies the row while the cell is held
    }
    End->NativeOnMouseButtonUp(Geo, Left(Centre, false));
    ++FrameNo;
  }
  TestEqual(TEXT("end (primary): every click acts, 0 lost"), Acts[3], N);
  for (const K Key : {K::Maneuver, K::Attack, K::Scheme}) {
    UUmButton* Btn = A->GetButton(Key);
    for (int32 I = 0; I < N; ++I) {
      Btn->NativeOnMouseButtonDown(Geo, Left(Centre, true));
      FrameNo += (I % 2) ? 3 : 0;
      Btn->NativeOnMouseButtonUp(Geo, Left(Centre, false));
      ++FrameNo;
    }
    TestEqual(FString::Printf(TEXT("%s disabled: every press refused (0 silent)"), UmHudActions::KeyName(Key)), Refused[static_cast<int32>(Key)], N);
  }
  TestTrue(TEXT("refused with why.no.actions"), LastWhy == FName(TEXT("why.no.actions")));
  // own-2: the three actions act, the end refuses with why.actions.remaining
  A->ApplyModel(UmHudActions::Decide(Own(2)));
  for (const K Key : {K::Maneuver, K::Attack, K::Scheme}) {
    UUmButton* Btn = A->GetButton(Key);
    for (int32 I = 0; I < N; ++I) {
      Btn->NativeOnMouseButtonDown(Geo, Left(Centre, true));
      FrameNo += (I % 2) ? 3 : 0;
      Btn->NativeOnMouseButtonUp(Geo, Left(Centre, false));
      ++FrameNo;
    }
    TestEqual(FString::Printf(TEXT("%s available: every click acts"), UmHudActions::KeyName(Key)), Acts[static_cast<int32>(Key)], N);
  }
  UUmButton* End = A->GetButton(K::EndTurn);
  End->NativeOnMouseButtonDown(Geo, Left(Centre, true));
  End->NativeOnMouseButtonUp(Geo, Left(Centre, false));
  TestTrue(TEXT("end disabled: refused with why.actions.remaining"), LastWhy == FName(TEXT("why.actions.remaining")) && Refused[3] == 1);
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
