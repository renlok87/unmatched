// VS-6 F3 FX-30 automation tests: the staging of Medusa's gaze (S09AbilityStage.h) - the timeline of the card
// (contact t0+454, «−N» +60, HP +80, fall +450, CUE-014 800), the HP / figure hold, reduced motion, the repeat and the cut.
#include "S09AbilityStage.h"
#include "../S08/S08CueDispatcher.h"

#if WITH_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"

namespace {
FS09AbilityStageInput Gaze(int32 Seq, int32 HpBefore, bool bLethal, bool bReduced) {
  FS09AbilityStageInput In;
  In.Seq = Seq;
  In.FighterId = TEXT("f-0-hero");
  In.TargetId = TEXT("f-1-sk0");
  In.Damage = 1;
  In.HpBefore = HpBefore;
  In.HpAfter = HpBefore - 1;
  In.bLethal = bLethal;
  In.TargetX = 3;
  In.TargetY = 4;
  In.bReducedMotion = bReduced;
  return In;
}

int64 StageT(const TArray<FString>& Lines, const TCHAR* Stage) {
  for (const FString& L : Lines) {
    if (!L.StartsWith(TEXT("CUE ability ")) || !L.Contains(FString::Printf(TEXT(" stage=%s "), Stage))) continue;
    int32 At = L.Find(TEXT(" t="));
    return At >= 0 ? FCString::Atoi64(*L.Mid(At + 3)) : -1;
  }
  return -1;
}

bool HasEvent(const TArray<FS09AbilityStageEvent>& Events, ES09AbilityEvent Type, int64 AtMs) {
  return Events.ContainsByPredicate([Type, AtMs](const FS09AbilityStageEvent& E) { return E.Type == Type && E.AtMs == AtMs; });
}
}  // namespace

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09AbilityStageTimelineTest,
    "Unmatched.S09.AbilityStage.Timeline Medusa's gaze: vortex t0, contact +454, minus +60, hp +80, fall +450, CUE-014 800 (FX-30)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09AbilityStageTimelineTest::RunTest(const FString&) {
  {
    FS08CueDispatcher Cues;
    FS09AbilityStage Stage;
    TArray<FString> Lines;
    TArray<FS09AbilityStageEvent> Events;
    TestTrue("starts", Stage.Start(Gaze(40, 6, false, false), 1000, Cues, Lines, Events));
    TestTrue("start line", Lines.ContainsByPredicate([](const FString& L) {
      return L == TEXT("CUE ability seq=40 stage=start t=1000 hero=medusa fighter=f-0-hero target=f-1-sk0 damage=1 "
                       "lethal=0 reduced=0");
    }));
    TestTrue("CUE-014 on Medusa at t0", Lines.ContainsByPredicate([](const FString& L) {
      return L.StartsWith(TEXT("CUE fx id=CUE-014 subject=f-0-hero seq=40 t=1000 "));
    }));
    TestTrue("vortex at t0", HasEvent(Events, ES09AbilityEvent::Vortex, 1000));
    TestTrue("HP held", Stage.GetHold().bHpHeld && Stage.GetHold().HeldHealth == 6 && !Stage.GetHold().bAliveHeld);
    TestTrue("owns the target's damage of its seq", Stage.HoldsDamage(TEXT("f-1-sk0"), 40) &&
                                                         !Stage.HoldsDamage(TEXT("f-1-sk0"), 41));
    Stage.Tick(1453, Cues, Lines, Events);
    TestEqual("no contact before 454", StageT(Lines, TEXT("contact")), static_cast<int64>(-1));
    Stage.Tick(1533, Cues, Lines, Events);
    TestEqual("contact t0+454", StageT(Lines, TEXT("contact")), static_cast<int64>(1454));
    TestEqual("minus +60", StageT(Lines, TEXT("minus")), static_cast<int64>(1514));
    TestTrue("still held before +80", Stage.GetHold().bHpHeld);
    TestTrue("CUE-011 of the target staged at contact", Lines.ContainsByPredicate([](const FString& L) {
      return L.StartsWith(TEXT("CUE fx id=CUE-011 subject=f-1-sk0 seq=40 t=1454 "));
    }));
    Stage.Tick(1534, Cues, Lines, Events);
    TestEqual("hp +80", StageT(Lines, TEXT("hp")), static_cast<int64>(1534));
    TestFalse("HP released", Stage.GetHold().bHpHeld);
    TestTrue("contact / minus / hp events", HasEvent(Events, ES09AbilityEvent::Contact, 1454) &&
                                                HasEvent(Events, ES09AbilityEvent::Minus, 1514) &&
                                                HasEvent(Events, ES09AbilityEvent::Hp, 1534));
    Stage.Tick(1800, Cues, Lines, Events);
    TestEqual("end = t0 + 800 (CUE-014)", StageT(Lines, TEXT("end")), static_cast<int64>(1800));
    TestEqual("no fall", StageT(Lines, TEXT("fall")), static_cast<int64>(-1));
    TestFalse("over", Stage.IsActive());
    TestFalse("the same seq never stages twice (ACC-012)", Stage.Start(Gaze(40, 6, false, false), 2000, Cues, Lines, Events));
  }
  {  // lethal: the figure stands until contact + 450, the end waits for the fall
    FS08CueDispatcher Cues;
    FS09AbilityStage Stage;
    TArray<FString> Lines;
    TArray<FS09AbilityStageEvent> Events;
    Stage.Start(Gaze(50, 1, true, false), 0, Cues, Lines, Events);
    TestTrue("alive held", Stage.GetHold().bAliveHeld && Stage.GetHold().HeldX == 3 && Stage.GetHold().HeldY == 4);
    Stage.Tick(903, Cues, Lines, Events);
    TestTrue("still standing at +903", Stage.GetHold().bAliveHeld);
    Stage.Tick(904, Cues, Lines, Events);
    TestEqual("fall = contact + 450", StageT(Lines, TEXT("fall")), static_cast<int64>(904));
    TestEqual("end with the fall", StageT(Lines, TEXT("end")), static_cast<int64>(904));
    TestTrue("fall event", HasEvent(Events, ES09AbilityEvent::Fall, 904));
  }
  {  // reduced motion: no vortex, the hit at t0 + 100, CUE-014 shortened
    FS08CueDispatcher Cues;
    TArray<FString> Lines;
    Cues.SetReducedMotion(true, 0, Lines);
    FS09AbilityStage Stage;
    TArray<FS09AbilityStageEvent> Events;
    Stage.Start(Gaze(60, 5, false, true), 0, Cues, Lines, Events);
    TestFalse("no vortex", Events.ContainsByPredicate([](const FS09AbilityStageEvent& E) {
      return E.Type == ES09AbilityEvent::Vortex;
    }));
    Stage.Tick(1000, Cues, Lines, Events);
    TestEqual("reduced contact t0+100", StageT(Lines, TEXT("contact")), static_cast<int64>(100));
    TestEqual("reduced end = contact + 80", StageT(Lines, TEXT("end")), static_cast<int64>(180));
  }
  {  // a new gaze cuts the running one: the HP goes at once, cut=replace
    FS08CueDispatcher Cues;
    FS09AbilityStage Stage;
    TArray<FString> Lines;
    TArray<FS09AbilityStageEvent> Events;
    Stage.Start(Gaze(70, 6, false, false), 0, Cues, Lines, Events);
    Stage.Start(Gaze(71, 5, false, false), 200, Cues, Lines, Events);
    TestTrue("cut line", Lines.ContainsByPredicate([](const FString& L) {
      return L == TEXT("CUE ability seq=70 stage=end t=200 hero=medusa target=f-1-sk0 cut=replace");
    }));
    TestTrue("hp released by the cut", HasEvent(Events, ES09AbilityEvent::Hp, 200));
    TestTrue("the new one runs", Stage.IsActive() && Stage.GetSeq() == 71);
  }
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
