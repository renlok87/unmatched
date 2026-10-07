// VS-3 HB-27 (docs/game-design/visual/06-tasks/hud.csv HB-27; 04-hud-spec.md §2.9, §1.6, §4.3, §7.1; ВР-H16; accepted
// mockup HB-26 art/imagegen/hud-decks-v1-codex, ВР-VS2-HB26-06 / -09): DECKS - UUmHudDecks
// (/Game/S08/UI/Hud/WBP_UI_HUD_DECKS), the own deck and discard counters: the only place they show (ВР-H16).
//
//   chips    two UUmButton (Normal look, Btn_Normal skin) inside the DECKS slot (UmHudLayout::DeckChipRect):
//            class L - 56 su high, RU 156 / 124 su, EN 144 / 136 su, 8 su apart; the mini card 32 x 45 su 9 su from the
//            chip's left edge (its keyline at 8), the label «Колода n» / «Сброс n» (hud.decks.deck / .discard, 20 su
//            Roboto Bold Condensed, sentence case, tabular numerals) 50 su from the left; class S - 64 x 48 su, the mini
//            card 18 x 25.3 su 5 su from the left, the number only (20 su) 28 su from the left.
//   minis    the deck chip - the back of the own hero (UUmCardWidget MiniChip, face down: CP-05 / CP-06); the discard
//            chip - the top card of the own discard pile (the last public entry; a face-down entry shows its back);
//            an empty pile - the v3 resource-card icon, 32 su while DPI x UI scale < 1, else 24 su (IC-34 П-1: >= 24 px).
//   stale    hud.decks.stale «≈{n}» replaces the deck number while the server's deck count is from an older seq
//            (ViewerPanel().bDeckCountStale); the discard the same with bDiscardStale.
//   input    a click on the deck chip opens the deck panel on «Ваша» (HB-28); on the discard chip - the same panel with
//            the filter «Только сброс» (the old discard browser merged into it). The press is the arbiter's (DE-014).
//   flights  the chip centres go to FUmHudLayout (DeckChipCentreSu / DiscardChipCentreSu): the draw flies from the deck
//            chip (HB-24), the combat cards go to the discard chip (HB-32).
//   rollback -S08SlateHud=decks: the Slate buttons «YOUR DECK (K)» / «BROWSE DISCARD PILES (D)» of the side panel.
// SHOT: 'SHOT widget id=UI-HUD-DECKS impl=umg state=idle|stale ... class=L|S deck=<n> discard=<n> deckStale=0|1
//        discardStale=0|1 top=face|back|none chips=<w>x<h>,<w>x<h> lang=ru|en' (counts only, no card name).
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../../S09/S09HudModel.h"
#include "../../S09/S09HudPress.h"
#include "../S08ArtHudWidgets.h"
#include "UmHudDecks.generated.h"

class UCanvasPanel;
class UScaleBox;
class USizeBox;
class UTextBlock;
class UUmButton;
class UUmCardWidget;
class US08AnimatedIconWidget;

/** What the chips show (the own panel of the applied snapshot). */
struct UNMATCHED_API FUmDecksModel {
  bool bShow = false;
  int32 DeckCount = 0;
  bool bDeckStale = false;
  int32 DiscardCount = 0;
  bool bDiscardStale = false;
  /** The own hero slug: the back of the deck chip and the scan key of the top card. */
  FString HeroSlug;
  /** The top of the own discard pile (the last entry); bHasTop false = an empty pile. */
  bool bHasTop = false;
  FS09CardView Top;
  bool operator==(const FUmDecksModel& O) const {
    return bShow == O.bShow && DeckCount == O.DeckCount && bDeckStale == O.bDeckStale && DiscardCount == O.DiscardCount &&
           bDiscardStale == O.bDiscardStale && HeroSlug == O.HeroSlug && bHasTop == O.bHasTop &&
           Top.InstanceId == O.Top.InstanceId && Top.CardId == O.Top.CardId && Top.bHidden == O.Top.bHidden;
  }
  bool operator!=(const FUmDecksModel& O) const { return !(*this == O); }
};

/** The layout event of DECKS: the class, px per su, the slot rect (canvas su), the language of the chip widths. */
struct UNMATCHED_API FUmDecksFrame {
  bool bClassS = false;
  float PxPerSu = 1.0f;
  FBox2D RectSu = FBox2D(ForceInit);
  bool bEnglish = false;
  bool operator==(const FUmDecksFrame& O) const {
    return bClassS == O.bClassS && PxPerSu == O.PxPerSu && RectSu == O.RectSu && bEnglish == O.bEnglish;
  }
};

namespace UmHudDecks {
inline constexpr float ChipHeightLSu = 56.0f;
inline constexpr float ChipHeightSSu = 48.0f;
inline constexpr float MiniWSu = 32.0f;   // 02 §6.2: the DECKS mini card 32 x 45
inline constexpr float MiniHSu = 45.0f;
inline constexpr float MiniSWSu = 18.0f;  // HB-26 fix1: class S 18 x 25.3125
inline constexpr float MiniLeftLSu = 9.0f;   // the keyline at 8 su, the card at 9 (HB-26 delta 04)
inline constexpr float MiniLeftSSu = 5.0f;   // the keyline at 4, the card at 5
inline constexpr float TextLeftLSu = 50.0f;
inline constexpr float TextLeftSSu = 28.0f;
inline constexpr float TextSu = 20.0f;
/** FUmDecksModel of the viewer's panel (null = hidden). HeroSlug = the own hero (the deck owner's). */
UNMATCHED_API FUmDecksModel Gather(const FS09PlayerPanel* Own, const FString& HeroSlug);
/** «Колода 23» / «Колода ≈24» (L); «23» / «≈24» (S). */
UNMATCHED_API FText DeckLabel(const FUmDecksModel& M, bool bClassS);
/** «Сброс 2» (L); «2» (S); «≈» with bDiscardStale. */
UNMATCHED_API FText DiscardLabel(const FUmDecksModel& M, bool bClassS);
/** IC-34 П-1: the resource-card icon of an empty pile - 32 su below 1 px per su, else 24 su. */
UNMATCHED_API float IconSuFor(float PxPerSu);
/** idle | stale (04 §7.1). */
UNMATCHED_API const TCHAR* StateName(const FUmDecksModel& M);
}  // namespace UmHudDecks

UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmHudDecks : public UUserWidget {
  GENERATED_BODY()

 public:
  static const TCHAR* const WidgetBlueprintPath;  // /Game/S08/UI/Hud/WBP_UI_HUD_DECKS
  static UClass* WidgetClass();

  virtual bool Initialize() override;
  /** CanvasPanel "Row" > DeckChip, DiscardChip (UUmButton) + DeckMiniBox > DeckMiniScale > DeckMini (UUmCardWidget),
   *  DeckIcon, DeckCount; the same for the discard (DiscardMiniBox, DiscardMiniScale, DiscardMini, DiscardIcon,
   *  DiscardCount). */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  bool HasAllParts(FString* OutMissing = nullptr) const;
  bool UsesCodeDefaultTree() const { return bCodeDefaultTree; }
  FString SourceName() const;

  /** The layout event (window / UI scale / language). */
  void SetFrame(const FUmDecksFrame& InFrame);
  const FUmDecksFrame& GetFrame() const { return Frame; }
  /** The one data input (П1): the applied snapshot. Same model = no work. */
  void ApplyModel(const FUmDecksModel& InModel);
  const FUmDecksModel& GetModel() const { return Model; }
  /** OnPress(outcome, bDiscard) answers a resolved press of a chip. */
  void SetInput(const TSharedPtr<FS09HudPressArbiter>& InArbiter, TFunction<void(const FS09HudPressOutcome&, bool)> InOnPress);
  void CollectShotLines(TArray<FString>& Out) const;
  /** The chip rect (canvas su) as laid out now. */
  FBox2D ChipRectSu(int32 Index) const;
  /** Applies since the first model (tests: same model = no work). */
  int32 GetApplyCount() const { return ApplyCount; }
  void SetSyncLoad(bool bOn);
  void SetLegacyForTest(int32 InLegacy);

  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UCanvasPanel> Row;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UUmButton> DeckChip;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UUmButton> DiscardChip;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UTextBlock> DeckCount;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UTextBlock> DiscardCount;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<USizeBox> DeckMiniBox;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UScaleBox> DeckMiniScale;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UUmCardWidget> DeckMini;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<US08AnimatedIconWidget> DeckIcon;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<USizeBox> DiscardMiniBox;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UScaleBox> DiscardMiniScale;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UUmCardWidget> DiscardMini;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<US08AnimatedIconWidget> DiscardIcon;

 private:
  void Relayout();
  void ApplyContent();
  FUmDecksFrame Frame;
  bool bHasFrame = false;
  FUmDecksModel Model;
  bool bHasModel = false;
  bool bCodeDefaultTree = false;
  int32 ApplyCount = 0;
  float IconSuNow = 0.0f;
};
