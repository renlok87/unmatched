// DE-018 automation tests: the combat staging (S09CombatStage.h) and the combat panel model (S09HudModel.h).
//   Unmatched.S09.CombatStage.Fixtures - the staging + dispatcher rebuild the expect_trace of every fixture with a
//                                        `staging` block byte for byte (docs/unreal/contracts/cue-dispatcher);
//   Unmatched.S09.CombatStage.Timeline - the F-01 scale (3.9 s with effect text, 2.9 s without, +0.6 s per line),
//                                        the speed multiplier, reduced motion, the skip, events and holds;
//   Unmatched.S09.CombatStage.Reveal   - the revealed cards from the real gd034 projections (no hidden identity),
//                                        the defense slot in three states.
#if WITH_AUTOMATION_TESTS

#include "S09CombatStage.h"
#include "S09HudModel.h"
#include "../S08/S08Contracts.h"
#include "../S08/S08CueDispatcher.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "HAL/FileManager.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace S09CombatStageTest {
TSharedPtr<FJsonObject> LoadJson(const FString& Path) {
  FString Text;
  TSharedPtr<FJsonObject> Object;
  if (!FFileHelper::LoadFileToString(Text, *Path)) return nullptr;
  const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Text);
  if (!FJsonSerializer::Deserialize(Reader, Object)) return nullptr;
  return Object;
}

FString ContractDir() {
  return FPaths::ConvertRelativePathToFull(
      FPaths::Combine(FPaths::ProjectDir(), TEXT("../../docs/unreal/contracts/cue-dispatcher")));
}

/** The fixtures' clip rule (cue_contract.fighter_clip): trace subject -> AM_<Key>_<Role>. */
void BindClips(FS08CueDispatcher& Cues) {
  Cues.AssetResolver = [](const FString& CueId, const FString& Channel, const FString& Subject) -> FString {
    if (Channel != TEXT("clip")) return TEXT("missing");
    const FS08CueRow* Row = S08CueRows::Find(S08CueRows::Combat(), CueId);
    FString Letters;
    for (const TCHAR C : Subject.ToLower()) {
      if (C >= TEXT('a') && C <= TEXT('z')) Letters.AppendChar(C);
    }
    for (const TCHAR* Key : {TEXT("KingArthur"), TEXT("Merlin"), TEXT("Medusa"), TEXT("Harpy")}) {
      const FString K = FString(Key).ToLower();
      if (Row && Letters.Len() >= 3 && (Letters == K || K.EndsWith(Letters) || Letters.StartsWith(K))) {
        return FString::Printf(TEXT("AM_%s_%s"), Key, *Row->ClipRole);
      }
    }
    return TEXT("missing");
  };
}

FS09CombatStageInput BaseInput(bool bText, int32 Damage) {
  FS09CombatStageInput In;
  In.Seq = 31;
  In.AttackerId = TEXT("arthur");
  In.TargetId = TEXT("medusa");
  In.bHasEffectText = bText;
  In.Damage = Damage;
  In.HpBefore = 7;
  In.HpAfter = 7 - Damage;
  In.TargetX = 3;
  In.TargetY = 4;
  In.ContactMs = 292;
  In.ContactSource = TEXT("notify");
  In.Reveal.AttackValue = 4;
  In.Reveal.DefenseValue = 0;
  In.Reveal.bNoDefense = true;
  return In;
}

/** Runs one staging to its end on a 1 ms clock; returns the trace and the events. */
struct FRun {
  TArray<FString> Lines;
  TArray<FS09CombatStageEvent> Events;
  FS09CombatStage Stage;
  FS08CueDispatcher Cues;
};
void RunToEnd(FRun& Run, const FS09CombatStageInput& In, int64 StartMs = 1000, int64 SkipAt = -1,
              bool bReduced = false) {
  if (bReduced) Run.Cues.SetReducedMotion(true, 0, Run.Lines);
  Run.Stage.Start(In, StartMs, Run.Cues, Run.Lines, Run.Events);
  for (int64 T = StartMs; T <= StartMs + 20000 && Run.Stage.IsActive(); ++T) {
    Run.Stage.Tick(T, Run.Cues, Run.Lines, Run.Events);
    Run.Cues.Advance(T, Run.Lines);
    if (T == SkipAt) Run.Stage.Skip(T, TEXT("click"), Run.Cues, Run.Lines, Run.Events);
  }
  Run.Cues.Finish(Run.Lines);
}

int64 EventAt(const TArray<FS09CombatStageEvent>& Events, ES09CombatEvent Type) {
  for (const FS09CombatStageEvent& E : Events) {
    if (E.Type == Type) return E.AtMs;
  }
  return -1;
}

bool LoadS09Snapshot(const FString& Name, FS08Snapshot& Out) {
  const FString Path = FPaths::Combine(FPaths::ProjectDir(), TEXT("../../docs/game-design/evidence/S09/fixtures"),
                                       Name + TEXT(".json"));
  const TSharedPtr<FJsonObject> Root = LoadJson(Path);
  if (!Root.IsValid()) return false;
  FString Raw;
  if (!Root->TryGetStringField(TEXT("raw"), Raw)) return false;
  FString RawState;
  FS08GraphQLError Error;
  return FS08Contracts::ParseGameStateQuery(Raw, Out, RawState, Error);
}
}  // namespace S09CombatStageTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09CombatStageFixturesTest, "Unmatched.S09.CombatStage.Fixtures",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09CombatStageFixturesTest::RunTest(const FString&) {
  using namespace S09CombatStageTest;
  TArray<FString> Files;
  IFileManager::Get().FindFiles(Files, *(ContractDir() / TEXT("fixtures/*.json")), true, false);
  Files.Sort();
  int32 Ported = 0;
  for (const FString& File : Files) {
    const TSharedPtr<FJsonObject> Fixture = LoadJson(ContractDir() / TEXT("fixtures") / File);
    const TSharedPtr<FJsonObject>* StagingPtr = nullptr;
    if (!Fixture.IsValid() || !Fixture->TryGetObjectField(TEXT("staging"), StagingPtr)) continue;
    ++Ported;
    const TSharedPtr<FJsonObject> Staging = *StagingPtr;
    const TSharedPtr<FJsonObject> J = Staging->GetObjectField(TEXT("input"));
    FS09CombatStageInput In;
    In.Seq = static_cast<int32>(J->GetNumberField(TEXT("seq")));
    In.AttackerId = J->GetStringField(TEXT("attacker"));
    In.TargetId = J->GetStringField(TEXT("target"));
    In.bHasEffectText = J->GetBoolField(TEXT("text"));
    In.EffectLines = static_cast<int32>(J->GetNumberField(TEXT("lines")));
    In.Damage = static_cast<int32>(J->GetNumberField(TEXT("damage")));
    In.bLethal = J->GetBoolField(TEXT("lethal"));
    In.bDamageShown = J->GetBoolField(TEXT("shown"));
    In.HpBefore = static_cast<int32>(J->GetNumberField(TEXT("hp_before")));
    In.HpAfter = static_cast<int32>(J->GetNumberField(TEXT("hp_after")));
    In.ContactMs = static_cast<int32>(J->GetNumberField(TEXT("contact")));
    In.ContactSource = J->GetStringField(TEXT("src"));
    In.SpeedMul = static_cast<float>(J->GetNumberField(TEXT("speed")));
    In.Reveal.AttackValue = static_cast<int32>(J->GetNumberField(TEXT("a")));
    In.Reveal.DefenseValue = static_cast<int32>(J->GetNumberField(TEXT("d")));
    const int64 StartT = static_cast<int64>(Staging->GetNumberField(TEXT("start_t")));
    const int64 EndT = static_cast<int64>(Staging->GetNumberField(TEXT("end_t")));
    TMap<int64, FString> Skips;
    const TArray<TSharedPtr<FJsonValue>>* SkipValues = nullptr;
    if (Staging->TryGetArrayField(TEXT("skips"), SkipValues)) {
      for (const TSharedPtr<FJsonValue>& V : *SkipValues) {
        const TSharedPtr<FJsonObject> S = V->AsObject();
        Skips.Add(static_cast<int64>(S->GetNumberField(TEXT("t"))), S->GetStringField(TEXT("src")));
      }
    }
    const TSharedPtr<FJsonObject>* Declare = nullptr;
    const bool bDeclare = Staging->TryGetObjectField(TEXT("declare"), Declare);
    FS08CueDispatcher Cues;
    BindClips(Cues);
    FS09CombatStage Stage;
    TArray<FString> Lines;
    TArray<FS09CombatStageEvent> Events;
    // The game mode's order per frame: CUE-008 of the attack, the staging start, Tick + Advance, then a skip.
    for (int64 T = 0; T <= EndT; ++T) {
      if (bDeclare && T == static_cast<int64>((*Declare)->GetNumberField(TEXT("t")))) {
        Cues.Feed(TEXT("CUE-008"), (*Declare)->GetStringField(TEXT("subject")),
                  static_cast<int32>((*Declare)->GetNumberField(TEXT("seq"))), T, Lines);
      }
      if (T == StartT) TestTrue(File + TEXT(": started"), Stage.Start(In, T, Cues, Lines, Events));
      Stage.Tick(T, Cues, Lines, Events);
      Cues.Advance(T, Lines);
      if (const FString* Src = Skips.Find(T)) {
        TestTrue(File + TEXT(": skip accepted"), Stage.Skip(T, **Src, Cues, Lines, Events));
      }
    }
    Cues.Finish(Lines);
    TArray<FString> Want;
    for (const TSharedPtr<FJsonValue>& V : Fixture->GetArrayField(TEXT("expect_trace"))) Want.Add(V->AsString());
    TestEqual(File + TEXT(": line count"), Lines.Num(), Want.Num());
    for (int32 I = 0; I < FMath::Min(Lines.Num(), Want.Num()); ++I) {
      TestEqual(FString::Printf(TEXT("%s: line %d"), *File, I + 1), Lines[I], Want[I]);
    }
    TestFalse(File + TEXT(": staging ended"), Stage.IsActive());
  }
  TestTrue(FString::Printf(TEXT("combat fixtures %d >= 3"), Ported), Ported >= 3);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09CombatStageTimelineTest, "Unmatched.S09.CombatStage.Timeline",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09CombatStageTimelineTest::RunTest(const FString&) {
  using namespace S09CombatStageTest;
  // ---- 01 F-01 + "Резолюция" п. 1: 600 + 800 + 1000 + 300 + contact + 900 ----
  {
    FRun Run;
    RunToEnd(Run, BaseInput(true, 2));
    TestEqual("with effect text: 3892 ms", Run.Stage.TotalMs(), static_cast<int64>(3892));
    TestTrue("within 3.9 s +-10 %", Run.Stage.TotalMs() >= 3510 && Run.Stage.TotalMs() <= 4290);
    TestEqual("lunge after slam + 300", EventAt(Run.Events, ES09CombatEvent::Lunge), static_cast<int64>(3100));
    TestEqual("HitReact in the contact frame", EventAt(Run.Events, ES09CombatEvent::HitReact),
              static_cast<int64>(3392));
    TestEqual("-N contact + 60", EventAt(Run.Events, ES09CombatEvent::Minus), static_cast<int64>(3452));
    TestEqual("HP contact + 80", EventAt(Run.Events, ES09CombatEvent::Hp), static_cast<int64>(3472));
    TestEqual("no fall without a lethal blow", EventAt(Run.Events, ES09CombatEvent::Fall), static_cast<int64>(-1));
    TestEqual("end = contact + 900", EventAt(Run.Events, ES09CombatEvent::End), static_cast<int64>(4292));
    TestEqual("hit tint 450", Run.Stage.GetHitTintMs(), 450);
  }
  {
    FRun Run;
    RunToEnd(Run, BaseInput(false, 2));
    TestEqual("without effect text: 2892 ms", Run.Stage.TotalMs(), static_cast<int64>(2892));
  }
  // ---- AN-24 (ВР-06): the Face turn to the target 120 ms before the lunge, inside the pause "score" ----
  {
    FRun Run;
    RunToEnd(Run, BaseInput(true, 2));
    TestEqual("face = lunge - 120", EventAt(Run.Events, ES09CombatEvent::Face),
              EventAt(Run.Events, ES09CombatEvent::Lunge) - 120);
    TestEqual("GetFaceMs = the lunge - 120", Run.Stage.GetFaceMs(), Run.Stage.GetLungeMs() - 120);
    bool bFaceLine = false;
    for (const FString& L : Run.Lines) bFaceLine |= L.Contains(TEXT(" stage=face ")) && L.Contains(TEXT(" ms=120"));
    TestTrue("the face line is traced with its window", bFaceLine);
  }
  {
    // A skip drops the pause: the face fires together with the lunge (the turn runs with the clip's first 120 ms).
    FRun Run;
    RunToEnd(Run, BaseInput(true, 2), 1000, /*SkipAt=*/2000);
    TestEqual("after the skip: face together with the lunge", EventAt(Run.Events, ES09CombatEvent::Face),
              Run.Stage.GetLungeMs());
  }
  {
    FRun Run;
    FS09CombatStageInput In = BaseInput(true, 2);
    In.EffectLines = 2;
    RunToEnd(Run, In);
    TestEqual("+600 ms per fired line", Run.Stage.TotalMs(), static_cast<int64>(3892 + 1200));
    int32 EffectLines = 0;
    for (const FString& L : Run.Lines) EffectLines += L.Contains(TEXT(" stage=effect ")) ? 1 : 0;
    TestEqual("one effect line each", EffectLines, 2);
  }
  // ---- speed (SD-49): flip / slam / lunge / "-N" scale, holds do not ----
  {
    FRun Run;
    FS09CombatStageInput In = BaseInput(true, 2);
    In.SpeedMul = 0.5f;
    RunToEnd(Run, In);
    TestEqual("fast: 300 + 400 + 1000 + 300 + 146 + 450", Run.Stage.TotalMs(), static_cast<int64>(2596));
    TestEqual("fast -N 450", Run.Stage.MinusLifeMs(), 450);
    // DE-025: the lunge clip at play rate 2 lands its contact frame on the scaled 146; the tint stays 450.
    TestEqual("fast lunge rate 2", Run.Stage.LungePlayRate(), 2.0f);
    TestEqual("fast: hit tint not scaled", Run.Stage.GetHitTintMs(), 450);
    bool bRateLine = false;
    for (const FString& L : Run.Lines) bRateLine |= L.Contains(TEXT(" stage=lunge ")) && L.Contains(TEXT(" rate=2.00"));
    TestTrue("lunge line carries rate=2.00", bRateLine);
  }
  {
    FRun Run;
    FS09CombatStageInput In = BaseInput(true, 2);
    In.SpeedMul = 1.5f;
    RunToEnd(Run, In);
    TestEqual("slow: 900 + 1200 + 1000 + 300 + 438 + 1000 (CUE-011 <= 1 s block)", Run.Stage.TotalMs(),
              static_cast<int64>(4838));
    TestEqual("slow -N 1350", Run.Stage.MinusLifeMs(), 1350);
    TestTrue("slow lunge rate 1/1.5", FMath::IsNearlyEqual(Run.Stage.LungePlayRate(), 1.0f / 1.5f));
  }
  {
    FRun Run;
    FS09CombatStageInput In = BaseInput(true, 2);
    In.SpeedMul = 0.0f;
    RunToEnd(Run, In);
    TestEqual("none: animations 0, holds stay (1000 + 300 + 450)", Run.Stage.TotalMs(), static_cast<int64>(1750));
    TestEqual("none: no lunge clip (rate 0)", Run.Stage.LungePlayRate(), 0.0f);
    TestEqual("none: -N keeps the fast 450", Run.Stage.MinusLifeMs(), 450);
    TestEqual("none: contact = lunge frame", Run.Stage.GetContactMs(), Run.Stage.GetLungeMs());
  }
  // ---- reduced motion (D11): CUE-010 <= 100, CUE-011 <= 100, the holds stay ----
  {
    FRun Run;
    RunToEnd(Run, BaseInput(true, 2), 1000, -1, /*bReduced=*/true);
    TestEqual("reduced: 600 + 100 + 1000 + 300 + 292 + 100", Run.Stage.TotalMs(), static_cast<int64>(2392));
    bool bReducedLine = false;
    for (const FString& L : Run.Lines) bReducedLine |= L.Contains(TEXT("id=CUE-011")) && L.Contains(TEXT("reduced=1"));
    TestTrue("CUE-011 shown reduced", bReducedLine);
  }
  // ---- lethal: tint 550, the fall (DeathSettle start, F-09) at contact + 450 ----
  {
    FRun Run;
    FS09CombatStageInput In = BaseInput(false, 7);
    In.bLethal = true;
    RunToEnd(Run, In);
    TestEqual("lethal tint 550", Run.Stage.GetHitTintMs(), 550);
    TestEqual("fall = contact + 450", EventAt(Run.Events, ES09CombatEvent::Fall),
              EventAt(Run.Events, ES09CombatEvent::HitReact) + 450);
  }
  // ---- the skip: holds to 0, clips never cut, once ----
  {
    FRun Run;
    RunToEnd(Run, BaseInput(true, 2), 1000, /*SkipAt=*/2000);
    TestEqual("skip in the read: 2000 is the slam", Run.Stage.GetSlamStartMs(), static_cast<int64>(2000));
    TestEqual("pause dropped: lunge at the slam end", Run.Stage.GetLungeMs(), static_cast<int64>(2180));
    TestEqual("total after skip", Run.Stage.TotalMs(), static_cast<int64>(600 + 2180 - 1000 + 292 + 900));
  }
  {
    FS09CombatStage Stage;
    FS08CueDispatcher Cues;
    TArray<FString> Lines;
    TArray<FS09CombatStageEvent> Events;
    Stage.Start(BaseInput(true, 2), 0, Cues, Lines, Events);
    TestTrue("skippable in the flip", Stage.IsSkippable(100));
    TestTrue("skip in the flip", Stage.Skip(100, TEXT("space"), Cues, Lines, Events));
    TestFalse("a second skip has nothing left", Stage.Skip(200, TEXT("space"), Cues, Lines, Events));
    TestEqual("flip plays on, slam at its end", Stage.GetSlamStartMs(), static_cast<int64>(620));
    for (int64 T = 0; T <= 900; ++T) Stage.Tick(T, Cues, Lines, Events);
    TestFalse("lunge running: not skippable", Stage.IsSkippable(900));
    TestFalse("skip refused during the lunge (clip not cut)", Stage.Skip(900, TEXT("click"), Cues, Lines, Events));
  }
  // ---- holds: the HUD shows the old HP until contact + 80, the board keeps a fallen figure until + 450 ----
  {
    FS09CombatStage Stage;
    FS08CueDispatcher Cues;
    TArray<FString> Lines;
    TArray<FS09CombatStageEvent> Events;
    FS09CombatStageInput In = BaseInput(false, 7);
    In.bLethal = true;
    In.HpAfter = 0;
    Stage.Start(In, 0, Cues, Lines, Events);
    TArray<FS08BoardFighter> Snapshot;
    FS08BoardFighter Medusa;
    Medusa.Id = TEXT("medusa");
    Medusa.Health = 0;
    Medusa.X = -1;
    Medusa.Y = -1;
    Medusa.bDefeated = true;
    Snapshot.Add(Medusa);
    TArray<FS08BoardFighter> Hud = Snapshot, Board = Snapshot;
    Stage.GetHold().Apply(Hud, false);
    Stage.GetHold().Apply(Board, true);
    TestTrue("HUD: still standing with 7 HP", Hud[0].Health == 7 && Hud[0].IsAlive());
    TestTrue("board: on its cell", Board[0].X == 3 && Board[0].Y == 4 && !Board[0].bDefeated);
    const int64 Contact = Stage.GetContactMs();
    for (int64 T = 0; T <= Contact + 80; ++T) Stage.Tick(T, Cues, Lines, Events);
    Hud = Snapshot;
    Board = Snapshot;
    Stage.GetHold().Apply(Hud, false);
    Stage.GetHold().Apply(Board, true);
    TestFalse("HUD: HP released at contact + 80", Hud[0].IsAlive());
    TestTrue("board: the figure stands until the fall", Board[0].IsAlive());
    for (int64 T = Contact + 81; T <= Contact + 450; ++T) Stage.Tick(T, Cues, Lines, Events);
    Board = Snapshot;
    Stage.GetHold().Apply(Board, true);
    TestFalse("board: released at contact + 450", Board[0].IsAlive());
  }
  // ---- ACC-012: a repeated seq never starts a second staging; a new combat cuts the running one ----
  {
    FS09CombatStage Stage;
    FS08CueDispatcher Cues;
    TArray<FString> Lines;
    TArray<FS09CombatStageEvent> Events;
    TestTrue("first start", Stage.Start(BaseInput(true, 2), 0, Cues, Lines, Events));
    const int32 LinesAfterStart = Lines.Num();
    TestFalse("same seq again: refused", Stage.Start(BaseInput(true, 2), 10, Cues, Lines, Events));
    TestEqual("refused start writes nothing", Lines.Num(), LinesAfterStart);
    FS09CombatStageInput Next = BaseInput(false, 1);
    Next.Seq = 35;
    TestTrue("next combat starts", Stage.Start(Next, 500, Cues, Lines, Events));
    bool bCut = false;
    for (const FString& L : Lines) bCut |= L.StartsWith(TEXT("CUE combat seq=31 stage=end")) && L.Contains(TEXT("cut=replace"));
    TestTrue("the running staging ended cut=replace", bCut);
    TestTrue("its HP was released", EventAt(Events, ES09CombatEvent::Hp) == 500);
  }
  // ---- a combat paused after its damage: the close shows no second blow ----
  {
    FRun Run;
    FS09CombatStageInput In = BaseInput(false, 2);
    In.bDamageShown = true;
    RunToEnd(Run, In);
    TestEqual("no HitReact", EventAt(Run.Events, ES09CombatEvent::HitReact), static_cast<int64>(-1));
    TestEqual("no -N", EventAt(Run.Events, ES09CombatEvent::Minus), static_cast<int64>(-1));
    TestFalse("no hold", Run.Stage.GetHold().IsSet());
    bool bCue011 = false;
    for (const FString& L : Run.Lines) bCue011 |= L.Contains(TEXT("id=CUE-011"));
    TestFalse("no CUE-011", bCue011);
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09CombatStageRevealTest, "Unmatched.S09.CombatStage.Reveal",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09CombatStageRevealTest::RunTest(const FString&) {
  using namespace S09CombatStageTest;
  const FString AttackerOwner = TEXT("cmuhntivg0000wib0anhqyswc");
  FS08Snapshot OpenAttacker, ResolveAttacker, ResolveDefender, DoneAttacker, DoneDefender;
  TestTrue("fixtures load",
           LoadS09Snapshot(TEXT("gd034-combat-open-attacker-view"), OpenAttacker) &&
               LoadS09Snapshot(TEXT("gd034-resolve-window-attacker-view"), ResolveAttacker) &&
               LoadS09Snapshot(TEXT("gd034-resolve-window-defender-view"), ResolveDefender) &&
               LoadS09Snapshot(TEXT("gd034-combat-done-attacker-view"), DoneAttacker) &&
               LoadS09Snapshot(TEXT("gd034-combat-done-defender-view"), DoneDefender));
  // Attacker seat: own card by id, the defense card from the defender pile's placeholder (hidden-4 -> Skirmish).
  {
    FS08CombatInfo Combat;
    TestTrue("attacker combatInfo", FS08Contracts::CombatInfo(ResolveAttacker, Combat));
    TestFalse("attacker seat: defense id hidden", Combat.bHasDefenderCard);
    const FS09CombatReveal R =
        FS09CombatReveal::Derive(Combat, AttackerOwner, ResolveAttacker.DiscardPiles, DoneAttacker.DiscardPiles);
    TestTrue("attack known", R.bAttackKnown && R.Attack.Name == TEXT("Regroup"));
    TestTrue("defense revealed by position", R.bDefenseKnown && R.Defense.Name == TEXT("Skirmish"));
    TestEqual("A 1 vs D 4", FString::Printf(TEXT("%d/%d"), R.AttackValue, R.DefenseValue), FString(TEXT("1/4")));
    TestFalse("not a no-defense combat", R.bNoDefense);
    TestFalse("no effect text on these cards", R.HasEffectText());
  }
  // Defender seat: the attack card from the attacker pile's placeholder, the own defense by id.
  {
    FS08CombatInfo Combat;
    TestTrue("defender combatInfo", FS08Contracts::CombatInfo(ResolveDefender, Combat));
    const FS09CombatReveal R =
        FS09CombatReveal::Derive(Combat, AttackerOwner, ResolveDefender.DiscardPiles, DoneDefender.DiscardPiles);
    TestTrue("attack revealed by position", R.bAttackKnown && R.Attack.Name == TEXT("Regroup"));
    TestTrue("own defense", R.bDefenseKnown && R.Defense.InstanceId == Combat.DefenderCardId);
    TestEqual("same score on both seats", FString::Printf(TEXT("%d/%d"), R.AttackValue, R.DefenseValue),
              FString(TEXT("1/4")));
  }
  // A combat closed straight from the defense window (no playDefense): the slot gets the cross.
  {
    FS08CombatInfo Combat;
    TestTrue("open combatInfo", FS08Contracts::CombatInfo(OpenAttacker, Combat));
    const FS09CombatReveal R =
        FS09CombatReveal::Derive(Combat, AttackerOwner, OpenAttacker.DiscardPiles, DoneAttacker.DiscardPiles);
    TestTrue("no defense", R.bNoDefense && !R.bDefenseKnown && R.DefenseValue == 0);
  }
  // Effect text: Text or effects[] on a revealed attack / defense card.
  {
    FS09CombatReveal R;
    R.bAttackKnown = true;
    R.Attack.Name = TEXT("Test");
    TestFalse("plain card", R.HasEffectText());
    R.Attack.EffectCount = 1;
    TestTrue("effects[] counts", R.HasEffectText());
    R.Attack.EffectCount = 0;
    R.bDefenseKnown = true;
    R.Defense.Text = TEXT("After combat: draw 1 card.");
    TestTrue("defense text counts", R.HasEffectText());
  }
  // The defense slot (SD-04).
  TestTrue("COMBAT, nothing picked: shield",
           S09DefenseSlotState(TEXT("COMBAT"), true, false, false) == ES09DefenseSlot::Shield);
  TestTrue("COMBAT, defender picked: card back",
           S09DefenseSlotState(TEXT("COMBAT"), true, true, false) == ES09DefenseSlot::CardBack);
  TestTrue("COMBAT, attacker never sees the pick",
           S09DefenseSlotState(TEXT("COMBAT"), false, true, false) == ES09DefenseSlot::Shield);
  TestTrue("COMBAT_RESOLVE: committed face down",
           S09DefenseSlotState(TEXT("COMBAT_RESOLVE"), false, false, false) == ES09DefenseSlot::CardBack);
  TestTrue("reveal without a card: cross",
           S09DefenseSlotState(TEXT("ACTION_MANEUVER"), false, false, true) == ES09DefenseSlot::NoDefense);
  TestEqual("slot names", FString(S09DefenseSlotName(ES09DefenseSlot::NoDefense)), FString(TEXT("no-defense")));
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
