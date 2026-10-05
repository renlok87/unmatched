// DE-023 (W-15 HUD; 01 F-07, F-12, D-DE-07, D-DE-12; 02-ux-ui-spec §4.3 "Ход и действия" п. 1, 2, 4; ICON-MOTION.md
// "Трекер действий: поведение игры"): the persistent UMG portrait of a player - built once with the HUD, never
// recreated by RefreshHud, so the long animations (the turn ring, the tracker marks, the heart pulse) play on it.
//
// Native UUserWidget with a code-built tree (no WBP, like US08AnimatedIconWidget):
//   Border (HUD panel) > HorizontalBox
//     [Overlay "Avatar": round disc in the team colour + the hero monogram (no portrait art yet), the turn ring icon
//      over it (marker-turn-ring candidate geometry: canvas 32 u, portrait window 21 u)]
//     [VerticalBox: hero name, status ("YOUR TURN" / "THEIR TURN" / "waiting"), heart icon + "hp/max", tracker icons]
//
// What plays (the game mode feeds S09/S09TurnHud.h models and calls these):
//   - ring: the contract record named by -S08TurnRingIcon=<id> (the DE-012 candidates until the user's art acceptance -
//     no ring id is built in, accepted art stays the default); PlayRing = appear (flash 1000 ms -> smouldering rim),
//     at rest for a join mid-turn; StopRing = leave;
//   - tracker: one resource-action-full per slot (v3 "spent = faded": spend / gain - accepted v3 animations);
//     a new turn snaps to the rest pose in one frame; the opponent's container fades in over 150 ms (UMG opacity);
//   - heart: resource-hp-full damage / deplete / heal; its `glow` layer (DE-012 candidate) is hidden unless
//     -S08HeartGlow (the A/B option of DE-028).
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "S08TurnPortraitWidget.generated.h"

class UBorder;
class UHorizontalBox;
class UImage;
class UOverlay;
class USizeBox;
class UTextBlock;
class US08AnimatedIconWidget;

/** The look options of the turn HUD (command line, traced 'HUD-TURN config ...'). */
struct UNMATCHED_API FS08TurnHudLook {
  /** Contract icon of the turn ring (NAME_None = no ring drawn - the default until the art acceptance). */
  FName RingIcon = NAME_None;
  /** Play the heart damage with its glow layer (DE-012 candidate). */
  bool bHeartGlow = false;
  /** Refused option text (empty = all accepted). */
  FString Issues;

  /** -S08TurnRingIcon=<contract id with appear + leave> -S08HeartGlow. */
  static FS08TurnHudLook FromCommandLine(const TCHAR* CommandLine);
  FString Describe() const;
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
   *  cancelled choice). Returns the animation name ('spend' / 'gain' / 'reset' / '' when nothing changed). */
  FString ApplyTracker(int32 Slots, int32 Shown, bool bReset);
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

private:
  UPROPERTY() TObjectPtr<UBorder> Panel;
  UPROPERTY() TObjectPtr<UImage> Disc;
  UPROPERTY() TObjectPtr<UTextBlock> MonogramText;
  UPROPERTY() TObjectPtr<UTextBlock> NameText;
  UPROPERTY() TObjectPtr<UTextBlock> StatusText;
  UPROPERTY() TObjectPtr<UTextBlock> HpText;
  UPROPERTY() TObjectPtr<UHorizontalBox> TrackerRow;
  UPROPERTY() TObjectPtr<US08AnimatedIconWidget> RingIcon;
  UPROPERTY() TObjectPtr<US08AnimatedIconWidget> HeartIcon;
  UPROPERTY() TArray<TObjectPtr<US08AnimatedIconWidget>> TrackerIcons;
  UPROPERTY() TObjectPtr<UOverlay> Avatar;

  FS08TurnHudLook Look;
  bool bOpponent = false;
  bool bActive = false;
  bool bRingShown = false;
  int32 TrackerShown = 0;
  FString HeroName;
  int32 LastHealth = MIN_int32;
  int32 LastMaxHealth = MIN_int32;
  bool bTeamColorSet = false;
  FLinearColor LastTeamColor = FLinearColor::Transparent;
};
