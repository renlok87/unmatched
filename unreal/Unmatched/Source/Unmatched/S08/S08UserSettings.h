// MS-T-16 (move-selection 04 §6.3, MS-R-54): the player's settings kept next to the engine's GameUserSettings -
// reduced motion (UI-ACC-005/006), the animation speed (UI-ACC-013) and the screen shake (UI-ACC-005 "no shake").
// The values live in the saved GameUserSettings.ini, section [/Script/Unmatched.S08UserSettings] (config =
// GameUserSettings); the class default object holds them (US08UserSettings::Get) and Save writes them back.
//
// Deviation from 04 §6.3 (MS-T-16 journal, run D): the plan made this class a UGameUserSettings subclass set by
// GameUserSettingsClassName in DefaultEngine.ini. That breaks the engine settings: a subclass reads its config keys only
// from its own section, so [/Script/Engine.GameUserSettings] FrameRateLimit=60 (ACC-022, AGENTS.md "Unreal GPU load")
// and every saved resolution would be dropped (measured: parent CDO 60, subclass CDO 0), and the demo scripts that
// stage GameUserSettings.ini (tools/s09/run-*-demo.ps1) would edit the ignored section. A plain config object in the
// same ini keeps the engine class untouched.
//
// There is no settings screen yet (UI-SCR-PAUSE is not in the client): the ini and the flags -S08ReducedMotion /
// -S08AnimSpeed=<none|fast|normal|slow> change them; the flags win over the saved values (S08Motion::Resolve).
// DE-024 adds UI-ACC-012 "rule hints" (bRuleHints; flag -S08RuleHints=on|off, ResolveRuleHints); DE-025 adds the volumes.
#pragma once

#include "CoreMinimal.h"
#include "UObject/Object.h"
#include "S08MoveAnim.h"
#include "S08UserSettings.generated.h"

UCLASS(config = GameUserSettings)
class UNMATCHED_API US08UserSettings : public UObject {
  GENERATED_BODY()

public:
  /** The settings object (the class default object, loaded from GameUserSettings.ini). */
  static US08UserSettings* Get();

  /** Resets the values to the defaults (not saved). */
  void SetToDefaults();
  /** Writes the values to the saved GameUserSettings.ini. */
  void Save();

  /** The saved motion settings (no command-line overrides). */
  FS08MotionSettings GetSavedMotion() const;
  void SetSavedMotion(const FS08MotionSettings& Motion);

  /** UI-ACC-005/006: moves snap, the HUD icon loops stand still, the hop / travel lean stop, the V-08 shake is off. */
  UPROPERTY(config)
  bool bReducedMotion = false;

  /** UI-ACC-013: none | fast | normal | slow (an unknown value reads as normal). */
  UPROPERTY(config)
  FString AnimSpeed = TEXT("normal");

  /** UI-ACC-005: false turns the V-08 screen shake (CUE-004) off. */
  UPROPERTY(config)
  bool bScreenShake = true;

  /** UI-ACC-012 (DE-024, 02 SD-42): the one-shot rule toasts (the first is the hand limit 7); false = no toasts. */
  UPROPERTY(config)
  bool bRuleHints = true;

  /** UI-ACC-012 of this run: -S08RuleHints=on|off (also 1|0, true|false; any case) wins over the saved value; another
   *  value keeps it. */
  static bool ResolveRuleHints(bool bSaved, const TCHAR* CommandLine);
  /** The saved value with the flag of this process applied. */
  static bool RuleHintsNow();
};
