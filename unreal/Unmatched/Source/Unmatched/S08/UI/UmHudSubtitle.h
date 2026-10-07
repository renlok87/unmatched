// VS-4 HB-41 (docs/game-design/visual/06-tasks/hud.csv HB-41; 04-hud-spec.md §2.13, §4.3, §7.1; the accepted mockup
// HB-38 art/imagegen/hud-feed-v1-codex, ВР-VS2-HB38-08 / -15; docs/game-design/audio/02-audio-design.md §3.4): the
// subtitle of a hero's line - UUmHudSubtitle (/Game/S08/UI/Hud/WBP_UI_HUD_SUB). It replaces the Slate SubtitleBox
// (S08FlowGameModeAudio.cpp, a bold line without a plate; rollback -S08SlateHud=sub).
//
//   look   a capsule (T_Skin_Capsule: panel.bg 0.92, panel.edge 1 su, radius 4 su; 02 §3.5 - no text on the scene
//          without a plate), padding 12 su, height = the line box + 2 x 5 su (>= 28 su); the speaker «{name}:»
//          (hud.sub.speaker) type.tag card.cream, 8 su, the line type.body text.primary. One line up to 720 su; a longer
//          line wraps to a second one (never cut). A line without a speaker (the harpy's described cry,
//          UI-ACC-016) is the line alone.
//   place  the owner's group placement (UmHudFeed::Place): under the toasts, its bottom 4 su over the hand cards at
//          rest, down with the lowered hand; the same chain upward when it would cross a figure, a space or a block.
//   time   the line's length + 500 ms (FS08VoDirector); a new line replaces the old one; in <= 150 ms (hover.ms);
//          UI-ACC-015 off - nothing; reduced motion - no fade.
//   input  HitTestInvisible: never takes the mouse.
// SHOT: 'SHOT widget id=UI-HUD-SUB impl=umg state=shown fighter=none bbox=... lines=1|2 speaker=0|1 lowered=0|1' - no text.
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../S08ArtHud.h"
#include "../S08ArtHudWidgets.h"
#include "UmHudSubtitle.generated.h"

class UBorder;
class UCanvasPanel;
class UHorizontalBox;
class UTextBlock;

/** One line on screen. */
struct UNMATCHED_API FUmSubtitleModel {
  /** The speaker's name (data: the hero / fighter name), '' = none. */
  FText Speaker;
  FText Line;
  double StartMs = 0.0;
  /** The line's length + 500 ms. */
  double DurationMs = 0.0;
  bool IsSet() const { return !Line.IsEmpty() && DurationMs > 0.0; }
};

/** The capsule's size and rows (su). */
struct UNMATCHED_API FUmSubtitlePlan {
  FVector2D SizeSu = FVector2D::ZeroVector;
  float SpeakerWidthSu = 0.0f;
  float LineWidthSu = 0.0f;
  int32 Lines = 1;
};

namespace UmHudSubtitle {
using FMeasure = TFunctionRef<float(const FString& Text, float SizeSu, FName Token)>;
/** The capsule of a model (720 su cap; a longer line wraps to two rows). */
UNMATCHED_API FUmSubtitlePlan Plan(const FUmSubtitleModel& Model, FMeasure Measure);
/** Text measured at the drawn scale (su), an estimate without a renderer. */
UNMATCHED_API float MeasureSu(const FString& Text, float SizeSu, FName Token, float PxPerSu);
/** «{name}:» of hud.sub.speaker. */
UNMATCHED_API FText SpeakerText(const FString& Name);
inline constexpr float LineBoxSu = 19.0f;  // Roboto 16 su: the line box (HB-38 P7: 29 su capsule = 19 + 2 x 5)
}  // namespace UmHudSubtitle

UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmHudSubtitle : public UUserWidget {
  GENERATED_BODY()

 public:
  static const TCHAR* const WidgetBlueprintPath;  // /Game/S08/UI/Hud/WBP_UI_HUD_SUB

  virtual bool Initialize() override;
  /** CanvasPanel "Root" > Border "Capsule" > HorizontalBox "Row" > TextBlock "Speaker", TextBlock "Line". */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  static UClass* WidgetClass();
  bool HasAllParts(FString* OutMissing = nullptr) const;
  bool UsesCodeDefaultTree() const { return bCodeDefaultTree; }
  FString SourceName() const;

  /** The data input (П1): a new line replaces the old one; an unset model hides. */
  void ApplyModel(const FUmSubtitleModel& InModel);
  void SetPxPerSu(float InPxPerSu, bool bInReduced);
  /** The fade-in and the end of the line; true when it just ended (place the stack again). */
  bool Tick(double NowMs);
  void Hide();
  bool IsShown() const;
  /** The capsule's size (zero when hidden) - the owner places it with the toasts. */
  FVector2D DesiredSizeSu() const { return IsShown() ? PlanNow.SizeSu : FVector2D::ZeroVector; }
  /** The capsule at its rect (canvas su); bLowered = the hand is lowered (the SHOT state). */
  void ApplyPlacement(const FBox2D& RectSu, bool bInLowered);
  FBox2D GetRectSu() const { return RectSu; }
  const FUmSubtitleModel& GetModel() const { return Model; }
  const FUmSubtitlePlan& GetPlan() const { return PlanNow; }
  void SetMeasureForTest(TFunction<float(const FString&, float, FName)> InMeasure) { MeasureOverride = MoveTemp(InMeasure); }
  void CollectShotLines(TArray<FString>& Out) const;

  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget))
  TObjectPtr<UTextBlock> Speaker;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget))
  TObjectPtr<UTextBlock> Line;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional))
  TObjectPtr<UCanvasPanel> Root;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional))
  TObjectPtr<UBorder> Capsule;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional))
  TObjectPtr<UHorizontalBox> Row;

 private:
  void BindFromTree();
  void Restyle();
  FUmSubtitleModel Model;
  FUmSubtitlePlan PlanNow;
  FBox2D RectSu = FBox2D(ForceInit);
  float PxPerSu = 1.0f;
  bool bReduced = false;
  bool bLowered = false;
  bool bShown = false;
  bool bPlaced = false;
  TFunction<float(const FString&, float, FName)> MeasureOverride;
  bool bCodeDefaultTree = false;
};
