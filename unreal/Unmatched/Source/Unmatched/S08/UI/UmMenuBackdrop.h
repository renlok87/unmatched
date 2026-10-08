// VS-7 SC-02 (docs/game-design/visual/06-tasks/screens.csv SC-02; 04-hud-spec.md §1 «фон BOOT…ROOM», §7.4; 02 §10.1,
// §10.5; ВР-53...ВР-56, ВР-75; AGENTS.md «Board scenes and heroes»): the menu backdrop - the live Marmoreal original K1
// scene WITHOUT figures behind BOOT, LOGIN, LOBBY, ROOM and the match loading, under the screens' panel.veil 0.6.
//
//   scene     the board of the -Bench fixture Config/Bench/S08BenchMarmoreal.json (Board c121b47f8d6eb28daccb76d05, its
//             art profile marmoreal-original with the default painted backdrop of ENV-U16 / EN-13 - the 3D P5c only with
//             -NoConceptPaste), built by the same AS08BoardActor path as a match board: map surface, light profile,
//             concept paste with its animated parts (ВР-55); no fighters, so no plates, tags or bases. The K1 camera
//             of SetupCameraForBoard (pitch -55, yaw -90, FOV 35, the profile's k1DistanceMul) on BoardCamera.
//   life      built once at BOOT and kept while the screens change; the first match snapshot hands it over:
//             Marmoreal - the same actor becomes the match board (no second copy, the fighters come from the snapshot);
//             any other board (Sarpedon) - the menu board goes and the match board spawns in the same frame (the swap
//             under the loading screen, never a Marmoreal frame with figures). After the match (the board is torn
//             down when Started ends) the menu board is built again.
//   trace     'SCREEN-BG board=marmoreal-original boardId=<id> profile=<art profile> fighters=0 veil=0.60
//             backdrop=paste|p5c stage=<Boot|Login|Lobby|Room|Started|Failed> state=menu|swap|handover|off' on every
//             change; ARTLOOK unchanged.
//   rollback  -S08SlateHud=menubg or -S08SlateHud (the whole HUD): no scene - the black background of the legacy root.
//   cost      the same scene as the K1 bench frame of the match minus the six figures (budget: GPU <= K1 of the match).
#pragma once

#include "CoreMinimal.h"
#include "../S08ArtLook.h"
#include "../S08BoardModel.h"

class AS08BoardActor;
class UWorld;

namespace UmMenuBackdrop {
/** Marmoreal · original map, the default board of the menus (AGENTS.md). */
inline const TCHAR* const BoardId = TEXT("c121b47f8d6eb28daccb76d05");
inline const TCHAR* const BoardKey = TEXT("marmoreal-original");
/** The screens' veil drawn over the scene (UUmScreenBase, panel.veil). */
inline constexpr float VeilAlpha = 0.60f;

/** False with -S08SlateHud=menubg or the whole-HUD rollback. */
UNMATCHED_API bool Wanted(const S08ArtLook::FS08SlateHudBlocks& Blocks);
/** Config/Bench/S08BenchMarmoreal.json (the -Bench fixture of the K1 frame). */
UNMATCHED_API FString FixturePath();
/** The fixture's board (boardState only - its fighters are never read) and its benchBoardId. */
UNMATCHED_API bool LoadBoard(const FString& File, FS08BoardModel& OutBoard, FString& OutBoardId, FString* OutProblem = nullptr);
/** "paste(default)" -> "paste", "p5c(flag-off)" -> "p5c", "" -> "-". */
UNMATCHED_API FString BackdropShort(const FString& Field);
/** The SCREEN-BG line. */
UNMATCHED_API FString TraceLine(const FString& BoardIdIn, const FString& Profile, int32 Fighters, const FString& Backdrop,
                                const TCHAR* Stage, const TCHAR* State);
}  // namespace UmMenuBackdrop
