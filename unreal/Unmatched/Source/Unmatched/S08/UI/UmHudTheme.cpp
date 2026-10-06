#include "UmHudTheme.h"

#include "../S08HudTokens.generated.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "HAL/PlatformTime.h"
#include "Misc/PackageName.h"
#include "Styling/CoreStyle.h"
#include "UObject/Package.h"

DEFINE_LOG_CATEGORY_STATIC(LogUmHudTheme, Log, All);

const TCHAR* const UUmHudTheme::AssetPath = TEXT("/Game/S08/UI/Theme/DA_UmHudTheme.DA_UmHudTheme");

namespace {
/** One Warning per missing token name (a missing token must not spam the log every frame). */
void WarnMissing(const TCHAR* Map, FName Token) {
  static TSet<FString> Reported;
  const FString Key = FString::Printf(TEXT("%s/%s"), Map, *Token.ToString());
  if (!Reported.Contains(Key)) {
    Reported.Add(Key);
    UE_LOG(LogUmHudTheme, Warning, TEXT("UMHUDTHEME missing %s token '%s'"), Map, *Token.ToString());
  }
}

bool ParseHex(const FString& Hex, FColor& Out) {
  const FString H = Hex.TrimStartAndEnd();
  if (H.Len() != 7 || H[0] != TEXT('#')) return false;
  for (int32 I = 1; I < 7; ++I) {
    if (!FChar::IsHexDigit(H[I])) return false;
  }
  Out = FColor::FromHex(H);
  return true;
}
}  // namespace

const UUmHudTheme& UUmHudTheme::Get() {
  static TWeakObjectPtr<UUmHudTheme> Cached;
  if (UUmHudTheme* Theme = Cached.Get()) return *Theme;
  bool bFallback = false;
  UUmHudTheme* Theme = LoadOrFallback(AssetPath, bFallback);
  Theme->AddToRoot();  // loaded once and kept: 0 ms per frame (HB-04 budget)
  Cached = Theme;
  return *Theme;
}

UUmHudTheme* UUmHudTheme::LoadOrFallback(const FString& ObjectPath, bool& bOutFallback) {
  const double Start = FPlatformTime::Seconds();
  UUmHudTheme* Theme = nullptr;
  const FString PackageName = FPackageName::ObjectPathToPackageName(ObjectPath);
  if (FPackageName::IsValidLongPackageName(PackageName) && FPackageName::DoesPackageExist(PackageName)) {
    Theme = LoadObject<UUmHudTheme>(nullptr, *ObjectPath, nullptr, LOAD_NoWarn | LOAD_Quiet);
  }
  bOutFallback = Theme == nullptr;
  if (!Theme) {
    UE_LOG(LogUmHudTheme, Warning,
           TEXT("UMHUDTHEME asset %s not found - the HUD theme is built from S08HudTokens.generated.h"), *ObjectPath);
    return BuildFromHeader();
  }
  if (Theme->TokensJsonSha256 != S08HudTokens::kTokensJsonSha256) {
    UE_LOG(LogUmHudTheme, Warning,
           TEXT("UMHUDTHEME asset %s was imported from tokens %s, the header is %s - run hud_theme_import.py"),
           *ObjectPath, *Theme->TokensJsonSha256.Left(12), *FString(S08HudTokens::kTokensJsonSha256).Left(12));
  }
  UE_LOG(LogUmHudTheme, Log, TEXT("UMHUDTHEME loaded %s in %.2f ms (colors=%d type=%d skins=%d)"), *ObjectPath,
         (FPlatformTime::Seconds() - Start) * 1000.0, Theme->Colors.Num(), Theme->Type.Num(), Theme->Skins.Num());
  return Theme;
}

UUmHudTheme* UUmHudTheme::BuildFromHeader(UObject* Outer) {
  UUmHudTheme* Theme = NewObject<UUmHudTheme>(Outer ? Outer : GetTransientPackage());
  Theme->FillFromHeader();
  Theme->bHeaderFallback = true;
  return Theme;
}

void UUmHudTheme::FillFromHeader() {
  ImportReset();
  for (const S08HudTokens::FColorToken& C : S08HudTokens::kColors) SetColor(C.Name, C.Srgb, C.Alpha);
  for (const S08HudTokens::FScalarToken& A : S08HudTokens::kAlphas) ImportAlpha(A.Name, A.Value);
  for (const S08HudTokens::FTypeToken& T : S08HudTokens::kTypes) ImportFont(T.Name, T.Face, T.Su);
  for (const S08HudTokens::FScalarToken& S : S08HudTokens::kSpace) ImportSpace(S.Name, S.Value);
  for (const S08HudTokens::FScalarToken& R : S08HudTokens::kRadius) ImportRadius(R.Name, R.Value);
  for (const S08HudTokens::FScalarToken& M : S08HudTokens::kMotionMs) ImportMotionMs(M.Name, M.Value);
  for (int32 I = 0; I < S08HudTokens::kNumSkins; ++I) {
    const S08HudTokens::FSkinToken& S = S08HudTokens::kSkins[I];
    SetRoundedSkin(S.Name, S.Fill, S.FillAlpha, S.Edge, S.EdgeAlpha, S.EdgeSu, S.RadiusSu, S.bHalfHeight);
  }
  ImportTokensSha(S08HudTokens::kTokensJsonSha256);
}

FLinearColor UUmHudTheme::Color(FName Token) const {
  if (const FLinearColor* Found = Colors.Find(Token)) return *Found;
  WarnMissing(TEXT("color"), Token);
  return FLinearColor::Transparent;
}

FSlateFontInfo UUmHudTheme::Font(FName Token) const {
  FName Typeface(TEXT("Regular"));
  float Size = S08HudTokens::TypeSu_Body;
  if (const FSlateFontInfo* Found = Type.Find(Token)) {
    if (Found->FontObject || Found->CompositeFont.IsValid()) return *Found;
    Typeface = Found->TypefaceFontName;
    Size = Found->Size;
  } else {
    WarnMissing(TEXT("type"), Token);
  }
  // Empty FontObject: the typeface of the default Slate composite font (Roboto, Engine/Content/Slate/Fonts).
  return FSlateFontInfo(FCoreStyle::GetDefaultFont(), Size, Typeface);
}

float UUmHudTheme::SpaceSu(FName Token) const {
  if (const float* Found = Space.Find(Token)) return *Found;
  WarnMissing(TEXT("space"), Token);
  return 0.0f;
}

float UUmHudTheme::RadiusSu(FName Token) const {
  if (const float* Found = Radius.Find(Token)) return *Found;
  WarnMissing(TEXT("radius"), Token);
  return 0.0f;
}

float UUmHudTheme::Ms(FName Token) const {
  if (const float* Found = MotionMs.Find(Token)) return *Found;
  WarnMissing(TEXT("motion"), Token);
  return 0.0f;
}

float UUmHudTheme::Alpha(FName Token) const {
  if (const float* Found = Alphas.Find(Token)) return *Found;
  WarnMissing(TEXT("alpha"), Token);
  return 1.0f;
}

const FSlateBrush* UUmHudTheme::Skin(FName Key) const {
  const FSlateBrush* Found = Skins.Find(Key);
  if (!Found) WarnMissing(TEXT("skin"), Key);
  return Found;
}

void UUmHudTheme::ImportReset() {
  Colors.Reset();
  Alphas.Reset();
  Type.Reset();
  Space.Reset();
  Radius.Reset();
  MotionMs.Reset();
  Skins.Reset();
  TokensJsonSha256.Reset();
}

bool UUmHudTheme::ImportColor(FName Token, const FString& Hex, float InAlpha) {
  FColor Srgb;
  if (!ParseHex(Hex, Srgb)) {
    UE_LOG(LogUmHudTheme, Error, TEXT("UMHUDTHEME import: color '%s' hex '%s'"), *Token.ToString(), *Hex);
    return false;
  }
  SetColor(Token, Srgb, InAlpha);
  return true;
}

void UUmHudTheme::ImportAlpha(FName Token, float Value) { Alphas.Add(Token, FMath::Clamp(Value, 0.0f, 1.0f)); }

void UUmHudTheme::ImportFont(FName Token, FName Typeface, int32 SizeSu) {
  FSlateFontInfo Info;  // FontObject stays empty: Font() resolves the default composite font
  Info.TypefaceFontName = Typeface;
  Info.Size = static_cast<float>(SizeSu);
  Type.Add(Token, Info);
}

void UUmHudTheme::ImportSpace(FName Token, float Su) { Space.Add(Token, Su); }
void UUmHudTheme::ImportRadius(FName Token, float Su) { Radius.Add(Token, Su); }
void UUmHudTheme::ImportMotionMs(FName Token, float InMs) { MotionMs.Add(Token, InMs); }

bool UUmHudTheme::ImportRoundedSkin(FName Key, const FString& FillHex, float FillAlpha, const FString& EdgeHex,
                                    float EdgeAlpha, float EdgeSu, float RadiusSu, bool bHalfHeight) {
  FColor Fill;
  FColor Edge;
  if (!ParseHex(FillHex, Fill) || !ParseHex(EdgeHex, Edge)) {
    UE_LOG(LogUmHudTheme, Error, TEXT("UMHUDTHEME import: skin '%s' hex '%s' / '%s'"), *Key.ToString(), *FillHex, *EdgeHex);
    return false;
  }
  SetRoundedSkin(Key, Fill, FillAlpha, Edge, EdgeAlpha, EdgeSu, RadiusSu, bHalfHeight);
  return true;
}

void UUmHudTheme::ImportTokensSha(const FString& Sha256) { TokensJsonSha256 = Sha256; }

void UUmHudTheme::SetColor(FName Token, const FColor& Srgb, float InAlpha) {
  FLinearColor Linear = FLinearColor::FromSRGBColor(Srgb);  // AD-OPEN-39: never hex / 255
  Linear.A = FMath::Clamp(InAlpha, 0.0f, 1.0f);
  Colors.Add(Token, Linear);
}

void UUmHudTheme::SetRoundedSkin(FName Key, const FColor& Fill, float FillAlpha, const FColor& Edge, float EdgeAlpha,
                                 float EdgeSu, float RadiusSu, bool bHalfHeight) {
  FLinearColor FillColor = FLinearColor::FromSRGBColor(Fill);
  FillColor.A = FMath::Clamp(FillAlpha, 0.0f, 1.0f);
  FLinearColor EdgeColor = FLinearColor::FromSRGBColor(Edge);
  EdgeColor.A = EdgeSu > 0.0f ? FMath::Clamp(EdgeAlpha, 0.0f, 1.0f) : 0.0f;
  const float Width = FMath::Max(EdgeSu, 0.0f);
  // ВР-HB06: the fallback brush until the 9-slice PNG of HB-08 (HB-10 replaces it under the same key)
  const FSlateBrush Brush = bHalfHeight ? FSlateBrush(FSlateRoundedBoxBrush(FillColor, EdgeColor, Width))
                                        : FSlateBrush(FSlateRoundedBoxBrush(FillColor, RadiusSu, EdgeColor, Width));
  Skins.Add(Key, Brush);
}
