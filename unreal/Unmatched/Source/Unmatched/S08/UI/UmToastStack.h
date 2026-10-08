// VS-4 HB-40 (docs/game-design/visual/06-tasks/hud.csv HB-40, the HB-36 toast trigger; 04-hud-spec.md §2.12, §4.3,
// §7.1, ВР-H06; the accepted mockup HB-38 art/imagegen/hud-feed-v1-codex, ВР-VS2-HB38-06...12, -18): the toast stack -
// UUmToastStack (/Game/S08/UI/Hud/WBP_UI_HUD_TOAST), a pool of UUmToast and the refusal badge.
//
//   data     Push(FUmToastSpec): a refusal (ShowReason: FS09Reason why.* - CUE-004), the hand-limit rule (FS09HandLimitHint,
//            sticky), «Позиции обновлены (пропущено {n})» after a reconnect, «Нет допустимых целей» (the skipped
//            effect's reason). The same key and text again only renews the hold. The HB-36 repeating optional trigger
//            (UUmHudPending's toast form, Enter / X / C) is one member of the stack (SetExternal): it takes its place in
//            the order and the chain, the pending block draws it at GetExternalRect().
//   time     in 180 (icon.appear.ms), held 2-4 s (an error 4 s), out 120 (icon.leave.ms); a sticky toast until its cross,
//            the owner's dismiss (end of turn, GAME_OVER); reduced motion - no fade. A new toast waits for the end of the
//            «ВАШ ХОД» banner (600 ms, 04 §2.12). At most 2 members: the oldest leaves for a newer one; the newest at
//            the bottom.
//   place    the owner runs UmHudFeed::Place over Members() (+ the subtitle) and hands the result to ApplyPlacement:
//            a toast the chain dropped (step 4) leaves early; the external member is hidden until there is room.
//   badge    ShowBadge(centre): badge-refuse (IC-40) 24 su for refuse.ms 350 next to the refused button or over the
//            refused space (V-08) - transient, may cover the field; no shake.
//   input    the stack and its toasts never take focus or the mouse - only a sticky toast's close cross.
// SHOT: 'SHOT widget id=UI-HUD-TOAST impl=umg state=bottom|top fighter=none bbox=<the stack> ... n=<k> kinds=<list>
//        step=<bottom|top|upward|newest|fail> overlap=<px2> dropped=<d> sticky=0|1 external=0|1 badge=0|1' - no text.
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../../S09/S09HudPress.h"
#include "../S08ArtHud.h"
#include "../S08ArtHudWidgets.h"
#include "UmHudFeed.h"
#include "UmToast.h"
#include "UmToastStack.generated.h"

class UCanvasPanel;
class US08AnimatedIconWidget;

/** The canvas the stack lives on. */
struct UNMATCHED_API FUmToastFrame {
  FVector2D CanvasSu = FVector2D(1920.0, 1080.0);
  float PxPerSu = 1.0f;
  bool bClassS = false;
  bool bTall = true;
  bool bReduced = false;
  bool operator==(const FUmToastFrame& O) const {
    return CanvasSu == O.CanvasSu && PxPerSu == O.PxPerSu && bClassS == O.bClassS && bTall == O.bTall && bReduced == O.bReduced;
  }
};

/** One member of the stack as the placement sees it. Id = the toast's sequence number; ExternalId = the pending one. */
struct UNMATCHED_API FUmToastMember {
  int32 Id = 0;
  FVector2D SizeSu = FVector2D::ZeroVector;
};

namespace UmToastStack {
inline constexpr int32 ExternalId = -1;
/** The pool: 2 shown + 1 leaving. */
inline constexpr int32 PoolSize = 3;
}  // namespace UmToastStack

UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmToastStack : public UUserWidget {
  GENERATED_BODY()

 public:
  static const TCHAR* const WidgetBlueprintPath;  // /Game/S08/UI/Hud/WBP_UI_HUD_TOAST

  virtual bool Initialize() override;
  /** CanvasPanel "Canvas" > US08AnimatedIconWidget "Badge" (the toasts are pooled UUmToast made at run time). */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  static UClass* WidgetClass();
  bool HasAllParts(FString* OutMissing = nullptr) const;
  bool UsesCodeDefaultTree() const { return bCodeDefaultTree; }
  FString SourceName() const;

  void SetFrame(const FUmToastFrame& InFrame);
  const FUmToastFrame& GetFrame() const { return Frame; }
  /** The close crosses through the HUD press arbiter; OnClose(key) answers an accepted release. */
  void SetInput(const TSharedPtr<FS09HudPressArbiter>& InArbiter, TFunction<void(const FS09HudPressOutcome&, FName)> InOnClose);
  /** Text measure (tests: an estimate; the game: the drawn font at the frame's scale). */
  void SetMeasureForTest(TFunction<float(const FString&, float)> InMeasure) { MeasureOverride = MoveTemp(InMeasure); }

  /** A new toast (or the hold of the same one renewed); returns its id. */
  int32 Push(const FUmToastSpec& Spec, double NowMs);
  /** Every toast, the trigger and the badge gone at once (the review sheet between its states). */
  void Clear();
  /** VS-4 HB-49: the toasts belong to the live match - off the match (lobby, result, interruption) the stack clears
   *  (once, and again whenever something was pushed meanwhile). */
  void SetLive(bool bLive);
  bool IsEmpty() const { return Entries.Num() == 0 && !bExternal && BadgeUntilMs <= 0.0; }
  /** The toast of Key leaves (a sticky one closed by its owner: the click, the end of the turn, GAME_OVER). */
  bool Dismiss(FName Key, double NowMs);
  /** A toast of Key is on screen or waiting for the banner. */
  bool Has(FName Key) const;
  /** HB-36: the pending trigger's toast as a member of the stack (Size su; off = gone). */
  void SetExternal(bool bOn, const FVector2D& SizeSu, double NowMs);
  /** Where the pending block draws its toast (invalid = not placed / no room this frame). */
  FBox2D GetExternalRect() const { return ExternalRect; }
  /** Moves the clocks: the banner gate, the fades, the holds; true when the members changed (place again). */
  bool Tick(double NowMs, bool bBannerShown);
  /** The members that want a place now, oldest first. */
  void Members(TArray<FUmToastMember>& Out) const;
  /** Puts every member at its rect of Result (Ids = Members() order). */
  void ApplyPlacement(const UmHudFeed::FStackResult& Result, const TArray<FUmToastMember>& InMembers, double NowMs);
  const UmHudFeed::FStackResult& GetPlacement() const { return Placed; }

  /** badge-refuse 24 su centred on CentreSu (canvas su) for refuse.ms. VS-6 FX-10: SizeSu (> 0) sizes the stamp at
   *  a space (clamp(0.3 x the space on screen, 24, 32) px); the stamp curve of S08FieldFx::RefuseStamp; a repeat within
   *  300 ms does not restart it (returns false). -S08FxLegacy: the icon's own appear, every repeat restarts. */
  bool ShowBadge(const FVector2D& CentreSu, double NowMs, float SizeSu = 0.0f);
  bool IsBadgeShown() const { return BadgeUntilMs > 0.0; }
  FBox2D BadgeRectSu() const;

  /** The rects of the toasts drawn now (canvas su), oldest first. */
  void DrawnRectsSu(TArray<FBox2D>& Out) const;
  /** A sticky toast's close cross under the point (canvas su) - the board must not take that click. */
  bool HitsClose(const FVector2D& PointSu) const;
  /** The shown toasts' kinds, oldest first ('info,error'). */
  FString KindsField() const;
  int32 NumShown() const;
  /** 'TOAST place=bottom|top step=... overlap=... n=... kinds=... dropped=... y=...' once per placement change. */
  FString TakePlaceLine();
  void CollectShotLines(TArray<FString>& Out) const;

  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget))
  TObjectPtr<UCanvasPanel> Canvas;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional))
  TObjectPtr<US08AnimatedIconWidget> Badge;

 private:
  struct FEntry {
    int32 Id = 0;
    FUmToastSpec Spec;
    FUmToastPlan Plan;
    double QueuedMs = 0.0;
    double ShownMs = -1.0;       // -1: waits for the banner
    bool bWaited = false;        // a tick saw it wait for the banner (it then appears from that tick, else from its push)
    double HoldUntilMs = 0.0;    // 0: sticky
    double LeaveStartMs = -1.0;
    int32 Pool = -1;
    bool bPlaced = false;
  };
  void BindFromTree();
  UUmToast* PoolAt(int32 I);
  int32 FreePool() const;
  float MeasureSu(const FString& Text, float SizeSu) const;
  FUmToastPlan PlanOf(const FUmToastSpec& Spec) const;
  void StartLeave(FEntry& E, double NowMs);
  float AlphaOf(const FEntry& E, double NowMs) const;
  void ApplyAlphas(double NowMs);

  UPROPERTY() TArray<TObjectPtr<UUmToast>> Pool;
  TArray<FEntry> Entries;
  int32 NextId = 1;
  FUmToastFrame Frame;
  TSharedPtr<FS09HudPressArbiter> Arbiter;
  TFunction<void(const FS09HudPressOutcome&, FName)> OnClose;
  TFunction<float(const FString&, float)> MeasureOverride;
  // the pending trigger
  bool bExternal = false;
  FVector2D ExternalSize = FVector2D::ZeroVector;
  int32 ExternalSeq = 0;
  FBox2D ExternalRect = FBox2D(ForceInit);
  // the last placement
  UmHudFeed::FStackResult Placed;
  FString LastPlaceLine;
  FString PendingPlaceLine;
  // the badge
  double BadgeUntilMs = 0.0;
  double BadgeShownMs = -1.0e9;
  float BadgeSizeSu = 0.0f;
  bool bBadgeStamp = false;
  FVector2D BadgeCentreSu = FVector2D::ZeroVector;
  bool bCodeDefaultTree = false;
};
