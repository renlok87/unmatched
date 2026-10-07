// VS-3 SC-01 UE part (screens.csv SC-01; 04-hud-spec.md §1 «Разрушительное действие всегда через подтверждение»,
// §1.8, §4.3; the accepted mockup art/imagegen/sc01-screen-base-codex «base-modal», ВР-VS3-SC01-01...10): the confirm
// dialog - UUmConfirmDialog (/Game/S08/UI/Common/WBP_UmConfirmDialog), a UUmModalBase.
//
//   layout   the modal 640 x 360 su centred over the veil (the SC-01 base sheet): the title (type.title 28 su) and the
//            message (type.body, wraps) 16 su from the frame's left and top; «Отмена» (common.confirm.cancel, UUmButton
//            Normal) and «Да» (common.confirm.yes, the one Primary of the window) 168 x 48 su at the bottom right, 16 su
//            apart and from the frame.
//   answer   Confirm runs OnConfirm; Cancel, Esc and a click outside the frame (on the veil) run OnCancel (SC-01 do);
//            either closes the dialog (120 ms). A destructive action goes only through it.
//   gate     the dialog belongs to the screen that asked: 'SHOT widget id=<owner UI-ID> state=confirm ...' (ВР-SC11:
//            UI-SCR-PAUSE confirm).
// BindWidget Title, Message, Confirm, Cancel (+ the base Veil, Frame, Body) - 04 §4.3 names the message «Body», which is the
// base's named slot here: the slot holds the dialog's content (ВР-VS3-58).
#pragma once

#include "CoreMinimal.h"
#include "../../S09/S09HudPress.h"
#include "UmScreenBase.h"
#include "UmConfirmDialog.generated.h"

class UCanvasPanel;
class UTextBlock;
class UUmButton;

UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmConfirmDialog : public UUmModalBase {
  GENERATED_BODY()

 public:
  static const TCHAR* const WidgetBlueprintPath;  // /Game/S08/UI/Common/WBP_UmConfirmDialog
  static UClass* WidgetClass();
  /** The SC-01 base sheet: 640 x 360 su; the buttons 168 x 48. */
  static constexpr float FrameWSu = 640.0f;
  static constexpr float FrameHSu = 360.0f;
  static constexpr float ButtonWSu = 168.0f;
  static constexpr float ButtonHSu = 48.0f;
  static constexpr float PadSu = 16.0f;

  struct FRequest {
    /** The UI-ID of the screen that asks (its SHOT line gets state=confirm). */
    FString OwnerUiId;
    FText Title;
    FText Message;
    TFunction<void()> OnConfirm;
    TFunction<void()> OnCancel;
  };

  virtual bool Initialize() override;
  /** The base tree + Content (Canvas) > Title, Message, Cancel, Confirm in Body. */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  bool HasAllParts(FString* OutMissing = nullptr) const;

  /** The presses go through the arbiter (DE-014): «common.confirm.yes» / «common.confirm.cancel». */
  void SetInput(const TSharedPtr<FS09HudPressArbiter>& InArbiter);
  void Open(FRequest InRequest);
  /** Confirm (true) or cancel (false): the callback once, then the dialog goes (120 ms). */
  void Answer(bool bConfirm);
  /** Esc: cancel while open (04 §1); false when the dialog is not open. */
  bool HandleEscape();
  bool IsOpen() const { return IsShown(); }
  const FString& GetOwnerUiId() const { return Request.OwnerUiId; }

  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> Title;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> Message;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> Confirm;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> Cancel;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UCanvasPanel> Content;

 protected:
  virtual void OnVeilClick() override { Answer(false); }
  virtual void BuildContent() override;

 private:
  static bool AttachContent(UWidgetTree& Tree, UPanelWidget* Parent, FS08AttachWidget Attach, FString* OutError);
  void ApplyContent();
  FRequest Request;
  bool bAnswered = false;
};
