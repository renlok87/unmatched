// AU-S4 (docs/game-design/audio/02-audio-design.md, 05-production-plan AUC-U01..U05): the UE adapter of the music,
// the hero lines with subtitles, the map ambience and the extra CUE sounds. The decisions are world-free
// (FS08MusicDirector, FS08VoDirector, FS08AmbienceScheduler, FS08CueSound); this file loads the sounds, owns the audio
// components and calls the directors from the presentation events of the game mode:
//   - match start (first applied board): STG-MATCH-START, the map theme, the ambience, the match-start lines;
//   - CUE-008 attack / CUE-009 defense: combat music, the attack / defend lines, their sounds;
//   - the combat staging: card flips (or the no-defense stamp), effect-line bells, the slam, the lunge whoosh, the
//     block at damage 0, signature-card lines at the slam (public from the reveal on);
//   - hits (CUE-011, one "multi" sound per frame), heals (CUE-012), low HP (final stand), deaths (CUE-013), the
//     sidekick-down stings; schemes / boosts / discards of the card slot; the hand limit; the result (CUE-016).
// Music: both layers of a theme start in the same frame (sample-aligned), the director moves their gains. VO: one
// component, subtitles in a Slate line at the bottom centre (UI-ACC-015). Ambience: looping beds + scheduled spots,
// silent in -Bench (the env FX are frozen there).
// AU-S5 (07-production-log §9): Medusa's gaze head (request / beam / decline), Arthur's ability boost (and its fizzle
// when the attack card is cancelled), the push of an enemy figure, the move candidates, the placement cascade, the
// defense deadline beeps, the menu theme and the login sounds; -S08AudioRecord writes the client's output for the
// loudness pass.
#include "S08HeroesV2.h"

#include "AudioDeviceManager.h"
#include "AudioMixerDevice.h"
#include "Components/AudioComponent.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Engine/World.h"
#include "Internationalization/Culture.h"
#include "Internationalization/Internationalization.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/App.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "S08BoardActor.h"
#include "S08FlowGameMode.h"
#include "S08TraceLog.h"
#include "Sound/SampleBufferIO.h"
#include "S08MixLimiter.h"
#include "AudioMixerBlueprintLibrary.h"
#include "Sound/SoundBase.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Text/STextBlock.h"

DEFINE_LOG_CATEGORY_STATIC(LogS08Audio, Log, All);

namespace {
FString SpeakerName(const FString& Key, bool bRu) {
  if (Key == TEXT("ARTHUR")) return bRu ? TEXT("Король Артур")
                                        : TEXT("King Arthur");
  if (Key == TEXT("MERLIN")) return bRu ? TEXT("Мерлин") : TEXT("Merlin");
  if (Key == TEXT("MEDUSA")) return bRu ? TEXT("Медуза") : TEXT("Medusa");
  return Key;
}

/** Signature cards (02 §3.3, §4.7): the speaker, its line event and the effect sound. */
struct FSignatureCard {
  const TCHAR* Name;
  const TCHAR* Speaker;
  const TCHAR* Event;
  const TCHAR* Fx;
};
const FSignatureCard* FindSignature(const FString& CardName) {
  static const FSignatureCard Cards[] = {
      {TEXT("Excalibur"), TEXT("ARTHUR"), TEXT("CARD-EXCALIBUR"), TEXT("CMB-HIT-HEAVY")},
      {TEXT("The Holy Grail"), TEXT("ARTHUR"), TEXT("CARD-GRAIL"), TEXT("CMB-HEAL-GRAIL")},
      {TEXT("The Lady of the Lake"), TEXT("ARTHUR"), TEXT("CARD-LADY"), TEXT("FX-LADY-LAKE")},
      {TEXT("Prophecy"), TEXT("MERLIN"), TEXT("CARD-PROPHECY"), TEXT("FX-PROPHECY")},
      {TEXT("Command the Storms"), TEXT("MERLIN"), TEXT("CARD-STORMS"), TEXT("FX-STORM")},
      {TEXT("Restless Spirits"), TEXT("MERLIN"), TEXT("CARD-SPIRITS"), TEXT("FX-SPIRITS")},
      {TEXT("Bewilderment"), TEXT("MERLIN"), TEXT("CARD-BEWILDERMENT"), TEXT("CMB-BLOCK-ILLUSION")},
      {TEXT("Gaze of Stone"), TEXT("MEDUSA"), TEXT("CARD-GAZE-OF-STONE"), TEXT("FX-PETRIFY")},
      {TEXT("A Momentary Glance"), TEXT("MEDUSA"), TEXT("CARD-GLANCE"), TEXT("FX-GAZE-BEAM")},
      {TEXT("Winged Frenzy"), TEXT("MEDUSA"), TEXT("CARD-FRENZY"), TEXT("FX-FRENZY")},
      {TEXT("Hiss and Slither"), TEXT("MEDUSA"), TEXT("CARD-HISS"), TEXT("FX-HISS")},
      {TEXT("Feint"), TEXT(""), TEXT(""), TEXT("CRD-CANCEL")},
      {TEXT("Clutching Claws"), TEXT(""), TEXT(""), TEXT("FX-CLAWS")},
  };
  for (const FSignatureCard& C : Cards) {
    if (CardName.Equals(C.Name, ESearchCase::IgnoreCase)) return &C;
  }
  return nullptr;
}
}  // namespace

// ---------------------------------------------------------------- loading and plain playback

USoundBase* AS08FlowGameMode::LoadAudio(const FString& SoftPath) {
  if (SoftPath.IsEmpty()) return nullptr;
  TObjectPtr<UObject>* Cached = CueSoundAssets.Find(SoftPath);
  if (!Cached) {
    USoundBase* Loaded = LoadObject<USoundBase>(nullptr, *SoftPath);
    if (!Loaded) UE_LOG(LogS08Audio, Warning, TEXT("audio %s did not load"), *SoftPath);
    Cached = &CueSoundAssets.Add(SoftPath, Loaded);
  }
  return Cast<USoundBase>(Cached->Get());
}

void AS08FlowGameMode::PlayBankSfx(const FString& BankId, const TCHAR* SoundClass, const TCHAR* Tag, float GainMul) {
  const FString Path = CueSound.PickVariant(BankId);
  USoundBase* Sound = LoadAudio(Path);
  const float Gain = CueSound.ClassGain(SoundClass) * GainMul;
  FS08Trace::Write(FString::Printf(TEXT("SFX bank=%s tag=%s class=%s t=%lld sound=%s gain=%.2f"), *BankId, Tag,
                                   SoundClass, static_cast<long long>(NowMs()),
                                   Sound ? *S08SoundRows::ShortName(Path) : TEXT("missing"),
                                   CueSound.GetAudio().MasterGain() * Gain));
  if (Sound && Gain > 0.0f) UGameplayStatics::PlaySound2D(this, Sound, Gain, 1.0f, 0.0f, nullptr, nullptr, false);
  // AU-S5: an effect with a voice layer (the hiss, the prophecy whisper, the gaze whisper) plays it with the effect,
  // on the voice bus
  if (BankId.StartsWith(TEXT("FX-")) && !BankId.EndsWith(TEXT("-VOICE"))) {
    const FString Layer = BankId + TEXT("-VOICE");
    if (S08AudioBank::Find(Layer)) PlayBankSfx(Layer, TEXT("VO"), TEXT("voice"));
  }
}

void AS08FlowGameMode::PlayCueBank(const TCHAR* CueId, const FString& Subject, int32 Seq, const FString& BankId) {
  FS08SoundRequest Request;
  Request.Point = ES08SoundPoint::Cue;
  Request.CueId = CueId;
  Request.Subject = Subject;
  Request.Seq = Seq;
  Request.EventMs = NowMs();
  Request.BankId = BankId;
  PlayCueSound(Request);
}

void AS08FlowGameMode::DelaySound(int32 InMs, const FString& BankId, const TCHAR* SoundClass, const TCHAR* Tag) {
  FS08DelayedSound D;
  D.DueMs = NowMs() + InMs;
  D.BankId = BankId;
  D.SoundClass = SoundClass;
  D.Tag = Tag;
  DelayedSounds.Add(D);
}

// ---------------------------------------------------------------- runtime

void AS08FlowGameMode::InitAudioRuntime() {
  FParse::Value(FCommandLine::Get(), TEXT("S08AudioRecord="), AudioRecordFile);
  InstallMasterLimiter();
  const int32 Seed = 0x5EED;
  Vo.NewMatch(Seed);
  AudioRng.Initialize(Seed);
  if (GEngine && GEngine->GameViewport && !SubtitleBox.IsValid()) {
    SubtitleBox = SNew(SBox)
                      .HAlign(HAlign_Center)
                      .VAlign(VAlign_Bottom)
                      .Padding(FMargin(0.0f, 0.0f, 0.0f, 210.0f))
                      .Visibility(EVisibility::Collapsed)[SAssignNew(SubtitleText, STextBlock)
                                                              .Font(FCoreStyle::GetDefaultFontStyle("Bold", 20))
                                                              .ColorAndOpacity(FLinearColor(0.97f, 0.95f, 0.88f))
                                                              .ShadowOffset(FVector2D(1.5f, 1.5f))
                                                              .ShadowColorAndOpacity(FLinearColor(0, 0, 0, 0.85f))
                                                              .Justification(ETextJustify::Center)
                                                              .WrapTextAt(900.0f)];
    GEngine->GameViewport->AddViewportWidgetContent(SubtitleBox.ToSharedRef(), 40);
  }
}

void AS08FlowGameMode::ShutdownAudioRuntime() {
  StopAudioRecording(TEXT("end"));
  RemoveMasterLimiter();
  if (GEngine && GEngine->GameViewport && SubtitleBox.IsValid()) {
    GEngine->GameViewport->RemoveViewportWidgetContent(SubtitleBox.ToSharedRef());
  }
  SubtitleBox.Reset();
  SubtitleText.Reset();
}

void AS08FlowGameMode::StartTheme(const FString& Theme) {
  if (MusicL1) MusicL1->Stop();
  if (MusicL2) MusicL2->Stop();
  MusicL1 = nullptr;
  MusicL2 = nullptr;
  if (Theme.IsEmpty()) return;
  USoundBase* L1 = LoadAudio(CueSound.PickVariant(Theme + TEXT("-L1")));
  USoundBase* L2 = LoadAudio(CueSound.PickVariant(Theme + TEXT("-L2")));
  // both layers start in this frame: the same audio render block, sample-aligned (02 §2.3)
  if (L1) MusicL1 = UGameplayStatics::CreateSound2D(this, L1, 0.001f, 1.0f, 0.0f, nullptr, false, false);
  if (L2) MusicL2 = UGameplayStatics::CreateSound2D(this, L2, 0.001f, 1.0f, 0.0f, nullptr, false, false);
  if (MusicL1) MusicL1->Play();
  if (MusicL2) MusicL2->Play();
  FS08Trace::Write(FString::Printf(TEXT("MUSIC theme=%s t=%lld l1=%s l2=%s"), *Theme, static_cast<long long>(NowMs()),
                                   L1 ? TEXT("ok") : TEXT("missing"), L2 ? TEXT("ok") : TEXT("missing")));
}

void AS08FlowGameMode::FlushPendingHits() {
  // hits of this frame: one sound, the rest grouped (02 §4.5). Called at the end of the frame (HandleEndFrame), after
  // every presentation of the tick (the deferred cascade damage comes late in Tick) - the sound stays in its frame.
  if (!PendingHits.Num()) return;
  TArray<FString> Lines;
  const int64 Now = NowMs();
  const bool bMulti = PendingHits.Num() > 1;
  bool bExhaust = bMulti;
  for (const FS08PendingHit& H : PendingHits) bExhaust &= !H.bStaged && H.Damage == 2;
  for (int32 I = 0; I < PendingHits.Num(); ++I) {
    FS08SoundRequest R = PendingHits[I].Request;
    if (I == 0) {
      if (bMulti) R.BankId = bExhaust ? TEXT("CMB-EXHAUST") : TEXT("CMB-HIT-MULTI");
      PlayCueSound(R);
    } else {
      CueSound.Grouped(R, Now, Lines);
    }
  }
  PendingHits.Reset();
  WriteCueLines(Lines);
}

void AS08FlowGameMode::TickAudioRuntime() {
  const int64 Now = NowMs();
  TArray<FString> Lines;
  // delayed one-shots (dissolve after the settle, VO answers, the result lines)
  for (int32 I = 0; I < DelayedSounds.Num();) {
    if (DelayedSounds[I].DueMs > Now) {
      ++I;
      continue;
    }
    const FS08DelayedSound D = DelayedSounds[I];
    DelayedSounds.RemoveAt(I);
    if (D.SoundClass == TEXT("VO")) {
      OfferVoLine(D.BankId, D.Tag, D.bAnswer);
    } else {
      PlayBankSfx(D.BankId, *D.SoundClass, *D.Tag);
    }
  }
  // AU-S5: the gaze request waits for the end of a combat staging (the head opens "after combat")
  if (bAudioGazeRequestDue && !CombatStage.IsActive()) {
    bAudioGazeRequestDue = false;
    PlayBankSfx(TEXT("FX-GAZE-REQUEST"), TEXT("SFX"), TEXT("gaze"));
  }
  if (bAudioRecording && AudioRecordStopMs > 0 && Now >= AudioRecordStopMs) StopAudioRecording(TEXT("result"));
  TickAudioWatchers();
  // music
  const FS08MusicMix Mix = Music.Mix(Now);
  if (Mix.bThemeChanged) StartTheme(Mix.Theme);
  const float MusicBus = CueSound.ClassGain(TEXT("Music"));
  if (MusicL1) MusicL1->SetVolumeMultiplier(FMath::Max(0.001f, Mix.L1 * MusicBus));
  if (MusicL2) MusicL2->SetVolumeMultiplier(FMath::Max(0.001f, Mix.L2 * MusicBus));
  for (const FString& Sting : Music.TakeStings()) {
    if (Sting == TEXT("STG-MATCH-START") || Sting.StartsWith(TEXT("STG-SIDEKICK")) || Sting == TEXT("STG-HAND-LIMIT")) {
      PlayBankSfx(Sting, Sting == TEXT("STG-HAND-LIMIT") ? TEXT("UI") : TEXT("Music"), TEXT("sting"));
    }
    // the result sting is the CUE-016 sound (PlayResultSting)
  }
  // VO end: the component stopped (the director then takes the next line, the music duck releases)
  if (bVoPlaying && (!VoAudio || !VoAudio->IsPlaying())) {
    bVoPlaying = false;
    Vo.Finished(Now);
    Music.SetVoActive(false, Now);
  }
  // subtitles
  if (SubtitleBox.IsValid() && SubtitleUntilMs > 0 && Now >= SubtitleUntilMs) {
    SubtitleBox->SetVisibility(EVisibility::Collapsed);
    SubtitleUntilMs = 0;
  }
  // ambience: beds follow the bus volume and the combat duck; spots on their schedule
  const float AmbDuck = Music.GetState() == ES08MusicState::Combat ? 0.63f      // -4 dB
                        : Music.GetState() == ES08MusicState::HeroFallen ? 0.5f  // -6 dB
                                                                         : 1.0f;
  const float AmbBus = CueSound.ClassGain(TEXT("Ambience"));
  for (const TObjectPtr<UAudioComponent>& Bed : AmbBeds) {
    if (Bed) Bed->SetVolumeMultiplier(FMath::Max(0.001f, AmbBus * AmbDuck));
  }
  if (!bBench && AmbBeds.Num()) {
    for (const FString& Spot : Ambience.TakeDue(Now, Lines)) PlayBankSfx(Spot, TEXT("Ambience"), TEXT("spot"), AmbDuck);
  }
  // idle: 45 s of the own turn without an input (02 §3.2), at most once per turn
  if (bAudioMatchStarted && Hud.bViewerTurn && !Hud.bGameOver && !bIdleOffered && AudioLastInputMs > 0 &&
      Now - AudioLastInputMs > 45000 && AudioIdleCount < 3) {
    bIdleOffered = true;
    ++AudioIdleCount;
    OfferVoLine(TEXT("IDLE"), AudioOwnHeroKey);
  }
  WriteCueLines(Lines);
}

// ---------------------------------------------------------------- VO

void AS08FlowGameMode::OfferVoLine(const FString& Event, const FString& SpeakerKey, bool bAnswer, int32 HarpyIndex) {
  if (SpeakerKey.IsEmpty() || bBench) return;
  FS08VoOffer Offer;
  Offer.Event = Event;
  Offer.Speaker = SpeakerKey;
  Offer.HarpyIndex = HarpyIndex;
  Offer.TMs = NowMs();
  Offer.SpeedMul = CombatSpeedMul();
  Offer.bAnswer = bAnswer;
  TArray<FString> Lines;
  const FS08VoDecision D = Vo.Offer(Offer, Lines);
  WriteCueLines(Lines);
  if (!D.bPlay) return;
  USoundBase* Sound = LoadAudio(D.Path);
  const float Gain = CueSound.ClassGain(TEXT("VO"));
  if (!Sound || Gain <= 0.0f) {
    Vo.Finished(NowMs());
    return;
  }
  if (VoAudio) VoAudio->Stop();
  VoAudio = UGameplayStatics::CreateSound2D(this, Sound, Gain, 1.0f, 0.0f, nullptr, false, false);
  if (!VoAudio) {
    Vo.Finished(NowMs());
    return;
  }
  VoAudio->Play();
  bVoPlaying = true;
  const int32 LenMs = FMath::RoundToInt(Sound->GetDuration() * 1000.0f);
  Vo.Started(NowMs(), LenMs);
  Music.SetVoActive(true, NowMs());
  // subtitles (UI-ACC-015): the speaker and the line in the interface language; efforts and cries have none
  const FS08AudioSettings& Audio = CueSound.GetAudio();
  if (SubtitleBox.IsValid() && SubtitleText.IsValid() && Audio.bSubtitles) {
    const bool bRu = FInternationalization::Get().GetCurrentCulture()->GetTwoLetterISOLanguageName() == TEXT("ru");
    FString Text = bRu ? D.Ru : D.En;
    if (Text.IsEmpty() && Audio.bDescribeSounds && SpeakerKey == TEXT("HARPY")) {
      Text = bRu ? TEXT("[Гарпия кричит]")
                 : TEXT("[Harpy shrieks]");
    }
    if (!Text.IsEmpty()) {
      const FString Shown = SpeakerKey == TEXT("HARPY") ? Text : SpeakerName(SpeakerKey, bRu) + TEXT(": ") + Text;
      SubtitleText->SetText(FText::FromString(Shown));
      SubtitleBox->SetVisibility(EVisibility::HitTestInvisible);
      SubtitleUntilMs = NowMs() + LenMs + 500;
      // VS-4 HB-41: the UMG capsule (UUmHudSubtitle) shows the line - the Slate box only on -S08SlateHud=sub
      if (UmHudShowSubtitle(SpeakerKey == TEXT("HARPY") ? FString() : SpeakerName(SpeakerKey, bRu), Text, LenMs + 500)) {
        SubtitleBox->SetVisibility(EVisibility::Collapsed);
      }
      FS08Trace::Write(FString::Printf(TEXT("VO subtitle line=%s until=%lld"), *D.LineId,
                                       static_cast<long long>(SubtitleUntilMs)));
    }
  }
}

FString AS08FlowGameMode::AudioKeyOf(const FString& FighterId, int32* OutHarpyIndex) const {
  const FS08BoardFighter* F =
      Fighters.FindByPredicate([&FighterId](const FS08BoardFighter& E) { return E.Id == FighterId; });
  if (!F) return FString();
  const FString Key = S08AudioBank::CharacterKey(F->Name.IsEmpty() ? F->Label : F->Name);
  if (OutHarpyIndex && Key == TEXT("HARPY")) {
    *OutHarpyIndex = S08HeroesV2::HarpyNumber(*F);  // AN-31: one number rule - the tag, the disc and the audio key
  }
  return Key;
}

FString AS08FlowGameMode::HeroKeyOfOwner(const FString& OwnerId) const {
  for (const FS08BoardFighter& F : Fighters) {
    if (F.OwnerId == OwnerId && F.bIsHero) return S08AudioBank::CharacterKey(F.Name.IsEmpty() ? F.Label : F.Name);
  }
  return FString();
}

// ---------------------------------------------------------------- presentation hooks

void AS08FlowGameMode::AudioOnApplied(const FS08Snapshot& Snapshot, const TArray<FS08BoardFighter>& Before) {
  const int64 Now = NowMs();
  TArray<FString> Lines;
  const FString Viewer = ViewerIdNow();
  // a new game in the same process (back to the lobby, another room): the per-match audio starts over
  const FString GameId = Flow.IsValid() ? Flow->GetRoom().GameId : FString();
  if (bAudioMatchStarted && !GameId.IsEmpty() && GameId != AudioMatchGameId) ResetAudioMatch();
  // match start: the first applied board with both heroes
  if (!bAudioMatchStarted && Fighters.Num() && !Viewer.IsEmpty()) {
    AudioOwnHeroKey = HeroKeyOfOwner(Viewer);
    FString OppKey;
    for (const FS08BoardFighter& F : Fighters) {
      if (F.bIsHero && F.OwnerId != Viewer) OppKey = S08AudioBank::CharacterKey(F.Name.IsEmpty() ? F.Label : F.Name);
    }
    if (!AudioOwnHeroKey.IsEmpty()) {
      bAudioMatchStarted = true;
      AudioMatchGameId = GameId;
      const FString Board = BoardActor && !BoardActor->GetArtProfileId().IsEmpty() ? BoardActor->GetArtProfileId()
                            : Flow.IsValid()                                       ? Flow->GetRoom().BoardId
                                                                                   : FString();
      AudioMapKey = S08Ambience::MapKeyOf(Board);
      Vo.NewMatch(Snapshot.SequenceNumber * 7919 + 17);
      if (!bBench) {
        Music.StartMatch(AudioMapKey.IsEmpty() ? TEXT("MARMOREAL") : AudioMapKey, Now, Lines);
        StartAmbience(AudioMapKey, Lines);
        StartAudioRecording();
        // BRD-SETUP: the figures take their cells - one placement sound each (a re-entry mid-match stays quiet)
        if (Snapshot.TurnCount <= 1) {
          for (const int32 Ms : S08AudioCues::SetupDelays(Fighters.Num())) {
            DelaySound(Ms, TEXT("BRD-SETUP"), TEXT("SFX"), TEXT("setup"));
          }
        }
      }
      const FString Matchup = OppKey.IsEmpty() ? FString() : FString::Printf(TEXT("MATCHUP-%s"), *OppKey);
      const bool bMatchup = !Matchup.IsEmpty() && AudioRng.FRand() < 0.5f &&
                            S08AudioBank::VoLines().ContainsByPredicate([&](const FS08VoLine& L) {
                              return L.Fighter == AudioOwnHeroKey && L.Event == Matchup;
                            });
      FS08DelayedSound Own;
      Own.DueMs = Now + 2600;  // after STG-MATCH-START
      Own.BankId = bMatchup ? Matchup : TEXT("MATCH-START");
      Own.SoundClass = TEXT("VO");
      Own.Tag = AudioOwnHeroKey;
      DelayedSounds.Add(Own);
      if (!OppKey.IsEmpty()) {
        FS08DelayedSound Ans = Own;
        Ans.DueMs = Now + 5200;
        Ans.BankId = TEXT("MATCH-START");
        Ans.Tag = OppKey;
        Ans.bAnswer = true;
        DelayedSounds.Add(Ans);
      }
      AudioLastInputMs = Now;
    }
  }
  // own hand grows: the draw (CUE-005; the starting hand cascades, at most 2 at once - the concurrency of the row)
  if (const FS09PlayerPanel* Own = Hud.ViewerPanel()) {
    if (AudioOwnHand >= 0 && Own->HandCount > AudioOwnHand) {
      const int32 N = FMath::Min(Own->HandCount - AudioOwnHand, 6);
      PlayCueBank(TEXT("CUE-005"), TEXT("hand.own"), Snapshot.SequenceNumber, FString());
      for (int32 I = 1; I < N; ++I) DelaySound(I * 170, TEXT("CRD-DRAW"), TEXT("SFX"), TEXT("draw"));
    }
    AudioOwnHand = Own->HandCount;
  }
  if (const FS09PlayerPanel* Opp = Hud.OpponentPanel()) {
    if (AudioOppHand >= 0 && Opp->HandCount > AudioOppHand) {
      PlayCueBank(TEXT("CUE-005"), TEXT("hand.opp"), Snapshot.SequenceNumber, FString());
    }
    AudioOppHand = Opp->HandCount;
  }
  // heals (CUE-012): HP up; the Grail sets HP 8 from <= 4 (02 §4.7)
  for (const FS08BoardFighter& After : Fighters) {
    const FS08BoardFighter* B =
        Before.FindByPredicate([&After](const FS08BoardFighter& E) { return E.Id == After.Id; });
    if (B && After.Health > B->Health && !After.bDefeated && !B->bDefeated && B->Health > 0) {  // a revive is no heal
      const bool bGrail = After.Health == 8 && B->Health <= 4 && AudioKeyOf(After.Id) == TEXT("ARTHUR");
      PlayCueBank(TEXT("CUE-012"), After.Id, Snapshot.SequenceNumber,
                  bGrail ? TEXT("CMB-HEAL-GRAIL") : TEXT("CMB-HEAL"));
      if (bGrail) OfferVoLine(TEXT("CARD-GRAIL"), TEXT("ARTHUR"));
    }
  }
  // the hand limit discard (DE-024 draft): the short harp gesture once per draft
  const bool bDiscardDraft = CommandUi.Mode == ES09CommandMode::DiscardDraft;
  // the draft reopens with every re-apply of the same state (WS push + HTTP refetch): once per 20 s at most
  if (bDiscardDraft && !bAudioDiscardDraft && Now - AudioHandLimitMs > 20000) {
    AudioHandLimitMs = Now;
    Music.Sting(TEXT("STG-HAND-LIMIT"), 1000, Now, Lines);
  }
  bAudioDiscardDraft = bDiscardDraft;
  WriteCueLines(Lines);
}

void AS08FlowGameMode::StartAmbience(const FString& MapKey, TArray<FString>& OutLines) {
  for (const TObjectPtr<UAudioComponent>& Bed : AmbBeds) {
    if (Bed) Bed->Stop();
  }
  AmbBeds.Reset();
  const FS08AmbPlan Plan = S08Ambience::PlanFor(MapKey);
  Ambience.Start(Plan, NowMs(), OutLines);
  for (const FString& Id : Plan.Beds) {
    if (USoundBase* Bed = LoadAudio(CueSound.PickVariant(Id))) {
      UAudioComponent* C = UGameplayStatics::CreateSound2D(this, Bed, CueSound.ClassGain(TEXT("Ambience")), 1.0f, 0.0f,
                                                           nullptr, false, false);
      if (C) {
        C->FadeIn(2.0f, CueSound.ClassGain(TEXT("Ambience")));
        AmbBeds.Add(C);
      }
    }
  }
}

void AS08FlowGameMode::AudioOnAttackDeclared(const FString& AttackerId, int32 Seq, bool bAbilityBoost) {
  TArray<FString> Lines;
  Music.CombatBegin(NowMs(), Lines);
  WriteCueLines(Lines);
  PlayCueBank(TEXT("CUE-008"), AttackerId, Seq, FString());
  int32 Harpy = 1;
  const FString Key = AudioKeyOf(AttackerId, &Harpy);
  // AU-S5 CUE-014: Arthur's ability boost - the attacker knows it now; the defender hears it at the reveal (the boost
  // card id is stripped from its combat info)
  bAudioBoostDeclared = bAbilityBoost && Key == TEXT("ARTHUR");
  FS08Trace::Write(FString::Printf(TEXT("AUDIO attack seq=%d key=%s abilityBoost=%d"), Seq, Key.IsEmpty() ? TEXT("-") : *Key,
                                   bAbilityBoost ? 1 : 0));
  if (bAudioBoostDeclared) PlayCueBank(TEXT("CUE-014"), AttackerId, Seq, TEXT("FX-ARTHUR-BOOST"));
  OfferVoLine(TEXT("ATTACK"), Key, false, Harpy);
}

void AS08FlowGameMode::AudioOnDefensePlayed(const FString& TargetId, int32 Seq) {
  PlayCueBank(TEXT("CUE-009"), TargetId, Seq, FString());
  int32 Harpy = 1;
  const FString Key = AudioKeyOf(TargetId, &Harpy);
  if (Key != TEXT("HARPY")) OfferVoLine(TEXT("DEFEND"), Key);  // impersonal line: the card is still face down
}

void AS08FlowGameMode::AudioOnCombatEvent(const FS09CombatStageEvent& Event) {
  const FS09CombatStageInput& In = CombatStage.GetInput();
  const FS09CombatReveal& R = In.Reveal;
  switch (Event.Type) {
    case ES09CombatEvent::FlipAttack:
      PlayCueBank(TEXT("CUE-010"), TEXT("card.attack"), In.Seq, TEXT("CRD-FLIP"));
      if (!bAudioBoostDeclared && R.Boosts.Num() > 0 && AudioKeyOf(In.AttackerId) == TEXT("ARTHUR")) {
        PlayCueBank(TEXT("CUE-014"), In.AttackerId, In.Seq, TEXT("FX-ARTHUR-BOOST"));
      }
      bAudioBoostDeclared = false;
      break;
    case ES09CombatEvent::FlipDefense:
      PlayCueBank(TEXT("CUE-010"), TEXT("card.defense"), In.Seq,
                  R.bNoDefense ? TEXT("CMB-NO-DEFENSE") : TEXT("CRD-FLIP"));
      break;
    case ES09CombatEvent::Effect:
      PlayBankSfx(TEXT("CMB-EFFECT-LINE"), TEXT("SFX"), TEXT("effect"));
      break;
    case ES09CombatEvent::Slam: {
      PlayCueBank(TEXT("CUE-010"), TEXT("slam"), In.Seq, TEXT("CMB-SLAM"));
      if (bAudioBoostFizzle) {  // the attack card was cancelled: its boost goes out without effect
        bAudioBoostFizzle = false;
        PlayBankSfx(TEXT("FX-ARTHUR-BOOST-FIZZLE"), TEXT("SFX"), TEXT("fizzle"));
      }
      // signature cards speak from the reveal on (public)
      if (R.bAttackKnown) {
        if (const FSignatureCard* S = FindSignature(R.Attack.Name); S && *S->Speaker) {
          OfferVoLine(S->Event, S->Speaker);
        }
      }
      if (R.bDefenseKnown && !R.bNoDefense) {
        if (const FSignatureCard* S = FindSignature(R.Defense.Name)) {
          if (*S->Speaker) OfferVoLine(S->Event, S->Speaker);
          if (FCString::Strcmp(S->Fx, TEXT("FX-HISS")) == 0) PlayBankSfx(TEXT("FX-HISS"), TEXT("SFX"), TEXT("card"));
        }
      }
      break;
    }
    case ES09CombatEvent::Lunge: {
      if (CombatStage.LungePlayRate() <= 0.0f) break;  // speed "none": no lunge, no whoosh (02 §5.6)
      const FString Type = S08AudioBank::HitType(AudioKeyOf(In.AttackerId));
      PlayBankSfx(FString::Printf(TEXT("CMB-LUNGE-%s"), *Type), TEXT("SFX"), TEXT("lunge"));
      break;
    }
    case ES09CombatEvent::Block: {
      // damage 0 at the contact frame: the block, not the hit (02 §6 p. 3); Bewilderment blocks with an illusion
      const bool bIllusion = R.bDefenseKnown && R.Defense.Name.Equals(TEXT("Bewilderment"), ESearchCase::IgnoreCase);
      FS08SoundRequest Hit;
      Hit.Point = ES08SoundPoint::Hit;
      Hit.CueId = TEXT("CUE-011");
      Hit.Subject = In.TargetId;
      Hit.Seq = In.Seq;
      Hit.EventMs = NowMs();
      Hit.DueMs = Event.AtMs;
      Hit.BankId = bIllusion ? TEXT("CMB-BLOCK-ILLUSION") : TEXT("CMB-BLOCK-SHIELD");
      PlayCueSound(Hit);
      break;
    }
    case ES09CombatEvent::End: {
      TArray<FString> Lines;
      Music.CombatEnd(NowMs(), Lines);
      WriteCueLines(Lines);
      break;
    }
    default:
      break;
  }
}

void AS08FlowGameMode::AudioOnHit(const FString& FighterId, int32 Seq, int64 DueMs) {
  // the hit type of the attacker (02 §4.5); outside a staged combat: the effect / exhaustion hit
  const bool bStaged = CombatStage.IsActive() && CombatStage.GetInput().TargetId == FighterId;
  const FS09CombatStageInput& In = CombatStage.GetInput();
  int32 Damage = bStaged ? In.Damage : 0;
  const FS08BoardFighter* Target =
      Fighters.FindByPredicate([&FighterId](const FS08BoardFighter& E) { return E.Id == FighterId; });
  if (!bStaged && Target) {
    if (const int32* Last = AudioLastHp.Find(FighterId)) Damage = FMath::Max(0, *Last - Target->Health);
  }
  FString Bank = bStaged ? FString::Printf(TEXT("CMB-HIT-%s"), *S08AudioBank::HitType(AudioKeyOf(In.AttackerId)))
                         : TEXT("CMB-HIT-MAGIC");
  if (bStaged && In.Reveal.bAttackKnown && In.Reveal.Attack.Name.Equals(TEXT("Gaze of Stone"), ESearchCase::IgnoreCase) &&
      Damage >= 8) {
    Bank = TEXT("FX-PETRIFY");
  }
  FS08PendingHit Pending;
  Pending.Request.Point = ES08SoundPoint::Hit;
  Pending.Request.CueId = TEXT("CUE-011");
  Pending.Request.Subject = FighterId;
  Pending.Request.Seq = Seq;
  Pending.Request.EventMs = NowMs();
  Pending.Request.DueMs = DueMs;
  Pending.Request.BankId = Bank;
  Pending.Damage = Damage;
  Pending.bStaged = bStaged;
  PendingHits.Add(Pending);
  // layers: heavy (Excalibur / >= 5) and the lethal tail
  const bool bExcalibur = bStaged && In.Reveal.bAttackKnown && In.Reveal.Attack.Name.Equals(TEXT("Excalibur"),
                                                                                            ESearchCase::IgnoreCase);
  if (bExcalibur || Damage >= 5) PlayBankSfx(TEXT("CMB-HIT-HEAVY"), TEXT("SFX"), TEXT("layer"));
  if (bStaged && In.bLethal) PlayBankSfx(TEXT("CMB-HIT-LETHAL"), TEXT("SFX"), TEXT("layer"));
  // VO: hurt (wordless), a big hit for heroes; low HP once (final stand)
  int32 Harpy = 1;
  const FString Key = AudioKeyOf(FighterId, &Harpy);
  const bool bLethal = Target && (Target->Health <= 0 || Target->bDefeated);
  if (!bLethal) {
    if (Target && Target->bIsHero && Damage >= 4) {
      OfferVoLine(TEXT("HURT-BIG"), Key);
    } else {
      OfferVoLine(TEXT("HURT"), Key, false, Harpy);
    }
  }
  if (Target && Target->bIsHero && !bLethal && Target->MaxHealth > 0 && Target->Health * 4 <= Target->MaxHealth) {
    TArray<FString> Lines;
    Music.HeroHp(Target->Health, Target->MaxHealth, NowMs(), Lines);
    WriteCueLines(Lines);
    if (!AudioLowHpDone.Contains(FighterId)) {
      AudioLowHpDone.Add(FighterId);
      OfferVoLine(TEXT("LOW-HP"), Key);
      if (Key == TEXT("ARTHUR")) {
        DelaySoundVo(TEXT("ALLY-LOW"), TEXT("MERLIN"), 2600);  // Merlin answers, if alive (the director drops it if not)
      }
    }
  }
  if (Target) AudioLastHp.Add(FighterId, Target->Health);
}

void AS08FlowGameMode::DelaySoundVo(const FString& Event, const FString& Speaker, int32 InMs, bool bAnswer) {
  FS08DelayedSound D;
  D.DueMs = NowMs() + InMs;
  D.BankId = Event;
  D.SoundClass = TEXT("VO");
  D.Tag = Speaker;
  D.bAnswer = bAnswer;
  DelayedSounds.Add(D);
}

void AS08FlowGameMode::AudioOnDeath(const FString& FighterId, bool bHero, int32 Seq, int32 DissolveAtMs) {
  int32 Harpy = 1;
  const FString Key = AudioKeyOf(FighterId, &Harpy);
  const FS08BoardFighter* F =
      Fighters.FindByPredicate([&FighterId](const FS08BoardFighter& E) { return E.Id == FighterId; });
  const FString Bank = Key.IsEmpty() ? FString(TEXT("DTH-TEMPLATE")) : FString::Printf(TEXT("DTH-%s"), *Key);
  PlayCueBank(TEXT("CUE-013"), FighterId, Seq, S08AudioBank::Find(Bank) ? Bank : FString(TEXT("DTH-TEMPLATE")));
  DelaySound(FMath::Max(0, DissolveAtMs), TEXT("DTH-DISSOLVE"), TEXT("SFX"), TEXT("dissolve"));
  OfferVoLine(TEXT("DEATH"), Key, false, Harpy);
  TArray<FString> Lines;
  if (bHero) {
    Music.HeroFallen(NowMs(), Lines);
  } else if (F) {
    // a sidekick: its hero grieves, the killer gloats, the music marks it (own: the hero's motif; enemy: an accent)
    const FString OwnerHero = HeroKeyOfOwner(F->OwnerId);
    if (!OwnerHero.IsEmpty()) DelaySoundVo(TEXT("ALLY-DOWN"), OwnerHero, 1400);
    const bool bOwnSide = F->OwnerId == ViewerIdNow();
    Music.Sting(bOwnSide && !AudioOwnHeroKey.IsEmpty()
                    ? FString::Printf(TEXT("STG-SIDEKICK-DOWN-%s"), *AudioOwnHeroKey)
                    : FString(TEXT("STG-SIDEKICK-DOWN-ENEMY")),
                1500, NowMs(), Lines);
    if (CombatStage.IsActive() && CombatStage.GetInput().TargetId == FighterId) {
      int32 KillerHarpy = 1;
      const FString Killer = AudioKeyOf(CombatStage.GetInput().AttackerId, &KillerHarpy);
      DelaySoundVo(TEXT("ENEMY-DOWN"), Killer, 2600);
    }
  }
  WriteCueLines(Lines);
}

void AS08FlowGameMode::AudioOnCardSlot(const FS09SlotCard& Card) {
  const int32 Seq = Card.Seq;
  if (Card.Ribbon == ES09SlotRibbon::Discarded) {
    PlayBankSfx(TEXT("CRD-DISCARD"), TEXT("SFX"), TEXT("discard"));
    return;
  }
  if (Card.Ribbon == ES09SlotRibbon::Boosted) {
    PlayBankSfx(TEXT("CRD-BOOST-REVEAL"), TEXT("SFX"), TEXT("boost"));
    return;
  }
  // a scheme (CUE-006): the seal and page for everyone; the signature effect and line (Prophecy: the owner only)
  PlayCueBank(TEXT("CUE-006"), Card.OwnerId, Seq, TEXT("CRD-SCHEME"));
  const FString HeroKey = HeroKeyOfOwner(Card.OwnerId);
  if (const FSignatureCard* S = FindSignature(Card.Card.Name)) {
    const bool bPrivate = FCString::Strcmp(S->Name, TEXT("Prophecy")) == 0;
    if (!bPrivate || !Card.bOpponent) DelaySound(450, S->Fx, TEXT("SFX"), TEXT("scheme"));
    if (*S->Speaker) OfferVoLine(S->Event, S->Speaker);
    if (FCString::Strcmp(S->Name, TEXT("Winged Frenzy")) == 0) DelaySoundVo(TEXT("FRENZY"), TEXT("HARPY"), 900);
  } else {
    OfferVoLine(TEXT("SCHEME"), HeroKey);
  }
}

void AS08FlowGameMode::AudioOnTurn(bool bOwnTurn) {
  if (!bOwnTurn) return;
  AudioLastInputMs = NowMs();
  bIdleOffered = false;
  if (AudioOwnTurns++ > 0) OfferVoLine(TEXT("TURN-START"), AudioOwnHeroKey);
}

FString AS08FlowGameMode::AudioOnResult() {
  TArray<FString> Lines;
  const ES08MatchOutcome Outcome = !Hud.bWinnerKnown ? ES08MatchOutcome::Aborted
                                   : Hud.bViewerWon  ? ES08MatchOutcome::Win
                                                     : ES08MatchOutcome::Lose;
  const FString Sting = Music.Result(Outcome, AudioOwnHeroKey, NowMs(), Lines);
  WriteCueLines(Lines);
  for (const TObjectPtr<UAudioComponent>& Bed : AmbBeds) {
    if (Bed) Bed->FadeOut(2.0f, 0.0f);
  }
  Ambience.Stop();
  if (Outcome != ES08MatchOutcome::Aborted) {
    DelaySoundVo(Outcome == ES08MatchOutcome::Win ? TEXT("VICTORY") : TEXT("DEFEAT"), AudioOwnHeroKey, 3900);
  }
  if (bAudioRecording) AudioRecordStopMs = NowMs() + 8000;  // the sting, the theme and the last line are in
  return Sting;
}

void AS08FlowGameMode::NoteAudioInput() { AudioLastInputMs = NowMs(); }

// ---------------------------------------------------------------- AU-S5

void AS08FlowGameMode::AudioOnStage(ES08Stage OldStage, ES08Stage NewStage) {
  TArray<FString> Lines;
  if (OldStage == ES08Stage::Started && NewStage != ES08Stage::Started) {
    StopAudioRecording(TEXT("leave"));
    StopMatchVoice(TEXT("leave"));
  }
  // the match begins: the host's countdown screen (SC-18) plays UI-ROOM-COUNT-GO itself at its end; the guest has no
  // countdown - the start sounds here unless the screen played it just before
  if (OldStage == ES08Stage::Room && NewStage == ES08Stage::Started && NowMs() - AudioRoomCountGoMs > 8000) {
    PlayBankSfx(TEXT("UI-ROOM-COUNT-GO"), TEXT("UI"), TEXT("room"));
  }
  // the menu theme outside the match from the end of BOOT on (visual SC-03): the login and the lobby full, the room
  // quiet (no drums) while the players get ready
  if (!bBench && (NewStage == ES08Stage::Login || NewStage == ES08Stage::Lobby || NewStage == ES08Stage::Room) &&
      OldStage != NewStage) {
    Music.Menu(NowMs(), NewStage == ES08Stage::Room, Lines);
  }
  if (OldStage == ES08Stage::Login || OldStage == ES08Stage::Boot) {
    // an automated client goes straight to its room: any stage after the sign-in is its success
    if (NewStage == ES08Stage::Lobby || NewStage == ES08Stage::Room || NewStage == ES08Stage::Started) {
      PlayBankSfx(TEXT("UI-LOGIN-OK"), TEXT("UI"), TEXT("login"));
    }
    if (NewStage == ES08Stage::Failed) PlayBankSfx(TEXT("UI-LOGIN-ERR"), TEXT("UI"), TEXT("login"));
  }
  WriteCueLines(Lines);
}

void AS08FlowGameMode::StopMatchVoice(const TCHAR* Reason) {
  // the match is left (the result screen -> the lobby): its line, its subtitle and its queued sounds end with it
  const int64 Now = NowMs();
  const int32 Dropped = DelayedSounds.Num();
  DelayedSounds.Reset();
  PendingHits.Reset();
  const bool bWasPlaying = bVoPlaying;
  if (VoAudio) VoAudio->Stop();
  if (bVoPlaying) {
    bVoPlaying = false;
    Vo.Finished(Now);
    Music.SetVoActive(false, Now);
  }
  if (SubtitleBox.IsValid()) SubtitleBox->SetVisibility(EVisibility::Collapsed);
  UmHudHideSubtitle();  // VS-4 HB-41
  SubtitleUntilMs = 0;
  FS08Trace::Write(FString::Printf(TEXT("VO stop reason=%s playing=%d dropped=%d t=%lld"), Reason, bWasPlaying ? 1 : 0,
                                   Dropped, static_cast<long long>(Now)));
}

void AS08FlowGameMode::ResetAudioMatch() {
  bAudioMatchStarted = false;
  AudioMatchGameId.Reset();
  AudioOwnTurns = 0;
  AudioOwnHand = -1;
  AudioOppHand = -1;
  AudioLastHp.Reset();
  AudioLowHpDone.Reset();
  bIdleOffered = false;
  AudioIdleCount = 0;
  bAudioDiscardDraft = false;
  AudioHandLimitMs = MIN_int64 / 2;
  PendingHits.Reset();
  DelayedSounds.Reset();
  DeadlineBeeper.Reset();
  AudioGazeHeadId.Reset();
  bAudioGazeRequestDue = false;
  AudioDraftManeuverId.Reset();
  AudioPushBySeq.Reset();
  bAudioBoostDeclared = false;
  bAudioBoostFizzle = false;
  AudioPlaceSteps.Reset();
  AudioBoostCardId.Reset();
  bAudioStreamSeenReady = false;
  bAudioNetLost = false;
  AudioStreamDownSinceMs = -1;
}

void AS08FlowGameMode::AudioOnPendingOpen(const FString& HeadId) {
  // the presenter's Observe already gates the reopen of one head (the server reuses the id every turn)
  if (!S08AudioCues::IsMedusaGazeHead(HeadId)) return;
  AudioGazeHeadId = HeadId;
  bAudioGazeRequestDue = true;
}

void AS08FlowGameMode::AudioOnPendingAnswered(const FString& HeadId, const FString& FighterId, bool bUsed,
                                              const FString& Type) {
  // a card made this player discard (DISCARD_CARDS): the cards leave the hand with the forced-discard sweep
  if (bUsed && Type == TEXT("DISCARD_CARDS")) PlayBankSfx(TEXT("CRD-FORCED-DISCARD"), TEXT("SFX"), TEXT("discard"));
  if (!S08AudioCues::IsMedusaGazeHead(HeadId)) return;
  bAudioGazeRequestDue = false;
  AudioGazeHeadId.Reset();
  if (bUsed) {
    PlayCueBank(TEXT("CUE-014"), FighterId.IsEmpty() ? HeadId : FighterId,
                Flow.IsValid() ? Flow->GetAppliedSnapshot().SequenceNumber : -1, TEXT("FX-GAZE-BEAM"));
  } else {
    PlayBankSfx(TEXT("FX-GAZE-DECLINE"), TEXT("SFX"), TEXT("gaze"));
  }
}

void AS08FlowGameMode::AudioOnDraftOpen(const FString& ManeuverId, int32 Movable) {
  if (Movable < 2 || ManeuverId.IsEmpty() || ManeuverId == AudioDraftManeuverId) return;
  AudioDraftManeuverId = ManeuverId;
  PlayBankSfx(TEXT("BRD-CANDIDATES"), TEXT("SFX"), TEXT("candidates"));
}

void AS08FlowGameMode::AudioOnEffectTrail(int32 Seq, const TArray<FString>& Pushed) {
  if (!Pushed.Num()) return;
  AudioPushBySeq.Add(Seq, Pushed);
  for (auto It = AudioPushBySeq.CreateIterator(); It; ++It) {
    if (It.Key() < Seq - 16) It.RemoveCurrent();  // a held scheme releases its moves a few seqs later at most
  }
}

void AS08FlowGameMode::AudioTickDeadline() {
  if (CommandUi.Mode != ES09CommandMode::CombatDefense || !CommandUi.Combat.bHasTimeoutAt) return;
  const FString Bank =
      DeadlineBeeper.Feed(CommandUi.Combat.TimeoutAt.ToIso8601(), CommandUi.Combat.SecondsUntilDeadline());
  if (!Bank.IsEmpty()) PlayBankSfx(Bank, TEXT("UI"), TEXT("timer"));
}

void AS08FlowGameMode::StartAudioRecording() {
  if (AudioRecordFile.IsEmpty() || bAudioRecording) return;
  Audio::FMixerDevice* Mixer = FAudioDeviceManager::GetAudioMixerDeviceFromWorldContext(this);
  if (!Mixer) {
    FS08Trace::Write(TEXT("AUDIO-REC unavailable (no audio mixer device)"));
    return;
  }
  // An automated client runs unfocused, and the engine mutes an unfocused app before the mix
  // (UnfocusedVolumeMultiplier=0): the recording would be silence. The recording client keeps its volume and silences
  // its speakers at the main submix's output gain instead - the submix records its buffer before that gain.
  AudioRecordPrevUnfocused = FApp::GetUnfocusedVolumeMultiplier();
  FApp::SetUnfocusedVolumeMultiplier(1.0f);
  FApp::SetVolumeMultiplier(1.0f);
  Mixer->SetSubmixOutputVolume(&Mixer->GetMainSubmixObject(), 0.0f);
  Mixer->StartRecording(nullptr, 900.0f);  // the main submix: everything this client plays, after the master volume
  bAudioRecording = true;
  AudioRecordStopMs = -1;
  FS08Trace::Write(FString::Printf(TEXT("AUDIO-REC start t=%lld file=%s master=%.2f"), static_cast<long long>(NowMs()),
                                   *AudioRecordFile, CueSound.GetAudio().MasterGain()));
}

void AS08FlowGameMode::StopAudioRecording(const TCHAR* Why) {
  if (!bAudioRecording) return;
  bAudioRecording = false;
  AudioRecordStopMs = -1;
  Audio::FMixerDevice* Mixer = FAudioDeviceManager::GetAudioMixerDeviceFromWorldContext(this);
  if (!Mixer) return;
  float Channels = 0.0f;
  float Rate = 0.0f;
  Audio::FAlignedFloatBuffer& Recorded = Mixer->StopRecording(nullptr, Channels, Rate);
  Mixer->SetSubmixOutputVolume(&Mixer->GetMainSubmixObject(), 1.0f);
  FApp::SetUnfocusedVolumeMultiplier(AudioRecordPrevUnfocused);
  if (Recorded.Num() == 0 || Channels < 1.0f || Rate <= 0.0f) {
    FS08Trace::Write(FString::Printf(TEXT("AUDIO-REC stop why=%s ok=0 (no data)"), Why));
    return;
  }
  const double Seconds = Recorded.Num() / (static_cast<double>(Channels) * Rate);
  // written now, on the game thread: an automated client may exit right after the match
  Audio::TSampleBuffer<int16> Samples(Recorded, FMath::RoundToInt(Channels), FMath::RoundToInt(Rate));
  Audio::FSoundWavePCMWriter Writer;
  FString Written;
  const bool bOk = Writer.SynchronouslyWriteToWavFile(Samples, FPaths::GetBaseFilename(AudioRecordFile),
                                                      FPaths::GetPath(AudioRecordFile), &Written);
  FS08Trace::Write(FString::Printf(
      TEXT("AUDIO-REC stop why=%s ok=%d t=%lld seconds=%.1f channels=%d rate=%d master=%.2f file=%s"), Why, bOk ? 1 : 0,
      static_cast<long long>(NowMs()), Seconds, FMath::RoundToInt(Channels), FMath::RoundToInt(Rate),
      CueSound.GetAudio().MasterGain(), Written.IsEmpty() ? *AudioRecordFile : *Written));
}

namespace {
// AU-S5 (07 §9): the make-up gain of the mix bus. A recorded match at the default volumes measured -24.9..-25.7 LUFS-I
// without it (target -20 ±2); FS08PeakLimiter keeps every sample under -1.5 dBFS.
constexpr float GS08MixMakeupDb = 5.0f;
}  // namespace

void AS08FlowGameMode::InstallMasterLimiter() {
  if (MasterLimiter) return;
  if (FParse::Param(FCommandLine::Get(), TEXT("S08MixLegacy"))) {
    ArtHud.PendingTrace.Add(TEXT("AUDIO-MIX legacy (no limiter, no make-up)"));
    return;
  }
  FS08MixLimiterSettings Settings;
  Settings.MakeupDb = GS08MixMakeupDb;
  FParse::Value(FCommandLine::Get(), TEXT("S08MixMakeupDb="), Settings.MakeupDb);
  Settings.MakeupDb = FMath::Clamp(Settings.MakeupDb, -12.0f, 12.0f);
  Settings.CeilingDb = -1.5f;  // the sample ceiling; the true peak stays <= -1 dBTP
  US08MixLimiterPreset* Preset = NewObject<US08MixLimiterPreset>(this);
  Preset->Settings = Settings;
  Preset->SetSettings(Settings);
  UAudioMixerBlueprintLibrary::AddMasterSubmixEffect(this, Preset);
  Preset->SetSettings(Settings);  // the registered instance picks the settings up on the next audio block as well
  MasterLimiter = Preset;
  ArtHud.PendingTrace.Add(FString::Printf(TEXT("AUDIO-MIX limiter ceiling=%.1f lookahead=%.0f makeup=%.1f"),
                                          Settings.CeilingDb, Settings.LookaheadMs, Settings.MakeupDb));
}

void AS08FlowGameMode::RemoveMasterLimiter() {
  if (!MasterLimiter) return;
  UAudioMixerBlueprintLibrary::RemoveMasterSubmixEffect(this, MasterLimiter);
  MasterLimiter = nullptr;
}

void AS08FlowGameMode::AudioOnRoom(const FS08RoomState& Room) {
  const FString Viewer = Flow.IsValid() ? Flow->GetUserId() : FString();
  for (const FString& Bank : S08AudioCues::RoomSounds(AudioRoom, Room, Viewer)) PlayBankSfx(Bank, TEXT("UI"), TEXT("room"));
  AudioRoom = Room;
}

void AS08FlowGameMode::AudioOnRevive(const FString& FighterId) {
  if (AudioKeyOf(FighterId) == TEXT("HARPY")) PlayBankSfx(TEXT("FX-HARPY-RETURN"), TEXT("SFX"), TEXT("revive"));
}

void AS08FlowGameMode::AudioOnSkippedEffect() {
  if (AudioNoTargetFrame == GFrameCounter) return;
  AudioNoTargetFrame = GFrameCounter;
  PlayBankSfx(TEXT("FX-NO-TARGET"), TEXT("SFX"), TEXT("no-target"));
}

void AS08FlowGameMode::AudioNotePlace(const FString& FighterId, int32 Seq) {
  AudioPlaceSteps.Add(FString::Printf(TEXT("%s|%d"), *FighterId, Seq));
}

void AS08FlowGameMode::TickAudioWatchers() {
  // panels: the deck lists (K / Shift+K) and the discard browser (D)
  const bool bDeck = DeckPanel.IsOpen();
  if (bDeck != bAudioDeckPanelOpen) PlayBankSfx(bDeck ? TEXT("UI-PANEL-OPEN") : TEXT("UI-PANEL-CLOSE"), TEXT("UI"), TEXT("panel"));
  bAudioDeckPanelOpen = bDeck;
  if (bDiscardBrowserOpen != bAudioDiscardOpen) {
    PlayBankSfx(bDiscardBrowserOpen ? TEXT("UI-PANEL-OPEN") : TEXT("UI-PANEL-CLOSE"), TEXT("UI"), TEXT("panel"));
  }
  bAudioDiscardOpen = bDiscardBrowserOpen;
  // the card inspector: open, then a page per other card
  if (bInspecting && !bAudioInspecting) {
    PlayBankSfx(TEXT("CRD-INSPECT-OPEN"), TEXT("SFX"), TEXT("inspect"));
  } else if (bInspecting && InspectedCard.InstanceId != AudioInspectedId) {
    PlayBankSfx(TEXT("CRD-INSPECT-PAGE"), TEXT("SFX"), TEXT("inspect"));
  }
  bAudioInspecting = bInspecting;
  AudioInspectedId = bInspecting ? InspectedCard.InstanceId : FString();
  // the boost slot of an open maneuver draft: a card put in by the player (a snapshot re-baselines it silently)
  if (CommandUi.Mode == ES09CommandMode::ManeuverDraft && !CommandUi.BoostCardId.IsEmpty() &&
      CommandUi.BoostCardId != AudioBoostCardId) {
    PlayBankSfx(TEXT("CRD-BOOST-PLACE"), TEXT("SFX"), TEXT("boost"));
  }
  AudioBoostCardId = CommandUi.BoostCardId;
  // the live stream of the match (the reconnect banner keys off the same state): lost for 1.5 s / back
  if (Flow.IsValid() && Flow->GetStage() == ES08Stage::Started && bAudioMatchStarted && !bBench) {
    const int64 Now = NowMs();
    const bool bReady = Flow->IsStreamReady();
    if (bReady) {
      bAudioStreamSeenReady = true;
      AudioStreamDownSinceMs = -1;
      if (bAudioNetLost) {
        bAudioNetLost = false;
        TArray<FString> Lines;
        Music.SetDisconnected(false, Now, Lines);
        WriteCueLines(Lines);
        PlayCueBank(TEXT("CUE-018"), TEXT("net"), Hud.SequenceNumber, FString());
      }
    } else if (bAudioStreamSeenReady && !bAudioNetLost) {
      if (AudioStreamDownSinceMs < 0) AudioStreamDownSinceMs = Now;
      if (Now - AudioStreamDownSinceMs >= 1500) {
        bAudioNetLost = true;
        TArray<FString> Lines;
        Music.SetDisconnected(true, Now, Lines);
        WriteCueLines(Lines);
        PlayCueBank(TEXT("CUE-017"), TEXT("net"), Hud.SequenceNumber, FString());
      }
    }
  }
}

void AS08FlowGameMode::PlayScreenSound(FName BankId) {
  const FString Id = BankId.ToString();
  if (!S08AudioBank::Find(Id)) {
    FS08Trace::Write(FString::Printf(TEXT("AUDIO-SCREEN unknown bank=%s"), *Id));
    return;
  }
  if (Id == TEXT("UI-ROOM-COUNT-GO")) AudioRoomCountGoMs = NowMs();  // the stage change does not repeat it
  PlayBankSfx(Id, Id.StartsWith(TEXT("STG-")) ? TEXT("Music") : TEXT("UI"), TEXT("screen"));
}

void AS08FlowGameMode::SetAudioPaused(bool bPaused) {
  Music.SetPaused(bPaused, NowMs());
  FS08Trace::Write(FString::Printf(TEXT("MUSIC pause=%d t=%lld"), bPaused ? 1 : 0, static_cast<long long>(NowMs())));
}

void AS08FlowGameMode::PlayHeroSelectSting(const FString& HeroName) {
  const FString Bank = FString::Printf(TEXT("STG-SELECT-%s"), *S08AudioBank::CharacterKey(HeroName));
  if (S08AudioBank::Find(Bank)) PlayBankSfx(Bank, TEXT("Music"), TEXT("select"));
}
