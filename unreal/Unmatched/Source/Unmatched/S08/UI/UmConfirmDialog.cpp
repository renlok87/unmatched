// VS-3 SC-01: the confirm dialog - see UmConfirmDialog.h.
#include "UmConfirmDialog.h"

#include "UmButton.h"
#include "UmGameHud.h"
#include "UmHudTheme.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/NamedSlot.h"
#include "Components/TextBlock.h"

const TCHAR* const UUmConfirmDialog::WidgetBlueprintPath = TEXT("/Game/S08/UI/Common/WBP_UmConfirmDialog");

UClass* UUmConfirmDialog::WidgetClass() {
  return UmGameHudSlots::WbpOrNative(UUmConfirmDialog::StaticClass(), WidgetBlueprintPath);
}

namespace {
void UmDlgPlace(UWidget* W, const FVector2D& Pos, const FVector2D& Size) {
  if (UCanvasPanelSlot* S = W ? Cast<UCanvasPanelSlot>(W->Slot) : nullptr) {
    S->SetAnchors(FAnchors(0.0f, 0.0f));
    S->SetAlignment(FVector2D::ZeroVector);
    S->SetAutoSize(false);
    S->SetPosition(Pos);
    S->SetSize(Size);
  }
}

void UmDlgText(UTextBlock* T, FName Type, FName Color) {
  if (!T) return;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  T->SetFont(Theme.Font(Type));
  T->SetColorAndOpacity(FSlateColor(Theme.Color(Color)));
  T->SetShadowOffset(FVector2D::ZeroVector);
}
}  // namespace

bool UUmConfirmDialog::AttachContent(UWidgetTree& Tree, UPanelWidget* Parent, FS08AttachWidget Attach, FString* OutError) {
  auto Fail = [OutError](const TCHAR* What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), What);
    return false;
  };
  UCanvasPanel* ContentW = Tree.ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Content")));
  if (!Attach(ContentW, Parent)) return Fail(TEXT("Content"));
  UTextBlock* TitleW = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("Title")));
  if (!Attach(TitleW, ContentW)) return Fail(TEXT("Title"));
  UTextBlock* MessageW = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("Message")));
  MessageW->SetAutoWrapText(true);
  if (!Attach(MessageW, ContentW)) return Fail(TEXT("Message"));
  UClass* ButtonClass = UmGameHudSlots::WbpOrNative(UUmButton::StaticClass(), UUmButton::WidgetBlueprintPath);
  for (const TCHAR* Name : {TEXT("Cancel"), TEXT("Confirm")}) {
    UUmButton* B = Tree.ConstructWidget<UUmButton>(ButtonClass, FName(Name));
    if (!Attach(B, ContentW)) return Fail(Name);
  }
  return true;
}

bool UUmConfirmDialog::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  if (!UUmScreenBase::BuildDefaultTree(Tree, Attach, OutError)) return false;
  UNamedSlot* BodyW = Cast<UNamedSlot>(Tree.FindWidget(FName(TEXT("Body"))));
  if (!BodyW) {
    if (OutError) *OutError = TEXT("no Body");
    return false;
  }
  return AttachContent(Tree, BodyW, Attach, OutError);
}

void UUmConfirmDialog::BuildContent() {
  if (!WidgetTree || !Body || Body->GetContent()) return;
  UWidgetTree* Tree = WidgetTree;
  FString Error;
  if (!AttachContent(*Tree, Body, [](UWidget* Child, UPanelWidget* Parent) { return Parent && Parent->AddChild(Child) != nullptr; }, &Error)) {
    UE_LOG(LogTemp, Error, TEXT("UMHUD confirm dialog content: %s"), *Error);
  }
}

bool UUmConfirmDialog::Initialize() {
  const bool bFirst = Super::Initialize();
  if (!bFirst || !WidgetTree) return bFirst;
  Content = Cast<UCanvasPanel>(WidgetTree->FindWidget(FName(TEXT("Content"))));
  Title = Cast<UTextBlock>(WidgetTree->FindWidget(FName(TEXT("Title"))));
  Message = Cast<UTextBlock>(WidgetTree->FindWidget(FName(TEXT("Message"))));
  Confirm = Cast<UUmButton>(WidgetTree->FindWidget(FName(TEXT("Confirm"))));
  Cancel = Cast<UUmButton>(WidgetTree->FindWidget(FName(TEXT("Cancel"))));
  UmDlgText(Title, TEXT("type.title"), TEXT("text.primary"));
  UmDlgText(Message, TEXT("type.body"), TEXT("text.primary"));
  if (Message) Message->SetAutoWrapText(true);
  SetFrameSize(FVector2D(FrameWSu, FrameHSu));
  ApplyContent();
  return bFirst;
}

bool UUmConfirmDialog::HasAllParts(FString* OutMissing) const {
  FString Base;
  HasBaseParts(&Base);
  TArray<FString> Missing;
  if (!Base.IsEmpty()) Missing.Add(Base);
  if (!Title) Missing.Add(TEXT("Title"));
  if (!Message) Missing.Add(TEXT("Message"));
  if (!Confirm) Missing.Add(TEXT("Confirm"));
  if (!Cancel) Missing.Add(TEXT("Cancel"));
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

void UUmConfirmDialog::SetInput(const TSharedPtr<FS09HudPressArbiter>& InArbiter) {
  TWeakObjectPtr<UUmConfirmDialog> WeakThis(this);
  auto Bind = [&InArbiter, WeakThis](UUmButton* B, const TCHAR* Id, bool bConfirm) {
    if (!B) return;
    B->SetPress(FName(Id), InArbiter, FS09OnHudPressOutcome::CreateLambda([WeakThis, bConfirm](const FS09HudPressOutcome& O) {
      if (UUmConfirmDialog* Self = WeakThis.Get()) {
        if (O.Result == ES09HudPressResult::Act) Self->Answer(bConfirm);
      }
    }));
  };
  Bind(Confirm, TEXT("common.confirm.yes"), true);
  Bind(Cancel, TEXT("common.confirm.cancel"), false);
}

void UUmConfirmDialog::ApplyContent() {
  if (Title) Title->SetText(Request.Title);
  if (Message) Message->SetText(Request.Message);
  const FVector2D Size(FrameWSu, FrameHSu);
  // inside the frame: 16 su padding, the title row 36 su (type.title 28), the message under it
  UmDlgPlace(Title, FVector2D(PadSu), FVector2D(Size.X - 2.0f * PadSu, 36.0f));
  UmDlgPlace(Message, FVector2D(PadSu, PadSu + 36.0f + 8.0f), FVector2D(Size.X - 2.0f * PadSu, Size.Y - 3.0f * PadSu - 36.0f - 8.0f - ButtonHSu));
  const float Y = Size.Y - PadSu - ButtonHSu;
  if (Cancel) {
    FUmButtonModel B;
    B.Variant = EUmButtonVariant::Normal;
    B.Label = UmText::Get(EUmTable::Screens, TEXT("common.confirm.cancel"));
    B.HeightSu = ButtonHSu;
    B.MinWidthSu = ButtonWSu;
    Cancel->ApplyModel(B);
    UmDlgPlace(Cancel, FVector2D(Size.X - PadSu - ButtonWSu - PadSu - ButtonWSu, Y), FVector2D(ButtonWSu, ButtonHSu));
  }
  if (Confirm) {
    FUmButtonModel B;
    B.Variant = EUmButtonVariant::Primary;  // the one primary button of the window (04 §3.1)
    B.Label = UmText::Get(EUmTable::Screens, TEXT("common.confirm.yes"));
    B.HeightSu = ButtonHSu;
    B.MinWidthSu = ButtonWSu;
    Confirm->ApplyModel(B);
    UmDlgPlace(Confirm, FVector2D(Size.X - PadSu - ButtonWSu, Y), FVector2D(ButtonWSu, ButtonHSu));
  }
}

void UUmConfirmDialog::Open(FRequest InRequest) {
  Request = MoveTemp(InRequest);
  bAnswered = false;
  SetUiId(Request.OwnerUiId);
  SetScreenState(FName(TEXT("confirm")));
  ApplyContent();
  PlayShow();
}

void UUmConfirmDialog::Answer(bool bConfirm) {
  if (bAnswered || !IsShown()) return;
  bAnswered = true;
  TFunction<void()> Fn = bConfirm ? Request.OnConfirm : Request.OnCancel;
  PlayHide();
  if (Fn) Fn();
}

bool UUmConfirmDialog::HandleEscape() {
  if (!IsShown()) return false;
  Answer(false);
  return true;
}
