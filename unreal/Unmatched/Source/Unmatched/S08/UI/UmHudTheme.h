// VS-1 HB-04 (04-hud-spec.md §4.1, §4.4; 02 §2.8; ВР-45, ВР-46, ВР-77; HUD-RULES П3, П9): the UMG theme of the HUD.
// WBP and the UUm* C++ bases take colours, fonts, spacing, radii, durations and brushes from ONE asset,
//   /Game/S08/UI/Theme/DA_UmHudTheme (this class),
// imported by tools/s08/hud_contract/hud_theme_import.py from docs/unreal/contracts/hud/hud-style-tokens.json, the same
// JSON that hud_tokens_codegen.py turns into S08HudTokens.generated.h. No literal in a WBP or a base (G-TOKENS).
//   - Colors: FLinearColor::FromSRGBColor(sRGB bytes), alpha = the token alpha (AD-OPEN-39, never hex / 255);
//   - Type: typeface + size of the default Slate composite font (Roboto Bold Condensed / Regular, Engine/Content/Slate/
//     Fonts); FontObject stays empty and Font() fills the composite font at use;
//   - Space / Radius (su) and MotionMs (ms) as floats;
//   - Skins: 29 FSlateRoundedBoxBrush fallbacks under the HB-08 names (ВР-HB06), HB-10 swaps in the 9-slice PNG.
// Without the asset (fresh worktree, missing cook) Get() builds the same maps from S08HudTokens.generated.h and logs
// one Warning; the Slate rollback -S08SlateHud does not read the theme at all.
#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "Fonts/SlateFontInfo.h"
#include "Styling/SlateBrush.h"
#include "UmHudTheme.generated.h"

UCLASS(BlueprintType)
class UNMATCHED_API UUmHudTheme : public UDataAsset {
  GENERATED_BODY()

 public:
  /** Object path of the theme asset. */
  static const TCHAR* const AssetPath;

  /** Colour tokens by name (panel.bg, card.navy, …): linear, alpha = token alpha. */
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Um HUD Theme")
  TMap<FName, FLinearColor> Colors;
  /** Opacity tokens without a colour (state.disabled.opacity) and the alpha of the colour tokens that have one. */
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Um HUD Theme")
  TMap<FName, float> Alphas;
  /** type.* scale (02 §3.3): typeface name + size in su; FontObject empty = the default Slate composite font. */
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Um HUD Theme")
  TMap<FName, FSlateFontInfo> Type;
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Um HUD Theme")
  TMap<FName, float> Space;
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Um HUD Theme")
  TMap<FName, float> Radius;
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Um HUD Theme")
  TMap<FName, float> MotionMs;
  /** 9-slice skins (HB-08 / HB-10) by key: panel, panel.inset, modal, btn.normal … input.error. */
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Um HUD Theme")
  TMap<FName, FSlateBrush> Skins;
  /** sha256 of hud-style-tokens.json the asset was imported from (hud_contract.py validate compares it). */
  UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Um HUD Theme")
  FString TokensJsonSha256;

  /** The theme: the asset (loaded once, rooted), or the header fallback with one Warning. */
  static const UUmHudTheme& Get();
  /** Loads ObjectPath; when it is missing builds the fallback from the header (bOutFallback = true, Warning). */
  static UUmHudTheme* LoadOrFallback(const FString& ObjectPath, bool& bOutFallback);
  /** A transient theme filled from S08HudTokens.generated.h (the asset-less BuildDefaultTree path). */
  static UUmHudTheme* BuildFromHeader(UObject* Outer = nullptr);
  /** Fills every map from S08HudTokens.generated.h (kColors, kAlphas, kTypes, kSpace, kRadius, kMotionMs, kSkins). */
  void FillFromHeader();
  bool IsHeaderFallback() const { return bHeaderFallback; }

  FLinearColor Color(FName Token) const;
  /** Font of a type.* token, composite font resolved (empty FontObject = default Slate font). */
  FSlateFontInfo Font(FName Token) const;
  float SpaceSu(FName Token) const;
  float RadiusSu(FName Token) const;
  float Ms(FName Token) const;
  float Alpha(FName Token) const;
  const FSlateBrush* Skin(FName Key) const;

  // ---- import (UE Python: tools/s08/hud_contract/hud_theme_import.py; FillFromHeader uses the same calls) ----
  UFUNCTION(BlueprintCallable, Category = "Um HUD Theme|Import")
  void ImportReset();
  /** Hex "#RRGGBB" -> FLinearColor::FromSRGBColor(FColor::FromHex(Hex)), A = Alpha. False on a malformed hex. */
  UFUNCTION(BlueprintCallable, Category = "Um HUD Theme|Import")
  bool ImportColor(FName Token, const FString& Hex, float InAlpha);
  UFUNCTION(BlueprintCallable, Category = "Um HUD Theme|Import")
  void ImportAlpha(FName Token, float Value);
  UFUNCTION(BlueprintCallable, Category = "Um HUD Theme|Import")
  void ImportFont(FName Token, FName Typeface, int32 SizeSu);
  UFUNCTION(BlueprintCallable, Category = "Um HUD Theme|Import")
  void ImportSpace(FName Token, float Su);
  UFUNCTION(BlueprintCallable, Category = "Um HUD Theme|Import")
  void ImportRadius(FName Token, float Su);
  UFUNCTION(BlueprintCallable, Category = "Um HUD Theme|Import")
  void ImportMotionMs(FName Token, float InMs);
  /** FSlateRoundedBoxBrush: fill, inner edge EdgeSu (0 = none), corner RadiusSu or half height. */
  UFUNCTION(BlueprintCallable, Category = "Um HUD Theme|Import")
  bool ImportRoundedSkin(FName Key, const FString& FillHex, float FillAlpha, const FString& EdgeHex, float EdgeAlpha,
                         float EdgeSu, float RadiusSu, bool bHalfHeight);
  UFUNCTION(BlueprintCallable, Category = "Um HUD Theme|Import")
  void ImportTokensSha(const FString& Sha256);

 private:
  void SetColor(FName Token, const FColor& Srgb, float InAlpha);
  void SetRoundedSkin(FName Key, const FColor& Fill, float FillAlpha, const FColor& Edge, float EdgeAlpha, float EdgeSu,
                      float RadiusSu, bool bHalfHeight);

  bool bHeaderFallback = false;
};
