// DE-010 (W-26, 01 F-03): the contact frame of a LungeAttack clip as an AnimNotify named "Contact".
// The v2 figures play their clips single-node (no Anim Blueprint), so the notify is read as data: the combat
// schedule (DE-018) takes its trigger time from the clip (S08HeroesV2::ContactSeconds) and falls back to the frame of
// the clip build profile when a clip has none. A named skeleton notify cannot be added from editor Python (the library
// sets NotifyName from the notify object), so the clips carry this class; its event name is "Contact".
// The notifies are written by tools/art/de010/de010_apply_ue.py (frames from the *-h2anim.json build profiles).
#pragma once

#include "CoreMinimal.h"
#include "Animation/AnimNotifies/AnimNotify.h"
#include "S08ContactAnimNotify.generated.h"

UCLASS(meta = (DisplayName = "S08 Contact"))
class UNMATCHED_API US08ContactAnimNotify : public UAnimNotify {
  GENERATED_BODY()

public:
  virtual FString GetNotifyName_Implementation() const override;
};
