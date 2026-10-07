// VS-3 HB-27 / HB-28 / HB-47 review sheet in the backend-less icon gallery (-S08IconGallery, review tooling only, never a
// match): -S08IconGalleryDecks=marmoreal|sarpedon puts the real UUmHudDecks and UUmHudDeckPanel (theme, card widgets,
// registry backs and scans) on the GAME layout of the window (FUmHudLayout with the live K1 FIELD of that board, as the
// hand sheet UmHandGallery.h), over the bench K1 frame of the board as a picture (Marmoreal original with the painted
// backdrop -ConceptPaste, Sarpedon original lit3d - the HB-26 backgrounds, ВР-VS2-HB26-01).
// The match moment is the HB-26 one (ВР-VS2-HB26-02, run I): Marmoreal - own Medusa deck 23 / discard 2 (A Momentary
// Glance, Feint on top) / hand 5 (Gaze of Stone x2, Snipe, Clutching Claws, Dash), the opponent King Arthur 24 / 1 (Swift
// Strike) / 5, stale ≈24; Sarpedon - own King Arthur 25 / 2 (Momentous Shift, Swift Strike on top) / 3 (Noble Sacrifice,
// Swift Strike, The Holy Grail), the opponent Medusa 22 / 2 (Dash, Regroup) / 6, stale ≈25. The deck lists are the S01
// capture of the content API (docs/game-design/evidence/S01/content-<hero>.json: names and nameRu as in the backend).
// One state per second of the gallery clock (-S08IconGalleryTimes=600,1600,...):
//   0 chips  1 chips-stale  2 own  3 own-end  4 own-discard  5 opp  6 opp-end  7 loading (the skeleton from +300 ms)
//   8 failed  9 empty-discard (the resource-card icon)  10 own-fan9 (a 9-card hand fan under the panel, ВР-VS3-37)
// It is a sheet of the widgets, not an acceptance frame (those are packaged -Bench runs of the "Frames" step).
// Trace: 'UMGALLERY decks board=<b> state=<k>:<name> ...' + the blocks' SHOT lines + HUD-LOADER.
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../../S09/S09DeckPanel.h"
#include "UmHudLayout.h"
#include "UmDecksGallery.generated.h"

class UCanvasPanel;
class UImage;
class UTextBlock;
class UTexture2D;
class UUmHudDecks;
class UUmHudDeckPanel;
class UUmHudHand;

namespace UmDecksGallery {
inline constexpr int32 StateCount = 11;
UNMATCHED_API const TCHAR* StateName(int32 State);
/** The deck list of a hero from the S01 content capture (cardId = the content id, -1 for a missing printed value). */
UNMATCHED_API FS09DeckList LoadList(const FString& HeroSlug, const FString& PlayerId);
}  // namespace UmDecksGallery

UCLASS()
class UNMATCHED_API UUmDecksGalleryWidget : public UUserWidget {
  GENERATED_BODY()

 public:
  virtual bool Initialize() override;
  TArray<FString> Build(const FString& Board, const FVector2D& CanvasSu, float PxPerSu);
  /** State = floor(TMs / 1000); the loader clock runs from the start of that second. */
  TArray<FString> SetClockMs(float TMs);
  UUmHudDecks* GetDecks() const { return Decks; }
  UUmHudDeckPanel* GetPanel() const { return Panel; }

 private:
  struct FSide {
    FString Hero;
    FString Slug;
    FS09PlayerPanel Panel;
    FS09DeckList List;
  };
  void ApplyState(int32 State, double TMs);
  UPROPERTY() TObjectPtr<UCanvasPanel> Root;
  UPROPERTY() TObjectPtr<UImage> Background;
  UPROPERTY() TObjectPtr<UTextBlock> Label;
  UPROPERTY() TObjectPtr<UUmHudDecks> Decks;
  UPROPERTY() TObjectPtr<UUmHudDeckPanel> Panel;
  UPROPERTY() TObjectPtr<UUmHudHand> Hand;
  UPROPERTY() TObjectPtr<UTexture2D> BackgroundTexture;
  FString BoardNow;
  FUmHudLayout Layout;
  int32 StateNow = -1;
  FSide Own;
  FSide Opp;
};
