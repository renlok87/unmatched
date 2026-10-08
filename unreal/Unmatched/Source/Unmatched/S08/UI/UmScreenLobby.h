// VS-7 SC-08...SC-13 (docs/game-design/visual/06-tasks/screens.csv SC-08...SC-13; 04-hud-spec.md §1.3, §3.1, §3.3, §6.1;
// ВР-H11, ВР-H20; the accepted CX-29 mockups art/imagegen/sc08-lobby-list-codex ... sc13-lobby-error-codex and their
// decisions ВР-VS4-SC08-01...17, ВР-VS4-SC09-01...03, ВР-VS4-SC10-01, ВР-VS4-SC11-01...05, ВР-VS4-SC12-01 / -02,
// ВР-VS4-SC13-01): LOBBY - UUmScreenLobby (/Game/S08/UI/Screens/WBP_UI_SCR_LOBBY) in the root's Screens over the menu
// backdrop (SC-02). A full screen: the panels stand on the veil, the base frame draws nothing.
//
//   layout   class L (04 §1.3 table): Header (24, 24, W-48, 64) panel 0.92; GameList (24, 112, ..., H-136); the right
//            column 672 su (568 at the 720p canvas): Create (.., 112, .., 520 | 500), Code (.., 648 | 628, .., 200), all
//            three panel.bg 1.0 (the modal skin). Class S (ВР-VS4-SC08-09): margins 16, header (16, 16, W-32, 64), the
//            right column 456 su from y 96 (Create 312 high, Code down to H-16), the Create title and the mode row on
//            one line, thumbnails 136 su high, cells 48 su, the code «Войти» under the cells.
//   SC-08    Header: NicknameText (the login's username), MenuButton «≡» (ui-menu 24 su), LangRu / LangEn (UmText UI
//            language, as LOGIN). GameList: ListTitle «Список игр», RefreshButton «Обновить» (text: no v3 glyph ⟳,
//            ВР-VS4-SC08-05), Skeleton (HB-47, 3 rows of 56 su, the 900 ms pulse, after 300 ms of the first wait), Rows
//            (a scroll box of pooled UUmLobbyGameRow - one row per availableGames room, answer order).
//   SC-09    Create: CreateTitle «Создать игру», ModeLabel «Режим», ModeChip1v1 «1×1» / ModeChipAi «Против ИИ» (32 su,
//            selected state.pending), BoardLabel «Доска», BoardChips (2 x UUmBoardChip: Marmoreal original - the default
//            - and Sarpedon original, names from boardList, ВР-VS4-SC09-02), CreateButton «Создать» (the window's one
//            primary unless six code characters are typed, ВР-VS4-SC11-02); busy «Создаём…» with the 32 su spinner,
//            disabled with why.syncing until the answer (a second press sends nothing); CreateError «Сервер недоступен».
//   SC-10    the AI chip: CreateNote «Соперник — ИИ: AI Bot» (backend/prisma/seed-ai.ts:24; no bot hero - the server
//            picks it); createGame(VS_AI, boardId) by the same path.
//   SC-11    Code: CodeTitle «Войти по коду», six cells (CodeCells: input.normal / input.focus skin, the character type.title
//            upper case; an empty cell shows a 24 x 2 su underline - the shape channel, ВР-VS4-SC11-04) over one invisible
//            UEditableTextBox CodeBox that takes the keys (A-Z 0-9 only, upper case, at most six); CodeJoinButton «Войти»
//            disabled with why.code.length below six; CodeError (badge-refuse 24 su + «Игра не найдена» / «Комната
//            заполнена») under the cells - the code is kept; RecoverButton «Вернуться в мою партию» while myGames has
//            the player's live match (L: under the Join button, S: in the header).
//   SC-12    no rows: EmptyIcon state-hint 32 su over EmptyText (text.secondary, two lines at most).
//   SC-13    no answer for 10 s or a failed one: ErrorIcon resource-connection-lost 48 su, ErrorText «Не удалось загрузить
//            список игр», RetryButton «Повторить» (normal; the refresh button hides - one action once, ВР-VS4-SC13-01);
//            the right columns stay usable, the 15 s poll goes on.
//   gate     'SHOT widget id=UI-SCR-LOBBY impl=umg state=<loading|list|empty|error|create|code|code-error> ... list=<..>
//            rows=<n> unavailable=<n> mode=<1v1|ai> board=<marmoreal|sarpedon> busy=0|1 code=<0..6> codeError=<..>
//            recover=0|1 primary=<create|code>' - never a room code, never a name.
//   sound    PlayScreenSound UI-BTN-CLICK (create, join, refresh, retry, menu), UI-TOGGLE (chips, language), UI-REJECT
//            (a code or a list error); room create / join sounds and MUS-MENU play by themselves.
//   rollback -S08SlateHud=lobby: the GD-036 / GD-029 Slate panels, this is not built.
#pragma once

#include "CoreMinimal.h"
#include "../../S09/S09HudPress.h"
#include "UmLobbyGameRow.h"
#include "UmScreenBase.h"
#include "UmScreenLobby.generated.h"

class UBorder;
class UCanvasPanel;
class UEditableTextBox;
class UImage;
class UScrollBox;
class UTextBlock;
class UUmBoardChip;
class UUmButton;
class UUmSkeletonRows;
class UUmSpinner;
class UVerticalBox;
class US08AnimatedIconWidget;

enum class EUmLobbyList : uint8 { Loading, List, Empty, Error };
enum class EUmCodeError : uint8 { None, NotFound, Full };
enum class EUmLobbyMode : uint8 { OneVOne, VsAi };

/** One rectangle in canvas su. */
struct UNMATCHED_API FUmRectSu {
  float X = 0.0f, Y = 0.0f, W = 0.0f, H = 0.0f;
  FVector2D Pos() const { return FVector2D(X, Y); }
  FVector2D Size() const { return FVector2D(W, H); }
};

/** The four panels of the screen for a canvas and its class (04 §1.3, ВР-VS4-SC08-09). */
struct UNMATCHED_API FUmLobbyLayout {
  bool bClassS = false;
  FUmRectSu Header, List, Create, Code;
};

namespace UmLobby {
inline const TCHAR* const MarmorealId = TEXT("c121b47f8d6eb28daccb76d05");  // AGENTS.md: the default board
inline const TCHAR* const SarpedonId = TEXT("c7fa64a26c29a0835f2383e63");
/** The fallback names of the two maps (AGENTS.md) while boardList has not answered. */
inline const TCHAR* const MarmorealName = TEXT("Marmoreal · original map");
inline const TCHAR* const SarpedonName = TEXT("Sarpedon · original map");
/** The AI opponent's username (backend/prisma/seed-ai.ts line 24, ВР-VS4-SC10-01). */
inline const TCHAR* const AiBotName = TEXT("AI Bot");
inline constexpr int32 CodeLength = 6;
inline constexpr double PollMs = 15000.0;     // ВР-H20
inline constexpr double TimeoutMs = 10000.0;  // SC-13: the error not later than 10 s
inline constexpr float RowsTopSu = 72.0f;     // the first row / skeleton row under the list title (list-local)
inline constexpr int32 SkeletonRows = 3;

UNMATCHED_API FUmLobbyLayout Layout(const FVector2D& CanvasSu, bool bClassS);
/** Typed text -> the code: upper case, A-Z and 0-9 only, at most six. */
UNMATCHED_API FString NormalizeCode(const FString& Typed);
/** A refused join by code (NOT_FOUND of the lookup, the joinGame message) -> what the screen says. */
UNMATCHED_API EUmCodeError ClassifyCodeError(const FString& ErrorCode, const FString& Message);
/** A refused join of a list row (the joinGame message, ВР-VS4-SC08-02) -> why.room.full / why.room.started. */
UNMATCHED_API FName RowWhy(const FString& ErrorCode, const FString& Message);
UNMATCHED_API const TCHAR* ListName(EUmLobbyList L);
UNMATCHED_API const TCHAR* CodeErrorName(EUmCodeError E);
/** The gate state: code-error > code (characters typed) > create (a create chip touched / busy) > the list state. */
UNMATCHED_API const TCHAR* StateName(EUmLobbyList List, bool bCreateTouched, int32 CodeChars, EUmCodeError CodeError);

/** ВР-H20: when to ask availableGames - on entry, every 15 s after the last request, at once on «Обновить» /
 *  «Повторить» and when the window gets its focus back; a request without an answer for 10 s is the error. */
struct UNMATCHED_API FUmLobbyPoll {
  double LastSentMs = -1.0;
  double InFlightSinceMs = -1.0;
  bool bHadFocus = true;
  bool bForce = false;
  /** True = send now (the caller sends and calls Sent). */
  bool Due(double NowMs, bool bHasFocus);
  void Sent(double NowMs) {
    LastSentMs = NowMs;
    InFlightSinceMs = NowMs;
    bForce = false;
  }
  void Answered() { InFlightSinceMs = -1.0; }
  bool TimedOut(double NowMs) const { return InFlightSinceMs >= 0.0 && NowMs - InFlightSinceMs >= TimeoutMs; }
  void Reset() { *this = FUmLobbyPoll(); }
};
}  // namespace UmLobby

UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmScreenLobby : public UUmScreenBase {
  GENERATED_BODY()

 public:
  static const TCHAR* const WidgetBlueprintPath;  // /Game/S08/UI/Screens/WBP_UI_SCR_LOBBY
  static UClass* WidgetClass();

  virtual bool Initialize() override;
  /** The base tree + Content (Canvas) > Header, GameList, CreateColumn, CodeColumn (UBorder panels) and their parts
   *  (see the file comment); the board chips and the rows are code-built widgets (UUmBoardChip, UUmLobbyGameRow). */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  bool HasAllParts(FString* OutMissing = nullptr) const;
  void ApplyCanvas(const FVector2D& InCanvasSu, bool bInClassS, float InPxPerSu);

  struct FInput {
    TFunction<void()> OnRefresh;  // «Обновить» / «Повторить»: an out-of-turn availableGames
    TFunction<void(EUmLobbyMode Mode, const FString& BoardId)> OnCreate;
    TFunction<void(const FString& GameId)> OnJoinRow;
    TFunction<void(const FString& Code)> OnJoinCode;
    TFunction<void()> OnRecover;
    TFunction<void()> OnMenu;
    TFunction<void(FName BankId)> OnSound;
  };
  void SetInput(const TSharedPtr<FS09HudPressArbiter>& InArbiter, FInput InInput);

  // ---- the model (the owner feeds it) ----
  void SetNickname(const FString& Name);
  /** The two board names (boardList); an empty one keeps the AGENTS.md name. */
  void SetBoardNames(const FString& Marmoreal, const FString& Sarpedon);
  /** The list: its state and (List) the rows in answer order; a row keeps its why until the next answer drops it. */
  void SetList(EUmLobbyList InList, const TArray<FUmLobbyRowModel>& InRows);
  /** A joinGame of a row was refused: the row explains itself until the next poll. */
  void MarkRowUnavailable(const FString& GameId, FName Why);
  void SetRecoverVisible(bool bVisible);
  /** Answers: a refused code (the code stays), a failed create; any answer ends busy. */
  void ShowCodeError(EUmCodeError E);
  void ShowCreateError();
  void EndBusy();
  /** Shown again (a new entry): busy ends, the code and the errors stay (the room entry may have been refused). */
  void OnShown();

  // ---- what the screen shows (tests, the gate, the evidence drive) ----
  EUmLobbyList GetList() const { return List; }
  EUmLobbyMode GetMode() const { return Mode; }
  const FString& GetBoardId() const { return BoardId; }
  bool IsCreateBusy() const { return bCreateBusy; }
  bool IsJoinBusy() const { return bJoinBusy; }
  bool IsBusy() const { return bCreateBusy || bJoinBusy; }
  bool IsCreateTouched() const { return bCreateTouched; }
  EUmCodeError GetCodeError() const { return CodeErr; }
  FString GetCode() const;
  bool IsCodeJoinEnabled() const;
  bool IsCodeJoinPrimary() const;
  bool IsCreatePrimary() const;
  int32 GetRowCount() const;
  int32 GetUnavailableCount() const;
  UUmLobbyGameRow* GetRow(int32 Index) const;
  UUmBoardChip* GetBoardChip(int32 Index) const;
  bool IsRecoverVisible() const { return bRecover; }
  bool IsSkeletonShown() const;
  bool IsCreateSpinnerShown() const;
  int32 GetCreateCount() const { return CreateCount; }
  int32 GetRowsBuilt() const { return RowsBuilt; }
  FString GetCreateLabel() const;
  FString GetNoteText() const;
  FString GetCodeErrorText() const;
  FString GetEmptyText() const;
  FString GetListErrorText() const;
  /** Press a control as a click does (the evidence drive, tests): screens.lobby.* ids. */
  void SimulatePress(FName Id);
  /** Type into the code box as the keyboard does (normalised). */
  void SetCodeText(const FString& Typed, bool bKeyboard = true);
  /** Per frame: the skeleton wait, the spinner, the code focus. */
  void StepLobby();
  virtual FString ShotExtra() const override;

  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UBorder> Header;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> NicknameText;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> MenuButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> LangRu;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> LangEn;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UBorder> GameList;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> ListTitle;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> RefreshButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmSkeletonRows> Skeleton;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UScrollBox> RowsScroll;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UVerticalBox> Rows;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> EmptyText;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> ErrorText;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> RetryButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UBorder> CreateColumn;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> CreateTitle;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> ModeChip1v1;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> ModeChipAi;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> CreateNote;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UCanvasPanel> BoardChips;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> CreateButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UBorder> CodeColumn;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> CodeTitle;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UEditableTextBox> CodeBox;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UCanvasPanel> CodeCells;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> CodeJoinButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> CodeError;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> RecoverButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UCanvasPanel> Content;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UTextBlock> ModeLabel;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UTextBlock> BoardLabel;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UTextBlock> CreateError;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UUmSpinner> CreateSpinner;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<US08AnimatedIconWidget> EmptyIcon;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<US08AnimatedIconWidget> ErrorIcon;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<US08AnimatedIconWidget> CodeErrorIcon;

  UPROPERTY() TArray<TObjectPtr<UUmLobbyGameRow>> RowPool;
  UPROPERTY() TArray<TObjectPtr<UUmBoardChip>> Boards;
  UPROPERTY() TArray<TObjectPtr<UBorder>> CellBoxes;
  UPROPERTY() TArray<TObjectPtr<UTextBlock>> CellChars;
  UPROPERTY() TArray<TObjectPtr<UImage>> CellLines;

 protected:
  virtual void BuildContent() override;
  virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;

 private:
  static bool AttachContent(UWidgetTree& Tree, UPanelWidget* Parent, FS08AttachWidget Attach, FString* OutError);
  void BindParts();
  void BuildCodeParts();
  void BuildBoardChips();
  void Layout();
  void LayoutRows();
  void Refresh();
  void RefreshTexts();
  void OnPressOutcome(FName Id, const FS09HudPressOutcome& Outcome);
  void BindRowPress(UUmLobbyGameRow* Row, int32 Index);
  void Sound(const TCHAR* Bank) const;
  void SubmitCreate();
  void SubmitCode();
  bool IsEnglish() const;
  UFUNCTION()
  void HandleCodeChanged(const FText& Text);
  UFUNCTION()
  void HandleCodeCommitted(const FText& Text, ETextCommit::Type Method);

  EUmLobbyList List = EUmLobbyList::Loading;
  TArray<FUmLobbyRowModel> RowModels;
  EUmLobbyMode Mode = EUmLobbyMode::OneVOne;
  FString BoardId = FString(UmLobby::MarmorealId);
  FString BoardName[2];
  bool bCreateTouched = false;
  bool bCreateBusy = false;
  bool bCreateError = false;
  bool bJoinBusy = false;
  bool bCodeKeyboard = false;
  bool bRecover = false;
  EUmCodeError CodeErr = EUmCodeError::None;
  bool bLastCodeFocus = false;
  int32 CreateCount = 0;
  int32 RowsBuilt = 0;
  double BusySinceMs = -1.0;
  double LoadingSinceMs = -1.0;
  bool bSettingCode = false;
  TSharedPtr<FS09HudPressArbiter> Arbiter;
  FInput Input;
};
