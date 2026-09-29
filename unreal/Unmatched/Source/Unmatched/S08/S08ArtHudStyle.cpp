#include "S08ArtHudStyle.h"

#include "Styling/CoreStyle.h"

FSlateFontInfo FS08ArtHudFontToken::Resolve() const {
  if (FontObject) return FSlateFontInfo(FontObject, Size, Typeface);
  return FCoreStyle::GetDefaultFontStyle(Typeface, Size);
}
