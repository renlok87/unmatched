// VS-5 E4 (docs/game-design/evidence/VISUAL/VS-4/README.md «Открыто» пп. 4, 7, 10): one-line text fitting on the theme's
// type tokens - the width a string takes in a token's font (the Slate font measure service, the composite font with
// its fallbacks) and the first token of a list (largest first) whose line fits a width. Used by the class S HP of the
// player panels and the opponent's hand caption under the pseudo-locale (LEET grows every table string ~30 %).
#pragma once

#include "CoreMinimal.h"

namespace UmTextFit {
/** The su width of Text in the font of a type token at scale 1; -1 without a Slate renderer (a commandlet). */
UNMATCHED_API float WidthSu(const FText& Text, FName Token);
/** The first of Tokens whose line of Text is <= MaxWidthSu (Measure: su of a text in a token); else the last token. */
UNMATCHED_API FName PickToken(const FText& Text, float MaxWidthSu, const TArray<FName>& Tokens,
                              TFunctionRef<float(const FText&, FName)> Measure);
/** PickToken with WidthSu; without a renderer the first token. */
UNMATCHED_API FName PickToken(const FText& Text, float MaxWidthSu, const TArray<FName>& Tokens);
}  // namespace UmTextFit
