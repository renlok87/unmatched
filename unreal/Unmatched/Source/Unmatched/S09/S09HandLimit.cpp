#include "S09HandLimit.h"

FS09HandLimitHintEvent FS09HandLimitHint::OnApplied(const FString& GameId, const FString& TurnKey, bool bGameOver,
                                                    int32 OwnHandCount, int32 HandLimit, bool bEnabled) {
  FS09HandLimitHintEvent Event;
  if (GameId != GameKey) {
    // "once per match" is kept in the client's match state (01 review resolution п. 4): a new match starts over
    const bool bWasVisible = bVisible;
    Reset();
    GameKey = GameId;
    if (bWasVisible) Event.Closed = ES09HintClose::GameOver;
  }
  if (bVisible) {
    ES09HintClose Why = ES09HintClose::None;
    if (bGameOver) {
      Why = ES09HintClose::GameOver;
    } else if (!bEnabled) {
      Why = ES09HintClose::Off;
    } else if (TurnKey != ShownTurnKey) {
      Why = ES09HintClose::TurnEnd;  // SD-42 п. 2: it stays until a click or the end of the turn
    }
    if (Why != ES09HintClose::None) {
      bVisible = false;
      Event.Closed = Why;
    }
  }
  const bool bFirst = !bSeen;
  bSeen = true;
  const int32 Previous = LastCount;
  LastCount = OwnHandCount;
  if (bFirst || bShown || !bEnabled || bGameOver || HandLimit <= 0) return Event;
  if (OwnHandCount >= HandLimit && Previous < HandLimit) {
    bShown = true;
    bVisible = true;
    ShownTurnKey = TurnKey;
    Limit = HandLimit;
    Event.bShown = true;
  }
  return Event;
}

bool FS09HandLimitHint::Dismiss() {
  if (!bVisible) return false;
  bVisible = false;
  return true;
}

const TCHAR* FS09HandLimitHint::CloseName(ES09HintClose Close) {
  switch (Close) {
    case ES09HintClose::Click: return TEXT("click");
    case ES09HintClose::TurnEnd: return TEXT("turn");
    case ES09HintClose::GameOver: return TEXT("over");
    case ES09HintClose::Off: return TEXT("off");
    default: return TEXT("none");
  }
}

FS09DiscardPick FS09DiscardPick::From(const FS09CommandUi& Ui) {
  FS09DiscardPick Pick;
  if (Ui.Mode == ES09CommandMode::DiscardDraft) {
    Pick.Source = ES09DiscardSource::HandLimit;
    Pick.Need = Ui.PendingDiscard.Count;
    Pick.Picked = Ui.DiscardSelection.Array();
    Pick.Picked.Sort();
    return Pick;
  }
  if (Ui.Mode == ES09CommandMode::PendingChoice && Ui.bHasPendingChoice &&
      Ui.PendingChoice.Type == TEXT("DISCARD_CARDS")) {
    Pick.Source = ES09DiscardSource::Effect;
    Pick.Need = Ui.PendingChoice.bHasValue ? Ui.PendingChoice.Value : 1;
    Pick.Picked = Ui.PendingCardIds;
    Pick.bOptional = Ui.PendingChoice.bOptional;
  }
  return Pick;
}

ES09HandMark FS09DiscardPick::Mark(const FString& InstanceId, bool bHidden) const {
  if (!IsOpen() || bHidden || InstanceId.IsEmpty()) return ES09HandMark::None;
  return Picked.Contains(InstanceId) ? ES09HandMark::Picked : ES09HandMark::Candidate;
}

FString FS09DiscardPick::PickLine() const {
  if (!IsOpen()) return FString();
  return FString::Printf(TEXT("CHOOSE %d CARD%s: selected %d/%d (%d more)"), Need, Need == 1 ? TEXT("") : TEXT("S"),
                         Picked.Num(), Need, Left());
}

const TCHAR* FS09DiscardPick::SourceName(ES09DiscardSource Source) {
  switch (Source) {
    case ES09DiscardSource::HandLimit: return TEXT("limit");
    case ES09DiscardSource::Effect: return TEXT("effect");
    default: return TEXT("none");
  }
}
