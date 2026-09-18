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
#include "HighResScreenshot.h"
IMPLEMENT_PRIMARY_GAME_MODULE(FDefaultGameModuleImpl, Unmatched, "Unmatched");
ASmokeGameMode::ASmokeGameMode() { PrimaryActorTick.bCanEverTick = true; DefaultPawnClass = nullptr; }
void ASmokeGameMode::BeginPlay()
{
 Super::BeginPlay(); Smoke = FParse::Param(FCommandLine::Get(), TEXT("S01Smoke"));
 FString Url; GConfig->GetString(TEXT("Unmatched.API"), TEXT("GraphQLUrl"), Url, GGameIni);
 auto* Camera = GetWorld()->SpawnActor<ACameraActor>(FVector(0, 1032.4f, 1474.5f), FRotator(-55,-90,0));
 Camera->GetCameraComponent()->SetFieldOfView(35);
 if (auto* PC = GetWorld()->GetFirstPlayerController()) { PC->SetViewTarget(Camera); PC->bShowMouseCursor = true; }
 UE_LOG(LogTemp, Display, TEXT("S01_SMOKE_READY map=%s api=%s fov=35 pitch=-55 yaw=-90 distance=1800"), *GetWorld()->GetMapName(), *Url);
}
void ASmokeGameMode::Tick(float DeltaSeconds)
{
 Super::Tick(DeltaSeconds); Elapsed += DeltaSeconds;
 if (Smoke && Elapsed > 8 && !Captured) { Captured = true; FScreenshotRequest::RequestScreenshot(TEXT("S01Smoke.png"), false, false); }
 if (Smoke && Elapsed > 12) { UE_LOG(LogTemp, Display, TEXT("S01_SMOKE_COMPLETE elapsed=%f"), Elapsed); FGenericPlatformMisc::RequestExit(false); }
}
