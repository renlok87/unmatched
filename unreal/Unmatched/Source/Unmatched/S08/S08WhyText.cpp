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
    // VS-1 HB-05: the screen reasons of visual/04-hud-spec.md §6.1
    {TEXT("why.login.fields"), TEXT("Enter your email and password")},
    {TEXT("why.code.length"), TEXT("Enter 6 characters")},
    {TEXT("why.room.started"), TEXT("The game has already started")},
    {TEXT("why.room.full"), TEXT("The room is full")},
    {TEXT("why.hero.taken"), TEXT("Taken by the opponent")},
    {TEXT("why.room.not.ready"), TEXT("The opponent is not ready")},
    {TEXT("why.room.no.hero"), TEXT("Choose a hero")},
    {TEXT("why.room.board.locked"), TEXT("The board is chosen when the room is created")},
    // ---- ms.* (03 §9) ----
    {TEXT("ms.begin.already"), TEXT("Maneuver already begun — Enter confirms")},
    {TEXT("ms.begin.exhaustion"),
     TEXT("Your deck is empty: the maneuver deals 2 damage to each of your fighters ({n})")},
    {TEXT("ms.btn.begin.anyway"), TEXT("Begin anyway")},
    {TEXT("ms.btn.cancel"), TEXT("Cancel")},
    {TEXT("ms.boost.empty"), TEXT("No cards to boost with")},
    {TEXT("ms.confirm.zero"), TEXT("You may stay: confirm the maneuver without moving")},
    {TEXT("ms.order.swap.hint"), TEXT("Change the order (Ctrl+↑/↓)")},
    // MS-T-12: the pending MOVE / PLACE panel (MS-S-12, MS-R-25)
    {TEXT("ms.pending.move"), TEXT("Effect choice: move {fighterName} up to {n}")},
    {TEXT("ms.pending.move.enemy"), TEXT("You are moving an opponent's fighter: {fighterName}")},
    {TEXT("ms.pending.place"), TEXT("Effect choice: place {fighterName}")},
    {TEXT("ms.btn.stay"), TEXT("Stay in place")},
    {TEXT("ms.btn.decline"), TEXT("Decline (X)")},
    {TEXT("ms.place.no.space"), TEXT("No free space. Waiting for the server")},
    {TEXT("ms.choice.object"), TEXT("Choose what to move")},
    // DE-020 (W-11; 02-ux-ui-spec §4.6, SD-19, SD-28, SD-56): serving the deferred choices
    {TEXT("ms.choice.target"), TEXT("Choose a target (up to {n})")},
    {TEXT("ms.pending.opp.turn"), TEXT("Your choice during the opponent's turn")},
    {TEXT("ms.pending.collapsed"), TEXT("Your choice is waiting: {choice}")},
    {TEXT("ms.pending.again"), TEXT("Again: {choice}")},
    {TEXT("ms.pending.remembered"), TEXT("Last time: {choice}")},
    {TEXT("ms.btn.collapse"), TEXT("Collapse (C)")},
    {TEXT("ms.btn.expand"), TEXT("Expand (C)")},
    {TEXT("ms.ability.boost"), TEXT("{fighterName}: add a BOOST to this attack?")},
    {TEXT("ms.btn.boost.attack"), TEXT("Attack with BOOST (Enter)")},
    {TEXT("ms.btn.noboost"), TEXT("Attack without BOOST (N)")},
    // MS-T-17 (03 §7, §9): the opponent's planning indicator and the event feed
    {TEXT("ms.opp.planning"), TEXT("Opponent is planning a maneuver")},
    {TEXT("ms.log.maneuver"), TEXT("{player}: maneuver{boostPart}: {moves}")},
    {TEXT("ms.log.boost.part"), TEXT(", boost +{n} ({cardName})")},
    {TEXT("ms.log.move"), TEXT("{fighterName} {from}→{to}")},
    {TEXT("ms.log.more"), TEXT("and {n} more")},
    {TEXT("ms.log.stay"), TEXT("no movement")},
    // DE-022 (03 §7 п. 1-3, §9; 02-ux-ui-spec SD-31): the opponent's verb, my fighter moved by their effect, the
    // effect line of the feed and the "what to do now" line (ms.status.*, ms.opp.phase.turn, ms.log.effect - DE-022)
    {TEXT("ms.opp.phase.attack"), TEXT("Opponent is attacking")},
    {TEXT("ms.opp.phase.defend"), TEXT("Opponent is defending")},
    {TEXT("ms.opp.phase.card"), TEXT("Opponent is choosing a card")},
    {TEXT("ms.opp.phase.ability"), TEXT("Opponent is using an ability")},
    {TEXT("ms.opp.phase.turn"), TEXT("Opponent is choosing an action")},
    {TEXT("ms.opp.moves.yours"), TEXT("Your fighter {fighterName}: {cardName} effect")},
    {TEXT("ms.log.effect"), TEXT("{player}: {cardName} effect: {moves}")},
    {TEXT("ms.status.opp"), TEXT("{player} — {verb}")},
    {TEXT("ms.status.action"), TEXT("Choose an action: maneuver (M), attack (A) or scheme (G)")},
    {TEXT("ms.status.end"), TEXT("No actions left: end your turn (E)")},
    {TEXT("ms.status.fighter"), TEXT("Choose a fighter to move")},
    {TEXT("ms.status.space"), TEXT("Choose a space for {fighterName}; Enter confirms the maneuver")},
    {TEXT("ms.status.attacker"), TEXT("Choose the attacking fighter")},
    {TEXT("ms.status.target"), TEXT("Choose a target for {fighterName}")},
    {TEXT("ms.status.attack.card"), TEXT("Choose an attack card against {target} (1–9)")},
    {TEXT("ms.status.attack.go"), TEXT("Attack {target} (Enter)")},
    {TEXT("ms.status.scheme"), TEXT("Choose a scheme card and play it (Enter)")},
    {TEXT("ms.status.defend"), TEXT("You are attacked: choose a defense card or No defense (N)")},
    {TEXT("ms.status.resolve"), TEXT("Resolve the combat (R)")},
    {TEXT("ms.status.discard"), TEXT("Hand over the limit: discard {n}")},
    {TEXT("ms.status.confirm"), TEXT("Confirm (Enter)")},
    {TEXT("ms.status.choice"), TEXT("Make your choice: {choice}")},
    // DE-024 (W-23; 02 SD-42; 02-ux-ui-spec §4.2): the one-shot rule toast of the hand limit (UI-ACC-012)
    {TEXT("ms.hint.hand.limit"), TEXT("Hand limit: {n} cards. At the end of your turn, discard down to {n}")},
    {TEXT("ms.hint.close"), TEXT("Click to close")},
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
