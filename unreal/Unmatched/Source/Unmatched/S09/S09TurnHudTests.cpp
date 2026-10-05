// DE-023 (W-15 HUD; 01 F-07, F-12): the world-free turn HUD models (S09TurnHud.h).
//   Unmatched.S09.TurnHud.Cue     - the ring event at both sides, the banner 600 ms only on the own turn (reduced 100,
//                                   none on the first snapshot / reconnect, none after GAME_OVER), merges change nothing;
//   Unmatched.S09.TurnHud.Tracker - the own slot is marked at the choice (draft open / sent), given back on cancel, the
//                                   server marks take over, a refused or lost answer drops the latch, a new turn resets;
//   Unmatched.S09.TurnHud.Heart   - damage / deplete / heal of the shown hero HP, first sample and other hero silent.
#if WITH_AUTOMATION_TESTS

#include "S09TurnHud.h"
#include "Misc/AutomationTest.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09TurnHudCueTest, "Unmatched.S09.TurnHud.Cue",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FS09TurnHudCueTest::RunTest(const FString& Parameters) {
  FS09TurnCue Cue;
  // the first snapshot (join / reconnect mid-turn): the ring at rest, no banner
  FS09TurnCueEvent E = Cue.OnApplied(TEXT("me"), 3, TEXT("me"), false, 1000.0, false);
  TestTrue(TEXT("first: changed"), E.bChanged);
  TestTrue(TEXT("first: initial"), E.bInitial);
  TestTrue(TEXT("first: own"), E.bOwn);
  TestEqual(TEXT("first: no banner"), Cue.BannerLengthMs(), 0.0);
  TestFalse(TEXT("first: banner hidden"), Cue.IsBannerVisible(1050.0));
  // a merge of the same turn changes nothing
  E = Cue.OnApplied(TEXT("me"), 3, TEXT("me"), false, 1200.0, false);
  TestFalse(TEXT("same turn: no event"), E.bChanged);
  E = Cue.OnApplied(TEXT(""), 3, TEXT("me"), false, 1250.0, false);
  TestFalse(TEXT("no turn owner: no event"), E.bChanged);
  // the opponent's turn: the ring on their portrait, no banner (01 F-07: banner only on the own turn)
  E = Cue.OnApplied(TEXT("opp"), 3, TEXT("me"), false, 2000.0, false);
  TestTrue(TEXT("opp: changed"), E.bChanged);
  TestFalse(TEXT("opp: not initial"), E.bInitial);
  TestFalse(TEXT("opp: not own"), E.bOwn);
  TestTrue(TEXT("opp: opponent turn"), Cue.IsOpponentTurn());
  TestEqual(TEXT("opp: no banner"), Cue.BannerLengthMs(), 0.0);
  // my next turn: the banner 600 ms with a fade, never blocking anything (the model has no input gate at all)
  E = Cue.OnApplied(TEXT("me"), 4, TEXT("me"), false, 5000.0, false);
  TestTrue(TEXT("own: changed"), E.bChanged && E.bOwn && !E.bInitial);
  TestEqual(TEXT("own: banner 600 ms (CUE-015)"), Cue.BannerLengthMs(), FS09TurnCue::BannerMs);
  TestTrue(TEXT("frame 0 not empty"), Cue.BannerAlpha(5000.0) >= 0.15f - 1.0e-4f);
  TestEqual(TEXT("held at 300 ms"), Cue.BannerAlpha(5300.0), 1.0f);
  TestTrue(TEXT("fading at 550 ms"), Cue.BannerAlpha(5550.0) > 0.0f && Cue.BannerAlpha(5550.0) < 1.0f);
  TestFalse(TEXT("gone at 600 ms"), Cue.IsBannerVisible(5600.0));
  TestFalse(TEXT("gone later"), Cue.IsBannerVisible(9000.0));
  // reduced motion: 100 ms, static
  E = Cue.OnApplied(TEXT("opp"), 4, TEXT("me"), false, 10000.0, true);
  E = Cue.OnApplied(TEXT("me"), 5, TEXT("me"), false, 12000.0, true);
  TestEqual(TEXT("reduced: banner 100 ms"), Cue.BannerLengthMs(), FS09TurnCue::BannerReducedMs);
  TestEqual(TEXT("reduced: static"), Cue.BannerAlpha(12000.0), 1.0f);
  TestFalse(TEXT("reduced: gone at 100 ms"), Cue.IsBannerVisible(12100.0));
  // GAME_OVER: one event, the ring leaves, no banner; repeats are silent
  E = Cue.OnApplied(TEXT("me"), 5, TEXT("me"), true, 13000.0, false);
  TestTrue(TEXT("over: changed"), E.bChanged && E.bGameOver);
  TestEqual(TEXT("over: no banner"), Cue.BannerLengthMs(), 0.0);
  E = Cue.OnApplied(TEXT("me"), 5, TEXT("me"), true, 13100.0, false);
  TestFalse(TEXT("over again: no event"), E.bChanged);
  // a turn key also changes with the same player (a GAIN_ACTION does not; a new turn count does)
  FS09TurnCue Solo;
  Solo.OnApplied(TEXT("me"), 1, TEXT("me"), false, 0.0, false);
  E = Solo.OnApplied(TEXT("me"), 2, TEXT("me"), false, 100.0, false);
  TestTrue(TEXT("new turn count of the same player: a new turn with its banner"), E.bChanged && Solo.BannerLengthMs() > 0.0);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09TurnHudTrackerTest, "Unmatched.S09.TurnHud.Tracker",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FS09TurnHudTrackerTest::RunTest(const FString& Parameters) {
  FS09TrackerMarks Marks;
  Marks.OnApplied(TEXT("me#1"), 10, 0);
  TestEqual(TEXT("nothing chosen"), Marks.Shown(0, 2, false, 0.0), 0);
  // an attack draft opens: the slot is marked at the choice, before anything is sent
  TestEqual(TEXT("draft open -> marked"), Marks.Shown(0, 2, true, 10.0), 1);
  // cancelled (Esc): given back
  TestEqual(TEXT("draft cancelled -> back"), Marks.Shown(0, 2, false, 20.0), 0);
  // sent: the latch keeps it marked while the answer travels (the draft closed in the same frame)
  Marks.Choose(0, 10, 100.0);
  TestEqual(TEXT("sent -> still marked"), Marks.Shown(0, 2, false, 150.0), 1);
  // the answer: the server spent it - its mark takes over, no double count
  Marks.OnApplied(TEXT("me#1"), 11, 1);
  TestFalse(TEXT("answer -> latch dropped"), Marks.IsLatched(200.0));
  TestEqual(TEXT("answer -> server mark"), Marks.Shown(1, 2, false, 200.0), 1);
  // the second action: begin maneuver sent, refused - a newer seq without the spend drops the mark
  Marks.Choose(1, 11, 300.0);
  TestEqual(TEXT("second sent -> 2 marked"), Marks.Shown(1, 2, false, 310.0), 2);
  Marks.OnApplied(TEXT("me#1"), 12, 1);
  TestEqual(TEXT("refused -> back to 1"), Marks.Shown(1, 2, false, 320.0), 1);
  // a lost answer: the latch stops counting after the command deadline
  Marks.Choose(1, 12, 1000.0);
  TestEqual(TEXT("lost: marked before the deadline"), Marks.Shown(1, 2, false, 1000.0 + 9000.0), 2);
  TestEqual(TEXT("lost: back after the deadline"),
            Marks.Shown(1, 2, false, 1000.0 + FS09TrackerMarks::LatchTimeoutMs + 1.0), 1);
  // never more than the slots
  TestEqual(TEXT("clamped to the slots"), Marks.Shown(2, 2, true, 2000.0), 2);
  // a new turn resets every local mark in one frame
  Marks.Choose(1, 12, 3000.0);
  Marks.OnApplied(TEXT("opp#1"), 13, 0);
  TestFalse(TEXT("new turn -> no latch"), Marks.IsLatched(3001.0));
  TestEqual(TEXT("new turn -> server marks only"), Marks.Shown(0, 2, false, 3001.0), 0);
  // a merge of the same seq keeps an open latch (the answer is not there yet)
  Marks.OnApplied(TEXT("me#2"), 20, 0);
  Marks.Choose(0, 20, 4000.0);
  Marks.OnApplied(TEXT("me#2"), 20, 0);
  TestTrue(TEXT("same-seq merge keeps the latch"), Marks.IsLatched(4010.0));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09TurnHudHeartTest, "Unmatched.S09.TurnHud.Heart",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FS09TurnHudHeartTest::RunTest(const FString& Parameters) {
  FS09HeartWatch Heart;
  TestEqual(TEXT("first sample silent"), Heart.Sample(TEXT("arthur"), 16), ES09HeartEvent::None);
  TestEqual(TEXT("same HP silent"), Heart.Sample(TEXT("arthur"), 16), ES09HeartEvent::None);
  TestEqual(TEXT("hit -> damage"), Heart.Sample(TEXT("arthur"), 13), ES09HeartEvent::Damage);
  TestEqual(TEXT("heal"), Heart.Sample(TEXT("arthur"), 14), ES09HeartEvent::Heal);
  TestEqual(TEXT("lethal -> deplete"), Heart.Sample(TEXT("arthur"), 0), ES09HeartEvent::Deplete);
  TestEqual(TEXT("no hero -> nothing"), Heart.Sample(TEXT("arthur"), -1), ES09HeartEvent::None);
  TestEqual(TEXT("another hero: first sample silent"), Heart.Sample(TEXT("medusa"), 15), ES09HeartEvent::None);
  TestEqual(TEXT("anim names"), S09TurnHud::HeartAnim(ES09HeartEvent::Damage), FName(TEXT("damage")));
  TestTrue(TEXT("no anim for none"), S09TurnHud::HeartAnim(ES09HeartEvent::None).IsNone());
  TestEqual(TEXT("monogram two words"), S09TurnHud::Monogram(TEXT("King Arthur")), FString(TEXT("KA")));
  TestEqual(TEXT("monogram one word"), S09TurnHud::Monogram(TEXT("Medusa")), FString(TEXT("M")));
  TestEqual(TEXT("monogram empty"), S09TurnHud::Monogram(TEXT("")), FString(TEXT("?")));
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
