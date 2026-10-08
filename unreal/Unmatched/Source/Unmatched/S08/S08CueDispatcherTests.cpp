// DE-018 automation tests: the world-free CUE dispatcher (S08CueDispatcher.h) against the contract
// docs/unreal/contracts/cue-dispatcher (CUE-DISPATCHER.md §4, §7):
//   Unmatched.S08.CueDispatcher.Table    - the built-in combat rows ARE cue-table.json (field by field);
//   Unmatched.S08.CueDispatcher.Fixtures - every scenario fixture of those rows (no combat staging) gives its
//                                          expect_trace byte for byte (the C++ port the contract asks for);
//   Unmatched.S08.CueDispatcher.Hold     - the DE-018 hold inside CUE-010 and its change by a skip.
#if WITH_AUTOMATION_TESTS

#include "S08CueDispatcher.h"
#include "S08FlowController.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Misc/AutomationTest.h"
#include "HAL/FileManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace S08CueDispatcherTest {
FString ContractDir() {
  return FPaths::ConvertRelativePathToFull(
      FPaths::Combine(FPaths::ProjectDir(), TEXT("../../docs/unreal/contracts/cue-dispatcher")));
}

TSharedPtr<FJsonObject> LoadJson(const FString& Path) {
  FString Text;
  TSharedPtr<FJsonObject> Object;
  if (!FFileHelper::LoadFileToString(Text, *Path)) return nullptr;
  const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Text);
  if (!FJsonSerializer::Deserialize(Reader, Object)) return nullptr;
  return Object;
}

/** /Game/A/B.B -> B (cue_contract.short_name). */
FString ShortName(const FString& SoftPath) {
  FString Left, Right;
  return SoftPath.Split(TEXT("."), &Left, &Right, ESearchCase::CaseSensitive, ESearchDir::FromEnd) ? Right : SoftPath;
}

/** cue_contract.fighter_clip: the H2Anim clip of a trace subject (merlin -> Merlin, arthur -> KingArthur). */
FString FighterClip(const FString& Subject, const FString& Role) {
  FString Letters;
  for (const TCHAR C : Subject.ToLower()) {
    if (C >= TEXT('a') && C <= TEXT('z')) Letters.AppendChar(C);
  }
  if (Letters.Len() < 3) return FString();
  for (const TCHAR* Key : {TEXT("KingArthur"), TEXT("Merlin"), TEXT("Medusa"), TEXT("Harpy")}) {
    const FString K = FString(Key).ToLower();
    if (Letters == K || K.EndsWith(Letters) || Letters.StartsWith(K)) {
      return FString::Printf(TEXT("AM_%s_%s"), Key, *Role);
    }
  }
  return FString();
}

/** VS-6 F1: the vfx systems the table marks present (cue_contract ReferenceDispatcher: vfx.system when status present). */
TMap<FString, FString> TablePresentVfx() {
  TMap<FString, FString> Out;
  const TSharedPtr<FJsonObject> Table = LoadJson(ContractDir() / TEXT("cue-table.json"));
  if (!Table.IsValid()) return Out;
  for (const TSharedPtr<FJsonValue>& Value : Table->GetArrayField(TEXT("cues"))) {
    const TSharedPtr<FJsonObject> Row = Value->AsObject();
    const TSharedPtr<FJsonObject>* Vfx = nullptr;
    FString Status, System;
    if (Row.IsValid() && Row->TryGetObjectField(TEXT("vfx"), Vfx) && (*Vfx)->TryGetStringField(TEXT("status"), Status) &&
        Status == TEXT("present") && (*Vfx)->TryGetStringField(TEXT("system"), System)) {
      Out.Add(Row->GetStringField(TEXT("id")), System);
    }
  }
  return Out;
}

/** Asset tokens of a fixture: assets_present overrides (short names; assets_unloadable -> missing), else the
 *  rows' state - a vfx system the table marks present (VS-6 F1), no sfx path (ART-010), the H2Anim clip of the
 *  subject. */
void BindFixtureAssets(FS08CueDispatcher& Cues, const TSharedPtr<FJsonObject>& Fixture) {
  TMap<FString, FString> Present;  // "<cue>|<channel>" -> path
  const TSharedPtr<FJsonObject>* Assets = nullptr;
  if (Fixture->TryGetObjectField(TEXT("assets_present"), Assets)) {
    for (const auto& Cue : (*Assets)->Values) {
      const TSharedPtr<FJsonObject> Channels = Cue.Value->AsObject();
      if (!Channels.IsValid()) continue;
      for (const auto& Channel : Channels->Values) {
        Present.Add(FString(*Cue.Key) + TEXT("|") + FString(*Channel.Key), Channel.Value->AsString());
      }
    }
  }
  TSet<FString> Unloadable;
  const TArray<TSharedPtr<FJsonValue>>* Bad = nullptr;
  if (Fixture->TryGetArrayField(TEXT("assets_unloadable"), Bad)) {
    for (const TSharedPtr<FJsonValue>& Value : *Bad) Unloadable.Add(Value->AsString());
  }
  const TArray<FS08CueRow> Rows = S08CueRows::Combat();
  const TMap<FString, FString> TableVfx = TablePresentVfx();
  Cues.AssetResolver = [Present, Unloadable, Rows, TableVfx](const FString& CueId, const FString& Channel,
                                                             const FString& Subject) -> FString {
    FString Path;
    if (const FString* Override = Present.Find(CueId + TEXT("|") + Channel)) Path = *Override;
    if (Path.IsEmpty() && Channel == TEXT("vfx")) {
      if (const FString* System = TableVfx.Find(CueId)) Path = *System;
    }
    if (Path.IsEmpty() && Channel == TEXT("clip")) {
      const FS08CueRow* Row = S08CueRows::Find(Rows, CueId);
      const FString Clip = Row ? FighterClip(Subject, Row->ClipRole) : FString();
      return Clip.IsEmpty() ? FString(TEXT("missing")) : Clip;
    }
    if (Path.IsEmpty() || Unloadable.Contains(Path)) return TEXT("missing");
    return ShortName(Path);
  };
}

TArray<FString> StringArray(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field) {
  TArray<FString> Out;
  const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
  if (Object->TryGetArrayField(Field, Values)) {
    for (const TSharedPtr<FJsonValue>& Value : *Values) Out.Add(Value->AsString());
  }
  return Out;
}
}  // namespace S08CueDispatcherTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08CueDispatcherTableTest, "Unmatched.S08.CueDispatcher.Table",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08CueDispatcherTableTest::RunTest(const FString&) {
  using namespace S08CueDispatcherTest;
  const TSharedPtr<FJsonObject> Table = LoadJson(ContractDir() / TEXT("cue-table.json"));
  TestTrue("cue-table.json read", Table.IsValid());
  if (!Table.IsValid()) return false;
  TMap<FString, TSharedPtr<FJsonObject>> ById;
  for (const TSharedPtr<FJsonValue>& Value : Table->GetArrayField(TEXT("cues"))) {
    const TSharedPtr<FJsonObject> Row = Value->AsObject();
    ById.Add(Row->GetStringField(TEXT("id")), Row);
  }
  auto OnNewName = [](ES08CueOnNew OnNew) {
    switch (OnNew) {
      case ES08CueOnNew::Cascade: return TEXT("cascade");
      case ES08CueOnNew::JumpToFinal: return TEXT("jump_to_final");
      case ES08CueOnNew::Interrupt: return TEXT("interrupt");
      case ES08CueOnNew::None: return TEXT("none");
      default: return TEXT("replace");
    }
  };
  // VS-6 F1: + CUE-002 / 003 / 004 (local board answers) and CUE-007 (the move)
  TestEqual("eleven cue rows (CUE-001..004, CUE-007 + the six combat rows)", S08CueRows::Combat().Num(), 11);
  for (const FS08CueRow& Row : S08CueRows::Combat()) {
    const TSharedPtr<FJsonObject>* JsonPtr = ById.Find(Row.Id);
    TestTrue(Row.Id + TEXT(" in the table"), JsonPtr != nullptr);
    if (!JsonPtr) continue;
    const TSharedPtr<FJsonObject> J = *JsonPtr;
    const FString P = Row.Id + TEXT(" ");
    TestEqual(P + TEXT("source"), Row.bServer, J->GetStringField(TEXT("source")) == TEXT("server"));
    TestEqual(P + TEXT("subject"), Row.Subject, J->GetStringField(TEXT("subject")));
    double DurationJ = 0.0;  // CUE-007: null - the duration is the move schedule of the caller
    J->TryGetNumberField(TEXT("duration_ms"), DurationJ);
    TestEqual(P + TEXT("duration_ms"), Row.DurationMs, static_cast<int32>(DurationJ));
    TestEqual(P + TEXT("blocks_input"), Row.bBlocksInput, J->GetBoolField(TEXT("blocks_input")));
    TestEqual(P + TEXT("on_new_event"), FString(OnNewName(Row.OnNew)), J->GetStringField(TEXT("on_new_event")));
    TestEqual(P + TEXT("replace_scope"), Row.bReplaceScopeCue, J->GetStringField(TEXT("replace_scope")) == TEXT("cue"));
    TestEqual(P + TEXT("interrupted_by"), FString::Join(Row.InterruptedBy, TEXT(",")),
              FString::Join(StringArray(J, TEXT("interrupted_by")), TEXT(",")));
    const TSharedPtr<FJsonObject> Reduced = J->GetObjectField(TEXT("reduced_motion"));
    TestEqual(P + TEXT("reduced_motion.mode"),
              FString(Row.Reduced == ES08CueReduced::Shorten ? TEXT("shorten")
                      : Row.Reduced == ES08CueReduced::Snap  ? TEXT("snap")
                                                             : TEXT("keep")),
              Reduced->GetStringField(TEXT("mode")));
    if (Row.Reduced == ES08CueReduced::Shorten) {
      TestEqual(P + TEXT("reduced_motion.max_ms"), Row.ReducedMaxMs,
                static_cast<int32>(Reduced->GetNumberField(TEXT("max_ms"))));
    }
    const TSharedPtr<FJsonObject>* Vfx = nullptr;
    const bool bVfx = J->TryGetObjectField(TEXT("vfx"), Vfx);
    TestEqual(P + TEXT("vfx present"), Row.bHasVfx, bVfx);
    if (bVfx) {
      const bool bSocket = (*Vfx)->GetStringField(TEXT("attach")) == TEXT("socket");
      TestEqual(P + TEXT("vfx.attach"), Row.bVfxSocket, bSocket);
      if (bSocket) TestEqual(P + TEXT("vfx.socket"), Row.Socket, (*Vfx)->GetStringField(TEXT("socket")));
    }
    const TSharedPtr<FJsonObject>* Sfx = nullptr;
    const bool bSfx = J->TryGetObjectField(TEXT("sfx"), Sfx);
    TestEqual(P + TEXT("sfx present"), Row.bHasSfx, bSfx);
    if (bSfx) {
      const TSharedPtr<FJsonObject> Conc = (*Sfx)->GetObjectField(TEXT("concurrency"));
      double MaxCount = 0.0;
      Conc->TryGetNumberField(TEXT("max_count"), MaxCount);
      TestEqual(P + TEXT("sfx.max_count"), Row.SfxMaxCount, static_cast<int32>(MaxCount));
      TestEqual(P + TEXT("sfx.resolution"), Row.bSfxPreventNew,
                Conc->GetStringField(TEXT("resolution")) == TEXT("PreventNew"));
      TestEqual(P + TEXT("sfx.retrigger_ms"), Row.SfxRetriggerMs,
                static_cast<int32>(Conc->GetNumberField(TEXT("retrigger_ms"))));
    }
    const TSharedPtr<FJsonObject>* Clip = nullptr;
    const FString ClipRole = J->TryGetObjectField(TEXT("clip"), Clip) ? (*Clip)->GetStringField(TEXT("role")) : FString();
    TestEqual(P + TEXT("clip.role"), Row.ClipRole, ClipRole);
    const TSharedPtr<FJsonObject>* Material = nullptr;
    const FString Mat = J->TryGetObjectField(TEXT("material"), Material)
                            ? (*Material)->GetStringField(TEXT("cpd_param")) : FString(TEXT("none"));
    TestEqual(P + TEXT("material.cpd_param"), Row.Mat, Mat);
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08CueDispatcherFixturesTest, "Unmatched.S08.CueDispatcher.Fixtures",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08CueDispatcherFixturesTest::RunTest(const FString&) {
  using namespace S08CueDispatcherTest;
  TArray<FString> Files;
  IFileManager::Get().FindFiles(Files, *(ContractDir() / TEXT("fixtures/*.json")), true, false);
  Files.Sort();
  int32 Ported = 0;
  for (const FString& File : Files) {
    const TSharedPtr<FJsonObject> Fixture = LoadJson(ContractDir() / TEXT("fixtures") / File);
    TestTrue(File + TEXT(" parses"), Fixture.IsValid());
    if (!Fixture.IsValid() || Fixture->GetStringField(TEXT("kind")) != TEXT("scenario")) continue;
    if (Fixture->HasField(TEXT("staging"))) continue;  // Unmatched.S09.CombatStage.Fixtures runs those
    // Only the rows this dispatcher carries and the event kinds it takes.
    bool bPortable = true;
    for (const TSharedPtr<FJsonValue>& Value : Fixture->GetArrayField(TEXT("events"))) {
      const TSharedPtr<FJsonObject> E = Value->AsObject();
      const FString Kind = E->GetStringField(TEXT("kind"));
      if (Kind == TEXT("cue") && !S08CueRows::Find(S08CueRows::Combat(), E->GetStringField(TEXT("id")))) {
        bPortable = false;
      }
      if (Kind != TEXT("cue") && Kind != TEXT("settings") && Kind != TEXT("advance") && Kind != TEXT("reconnect")) {
        bPortable = false;
      }
    }
    if (!bPortable) continue;
    ++Ported;
    FS08CueDispatcher Cues;
    BindFixtureAssets(Cues, Fixture);
    TArray<FString> Lines;
    for (const TSharedPtr<FJsonValue>& Value : Fixture->GetArrayField(TEXT("events"))) {
      const TSharedPtr<FJsonObject> E = Value->AsObject();
      const int64 T = static_cast<int64>(E->GetNumberField(TEXT("t")));
      const FString Kind = E->GetStringField(TEXT("kind"));
      if (Kind == TEXT("advance")) {
        Cues.Advance(T, Lines);
      } else if (Kind == TEXT("settings")) {
        Cues.SetReducedMotion(E->GetBoolField(TEXT("reduced_motion")), T, Lines);
      } else if (Kind == TEXT("reconnect")) {
        Cues.OnReconnect(static_cast<int32>(E->GetNumberField(TEXT("recovered_seq"))), T, Lines);
      } else {
        double Seq = -1.0;
        E->TryGetNumberField(TEXT("seq"), Seq);
        double Hold = 0.0, Duration = -1.0;
        E->TryGetNumberField(TEXT("hold_ms"), Hold);
        E->TryGetNumberField(TEXT("duration_ms"), Duration);
        FString Subject;
        E->TryGetStringField(TEXT("subject"), Subject);
        bool bStaged = false;
        E->TryGetBoolField(TEXT("staged"), bStaged);
        // VS-6 FX-13: CUE-007 lasts its move schedule (04 §6.3) - the seq's moves (seq_moves + order) or this one
        // move; the game passes the plan's duration the same way (FS08MoveCueSchedule, cue_contract move_schedule)
        if (E->GetStringField(TEXT("id")) == TEXT("CUE-007") && Duration < 0.0) {
          TArray<FS08MoveCueInput> Moves;
          const TArray<TSharedPtr<FJsonValue>>* SeqMoves = nullptr;
          auto AddMove = [&Moves](const TSharedPtr<FJsonObject>& M, const TCHAR* KindField) {
            FS08MoveCueInput In;
            FString Kind;
            M->TryGetStringField(KindField, Kind);
            In.Kind = Kind == TEXT("place") ? ES08MoveKind::Place : ES08MoveKind::Move;
            double Steps = 1.0;
            M->TryGetNumberField(TEXT("steps"), Steps);
            In.Steps = FMath::Max(1, static_cast<int32>(Steps));
            Moves.Add(In);
          };
          if (E->TryGetArrayField(TEXT("seq_moves"), SeqMoves) && SeqMoves && SeqMoves->Num() > 0) {
            for (const TSharedPtr<FJsonValue>& M : *SeqMoves) AddMove(M->AsObject(), TEXT("kind"));
          } else {
            AddMove(E, TEXT("move_kind"));
          }
          double Order = 0.0;
          E->TryGetNumberField(TEXT("order"), Order);
          const TArray<FS08MoveCueTiming> Timing = FS08MoveCueSchedule::Compute(Moves);
          const int32 Index = FMath::Clamp(static_cast<int32>(Order), 0, Timing.Num() - 1);
          Duration = Timing.IsValidIndex(Index) ? FMath::RoundToDouble(Timing[Index].DurationMs) : 0.0;
        }
        Cues.Feed(E->GetStringField(TEXT("id")), Subject, static_cast<int32>(Seq), T, Lines, static_cast<int32>(Hold),
                  static_cast<int32>(Duration), bStaged);
      }
    }
    Cues.Finish(Lines);
    const TArray<FString> Want = StringArray(Fixture, TEXT("expect_trace"));
    TestEqual(File + TEXT(": line count"), Lines.Num(), Want.Num());
    for (int32 I = 0; I < FMath::Min(Lines.Num(), Want.Num()); ++I) {
      TestEqual(FString::Printf(TEXT("%s: line %d"), *File, I + 1), Lines[I], Want[I]);
    }
  }
  // attack-interrupt, dedupe-http-ws, missing-assets-fallback, sfx-concurrency-stop-oldest at least.
  TestTrue(FString::Printf(TEXT("ported fixtures %d >= 4"), Ported), Ported >= 4);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08CueDispatcherHoldTest, "Unmatched.S08.CueDispatcher.Hold",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08CueDispatcherHoldTest::RunTest(const FString&) {
  // DE-018 (§4 D12): CUE-010 with a 1000 ms read hold lasts 1800 ms and writes hold=; a skip shortens it.
  {
    FS08CueDispatcher Cues;
    TArray<FString> Lines;
    Cues.Feed(TEXT("CUE-010"), TEXT("scene"), 7, 100, Lines, 1000);
    TestEqual("show line", Lines.Last(),
              FString(TEXT("CUE fx id=CUE-010 subject=scene seq=7 t=100 vfx=none sfx=missing clip=none mat=none "
                           "socket=- reduced=0 result=fallback")));
    Cues.Advance(1899, Lines);
    TestTrue("still active before 1900", Cues.IsActive(TEXT("CUE-010"), TEXT("scene"), 7));
    Cues.Advance(1900, Lines);
    TestEqual("done with hold", Lines.Last(),
              FString(TEXT("CUE fx done id=CUE-010 subject=scene seq=7 t=1900 ms=1800 cut=0 hold=1000")));
  }
  {
    FS08CueDispatcher Cues;
    TArray<FString> Lines;
    Cues.Feed(TEXT("CUE-010"), TEXT("scene"), 8, 0, Lines, 1000);
    TestTrue("skip moves the end", Cues.SetHold(TEXT("CUE-010"), TEXT("scene"), 8, 380));
    Cues.Finish(Lines);
    TestEqual("done after skip", Lines.Last(),
              FString(TEXT("CUE fx done id=CUE-010 subject=scene seq=8 t=1180 ms=1180 cut=0 hold=380")));
    TestFalse("no active show to change", Cues.SetHold(TEXT("CUE-010"), TEXT("scene"), 8, 0));
  }
  // D2: the same seq twice is one show - a repeated seq never shows the damage again (ACC-012).
  {
    FS08CueDispatcher Cues;
    TArray<FString> Lines;
    TestTrue("first CUE-011 shown",
             Cues.Feed(TEXT("CUE-011"), TEXT("f-1-hero"), 31, 0, Lines) == ES08CueResult::Fallback);
    TestTrue("repeat is a duplicate",
             Cues.Feed(TEXT("CUE-011"), TEXT("f-1-hero"), 31, 40, Lines) == ES08CueResult::Duplicate);
    TestTrue("older seq is stale", Cues.Feed(TEXT("CUE-011"), TEXT("f-0-hero"), 30, 50, Lines) == ES08CueResult::Stale);
  }
  // D3 and the staging (run C G-LIVE 2026-10-05): the next attack (seq 28/29) lands while the combat of seq 24 is
  // staged; its contact CUE-011 still shows at seq 24, a repeat of it stays a duplicate, a reconnect still covers it.
  {
    FS08CueDispatcher Cues;
    TArray<FString> Lines;
    Cues.Feed(TEXT("CUE-010"), TEXT("scene"), 24, 0, Lines, 1000);
    Cues.Feed(TEXT("CUE-008"), TEXT("f-0-hero"), 28, 1600, Lines);
    Cues.Feed(TEXT("CUE-009"), TEXT("f-1-hero"), 29, 1700, Lines);
    TestTrue("staged CUE-011 after newer seqs is shown",
             Cues.Feed(TEXT("CUE-011"), TEXT("f-0-hero"), 24, 2433, Lines, 0, -1, true) == ES08CueResult::Fallback);
    TestTrue("staged repeat is a duplicate",
             Cues.Feed(TEXT("CUE-011"), TEXT("f-0-hero"), 24, 2440, Lines, 0, -1, true) == ES08CueResult::Duplicate);
    TestTrue("unstaged older seq is still stale",
             Cues.Feed(TEXT("CUE-011"), TEXT("f-1-hero"), 25, 2450, Lines) == ES08CueResult::Stale);
    Cues.OnReconnect(30, 2500, Lines);
    TestTrue("staged cue under a reconnect is stale",
             Cues.Feed(TEXT("CUE-013"), TEXT("f-1-hero"), 29, 2600, Lines, 0, -1, true) == ES08CueResult::Stale);
  }
  // D11: reduced motion shortens the animation part only.
  {
    FS08CueDispatcher Cues;
    TArray<FString> Lines;
    Cues.SetReducedMotion(true, 0, Lines);
    TestEqual("reduced CUE-010 length", Cues.ShowDurationMs(TEXT("CUE-010")), 100);
    Cues.Feed(TEXT("CUE-010"), TEXT("scene"), 9, 0, Lines, 500);
    Cues.Finish(Lines);
    TestEqual("reduced + hold", Lines.Last(),
              FString(TEXT("CUE fx done id=CUE-010 subject=scene seq=9 t=600 ms=600 cut=0 hold=500")));
  }
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
