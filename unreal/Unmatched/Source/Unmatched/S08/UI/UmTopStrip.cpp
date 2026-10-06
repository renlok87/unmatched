// VS-2 HB-14...HB-16: the top strip runtime - see UmTopStrip.h.
#include "UmTopStrip.h"

#include "UmButton.h"
#include "UmGameHud.h"
#include "UmHudBanner.h"
#include "UmHudStatusLine.h"
#include "UmHudTop.h"
#include "Blueprint/UserWidget.h"
#include "Components/Border.h"

TArray<FString> FUmTopStrip::Build(UUmGameHud& Game, const S08ArtLook::FS08SlateHudBlocks& Blocks,
                                   const TSharedPtr<FS09HudPressArbiter>& Arbiter,
                                   TFunction<void(const FS09HudPressOutcome&, const TCHAR*)> OnPress) {
  TArray<FString> Lines;
  TArray<FString> Fields;
  if (!Blocks.IsSlate(FName(TEXT("top")))) {
    Top = CreateWidget<UUmHudTop>(&Game, UUmHudTop::WidgetClass());
    if (Top.IsValid() && Game.SetBlock(EUmGameSlot::Top, Top.Get())) {
      auto Wire = [&Arbiter, &OnPress](UUmButton* Button, const TCHAR* Id, const TCHAR* What) {
        if (!Button) return;
        TFunction<void(const FS09HudPressOutcome&, const TCHAR*)> Press = OnPress;
        Button->SetPress(FName(Id), Arbiter, FS09OnHudPressOutcome::CreateLambda([Press, What](const FS09HudPressOutcome& O) {
                           if (Press) Press(O, What);
                         }));
      };
      Wire(Top->MenuButton, TEXT("hud.top.menu"), TEXT("menu"));
      Wire(Top->LogButton, TEXT("hud.top.log"), TEXT("log"));
      Top->SetVisibility(ESlateVisibility::Collapsed);  // shown with the live match HUD (Tick)
      Fields.Add(FString::Printf(TEXT("top=umg topSource=%s conn=%s"), *Top->SourceName(),
                                 Top->Conn ? *Top->Conn->SourceName() : TEXT("none")));
    } else {
      Top = nullptr;
      Fields.Add(TEXT("top=failed"));
    }
  } else {
    Fields.Add(TEXT("top=slate(none)"));  // before HB-14 there was no TOP: the rollback has none
  }
  if (!Blocks.IsSlate(FName(TEXT("status")))) {
    Status = CreateWidget<UUmHudStatusLine>(&Game, UUmHudStatusLine::WidgetClass());
    if (Status.IsValid() && Game.SetBlock(EUmGameSlot::Status, Status.Get())) {
      Status->SetVisibility(ESlateVisibility::Collapsed);  // shown with the live match HUD (Tick)
      Fields.Add(FString::Printf(TEXT("status=umg statusSource=%s"), *Status->SourceName()));
    } else {
      Status = nullptr;
      Fields.Add(TEXT("status=failed"));
    }
  } else {
    Fields.Add(TEXT("status=slate"));
  }
  if (!Blocks.IsSlate(FName(TEXT("banner")))) {
    Banner = CreateWidget<UUmHudBanner>(&Game, UUmHudBanner::WidgetClass());
    if (Banner.IsValid() && Game.SetBlock(EUmGameSlot::Banner, Banner.Get())) {
      Fields.Add(FString::Printf(TEXT("banner=umg bannerSource=%s"), *Banner->SourceName()));
    } else {
      Banner = nullptr;
      Fields.Add(TEXT("banner=failed"));
    }
  } else {
    Fields.Add(TEXT("banner=slate"));
  }
  Lines.Add(TEXT("HUD-TOPSTRIP ") + FString::Join(Fields, TEXT(" ")));
  return Lines;
}

void FUmTopStrip::SetFrame(const FUmTopStripFrame& InFrame) {
  Frame = InFrame;
  if (UUmHudStatusLine* S = Status.Get()) {
    FUmStatusFrame F;
    F.MaxWidthSu = Frame.StatusMaxWidthSu;
    F.PxPerSu = Frame.PxPerSu;
    F.bKeyHints = Frame.bKeyHints;
    S->SetFrame(F);
  }
  if (UUmHudBanner* B = Banner.Get()) B->SetPxPerSu(Frame.PxPerSu);
}

FUmConnInput FUmTopStrip::ConnInput(const FUmTopStripTick& T) {
  if (T.bStreamReady) bWasReady = true;
  if (!T.bInFlight) {
    InFlightSince = -1.0;
  } else if (InFlightSince < 0.0) {
    InFlightSince = T.NowSeconds;
  }
  FUmConnInput In;
  In.bStreamReady = T.bStreamReady;
  In.bWasReady = bWasReady;
  In.bCommandSlow = T.bManeuverSlow || (InFlightSince >= 0.0 && T.NowSeconds - InFlightSince >= SlowSeconds);
  In.bRecovering = T.bRecovering;
  return In;
}

FString FUmTopStrip::Tick(const FUmTopStripTick& T) {
  const FUmConnInput In = ConnInput(T);
  const EUmConnState Now = UmConnection::Resolve(In);
  FString Line;
  if (!bConnKnown || Now != Conn) {
    Line = FString::Printf(TEXT("HUD-CONN state=%s ready=%d wasReady=%d slow=%d recovering=%d"),
                           UmConnection::StateName(Now), In.bStreamReady ? 1 : 0, In.bWasReady ? 1 : 0,
                           In.bCommandSlow ? 1 : 0, In.bRecovering ? 1 : 0);
  }
  Conn = Now;
  bConnKnown = true;
  if (bShown != T.bShow) {
    bShown = T.bShow;
    const ESlateVisibility Vis = bShown ? ESlateVisibility::SelfHitTestInvisible : ESlateVisibility::Collapsed;
    if (UUmHudTop* TopW = Top.Get()) TopW->SetVisibility(Vis);
    if (UUmHudStatusLine* S = Status.Get()) S->SetVisibility(Vis);
  }
  if (UUmHudTop* TopW = Top.Get()) {
    if (bShown) {
      FUmTopModel M;
      M.TurnCount = T.TurnCount;
      M.Conn = Conn;
      M.bClassS = Frame.bClassS;
      M.PxPerSu = Frame.PxPerSu;
      TopW->ApplyModel(M);
    }
  }
  if (UUmHudBanner* B = Banner.Get()) {
    if (T.Cue) {
      B->ApplyModel(*T.Cue, T.CueNowMs, T.bShow);
    }
  }
  return Line;
}

bool FUmTopStrip::ApplyStatus(const FS09TurnStatusInput& In) {
  UUmHudStatusLine* S = Status.Get();
  if (!S) return false;
  S->ApplyModel(In);
  return true;
}

void FUmTopStrip::CollectShotLines(TArray<FString>& Out, TFunctionRef<FS08ScreenRect(UWidget*)> RectOf) const {
  if (const UUmHudTop* TopW = Top.Get()) {
    if (UmGameHudSlots::ShownByProperty(TopW)) TopW->CollectShotLines(Out, RectOf(TopW->Plate.Get()), RectOf(TopW->Conn.Get()));
  }
  if (const UUmHudStatusLine* S = Status.Get()) {
    if (UmGameHudSlots::ShownByProperty(S)) S->CollectShotLines(Out, RectOf(S->Body.Get()));
  }
  if (const UUmHudBanner* B = Banner.Get()) B->CollectShotLines(Out, RectOf(B->Plate.Get()));
}
