// W4-C hybrid HUD: the view side of the ART-004 art HUD layer behind one
// interface, so the controller (AS08FlowGameMode UpdatePlate/UpdateCombatIcon,
// WriteArtHudShotLines) is identical for both implementations:
//   umg     (default) US08ArtPlateWidget / US08ArtIconWidget - the WBP when it
//           is cooked, else the code default tree of the same classes;
//   slate   the T2.2 Slate widgets, kept behind -ArtHudImpl=slate for the
//           transitional period (A/B evidence and a fallback) until the rest of
//           the HUD moves to UMG in GD-047;
//   compare UMG shown + a Slate twin painted at render opacity 0 in the same
//           canvas slot geometry: every SHOT writes `SHOT widget` lines of
//           both, so "bbox UMG = Slate +-1 px" is checked on the SAME frames;
//   alternate both views in the same slot geometry, only one visible at a
//           time, swapped every few seconds - the game-thread A/B of the two
//           implementations inside ONE process (no between-run drift).
// Every view lives in a slot of the HUD SConstraintCanvas (below the S09
// panels), so the viewport transform (DPI scaler, HudPixelsPerUnit) is the
// one the Slate plate had.
#pragma once

#include "CoreMinimal.h"
#include "Styling/SlateBrush.h"
#include "Widgets/Layout/SConstraintCanvas.h"
#include "S08ArtHudStyle.h"
#include "S08ArtHudText.h"
#include "S08ArtHudWidgets.h"

class SWidget;

enum class ES08ArtHudImpl : uint8 { Umg, Slate, Compare, Alternate };

/** -ArtHudImpl=: "" or "umg" -> Umg, "slate", "compare", "alternate"
 *  (case-insensitive); anything else -> false (the caller traces the refusal
 *  and keeps Umg). alternate = both views, ONE shown at a time, swapped every
 *  -ArtHudAlternateSeconds (default 5): the same-process A/B of the game-thread
 *  cost (PERF summary scope=artHudUmg / artHudSlate). */
bool S08ParseArtHudImpl(const FString& Text, ES08ArtHudImpl& Out);
const TCHAR* S08ArtHudImplName(ES08ArtHudImpl Impl);

class IS08ArtPlateView {
public:
  virtual ~IS08ArtPlateView() = default;
  /** "umg" | "slate" */
  virtual const TCHAR* ImplName() const = 0;
  /** WBP object path, "code-default" (UMG class without a designer tree) or "slate". */
  virtual FString Source() const = 0;
  /** Content of the canvas slot. */
  virtual TSharedRef<SWidget> GetRoot() = 0;
  /** Plate size in HUD slate units (Style tokens of this view). */
  virtual FVector2D SizeSu() const = 0;
  virtual void ApplyTexts(const FS08PlateTexts& Texts) = 0;
  /** HitTestInvisible when shown, Collapsed when hidden. */
  virtual void SetShown(bool bShown) = 0;
  /** Compare-mode twin: laid out and painted, but at render opacity 0. */
  virtual void SetTwin(bool bTwin) = 0;
  virtual void CollectParts(TArray<FS08WidgetPart>& Out) const = 0;

  SConstraintCanvas::FSlot* Slot = nullptr;
  bool bTwin = false;
};

class IS08ArtIconView {
public:
  virtual ~IS08ArtIconView() = default;
  virtual const TCHAR* ImplName() const = 0;
  virtual FString Source() const = 0;
  virtual TSharedRef<SWidget> GetRoot() = 0;
  /** The exact-size texture brush (ImageSize in slate units). */
  virtual void SetIconBrush(const FSlateBrush& Brush) = 0;
  virtual void SetShown(bool bShown) = 0;
  virtual void SetTwin(bool bTwin) = 0;
  virtual void CollectParts(TArray<FS08WidgetPart>& Out) const = 0;

  SConstraintCanvas::FSlot* Slot = nullptr;
  bool bTwin = false;
};

/** The T2.2 Slate plate (same widgets, constants now from the Style tokens). */
TSharedRef<IS08ArtPlateView> S08MakeSlatePlateView(const FS08ArtHudPlateStyle& Style);
TSharedRef<IS08ArtIconView> S08MakeSlateIconView();
/** Views over live UMG widgets (the caller keeps the UObjects referenced). */
TSharedRef<IS08ArtPlateView> S08MakeUmgPlateView(US08ArtPlateWidget& Widget, const FString& Source);
TSharedRef<IS08ArtIconView> S08MakeUmgIconView(US08ArtIconWidget& Widget, const FString& Source);

/** Loads the WBP class of a widget (object path without the _C suffix), or
 *  nullptr when it is not cooked / not a child of Native. */
UClass* S08LoadArtHudWidgetClass(const TCHAR* BlueprintPath, UClass* Native);
