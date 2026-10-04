#include "S08WhyText.h"

namespace S08WhyText {
namespace {
struct FRow {
  const TCHAR* Key;
  const TCHAR* En;
};
// why.*: docs/unreal/contracts/hud/why-reasons.json "en" (same order).
// ms.*: move-selection 03 §9 EN column (ms.begin.already: the M-in-draft
// toast of 03 §3.2, B-03).
const FRow GRows[] = {
    {TEXT("why.not.your.turn"), TEXT("Not your turn")},
    {TEXT("why.no.actions"), TEXT("No actions left")},
    {TEXT("why.defense.only.in.combat"), TEXT("Defense cards are played only in combat")},
    {TEXT("why.banner.mismatch"), TEXT("{bannerName} only")},
    {TEXT("why.syncing"), TEXT("Syncing…")},
    {TEXT("why.wait.defender"), TEXT("Waiting for the defender")},
    {TEXT("why.immobilized"), TEXT("{fighterName} cannot move")},
    {TEXT("why.not.in.range"), TEXT("Target out of range")},
    {TEXT("why.cell.unreachable"), TEXT("Not enough movement: need {need}, have {have}")},
    {TEXT("why.cell.no.path"), TEXT("No way to get there")},
    {TEXT("why.cell.needs.boost"), TEXT("Needs boost +{n}")},
    {TEXT("why.cell.enemy"), TEXT("An enemy is here")},
    {TEXT("why.cell.enemy.path"), TEXT("The path is blocked by an enemy")},
    {TEXT("why.cell.ally"), TEXT("Occupied by an ally")},
    {TEXT("why.cell.occupied"), TEXT("The space is occupied")},
    {TEXT("why.cell.not.linked"), TEXT("These spaces are not linked")},
    {TEXT("why.cell.not.space"), TEXT("Not a board space")},
    {TEXT("why.swap.impossible"), TEXT("Fighters cannot swap spaces")},
    {TEXT("why.draft.conflict"), TEXT("{fighterName}: move is no longer legal")},
    {TEXT("why.draft.open"), TEXT("Confirm the maneuver first")},
    {TEXT("why.fighter.not.yours"), TEXT("That is an opponent's fighter")},
    {TEXT("why.fighter.defeated"), TEXT("Fighter is defeated")},
    {TEXT("why.boost.no.value"), TEXT("This card has no BOOST")},
    {TEXT("why.boost.card.gone"), TEXT("The boost card is no longer in hand")},
    {TEXT("why.maneuver.not.open"), TEXT("No maneuver in progress")},
    {TEXT("why.place.zone"), TEXT("Choose a space in {fighterName}'s zone")},
    {TEXT("why.predraft.lost"), TEXT("Target no longer reachable — choose again")},
    {TEXT("why.wait.opponent.choice"), TEXT("Waiting for the opponent's choice")},
    {TEXT("why.board.too.large"), TEXT("Board wider than 20 — maneuver unavailable")},
    {TEXT("why.state.changed"), TEXT("The game state changed — refreshing")},
    {TEXT("why.client.desync"), TEXT("Out of sync with the server — refreshing")},
    {TEXT("why.command.rejected"), TEXT("Command rejected — refreshing")},
    {TEXT("why.auth.refreshed"), TEXT("Session refreshed — confirm again")},
    {TEXT("why.actions.remaining"), TEXT("Use your actions first: {n} left")},
    {TEXT("why.effect.no.targets"), TEXT("No legal targets — effect skipped")},
    {TEXT("why.defense.none"), TEXT("Nothing to defend with")},
    {TEXT("why.discard.count"), TEXT("Choose {need} cards to discard: {have} chosen")},
    {TEXT("why.scheme.none"), TEXT("Pick a scheme card first")},
    {TEXT("why.choice.required"), TEXT("This choice is mandatory")},
    {TEXT("why.deadline.passed"), TEXT("Time is up — the server resolves")},
    // ---- ms.* (03 §9) ----
    {TEXT("ms.begin.already"), TEXT("Maneuver already begun — Enter confirms")},
    {TEXT("ms.begin.exhaustion"),
     TEXT("Your deck is empty: the maneuver deals 2 damage to each of your fighters ({n})")},
    {TEXT("ms.btn.begin.anyway"), TEXT("Begin anyway")},
    {TEXT("ms.btn.cancel"), TEXT("Cancel")},
    {TEXT("ms.boost.empty"), TEXT("No cards to boost with")},
    {TEXT("ms.confirm.zero"), TEXT("You may stay: confirm the maneuver without moving")},
    {TEXT("ms.order.swap.hint"), TEXT("Change the order (Ctrl+↑/↓)")},
};

const FRow* Find(FName Key) {
  if (Key.IsNone()) return nullptr;
  const FString Wanted = Key.ToString();
  for (const FRow& Row : GRows) {
    if (Wanted.Equals(Row.Key, ESearchCase::CaseSensitive)) return &Row;
  }
  return nullptr;
}
}  // namespace

FString Template(FName Key) {
  const FRow* Row = Find(Key);
  return Row ? FString(Row->En) : FString();
}

bool Has(FName Key) { return Find(Key) != nullptr; }

FString En(FName Key, const TMap<FString, FString>& Args) {
  const FRow* Row = Find(Key);
  if (!Row) return Key.ToString();
  const FString Source(Row->En);
  FString Out;
  Out.Reserve(Source.Len() + 16);
  for (int32 Index = 0; Index < Source.Len(); ++Index) {
    const int32 Close = Source[Index] == TEXT('{') ? Source.Find(TEXT("}"), ESearchCase::CaseSensitive,
                                                                ESearchDir::FromStart, Index)
                                                   : INDEX_NONE;
    if (Close == INDEX_NONE) {
      Out.AppendChar(Source[Index]);
      continue;
    }
    const FString Name = Source.Mid(Index + 1, Close - Index - 1);
    const FString* Value = Args.Find(Name);
    Out += Value && !Value->IsEmpty() ? *Value : FString(TEXT("?"));
    Index = Close;
  }
  return Out;
}

TArray<FName> Keys() {
  TArray<FName> Out;
  for (const FRow& Row : GRows) Out.Add(FName(Row.Key));
  return Out;
}
}  // namespace S08WhyText
