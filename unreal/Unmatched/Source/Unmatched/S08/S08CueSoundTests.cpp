// DE-032 automation tests: the world-free sound of the CUE sync points (S08CueSound.h, CUE-DISPATCHER.md §3.2):
//   Unmatched.S08.CueSound.Table   - the built-in sound rows ARE the sfx blocks of cue-table.json;
//   Unmatched.S08.CueSound.Points  - ui / hit / turn / result lines, the fallback without assets, the own-turn-only
//                                    chime, the D8 retrigger of CUE-004, a present asset plays;
//   Unmatched.S08.CueSound.Steps   - one step per edge from the move's start, one landing sound of a snapped move,
//                                    the drop on a skip / a replaced move;
//   Unmatched.S08.CueSound.Volumes - `CUE audio` lines and the gains: a change applies to the next sound (no restart);
//                                    AU-S4: every class has its bus volume (Music 60 / SFX 80 / UI 80 / VO 80).
#if WITH_AUTOMATION_TESTS

#include "S08CueSound.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace S08CueSoundTest {
TSharedPtr<FJsonObject> LoadTable() {
  const FString Path = FPaths::ConvertRelativePathToFull(FPaths::Combine(
      FPaths::ProjectDir(), TEXT("../../docs/unreal/contracts/cue-dispatcher/cue-table.json")));
  FString Text;
  TSharedPtr<FJsonObject> Object;
  if (!FFileHelper::LoadFileToString(Text, *Path)) return nullptr;
  const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Text);
  if (!FJsonSerializer::Deserialize(Reader, Object)) return nullptr;
  return Object;
}

FS08SoundRequest Request(ES08SoundPoint Point, const TCHAR* CueId, const TCHAR* Subject, int32 Seq, int64 EventMs) {
  FS08SoundRequest R;
  R.Point = Point;
  R.CueId = CueId;
  R.Subject = Subject;
  R.Seq = Seq;
  R.EventMs = EventMs;
  return R;
}
}  // namespace S08CueSoundTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08CueSoundTableTest, "Unmatched.S08.CueSound.Table",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08CueSoundTableTest::RunTest(const FString&) {
  using namespace S08CueSoundTest;
  const TSharedPtr<FJsonObject> Table = LoadTable();
  if (!TestTrue("cue-table.json loads", Table.IsValid())) return false;
  TMap<FString, TSharedPtr<FJsonObject>> ById;
  for (const TSharedPtr<FJsonValue>& Value : Table->GetArrayField(TEXT("cues"))) {
    const TSharedPtr<FJsonObject> Cue = Value->AsObject();
    ById.Add(Cue->GetStringField(TEXT("id")), Cue);
  }
  for (const FS08SoundRow& Row : S08SoundRows::All()) {
    const TSharedPtr<FJsonObject>* Cue = ById.Find(Row.CueId);
    if (!TestTrue(Row.CueId + TEXT(" in the table"), Cue != nullptr)) continue;
    const TSharedPtr<FJsonObject>* Sfx = nullptr;
    if (!TestTrue(Row.CueId + TEXT(" has an sfx block"), (*Cue)->TryGetObjectField(TEXT("sfx"), Sfx))) continue;
    TestEqual(Row.CueId + TEXT(" sound_class"), Row.SoundClass, (*Sfx)->GetStringField(TEXT("sound_class")));
    TestEqual(Row.CueId + TEXT(" priority"), Row.Priority, static_cast<int32>((*Sfx)->GetNumberField(TEXT("priority"))));
    const TSharedPtr<FJsonObject> Conc = (*Sfx)->GetObjectField(TEXT("concurrency"));
    TestEqual(Row.CueId + TEXT(" retrigger_ms"), Row.RetriggerMs,
              static_cast<int32>(Conc->GetNumberField(TEXT("retrigger_ms"))));
    FString Sound;
    const bool bHasSound = (*Sfx)->TryGetStringField(TEXT("sound"), Sound) && !Sound.IsEmpty();
    TestEqual(Row.CueId + TEXT(" sound path"), Row.SoundPath, bHasSound ? Sound : FString());
    FString Bank;
    (*Sfx)->TryGetStringField(TEXT("bank"), Bank);
    TestEqual(Row.CueId + TEXT(" bank"), Row.BankId, Bank);
    TestTrue(Row.CueId + TEXT(" bank id is in the sound bank"), S08AudioBank::Find(Row.BankId) != nullptr);
  }
  // AU-S4: every CUE with a sound (001 is silent by design: no hover sound on the board)
  TestEqual("seventeen sound rows (002-018)", S08SoundRows::All().Num(), 17);
  TestTrue("no row for CUE-001", S08SoundRows::Find(TEXT("CUE-001")) == nullptr);
  TestEqual("short name", S08SoundRows::ShortName(TEXT("/Game/Audio/UI/SW_Click.SW_Click")), FString(TEXT("SW_Click")));
  // the ui CUE of a board release
  TestEqual("refused", FString(S08SoundRows::BoardUiCue(true, true, true, true)), FString(TEXT("CUE-004")));
  TestEqual("command", FString(S08SoundRows::BoardUiCue(false, true, true, true)), FString(TEXT("CUE-003")));
  TestEqual("own pick", FString(S08SoundRows::BoardUiCue(false, false, true, true)), FString(TEXT("CUE-002")));
  TestEqual("cell pick", FString(S08SoundRows::BoardUiCue(false, false, false, true)), FString(TEXT("CUE-003")));
  TestTrue("no response, no sound", S08SoundRows::BoardUiCue(false, false, false, false) == nullptr);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08CueSoundPointsTest, "Unmatched.S08.CueSound.Points",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08CueSoundPointsTest::RunTest(const FString&) {
  using namespace S08CueSoundTest;
  FS08CueSound Sound;
  Sound.AssetResolver = [](const FString&) -> FString { return FString(); };  // no asset loads: fallback lines
  TArray<FString> Lines;
  Sound.SetAudio(FS08AudioSettings(), 0, true, Lines);
  TestEqual("start line", Lines.Last(),
            FString(TEXT("CUE audio master=100 master_mute=0 ambience=60 ambience_mute=0 gain_master=1.00 "
                         "gain_ambience=0.60 music=60 sfx=80 ui=80 vo=80 subtitles=1 t=0 applied=start")));
  Lines.Reset();
  // ui in the release frame, no asset: a fallback line, nothing to play
  FS08SoundDecision D = Sound.Play(Request(ES08SoundPoint::Ui, TEXT("CUE-003"), TEXT("hud.endturn"), 12, 1000), 1000,
                                   Lines);
  TestTrue("ui fallback", D.Result == ES08SoundResult::Fallback);
  TestTrue("ui is a UI sound", D.bUiSound);
  TestEqual("ui line", Lines.Last(),
            FString(TEXT("CUE sound id=CUE-003 point=ui subject=hud.endturn seq=12 t=1000 event_t=1000 dt=0 class=UI "
                         "sound=missing gain=0.80 result=fallback")));
  // CUE-004 at most once in 300 ms (D8)
  Sound.Play(Request(ES08SoundPoint::Ui, TEXT("CUE-004"), TEXT(""), 12, 1100), 1100, Lines);
  D = Sound.Play(Request(ES08SoundPoint::Ui, TEXT("CUE-004"), TEXT(""), 12, 1250), 1250, Lines);
  TestTrue("refusal throttled", D.Result == ES08SoundResult::Throttled);
  TestTrue("throttled line", Lines.Last().EndsWith(TEXT("sound=none gain=0.80 result=throttled")));
  D = Sound.Play(Request(ES08SoundPoint::Ui, TEXT("CUE-004"), TEXT(""), 12, 1400), 1400, Lines);
  TestTrue("refusal after 300 ms", D.Result == ES08SoundResult::Fallback);
  // hit in the contact frame: the staged contact boundary is its due
  FS08SoundRequest Hit = Request(ES08SoundPoint::Hit, TEXT("CUE-011"), TEXT("medusa"), 24, 2016);
  Hit.DueMs = 2000;
  Sound.Play(Hit, 2016, Lines);
  TestEqual("hit line", Lines.Last(),
            FString(TEXT("CUE sound id=CUE-011 point=hit subject=medusa seq=24 t=2016 event_t=2016 dt=0 class=SFX "
                         "sound=missing gain=0.80 result=fallback due=2000")));
  // the chime: own turn only; the opponent's turn start is silent
  FS08SoundRequest Turn = Request(ES08SoundPoint::Turn, TEXT("CUE-015"), TEXT(""), 30, 3000);
  Turn.bOwnTurn = false;
  D = Sound.Play(Turn, 3000, Lines);
  TestTrue("opponent turn silent", D.Result == ES08SoundResult::Silent);
  TestEqual("opponent turn line", Lines.Last(),
            FString(TEXT("CUE sound id=CUE-015 point=turn subject=- seq=30 t=3000 event_t=3000 dt=0 class=UI "
                         "sound=none gain=0.80 result=silent turn=opp reason=opponent")));
  Turn.bOwnTurn = true;
  Turn.Seq = 34;
  Turn.EventMs = 5000;
  D = Sound.Play(Turn, 5000, Lines);
  TestTrue("own turn chime (fallback)", D.Result == ES08SoundResult::Fallback);
  TestTrue("own turn line", Lines.Last().EndsWith(TEXT("result=fallback turn=own")));
  // the result sting with the screen (Music)
  Sound.Play(Request(ES08SoundPoint::Result, TEXT("CUE-016"), TEXT(""), 40, 9000), 9000, Lines);
  TestTrue("result line", Lines.Last().StartsWith(TEXT("CUE sound id=CUE-016 point=result subject=- seq=40 t=9000 "
                                                       "event_t=9000 dt=0 class=Music sound=missing")));
  // an unknown cue writes nothing
  const int32 Before = Lines.Num();
  D = Sound.Play(Request(ES08SoundPoint::Ui, TEXT("CUE-099"), TEXT(""), 1, 9100), 9100, Lines);
  TestTrue("unknown silent", D.Result == ES08SoundResult::Silent);
  TestEqual("unknown writes nothing", Lines.Num(), Before);
  // a present asset plays at the class gain (master is the device volume); the variant comes from the bank
  Sound.AssetResolver = [](const FString& Path) -> FString { return S08SoundRows::ShortName(Path); };
  D = Sound.Play(Request(ES08SoundPoint::Hit, TEXT("CUE-011"), TEXT("arthur"), 41, 9200), 9200, Lines);
  TestTrue("asset plays", D.Result == ES08SoundResult::Played);
  TestEqual("class gain of SFX", D.ClassGain, 0.8f);
  TestTrue("played line", Lines.Last().Contains(TEXT("sound=SW_CMB_HIT_BLADE_0")) &&
                              Lines.Last().Contains(TEXT("gain=0.80 result=played")));
  // a request may override the bank (the hit type of the attacker) - traced bank=
  FS08SoundRequest Arrow = Request(ES08SoundPoint::Hit, TEXT("CUE-011"), TEXT("arthur"), 42, 9300);
  Arrow.BankId = TEXT("CMB-HIT-ARROW");
  Sound.Play(Arrow, 9300, Lines);
  TestTrue("override bank", Lines.Last().Contains(TEXT("sound=SW_CMB_HIT_ARROW_0")) &&
                                Lines.Last().Contains(TEXT("bank=CMB-HIT-ARROW")));
  // a grouped hit of the same frame: silent, reason=grouped
  Sound.Grouped(Request(ES08SoundPoint::Hit, TEXT("CUE-011"), TEXT("merlin"), 42, 9300), 9300, Lines);
  TestTrue("grouped line", Lines.Last().EndsWith(TEXT("result=silent reason=grouped")));
  // the generic cue point
  Sound.Play(Request(ES08SoundPoint::Cue, TEXT("CUE-008"), TEXT("arthur"), 43, 9400), 9400, Lines);
  TestTrue("cue point line", Lines.Last().Contains(TEXT("point=cue")) &&
                                 Lines.Last().Contains(TEXT("sound=SW_CMB_ATTACK_DECLARE_0")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08CueSoundStepsTest, "Unmatched.S08.CueSound.Steps",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08CueSoundStepsTest::RunTest(const FString&) {
  FS08CueSound Sound;
  Sound.AssetResolver = [](const FString&) -> FString { return FString(); };  // no asset loads: fallback lines
  // a three-edge move from the seq start (280 ms per edge) and a second fighter's move starting 420 ms later
  Sound.ScheduleSteps(TEXT("arthur"), 20, 1000, 280.0, 3, false);
  Sound.ScheduleSteps(TEXT("merlin"), 20, 1420, 280.0, 1, false);
  TestEqual("four step sounds pending", Sound.PendingSteps(), 4);
  TArray<FS08StepSound> Due;
  Sound.TakeDueSteps(1000, Due);
  TestEqual("the first edge sounds in the start frame", Due.Num(), 1);
  if (Due.Num() == 1) {
    TestEqual("edge 0", Due[0].Edge, 0);
    TestEqual("due 1000", Due[0].DueMs, static_cast<int64>(1000));
  }
  Due.Reset();
  Sound.TakeDueSteps(1290, Due);  // 1280 is due; the frame lands 10 ms later
  TestEqual("second edge", Due.Num(), 1);
  if (Due.Num() == 1) TestEqual("due 1280", Due[0].DueMs, static_cast<int64>(1280));
  Due.Reset();
  Sound.TakeDueSteps(1600, Due);
  TestEqual("merlin's edge (1420) before arthur's third (1560)", Due.Num(), 2);
  if (Due.Num() == 2) {
    TestEqual("order merlin", Due[0].FighterId, FString(TEXT("merlin")));
    TestEqual("order arthur", Due[1].FighterId, FString(TEXT("arthur")));
    TestEqual("arthur edge 3 of 3", Due[1].Edge, 2);
  }
  TestEqual("all played", Sound.PendingSteps(), 0);
  // a snapped move: one landing sound at its start
  Sound.ScheduleSteps(TEXT("medusa"), 21, 2000, 0.0, 4, true);
  Due.Reset();
  Sound.TakeDueSteps(2000, Due);
  TestEqual("one landing sound", Due.Num(), 1);
  if (Due.Num() == 1) TestEqual("snap edge", Due[0].Edge, -1);
  // the trace of a step
  TArray<FString> Lines;
  Sound.SetAudio(FS08AudioSettings(), 0, true, Lines);
  FS08SoundRequest Step;
  Step.Point = ES08SoundPoint::Step;
  Step.CueId = TEXT("CUE-007");
  Step.Subject = TEXT("arthur");
  Step.Seq = 20;
  Step.EventMs = 1290;
  Step.Edge = 1;
  Step.Edges = 3;
  Step.DueMs = 1280;
  Sound.Play(Step, 1290, Lines);
  TestEqual("step line", Lines.Last(),
            FString(TEXT("CUE sound id=CUE-007 point=step subject=arthur seq=20 t=1290 event_t=1290 dt=0 class=SFX "
                         "sound=missing gain=0.80 result=fallback edge=2/3 due=1280")));
  // a skip drops every pending step (one line per seq); a replaced move drops only its fighter's
  Sound.ScheduleSteps(TEXT("arthur"), 22, 3000, 280.0, 3, false);
  Sound.ScheduleSteps(TEXT("merlin"), 22, 3000, 280.0, 2, false);
  Lines.Reset();
  TestEqual("replace drops arthur's three", Sound.DropSteps(3000, TEXT("replace"), Lines, TEXT("arthur")), 3);
  TestEqual("replace line", Lines.Last(),
            FString(TEXT("CUE sound drop point=step seq=22 fighter=arthur t=3000 count=3 reason=replace")));
  TestEqual("skip drops the rest", Sound.DropSteps(3100, TEXT("skip"), Lines), 2);
  TestEqual("skip line", Lines.Last(), FString(TEXT("CUE sound drop point=step seq=22 fighter=* t=3100 count=2 reason=skip")));
  TestEqual("nothing pending", Sound.PendingSteps(), 0);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08CueSoundVolumesTest, "Unmatched.S08.CueSound.Volumes",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08CueSoundVolumesTest::RunTest(const FString&) {
  using namespace S08CueSoundTest;
  FS08CueSound Sound;
  TArray<FString> Lines;
  FS08AudioSettings Audio;
  Audio.MasterPercent = 80;
  TestTrue("start applied", Sound.SetAudio(Audio, 0, true, Lines));
  TestFalse("the same values write nothing", Sound.SetAudio(Audio, 10, false, Lines));
  TestEqual("one line", Lines.Num(), 1);
  Sound.Play(Request(ES08SoundPoint::Ui, TEXT("CUE-003"), TEXT(""), 1, 100), 100, Lines);
  TestTrue("gain 0.64 (master 0.8 x UI 0.8)", Lines.Last().Contains(TEXT("gain=0.64")));
  TestEqual("ambience class gain without master", Sound.ClassGain(TEXT("Ambience")), 0.6f);
  TestEqual("ambience effective gain", Sound.EffectiveGain(TEXT("Ambience")), 0.8f * 0.6f);
  TestEqual("UI class gain", Sound.ClassGain(TEXT("UI")), 0.8f);
  TestEqual("Music class gain", Sound.ClassGain(TEXT("Music")), 0.6f);
  TestEqual("VO class gain", Sound.ClassGain(TEXT("VO")), 0.8f);
  // a saved change applies to the next sound, no restart
  Audio.MasterPercent = 50;
  Audio.bAmbienceMuted = true;
  TestTrue("change applied", Sound.SetAudio(Audio, 200, false, Lines));
  TestEqual("change line", Lines.Last(),
            FString(TEXT("CUE audio master=50 master_mute=0 ambience=60 ambience_mute=1 gain_master=0.50 "
                         "gain_ambience=0.00 music=60 sfx=80 ui=80 vo=80 subtitles=1 t=200 applied=change")));
  Sound.Play(Request(ES08SoundPoint::Hit, TEXT("CUE-011"), TEXT("medusa"), 2, 300), 300, Lines);
  TestTrue("gain 0.40 after the change (master 0.5 x SFX 0.8)", Lines.Last().Contains(TEXT("gain=0.40")));
  TestEqual("muted ambience", Sound.ClassGain(TEXT("Ambience")), 0.0f);
  // master muted: every point is silent (reason=muted), still traced
  Audio.bMasterMuted = true;
  Sound.SetAudio(Audio, 400, false, Lines);
  const FS08SoundDecision D = Sound.Play(Request(ES08SoundPoint::Result, TEXT("CUE-016"), TEXT(""), 3, 500), 500, Lines);
  TestTrue("muted silent", D.Result == ES08SoundResult::Silent);
  TestTrue("muted line", Lines.Last().EndsWith(TEXT("sound=none gain=0.00 result=silent reason=muted")));
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
