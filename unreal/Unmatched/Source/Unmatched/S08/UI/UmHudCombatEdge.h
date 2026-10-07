// VS-3 HB-30 / HB-31 / HB-32 (docs/game-design/visual/06-tasks/hud.csv HB-30, HB-31, HB-32; 04-hud-spec.md §2.7, §3.5,
// §4.3, §5.2 step H9, §7.1; ВР-H04, ВР-H18, ВР-78; the accepted mockup HB-29 art/imagegen/hud-combat-v1-codex,
// ВР-VS2-HB29-01...15): one combat card at a field edge - UUmHudCombatEdge (/Game/S08/UI/Hud/WBP_UI_HUD_COMBAT_EDGE), two
// of them in the GAME screen: Side Own at the left edge, Side Opp at the right edge, whatever the role (ВР-H04).
//
//   card     UUmCardWidget 230 x 319 su (class S 150 x 208) at the top of the edge column (04 §2.7: L (24, 360), the
//            right one 24 su from the right edge; S (16, 240)); its states:
//              back      the committed card before the reveal: the face only on its owner's HUD (the attacker sees his
//                        attack card face up, ВР-VS2-HB29-07), the deck owner's back on the other HUD;
//              shield    the defender has chosen nothing: the empty CP-13 frame on card.navy, the v3 action-defense glyph
//                        64 su in its upper half and «Карта не выбрана» (hud.combat.slot.empty, type.body, text.secondary);
//              chosen    a defense card is chosen / committed face down: the defender's back + «Карта выбрана»
//                        (hud.combat.slot.chosen) on its own 24 su plate 4 su above the card (HB-29 delta 04 SLOT-CAPTION);
//              reveal    the face (the flip of HB-32 on the spot: UUmCardWidget::Flip, the defense card +120 ms);
//              nodefense the empty frame and the v3 marker-x-stamp 64 su centred, «appear» 200 ms (AB-8; -S08CrossLegacy:
//                        the text X in state.error), «Нет защиты» under it (hud.combat.nodefense, type.body; VS-4 -
//                        04 §3.8 «штамп X + текст», VS-3 item 13).
//   ribbon   a panel under the card (4 su gap): the type disc 24 su (v3 action-attack / action-defense), «АТАКА · Merlin»
//            / «ЗАЩИТА · Medusa» (hud.combat.role.*, type.tag 14 su, text.primary; wraps, never cut - the ribbon grows)
//            and the team chip 24 su at its right end (P1 circle, P2 hexagon, team.p<n>.screen; ВР-78). L 230 x 28,
//            S 150 x 24 (40 with two rows of text).
//   timer    HB-31 (ВР-H18): only on the own ribbon of the defender in the defense window - «{n} с» (hud.combat.timer,
//            type.tag, tabular digits) on its own 28 su row and the bar 230 x 4 (S 150 x 4, card.cream on
//            panel.bg.inset) at the ribbon bottom, n / window of its width. The last 10 s: a state.warning 2 su edge round
//            the ribbon and the v3 state-warning 24 su (IC-47) right of the seconds. Expired: 0 s, the buttons refuse
//            with why.deadline.passed. The clock is the model's deadline on FPlatformTime (the adapter derives it from
//            combatInfo.timeoutAt and the server time of the snapshot, never from the local wall clock); a 4 Hz
//            FTSTicker runs only while the timer is shown.
//   buttons  only the own defender in the defense window: «Защититься» (UUmButton Primary, Enter) and «Без защиты»
//            (Normal, N), one per row (HB-07 / HB-29 delta 04: L 1080p under the ribbon at y 747 / 803, ВР-VS2-HB29-11;
//            720p and class S at the top left, y 112 / 168 or 112 / 160). Disabled defend: no card chosen
//            (why.defense.pick), nothing to defend with (why.defense.none), the deadline passed, a command in flight.
//   leave    HB-32: after CUE-011 the edge fades its ribbon, plate and stamp in 150 ms (the card to 0.5) and the card flies
//            200 ms to LeaveToSu (the own card to the own discard chip, the opponent's to PANEL-OPP, ВР-VS3-55), x the
//            combat speed; reduced motion - opacity only, 100 ms.
//   input    a right click on the card opens the inspector (the owner's OnInspect with the shown face; VS-4 SC-22: a back
//            opens the hidden card - a placeholder without name or values, QA-005).
//   rollback -S08SlateHud=combat (the Slate text panels at the edges, BuildCombatStageHud).
// SHOT: 'SHOT widget id=UI-HUD-COMBAT-EDGE impl=umg state=back|shield|chosen|reveal|nodefense fighter=own|opp bbox=...
//        geom=painted visible=1 twin=0 source=... role=attack|defense face=0|1 class=L|S card=<w>x<h> ribbon=<w>x<h>
//        timer=<n>|- timerState=off|normal|warning|expired buttons=0|1 defend=<on|off:why> stamp=0|1 leave=0|1 seq=<n>'
//        - no card name, no key (privacy: face=1 on fighter=opp only with state=reveal, hud_contract.py check-trace).
// Trace on a change: 'HUD-TIMER left=<s> state=normal|warning|expired side=own seq=<n>'.
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "Containers/Ticker.h"
#include "../../S09/S09HudModel.h"
#include "../../S09/S09HudPress.h"
#include "../S08ArtHudWidgets.h"
#include "UmHudCombatEdge.generated.h"

class UBorder;
class UCanvasPanel;
class UImage;
class UTextBlock;
class UUmButton;
class UUmCardWidget;
class US08AnimatedIconWidget;

enum class EUmEdgeSide : uint8 { Own, Opp };
enum class EUmEdgeRole : uint8 { Attack, Defense };
enum class EUmEdgeState : uint8 { Hidden, Back, Shield, Chosen, Reveal, NoDefense };
enum class EUmTimerState : uint8 { Off, Normal, Warning, Expired };

/** What one edge shows (the adapter FUmCombatBlocks builds it from the snapshot and the staging). */
struct UNMATCHED_API FUmCombatEdgeModel {
  bool bShow = false;
  EUmEdgeRole Role = EUmEdgeRole::Attack;
  EUmEdgeState State = EUmEdgeState::Hidden;
  /** The combat this edge belongs to (the applied seq that opened it); a new one drops a leave in flight. */
  FString CombatKey;
  int32 Seq = -1;
  FString FighterName;  // as the backend has it (Medusa, King Arthur, Merlin)
  int32 TeamSlot = 0;   // 0 = P1 (circle), 1 = P2 (hexagon)
  /** The deck owner's hero slug: the back and the scan key (Merlin's cards: king-arthur). */
  FString HeroSlug;
  /** The card: with bFace its face, else only its instance id (QA-005: a hidden card has no face in the model). */
  FS09CardView Card;
  bool bFace = false;
  /** The flip of a reveal waits this long after the reveal (the defense card: +120 ms x speed, HB-32). */
  float FlipDelayMs = 0.0f;
  /** "+N" on the attack card (UmCardWidget::NoBoostChip = none). */
  int32 Boost = -1;
  // ---- the own defender in the defense window ----
  bool bButtons = false;
  FS09Reason DefendWhy;     // unset = enabled
  FS09Reason NoDefenseWhy;  // unset = enabled
  bool bTimer = false;
  /** The deadline on the FPlatformTime clock (s) and the length of the window (s) - the bar is left / window. */
  double DeadlineSec = 0.0;
  float WindowSec = 30.0f;
  bool operator==(const FUmCombatEdgeModel& O) const;
  bool operator!=(const FUmCombatEdgeModel& O) const { return !(*this == O); }
};

/** The layout event of one edge (canvas su). */
struct UNMATCHED_API FUmCombatEdgeFrame {
  bool bClassS = false;
  float PxPerSu = 1.0f;
  /** The top left of the edge's GAME slot (every rect below is canvas su; the widget places them relative to it). */
  FVector2D OriginSu = FVector2D::ZeroVector;
  FBox2D CardSu = FBox2D(ForceInit);
  FBox2D DefendSu = FBox2D(ForceInit);
  FBox2D NoDefenseSu = FBox2D(ForceInit);
  /** Where the card flies when it leaves (canvas su, the centre of the target). */
  FVector2D LeaveToSu = FVector2D::ZeroVector;
  float SpeedMul = 1.0f;
  bool operator==(const FUmCombatEdgeFrame& O) const {
    return bClassS == O.bClassS && PxPerSu == O.PxPerSu && OriginSu == O.OriginSu && CardSu == O.CardSu &&
           DefendSu == O.DefendSu && NoDefenseSu == O.NoDefenseSu && LeaveToSu == O.LeaveToSu && SpeedMul == O.SpeedMul;
  }
};

namespace UmHudCombatEdge {
inline constexpr float CardWLSu = 230.0f;
inline constexpr float CardHLSu = 319.0f;
inline constexpr float CardWSSu = 150.0f;
inline constexpr float CardHSSu = 208.0f;
inline constexpr float RibbonGapSu = 4.0f;       // card bottom -> ribbon
inline constexpr float RibbonLSu = 28.0f;         // 04 §2.7: 230 x 28
inline constexpr float RibbonSSu = 24.0f;         // 150 x 24
inline constexpr float TagRowLSu = 20.0f;         // one row of type.tag in the ribbon (HB-29 ROLE.tag)
inline constexpr float TagRowSSu = 16.0f;
inline constexpr float TagLeftSu = 32.0f;         // disc 3 + 24 + 5
inline constexpr float TagRightSu = 32.0f;        // gap 4 + chip 24 + 4
inline constexpr float DiscSu = 24.0f;
inline constexpr float TimerRowSu = 28.0f;        // HB-29 delta 04: ROLE-L 28 -> 56 (S 40 -> 68)
inline constexpr float TimerBarSu = 4.0f;
inline constexpr float CaptionHSu = 24.0f;        // «Карта выбрана» plate (HB-29 SLOT-CAPTION)
inline constexpr float CaptionGapSu = 4.0f;
inline constexpr float SlotGlyphSu = 64.0f;       // action-defense / marker-x-stamp
inline constexpr float WarnSu = 24.0f;            // state-warning (IC-47)
inline constexpr float WarnFromSec = 10.0f;       // ВР-H18: the last 10 s
inline constexpr float TickSec = 0.25f;           // 4 Hz
inline constexpr float LeaveFadeMs = 150.0f;      // HB-32: 150 + 200
inline constexpr float LeaveFlyMs = 200.0f;
inline constexpr float LeaveCardAlpha = 0.5f;
inline constexpr float ReducedMs = 100.0f;
/** The state name of the gate (04 §7.1): back | shield | chosen | reveal | nodefense ('' for hidden). */
UNMATCHED_API const TCHAR* StateName(EUmEdgeState State);
UNMATCHED_API const TCHAR* TimerStateName(EUmTimerState State);
/** HB-31: off without a timer; expired at <= 0 s; warning from 10 s on (the shown «10 с»); else normal. */
UNMATCHED_API EUmTimerState TimerStateFor(bool bTimer, double LeftSec);
/** The seconds shown: ceil, never below 0. */
UNMATCHED_API int32 ShownSeconds(double LeftSec);
UNMATCHED_API FVector2D CardSize(bool bClassS);
/** The width the role text has in the ribbon (L 166, S 86 su). */
UNMATCHED_API float TagRoomSu(bool bClassS);
/** «АТАКА · Merlin» / «ЗАЩИТА · Medusa» (hud.combat.role.attack / .defense). */
UNMATCHED_API FText RoleText(EUmEdgeRole Role, const FString& Fighter);
/** The ribbon height for TagRows rows of the role text, + the timer row (su). */
UNMATCHED_API float RibbonHeightSu(bool bClassS, int32 TagRows, bool bTimer);
/** HB-32 leave at TMs (from its start) of the speed: the opacity of the ribbon / plate / stamp, of the card and the
 *  0..1 progress of the flight. Reduced: everything fades in 100 ms, no flight. */
UNMATCHED_API void LeaveAt(float TMs, float SpeedMul, bool bReduced, float& OutDecor, float& OutCard, float& OutFly);
/** The length of a leave (ms): 350 x speed (reduced 100). */
UNMATCHED_API float LeaveMs(float SpeedMul, bool bReduced);
}  // namespace UmHudCombatEdge

UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmHudCombatEdge : public UUserWidget {
  GENERATED_BODY()

 public:
  static const TCHAR* const WidgetBlueprintPath;  // /Game/S08/UI/Hud/WBP_UI_HUD_COMBAT_EDGE
  static UClass* WidgetClass();

  virtual bool Initialize() override;
  virtual void BeginDestroy() override;
  /** Canvas "Root" > SlotUnderlay, SlotFrame, SlotGlyph, SlotText, Card, Stamp, StampText, CaptionPlate > CaptionText,
   *  Ribbon (Border) + WarnEdge, RoleIcon, RoleText, TeamChip, TimerText, TimerBar (track TimerTrack + fill), WarnIcon,
   *  DefendButton, NoDefenseButton. */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  bool HasAllParts(FString* OutMissing = nullptr) const;
  bool UsesCodeDefaultTree() const { return bCodeDefaultTree; }
  FString SourceName() const;

  /** Own (left edge) or Opp (right edge) - fixed at build, never from the role (ВР-H04). */
  void SetSide(EUmEdgeSide InSide) { Side = InSide; }
  EUmEdgeSide GetSide() const { return Side; }
  void SetFrame(const FUmCombatEdgeFrame& InFrame);
  const FUmCombatEdgeFrame& GetFrame() const { return Frame; }
  /** The one data input (П1). Same model = no work. A face that becomes public flips (HB-32); NoDefense stamps. */
  void ApplyModel(const FUmCombatEdgeModel& InModel);
  const FUmCombatEdgeModel& GetModel() const { return Model; }
  /** HB-32: the leave after CUE-011 (fade 150 + flight 200 x speed) from now; IsLeaving until it ends, then hidden. */
  void StartLeave();
  /** A new combat (CUE-008): a leave in flight ends now, nothing of the old combat stays. */
  void CutLeave();
  bool IsLeaving() const { return LeaveStartMs >= 0.0; }
  /** Steps the delayed flip, the leave and (without the ticker, tests) the timer at the widget clock. */
  void Step();
  /** HB-31: the timer state now (the clock of the widget). */
  EUmTimerState GetTimerState() const { return TimerNow; }
  int32 GetTimerSeconds() const { return TimerSecondsNow; }
  /** OnDefend / OnNoDefense answer a resolved press (the arbiter, DE-014); OnInspect - a right click on the card. */
  void SetInput(const TSharedPtr<FS09HudPressArbiter>& InArbiter, TFunction<void(const FS09HudPressOutcome&)> InOnDefend,
                TFunction<void(const FS09HudPressOutcome&)> InOnNoDefense, TFunction<void(const FS09CardView&)> InOnInspect);
  void CollectShotLines(TArray<FString>& Out) const;
  /** The rect the edge draws now (canvas su): card + ribbon (+ caption, + buttons). */
  FBox2D DrawnRectSu() const;
  /** ВР-VS3-72: DrawnRectSu + the HB-32 leave flight of the card (canvas su; trace 'HUD-EDGE-PAINT' while leaving). */
  FBox2D PaintedRectSu() const;
  FBox2D RibbonRectSu() const;
  /** Trace lines since the last call (HUD-TIMER, HUD-STAMP). */
  TArray<FString> TakeTrace();

  // ---- tests ----
  /** >= 0 freezes the clock (ms; FPlatformTime otherwise). The timer reads it as seconds. */
  void SetClockOverrideMs(double Ms);
  void SetReducedForTest(int32 InReduced) { ReducedOverride = InReduced; }
  void SetSyncLoad(bool bOn);
  int32 GetRibbonRows() const { return TagRows; }
  bool IsStampShown() const;
  float GetLeaveDecorAlpha() const { return LeaveDecorNow; }
  float GetLeaveCardAlpha() const { return LeaveCardNow; }
  FVector2D GetLeaveOffsetSu() const { return LeaveOffsetNow; }
  bool IsFlipPending() const { return PendingFlipAtMs >= 0.0; }

  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UCanvasPanel> Root;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UUmCardWidget> Card;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UBorder> Ribbon;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<US08AnimatedIconWidget> RoleIcon;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UTextBlock> RoleText;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UTextBlock> TimerText;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UImage> TimerBar;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UUmButton> DefendButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UUmButton> NoDefenseButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<US08AnimatedIconWidget> Stamp;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UImage> SlotUnderlay;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UImage> SlotFrame;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<US08AnimatedIconWidget> SlotGlyph;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UTextBlock> SlotText;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UTextBlock> StampText;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UBorder> CaptionPlate;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UTextBlock> CaptionText;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UImage> WarnEdge;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UImage> TeamChip;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UImage> TimerTrack;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<US08AnimatedIconWidget> WarnIcon;

 protected:
  virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;

 private:
  void Relayout();
  void ApplyContent(const FUmCombatEdgeModel* Old);
  void ApplyTimer(bool bForce);
  void ApplyButtons();
  void ApplyLeave();
  void SetDecorOpacity(float Alpha);
  void StartTicker();
  void StopTicker();
  bool OnTicker(float DeltaTime);
  bool IsReduced() const;
  double NowMs() const;
  bool IsCrossLegacy() const;

  EUmEdgeSide Side = EUmEdgeSide::Own;
  FUmCombatEdgeFrame Frame;
  bool bHasFrame = false;
  FUmCombatEdgeModel Model;
  bool bHasModel = false;
  bool bCodeDefaultTree = false;
  int32 TagRows = 1;
  // the card face drawn now (the flip turns it)
  bool bFaceShown = false;
  FString CardShownId;
  double PendingFlipAtMs = -1.0;
  // the stamp of the current combat (played once)
  FString StampKey;
  // HB-31
  EUmTimerState TimerNow = EUmTimerState::Off;
  int32 TimerSecondsNow = -1;
  FTSTicker::FDelegateHandle TickerHandle;
  // HB-32
  double LeaveStartMs = -1.0;
  float LeaveDecorNow = 1.0f;
  float LeaveCardNow = 1.0f;
  FVector2D LeaveOffsetNow = FVector2D::ZeroVector;
  FVector2D CardCentreSu = FVector2D::ZeroVector;
  // input
  TSharedPtr<FS09HudPressArbiter> Arbiter;
  TFunction<void(const FS09CardView&)> OnInspect;
  // tests
  double ClockOverrideMs = -1.0;
  int32 ReducedOverride = -1;
  TArray<FString> PendingTrace;
};
