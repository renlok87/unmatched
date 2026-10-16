// SEL (docs/game-design/select-screens/02-DESIGN.md §3, §4): one tile of the select screens' strips - a hero portrait
// of the roster strip or a board thumbnail of the board strip, or the «?» of a random pick. A marble-and-bronze plate
// (hud.table.card) with the image, a caption band, a corner badge of the side that picked it (P1 gold / P2 silver-blue)
// and a frame that lights in the viewer's team colour on hover; it rises 6 su on hover.
//
//   states   Normal, Hover (the pointer is over it), Picked (the viewer's pick: the badge of its side), Taken (the other
//            side's pick: dimmed 50 %, not clickable - GD-016 no duplicates), Disabled (a request in flight).
//   input    the native mouse: enter / leave -> OnHover(true / false), a left click -> OnClick (Normal / Picked only).
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../S08Team.h"
#include "UmSelectTile.generated.h"

class UBorder;
class UCanvasPanel;
class UImage;
class UTextBlock;
class UTexture2D;

enum class EUmTileState : uint8 { Normal, Picked, Taken, Disabled };

struct UNMATCHED_API FUmSelectTileModel {
  FString Id;            // hero id / board id / "random"
  FString Label;         // the caption (DB name)
  UTexture2D* Image = nullptr;  // null = the «?» glyph (random, no portrait)
  /** The UV rectangle of the image to show (portraits sit padded in their texture: the face crop of the registry). */
  FBox2f Region = FBox2f(FVector2f(0.0f, 0.0f), FVector2f(1.0f, 1.0f));
  EUmTileState State = EUmTileState::Normal;
  /** The badge: none, or the side whose pick it is (its team colour and «1» / «2»). */
  bool bBadge = false;
  ES08TeamSlot BadgeLook = ES08TeamSlot::P1;
  int32 BadgeDigit = 1;
  /** The selected frame (the room board, the hero shown in the viewer's niche). */
  bool bSelected = false;
};

UCLASS()
class UNMATCHED_API UUmSelectTile : public UUserWidget {
  GENERATED_BODY()

 public:
  virtual bool Initialize() override;
  void Apply(const FUmSelectTileModel& InModel, const FVector2D& InSizeSu, ES08TeamSlot InViewerLook);
  const FUmSelectTileModel& GetModel() const { return Model; }
  bool IsHovered() const { return bHover; }
  bool IsClickable() const { return Model.State == EUmTileState::Normal || Model.State == EUmTileState::Picked; }

  TFunction<void()> OnClick;
  TFunction<void(bool bOn)> OnHover;

  UPROPERTY() TObjectPtr<UCanvasPanel> Canvas;
  UPROPERTY() TObjectPtr<UBorder> Plate;
  UPROPERTY() TObjectPtr<UImage> Picture;
  UPROPERTY() TObjectPtr<UTextBlock> Glyph;
  UPROPERTY() TObjectPtr<UBorder> Band;
  UPROPERTY() TObjectPtr<UTextBlock> Caption;
  UPROPERTY() TObjectPtr<UBorder> Frame;
  UPROPERTY() TObjectPtr<UBorder> Badge;
  UPROPERTY() TObjectPtr<UTextBlock> BadgeText;

 protected:
  virtual void NativeOnMouseEnter(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
  virtual void NativeOnMouseLeave(const FPointerEvent& InMouseEvent) override;
  virtual FReply NativeOnMouseButtonDown(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
  virtual FReply NativeOnMouseButtonUp(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;

 private:
  void Layout();

  FUmSelectTileModel Model;
  FVector2D SizeSu = FVector2D(128.0, 168.0);
  ES08TeamSlot ViewerLook = ES08TeamSlot::P1;
  bool bHover = false;
  bool bDown = false;
};
