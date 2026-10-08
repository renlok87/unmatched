// VS-4 HB-45 / HB-46 / FX-38 review sheet in the backend-less icon gallery (-S08IconGallery, review tooling only, never a
// match), the way of the VS-3 / V1 / V2 sheets (ВР-VS3-47, ВР-VS3-62):
//   -S08IconGalleryWorld=marmoreal|sarpedon   the real US08ArtTagWidget / US08ArtPlateWidget on their H12 look (UI/
//       UmWorldLayer.h) and the real UUmZoneBadges over the bench K1 frame of the board as a picture (Marmoreal original with
//       the painted backdrop -ConceptPaste, Sarpedon original lit3d - the HB-44 backgrounds, ВР-VS2-HB44-01), placed at the
//       panel boxes of the accepted HB-44 mockup (art/imagegen/hud-world-v1-codex/layout-measurements.json: the boxes of
//       the mockup canvas nearest in panel size per window width - 1920x1080 100 % or 1280x720 150 % - scaled with the
//       window, each panel centred on its box), the six v2 figures: Medusa, the Harpies 1-3
//       (sidekicks[] order), King Arthur, Merlin; HP of the start and of run I (HB-44 facts). The zone states hover a space of
//       one, two and three zones (Marmoreal M02 / M01 / M04, Sarpedon S01 / S21 / S25; the space polygons of
//       art/imagegen/hud-composition-v1-codex/masks.json registered on the frames). One state per second:
//         0 tags-start  1 tags-run-I  2 hover-medusa  3 hover-harpy1  4 hover-arthur  5 hover-merlin  6 attack-medusa
//         7 zone-1  8 zone-2  9 zone-3
//       The bench frames carry the old client's small world labels (the HB-07 / HB-42 background artefact); the live game
//       hides them under the tag layer (SetWorldLabelsSuppressed).
// These are sheets of the widgets, not acceptance frames (those are packaged -Bench runs of the "Frames" step).
// Trace: 'UMGALLERY world board=<b> state=<k>:<name> ...' + the SHOT lines of the zone badges.
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "UmWorldGallery.generated.h"

class UCanvasPanel;
class UImage;
class UTextBlock;
class UTexture2D;
class US08ArtTagWidget;
class US08ArtPlateWidget;
class UUmZoneBadges;
class US08ArtDamageWidget;

namespace UmWorldGallery {
// VS-6 F2 (FX-22, IC-49): + 10 damage-medusa «−2» at 300 ms, 11 heal-arthur «+5» at 250 ms, 12 heal-reduced «+5» with the
// state-heal «+» (reduced motion, 200 ms), 13 damage-stack «−2» then «−1» 300 ms later (the newer 28 su above)
inline constexpr int32 StateCount = 14;
UNMATCHED_API const TCHAR* StateName(int32 State);
}  // namespace UmWorldGallery

UCLASS()
class UNMATCHED_API UUmWorldGalleryWidget : public UUserWidget {
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
  UPROPERTY() TArray<TObjectPtr<US08ArtTagWidget>> Tags;
  UPROPERTY() TObjectPtr<US08ArtPlateWidget> Plate;
  UPROPERTY() TObjectPtr<UUmZoneBadges> Zones;
  UPROPERTY() TObjectPtr<US08ArtDamageWidget> Damage;
  double FakeNowS = 100.0;
  UPROPERTY() TObjectPtr<UTexture2D> BackgroundTexture;
  FString BoardNow;
  FVector2D CanvasPx = FVector2D(1920.0, 1080.0);
  float PxNow = 1.0f;
  int32 StateNow = -1;
};
