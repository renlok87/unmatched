// HUD icon motion v3 (docs/unreal/contracts/hud/ICON-MOTION-PLAN.md): an animated HUD icon and the
// backend-less gallery that plays every icon's demo script (-S08IconGallery).
//
// US08AnimatedIconWidget is a native UUserWidget with a code-built tree (no WBP):
//   SizeBox (icon side in slate units x canvas) > Overlay "Stage" (root pose) > one UImage per layer (layer pose).
// The pose comes from FS08IconAnimator (S08IconMotion.h) - the same numbers the Python reference renders.
// Root and layers get RenderTransform (scale, rotate, translate around the contract pivot) and RenderOpacity;
// a flipbook layer swaps its texture. Nothing is clipped, so overscale (appear 1.04, token 1.25) draws outside.
// Ticks only while the animator moves (plus one settle frame), so idle icons cost nothing but the tick call.
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "S08IconMotion.h"
#include "S08AnimatedIconWidget.generated.h"

class UImage;
class UOverlay;
class USizeBox;
class UTextBlock;
class UTexture2D;
class UUniformGridPanel;
class UBorder;
struct FUmHudScaleState;

UCLASS()
class UNMATCHED_API US08AnimatedIconWidget : public UUserWidget {
  GENERATED_BODY()

public:
  virtual bool Initialize() override;

  /** Icon from the motion contract (variants resolve to their base). SizeSu = icon side in slate units
   *  (32 u canvas); TexturePx = exact-size texture to sample (24 / 32 / 48 / 64). false = unknown icon. */
  bool SetIcon(FName IconId, float InSizeSu, int32 InTexturePx);
  /** VS-2 HB-23 (02 §5.3, И-9; IC-33): the icon side in su; the texture is the export for su x DPI x UI scale
   *  (S08IconMotion::ExportSizePx: 24 su at 720p -> 18, at 1080p 150 % -> 36; 32 su at 150 % -> 48), re-picked on
   *  UmHudScale::OnUiScaleChanged - an event, no tick; only the needed size is loaded. Call after SetIcon (any
   *  TexturePx there); -S08IconLegacy keeps the texture of the su itself. Trace (on a change):
   *  'ICON size su=<x> px=<y> tex=<asset> icon=<id> dpiScale=<px per su> legacy=0|1 clamped=0|1'. */
  void SetDisplaySizeSu(float InSu);
  float GetDisplaySizeSu() const { return DisplaySizeSu; }
  int32 GetTexturePx() const { return TexturePx; }
  /** The px per su the last pick used (tests force it; 0 = UmHudScale::Current()). */
  void SetPxPerSuOverrideForTest(float InPxPerSu) { PxPerSuOverride = InPxPerSu; }
  /** Plays a contract animation at the widget clock. */
  bool PlayAnim(FName Anim);
  /** Plays at an explicit time (gallery replay, tests). */
  bool PlayAnimAt(FName Anim, float TMs);
  void SetTeamTint(const FLinearColor& Tint);
  /** Re-initialises the animator (the icon becomes hidden until the next appear). */
  void SetReducedMotion(bool bInReduced);
  bool IsReducedMotion() const { return bReduced; }
  /** >= 0 freezes the widget clock at Ms (deterministic shots, tests); < 0 resumes ticking from the current time. */
  void SetClockOverrideMs(float Ms);
  float GetClockMs() const { return ClockOverrideMs >= 0.0f ? ClockOverrideMs : ClockMs; }
  /** Applies the pose at TMs to the widget tree. */
  void ApplyPose(float TMs);
  /** Driven by a parent (the gallery replays and applies poses itself): the widget's own tick does nothing. */
  void SetExternallyDriven(bool bInExternal) { bExternal = bInExternal; }
  /** DE-023: a layer drawn at opacity 0 whatever the pose says (the HUD heart plays damage without the DE-012 `glow`
   *  candidate layer until the user's art acceptance). Survives SetIcon of the same icon. */
  void SetLayerHidden(FName LayerId, bool bHidden);
  bool IsLayerHidden(FName LayerId) const { return HiddenLayers.Contains(LayerId); }
  /** Run I (AB-7): draw a single-frame layer from another contract texture src (the DE tracker slot fills its
   *  body / glyph layers with action-<type>_body / _glyph). Survives SetIcon of the same icon; a new icon drops it.
   *  False = no such layer, a flipbook layer, or the texture is missing (the layer keeps its texture). */
  bool SetLayerSource(FName LayerId, const FString& Src);
  /** The src a layer draws now (the contract's, or the SetLayerSource override); '' for no such layer. */
  FString GetLayerSource(FName LayerId) const;
  /** DE-023: the icon at rest now, without its appear (a HUD tracker reset "in one frame", 01 F-12); with HeldEvent a
   *  hold event (spend) already played out - the reconnect mid-turn state. */
  void ShowAtRest(FName HeldEvent = NAME_None);

  FS08IconAnimator& GetAnimator() { return Animator; }
  const FS08IconPose& GetLastPose() const { return LastPose; }
  UOverlay* GetStage() const { return Stage; }
  int32 GetLayerCount() const { return LayerImages.Num(); }
  UImage* GetLayerImage(int32 Index) const { return LayerImages.IsValidIndex(Index) ? LayerImages[Index] : nullptr; }
  UTexture2D* GetLayerTexture(int32 Layer, int32 Frame) const;
  FName GetIconId() const { return IconId; }
  FVector2D GetCanvasSizeSu() const;

protected:
  virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;
  virtual void BeginDestroy() override;

private:
  void PickDisplayTexture();
  void HandleUiScaleChanged(const FUmHudScaleState& State);
  float DisplaySizeSu = 0.0f;
  float PxPerSuOverride = 0.0f;
  FDelegateHandle ScaleChangedHandle;

  UPROPERTY() TObjectPtr<USizeBox> Box;
  UPROPERTY() TObjectPtr<UOverlay> Stage;
  UPROPERTY() TArray<TObjectPtr<UImage>> LayerImages;
  UPROPERTY() TArray<TObjectPtr<UTexture2D>> Textures;  // flat: LayerFirstTexture[layer] + frame

  FS08IconAnimator Animator;
  FS08IconPose LastPose;
  const FS08IconMotionDef* Def = nullptr;
  FName IconId;
  TArray<int32> LayerFirstTexture;
  TArray<int32> LayerFrameCount;
  TArray<int32> CurrentFrame;
  float SizeSu = 48.0f;
  int32 TexturePx = 48;
  float ClockMs = 0.0f;
  float ClockOverrideMs = -1.0f;
  bool bReduced = false;
  bool bDirty = true;
  bool bWasMoving = false;
  bool bExternal = false;
  FLinearColor TeamTint = FLinearColor::White;
  TSet<FName> HiddenLayers;
  TMap<FName, FString> LayerSources;  // SetLayerSource overrides (layer id -> src)
};

/** Backend-less gallery: every contract icon in a grid on the HUD panel colour, each looping its demo script
 *  (the same script the Python reference renders). Deterministic: the pose at clock t replays the script from 0. */
UCLASS()
class UNMATCHED_API US08IconGalleryWidget : public UUserWidget {
  GENERATED_BODY()

public:
  virtual bool Initialize() override;
  /** Builds the grid; SizeSu = icon side, TexturePx = texture size (<= 0: by display size, HB-23). Returns the icon
   *  count. */
  int32 Build(float InSizeSu, int32 InTexturePx, bool bInReduced, int32 Columns = 6, bool bLabels = true);
  /** >= 0 freezes the gallery clock (shots); < 0 = real time. */
  void SetClockOverrideMs(float Ms) { ClockOverrideMs = Ms; }
  float GetClockMs() const { return ClockOverrideMs >= 0.0f ? ClockOverrideMs : ClockMs; }
  /** Pose of every icon at gallery time TMs (icon i loops with its own period = demo + PauseMs). */
  void EvaluateAt(float TMs);
  int32 GetIconCount() const { return Icons.Num(); }
  US08AnimatedIconWidget* GetIcon(int32 Index) const { return Icons.IsValidIndex(Index) ? Icons[Index] : nullptr; }
  static constexpr float PauseMs = 400.0f;
  /** Cost of EvaluateAt (all icons: replay + pose + render transforms) per frame since Build: "avg p95 max frames". */
  FString PerfSummary() const;
  void ResetPerf() { EvalSamples.Reset(); }

protected:
  virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;

private:
  UPROPERTY() TObjectPtr<UBorder> Background;
  UPROPERTY() TObjectPtr<UUniformGridPanel> Grid;
  UPROPERTY() TArray<TObjectPtr<US08AnimatedIconWidget>> Icons;

  struct FScript {
    TArray<TPair<float, FName>> Commands;
    float PeriodMs = 1.0f;
  };
  TArray<FScript> Scripts;
  bool bReduced = false;
  float ClockMs = 0.0f;
  float ClockOverrideMs = -1.0f;
  TArray<float> EvalSamples;
};
