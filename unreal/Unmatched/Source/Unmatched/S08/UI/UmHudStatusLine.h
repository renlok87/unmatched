// VS-2 HB-15 (docs/game-design/visual/06-tasks/hud.csv HB-15; 04-hud-spec.md §2.5, §2.11, §4.3, §5.2 step H5, §7.1;
// ВР-H09; move-selection/03-ux-spec.md §9; CX-08 mockup art/imagegen/hud-topstrip-v1-codex, accepted by delegation):
// STATUS - UUmHudStatusLine (/Game/S08/UI/Hud/WBP_UI_HUD_STATUS), the one line "what to do now" (SD-31) or what the
// opponent does (SD-15). It replaces the Slate line of the hand panel (AddTurnStatusLine) and the command panel
// headers «OPPONENT'S TURN», «AFTER COMBAT» (rollback -S08SlateHud=status).
//
//   data     ApplyModel(FS09TurnStatusInput) -> S09TurnStatus::Line -> the ms.* / why.* key and its arguments, RU / EN
//            from ST_Ms / ST_Why (UmText); the opponent's verb is ms.opp.phase.* of the same table, never the EN trace
//            text. An empty line (game over, nobody acts) hides the block; while a figure moves or a combat plays
//            the line keeps its text (the snapshot does not change it).
//   layout   the capsule (T_Skin_Capsule, panel.bg 0.92 + panel.edge) centred at the top of the STATUS slot; width =
//            the measured text + 2 x space.m + the pulse dot / key chips, at most the slot (880 / 720 / 600 su, the
//            width is recomputed only when the text changes). ВР-VS2-46 (CX-08, ВР-VS2-HB13-05): one line 48 su; a
//            longer text wraps to two lines at 1.25 x the size (78 su), «…» quotes never split; still longer - one
//            step down the type scale (24 -> 20 -> 16 su, type.heading / type.button / type.body sizes), then «…»
//            and the full text in the tooltip.
//   states   own (text.primary), opp (text.secondary + the 10 su pulse dot, 1 Hz; also while waiting on the
//            defender or the opponent's choice), defend, discard, choice, sync - the SHOT state of UI-HUD-STATUS
//            (ВР-VS2-48).
//   keys     ВР-H09: the key is a chip right of the text (04 §2.11, 20 x 20 su), never in the text; shown only when
//            the UI-ACC-017 mode says so (FUmStatusFrame::bKeyHints - the mode comes with HB-43, off until then).
//   motion   ВР-VS2-47: a new text fades in over 120 ms (0.15 -> 1; reduced 100 ms); the dot pulses 1 -> 0.35 -> 1
//            at 1 Hz (reduced: static). Nothing ticks outside those.
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../../S09/S09TurnStatus.h"
#include "../S08ArtHud.h"
#include "../S08ArtHudWidgets.h"
#include "UmHudStatusLine.generated.h"

class UBorder;
class UHorizontalBox;
class UImage;
class USizeBox;
class UTextBlock;

/** The SHOT states of UI-HUD-STATUS (04 §7.1). */
enum class EUmStatusState : uint8 { Own, Opp, Defend, Discard, Choice, Sync };

/** The frame the layout gives the line (event: a window / scale change, the UI-ACC-017 mode). */
struct UNMATCHED_API FUmStatusFrame {
  /** The STATUS rect width: 880 (L 1080p) / 720 (L 720p) / 600 (S) su. */
  float MaxWidthSu = 880.0f;
  /** DPI x UI scale (the x2 capsule skin from 1.5). */
  float PxPerSu = 1.0f;
  /** UI-ACC-017 «Вкл» / «Авто» in the first match (HB-43): the key chips. */
  bool bKeyHints = false;

  bool operator==(const FUmStatusFrame& O) const {
    return MaxWidthSu == O.MaxWidthSu && PxPerSu == O.PxPerSu && bKeyHints == O.bKeyHints;
  }
};

/** How a text fits the capsule (UmHudStatus::Fit). */
struct UNMATCHED_API FUmStatusFit {
  FString Display;       // the text drawn (with «…» when cut)
  float SizeSu = 24.0f;  // the em
  int32 Lines = 1;
  bool bEllipsis = false;
  float TextWidthSu = 0.0f;  // the widest drawn line
};

namespace UmHudStatus {
/** 04 §2.5: the capsule height of one line; ВР-VS2-HB13-05: line pitch = 1.25 x the size; two lines at most. */
inline constexpr float MinHeightSu = 48.0f;
inline constexpr float PitchFactor = 1.25f;
inline constexpr int32 MaxLines = 2;
/** ВР-VS2-HB13-06: the pulse dot 10 su, 8 su to the text; 04 §2.11: key chips 20 x 20 su (wider for «Enter»,
 *  «1–9»: the measured key + 2 x tag.padding.x), 4 su apart, 8 su from the text. */
inline constexpr float DotSu = 10.0f;
inline constexpr float DotGapSu = 8.0f;
inline constexpr float ChipSu = 20.0f;
inline constexpr float ChipGapSu = 4.0f;
inline constexpr int32 MaxChips = 3;
/** ВР-VS2-47: the fade-in of a new text (reduced: 100 ms); the pulse period. */
inline constexpr double FadeMs = 120.0;
inline constexpr double FadeReducedMs = 100.0;
inline constexpr double PulsePeriodMs = 1000.0;
inline constexpr float PulseLow = 0.35f;
inline constexpr float FadeFrom = 0.15f;

UNMATCHED_API const TCHAR* StateName(EUmStatusState State);
/** ВР-VS2-48: the SHOT state of a line. */
UNMATCHED_API EUmStatusState StateOf(const FS09TurnStatusInput& In, const FS09Reason& Line);
/** The player-facing text of the line (RU / EN from the tables; the opponent's verb localized). Empty for no line. */
UNMATCHED_API FText LineText(const FS09Reason& Line, const FS09TurnStatusInput& In);
/** ВР-H09: the hud.key.* chips of a line key (ms.status.action -> M, A, G; .defend -> N; ...); empty for none. */
UNMATCHED_API TArray<FString> KeyHints(FName LineKey);
/** «Без защиты» stays whole: the spaces inside «…» become no-break spaces. */
UNMATCHED_API FString BindQuotes(const FString& Text);
/** Width (su) of one line of Text at the em SizeSu. */
using FMeasureSu = TFunctionRef<float(const FString& Text, float SizeSu)>;
/** Greedy word wrap at WrapSu: the line count and the widest line (OutLines: the lines). */
UNMATCHED_API int32 WrapLines(const FString& Text, float WrapSu, float SizeSu, FMeasureSu Measure,
                              float* OutWidestSu = nullptr, TArray<FString>* OutLines = nullptr);
/** ВР-VS2-46: the size and line count for Text in TextRoomSu (Sizes from big to small); none fits two lines - the
 *  smallest size and the text cut with «…» to two lines. */
UNMATCHED_API FUmStatusFit Fit(const FString& Text, float TextRoomSu, const TArray<float>& Sizes, FMeasureSu Measure);
/** The capsule height of a fit: max(48, lines x pitch + 2 x inset), inset = (48 - pitch of the 24 su line) / 2. */
UNMATCHED_API float BodyHeightSu(const FUmStatusFit& Fit, float BaseSizeSu);
}  // namespace UmHudStatus

UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmHudStatusLine : public UUserWidget {
  GENERATED_BODY()

 public:
  static const TCHAR* const WidgetBlueprintPath;  // /Game/S08/UI/Hud/WBP_UI_HUD_STATUS

  virtual bool Initialize() override;
  /** Border "Frame" > SizeBox "BodyBox" > Border "Body" > HorizontalBox "Row" > PulseDot, StatusText,
   *  KeyChip > KeyRow > KeyBox0..2 > Key0..2 > KeyText0..2. */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  static UClass* WidgetClass();
  bool HasAllParts(FString* OutMissing = nullptr) const;
  bool UsesCodeDefaultTree() const { return bCodeDefaultTree; }

  /** The data input (П1): the same line, state and frame again = no work. */
  void ApplyModel(const FS09TurnStatusInput& In);
  /** The layout frame (event). */
  void SetFrame(const FUmStatusFrame& InFrame);

  bool IsShown() const { return bShown; }
  EUmStatusState GetState() const { return State; }
  FName GetLineKey() const { return LineKey; }
  const FUmStatusFit& GetFit() const { return FitNow; }
  FString GetFullText() const { return FullText; }
  FVector2D GetBodySizeSu() const { return BodySizeSu; }
  const TArray<FString>& GetKeysShown() const { return KeysShown; }
  FString SourceName() const;
  /** 'SHOT widget id=UI-HUD-STATUS state=<own|opp|...> ... key=<ms.*> lines=<n> size=<su> ellipsis=0|1 keys=<..>'
   *  for the capsule rect (viewport px); nothing while hidden. */
  void CollectShotLines(TArray<FString>& Out, const FS08ScreenRect& BodyRect) const;

  // ---- tests ----
  void SetClockForTest(TFunction<double()> InClock) { Clock = MoveTemp(InClock); }
  void SetReducedMotionForTest(bool bOn) { ReducedOverride = bOn ? 1 : 0; }
  void TickForTest() { Step(); }
  float GetTextOpacity() const;
  float GetDotOpacity() const;

  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget))
  TObjectPtr<UBorder> Body;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget))
  TObjectPtr<UTextBlock> StatusText;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget))
  TObjectPtr<UImage> PulseDot;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget))
  TObjectPtr<UBorder> KeyChip;
  /** The full-width frame in the STATUS slot that centres the capsule, and the capsule's size box. */
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget))
  TObjectPtr<UBorder> Frame;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget))
  TObjectPtr<USizeBox> BodyBox;

 protected:
  virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;

 private:
  void Render();
  void Step();
  bool IsReduced() const;
  double Now() const;
  /** Width (su) of one line of Text in the typeface of Token at the em SizeSu. */
  float MeasureSu(const FString& Text, float SizeSu, const TCHAR* Token = TEXT("type.heading")) const;

  UPROPERTY()
  TArray<TObjectPtr<UWidget>> KeyBoxes;
  UPROPERTY()
  TArray<TObjectPtr<UTextBlock>> KeyTexts;

  FUmStatusFrame StatusFrame;
  FS09TurnStatusInput Input;
  FS09Reason Line;
  FName LineKey;
  FString FullText;
  EUmStatusState State = EUmStatusState::Own;
  FUmStatusFit FitNow;
  FVector2D BodySizeSu = FVector2D::ZeroVector;
  TArray<FString> KeysShown;
  bool bHasModel = false;
  bool bShown = false;
  double FadeStart = -1.0;
  double PulseStart = 0.0;
  int32 ReducedOverride = -1;
  TFunction<double()> Clock;
  bool bCodeDefaultTree = false;
};
