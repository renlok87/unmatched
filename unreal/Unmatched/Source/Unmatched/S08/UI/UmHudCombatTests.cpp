// VS-3 automation tests of the combat blocks (docs/game-design/visual/06-tasks/hud.csv HB-30...HB-33; 04-hud-spec.md
// §2.7, §7.1; the accepted mockup HB-29, ВР-VS2-HB29-03):
//   Unmatched.S08.Hud.CombatEdge.Tree     BuildDefaultTree of the edge and the centre, every BindWidget, the GAME slots
//                                         take them, the WBPs (when generated) are children of the bases.
//   Unmatched.S08.Hud.CombatEdge.Sides    the own fighter on the left whatever its role (ВР-H04): Marmoreal (Medusa's
//                                         player defends against Merlin) and Sarpedon (King Arthur's player attacks).
//   Unmatched.S08.Hud.CombatEdge.Slot     the defense slot in its three states (shield, chosen, nodefense) with their
//                                         parts, the back of the attack card, the ribbons and the SHOT states.
//   Unmatched.S08.Hud.CombatEdge.Privacy  no face of the opponent's card before state=reveal (models, SHOT lines,
//                                         CARD-ART keys), even when the projection carries one by mistake.
//   Unmatched.S08.Hud.CombatEdge.Timer    HB-31: 11 s normal, 10 s warning (edge + sign), 0 expired - the buttons refuse
//                                         with why.deadline.passed; HUD-TIMER lines; no ticker outside the window.
//   Unmatched.S08.Hud.CombatEdge.Flip     HB-32: the reveal turns the attack card at once and the defense card +120 ms
//                                         (x speed), the face set at the edge frame.
//   Unmatched.S08.Hud.CombatEdge.Leave    HB-32: after CUE-011 fade 150 + flight 200 (reduced 100), then nothing of the
//                                         old combat; a new combat cuts a leave in flight.
//   Unmatched.S08.Hud.CombatCenter.Lines  HB-33: the plan (3 lines L / 2 S, «ещё n», <= 160 su), the 2 rows + «…» of the
//                                         Winged Frenzy RU line (194 chars), the cancelled line with its X.
//   Unmatched.S08.Hud.CombatCenter.Stage  HB-33: wait -> read -> effects -> slam -> hit -> gone over a run I combat A.
// Headless: node tools/s08/run-ue-tests.cjs "Unmatched.S08.Hud.Combat" <abs log>
#if WITH_AUTOMATION_TESTS

#include "../../S09/S09CombatStage.h"
#include "../S08CueDispatcher.h"
#include "Components/Border.h"
#include "Components/Image.h"
#include "Components/TextBlock.h"
#include "Dom/JsonObject.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "HAL/PlatformTime.h"
#include "Internationalization/Internationalization.h"
#include "Internationalization/Regex.h"
#include "Internationalization/TextLocalizationManager.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "UmButton.h"
#include "UmCardWidget.h"
#include "UmGameHud.h"
#include "UmHudCombatBlocks.h"
#include "UmHudCombatCenter.h"
#include "UmHudCombatEdge.h"
#include "UmHudLayout.h"
#include "UmText.h"
#include "../S08AnimatedIconWidget.h"

namespace UmCombatTest {
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

struct FRu {
  FInternationalization::FCultureStateSnapshot Snapshot;
  FRu() {
    FInternationalization::Get().BackupCultureState(Snapshot);
    FInternationalization::Get().SetCurrentLanguageAndLocale(TEXT("ru"));
#if WITH_EDITOR  // the preview API exists only WITH_EDITOR (the VS-1 / VS-2 C2039 trap of the game target)
    FTextLocalizationManager::Get().EnableGameLocalizationPreview(TEXT("ru"));
#endif
    FTextLocalizationManager::Get().WaitForAsyncTasks();
  }
  ~FRu() { FInternationalization::Get().RestoreCultureState(Snapshot); }
};

bool ShotLineOk(const FString& Line) {
  FRegexMatcher M(FRegexPattern(TEXT("^SHOT widget id=(\\S+) impl=(umg|slate) state=(\\S+) fighter=(\\S+) "
                                     "bbox=\\((-?\\d+),(-?\\d+),(-?\\d+),(-?\\d+)\\) geom=(painted|unpainted) visible=([01]) "
                                     "twin=([01]) source=(\\S+)( .*)?$")),
                  Line);
  return M.FindNext();
}

FString Field(const FString& Line, const TCHAR* Key) {
  FString V;
  FParse::Value(*Line, *(FString(Key) + TEXT("=")), V);
  return V;
}

/** A public card of the run I combats (S01 content: name, type, values; the printed effect of the parser). */
FS09CardView Card(const TCHAR* Name, const TCHAR* Type, int32 A, int32 D, const TCHAR* EffectText, const TCHAR* Instance) {
  FS09CardView C;
  C.Name = Name;
  C.NameRu = Name;  // the backend: nameRu = nameEn for these cards (CX-12 database check)
  C.CardId = FString::Printf(TEXT("cat-%s"), Name);
  C.InstanceId = Instance;
  C.CardType = Type;
  C.AttackValue = A;
  C.DefenseValue = D;
  C.EffectText = EffectText;
  C.EffectCount = 1;
  C.bVisible = true;
  return C;
}

FS09CardView SwiftStrike() { return Card(TEXT("Swift Strike"), TEXT("ATTACK"), 3, 0, TEXT("Move your fighter up to 4 spaces."), TEXT("ka::swift")); }
FS09CardView Feint() { return Card(TEXT("Feint"), TEXT("VERSATILE"), 2, 2, TEXT("Cancel all effects on your opponent's card."), TEXT("me::feint")); }

FUmCombatFighter Fighter(const TCHAR* Id, const TCHAR* Name, const TCHAR* Owner, int32 Team, const TCHAR* Slug) {
  FUmCombatFighter F;
  F.Id = Id;
  F.Name = Name;
  F.OwnerId = Owner;
  F.TeamSlot = Team;
  F.DeckSlug = Slug;
  return F;
}

/** Combat A (run I Marmoreal seq=10): Merlin (King Arthur's side, P2) attacks Medusa (P1) - the open COMBAT window. */
FUmCombatInput OpenA(const FUmHudLayout& Layout, const TCHAR* Viewer, bool bResolve = false) {
  FUmCombatInput In;
  In.Layout = &Layout;
  In.bLive = true;
  In.ViewerId = Viewer;
  In.NowMs = 100000;
  In.NowSec = 100.0;
  In.bOpen = true;
  In.bResolvePhase = bResolve;
  In.AppliedSeq = 8;
  In.Combat.bPresent = true;
  In.Combat.AttackerId = TEXT("f-1-sk0");
  In.Combat.TargetFighterId = TEXT("f-0-hero");
  In.Combat.DefenderId = TEXT("p-medusa");
  In.Attacker = Fighter(TEXT("f-1-sk0"), TEXT("Merlin"), TEXT("p-arthur"), 1, TEXT("king-arthur"));
  In.Target = Fighter(TEXT("f-0-hero"), TEXT("Medusa"), TEXT("p-medusa"), 0, TEXT("medusa"));
  return In;
}

/** The staging of combat A at a 1 ms clock (Feint's line, Swift Strike cancelled, 3 : 2, damage 1). */
struct FStageA {
  FS08CueDispatcher Cues;
  FS09CombatStage Stage;
  TArray<FString> Lines;
  TArray<FS09CombatStageEvent> Events;
  int64 Start = 200000;
  FStageA(int32 Damage = 1, bool bNoDefense = false) {
    FS09CombatStageInput In;
    In.Seq = 10;
    In.AttackerId = TEXT("f-1-sk0");
    In.TargetId = TEXT("f-0-hero");
    In.AttackerLabel = TEXT("Merlin");
    In.TargetLabel = TEXT("Medusa");
    In.Damage = Damage;
    In.HpBefore = 16;
    In.HpAfter = 16 - Damage;
    In.ContactMs = 292;
    In.Reveal.bAttackKnown = true;
    In.Reveal.Attack = SwiftStrike();
    In.Reveal.AttackValue = 3;
    In.Reveal.bNoDefense = bNoDefense;
    if (!bNoDefense) {
      In.Reveal.bDefenseKnown = true;
      In.Reveal.Defense = Feint();
      In.Reveal.DefenseValue = 2;
      FS09CombatEffectLine L;
      L.EntryIndex = 0;
      L.bAttackerSide = false;
      L.CardName = TEXT("Feint");
      L.Text = TEXT("Cancel all effects on your opponent's card.");
      L.bPrintedText = true;
      L.Outcome = TEXT("APPLIED");
      In.Effects.Add(L);
      In.bAttackCardCancelled = true;
    } else {
      In.Reveal.DefenseValue = 0;
    }
    In.EffectLines = In.Effects.Num();
    In.bHasEffectText = true;
    Stage.Start(In, Start, Cues, Lines, Events);
  }
  void At(int64 T) {
    Stage.Tick(T, Cues, Lines, Events);
    Cues.Advance(T, Lines);
  }
};

FUmHudLayout Layout1080() {
  const FBox2D Field(FVector2D(466.0, 258.0), FVector2D(1461.0, 857.0));  // Marmoreal K1 (ВР-VS2-09)
  return FUmHudLayout::Compute(FVector2D(1920.0, 1080.0), 1.0f, &Field);
}

UUmHudCombatEdge* MakeEdge(UWorld* World, EUmEdgeSide Side, const FUmHudLayout& L) {
  UUmHudCombatEdge* E = CreateWidget<UUmHudCombatEdge>(World, UUmHudCombatEdge::StaticClass());
  if (!E) return nullptr;
  E->SetSide(Side);
  E->SetSyncLoad(true);
  FUmCombatEdgeFrame F;
  F.bClassS = L.bClassS;
  F.PxPerSu = L.PxPerSu;
  const bool bOwn = Side == EUmEdgeSide::Own;
  F.OriginSu = UmGameHudSlots::SlotRect(L, bOwn ? EUmGameSlot::CombatEdgeL : EUmGameSlot::CombatEdgeR).Min;
  const FBox2D B = L.Rect(bOwn ? EUmHudBlock::CombatL : EUmHudBlock::CombatR);
  F.CardSu = FBox2D(B.Min, B.Min + UmHudCombatEdge::CardSize(L.bClassS));
  if (bOwn) {
    const FBox2D D = L.Rect(EUmHudBlock::Defend);
    const float H = L.bClassS ? 40.0f : 48.0f;
    F.DefendSu = FBox2D(D.Min, FVector2D(D.Max.X, D.Min.Y + H));
    F.NoDefenseSu = FBox2D(FVector2D(D.Min.X, D.Max.Y - H), D.Max);
  }
  F.LeaveToSu = bOwn ? L.DiscardChipCentreSu() : FVector2D(L.Rect(EUmHudBlock::PanelOpp).GetCenter());
  E->SetFrame(F);
  return E;
}
}  // namespace UmCombatTest

using namespace UmCombatTest;

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmCombatEdgeTreeTest, "Unmatched.S08.Hud.CombatEdge.Tree",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FUmCombatEdgeTreeTest::RunTest(const FString& Parameters) {
  FWorld W(TEXT("UmCombatTree"));
  if (!TestNotNull(TEXT("world"), W.World)) return false;
  UUmHudCombatEdge* E = CreateWidget<UUmHudCombatEdge>(W.World, UUmHudCombatEdge::StaticClass());
  FString Missing;
  TestTrue(TEXT("edge: the code tree"), E && E->UsesCodeDefaultTree());
  TestTrue(FString::Printf(TEXT("edge: every BindWidget (%s)"), *Missing), E && E->HasAllParts(&Missing));
  TestTrue(TEXT("edge: the optional parts too"), E && E->SlotFrame && E->SlotGlyph && E->SlotText && E->CaptionPlate &&
                                                    E->CaptionText && E->WarnEdge && E->TeamChip && E->TimerTrack && E->WarnIcon);
  UUmHudCombatCenter* C = CreateWidget<UUmHudCombatCenter>(W.World, UUmHudCombatCenter::StaticClass());
  Missing.Reset();
  TestTrue(FString::Printf(TEXT("centre: every BindWidget (%s)"), *Missing), C && C->HasAllParts(&Missing));
  // the GAME slots take the blocks
  UUmGameHud* Game = CreateWidget<UUmGameHud>(W.World, UUmGameHud::StaticClass());
  if (TestNotNull(TEXT("game"), Game)) {
    UUmHudCombatEdge* L = CreateWidget<UUmHudCombatEdge>(Game, UUmHudCombatEdge::StaticClass());
    UUmHudCombatEdge* R = CreateWidget<UUmHudCombatEdge>(Game, UUmHudCombatEdge::StaticClass());
    UUmHudCombatCenter* Ctr = CreateWidget<UUmHudCombatCenter>(Game, UUmHudCombatCenter::StaticClass());
    TestTrue(TEXT("CombatEdgeL / R / CombatCenter slots"), Game->SetBlock(EUmGameSlot::CombatEdgeL, L) &&
                                                               Game->SetBlock(EUmGameSlot::CombatEdgeR, R) &&
                                                               Game->SetBlock(EUmGameSlot::CombatCenter, Ctr));
  }
  // the slot rects (VS-3: the column with the caption above and the buttons; the centre 560 x 168 at y 80)
  const FUmHudLayout L = Layout1080();
  const FBox2D SlotL = UmGameHudSlots::SlotRect(L, EUmGameSlot::CombatEdgeL);
  TestTrue(FString::Printf(TEXT("the left edge column (%.0f,%.0f)-(%.0f,%.0f) holds caption, card, ribbon, buttons"), SlotL.Min.X,
                           SlotL.Min.Y, SlotL.Max.X, SlotL.Max.Y),
           FMath::IsNearlyEqual(SlotL.Min.Y, 332.0) && SlotL.Max.Y >= 851.0 && FMath::IsNearlyEqual(SlotL.Min.X, 24.0));
  const FBox2D SlotC = UmGameHudSlots::SlotRect(L, EUmGameSlot::CombatCenter);
  TestTrue(TEXT("the centre slot 560 su at y 80"), FMath::IsNearlyEqual(SlotC.Min.X, 680.0) && FMath::IsNearlyEqual(SlotC.Min.Y, 80.0) &&
                                                       FMath::IsNearlyEqual(SlotC.Max.X - SlotC.Min.X, 560.0));
  TestEqual(TEXT("the combat rects keep out of FIELD (overlapField)"), L.OverlapFieldPx2, 0.0);
  // the WBPs, once generated (ue_author_um_hud.py), are children of the bases
  const TPair<UClass*, const TCHAR*> Wbps[] = {{UUmHudCombatEdge::StaticClass(), UUmHudCombatEdge::WidgetBlueprintPath},
                                               {UUmHudCombatCenter::StaticClass(), UUmHudCombatCenter::WidgetBlueprintPath}};
  for (const TPair<UClass*, const TCHAR*>& Wbp : Wbps) {
    UClass* Cls = UmGameHudSlots::WbpOrNative(Wbp.Key, Wbp.Value);
    if (Cls != Wbp.Key) {
      TestTrue(FString::Printf(TEXT("%s a child of its base"), Wbp.Value), Cls && Cls->IsChildOf(Wbp.Key));
      UUserWidget* Made = CreateWidget<UUserWidget>(W.World, Cls);
      FString WbpMissing;
      if (UUmHudCombatEdge* WE = Cast<UUmHudCombatEdge>(Made)) TestTrue(FString::Printf(TEXT("WBP edge parts (%s)"), *WbpMissing), WE->HasAllParts(&WbpMissing));
      if (UUmHudCombatCenter* WC = Cast<UUmHudCombatCenter>(Made)) TestTrue(FString::Printf(TEXT("WBP centre parts (%s)"), *WbpMissing), WC->HasAllParts(&WbpMissing));
    } else {
      AddInfo(FString::Printf(TEXT("%s not generated yet (the code tree)"), Wbp.Value));
    }
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmCombatEdgeSidesTest, "Unmatched.S08.Hud.CombatEdge.Sides",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FUmCombatEdgeSidesTest::RunTest(const FString& Parameters) {
  FRu Ru;
  const FUmHudLayout L = Layout1080();
  FUmCombatEdgeModel Own, Opp;
  FUmCombatCenterModel Ctr;
  // Marmoreal: Medusa's player defends - the own (left) edge is the defense
  FUmCombatBlocks::Gather(OpenA(L, TEXT("p-medusa")), TEXT("c8"), Own, Opp, Ctr);
  TestTrue(TEXT("Marmoreal: left = own defense (Medusa)"), Own.bShow && Own.Role == EUmEdgeRole::Defense && Own.FighterName == TEXT("Medusa"));
  TestTrue(TEXT("Marmoreal: right = the attacker (Merlin)"), Opp.bShow && Opp.Role == EUmEdgeRole::Attack && Opp.FighterName == TEXT("Merlin"));
  TestEqual(TEXT("Marmoreal: Medusa's chip P1"), Own.TeamSlot, 0);
  TestEqual(TEXT("Marmoreal: Merlin's chip P2"), Opp.TeamSlot, 1);
  TestEqual(TEXT("Marmoreal: Merlin's cards carry the King Arthur back"), Opp.HeroSlug, FString(TEXT("king-arthur")));
  // Sarpedon: King Arthur's player attacks with Merlin - the own (left) edge is the attack
  FUmCombatBlocks::Gather(OpenA(L, TEXT("p-arthur")), TEXT("c8"), Own, Opp, Ctr);
  TestTrue(TEXT("Sarpedon: left = own attack (Merlin)"), Own.Role == EUmEdgeRole::Attack && Own.FighterName == TEXT("Merlin"));
  TestTrue(TEXT("Sarpedon: right = the defense (Medusa)"), Opp.Role == EUmEdgeRole::Defense && Opp.FighterName == TEXT("Medusa"));
  // the ribbon text (RU)
  TestEqual(TEXT("«АТАКА · Merlin»"), UmHudCombatEdge::RoleText(EUmEdgeRole::Attack, TEXT("Merlin")).ToString(),
            FString(TEXT("АТАКА · Merlin")));
  TestEqual(TEXT("«ЗАЩИТА · Medusa»"), UmHudCombatEdge::RoleText(EUmEdgeRole::Defense, TEXT("Medusa")).ToString(),
            FString(TEXT("ЗАЩИТА · Medusa")));
  // the widgets: the left one at x 24, the right one 24 su from the right edge, in every class
  FWorld W(TEXT("UmCombatSides"));
  for (const FVector2D Canvas : {FVector2D(1920.0, 1080.0), FVector2D(1280.0, 720.0), FVector2D(1280.0 / 1.125, 640.0)}) {
    const float Px = Canvas.X == 1920.0 ? 1.0f : Canvas.X == 1280.0 ? 1.5f : 1.125f;
    const FUmHudLayout LL = FUmHudLayout::Compute(Canvas, Px, nullptr);
    UUmHudCombatEdge* EL = MakeEdge(W.World, EUmEdgeSide::Own, LL);
    UUmHudCombatEdge* ER = MakeEdge(W.World, EUmEdgeSide::Opp, LL);
    if (!EL || !ER) continue;
    FUmCombatBlocks::Gather(OpenA(LL, TEXT("p-medusa")), TEXT("c8"), Own, Opp, Ctr);
    EL->ApplyModel(Own);
    ER->ApplyModel(Opp);
    const FBox2D A = EL->DrawnRectSu();
    const FBox2D B = ER->DrawnRectSu();
    TestTrue(FString::Printf(TEXT("%.0fx%.0f: own left at the margin, opp right at the margin"), Canvas.X, Canvas.Y),
             FMath::IsNearlyEqual(A.Min.X, LL.MarginSu) && FMath::IsNearlyEqual(B.Max.X, Canvas.X - LL.MarginSu, 0.01));
    TArray<FString> Lines;
    EL->CollectShotLines(Lines);
    ER->CollectShotLines(Lines);
    TestTrue(TEXT("own line fighter=own, opp line fighter=opp"), Lines.Num() == 2 && Field(Lines[0], TEXT("fighter")) == TEXT("own") &&
                                                                 Field(Lines[1], TEXT("fighter")) == TEXT("opp"));
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmCombatEdgeSlotTest, "Unmatched.S08.Hud.CombatEdge.Slot",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FUmCombatEdgeSlotTest::RunTest(const FString& Parameters) {
  FRu Ru;
  FWorld W(TEXT("UmCombatSlot"));
  const FUmHudLayout L = Layout1080();
  FUmCombatEdgeModel Own, Opp;
  FUmCombatCenterModel Ctr;
  // the defense window, nothing chosen: shield + «Карта не выбрана», the buttons, «Защититься» refuses (pick first)
  FUmCombatInput In = OpenA(L, TEXT("p-medusa"));
  FUmCombatBlocks::Gather(In, TEXT("c8"), Own, Opp, Ctr);
  const FUmCombatEdgeModel Shield = Own;
  TestEqual(TEXT("shield"), Own.State, EUmEdgeState::Shield);
  TestTrue(TEXT("the defender's buttons"), Own.bButtons && !Opp.bButtons);
  TestEqual(TEXT("defend refuses: why.defense.pick"), Own.DefendWhy.Key, FName(TEXT("why.defense.pick")));
  TestFalse(TEXT("no defense is open"), Own.NoDefenseWhy.IsSet());
  TestEqual(TEXT("the attacker's card on the defender's HUD: the back"), Opp.State, EUmEdgeState::Back);
  TestFalse(TEXT("... without a face"), Opp.bFace);
  UUmHudCombatEdge* E = MakeEdge(W.World, EUmEdgeSide::Own, L);
  if (!TestNotNull(TEXT("edge"), E)) return false;
  E->ApplyModel(Own);
  TestTrue(TEXT("shield: the glyph and the caption"), E->SlotGlyph && E->SlotGlyph->GetVisibility() != ESlateVisibility::Collapsed &&
                                                          E->SlotText && E->SlotText->GetText().ToString() == TEXT("Карта не выбрана"));
  TestTrue(TEXT("shield: no card widget"), E->Card && E->Card->GetVisibility() == ESlateVisibility::Collapsed);
  TestTrue(TEXT("shield: the buttons shown"), E->DefendButton && E->DefendButton->GetVisibility() == ESlateVisibility::Visible &&
                                                  E->NoDefenseButton->GetVisibility() == ESlateVisibility::Visible);
  TestTrue(TEXT("«ЗАЩИТИТЬСЯ» disabled (primary), «БЕЗ ЗАЩИТЫ» enabled"),
           E->DefendButton->GetModel().Variant == EUmButtonVariant::Primary && !E->DefendButton->GetModel().bEnabled &&
               E->NoDefenseButton->GetModel().bEnabled);
  // a card chosen: chosen (the back of the own deck) + «Карта выбрана», defend enabled
  In.DraftDefenseId = TEXT("me::feint");
  FUmCombatBlocks::Gather(In, TEXT("c8"), Own, Opp, Ctr);
  TestEqual(TEXT("chosen"), Own.State, EUmEdgeState::Chosen);
  TestFalse(TEXT("defend open"), Own.DefendWhy.IsSet());
  E->ApplyModel(Own);
  TestTrue(TEXT("chosen: the caption plate above the card"), E->CaptionPlate && E->CaptionPlate->GetVisibility() != ESlateVisibility::Collapsed &&
                                                                  E->CaptionText->GetText().ToString() == TEXT("Карта выбрана"));
  TestTrue(TEXT("chosen: the back"), E->Card->GetVisibility() != ESlateVisibility::Collapsed && E->Card->GetFace() == EUmCardFace::Back);
  const FBox2D Drawn = E->DrawnRectSu();
  TestTrue(TEXT("chosen: the plate 4 su above the card (y 332)"), FMath::IsNearlyEqual(Drawn.Min.Y, 332.0));
  // nothing to defend with
  In.bHasLegalDefense = false;
  In.DraftDefenseId.Reset();
  FUmCombatBlocks::Gather(In, TEXT("c8"), Own, Opp, Ctr);
  TestEqual(TEXT("why.defense.none"), Own.DefendWhy.Key, FName(TEXT("why.defense.none")));
  // after CUE-009 (COMBAT_RESOLVE, not revealed): chosen on both HUDs, no buttons
  FUmCombatBlocks::Gather(OpenA(L, TEXT("p-arthur"), true), TEXT("c8"), Own, Opp, Ctr);
  TestTrue(TEXT("CUE-009 on the attacker's HUD: the defense slot chosen"), Opp.State == EUmEdgeState::Chosen && !Opp.bButtons);
  // no defense: the staging stamps X (AB-8)
  FStageA S(3, true);
  FUmCombatInput Staged = OpenA(L, TEXT("p-arthur"));
  Staged.bOpen = false;
  Staged.Stage = &S.Stage;
  Staged.NowMs = S.Start + 10;
  S.At(Staged.NowMs);
  FUmCombatBlocks::Gather(Staged, TEXT("s10"), Own, Opp, Ctr);
  TestEqual(TEXT("nodefense"), Opp.State, EUmEdgeState::NoDefense);
  UUmHudCombatEdge* R = MakeEdge(W.World, EUmEdgeSide::Opp, L);
  R->ApplyModel(Opp);
  TestTrue(TEXT("nodefense: the stamp, the empty frame, no card"), R->IsStampShown() && R->SlotFrame->GetVisibility() != ESlateVisibility::Collapsed &&
                                                                       R->Card->GetVisibility() == ESlateVisibility::Collapsed);
  const TArray<FString> Trace = R->TakeTrace();
  TestTrue(TEXT("HUD-STAMP once"), Trace.Num() == 1 && Trace[0].StartsWith(TEXT("HUD-STAMP no-defense seq=10 side=opp")));
  R->ApplyModel(Opp);
  TestEqual(TEXT("the same combat stamps once"), R->TakeTrace().Num(), 0);
  // the SHOT states
  TArray<FString> Lines;
  E->ApplyModel(Shield);
  E->CollectShotLines(Lines);
  R->CollectShotLines(Lines);
  for (const FString& Line : Lines) TestTrue(FString::Printf(TEXT("SHOT format: %s"), *Line), ShotLineOk(Line));
  TestTrue(TEXT("states shield / nodefense"), Lines.Num() == 2 && Field(Lines[0], TEXT("state")) == TEXT("shield") &&
                                                  Field(Lines[1], TEXT("state")) == TEXT("nodefense"));
  // the ribbon: one row in L; class S wraps «ЗАЩИТА · King Arthur» to two rows (40 su)
  TestEqual(TEXT("L ribbon 230 x 28"), UmHudCombatEdge::RibbonHeightSu(false, 1, false), 28.0f);
  TestEqual(TEXT("L ribbon with the timer 56"), UmHudCombatEdge::RibbonHeightSu(false, 1, true), 56.0f);
  TestEqual(TEXT("S ribbon two rows 40"), UmHudCombatEdge::RibbonHeightSu(true, 2, false), 40.0f);
  TestEqual(TEXT("S ribbon two rows + timer 68"), UmHudCombatEdge::RibbonHeightSu(true, 2, true), 68.0f);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmCombatEdgePrivacyTest, "Unmatched.S08.Hud.CombatEdge.Privacy",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FUmCombatEdgePrivacyTest::RunTest(const FString& Parameters) {
  FRu Ru;
  FWorld W(TEXT("UmCombatPrivacy"));
  const FUmHudLayout L = Layout1080();
  FUmCombatEdgeModel Own, Opp;
  FUmCombatCenterModel Ctr;
  // the defender's HUD before the reveal: even a projection that carries the attack card by mistake shows no face
  FUmCombatInput In = OpenA(L, TEXT("p-medusa"));
  In.AttackCard = SwiftStrike();
  In.Combat.bHasAttackerCard = false;  // the server's privacy flag: the attacker's card is not public yet
  FUmCombatBlocks::Gather(In, TEXT("c8"), Own, Opp, Ctr);
  TestTrue(TEXT("the attack edge without a face"), !Opp.bFace && Opp.Card.Name.IsEmpty() && Opp.Card.CardId.IsEmpty());
  In.Combat.bHasAttackerCard = true;  // even then: not revealed = no face on the defender's HUD
  In.Combat.AttackerCardId = TEXT("ka::swift");
  FUmCombatBlocks::Gather(In, TEXT("c8"), Own, Opp, Ctr);
  TestTrue(TEXT("not revealed: still the back"), !Opp.bFace && Opp.Card.Name.IsEmpty());
  // the attacker's HUD after CUE-009: the defense card committed face down
  FUmCombatInput Att = OpenA(L, TEXT("p-arthur"), true);
  Att.DefenseCard = Feint();
  Att.Combat.bHasDefenderCard = true;
  Att.Combat.bRevealed = false;
  FUmCombatBlocks::Gather(Att, TEXT("c8"), Own, Opp, Ctr);
  TestTrue(TEXT("CUE-009: the defense edge has no face"), Opp.State == EUmEdgeState::Chosen && !Opp.bFace && Opp.Card.Name.IsEmpty());
  UUmHudCombatEdge* E = MakeEdge(W.World, EUmEdgeSide::Opp, L);
  E->ApplyModel(Opp);
  TArray<FString> Lines;
  E->CollectShotLines(Lines);
  TestTrue(TEXT("SHOT before the reveal: face=0, no name"), Lines.Num() == 1 && Field(Lines[0], TEXT("face")) == TEXT("0") &&
                                                                 !Lines[0].Contains(TEXT("Feint")));
  TestTrue(TEXT("CARD-ART key = the back"), E->Card && E->Card->GetFaceKey().StartsWith(TEXT("back:")));
  // the reveal (the resolve window's public combatInfo): the face, state=reveal
  Att.Combat.bRevealed = true;
  Att.Combat.bHasAttackerCard = true;
  Att.Combat.AttackerCardId = TEXT("ka::swift");
  Att.AttackCard = SwiftStrike();
  FUmCombatBlocks::Gather(Att, TEXT("c8"), Own, Opp, Ctr);
  TestTrue(TEXT("revealed: the face, state=reveal"), Opp.State == EUmEdgeState::Reveal && Opp.bFace && Opp.Card.Name == TEXT("Feint"));
  E->ApplyModel(Opp);
  E->SetClockOverrideMs(FPlatformTime::Seconds() * 1000.0 + 10000.0);  // past the flip
  E->Step();
  if (E->Card) E->Card->Step();
  Lines.Reset();
  E->CollectShotLines(Lines);
  TestTrue(TEXT("SHOT after the reveal: state=reveal face=1, still no name"), Lines.Num() == 1 && Field(Lines[0], TEXT("state")) == TEXT("reveal") &&
                                                                                   Field(Lines[0], TEXT("face")) == TEXT("1") && !Lines[0].Contains(TEXT("Feint")));
  // the rule of the gate: a fighter=opp line with face=1 only in state=reveal
  TestEqual(TEXT("the instance id is the combat's, never the card's"), Opp.Card.InstanceId, FString(TEXT("combat.c8.defense")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmCombatEdgeTimerTest, "Unmatched.S08.Hud.CombatEdge.Timer",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FUmCombatEdgeTimerTest::RunTest(const FString& Parameters) {
  FRu Ru;
  FWorld W(TEXT("UmCombatTimer"));
  const FUmHudLayout L = Layout1080();
  TestEqual(TEXT("off without a timer"), UmHudCombatEdge::TimerStateFor(false, 5.0), EUmTimerState::Off);
  TestEqual(TEXT("11 s normal"), UmHudCombatEdge::TimerStateFor(true, 11.0), EUmTimerState::Normal);
  TestEqual(TEXT("10.5 s (shown «11 с») normal"), UmHudCombatEdge::TimerStateFor(true, 10.5), EUmTimerState::Normal);
  TestEqual(TEXT("10 s warning (the last 10 s, HB-31: 11 -> 10)"), UmHudCombatEdge::TimerStateFor(true, 10.0), EUmTimerState::Warning);
  TestEqual(TEXT("9.9 s warning"), UmHudCombatEdge::TimerStateFor(true, 9.9), EUmTimerState::Warning);
  TestEqual(TEXT("0 expired"), UmHudCombatEdge::TimerStateFor(true, 0.0), EUmTimerState::Expired);
  TestEqual(TEXT("9.2 s shows 10"), UmHudCombatEdge::ShownSeconds(9.2), 10);
  FUmCombatEdgeModel Own, Opp;
  FUmCombatCenterModel Ctr;
  FUmCombatInput In = OpenA(L, TEXT("p-medusa"));
  In.DeadlineSec = 1011.0;  // the edge's clock below: 1000 s
  In.WindowSec = 30.0f;
  FUmCombatBlocks::Gather(In, TEXT("c8"), Own, Opp, Ctr);
  TestTrue(TEXT("the timer on the own defender only"), Own.bTimer && !Opp.bTimer);
  UUmHudCombatEdge* E = MakeEdge(W.World, EUmEdgeSide::Own, L);
  if (!TestNotNull(TEXT("edge"), E)) return false;
  E->SetClockOverrideMs(1000000.0);
  E->ApplyModel(Own);
  TestEqual(TEXT("11 s: normal"), E->GetTimerState(), EUmTimerState::Normal);
  TestEqual(TEXT("«11 с»"), E->TimerText->GetText().ToString(), FString(TEXT("11 с")));
  TestTrue(TEXT("no warning edge / sign"), E->WarnEdge->GetVisibility() == ESlateVisibility::Collapsed &&
                                               E->WarnIcon->GetVisibility() == ESlateVisibility::Collapsed);
  TestEqual(TEXT("the ribbon grows to 56 su"), static_cast<float>(E->RibbonRectSu().GetSize().Y), 56.0f);
  E->SetClockOverrideMs(1001000.0);  // 10 s left: «10 с»
  E->Step();
  TestEqual(TEXT("10 s: warning"), E->GetTimerState(), EUmTimerState::Warning);
  TestTrue(TEXT("warning: the state.warning edge and the sign"), E->WarnEdge->GetVisibility() != ESlateVisibility::Collapsed &&
                                                                     E->WarnIcon->GetVisibility() != ESlateVisibility::Collapsed);
  TestEqual(TEXT("«10 с»"), E->TimerText->GetText().ToString(), FString(TEXT("10 с")));
  E->SetClockOverrideMs(1011000.0);
  E->Step();
  TestEqual(TEXT("0: expired"), E->GetTimerState(), EUmTimerState::Expired);
  TestTrue(TEXT("expired: both buttons refuse with why.deadline.passed"),
           !E->DefendButton->GetModel().bEnabled && E->DefendButton->GetModel().Reason.Key == FName(TEXT("why.deadline.passed")) &&
               !E->NoDefenseButton->GetModel().bEnabled);
  const TArray<FString> Trace = E->TakeTrace();
  TestTrue(FString::Printf(TEXT("HUD-TIMER normal -> warning -> expired (%d lines)"), Trace.Num()),
           Trace.Num() == 3 && Trace[0].Contains(TEXT("state=normal")) && Trace[1].Contains(TEXT("state=warning")) &&
               Trace[2].StartsWith(TEXT("HUD-TIMER left=0 state=expired")));
  // the attacker never gets a timer (04 §2.7: «Ждём защиту…» in the centre)
  FUmCombatBlocks::Gather(OpenA(L, TEXT("p-arthur")), TEXT("c8"), Own, Opp, Ctr);
  TestTrue(TEXT("attacker: no timer, the centre waits"), !Own.bTimer && !Opp.bTimer && Ctr.State == EUmCenterState::Wait);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmCombatEdgeFlipTest, "Unmatched.S08.Hud.CombatEdge.Flip",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FUmCombatEdgeFlipTest::RunTest(const FString& Parameters) {
  FRu Ru;
  FWorld W(TEXT("UmCombatFlip"));
  const FUmHudLayout L = Layout1080();
  TestEqual(TEXT("the defense card +120 ms at x1"), UmCardWidget::DefenseFlipDelayMs(1.0f), 120.0f);
  TestEqual(TEXT("+60 ms fast"), UmCardWidget::DefenseFlipDelayMs(0.5f), 60.0f);
  FUmCombatEdgeModel Own, Opp;
  FUmCombatCenterModel Ctr;
  // the defender's HUD: the attack back, then the staging of the same combat reveals both
  FUmCombatInput Open = OpenA(L, TEXT("p-medusa"), true);
  FUmCombatBlocks::Gather(Open, TEXT("c8"), Own, Opp, Ctr);
  UUmHudCombatEdge* EA = MakeEdge(W.World, EUmEdgeSide::Opp, L);  // the attack card (right)
  UUmHudCombatEdge* ED = MakeEdge(W.World, EUmEdgeSide::Own, L);  // the own defense card (left)
  if (!EA || !ED) return false;
  const double T0 = 5000000.0;
  EA->SetClockOverrideMs(T0);
  ED->SetClockOverrideMs(T0);
  EA->ApplyModel(Opp);
  ED->ApplyModel(Own);
  TestTrue(TEXT("before: both backs"), EA->Card->GetFace() == EUmCardFace::Back && ED->Card->GetFace() == EUmCardFace::Back);
  FStageA S;
  FUmCombatInput Staged = OpenA(L, TEXT("p-medusa"));
  Staged.bOpen = false;
  Staged.Stage = &S.Stage;
  Staged.NowMs = S.Start;
  FUmCombatBlocks::Gather(Staged, TEXT("c8"), Own, Opp, Ctr);
  TestTrue(TEXT("the staging: both faces public"), Own.bFace && Opp.bFace && Own.State == EUmEdgeState::Reveal);
  EA->ApplyModel(Opp);
  ED->ApplyModel(Own);
  TestTrue(TEXT("t 0: the attack card turns at once"), !EA->IsFlipPending() && EA->Card->IsFlipping());
  TestTrue(TEXT("t 0: the defense card waits"), ED->IsFlipPending());
  ED->SetClockOverrideMs(T0 + 119.0);
  ED->Step();
  TestTrue(TEXT("t 119: still waiting"), ED->IsFlipPending());
  ED->SetClockOverrideMs(T0 + 120.0);
  ED->Step();
  TestTrue(TEXT("t 120: the defense card turns"), !ED->IsFlipPending() && ED->Card->IsFlipping());
  // the face enters at the edge frame and the flip ends within 130-200 ms (CP-20: 160)
  EA->SetClockOverrideMs(T0 + 200.0);
  EA->Card->Step();
  TestTrue(TEXT("t 200: the attack face shown"), !EA->Card->IsFlipping() && EA->Card->GetFace() != EUmCardFace::Back);
  ED->SetClockOverrideMs(T0 + 320.0);
  ED->Card->Step();
  TestTrue(TEXT("t 320: the defense face shown"), !ED->Card->IsFlipping() && ED->Card->GetFace() != EUmCardFace::Back);
  // a staging without its open combat (a reconnect): the faces at once, no flip
  UUmHudCombatEdge* EX = MakeEdge(W.World, EUmEdgeSide::Opp, L);
  FUmCombatBlocks::Gather(Staged, TEXT("s10"), Own, Opp, Ctr);
  EX->ApplyModel(Opp);
  TestTrue(TEXT("reconnect: no pending flip"), !EX->IsFlipPending());
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmCombatEdgeLeaveTest, "Unmatched.S08.Hud.CombatEdge.Leave",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FUmCombatEdgeLeaveTest::RunTest(const FString& Parameters) {
  FRu Ru;
  FWorld W(TEXT("UmCombatLeave"));
  // the curve: fade 150 (decor 1 -> 0, card 1 -> 0.5), flight 200 (card 0.5 -> 0)
  float D = 0, C = 0, F = 0;
  UmHudCombatEdge::LeaveAt(75.0f, 1.0f, false, D, C, F);
  TestTrue(TEXT("75 ms: decor 0.5, card 0.75, no flight"), FMath::IsNearlyEqual(D, 0.5f) && FMath::IsNearlyEqual(C, 0.75f) && F == 0.0f);
  UmHudCombatEdge::LeaveAt(250.0f, 1.0f, false, D, C, F);
  TestTrue(TEXT("250 ms: flying"), D == 0.0f && F > 0.5f && F < 1.0f && C < 0.5f);
  TestEqual(TEXT("350 ms at x1"), UmHudCombatEdge::LeaveMs(1.0f, false), 350.0f);
  TestEqual(TEXT("525 ms slow"), UmHudCombatEdge::LeaveMs(1.5f, false), 525.0f);
  TestEqual(TEXT("reduced 100"), UmHudCombatEdge::LeaveMs(1.0f, true), 100.0f);
  UmHudCombatEdge::LeaveAt(50.0f, 1.0f, true, D, C, F);
  TestTrue(TEXT("reduced: opacity only"), FMath::IsNearlyEqual(D, 0.5f) && FMath::IsNearlyEqual(C, 0.5f) && F == 0.0f);
  // the blocks: the staging's end starts the leave; after it nothing of the combat stays
  UUmGameHud* Game = CreateWidget<UUmGameHud>(W.World, UUmGameHud::StaticClass());
  if (!TestNotNull(TEXT("game"), Game)) return false;
  FUmCombatBlocks Blocks;
  Blocks.Build(*Game, S08ArtLook::FS08SlateHudBlocks(), MakeShared<FS09HudPressArbiter>(), FUmCombatBlocks::FCallbacks());
  if (!TestTrue(TEXT("the blocks built"), Blocks.EdgesOnUmg() && Blocks.CenterOnUmg())) return false;
  const FUmHudLayout L = Layout1080();
  FStageA S;
  FUmCombatInput In = OpenA(L, TEXT("p-medusa"));
  In.bOpen = false;
  In.Stage = &S.Stage;
  In.NowMs = S.Start + 10;
  S.At(In.NowMs);
  Blocks.Refresh(In);
  UUmHudCombatEdge* Own = Blocks.GetEdge(EUmEdgeSide::Own);
  TestTrue(TEXT("staged: the own edge shown"), Own->GetVisibility() != ESlateVisibility::Collapsed);
  int64 T = In.NowMs;
  while (S.Stage.IsActive() && T < S.Start + 20000) S.At(++T);
  In.NowMs = T + 1;
  const double Clock = FPlatformTime::Seconds() * 1000.0;
  Own->SetClockOverrideMs(Clock);
  Blocks.GetEdge(EUmEdgeSide::Opp)->SetClockOverrideMs(Clock);
  const TArray<FString> Trace = Blocks.Refresh(In);
  TestTrue(TEXT("HUD-COMBAT leave seq=10"), Trace.ContainsByPredicate([](const FString& X) { return X.StartsWith(TEXT("HUD-COMBAT leave seq=10")); }));
  TestTrue(TEXT("leaving"), Own->IsLeaving());
  Own->SetClockOverrideMs(Clock + 351.0);
  Own->Step();
  TestTrue(TEXT("after 350 ms: gone"), !Own->IsLeaving() && Own->GetVisibility() == ESlateVisibility::Collapsed);
  TArray<FString> Lines;
  Blocks.CollectShotLines(Lines);
  TestFalse(TEXT("no combat line after the leave"), Lines.ContainsByPredicate([](const FString& X) { return X.Contains(TEXT("UI-HUD-COMBAT-EDGE")) && X.Contains(TEXT("visible=1")); }));
  // a new combat (CUE-008) cuts a leave in flight: the new cards, nothing of the old ones
  FStageA S2;
  In.Stage = &S2.Stage;
  In.NowMs = S2.Start + 10;
  S2.At(In.NowMs);
  Blocks.Refresh(In);
  int64 T2 = In.NowMs;
  while (S2.Stage.IsActive() && T2 < S2.Start + 20000) S2.At(++T2);
  In.NowMs = T2 + 1;
  UUmHudCombatEdge* Opp = Blocks.GetEdge(EUmEdgeSide::Opp);
  Opp->SetClockOverrideMs(Clock + 1000.0);
  Blocks.Refresh(In);
  TestTrue(TEXT("the second combat leaves"), Opp->IsLeaving());
  FUmCombatInput Next = OpenA(L, TEXT("p-medusa"));
  Next.AppliedSeq = 22;
  Next.NowMs = In.NowMs + 50;
  Blocks.Refresh(Next);
  TestTrue(TEXT("a new combat: the leave cut, the new card shown"), !Opp->IsLeaving() && Opp->GetModel().CombatKey == TEXT("c22") &&
                                                                        Opp->GetVisibility() != ESlateVisibility::Collapsed);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmCombatCenterLinesTest, "Unmatched.S08.Hud.CombatCenter.Lines",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FUmCombatCenterLinesTest::RunTest(const FString& Parameters) {
  FRu Ru;
  using namespace UmHudCombatCenter;
  TestEqual(TEXT("one row 24"), LineBoxSu(1), 24.0f);
  TestEqual(TEXT("two rows 46 (22 su apart)"), LineBoxSu(2), 46.0f);
  // HB-29 effects-long: Feint (current), Swift Strike (X), Winged Frenzy (2 rows + «…»), Regroup
  FPlan P = Plan(EUmCenterState::Effects, false, {1, 1, 2, 1}, 0, false);
  TestTrue(FString::Printf(TEXT("L: 3 lines + «ещё 1», %.0f su <= 160"), P.HeightSu), P.First == 0 && P.Count == 3 && P.More == 1 && P.HeightSu <= 160.0f);
  P = Plan(EUmCenterState::Effects, false, {1, 1, 2, 1}, 0, true);
  TestTrue(TEXT("S: 2 lines + «ещё 2»"), P.Count == 2 && P.More == 2);
  P = Plan(EUmCenterState::Effects, false, {1, 1, 2, 1}, 3, false);
  TestTrue(TEXT("the window follows the current line"), P.First == 1 && P.Count == 3 && P.More == 1);
  P = Plan(EUmCenterState::Slam, true, {1, 1}, -1, false);
  TestTrue(FString::Printf(TEXT("slam: score, outcome and both lines (%.0f su)"), P.HeightSu), P.Count == 2 && P.More == 0 && FMath::IsNearlyEqual(P.HeightSu, 152.0f));
  P = Plan(EUmCenterState::Slam, true, {2, 2}, -1, false);
  TestTrue(FString::Printf(TEXT("slam with two 2-row lines: <= 160 (%.0f), the rest in the chip"), P.HeightSu), P.HeightSu <= 160.0f && P.Count + P.More == 2 && P.More > 0);
  TestEqual(TEXT("wait 64 su"), Plan(EUmCenterState::Wait, false, {}, -1, false).HeightSu, 64.0f);
  TestEqual(TEXT("read draws nothing"), Plan(EUmCenterState::Read, false, {1}, 0, false).HeightSu, 0.0f);
  // the Winged Frenzy RU line of the HB-29 test set (facts.json effects.winged, 194 chars): 2 rows + «…»
  FString Winged;
  {
    FString Json;
    TSharedPtr<FJsonObject> Root;
    const FString Path = FPaths::ConvertRelativePathToFull(FPaths::ProjectDir() / TEXT("../../art/imagegen/hud-combat-v1-codex/facts.json"));
    if (FFileHelper::LoadFileToString(Json, *Path) && FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Json), Root) && Root.IsValid()) {
      const TSharedPtr<FJsonObject>* Effects = nullptr;
      const TSharedPtr<FJsonObject>* W = nullptr;
      if (Root->TryGetObjectField(TEXT("effects"), Effects) && (*Effects)->TryGetObjectField(TEXT("winged"), W)) (*W)->TryGetStringField(TEXT("text"), Winged);
    }
  }
  if (TestFalse(TEXT("the Winged Frenzy RU line loaded"), Winged.IsEmpty())) {
    for (const bool bS : {false, true}) {
      int32 Rows = 0;
      bool bE = false;
      const FString Fitted = FitLine(Winged, (bS ? WidthSSu : WidthLSu) - TextLeftSu - PadSu, Rows, bE);
      TestTrue(FString::Printf(TEXT("%s: 2 rows + «…» (%s)"), bS ? TEXT("S") : TEXT("L"), *Fitted.Replace(TEXT("\n"), TEXT(" / "))),
               Rows == 2 && bE && Fitted.EndsWith(TEXT("…")));
    }
  }
  // the centre lines of combat A: Feint lit, then the cancelled Swift Strike - its X when the Feint highlight ends
  FStageA S;
  int64 T = S.Start;
  while (S.Stage.EffectLinesShown(T) == 0 && T < S.Start + 5000) S.At(++T);
  int32 Current = -1;
  TArray<FUmCenterLine> Lines = FUmCombatBlocks::CenterLines(S.Stage, T, true, Current);
  TestTrue(TEXT("Feint lit + Swift Strike cancelled"), Lines.Num() == 2 && Current == 0 && Lines[0].Title == TEXT("Feint") &&
                                                           Lines[1].bCancelled && Lines[1].Title == TEXT("Swift Strike"));
  TestTrue(TEXT("the X with its canceller (Feint lit, HB-29)"), Lines.Num() == 2 && Lines[1].bStamp);
  TestEqual(TEXT("the cancelled line: the card's printed effect"), Lines.Num() == 2 ? Lines[1].Display() : FString(),
            FString(TEXT("Swift Strike: Move your fighter up to 4 spaces.")));
  S.At(T + 401);
  Lines = FUmCombatBlocks::CenterLines(S.Stage, T + 401, true, Current);
  TestTrue(TEXT("the X stays after the 400 ms highlight"), Lines.Num() == 2 && Lines[1].bStamp && Current == -1);
  // the widget: the X glyph, «ещё n», the SHOT line (counts only)
  FWorld W(TEXT("UmCombatCenterLines"));
  UUmHudCombatCenter* C = CreateWidget<UUmHudCombatCenter>(W.World, UUmHudCombatCenter::StaticClass());
  if (!TestNotNull(TEXT("centre"), C)) return false;
  const FUmHudLayout L = Layout1080();
  FUmCombatCenterFrame F;
  F.CanvasSu = L.CanvasSu;
  F.OriginSu = UmGameHudSlots::SlotRect(L, EUmGameSlot::CombatCenter).Min;
  C->SetFrame(F);
  FUmCombatCenterModel M;
  M.State = EUmCenterState::Effects;
  M.Seq = 10;
  M.Lines = Lines;
  M.Current = 0;
  if (!Winged.IsEmpty()) {
    FUmCenterLine LW;
    LW.Text = Winged;  // the HB-29 test set: the title is already in the text
    M.Lines.Add(LW);
    FUmCenterLine LR;
    LR.Title = TEXT("Regroup");
    LR.Text = TEXT("Draw 1 card. If you won the combat, draw 2 cards instead.");
    M.Lines.Add(LR);
  }
  C->ApplyModel(M);
  TestTrue(FString::Printf(TEXT("3 shown + «ещё 1», %d with «…»"), C->GetEllipsisCount()), C->GetPlan().Count == 3 && C->GetPlan().More == 1 && C->GetEllipsisCount() == 1);
  TestTrue(TEXT("«ещё 1»"), C->MoreText && C->MoreText->GetText().ToString() == TEXT("ещё 1"));
  TArray<FString> Shot;
  C->CollectShotLines(Shot);
  TestTrue(TEXT("SHOT UI-HUD-COMBAT effects, no text"), Shot.Num() == 1 && ShotLineOk(Shot[0]) && Field(Shot[0], TEXT("state")) == TEXT("effects") &&
                                                            Field(Shot[0], TEXT("cancelled")) == TEXT("1") && !Shot[0].Contains(TEXT("Feint")));
  const FBox2D R = C->PanelRectSu();
  TestTrue(FString::Printf(TEXT("the panel at y 80, 560 wide, %.0f <= 160 high"), R.GetSize().Y), FMath::IsNearlyEqual(R.Min.Y, 80.0) &&
                                                                                                         FMath::IsNearlyEqual(R.GetSize().X, 560.0) && R.GetSize().Y <= 160.0);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmCombatCenterStageTest, "Unmatched.S08.Hud.CombatCenter.Stage",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FUmCombatCenterStageTest::RunTest(const FString& Parameters) {
  FRu Ru;
  FWorld W(TEXT("UmCombatStage"));
  const FUmHudLayout L = Layout1080();
  UUmGameHud* Game = CreateWidget<UUmGameHud>(W.World, UUmGameHud::StaticClass());
  if (!TestNotNull(TEXT("game"), Game)) return false;
  FUmCombatBlocks Blocks;
  Blocks.Build(*Game, S08ArtLook::FS08SlateHudBlocks(), MakeShared<FS09HudPressArbiter>(), FUmCombatBlocks::FCallbacks());
  TArray<FString> States;
  auto Note = [&Blocks, &States]() {
    TArray<FString> Lines;
    Blocks.CollectShotLines(Lines);
    for (const FString& Line : Lines) {
      if (!Line.Contains(TEXT("id=UI-HUD-COMBAT "))) continue;
      const FString S = Field(Line, TEXT("state"));
      if (States.Num() == 0 || States.Last() != S) States.Add(S);
    }
  };
  // the attacker's HUD (Sarpedon): the defense window, then the staging of combat A
  FUmCombatInput Open = OpenA(L, TEXT("p-arthur"));
  Open.DeclareMs = 0.0f;  // past the CUE-008 declare: the defense window
  Blocks.Refresh(Open);
  Note();
  FStageA S;
  FUmCombatInput In = OpenA(L, TEXT("p-arthur"));
  In.bOpen = false;
  In.Stage = &S.Stage;
  double PerFrame = 0.0;
  TArray<double> Costs;
  for (int64 T = S.Start; T < S.Start + 8000 && (S.Stage.IsActive() || T < S.Start + 10); T += 10) {
    S.At(T);
    In.NowMs = T;
    const double T0 = FPlatformTime::Seconds();
    Blocks.Refresh(In);
    Costs.Add((FPlatformTime::Seconds() - T0) * 1000.0);
    Note();
    if (!S.Stage.IsActive()) break;
  }
  In.NowMs += 10;
  Blocks.Refresh(In);
  Note();
  const FString Seq = FString::Join(States, TEXT(","));
  TestEqual(TEXT("wait -> read -> effects -> slam -> hit"), Seq, FString(TEXT("wait,read,effects,slam,hit")));
  // the score and the outcome of combat A
  const FUmCombatCenterModel& M = Blocks.GetCenter()->GetModel();
  TestTrue(TEXT("hidden after the staging"), M.State == EUmCenterState::Hidden);
  // the cost: the refresh of both edges and the centre per frame of the staging (HB-30 0.08, HB-33 0.05 ms GT p95)
  Costs.Sort();
  const double P95 = Costs.Num() ? Costs[FMath::Min(Costs.Num() - 1, FMath::FloorToInt(0.95 * Costs.Num()))] : 0.0;
  AddInfo(FString::Printf(TEXT("Refresh per frame of the staging: p50 %.4f / p95 %.4f ms (n=%d)"),
                          Costs.Num() ? Costs[Costs.Num() / 2] : 0.0, P95, Costs.Num()));
  (void)PerFrame;
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
