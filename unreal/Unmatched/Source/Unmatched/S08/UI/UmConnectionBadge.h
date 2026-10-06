// VS-2 HB-14 (docs/game-design/visual/06-tasks/hud.csv HB-14; 04-hud-spec.md §2.1, §4.3, §7.1; ВР-H17; CX-08 mockup
// art/imagegen/hud-topstrip-v1-codex): the connection chip of TOP - UUmConnectionBadge
// (/Game/S08/UI/Common/WBP_UmConnectionBadge).
//
//   states   online   resource-connection-online        the bars (text.secondary)           «Связь в порядке»
//            syncing  resource-connection-reconnecting  the bars + ↻ (cycle icon.reconnect.ms 1200)  «Синхронизация…»
//            lost     resource-connection-lost          the bars + X (state.error, the sign only)    «Связи нет»
//            The form tells them apart in grey (bars / ↻ / X); there is no fourth icon: syncing draws reconnecting.
//   input    ВР-VS2-43 (UmConnection::Resolve): lost = the match stream was ready once and IsStreamReady is false now;
//            before the first ready stream (join) it is syncing; syncing = IsCommandSlow, any command in flight for
//            FS08FlowController::CommandSlowSeconds or longer, or the state recovery (IsAwaitingStateRecovery).
//   motion   a change plays the new icon's appear (a crossfade, icon.appear.ms; online -> lost: appear_from_online);
//            the reconnecting cycle loops after its appear; reduced motion - no cycle (the contract's reduced branch).
//   hover    the tooltip (hud.conn.*) after 300 ms over the chip.
//   missing  ВР-HB08: an icon the contract or the pak does not have -> the hud.conn.* text in type.tag and one trace
//            'ICON missing=<id> block=UI-HUD-CONN'.
// The RECONNECT overlay is not opened from here (screens.csv SC-31).
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../S08ArtHud.h"
#include "../S08ArtHudWidgets.h"
#include "UmConnectionBadge.generated.h"

class USizeBox;
class UOverlay;
class UTextBlock;
class US08AnimatedIconWidget;

enum class EUmConnState : uint8 { Online, Syncing, Lost };

/** What the game mode knows about the link this frame (FS08FlowController). */
struct UNMATCHED_API FUmConnInput {
  bool bStreamReady = true;   // IsStreamReady
  bool bWasReady = true;      // the stream has been ready once in this match
  bool bCommandSlow = false;  // IsCommandSlow, or a command in flight >= CommandSlowSeconds
  bool bRecovering = false;   // IsAwaitingStateRecovery (the seq gap is being fetched)
};

namespace UmConnection {
/** ВР-VS2-43: lost > syncing > online. */
UNMATCHED_API EUmConnState Resolve(const FUmConnInput& In);
/** online | syncing | lost (the SHOT state of UI-HUD-CONN). */
UNMATCHED_API const TCHAR* StateName(EUmConnState State);
/** The v3 icon of a state. */
UNMATCHED_API FName IconId(EUmConnState State);
/** hud.conn.online | .syncing | .lost (ST_Hud). */
UNMATCHED_API const TCHAR* TooltipKey(EUmConnState State);
/** The contract animation that brings the icon of To in after From. */
UNMATCHED_API FName AppearAnim(EUmConnState From, EUmConnState To);
/** 04 §2.1: the chip zone is 44 su in L, 40 su in S; the icon 24 su (ВР-42). */
inline constexpr float ZoneLSu = 44.0f;
inline constexpr float ZoneSSu = 40.0f;
inline constexpr float IconSu = 24.0f;
/** 04 §2.1: the tooltip after 300 ms of hover. */
inline constexpr double TooltipDelaySeconds = 0.3;
}  // namespace UmConnection

UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmConnectionBadge : public UUserWidget {
  GENERATED_BODY()

 public:
  static const TCHAR* const WidgetBlueprintPath;  // /Game/S08/UI/Common/WBP_UmConnectionBadge

  virtual bool Initialize() override;
  /** SizeBox "Box" > Overlay "Stack" > Icon (US08AnimatedIconWidget), FallbackText. */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  /** The WBP's generated class when the asset exists, else the native class. */
  static UClass* WidgetClass();
  bool HasAllParts(FString* OutMissing = nullptr) const;
  bool UsesCodeDefaultTree() const { return bCodeDefaultTree; }

  /** The one data input (П1): the state and the zone side (44 / 40 su). The same state again = no work. */
  void ApplyState(EUmConnState InState, float ZoneSu = UmConnection::ZoneLSu);
  EUmConnState GetState() const { return State; }
  bool HasState() const { return bHasState; }
  /** The icon drawn now (NAME_None = the text fallback). */
  FName GetShownIcon() const { return ShownIcon; }
  /** The animation the last change played ('rest' for the first state). */
  FName GetLastAnim() const { return LastAnim; }
  bool IsTooltipShown() const { return bTooltipShown; }
  FText GetTooltipText() const;
  /** "SHOT widget id=UI-HUD-CONN impl=umg state=online ... icon=<id> anim=<appear|rest|...>" for Rect (viewport px). */
  FString ShotLine(const FS08ScreenRect& Rect, const FString& Source) const;
  /** "code-default" or the WBP path. */
  FString SourceName() const;

  // ---- tests (the same paths as the mouse) ----
  void SetClockForTest(TFunction<double()> InClock) { Clock = MoveTemp(InClock); }
  void SimulateHover(bool bIn);
  void TickForTest() { StepTooltip(); }

  virtual void NativeOnMouseEnter(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
  virtual void NativeOnMouseLeave(const FPointerEvent& InMouseEvent) override;

  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget))
  TObjectPtr<USizeBox> Box;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget))
  TObjectPtr<US08AnimatedIconWidget> Icon;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional))
  TObjectPtr<UTextBlock> FallbackText;

 protected:
  virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;

 private:
  void StepTooltip();
  double Now() const;

  EUmConnState State = EUmConnState::Online;
  bool bHasState = false;
  FName ShownIcon;
  FName LastAnim;
  float ZoneShown = 0.0f;
  bool bHovered = false;
  double HoverSince = -1.0;
  bool bTooltipShown = false;
  bool bMissingTraced = false;
  TFunction<double()> Clock;
  bool bCodeDefaultTree = false;
};
