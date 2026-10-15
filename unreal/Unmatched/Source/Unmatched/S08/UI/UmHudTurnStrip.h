// HB-50 TURN-STRIP (docs/game-design/visual/TURN-STRIP.md): the stages of the running turn as icons with a state each,
// in the TOP row right of «Ход N» (slot EUmGameSlot::TurnStrip, rect UmHudLayout EUmHudBlock::TurnStrip).
//
//   layout   one plate (the «Ход N» skin of TOP), height = TOP; left to right: action 1, [its sub-steps], action 2,
//            [its sub-steps], discard to 7, end of turn, joined by 2 su lines (gold after a done node, a divider ahead).
//            Full: the sub-steps of the action in progress in a thin tray after its node. Compact (the layout leaves too
//            little room, UmHudLayout::TurnStripFullFits): the four nodes only, the step now as a badge on its node.
//   states   done = the full icon + a check badge; now = the full icon, a 3 su ring of the side (own gold, opponent
//            P2; my step in their turn gold) pulsing 1200 ms (static with reduced motion); next = 50 % greyed icon and a
//            thin ring; skip = 25 % icon, no ring. A choice open at the step: the state-hint badge.
//   tips     hover on a node: its rule (hud.turnstrip.*).
//   data     ApplyModel(FS09TurnStripModel, frame) only - S09TurnStrip::Build is the logic; same input = no work.
// Rollback: -S08SlateHud=turnstrip (the strip is not built).
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../../S09/S09TurnStrip.h"
#include "../S08ArtHud.h"
#include "../S08ArtHudWidgets.h"
#include "UmHudTurnStrip.generated.h"

class UBorder;
class UHorizontalBox;
class USizeBox;
class US08AnimatedIconWidget;

struct UNMATCHED_API FUmTurnStripFrame {
  bool bClassS = false;
  bool bCompact = false;
  float PxPerSu = 1.0f;
  bool bReducedMotion = false;
  bool operator==(const FUmTurnStripFrame& O) const {
    return bClassS == O.bClassS && bCompact == O.bCompact && PxPerSu == O.PxPerSu && bReducedMotion == O.bReducedMotion;
  }
};

namespace UmHudTurnStrip {
inline constexpr int32 MainNodes = 4;
inline constexpr int32 MaxSubs = 4;
inline constexpr int32 Trays = 2;  // one per action slot
inline float NodeSu(bool bClassS) { return bClassS ? 26.0f : 32.0f; }
inline float SubSu(bool bClassS) { return bClassS ? 20.0f : 24.0f; }
inline float LinkSu(bool bClassS) { return bClassS ? 6.0f : 10.0f; }
inline constexpr float SubLinkSu = 6.0f;
inline constexpr float PadSu = 8.0f;
inline constexpr float TrayGapSu = 6.0f;
/** The widths the layout reserves (su): the four nodes, and with a tray of MaxSubs sub-steps. */
UNMATCHED_API float CompactWidthSu(bool bClassS);
UNMATCHED_API float FullWidthSu(bool bClassS);
inline constexpr double PulseMs = 1200.0;
}  // namespace UmHudTurnStrip

UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmHudTurnStrip : public UUserWidget {
  GENERATED_BODY()

 public:
  virtual bool Initialize() override;
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);

  void ApplyModel(const FS09TurnStripModel& InModel, const FUmTurnStripFrame& InFrame);
  const FS09TurnStripModel& GetModel() const { return Model; }
  const FUmTurnStripFrame& GetFrame() const { return Frame; }
  /** Shown nodes / sub-steps (tests, shot line). */
  int32 ShownNodes() const;
  int32 ShownSubs() const;
  /** The tooltip of main node I ('' when hidden). */
  FText NodeTip(int32 I) const;
  /** 'SHOT widget id=UI-HUD-TURNSTRIP impl=umg state=own|opp ... mode=full|compact nodes=.. subs=..'. */
  void CollectShotLines(TArray<FString>& Out, const FS08ScreenRect& Rect) const;

  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget))
  TObjectPtr<UBorder> Plate;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget))
  TObjectPtr<UHorizontalBox> Row;

 protected:
  virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;

 private:
  /** One drawn node (main or sub): the size box (tooltip, hit test), the ring, the icon, the badge. */
  void StyleNode(int32 Box, const FS09StripNode& N, float Su, FName Badge);
  void BindParts();

  UPROPERTY() TArray<TObjectPtr<USizeBox>> Boxes;               // main 0..3, then subs (tray * MaxSubs + j)
  UPROPERTY() TArray<TObjectPtr<UBorder>> Rings;
  UPROPERTY() TArray<TObjectPtr<US08AnimatedIconWidget>> Icons;
  UPROPERTY() TArray<TObjectPtr<US08AnimatedIconWidget>> Badges;
  UPROPERTY() TArray<TObjectPtr<UBorder>> Links;               // main 0..2, then sub links (tray * MaxSubs + j)
  UPROPERTY() TArray<TObjectPtr<UBorder>> TrayBoxes;

  FS09TurnStripModel Model;
  FUmTurnStripFrame Frame;
  bool bHasModel = false;
  TArray<int32> PulseBoxes;  // boxes whose ring pulses (state now)
  FLinearColor PulseColor = FLinearColor::White;
  double PulseStart = 0.0;
  bool bCodeDefaultTree = false;
};
