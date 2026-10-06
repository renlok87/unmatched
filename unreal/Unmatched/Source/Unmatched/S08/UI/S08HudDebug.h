// VS-1 HB-02 (docs/game-design/visual/04-hud-spec.md s5.1, s5.2 step H0b; VR-35, VR-H16): the debug layer of the S09/S10
// gates leaves the player's view. Without -S09Markers (S08ArtLook::S08Markers, off by default since H0b) the Slate HUD
// of AS08FlowGameMode draws none of:
//   - the pixel markers of the command panel (AddMarker) and of the lobby / interruption panels - S08FlowGameMode.cpp;
//   - the 4-colour gate stripe of the result modal - S08FlowGameModeResult.cpp;
//   - the side-panel lines "you: hand=.. deck=..~ discard=..", "opponent: hand=..(hidden) ..", "seq=.. phase=.. turn=..
//     actions=.." and the "seq=.. - waiting for the authoritative stream" line of the opponent's turn (the deck counts
//     stay in the deck chips and the deck panel, VR-H16);
//   - the command echo toasts ("attack sent", "begin maneuver sent (server draws 1 card)", ...) and the AUTO toasts of
//     the S09 auto driver - PlayerToast below; a toast left without text is not drawn at all;
//   - the "UNMATCHED S08 grey flow" title of the legacy panel and the F10 operator panel.
// Nothing of it is deleted: the gates pass -S09Markers and get the old frames back. The trace does not change ('TOAST
// text=...' still lands once per toast; ARTLOOK carries markers=0|1).
#pragma once

#include "CoreMinimal.h"
#include "Layout/Visibility.h"

namespace S08HudDebug {

/** True for a toast that only echoes a sent command ("attack sent", "begin maneuver sent (server draws 1 card)",
 *  "lobby return already sent") or narrates the S09 auto driver ("AUTO maneuver: f-0-hero -> ..."). A refusal with its
 *  reason ("attack not sent - command gate blocked it ...", "attack rejected: ...") is the player's and stays. */
UNMATCHED_API bool IsDebugToast(const FString& Toast);

/** The toast text the HUD draws: Toast itself, or empty for a debug toast without the debug layer (bMarkers false). */
UNMATCHED_API FString PlayerToast(const FString& Toast, bool bMarkers);

/** PlayerToast with the debug layer of this run (S08ArtLook::S08Markers). */
UNMATCHED_API FString PlayerToast(const FString& Toast);

/** Visible with the debug layer of this run, Collapsed without it: a debug-only widget (the legacy panel title). */
UNMATCHED_API EVisibility Visibility();

}  // namespace S08HudDebug
