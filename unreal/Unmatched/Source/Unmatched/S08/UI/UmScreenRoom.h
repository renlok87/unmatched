// VS-7 SC-14...SC-18 (docs/game-design/visual/06-tasks/screens.csv SC-14...SC-18; 04-hud-spec.md §1.4, §3.1, §6.1;
// ВР-38, ВР-H11, ВР-H12; the accepted CX-30 mockups art/imagegen/sc14-room-hero-codex ... sc18-room-countdown-codex and
// their decisions ВР-VS4-SC14-01...16, ВР-VS4-SC15-01, ВР-VS4-SC16-01, ВР-VS4-SC17-01...03, ВР-VS4-SC18-01 / -02): ROOM -
// UUmScreenRoom (/Game/S08/UI/Screens/WBP_UI_SCR_ROOM) in the root's Screens over the menu backdrop (SC-02). A full
// screen: the panels stand on the veil, the base frame draws nothing.
//
//   layout   class L: the 04 §1.4 table (1080p and the 720p column): Header (24, 24, W-48, 64) panel 0.92; slots 560x200
//            (720p 500) from y 112 with 16 su gap; the hero grid (608 | 548, 112, .., 560 | 480); the board block
//            (.., 688 | 608, .., 160 | 140); the deck row (.., 864 | 764, .., 80 | 68); the bottom strip (24, H-112, W-48, 88).
//            Class S (ВР-VS4-SC14-11): margins 16, the left column 300 su (two 136 su slots, the deck row), the right area
//            with two 360x240 compact hero cards and the board block, the bottom strip (16, H-96, W-32, 80).
//   SC-14    Header: TitleText «Комната · код <код>», CopyButton «Копировать» (the code to the clipboard - never traced),
//            ModeLabel «Режим» + ModeText «1×1» / «Против ИИ», MenuButton «≡» (ui-menu). HeroGrid (UScrollBox > UniformGrid):
//            a pool of UUmHeroCard, 4 columns (as many as fit), the MVP roster heroes of heroList (ВР-02, ВР-H12).
//   SC-15    BoardBlock: BoardTitle «Доска», two UUmBoardCard (the room's board marked; the other locked with
//            why.room.board.locked, shown next to the cards and as the tooltip) - never a board change on the client.
//   SC-16    DeckRow: DeckCount «Колода: 30 карт» (the sum of the hero's catalogue copies, RU plural) and DeckButton «Просмотр
//            колоды» (opens the INSPECT deck mode of the picked hero; without a hero disabled with why.room.no.hero).
//   SC-17    two UUmRoomSlot; BottomStrip: LeaveButton «Выйти из комнаты» (normal; through the confirm dialog),
//            StatusText «Ждём готовности соперника…» / «Все готовы», ReadyButton (the toggle «Готов»; IC-57 ui-check on it
//            when on; the guest's primary, normal for the host), StartButton «Начать партию» (the host's primary; disabled
//            with why.room.no.hero / why.room.not.ready), WhyText under the buttons. VS_AI: slot 2 «ИИ-соперник · AI Bot»,
//            «Начать» after the own ready. One primary per window (a toggle that is on is never primary).
//   SC-18    Countdown: CountVeil (card.navy 0.8 over the whole canvas), CountPanel (panel.bg 1.0) > CountText: the host's
//            3-2-1 (type.display, 1000 ms each, reduced - only the digit changes) then «Партия начинается…» (type.title);
//            the guest only the latter. The input under it is closed (the veil takes the pointer).
//   gate     'SHOT widget id=UI-SCR-ROOM impl=umg state=<waiting|picked|ready|countdown> ... host=0|1 mode=<1v1|ai>
//            hero=0|1 ready=0|1 opp=<none|joined|hero|ready> primary=<start|ready|none> busy=0|1' and two block lines
//            'state=board board=<marmoreal|sarpedon>' and 'state=deck deck=<n> deckButton=0|1' - never a code or a name.
//   rollback -S08SlateHud=room: the legacy Slate room panel, this is not built.
#pragma once

#include "CoreMinimal.h"
#include "../../S09/S09HudPress.h"
#include "UmHeroCard.h"
#include "UmLobbyGameRow.h"
#include "UmRoomSlot.h"
#include "UmScreenBase.h"
#include "UmScreenLobby.h"
#include "UmScreenRoom.generated.h"

class UBorder;
class UCanvasPanel;
class UImage;
class UScrollBox;
class USizeBox;
class UTextBlock;
class UUniformGridPanel;
class UUmBoardCard;
class UUmButton;

enum class EUmRoomPhase : uint8 { Room, Countdown, Starting };

/** The seven rectangles of the screen for a canvas and its class (04 §1.4, ВР-VS4-SC14-11). */
struct UNMATCHED_API FUmRoomLayout {
  bool bClassS = false;
  FUmRectSu Header, Slot0, Slot1, Grid, Board, Deck, Bottom;
  FVector2D CardSu = FVector2D(300.0, 420.0);
  int32 Columns = 4;
};

/** What the ROOM shows (the owner builds it from FS08RoomState, heroList and the hero details). */
struct UNMATCHED_API FUmRoomModel {
  FString Code;
  bool bVsAi = false;
  bool bHost = false;
  FString BoardId;
  FString BoardNames[2];
  FUmRoomSlotModel Slots[2];
  TArray<FUmHeroCardModel> Heroes;
  FString OwnHeroId;
  bool bOwnReady = false;
  /** The opponent seat: none (waiting), joined, with a hero, ready; VS_AI: the bot counts as ready (ВР-VS4-SC17-01). */
  bool bOppPresent = false;
  bool bOppHero = false;
  bool bOppReady = false;
  /** The picked hero's deck: the sum of copies (-1 = not known yet). */
  int32 DeckCount = -1;
  /** A room mutation of this screen waits for its answer (why.syncing on the controls). */
  bool bBusy = false;
};

namespace UmRoom {
inline constexpr double CountStepMs = 1000.0;  // SC-18: 3-2-1 by 1000 ms
inline constexpr double StartingHoldMs = 1000.0;  // ВР-VS7-30: «Партия начинается…» before the loading screen
inline constexpr float CountVeilAlpha = 0.8f;
UNMATCHED_API FUmRoomLayout Layout(const FVector2D& CanvasSu, bool bClassS);
/** The gate state: countdown > ready (both seats ready / VS_AI: the own ready) > picked (an own hero) > waiting. */
UNMATCHED_API const TCHAR* StateName(EUmRoomPhase Phase, const FUmRoomModel& M);
/** Why «Начать партию» is disabled (NAME_None = enabled): why.room.no.hero, then why.room.not.ready. */
UNMATCHED_API FName StartWhy(const FUmRoomModel& M);
/** Why «Готов» is disabled: why.room.no.hero without an own hero. */
UNMATCHED_API FName ReadyWhy(const FUmRoomModel& M);
/** The digit of the countdown at ElapsedMs since the start (3, 2, 1; 0 once it ran out). */
UNMATCHED_API int32 CountDigit(double ElapsedMs);
}  // namespace UmRoom

UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmScreenRoom : public UUmScreenBase {
  GENERATED_BODY()

 public:
  static const TCHAR* const WidgetBlueprintPath;  // /Game/S08/UI/Screens/WBP_UI_SCR_ROOM
  static UClass* WidgetClass();

  virtual bool Initialize() override;
  /** The base tree + Content (Canvas) > Header, BoardBlock, DeckRow, BottomStrip (UBorder panels), the texts, the buttons,
   *  Slot0 / Slot1 (UUmRoomSlot), HeroScroll > HeroGrid, BoardCards (Canvas), CountVeil, CountPanel > CountText. */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  bool HasAllParts(FString* OutMissing = nullptr) const;
  void ApplyCanvas(const FVector2D& InCanvasSu, bool bInClassS, float InPxPerSu);

  struct FInput {
    TFunction<void(const FString& HeroId)> OnPick;
    TFunction<void()> OnReady;
    TFunction<void()> OnStart;
    TFunction<void()> OnLeave;  // «Выйти из комнаты»: the owner asks the confirm dialog
    TFunction<void()> OnDeck;
    TFunction<void()> OnCopy;
    TFunction<void()> OnMenu;
    TFunction<void(FName BankId)> OnSound;
  };
  void SetInput(const TSharedPtr<FS09HudPressArbiter>& InArbiter, FInput InInput);

  void ApplyModel(const FUmRoomModel& InModel);
  /** SC-18: the room phase - Countdown with its digit (3, 2, 1), Starting («Партия начинается…»), Room. */
  void SetPhase(EUmRoomPhase InPhase, int32 Digit = 0);

  // ---- what the screen shows (tests, the gate, the evidence drive) ----
  const FUmRoomModel& GetModel() const { return Model; }
  EUmRoomPhase GetPhase() const { return Phase; }
  int32 GetDigit() const { return Digit; }
  int32 GetHeroCount() const { return Model.Heroes.Num(); }
  UUmHeroCard* GetHeroCard(int32 Index) const;
  UUmRoomSlot* GetSlot(int32 Index) const;
  UUmBoardCard* GetBoardCard(int32 Index) const;
  bool IsStartShown() const;
  bool IsStartEnabled() const;
  bool IsStartPrimary() const;
  bool IsReadyEnabled() const;
  bool IsReadyPrimary() const;
  bool IsReadyOn() const;
  bool IsDeckEnabled() const;
  int32 PrimaryCount() const;
  FString GetTitleText() const;
  FString GetStatusText() const;
  FString GetWhyText() const;
  FString GetDeckText() const;
  FString GetDeckWhyText() const;
  FString GetBoardWhyText() const;
  FString GetCountText() const;
  bool IsCountShown() const;
  /** Press a control as a click does (the evidence drive, tests): screens.room.* ids. */
  void SimulatePress(FName Id);
  virtual void CollectShotLines(TArray<FString>& Out) const override;
  virtual FString ShotExtra() const override;
  /** The PORTRAIT lines of the shown cards and slots (show=room / slot), once per build. */
  void CollectPortraitLines(TArray<FString>& Out) const;

  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UBorder> Header;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> TitleText;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> CopyButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> ModeLabel;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> ModeText;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> MenuButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmRoomSlot> Slot0;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmRoomSlot> Slot1;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UScrollBox> HeroScroll;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUniformGridPanel> HeroGrid;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UBorder> BoardBlock;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> BoardTitle;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UCanvasPanel> BoardCards;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> BoardWhy;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UBorder> DeckRow;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> DeckCount;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> DeckButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> DeckWhy;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UBorder> BottomStrip;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> LeaveButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> StatusText;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> ReadyButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> StartButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> WhyText;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UImage> CountVeil;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UBorder> CountPanel;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> CountText;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UCanvasPanel> Content;

  UPROPERTY() TArray<TObjectPtr<UUmHeroCard>> CardPool;
  UPROPERTY() TArray<TObjectPtr<USizeBox>> CardBoxes;
  UPROPERTY() TArray<TObjectPtr<UUmBoardCard>> Boards;

 protected:
  virtual void BuildContent() override;

 private:
  static bool AttachContent(UWidgetTree& Tree, UPanelWidget* Parent, FS08AttachWidget Attach, FString* OutError);
  void BindParts();
  void BuildBoards();
  void SyncCards();
  void Layout();
  void Refresh();
  void OnPressOutcome(FName Id, const FS09HudPressOutcome& Outcome);
  void BindCardPress(UUmHeroCard* Card, int32 Index);
  void Sound(const TCHAR* Bank) const;
  FBox2D BlockRectPx(const FUmRectSu& R) const;

  FUmRoomModel Model;
  EUmRoomPhase Phase = EUmRoomPhase::Room;
  int32 Digit = 0;
  TSharedPtr<FS09HudPressArbiter> Arbiter;
  FInput Input;
};
