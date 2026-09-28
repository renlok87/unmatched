// GD-030 (TASK-021): grey mannequin for one fighter. Body shape separates
// hero (tall box) from minion (short box); base ring color separates own
// (blue) from enemy (red); a text label carries the numbered name.
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "S08BoardModel.h"
#include "S08FighterActor.generated.h"

class UStaticMeshComponent;
class USkeletalMeshComponent;
class UTextRenderComponent;
class UMaterialInstanceDynamic;

UCLASS()
class UNMATCHED_API AS08FighterActor : public AActor {
  GENERATED_BODY()

public:
  AS08FighterActor();

  /** Positions the mannequin at the cell center (Z=0) and applies the
   *  grey-slice visual distinctions. */
  void ApplyFighter(const FS08BoardFighter& Fighter, const FVector& CellCenter,
                    bool bOwn, bool bArtPreview);
  const FS08BoardFighter& GetFighter() const { return Fighter; }
  const FString& GetFighterId() const { return Fighter.Id; }

  void SetSelected(bool bSelected);

protected:
  virtual void BeginPlay() override;

private:
  UPROPERTY()
  TObjectPtr<UStaticMeshComponent> Base;

  UPROPERTY()
  TObjectPtr<UStaticMeshComponent> Body;

  UPROPERTY()
  TObjectPtr<UTextRenderComponent> Label;

  UPROPERTY()
  TObjectPtr<UTextRenderComponent> HpLabel;

  UPROPERTY()
  TObjectPtr<UStaticMeshComponent> Ring;

  UPROPERTY()
  TObjectPtr<USkeletalMeshComponent> ArtBody;

  UPROPERTY()
  TObjectPtr<UStaticMeshComponent> ArtBase;

  UPROPERTY()
  TObjectPtr<UStaticMeshComponent> ArtPlaceholder;

  FS08BoardFighter Fighter;
};
