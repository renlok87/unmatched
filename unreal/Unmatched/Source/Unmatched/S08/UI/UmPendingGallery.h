// VS-4 HB-35 / HB-37 review sheet in the backend-less icon gallery (-S08IconGallery, review tooling only, never a match),
// the way of the VS-3 sheets (ВР-VS3-47, ВР-VS3-62):
//   -S08IconGalleryPending=marmoreal|sarpedon   the real UUmHudPending and UUmHudSourceSlot in a UUmGameHud on the GAME
//       layout of the window (FIELD of the live K1 camera) over the bench K1 frame of the board as a picture (Marmoreal
//       original with the painted backdrop -ConceptPaste, Sarpedon original lit3d - the HB-34 backgrounds), fed with the
//       HB-34 state matrix (art/imagegen/hud-pending-v1-codex/facts.json; ВР-VS2-HB34-06): the card data of the S01
//       content capture (names and texts as the backend has them - King Arthur's EN, ВР-VS2-HB34-04), the strings of the
//       tables. One state per second of the gallery clock:
//         0 modal-pick  1 modal-order  2 choose-one (geometry: no MVP card, ВР-HB11)  3 number (the same)
//         4 compact-move  5 compact-place  6 compact-target  7 compact-space  8 toast  9 collapsed  10 discard
//         11 boost  12 opp  13 after-combat  14 slot-opp-fly  15 slot-opp-hold  16 slot-opp-show  17 slot-opp-fade
//         18 slot-boost  19 slot-discard
// These are sheets of the widgets, not acceptance frames (those are packaged -Bench runs of the "Frames" step); the board
// plates V-11 / V-12 are the field's (not drawn here).
// Trace: 'UMGALLERY pending board=<b> state=<k>:<name> ...' + the blocks' SHOT lines.
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../../S09/S09HudModel.h"
#include "UmHudLayout.h"
#include "UmPendingGallery.generated.h"

class UCanvasPanel;
class UImage;
class UTextBlock;
class UTexture2D;
class UUmGameHud;
class UUmHudPending;
class UUmHudSourceSlot;

namespace UmPendingGallery {
inline constexpr int32 StateCount = 20;
UNMATCHED_API const TCHAR* StateName(int32 State);
}  // namespace UmPendingGallery

UCLASS()
class UNMATCHED_API UUmPendingGalleryWidget : public UUserWidget {
  GENERATED_BODY()

 public:
  virtual bool Initialize() override;
  TArray<FString> Build(const FString& Board, const FVector2D& CanvasSu, float PxPerSu);
  TArray<FString> SetClockMs(float TMs);

 private:
  void ApplyState(int32 State, TArray<FString>& Lines);
  FS09CardView CardOf(const TCHAR* Hero, const TCHAR* Name) const;
  UPROPERTY() TObjectPtr<UCanvasPanel> Root;
  UPROPERTY() TObjectPtr<UImage> Background;
  UPROPERTY() TObjectPtr<UTextBlock> Label;
  UPROPERTY() TObjectPtr<UUmGameHud> Game;
  UPROPERTY() TObjectPtr<UUmHudPending> Pending;
  UPROPERTY() TObjectPtr<UUmHudSourceSlot> SourceSlot;
  UPROPERTY() TObjectPtr<UTexture2D> BackgroundTexture;
  FString BoardNow;
  FUmHudLayout Layout;
  int32 StateNow = -1;
  /** hero slug -> the deck's cards (S01 content: names, nameRu, texts). */
  TMap<FString, TArray<FS09CardView>> Decks;
};
