// VS-2 review sheets in the backend-less icon gallery (-S08IconGallery, S08FlowGameModeIconGallery.cpp):
//   -S08IconGallerySkins[=<page>]  HB-10: every 9-slice skin of DA_UmHudTheme in three sizes (its own x1 size, a
//                                  button / panel size, a wide one) on card.navy and on card.cream; the x2 textures at
//                                  DPI x UI scale >= 1.5 (UUmHudTheme::SkinFor). The page holds as many rows as the
//                                  canvas fits; the trace says how many pages there are.
//   -S08IconGalleryButtons[=<n>]   HB-11: UUmButton - 3 variants x 7 states (normal, hover, pressed, disabled, focus,
//                                  selected, busy) with real HUD strings (ST_Hud), the disabled ones with their why.*;
//                                  =1 / =2 / =3: only the normal / primary / disc variant (a page for 720p 150 %).
//   -S08IconGalleryTopStrip        VS-2 HB-14...HB-16: TOP (online / syncing / lost), STATUS in its six SHOT states (with
//                                  the key chips on the first row) at the STATUS width of the window's class, the
//                                  banner at alpha 1 - the real blocks at their layout sizes on fx.dust (review only).
// Trace: 'UMGALLERY skins page=<p>/<n> rows=<r> pxPerSu=<x> x2=0|1 textures=<k>/29' and
//        'UMGALLERY buttons variants=3 states=7 pxPerSu=<x> <variant>.<state>: <DescribeState>'.
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "UmHudGallery.generated.h"

class UBorder;
class UGridPanel;
class UUmButton;

UCLASS()
class UNMATCHED_API UUmSkinGalleryWidget : public UUserWidget {
  GENERATED_BODY()

 public:
  virtual bool Initialize() override;
  /** Builds page Page of the skin sheet for a canvas of CanvasSu at PxPerSu; returns the trace line. */
  FString Build(int32 Page, const FVector2D& CanvasSu, float PxPerSu);
  int32 GetPageCount() const { return PageCount; }

 private:
  UPROPERTY() TObjectPtr<UBorder> Background;
  UPROPERTY() TObjectPtr<UGridPanel> Grid;
  int32 PageCount = 1;
};

UCLASS()
class UNMATCHED_API UUmButtonGalleryWidget : public UUserWidget {
  GENERATED_BODY()

 public:
  virtual bool Initialize() override;
  /** Builds the 3 x 7 sheet for a canvas (states wrap into lines when it is narrow; OnlyVariant 1..3 = one variant -
   *  normal, primary, disc - per page); returns the trace lines. */
  TArray<FString> Build(const FVector2D& CanvasSu, int32 OnlyVariant = 0);
  const TArray<TObjectPtr<UUmButton>>& GetButtons() const { return Buttons; }

 private:
  UPROPERTY() TObjectPtr<UBorder> Background;
  UPROPERTY() TObjectPtr<UGridPanel> Grid;
  UPROPERTY() TArray<TObjectPtr<UUmButton>> Buttons;
};

class UUmHudTop;
class UUmHudStatusLine;
class UUmHudBanner;
class UVerticalBox;

UCLASS()
class UNMATCHED_API UUmTopStripGalleryWidget : public UUserWidget {
  GENERATED_BODY()

 public:
  virtual bool Initialize() override;
  /** Builds the sheet for a canvas of CanvasSu at PxPerSu (the layout class picks the sizes); returns trace lines. */
  TArray<FString> Build(const FVector2D& CanvasSu, float PxPerSu);

 private:
  UPROPERTY() TObjectPtr<UBorder> Background;
  UPROPERTY() TObjectPtr<UVerticalBox> Rows;
  UPROPERTY() TArray<TObjectPtr<UUserWidget>> Blocks;
};
