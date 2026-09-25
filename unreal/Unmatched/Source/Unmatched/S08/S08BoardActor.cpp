#include "S08BoardActor.h"
#include "S08FighterActor.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Materials/MaterialInterface.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "UObject/ConstructorHelpers.h"

namespace {
UMaterialInterface* LoadTileMaterial() {
  static UMaterialInterface* Cached = LoadObject<UMaterialInterface>(
      nullptr, TEXT("/Game/S08/M_S08_Tile.M_S08_Tile"));
  return Cached ? Cached
                : LoadObject<UMaterialInterface>(
                      nullptr, TEXT("/Engine/BasicShapes/BasicShapeMaterial"));
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
}

AS08FighterActor* AS08BoardActor::FindFighterActor(const FString& FighterId) const {
  for (AS08FighterActor* Actor : FighterActors) {
    if (Actor && Actor->GetFighterId() == FighterId) return Actor;
  }
  return nullptr;
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
          BoardModel.Cells[i].bIsOpen != Board.Cells[i].bIsOpen) {
        bSameTypes = false;
        break;
      }
    }
    if (bSameTypes) return true; // geometry unchanged: tiles stay as-is
  }
  BoardModel = Board;
  NormalTiles->ClearInstances();
  BlockerTiles->ClearInstances();
  UnderlayTiles->ClearInstances();
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
      Actor->ApplyFighter(Fighter, Board.CellToWorld(Fighter.X, Fighter.Y),
                          Fighter.OwnerId == OwnOwnerId);
      Actor->SetSelected(Fighter.Id == SelectedFighterId);
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
  for (const uint64 Key : ReachableCells) {
    const int32 X = static_cast<int32>(Key >> 32);
    const int32 Y = static_cast<int32>(Key & 0xFFFFFFFF);
    AActor* Tile = GetWorld()->SpawnActor<AActor>(AActor::StaticClass(),
                                                  BoardModel.CellToWorld(X, Y),
                                                  FRotator::ZeroRotator);
    if (!Tile) continue;
    UStaticMeshComponent* Mesh =
        NewObject<UStaticMeshComponent>(Tile, TEXT("Highlight"));
    Mesh->SetStaticMesh(BlockerTiles->GetStaticMesh());
    Mesh->SetWorldScale3D(FVector(0.85f, 0.85f, 0.02f));
    Mesh->SetRelativeLocation(FVector(0, 0, 1.5f));
    Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    if (Solid) {
      UMaterialInstanceDynamic* Mid = UMaterialInstanceDynamic::Create(Solid, Tile);
      // The mover's own cell (zero-step legal resolve) gets a neutral tint.
      const FS08BoardFighter* Selected = nullptr;
      for (const FS08BoardFighter& Fighter : Fighters) {
        if (Fighter.Id == FighterId) Selected = &Fighter;
      }
      const bool bOwnCell = Selected && Selected->X == X && Selected->Y == Y;
      Mid->SetVectorParameterValue(TEXT("Tint"),
                                   bOwnCell ? FLinearColor(0.5f, 0.5f, 0.55f)
                                            : FLinearColor(0.15f, 0.9f, 0.3f));
      Mesh->SetMaterial(0, Mid);
    }
    Tile->SetRootComponent(Mesh);
    Mesh->RegisterComponent();
    HighlightTiles.Add(Tile);
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
