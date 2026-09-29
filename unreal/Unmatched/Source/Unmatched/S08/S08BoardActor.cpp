#include "S08BoardActor.h"
#include "S08ArtPreviewMedusa.h"
#include "S08FighterActor.h"
#include "S08TraceLog.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/SceneComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/PointLight.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "Materials/Material.h"
#include "Materials/MaterialInterface.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "UObject/ConstructorHelpers.h"

namespace {
UMaterialInterface* LoadTileMaterial() {
  static UMaterialInterface* Cached = LoadObject<UMaterialInterface>(
      nullptr, TEXT("/Game/S08/M_S08_Tile.M_S08_Tile"));
  return Cached ? Cached
                : LoadObject<UMaterialInterface>(
                      nullptr, TEXT("/Engine/BasicShapes/BasicShapeMaterial"));
}

// T3.2: the Cobble-only SupportsCobbleArt (5x6, one blue/red zone per cell)
// became data: FS08BoardArtData::Select picks a profile per board row id or
// boardState signature, S08BuildZoneMarks lays out any zone keys/multizones.
constexpr float ArtTileScaleXY = 0.92f;  // 'tiles' surface: 8 uu stone groove
constexpr float ArtFrameUU = 24.0f;      // 'tiles' surface: wood frame width

FString ZoneComponentName(const FString& Key) {
  FString Safe;
  for (const TCHAR C : Key) Safe.AppendChar(FChar::IsAlnum(C) ? C : TEXT('_'));
  return TEXT("ArtZone_") + Safe;
}
} // namespace

AS08BoardActor::AS08BoardActor() {
  PrimaryActorTick.bCanEverTick = false;
  RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));

  static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeFinder(
      TEXT("/Engine/BasicShapes/Cube.Cube"));
  UStaticMesh* Cube = CubeFinder.Object;

  NormalTiles = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("NormalTiles"));
  NormalTiles->SetupAttachment(RootComponent);
  NormalTiles->SetStaticMesh(Cube);
  NormalTiles->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
  NormalTiles->SetCollisionResponseToChannel(ECC_Visibility, ECR_Block);

  BlockerTiles = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("BlockerTiles"));
  BlockerTiles->SetupAttachment(RootComponent);
  BlockerTiles->SetStaticMesh(Cube);
  BlockerTiles->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
  BlockerTiles->SetCollisionResponseToChannel(ECC_Visibility, ECR_Block);

  UnderlayTiles = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("UnderlayTiles"));
  UnderlayTiles->SetupAttachment(RootComponent);
  UnderlayTiles->SetStaticMesh(Cube);
  UnderlayTiles->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
  UnderlayTiles->SetCollisionResponseToChannel(ECC_Visibility, ECR_Block);

  ArtBoard = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("ArtBoard"));
  ArtBoard->SetupAttachment(RootComponent);
  ArtBoard->SetCollisionEnabled(ECollisionEnabled::NoCollision);
  ArtBoard->SetVisibility(false);

  ArtCorners = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("ArtCorners"));
  ArtCorners->SetupAttachment(RootComponent);
  ArtCorners->SetCollisionEnabled(ECollisionEnabled::NoCollision);
  ArtCorners->SetVisibility(false);


  ArtZoneGlyphs = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("ArtZoneGlyphs"));
  ArtZoneGlyphs->SetupAttachment(RootComponent);
  ArtZoneGlyphs->SetStaticMesh(Cube);
  ArtZoneGlyphs->SetCollisionEnabled(ECollisionEnabled::NoCollision);
  ArtZoneGlyphs->SetVisibility(false);
}

void AS08BoardActor::BeginPlay() {
  Super::BeginPlay();
  if (UMaterialInterface* Tile = LoadTileMaterial()) {
    GreyTileMaterial = Tile;
    NormalTiles->SetMaterial(0, Tile);
    GreyBlockerMaterial = UMaterialInstanceDynamic::Create(Tile, this);
    GreyBlockerMaterial->SetVectorParameterValue(TEXT("Tint"), FLinearColor(0.22f, 0.22f, 0.24f));
    BlockerTiles->SetMaterial(0, GreyBlockerMaterial);
    GreyUnderlayMaterial = UMaterialInstanceDynamic::Create(Tile, this);
    GreyUnderlayMaterial->SetVectorParameterValue(TEXT("Tint"), FLinearColor(0.07f, 0.07f, 0.09f));
    UnderlayTiles->SetMaterial(0, GreyUnderlayMaterial);
    // 'tiles' art surface: near-black unlit underlay so the stone grooves and
    // the non-space (obstacle) cells read as voids under the lit slabs.
    ArtVoidMaterial = UMaterialInstanceDynamic::Create(Tile, this);
    ArtVoidMaterial->SetVectorParameterValue(TEXT("Tint"), FLinearColor(0.012f, 0.012f, 0.016f));
  }
  if (!FParse::Param(FCommandLine::Get(), TEXT("ArtPreview"))) return;

  // T3.2 board data: zone palette/glyphs per key, light profiles, board
  // profiles. Without valid data no board gets art (grey board, traced).
  {
    TArray<FString> Errors;
    bArtDataLoaded = ArtData.LoadFile(FS08BoardArtData::DefaultPath(), Errors);
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW board profiles loaded=%d revision=%d boards=%d zoneStyles=%d lightProfiles=%d errors=%d path=Config/ArtBoards/S08ArtBoardProfiles.json"),
        bArtDataLoaded ? 1 : 0, ArtData.Revision, ArtData.Boards.Num(), ArtData.ZoneStyles.Num(),
        ArtData.Lights.Num(), Errors.Num()));
    for (int32 I = 0; I < Errors.Num() && I < 8; ++I) {
      FS08Trace::Write(TEXT("ARTPREVIEW board profiles error: ") + Errors[I]);
    }
    if (!bArtDataLoaded) {
      UE_LOG(LogTemp, Warning, TEXT("ARTPREVIEW board profiles invalid; keeping grey board"));
      FS08Trace::Write(TEXT("ARTPREVIEW board profiles invalid; keeping grey board"));
      return;
    }
  }

  UStaticMesh* Board = LoadObject<UStaticMesh>(nullptr,
      TEXT("/Game/ArtTests/ART005F/Meshes/SM_ART005_BoardStoneV4_WoodUV"));
  UStaticMesh* Corner = LoadObject<UStaticMesh>(nullptr,
      TEXT("/Game/ArtTests/ART005H/Meshes/SM_ART005_CornerBracket_v1"));
  UMaterialInterface* Stone = LoadObject<UMaterialInterface>(nullptr,
      TEXT("/Game/ArtTests/ART005E/Materials/M_ART005E_Stone_DiffuseOnly_v4"));
  UMaterialInterface* Wood = LoadObject<UMaterialInterface>(nullptr,
      TEXT("/Game/ArtTests/ART005G/Materials/M_ART005G_Wood_DiffuseOnly"));
  UMaterialInterface* Iron = LoadObject<UMaterialInterface>(nullptr,
      TEXT("/Game/ArtTests/ART005H/Materials/M_ART005H_IronCorner_Review"));
  UMaterialInterface* Glyph = LoadObject<UMaterialInterface>(nullptr,
      TEXT("/Game/ArtTests/ART005/Materials/M_ART005_ZoneGlyph_Review"));
  const FS08MedusaCandidate MedusaCandidate = S08SelectMedusaCandidate();
  USkeletalMesh* Medusa = MedusaCandidate.MeshPath
      ? LoadObject<USkeletalMesh>(nullptr, MedusaCandidate.MeshPath)
      : nullptr;
  UStaticMesh* Pedestal = LoadObject<UStaticMesh>(nullptr,
      TEXT("/Game/ArtPreview/Medusa/Meshes/SM_Medusa_Base_v2Candidate"));
  UMaterialInterface* TeamBlue = LoadObject<UMaterialInterface>(nullptr,
      TEXT("/Game/ArtPreview/Medusa/Materials/MI_Medusa_Blue"));
  UMaterialInterface* TeamRed = LoadObject<UMaterialInterface>(nullptr,
      TEXT("/Game/ArtPreview/Medusa/Materials/MI_Medusa_Red"));
  // Zone colours: the blue/red review materials of the Cobble data plus the
  // unlit 'Tint' material for every other key (FLinearColor(FColor) = sRGB).
  for (const TPair<FString, FS08ZoneStyle>& Style : ArtData.ZoneStyles) {
    if (Style.Value.MaterialPath.IsEmpty()) continue;
    if (UMaterialInterface* M = LoadObject<UMaterialInterface>(nullptr, *Style.Value.MaterialPath)) {
      ArtZoneMaterials.Add(Style.Key, M);
    } else {
      FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW zone material missing key=%s path=%s (tint fallback)"),
                                       *Style.Key, *Style.Value.MaterialPath));
    }
  }
  ArtSolidMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/S08/M_S08_Solid.M_S08_Solid"));
  ArtStoneTileMaterial = LoadObject<UMaterialInterface>(nullptr,
      TEXT("/Game/ArtTests/ART005/Materials/M_ART005_Stone_Probe"));
  ArtWoodMaterial = LoadObject<UMaterialInterface>(nullptr,
      TEXT("/Game/ArtTests/ART005/Materials/M_ART005_Wood_Probe"));
  const bool bShared = Corner && Iron && Glyph && ArtSolidMaterial;
  const bool bMedusa = Medusa && Medusa->GetSkeleton() && Pedestal && TeamBlue && TeamRed;
  if (!bShared || !bMedusa) {
    UE_LOG(LogTemp, Warning, TEXT("ARTPREVIEW Cobble assets missing; keeping grey board"));
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW Cobble assets missing medusaVariant=%s requested=%s medusa=%d; keeping grey board"),
        MedusaCandidate.Variant, *MedusaCandidate.Requested, bMedusa ? 1 : 0));
    return;
  }
  bCobbleMeshReady = false;
  if (Board && Stone && Wood) {
    const int32 StoneSlot = Board->GetMaterialIndex(TEXT("M_ART005_Stone_AtlasB_Provisional"));
    const int32 WoodSlot = Board->GetMaterialIndex(TEXT("M_ART005_Wood_Provisional"));
    if (StoneSlot >= 0 && WoodSlot >= 0) {
      ArtBoard->SetStaticMesh(Board);
      ArtBoard->SetRelativeRotation(FRotator(0.0f, -90.0f, 0.0f));
      ArtBoard->SetMaterial(StoneSlot, Stone);
      ArtBoard->SetMaterial(WoodSlot, Wood);
      bCobbleMeshReady = true;
    } else {
      UE_LOG(LogTemp, Warning, TEXT("ARTPREVIEW Cobble material slots changed; no cobble-5x6-mesh surface"));
    }
  }
  bTileArtReady = ArtStoneTileMaterial && ArtWoodMaterial && ArtVoidMaterial;
  if (!bCobbleMeshReady && !bTileArtReady) {
    FS08Trace::Write(TEXT("ARTPREVIEW board surfaces missing cobbleMesh=0 tiles=0; keeping grey board"));
    return;
  }
  ArtCorners->SetStaticMesh(Corner);
  ArtCorners->SetMaterial(0, Iron);
  ArtZoneGlyphs->SetMaterial(0, Glyph);
  bArtAssetsReady = true;
  if (bCobbleMeshReady) {
    UE_LOG(LogTemp, Display, TEXT("ARTPREVIEW Cobble assets ready"));
    FS08Trace::Write(TEXT("ARTPREVIEW Cobble assets ready"));
  }
  FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW board assets ready cobbleMesh=%d tiles=%d zoneMaterials=%d"),
                                   bCobbleMeshReady ? 1 : 0, bTileArtReady ? 1 : 0, ArtZoneMaterials.Num()));
  FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW medusa candidate variant=%s mesh=%s requested=%s"),
                                   MedusaCandidate.Variant, *Medusa->GetName(),
                                   *MedusaCandidate.Requested));
}

void AS08BoardActor::EndPlay(const EEndPlayReason::Type Reason) {
  ClearArtLights();
  ClearArtSurface();
  ClearChildren();
  Super::EndPlay(Reason);
}

AS08FighterActor* AS08BoardActor::FindFighterActor(const FString& FighterId) const {
  for (AS08FighterActor* Actor : FighterActors) {
    if (Actor && Actor->GetFighterId() == FighterId) return Actor;
  }
  return nullptr;
}

void AS08BoardActor::SetFighterLabelZoomRatio(float DistanceRatio,
                                             bool bOnlySelected) {
  for (AS08FighterActor* Actor : FighterActors) {
    if (Actor) Actor->SetLabelZoomRatio(DistanceRatio, bOnlySelected);
  }
}

void AS08BoardActor::SetLabelPresentation(const FString& PlateFighterId) {
  LabelPlateFighterId = PlateFighterId;
  for (AS08FighterActor* Actor : FighterActors) {
    if (!Actor) continue;
    Actor->SetLabelMode(PlateFighterId.IsEmpty() ? ES08FighterLabelMode::Full
                        : Actor->GetFighterId() == PlateFighterId ? ES08FighterLabelMode::Hidden
                                                                  : ES08FighterLabelMode::Compact);
  }
}

void AS08BoardActor::SetScreenIconMode(bool bScreen) {
  bScreenIconMode = bScreen;
  for (AS08FighterActor* Actor : FighterActors) {
    if (Actor) Actor->SetScreenIconMode(bScreen);
  }
}

bool AS08BoardActor::GetDamageNumberWorldBox(const FString& FighterId, FBox& OutBox) const {
  const TWeakObjectPtr<AActor>* Number = DamageNumbers.Find(FighterId);
  if (!Number || !Number->IsValid()) return false;
  const USceneComponent* Root = Number->Get()->GetRootComponent();
  if (!Root) return false;
  OutBox = Root->Bounds.GetBox();
  return OutBox.IsValid != 0;
}

TArray<FString> AS08BoardActor::GetActiveDamageNumberIds() const {
  TArray<FString> Out;
  for (const TPair<FString, TWeakObjectPtr<AActor>>& Entry : DamageNumbers) {
    if (Entry.Value.IsValid()) Out.Add(Entry.Key);
  }
  return Out;
}

void AS08BoardActor::SetCombatFocus(const FString& AttackerId,
                                   const FString& TargetId) {
  CombatAttackerId = AttackerId;
  CombatTargetId = TargetId;
  for (AS08FighterActor* Actor : FighterActors) {
    if (Actor) {
      Actor->SetCombatMarkers(Actor->GetFighterId() == CombatAttackerId,
                              Actor->GetFighterId() == CombatTargetId);
    }
  }
}

void AS08BoardActor::ShowDamageNumber(const FString& FighterId, int32 Damage,
                                     int32 SequenceNumber) {
  if (!bArtActive || Damage <= 0) return;
  const FS08BoardFighter* Target = Fighters.FindByPredicate(
      [&](const FS08BoardFighter& Fighter) { return Fighter.Id == FighterId; });
  if (!Target) return;
  if (!DamageDedupe.Accept(FighterId, SequenceNumber)) {
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW damage-number duplicate ignored fighter=%s amount=%d seq=%d"),
        *FighterId, Damage, SequenceNumber));
    return;
  }

  if (TWeakObjectPtr<AActor>* Old = DamageNumbers.Find(FighterId)) {
    if (Old->IsValid()) Old->Get()->Destroy();
  }
  const FVector Position = BoardModel.CellToWorld(Target->X, Target->Y) +
      FVector(Target->X == BoardModel.Width - 1 ? -20.0f : 20.0f,
              40.0f, Target->bIsHero ? 105.0f : 83.0f);
  AActor* Number = GetWorld()->SpawnActor<AActor>(AActor::StaticClass(),
                                                  Position, FRotator::ZeroRotator);
  if (!Number) return;
  UTextRenderComponent* Text = NewObject<UTextRenderComponent>(Number, TEXT("DamageNumber"));
  Number->SetRootComponent(Text);
  Text->SetText(FText::FromString(FString::Printf(TEXT("-%d"), Damage)));
  Text->SetHorizontalAlignment(EHTA_Center);
  Text->SetWorldSize(25.0f);
  Text->SetTextRenderColor(FColor(255, 224, 175));
  Text->SetCollisionEnabled(ECollisionEnabled::NoCollision);
  Text->RegisterComponent();
  Number->SetActorLocation(Position);
  Number->SetActorRotation(FRotator(0.0f, 90.0f, 0.0f));
  Number->SetLifeSpan(0.9f);
  DamageNumbers.Add(FighterId, Number);
  FS08Trace::Write(FString::Printf(
      TEXT("ARTPREVIEW damage-number fighter=%s amount=%d seq=%d cell=(%d,%d)"),
      *FighterId, Damage, SequenceNumber, Target->X, Target->Y));
}

void AS08BoardActor::ClearChildren() {
  for (const TPair<FString, TWeakObjectPtr<AActor>>& Entry : DamageNumbers) {
    if (Entry.Value.IsValid()) Entry.Value.Get()->Destroy();
  }
  DamageNumbers.Reset();
  for (AActor* Child : HighlightTiles) {
    if (Child) Child->Destroy();
  }
  HighlightTiles.Reset();
  if (IllegalCell) {
    IllegalCell->Destroy();
    IllegalCell = nullptr;
  }
  for (AS08FighterActor* Actor : FighterActors) {
    if (Actor) Actor->Destroy();
  }
  FighterActors.Reset();
}

UInstancedStaticMeshComponent* AS08BoardActor::ZoneStrokeComponent(const FS08ZoneStyle& Style) {
  if (TObjectPtr<UInstancedStaticMeshComponent>* Found = ArtZoneStrokes.Find(Style.Key)) {
    if (*Found) return *Found;
  }
  UInstancedStaticMeshComponent* Component = NewObject<UInstancedStaticMeshComponent>(
      this, FName(*ZoneComponentName(Style.Key)));
  Component->SetupAttachment(RootComponent);
  Component->SetStaticMesh(BlockerTiles->GetStaticMesh());
  Component->SetCollisionEnabled(ECollisionEnabled::NoCollision);
  Component->RegisterComponent();
  ArtZoneStrokes.Add(Style.Key, Component);
  return Component;
}

UMaterialInterface* AS08BoardActor::ZoneMaterialFor(const FS08ZoneStyle& Style, bool& bOutAuthored,
                                                    bool& bOutIsmUsage) {
  bOutAuthored = false;
  bOutIsmUsage = false;
  if (TObjectPtr<UMaterialInterface>* Authored = ArtZoneMaterials.Find(Style.Key)) {
    const UMaterial* Base = *Authored ? (*Authored)->GetMaterial() : nullptr;
    bOutIsmUsage = Base && Base->GetUsageByFlag(MATUSAGE_InstancedStaticMeshes);
    // The ART-005 review materials lack the instancing usage (cooked builds
    // fall back to the default material); the legacy Cobble profile keeps
    // them for byte-compatible evidence, every other board uses the tint.
    if (*Authored && (bOutIsmUsage || ActiveProfile.bLegacyCobbleTrace)) {
      bOutAuthored = true;
      return *Authored;
    }
  }
  if (TObjectPtr<UMaterialInstanceDynamic>* Cached = ArtZoneTints.Find(Style.Key)) {
    if (*Cached) return *Cached;
  }
  if (!ArtSolidMaterial) return nullptr;
  UMaterialInstanceDynamic* Mid = UMaterialInstanceDynamic::Create(ArtSolidMaterial, this);
  // sRGB bytes of the data survive the back buffer (memory trap 9).
  Mid->SetVectorParameterValue(TEXT("Tint"), FLinearColor(Style.Color));
  ArtZoneTints.Add(Style.Key, Mid);
  return Mid;
}

void AS08BoardActor::ClearArtSurface() {
  for (UStaticMeshComponent* Part : ArtSurfaceParts) {
    if (Part) Part->DestroyComponent();
  }
  ArtSurfaceParts.Reset();
}

void AS08BoardActor::AddArtSurfacePart(UMaterialInterface* Material, const FTransform& Transform) {
  UStaticMeshComponent* Part = NewObject<UStaticMeshComponent>(this);
  Part->SetupAttachment(RootComponent);
  Part->SetStaticMesh(BlockerTiles->GetStaticMesh());
  Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);
  Part->SetRelativeTransform(Transform);
  if (Material) Part->SetMaterial(0, Material);
  Part->RegisterComponent();
  ArtSurfaceParts.Add(Part);
}

void AS08BoardActor::ClearArtLights() {
  for (AActor* Light : ArtLights) {
    if (Light) Light->Destroy();
  }
  ArtLights.Reset();
  ActiveLightProfileId.Reset();
}

void AS08BoardActor::ApplyArtLights(const FS08LightProfile& Light, bool bLegacyCobbleTrace) {
  if (ActiveLightProfileId == Light.Id && !ArtLights.IsEmpty()) return;
  ClearArtLights();
  // S08Arena has no scene lights, so a PBR board would be black. Profile data:
  // 1 directional with shadow + <= 6 point lights without shadow (budget
  // validated on load). Measured probe candidates, not lighting norms.
  const TArray<FS08PlacedLight> Placed = S08PlaceLights(Light, BoardModel);
  bool bOk = true;
  float Key = 0.0f, Fill = 0.0f, Warm = 0.0f;
  int32 Points = 0, PointShadows = 0;
  for (const FS08PlacedLight& P : Placed) {
    if (P.Spec.bDirectional) {
      ADirectionalLight* Dir = GetWorld()->SpawnActor<ADirectionalLight>(P.Position, P.Spec.Rotation);
      if (!Dir) {
        bOk = false;
        break;
      }
      Dir->GetLightComponent()->SetMobility(EComponentMobility::Movable);
      Dir->GetLightComponent()->SetIntensity(P.Spec.Intensity);
      Dir->GetLightComponent()->SetCastShadows(P.Spec.bCastShadows);
      if (P.Spec.bHasColor) Dir->GetLightComponent()->SetLightColor(P.Spec.Color);
      ArtLights.Add(Dir);
      Key = P.Spec.Intensity;
    } else {
      APointLight* Point = GetWorld()->SpawnActor<APointLight>(P.Position, FRotator::ZeroRotator);
      if (!Point) {
        bOk = false;
        break;
      }
      UPointLightComponent* Component = CastChecked<UPointLightComponent>(Point->GetLightComponent());
      Component->SetMobility(EComponentMobility::Movable);
      Component->SetIntensity(P.Spec.Intensity);
      Component->SetAttenuationRadius(P.Spec.RadiusUU);
      Component->SetCastShadows(P.Spec.bCastShadows);
      if (P.Spec.bHasColor) Component->SetLightColor(P.Spec.Color);
      ArtLights.Add(Point);
      ++Points;
      PointShadows += P.Spec.bCastShadows ? 1 : 0;
      if (P.Spec.Name == TEXT("fill")) Fill = P.Spec.Intensity;
      if (P.Spec.Name == TEXT("warm")) Warm = P.Spec.Intensity;
    }
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW light profile=%s name=%s role=%s kind=%s at=(%.0f,%.0f,%.0f) intensity=%g radius=%g color=(%.2f,%.2f,%.2f) shadow=%d"),
        *Light.Id, *P.Spec.Name, *P.Spec.Role, P.Spec.bDirectional ? TEXT("directional") : TEXT("point"),
        P.Position.X, P.Position.Y, P.Position.Z, P.Spec.Intensity, P.Spec.RadiusUU,
        P.Spec.Color.R, P.Spec.Color.G, P.Spec.Color.B, P.Spec.bCastShadows ? 1 : 0));
  }
  if (!bOk) {
    ClearArtLights();
    FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW lights profile=%s failed"), *Light.Id));
    if (bLegacyCobbleTrace) FS08Trace::Write(TEXT("ARTPREVIEW Cobble probe lights failed"));
    return;
  }
  ActiveLightProfileId = Light.Id;
  FString Budget;
  const bool bBudget = Light.BudgetOk(Budget);
  FS08Trace::Write(FString::Printf(
      TEXT("ARTPREVIEW lights applied profile=%s directional=%d shadow=%d points=%d pointShadows=%d budgetOk=%d"),
      *Light.Id, Light.bHasDirectional ? 1 : 0, Light.Directional.bCastShadows ? 1 : 0, Points, PointShadows,
      bBudget ? 1 : 0));
  if (bLegacyCobbleTrace) {
    FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW Cobble probe lights key=%g fill=%g warm=%g"), Key, Fill, Warm));
  }
}

void AS08BoardActor::ApplySurfaceMaterials() {
  // The instanced tiles keep their grey materials in every mode; on an art
  // board they are hidden click surfaces (the art surface draws instead) and
  // the dark underlay stays visible on 'tiles' (grooves + non-space voids).
  if (GreyTileMaterial) NormalTiles->SetMaterial(0, GreyTileMaterial);
  if (GreyBlockerMaterial) BlockerTiles->SetMaterial(0, GreyBlockerMaterial);
  UMaterialInterface* Underlay = bArtTiles && ArtVoidMaterial ? ArtVoidMaterial.Get() : GreyUnderlayMaterial.Get();
  if (Underlay) UnderlayTiles->SetMaterial(0, Underlay);
}

bool AS08BoardActor::Rebuild(const FS08BoardModel& Board) {
  if (Board.Width <= 0 || Board.Height <= 0) return false;
  if (BoardModel.Width == Board.Width && BoardModel.Height == Board.Height &&
      BoardModel.Cells.Num() == Board.Cells.Num() && BuiltForBoardId == RoomBoardId) {
    bool bSameTypes = true;
    for (int32 i = 0; i < BoardModel.Cells.Num(); ++i) {
      if (BoardModel.Cells[i].Type != Board.Cells[i].Type ||
          BoardModel.Cells[i].bIsOpen != Board.Cells[i].bIsOpen ||
          BoardModel.Cells[i].Zones != Board.Cells[i].Zones) {
        bSameTypes = false;
        break;
      }
    }
    if (bSameTypes) return true; // geometry unchanged: tiles stay as-is
  }
  BoardModel = Board;
  BuiltForBoardId = RoomBoardId;
  const FS08BoardSummary Summary = S08SummarizeBoard(Board);

  // T3.2 profile selection: board row id, else W x H + exact zone-key set.
  bArtActive = false;
  bArtTiles = false;
  ActiveProfile = FS08BoardArtProfile();
  if (bArtAssetsReady) {
    ES08ProfileMatch Match = ES08ProfileMatch::None;
    const FS08BoardArtProfile* Profile = ArtData.Select(Board, RoomBoardId, Match);
    if (!Profile) {
      FS08Trace::Write(FString::Printf(
          TEXT("ARTPREVIEW board profile=none match=none board=%dx%d boardId=%s zoneKeys=%s; keeping grey board"),
          Board.Width, Board.Height, RoomBoardId.IsEmpty() ? TEXT("-") : *RoomBoardId,
          *FString::Join(Summary.ZoneKeys, TEXT("+"))));
    } else {
      ES08BoardSurface Surface = Profile->Surface;
      if (Surface == ES08BoardSurface::Cobble5x6Mesh &&
          (!bCobbleMeshReady || Board.Width != 5 || Board.Height != 6)) {
        FS08Trace::Write(FString::Printf(
            TEXT("ARTPREVIEW board surface cobble-5x6-mesh unavailable (mesh=%d board=%dx%d); using tiles"),
            bCobbleMeshReady ? 1 : 0, Board.Width, Board.Height));
        Surface = ES08BoardSurface::Tiles;
      }
      if (Surface == ES08BoardSurface::Tiles && !bTileArtReady) {
        FS08Trace::Write(TEXT("ARTPREVIEW board surface tiles unavailable (probe materials missing); keeping grey board"));
      } else {
        ActiveProfile = *Profile;
        ActiveProfile.Surface = Surface;
        bArtActive = true;
        bArtTiles = Surface == ES08BoardSurface::Tiles;
        FS08Trace::Write(FString::Printf(
            TEXT("ARTPREVIEW board profile=%s match=%s board=%dx%d boardId=%s surface=%s light=%s artFixture=%d"),
            *ActiveProfile.Id, S08ProfileMatchName(Match), Board.Width, Board.Height,
            RoomBoardId.IsEmpty() ? TEXT("-") : *RoomBoardId, S08BoardSurfaceName(Surface),
            *ActiveProfile.LightId, ActiveProfile.bArtFixture ? 1 : 0));
      }
    }
  }
  if (!bArtActive) {
    ClearArtLights();
  } else if (const FS08LightProfile* Light = ArtData.LightFor(ActiveProfile)) {
    ApplyArtLights(*Light, ActiveProfile.bLegacyCobbleTrace);
  }
  const bool bCobbleMesh = bArtActive && !bArtTiles;
  NormalTiles->ClearInstances();
  BlockerTiles->ClearInstances();
  UnderlayTiles->ClearInstances();
  ArtCorners->ClearInstances();
  ClearArtSurface();
  ArtZoneGlyphs->ClearInstances();
  for (TPair<FString, TObjectPtr<UInstancedStaticMeshComponent>>& Stroke : ArtZoneStrokes) {
    if (Stroke.Value) {
      Stroke.Value->ClearInstances();
      Stroke.Value->SetVisibility(bArtActive);
    }
  }
  ApplySurfaceMaterials();
  NormalTiles->SetVisibility(!bArtActive);
  BlockerTiles->SetVisibility(!bArtActive);
  UnderlayTiles->SetVisibility(!bCobbleMesh);
  ArtBoard->SetVisibility(bCobbleMesh);
  ArtCorners->SetVisibility(bArtActive);
  ArtZoneGlyphs->SetVisibility(bArtActive);
  // Full-board dark slab: top at z=-0.5 (just under the tile tops at z=0)
  // so grooves and the outer frame read dark; spans exactly the INT-019
  // cell boundaries, so a trace landing in a groove still resolves to the
  // right cell through WorldToCell.
  const float SlabHalfZ = 100.0f * 0.02f * 0.5f;
  UnderlayTiles->AddInstanceWorldSpace(FTransform(
      FRotator::ZeroRotator, FVector(0.0f, 0.0f, -0.5f - SlabHalfZ),
      FVector(static_cast<float>(Board.Width),
              static_cast<float>(Board.Height), 0.02f)));
  for (int32 Y = 0; Y < Board.Height; ++Y) {
    for (int32 X = 0; X < Board.Width; ++X) {
      const FS08Cell* Cell = Board.CellAt(X, Y);
      const FVector World = Board.CellToWorld(X, Y);
      const bool bBlocker = !Cell || !Cell->IsPassable();
      UInstancedStaticMeshComponent* Target = bBlocker ? BlockerTiles : NormalTiles;
      FTransform Instance(FRotator::ZeroRotator,
                          bBlocker ? World + FVector(0, 0, 25.0f)
                                   : World - FVector(0, 0, 5.0f),
                          bBlocker ? FVector(BlockerVisualScaleXY,
                                             BlockerVisualScaleXY, 0.5f)
                                   : FVector(TileVisualScaleXY,
                                             TileVisualScaleXY, 0.1f));
      Target->AddInstanceWorldSpace(Instance);
      if (bArtTiles && !bBlocker) {
        // Lit stone slab with a narrow dark groove; a non-space (obstacle)
        // cell gets no slab and reads as a dark void of the underlay.
        AddArtSurfacePart(ArtStoneTileMaterial,
                          FTransform(FRotator::ZeroRotator, World - FVector(0, 0, 5.0f),
                                     FVector(ArtTileScaleXY, ArtTileScaleXY, 0.1f)));
      }
    }
  }
  if (bArtActive) {
    // Zone strokes/glyphs from the data: every zone of every cell, multizone
    // cells on separate sides/slots (03 section 4.5: composite outline + glyphs).
    const FS08ZoneMarkLayout Marks = S08BuildZoneMarks(Board, ArtData);
    for (const FString& Key : Summary.ZoneKeys) {
      const FS08ZoneStyle Style = ArtData.StyleFor(Key);
      if (UInstancedStaticMeshComponent* Component = ZoneStrokeComponent(Style)) {
        bool bAuthored = false, bIsm = false;
        Component->SetMaterial(0, ZoneMaterialFor(Style, bAuthored, bIsm));
        Component->SetVisibility(true);
      }
    }
    for (const FS08ZoneMarkPiece& Piece : Marks.Strokes) {
      if (UInstancedStaticMeshComponent* Component = ZoneStrokeComponent(ArtData.StyleFor(Piece.Key))) {
        Component->AddInstance(Piece.Transform, true);
      }
    }
    // Glyphs in the zone colour (default) or the ART-005 review material.
    for (const FS08ZoneMarkPiece& Piece : Marks.Glyphs) {
      UInstancedStaticMeshComponent* Target = ActiveProfile.bZoneColorGlyphs
          ? ZoneStrokeComponent(ArtData.StyleFor(Piece.Key)) : ArtZoneGlyphs.Get();
      if (Target) Target->AddInstance(Piece.Transform, true);
    }
    const float HalfX = Board.Width * FS08BoardModel::CellSizeUU * 0.5f;
    const float HalfY = Board.Height * FS08BoardModel::CellSizeUU * 0.5f;
    for (const TPair<FVector, float>& Corner : {
             TPair<FVector, float>(FVector(HalfX, HalfY, 0), 180),
             TPair<FVector, float>(FVector(-HalfX, HalfY, 0), -90),
             TPair<FVector, float>(FVector(-HalfX, -HalfY, 0), 0),
             TPair<FVector, float>(FVector(HalfX, -HalfY, 0), 90)}) {
      ArtCorners->AddInstance(FTransform(
          FRotator(0, Corner.Value, 0), Corner.Key, FVector::OneVector), true);
    }
    if (bArtTiles) {
      const float Half = ArtFrameUU * 0.5f;
      const float SpanX = (Board.Width * FS08BoardModel::CellSizeUU + 2.0f * ArtFrameUU) / 100.0f;
      const float SpanY = Board.Height * FS08BoardModel::CellSizeUU / 100.0f;
      const float T = ArtFrameUU / 100.0f;
      for (const FTransform& Bar : {
               FTransform(FRotator::ZeroRotator, FVector(0, HalfY + Half, -3.0f), FVector(SpanX, T, 0.14f)),
               FTransform(FRotator::ZeroRotator, FVector(0, -HalfY - Half, -3.0f), FVector(SpanX, T, 0.14f)),
               FTransform(FRotator::ZeroRotator, FVector(-HalfX - Half, 0, -3.0f), FVector(T, SpanY, 0.14f)),
               FTransform(FRotator::ZeroRotator, FVector(HalfX + Half, 0, -3.0f), FVector(T, SpanY, 0.14f))}) {
        AddArtSurfacePart(ArtWoodMaterial, Bar);
      }
    }
    const FString Mismatch = S08ExpectMismatch(ActiveProfile, Summary);
    if (ActiveProfile.bLegacyCobbleTrace) {
      // ART-005 evidence line kept byte-compatible for the existing demo gates.
      const FString Legacy = FString::Printf(
          TEXT("ARTPREVIEW Cobble active %dx%d zones=%d blue=%d red=%d blueMarks=%d redMarks=%d"),
          Board.Width, Board.Height, Summary.ZoneCells, Marks.CellsByKey.FindRef(TEXT("blue")),
          Marks.CellsByKey.FindRef(TEXT("red")), Marks.StrokePiecesByKey.FindRef(TEXT("blue")),
          Marks.StrokePiecesByKey.FindRef(TEXT("red")));
      UE_LOG(LogTemp, Display, TEXT("%s"), *Legacy);
      FS08Trace::Write(Legacy);
    }
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW board active profile=%s %dx%d surface=%s cells=%d zoneCells=%d multizone=%d triple=%d obstacles=%d zoneKeys=%d strokes=%d glyphs=%d surfaceParts=%d glyphMaterial=%s expectOk=%d%s"),
        *ActiveProfile.Id, Board.Width, Board.Height, S08BoardSurfaceName(ActiveProfile.Surface), Summary.Cells,
        Summary.ZoneCells, Summary.MultizoneCells, Summary.TripleZoneCells, Summary.Obstacles,
        Summary.ZoneKeys.Num(), Marks.Strokes.Num(), Marks.Glyphs.Num(), ArtSurfaceParts.Num(),
        ActiveProfile.bZoneColorGlyphs ? TEXT("zone") : TEXT("review"), Mismatch.IsEmpty() ? 1 : 0,
        Mismatch.IsEmpty() ? TEXT("") : *(TEXT(" mismatch=") + Mismatch)));
    for (const FString& Key : Summary.ZoneKeys) {
      const FS08ZoneStyle Style = ArtData.StyleFor(Key);
      bool bAuthored = false, bIsm = false;
      ZoneMaterialFor(Style, bAuthored, bIsm);
      FS08Trace::Write(FString::Printf(
          TEXT("ARTPREVIEW board zone key=%s cells=%d stroke=%s glyph=%s %s=%s ismUsage=%d strokePieces=%d glyphPieces=%d fallback=%d"),
          *Key, Marks.CellsByKey.FindRef(Key), S08ZoneStrokeName(Style.Stroke), S08ZoneGlyphName(Style.Glyph),
          bAuthored ? TEXT("material") : TEXT("color"),
          bAuthored ? *FPaths::GetBaseFilename(Style.MaterialPath) : *Style.ColorHex(),
          bAuthored ? (bIsm ? 1 : 0) : 1, Marks.StrokePiecesByKey.FindRef(Key),
          Marks.GlyphPiecesByKey.FindRef(Key), Style.bFallback ? 1 : 0));
    }
    FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW board multizone cells=%d zonesListed=%d zonesMarked=%d"),
                                     Marks.MultizoneCells, Marks.MultizoneZonesListed, Marks.MultizoneZonesMarked));
    for (const FString& Line : Marks.MultizoneLines) {
      FS08Trace::Write(TEXT("ARTPREVIEW board multizone cell=") + Line);
    }
  }
  ClearChildren();
  return true;
}

void AS08BoardActor::SyncFighters(const FS08BoardModel& Board,
                                  const TArray<FS08BoardFighter>& InFighters,
                                  const FString& OwnOwnerId) {
  Fighters = InFighters;
  // Remove actors whose fighter disappeared from the projection.
  for (int32 i = FighterActors.Num() - 1; i >= 0; --i) {
    AS08FighterActor* Actor = FighterActors[i];
    if (!Actor) {
      FighterActors.RemoveAt(i);
      continue;
    }
    bool bStillThere = false;
    for (const FS08BoardFighter& Fighter : Fighters) {
      if (Fighter.Id == Actor->GetFighterId()) {
        bStillThere = true;
        break;
      }
    }
    if (!bStillThere) {
      Actor->Destroy();
      FighterActors.RemoveAt(i);
    }
  }
  for (const FS08BoardFighter& Fighter : Fighters) {
    AS08FighterActor* Actor = FindFighterActor(Fighter.Id);
    if (!Actor) {
      FActorSpawnParameters Params;
      Params.Owner = this;
      Actor = GetWorld()->SpawnActor<AS08FighterActor>(
          AS08FighterActor::StaticClass(), Board.CellToWorld(Fighter.X, Fighter.Y),
          FRotator::ZeroRotator, Params);
      FighterActors.Add(Actor);
    }
    if (Actor) {
      Actor->SetScreenIconMode(bScreenIconMode);
      Actor->ApplyFighter(Fighter, Board.CellToWorld(Fighter.X, Fighter.Y),
                          Fighter.OwnerId == OwnOwnerId, bArtActive);
      Actor->SetSelected(Fighter.Id == SelectedFighterId);
      Actor->SetCombatMarkers(Fighter.Id == CombatAttackerId,
                              Fighter.Id == CombatTargetId);
      Actor->SetLabelMode(LabelPlateFighterId.IsEmpty() ? ES08FighterLabelMode::Full
                          : Fighter.Id == LabelPlateFighterId ? ES08FighterLabelMode::Hidden
                                                              : ES08FighterLabelMode::Compact);
    }
  }
  // ART-004 T2.2 six-copies review: one summary once every fighter applied.
  if (bArtActive && S08ArtPreviewAllMedusa() && !bAllMedusaSummaryTraced && FighterActors.Num() > 0) {
    bAllMedusaSummaryTraced = true;
    int32 Visual = 0;
    for (const AS08FighterActor* Actor : FighterActors) {
      if (Actor && Actor->HasMedusaCandidate()) ++Visual;
    }
    FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW allMedusa copies=%d visual=%d"),
                                     FighterActors.Num(), Visual));
  }
}

void AS08BoardActor::SetSelectedFighter(const FString& FighterId,
                                        const TSet<uint64>& Reachable) {
  SelectedFighterId = FighterId;
  ReachableCells = Reachable;
  for (AS08FighterActor* Actor : FighterActors) {
    if (Actor) Actor->SetSelected(Actor->GetFighterId() == FighterId);
  }
  for (AActor* Tile : HighlightTiles) {
    if (Tile) Tile->Destroy();
  }
  HighlightTiles.Reset();
  if (FighterId.IsEmpty()) return;

  UMaterialInterface* Solid = LoadObject<UMaterialInterface>(
      nullptr, TEXT("/Game/S08/M_S08_Solid.M_S08_Solid"));
  const FS08BoardFighter* Selected = nullptr;
  for (const FS08BoardFighter& Fighter : Fighters) {
    if (Fighter.Id == FighterId) {
      Selected = &Fighter;
      break;
    }
  }
  int32 ArtOutlineCells = 0;
  bool bArtOutlinePositionsCorrect = true;
  for (const uint64 Key : ReachableCells) {
    const int32 X = static_cast<int32>(Key >> 32);
    const int32 Y = static_cast<int32>(Key & 0xFFFFFFFF);
    const bool bOwnCell = Selected && Selected->X == X && Selected->Y == Y;
    // The authored ring already marks the selected unit; avoid covering its
    // sculpt and name with a second cell overlay in the art review.
    if (bArtActive && bOwnCell) continue;
    const FVector CellCenter = BoardModel.CellToWorld(X, Y);
    AActor* Tile = GetWorld()->SpawnActor<AActor>(AActor::StaticClass(),
                                                  CellCenter,
                                                  FRotator::ZeroRotator);
    if (!Tile) continue;
    // AActor has no root of its own. Without one, attaching the mesh after
    // SpawnActor collapses all highlights to the world origin.
    USceneComponent* Root = NewObject<USceneComponent>(Tile, TEXT("HighlightRoot"));
    Tile->SetRootComponent(Root);
    Root->RegisterComponent();
    Tile->SetActorLocation(CellCenter);
    if (bArtActive) {
      ++ArtOutlineCells;
      bArtOutlinePositionsCorrect &= Tile->GetActorLocation().Equals(CellCenter, 0.01f);
    }
    UMaterialInstanceDynamic* Mid = nullptr;
    if (Solid) {
      Mid = UMaterialInstanceDynamic::Create(Solid, Tile);
      Mid->SetVectorParameterValue(TEXT("Tint"),
                                   bOwnCell ? FLinearColor(0.5f, 0.5f, 0.55f)
                                            : FLinearColor(0.12f, 0.65f, 0.22f));
    }
    auto AddHighlightPart = [&](const FVector& Position, const FVector& Scale) {
      UStaticMeshComponent* Mesh = NewObject<UStaticMeshComponent>(Tile);
      Mesh->SetupAttachment(Root);
      Mesh->SetStaticMesh(BlockerTiles->GetStaticMesh());
      Mesh->SetRelativeLocation(Position);
      Mesh->SetRelativeScale3D(Scale);
      Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
      if (Mid) Mesh->SetMaterial(0, Mid);
      Mesh->RegisterComponent();
    };
    if (bArtActive) {
      // Two diagonal L-shaped corner ticks keep cobble, labels and occupied
      // fighters visible. Their shape differs from the zone diamond/bars.
      for (int32 Corner = 0; Corner < 2; ++Corner) {
        const float Sign = Corner == 0 ? -1.0f : 1.0f;
        AddHighlightPart(FVector(Sign * 29.0f, Sign * 38.0f, 1.8f),
                         FVector(0.18f, 0.03f, 0.005f));
        AddHighlightPart(FVector(Sign * 38.0f, Sign * 29.0f, 1.8f),
                         FVector(0.03f, 0.18f, 0.005f));
      }
    } else {
      AddHighlightPart(FVector(0, 0, 1.5f),
                       FVector(0.85f, 0.85f, 0.02f));
    }
    HighlightTiles.Add(Tile);
  }
  if (bArtActive) {
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW reachable corners cells=%d placed=%d"),
        ArtOutlineCells, bArtOutlinePositionsCorrect ? 1 : 0));
  }
}

void AS08BoardActor::ClearSelection() {
  SetSelectedFighter(FString(), TSet<uint64>());
}

void AS08BoardActor::ShowIllegalCell(int32 X, int32 Y) {
  HideIllegalCell();
  UMaterialInterface* Solid = LoadObject<UMaterialInterface>(
      nullptr, TEXT("/Game/S08/M_S08_Solid.M_S08_Solid"));
  IllegalCell = GetWorld()->SpawnActor<AActor>(AActor::StaticClass(),
                                               BoardModel.CellToWorld(X, Y),
                                               FRotator::ZeroRotator);
  if (!IllegalCell) return;
  UStaticMeshComponent* Mesh = NewObject<UStaticMeshComponent>(IllegalCell, TEXT("Illegal"));
  Mesh->SetStaticMesh(BlockerTiles->GetStaticMesh());
  Mesh->SetWorldScale3D(FVector(0.85f, 0.85f, 0.02f));
  Mesh->SetRelativeLocation(FVector(0, 0, 1.5f));
  Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
  if (Solid) {
    UMaterialInstanceDynamic* Mid = UMaterialInstanceDynamic::Create(Solid, IllegalCell);
    Mid->SetVectorParameterValue(TEXT("Tint"), FLinearColor(0.9f, 0.15f, 0.15f));
    Mesh->SetMaterial(0, Mid);
  }
  IllegalCell->SetRootComponent(Mesh);
  Mesh->RegisterComponent();
}

void AS08BoardActor::HideIllegalCell() {
  if (IllegalCell) {
    IllegalCell->Destroy();
    IllegalCell = nullptr;
  }
}
