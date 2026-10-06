// VS-2 HB-18 / HB-19 / HB-20 (docs/game-design/visual/06-tasks/hud.csv; 04-hud-spec.md §2.2, §2.3, §4.2, §4.3, §5.2
// step H4, §7.1; ВР-01, ВР-43, ВР-47, ВР-72, ВР-H03; CX-09 mockup art/imagegen/hud-panels-v1-codex, accepted by
// delegation): the player panel of the GAME screen - UUmHudPlayerPanel, one class for both sides:
//   PANEL-LOC  /Game/S08/UI/Hud/WBP_UI_HUD_PANEL_LOC  Side Own, left-bottom: L (24, 920, 340, 136), S (16, H-112, 240, 96)
//   PANEL-OPP  /Game/S08/UI/Hud/WBP_UI_HUD_PANEL_OPP  Side Opp, right-top (ВР-01 diagonal): L (W-364, 24), S (W-256, 16),
//              mirrored (ВР-H03): the avatar on the right, the text right-aligned on one edge, the tracker outside left.
//
//   tree     Border "Panel" (T_Skin_Panel) > CanvasPanel "Canvas" > Portrait (US08TurnPortraitWidget, WBP_UmPortrait:
//            the circle and the turn ring), NameText, StatusRow [PulseDot, StatusText], HpRow [HeartIcon, HpText],
//            TrackerRow, SidekickRow - every place from UmHudPanel::Geometry (CX-09 facts.json, su):
//              L own   ring window (4, 12, 104) round the avatar 80; text x 128 (name y 12 type.heading 24, status y 38
//                      type.tag 14 caps, heart 24 + HP type.button 20 at y 54); tracker 2 x 32 su right edge 328, y 50;
//                      sidekicks y 82: mini portraits 32 su - the harpies 64 su apart with their number 1-3 on a
//                      card.navy disc 14 su and «1/1» under it (ВР-72, ВР-HB13), Merlin with his name and «7/7»
//              L opp   the same mirrored: ring (232, 12), text right edge 212, tracker x 12 y 46
//              S       240 x 96: ring (4, 8, 80) round the avatar 64, text x 92 (opp: right edge 148), heart + HP y 60,
//                      tracker 2 x 24 su (own: right edge 228, opp: x 12), y 58; the sidekicks in the panel's tooltip
//                      (hud.panel.sidekick rows, the fallen ones with the fallen heart; ВР-VS2-CX09-06)
//   logic    the ring (AB-5), the tracker (AB-7), the heart glow (AB-6) and the cross (AB-8) are the portrait's
//            (US08TurnPortraitWidget::AttachToPanel: the heart is HeartIcon, the tracker icons go into TrackerRow) -
//            the game mode drives them as before (S08FlowGameModeTurnHud.cpp); this class owns the text, the
//            sidekicks, the class sizes and the theme's ring.smoulder (ВР-43: L 0.35, S 0.55).
//   states   own «ВАШ ХОД» turn.flash.yellow; wait «ЖДЁТ» text.secondary; opp (their turn) - no status text
//            (ВР-VS2-CX09-07: the ring, their tracker and STATUS's verb say it); ai «ИИ ДУМАЕТ» with the pulse dot
//            8 su text.secondary, 1 Hz 1 -> 0.35 (reduced: static); fallen «ВНЕ ИГРЫ» + the portrait's grey circle.
//   input    a click on the panel = the deck panel of its side (the HUD press arbiter, DE-014; the owner wires it).
// Data in ApplyModel(FUmPlayerPanelModel) only (П1), same model = no work (П2); the gatherer is UmHudPanel::Gather
// (world-free) in UmHudPanels.h. SHOT: 'SHOT widget id=UI-HUD-PANEL-LOC|UI-HUD-PANEL-OPP state=own|wait|opp|ai|fallen'.
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../../S09/S09HudPress.h"
#include "../S08ArtHud.h"
#include "../S08ArtHudWidgets.h"
#include "UmPortrait.h"
#include "UmHudPlayerPanel.generated.h"

class UBorder;
class UCanvasPanel;
class UHorizontalBox;
class UImage;
class UTextBlock;
class US08AnimatedIconWidget;
class US08TurnPortraitWidget;
struct FS08TurnHudLook;

enum class EUmPanelSide : uint8 { Own, Opp };
/** SHOT states (04 §7.1: PANEL-LOC own | wait | fallen; PANEL-OPP opp | wait | fallen | ai). */
enum class EUmPanelState : uint8 { Own, Wait, Opp, Ai, Fallen };

/** One sidekick of the panel's row (fighters of the player that are not the hero; a fallen one stays). */
struct UNMATCHED_API FUmSidekickView {
  FString Id;
  FString Name;    // the fighter's label ("Harpies 2", "Merlin") - data, not a string table
  FName Key;       // portrait registry key "<hero>/<sidekick>" (CP-08)
  int32 Number = 0;  // the harpies 1..3 (ВР-72); 0 = a named sidekick
  int32 Hp = 0;
  int32 MaxHp = 0;
  bool bFallen = false;
  bool operator==(const FUmSidekickView& O) const {
    return Id == O.Id && Name == O.Name && Key == O.Key && Number == O.Number && Hp == O.Hp && MaxHp == O.MaxHp &&
           bFallen == O.bFallen;
  }
};

struct UNMATCHED_API FUmPlayerPanelModel {
  FString HeroName;
  bool bHasHp = false;
  int32 Hp = 0;
  int32 MaxHp = 0;
  EUmPanelState State = EUmPanelState::Wait;
  TArray<FUmSidekickView> Sidekicks;
  bool bClassS = false;
  float PxPerSu = 1.0f;
  bool operator==(const FUmPlayerPanelModel& O) const {
    return HeroName == O.HeroName && bHasHp == O.bHasHp && Hp == O.Hp && MaxHp == O.MaxHp && State == O.State &&
           Sidekicks == O.Sidekicks && bClassS == O.bClassS && PxPerSu == O.PxPerSu;
  }
};

namespace UmHudPanel {
/** The places of the panel (su, panel-local) for a class and a side (CX-09). */
struct UNMATCHED_API FGeom {
  FVector2D Size = FVector2D(340.0, 136.0);
  FVector2D RingPos = FVector2D(4.0, 12.0);
  float RingSu = 104.0f;
  float DiscSu = 80.0f;
  /** Own: the left edge of the text column; Opp: its right edge. */
  float TextX = 128.0f;
  float NameTop = 7.0f;    // the text box tops: the glyphs then sit at y 12 / 38 / 54 of the mockup
  float StatusTop = 35.0f;
  float HpTop = 54.0f;
  float TrackerSu = 32.0f;
  /** Own: the right edge of the tracker; Opp: its left edge. */
  float TrackerX = 328.0f;
  float TrackerTop = 50.0f;
  bool bSidekickRow = true;
  float SidekickTop = 82.0f;
};
UNMATCHED_API FGeom Geometry(bool bClassS, EUmPanelSide Side);
inline constexpr float SidekickSu = 32.0f;
inline constexpr float SidekickStepSu = 64.0f;  // the harpies 128 / 192 / 256
inline constexpr float IndexDiscSu = 14.0f;     // ВР-72: the number on a card.navy disc in the corner
inline constexpr float HeartSu = 24.0f;
inline constexpr float DotSu = 8.0f;            // CX-09 fix1: the «ИИ думает» dot 8 su, 5 su before the text
inline constexpr float DotGapSu = 5.0f;
inline constexpr int32 NameMaxChars = 14;       // 04 §2.2: type.heading up to 14 characters, else type.button
UNMATCHED_API const TCHAR* StateName(EUmPanelState State);
UNMATCHED_API const TCHAR* ShotId(EUmPanelSide Side);
/** The status line of a state (the string tables; opp = empty), upper case (type.tag caps, 04 §2.2). */
UNMATCHED_API FText StatusText(EUmPanelState State);
/** turn.flash.yellow for own, text.secondary otherwise. */
UNMATCHED_API FName StatusColorToken(EUmPanelState State);
/** type.heading, or type.button above 14 characters. */
UNMATCHED_API FName NameFontToken(const FString& Name);
/** hud.panel.hp «{hp}/{max}» (hp below 0 shows 0; no max = the number alone). */
UNMATCHED_API FText HpText(int32 Hp, int32 MaxHp);
/** hud.panel.sidekick «{name} {hp}/{max}». */
UNMATCHED_API FText SidekickLine(const FUmSidekickView& S);
/** The ring rest of the class (theme ring.smoulder / ring.smoulder.s). */
UNMATCHED_API float RingSmoulder(bool bClassS);
}  // namespace UmHudPanel

UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmHudPlayerPanel : public UUserWidget {
  GENERATED_BODY()

 public:
  static const TCHAR* const LocBlueprintPath;  // /Game/S08/UI/Hud/WBP_UI_HUD_PANEL_LOC
  static const TCHAR* const OppBlueprintPath;  // /Game/S08/UI/Hud/WBP_UI_HUD_PANEL_OPP

  virtual bool Initialize() override;
  /** Panel > Canvas > Portrait, NameText, StatusRow > (PulseDot, StatusText), HpRow > (HeartIcon, HpText), TrackerRow,
   *  SidekickRow; Side = the mirrored places of PANEL-OPP (the WBP of each side is authored from it). */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, EUmPanelSide Side, FString* OutError = nullptr);
  /** The WBP of the side when the asset exists, else the native class. */
  static UClass* WidgetClass(EUmPanelSide Side);
  bool HasAllParts(FString* OutMissing = nullptr) const;
  bool UsesCodeDefaultTree() const { return bCodeDefaultTree; }
  FString SourceName() const;

  /** Once after creation: the side (the mirrored places), the portrait in panel mode, the turn HUD look (rings and
   *  rollback flags), the team colour of the ring's team variant. */
  void Setup(EUmPanelSide InSide, const FS08TurnHudLook& Look, const FLinearColor& TeamColor);
  EUmPanelSide GetSide() const { return Side; }
  /** The one data input (П1); same model = no work. */
  void ApplyModel(const FUmPlayerPanelModel& InModel);
  const FUmPlayerPanelModel& GetModel() const { return Model; }
  bool HasModel() const { return bHasModel; }
  /** A click on the panel (DE-014: the arbiter's press / release; the owner opens the deck panel of the side). */
  void SetPress(FName InId, const TSharedPtr<FS09HudPressArbiter>& InArbiter, const FS09OnHudPressOutcome& InOnOutcome);
  /** 'SHOT widget id=UI-HUD-PANEL-LOC|OPP state=.. bbox=<Rect> ... hero=.. hp=.. sidekicks=.. tracker=.. ring=..'. */
  void CollectShotLines(TArray<FString>& Out, const FS08ScreenRect& Rect) const;
  /** VS-2 CP-10 / CP-12: one PORTRAIT line per sidekick mini portrait of the L row ('id=king-arthur/merlin',
   *  'id=medusa/harpies .. n=1..3', show=panel); class S shows none (the tooltip). */
  void CollectPortraitLines(TArray<FString>& Out) const;
  /** The mini portraits as built (the row order). */
  const TArray<FUmPortraitShown>& GetMiniPortraits() const { return MiniShown; }
  /** Tests / the gallery: the pulse clock (seconds; < 0 = the platform clock) and reduced motion (-1 = the setting). */
  void SetClockForTest(TFunction<double()> InClock) { Clock = MoveTemp(InClock); }
  void SetReducedForTest(int32 InReduced) { ReducedOverride = InReduced; }
  float GetDotOpacity() const;
  bool IsStatusFading() const { return StatusFadeStart >= 0.0; }
  /** The pulse of the «ИИ думает» dot now (the tick does it per frame). */
  void StepMotion();
  /** The sidekick items built (the row in L, the tooltip rows in S). */
  int32 GetSidekickItems() const { return SidekickItems; }
  int32 GetTooltipRows() const { return TooltipRows; }
  UWidget* GetSidekickTooltip() const { return SidekickTip; }

  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UBorder> Panel;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UCanvasPanel> Canvas;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<US08TurnPortraitWidget> Portrait;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UTextBlock> NameText;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UHorizontalBox> StatusRow;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UImage> PulseDot;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UTextBlock> StatusText;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UHorizontalBox> HpRow;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<US08AnimatedIconWidget> HeartIcon;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UTextBlock> HpText;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UHorizontalBox> TrackerRow;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UHorizontalBox> SidekickRow;

 protected:
  virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;
  virtual FReply NativeOnMouseButtonDown(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
  virtual FReply NativeOnMouseButtonUp(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;

 private:
  void BindParts();
  void ApplyFonts();
  void ApplyGeometry();
  void RebuildSidekicks();
  void ApplyStatus(EUmPanelState State);
  UWidget* MakeMiniPortrait(const FUmSidekickView& S);
  UWidget* MakeFallenHeart();
  bool IsReduced() const;
  double Now() const;

  EUmPanelSide Side = EUmPanelSide::Own;
  FUmPlayerPanelModel Model;
  bool bHasModel = false;
  bool bGeometryApplied = false;
  bool bAppliedClassS = false;
  float AppliedPxPerSu = 0.0f;
  bool bCodeDefaultTree = false;
  int32 SidekickItems = 0;
  int32 TooltipRows = 0;
  double PulseStart = 0.0;
  double StatusFadeStart = -1.0;  // the old status word fading out (120 ms), then the new one
  int32 ReducedOverride = -1;
  TFunction<double()> Clock;
  FName PressId;
  TSharedPtr<FS09HudPressArbiter> Arbiter;
  FS09OnHudPressOutcome OnOutcome;
  UPROPERTY(Transient) TObjectPtr<UWidget> SidekickTip;
  UPROPERTY(Transient) TArray<TObjectPtr<UObject>> KeepAlive;  // the MIDs of the mini portraits
  TArray<FUmPortraitShown> MiniShown;  // CP-10 / CP-12: what each mini portrait shows (the PORTRAIT lines)
};
