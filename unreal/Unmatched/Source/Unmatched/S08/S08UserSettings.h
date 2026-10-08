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
// DE-024 adds UI-ACC-012 "rule hints" (bRuleHints; flag -S08RuleHints=on|off, ResolveRuleHints).
// VS-1 HB-09 adds UI-ACC-001 "UI scale" (UiScalePercent, 75-150 %, console uiScale=; applied by S08/UI/UmHudScale.h).
//
// DE-025 (W-24; 02 SD-49, SD-55): the volumes "master" and "ambience" with their mutes are stored here (no UI-ACC rows
// yet - they come with the settings screen GD-047 and the backdrop sound SD-51; DE-032 applies them, AudioNow). Save
// broadcasts OnChanged: a running client re-reads the motion settings without a restart (the next move seq and the
// next combat staging use the new speed). Until the settings screen exists the console command
//   s08.Settings [speed=<none|fast|normal|slow>] [reduced=0|1] [shake=0|1] [ruleHints=0|1] [master=<0-100>]
//                [masterMute=0|1] [ambience=<0-100>] [ambienceMute=0|1] [music=<0-100>] [sfx=<0-100>] [ui=<0-100>]
//                [vo=<0-100>] [subtitles=0|1] [describeSounds=0|1]   (AU-S4)
// changes the saved values, saves them and broadcasts OnChanged (no arguments: prints the current values).
#pragma once

#include "CoreMinimal.h"
#include "UObject/Object.h"
#include "S08MoveAnim.h"
#include "S08UserSettings.generated.h"

/** DE-025: the stored volumes (percent 0-100, clamped on read) and mutes; DE-032 applies them to the sound mix. */
struct UNMATCHED_API FS08AudioSettings {
  int32 MasterPercent = 100;
  bool bMasterMuted = false;
  int32 AmbiencePercent = 60;
  bool bAmbienceMuted = false;
  // AU-S4 (docs/game-design/audio/02-audio-design.md §5.1; 02-ux-ui-spec UI-ACC-007..009 + the new VO and subtitle
  // rows UI-ACC-014..016):
  int32 MusicPercent = 60;        // UI-ACC-007
  int32 SfxPercent = 80;          // UI-ACC-008 "Эффекты"
  int32 UiPercent = 80;           // UI-ACC-009 "Интерфейс"
  int32 VoPercent = 80;           // UI-ACC-014 "Голоса"
  bool bSubtitles = true;         // UI-ACC-015
  bool bDescribeSounds = false;   // UI-ACC-016 "Описывать звуки"
  /** The ambience gain 0..1 after the master volume and both mutes (the backdrop sound, SD-51). */
  float AmbienceGain() const;
  /** The master gain 0..1 after its mute. */
  float MasterGain() const;
  /** The gain 0..1 of a bus WITHOUT master (master is the device volume): Music / SFX / UI / VO / Ambience (with its
   *  mute); 1 for an unknown class. */
  float BusGain(const FString& SoundClass) const;
  bool operator==(const FS08AudioSettings& Other) const {
    return MasterPercent == Other.MasterPercent && bMasterMuted == Other.bMasterMuted &&
           AmbiencePercent == Other.AmbiencePercent && bAmbienceMuted == Other.bAmbienceMuted &&
           MusicPercent == Other.MusicPercent && SfxPercent == Other.SfxPercent && UiPercent == Other.UiPercent &&
           VoPercent == Other.VoPercent && bSubtitles == Other.bSubtitles && bDescribeSounds == Other.bDescribeSounds;
  }
};

DECLARE_MULTICAST_DELEGATE(FS08UserSettingsChanged);

UCLASS(config = GameUserSettings)
class UNMATCHED_API US08UserSettings : public UObject {
  GENERATED_BODY()

public:
  /** The settings object (the class default object, loaded from GameUserSettings.ini). */
  static US08UserSettings* Get();

  /** Resets the values to the defaults (not saved). */
  void SetToDefaults();
  /** Writes the values to the saved GameUserSettings.ini and broadcasts OnChanged (applied without a restart). */
  void Save();

  /** DE-025: fired after Save (and by NotifyChanged): a running client re-reads the settings. */
  static FS08UserSettingsChanged OnChanged;
  static void NotifyChanged() { OnChanged.Broadcast(); }

  /** Sets one value by its console name (speed, reduced, shake, ruleHints, master, masterMute, ambience,
   *  ambienceMute, ..., uiScale); false and an error text for an unknown name or a bad value (nothing changed then). */
  bool ApplySetting(const FString& Name, const FString& Value, FString& OutError);
  /** The values as one trace token list: "speed=normal reduced=0 shake=1 ruleHints=1 master=100 ...". */
  FString Describe() const;

  /** The saved volumes, clamped to 0-100. */
  FS08AudioSettings GetSavedAudio() const;
  void SetSavedAudio(const FS08AudioSettings& Audio);
  /** The saved volumes of the settings object (no command-line overrides: there are no volume flags). */
  static FS08AudioSettings AudioNow();

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

  /** DE-025 (SD-55): DE "Master" + mute - the overall volume, percent 0-100. */
  UPROPERTY(config)
  int32 MasterVolume = 100;

  UPROPERTY(config)
  bool bMasterMuted = false;

  /** DE-025 (SD-55): DE "Ambience" + mute - the backdrop sound (SD-51), percent 0-100. */
  UPROPERTY(config)
  int32 AmbienceVolume = 60;

  UPROPERTY(config)
  bool bAmbienceMuted = false;

  /** AU-S4 (02-audio-design §5.1): the bus volumes, percent 0-100 (UI-ACC-007..009, UI-ACC-014). */
  UPROPERTY(config)
  int32 MusicVolume = 60;

  UPROPERTY(config)
  int32 SfxVolume = 80;

  UPROPERTY(config)
  int32 UiVolume = 80;

  UPROPERTY(config)
  int32 VoVolume = 80;

  /** UI-ACC-015: VO subtitles (on by default, 02 §3.4). */
  UPROPERTY(config)
  bool bSubtitles = true;

  /** UI-ACC-016: describe meaningful wordless sounds in the subtitle line (off by default). */
  UPROPERTY(config)
  bool bDescribeSounds = false;

  /** VS-1 HB-09, UI-ACC-001 (04-hud-spec §1.8 PAUSE "Интерфейс", §3.6; 02 §3.2, ВР-62): the player UI scale in percent,
   *  75-150 in steps of 5, 100 by default. Stored as set; S08/UI/UmHudScale.cpp applies it as ApplicationScale on top of
   *  the DPI curve and raises it to 100 % while the short side of the window is under 1080. The PAUSE screen only shows
   *  the slider and calls Save when it is released; console: s08.Settings uiScale=<75-150>. */
  UPROPERTY(config)
  int32 UiScalePercent = 100;

  /** 75..150, rounded to the nearest step of 5 (an ini value out of range reads clamped). */
  static int32 ClampUiScalePercent(int32 Percent);
  /** The saved UI scale, clamped (ClampUiScalePercent). */
  int32 GetSavedUiScalePercent() const { return ClampUiScalePercent(UiScalePercent); }
  /** "uiScale=<percent>" - kept out of Describe, whose exact text other tests pin. */
  FString DescribeUi() const;

  /** UI-ACC-012 of this run: -S08RuleHints=on|off (also 1|0, true|false; any case) wins over the saved value; another
   *  value keeps it. */
  static bool ResolveRuleHints(bool bSaved, const TCHAR* CommandLine);
  /** The saved value with the flag of this process applied. */
  static bool RuleHintsNow();

  /** VS-4 HB-43, UI-ACC-017 (04 §2.11, ВР-H09, ВР-HB07): the key chips of the HUD buttons and the status line -
   *  auto (the first match of the profile only: CompletedMatches = 0) | on | off; auto by default. The PAUSE screen
   *  (SC-24) only shows the switch; console: s08.Settings keyHints=auto|on|off. */
  UPROPERTY(config)
  FString KeyHintsMode = TEXT("auto");

  /** VS-4 HB-43 (ВР-HB07): the matches of this profile that reached GAME_OVER (NoteMatchCompleted); «Авто» shows the
   *  chips while it is 0. */
  UPROPERTY(config)
  int32 CompletedMatches = 0;

  /** auto | on | off of a value (any case; an unknown value reads as auto). */
  static FString NormalizeKeyHintsMode(const FString& Mode);
  /** World-free rule: on -> shown, off -> hidden, auto -> shown while no match was completed. */
  static bool KeyHintsShown(const FString& Mode, int32 InCompletedMatches);
  /** UI-ACC-017 of this run: -S08KeyHints=auto|on|off wins over the saved mode; another value keeps it. */
  static FString ResolveKeyHintsMode(const FString& Saved, const TCHAR* CommandLine);
  /** The mode of this run (saved value + flag) and whether the chips show now. */
  static FString KeyHintsModeNow();
  static bool KeyHintsNow();
  /** GAME_OVER of a match: CompletedMatches + 1, saved (no OnChanged broadcast: nothing else re-reads it). */
  static void NoteMatchCompleted();
  /** "keyHints=<mode> completedMatches=<n>" - kept out of Describe, whose exact text other tests pin. */
  FString DescribeKeyHints() const;

  /** VS-7 SC-26, UI-ACC-010 (04 §1.8 «Интерфейс» → «Язык»): the UI language ru | en, ru by default; the PAUSE screen and
   *  the LOGIN chips set it (console s08.Settings language=ru|en). -S08Lang=ru|en|pseudo wins for the run (pseudo = the
   *  RU texts with the +30 % pseudo-locale, UmText::IsPseudo; a check flag, never saved). */
  UPROPERTY(config)
  FString Language = TEXT("ru");

  /** ru | en of a value (any case; an unknown value reads as ru). */
  static FString NormalizeLanguage(const FString& InLanguage);
  /** The language of this run: -S08Lang=ru|en|pseudo, else the saved one (normalized). */
  static FString ResolveLanguage(const FString& Saved, const TCHAR* CommandLine);
  /** "language=<ru|en>" - kept out of Describe, whose exact text other tests pin. */
  FString DescribeLanguage() const;
};
