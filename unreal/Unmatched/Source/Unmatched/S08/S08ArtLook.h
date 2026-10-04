// ART-DEFAULT (2026-10-04): the accepted art look is the DEFAULT of every client run.
//
// User, 2026-10-04, on a Marmoreal demo frame with grey blockout statues: «Блять, а какого фига не те модели на доске?
// У нас же есть уже готовые модели для Артура и Мерлина и так далее.» The look accepted by delegation in the final
// GD-058 act (docs/game-design/evidence/GD-058/final-2026-10-03/README.md, render_bench variant dx12-lumen-high-v2) was
// opt-in: the art board behind -ArtPreview, the look-dev heroes behind -ArtPreviewHeroesV2, the tray behind
// -ArtPreviewDiorama. Pattern of the change: the v3 HUD token (default, rollback -S08IconLegacy).
//
// What -ArtPreview used to gate, split in two:
//   (a) the ART LOOK - on by default, Enabled() below:
//       * the board actor's art data and assets (S08ArtBoardProfiles.json profile of the room's board, the original
//         map image, zone content, light / sky / fog / exposure profile, hero light) - AS08BoardActor::BeginPlay;
//       * the figures (S08HeroesV2: look-dev heroes v2 by default, rollback -S08HeroesLegacy) and the art markers
//         (selection ring, target arcs, team rings) - AS08FighterActor::BeginPlay;
//       * the diorama tray + environment of the map boards (S08Diorama: T2b / T2 / T1, rollback -S08DioramaLegacy;
//         -ArtPreviewNoEnv still drops only the environment);
//       * the art HUD layer (plate, screen tags, team chips, target token, damage number) - BuildArtHudWidgets.
//       A board without a registered profile stays grey either way (traced 'ARTPREVIEW board profile=none').
//   (b) REVIEW TOOLING - still behind -ArtPreview, ReviewTooling() below: evidence shots (-ArtPreviewShotAfter), the
//       K2 focus zoom (-ArtPreviewFocusZoom), own-hero selection (-ArtPreviewSelectOwnHero), flag input plans
//       (-ArtPreviewInputPlan), the icon probe (-ArtPreviewIconProbe), the board id override (-ArtPreviewBoardId) and the
//       six-Medusa review (-ArtPreviewAllMedusa).
//
// Rollbacks:
//   -S08GreyBoard       the whole art look off: the grey board / grey topology view, grey mannequins, no tray, no art HUD
//                       layer (what a client without -ArtPreview showed before this change; S09 logic harnesses).
//   -S08HeroesLegacy    the pre-default figures (isolated Medusa candidate, ART-003 grey blockouts) - S08HeroesV2.h.
//   -S08DioramaLegacy   no tray and no environment around the map (the board as before -ArtPreviewDiorama) - S08Diorama.h.
//   -S08LegacyRender    unchanged: the pre-W4 render emulation (lights, exposure, game layer) of the bench, S08Render.h.
// -ArtPreviewHeroesV2 / -ArtPreviewDiorama stay accepted as no-op aliases (scripts pass them).
//
// The trace tags of the art path stay 'ARTPREVIEW ...' (every gate script and tool reads them); one 'ARTLOOK ...' line
// per board actor states the effective look and the flags it came from.
#pragma once

#include "CoreMinimal.h"

namespace S08ArtLook {

/** -S08GreyBoard: the rollback of the default art look (the grey board). */
inline const TCHAR* const GreyBoardFlagName = TEXT("S08GreyBoard");
/** -ArtPreview: the review tooling only (see the file comment). */
inline const TCHAR* const ReviewFlagName = TEXT("ArtPreview");

/** World-free rule: the art look unless the grey-board rollback is on the command line. */
constexpr bool Decide(bool bGreyBoardFlag) { return !bGreyBoardFlag; }

/** True unless -S08GreyBoard (or the automation override says otherwise). */
UNMATCHED_API bool Enabled();
/** True with -ArtPreview: evidence shots, probes, focus zoom, own-hero selection, input plans, board id override. */
UNMATCHED_API bool ReviewTooling();

/** Automation tests only: force the art look on/off (Reset -> read the command line again). */
UNMATCHED_API void SetOverrideForTest(bool bEnabled);
UNMATCHED_API void ResetOverrideForTest();

/** 'ARTLOOK art=1|0 source=default|S08GreyBoard|override heroes=v2|legacy(..) tray=on|legacy(..)|off env=on|off(..)
 *   review=0|1 legacyRender=0|1 aliases=<-ArtPreviewHeroesV2,-ArtPreviewDiorama or ->' - the effective look of this run. */
UNMATCHED_API FString TraceLine();

}  // namespace S08ArtLook
