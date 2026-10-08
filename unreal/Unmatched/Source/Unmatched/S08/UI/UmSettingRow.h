// VS-7 S4 SC-24...SC-30 (docs/game-design/visual/06-tasks/screens.csv SC-24...SC-30; 04-hud-spec.md §1.8; the accepted CX-32
// mockups art/imagegen/sc24-pause-codex ... sc30-settings-graphics-codex and their decisions ВР-VS5-SC24-02,
// ВР-VS5-SC25-01 / -02, ВР-VS5-SC26-01, ВР-VS5-SC27-01, ВР-VS5-SC28-01, ВР-VS5-SC29-01, ВР-VS5-SC30-01): one row of the
// PAUSE settings - UUmSettingRow, pooled by UUmScreenPause (code-built, no WBP of its own).
//
//   row      520 su wide; padding 8 su top and bottom; the owner draws the panel.divider line between rows.
//   slider   Label (type.body, text.primary) at x 0, wrapped in 140 su; the track 200 su at x 148 (slider.track skin, fill
//            card.cream from the left to the value, the slider.thumb 16 su centred on the value); Value «{n} %»
//            (settings.value.percent, type.body, right-aligned in 56 su after the track); then either the Mute check box
//            (24 su + 8 + «Без звука» type.caption text.secondary, up to 2 lines) or a Note (type.caption, «75–150 %»).
//            Height 48 + 16. A longer value / caption (EN, the pseudo-locale) shortens the track, never the text (ВР-VS7-46).
//            A drag moves the value in steps (ВР-VS5-SC25-02: 5 %), UI-SLIDER-TICK on every 10 % crossed (08 hooks);
//            the value is committed on the release only (04 §1.8: the scale applies after the release; the bus volume
//            changes in the release frame, SC-25).
//   check    the check box 24 su at x 148 (check.off / check.on skins + the IC-57 ui-check glyph 24 su when on: the
//            shape carries the state) and the value word «вкл» / «выкл» (type.body, text.secondary) 8 su after it.
//   chips    the Label on its own line, the chips 8 su below (UUmButton 32 su, text + 2 x 12 su, 8 su apart; the selected
//            one btn.selected with card.glyph text); a chips line that would pass 520 su (pseudo-locale) wraps; an
//            optional Note (type.caption, text.secondary) 8 su under the chips; SC-29 adds the KeyHintSample at the right.
//   input    the row takes the mouse: a press on the track / the box / the mute box; the chips are UUmButtons through
//            the press arbiter (DE-014). Commit(Key, Value) carries the s08.Settings name and value (ApplySetting).
//   rows of the screens: master + masterMute, music, sfx, ui, vo, ambience + ambienceMute, subtitles, describeSounds
//            (SC-25); language, uiScale, ruleHints, keyHints (SC-26, SC-27, SC-29); speed, reduced (SC-28, no shake row -
//            ВР-SC06); graphics (SC-30).
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../../S09/S09HudPress.h"
#include "UmSettingRow.generated.h"

class UBorder;
class UCanvasPanel;
class UTextBlock;
class UUmButton;
class US08AnimatedIconWidget;

enum class EUmSettingKind : uint8 { Slider, Check, Chips };

struct UNMATCHED_API FUmSettingRowModel {
  /** The s08.Settings name (ApplySetting): master, music, ..., language, uiScale, ruleHints, keyHints, speed, reduced,
   *  graphics (the last is GameUserSettings, the owner's own apply). */
  FName Key;
  EUmSettingKind Kind = EUmSettingKind::Slider;
  FText Label;
  // slider
  int32 Value = 0;
  int32 Min = 0;
  int32 Max = 100;
  int32 Step = 5;
  /** The Mute check box after the value (MuteKey: masterMute / ambienceMute). */
  FName MuteKey;
  bool bMuted = false;
  /** Slider: the note after the value (SC-27 «75–150 %»); chips: the line under the chips (SC-29, SC-30). */
  FText Note;
  // check
  bool bOn = false;
  // chips
  TArray<FText> Chips;
  TArray<FString> ChipValues;
  int32 Selected = -1;
  /** SC-29: the KeyHintSample (the END TURN disc with its key chip) at the right of the chips. */
  bool bSample = false;
  bool bSampleChip = true;
  bool bClassS = false;
  bool operator==(const FUmSettingRowModel& O) const;
  bool operator!=(const FUmSettingRowModel& O) const { return !(*this == O); }
};

namespace UmSettingRow {
inline constexpr float WidthSu = 520.0f;
inline constexpr float PadSu = 8.0f;
inline constexpr float BandSu = 48.0f;      // the control band of a slider / check row
inline constexpr float LabelWSu = 140.0f;   // the label column of a slider / check row
inline constexpr float ControlXSu = 148.0f; // the track / the box
inline constexpr float TrackWSu = 200.0f;
inline constexpr float ValueWSu = 56.0f;
inline constexpr float ChipHSu = 32.0f;
inline constexpr float ChipPadSu = 12.0f;
inline constexpr float GapSu = 8.0f;
inline constexpr float BoxSu = 24.0f;
inline constexpr float ThumbSu = 16.0f;
inline constexpr float LineSu = 20.0f;      // a type.body line
inline constexpr float CaptionLineSu = 18.0f;
/** The scroll bar's lane at the right of the rows (ВР-VS5-SC24-03: 4 su wide, 4 su inside the edge). */
inline constexpr float ScrollGutterSu = 8.0f;
/** The value of a slider at local x (su from the row's left), snapped to Step and clamped to [Min, Max]. */
UNMATCHED_API int32 ValueAtX(const FUmSettingRowModel& M, float X, float TrackW = TrackWSu);
/** The thumb centre x (su from the row's left) of a value. */
UNMATCHED_API float ThumbX(const FUmSettingRowModel& M, int32 Value, float TrackW = TrackWSu);
/** «{n} %» of the current culture (settings.value.percent). */
UNMATCHED_API FText Percent(int32 Value);
/** The 10 % band of a value - UI-SLIDER-TICK plays when it changes during a drag (08-screen-audio-hooks SC-25). */
inline int32 TickBand(int32 Value) { return Value / 10; }
}  // namespace UmSettingRow

UCLASS()
class UNMATCHED_API UUmSettingRow : public UUserWidget {
  GENERATED_BODY()

 public:
  struct FInput {
    TFunction<void(FName Key, const FString& Value)> OnCommit;
    TFunction<void(FName BankId)> OnSound;
  };

  virtual bool Initialize() override;
  void SetInput(FName InPressPrefix, const TSharedPtr<FS09HudPressArbiter>& InArbiter, FInput InInput);
  /** The model and the class; returns the row height (su). Same model = no work. */
  float Apply(const FUmSettingRowModel& InModel, float PxPerSu);
  const FUmSettingRowModel& GetModel() const { return Model; }
  float GetHeightSu() const { return HeightSu; }
  /** The texts as drawn (tests and the SHOT line). */
  FString GetLabelText() const;
  FString GetValueText() const;
  FString GetNoteText() const;
  int32 GetChipCount() const { return Chips.Num(); }
  UUmButton* GetChip(int32 Index) const { return Chips.IsValidIndex(Index) ? Chips[Index].Get() : nullptr; }
  bool IsSampleShown() const;
  bool IsSampleChipShown() const;
  /** Every element of the row inside 520 su and below its label (no overlap; tests). */
  bool LayoutFits(FString* OutWhy = nullptr) const;
  int32 GetChipLines() const { return ChipLines; }
  // ---- synthetic input (tests, the evidence drive): the same paths as the mouse
  void SimulateDrag(int32 ToValue);
  void SimulateToggle(bool bMute = false);
  void SimulateChip(int32 Index);
  bool IsDragging() const { return bDragging; }

 protected:
  virtual FReply NativeOnMouseButtonDown(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
  virtual FReply NativeOnMouseMove(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
  virtual FReply NativeOnMouseButtonUp(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
  virtual void NativeOnMouseCaptureLost(const FCaptureLostEvent& CaptureLostEvent) override;

 private:
  void Build();
  void Layout();
  void ShowValue(int32 InValue);
  void EnsureChips(int32 Count);
  void Commit(FName Key, const FString& Value);
  void Sound(const TCHAR* Bank);
  void OnChip(int32 Index, const FS09HudPressOutcome& Outcome);
  FVector2D LocalSu(const FGeometry& G, const FPointerEvent& E) const;

  UPROPERTY() TObjectPtr<UCanvasPanel> Canvas;
  UPROPERTY() TObjectPtr<UTextBlock> Label;
  UPROPERTY() TObjectPtr<UBorder> Track;
  UPROPERTY() TObjectPtr<UBorder> Fill;
  UPROPERTY() TObjectPtr<UBorder> Thumb;
  UPROPERTY() TObjectPtr<UTextBlock> Value;
  UPROPERTY() TObjectPtr<UBorder> Box;
  UPROPERTY() TObjectPtr<US08AnimatedIconWidget> BoxCheck;
  UPROPERTY() TObjectPtr<UTextBlock> BoxText;
  UPROPERTY() TObjectPtr<UBorder> MuteBox;
  UPROPERTY() TObjectPtr<US08AnimatedIconWidget> MuteCheck;
  UPROPERTY() TObjectPtr<UTextBlock> MuteText;
  UPROPERTY() TObjectPtr<UTextBlock> Note;
  UPROPERTY() TArray<TObjectPtr<UUmButton>> Chips;
  UPROPERTY() TObjectPtr<UBorder> SampleBox;
  UPROPERTY() TObjectPtr<UUmButton> Sample;

  FUmSettingRowModel Model;
  bool bHasModel = false;
  float Px = 1.0f;
  float HeightSu = 64.0f;
  float LabelHSu = 20.0f;
  /** ВР-VS7-46: the track gives way (200 -> at least 120 su) when the value or the mute caption is longer (EN, pseudo). */
  float TrackW = UmSettingRow::TrackWSu;
  float ValueW = UmSettingRow::ValueWSu;
  float AfterX = 420.0f;
  float BandCySu = 32.0f;
  bool bLabelAbove = false;
  float ChipsYSu = 0.0f;
  int32 ChipLines = 0;
  TArray<FBox2D> ChipRects;
  FBox2D SampleRect;
  bool bDragging = false;
  int32 DragValue = 0;
  FName PressPrefix;
  TSharedPtr<FS09HudPressArbiter> Arbiter;
  FInput Input;
};
