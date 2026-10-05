// DE-030 (W-19; 01 F-05, D-DE-05 "Принято: (б), расширено по DE"; 02 SD-29, SD-41; 02-ux-ui-spec §4.7
// UI-HUD-DECKS "Панель «Колода»"): the world-free model of the side panel with a hero's deck composition, tested by
// Unmatched.S09.DeckPanel.*.
//   - Data (02 §4.7): the PUBLIC deck list of the match (backend gameDeckLists - the composition grouped by catalog id,
//     no order, no instance id), the viewer's own hand (FS09PlayerPanel::Cards) and both public discard piles. The
//     snapshot's decks stay hidden placeholders: only their length (DeckCount) is read, never an entry, never topCard.
//   - Own deck: every card with its copies, "in hand" and "in discard" marks and "left xN" (copies - hand - discard);
//     the panel total "in deck N" is the server's drawPile length, the gap to the copies is "out of play".
//   - Opponent deck: the composition with the "in discard" mark only; the hand is a number of card backs, its cards
//     and the deck are not told apart (no "left" - it would mix the deck with the hidden hand). The model never reads
//     the opponent panel's Cards (empty by construction anyway: FS09HudModel decodes no opponent hand entry).
//   - The view: open <= 100 ms (OpenMs 80), close 150 ms; it closes by itself on an event that asks the viewer for
//     input (InputDemandKey: my turn starts, my defense window, my deferred choice, my hand-limit discard, game over).
// DE's assets, card texts and strings are not copied; the texts of the panel are ours.
#pragma once

#include "CoreMinimal.h"
#include "S09HudModel.h"

class FJsonObject;

/** One catalog card of a deck list (gameDeckLists.cards). Printed values are -1 when the card has none. */
struct UNMATCHED_API FS09DeckListCard {
  FString CardId;
  FString Name;
  FString NameRu;
  FString CardType;
  FString BannerName;
  FString Text;
  int32 AttackValue = -1;
  int32 DefenseValue = -1;
  int32 BoostValue = -1;
  int32 Count = 0;
};

/** One player's deck list. */
struct UNMATCHED_API FS09DeckList {
  FString PlayerId;
  int32 Total = 0;
  TArray<FS09DeckListCard> Cards;
};

enum class ES09DeckSide : uint8 { Own, Opponent };

/** One row of the panel: a catalog card with its copies side by side. */
struct UNMATCHED_API FS09DeckRow {
  FS09DeckListCard Card;
  int32 InHand = 0;     // own deck only (always 0 for the opponent)
  int32 InDiscard = 0;  // both decks: public faces of the discard pile
  int32 Left = -1;      // own deck only: copies - hand - discard (>= 0); -1 = not counted (opponent)
  /** A card view for the inspector (no instance id: the row is a catalog card, not an instance). */
  FS09CardView AsCardView() const;
};

struct UNMATCHED_API FS09DeckPanelModel {
  ES09DeckSide Side = ES09DeckSide::Own;
  FString PlayerId;
  bool bListKnown = false;  // the deck list of this player is loaded
  TArray<FS09DeckRow> Rows;  // the list order (type, then name) - never the draw order
  int32 Copies = 0;          // sum of the copies of the list
  int32 HandCount = 0;       // own: cards in hand; opponent: card backs
  int32 DeckCount = 0;       // the server's drawPile length
  bool bDeckStale = false;
  int32 DiscardCount = 0;
  bool bDiscardStale = false;
  int32 HiddenDiscard = 0;   // face-down discard entries (a committed combat card before the reveal) - not attributed
  int32 Unlisted = 0;        // own hand / discard faces whose cardId is not in the list (counted, not shown as rows)
  /** Own deck: copies - hand - discard - deck when that is >= 0 and the counters are fresh; -1 otherwise. */
  int32 OutOfPlay = -1;

  /** Builds the panel of one side. Panel = that side's FS09PlayerPanel; List = its deck list (null = not loaded). */
  static FS09DeckPanelModel Build(ES09DeckSide Side, const FS09PlayerPanel& Panel, const FS09DeckList* List);
  /** Trace-safe: counts only - no card name, no card id. */
  FString TraceLine() const;
};

/** What asks the viewer for input now (the auto-close of the panel). */
struct UNMATCHED_API FS09DeckDemandInput {
  bool bGameOver = false;
  bool bViewerTurn = false;
  int32 TurnCount = 0;
  /** The defense window is mine (COMBAT, I defend); CombatKey tells two combats apart (the attacker and the target). */
  bool bViewerDefends = false;
  FString CombatKey;
  /** My open deferred choice (the head of pendingEffects is mine) - its id. */
  FString OwnPendingId;
  /** My hand-limit discard (metadata.pendingHandDiscard) - its id. */
  FString OwnDiscardId;
};

namespace S09DeckPanel {
/** Parses the `data` object of gameDeckLists. False (OutError set) on a shape error; an empty array is valid. */
UNMATCHED_API bool ParseDeckLists(const TSharedPtr<FJsonObject>& Data, TArray<FS09DeckList>& Out, FString& OutError);
UNMATCHED_API const FS09DeckList* FindList(const TArray<FS09DeckList>& Lists, const FString& PlayerId);
/** "" = nothing asks for input; otherwise "<kind>:<identity>" (kind over / discard / choice / defend / turn). */
UNMATCHED_API FString InputDemandKey(const FS09DeckDemandInput& In);
/** The kind part of a demand key ("turn" of "turn:5"). */
UNMATCHED_API FString DemandKind(const FString& Key);
UNMATCHED_API const TCHAR* SideName(ES09DeckSide Side);
}  // namespace S09DeckPanel

/** Open / close timing and the auto-close rule of the panel. */
class UNMATCHED_API FS09DeckPanelView {
public:
  static constexpr int32 OpenMs = 80;    // 01 F-05: open <= 100 ms (DE: a slice in 17-50 ms)
  static constexpr int32 CloseMs = 150;  // 01 F-05: close 150 ms (DE 150-200)

  /** Opens Side at NowMs (from the current opacity when it was closing). DemandKey = the demand at the open: the
   *  panel may be opened in my turn and stays until a NEW demand comes. Opening the other side while open switches
   *  the content at once (no new fade). False when Side is already open. */
  bool Open(ES09DeckSide Side, int64 NowMs, const FString& DemandKey);
  /** Starts the 150 ms close; false when already closed / closing. */
  bool Close(int64 NowMs);
  /** Toggle of a side button / key: open Side, or close when Side is the open one. Returns true when it opened. */
  bool Toggle(ES09DeckSide Side, int64 NowMs, const FString& DemandKey);
  /** The demand of the applied state: a change to a non-empty key closes an open panel. Returns true when it closed. */
  bool NoteDemand(const FString& Key, int64 NowMs);
  void Reset() { *this = FS09DeckPanelView(); }

  bool IsOpen() const { return bOpen; }
  ES09DeckSide Side() const { return CurrentSide; }
  /** 0..1 at NowMs: the open ramp, the close ramp; 0 at rest when closed. */
  float Opacity(int64 NowMs) const;
  /** Drawn at NowMs (open, or the close still fading). */
  bool IsVisible(int64 NowMs) const { return Opacity(NowMs) > 0.0f; }
  const FString& LastDemand() const { return DemandSeen; }

private:
  bool bOpen = false;
  ES09DeckSide CurrentSide = ES09DeckSide::Own;
  int64 ChangeMs = -1;
  float FromAlpha = 0.0f;
  FString DemandSeen;
};
