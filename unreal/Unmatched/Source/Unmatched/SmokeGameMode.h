#pragma once
#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "SmokeGameMode.generated.h"
UCLASS()
class ASmokeGameMode : public AGameModeBase
{
 GENERATED_BODY()
public:
 ASmokeGameMode();
 virtual void BeginPlay() override;
 virtual void Tick(float DeltaSeconds) override;
private:
 float Elapsed = 0; bool Smoke = false; bool Captured = false;
 // S05 reference mode (-S05Ref): staged K1/K2/K3 captures, frame stats, root-motion probe.
 // Kept inside the single game mode class: two AGameModeBase-derived UCLASSes in the
 // primary module crash packaged Development builds during UClass registration (session
 // 2026-09-25 bisect: any second GameModeBase subclass reproduces it, an AActor subclass does not).
 void EnterK1();
 void EnterK2();
 void EnterK3();
 void LogFigurePose(const TCHAR* State);
 void CaptureHighRes(const FString& Name);
 void LogFrameStats();
 void StartRootMotionTest();
 void FinishRootMotionTest();
 void CheckMedusaClipRootMotion();
 bool Ref = false;
 bool NoK2Title = false;
 class ACameraActor* RefCamera = nullptr;
 TArray<class ASkeletalMeshActor*> Figures;
 TArray<class AActor*> K3Actors;
 class AActor* K2TitleActor = nullptr;
 class AStaticMeshActor* MarkerSelection = nullptr;
 class AStaticMeshActor* MarkerTarget = nullptr;
 class ASkeletalMeshActor* RootMotionProbe = nullptr;
 FVector RootMotionStart = FVector::ZeroVector;
 int32 StatFrames = 0;
 float StatTotalMs = 0;
 float StatMinMs = 1e9;
 float StatMaxMs = 0;
 bool ShotK1 = false;
 bool ShotK2 = false;
 bool ShotK3 = false;
 bool K3Entered = false;
 bool K3PoseLogged = false;
 bool StatsLogged = false;
 bool MedusaRmLogged = false;
 bool RootMotionStarted = false;
 bool RootMotionDone = false;
 bool RootMotionLogged = false;
 int32 RootMotionRMFrames = 0;
};
