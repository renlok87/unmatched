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
//   Run I (2026-10-05, the user's answers AB-5..AB-8 to the DE-028 A/B sheet; S08TurnPortraitWidget.h):
//   -S08TurnRingLegacy  no turn ring on the portraits (AB-5: the warm marker-turn-ring is the default).
//   -S08HeartGlowLegacy the heart damage without its red glow halo (AB-6).
//   -S08TrackerLegacy   the v3 tracker slots resource-action-full (AB-7: the DE slots filled with the action type).
//   -S08CrossLegacy     the dark heart of a fallen hero and the text X of "no defense" (AB-8: resource-hp-fallen at the
//                       heart mark, marker-x-stamp in the combat panel).
//   VS-1 HB-09 (02-visual-design.md §13.3; ВР-62): -S08DpiLegacy - the engine DPI curve (720 -> 0.666) instead of the
//                       project one (720 -> 0.75): UI/UmHudScale.h; traced as dpi=legacy(-S08DpiLegacy).
//   VS-1 CP-02 (ВР-CP08, 02 §6.1 / §6.4): the real avatars and card scans (UI/UmCardMedia.h registry) are the default;
//   -S08PortraitLegacy  the portraits as before: the team-colour disc + monogram (traced portraits=legacy(..)).
//   -S08CardArtLegacy   the card face is the 02 §6.1 fallback without the scan, the back the card.navy plate with the
//                       resource-card icon (traced cards=legacy(..)).
//   VS-2 HB-06 (04 §5.1, ВР-H15): the UMG HUD root (UI/UmHudRoot.h) and its layout are the default;
//   -S08SlateHud        the whole HUD as before the step (traced hudImpl=slate); -S08SlateHud=<key>,.. only those
//                       blocks (hudImpl=slate:<keys>).
// -ArtPreviewHeroesV2 / -ArtPreviewDiorama stay accepted as no-op aliases (scripts pass them).
//
// The trace tags of the art path stay 'ARTPREVIEW ...' (every gate script and tool reads them); one 'ARTLOOK ...' line
// per board actor states the effective look and the flags it came from.
//
// VS-1 HB-01 (docs/game-design/visual/04-hud-spec.md §5.1, §5.2 step H0a; ВР-35): -S09Markers is the debug layer of the
// S09/S10 gates - the pixel markers of the command panel (AddMarker), the result stripe, the seq/phase and
// you:/opponent: lines, the command echo and AUTO toasts, the "UNMATCHED S08 grey flow" title, the F10 operator panel.
// Every tools/s09/run-*.ps1 and tools/s10/run-*.ps1 passes it explicitly. Step H0a kept the layer on by default; step
// H0b (HB-02) turns the default OFF (MarkersDefault): the player sees none of it - the list is UI/S08HudDebug.h.
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

/** -S09Markers: the debug layer of the S09/S10 gates (see the file comment). */
inline const TCHAR* const MarkersFlagName = TEXT("S09Markers");
/** The debug layer without the flag: off since step H0b (HB-02) - the layer is opt-in for the gates. */
inline constexpr bool MarkersDefault = false;
/** World-free rule: the debug layer with -S09Markers, otherwise MarkersDefault. */
constexpr bool DecideMarkers(bool bMarkersFlag) { return bMarkersFlag || MarkersDefault; }
/** True when the gate debug layer is drawn: -S09Markers on the command line, or MarkersDefault (or the test override). */
UNMATCHED_API bool S08Markers();
/** Automation tests only: force the debug layer on/off (Reset -> read the command line again). */
UNMATCHED_API void SetMarkersOverrideForTest(bool bOn);
UNMATCHED_API void ResetMarkersOverrideForTest();

/** -S08PortraitLegacy: the portraits fall back to the team disc + monogram (VS-1 CP-02, ВР-CP08). */
inline const TCHAR* const PortraitLegacyFlagName = TEXT("S08PortraitLegacy");
/** -S08CardArtLegacy: the card faces / backs fall back to the 02 §6.1 plate without the scan (VS-1 CP-02, ВР-CP08). */
inline const TCHAR* const CardArtLegacyFlagName = TEXT("S08CardArtLegacy");
/** World-free rule of both: the accepted media unless the rollback flag is on the command line. */
constexpr bool DecideCardMedia(bool bLegacyFlag) { return !bLegacyFlag; }
/** True unless -S08PortraitLegacy: portraits show the hero / sidekick avatar textures (registry UI/UmCardMedia.h). */
UNMATCHED_API bool PortraitAvatars();
/** True unless -S08CardArtLegacy: card faces show the scan, backs the original card back. */
UNMATCHED_API bool CardArt();
/** The ARTLOOK fields of CP-02: "portraits=avatar|legacy(-S08PortraitLegacy) cards=art|legacy(-S08CardArtLegacy)". */
UNMATCHED_API FString CardMediaField(const TCHAR* CommandLine);

/** VS-2 HB-06 (04 §5.1, ВР-36, ВР-H15, ВР-HB01): the UMG HUD root is the default; -S08SlateHud rolls the whole HUD back
 *  to the Slate path of before the step (no root, no layout fixes), -S08SlateHud=<key>,<key> only the named blocks
 *  (regression hunt). Keys of the match HUD (04 §4.2 / §2): SlateHudKeys; the screens add their own (inspect, ...).
 *  tag, plate, damage = the world layer as before (12/11 su, #161A28, "H1", "-N" 18) - that is today's look until H12,
 *  the existing -ArtHudImpl=slate is a separate switch and does not change. */
inline const TCHAR* const SlateHudFlagName = TEXT("S08SlateHud");
/** The block keys -S08SlateHud=<list> knows (unknown keys are kept and reported, never fatal). */
inline const TCHAR* const SlateHudKeys[] = {
    TEXT("top"),   TEXT("status"),  TEXT("banner"), TEXT("panels"), TEXT("opphand"), TEXT("hand"),  TEXT("decks"),
    TEXT("deckpanel"), TEXT("actions"), TEXT("combat"), TEXT("pending"), TEXT("slot"), TEXT("log"), TEXT("toast"),
    TEXT("sub"),   TEXT("tag"),     TEXT("plate"),  TEXT("damage"), TEXT("cursor"), TEXT("inspect")};
/** What -S08SlateHud asked for: nothing (UMG root, every block on the new path), everything, or a block list. */
struct UNMATCHED_API FS08SlateHudBlocks {
  bool bAll = false;
  TArray<FName> Blocks;    // lower case, in command-line order, no duplicates
  TArray<FName> Unknown;   // keys not in SlateHudKeys (still honoured - a screen may own them)
  /** True when Key is drawn by the old Slate path (the whole HUD rolled back, or Key listed). */
  bool IsSlate(FName Key) const { return bAll || Blocks.Contains(Key); }
  /** The UMG root is built (anything but the whole-HUD rollback). */
  bool UmgRoot() const { return !bAll; }
  /** 'umg', 'slate' or 'slate:<key>,<key>' (ARTLOOK hudImpl=, 04 §4.5). */
  FString ImplField() const;
};
/** World-free parse of one command line: '-S08SlateHud' / '-S08SlateHud=' -> all; '-S08SlateHud=hand,decks' -> list. */
UNMATCHED_API FS08SlateHudBlocks ParseSlateHud(const TCHAR* CommandLine);
/** This process's -S08SlateHud (read per call from the command line, or the test override); the grey board
 *  (-S08GreyBoard, the S09 stand run-hud-demo) is always the whole Slate HUD (ВР-36). */
UNMATCHED_API FS08SlateHudBlocks SlateHudBlocks();
/** Automation tests only: force a -S08SlateHud value ("" = umg, "*" = all, "a,b" = list); Reset reads the command line. */
UNMATCHED_API void SetSlateHudOverrideForTest(const FString& Value);
UNMATCHED_API void ResetSlateHudOverrideForTest();

/** 'ARTLOOK art=1|0 source=default|S08GreyBoard|override heroes=v2|legacy(..) tray=on|legacy(..)|off env=on|off(..)
 *   review=0|1 legacyRender=0|1 markers=0|1 aliases=<-ArtPreviewHeroesV2,-ArtPreviewDiorama,-S08HeartGlow or ->
 *   hud=ring:<id>|legacy(..),glow:on|legacy(..),tracker:de|legacy(..),cross:on|legacy(..) dpi=project|legacy(..)
 *   portraits=avatar|legacy(..) cards=art|legacy(..) hudImpl=umg|slate[:<list>]' - the effective look of this run (the
 *   hud field: FS08TurnHudLook::ArtLookField; dpi: UmHudScale::ArtLookField, HB-09; portraits / cards: CardMediaField,
 *   CP-02; hudImpl: FS08SlateHudBlocks::ImplField, HB-06). */
UNMATCHED_API FString TraceLine();

}  // namespace S08ArtLook
