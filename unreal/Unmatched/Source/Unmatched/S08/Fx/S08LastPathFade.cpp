// VC C3: the 100 ms fade of a replaced last path (FX-14) - see S08LastPathFade.h.
#include "S08LastPathFade.h"

FString FS08OldPathFade::Observe(bool bDrawn, int32 TrailSeq, const FS08MoveDraftInput::FLastMove* Input, float InAlpha,
                                 double NowMs) {
  FString Line;
  if (IsFading() && (bDrawn || NowMs - StartMs >= FadeMs)) {
    Line = FString::Printf(TEXT("MS-LAST old-fade end seq=%d ms=%d reason=%s"), OldSeq, FMath::RoundToInt(NowMs - StartMs),
                           bDrawn ? TEXT("shown") : TEXT("done"));
    StartMs = -1.0;
    Old = FS08MoveDraftInput::FLastMove();
    OldSeq = -1;
    ++Revision;
  }
  if (bDrawn) {
    if (Input) Last = *Input;
    LastSeq = TrailSeq;
    LastAlpha = InAlpha;
    return Line;
  }
  if (LastSeq >= 0 && TrailSeq != LastSeq && Last.IsSet() && LastAlpha > 0.0f) {
    Old = Last;
    OldSeq = LastSeq;
    OldFrom = LastAlpha;
    StartMs = NowMs;
    ++Revision;
    Line = FString::Printf(TEXT("MS-LAST old-fade start seq=%d by=%d from=%.2f ms=%d"), OldSeq, TrailSeq, OldFrom,
                           FMath::RoundToInt(FadeMs));
  }
  Last = FS08MoveDraftInput::FLastMove();
  LastSeq = -1;
  LastAlpha = 0.0f;
  return Line;
}

float FS08OldPathFade::Alpha(double NowMs) const {
  if (!IsFading()) return 0.0f;
  return OldFrom * FMath::Clamp(1.0f - static_cast<float>((NowMs - StartMs) / FadeMs), 0.0f, 1.0f);
}

const FS08MoveDraftInput::FLastMove* FS08OldPathFade::Shown(bool bDrawn, int32 TrailSeq) const {
  if (bDrawn) return nullptr;
  if (IsFading()) return &Old;
  if (LastSeq >= 0 && TrailSeq != LastSeq && Last.IsSet()) return &Last;
  return nullptr;
}
