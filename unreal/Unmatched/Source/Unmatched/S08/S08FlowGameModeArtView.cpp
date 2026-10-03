// Art Tuner M1: the game-mode side of -ArtView=<map> (S08ArtView.h). BeginPlay arms the session and takes the -Bench path
// (no login, no room); RunRenderBench runs its fixture init unchanged, then parks in the free-view step (97) instead of
// the view walk. Every tick ArtViewTick reads the keys and the mouse; UpdateBoardCamera poses the camera from the orbit /
// pan state. Nothing here runs without the flag.
#include "S08FlowGameMode.h"

#include "S08ArtView.h"
#include "S08BoardActor.h"
#include "S08FighterActor.h"
#include "S08TraceLog.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Styling/CoreStyle.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/SOverlay.h"
#include "Widgets/Text/STextBlock.h"

namespace {
const FKey& S08ArtViewNumberKey(int32 Index) {
  static const FKey Keys[] = {EKeys::One, EKeys::Two, EKeys::Three, EKeys::Four, EKeys::Five};
  return Keys[FMath::Clamp(Index, 0, 4)];
}

TSharedRef<SBorder> S08ArtViewCard(const TSharedRef<SWidget>& Content) {
  return SNew(SBorder)
      .BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
      .BorderBackgroundColor(FLinearColor(0.02f, 0.025f, 0.035f, 0.78f))
      .Padding(FMargin(12.0f, 8.0f))[Content];
}
}  // namespace

void AS08FlowGameMode::ArtViewBegin() {
  ArtView = MakeShared<FS08ArtViewSession>();
  FS08ArtViewSession& V = *ArtView;
  V.Map = S08ArtView::MapFromCommandLine();
  FString File;
  if (!S08ArtView::FixtureFileFor(V.Map, File)) {
    FS08Trace::Write(FString::Printf(TEXT("ARTVIEW unknown map '%s' (sarpedon | marmoreal): using sarpedon"), *V.Map));
    V.Map = TEXT("sarpedon");
    S08ArtView::FixtureFileFor(V.Map, File);
  }
  V.Fixture = FPaths::Combine(FPaths::ProjectConfigDir(), TEXT("Bench"), File);
  FS08Trace::Write(FString::Printf(TEXT("ARTVIEW start map=%s fixture=%s (backend-less free view; the -Bench fixture init)"),
                                   *V.Map, *File));
}

void AS08FlowGameMode::ArtViewAfterBuild(const FString& HeroId) {
  FS08ArtViewSession& V = *ArtView;
  V.HeroId = HeroId;
  V.HintUntil = Elapsed + S08ArtViewSpec::HintSeconds;
  // P pauses the world (anims, Niagara, flicker, breath, material time): the game mode keeps reading the keys
  SetTickableWhenPaused(true);
  if (GEngine && GEngine->GameViewport) {
    const FSlateFontInfo Font = FCoreStyle::GetDefaultFontStyle("Regular", 13);
    const FSlateFontInfo Small = FCoreStyle::GetDefaultFontStyle("Regular", 11);
    TSharedRef<SVerticalBox> Column = SNew(SVerticalBox);
    Column->AddSlot().AutoHeight().Padding(FMargin(0.0f, 0.0f, 0.0f, 6.0f))[
        SAssignNew(V.HintBox, SBorder)
            .BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
            .BorderBackgroundColor(FLinearColor(0.02f, 0.025f, 0.035f, 0.7f))
            .Padding(FMargin(10.0f, 5.0f))[
                SAssignNew(V.HintText, STextBlock)
                    .Font(Small)
                    .ColorAndOpacity(FLinearColor(0.85f, 0.88f, 0.95f))
                    .Text(FText::FromString(S08ArtView::HintText(V.Map, ArtTunerEnabled())))]];
    Column->AddSlot().AutoHeight()[
        SAssignNew(V.HelpBox, SBorder)
            .BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
            .BorderBackgroundColor(FLinearColor(0.02f, 0.025f, 0.035f, 0.85f))
            .Padding(FMargin(14.0f, 10.0f))
            .Visibility(EVisibility::Collapsed)[
                SNew(SVerticalBox) +
                SVerticalBox::Slot().AutoHeight()[
                    SNew(STextBlock)
                        .Font(Font)
                        .ColorAndOpacity(FLinearColor(0.92f, 0.94f, 1.0f))
                        .Text(FText::FromString(S08ArtView::HelpText(ArtTunerEnabled())))] +
                SVerticalBox::Slot().AutoHeight().Padding(FMargin(0.0f, 8.0f, 0.0f, 0.0f))[
                    SAssignNew(V.StatusText, STextBlock).Font(Small).ColorAndOpacity(FLinearColor(0.7f, 0.76f, 0.86f))]]];
    V.Overlay = SNew(SOverlay) + SOverlay::Slot()
                                     .HAlign(HAlign_Left)
                                     .VAlign(VAlign_Top)
                                     .Padding(FMargin(16.0f, 14.0f))[Column];
    GEngine->GameViewport->AddViewportWidgetContent(V.Overlay.ToSharedRef(), 30);
  }
  ArtViewRefreshOverlay();
  FS08Trace::Write(FString::Printf(
      TEXT("ARTVIEW ready map=%s board=%dx%d fighters=%d hero=%s art=%d profile=%s fx=%s tuner=%d"), *V.Map, BoardModel.Width,
      BoardModel.Height, Fighters.Num(), HeroId.IsEmpty() ? TEXT("-") : *HeroId, BoardActor && BoardActor->IsArtActive() ? 1 : 0,
      BoardActor && !BoardActor->GetArtProfileId().IsEmpty() ? *BoardActor->GetArtProfileId() : TEXT("-"),
      BoardActor ? *BoardActor->GetFxOptions().Mode() : TEXT("-"), ArtTunerEnabled() ? 1 : 0));
}

void AS08FlowGameMode::ArtViewSetView(const FString& View) {
  FS08ArtViewSession& V = *ArtView;
  V.View = View;
  V.Cam.Reset();
  // a K2 view focuses the selected figure (Tab / click), else the fixture viewer's hero (the -Bench K2 subject)
  const FString Hero = !SelectedFighterId.IsEmpty() ? SelectedFighterId : V.HeroId;
  BenchSetupView(View, Hero);
  FS08Trace::Write(FString::Printf(TEXT("ARTVIEW view=%s hero=%s"), *View, Hero.IsEmpty() ? TEXT("-") : *Hero));
  ArtViewRefreshOverlay();
}

void AS08FlowGameMode::ArtViewRefreshOverlay() {
  if (!ArtView.IsValid()) return;
  FS08ArtViewSession& V = *ArtView;
  const FS08BoardFighter* Selected = FindFighter(SelectedFighterId);
  V.StatusLine = FString::Printf(TEXT("вид %s · герой %s · подсветка %s · %s · поворот %.0f° / наклон %.0f°"), *V.View,
                                 Selected ? *Selected->Label : TEXT("—"), V.bHeroLightOff ? TEXT("выкл") : TEXT("вкл"),
                                 V.bPaused ? TEXT("пауза") : TEXT("эффекты идут"), V.Cam.YawDeg + 90.0f,
                                 V.Cam.PitchDeg);
  if (V.StatusText.IsValid()) V.StatusText->SetText(FText::FromString(V.StatusLine));
  if (V.HelpBox.IsValid()) V.HelpBox->SetVisibility(V.bHelp ? EVisibility::HitTestInvisible : EVisibility::Collapsed);
  if (V.HintBox.IsValid()) {
    const bool bHint = !V.bHelp && Elapsed < V.HintUntil;
    V.HintBox->SetVisibility(bHint ? EVisibility::HitTestInvisible : EVisibility::Collapsed);
  }
}

void AS08FlowGameMode::ArtViewTick(float DeltaSeconds) {
  FS08ArtViewSession& V = *ArtView;
  APlayerController* PC = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr;
  if (!PC || !BoardActor || !CameraZoom.IsReady()) return;
  bool bChanged = false;
  const bool bShift = PC->IsInputKeyDown(EKeys::LeftShift) || PC->IsInputKeyDown(EKeys::RightShift);
  for (int32 I = 0; I < S08ArtView::Views().Num(); ++I) {
    if (PC->WasInputKeyJustPressed(S08ArtViewNumberKey(I))) ArtViewSetView(S08ArtView::Views()[I]);
  }
  if (PC->WasInputKeyJustPressed(EKeys::Tab)) {
    const int32 Next = S08ArtView::NextFighterIndex(Fighters, SelectedFighterId, bShift ? -1 : 1);
    if (Next != INDEX_NONE) {
      SelectFighter(Fighters[Next].Id);
      FS08Trace::Write(FString::Printf(TEXT("ARTVIEW select src=tab fighter=%s label=%s"), *Fighters[Next].Id,
                                       *Fighters[Next].Label));
    }
    bChanged = true;
  }
  if (PC->WasInputKeyJustPressed(EKeys::H)) {
    V.bHeroLightOff = !V.bHeroLightOff;
    BoardActor->SetHeroLightViewOff(V.bHeroLightOff);
    BoardActor->UpdateHeroLights();
    FS08Trace::Write(FString::Printf(TEXT("ARTVIEW hero-light view=%s lights=%d"), V.bHeroLightOff ? TEXT("off") : TEXT("on"),
                                     BoardActor->GetHeroLightCount()));
    bChanged = true;
  }
  if (PC->WasInputKeyJustPressed(EKeys::P)) {
    V.bPaused = !V.bPaused;
    PC->SetPause(V.bPaused);
    FS08Trace::Write(FString::Printf(TEXT("ARTVIEW pause=%d paused=%d"), V.bPaused ? 1 : 0, PC->IsPaused() ? 1 : 0));
    bChanged = true;
  }
  if (PC->WasInputKeyJustPressed(EKeys::F1)) {
    V.bHelp = !V.bHelp;
    V.HintUntil = 0.0f;
    bChanged = true;
  }
  if (PC->WasInputKeyJustPressed(EKeys::SpaceBar)) {
    // the zoom rig's overview comes from UpdateBoardCamera (ApplySpace); the orbit / pan go back here
    V.Cam.Reset();
    V.View = TEXT("K1");
    bChanged = true;
  }
  float MouseX = 0.0f, MouseY = 0.0f;
  const bool bMouse = PC->GetMousePosition(MouseX, MouseY);
  const FVector2D Mouse(MouseX, MouseY);
  if (bMouse && PC->WasInputKeyJustPressed(EKeys::LeftMouseButton)) {
    FHitResult Hit;
    if (PC->GetHitResultAtScreenPosition(Mouse, ECC_Visibility, false, Hit)) {
      if (const AS08FighterActor* Actor = Cast<AS08FighterActor>(Hit.GetActor())) {
        SelectFighter(Actor->GetFighterId());
        FS08Trace::Write(FString::Printf(TEXT("ARTVIEW select src=click fighter=%s"), *Actor->GetFighterId()));
        bChanged = true;
      }
    }
  }
  // right button: a drag orbits, a click deselects (the game's meaning)
  if (bMouse && PC->WasInputKeyJustPressed(EKeys::RightMouseButton)) {
    V.bRmbDown = true;
    V.bRmbDragging = false;
    V.RmbStart = Mouse;
    V.LastMouse = Mouse;
  }
  if (V.bRmbDown && bMouse && PC->IsInputKeyDown(EKeys::RightMouseButton)) {
    if (!V.bRmbDragging && FVector2D::Distance(Mouse, V.RmbStart) > S08ArtViewSpec::DragThresholdPx) V.bRmbDragging = true;
    if (V.bRmbDragging && Mouse != V.LastMouse) {
      V.Cam.Orbit(Mouse - V.LastMouse);
      bChanged = true;
    }
    V.LastMouse = Mouse;
  }
  if (V.bRmbDown && PC->WasInputKeyJustReleased(EKeys::RightMouseButton)) {
    if (!V.bRmbDragging) {
      SelectFighter(FString());
    } else {
      FS08Trace::Write(FString::Printf(TEXT("ARTVIEW orbit yaw=%.1f pitch=%.1f"), V.Cam.YawDeg, V.Cam.PitchDeg));
    }
    V.bRmbDown = false;
    V.bRmbDragging = false;
    bChanged = true;
  }
  // middle button: pan
  if (bMouse && PC->WasInputKeyJustPressed(EKeys::MiddleMouseButton)) {
    V.bMmbDown = true;
    V.LastMouse = Mouse;
  }
  if (V.bMmbDown && bMouse && PC->IsInputKeyDown(EKeys::MiddleMouseButton)) {
    FVector2D ViewportSize(1920.0, 1080.0);
    if (GEngine && GEngine->GameViewport) GEngine->GameViewport->GetViewportSize(ViewportSize);
    if (Mouse != V.LastMouse) {
      V.Cam.Pan(Mouse - V.LastMouse, CameraZoom.Current, static_cast<float>(ViewportSize.X));
      bChanged = true;
    }
    V.LastMouse = Mouse;
  }
  if (V.bMmbDown && PC->WasInputKeyJustReleased(EKeys::MiddleMouseButton)) {
    V.bMmbDown = false;
    FS08Trace::Write(FString::Printf(TEXT("ARTVIEW pan=(%.0f,%.0f)"), V.Cam.PanUU.X, V.Cam.PanUU.Y));
  }
  const bool bHintVisible = V.HintBox.IsValid() && V.HintBox->GetVisibility() != EVisibility::Collapsed;
  if (bChanged || (bHintVisible && Elapsed >= V.HintUntil)) ArtViewRefreshOverlay();
}
