// VS-4 HB-37 (docs/game-design/visual/06-tasks/hud.csv HB-37; 04-hud-spec.md §2.8 SLOT, §1.6, §4.3, §5.2 step H10, §7.1;
// 02 §6.2; the accepted mockup HB-34 art/imagegen/hud-pending-v1-codex, ВР-VS2-HB34-07, -08, -16, -17, -18; icons IC-50
// marker-slot-scheme, IC-51 marker-slot-boost, IC-52 marker-slot-discard): the source card at the top left -
// UUmHudSourceSlot (/Game/S08/UI/Hud/WBP_UI_HUD_SLOT). The timeline is FS09SourceSlot's (S09/S09CardSlot.h; DE F-10,
// SD-54): own scheme - fly 200, the effect at once, shown 500 ms after arrival and while its effect runs; the opponent's
// scheme - fly 200 -> hold 1500 before its effect (a click on the field, Space or Enter skips: the field click passes
// through this widget, HitTestInvisible) -> while its effect runs; the opponent's maneuver boost - at least 1000 ms;
// discards - at least 1000 ms. The widget draws it:
//
//   card     UUmCardWidget 190 x 264 su (class S 120 x 166 in the class-s-hand show) at SLOT (24, 84) / S (16, 64): the
//            scan face up (the card is public: a played scheme, a revealed boost, a discard), the hero's back when the
//            face is unknown; nothing is printed over the scan (ВР-49).
//   fly      own card - from where it left the hand (UUmHudHand hands its leaving card over, no second flight), the
//            opponent's - from the centre of OPP-HAND; ease-out 200 ms; the ribbon appears on arrival.
//   ribbon   a plate under the card (4 su gap, ВР-VS2-HB34-07 - the pennant «on the frame» would cover the scan's corner):
//            the IC-50 / IC-51 / IC-52 glyph 24 su (32 su when DPI x UI scale < 1, IC-34 П-2 / HB-37 p. 9) and
//            «{СХЕМА|BOOST|СБРОС} · {hero}» (hud.slot.owner, type.tag 14 su; wraps, never cut - the plate grows).
//              СХЕМА  card.type.scheme, label card.navy, edge card.navy 1 su (filled, ВР-VS2-HB34-18);
//              BOOST  card.navy 0.92, label card.glyph, the «+N» chip (state-boost 24 / 32 su + font.card) inside at the
//                     right (ВР-VS2-HB34-16); the S ribbon is 190 su wide (HB-34 delta 04);
//              СБРОС  card.navy 0.92 with a text.secondary 2 su edge, label text.secondary (outline, ВР-VS2-HB34-18).
//   hold     the opponent's scheme: a 4 su bar 2 su under the ribbon (card.navy 0.92 track, card.glyph fill from 0 to 1
//            over the 1500 ms hold, ВР-VS2-HB34-17).
//   leave    the card leaves with a 150 ms opacity fade (04 §2.8 «уход 150»; reduced motion 100) - the widget's own,
//            for every ribbon (the S09 model ends a scheme in one frame, DE); a new card replaces it at once (CUE-006).
// Rollback: -S08SlateHud=slot - the Slate slot of S08FlowGameModeCardSlot.cpp, nothing of this widget is built.
// SHOT: 'SHOT widget id=UI-HUD-SLOT impl=umg state=fly|hold|show|fade fighter=own|opp bbox=... ribbon=scheme|boost|discard
//        face=0|1 class=L|S card=<w>x<h> ribbonSu=<w>x<h> icon=<su> chip=0|1 hold=<0..1>|- seq=<n>' - no card name.
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../../S09/S09CardSlot.h"
#include "../S08ArtHudWidgets.h"
#include "UmHudSourceSlot.generated.h"

class UBorder;
class UCanvasPanel;
class UImage;
class UOverlay;
class UTextBlock;
class UUmCardWidget;
class US08AnimatedIconWidget;

enum class EUmSlotPhase : uint8 { Hidden, Fly, Hold, Show, Fade };

/** What the slot shows now (the game mode builds it every frame from FS09SourceSlot; cheap: the widget compares). */
struct UNMATCHED_API FUmSlotModel {
  bool bShow = false;
  /** FS09SourceSlot::GetRevision: a new card (or the old one gone). */
  uint32 Revision = 0;
  int32 Seq = -1;
  EUmSlotPhase Phase = EUmSlotPhase::Hidden;
  FS09CardView Card;
  /** The face is public (a played / revealed / discarded card): the scan; else the owner's back. */
  bool bFace = true;
  FString HeroSlug;
  ES09SlotRibbon Ribbon = ES09SlotRibbon::Scheme;
  bool bOpponent = false;
  FString OwnerName;
  /** «+N» of a boost (UmCardWidget::NoBoostChip = none). */
  int32 Boost = -1;
  /** 0 -> 1 over the fly (FS09SourceSlot::FlyT); 1 at rest. */
  float FlyT = 1.0f;
  /** 0 -> 1 over the 1500 ms hold of the opponent's scheme; < 0 = no hold. */
  float HoldFrac = -1.0f;
  /** The centre (canvas su) the card flies from. */
  FVector2D FlyFromSu = FVector2D::ZeroVector;
};

struct UNMATCHED_API FUmSlotFrame {
  bool bClassS = false;
  float PxPerSu = 1.0f;
  /** SLOT (04 §1.6): (24, 84, 190, 264), S (16, 64, 120, 166) - canvas su. */
  FBox2D CardSu = FBox2D(ForceInit);
  /** The top left of the widget's GAME slot (the parts are placed relative to it). */
  FVector2D OriginSu = FVector2D::ZeroVector;
  bool operator==(const FUmSlotFrame& O) const {
    return bClassS == O.bClassS && PxPerSu == O.PxPerSu && CardSu == O.CardSu && OriginSu == O.OriginSu;
  }
  bool operator!=(const FUmSlotFrame& O) const { return !(*this == O); }
};

namespace UmHudSourceSlot {
inline constexpr float RibbonGapSu = 4.0f;
inline constexpr float RibbonMinSu = 28.0f;
inline constexpr float HoldGapSu = 2.0f;
inline constexpr float HoldBarSu = 4.0f;
inline constexpr float LeaveMs = 150.0f;   // 04 §2.8 «уход 150»
inline constexpr float ReducedMs = 100.0f;
inline constexpr float BoostRibbonSSu = 190.0f;  // HB-34 delta 04: the S BOOST ribbon is 190 su wide
/** The ribbon glyph id: marker-slot-scheme / -boost / -discard (IC-50...IC-52). */
UNMATCHED_API FName RibbonIcon(ES09SlotRibbon Ribbon);
/** The ribbon key (hud.slot.scheme / .boost / .discard) and the theme tokens of its plate and label. */
UNMATCHED_API const TCHAR* RibbonKey(ES09SlotRibbon Ribbon);
UNMATCHED_API FName RibbonFill(ES09SlotRibbon Ribbon);
UNMATCHED_API FName RibbonInk(ES09SlotRibbon Ribbon);
/** The glyph and chip side (su) at DPI x UI scale: 32 below 1 px per su (>= 21 px on screen, IC-34 П-2), else 24. */
UNMATCHED_API float GlyphSu(float PxPerSu);
UNMATCHED_API const TCHAR* PhaseName(EUmSlotPhase Phase);
UNMATCHED_API EUmSlotPhase PhaseOf(ES09SlotState State);
/** The ribbon's width (the card's; BOOST in class S 190 su) and its height for Rows rows of the label. */
UNMATCHED_API float RibbonWidthSu(bool bClassS, float CardWidthSu, ES09SlotRibbon Ribbon);
UNMATCHED_API float RibbonHeightSu(int32 Rows, float GlyphSize);
/** The opacity of the widget's leave at TMs (1 -> 0 over 150 ms, reduced 100). */
UNMATCHED_API float LeaveAlpha(float TMs, bool bReduced);
}  // namespace UmHudSourceSlot

UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmHudSourceSlot : public UUserWidget {
  GENERATED_BODY()

 public:
  static const TCHAR* const WidgetBlueprintPath;  // /Game/S08/UI/Hud/WBP_UI_HUD_SLOT
  static UClass* WidgetClass();

  virtual bool Initialize() override;
  /** Canvas "Root" > Card (WBP_UmCard), Ribbon (Border), RibbonEdge, RibbonIcon, RibbonText, BoostChip (overlay:
   *  BoostIcon, BoostText), HoldTrack, HoldFill. */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  bool HasAllParts(FString* OutMissing = nullptr) const;
  bool UsesCodeDefaultTree() const { return bCodeDefaultTree; }
  FString SourceName() const;

  void SetFrame(const FUmSlotFrame& InFrame);
  const FUmSlotFrame& GetFrame() const { return Frame; }
  /** The one data input (П1), every frame: a new revision lays the card and ribbon out (pools - nothing is created);
   *  otherwise only the fly offset, the hold bar and the leave move. */
  void ApplyModel(const FUmSlotModel& InModel);
  const FUmSlotModel& GetModel() const { return Model; }
  /** The phase drawn now (the leave is the widget's own fade). */
  EUmSlotPhase GetPhase() const;
  bool IsLeaving() const { return LeaveStartMs >= 0.0; }
  float GetLeaveAlpha() const { return LeaveAlphaNow; }
  /** The card + ribbon (+ hold bar) at rest, canvas su; invalid when nothing shows. */
  FBox2D DrawnRectSu() const;
  /** DrawnRectSu + the card in flight (canvas su). */
  FBox2D PaintedRectSu() const;
  FBox2D RibbonRectSu() const;
  int32 GetRibbonRows() const { return RibbonRows; }
  void CollectShotLines(TArray<FString>& Out) const;
  /** 'HUD-SLOT-UMG phase=<p> ...' when the drawn phase changed since the last call ('' otherwise). */
  FString TakeChangeLine();

  // ---- tests / the review sheet ----
  void SetClockOverrideMs(double Ms);
  void SetReducedForTest(int32 InReduced) { ReducedOverride = InReduced; }
  void SetSyncLoad(bool bOn);

  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UUmCardWidget> Card;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UBorder> Ribbon;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UCanvasPanel> Root;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UImage> RibbonEdge;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<US08AnimatedIconWidget> RibbonIcon;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UTextBlock> RibbonText;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UOverlay> BoostChip;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<US08AnimatedIconWidget> BoostIcon;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UTextBlock> BoostText;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UImage> HoldTrack;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UImage> HoldFill;

 private:
  void Layout();
  void ApplyMotion();
  void SetDecorShown(bool bOn);
  bool IsReduced() const;
  double NowMs() const;

  FUmSlotFrame Frame;
  bool bHasFrame = false;
  FUmSlotModel Model;
  bool bHasModel = false;
  bool bCodeDefaultTree = false;
  /** The card being drawn (kept through the leave after the model has no card any more). */
  FUmSlotModel Drawn;
  bool bDrawn = false;
  uint32 LaidRevision = 0;
  bool bLaidClassS = false;
  float LaidPx = 0.0f;
  int32 RibbonRows = 1;
  float GlyphNow = 24.0f;
  double LeaveStartMs = -1.0;
  float LeaveAlphaNow = 1.0f;
  FString LastPhase;
  bool bPhaseChanged = false;
  double ClockOverrideMs = -1.0;
  int32 ReducedOverride = -1;
};
