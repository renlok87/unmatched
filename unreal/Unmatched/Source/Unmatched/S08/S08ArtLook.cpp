#include "S08ArtLook.h"

#include "S08ArtPreviewMedusa.h"
#include "Fx/S08CueFx.h"
#include "S08Diorama.h"
#include "S08EnvLayout.h"
#include "S08Facing.h"
#include "S08HeroesV2.h"
#include "S08MoveAnim.h"
#include "S08Render.h"
#include "S08TurnPortraitWidget.h"
#include "UI/UmHudScale.h"
#include "UI/UmTeamChip.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

namespace S08ArtLook {
namespace {
// -1 = read the command line, 0/1 = automation override.
int32 GOverride = -1;
// -1 = read the command line, 0/1 = automation override of the -S09Markers debug layer.
int32 GMarkersOverride = -1;
}  // namespace

bool Enabled() {
  if (GOverride >= 0) return GOverride == 1;
  return Decide(FParse::Param(FCommandLine::Get(), GreyBoardFlagName));
}

bool ReviewTooling() { return FParse::Param(FCommandLine::Get(), ReviewFlagName); }

void SetOverrideForTest(bool bEnabled) { GOverride = bEnabled ? 1 : 0; }

void ResetOverrideForTest() { GOverride = -1; }

bool S08Markers() {
  if (GMarkersOverride >= 0) return GMarkersOverride == 1;
  return DecideMarkers(FParse::Param(FCommandLine::Get(), MarkersFlagName));
}

void SetMarkersOverrideForTest(bool bOn) { GMarkersOverride = bOn ? 1 : 0; }

void ResetMarkersOverrideForTest() { GMarkersOverride = -1; }

bool PortraitAvatars() { return DecideCardMedia(FParse::Param(FCommandLine::Get(), PortraitLegacyFlagName)); }

bool CardArt() { return DecideCardMedia(FParse::Param(FCommandLine::Get(), CardArtLegacyFlagName)); }

FString CardMediaField(const TCHAR* CommandLine) {
  const bool bPortraitLegacy = CommandLine && FParse::Param(CommandLine, PortraitLegacyFlagName);
  const bool bCardLegacy = CommandLine && FParse::Param(CommandLine, CardArtLegacyFlagName);
  return FString::Printf(TEXT("portraits=%s cards=%s"),
                         DecideCardMedia(bPortraitLegacy) ? TEXT("avatar") : *FString::Printf(TEXT("legacy(-%s)"), PortraitLegacyFlagName),
                         DecideCardMedia(bCardLegacy) ? TEXT("art") : *FString::Printf(TEXT("legacy(-%s)"), CardArtLegacyFlagName));
}

FString TraceLine() {
  const TCHAR* Cmd = FCommandLine::Get();
  const bool bArt = Enabled();
  const TCHAR* Source = GOverride >= 0                                  ? TEXT("override")
                        : FParse::Param(Cmd, GreyBoardFlagName) ? TEXT("S08GreyBoard")
                                                                         : TEXT("default");
  // Figures: v2 by default; the reason of a legacy run (the rollback flag, or the six-Medusa review).
  FString Heroes = TEXT("v2");
  if (!S08HeroesV2::FlagEnabled()) {
    Heroes = S08HeroesV2::LegacyRequested() ? FString::Printf(TEXT("legacy(-%s)"), S08HeroesV2::LegacyFlagName)
             : S08ArtPreviewAllMedusa()     ? FString(TEXT("legacy(-ArtPreviewAllMedusa)"))
                                            : FString(TEXT("legacy(override)"));
  }
  FString Tray = TEXT("on");
  if (!S08Diorama::FlagEnabled()) {
    Tray = S08Diorama::LegacyRequested() ? FString::Printf(TEXT("legacy(-%s)"), S08Diorama::LegacyFlagName)
                                         : FString(TEXT("legacy(override)"));
  }
  const FString Env = !S08Diorama::FlagEnabled() ? FString(TEXT("off(no tray)"))
                      : S08EnvLayout::OptOut()   ? FString::Printf(TEXT("off(-%s)"), S08EnvLayoutSpec::NoEnvFlagName)
                                                 : FString(TEXT("on"));
  TArray<FString> Aliases;
  if (FParse::Param(Cmd, S08HeroesV2::FlagName)) Aliases.Add(FString(TEXT("-")) + S08HeroesV2::FlagName);
  if (FParse::Param(Cmd, S08Diorama::FlagName)) Aliases.Add(FString(TEXT("-")) + S08Diorama::FlagName);
  // On the grey board the figure / tray choice is not consulted (no art board): the fields still say what an art board
  // of this run would show.
  if (FParse::Param(Cmd, TEXT("S08HeartGlow"))) Aliases.Add(TEXT("-S08HeartGlow"));  // run I: the glow is the default
  // AN-21 (ВР-12): -S08MoveEase is a no-op alias of the now-default move ease
  if (FParse::Param(Cmd, TEXT("S08MoveEase"))) Aliases.Add(TEXT("-S08MoveEase"));
  // Run I (AB-5..AB-8): the turn HUD look of the portraits and the combat panel (S08TurnPortraitWidget.h)
  const FString HudLook = FS08TurnHudLook::ArtLookField(Cmd);
  // VS-1 HB-09: the DPI curve of this run (project ВР-62 or the -S08DpiLegacy rollback).
  const FString Dpi = UmHudScale::ArtLookField(Cmd);
  // VS-1 CP-02: the real avatars / card scans or their rollbacks (ВР-CP08).
  const FString CardMedia = CardMediaField(Cmd);
  // VS-2 IC-44 / IC-45: the v3 team chips or the -S08IconLegacy mvp-v1 chips.
  const FString Chips = UmTeamChip::ArtLookField(Cmd);
  // VS-2 HB-06: the UMG HUD root or the -S08SlateHud rollback (whole / block list).
  const FString HudImpl = SlateHudBlocks().ImplField();
  // AN-21 (ВР-12): the move ease of the ends (80 ms) with its rollback
  const FS08MoveAnimParams MoveParams = FS08MoveAnimParams::FromCommandLine(Cmd);
  const FString MoveEase = MoveParams.bEaseEnds ? FString::Printf(TEXT("ease%.0f"), MoveParams.EaseMs)
                                               : FString(TEXT("legacy(-S08MoveEaseLegacy)"));
  // AN-23 (ВР-06): the rest facing rule (three-quarter to the camera) with its rollback
  const FString Facing = S08Facing::LegacyRequested()
                             ? FString::Printf(TEXT("legacy(-%s)"), S08Facing::LegacyFlagName)
                             : FString(TEXT("v1"));
  // AN-31 (ВР-07, ВР-72): the harpy number on the base with its rollback
  const FString BaseDigit = FParse::Param(Cmd, S08HeroesV2::BaseDigitLegacyFlagName)
                                ? FString::Printf(TEXT("legacy(-%s)"), S08HeroesV2::BaseDigitLegacyFlagName)
                                : FString(TEXT("on"));
  // AN-32 (ВР-16): the heroMaterials Fix of the light profile with its rollback ("on" states the mechanism; the
  // applied heroes are counted in the 'ARTPREVIEW heroMat board' line - the profile loads after this line)
  const FString HeroMat = FParse::Param(Cmd, S08HeroesV2::HeroMatFixLegacyFlagName)
                              ? FString::Printf(TEXT("legacy(-%s)"), S08HeroesV2::HeroMatFixLegacyFlagName)
                              : FString(TEXT("on"));
  // VS-6 Z-2 (ВР-FX02): the combat FX base (systems, rim / flash writers) with its one rollback
  const FString Fx = FParse::Param(Cmd, S08CueFx::FxLegacyFlagName)
                         ? FString::Printf(TEXT("legacy(-%s)"), S08CueFx::FxLegacyFlagName)
                         : FString(TEXT("on"));
  // FX-19 (ВР-20): the white flash + cream rim of the hit, or the red fill of before
  const FString HitFx = FParse::Param(Cmd, S08CueFx::HitTintLegacyFlagName)
                            ? FString::Printf(TEXT("legacy(-%s)"), S08CueFx::HitTintLegacyFlagName)
                            : FString(TEXT("flash"));
  return FString::Printf(
      TEXT("ARTLOOK art=%d source=%s heroes=%s tray=%s env=%s review=%d legacyRender=%d markers=%d aliases=%s %s %s %s %s hudImpl=%s move=%s facing=%s baseDigit=%s heroMat=%s fx=%s hitFx=%s%s"),
      bArt ? 1 : 0, Source, *Heroes, *Tray, *Env, ReviewTooling() ? 1 : 0, S08LegacyRender() ? 1 : 0, S08Markers() ? 1 : 0,
      Aliases.Num() ? *FString::Join(Aliases, TEXT(",")) : TEXT("-"), *HudLook, *Dpi, *CardMedia, *Chips, *HudImpl,
      *MoveEase, *Facing, *BaseDigit, *HeroMat, *Fx, *HitFx,
      bArt ? TEXT("") : TEXT(" (grey board: no art profile, figures, tray or art HUD layer)"));
}

FString FS08SlateHudBlocks::ImplField() const {
  if (bAll) return TEXT("slate");
  if (Blocks.Num() == 0) return TEXT("umg");
  TArray<FString> Names;
  for (const FName& B : Blocks) Names.Add(B.ToString());
  return TEXT("slate:") + FString::Join(Names, TEXT(","));
}

FS08SlateHudBlocks ParseSlateHud(const TCHAR* CommandLine) {
  FS08SlateHudBlocks Out;
  if (!CommandLine) return Out;
  // The flag itself: '-S08SlateHud' alone (FParse::Param) or with '=' (an empty value = the whole HUD).
  FString Value;
  const FString ValueKey = FString(SlateHudFlagName) + TEXT("=");
  const FString Token = FString(TEXT("-")) + ValueKey;
  const TCHAR* At = FCString::Strifind(CommandLine, *Token);
  if (!At) {
    Out.bAll = FParse::Param(CommandLine, SlateHudFlagName);
    return Out;
  }
  // the raw value up to the next blank (FParse::Value skips the blank of an empty value and takes the next flag)
  const TCHAR* Cursor = At + Token.Len();
  const bool bQuoted = *Cursor == TEXT('"');
  if (bQuoted) ++Cursor;
  while (*Cursor && (bQuoted ? *Cursor != TEXT('"') : !FChar::IsWhitespace(*Cursor))) Value.AppendChar(*Cursor++);
  Value.TrimStartAndEndInline();
  TArray<FString> Parts;
  Value.ParseIntoArray(Parts, TEXT(","), true);
  for (FString& Part : Parts) {
    Part.TrimStartAndEndInline();
    if (Part.IsEmpty()) continue;
    const FName Key(*Part.ToLower());
    if (Out.Blocks.Contains(Key)) continue;
    Out.Blocks.Add(Key);
    bool bKnown = false;
    for (const TCHAR* Known : SlateHudKeys) bKnown |= Key == FName(Known);
    if (!bKnown) Out.Unknown.Add(Key);
  }
  if (Out.Blocks.Num() == 0) Out.bAll = true;  // '-S08SlateHud=' with nothing = the whole HUD
  return Out;
}

namespace {
bool GSlateHudOverride = false;
FString GSlateHudOverrideValue;
}  // namespace

FS08SlateHudBlocks SlateHudBlocks() {
  if (GSlateHudOverride) {
    if (GSlateHudOverrideValue.IsEmpty()) return FS08SlateHudBlocks();
    if (GSlateHudOverrideValue == TEXT("*")) return ParseSlateHud(*FString::Printf(TEXT("-%s"), SlateHudFlagName));
    return ParseSlateHud(*FString::Printf(TEXT("-%s=%s"), SlateHudFlagName, *GSlateHudOverrideValue));
  }
  // ВР-36 / ВР-VS2-12: the grey board (-S08GreyBoard: the S09 logic stand run-hud-demo) keeps the whole HUD on Slate
  FS08SlateHudBlocks Out = ParseSlateHud(FCommandLine::Get());
  if (!Enabled()) Out.bAll = true;
  return Out;
}

void SetSlateHudOverrideForTest(const FString& Value) {
  GSlateHudOverride = true;
  GSlateHudOverrideValue = Value;
}

void ResetSlateHudOverrideForTest() {
  GSlateHudOverride = false;
  GSlateHudOverrideValue.Reset();
}

}  // namespace S08ArtLook
