// VS-1 HB-09: the HUD scale of the client - see UmHudScale.h.
#include "UmHudScale.h"

#include "../S08TraceLog.h"
#include "../S08UserSettings.h"
#include "Containers/Ticker.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Engine/UserInterfaceSettings.h"
#include "Framework/Application/SlateApplication.h"
#include "Misc/CommandLine.h"
#include "Misc/DelayedAutoRegister.h"
#include "Misc/Parse.h"
#include "UnrealClient.h"

namespace UmHudScale {
namespace {
struct FKey {
  float Side;
  float Scale;
};
// ВР-62: the keys of Config/DefaultEngine.ini [/Script/Engine.UserInterfaceSettings] UIScaleCurve.
constexpr FKey ProjectKeys[] = {{720.0f, 0.75f}, {1080.0f, 1.0f}, {1440.0f, 1.333f}, {2160.0f, 2.0f}};
// UE 5.8 BaseEngine.ini [/Script/Engine.UserInterfaceSettings] UIScaleCurve (the curve before HB-09).
constexpr FKey EngineKeys[] = {{480.0f, 0.444f}, {720.0f, 0.666f}, {1080.0f, 1.0f}, {8640.0f, 8.0f}};

/** FRichCurve with linear keys and constant extrapolation, as the engine evaluates the UIScaleCurve. */
template <int32 N>
float Eval(const FKey (&Keys)[N], float Side) {
  if (Side <= Keys[0].Side) return Keys[0].Scale;
  for (int32 I = 1; I < N; ++I) {
    if (Side <= Keys[I].Side) {
      const float A = (Side - Keys[I - 1].Side) / (Keys[I].Side - Keys[I - 1].Side);
      return FMath::Lerp(Keys[I - 1].Scale, Keys[I].Scale, A);
    }
  }
  return Keys[N - 1].Scale;
}

FUmHudScaleState GState;
bool GTraceDirty = false;
bool GTraceWasOpen = false;
FTSTicker::FDelegateHandle GTicker;

/** The HUD-SCALE line reaches the trace as soon as the game mode opened it (AS08FlowGameMode::BeginPlay runs after the
 *  first apply), and again after a reopen; one bool per frame otherwise. */
bool TickTrace(float) {
  const bool bOpen = FS08Trace::IsOpen();
  if (bOpen && (GTraceDirty || !GTraceWasOpen) && GState.Window.X > 0) {
    FS08Trace::Write(TraceLine(GState));
    GTraceDirty = false;
  }
  GTraceWasOpen = bOpen;
  return true;
}

void OnViewportResized(FViewport* Viewport, uint32) {
  if (GEngine && GEngine->GameViewport && Viewport == GEngine->GameViewport->Viewport) Refresh();
}

void OnSettingsChanged() { Refresh(); }

/** -S08UiScale=<75-150>: a stand parameter for evidence runs (not a rollback); wins over the saved value. */
bool UiScaleOverride(int32& OutPercent) {
  int32 Value = 0;
  if (!FParse::Value(FCommandLine::Get(), TEXT("S08UiScale="), Value)) return false;
  OutPercent = US08UserSettings::ClampUiScalePercent(Value);
  return true;
}

FDelayedAutoRegisterHelper GRegister(EDelayedRegisterRunPhase::EndOfEngineInit, [] {
  // Game only: in the editor process ApplicationScale would rescale PIE and the editor's own game-layer previews.
  if (GIsEditor || IsRunningCommandlet()) return;
  FViewport::ViewportResizedEvent.AddStatic(&OnViewportResized);
  US08UserSettings::OnChanged.AddStatic(&OnSettingsChanged);
  GTicker = FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateStatic(&TickTrace), 0.0f);
  Refresh();
});
}  // namespace

float ProjectDpi(int32 ShortSide) { return Eval(ProjectKeys, static_cast<float>(ShortSide)); }

float EngineDpi(int32 ShortSide) { return Eval(EngineKeys, static_cast<float>(ShortSide)); }

float CurveDpi(FIntPoint Window) {
  const UUserInterfaceSettings* Ui = GetDefault<UUserInterfaceSettings>();
  if (!Ui || Window.X <= 0 || Window.Y <= 0) return 1.0f;
  // GetDPIScaleBasedOnSize = curve x ApplicationScale; ApplicationScale is what Refresh writes.
  return Ui->GetDPIScaleBasedOnSize(Window) / FMath::Max(Ui->ApplicationScale, 0.01f);
}

int32 EffectivePercent(int32 StoredPercent, int32 ShortSide) {
  const int32 Percent = US08UserSettings::ClampUiScalePercent(StoredPercent);
  return ShortSide > 0 && ShortSide < 1080 ? FMath::Max(Percent, 100) : Percent;
}

FUmHudScaleState Compute(FIntPoint Window, float Dpi, int32 StoredPercent, bool bLegacy) {
  FUmHudScaleState S;
  S.Window = Window;
  S.Dpi = Dpi;
  const int32 Short = FMath::Min(Window.X, Window.Y);
  S.UiPercentSet = US08UserSettings::ClampUiScalePercent(StoredPercent);
  S.UiPercent = EffectivePercent(StoredPercent, Short);
  S.bLegacy = bLegacy;
  float App = static_cast<float>(S.UiPercent) / 100.0f;
  if (bLegacy && Dpi > 0.0f && Short > 0) App *= EngineDpi(Short) / Dpi;  // the engine curve's size back
  S.AppScale = App;
  const float Px = S.PxPerSu();
  if (Px > 0.0f) {
    S.CanvasSu = FIntPoint(FMath::RoundToInt(static_cast<float>(Window.X) / Px),
                           FMath::RoundToInt(static_cast<float>(Window.Y) / Px));
  }
  S.bClassS = S.CanvasSu.X < ClassLMinWidthSu;
  return S;
}

FString TraceLine(const FUmHudScaleState& S) {
  return FString::Printf(TEXT("HUD-SCALE dpi=%.3f app=%.3f canvas=%dx%d window=%dx%d ui=%d uiSet=%d class=%s legacy=%d"),
                         S.Dpi, S.AppScale, S.CanvasSu.X, S.CanvasSu.Y, S.Window.X, S.Window.Y, S.UiPercent,
                         S.UiPercentSet, S.bClassS ? TEXT("S") : TEXT("L"), S.bLegacy ? 1 : 0);
}

bool LegacyRequested(const TCHAR* CommandLine) { return CommandLine && FParse::Param(CommandLine, LegacyFlagName); }

FString ArtLookField(const TCHAR* CommandLine) {
  return LegacyRequested(CommandLine) ? FString::Printf(TEXT("dpi=legacy(-%s)"), LegacyFlagName)
                                      : FString(TEXT("dpi=project"));
}

const FUmHudScaleState& Current() { return GState; }

FUmHudScaleChanged& OnUiScaleChanged() {
  static FUmHudScaleChanged Event;
  return Event;
}

void Refresh() {
  if (GIsEditor || IsRunningCommandlet() || !GEngine || !GEngine->GameViewport || !GEngine->GameViewport->Viewport) {
    return;
  }
  const FIntPoint Window = GEngine->GameViewport->Viewport->GetSizeXY();
  if (Window.X <= 0 || Window.Y <= 0) return;
  const US08UserSettings* Settings = US08UserSettings::Get();
  int32 Percent = Settings ? Settings->UiScalePercent : 100;
  UiScaleOverride(Percent);
  const FUmHudScaleState Next = Compute(Window, CurveDpi(Window), Percent, LegacyRequested(FCommandLine::Get()));
  if (Next == GState) return;
  if (UUserInterfaceSettings* Ui = GetMutableDefault<UUserInterfaceSettings>()) Ui->ApplicationScale = Next.AppScale;
  GState = Next;
  // The game layer reads the DPI scale every frame; the invalidation makes cached (invalidation-root) layouts follow.
  if (FSlateApplication::IsInitialized()) FSlateApplication::Get().InvalidateAllWidgets(false);
  UE_LOG(LogTemp, Display, TEXT("%s"), *TraceLine(Next));
  GTraceDirty = true;
  if (FS08Trace::IsOpen()) {
    FS08Trace::Write(TraceLine(Next));
    GTraceDirty = false;
    GTraceWasOpen = true;
  }
  OnUiScaleChanged().Broadcast(Next);
}

}  // namespace UmHudScale
