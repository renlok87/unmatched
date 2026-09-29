// W4-C hybrid HUD automation tests (user decision 2026-09-28): style tokens
// and the pixel-gate color rule, the art HUD string table, the -ArtHudImpl
// flag, the UMG widget classes (code default tree and the WBP children) and
// the layout parity UMG = Slate within 1 px for every traced plate part.
// Headless run (art worktree):
//   UnrealEditor-Cmd.exe Unmatched.uproject
//     -ExecCmds="Automation RunTests Unmatched.S08.ArtHudUmg; Quit" -unattended -nosplash -nullrhi
#if WITH_AUTOMATION_TESTS

#include "S08ArtHud.h"
#include "S08ArtHudStyle.h"
#include "S08ArtHudText.h"
#include "S08ArtHudViews.h"
#include "S08ArtHudWidgets.h"
#include "Blueprint/UserWidget.h"
#include "Components/Border.h"
#include "Components/SizeBox.h"
#include "Components/TextBlock.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Internationalization/Regex.h"
#include "Layout/ArrangedChildren.h"
#include "Misc/AutomationTest.h"
#include "Widgets/SWidget.h"

namespace {
struct FS08TestWorld {
  UWorld* World = nullptr;
  explicit FS08TestWorld(const TCHAR* Name) {
    World = UWorld::CreateWorld(EWorldType::Game, false, FName(Name));
    if (World) GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
  }
  ~FS08TestWorld() {
    if (!World) return;
    GEngine->DestroyWorldContext(World);
    World->DestroyWorld(false);
  }
};

// Arranged absolute rects (in root space) of every widget under Root.
void S08Walk(const TSharedRef<SWidget>& Widget, const FGeometry& Geometry, TMap<const SWidget*, FSlateRect>& Out) {
  const FVector2D Pos = Geometry.GetAbsolutePosition();
  const FVector2D Size = Geometry.GetAbsoluteSize();
  Out.Add(&Widget.Get(), FSlateRect(Pos.X, Pos.Y, Pos.X + Size.X, Pos.Y + Size.Y));
  FArrangedChildren Arranged(EVisibility::All);
  Widget->ArrangeChildren(Geometry, Arranged);
  for (const FArrangedWidget& Child : Arranged.GetInternalArray()) S08Walk(Child.Widget, Child.Geometry, Out);
}

TMap<FString, FSlateRect> S08Layout(const TSharedRef<SWidget>& Root, const TArray<FS08WidgetPart>& Parts,
                                    const FVector2D& SizeSu, float Scale) {
  Root->SlatePrepass(Scale);
  TMap<const SWidget*, FSlateRect> Rects;
  S08Walk(Root, FGeometry::MakeRoot(SizeSu, FSlateLayoutTransform(Scale)), Rects);
  TMap<FString, FSlateRect> Out;
  for (const FS08WidgetPart& Part : Parts) {
    if (const FSlateRect* R = Part.Widget.IsValid() ? Rects.Find(Part.Widget.Get()) : nullptr) Out.Add(Part.Id, *R);
  }
  return Out;
}

FS08PlateTexts S08SampleTexts(bool bOwn) {
  return S08ArtHudText::PlateTexts(TEXT("Medusa"), 7, 16, bOwn,
                                   S08PlateStatuses(true, bOwn, TEXT("ranged"), bOwn, !bOwn, {TEXT("stunned")}));
}

// Compares the arranged part rects of a UMG plate against the Slate plate;
// returns the largest edge difference in px.
float S08ComparePlate(FAutomationTestBase& Test, const FString& What, US08ArtPlateWidget& Widget, bool bOwn,
                      float Scale) {
  const FS08ArtHudPlateStyle Style;
  TSharedRef<IS08ArtPlateView> Slate = S08MakeSlatePlateView(Style);
  TSharedRef<IS08ArtPlateView> Umg = S08MakeUmgPlateView(Widget, TEXT("test"));
  const FS08PlateTexts Texts = S08SampleTexts(bOwn);
  Slate->ApplyTexts(Texts);
  Umg->ApplyTexts(Texts);
  Slate->SetShown(true);
  Umg->SetShown(true);
  TSharedRef<SWidget> SlateRoot = Slate->GetRoot();
  TSharedRef<SWidget> UmgRoot = Umg->GetRoot();
  TArray<FS08WidgetPart> SlateParts, UmgParts;
  Slate->CollectParts(SlateParts);
  Umg->CollectParts(UmgParts);
  Test.TestEqual(What + TEXT(": same part ids"), UmgParts.Num(), SlateParts.Num());
  const TMap<FString, FSlateRect> A = S08Layout(SlateRoot, SlateParts, Style.SizeSu, Scale);
  const TMap<FString, FSlateRect> B = S08Layout(UmgRoot, UmgParts, Widget.GetPlateSizeSu(), Scale);
  float Worst = 0.0f;
  for (const FS08WidgetPart& Part : SlateParts) {
    const FSlateRect* Ra = A.Find(Part.Id);
    const FSlateRect* Rb = B.Find(Part.Id);
    if (!Ra || !Rb) {
      Test.AddError(FString::Printf(TEXT("%s: part %s not arranged (slate=%d umg=%d)"), *What, *Part.Id, Ra ? 1 : 0,
                                    Rb ? 1 : 0));
      continue;
    }
    const float D = FMath::Max(FMath::Max(FMath::Abs(Ra->Left - Rb->Left), FMath::Abs(Ra->Top - Rb->Top)),
                               FMath::Max(FMath::Abs(Ra->Right - Rb->Right), FMath::Abs(Ra->Bottom - Rb->Bottom)));
    Worst = FMath::Max(Worst, D);
    Test.AddInfo(FString::Printf(TEXT("%s scale=%.2f %s slate=(%.1f,%.1f,%.1f,%.1f) umg=(%.1f,%.1f,%.1f,%.1f) d=%.2f"),
                                 *What, Scale, *Part.Id, Ra->Left, Ra->Top, Ra->Right, Ra->Bottom, Rb->Left, Rb->Top,
                                 Rb->Right, Rb->Bottom, D));
    Test.TestTrue(FString::Printf(TEXT("%s: %s within 1 px (d=%.2f)"), *What, *Part.Id, D), D <= 1.0f);
  }
  // Content equality: both show the same string-table text.
  Test.TestEqual(What + TEXT(": HP text"), Widget.HpText ? Widget.HpText->GetText().ToString() : FString(),
                 Texts.Hp.ToString());
  return Worst;
}
}  // namespace

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ArtHudUmgTokensTest,
    "Unmatched.S08.ArtHudUmg.Tokens colors go through FLinearColor(FColor): painted bytes = token bytes",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ArtHudUmgTokensTest::RunTest(const FString&) {
  const FS08ArtHudPlateStyle Style;
  // The T2.2 plate values (hud-input-t22-2026-09-28.md) are the defaults.
  TestEqual("marker #C8A0FF", Style.Marker, FColor(200, 160, 255, 255));
  TestEqual("background", Style.Background, FColor(22, 26, 40, 255));
  TestEqual("name", Style.NameText, FColor(242, 236, 222, 255));
  TestEqual("own chip", Style.OwnChip, FColor(70, 120, 200, 255));
  TestEqual("enemy chip", Style.EnemyChip, FColor(200, 70, 60, 255));
  TestEqual("hp back", Style.HpBack, FColor(70, 30, 30, 255));
  TestEqual("hp fill", Style.HpFill, FColor(80, 190, 100, 255));
  TestEqual("status", Style.StatusText, FColor(200, 204, 220, 255));
  TestTrue("plate 172x54 su", Style.SizeSu.Equals(FVector2D(172.0, 54.0)));
  TestEqual("hp bar 96 su", Style.HpBarWidthSu, 96.0f);
  for (const FColor& C : {Style.Marker, Style.Background, Style.NameText, Style.OwnChip, Style.EnemyChip, Style.HpBack,
                          Style.HpFill, Style.StatusText}) {
    // sRGB bytes -> linear -> back-buffer sRGB: the exact bytes (memory trap 9).
    TestEqual(FString::Printf(TEXT("round trip %s"), *C.ToHex()), FS08ArtHudPlateStyle::Linear(C).ToFColor(true), C);
  }
  TestFalse("a raw FLinearColor(1,.25,.25) does NOT paint #FF4040",
            FLinearColor(1.0f, 0.25f, 0.25f).ToFColor(true) == FColor(255, 64, 64, 255));
  const FSlateFontInfo Name = Style.NameFont.Resolve();
  TestEqual("name font Bold 12", Name.Size, 12.0f);
  TestEqual("name typeface", Name.TypefaceFontName, FName(TEXT("Bold")));
  TestTrue("default composite font (the Slate plate font)", Name.GetCompositeFont() != nullptr);
  TestEqual("status font Regular 8", Style.StatusFont.Resolve().Size, 8.0f);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ArtHudUmgStringsTest,
    "Unmatched.S08.ArtHudUmg.Strings the art HUD text comes from the S08ArtHud string table (en = pre-UMG text)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ArtHudUmgStringsTest::RunTest(const FString&) {
  TestTrue("table registered from the CSV", S08ArtHudText::EnsureTable());
  TestTrue("entries >= required keys", S08ArtHudText::NumEntries() >= S08ArtHudText::RequiredKeys().Num());
  const TArray<FString> Missing = S08ArtHudText::MissingKeys();
  TestEqual(FString::Printf(TEXT("no missing keys (%s)"), *FString::Join(Missing, TEXT(","))), Missing.Num(), 0);
  TestTrue("team text is a string-table text", S08ArtHudText::Get(TEXT("plate.team.own")).IsFromStringTable());
  // The en source strings reproduce the pre-UMG literals byte for byte.
  TestEqual("HP line", S08ArtHudText::PlateHp(7, 16).ToString(), FString(TEXT("HP 7/16")));
  TestEqual("HP no grouping", S08ArtHudText::PlateHp(1200, 1500).ToString(), FString(TEXT("HP 1200/1500")));
  TestEqual("own chip", S08ArtHudText::PlateTeam(true).ToString(), FString(TEXT("YOURS")));
  TestEqual("enemy chip", S08ArtHudText::PlateTeam(false).ToString(), FString(TEXT("ENEMY")));
  const TArray<FString> Codes = S08PlateStatuses(true, true, TEXT("melee"), true, false, {TEXT("stunned")});
  TestEqual("statuses = legacy join of the codes", S08ArtHudText::PlateStatuses(Codes).ToString(),
            FString::Join(Codes, TEXT("  |  ")));
  TestEqual("statuses text", S08ArtHudText::PlateStatuses(Codes).ToString(),
            FString(TEXT("HERO  |  MELEE  |  ATTACKER  |  STUNNED")));
  TestEqual("compact label", S08ArtHudText::CompactLabel(TEXT("Medusa"), 7, 16).ToString(),
            FString(TEXT("Medusa 7/16")));
  TestEqual("hp label", S08ArtHudText::HpLabel(7, 16).ToString(), FString(TEXT("7/16")));
  TestEqual("damage number", S08ArtHudText::DamageNumber(3).ToString(), FString(TEXT("-3")));
  TestEqual("missing key renders as the key", S08ArtHudText::Get(TEXT("no.such.key")).ToString(),
            FString(TEXT("no.such.key")));
  const FS08PlateTexts T = S08ArtHudText::PlateTexts(TEXT("Harpy"), 0, 4, false, {TEXT("SIDEKICK")});
  TestEqual("hp fraction 0", T.HpFraction, 0.0f);
  TestFalse("enemy", T.bOwn);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ArtHudUmgFlagTest,
    "Unmatched.S08.ArtHudUmg.Flag -ArtHudImpl umg (default) / slate / compare / alternate, SHOT widget line format",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ArtHudUmgFlagTest::RunTest(const FString&) {
  ES08ArtHudImpl Impl = ES08ArtHudImpl::Slate;
  TestTrue("empty = umg", S08ParseArtHudImpl(TEXT(""), Impl) && Impl == ES08ArtHudImpl::Umg);
  TestTrue("umg", S08ParseArtHudImpl(TEXT("UMG"), Impl) && Impl == ES08ArtHudImpl::Umg);
  TestTrue("slate", S08ParseArtHudImpl(TEXT("slate"), Impl) && Impl == ES08ArtHudImpl::Slate);
  TestTrue("compare", S08ParseArtHudImpl(TEXT(" compare "), Impl) && Impl == ES08ArtHudImpl::Compare);
  TestTrue("alternate", S08ParseArtHudImpl(TEXT("Alternate"), Impl) && Impl == ES08ArtHudImpl::Alternate);
  TestFalse("unknown refused", S08ParseArtHudImpl(TEXT("commonui"), Impl));
  FS08ArtHudRuntime Runtime;
  Runtime.ActiveView = 1;
  TestTrue("compare/umg/slate: every view is drawn", Runtime.IsViewShown(0, false) && Runtime.IsViewShown(1, false));
  TestTrue("alternate: only the active view", !Runtime.IsViewShown(0, true) && Runtime.IsViewShown(1, true));
  TestEqual("names", FString(S08ArtHudImplName(ES08ArtHudImpl::Compare)), FString(TEXT("compare")));

  const FString Line = S08ArtHud::FormatWidgetLine(TEXT("plate.name"), TEXT("umg"), TEXT("own"), TEXT("f-0-hero"),
                                                   FS08ScreenRect(981.4f, 520.6f, 1060.0f, 537.2f), true, false,
                                                   TEXT("/Game/S08/UI/ArtHud/WBP_S08ArtPlate"));
  TestEqual("line", Line, FString(TEXT("SHOT widget id=plate.name impl=umg state=own fighter=f-0-hero bbox=(981,521,1060,537) geom=painted visible=1 twin=0 source=/Game/S08/UI/ArtHud/WBP_S08ArtPlate")));
  const FString Twin = S08ArtHud::FormatWidgetLine(TEXT("plate"), TEXT("slate"), TEXT("enemy"), FString(),
                                                   FS08ScreenRect(1, 2, 3, 4), false, true, TEXT("slate"));
  TestEqual("unpainted twin", Twin, FString(TEXT("SHOT widget id=plate impl=slate state=enemy fighter=none bbox=(0,0,0,0) geom=unpainted visible=0 twin=1 source=slate")));
  // tools/art/art_hud_umg.py WIDGET regex; qa010 prefixes never match it.
  FRegexMatcher M(FRegexPattern(TEXT("^SHOT widget id=(\\S+) impl=(umg|slate) state=(\\S+) fighter=(\\S+) bbox=\\((-?\\d+),(-?\\d+),(-?\\d+),(-?\\d+)\\) geom=(painted|unpainted) visible=([01]) twin=([01]) source=(\\S+)$")), Line);
  TestTrue("parser regex", M.FindNext() && M.GetCaptureGroup(1) == TEXT("plate.name") && M.GetCaptureGroup(5) == TEXT("981"));
  for (const TCHAR* Prefix : {TEXT("SHOT plate"), TEXT("SHOT icon"), TEXT("SHOT reachable"), TEXT("PLATE "),
                              TEXT("ICON "), TEXT("REACHABLE ")}) {
    TestFalse(FString::Printf(TEXT("not a qa010 '%s' line"), Prefix), Line.StartsWith(Prefix));
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ArtHudUmgNativeTreeTest,
    "Unmatched.S08.ArtHudUmg.NativeTree the widget classes build and bind the code default tree",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ArtHudUmgNativeTreeTest::RunTest(const FString&) {
  FS08TestWorld W(TEXT("S08ArtHudUmgNativeTree"));
  if (!W.World) {
    AddError(TEXT("no test world"));
    return true;
  }
  US08ArtPlateWidget* Plate = CreateWidget<US08ArtPlateWidget>(W.World, US08ArtPlateWidget::StaticClass());
  TestNotNull("plate created", Plate);
  if (Plate) {
    FString Missing;
    TestTrue(FString::Printf(TEXT("all plate parts bound (%s)"), *Missing), Plate->HasAllParts(&Missing));
    TestTrue("code default tree", Plate->UsesCodeDefaultTree());
    Plate->ApplyTexts(S08SampleTexts(true));
    TestEqual("team text", Plate->TeamText->GetText().ToString(), FString(TEXT("YOURS")));
    TestEqual("status text", Plate->StatusText->GetText().ToString(),
              FString(TEXT("HERO  |  RANGED  |  ATTACKER  |  STUNNED")));
    TestEqual("hp fill 7/16 of 96 su", Plate->HpFill->GetWidthOverride(), 96.0f * 7.0f / 16.0f);
    TestEqual("chip = own token", Plate->TeamChip->GetBrushColor(), FS08ArtHudPlateStyle::Linear(Plate->Style.OwnChip));
    Plate->ApplyTexts(S08SampleTexts(false));
    TestEqual("chip = enemy token", Plate->TeamChip->GetBrushColor(),
              FS08ArtHudPlateStyle::Linear(Plate->Style.EnemyChip));
    TArray<FS08WidgetPart> Parts;
    Plate->TakeWidget();
    Plate->CollectParts(Parts);
    TestEqual("8 traced parts", Parts.Num(), 8);
  }
  US08ArtIconWidget* Icon = CreateWidget<US08ArtIconWidget>(W.World, US08ArtIconWidget::StaticClass());
  TestNotNull("icon created", Icon);
  if (Icon) {
    TestTrue("icon bound", Icon->HasAllParts());
    TestTrue("icon code default tree", Icon->UsesCodeDefaultTree());
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ArtHudUmgParityTest,
    "Unmatched.S08.ArtHudUmg.Parity UMG code default plate = Slate plate within 1 px (every part, 100 % and 150 %)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ArtHudUmgParityTest::RunTest(const FString&) {
  FS08TestWorld W(TEXT("S08ArtHudUmgParity"));
  if (!W.World) {
    AddError(TEXT("no test world"));
    return true;
  }
  for (const bool bOwn : {true, false}) {
    for (const float Scale : {1.0f, 1.5f}) {
      US08ArtPlateWidget* Plate = CreateWidget<US08ArtPlateWidget>(W.World, US08ArtPlateWidget::StaticClass());
      if (!Plate) {
        AddError(TEXT("plate not created"));
        continue;
      }
      const float Worst = S08ComparePlate(*this, bOwn ? TEXT("native own") : TEXT("native enemy"), *Plate, bOwn, Scale);
      AddInfo(FString::Printf(TEXT("native %s scale %.1f worst edge difference %.2f px"), bOwn ? TEXT("own") : TEXT("enemy"),
                              Scale, Worst));
    }
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ArtHudUmgWbpTest,
    "Unmatched.S08.ArtHudUmg.Wbp WBP_S08ArtPlate/WBP_S08ArtIcon are children of the classes, bind every part, = Slate within 1 px",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ArtHudUmgWbpTest::RunTest(const FString&) {
  UClass* PlateClass = S08LoadArtHudWidgetClass(US08ArtPlateWidget::WidgetBlueprintPath, US08ArtPlateWidget::StaticClass());
  UClass* IconClass = S08LoadArtHudWidgetClass(US08ArtIconWidget::WidgetBlueprintPath, US08ArtIconWidget::StaticClass());
  TestNotNull("WBP_S08ArtPlate class (art worktree /Game/S08/UI/ArtHud)", PlateClass);
  TestNotNull("WBP_S08ArtIcon class", IconClass);
  FS08TestWorld W(TEXT("S08ArtHudUmgWbp"));
  if (!W.World || !PlateClass || !IconClass) return true;
  US08ArtPlateWidget* Plate = CreateWidget<US08ArtPlateWidget>(W.World, PlateClass);
  TestNotNull("WBP plate instance", Plate);
  if (Plate) {
    FString Missing;
    TestTrue(FString::Printf(TEXT("WBP binds every part (%s)"), *Missing), Plate->HasAllParts(&Missing));
    TestFalse("WBP uses its own designer tree", Plate->UsesCodeDefaultTree());
    // Port gate (W4-C): at authoring time the WBP is the code default tree.
    // When a designer deliberately changes the layout, this check is retired
    // together with the Slate path (the packaged SHOT widget traces remain).
    for (const float Scale : {1.0f, 1.5f}) S08ComparePlate(*this, TEXT("WBP"), *Plate, true, Scale);
  }
  US08ArtIconWidget* Icon = CreateWidget<US08ArtIconWidget>(W.World, IconClass);
  TestNotNull("WBP icon instance", Icon);
  if (Icon) {
    TestTrue("WBP icon bound", Icon->HasAllParts());
    TestFalse("WBP icon designer tree", Icon->UsesCodeDefaultTree());
  }
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
