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
#include "Components/AudioComponent.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Engine/World.h"
#include "Internationalization/Culture.h"
#include "Internationalization/Internationalization.h"
#include "Kismet/GameplayStatics.h"
#include "S08BoardActor.h"
#include "S08FlowGameMode.h"
#include "S08TraceLog.h"
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
                                                              .AutoWrapText(true)];
    GEngine->GameViewport->AddViewportWidgetContent(SubtitleBox.ToSharedRef(), 40);
  }
}

void AS08FlowGameMode::ShutdownAudioRuntime() {
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
    int32 Index = 1;
    for (int32 I = F->Label.Len() - 1; I >= 0; --I) {
      if (FChar::IsDigit(F->Label[I])) {
        Index = FChar::ConvertCharDigitToInt(F->Label[I]);
        break;
      }
    }
    *OutHarpyIndex = FMath::Clamp(Index, 1, 3);
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
  // match start: the first applied board with both heroes
  if (!bAudioMatchStarted && Fighters.Num() && !Viewer.IsEmpty()) {
    AudioOwnHeroKey = HeroKeyOfOwner(Viewer);
    FString OppKey;
    for (const FS08BoardFighter& F : Fighters) {
      if (F.bIsHero && F.OwnerId != Viewer) OppKey = S08AudioBank::CharacterKey(F.Name.IsEmpty() ? F.Label : F.Name);
    }
    if (!AudioOwnHeroKey.IsEmpty()) {
      bAudioMatchStarted = true;
      const FString Board = BoardActor && !BoardActor->GetArtProfileId().IsEmpty() ? BoardActor->GetArtProfileId()
                            : Flow.IsValid()                                       ? Flow->GetRoom().BoardId
                                                                                   : FString();
      AudioMapKey = S08Ambience::MapKeyOf(Board);
      Vo.NewMatch(Snapshot.SequenceNumber * 7919 + 17);
      if (!bBench) {
        Music.StartMatch(AudioMapKey.IsEmpty() ? TEXT("MARMOREAL") : AudioMapKey, Now, Lines);
        StartAmbience(AudioMapKey, Lines);
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
    if (B && After.Health > B->Health && !After.bDefeated) {
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

void AS08FlowGameMode::AudioOnAttackDeclared(const FString& AttackerId, int32 Seq) {
  TArray<FString> Lines;
  Music.CombatBegin(NowMs(), Lines);
  WriteCueLines(Lines);
  PlayCueBank(TEXT("CUE-008"), AttackerId, Seq, FString());
  int32 Harpy = 1;
  const FString Key = AudioKeyOf(AttackerId, &Harpy);
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
  return Sting;
}

void AS08FlowGameMode::NoteAudioInput() { AudioLastInputMs = NowMs(); }
