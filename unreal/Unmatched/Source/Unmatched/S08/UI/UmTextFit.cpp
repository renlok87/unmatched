// VS-5 E4: one-line text fitting - see UmTextFit.h.
#include "UmTextFit.h"

#include "UmHudTheme.h"
#include "Fonts/FontMeasure.h"
#include "Framework/Application/SlateApplication.h"
#include "Rendering/SlateRenderer.h"

namespace UmTextFit {
float WidthSu(const FText& Text, FName Token) {
  if (!FSlateApplication::IsInitialized() || !FSlateApplication::Get().GetRenderer()) return -1.0f;
  const TSharedRef<FSlateFontMeasure> Measure = FSlateApplication::Get().GetRenderer()->GetFontMeasureService();
  return static_cast<float>(Measure->Measure(Text, UUmHudTheme::Get().Font(Token), 1.0f).X);
}

FName PickToken(const FText& Text, float MaxWidthSu, const TArray<FName>& Tokens, TFunctionRef<float(const FText&, FName)> Measure) {
  if (Tokens.Num() == 0) return NAME_None;
  for (const FName& T : Tokens) {
    if (Measure(Text, T) <= MaxWidthSu) return T;
  }
  return Tokens.Last();
}

FName PickToken(const FText& Text, float MaxWidthSu, const TArray<FName>& Tokens) {
  if (Tokens.Num() == 0) return NAME_None;
  if (WidthSu(Text, Tokens[0]) < 0.0f) return Tokens[0];
  return PickToken(Text, MaxWidthSu, Tokens, [](const FText& T, FName Token) { return WidthSu(T, Token); });
}
}  // namespace UmTextFit
