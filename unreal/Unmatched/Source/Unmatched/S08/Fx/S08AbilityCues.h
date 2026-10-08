// VS-6 F3 FX-28 (docs/game-design/visual/06-tasks/vfx.csv FX-28; CUE-DISPATCHER.md §8 AbilityTriggered): the world-free
// rule that turns one authoritative transition into the CUE-014 cue of Medusa's ability. Her ability is a TARGET_FIGHTER
// pending `ability-medusa-target-p<n>` (backend generic-hero-ability.handler.ts, "At the start of your turn, you may deal
// 1 damage to an opposing fighter in Medusa's zone"); it fired when the id of the previous applied state is gone from
// this snapshot's metadata.pendingEffects AND one of its targetFighterIds lost HP in the same transition. A decline
// (declinePendingEffect: no HP lost) or a pending never created (no target in the zone) gives no cue; the card Gaze of
// Stone is a card, not the ability, and never gives one; a reconnect barrier / gap computes no cues at all.
// King Arthur's ability (a BOOST of his attack) is not a transition rule: it rides the combat staging
// (FS09CombatStageInput::bAbilityBoost, ВР-FX10).
#pragma once

#include "CoreMinimal.h"
#include "../S08FlowController.h"

namespace S08AbilityCues {

/** Appends the AbilityTriggered cues of the transition OldFighters -> NewFighters (DamageCues = the FighterDamaged cues
 *  of the same transition) to OutCues. OldMetadata null or without the pending: nothing. */
UNMATCHED_API void Append(int32 Seq, const TSharedPtr<FJsonValue>& OldFighters, const TSharedPtr<FJsonValue>& NewFighters,
                          const TSharedPtr<FJsonValue>& NewMetadata, const TSharedPtr<FJsonValue>& OldMetadata,
                          const TArray<FS08Cue>& DamageCues, TArray<FS08Cue>& OutCues);

/** The hero key of an ability pending id ("ability-medusa-target-p0" -> "Medusa"), "" for any other id. */
UNMATCHED_API FString HeroKeyOfPending(const FString& PendingId);

}  // namespace S08AbilityCues
