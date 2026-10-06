// VS-2 HB-14...HB-16 (docs/game-design/visual/06-tasks/hud.csv; 04-hud-spec.md §2.1, §2.4, §2.5, §5.1, §5.2 steps H5,
// H6): the top strip of the GAME screen - TOP + CONN (UUmHudTop), STATUS (UUmHudStatusLine) and the banner
// (UUmHudBanner) - as one runtime object the game mode feeds (04 §5.1: the new code in S08/UI, the game mode only
// gathers its inputs in S08FlowGameModeUmHud.cpp).
//
//   build    each block whose -S08SlateHud key (top / status / banner) is not rolled back: WBP or code tree, into its
//            UUmGameHud slot; the menu and log presses go through the HUD press arbiter (DE-014, UI-INP-011).
//   frame    the layout event (window, UI scale, FIELD): class L / S, px per su, the STATUS width (880 / 720 / 600).
//   tick     per frame, cheap (same model = no work): TOP (turn, class), CONN (ВР-VS2-43: a command in flight counts
//            as slow after FS08FlowController::CommandSlowSeconds), the banner alpha of FS09TurnCue.
//   status   by event - the game mode's AddTurnStatusLine (every RefreshHud) hands its FS09TurnStatusInput over.
// Trace: 'HUD-TOPSTRIP top=umg|slate status=.. banner=.. source=..' at the build, 'HUD-CONN state=.. ready=.. slow=..
// recovering=..' on a change of the link state, SHOT lines per evidence frame.
#pragma once

#include "CoreMinimal.h"
#include "../../S09/S09HudPress.h"
#include "../../S09/S09TurnHud.h"
#include "../../S09/S09TurnStatus.h"
#include "../S08ArtHud.h"
#include "../S08ArtLook.h"
#include "UmConnectionBadge.h"

class UUmGameHud;
class UUmHudBanner;
class UUmHudStatusLine;
class UUmHudTop;
class UWidget;

struct UNMATCHED_API FUmTopStripFrame {
  bool bClassS = false;
  float PxPerSu = 1.0f;
  float StatusMaxWidthSu = 880.0f;
  /** UI-ACC-017 (HB-43): the key chips of STATUS. */
  bool bKeyHints = false;
};

struct UNMATCHED_API FUmTopStripTick {
  /** The live match HUD is up (not the lobby, not the result screen). */
  bool bShow = false;
  int32 TurnCount = 0;
  // the link (FS08FlowController)
  bool bStreamReady = true;
  bool bManeuverSlow = false;  // IsCommandSlow
  bool bInFlight = false;      // any command in flight (HudBusyReason)
  bool bRecovering = false;    // IsAwaitingStateRecovery
  double NowSeconds = 0.0;
  // the banner
  const FS09TurnCue* Cue = nullptr;
  double CueNowMs = 0.0;
};

class UNMATCHED_API FUmTopStrip {
 public:
  /** CommandSlowSeconds of FS08FlowController (MS-E-89): the in-flight time after which CONN shows syncing. */
  static constexpr double SlowSeconds = 3.0;

  /** Builds the blocks not rolled back; OnPress(outcome, "menu" | "log") answers a resolved press. Trace lines out. */
  TArray<FString> Build(UUmGameHud& Game, const S08ArtLook::FS08SlateHudBlocks& Blocks,
                        const TSharedPtr<FS09HudPressArbiter>& Arbiter,
                        TFunction<void(const FS09HudPressOutcome&, const TCHAR*)> OnPress);
  void SetFrame(const FUmTopStripFrame& InFrame);
  /** Per frame. Returns the 'HUD-CONN ...' line when the link state changed, else ''. */
  FString Tick(const FUmTopStripTick& T);
  /** The STATUS line (false: STATUS is on Slate). */
  bool ApplyStatus(const FS09TurnStatusInput& In);
  /** SHOT lines of the visible blocks; RectOf gives a widget's viewport px rect (empty when not drawn). */
  void CollectShotLines(TArray<FString>& Out, TFunctionRef<FS08ScreenRect(UWidget*)> RectOf) const;

  /** ВР-VS2-43 with the in-flight timer of this strip (world-free: the tests step NowSeconds). */
  FUmConnInput ConnInput(const FUmTopStripTick& T);
  EUmConnState GetConn() const { return Conn; }

  UUmHudTop* GetTop() const { return Top.Get(); }
  UUmHudStatusLine* GetStatus() const { return Status.Get(); }
  UUmHudBanner* GetBanner() const { return Banner.Get(); }

 private:
  TWeakObjectPtr<UUmHudTop> Top;
  TWeakObjectPtr<UUmHudStatusLine> Status;
  TWeakObjectPtr<UUmHudBanner> Banner;
  FUmTopStripFrame Frame;
  bool bWasReady = false;
  double InFlightSince = -1.0;
  EUmConnState Conn = EUmConnState::Online;
  bool bConnKnown = false;
  bool bShown = false;  // the blocks start collapsed (Build) and show with the live match HUD
};
