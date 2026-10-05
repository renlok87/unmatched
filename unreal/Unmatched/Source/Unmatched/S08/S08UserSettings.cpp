#include "S08UserSettings.h"
#include "HAL/IConsoleManager.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

US08UserSettings* US08UserSettings::Get() { return GetMutableDefault<US08UserSettings>(); }

void US08UserSettings::SetToDefaults() {
  SetSavedMotion(FS08MotionSettings());
  bRuleHints = true;
}

void US08UserSettings::Save() { SaveConfig(); }

FS08MotionSettings US08UserSettings::GetSavedMotion() const {
  FS08MotionSettings Out;
  Out.bReducedMotion = bReducedMotion;
  Out.bScreenShake = bScreenShake;
  S08Motion::ParseSpeed(AnimSpeed, Out.Speed);
  return Out;
}

bool US08UserSettings::ResolveRuleHints(bool bSaved, const TCHAR* CommandLine) {
  FString Value;
  if (!CommandLine || !FParse::Value(CommandLine, TEXT("S08RuleHints="), Value)) return bSaved;
  Value.TrimStartAndEndInline();
  if (Value.Equals(TEXT("off"), ESearchCase::IgnoreCase) || Value == TEXT("0") ||
      Value.Equals(TEXT("false"), ESearchCase::IgnoreCase)) {
    return false;
  }
  if (Value.Equals(TEXT("on"), ESearchCase::IgnoreCase) || Value == TEXT("1") ||
      Value.Equals(TEXT("true"), ESearchCase::IgnoreCase)) {
    return true;
  }
  return bSaved;
}

bool US08UserSettings::RuleHintsNow() {
  const US08UserSettings* Settings = Get();
  return ResolveRuleHints(Settings ? Settings->bRuleHints : true, FCommandLine::Get());
}

void US08UserSettings::SetSavedMotion(const FS08MotionSettings& Motion) {
  bReducedMotion = Motion.bReducedMotion;
  bScreenShake = Motion.bScreenShake;
  AnimSpeed = S08Motion::SpeedName(Motion.Speed);
}

FS08MotionSettings S08Motion::Current() {
  const US08UserSettings* Settings = US08UserSettings::Get();
  const FS08MotionSettings Saved = Settings ? Settings->GetSavedMotion() : FS08MotionSettings();
  // s08.ReducedMotion lives in S08IconMotion.cpp (HUD icon motion, UI-ACC-005/006).
  static IConsoleVariable* const ReducedCVar = IConsoleManager::Get().FindConsoleVariable(TEXT("s08.ReducedMotion"));
  return Resolve(Saved, FCommandLine::Get(), ReducedCVar && ReducedCVar->GetInt() > 0);
}
