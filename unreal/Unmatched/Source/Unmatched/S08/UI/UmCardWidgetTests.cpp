// VS-3 automation tests of the card widget (docs/game-design/visual/06-tasks/cards-portraits.csv CP-14...CP-20):
//   Unmatched.S08.Hud.Card.Tree      CP-15  BuildDefaultTree, every BindWidget, only the card takes the pointer; the
//                                           generated WBP_UmCard is a child of the base; the show sizes (ВР-70).
//   Unmatched.S08.Hud.Card.Fit       CP-15  the window 142 x 200 at 150 x 208 and the other windows (show - 2 x band);
//                                           contain of RU 287 x 398, EN 250 x 349 and the back 758 x 1051 (gap <= 3 su,
//                                           the drawn aspect within 1 px of the source); the widget draws that size.
//   Unmatched.S08.Hud.Card.Cap       CP-15  1080p 100 %: hand / combat <= 1.0, the inspector <= 1.6 without the cap;
//                                           1440p 150 %: the inspector capped to 1.6 (capped=1), the hover scale too.
//   Unmatched.S08.Hud.Card.Key       CP-03...CP-06, CP-15  the 54 MVP scans and 2 backs found by heroSlug:cardSlug of the
//                                           S01 decks (16 + 11 cards, 30 copies each) and loaded; an unknown key falls
//                                           back with a Warning; -S08CardArtLegacy falls back without one; a face-down
//                                           card keeps no face (QA-005).
//   Unmatched.S08.Hud.Card.Material  CP-14  M_UmCardFace: UI domain, translucent, Face / UVRect / Desaturation / Opacity,
//                                           Rec.709 weights; UVRect cuts the padding; the card.frame.* skins x1 / x2 with
//                                           the CP-13 9-slice margins, x2 from 2.0 px per su (ВР-VS3-16).
//   Unmatched.S08.Hud.Card.States    CP-16  unplayable (0.6 / 0.7 over 150 ms, the frame unchanged, cursor, why.*), new
//                                           (the dot 0 / 72 / 120 / 180 ms, leave 120 ms), reduced motion.
//   Unmatched.S08.Hud.Card.Hover     CP-17  hover 1.5 over 150 ms (pivot bottom centre), selected 3 su, focus ring 100 ms,
//                                           lowered = no preview, the cap at 2160p 150 %, reduced = no tween.
//   Unmatched.S08.Hud.Card.Boost     CP-18  the own card into the back in 150 ms and its chip +N after the flip; the
//                                           opponent's back with the chip without a number - no value anywhere.
//   Unmatched.S08.Hud.Card.Discard   CP-19  candidate = card.frame.warning; marked = 16 su down in 150 ms + card-drop.
//   Unmatched.S08.Hud.Card.Flip      CP-20  80 + 80 ms, the face only from the edge frame (privacy), the defense delay
//                                           120 x speed, instant at speed 0, the reduced cross-fade.
//   Unmatched.S09.HudPress.Card      CP-15  synthetic clicks on UUmCardWidget n 24, holds 0 and 50 ms, a re-apply in
//                                           between: 0 lost; an unplayable card answers Refused with its why.*.
// Headless: node tools/s08/run-ue-tests.cjs "Unmatched.S08.Hud.Card+Unmatched.S09.HudPress.Card" <abs log>
#if WITH_AUTOMATION_TESTS

#include "../../S09/S09CombatStage.h"
#include "../S08AnimatedIconWidget.h"
#include "UmCardGallery.h"
#include "UmCardMedia.h"
#include "UmCardWidget.h"
#include "UmHudScale.h"
#include "UmHudTheme.h"
#include "UmText.h"
#include "Components/Image.h"
#include "Components/Overlay.h"
#include "Components/SizeBox.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Engine/Engine.h"
#include "Engine/Texture2D.h"
#include "Engine/World.h"
#include "InputCoreTypes.h"
#include "Layout/Geometry.h"
#include "Materials/Material.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/AutomationTest.h"
#include "Misc/PackageName.h"
#if WITH_EDITORONLY_DATA
#include "Materials/MaterialExpressionCustom.h"
#endif

// Named namespace (not anonymous): unity builds merge test files.
namespace UmCardTest {
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

bool Near(double A, double B, double Tol = 0.01) { return FMath::Abs(A - B) <= Tol; }

FS09CardView Card(const TCHAR* Hero, const TCHAR* Name) {
  for (const FS09CardView& C : UmCardGallery::LoadDeck(Hero)) {
    if (C.Name == Name) return C;
  }
  FS09CardView None;
  None.Name = Name;
  return None;
}

UUmCardWidget* Make(UWorld* World, double ClockMs = 0.0, int32 Reduced = 0) {
  UUmCardWidget* C = CreateWidget<UUmCardWidget>(World, UUmCardWidget::StaticClass());
  if (!C) return nullptr;
  C->SetClockOverrideMs(ClockMs);
  C->SetReducedForTest(Reduced);
  C->SetLegacyForTest(0);
  C->SetSyncLoad(true);
  return C;
}

FUmCardState State(EUmCardShow Show, const TCHAR* Hero, const TCHAR* Lang = TEXT("ru"), float PxPerSu = 1.0f,
                   bool bFaceDown = false) {
  FUmCardState S;
  S.Show = Show;
  S.HeroSlug = Hero;
  S.Lang = Lang;
  S.PxPerSu = PxPerSu;
  S.bFaceDown = bFaceDown;
  return S;
}

void At(UUmCardWidget* C, double Ms) {
  C->SetClockOverrideMs(Ms);
  C->Step();
}

FPointerEvent LeftEvent(const FVector2D& At, bool bDown) {
  TSet<FKey> Pressed;
  if (bDown) Pressed.Add(EKeys::LeftMouseButton);
  return FPointerEvent(0, At, At, Pressed, EKeys::LeftMouseButton, 0.0f, FModifierKeysState());
}

const FIntPoint RuSrc(287, 398);
const FIntPoint EnSrc(250, 349);
const FIntPoint BackSrc(758, 1051);  // 768 - 2 x 5 (ВР-VS2-CP-03)
}  // namespace UmCardTest

// ------------------------------------------------------------------------------------------------ CP-15

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmCardTreeTest,
    "Unmatched.S08.Hud.Card.Tree UUmCardWidget default tree, every BindWidget, only the card takes the pointer, WBP_UmCard",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmCardTreeTest::RunTest(const FString&) {
  using namespace UmCardTest;
  FWorld W(TEXT("UmCardTree"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  UUmCardWidget* C = Make(W.World);
  if (!TestNotNull(TEXT("card"), C)) return false;
  FString Missing;
  TestTrue(TEXT("code default tree"), C->UsesCodeDefaultTree());
  TestTrue(FString::Printf(TEXT("every BindWidget (missing: %s)"), *Missing), C->HasAllParts(&Missing));
  TestNotNull(TEXT("BoostIcon"), C->BoostIcon.Get());
  TestNotNull(TEXT("DropIcon"), C->DropIcon.Get());
  TestNotNull(TEXT("PlateIcon"), C->PlateIcon.Get());
  TestNotNull(TEXT("Spinner"), C->Spinner.Get());
  TestNotNull(TEXT("Fallback"), C->Fallback.Get());
  TestEqual(TEXT("the card takes the pointer"), C->GetVisibility(), ESlateVisibility::Visible);
  for (UWidget* Part : {static_cast<UWidget*>(C->Box), static_cast<UWidget*>(C->Card), static_cast<UWidget*>(C->Layers),
                        static_cast<UWidget*>(C->Underlay), static_cast<UWidget*>(C->Frame)}) {
    TestEqual(FString::Printf(TEXT("%s never hit-tested"), *Part->GetName()), Part->GetVisibility(), ESlateVisibility::HitTestInvisible);
  }
  TestTrue(TEXT("the card pivot is the bottom centre"), C->Card->GetRenderTransformPivot().Equals(FVector2D(0.5, 1.0)));
  // ВР-70 / ВР-CP06: the show sizes
  struct FShow { EUmCardShow Show; double W; double H; };
  for (const FShow& S : {FShow{EUmCardShow::Hand, 150, 208}, FShow{EUmCardShow::Hover, 225, 312}, FShow{EUmCardShow::Combat, 230, 319},
                         FShow{EUmCardShow::Slot, 190, 264}, FShow{EUmCardShow::Inspector, 460, 640}, FShow{EUmCardShow::DeckGrid, 150, 208},
                         FShow{EUmCardShow::ClassSHand, 120, 166}, FShow{EUmCardShow::ClassSCombat, 150, 208},
                         FShow{EUmCardShow::MiniOpp, 48, 67}, FShow{EUmCardShow::MiniChip, 32, 45}}) {
    C->ApplyModel(Card(TEXT("king-arthur"), TEXT("Excalibur")), State(S.Show, TEXT("king-arthur")));
    TestTrue(FString::Printf(TEXT("%s box %gx%g"), UmCardWidget::ShowName(S.Show), S.W, S.H),
             Near(C->Box->GetWidthOverride(), S.W) && Near(C->Box->GetHeightOverride(), S.H));
    const double Aspect = S.W / S.H;
    TestTrue(FString::Printf(TEXT("%s aspect 0.721 +- 0.010 (ВР-VS2-CP-04)"), UmCardWidget::ShowName(S.Show)), Near(Aspect, 0.721, 0.0105));
  }
  TestTrue(TEXT("EN inspector 408 x 566"), UmCardWidget::ShowSize(EUmCardShow::Inspector, true).Equals(FVector2D(408.0, 566.0)));
  TestEqual(TEXT("mini band 2 su"), UmCardWidget::BandOf(EUmCardShow::MiniOpp), 2.0f);
  TestEqual(TEXT("mini frame key"), UmCardWidget::FrameKey(true, true, true, true), FName(TEXT("card.frame.mini")));
  // the generated blueprint (tools/s08/hud_contract/ue_author_um_hud.py)
  if (FPackageName::DoesPackageExist(UUmCardWidget::WidgetBlueprintPath)) {
    UClass* Wbp = UUmCardWidget::WidgetClass();
    TestTrue(TEXT("WBP_UmCard is a child of UUmCardWidget"), Wbp && Wbp != UUmCardWidget::StaticClass() &&
                                                               Wbp->IsChildOf(UUmCardWidget::StaticClass()));
    UUmCardWidget* FromWbp = Wbp ? CreateWidget<UUmCardWidget>(W.World, Wbp) : nullptr;
    FString WbpMissing;
    TestTrue(FString::Printf(TEXT("WBP_UmCard has every part (missing: %s)"), *WbpMissing), FromWbp && FromWbp->HasAllParts(&WbpMissing));
    TestTrue(TEXT("WBP_UmCard keeps its tree"), FromWbp && !FromWbp->UsesCodeDefaultTree());
  } else {
    AddWarning(TEXT("WBP_UmCard not generated yet (tools/s08/hud_contract/ue_author_um_hud.py)"));
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmCardFitTest,
    "Unmatched.S08.Hud.Card.Fit window 142x200 at 150x208, contain of RU / EN scans and the back, the drawn size",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmCardFitTest::RunTest(const FString&) {
  using namespace UmCardTest;
  // windows of CP-13 / ВР-CP06: show - 2 x band
  struct FWin { EUmCardShow Show; bool bEn; double W; double H; };
  for (const FWin& Wi : {FWin{EUmCardShow::Hand, false, 142, 200}, FWin{EUmCardShow::Hover, false, 217, 304},
                         FWin{EUmCardShow::Combat, false, 222, 311}, FWin{EUmCardShow::Slot, false, 182, 256},
                         FWin{EUmCardShow::Inspector, false, 452, 632}, FWin{EUmCardShow::Inspector, true, 400, 558},
                         FWin{EUmCardShow::ClassSHand, false, 112, 158}, FWin{EUmCardShow::MiniOpp, false, 44, 63},
                         FWin{EUmCardShow::MiniChip, false, 28, 41}}) {
    const FUmCardFit F = UmCardWidget::Fit(UmCardWidget::ShowSize(Wi.Show, Wi.bEn), UmCardWidget::BandOf(Wi.Show),
                                           Wi.bEn ? EnSrc : RuSrc, 1.0f);
    TestTrue(FString::Printf(TEXT("%s%s window %gx%g"), UmCardWidget::ShowName(Wi.Show), Wi.bEn ? TEXT(" EN") : TEXT(""), Wi.W, Wi.H),
             Near(F.WindowSu.X, Wi.W) && Near(F.WindowSu.Y, Wi.H));
  }
  // contain (ВР-CP05, ВР-VS2-CP-01 / 02): never cropped, the gap <= 3 su a side, the aspect of the source +- 1 px
  for (const FIntPoint& Src : {RuSrc, EnSrc, BackSrc}) {
    for (const EUmCardShow Show : {EUmCardShow::Hand, EUmCardShow::Hover, EUmCardShow::Combat, EUmCardShow::Slot,
                                   EUmCardShow::Inspector, EUmCardShow::ClassSHand, EUmCardShow::MiniOpp, EUmCardShow::MiniChip}) {
      const bool bEn = Src == EnSrc;
      const FUmCardFit F = UmCardWidget::Fit(UmCardWidget::ShowSize(Show, bEn), UmCardWidget::BandOf(Show), Src, 1.0f);
      const FString What = FString::Printf(TEXT("%s %dx%d"), UmCardWidget::ShowName(Show), Src.X, Src.Y);
      TestTrue(What + TEXT(": inside the window"), F.ScanSu.X <= F.WindowSu.X + 1e-3 && F.ScanSu.Y <= F.WindowSu.Y + 1e-3);
      TestTrue(What + TEXT(": one axis fills the window"), Near(F.ScanSu.X, F.WindowSu.X, 1e-3) || Near(F.ScanSu.Y, F.WindowSu.Y, 1e-3));
      TestTrue(What + FString::Printf(TEXT(": gap <= 3 su (%.2f, %.2f)"), (F.WindowSu.X - F.ScanSu.X) / 2, (F.WindowSu.Y - F.ScanSu.Y) / 2),
               (F.WindowSu.X - F.ScanSu.X) / 2 <= 3.0 + 1e-3 && (F.WindowSu.Y - F.ScanSu.Y) / 2 <= 3.0 + 1e-3);
      // the drawn height from the drawn width differs from the source aspect by < 1 px
      TestTrue(What + TEXT(": aspect of the source within 1 px"), FMath::Abs(F.ScanSu.X * Src.Y / Src.X - F.ScanSu.Y) < 1.0);
    }
  }
  const FUmCardFit Hand = UmCardWidget::Fit(FVector2D(150, 208), 4.0f, RuSrc, 1.0f);
  TestTrue(TEXT("RU hand: 142 x 196.9"), Near(Hand.ScanSu.X, 142.0) && Near(Hand.ScanSu.Y, 142.0 * 398 / 287));
  // the widget draws that
  FWorld W(TEXT("UmCardFit"));
  UUmCardWidget* C = Make(W.World);
  if (!TestNotNull(TEXT("card"), C)) return false;
  C->ApplyModel(Card(TEXT("king-arthur"), TEXT("Excalibur")), State(EUmCardShow::Hand, TEXT("king-arthur")));
  TestTrue(TEXT("the scan texture is loaded"), C->HasFaceTexture());
  TestTrue(TEXT("the widget fit = Fit()"), C->GetFit().ScanSu.Equals(Hand.ScanSu, 1e-3));
  TestTrue(TEXT("the face brush is the scan size"), FVector2D(C->Face->GetBrush().ImageSize).Equals(Hand.ScanSu, 1e-3));
  TestTrue(TEXT("the card size = the show (no cap at 1080p)"), Near(C->Card->GetWidthOverride(), 150.0) && Near(C->Card->GetHeightOverride(), 208.0));
  // the back: the sides cropped 5 px, the logo stays (ВР-VS2-CP-03)
  C->ApplyModel(FS09CardView(), State(EUmCardShow::Combat, TEXT("medusa"), TEXT("ru"), 1.0f, true));
  TestEqual(TEXT("back face"), C->GetFace(), EUmCardFace::Back);
  const FUmCardMediaEntry* Back = UmCardMedia::FindBack(TEXT("medusa"));
  if (TestNotNull(TEXT("back:medusa in the registry"), Back)) {
    TestEqual(TEXT("back drawn source 758 x 1051"), UmCardWidget::DrawnSrcPx(*Back), BackSrc);
    const FVector4 Uv = UmCardWidget::UvRect(*Back);
    TestTrue(TEXT("back UV crops 5 px a side of 1024"), Near(Uv.X, 5.0 / 1024, 1e-6) && Near(Uv.Z, 763.0 / 1024, 1e-6));
    TestTrue(TEXT("back side crop 1.30 % <= 1.4 %"), 2.0 * UmCardWidget::BackCropPx / 768.0 <= 0.014);
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmCardCapTest,
    "Unmatched.S08.Hud.Card.Cap 1080p 100 percent hand and combat at most 1.0, inspector at most 1.6; 1440p 150 percent capped",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmCardCapTest::RunTest(const FString&) {
  using namespace UmCardTest;
  // 1080p 100 %: px per su 1
  for (const FIntPoint& Src : {RuSrc, EnSrc}) {
    const bool bEn = Src == EnSrc;
    for (const EUmCardShow Show : {EUmCardShow::Hand, EUmCardShow::Hover, EUmCardShow::Combat, EUmCardShow::Slot, EUmCardShow::DeckGrid}) {
      const FUmCardFit F = UmCardWidget::Fit(UmCardWidget::ShowSize(Show), 4.0f, Src, 1.0f);
      TestTrue(FString::Printf(TEXT("1080p %s %s: scale %.3f <= 1.0"), bEn ? TEXT("EN") : TEXT("RU"), UmCardWidget::ShowName(Show), F.Scale),
               F.Scale <= 1.0f + 1e-4 && !F.bCapped);
    }
    const FUmCardFit Insp = UmCardWidget::Fit(UmCardWidget::ShowSize(EUmCardShow::Inspector, bEn), 4.0f, Src, 1.0f);
    TestTrue(FString::Printf(TEXT("1080p inspector %s: %.3f <= 1.6, not capped"), bEn ? TEXT("EN") : TEXT("RU"), Insp.Scale),
             Insp.Scale <= 1.6f + 1e-3 && !Insp.bCapped);
  }
  // 1440p 150 % (the project DPI curve x 1.5)
  const float Px1440 = UmHudScale::ProjectDpi(1440) * 1.5f;
  TestTrue(FString::Printf(TEXT("1440p 150 %%: %.3f px per su"), Px1440), Px1440 > 1.9f);
  for (const FIntPoint& Src : {RuSrc, EnSrc}) {
    const bool bEn = Src == EnSrc;
    const FVector2D Show = UmCardWidget::ShowSize(EUmCardShow::Inspector, bEn);
    const FUmCardFit F = UmCardWidget::Fit(Show, 4.0f, Src, Px1440);
    TestTrue(FString::Printf(TEXT("1440p 150 %% inspector %s: capped to 1.6 (%.4f)"), bEn ? TEXT("EN") : TEXT("RU"), F.Scale),
             F.bCapped && Near(F.Scale, 1.6, 2e-3));
    TestTrue(TEXT("the card smaller than the show, its aspect kept"),
             F.CardSu.X < Show.X && F.CardSu.Y < Show.Y && Near(F.CardSu.X / F.CardSu.Y, Show.X / Show.Y, 1e-3));
    const FUmCardFit Hand = UmCardWidget::Fit(UmCardWidget::ShowSize(EUmCardShow::Hand), 4.0f, Src, Px1440);
    TestTrue(TEXT("the hover scale keeps the cap"), Hand.Scale * UmCardWidget::HoverScaleFor(Hand) <= 1.6f + 1e-3);
  }
  // the widget at 1440p 150 % writes capped=1
  FWorld W(TEXT("UmCardCap"));
  UUmCardWidget* C = Make(W.World);
  if (!TestNotNull(TEXT("card"), C)) return false;
  C->ApplyModel(Card(TEXT("medusa"), TEXT("The Hounds of Mighty Zeus")), State(EUmCardShow::Inspector, TEXT("medusa"), TEXT("ru"), Px1440));
  const FString Line = C->ArtLine();
  TestTrue(TEXT("CARD-ART capped=1 at 1440p 150 %: ") + Line, Line.Contains(TEXT("capped=1")) && Line.Contains(TEXT("scale=1.600")));
  TestTrue(TEXT("the card box keeps the show, the card shrinks"), Near(C->Box->GetWidthOverride(), 460.0) && C->Card->GetWidthOverride() < 460.0f);
  C->ApplyModel(Card(TEXT("medusa"), TEXT("The Hounds of Mighty Zeus")), State(EUmCardShow::Inspector, TEXT("medusa"), TEXT("ru"), 1.0f));
  TestTrue(TEXT("1080p: capped=0 ") + C->ArtLine(), C->ArtLine().Contains(TEXT("capped=0")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmCardKeyTest,
    "Unmatched.S08.Hud.Card.Key 54 MVP scans and 2 backs by heroSlug cardSlug, unknown key falls back with a Warning",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmCardKeyTest::RunTest(const FString&) {
  using namespace UmCardTest;
  UmCardMedia::ResetForTest();
  int32 Found = 0;
  int32 Loaded = 0;
  for (const TCHAR* Hero : {TEXT("king-arthur"), TEXT("medusa")}) {
    TArray<int32> Copies;
    const TArray<FS09CardView> Deck = UmCardGallery::LoadDeck(Hero, &Copies);
    int32 Sum = 0;
    for (int32 N : Copies) Sum += N;
    TestEqual(FString::Printf(TEXT("%s: cards of the S01 deck"), Hero), Deck.Num(), FCString::Strcmp(Hero, TEXT("medusa")) == 0 ? 11 : 16);
    TestEqual(FString::Printf(TEXT("%s: 30 copies"), Hero), Sum, 30);
    for (const FS09CardView& C : Deck) {
      for (const TCHAR* Lang : {TEXT("ru"), TEXT("en")}) {
        const FUmCardMediaEntry* E = UmCardMedia::FindCard(Hero, UmCardWidget::Slug(C.Name), Lang);
        if (!TestNotNull(FString::Printf(TEXT("%s.%s in the registry"), *UmCardWidget::CardKey(Hero, C.Name), Lang), E)) continue;
        ++Found;
        Loaded += UmCardMedia::LoadTexture(*E) ? 1 : 0;
      }
    }
    const FUmCardMediaEntry* Back = UmCardMedia::FindBack(Hero);
    if (TestNotNull(FString::Printf(TEXT("back:%s"), Hero), Back)) {
      TestNotNull(FString::Printf(TEXT("back:%s texture"), Hero), UmCardMedia::LoadTexture(*Back));
    }
  }
  TestEqual(TEXT("54 MVP scans in the registry"), Found, 54);
  TestEqual(TEXT("54 MVP scans loaded"), Loaded, 54);
  TestEqual(TEXT("slug rule"), UmCardWidget::Slug(TEXT("The Hounds of Mighty Zeus")), FString(TEXT("the-hounds-of-mighty-zeus")));
  TestEqual(TEXT("slug rule drops punctuation"), UmCardWidget::Slug(TEXT("Hit & Run!")), FString(TEXT("hit-run")));
  FWorld W(TEXT("UmCardKey"));
  UUmCardWidget* C = Make(W.World);
  if (!TestNotNull(TEXT("card"), C)) return false;
  // RU and EN by the language
  C->ApplyModel(Card(TEXT("medusa"), TEXT("Gaze of Stone")), State(EUmCardShow::Hand, TEXT("medusa"), TEXT("en")));
  TestEqual(TEXT("EN scan"), C->GetFace(), EUmCardFace::En);
  TestTrue(TEXT("EN texture"), C->GetTexturePath().EndsWith(TEXT("_EN")));
  C->ApplyModel(Card(TEXT("medusa"), TEXT("Gaze of Stone")), State(EUmCardShow::Hand, TEXT("medusa"), TEXT("ru")));
  TestEqual(TEXT("RU scan"), C->GetFace(), EUmCardFace::Ru);
  TestTrue(TEXT("CARD-ART lang=ru ") + C->ArtLine(), C->ArtLine().Contains(TEXT("key=medusa:gaze-of-stone lang=ru")));
  // unknown key: the 02 §6.1 fallback and one Warning with the key (INT-018 p. 4)
  AddExpectedMessagePlain(TEXT("CARD-ART fallback key=king-arthur:not-a-card"), ELogVerbosity::Warning, EAutomationExpectedMessageFlags::Contains, 1);
  UUmCardWidget* U = Make(W.World);
  FS09CardView Unknown;
  Unknown.Name = TEXT("Not A Card");
  Unknown.CardType = TEXT("ATTACK");
  Unknown.AttackValue = 3;
  U->ApplyModel(Unknown, State(EUmCardShow::Hand, TEXT("king-arthur")));
  TestEqual(TEXT("unknown key -> fallback"), U->GetFace(), EUmCardFace::Fallback);
  TestTrue(TEXT("fallback content shown"), U->Fallback && U->Fallback->GetVisibility() != ESlateVisibility::Collapsed);
  TestTrue(TEXT("the name of the data"), U->FallbackName && U->FallbackName->GetText().ToString() == TEXT("Not A Card"));
  TestTrue(TEXT("RU missing: the EN tag (INT-018 p. 3)"), U->FallbackLang && U->FallbackLang->GetVisibility() != ESlateVisibility::Collapsed);
  TestTrue(TEXT("CARD-ART lang=fallback ") + U->ArtLine(), U->ArtLine().Contains(TEXT("lang=fallback tex=fallback")));
  // -S08CardArtLegacy: the fallback face and the plate back, no Warning
  UUmCardWidget* L = Make(W.World);
  L->SetLegacyForTest(1);
  L->ApplyModel(Card(TEXT("king-arthur"), TEXT("Excalibur")), State(EUmCardShow::Hand, TEXT("king-arthur")));
  TestEqual(TEXT("legacy face"), L->GetFace(), EUmCardFace::Fallback);
  TestTrue(TEXT("legacy tex ") + L->ArtLine(), L->ArtLine().Contains(TEXT("tex=legacy")));
  L->ApplyModel(FS09CardView(), State(EUmCardShow::Hand, TEXT("king-arthur"), TEXT("ru"), 1.0f, true));
  TestTrue(TEXT("legacy back: the plate with resource-card"), L->PlateIcon && L->PlateIcon->GetVisibility() != ESlateVisibility::Collapsed &&
                                                                 !L->HasFaceTexture());
  // a face-down card keeps no face (QA-005)
  UUmCardWidget* D = Make(W.World);
  D->ApplyModel(Card(TEXT("king-arthur"), TEXT("Excalibur")), State(EUmCardShow::Combat, TEXT("king-arthur"), TEXT("ru"), 1.0f, true));
  TestTrue(TEXT("face down: no name in the widget"), D->GetCard().Name.IsEmpty() && D->GetCard().BoostValue == 0);
  TestTrue(TEXT("face down: back:king-arthur ") + D->ArtLine(), D->ArtLine().Contains(TEXT("key=back:king-arthur lang=back")) &&
                                                               !D->ArtLine().Contains(TEXT("excalibur")));
  TestTrue(TEXT("the back texture"), D->GetTexturePath().Contains(TEXT("T_CardBack_king_arthur")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmCardMaterialTest,
    "Unmatched.S08.Hud.Card.Material M_UmCardFace parameters, Rec709 desaturation, UVRect cuts the padding, card frame skins",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmCardMaterialTest::RunTest(const FString&) {
  using namespace UmCardTest;
  UMaterialInterface* M = LoadObject<UMaterialInterface>(nullptr, UmCardWidget::MaterialPath, nullptr, LOAD_NoWarn | LOAD_Quiet);
  if (!TestNotNull(TEXT("M_UmCardFace (tools/art/cards/ue_card_face_material.py)"), M)) return false;
  UMaterial* Base = M->GetMaterial();
  TestTrue(TEXT("User Interface domain"), Base && Base->MaterialDomain == MD_UI);
  TestTrue(TEXT("translucent"), Base && Base->GetBlendMode() == BLEND_Translucent);
  auto Names = [](const TArray<FMaterialParameterInfo>& Infos) {
    TSet<FName> Out;
    for (const FMaterialParameterInfo& I : Infos) Out.Add(I.Name);
    return Out;
  };
  TArray<FMaterialParameterInfo> Infos;
  TArray<FGuid> Ids;
  M->GetAllScalarParameterInfo(Infos, Ids);
  const TSet<FName> Scalars = Names(Infos);
  M->GetAllVectorParameterInfo(Infos, Ids);
  const TSet<FName> Vectors = Names(Infos);
  M->GetAllTextureParameterInfo(Infos, Ids);
  const TSet<FName> Textures = Names(Infos);
  TestTrue(TEXT("Face texture"), Textures.Contains(UmCardWidget::ParamFace));
  TestTrue(TEXT("UVRect vector"), Vectors.Contains(UmCardWidget::ParamUvRect));
  TestTrue(TEXT("Desaturation / Opacity scalars"), Scalars.Contains(UmCardWidget::ParamDesaturation) && Scalars.Contains(UmCardWidget::ParamOpacity));
#if WITH_EDITORONLY_DATA
  bool bRec709 = false;
  int32 Samples = 0;
  for (UMaterialExpression* E : Base->GetExpressions()) {
    if (const UMaterialExpressionCustom* Custom = Cast<UMaterialExpressionCustom>(E)) {
      bRec709 |= Custom->Code.Contains(TEXT("0.2126")) && Custom->Code.Contains(TEXT("0.7152")) && Custom->Code.Contains(TEXT("0.0722"));
      int32 From = 0;
      while ((From = Custom->Code.Find(TEXT("Texture2DSample"), ESearchCase::CaseSensitive, ESearchDir::FromStart, From)) != INDEX_NONE) {
        ++Samples;
        From += 15;
      }
    }
  }
  TestTrue(TEXT("Desaturation by the Rec.709 weights"), bRec709);
  TestEqual(TEXT("one texture sample (budget)"), Samples, 1);
#endif
  // the widget: UVRect = (0, 0, src / pad) cuts the padding; unplayable = 0.6 / 0.7
  FWorld W(TEXT("UmCardMaterial"));
  UUmCardWidget* C = Make(W.World, 0.0, 1);
  if (!TestNotNull(TEXT("card"), C)) return false;
  C->ApplyModel(Card(TEXT("king-arthur"), TEXT("Excalibur")), State(EUmCardShow::Hand, TEXT("king-arthur")));
  UMaterialInstanceDynamic* Mid = C->GetFaceMid();
  if (TestNotNull(TEXT("the face MID"), Mid)) {
    FLinearColor Uv;
    Mid->GetVectorParameterValue(FHashedMaterialParameterInfo(UmCardWidget::ParamUvRect), Uv);
    TestTrue(FString::Printf(TEXT("UVRect = 0, 0, 287/512, 398/512 (%s)"), *Uv.ToString()),
             Near(Uv.R, 0.0, 1e-6) && Near(Uv.G, 0.0, 1e-6) && Near(Uv.B, 287.0 / 512, 1e-5) && Near(Uv.A, 398.0 / 512, 1e-5));
    C->SetPlayable(false, FS09Reason::Make(TEXT("why.defense.only.in.combat")));
    At(C, 200.0);
    float Desat = 0.0f, Opacity = 0.0f;
    Mid->GetScalarParameterValue(FHashedMaterialParameterInfo(UmCardWidget::ParamDesaturation), Desat);
    Mid->GetScalarParameterValue(FHashedMaterialParameterInfo(UmCardWidget::ParamOpacity), Opacity);
    TestTrue(FString::Printf(TEXT("unplayable: Desaturation 0.6 (%.3f), Opacity 0.7 (%.3f)"), Desat, Opacity), Near(Desat, 0.6) && Near(Opacity, 0.7));
  }
  // the card frame skins of CP-13 (the package verification.json margins)
  bool bFallbackTheme = true;
  const UUmHudTheme* Theme = UUmHudTheme::LoadOrFallback(UUmHudTheme::AssetPath, bFallbackTheme);
  if (!TestFalse(TEXT("DA_UmHudTheme"), bFallbackTheme) || !Theme) return false;
  struct FFrame { const TCHAR* Key; int32 M1; int32 M2; FVector2D Size; };
  for (const FFrame& F : {FFrame{TEXT("card.frame.idle"), 11, 21, FVector2D(460, 640)}, FFrame{TEXT("card.frame.hover"), 11, 21, FVector2D(460, 640)},
                          FFrame{TEXT("card.frame.selected"), 13, 25, FVector2D(460, 640)}, FFrame{TEXT("card.frame.warning"), 12, 23, FVector2D(460, 640)},
                          FFrame{TEXT("card.frame.flash"), 12, 23, FVector2D(460, 640)}, FFrame{TEXT("card.frame.focus"), 13, 25, FVector2D(468, 648)},
                          FFrame{TEXT("card.frame.mini"), 7, 13, FVector2D(48, 67)}}) {
    const FSlateBrush* X1 = Theme->CardFrames.Find(F.Key);
    const FSlateBrush* X2 = Theme->CardFramesX2.Find(F.Key);
    if (!TestTrue(FString::Printf(TEXT("%s x1 and x2 (CP-14 import)"), F.Key), X1 && X2 && X1->GetResourceObject() && X2->GetResourceObject())) continue;
    TestEqual(FString::Printf(TEXT("%s: 9-slice box"), F.Key), X1->DrawAs, ESlateBrushDrawType::Box);
    TestTrue(FString::Printf(TEXT("%s: image size %s su"), F.Key, *F.Size.ToString()), X1->ImageSize.Equals(F.Size) && X2->ImageSize.Equals(F.Size));
    TestTrue(FString::Printf(TEXT("%s: x1 margin %d px"), F.Key, F.M1), Near(X1->Margin.Left * F.Size.X, F.M1, 1e-3) && Near(X1->Margin.Top * F.Size.Y, F.M1, 1e-3));
    TestTrue(FString::Printf(TEXT("%s: x2 margin %d px"), F.Key, F.M2), Near(X2->Margin.Left * 2.0 * F.Size.X, F.M2, 1e-3));
    TestTrue(FString::Printf(TEXT("%s: x2 from 2.0 px per su, x1 below (ВР-VS3-16)"), F.Key),
             Theme->CardFrameFor(F.Key, 2.0f) == X2 && Theme->CardFrameFor(F.Key, 1.5f) == X1 &&
                 Theme->CardFrameFor(F.Key, 1.0f) == X1 && Theme->CardFrameFor(F.Key, 0.75f) == X1);
    TestTrue(FString::Printf(TEXT("%s: corner <= 13 px at x1"), F.Key), F.M1 <= 13);
  }
  const FSlateBrush* Dot = Theme->CardFrames.Find(TEXT("card.frame.new"));
  TestTrue(TEXT("card.frame.new: the dot (an image, not 9-slice)"), Dot && Dot->GetResourceObject() && Dot->DrawAs == ESlateBrushDrawType::Image);
  TestFalse(TEXT("the 29 token skins untouched"), Theme->Skins.Contains(TEXT("card.frame.idle")));
  return true;
}

// ------------------------------------------------------------------------------------------------ CP-16 ... CP-20

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmCardStatesTest,
    "Unmatched.S08.Hud.Card.States unplayable 0.6 and 0.7 over 150 ms with why, new dot 0 72 120 180 ms, reduced motion",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmCardStatesTest::RunTest(const FString&) {
  using namespace UmCardTest;
  FWorld W(TEXT("UmCardStates"));
  UUmCardWidget* C = Make(W.World);
  if (!TestNotNull(TEXT("card"), C)) return false;
  C->ApplyModel(Card(TEXT("king-arthur"), TEXT("Bewilderment")), State(EUmCardShow::Hand, TEXT("king-arthur")));
  const FName FrameBefore = C->GetFrameKey();
  C->SetPlayable(false, FS09Reason::Make(TEXT("why.defense.only.in.combat")));
  At(C, 75.0);
  TestTrue(FString::Printf(TEXT("75 ms: on the way (%.3f)"), C->GetDesaturation()), C->GetDesaturation() > 0.05f && C->GetDesaturation() < 0.55f);
  At(C, 150.0);
  TestTrue(TEXT("150 ms: desaturation 0.6, opacity 0.7"), Near(C->GetDesaturation(), 0.6) && Near(C->GetFaceOpacity(), 0.7));
  TestEqual(TEXT("the frame does not change (02 §6.3)"), C->GetFrameKey(), FrameBefore);
  TestEqual(TEXT("cursor unavailable"), C->GetCursor(), EMouseCursor::SlashedCircle);
  TestEqual(TEXT("why.* of the reason"), C->GetWhyText().ToString(), UmText::Get(EUmTable::Why, TEXT("why.defense.only.in.combat")).ToString());
  TestFalse(TEXT("why text not empty"), C->GetWhyText().IsEmpty());
  C->SetPlayable(true);
  At(C, 400.0);
  TestTrue(TEXT("playable again"), Near(C->GetDesaturation(), 0.0) && C->GetCursor() == EMouseCursor::Hand);
  // new: the dot appears (icon-motion appear) and leaves at the first hover / 10 s (the owner decides when)
  At(C, 1000.0);
  C->SetNew(true);
  At(C, 1000.0);
  TestTrue(FString::Printf(TEXT("new 0 ms: opacity 0.15 (%.3f)"), C->GetNewDotOpacity()), Near(C->GetNewDotOpacity(), 0.15));
  TestTrue(TEXT("new 0 ms: scale 0.80"), Near(C->NewDot->GetRenderTransform().Scale.X, 0.80));
  At(C, 1072.0);
  TestTrue(TEXT("new 72 ms: scale 1.04"), Near(C->NewDot->GetRenderTransform().Scale.X, 1.04));
  At(C, 1120.0);
  TestTrue(TEXT("new 120 ms: opacity 1"), Near(C->GetNewDotOpacity(), 1.0));
  At(C, 1180.0);
  TestTrue(TEXT("new 180 ms: scale 1.00"), Near(C->NewDot->GetRenderTransform().Scale.X, 1.0));
  TestTrue(TEXT("CARD-ART state=new ") + C->ArtLine(), C->ArtLine().Contains(TEXT("state=new")));
  C->SetNew(false);
  At(C, 1240.0);
  TestTrue(TEXT("leave 60 ms: fading, scale toward 0.92"), C->GetNewDotOpacity() < 1.0f && C->NewDot->GetRenderTransform().Scale.X < 1.0f);
  At(C, 1320.0);
  TestEqual(TEXT("leave 120 ms: gone"), C->GetNewDotOpacity(), 0.0f);
  // the 8 su dot + keyline at 10 su from the right and the top edge
  TestTrue(TEXT("dot image 10 su"), C->NewDot->GetBrush().ImageSize.Equals(FVector2D(10.0, 10.0)));
  // unplayable + new in the trace
  C->SetPlayable(false, FS09Reason::Make(TEXT("why.not.your.turn")));
  C->SetNew(true);
  TestTrue(TEXT("CARD-ART state=unplayable+new ") + C->ArtLine(), C->ArtLine().Contains(TEXT("state=unplayable+new")));
  // reduced motion: opacity only, 100 ms
  UUmCardWidget* R = Make(W.World, 0.0, 1);
  R->ApplyModel(Card(TEXT("medusa"), TEXT("Snipe")), State(EUmCardShow::Hand, TEXT("medusa")));
  R->SetNew(true);
  At(R, 50.0);
  TestTrue(TEXT("reduced: opacity 0.5 at 50 ms, no scale"), Near(R->GetNewDotOpacity(), 0.5) && Near(R->NewDot->GetRenderTransform().Scale.X, 1.0));
  R->SetPlayable(false);
  At(R, 150.0);
  TestTrue(TEXT("reduced: unplayable within 100 ms"), Near(R->GetDesaturation(), 0.6));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmCardHoverTest,
    "Unmatched.S08.Hud.Card.Hover hover 1.5 over 150 ms, selected and focus, lowered without preview, cap, reduced",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmCardHoverTest::RunTest(const FString&) {
  using namespace UmCardTest;
  FWorld W(TEXT("UmCardHover"));
  UUmCardWidget* C = Make(W.World);
  if (!TestNotNull(TEXT("card"), C)) return false;
  C->ApplyModel(Card(TEXT("medusa"), TEXT("Gaze of Stone")), State(EUmCardShow::Hand, TEXT("medusa")));
  C->SetHover(true);
  At(C, 0.0);
  TestTrue(TEXT("0 ms: at rest 1 (an idle card is never scaled)"), Near(C->GetScale(), 1.0));
  At(C, 75.0);
  TestTrue(FString::Printf(TEXT("75 ms: between 1 and 1.5 (%.3f)"), C->GetScale()), C->GetScale() > 1.2f && C->GetScale() < 1.5f);
  At(C, 150.0);
  TestTrue(TEXT("150 ms: 1.5 (225 x 312)"), Near(C->GetScale(), 1.5));
  TestTrue(TEXT("render transform scale 1.5"), Near(C->Card->GetRenderTransform().Scale.Y, 1.5));
  TestEqual(TEXT("hover frame card.cream"), C->GetFrameKey(), FName(TEXT("card.frame.hover")));
  TestTrue(TEXT("CARD-ART state=hover ") + C->ArtLine(), C->ArtLine().Contains(TEXT("state=hover")));
  TestTrue(TEXT("hovered scan <= 1.6"), C->GetFit().Scale * C->GetScale() <= 1.6f + 1e-3);
  C->SetSelected(true);
  TestEqual(TEXT("selected + hover: the selected edge 3 su"), C->GetFrameKey(), FName(TEXT("card.frame.selected")));
  C->SetHover(false);
  At(C, 400.0);
  TestTrue(TEXT("hover off: back to 1"), Near(C->GetScale(), 1.0));
  TestEqual(TEXT("selected"), C->GetFrameKey(), FName(TEXT("card.frame.selected")));
  C->SetSelected(false);
  C->SetFocus(true);
  At(C, 450.0);
  TestTrue(TEXT("focus 50 ms: ring appearing"), C->GetFocusOpacity() > 0.0f && C->GetFocusOpacity() < 1.0f);
  At(C, 500.0);
  TestTrue(TEXT("focus 100 ms: ring shown"), Near(C->GetFocusOpacity(), 1.0));
  TestEqual(TEXT("focus keeps the idle edge (the ring is its own layer)"), C->GetFrameKey(), FName(TEXT("card.frame.idle")));
  // lowered (SD-26): no preview
  C->SetLowered(true);
  C->SetHover(true);
  At(C, 800.0);
  TestTrue(TEXT("lowered: no preview scale"), Near(C->GetScale(), 1.0));
  C->SetLowered(false);
  C->SetHover(false);
  // the cap at 2160p 150 % (3 px per su): the hovered scan stays <= 1.6
  UUmCardWidget* Big = Make(W.World);
  Big->ApplyModel(Card(TEXT("medusa"), TEXT("Gaze of Stone")), State(EUmCardShow::Hand, TEXT("medusa"), TEXT("en"), 3.0f));
  Big->SetHover(true);
  At(Big, 200.0);
  TestTrue(FString::Printf(TEXT("2160p 150 %%: hover %.3f x scan %.3f <= 1.6"), Big->GetScale(), Big->GetFit().Scale),
           Big->GetFit().Scale * Big->GetScale() <= 1.6f + 1e-3 && Big->GetScale() < 1.5f);
  // reduced: no tween
  UUmCardWidget* R = Make(W.World, 0.0, 1);
  R->ApplyModel(Card(TEXT("medusa"), TEXT("Gaze of Stone")), State(EUmCardShow::Hand, TEXT("medusa")));
  R->SetHover(true);
  At(R, 0.0);
  TestTrue(TEXT("reduced: scale without a tween"), Near(R->GetScale(), 1.5));
  // a mini never previews
  UUmCardWidget* M = Make(W.World);
  M->ApplyModel(FS09CardView(), State(EUmCardShow::MiniOpp, TEXT("medusa"), TEXT("ru"), 1.0f, true));
  M->SetHover(true);
  At(M, 300.0);
  TestTrue(TEXT("mini: no preview, mini-idle frame"), Near(M->GetScale(), 1.0) && M->GetFrameKey() == FName(TEXT("card.frame.mini")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmCardBoostTest,
    "Unmatched.S08.Hud.Card.Boost own boost face down with chip plus N after the flip, opponent chip without a number",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmCardBoostTest::RunTest(const FString&) {
  using namespace UmCardTest;
  FWorld W(TEXT("UmCardBoost"));
  UUmCardWidget* Own = Make(W.World);
  if (!TestNotNull(TEXT("card"), Own)) return false;
  const FS09CardView Noble = Card(TEXT("king-arthur"), TEXT("Noble Sacrifice"));
  Own->ApplyModel(Noble, State(EUmCardShow::Hand, TEXT("king-arthur")));
  Own->SetFaceDown(true);
  Own->SetBoostChip(Noble.BoostValue);
  At(Own, 37.5);
  TestTrue(FString::Printf(TEXT("37.5 ms: turning (%.3f)"), Own->GetScaleX()), Own->GetScaleX() > 0.0f && Own->GetScaleX() < 1.0f);
  TestEqual(TEXT("37.5 ms: still the face"), Own->GetFace(), EUmCardFace::Ru);
  At(Own, 75.0);
  TestEqual(TEXT("75 ms: the edge - the back swapped in"), Own->GetFace(), EUmCardFace::Back);
  TestTrue(TEXT("75 ms: scaleX 0"), Near(Own->GetScaleX(), 0.0));
  At(Own, 100.0);
  TestEqual(TEXT("chip waits for the flip"), Own->GetChipOpacity(), 0.0f);
  At(Own, 150.0);
  TestTrue(TEXT("150 ms: the back, scaleX 1, the chip appears (0.15)"), Near(Own->GetScaleX(), 1.0) && Near(Own->GetChipOpacity(), 0.15));
  At(Own, 330.0);
  TestTrue(TEXT("330 ms: the chip at rest"), Near(Own->GetChipOpacity(), 1.0));
  TestEqual(TEXT("+N is runtime text from the data"), Own->GetChipText(), FString(TEXT("+3")));
  TestTrue(TEXT("CARD-ART lang=back state=back+boost ") + Own->ArtLine(),
           Own->ArtLine().Contains(TEXT("lang=back")) && Own->ArtLine().Contains(TEXT("boost")) && Own->ArtLine().Contains(TEXT("chip=1")));
  TestTrue(TEXT("the trace carries no value"), !Own->ArtLine().Contains(TEXT("+3")));
  // the opponent's boost: the back, the chip without a number - no face, no value in the widget (ВР-CP11, QA-005)
  UUmCardWidget* Opp = Make(W.World);
  Opp->ApplyModel(Noble, State(EUmCardShow::Hand, TEXT("king-arthur"), TEXT("ru"), 1.0f, true));
  Opp->SetBoostChip(UmCardWidget::HiddenBoost);
  At(Opp, 400.0);
  TestTrue(TEXT("opp: the chip shown"), Near(Opp->GetChipOpacity(), 1.0));
  TestTrue(TEXT("opp: no number"), Opp->GetChipText().IsEmpty() && Opp->BoostText->GetVisibility() == ESlateVisibility::Collapsed);
  TestTrue(TEXT("opp: no face in the widget"), Opp->GetCard().Name.IsEmpty() && Opp->GetCard().BoostValue == 0 && !Opp->GetCard().bHasBoostValue);
  TestTrue(TEXT("opp: the trace names the back only ") + Opp->ArtLine(),
           Opp->ArtLine().Contains(TEXT("key=back:king-arthur")) && !Opp->ArtLine().Contains(TEXT("noble")));
  // reduced: a cross-fade of 100 ms, the chip by opacity
  UUmCardWidget* R = Make(W.World, 0.0, 1);
  R->ApplyModel(Noble, State(EUmCardShow::Hand, TEXT("king-arthur")));
  R->SetFaceDown(true);
  At(R, 25.0);
  TestTrue(TEXT("reduced: the face fades, no turn"), Near(R->GetScaleX(), 1.0) && Near(R->GetFaceOpacity(), 0.5));
  At(R, 100.0);
  TestEqual(TEXT("reduced: the back after 100 ms"), R->GetFace(), EUmCardFace::Back);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmCardDiscardTest,
    "Unmatched.S08.Hud.Card.Discard candidate warning edge, marked 16 su down in 150 ms with card-drop",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmCardDiscardTest::RunTest(const FString&) {
  using namespace UmCardTest;
  FWorld W(TEXT("UmCardDiscard"));
  UUmCardWidget* C = Make(W.World);
  if (!TestNotNull(TEXT("card"), C)) return false;
  C->ApplyModel(Card(TEXT("medusa"), TEXT("Dash")), State(EUmCardShow::Hand, TEXT("medusa")));
  C->SetDiscardCandidate(true);
  TestEqual(TEXT("candidate: card.frame.warning 2 su"), C->GetFrameKey(), FName(TEXT("card.frame.warning")));
  C->SetMarkedForDiscard(true);
  At(C, 75.0);
  TestTrue(FString::Printf(TEXT("75 ms: going down (%.2f)"), C->GetShiftSu()), C->GetShiftSu() > 4.0f && C->GetShiftSu() < 16.0f);
  At(C, 150.0);
  TestTrue(TEXT("150 ms: 16 su down"), Near(C->GetShiftSu(), 16.0));
  TestTrue(TEXT("render transform y +16"), Near(C->Card->GetRenderTransform().Translation.Y, 16.0));
  At(C, 180.0);
  TestTrue(TEXT("card-drop at rest"), Near(C->GetDropOpacity(), 1.0));
  TestTrue(TEXT("CARD-ART state=discard+marked ") + C->ArtLine(), C->ArtLine().Contains(TEXT("discard+marked")));
  C->SetMarkedForDiscard(false);
  At(C, 330.0);
  TestTrue(TEXT("unmarked: back up, the icon gone"), Near(C->GetShiftSu(), 0.0) && C->GetDropOpacity() == 0.0f);
  TestEqual(TEXT("still a candidate"), C->GetFrameKey(), FName(TEXT("card.frame.warning")));
  UUmCardWidget* R = Make(W.World, 0.0, 1);
  R->ApplyModel(Card(TEXT("medusa"), TEXT("Dash")), State(EUmCardShow::Hand, TEXT("medusa")));
  R->SetMarkedForDiscard(true);
  At(R, 0.0);
  TestTrue(TEXT("reduced: no shift tween"), Near(R->GetShiftSu(), 16.0));
  At(R, 50.0);
  TestTrue(TEXT("reduced: the icon by opacity"), Near(R->GetDropOpacity(), 0.5));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmCardFlipTest,
    "Unmatched.S08.Hud.Card.Flip reveal 80 plus 80 ms, face only from the edge frame, defense delay 120, reduced cross-fade",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmCardFlipTest::RunTest(const FString&) {
  using namespace UmCardTest;
  FWorld W(TEXT("UmCardFlip"));
  UUmCardWidget* A = Make(W.World);
  if (!TestNotNull(TEXT("card"), A)) return false;
  FS09CardView Hidden;
  Hidden.InstanceId = TEXT("hidden-0");
  A->ApplyModel(Hidden, State(EUmCardShow::Combat, TEXT("king-arthur"), TEXT("ru"), 1.0f, true));
  const FS09CardView Excalibur = Card(TEXT("king-arthur"), TEXT("Excalibur"));
  A->Flip(true, 1.0f, &Excalibur);
  At(A, 40.0);
  TestTrue(FString::Printf(TEXT("40 ms: scaleX 0.75 ease-in-quad (%.3f)"), A->GetScaleX()), Near(A->GetScaleX(), 0.75));
  TestEqual(TEXT("40 ms: still the back"), A->GetFace(), EUmCardFace::Back);
  TestTrue(TEXT("40 ms: no face in the widget (privacy)"), A->GetCard().Name.IsEmpty() && !A->ArtLine().Contains(TEXT("excalibur")));
  At(A, 80.0);
  TestTrue(TEXT("80 ms: the edge (scaleX 0) - nothing drawn"), Near(A->GetScaleX(), 0.0));
  TestEqual(TEXT("80 ms: the face swapped in"), A->GetFace(), EUmCardFace::Ru);
  TestTrue(TEXT("80 ms: the key of the revealed card"), A->GetFaceKey() == TEXT("king-arthur:excalibur"));
  At(A, 120.0);
  TestTrue(FString::Printf(TEXT("120 ms: scaleX 0.75 ease-out-quad (%.3f)"), A->GetScaleX()), Near(A->GetScaleX(), 0.75));
  At(A, 160.0);
  TestTrue(TEXT("160 ms: the face at scaleX 1, scan 230 x 319 whole"), Near(A->GetScaleX(), 1.0) && !A->IsFlipping() && A->HasFaceTexture());
  TestTrue(TEXT("CARD-ART state=reveal ") + A->ArtLine(), A->ArtLine().Contains(TEXT("state=reveal")) && A->ArtLine().Contains(TEXT("show=combat")));
  // the defense card turns 120 ms later (x the combat speed)
  TestEqual(TEXT("defense delay 120"), UmCardWidget::DefenseFlipDelayMs(1.0f), static_cast<float>(FS09CombatTiming::DefenseFlipDelayMs));
  TestEqual(TEXT("defense delay fast 60"), UmCardWidget::DefenseFlipDelayMs(0.5f), 60.0f);
  TestEqual(TEXT("defense delay slow 180"), UmCardWidget::DefenseFlipDelayMs(1.5f), 180.0f);
  TestTrue(TEXT("flip + defense delay inside FlipMs 620"),
           UmCardWidget::RevealFlipMs + UmCardWidget::DefenseFlipDelayMs(1.0f) <= FS09CombatTiming::FlipMs);
  UUmCardWidget* D = Make(W.World);
  D->ApplyModel(Hidden, State(EUmCardShow::Combat, TEXT("medusa"), TEXT("ru"), 1.0f, true));
  const FS09CardView Hiss = Card(TEXT("medusa"), TEXT("Hiss and Slither"));
  At(D, UmCardWidget::DefenseFlipDelayMs(1.0f));
  D->Flip(true, 1.0f, &Hiss);
  At(D, 199.0);
  TestEqual(TEXT("defense 199 ms: still the back"), D->GetFace(), EUmCardFace::Back);
  At(D, 200.0);
  TestEqual(TEXT("defense 200 ms (120 + 80): the face"), D->GetFace(), EUmCardFace::Ru);
  At(D, 280.0);
  TestTrue(TEXT("defense 280 ms: done"), !D->IsFlipping() && Near(D->GetScaleX(), 1.0));
  // speed 0 ("none"): instant
  UUmCardWidget* I = Make(W.World);
  I->ApplyModel(Hidden, State(EUmCardShow::Combat, TEXT("medusa"), TEXT("ru"), 1.0f, true));
  I->Flip(true, 0.0f, &Hiss);
  TestEqual(TEXT("speed 0: the face at once"), I->GetFace(), EUmCardFace::Ru);
  // reduced: a 100 ms cross-fade, no turn
  UUmCardWidget* R = Make(W.World, 0.0, 1);
  R->ApplyModel(Hidden, State(EUmCardShow::Combat, TEXT("medusa"), TEXT("ru"), 1.0f, true));
  R->Flip(true, 1.0f, &Hiss);
  At(R, 25.0);
  TestTrue(TEXT("reduced 25 ms: back fading, no scaleX"), Near(R->GetScaleX(), 1.0) && Near(R->GetFaceOpacity(), 0.5) &&
                                                            R->GetFace() == EUmCardFace::Back);
  At(R, 50.0);
  TestEqual(TEXT("reduced 50 ms: the face"), R->GetFace(), EUmCardFace::Ru);
  At(R, 100.0);
  TestTrue(TEXT("reduced 100 ms: done"), !R->IsFlipping() && Near(R->GetFaceOpacity(), 1.0));
  // the curve
  TestTrue(TEXT("FlipScaleX 0 / 80 / 160"), Near(UmCardWidget::FlipScaleX(0, 160), 1.0) && Near(UmCardWidget::FlipScaleX(80, 160), 0.0) &&
                                              Near(UmCardWidget::FlipScaleX(160, 160), 1.0));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmCardPressTest,
    "Unmatched.S09.HudPress.Card synthetic clicks on UUmCardWidget n 24, holds 0 and 50 ms, a re-apply in between, 0 lost",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmCardPressTest::RunTest(const FString&) {
  using namespace UmCardTest;
  FWorld W(TEXT("UmCardPress"));
  TSharedPtr<FS09HudPressArbiter> Arbiter = MakeShared<FS09HudPressArbiter>();
  uint64 Frame = 2000;
  Arbiter->SetFrameClock([&Frame]() { return Frame; });
  UUmCardWidget* C = Make(W.World);
  if (!TestNotNull(TEXT("card"), C)) return false;
  int32 Acts = 0, Refused = 0;
  FName LastWhy;
  C->SetPress(TEXT("hand.card::3"), Arbiter, FS09OnHudPressOutcome::CreateLambda([&](const FS09HudPressOutcome& O) {
    if (O.Result == ES09HudPressResult::Act) ++Acts;
    if (O.Result == ES09HudPressResult::Refused) {
      ++Refused;
      LastWhy = O.Reason.Key;
    }
  }));
  const FS09CardView Data = Card(TEXT("medusa"), TEXT("Gaze of Stone"));
  const FUmCardState S = State(EUmCardShow::Hand, TEXT("medusa"));
  C->ApplyModel(Data, S);
  const FGeometry Geo = FGeometry::MakeRoot(FVector2D(150.0, 208.0), FSlateLayoutTransform());
  const FVector2D Centre(75.0, 104.0);
  const int32 N = 24;
  for (int32 I = 0; I < N; ++I) {
    const int32 HoldFrames = (I % 2) ? 3 : 0;
    C->NativeOnMouseButtonDown(Geo, LeftEvent(Centre, true));
    for (int32 F = 0; F < HoldFrames; ++F) {
      ++Frame;
      Arbiter->NoteRebuild();  // a snapshot re-applies the hand while the card is held (the pool keeps the widget)
      C->ApplyModel(Data, S);
    }
    C->NativeOnMouseButtonUp(Geo, LeftEvent(Centre, false));
    ++Frame;
  }
  TestEqual(TEXT("every click answered: 0 lost"), Acts, N);
  TestEqual(TEXT("no refusal on a playable card"), Refused, 0);
  C->NativeOnMouseButtonDown(Geo, LeftEvent(Centre, true));
  C->NativeOnMouseButtonUp(Geo, LeftEvent(FVector2D(600.0, 600.0), false));
  TestEqual(TEXT("drag away: no action"), Acts, N);
  C->SetPlayable(false, FS09Reason::Make(TEXT("why.not.your.turn")));
  for (int32 I = 0; I < N; ++I) {
    C->NativeOnMouseButtonDown(Geo, LeftEvent(Centre, true));
    Frame += (I % 2) ? 3 : 0;
    C->NativeOnMouseButtonUp(Geo, LeftEvent(Centre, false));
    ++Frame;
  }
  TestEqual(TEXT("unplayable: every press refused (0 silent)"), Refused, N);
  TestTrue(TEXT("unplayable: with its why"), LastWhy == FName(TEXT("why.not.your.turn")));
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
