// MS-T-17 automation (docs/game-design/move-selection 06 MS-AT-26): Unmatched.S09.MoveSel.OpponentView - the planning
// indicator of the opponent's pendingManeuver (and no draft of theirs on this client), the last-move highlight that
// appears after the animation and goes out on the first applied seq > lastMovement.seq in which positions, the HP of
// any fighter or currentTurnPlayerId changed (MS-P-03), kept by an opponent's beginManeuver (MS-E-103), restored
// without an animation after a reconnect at lastMovement.seq == snapshot seq (MS-E-102), the ms.log.* feed line with
// "and N more" over three moves (MS-E-106), the plate channels V-14 / V-15 on a real board, the edge arrow (MS-E-73)
// and the -BenchMoveDraft lastMovement scene. Board: the real Marmoreal bench game state only.
#include "Misc/AutomationTest.h"

#include "S09OpponentView.h"
#include "S09ManeuverUi.h"
#include "S09MoveDraftView.h"
#include "../S08/S08BoardModel.h"
#include "../S08/S08Contracts.h"
#include "../S08/S08MoveHighlight.h"
#include "../S08/S08WhyText.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

namespace S09OppTest {
struct FBench {
  FS08Snapshot Snapshot;
  FS08BoardModel Board;
  TArray<FS08BoardFighter> Fighters;
  FString ViewerId;
};

bool LoadBench(const TCHAR* File, FBench& Out) {
  FString Text;
  if (!FFileHelper::LoadFileToString(Text, *FPaths::Combine(FPaths::ProjectConfigDir(), TEXT("Bench"), File))) return false;
  TSharedPtr<FJsonObject> Root;
  FString Problem;
  if (!FS08Contracts::TryParseJsonObject(Text, Root, Problem) || !Root.IsValid()) return false;
  Root->TryGetStringField(TEXT("benchViewerId"), Out.ViewerId);
  FString Body;
  const TSharedPtr<FJsonObject>* Raw = nullptr;
  if (!Root->TryGetStringField(TEXT("raw"), Body)) {
    if (!Root->TryGetObjectField(TEXT("raw"), Raw) || !Raw->IsValid()) return false;
    const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Body);
    FJsonSerializer::Serialize(Raw->ToSharedRef(), Writer);
  }
  FString RawState;
  FS08GraphQLError Error;
  return FS08Contracts::ParseGameStateQuery(Body, Out.Snapshot, RawState, Error) &&
         FS08BoardModel::DecodeFighters(Out.Snapshot.Fighters, Out.Fighters) && Out.Board.Decode(Out.Snapshot.BoardState);
}

FIntPoint SpaceAt(const FS08BoardModel& Board, const TCHAR* SpaceId) {
  for (const FS08Cell& C : Board.Cells) {
    if (C.SpaceId == SpaceId) return FIntPoint(C.X, C.Y);
  }
  return FIntPoint(-1, -1);
}

TSharedPtr<FJsonValue> Json(const FString& Text) {
  TSharedPtr<FJsonValue> Value;
  FString Problem;
  FS08Contracts::TryParseJsonValue(Text, Value, Problem);
  return Value;
}

FString XY(const FIntPoint& C) { return FString::Printf(TEXT("{\"x\":%d,\"y\":%d}"), C.X, C.Y); }

/** metadata with lastMovement: Moves = "fighterId:from>step>step..." over space ids of Board. */
TSharedPtr<FJsonValue> TrailMeta(const FS08BoardModel& Board, int32 Seq, const FString& PlayerId, const FString& Source,
                                 const FString& BoostJson, const TArray<FString>& Moves) {
  TArray<FString> Entries;
  for (int32 I = 0; I < Moves.Num(); ++I) {
    FString Fighter, Cells;
    Moves[I].Split(TEXT(":"), &Fighter, &Cells);
    TArray<FString> Ids;
    Cells.ParseIntoArray(Ids, TEXT(">"));
    TArray<FString> Path;
    for (int32 K = 1; K < Ids.Num(); ++K) Path.Add(XY(SpaceAt(Board, *Ids[K])));
    Entries.Add(FString::Printf(TEXT("{\"order\":%d,\"fighterId\":\"%s\",\"kind\":\"MOVE\",\"from\":%s,\"path\":[%s]}"), I,
                                *Fighter, *XY(SpaceAt(Board, *Ids[0])), *FString::Join(Path, TEXT(","))));
  }
  return Json(FString::Printf(
      TEXT("{\"actionsRemaining\":1,\"lastMovement\":{\"seq\":%d,\"playerId\":\"%s\",\"source\":\"%s\",")
          TEXT("\"sourceRef\":\"maneuver:1\",\"boost\":%s,\"moves\":[%s]}}"),
      Seq, *PlayerId, *Source, *BoostJson, *FString::Join(Entries, TEXT(","))));
}

FS08BoardFighter* Mutable(TArray<FS08BoardFighter>& Fighters, const TCHAR* Id) {
  return Fighters.FindByPredicate([Id](const FS08BoardFighter& F) { return F.Id == Id; });
}
}  // namespace S09OppTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09MoveSelOpponentViewTest, "Unmatched.S09.MoveSel.OpponentView",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09MoveSelOpponentViewTest::RunTest(const FString&) {
  using namespace S09OppTest;
  FBench B;
  if (!TestTrue(TEXT("Marmoreal bench state"), LoadBench(TEXT("S08BenchMarmoreal.json"), B))) return false;
  const FString Me = B.ViewerId;
  const FS08BoardFighter* Arthur = B.Fighters.FindByPredicate([](const FS08BoardFighter& F) { return F.Id == TEXT("f-1-hero"); });
  if (!TestNotNull(TEXT("King Arthur in the bench state"), Arthur)) return false;
  const FString Opp = Arthur->OwnerId;
  TestTrue(TEXT("Arthur on M31"), FIntPoint(Arthur->X, Arthur->Y) == SpaceAt(B.Board, TEXT("M31")));

  // ---- MS-S-11: the indicator follows pendingManeuver.playerId; the opponent's draft never opens here ----
  {
    FS08Snapshot Planning = B.Snapshot;
    Planning.Metadata = Json(FString::Printf(TEXT("{\"actionsRemaining\":1,\"pendingManeuver\":{\"id\":\"m:1\",\"playerId\":\"%s\"}}"), *Opp));
    Planning.CurrentTurnPlayerId = Opp;
    TestEqual(TEXT("pendingManeuver.playerId"), S09OpponentView::PendingManeuverPlayer(Planning), Opp);
    TestTrue(TEXT("the opponent plans: indicator on"), S09OpponentView::OpponentPlanning(Planning, Me));
    TestFalse(TEXT("the same snapshot for its owner: no indicator"), S09OpponentView::OpponentPlanning(Planning, Opp));
    TestFalse(TEXT("no open maneuver: no indicator"), S09OpponentView::OpponentPlanning(B.Snapshot, Me));
    FS09CommandUi Ui;
    Ui.ViewerId = Me;
    Ui.OnSnapshot(Planning, B.Board, B.Fighters);
    TestTrue(TEXT("no draft of the opponent's maneuver on this client (AP-13)"), Ui.Mode != ES09CommandMode::ManeuverDraft &&
                                                                                   Ui.Moves.Num() == 0);
    TestEqual(TEXT("ms.opp.planning EN"), S08WhyText::En(FName(TEXT("ms.opp.planning"))),
              FString(TEXT("Opponent is planning a maneuver")));
    TestEqual(TEXT("pulse off with reduced motion"), S09OpponentView::PlanningPulse(0.37, true), 1.0f);
    TestTrue(TEXT("pulse 1 Hz: full at 0 s"), FMath::IsNearlyEqual(S09OpponentView::PlanningPulse(0.0, false), 1.0f));
    TestTrue(TEXT("pulse 1 Hz: low at 0.5 s"), FMath::IsNearlyEqual(S09OpponentView::PlanningPulse(0.5, false), 0.45f, 1e-4f));
    TestTrue(TEXT("pulse 1 Hz: full again at 1 s"), FMath::IsNearlyEqual(S09OpponentView::PlanningPulse(1.0, false), 1.0f, 1e-4f));
  }

  // ---- lastMovement (04 §4.3) ----
  const TSharedPtr<FJsonValue> Meta10 =
      TrailMeta(B.Board, 10, Opp, TEXT("MANEUVER"), TEXT("{\"cardId\":\"c::1\",\"catalogId\":\"c1\",\"name\":\"Feint\",\"value\":2}"),
                {TEXT("f-1-hero:M22>M30>M31"), TEXT("f-1-sk0:M24>M23")});
  FS09LastMovement Trail10;
  if (!TestTrue(TEXT("trail reads"), FS09LastMovement::Read(Meta10, Trail10))) return false;
  TestEqual(TEXT("trail seq"), Trail10.Seq, 10);
  TestEqual(TEXT("trail player"), Trail10.PlayerId, Opp);
  TestTrue(TEXT("trail boost +2 Feint"), Trail10.bBoost && Trail10.BoostValue == 2 && Trail10.BoostName == TEXT("Feint"));
  TestEqual(TEXT("two moves"), Trail10.Moves.Num(), 2);
  TestTrue(TEXT("Arthur's path ends on M31"), Trail10.Moves[0].Dest() == SpaceAt(B.Board, TEXT("M31")));
  {
    FS09LastMovement Bad;
    TestFalse(TEXT("no lastMovement"), FS09LastMovement::Read(Json(TEXT("{\"actionsRemaining\":1}")), Bad));
    TestFalse(TEXT("lastMovement null (a save before MS-T-14)"), FS09LastMovement::Read(Json(TEXT("{\"lastMovement\":null}")), Bad));
    TestFalse(TEXT("no playerId"), FS09LastMovement::Read(Json(TEXT("{\"lastMovement\":{\"seq\":3,\"moves\":[]}}")), Bad));
    TestTrue(TEXT("boost null, a PLACE with two cells dropped"),
             FS09LastMovement::Read(Json(TEXT("{\"lastMovement\":{\"seq\":3,\"playerId\":\"p\",\"source\":\"EFFECT\",\"boost\":null,")
                                         TEXT("\"moves\":[{\"fighterId\":\"a\",\"kind\":\"PLACE\",\"from\":{\"x\":0,\"y\":0},")
                                         TEXT("\"path\":[{\"x\":1,\"y\":0},{\"x\":2,\"y\":0}]}]}}")),
                                    Bad) &&
                 !Bad.bBoost && Bad.Moves.Num() == 0);
  }

  // ---- MS-P-03: after the animation; kept by beginManeuver; out on the first changed seq, 300 ms fade ----
  const FS09BoardStamp Before = FS09BoardStamp::Make(B.Fighters, Opp);
  {
    FS09LastMoveTracker T;
    T.OnApplied(9, FS09LastMovement(), Before, 0.0, false);
    TArray<FS08BoardFighter> After10 = B.Fighters;  // the positions of the bench state are the trail's ends
    const FS09BoardStamp Stamp10 = FS09BoardStamp::Make(After10, Opp);
    const TArray<FString> Enter = T.OnApplied(10, Trail10, Stamp10, 1000.0, false);
    TestTrue(TEXT("enter traced"), Enter.Num() == 1 && Enter[0].StartsWith(TEXT("MS-LAST enter seq=10")));
    T.OnMoveAnimation(10, 1000.0 + 990.0);
    TestTrue(TEXT("waiting for the animation"), T.GetState() == ES09LastMoveState::Waiting && !T.IsDrawn());
    T.Tick(1500.0, true);
    TestTrue(TEXT("not during the move (MS-P-02)"), T.GetState() == ES09LastMoveState::Waiting);
    const TArray<FString> Show = T.Tick(2000.0, false);
    TestTrue(TEXT("shown at the end of the animation"), T.GetState() == ES09LastMoveState::Shown && T.Alpha(2000.0) == 1.0f);
    TestTrue(TEXT("show traced mode=anim"), Show.Num() == 1 && Show[0].Contains(TEXT("mode=anim")));
    TestFalse(TEXT("not a restore"), T.WasRestored());
    FS09LastMovement Revealed;
    TestTrue(TEXT("the feed gets the reveal once"), T.ConsumeRevealed(Revealed) && Revealed.Seq == 10 && !T.ConsumeRevealed(Revealed));
    // the turn passes at seq 11 (end of turn, no movement): currentTurnPlayerId changed -> out
    const FS09BoardStamp Turn = FS09BoardStamp::Make(After10, Me);
    T.OnApplied(11, Trail10, Turn, 2100.0, false);
    TestTrue(TEXT("a changed currentTurnPlayerId puts it out"), T.GetState() == ES09LastMoveState::Fading);

    FS09LastMoveTracker K;
    K.OnApplied(10, Trail10, Stamp10, 0.0, false);
    K.Tick(0.0, false);
    TestTrue(TEXT("no animation for its seq: shown at once"), K.GetState() == ES09LastMoveState::Shown && K.WasRestored());
    K.OnApplied(10, Trail10, Stamp10, 10.0, false);
    TestTrue(TEXT("a same-seq merge keeps it"), K.GetState() == ES09LastMoveState::Shown);
    const uint32 Rev = K.GetRevision();
    K.OnApplied(11, Trail10, Stamp10, 20.0, false);  // beginManeuver: hand only
    TestTrue(TEXT("beginManeuver keeps it (MS-E-103)"), K.GetState() == ES09LastMoveState::Shown && K.GetRevision() == Rev);
    TArray<FS08BoardFighter> Hit = After10;
    Mutable(Hit, TEXT("f-0-hero"))->Health -= 2;
    K.OnApplied(12, Trail10, FS09BoardStamp::Make(Hit, Opp), 100.0, false);
    TestTrue(TEXT("HP of any fighter puts it out"), K.GetState() == ES09LastMoveState::Fading);
    TestTrue(TEXT("half faded at 150 ms"), FMath::IsNearlyEqual(K.Alpha(250.0), 0.5f, 1e-3f));
    K.Tick(399.0, false);
    TestTrue(TEXT("still fading at 299 ms"), K.GetState() == ES09LastMoveState::Fading);
    K.Tick(400.0, false);
    TestTrue(TEXT("gone after 300 ms"), K.GetState() == ES09LastMoveState::None && K.Alpha(400.0) == 0.0f);

    FS09LastMoveTracker Moved;
    Moved.OnApplied(10, Trail10, Stamp10, 0.0, false);
    Moved.Tick(0.0, false);
    TArray<FS08BoardFighter> Step = After10;
    Mutable(Step, TEXT("f-0-sk0"))->X = 1;
    Moved.OnApplied(12, Trail10, FS09BoardStamp::Make(Step, Opp), 50.0, true);
    TestTrue(TEXT("a position puts it out; reduced motion: at once"), Moved.GetState() == ES09LastMoveState::None);

    FS09LastMoveTracker Skip;
    Skip.OnApplied(10, Trail10, Stamp10, 0.0, false);
    Skip.OnMoveAnimation(10, 2400.0);
    Skip.Tick(300.0, false);  // a skip key landed the figures
    TestTrue(TEXT("a skip reveals it with the arrival"), Skip.GetState() == ES09LastMoveState::Shown && !Skip.WasRestored());
  }
  // ---- MS-E-102: reconnect - restored without an animation only at lastMovement.seq == snapshot seq ----
  {
    FS09LastMoveTracker Fresh;
    Fresh.OnApplied(10, Trail10, Before, 0.0, false);
    const TArray<FString> Show = Fresh.Tick(0.0, false);
    TestTrue(TEXT("restored at once"), Fresh.IsDrawn() && Fresh.WasRestored() && Show.Num() == 1 && Show[0].Contains(TEXT("mode=restore")));
    FS09LastMoveTracker Later;
    Later.OnApplied(11, Trail10, Before, 0.0, false);
    Later.Tick(0.0, false);
    TestFalse(TEXT("an older trail is not restored"), Later.IsDrawn());
  }

  // ---- the feed: ms.log.*, "and N more" over three moves, once per seq, three lines ----
  {
    auto PlayerName = [&](const FString& Id) { return Id == Opp ? FString(TEXT("King Arthur")) : FString(TEXT("Medusa")); };
    auto FighterName = [&](const FString& Id) {
      const FS08BoardFighter* F = B.Fighters.FindByPredicate([&Id](const FS08BoardFighter& X) { return X.Id == Id; });
      return F ? (F->Label.IsEmpty() ? F->Name : F->Label) : Id;
    };
    auto CellName = [&](const FIntPoint& C) { return B.Board.CellLabel(C.X, C.Y); };
    const FS09FeedEntry Line = FS09EventFeed::Describe(Trail10, PlayerName, FighterName, CellName);
    TestEqual(TEXT("maneuver line with boost"), Line.Text,
              FString(TEXT("King Arthur: maneuver, boost +2 (Feint): King Arthur M22→M31, Merlin M24→M23")));
    TestFalse(TEXT("two moves: not cut"), Line.bTruncated);
    FS09LastMovement Four;
    FS09LastMovement::Read(TrailMeta(B.Board, 20, Me, TEXT("MANEUVER"), TEXT("null"),
                                     {TEXT("f-0-sk2:M01>M02"), TEXT("f-0-sk0:M07>M08"), TEXT("f-0-hero:M13>M20"),
                                      TEXT("f-0-sk1:M20>M21")}),
                           Four);
    const FS09FeedEntry Cut = FS09EventFeed::Describe(Four, PlayerName, FighterName, CellName);
    TestTrue(TEXT("four moves: the first two + and 2 more (MS-E-106)"),
             Cut.bTruncated && Cut.Text.EndsWith(TEXT(", and 2 more")) && Cut.Text.StartsWith(TEXT("Medusa: maneuver: ")));
    TestTrue(TEXT("the tooltip lists all four"), Cut.Full.Contains(TEXT("M20→M21")) && !Cut.Text.Contains(TEXT("M20→M21")));
    FS09LastMovement Stay;
    FS09LastMovement::Read(TrailMeta(B.Board, 21, Opp, TEXT("MANEUVER"), TEXT("null"), {}), Stay);
    TestEqual(TEXT("a maneuver without movement"), FS09EventFeed::Describe(Stay, PlayerName, FighterName, CellName).Text,
              FString(TEXT("King Arthur: maneuver: no movement")));
    FS09EventFeed Feed;
    TestTrue(TEXT("added"), Feed.Add(Trail10, PlayerName, FighterName, CellName));
    TestFalse(TEXT("once per seq (a reconnect restore does not repeat it)"), Feed.Add(Trail10, PlayerName, FighterName, CellName));
    FS09LastMovement Effect;
    FS09LastMovement::Read(TrailMeta(B.Board, 22, Opp, TEXT("EFFECT"), TEXT("null"), {TEXT("f-1-sk0:M24>M23")}), Effect);
    TestFalse(TEXT("an EFFECT move is not a maneuver line (DE-022)"), Feed.Add(Effect, PlayerName, FighterName, CellName));
    Feed.Add(Four, PlayerName, FighterName, CellName);
    Feed.Add(Stay, PlayerName, FighterName, CellName);
    FS09LastMovement Next = Stay;
    Next.Seq = 30;
    Feed.Add(Next, PlayerName, FighterName, CellName);
    TestEqual(TEXT("three lines"), Feed.GetLines().Num(), 3);
    TestEqual(TEXT("the oldest dropped"), Feed.GetLines()[0].Seq, 20);
  }

  // ---- V-14 / V-15 on the plates of a real board ----
  {
    const FS08MoveDraftInput::FLastMove Last = S09OpponentView::LastMoveInput(Trail10, ES08PlateColor::TeamP2);
    FS08MoveDraftInput Input;
    Input.ViewerId = Me;
    Input.LastMove = Last;
    Input.Source = TEXT("last");
    const FS08MoveDraftView View = S08MoveHighlight::BuildDraftView(B.Board, B.Fighters, Input);
    auto At = [&](const TCHAR* Id) {
      const FIntPoint C = SpaceAt(B.Board, Id);
      return View.Find(C.X, C.Y);
    };
    TestTrue(TEXT("M22 start: LastFrom in P2"), At(TEXT("M22")) && At(TEXT("M22"))->Outline == ES08OutlineState::LastFrom &&
                                                 At(TEXT("M22"))->OutlineColor == ES08PlateColor::TeamP2);
    TestTrue(TEXT("M30 path point: a centre dot, no outline"),
             At(TEXT("M30")) && At(TEXT("M30"))->bPathDot && At(TEXT("M30"))->Outline == ES08OutlineState::None);
    TestTrue(TEXT("M31 end: LastTo"), At(TEXT("M31")) && At(TEXT("M31"))->Outline == ES08OutlineState::LastTo);
    TestTrue(TEXT("M23 end of the second move: LastTo"), At(TEXT("M23")) && At(TEXT("M23"))->Outline == ES08OutlineState::LastTo);
    TestTrue(TEXT("no ring of its own"), At(TEXT("M31"))->Ring == ES08RingState::None);
    // a chain: Merlin ends where Arthur started -> the end wins
    FS09LastMovement Chain;
    FS09LastMovement::Read(TrailMeta(B.Board, 5, Opp, TEXT("MANEUVER"), TEXT("null"), {TEXT("f-1-hero:M22>M30"), TEXT("f-1-sk0:M18>M22")}), Chain);
    const FS08MoveDraftView ChainView = S08MoveHighlight::BuildDraftView(
        B.Board, B.Fighters, [&] {
          FS08MoveDraftInput In;
          In.LastMove = S09OpponentView::LastMoveInput(Chain, ES08PlateColor::TeamP1);
          return In;
        }());
    const FIntPoint M22 = SpaceAt(B.Board, TEXT("M22"));
    TestTrue(TEXT("a start that is also an end: LastTo"), ChainView.Find(M22.X, M22.Y) &&
                                                         ChainView.Find(M22.X, M22.Y)->Outline == ES08OutlineState::LastTo);
    // joined with an own draft: the draft keeps its rings, the outline channel the last move
    FS08MoveDraftInput Draft;
    Draft.ViewerId = Me;
    FS08MoveDraftInput::FMove Move;
    Move.FighterId = TEXT("f-0-hero");
    Move.Start = SpaceAt(B.Board, TEXT("M13"));
    Move.Dest = SpaceAt(B.Board, TEXT("M20"));
    Move.Path = {Move.Dest};
    Draft.Moves.Add(Move);
    Draft.LastMove = Last;
    const FS08MoveDraftView Joined = S08MoveHighlight::BuildDraftView(B.Board, B.Fighters, Draft);
    const FS08PlateView* Dest = Joined.Find(Move.Dest.X, Move.Dest.Y);
    const FIntPoint M31 = SpaceAt(B.Board, TEXT("M31"));
    TestTrue(TEXT("draft destination kept"), Dest && Dest->Ring == ES08RingState::Destination);
    TestTrue(TEXT("last move kept in the draft"), Joined.Find(M31.X, M31.Y) && Joined.Find(M31.X, M31.Y)->Outline == ES08OutlineState::LastTo);
    TestNotEqual(TEXT("the last move changes the view hash"), Joined.Revision,
                 S08MoveHighlight::BuildDraftView(B.Board, B.Fighters, [&] {
                   FS08MoveDraftInput D = Draft;
                   D.LastMove = FS08MoveDraftInput::FLastMove();
                   return D;
                 }()).Revision);
  }

  // ---- MS-E-73: the edge arrow (viewport 1920x1080, margin 48) ----
  {
    const FVector2D Vp(1920.0, 1080.0);
    TestFalse(TEXT("inside: no arrow"), S09OpponentView::EdgeArrow(FVector2D(900, 500), true, Vp, 48.0f).bShow);
    TestFalse(TEXT("not projectable: no arrow"), S09OpponentView::EdgeArrow(FVector2D(5000, 500), false, Vp, 48.0f).bShow);
    const S09OpponentView::FEdgeArrow Right = S09OpponentView::EdgeArrow(FVector2D(3000, 540), true, Vp, 48.0f);
    TestTrue(TEXT("right: on the right edge, pointing right"),
             Right.bShow && FMath::IsNearlyEqual(Right.Pos.X, 1872.0, 0.5) && FMath::IsNearlyEqual(Right.Pos.Y, 540.0, 0.5) &&
                 FMath::IsNearlyEqual(Right.AngleDeg, 0.0f, 0.1f));
    const S09OpponentView::FEdgeArrow Up = S09OpponentView::EdgeArrow(FVector2D(960, -400), true, Vp, 48.0f);
    TestTrue(TEXT("above: on the top edge, pointing up"),
             Up.bShow && FMath::IsNearlyEqual(Up.Pos.Y, 48.0, 0.5) && FMath::IsNearlyEqual(Up.AngleDeg, -90.0f, 0.1f));
    const S09OpponentView::FEdgeArrow Corner = S09OpponentView::EdgeArrow(FVector2D(-2000, 2000), true, Vp, 48.0f);
    TestTrue(TEXT("down-left: inside the inset rectangle"),
             Corner.bShow && Corner.Pos.X >= 47.5 && Corner.Pos.X <= 1872.5 && Corner.Pos.Y >= 47.5 && Corner.Pos.Y <= 1032.5);
  }

  // ---- -BenchMoveDraft "lastMovement": the trail of the bench seq, no draft (MS-AT-30 scenes 3 / 5) ----
  {
    S09MoveDraftBench::FFixture Fixture;
    TArray<FString> Errors;
    const FString Doc = TEXT("{\"schema\":\"unmatched.move-draft/1\",\"lastMovement\":{\"moves\":[")
                        TEXT("{\"fighterId\":\"f-1-hero\",\"from\":\"M22\",\"path\":[\"M30\",\"M31\"]},")
                        TEXT("{\"fighterId\":\"f-1-sk0\",\"from\":\"M24\",\"path\":[\"M23\"]}]}}");
    TestTrue(TEXT("lastMovement fixture parses: ") + FString::Join(Errors, TEXT(" | ")),
             S09MoveDraftBench::Parse(Doc, TEXT("last.json"), Fixture, Errors) && Fixture.IsTrailOnly());
    FS09CommandUi Ui;
    const S09MoveDraftBench::FApplyResult R = S09MoveDraftBench::Apply(Fixture, B.Snapshot, B.Board, B.Fighters, Me, Ui);
    TestTrue(TEXT("applies: ") + R.Error, R.bOk && R.bTrail);
    TestTrue(TEXT("no draft opened"), Ui.Mode == ES09CommandMode::None);
    FS09LastMovement Synth;
    TestTrue(TEXT("lastMovement of the bench seq, by the movers' owner"),
             FS09LastMovement::Read(R.Snapshot.Metadata, Synth) && Synth.Seq == B.Snapshot.SequenceNumber &&
                 Synth.PlayerId == Opp && Synth.Moves.Num() == 2 && Synth.Source == TEXT("MANEUVER"));
    FS09LastMoveTracker T;
    T.OnApplied(R.Snapshot.SequenceNumber, Synth, FS09BoardStamp::Make(B.Fighters, Opp), 0.0, false);
    T.Tick(0.0, false);
    TestTrue(TEXT("restored without an animation"), T.IsDrawn() && T.WasRestored());
    S09MoveDraftBench::FFixture Wrong;
    Errors.Reset();
    S09MoveDraftBench::Parse(TEXT("{\"schema\":\"unmatched.move-draft/1\",\"lastMovement\":{\"moves\":[")
                                 TEXT("{\"fighterId\":\"f-1-hero\",\"from\":\"M22\",\"path\":[\"M30\"]}]}}"),
                             TEXT("wrong.json"), Wrong, Errors);
    FS09CommandUi Ui2;
    const S09MoveDraftBench::FApplyResult W = S09MoveDraftBench::Apply(Wrong, B.Snapshot, B.Board, B.Fighters, Me, Ui2);
    TestFalse(TEXT("a trail that does not end on the fighter's space is refused"), W.bOk);
    TestTrue(TEXT("its reason names the spaces"), W.Error.Contains(TEXT("M30")) && W.Error.Contains(TEXT("M31")));
    Errors.Reset();
    S09MoveDraftBench::FFixture Ghost;
    S09MoveDraftBench::Parse(TEXT("{\"schema\":\"unmatched.move-draft/1\",\"lastMovement\":{\"moves\":[")
                                 TEXT("{\"fighterId\":\"f-9-ghost\",\"from\":\"M22\",\"path\":[\"M30\"]}]}}"),
                             TEXT("ghost.json"), Ghost, Errors);
    FS09CommandUi Ui3;
    TestEqual(TEXT("an unknown fighter is a mismatch"),
              S09MoveDraftBench::Apply(Ghost, B.Snapshot, B.Board, B.Fighters, Me, Ui3).MismatchId, FString(TEXT("f-9-ghost")));
  }
  return true;
}
