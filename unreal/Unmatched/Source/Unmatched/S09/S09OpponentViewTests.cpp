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
#include "S09TurnStatus.h"
#include "../S08/S08BoardModel.h"
#include "../S08/S08Contracts.h"
#include "../S08/S08MoveHighlight.h"
#include "../S08/Fx/S08FieldFx.h"
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
  // VS-6 FX-14 (ВР-29): by default the last move is the dashed path + arrow (FS08MoveDraftView::LastPaths)
  {
    S08FieldFx::SetLegacyOverrideForTest(0);
    const FS08MoveDraftInput::FLastMove Last = S09OpponentView::LastMoveInput(Trail10, ES08PlateColor::TeamP2);
    TestEqual(TEXT("FX-14: one path per move (start + cells)"), Last.Paths.Num(), Trail10.Moves.Num());
    FS08MoveDraftInput Input;
    Input.LastMove = Last;
    const FS08MoveDraftView View = S08MoveHighlight::BuildDraftView(B.Board, B.Fighters, Input);
    TestEqual(TEXT("FX-14: the dashed paths"), View.LastPaths.Num(), Trail10.Moves.Num());
    const FIntPoint M31 = SpaceAt(B.Board, TEXT("M31"));
    TestTrue(TEXT("FX-14: no MS-T-17 outline by default"),
             !View.Find(M31.X, M31.Y) || View.Find(M31.X, M31.Y)->Outline == ES08OutlineState::None);
  }
  // the MS-T-17 contour stays the rollback (-S08LastMoveLegacy)
  S08FieldFx::SetLegacyOverrideForTest(S08FieldFx::LastMove);
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
  S08FieldFx::ResetLegacyOverrideForTest();

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

// DE-022 automation (W-13; move-selection 03 §7 "Дополнение по живым данным DE" п. 1-3, MS-R-77; 01 F-12;
// 02-ux-ui-spec SD-31; MS-AT-26 cases of DE-022): Unmatched.S09.MoveSel.OpponentStatus - the opponent's verb from the
// server state, the "what to do now" line in every state of a turn, the action tracker by the snapshot (the
// opponent's only in their turn, 150 ms in, hidden in one apply), the source card and "your fighter" of an
// opponent's effect moving my fighter, the effect lines of the feed. Board: the real Marmoreal bench game state.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09MoveSelOpponentStatusTest, "Unmatched.S09.MoveSel.OpponentStatus",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09MoveSelOpponentStatusTest::RunTest(const FString&) {
  using namespace S09OppTest;
  FBench B;
  if (!TestTrue(TEXT("Marmoreal bench state"), LoadBench(TEXT("S08BenchMarmoreal.json"), B))) return false;
  const FString Me = B.ViewerId;
  const FS08BoardFighter* Arthur = B.Fighters.FindByPredicate([](const FS08BoardFighter& F) { return F.Id == TEXT("f-1-hero"); });
  if (!TestNotNull(TEXT("King Arthur in the bench state"), Arthur)) return false;
  const FString Opp = Arthur->OwnerId;
  auto LabelOf = [&](const FString& Id) {
    const FS08BoardFighter* F = B.Fighters.FindByPredicate([&Id](const FS08BoardFighter& X) { return X.Id == Id; });
    return F ? (F->Label.IsEmpty() ? F->Name : F->Label) : Id;
  };
  auto With = [&](const FString& TurnPlayer, const FString& MetaJson, const TCHAR* Phase = TEXT("ACTION_MANEUVER")) {
    FS08Snapshot S = B.Snapshot;
    S.CurrentTurnPlayerId = TurnPlayer;
    S.Phase = Phase;
    S.Metadata = Json(MetaJson);
    return S;
  };
  auto CombatJson = [](const FString& Attacker, const FString& Defender, const FString& Target) {
    return FString::Printf(TEXT("\"combatInfo\":{\"attackerId\":\"%s\",\"defenderId\":\"%s\",\"targetFighterId\":\"%s\",")
                               TEXT("\"attackerCardId\":\"\",\"defenderCardId\":\"\",\"cardBoostCardId\":\"\",\"abilityBoostCardId\":\"\"}"),
                           *Attacker, *Defender, *Target);
  };

  // ---- 03 §7 п. 1: the verb from the server state, never a client guess ----
  {
    using S09OpponentView::OpponentVerb;
    TestTrue(TEXT("the opponent's turn, nothing open: Turn"),
             OpponentVerb(With(Opp, TEXT("{\"actionsRemaining\":2}")), Me) == ES09OpponentVerb::Turn);
    TestTrue(TEXT("my turn, nothing open: None"),
             OpponentVerb(With(Me, TEXT("{\"actionsRemaining\":2}")), Me) == ES09OpponentVerb::None);
    TestTrue(TEXT("the opponent's pendingManeuver: Maneuver"),
             OpponentVerb(With(Opp, FString::Printf(TEXT("{\"pendingManeuver\":{\"id\":\"m:1\",\"playerId\":\"%s\"}}"), *Opp)), Me) ==
                 ES09OpponentVerb::Maneuver);
    TestTrue(TEXT("my own pendingManeuver: None"),
             OpponentVerb(With(Me, FString::Printf(TEXT("{\"pendingManeuver\":{\"id\":\"m:1\",\"playerId\":\"%s\"}}"), *Me)), Me) ==
                 ES09OpponentVerb::None);
    TestTrue(TEXT("combat, I defend: the opponent attacks"),
             OpponentVerb(With(Opp, TEXT("{") + CombatJson(TEXT("f-1-hero"), Me, TEXT("f-0-hero")) + TEXT("}"), TEXT("COMBAT")), Me) ==
                 ES09OpponentVerb::Attack);
    TestTrue(TEXT("combat, they defend: Defend"),
             OpponentVerb(With(Me, TEXT("{") + CombatJson(TEXT("f-0-hero"), Opp, TEXT("f-1-hero")) + TEXT("}"), TEXT("COMBAT")), Me) ==
                 ES09OpponentVerb::Defend);
    auto Head = [&](const FString& Owner, const TCHAR* Type, const FString& Extra) {
      return FString::Printf(
          TEXT("{%s\"pendingEffects\":[{\"id\":\"e-p0\",\"playerId\":\"%s\",\"type\":\"%s\",\"text\":\"Move up to 2 spaces.\"}]}"), *Extra,
          *Owner, Type);
    };
    TestTrue(TEXT("their MOVE choice: Ability"), OpponentVerb(With(Opp, Head(Opp, TEXT("MOVE"), FString())), Me) == ES09OpponentVerb::Ability);
    TestTrue(TEXT("their BOOST_CHOICE in combat: Card (the head wins over the combat)"),
             OpponentVerb(With(Me, Head(Opp, TEXT("BOOST_CHOICE"), CombatJson(TEXT("f-0-hero"), Opp, TEXT("f-1-hero")) + TEXT(",")),
                               TEXT("COMBAT_RESOLVE")),
                          Me) == ES09OpponentVerb::Card);
    TestTrue(TEXT("my choice in their turn: None (they wait on me)"),
             OpponentVerb(With(Opp, Head(Me, TEXT("MOVE"), FString())), Me) == ES09OpponentVerb::None);
    TestTrue(TEXT("their hand-limit discard: Card"),
             OpponentVerb(With(Opp, FString::Printf(TEXT("{\"pendingHandDiscard\":{\"id\":\"d:1\",\"playerId\":\"%s\",\"count\":1}}"), *Opp)),
                          Me) == ES09OpponentVerb::Card);
    TestTrue(TEXT("GAME_OVER: None"), OpponentVerb(With(Opp, TEXT("{}"), TEXT("GAME_OVER")), Me) == ES09OpponentVerb::None);
    TestTrue(TEXT("no viewer: None"), OpponentVerb(With(Opp, TEXT("{}")), FString()) == ES09OpponentVerb::None);
    TestEqual(TEXT("Maneuver reads ms.opp.planning"), S09OpponentView::VerbKey(ES09OpponentVerb::Maneuver), FName(TEXT("ms.opp.planning")));
    TestEqual(TEXT("ms.opp.phase.attack EN"), S08WhyText::En(S09OpponentView::VerbKey(ES09OpponentVerb::Attack)),
              FString(TEXT("Opponent is attacking")));
    for (ES09OpponentVerb V : {ES09OpponentVerb::Turn, ES09OpponentVerb::Maneuver, ES09OpponentVerb::Attack, ES09OpponentVerb::Defend,
                               ES09OpponentVerb::Card, ES09OpponentVerb::Ability}) {
      TestTrue(FString::Printf(TEXT("%s has an EN line"), S09OpponentView::VerbName(V)), S08WhyText::Has(S09OpponentView::VerbKey(V)));
    }
  }

  // ---- 02 SD-31: one "what to do now" line in every state of a turn ----
  {
    auto Line = [](const FS09TurnStatusInput& In) { return S09TurnStatus::Text(In); };
    FS09TurnStatusInput Mine;
    Mine.bViewerTurn = true;
    Mine.ActionsRemaining = 2;
    TestEqual(TEXT("S0: choose an action"), Line(Mine), FString(TEXT("Choose an action: maneuver (M), attack (A) or scheme (G)")));
    FS09TurnStatusInput Done = Mine;
    Done.ActionsRemaining = 0;
    TestEqual(TEXT("no actions: end the turn"), Line(Done), FString(TEXT("No actions left: end your turn (E)")));
    FS09TurnStatusInput Busy = Mine;
    Busy.bSyncing = true;
    TestEqual(TEXT("in flight: syncing"), Line(Busy), FString(TEXT("Syncing…")));
    FS09TurnStatusInput Draft = Mine;
    Draft.Mode = ES09CommandMode::ManeuverDraft;
    TestEqual(TEXT("S1 no fighter: choose a fighter"), Line(Draft), FString(TEXT("Choose a fighter to move")));
    Draft.SelectedFighterName = TEXT("Medusa");
    TestEqual(TEXT("S1 fighter picked: choose a space"), Line(Draft), FString(TEXT("Choose a space for Medusa; Enter confirms the maneuver")));
    FS09TurnStatusInput Attack = Mine;
    Attack.Mode = ES09CommandMode::AttackDraft;
    TestEqual(TEXT("S2: attacker"), Line(Attack), FString(TEXT("Choose the attacking fighter")));
    Attack.AttackerName = TEXT("Medusa");
    TestEqual(TEXT("S2: target"), Line(Attack), FString(TEXT("Choose a target for Medusa")));
    Attack.TargetName = TEXT("King Arthur");
    TestEqual(TEXT("S2: card"), Line(Attack), FString(TEXT("Choose an attack card against King Arthur (1–9)")));
    Attack.bAttackCard = true;
    TestEqual(TEXT("S2: attack"), Line(Attack), FString(TEXT("Attack King Arthur (Enter)")));
    Attack.bAbilityPrompt = true;
    TestEqual(TEXT("the ability prompt"), Line(Attack), FString(TEXT("Medusa: add a BOOST to this attack?")));
    FS09TurnStatusInput Scheme = Mine;
    Scheme.Mode = ES09CommandMode::SchemeChoice;
    TestEqual(TEXT("scheme picker"), Line(Scheme), FString(TEXT("Choose a scheme card and play it (Enter)")));
    FS09TurnStatusInput Defend;
    Defend.Mode = ES09CommandMode::CombatDefense;
    Defend.OpponentVerb = ES09OpponentVerb::Attack;
    TestEqual(TEXT("I defend"), Line(Defend), FString(TEXT("You are attacked: choose a defense card or No defense (N)")));
    FS09TurnStatusInput Resolve = Mine;
    Resolve.Mode = ES09CommandMode::CombatResolve;
    TestEqual(TEXT("resolve window"), Line(Resolve), FString(TEXT("Resolve the combat (R)")));
    Resolve.bOpponentChoice = true;
    TestEqual(TEXT("resolve blocked by their choice"), Line(Resolve), FString(TEXT("Waiting for the opponent's choice")));
    FS09TurnStatusInput Waiting = Mine;
    Waiting.bCombatAttacking = true;
    TestEqual(TEXT("I attack, the defender has the window"), Line(Waiting), FString(TEXT("Waiting for the defender")));
    FS09TurnStatusInput Pending;
    Pending.Mode = ES09CommandMode::PendingChoice;
    Pending.PendingPrompt = FS09Reason::Make(TEXT("ms.choice.target")).Arg(TEXT("n"), 2);
    TestEqual(TEXT("my choice in their turn: its own prompt"), Line(Pending), FString(TEXT("Choose a target (up to 2)")));
    Pending.PendingPrompt.Reset();
    TestEqual(TEXT("a choice without a prompt: choose what to move"), Line(Pending), FString(TEXT("Choose what to move")));
    FS09TurnStatusInput Discard;
    Discard.Mode = ES09CommandMode::DiscardDraft;
    Discard.DiscardNeed = 2;
    TestEqual(TEXT("hand limit: discard 2"), Line(Discard), FString(TEXT("Hand over the limit: discard 2")));
    Discard.DiscardChosen = 2;
    TestEqual(TEXT("hand limit picked: confirm"), Line(Discard), FString(TEXT("Confirm (Enter)")));
    FS09TurnStatusInput Theirs;
    Theirs.OpponentVerb = ES09OpponentVerb::Attack;
    Theirs.OpponentName = TEXT("King Arthur");
    TestEqual(TEXT("their turn: <name> - <verb>"), Line(Theirs), FString(TEXT("King Arthur — Opponent is attacking")));
    Theirs.OpponentVerb = ES09OpponentVerb::Turn;
    Theirs.OpponentName.Reset();
    TestEqual(TEXT("their turn, no hero name"), Line(Theirs), FString(TEXT("Opponent — Opponent is choosing an action")));
    FS09TurnStatusInput TheirChoice = Mine;
    TheirChoice.bOpponentChoice = true;
    TestEqual(TEXT("their choice in my turn"), Line(TheirChoice), FString(TEXT("Waiting for the opponent's choice")));
    FS09TurnStatusInput Over = Mine;
    Over.bGameOver = true;
    TestEqual(TEXT("game over: no line"), Line(Over), FString());
    // every input mode in my turn and in theirs (with a verb - the server state always gives one) has a line by a
    // known key; the input carries no animation state at all, so the line never empties while a figure moves
    // (CUE-007 blocks_input: no)
    for (ES09CommandMode Mode : {ES09CommandMode::None, ES09CommandMode::ManeuverDraft, ES09CommandMode::DiscardDraft,
                                 ES09CommandMode::AttackDraft, ES09CommandMode::CombatDefense, ES09CommandMode::CombatResolve,
                                 ES09CommandMode::PendingChoice, ES09CommandMode::SchemeChoice}) {
      for (const bool bMine : {true, false}) {
        FS09TurnStatusInput In;
        In.Mode = Mode;
        In.bViewerTurn = bMine;
        In.ActionsRemaining = 1;
        In.DiscardNeed = 1;
        In.OpponentVerb = bMine ? ES09OpponentVerb::None : ES09OpponentVerb::Turn;
        const FS09Reason R = S09TurnStatus::Line(In);
        TestTrue(FString::Printf(TEXT("mode %d %s: a line by a known key (%s)"), static_cast<int32>(Mode),
                                 bMine ? TEXT("mine") : TEXT("theirs"), *R.Key.ToString()),
                 R.IsSet() && S08WhyText::Has(R.Key));
      }
    }
  }

  // ---- 01 F-12: the tracker by the snapshot - own always, the opponent's only in their turn ----
  {
    FS09ActionTracker T;
    FString L = T.OnApplied(30, Me, 3, 2, Me, 0.0);
    TestEqual(TEXT("my turn opens: own 0/2, theirs hidden"), L, FString(TEXT("MS-TRACK own=0/2 opp=0/2 oppVisible=0 seq=30")));
    TestFalse(TEXT("their tracker hidden in my turn"), T.OpponentVisible());
    TestEqual(TEXT("hidden alpha"), T.OpponentAlpha(0.0, false), 0.0f);
    T.OnApplied(31, Me, 3, 1, Me, 10.0);  // beginManeuver spends the action
    TestTrue(TEXT("marked at the choice: own 1/2"), T.Own() == FS09ActionTracker::FSlots{2, 1});
    TestEqual(TEXT("a merge without metadata keeps the marks, no trace"), T.OnApplied(31, Me, 3, -1, Me, 20.0), FString());
    T.OnApplied(32, Opp, 4, 2, Me, 1000.0);  // the turn passes
    TestTrue(TEXT("own reset in the same apply: 0/2"), T.Own() == FS09ActionTracker::FSlots{2, 0});
    TestTrue(TEXT("theirs visible: 0/2"), T.OpponentVisible() && T.Opponent() == FS09ActionTracker::FSlots{2, 0});
    TestEqual(TEXT("appears from 0"), T.OpponentAlpha(1000.0, false), 0.0f);
    TestTrue(TEXT("half in at 75 ms"), FMath::IsNearlyEqual(T.OpponentAlpha(1075.0, false), 0.5f, 1e-3f));
    TestEqual(TEXT("fully in at 150 ms"), T.OpponentAlpha(1150.0, false), 1.0f);
    TestEqual(TEXT("reduced motion: at once"), T.OpponentAlpha(1000.0, true), 1.0f);
    T.OnApplied(33, Opp, 4, 1, Me, 1200.0);
    TestTrue(TEXT("their action marked: 1/2"), T.Opponent() == FS09ActionTracker::FSlots{2, 1});
    TestEqual(TEXT("the appear clock does not restart within their turn"), T.OpponentAlpha(1200.0, false), 1.0f);
    T.OnApplied(34, Opp, 4, 2, Me, 1300.0);  // a gained action
    TestTrue(TEXT("a gained action adds a slot: 1/3"), T.Opponent() == FS09ActionTracker::FSlots{3, 1});
    L = T.OnApplied(35, Me, 5, 2, Me, 1400.0);
    TestTrue(TEXT("my turn: theirs hidden in this apply (one frame)"), !T.OpponentVisible() && T.OpponentAlpha(1400.0, false) == 0.0f);
    TestTrue(TEXT("traced"), L.Contains(TEXT("oppVisible=0")) && L.Contains(TEXT("seq=35")));
    FS09ActionTracker Rejoin;
    Rejoin.OnApplied(40, Opp, 6, 1, Me, 0.0);
    TestTrue(TEXT("a reconnect mid-turn sees 2 - actionsRemaining spent"), Rejoin.Opponent() == FS09ActionTracker::FSlots{2, 1});
  }

  // ---- run I (AB-7, the DE tracker): the type of a spent action, from the spending snapshot ----
  {
    using S09OpponentView::SpentActionType;
    const FString Maneuver = FString::Printf(TEXT("{\"actionsRemaining\":1,\"pendingManeuver\":{\"id\":\"m:1\",\"playerId\":\"%s\"}}"), *Opp);
    TestEqual(TEXT("an open pendingManeuver: maneuver"), SpentActionType(With(Opp, Maneuver)), FName(TEXT("maneuver")));
    FS08Snapshot Done = With(Opp, FString::Printf(TEXT("{\"actionsRemaining\":1,\"lastMovement\":{\"seq\":%d,\"playerId\":\"%s\",")
                                                      TEXT("\"source\":\"MANEUVER\",\"moves\":[]}}"), B.Snapshot.SequenceNumber, *Opp));
    TestEqual(TEXT("a MANEUVER lastMovement of this seq: maneuver"), SpentActionType(Done), FName(TEXT("maneuver")));
    FS08Snapshot Older = Done;
    Older.SequenceNumber += 1;
    TestEqual(TEXT("an older MANEUVER trail is not this action: scheme"), SpentActionType(Older), FName(TEXT("scheme")));
    TestEqual(TEXT("the open combat: attack"),
              SpentActionType(With(Opp, TEXT("{\"actionsRemaining\":1,") + CombatJson(TEXT("f-1-hero"), Me, TEXT("f-0-hero")) + TEXT("}"),
                                   TEXT("COMBAT"))),
              FName(TEXT("attack")));
    TestEqual(TEXT("a COMBAT phase alone: attack"), SpentActionType(With(Opp, TEXT("{\"actionsRemaining\":1}"), TEXT("COMBAT"))),
              FName(TEXT("attack")));
    TestEqual(TEXT("neither: the scheme"), SpentActionType(With(Opp, TEXT("{\"actionsRemaining\":1}"))), FName(TEXT("scheme")));

    FS09ActionTracker T;
    T.OnApplied(50, Opp, 7, 2, Me, 0.0, FName(TEXT("scheme")));
    TestEqual(TEXT("nothing spent: no type"), T.SpentType(0), FName(NAME_None));
    T.OnApplied(51, Opp, 7, 1, Me, 10.0, FName(TEXT("attack")));
    TestEqual(TEXT("slot 0 spent by the attack"), T.SpentType(0), FName(TEXT("attack")));
    T.OnApplied(52, Opp, 7, 1, Me, 20.0, FName(TEXT("scheme")));
    TestEqual(TEXT("no new spend: the type stays"), T.SpentType(0), FName(TEXT("attack")));
    T.OnApplied(53, Opp, 7, 0, Me, 30.0, FName(TEXT("maneuver")));
    TestTrue(TEXT("slot 1 spent by the maneuver"), T.SpentType(0) == FName(TEXT("attack")) && T.SpentType(1) == FName(TEXT("maneuver")));
    T.OnApplied(54, Me, 8, 2, Me, 40.0, FName(TEXT("scheme")));
    TestEqual(TEXT("a new turn drops the types"), T.SpentType(0), FName(NAME_None));
    FS09ActionTracker Rejoin;
    Rejoin.OnApplied(60, Opp, 9, 0, Me, 0.0, FName(TEXT("attack")));
    TestTrue(TEXT("a reconnect mid-turn types every spent slot by the snapshot"),
             Rejoin.SpentType(0) == FName(TEXT("attack")) && Rejoin.SpentType(1) == FName(TEXT("attack")));
  }

  // ---- 03 §7 п. 3: the opponent's effect moves MY fighter - source card + "your fighter"; effect lines ----
  {
    FS09EffectSources Sources;
    FS08PendingEffect Pending;
    Pending.Id = TEXT("fx-1-p0");
    Pending.PlayerId = Opp;
    Pending.Type = TEXT("MOVE");
    Pending.Text = TEXT("move up to 2 spaces");
    Sources.Note({Pending});
    TestEqual(TEXT("the pending text is kept by its id"), Sources.TextOf(TEXT("fx-1-p0")), Pending.Text);
    TestEqual(TEXT("an unseen id: no text"), Sources.TextOf(TEXT("fx-9")), FString());
    auto Card = [](const TCHAR* Name, const TCHAR* Text, bool bHidden) {
      FS09CardView C;
      C.Name = Name;
      C.Text = Text;
      C.bHidden = bHidden;
      return C;
    };
    const TArray<FS09CardView> Pile = {Card(TEXT("Feint"), TEXT("After combat: Move up to 2 spaces."), false),
                                       Card(TEXT("Regroup"), TEXT(""), false), Card(TEXT(""), TEXT(""), true)};
    TestEqual(TEXT("the card whose text holds the effect"), S09OpponentView::EffectCardName(Pending.Text, Pile), FString(TEXT("Feint")));
    TestEqual(TEXT("unknown text: the newest card with text"), S09OpponentView::EffectCardName(FString(), Pile), FString(TEXT("Feint")));
    TestEqual(TEXT("nothing public: no name"), S09OpponentView::EffectCardName(Pending.Text, {Card(TEXT(""), TEXT(""), true)}), FString());

    FS09LastMovement Effect;
    FS09LastMovement::Read(TrailMeta(B.Board, 22, Opp, TEXT("EFFECT"), TEXT("null"), {TEXT("f-0-hero:M13>M20"), TEXT("f-1-sk0:M24>M23")}),
                           Effect);
    auto OwnerOf = [&](const FString& Id) {
      const FS08BoardFighter* F = B.Fighters.FindByPredicate([&Id](const FS08BoardFighter& X) { return X.Id == Id; });
      return F ? F->OwnerId : FString();
    };
    const TArray<FString> Yours = S09OpponentView::YourFightersMoved(Effect, Me, OwnerOf);
    TestTrue(TEXT("their effect moved my hero only"), Yours.Num() == 1 && Yours[0] == TEXT("f-0-hero"));
    TestEqual(TEXT("for its owner nothing is 'yours'"), S09OpponentView::YourFightersMoved(Effect, Opp, OwnerOf).Num(), 0);
    FS09LastMovement Maneuver = Effect;
    Maneuver.Source = TEXT("MANEUVER");
    TestEqual(TEXT("a maneuver is not an effect"), S09OpponentView::YourFightersMoved(Maneuver, Me, OwnerOf).Num(), 0);
    TestEqual(TEXT("sourceRef read"), Effect.SourceRef, FString(TEXT("maneuver:1")));

    auto PlayerName = [&](const FString& Id) { return Id == Opp ? FString(TEXT("King Arthur")) : FString(TEXT("Medusa")); };
    auto FighterName = [&](const FString& Id) { return LabelOf(Id); };
    auto CellName = [&](const FIntPoint& C) { return B.Board.CellLabel(C.X, C.Y); };
    const FS09FeedEntry YoursLine = FS09EventFeed::DescribeEffect(Effect, TEXT("Feint"), Yours, PlayerName, FighterName, CellName);
    TestEqual(TEXT("ms.opp.moves.yours"), YoursLine.Text,
              FString::Printf(TEXT("Your fighter %s: Feint effect"), *LabelOf(TEXT("f-0-hero"))));
    const FS09FeedEntry Plain = FS09EventFeed::DescribeEffect(Effect, FString(), {}, PlayerName, FighterName, CellName);
    TestTrue(TEXT("ms.log.effect with an unknown card: ") + Plain.Text,
             Plain.Text.StartsWith(TEXT("King Arthur: ? effect: ")) && Plain.Text.Contains(TEXT("M24→M23")));
    FS09EventFeed Feed;
    TestFalse(TEXT("Add stays maneuver-only"), Feed.Add(Effect, PlayerName, FighterName, CellName));
    TestTrue(TEXT("AddEffect writes it"), Feed.AddEffect(Effect, TEXT("Feint"), Yours, PlayerName, FighterName, CellName));
    TestFalse(TEXT("once per seq"), Feed.AddEffect(Effect, TEXT("Feint"), Yours, PlayerName, FighterName, CellName));
    TestFalse(TEXT("AddEffect refuses a maneuver"), Feed.AddEffect(Maneuver, TEXT("Feint"), {}, PlayerName, FighterName, CellName));
    TestEqual(TEXT("the line is the callout's"), Feed.GetLines().Last().Text, YoursLine.Text);
  }
  return true;
}
