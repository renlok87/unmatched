// VS-3 HB-24 / HB-25 review sheet in the backend-less icon gallery (-S08IconGallery, review tooling only, never a
// match): -S08IconGalleryHand=marmoreal|sarpedon puts the real UUmHudHand (theme, card widgets, registry scans) on the
// GAME layout of the window (FUmHudLayout with the FIELD the live K1 camera projects on that board - the VS-2 traces
// 'HUD-LAYOUT ... field=' at 1080p 100 %, scaled with the window), over the bench K1 frame of the board as a picture
// (Marmoreal original with the painted backdrop -ConceptPaste, Sarpedon original lit3d; the HB-22 backgrounds, ВР-VS2-01).
// The cards are the run I hands and the HB-22 test hand (docs/game-design/evidence/S01/content-<hero>.json, the S01
// capture of the content API). One state per second of the gallery clock (-S08IconGalleryTimes=600,1600,...):
//   0 rest-new  1 hover  2 selected  3 unplayable (attack step, hover on the Harpy card: why.banner.mismatch)
//   4 boost-maneuver  5 boost-attack (King Arthur)  6 drop (9 / 7, two marked)  7 lowered  8 fan-3  9 fan-7  10 fan-9
//   11 empty  12 draw (the last card flies in from the deck chip; t within the second = the flight time)
// -S08IconGalleryHandPlain: the panel.bg.inset fill instead of the picture (with -S08CardArtLegacy: no scan, no back, no
// board art - the sheet that may go to git, ВР-CP12).
// It is a sheet of the widget, not an acceptance frame (those are packaged -Bench runs of the "Frames" step).
// Trace: 'UMGALLERY hand board=<b> state=<k>:<name> ...' + the hand's SHOT lines.
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../../S09/S09HudModel.h"
#include "UmHudHand.h"
#include "UmHudLayout.h"
#include "UmHandGallery.generated.h"

class UCanvasPanel;
class UImage;
class UTextBlock;
class UTexture2D;

namespace UmHandGallery {
inline constexpr int32 StateCount = 13;
UNMATCHED_API const TCHAR* StateName(int32 State);
/** The FIELD of the board on this window (su): the live 1080p 100 % envelope scaled with the window height. */
UNMATCHED_API FBox2D FieldSu(const FString& Board, const FVector2D& CanvasSu, float PxPerSu);
}  // namespace UmHandGallery

UCLASS()
class UNMATCHED_API UUmHandGalleryWidget : public UUserWidget {
  GENERATED_BODY()

 public:
  virtual bool Initialize() override;
  TArray<FString> Build(const FString& Board, const FVector2D& CanvasSu, float PxPerSu);
  /** State = floor(TMs / 1000); the hand clock runs from the start of that second. */
  TArray<FString> SetClockMs(float TMs);
  UUmHudHand* GetHand() const { return Hand; }

 private:
  FUmHandModel ModelFor(int32 State) const;
  UPROPERTY() TObjectPtr<UCanvasPanel> Root;
  UPROPERTY() TObjectPtr<UImage> Background;
  UPROPERTY() TObjectPtr<UTextBlock> Label;
  UPROPERTY() TObjectPtr<UUmHudHand> Hand;
  UPROPERTY() TObjectPtr<UTexture2D> BackgroundTexture;
  FString BoardNow;
  FUmHudLayout Layout;
  int32 StateNow = -1;
  TArray<FS09CardView> Medusa;
  TArray<FS09CardView> Arthur;
};
