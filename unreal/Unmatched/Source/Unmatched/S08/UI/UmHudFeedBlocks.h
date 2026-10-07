// VS-4 HB-39...HB-41 and the HB-36 toast trigger (docs/game-design/visual/06-tasks/hud.csv; 04-hud-spec.md §2.10, §2.12,
// §2.13, §5.1, §5.2 steps H5 / H11, §7.1): the game mode's side of the feed blocks, world-free - FUmFeedBlocks builds the
// log (UUmHudLog), the toast stack (UUmToastStack) and the subtitle (UUmHudSubtitle) into the GAME screen unless rolled
// back (-S08SlateHud=log | toast | sub: that block stays the old Slate one), and every frame
//   - hides the log in the combat, opens / closes the class S list,
//   - moves the toast clocks (the banner gate) and the subtitle's, and
//   - places the group «toasts + subtitle» by the chain of 04 §2.12 (UmHudFeed::Place) over the obstacles the game mode
//     collects: the figures (+ their tags and the plate), the spaces (not in the defense window, ВР-VS2-HB38-18), every
//     drawn HUD block, the hand caption + 8 su; again only when an input changed (a hash of the rounded rects).
// S08FlowGameModeUmHud.cpp only collects the input, turns the events into entries and the presses into commands (04 §5.1).
#pragma once

#include "CoreMinimal.h"
#include "../../S09/S09HudPress.h"
#include "../S08ArtLook.h"
#include "UmHudFeed.h"
#include "UmHudLayout.h"
#include "UmHudLog.h"
#include "UmHudSubtitle.h"
#include "UmToastStack.h"

class UUmGameHud;

/** One frame of the feed. */
struct UNMATCHED_API FUmFeedInput {
  const FUmHudLayout* Layout = nullptr;
  /** The live match HUD (no result screen, no lobby). */
  bool bLive = false;
  double NowMs = 0.0;
  bool bReduced = false;
  /** The combat is on screen (the defense window, the staging): the log hides, the spaces stop being obstacles. */
  bool bCombat = false;
  /** The «ВАШ ХОД» banner is up (a new toast waits for it). */
  bool bBannerShown = false;
  /** The bottom of the drawn STATUS capsule (su), -1 none (then the TOP bottom). */
  float StatusBottomSu = -1.0f;
  TArray<FBox2D> Figures;  // + their tags and the plate
  TArray<FBox2D> Spaces;   // every board space (centre +- radius through the K1 camera)
  TArray<FBox2D> Blocks;   // every drawn HUD block
  /** The top of the hand cards as drawn now (the lowering included), -1 = no hand. */
  float CardsTopSu = -1.0f;
  /** The «Рука n/max» plate when shown (invalid otherwise). */
  FBox2D CaptionSu = FBox2D(ForceInit);
  bool bHandLowered = false;
  /** HB-36: the pending trigger's toast (zero = none). */
  FVector2D PendingToastSu = FVector2D::ZeroVector;
};

class UNMATCHED_API FUmFeedBlocks {
 public:
  struct FCallbacks {
    /** A sticky toast's cross: the press outcome and the toast's key. */
    TFunction<void(const FS09HudPressOutcome&, FName)> OnToastClose;
    /** A log line with a known card. */
    TFunction<void(const FString& CardId)> OnLogInspect;
  };
  /** Builds the blocks not rolled back; trace lines out (HUD-FEED-UMG ...). */
  TArray<FString> Build(UUmGameHud& Game, const S08ArtLook::FS08SlateHudBlocks& Blocks,
                        const TSharedPtr<FS09HudPressArbiter>& Arbiter, FCallbacks Callbacks);
  /** One frame: the clocks, the log's visibility, the placement; trace lines of the changes (TOAST place=..., HUD-LOG ...). */
  TArray<FString> Refresh(const FUmFeedInput& In);

  bool LogOnUmg() const { return Log.IsValid(); }
  bool ToastOnUmg() const { return Toasts.IsValid(); }
  bool SubOnUmg() const { return Sub.IsValid(); }
  UUmHudLog* GetLog() const { return Log.Get(); }
  UUmToastStack* GetToasts() const { return Toasts.Get(); }
  UUmHudSubtitle* GetSub() const { return Sub.Get(); }

  void PushLog(const FUmLogEntry& Entry, double NowMs);
  void PushToast(const FUmToastSpec& Spec, double NowMs);
  void DismissToast(FName Key, double NowMs);
  void ShowBadge(const FVector2D& CentreSu, double NowMs);
  void ShowSubtitle(const FUmSubtitleModel& Model);
  void HideSubtitle();
  /** Class S: «Журнал» toggles the list; any other click / Esc / the combat closes it. */
  void SetLogOpen(bool bOpen);
  bool IsLogOpen() const;
  /** HB-36: where the pending block draws its toast (invalid = none / no room). */
  FBox2D PendingToastRect() const;
  /** The point (canvas su) is over the open S list or a sticky toast - the board must not take that click. */
  bool CoversPoint(const FVector2D& PointSu) const;
  /** The rect of the open S list (invalid otherwise). */
  FBox2D LogListRectSu() const;
  /** Place again on the next Refresh (the review sheet between its states). */
  void Invalidate() { bHasHash = false; }
  /** The last placement (tests, the trace). */
  const UmHudFeed::FStackResult& GetPlacement() const { return Placed; }
  /** The world-free placement of one input (tests). */
  static UmHudFeed::FStackInput StackInput(const FUmFeedInput& In, const TArray<FUmToastMember>& Members, const FVector2D& SubSize);
  void CollectShotLines(TArray<FString>& Out, float PxPerSu) const;

 private:
  TWeakObjectPtr<UUmHudLog> Log;
  TWeakObjectPtr<UUmToastStack> Toasts;
  TWeakObjectPtr<UUmHudSubtitle> Sub;
  UmHudFeed::FStackResult Placed;
  uint32 PlaceHash = 0;
  bool bHasHash = false;
  FBox2D LogRect = FBox2D(ForceInit);
  bool bLogHiddenTraced = false;
  FString LastLogLine;
};
