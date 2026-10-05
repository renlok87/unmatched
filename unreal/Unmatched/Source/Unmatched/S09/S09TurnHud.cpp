#include "S09TurnHud.h"

// ------------------------------------------------------------------------------------------------- turn cue

FS09TurnCueEvent FS09TurnCue::OnApplied(const FString& TurnPlayerId, int32 TurnCount, const FString& ViewerId,
                                        bool bGameOver, double NowMs, bool bReducedMotion) {
  FS09TurnCueEvent Event;
  Event.TurnPlayerId = TurnPlayerId;
  if (bGameOver) {
    // the duel is over: the ring leaves once, no banner (the result gate owns the screen)
    if (!bOver) {
      Event.bChanged = true;
      Event.bGameOver = true;
    }
    bOver = true;
    bOwnTurn = bOpponentTurn = false;
    bBanner = false;
    return Event;
  }
  if (TurnPlayerId.IsEmpty()) return Event;  // a merge without the turn owner changes nothing
  const FString Key = FString::Printf(TEXT("%s#%d"), *TurnPlayerId, TurnCount);
  if (Key == TurnKey && !bOver) return Event;
  const bool bFirst = !bSeen;
  bSeen = true;
  bOver = false;
  TurnKey = Key;
  bOwnTurn = !ViewerId.IsEmpty() && TurnPlayerId == ViewerId;
  bOpponentTurn = !ViewerId.IsEmpty() && TurnPlayerId != ViewerId;
  Event.bChanged = true;
  Event.bInitial = bFirst;
  Event.bOwn = bOwnTurn;
  // 01 F-07: the banner only on the own turn, 600 ms (reduced: 100); not on a join / reconnect mid-turn
  bBanner = bOwnTurn && !bFirst;
  BannerSinceMs = NowMs;
  BannerLength = bReducedMotion ? BannerReducedMs : BannerMs;
  return Event;
}

float FS09TurnCue::BannerAlpha(double NowMs) const {
  if (!bBanner) return 0.0f;
  const double T = NowMs - BannerSinceMs;
  if (T < 0.0 || T >= BannerLength) return 0.0f;
  if (BannerLength <= BannerReducedMs) return 1.0f;  // reduced motion: static
  if (T < BannerFadeInMs) return static_cast<float>(FMath::Max(T / BannerFadeInMs, 0.15));  // frame 0 is not empty
  const double OutFrom = BannerLength - BannerFadeOutMs;
  if (T > OutFrom) return static_cast<float>(FMath::Clamp((BannerLength - T) / BannerFadeOutMs, 0.0, 1.0));
  return 1.0f;
}

// ------------------------------------------------------------------------------------------------- tracker

void FS09TrackerMarks::Choose(int32 ServerSpent, int32 AppliedSeq, double NowMs) {
  bLatched = true;
  LatchBase = ServerSpent;
  LatchSeq = AppliedSeq;
  LatchSinceMs = NowMs;
}

void FS09TrackerMarks::OnApplied(const FString& InTurnKey, int32 Seq, int32 ServerSpent) {
  if (InTurnKey != TurnKey) {
    TurnKey = InTurnKey;
    bLatched = false;  // 01 F-12: the reset of a new turn in one frame
    return;
  }
  // the server answered: its marks take over (an accepted choice is in ServerSpent, a refused one is gone)
  if (bLatched && (ServerSpent > LatchBase || Seq > LatchSeq)) bLatched = false;
}

int32 FS09TrackerMarks::Shown(int32 ServerSpent, int32 Slots, bool bDraftOpen, double NowMs) const {
  const int32 Server = FMath::Clamp(ServerSpent, 0, FMath::Max(Slots, 0));
  const bool bLocal = bDraftOpen || (IsLatched(NowMs) && ServerSpent <= LatchBase);
  return bLocal ? FMath::Min(Server + 1, FMath::Max(Slots, 0)) : Server;
}

// ------------------------------------------------------------------------------------------------- heart

ES09HeartEvent FS09HeartWatch::Sample(const FString& InHeroId, int32 InHealth) {
  if (InHealth < 0) return ES09HeartEvent::None;
  if (InHeroId != HeroId || Health < 0) {
    HeroId = InHeroId;
    Health = InHealth;
    return ES09HeartEvent::None;
  }
  const int32 Before = Health;
  Health = InHealth;
  if (InHealth < Before) return InHealth <= 0 ? ES09HeartEvent::Deplete : ES09HeartEvent::Damage;
  if (InHealth > Before) return ES09HeartEvent::Heal;
  return ES09HeartEvent::None;
}

// ------------------------------------------------------------------------------------------------- helpers

const TCHAR* S09TurnHud::HeartEventName(ES09HeartEvent Event) {
  switch (Event) {
    case ES09HeartEvent::Damage: return TEXT("damage");
    case ES09HeartEvent::Deplete: return TEXT("deplete");
    case ES09HeartEvent::Heal: return TEXT("heal");
    default: return TEXT("none");
  }
}

FName S09TurnHud::HeartAnim(ES09HeartEvent Event) {
  switch (Event) {
    case ES09HeartEvent::Damage: return FName(TEXT("damage"));
    case ES09HeartEvent::Deplete: return FName(TEXT("deplete"));
    case ES09HeartEvent::Heal: return FName(TEXT("heal"));
    default: return NAME_None;
  }
}

FString S09TurnHud::Monogram(const FString& Name) {
  TArray<FString> Words;
  Name.ParseIntoArrayWS(Words);
  FString Out;
  for (const FString& Word : Words) {
    if (Out.Len() >= 2) break;
    if (!Word.IsEmpty() && FChar::IsAlpha(Word[0])) Out.AppendChar(FChar::ToUpper(Word[0]));
  }
  return Out.IsEmpty() ? FString(TEXT("?")) : Out;
}

float S09TurnHud::HandPanelLeft(float CanvasWidthSu, float PanelWidthSu, float ObstacleRightSu) {
  const float Centred = 0.5f * (CanvasWidthSu - PanelWidthSu);
  if (ObstacleRightSu <= 0.0f) return Centred;
  return FMath::Max(Centred, ObstacleRightSu + HandGutterSu);
}

float S09TurnHud::HandStripWrap(float CanvasWidthSu, float ObstacleRightSu, float PanelPaddingSu) {
  const float Left = ObstacleRightSu > 0.0f ? ObstacleRightSu + HandGutterSu : HandEdgeSu;
  return FMath::Max(200.0f, CanvasWidthSu - Left - HandEdgeSu - PanelPaddingSu);
}
