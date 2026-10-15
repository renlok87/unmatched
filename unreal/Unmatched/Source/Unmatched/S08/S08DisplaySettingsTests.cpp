#if WITH_AUTOMATION_TESTS

#include "S08DisplaySettings.h"
#include "Misc/AutomationTest.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08DisplaySettingsTest, "Unmatched.S08.Display.Settings",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08DisplaySettingsTest::RunTest(const FString&) {
  const TArray<FIntPoint> Hd = S08Display::ResolutionOptions({1920, 1080}, {1920, 1080});
  TestTrue(TEXT("1080p has 720p and 1080p choices"), Hd.Contains(FIntPoint(1280, 720)) && Hd.Contains(FIntPoint(1920, 1080)));
  TestFalse(TEXT("does not offer a resolution larger than the display"), Hd.Contains(FIntPoint(3840, 2160)));
  TestEqual(TEXT("native resolution occurs once"), Hd.FilterByPredicate([](FIntPoint R) { return R == FIntPoint(1920, 1080); }).Num(), 1);
  const TArray<FIntPoint> Wide = S08Display::ResolutionOptions({5120, 1440}, {1736, 984});
  TestTrue(TEXT("ultrawide native, 1440p and a resized window remain selectable"),
           Wide.Contains(FIntPoint(5120, 1440)) && Wide.Contains(FIntPoint(2560, 1440)) && Wide.Contains(FIntPoint(1736, 984)));
  FS08DisplaySettings Current, Next;
  Current.Desktop = {5120, 1440};
  Current.Resolution = Current.Desktop;
  Current.Resolutions = {Current.Desktop};
  FString Error;
  TestTrue(TEXT("borderless to windowed"), S08Display::Resolve(Current, TEXT("windowMode"), TEXT("2"), Next, Error));
  TestTrue(TEXT("window fits including its title bar"), Next.WindowMode == 2 && Next.Resolution == FIntPoint(1920, 1080));
  Current = Next;
  Current.Resolutions = S08Display::ResolutionOptions(Current.Desktop, Current.Resolution);
  TestTrue(TEXT("select 1440p"), S08Display::Resolve(Current, TEXT("resolution"), TEXT("2560x1440"), Next, Error));
  TestEqual(TEXT("selected resolution"), Next.Resolution, FIntPoint(2560, 1440));
  TestTrue(TEXT("borderless returns to desktop resolution"),
           S08Display::Resolve(Current, TEXT("windowMode"), TEXT("1"), Next, Error) && Next.Resolution == Current.Desktop);
  const FIntPoint Before = Next.Resolution;
  TestFalse(TEXT("invalid resolution refused"), S08Display::Resolve(Current, TEXT("resolution"), TEXT("99999x1"), Next, Error));
  TestEqual(TEXT("invalid choice leaves output unchanged"), Next.Resolution, Before);
  TestFalse(TEXT("malformed mode refused"), S08Display::Resolve(Current, TEXT("windowMode"), TEXT("2junk"), Next, Error));
  TestFalse(TEXT("unrelated setting refused"), S08Display::Resolve(Current, TEXT("graphics"), TEXT("0"), Next, Error));
  return true;
}
#endif
