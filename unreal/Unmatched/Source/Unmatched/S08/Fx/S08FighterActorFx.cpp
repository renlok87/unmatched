// VS-6 F3: the bench hooks of AS08FighterActor for the death FX (kept out of the hot S08FighterActor.cpp).
#include "../S08FighterActor.h"

#include "Components/SkeletalMeshComponent.h"
#include "Materials/MaterialInterface.h"
#include "../S08HeroesV2.h"

bool AS08FighterActor::BenchDissolveAt(float Progress) {
  using namespace S08HeroesV2;
  if (!HeroV2Spec || !ArtBody || !bHeroV2Visual) return false;
  UMaterialInterface* Mic = LoadObject<UMaterialInterface>(nullptr, *DissolveMaterialPath(*HeroV2Spec, Look));
  if (!Mic) return false;
  for (int32 Slot = 0; Slot < ArtBody->GetNumMaterials(); ++Slot) ArtBody->SetMaterial(Slot, Mic);
  ApplyHeroMaterialMids();  // AN-32: the fix rides the dissolve MIC too
  SetDissolve(ArtBody, ArtBase, FMath::Clamp(Progress, 0.0f, 1.0f), DissolveStyle());
  // progress 1 clips every pixel of the body (the pedestal greys out with the progress like the death); the actor stays
  // visible so the K2 bench view keeps its framing on the figure's cell
  return true;
}
