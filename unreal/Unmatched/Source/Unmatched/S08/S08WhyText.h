// MS-T-06 (move-selection 03 §8.2, §9): the English texts of the why.* reason
// keys and of the ms.* strings the move-selection input shows, BY KEY. The
// why.* rows are the "en" column of docs/unreal/contracts/hud/why-reasons.json
// (Unmatched.S09.MoveSel.ReasonsAndStrings compares them byte for byte); the
// ms.* rows are the EN column of 03 §9. RU and the StringTable mechanism
// (gather / .locres, packaging) come with MS-T-28 - until then this is the
// one EN table toasts and banners read, so no toast carries hand-written
// English or grid coordinates.
#pragma once

#include "CoreMinimal.h"

namespace S08WhyText {
/** The EN template of Key ("{need}" style arguments); empty when unknown. */
FString Template(FName Key);
bool Has(FName Key);
/** Template with every {arg} of Args replaced; an argument without a value
 *  renders "?"; an unknown key renders the key itself (a visible defect). */
FString En(FName Key, const TMap<FString, FString>& Args = TMap<FString, FString>());
/** Every key of the table (why.* and ms.*), in table order. */
TArray<FName> Keys();
}  // namespace S08WhyText
