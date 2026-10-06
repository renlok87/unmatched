#include "S08AnimatedIconWidget.h"

#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/Image.h"
#include "Components/Overlay.h"
#include "Components/OverlaySlot.h"
#include "Components/SizeBox.h"
#include "Components/TextBlock.h"
#include "Components/UniformGridPanel.h"
#include "Components/UniformGridSlot.h"
#include "Engine/Texture2D.h"
#include "Misc/CommandLine.h"
#include "S08TraceLog.h"
#include "UI/UmHudScale.h"

namespace {
FLinearColor S08Srgb(uint8 R, uint8 G, uint8 B, float A = 1.0f) {
  FLinearColor C = FLinearColor::FromSRGBColor(FColor(R, G, B));
  C.A = A;
  return C;
}

bool SameTransform(const FWidgetTransform& A, const FWidgetTransform& B) {
  return A.Translation.Equals(B.Translation, 1.0e-4) && A.Scale.Equals(B.Scale, 1.0e-5) &&
         FMath::IsNearlyEqual(A.Angle, B.Angle, 1.0e-4f);
}

/** Sets transform / pivot / opacity only when they change: an idle icon then invalidates nothing. */
void ApplyIfChanged(UWidget& W, const FWidgetTransform& T, const FVector2D& Pivot, float Opacity) {
  if (!W.GetRenderTransformPivot().Equals(Pivot, 1.0e-5)) W.SetRenderTransformPivot(Pivot);
  if (!SameTransform(W.GetRenderTransform(), T)) W.SetRenderTransform(T);
  if (!FMath::IsNearlyEqual(W.GetRenderOpacity(), Opacity, 1.0e-4f)) W.SetRenderOpacity(Opacity);
}

FWidgetTransform ToWidgetTransform(const FS08IconTargetPose& P, float SuPerU) {
  const float S = P.Get(ES08IconProp::Scale);
  return FWidgetTransform(FVector2D(P.Get(ES08IconProp::Tx), P.Get(ES08IconProp::Ty)) * SuPerU,
                          FVector2D(S * P.Get(ES08IconProp::ScaleX), S * P.Get(ES08IconProp::ScaleY)),
                          FVector2D::ZeroVector, P.Get(ES08IconProp::Rotate));
}
}  // namespace

// ------------------------------------------------------------------------------------------- icon

bool US08AnimatedIconWidget::Initialize() {
  const bool bFirst = Super::Initialize();
  if (bFirst && WidgetTree && !WidgetTree->RootWidget) {
    Box = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass(), TEXT("Box"));
    Stage = WidgetTree->ConstructWidget<UOverlay>(UOverlay::StaticClass(), TEXT("Stage"));
    Box->AddChild(Stage);
    WidgetTree->RootWidget = Box;
    bReduced = S08IconMotion::IsReducedMotion();
  }
  return bFirst;
}

FVector2D US08AnimatedIconWidget::GetCanvasSizeSu() const {
  return Def ? Def->CanvasU * (SizeSu / 32.0f) : FVector2D(SizeSu, SizeSu);
}

UTexture2D* US08AnimatedIconWidget::GetLayerTexture(int32 Layer, int32 Frame) const {
  if (!LayerFirstTexture.IsValidIndex(Layer)) return nullptr;
  const int32 N = LayerFrameCount[Layer];
  const int32 Index = LayerFirstTexture[Layer] + FMath::Clamp(Frame, 0, FMath::Max(N - 1, 0));
  return Textures.IsValidIndex(Index) ? Textures[Index].Get() : nullptr;
}

bool US08AnimatedIconWidget::SetIcon(FName InIconId, float InSizeSu, int32 InTexturePx) {
  const FS08IconMotionDef* NewDef = FS08IconMotionLibrary::Get().Find(InIconId);
  if (!NewDef || !Stage || !Box) return false;
  // Same icon, new size (DPI, zoom): rebuild the images but keep the animation state (no restart of appear/pulse).
  const bool bSameIcon = NewDef == Def && InIconId == IconId;
  if (!bSameIcon) LayerSources.Reset();
  Def = NewDef;
  IconId = InIconId;
  SizeSu = InSizeSu;
  TexturePx = InTexturePx;
  Stage->ClearChildren();
  LayerImages.Reset();
  Textures.Reset();
  LayerFirstTexture.Reset();
  LayerFrameCount.Reset();
  CurrentFrame.Reset();
  const FVector2D Size = GetCanvasSizeSu();
  Box->SetWidthOverride(Size.X);
  Box->SetHeightOverride(Size.Y);
  // Variants of the same id (resource-hp-full-enemy) keep the base icon's animations but draw their own texture:
  // a whole-icon layer whose src is the base id takes the variant id.
  const FString BaseId = Def->Icon.ToString();
  for (int32 L = 0; L < Def->Layers.Num(); ++L) {
    const FS08IconLayer& Layer = Def->Layers[L];
    FString Src = Layer.Src;
    if (Src == BaseId && InIconId != Def->Icon) Src = InIconId.ToString();
    if (const FString* Override = LayerSources.Find(Layer.Id)) Src = *Override;
    const int32 Frames = Src.EndsWith(TEXT("#")) ? FMath::Max(Layer.Frames, 1) : 1;
    LayerFirstTexture.Add(Textures.Num());
    LayerFrameCount.Add(Frames);
    for (int32 F = 0; F < Frames; ++F) {
      const FString Path = S08IconMotion::TextureObjectPath(Src, F, TexturePx);
      UTexture2D* Tex = LoadObject<UTexture2D>(nullptr, *Path);
      if (!Tex) UE_LOG(LogTemp, Warning, TEXT("S08 icon motion: texture %s not found"), *Path);
      Textures.Add(Tex);
    }
    UImage* Image = WidgetTree->ConstructWidget<UImage>(UImage::StaticClass());
    FSlateBrush Brush;
    Brush.SetResourceObject(GetLayerTexture(L, 0));
    Brush.ImageSize = Size;
    Brush.DrawAs = ESlateBrushDrawType::Image;
    Image->SetBrush(Brush);
    if (Layer.bTintTeam) Image->SetColorAndOpacity(TeamTint);
    UOverlaySlot* LayerSlot = Stage->AddChildToOverlay(Image);
    LayerSlot->SetHorizontalAlignment(HAlign_Fill);
    LayerSlot->SetVerticalAlignment(VAlign_Fill);
    LayerImages.Add(Image);
    CurrentFrame.Add(0);
  }
  if (!bSameIcon) Animator.Init(Def, bReduced);
  bDirty = true;
  ApplyPose(GetClockMs());
  return true;
}

void US08AnimatedIconWidget::SetDisplaySizeSu(float InSu) {
  DisplaySizeSu = FMath::Max(InSu, 1.0f);
  if (!ScaleChangedHandle.IsValid()) {
    ScaleChangedHandle = UmHudScale::OnUiScaleChanged().AddUObject(this, &US08AnimatedIconWidget::HandleUiScaleChanged);
  }
  PickDisplayTexture();
}

void US08AnimatedIconWidget::HandleUiScaleChanged(const FUmHudScaleState& /*State*/) {
  if (DisplaySizeSu > 0.0f) PickDisplayTexture();
}

void US08AnimatedIconWidget::PickDisplayTexture() {
  if (!Def || DisplaySizeSu <= 0.0f) return;
  const bool bLegacy = S08IconMotion::IconSizeLegacy(FCommandLine::Get());
  const float PxPerSu = PxPerSuOverride > 0.0f ? PxPerSuOverride : UmHudScale::Current().PxPerSu();
  bool bClamped = false;
  const int32 Wanted = S08IconMotion::ExportSizePx(DisplaySizeSu, bLegacy ? 1.0f : PxPerSu, &bClamped);
  if (bClamped) {
    UE_LOG(LogTemp, Warning, TEXT("S08 icon %s: %.0f su x %.3f needs more than the largest export - 64 is used"),
           *IconId.ToString(), DisplaySizeSu, PxPerSu);
  }
  if (Wanted == TexturePx && FMath::IsNearlyEqual(SizeSu, DisplaySizeSu)) return;
  // same icon: SetIcon keeps the animation state and rebuilds only the images at the new texture size
  SetIcon(IconId, DisplaySizeSu, Wanted);
  const FString Src = Def->Layers.Num() ? Def->Layers[0].Src : IconId.ToString();
  const FString Path = S08IconMotion::TextureObjectPath(Src, 0, Wanted);
  FString Asset;
  Path.Split(TEXT("."), nullptr, &Asset);
  FS08Trace::Write(FString::Printf(TEXT("ICON size su=%.0f px=%.1f tex=%s icon=%s dpiScale=%.3f legacy=%d clamped=%d"),
                                   DisplaySizeSu, DisplaySizeSu * (bLegacy ? 1.0f : PxPerSu), *Asset,
                                   *IconId.ToString(), PxPerSu, bLegacy ? 1 : 0, bClamped ? 1 : 0));
}

void US08AnimatedIconWidget::BeginDestroy() {
  if (ScaleChangedHandle.IsValid()) {
    UmHudScale::OnUiScaleChanged().Remove(ScaleChangedHandle);
    ScaleChangedHandle.Reset();
  }
  Super::BeginDestroy();
}

bool US08AnimatedIconWidget::PlayAnim(FName Anim) { return PlayAnimAt(Anim, GetClockMs()); }

bool US08AnimatedIconWidget::PlayAnimAt(FName Anim, float TMs) {
  const bool bOk = Animator.Play(Anim, TMs);
  bDirty |= bOk;
  return bOk;
}

void US08AnimatedIconWidget::SetTeamTint(const FLinearColor& Tint) {
  TeamTint = Tint;
  if (!Def) return;
  for (int32 L = 0; L < Def->Layers.Num() && L < LayerImages.Num(); ++L) {
    if (Def->Layers[L].bTintTeam) LayerImages[L]->SetColorAndOpacity(TeamTint);
  }
}

void US08AnimatedIconWidget::SetReducedMotion(bool bInReduced) {
  bReduced = bInReduced;
  Animator.Init(Def, bReduced);
  bDirty = true;
}

void US08AnimatedIconWidget::SetLayerHidden(FName LayerId, bool bHidden) {
  const bool bChanged = bHidden ? !HiddenLayers.Contains(LayerId) : HiddenLayers.Contains(LayerId);
  if (bHidden) {
    HiddenLayers.Add(LayerId);
  } else {
    HiddenLayers.Remove(LayerId);
  }
  if (bChanged) {
    bDirty = true;
    ApplyPose(GetClockMs());
  }
}

bool US08AnimatedIconWidget::SetLayerSource(FName LayerId, const FString& Src) {
  if (!Def || Src.IsEmpty() || Src.EndsWith(TEXT("#"))) return false;
  for (int32 L = 0; L < Def->Layers.Num() && L < LayerImages.Num(); ++L) {
    if (Def->Layers[L].Id != LayerId) continue;
    if (LayerFrameCount[L] != 1) return false;
    if (GetLayerSource(LayerId) == Src) return true;
    UTexture2D* Tex = LoadObject<UTexture2D>(nullptr, *S08IconMotion::TextureObjectPath(Src, 0, TexturePx));
    if (!Tex) {
      UE_LOG(LogTemp, Warning, TEXT("S08 icon motion: layer %s src %s not found"), *LayerId.ToString(), *Src);
      return false;
    }
    Textures[LayerFirstTexture[L]] = Tex;
    FSlateBrush Brush = LayerImages[L]->GetBrush();
    Brush.SetResourceObject(Tex);
    LayerImages[L]->SetBrush(Brush);
    LayerSources.Add(LayerId, Src);
    return true;
  }
  return false;
}

FString US08AnimatedIconWidget::GetLayerSource(FName LayerId) const {
  if (const FString* Override = LayerSources.Find(LayerId)) return *Override;
  if (!Def) return FString();
  for (const FS08IconLayer& Layer : Def->Layers) {
    if (Layer.Id == LayerId) return Layer.Src;
  }
  return FString();
}

void US08AnimatedIconWidget::ShowAtRest(FName HeldEvent) {
  if (!Def) return;
  // a fresh animator, the appear (and the held event) far enough in the past to be over: the pose is the rest pose now
  constexpr float Past = 100000.0f;
  const float T = GetClockMs();
  Animator.Init(Def, bReduced);
  Animator.Play(TEXT("appear"), T - Past);
  if (!HeldEvent.IsNone()) Animator.Play(HeldEvent, T - Past * 0.5f);
  bDirty = true;
  ApplyPose(T);
}

void US08AnimatedIconWidget::SetClockOverrideMs(float Ms) {
  if (Ms == ClockOverrideMs) return;  // the gallery sets the same frozen time every frame: no second ApplyPose
  if (Ms < 0.0f && ClockOverrideMs >= 0.0f) ClockMs = ClockOverrideMs;
  ClockOverrideMs = Ms;
  bDirty = true;
}

void US08AnimatedIconWidget::ApplyPose(float TMs) {
  if (!Def || !Stage || !Box) return;
  LastPose = Animator.Pose(TMs);
  const ESlateVisibility Vis = LastPose.bVisible ? ESlateVisibility::SelfHitTestInvisible : ESlateVisibility::Hidden;
  if (Box->GetVisibility() != Vis) Box->SetVisibility(Vis);
  if (!LastPose.bVisible) return;
  const float SuPerU = SizeSu / 32.0f;
  const FVector2D Canvas = Def->CanvasU;
  const FS08IconTargetPose& Root = LastPose.Targets[0];
  ApplyIfChanged(*Stage, ToWidgetTransform(Root, SuPerU), Root.PivotU / Canvas, Root.Get(ES08IconProp::Opacity));
  for (int32 L = 0; L < LayerImages.Num(); ++L) {
    const FS08IconTargetPose& P = LastPose.Targets[L + 1];
    UImage* Image = LayerImages[L];
    const float Opacity = HiddenLayers.Contains(Def->Layers[L].Id) ? 0.0f : P.Get(ES08IconProp::Opacity);
    ApplyIfChanged(*Image, ToWidgetTransform(P, SuPerU), P.PivotU / Canvas, Opacity);
    const int32 Frame = FMath::FloorToInt(P.Get(ES08IconProp::Frame) + 1.0e-4f);
    if (LayerFrameCount[L] > 1 && Frame != CurrentFrame[L]) {
      CurrentFrame[L] = Frame;
      FSlateBrush Brush = Image->GetBrush();
      Brush.SetResourceObject(GetLayerTexture(L, Frame));
      Image->SetBrush(Brush);
    }
  }
}

void US08AnimatedIconWidget::NativeTick(const FGeometry& MyGeometry, float InDeltaTime) {
  Super::NativeTick(MyGeometry, InDeltaTime);
  if (bExternal) return;
  if (ClockOverrideMs < 0.0f) ClockMs += InDeltaTime * 1000.0f;
  const float T = GetClockMs();
  const bool bMoving = Animator.IsMoving(T);
  // Moving, just stopped (settle on the final pose), or a command/clock change since the last frame.
  if (bMoving || bWasMoving || bDirty) {
    ApplyPose(T);
    bDirty = false;
  }
  bWasMoving = bMoving;
}

// ------------------------------------------------------------------------------------------- gallery

bool US08IconGalleryWidget::Initialize() {
  const bool bFirst = Super::Initialize();
  if (bFirst && WidgetTree && !WidgetTree->RootWidget) {
    Background = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(), TEXT("Background"));
    Background->SetBrushColor(S08Srgb(0x1E, 0x20, 0x28));  // sheet background of the reference (D.SHEET_BG)
    Background->SetHorizontalAlignment(HAlign_Center);
    Background->SetVerticalAlignment(VAlign_Center);
    Grid = WidgetTree->ConstructWidget<UUniformGridPanel>(UUniformGridPanel::StaticClass(), TEXT("Grid"));
    Grid->SetSlotPadding(FMargin(SlotPaddingSu));
    Background->SetContent(Grid);
    WidgetTree->RootWidget = Background;
  }
  return bFirst;
}

int32 US08IconGalleryWidget::Build(float InSizeSu, int32 InTexturePx, bool bInReduced, int32 Columns, bool bLabels) {
  if (!Grid) return 0;
  bReduced = bInReduced;
  Grid->ClearChildren();
  Icons.Reset();
  Scripts.Reset();
  const FS08IconMotionLibrary& Lib = FS08IconMotionLibrary::Get();
  const float Pad = FMath::RoundToFloat(0.25f * InSizeSu);
  const FVector2D Cell = CellSizeSu(InSizeSu);
  int32 Index = 0;
  for (const FName Id : Lib.Order) {
    const FS08IconMotionDef* Def = Lib.Find(Id);
    if (!Def) continue;
    USizeBox* CellBox = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass());
    CellBox->SetWidthOverride(Cell.X);
    CellBox->SetHeightOverride(Cell.Y);
    UBorder* Panel = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass());
    Panel->SetBrushColor(S08Srgb(0x16, 0x1A, 0x28));  // tag.background - the HUD panel
    Panel->SetPadding(FMargin(0.0f));
    CellBox->AddChild(Panel);
    UOverlay* Ov = WidgetTree->ConstructWidget<UOverlay>(UOverlay::StaticClass());
    Panel->SetContent(Ov);
    US08AnimatedIconWidget* Icon = CreateWidget<US08AnimatedIconWidget>(this, US08AnimatedIconWidget::StaticClass());
    Icon->SetReducedMotion(bReduced);
    Icon->SetExternallyDriven(true);  // EvaluateAt applies every pose (and is what the perf sample measures)
    // VS-2 HB-23: InTexturePx <= 0 = by display size (the export for su x DPI x UI scale, traced 'ICON size')
    Icon->SetIcon(Id, InSizeSu, InTexturePx > 0 ? InTexturePx : S08IconMotion::ExportSizePx(InSizeSu, 1.0f));
    if (InTexturePx <= 0) Icon->SetDisplaySizeSu(InSizeSu);
    Icon->SetTeamTint(FLinearColor::FromSRGBColor(FColor(0xDA, 0xC5, 0x76)));  // team.p1.screen (reference demo)
    UOverlaySlot* IconSlot = Ov->AddChildToOverlay(Icon);
    IconSlot->SetHorizontalAlignment(HAlign_Center);
    IconSlot->SetVerticalAlignment(VAlign_Top);
    IconSlot->SetPadding(FMargin(0.0f, Pad, 0.0f, 0.0f));
    UTextBlock* Label = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
    if (!bLabels) Label->SetVisibility(ESlateVisibility::Collapsed);  // perf: the icons alone
    Label->SetText(FText::FromName(Id));
    FSlateFontInfo Font = Label->GetFont();
    Font.Size = 9;
    Label->SetFont(Font);
    Label->SetColorAndOpacity(FSlateColor(S08Srgb(0xEC, 0xE6, 0xDC)));
    Label->SetAutoWrapText(true);
    Label->SetJustification(ETextJustify::Center);
    UOverlaySlot* LabelSlot = Ov->AddChildToOverlay(Label);
    LabelSlot->SetHorizontalAlignment(HAlign_Fill);  // a width for AutoWrapText; the text itself is centred
    LabelSlot->SetVerticalAlignment(VAlign_Bottom);
    LabelSlot->SetPadding(FMargin(0.0f, 0.0f, 0.0f, 3.0f));
    UUniformGridSlot* GridSlot = Grid->AddChildToUniformGrid(CellBox, Index / Columns, Index % Columns);
    GridSlot->SetHorizontalAlignment(HAlign_Center);
    GridSlot->SetVerticalAlignment(VAlign_Center);
    FScript Script;
    float Total = 0.0f;
    S08IconMotion::DemoSchedule(*Def, bReduced, Script.Commands, Total);
    Script.PeriodMs = Total + PauseMs;
    Scripts.Add(MoveTemp(Script));
    Icons.Add(Icon);
    ++Index;
  }
  EvaluateAt(GetClockMs());
  return Icons.Num();
}

void US08IconGalleryWidget::EvaluateAt(float TMs) {
  const FS08IconMotionLibrary& Lib = FS08IconMotionLibrary::Get();
  for (int32 I = 0; I < Icons.Num(); ++I) {
    US08AnimatedIconWidget* Icon = Icons[I];
    const FScript& S = Scripts[I];
    const float Local = FMath::Fmod(TMs, S.PeriodMs);
    Icon->GetAnimator().Init(Lib.Find(Icon->GetIconId()), bReduced);
    for (const TPair<float, FName>& C : S.Commands) {
      if (C.Key > Local) break;
      Icon->PlayAnimAt(C.Value, C.Key);
    }
    Icon->SetClockOverrideMs(Local);
    Icon->ApplyPose(Local);
  }
}

void US08IconGalleryWidget::NativeTick(const FGeometry& MyGeometry, float InDeltaTime) {
  Super::NativeTick(MyGeometry, InDeltaTime);
  if (ClockOverrideMs < 0.0f) ClockMs += InDeltaTime * 1000.0f;
  const double T0 = FPlatformTime::Seconds();
  EvaluateAt(GetClockMs());
  EvalSamples.Add(static_cast<float>((FPlatformTime::Seconds() - T0) * 1000.0));
}

FVector2D US08IconGalleryWidget::CellSizeSu(float SizeSu) {
  const float Pad = FMath::RoundToFloat(0.25f * SizeSu);
  return FVector2D(FMath::Max(2.0f * SizeSu + 2.0f * Pad, 168.0f), SizeSu + 2.0f * Pad + 34.0f);
}

int32 US08IconGalleryWidget::ColumnsToFit(int32 Count, float SizeSu, float CanvasHeightSu) {
  const float RowSu = CellSizeSu(SizeSu).Y + 2.0f * SlotPaddingSu;
  const int32 Rows = FMath::Max(1, FMath::FloorToInt(CanvasHeightSu / RowSu));
  return FMath::Max(6, FMath::DivideAndRoundUp(FMath::Max(Count, 1), Rows));
}

FString US08IconGalleryWidget::IdList() const {
  TArray<FString> Ids;
  for (const US08AnimatedIconWidget* Icon : Icons) {
    if (Icon) Ids.Add(Icon->GetIconId().ToString());
  }
  return FString::Join(Ids, TEXT(","));
}

FString US08IconGalleryWidget::PerfSummary() const {
  if (EvalSamples.Num() == 0) return TEXT("evalMsAvg=0 evalMsP95=0 evalMsMax=0 frames=0");
  TArray<float> S = EvalSamples;
  S.Sort();
  float Sum = 0.0f;
  for (const float V : S) Sum += V;
  const float P95 = S[FMath::Clamp(FMath::CeilToInt(0.95f * S.Num()) - 1, 0, S.Num() - 1)];
  return FString::Printf(TEXT("evalMsAvg=%.4f evalMsP95=%.4f evalMsMax=%.4f frames=%d icons=%d"), Sum / S.Num(), P95,
                         S.Last(), S.Num(), Icons.Num());
}
