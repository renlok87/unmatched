// AU-S4 automation tests (docs/game-design/audio/02-audio-design.md), world-free:
//   Unmatched.S08.Audio.Bank      - the generated bank: every registry group present, VO lines with subtitles, the
//                                   character keys and hit types, the bag plays every variant before a repeat;
//   Unmatched.S08.Audio.Music     - states and gains: intro, combat (L2 in 400 ms, out 2.5 s after the 4 s tail), final
//                                   stand once, hero fallen, the result sting per hero / outcome, ducks;
//   Unmatched.S08.Audio.Vo        - one voice, priorities and interrupt, the 3 s gap, cooldowns, once-per-match,
//                                   harpy pitch versions, no repeat;
//   Unmatched.S08.Audio.Ambience  - plans per map, the spot schedule (seeded), followers, the map key of a board;
//   Unmatched.S08.Audio.Settings  - the bus volumes and the subtitle switches (console names, gains, defaults).
#if WITH_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "S08Ambience.h"
#include "S08AudioBank.h"
#include "S08MusicDirector.h"
#include "S08UserSettings.h"
#include "S08VoDirector.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08AudioBankTest, "Unmatched.S08.Audio.Bank",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08AudioBankTest::RunTest(const FString&) {
  for (const TCHAR* Id : {TEXT("UI-SELECT"), TEXT("UI-TURN-CHIME"), TEXT("CRD-DRAW"), TEXT("BRD-STEP"),
                          TEXT("CMB-HIT-BLADE"), TEXT("CMB-HIT-CLAW"), TEXT("CMB-HIT-ARROW"), TEXT("CMB-HIT-MAGIC"),
                          TEXT("CMB-BLOCK-SHIELD"), TEXT("DTH-ARTHUR"), TEXT("DTH-MEDUSA"), TEXT("FX-PETRIFY"),
                          TEXT("MUS-MENU-L1"), TEXT("MUS-MAP-MARMOREAL-L2"), TEXT("MUS-MAP-SARPEDON-L1"),
                          TEXT("STG-MATCH-START"), TEXT("STG-WIN-ARTHUR"), TEXT("STG-LOSE-MEDUSA"), TEXT("STG-ABORTED"),
                          TEXT("AMB-MARMOREAL-BED"), TEXT("AMB-SARPEDON-FALLS"), TEXT("VO-ARTHUR-ATTACK"),
                          TEXT("VO-HARPY-ATTACK-H2")}) {
    const TArray<FString>* V = S08AudioBank::Find(Id);
    TestTrue(FString(Id) + TEXT(" in the bank"), V && V->Num() > 0);
    if (V && V->Num()) TestTrue(FString(Id) + TEXT(" soft path"), (*V)[0].StartsWith(TEXT("/Game/Audio/")));
  }
  TestEqual("five step variants", S08AudioBank::Find(TEXT("BRD-STEP")) ? S08AudioBank::Find(TEXT("BRD-STEP"))->Num() : 0,
            5);
  TestEqual("101 VO lines (04-vo-script)", S08AudioBank::VoLines().Num(), 101);
  const FS08VoLine* L = S08AudioBank::FindVoLine(TEXT("ARTHUR-ATTACK-02"));
  TestTrue("a line with EN and RU", L && L->En == TEXT("For Camelot!") && !L->Ru.IsEmpty());
  const FS08VoLine* Effort = S08AudioBank::FindVoLine(TEXT("MEDUSA-HURT-01"));
  TestTrue("an effort has no subtitle", Effort && Effort->En.IsEmpty() && Effort->Ru.IsEmpty());
  TestEqual("character key", S08AudioBank::CharacterKey(TEXT("King Arthur")), FString(TEXT("ARTHUR")));
  TestEqual("harpy key", S08AudioBank::CharacterKey(TEXT("Harpies 2")), FString(TEXT("HARPY")));
  TestEqual("unknown hero", S08AudioBank::CharacterKey(TEXT("Robin Hood")), FString());
  TestEqual("medusa shoots", S08AudioBank::HitType(TEXT("MEDUSA")), FString(TEXT("ARROW")));
  TestEqual("unknown blunt", S08AudioBank::HitType(FString()), FString(TEXT("BLUNT")));
  // the bag: all variants once per round, no repeat across rounds
  FS08SoundBag Bag;
  FRandomStream Rng(7);
  const TArray<FString> V = {TEXT("a"), TEXT("b"), TEXT("c"), TEXT("d")};
  FString Prev;
  for (int32 Round = 0; Round < 25; ++Round) {
    TSet<FString> Seen;
    for (int32 I = 0; I < V.Num(); ++I) {
      const FString P = Bag.Pick(TEXT("k"), V, Rng);
      TestFalse("no immediate repeat", P == Prev);
      Prev = P;
      Seen.Add(P);
    }
    TestEqual("a round plays every variant", Seen.Num(), V.Num());
  }
  TestEqual("one variant", Bag.Pick(TEXT("one"), {TEXT("x")}, Rng), FString(TEXT("x")));
  TestEqual("no variant", Bag.Pick(TEXT("none"), {}, Rng), FString());
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08AudioMusicTest, "Unmatched.S08.Audio.Music",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08AudioMusicTest::RunTest(const FString&) {
  FS08MusicDirector M;
  TArray<FString> Lines;
  M.StartMatch(TEXT("MARMOREAL"), 1000, Lines);
  TestEqual("intro line", Lines.Last(),
            FString(TEXT("MUSIC state=intro theme=MUS-MAP-MARMOREAL t=1000 sting=STG-MATCH-START")));
  TArray<FString> Stings = M.TakeStings();
  TestTrue("match-start sting", Stings.Num() == 1 && Stings[0] == TEXT("STG-MATCH-START"));
  FS08MusicMix Mix = M.Mix(1000);
  TestTrue("theme starts", Mix.bThemeChanged && Mix.Theme == TEXT("MUS-MAP-MARMOREAL"));
  TestFalse("only once", M.Mix(1001).bThemeChanged);
  Mix = M.Mix(6000);
  TestTrue("L1 up after the intro (no duck)", FMath::IsNearlyEqual(Mix.L1, 1.0f, 0.01f));
  TestTrue("L2 off", Mix.L2 < 0.01f);
  TestTrue("maneuver", M.GetState() == ES08MusicState::Maneuver);
  M.CombatBegin(7000, Lines);
  TestTrue("combat state", M.GetState() == ES08MusicState::Combat);
  Mix = M.Mix(7400);
  TestTrue("L2 in after 400 ms (+4 dB)", FMath::IsNearlyEqual(Mix.L2, FMath::Pow(10.0f, 0.2f), 0.02f));
  M.CombatEnd(9000, Lines);
  TestTrue("L2 held during the tail", M.Mix(12000).L2 > 1.0f);
  M.Mix(13000);  // tail over: the ramp out starts
  TestTrue("L2 out 2.5 s later", M.Mix(15600).L2 < 0.01f);
  // final stand once: L2 rests at -8 dB
  M.HeroHp(4, 18, 16000, Lines);
  TestTrue("final stand", M.IsFinalStand() && Lines.Last().Contains(TEXT("state=final_stand")));
  const int32 Before = Lines.Num();
  M.HeroHp(3, 18, 16100, Lines);
  TestEqual("once", Lines.Num(), Before);
  TestTrue("L2 at -8 dB", FMath::IsNearlyEqual(M.Mix(20000).L2, FMath::Pow(10.0f, -0.4f), 0.02f));
  // VO ducks -6 dB
  M.SetVoActive(true, 20000);
  TestTrue("VO duck", FMath::IsNearlyEqual(M.Mix(20000).L1, 0.5f, 0.02f));
  M.SetVoActive(false, 20100);
  // hero fallen: both layers leave in 1.2 s
  M.HeroFallen(21000, Lines);
  TestTrue("fallen", M.Mix(22300).L1 < 0.01f && M.Mix(22300).L2 < 0.01f);
  // the result: the own hero's sting, then the quiet menu theme after the gap
  TestEqual("win sting", M.Result(ES08MatchOutcome::Win, TEXT("ARTHUR"), 23000, Lines), FString(TEXT("STG-WIN-ARTHUR")));
  TestTrue("result sting queued", M.TakeStings().Contains(TEXT("STG-WIN-ARTHUR")));
  Mix = M.Mix(30000);
  TestTrue("menu theme after the result", Mix.bThemeChanged && Mix.Theme == TEXT("MUS-MENU"));
  FS08MusicDirector N;
  TestEqual("lose sting", N.Result(ES08MatchOutcome::Lose, TEXT("MEDUSA"), 0, Lines), FString(TEXT("STG-LOSE-MEDUSA")));
  TestEqual("fallback sting", N.Result(ES08MatchOutcome::Win, TEXT("ROBIN"), 0, Lines), FString(TEXT("STG-WIN")));
  TestEqual("aborted", N.Result(ES08MatchOutcome::Aborted, TEXT("ARTHUR"), 0, Lines), FString(TEXT("STG-ABORTED")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08AudioVoTest, "Unmatched.S08.Audio.Vo",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08AudioVoTest::RunTest(const FString&) {
  FS08VoDirector Vo(1);
  TArray<FString> Lines;
  auto Offer = [&](const TCHAR* Event, const TCHAR* Speaker, int64 T, bool bAnswer = false) {
    FS08VoOffer O;
    O.Event = Event;
    O.Speaker = Speaker;
    O.TMs = T;
    O.bAnswer = bAnswer;
    return Vo.Offer(O, Lines);
  };
  FS08VoDecision D = Offer(TEXT("MATCH-START"), TEXT("ARTHUR"), 1000);
  TestTrue("match start plays", D.bPlay && D.LineId.StartsWith(TEXT("ARTHUR-MATCH-START-")) && !D.En.IsEmpty());
  TestTrue("trace", Lines.Last().StartsWith(TEXT("VO event=MATCH-START speaker=ARTHUR t=1000 result=played")));
  Vo.Started(1000, 2000);
  D = Offer(TEXT("HURT"), TEXT("MEDUSA"), 1500);
  TestTrue("busy: an equal or lower priority is dropped", !D.bPlay && D.Reason == TEXT("busy"));
  D = Offer(TEXT("DEATH"), TEXT("MEDUSA"), 1600);
  TestTrue("priority 1 interrupts", D.bPlay && D.bInterrupt);
  Vo.Started(1600, 800);
  Vo.Finished(2400);
  D = Offer(TEXT("CARD-EXCALIBUR"), TEXT("ARTHUR"), 3000);
  TestTrue("the 3 s gap", !D.bPlay && D.Reason == TEXT("gap"));
  D = Offer(TEXT("LOW-HP"), TEXT("ARTHUR"), 5000);
  TestTrue("low HP plays", D.bPlay);
  Vo.Finished(6000);
  D = Offer(TEXT("LOW-HP"), TEXT("ARTHUR"), 20000);
  TestTrue("once per match", !D.bPlay && D.Reason == TEXT("once"));
  // cooldowns and no repeat: hurt-big has a 10 s cooldown, two lines alternate
  D = Offer(TEXT("HURT-BIG"), TEXT("MEDUSA"), 30000);
  const FString First = D.LineId;
  Vo.Finished(31000);
  D = Offer(TEXT("HURT-BIG"), TEXT("MEDUSA"), 35000);
  TestTrue("cooldown", !D.bPlay && D.Reason == TEXT("cooldown"));
  D = Offer(TEXT("HURT-BIG"), TEXT("MEDUSA"), 41000);
  TestTrue("the other line next", D.bPlay && D.LineId != First);
  Vo.Finished(42000);
  // harpies: the pitch version of the harpy
  FS08VoOffer H;
  H.Event = TEXT("DEATH");
  H.Speaker = TEXT("HARPY");
  H.HarpyIndex = 3;
  H.TMs = 50000;
  D = Vo.Offer(H, Lines);
  TestTrue("harpy 3 cry", D.bPlay && D.Path.Contains(TEXT("_H3")) && D.En.IsEmpty());
  Vo.Finished(51000);
  // an unknown speaker (a hero without VO) stays silent
  D = Offer(TEXT("ATTACK"), TEXT("ROBIN"), 60000);
  TestTrue("no lines", !D.bPlay);
  // rules
  TestEqual("attack chance", FS08VoDirector::RuleFor(TEXT("ARTHUR"), TEXT("ATTACK")).Chance, 0.5f);
  TestEqual("medusa ability chance", FS08VoDirector::RuleFor(TEXT("MEDUSA"), TEXT("ABILITY")).Chance, 0.7f);
  TestEqual("death priority", FS08VoDirector::RuleFor(TEXT("MERLIN"), TEXT("DEATH")).Priority, 1);
  TestEqual("idle priority", FS08VoDirector::RuleFor(TEXT("ARTHUR"), TEXT("IDLE")).Priority, 5);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08AudioAmbienceTest, "Unmatched.S08.Audio.Ambience",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08AudioAmbienceTest::RunTest(const FString&) {
  TestEqual("marmoreal by profile", S08Ambience::MapKeyOf(TEXT("marmoreal-original")), FString(TEXT("MARMOREAL")));
  TestEqual("sarpedon by board id", S08Ambience::MapKeyOf(TEXT("c7fa64a26c29a0835f2383e63")), FString(TEXT("SARPEDON")));
  TestEqual("a synthetic board has none", S08Ambience::MapKeyOf(TEXT("cobble-5x6")), FString());
  const FS08AmbPlan Sarp = S08Ambience::PlanFor(TEXT("SARPEDON"));
  TestEqual("sarpedon beds", Sarp.Beds.Num(), 5);
  TestFalse("no cannon shots", Sarp.Spots.ContainsByPredicate([](const FS08AmbSpot& S) {
    return S.BankId.Contains(TEXT("CANNON"));
  }));
  TestEqual("empty plan", S08Ambience::PlanFor(TEXT("COBBLE")).Beds.Num(), 0);
  FS08AmbienceScheduler A(3);
  TArray<FString> Lines;
  A.Start(S08Ambience::PlanFor(TEXT("MARMOREAL")), 0, Lines);
  TestEqual("start line", Lines.Last(), FString(TEXT("AMB map=MARMOREAL beds=1 spots=4 t=0")));
  int32 Gusts = 0, Petals = 0, Total = 0;
  for (int64 T = 0; T <= 600000; T += 100) {
    for (const FString& Id : A.TakeDue(T, Lines)) {
      ++Total;
      Gusts += Id == TEXT("AMB-MARMOREAL-GUST");
      Petals += Id == TEXT("AMB-MARMOREAL-PETALS");
    }
  }
  TestTrue("gusts every 15-40 s over 10 min", Gusts >= 15 && Gusts <= 40);
  TestTrue("petals follow some gusts", Petals > 0 && Petals <= Gusts);
  TestTrue("spots are sparse (< 1 per 6 s)", Total < 100);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08AudioSettingsTest, "Unmatched.S08.Audio.Settings",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08AudioSettingsTest::RunTest(const FString&) {
  FS08AudioSettings A;
  TestEqual("music default 60", A.BusGain(TEXT("Music")), 0.6f);
  TestEqual("sfx default 80", A.BusGain(TEXT("SFX")), 0.8f);
  TestEqual("ui default 80", A.BusGain(TEXT("UI")), 0.8f);
  TestEqual("vo default 80", A.BusGain(TEXT("VO")), 0.8f);
  TestEqual("ambience default 60", A.BusGain(TEXT("Ambience")), 0.6f);
  TestTrue("subtitles on by default", A.bSubtitles);
  TestFalse("describe sounds off by default", A.bDescribeSounds);
  US08UserSettings* S = NewObject<US08UserSettings>();
  FString Error;
  TestTrue("music=35", S->ApplySetting(TEXT("music"), TEXT("35"), Error));
  TestTrue("vo=0", S->ApplySetting(TEXT("vo"), TEXT("0"), Error));
  TestTrue("subtitles=0", S->ApplySetting(TEXT("subtitles"), TEXT("0"), Error));
  TestFalse("sfx=150 refused", S->ApplySetting(TEXT("sfx"), TEXT("150"), Error));
  const FS08AudioSettings Saved = S->GetSavedAudio();
  TestEqual("music stored", Saved.MusicPercent, 35);
  TestEqual("vo stored", Saved.VoPercent, 0);
  TestFalse("subtitles stored", Saved.bSubtitles);
  TestTrue("describe has the buses", S->Describe().Contains(TEXT("music=35 sfx=80 ui=80 vo=0 subtitles=0")));
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
