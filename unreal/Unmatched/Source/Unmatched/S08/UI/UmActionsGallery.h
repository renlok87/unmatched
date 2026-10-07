// VS-4 HB-43 review sheet in the backend-less icon gallery (-S08IconGallery, review tooling only, never a match), the
// way of the VS-3 / V1 / V2 sheets (ВР-VS3-47, ВР-VS3-62):
//   -S08IconGalleryActions=marmoreal|sarpedon   the real UUmHudActions, UUmHudDecks and UUmHudTop in a UUmGameHud on the
//       GAME layout of the window (FIELD of the live K1 camera) over the bench K1 frame of the board as a picture
//       (Marmoreal original with the painted backdrop -ConceptPaste, Sarpedon original lit3d - the HB-42 backgrounds,
//       ВР-VS2-HB42-01), fed with the HB-42 state matrix (art/imagegen/hud-actions-v1-codex/facts.json): the owner Medusa
//       on Marmoreal, King Arthur on Sarpedon; the DECKS chips of HB-26 (ВР-VS2-HB42-10: «Колода 23» / «Сброс 2» Feint on
//       top, «Колода 25» / «Сброс 2» Swift Strike on top); n = 2 / 1 from ACTIONS_PER_TURN, need 1 / have 0 for the hand
//       limit (ВР-VS2-HB42-06). One state per second of the gallery clock:
//         0 own-2  1 own-2-why  2 own-1-why  3 own-0  4 own-0-why  5 mode-maneuver  6 mode-maneuver-why  7 mode-attack
//         8 mode-scheme  9 discard-why  10 opp  11 opp-why  12 hover  13 focus  14 keys  15 keys-own-0
//       The pointed cell carries the software cursor of its form (IC-59 pointer over an enabled cell, IC-60 denied over a
//       disabled one) drawn 1 : 1 at its hot spot; TOP shows «Журнал» (IC-55) in class S.
// These are sheets of the widgets, not acceptance frames (those are packaged -Bench runs of the "Frames" step).
// Trace: 'UMGALLERY actions board=<b> state=<k>:<name> ...' + the blocks' SHOT lines.
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../../S09/S09DeckPanel.h"
#include "UmHudActions.h"
#include "UmHudLayout.h"
#include "UmActionsGallery.generated.h"

class UCanvasPanel;
class UImage;
class UTextBlock;
class UTexture2D;
class UUmGameHud;
class UUmHudDecks;
class UUmHudTop;

namespace UmActionsGallery {
inline constexpr int32 StateCount = 16;
UNMATCHED_API const TCHAR* StateName(int32 State);
/** The FUmActionsInput of a state (HB-42 A4) and its pointed cell (INDEX_NONE: none) in a class. */
UNMATCHED_API FUmActionsInput StateInput(int32 State, bool bClassS, int32& OutPointer);
}  // namespace UmActionsGallery

UCLASS()
class UNMATCHED_API UUmActionsGalleryWidget : public UUserWidget {
  GENERATED_BODY()

 public:
  virtual bool Initialize() override;
  TArray<FString> Build(const FString& Board, const FVector2D& CanvasSu, float PxPerSu);
  TArray<FString> SetClockMs(float TMs);

 private:
  void ApplyState(int32 State, TArray<FString>& Lines);
  UPROPERTY() TObjectPtr<UCanvasPanel> Root;
  UPROPERTY() TObjectPtr<UImage> Background;
  UPROPERTY() TObjectPtr<UTextBlock> Label;
  UPROPERTY() TObjectPtr<UUmGameHud> Game;
  UPROPERTY() TObjectPtr<UUmHudActions> Actions;
  UPROPERTY() TObjectPtr<UUmHudDecks> Decks;
  UPROPERTY() TObjectPtr<UUmHudTop> Top;
  UPROPERTY() TObjectPtr<UImage> CursorImage;
  UPROPERTY() TObjectPtr<UTexture2D> BackgroundTexture;
  FUmHudLayout Layout;
  FString BoardNow;
  int32 StateNow = -1;
  float PxNow = 1.0f;
};
