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
};
