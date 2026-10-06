// VS-3 CP-15...CP-20 (docs/game-design/visual/06-tasks/cards-portraits.csv CP-15, CP-16, CP-17, CP-18, CP-19, CP-20;
// 04-hud-spec.md §2.6-§2.9, §1.7, §4.1-§4.3; 02-visual-design.md §6.1-§6.4; ВР-48...ВР-51, ВР-CP04...ВР-CP13,
// ВР-VS2-CP-01...09): one card = one widget in every display - UUmCardWidget (/Game/S08/UI/Common/WBP_UmCard).
//
//   shows     hand 150x208, hover 225x312, combat 230x319, slot 190x264, inspector (RU 460x640, EN 408x566), deckgrid
//             150x208, classS-hand 120x166, classS-combat 150x208, mini 48x67 (OPP-HAND) and 32x45 (DECKS chips) - su of
//             02 §6.2 / ВР-70 / ВР-CP06 (the integer sizes are normative, ВР-VS2-CP-04).
//   layers    bottom to top (ВР-VS2-CP-07): the card.navy underlay inside the keyline (inset 1 su, radius r - 1, drawn in
//             code); the scan "contain" in the constant window (show - 2 x 4 su band, mini 2 su; never cropped, the gap
//             up to 3 su is the underlay, ВР-VS2-CP-02) through M_UmCardFace (CP-14: Face, UVRect, Desaturation,
//             Opacity); the frame PNG of the state (DA_UmHudTheme card.frame.*, CP-13 package, CP-14 import); the
//             focus ring outside the keyline (2 su gap, 2 su ring, 02 §4.3); the new dot, the boost chip and the drop
//             icon. No text or value is ever drawn over a scan (ВР-49).
//   face      ru | en (the scan of the build language, ВР-51; the key heroSlug:cardSlug of the deck owner's hero, INT-014),
//             back (the original back of the owner's hero, ВР-50: sides cropped 5 px of 768, then contain - ВР-VS2-CP-03),
//             fallback (no key / no texture: the 02 §6.1 plate - the name of the data type.heading, the type disc,
//             value and BOOST, the banner; RU missing -> the EN name with the "EN" tag, INT-018 p. 3; a Warning naming
//             the key, INT-018 p. 4). A hidden card has no face in the model at all (QA-005): ApplyModel with bFaceDown
//             keeps only the instance id, Flip(true, .., Face) hands the face in at the reveal and the texture is set in
//             the frame the card stands on its edge (CP-20).
//   cap       ВР-CP04: the scan drawn is at most 1.6 x its source pixels - the card shrinks to
//             min(show, the size whose scan is 1.6 x src at DPI x UI scale), the rest is padding around the centre.
//   load      the texture loads asynchronously (FStreamableManager); until it is there the frame and loader-spinner 32 su.
//   states    CP-16 SetPlayable (Desaturation 0 -> 0.6, Opacity 1 -> 0.7 over hover.ms 150; the frame does not change;
//             the cursor "unavailable") and SetNew (the dot card.glyph 8 su + keyline, centre 10 su from the right and the
//             top edge; appear 180 / leave 120 ms); CP-17 SetHover (scale 1.5 over 150 ms ease-out-quad, pivot bottom
//             centre, card.frame.hover; never above the 1.6 cap), SetSelected (card.frame.selected 3 su), SetFocus (the
//             ring, appear 100 ms), SetLowered (the hand is down: no hover preview, SD-26); CP-18 SetFaceDown (flip into
//             the back in 150 ms) and SetBoostChip (state-boost 24 su with "+N" - runtime text, И-7; the opponent's chip
//             has no number, ВР-CP11); CP-19 SetDiscardCandidate (card.frame.warning) and SetMarkedForDiscard (+16 su down
//             in 150 ms, card-drop 24 su); CP-20 Flip (scaleX 1 -> 0 in 80 ms ease-in-quad, the face swaps, 0 -> 1 in
//             80 ms ease-out-quad - x the combat speed; the defense card starts DefenseFlipDelayMs later, the owner calls);
//             CUE-006 PlayFlash (fx.flash edge fading to idle in 500 ms). Reduced motion: opacity only, <= 100 ms; the
//             hover scale without a tween; the flip a face cross-fade of 100 ms.
//   frame     priority flash > warning > selected > hover > idle (mini displays: mini-idle only, ВР-VS2-CP-06).
//   input     the press on the release through FS09HudPressArbiter (UI-INP-011): an unplayable card answers Refused with
//             its why.*; the right button calls the owner's inspector; the pointer enter / leave go to the owner (it lifts
//             the card and orders it over the neighbours, HAND). Cursor: Hand, SlashedCircle when unplayable (HB-12).
//   pool      the owner keeps the widgets (04 §4.1): ApplyModel never rebuilds the tree, only brushes and parameters.
//   rollback  -S08CardArtLegacy (ВР-CP08): the fallback face always, the card.navy plate with resource-card 24 su instead
//             of the back (ARTLOOK cards=legacy(..)); blocks -S08SlateHud=hand,combat,slot,inspect keep the Slate path.
//   trace     'CARD-ART key=<heroSlug:cardSlug|back:<hero>> lang=ru|en|back|fallback tex=<path|fallback|legacy|loading>
//             show=<show> su=WxH px=WxH scale=<x> capped=0|1 state=<a+b..> chip=0|1' (ВР-CP10; no value, no name);
//             tools/s08/hud_contract/hud_contract.py check-trace fails at scale > 1.6 and at lang=fallback for a key the
//             registry has (tex=legacy excepted).
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../../S09/S09HudModel.h"
#include "../../S09/S09HudPress.h"
#include "../S08ArtHudWidgets.h"
#include "UObject/SoftObjectPath.h"
#include "UmCardWidget.generated.h"

struct FStreamableHandle;
struct FUmCardMediaEntry;
class UHorizontalBox;
class UImage;
class UMaterialInstanceDynamic;
class UOverlay;
class USizeBox;
class UTextBlock;
class UTexture2D;
class UVerticalBox;
class US08AnimatedIconWidget;

enum class EUmCardShow : uint8 {
  Hand,          // 150 x 208
  Hover,         // 225 x 312
  Combat,        // 230 x 319
  Slot,          // 190 x 264
  Inspector,     // RU 460 x 640, EN 408 x 566
  DeckGrid,      // 150 x 208
  ClassSHand,    // 120 x 166
  ClassSCombat,  // 150 x 208
  MiniOpp,       // 48 x 67
  MiniChip,      // 32 x 45
};

/** What the face shows now. */
enum class EUmCardFace : uint8 { Ru, En, Back, Fallback };

/** The owner's half of the model (the card data is FS09CardView). */
struct UNMATCHED_API FUmCardState {
  EUmCardShow Show = EUmCardShow::Hand;
  /** The deck owner's hero slug ("king-arthur", "medusa"): the scan key and the back (Merlin's cards: King Arthur). */
  FString HeroSlug;
  /** The back up: no face in the widget at all (QA-005). */
  bool bFaceDown = false;
  /** "" = the build culture (UmCardMedia::PreferredLang), "ru" / "en" = forced (the inspector's language toggle). */
  FString Lang;
  /** DPI x UI scale; 0 = UmHudScale::Current(). */
  float PxPerSu = 0.0f;
  bool operator==(const FUmCardState& O) const {
    return Show == O.Show && HeroSlug == O.HeroSlug && bFaceDown == O.bFaceDown && Lang == O.Lang && PxPerSu == O.PxPerSu;
  }
  bool operator!=(const FUmCardState& O) const { return !(*this == O); }
};

/** The fit of a scan into a display (all su, the scale in source pixels per screen pixel). */
struct UNMATCHED_API FUmCardFit {
  FVector2D ShowSu = FVector2D::ZeroVector;    // the display box
  FVector2D CardSu = FVector2D::ZeroVector;    // the card drawn (ВР-CP04: <= ShowSu)
  FVector2D WindowSu = FVector2D::ZeroVector;  // CardSu - 2 x band
  FVector2D ScanSu = FVector2D::ZeroVector;    // the scan, contain in the window
  float Scale = 0.0f;                          // screen px of the scan / source px
  bool bCapped = false;
};

namespace UmCardWidget {
inline const TCHAR* const MaterialPath = TEXT("/Game/S08/UI/Common/M_UmCardFace.M_UmCardFace");
// M_UmCardFace parameters (tools/art/cards/ue_card_face_material.py builds them; its --check reads these)
inline const TCHAR* const ParamFace = TEXT("Face");
inline const TCHAR* const ParamUvRect = TEXT("UVRect");
inline const TCHAR* const ParamDesaturation = TEXT("Desaturation");
inline const TCHAR* const ParamOpacity = TEXT("Opacity");

inline constexpr float CapScale = 1.6f;            // ВР-CP04 / ВР-48
inline constexpr float BandSu = 4.0f;              // keyline 1 + edge band (ВР-VS2-CP-08)
inline constexpr float MiniBandSu = 2.0f;
inline constexpr float UnderlayInsetSu = 1.0f;     // inside the keyline (ВР-VS2-CP-07)
inline constexpr float FocusOutsetSu = 4.0f;       // gap 2 + ring 2 (02 §4.3)
inline constexpr int32 BackCropPx = 5;             // ВР-VS2-CP-03: 5 px a side of the 768 px back (1.30 %)
inline constexpr float UnplayableDesaturation = 0.6f;
inline constexpr float UnplayableOpacity = 0.7f;
inline constexpr float HoverScale = 1.5f;          // 150 x 208 -> 225 x 312
inline constexpr float DiscardShiftSu = 16.0f;
inline constexpr float NewDotSu = 10.0f;           // 8 su card.glyph + 1 su keyline a side
inline constexpr float NewDotCentreInsetSu = 10.0f;
inline constexpr float ChipSu = 24.0f;             // state-boost / card-drop (ВР-42 minimum)
inline constexpr float ChipTopSu = -16.0f;         // the chip's top above the card: 16 su out, 8 su on the frame
inline constexpr float SpinnerSu = 32.0f;
inline constexpr float BoostFlipMs = 150.0f;       // CP-18
inline constexpr float RevealFlipMs = 160.0f;      // CP-20 (ВР-CP13)
inline constexpr float FlashMs = 500.0f;           // CUE-006
inline constexpr float FocusAppearMs = 100.0f;
inline constexpr float ReducedMs = 100.0f;
/** SetBoostChip: no chip / the chip without its number (the opponent's boost before the reveal, ВР-CP11). */
inline constexpr int32 NoBoostChip = INDEX_NONE;
inline constexpr int32 HiddenBoost = -2;

UNMATCHED_API const TCHAR* ShowName(EUmCardShow Show);
UNMATCHED_API const TCHAR* FaceName(EUmCardFace Face);
UNMATCHED_API bool IsMini(EUmCardShow Show);
UNMATCHED_API float BandOf(EUmCardShow Show);
/** The display size in su (the inspector by the scan language: RU 460 x 640, EN 408 x 566). */
UNMATCHED_API FVector2D ShowSize(EUmCardShow Show, bool bEnglishScan = false);
/** The card / deck owner slug rule (INT-014): lower case, ' ' -> '-', anything but a-z 0-9 '-' dropped. */
UNMATCHED_API FString Slug(const FString& Name);
/** "heroSlug:cardSlug" of a card of the deck of HeroSlug ("" when either is empty). */
UNMATCHED_API FString CardKey(const FString& HeroSlug, const FString& CardName);
/** The source pixels a texture of the registry draws: cards the whole source, backs without the side crop. */
UNMATCHED_API FIntPoint DrawnSrcPx(const FUmCardMediaEntry& Entry);
/** The UV rectangle (minU, minV, maxU, maxV) of what DrawnSrcPx covers in the padded texture. */
UNMATCHED_API FVector4 UvRect(const FUmCardMediaEntry& Entry);
/** Contain of SrcPx into the window of ShowSu (band BandSu) at PxPerSu, the card shrunk by the ВР-CP04 cap. */
UNMATCHED_API FUmCardFit Fit(const FVector2D& ShowSu, float Band, const FIntPoint& SrcPx, float PxPerSu, float Cap = CapScale);
/** The hover scale for a base fit: 1.5, or less when the hovered scan would pass the cap (CP-17). */
UNMATCHED_API float HoverScaleFor(const FUmCardFit& Base, float Cap = CapScale);
/** Theme skin key of the base frame: warning > selected > hover > idle (mini: card.frame.mini only). The CUE-006 flash
 *  is its own layer (card.frame.flash) over this frame. */
UNMATCHED_API FName FrameKey(bool bMini, bool bWarning, bool bSelected, bool bHover);
// ---- motion curves (02 §6.3, icon-motion.json appear / leave; CP-16 keyframes) ----
UNMATCHED_API float AppearScale(float TMs);
UNMATCHED_API float AppearOpacity(float TMs);
UNMATCHED_API float LeaveScale(float TMs);
UNMATCHED_API float LeaveOpacity(float TMs);
/** CP-20: scaleX of a flip at TMs of TotalMs - ease-in-quad to 0 at the half, ease-out-quad back to 1. */
UNMATCHED_API float FlipScaleX(float TMs, float TotalMs);
/** When the defense card starts its flip after the attack card's (FS09CombatTiming::DefenseFlipDelayMs x speed). */
UNMATCHED_API float DefenseFlipDelayMs(float SpeedMul);
/** The CARD-ART line (ВР-CP10). */
UNMATCHED_API FString TraceLine(const FString& Key, EUmCardFace Face, const FString& Tex, EUmCardShow Show,
                                const FUmCardFit& Fit, float PxPerSu, const FString& State, bool bChip);
}  // namespace UmCardWidget

UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmCardWidget : public UUserWidget {
  GENERATED_BODY()

 public:
  static const TCHAR* const WidgetBlueprintPath;  // /Game/S08/UI/Common/WBP_UmCard
  static UClass* WidgetClass();

  virtual bool Initialize() override;
  /** SizeBox "Box" > Overlay "Stack" > SizeBox "Card" > Overlay "Layers" > FocusRing, Underlay, Face, Fallback (type
   *  discs, name, lang tag, values, banner), PlateIcon, Spinner, Frame, FlashLayer, NewDot, DropIcon, BoostChip
   *  (BoostIcon, BoostText). */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  bool HasAllParts(FString* OutMissing = nullptr) const;
  bool UsesCodeDefaultTree() const { return bCodeDefaultTree; }

  /** The one data input (П1): the card and the owner's state. Same input = no work. With State.bFaceDown the face of
   *  Card is not kept (only its instance id). */
  void ApplyModel(const FS09CardView& Card, const FUmCardState& State);
  const FS09CardView& GetCard() const { return CardModel; }
  const FUmCardState& GetState() const { return StateModel; }

  // ---- CP-16 ----
  void SetPlayable(bool bPlayable, const FS09Reason& Reason = FS09Reason());
  void SetNew(bool bNew);
  bool IsPlayable() const { return bPlayable; }
  bool IsNew() const { return bNew; }
  const FS09Reason& GetReason() const { return Reason; }
  /** The why.* of an unplayable card (ST_Why) - the HAND owner shows it on hover. */
  FText GetWhyText() const;
  // ---- CP-17 ----
  void SetHover(bool bOn);
  void SetSelected(bool bOn);
  void SetFocus(bool bOn);
  /** SD-26: the hand is down - the hover shows no preview. */
  void SetLowered(bool bOn);
  // ---- CP-18 ----
  /** Turns the card into its back (bDown) or back to its face, AnimMs (150) of flip; reduced motion - a 100 ms
   *  cross-fade. The face stays in the widget of the OWN card (the owner's model has it); the opponent's boost comes
   *  in face down through ApplyModel. */
  void SetFaceDown(bool bDown, float AnimMs = UmCardWidget::BoostFlipMs);
  /** The boost chip: N >= 0 "+N", HiddenBoost = the chip without a number, NoBoostChip = none. Appears after a running
   *  flip (CP-18: 150 - 330 ms). */
  void SetBoostChip(int32 N);
  // ---- CP-19 ----
  void SetDiscardCandidate(bool bOn);
  void SetMarkedForDiscard(bool bOn);
  // ---- CP-20 ----
  /** The flip on the spot (scaleX, pivot centre): to the face (Face = the revealed card, set at the edge frame) or to
   *  the back. SpeedMul is the combat speed (0 = instant, 0.5 fast, 1, 1.5 slow). */
  void Flip(bool bToFace, float SpeedMul = 1.0f, const FS09CardView* Face = nullptr);
  /** CUE-006: the fx.flash edge over idle, fading in 500 ms. */
  void PlayFlash();

  // ---- trace ----
  FString ArtLine() const;
  void CollectShotLines(TArray<FString>& Out) const;
  FString StateText() const;

  // ---- input (the owner) ----
  void SetPress(FName InId, const TSharedPtr<FS09HudPressArbiter>& InArbiter, const FS09OnHudPressOutcome& InOnOutcome);
  void SetOnHoverChanged(TFunction<void(bool)> In) { OnHoverChanged = MoveTemp(In); }
  void SetOnInspect(TFunction<void()> In) { OnInspect = MoveTemp(In); }
  FName GetPressId() const { return PressId; }

  // ---- what is drawn now (tests, gallery) ----
  EUmCardFace GetFace() const { return FaceKind; }
  const FString& GetFaceKey() const { return FaceKey; }
  const FString& GetTexturePath() const { return TexPath; }
  bool IsLoading() const { return bLoading; }
  bool HasFaceTexture() const { return FaceTexture != nullptr; }
  UMaterialInstanceDynamic* GetFaceMid() const { return FaceMid; }
  const FUmCardFit& GetFit() const { return FitNow; }
  float GetPxPerSu() const;
  FName GetFrameKey() const { return FrameKeyNow; }
  bool IsFrameTexture() const { return bFrameTexture; }
  float GetDesaturation() const { return DesatNow; }
  float GetFaceOpacity() const { return FaceOpacityNow; }
  float GetScaleX() const { return ScaleXNow; }
  float GetScale() const { return ScaleNow; }
  float GetShiftSu() const { return ShiftNow; }
  float GetNewDotOpacity() const;
  float GetChipOpacity() const;
  float GetDropOpacity() const;
  float GetFocusOpacity() const;
  bool IsHover() const { return bHover; }
  bool IsSelected() const { return bSelected; }
  bool IsFocused() const { return bFocus; }
  bool IsFaceDown() const { return bFaceDownNow; }
  bool IsDiscardCandidate() const { return bCandidate; }
  bool IsMarked() const { return bMarked; }
  bool IsFlipping() const { return FlipStartMs >= 0.0; }
  int32 GetBoost() const { return Boost; }
  FString GetChipText() const;
  bool IsLegacy() const;
  /** True while a tween runs (the tick steps it). */
  bool IsAnimating() const;

  // ---- tests and the review sheet ----
  /** >= 0 freezes the widget clock at Ms (the review sheet, tests); < 0 = FPlatformTime. */
  void SetClockOverrideMs(double Ms) { ClockOverrideMs = Ms; }
  void SetReducedForTest(int32 InReduced) { ReducedOverride = InReduced; }
  /** -1 = the -S08CardArtLegacy command line, 0 / 1 forced. */
  void SetLegacyForTest(int32 InLegacy) { LegacyOverride = InLegacy; }
  /** Load the face synchronously (tests, the review sheet: no spinner frame). */
  void SetSyncLoad(bool bOn) { bSyncLoad = bOn; }
  /** Review sheet (CP-14 frame page): draw this card.frame.* key whatever the state (NAME_None = the state's). */
  void SetFrameOverrideForSheet(FName Key) {
    FrameOverride = Key;
    ApplyFrame();
  }
  /** Steps every tween at the current clock (the tick does it per frame while one runs). */
  void Step();

  virtual FReply NativeOnMouseButtonDown(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
  virtual FReply NativeOnMouseButtonDoubleClick(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
  virtual FReply NativeOnMouseButtonUp(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
  virtual void NativeOnMouseEnter(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
  virtual void NativeOnMouseLeave(const FPointerEvent& InMouseEvent) override;
  virtual bool NativeSupportsKeyboardFocus() const override { return false; }

  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<USizeBox> Box;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<USizeBox> Card;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UOverlay> Layers;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UImage> Underlay;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UImage> Face;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UImage> Frame;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UImage> FlashLayer;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UImage> FocusRing;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UImage> NewDot;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UOverlay> BoostChip;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<US08AnimatedIconWidget> BoostIcon;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UTextBlock> BoostText;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<US08AnimatedIconWidget> DropIcon;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<US08AnimatedIconWidget> PlateIcon;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<US08AnimatedIconWidget> Spinner;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UVerticalBox> Fallback;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UHorizontalBox> FallbackTypes;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<US08AnimatedIconWidget> TypeIcon0;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<US08AnimatedIconWidget> TypeIcon1;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UTextBlock> FallbackName;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UTextBlock> FallbackLang;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UTextBlock> FallbackValues;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UTextBlock> FallbackBanner;

 protected:
  virtual void NativeConstruct() override;
  virtual void NativeDestruct() override;
  virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;

 private:
  struct FTween {
    double StartMs = -1.0;
    float DurMs = 0.0f;
    float From = 0.0f;
    float To = 0.0f;
    bool IsRunning(double Now) const { return StartMs >= 0.0 && Now < StartMs + DurMs; }
  };
  /** Resolves the face of the model (key, texture path, kind) and loads it. */
  void ResolveFace();
  /** Loads the texture of Entry (FindObject, sync for tests / the sheet, else async with the spinner). */
  void LoadFace(const FUmCardMediaEntry& Entry);
  void SetFaceTexture(UTexture2D* Tex);
  void OnFaceLoaded();
  /** The face falls back to the 02 §6.1 plate (a back to the card.navy plate) - with one Warning unless legacy. */
  void FallBack(const TCHAR* Why);
  /** The edge frame of a flip: the face (or the back) is swapped in. */
  void DoSwap();
  void StartFlip(bool bToFace, float DurMs);
  void ApplyLayout();
  void ApplyFrame();
  void ApplyFallbackContent();
  void ApplyCursor();
  bool IsReduced() const;
  double NowMs() const;
  float TweenValue(const FTween& T, double Now, bool bEaseOutQuad) const;
  void StartTween(FTween& T, float From, float To, float DurMs);

  FS09CardView CardModel;
  FUmCardState StateModel;
  bool bHasModel = false;
  bool bCodeDefaultTree = false;
  // what is shown
  EUmCardFace FaceKind = EUmCardFace::Fallback;
  FString FaceKey;
  FString TexPath;
  FIntPoint SrcPx = FIntPoint::ZeroValue;
  FVector4 FaceUv = FVector4(0.0, 0.0, 1.0, 1.0);
  bool bLoading = false;
  bool bWarnedFallback = false;
  FUmCardFit FitNow;
  FName FrameKeyNow;
  FName FrameOverride;
  bool bFrameTexture = false;
  // states
  bool bPlayable = true;
  FS09Reason Reason;
  bool bNew = false;
  bool bHover = false;
  bool bSelected = false;
  bool bFocus = false;
  bool bLowered = false;
  bool bFaceDownNow = false;
  bool bRevealed = false;
  int32 Boost = UmCardWidget::NoBoostChip;
  bool bCandidate = false;
  bool bMarked = false;
  // tweens
  FTween ScaleTween = {-1.0, 0.0f, 1.0f, 1.0f};  // hover scale (at rest 1: the To of an idle tween)
  FTween DesatTween;       // 0..1 of the unplayable look
  FTween ShiftTween;       // discard shift su
  FTween FocusTween;       // focus ring opacity
  double NewStartMs = -1.0;
  double NewLeaveMs = -1.0;
  double ChipStartMs = -1.0;
  double ChipLeaveMs = -1.0;
  double DropStartMs = -1.0;
  double DropLeaveMs = -1.0;
  double FlashStartMs = -1.0;
  double FlipStartMs = -1.0;
  float FlipDurMs = 0.0f;
  bool bFlipToFace = false;
  bool bFlipSwapped = false;
  bool bFlipReduced = false;
  TOptional<FS09CardView> PendingFace;
  float ScaleNow = 1.0f;
  float ScaleXNow = 1.0f;
  float ShiftNow = 0.0f;
  float DesatNow = 0.0f;
  float FaceOpacityNow = 1.0f;
  // input
  FName PressId;
  TSharedPtr<FS09HudPressArbiter> Arbiter;
  FS09OnHudPressOutcome OnOutcome;
  TFunction<void(bool)> OnHoverChanged;
  TFunction<void()> OnInspect;
  // test / sheet hooks
  double ClockOverrideMs = -1.0;
  int32 ReducedOverride = -1;
  int32 LegacyOverride = -1;
  bool bSyncLoad = false;
  FDelegateHandle CultureHandle;
  TSharedPtr<FStreamableHandle> LoadHandle;
  TSharedPtr<FStreamableHandle> PreloadHandle;  // CP-20: the revealed face loads during the first half of the flip
  FSoftObjectPath LoadingPath;
  UPROPERTY(Transient) TObjectPtr<UTexture2D> FaceTexture;
  UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> FaceMid;
};
