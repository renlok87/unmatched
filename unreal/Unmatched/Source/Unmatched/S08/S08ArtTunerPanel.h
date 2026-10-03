// Art Tuner M3 (docs/art-pipeline/ART-TUNER-PLAN.md §1): the Slate panel of -ArtTuner. UI only: every row reads the
// session's model (S08ArtTuner.h) each frame and writes through the game mode's one value path (Actions.Set ->
// AS08FlowGameMode::ArtTunerSetValue), so the panel, the live-tune "tune" action and the saved file can never disagree.
// A slider drag sends at most S08ArtTunerSpec::ApplyHz values per second (and the last one when the mouse is released).
#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"

struct FS08ArtTunerSession;
struct FS08TunerParam;
struct FS08TunerGroup;
class FJsonValue;
class SBox;

/** What the panel can ask the game mode to do. */
struct FS08ArtTunerPanelActions {
  TFunction<bool(const FString& RowId, const TSharedPtr<FJsonValue>& Value, FString& OutError)> Set;
  TFunction<void(const FString& RowId)> ResetRow;
  TFunction<void(const FString& GroupId)> ResetGroup;  // empty = every group
  TFunction<void()> Save;
  TFunction<void()> Close;
  FString CloseKey = TEXT("F10");  // the key that toggles the panel (Shift+F10 in a live game)
};

class SS08ArtTunerPanel : public SCompoundWidget {
public:
  SLATE_BEGIN_ARGS(SS08ArtTunerPanel) {}
  SLATE_END_ARGS()

  void Construct(const FArguments& InArgs, const TSharedPtr<FS08ArtTunerSession>& InSession, FS08ArtTunerPanelActions InActions);
  virtual void Tick(const FGeometry& AllottedGeometry, const double InCurrentTime, const float InDeltaTime) override;
  /** The pending slider value goes out now (mouse released, panel closed). */
  void Flush();
  /** The rows of the session's current groups (a rebase / another board). */
  void Rebuild();

private:
  TSharedRef<SWidget> BuildGroup(const FS08TunerGroup& Group, bool bExpanded);
  TSharedRef<SWidget> BuildRow(const FS08TunerParam& Param);
  TSharedRef<SWidget> BuildNumberRow(const FS08TunerParam& Param);
  TSharedRef<SWidget> BuildBoolRow(const FS08TunerParam& Param);
  TSharedRef<SWidget> BuildSrgbRow(const FS08TunerParam& Param);
  TSharedRef<SWidget> BuildLinearRow(const FS08TunerParam& Param);
  TSharedRef<SWidget> RowFrame(const FS08TunerParam& Param, const TSharedRef<SWidget>& Editor);

  const FS08TunerParam* Find(const FString& RowId) const;
  /** The value pointer of a row (ev100: the exposure block's ev100). */
  FString ValuePointer(const FString& RowId) const;
  double NumberOf(const FString& RowId) const;
  bool BoolOf(const FString& RowId) const;
  FString HexOf(const FString& RowId) const;
  TArray<double> LinearOf(const FString& RowId) const;
  bool IsChanged(const FString& RowId) const;
  /** Queues a value (a slider drag: sent by Tick at <= ApplyHz). */
  void Queue(const FString& RowId, const TSharedPtr<FJsonValue>& Value);
  /** Sends a value now; an error goes into the status line. */
  void Send(const FString& RowId, const TSharedPtr<FJsonValue>& Value);
  FText StatusText() const;
  FSlateColor StatusColor() const;
  FString RowsSignature() const;

  TWeakPtr<FS08ArtTunerSession> Session;
  FS08ArtTunerPanelActions Actions;
  TSharedPtr<SBox> Body;
  FString Signature;
  TSet<FString> Expanded;
  FString PendingId;
  TSharedPtr<FJsonValue> PendingValue;
  double LastSent = 0.0;
  FString LocalError;
};
