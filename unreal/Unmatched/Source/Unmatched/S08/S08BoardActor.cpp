#include "S08BoardActor.h"
#include "S08FighterActor.h"
#include "S08TraceLog.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/SceneComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/PointLight.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "UObject/ConstructorHelpers.h"

namespace {
UMaterialInterface* LoadTileMaterial() {
  static UMaterialInterface* Cached = LoadObject<UMaterialInterface>(
      nullptr, TEXT("/Game/S08/M_S08_Tile.M_S08_Tile"));
  return Cached ? Cached
                : LoadObject<UMaterialInterface>(
                      nullptr, TEXT("/Engine/BasicShapes/BasicShapeMaterial"));
}

bool SupportsCobbleArt(const FS08BoardModel& Board) {
  if (Board.Width != 5 || Board.Height != 6 || Board.Cells.Num() != 30) return false;
  for (const FS08Cell& Cell : Board.Cells) {
    if (Cell.Type != ES08CellType::Normal || Cell.Zones.Num() != 1 ||
        (Cell.Zones[0] != TEXT("blue") && Cell.Zones[0] != TEXT("red"))) return false;
  }
  return true;
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

  ArtBlueZones = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("ArtBlueZones"));
  ArtBlueZones->SetupAttachment(RootComponent);
  ArtBlueZones->SetStaticMesh(Cube);
  ArtBlueZones->SetCollisionEnabled(ECollisionEnabled::NoCollision);
  ArtBlueZones->SetVisibility(false);

  ArtRedZones = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("ArtRedZones"));
  ArtRedZones->SetupAttachment(RootComponent);
  ArtRedZones->SetStaticMesh(Cube);
  ArtRedZones->SetCollisionEnabled(ECollisionEnabled::NoCollision);
  ArtRedZones->SetVisibility(false);

  ArtZoneGlyphs = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("ArtZoneGlyphs"));
  ArtZoneGlyphs->SetupAttachment(RootComponent);
  ArtZoneGlyphs->SetStaticMesh(Cube);
  ArtZoneGlyphs->SetCollisionEnabled(ECollisionEnabled::NoCollision);
  ArtZoneGlyphs->SetVisibility(false);
}

void AS08BoardActor::BeginPlay() {
  Super::BeginPlay();
  if (UMaterialInterface* Tile = LoadTileMaterial()) {
    NormalTiles->SetMaterial(0, Tile);
    UMaterialInstanceDynamic* BlockerMid = UMaterialInstanceDynamic::Create(Tile, this);
    BlockerMid->SetVectorParameterValue(TEXT("Tint"), FLinearColor(0.22f, 0.22f, 0.24f));
    BlockerTiles->SetMaterial(0, BlockerMid);
    UMaterialInstanceDynamic* UnderlayMid = UMaterialInstanceDynamic::Create(Tile, this);
    UnderlayMid->SetVectorParameterValue(TEXT("Tint"), FLinearColor(0.07f, 0.07f, 0.09f));
    UnderlayTiles->SetMaterial(0, UnderlayMid);
  }
  if (!FParse::Param(FCommandLine::Get(), TEXT("ArtPreview"))) return;
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
  UMaterialInterface* Blue = LoadObject<UMaterialInterface>(nullptr,
      TEXT("/Game/ArtTests/ART005/Materials/M_ART005_BlueSection_Review"));
  UMaterialInterface* Red = LoadObject<UMaterialInterface>(nullptr,
      TEXT("/Game/ArtTests/ART005/Materials/M_ART005_RedSection_Review"));
  UMaterialInterface* Glyph = LoadObject<UMaterialInterface>(nullptr,
      TEXT("/Game/ArtTests/ART005/Materials/M_ART005_ZoneGlyph_Review"));
  USkeletalMesh* Medusa = LoadObject<USkeletalMesh>(nullptr,
      TEXT("/Game/ArtPreview/Medusa/Meshes/SK_Medusa_FaceNeck_v2Candidate"));
  UStaticMesh* Pedestal = LoadObject<UStaticMesh>(nullptr,
      TEXT("/Game/ArtPreview/Medusa/Meshes/SM_Medusa_Base_v2Candidate"));
  UMaterialInterface* TeamBlue = LoadObject<UMaterialInterface>(nullptr,
      TEXT("/Game/ArtPreview/Medusa/Materials/MI_Medusa_Blue"));
  UMaterialInterface* TeamRed = LoadObject<UMaterialInterface>(nullptr,
      TEXT("/Game/ArtPreview/Medusa/Materials/MI_Medusa_Red"));
  if (!Board || !Corner || !Stone || !Wood || !Iron || !Blue || !Red || !Glyph ||
      !Medusa || !Medusa->GetSkeleton() || !Pedestal || !TeamBlue || !TeamRed) {
    UE_LOG(LogTemp, Warning, TEXT("ARTPREVIEW Cobble assets missing; keeping grey board"));
    return;
  }
  const int32 StoneSlot = Board->GetMaterialIndex(TEXT("M_ART005_Stone_AtlasB_Provisional"));
  const int32 WoodSlot = Board->GetMaterialIndex(TEXT("M_ART005_Wood_Provisional"));
  if (StoneSlot < 0 || WoodSlot < 0) {
    UE_LOG(LogTemp, Warning, TEXT("ARTPREVIEW Cobble material slots changed; keeping grey board"));
    return;
  }
  ArtBoard->SetStaticMesh(Board);
  ArtBoard->SetRelativeRotation(FRotator(0.0f, -90.0f, 0.0f));
  ArtBoard->SetMaterial(StoneSlot, Stone);
  ArtBoard->SetMaterial(WoodSlot, Wood);
  ArtCorners->SetStaticMesh(Corner);
  ArtCorners->SetMaterial(0, Iron);
  ArtBlueZones->SetMaterial(0, Blue);
  ArtRedZones->SetMaterial(0, Red);
  ArtZoneGlyphs->SetMaterial(0, Glyph);
  bArtAssetsReady = true;
  UE_LOG(LogTemp, Display, TEXT("ARTPREVIEW Cobble assets ready"));
  FS08Trace::Write(TEXT("ARTPREVIEW Cobble assets ready"));
}

void AS08BoardActor::EndPlay(const EEndPlayReason::Type Reason) {
  for (AActor* Light : ArtLights) {
    if (Light) Light->Destroy();
  }
  ArtLights.Reset();
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

void AS08BoardActor::ClearChildren() {
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

bool AS08BoardActor::Rebuild(const FS08BoardModel& Board) {
  if (Board.Width <= 0 || Board.Height <= 0) return false;
  if (BoardModel.Width == Board.Width && BoardModel.Height == Board.Height &&
      BoardModel.Cells.Num() == Board.Cells.Num()) {
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
  bArtActive = bArtAssetsReady && SupportsCobbleArt(Board);
  if (!bArtActive) {
    for (AActor* Light : ArtLights) {
      if (Light) Light->Destroy();
    }
    ArtLights.Reset();
  } else if (ArtLights.IsEmpty()) {
    // ART-005 editor probe lighting, reproduced only for this opt-in Cobble
    // review. S08Arena has no scene lights, so the PBR board would be black.
    // These measured candidates are not lighting settings for other maps.
    ADirectionalLight* Key = GetWorld()->SpawnActor<ADirectionalLight>(
        FVector(-350, -150, 600), FRotator(0, -55, 30));
    APointLight* Ambient = GetWorld()->SpawnActor<APointLight>(
        FVector(0, -100, 550), FRotator::ZeroRotator);
    APointLight* Warm = GetWorld()->SpawnActor<APointLight>(
        FVector(260, -300, 250), FRotator::ZeroRotator);
    if (Key && Ambient && Warm) {
      Key->GetLightComponent()->SetMobility(EComponentMobility::Movable);
      Key->GetLightComponent()->SetIntensity(4.5f);
      auto ConfigureFill = [](APointLight* Light, float Intensity, float Radius) {
        UPointLightComponent* Component = CastChecked<UPointLightComponent>(Light->GetLightComponent());
        Component->SetMobility(EComponentMobility::Movable);
        Component->SetIntensity(Intensity);
        Component->SetAttenuationRadius(Radius);
        Component->SetCastShadows(false);
      };
      ConfigureFill(Ambient, 700.0f, 1800.0f);
      ConfigureFill(Warm, 85.0f, 450.0f);
      ArtLights.Add(Key);
      ArtLights.Add(Ambient);
      ArtLights.Add(Warm);
      FS08Trace::Write(TEXT("ARTPREVIEW Cobble probe lights key=4.5 fill=700 warm=85"));
    } else {
      if (Key) Key->Destroy();
      if (Ambient) Ambient->Destroy();
      if (Warm) Warm->Destroy();
      FS08Trace::Write(TEXT("ARTPREVIEW Cobble probe lights failed"));
    }
  }
  NormalTiles->ClearInstances();
  BlockerTiles->ClearInstances();
  UnderlayTiles->ClearInstances();
  ArtCorners->ClearInstances();
  ArtBlueZones->ClearInstances();
  ArtRedZones->ClearInstances();
  ArtZoneGlyphs->ClearInstances();
  NormalTiles->SetVisibility(!bArtActive);
  BlockerTiles->SetVisibility(!bArtActive);
  UnderlayTiles->SetVisibility(!bArtActive);
  ArtBoard->SetVisibility(bArtActive);
  ArtCorners->SetVisibility(bArtActive);
  ArtBlueZones->SetVisibility(bArtActive);
  ArtRedZones->SetVisibility(bArtActive);
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
  int32 BlueZoneCells = 0;
  int32 RedZoneCells = 0;
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
      if (bArtActive) {
        const bool bBlue = Cell->Zones[0] == TEXT("blue");
        // The continuous blue edge and three separated red strokes remain
        // different when hue is lost. Counts below refer to board cells, not
        // to the number of decorative mesh instances.
        if (bBlue) {
          ++BlueZoneCells;
          ArtBlueZones->AddInstance(FTransform(
              FRotator::ZeroRotator, World + FVector(0, 46, 0.28f),
              FVector(0.96f, 0.04f, 0.004f)), true);
        } else {
          ++RedZoneCells;
          for (const float Offset : {-32.0f, 0.0f, 32.0f}) {
            ArtRedZones->AddInstance(FTransform(
                FRotator::ZeroRotator, World + FVector(Offset, 46, 0.28f),
                FVector(0.28f, 0.045f, 0.004f)), true);
          }
        }
        const FVector GlyphAt = World + FVector(-32, 32, 0.28f);
        if (bBlue) {
          ArtZoneGlyphs->AddInstance(FTransform(
              FRotator(0, 45, 0), GlyphAt, FVector(0.18f, 0.18f, 0.004f)), true);
        } else {
          for (const float Offset : {-6.0f, 6.0f}) {
            ArtZoneGlyphs->AddInstance(FTransform(
                FRotator::ZeroRotator, GlyphAt + FVector(Offset, 0, 0),
                FVector(0.05f, 0.20f, 0.004f)), true);
          }
        }
      }
    }
  }
  if (bArtActive) {
    for (const TPair<FVector, float>& Corner : {
             TPair<FVector, float>(FVector(250, 300, 0), 180),
             TPair<FVector, float>(FVector(-250, 300, 0), -90),
             TPair<FVector, float>(FVector(-250, -300, 0), 0),
             TPair<FVector, float>(FVector(250, -300, 0), 90)}) {
      ArtCorners->AddInstance(FTransform(
          FRotator(0, Corner.Value, 0), Corner.Key, FVector::OneVector), true);
    }
    const int32 ZoneCells = BlueZoneCells + RedZoneCells;
    UE_LOG(LogTemp, Display,
           TEXT("ARTPREVIEW Cobble active 5x6 zones=%d blue=%d red=%d blueMarks=%d redMarks=%d"),
           ZoneCells, BlueZoneCells, RedZoneCells,
           ArtBlueZones->GetInstanceCount(), ArtRedZones->GetInstanceCount());
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW Cobble active 5x6 zones=%d blue=%d red=%d blueMarks=%d redMarks=%d"),
        ZoneCells, BlueZoneCells, RedZoneCells,
        ArtBlueZones->GetInstanceCount(), ArtRedZones->GetInstanceCount()));
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
      Actor->ApplyFighter(Fighter, Board.CellToWorld(Fighter.X, Fighter.Y),
                          Fighter.OwnerId == OwnOwnerId, bArtActive);
      Actor->SetSelected(Fighter.Id == SelectedFighterId);
      Actor->SetCombatMarkers(Fighter.Id == CombatAttackerId,
                              Fighter.Id == CombatTargetId);
    }
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
