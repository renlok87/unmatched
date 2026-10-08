// VS-7 SC-08...SC-13: LOBBY - see UmScreenLobby.h.
#include "UmScreenLobby.h"

#include "../S08AnimatedIconWidget.h"
#include "../S08IconMotion.h"
#include "UmBoardChip.h"
#include "UmButton.h"
#include "UmGameHud.h"
#include "UmHudScale.h"
#include "UmHudTheme.h"
#include "UmSkeletonRows.h"
#include "UmSpinner.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/EditableTextBox.h"
#include "Components/Image.h"
#include "Components/NamedSlot.h"
#include "Components/ScrollBox.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "Fonts/FontMeasure.h"
#include "Framework/Application/SlateApplication.h"
#include "HAL/PlatformTime.h"
#include "Internationalization/Culture.h"
#include "Internationalization/Internationalization.h"

const TCHAR* const UUmScreenLobby::WidgetBlueprintPath = TEXT("/Game/S08/UI/Screens/WBP_UI_SCR_LOBBY");

UClass* UUmScreenLobby::WidgetClass() { return UmGameHudSlots::WbpOrNative(UUmScreenLobby::StaticClass(), WidgetBlueprintPath); }

// ------------------------------------------------------------------------------------------------ the model

namespace UmLobby {
FUmLobbyLayout Layout(const FVector2D& CanvasSu, bool bClassS) {
  FUmLobbyLayout L;
  L.bClassS = bClassS;
  const float W = CanvasSu.X, H = CanvasSu.Y;
  if (!bClassS) {
    // 04 §1.3 table (1080p and the 720p column at 1707 x 960 su)
    const bool bWide = W >= 1800.0f;
    const float RightW = bWide ? 672.0f : 568.0f;
    const float CreateH = bWide ? 520.0f : 500.0f;
    const float Rx = W - 24.0f - RightW;
    L.Header = {24.0f, 24.0f, W - 48.0f, 64.0f};
    L.List = {24.0f, 112.0f, Rx - 48.0f, H - 136.0f};
    L.Create = {Rx, 112.0f, RightW, CreateH};
    L.Code = {Rx, 112.0f + CreateH + 16.0f, RightW, 200.0f};
  } else {
    // ВР-VS4-SC08-09: margins and gaps 16, the right column 456 su
    const float Rx = W - 16.0f - 456.0f;
    L.Header = {16.0f, 16.0f, W - 32.0f, 64.0f};
    L.List = {16.0f, 96.0f, Rx - 32.0f, H - 112.0f};
    L.Create = {Rx, 96.0f, 456.0f, 312.0f};
    L.Code = {Rx, 424.0f, 456.0f, FMath::Max(200.0f, H - 16.0f - 424.0f)};
  }
  return L;
}

FString NormalizeCode(const FString& Typed) {
  FString Out;
  for (TCHAR C : Typed.ToUpper()) {
    if ((C >= TEXT('A') && C <= TEXT('Z')) || (C >= TEXT('0') && C <= TEXT('9'))) Out.AppendChar(C);
    if (Out.Len() >= CodeLength) break;
  }
  return Out;
}

EUmCodeError ClassifyCodeError(const FString& ErrorCode, const FString& Message) {
  // gameByCode answers null for unknown / full / started codes alike (NOT_FOUND of the lookup); joinGame says
  // «Игра уже заполнена» when the seat went between the lookup and the join (GD-029, ВР-VS4-SC11-01)
  if (Message.Contains(TEXT("заполнена")) || Message.Contains(TEXT("full"), ESearchCase::IgnoreCase)) return EUmCodeError::Full;
  return EUmCodeError::NotFound;
}

FName RowWhy(const FString& ErrorCode, const FString& Message) {
  if (Message.Contains(TEXT("заполнена")) || Message.Contains(TEXT("full"), ESearchCase::IgnoreCase)) return FName(TEXT("why.room.full"));
  // «Нельзя присоединиться к игре, которая уже началась или завершилась»; a room gone meanwhile reads the same
  return FName(TEXT("why.room.started"));
}

const TCHAR* ListName(EUmLobbyList L) {
  switch (L) {
    case EUmLobbyList::List: return TEXT("list");
    case EUmLobbyList::Empty: return TEXT("empty");
    case EUmLobbyList::Error: return TEXT("error");
    default: return TEXT("loading");
  }
}

const TCHAR* CodeErrorName(EUmCodeError E) {
  switch (E) {
    case EUmCodeError::NotFound: return TEXT("notfound");
    case EUmCodeError::Full: return TEXT("full");
    default: return TEXT("-");
  }
}

const TCHAR* StateName(EUmLobbyList InList, bool bCreateTouched, int32 CodeChars, EUmCodeError InCodeError) {
  if (InCodeError != EUmCodeError::None) return TEXT("code-error");
  if (CodeChars > 0) return TEXT("code");
  if (bCreateTouched) return TEXT("create");
  return ListName(InList);
}

bool FUmLobbyPoll::Due(double NowMs, bool bHasFocus) {
  const bool bRegained = bHasFocus && !bHadFocus;
  bHadFocus = bHasFocus;
  if (InFlightSinceMs >= 0.0 && !TimedOut(NowMs)) return false;  // one request at a time (a timed-out one may be re-asked)
  if (LastSentMs < 0.0 || bForce || bRegained) return true;
  return NowMs - LastSentMs >= PollMs;
}
}  // namespace UmLobby

// ------------------------------------------------------------------------------------------------ helpers

namespace {
template <typename T>
T* UmLbFind(UWidgetTree* Tree, const TCHAR* Name) {
  return Tree ? Cast<T>(Tree->FindWidget(FName(Name))) : nullptr;
}

void UmLbText(UTextBlock* T, const TCHAR* Type, const TCHAR* Color) {
  if (!T) return;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  T->SetFont(Theme.Font(FName(Type)));
  T->SetColorAndOpacity(FSlateColor(Theme.Color(FName(Color))));
  T->SetShadowOffset(FVector2D::ZeroVector);
}

void UmLbPlace(UWidget* W, const FVector2D& Pos, const FVector2D& Size) {
  UCanvasPanelSlot* S = W ? Cast<UCanvasPanelSlot>(W->Slot) : nullptr;
  if (!S) return;
  S->SetAnchors(FAnchors(0.0f, 0.0f));
  S->SetAlignment(FVector2D::ZeroVector);
  S->SetAutoSize(false);
  S->SetPosition(Pos);
  S->SetSize(Size);
}

float UmLbMeasureW(const FText& Text, const TCHAR* Type) {
  const FSlateFontInfo Font = UUmHudTheme::Get().Font(FName(Type));
  if (FSlateApplication::IsInitialized()) {
    return static_cast<float>(FSlateApplication::Get().GetRenderer()->GetFontMeasureService()->Measure(Text, Font, 1.0f).X);
  }
  return 0.55f * Font.Size * 96.0f / 72.0f * Text.ToString().Len();
}

void UmLbVis(UWidget* W, bool bOn, bool bHit = false) {
  if (W) W->SetVisibility(bOn ? (bHit ? ESlateVisibility::Visible : ESlateVisibility::HitTestInvisible) : ESlateVisibility::Collapsed);
}

FText UmLbS(const TCHAR* Key) { return UmText::Get(EUmTable::Screens, Key); }

bool UmLbIcon(US08AnimatedIconWidget* W, const TCHAR* Id, float Su) {
  if (!W) return false;
  const FName Icon(Id);
  if (W->GetIconId() != Icon && W->SetIcon(Icon, Su, S08IconMotion::ExportSizePx(Su, UmHudScale::Current().PxPerSu()))) {
    W->SetDisplaySizeSu(Su);
    W->ShowAtRest();
  }
  return true;
}

const TCHAR* const UmLbTextNames[] = {TEXT("NicknameText"), TEXT("ListTitle"), TEXT("EmptyText"), TEXT("ErrorText"),
                                      TEXT("CreateTitle"), TEXT("ModeLabel"), TEXT("CreateNote"), TEXT("BoardLabel"),
                                      TEXT("CreateError"), TEXT("CodeTitle"), TEXT("CodeError")};
const TCHAR* const UmLbButtonNames[] = {TEXT("MenuButton"), TEXT("LangRu"), TEXT("LangEn"), TEXT("RefreshButton"),
                                        TEXT("RetryButton"), TEXT("ModeChip1v1"), TEXT("ModeChipAi"), TEXT("CreateButton"),
                                        TEXT("CodeJoinButton"), TEXT("RecoverButton")};
const TCHAR* const UmLbIconNames[] = {TEXT("EmptyIcon"), TEXT("ErrorIcon"), TEXT("CodeErrorIcon")};
}  // namespace

// ------------------------------------------------------------------------------------------------ the tree

bool UUmScreenLobby::AttachContent(UWidgetTree& Tree, UPanelWidget* Parent, FS08AttachWidget Attach, FString* OutError) {
  auto Fail = [OutError](const TCHAR* What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), What);
    return false;
  };
  UCanvasPanel* ContentW = Tree.ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Content")));
  ContentW->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  if (!Attach(ContentW, Parent)) return Fail(TEXT("Content"));
  // the panels first (under everything else)
  for (const TCHAR* Name : {TEXT("Header"), TEXT("GameList"), TEXT("CreateColumn"), TEXT("CodeColumn")}) {
    UBorder* B = Tree.ConstructWidget<UBorder>(UBorder::StaticClass(), FName(Name));
    B->SetVisibility(ESlateVisibility::HitTestInvisible);
    if (!Attach(B, ContentW)) return Fail(Name);
  }
  for (const TCHAR* Name : UmLbTextNames) {
    UTextBlock* T = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(Name));
    T->SetVisibility(ESlateVisibility::HitTestInvisible);
    if (!Attach(T, ContentW)) return Fail(Name);
  }
  UClass* ButtonClass = UmGameHudSlots::WbpOrNative(UUmButton::StaticClass(), UUmButton::WidgetBlueprintPath);
  for (const TCHAR* Name : UmLbButtonNames) {
    if (!Attach(Tree.ConstructWidget<UUmButton>(ButtonClass, FName(Name)), ContentW)) return Fail(Name);
  }
  for (const TCHAR* Name : UmLbIconNames) {
    if (!Attach(Tree.ConstructWidget<US08AnimatedIconWidget>(US08AnimatedIconWidget::StaticClass(), FName(Name)), ContentW)) return Fail(Name);
  }
  if (!Attach(Tree.ConstructWidget<UUmSpinner>(UUmSpinner::WidgetClass(), FName(TEXT("CreateSpinner"))), ContentW)) return Fail(TEXT("CreateSpinner"));
  if (!Attach(Tree.ConstructWidget<UUmSkeletonRows>(UUmSkeletonRows::StaticClass(), FName(TEXT("Skeleton"))), ContentW)) return Fail(TEXT("Skeleton"));
  UScrollBox* Scroll = Tree.ConstructWidget<UScrollBox>(UScrollBox::StaticClass(), FName(TEXT("RowsScroll")));
  if (!Attach(Scroll, ContentW)) return Fail(TEXT("RowsScroll"));
  if (!Attach(Tree.ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), FName(TEXT("Rows"))), Scroll)) return Fail(TEXT("Rows"));
  for (const TCHAR* Name : {TEXT("BoardChips"), TEXT("CodeCells")}) {
    UCanvasPanel* C = Tree.ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(Name));
    C->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
    if (!Attach(C, ContentW)) return Fail(Name);
  }
  // the code box over the cells (invisible: the cells draw the code)
  if (!Attach(Tree.ConstructWidget<UEditableTextBox>(UEditableTextBox::StaticClass(), FName(TEXT("CodeBox"))), ContentW)) return Fail(TEXT("CodeBox"));
  return true;
}

bool UUmScreenLobby::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  if (!UUmScreenBase::BuildDefaultTree(Tree, Attach, OutError)) return false;
  UNamedSlot* BodyW = Cast<UNamedSlot>(Tree.FindWidget(FName(TEXT("Body"))));
  if (!BodyW) {
    if (OutError) *OutError = TEXT("no Body");
    return false;
  }
  return AttachContent(Tree, BodyW, Attach, OutError);
}

void UUmScreenLobby::BuildContent() {
  if (!WidgetTree || !Body || Body->GetContent()) return;
  FString Problem;
  auto AddTo = [](UWidget* Child, UPanelWidget* Parent) { return Parent && Parent->AddChild(Child) != nullptr; };
  if (!AttachContent(*WidgetTree, Body, AddTo, &Problem)) UE_LOG(LogTemp, Error, TEXT("UMHUD lobby content: %s"), *Problem);
}

void UUmScreenLobby::BindParts() {
  Content = UmLbFind<UCanvasPanel>(WidgetTree, TEXT("Content"));
  Header = UmLbFind<UBorder>(WidgetTree, TEXT("Header"));
  GameList = UmLbFind<UBorder>(WidgetTree, TEXT("GameList"));
  CreateColumn = UmLbFind<UBorder>(WidgetTree, TEXT("CreateColumn"));
  CodeColumn = UmLbFind<UBorder>(WidgetTree, TEXT("CodeColumn"));
  NicknameText = UmLbFind<UTextBlock>(WidgetTree, TEXT("NicknameText"));
  ListTitle = UmLbFind<UTextBlock>(WidgetTree, TEXT("ListTitle"));
  EmptyText = UmLbFind<UTextBlock>(WidgetTree, TEXT("EmptyText"));
  ErrorText = UmLbFind<UTextBlock>(WidgetTree, TEXT("ErrorText"));
  CreateTitle = UmLbFind<UTextBlock>(WidgetTree, TEXT("CreateTitle"));
  ModeLabel = UmLbFind<UTextBlock>(WidgetTree, TEXT("ModeLabel"));
  CreateNote = UmLbFind<UTextBlock>(WidgetTree, TEXT("CreateNote"));
  BoardLabel = UmLbFind<UTextBlock>(WidgetTree, TEXT("BoardLabel"));
  CreateError = UmLbFind<UTextBlock>(WidgetTree, TEXT("CreateError"));
  CodeTitle = UmLbFind<UTextBlock>(WidgetTree, TEXT("CodeTitle"));
  CodeError = UmLbFind<UTextBlock>(WidgetTree, TEXT("CodeError"));
  MenuButton = UmLbFind<UUmButton>(WidgetTree, TEXT("MenuButton"));
  LangRu = UmLbFind<UUmButton>(WidgetTree, TEXT("LangRu"));
  LangEn = UmLbFind<UUmButton>(WidgetTree, TEXT("LangEn"));
  RefreshButton = UmLbFind<UUmButton>(WidgetTree, TEXT("RefreshButton"));
  RetryButton = UmLbFind<UUmButton>(WidgetTree, TEXT("RetryButton"));
  ModeChip1v1 = UmLbFind<UUmButton>(WidgetTree, TEXT("ModeChip1v1"));
  ModeChipAi = UmLbFind<UUmButton>(WidgetTree, TEXT("ModeChipAi"));
  CreateButton = UmLbFind<UUmButton>(WidgetTree, TEXT("CreateButton"));
  CodeJoinButton = UmLbFind<UUmButton>(WidgetTree, TEXT("CodeJoinButton"));
  RecoverButton = UmLbFind<UUmButton>(WidgetTree, TEXT("RecoverButton"));
  EmptyIcon = UmLbFind<US08AnimatedIconWidget>(WidgetTree, TEXT("EmptyIcon"));
  ErrorIcon = UmLbFind<US08AnimatedIconWidget>(WidgetTree, TEXT("ErrorIcon"));
  CodeErrorIcon = UmLbFind<US08AnimatedIconWidget>(WidgetTree, TEXT("CodeErrorIcon"));
  CreateSpinner = UmLbFind<UUmSpinner>(WidgetTree, TEXT("CreateSpinner"));
  Skeleton = UmLbFind<UUmSkeletonRows>(WidgetTree, TEXT("Skeleton"));
  RowsScroll = UmLbFind<UScrollBox>(WidgetTree, TEXT("RowsScroll"));
  Rows = UmLbFind<UVerticalBox>(WidgetTree, TEXT("Rows"));
  BoardChips = UmLbFind<UCanvasPanel>(WidgetTree, TEXT("BoardChips"));
  CodeCells = UmLbFind<UCanvasPanel>(WidgetTree, TEXT("CodeCells"));
  CodeBox = UmLbFind<UEditableTextBox>(WidgetTree, TEXT("CodeBox"));
}

void UUmScreenLobby::BuildCodeParts() {
  // six cells: the input skin, the character, the underline of an empty cell (run-time children of CodeCells)
  if (!CodeCells || !WidgetTree || CellBoxes.Num() == UmLobby::CodeLength) return;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  for (int32 I = 0; I < UmLobby::CodeLength; ++I) {
    UBorder* Box = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass());
    Box->SetVisibility(ESlateVisibility::HitTestInvisible);
    Box->SetPadding(FMargin(0.0f));
    Box->SetHorizontalAlignment(HAlign_Center);
    Box->SetVerticalAlignment(VAlign_Center);
    UTextBlock* Char = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
    UmLbText(Char, TEXT("type.title"), TEXT("text.primary"));
    Char->SetJustification(ETextJustify::Center);
    Box->SetContent(Char);
    CodeCells->AddChild(Box);
    UImage* Line = WidgetTree->ConstructWidget<UImage>(UImage::StaticClass());
    Line->SetBrush(UmLoader::LineBrush());
    Line->SetColorAndOpacity(Theme.Color(TEXT("text.secondary")));
    Line->SetVisibility(ESlateVisibility::HitTestInvisible);
    CodeCells->AddChild(Line);
    CellBoxes.Add(Box);
    CellChars.Add(Char);
    CellLines.Add(Line);
  }
}

void UUmScreenLobby::BuildBoardChips() {
  if (!BoardChips || !WidgetTree || Boards.Num() == 2) return;
  for (int32 I = 0; I < 2; ++I) {
    UUmBoardChip* Chip = WidgetTree->ConstructWidget<UUmBoardChip>(UUmBoardChip::StaticClass(), FName(*FString::Printf(TEXT("BoardChip%d"), I)));
    BoardChips->AddChild(Chip);
    Boards.Add(Chip);
  }
  Boards[0]->Setup(UmLobby::MarmorealId, FText::FromString(BoardName[0]));
  Boards[1]->Setup(UmLobby::SarpedonId, FText::FromString(BoardName[1]));
}

bool UUmScreenLobby::Initialize() {
  SetIsFocusable(true);
  const bool bFirst = Super::Initialize();
  if (!bFirst || !WidgetTree) return bFirst;
  SetUiId(TEXT("UI-SCR-LOBBY"));
  SetScreenState(FName(TEXT("loading")));
  BoardName[0] = UmLobby::MarmorealName;
  BoardName[1] = UmLobby::SarpedonName;
  BindParts();
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  const float ScalePx = UmHudScale::Current().PxPerSu();
  if (const FSlateBrush* Panel = Theme.SkinFor(TEXT("panel"), ScalePx)) {
    if (Header) Header->SetBrush(*Panel);
  }
  for (UBorder* B : {GameList.Get(), CreateColumn.Get(), CodeColumn.Get()}) {
    if (const FSlateBrush* Screen = Theme.SkinFor(TEXT("modal"), ScalePx)) {
      if (B) B->SetBrush(*Screen);
    }
  }
  UmLbText(NicknameText, TEXT("type.heading"), TEXT("text.primary"));
  UmLbText(ListTitle, TEXT("type.heading"), TEXT("text.primary"));
  UmLbText(EmptyText, TEXT("type.body"), TEXT("text.secondary"));
  UmLbText(ErrorText, TEXT("type.body"), TEXT("text.primary"));
  UmLbText(CreateTitle, TEXT("type.title"), TEXT("text.primary"));
  UmLbText(ModeLabel, TEXT("type.body"), TEXT("text.secondary"));
  UmLbText(CreateNote, TEXT("type.body"), TEXT("text.secondary"));
  UmLbText(BoardLabel, TEXT("type.body"), TEXT("text.secondary"));
  UmLbText(CreateError, TEXT("type.body"), TEXT("text.primary"));
  UmLbText(CodeTitle, TEXT("type.title"), TEXT("text.primary"));
  UmLbText(CodeError, TEXT("type.body"), TEXT("text.primary"));
  if (EmptyText) {
    EmptyText->SetJustification(ETextJustify::Center);
    EmptyText->SetAutoWrapText(true);
  }
  if (ErrorText) ErrorText->SetJustification(ETextJustify::Center);
  UmLbIcon(EmptyIcon, TEXT("state-hint"), 32.0f);
  UmLbIcon(ErrorIcon, TEXT("resource-connection-lost"), 48.0f);
  UmLbIcon(CodeErrorIcon, TEXT("badge-refuse"), 24.0f);
  if (CreateSpinner) CreateSpinner->SetSizeSu(UmLoader::SpinnerSmallSu);
  if (Skeleton) Skeleton->SetRows(UmLobby::SkeletonRows, UmLobbyRow::HeightSu);
  if (CodeBox) {
    // the box takes the keys; the cells draw the code (ВР-VS4-SC11-04) - its own glyphs and skin stay invisible
    CodeBox->SetRenderOpacity(0.0f);
    CodeBox->SetRevertTextOnEscape(false);
    CodeBox->SetClearKeyboardFocusOnCommit(false);
    CodeBox->OnTextChanged.AddUniqueDynamic(this, &UUmScreenLobby::HandleCodeChanged);
    CodeBox->OnTextCommitted.AddUniqueDynamic(this, &UUmScreenLobby::HandleCodeCommitted);
  }
  BuildCodeParts();
  BuildBoardChips();
  // a full screen: the panels stand on the veil, the frame draws nothing
  if (Frame) Frame->SetBrush(FSlateNoResource());
  RefreshTexts();
  Refresh();
  return bFirst;
}

bool UUmScreenLobby::HasAllParts(FString* OutMissing) const {
  FString Base;
  HasBaseParts(&Base);
  TArray<FString> Missing;
  if (!Base.IsEmpty()) Missing.Add(Base);
  auto Need = [&Missing](const UObject* P, const TCHAR* Name) {
    if (!P) Missing.Add(Name);
  };
  Need(Header, TEXT("Header"));
  Need(NicknameText, TEXT("NicknameText"));
  Need(MenuButton, TEXT("MenuButton"));
  Need(LangRu, TEXT("LangRu"));
  Need(LangEn, TEXT("LangEn"));
  Need(GameList, TEXT("GameList"));
  Need(ListTitle, TEXT("ListTitle"));
  Need(RefreshButton, TEXT("RefreshButton"));
  Need(Skeleton, TEXT("Skeleton"));
  Need(RowsScroll, TEXT("RowsScroll"));
  Need(Rows, TEXT("Rows"));
  Need(EmptyText, TEXT("EmptyText"));
  Need(ErrorText, TEXT("ErrorText"));
  Need(RetryButton, TEXT("RetryButton"));
  Need(CreateColumn, TEXT("CreateColumn"));
  Need(CreateTitle, TEXT("CreateTitle"));
  Need(ModeChip1v1, TEXT("ModeChip1v1"));
  Need(ModeChipAi, TEXT("ModeChipAi"));
  Need(CreateNote, TEXT("CreateNote"));
  Need(BoardChips, TEXT("BoardChips"));
  Need(CreateButton, TEXT("CreateButton"));
  Need(CodeColumn, TEXT("CodeColumn"));
  Need(CodeTitle, TEXT("CodeTitle"));
  Need(CodeBox, TEXT("CodeBox"));
  Need(CodeCells, TEXT("CodeCells"));
  Need(CodeJoinButton, TEXT("CodeJoinButton"));
  Need(CodeError, TEXT("CodeError"));
  Need(RecoverButton, TEXT("RecoverButton"));
  if (Boards.Num() != 2) Missing.Add(TEXT("BoardChips[2]"));
  if (CellBoxes.Num() != UmLobby::CodeLength) Missing.Add(TEXT("CodeCells[6]"));
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

void UUmScreenLobby::ApplyCanvas(const FVector2D& InCanvasSu, bool bInClassS, float InPxPerSu) {
  SetCanvas(InCanvasSu, bInClassS, InPxPerSu);
  if (Frame) Frame->SetBrush(FSlateNoResource());  // Relayout put the modal skin back
  Layout();
}

// ------------------------------------------------------------------------------------------------ layout

void UUmScreenLobby::Layout() {
  const FUmLobbyLayout L = UmLobby::Layout(CanvasSu, bClassS);
  const FVector2D O = FrameRectSu().Min;  // canvas su -> the frame's local su
  auto P = [&O](UWidget* W, float X, float Y, float Wd, float Ht) { UmLbPlace(W, FVector2D(X, Y) - O, FVector2D(Wd, Ht)); };
  P(Header, L.Header.X, L.Header.Y, L.Header.W, L.Header.H);
  P(GameList, L.List.X, L.List.Y, L.List.W, L.List.H);
  P(CreateColumn, L.Create.X, L.Create.Y, L.Create.W, L.Create.H);
  P(CodeColumn, L.Code.X, L.Code.Y, L.Code.W, L.Code.H);
  // ---- header: the nickname left, ≡ RU EN right (ВР-VS4-SC08-07)
  const FUmRectSu& Hd = L.Header;
  P(NicknameText, Hd.X + 16.0f, Hd.Y + 16.0f, 360.0f, 32.0f);
  const float EnX = Hd.X + Hd.W - 16.0f - 48.0f;
  P(LangEn, EnX, Hd.Y + 16.0f, 48.0f, 32.0f);
  P(LangRu, EnX - 56.0f, Hd.Y + 16.0f, 48.0f, 32.0f);
  P(MenuButton, EnX - 112.0f, Hd.Y + 12.0f, 40.0f, 40.0f);
  // ---- the list
  const FUmRectSu& Ls = L.List;
  P(ListTitle, Ls.X + 16.0f, Ls.Y + 16.0f, Ls.W - 200.0f, 32.0f);
  P(RefreshButton, Ls.X + Ls.W - 16.0f - 144.0f, Ls.Y + 16.0f, 144.0f, 40.0f);
  const float RowsY = Ls.Y + UmLobby::RowsTopSu;
  const float RowsW = Ls.W - 32.0f;
  const float RowsH = Ls.H - UmLobby::RowsTopSu - 16.0f;
  P(Skeleton, Ls.X + 16.0f, RowsY, RowsW, UmLobby::SkeletonRows * UmLobbyRow::HeightSu);
  P(RowsScroll, Ls.X + 16.0f, RowsY, RowsW, RowsH);
  const float Cy = RowsY + 0.38f * RowsH;  // the empty / error block a little above the middle of the rows area
  P(EmptyIcon, Ls.X + 0.5f * Ls.W - 16.0f, Cy - 48.0f, 32.0f, 32.0f);
  P(EmptyText, Ls.X + 0.5f * Ls.W - FMath::Min(560.0f, 0.5f * RowsW), Cy, FMath::Min(1120.0f, RowsW), 52.0f);
  P(ErrorIcon, Ls.X + 0.5f * Ls.W - 24.0f, Cy - 64.0f, 48.0f, 48.0f);
  P(ErrorText, Ls.X + 16.0f, Cy, RowsW, 24.0f);
  P(RetryButton, Ls.X + 0.5f * Ls.W - 80.0f, Cy + 40.0f, 160.0f, 40.0f);
  // ---- Create (L: title / mode row / note / board label / tiles / button; S: title and mode row on one line)
  const FUmRectSu& Cr = L.Create;
  const float Iw = Cr.W - 32.0f;
  const bool bAi = Mode == EUmLobbyMode::VsAi;
  const float ModeLabelW = UmLbMeasureW(ModeLabel ? ModeLabel->GetText() : FText(), TEXT("type.body")) + 2.0f;
  const float ChipAiW = FMath::Max(100.0f, UmLbMeasureW(UmLbS(TEXT("screens.lobby.create.mode.ai")), TEXT("type.button")) + 24.0f);
  const float Chip1W = FMath::Max(48.0f, UmLbMeasureW(UmLbS(TEXT("screens.lobby.create.mode.1v1")), TEXT("type.button")) + 24.0f);
  float ModeX = Cr.X + 16.0f, ModeY = Cr.Y + 72.0f, NoteY, LabelY, TilesY, TilesH;
  if (!bClassS) {
    P(CreateTitle, Cr.X + 16.0f, Cr.Y + 16.0f, Iw, 34.0f);
    NoteY = Cr.Y + 120.0f;
    LabelY = Cr.Y + 152.0f;
    TilesY = Cr.Y + 180.0f;
    TilesH = 232.0f;
  } else {
    const float TitleW = UmLbMeasureW(CreateTitle ? CreateTitle->GetText() : FText(), TEXT("type.title")) + 2.0f;
    P(CreateTitle, Cr.X + 16.0f, Cr.Y + 16.0f, TitleW, 34.0f);
    ModeX = Cr.X + 16.0f + TitleW + 16.0f;
    ModeY = Cr.Y + 16.0f;
    NoteY = Cr.Y + 60.0f;
    LabelY = Cr.Y + (bAi ? 84.0f : 72.0f);
    TilesY = LabelY + 28.0f;
    TilesH = 136.0f;
  }
  P(ModeLabel, ModeX, ModeY + 6.0f, ModeLabelW, 20.0f);
  P(ModeChip1v1, ModeX + ModeLabelW + 8.0f, ModeY, Chip1W, 32.0f);
  P(ModeChipAi, ModeX + ModeLabelW + 8.0f + Chip1W + 8.0f, ModeY, ChipAiW, 32.0f);
  P(CreateNote, Cr.X + 16.0f, NoteY, Iw, 22.0f);
  P(BoardLabel, Cr.X + 16.0f, LabelY, Iw, 22.0f);
  const float TileW = 0.5f * (Iw - 16.0f);
  P(BoardChips, Cr.X + 16.0f, TilesY, Iw, TilesH);
  for (int32 I = 0; I < Boards.Num(); ++I) {
    UmLbPlace(Boards[I], FVector2D(I * (TileW + 16.0f), 0.0f), FVector2D(TileW, TilesH));
    Boards[I]->Apply(FVector2D(TileW, TilesH), BoardId == Boards[I]->GetBoardId(), false, true);  // busy keeps the selection look
  }
  const float CreateY = bClassS ? TilesY + TilesH + 12.0f : Cr.Y + Cr.H - 64.0f;
  P(CreateButton, Cr.X + 16.0f, CreateY, Iw, 48.0f);
  const float LabelW = UmLbMeasureW(FText::FromString(GetCreateLabel().ToUpper()), TEXT("type.button"));
  P(CreateSpinner, Cr.X + 16.0f + 0.5f * (Iw - LabelW) - 8.0f - 32.0f, CreateY + 8.0f, 32.0f, 32.0f);
  // the create error: above the button (L), in the note slot (S)
  P(CreateError, Cr.X + 16.0f, bClassS ? NoteY : CreateY - 30.0f, Iw, 22.0f);
  // ---- Code (ВР-VS4-SC11-04: 56 su cells, class S 48; the code «Войти» right of them, class S under them)
  const FUmRectSu& Cd = L.Code;
  P(CodeTitle, Cd.X + 16.0f, Cd.Y + 16.0f, Cd.W - 32.0f, 34.0f);
  const float CellSu = bClassS ? 48.0f : 56.0f;
  const float CellStep = CellSu + 8.0f;
  const float CellsY = Cd.Y + (bClassS ? 56.0f : 64.0f);
  P(CodeCells, Cd.X + 16.0f, CellsY, UmLobby::CodeLength * CellStep, CellSu);
  P(CodeBox, Cd.X + 16.0f, CellsY, UmLobby::CodeLength * CellStep - 8.0f, CellSu);
  for (int32 I = 0; I < CellBoxes.Num(); ++I) {
    UmLbPlace(CellBoxes[I], FVector2D(I * CellStep, 0.0f), FVector2D(CellSu, CellSu));
    UmLbPlace(CellLines[I], FVector2D(I * CellStep + 0.5f * (CellSu - 24.0f), CellSu - 12.0f - 2.0f), FVector2D(24.0f, 2.0f));
  }
  float ErrY;
  if (!bClassS) {
    const float JoinW = FMath::Min(160.0f, Cd.W - 32.0f - UmLobby::CodeLength * CellStep - 8.0f);
    P(CodeJoinButton, Cd.X + Cd.W - 16.0f - JoinW, CellsY + 4.0f, JoinW, 48.0f);
    ErrY = CellsY + CellSu + 12.0f;
  } else {
    P(CodeJoinButton, Cd.X + 16.0f, CellsY + CellSu + 8.0f, Cd.W - 32.0f, 48.0f);
    ErrY = CellsY + CellSu + 8.0f + 48.0f + 8.0f;
  }
  const bool bErrIcon = CodeErr != EUmCodeError::None;
  P(CodeErrorIcon, Cd.X + 16.0f, ErrY, 24.0f, 24.0f);
  P(CodeError, Cd.X + 16.0f + (bErrIcon ? 32.0f : 0.0f), ErrY + 1.0f, Cd.W - 32.0f - (bErrIcon ? 32.0f : 0.0f), 24.0f);
  // «Вернуться в мою партию»: L under the code «Войти» at the right; S in the header (no room in the column)
  const float RecW = FMath::Max(120.0f, UmLbMeasureW(FText::FromString(UmLbS(TEXT("screens.lobby.recover")).ToString().ToUpper()), TEXT("type.button")) + 32.0f);
  if (!bClassS) {
    P(RecoverButton, Cd.X + Cd.W - 16.0f - RecW, Cd.Y + 124.0f, RecW, 40.0f);
  } else {
    P(RecoverButton, EnX - 112.0f - 16.0f - RecW, Hd.Y + 12.0f, RecW, 40.0f);
  }
  LayoutRows();
}

void UUmScreenLobby::LayoutRows() {
  if (!Rows) return;
  const FUmLobbyLayout L = UmLobby::Layout(CanvasSu, bClassS);
  const float RowW = L.List.W - 32.0f;
  // one fixed x per column: the widest text of each column over the shown rows (ВР-VS4-SC08-04)
  float CodeW = 0.0f, ModeW = 0.0f, BoardW = 0.0f, SeatsW = 0.0f, DiscsW = 0.0f;
  for (const FUmLobbyRowModel& M : RowModels) {
    CodeW = FMath::Max(CodeW, UmLbMeasureW(FText::FromString(M.Code), TEXT("type.heading")));
    ModeW = FMath::Max(ModeW, UmLbMeasureW(M.Mode, TEXT("type.body")));
    BoardW = FMath::Max(BoardW, UmLbMeasureW(FText::FromString(M.Board), TEXT("type.body")));
    SeatsW = FMath::Max(SeatsW, UmLbMeasureW(FText::FromString(UmLobbyRow::SeatsText(M.Seats, M.MaxSeats)), TEXT("type.body")));
    DiscsW = FMath::Max(DiscsW, M.HeroKeys.Num() * (UmLobbyRow::DiscSu + UmLobbyRow::DiscGapSu));
  }
  DiscsW = FMath::Max(DiscsW, UmLobbyRow::DiscSu);
  const float JoinW = UmLbMeasureW(FText::FromString(UmLbS(TEXT("screens.lobby.row.join")).ToString().ToUpper()), TEXT("type.button")) + 2.0f * 32.0f;
  const FUmLobbyColumns C = UmLobbyRow::Columns(RowW, CodeW + 4.0f, ModeW + 4.0f, BoardW + 4.0f, SeatsW + 4.0f, DiscsW, JoinW);
  for (UUmLobbyGameRow* Row : RowPool) {
    if (Row) Row->ApplyColumns(C, RowW);
  }
}

// ------------------------------------------------------------------------------------------------ model in

void UUmScreenLobby::SetNickname(const FString& Name) {
  if (NicknameText) NicknameText->SetText(FText::FromString(Name));
}

void UUmScreenLobby::SetBoardNames(const FString& Marmoreal, const FString& Sarpedon) {
  const FString A = Marmoreal.IsEmpty() ? FString(UmLobby::MarmorealName) : Marmoreal;
  const FString B = Sarpedon.IsEmpty() ? FString(UmLobby::SarpedonName) : Sarpedon;
  if (A == BoardName[0] && B == BoardName[1]) return;
  BoardName[0] = A;
  BoardName[1] = B;
  if (Boards.Num() == 2) {
    Boards[0]->Setup(UmLobby::MarmorealId, FText::FromString(A));
    Boards[1]->Setup(UmLobby::SarpedonId, FText::FromString(B));
  }
  Layout();
}

void UUmScreenLobby::SetList(EUmLobbyList InList, const TArray<FUmLobbyRowModel>& InRows) {
  // ВР-VS4-SC13-01 draws the error in the empty list area: rows show only in the list state
  TArray<FUmLobbyRowModel> Next = InRows;
  for (FUmLobbyRowModel& M : Next) {
    const FUmLobbyRowModel* Old = RowModels.FindByPredicate([&M](const FUmLobbyRowModel& R) { return R.GameId == M.GameId; });
    if (Old && !Old->Why.IsNone() && M.Why.IsNone()) M.Why = Old->Why;  // stays until the next answer drops the row
  }
  List = InList;
  if (InList != EUmLobbyList::Loading) RowModels = InList == EUmLobbyList::List ? Next : TArray<FUmLobbyRowModel>();
  if (InList == EUmLobbyList::Loading) LoadingSinceMs = FPlatformTime::Seconds() * 1000.0;
  // the pool: grows once, a poll never recreates a row
  const float ScalePx = UmHudScale::Current().PxPerSu();
  while (Rows && RowPool.Num() < RowModels.Num()) {
    UUmLobbyGameRow* Row = CreateWidget<UUmLobbyGameRow>(this, UUmLobbyGameRow::StaticClass());
    if (!Row) break;
    if (UVerticalBoxSlot* S = Rows->AddChildToVerticalBox(Row)) S->SetPadding(FMargin(0.0f, 0.0f, 0.0f, UmLobbyRow::GapSu));
    BindRowPress(Row, RowPool.Num());
    RowPool.Add(Row);
    ++RowsBuilt;
  }
  for (int32 I = 0; I < RowPool.Num(); ++I) {
    UUmLobbyGameRow* Row = RowPool[I];
    if (!Row) continue;
    if (I < RowModels.Num()) {
      if (Row->GetModel() != RowModels[I]) Row->ApplyModel(RowModels[I], ScalePx);
      Row->SetVisibility(ESlateVisibility::Visible);
    } else {
      Row->SetVisibility(ESlateVisibility::Collapsed);
    }
  }
  LayoutRows();
  Refresh();
}

void UUmScreenLobby::MarkRowUnavailable(const FString& GameId, FName Why) {
  for (int32 I = 0; I < RowModels.Num(); ++I) {
    if (RowModels[I].GameId != GameId) continue;
    RowModels[I].Why = Why;
    if (RowPool.IsValidIndex(I) && RowPool[I]) RowPool[I]->ApplyModel(RowModels[I], UmHudScale::Current().PxPerSu());
  }
  bJoinBusy = false;
  Refresh();
}

void UUmScreenLobby::SetRecoverVisible(bool bVisible) {
  if (bRecover == bVisible) return;
  bRecover = bVisible;
  Refresh();
}

void UUmScreenLobby::ShowCodeError(EUmCodeError E) {
  CodeErr = E;
  bJoinBusy = false;
  if (E != EUmCodeError::None) Sound(TEXT("UI-REJECT"));
  Layout();
  Refresh();
}

void UUmScreenLobby::ShowCreateError() {
  bCreateBusy = false;
  bCreateError = true;
  Refresh();
}

void UUmScreenLobby::EndBusy() {
  bCreateBusy = false;
  bJoinBusy = false;
  Refresh();
}

void UUmScreenLobby::OnShown() {
  bCreateBusy = false;
  bJoinBusy = false;
  bCreateError = false;
  RefreshTexts();
  Layout();
  Refresh();
}

// ------------------------------------------------------------------------------------------------ what it shows

FString UUmScreenLobby::GetCode() const { return CodeBox ? UmLobby::NormalizeCode(CodeBox->GetText().ToString()) : FString(); }
bool UUmScreenLobby::IsCodeJoinEnabled() const { return CodeJoinButton && CodeJoinButton->GetModel().bEnabled; }
bool UUmScreenLobby::IsCodeJoinPrimary() const { return CodeJoinButton && CodeJoinButton->GetModel().Variant == EUmButtonVariant::Primary; }
bool UUmScreenLobby::IsCreatePrimary() const { return CreateButton && CreateButton->GetModel().Variant == EUmButtonVariant::Primary; }
int32 UUmScreenLobby::GetRowCount() const { return RowModels.Num(); }
int32 UUmScreenLobby::GetUnavailableCount() const {
  return RowModels.FilterByPredicate([](const FUmLobbyRowModel& M) { return !M.Why.IsNone(); }).Num();
}
UUmLobbyGameRow* UUmScreenLobby::GetRow(int32 Index) const { return RowPool.IsValidIndex(Index) && Index < RowModels.Num() ? RowPool[Index].Get() : nullptr; }
UUmBoardChip* UUmScreenLobby::GetBoardChip(int32 Index) const { return Boards.IsValidIndex(Index) ? Boards[Index].Get() : nullptr; }
bool UUmScreenLobby::IsSkeletonShown() const { return Skeleton && Skeleton->IsShown(); }
bool UUmScreenLobby::IsCreateSpinnerShown() const { return CreateSpinner && CreateSpinner->IsShown(); }
FString UUmScreenLobby::GetCreateLabel() const { return CreateButton ? CreateButton->GetModel().Label.ToString() : FString(); }
FString UUmScreenLobby::GetNoteText() const {
  return CreateNote && CreateNote->GetVisibility() != ESlateVisibility::Collapsed ? CreateNote->GetText().ToString() : FString();
}
FString UUmScreenLobby::GetCodeErrorText() const {
  return CodeErr != EUmCodeError::None && CodeError && CodeError->GetVisibility() != ESlateVisibility::Collapsed
             ? CodeError->GetText().ToString()
             : FString();
}
FString UUmScreenLobby::GetEmptyText() const {
  return EmptyText && EmptyText->GetVisibility() != ESlateVisibility::Collapsed ? EmptyText->GetText().ToString() : FString();
}
FString UUmScreenLobby::GetListErrorText() const {
  return ErrorText && ErrorText->GetVisibility() != ESlateVisibility::Collapsed ? ErrorText->GetText().ToString() : FString();
}
bool UUmScreenLobby::IsEnglish() const {
  return FInternationalization::Get().GetCurrentLanguage()->GetTwoLetterISOLanguageName() == TEXT("en");
}

// ------------------------------------------------------------------------------------------------ refresh

void UUmScreenLobby::RefreshTexts() {
  if (ListTitle) ListTitle->SetText(UmLbS(TEXT("screens.lobby.list.title")));
  if (EmptyText) EmptyText->SetText(UmLbS(TEXT("screens.lobby.list.empty")));
  if (ErrorText) ErrorText->SetText(UmLbS(TEXT("screens.lobby.list.error")));
  if (CreateTitle) CreateTitle->SetText(UmLbS(TEXT("screens.lobby.create.title")));
  if (ModeLabel) ModeLabel->SetText(UmLbS(TEXT("screens.lobby.create.mode")));
  if (CreateNote) {
    FFormatNamedArguments Args;
    Args.Add(TEXT("name"), FText::FromString(UmLobby::AiBotName));
    CreateNote->SetText(FText::Format(UmLbS(TEXT("screens.lobby.create.ai.note")), Args));
  }
  if (BoardLabel) BoardLabel->SetText(UmLbS(TEXT("screens.lobby.create.board")));
  if (CreateError) CreateError->SetText(UmLbS(TEXT("screens.boot.error.server")));
  if (CodeTitle) CodeTitle->SetText(UmLbS(TEXT("screens.lobby.code.title")));
  const FText Mode1v1 = UmLbS(TEXT("screens.lobby.create.mode.1v1"));
  for (FUmLobbyRowModel& M : RowModels) M.Mode = Mode1v1;
  for (int32 I = 0; I < RowPool.Num() && I < RowModels.Num(); ++I) {
    if (RowPool[I]) RowPool[I]->ApplyModel(RowModels[I], UmHudScale::Current().PxPerSu());
  }
}

void UUmScreenLobby::Refresh() {
  const FString Code = GetCode();
  const bool bCodeFull = Code.Len() == UmLobby::CodeLength;
  const bool bAi = Mode == EUmLobbyMode::VsAi;
  auto Btn = [](UUmButton* B, const FText& Label, EUmButtonVariant V, float H, float MinW, bool bEnabled, const TCHAR* Why,
                bool bSelected = false, bool bFocused = false, FName Icon = NAME_None) {
    if (!B) return;
    FUmButtonModel M;
    M.Variant = V;
    M.Label = Label;
    M.HeightSu = H;
    M.MinWidthSu = MinW;
    M.bEnabled = bEnabled;
    if (!bEnabled && Why) M.Reason.Key = FName(Why);
    M.bSelected = bSelected;
    M.bFocused = bFocused;
    M.IconName = Icon;
    M.PadXSu = H <= 32.0f ? 12.0f : 0.0f;
    B->ApplyModel(M);
  };
  // header
  Btn(MenuButton, FText::GetEmpty(), EUmButtonVariant::Normal, 40.0f, 40.0f, true, nullptr, false, false, FName(TEXT("ui-menu")));
  const bool bEn = IsEnglish();
  Btn(LangRu, UmLbS(TEXT("screens.login.lang.ru")), EUmButtonVariant::Normal, 32.0f, 48.0f, true, nullptr, !bEn);
  Btn(LangEn, UmLbS(TEXT("screens.login.lang.en")), EUmButtonVariant::Normal, 32.0f, 48.0f, true, nullptr, bEn);
  // the list
  const bool bError = List == EUmLobbyList::Error;
  Btn(RefreshButton, UmLbS(TEXT("common.btn.refresh")), EUmButtonVariant::Normal, 40.0f, 144.0f, true, nullptr);
  UmLbVis(RefreshButton, !bError, true);  // ВР-VS4-SC13-01: the error offers «Повторить» only
  Btn(RetryButton, UmLbS(TEXT("common.btn.retry")), EUmButtonVariant::Normal, 40.0f, 160.0f, true, nullptr);
  UmLbVis(RetryButton, bError, true);
  UmLbVis(ErrorIcon, bError);
  UmLbVis(ErrorText, bError);
  const bool bEmpty = List == EUmLobbyList::Empty;
  UmLbVis(EmptyIcon, bEmpty);
  UmLbVis(EmptyText, bEmpty);
  UmLbVis(RowsScroll, List == EUmLobbyList::List, true);
  // create: the one primary unless six code characters are typed (ВР-VS4-SC11-02)
  // busy: the chips and tiles keep their state (ВР-VS4-SC09-01); a press on them waits (OnPressOutcome)
  Btn(ModeChip1v1, UmLbS(TEXT("screens.lobby.create.mode.1v1")), EUmButtonVariant::Normal, 32.0f, 48.0f, true, nullptr, !bAi);
  Btn(ModeChipAi, UmLbS(TEXT("screens.lobby.create.mode.ai")), EUmButtonVariant::Normal, 32.0f, 100.0f, true, nullptr, bAi);
  UmLbVis(CreateNote, bAi && !(bClassS && bCreateError));
  const FText CreateLabel = bCreateBusy ? UmLbS(TEXT("screens.lobby.create.busy")) : UmLbS(TEXT("screens.lobby.create.submit"));
  Btn(CreateButton, CreateLabel, bCodeFull ? EUmButtonVariant::Normal : EUmButtonVariant::Primary, 48.0f, 120.0f,
      !bCreateBusy && !bJoinBusy, TEXT("why.syncing"));
  UmLbVis(CreateError, bCreateError && !bCreateBusy);
  // code
  Btn(CodeJoinButton, UmLbS(TEXT("screens.lobby.code.submit")), bCodeFull ? EUmButtonVariant::Primary : EUmButtonVariant::Normal, 48.0f, 120.0f,
      bCodeFull && !bJoinBusy && !bCreateBusy, bCodeFull ? TEXT("why.syncing") : TEXT("why.code.length"), false,
      bCodeFull && bCodeKeyboard && CodeErr == EUmCodeError::None);
  const bool bCodeErr = CodeErr != EUmCodeError::None;
  if (CodeError) {
    if (bCodeErr) {
      CodeError->SetText(UmLbS(CodeErr == EUmCodeError::Full ? TEXT("screens.lobby.code.error.full") : TEXT("screens.lobby.code.error.notfound")));
      CodeError->SetColorAndOpacity(FSlateColor(UUmHudTheme::Get().Color(TEXT("text.primary"))));
    } else {
      // the why of the disabled «Войти» shows in the error zone (as SC-06 empty, ВР-VS4-SC08-08)
      CodeError->SetText(UmText::Get(EUmTable::Why, TEXT("why.code.length")));
      CodeError->SetColorAndOpacity(FSlateColor(UUmHudTheme::Get().Color(TEXT("text.secondary"))));
    }
    UmLbVis(CodeError, bCodeErr || !bCodeFull);
  }
  UmLbVis(CodeErrorIcon, bCodeErr);
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  const float PxPerSuNow = UmHudScale::Current().PxPerSu();
  const bool bBoxFocus = CodeBox && CodeBox->HasKeyboardFocus();
  for (int32 I = 0; I < CellBoxes.Num(); ++I) {
    const bool bFilled = I < Code.Len();
    const bool bFocusCell = bBoxFocus && I == FMath::Min(Code.Len(), UmLobby::CodeLength - 1) && !bCodeFull;
    if (const FSlateBrush* Skin = Theme.SkinFor(bFocusCell ? TEXT("input.focus") : TEXT("input.normal"), PxPerSuNow)) CellBoxes[I]->SetBrush(*Skin);
    if (CellChars[I]) CellChars[I]->SetText(bFilled ? FText::FromString(Code.Mid(I, 1)) : FText::GetEmpty());
    UmLbVis(CellLines[I], !bFilled);
  }
  Btn(RecoverButton, UmLbS(TEXT("screens.lobby.recover")), EUmButtonVariant::Normal, 40.0f, 120.0f, !IsBusy(), TEXT("why.syncing"));
  UmLbVis(RecoverButton, bRecover, true);
  // busy: the spinner after 300 ms (HB-47)
  if (CreateSpinner) CreateSpinner->SetWaiting(bCreateBusy, FPlatformTime::Seconds() * 1000.0, TEXT("lobby.create"));
  SetScreenState(FName(UmLobby::StateName(List, bCreateTouched || bCreateBusy, Code.Len(), CodeErr)));
}

// ------------------------------------------------------------------------------------------------ input

void UUmScreenLobby::Sound(const TCHAR* Bank) const {
  if (Input.OnSound) Input.OnSound(FName(Bank));
}

void UUmScreenLobby::SetInput(const TSharedPtr<FS09HudPressArbiter>& InArbiter, FInput InInput) {
  Arbiter = InArbiter;
  Input = MoveTemp(InInput);
  TWeakObjectPtr<UUmScreenLobby> WeakThis(this);
  auto Bind = [&WeakThis, this](UUmButton* B, const TCHAR* Id) {
    if (!B) return;
    const FName Name(Id);
    B->SetPress(Name, Arbiter, FS09OnHudPressOutcome::CreateLambda([WeakThis, Name](const FS09HudPressOutcome& O) {
      if (UUmScreenLobby* Self = WeakThis.Get()) Self->OnPressOutcome(Name, O);
    }));
  };
  Bind(MenuButton, TEXT("screens.lobby.menu"));
  Bind(LangRu, TEXT("screens.login.lang.ru"));
  Bind(LangEn, TEXT("screens.login.lang.en"));
  Bind(RefreshButton, TEXT("common.btn.refresh"));
  Bind(RetryButton, TEXT("common.btn.retry"));
  Bind(ModeChip1v1, TEXT("screens.lobby.create.mode.1v1"));
  Bind(ModeChipAi, TEXT("screens.lobby.create.mode.ai"));
  Bind(CreateButton, TEXT("screens.lobby.create.submit"));
  Bind(CodeJoinButton, TEXT("screens.lobby.code.submit"));
  Bind(RecoverButton, TEXT("screens.lobby.recover"));
  for (int32 I = 0; I < Boards.Num(); ++I) {
    const FName Name(*FString::Printf(TEXT("screens.lobby.board.%d"), I));
    Boards[I]->SetPress(Name, Arbiter, FS09OnHudPressOutcome::CreateLambda([WeakThis, Name](const FS09HudPressOutcome& O) {
      if (UUmScreenLobby* Self = WeakThis.Get()) Self->OnPressOutcome(Name, O);
    }));
  }
  for (int32 I = 0; I < RowPool.Num(); ++I) BindRowPress(RowPool[I], I);
}

void UUmScreenLobby::BindRowPress(UUmLobbyGameRow* Row, int32 Index) {
  if (!Row) return;
  TWeakObjectPtr<UUmScreenLobby> WeakThis(this);
  const FName Name(*FString::Printf(TEXT("screens.lobby.row.join.%d"), Index));
  Row->SetPress(Name, Arbiter, FS09OnHudPressOutcome::CreateLambda([WeakThis, Name](const FS09HudPressOutcome& O) {
    if (UUmScreenLobby* Self = WeakThis.Get()) Self->OnPressOutcome(Name, O);
  }));
}

void UUmScreenLobby::OnPressOutcome(FName Id, const FS09HudPressOutcome& Outcome) {
  if (Outcome.Result != ES09HudPressResult::Act) return;
  bCodeKeyboard = false;  // a mouse press: no keyboard ring (04 §3.4)
  const FString S = Id.ToString();
  if (S == TEXT("screens.lobby.menu")) {
    Sound(TEXT("UI-BTN-CLICK"));
    if (Input.OnMenu) Input.OnMenu();
  } else if (S == TEXT("screens.login.lang.ru") || S == TEXT("screens.login.lang.en")) {
    Sound(TEXT("UI-TOGGLE"));
    UmText::SetUiLanguage(S.EndsWith(TEXT(".en")) ? TEXT("en") : TEXT("ru"));
    RefreshTexts();
    Layout();
  } else if (S == TEXT("common.btn.refresh") || S == TEXT("common.btn.retry")) {
    Sound(TEXT("UI-BTN-CLICK"));
    if (Input.OnRefresh) Input.OnRefresh();
  } else if (bCreateBusy && (S.StartsWith(TEXT("screens.lobby.create.mode.")) || S.StartsWith(TEXT("screens.lobby.board.")))) {
    // the create in flight keeps its mode and board
  } else if (S == TEXT("screens.lobby.create.mode.1v1") || S == TEXT("screens.lobby.create.mode.ai")) {
    const EUmLobbyMode Next = S.EndsWith(TEXT(".ai")) ? EUmLobbyMode::VsAi : EUmLobbyMode::OneVOne;
    Sound(TEXT("UI-TOGGLE"));
    bCreateTouched = true;
    bCreateError = false;
    Mode = Next;
    Layout();
  } else if (S.StartsWith(TEXT("screens.lobby.board."))) {
    const int32 I = FCString::Atoi(*S.RightChop(20));
    if (Boards.IsValidIndex(I)) {
      Sound(TEXT("UI-TOGGLE"));
      bCreateTouched = true;
      bCreateError = false;
      BoardId = Boards[I]->GetBoardId();
      Layout();
    }
  } else if (S == TEXT("screens.lobby.create.submit")) {
    SubmitCreate();
  } else if (S == TEXT("screens.lobby.code.submit")) {
    SubmitCode();
  } else if (S == TEXT("screens.lobby.recover")) {
    Sound(TEXT("UI-BTN-CLICK"));
    if (Input.OnRecover) Input.OnRecover();
  } else if (S.StartsWith(TEXT("screens.lobby.row.join."))) {
    const int32 I = FCString::Atoi(*S.RightChop(23));
    if (RowModels.IsValidIndex(I) && RowModels[I].Why.IsNone() && !IsBusy()) {
      Sound(TEXT("UI-BTN-CLICK"));
      bJoinBusy = true;
      BusySinceMs = FPlatformTime::Seconds() * 1000.0;
      if (Input.OnJoinRow) Input.OnJoinRow(RowModels[I].GameId);
    }
  }
  Refresh();
}

void UUmScreenLobby::SubmitCreate() {
  if (IsBusy()) return;  // a repeat waits for the answer: one room per intent (idempotencyKey, 04 §1.3)
  bCreateBusy = true;
  bCreateTouched = true;
  bCreateError = false;
  BusySinceMs = FPlatformTime::Seconds() * 1000.0;
  ++CreateCount;
  Sound(TEXT("UI-BTN-CLICK"));
  Refresh();
  Layout();
  if (Input.OnCreate) Input.OnCreate(Mode, BoardId);
}

void UUmScreenLobby::SubmitCode() {
  const FString Code = GetCode();
  if (Code.Len() != UmLobby::CodeLength || IsBusy()) return;
  bJoinBusy = true;
  CodeErr = EUmCodeError::None;
  BusySinceMs = FPlatformTime::Seconds() * 1000.0;
  Sound(TEXT("UI-BTN-CLICK"));
  Refresh();
  if (Input.OnJoinCode) Input.OnJoinCode(Code);
}

void UUmScreenLobby::SimulatePress(FName Id) {
  if (!Arbiter.IsValid()) Arbiter = MakeShared<FS09HudPressArbiter>();
  Arbiter->Press(Id, Arbiter->Now());
  OnPressOutcome(Id, FS09HudPressArbiter::Decide(Arbiter->Release(Id, Arbiter->Now()), FS09Reason()));
}

void UUmScreenLobby::SetCodeText(const FString& Typed, bool bKeyboard) {
  if (!CodeBox) return;
  bCodeKeyboard = bKeyboard;
  CodeBox->SetText(FText::FromString(UmLobby::NormalizeCode(Typed)));
  HandleCodeChanged(CodeBox->GetText());
}

void UUmScreenLobby::HandleCodeChanged(const FText& Text) {
  if (bSettingCode || !CodeBox) return;
  const FString Norm = UmLobby::NormalizeCode(Text.ToString());
  if (Norm != Text.ToString()) {
    bSettingCode = true;
    CodeBox->SetText(FText::FromString(Norm));
    bSettingCode = false;
  }
  if (CodeBox->HasKeyboardFocus()) bCodeKeyboard = true;
  CodeErr = EUmCodeError::None;  // typing clears a shown error (the next join gives a fresh answer)
  Layout();
  Refresh();
}

void UUmScreenLobby::HandleCodeCommitted(const FText& /*Text*/, ETextCommit::Type Method) {
  if (Method == ETextCommit::OnEnter) SubmitCode();
}

void UUmScreenLobby::StepLobby() {
  const double Now = FPlatformTime::Seconds() * 1000.0;
  if (Skeleton) Skeleton->SetWaiting(List == EUmLobbyList::Loading, Now, TEXT("lobby.list"));
  if (CreateSpinner) CreateSpinner->SetWaiting(bCreateBusy, Now, TEXT("lobby.create"));
  // the focused cell follows the box's keyboard focus
  const bool bFocus = CodeBox && CodeBox->HasKeyboardFocus();
  if (bFocus != bLastCodeFocus) {
    bLastCodeFocus = bFocus;
    Refresh();
  }
}

void UUmScreenLobby::NativeTick(const FGeometry& MyGeometry, float InDeltaTime) {
  Super::NativeTick(MyGeometry, InDeltaTime);
  if (IsShown()) StepLobby();
}

FString UUmScreenLobby::ShotExtra() const {
  return FString::Printf(TEXT(" list=%s rows=%d unavailable=%d mode=%s board=%s busy=%d code=%d codeError=%s recover=%d primary=%s lang=%s"),
                         UmLobby::ListName(List), RowModels.Num(), GetUnavailableCount(), Mode == EUmLobbyMode::VsAi ? TEXT("ai") : TEXT("1v1"),
                         BoardId == UmLobby::SarpedonId ? TEXT("sarpedon") : TEXT("marmoreal"), IsBusy() ? 1 : 0, GetCode().Len(),
                         UmLobby::CodeErrorName(CodeErr), bRecover ? 1 : 0, IsCodeJoinPrimary() ? TEXT("code") : TEXT("create"),
                         IsEnglish() ? TEXT("en") : TEXT("ru"));
}
