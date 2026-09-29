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
#include "S08Team.h"
#include "Blueprint/UserWidget.h"
#include "Components/Image.h"
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
  // W5b-R D-2/D-3: the team chip = the on-screen colour of the team ring fill (team.p1.screen / team.p2.screen).
  TestEqual("team chip P1 = team.p1.screen #DAC576", Style.TeamChipP1, FColor(218, 197, 118, 255));
  TestEqual("team chip P2 = team.p2.screen #5786A8", Style.TeamChipP2, FColor(87, 134, 168, 255));
  TestEqual("chip P1 = palette header", Style.TeamChipP1, S08TeamPalette::ChipColor(ES08TeamSlot::P1));
  TestEqual("chip P2 = palette header", Style.TeamChipP2, S08TeamPalette::ChipColor(ES08TeamSlot::P2));
  TestEqual("hp back", Style.HpBack, FColor(70, 30, 30, 255));
  TestEqual("hp fill", Style.HpFill, FColor(80, 190, 100, 255));
  TestEqual("status", Style.StatusText, FColor(200, 204, 220, 255));
  TestTrue("plate 172x54 su", Style.SizeSu.Equals(FVector2D(172.0, 54.0)));
  TestEqual("hp bar 96 su", Style.HpBarWidthSu, 96.0f);
  for (const FColor& C : {Style.Marker, Style.Background, Style.NameText, Style.TeamChipP1, Style.TeamChipP2,
                          Style.HpBack, Style.HpFill, Style.StatusText}) {
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
    // W5b-R D-3: the chip box is the plate background; the team shape carries the team colour.
    TestEqual("chip box = plate background", Plate->TeamChip->GetBrushColor(),
              FS08ArtHudPlateStyle::Linear(Plate->Style.Background));
    TestEqual("P1 shape = team chip P1", Plate->TeamShape->GetColorAndOpacity(), Plate->Style.TeamChipColor(0));
    FS08PlateTexts P2 = S08SampleTexts(false);
    P2.TeamSlot = 1;
    Plate->ApplyTexts(P2);
    TestEqual("P2 shape = team chip P2", Plate->TeamShape->GetColorAndOpacity(), Plate->Style.TeamChipColor(1));
    TestEqual("enemy text", Plate->TeamText->GetText().ToString(), FString(TEXT("ENEMY")));
    TArray<FS08WidgetPart> Parts;
    Plate->TakeWidget();
    Plate->CollectParts(Parts);
    TestEqual("9 traced parts (plate.teamshape added)", Parts.Num(), 9);
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

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ArtHudUmgTagTest,
    "Unmatched.S08.ArtHudUmg.Tag W5b-R screen tag: code default tree, modes, tokens, traced parts, 14.7:1 by construction",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ArtHudUmgTagTest::RunTest(const FString&) {
  FS08TestWorld W(TEXT("S08ArtHudUmgTag"));
  if (!W.World) {
    AddError(TEXT("no test world"));
    return true;
  }
  const FS08ArtHudTagStyle Style;
  TestEqual("tag background = tag.background #161A28", Style.Background, FColor(22, 26, 40, 255));
  TestEqual("tag text = tag.text #F2ECDE", Style.Text, FColor(242, 236, 222, 255));
  TestTrue("name font Bold >= 11 su", Style.NameFont.Size >= 11 && Style.NameFont.Typeface == FName(TEXT("Bold")));
  TestTrue("HP font Bold >= 11 su", Style.HpFont.Size >= 11 && Style.HpFont.Typeface == FName(TEXT("Bold")));
  // WCAG 2.x of the tokens (sRGB -> relative luminance): text on the tag background >= 4.5 (predicted 14.7).
  auto Lum = [](const FColor& C) {
    const FLinearColor L(C);
    return 0.2126 * L.R + 0.7152 * L.G + 0.0722 * L.B;
  };
  const double Ratio = (Lum(Style.Text) + 0.05) / (Lum(Style.Background) + 0.05);
  TestTrue(FString::Printf(TEXT("text/background %.2f:1 >= 4.5"), Ratio), Ratio >= 4.5);
  const FS08ArtHudDamageStyle Damage;
  const double DamageRatio = (Lum(Damage.Text) + 0.05) / (Lum(Damage.Background) + 0.05);
  TestTrue(FString::Printf(TEXT("damage text/capsule %.2f:1 >= 4.5"), DamageRatio), DamageRatio >= 4.5);
  TestTrue("damage font Bold 18 (large text)", Damage.Font.Size >= 18);

  US08ArtTagWidget* Tag = CreateWidget<US08ArtTagWidget>(W.World, US08ArtTagWidget::StaticClass());
  if (!TestNotNull("tag created", Tag)) return true;
  FString Missing;
  TestTrue(FString::Printf(TEXT("tag parts bound (%s)"), *Missing), Tag->HasAllParts(&Missing));
  TestTrue("tag code default tree", Tag->UsesCodeDefaultTree());
  Tag->TakeWidget();
  FS08TagTexts T;
  T.Name = FText::FromString(TEXT("Harpies 2"));
  T.Hp = S08ArtHudText::HpLabel(1, 1);
  T.HpFraction = 1.0f;
  T.TeamSlot = 1;
  T.Mode = ES08TagMode::Full;
  Tag->ApplyModel(T);
  TestEqual("full: name visible", Tag->NameText->GetVisibility(), ESlateVisibility::HitTestInvisible);
  TestEqual("hp text", Tag->HpText->GetText().ToString(), FString(TEXT("1/1")));
  TestEqual("P2 chip colour", Tag->TeamShape->GetColorAndOpacity(), FS08ArtHudPlateStyle().TeamChipColor(1));
  TArray<FS08WidgetPart> Parts;
  Tag->CollectParts(Parts);
  TArray<FString> Ids;
  for (const FS08WidgetPart& Part : Parts) Ids.Add(Part.Id);
  TestEqual("full: tag + name + hp + bar + chip", FString::Join(Ids, TEXT(",")),
            FString(TEXT("board.tag,board.tag.name,board.tag.hp,board.tag.bar,board.tag.chip")));
  T.Mode = ES08TagMode::Compact;
  T.Hp = S08ArtHudText::HpLabel(3, 7);
  T.HpFraction = 3.0f / 7.0f;
  Tag->ApplyModel(T);
  TestEqual("compact: name collapsed", Tag->NameText->GetVisibility(), ESlateVisibility::Collapsed);
  TestEqual("compact: bar fill 3/7", Tag->HpFill->GetWidthOverride(), Style.BarWidthSu * 3.0f / 7.0f);
  Parts.Reset();
  Tag->CollectParts(Parts);
  TestEqual("compact: 4 traced parts", Parts.Num(), 4);
  // desired size (the controller's S08ArtHudPrepassSize, layout scale 1): at least the 12-su chip + padding; with
  // measured fonts (a Slate renderer - not under -nullrhi) the full tag is taller than the compact one
  const FVector2D Compact = S08ArtHudPrepassSize(*Tag);
  T.Mode = ES08TagMode::Full;
  Tag->ApplyModel(T);
  const FVector2D Full = S08ArtHudPrepassSize(*Tag);
  AddInfo(FString::Printf(TEXT("tag desired size compact=%s full=%s"), *Compact.ToString(), *Full.ToString()));
  TestTrue("compact >= chip 12 + padding 2x2 high", Compact.Y >= 16.0 - 1e-3);
  TestTrue("compact >= chip + gap + bar + padding wide", Compact.X >= 4.0 + 12.0 + 3.0 + 34.0 + 3.0 + 4.0 - 1e-3);
  if (Full.Y > Compact.Y + 0.5) {
    TestTrue("full taller than compact (name line)", Full.Y >= Compact.Y + 11.0);
  } else {
    AddInfo(TEXT("fonts not measured in this process (no Slate renderer, -nullrhi): name-line height not checked"));
  }

  US08ArtDamageWidget* Number = CreateWidget<US08ArtDamageWidget>(W.World, US08ArtDamageWidget::StaticClass());
  if (TestNotNull("damage widget created", Number)) {
    TestTrue("damage parts bound", Number->HasAllParts());
    Number->ApplyAmount(S08ArtHudText::DamageNumber(2));
    TestEqual("damage text", Number->DamageText->GetText().ToString(), FString(TEXT("-2")));
    Number->TakeWidget();
    TArray<FS08WidgetPart> DamageParts;
    Number->CollectParts(DamageParts);
    TestEqual("damage parts", DamageParts.Num(), 2);
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ArtHudUmgLayoutTest,
    "Unmatched.S08.ArtHudUmg.Layout W5b-R label / icon placement: deterministic, never over hard obstacles, anchor order",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ArtHudUmgLayoutTest::RunTest(const FString&) {
  using namespace S08ArtHud;
  // 1) free space: the tag sits right above the figure, centred, ring 0
  FLabelPlacementInput In;
  In.Viewport = FVector2D(1920.0, 1080.0);
  In.Size = FVector2D(70.0, 30.0);
  In.Anchor = FS08ScreenRect(900.0f, 500.0f, 960.0f, 600.0f);
  FLabelPlacementResult R = ChooseLabelRect(In);
  TestTrue("clean", R.bClean);
  TestEqual("above first", R.Candidate, FString(TEXT("above")));
  TestEqual("ring 0", R.Ring, 0);
  TestTrue("centred above the anchor", FMath::IsNearlyEqual(R.Rect.Center().X, 930.0, 1.0) && R.Rect.Y1 <= In.Anchor.Y0);
  // 2) the slot above is taken (hard): right of the figure
  In.Hard.Add(FS08ScreenRect(820.0f, 380.0f, 1040.0f, 498.0f));
  R = ChooseLabelRect(In);
  TestTrue("hard-clean", R.bHardClean);
  TestEqual("right when above is taken", R.Candidate, FString(TEXT("right")));
  TestTrue("no hard overlap", OverlapArea(R.Rect, In.Hard) <= 0.5);
  // 3) deterministic: the same input -> the same rect
  const FLabelPlacementResult R2 = ChooseLabelRect(In);
  TestTrue("deterministic", R2.Rect.X0 == R.Rect.X0 && R2.Rect.Y0 == R.Rect.Y0 && R2.Candidate == R.Candidate);
  // 4) soft obstacles are avoided when a clean spot exists, tolerated otherwise (hard never)
  In.Soft.Add(FS08ScreenRect(963.0f, 490.0f, 1100.0f, 620.0f));
  R = ChooseLabelRect(In);
  TestTrue("hard never crossed", OverlapArea(R.Rect, In.Hard) <= 0.5);
  TestTrue("soft avoided when possible", R.bClean);
  // 5) damage number: right of the anchor first
  FLabelPlacementInput D;
  D.Viewport = FVector2D(1920.0, 1080.0);
  D.Size = FVector2D(40.0, 26.0);
  D.Anchor = FS08ScreenRect(900.0f, 460.0f, 970.0f, 490.0f);
  D.bRightFirst = true;
  TestEqual("damage right first", ChooseLabelRect(D).Candidate, FString(TEXT("right")));
  // 5b) binding (t53 damage.binding, the Cobble rehearsal case): the anchor is the target's tag LEFT of the target
  // figure, a neighbour figure sits left-above the tag - the number must stay nearer the target than the neighbour
  {
    FLabelPlacementInput B;
    B.Viewport = FVector2D(1920.0, 1080.0);
    B.Size = FVector2D(40.0, 28.0);
    const FS08ScreenRect TargetFig(914.0f, 517.0f, 1006.0f, 643.0f);
    const FS08ScreenRect Neighbour(766.0f, 410.0f, 839.0f, 504.0f);
    B.Anchor = FS08ScreenRect(807.0f, 517.0f, 912.0f, 558.0f);  // the target's tag
    B.Hard.Add(TargetFig);
    B.Hard.Add(B.Anchor);
    B.Soft.Add(Neighbour);
    B.bRightFirst = true;
    B.BindTarget = TargetFig;
    B.BindOthers.Add(Neighbour);
    const FLabelPlacementResult Rb = ChooseLabelRect(B);
    TestTrue("bound result", Rb.bBound && Rb.bHardClean);
    TestTrue("centre nearer the target than the neighbour",
             PointRectDistance(Rb.Rect.Center(), TargetFig) < PointRectDistance(Rb.Rect.Center(), Neighbour));
    TestTrue("no hard overlap (target figure, tag)", OverlapArea(Rb.Rect, B.Hard) <= 0.5);
    TestFalse("unbound point", IsBoundTo(FVector2D(860.0, 501.0), TargetFig, B.BindOthers));
  }
  // 6) icon anchors: right -> left -> below -> above, first free
  FIconAnchorInput I;
  I.Viewport = FVector2D(1920.0, 1080.0);
  I.Size = 32.0f;
  I.Target = FS08ScreenRect(900.0f, 500.0f, 960.0f, 600.0f);
  FIconAnchorResult A = ChooseIconAnchor(I);
  TestEqual("icon right", A.Anchor, FString(TEXT("right")));
  TestTrue("icon at 35 % of the height", FMath::IsNearlyEqual(A.Rect.Center().Y, 535.0, 1.0));
  I.Figures.Add(FS08ScreenRect(962.0f, 480.0f, 1040.0f, 620.0f));
  A = ChooseIconAnchor(I);
  TestEqual("icon left when a figure is on the right", A.Anchor, FString(TEXT("left")));
  I.Hard.Add(FS08ScreenRect(820.0f, 480.0f, 898.0f, 620.0f));
  A = ChooseIconAnchor(I);
  TestEqual("icon below when both sides are taken", A.Anchor, FString(TEXT("below")));
  I.Hard.Add(FS08ScreenRect(880.0f, 601.0f, 980.0f, 700.0f));
  A = ChooseIconAnchor(I);
  TestEqual("icon above", A.Anchor, FString(TEXT("above")));
  TestFalse("above is free here", A.bFallback);
  I.Hard.Add(FS08ScreenRect(880.0f, 400.0f, 980.0f, 499.0f));
  A = ChooseIconAnchor(I);
  TestTrue("every anchor taken -> above with the overlap recorded", A.bFallback && A.OverlapArea > 0.0);
  // 7) team mapping (D-2): P1 = the lowest seat; relative mode draws the viewer as P1
  TestTrue("fighter prefix fallback", S08TeamOf(TEXT("f-0-hero"), TEXT("u1"), FString()) == ES08TeamSlot::P1 &&
                                          S08TeamOf(TEXT("f-1-sk0"), TEXT("u2"), FString()) == ES08TeamSlot::P2);
  TestTrue("owner mapping", S08TeamOf(TEXT("x"), TEXT("host"), TEXT("host")) == ES08TeamSlot::P1 &&
                                S08TeamOf(TEXT("y"), TEXT("guest"), TEXT("host")) == ES08TeamSlot::P2);
  TestTrue("relative: own looks P1", S08TeamLook(ES08TeamSlot::P2, true, ES08TeamColorMode::Relative) == ES08TeamSlot::P1);
  TestTrue("absolute keeps the seat team",
           S08TeamLook(ES08TeamSlot::P2, true, ES08TeamColorMode::Absolute) == ES08TeamSlot::P2);
  ES08TeamColorMode Mode;
  TestTrue("parse relative", S08ParseTeamColorMode(TEXT("Relative"), Mode) && Mode == ES08TeamColorMode::Relative);
  TestFalse("refuse unknown", S08ParseTeamColorMode(TEXT("own"), Mode));
  // palette: one colour rule (FromSRGBColor of the token hex)
  TestTrue("P1 fill = FromSRGBColor(#E8C06A)", S08TeamPalette::RingFill(ES08TeamSlot::P1)
                                                   .Equals(FLinearColor::FromSRGBColor(FColor(0xE8, 0xC0, 0x6A)), 1e-6f));
  TestTrue("P2 fill = FromSRGBColor(#5A7F9F)", S08TeamPalette::RingFill(ES08TeamSlot::P2)
                                                   .Equals(FLinearColor::FromSRGBColor(FColor(0x5A, 0x7F, 0x9F)), 1e-6f));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ArtHudUmgTagBindingTest,
    "Unmatched.S08.ArtHudUmg.TagBinding W5b-R r3: initial Cobble arrangement - every tag centre is nearer its owner's figure than any other",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ArtHudUmgTagBindingTest::RunTest(const FString&) {
  using namespace S08ArtHud;
  // FigureScreenRects and painted tag sizes of the initial Cobble K1 (both clients, G3 traces of W5b-R
  // k1/cobble-5x6/run-20260929-175824): Medusa at (2,2), Harpies 1 (3,2) right, Harpies 2 (2,1) behind,
  // Harpies 3 (1,2) left, King Arthur (2,3) in front, Merlin (3,3).
  struct FFig {
    const TCHAR* Id;
    FS08ScreenRect Rect;
    FVector2D Size;  // painted tag size (Medusa: compact, blockouts: full)
  };
  const TArray<FFig> Figs = {
      {TEXT("f-0-hero"), FS08ScreenRect(915.0f, 389.0f, 1005.0f, 512.0f), FVector2D(102.0, 22.0)},
      {TEXT("f-0-sk0"), FS08ScreenRect(1081.0f, 410.0f, 1154.0f, 504.0f), FVector2D(91.0, 41.0)},
      {TEXT("f-0-sk1"), FS08ScreenRect(926.0f, 288.0f, 994.0f, 381.0f), FVector2D(91.0, 41.0)},
      {TEXT("f-0-sk2"), FS08ScreenRect(766.0f, 410.0f, 839.0f, 504.0f), FVector2D(91.0, 41.0)},
      {TEXT("f-1-hero"), FS08ScreenRect(914.0f, 517.0f, 1006.0f, 643.0f), FVector2D(105.0, 41.0)},
      {TEXT("f-1-sk0"), FS08ScreenRect(1084.0f, 520.0f, 1162.0f, 635.0f), FVector2D(84.0, 41.0)},
  };
  const FVector2D Viewport(1920.0, 1080.0);
  auto OthersOf = [&Figs](int32 Index) {
    TArray<FS08ScreenRect> Out;
    for (int32 I = 0; I < Figs.Num(); ++I) {
      if (I != Index) Out.Add(Figs[I].Rect);
    }
    return Out;
  };
  // far first: screen Y0 of the figure, then the fighter id (the game mode's order for K1: no icon, no damage)
  TArray<int32> Order = {0, 1, 2, 3, 4, 5};
  Order.Sort([&Figs](int32 A, int32 B) {
    return Figs[A].Rect.Y0 != Figs[B].Rect.Y0 ? Figs[A].Rect.Y0 < Figs[B].Rect.Y0
                                              : FCString::Strcmp(Figs[A].Id, Figs[B].Id) < 0;
  });

  // 1) the G3 defect: without binding the Medusa tag leaves Medusa (the traced G3 result was ring 16, 98 px away,
  //    next to the Harpies 2 tag) - its centre is nearer another figure
  {
    TArray<FS08ScreenRect> Hard = {FS08ScreenRect(0.0f, 0.0f, 393.0f, 69.0f), FS08ScreenRect(1431.0f, 0.0f, 1920.0f, 121.0f),
                                   FS08ScreenRect(511.0f, 985.0f, 1409.0f, 1080.0f)};
    FS08ScreenRect OldMedusa;
    for (const int32 I : Order) {
      FLabelPlacementInput In;  // the G3 input: soft figures, no BindTarget, no inset, no near rings
      In.Viewport = Viewport;
      In.Size = Figs[I].Size;
      In.Anchor = Figs[I].Rect;
      In.Hard = Hard;
      In.Soft = OthersOf(I);
      const FLabelPlacementResult R = ChooseLabelRect(In);
      if (I == 0) OldMedusa = R.Rect;
      Hard.Add(R.Rect);
    }
    AddInfo(FString::Printf(TEXT("G3 policy: Medusa tag %s"), *FormatRect(OldMedusa)));
    TestFalse("G3 policy reproduces the defect (Medusa tag centre not nearest Medusa)",
              IsBoundTo(OldMedusa.Center(), Figs[0].Rect, OthersOf(0)));
  }

  // 2) r3 policy on both clients: joiner (no plate) and host (Medusa's plate pushed next to Merlin by K-2 -> unbound
  //    -> Medusa keeps a compact tag)
  struct FClient {
    const TCHAR* Name;
    TArray<FS08ScreenRect> Panels;
    FS08ScreenRect Plate;
  };
  const TArray<FClient> Clients = {
      {TEXT("joiner"),
       {FS08ScreenRect(0.0f, 0.0f, 393.0f, 69.0f), FS08ScreenRect(1431.0f, 0.0f, 1920.0f, 121.0f),
        FS08ScreenRect(511.0f, 985.0f, 1409.0f, 1080.0f)},
       FS08ScreenRect()},
      {TEXT("host"),
       {FS08ScreenRect(0.0f, 0.0f, 601.0f, 138.0f), FS08ScreenRect(1432.0f, 0.0f, 1920.0f, 121.0f),
        FS08ScreenRect(449.0f, 985.0f, 1471.0f, 1080.0f)},
       FS08ScreenRect(1009.0f, 638.0f, 1181.0f, 692.0f)},
  };
  for (const FClient& C : Clients) {
    TArray<FS08ScreenRect> Hard = C.Panels;
    if (!C.Plate.IsEmpty()) {
      TestFalse(FString::Printf(TEXT("%s: the K-2 plate next to Merlin is not bound to Medusa"), C.Name),
                IsRectBoundTo(C.Plate, Figs[0].Rect, OthersOf(0)));
      Hard.Add(C.Plate);
    }
    TArray<FS08ScreenRect> Placed;
    Placed.SetNum(Figs.Num());
    for (const int32 I : Order) {
      const FLabelPlacementInput In = MakeTagPlacementInput(Viewport, Figs[I].Size, Figs[I].Rect, OthersOf(I), Hard);
      const FLabelPlacementResult R = ChooseLabelRect(In);
      const FLabelPlacementResult Again = ChooseLabelRect(In);
      TestTrue(FString::Printf(TEXT("%s %s: deterministic"), C.Name, Figs[I].Id),
               Again.Rect.X0 == R.Rect.X0 && Again.Rect.Y0 == R.Rect.Y0 && Again.Candidate == R.Candidate);
      AddInfo(FString::Printf(TEXT("%s %s: %s %s ring=%d soft=%.0f bound=%d"), C.Name, Figs[I].Id, *FormatRect(R.Rect),
                              *R.Candidate, R.Ring, R.SoftArea, R.bBound ? 1 : 0));
      TestFalse(FString::Printf(TEXT("%s %s: placed"), C.Name, Figs[I].Id), R.Rect.IsEmpty());
      TestTrue(FString::Printf(TEXT("%s %s: bound + hard-clean"), C.Name, Figs[I].Id), R.bBound && R.bHardClean);
      // the registered metric (t53 revision 1): centre strictly nearer the owner's figure than any other figure
      const double Own = PointRectDistance(R.Rect.Center(), Figs[I].Rect);
      for (int32 J = 0; J < Figs.Num(); ++J) {
        if (J == I) continue;
        TestTrue(FString::Printf(TEXT("%s %s: centre nearer the owner than %s"), C.Name, Figs[I].Id, Figs[J].Id),
                 Own < PointRectDistance(R.Rect.Center(), Figs[J].Rect));
      }
      TestTrue(FString::Printf(TEXT("%s %s: no hard overlap"), C.Name, Figs[I].Id), OverlapArea(R.Rect, Hard) <= 0.5);
      TestTrue(FString::Printf(TEXT("%s %s: within the first two rings"), C.Name, Figs[I].Id), R.Ring >= 0 && R.Ring < 2);
      Placed[I] = R.Rect;
      Hard.Add(R.Rect);
    }
    // Medusa: the tag touches her own box (the G3 tag was 98 px away) and not the Harpies 2 tag
    TestTrue(FString::Printf(TEXT("%s: Medusa tag at Medusa (gap <= 2 px)"), C.Name), RectGap(Placed[0], Figs[0].Rect) <= 2.0);
    TestTrue(FString::Printf(TEXT("%s: Medusa tag clear of the Harpies 2 tag"), C.Name),
             Placed[0].IntersectionArea(Placed[2]) <= 0.5);
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
  // W5b-R D-1: WBP_S08ArtTag / WBP_S08ArtDamage
  UClass* TagClass = S08LoadArtHudWidgetClass(US08ArtTagWidget::WidgetBlueprintPath, US08ArtTagWidget::StaticClass());
  UClass* DamageClass =
      S08LoadArtHudWidgetClass(US08ArtDamageWidget::WidgetBlueprintPath, US08ArtDamageWidget::StaticClass());
  TestNotNull("WBP_S08ArtTag class", TagClass);
  TestNotNull("WBP_S08ArtDamage class", DamageClass);
  if (TagClass) {
    US08ArtTagWidget* Tag = CreateWidget<US08ArtTagWidget>(W.World, TagClass);
    FString Missing;
    TestTrue(FString::Printf(TEXT("WBP tag binds every part (%s)"), *Missing), Tag && Tag->HasAllParts(&Missing));
    TestTrue("WBP tag designer tree", Tag && !Tag->UsesCodeDefaultTree());
  }
  if (DamageClass) {
    US08ArtDamageWidget* Number = CreateWidget<US08ArtDamageWidget>(W.World, DamageClass);
    TestTrue("WBP damage binds every part", Number && Number->HasAllParts());
  }
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
