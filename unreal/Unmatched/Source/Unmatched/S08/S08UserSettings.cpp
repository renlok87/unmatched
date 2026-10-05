#include "S08UserSettings.h"
#include "HAL/IConsoleManager.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "UObject/Package.h"

FS08UserSettingsChanged US08UserSettings::OnChanged;

namespace {
float Gain(int32 Percent, bool bMuted) {
  return bMuted ? 0.0f : static_cast<float>(FMath::Clamp(Percent, 0, 100)) / 100.0f;
}

/** 0/1, on/off, true/false (any case). */
bool ParseBool(const FString& Text, bool& Out) {
  const FString T = Text.TrimStartAndEnd();
  if (T == TEXT("1") || T.Equals(TEXT("on"), ESearchCase::IgnoreCase) || T.Equals(TEXT("true"), ESearchCase::IgnoreCase)) {
    Out = true;
    return true;
  }
  if (T == TEXT("0") || T.Equals(TEXT("off"), ESearchCase::IgnoreCase) ||
      T.Equals(TEXT("false"), ESearchCase::IgnoreCase)) {
    Out = false;
    return true;
  }
  return false;
}

bool ParsePercent(const FString& Text, int32& Out) {
  const FString T = Text.TrimStartAndEnd();
  if (T.IsEmpty() || !T.IsNumeric() || T.Contains(TEXT("."))) return false;
  const int32 Value = FCString::Atoi(*T);
  if (Value < 0 || Value > 100) return false;
  Out = Value;
  return true;
}
}  // namespace

float FS08AudioSettings::MasterGain() const { return Gain(MasterPercent, bMasterMuted); }

float FS08AudioSettings::AmbienceGain() const { return MasterGain() * Gain(AmbiencePercent, bAmbienceMuted); }

float FS08AudioSettings::BusGain(const FString& SoundClass) const {
  if (SoundClass == TEXT("Ambience")) return Gain(AmbiencePercent, bAmbienceMuted);
  if (SoundClass == TEXT("Music")) return Gain(MusicPercent, false);
  if (SoundClass == TEXT("SFX")) return Gain(SfxPercent, false);
  if (SoundClass == TEXT("UI")) return Gain(UiPercent, false);
  if (SoundClass == TEXT("VO")) return Gain(VoPercent, false);
  return 1.0f;
}

US08UserSettings* US08UserSettings::Get() { return GetMutableDefault<US08UserSettings>(); }

void US08UserSettings::SetToDefaults() {
  SetSavedMotion(FS08MotionSettings());
  bRuleHints = true;
  SetSavedAudio(FS08AudioSettings());
}

void US08UserSettings::Save() {
  SaveConfig();
  NotifyChanged();
}

FS08AudioSettings US08UserSettings::GetSavedAudio() const {
  FS08AudioSettings Out;
  Out.MasterPercent = FMath::Clamp(MasterVolume, 0, 100);
  Out.bMasterMuted = bMasterMuted;
  Out.AmbiencePercent = FMath::Clamp(AmbienceVolume, 0, 100);
  Out.bAmbienceMuted = bAmbienceMuted;
  Out.MusicPercent = FMath::Clamp(MusicVolume, 0, 100);
  Out.SfxPercent = FMath::Clamp(SfxVolume, 0, 100);
  Out.UiPercent = FMath::Clamp(UiVolume, 0, 100);
  Out.VoPercent = FMath::Clamp(VoVolume, 0, 100);
  Out.bSubtitles = bSubtitles;
  Out.bDescribeSounds = bDescribeSounds;
  return Out;
}

void US08UserSettings::SetSavedAudio(const FS08AudioSettings& Audio) {
  MasterVolume = FMath::Clamp(Audio.MasterPercent, 0, 100);
  bMasterMuted = Audio.bMasterMuted;
  AmbienceVolume = FMath::Clamp(Audio.AmbiencePercent, 0, 100);
  bAmbienceMuted = Audio.bAmbienceMuted;
  MusicVolume = FMath::Clamp(Audio.MusicPercent, 0, 100);
  SfxVolume = FMath::Clamp(Audio.SfxPercent, 0, 100);
  UiVolume = FMath::Clamp(Audio.UiPercent, 0, 100);
  VoVolume = FMath::Clamp(Audio.VoPercent, 0, 100);
  bSubtitles = Audio.bSubtitles;
  bDescribeSounds = Audio.bDescribeSounds;
}

FS08AudioSettings US08UserSettings::AudioNow() {
  const US08UserSettings* Settings = Get();
  return Settings ? Settings->GetSavedAudio() : FS08AudioSettings();
}

bool US08UserSettings::ApplySetting(const FString& Name, const FString& Value, FString& OutError) {
  bool Flag = false;
  int32 Percent = 0;
  if (Name.Equals(TEXT("speed"), ESearchCase::IgnoreCase)) {
    ES08AnimSpeed Speed = ES08AnimSpeed::Normal;
    if (!S08Motion::ParseSpeed(Value, Speed)) {
      OutError = FString::Printf(TEXT("speed=%s: none|fast|normal|slow"), *Value);
      return false;
    }
    AnimSpeed = S08Motion::SpeedName(Speed);
    return true;
  }
  struct FBoolSetting {
    const TCHAR* Name;
    bool US08UserSettings::*Field;
  };
  static const FBoolSetting Bools[] = {
      {TEXT("reduced"), &US08UserSettings::bReducedMotion}, {TEXT("shake"), &US08UserSettings::bScreenShake},
      {TEXT("ruleHints"), &US08UserSettings::bRuleHints},   {TEXT("masterMute"), &US08UserSettings::bMasterMuted},
      {TEXT("ambienceMute"), &US08UserSettings::bAmbienceMuted}, {TEXT("subtitles"), &US08UserSettings::bSubtitles},
      {TEXT("describeSounds"), &US08UserSettings::bDescribeSounds}};
  for (const FBoolSetting& B : Bools) {
    if (!Name.Equals(B.Name, ESearchCase::IgnoreCase)) continue;
    if (!ParseBool(Value, Flag)) {
      OutError = FString::Printf(TEXT("%s=%s: 0|1"), B.Name, *Value);
      return false;
    }
    this->*B.Field = Flag;
    return true;
  }
  struct FPercentSetting {
    const TCHAR* Name;
    int32 US08UserSettings::*Field;
  };
  static const FPercentSetting Percents[] = {
      {TEXT("master"), &US08UserSettings::MasterVolume}, {TEXT("ambience"), &US08UserSettings::AmbienceVolume},
      {TEXT("music"), &US08UserSettings::MusicVolume},   {TEXT("sfx"), &US08UserSettings::SfxVolume},
      {TEXT("ui"), &US08UserSettings::UiVolume},         {TEXT("vo"), &US08UserSettings::VoVolume}};
  for (const FPercentSetting& P : Percents) {
    if (!Name.Equals(P.Name, ESearchCase::IgnoreCase)) continue;
    if (!ParsePercent(Value, Percent)) {
      OutError = FString::Printf(TEXT("%s=%s: 0-100"), P.Name, *Value);
      return false;
    }
    this->*P.Field = Percent;
    return true;
  }
  OutError = FString::Printf(TEXT("unknown setting %s"), *Name);
  return false;
}

FString US08UserSettings::Describe() const {
  const FS08MotionSettings Motion = GetSavedMotion();
  const FS08AudioSettings Audio = GetSavedAudio();
  return FString::Printf(
      TEXT("speed=%s reduced=%d shake=%d ruleHints=%d master=%d masterMute=%d ambience=%d ambienceMute=%d music=%d "
           "sfx=%d ui=%d vo=%d subtitles=%d describeSounds=%d"),
      S08Motion::SpeedName(Motion.Speed), Motion.bReducedMotion ? 1 : 0, Motion.bScreenShake ? 1 : 0,
      bRuleHints ? 1 : 0, Audio.MasterPercent, Audio.bMasterMuted ? 1 : 0, Audio.AmbiencePercent,
      Audio.bAmbienceMuted ? 1 : 0, Audio.MusicPercent, Audio.SfxPercent, Audio.UiPercent, Audio.VoPercent,
      Audio.bSubtitles ? 1 : 0, Audio.bDescribeSounds ? 1 : 0);
}

namespace {
// DE-025: the settings without a settings screen (UI-SCR-PAUSE is not in the client yet).
FAutoConsoleCommand GS08SettingsCommand(
    TEXT("s08.Settings"),
    TEXT("DE-025: s08.Settings [speed=none|fast|normal|slow] [reduced=0|1] [shake=0|1] [ruleHints=0|1] "
         "[master=0-100] [masterMute=0|1] [ambience=0-100] [ambienceMute=0|1] - saves to GameUserSettings.ini and "
         "applies without a restart (the -S08AnimSpeed / -S08ReducedMotion / -S08RuleHints flags still win)"),
    FConsoleCommandWithArgsDelegate::CreateLambda([](const TArray<FString>& Args) {
      US08UserSettings* Settings = US08UserSettings::Get();
      if (!Settings) return;
      // All or nothing: the arguments are checked on a scratch object first (ApplySetting does not read the values).
      US08UserSettings* Probe = NewObject<US08UserSettings>(GetTransientPackage());
      for (const FString& Arg : Args) {
        FString Name, Value, Error;
        if (!Arg.Split(TEXT("="), &Name, &Value) || !Probe->ApplySetting(Name, Value, Error)) {
          UE_LOG(LogTemp, Warning, TEXT("s08.Settings: %s"), Error.IsEmpty() ? *(TEXT("not name=value: ") + Arg) : *Error);
          Probe->MarkAsGarbage();
          return;
        }
      }
      Probe->MarkAsGarbage();
      if (Args.Num() > 0) {
        for (const FString& Arg : Args) {
          FString Name, Value, Error;
          Arg.Split(TEXT("="), &Name, &Value);
          Settings->ApplySetting(Name, Value, Error);
        }
        Settings->Save();
      }
      UE_LOG(LogTemp, Display, TEXT("s08.Settings %s%s"), *Settings->Describe(), Args.Num() > 0 ? TEXT(" (saved)") : TEXT(""));
    }));
}  // namespace

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
