// MS-T-08 automation (docs/game-design/move-selection 06 §2): the moveSelection profile blocks (MS-AT-34, parse part),
// the channel priorities of the plate view (03 §4.2a), the plate ISMs on a real board (MS-AT-21) and the
// -BenchMoveDraft scene fixtures (06 §6.2). Boards: the real Marmoreal / Sarpedon bench game states only.
#include "Misc/AutomationTest.h"

#include "S08BoardActor.h"
#include "S08BoardArt.h"
#include "S08BoardModel.h"
#include "S08Contracts.h"
#include "S08MoveHighlight.h"
#include "S08Team.h"
#include "../S09/S09ManeuverUi.h"
#include "../S09/S09MoveDraftView.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "HAL/FileManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

namespace S08MoveHLTest {
/** A Config/Bench game state (the -Bench fixture): snapshot, board, fighters, viewer. */
struct FBench {
  FS08Snapshot Snapshot;
  FS08BoardModel Board;
  TArray<FS08BoardFighter> Fighters;
  FString ViewerId;
  FString BoardId;
};

bool LoadBench(const TCHAR* File, FBench& Out) {
  FString Text;
  if (!FFileHelper::LoadFileToString(Text, *FPaths::Combine(FPaths::ProjectConfigDir(), TEXT("Bench"), File))) return false;
  TSharedPtr<FJsonObject> Root;
  FString Problem;
  if (!FS08Contracts::TryParseJsonObject(Text, Root, Problem) || !Root.IsValid()) return false;
  Root->TryGetStringField(TEXT("benchViewerId"), Out.ViewerId);
  Root->TryGetStringField(TEXT("benchBoardId"), Out.BoardId);
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

const FS08BoardFighter* FighterById(const TArray<FS08BoardFighter>& Fighters, const TCHAR* Id) {
  return Fighters.FindByPredicate([Id](const FS08BoardFighter& F) { return F.Id == Id; });
}

FString MoveDraftDir() {
  return FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectDir(), TEXT("../../tools/s08/fixtures/move-draft")));
}

/** Two tiles boards (a grid "grid" 3x2 and "grid2" 4x2); Root / Grid / Grid2 are JSON fragments (with a leading
 *  comma) spliced in: the root block and the board blocks. */
FString Doc(const FString& Root, const FString& Grid, const FString& Grid2) {
  return FString(TEXT("{\"schema\":\"unmatched.s08-art-board-profiles/1\",\"revision\":1")) + Root +
         TEXT(",\"lightProfiles\":{\"L\":{\"directional\":{\"name\":\"key\",\"posUU\":[0,0,600],\"rotation\":[-50,-90,0],"
              "\"intensity\":3,\"castShadows\":true},\"points\":[{\"name\":\"p\",\"at\":[0.5,-0.5,200],\"intensity\":50,"
              "\"radiusUU\":300,\"colorLinear\":[1,0.5,0.25]}]}},"
              "\"boards\":[{\"id\":\"grid\",\"match\":{\"boardIds\":[\"cidGrid\"],\"width\":3,\"height\":2},"
              "\"surface\":\"tiles\",\"light\":\"L\"") +
         Grid +
         TEXT("},{\"id\":\"grid2\",\"match\":{\"boardIds\":[\"cidGrid2\"],\"width\":4,\"height\":2},"
              "\"surface\":\"tiles\",\"light\":\"L\"") +
         Grid2 + TEXT("}]}");
}

const FS08BoardArtProfile* Profile(const FS08BoardArtData& Data, const TCHAR* Id) {
  return Data.Boards.FindByPredicate([Id](const FS08BoardArtProfile& B) { return B.Id == Id; });
}
}  // namespace S08MoveHLTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08MoveHLProfileTest,
    "Unmatched.S08.MoveHL.Profile moveSelection: code defaults without blocks, root defaults, board override on any surface, geometry and unknown fields refused",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08MoveHLProfileTest::RunTest(const FString&) {
  using namespace S08MoveHLTest;
  const FS08MoveSelectionSpec Code;
  // 1) no block at all: the code defaults (04 §4.7) on the root and on every board
  {
    FS08BoardArtData Data;
    TArray<FString> Errors;
    TestTrue(TEXT("doc without blocks parses: ") + FString::Join(Errors, TEXT(" | ")),
             Data.ParseJson(Doc(FString(), FString(), FString()), Errors));
    TestEqual("root source code", Data.MoveSelection.Source, FString(TEXT("code")));
    const FS08BoardArtProfile* Grid = Profile(Data, TEXT("grid"));
    if (TestNotNull("grid profile", Grid)) {
      TestTrue("grid: code plate colour #F2E9D8", Grid->MoveSelection.PlateColor == FColor(0xF2, 0xE9, 0xD8, 255));
      TestEqual("grid: ring centre 36", Grid->MoveSelection.RingCenterUU, 36.0f);
      TestEqual("grid: hop height 0 (D-DE-02)", Grid->MoveSelection.HopHeightRel, 0.0f);
      TestEqual("grid: source code", Grid->MoveSelection.Source, FString(TEXT("code")));
    }
    TestTrue("code defaults pass the geometry", S08MoveHighlight::CheckGeometry(Code).Ok());
  }
  // 2) root block + an override on a GRID (any surface, MS-R-50): the board wins, the other board takes the root
  {
    FS08BoardArtData Data;
    TArray<FString> Errors;
    const bool bOk = Data.ParseJson(
        Doc(TEXT(",\"moveSelection\":{\"plate\":{\"colorSrgb\":\"#4CD2DC\",\"fillAlpha\":0.15},\"anim\":{\"stepMs\":300}}"),
            TEXT(",\"moveSelection\":{\"plate\":{\"colorSrgb\":\"#FFC857\"},\"path\":{\"colorSrgb\":\"#FFC857\"}}"),
            FString()),
        Errors);
    TestTrue(TEXT("grid with moveSelection is not refused: ") + FString::Join(Errors, TEXT(" | ")), bOk);
    TestEqual("root source", Data.MoveSelection.Source, FString(TEXT("root")));
    const FS08BoardArtProfile* Grid = Profile(Data, TEXT("grid"));
    const FS08BoardArtProfile* Grid2 = Profile(Data, TEXT("grid2"));
    if (TestNotNull("grid", Grid) && TestNotNull("grid2", Grid2)) {
      TestTrue("override wins: plate #FFC857", Grid->MoveSelection.PlateColor == FColor(0xFF, 0xC8, 0x57, 255));
      TestTrue("override: path #FFC857", Grid->MoveSelection.PathColor == FColor(0xFF, 0xC8, 0x57, 255));
      TestEqual("override keeps the root fill 0.15", Grid->MoveSelection.FillAlpha, 0.15f);
      TestEqual("override keeps the root stepMs 300", Grid->MoveSelection.StepMs, 300);
      TestEqual("override source board", Grid->MoveSelection.Source, FString(TEXT("board")));
      TestTrue("other board: the root colour #4CD2DC", Grid2->MoveSelection.PlateColor == FColor(0x4C, 0xD2, 0xDC, 255));
      TestEqual("other board: source root", Grid2->MoveSelection.Source, FString(TEXT("root")));
    }
  }
  // 3) refusals (the document is rejected, never a silent default)
  struct FBad {
    const TCHAR* Block;
    const TCHAR* Needle;
  };
  const FBad Bad[] = {
      {TEXT(",\"moveSelection\":{\"plate\":{\"ringWidthUU\":8}}"), TEXT("[30, 40]")},
      {TEXT(",\"moveSelection\":{\"plate\":{\"outlineOuterUU\":42}}"), TEXT("rim 41.6")},
      {TEXT(",\"moveSelection\":{\"plate\":{\"colour\":\"#FFFFFF\"}}"), TEXT("not a known field")},
      {TEXT(",\"moveSelection\":{\"plates\":{}}"), TEXT("not a known block")},
      {TEXT(",\"moveSelection\":{\"boostTier\":{\"dashCount\":12.5}}"), TEXT("whole number")},
      {TEXT(",\"moveSelection\":{\"anim\":{\"easeEnds\":\"yes\"}}"), TEXT("true|false")},
      {TEXT(",\"moveSelection\":{\"plate\":{\"fillAlpha\":0.5}}"), TEXT("fillAlpha")},
  };
  for (const FBad& B : Bad) {
    FS08BoardArtData Data;
    TArray<FString> Errors;
    TestFalse(FString::Printf(TEXT("refused: %s"), B.Block), Data.ParseJson(Doc(FString(), B.Block, FString()), Errors));
    TestTrue(FString::Printf(TEXT("error names it (%s): %s"), B.Needle, *FString::Join(Errors, TEXT(" | "))),
             Errors.ContainsByPredicate([&B](const FString& E) { return E.Contains(B.Needle); }));
  }
  {
    FS08BoardArtData Data;
    TArray<FString> Errors;
    TestFalse("a broken ROOT block refuses the document",
              Data.ParseJson(Doc(TEXT(",\"moveSelection\":{\"plate\":{\"keylineUU\":3}}"), FString(), FString()), Errors));
  }
  // 4) the shipped document: root = the code numbers, the two maps #FFC857 (03 §4.2b)
  FS08BoardArtData Shipped;
  TArray<FString> Errors;
  if (TestTrue(TEXT("shipped profiles: ") + FString::Join(Errors, TEXT(" | ")),
               Shipped.LoadFile(FS08BoardArtData::DefaultPath(), Errors))) {
    TestEqual("shipped root source", Shipped.MoveSelection.Source, FString(TEXT("root")));
    TestTrue("shipped root plate = code", Shipped.MoveSelection.PlateColor == Code.PlateColor);
    TestEqual("shipped root ring = code", Shipped.MoveSelection.RingCenterUU, Code.RingCenterUU);
    for (const TCHAR* Id : {TEXT("marmoreal-original"), TEXT("sarpedon-original")}) {
      const FS08BoardArtProfile* P = Profile(Shipped, Id);
      if (!TestNotNull(Id, P)) continue;
      TestTrue(FString::Printf(TEXT("%s plate #FFC857"), Id), P->MoveSelection.PlateColor == FColor(0xFF, 0xC8, 0x57, 255));
      TestTrue(FString::Printf(TEXT("%s path #FFC857"), Id), P->MoveSelection.PathColor == FColor(0xFF, 0xC8, 0x57, 255));
      const S08MoveHighlight::FGeometryCheck G = S08MoveHighlight::CheckGeometry(P->MoveSelection);
      AddInfo(G.TraceLine(Id));
      TestTrue(FString::Printf(TEXT("%s geometry 03 §4.1"), Id), G.Ok());
    }
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08MoveHLViewTest,
    "Unmatched.S08.MoveHL.View BuildDraftView resolves one state per channel by the 03 s4-2a priorities on the real Marmoreal state",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08MoveHLViewTest::RunTest(const FString&) {
  using namespace S08MoveHLTest;
  FBench B;
  if (!TestTrue("Marmoreal bench state", LoadBench(TEXT("S08BenchMarmoreal.json"), B))) return false;
  const FIntPoint M13 = SpaceAt(B.Board, TEXT("M13")), M14 = SpaceAt(B.Board, TEXT("M14")),
                  M08 = SpaceAt(B.Board, TEXT("M08")), M15 = SpaceAt(B.Board, TEXT("M15")),
                  M02 = SpaceAt(B.Board, TEXT("M02")), M07 = SpaceAt(B.Board, TEXT("M07")),
                  M23 = SpaceAt(B.Board, TEXT("M23")), M01 = SpaceAt(B.Board, TEXT("M01"));
  FS08MoveDraftInput In;
  In.ViewerId = B.ViewerId;
  In.SelectedFighterId = TEXT("f-0-hero");
  In.SelectedStart = M13;
  In.BaseTier = {M13, M14, M08, M15};          // the own space never gets a plate
  In.BoostTier = {{M14, 2}, {M02, 3}};         // M14 in both tiers: the base tier wins
  In.MarkRange = 7;
  // a Destination over the base tier, a NeedBoost with its chip, a Conflict with a path dot through it
  FS08MoveDraftInput::FMove Dest;
  Dest.FighterId = TEXT("f-0-sk0");
  Dest.Start = M07;
  Dest.Dest = M08;
  Dest.Order = 0;
  Dest.Path = {M08};
  FS08MoveDraftInput::FMove Need = Dest;
  Need.FighterId = TEXT("f-0-hero");
  Need.Start = M13;
  Need.Dest = M15;
  Need.Order = 1;
  Need.Status = FS08MoveDraftInput::EMoveStatus::NeedBoost;
  Need.RequiredBoost = 1;
  Need.Path = {M14, M02, M15};  // M14, M02 get the centre dot (one per space)
  FS08MoveDraftInput::FMove Conf = Dest;
  Conf.FighterId = TEXT("f-0-sk2");
  Conf.Start = M01;
  Conf.Dest = M02;
  Conf.Order = 2;
  Conf.Status = FS08MoveDraftInput::EMoveStatus::Conflict;
  Conf.Path = {M02};
  In.Moves = {Dest, Need, Conf};
  In.bLeaderPips = true;
  const FS08MoveDraftView View = S08MoveHighlight::BuildDraftView(B.Board, B.Fighters, In);
  auto Ring = [&View](const FIntPoint& C) {
    const FS08PlateView* P = View.Find(C.X, C.Y);
    return P ? P->Ring : ES08RingState::None;
  };
  TestTrue("own space: no plate", Ring(M13) == ES08RingState::None);
  TestTrue("base over boost tier (M14 ReachBase)", Ring(M14) == ES08RingState::ReachBase);
  TestTrue("destination over base (M08)", Ring(M08) == ES08RingState::Destination);
  TestTrue("NeedBoost (M15)", Ring(M15) == ES08RingState::NeedBoost);
  TestTrue("conflict over boost tier (M02)", Ring(M02) == ES08RingState::Conflict);
  if (const FS08PlateView* P = View.Find(M15.X, M15.Y)) {
    TestEqual("NeedBoost chip +1", P->Chip, 1);
    TestEqual("NeedBoost order badge 2", P->Order, 2);
    TestTrue("NeedBoost glyph = order badge", P->Glyph == ES08GlyphState::Order);
  }
  if (const FS08PlateView* P = View.Find(M02.X, M02.Y)) {
    TestTrue("conflict glyph '!' beats the order badge", P->Glyph == ES08GlyphState::Conflict);
    TestTrue("conflict space also carries the path dot of the NeedBoost path", P->bPathDot);
  }
  if (const FS08PlateView* P = View.Find(M14.X, M14.Y)) TestTrue("path dot on M14", P->bPathDot);
  // allies and enemies in range (V-06 / V-07), the hero's leader pip and the occupied flag
  const FS08BoardFighter* Merlin = FighterById(B.Fighters, TEXT("f-1-sk0"));
  if (Merlin && B.Board.GraphDistance(M13, M23) <= 7) {
    TestTrue("enemy in range: EnemyBlock (Merlin M23)", Ring(M23) == ES08RingState::EnemyBlock);
    if (const FS08PlateView* P = View.Find(M23.X, M23.Y)) TestTrue("enemy space occupied", (P->Flags & S08PlateFlags::Occupied) != 0);
  }
  TestTrue("ally in range: AllyPass (Harpy M07)", Ring(M07) == ES08RingState::AllyPass);
  // determinism and hover: the same input is the same view; a hover changes it only on a space
  TestEqual("deterministic revision", S08MoveHighlight::BuildDraftView(B.Board, B.Fighters, In).Revision, View.Revision);
  FS08MoveDraftInput Hovered = In;
  Hovered.Hover = M14;
  const FS08MoveDraftView HoverView = S08MoveHighlight::BuildDraftView(B.Board, B.Fighters, Hovered);
  TestNotEqual("hover on a space changes the view", HoverView.Revision, View.Revision);
  if (const FS08PlateView* P = HoverView.Find(M14.X, M14.Y)) TestTrue("hover flag", (P->Flags & S08PlateFlags::Hover) != 0);
  // pending MOVE (V-11) never beats a draft state; candidates (V-17) are the lowest priority
  FS08MoveDraftInput Pending;
  Pending.bPending = true;
  Pending.PendingCells = {FS08BoardModel::CellKey(M14.X, M14.Y)};
  Pending.CandidateFighterIds = {TEXT("f-0-hero"), TEXT("f-0-sk0")};
  Pending.bLeaderPips = true;
  const FS08MoveDraftView PV = S08MoveHighlight::BuildDraftView(B.Board, B.Fighters, Pending);
  const FS08PlateView* PM = PV.Find(M14.X, M14.Y);
  TestTrue("pending MOVE plate", PM && PM->Ring == ES08RingState::PendingMove);
  const FS08PlateView* Hero = PV.Find(M13.X, M13.Y);
  const FS08PlateView* Harpy = PV.Find(M07.X, M07.Y);
  TestTrue("candidate under Medusa (scale 1, leader pip, occupied)",
           Hero && Hero->Ring == ES08RingState::Candidate && Hero->FigureScale == 1.0f &&
               (Hero->Flags & S08PlateFlags::LeaderPip) && (Hero->Flags & S08PlateFlags::Occupied));
  TestTrue("candidate under a Harpy at sidekick scale",
           Harpy && Harpy->Ring == ES08RingState::Candidate &&
               FMath::IsNearlyEqual(Harpy->FigureScale, S08TeamRingSpec::SidekickScale));
  // the compatibility view of a plain reachable set
  const FS08MoveDraftView Legacy = S08MoveHighlight::ViewFromReachable(
      B.Board, B.Fighters, TEXT("f-0-hero"), {FS08BoardModel::CellKey(M13.X, M13.Y), FS08BoardModel::CellKey(M14.X, M14.Y)},
      false);
  TestEqual("reach view: one plate (own space skipped)", Legacy.Plates.Num(), 1);
  TestTrue("reach view: ReachBase", Legacy.Plates.Num() == 1 && Legacy.Plates[0].Ring == ES08RingState::ReachBase);
  (void)M01;
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08MoveHLIsmStatesTest,
    "Unmatched.S08.MoveHL.IsmStates plates: one ISM instance per board space per channel, custom data = the view, no spawns on select / boost / hover (MS-AT-21)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08MoveHLIsmStatesTest::RunTest(const FString&) {
  using namespace S08MoveHLTest;
  using S08MovePlateSpec::EChannel;
  FBench B;
  if (!TestTrue("Marmoreal bench state", LoadBench(TEXT("S08BenchMarmoreal.json"), B))) return false;
  S08MoveHighlight::SetEnabledOverrideForTest(true);
  ON_SCOPE_EXIT { S08MoveHighlight::SetEnabledOverrideForTest(TOptional<bool>()); };
  UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, FName(TEXT("S08MoveHLIsm")));
  if (!TestNotNull("test world", World)) return false;
  FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
  Context.SetCurrentWorld(World);
  ON_SCOPE_EXIT {
    GEngine->DestroyWorldContext(World);
    World->DestroyWorld(false);
  };
  AS08BoardActor* Board = World->SpawnActor<AS08BoardActor>(AS08BoardActor::StaticClass(), FVector::ZeroVector, FRotator::ZeroRotator);
  if (!TestNotNull("board actor", Board)) return false;
  TestTrue("rebuild Marmoreal", Board->Rebuild(B.Board));
  Board->SyncFighters(B.Board, B.Fighters, B.ViewerId);
  const US08MoveHighlightComponent* Built = Board->GetMoveHighlight();
  TestTrue("the topology board's Rebuild builds the plates itself", Built && Built->GetBuildCount() == 1);
  const US08MoveHighlightComponent* HL = Board->EnsureMoveHighlightForTest();
  if (!TestNotNull("move highlight component", HL)) return false;
  AddInfo(FString::Printf(TEXT("plate material: %s"), HL->GetMaterialName().IsEmpty() ? TEXT("(missing - test-ready)")
                                                                                       : *HL->GetMaterialName()));
  if (HL->GetMaterialName().IsEmpty()) {
    AddWarning(TEXT("M_UM_MovePlate not found: run tools/art/move_selection/ue_move_plate_material.py (the plates are drawn without it in this test only)"));
  } else {
    TestEqual("material M_UM_MovePlate (MS-R-74)", HL->GetMaterialName(), FString(TEXT("M_UM_MovePlate")));
  }
  TestTrue("plates in use", Board->UsesMovePlates());
  int32 Spaces = 0;
  FIntPoint NonSpace(-1, -1);
  for (int32 Y = 0; Y < B.Board.Height; ++Y) {
    for (int32 X = 0; X < B.Board.Width; ++X) {
      if (B.Board.IsBoardSpace(X, Y)) {
        ++Spaces;
      } else if (NonSpace.X < 0) {
        NonSpace = FIntPoint(X, Y);
      }
    }
  }
  TestEqual("instances per channel = board spaces", HL->GetSpaceCount(), Spaces);
  for (int32 C = 0; C < static_cast<int32>(EChannel::Count); ++C) {
    const UInstancedStaticMeshComponent* Ism = HL->GetChannel(static_cast<EChannel>(C));
    TestTrue(FString::Printf(TEXT("channel %s: %d instances, 6 custom floats"), S08MovePlateSpec::ChannelName(static_cast<EChannel>(C)), Spaces),
             Ism && Ism->GetInstanceCount() == Spaces && Ism->NumCustomDataFloats == S08MovePlateSpec::NumCustomData);
  }
  if (NonSpace.X >= 0) TestEqual("no plate on a lattice cell that is not a space", HL->InstanceOf(NonSpace.X, NonSpace.Y), INDEX_NONE);
  // the draft of the real game, as the game mode feeds it (provider = S09MoveDraftView over FS09CommandUi)
  FS09CommandUi Ui;
  S09MoveDraftBench::FFixture Fixture;
  TArray<FString> Errors;
  FString Text;
  const FString File = FPaths::Combine(MoveDraftDir(), TEXT("marmoreal-1-select-boost.json"));
  if (!TestTrue(TEXT("scene fixture ") + File, FFileHelper::LoadFileToString(Text, *File) &&
                                                   S09MoveDraftBench::Parse(Text, FPaths::GetCleanFilename(File), Fixture, Errors))) {
    return false;
  }
  const S09MoveDraftBench::FApplyResult Applied = S09MoveDraftBench::Apply(Fixture, B.Snapshot, B.Board, B.Fighters, B.ViewerId, Ui);
  if (!TestTrue(TEXT("scene applied: ") + Applied.Error, Applied.bOk)) return false;
  FIntPoint Hover = Applied.Hover;
  Board->SetMoveDraftViewProvider([&](const FString&, const TSet<uint64>&, FS08MoveDraftView& Out) {
    FS08MoveDraftInput Input = S09MoveDraftView::BuildInput(Ui, B.Board, B.Fighters);
    Input.Hover = Hover;
    Input.bLeaderPips = true;
    Out = S08MoveHighlight::BuildDraftView(B.Board, B.Fighters, Input);
    return true;
  });
  auto CountActors = [World]() {
    int32 N = 0;
    for (TActorIterator<AActor> It(World); It; ++It) ++N;
    return N;
  };
  auto CountComponents = [Board]() { return Board->GetComponents().Num(); };
  Board->SetSelectedFighter(Ui.SelectedFighterId, Ui.ReachableCells);
  const int32 Actors0 = CountActors();
  const int32 Components0 = CountComponents();
  TestEqual("no highlight actors with the plates", Board->GetHighlightActorCount(), 0);
  // every channel of every instance = the view (100 %)
  auto CheckView = [&](const TCHAR* What) {
    FS08MoveDraftInput Input = S09MoveDraftView::BuildInput(Ui, B.Board, B.Fighters);
    Input.Hover = Hover;
    Input.bLeaderPips = true;
    const FS08MoveDraftView View = S08MoveHighlight::BuildDraftView(B.Board, B.Fighters, Input);
    int32 Wrong = 0, Shown = 0;
    for (int32 Y = 0; Y < B.Board.Height; ++Y) {
      for (int32 X = 0; X < B.Board.Width; ++X) {
        const int32 I = HL->InstanceOf(X, Y);
        if (I == INDEX_NONE) continue;
        const FS08PlateView* P = View.Find(X, Y);
        const ES08RingState R = P ? P->Ring : ES08RingState::None;
        const bool bRingShown = R != ES08RingState::None && !(R == ES08RingState::AllyPass && !(P->Flags & S08PlateFlags::Hover));
        Shown += bRingShown ? 1 : 0;
        if (HL->IsInstanceVisible(EChannel::Ring, I) != bRingShown) ++Wrong;
        if (bRingShown && FMath::RoundToInt(HL->GetCustomData(EChannel::Ring, I, S08MovePlateCpd::State)) != static_cast<int32>(R)) ++Wrong;
        if (bRingShown && FMath::RoundToInt(HL->GetCustomData(EChannel::Ring, I, S08MovePlateCpd::Flags)) != P->Flags) ++Wrong;
        if (bRingShown && R == ES08RingState::ReachBoost &&
            FMath::RoundToInt(HL->GetCustomData(EChannel::Ring, I, S08MovePlateCpd::Chip)) != P->Chip) {
          ++Wrong;
        }
        const ES08GlyphState G = P ? P->Glyph : ES08GlyphState::None;
        const bool bGlyph = G == ES08GlyphState::Invalid || G == ES08GlyphState::Conflict;
        if (HL->IsInstanceVisible(EChannel::Glyph, I) != bGlyph) ++Wrong;
      }
    }
    TestEqual(FString::Printf(TEXT("%s: every instance = the view (%d plates shown)"), What, Shown), Wrong, 0);
    return Shown;
  };
  const int32 ShownSelect = CheckView(TEXT("Medusa selected, +2"));
  TestTrue("Medusa's tiers are drawn", ShownSelect >= 10);
  int32 BoostChips = 0;
  for (const FIntPoint& Cell : Ui.SelectedTiers.BoostTier) {
    const int32 I = HL->InstanceOf(Cell.X, Cell.Y);
    if (I != INDEX_NONE && HL->GetCustomData(EChannel::Ring, I, S08MovePlateCpd::Chip) > 0.0f) ++BoostChips;
  }
  TestTrue(FString::Printf(TEXT("boost tier carries the +N chips (%d)"), BoostChips),
           Ui.SelectedTiers.BoostTier.Num() == 0 || BoostChips == Ui.SelectedTiers.BoostTier.Num());
  // select another fighter, change the boost, hover between the circles: no actor, no component
  TestTrue("select Harpy 1", Ui.SelectFighter(TEXT("f-0-sk0"), Applied.Snapshot, B.Board, B.Fighters));
  Board->SetSelectedFighter(Ui.SelectedFighterId, Ui.ReachableCells);
  CheckView(TEXT("Harpy 1 selected"));
  FString Reason;
  TestTrue("boost +4", Ui.ToggleBoostCard(TEXT("cmuhgvgki00sswi9gdr1ptm2z::0"), Applied.Snapshot, B.Board, B.Fighters, Reason));
  Board->RefreshMoveDraftView();
  CheckView(TEXT("boost +4"));
  Hover = FIntPoint(-1, -1);  // the cursor leaves M14
  Board->RefreshMoveDraftView();
  const uint32 HashBefore = HL->GetAppliedHash();
  // a cursor between two linked circles (M13 - M14) has no space: the hover stays "none" and the view does not change
  int32 HX = -1, HY = -1;
  const FIntPoint M13 = SpaceAt(B.Board, TEXT("M13")), M14 = SpaceAt(B.Board, TEXT("M14"));
  const FVector CA = B.Board.CellToWorld(M13.X, M13.Y), CB = B.Board.CellToWorld(M14.X, M14.Y);
  if (FVector::Dist(CA, CB) > 2.0f * B.Board.LayoutFrame.SpaceRadiusUU() + 2.0f) {
    TestFalse("between the circles: no space", Board->WorldToCell((CA + CB) * 0.5f, HX, HY));
  }
  if (Board->WorldToCell((CA + CB) * 0.5f, HX, HY)) Hover = FIntPoint(HX, HY);
  Board->RefreshMoveDraftView();
  TestEqual("hover between circles keeps the view", HL->GetAppliedHash(), HashBefore);
  TestEqual("no actor spawned or destroyed (select / boost / hover)", CountActors(), Actors0);
  TestEqual("no component added (select / boost / hover)", CountComponents(), Components0);
  TestEqual("still no highlight actors", Board->GetHighlightActorCount(), 0);
  // the draft of scene 2: destinations, NeedBoost and a Conflict glyph on the plates
  FS09CommandUi Ui2;
  const FString File2 = FPaths::Combine(MoveDraftDir(), TEXT("marmoreal-2-draft-conflict-needboost.json"));
  S09MoveDraftBench::FFixture Fixture2;
  Errors.Reset();
  if (TestTrue("scene 2 fixture", FFileHelper::LoadFileToString(Text, *File2) &&
                                      S09MoveDraftBench::Parse(Text, FPaths::GetCleanFilename(File2), Fixture2, Errors))) {
    const S09MoveDraftBench::FApplyResult A2 = S09MoveDraftBench::Apply(Fixture2, B.Snapshot, B.Board, B.Fighters, B.ViewerId, Ui2);
    if (TestTrue(TEXT("scene 2 applied: ") + A2.Error, A2.bOk)) {
      Board->SetMoveDraftViewProvider([&](const FString&, const TSet<uint64>&, FS08MoveDraftView& Out) {
        Out = S08MoveHighlight::BuildDraftView(B.Board, B.Fighters, S09MoveDraftView::BuildInput(Ui2, B.Board, B.Fighters));
        return true;
      });
      Board->SetSelectedFighter(Ui2.SelectedFighterId, Ui2.ReachableCells);
      int32 Conflicts = 0, NeedBoost = 0, Destinations = 0, Glyphs = 0;
      for (int32 I = 0; I < HL->GetSpaceCount(); ++I) {
        if (!HL->IsInstanceVisible(EChannel::Ring, I)) continue;
        const int32 S = FMath::RoundToInt(HL->GetCustomData(EChannel::Ring, I, S08MovePlateCpd::State));
        Conflicts += S == static_cast<int32>(ES08RingState::Conflict);
        NeedBoost += S == static_cast<int32>(ES08RingState::NeedBoost);
        Destinations += S == static_cast<int32>(ES08RingState::Destination);
        Glyphs += HL->IsInstanceVisible(EChannel::Glyph, I) ? 1 : 0;
      }
      TestEqual("scene 2: one Conflict ring", Conflicts, 1);
      TestEqual("scene 2: one NeedBoost ring", NeedBoost, 1);
      TestEqual("scene 2: one Destination ring", Destinations, 1);
      TestEqual("scene 2: one '!' glyph", Glyphs, 1);
      TestEqual("scene 2: no actor spawned", CountActors(), Actors0);
    }
  }
  // without the flag the old ring path is back (the reference frames of other sessions do not change)
  S08MoveHighlight::SetEnabledOverrideForTest(false);
  TestFalse("flag off: no plates", Board->UsesMovePlates());
  S08MoveHighlight::SetEnabledOverrideForTest(true);
  Board->Destroy();
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08MoveHLBenchDraftTest,
    "Unmatched.S08.MoveHL.BenchDraft -BenchMoveDraft scene fixtures open the draft over the real bench states; unknown ids are a mismatch",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08MoveHLBenchDraftTest::RunTest(const FString&) {
  using namespace S08MoveHLTest;
  TArray<FString> Files;
  IFileManager::Get().FindFiles(Files, *FPaths::Combine(MoveDraftDir(), TEXT("*.json")), true, false);
  Files.Sort();
  TestTrue(FString::Printf(TEXT("scene fixtures in %s (%d)"), *MoveDraftDir(), Files.Num()), Files.Num() >= 4);
  for (const FString& Name : Files) {
    FString Text;
    S09MoveDraftBench::FFixture Fixture;
    TArray<FString> Errors;
    if (!TestTrue(Name + TEXT(" parses: ") + FString::Join(Errors, TEXT(" | ")),
                  FFileHelper::LoadFileToString(Text, *FPaths::Combine(MoveDraftDir(), Name)) &&
                      S09MoveDraftBench::Parse(Text, Name, Fixture, Errors))) {
      continue;
    }
    FBench B;
    if (!TestTrue(Name + TEXT(": bench fixture ") + Fixture.BenchFixture, LoadBench(*Fixture.BenchFixture, B))) continue;
    TestTrue(Name + TEXT(": a real board (Marmoreal / Sarpedon original)"),
             B.BoardId == TEXT("c121b47f8d6eb28daccb76d05") || B.BoardId == TEXT("c7fa64a26c29a0835f2383e63"));
    FS09CommandUi Ui;
    const S09MoveDraftBench::FApplyResult R = S09MoveDraftBench::Apply(Fixture, B.Snapshot, B.Board, B.Fighters, B.ViewerId, Ui);
    TestTrue(Name + TEXT(" applies: ") + R.Error, R.bOk);
    AddInfo(R.Summary);
    TestTrue(Name + TEXT(": draft mode"), Ui.Mode == ES09CommandMode::ManeuverDraft);
    TestTrue(Name + TEXT(": bench maneuver id"), Ui.PendingManeuverId == TEXT("bench:") + Name);
    if (Fixture.Scene.StartsWith(TEXT("1-"))) {
      TestTrue(Name + TEXT(": scene 1 selects with base and boost tiers"),
               !Ui.SelectedFighterId.IsEmpty() && Ui.SelectedTiers.BaseTier.Num() > 0 && Ui.SelectedTiers.BoostTier.Num() > 0);
      TestTrue(Name + TEXT(": hover on a space"), R.Hover.X >= 0);
    } else if (Fixture.Scene.StartsWith(TEXT("2-"))) {
      TestEqual(Name + TEXT(": three moves"), Ui.Moves.Num(), 3);
      TestEqual(Name + TEXT(": one Ok"), Ui.Eval.NumOk, 1);
      TestEqual(Name + TEXT(": one NeedBoost"), Ui.Eval.NumNeedBoost, 1);
      TestEqual(Name + TEXT(": one Conflict"), Ui.Eval.NumConflict, 1);
    } else if (Fixture.Scene.StartsWith(TEXT("0-"))) {
      // DE-017 (MS-R-75): MS-S-06 - a candidate ring V-17 under every own fighter that may move, nothing selected
      const TArray<FString> Movers = Ui.MovableFighterIds(B.Fighters);
      const FS08MoveDraftView View =
          S08MoveHighlight::BuildDraftView(B.Board, B.Fighters, S09MoveDraftView::BuildInput(Ui, B.Board, B.Fighters));
      int32 Rings = 0;
      for (const FS08PlateView& P : View.Plates) Rings += P.Ring == ES08RingState::Candidate ? 1 : 0;
      TestTrue(Name + TEXT(": scene 0 has no selection and no move"), Ui.SelectedFighterId.IsEmpty() && Ui.Moves.Num() == 0);
      TestTrue(Name + TEXT(": several own movers (Medusa + Harpies)"), Movers.Num() >= 2);
      TestEqual(Name + TEXT(": one candidate ring per mover"), Rings, Movers.Num());
    }
  }
  // a fighter or a card the bench state does not have: MS-BENCH mismatch, no draft
  FBench B;
  if (TestTrue("Sarpedon bench state", LoadBench(TEXT("S08BenchSarpedon.json"), B))) {
    for (const TCHAR* Doc : {
             TEXT("{\"schema\":\"unmatched.move-draft/1\",\"moves\":[{\"fighterId\":\"f-9-ghost\",\"to\":\"S20\"}]}"),
             TEXT("{\"schema\":\"unmatched.move-draft/1\",\"boostCardId\":\"nope::0\",\"selected\":\"f-0-hero\"}")}) {
      S09MoveDraftBench::FFixture Fixture;
      TArray<FString> Errors;
      TestTrue("mismatch doc parses", S09MoveDraftBench::Parse(Doc, TEXT("mismatch.json"), Fixture, Errors));
      FS09CommandUi Ui;
      const S09MoveDraftBench::FApplyResult R = S09MoveDraftBench::Apply(Fixture, B.Snapshot, B.Board, B.Fighters, B.ViewerId, Ui);
      TestFalse(FString::Printf(TEXT("mismatch refused (%s)"), *R.Error), R.bOk);
      TestFalse("mismatch id reported", R.MismatchId.IsEmpty());
    }
    S09MoveDraftBench::FFixture Fixture;
    TArray<FString> Errors;
    TestFalse("wrong schema refused", S09MoveDraftBench::Parse(TEXT("{\"schema\":\"x/1\"}"), TEXT("x.json"), Fixture, Errors));
    Errors.Reset();
    TestFalse("unknown field refused",
              S09MoveDraftBench::Parse(TEXT("{\"schema\":\"unmatched.move-draft/1\",\"move\":[]}"), TEXT("x.json"), Fixture, Errors));
    Errors.Reset();
    TestTrue("reserved fields traced as skipped",
             S09MoveDraftBench::Parse(TEXT("{\"schema\":\"unmatched.move-draft/1\",\"lastMovement\":{}}"), TEXT("x.json"), Fixture,
                                      Errors) &&
                 Fixture.Skipped.Contains(TEXT("lastMovement")));
  }
  return true;
}
