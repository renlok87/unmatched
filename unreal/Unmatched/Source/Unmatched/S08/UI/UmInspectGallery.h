// VS-4 V4 (H13) review sheet in the backend-less icon gallery (-S08IconGallery, review tooling only, never a match):
// -S08IconGalleryInspect=marmoreal|sarpedon puts the real UUmScreenInspect (theme, WBP_UI_SCR_INSPECT or the code tree,
// UUmCardWidget with the registry scans and backs) over the bench K1 frame of the board as a picture (Marmoreal original -
// the painted backdrop -ConceptPaste, Sarpedon original - lit3d; the CX-23 mockups' background is Sarpedon P10), at the
// window's canvas and class. The data is the S01 capture of the content API (docs/game-design/evidence/S01/content-
// <hero>.json: names, nameRu, types, values, BOOST, copies, textEn - as the backend has them) and the HB-26 run I moment
// of UmDecksGallery (own Medusa: Gaze of Stone x2 in hand). One state per second of the gallery clock
// (-S08IconGalleryTimes=600,1600,...), each a fresh modal shown at alpha 1:
//   0 own          SC-21 own: Medusa's Gaze of Stone (RU scan), the copies line of the own deck (3 - 2 in hand - 0)
//   1 own-en       the same after Tab: the EN scan 400 x 558 in 408 x 566 and the EN name
//   2 loading      the scan loading: the frame and the 32 su spinner (the load held for the sheet, + 600 ms)
//   3 missing      the card without a scan key (the hero unknown): the 02 §6.1 plate + «Скан карты недоступен»
//   4 hidden       SC-22: the viewer King Arthur, Medusa's back, «Скрытая информация», the owner - nothing of the card
//   5 deck         SC-23: «Колода · Medusa», 11 cards x copies (sum 30) in the catalogue order, the first rows
//   6 deck-end     the grid scrolled to its last rows (wheel steps)
//   7 deck-card    Hiss and Slither opened from the grid: the «×3» chip after BOOST and «Назад»
//   8 deck-ka      the King Arthur grid (16 cards, sum 30)
//   9 opp-card     the opponent's public card (King Arthur's Swift Strike from his discard): no copies line
// Trace: 'UMGALLERY inspect board=<b> state=<k>:<name> ...' + the modal's SHOT and CARD-ART lines.
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../../S09/S09DeckPanel.h"
#include "UmHudLayout.h"
#include "UmInspectGallery.generated.h"

class UCanvasPanel;
class UImage;
class UTextBlock;
class UTexture2D;
class UUmScreenInspect;

namespace UmInspectGallery {
inline constexpr int32 StateCount = 10;
UNMATCHED_API const TCHAR* StateName(int32 State);
}  // namespace UmInspectGallery

UCLASS()
class UNMATCHED_API UUmInspectGalleryWidget : public UUserWidget {
  GENERATED_BODY()

 public:
  virtual bool Initialize() override;
  TArray<FString> Build(const FString& Board, const FVector2D& CanvasSu, float PxPerSu);
  /** State = floor(TMs / 1000); the loading clock runs from the start of that second. */
  TArray<FString> SetClockMs(float TMs);
  UUmScreenInspect* GetScreen() const { return Screen; }

 private:
  void ApplyState(int32 State, double TMs);
  UPROPERTY() TObjectPtr<UCanvasPanel> Root;
  UPROPERTY() TObjectPtr<UImage> Background;
  UPROPERTY() TObjectPtr<UTextBlock> Label;
  UPROPERTY() TObjectPtr<UUmScreenInspect> Screen;
  UPROPERTY() TObjectPtr<UTexture2D> BackgroundTexture;
  FString BoardNow;
  FUmHudLayout Layout;
  int32 StateNow = -1;
  FS09DeckList Medusa;
  FS09DeckList Arthur;
};
