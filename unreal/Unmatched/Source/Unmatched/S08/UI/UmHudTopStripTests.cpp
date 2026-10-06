// VS-2 HB-14...HB-16 tests (docs/game-design/visual/06-tasks/hud.csv HB-14, HB-15, HB-16; 04-hud-spec.md §2.1, §2.4,
// §2.5, §7.1):
//   Unmatched.S08.Hud.Top.Tree      UUmHudTop: BuildDefaultTree and WBP_UI_HUD_TOP, every BindWidget, the plate never
//                                   takes the mouse, L / S squares 44 / 40, «Журнал» only in S, «Ход 7» (no caps), the
//                                   ui-menu / ui-log glyphs on flat buttons, the SHOT lines.
//   Unmatched.S08.Hud.Top.Conn      CONN by input (ВР-VS2-43): online / syncing / lost, the in-flight timer, the icon and
//                                   its change animation, the tooltip after 300 ms, the SHOT state.
//   Unmatched.S08.Hud.Status.Tree   UUmHudStatusLine: trees, hidden without a line, the 48 su capsule, the em of the
//                                   type scale (ВР-VS2-41).
//   Unmatched.S08.Hud.Status.Keys   every state of 04 §2.5 gives its key and SHOT state; no key letter in the text
//                                   (ВР-H09); RU defend in S - two lines without «…», «Без защиты» whole; the 24 -> 20 ->
//                                   16 -> «…» fit; key chips; the pulse and the fade (ВР-VS2-46...48).
//   Unmatched.S08.Hud.Banner.Alpha  0 / 100 / 450 / 600 ms -> 0 / 1 / 1 / 0, reduced 100 ms, never in the opponent's
//                                   turn, hit-test invisible, the SHOT line only while shown (ВР-VS2-49).
// Headless: node tools/s08/run-ue-tests.cjs "Unmatched.S08.Hud" <abs log>
#if WITH_AUTOMATION_TESTS

#include "UmButton.h"
#include "UmConnectionBadge.h"
#include "UmHudBanner.h"
#include "UmHudStatusLine.h"
#include "UmHudTheme.h"
#include "UmHudTop.h"
#include "UmText.h"
#include "UmTopStrip.h"
#include "../S08AnimatedIconWidget.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/Image.h"
#include "Components/SizeBox.h"
#include "Components/TextBlock.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Framework/Application/SlateApplication.h"
#include "Fonts/FontMeasure.h"
#include "Internationalization/Internationalization.h"
#include "Internationalization/TextLocalizationManager.h"
#include "Internationalization/Regex.h"
#include "Misc/AutomationTest.h"
#include "Rendering/SlateRenderer.h"

namespace UmTopStripTest {
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

/** RU for the test (the game default), the editor culture back at the end. */
struct FRu {
  FInternationalization::FCultureStateSnapshot Snapshot;
  FRu() {
    FInternationalization::Get().BackupCultureState(Snapshot);
    Use(TEXT("ru"));
  }
  ~FRu() { FInternationalization::Get().RestoreCultureState(Snapshot); }
  static void Use(const TCHAR* Culture) {
    FInternationalization::Get().SetCurrentLanguageAndLocale(Culture);
    FTextLocalizationManager::Get().EnableGameLocalizationPreview(Culture);
    FTextLocalizationManager::Get().WaitForAsyncTasks();
  }
};

bool ShotLineOk(const FString& Line) {
  FRegexMatcher M(FRegexPattern(TEXT("^SHOT widget id=(\\S+) impl=(umg|slate) state=(\\S+) fighter=(\\S+) "
                                     "bbox=\\((-?\\d+),(-?\\d+),(-?\\d+),(-?\\d+)\\) geom=(painted|unpainted) visible=([01]) "
                                     "twin=([01]) source=(\\S+)( .*)?$")),
                  Line);
  return M.FindNext();
}

bool Visible(const UWidget* W) { return W && W->GetVisibility() != ESlateVisibility::Collapsed; }

FS09TurnStatusInput OwnTurn() {
  FS09TurnStatusInput In;
  In.bViewerTurn = true;
  In.ActionsRemaining = 2;
  return In;
}
}  // namespace UmTopStripTest

// ------------------------------------------------------------------------------------------------------------- TOP

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHudTopTreeTest, "Unmatched.S08.Hud.Top.Tree",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHudTopTreeTest::RunTest(const FString&) {
  using namespace UmTopStripTest;
  FWorld W(TEXT("UmHudTopTree"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  FRu Ru;
  UUmHudTop* Code = CreateWidget<UUmHudTop>(W.World, UUmHudTop::StaticClass());
  if (!TestNotNull(TEXT("top"), Code)) return false;
  FString Missing;
  TestTrue(TEXT("code default tree"), Code->UsesCodeDefaultTree());
  TestTrue(FString::Printf(TEXT("every part bound (missing %s)"), *Missing), Code->HasAllParts(&Missing));
  UClass* Wbp = UUmHudTop::WidgetClass();
  if (Wbp != UUmHudTop::StaticClass()) {
    UUmHudTop* FromWbp = CreateWidget<UUmHudTop>(W.World, Wbp);
    TestTrue(TEXT("WBP_UI_HUD_TOP: authored tree"), FromWbp && !FromWbp->UsesCodeDefaultTree());
    TestTrue(FString::Printf(TEXT("WBP_UI_HUD_TOP: every part bound (missing %s)"), *Missing),
             FromWbp && FromWbp->HasAllParts(&Missing));
    TestTrue(TEXT("WBP_UI_HUD_TOP: the chip is WBP_UmConnectionBadge"),
             FromWbp && FromWbp->Conn && FromWbp->Conn->SourceName().Contains(TEXT("WBP_UmConnectionBadge")));
    // a WBP does not keep the composite theme font: without the reload «Ход 7» draws as tofu (gallery 2026-10-06)
    TestTrue(TEXT("WBP_UI_HUD_TOP: «Ход n» has a real font"), FromWbp && FromWbp->TurnText->GetFont().HasValidFont());
  } else {
    AddWarning(TEXT("WBP_UI_HUD_TOP not authored yet: only the code tree checked"));
  }
  // nothing but the two buttons and the chip takes the mouse
  TestTrue(TEXT("the plate is SelfHitTestInvisible"), Code->Plate->GetVisibility() == ESlateVisibility::SelfHitTestInvisible);
  TestTrue(TEXT("the root is SelfHitTestInvisible"), Code->GetVisibility() == ESlateVisibility::SelfHitTestInvisible);
  // L: 44 su squares, no log button, «Ход 7»
  FUmTopModel M;
  M.TurnCount = 7;
  M.Conn = EUmConnState::Online;
  Code->ApplyModel(M);
  TestEqual(TEXT("L: «Ход 7», not caps"), Code->TurnText->GetText().ToString(), FString(TEXT("Ход 7")));
  TestEqual(TEXT("L: menu square 44 su"), Code->MenuButton->GetModel().HeightSu, 44.0f);
  TestEqual(TEXT("L: menu min width 44 su"), Code->MenuButton->GetModel().MinWidthSu, 44.0f);
  TestTrue(TEXT("L: the menu button is flat (CX-08)"), Code->MenuButton->GetModel().bFlat);
  TestFalse(TEXT("L: no «Журнал» button (ВР-H07)"), Visible(Code->LogButton));
  TestTrue(TEXT("the menu takes the mouse"), Code->MenuButton->GetVisibility() == ESlateVisibility::Visible);
  TestTrue(TEXT("ВР-VS2-42: the ui-menu glyph (IC-53) loads"), Code->HasMenuGlyph());
  TestTrue(TEXT("the glyph button has no label"), Code->MenuButton->GetModel().Label.IsEmpty());
  TestEqual(TEXT("the word as the menu tooltip"), Code->MenuButton->GetToolTipText().ToString(), FString(TEXT("Меню")));
  TestEqual(TEXT("L: the chip zone 44 su"), Code->Conn->Box->GetWidthOverride(), 44.0f);
  // S: 40 su, the log button with its glyph
  M.bClassS = true;
  Code->ApplyModel(M);
  TestTrue(TEXT("S: «Журнал» shown"), Code->LogButton->GetVisibility() == ESlateVisibility::Visible);
  TestEqual(TEXT("S: squares 40 su"), Code->LogButton->GetModel().HeightSu, 40.0f);
  TestEqual(TEXT("S: the chip zone 40 su"), Code->Conn->Box->GetWidthOverride(), 40.0f);
  TestTrue(TEXT("ВР-VS2-42: the ui-log glyph (IC-55) loads"), Code->HasLogGlyph());
  TestEqual(TEXT("the word as the log tooltip"), Code->LogButton->GetToolTipText().ToString(), FString(TEXT("Журнал")));
  // no turn yet: the text is hidden, the row keeps its place
  M.TurnCount = 0;
  Code->ApplyModel(M);
  TestTrue(TEXT("turn 0: hidden"), Code->TurnText->GetVisibility() == ESlateVisibility::Hidden);
  // the SHOT lines of the gate (04 §4.5, §7.1)
  M.TurnCount = 3;
  M.bClassS = false;
  Code->ApplyModel(M);
  TArray<FString> Lines;
  Code->CollectShotLines(Lines, FS08ScreenRect(24.0f, 24.0f, 276.0f, 68.0f), FS08ScreenRect(68.0f, 24.0f, 112.0f, 68.0f));
  TestEqual(TEXT("two lines: TOP and CONN"), Lines.Num(), 2);
  if (Lines.Num() == 2) {
    AddInfo(Lines[0]);
    AddInfo(Lines[1]);
    TestTrue(TEXT("TOP line format"), ShotLineOk(Lines[0]) && Lines[0].StartsWith(TEXT("SHOT widget id=UI-HUD-TOP impl=umg state=idle "
                                                                                       "fighter=none bbox=(24,24,276,68) geom=painted visible=1")));
    TestTrue(TEXT("TOP line: turn and glyph"), Lines[0].Contains(TEXT("turn=3 class=L menu=glyph log=0")));
    TestTrue(TEXT("CONN line format"), ShotLineOk(Lines[1]) && Lines[1].StartsWith(TEXT("SHOT widget id=UI-HUD-CONN impl=umg state=online ")));
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHudTopConnTest, "Unmatched.S08.Hud.Top.Conn",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHudTopConnTest::RunTest(const FString&) {
  using namespace UmTopStripTest;
  // ---- the rule (ВР-VS2-43) ----
  struct FCase {
    bool bReady, bWas, bSlow, bRecover;
    EUmConnState Want;
  };
  const FCase Cases[] = {
      {true, true, false, false, EUmConnState::Online},   {true, true, true, false, EUmConnState::Syncing},
      {true, true, false, true, EUmConnState::Syncing},   {false, true, false, false, EUmConnState::Lost},
      {false, true, true, true, EUmConnState::Lost},      {false, false, false, false, EUmConnState::Syncing},
  };
  for (const FCase& C : Cases) {
    FUmConnInput In;
    In.bStreamReady = C.bReady;
    In.bWasReady = C.bWas;
    In.bCommandSlow = C.bSlow;
    In.bRecovering = C.bRecover;
    TestEqual(FString::Printf(TEXT("ready=%d was=%d slow=%d recovering=%d"), C.bReady, C.bWas, C.bSlow, C.bRecover),
              FString(UmConnection::StateName(UmConnection::Resolve(In))), FString(UmConnection::StateName(C.Want)));
  }
  // ---- the strip: the join, the in-flight timer, the loss, one trace line per change ----
  FUmTopStrip Strip;
  FUmTopStripTick T;
  T.bStreamReady = false;
  T.NowSeconds = 10.0;
  TestTrue(TEXT("join, stream not ready yet: a line"), Strip.Tick(T).StartsWith(TEXT("HUD-CONN state=syncing")));
  TestEqual(TEXT("join: syncing, not lost"), Strip.GetConn(), EUmConnState::Syncing);
  T.bStreamReady = true;
  TestTrue(TEXT("ready: online"), Strip.Tick(T).StartsWith(TEXT("HUD-CONN state=online")) && Strip.GetConn() == EUmConnState::Online);
  TestTrue(TEXT("no change, no line"), Strip.Tick(T).IsEmpty());
  T.bInFlight = true;
  Strip.Tick(T);
  T.NowSeconds = 12.9;
  Strip.Tick(T);
  TestEqual(TEXT("a command in flight 2.9 s: still online"), Strip.GetConn(), EUmConnState::Online);
  T.NowSeconds = 13.0;
  Strip.Tick(T);
  TestEqual(TEXT("in flight 3 s (CommandSlowSeconds): syncing"), Strip.GetConn(), EUmConnState::Syncing);
  T.bInFlight = false;
  Strip.Tick(T);
  TestEqual(TEXT("answered: online"), Strip.GetConn(), EUmConnState::Online);
  T.bManeuverSlow = true;
  Strip.Tick(T);
  TestEqual(TEXT("IsCommandSlow: syncing"), Strip.GetConn(), EUmConnState::Syncing);
  T.bManeuverSlow = false;
  T.bRecovering = true;
  Strip.Tick(T);
  TestEqual(TEXT("state recovery (the seq gap): syncing"), Strip.GetConn(), EUmConnState::Syncing);
  T.bRecovering = false;
  T.bStreamReady = false;
  TestTrue(TEXT("the stream drops: lost"), Strip.Tick(T).StartsWith(TEXT("HUD-CONN state=lost ready=0 wasReady=1")));
  // ---- the chip ----
  FWorld W(TEXT("UmHudConn"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  FRu Ru;
  UUmConnectionBadge* Badge = CreateWidget<UUmConnectionBadge>(W.World, UUmConnectionBadge::StaticClass());
  if (!TestNotNull(TEXT("badge"), Badge)) return false;
  FString Missing;
  TestTrue(FString::Printf(TEXT("every part bound (missing %s)"), *Missing), Badge->HasAllParts(&Missing));
  UClass* Wbp = UUmConnectionBadge::WidgetClass();
  if (Wbp != UUmConnectionBadge::StaticClass()) {
    UUmConnectionBadge* FromWbp = CreateWidget<UUmConnectionBadge>(W.World, Wbp);
    TestTrue(TEXT("WBP_UmConnectionBadge: authored tree, every part"), FromWbp && !FromWbp->UsesCodeDefaultTree() && FromWbp->HasAllParts());
  }
  double Clock = 100.0;
  Badge->SetClockForTest([&Clock]() { return Clock; });
  Badge->ApplyState(EUmConnState::Online);
  TestEqual(TEXT("online: the bars"), Badge->GetShownIcon(), FName(TEXT("resource-connection-online")));
  TestEqual(TEXT("the first state shows at rest"), Badge->GetLastAnim(), FName(TEXT("rest")));
  Badge->ApplyState(EUmConnState::Lost);
  TestEqual(TEXT("lost: bars + X"), Badge->GetShownIcon(), FName(TEXT("resource-connection-lost")));
  TestEqual(TEXT("online -> lost: the contract's appear_from_online"), Badge->GetLastAnim(), FName(TEXT("appear_from_online")));
  Badge->ApplyState(EUmConnState::Syncing, UmConnection::ZoneSSu);
  TestEqual(TEXT("syncing: bars + ↻ (no fourth icon)"), Badge->GetShownIcon(), FName(TEXT("resource-connection-reconnecting")));
  TestEqual(TEXT("lost -> syncing: appear"), Badge->GetLastAnim(), FName(TEXT("appear")));
  TestEqual(TEXT("S zone 40 su"), Badge->Box->GetWidthOverride(), 40.0f);
  if (Badge->Icon && !S08IconMotion::IsReducedMotion()) {
    const float After = Badge->Icon->GetClockMs() + 400.0f;
    TestTrue(TEXT("syncing: the ↻ cycles after its appear (icon.reconnect.ms)"), Badge->Icon->GetAnimator().IsCycling(After));
  }
  // the tooltip after 300 ms of hover
  Badge->SimulateHover(true);
  Clock += 0.2;
  Badge->TickForTest();
  TestFalse(TEXT("hover 200 ms: no tooltip yet"), Badge->IsTooltipShown());
  Clock += 0.11;
  Badge->TickForTest();
  TestTrue(TEXT("hover 310 ms: the tooltip"), Badge->IsTooltipShown());
  TestEqual(TEXT("RU syncing tooltip"), Badge->GetToolTipText().ToString(), FString(TEXT("Синхронизация…")));
  Badge->SimulateHover(false);
  TestFalse(TEXT("leave: no tooltip"), Badge->IsTooltipShown());
  const TPair<EUmConnState, const TCHAR*> States[] = {
      {EUmConnState::Online, TEXT("online")}, {EUmConnState::Syncing, TEXT("syncing")}, {EUmConnState::Lost, TEXT("lost")}};
  for (const auto& S : States) {
    Badge->ApplyState(S.Key);
    const FString Line = Badge->ShotLine(FS08ScreenRect(68.0f, 24.0f, 112.0f, 68.0f), Badge->SourceName());
    TestTrue(FString::Printf(TEXT("SHOT state=%s (%s)"), S.Value, *Line),
             ShotLineOk(Line) && Line.Contains(FString::Printf(TEXT("id=UI-HUD-CONN impl=umg state=%s "), S.Value)) &&
                 Line.Contains(TEXT("geom=painted visible=1")));
  }
  return true;
}

// ---------------------------------------------------------------------------------------------------------- STATUS

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHudStatusTreeTest, "Unmatched.S08.Hud.Status.Tree",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHudStatusTreeTest::RunTest(const FString&) {
  using namespace UmTopStripTest;
  FWorld W(TEXT("UmHudStatusTree"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  FRu Ru;
  UUmHudStatusLine* Line = CreateWidget<UUmHudStatusLine>(W.World, UUmHudStatusLine::StaticClass());
  if (!TestNotNull(TEXT("status"), Line)) return false;
  FString Missing;
  TestTrue(TEXT("code default tree"), Line->UsesCodeDefaultTree());
  TestTrue(FString::Printf(TEXT("every part bound (missing %s)"), *Missing), Line->HasAllParts(&Missing));
  UClass* Wbp = UUmHudStatusLine::WidgetClass();
  if (Wbp != UUmHudStatusLine::StaticClass()) {
    UUmHudStatusLine* FromWbp = CreateWidget<UUmHudStatusLine>(W.World, Wbp);
    TestTrue(FString::Printf(TEXT("WBP_UI_HUD_STATUS: authored tree, every part (missing %s)"), *Missing),
             FromWbp && !FromWbp->UsesCodeDefaultTree() && FromWbp->HasAllParts(&Missing));
    TestTrue(TEXT("WBP_UI_HUD_STATUS: text and key chips have a real font"),
             FromWbp && FromWbp->StatusText->GetFont().HasValidFont() &&
                 Cast<UTextBlock>(FromWbp->WidgetTree->FindWidget(TEXT("KeyText0")))->GetFont().HasValidFont());
  } else {
    AddWarning(TEXT("WBP_UI_HUD_STATUS not authored yet: only the code tree checked"));
  }
  TestFalse(TEXT("nothing before the first line"), Line->IsShown());
  FS09TurnStatusInput Over;
  Over.bGameOver = true;
  Line->ApplyModel(Over);
  TestFalse(TEXT("game over: no line, hidden"), Line->IsShown());
  Line->ApplyModel(OwnTurn());
  TestTrue(TEXT("own turn: shown"), Line->IsShown());
  TestEqual(TEXT("one line: the capsule is 48 su"), static_cast<float>(Line->GetBodySizeSu().Y), 48.0f);
  TestTrue(TEXT("the capsule never takes the mouse (no «…»)"), Line->Body->GetVisibility() == ESlateVisibility::HitTestInvisible);
  TestFalse(TEXT("no pulse dot in the own turn"), Visible(Line->PulseDot));
  TestFalse(TEXT("no key chip by default (UI-ACC-017 off until HB-43)"), Visible(Line->KeyChip));
  // ВР-VS2-41: the type scale is the em in su - 24 su draws a ~28 su line, not 37 (Slate points at 96 DPI)
  if (FSlateApplication::IsInitialized() && FSlateApplication::Get().GetRenderer()) {
    const FSlateFontInfo Font = UUmHudTheme::Get().Font(TEXT("type.heading"));
    const float LineSu = FSlateApplication::Get().GetRenderer()->GetFontMeasureService()->GetMaxCharacterHeight(Font);
    AddInfo(FString::Printf(TEXT("type.heading: %.2f pt, line %.1f su"), Font.Size, LineSu));
    TestTrue(TEXT("ВР-VS2-41: type.heading 24 su -> a line of 24..32 su"), LineSu >= 24.0f && LineSu < 32.0f);
    TestEqual(TEXT("ВР-VS2-41: 24 su = 18 pt"), Font.Size, 18.0f);
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHudStatusKeysTest, "Unmatched.S08.Hud.Status.Keys",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHudStatusKeysTest::RunTest(const FString&) {
  using namespace UmTopStripTest;
  FWorld W(TEXT("UmHudStatusKeys"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  FRu Ru;
  UUmHudStatusLine* Line = CreateWidget<UUmHudStatusLine>(W.World, UUmHudStatusLine::StaticClass());
  if (!TestNotNull(TEXT("status"), Line)) return false;
  double Clock = 50.0;
  Line->SetClockForTest([&Clock]() { return Clock; });
  Line->SetReducedMotionForTest(false);
  FUmStatusFrame Frame;
  Frame.MaxWidthSu = 880.0f;
  Line->SetFrame(Frame);
  // ---- every state of 04 §2.5 -> its key and its SHOT state ----
  struct FCase {
    const TCHAR* Name;
    FS09TurnStatusInput In;
    const TCHAR* Key;
    EUmStatusState State;
  };
  TArray<FCase> Cases;
  {
    FS09TurnStatusInput In = OwnTurn();
    Cases.Add({TEXT("action"), In, TEXT("ms.status.action"), EUmStatusState::Own});
    In.ActionsRemaining = 0;
    Cases.Add({TEXT("end"), In, TEXT("ms.status.end"), EUmStatusState::Own});
    In = OwnTurn();
    In.Mode = ES09CommandMode::ManeuverDraft;
    Cases.Add({TEXT("fighter"), In, TEXT("ms.status.fighter"), EUmStatusState::Own});
    In.SelectedFighterName = TEXT("Medusa");
    Cases.Add({TEXT("space"), In, TEXT("ms.status.space"), EUmStatusState::Own});
    In = OwnTurn();
    In.Mode = ES09CommandMode::AttackDraft;
    Cases.Add({TEXT("attacker"), In, TEXT("ms.status.attacker"), EUmStatusState::Own});
    In.AttackerName = TEXT("Medusa");
    Cases.Add({TEXT("target"), In, TEXT("ms.status.target"), EUmStatusState::Own});
    In.TargetName = TEXT("King Arthur");
    Cases.Add({TEXT("attack.card"), In, TEXT("ms.status.attack.card"), EUmStatusState::Own});
    In.bAttackCard = true;
    Cases.Add({TEXT("attack.go"), In, TEXT("ms.status.attack.go"), EUmStatusState::Own});
    In = OwnTurn();
    In.Mode = ES09CommandMode::SchemeChoice;
    Cases.Add({TEXT("scheme"), In, TEXT("ms.status.scheme"), EUmStatusState::Own});
    In = FS09TurnStatusInput();
    In.Mode = ES09CommandMode::CombatDefense;
    Cases.Add({TEXT("defend"), In, TEXT("ms.status.defend"), EUmStatusState::Defend});
    In = OwnTurn();
    In.Mode = ES09CommandMode::DiscardDraft;
    In.DiscardNeed = 2;
    Cases.Add({TEXT("discard"), In, TEXT("ms.status.discard"), EUmStatusState::Discard});
    In = OwnTurn();
    In.Mode = ES09CommandMode::PendingChoice;
    In.PendingPrompt = FS09Reason::Make(TEXT("ms.status.choice")).Arg(TEXT("choice"), TEXT("Можете усилить эту атаку."));
    Cases.Add({TEXT("choice"), In, TEXT("ms.status.choice"), EUmStatusState::Choice});
    In = FS09TurnStatusInput();
    In.OpponentVerb = ES09OpponentVerb::Turn;
    In.OpponentName = TEXT("King Arthur");
    Cases.Add({TEXT("opp"), In, TEXT("ms.status.opp"), EUmStatusState::Opp});
    In.OpponentVerb = ES09OpponentVerb::Maneuver;  // VS_AI thinks: the same keys (ВР-VS2-HB13-03)
    Cases.Add({TEXT("ai"), In, TEXT("ms.status.opp"), EUmStatusState::Opp});
    In = OwnTurn();
    In.bCombatAttacking = true;
    Cases.Add({TEXT("wait defender"), In, TEXT("why.wait.defender"), EUmStatusState::Opp});
    In = OwnTurn();
    In.bSyncing = true;
    Cases.Add({TEXT("sync"), In, TEXT("why.syncing"), EUmStatusState::Sync});
  }
  TSet<FString> StatesSeen;
  const TCHAR* const KeyLetters[] = {TEXT("(M)"), TEXT("(A)"), TEXT("(G)"), TEXT("(E)"), TEXT("(N)"), TEXT("(R)"),
                                     TEXT("(Enter)"), TEXT("(1–9)")};
  for (const FCase& C : Cases) {
    Line->ApplyModel(C.In);
    const FString Text = Line->GetFullText();
    TestEqual(FString::Printf(TEXT("%s: key"), C.Name), Line->GetLineKey(), FName(C.Key));
    TestEqual(FString::Printf(TEXT("%s: SHOT state"), C.Name), FString(UmHudStatus::StateName(Line->GetState())),
              FString(UmHudStatus::StateName(C.State)));
    TestTrue(FString::Printf(TEXT("%s: a RU text from the table ('%s')"), C.Name, *Text),
             !Text.IsEmpty() && !Text.StartsWith(TEXT("?")));
    for (const TCHAR* K : KeyLetters) {
      TestFalse(FString::Printf(TEXT("%s: no key %s in the text (ВР-H09)"), C.Name, K), Text.Contains(K));
    }
    TestTrue(FString::Printf(TEXT("%s: width %.0f <= 880"), C.Name, Line->GetBodySizeSu().X), Line->GetBodySizeSu().X <= 880.0);
    TArray<FString> Shot;
    Line->CollectShotLines(Shot, FS08ScreenRect(500.0f, 24.0f, 1400.0f, 72.0f));
    TestTrue(FString::Printf(TEXT("%s: one SHOT line"), C.Name), Shot.Num() == 1 && ShotLineOk(Shot[0]) &&
                                                                     Shot[0].Contains(FString::Printf(TEXT("id=UI-HUD-STATUS impl=umg state=%s "),
                                                                                                      UmHudStatus::StateName(C.State))));
    StatesSeen.Add(UmHudStatus::StateName(Line->GetState()));
  }
  TestEqual(TEXT("all six states of 04 §7.1"), StatesSeen.Num(), 6);
  // the opponent's verb is the RU table text, the name is data
  {
    FS09TurnStatusInput In;
    In.OpponentVerb = ES09OpponentVerb::Turn;
    In.OpponentName = TEXT("King Arthur");
    Line->ApplyModel(In);
    TestEqual(TEXT("RU opp line"), Line->GetFullText(), FString(TEXT("King Arthur — Соперник выбирает действие")));
    TestTrue(TEXT("opp: the pulse dot"), Visible(Line->PulseDot));
    const FLinearColor Secondary = UUmHudTheme::Get().Color(TEXT("text.secondary"));
    TestTrue(TEXT("opp: text.secondary"), Line->StatusText->GetColorAndOpacity().GetSpecifiedColor().Equals(Secondary, 1e-4f));
    // the pulse 1 Hz: full at the phase 0, 0.35 at half a second
    Clock = 1000.0;
    Line->ApplyModel(OwnTurn());
    Line->ApplyModel(In);  // a new opp state: the pulse restarts at the clock
    Line->TickForTest();
    TestTrue(FString::Printf(TEXT("pulse at 0 ms = 1 (%.2f)"), Line->GetDotOpacity()), FMath::IsNearlyEqual(Line->GetDotOpacity(), 1.0f, 0.01f));
    Clock += 0.5;
    Line->TickForTest();
    TestTrue(FString::Printf(TEXT("pulse at 500 ms = 0.35 (%.2f)"), Line->GetDotOpacity()),
             FMath::IsNearlyEqual(Line->GetDotOpacity(), UmHudStatus::PulseLow, 0.01f));
    Line->SetReducedMotionForTest(true);
    Line->TickForTest();
    TestTrue(TEXT("reduced: the dot is static"), FMath::IsNearlyEqual(Line->GetDotOpacity(), 1.0f, 0.01f));
    Line->SetReducedMotionForTest(false);
  }
  // ВР-VS2-47: a new text fades in over 120 ms
  {
    Clock = 2000.0;
    FS09TurnStatusInput In = OwnTurn();
    In.Mode = ES09CommandMode::SchemeChoice;
    Line->ApplyModel(In);
    TestTrue(FString::Printf(TEXT("fade at 0 ms = 0.15 (%.2f)"), Line->GetTextOpacity()), FMath::IsNearlyEqual(Line->GetTextOpacity(), 0.15f, 0.01f));
    Clock += 0.06;
    Line->TickForTest();
    TestTrue(TEXT("fade at 60 ms: half way"), Line->GetTextOpacity() > 0.5f && Line->GetTextOpacity() < 0.65f);
    Clock += 0.07;
    Line->TickForTest();
    TestTrue(TEXT("fade at 130 ms: done"), FMath::IsNearlyEqual(Line->GetTextOpacity(), 1.0f, 0.001f));
  }
  // ---- the fit (ВР-VS2-46) ----
  FS09TurnStatusInput Defend;
  Defend.Mode = ES09CommandMode::CombatDefense;
  const struct {
    const TCHAR* Name;
    float Width;
    int32 Lines;
  } Widths[] = {{TEXT("L 1080p 880"), 880.0f, 1}, {TEXT("L 720p 720"), 720.0f, 1}, {TEXT("S 600 (720p and 1080p at 150 %)"), 600.0f, 2}};
  for (const auto& Wd : Widths) {
    Frame.MaxWidthSu = Wd.Width;
    Line->SetFrame(Frame);
    Line->ApplyModel(Defend);
    const FUmStatusFit& Fit = Line->GetFit();
    AddInfo(FString::Printf(TEXT("defend %s: %d lines, %.0f su, width %.0f, height %.0f: '%s'"), Wd.Name, Fit.Lines,
                            Fit.SizeSu, Line->GetBodySizeSu().X, Line->GetBodySizeSu().Y, *Fit.Display.Replace(TEXT("\n"), TEXT(" | "))));
    TestEqual(FString::Printf(TEXT("defend %s: lines"), Wd.Name), Fit.Lines, Wd.Lines);
    TestEqual(FString::Printf(TEXT("defend %s: 24 su"), Wd.Name), Fit.SizeSu, 24.0f);
    TestFalse(FString::Printf(TEXT("defend %s: no «…»"), Wd.Name), Fit.bEllipsis);
    TestTrue(FString::Printf(TEXT("defend %s: within the width"), Wd.Name), Line->GetBodySizeSu().X <= Wd.Width);
    TArray<FString> Rows;
    Fit.Display.ParseIntoArray(Rows, TEXT("\n"));
    bool bWhole = false;
    for (const FString& R : Rows) bWhole |= R.Contains(TEXT("«Без\x00A0защиты»"));
    TestTrue(FString::Printf(TEXT("defend %s: «Без защиты» on one line"), Wd.Name), bWhole);
    if (Wd.Lines == 2) TestEqual(TEXT("two lines: the capsule 78 su (CX-08)"), static_cast<float>(Line->GetBodySizeSu().Y), 78.0f);
  }
  // still longer: 20, 16, then «…» with the full text in the tooltip
  {
    Frame.MaxWidthSu = 600.0f;
    Line->SetFrame(Frame);
    FS09TurnStatusInput In = OwnTurn();
    In.Mode = ES09CommandMode::PendingChoice;
    FString Long;
    for (int32 I = 0; I < 12; ++I) Long += TEXT("Переместите одного бойца на расстояние до трёх клеток. ");
    In.PendingPrompt = FS09Reason::Make(TEXT("ms.status.choice")).Arg(TEXT("choice"), Long.TrimEnd());
    Line->ApplyModel(In);
    const FUmStatusFit& Fit = Line->GetFit();
    TestTrue(TEXT("very long: «…»"), Fit.bEllipsis && Fit.Display.EndsWith(TEXT("\x2026")));
    TestEqual(TEXT("very long: type.body 16 su"), Fit.SizeSu, 16.0f);
    TestEqual(TEXT("very long: two lines"), Fit.Lines, 2);
    TestTrue(TEXT("very long: the full text in the tooltip, the capsule takes the hover"),
             Line->Body->GetToolTipText().ToString() == Line->GetFullText() && Line->Body->GetVisibility() == ESlateVisibility::Visible);
    // a middle length steps to 20 su
    FString Mid;
    for (int32 I = 0; I < 2; ++I) Mid += TEXT("Переместите одного бойца на расстояние до трёх клеток. ");
    In.PendingPrompt = FS09Reason::Make(TEXT("ms.status.choice")).Arg(TEXT("choice"), Mid.TrimEnd());
    Line->ApplyModel(In);
    AddInfo(FString::Printf(TEXT("middle: %d lines at %.0f su"), Line->GetFit().Lines, Line->GetFit().SizeSu));
    TestTrue(TEXT("middle: smaller than 24 su or two lines, never «…»"), !Line->GetFit().bEllipsis);
  }
  // ---- key chips (ВР-H09: UI-ACC-017 on) ----
  {
    Frame.MaxWidthSu = 880.0f;
    Frame.bKeyHints = false;
    Line->SetFrame(Frame);
    Line->ApplyModel(OwnTurn());
    const float Plain = static_cast<float>(Line->GetBodySizeSu().X);
    Frame.bKeyHints = true;
    Line->SetFrame(Frame);
    TestEqual(TEXT("action: three chips M, A, G"), Line->GetKeysShown(),
              TArray<FString>({TEXT("hud.key.maneuver"), TEXT("hud.key.attack"), TEXT("hud.key.scheme")}));
    TestTrue(TEXT("the chip row is shown"), Visible(Line->KeyChip));
    const float Growth = static_cast<float>(Line->GetBodySizeSu().X) - Plain;
    TestTrue(FString::Printf(TEXT("the capsule grows by 8 + 3 chips (>= 20 su, the measured key) + 2 x 4 su: %.0f"), Growth),
             Growth >= 76.0f && Growth <= 100.0f);
    Line->ApplyModel(Defend);
    TestEqual(TEXT("defend: the N chip"), Line->GetKeysShown(), TArray<FString>({TEXT("hud.key.no_defense")}));
    TestFalse(TEXT("the text still has no key"), Line->GetFullText().Contains(TEXT("(N)")));
  }
  // EN: the same keys, no key letter either
  {
    FRu::Use(TEXT("en"));
    Frame.bKeyHints = false;
    Line->SetFrame(Frame);
    Line->ApplyModel(OwnTurn());
    FS09TurnStatusInput Other = OwnTurn();
    Other.ActionsRemaining = 0;
    Line->ApplyModel(Other);
    TestEqual(TEXT("EN end"), Line->GetFullText(), FString(TEXT("No actions left: end your turn")));
    FRu::Use(TEXT("ru"));
  }
  return true;
}

// ---------------------------------------------------------------------------------------------------------- BANNER

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHudBannerAlphaTest, "Unmatched.S08.Hud.Banner.Alpha",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHudBannerAlphaTest::RunTest(const FString&) {
  using namespace UmTopStripTest;
  FWorld W(TEXT("UmHudBanner"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  FRu Ru;
  UUmHudBanner* Banner = CreateWidget<UUmHudBanner>(W.World, UUmHudBanner::StaticClass());
  if (!TestNotNull(TEXT("banner"), Banner)) return false;
  FString Missing;
  TestTrue(FString::Printf(TEXT("every part bound (missing %s)"), *Missing), Banner->HasAllParts(&Missing));
  UClass* Wbp = UUmHudBanner::WidgetClass();
  if (Wbp != UUmHudBanner::StaticClass()) {
    UUmHudBanner* FromWbp = CreateWidget<UUmHudBanner>(W.World, Wbp);
    TestTrue(TEXT("WBP_UI_HUD_BANNER: authored tree, every part"), FromWbp && !FromWbp->UsesCodeDefaultTree() && FromWbp->HasAllParts());
    TestTrue(TEXT("WBP_UI_HUD_BANNER: «ВАШ ХОД» has a real font"), FromWbp && FromWbp->Text->GetFont().HasValidFont());
  } else {
    AddWarning(TEXT("WBP_UI_HUD_BANNER not authored yet: only the code tree checked"));
  }
  TestEqual(TEXT("RU «ВАШ ХОД»"), Banner->Text->GetText().ToString(), FString(TEXT("ВАШ ХОД")));
  const FLinearColor Yellow = UUmHudTheme::Get().Color(TEXT("turn.flash.yellow"));
  TestTrue(TEXT("turn.flash.yellow text"), Banner->Text->GetColorAndOpacity().GetSpecifiedColor().Equals(Yellow, 1e-4f));
  TestFalse(TEXT("collapsed before any turn"), Visible(Banner));
  FS09TurnCue Cue;
  Cue.OnApplied(TEXT("me"), 1, TEXT("me"), false, 0.0, false);       // the first snapshot: no banner (join)
  Cue.OnApplied(TEXT("them"), 2, TEXT("me"), false, 500.0, false);   // the opponent's turn
  Banner->ApplyModel(Cue, 550.0);
  TestEqual(TEXT("the opponent's turn: never shown"), Banner->GetAlpha(), 0.0f);
  Cue.OnApplied(TEXT("me"), 3, TEXT("me"), false, 1000.0, false);    // the own turn starts at 1000
  const struct {
    double Ms;
    float Alpha;
  } Keys[] = {{-1.0, 0.0f}, {100.0, 1.0f}, {450.0, 1.0f}, {600.0, 0.0f}};
  for (const auto& K : Keys) {
    Banner->ApplyModel(Cue, 1000.0 + K.Ms);
    TestTrue(FString::Printf(TEXT("%+.0f ms: alpha %.2f = %.2f"), K.Ms, Banner->GetAlpha(), K.Alpha),
             FMath::IsNearlyEqual(Banner->GetAlpha(), K.Alpha, 1e-3f));
    TestEqual(FString::Printf(TEXT("%+.0f ms: shown only with alpha"), K.Ms), Visible(Banner), K.Alpha > 0.0f);
    TArray<FString> Shot;
    Banner->CollectShotLines(Shot, FS08ScreenRect(750.0f, 144.0f, 1170.0f, 208.0f));
    TestEqual(FString::Printf(TEXT("%+.0f ms: SHOT line only while shown"), K.Ms), Shot.Num(), K.Alpha > 0.0f ? 1 : 0);
    if (Shot.Num()) TestTrue(TEXT("SHOT UI-HUD-BANNER state=shown"), ShotLineOk(Shot[0]) && Shot[0].Contains(TEXT("id=UI-HUD-BANNER impl=umg state=shown ")));
  }
  // ВР-VS2-49: the frame at 0 ms is not empty (DE-023: 0.15), it fades in to 1 at 100 ms
  Banner->ApplyModel(Cue, 1000.0);
  TestTrue(TEXT("0 ms: 0.15 (frame 0 not empty)"), FMath::IsNearlyEqual(Banner->GetAlpha(), 0.15f, 1e-3f));
  Banner->ApplyModel(Cue, 1050.0);
  TestTrue(TEXT("50 ms: fading in"), Banner->GetAlpha() > 0.15f && Banner->GetAlpha() < 1.0f);
  TestTrue(TEXT("shown: hit-test invisible (SD-47)"), Banner->GetVisibility() == ESlateVisibility::HitTestInvisible);
  Banner->ApplyModel(Cue, 1525.0);
  TestTrue(TEXT("525 ms: fading out"), Banner->GetAlpha() > 0.0f && Banner->GetAlpha() < 1.0f);
  Banner->ApplyModel(Cue, 1300.0, false);
  TestEqual(TEXT("the result screen: hidden"), Banner->GetAlpha(), 0.0f);
  // reduced motion: 100 ms, static
  Cue.OnApplied(TEXT("them"), 4, TEXT("me"), false, 2000.0, true);
  Cue.OnApplied(TEXT("me"), 5, TEXT("me"), false, 3000.0, true);
  Banner->ApplyModel(Cue, 3000.0);
  TestEqual(TEXT("reduced 0 ms: 1"), Banner->GetAlpha(), 1.0f);
  Banner->ApplyModel(Cue, 3099.0);
  TestEqual(TEXT("reduced 99 ms: 1"), Banner->GetAlpha(), 1.0f);
  Banner->ApplyModel(Cue, 3100.0);
  TestEqual(TEXT("reduced 100 ms: gone"), Banner->GetAlpha(), 0.0f);
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
