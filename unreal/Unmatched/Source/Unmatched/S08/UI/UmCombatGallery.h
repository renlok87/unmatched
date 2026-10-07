// VS-3 HB-30...HB-33 / SC-01 review sheets in the backend-less icon gallery (-S08IconGallery, review tooling only, never
// a match), the way of the HB-24 / HB-28 sheets (ВР-VS3-47):
//   -S08IconGalleryCombat=marmoreal|sarpedon   the real combat blocks (FUmCombatBlocks: two UUmHudCombatEdge and the
//       UUmHudCombatCenter in a UUmGameHud on the GAME layout of the window, FIELD of the live K1 camera) over the bench K1
//       frame of the board as a picture (Marmoreal original with the painted backdrop -ConceptPaste, Sarpedon original
//       lit3d - the HB-29 backgrounds, ВР-VS2-HB29-01), fed through FUmCombatBlocks::Refresh by the HB-29 state matrix
//       (ВР-VS2-HB29-03): the owner of the HUD on the left - Marmoreal Medusa's player, Sarpedon King Arthur's player;
//       combat A (Merlin, Swift Strike 3 -> Medusa, Feint 2; 3 : 2; Feint cancels Swift Strike), B (Merlin, Momentous
//       Shift 3 -> Medusa, Dash 3; 3 : 3), C (Medusa -> King Arthur without defense: Marmoreal Snipe 3, Sarpedon
//       Regroup 1). The effect lines are the HB-29 test set (facts.json: «Уловка» / «Рывок» / «Крылатое буйство» /
//       «Передышка» from i18n.ru, Swift Strike / Momentous Shift EN - no RU in the data) - the live game prints the
//       backend's texts (EN today, ВР-VS3-53). One state per second of the gallery clock:
//         0 declare  1 defense-window  2 timer-warning (Marmoreal; Sarpedon skips to 3)  3 defense-chosen  4 reveal
//         5 effects  6 slam  7 hit  8 effects-long  9 holds  10 nodefense
//   -S08IconGalleryConfirm=marmoreal|sarpedon   the SC-01 sample modal: UUmConfirmDialog «Покинуть партию» / «Партия
//       прервётся для обоих игроков» (screens.pause.leave / .leave.confirm) over the same frame under panel.veil 0.6.
// These are sheets of the widgets, not acceptance frames (those are packaged -Bench runs of the "Frames" step).
// Trace: 'UMGALLERY combat board=<b> state=<k>:<name> ...' + the blocks' SHOT lines.
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../../S09/S09CombatStage.h"
#include "../S08CueDispatcher.h"
#include "UmHudCombatBlocks.h"
#include "UmHudLayout.h"
#include "UmCombatGallery.generated.h"

class UCanvasPanel;
class UImage;
class UTextBlock;
class UTexture2D;
class UUmConfirmDialog;
class UUmGameHud;

namespace UmCombatGallery {
inline constexpr int32 StateCount = 11;
UNMATCHED_API const TCHAR* StateName(int32 State);
}  // namespace UmCombatGallery

UCLASS()
class UNMATCHED_API UUmCombatGalleryWidget : public UUserWidget {
  GENERATED_BODY()

 public:
  virtual bool Initialize() override;
  /** bConfirm: the SC-01 modal sheet instead of the combat states. */
  TArray<FString> Build(const FString& Board, const FVector2D& CanvasSu, float PxPerSu, bool bConfirm);
  TArray<FString> SetClockMs(float TMs);

 private:
  struct FCombat {
    TUniquePtr<FS08CueDispatcher> Cues;
    TUniquePtr<FS09CombatStage> Stage;
    int64 StartMs = 0;
  };
  void StartCombat(FCombat& Run, const FS09CombatStageInput& In, int64 StartMs);
  FUmCombatInput BaseInput(bool bAttackerA) const;
  void ApplyState(int32 State, float TMs, TArray<FString>& Lines);
  UPROPERTY() TObjectPtr<UCanvasPanel> Root;
  UPROPERTY() TObjectPtr<UImage> Background;
  UPROPERTY() TObjectPtr<UTextBlock> Label;
  UPROPERTY() TObjectPtr<UUmGameHud> Game;
  UPROPERTY() TObjectPtr<UUmConfirmDialog> Dialog;
  UPROPERTY() TObjectPtr<UTexture2D> BackgroundTexture;
  FString BoardNow;
  bool bConfirmSheet = false;
  FUmHudLayout Layout;
  FUmCombatBlocks Blocks;
  int32 StateNow = -1;
  FCombat A;
  FCombat B;
  FCombat C;
  TMap<FString, FS09CardView> Cards;
  TMap<FString, TPair<FString, FString>> Effects;  // facts.json effects: key -> (title, effect)
};
