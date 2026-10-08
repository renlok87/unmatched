// VS-7 SC-03...SC-05: BOOT - see UmScreenBoot.h.
#include "UmScreenBoot.h"

#include "../S08AnimatedIconWidget.h"
#include "../S08IconMotion.h"
#include "UmButton.h"
#include "UmGameHud.h"
#include "UmHudScale.h"
#include "UmHudTheme.h"
#include "UmProgressBar.h"
#include "UmSpinner.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/Image.h"
#include "Components/NamedSlot.h"
#include "Components/TextBlock.h"
#include "Dom/JsonObject.h"
#include "Framework/Application/SlateApplication.h"
#include "Fonts/FontMeasure.h"
#include "InputCoreTypes.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

const TCHAR* const UUmScreenBoot::WidgetBlueprintPath = TEXT("/Game/S08/UI/Screens/WBP_UI_SCR_BOOT");

UClass* UUmScreenBoot::WidgetClass() { return UmGameHudSlots::WbpOrNative(UUmScreenBoot::StaticClass(), WidgetBlueprintPath); }

// ------------------------------------------------------------------------------------------------ the model

namespace UmBoot {
int32 DoneOf(const FUmBootModel& M) {
  switch (M.Stage) {
    case EUmBootStage::Session: return 0;
    case EUmBootStage::Heroes: return M.bHeroesLoaded ? 2 : 1;
    case EUmBootStage::Boards: return 2;
    default: return 3;
  }
}

FString CaptionKey(const FUmBootModel& M) {
  switch (M.Stage) {
    case EUmBootStage::Session: return TEXT("screens.boot.stage.session");
    case EUmBootStage::Heroes: return M.bHeroesLoaded ? TEXT("screens.boot.stage.heroes") : TEXT("screens.boot.stage.heroes.wait");
    default: return TEXT("screens.boot.stage.boards");  // boards and the 3/3 moment before the resume check answers
  }
}

FText Caption(const FUmBootModel& M) {
  const FString Key = CaptionKey(M);
  if (Key == TEXT("screens.boot.stage.heroes")) {
    FFormatNamedArguments Args;
    Args.Add(TEXT("n"), FText::AsNumber(M.Heroes));
    Args.Add(TEXT("total"), FText::AsNumber(M.HeroesTotal > 0 ? M.HeroesTotal : M.Heroes));
    return UmText::Format(EUmTable::Screens, Key, Args);
  }
  return UmText::Get(EUmTable::Screens, Key);
}

const TCHAR* StageName(EUmBootStage Stage) {
  switch (Stage) {
    case EUmBootStage::Session: return TEXT("session");
    case EUmBootStage::Heroes: return TEXT("heroes");
    case EUmBootStage::Boards: return TEXT("boards");
    default: return TEXT("done");
  }
}

const TCHAR* StateName(const FUmBootModel& M) {
  if (M.bResume) return TEXT("resume");
  return M.bError ? TEXT("error") : TEXT("loading");
}

bool TimedOut(double StartMs, double NowMs) { return StartMs >= 0.0 && NowMs - StartMs >= StageTimeoutMs; }

FString CommitFromStamp(const FString& StampJson) {
  TSharedPtr<FJsonObject> Root;
  const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(StampJson);
  FString Commit;
  if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid() || !Root->TryGetStringField(TEXT("commit"), Commit)) {
    return FString();
  }
  Commit.TrimStartAndEndInline();
  return Commit.Len() >= 8 ? Commit.Left(8) : FString();
}

namespace {
FString ReadTrimmed(const FString& File) {
  FString Text;
  if (!FFileHelper::LoadFileToString(Text, *File)) return FString();
  Text.TrimStartAndEndInline();
  return Text;
}

FString GitHeadCommit() {
  // the repository of the project (unreal/Unmatched -> the checkout root); a worktree's .git is a file "gitdir: <dir>"
  const FString Checkout = FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectDir(), TEXT("../..")));
  FString GitDir = FPaths::Combine(Checkout, TEXT(".git"));
  if (!FPaths::DirectoryExists(GitDir)) {
    const FString Pointer = ReadTrimmed(GitDir);
    if (!Pointer.StartsWith(TEXT("gitdir:"))) return FString();
    GitDir = Pointer.RightChop(7).TrimStartAndEnd();
  }
  FString CommonDir = GitDir;
  const FString Common = ReadTrimmed(FPaths::Combine(GitDir, TEXT("commondir")));
  if (!Common.IsEmpty()) CommonDir = FPaths::ConvertRelativePathToFull(FPaths::Combine(GitDir, Common));
  const FString Head = ReadTrimmed(FPaths::Combine(GitDir, TEXT("HEAD")));
  if (!Head.StartsWith(TEXT("ref:"))) return Head.Len() >= 8 ? Head.Left(8) : FString();
  const FString Ref = Head.RightChop(4).TrimStartAndEnd();
  for (const FString& Dir : {GitDir, CommonDir}) {
    const FString Sha = ReadTrimmed(FPaths::Combine(Dir, Ref));
    if (Sha.Len() >= 8) return Sha.Left(8);
  }
  TArray<FString> Packed;
  FFileHelper::LoadFileToStringArray(Packed, *FPaths::Combine(CommonDir, TEXT("packed-refs")));
  for (const FString& Line : Packed) {
    if (Line.EndsWith(TEXT(" ") + Ref) && Line.Len() >= 8) return Line.Left(8);
  }
  return FString();
}
}  // namespace

FString BuildCommit() {
  // a staged build: tools/s08/package-client.ps1 writes BuildStamp.json next to the root exe
  const FString Stamp = ReadTrimmed(FPaths::Combine(FPaths::RootDir(), TEXT("BuildStamp.json")));
  const FString FromStamp = Stamp.IsEmpty() ? FString() : CommitFromStamp(Stamp);
  return FromStamp.IsEmpty() ? GitHeadCommit() : FromStamp;
}

FVector2D WordmarkBar(const FVector2D& CanvasSu, bool bClassS) {
  // 04 §1.1: 1080p y 400 / 500, 720p (canvas 1706.67 x 960) y 356 / 448; 150 % canvases: the 1080p offsets
  if (!bClassS && FMath::IsNearlyEqual(CanvasSu.Y, 960.0, 1.0)) return FVector2D(356.0, 448.0);
  const double C = 0.5 * CanvasSu.Y;
  return FVector2D(C + WordmarkFromCentreSu, C + BarFromCentreSu);
}
}  // namespace UmBoot

// ------------------------------------------------------------------------------------------------ helpers

namespace {
template <typename T>
T* UmBtFind(UWidgetTree* Tree, const TCHAR* Name) {
  return Tree ? Cast<T>(Tree->FindWidget(FName(Name))) : nullptr;
}

void UmBtText(UTextBlock* T, const TCHAR* Type, const TCHAR* Color) {
  if (!T) return;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  T->SetFont(Theme.Font(FName(Type)));
  T->SetColorAndOpacity(FSlateColor(Theme.Color(FName(Color))));
  T->SetShadowOffset(FVector2D::ZeroVector);
}

UCanvasPanelSlot* UmBtPlace(UWidget* W, const FVector2D& Pos, const FVector2D& Size, bool bAutoSize = false) {
  UCanvasPanelSlot* S = W ? Cast<UCanvasPanelSlot>(W->Slot) : nullptr;
  if (!S) return nullptr;
  S->SetAnchors(FAnchors(0.0f, 0.0f));
  S->SetAlignment(FVector2D::ZeroVector);
  S->SetAutoSize(bAutoSize);
  S->SetPosition(Pos);
  if (!bAutoSize) S->SetSize(Size);
  return S;
}

/** The measured size (su) of a text in a font token (Slate's measure; a rough estimate without Slate). */
FVector2D UmBtMeasure(const FText& Text, const TCHAR* Type) {
  const FSlateFontInfo Font = UUmHudTheme::Get().Font(FName(Type));
  if (FSlateApplication::IsInitialized()) {
    const TSharedRef<FSlateFontMeasure> Measure = FSlateApplication::Get().GetRenderer()->GetFontMeasureService();
    return Measure->Measure(Text, Font, 1.0f);
  }
  return FVector2D(0.55 * Font.Size * 96.0 / 72.0 * Text.ToString().Len(), Font.Size * 96.0 / 72.0 * 1.2);
}

void UmBtFill(UWidget* W) {
  if (UCanvasPanelSlot* S = W ? Cast<UCanvasPanelSlot>(W->Slot) : nullptr) {
    S->SetAnchors(FAnchors(0.0f, 0.0f, 1.0f, 1.0f));
    S->SetOffsets(FMargin(0.0f));
  }
}

UPanelWidget* UmBtBody(UWidgetTree& Tree, FString* OutError) {
  UNamedSlot* BodyW = Cast<UNamedSlot>(Tree.FindWidget(FName(TEXT("Body"))));
  if (!BodyW && OutError) *OutError = TEXT("no Body");
  return BodyW;
}
}  // namespace

// ------------------------------------------------------------------------------------------------ the resume modal

bool UUmBootResume::AttachContent(UWidgetTree& Tree, UPanelWidget* Parent, FS08AttachWidget Attach, FString* OutError) {
  auto Fail = [OutError](const TCHAR* What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), What);
    return false;
  };
  UCanvasPanel* ContentW = Tree.ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Content")));
  ContentW->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  if (!Attach(ContentW, Parent)) return Fail(TEXT("Content"));
  for (const TCHAR* Name : {TEXT("ResumeTitle"), TEXT("ResumeLine"), TEXT("ResumeWhy")}) {
    UTextBlock* T = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(Name));
    T->SetVisibility(ESlateVisibility::HitTestInvisible);
    if (!Attach(T, ContentW)) return Fail(Name);
  }
  UClass* ButtonClass = UmGameHudSlots::WbpOrNative(UUmButton::StaticClass(), UUmButton::WidgetBlueprintPath);
  for (const TCHAR* Name : {TEXT("LobbyButton"), TEXT("ResumeButton")}) {
    if (!Attach(Tree.ConstructWidget<UUmButton>(ButtonClass, FName(Name)), ContentW)) return Fail(Name);
  }
  if (!Attach(Tree.ConstructWidget<UUmSpinner>(UUmSpinner::WidgetClass(), FName(TEXT("ResumeSpinner"))), ContentW)) {
    return Fail(TEXT("ResumeSpinner"));
  }
  return true;
}

bool UUmBootResume::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  if (!UUmScreenBase::BuildDefaultTree(Tree, Attach, OutError)) return false;
  UPanelWidget* BodyW = UmBtBody(Tree, OutError);
  return BodyW && AttachContent(Tree, BodyW, Attach, OutError);
}

void UUmBootResume::BuildContent() {
  if (!WidgetTree || !Body || Body->GetContent()) return;
  FString Error;
  if (!AttachContent(*WidgetTree, Body, [](UWidget* Child, UPanelWidget* Parent) { return Parent && Parent->AddChild(Child) != nullptr; },
                     &Error)) {
    UE_LOG(LogTemp, Error, TEXT("UMHUD boot resume content: %s"), *Error);
  }
}

void UUmBootResume::BindParts() {
  Content = UmBtFind<UCanvasPanel>(WidgetTree, TEXT("Content"));
  ResumeTitle = UmBtFind<UTextBlock>(WidgetTree, TEXT("ResumeTitle"));
  ResumeLine = UmBtFind<UTextBlock>(WidgetTree, TEXT("ResumeLine"));
  ResumeWhy = UmBtFind<UTextBlock>(WidgetTree, TEXT("ResumeWhy"));
  LobbyButton = UmBtFind<UUmButton>(WidgetTree, TEXT("LobbyButton"));
  ResumeButton = UmBtFind<UUmButton>(WidgetTree, TEXT("ResumeButton"));
  ResumeSpinner = UmBtFind<UUmSpinner>(WidgetTree, TEXT("ResumeSpinner"));
}

bool UUmBootResume::Initialize() {
  const bool bFirst = Super::Initialize();
  if (!bFirst || !WidgetTree) return bFirst;
  BindParts();
  // ВР-VS4-SC03-06: the screen's veil is the only one - this modal's veil stays clear (it still takes the pointer)
  if (Veil) {
    FLinearColor Clear = UUmHudTheme::Get().Color(TEXT("panel.veil"));
    Clear.A = 0.0f;
    Veil->SetColorAndOpacity(Clear);
  }
  UmBtText(ResumeTitle, TEXT("type.title"), TEXT("text.primary"));
  UmBtText(ResumeLine, TEXT("type.body"), TEXT("text.primary"));
  UmBtText(ResumeWhy, TEXT("type.caption"), TEXT("text.secondary"));
  if (ResumeLine) ResumeLine->SetAutoWrapText(true);
  if (ResumeTitle) ResumeTitle->SetText(UmText::Get(EUmTable::Screens, TEXT("screens.boot.resume.title")));
  if (ResumeWhy) ResumeWhy->SetText(UmText::Get(EUmTable::Why, TEXT("why.syncing")));
  if (ResumeSpinner) ResumeSpinner->SetSizeSu(UmLoader::SpinnerSmallSu);
  SetFrameSize(FVector2D(UmBoot::ResumeWSu, UmBoot::ResumeHSu));
  return bFirst;
}

bool UUmBootResume::HasAllParts(FString* OutMissing) const {
  FString Base;
  HasBaseParts(&Base);
  TArray<FString> Missing;
  if (!Base.IsEmpty()) Missing.Add(Base);
  if (!ResumeTitle) Missing.Add(TEXT("ResumeTitle"));
  if (!ResumeLine) Missing.Add(TEXT("ResumeLine"));
  if (!LobbyButton) Missing.Add(TEXT("LobbyButton"));
  if (!ResumeButton) Missing.Add(TEXT("ResumeButton"));
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

void UUmBootResume::ApplyCanvas(const FVector2D& InCanvasSu, bool bInClassS, float InPxPerSu) {
  SetCanvas(InCanvasSu, bInClassS, InPxPerSu);
  Layout();
}

void UUmBootResume::Layout() {
  const float P = UmBoot::ResumePadSu;
  const float W = UmBoot::ResumeWSu - 2.0f * P;
  UmBtPlace(ResumeTitle, FVector2D(P, P), FVector2D(W, 32.0f));
  UmBtPlace(ResumeLine, FVector2D(P, UmBoot::ResumeLineYSu), FVector2D(W + 0.0f, 44.0f));  // 608 x 44: two lines at most
  UmBtPlace(LobbyButton, FVector2D(P, UmBoot::ResumeButtonsYSu), FVector2D(UmBoot::ResumeLobbyWSu, UmBoot::RetryHSu));
  const float ReturnX = UmBoot::ResumeWSu - P - UmBoot::ResumeReturnWSu;
  UmBtPlace(ResumeButton, FVector2D(ReturnX, UmBoot::ResumeButtonsYSu), FVector2D(UmBoot::ResumeReturnWSu, UmBoot::RetryHSu));
  // ВР-VS4-SC03-07: the spinner inside the button left of the label (38 su in, centred on the button's height)
  const FText Label = ResumeButton ? FText::FromString(ResumeButton->GetModel().Label.ToString().ToUpper()) : FText();
  const float LabelW = static_cast<float>(UmBtMeasure(Label, TEXT("type.button")).X);
  UmBtPlace(ResumeSpinner, FVector2D(ReturnX + 0.5f * (UmBoot::ResumeReturnWSu - LabelW) - 8.0f - 32.0f, UmBoot::ResumeButtonsYSu + 8.0f),
            FVector2D(32.0f, 32.0f));
  UmBtPlace(ResumeWhy, FVector2D(ReturnX, UmBoot::ResumeButtonsYSu + UmBoot::RetryHSu + UmBoot::WhyGapSu), FVector2D(0, 0), true);
}

void UUmBootResume::ApplyModel(const FUmBootModel& M) {
  if (ResumeLine) {
    FFormatNamedArguments Args;
    Args.Add(TEXT("hero"), FText::FromString(M.ResumeHero));          // database names, nominative (ВР-SC10)
    Args.Add(TEXT("opponent"), FText::FromString(M.ResumeOpponent));
    Args.Add(TEXT("board"), FText::FromString(M.ResumeBoard));
    ResumeLine->SetText(UmText::Format(EUmTable::Screens, TEXT("screens.boot.resume.line"), Args));
  }
  if (LobbyButton) {
    FUmButtonModel B;
    B.Variant = EUmButtonVariant::Normal;
    B.Label = UmText::Get(EUmTable::Screens, TEXT("screens.boot.resume.lobby"));
    B.HeightSu = UmBoot::RetryHSu;
    B.MinWidthSu = UmBoot::ResumeLobbyWSu;
    LobbyButton->ApplyModel(B);
  }
  if (ResumeButton) {
    FUmButtonModel B;
    B.Variant = EUmButtonVariant::Primary;  // the one primary of the modal
    B.Label = UmText::Get(EUmTable::Screens, TEXT("screens.boot.resume.return"));
    B.HeightSu = UmBoot::RetryHSu;
    B.MinWidthSu = UmBoot::ResumeReturnWSu;
    B.bEnabled = !M.bResuming;
    if (M.bResuming) B.Reason.Key = FName(TEXT("why.syncing"));
    ResumeButton->ApplyModel(B);
  }
  Layout();  // the spinner follows the label's width
  if (ResumeSpinner) ResumeSpinner->SetWaiting(M.bResuming, FPlatformTime::Seconds() * 1000.0, TEXT("boot.resume"));
  if (ResumeWhy) ResumeWhy->SetVisibility(M.bResuming ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
}

// ------------------------------------------------------------------------------------------------ the screen

bool UUmScreenBoot::AttachContent(UWidgetTree& Tree, UPanelWidget* Parent, FS08AttachWidget Attach, FString* OutError) {
  auto Fail = [OutError](const TCHAR* What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), What);
    return false;
  };
  UCanvasPanel* ContentW = Tree.ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Content")));
  ContentW->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  if (!Attach(ContentW, Parent)) return Fail(TEXT("Content"));
  UTextBlock* WordW = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("Wordmark")));
  if (!Attach(WordW, ContentW)) return Fail(TEXT("Wordmark"));
  if (!Attach(Tree.ConstructWidget<UUmProgressBar>(UUmProgressBar::StaticClass(), FName(TEXT("Progress"))), ContentW)) {
    return Fail(TEXT("Progress"));
  }
  UBorder* CapsuleW = Tree.ConstructWidget<UBorder>(UBorder::StaticClass(), FName(TEXT("StageCapsule")));
  if (!Attach(CapsuleW, ContentW)) return Fail(TEXT("StageCapsule"));
  if (!Attach(Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("StageText"))), CapsuleW)) return Fail(TEXT("StageText"));
  if (!Attach(Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("BuildText"))), ContentW)) return Fail(TEXT("BuildText"));
  UBorder* BannerW = Tree.ConstructWidget<UBorder>(UBorder::StaticClass(), FName(TEXT("ErrorBanner")));
  if (!Attach(BannerW, ContentW)) return Fail(TEXT("ErrorBanner"));
  UCanvasPanel* RowW = Tree.ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("ErrorRow")));
  if (!Attach(RowW, BannerW)) return Fail(TEXT("ErrorRow"));
  if (!Attach(Tree.ConstructWidget<US08AnimatedIconWidget>(US08AnimatedIconWidget::StaticClass(), FName(TEXT("ErrorIcon"))), RowW)) {
    return Fail(TEXT("ErrorIcon"));
  }
  if (!Attach(Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("ErrorText"))), RowW)) return Fail(TEXT("ErrorText"));
  UClass* ButtonClass = UmGameHudSlots::WbpOrNative(UUmButton::StaticClass(), UUmButton::WidgetBlueprintPath);
  if (!Attach(Tree.ConstructWidget<UUmButton>(ButtonClass, FName(TEXT("RetryButton"))), RowW)) return Fail(TEXT("RetryButton"));
  if (!Attach(Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("WhyText"))), RowW)) return Fail(TEXT("WhyText"));
  return true;
}

bool UUmScreenBoot::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  if (!UUmScreenBase::BuildDefaultTree(Tree, Attach, OutError)) return false;
  UPanelWidget* BodyW = UmBtBody(Tree, OutError);
  if (!BodyW || !AttachContent(Tree, BodyW, Attach, OutError)) return false;
  // SC-05: the resume modal over the whole canvas (a sibling of the frame in Root)
  UCanvasPanel* RootW = Cast<UCanvasPanel>(Tree.FindWidget(FName(TEXT("Root"))));
  UUmBootResume* ResumeW = Tree.ConstructWidget<UUmBootResume>(UUmBootResume::StaticClass(), FName(TEXT("ResumeModal")));
  if (!RootW || !Attach(ResumeW, RootW)) {
    if (OutError) *OutError = TEXT("attach failed: ResumeModal");
    return false;
  }
  UmBtFill(ResumeW);
  return true;
}

void UUmScreenBoot::BuildContent() {
  if (!WidgetTree || !Body || Body->GetContent()) return;
  FString Error;
  auto AddTo = [](UWidget* Child, UPanelWidget* Parent) { return Parent && Parent->AddChild(Child) != nullptr; };
  if (!AttachContent(*WidgetTree, Body, AddTo, &Error)) UE_LOG(LogTemp, Error, TEXT("UMHUD boot content: %s"), *Error);
  if (Root && !WidgetTree->FindWidget(FName(TEXT("ResumeModal")))) {
    UUmBootResume* ResumeW = WidgetTree->ConstructWidget<UUmBootResume>(UUmBootResume::StaticClass(), FName(TEXT("ResumeModal")));
    if (Root->AddChild(ResumeW)) UmBtFill(ResumeW);
  }
}

void UUmScreenBoot::BindParts() {
  Content = UmBtFind<UCanvasPanel>(WidgetTree, TEXT("Content"));
  Wordmark = UmBtFind<UTextBlock>(WidgetTree, TEXT("Wordmark"));
  Progress = UmBtFind<UUmProgressBar>(WidgetTree, TEXT("Progress"));
  StageCapsule = UmBtFind<UBorder>(WidgetTree, TEXT("StageCapsule"));
  StageText = UmBtFind<UTextBlock>(WidgetTree, TEXT("StageText"));
  BuildText = UmBtFind<UTextBlock>(WidgetTree, TEXT("BuildText"));
  ErrorBanner = UmBtFind<UBorder>(WidgetTree, TEXT("ErrorBanner"));
  ErrorIcon = UmBtFind<US08AnimatedIconWidget>(WidgetTree, TEXT("ErrorIcon"));
  ErrorText = UmBtFind<UTextBlock>(WidgetTree, TEXT("ErrorText"));
  RetryButton = UmBtFind<UUmButton>(WidgetTree, TEXT("RetryButton"));
  WhyText = UmBtFind<UTextBlock>(WidgetTree, TEXT("WhyText"));
  ResumeModal = UmBtFind<UUmBootResume>(WidgetTree, TEXT("ResumeModal"));
}

bool UUmScreenBoot::Initialize() {
  const bool bFirst = Super::Initialize();
  if (!bFirst || !WidgetTree) return bFirst;
  SetUiId(TEXT("UI-SCR-BOOT"));
  SetScreenState(FName(TEXT("loading")));
  BindParts();
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  UmBtText(Wordmark, TEXT("type.display"), TEXT("text.primary"));
  UmBtText(StageText, TEXT("type.body"), TEXT("text.secondary"));
  UmBtText(BuildText, TEXT("type.caption"), TEXT("text.secondary"));
  UmBtText(ErrorText, TEXT("type.body"), TEXT("text.primary"));
  UmBtText(WhyText, TEXT("type.caption"), TEXT("text.secondary"));
  if (Wordmark) {
    Wordmark->SetText(UmText::Get(EUmTable::Screens, TEXT("screens.boot.title")));  // ВР-H19: plain text, no logo image
    Wordmark->SetJustification(ETextJustify::Center);
  }
  if (StageText) StageText->SetJustification(ETextJustify::Center);
  if (StageCapsule) {
    if (const FSlateBrush* Skin = Theme.Skin(TEXT("capsule"))) StageCapsule->SetBrush(*Skin);
    StageCapsule->SetPadding(FMargin(UmBoot::CaptionPadXSu, UmBoot::CaptionPadYSu));
    StageCapsule->SetHorizontalAlignment(HAlign_Center);
    StageCapsule->SetVerticalAlignment(VAlign_Center);
    StageCapsule->SetVisibility(ESlateVisibility::HitTestInvisible);
  }
  if (ErrorBanner) {
    if (const FSlateBrush* Skin = Theme.Skin(TEXT("capsule"))) ErrorBanner->SetBrush(*Skin);
    ErrorBanner->SetPadding(FMargin(0.0f));
    ErrorBanner->SetVisibility(ESlateVisibility::Collapsed);
  }
  if (ErrorText) ErrorText->SetText(UmText::Get(EUmTable::Screens, TEXT("screens.boot.error.server")));
  if (WhyText) WhyText->SetText(UmText::Get(EUmTable::Why, TEXT("why.syncing")));
  if (WhyText) WhyText->SetJustification(ETextJustify::Right);
  if (ErrorIcon && ErrorIcon->SetIcon(FName(TEXT("resource-connection-lost")), UmBoot::ErrorIconSu,
                                      S08IconMotion::ExportSizePx(UmBoot::ErrorIconSu, UmHudScale::Current().PxPerSu()))) {
    ErrorIcon->SetDisplaySizeSu(UmBoot::ErrorIconSu);
    ErrorIcon->ShowAtRest();
  }
  if (Progress && Progress->Caption) Progress->Caption->SetVisibility(ESlateVisibility::Collapsed);  // the capsule shows it
  // a full screen: the elements stand on the veil, the frame draws nothing
  if (Frame) Frame->SetBrush(FSlateNoResource());
  return bFirst;
}

bool UUmScreenBoot::HasAllParts(FString* OutMissing) const {
  FString Base;
  HasBaseParts(&Base);
  TArray<FString> Missing;
  if (!Base.IsEmpty()) Missing.Add(Base);
  if (!Wordmark) Missing.Add(TEXT("Wordmark"));
  if (!Progress) Missing.Add(TEXT("Progress"));
  if (!StageText) Missing.Add(TEXT("StageText"));
  if (!BuildText) Missing.Add(TEXT("BuildText"));
  if (!ErrorBanner) Missing.Add(TEXT("ErrorBanner"));
  if (!ErrorIcon) Missing.Add(TEXT("ErrorIcon"));
  if (!ErrorText) Missing.Add(TEXT("ErrorText"));
  if (!RetryButton) Missing.Add(TEXT("RetryButton"));
  FString ResumeMissing;
  if (!ResumeModal) {
    Missing.Add(TEXT("ResumeModal"));
  } else if (!ResumeModal->HasAllParts(&ResumeMissing)) {
    Missing.Add(TEXT("ResumeModal:") + ResumeMissing);
  }
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

void UUmScreenBoot::ApplyCanvas(const FVector2D& InCanvasSu, bool bInClassS, float InPxPerSu) {
  SetCanvas(InCanvasSu, bInClassS, InPxPerSu);
  if (Frame) Frame->SetBrush(FSlateNoResource());  // Relayout put the modal skin back
  if (ResumeModal) ResumeModal->ApplyCanvas(InCanvasSu, bInClassS, InPxPerSu);
  Layout();
}

void UUmScreenBoot::Layout() {
  // canvas su -> the frame's local su (the frame spans the canvas inside the safe margins)
  const FVector2D O = FrameRectSu().Min;
  const FVector2D YY = UmBoot::WordmarkBar(CanvasSu, bClassS);
  const float Cx = 0.5f * CanvasSu.X;
  const float BarX = Cx - 0.5f * UUmProgressBar::WidthSu;
  UmBtPlace(Wordmark, FVector2D(0.0f, YY.X) - FVector2D(0.0f, O.Y), FVector2D(CanvasSu.X - 2.0 * O.X, 60.0f));
  UmBtPlace(Progress, FVector2D(BarX, YY.Y) - O, FVector2D(UUmProgressBar::WidthSu, UUmProgressBar::HeightSu));
  // the caption capsule: width = text + 24 su, <= 600 su, centred, 8 su under the bar (y 516)
  const float CapY = YY.Y + UUmProgressBar::HeightSu + UmBoot::CaptionGapSu;
  const FText Cap = StageText ? StageText->GetText() : FText();
  const float CapW = FMath::Min(600.0f, static_cast<float>(UmBtMeasure(Cap, TEXT("type.body")).X) + 2.0f * UmBoot::CaptionPadXSu);
  UmBtPlace(StageCapsule, FVector2D(Cx - 0.5f * CapW, CapY) - O, FVector2D(CapW, UmBoot::CaptionHSu));
  // the build: bottom right, the safe margin from both edges
  const FText Build = BuildText ? BuildText->GetText() : FText();
  const FVector2D BuildSize = UmBtMeasure(Build, TEXT("type.caption"));
  const float M = GetSafeMarginSu();
  UmBtPlace(BuildText, FVector2D(CanvasSu.X - M - BuildSize.X, CanvasSu.Y - M - BuildSize.Y) - O, BuildSize + FVector2D(2.0, 0.0));
  // SC-04: the error capsule 480 x 104, 16 su under the caption capsule; one row: icon, text, «Повторить» on the right
  const float ErrY = CapY + UmBoot::CaptionHSu + UmBoot::ErrorGapSu;
  UmBtPlace(ErrorBanner, FVector2D(BarX, ErrY) - O, FVector2D(UmBoot::ErrorWSu, UmBoot::ErrorHSu));
  const float P = UmBoot::ErrorPadSu;
  UmBtPlace(ErrorIcon, FVector2D(P, P), FVector2D(UmBoot::ErrorIconSu, UmBoot::ErrorIconSu));
  const float RetryX = UmBoot::ErrorWSu - P - UmBoot::RetryWSu;
  UmBtPlace(ErrorText, FVector2D(P + UmBoot::ErrorIconSu + 12.0f, P + 0.5f * UmBoot::ErrorIconSu - 10.0f),
            FVector2D(RetryX - (P + UmBoot::ErrorIconSu + 12.0f) - 8.0f, 22.0f));
  UmBtPlace(RetryButton, FVector2D(RetryX, P), FVector2D(UmBoot::RetryWSu, UmBoot::RetryHSu));
  UmBtPlace(WhyText, FVector2D(RetryX, P + UmBoot::RetryHSu + UmBoot::WhyGapSu), FVector2D(UmBoot::RetryWSu, 18.0f));
}

void UUmScreenBoot::ApplyModel(const FUmBootModel& InModel, double NowMs) {
  const bool bSame = bHasModel && Model == InModel;
  Model = InModel;
  bHasModel = true;
  if (Progress) {
    Progress->ApplyModel(static_cast<float>(UmBoot::DoneOf(Model)) / 3.0f, UmBoot::Caption(Model), NowMs);
    Progress->SetWaiting(IsShown(), NowMs, TEXT("boot"));
  }
  if (bSame) return;
  if (StageText) StageText->SetText(UmBoot::Caption(Model));
  if (BuildText) {
    FFormatNamedArguments Args;
    Args.Add(TEXT("commit"), FText::FromString(Model.BuildCommit));
    BuildText->SetText(UmText::Format(EUmTable::Screens, TEXT("screens.boot.build"), Args));
    BuildText->SetVisibility(Model.BuildCommit.IsEmpty() ? ESlateVisibility::Collapsed : ESlateVisibility::HitTestInvisible);
  }
  if (ErrorBanner) ErrorBanner->SetVisibility(Model.bError ? ESlateVisibility::SelfHitTestInvisible : ESlateVisibility::Collapsed);
  if (RetryButton) {
    FUmButtonModel B;
    B.Variant = EUmButtonVariant::Primary;  // the one primary of the screen (SC-04)
    B.Label = UmText::Get(EUmTable::Screens, TEXT("common.btn.retry"));
    B.HeightSu = UmBoot::RetryHSu;
    B.MinWidthSu = UmBoot::RetryWSu;
    B.bEnabled = !Model.bRetrying;
    if (Model.bRetrying) B.Reason.Key = FName(TEXT("why.syncing"));
    RetryButton->ApplyModel(B);
  }
  if (WhyText) WhyText->SetVisibility(Model.bError && Model.bRetrying ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
  if (ResumeModal) {
    ResumeModal->ApplyModel(Model);
    if (Model.bResume) {
      ResumeModal->PlayShow();
    } else {
      ResumeModal->PlayHide();
    }
  }
  SetScreenState(FName(UmBoot::StateName(Model)));
  Layout();  // the capsule follows the caption's width
}

void UUmScreenBoot::SetInput(const TSharedPtr<FS09HudPressArbiter>& InArbiter, FInput InInput) {
  Arbiter = InArbiter;
  Input = MoveTemp(InInput);
  TWeakObjectPtr<UUmScreenBoot> WeakThis(this);
  auto Bind = [&WeakThis, this](UUmButton* B, const TCHAR* Id) {
    if (!B) return;
    const FName Name(Id);
    B->SetPress(Name, Arbiter, FS09OnHudPressOutcome::CreateLambda([WeakThis, Name](const FS09HudPressOutcome& O) {
      if (UUmScreenBoot* Self = WeakThis.Get()) Self->OnPressOutcome(Name, O);
    }));
  };
  Bind(RetryButton, TEXT("screens.boot.retry"));
  if (ResumeModal) {
    Bind(ResumeModal->ResumeButton, TEXT("screens.boot.resume"));
    Bind(ResumeModal->LobbyButton, TEXT("screens.boot.lobby"));
  }
}

void UUmScreenBoot::OnPressOutcome(FName Id, const FS09HudPressOutcome& Outcome) {
  if (Outcome.Result != ES09HudPressResult::Act) return;
  const FString S = Id.ToString();
  if (S == TEXT("screens.boot.retry")) {
    if (Model.bError && !Model.bRetrying && Input.OnRetry) Input.OnRetry();
  } else if (S == TEXT("screens.boot.resume")) {
    if (Model.bResume && !Model.bResuming && Input.OnResume) Input.OnResume();
  } else if (S == TEXT("screens.boot.lobby")) {
    if (Model.bResume && Input.OnLobby) Input.OnLobby();
  }
}

void UUmScreenBoot::SimulatePress(FName Id) {
  if (!Arbiter.IsValid()) Arbiter = MakeShared<FS09HudPressArbiter>();
  Arbiter->Press(Id, Arbiter->Now());
  OnPressOutcome(Id, FS09HudPressArbiter::Decide(Arbiter->Release(Id, Arbiter->Now()), FS09Reason()));
}

bool UUmScreenBoot::HandleKey(const FKey& Key) {
  if (!IsShown() || !Model.bResume) return false;
  if (Key == EKeys::Enter) {
    SimulatePress(FName(TEXT("screens.boot.resume")));
    return true;
  }
  if (Key == EKeys::Escape) {
    SimulatePress(FName(TEXT("screens.boot.lobby")));
    return true;
  }
  return false;
}

FString UUmScreenBoot::GetStageText() const { return StageText ? StageText->GetText().ToString() : FString(); }
FString UUmScreenBoot::GetBuildText() const { return BuildText ? BuildText->GetText().ToString() : FString(); }
FString UUmScreenBoot::GetResumeLineText() const {
  return ResumeModal && ResumeModal->ResumeLine ? ResumeModal->ResumeLine->GetText().ToString() : FString();
}
float UUmScreenBoot::GetBarPercent() const { return Progress ? Progress->GetPercent() : 0.0f; }
bool UUmScreenBoot::IsErrorShown() const { return Model.bError && ErrorBanner && ErrorBanner->GetVisibility() != ESlateVisibility::Collapsed; }
bool UUmScreenBoot::IsResumeShown() const { return Model.bResume && ResumeModal && ResumeModal->IsShown(); }

FString UUmScreenBoot::ShotExtra() const {
  return FString::Printf(TEXT(" stage=%s done=%d/3 retrying=%d resuming=%d build=%s"), UmBoot::StageName(Model.Stage),
                         UmBoot::DoneOf(Model), Model.bRetrying ? 1 : 0, Model.bResuming ? 1 : 0,
                         Model.BuildCommit.IsEmpty() ? TEXT("-") : *Model.BuildCommit);
}
