// SEL (docs/game-design/select-screens/02-DESIGN.md §6): the 3D hero showcases of the fighting-game style select
// screens - AUmHeroShowcase, one actor far from the board (X = +ShowcaseOffsetUU) with two sides (0 = the viewer,
// left on screen; 1 = the opponent, right). Each side: the look-dev v2 figure of a hero (S08HeroesV2 mesh, team MI,
// pedestal, Idle / LungeAttack clips), a warm key light and a team-colour rim light with a short reach, and a
// USceneCaptureComponent2D that renders ONLY that figure and pedestal (ShowOnlyList, FinalColorLDR, no Lumen) into its
// render target; the screens draw the targets in UImage brushes.
//
//   framing  the figure turns three quarters towards the screen centre (side 0 looks right, side 1 left - never its
//            back, ВР-06), the camera frames the pedestal and the bounds top with a margin.
//   capture  every frame only while SetActive(true) (the select / VS screens are up); otherwise the captures sleep.
//   trace    'SHOWCASE side=<0|1> hero=<key|none> look=<P1|P2> clip=<Idle|LungeAttack|None> rt=<w>x<h> active=<0|1>'
//            on every change of the side.
//   rollback -S08SelectLegacy: never spawned (the legacy room and loading screens).
//   hipoly   DEFAULT since the blind rounds of 2026-10-16 (docs/game-design/select-screens/05-HIPOLY-COMPARE.md: round 2,
//            Opus and GPT Astra, 2:0): a static Nanite mesh of the Tripo H2 high-poly source without its phantom parts
//            and Tripo base (tools/art/showcase/clean_hipoly.py + import_hipoly.py, /Game/PipelineCandidates/<Key>/HP)
//            stands on the game pedestal with the team ring; a hero without an imported source keeps its v2 figure.
//            Rollback -S08ShowcaseV2: the animated skeletal v2 figure (Idle / LungeAttack) in every niche.
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "../S08HeroesV2.h"
#include "../S08Team.h"
#include "UmHeroShowcase.generated.h"

class UAnimSequenceBase;
class UPointLightComponent;
class USceneCaptureComponent2D;
class USkeletalMeshComponent;
class UStaticMeshComponent;
class UTextureRenderTarget2D;

namespace UmShowcase {
/** The select screens' look is the default; -S08SelectLegacy keeps the legacy room / loading screens. */
inline const TCHAR* const LegacyFlagName = TEXT("S08SelectLegacy");
UNMATCHED_API bool Enabled();
/** The static high-poly source in the niches (default); false with the rollback -S08ShowcaseV2. */
UNMATCHED_API bool HiPolyRequested();
inline const TCHAR* const V2FlagName = TEXT("S08ShowcaseV2");
/** /Game/PipelineCandidates/<Key>/HP/<source>.<source> of a v2 key, or "" when no high-poly source was imported. */
UNMATCHED_API FString HiPolyPath(const TCHAR* Key);
/** The game-look instance of one Tripo part of the high-poly (MI_<Key>_HP_<part>_<P1|P2>). */
UNMATCHED_API FString HiPolyMaterialPath(const TCHAR* Key, const FString& Part, ES08TeamSlot Look);
/** Automation tests only (Reset -> the command line again). */
UNMATCHED_API void SetEnabledOverrideForTest(bool bEnabled);
UNMATCHED_API void ResetEnabledOverrideForTest();
/** Far from every board (the boards stand around the origin, a few thousand uu wide): no board shadow or light. */
inline constexpr double ShowcaseOffsetUU = 400000.0;
/** The render target of a side (portrait 2:3): twice the niche's pixels at 1080p, mip-mapped - UMG minifies it
 *  through the mips (a supersampled edge; the first live frames at 512x768 showed jaggies on swords and snakes). */
inline constexpr int32 TargetW = 1024;
inline constexpr int32 TargetH = 1536;
/** The server fighter name of a portrait slug ("king-arthur" -> "King Arthur") from the S08HeroesV2 table; Fallback
 *  when no v2 figure has that slug. */
UNMATCHED_API FString FighterForSlug(FName Slug, const FString& Fallback);
/** The lock-in push of the camera (MK11: the camera closes in on the locked fighter): FOV at Seconds since the lock-in. */
UNMATCHED_API float PushFov(float BaseFov, double Seconds);
/** The yaw that turns a v2 figure (rig faces +X) three quarters towards the screen centre seen by the side's camera. */
UNMATCHED_API float FigureYawDeg(int32 Side);
}  // namespace UmShowcase

UCLASS(NotPlaceable, Transient)
class UNMATCHED_API AUmHeroShowcase : public AActor {
  GENERATED_BODY()

 public:
  AUmHeroShowcase();

  /** The one showcase of the world (spawned on first use). Null without a world or with -S08SelectLegacy. */
  static AUmHeroShowcase* Get(UWorld* World);

  /** Shows a hero on a side (the server fighter name: "King Arthur", "Medusa"); "" or an unmapped name = the empty
   *  pedestal of nobody (the side's capture shows black). Look = the team MI of the side. Restarts Idle on a change. */
  void SetHero(int32 Side, const FString& FighterName, ES08TeamSlot Look);
  /** The lock-in pose: LungeAttack once, then Idle again (S08HeroesV2::NextClip). */
  void PlayLockIn(int32 Side);
  /** Captures run every frame while active. */
  void SetActive(bool bInActive);
  /** A screen that shows the targets asks for the captures every frame (a lease): the showcase stays active while some
   *  screen asked within the last two frames, so the room and the loading screens never fight over SetActive. */
  void RequestActive();
  bool IsActive() const { return bActive; }

  UTextureRenderTarget2D* GetTarget(int32 Side) const;
  FString GetHeroKey(int32 Side) const;
  bool HasFigure(int32 Side) const;
  const TCHAR* GetClipName(int32 Side) const;

  virtual void Tick(float DeltaSeconds) override;

  UPROPERTY() TObjectPtr<USceneComponent> Root;
  UPROPERTY() TObjectPtr<USkeletalMeshComponent> Body[2];
  UPROPERTY() TObjectPtr<UStaticMeshComponent> Base[2];
  /** A dark matte wall behind the figure: the rim light paints a soft team-colour halo on it. */
  UPROPERTY() TObjectPtr<UStaticMeshComponent> Backdrop[2];
  /** The static high-poly source in place of Body (on the game pedestal Base); hidden with -S08ShowcaseV2. */
  UPROPERTY() TObjectPtr<UStaticMeshComponent> HiPoly[2];
  UPROPERTY() TObjectPtr<UPointLightComponent> Key[2];
  UPROPERTY() TObjectPtr<UPointLightComponent> RimLight[2];
  UPROPERTY() TObjectPtr<UPointLightComponent> Fill[2];
  UPROPERTY() TObjectPtr<USceneCaptureComponent2D> Capture[2];
  UPROPERTY() TObjectPtr<UTextureRenderTarget2D> Target[2];
  UPROPERTY() TArray<TObjectPtr<UAnimSequenceBase>> Clips0;
  UPROPERTY() TArray<TObjectPtr<UAnimSequenceBase>> Clips1;

 private:
  void EnsureTargets();
  void Frame(int32 Side);
  void PlayClip(int32 Side, S08HeroesV2::EClip Clip);
  void TraceSide(int32 Side) const;
  TArray<TObjectPtr<UAnimSequenceBase>>& ClipsOf(int32 Side) { return Side == 0 ? Clips0 : Clips1; }

  const S08HeroesV2::FHeroSpec* Spec[2] = {nullptr, nullptr};
  ES08TeamSlot SideLook[2] = {ES08TeamSlot::P1, ES08TeamSlot::P2};
  S08HeroesV2::EClip Clip[2] = {S08HeroesV2::EClip::None, S08HeroesV2::EClip::None};
  double ClipEndsAt[2] = {0.0, 0.0};
  double PushStartedAt[2] = {-100.0, -100.0};
  float LastArthurYaw[2] = {-1.0f, -1.0f};
  bool bActive = false;
  uint64 LastRequestFrame = 0;
};
