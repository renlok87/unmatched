#include "S08FighterActor.h"
#include "S08TraceLog.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/StaticMeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "Components/TextRenderComponent.h"
#include "GameFramework/PlayerController.h"
#include "Materials/MaterialInterface.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
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

  TargetRing = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("TargetRing"));
  TargetRing->SetupAttachment(RootComponent);
  TargetRing->SetCollisionEnabled(ECollisionEnabled::NoCollision);
  TargetRing->SetVisibility(false);

  ArtBody = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("ArtBody"));
  ArtBody->SetupAttachment(RootComponent);
  ArtBody->SetCollisionEnabled(ECollisionEnabled::NoCollision);
  ArtBody->SetVisibility(false);

  ArtBase = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("ArtBase"));
  ArtBase->SetupAttachment(RootComponent);
  ArtBase->SetCollisionEnabled(ECollisionEnabled::NoCollision);
  ArtBase->SetVisibility(false);

  ArtPlaceholder = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("ArtPlaceholder"));
  ArtPlaceholder->SetupAttachment(RootComponent);
  ArtPlaceholder->SetCollisionEnabled(ECollisionEnabled::NoCollision);
  ArtPlaceholder->SetVisibility(false);

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
  if (FParse::Param(FCommandLine::Get(), TEXT("ArtPreview"))) {
    if (UStaticMesh* ArtRing = LoadObject<UStaticMesh>(nullptr,
            TEXT("/Game/ArtTests/ARTMarkers/Meshes/SM_Marker_SelectionRing"))) {
      Ring->SetStaticMesh(ArtRing);
      bArtSelectionRingLoaded = true;
    }
    if (UStaticMesh* ArtTarget = LoadObject<UStaticMesh>(nullptr,
            TEXT("/Game/ArtTests/ARTMarkers/Meshes/SM_Marker_TargetRing"))) {
      TargetRing->SetStaticMesh(ArtTarget);
      bArtTargetRingLoaded = true;
    }
  }
  // Text faces the camera (+Y side, camera yaw -90 looks along -Y).
  Label->SetWorldRotation(FRotator(0.0f, 90.0f, 0.0f));
  HpLabel->SetWorldRotation(FRotator(0.0f, 90.0f, 0.0f));
  if (UMaterialInterface* Solid = LoadSolidMaterial()) {
    Ring->SetMaterial(0, UMaterialInstanceDynamic::Create(Solid, this));
    UMaterialInstanceDynamic* TargetMid = UMaterialInstanceDynamic::Create(Solid, this);
    TargetMid->SetVectorParameterValue(TEXT("Tint"), FLinearColor(1.4f, 0.18f, 0.06f));
    TargetRing->SetMaterial(0, TargetMid);
  }
}

void AS08FighterActor::ApplyFighter(const FS08BoardFighter& InFighter,
                                    const FVector& CellCenter, bool bOwn,
                                    bool bArtPreview) {
  Fighter = InFighter;
  SetActorLocation(CellCenter);

  bool bVisualArt = false;
  bool bVisualBlockout = false;
  // The candidate is a Medusa sculpt, not a substitute for Arthur, Merlin or
  // the three Harpies. Keep their honest grey blockouts in this pilot.
  const bool bMedusaCandidate = bArtPreview && Fighter.bIsHero &&
      Fighter.Name.Equals(TEXT("Medusa"), ESearchCase::IgnoreCase);
  if (bMedusaCandidate) {
    USkeletalMesh* Mesh = LoadObject<USkeletalMesh>(nullptr,
        TEXT("/Game/ArtPreview/Medusa/Meshes/SK_Medusa_FaceNeck_v2Candidate"));
    UStaticMesh* Pedestal = LoadObject<UStaticMesh>(nullptr,
        TEXT("/Game/ArtPreview/Medusa/Meshes/SM_Medusa_Base_v2Candidate"));
    UMaterialInterface* TeamMaterial = LoadObject<UMaterialInterface>(nullptr,
        bOwn ? TEXT("/Game/ArtPreview/Medusa/Materials/MI_Medusa_Blue")
             : TEXT("/Game/ArtPreview/Medusa/Materials/MI_Medusa_Red"));
    bVisualArt = Mesh && Mesh->GetSkeleton() && Pedestal && TeamMaterial;
    if (bVisualArt) {
      ArtBody->SetSkeletalMeshAsset(Mesh);
      ArtBase->SetStaticMesh(Pedestal);
      for (int32 Slot = 0; Slot < 2; ++Slot) ArtBody->SetMaterial(Slot, TeamMaterial);
      ArtBase->SetMaterial(0, TeamMaterial);
      // The 5x6 board's negative-Y side faces +Y; the far side faces -Y.
      ArtBody->SetRelativeRotation(FRotator(0, CellCenter.Y < 0 ? 0 : 180, 0));
      ArtBase->SetRelativeRotation(FRotator(0, CellCenter.Y < 0 ? 0 : 180, 0));
      const float FigureScale = Fighter.bIsHero ? 1.0f : 0.78f;
      ArtBody->SetRelativeScale3D(FVector(FigureScale));
      ArtBase->SetRelativeScale3D(FVector(FigureScale));
    }
  }
  if (bArtPreview && !bMedusaCandidate) {
    const TCHAR* MeshPath = nullptr;
    if (Fighter.Name.Equals(TEXT("King Arthur"), ESearchCase::IgnoreCase)) {
      MeshPath = TEXT("/Game/ArtTests/ART003/Meshes/SM_ART003_Arthur");
    } else if (Fighter.Name.Equals(TEXT("Merlin"), ESearchCase::IgnoreCase)) {
      MeshPath = TEXT("/Game/ArtTests/ART003/Meshes/SM_ART003_Merlin");
    } else if (Fighter.Name.Equals(TEXT("Harpies"), ESearchCase::IgnoreCase)) {
      MeshPath = TEXT("/Game/ArtTests/ART003/Meshes/SM_ART003_Harpy");
    }
    if (MeshPath) {
      if (UStaticMesh* PreviewMesh = LoadObject<UStaticMesh>(nullptr, MeshPath)) {
        ArtPlaceholder->SetStaticMesh(PreviewMesh);
        ArtPlaceholder->SetRelativeRotation(
            FRotator(0, CellCenter.Y < 0 ? 0 : 180, 0));
        bVisualBlockout = true;
      }
    }
  }
  const bool bArtFigure = bVisualArt || bVisualBlockout;
  Body->SetVisibility(!bArtFigure);
  ArtBody->SetVisibility(bVisualArt);
  ArtBase->SetVisibility(bVisualArt);
  ArtPlaceholder->SetVisibility(bVisualBlockout);
  if (bArtPreview && Fighter.Name.Contains(TEXT("Medusa"))) {
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW fighter=%s hero=%d eligible=%d visual=%d mesh=%s"),
        *Fighter.Name, Fighter.bIsHero ? 1 : 0, bMedusaCandidate ? 1 : 0,
        bVisualArt ? 1 : 0,
        ArtBody->GetSkeletalMeshAsset() ?
            *ArtBody->GetSkeletalMeshAsset()->GetName() : TEXT("none")));
  }

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
  TargetRing->SetRelativeScale3D(FVector(Fighter.bIsHero ? 1.0f : 0.78f));
  TargetRing->SetRelativeLocation(FVector::ZeroVector);
  if (bArtFigure) {
    // The 30-uu pedestal remains a separate visual mesh. The original
    // cylinders are still team/selection feedback and query-only hit areas.
    const float FigureScale = Fighter.bIsHero ? 1.0f : 0.78f;
    Base->SetWorldScale3D(FVector(.4f * FigureScale, .4f * FigureScale, .02f));
    Base->SetRelativeLocation(FVector(0, 0, -1.0f));
    if (bArtSelectionRingLoaded) {
      // The authored mesh is already Ø40 uu and hollow, with its own Z offset.
      Ring->SetWorldScale3D(FVector(FigureScale));
      Ring->SetRelativeLocation(FVector::ZeroVector);
    } else {
      Ring->SetWorldScale3D(FVector(.47f * FigureScale, .47f * FigureScale, .02f));
      Ring->SetRelativeLocation(FVector(0, 0, .5f));
    }
    Label->SetRelativeLocation(FVector(0, 0, Fighter.bIsHero ? 82.0f : 65.0f));
    HpLabel->SetRelativeLocation(FVector(0, 0, Fighter.bIsHero ? 66.0f : 52.0f));
  }

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
  BaseNameWorldSize = FMath::Min(18.0f, NameFit) * FMath::Min(BoardScale, 1.2f);
  BaseHpWorldSize = 22.0f * BoardScale;
  BaseNameHeight = Label->GetRelativeLocation().Z;
  BaseHpHeight = HpLabel->GetRelativeLocation().Z;
  LastLabelRatio = -1.0f;
  SetLabelZoomRatio(1.0f, false);

  Label->SetText(FText::FromString(Fighter.Label));
  HpLabel->SetText(FText::FromString(
      FString::Printf(TEXT("%d/%d"), Fighter.Health, Fighter.MaxHealth)));

  // Death (isDefeated/health<=0): instant hide, no animations (grey slice).
  SetActorHiddenInGame(!Fighter.IsAlive());
  SetActorEnableCollision(Fighter.IsAlive());
}

void AS08FighterActor::SetSelected(bool bSelected) {
  bIsSelected = bSelected;
  LastLabelRatio = -1.0f;
  Ring->SetVisibility(bSelected || (bArtSelectionRingLoaded && bIsCombatAttacker));
  if (bSelected && bArtSelectionRingLoaded) {
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW selection ring shown fighter=%s mesh=%s"),
        *Fighter.Name, *Ring->GetStaticMesh()->GetName()));
  }
}

void AS08FighterActor::SetCombatMarkers(bool bAttacker, bool bTarget) {
  const bool bNewAttacker = bArtSelectionRingLoaded && bAttacker && Fighter.IsAlive();
  const bool bNewTarget = bArtTargetRingLoaded && bTarget && Fighter.IsAlive();
  if (bIsCombatAttacker == bNewAttacker && bIsCombatTarget == bNewTarget) return;
  bIsCombatAttacker = bNewAttacker;
  bIsCombatTarget = bNewTarget;
  Ring->SetVisibility(bIsSelected || bIsCombatAttacker);
  TargetRing->SetVisibility(bIsCombatTarget);
  FS08Trace::Write(FString::Printf(
      TEXT("ARTPREVIEW combat marker fighter=%s attacker=%d target=%d targetMesh=%s"),
      *Fighter.Name, bIsCombatAttacker ? 1 : 0, bIsCombatTarget ? 1 : 0,
      TargetRing->GetStaticMesh() ? *TargetRing->GetStaticMesh()->GetName()
                                  : TEXT("none")));
}

void AS08FighterActor::SetLabelZoomRatio(float DistanceRatio,
                                         bool bOnlySelected) {
  const float Ratio = FMath::Clamp(DistanceRatio, 0.15f, 1.5f);
  if (FMath::Abs(Ratio - LastLabelRatio) < 0.01f &&
      bOnlySelected == bLastOnlySelected) return;
  LastLabelRatio = Ratio;
  bLastOnlySelected = bOnlySelected;
  Label->SetWorldSize(BaseNameWorldSize * Ratio);
  HpLabel->SetWorldSize(BaseHpWorldSize * Ratio);
  // Bring the compact label closer to the sculpt at K2 while keeping the
  // overview's original vertical clearance. This remains world-space text,
  // so it never captures mouse input or changes the authoritative fighter.
  const float CloseAmount = FMath::Clamp((1.0f - Ratio) / 0.8f, 0.0f, 1.0f);
  const float CloseNameZ = Fighter.bIsHero ? 68.0f : 48.0f;
  const float CloseHpZ = Fighter.bIsHero ? 61.0f : 41.0f;
  Label->SetRelativeLocation(FVector(0.0f, 0.0f,
      FMath::Lerp(BaseNameHeight, CloseNameZ, CloseAmount)));
  HpLabel->SetRelativeLocation(FVector(0.0f, 0.0f,
      FMath::Lerp(BaseHpHeight, CloseHpZ, CloseAmount)));
  const bool bShow = !bOnlySelected || bIsSelected;
  Label->SetVisibility(bShow);
  HpLabel->SetVisibility(bShow);
}
