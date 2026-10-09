// VC C3 (visual chat, 2026-10-09; vfx.csv FX-14 state «новый ход до угасания (старый гаснет за 100 мс)», ВР-VS6-10,
// ВР-VC-14): the opponent's last path that a newer move replaced fades over 100 ms instead of vanishing in the frame of
// the replace. FS09LastMoveTracker keeps one trail (its alpha is one value for every outline), and the new trail waits
// for its move animation (Waiting, not drawn) - so the plates draw this copy of the replaced trail meanwhile, with its
// own alpha. A new trail revealed during the fade ends it. -S08LastMoveLegacy: not used (the game mode skips Observe).
#pragma once

#include "CoreMinimal.h"
#include "../S08MoveHighlight.h"

struct UNMATCHED_API FS08OldPathFade {
  static constexpr double FadeMs = 100.0;  // reduced motion too (the card: an opacity change <= 100 ms)

  /** Every tick after the tracker: is its trail drawn, its seq, its plate input (when drawn) and its alpha. Returns a
   *  trace line ("MS-LAST old-fade start|end ...") when the fade starts or ends, otherwise empty. */
  FString Observe(bool bDrawn, int32 TrailSeq, const FS08MoveDraftInput::FLastMove* Input, float Alpha, double NowMs);
  bool IsFading() const { return StartMs >= 0.0; }
  /** The replaced trail's alpha: its alpha at the replace x (1 - t / 100 ms); 0 outside the fade. */
  float Alpha(double NowMs) const;
  /** What the plates draw while the tracker draws nothing: the fading trail, or the drawn one a replace (seen by the
   *  tracker, not observed yet this tick) is about to fade; nullptr otherwise. */
  const FS08MoveDraftInput::FLastMove* Shown(bool bDrawn, int32 TrailSeq) const;
  /** Changes when a fade starts or ends (the plates' redraw key). */
  uint32 GetRevision() const { return Revision; }
  void Reset() { *this = FS08OldPathFade(); }

private:
  FS08MoveDraftInput::FLastMove Last;  // the trail drawn at the last observed tick
  int32 LastSeq = -1;
  float LastAlpha = 0.0f;
  FS08MoveDraftInput::FLastMove Old;   // the replaced trail in its fade
  int32 OldSeq = -1;
  float OldFrom = 0.0f;
  double StartMs = -1.0;
  uint32 Revision = 0;
};
