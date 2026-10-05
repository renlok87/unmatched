// DE-014 (W-21, UI-INP-011 of docs/game-design/02-ux-ui-spec.md §5, SD-46):
// synthetic clicks on the HUD elements - the HUD gate of the S11b..S11f tasks.
//   Unmatched.S09.HudPress.Arbiter         - the press is a logical element id:
//       release over the same id = the click (no hover, no minimum hold, press
//       and release in one tick count), a drag away cancels (MS-R-34), a
//       release over another element after a rebuild is refused with
//       why.state.changed, a blocked element answers its reason, trace line.
//   Unmatched.S09.HudPress.SyntheticClicks - n = 20 clicks with a 0 ms and a
//       50 ms hold on EVERY element the game mode builds with MakeHudPress
//       (the list is read from the S08FlowGameMode*.cpp sources, run H R-05),
//       driven through the real SS09HudPress widgets (OnMouseButtonDown /
//       OnMouseButtonUp with synthetic pointer events) on a stepped frame
//       clock, while the HUD is rebuilt on the 0.25 s combat countdown and on
//       snapshots: 0 lost, every press answered in the frame of the release
//       (the action, or CUE-004 with a why.* key); the SButton contract (same
//       instance for the press and the release) loses the presses that
//       straddle a rebuild - the defect the arbiter removes.
//   Unmatched.S09.HudPress.Interactable   - the readiness half of Automation
//       Driver's ElementIsInteractable for the key HUD buttons, without the
//       Developer module: the element is enabled and hit-test visible even when
//       blocked (dimmed), and no SButton of its content can take the press.
// The board spaces have their own half: Unmatched.S09.MoveSel.ClickReliability.
// Headless run:
//   node tools/s08/run-ue-tests.cjs "Unmatched.S09.HudPress" <abs log>
#if WITH_AUTOMATION_TESTS

#include "S09HudPress.h"
#include "../S08/S08WhyText.h"
#include "HAL/FileManager.h"
#include "Input/Events.h"
#include "InputCoreTypes.h"
#include "Layout/Geometry.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Widgets/Text/STextBlock.h"

// Named namespace (not anonymous): unity builds merge test files.
namespace S09HudPressTest {

constexpr double FrameSeconds = 1.0 / 60.0;
constexpr double CountdownSeconds = 0.25; // RefreshHud on the combat deadline tick

FPointerEvent LeftEvent(const FVector2D& At, bool bDown) {
  TSet<FKey> Pressed;
  if (bDown) Pressed.Add(EKeys::LeftMouseButton);
  return FPointerEvent(0, At, At, Pressed, EKeys::LeftMouseButton, 0.0f, FModifierKeysState());
}

struct FElement {
  FName Id;
  const TCHAR* Kind;   // button | card | deck
  FS09Reason Blocked;  // reason the element answers right now (unset: acts)
};

// ---- the HUD layout, read from the game mode source ---------------------------
//
// Every MakeHudPress call of S08FlowGameMode*.cpp is one HUD element. Its first
// argument is the id: FName(TEXT("hud.x")) (exact), FName(*(TEXT("hand.") + ...))
// (a prefix and a runtime part), FName(*FString::Printf(TEXT("discard.%d.%s"), ...))
// (a format), or FName(Id) inside a local helper lambda (auto Tab = [...](...,
// const TCHAR* Id) { return MakeHudPress(FName(Id), ...); }) whose call sites pass
// the literal ids. A new element appears in the sweep without a test edit; only a
// reason or a runtime sample needs a row in ReasonOverlay().

/** One HUD id of the source: exact, or a wildcard ('*' = a runtime part). */
struct FSourceId {
  FString Wildcard;
  FString Where;  // file:line of the first call
};

bool IsHudId(const FString& S) {
  return S.StartsWith(TEXT("hud."), ESearchCase::CaseSensitive) ||
         S.StartsWith(TEXT("hand."), ESearchCase::CaseSensitive) ||
         S.StartsWith(TEXT("pending."), ESearchCase::CaseSensitive) ||
         S.StartsWith(TEXT("discard."), ESearchCase::CaseSensitive);
}

/** Index past a "..." or '...' literal that opens at I (escapes skipped). */
int32 SkipQuoted(const FString& S, int32 I) {
  const TCHAR Quote = S[I];
  for (++I; I < S.Len(); ++I) {
    if (S[I] == TEXT('\\')) {
      ++I;
    } else if (S[I] == Quote) {
      return I + 1;
    }
  }
  return S.Len();
}

/** The ')' that closes the '(' at Open (nesting and literals respected). */
int32 CloseParen(const FString& S, int32 Open) {
  int32 Depth = 0;
  for (int32 I = Open; I < S.Len();) {
    const TCHAR C = S[I];
    if (C == TEXT('"') || C == TEXT('\'')) {
      I = SkipQuoted(S, I);
      continue;
    }
    if (C == TEXT('(') || C == TEXT('[') || C == TEXT('{')) ++Depth;
    if (C == TEXT(')') || C == TEXT(']') || C == TEXT('}')) {
      if (--Depth == 0) return I;
    }
    ++I;
  }
  return INDEX_NONE;
}

/** The first ',' at depth 0 in [From, End) (End when the call has one argument). */
int32 TopLevelComma(const FString& S, int32 From, int32 End) {
  int32 Depth = 0;
  for (int32 I = From; I < End;) {
    const TCHAR C = S[I];
    if (C == TEXT('"') || C == TEXT('\'')) {
      I = SkipQuoted(S, I);
      continue;
    }
    if (C == TEXT('(') || C == TEXT('[') || C == TEXT('{')) ++Depth;
    if (C == TEXT(')') || C == TEXT(']') || C == TEXT('}')) --Depth;
    if (C == TEXT(',') && Depth == 0) return I;
    ++I;
  }
  return End;
}

/** The contents of every TEXT("...") in Expr. */
TArray<FString> TextLiterals(const FString& Expr) {
  TArray<FString> Out;
  const FString Open(TEXT("TEXT(\""));
  for (int32 At = Expr.Find(Open, ESearchCase::CaseSensitive); At != INDEX_NONE;
       At = Expr.Find(Open, ESearchCase::CaseSensitive, ESearchDir::FromStart, At + 1)) {
    const int32 Begin = At + Open.Len();
    const int32 End = SkipQuoted(Expr, Begin - 1) - 1;  // the closing quote
    Out.Add(Expr.Mid(Begin, End - Begin));
  }
  return Out;
}

bool IsIdentChar(TCHAR C) { return FChar::IsAlnum(C) || C == TEXT('_'); }

int32 LineOf(const FString& S, int32 At) {
  int32 Line = 1;
  for (int32 I = 0; I < At && I < S.Len(); ++I) Line += S[I] == TEXT('\n') ? 1 : 0;
  return Line;
}

/** The local helper lambda around At ("auto Name = [") - its name and position. */
bool EnclosingLambda(const FString& S, int32 At, FString& OutName, int32& OutPos) {
  for (int32 A = S.Find(TEXT("auto "), ESearchCase::CaseSensitive, ESearchDir::FromEnd, At); A != INDEX_NONE;
       A = A > 0 ? S.Find(TEXT("auto "), ESearchCase::CaseSensitive, ESearchDir::FromEnd, A) : INDEX_NONE) {
    int32 I = A + 5;
    const int32 NameBegin = I;
    while (I < S.Len() && IsIdentChar(S[I])) ++I;
    const FString Name = S.Mid(NameBegin, I - NameBegin);
    while (I < S.Len() && S[I] == TEXT(' ')) ++I;
    if (Name.IsEmpty() || I + 1 >= S.Len() || S[I] != TEXT('=')) continue;
    ++I;
    while (I < S.Len() && S[I] == TEXT(' ')) ++I;
    if (I < S.Len() && S[I] == TEXT('[')) {
      OutName = Name;
      OutPos = A;
      return true;
    }
  }
  return false;
}

void AddSourceId(TArray<FSourceId>& Out, const FString& Wildcard, const FString& Where) {
  if (!Out.ContainsByPredicate([&Wildcard](const FSourceId& X) { return X.Wildcard == Wildcard; })) {
    Out.Add(FSourceId{Wildcard, Where});
  }
}

/** Every HUD id the game mode file Text builds with MakeHudPress. */
void ParseHudIds(const FString& Text, const FString& File, TArray<FSourceId>& Out, TArray<FString>& Errors) {
  const FString Call(TEXT("MakeHudPress("));
  for (int32 At = Text.Find(Call, ESearchCase::CaseSensitive); At != INDEX_NONE;
       At = Text.Find(Call, ESearchCase::CaseSensitive, ESearchDir::FromStart, At + Call.Len())) {
    if (At >= 2 && Text.Mid(At - 2, 2) == TEXT("::")) continue;  // the definition
    if (At >= 1 && IsIdentChar(Text[At - 1])) continue;          // another name ending in MakeHudPress
    const FString Where = FString::Printf(TEXT("%s:%d"), *File, LineOf(Text, At));
    const int32 Open = At + Call.Len() - 1;
    const int32 Close = CloseParen(Text, Open);
    if (Close == INDEX_NONE) {
      Errors.Add(Where + TEXT(": unbalanced MakeHudPress call"));
      continue;
    }
    const FString Expr = Text.Mid(Open + 1, TopLevelComma(Text, Open + 1, Close) - Open - 1).TrimStartAndEnd();
    const TArray<FString> Literals = TextLiterals(Expr);
    if (Literals.Num() == 1 && IsHudId(Literals[0])) {
      FString Wildcard = Literals[0];
      if (Expr.Contains(TEXT("Printf"), ESearchCase::CaseSensitive)) {
        Wildcard.ReplaceInline(TEXT("%d"), TEXT("*"), ESearchCase::CaseSensitive);
        Wildcard.ReplaceInline(TEXT("%s"), TEXT("*"), ESearchCase::CaseSensitive);
      } else if (Expr.Contains(TEXT("+"))) {
        Wildcard += TEXT("*");
      }
      AddSourceId(Out, Wildcard, Where);
      continue;
    }
    // FName(Param) forwarded by a local helper lambda: the ids are the literals of its call sites in the same function.
    FString Lambda;
    int32 LambdaPos = INDEX_NONE;
    if (Literals.Num() != 0 || !EnclosingLambda(Text, At, Lambda, LambdaPos)) {
      Errors.Add(FString::Printf(TEXT("%s: id argument '%s' is not a literal HUD id nor a helper parameter"), *Where,
                                 *Expr));
      continue;
    }
    int32 FunctionEnd = Text.Find(TEXT("\n}"), ESearchCase::CaseSensitive, ESearchDir::FromStart, LambdaPos);
    if (FunctionEnd == INDEX_NONE) FunctionEnd = Text.Len();
    int32 Found = 0;
    const FString Use = Lambda + TEXT("(");
    for (int32 U = Text.Find(Use, ESearchCase::CaseSensitive, ESearchDir::FromStart, LambdaPos);
         U != INDEX_NONE && U < FunctionEnd;
         U = Text.Find(Use, ESearchCase::CaseSensitive, ESearchDir::FromStart, U + Use.Len())) {
      if (U > 0 && IsIdentChar(Text[U - 1])) continue;
      const int32 UseClose = CloseParen(Text, U + Use.Len() - 1);
      if (UseClose == INDEX_NONE) continue;
      for (const FString& L : TextLiterals(Text.Mid(U, UseClose - U))) {
        if (!IsHudId(L)) continue;
        AddSourceId(Out, L, FString::Printf(TEXT("%s:%d"), *File, LineOf(Text, U)));
        ++Found;
      }
    }
    if (Found == 0) Errors.Add(FString::Printf(TEXT("%s: helper '%s' has no call with a HUD id"), *Where, *Lambda));
  }
}

/** The ids of the live HUD: every MakeHudPress of the S08FlowGameMode*.cpp files. */
TArray<FSourceId> HudSourceIds(TArray<FString>& Errors) {
  TArray<FSourceId> Out;
  const FString Dir = FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::GameSourceDir(), TEXT("Unmatched/S08")));
  TArray<FString> Files;
  IFileManager::Get().FindFiles(Files, *FPaths::Combine(Dir, TEXT("S08FlowGameMode*.cpp")), true, false);
  Files.Sort();
  if (Files.Num() == 0) Errors.Add(TEXT("no S08FlowGameMode*.cpp under ") + Dir);
  for (const FString& File : Files) {
    FString Text;
    if (!FFileHelper::LoadFileToString(Text, *FPaths::Combine(Dir, File))) {
      Errors.Add(TEXT("cannot read ") + File);
      continue;
    }
    ParseHudIds(Text, File, Out, Errors);
  }
  return Out;
}

/** What the source cannot say: the reason a blocked element answers right
 *  now, and the runtime instances of the wildcard ids (three hand cards...).
 *  Every row must match an id of the source - a stale row fails the gate. */
TArray<FElement> ReasonOverlay() {
  return {
      FElement{FName(TEXT("hud.end.turn")), TEXT("button"),
               FS09Reason::Make(TEXT("why.actions.remaining")).Arg(TEXT("n"), 2)},
      FElement{FName(TEXT("hud.discard.confirm")), TEXT("button"),
               FS09Reason::Make(TEXT("why.discard.count")).Arg(TEXT("need"), 2).Arg(TEXT("have"), 1)},
      FElement{FName(TEXT("hud.scheme.play")), TEXT("button"), FS09Reason::Make(TEXT("why.scheme.none"))},
      FElement{FName(TEXT("hud.defense.none")), TEXT("button"), FS09Reason::Make(TEXT("why.deadline.passed"))},
      FElement{FName(TEXT("hud.combat.resolve")), TEXT("button"), FS09Reason::Make(TEXT("why.wait.opponent.choice"))},
      FElement{FName(TEXT("hud.pending.decline")), TEXT("button"), FS09Reason::Make(TEXT("why.choice.required"))},
      FElement{FName(TEXT("hud.result.lobby")), TEXT("button"), FS09Reason::Make(TEXT("why.syncing"))},
      FElement{FName(TEXT("hud.result.board.lobby")), TEXT("button"), FS09Reason::Make(TEXT("why.syncing"))},
      FElement{FName(TEXT("hud.abort.lobby")), TEXT("button"), FS09Reason::Make(TEXT("why.syncing"))},
      FElement{FName(TEXT("hand.card::0")), TEXT("card"), FS09Reason()},
      FElement{FName(TEXT("hand.card::1")), TEXT("card"), FS09Reason()},
      FElement{FName(TEXT("hand.card::2")), TEXT("card"), FS09Reason()},
      FElement{FName(TEXT("discard.0.card::4")), TEXT("deck"), FS09Reason()},
      FElement{FName(TEXT("hud.deck.row.card-7")), TEXT("deck"), FS09Reason()},
      FElement{FName(TEXT("pending.option.0")), TEXT("button"), FS09Reason()},
      FElement{FName(TEXT("pending.reveal.card::7")), TEXT("button"), FS09Reason()},
  };
}

const TCHAR* KindOf(const FString& Id) {
  if (Id.StartsWith(TEXT("hand."))) return TEXT("card");
  if (Id.StartsWith(TEXT("discard.")) || Id.StartsWith(TEXT("hud.deck.")) || Id == TEXT("hud.discard.browse")) {
    return TEXT("deck");
  }
  return TEXT("button");
}

/** The HUD layout: every source id (its overlay rows, else one open element). */
TArray<FElement> HudLayout(const TArray<FSourceId>& Source, TArray<FString>& Errors) {
  const TArray<FElement> Overlay = ReasonOverlay();
  TArray<bool> Used;
  Used.Init(false, Overlay.Num());
  TArray<FElement> Layout;
  for (const FSourceId& Src : Source) {
    bool bAny = false;
    for (int32 R = 0; R < Overlay.Num(); ++R) {
      if (Used[R] || !Overlay[R].Id.ToString().MatchesWildcard(Src.Wildcard, ESearchCase::CaseSensitive)) continue;
      Used[R] = true;
      bAny = true;
      Layout.Add(Overlay[R]);
    }
    if (!bAny) {
      const FString Sample = Src.Wildcard.Replace(TEXT("*"), TEXT("x0"));
      Layout.Add(FElement{FName(*Sample), KindOf(Sample), FS09Reason()});
    }
  }
  for (int32 R = 0; R < Overlay.Num(); ++R) {
    if (!Used[R]) Errors.Add(TEXT("overlay row without a MakeHudPress id in the source: ") + Overlay[R].Id.ToString());
  }
  return Layout;
}

// ---- the Slate HUD on a stepped frame clock -------------------------------------

/** A Slate HUD that RefreshHud rebuilds wholesale: one live SS09HudPress per
 *  element id, re-created (a new instance, same id and place) on Rebuild. The
 *  frame clock of the press stamps is the test's: Step advances it and ticks
 *  every live element, as Slate does once per frame. */
struct FHud {
  TSharedPtr<FS09HudPressArbiter> Arbiter = MakeShared<FS09HudPressArbiter>();
  TArray<FElement> Layout;
  TMap<FName, TSharedPtr<SS09HudPress>> Live;
  TMap<FName, int32> Row;  // element -> row (its place on screen)
  TMap<FName, int32> Acts;
  TArray<FS09HudPressOutcome> Answers;  // every resolved release (Act / Refused)
  TArray<uint64> AnswerFrames;          // the frame each answer reached the game mode in
  uint64 Frame = 1000;
  int32 Rebuilds = 0;

  explicit FHud(const TArray<FElement>& InLayout) : Layout(InLayout) {
    Arbiter->SetFrameClock([this]() { return Frame; });
    Build();
  }
  FHud(const FHud&) = delete;  // the clock captures this

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
                                 AnswerFrames.Add(Frame);
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
  /** Frames pass: the clock moves and every live element ticks. */
  void Step(int32 Frames) {
    for (int32 F = 0; F < Frames; ++F) {
      ++Frame;
      TArray<FName> Ids;
      Live.GetKeys(Ids);
      for (const FName& Id : Ids) {
        const TSharedPtr<SS09HudPress> W = Live.FindRef(Id);
        if (W.IsValid()) static_cast<SWidget&>(*W).Tick(GeometryOf(Id), Frame * FrameSeconds, static_cast<float>(FrameSeconds));
      }
    }
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

/** The frames one synthetic click was issued in. */
struct FIssued {
  uint64 Press = 0;
  uint64 Release = 0;
};

/** Frames after a release before the next press: a deferred answer would land
 *  here, in a frame other than the release's. */
constexpr int32 GapFrames = 2;

/** One synthetic click: the press lands on the element under At; HoldFrames
 *  frames pass (the rebuilds happen in the first of them); the release goes to
 *  the captor while it lives, else (rebuilt away) to the element now under the
 *  cursor - exactly Slate's routing; then GapFrames pass. */
FIssued Click(FHud& Hud, const FVector2D& At, int32 RebuildsDuringHold, int32 HoldFrames,
              const FVector2D* ReleaseAt = nullptr, TFunction<void(FHud&)> MoveLayout = nullptr) {
  FIssued Issued;
  FName DownId;
  TSharedPtr<SS09HudPress> Pressed = Hud.Under(At, DownId);
  if (!Pressed.IsValid()) return Issued;
  Issued.Press = Hud.Frame;
  Pressed->OnMouseButtonDown(Hud.GeometryOf(DownId), LeftEvent(At, true));
  TWeakPtr<SS09HudPress> Captor = Pressed;
  Pressed.Reset();
  if (HoldFrames > 0) Hud.Step(1);
  for (int32 R = 0; R < RebuildsDuringHold; ++R) Hud.Rebuild();
  if (MoveLayout) MoveLayout(Hud);
  if (HoldFrames > 1) Hud.Step(HoldFrames - 1);
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
  Issued.Release = Hud.Frame;
  if (Target.IsValid()) {
    Target->OnMouseButtonUp(Hud.GeometryOf(TargetId), LeftEvent(Up, false));
  } else {
    Hud.Arbiter->Release(NAME_None, Hud.Frame);  // the game mode's stray-release resolve
  }
  Hud.Step(GapFrames);
  return Issued;
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

/** True when a hit-testable SButton sits anywhere under Widget's hit-testable children. */
bool ContentTakesHit(const TSharedRef<SWidget>& Widget) {
  FChildren* Children = Widget->GetChildren();
  if (!Children) return false;
  for (int32 I = 0; I < Children->Num(); ++I) {
    const TSharedRef<SWidget> Child = Children->GetChildAt(I);
    const EVisibility Vis = Child->GetVisibility();
    if (Vis.IsHitTestVisible() && Child->GetType() == FName(TEXT("SButton"))) return true;
    if (Vis.AreChildrenHitTestVisible() && ContentTakesHit(Child)) return true;
  }
  return false;
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
    TestTrue(TEXT("press and release frames kept apart"), Rebuilt.PressFrame == 1 && Rebuilt.ReleaseFrame == 4);
  }
  {
    FS09HudPressArbiter Arb;
    TestTrue(TEXT("default clock: the engine frame"), Arb.Now() == GFrameCounter);
    uint64 Clock = 41;
    Arb.SetFrameClock([&Clock]() { return Clock; });
    TestTrue(TEXT("a test clock drives the stamps"), Arb.Now() == 41);
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
  TArray<FString> Errors;
  const TArray<FSourceId> Source = HudSourceIds(Errors);
  const TArray<FElement> Layout = HudLayout(Source, Errors);
  for (const FString& E : Errors) AddError(TEXT("HUD layout from the source: ") + E);
  // The parser still sees the HUD (34 ids at run H; a lost parse shows as a short list and stale overlay rows).
  TestTrue(TEXT("the game mode source yields the HUD ids"), Source.Num() >= 30);
  for (const FSourceId& Src : Source) AddInfo(FString::Printf(TEXT("HUD id %s (%s)"), *Src.Wildcard, *Src.Where));

  constexpr int32 N = 20;
  // Snapshots land at irregular times (WS events), on top of the countdown.
  const TArray<double> Snapshots = {0.31, 0.74, 1.12, 1.53, 2.08, 2.61, 3.37, 4.02, 4.66};
  int32 TotalPresses = 0;
  int32 TotalAnswered = 0;
  int32 SButtonLost = 0;  // the instance-bound contract, same timeline
  int32 Straddled = 0;
  int32 SpannedFrames = 0;  // presses whose release came in a later frame than the press
  for (const double Hold : {0.0, 0.050}) {
    const int32 HoldFrames = FMath::RoundToInt(Hold / FrameSeconds);  // 0 and 3
    for (int32 E = 0; E < Layout.Num(); ++E) {
      const FElement& Element = Layout[E];
      FHud Hud(Layout);
      TArray<FIssued> Issued;
      for (int32 K = 0; K < N; ++K) {
        // Press phases sweep the countdown period: every second 50 ms hold
        // straddles a rebuild (0.22 + 0.05 crosses the 0.25 s tick).
        const double PressAt = K * CountdownSeconds + ((K % 2) ? 0.22 : 0.05) + E * FrameSeconds * 0.01;
        const int32 Rebuilds = RebuildsInHold(PressAt, Hold, Snapshots);
        Straddled += Rebuilds > 0 ? 1 : 0;
        SButtonLost += Rebuilds > 0 ? 1 : 0;  // a new instance never saw the press
        Issued.Add(Click(Hud, FHud::RowCentre(E), Rebuilds, HoldFrames));
        ++TotalPresses;
      }
      const int32 Answered = Hud.Answers.Num();
      TotalAnswered += Answered;
      const FString Tag =
          FString::Printf(TEXT("%s %s hold %.0f ms"), Element.Kind, *Element.Id.ToString(), Hold * 1000.0);
      TestEqual(Tag + TEXT(": every press answered (0 lost)"), Answered, N);
      int32 Acted = 0;
      int32 Refused = 0;
      bool bReasonKeyed = true;
      bool bOwnId = true;
      bool bStamped = true;      // the outcome carries the frames of its own press and release
      bool bReleaseFrame = true; // the answer reached the game mode in the frame of the release
      for (int32 I = 0; I < Hud.Answers.Num(); ++I) {
        const FS09HudPressOutcome& A = Hud.Answers[I];
        Acted += A.Result == ES09HudPressResult::Act ? 1 : 0;
        Refused += A.Result == ES09HudPressResult::Refused ? 1 : 0;
        if (A.Result == ES09HudPressResult::Refused) {
          bReasonKeyed &= A.Reason.IsSet() && A.Reason.Key.ToString().StartsWith(TEXT("why.")) &&
                          S08WhyText::Has(A.Reason.Key);
        }
        bOwnId &= A.PressedId == Element.Id && A.ReleasedId == Element.Id;
        if (!Issued.IsValidIndex(I)) continue;  // more answers than presses: the count check fails above
        bStamped &= A.PressFrame == Issued[I].Press && A.ReleaseFrame == Issued[I].Release;
        bReleaseFrame &= Hud.AnswerFrames[I] == Issued[I].Release;
        SpannedFrames += Issued[I].Release > Issued[I].Press ? 1 : 0;
      }
      if (Element.Blocked.IsSet()) {
        TestEqual(Tag + TEXT(": blocked - every press is CUE-004"), Refused, N);
        TestTrue(Tag + TEXT(": ... with a why.* key"), bReasonKeyed);
      } else {
        TestEqual(Tag + TEXT(": open - every press acts"), Acted, N);
        TestEqual(Tag + TEXT(": ... once per press"), Hud.Acts.FindRef(Element.Id), N);
      }
      TestTrue(Tag + TEXT(": the answer belongs to the pressed element"), bOwnId);
      TestTrue(Tag + TEXT(": the press and release frames are stamped"), bStamped);
      TestTrue(Tag + TEXT(": answered in the frame of the release (no deferral)"), bReleaseFrame);
      TestFalse(Tag + TEXT(": no press left hanging"), Hud.Arbiter->IsPressed());
    }
  }
  TestEqual(TEXT("n >= 20 per element and hold: all answered"), TotalAnswered, TotalPresses);
  TestTrue(TEXT("the timeline straddles rebuilds (the test can see the defect)"), Straddled >= Layout.Num() * N / 2);
  TestEqual(TEXT("every 50 ms hold spans frames (the frame check can see a deferral)"), SpannedFrames,
            Layout.Num() * N);
  TestTrue(TEXT("the SButton contract would lose those presses"), SButtonLost > 0);
  AddInfo(FString::Printf(TEXT("DE-014 synthetic clicks: %d presses on %d elements (%d MakeHudPress ids of the game "
                               "mode source) x {0, 50 ms} x %d, answered %d, lost 0, every answer in the frame of its "
                               "release; %d presses straddled a HUD rebuild (an instance-bound SButton loses them)"),
                          TotalPresses, Layout.Num(), Source.Num(), N, TotalAnswered, Straddled));

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
    Click(Hud, FHud::RowCentre(0), 0, 0, &Other);
    TestEqual(TEXT("drag to another element, no rebuild: cancelled, no answer (MS-R-34)"), Hud.Answers.Num(), 0);
    // A card drawn under the held press shifts the hand: another element is
    // under the cursor after the rebuild.
    const FName Card0(TEXT("hand.card::0"));
    const int32 CardRow = Hud.Row.FindChecked(Card0);
    Click(Hud, FHud::RowCentre(CardRow), 1, 3, nullptr, [Card0](FHud& H) {
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

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09HudPressInteractableTest, "Unmatched.S09.HudPress.Interactable",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09HudPressInteractableTest::RunTest(const FString&) {
  // Automation Driver's ElementIsInteractable = IsEnabled + hit-test visible + the
  // hit test at the centre reaches the widget. The first two legs and the
  // structure behind the third are checked here on the game mode's own builder
  // (SS09HudPress::MakeButton); the painted hit-test grid needs a live window
  // (run H R-05 journal: why the Developer module is not used).
  const TSharedPtr<FS09HudPressArbiter> Arbiter = MakeShared<FS09HudPressArbiter>();
  struct FKeyButton {
    const TCHAR* Id;
    bool bDimmed;
  };
  const FKeyButton Keys[] = {
      {TEXT("hud.end.turn"), true},          {TEXT("hud.end.turn"), false},
      {TEXT("hud.begin.maneuver"), false},   {TEXT("hud.defense.play"), false},
      {TEXT("hud.defense.none"), true},      {TEXT("hud.combat.resolve"), true},
      {TEXT("hud.pending.confirm"), false},  {TEXT("hud.result.lobby"), true},
      {TEXT("hand.card::0"), false},         {TEXT("hud.deck.close"), false},
  };
  for (const FKeyButton& Key : Keys) {
    int32 Answers = 0;
    const TSharedRef<SS09HudPress> W = SS09HudPress::MakeButton(
        FName(Key.Id), Arbiter,
        FS09OnHudPressOutcome::CreateLambda([&Answers](const FS09HudPressOutcome&) { ++Answers; }), FMargin(8, 3),
        FLinearColor::White, Key.bDimmed, SNew(STextBlock).Text(FText::FromString(Key.Id)));
    const FString Tag = FString::Printf(TEXT("%s%s"), Key.Id, Key.bDimmed ? TEXT(" (blocked, dimmed)") : TEXT(""));
    TestTrue(Tag + TEXT(": enabled (a blocked element answers its reason, never drops the press)"), W->IsEnabled());
    TestTrue(Tag + TEXT(": hit-test visible"), W->GetVisibility().IsHitTestVisible());
    TestFalse(Tag + TEXT(": no SButton of the content can take the press"), ContentTakesHit(W));
    TestFalse(Tag + TEXT(": takes no keyboard focus (the viewport keeps it)"), W->SupportsKeyboardFocus());
    // The element itself answers a click at its centre (the leg the hit test would route here).
    const FGeometry G = FGeometry::MakeRoot(FVector2D(160.0, 40.0), FSlateLayoutTransform(FVector2D(100.0, 200.0)));
    const FVector2D Centre = G.LocalToAbsolute(G.GetLocalSize() * 0.5f);
    W->OnMouseButtonDown(G, LeftEvent(Centre, true));
    W->OnMouseButtonUp(G, LeftEvent(Centre, false));
    TestEqual(Tag + TEXT(": a click at the centre is answered"), Answers, 1);
  }
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
