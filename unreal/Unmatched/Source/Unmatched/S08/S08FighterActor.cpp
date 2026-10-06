#include "S08FighterActor.h"
#include "S08ArtHudText.h"
#include "S08ArtHud.h"
#include "S08ArtLook.h"
#include "S08ArtPreviewMedusa.h"
#include "S08BoardActor.h"
#include "S08Facing.h"
#include "S08IconMotion.h"
#include "S08Render.h"
#include "S08TraceLog.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/CapsuleComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/BillboardComponent.h"
#include "Components/SpotLightComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "Engine/Texture2D.h"
#include "Engine/Font.h"
#include "Components/TextRenderComponent.h"
#include "Animation/AnimSequenceBase.h"
#include "Animation/AnimSingleNodeInstance.h"
#include "Animation/AnimSequence.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "Materials/MaterialInterface.h"
#include "Materials/MaterialInstance.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "UObject/ConstructorHelpers.h"

namespace {
// W4-A game layer: the unlit EyeAdaptationInverse material (or the pre-W4
// M_S08_Solid under -S08LegacyRender); both carry the "Tint" parameter.
UMaterialInterface* LoadSolidMaterial() {
  if (UMaterialInterface* GameLayer = S08GameLayerMaterial()) return GameLayer;
  return LoadObject<UMaterialInterface>(nullptr, TEXT("/Engine/BasicShapes/BasicShapeMaterial"));
}

// AN-31 (ВР-72, ВР-Z1R-03): the digit font - the OFFLINE (texture-page) Roboto Bold Condensed digits 0-9
// (tools/art/hero/base_digit_import.py). UTextRenderComponent draws offline fonts only: a runtime-cached font never
// reaches its scene proxy (FTextRenderSceneProxy::CreateRenderThreadResources returns early), which is why the
// first Z-1 digit (a transient runtime UFont over the FontFace) was never drawn.
UFont* S08BaseDigitFont() {
  UFont* Font = LoadObject<UFont>(nullptr, *S08HeroesV2::BaseDigitFontPath(), nullptr, LOAD_NoWarn);
  return Font && Font->FontCacheType == EFontCacheType::Offline && Font->Textures.Num() > 0 ? Font : nullptr;
}
// Stage 3 T5.2 ("MI Medusa identical by hash on every board"): sha256 of what
// the loaded (cooked) material carries - its path, its parent path and every
// scalar/vector/texture parameter override, sorted by name. The same pak gives
// the same digest on every board; a per-board material swap or a runtime
// override would change it. Written once per Medusa fighter.
FString S08MaterialDigest(const UMaterialInterface* Material, FString& OutParent, int32& OutParams) {
  OutParent = TEXT("-");
  OutParams = 0;
  if (!Material) return TEXT("-");
  TArray<FString> Parts;
  if (const UMaterialInstance* Instance = Cast<UMaterialInstance>(Material)) {
    if (Instance->Parent) OutParent = Instance->Parent->GetPathName();
    for (const FScalarParameterValue& P : Instance->ScalarParameterValues) {
      Parts.Add(FString::Printf(TEXT("S:%s=%.6f"), *P.ParameterInfo.Name.ToString(), P.ParameterValue));
    }
    for (const FVectorParameterValue& P : Instance->VectorParameterValues) {
      Parts.Add(FString::Printf(TEXT("V:%s=%.6f,%.6f,%.6f,%.6f"), *P.ParameterInfo.Name.ToString(),
                                P.ParameterValue.R, P.ParameterValue.G, P.ParameterValue.B,
                                P.ParameterValue.A));
    }
    for (const FTextureParameterValue& P : Instance->TextureParameterValues) {
      Parts.Add(FString::Printf(TEXT("T:%s=%s"), *P.ParameterInfo.Name.ToString(),
                                P.ParameterValue ? *P.ParameterValue->GetPathName() : TEXT("-")));
    }
  }
  Parts.Sort();
  OutParams = Parts.Num();
  const FString Canonical = Material->GetPathName() + TEXT("|") + OutParent + TEXT("|") +
                            FString::Join(Parts, TEXT(";"));
  const FTCHARToUTF8 Utf8(*Canonical);
  return S08Sha256Hex(reinterpret_cast<const uint8*>(Utf8.Get()), Utf8.Length());
}
} // namespace

AS08FighterActor::AS08FighterActor() {
  // AN-23 (ВР-06, F6): the actor ticks only while a facing turn blends (StartFacingTurn enables it, the end disables).
  PrimaryActorTick.bCanEverTick = true;
  PrimaryActorTick.bStartWithTickEnabled = false;
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

  TeamRing = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("TeamRing"));
  TeamRing->SetupAttachment(RootComponent);
  TeamRing->SetCollisionEnabled(ECollisionEnabled::NoCollision);
  TeamRing->SetVisibility(false);

  TargetRing = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("TargetRing"));
  TargetRing->SetupAttachment(RootComponent);
  TargetRing->SetCollisionEnabled(ECollisionEnabled::NoCollision);
  TargetRing->SetVisibility(false);

  TargetIcon = CreateDefaultSubobject<UBillboardComponent>(TEXT("TargetIcon"));
  TargetIcon->SetupAttachment(RootComponent);
  TargetIcon->SetCollisionEnabled(ECollisionEnabled::NoCollision);
  // BillboardComponent is hidden in game by default (editor helper sprite).
  TargetIcon->SetHiddenInGame(false);
  TargetIcon->SetVisibility(false);

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

  // AN-31 (ВР-07, ВР-72): the harpy base digit - attached to the actor, not ArtBase, so it never rotates with the
  // figure; the placement towards the camera is recomputed by UpdateBaseDigit.
  BaseDigitDisc = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("BaseDigitDisc"));
  BaseDigitDisc->SetupAttachment(RootComponent);
  BaseDigitDisc->SetStaticMesh(Cylinder);
  BaseDigitDisc->SetCollisionEnabled(ECollisionEnabled::NoCollision);
  BaseDigitDisc->SetVisibility(false);

  BaseDigitText = CreateDefaultSubobject<UTextRenderComponent>(TEXT("BaseDigitText"));
  BaseDigitText->SetupAttachment(RootComponent);
  BaseDigitText->SetHorizontalAlignment(EHTA_Center);
  BaseDigitText->SetVerticalAlignment(EVRTA_TextCenter);
  BaseDigitText->SetCollisionEnabled(ECollisionEnabled::NoCollision);
  BaseDigitText->SetVisibility(false);

  // ART-004 T2.2: visibility-channel click volume of an art figure. Enabled
  // only while an art figure replaces the grey Body box (ApplyFighter).
  ClickCapsule = CreateDefaultSubobject<UCapsuleComponent>(TEXT("ClickCapsule"));
  ClickCapsule->SetupAttachment(RootComponent);
  ClickCapsule->SetCollisionEnabled(ECollisionEnabled::NoCollision);
  ClickCapsule->SetCollisionResponseToAllChannels(ECR_Ignore);
  ClickCapsule->SetCollisionResponseToChannel(ECC_Visibility, ECR_Block);
  ClickCapsule->SetCanEverAffectNavigation(false);
  ClickCapsule->SetHiddenInGame(true);

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
  // ART-DEFAULT (S08ArtLook.h): the art markers (selection ring, target arcs and icon, team rings) belong to the
  // accepted look - default on, -S08GreyBoard off (they used to need -ArtPreview).
  if (S08ArtLook::Enabled()) {
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
    if (UTexture2D* AttackIcon = LoadObject<UTexture2D>(nullptr,
            TEXT("/Game/ArtTests/ARTMarkers/Textures/T_UI_Action_AttackConcept"))) {
      TargetIcon->SetSprite(AttackIcon);
      TargetIcon->SetRelativeScale3D(FVector(0.042f));
      bArtTargetIconLoaded = true;
    }
    LoadTeamRingAssets();
  }
  // W4-A game layer: rings, team base and labels cast no shadow and stay out
  // of Lumen / distance-field lighting (the art figure and pedestal do not).
  for (UPrimitiveComponent* GameLayer : {static_cast<UPrimitiveComponent*>(Ring.Get()),
                                         static_cast<UPrimitiveComponent*>(TargetRing.Get()),
                                         static_cast<UPrimitiveComponent*>(Base.Get()),
                                         static_cast<UPrimitiveComponent*>(Label.Get()),
                                         static_cast<UPrimitiveComponent*>(HpLabel.Get()),
                                         static_cast<UPrimitiveComponent*>(TargetIcon.Get()),
                                         static_cast<UPrimitiveComponent*>(TeamRing.Get()),
                                         static_cast<UPrimitiveComponent*>(BaseDigitDisc.Get()),
                                         static_cast<UPrimitiveComponent*>(BaseDigitText.Get())}) {
    S08ApplyGameLayerPrimitive(GameLayer);
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

bool AS08FighterActor::LoadTeamRingAssets() {
  // W5b-R D-3: team ring meshes + keyline / fill MIs (game-layer master); -S08LegacyRender keeps the pre-W5b disc.
  if (S08LegacyRender()) return false;
  TeamRingMeshP1 = LoadObject<UStaticMesh>(nullptr, S08TeamRingSpec::MeshPath(ES08TeamSlot::P1));
  TeamRingMeshP2 = LoadObject<UStaticMesh>(nullptr, S08TeamRingSpec::MeshPath(ES08TeamSlot::P2));
  TeamRingKeyline = LoadObject<UMaterialInterface>(nullptr, S08TeamRingSpec::KeylineMaterialPath);
  TeamRingFill = LoadObject<UMaterialInterface>(nullptr, S08TeamRingSpec::FillMaterialPath);
  // 5c-B1: the light rim of the two-tone edge (mesh slot 2; the mesh keeps it as its default material too)
  TeamRingRim = LoadObject<UMaterialInterface>(nullptr, S08TeamRingSpec::RimMaterialPath);
  bTeamRingReady = TeamRingMeshP1 && TeamRingMeshP2 && TeamRingKeyline && TeamRingFill && TeamRingRim &&
                   TeamRingMeshP1->GetStaticMaterials().Num() == 3 && TeamRingMeshP2->GetStaticMaterials().Num() == 3;
  if (bTeamRingReady && !TeamRingFillMid) TeamRingFillMid = UMaterialInstanceDynamic::Create(TeamRingFill, this);
  bTeamRingReady = bTeamRingReady && TeamRingFillMid;
  return bTeamRingReady;
}

void AS08FighterActor::ApplyFighter(const FS08BoardFighter& InFighter,
                                    const FVector& CellCenter, bool bOwn,
                                    bool bArtPreview, bool bTopologyBoard) {
  // Wave 5c-B / DE-019: a v2 figure that was alive plays its death on the spot - DeathSettle, the still and the
  // dissolve (01 F-09) - before the usual hide; the defeated fighter's cell (X = -1) is not used.
  const bool bWasAlive = bHasApplied && Fighter.IsAlive();
  bHasApplied = true;
  Fighter = InFighter;
  // MS-T-16: a move keeps playing while the snapshot keeps the fighter on its destination; a new cell or a death jumps
  // it to its final pose first (CUE-007 on_new_event = jump_to_final).
  if (bMoving && !(Fighter.IsAlive() && CellCenter.Equals(LogicalCenter, 1.0))) FinishMove();
  LogicalCenter = CellCenter;
  if (bHeroV2Visual && !Fighter.IsAlive() && (bWasAlive || bDeathHold)) {
    if (!bDeathHold && !bDeathDone) BeginHeroDeath();
    if (bDeathHold) return;
  }
  SetActorLocation(CellCenter);

  bool bVisualArt = false;
  bool bVisualBlockout = false;
  // Wave 5c-B heroes v2 (the default since ART-DEFAULT): the look-dev C figure replaces the Medusa candidate / ART-003
  // blockout of a mapped fighter; a missing asset falls back to the legacy path (traced). With -S08HeroesLegacy (or the
  // -ArtPreview -ArtPreviewAllMedusa review) and on the grey board V2Spec is null.
  const S08HeroesV2::FHeroSpec* V2Spec =
      S08HeroesV2::Find(bArtPreview, S08HeroesV2::FlagEnabled(), Fighter.Name);
  USkeletalMesh* V2Mesh = nullptr;
  const bool bHeroV2 = V2Spec && ApplyHeroV2(*V2Spec, CellCenter, V2Mesh);
  // The candidate is a Medusa sculpt, not a substitute for Arthur, Merlin or
  // the three Harpies. Keep their honest grey blockouts in this pilot - except
  // in the opt-in -ArtPreviewAllMedusa review (ART-004 T2.2): six copies of
  // the candidate with the team MI and the hero/sidekick scale, so the art
  // review sees six sculpts in one live frame. Never a production mapping.
  const bool bAllMedusa = S08ArtPreviewAllMedusa();
  const bool bMedusaCandidate = !bHeroV2 && S08IsMedusaCandidateFighter(
      bArtPreview, bAllMedusa, Fighter.bIsHero, Fighter.Name);
  USkeletalMesh* CandidateMesh = bHeroV2 ? V2Mesh : nullptr;
  UStaticMesh* BlockoutMesh = nullptr;
  if (bHeroV2) bVisualArt = true;
  if (bMedusaCandidate) {
    const FS08MedusaCandidate MedusaCandidate = S08SelectMedusaCandidate();
    USkeletalMesh* Mesh = MedusaCandidate.MeshPath
        ? LoadObject<USkeletalMesh>(nullptr, MedusaCandidate.MeshPath)
        : nullptr;
    UStaticMesh* Pedestal = LoadObject<UStaticMesh>(nullptr,
        TEXT("/Game/ArtPreview/Medusa/Meshes/SM_Medusa_Base_v2Candidate"));
    // W5b-R D-2: the TeamColor MI by the team look (MI_Medusa_P1 / _P2; 5c-B1 B1-4, user decision "accents + ring":
    // both TeamColor (1,1,1,1) - concept colours, the team shows on the ring and the chip; W5b-R had the pastel); the former
    // own/enemy MI_Medusa_Blue/_Red stay the fallback and the -S08LegacyRender look.
    UMaterialInterface* TeamMaterial = S08LegacyRender() ? nullptr : LoadObject<UMaterialInterface>(nullptr,
        Look == ES08TeamSlot::P1 ? TEXT("/Game/ArtPreview/Medusa/Materials/MI_Medusa_P1")
                                 : TEXT("/Game/ArtPreview/Medusa/Materials/MI_Medusa_P2"));
    if (!TeamMaterial) {
      TeamMaterial = LoadObject<UMaterialInterface>(nullptr,
          bOwn ? TEXT("/Game/ArtPreview/Medusa/Materials/MI_Medusa_Blue")
               : TEXT("/Game/ArtPreview/Medusa/Materials/MI_Medusa_Red"));
    }
    bVisualArt = Mesh && Mesh->GetSkeleton() && Pedestal && TeamMaterial;
    if (bVisualArt) {
      CandidateMesh = Mesh;
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
      if (!bMedusaMaterialsTraced) {
        bMedusaMaterialsTraced = true;
        FString Parent;
        int32 Params = 0;
        const FString Digest = S08MaterialDigest(ArtBody->GetMaterial(0), Parent, Params);
        const UMaterialInterface* Slot1 = ArtBody->GetMaterial(1);
        const UMaterialInterface* BaseMaterial = ArtBase->GetMaterial(0);
        FS08Trace::Write(FString::Printf(
            TEXT("ARTPREVIEW medusa materials fighter=%s team=%s mesh=%s slots=%d mi=%s slot1=%s base=%s parent=%s params=%d miSha256=%s teamSlot=%s look=%s mode=%s"),
            *Fighter.Id, bOwn ? TEXT("own") : TEXT("enemy"), *Mesh->GetName(), ArtBody->GetNumMaterials(),
            ArtBody->GetMaterial(0) ? *ArtBody->GetMaterial(0)->GetPathName() : TEXT("-"),
            Slot1 ? *Slot1->GetPathName() : TEXT("-"),
            BaseMaterial ? *BaseMaterial->GetPathName() : TEXT("-"), *Parent, Params, *Digest,
            S08TeamSlotName(Team), S08TeamSlotName(Look), S08TeamColorModeName(TeamMode)));
      }
    }
  }
  if (bArtPreview && !bMedusaCandidate && !bHeroV2) {
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
        BlockoutMesh = PreviewMesh;
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
  bArtFigureVisible = bArtFigure;
  bMedusaVisual = bVisualArt && !bHeroV2;
  bHeroV2Visual = bHeroV2;
  bBlockoutVisible = bVisualBlockout;

  // ART-004 T2.2 click volume. The hidden grey Body box (60x60x120 uu for a
  // hero) kept catching visibility traces far above the 55-uu sculpt; an art
  // figure gets a capsule sized from its own mesh bounds instead, and the
  // hidden box stops blocking. The candidate skeletal meshes have no physics
  // asset (checked and traced), so the capsule is the click contract.
  const float ArtScale = bHeroV2 ? HeroV2Scale : (Fighter.bIsHero ? 1.0f : 0.78f);
  if (bArtFigure) {
    const FBoxSphereBounds MeshBounds = CandidateMesh ? CandidateMesh->GetBounds()
        : (BlockoutMesh ? BlockoutMesh->GetBounds()
                        : FBoxSphereBounds(FVector::ZeroVector, FVector(15.0f, 15.0f, 27.5f), 30.0f));
    const float Scale = bVisualArt ? ArtScale : 1.0f;
    const float Top = FMath::Max(10.0f, static_cast<float>(MeshBounds.Origin.Z + MeshBounds.BoxExtent.Z) * Scale);
    const float Radius = FMath::Clamp(
        0.5f * static_cast<float>(MeshBounds.BoxExtent.X + MeshBounds.BoxExtent.Y) * Scale,
        8.0f * Scale, 20.0f * Scale);
    const float HalfHeight = FMath::Max(Radius, Top * 0.5f);
    FigureHeightUU = Top;
    ClickCapsule->SetCapsuleSize(Radius, HalfHeight);
    ClickCapsule->SetRelativeLocation(FVector(0.0f, 0.0f, HalfHeight));
    ClickCapsule->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
    Body->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    if (!bCapsuleTraced) {
      bCapsuleTraced = true;
      FS08Trace::Write(FString::Printf(
          TEXT("ARTPREVIEW click capsule fighter=%s mesh=%s physicsAsset=%d radius=%.1f halfHeight=%.1f top=%.1f bodyCollision=0 source=meshBounds"),
          *Fighter.Id,
          CandidateMesh ? *CandidateMesh->GetName() : (BlockoutMesh ? *BlockoutMesh->GetName() : TEXT("none")),
          CandidateMesh && CandidateMesh->GetPhysicsAsset() ? 1 : 0, Radius, HalfHeight, Top));
    }
  } else {
    FigureHeightUU = Fighter.bIsHero ? 120.0f : 50.0f;
    ClickCapsule->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Body->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
  }
  if (bAllMedusa && bArtPreview && !bAllMedusaTraced) {
    bAllMedusaTraced = true;
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW allMedusa copy fighter=%s hero=%d team=%s visual=%d mesh=%s scale=%.2f name=%s"),
        *Fighter.Id, Fighter.bIsHero ? 1 : 0, bOwn ? TEXT("own") : TEXT("enemy"), bVisualArt ? 1 : 0,
        ArtBody->GetSkeletalMeshAsset() ? *ArtBody->GetSkeletalMeshAsset()->GetName() : TEXT("none"),
        ArtScale, *Fighter.Name));
  }
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
  {
    // 5c-B3: the arcs sit inside the ring's inner keyline (S08TeamRingSpec::TargetArcScale, XY only).
    const float ArcSize = Fighter.bIsHero ? 1.0f : 0.78f;
    const float ArcXY = ArcSize * S08TeamRingSpec::TargetArcScale;
    TargetRing->SetRelativeScale3D(FVector(ArcXY, ArcXY, ArcSize));
  }
  TargetRing->SetRelativeLocation(FVector::ZeroVector);
  // Grid boards keep the column rule `Fighter.X >= 4` (Cobble and the
  // Sherwood / T-Rex art-fixture frames unchanged). On an original map
  // (topology board) the lattice column means nothing on screen: the world
  // target icon leans towards the board centre (x = 0 in world) once the
  // figure stands more than 1.5 cell pitches right of it.
  const bool bRightBand = bTopologyBoard
                              ? CellCenter.X > 1.5f * FS08BoardModel::CellSizeUU
                              : Fighter.X >= 4;
  TargetIcon->SetRelativeLocation(FVector(bRightBand ? -20.0f : 20.0f, 0.0f,
      Fighter.bIsHero ? 112.0f : 90.0f));
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
  // W5b-R D-3: the authored team ring replaces the grey disc of an art figure (the T5.2 disc top lay in the tile
  // plane z = 0 and z-fought with it: A/B in the live editor, act W5b-R). The disc keeps its query collision (click
  // volume of the grey path); only its rendering goes. Grey S08/S09 (no art figure) keep the blue/red disc.
  bTeamRingShown = bArtFigure && bTeamRingReady;
  if (bTeamRingShown) {
    const float FigureScale = Fighter.bIsHero ? 1.0f : S08TeamRingSpec::SidekickScale;
    TeamRing->SetStaticMesh(Look == ES08TeamSlot::P1 ? TeamRingMeshP1.Get() : TeamRingMeshP2.Get());
    TeamRing->SetRelativeLocation(FVector::ZeroVector);
    TeamRing->SetRelativeScale3D(FVector(FigureScale, FigureScale, 1.0f));
    TeamRing->SetMaterial(0, TeamRingKeyline);
    TeamRingFillMid->SetVectorParameterValue(TEXT("LayerColor"), S08TeamPalette::RingFill(Look));
    TeamRing->SetMaterial(1, TeamRingFillMid);
    TeamRing->SetMaterial(2, TeamRingRim);
  }
  TeamRing->SetVisibility(bTeamRingShown);
  Base->SetVisibility(!bTeamRingShown);
  if (bArtPreview && !bTeamRingTraced) {
    bTeamRingTraced = true;
    const FLinearColor Fill = S08TeamPalette::RingFill(Look);
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW team ring fighter=%s team=%s look=%s mode=%s shape=%s shown=%d mesh=%s fill=%s keyline=%s fillLinear=(%.4f,%.4f,%.4f) zMin=%.2f zMax=%.2f scale=%.2f base=%s blockout=%d art=%d rim=%s"),
        *Fighter.Id, S08TeamSlotName(Team), S08TeamSlotName(Look), S08TeamColorModeName(TeamMode),
        S08TeamShapeName(Look), bTeamRingShown ? 1 : 0,
        bTeamRingShown ? *TeamRing->GetStaticMesh()->GetName() : TEXT("none"),
        Look == ES08TeamSlot::P1 ? S08TeamPalette::P1Hex : S08TeamPalette::P2Hex, S08TeamPalette::KeylineHex,
        Fill.R, Fill.G, Fill.B, S08TeamRingSpec::ZMin, S08TeamRingSpec::ZMax,
        Fighter.bIsHero ? 1.0f : S08TeamRingSpec::SidekickScale, bTeamRingShown ? TEXT("hidden") : TEXT("shown"),
        bVisualBlockout ? 1 : 0, bVisualArt ? 1 : 0, S08TeamPalette::RimHex));
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

  ApplyLabelVisibility();

  // Death (isDefeated/health<=0): instant hide, no animations (grey slice). A v2 figure first plays its death
  // (early return above: DeathSettle, still, dissolve - DE-019) and reaches this line once it is gone.
  SetActorHiddenInGame(!Fighter.IsAlive());
  SetActorEnableCollision(Fighter.IsAlive());
  if (bHeroV2 && Fighter.IsAlive()) {
    const S08HeroesV2::FClipChoice Choice = S08HeroesV2::NextClip(HeroClip, S08HeroesV2::EEvent::Spawn);
    if (Choice.bRestart) PlayHeroClip(Choice.Clip, S08HeroesV2::EEvent::Spawn, -1);
    ApplyBenchDissolve();
  }
  if (bMoving) {
    // MS-T-16: a re-application during the move (another fighter's snapshot) keeps the travelling pose.
    ApplyMovePose(MovePose);
  } else if (S08Facing::LegacyRequested()) {
    // The legacy half-field reset of every apply; AN-23 (ВР-06) keeps the current angle instead - the board actor's
    // ApplyRestFacing right after decides.
    FacingYawDeg = static_cast<float>(FS08MoveAnim::RestYawDeg(CellCenter));
    FacingLeanDeg = 0.0f;
  } else if (bRestFacingApplied) {
    // F1 (Z-1 review): ApplyHeroV2 / the legacy visuals reset the mesh yaw to the half-field rule on every snapshot;
    // the v1 facing (or the turn blending towards it) is re-applied so a snapshot never shows the old rule.
    ApplyFigureFacing(FacingYawDeg, FacingLeanDeg);
  } else {
    // Before the first rest facing the figure shows the half-field angle ApplyHeroV2 set: the turn starts there.
    FacingYawDeg = static_cast<float>(FS08MoveAnim::RestYawDeg(CellCenter));
    FacingLeanDeg = 0.0f;
  }
  UpdateBaseDigit();  // AN-31: the harpy digit rides the apply (spawn / snapshot), placed towards the camera
}

// ---- AN-23 (ВР-06): the rest facing ---------------------------------------------------------------------------

void AS08FighterActor::ApplyRestFacing(const TCHAR* Src, bool bLegacy, const FVector& CameraPos, bool bHasEnemy,
                                       const FVector& NearestEnemyPos, const FString& EnemyId) {
  if (bLegacy) {
    StopFacingTurn();
    bRestFacingApplied = true;
    bFaceHold = bFacePending = false;
    FacingYawDeg = static_cast<float>(FS08MoveAnim::RestYawDeg(GetActorLocation()));
    FacingLeanDeg = 0.0f;
    ApplyFigureFacing(FacingYawDeg, 0.0);
    return;
  }
  // The move plan owns the facing until the move ends; the attack holds the target angle until its return (AN-24 /
  // AN-25), and the dead never turn (ВР-06 states).
  if (bMoving || bDeathHold || !Fighter.IsAlive() || bFaceHold) return;
  if (HeroClip == S08HeroesV2::EClip::LungeAttack || HeroClip == S08HeroesV2::EClip::HitReact) return;
  const bool bSpawn = !bRestFacingApplied;
  bRestFacingApplied = true;
  const double Cam = S08Facing::YawToward(GetActorLocation(), CameraPos);
  // A spawn without a living enemy faces the camera axis (the card); later snapshots without one keep the angle.
  const double Want = !bHasEnemy && bSpawn
      ? Cam
      : S08Facing::RestYaw(GetActorLocation(), CameraPos, bHasEnemy, NearestEnemyPos, FacingYawDeg);
  DigitRestYawDeg = Want;
  bDigitRestYawSet = true;
  const double Change = FMath::Abs(FMath::FindDeltaAngleDegrees(FacingYawDeg, Want));
  if (!bSpawn && Change < S08Facing::MinTurnDeg) {
    UpdateBaseDigit();
    return;  // the dead band / no enemy kept the angle: no turn, no trace (F4)
  }
  FS08Trace::Write(FString::Printf(
      TEXT("FACING fighter=%s src=%s from=%.0f rest=%.0f cam=%.0f off=%.0f enemy=%s"), *Fighter.Id,
      bSpawn ? TEXT("spawn") : Src, FacingYawDeg, Want, Cam, FMath::Abs(FMath::FindDeltaAngleDegrees(Cam, Want)),
      bHasEnemy ? *EnemyId : TEXT("none")));
  if (Change >= S08Facing::MinTurnDeg) StartFacingTurn(Want, S08Facing::ReturnMs);
  UpdateBaseDigit();  // the digit sits on the side away from the new rest offset
}

void AS08FighterActor::StartFacingTurn(double WantYawDeg, double Ms) {
  FacingTurnFromDeg = FacingYawDeg;
  FacingTurnToDeg = WantYawDeg;
  FacingTurnMs = FMath::Max(0.0, Ms);
  FacingTurnElapsedMs = 0.0;
  // Reduced motion / speed "none" snap every turn (ВР-06 states).
  if (!GetWorld() || FacingTurnMs <= 0.0 || S08IconMotion::IsReducedMotion() || S08Motion::Current().SnapsMoves()) {
    StopFacingTurn();
    ApplyFigureFacing(WantYawDeg, 0.0);
    return;
  }
  bFacingTurning = true;
  SetActorTickEnabled(true);  // F6: the frame tick drives the blend (no fixed-rate timer)
}

void AS08FighterActor::StopFacingTurn() {
  bFacingTurning = false;
  if (IsActorTickEnabled()) SetActorTickEnabled(false);
}

void AS08FighterActor::Tick(float DeltaSeconds) {
  Super::Tick(DeltaSeconds);
  AdvanceFacingTurn(DeltaSeconds);
}

void AS08FighterActor::AdvanceFacingTurn(float DeltaSeconds) {
  if (!bFacingTurning) {
    StopFacingTurn();
    return;
  }
  if (bMoving || bDeathHold) {  // the move plan / the death own the figure now
    StopFacingTurn();
    return;
  }
  FacingTurnElapsedMs += FMath::Max(0.0, static_cast<double>(DeltaSeconds)) * 1000.0;
  const double Alpha = FMath::Clamp(FacingTurnElapsedMs / FMath::Max(1e-9, FacingTurnMs), 0.0, 1.0);
  ApplyFigureFacing(S08Facing::TurnYawAt(FacingTurnFromDeg, FacingTurnToDeg, Alpha), 0.0);
  if (Alpha >= 1.0) StopFacingTurn();
}

float AS08FighterActor::GetShownFigureYawDeg() const {
  if (bHeroV2Visual && ArtBody) return static_cast<float>(ArtBody->GetRelativeRotation().Yaw);
  if (bMedusaVisual && ArtBody) return static_cast<float>(ArtBody->GetRelativeRotation().Yaw + 90.0);
  if (bBlockoutVisible && ArtPlaceholder) return static_cast<float>(ArtPlaceholder->GetRelativeRotation().Yaw + 90.0);
  return FacingYawDeg;
}

void AS08FighterActor::PlayFaceTarget(const FString& TargetId, const FVector& TargetWorldPos, double Ms, int64 NowMs,
                                      bool bSnapAtLunge) {
  if (S08Facing::LegacyRequested() || !Fighter.IsAlive() || bDeathHold || bMoving) return;
  const FVector CameraPos = AS08BoardActor::ViewCameraLocation(GetWorld());
  const double Axis = S08Facing::YawToward(GetActorLocation(), CameraPos);
  const double ToTarget = S08Facing::YawToward(GetActorLocation(), TargetWorldPos);
  const bool bClamped = FMath::Abs(FMath::FindDeltaAngleDegrees(Axis, ToTarget)) > S08Facing::AttackMaxOffDeg;
  const double Want = S08Facing::AttackYaw(GetActorLocation(), TargetWorldPos, CameraPos);
  bFaceHold = true;  // the rest facing of later snapshots waits for the return (AN-25)
  const FString Line = FString::Printf(
      TEXT("FACING fighter=%s src=attack t=%lld from=%.0f yaw=%.0f target=%s clamped=%d"), *Fighter.Id,
      static_cast<long long>(NowMs), FacingYawDeg, Want, *TargetId, bClamped ? 1 : 0);
  if (bSnapAtLunge || S08IconMotion::IsReducedMotion() || S08Motion::Current().SnapsMoves()) {
    // ВР-Z1R-05: reduced motion / speed "none" - no turn inside the pause; the angle snaps in the Lunge frame.
    StopFacingTurn();
    bFacePending = true;
    FacePendingYawDeg = Want;
    FacePendingTrace = Line;
    return;
  }
  bFacePending = false;
  FS08Trace::Write(Line + FString::Printf(TEXT(" ms=%.0f"), Ms));
  StartFacingTurn(Want, Ms);
}

void AS08FighterActor::CommitFaceTarget(int64 NowMs) {
  if (!bFacePending) return;
  bFacePending = false;
  if (!Fighter.IsAlive() || bDeathHold || bMoving) return;
  FS08Trace::Write(FacePendingTrace + FString::Printf(TEXT(" ms=0 snap=lunge lungeT=%lld"),
                                                      static_cast<long long>(NowMs)));
  StopFacingTurn();
  ApplyFigureFacing(FacePendingYawDeg, 0.0);
}

void AS08FighterActor::ReturnToRestFacing(const TCHAR* Src, double WantYawDeg, double Ms, int64 NowMs) {
  bFaceHold = false;
  bFacePending = false;
  if (S08Facing::LegacyRequested() || bDeathHold || !Fighter.IsAlive() || bMoving) return;
  DigitRestYawDeg = WantYawDeg;
  bDigitRestYawSet = true;
  // AN-25: the dead band never holds the return - it always reaches the rest angle; F4: a change under
  // MinTurnDeg (a HitReact of a figure that never turned) is no turn and no line.
  if (FMath::Abs(FMath::FindDeltaAngleDegrees(FacingYawDeg, WantYawDeg)) < S08Facing::MinTurnDeg) return;
  FS08Trace::Write(FString::Printf(
      TEXT("FACING fighter=%s src=%s t=%lld from=%.0f rest=%.0f ms=%.0f"), *Fighter.Id, Src,
      static_cast<long long>(NowMs), FacingYawDeg, WantYawDeg, Ms));
  StartFacingTurn(WantYawDeg, Ms);
  UpdateBaseDigit();
}

// ---- MS-T-16 move animation ------------------------------------------------

void AS08FighterActor::PlayMove(const FS08MovePlan& Plan, const FS08MoveAnimParams& Params, int64 NowMs) {
  if (bMoving) FinishMove();  // jump_to_final: the new event of the same figure
  if (Plan.Points.Num() == 0 || !Fighter.IsAlive() || bDeathHold) return;
  StopFacingTurn();  // AN-23: the plan owns the facing (an attack hold or a deferred snap ends with the move)
  bFaceHold = bFacePending = false;
  MovePlan = Plan;
  MoveParams = Params;
  MoveSeqStartMs = NowMs;
  LogicalCenter = Plan.Destination();
  bMoving = true;
  if (!bArtFigureVisible) {
    // The grey mannequin has no sized click capsule: one around the box keeps the click on the logical cell.
    ClickCapsule->SetCapsuleSize(Fighter.bIsHero ? 30.0f : 25.0f, FMath::Max(30.0f, FigureHeightUU * 0.5f));
  }
  ClickCapsule->SetUsingAbsoluteLocation(true);
  TickMove(NowMs);
  UpdateBaseDigit();  // AN-31: a Place transfer hides the digit for the whole transfer (D3)
}

bool AS08FighterActor::TickMove(int64 NowMs) {
  if (!bMoving) return false;
  const FS08MovePose Pose = FS08MoveAnim::Sample(MovePlan, MoveParams, static_cast<double>(NowMs - MoveSeqStartMs),
                                                 FigureHeightUU);
  ApplyMovePose(Pose);
  if (!Pose.bDone) return true;
  EndMove();
  return false;
}

bool AS08FighterActor::FinishMove() {
  if (!bMoving) return false;
  ApplyMovePose(FS08MoveAnim::Sample(MovePlan, MoveParams, MovePlan.EndMs(MoveParams) + 1.0, FigureHeightUU));
  EndMove();
  return true;
}

FVector AS08FighterActor::GetClickVolumeLocation() const {
  return ClickCapsule ? ClickCapsule->GetComponentLocation() : GetActorLocation();
}

void AS08FighterActor::ApplyMovePose(const FS08MovePose& Pose) {
  MovePose = Pose;
  SetActorLocation(Pose.Location);
  if (bMoving) {
    // MS-R-53: the hit test stays on the snapshot's cell - the capsule is pinned there, the travelling base / box
    // stop catching clicks until the figure arrives.
    ClickCapsule->SetWorldLocation(LogicalCenter + FVector(0.0f, 0.0f, ClickCapsule->GetUnscaledCapsuleHalfHeight()));
    ClickCapsule->SetCollisionEnabled(Fighter.IsAlive() ? ECollisionEnabled::QueryOnly : ECollisionEnabled::NoCollision);
    Base->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Body->SetCollisionEnabled(ECollisionEnabled::NoCollision);
  }
  ApplyFigureFacing(Pose.YawDeg, Pose.LeanDeg);
  if (MovePlan.Kind == ES08MoveKind::Place && bHeroV2Visual && HeroV2Spec && ArtBody) {
    // Place (04 §6.3): fade out on the old cell, fade in on the new one - the DE-011 dissolve MIC in its fade style.
    if (Pose.Fade > 0.0 && !bMoveFading) {
      if (UMaterialInterface* Mic = LoadObject<UMaterialInterface>(
              nullptr, *S08HeroesV2::DissolveMaterialPath(*HeroV2Spec, Look))) {
        for (int32 Slot = 0; Slot < ArtBody->GetNumMaterials(); ++Slot) ArtBody->SetMaterial(Slot, Mic);
        ApplyHeroMaterialMids();  // AN-32: the fix rides the Place fade MIC too
        bMoveFading = true;
      }
    }
    if (bMoveFading) {
      S08HeroesV2::SetDissolve(ArtBody, ArtBase, static_cast<float>(Pose.Fade), S08HeroesV2::EDissolveStyle::Fade);
    }
  }
}

void AS08FighterActor::EndMove() {
  bMoving = false;
  if (bMoveFading) {
    bMoveFading = false;
    if (HeroV2Spec && ArtBody) {
      if (UMaterialInterface* BodyMi = LoadObject<UMaterialInterface>(
              nullptr, *S08HeroesV2::BodyMaterialPath(*HeroV2Spec, Look))) {
        for (int32 Slot = 0; Slot < ArtBody->GetNumMaterials(); ++Slot) ArtBody->SetMaterial(Slot, BodyMi);
      }
      S08HeroesV2::SetDissolve(ArtBody, ArtBase, 0.0f, S08HeroesV2::EDissolveStyle::Fade);
      ApplyHeroMaterialMids();  // AN-32: the body MI is back
    }
  }
  ClickCapsule->SetUsingAbsoluteLocation(false);
  ClickCapsule->SetRelativeLocation(FVector(0.0f, 0.0f, ClickCapsule->GetUnscaledCapsuleHalfHeight()));
  // The click contract of ApplyFighter: an art figure clicks through its capsule, the grey box through itself.
  ClickCapsule->SetCollisionEnabled(bArtFigureVisible ? ECollisionEnabled::QueryOnly : ECollisionEnabled::NoCollision);
  Body->SetCollisionEnabled(bArtFigureVisible ? ECollisionEnabled::NoCollision : ECollisionEnabled::QueryOnly);
  Base->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
  UpdateBaseDigit();  // AN-31: the arrival re-places the digit on the camera side
}

void AS08FighterActor::ApplyFigureFacing(double YawDeg, double LeanDeg) {
  FacingYawDeg = static_cast<float>(YawDeg);
  FacingLeanDeg = static_cast<float>(LeanDeg);
  // Rig v2 faces +X (its yaw is the world facing); the Medusa candidate and the ART-003 blockouts face +Y.
  if (bHeroV2Visual) {
    ArtBody->SetRelativeRotation(FS08MoveAnim::FigureRotation(YawDeg, LeanDeg, 0.0));
    ArtBase->SetRelativeRotation(FRotator(0.0, YawDeg, 0.0));
  } else if (bMedusaVisual) {
    ArtBody->SetRelativeRotation(FS08MoveAnim::FigureRotation(YawDeg, LeanDeg, -90.0));
    ArtBase->SetRelativeRotation(FRotator(0.0, YawDeg - 90.0, 0.0));
  } else if (bBlockoutVisible) {
    ArtPlaceholder->SetRelativeRotation(FS08MoveAnim::FigureRotation(YawDeg, LeanDeg, -90.0));
  }
}

void AS08FighterActor::ApplyBenchDissolve() {
  using namespace S08HeroesV2;
  const float Progress = BenchDissolveProgress();
  if (Progress < 0.0f || !HeroV2Spec || !ArtBody) return;
  const FString Path = DissolveMaterialPath(*HeroV2Spec, Look);
  UMaterialInterface* Mic = LoadObject<UMaterialInterface>(nullptr, *Path);
  if (Mic) {
    for (int32 Slot = 0; Slot < ArtBody->GetNumMaterials(); ++Slot) ArtBody->SetMaterial(Slot, Mic);
    ApplyHeroMaterialMids();  // AN-32: the fix rides the dissolve MIC too
    SetDissolve(ArtBody, ArtBase, Progress, DissolveStyle());
  }
  if (!bBenchDissolveTraced) {
    bBenchDissolveTraced = true;
    FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW dissolve bench fighter=%s progress=%.2f style=%s mi=%s"),
                                     *Fighter.Id, Progress, DissolveStyleName(DissolveStyle()),
                                     Mic ? *Mic->GetName() : TEXT("missing")));
  }
}

bool AS08FighterActor::ApplyHeroV2(const S08HeroesV2::FHeroSpec& Spec, const FVector& CellCenter,
                                   USkeletalMesh*& OutMesh) {
  using namespace S08HeroesV2;
  OutMesh = nullptr;
  const FString MeshPathV2 = MeshPath(Spec);
  const FString PedestalPathV2 = PedestalPath(Spec);
  const FString BodyMiPath = BodyMaterialPath(Spec, Look);
  const FString BaseMiPath = PedestalMaterialPath(Spec, Look);
  USkeletalMesh* Mesh = LoadObject<USkeletalMesh>(nullptr, *MeshPathV2);
  UStaticMesh* Pedestal = LoadObject<UStaticMesh>(nullptr, *PedestalPathV2);
  UMaterialInterface* BodyMi = LoadObject<UMaterialInterface>(nullptr, *BodyMiPath);
  UMaterialInterface* BaseMi = LoadObject<UMaterialInterface>(nullptr, *BaseMiPath);
  FString Missing;
  if (!Mesh || !Mesh->GetSkeleton()) Missing = MeshPathV2;
  else if (!Pedestal) Missing = PedestalPathV2;
  else if (!BodyMi) Missing = BodyMiPath;
  else if (!BaseMi) Missing = BaseMiPath;
  if (HeroClips.Num() != ClipCount) HeroClips.SetNum(ClipCount);
  int32 ClipsLoaded = 0;
  if (Missing.IsEmpty()) {
    for (const EClip Clip : {EClip::Idle, EClip::LungeAttack, EClip::HitReact, EClip::DeathSettle}) {
      TObjectPtr<UAnimSequenceBase>& Slot = HeroClips[static_cast<int32>(Clip)];
      if (!Slot) Slot = LoadObject<UAnimSequenceBase>(nullptr, *ClipPath(Spec, Clip));
      // A clip on another skeleton would not pose this mesh: dropped (traced as missing when it is Idle).
      if (Slot && Slot->GetSkeleton() != Mesh->GetSkeleton()) Slot = nullptr;
      if (Slot) ++ClipsLoaded;
    }
    if (!HeroClips[static_cast<int32>(EClip::Idle)]) Missing = ClipPath(Spec, EClip::Idle);
  }
  if (!Missing.IsEmpty()) {
    const FString Key = TEXT("missing|") + Missing;
    if (Key != HeroV2TraceKey) {
      HeroV2TraceKey = Key;
      FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW heroesV2 fighter=%s missing=%s fallback=legacy"),
                                       *Fighter.Id, *Missing));
    }
    HeroV2Spec = nullptr;
    return false;
  }
  HeroV2Spec = &Spec;
  HeroV2Yaw = FigureYawDeg(CellCenter.Y);
  HeroV2Scale = FigureScale(Spec);
  if (ArtBody->GetSkeletalMeshAsset() != Mesh) {
    ArtBody->SetSkeletalMeshAsset(Mesh);
    HeroClip = EClip::None;  // a new mesh starts its Idle again
  }
  ArtBase->SetStaticMesh(Pedestal);
  for (int32 Slot = 0; Slot < ArtBody->GetNumMaterials(); ++Slot) ArtBody->SetMaterial(Slot, BodyMi);
  for (int32 Slot = 0; Slot < ArtBase->GetNumMaterials(); ++Slot) ArtBase->SetMaterial(Slot, BaseMi);
  ApplyHeroMaterialMids();  // AN-32: re-wrap the fresh slots with the profile fix
  // Rig v2 faces +X: the legacy 0/180 yaw plus FacingYawOffsetDeg keeps the legacy world facing (+Y / -Y).
  ArtBody->SetRelativeRotation(FRotator(0.0f, HeroV2Yaw, 0.0f));
  ArtBase->SetRelativeRotation(FRotator(0.0f, HeroV2Yaw, 0.0f));
  ArtBody->SetRelativeScale3D(FVector(HeroV2Scale));
  ArtBase->SetRelativeScale3D(FVector(HeroV2Scale));
  OutMesh = Mesh;
  const FString Key = FString::Printf(TEXT("%s|%s|%s|%.1f|%.4f"), *MeshPathV2, *BodyMiPath, *BaseMiPath, HeroV2Yaw,
                                      HeroV2Scale);
  if (Key != HeroV2TraceKey) {
    HeroV2TraceKey = Key;
    const FBoxSphereBounds Bounds = Mesh->GetBounds();
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW heroesV2 fighter=%s mesh=%s mi=%s yaw=%.1f scale=%.4f name=%s hero=%d look=%s base=%s baseMi=%s skeleton=%s clips=%d/4 boundsTop=%.2f figureTop=%.2f budget=%.1f"),
        *Fighter.Id, *MeshPathV2, *BodyMiPath, HeroV2Yaw, HeroV2Scale, *Fighter.Name, Fighter.bIsHero ? 1 : 0,
        S08TeamSlotName(Look), *PedestalPathV2, *BaseMiPath, *Mesh->GetSkeleton()->GetPathName(), ClipsLoaded,
        static_cast<float>(Bounds.Origin.Z + Bounds.BoxExtent.Z) * HeroV2Scale, Spec.FigureTopUU * HeroV2Scale,
        Spec.BudgetUU));
  }
  return true;
}

void AS08FighterActor::NotifyHeroAnimEvent(S08HeroesV2::EEvent Event, int32 Seq, float PlayRate) {
  if (!bHeroV2Visual) return;
  const S08HeroesV2::FClipChoice Choice = S08HeroesV2::NextClip(HeroClip, Event);
  if (!Choice.bRestart) return;
  // DE-025 (SD-49): only the lunge follows the animation speed; HitReact (with its tint) and the rest never do.
  const bool bScaled = Choice.Clip == S08HeroesV2::EClip::LungeAttack && PlayRate > 0.0f;
  PlayHeroClip(Choice.Clip, Event, Seq, bScaled ? PlayRate : 1.0f);
}

void AS08FighterActor::PlayHeroClip(S08HeroesV2::EClip Clip, S08HeroesV2::EEvent Event, int32 Seq, float PlayRate) {
  using namespace S08HeroesV2;
  UAnimSequenceBase* Anim = HeroClips.IsValidIndex(static_cast<int32>(Clip))
      ? HeroClips[static_cast<int32>(Clip)].Get() : nullptr;
  if (!Anim) {
    FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW anim fighter=%s clip=%s missing=1 event=%s seq=%d"),
                                     *Fighter.Id, ClipName(Clip), EventName(Event), Seq));
    return;
  }
  const bool bLoop = ClipLoops(Clip);
  const float Len = Anim->GetPlayLength();
  const float Phase = Clip == EClip::Idle ? IdlePhase(Fighter.Id) : 0.0f;
  const float Rate = PlayRate > 0.0f ? PlayRate : 1.0f;
  ArtBody->PlayAnimation(Anim, bLoop);
  ArtBody->SetPlayRate(Rate);  // explicit: a new clip never inherits the lunge rate
  if (Phase > 0.0f) ArtBody->SetPosition(Phase * Len, false);
  HeroClip = Clip;
  if (UWorld* World = GetWorld()) {
    FTimerManager& Timers = World->GetTimerManager();
    Timers.ClearTimer(HeroClipTimer);
    if (Clip == EClip::LungeAttack || Clip == EClip::HitReact) {
      Timers.SetTimer(HeroClipTimer, this, &AS08FighterActor::OnHeroClipFinished, FMath::Max(Len / Rate, 0.05f),
                      false);
    }
  }
  FS08Trace::Write(FString::Printf(
      TEXT("ARTPREVIEW anim fighter=%s clip=%s len=%.3f event=%s loop=%d phase=%.4f seq=%d asset=%s rate=%.2f"),
      *Fighter.Id, ClipName(Clip), Len, EventName(Event), bLoop ? 1 : 0, Phase, Seq, *Anim->GetName(), Rate));
}

bool AS08FighterActor::GetHeroClipTime(float& OutPosition, float& OutLength) const {
  if (!bHeroV2Visual || !ArtBody || !S08HeroesV2::ClipLoops(HeroClip) || !ArtBody->IsPlaying()) return false;
  const UAnimSequenceBase* Anim = HeroClips.IsValidIndex(static_cast<int32>(HeroClip))
      ? HeroClips[static_cast<int32>(HeroClip)].Get() : nullptr;
  if (!Anim) return false;
  OutLength = Anim->GetPlayLength();
  OutPosition = ArtBody->GetPosition();
  return OutLength > 0.0f;
}

bool AS08FighterActor::ShiftHeroClipClock(float DeltaSeconds) {
  float Position = 0.0f, Length = 0.0f;
  if (!GetHeroClipTime(Position, Length)) return false;
  float P = FMath::Fmod(Position + DeltaSeconds, Length);
  if (P < 0.0f) P += Length;
  ArtBody->SetPosition(P, /*bFireNotifies=*/false);
  return true;
}

bool AS08FighterActor::BenchHoldClipPose(const S08HeroesV2::FBenchClipPoseSpec& Spec, double& OutT, double& OutLen,
                                         double& OutRootDeltaUU) {
  using namespace S08HeroesV2;
  OutT = OutLen = OutRootDeltaUU = 0.0;
  if (!bHeroV2Visual || !ArtBody) return false;
  UAnimSequenceBase* Anim = HeroClips.IsValidIndex(static_cast<int32>(Spec.Clip))
      ? HeroClips[static_cast<int32>(Spec.Clip)].Get() : nullptr;
  if (!Anim) return false;
  PlayHeroClip(Spec.Clip, EEvent::Spawn, -1);  // the trace event only; the pose overrides the Idle phase below
  const double Len = Anim->GetPlayLength();
  const double T = BenchClipPoseSeconds(Spec, Len);
  if (UAnimSingleNodeInstance* Node = ArtBody->GetSingleNodeInstance()) {
    Node->SetPlaying(false);
    Node->SetPosition(static_cast<float>(T), false);
  }
  if (UWorld* World = GetWorld()) World->GetTimerManager().ClearTimer(HeroClipTimer);
  if (const UAnimSequence* Sequence = Cast<UAnimSequence>(Anim)) {
    OutRootDeltaUU = Sequence->ExtractRootMotionFromRange(0.0, T, FAnimExtractContext()).GetTranslation().Size();
  }
  OutT = T;
  OutLen = Len;
  return true;
}

FBox AS08FighterActor::GetV2FigureBox() const {
  FBox Out(ForceInit);
  if (!bHeroV2Visual) return Out;
  if (ArtBody) Out += ArtBody->Bounds.GetBox();
  if (ArtBase) Out += ArtBase->Bounds.GetBox();
  return Out;
}

// ---- AN-31 (ВР-07, ВР-72): the harpy number on the base ---------------------------------------------------------

void AS08FighterActor::UpdateBaseDigit() {
  const bool bHarpy = bHeroV2Visual && HeroV2Spec && FCString::Strcmp(HeroV2Spec->Key, TEXT("Harpy")) == 0;
  // D3: hidden for the whole Place transfer (the fade-out, the jump, the fade-in), not only while the MIC fades.
  const bool bPlacing = bMoving && MovePlan.Kind == ES08MoveKind::Place;
  const bool bShow = bHarpy && !FParse::Param(FCommandLine::Get(), S08HeroesV2::BaseDigitLegacyFlagName) &&
                     Fighter.IsAlive() && !bDeathHold && !bDissolving && !bMoveFading && !bPlacing;
  bBaseDigitDrawable = false;
  const UStaticMesh* PedestalMesh = ArtBase ? ArtBase->GetStaticMesh() : nullptr;
  if (!bShow || !PedestalMesh) {
    if (BaseDigitDisc) BaseDigitDisc->SetVisibility(false);
    if (BaseDigitText) BaseDigitText->SetVisibility(false);
    return;
  }
  // The pedestal's top face from its mesh bounds x the component scale - rotation-free (the world AABB of a turned
  // pedestal would grow), measured where the pedestal stands (the actor; the plate rides the actor).
  const FBoxSphereBounds Local = PedestalMesh->GetBounds();
  const FVector Scale = ArtBase->GetComponentScale();
  const FVector Centre = ArtBase->GetComponentLocation();
  const float TopZ = static_cast<float>(Centre.Z + (Local.Origin.Z + Local.BoxExtent.Z) * Scale.Z);
  const float RadiusUU = static_cast<float>(0.5 * (Local.BoxExtent.X * Scale.X + Local.BoxExtent.Y * Scale.Y));
  if (RadiusUU <= 1.0f) return;
  // ВР-Z1R-04: the view camera (the BoardCamera view target), not the camera manager's cached POV.
  const FVector CameraPos = AS08BoardActor::ViewCameraLocation(GetWorld());
  const double RestYaw = bDigitRestYawSet ? DigitRestYawDeg : static_cast<double>(FacingYawDeg);
  const float TurnDeg = S08HeroesV2::BaseDigitTurnDeg();
  const S08HeroesV2::FBaseDigitPlacement P =
      S08HeroesV2::BaseDigitPlacement(Centre, TopZ, RadiusUU, CameraPos, RestYaw, TurnDeg);
  if (!BaseDigitMid) {
    if (UMaterialInterface* DiscMaterial = LoadObject<UMaterialInterface>(nullptr,
                                                                          *S08HeroesV2::BaseDigitMaterialPath())) {
      BaseDigitMid = UMaterialInstanceDynamic::Create(DiscMaterial, this);
    }
  }
  if (!BaseDigitMid) return;  // the material asset missing in this build - no digit (fallback, traced by nothing)
  BaseDigitMid->SetVectorParameterValue(TEXT("Color"), FLinearColor::FromSRGBColor(FColor(0x06, 0x16, 0x23)));  // card.navy
  BaseDigitDisc->SetMaterial(0, BaseDigitMid);
  BaseDigitDisc->SetWorldScale3D(P.DiscScale);
  BaseDigitDisc->SetWorldLocationAndRotation(P.DiscCenter, FRotator::ZeroRotator);
  BaseDigitDisc->SetVisibility(true);
  // The digit: runtime text (И-7) in the offline Roboto Bold Condensed, unlit card.cream, flat on the plate.
  UFont* DigitFont = S08BaseDigitFont();
  if (DigitFont && !BaseDigitTextMid) {
    if (UMaterialInterface* TextMaterial = LoadObject<UMaterialInterface>(nullptr,
                                                                          *S08HeroesV2::BaseDigitTextMaterialPath())) {
      BaseDigitTextMid = UMaterialInstanceDynamic::Create(TextMaterial, this);
      BaseDigitTextMid->SetVectorParameterValue(TEXT("Color"),
                                                FLinearColor::FromSRGBColor(FColor(0xF9, 0xEB, 0xDB)));  // card.cream
    }
  }
  const int32 Number = S08HeroesV2::HarpyNumber(Fighter);
  if (DigitFont && BaseDigitTextMid) {
    if (BaseDigitText->Font != DigitFont) BaseDigitText->SetFont(DigitFont);
    if (BaseDigitText->TextMaterial != BaseDigitTextMid) BaseDigitText->SetTextMaterial(BaseDigitTextMid);
    BaseDigitText->SetText(FText::AsNumber(Number));
    BaseDigitText->SetTextRenderColor(FColor(0xF9, 0xEB, 0xDB));  // card.cream (the material reads its own token)
    BaseDigitText->SetWorldSize(P.TextWorldSizeUU);
    BaseDigitText->SetWorldLocationAndRotation(P.TextLocation, P.TextRotation);
    BaseDigitText->SetVisibility(true);
    bBaseDigitDrawable = true;
  } else {
    BaseDigitText->SetVisibility(false);  // the offline font / text material missing - the disc stays, the number not
  }
  // One line per change of the number / side (the spawn, then the rest facing that decides the side).
  const FString TraceKey = FString::Printf(TEXT("%d|%d|%d"), Number, P.Side, bBaseDigitDrawable ? 1 : 0);
  if (TraceKey != BaseDigitTraceKey) {
    BaseDigitTraceKey = TraceKey;
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW basedigit fighter=%s n=%d discUU=%.1f capUU=%.1f topRadiusUU=%.1f side=%d turn=%.0f ")
            TEXT("drawable=%d font=%s"),
        *Fighter.Id, Number, P.DiscDiameterUU, P.CapUU, RadiusUU, P.Side, TurnDeg, bBaseDigitDrawable ? 1 : 0,
        DigitFont ? *DigitFont->GetName() : TEXT("missing")));
  }
}

// ---- AN-32 (ВР-16): the heroMaterials Fix of the light profile ----------------------------------------------

void AS08FighterActor::ApplyHeroMaterials(const FS08HeroMaterialFix* Fix) {
  const bool bLegacy = FParse::Param(FCommandLine::Get(), S08HeroesV2::HeroMatFixLegacyFlagName);
  bHasHeroMaterialFix = Fix != nullptr && !Fix->IsNeutral() && !bLegacy;
  if (bHasHeroMaterialFix) {
    HeroMatClassA = Fix->ClassA;
    HeroMatGainA = Fix->GainA;
    HeroMatSpecA = Fix->SpecA;
    HeroMatClassB = Fix->ClassB;
    HeroMatGainB = Fix->GainB;
    HeroMatSpecB = Fix->SpecB;
  }
  ApplyHeroMaterialMids();
  if (bHeroMatTraced || !bHeroV2Visual || !HeroV2Spec) return;
  bHeroMatTraced = true;
  const FString Sides = bHasHeroMaterialFix
      ? FString::Printf(TEXT("A=%d/%.2f/%.2f B=%d/%.2f/%.2f"), HeroMatClassA, HeroMatGainA, HeroMatSpecA,
                        HeroMatClassB, HeroMatGainB, HeroMatSpecB)
      : FString(TEXT("A=none B=none"));
  FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW heroMat fighter=%s hero=%s look=%s %s"), *Fighter.Id,
                                   HeroV2Spec->Key, S08TeamSlotName(Look), *Sides));
}

void AS08FighterActor::ApplyHeroMaterialMids() {
  if (!bHeroV2Visual || !ArtBody) {
    HeroMaterialMids.Reset();
    return;
  }
  const int32 Slots = ArtBody->GetNumMaterials();
  if (!bHasHeroMaterialFix) {
    // Neutral: the plain material of every slot exactly - unwrap our MIDs where they still sit on a slot.
    if (HeroMaterialMids.Num() > 0) {
      for (int32 Slot = 0; Slot < Slots && Slot < HeroMaterialMids.Num(); ++Slot) {
        UMaterialInstanceDynamic* Mid = HeroMaterialMids[Slot].Get();
        if (Mid && ArtBody->GetMaterial(Slot) == Mid && Mid->Parent) ArtBody->SetMaterial(Slot, Mid->Parent);
      }
      HeroMaterialMids.Reset();
    }
    return;
  }
  HeroMaterialMids.SetNum(Slots);
  for (int32 Slot = 0; Slot < Slots; ++Slot) {
    UMaterialInterface* Current = ArtBody->GetMaterial(Slot);
    UMaterialInstanceDynamic* Mid = HeroMaterialMids[Slot].Get();
    if (Mid && Current != Mid) {
      if (Mid->Parent == Current) {
        // M4: ApplyHeroV2 re-sets the body MI on every snapshot - the cached MID over that same MI goes back on.
        ArtBody->SetMaterial(Slot, Mid);
      } else {
        Mid = nullptr;  // the slot was swapped to another material (dissolve / Place): a MID over the new one
      }
    }
    if (!Mid && Current) {
      Mid = UMaterialInstanceDynamic::Create(Current, this);
      HeroMaterialMids[Slot] = Mid;
      ArtBody->SetMaterial(Slot, Mid);
    }
    if (!Mid) continue;
    Mid->SetScalarParameterValue(TEXT("FixClassA"), static_cast<float>(HeroMatClassA));
    Mid->SetScalarParameterValue(TEXT("FixGainA"), HeroMatGainA);
    Mid->SetScalarParameterValue(TEXT("FixSpecA"), HeroMatSpecA);
    Mid->SetScalarParameterValue(TEXT("FixClassB"), static_cast<float>(HeroMatClassB));
    Mid->SetScalarParameterValue(TEXT("FixGainB"), HeroMatGainB);
    Mid->SetScalarParameterValue(TEXT("FixSpecB"), HeroMatSpecB);
  }
}

int32 AS08FighterActor::GetLungeContactMs(FString& OutSource) const {
  using namespace S08HeroesV2;
  OutSource = TEXT("default");
  if (!bHeroV2Visual || !HeroV2Spec) return -1;
  const UAnimSequenceBase* Lunge = HeroClips.IsValidIndex(static_cast<int32>(EClip::LungeAttack))
      ? HeroClips[static_cast<int32>(EClip::LungeAttack)].Get() : nullptr;
  const float Notify = NotifyContactSeconds(Lunge);
  OutSource = Notify >= 0.0f ? TEXT("notify") : TEXT("profile");
  return FMath::RoundToInt(ContactSeconds(*HeroV2Spec, Lunge) * 1000.0f);
}

FString AS08FighterActor::GetHeroClipAssetName(S08HeroesV2::EClip Clip) const {
  const UAnimSequenceBase* Anim = bHeroV2Visual && HeroClips.IsValidIndex(static_cast<int32>(Clip))
      ? HeroClips[static_cast<int32>(Clip)].Get() : nullptr;
  return Anim ? Anim->GetName() : FString();
}

void AS08FighterActor::PlayHitTint(float Seconds) {
  if (!bHeroV2Visual || !ArtBody || Seconds <= 0.0f) return;
  UWorld* World = GetWorld();
  if (!World) return;
  HitTintStartSeconds = World->GetTimeSeconds();
  HitTintSeconds = Seconds;
  World->GetTimerManager().SetTimer(HitTintTimer, this, &AS08FighterActor::TickHitTint, 1.0f / 60.0f, true);
  TickHitTint();
  FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW hit-tint fighter=%s ms=%d"), *Fighter.Id,
                                   FMath::RoundToInt(Seconds * 1000.0f)));
}

void AS08FighterActor::TickHitTint() {
  UWorld* World = GetWorld();
  if (!World || !ArtBody) return;
  // 01 F-03 (DE: 467-567 ms, bright for the first ~70 ms): full red for 70 ms, then from 0.65 down to 0 at the end.
  const float T = static_cast<float>(World->GetTimeSeconds() - HitTintStartSeconds);
  constexpr float BrightSeconds = 0.07f;
  float Value = 0.0f;
  if (T < BrightSeconds) {
    Value = 1.0f;
  } else if (T < HitTintSeconds) {
    Value = 0.65f * (1.0f - (T - BrightSeconds) / FMath::Max(0.01f, HitTintSeconds - BrightSeconds));
  }
  HitTintValue = Value;
  ArtBody->SetCustomPrimitiveDataFloat(S08HeroesV2::HitTintCpdIndex, Value);
  if (T >= HitTintSeconds) World->GetTimerManager().ClearTimer(HitTintTimer);
}

void AS08FighterActor::OnHeroClipFinished() {
  const S08HeroesV2::EClip Ended = HeroClip;
  NotifyHeroAnimEvent(S08HeroesV2::EEvent::ClipFinished, -1);  // back to Idle
  // AN-25 (ВР-06): the attacker returns to its rest angle when the one-shot clip ends (src=attack-return); a HitReact
  // end returns too (src=hit-return: the attacker of an effect's counter-damage after its flinch - a target that never
  // turned is no change, so no line). The board actor owns the camera / enemy context.
  if ((Ended == S08HeroesV2::EClip::LungeAttack || Ended == S08HeroesV2::EClip::HitReact) &&
      !S08Facing::LegacyRequested() && Fighter.IsAlive() && !bDeathHold && !bMoving) {
    if (AS08BoardActor* Board = Cast<AS08BoardActor>(GetOwner())) {
      Board->FighterReturnToRest(Fighter.Id,
                                 Ended == S08HeroesV2::EClip::LungeAttack ? TEXT("attack-return") : TEXT("hit-return"));
    }
  }
}

void AS08FighterActor::BeginHeroDeath() {
  using namespace S08HeroesV2;
  // The figure stays where it fell: labels, selection / combat markers and the click volume go at once;
  // the pedestal and the team ring stay under the settling figure until it is gone.
  bDeathHold = true;
  StopFacingTurn();  // ВР-06: death never turns (the fall keeps the angle it had)
  bFaceHold = bFacePending = false;
  SetActorEnableCollision(false);
  bIsSelected = false;
  bIsCombatAttacker = false;
  bIsCombatTarget = false;
  Label->SetVisibility(false);
  HpLabel->SetVisibility(false);
  Ring->SetVisibility(false);
  TargetRing->SetVisibility(false);
  TargetIcon->SetVisibility(false);
  NotifyHeroAnimEvent(EEvent::Defeated, -1);
  RefreshHeroLightState();  // ENV-MAPS P9: a defeated fighter's hero light goes (DefeatedMul) as the figure falls
  // DE-019 (01 F-09): DeathSettle -> still (hero 0.3 s, sidekick 0) -> dissolve (hero 0.5 s, sidekick 0.4 s; DE-011
  // MIC, fade by default, ash only with -S08DissolveAsh) -> hidden. A missing MIC hides the figure when the still ends.
  const UAnimSequenceBase* Anim = HeroClips.IsValidIndex(static_cast<int32>(EClip::DeathSettle))
      ? HeroClips[static_cast<int32>(EClip::DeathSettle)].Get() : nullptr;
  const FString MicPath = HeroV2Spec ? DissolveMaterialPath(*HeroV2Spec, Look) : FString();
  DissolveMaterial = MicPath.IsEmpty() ? nullptr : LoadObject<UMaterialInterface>(nullptr, *MicPath);
  if (HeroV2Spec) {
    DeathPlan = MakeDeathPlan(*HeroV2Spec, Anim ? Anim->GetPlayLength() : 0.0f, DissolveMaterial != nullptr);
  } else {
    DeathPlan = FDeathPlan();
    DeathPlan.SettleSeconds = Anim ? Anim->GetPlayLength() : 0.0f;
  }
  DeathStyle = DissolveStyle();
  bDissolving = false;
  DissolveValue = 0.0f;
  UWorld* World = GetWorld();
  DeathFallSeconds = World ? World->GetTimeSeconds() : 0.0;
  FS08Trace::Write(FString::Printf(
      TEXT("ARTPREVIEW anim fighter=%s death hold=%.3f settle=%.3f still=%.3f dissolve=%.3f style=%s mi=%s"),
      *Fighter.Id, DeathPlan.GoneSeconds(), DeathPlan.SettleSeconds, DeathPlan.StillSeconds,
      DeathPlan.DissolveSeconds, DissolveMaterial ? DissolveStyleName(DeathStyle) : TEXT("none"),
      DissolveMaterial ? *DissolveMaterial->GetName() : TEXT("missing")));
  const float StillEnd = DeathPlan.DissolveStartSeconds();
  if (World && StillEnd > 0.0f) {
    World->GetTimerManager().SetTimer(DeathHideTimer, this, &AS08FighterActor::OnDeathStillFinished, StillEnd, false);
  } else if (World) {
    OnDeathStillFinished();
  }
}

bool AS08FighterActor::GetDeathPlan(S08HeroesV2::FDeathPlan& OutPlan, FString& OutStyle) const {
  if (!bDeathHold) return false;
  OutPlan = DeathPlan;
  OutStyle = DissolveMaterial ? S08HeroesV2::DissolveStyleName(DeathStyle) : TEXT("none");
  return true;
}

void AS08FighterActor::OnDeathStillFinished() {
  using namespace S08HeroesV2;
  if (!bDeathHold) return;
  if (DeathPlan.DissolveSeconds <= 0.0f || !DissolveMaterial || !ArtBody) {
    // cue-table CUE-013 fallback: no dissolve material - the figure hides when the still ends.
    FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW anim fighter=%s death dissolve=missing fallback=hide"),
                                     *Fighter.Id));
    OnDeathHoldFinished();
    return;
  }
  // The dissolve MIC is a child of the body MI (DE-011): the look is identical at progress 0, then the figure
  // dissolves; the pedestal greys out with the same progress (CPD_Fade) and goes with the figure.
  for (int32 Slot = 0; Slot < ArtBody->GetNumMaterials(); ++Slot) ArtBody->SetMaterial(Slot, DissolveMaterial);
  ApplyHeroMaterialMids();  // AN-32: the fix rides the dissolve MIC too
  bDissolving = true;
  DissolveValue = 0.0f;
  SetDissolve(ArtBody, ArtBase, 0.0f, DeathStyle);
  UpdateBaseDigit();  // AN-31: the digit hides from the start of the dissolve
  FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW anim fighter=%s death dissolve ms=%d style=%s mi=%s"), *Fighter.Id,
                                   FMath::RoundToInt(DeathPlan.DissolveSeconds * 1000.0f),
                                   DissolveStyleName(DeathStyle), *DissolveMaterial->GetName()));
  if (UWorld* World = GetWorld()) {
    World->GetTimerManager().SetTimer(DissolveTimer, this, &AS08FighterActor::TickDissolve, 1.0f / 60.0f, true);
  }
}

void AS08FighterActor::TickDissolve() {
  UWorld* World = GetWorld();
  if (!World) return;
  StepDissolve(static_cast<float>(World->GetTimeSeconds() - DeathFallSeconds));
}

void AS08FighterActor::StepDissolve(float SecondsSinceFall) {
  if (!bDissolving) return;
  DissolveValue = S08HeroesV2::DissolveProgressAt(DeathPlan, SecondsSinceFall);
  S08HeroesV2::SetDissolve(ArtBody, ArtBase, DissolveValue, DeathStyle);
  if (DissolveValue >= 1.0f) OnDeathHoldFinished();
}

void AS08FighterActor::AdvanceDeathForTest(float SecondsSinceFall) {
  if (!bDeathHold) return;
  if (!bDissolving && SecondsSinceFall >= DeathPlan.DissolveStartSeconds()) {
    if (UWorld* World = GetWorld()) World->GetTimerManager().ClearTimer(DeathHideTimer);
    OnDeathStillFinished();
  }
  StepDissolve(SecondsSinceFall);
}

void AS08FighterActor::OnDeathHoldFinished() {
  UWorld* World = GetWorld();
  if (World) {
    World->GetTimerManager().ClearTimer(DissolveTimer);
    World->GetTimerManager().ClearTimer(DeathHideTimer);
  }
  const double AfterFall = World ? World->GetTimeSeconds() - DeathFallSeconds : 0.0;
  bDeathHold = false;
  bDeathDone = true;
  bDissolving = false;
  if (!Fighter.IsAlive()) {
    SetActorHiddenInGame(true);
    SetActorEnableCollision(false);
  }
  RefreshHeroLightState();
  FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW anim fighter=%s death hidden=%d afterFall=%.3f plan=%.3f"),
                                   *Fighter.Id, Fighter.IsAlive() ? 0 : 1, AfterFall, DeathPlan.GoneSeconds()));
}

void AS08FighterActor::SetScreenIconMode(bool bScreen) {
  if (bScreenIconMode == bScreen) return;
  bScreenIconMode = bScreen;
  TargetIcon->SetVisibility(bIsCombatTarget && bArtTargetIconLoaded && !bScreenIconMode);
}

void AS08FighterActor::SetSelected(bool bSelected) {
  bIsSelected = bSelected && !bDeathHold;
  LastLabelRatio = -1.0f;
  Ring->SetVisibility(bIsSelected || (bArtSelectionRingLoaded && bIsCombatAttacker));
  if (bIsSelected && bArtSelectionRingLoaded) {
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW selection ring shown fighter=%s mesh=%s"),
        *Fighter.Name, *Ring->GetStaticMesh()->GetName()));
  }
  RefreshHeroLightState();
}

void AS08FighterActor::SetCombatMarkers(bool bAttacker, bool bTarget) {
  const bool bNewAttacker = bArtSelectionRingLoaded && bAttacker && Fighter.IsAlive();
  const bool bNewTarget = bArtTargetRingLoaded && bTarget && Fighter.IsAlive();
  if (bIsCombatAttacker == bNewAttacker && bIsCombatTarget == bNewTarget) return;
  bIsCombatAttacker = bNewAttacker;
  bIsCombatTarget = bNewTarget;
  Ring->SetVisibility(bIsSelected || bIsCombatAttacker);
  TargetRing->SetVisibility(bIsCombatTarget);
  RefreshHeroLightState();
  TargetIcon->SetVisibility(bIsCombatTarget && bArtTargetIconLoaded && !bScreenIconMode);
  // icon=1 means "the target icon is bound to this fighter"; iconMode says
  // whether the world billboard or the exact-size HUD icon (T2.2) draws it.
  FS08Trace::Write(FString::Printf(
      TEXT("ARTPREVIEW combat marker fighter=%s attacker=%d target=%d icon=%d targetMesh=%s iconMode=%s "
           "targetArcScaleXY=%.3f"),
      *Fighter.Name, bIsCombatAttacker ? 1 : 0, bIsCombatTarget ? 1 : 0,
      bIsCombatTarget && bArtTargetIconLoaded ? 1 : 0,
      TargetRing->GetStaticMesh() ? *TargetRing->GetStaticMesh()->GetName()
                                  : TEXT("none"),
      bScreenIconMode ? TEXT("screen") : TEXT("world"), TargetRing->GetRelativeScale3D().X));
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
  ApplyLabelVisibility();
}

void AS08FighterActor::SetLabelMode(ES08FighterLabelMode Mode) {
  if (LabelMode == Mode) return;
  LabelMode = Mode;
  ApplyLabelVisibility();
}

void AS08FighterActor::SetWorldLabelsSuppressed(bool bSuppressed) {
  if (bWorldLabelsSuppressed == bSuppressed) return;
  bWorldLabelsSuppressed = bSuppressed;
  ApplyLabelVisibility();
}

void AS08FighterActor::ApplyLabelVisibility() {
  if (bWorldLabelsSuppressed || bDeathHold) {
    Label->SetVisibility(false);
    HpLabel->SetVisibility(false);
    return;
  }
  const float Ratio = LastLabelRatio > 0.0f ? LastLabelRatio : 1.0f;
  if (LabelMode == ES08FighterLabelMode::Compact) {
    // One short line "Label HP" at the name height: neighbours of the plate
    // owner stay identifiable at K2 without two stacked lines per figure.
    Label->SetText(S08ArtHudText::CompactLabel(Fighter.Label, Fighter.Health, Fighter.MaxHealth));
    Label->SetWorldSize(FMath::Min(BaseNameWorldSize, BaseHpWorldSize) * 0.85f * Ratio);
    Label->SetVisibility(true);
    HpLabel->SetVisibility(false);
    return;
  }
  Label->SetText(FText::FromString(Fighter.Label));
  HpLabel->SetText(S08ArtHudText::HpLabel(Fighter.Health, Fighter.MaxHealth));
  Label->SetWorldSize(BaseNameWorldSize * Ratio);
  HpLabel->SetWorldSize(BaseHpWorldSize * Ratio);
  const bool bShow = LabelMode == ES08FighterLabelMode::Full && (!bLastOnlySelected || bIsSelected);
  Label->SetVisibility(bShow);
  HpLabel->SetVisibility(bShow);
}

bool AS08FighterActor::GetVisibleLabelBox(FBox& OutBox) const {
  OutBox = FBox(ForceInit);
  if (IsHidden()) return false;
  const UTextRenderComponent* Texts[2] = {Label.Get(), HpLabel.Get()};
  for (const UTextRenderComponent* Text : Texts) {
    if (Text && Text->IsVisible()) OutBox += Text->Bounds.GetBox();
  }
  return OutBox.IsValid != 0;
}

float AS08FighterActor::GetFigureHeightUU() const {
  return FigureHeightUU;
}

bool AS08FighterActor::IsBaseVisible() const { return Base && Base->IsVisible(); }

bool AS08FighterActor::IsTeamRingVisible() const { return TeamRing && TeamRing->IsVisible(); }

const UStaticMesh* AS08FighterActor::GetTeamRingMesh() const { return TeamRing ? TeamRing->GetStaticMesh() : nullptr; }

FVector AS08FighterActor::GetTeamRingScale() const {
  return TeamRing ? TeamRing->GetRelativeScale3D() : FVector::ZeroVector;
}

// ---- ENV-MAPS P9 hero light (S08HeroLight.h, docs/art-pipeline/ENV-HERO-LIGHT.md) ----------------------------------

void AS08FighterActor::ApplyHeroLight(const FS08HeroLightSpec* Spec, int32 LayerCount, bool bFrozen) {
  using namespace S08HeroLightSpec;
  bHeroLightFrozen = bFrozen;
  const bool bOn = Spec && Spec->bSet && Spec->bEnabled && LayerCount > 0 && Spec->Layers() > 0;
  if (!bOn) {
    for (USpotLightComponent* Light : HeroLights) {
      if (Light) Light->SetVisibility(false);
    }
    HeroLightLayers = 0;
    HeroLightRigKey.Reset();
    SetHeroLitChannels(false, false);
    RefreshHeroLightState();
    return;
  }
  HeroLightSpec = *Spec;
  const int32 Want = FMath::Clamp(FMath::Min(LayerCount, Spec->Layers()), 0, MaxLightsPerFigure);
  const float Height = GetFigureHeightUU();
  const FString RigKey = FString::Printf(TEXT("%s|%d|%.2f"), *Spec->Signature(), Want, Height);
  if (RigKey != HeroLightRigKey) {
    HeroLightRigKey = RigKey;
    HeroLightLayers = Want;
    HeroLightPhase = static_cast<float>(GetTypeHash(Fighter.Id) % 997u) / 997.0f * 2.0f * UE_PI;
    HeroLights.SetNum(MaxLightsPerFigure);
    HeroLightBaseCd.Init(0.0f, MaxLightsPerFigure);
    FString Placed;
    for (int32 I = 0; I < MaxLightsPerFigure; ++I) {
      const FS08HeroLightLayer& Layer = I == 0 ? Spec->Key : Spec->Rim;
      if (I >= Want || !Layer.bSet) {
        if (HeroLights[I]) HeroLights[I]->SetVisibility(false);
        continue;
      }
      USpotLightComponent* Light = HeroLights[I];
      if (!Light) {
        // A child of the fighter: it follows every move and hides with the actor. Channel 1 only, never a shadow map
        // (ShadowResolutionScale 0: a layer with contact shadows only traces the screen-space contact ray), no GI /
        // volumetric / translucency share (the translucency volume and the Lumen surface cache ignore the channels).
        Light = NewObject<USpotLightComponent>(this, I == 0 ? TEXT("HeroLightKey") : TEXT("HeroLightRim"));
        Light->SetupAttachment(RootComponent);
        Light->SetMobility(EComponentMobility::Movable);
        Light->SetIntensityUnits(ELightUnits::Candelas);
        Light->SetCastShadows(false);
        Light->ShadowResolutionScale = 0.0f;
        Light->ContactShadowLengthInWS = false;
        Light->SetLightingChannels(false, true, false);
        Light->SetIndirectLightingIntensity(0.0f);
        Light->SetVolumetricScatteringIntensity(0.0f);
        Light->SetAffectTranslucentLighting(false);
        Light->SetAffectGlobalIllumination(false);
        Light->bUseInverseSquaredFalloff = true;
        Light->RegisterComponent();
        HeroLights[I] = Light;
      }
      const FS08HeroLightPlacement P = S08HeroLight::Place(*Spec, Layer, Height);
      Light->SetRelativeLocationAndRotation(P.Location, P.Rotation);
      Light->SetLightColor(Layer.Linear());
      Light->SetInnerConeAngle(Layer.InnerConeDeg);
      Light->SetOuterConeAngle(Layer.OuterConeDeg);
      Light->SetAttenuationRadius(P.AttenuationRadiusUU);
      // P9b: less sheen on the PBR figures, and the layer's own screen-space contact shadows (wings / arms / folds occlude
      // it). Contact shadows need a shadow-casting light (DeferredLightingCommon.ush: ShadowedBits > 1); with
      // ShadowResolutionScale 0 the renderer never allocates a shadow map for it (ShadowSetup.cpp early-out).
      Light->SetSpecularScale(Layer.SpecularScale);
      const bool bContact = Layer.HasContactShadow();
      if (Light->ContactShadowLength != Layer.ContactShadowLength || Light->ShadowResolutionScale != 0.0f) {
        Light->ContactShadowLength = Layer.ContactShadowLength;
        Light->ShadowResolutionScale = 0.0f;
        Light->MarkRenderStateDirty();
      }
      Light->SetCastShadows(bContact);
      HeroLightBaseCd[I] = P.Candelas;
      Placed += FString::Printf(TEXT(" %s=(%.0f,%.0f,%.0f)d%.0f/%.3fcd/r%.0f/cone%.0f-%.0f/#%s/spec%.2f/contact%.3f"),
                                I == 0 ? TEXT("key") : TEXT("rim"), P.Location.X, P.Location.Y, P.Location.Z, P.DistanceUU,
                                P.Candelas, P.AttenuationRadiusUU, Layer.InnerConeDeg, Layer.OuterConeDeg,
                                *Layer.ColorSrgb.ToHex().Left(6), Layer.SpecularScale, Layer.ContactShadowLength);
    }
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW hero-light rig fighter=%s layers=%d height=%.1f channel=%d shadowMaps=0 indirect=0 translucency=0 pedestal=%d key=%.2flux rim=%.2flux%s"),
        *Fighter.Id, Want, Height, Channel, Spec->bLitPedestal ? 1 : 0, Spec->Key.bSet ? Spec->Key.Lux : 0.0f,
        Spec->Rim.bSet && Want > 1 ? Spec->Rim.Lux : 0.0f, *Placed));
  }
  SetHeroLitChannels(true, Spec->bLitPedestal);
  RefreshHeroLightState();
}

void AS08FighterActor::SetHeroLitChannels(bool bLit, bool bPedestal) {
  const bool bPedestalLit = bLit && bPedestal;
  if (bHeroLitChannels == bLit && bHeroLitPedestal == bPedestalLit) return;
  bHeroLitChannels = bLit;
  bHeroLitPedestal = bPedestalLit;
  // the figure takes the scene light (channel 0) and, while a rig is on, the hero light (channel 1); the pedestal only
  // with "litPedestal" (P9b: a lit pedestal turned into a cream disk, the brightest part of the figure); rings, labels,
  // the readability blob / pip and every board / environment primitive stay on channel 0 only
  for (UPrimitiveComponent* Figure : {static_cast<UPrimitiveComponent*>(ArtBody.Get()), static_cast<UPrimitiveComponent*>(ArtPlaceholder.Get()),
                                      static_cast<UPrimitiveComponent*>(Body.Get())}) {
    if (Figure) Figure->SetLightingChannels(true, bLit, false);
  }
  if (ArtBase) ArtBase->SetLightingChannels(true, bPedestalLit, false);
}

TArray<const UPrimitiveComponent*> AS08FighterActor::GetHeroLitPrimitives() const {
  TArray<const UPrimitiveComponent*> Out = {ArtBody.Get(), ArtPlaceholder.Get(), Body.Get()};
  if (bHeroLitPedestal) Out.Add(ArtBase.Get());
  return Out;
}

const UPrimitiveComponent* AS08FighterActor::GetHeroPedestal() const { return ArtBase.Get(); }

int32 AS08FighterActor::GetHeroLightCount() const {
  int32 N = 0;
  for (const USpotLightComponent* Light : HeroLights) N += Light && Light->IsVisible() ? 1 : 0;
  return N;
}

const USpotLightComponent* AS08FighterActor::GetHeroLight(int32 Layer) const {
  return HeroLights.IsValidIndex(Layer) ? HeroLights[Layer].Get() : nullptr;
}

ES08HeroLightState AS08FighterActor::ComputeHeroLightState() const {
  if (HeroLightLayers <= 0) return ES08HeroLightState::Off;
  if (!Fighter.IsAlive() || bDeathHold) return ES08HeroLightState::Defeated;
  // "whose turn / selected" (ENV-HERO-LIGHT.md): the selected fighter or the attacker of the combat focus
  if (bIsSelected || bIsCombatAttacker) return ES08HeroLightState::Active;
  return ES08HeroLightState::Idle;
}

void AS08FighterActor::RefreshHeroLightState() {
  HeroLightState = ComputeHeroLightState();
  ApplyHeroLightIntensity();
  const bool bPulse = HeroLightState == ES08HeroLightState::Active && !bHeroLightFrozen && HeroLightSpec.BreathHz > 0.0f &&
                      HeroLightSpec.BreathAmp > 0.0f;
  if (UWorld* World = GetWorld()) {
    FTimerManager& Timers = World->GetTimerManager();
    if (bPulse && !Timers.IsTimerActive(HeroLightPulseTimer)) {
      Timers.SetTimer(HeroLightPulseTimer, this, &AS08FighterActor::OnHeroLightPulse, S08HeroLightSpec::PulseTickS, true);
    } else if (!bPulse) {
      Timers.ClearTimer(HeroLightPulseTimer);
    }
  }
  const FString TraceKey = FString::Printf(TEXT("%s|%d"), S08HeroLightStateName(HeroLightState), HeroLightLayers);
  if (TraceKey == HeroLightTraceKey || (HeroLightTraceKey.IsEmpty() && HeroLightState == ES08HeroLightState::Off)) return;
  HeroLightTraceKey = TraceKey;
  const FString Pulse = bPulse ? FString::Printf(TEXT("%.2fHz+-%.0f%%"), HeroLightSpec.BreathHz, HeroLightSpec.BreathAmp * 100.0f)
                               : FString(bHeroLightFrozen && HeroLightState == ES08HeroLightState::Active ? TEXT("frozen")
                                                                                                         : TEXT("none"));
  FS08Trace::Write(FString::Printf(
      TEXT("ARTPREVIEW hero-light fighter=%s state=%s layers=%d lightsOn=%d keyCd=%.3f rimCd=%.3f mul=%.3f pulse=%s"),
      *Fighter.Id, S08HeroLightStateName(HeroLightState), HeroLightLayers, GetHeroLightCount(),
      HeroLightBaseCd.IsValidIndex(0) ? HeroLightBaseCd[0] * HeroLightMul : 0.0f,
      HeroLightBaseCd.IsValidIndex(1) ? HeroLightBaseCd[1] * HeroLightMul : 0.0f, HeroLightMul, *Pulse));
}

void AS08FighterActor::ApplyHeroLightIntensity() {
  const UWorld* World = GetWorld();
  const double T = World ? World->GetTimeSeconds() : 0.0;
  HeroLightMul = HeroLightLayers > 0
      ? S08HeroLight::StateMultiplier(HeroLightSpec, HeroLightState, T, bHeroLightFrozen, HeroLightPhase)
      : 0.0f;
  for (int32 I = 0; I < HeroLights.Num(); ++I) {
    USpotLightComponent* Light = HeroLights[I];
    if (!Light) continue;
    const float BaseCd = HeroLightBaseCd.IsValidIndex(I) ? HeroLightBaseCd[I] : 0.0f;
    const bool bVisible = I < HeroLightLayers && BaseCd > 0.0f && HeroLightMul > 0.0f;
    if (bVisible) Light->SetIntensity(BaseCd * HeroLightMul);
    if (Light->IsVisible() != bVisible) Light->SetVisibility(bVisible);
  }
}

void AS08FighterActor::OnHeroLightPulse() {
  if (HeroLightState != ES08HeroLightState::Active || bHeroLightFrozen) {
    if (UWorld* World = GetWorld()) World->GetTimerManager().ClearTimer(HeroLightPulseTimer);
    return;
  }
  ApplyHeroLightIntensity();
}
