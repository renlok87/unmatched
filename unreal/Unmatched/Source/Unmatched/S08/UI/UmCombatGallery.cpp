// VS-3 HB-30...HB-33 / SC-01 review sheets - see UmCombatGallery.h.
#include "UmCombatGallery.h"

#include "UmCardMedia.h"
#include "UmConfirmDialog.h"
#include "UmGameHud.h"
#include "UmHandGallery.h"
#include "UmHudCombatCenter.h"
#include "UmHudCombatEdge.h"
#include "UmHudTheme.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/Image.h"
#include "Components/TextBlock.h"
#include "Dom/JsonObject.h"
#include "Engine/Texture2D.h"
#include "HAL/PlatformTime.h"
#include "ImageUtils.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace UmCombatGallery {
const TCHAR* StateName(int32 State) {
  static const TCHAR* Names[StateCount] = {TEXT("declare"), TEXT("defense-window"), TEXT("timer-warning"), TEXT("defense-chosen"),
                                           TEXT("reveal"),  TEXT("effects"),        TEXT("slam"),          TEXT("hit"),
                                           TEXT("effects-long"), TEXT("holds"),     TEXT("nodefense")};
  return State >= 0 && State < StateCount ? Names[State] : TEXT("?");
}
}  // namespace UmCombatGallery

namespace {
FUmCombatFighter UmCgFighter(const TCHAR* Id, const TCHAR* Name, const TCHAR* Owner, int32 Team, const TCHAR* Slug) {
  FUmCombatFighter F;
  F.Id = Id;
  F.Name = Name;
  F.OwnerId = Owner;
  F.TeamSlot = Team;
  F.DeckSlug = Slug;
  return F;
}
const FUmCombatFighter& UmCgMerlin() {
  static const FUmCombatFighter F = UmCgFighter(TEXT("f-1-sk0"), TEXT("Merlin"), TEXT("p-arthur"), 1, TEXT("king-arthur"));
  return F;
}
const FUmCombatFighter& UmCgMedusa() {
  static const FUmCombatFighter F = UmCgFighter(TEXT("f-0-hero"), TEXT("Medusa"), TEXT("p-medusa"), 0, TEXT("medusa"));
  return F;
}
const FUmCombatFighter& UmCgArthur() {
  static const FUmCombatFighter F = UmCgFighter(TEXT("f-1-hero"), TEXT("King Arthur"), TEXT("p-arthur"), 1, TEXT("king-arthur"));
  return F;
}
}  // namespace

bool UUmCombatGalleryWidget::Initialize() {
  const bool bFirst = Super::Initialize();
  if (bFirst && WidgetTree && !WidgetTree->RootWidget) {
    Root = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Root")));
    WidgetTree->RootWidget = Root;
  }
  return bFirst;
}

void UUmCombatGalleryWidget::StartCombat(FCombat& Run, const FS09CombatStageInput& In, int64 StartMs) {
  Run.Cues = MakeUnique<FS08CueDispatcher>();
  Run.Stage = MakeUnique<FS09CombatStage>();
  Run.StartMs = StartMs;
  TArray<FString> Lines;
  TArray<FS09CombatStageEvent> Events;
  Run.Stage->Start(In, StartMs, *Run.Cues, Lines, Events);
}

TArray<FString> UUmCombatGalleryWidget::Build(const FString& Board, const FVector2D& CanvasSu, float PxPerSu, bool bConfirm) {
  TArray<FString> Lines;
  if (!Root) return Lines;
  if (CanvasSu.X < 1.0 || CanvasSu.Y < 1.0) {
    Lines.Add(TEXT("UMGALLERY combat pending canvas=0x0"));
    return Lines;
  }
  BoardNow = Board.ToLower();
  bConfirmSheet = bConfirm;
  const bool bSarpedon = BoardNow == TEXT("sarpedon");
  const FBox2D Field = UmHandGallery::FieldSu(BoardNow, CanvasSu, PxPerSu);
  Layout = FUmHudLayout::Compute(CanvasSu, PxPerSu, &Field);
  // ---- the picture: the bench K1 frame of the board (HB-29 backgrounds) ----
  const FString Rel = bSarpedon ? TEXT("docs/game-design/evidence/ENV-MAPS/p10-sarpedon-rework-2026-10-03/sarpedon-packaged/bench-K1-1920x1080.png")
                                : TEXT("docs/game-design/evidence/ENV-MAPS/p7-concept-paste-2026-10-01/marmoreal-concept-flag/bench-K1-1920x1080.png");
  const FString Path = FPaths::ConvertRelativePathToFull(FPaths::ProjectDir() / TEXT("../..") / Rel);
  BackgroundTexture = FParse::Param(FCommandLine::Get(), TEXT("S08IconGalleryHandPlain")) ? nullptr : FImageUtils::ImportFileAsTexture2D(Path);
  Background = WidgetTree->ConstructWidget<UImage>(UImage::StaticClass(), FName(TEXT("Background")));
  if (BackgroundTexture) {
    Background->SetBrushFromTexture(BackgroundTexture);
  } else {
    Background->SetColorAndOpacity(UUmHudTheme::Get().Color(TEXT("panel.bg.inset")));
  }
  if (UCanvasPanelSlot* S = Root->AddChildToCanvas(Background)) {
    S->SetAnchors(FAnchors(0.0f, 0.0f, 1.0f, 1.0f));
    S->SetOffsets(FMargin(0.0f));
  }
  if (bConfirm) {
    // SC-01: the sample modal over the frame (PAUSE «Покинуть партию» -> the confirm of 04 §1.8)
    Dialog = CreateWidget<UUmConfirmDialog>(this, UUmConfirmDialog::WidgetClass());
    if (Dialog) {
      if (UCanvasPanelSlot* S = Root->AddChildToCanvas(Dialog)) {
        S->SetAnchors(FAnchors(0.0f, 0.0f, 1.0f, 1.0f));
        S->SetOffsets(FMargin(0.0f));
      }
      Dialog->SetCanvas(CanvasSu, Layout.bClassS, PxPerSu);
      Dialog->SetReducedForTest(1);  // the sheet: no fade in the shot
      UUmConfirmDialog::FRequest R;
      R.OwnerUiId = TEXT("UI-SCR-PAUSE");
      R.Title = UmText::Get(EUmTable::Screens, TEXT("screens.pause.leave"));
      R.Message = UmText::Get(EUmTable::Screens, TEXT("screens.pause.leave.confirm"));
      Dialog->Open(R);
    }
  } else {
    Game = CreateWidget<UUmGameHud>(this, UUmGameHud::StaticClass());
    if (Game) {
      if (UCanvasPanelSlot* S = Root->AddChildToCanvas(Game)) {
        S->SetAnchors(FAnchors(0.0f, 0.0f, 1.0f, 1.0f));
        S->SetOffsets(FMargin(0.0f));
      }
      Lines.Append(Blocks.Build(*Game, S08ArtLook::FS08SlateHudBlocks(), MakeShared<FS09HudPressArbiter>(), FUmCombatBlocks::FCallbacks()));
      for (const EUmEdgeSide Side : {EUmEdgeSide::Own, EUmEdgeSide::Opp}) {
        if (UUmHudCombatEdge* E = Blocks.GetEdge(Side)) E->SetSyncLoad(true);  // the sheet: no loading frame in a shot
      }
      Game->ApplyLayout(Layout, TArray<FName>(), false);
    }
    // ---- the data: the S01 cards of run I and the HB-29 effect lines (facts.json) ----
    {
      FString Json;
      TSharedPtr<FJsonObject> FactsRoot;
      const FString Facts = FPaths::ConvertRelativePathToFull(FPaths::ProjectDir() / TEXT("../../art/imagegen/hud-combat-v1-codex/facts.json"));
      const TSharedPtr<FJsonObject>* E = nullptr;
      if (FFileHelper::LoadFileToString(Json, *Facts) && FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Json), FactsRoot) &&
          FactsRoot.IsValid() && FactsRoot->TryGetObjectField(TEXT("effects"), E)) {
        for (const TPair<FString, TSharedPtr<FJsonValue>>& P : (*E)->Values) {
          const TSharedPtr<FJsonObject> O = P.Value.IsValid() ? P.Value->AsObject() : nullptr;
          FString Title, Effect;
          if (O.IsValid() && O->TryGetStringField(TEXT("title"), Title) && O->TryGetStringField(TEXT("effect"), Effect)) {
            Effects.Add(P.Key, TPair<FString, FString>(Title, Effect.TrimStartAndEnd()));
          }
        }
      }
    }
    auto MakeCard = [this](const TCHAR* Key, const TCHAR* Name, const TCHAR* Type, int32 A, int32 D, const TCHAR* Inst) {
      FS09CardView C;
      C.Name = Name;
      const TPair<FString, FString>* Fx = Effects.Find(Key);
      C.NameRu = Fx ? Fx->Key : FString(Name);
      C.EffectText = Fx ? Fx->Value : FString();
      C.EffectCount = 1;
      C.CardId = FString::Printf(TEXT("gallery-%s"), Key);
      C.InstanceId = Inst;
      C.CardType = Type;
      C.AttackValue = A;
      C.DefenseValue = D;
      C.bVisible = true;
      Cards.Add(Key, C);
    };
    MakeCard(TEXT("swift"), TEXT("Swift Strike"), TEXT("ATTACK"), 3, 0, TEXT("ka::swift"));
    MakeCard(TEXT("feint"), TEXT("Feint"), TEXT("VERSATILE"), 2, 2, TEXT("me::feint"));
    MakeCard(TEXT("shift"), TEXT("Momentous Shift"), TEXT("VERSATILE"), 3, 3, TEXT("ka::shift"));
    MakeCard(TEXT("dash"), TEXT("Dash"), TEXT("VERSATILE"), 3, 3, TEXT("me::dash"));
    MakeCard(TEXT("snipe"), TEXT("Snipe"), TEXT("VERSATILE"), 3, 3, TEXT("me::snipe"));
    MakeCard(TEXT("regroup"), TEXT("Regroup"), TEXT("VERSATILE"), 1, 1, TEXT("me::regroup"));
    auto Line = [this](const TCHAR* Key, const TCHAR* Name, bool bAttacker) {
      FS09CombatEffectLine L;
      L.CardName = Name;
      const TPair<FString, FString>* Fx = Effects.Find(Key);
      L.Text = Fx ? Fx->Value : FString();
      L.bPrintedText = !L.Text.IsEmpty();
      L.bAttackerSide = bAttacker;
      L.Outcome = TEXT("APPLIED");
      return L;
    };
    auto Stage = [this](int32 Seq, const FUmCombatFighter& Att, const FUmCombatFighter& Tgt, const TCHAR* AttackKey, const TCHAR* DefenseKey,
                        int32 A, int32 D, int32 Damage) {
      FS09CombatStageInput In;
      In.Seq = Seq;
      In.AttackerId = Att.Id;
      In.TargetId = Tgt.Id;
      In.AttackerLabel = Att.Name;
      In.TargetLabel = Tgt.Name;
      In.Damage = Damage;
      In.HpBefore = 16;
      In.HpAfter = 16 - Damage;
      In.Reveal.bAttackKnown = true;
      In.Reveal.Attack = Cards.FindRef(AttackKey);
      In.Reveal.AttackValue = A;
      In.Reveal.DefenseValue = D;
      if (DefenseKey) {
        In.Reveal.bDefenseKnown = true;
        In.Reveal.Defense = Cards.FindRef(DefenseKey);
      } else {
        In.Reveal.bNoDefense = true;
      }
      In.bHasEffectText = true;
      return In;
    };
    FS09CombatStageInput InA = Stage(10, UmCgMerlin(), UmCgMedusa(), TEXT("swift"), TEXT("feint"), 3, 2, 1);
    InA.Effects.Add(Line(TEXT("feint"), TEXT("Feint"), false));
    InA.EffectLines = 1;
    InA.bAttackCardCancelled = true;
    StartCombat(A, InA, 100000);
    FS09CombatStageInput InB = Stage(9, UmCgMerlin(), UmCgMedusa(), TEXT("shift"), TEXT("dash"), 3, 3, 0);
    InB.Effects.Add(Line(TEXT("dash"), TEXT("Dash"), false));
    InB.EffectLines = 1;
    StartCombat(B, InB, 200000);
    // C: each board its own moment - Marmoreal seq=54 Snipe 3, Sarpedon seq=19 Regroup 1; Medusa -> King Arthur
    FS09CombatStageInput InC = bSarpedon ? Stage(19, UmCgMedusa(), UmCgArthur(), TEXT("regroup"), nullptr, 1, 0, 1)
                                         : Stage(54, UmCgMedusa(), UmCgArthur(), TEXT("snipe"), nullptr, 3, 0, 3);
    InC.bHasEffectText = false;
    StartCombat(C, InC, 300000);
  }
  Label = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("Label")));
  Label->SetFont(UUmHudTheme::Get().Font(TEXT("type.caption")));
  Label->SetColorAndOpacity(FSlateColor(UUmHudTheme::Get().Color(TEXT("text.primary"))));
  if (UCanvasPanelSlot* S = Root->AddChildToCanvas(Label)) {
    S->SetAutoSize(true);
    S->SetPosition(FVector2D(Layout.MarginSu, CanvasSu.Y - Layout.MarginSu - 20.0));
  }
  Lines.Add(FString::Printf(TEXT("UMGALLERY combat board=%s canvas=%.0fx%.0f pxPerSu=%.3f background=%s sheet=%s"), *BoardNow, CanvasSu.X,
                            CanvasSu.Y, PxPerSu, BackgroundTexture ? TEXT("bench-K1") : TEXT("plain"), bConfirm ? TEXT("confirm") : TEXT("combat")));
  Lines.Add(Layout.TraceLine(FIntPoint(FMath::RoundToInt(CanvasSu.X * PxPerSu), FMath::RoundToInt(CanvasSu.Y * PxPerSu))));
  return Lines;
}

FUmCombatInput UUmCombatGalleryWidget::BaseInput(bool bAttackerA) const {
  FUmCombatInput In;
  In.Layout = &Layout;
  In.bLive = true;
  In.bRu = UmCardMedia::PreferredLang() != TEXT("en");
  In.ViewerId = BoardNow == TEXT("sarpedon") ? TEXT("p-arthur") : TEXT("p-medusa");
  In.SpeedMul = 0.0f;  // the sheet: every flip and stamp at its end in the shot frame
  In.DeclareMs = 600.0f;  // CUE-008 x1 (the declare state is shot inside it)
  In.NowSec = FPlatformTime::Seconds();
  (void)bAttackerA;
  return In;
}

void UUmCombatGalleryWidget::ApplyState(int32 State, float TMs, TArray<FString>& Lines) {
  const bool bSarpedon = BoardNow == TEXT("sarpedon");
  // the blocks' clock: a small monotonic base per state (the icons keep it in float: FPlatformTime ms would lose the
  // 200 ms of an appear), frozen 400 ms after the state began for the shot - every stamp / sign appear (<= 200 ms) and
  // the speed-0 flips and slam at rest; the timer keeps its state from the base to the freeze
  const double Base = 1.0e6 + 20000.0 * State;
  const double Freeze = Base + 400.0;
  for (const EUmEdgeSide Side : {EUmEdgeSide::Own, EUmEdgeSide::Opp}) {
    if (UUmHudCombatEdge* E = Blocks.GetEdge(Side)) E->SetClockOverrideMs(Base);
  }
  if (UUmHudCombatCenter* Ctr = Blocks.GetCenter()) Ctr->SetClockOverrideMs(Base);
  FUmCombatInput In = BaseInput(true);
  In.NowSec = Base / 1000.0;
  // ---- the open combat A (states 0-3): COMBAT, CUE-009 -> COMBAT_RESOLVE ----
  if (State <= 3) {
    In.bOpen = true;
    In.AppliedSeq = 8;
    In.NowMs = 50000 + static_cast<int64>(TMs);
    In.Combat.bPresent = true;
    In.Combat.AttackerId = UmCgMerlin().Id;
    In.Combat.TargetFighterId = UmCgMedusa().Id;
    In.Combat.DefenderId = UmCgMedusa().OwnerId;
    In.Attacker = UmCgMerlin();
    In.Target = UmCgMedusa();
    if (bSarpedon) {
      // the attacker's HUD: its own committed Swift Strike face up (the projection's own discard)
      In.Combat.bHasAttackerCard = true;
      In.Combat.AttackerCardId = TEXT("ka::swift");
      In.AttackCard = Cards.FindRef(TEXT("swift"));
      In.bResolvePhase = State == 3;  // defense-chosen: after CUE-009
      In.StatusBottomSu = static_cast<float>(Layout.Rect(EUmHudBlock::Status).Min.Y) + 48.0f;  // «Ждём защитника»
    } else {
      // run I: «30 с»; the «10 с» example (ВР-VS2-HB29-04) - already in the warning at the base (its sign appears then)
      In.DeadlineSec = In.NowSec + (State == 2 ? 9.9 : 30.4);
      In.WindowSec = 30.0f;
      In.DraftDefenseId = State == 3 ? TEXT("me::feint") : FString();
    }
  } else {
    // ---- the staging: A (reveal, effects, slam, hit, effects-long), B (holds), C (nodefense) ----
    FCombat& Run = State == 9 ? B : State == 10 ? C : A;
    FS09CombatStage& S = *Run.Stage;
    int64 T = Run.StartMs + (State == 10 ? 300 : 700);  // reveal: after the flip, in the read hold; nodefense: the stamp
    if (State == 5 || State == 8) {
      for (T = Run.StartMs; T < Run.StartMs + 6000 && S.EffectLinesShown(T) == 0; T += 10) {
      }
      T += 100;  // the line lit
    } else if (State == 6 || State == 9) {
      T = S.GetSlamStartMs() + 100;
    } else if (State == 7) {
      T = S.GetContactMs() + 100;
    }
    TArray<FString> Ignored;
    TArray<FS09CombatStageEvent> Events;
    S.Tick(T, *Run.Cues, Ignored, Events);
    In.Stage = &S;
    In.NowMs = T;
    const FS09CombatStageInput& SI = S.GetInput();
    In.Attacker = SI.AttackerId == UmCgMedusa().Id ? UmCgMedusa() : UmCgMerlin();
    In.Target = SI.TargetId == UmCgArthur().Id ? UmCgArthur() : UmCgMedusa();
  }
  Lines.Append(Blocks.Refresh(In));
  // effects-long: the HB-29 test set (not a run I moment): Уловка (lit), Swift Strike (X), Крылатое буйство, Передышка
  if (State == 8) {
    if (UUmHudCombatCenter* Ctr = Blocks.GetCenter()) {
      FUmCombatCenterModel M = Ctr->GetModel();
      for (const TCHAR* Key : {TEXT("winged"), TEXT("regroup")}) {
        FUmCenterLine L;
        if (const TPair<FString, FString>* Fx = Effects.Find(Key)) {
          L.Title = Fx->Key;
          L.Text = Fx->Value;
        }
        M.Lines.Add(L);
      }
      Ctr->ApplyModel(M);
    }
  }
  for (const EUmEdgeSide Side : {EUmEdgeSide::Own, EUmEdgeSide::Opp}) {
    if (UUmHudCombatEdge* E = Blocks.GetEdge(Side)) {
      E->SetClockOverrideMs(Freeze);
      E->Step();
    }
  }
  if (UUmHudCombatCenter* Ctr = Blocks.GetCenter()) Ctr->SetClockOverrideMs(Freeze);
}

TArray<FString> UUmCombatGalleryWidget::SetClockMs(float TMs) {
  TArray<FString> Lines;
  if (bConfirmSheet) {
    if (Dialog) {
      Dialog->Step();
      Dialog->CollectShotLines(Lines);
    }
    if (Label) Label->SetText(FText::FromString(FString::Printf(TEXT("SC-01 sheet · %s · confirm (review tooling, not an acceptance frame)"), *BoardNow)));
    return Lines;
  }
  // Sarpedon has no timer-warning (the attacker's HUD has no timer, ВР-H18): its 10 states skip index 2
  int32 Index = FMath::Clamp(FMath::FloorToInt(TMs / 1000.0f), 0, UmCombatGallery::StateCount - 1);
  if (BoardNow == TEXT("sarpedon") && Index >= 2) Index = FMath::Min(Index + 1, UmCombatGallery::StateCount - 1);
  if (Index != StateNow) {
    StateNow = Index;
    ApplyState(Index, TMs, Lines);
    if (Label) {
      Label->SetText(FText::FromString(FString::Printf(TEXT("HB-30…33 sheet · %s · %s (review tooling, not an acceptance frame)"), *BoardNow,
                                                       UmCombatGallery::StateName(Index))));
    }
  }
  Lines.Add(FString::Printf(TEXT("UMGALLERY combat board=%s state=%d:%s t=%.0f"), *BoardNow, Index, UmCombatGallery::StateName(Index), TMs));
  Blocks.CollectShotLines(Lines);
  return Lines;
}
