// Evidence-shot queue (run I, I-03; defect D-1 of run H, docs/game-design/de-footage/task/runs/H-2026-10-05.md).
//
// FScreenshotRequest holds ONE request: a second AS08FlowGameMode::TakeEvidenceShot in the same engine frame replaced
// the first, so the first PNG was never written (Sarpedon s09-damage-number.png and s09-combat-resolve-window.png both
// asked in frame 530). The queue lets at most one request out per frame and only while the engine holds none of ours;
// the rest wait in FIFO order and go out in the following frames under their own names. Pure model (no world): the game
// mode passes the frame number and whether a capture is still in flight (FScreenshotRequest::IsScreenshotRequested()
// or a path the OnScreenshotCaptured delegate has not saved yet).
#pragma once

#include "CoreMinimal.h"

struct FS08ShotQueue {
  struct FEntry {
    FString Path;
    uint64 QueuedFrame = 0;
  };

  /** A new shot. true = issue the request now (it becomes this frame's request); false = queued behind the others
   *  (engine busy, a request already left this frame, or older shots still waiting - the order is kept). */
  bool Admit(const FString& Path, uint64 Frame, bool bCaptureBusy) {
    if (bCaptureBusy || Pending.Num() > 0 || IssuedThisFrame(Frame)) {
      Pending.Add({Path, Frame});
      return false;
    }
    MarkIssued(Frame);
    return true;
  }

  /** Once per frame, before gameplay asks for new shots: the oldest waiting shot when this frame may issue it. */
  bool PopReady(uint64 Frame, bool bCaptureBusy, FEntry& Out) {
    if (Pending.Num() == 0 || bCaptureBusy || IssuedThisFrame(Frame)) return false;
    Out = MoveTemp(Pending[0]);
    Pending.RemoveAt(0);
    MarkIssued(Frame);
    return true;
  }

  int32 Num() const { return Pending.Num(); }
  bool IssuedThisFrame(uint64 Frame) const { return bIssued && IssuedFrame == Frame; }

 private:
  void MarkIssued(uint64 Frame) {
    bIssued = true;
    IssuedFrame = Frame;
  }

  TArray<FEntry> Pending;
  bool bIssued = false;
  uint64 IssuedFrame = 0;
};
