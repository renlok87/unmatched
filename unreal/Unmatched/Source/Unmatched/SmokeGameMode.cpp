#include "SmokeGameMode.h"
#include "Modules/ModuleManager.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "GameFramework/PlayerController.h"
#include "Misc/ConfigCacheIni.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Engine/GameViewportClient.h"
#include "Engine/Engine.h"
#include "Engine/SkeletalMesh.h"
#include "ReferenceSkeleton.h"
#include "Engine/StaticMeshActor.h"
#include "Animation/SkeletalMeshActor.h"
#include "Components/SkeletalMeshComponent.h"
#include "Animation/AnimSequence.h"
#include "Animation/AnimSingleNodeInstance.h"
#include "HighResScreenshot.h"
#include "EngineUtils.h"
IMPLEMENT_PRIMARY_GAME_MODULE(FDefaultGameModuleImpl, Unmatched, "Unmatched");
ASmokeGameMode::ASmokeGameMode() { PrimaryActorTick.bCanEverTick = true; DefaultPawnClass = nullptr; }
void ASmokeGameMode::BeginPlay()
{
 Super::BeginPlay(); Smoke = FParse::Param(FCommandLine::Get(), TEXT("S01Smoke"));
 Ref = FParse::Param(FCommandLine::Get(), TEXT("S05Ref"));
 Elapsed = 0;
 FString Url; GConfig->GetString(TEXT("Unmatched.API"), TEXT("GraphQLUrl"), Url, GGameIni);
 // K1 camera per 03-art-direction.md S2 proposal: perspective, FOV 35, pitch -55, yaw -90, 1800 uu.
 // Spawned unconditionally: the S01 baseline (b778726) spawned the same camera on every map,
 // so -S05Ref changes nothing about the S01 view target.
 RefCamera = GetWorld()->SpawnActor<ACameraActor>(FVector(0, 1032.4f, 1474.5f), FRotator(-55,-90,0));
 RefCamera->GetCameraComponent()->SetFieldOfView(35);
 if (auto* PC = GetWorld()->GetFirstPlayerController()) { PC->SetViewTarget(RefCamera); PC->bShowMouseCursor = true; }
 UE_LOG(LogTemp, Display, TEXT("S01_SMOKE_READY map=%s api=%s fov=35 pitch=-55 yaw=-90 distance=1800"), *GetWorld()->GetMapName(), *Url);
 if (!Ref)
 {
  return;
 }
 UE_LOG(LogTemp, Display, TEXT("S05_REF_READY map=%s active=1"), *GetWorld()->GetMapName());
 for (TActorIterator<ASkeletalMeshActor> It(GetWorld()); It; ++It)
 {
  if (It->ActorHasTag(TEXT("s05_cookref"))) continue;
  Figures.Add(*It);
 }
 for (TActorIterator<AStaticMeshActor> It(GetWorld()); It; ++It)
 {
  if (It->ActorHasTag(TEXT("s05_marker_selection"))) MarkerSelection = *It;
  if (It->ActorHasTag(TEXT("s05_marker_target"))) MarkerTarget = *It;
 }
 for (TActorIterator<AActor> It(GetWorld()); It; ++It)
 {
  if (It->ActorHasTag(TEXT("s05_k3"))) K3Actors.Add(*It);
  // The K2 hero title is the 's05_label' TextRender at world (0,-50,65.2) (import report:
  // f-0-hero label_world; the other f-0 labels sit at x=100 / y=-150). Addressed by tag +
  // position so the -S05NoK2Title diagnostic flag can hide EXACTLY this actor for the real
  // no-title negative capture; every other scene object is untouched.
  if (It->ActorHasTag(TEXT("s05_label")) && FMath::Abs(It->GetActorLocation().X) < 1.0f &&
      FMath::Abs(It->GetActorLocation().Y + 50.0f) < 1.0f)
  {
   K2TitleActor = *It;
  }
 }
 NoK2Title = FParse::Param(FCommandLine::Get(), TEXT("S05NoK2Title"));
 UE_LOG(LogTemp, Display, TEXT("S05_REF_SCENE figures=%d selection=%d target=%d k3_actors=%d"), Figures.Num(),
        MarkerSelection ? 1 : 0, MarkerTarget ? 1 : 0, K3Actors.Num());
}
void ASmokeGameMode::CaptureHighRes(const FString& Name)
{
 // -RenderOffscreen clamps the backbuffer to ~888x500, so FScreenshotRequest::RequestScreenshot
 // cannot reach 1920x1080 (the 14:52 run captured K frames at 888x500; the single 1920x1080 file
 // came from the one-shot HighResScreenshotConfig). The HighResShot exec re-renders into an
 // absolute-resolution target, and filename= keeps the exact name (no numeric suffix).
 if (GEngine && GEngine->GameViewport)
 {
  GEngine->GameViewport->Exec(GetWorld(),
   *FString::Printf(TEXT("HighResShot filename=\"%s\" 1920x1080"), *Name), *GLog);
 }
}
void ASmokeGameMode::EnterK1()
{
 if (RefCamera)
 {
  RefCamera->SetActorLocation(FVector(0, 1032.4f, 1474.5f));
  RefCamera->SetActorRotation(FRotator(-55, -90, 0));
  // K2 narrows the FOV for its close-up; every other view restores the spec camera (FOV 35).
  RefCamera->GetCameraComponent()->SetFieldOfView(35.0f);
 }
}
void ASmokeGameMode::EnterK2()
{
 // Single-hero isolation close-up (review P1-2: 500 uu at pitch -55 kept 3+ neighbor Medusa
 // meshes in frame with clipped bodies). FOV 20 at 300 uu gives a 105.8 uu frame height at the
 // target plane; the nearest neighbor figure center sits ~82 uu off the view axis (100 uu cell
 // pitch * cos 35), outside the 52.9 uu half-height, so only the hero figure fits fully. The
 // 0.65-1.6x zoom range of the camera proposal stays open (Q-302).
 // Target z 26 -> 32 (2026-09-25): at z=26 the hero label top (fig_z+62+6) projected ~2 uu past
 // the frame top edge and visually touched it; +6 uu of target height puts the label top ~1.5 uu
 // inside the half-height while the figure base keeps a ~16 uu bottom margin.
 const FVector Target(0, -50, 32);
 if (RefCamera)
 {
  RefCamera->GetCameraComponent()->SetFieldOfView(20.0f);
  RefCamera->SetActorLocation(Target + FVector(0, 1032.4f, 1474.5f) * (300.0f / 1800.0f));
  RefCamera->SetActorRotation(FRotator(-55, -90, 0));
 }
 // S05_K2_TITLE proves the -S05NoK2Title diagnostic flag is scoped to the negative capture:
 // a normal run logs actor=1 hidden=0 flag=0 (title rendered); the negative run logs
 // suppressed=1 after hiding ONLY this TextRender actor.
 UE_LOG(LogTemp, Display, TEXT("S05_K2_TITLE actor=%d flag=%d"), K2TitleActor ? 1 : 0, NoK2Title ? 1 : 0);
 if (NoK2Title && K2TitleActor)
 {
  K2TitleActor->SetActorHiddenInGame(true);
  UE_LOG(LogTemp, Display, TEXT("S05_K2_TITLE suppressed=1 (diagnostic negative capture)"));
 }
}
void ASmokeGameMode::LogFigurePose(const TCHAR* State)
{
 // P0 diagnostic + P2 evidence: per staged figure, log the component bounds, the bone-0 ref-pose
 // scale, component-space bone transforms and the Weapon/Head socket world transforms. The bounds
 // tell whether the posed mesh is on the board (extent ~26uu), collapsed to a point or thrown far
 // away; the sockets prove (or disprove) that cooked attachment follows the played pose.
 for (auto* Figure : Figures)
 {
  if (!Figure || Figure->ActorHasTag(TEXT("s05_rm_probe")) || Figure->ActorHasTag(TEXT("s05_cookref"))) continue;
  if (!Figure->ActorHasTag(TEXT("s05_attacker")) && !Figure->ActorHasTag(TEXT("s05_target"))) continue;
  USkeletalMeshComponent* Comp = Figure->GetSkeletalMeshComponent();
  if (!Comp || !Comp->GetSkinnedAsset()) continue;
  const FString RoleStr = Figure->ActorHasTag(TEXT("s05_attacker")) ? TEXT("attacker") : TEXT("target");
  FString Line = FString::Printf(TEXT("S05_K3_POSE state=%s role=%s"), State, *RoleStr);
  const FBoxSphereBounds& B = Comp->Bounds;
  Line += FString::Printf(TEXT(" bounds_origin=(%.1f,%.1f,%.1f) bounds_extent=(%.1f,%.1f,%.1f)"),
                          B.Origin.X, B.Origin.Y, B.Origin.Z, B.BoxExtent.X, B.BoxExtent.Y, B.BoxExtent.Z);
  if (const USkeleton* Skel = Comp->GetSkinnedAsset()->GetSkeleton())
  {
   const FReferenceSkeleton& RefSkel = Skel->GetReferenceSkeleton();
   if (RefSkel.GetNum() > 0)
   {
    const FTransform& B0 = RefSkel.GetRefBonePose()[0];
    Line += FString::Printf(TEXT(" bone0=%s ref_scale=(%.1f,%.1f,%.1f) bones=%d"),
                            *RefSkel.GetBoneName(0).ToString(), B0.GetScale3D().X, B0.GetScale3D().Y, B0.GetScale3D().Z, RefSkel.GetNum());
   }
  }
  if (UAnimSingleNodeInstance* Node = Comp->GetSingleNodeInstance())
  {
   Line += FString::Printf(TEXT(" anim_pos=%.3f"), Node->GetCurrentTime());
  }
  const TCHAR* Bones[] = { TEXT("root"), TEXT("hips"), TEXT("spine"), TEXT("head") };
  for (const TCHAR* Bn : Bones)
  {
   const FName N(Bn);
   const int32 Idx = Comp->GetBoneIndex(N);
   if (Idx == INDEX_NONE) continue;
   const FVector CS = Comp->GetBoneTransform(Idx).GetTranslation() - Comp->GetComponentLocation();
   Line += FString::Printf(TEXT(" %s_cs=(%.1f,%.1f,%.1f)"), Bn, CS.X, CS.Y, CS.Z);
  }
  const FTransform W = Comp->GetSocketTransform(FName(TEXT("Weapon")), RTS_World);
  const FTransform H = Comp->GetSocketTransform(FName(TEXT("Head")), RTS_World);
  Line += FString::Printf(TEXT(" socket_Weapon=(%.1f,%.1f,%.1f) socket_Head=(%.1f,%.1f,%.1f)"),
                          W.GetTranslation().X, W.GetTranslation().Y, W.GetTranslation().Z,
                          H.GetTranslation().X, H.GetTranslation().Y, H.GetTranslation().Z);
  UE_LOG(LogTemp, Display, TEXT("%s"), *Line);
 }
}
void ASmokeGameMode::EnterK3()
{
 // Staged combat arrangement (not live combat): attacker f-0-hero (2,2) fires at f-1-hero (2,3).
 // Attacker frozen mid LungeAttack, target frozen mid HitReact, gameplay markers + attack beam +
 // staged card quad + screen-space inspector HUD revealed.
 // NOTE: the legacy FBX animation importer names sequences "<Dest>_Anim" (see s05_import_scene.py).
 EnterK1();
 LogFigurePose(TEXT("pre_switch"));
 // K3 inspector is SCENE-space now (s05_k3_hud-tagged quad + TextRender actors, built by
 // s05_import_scene.py): the HighResShot exec re-renders the scene without the Slate/UMG layer,
 // so the previous screen-space WBP_K3Hud never appeared in any captured frame (measured
 // 2026-09-25: panel-region pixels were identical in K1 and K3 while the log said created=1).
 // This marker counts the revealed scene actors, NOT visibility — visibility is gated
 // pixel-wise (K3-vs-K1 differential) in s05_validate.ps1.
 int32 HudActors = 0;
 for (AActor* Actor : K3Actors)
 {
  if (Actor && Actor->ActorHasTag(TEXT("s05_k3_hud"))) HudActors++;
 }
 UE_LOG(LogTemp, Display, TEXT("S05_K3_HUD panel=scene hud_actors=%d"), HudActors);
 if (MarkerSelection) MarkerSelection->SetActorHiddenInGame(false);
 if (MarkerTarget) MarkerTarget->SetActorHiddenInGame(false);
 for (AActor* Actor : K3Actors)
 {
  if (Actor) Actor->SetActorHiddenInGame(false);
 }
 auto* Lunge = LoadObject<UAnimSequence>(nullptr, TEXT("/Game/S05/Anims/AM_Medusa_LungeAttack_Anim.AM_Medusa_LungeAttack_Anim"));
 auto* Hit = LoadObject<UAnimSequence>(nullptr, TEXT("/Game/S05/Anims/AM_Medusa_HitReact_Anim.AM_Medusa_HitReact_Anim"));
 for (auto* Figure : Figures)
 {
  if (!Figure || Figure->ActorHasTag(TEXT("s05_rm_probe")) || Figure->ActorHasTag(TEXT("s05_cookref"))) continue;
  USkeletalMeshComponent* Comp = Figure->GetSkeletalMeshComponent();
  if (!Comp || !Comp->GetSkinnedAsset()) continue;
  UAnimSequence* Seq = Figure->ActorHasTag(TEXT("s05_target")) ? Hit : (Figure->ActorHasTag(TEXT("s05_attacker")) ? Lunge : nullptr);
  if (!Seq) continue;
  Comp->SetAnimationMode(EAnimationMode::AnimationSingleNode);
  Comp->PlayAnimation(Seq, false);
  if (UAnimSingleNodeInstance* Node = Comp->GetSingleNodeInstance())
  {
   Node->SetPlayRate(0.0f);
   Node->SetPosition(Seq == Lunge ? 0.29f : 0.16f, false);
  }
 }
 LogFigurePose(TEXT("post_set"));
}
void ASmokeGameMode::CheckMedusaClipRootMotion()
{
 // ART-004 evidence: the four Medusa clips must carry NO root motion (only RM_Test deliberately
 // does). Extract each clip's bone-0 track directly and log the end-vs-start delta.
 MedusaRmLogged = true;
 const TCHAR* Names[4] = { TEXT("AM_Medusa_Idle"), TEXT("AM_Medusa_LungeAttack"),
                           TEXT("AM_Medusa_HitReact"), TEXT("AM_Medusa_DeathSettle") };
 FString Line = TEXT("S05_MEDUSA_RM");
 for (const TCHAR* N : Names)
 {
  UAnimSequence* Seq = LoadObject<UAnimSequence>(nullptr, *FString::Printf(TEXT("/Game/S05/Anims/%s_Anim.%s_Anim"), N, N));
  if (!Seq)
  {
   UE_LOG(LogTemp, Warning, TEXT("S05_MEDUSA_RM %s=LOAD_FAILED"), N);
   Line += FString::Printf(TEXT(" %s=LOAD_FAILED"), N);
   continue;
  }
  FAnimExtractContext Ctx;
  Ctx.bExtractRootMotion = true;
  Ctx.CurrentTime = 0.0;
  const FTransform T0 = Seq->ExtractRootTrackTransform(Ctx, nullptr);
  Ctx.CurrentTime = Seq->GetPlayLength();
  const FTransform T1 = Seq->ExtractRootTrackTransform(Ctx, nullptr);
  const FVector D = (T1.GetTranslation() - T0.GetTranslation());
  Line += FString::Printf(TEXT(" %s=(%.2f,%.2f,%.2f)"), N, D.X, D.Y, D.Z);
 }
 UE_LOG(LogTemp, Display, TEXT("%s"), *Line);
}
void ASmokeGameMode::LogFrameStats()
{
 UE_LOG(LogTemp, Display,
        TEXT("S05_FRAME_STATS frames=%d avg_ms=%.3f min_ms=%.3f max_ms=%.3f note=dev-machine-not-target-D07"),
        StatFrames, StatFrames ? StatTotalMs / StatFrames : 0.0f, StatMinMs, StatMaxMs);
}
void ASmokeGameMode::StartRootMotionTest()
{
 // ART-001 skeletal check: play the mannequin RM_Test clip and measure the real displacement.
 // Blender -Y forward lands on UE +Y in this import chain (Q-311), so the expected axis is +Y here.
 // RootMotionDone is set first: a missing asset must log SKIP once, not spam every frame.
 RootMotionDone = true;
 auto* Mesh = LoadObject<USkeletalMesh>(nullptr, TEXT("/Game/S05/Meshes/SM_S05_Mannequin.SM_S05_Mannequin"));
 auto* Seq = LoadObject<UAnimSequence>(nullptr, TEXT("/Game/S05/Anims/AM_RM_Test_Anim.AM_RM_Test_Anim"));
 if (!Mesh || !Seq)
 {
  UE_LOG(LogTemp, Warning, TEXT("S05_ROOTMOTION_SKIP mesh_or_sequence_missing"));
  return;
 }
 FActorSpawnParameters Params;
 Params.Name = TEXT("S05_RM_Probe");
 // ART-001 evidence: sample the root-bone track directly. If T0==Tend the clip itself carries
 // no bone-0 motion (import side); if they differ, any zero delta is on the consume side.
 {
  FAnimExtractContext Ctx;
  Ctx.bExtractRootMotion = true;
  Ctx.CurrentTime = 0.0;
  const FTransform T0 = Seq->ExtractRootTrackTransform(Ctx, nullptr);
  Ctx.CurrentTime = Seq->GetPlayLength() * 0.5;
  const FTransform TM = Seq->ExtractRootTrackTransform(Ctx, nullptr);
  Ctx.CurrentTime = Seq->GetPlayLength();
  const FTransform T1 = Seq->ExtractRootTrackTransform(Ctx, nullptr);
  const auto Tr = [](const FTransform& T) { return T.GetTranslation().ToString(); };
  UE_LOG(LogTemp, Display, TEXT("S05_RM_CLIP root_track t0=%s mid=%s end=%s enable_rm=%d len=%.3fs"),
         *Tr(T0), *Tr(TM), *Tr(T1), Seq->HasRootMotion() ? 1 : 0, Seq->GetPlayLength());
 }
 RootMotionProbe = GetWorld()->SpawnActor<ASkeletalMeshActor>(FVector(-800, 0, 0), FRotator(0, 0, 0), Params);
 if (!RootMotionProbe)
 {
  UE_LOG(LogTemp, Warning, TEXT("S05_ROOTMOTION_SKIP spawn_failed"));
  return;
 }
 RootMotionProbe->Tags.Add(TEXT("s05_rm_probe"));
 // A 100uu clip displacing the probe by exactly 10000uu points at a x100 scale hiding in the
 // skeleton root ref pose (FBX unit conversion); log it as evidence.
 if (const FReferenceSkeleton* RefSkel = &Mesh->GetRefSkeleton(); RefSkel->GetNum() > 0)
 {
  UE_LOG(LogTemp, Display, TEXT("S05_RM_SKEL bone0=%s refpose_scale=%s bones=%d"),
         *RefSkel->GetBoneName(0).ToString(), *RefSkel->GetRefBonePose()[0].GetScale3D().ToString(), RefSkel->GetNum());
 }
 USkeletalMeshComponent* Comp = RootMotionProbe->GetSkeletalMeshComponent();
 Comp->SetSkeletalMesh(Mesh);
 // The probe sits off-camera (x=-800); with the default OnlyTickPoseWhenRendered its pose
 // would never advance offscreen.
 Comp->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
 Comp->SetAnimationMode(EAnimationMode::AnimationSingleNode);
 Comp->PlayAnimation(Seq, false);
 if (UAnimSingleNodeInstance* Node = Comp->GetSingleNodeInstance())
 {
  Node->SetRootMotionMode(ERootMotionMode::RootMotionFromEverything);
  Node->SetPlayRate(1.0f);
 }
 RootMotionStart = RootMotionProbe->GetActorLocation();
 RootMotionStarted = true;
 UE_LOG(LogTemp, Display, TEXT("S05_ROOTMOTION_START pos=%s expected=+100uu_along_Y"), *RootMotionStart.ToString());
}
void ASmokeGameMode::FinishRootMotionTest()
{
 if (!RootMotionProbe || !RootMotionStarted)
 {
  return;
 }
 const FVector Delta = RootMotionProbe->GetActorLocation() - RootMotionStart;
 UE_LOG(LogTemp, Display, TEXT("S05_ROOTMOTION_RESULT delta=(x=%.2f y=%.2f z=%.2f) rm_frames=%d"),
        Delta.X, Delta.Y, Delta.Z, RootMotionRMFrames);
 RootMotionLogged = true;
}
void ASmokeGameMode::Tick(float DeltaSeconds)
{
 Super::Tick(DeltaSeconds); Elapsed += DeltaSeconds;
 if (Ref)
 {
  // warmup, then three staged captures (03-art-direction.md K-1/K-2/K-3)
  if (!ShotK1 && Elapsed > 2.0f)
  {
   ShotK1 = true;
   CaptureHighRes(TEXT("S05_K1_overview"));
  }
  if (!ShotK2 && Elapsed > 3.5f)
  {
   ShotK2 = true;
   EnterK2();
  }
  if (ShotK2 && !ShotK3 && Elapsed > 5.0f)
  {
   CaptureHighRes(TEXT("S05_K2_closeup"));
   ShotK3 = true;
  }
  // K3Entered guard: StatFrames stays 0 until t=8.0, so without the flag EnterK3() (and its
  // S05_K3_HUD log marker + PlayAnimation restart) ran on every tick for two full seconds.
  if (ShotK3 && Elapsed > 6.0f && !K3Entered)
  {
   K3Entered = true;
   EnterK3();
  }
  if (K3Entered && !K3PoseLogged && Elapsed > 6.6f)
  {
   K3PoseLogged = true;
   LogFigurePose(TEXT("after_eval"));
  }
  if (ShotK3 && Elapsed > 8.0f && StatFrames == 0)
  {
   CaptureHighRes(TEXT("S05_K3_combat"));
  }
  if (Elapsed > 8.0f && Elapsed < 13.0f)
  {
   const float Ms = DeltaSeconds * 1000.0f;
   StatFrames++;
   StatTotalMs += Ms;
   StatMinMs = FMath::Min(StatMinMs, Ms);
   StatMaxMs = FMath::Max(StatMaxMs, Ms);
  }
  if (!StatsLogged && Elapsed >= 13.0f && StatFrames > 0)
  {
   StatsLogged = true;
   LogFrameStats();
  }
  if (!MedusaRmLogged && StatsLogged)
  {
   CheckMedusaClipRootMotion();
  }
  if (!RootMotionDone && MedusaRmLogged)
  {
   StartRootMotionTest();
  }
  if (RootMotionStarted && !RootMotionLogged)
  {
   // Root motion is extracted per frame by the anim instance, but only ACharacter/CharacterMovement
   // consumes it — a bare ASkeletalMeshActor never moves on its own (the 10:02 packaged run logged
   // delta=0 with the clips loading fine). Consume it here and apply it to the probe; the
   // translation is component-local ("animation root motion is always local").
   if (RootMotionProbe)
   {
    if (USkeletalMeshComponent* Comp = RootMotionProbe->GetSkeletalMeshComponent())
    {
     FRootMotionMovementParams RM = Comp->ConsumeRootMotion();
     if (RM.bHasRootMotion)
     {
      const FVector Local = RM.GetRootMotionTransform().GetTranslation();
      RootMotionProbe->AddActorWorldOffset(RootMotionProbe->GetActorQuat().RotateVector(Local));
      RootMotionRMFrames++;
      if (RootMotionRMFrames <= 3 || (RootMotionRMFrames % 300) == 0)
      {
       UE_LOG(LogTemp, Display, TEXT("S05_RM_CONSUME frame=%d step=(%.3f %.3f %.3f) pos=%s"),
              RootMotionRMFrames, Local.X, Local.Y, Local.Z, *RootMotionProbe->GetActorLocation().ToString());
      }
     }
    }
   }
  }
  if (RootMotionStarted && !RootMotionLogged && Elapsed > 15.0f)
  {
   FinishRootMotionTest();
  }
  if (RootMotionDone && !RootMotionStarted)
  {
   RootMotionLogged = true;
  }
  if (RootMotionLogged && Elapsed > 16.0f)
  {
   UE_LOG(LogTemp, Display, TEXT("S05_REF_COMPLETE elapsed=%.2f"), Elapsed);
   FGenericPlatformMisc::RequestExit(false);
  }
  return;
 }
 if (Smoke && Elapsed > 8 && !Captured) { Captured = true; FScreenshotRequest::RequestScreenshot(TEXT("S01Smoke.png"), false, false); }
 if (Smoke && Elapsed > 12) { UE_LOG(LogTemp, Display, TEXT("S01_SMOKE_COMPLETE elapsed=%f"), Elapsed); FGenericPlatformMisc::RequestExit(false); }
}
