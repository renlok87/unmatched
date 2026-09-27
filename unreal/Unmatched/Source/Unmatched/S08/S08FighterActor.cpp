#include "S08FighterActor.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "GameFramework/PlayerController.h"
#include "Materials/MaterialInterface.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "UObject/ConstructorHelpers.h"

namespace {
UMaterialInterface* LoadSolidMaterial() {
  static UMaterialInterface* Cached = LoadObject<UMaterialInterface>(
      nullptr, TEXT("/Game/S08/M_S08_Solid.M_S08_Solid"));
  if (!Cached) {
    Cached = LoadObject<UMaterialInterface>(
        nullptr, TEXT("/Engine/BasicShapes/BasicShapeMaterial"));
  }
  return Cached;
}
} // namespace

AS08FighterActor::AS08FighterActor() {
  PrimaryActorTick.bCanEverTick = false;
  RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));

  static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeFinder(
      TEXT("/Engine/BasicShapes/Cube.Cube"));
  static ConstructorHelpers::FObjectFinder<UStaticMesh> CylinderFinder(
      TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
  UStaticMesh* Cube = CubeFinder.Object;
  UStaticMesh* Cylinder = CylinderFinder.Object;

  Base = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Base"));
  Base->SetupAttachment(RootComponent);
  Base->SetStaticMesh(Cylinder);
  Base->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
  Base->SetCollisionResponseToChannel(ECC_Visibility, ECR_Block);

  Body = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Body"));
  Body->SetupAttachment(RootComponent);
  Body->SetStaticMesh(Cube);
  Body->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
  Body->SetCollisionResponseToChannel(ECC_Visibility, ECR_Block);

  Ring = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Ring"));
  Ring->SetupAttachment(RootComponent);
  Ring->SetStaticMesh(Cylinder);
  Ring->SetCollisionEnabled(ECollisionEnabled::NoCollision);
  Ring->SetVisibility(false);

  Label = CreateDefaultSubobject<UTextRenderComponent>(TEXT("Label"));
  Label->SetupAttachment(RootComponent);
  Label->SetHorizontalAlignment(EHTA_Center);
  Label->SetTextRenderColor(FColor::White);
  Label->SetWorldSize(26);
  Label->SetCollisionEnabled(ECollisionEnabled::NoCollision);

  HpLabel = CreateDefaultSubobject<UTextRenderComponent>(TEXT("HpLabel"));
  HpLabel->SetupAttachment(RootComponent);
  HpLabel->SetHorizontalAlignment(EHTA_Center);
  HpLabel->SetTextRenderColor(FColor::White);
  HpLabel->SetWorldSize(26);
  HpLabel->SetCollisionEnabled(ECollisionEnabled::NoCollision);
}

void AS08FighterActor::BeginPlay() {
  Super::BeginPlay();
  // Text faces the camera (+Y side, camera yaw -90 looks along -Y).
  Label->SetWorldRotation(FRotator(0.0f, 90.0f, 0.0f));
  HpLabel->SetWorldRotation(FRotator(0.0f, 90.0f, 0.0f));
  if (UMaterialInterface* Solid = LoadSolidMaterial()) {
    Ring->SetMaterial(0, UMaterialInstanceDynamic::Create(Solid, this));
  }
}

void AS08FighterActor::ApplyFighter(const FS08BoardFighter& InFighter,
                                    const FVector& CellCenter, bool bOwn) {
  Fighter = InFighter;
  SetActorLocation(CellCenter);

  // Team-colored base: own = blue, enemy = red (grey-slice distinction).
  // The blue rides an HDR emissive value: the tonemapper dims dark blues
  // much harder than the equally-bright red, washing the team out.
  const FLinearColor TeamColor = bOwn ? FLinearColor(0.02f, 0.25f, 1.5f)
                                      : FLinearColor(0.85f, 0.2f, 0.2f);
  if (UMaterialInterface* Solid = LoadSolidMaterial()) {
    UMaterialInstanceDynamic* BaseMid = UMaterialInstanceDynamic::Create(Solid, this);
    BaseMid->SetVectorParameterValue(TEXT("Tint"), TeamColor);
    Base->SetMaterial(0, BaseMid);
    UMaterialInstanceDynamic* BodyMid = UMaterialInstanceDynamic::Create(Solid, this);
    BodyMid->SetVectorParameterValue(TEXT("Tint"),
                                     FLinearColor(0.62f, 0.62f, 0.65f));
    Body->SetMaterial(0, BodyMid);
    if (UMaterialInstanceDynamic* RingMid =
            Cast<UMaterialInstanceDynamic>(Ring->GetMaterial(0))) {
      RingMid->SetVectorParameterValue(TEXT("Tint"),
                                       FLinearColor(1.0f, 0.85f, 0.2f));
    }
  }

  // Shape distinction: hero = tall box, minion = short box.
  // Labels are two stacked single-line renders (TextRender cannot wrap):
  // name on top, HP below. The old one-line "Name [H] HP/HP" was ~2.3 cells
  // wide at world size 26 and overlapped neighbouring fighters' labels.
  if (Fighter.bIsHero) {
    Body->SetWorldScale3D(FVector(0.6f, 0.6f, 1.2f));
    Body->SetRelativeLocation(FVector(0, 0, 60.0f));
    Label->SetRelativeLocation(FVector(0, 0, 170.0f));
    HpLabel->SetRelativeLocation(FVector(0, 0, 136.0f));
  } else {
    Body->SetWorldScale3D(FVector(0.5f, 0.5f, 0.5f));
    Body->SetRelativeLocation(FVector(0, 0, 25.0f));
    Label->SetRelativeLocation(FVector(0, 0, 102.0f));
    HpLabel->SetRelativeLocation(FVector(0, 0, 68.0f));
  }
  Base->SetWorldScale3D(FVector(0.9f, 0.9f, 0.06f));
  Base->SetRelativeLocation(FVector(0, 0, 3.0f));
  Ring->SetWorldScale3D(FVector(1.15f, 1.15f, 0.04f));
  Ring->SetRelativeLocation(FVector(0, 0, 1.0f));

  // SetupCameraForBoard pulls the camera back to fit bigger boards, which
  // shrinks on-screen text; grow both lines back with the camera distance
  // (2200 uu = the 5x7 reference distance). Caps keep each line inside the
  // 100-uu cell: 0.58 ~ average glyph width as a fraction of world size.
  float BoardScale = 1.0f;
  if (const UWorld* World = GetWorld()) {
    if (const APlayerController* PC = World->GetFirstPlayerController()) {
      if (const APlayerCameraManager* Cam = PC->PlayerCameraManager) {
        BoardScale = FMath::Clamp(Cam->GetCameraLocation().Size() / 2200.0f, 1.0f, 1.4f);
      }
    }
  }
  const float NameFit = 84.0f / (FMath::Max(1, Fighter.Label.Len()) * 0.58f);
  Label->SetWorldSize(FMath::Min(18.0f, NameFit) * FMath::Min(BoardScale, 1.2f));
  HpLabel->SetWorldSize(22.0f * BoardScale);

  Label->SetText(FText::FromString(Fighter.Label));
  HpLabel->SetText(FText::FromString(
      FString::Printf(TEXT("%d/%d"), Fighter.Health, Fighter.MaxHealth)));

  // Death (isDefeated/health<=0): instant hide, no animations (grey slice).
  SetActorHiddenInGame(!Fighter.IsAlive());
  SetActorEnableCollision(Fighter.IsAlive());
}

void AS08FighterActor::SetSelected(bool bSelected) {
  Ring->SetVisibility(bSelected);
}
