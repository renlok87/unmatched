// VS-4 HB-39...HB-41 review sheet in the backend-less icon gallery (-S08IconGallery, review tooling only, never a match),
// the way of the VS-3 / V1 sheets (ВР-VS3-47, ВР-VS3-62):
//   -S08IconGalleryFeed=marmoreal|sarpedon   the real UUmHudLog, UUmToastStack and UUmHudSubtitle (FUmFeedBlocks) in a
//       UUmGameHud on the GAME layout of the window and the real UUmHudHand, over the bench K1 frame of the board as a
//       picture (Marmoreal original with the painted backdrop -ConceptPaste, Sarpedon original lit3d - the HB-38
//       backgrounds), fed with the HB-38 state matrix (art/imagegen/hud-feed-v1-codex/facts.json): the owner Medusa on
//       Marmoreal, King Arthur on Sarpedon; the log lines of run I (MS-LOG seq 5...23 / 3...26) rendered through ms.log.*
//       by UmHudLog::DescribeTrail; the toasts and lines of the tables and the VO script. The obstacles of the chain: the
//       figure polygons of the frames (art/imagegen/hud-composition-v1-codex/masks.json, + 4 px), the spaces as FIELD
//       (conservative - the live client uses each space's rect), every block rect of the layout. One state per second:
//         0 log  1 toast-info  2 toast-warning  3 toast-error  4 toast-stack  5 toast-bottom  6 sub  7 sub-lowered
//         8 combat (the defense window: the log hidden, the spaces no obstacle, two toasts + the long line)
// These are sheets of the widgets, not acceptance frames (those are packaged -Bench runs of the "Frames" step).
// Trace: 'UMGALLERY feed board=<b> state=<k>:<name> ...' + the blocks' SHOT and TOAST lines.
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../../S09/S09HudModel.h"
#include "UmHudFeedBlocks.h"
#include "UmHudLayout.h"
#include "UmFeedGallery.generated.h"

class UCanvasPanel;
class UImage;
class UTextBlock;
class UTexture2D;
class UUmGameHud;
class UUmHudHand;

namespace UmFeedGallery {
inline constexpr int32 StateCount = 9;
UNMATCHED_API const TCHAR* StateName(int32 State);
}  // namespace UmFeedGallery

UCLASS()
class UNMATCHED_API UUmFeedGalleryWidget : public UUserWidget {
  GENERATED_BODY()

 public:
  virtual bool Initialize() override;
  TArray<FString> Build(const FString& Board, const FVector2D& CanvasSu, float PxPerSu);
  TArray<FString> SetClockMs(float TMs);

 private:
  void ApplyState(int32 State, double Start, TArray<FString>& Lines);
  void PushLog(double NowMs);
  FUmFeedInput InputNow(double NowMs) const;
  UPROPERTY() TObjectPtr<UCanvasPanel> Root;
  UPROPERTY() TObjectPtr<UImage> Background;
  UPROPERTY() TObjectPtr<UTextBlock> Label;
  UPROPERTY() TObjectPtr<UUmGameHud> Game;
  UPROPERTY() TObjectPtr<UUmHudHand> Hand;
  UPROPERTY() TObjectPtr<UTexture2D> BackgroundTexture;
  FUmFeedBlocks Feed;
  FUmHudLayout Layout;
  FString BoardNow;
  int32 StateNow = -1;
  double StateStart = 0.0;
  bool bBadgeDone = false;
  bool bCombat = false;
  /** The six v2 figures of the bench frame (masks.json polygons, + 4 px), canvas su. */
  TArray<FBox2D> FiguresSu;
  TArray<FS09CardView> Medusa;
  TArray<FS09CardView> Arthur;
};
