// VS-3 HB-28 (hud.csv HB-28; 04-hud-spec.md §2.9, §6.2; accepted mockup HB-26 art/imagegen/hud-decks-v1-codex, D3 /
// D4, ВР-VS2-HB26-03 / -04 / -12; ВР-HB14): one row of the deck panel - UUmDeckRow (pooled by UUmHudDeckPanel).
//
//   row      48 su on a panel.bg.inset cell, a panel.divider line under it (hover: panel.bg.hover); the v3 type disc 24 su
//            at (4, 3) - action-attack / -defense / -maneuver (versatile) / -scheme; «×N» 20 su font.card at x 32; the
//            name 20 su Roboto Bold Condensed, sentence case, text.primary at x 59; the values at the right (6 su in)
//            as runtime text font.card 20 su «A2 B4» / «D3 B1» / «V3 B2» / «B2» (ВР-HB14); the three share one baseline
//            (the cap top of the 20 su text 3 su under the row top, ВР-VS2-HB26-12).
//   name     D4: 20 su while it fits its column (59 .. values - 7); else one step down to 16 su; if it still does not
//            fit, it ends with «…» (the full name stays for the inspector). Nothing else is ever cut.
//   marks    the second line: chips (the Btn_Normal look: card.navy body, card.cream edge 0.45, radius 4), text type.tag
//            14 su centred, 4 su apart - VS-4 (VS-3 item 11, ВР-VS4-59): the chip is as high as the line of type.tag
//            (Slate's natural pitch, rounded up) + 1 su a side (>= 18 su) and sits 2 su over the row's bottom, so no
//            label is cut on any canvas (class S 1080p / 720p 150 % cut the descenders) - own: «В руке n» (n > 0),
//            «В сбросе n» (n > 0), «Осталось n»
//            (always, 0 included); opponent: only «В сбросе n» (n > 0) - never the hand or what is left (F-05, D7).
//   press    on the release through the arbiter (id hud.deck.row.<cardId>, DE-014): the inspector of the catalog card.
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../../S09/S09DeckPanel.h"
#include "../../S09/S09HudPress.h"
#include "../S08ArtHudWidgets.h"
#include "UmDeckRow.generated.h"

class UBorder;
class UCanvasPanel;
class UHorizontalBox;
class UImage;
class USizeBox;
class UTextBlock;
class US08AnimatedIconWidget;

/** What one row shows. */
struct UNMATCHED_API FUmDeckRowModel {
  FString CardId;
  /** The displayed name (nameRu in the RU build when the data has it, else name - ВР-VS2-02 / -HB26-03). */
  FString Name;
  FString CardType;  // ATTACK | DEFENSE | VERSATILE | SCHEME
  int32 Copies = 0;
  FString Values;    // «A2 B4» (ВР-HB14)
  bool bOwn = true;
  int32 InHand = 0;
  int32 InDiscard = 0;
  int32 Left = 0;
  bool operator==(const FUmDeckRowModel& O) const {
    return CardId == O.CardId && Name == O.Name && CardType == O.CardType && Copies == O.Copies && Values == O.Values &&
           bOwn == O.bOwn && InHand == O.InHand && InDiscard == O.InDiscard && Left == O.Left;
  }
  bool operator!=(const FUmDeckRowModel& O) const { return !(*this == O); }
};

/** The D4 fit of a name into its column. */
struct UNMATCHED_API FUmNameFit {
  float SizeSu = 20.0f;
  FString Shown;
  bool bEllipsis = false;
  float WidthSu = 0.0f;
  float ColumnSu = 0.0f;
};

namespace UmDeckRow {
inline constexpr float HeightSu = 48.0f;
inline constexpr float IconSu = 24.0f;
inline constexpr float IconXSu = 4.0f;
inline constexpr float IconYSu = 3.0f;
inline constexpr float CopiesXSu = 32.0f;
inline constexpr float NameXSu = 59.0f;
inline constexpr float ValuesRightSu = 6.0f;
inline constexpr float NameGapSu = 7.0f;
inline constexpr float TextSu = 20.0f;
inline constexpr float NameSmallSu = 16.0f;
inline constexpr float CapTopSu = 3.0f;      // the cap top of the 20 su text under the row top
inline constexpr float MarksYSu = 29.0f;
inline constexpr float MarkHSu = 18.0f;
inline constexpr float MarkPadXSu = 4.0f;
inline constexpr float MarkPadYSu = 1.0f;     // VS-4 (VS-3 item 11): 1 su over and under the centred label
inline constexpr float MarkBottomSu = 2.0f;   // the chips end 2 su over the row's bottom (the divider)
inline constexpr float MarkGapSu = 4.0f;
/** Roboto (hhea): ascender 1900 / 2048, cap height 1456 / 2048 - the baseline rule without Slate (a commandlet). */
inline constexpr float AscentEm = 1900.0f / 2048.0f;
inline constexpr float CapEm = 1456.0f / 2048.0f;
/** Type order of the rows (ВР-VS2-HB26-04): attack 0, defense 1, versatile 2, scheme 3 (other 4). */
UNMATCHED_API int32 TypeOrder(const FString& CardType);
/** The v3 type disc: action-attack / action-defense / action-maneuver (versatile) / action-scheme. */
UNMATCHED_API FName TypeIcon(const FString& CardType);
/** ВР-HB14: «A2 B4» / «D3 B1» / «V3 B2» / «B2» (no «B» part for a card without a printed BOOST). */
UNMATCHED_API FString Values(const FS09DeckListCard& Card);
/** The displayed name: nameRu in the RU build when the data has it, else name. */
UNMATCHED_API FString ShownName(const FS09DeckListCard& Card, bool bRu);
/** The width of Text at SizeSu of the type.button face (su): Slate's font measure, or the condensed estimate. */
UNMATCHED_API float MeasureSu(const FString& Text, float SizeSu, FName Token = FName(TEXT("type.button")));
/** The ascent (baseline below the text top) of SizeSu of Token (su). */
UNMATCHED_API float AscentSu(float SizeSu, FName Token = FName(TEXT("type.button")));
/** VS-4 (VS-3 item 11): the natural line of the mark label (type.tag 14 su; Slate's font measure, or the Roboto
 *  ascender - descender estimate without Slate), the chip height (the line rounded up + 2 x MarkPadYSu, >= MarkHSu)
 *  and the chips' top in the row (HeightSu - MarkBottomSu - chip). */
UNMATCHED_API float MarkLineSu();
UNMATCHED_API float MarkChipSu();
UNMATCHED_API float MarksTopSu();
/** D4: 20 su, else 16 su, else 16 su with «…». Measure(text, sizeSu) -> su. */
UNMATCHED_API FUmNameFit FitName(const FString& Name, float ColumnSu, TFunctionRef<float(const FString&, float)> Measure);
}  // namespace UmDeckRow

UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmDeckRow : public UUserWidget {
  GENERATED_BODY()

 public:
  virtual bool Initialize() override;
  /** SizeBox "Box" > Overlay "Stack" > Image "Cell", Image "Divider", Canvas "Canvas" > TypeIcon, CopiesText, NameText,
   *  ValuesText, HorizontalBox "Marks" > MarkHand / MarkDiscard / MarkLeft (Border) > MarkHandText / ... (TextBlock). */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  bool HasAllParts(FString* OutMissing = nullptr) const;

  /** The one data input; WidthSu = the row width (the panel's list width). Same input = no work. */
  void ApplyModel(const FUmDeckRowModel& InModel, float WidthSu);
  const FUmDeckRowModel& GetModel() const { return Model; }
  const FUmNameFit& GetNameFit() const { return NameFit; }
  void SetPress(FName InId, const TSharedPtr<FS09HudPressArbiter>& InArbiter, const FS09OnHudPressOutcome& InOnOutcome);
  FName GetPressId() const { return PressId; }
  /** The mark texts shown now (tests): «В руке 1», ... */
  TArray<FString> MarkTexts() const;
  bool IsHovered() const { return bHovered; }

  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<USizeBox> Box;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UImage> Cell;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UCanvasPanel> Canvas;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<US08AnimatedIconWidget> TypeIcon;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UTextBlock> CopiesText;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UTextBlock> NameText;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UTextBlock> ValuesText;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UHorizontalBox> Marks;

  virtual FReply NativeOnMouseButtonDown(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
  virtual FReply NativeOnMouseButtonUp(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
  virtual void NativeOnMouseEnter(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
  virtual void NativeOnMouseLeave(const FPointerEvent& InMouseEvent) override;
  virtual bool NativeSupportsKeyboardFocus() const override { return false; }

 private:
  void ApplyCell();
  FUmDeckRowModel Model;
  bool bHasModel = false;
  float WidthNow = 0.0f;
  FUmNameFit NameFit;
  bool bHovered = false;
  FName PressId;
  TSharedPtr<FS09HudPressArbiter> Arbiter;
  FS09OnHudPressOutcome OnOutcome;
  UPROPERTY() TArray<TObjectPtr<UBorder>> MarkChips;
  UPROPERTY() TArray<TObjectPtr<UTextBlock>> MarkLabels;
};
