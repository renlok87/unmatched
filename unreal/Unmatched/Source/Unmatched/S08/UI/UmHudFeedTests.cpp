// VS-4 automation tests of the feed blocks (docs/game-design/visual/06-tasks/hud.csv HB-39, HB-40, HB-41, HB-36;
// 04-hud-spec.md §2.8, §2.10, §2.12, §2.13, §7.1; the accepted mockup HB-38, ВР-VS2-HB38-*):
//   Unmatched.S08.Hud.Log.Feed           the row (stripe of the team, «Х{n}», RU text through ms.log.*, «→», tooltip = the
//                                        full line, last row text.primary), 50 lines kept, the autoscroll waits while the
//                                        player reads, 6 / 3 / 12 rows, hidden in the combat, the class S list, budget.
//   Unmatched.S08.Hud.Toast.Place        the chain of 04 §2.12: bottom -> top band -> whole-pixel shift up -> newest only ->
//                                        fail; the subtitle under the toasts; the lowered hand; the defense window (spaces
//                                        are no obstacle); the look of info / warning / error; the SHOT and TOAST lines.
//   Unmatched.S08.Hud.Toast.Sticky       the hand-limit rule holds until its cross / the owner's dismiss, only its cross
//                                        takes the mouse, a newer toast hides it (never drops it).
//   Unmatched.S08.Hud.Toast.Queue        at most 2, the newest at the bottom, the same toast renews its hold, the banner
//                                        gate, the holds (error 4 s, others 2-4 s), the fades, the refusal badge 350 ms.
//   Unmatched.S08.Hud.Subtitle.Duration  length + 500 ms, a new line replaces the old one, the capsule (one line <= 720 su,
//                                        a longer one two rows), «{name}:», lowered with the hand, the SHOT line.
//   Unmatched.S08.Hud.Pending.Compact    HB-36: the compact MOVE (L two rows 720 x >= 56 under STATUS, S one row in the
//                                        band), the collapsed plate 320 x 44 «{карта}: выбор ждёт».
//   Unmatched.S08.Hud.Pending.Toast      HB-36: the repeating trigger is a member of UUmToastStack - placed by its chain,
//                                        waits hidden while a newer toast takes the only room, comes back after it.
//   Unmatched.S08.Hud.Pending.Opp        HB-36: the opponent's choice grey, >= 320 su, no buttons, SHOT state=opp.
//   Unmatched.S08.Hud.Pending.Discard    HB-36: the hand-limit discard «Сбросьте {n}: выбрано {h}/{n}», no cancel,
//                                        «Подтвердить» refused with why.discard.count; the «+N» chip >= 21 px (IC-34 П-2).
// Headless: node tools/s08/run-ue-tests.cjs "Unmatched.S08.Hud.Log+Unmatched.S08.Hud.Toast+Unmatched.S08.Hud.Subtitle+Unmatched.S08.Hud.Pending" <log>
#if WITH_AUTOMATION_TESTS

#include "../../S09/S09ManeuverUi.h"
#include "../../S09/S09OpponentView.h"
#include "../../S09/S09PendingPresent.h"
#include "../S08AnimatedIconWidget.h"
#include "Components/ScrollBox.h"
#include "Components/VerticalBox.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "HAL/PlatformTime.h"
#include "Internationalization/Internationalization.h"
#include "Internationalization/TextLocalizationManager.h"
#include "Misc/AutomationTest.h"
#include "UmCardWidget.h"
#include "UmHudFeed.h"
#include "UmHudFeedBlocks.h"
#include "UmHudLayout.h"
#include "UmHudLog.h"
#include "UmHudPending.h"
#include "UmHudSubtitle.h"
#include "UmHudTheme.h"
#include "UmText.h"
#include "UmToast.h"
#include "UmToastStack.h"

// Named namespace (not anonymous): unity builds merge test files.
namespace UmFeedTest {
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

struct FRu {
  FInternationalization::FCultureStateSnapshot Snapshot;
  FRu() {
    FInternationalization::Get().BackupCultureState(Snapshot);
    FInternationalization::Get().SetCurrentLanguageAndLocale(TEXT("ru"));
#if WITH_EDITOR  // the preview API exists only WITH_EDITOR (the VS-1 / VS-2 C2039 trap of the game target)
    FTextLocalizationManager::Get().EnableGameLocalizationPreview(TEXT("ru"));
#endif
    FTextLocalizationManager::Get().WaitForAsyncTasks();
  }
  ~FRu() { FInternationalization::Get().RestoreCultureState(Snapshot); }
};

float Est(const FString& Text, float SizeSu) { return 0.5f * SizeSu * Text.Len(); }

/** The layout of a canvas with the Marmoreal FIELD of 04 §1.6 (measured on run I at 1080p), scaled to the canvas. */
FUmHudLayout Layout(const FVector2D& CanvasSu, float Px) {
  // FIELD in px of a 1080p frame -> su of this canvas: the window is CanvasSu x Px px
  const float Win = static_cast<float>(CanvasSu.Y) * Px;  // window height px
  const float S = Win / 1080.0f / Px;                     // 1080p px -> su
  const FBox2D Field(FVector2D(410.0f * S, 255.0f * S), FVector2D(1440.0f * S, 850.0f * S));
  return FUmHudLayout::Compute(CanvasSu, Px, &Field);
}

/** The feed input of a canvas: STATUS one line, the hand at rest (5 cards), the caption plate, every space of FIELD as
 *  one conservative rect. */
FUmFeedInput Input(const FUmHudLayout& L) {
  FUmFeedInput In;
  In.Layout = &L;
  In.bLive = true;
  In.StatusBottomSu = static_cast<float>(L.Rect(EUmHudBlock::Status).Min.Y) + 48.0f;
  In.Spaces.Add(L.FieldSu);
  const FBox2D& Hand = L.Rect(EUmHudBlock::Hand);
  In.CardsTopSu = static_cast<float>(Hand.Min.Y);
  In.CaptionSu = FBox2D(FVector2D(Hand.Min.X, Hand.Min.Y - 22.0), FVector2D(Hand.Min.X + 83.0, Hand.Min.Y));
  In.Blocks.Add(Hand);
  for (const EUmHudBlock B : {EUmHudBlock::Top, EUmHudBlock::PanelLoc, EUmHudBlock::PanelOpp, EUmHudBlock::OppHand, EUmHudBlock::Decks,
                              EUmHudBlock::Actions}) {
    if (L.HasRect(B)) In.Blocks.Add(L.Rect(B));
  }
  return In;
}

TArray<FUmToastMember> Members(std::initializer_list<FVector2D> Sizes) {
  TArray<FUmToastMember> Out;
  int32 Id = 1;
  for (const FVector2D& S : Sizes) Out.Add({Id++, S});
  return Out;
}

/** The Slate scroll box laid out at its size (the autoscroll reads its cached geometry); Root keeps the Slate tree
 *  alive (a UUserWidget holds its Slate widget only weakly). */
void LayoutScroll(UUmHudLog* Log, const TSharedRef<SWidget>& Root, float W, float H) {
  if (!Log || !Log->Scroll) return;
  Root->SlatePrepass(1.0f);
  const TSharedPtr<SWidget> Sb = Log->Scroll->GetCachedWidget();
  if (!Sb.IsValid()) return;
  Sb->SlatePrepass(1.0f);
  for (int32 I = 0; I < 2; ++I) Sb->Tick(FGeometry::MakeRoot(FVector2D(W, H), FSlateLayoutTransform()), 0.0, 0.016f);
}

FString ShotOf(const TArray<FString>& Lines, const TCHAR* Id) {
  for (const FString& L : Lines) {
    if (L.Contains(FString(TEXT("id=")) + Id)) return L;
  }
  return FString();
}

FUmToastSpec Spec(EUmToastKind Kind, const TCHAR* Key, const FString& Text, bool bSticky = false, float Hold = 3.0f) {
  FUmToastSpec S;
  S.Kind = Kind;
  S.Key = FName(Key);
  S.Text = FText::FromString(Text);
  S.bSticky = bSticky;
  S.HoldSec = Hold;
  return S;
}
}  // namespace UmFeedTest

// ---------------------------------------------------------------------------------------------------------------- Log

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHudLogFeedTest,
    "Unmatched.S08.Hud.Log.Feed row, 50 lines, autoscroll, 6 / 3 / 12 rows, hidden in the combat",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHudLogFeedTest::RunTest(const FString&) {
  using namespace UmFeedTest;
  FWorld W(TEXT("UmHudLogFeed"));
  if (!TestNotNull(TEXT("world"), W.World)) return false;
  FRu Ru;
  // ---- the line of a trail in RU (run I Marmoreal seq 5: «Medusa: манёвр: Medusa M13→M25») ----
  FS09LastMovement T;
  T.bValid = true;
  T.Seq = 5;
  T.PlayerId = TEXT("p1");
  T.Source = TEXT("MANEUVER");
  FS09LastMovement::FMove M;
  M.FighterId = TEXT("medusa");
  M.From = FIntPoint(1, 2);
  M.Path = {FIntPoint(3, 4)};
  T.Moves.Add(M);
  auto Player = [](const FString&) { return FString(TEXT("Medusa")); };
  auto Fighter = [](const FString& Id) { return Id == TEXT("medusa") ? FString(TEXT("Medusa")) : Id; };
  auto Cell = [](const FIntPoint& C) { return C == FIntPoint(1, 2) ? FString(TEXT("M13")) : FString(TEXT("M25")); };
  FText Text, Full;
  UmHudLog::DescribeTrail(T, FString(), {}, Player, Fighter, Cell, Text, Full);
  TestEqual(TEXT("maneuver RU through ms.log.maneuver / ms.log.move (the arrow kept)"), Text.ToString(),
            FString(TEXT("Medusa: манёвр: Medusa M13→M25")));
  // run I Marmoreal seq 22: «Medusa: эффект Рывок: без движения»
  FS09LastMovement E = T;
  E.Source = TEXT("EFFECT");
  E.Moves.Reset();
  UmHudLog::DescribeTrail(E, TEXT("Рывок"), {}, Player, Fighter, Cell, Text, Full);
  TestEqual(TEXT("effect RU, ms.log.stay"), Text.ToString(), FString(TEXT("Medusa: эффект Рывок: без движения")));
  // a boost and more than three moves: «и ещё N» inline, every move in the tooltip text
  FS09LastMovement B = T;
  B.bBoost = true;
  B.BoostValue = 2;
  B.BoostName = TEXT("Рывок");
  for (int32 I = 0; I < 3; ++I) B.Moves.Add(M);
  UmHudLog::DescribeTrail(B, FString(), {}, Player, Fighter, Cell, Text, Full);
  TestTrue(TEXT("boost part «, буст +2 (Рывок)»"), Text.ToString().Contains(TEXT(", буст +2 (Рывок)")));
  TestTrue(TEXT("four moves: inline «и ещё 2», full has all four"),
           Text.ToString().Contains(TEXT("и ещё 2")) && !Full.ToString().Contains(TEXT("и ещё")));
  TestEqual(TEXT("«Х{n}» (hud.log.turn)"), UmHudLog::TurnText(3).ToString(), FString(TEXT("Х3")));
  // ---- the widget ----
  UUmHudLog* Log = CreateWidget<UUmHudLog>(W.World, UUmHudLog::StaticClass());
  if (!TestNotNull(TEXT("log"), Log)) return false;
  FString Missing;
  TestTrue(TEXT("BindWidget Lines, Scroll (+ Title, Empty)"), Log->HasAllParts(&Missing));
  FUmLogFrame F;
  F.SizeSu = FVector2D(300.0, 200.0);
  F.bTall = true;
  Log->SetFrame(F);
  TArray<FString> Lines;
  Log->CollectShotLines(Lines, FS08ScreenRect(24.0f, 712.0f, 324.0f, 912.0f));
  TestTrue(TEXT("empty: lines=0 (hud.log.empty shown)"), Lines.Num() == 1 && Lines[0].Contains(TEXT("state=lines=0")));
  for (int32 I = 1; I <= 60; ++I) {
    FUmLogEntry En;
    En.Seq = I;
    En.Turn = 1 + I / 3;
    En.TeamSlot = I % 2;
    En.Text = FText::FromString(FString::Printf(TEXT("Medusa: манёвр: Medusa M%d→M%d"), I, I + 1));
    En.Full = FText::FromString(FString::Printf(TEXT("Medusa: манёвр: Medusa M%d→M%d (full)"), I, I + 1));
    Log->Push(En, 1000.0 * I);
  }
  TestEqual(TEXT("at most 50 lines"), Log->Num(), 50);
  TestTrue(TEXT("the oldest left: the first row is seq 11"), Log->GetRowText(0).ToString().Contains(TEXT("M11→")));
  TestEqual(TEXT("the last row text.primary"), Log->GetRowColorToken(49), FName(TEXT("text.primary")));
  TestEqual(TEXT("the others text.secondary"), Log->GetRowColorToken(48), FName(TEXT("text.secondary")));
  TestTrue(TEXT("the tooltip is the full line"), Log->GetRowTooltip(49).ToString().EndsWith(TEXT("(full)")));
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  TestTrue(TEXT("team stripe: P2 team.p2.screen, P1 team.p1.screen"),
           Log->GetStripeColor(49).Equals(Theme.Color(TEXT("team.p1.screen")), 1.0e-3f) &&
               Log->GetStripeColor(48).Equals(Theme.Color(TEXT("team.p2.screen")), 1.0e-3f));
  TestEqual(TEXT("1080p: 6 rows shown"), Log->ShownRows(), 6);
  // ---- the autoscroll: follows the newest; waits while the player reads older lines ----
  const TSharedRef<SWidget> LogRootSlate = Log->TakeWidget();
  LayoutScroll(Log, LogRootSlate, 300.0f, 132.0f);
  Log->Scroll->ScrollToEnd();
  LayoutScroll(Log, LogRootSlate, 300.0f, 132.0f);
  {
    const TSharedPtr<SWidget> Sb = Log->Scroll->GetCachedWidget();
    const TSharedPtr<SWidget> Lb = Log->Lines->GetCachedWidget();
    const FString Desired = Sb.IsValid() ? Sb->GetDesiredSize().ToString() : FString(TEXT("-"));
    const FString LinesDesired = Lb.IsValid() ? Lb->GetDesiredSize().ToString() : FString(TEXT("-"));
    const FString Geom = Sb.IsValid() ? Sb->GetTickSpaceGeometry().GetLocalSize().ToString() : FString(TEXT("-"));
    AddInfo(FString::Printf(TEXT("scroll: desired %s lines %s end %.1f offset %.1f geom %s"), *Desired, *LinesDesired,
                            Log->Scroll->GetScrollOffsetOfEnd(), Log->Scroll->GetScrollOffset(), *Geom));
  }
  TestTrue(TEXT("at the end after the newest line"), Log->IsAtEnd() && Log->Scroll->GetScrollOffsetOfEnd() > 0.0f);
  Log->ScrollRowsForTest(-5.0f);
  LayoutScroll(Log, LogRootSlate, 300.0f, 132.0f);
  const float Reading = Log->Scroll->GetScrollOffset();
  TestFalse(TEXT("the player scrolled up"), Log->IsAtEnd());
  FUmLogEntry Next;
  Next.Seq = 61;
  Next.Text = FText::FromString(TEXT("King Arthur: манёвр: без движения"));
  Log->Push(Next, 61000.0);
  LayoutScroll(Log, LogRootSlate, 300.0f, 132.0f);
  TestTrue(TEXT("autoscroll waits while the player reads"), FMath::IsNearlyEqual(Log->Scroll->GetScrollOffset(), Reading, 1.0f) && !Log->IsAtEnd());
  Log->Scroll->ScrollToEnd();
  LayoutScroll(Log, LogRootSlate, 300.0f, 132.0f);
  FUmLogEntry Next2 = Next;
  Next2.Seq = 62;
  Log->Push(Next2, 62000.0);
  LayoutScroll(Log, LogRootSlate, 300.0f, 132.0f);
  TestTrue(TEXT("back at the end it follows again"), Log->IsAtEnd());
  // ---- hidden in the combat, shown after it (150 ms) ----
  Log->SetHidden(true, 70000.0);
  Lines.Reset();
  Log->CollectShotLines(Lines, FS08ScreenRect(24.0f, 712.0f, 324.0f, 912.0f));
  TestTrue(TEXT("combat: state=hidden, 0 rows"), Lines.Num() == 1 && Lines[0].Contains(TEXT("state=hidden")) && Log->ShownRows() == 0);
  Log->Tick(70200.0);
  TestEqual(TEXT("combat: collapsed after the fade"), Log->GetVisibility(), ESlateVisibility::Collapsed);
  Log->SetHidden(false, 71000.0);
  Log->Tick(71200.0);
  TestTrue(TEXT("after the combat: shown, lines=6"), Log->GetVisibility() == ESlateVisibility::Visible && Log->ShownRows() == 6);
  // ---- 720p: 3 rows from y + 38 inside the 104 su rect; class S: the list 360 x 320, 12 rows, only while open ----
  F.bTall = false;
  F.SizeSu = FVector2D(300.0, 104.0);
  Log->SetFrame(F);
  TestTrue(TEXT("720p: 3 rows, 38 + 3 x 22 = 104"), Log->ShownRows() == 3 && FMath::IsNearlyEqual(UmHudLog::FirstRowSu(F) + 3.0f * UmHudLog::RowSu, 104.0f));
  F.bClassS = true;
  F.SizeSu = UmHudLog::ListSizeSu();
  Log->SetFrame(F);
  TestEqual(TEXT("S closed: nothing"), Log->ShownRows(), 0);
  Log->SetOpen(true);
  TestEqual(TEXT("S open: 12 rows"), Log->ShownRows(), 12);
  const FBox2D List = UmHudLog::ListRectSu(FBox2D(FVector2D(16.0, 16.0), FVector2D(252.0, 56.0)));
  TestTrue(TEXT("S list under TOP: (16, 64, 360, 320)"), FMath::IsNearlyEqual(List.Min.X, 16.0) && FMath::IsNearlyEqual(List.Min.Y, 64.0) &&
                                                          FMath::IsNearlyEqual(List.GetSize().X, 360.0) && FMath::IsNearlyEqual(List.GetSize().Y, 320.0));
  // ---- budget (≤ 0.03 ms GT p95): the per-frame tick ----
  TArray<double> Ms;
  for (int32 I = 0; I < 200; ++I) {
    const double T0 = FPlatformTime::Seconds();
    Log->Tick(80000.0 + I * 16.0);
    Ms.Add((FPlatformTime::Seconds() - T0) * 1000.0);
  }
  Ms.Sort();
  AddInfo(FString::Printf(TEXT("log tick p95 %.4f ms"), Ms[189]));
  TestTrue(TEXT("tick p95 <= 0.03 ms"), Ms[189] <= 0.03);
  return true;
}

// -------------------------------------------------------------------------------------------------------------- Toast

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHudToastPlaceTest,
    "Unmatched.S08.Hud.Toast.Place chain bottom - top band - shift up - newest only - fail, the look, SHOT and TOAST lines",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHudToastPlaceTest::RunTest(const FString&) {
  using namespace UmFeedTest;
  using namespace UmHudFeed;
  FWorld W(TEXT("UmHudToastPlace"));
  if (!TestNotNull(TEXT("world"), W.World)) return false;
  FRu Ru;
  // ---- kinds by key (ВР-VS2-HB38-06), caps, holds ----
  TestTrue(TEXT("why.* error, ms.hint.* warning, hud.toast.* info"),
           KindOfKey(FName(TEXT("why.not.your.turn"))) == EUmToastKind::Error &&
               KindOfKey(FName(TEXT("ms.hint.hand.limit"))) == EUmToastKind::Warning &&
               KindOfKey(FName(TEXT("hud.toast.reconnected"))) == EUmToastKind::Info);
  TestTrue(TEXT("caps 560 / 520 / 440"), ToastCapSu(false, true) == 560.0f && ToastCapSu(false, false) == 520.0f && ToastCapSu(true, true) == 440.0f);
  TestTrue(TEXT("holds: error 4 s, others 2...4 s"), HoldSec(EUmToastKind::Error, 1.0f) == 4.0f && HoldSec(EUmToastKind::Info, 10.0f) == 4.0f &&
                                                       HoldSec(EUmToastKind::Info, 1.0f) == 2.0f && HoldSec(EUmToastKind::Warning, 3.0f) == 3.0f);
  TestEqual(TEXT("why.not.your.turn RU"), ReasonText(FS09Reason::Make(TEXT("why.not.your.turn"))).ToString(), FString(TEXT("Сейчас не ваш ход")));
  // ---- the plans: width = text + padding (+ sign, + cross), two lines at the cap, never cut ----
  const FUmToastPlan Info = UmToast::Plan(Spec(EUmToastKind::Info, TEXT("hud.toast.reconnected"), TEXT("Позиции обновлены (пропущено 0)")), 560.0f, &Est);
  const FUmToastPlan Err = UmToast::Plan(Spec(EUmToastKind::Error, TEXT("why.not.your.turn"), TEXT("Сейчас не ваш ход")), 560.0f, &Est);
  const FString Rule = TEXT("Предел руки — 7 карт. В конце хода лишние карты нужно сбросить до 7");
  const FUmToastPlan Warn = UmToast::Plan(Spec(EUmToastKind::Warning, TEXT("ms.hint.hand.limit"), Rule, true), 440.0f, &Est);
  TestTrue(TEXT("info: one line 48, no sign"), Info.Lines == 1 && Info.SizeSu.Y == 48.0 && !Info.bSign && Info.SizeSu.X <= 560.0);
  TestTrue(TEXT("error: the sign + 32 su"), Err.bSign && !Err.bClose &&
                                              FMath::IsNearlyEqual(static_cast<float>(Err.SizeSu.X), Err.TextWidthSu + 2.0f * ToastPadSu + 32.0f, 1.0f));
  TestTrue(TEXT("warning held: sign + cross, wraps to 2 lines under 440 (60 su), never wider than the cap"),
           Warn.bSign && Warn.bClose && Warn.Lines == 2 && Warn.SizeSu.Y == 60.0 && Warn.SizeSu.X <= 440.0);
  // ---- the chain on the 1080p canvas (Marmoreal FIELD) ----
  const FUmHudLayout L = Layout(FVector2D(1920.0, 1080.0), 1.0f);
  FUmFeedInput In = Input(L);
  const FVector2D One(300.0, 48.0);
  FStackInput S = FUmFeedBlocks::StackInput(In, Members({One}), FVector2D::ZeroVector);
  FUmFeedInput Free = In;
  Free.Spaces.Reset();
  FStackResult R = Place(FUmFeedBlocks::StackInput(Free, Members({One}), FVector2D::ZeroVector));
  TestTrue(TEXT("1: no space crossed - over the hand caption (bottom = caption top - 8)"),
           R.Place == EUmFeedPlace::Bottom && FMath::IsNearlyEqual(R.ToastRects[0].Max.Y, In.CaptionSu.Min.Y - 8.0, 0.01) && !R.bTop);
  R = Place(S);
  TestTrue(TEXT("at rest the spaces sit 7-13 px over the caption: the stack goes up (top / upward)"),
           R.Place == EUmFeedPlace::Top || R.Place == EUmFeedPlace::Upward);
  TestTrue(TEXT("upward: 0 px^2 with every obstacle, not above STATUS + 8, whole pixels"),
           OverlapPx2(R.ToastRects[0], S.Obstacles, 1.0f) == 0.0 && R.ToastRects[0].Min.Y >= S.MinTopSu - 0.01 &&
               FMath::IsNearlyEqual(R.ToastRects[0].Max.Y, L.FieldSu.Min.Y, 1.0) && R.bTop);
  AddInfo(FString::Printf(TEXT("1080p: %s y=%.1f field top %.1f attempts %d"), PlaceName(R.Place), R.ToastRects[0].Min.Y, L.FieldSu.Min.Y, R.Attempts));
  // the group with the long subtitle: the capsule under the toasts, 8 su, on the corridor centre
  const FVector2D Sub(493.0, 29.0);
  R = Place(FUmFeedBlocks::StackInput(In, Members({One, One}), Sub));
  TestTrue(TEXT("group: two toasts + the capsule 8 su under them, 0 px^2"),
           R.ToastRects.Num() == 2 && R.SubRect.bIsValid && FMath::IsNearlyEqual(R.SubRect.Min.Y, R.ToastRects[1].Max.Y + 8.0, 0.01) &&
               R.OverlapPx2 == 0.0 && R.ToastRects[0].Max.Y + 8.0 <= R.ToastRects[1].Min.Y + 0.01);
  TestTrue(TEXT("the capsule on the hand corridor's centre"), FMath::IsNearlyEqual(R.SubRect.GetCenter().X, 0.5 * (L.HandLeftSu + L.HandRightSu), 0.6));
  // the lowered hand (48 su visible, caption hidden): the group fits over it
  FUmFeedInput Low = In;
  Low.CardsTopSu = static_cast<float>(L.CanvasSu.Y) - 48.0f;
  Low.CaptionSu = FBox2D(ForceInit);
  Low.Blocks[0] = FBox2D(FVector2D(L.HandLeftSu, Low.CardsTopSu), FVector2D(L.HandRightSu, L.CanvasSu.Y));
  R = Place(FUmFeedBlocks::StackInput(Low, Members({One}), FVector2D(196.0, 29.0)));
  TestTrue(TEXT("lowered: bottom - the capsule 4 su over the lowered cards"),
           R.Place == EUmFeedPlace::Bottom && FMath::IsNearlyEqual(R.SubRect.Max.Y, Low.CardsTopSu - 4.0, 0.01));
  // the defense window: the spaces are no obstacle (ВР-VS2-HB38-18), the figures still are
  FUmFeedInput Combat = In;
  Combat.bCombat = true;
  R = Place(FUmFeedBlocks::StackInput(Combat, Members({One}), FVector2D::ZeroVector));
  TestEqual(TEXT("combat: the spaces do not push the stack up"), R.Place, EUmFeedPlace::Bottom);
  Combat.Figures.Add(FBox2D(FVector2D(800.0, 820.0), FVector2D(1100.0, 900.0)));
  R = Place(FUmFeedBlocks::StackInput(Combat, Members({One}), FVector2D::ZeroVector));
  TestTrue(TEXT("combat: a figure over the hand still moves it up"), R.Place != EUmFeedPlace::Bottom && R.OverlapPx2 == 0.0);
  // ---- class S (1080p 150 %): two toasts do not fit under the field - only the newest (step 4) ----
  const FUmHudLayout LS = Layout(FVector2D(1280.0, 720.0), 1.5f);
  const FUmFeedInput InS = Input(LS);
  R = Place(FUmFeedBlocks::StackInput(InS, Members({FVector2D(300.0, 48.0), FVector2D(360.0, 48.0)}), FVector2D::ZeroVector));
  TestTrue(TEXT("S: newest only, the older dropped, 0 px^2"),
           R.Place == EUmFeedPlace::Newest && R.Shown.Num() == 1 && R.Shown[0] == 1 && R.Dropped == 1 && R.OverlapPx2 == 0.0);
  AddInfo(FString::Printf(TEXT("S: y=%.1f field top %.1f band %.0f min %.0f"), R.ToastRects[0].Min.Y, LS.FieldSu.Min.Y, TopBandSSu,
                          FUmFeedBlocks::StackInput(InS, Members({One}), FVector2D::ZeroVector).MinTopSu));
  // ---- step 5: nowhere free - FAIL, the newest still shows (never silent) ----
  FUmFeedInput Full = In;
  Full.Figures.Add(FBox2D(FVector2D(0.0, 0.0), L.CanvasSu));
  R = Place(FUmFeedBlocks::StackInput(Full, Members({One, One}), FVector2D::ZeroVector));
  TestTrue(TEXT("fail: traced, overlap > 0, a toast still drawn"), R.Place == EUmFeedPlace::Fail && R.OverlapPx2 > 0.0 && R.ToastRects.Num() >= 1);
  // ---- the widgets: the look of the three kinds, the stack's SHOT and TOAST lines ----
  UUmToast* Toast = CreateWidget<UUmToast>(W.World, UUmToast::StaticClass());
  if (!TestNotNull(TEXT("toast"), Toast)) return false;
  FString Missing;
  TestTrue(TEXT("BindWidget Body, Icon, Text, CloseButton"), Toast->HasAllParts(&Missing));
  Toast->ApplySpec(Spec(EUmToastKind::Error, TEXT("why.not.your.turn"), TEXT("Сейчас не ваш ход")), Err, 1.0f);
  TestEqual(TEXT("error sign badge-refuse (IC-40)"), Toast->GetSignIcon(), FName(TEXT("badge-refuse")));
  Toast->ApplySpec(Spec(EUmToastKind::Warning, TEXT("ms.hint.hand.limit"), Rule, true), Warn, 1.0f);
  TestTrue(TEXT("warning: state-warning (IC-47) and the cross (IC-54)"), Toast->GetSignIcon() == FName(TEXT("state-warning")) && Toast->IsCloseShown());
  Toast->ApplySpec(Spec(EUmToastKind::Info, TEXT("hud.toast.reconnected"), TEXT("Позиции обновлены (пропущено 0)")), Info, 1.0f);
  TestTrue(TEXT("info: no sign, no cross"), Toast->GetSignIcon().IsNone() && !Toast->IsCloseShown());
  UUmToastStack* Stack = CreateWidget<UUmToastStack>(W.World, UUmToastStack::StaticClass());
  if (!TestNotNull(TEXT("stack"), Stack)) return false;
  TestTrue(TEXT("BindWidget Canvas (+ Badge)"), Stack->HasAllParts(&Missing));
  Stack->SetMeasureForTest(&Est);
  FUmToastFrame TF;
  Stack->SetFrame(TF);
  Stack->Push(Spec(EUmToastKind::Error, TEXT("why.not.your.turn"), TEXT("Сейчас не ваш ход")), 0.0);
  Stack->Tick(0.0, false);
  TArray<FUmToastMember> Ms;
  Stack->Members(Ms);
  S = FUmFeedBlocks::StackInput(In, Ms, FVector2D::ZeroVector);
  R = Place(S);
  Stack->ApplyPlacement(R, Ms, 0.0);
  const FString PlaceLine = Stack->TakePlaceLine();
  TestTrue(TEXT("TOAST place=top overlap=0 (04 §2.12)"), PlaceLine.StartsWith(TEXT("TOAST place=top")) && PlaceLine.Contains(TEXT(" overlap=0 ")));
  TArray<FString> Lines;
  Stack->CollectShotLines(Lines);
  const FString Shot = ShotOf(Lines, TEXT("UI-HUD-TOAST"));
  TestTrue(TEXT("SHOT UI-HUD-TOAST state=top kinds=error, no text"),
           Shot.Contains(TEXT("state=top")) && Shot.Contains(TEXT("kinds=error")) && !Shot.Contains(TEXT("ваш")));
  FUmFeedInput LowIn = Low;
  S = FUmFeedBlocks::StackInput(LowIn, Ms, FVector2D::ZeroVector);
  R = Place(S);
  Stack->ApplyPlacement(R, Ms, 10.0);
  TestTrue(TEXT("TOAST place=bottom with the lowered hand"), Stack->TakePlaceLine().StartsWith(TEXT("TOAST place=bottom")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHudToastStickyTest,
    "Unmatched.S08.Hud.Toast.Sticky the hand-limit rule held until its cross or the owner, hidden for a newer toast",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHudToastStickyTest::RunTest(const FString&) {
  using namespace UmFeedTest;
  FWorld W(TEXT("UmHudToastSticky"));
  if (!TestNotNull(TEXT("world"), W.World)) return false;
  FRu Ru;
  UUmToastStack* Stack = CreateWidget<UUmToastStack>(W.World, UUmToastStack::StaticClass());
  if (!TestNotNull(TEXT("stack"), Stack)) return false;
  Stack->SetMeasureForTest(&Est);
  Stack->SetFrame(FUmToastFrame());
  const FName Key(TEXT("ms.hint.hand.limit"));
  Stack->Push(Spec(EUmToastKind::Warning, TEXT("ms.hint.hand.limit"), TEXT("Предел руки — 7 карт. В конце хода лишние карты нужно сбросить до 7"), true), 0.0);
  const FUmHudLayout L = Layout(FVector2D(1920.0, 1080.0), 1.0f);
  FUmFeedInput In = Input(L);
  auto PlaceNow = [&](double Now) {
    TArray<FUmToastMember> Ms;
    Stack->Members(Ms);
    const UmHudFeed::FStackResult R = UmHudFeed::Place(FUmFeedBlocks::StackInput(In, Ms, FVector2D::ZeroVector));
    Stack->ApplyPlacement(R, Ms, Now);
    return R;
  };
  Stack->Tick(0.0, false);
  PlaceNow(0.0);
  Stack->Tick(30000.0, false);
  TestTrue(TEXT("held after 30 s (until the cross / the end of the turn / GAME_OVER)"), Stack->Has(Key) && Stack->NumShown() == 1);
  TArray<FBox2D> Rects;
  Stack->DrawnRectsSu(Rects);
  TestTrue(TEXT("only the held toast takes the click (its rect)"), Rects.Num() == 1 && Stack->HitsClose(Rects[0].GetCenter()) &&
                                                                    !Stack->HitsClose(FVector2D(5.0, 5.0)));
  // a newer error in a class S canvas where only one fits: the rule waits hidden, never dropped
  const FUmHudLayout LS = Layout(FVector2D(1280.0, 720.0), 1.5f);
  In = Input(LS);
  FUmToastFrame SF;
  SF.CanvasSu = LS.CanvasSu;
  SF.PxPerSu = 1.5f;
  SF.bClassS = true;
  Stack->SetFrame(SF);
  Stack->Push(Spec(EUmToastKind::Error, TEXT("why.not.your.turn"), TEXT("Сейчас не ваш ход")), 31000.0);
  Stack->Tick(31000.0, false);
  UmHudFeed::FStackResult R = PlaceNow(31000.0);
  TestTrue(TEXT("S: the newest shows, the rule waits (not leaving)"), R.Place == EUmFeedPlace::Newest && Stack->Has(Key) && Stack->NumShown() == 1);
  Stack->Tick(35500.0, false);  // the error's 4 s ran out
  Stack->Tick(35700.0, false);
  R = PlaceNow(35700.0);
  TestTrue(TEXT("after the error the rule is back"), Stack->Has(Key) && Stack->NumShown() == 1 && R.ToastRects.Num() == 1);
  // the owner closes it (the cross / the end of the turn): it leaves in 120 ms
  TestTrue(TEXT("dismiss"), Stack->Dismiss(Key, 36000.0));
  Stack->Tick(36000.0, false);
  TestFalse(TEXT("leaving: no longer held"), Stack->Has(Key));
  Stack->Tick(36200.0, false);
  TestEqual(TEXT("gone after icon.leave.ms"), Stack->NumShown(), 0);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHudToastOffMatchTest,
    "Unmatched.S08.Hud.Toast.OffMatch no toast off the live match, the reconnect toast only inside the running match",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHudToastOffMatchTest::RunTest(const FString&) {
  using namespace UmFeedTest;
  FWorld W(TEXT("UmHudToastOffMatch"));
  if (!TestNotNull(TEXT("world"), W.World)) return false;
  FRu Ru;
  UUmToastStack* Stack = CreateWidget<UUmToastStack>(W.World, UUmToastStack::StaticClass());
  if (!TestNotNull(TEXT("stack"), Stack)) return false;
  Stack->SetMeasureForTest(&Est);
  Stack->SetFrame(FUmToastFrame());
  Stack->Push(Spec(EUmToastKind::Info, TEXT("hud.toast.reconnected"), TEXT("Позиции обновлены (пропущено 0)")), 0.0);
  Stack->Tick(0.0, false);
  Stack->SetLive(true);
  TestFalse(TEXT("live: the toast stays"), Stack->IsEmpty());
  Stack->SetLive(false);
  TestTrue(TEXT("off the match (vsai-abort lobby, 2026-10-07): the stack is empty"), Stack->IsEmpty());
  TestEqual(TEXT("nothing shown"), Stack->NumShown(), 0);
  Stack->Push(Spec(EUmToastKind::Error, TEXT("why.not.your.turn"), TEXT("Сейчас не ваш ход")), 100.0);
  Stack->SetLive(false);
  TestTrue(TEXT("a push off the match is cleared too"), Stack->IsEmpty());
  // the rule of the reconnect toast: the stream back inside the running match only
  TestTrue(TEXT("back inside the match: shown"), UmHudFeed::ReconnectedToastDue(true, true, false));
  TestFalse(TEXT("left the room while recovering: none"), UmHudFeed::ReconnectedToastDue(false, true, false));
  TestFalse(TEXT("the room aborted: none"), UmHudFeed::ReconnectedToastDue(true, true, true));
  TestFalse(TEXT("no HUD (lobby): none"), UmHudFeed::ReconnectedToastDue(true, false, false));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHudToastQueueTest,
    "Unmatched.S08.Hud.Toast.Queue at most 2, the same toast renews, the banner gate, holds, fades, the refusal badge",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHudToastQueueTest::RunTest(const FString&) {
  using namespace UmFeedTest;
  FWorld W(TEXT("UmHudToastQueue"));
  if (!TestNotNull(TEXT("world"), W.World)) return false;
  FRu Ru;
  UUmToastStack* Stack = CreateWidget<UUmToastStack>(W.World, UUmToastStack::StaticClass());
  if (!TestNotNull(TEXT("stack"), Stack)) return false;
  Stack->SetMeasureForTest(&Est);
  Stack->SetFrame(FUmToastFrame());
  const int32 A = Stack->Push(Spec(EUmToastKind::Info, TEXT("hud.toast.reconnected"), TEXT("Позиции обновлены (пропущено 0)")), 0.0);
  Stack->Tick(0.0, false);
  const int32 B = Stack->Push(Spec(EUmToastKind::Error, TEXT("why.client.desync"), TEXT("Расхождение с сервером — обновляем")), 100.0);
  Stack->Tick(100.0, false);
  TArray<FUmToastMember> Ms;
  Stack->Members(Ms);
  TestTrue(TEXT("two: the older first, the newest last (at the bottom)"), Ms.Num() == 2 && Ms[0].Id == A && Ms[1].Id == B);
  const int32 C = Stack->Push(Spec(EUmToastKind::Error, TEXT("why.not.your.turn"), TEXT("Сейчас не ваш ход")), 200.0);
  Stack->Tick(200.0, false);
  Stack->Members(Ms);
  TestTrue(TEXT("a third: the oldest leaves, never more than 2"), Ms.Num() == 2 && Ms[0].Id == B && Ms[1].Id == C);
  TestEqual(TEXT("the same toast again only renews its hold"),
            Stack->Push(Spec(EUmToastKind::Error, TEXT("why.not.your.turn"), TEXT("Сейчас не ваш ход")), 300.0), C);
  // the banner gate: a new toast waits for the end of «ВАШ ХОД»
  const int32 D = Stack->Push(Spec(EUmToastKind::Info, TEXT("hud.toast.reconnected"), TEXT("Позиции обновлены (пропущено 3)")), 400.0);
  Stack->Tick(400.0, true);
  Stack->Members(Ms);
  TestFalse(TEXT("banner up: not shown yet"), Ms.ContainsByPredicate([D](const FUmToastMember& M) { return M.Id == D; }));
  Stack->Tick(1000.0, false);
  Stack->Members(Ms);
  TestTrue(TEXT("banner over: shown"), Ms.ContainsByPredicate([D](const FUmToastMember& M) { return M.Id == D; }));
  // holds: the error renewed at 300 holds 4 s -> leaves at 4300; the info (3 s) at 1000 + 3000
  Stack->Tick(4250.0, false);
  Stack->Members(Ms);
  TestTrue(TEXT("error still held at 4.25 s"), Ms.ContainsByPredicate([C](const FUmToastMember& M) { return M.Id == C; }));
  Stack->Tick(4350.0, false);
  Stack->Members(Ms);
  TestFalse(TEXT("error gone after its 4 s"), Ms.ContainsByPredicate([C](const FUmToastMember& M) { return M.Id == C; }));
  // the refusal badge: 350 ms (refuse.ms)
  Stack->ShowBadge(FVector2D(1700.0, 1000.0), 5000.0);
  TestTrue(TEXT("badge shown, 24 su"), Stack->IsBadgeShown() && FMath::IsNearlyEqual(Stack->BadgeRectSu().GetSize().X, 24.0));
  Stack->Tick(5340.0, false);
  TestTrue(TEXT("badge at 340 ms"), Stack->IsBadgeShown());
  Stack->Tick(5360.0, false);
  TestFalse(TEXT("badge gone after 350 ms"), Stack->IsBadgeShown());
  // budget (≤ 0.02 ms GT p95): the per-frame tick with two toasts
  Stack->Push(Spec(EUmToastKind::Info, TEXT("hud.toast.a"), TEXT("a")), 6000.0);
  Stack->Push(Spec(EUmToastKind::Info, TEXT("hud.toast.b"), TEXT("b")), 6000.0);
  TArray<double> T;
  for (int32 I = 0; I < 200; ++I) {
    const double T0 = FPlatformTime::Seconds();
    Stack->Tick(6000.0 + I * 5.0, false);
    T.Add((FPlatformTime::Seconds() - T0) * 1000.0);
  }
  T.Sort();
  AddInfo(FString::Printf(TEXT("toast tick p95 %.4f ms"), T[189]));
  TestTrue(TEXT("tick p95 <= 0.02 ms"), T[189] <= 0.02);
  return true;
}

// ----------------------------------------------------------------------------------------------------------- Subtitle

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHudSubtitleDurationTest,
    "Unmatched.S08.Hud.Subtitle.Duration length + 500 ms, replaced by a new line, the capsule, lowered, SHOT",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHudSubtitleDurationTest::RunTest(const FString&) {
  using namespace UmFeedTest;
  FWorld W(TEXT("UmHudSubtitle"));
  if (!TestNotNull(TEXT("world"), W.World)) return false;
  FRu Ru;
  UUmHudSubtitle* Sub = CreateWidget<UUmHudSubtitle>(W.World, UUmHudSubtitle::StaticClass());
  if (!TestNotNull(TEXT("subtitle"), Sub)) return false;
  FString Missing;
  TestTrue(TEXT("BindWidget Speaker, Line (+ Capsule)"), Sub->HasAllParts(&Missing));
  Sub->SetMeasureForTest([](const FString& T, float S, FName) { return 0.5f * S * T.Len(); });
  Sub->SetPxPerSu(1.0f, false);
  TestEqual(TEXT("«{name}:» (hud.sub.speaker)"), UmHudSubtitle::SpeakerText(TEXT("King Arthur")).ToString(), FString(TEXT("King Arthur:")));
  // ARTHUR-MATCHUP-MEDUSA-01 RU (the long line of the VO script), 1200 ms of audio -> 1700 ms
  FUmSubtitleModel M;
  M.Speaker = UmHudSubtitle::SpeakerText(TEXT("King Arthur"));
  M.Line = FText::FromString(TEXT("Оставь себе свой взгляд, горгона. Мне хватит меча."));
  M.StartMs = 1000.0;
  M.DurationMs = 1200.0 + 500.0;
  Sub->ApplyModel(M);
  const FUmSubtitlePlan P = Sub->GetPlan();
  TestTrue(TEXT("one line <= 720 su, height = line box + 2 x 5 (>= 28)"), P.Lines == 1 && P.SizeSu.X <= 720.0 && P.SizeSu.Y >= 28.0);
  TestTrue(TEXT("shown"), Sub->IsShown() && Sub->DesiredSizeSu().X > 0.0);
  Sub->ApplyPlacement(FBox2D(FVector2D(711.0, 874.0), FVector2D(711.0 + P.SizeSu.X, 874.0 + P.SizeSu.Y)), false);
  TestEqual(TEXT("never takes the mouse"), Sub->GetVisibility(), ESlateVisibility::HitTestInvisible);
  TestFalse(TEXT("t = 1.6 s: still shown"), Sub->Tick(2600.0));
  TestTrue(TEXT("t = 1.7 s: ended"), Sub->Tick(2701.0) && !Sub->IsShown());
  // a new line replaces the old one at once; ARTHUR-ATTACK-01 «Защищайся!» with the lowered hand
  Sub->ApplyModel(M);
  FUmSubtitleModel Short = M;
  Short.Line = FText::FromString(TEXT("Защищайся!"));
  Short.StartMs = 1500.0;
  Sub->ApplyModel(Short);
  TestTrue(TEXT("replaced"), Sub->GetModel().Line.EqualTo(Short.Line));
  Sub->ApplyPlacement(FBox2D(FVector2D(860.0, 999.0), FVector2D(1056.0, 1028.0)), true);
  TArray<FString> Lines;
  Sub->CollectShotLines(Lines);
  TestTrue(TEXT("SHOT UI-HUD-SUB state=shown lowered=1, no text"), Lines.Num() == 1 && Lines[0].Contains(TEXT("state=shown")) &&
                                                                      Lines[0].Contains(TEXT("lowered=1")) && !Lines[0].Contains(TEXT("Защищайся")));
  // a line longer than 720 su wraps to two rows (never cut)
  FUmSubtitleModel Long = M;
  Long.Line = FText::FromString(FString::ChrN(120, TEXT('а')) + TEXT(" ") + FString::ChrN(40, TEXT('б')));
  Sub->ApplyModel(Long);
  TestTrue(TEXT("long: two rows, <= 720 su"), Sub->GetPlan().Lines == 2 && Sub->GetPlan().SizeSu.X <= 720.0);
  Sub->Hide();
  TestFalse(TEXT("hidden: no SHOT"), Sub->IsShown());
  return true;
}

// ------------------------------------------------------------------------------------------------------------ HB-36

namespace UmFeedTest {
FUmPendingFrame PendingFrame(const FUmHudLayout& L) {
  FUmPendingFrame F;
  F.bClassS = L.bClassS;
  F.PxPerSu = L.PxPerSu;
  F.CanvasSu = L.CanvasSu;
  F.TopSu = static_cast<float>(L.Rect(EUmHudBlock::Status).Min.Y) + 48.0f + 8.0f;
  F.ModalWidthSu = L.bClassS ? 560.0f : 640.0f;
  F.ModalCapSu = L.bClassS ? 360.0f : (L.bTall ? 420.0f : 380.0f);
  F.BandLeftSu = static_cast<float>(L.Rect(EUmHudBlock::SourceSlot).Max.X) + 8.0f;
  F.BandRightSu = static_cast<float>(FMath::Min(L.Rect(EUmHudBlock::PanelOpp).Min.X, L.Rect(EUmHudBlock::OppHand).Min.X)) - 8.0f;
  return F;
}

/** The MOVE head of The Hounds of Mighty Zeus (HB-34 compact-move) and its gather input. */
struct FHounds {
  FS09CommandUi Ui;
  FS09CardView Card;
  UmHudPending::FUmPendingInput In;
  FHounds() {
    Ui.Mode = ES09CommandMode::PendingChoice;
    Ui.bHasPendingChoice = true;
    Ui.ViewerId = TEXT("p1");
    FS08PendingEffect Move;
    Move.Id = TEXT("cat-hounds-after-0-p0");
    Move.PlayerId = TEXT("p1");
    Move.Type = TEXT("MOVE");
    Move.Value = 3;
    Move.bHasValue = true;
    Ui.PendingChoice = Move;
    Ui.PendingQueue.Add(Move);
    Card.CardId = TEXT("cat-hounds");
    Card.Name = TEXT("The Hounds of Mighty Zeus");
    In.bLive = true;
    In.ViewerId = TEXT("p1");
    In.Ui = &Ui;
    In.MovePrompt = FS09Reason::Make(TEXT("ms.pending.move")).Arg(TEXT("fighterName"), TEXT("Harpies")).Arg(TEXT("n"), 3);
    In.bCanStay = true;
    In.Known.Add(Card);
  }
};
}  // namespace UmFeedTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHudPendingCompactTest,
    "Unmatched.S08.Hud.Pending.Compact MOVE on the board L two rows under STATUS, S one row in the band, collapsed 320 x 44",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHudPendingCompactTest::RunTest(const FString&) {
  using namespace UmFeedTest;
  FWorld W(TEXT("UmHudPendingCompact"));
  if (!TestNotNull(TEXT("world"), W.World)) return false;
  FRu Ru;
  FHounds H;
  const FUmPendingModel M = UmHudPending::Gather(H.In);
  TestTrue(TEXT("MOVE: compact, «Оставить на месте» and «Свернуть», no modal"), M.View == EUmPendingView::Compact && M.bStay && M.bCollapse);
  UUmHudPending* P = CreateWidget<UUmHudPending>(W.World, UUmHudPending::StaticClass());
  if (!TestNotNull(TEXT("pending"), P)) return false;
  const FUmHudLayout L = Layout(FVector2D(1920.0, 1080.0), 1.0f);
  const FUmPendingFrame F = PendingFrame(L);
  P->SetFrame(F);
  P->ApplyModel(M);
  FUmPendingPlan Plan = P->GetPlan();
  TestTrue(TEXT("L: 720 su, >= 56, two rows, 8 su under STATUS"),
           FMath::IsNearlyEqual(Plan.Panel.GetSize().X, 720.0) && Plan.Panel.GetSize().Y >= 56.0 && Plan.Hint.bIsValid &&
               Plan.Panel.Min.Y >= F.TopSu - 0.01);
  TestTrue(TEXT("L: the compact keeps out of FIELD (the spaces and the figures on them)"), Plan.Panel.Max.Y <= L.FieldSu.Min.Y);
  const FUmHudLayout LS = Layout(FVector2D(1280.0, 720.0), 1.5f);
  const FUmPendingFrame FS = PendingFrame(LS);
  P->SetFrame(FS);
  P->ApplyModel(M);
  Plan = P->GetPlan();
  TestTrue(TEXT("S: one row in the band, the hint in STATUS"), !Plan.Hint.bIsValid && Plan.Panel.Min.X >= FS.BandLeftSu - 0.01 &&
                                                                 Plan.Panel.Max.X <= FS.BandRightSu + 0.01);
  TArray<FString> Lines;
  P->CollectShotLines(Lines);
  TestTrue(TEXT("SHOT state=compact kind=MOVE"), Lines.Num() == 1 && Lines[0].Contains(TEXT("state=compact")) && Lines[0].Contains(TEXT("kind=MOVE")));
  // collapsed: «{карта}: выбор ждёт» 320 x 44 at the compact's place
  FS09PendingPresenter Presenter;
  Presenter.Observe(H.Ui.PendingChoice, 1);
  Presenter.Collapse();
  H.In.Presenter = &Presenter;
  const FUmPendingModel C = UmHudPending::Gather(H.In);
  TestEqual(TEXT("collapsed"), C.View, EUmPendingView::Collapsed);
  P->SetFrame(F);
  P->ApplyModel(C);
  Plan = P->GetPlan();
  TestTrue(TEXT("collapsed: >= 320 x 44"), Plan.Panel.GetSize().X >= 320.0 && FMath::IsNearlyEqual(Plan.Panel.GetSize().Y, 44.0, 0.5));
  Lines.Reset();
  P->CollectShotLines(Lines);
  TestTrue(TEXT("SHOT state=collapsed"), Lines.Num() == 1 && Lines[0].Contains(TEXT("state=collapsed")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHudPendingToastTest,
    "Unmatched.S08.Hud.Pending.Toast the repeating trigger is a member of UUmToastStack - placed, waits, comes back",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHudPendingToastTest::RunTest(const FString&) {
  using namespace UmFeedTest;
  FWorld W(TEXT("UmHudPendingToast"));
  if (!TestNotNull(TEXT("world"), W.World)) return false;
  FRu Ru;
  FHounds H;
  // the second open of an optional head the player answered before (SD-19 / SD-28)
  FS09PendingPresenter Presenter;
  H.Ui.PendingChoice.bOptional = true;
  Presenter.Observe(H.Ui.PendingChoice, 1);
  FS09PendingChoiceCommand Cmd;
  Cmd.EffectId = H.Ui.PendingChoice.Id;
  Cmd.FighterId = TEXT("f-h1");
  Presenter.Remember(H.Ui.PendingChoice, FS09PendingVariant::FromCommand(Cmd));
  Presenter.Clear();
  FS08PendingEffect Again = H.Ui.PendingChoice;
  Again.Id = TEXT("cat-hounds-after-0-p9");
  H.Ui.PendingChoice = Again;
  Presenter.Observe(Again, 3);
  H.In.Presenter = &Presenter;
  H.In.RememberedChoice = TEXT("Harpies 1");
  const FUmPendingModel M = UmHudPending::Gather(H.In);
  if (Presenter.Present != ES09PendingPresent::Toast) {
    AddInfo(TEXT("the presenter chose a non-toast form for this signature"));
    return true;
  }
  TestEqual(TEXT("toast form"), M.View, EUmPendingView::Toast);
  UUmToastStack* Stack = CreateWidget<UUmToastStack>(W.World, UUmToastStack::StaticClass());
  UUmHudPending* P = CreateWidget<UUmHudPending>(W.World, UUmHudPending::StaticClass());
  if (!TestNotNull(TEXT("stack"), Stack) || !TestNotNull(TEXT("pending"), P)) return false;
  Stack->SetMeasureForTest(&Est);
  const FUmHudLayout L = Layout(FVector2D(1920.0, 1080.0), 1.0f);
  FUmFeedInput In = Input(L);
  Stack->SetFrame(FUmToastFrame());
  const FVector2D Size(UmHudPending::ToastWidthSu(false, true), 48.0);
  Stack->SetExternal(true, Size, 0.0);
  Stack->Tick(0.0, false);
  auto PlaceNow = [&](double Now) {
    TArray<FUmToastMember> Ms;
    Stack->Members(Ms);
    const UmHudFeed::FStackResult R = UmHudFeed::Place(FUmFeedBlocks::StackInput(In, Ms, FVector2D::ZeroVector));
    Stack->ApplyPlacement(R, Ms, Now);
    return R;
  };
  UmHudFeed::FStackResult R = PlaceNow(0.0);
  const FBox2D Rect = Stack->GetExternalRect();
  TestTrue(TEXT("the stack places the trigger: 560 x 48, 0 px^2"), Rect.bIsValid && FMath::IsNearlyEqual(Rect.GetSize().X, 560.0) && R.OverlapPx2 == 0.0);
  FUmPendingFrame F = PendingFrame(L);
  F.ToastSu = Rect;
  P->SetFrame(F);
  P->ApplyModel(M);
  TestTrue(TEXT("the pending block draws it at the stack's rect"), P->GetPlan().Panel.bIsValid &&
                                                                     FMath::IsNearlyEqual(P->GetPlan().Panel.Min.Y, Rect.Min.Y, 0.5));
  TArray<FString> Lines;
  Stack->CollectShotLines(Lines);
  TestTrue(TEXT("SHOT UI-HUD-TOAST kinds=pending external=1"), ShotOf(Lines, TEXT("UI-HUD-TOAST")).Contains(TEXT("external=1")));
  // a refusal in class S: only one fits - the newest error shows, the trigger waits hidden (step 4), then comes back
  const FUmHudLayout LS = Layout(FVector2D(1280.0, 720.0), 1.5f);
  In = Input(LS);
  FUmToastFrame SF;
  SF.CanvasSu = LS.CanvasSu;
  SF.PxPerSu = 1.5f;
  SF.bClassS = true;
  Stack->SetFrame(SF);
  Stack->SetExternal(true, FVector2D(UmHudPending::ToastWidthSu(true, false), 48.0), 100.0);
  Stack->Push(Spec(EUmToastKind::Error, TEXT("why.not.your.turn"), TEXT("Сейчас не ваш ход")), 100.0);
  Stack->Tick(100.0, false);
  R = PlaceNow(100.0);
  TestTrue(TEXT("S: the error shows, the trigger waits"), R.Place == EUmFeedPlace::Newest && !Stack->GetExternalRect().bIsValid);
  F = PendingFrame(LS);
  F.ToastSu = Stack->GetExternalRect();
  F.bToastWaits = !F.ToastSu.bIsValid;
  P->SetFrame(F);
  P->ApplyModel(M);
  TestTrue(TEXT("the pending toast hidden while it waits"), !P->GetPlan().Panel.bIsValid && P->GetVisibility() == ESlateVisibility::Collapsed);
  Stack->Tick(4200.0, false);
  Stack->Tick(4400.0, false);
  R = PlaceNow(4400.0);
  TestTrue(TEXT("after the error: the trigger back in the stack"), Stack->GetExternalRect().bIsValid);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHudPendingOppTest,
    "Unmatched.S08.Hud.Pending.Opp the opponent's choice grey, >= 320 su, no buttons, SHOT state=opp",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHudPendingOppTest::RunTest(const FString&) {
  using namespace UmFeedTest;
  FWorld W(TEXT("UmHudPendingOpp"));
  if (!TestNotNull(TEXT("world"), W.World)) return false;
  FRu Ru;
  FS09CommandUi Opp;
  Opp.ViewerId = TEXT("p1");
  FS08PendingEffect Hiss;
  Hiss.Id = TEXT("discard-choice-cat-hiss-after-0-21");
  Hiss.PlayerId = TEXT("p2");
  Hiss.Type = TEXT("DISCARD_CARDS");
  Opp.PendingQueue.Add(Hiss);
  Opp.bHasPendingChoice = true;
  UmHudPending::FUmPendingInput In;
  In.bLive = true;
  In.ViewerId = TEXT("p1");
  In.Ui = &Opp;
  FS09CardView Card;
  Card.CardId = TEXT("cat-hiss");
  Card.Name = TEXT("Hiss and Slither");
  In.Known.Add(Card);
  In.bStatusSaysOpp = false;  // STATUS does not say it (one text once, ВР-VS4-05)
  const FUmPendingModel M = UmHudPending::Gather(In);
  TestTrue(TEXT("grey: the source card and «Соперник делает выбор»"), M.View == EUmPendingView::Opp && !M.Text.IsEmpty());
  TestEqual(TEXT("why.wait.opponent.choice"), M.Text, UmText::Get(EUmTable::Why, TEXT("why.wait.opponent.choice")).ToString());
  UUmHudPending* P = CreateWidget<UUmHudPending>(W.World, UUmHudPending::StaticClass());
  if (!TestNotNull(TEXT("pending"), P)) return false;
  const FUmHudLayout L = Layout(FVector2D(1920.0, 1080.0), 1.0f);
  P->SetFrame(PendingFrame(L));
  P->ApplyModel(M);
  TestTrue(TEXT(">= 320 su, no buttons"), P->GetPlan().Panel.GetSize().X >= 320.0 && P->GetPlan().Buttons.Num() == 0);
  TArray<FString> Lines;
  P->CollectShotLines(Lines);
  TestTrue(TEXT("SHOT state=opp tone=grey, no card name"), Lines.Num() == 1 && Lines[0].Contains(TEXT("state=opp")) &&
                                                             Lines[0].Contains(TEXT("tone=grey")) && !Lines[0].Contains(TEXT("Hiss")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHudPendingDiscardTest,
    "Unmatched.S08.Hud.Pending.Discard the hand-limit discard compact, no cancel, why.discard.count, the +N chip >= 21 px",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHudPendingDiscardTest::RunTest(const FString&) {
  using namespace UmFeedTest;
  FWorld W(TEXT("UmHudPendingDiscard"));
  if (!TestNotNull(TEXT("world"), W.World)) return false;
  FRu Ru;
  FS09CommandUi Limit;
  Limit.Mode = ES09CommandMode::DiscardDraft;
  Limit.PendingDiscard.Count = 2;
  Limit.DiscardSelection.Add(TEXT("a"));
  UmHudPending::FUmPendingInput In;
  In.bLive = true;
  In.Ui = &Limit;
  const FUmPendingModel M = UmHudPending::Gather(In);
  TestTrue(TEXT("compact discard (LIMIT)"), M.View == EUmPendingView::Compact && M.Compact == EUmPendingCompact::Discard && M.Kind == TEXT("LIMIT"));
  TestTrue(TEXT("«Сбросьте 2: выбрано 1/2»"), M.Text.Contains(TEXT("2")) && M.Text.Contains(TEXT("1/2")));
  TestEqual(TEXT("«Подтвердить» refused with why.discard.count"), M.ConfirmWhy.Key, FName(TEXT("why.discard.count")));
  TestTrue(TEXT("no cancel at the limit: no «Отказаться», no «Назад», no «Свернуть»"), !M.bDecline && !M.bBack && !M.bCollapse);
  UUmHudPending* P = CreateWidget<UUmHudPending>(W.World, UUmHudPending::StaticClass());
  if (!TestNotNull(TEXT("pending"), P)) return false;
  P->SetFrame(PendingFrame(Layout(FVector2D(1920.0, 1080.0), 1.0f)));
  P->ApplyModel(M);
  TArray<FString> Lines;
  P->CollectShotLines(Lines);
  TestTrue(TEXT("SHOT state=compact kind=LIMIT"), Lines.Num() == 1 && Lines[0].Contains(TEXT("state=compact")) && Lines[0].Contains(TEXT("kind=LIMIT")));
  // IC-34 П-2: a glyph with a number (the «+N» chip of a BOOST candidate) >= 21 px - 32 su below 1 px per su, else 24
  TestTrue(TEXT("+N chip: 720p 100 % 32 su x 0.75 = 24 px >= 21"), UmCardWidget::ChipSuFor(0.75f) * 0.75f >= 21.0f);
  TestTrue(TEXT("+N chip: 1080p 100 % 24 su = 24 px"), UmCardWidget::ChipSuFor(1.0f) >= 21.0f);
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
