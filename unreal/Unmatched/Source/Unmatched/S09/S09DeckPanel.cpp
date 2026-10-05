#include "S09DeckPanel.h"

#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"

FS09CardView FS09DeckRow::AsCardView() const {
  FS09CardView View;
  View.CardId = Card.CardId;
  View.Name = Card.Name;
  View.NameRu = Card.NameRu;
  View.CardType = Card.CardType;
  View.BannerName = Card.BannerName;
  View.Text = Card.Text;
  View.AttackValue = FMath::Max(0, Card.AttackValue);
  View.DefenseValue = FMath::Max(0, Card.DefenseValue);
  View.BoostValue = FMath::Max(0, Card.BoostValue);
  View.bHasBoostValue = Card.BoostValue >= 0;
  View.bVisible = true;
  return View;
}

FS09DeckPanelModel FS09DeckPanelModel::Build(ES09DeckSide Side, const FS09PlayerPanel& Panel,
                                             const FS09DeckList* List) {
  FS09DeckPanelModel M;
  M.Side = Side;
  M.PlayerId = Panel.PlayerId;
  M.HandCount = Panel.HandCount;
  M.DeckCount = Panel.DeckCount;
  M.bDeckStale = Panel.bDeckCountStale;
  M.DiscardCount = Panel.Discard.Num();
  M.bDiscardStale = Panel.bDiscardStale;
  for (const FS09CardView& Card : Panel.Discard) {
    if (Card.bHidden) ++M.HiddenDiscard;
  }
  M.bListKnown = List != nullptr;
  if (!List) return M;

  TMap<FString, int32> RowOf;
  for (const FS09DeckListCard& Card : List->Cards) {
    if (Card.CardId.IsEmpty() || RowOf.Contains(Card.CardId)) continue;
    FS09DeckRow Row;
    Row.Card = Card;
    RowOf.Add(Card.CardId, M.Rows.Num());
    M.Copies += FMath::Max(0, Card.Count);
    M.Rows.Add(MoveTemp(Row));
  }
  // public discard faces - both sides (a face-down placeholder has no identity and is never attributed)
  for (const FS09CardView& Card : Panel.Discard) {
    if (Card.bHidden) continue;
    if (const int32* Index = RowOf.Find(Card.CardId)) {
      ++M.Rows[*Index].InDiscard;
    } else {
      ++M.Unlisted;
    }
  }
  if (Side == ES09DeckSide::Own) {
    // my own hand: exact instances (the opponent's Cards are never read - QA-005)
    for (const FS09CardView& Card : Panel.Cards) {
      if (Card.bHidden) continue;
      if (const int32* Index = RowOf.Find(Card.CardId)) {
        ++M.Rows[*Index].InHand;
      } else {
        ++M.Unlisted;
      }
    }
    int32 Placed = 0;
    for (FS09DeckRow& Row : M.Rows) {
      Row.Left = FMath::Max(0, Row.Card.Count - Row.InHand - Row.InDiscard);
      Placed += Row.InHand + Row.InDiscard;
    }
    const int32 Gap = M.Copies - Placed - M.HiddenDiscard - M.DeckCount;
    M.OutOfPlay = !M.bDeckStale && !M.bDiscardStale && Gap >= 0 ? Gap : -1;
  }
  return M;
}

FString FS09DeckPanelModel::TraceLine() const {
  int32 Hand = 0, Discard = 0, Left = 0;
  for (const FS09DeckRow& Row : Rows) {
    Hand += Row.InHand;
    Discard += Row.InDiscard;
    if (Row.Left > 0) Left += Row.Left;
  }
  FString Line = FString::Printf(TEXT("DECK model side=%s list=%d kinds=%d copies=%d deck=%d%s discard=%d%s"),
                                 S09DeckPanel::SideName(Side), bListKnown ? 1 : 0, Rows.Num(), Copies, DeckCount,
                                 bDeckStale ? TEXT("~") : TEXT(""), DiscardCount, bDiscardStale ? TEXT("~") : TEXT(""));
  if (Side == ES09DeckSide::Own) {
    Line += FString::Printf(TEXT(" inHand=%d inDiscard=%d left=%d out=%d"), Hand, Discard, Left, OutOfPlay);
  } else {
    Line += FString::Printf(TEXT(" backs=%d inDiscard=%d"), HandCount, Discard);
  }
  if (HiddenDiscard > 0) Line += FString::Printf(TEXT(" faceDown=%d"), HiddenDiscard);
  if (Unlisted > 0) Line += FString::Printf(TEXT(" unlisted=%d"), Unlisted);
  return Line;
}

namespace S09DeckPanel {
namespace {
int32 IntOrMinus(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field) {
  const TSharedPtr<FJsonValue> Value = Object->TryGetField(Field);
  double Number = 0.0;
  if (!Value.IsValid() || Value->Type != EJson::Number || !Value->TryGetNumber(Number) || !FMath::IsFinite(Number)) {
    return -1;
  }
  return static_cast<int32>(Number);
}

FString StringOrEmpty(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field) {
  FString Out;
  Object->TryGetStringField(Field, Out);  // null / absent -> ''
  return Out;
}
}  // namespace

bool ParseDeckLists(const TSharedPtr<FJsonObject>& Data, TArray<FS09DeckList>& Out, FString& OutError) {
  Out.Reset();
  OutError.Reset();
  const TArray<TSharedPtr<FJsonValue>>* Lists = nullptr;
  if (!Data.IsValid() || !Data->TryGetArrayField(TEXT("gameDeckLists"), Lists) || !Lists) {
    OutError = TEXT("gameDeckLists missing");
    return false;
  }
  for (const TSharedPtr<FJsonValue>& Value : *Lists) {
    const TSharedPtr<FJsonObject> ListObject = Value.IsValid() ? Value->AsObject() : nullptr;
    if (!ListObject.IsValid()) {
      OutError = TEXT("list is not an object");
      return false;
    }
    FS09DeckList List;
    List.PlayerId = StringOrEmpty(ListObject, TEXT("playerId"));
    if (List.PlayerId.IsEmpty()) {
      OutError = TEXT("list without playerId");
      return false;
    }
    List.Total = FMath::Max(0, IntOrMinus(ListObject, TEXT("total")));
    const TArray<TSharedPtr<FJsonValue>>* Cards = nullptr;
    if (!ListObject->TryGetArrayField(TEXT("cards"), Cards) || !Cards) {
      OutError = TEXT("list without cards");
      return false;
    }
    for (const TSharedPtr<FJsonValue>& CardValue : *Cards) {
      const TSharedPtr<FJsonObject> C = CardValue.IsValid() ? CardValue->AsObject() : nullptr;
      if (!C.IsValid()) continue;
      FS09DeckListCard Card;
      Card.CardId = StringOrEmpty(C, TEXT("cardId"));
      if (Card.CardId.IsEmpty()) continue;
      Card.Name = StringOrEmpty(C, TEXT("name"));
      Card.NameRu = StringOrEmpty(C, TEXT("nameRu"));
      Card.CardType = StringOrEmpty(C, TEXT("cardType"));
      Card.BannerName = StringOrEmpty(C, TEXT("bannerName"));
      Card.Text = StringOrEmpty(C, TEXT("text"));
      Card.AttackValue = IntOrMinus(C, TEXT("attackValue"));
      Card.DefenseValue = IntOrMinus(C, TEXT("defenseValue"));
      Card.BoostValue = IntOrMinus(C, TEXT("boostValue"));
      Card.Count = FMath::Max(0, IntOrMinus(C, TEXT("count")));
      List.Cards.Add(MoveTemp(Card));
    }
    Out.Add(MoveTemp(List));
  }
  return true;
}

const FS09DeckList* FindList(const TArray<FS09DeckList>& Lists, const FString& PlayerId) {
  if (PlayerId.IsEmpty()) return nullptr;
  for (const FS09DeckList& List : Lists) {
    if (List.PlayerId == PlayerId) return &List;
  }
  return nullptr;
}

FString InputDemandKey(const FS09DeckDemandInput& In) {
  if (In.bGameOver) return TEXT("over:");
  if (!In.OwnDiscardId.IsEmpty()) return TEXT("discard:") + In.OwnDiscardId;
  if (!In.OwnPendingId.IsEmpty()) return TEXT("choice:") + In.OwnPendingId;
  if (In.bViewerDefends) return TEXT("defend:") + In.CombatKey;
  if (In.bViewerTurn) return FString::Printf(TEXT("turn:%d"), In.TurnCount);
  return FString();
}

FString DemandKind(const FString& Key) {
  FString Kind, Rest;
  return Key.Split(TEXT(":"), &Kind, &Rest) ? Kind : Key;
}

const TCHAR* SideName(ES09DeckSide Side) { return Side == ES09DeckSide::Own ? TEXT("own") : TEXT("opp"); }
}  // namespace S09DeckPanel

bool FS09DeckPanelView::Open(ES09DeckSide Side, int64 NowMs, const FString& DemandKey) {
  DemandSeen = DemandKey;
  if (bOpen) {
    if (CurrentSide == Side) return false;
    CurrentSide = Side;  // the other deck: the content switches, the panel stays
    return true;
  }
  FromAlpha = Opacity(NowMs);
  bOpen = true;
  CurrentSide = Side;
  ChangeMs = NowMs;
  return true;
}

bool FS09DeckPanelView::Close(int64 NowMs) {
  if (!bOpen) return false;
  FromAlpha = Opacity(NowMs);
  bOpen = false;
  ChangeMs = NowMs;
  return true;
}

bool FS09DeckPanelView::Toggle(ES09DeckSide Side, int64 NowMs, const FString& DemandKey) {
  if (bOpen && CurrentSide == Side) {
    Close(NowMs);
    return false;
  }
  return Open(Side, NowMs, DemandKey);
}

bool FS09DeckPanelView::NoteDemand(const FString& Key, int64 NowMs) {
  if (Key == DemandSeen) return false;
  DemandSeen = Key;
  if (Key.IsEmpty()) return false;
  return Close(NowMs);
}

float FS09DeckPanelView::Opacity(int64 NowMs) const {
  if (ChangeMs < 0) return 0.0f;
  const float Target = bOpen ? 1.0f : 0.0f;
  const int32 Span = bOpen ? OpenMs : CloseMs;
  const int64 Since = NowMs - ChangeMs;
  if (Since >= Span) return Target;
  const float T = Since <= 0 ? 0.0f : static_cast<float>(Since) / static_cast<float>(Span);
  return FMath::Lerp(FromAlpha, Target, T);
}
