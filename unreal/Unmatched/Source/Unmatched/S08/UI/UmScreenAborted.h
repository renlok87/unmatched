// VS-7 S5 SC-38 (docs/game-design/visual/06-tasks/screens.csv SC-38; 04-hud-spec.md §1.11 (new id UI-SCR-ABORTED), H14;
// GD-040; the accepted CX-34 mockup art/imagegen/sc38-aborted-codex and its decisions ВР-VS5-SC38-01...04): the
// interrupted match - UUmScreenAborted (/Game/S08/UI/Screens/WBP_UI_SCR_ABORTED) in the root's Modals.
//
//   when     the room row of the live match is ABORTED (game(id) or a mutation answer - never a snapshot, never a CUE).
//   modal    AbortedModal 640 x 360 su centred over the veil 0.6, one centred column vertically centred
//            (ВР-VS5-SC38-02): Icon resource-connection-lost 48 su; 16; TitleText «Партия прервана» (type.title); 12;
//            WhoText (type.body): «Игрок {player} покинул партию» only when the server names the leaver, else «Соперник
//            покинул партию» (ВР-SC13 - the client gets no leaver today); 8; TurnText «Ход {n}» (type.caption,
//            text.secondary); 24; LobbyButton «В лобби» + Enter chip (the one primary). No victory / defeat word or colour,
//            no CUE-016 grade; the X of the icon is the only red.
//   input    the match input is closed (the controller gates); «В лобби», L and Enter -> leaveGame -> LOBBY.
//   gate     'SHOT widget id=UI-SCR-ABORTED impl=umg state=shown ... who=<named|unknown> turn=<n>' - never a name.
//   rollback -S08SlateHud=aborted: the interruption text of the command panel (marker #FF6414 with -S09Markers).
#pragma once

#include "CoreMinimal.h"
#include "../../S09/S09HudPress.h"
#include "UmScreenBase.h"
#include "UmScreenAborted.generated.h"

class UCanvasPanel;
class UTextBlock;
class UUmButton;
class US08AnimatedIconWidget;

struct UNMATCHED_API FUmAbortedModel {
  FString Leaver;        // the nickname of the player who left ('' = not given by the server)
  int32 Turn = 0;        // the last applied turnCount (0 = unknown: no line)
  bool bKeyChips = true;
  bool bLobbyBusy = false;
  bool operator==(const FUmAbortedModel& O) const {
    return Leaver == O.Leaver && Turn == O.Turn && bKeyChips == O.bKeyChips && bLobbyBusy == O.bLobbyBusy;
  }
  bool operator!=(const FUmAbortedModel& O) const { return !(*this == O); }
};

namespace UmAborted {
inline constexpr float ModalWSu = 640.0f;
inline constexpr float ModalHSu = 360.0f;
UNMATCHED_API FText WhoText(const FUmAbortedModel& M);
UNMATCHED_API FText TurnText(const FUmAbortedModel& M);
}  // namespace UmAborted

UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmScreenAborted : public UUmModalBase {
  GENERATED_BODY()

 public:
  static const TCHAR* const WidgetBlueprintPath;  // /Game/S08/UI/Screens/WBP_UI_SCR_ABORTED
  static UClass* WidgetClass();

  virtual bool Initialize() override;
  /** The base tree + Content (Canvas) > Icon (US08AnimatedIconWidget), TitleText, WhoText, TurnText, LobbyButton. */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  bool HasAllParts(FString* OutMissing = nullptr) const;
  void ApplyCanvas(const FVector2D& InCanvasSu, bool bInClassS, float InPxPerSu);

  struct FInput {
    TFunction<void()> OnLobby;
    TFunction<void(FName BankId)> OnSound;
  };
  void SetInput(const TSharedPtr<FS09HudPressArbiter>& InArbiter, FInput InInput);
  void ApplyModel(const FUmAbortedModel& InModel);
  const FUmAbortedModel& GetModel() const { return Model; }
  void SimulatePress(FName Id);

  FString GetTitleText() const;
  FString GetWhoText() const;
  FString GetTurnText() const;
  bool IsLobbyPrimary() const;
  virtual FString ShotExtra() const override;

  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<US08AnimatedIconWidget> Icon;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> TitleText;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> WhoText;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> TurnText;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> LobbyButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UCanvasPanel> Content;

 protected:
  virtual void BuildContent() override;

 private:
  static bool AttachContent(UWidgetTree& Tree, UPanelWidget* Parent, FS08AttachWidget Attach, FString* OutError);
  void BindParts();
  void Refresh();
  void OnPressOutcome(FName Id, const FS09HudPressOutcome& Outcome);

  FUmAbortedModel Model;
  bool bHasModel = false;
  TSharedPtr<FS09HudPressArbiter> Arbiter;
  FInput Input;
};
