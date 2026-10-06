// DE-023 (W-15 HUD; 01 F-07, F-12, D-DE-07, D-DE-12; 02-ux-ui-spec §4.3 "Ход и действия" п. 1, 2, 4; ICON-MOTION.md
// "Трекер действий: поведение игры"): the persistent UMG portrait of a player - built once with the HUD, never
// recreated by RefreshHud, so the long animations (the turn ring, the tracker marks, the heart pulse) play on it.
//
// Native UUserWidget with a code-built tree (no WBP, like US08AnimatedIconWidget):
//   Border (HUD panel) > HorizontalBox
//     [Overlay "Avatar": round disc in the team colour + the hero monogram (no portrait art yet), the turn ring icon
//      over it (marker-turn-ring geometry: canvas 32 u, portrait window 21 u)]
//     [VerticalBox: hero name, status ("YOUR TURN" / "THEIR TURN" / "waiting"), heart icon + "hp/max", tracker icons]
//
// What plays (the game mode feeds S09/S09TurnHud.h models and calls these). Run I (2026-10-05, the user's answer to
// the A/B sheet of DE-028: AB-5 warm ring, AB-6 heart glow on, AB-7 DE tracker, AB-8 the fallen cross and the stamp in
// the Codex form) made the accepted DE-012 look the default; each part has its rollback flag (AGENTS.md: accepted art
// is the default, flags only roll it back):
//   - ring (AB-5): marker-turn-ring - the warm flash of the whole rim 1000 ms (yellow -> orange -> red), then the
//     smouldering rim; PlayRing = appear, at rest for a join mid-turn; StopRing = leave. -S08TurnRingLegacy: no ring
//     (the turn shows by the status and the banner). -S08TurnRingIcon=<id> draws another contract record with appear +
//     leave (the team candidate of the A/B sheet), =none no ring;
//   - tracker (AB-7): one marker-action-slot-de per slot - the grey ghost in the orange rim; a spent slot fills with the
//     icon of its action type (body / glyph layers from action-<type>, `fill` 300 ms, held), a cancel `unfill`s it.
//     -S08TrackerLegacy: the v3 slot resource-action-full (spend = faded, gain). Both: a new turn snaps to the rest pose
//     in one frame; the opponent's container fades in over 150 ms (UMG opacity); no slot pulse in the HUD (the
//     contract's loop budget: the pulse cycles in the gallery only);
//   - heart (AB-6): resource-hp-full damage / deplete / heal with its `glow` layer (the red halo 200-1000 ms);
//     -S08HeartGlowLegacy hides that layer. -S08HeartGlow (the former A/B option) is a no-op alias;
//   - fallen (AB-8): at the heart mark of the hero's death (contact + 1100, DE-019) the heart becomes resource-hp-fallen
//     and its small cross stamps in (appear); -S08CrossLegacy keeps the emptied heart of the deplete (the "dark" heart).
//     The same flag rolls back the marker-x-stamp of "no defense" in the combat panel (S08FlowGameMode).
//
// VS-2 CP-08 (cards-portraits.csv CP-08; 04 §4.3 WBP_UmPortrait; UI/UmPortrait.h): the avatar of the registry in the
// circle (UImage AvatarImage with a MID of M_UmPortraitDisc: our rim, the turn ring outside, no team colour); the
// team-colour disc and the monogram stay only for the fallback (no key / no PNG: a card.navy disc, a Warning) and the
// rollback -S08PortraitLegacy. The tree is BuildDefaultTree (also the source of WBP_UmPortrait); the animated icons
// (ring, heart, tracker) are added in code. SetPortrait takes the hero slug; SetHeroName falls back to the name's slug.
//
// VS-2 HB-18 / HB-19 (hud.csv; 04 §2.2, §2.3, §4.3): inside UUmHudPlayerPanel (UI/UmHudPlayerPanel.h) the portrait is
// the circle only - AttachToPanel collapses its own plate and text column, moves the heart into the panel's HeartIcon
// and puts the tracker icons into the panel's TrackerRow; the logic of the ring (AB-5), the tracker (AB-7), the heart
// glow (AB-6) and the cross (AB-8) stays here, the look does not change. SetPanelGeometry sizes the ring window, the
// circle and the tracker slots of the class (L 104 / 80 / 32 su, S 80 / 64 / 24 su, CX-09); SetRingSmoulder sets the
// rest of the rim (theme ring.smoulder / ring.smoulder.s, ВР-43). Colours of the plate and the status (the rollback
// column, -S08SlateHud=panels) come from UUmHudTheme.
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "S08ArtHudWidgets.h"
#include "UI/UmPortrait.h"
#include "S08TurnPortraitWidget.generated.h"

class UBorder;
class UHorizontalBox;
class UImage;
class UMaterialInstanceDynamic;
class UOverlay;
class USizeBox;
class UTextBlock;
class UTexture2D;
class US08AnimatedIconWidget;

/** The look options of the turn HUD (command line; traced 'HUD-TURN config ...' and in the ARTLOOK line). */
struct UNMATCHED_API FS08TurnHudLook {
  /** The accepted ring (AB-5) and its rollback flags. */
  static constexpr const TCHAR* DefaultRingIcon = TEXT("marker-turn-ring");
  static constexpr const TCHAR* RingLegacyFlag = TEXT("S08TurnRingLegacy");
  static constexpr const TCHAR* HeartGlowLegacyFlag = TEXT("S08HeartGlowLegacy");
  static constexpr const TCHAR* TrackerLegacyFlag = TEXT("S08TrackerLegacy");
  static constexpr const TCHAR* CrossLegacyFlag = TEXT("S08CrossLegacy");
  /** The tracker slot icons: DE (AB-7, default) and v3 (rollback). */
  static constexpr const TCHAR* TrackerDeIcon = TEXT("marker-action-slot-de");
  static constexpr const TCHAR* TrackerV3Icon = TEXT("resource-action-full");
  static constexpr const TCHAR* FallenHeartIcon = TEXT("resource-hp-fallen");
  static constexpr const TCHAR* NoDefenseStampIcon = TEXT("marker-x-stamp");

  /** Contract icon of the turn ring (NAME_None = no ring drawn: -S08TurnRingLegacy or -S08TurnRingIcon=none). */
  FName RingIcon = FName(DefaultRingIcon);
  /** Play the heart damage with its glow layer (AB-6). */
  bool bHeartGlow = true;
  /** The DE tracker (AB-7); false = the v3 slots. */
  bool bTrackerDe = true;
  /** The fallen heart's cross and the "no defense" stamp (AB-8); false = the dark heart and the text X. */
  bool bCrossGlyphs = true;
  /** Refused option text (empty = all accepted). */
  FString Issues;

  /** Defaults above; -S08TurnRingLegacy -S08TurnRingIcon=<contract id with appear + leave | none> -S08HeartGlowLegacy
   *  -S08TrackerLegacy -S08CrossLegacy. A ring id the contract lacks is refused (Issues) and no ring is drawn. */
  static FS08TurnHudLook FromCommandLine(const TCHAR* CommandLine);
  /** 'ring=<id|none> heartGlow=0|1 tracker=de|v3 cross=0|1[ issues=...]' (the HUD-TURN config line). */
  FString Describe() const;
  /** The ARTLOOK field: 'hud=ring:<id>,glow:on,tracker:de,cross:on' - a rolled back part names its flag
   *  ('ring:legacy(-S08TurnRingLegacy)'), a -S08TurnRingIcon choice its id. */
  static FString ArtLookField(const TCHAR* CommandLine);
  FName TrackerIcon() const { return FName(bTrackerDe ? TrackerDeIcon : TrackerV3Icon); }
};

UCLASS()
class UNMATCHED_API US08TurnPortraitWidget : public UUserWidget {
  GENERATED_BODY()

public:
  /** Side of the avatar disc / ring window in slate units; the ring icon is 64 su (32 u canvas, exact 64 px texture). */
  static constexpr float RingSu = 64.0f;
  static constexpr float DiscSu = 42.0f;  // 64 * 21 / 32
  static constexpr float SmallIconSu = 24.0f;
  static constexpr float TrackerIconSu = 32.0f;

  virtual bool Initialize() override;
  /** VS-2 CP-08: Panel > Row > [AvatarBox > Avatar > (DiscBox > DiscStack > Disc, AvatarImage) + MonogramText] +
   *  [Column > NameText, StatusText, Stats > HpText, TrackerRow] - names = BindWidget names; the WBP is authored from it. */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  /** WBP_UmPortrait's class when the asset exists, else the native class (OutSource: the WBP path or "code-default"). */
  static US08TurnPortraitWidget* Create(UWorld* World, FString* OutSource = nullptr);
  bool HasAllParts(FString* OutMissing = nullptr) const;
  bool UsesCodeDefaultTree() const { return bCodeDefaultTree; }

  /** CP-08: the registry key of the circle ("king-arthur", "medusa/harpies"; NAME_None = monogram); SidekickNumber is
   *  the harpy's 1..3 for the fallback digit. Same key again = no work (П2). */
  void SetPortrait(FName Key, int32 SidekickNumber = 0);
  /** avatar / fallen (saturation 0) / loser (saturation 0 + opacity 0.6 over 400 ms; reduced motion and !bAnimate -
   *  at once). */
  void SetPortraitState(EUmPortraitState State, bool bAnimate = true);
  /** 'PORTRAIT id=.. tex=.. su=.. px=.. scale=.. show=<Show> side=own|opp state=..'. */
  FString PortraitShotLine(const TCHAR* Show = TEXT("panel")) const;
  FName GetPortraitKey() const { return PortraitKey; }
  bool IsAvatarShown() const { return bAvatarShown; }
  /** The circle su shown (the ВР-CP04 cap applied) and the monogram text (fallback / legacy). */
  float GetCircleSu() const { return CircleSu; }
  FString GetMonogram() const;
  const UTexture2D* GetAvatarTexture() const { return AvatarTexture; }
  UMaterialInstanceDynamic* GetAvatarMaterial() const { return AvatarMid; }
  EUmPortraitState GetPortraitState() const { return PortraitState; }
  /** Tests: px per su instead of UmHudScale::Current() (the 1440p 150 % cap), and the legacy flag. */
  void SetPxPerSuForTest(float PxPerSu) { PxPerSuOverride = PxPerSu; }
  void SetPortraitLegacyForTest(int32 Legacy) { LegacyOverride = Legacy; }

  /** Once after creation: side, look, team colour (the C-11 chip colour of the hero's team look). */
  void Setup(bool bInOpponent, const FS08TurnHudLook& InLook, const FLinearColor& TeamColor);
  void SetTeamColor(const FLinearColor& TeamColor);
  void SetHeroName(const FString& Name);
  /** "hp/max" next to the heart; no anim (the heart events come from PlayHeart). */
  void SetHealth(int32 Health, int32 MaxHealth);
  /** The status line under the name (own / opponent / waiting). */
  void SetActive(bool bActive);
  /** Heart event animation ('damage' / 'deplete' / 'heal'); false = unknown. */
  bool PlayHeart(FName Anim);

  /** Ring: appear (bAtRest: already smouldering - join / reconnect mid-turn). No-op without a ring icon. */
  void PlayRing(bool bAtRest);
  void StopRing();
  bool IsRingShown() const { return bRingShown; }
  bool HasRingIcon() const { return RingIcon != nullptr; }

  /** Tracker: Slots icons, Shown of them spent. bReset = a new turn / first frame: the poses snap without an animation
   *  (01 F-12 "сброс за 1 кадр"); otherwise a growing count plays spend, a shrinking one gain (the restore of a
   *  cancelled choice). Types[i] = the action type of spent slot i ('attack' / 'maneuver' / 'scheme' / 'defense'):
   *  the DE slot fills with that icon (a missing / unknown type keeps the slot's current fill). Returns the game
   *  event ('spend' / 'gain' / 'reset' / 'slots' / '' when nothing changed) - the DE slot plays fill / unfill for it. */
  FString ApplyTracker(int32 Slots, int32 Shown, bool bReset, const TArray<FName>& Types = TArray<FName>());
  /** The action type a DE slot is filled with ('' for a v3 slot or an unfilled one). */
  FString GetTrackerFill(int32 Index) const;
  /** AB-8: the hero fell (the heart mark, contact + 1100) - the heart becomes resource-hp-fallen and stamps its cross
   *  (bAtRest: already crossed, no stamp); false brings the full heart back (a new game). No-op with -S08CrossLegacy
   *  or when unchanged. Returns true when the heart changed. */
  bool SetHeartFallen(bool bFallen, bool bAtRest = false);
  bool IsHeartFallen() const { return bHeartFallen; }
  /** Opacity of the tracker row (the opponent's 150 ms appear; 0 hides it). */
  void SetTrackerOpacity(float Alpha);
  int32 GetTrackerSlots() const { return TrackerIcons.Num(); }
  int32 GetTrackerShown() const { return TrackerShown; }
  US08AnimatedIconWidget* GetTrackerIcon(int32 Index) const {
    return TrackerIcons.IsValidIndex(Index) ? TrackerIcons[Index].Get() : nullptr;
  }
  US08AnimatedIconWidget* GetHeartIcon() const { return HeartIcon; }
  US08AnimatedIconWidget* GetRingIcon() const { return RingIcon; }
  UTextBlock* GetStatusText() const { return StatusText; }
  bool IsOpponent() const { return bOpponent; }
  /** Freezes (>= 0) or resumes (< 0) the clock of every icon of the portrait (gallery preview shots). */
  void SetClockOverrideMs(float Ms);
  const FS08TurnHudLook& GetLook() const { return Look; }

  // ---- VS-2 HB-18 / HB-19: the circle of a UUmHudPlayerPanel ----
  /** Once, before Setup: the own plate and text column collapse; Heart (the panel's HeartIcon) becomes the heart of
   *  PlayHeart / SetHeartFallen, TrackerHost (the panel's TrackerRow) receives the tracker icons. */
  void AttachToPanel(UHorizontalBox* TrackerHost, US08AnimatedIconWidget* Heart);
  bool IsPanelMode() const { return bPanelMode; }
  /** The class sizes in a panel: ring window, circle, tracker slot (su). Existing icons resize in place. */
  void SetPanelGeometry(float InRingSu, float InDiscSu, float InTrackerSu);
  float GetRingWindowSu() const { return RingWindowSu; }
  float GetTrackerSlotSu() const { return TrackerSlotSu; }
  /** ВР-43: the rest of the smouldering rim (the contract's 0.35 scales its rim track; <= 0 = the contract). */
  void SetRingSmoulder(float Rest);
  float GetRingSmoulder() const { return RingSmoulder; }

  // ---- the tree (04 §4.3: BindWidget names; RingIcon / HeartIcon / tracker icons are added in code) ----
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UBorder> Panel;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UOverlay> Avatar;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<USizeBox> DiscBox;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UImage> Disc;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UImage> AvatarImage;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UTextBlock> MonogramText;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UTextBlock> NameText;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UTextBlock> StatusText;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UHorizontalBox> Stats;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UTextBlock> HpText;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UHorizontalBox> TrackerRow;

protected:
  virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;

private:
  void BindParts();
  void ApplyPortraitLook();
  void ApplyStateParams();
  bool PortraitLegacy() const;
  float PxPerSuNow() const;

  UPROPERTY() TObjectPtr<US08AnimatedIconWidget> RingIcon;
  UPROPERTY() TObjectPtr<US08AnimatedIconWidget> HeartIcon;
  UPROPERTY() TArray<TObjectPtr<US08AnimatedIconWidget>> TrackerIcons;
  UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> AvatarMid;
  UPROPERTY(Transient) TObjectPtr<UTexture2D> AvatarTexture;
  bool bCodeDefaultTree = false;
  FName PortraitKey;
  bool bPortraitKeyExplicit = false;
  int32 PortraitSidekick = 0;
  bool bPortraitApplied = false;
  bool bAvatarShown = false;
  float CircleSu = 0.0f;
  float SrcCirclePx = 0.0f;
  float AppliedPxPerSu = 0.0f;
  FString AvatarPath;
  EUmPortraitState PortraitState = EUmPortraitState::Avatar;
  float StateFrom = 1.0f;     // the loser fade: opacity 1 -> 0.6, desaturation 0 -> 1 over LoserMs
  double StateStart = -1.0;
  float PxPerSuOverride = 0.0f;
  int32 LegacyOverride = -1;
  TSet<FName> WarnedKeys;
  FString LastPortraitLine;

  FS08TurnHudLook Look;
  // VS-2 HB-18 / HB-19: the panel mode and the class sizes (the column of the rollback keeps the constants)
  bool bPanelMode = false;
  float RingWindowSu = RingSu;
  float DiscWindowSu = DiscSu;
  float TrackerSlotSu = TrackerIconSu;
  float RingSmoulder = 0.0f;
  bool bOpponent = false;
  bool bActive = false;
  bool bRingShown = false;
  int32 TrackerShown = 0;
  bool bHeartFallen = false;
  TArray<FName> TrackerFill;  // DE slots: the type each slot is filled with (NAME_None = the contract's)
  FString HeroName;
  int32 LastHealth = MIN_int32;
  int32 LastMaxHealth = MIN_int32;
  bool bTeamColorSet = false;
  FLinearColor LastTeamColor = FLinearColor::Transparent;
};
