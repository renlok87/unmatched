// VS-4 automation test of the zone icons at a hovered space (docs/game-design/visual/06-tasks/vfx.csv FX-38; IC-62...IC-69):
//   Unmatched.S08.Hud.ZoneBadges   the L6 size (clamp 0.3 d, 16, 32) and the export 24 / 32; the keys -> icons (<= 3), four
//                                  keys -> two icons and «+N» (ВР-VS4-55), L6 < 20 px hidden, 20...23 at 24 px (ВР-VS4-56),
//                                  a key without a profile colour hidden, the disc colour from the profile and the glyph by
//                                  contrast (navy / card.glyph),
//                                  the column moves right of a covered figure, the SHOT line, the -S08SlateHud=zone key.
// Headless: node tools/s08/run-ue-tests.cjs "Unmatched.S08.Hud.ZoneBadges" <abs log>
#if WITH_AUTOMATION_TESTS

#include "../S08AnimatedIconWidget.h"
#include "../S08ArtLook.h"
#include "../S08BoardArt.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Misc/AutomationTest.h"
#include "UmHudTheme.h"
#include "UmZoneBadges.h"

namespace UmZoneTest {
struct FWorld {
  UWorld* World = nullptr;
  explicit FWorld(const TCHAR* Name) {
    World = UWorld::CreateWorld(EWorldType::Game, false, FName(Name));
    if (World) GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
  }
  ~FWorld() {
    if (!World) return;
    GEngine->DestroyWorldContext(World);
    World->DestroyWorld(false);
  }
};

/** The zone icon colours of a real board profile (S08ArtBoardProfiles.json boards[].zoneIconSrgb, the run I measurements
 *  of 02 §7.4) - the test reads the shipped file, so no colour literal lives here (G-TOKENS). */
const TMap<FName, FColor>& ProfileDiscs(const TCHAR* ProfileId) {
  static FS08BoardArtData Data;
  static bool bLoaded = false;
  static const TMap<FName, FColor> None;
  if (!bLoaded) {
    TArray<FString> Errors;
    Data.LoadFile(FS08BoardArtData::DefaultPath(), Errors);
    bLoaded = true;
  }
  for (const FS08BoardArtProfile& B : Data.Boards) {
    if (B.Id == ProfileId) return B.ZoneIconSrgb;
  }
  return None;
}

bool MarmorealDisc(FName Key, FColor& Out) {
  const FColor* F = ProfileDiscs(TEXT("marmoreal-original")).Find(Key);
  if (F) Out = *F;
  return F != nullptr;
}

FColor Marm(const TCHAR* Key) {
  FColor C = FColor::Transparent;
  MarmorealDisc(FName(Key), C);
  return C;
}

FUmZoneBadgeInput Hover(std::initializer_list<const TCHAR*> Keys, float RadiusPx = 50.0f) {
  FUmZoneBadgeInput In;
  In.bShow = true;
  In.SpaceId = TEXT("M04");
  for (const TCHAR* K : Keys) In.Keys.Add(FName(K));
  In.CentrePx = FVector2D(800.0, 500.0);
  In.RadiusPx = RadiusPx;
  In.AnchorPx = RadiusPx * 38.0f / 40.0f;
  In.DiscColor = [](FName K, FColor& Out) { return MarmorealDisc(K, Out); };
  return In;
}
}  // namespace UmZoneTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHudZoneBadgesTest,
    "Unmatched.S08.Hud.ZoneBadges keys to icons, more than three, L6 below 20 px, profile disc, glyph by contrast, figure, SHOT, rollback",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHudZoneBadgesTest::RunTest(const FString&) {
  using namespace UmZoneTest;
  TestEqual(TEXT("L6: r 50 px -> 30"), UmZoneBadges::L6SizePx(50.0f), 30);
  TestEqual(TEXT("L6: r 20 px -> 16 (min)"), UmZoneBadges::L6SizePx(20.0f), 16);
  TestEqual(TEXT("L6: r 100 px -> 32 (max)"), UmZoneBadges::L6SizePx(100.0f), 32);
  TestEqual(TEXT("export: 16 -> none"), UmZoneBadges::TexturePxFor(16), 0);
  TestEqual(TEXT("export: 19 -> none (minimum zoom)"), UmZoneBadges::TexturePxFor(19), 0);
  TestEqual(TEXT("export: 20 -> 24 (720p K1, ВР-VS4-56)"), UmZoneBadges::TexturePxFor(20), 24);
  TestEqual(TEXT("export: 23 -> 24"), UmZoneBadges::TexturePxFor(23), 24);
  TestEqual(TEXT("export: 24 -> 24"), UmZoneBadges::TexturePxFor(24), 24);
  TestEqual(TEXT("export: 28 -> 32 (a tie - the larger)"), UmZoneBadges::TexturePxFor(28), 32);
  TestEqual(TEXT("export: 26 -> 24"), UmZoneBadges::TexturePxFor(26), 24);
  TestEqual(TEXT("export: 32 -> 32"), UmZoneBadges::TexturePxFor(32), 32);
  // keys -> icons
  {
    const FUmZonePlan P = UmZoneBadges::Plan(Hover({TEXT("gray"), TEXT("green"), TEXT("blue")}));
    TestEqual(TEXT("three keys: three icons"), P.Shown.Num(), 3);
    TestEqual(TEXT("three keys: no «+N»"), P.More, 0);
    TestEqual(TEXT("three keys: 32 px (r 50 -> L6 30)"), P.TexturePx, 32);
    TestTrue(TEXT("three keys: a column right of the centre, centred on it vertically"),
             P.Column.X0 > 800.0f && FMath::Abs(P.Column.Center().Y - 500.0f) <= 1.0f && P.IconRects.Num() == 3);
    TestTrue(TEXT("the column on the right anchor (+38 uu)"), FMath::Abs(P.Column.Center().X - (800.0f + 50.0f * 38.0f / 40.0f)) <= 1.0f);
  }
  {
    const FUmZonePlan P = UmZoneBadges::Plan(Hover({TEXT("gray"), TEXT("green"), TEXT("blue"), TEXT("red")}));
    TestEqual(TEXT("four keys: two icons"), P.Shown.Num(), 2);
    TestEqual(TEXT("four keys: «+2» (the zones not shown, ВР-VS4-55)"), P.More, 2);
    TestFalse(TEXT("four keys: the chip below the icons"), P.MoreRect.IsEmpty());
  }
  {
    const FUmZonePlan P = UmZoneBadges::Plan(Hover({TEXT("gray"), TEXT("green")}, 30.0f));
    TestEqual(TEXT("r 30 px -> L6 18 < 20: hidden"), P.Hidden, FString(TEXT("small")));
    TestEqual(TEXT("... and no icon"), P.Shown.Num(), 0);
    const FUmZonePlan Q = UmZoneBadges::Plan(Hover({TEXT("gray"), TEXT("green")}, 35.0f));
    TestTrue(FString::Printf(TEXT("r 35 px (720p K1) -> L6 21: two icons at 24 px (%d, %d)"), Q.L6Px, Q.TexturePx),
             Q.L6Px == 21 && Q.TexturePx == 24 && Q.Shown.Num() == 2 && Q.Hidden.IsEmpty());
  }
  {
    FUmZoneBadgeInput In = Hover({TEXT("violet")});
    In.DiscColor = [](FName K, FColor& Out) { return K != FName(TEXT("violet")) && MarmorealDisc(K, Out); };  // Sarpedon: no violet
    TestEqual(TEXT("a key without a profile colour: hidden (never the topology hex)"), UmZoneBadges::Plan(In).Hidden, FString(TEXT("nocolor")));
    FUmZoneBadgeInput Off = Hover({TEXT("gray")});
    Off.bShow = false;
    TestEqual(TEXT("no hover: nothing (ВР-32)"), UmZoneBadges::Plan(Off).Hidden, FString(TEXT("off")));
  }
  {
    FUmZoneBadgeInput In = Hover({TEXT("gray"), TEXT("green")});
    In.Avoid.Add(FS08ScreenRect(820.0f, 440.0f, 880.0f, 560.0f));  // a figure on the anchor
    const FUmZonePlan P = UmZoneBadges::Plan(In);
    TestTrue(FString::Printf(TEXT("a covered figure: the column moves right of it (x0 %.0f)"), P.Column.X0), P.bMoved && P.Column.X0 >= 880.0f);
    TestEqual(TEXT("... and covers nothing"), P.Overlap, 0.0);
  }
  // the contrast rule (02 §7.4, ВР-68): gray -> navy 13.6 : 1, purple -> card.glyph 5.7 : 1, brown -> card.glyph
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  bool bNavy = false;
  TestEqual(TEXT("profile marmoreal-original: 8 zone colours"), ProfileDiscs(TEXT("marmoreal-original")).Num(), 8);
  TestEqual(TEXT("profile sarpedon-original: 6 zone colours (no gray, no violet)"), ProfileDiscs(TEXT("sarpedon-original")).Num(), 6);
  UmZoneBadges::InkFor(Marm(TEXT("gray")), &bNavy);
  TestTrue(TEXT("gray: navy glyph"), bNavy);
  UmZoneBadges::InkFor(Marm(TEXT("purple")), &bNavy);
  TestFalse(TEXT("purple: card.glyph"), bNavy);
  UmZoneBadges::InkFor(Marm(TEXT("brown")), &bNavy);
  TestFalse(TEXT("brown: card.glyph"), bNavy);
  for (const TCHAR* Profile : {TEXT("marmoreal-original"), TEXT("sarpedon-original")}) {
    for (const TPair<FName, FColor>& P : ProfileDiscs(Profile)) {
      const double C = UmZoneBadges::Contrast(UmZoneBadges::InkFor(P.Value), FLinearColor::FromSRGBColor(P.Value));
      TestTrue(FString::Printf(TEXT("glyph to disc %s %s: %.2f : 1 >= 3"), Profile, *P.Key.ToString(), C), C >= 3.0);
    }
  }
  // the widget: the icons with the profile disc and the ink, the SHOT line
  FWorld W(TEXT("UmHudZoneBadges"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  UUmZoneBadges* Z = CreateWidget<UUmZoneBadges>(W.World, UUmZoneBadges::StaticClass());
  if (!TestNotNull(TEXT("zone badges"), Z)) return false;
  Z->SetReducedForTest(1);
  Z->ApplyInput(Hover({TEXT("gray"), TEXT("purple")}));
  FLinearColor Disc, Ink;
  TestTrue(TEXT("gray shown"), Z->GetShownColors(TEXT("gray"), Disc, Ink));
  TestTrue(TEXT("gray: the disc is the profile colour"), Disc.Equals(FLinearColor::FromSRGBColor(Marm(TEXT("gray")))));
  TestTrue(TEXT("gray: the glyph card.navy"), Ink.Equals(Theme.Color(TEXT("card.navy"))));
  TestTrue(TEXT("purple shown"), Z->GetShownColors(TEXT("purple"), Disc, Ink));
  TestTrue(TEXT("purple: the glyph card.glyph"), Ink.Equals(Theme.Color(TEXT("card.glyph"))));
  const int32 Applies = Z->GetApplyCount();
  Z->ApplyInput(Hover({TEXT("gray"), TEXT("purple")}));
  TestEqual(TEXT("the same hover: no work"), Z->GetApplyCount(), Applies);
  TArray<FString> Lines;
  Z->CollectShotLines(Lines);
  TestTrue(FString::Printf(TEXT("SHOT: %s"), Lines.Num() ? *Lines[0] : TEXT("none")),
           Lines.Num() == 1 && Lines[0].StartsWith(TEXT("SHOT widget id=zone impl=umg state=shown ")) &&
               Lines[0].Contains(TEXT(" space=M04 keys=gray,purple shown=2 more=0 px=30 tex=32 ")));
  Z->ApplyInput(Hover({TEXT("gray")}, 30.0f));
  Lines.Reset();
  Z->CollectShotLines(Lines);
  TestTrue(TEXT("below 24 px: SHOT state=hidden"), Lines.Num() == 1 && Lines[0].Contains(TEXT(" state=hidden ")) && Lines[0].Contains(TEXT("hidden=small")));
  // the rollback key (VS-3 item 16)
  const S08ArtLook::FS08SlateHudBlocks Blocks = S08ArtLook::ParseSlateHud(TEXT("-S08SlateHud=zone"));
  TestTrue(TEXT("-S08SlateHud=zone: the zone block on the old path"), Blocks.IsSlate(FName(TEXT("zone"))) && Blocks.Unknown.Num() == 0);
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
