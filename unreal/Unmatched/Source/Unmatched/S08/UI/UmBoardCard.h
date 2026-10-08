// VS-7 SC-15 (docs/game-design/visual/06-tasks/screens.csv SC-15; 04-hud-spec.md §1.4 «Доска», ВР-H11; the accepted
// CX-30 mockup art/imagegen/sc15-room-board-codex; ВР-VS4-SC14-10, ВР-VS4-SC15-01): one board card of the ROOM board
// block - UUmBoardCard (two of them in UUmScreenRoom: Marmoreal original left, Sarpedon original right; code tree).
//
//   card      240x136 su (the 720p column 240x124): the Chip body, the whole map illustration on top (the LOBBY tile
//             thumbnails /Game/S08/UI/Boards/T_BoardThumb_*, LAN only, aspect kept, nothing printed over it) and the
//             boardList name under it (type.body).
//   room      the room's board: the 3 su state.pending edge and the check chip (check.on body + the IC-57 ui-check glyph
//             24 su) in the top-right corner, never over the illustration.
//   locked    the other card: the illustration at opacity 0.4, the name text.secondary, the tooltip why.room.board.locked
//             «Доску выбирают при создании комнаты» - no press, no hover: the server has no board change in a room (ВР-H11).
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "UmBoardCard.generated.h"

class UBorder;
class UCanvasPanel;
class UImage;
class UTextBlock;
class UTexture2D;
class US08AnimatedIconWidget;

UCLASS()
class UNMATCHED_API UUmBoardCard : public UUserWidget {
  GENERATED_BODY()

 public:
  virtual bool Initialize() override;
  void Setup(const FString& InBoardId, const FString& InName);
  void Apply(const FVector2D& InSizeSu, bool bInRoomBoard);
  const FString& GetBoardId() const { return BoardId; }
  bool IsRoomBoard() const { return bRoom; }
  bool HasThumb() const { return ThumbTexture != nullptr; }
  FString GetNameText() const;
  bool IsCheckShown() const;

  UPROPERTY() TObjectPtr<UCanvasPanel> Canvas;
  UPROPERTY() TObjectPtr<UBorder> Body;
  UPROPERTY() TObjectPtr<UImage> Thumb;
  UPROPERTY() TObjectPtr<UTextBlock> NameText;
  UPROPERTY() TObjectPtr<UBorder> Edge;
  UPROPERTY() TObjectPtr<UBorder> CheckChip;
  UPROPERTY() TObjectPtr<US08AnimatedIconWidget> CheckIcon;
  UPROPERTY() TObjectPtr<UTexture2D> ThumbTexture;

 private:
  FString BoardId;
  FVector2D SizeSu = FVector2D(240.0, 136.0);
  bool bRoom = false;
};
