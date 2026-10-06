// VS-3 HB-24 / HB-25 (docs/game-design/visual/06-tasks/hud.csv HB-24, HB-25; 04-hud-spec.md §2.6, §1.6, §2.8, §5.2 step H7,
// §7.1, §7.4; 02 §6.1-§6.3; HB-22 mockup art/imagegen/hud-hand-v1-codex, accepted by delegation, ВР-VS2-HB22-01...13):
// HAND - UUmHudHand (/Game/S08/UI/Hud/WBP_UI_HUD_HAND), the own hand as UUmCardWidget scans (CP-15...CP-21) in the
// corridor between PANEL-LOC and ACTIONS. The opponent's hand is never here (GD-032: count only, UUmHudOppHand).
//
//   row      card 150 x 208 (class S 120 x 166), step 158 (S 128): centred in the corridor while it fits (1080p
//            376..1540, 720p 376..1327, S 268..W-240 - FUmHudLayout); else a fan over the whole corridor with step
//            (corridor - card) / (n - 1) - never under 72 su except where the corridor cannot hold it (ВР-VS2-HB22-09:
//            9 cards at 720p 150 % = 63.7 su; the wheel browses the fan). Later cards lie over earlier ones.
//   height   a resting card shows FUmHudLayout::HandVisibleSu (canvas bottom - FIELD bottom - 8 - caption 22, at most
//            208 / 166, ВР-VS2-HB22-02); the rest runs off the bottom edge, the scan is never cropped.
//   caption  «Рука {n}/{max}» (hud.hand.count, type.caption) on a short plate (text + 2 x 12 su, 22 su, radius.s,
//            panel.bg + panel.edge) at the left edge of the first card, on top of the row cards; hidden while the hand is
//            lowered (ВР-VS2-HB22-10). n counts the cards in the row (a boost card in its slot left the hand).
//   hover    the card under the pointer (strips of the row, not the moving card: no flicker) rises to 225 x 312 su with
//            its bottom 24 su over the canvas bottom, centred on its slot, over every neighbour (card.cream frame, CP-17);
//            hover.ms 150. The drawn preview takes the pointer too (a click on it plays the card); the slot stays.
//   selected the card of the open choice (attack / defense / scheme / pending pick, or the inspected card): 3 su
//            state.pending frame, raised 32 su - never above FIELD (ВР-VS2-HB22-12); not raised while lowered.
//   lowered  SD-26 (FS09HandLower: a cell or a target is picked on the board, the pointer is not on the HUD): the row
//            drops to 48 su of visible height in 150 ms, no preview, the caption hides.
//   states   CP-16 playable / unplayable (why.* tooltip over the hovered card - only an exact key: why.banner.mismatch,
//            why.boost.no.value; a type mismatch dims the card without a tooltip, ВР-VS3-19), new (the dot until the first
//            hover or 10 s); HB-25 discard (every card a candidate - card.frame.warning 2 su; a marked one 16 su down with
//            card-drop, CP-19) and boost (candidates = a printed BOOST > 0, the rest why.boost.no.value; the picked card
//            turns face down and flies into the boost slot with "+N": the maneuver - SLOT (24, 84, 190, 264) / S (16, 64,
//            120, 166) with the BOOST ribbon under it; King Arthur's attack - the COMBAT-L card size 40 su (S 32) right of
//            COMBAT-L, the chip right-aligned 4 su over it, ВР-VS2-HB22-11).
//   motion   draw (CUE-005): a new card flies from the deck chip of DECKS to its place in 350 ms x UI-ACC-013; the
//            starting hand cascades 175 ms per card (the whole hand <= 1.1 s, SD-01); a card that leaves flashes (CUE-006,
//            CP-21) and flies to SLOT / the combat edge / the discard chip, fading over 500 ms; reduced motion - no flight,
//            opacity only (<= 100 ms).
//   pool     one UUmCardWidget per instance id (two copies = two elements, UI-INP-007), reused; 0 new widgets after the
//            warm-up (10). A snapshot never recreates a card (ApplyModel of the same input does no work).
//   input    the press on the release through the HUD arbiter, id "hand.<instanceId>" (DE-014); double click = play
//            (UI-INP-003); right button = the inspector; 1-9 = the card by position (the game mode, as before); the
//            wheel over the hand browses the fan.
//   rollback -S08SlateHud=hand: the Slate text chips of RefreshHud, nothing of this widget is built.
// Trace (per evidence frame): 'SHOT widget id=UI-HUD-HAND impl=umg state=rest|hover|selected|lowered|discard|empty ...
//   n=<row> max=<max> mode=rest|discard|boost step=<su> fan=0|1 below72=0|1 rowVisible=<su> placed=0|1 scaleMax=<x>
//   fallback=<n> pool=<n> created=<n>' and per card 'HUD-HAND card=<i> lang=.. show=.. scale=.. capped=.. state=..' -
//   no card key, no name, no value (the published traces stay reveal-free; ВР-VS3-21).
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../../S09/S09HudModel.h"
#include "../../S09/S09HudPress.h"
#include "../S08ArtHud.h"
#include "../S08ArtHudWidgets.h"
#include "UmCardWidget.h"
#include "UmHudLayout.h"
#include "UmHudHand.generated.h"

class UBorder;
class UCanvasPanel;
class UTextBlock;
class US08AnimatedIconWidget;
class FS09CommandUi;
struct FS08BoardFighter;

/** What the whole hand is doing. */
enum class EUmHandMode : uint8 { Rest, Discard, Boost };
/** Where a boost card goes: the source-card slot (a maneuver, BOOST_CHOICE out of combat) or beside the own combat card. */
enum class EUmHandBoostSlot : uint8 { Slot, Combat };
/** Where a card that leaves the hand flies (the mode it left in). */
enum class EUmHandPlayTo : uint8 { Slot, Combat, Discard };

struct UNMATCHED_API FUmHandCardModel {
  FS09CardView Card;
  bool bPlayable = true;
  FS09Reason Reason;   // why.* of an unplayable card (unset: no exact key - no tooltip, the press goes on)
  bool bSelected = false;
  bool bCandidate = false;    // discard: every card of the hand
  bool bMarked = false;       // discard: picked
  bool bBoostPlaced = false;  // boost: face down in the boost slot with "+N"
  bool operator==(const FUmHandCardModel& O) const;
  bool operator!=(const FUmHandCardModel& O) const { return !(*this == O); }
};

struct UNMATCHED_API FUmHandModel {
  /** The own hand in the order of FS09PlayerPanel::Cards (1-9 = this position). */
  TArray<FUmHandCardModel> Cards;
  int32 HandMaxSize = 7;
  /** The deck owner's hero slug: the scan key heroSlug:cardSlug and the back (Merlin's cards: King Arthur). */
  FString HeroSlug;
  EUmHandMode Mode = EUmHandMode::Rest;
  EUmHandBoostSlot BoostSlot = EUmHandBoostSlot::Slot;
  EUmHandPlayTo PlayTo = EUmHandPlayTo::Slot;
  bool bLowered = false;
  /** The starting hand of the match: its first cards cascade in (SD-01); a join mid-game shows the hand at rest. */
  bool bStartHand = false;
  bool bShow = true;
  bool operator==(const FUmHandModel& O) const;
  bool operator!=(const FUmHandModel& O) const { return !(*this == O); }
  int32 RowCount() const;
};

/** The layout event of the hand (FUmHudLayout + the animation speed). All su of the canvas. */
struct UNMATCHED_API FUmHandFrame {
  FVector2D CanvasSu = FVector2D(1920.0, 1080.0);
  float PxPerSu = 1.0f;
  bool bClassS = false;
  float CorridorLeftSu = 376.0f;
  float CorridorRightSu = 1540.0f;
  float VisibleSu = 208.0f;
  bool bHasField = false;
  float FieldBottomSu = 0.0f;
  /** The UUmGameHud hand slot (row + caption): the origin of the widget. */
  FBox2D SlotSu = FBox2D(ForceInit);
  /** SLOT (04 §1.6) and the own combat card (COMBAT-L without its ribbon). */
  FBox2D SourceSlotSu = FBox2D(ForceInit);
  FBox2D CombatLSu = FBox2D(ForceInit);
  FVector2D DeckChipSu = FVector2D::ZeroVector;
  FVector2D DiscardChipSu = FVector2D::ZeroVector;
  /** UI-ACC-013: 0 none, 0.5 fast, 1 normal, 1.5 slow. */
  float SpeedMul = 1.0f;
  static FUmHandFrame FromLayout(const FUmHudLayout& Layout, float SpeedMul = 1.0f);
  bool operator==(const FUmHandFrame& O) const;
  bool operator!=(const FUmHandFrame& O) const { return !(*this == O); }
};

namespace UmHudHand {
inline constexpr float CardWL = 150.0f;
inline constexpr float CardHL = 208.0f;
inline constexpr float CardWS = 120.0f;
inline constexpr float CardHS = 166.0f;
inline constexpr float StepL = 158.0f;     // 8 su gap
inline constexpr float StepS = 128.0f;
inline constexpr float MinStepSu = 72.0f;  // 04 §2.6, §7.4
inline constexpr float CaptionSu = 22.0f;
inline constexpr float CaptionPadSu = 12.0f;
inline constexpr float HoverWSu = 225.0f;
inline constexpr float HoverHSu = 312.0f;
inline constexpr float HoverBottomGapSu = 24.0f;
inline constexpr float SelectedRaiseSu = 32.0f;
inline constexpr float LoweredVisibleSu = 48.0f;
inline constexpr float FieldGapSu = 8.0f;
inline constexpr float BoostCombatShiftL = 40.0f;  // ВР-VS2-HB22-11
inline constexpr float BoostCombatShiftS = 32.0f;
inline constexpr float RibbonGapSu = 4.0f;         // the BOOST ribbon under the slot card (HB-22)
inline constexpr float RibbonHSu = 28.0f;
inline constexpr float TooltipHSu = 44.0f;
inline constexpr float TooltipGapSu = 8.0f;
inline constexpr float DrawMs = 350.0f;            // CUE-005
inline constexpr float CascadeMs = 175.0f;         // SD-01
inline constexpr float CascadeMaxMs = 1100.0f;
inline constexpr float PlayMs = 500.0f;            // CUE-006
inline constexpr float BoostMs = 150.0f;
inline constexpr float LowerMs = 150.0f;
inline constexpr double NewDotMs = 10000.0;        // the dot leaves after the first hover or 10 s
inline constexpr int32 PoolWarm = 10;              // 7 + the draws of a turn

/** The rest layout of N cards (canvas su). */
struct UNMATCHED_API FRow {
  TArray<FVector2D> CardPos;  // the top-left of each card
  FVector2D CardSize = FVector2D(CardWL, CardHL);
  float StepSu = StepL;
  bool bFan = false;
  bool bBelowMin = false;     // the corridor forced a step under 72 su (ВР-VS2-HB22-09)
  float CardTopSu = 0.0f;
  float LeftSu = 0.0f;
  float RightSu = 0.0f;
};
UNMATCHED_API FRow Row(int32 N, const FUmHandFrame& F);
/** The hover preview of the card resting at RestPos: 225 x 312, bottom 24 su over the canvas bottom, centred on it and
 *  kept inside the canvas. */
UNMATCHED_API FBox2D HoverRect(const FVector2D& RestPos, const FUmHandFrame& F);
/** 32 su, never above FIELD + its 8 su gap (ВР-VS2-HB22-12); 0 without room. */
UNMATCHED_API float SelectedRaiseFor(const FUmHandFrame& F);
/** How far the lowered row goes down: visible - 48 (>= 0). */
UNMATCHED_API float LowerDropSu(const FUmHandFrame& F);
/** The boost card in its slot (canvas su) and its display. */
UNMATCHED_API FBox2D BoostRect(EUmHandBoostSlot Slot, const FUmHandFrame& F);
UNMATCHED_API EUmCardShow BoostShow(EUmHandBoostSlot Slot, const FUmHandFrame& F);
UNMATCHED_API EUmCardShow RowShow(const FUmHandFrame& F);
/** The BOOST ribbon under the slot card (HB-22: x of the slot, 4 su under it, its width, 28 su). */
UNMATCHED_API FBox2D RibbonRect(const FUmHandFrame& F);
/** The cascade delay of the starting hand: 175 ms per card, the last one landing by 1.1 s. */
UNMATCHED_API float CascadeDelayMs(int32 Count);
/** «Рука {n}/{max}». */
UNMATCHED_API FText Caption(int32 N, int32 Max);
UNMATCHED_API const TCHAR* ModeName(EUmHandMode Mode);
/** Mirror of the attack / defense card banner rule of S09ManeuverUi.cpp (PlayableByBanner): empty or 'any' is
 *  universal, else the fighter name and the banner contain one another (case-insensitive). */
UNMATCHED_API bool BannerAllows(const FString& Banner, const FString& FighterName);

/** The command state the hand reads (the game mode fills it from the applied snapshot). */
struct UNMATCHED_API FGatherIn {
  const FS09PlayerPanel* Own = nullptr;
  const FS09CommandUi* Ui = nullptr;
  const TArray<FS08BoardFighter>* Fighters = nullptr;
  FString ViewerId;
  /** The hand-card index of the open inspector (selected outside a choice), -1 none. */
  int32 InspectedIndex = -1;
  bool bLowered = false;
  bool bStartHand = false;
  FString HeroSlug;
};
/** World-free: the hand model of the command state (modes, selection, playability, discard and boost marks). */
UNMATCHED_API FUmHandModel Gather(const FGatherIn& In);
/** The instance id the key 1-9 picks (Key 1-based; '' when there is no such card). */
UNMATCHED_API FString KeyTarget(const FUmHandModel& Model, int32 Key);
}  // namespace UmHudHand

UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmHudHand : public UUserWidget {
  GENERATED_BODY()

 public:
  static const TCHAR* const WidgetBlueprintPath;  // /Game/S08/UI/Hud/WBP_UI_HUD_HAND
  static UClass* WidgetClass();

  virtual bool Initialize() override;
  /** CanvasPanel "Row" > CountPlate (Border) > CountText; WhyPlate > WhyText; BoostRibbon > RibbonRow > RibbonIcon,
   *  RibbonText. The cards are pooled children of Row. */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  bool HasAllParts(FString* OutMissing = nullptr) const;
  bool UsesCodeDefaultTree() const { return bCodeDefaultTree; }
  FString SourceName() const;

  /** The layout event (window / UI scale / FIELD). */
  void SetFrame(const FUmHandFrame& InFrame);
  const FUmHandFrame& GetFrame() const { return Frame; }
  /** The one data input (П1): a snapshot, a selection, a mode change. Same model = no work. */
  void ApplyModel(const FUmHandModel& InModel);
  const FUmHandModel& GetModel() const { return Model; }
  /** OnPress(outcome, instance id) answers a resolved press of a card; OnInspect(instance id) the right button;
   *  OnPlay(instance id) the double click. */
  void SetInput(const TSharedPtr<FS09HudPressArbiter>& InArbiter,
                TFunction<void(const FS09HudPressOutcome&, const FString&)> InOnPress,
                TFunction<void(const FString&)> InOnInspect, TFunction<void(const FString&)> InOnPlay);
  /** SHOT widget + one HUD-HAND line per card (no key, no name). */
  void CollectShotLines(TArray<FString>& Out) const;
  FString StateName() const;

  // ---- queries (tests, the game mode) ----
  UUmCardWidget* FindCard(const FString& InstanceId) const;
  /** Position of InstanceId in the model (-1 none). */
  int32 IndexOf(const FString& InstanceId) const;
  int32 GetHoverIndex() const { return HoverIndex; }
  const UmHudHand::FRow& GetRow() const { return RowNow; }
  /** The rest rectangle of the row card at model index I (canvas su; invalid for a placed / missing card). */
  FBox2D RestRectSu(int32 I) const;
  /** Row + caption as drawn now (canvas su, the lowering included, clipped to the canvas). */
  FBox2D DrawnRectSu() const;
  FBox2D CaptionRectSu() const;
  bool IsCaptionShown() const;
  float GetLowerNowSu() const { return LowerNow; }
  int32 PoolSize() const { return Pool.Num(); }
  int32 CreatedCount() const { return Created; }
  bool IsTooltipShown() const;
  FText GetTooltipText() const;
  /** The hover by a point of the canvas (su) - what the pointer moves do; tests call it directly. */
  void HoverAtSu(const FVector2D& CanvasSu);
  void SetHoverIndex(int32 Index);
  void ClearHover();
  /** One wheel notch over the hand: the preview walks to the next (bForward) / previous card of the row. */
  bool WheelStep(bool bForward);

  // ---- tests and the review sheet ----
  void SetClockOverrideMs(double Ms);
  void SetReducedForTest(int32 InReduced);
  void SetLegacyForTest(int32 InLegacy);
  void SetSyncLoad(bool bOn);
  /** Steps the hand tweens and every card at the current clock (the tick does it while one runs). */
  void Step();

  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UCanvasPanel> Row;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UTextBlock> CountText;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UBorder> CountPlate;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UBorder> WhyPlate;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UTextBlock> WhyText;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UBorder> BoostRibbon;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<US08AnimatedIconWidget> RibbonIcon;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UTextBlock> RibbonText;

 protected:
  virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;
  virtual FReply NativeOnMouseMove(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
  virtual void NativeOnMouseEnter(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
  virtual void NativeOnMouseLeave(const FPointerEvent& InMouseEvent) override;
  virtual FReply NativeOnMouseWheel(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;

 private:
  struct FLeaving {
    TWeakObjectPtr<UUmCardWidget> W;
    double StartMs = 0.0;
    float DurMs = UmHudHand::PlayMs;
  };
  UUmCardWidget* Acquire(const FString& InstanceId);
  void Release(UUmCardWidget* W);
  void EnsurePool(int32 Count);
  void Relayout(bool bAnimate);
  void ApplyCardStates();
  void ApplyOffsets(float DurMs);
  void ApplyCaption();
  void ApplyTooltip();
  void ApplyRibbon();
  /** The hand's own tweens at Now: the lowering, the new-dot timers, the leaving cards. */
  void StepHand(double Now);
  bool NeedsHandStep() const;
  void PlaceCard(UUmCardWidget* W, const FVector2D& PosSu, const FVector2D& SizeSu, int32 Z);
  FVector2D LocalOf(const FVector2D& CanvasSu) const;
  FVector2D ShowSizeOf(EUmCardShow Show) const;
  bool IsReduced() const;
  double NowMs() const;
  void WireCard(UUmCardWidget* W, const FString& InstanceId);
  FUmCardState CardState(EUmCardShow Show) const;

  FUmHandFrame Frame;
  bool bHasFrame = false;
  FUmHandModel Model;
  bool bHasModel = false;
  bool bCodeDefaultTree = false;
  UmHudHand::FRow RowNow;
  /** Model index -> row position (-1: placed in the boost slot). */
  TArray<int32> RowIndex;
  int32 HoverIndex = INDEX_NONE;
  int32 WheelIndex = INDEX_NONE;
  // the lowering of the row (su down), tweened
  float LowerNow = 0.0f;
  float LowerFrom = 0.0f;
  float LowerTo = 0.0f;
  double LowerStartMs = -1.0;
  // the new dots: first seen as new / hovered
  TMap<FString, double> NewSinceMs;
  TSet<FString> NewDone;
  // the placed boost cards (instance ids) of the last apply (a fresh placement flies)
  TSet<FString> PlacedNow;
  TArray<FLeaving> Leaving;
  TMap<FString, TObjectPtr<UUmCardWidget>> Live;
  UPROPERTY(Transient) TArray<TObjectPtr<UUmCardWidget>> Pool;
  TArray<TObjectPtr<UUmCardWidget>> Free;
  int32 Created = 0;
  int32 ReducedOverride = -1;
  int32 LegacyOverride = -1;
  bool bSyncLoad = false;
  double ClockOverrideMs = -1.0;
  TSharedPtr<FS09HudPressArbiter> Arbiter;
  TFunction<void(const FS09HudPressOutcome&, const FString&)> OnPress;
  TFunction<void(const FString&)> OnInspect;
  TFunction<void(const FString&)> OnPlay;
};
