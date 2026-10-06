// VS-1 HB-02 automation test of UI/S08HudDebug.h: which toasts are the debug layer (command echo, AUTO driver) and
// leave the player's view without -S09Markers; a refusal with its reason stays; an empty toast stays empty (not drawn).
//   node tools/s08/run-ue-tests.cjs Unmatched.S08.ArtLook <log>
#if WITH_AUTOMATION_TESTS

#include "S08HudDebug.h"
#include "../S08ArtLook.h"
#include "Misc/AutomationTest.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08HudDebugToastTest,
    "Unmatched.S08.ArtLook.DebugToast command echo and AUTO toasts are the debug layer, refusals stay for the player",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08HudDebugToastTest::RunTest(const FString&) {
  // the toasts of S08FlowGameMode.cpp that only echo a sent command, and the S09 auto driver (HD-01)
  const TCHAR* const Debug[] = {TEXT("begin maneuver sent (server draws 1 card)"), TEXT("end turn sent"),
                                TEXT("resolve sent"), TEXT("scheme sent"), TEXT("attack sent"), TEXT("defense sent"),
                                TEXT("choice sent"), TEXT("lobby return already sent"),
                                TEXT("AUTO maneuver: f-0-hero -> (3,4) (through the draft)"),
                                TEXT("AUTO maneuver: plan step (through the draft)")};
  // the player's: refusals with a reason, prompts, results
  const TCHAR* const Player[] = {TEXT("attack not sent - command gate blocked it (see trace)"),
                                 TEXT("choice not sent - command gate blocked it (see trace)"),
                                 TEXT("attack rejected: no target in range"), TEXT("attack draft closed (nothing was sent)"),
                                 TEXT("no defense - resolving"), TEXT("returning to the lobby"),
                                 TEXT("session expired - sign in again (F10 panel)"), TEXT("attack card Skirmish"),
                                 TEXT("AUTOMATIC"), TEXT("attack sent twice")};
  for (const TCHAR* T : Debug) {
    TestTrue(FString::Printf(TEXT("debug toast: '%s'"), T), S08HudDebug::IsDebugToast(T));
    TestEqual(FString::Printf(TEXT("hidden without -S09Markers: '%s'"), T), S08HudDebug::PlayerToast(T, false), FString());
    TestEqual(FString::Printf(TEXT("kept with -S09Markers: '%s'"), T), S08HudDebug::PlayerToast(T, true), FString(T));
  }
  for (const TCHAR* T : Player) {
    TestFalse(FString::Printf(TEXT("player toast: '%s'"), T), S08HudDebug::IsDebugToast(T));
    TestEqual(FString::Printf(TEXT("shown without -S09Markers: '%s'"), T), S08HudDebug::PlayerToast(T, false), FString(T));
  }
  TestEqual("an empty toast stays empty (not drawn)", S08HudDebug::PlayerToast(FString(), false), FString());
  // the run's layer: the test override stands in for -S09Markers
  S08ArtLook::SetMarkersOverrideForTest(false);
  TestEqual("run without the layer: the echo is hidden", S08HudDebug::PlayerToast(TEXT("attack sent")), FString());
  TestTrue("run without the layer: debug widgets collapsed", S08HudDebug::Visibility() == EVisibility::Collapsed);
  S08ArtLook::SetMarkersOverrideForTest(true);
  TestEqual("run with the layer: the echo is back", S08HudDebug::PlayerToast(TEXT("attack sent")), FString(TEXT("attack sent")));
  TestTrue("run with the layer: debug widgets visible", S08HudDebug::Visibility() == EVisibility::Visible);
  S08ArtLook::ResetMarkersOverrideForTest();
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
