// VS-7 SC-08 (docs/game-design/visual/06-tasks/screens.csv SC-08; 04-hud-spec.md §1.3, §6.1; the accepted CX-29 mockup
// art/imagegen/sc08-lobby-list-codex and ВР-VS4-SC08-01...17): one open room of the LOBBY list - UUmLobbyGameRow
// (pooled by UUmScreenLobby; code tree, no WBP of its own; a poll never recreates rows, ВР-H20 budget).
//
//   row      56 su on the panel.inset skin (hover: panel.bg.hover); left to right Code (type.heading, text.primary),
//            Mode («1×1», type.body), Board (the Board row's name, type.body), Seats «n/2» (type.body), HeroDiscs (a
//            32 su LOBBY disc of every player with a hero, CP-07 variant B, no team ring, ВР-VS4-SC08-11), JoinButton
//            (normal, 40 su, «Войти», right, 8 su in). One fixed x per column for the whole list (UUmScreenLobby lays the
//            columns out over the widest text of each; codes and board names are never cut, type never shrinks).
//   unavail  a joinGame refused for the row (ВР-VS4-SC08-02 / -03): code, mode, board in text.secondary, the seats slot
//            empty, the disc stays, no button - its slot holds the why text (why.room.full «Комната заполнена» /
//            why.room.started «Игра уже началась», type.body text.secondary, right-aligned) and the same text is the
//            row's tooltip; the next poll drops the row.
//   press    JoinButton through the screen's arbiter (id screens.lobby.row.join.<n>).
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../../S09/S09HudPress.h"
#include "UmLobbyGameRow.generated.h"

class UBorder;
class UCanvasPanel;
class UHorizontalBox;
class UTextBlock;
class UUmButton;

/** What one row shows (texts already resolved: the board name from boardList, the hero slugs for the discs). */
struct UNMATCHED_API FUmLobbyRowModel {
  FString GameId;
  FString Code;
  FText Mode;
  FString Board;
  int32 Seats = 1;
  int32 MaxSeats = 2;
  TArray<FName> HeroKeys;    // portrait keys (UmPortrait::SlugOf of the hero name)
  TArray<FString> HeroNames; // the monogram fallback
  FName Why;                 // why.room.full / why.room.started after a refused join; NAME_None = available
  bool operator==(const FUmLobbyRowModel& O) const {
    return GameId == O.GameId && Code == O.Code && Mode.EqualTo(O.Mode) && Board == O.Board && Seats == O.Seats &&
           MaxSeats == O.MaxSeats && HeroKeys == O.HeroKeys && Why == O.Why;
  }
  bool operator!=(const FUmLobbyRowModel& O) const { return !(*this == O); }
};

/** One fixed x per column (su, row-local), the same for every row of the list. */
struct UNMATCHED_API FUmLobbyColumns {
  float CodeX = 16.0f;
  float ModeX = 0.0f;
  float BoardX = 0.0f;
  float SeatsX = 0.0f;
  float DiscsX = 0.0f;
  float JoinX = 0.0f;
  float JoinW = 150.0f;
};

namespace UmLobbyRow {
inline constexpr float HeightSu = 56.0f;
inline constexpr float GapSu = 8.0f;
inline constexpr float PadSu = 16.0f;       // the code starts 16 su in (ВР-VS4-SC08-14)
inline constexpr float EndPadSu = 8.0f;     // the button / the why text end 8 su before the right edge
inline constexpr float JoinHSu = 40.0f;
inline constexpr float JoinMinWSu = 120.0f;
inline constexpr float DiscSu = 32.0f;
inline constexpr float DiscGapSu = 4.0f;
/** ВР-VS4-SC08-04 (the mockup's measured layout): the free width between the code and the button is split into five
 *  equal gaps around mode, board, seats and the discs (widths = the widest text of each column). */
UNMATCHED_API FUmLobbyColumns Columns(float RowW, float CodeW, float ModeW, float BoardW, float SeatsW, float DiscsW, float JoinW);
/** «n/2». */
UNMATCHED_API FString SeatsText(int32 Seats, int32 MaxSeats);
}  // namespace UmLobbyRow

UCLASS()
class UNMATCHED_API UUmLobbyGameRow : public UUserWidget {
  GENERATED_BODY()

 public:
  virtual bool Initialize() override;
  /** Text and discs (a disc is rebuilt only when the row's heroes change). */
  void ApplyModel(const FUmLobbyRowModel& InModel, float PxPerSu);
  void ApplyColumns(const FUmLobbyColumns& Columns, float RowW);
  void SetPress(FName Id, const TSharedPtr<FS09HudPressArbiter>& Arbiter, const FS09OnHudPressOutcome& OnOutcome);
  const FUmLobbyRowModel& GetModel() const { return Model; }
  bool IsAvailable() const { return Model.Why.IsNone(); }
  bool IsHovered() const { return bHover; }
  int32 GetDiscCount() const;
  /** Tests: the hover look without a pointer. */
  void SimulateHover(bool bIn);

  UPROPERTY() TObjectPtr<UBorder> Cell;
  UPROPERTY() TObjectPtr<UCanvasPanel> Canvas;
  UPROPERTY() TObjectPtr<UTextBlock> Code;
  UPROPERTY() TObjectPtr<UTextBlock> Mode;
  UPROPERTY() TObjectPtr<UTextBlock> Board;
  UPROPERTY() TObjectPtr<UTextBlock> Seats;
  UPROPERTY() TObjectPtr<UHorizontalBox> HeroDiscs;
  UPROPERTY() TObjectPtr<UUmButton> JoinButton;
  UPROPERTY() TObjectPtr<UTextBlock> WhyText;
  UPROPERTY() TArray<TObjectPtr<UObject>> KeepAlive;

 protected:
  virtual void NativeOnMouseEnter(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
  virtual void NativeOnMouseLeave(const FPointerEvent& InMouseEvent) override;

 private:
  void Restyle();
  FUmLobbyRowModel Model;
  TArray<FName> DiscKeys;
  bool bHover = false;
  bool bHasModel = false;
};
