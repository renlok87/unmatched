// DE-014 (W-21, UI-INP-011 of docs/game-design/02-ux-ui-spec.md §5, SD-46):
// synthetic clicks on the HUD elements - the HUD gate of the S11b..S11f tasks.
//   Unmatched.S09.HudPress.Arbiter         - the press is a logical element id:
//       release over the same id = the click (no hover, no minimum hold, press
//       and release in one tick count), a drag away cancels (MS-R-34), a
//       release over another element after a rebuild is refused with
//       why.state.changed, a blocked element answers its reason, trace line.
//   Unmatched.S09.HudPress.SyntheticClicks - n = 20 clicks with a 0 ms and a
//       50 ms hold on EVERY HUD button, hand card and the deck/discard
//       controls of the layout, driven through the real SS09HudPress widgets
//       (OnMouseButtonDown / OnMouseButtonUp with synthetic pointer events),
//       while the HUD is rebuilt on the 0.25 s combat countdown and on
//       snapshots: 0 lost, every press answered in the frame of the release
//       (the action, or CUE-004 with a why.* key); the SButton contract (same
//       instance for the press and the release) loses the presses that
//       straddle a rebuild - the defect the arbiter removes.
// The board spaces have their own half: Unmatched.S09.MoveSel.ClickReliability.
// Headless run:
//   node tools/s08/run-ue-tests.cjs "Unmatched.S09.HudPress" <abs log>
#if WITH_AUTOMATION_TESTS

#include "S09HudPress.h"
#include "../S08/S08WhyText.h"
#include "Input/Events.h"
#include "InputCoreTypes.h"
#include "Layout/Geometry.h"
#include "Misc/AutomationTest.h"

// Named namespace (not anonymous): unity builds merge test files.
namespace S09HudPressTest {

constexpr double FrameSeconds = 1.0 / 60.0;
constexpr double CountdownSeconds = 0.25; // RefreshHud on the combat deadline tick

FPointerEvent LeftEvent(const FVector2D& At, bool bDown) {
  TSet<FKey> Pressed;
  if (bDown) Pressed.Add(EKeys::LeftMouseButton);
  return FPointerEvent(0, At, At, Pressed, EKeys::LeftMouseButton, 0.0f, FModifierKeysState());
}

/** The HUD layout of the S09 panels: every element the game mode builds with
 *  MakeHudPress (buttons of every command panel, three hand cards, the
 *  deck/discard browse control and a discard chip), one row each. */
struct FElement {
  FName Id;
  const TCHAR* Kind;   // button | card | deck
  FS09Reason Blocked;  // reason the element answers right now (unset: acts)
};

TArray<FElement> HudLayout() {
  auto Button = [](const TCHAR* Id) { return FElement{FName(Id), TEXT("button"), FS09Reason()}; };
  TArray<FElement> L = {
      Button(TEXT("hud.begin.maneuver")),
      FElement{FName(TEXT("hud.end.turn")), TEXT("button"),
               FS09Reason::Make(TEXT("why.actions.remaining")).Arg(TEXT("n"), 2)},
      Button(TEXT("hud.maneuver.confirm")),
      Button(TEXT("hud.maneuver.clear")),
      FElement{FName(TEXT("hud.discard.confirm")), TEXT("button"),
               FS09Reason::Make(TEXT("why.discard.count")).Arg(TEXT("need"), 2).Arg(TEXT("have"), 1)},
      Button(TEXT("hud.attack.confirm")),
      Button(TEXT("hud.attack.close")),
      FElement{FName(TEXT("hud.scheme.play")), TEXT("button"), FS09Reason::Make(TEXT("why.scheme.none"))},
      Button(TEXT("hud.scheme.cancel")),
      Button(TEXT("hud.defense.play")),
      FElement{FName(TEXT("hud.defense.none")), TEXT("button"), FS09Reason::Make(TEXT("why.deadline.passed"))},
      FElement{FName(TEXT("hud.combat.resolve")), TEXT("button"), FS09Reason::Make(TEXT("why.wait.opponent.choice"))},
      Button(TEXT("hud.pending.confirm")),
      Button(TEXT("hud.pending.stay")),
      FElement{FName(TEXT("hud.pending.decline")), TEXT("button"), FS09Reason::Make(TEXT("why.choice.required"))},
      Button(TEXT("pending.option.0")),
      Button(TEXT("pending.reveal.card::7")),
      FElement{FName(TEXT("hud.result.lobby")), TEXT("button"), FS09Reason::Make(TEXT("why.syncing"))},
      Button(TEXT("hud.abort.lobby")),
      FElement{FName(TEXT("hand.card::0")), TEXT("card"), FS09Reason()},
      FElement{FName(TEXT("hand.card::1")), TEXT("card"), FS09Reason()},
      FElement{FName(TEXT("hand.card::2")), TEXT("card"), FS09Reason()},
      FElement{FName(TEXT("hud.discard.browse")), TEXT("deck"), FS09Reason()},
      FElement{FName(TEXT("discard.0.card::4")), TEXT("deck"), FS09Reason()},
  };
  return L;
}

/** A Slate HUD that RefreshHud rebuilds wholesale: one live SS09HudPress per
 *  element id, re-created (a new instance, same id and place) on Rebuild. */
struct FHud {
  TSharedPtr<FS09HudPressArbiter> Arbiter = MakeShared<FS09HudPressArbiter>();
  TArray<FElement> Layout;
  TMap<FName, TSharedPtr<SS09HudPress>> Live;
  TMap<FName, int32> Row;  // element -> row (its place on screen)
  TMap<FName, int32> Acts;
  TArray<FS09HudPressOutcome> Answers;  // every resolved release (Act / Refused)
  int32 Rebuilds = 0;

  explicit FHud(const TArray<FElement>& InLayout) : Layout(InLayout) { Build(); }

  void Build() {
    Live.Reset();
    Row.Reset();
    for (int32 I = 0; I < Layout.Num(); ++I) {
      const FElement Element = Layout[I];
      Row.Add(Element.Id, I);
      Live.Add(Element.Id, SNew(SS09HudPress)
                               .Id(Element.Id)
                               .Arbiter(Arbiter)
                               .OnOutcome_Lambda([this, Element](const FS09HudPressOutcome& Outcome) {
                                 // The game mode's HandleHudPressOutcome: decide, then act or CUE-004.
                                 const FS09HudPressOutcome Answer = FS09HudPressArbiter::Decide(
                                     Outcome, Outcome.Result == ES09HudPressResult::Act ? Element.Blocked
                                                                                        : FS09Reason());
                                 Answers.Add(Answer);
                                 if (Answer.Result == ES09HudPressResult::Act) Acts.FindOrAdd(Element.Id) += 1;
                               })[SNullWidget::NullWidget]);
    }
  }
  /** RefreshHud: ClearChildren + SNew (the arbiter learns the layout moved). */
  void Rebuild() {
    Arbiter->NoteRebuild();
    Build();
    ++Rebuilds;
  }
  static FVector2D RowOrigin(int32 RowIndex) { return FVector2D(40.0, 40.0 + 44.0 * RowIndex); }
  static FVector2D RowCentre(int32 RowIndex) { return RowOrigin(RowIndex) + FVector2D(110.0, 18.0); }
  FGeometry GeometryOf(FName Id) const {
    return FGeometry::MakeRoot(FVector2D(220.0, 36.0), FSlateLayoutTransform(RowOrigin(Row.FindChecked(Id))));
  }
  /** Slate's hit test at a screen point: the live element under it. */
  TSharedPtr<SS09HudPress> Under(const FVector2D& At, FName& OutId) const {
    for (const auto& Pair : Live) {
      if (GeometryOf(Pair.Key).IsUnderLocation(At)) {
        OutId = Pair.Key;
        return Pair.Value;
      }
    }
    OutId = NAME_None;
    return nullptr;
  }
};

/** One synthetic click: the press lands on the element under At, the release
 *  goes to the captor while it lives, else (rebuilt away) to the element now
 *  under the cursor - exactly Slate's routing. RebuildAt: rebuilds inside the
 *  hold (each one replaces the captor instance). */
void Click(FHud& Hud, const FVector2D& At, int32 RebuildsDuringHold, const FVector2D* ReleaseAt = nullptr,
           TFunction<void(FHud&)> MoveLayout = nullptr) {
  FName DownId;
  TSharedPtr<SS09HudPress> Pressed = Hud.Under(At, DownId);
  if (!Pressed.IsValid()) return;
  Pressed->OnMouseButtonDown(Hud.GeometryOf(DownId), LeftEvent(At, true));
  TWeakPtr<SS09HudPress> Captor = Pressed;
  Pressed.Reset();
  for (int32 R = 0; R < RebuildsDuringHold; ++R) Hud.Rebuild();
  if (MoveLayout) MoveLayout(Hud);
  const FVector2D Up = ReleaseAt ? *ReleaseAt : At;
  TSharedPtr<SS09HudPress> Target;
  FName TargetId;
  bool bCaptorAlive = false;
  for (const auto& Pair : Hud.Live) {
    if (Pair.Value == Captor.Pin()) {
      Target = Pair.Value;
      TargetId = Pair.Key;
      bCaptorAlive = true;
    }
  }
  if (!bCaptorAlive) Target = Hud.Under(Up, TargetId);
  if (Target.IsValid()) {
    Target->OnMouseButtonUp(Hud.GeometryOf(TargetId), LeftEvent(Up, false));
  } else {
    Hud.Arbiter->Release(NAME_None, GFrameCounter);  // the game mode's stray-release resolve
  }
}

/** Rebuilds inside a hold of HoldSeconds pressed at PressAt: the HUD
 *  countdown ticks (every 0.25 s) and the snapshot times in Snapshots. With a
 *  0 ms hold the press and the release are one Slate input pass - nothing can
 *  run between them. */
int32 RebuildsInHold(double PressAt, double HoldSeconds, const TArray<double>& Snapshots) {
  if (HoldSeconds <= 0.0) return 0;
  const double ReleaseAt = PressAt + HoldSeconds;
  int32 N = FMath::FloorToInt(ReleaseAt / CountdownSeconds) - FMath::FloorToInt(PressAt / CountdownSeconds);
  for (const double T : Snapshots) N += (T > PressAt && T <= ReleaseAt) ? 1 : 0;
  return N;
}

}  // namespace S09HudPressTest

using namespace S09HudPressTest;

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09HudPressArbiterTest, "Unmatched.S09.HudPress.Arbiter",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09HudPressArbiterTest::RunTest(const FString&) {
  const FName A(TEXT("hud.end.turn"));
  const FName B(TEXT("hud.begin.maneuver"));
  {
    FS09HudPressArbiter Arb;
    TestTrue(TEXT("release without a press: not a HUD click"), Arb.Release(A, 1).Result == ES09HudPressResult::None);
    Arb.Press(A, 7);
    TestTrue(TEXT("the press is held by id"), Arb.IsPressed(A) && !Arb.IsPressed(B));
    const FS09HudPressOutcome Same = Arb.Release(A, 7);
    TestTrue(TEXT("press and release in one frame: the click"), Same.Result == ES09HudPressResult::Act);
    TestTrue(TEXT("same frame recorded"), Same.PressFrame == 7 && Same.ReleaseFrame == 7);
    TestFalse(TEXT("the click consumes the press"), Arb.IsPressed());
  }
  {
    FS09HudPressArbiter Arb;
    Arb.Press(A, 1);
    Arb.NoteRebuild();
    Arb.NoteRebuild();
    const FS09HudPressOutcome Rebuilt = Arb.Release(A, 4);
    TestTrue(TEXT("two rebuilds under the hold: still the click"), Rebuilt.Result == ES09HudPressResult::Act);
    TestEqual(TEXT("rebuilds counted"), Rebuilt.Rebuilds, 2);
  }
  {
    FS09HudPressArbiter Arb;
    Arb.Press(A, 1);
    TestTrue(TEXT("a drag to another element without a rebuild cancels (MS-R-34)"),
             Arb.Release(B, 2).Result == ES09HudPressResult::Cancelled);
    Arb.Press(A, 3);
    TestTrue(TEXT("a drag off the HUD cancels"), Arb.Release(NAME_None, 4).Result == ES09HudPressResult::Cancelled);
    Arb.Press(A, 5);
    Arb.NoteRebuild();
    const FS09HudPressOutcome Moved = Arb.Release(B, 6);
    TestTrue(TEXT("the layout moved under the press: refused"), Moved.Result == ES09HudPressResult::Refused);
    TestEqual(TEXT("... with why.state.changed"), Moved.Reason.Key.ToString(), FString(TEXT("why.state.changed")));
    Arb.Press(A, 7);
    Arb.NoteRebuild();
    TestTrue(TEXT("rebuilt away, released off the HUD: refused"),
             Arb.Release(NAME_None, 8).Result == ES09HudPressResult::Refused);
    Arb.Press(A, 9);
    Arb.Reset();
    TestTrue(TEXT("focus lost: the press is gone"), Arb.Release(A, 10).Result == ES09HudPressResult::None);
  }
  {
    FS09HudPressOutcome Act;
    Act.Result = ES09HudPressResult::Act;
    Act.PressedId = Act.ReleasedId = A;
    const FS09HudPressOutcome Blocked =
        FS09HudPressArbiter::Decide(Act, FS09Reason::Make(TEXT("why.actions.remaining")).Arg(TEXT("n"), 1));
    TestTrue(TEXT("a blocked element answers CUE-004"), Blocked.Result == ES09HudPressResult::Refused);
    TestEqual(TEXT("... with its reason"), Blocked.Reason.Key.ToString(), FString(TEXT("why.actions.remaining")));
    TestTrue(TEXT("an open element acts"),
             FS09HudPressArbiter::Decide(Act, FS09Reason()).Result == ES09HudPressResult::Act);
    const FString Line = FS09HudPressArbiter::TraceLine(Blocked);
    TestTrue(TEXT("trace line"), Line.StartsWith(TEXT("HUD-PRESS id=hud.end.turn result=refused over=hud.end.turn")) &&
                                     Line.EndsWith(TEXT("why=why.actions.remaining")));
  }
  // Every reason a HUD element can answer is a key of the EN table (why-reasons.json).
  for (const TCHAR* Key : {TEXT("why.state.changed"), TEXT("why.syncing"), TEXT("why.no.actions"),
                           TEXT("why.actions.remaining"), TEXT("why.discard.count"), TEXT("why.scheme.none"),
                           TEXT("why.choice.required"), TEXT("why.deadline.passed"), TEXT("why.wait.opponent.choice"),
                           TEXT("why.not.your.turn"), TEXT("why.wait.defender")}) {
    TestTrue(FString::Printf(TEXT("%s in the EN table"), Key), S08WhyText::Has(FName(Key)));
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09HudPressSyntheticClicksTest, "Unmatched.S09.HudPress.SyntheticClicks",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09HudPressSyntheticClicksTest::RunTest(const FString&) {
  const TArray<FElement> Layout = HudLayout();
  constexpr int32 N = 20;
  // Snapshots land at irregular times (WS events), on top of the countdown.
  const TArray<double> Snapshots = {0.31, 0.74, 1.12, 1.53, 2.08, 2.61, 3.37, 4.02, 4.66};
  int32 TotalPresses = 0;
  int32 TotalAnswered = 0;
  int32 SButtonLost = 0;  // the instance-bound contract, same timeline
  int32 Straddled = 0;
  for (const double Hold : {0.0, 0.050}) {
    for (int32 E = 0; E < Layout.Num(); ++E) {
      const FElement& Element = Layout[E];
      FHud Hud(Layout);
      const int32 Before = Hud.Answers.Num();
      for (int32 K = 0; K < N; ++K) {
        // Press phases sweep the countdown period: every second 50 ms hold
        // straddles a rebuild (0.22 + 0.05 crosses the 0.25 s tick).
        const double PressAt = K * CountdownSeconds + ((K % 2) ? 0.22 : 0.05) + E * FrameSeconds * 0.01;
        const int32 Rebuilds = RebuildsInHold(PressAt, Hold, Snapshots);
        Straddled += Rebuilds > 0 ? 1 : 0;
        SButtonLost += Rebuilds > 0 ? 1 : 0;  // a new instance never saw the press
        Click(Hud, FHud::RowCentre(E), Rebuilds);
        ++TotalPresses;
      }
      const int32 Answered = Hud.Answers.Num() - Before;
      TotalAnswered += Answered;
      const FString Tag =
          FString::Printf(TEXT("%s %s hold %.0f ms"), Element.Kind, *Element.Id.ToString(), Hold * 1000.0);
      TestEqual(Tag + TEXT(": every press answered (0 lost)"), Answered, N);
      int32 Acted = 0;
      int32 Refused = 0;
      bool bReasonKeyed = true;
      bool bOwnId = true;
      for (int32 I = Before; I < Hud.Answers.Num(); ++I) {
        const FS09HudPressOutcome& A = Hud.Answers[I];
        Acted += A.Result == ES09HudPressResult::Act ? 1 : 0;
        Refused += A.Result == ES09HudPressResult::Refused ? 1 : 0;
        if (A.Result == ES09HudPressResult::Refused) {
          bReasonKeyed &= A.Reason.IsSet() && A.Reason.Key.ToString().StartsWith(TEXT("why.")) &&
                          S08WhyText::Has(A.Reason.Key);
        }
        bOwnId &= A.PressedId == Element.Id && A.ReleasedId == Element.Id;
        bOwnId &= A.ReleaseFrame == A.PressFrame;  // answered in the frame of the release (no deferral)
      }
      if (Element.Blocked.IsSet()) {
        TestEqual(Tag + TEXT(": blocked - every press is CUE-004"), Refused, N);
        TestTrue(Tag + TEXT(": ... with a why.* key"), bReasonKeyed);
      } else {
        TestEqual(Tag + TEXT(": open - every press acts"), Acted, N);
        TestEqual(Tag + TEXT(": ... once per press"), Hud.Acts.FindRef(Element.Id), N);
      }
      TestTrue(Tag + TEXT(": the answer belongs to the pressed element"), bOwnId);
      TestFalse(Tag + TEXT(": no press left hanging"), Hud.Arbiter->IsPressed());
    }
  }
  TestEqual(TEXT("n >= 20 per element and hold: all answered"), TotalAnswered, TotalPresses);
  TestTrue(TEXT("the timeline straddles rebuilds (the test can see the defect)"), Straddled >= Layout.Num() * N / 2);
  TestTrue(TEXT("the SButton contract would lose those presses"), SButtonLost > 0);
  AddInfo(FString::Printf(TEXT("DE-014 synthetic clicks: %d presses on %d elements x {0, 50 ms} x %d, answered %d, "
                               "lost 0; %d presses straddled a HUD rebuild (an instance-bound SButton loses them)"),
                          TotalPresses, Layout.Num(), N, TotalAnswered, Straddled));

  // ---- the press acts on the release, not on the press (MS-D-17) ----
  {
    FHud Hud(Layout);
    const int32 Row = 0;
    FName Id;
    TSharedPtr<SS09HudPress> W = Hud.Under(FHud::RowCentre(Row), Id);
    W->OnMouseButtonDown(Hud.GeometryOf(Id), LeftEvent(FHud::RowCentre(Row), true));
    TestEqual(TEXT("nothing happens on the press"), Hud.Answers.Num(), 0);
    W->OnMouseButtonUp(Hud.GeometryOf(Id), LeftEvent(FHud::RowCentre(Row), false));
    TestEqual(TEXT("the release acts"), Hud.Answers.Num(), 1);
  }
  // ---- a drag away is the player's cancel; a moved layout is refused, never silent ----
  {
    FHud Hud(Layout);
    const FVector2D Other = FHud::RowCentre(1);
    Click(Hud, FHud::RowCentre(0), 0, &Other);
    TestEqual(TEXT("drag to another element, no rebuild: cancelled, no answer (MS-R-34)"), Hud.Answers.Num(), 0);
    // A card drawn under the held press shifts the hand: another element is
    // under the cursor after the rebuild.
    const FName Card0(TEXT("hand.card::0"));
    const int32 CardRow = Hud.Row.FindChecked(Card0);
    Click(Hud, FHud::RowCentre(CardRow), 1, nullptr, [Card0](FHud& H) {
      H.Layout.Insert(FElement{FName(TEXT("hand.card::9")), TEXT("card"), FS09Reason()},
                      H.Layout.IndexOfByPredicate([Card0](const FElement& X) { return X.Id == Card0; }));
      H.Build();
    });
    TestEqual(TEXT("the layout moved under the press: one answer"), Hud.Answers.Num(), 1);
    TestTrue(TEXT("... CUE-004 why.state.changed, the new card not played"),
             Hud.Answers.Num() == 1 && Hud.Answers[0].Result == ES09HudPressResult::Refused &&
                 Hud.Answers[0].Reason.Key == FName(TEXT("why.state.changed")) &&
                 Hud.Acts.FindRef(FName(TEXT("hand.card::9"))) == 0);
  }
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
