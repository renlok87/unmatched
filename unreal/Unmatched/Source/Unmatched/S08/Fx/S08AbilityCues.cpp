// VS-6 F3 FX-28: the AbilityTriggered rule - see S08AbilityCues.h.
#include "S08AbilityCues.h"

#include "../S08BoardModel.h"
#include "../S08Contracts.h"
#include "S08AbilityFx.h"

namespace S08AbilityCues {

FString HeroKeyOfPending(const FString& PendingId) {
  return PendingId.StartsWith(S08AbilityFx::MedusaPendingPrefix, ESearchCase::IgnoreCase) ? FString(TEXT("Medusa"))
                                                                                          : FString();
}

void Append(int32 Seq, const TSharedPtr<FJsonValue>& OldFighters, const TSharedPtr<FJsonValue>& NewFighters,
            const TSharedPtr<FJsonValue>& NewMetadata, const TSharedPtr<FJsonValue>& OldMetadata,
            const TArray<FS08Cue>& DamageCues, TArray<FS08Cue>& OutCues) {
  if (!OldMetadata.IsValid() || DamageCues.Num() == 0) return;
  FS08Snapshot OldSnap;
  OldSnap.Metadata = OldMetadata;
  TArray<FS08PendingEffect> OldPending;
  if (!FS08Contracts::PendingEffects(OldSnap, OldPending)) return;
  FS08Snapshot NewSnap;
  NewSnap.Metadata = NewMetadata;
  TArray<FS08PendingEffect> NewPending;
  FS08Contracts::PendingEffects(NewSnap, NewPending);  // absent / empty: every old pending is resolved
  TArray<FS08BoardFighter> Before, After;
  FS08BoardModel::DecodeFighters(OldFighters, Before);
  FS08BoardModel::DecodeFighters(NewFighters, After);
  for (const FS08PendingEffect& P : OldPending) {
    const FString HeroKey = HeroKeyOfPending(P.Id);
    if (HeroKey.IsEmpty() || P.Type != TEXT("TARGET_FIGHTER")) continue;
    if (NewPending.ContainsByPredicate([&P](const FS08PendingEffect& N) { return N.Id == P.Id; })) continue;
    const FS08Cue* Hit = DamageCues.FindByPredicate([&P](const FS08Cue& C) {
      return C.Type == ES08CueType::FighterDamaged && P.TargetFighterIds.Contains(C.FighterId);
    });
    if (!Hit) continue;  // declined: the pending is gone, nobody lost HP
    // the hero of the pending's player (the ability's figure, the vortex's root)
    const FS08BoardFighter* Hero = After.FindByPredicate([&P](const FS08BoardFighter& F) {
      return F.bIsHero && F.OwnerId == P.PlayerId;
    });
    if (!Hero) {
      Hero = Before.FindByPredicate([&P](const FS08BoardFighter& F) { return F.bIsHero && F.OwnerId == P.PlayerId; });
    }
    if (!Hero) continue;
    const FS08BoardFighter* TargetBefore =
        Before.FindByPredicate([Hit](const FS08BoardFighter& F) { return F.Id == Hit->FighterId; });
    FS08Cue Cue;
    Cue.Type = ES08CueType::AbilityTriggered;
    Cue.SequenceNumber = Seq;
    Cue.FighterId = Hero->Id;
    Cue.TargetId = Hit->FighterId;
    Cue.HeroKey = HeroKey;
    Cue.Damage = Hit->Damage;
    Cue.TargetHpBefore = TargetBefore ? TargetBefore->Health : -1;
    Cue.FromX = TargetBefore ? TargetBefore->X : -1;  // the target's cell before the blow (a lethal one stands there)
    Cue.FromY = TargetBefore ? TargetBefore->Y : -1;
    OutCues.Add(MoveTemp(Cue));
  }
}

}  // namespace S08AbilityCues
