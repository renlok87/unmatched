// Art Tuner M1: the pure part of -ArtView (S08ArtView.h).
#include "S08ArtView.h"

#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

bool FS08ArtViewCamera::IsDefault() const {
  return YawDeg == S08ArtViewSpec::DefaultYawDeg && PitchDeg == S08ArtViewSpec::DefaultPitchDeg && PanUU.IsZero();
}

void FS08ArtViewCamera::Reset() { *this = FS08ArtViewCamera(); }

void FS08ArtViewCamera::Orbit(const FVector2D& DeltaPx) {
  YawDeg = FRotator::NormalizeAxis(YawDeg + static_cast<float>(DeltaPx.X) * S08ArtViewSpec::YawDegPerPx);
  // dragging down tilts the view down onto the board (a higher camera)
  PitchDeg = FMath::Clamp(PitchDeg + static_cast<float>(DeltaPx.Y) * S08ArtViewSpec::PitchDegPerPx,
                          S08ArtViewSpec::MinPitchDeg, S08ArtViewSpec::MaxPitchDeg);
}

void FS08ArtViewCamera::Pan(const FVector2D& DeltaPx, float DistanceUU, float ViewportWidthPx) {
  if (ViewportWidthPx <= 0.0f || DistanceUU <= 0.0f) return;
  const float UuPerPx =
      2.0f * DistanceUU * FMath::Tan(FMath::DegreesToRadians(S08ArtViewSpec::HfovDeg * 0.5f)) / ViewportWidthPx;
  const float Yaw = FMath::DegreesToRadians(YawDeg);
  const FVector2D Forward(FMath::Cos(Yaw), FMath::Sin(Yaw));
  const FVector2D Right(-FMath::Sin(Yaw), FMath::Cos(Yaw));
  // "grab": the board follows the cursor, so the focus moves against the drag on the screen-right axis and along it on
  // the ground-forward axis (dragging down pulls the far side closer)
  PanUU += (-Right * DeltaPx.X + Forward * DeltaPx.Y) * UuPerPx;
  if (PanUU.Size() > S08ArtViewSpec::MaxPanUU) PanUU = PanUU.GetSafeNormal() * S08ArtViewSpec::MaxPanUU;
}

void FS08ArtViewCamera::Pose(const FVector& Focus, float DistanceUU, FVector& OutLocation, FRotator& OutRotation) const {
  const float P = FMath::DegreesToRadians(PitchDeg);
  const float Y = FMath::DegreesToRadians(YawDeg);
  const FVector Target = Focus + FVector(PanUU.X, PanUU.Y, 0.0);
  OutLocation = Target + DistanceUU * FVector(-FMath::Cos(P) * FMath::Cos(Y), -FMath::Cos(P) * FMath::Sin(Y), FMath::Sin(P));
  OutRotation = FRotator(-PitchDeg, YawDeg, 0.0f);
}

namespace S08ArtView {
bool Enabled(const TCHAR* CommandLine) { return !MapFromCommandLine(CommandLine).IsEmpty(); }

FString MapFromCommandLine(const TCHAR* CommandLine) {
  FString Map;
  FParse::Value(CommandLine ? CommandLine : FCommandLine::Get(), S08ArtViewSpec::MapParam, Map);
  return Map.TrimStartAndEnd().ToLower();
}

const TArray<FString>& Maps() {
  static const TArray<FString> Names = {TEXT("sarpedon"), TEXT("marmoreal")};
  return Names;
}

bool FixtureFileFor(const FString& Map, FString& OutFileName) {
  const FString Name = Map.ToLower();
  if (!Maps().Contains(Name)) return false;
  OutFileName = FString::Printf(TEXT("S08Bench%s%s.json"), *Name.Left(1).ToUpper(), *Name.Mid(1));
  return true;
}

const TArray<FString>& Views() {
  static const TArray<FString> Names = {TEXT("K1"), TEXT("K1x0.65"), TEXT("K2x1.6"), TEXT("K2x2.5"), TEXT("Fitx1.45")};
  return Names;
}

int32 NextFighterIndex(const TArray<FS08BoardFighter>& Fighters, const FString& Current, int32 Direction) {
  const int32 N = Fighters.Num();
  if (N == 0) return INDEX_NONE;
  const int32 Step = Direction < 0 ? -1 : 1;
  int32 Start = INDEX_NONE;
  for (int32 I = 0; I < N; ++I) {
    if (!Current.IsEmpty() && Fighters[I].Id == Current) Start = I;
  }
  // no current: the first living one (forward) or the last (backward)
  int32 I = Start == INDEX_NONE ? (Step > 0 ? -1 : N) : Start;
  for (int32 Tries = 0; Tries < N; ++Tries) {
    I = ((I + Step) % N + N) % N;
    if (Fighters[I].IsAlive()) return I;
  }
  return INDEX_NONE;
}

FString HelpText(bool bTuner) {
  TArray<FString> Lines = {
      TEXT("Просмотр доски без сервера"),
      TEXT(""),
      TEXT("Колесо — приблизить / отдалить"),
      TEXT("Пробел — общий вид (сбрасывает поворот и сдвиг)"),
      TEXT("Правая кнопка + движение — повернуть камеру"),
      TEXT("Правая кнопка (щелчок) — снять выбор героя"),
      TEXT("Средняя кнопка + движение — сдвинуть камеру"),
      TEXT("Левая кнопка по фигуре — выбрать героя"),
      TEXT("1–5 — виды K1 / K1x0.65 / K2x1.6 / K2x2.5 / Fitx1.45"),
      TEXT("Tab / Shift+Tab — следующий / предыдущий герой (подсветка «активный»)"),
      TEXT("H — подсветка героев вкл/выкл (только вид, не сохраняется)"),
      TEXT("P — пауза эффектов, ветра, мерцания и дыхания"),
  };
  if (bTuner) {
    Lines.Add(TEXT("F10 — панель Art Tuner"));
    Lines.Add(TEXT("Ctrl+S — сохранить изменения тюнера"));
  }
  Lines.Add(TEXT("F1 — скрыть эту справку"));
  Lines.Add(TEXT("Alt+Enter / F11 — полный экран"));
  return FString::Join(Lines, TEXT("\n"));
}

FString HintText(const FString& Map, bool bTuner) {
  return FString::Printf(TEXT("Art View · %s · F1 — справка%s"), *Map, bTuner ? TEXT(" · F10 — Art Tuner") : TEXT(""));
}
}  // namespace S08ArtView
