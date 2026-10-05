#include "S09ResultScreen.h"

#include "S09HudModel.h"
#include "../S08/S08Contracts.h"
#include "Dom/JsonObject.h"
#include "Misc/DateTime.h"

namespace {
const TArray<TSharedPtr<FJsonValue>>* ArrayOf(const TSharedPtr<FJsonValue>& Value) {
  const TArray<TSharedPtr<FJsonValue>>* Out = nullptr;
  if (!Value.IsValid() || !Value->TryGetArray(Out)) return nullptr;
  return Out;
}

int32 IntField(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field) {
  double Number = 0.0;
  return Object.IsValid() && Object->TryGetNumberField(Field, Number) ? static_cast<int32>(Number) : -1;
}

bool HasNumber(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field) {
  double Number = 0.0;
  return Object.IsValid() && Object->TryGetNumberField(Field, Number);
}

/** The side of one player: hero fighter (HERO / HUGE wins over the first own fighter) and players[] for the rest. */
FS09ResultSide SideOf(const FS09PlayerPanel& Panel, const FS08Snapshot& Snapshot) {
  FS09ResultSide Side;
  Side.PlayerId = Panel.PlayerId;
  Side.bViewer = Panel.bIsViewer;
  Side.bAlive = Panel.bIsAlive;
  if (const TArray<TSharedPtr<FJsonValue>>* Fighters = ArrayOf(Snapshot.Fighters)) {
    TSharedPtr<FJsonObject> Chosen;
    for (const TSharedPtr<FJsonValue>& Value : *Fighters) {
      const TSharedPtr<FJsonObject> Fighter = Value.IsValid() ? Value->AsObject() : nullptr;
      if (!Fighter.IsValid() || Fighter->GetStringField(TEXT("ownerId")) != Panel.PlayerId) continue;
      const FString Type = Fighter->GetStringField(TEXT("type"));
      if (Type == TEXT("HERO") || Type == TEXT("HUGE")) {
        Chosen = Fighter;
        break;
      }
      if (!Chosen.IsValid()) Chosen = Fighter;
    }
    if (Chosen.IsValid()) {
      Side.HeroName = Chosen->GetStringField(TEXT("name"));
      Side.HeroFighterId = Chosen->GetStringField(TEXT("id"));
      Side.bHpKnown = HasNumber(Chosen, TEXT("health"));
      Side.Hp = IntField(Chosen, TEXT("health"));
      Side.MaxHp = IntField(Chosen, TEXT("maxHealth"));
    }
  }
  if (!Side.bHpKnown) {
    // no fighter entry: players[] carries the hero's health too (02 §2.9 "players[] (heroId, health, maxHealth)")
    if (const TArray<TSharedPtr<FJsonValue>>* Players = ArrayOf(Snapshot.Players)) {
      for (const TSharedPtr<FJsonValue>& Value : *Players) {
        const TSharedPtr<FJsonObject> Player = Value.IsValid() ? Value->AsObject() : nullptr;
        if (!Player.IsValid() || Player->GetStringField(TEXT("userId")) != Panel.PlayerId) continue;
        Side.bHpKnown = HasNumber(Player, TEXT("health"));
        Side.Hp = IntField(Player, TEXT("health"));
        Side.MaxHp = IntField(Player, TEXT("maxHealth"));
        break;
      }
    }
  }
  return Side;
}
}  // namespace

FS09ResultSummary FS09ResultSummary::Build(const FS09HudModel& Hud, const FS08Snapshot& Snapshot,
                                           const FString& StartedAt, const FString& EndedAt) {
  FS09ResultSummary Out;
  Out.bValid = Hud.bGameOver;
  Out.Outcome = Hud.OutcomeWord();
  Out.TurnCount = Snapshot.TurnCount;
  Out.DurationSec = DurationSeconds(StartedAt, EndedAt);
  const FS09PlayerPanel* Viewer = Hud.ViewerPanel();
  const FS09PlayerPanel* Opponent = Hud.OpponentPanel();
  FS09ResultSide Own = Viewer ? SideOf(*Viewer, Snapshot) : FS09ResultSide();
  FS09ResultSide Other = Opponent ? SideOf(*Opponent, Snapshot) : FS09ResultSide();
  if (Hud.bWinnerKnown) {
    FS09ResultSide& Winner = Own.PlayerId == Hud.WinnerPlayerId ? Own : Other;
    FS09ResultSide& Loser = Own.PlayerId == Hud.WinnerPlayerId ? Other : Own;
    Winner.bWinner = true;
    Loser.bSilhouette = Loser.IsKnown();
    // the headline names the winning HERO (the GD-036 model reads it from the fighters projection), never the
    // fighter that struck the last blow (01 F-06, SD-45 p. 1)
    const FString WinnerHero = !Hud.WinnerHeroName.IsEmpty() ? Hud.WinnerHeroName : Winner.HeroName;
    Out.Headline = WinnerHero.IsEmpty() ? (Winner.bViewer ? FString(TEXT("YOU WIN")) : FString(TEXT("OPPONENT WINS")))
                                        : WinnerHero.ToUpper() + TEXT(" WINS");
    if (Loser.IsKnown() && ((Loser.bHpKnown && Loser.Hp <= 0) || !Loser.bAlive)) {
      Out.Reason = ES09ResultReason::HeroHpZero;
      Out.ReasonText = Loser.HeroName.IsEmpty() ? FString(TEXT("The defeated hero's HP reached 0"))
                                                : FString::Printf(TEXT("%s's HP reached 0"), *Loser.HeroName);
    } else {
      Out.Reason = ES09ResultReason::Verdict;
      Out.ReasonText = TEXT("The server declared the winner");
    }
    Out.Left = Winner;
    Out.Right = Loser;
  } else {
    Out.Left = Own;
    Out.Right = Other;
    if (Hud.bDraw) {
      Out.Reason = ES09ResultReason::Draw;
      Out.Headline = TEXT("MUTUAL DESTRUCTION");
      Out.ReasonText = TEXT("Both heroes fell - no winner");
    } else {
      Out.Reason = ES09ResultReason::Unknown;
      Out.Headline = TEXT("NO SERVER VERDICT");
      Out.ReasonText = TEXT("The server sent no winner - the outcome is unavailable");
    }
  }
  return Out;
}

int32 FS09ResultSummary::DurationSeconds(const FString& StartedAt, const FString& EndedAt) {
  FDateTime Start;
  FDateTime End;
  if (StartedAt.IsEmpty() || EndedAt.IsEmpty() || !FDateTime::ParseIso8601(*StartedAt, Start) ||
      !FDateTime::ParseIso8601(*EndedAt, End) || End < Start) {
    return -1;
  }
  return static_cast<int32>(FMath::Min<double>((End - Start).GetTotalSeconds(), static_cast<double>(MAX_int32)));
}

FString FS09ResultSummary::FormatDuration(int32 Seconds) {
  if (Seconds < 0) return TEXT("-");
  const int32 H = Seconds / 3600;
  const int32 M = (Seconds / 60) % 60;
  const int32 S = Seconds % 60;
  return H > 0 ? FString::Printf(TEXT("%d:%02d:%02d"), H, M, S) : FString::Printf(TEXT("%d:%02d"), M, S);
}

FString FS09ResultSummary::StatsLine() const {
  FString Line = FString::Printf(TEXT("Turn %d"), TurnCount);
  if (DurationSec >= 0) Line += FString::Printf(TEXT("  ·  %s"), *FormatDuration(DurationSec));
  return Line;
}

const TCHAR* FS09ResultSummary::ReasonName(ES09ResultReason Reason) {
  switch (Reason) {
    case ES09ResultReason::HeroHpZero: return TEXT("hp0");
    case ES09ResultReason::Draw: return TEXT("draw");
    case ES09ResultReason::Verdict: return TEXT("verdict");
    default: return TEXT("unknown");
  }
}

FString FS09ResultSummary::TraceLine() const {
  auto Name = [](const FString& S) { return S.IsEmpty() ? FString(TEXT("-")) : S.Replace(TEXT(" "), TEXT("_")); };
  const bool bDecided = Left.bWinner;
  return FString::Printf(
      TEXT("RESULT summary outcome=%s winnerHero=%s loserHero=%s reason=%s turn=%d duration=%s left=%s silhouette=%d"),
      *Outcome.Replace(TEXT(" "), TEXT("_")), bDecided ? *Name(Left.HeroName) : TEXT("-"),
      bDecided ? *Name(Right.HeroName) : TEXT("-"), ReasonName(Reason), TurnCount,
      DurationSec >= 0 ? *FString::FromInt(DurationSec) : TEXT("-"), Left.bViewer ? TEXT("viewer") : TEXT("opponent"),
      Right.bSilhouette ? 1 : 0);
}

// ------------------------------------------------------------------------------------------------- view

bool FS09ResultView::Open(int64 NowMs) {
  if (CurrentMode != ES09ResultMode::Hidden) return false;
  CurrentMode = ES09ResultMode::Results;
  OpenMs = NowMs;
  ChangeMs = -1;
  FromAlpha = 0.0f;
  return true;
}

bool FS09ResultView::ToggleBoard(int64 NowMs) {
  if (CurrentMode == ES09ResultMode::Hidden) return false;
  FromAlpha = ResultsAlpha(NowMs);
  ChangeMs = NowMs;
  CurrentMode = CurrentMode == ES09ResultMode::Results ? ES09ResultMode::Board : ES09ResultMode::Results;
  ++ToggleCount;
  return true;
}

float FS09ResultView::ResultsAlpha(int64 NowMs) const {
  if (CurrentMode == ES09ResultMode::Hidden) return 0.0f;
  if (ChangeMs < 0) {
    // the first entry: the intro (SD-45 p. 3)
    const int64 Since = NowMs - OpenMs;
    if (Since >= IntroMs) return 1.0f;
    return Since <= 0 ? 0.0f : static_cast<float>(Since) / static_cast<float>(IntroMs);
  }
  // a toggle: the crossfade from where the modal stood (a re-entry has no intro)
  const float Target = CurrentMode == ES09ResultMode::Results ? 1.0f : 0.0f;
  const int64 Since = NowMs - ChangeMs;
  if (Since >= CrossfadeMs) return Target;
  const float T = Since <= 0 ? 0.0f : static_cast<float>(Since) / static_cast<float>(CrossfadeMs);
  return FMath::Lerp(FromAlpha, Target, T);
}

float FS09ResultView::BoardBarAlpha(int64 NowMs) const {
  if (CurrentMode == ES09ResultMode::Hidden || ChangeMs < 0) return 0.0f;
  return 1.0f - ResultsAlpha(NowMs);
}

ES09ResultAction FS09ResultView::OnKey(ES09ResultKey Key) const {
  if (CurrentMode == ES09ResultMode::Hidden) return ES09ResultAction::None;
  switch (Key) {
    case ES09ResultKey::V: return ES09ResultAction::ToggleBoard;
    case ES09ResultKey::Escape:
      return CurrentMode == ES09ResultMode::Board ? ES09ResultAction::ToggleBoard : ES09ResultAction::Lobby;
    case ES09ResultKey::Enter:
    case ES09ResultKey::L: return ES09ResultAction::Lobby;
  }
  return ES09ResultAction::None;
}
