// VS-7 SC-09 (docs/game-design/visual/06-tasks/screens.csv SC-09; 04-hud-spec.md §1.3; ВР-VS4-SC08-08, ВР-VS4-SC09-01 / -02;
// AGENTS.md «Board scenes and heroes»): one board tile of the LOBBY Create column - UUmBoardChip (two of them, pooled
// by UUmScreenLobby; code tree, no WBP of its own).
//
//   tile     a UUmButton body (Chip look at rest = Btn_Normal; selected = Btn_Selected, state.pending) under the whole map
//            illustration (aspect kept, no crop, nothing printed over it, 8 su inset) and the board name under it
//            (type.body; text.primary, card.glyph on the selected tile) - the name always shows, never the picture alone.
//   texture  /Game/S08/UI/Boards/T_BoardThumb_<marmoreal|sarpedon> (LAN only, out of git like the portraits, ВР-48;
//            tools/s08/screens/ue_import_board_thumbs.py); missing -> the name alone and one 'BOARDTHUMB missing=' log.
//   press    through the screen's FS09HudPressArbiter (id screens.lobby.board.<n>), like every UUmButton.
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../../S09/S09HudPress.h"
#include "UmBoardChip.generated.h"

class UImage;
class UOverlay;
class UTextBlock;
class UTexture2D;
class UUmButton;

namespace UmBoardChip {
inline constexpr float InsetSu = 8.0f;
inline constexpr float NameRowSu = 28.0f;
/** The thumbnail of a real board (its slug: marmoreal / sarpedon); empty for any other id. */
UNMATCHED_API FString ThumbPath(const FString& BoardId);
/** The image rectangle (su, tile-local) of a WxH source inside a tile, aspect kept, centred in the area above the name. */
UNMATCHED_API FBox2D ImageRect(const FVector2D& TileSu, const FVector2D& SrcPx);
}  // namespace UmBoardChip

UCLASS()
class UNMATCHED_API UUmBoardChip : public UUserWidget {
  GENERATED_BODY()

 public:
  virtual bool Initialize() override;
  void Setup(const FString& InBoardId, const FText& InName);
  void SetPress(FName Id, const TSharedPtr<FS09HudPressArbiter>& Arbiter, const FS09OnHudPressOutcome& OnOutcome);
  /** The tile size (su) and its state. */
  void Apply(const FVector2D& InSizeSu, bool bInSelected, bool bInFocused, bool bInEnabled);
  const FString& GetBoardId() const { return BoardId; }
  FString GetNameText() const;
  bool IsSelected() const { return bSelected; }
  bool HasThumb() const;

  UPROPERTY() TObjectPtr<UUmButton> Button;
  UPROPERTY() TObjectPtr<UImage> Thumb;
  UPROPERTY() TObjectPtr<UTextBlock> NameText;
  UPROPERTY() TObjectPtr<UTexture2D> ThumbTexture;

 private:
  FString BoardId;
  FVector2D SizeSu = FVector2D(312.0, 232.0);
  bool bSelected = false;
};
