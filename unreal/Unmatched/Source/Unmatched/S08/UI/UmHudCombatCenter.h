// VS-3 HB-33 (docs/game-design/visual/06-tasks/hud.csv HB-33; 04-hud-spec.md §2.7 (CENTER: y 80, 560 x <= 160, class S
// 480), §1.6, §6.2, §7.1; ВР-H05; the accepted mockup HB-29 art/imagegen/hud-combat-v1-codex, ВР-VS2-HB29-14): the combat
// centre over the field - UUmHudCombatCenter (/Game/S08/UI/Hud/WBP_UI_HUD_COMBAT).
//
//   panel    the panel skin (panel.bg 0.92 + panel.edge), centred on the canvas, top y 80 (class S 64; 8 su under STATUS when
//            STATUS is shown), 560 su wide (S 480), as high as its content (12 su padding top and bottom), never above
//            160 su (ВР-VS2-HB29-14). Transient (04 §1.6 exception): it may cross FIELD while it is shown.
//   wait     the attacker in the defense window: «Ждём защиту…» (hud.combat.wait.defense, type.heading).
//   read     the flip and the read hold: nothing drawn (the cards at the edges speak, HB-29 «reveal»).
//   effects  the fired effect lines (F-01, R-02): «{card}: {text}» in type.body 16 su, at most 2 rows then «…» (the only
//            ellipsis, 04 §6.2; the full text is the row's tooltip and the card inspector); rows 22 su apart, lines 6 su
//            apart. The current line - a state.pending 3 su bar at its left and text.primary, the others text.secondary;
//            a cancelled line - the v3 marker-x-stamp 24 su at its left («appear» 200 ms), so it differs by shape. At
//            most 3 lines (S 2) while the panel stays <= 160 su, the rest in the chip «ещё {n}» (hud.combat.effects.more,
//            panel.bg.inset, radius 4, 24 su, type.tag) at the text column.
//   slam/hit the score «{a} : {d}» (hud.combat.score, type.display 48 su) with the slam (~180 ms: 1.15 -> 1.0 x speed;
//            reduced - opacity 100 ms) and the outcome «{fighter} побеждает» (.wins) / «Защита держит» (.holds) in
//            type.title 28 su; under them the resolved lines while the panel stays <= 160 su, else the «ещё {n}» chip.
//            The label holds to the end of CUE-011 (~1.5 s, F-01). No blot, brush, splash or glow (ВР-09).
//   rollback -S08SlateHud=combat (the whole combat) or -S08SlateHud=combatcenter (only the centre: the Slate outcome box
//            CombatOutcomeBox, the UMG edges stay) - ВР-VS3-50.
// SHOT: 'SHOT widget id=UI-HUD-COMBAT impl=umg state=wait|read|effects|slam|hit fighter=none bbox=... geom=painted
//        visible=0|1 twin=0 source=... class=L|S h=<su> lines=<n> shown=<k> more=<m> cancelled=<c> current=<i>
//        ellipsis=<e> score=<a>:<d>|- outcome=wins|holds|- seq=<n>' - counts only, no card name, no text.
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../S08ArtHudWidgets.h"
#include "UmHudCombatCenter.generated.h"

class UBorder;
class UCanvasPanel;
class UImage;
class USizeBox;
class UTextBlock;
class UVerticalBox;
class US08AnimatedIconWidget;

enum class EUmCenterState : uint8 { Hidden, Wait, Read, Effects, Slam, Hit };

/** One effect line as the centre prints it. */
struct UNMATCHED_API FUmCenterLine {
  /** The card's title in the UI language when the data has it, else as the data has it. */
  FString Title;
  /** The printed effect text (+ "-> option"); empty = the title alone (never the parser's kind / value prose). */
  FString Text;
  bool bCancelled = false;
  /** The X stamp of a cancelled line is drawn now (it appears 400 ms after its line, 200 ms long). */
  bool bStamp = false;
  bool operator==(const FUmCenterLine& O) const {
    return Title == O.Title && Text == O.Text && bCancelled == O.bCancelled && bStamp == O.bStamp;
  }
  FString Display() const;
};

struct UNMATCHED_API FUmCombatCenterModel {
  EUmCenterState State = EUmCenterState::Hidden;
  int32 Seq = -1;
  bool bScore = false;
  int32 AttackValue = -1;
  int32 DefenseValue = -1;
  bool bAttackerWins = false;
  FString AttackerName;
  /** Every line fired so far, in the server's order (the cancelled line of the attack card after its canceller). */
  TArray<FUmCenterLine> Lines;
  /** The highlighted line (index into Lines), -1 = none. */
  int32 Current = -1;
  bool operator==(const FUmCombatCenterModel& O) const {
    return State == O.State && Seq == O.Seq && bScore == O.bScore && AttackValue == O.AttackValue &&
           DefenseValue == O.DefenseValue && bAttackerWins == O.bAttackerWins && AttackerName == O.AttackerName &&
           Lines == O.Lines && Current == O.Current;
  }
  bool operator!=(const FUmCombatCenterModel& O) const { return !(*this == O); }
};

struct UNMATCHED_API FUmCombatCenterFrame {
  bool bClassS = false;
  float PxPerSu = 1.0f;
  FVector2D CanvasSu = FVector2D::ZeroVector;
  /** The top left of the GAME slot (canvas su). */
  FVector2D OriginSu = FVector2D::ZeroVector;
  /** The bottom of STATUS when it is shown (su), -1 otherwise: the panel keeps 8 su under it. */
  float StatusBottomSu = -1.0f;
  float SpeedMul = 1.0f;
  bool operator==(const FUmCombatCenterFrame& O) const {
    return bClassS == O.bClassS && PxPerSu == O.PxPerSu && CanvasSu == O.CanvasSu && OriginSu == O.OriginSu &&
           StatusBottomSu == O.StatusBottomSu && SpeedMul == O.SpeedMul;
  }
};

namespace UmHudCombatCenter {
inline constexpr float WidthLSu = 560.0f;
inline constexpr float WidthSSu = 480.0f;
inline constexpr float TopLSu = 80.0f;
inline constexpr float TopSSu = 64.0f;
inline constexpr float MaxHeightSu = 160.0f;
inline constexpr float PadSu = 12.0f;
inline constexpr float PadXSu = 16.0f;
inline constexpr float TextLeftSu = 44.0f;        // the line text column (HB-29: CENTER.x + 44)
inline constexpr float MarkLeftSu = 12.0f;        // the current bar / the X stamp
inline constexpr float BarWSu = 3.0f;
inline constexpr float StampSu = 24.0f;
inline constexpr float LineGapSu = 6.0f;
inline constexpr float RowPitchSu = 22.0f;        // 04 §2.7
inline constexpr float BodySu = 16.0f;
inline constexpr int32 MaxRows = 2;
inline constexpr float ScoreInkSu = 36.0f;        // HB-29: the score's ink box 36, the outcome 26, gaps 4 / 8
inline constexpr float OutcomeInkSu = 26.0f;
inline constexpr float ScoreGapSu = 4.0f;
inline constexpr float OutcomeGapSu = 8.0f;
inline constexpr float WaitHSu = 40.0f;
inline constexpr float ChipHSu = 24.0f;
inline constexpr float ChipPadSu = 8.0f;
inline constexpr float SlamMs = 180.0f;
inline constexpr float SlamFromScale = 1.15f;
inline constexpr int32 MaxLinesL = 3;
inline constexpr int32 MaxLinesS = 2;
UNMATCHED_API const TCHAR* StateName(EUmCenterState State);
/** The box height of a line of Rows rows: 24 / 46. */
UNMATCHED_API float LineBoxSu(int32 Rows);
/** One line fitted to the text column: at most 2 rows, then «…» (OutRows, bOutEllipsis). */
UNMATCHED_API FString FitLine(const FString& Display, float ColumnSu, int32& OutRows, bool& bOutEllipsis);
/** What the panel shows: the first index, the count of the lines drawn, the rest in the chip; and its height (su).
 *  Effects: up to MaxLines (L 3, S 2) ending at the current line, while <= 160 su; slam / hit: under the score and
 *  the outcome, while <= 160 su (else none and the chip). Rows[i] = the rows of Lines[i]. */
struct FPlan {
  int32 First = 0;
  int32 Count = 0;
  int32 More = 0;
  float HeightSu = 0.0f;
};
UNMATCHED_API FPlan Plan(EUmCenterState State, bool bScore, const TArray<int32>& Rows, int32 Current, bool bClassS);
}  // namespace UmHudCombatCenter

UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmHudCombatCenter : public UUserWidget {
  GENERATED_BODY()

 public:
  static const TCHAR* const WidgetBlueprintPath;  // /Game/S08/UI/Hud/WBP_UI_HUD_COMBAT
  static UClass* WidgetClass();
  static constexpr int32 PoolSize = 3;

  virtual bool Initialize() override;
  /** Canvas "Root" > Panel (Border) ; WaitText, ScoreText, OutcomeText, EffectLines (VerticalBox: Line0..2 = SizeBox >
   *  Canvas > Bar0..2, Mark0..2, Text0..2), MoreChip (Border) > MoreText. */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  bool HasAllParts(FString* OutMissing = nullptr) const;
  bool UsesCodeDefaultTree() const { return bCodeDefaultTree; }
  FString SourceName() const;

  void SetFrame(const FUmCombatCenterFrame& InFrame);
  const FUmCombatCenterFrame& GetFrame() const { return Frame; }
  /** The one data input (П1): the staging tick (state, lines, highlight). Same model = no work. */
  void ApplyModel(const FUmCombatCenterModel& InModel);
  const FUmCombatCenterModel& GetModel() const { return Model; }
  void CollectShotLines(TArray<FString>& Out) const;
  /** The panel rect (canvas su), invalid while hidden or reading. */
  FBox2D PanelRectSu() const;
  const UmHudCombatCenter::FPlan& GetPlan() const { return PlanNow; }
  /** The lines fitted now (the display strings as drawn, «…» included) - tests. */
  const TArray<FString>& GetShownTexts() const { return ShownTexts; }
  int32 GetEllipsisCount() const { return EllipsisCount; }
  /** >= 0 freezes the clock (ms; the line stamps too); FPlatformTime otherwise. */
  void SetClockOverrideMs(double Ms);
  void SetReducedForTest(int32 InReduced) { ReducedOverride = InReduced; }
  float GetScoreScale() const { return ScoreScaleNow; }
  void Step();

  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UCanvasPanel> Root;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UBorder> Panel;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UTextBlock> ScoreText;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UTextBlock> OutcomeText;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UVerticalBox> EffectLines;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UTextBlock> MoreText;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UTextBlock> WaitText;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UBorder> MoreChip;

 protected:
  virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;

 private:
  void Relayout();
  bool IsReduced() const;
  double NowMs() const;
  FUmCombatCenterFrame Frame;
  bool bHasFrame = false;
  FUmCombatCenterModel Model;
  bool bHasModel = false;
  bool bCodeDefaultTree = false;
  UmHudCombatCenter::FPlan PlanNow;
  TArray<FString> ShownTexts;
  int32 EllipsisCount = 0;
  // the pool (found by name)
  UPROPERTY() TArray<TObjectPtr<USizeBox>> LineBoxes;
  UPROPERTY() TArray<TObjectPtr<UImage>> LineBars;
  UPROPERTY() TArray<TObjectPtr<US08AnimatedIconWidget>> LineMarks;
  UPROPERTY() TArray<TObjectPtr<UTextBlock>> LineTexts;
  /** The line key of each pool row's played stamp (seq:index) - the X appears once. */
  TArray<FString> StampPlayed;
  double SlamStartMs = -1.0;
  float ScoreScaleNow = 1.0f;
  double ClockOverrideMs = -1.0;
  int32 ReducedOverride = -1;
};
