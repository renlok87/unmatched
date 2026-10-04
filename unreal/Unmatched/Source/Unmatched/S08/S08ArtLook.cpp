#include "S08ArtLook.h"

#include "S08ArtPreviewMedusa.h"
#include "S08Diorama.h"
#include "S08EnvLayout.h"
#include "S08HeroesV2.h"
#include "S08Render.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

namespace S08ArtLook {
namespace {
// -1 = read the command line, 0/1 = automation override.
int32 GOverride = -1;
}  // namespace

bool Enabled() {
  if (GOverride >= 0) return GOverride == 1;
  return Decide(FParse::Param(FCommandLine::Get(), GreyBoardFlagName));
}

bool ReviewTooling() { return FParse::Param(FCommandLine::Get(), ReviewFlagName); }

void SetOverrideForTest(bool bEnabled) { GOverride = bEnabled ? 1 : 0; }

void ResetOverrideForTest() { GOverride = -1; }

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
  return FString::Printf(TEXT("ARTLOOK art=%d source=%s heroes=%s tray=%s env=%s review=%d legacyRender=%d aliases=%s%s"),
                         bArt ? 1 : 0, Source, *Heroes, *Tray, *Env, ReviewTooling() ? 1 : 0,
                         S08LegacyRender() ? 1 : 0, Aliases.Num() ? *FString::Join(Aliases, TEXT(",")) : TEXT("-"),
                         bArt ? TEXT("") : TEXT(" (grey board: no art profile, figures, tray or art HUD layer)"));
}

}  // namespace S08ArtLook
