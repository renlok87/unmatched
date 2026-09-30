#include "S08BoardActor.h"
#include "S08ArtHudText.h"
#include "S08ArtPreviewMedusa.h"
#include "S08Diorama.h"
#include "S08FighterActor.h"
#include "S08Render.h"
#include "S08TraceLog.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/SkyLightComponent.h"
#include "Engine/PostProcessVolume.h"
#include "Engine/SkyLight.h"
#include "Engine/TextureCube.h"
#include "Components/SceneComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/CollisionProfile.h"
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

  // W5b-R D-4: stroke keylines (and cube glyph keylines) under the zone fills.
  ArtZoneKeylines = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("ArtZoneKeylines"));
  ArtZoneKeylines->SetupAttachment(RootComponent);
  ArtZoneKeylines->SetStaticMesh(Cube);
  ArtZoneKeylines->SetCollisionEnabled(ECollisionEnabled::NoCollision);
  ArtZoneKeylines->SetVisibility(false);
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
  // Wave 5c-B: the diorama tray only with -ArtPreviewDiorama (hidden until an art profile is active).
  EnsureDioramaTray(true);

  // T3.2 board data: zone palette/glyphs per key, light profiles, board
  // profiles. Without valid data no board gets art (grey board, traced).
  {
    TArray<FString> Errors;
    bool bOverride = false;
    const FString ProfilesPath = FS08BoardArtData::ResolvePath(bOverride);
    bArtDataLoaded = ArtData.LoadFile(ProfilesPath, Errors);
    // W4-A RENDER fingerprint: which bytes the light profiles came from.
    AppliedRender.ProfilesSha256 = ArtData.SourceSha256;
    AppliedRender.ProfilesSource = bOverride ? TEXT("override") : TEXT("pak");
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW board profiles loaded=%d revision=%d boards=%d zoneStyles=%d lightProfiles=%d errors=%d path=Config/ArtBoards/S08ArtBoardProfiles.json"),
        bArtDataLoaded ? 1 : 0, ArtData.Revision, ArtData.Boards.Num(), ArtData.ZoneStyles.Num(),
        ArtData.Lights.Num(), Errors.Num()));
    FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW board profiles source=%s sha256=%s%s%s"),
                                     *AppliedRender.ProfilesSource,
                                     ArtData.SourceSha256.IsEmpty() ? TEXT("-") : *ArtData.SourceSha256,
                                     bOverride ? TEXT(" overridePath=") : TEXT(""),
                                     bOverride ? *ProfilesPath : TEXT("")));
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
  // T4.2 content (ART-005): zone MIs of the game-layer master (MI_ART005_Zone_<Key>, LayerColor = the data
  // colour) and glyph meshes (SM_ART005_ZoneGlyph_<Glyph> = the S08GlyphPieces cubes merged). Soft paths from
  // the data, cooked through DirectoriesToAlwaysCook /Game/ArtTests/ART005. A missing asset keeps the runtime
  // tint MID / cube pieces (traced); -S08LegacyRender (pre-W4 emulation) loads none of them.
  if (!S08LegacyRender()) {
    int32 Wanted = 0, Loaded = 0;
    auto LoadInstance = [&](const FString& MapKey, const FS08ZoneStyle& Style) {
      if (Style.MaterialInstancePath.IsEmpty()) return;
      ++Wanted;
      if (UMaterialInterface* M = LoadObject<UMaterialInterface>(nullptr, *Style.MaterialInstancePath)) {
        ArtZoneInstances.Add(MapKey, M);
        ++Loaded;
      } else {
        FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW zone content missing key=%s mi=%s (tint fallback)"),
                                         MapKey.IsEmpty() ? TEXT("(fallback)") : *MapKey, *Style.MaterialInstancePath));
      }
    };
    for (const TPair<FString, FS08ZoneStyle>& Style : ArtData.ZoneStyles) LoadInstance(Style.Key, Style.Value);
    LoadInstance(FString(), ArtData.FallbackStyle);
    int32 MeshesLoaded = 0;
    for (const TPair<FString, FString>& GlyphPath : ArtData.GlyphMeshPaths) {
      if (UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, *GlyphPath.Value)) {
        ArtGlyphMeshes.Add(GlyphPath.Key, Mesh);
        ++MeshesLoaded;
      } else {
        FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW zone content missing glyph=%s mesh=%s (cube pieces)"),
                                         *GlyphPath.Key, *GlyphPath.Value));
      }
    }
    FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW zone content instances=%d/%d glyphMeshes=%d/%d"), Loaded,
                                     Wanted, MeshesLoaded, ArtData.GlyphMeshPaths.Num()));
    // W5b-R D-4 keylines: the keyline MI and the glyph keyline meshes of the data (profile rev 4 "zoneKeyline").
    if (ArtData.Keyline.bSet) {
      if (!ArtData.Keyline.MaterialInstancePath.IsEmpty()) {
        ArtKeylineMaterial = LoadObject<UMaterialInterface>(nullptr, *ArtData.Keyline.MaterialInstancePath);
      }
      int32 KeyMeshes = 0;
      for (const TPair<FString, FString>& Path : ArtData.Keyline.GlyphMeshPaths) {
        if (UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, *Path.Value)) {
          ArtGlyphKeylineMeshes.Add(Path.Key, Mesh);
          ++KeyMeshes;
        } else {
          FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW zone keyline content missing glyph=%s mesh=%s (cube pieces)"),
                                           *Path.Key, *Path.Value));
        }
      }
      FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW zone keyline content mi=%s glyphKeyMeshes=%d/%d color=#%02X%02X%02X"),
                                       ArtKeylineMaterial ? *ArtKeylineMaterial->GetName() : TEXT("missing(tint)"),
                                       KeyMeshes, ArtData.Keyline.GlyphMeshPaths.Num(), ArtData.Keyline.Color.R,
                                       ArtData.Keyline.Color.G, ArtData.Keyline.Color.B));
    } else {
      FS08Trace::Write(TEXT("ARTPREVIEW zone keyline content none (profile without zoneKeyline)"));
    }
  }
  // W4-A game layer: unlit + EyeAdaptationInverse (M_S08_GameLayerUnlit);
  // -S08LegacyRender or a missing asset keeps the pre-W4 M_S08_Solid.
  ArtSolidMaterial = S08GameLayerMaterial();
  S08ApplyGameLayerPrimitive(ArtZoneGlyphs);
  S08ApplyGameLayerPrimitive(ArtZoneKeylines);
  if (!ArtKeylineMaterial && ArtData.Keyline.bSet && ArtSolidMaterial && !S08LegacyRender()) {
    UMaterialInstanceDynamic* Mid = UMaterialInstanceDynamic::Create(ArtSolidMaterial, this);
    Mid->SetVectorParameterValue(TEXT("Tint"), FLinearColor::FromSRGBColor(ArtData.Keyline.Color));
    ArtKeylineMaterial = Mid;
  }
  if (ArtKeylineMaterial) {
    ArtZoneKeylines->SetMaterial(0, ArtKeylineMaterial);
    ArtKeylineMaterialName = ArtKeylineMaterial->GetName();
  }
  FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW game layer material=%s unlitEyeAdaptInv=%d legacyRender=%d"),
                                   ArtSolidMaterial ? *ArtSolidMaterial->GetName() : TEXT("none"),
                                   S08GameLayerIsUnlit() ? 1 : 0, S08LegacyRender() ? 1 : 0));
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

ES08TeamSlot AS08BoardActor::TeamOfFighter(const FS08BoardFighter& Fighter) const {
  return S08TeamOf(Fighter.Id, Fighter.OwnerId, TeamP1OwnerId);
}

void AS08BoardActor::SetScreenLabelMode(bool bScreen) {
  if (bScreenLabelMode == bScreen) return;
  bScreenLabelMode = bScreen;
  for (AS08FighterActor* Actor : FighterActors) {
    if (Actor) Actor->SetWorldLabelsSuppressed(bScreen);
  }
  for (const TPair<FString, TWeakObjectPtr<AActor>>& Entry : DamageNumbers) {
    if (!Entry.Value.IsValid()) continue;
    if (USceneComponent* Root = Entry.Value.Get()->GetRootComponent()) Root->SetVisibility(!bScreen);
  }
  FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW screen labels=%d (world TextRender labels and damage text %s)"),
                                   bScreen ? 1 : 0, bScreen ? TEXT("hidden") : TEXT("shown")));
}

int32 AS08BoardActor::GetDamageNumberSeq(const FString& FighterId) const {
  const TWeakObjectPtr<AActor>* Number = DamageNumbers.Find(FighterId);
  if (!Number || !Number->IsValid()) return -1;
  const FIntPoint* Info = DamageNumberInfo.Find(FighterId);
  return Info ? Info->Y : -1;
}

int32 AS08BoardActor::GetDamageNumberAmount(const FString& FighterId) const {
  const TWeakObjectPtr<AActor>* Number = DamageNumbers.Find(FighterId);
  if (!Number || !Number->IsValid()) return 0;
  const FIntPoint* Info = DamageNumberInfo.Find(FighterId);
  return Info ? Info->X : 0;
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
  Text->SetText(S08ArtHudText::DamageNumber(Damage));
  Text->SetHorizontalAlignment(EHTA_Center);
  Text->SetWorldSize(25.0f);
  Text->SetTextRenderColor(FColor(255, 224, 175));
  Text->SetCollisionEnabled(ECollisionEnabled::NoCollision);
  S08ApplyGameLayerPrimitive(Text);
  Text->RegisterComponent();
  // W5b-R D-1: with the screen tag layer the number is drawn by the HUD (US08ArtDamageWidget); this actor keeps the
  // 0.9 s lifetime, the exactly-once dedupe and the trace line.
  Text->SetVisibility(!bScreenLabelMode);
  Number->SetActorLocation(Position);
  Number->SetActorRotation(FRotator(0.0f, 90.0f, 0.0f));
  Number->SetLifeSpan(0.9f);
  DamageNumbers.Add(FighterId, Number);
  DamageNumberInfo.Add(FighterId, FIntPoint(Damage, SequenceNumber));
  FS08Trace::Write(FString::Printf(
      TEXT("ARTPREVIEW damage-number fighter=%s amount=%d seq=%d cell=(%d,%d)"),
      *FighterId, Damage, SequenceNumber, Target->X, Target->Y));
}

void AS08BoardActor::ClearChildren() {
  for (const TPair<FString, TWeakObjectPtr<AActor>>& Entry : DamageNumbers) {
    if (Entry.Value.IsValid()) Entry.Value.Get()->Destroy();
  }
  DamageNumbers.Reset();
  DamageNumberInfo.Reset();
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
  S08ApplyGameLayerPrimitive(Component);
  Component->RegisterComponent();
  ArtZoneStrokes.Add(Style.Key, Component);
  return Component;
}

UMaterialInterface* AS08BoardActor::ZoneMaterialFor(const FS08ZoneStyle& Style, bool& bOutAuthored,
                                                    bool& bOutIsmUsage) {
  bOutAuthored = false;
  bOutIsmUsage = false;
  // W4-A: zones are game layer - the data colour on the unlit
  // EyeAdaptationInverse material for every key. The ART-005 review
  // materials (no ISM usage: default material in cooked builds) stay only in
  // the -S08LegacyRender bench leg.
  TObjectPtr<UMaterialInterface>* Authored = S08LegacyRender() ? ArtZoneMaterials.Find(Style.Key) : nullptr;
  if (Authored) {
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
  // T4.2: the zone MI of the data (same linear colour as the tint below, on the game-layer master).
  if (UMaterialInterface* Instance = ZoneInstanceFor(Style)) {
    const UMaterial* Base = Instance->GetMaterial();
    bOutIsmUsage = Base && Base->GetUsageByFlag(MATUSAGE_InstancedStaticMeshes);
    return Instance;
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

UMaterialInterface* AS08BoardActor::ZoneInstanceFor(const FS08ZoneStyle& Style) const {
  if (S08LegacyRender()) return nullptr;
  const TObjectPtr<UMaterialInterface>* Found = ArtZoneInstances.Find(Style.bFallback ? FString() : Style.Key);
  return Found ? Found->Get() : nullptr;
}

UInstancedStaticMeshComponent* AS08BoardActor::ZoneGlyphMeshComponent(const FS08ZoneStyle& Style) {
  if (S08LegacyRender()) return nullptr;
  const TObjectPtr<UStaticMesh>* Mesh = ArtGlyphMeshes.Find(S08ZoneGlyphName(Style.Glyph));
  if (!Mesh || !*Mesh) return nullptr;
  if (TObjectPtr<UInstancedStaticMeshComponent>* Found = ArtZoneGlyphMeshes.Find(Style.Key)) {
    if (*Found) return *Found;
  }
  UInstancedStaticMeshComponent* Component = NewObject<UInstancedStaticMeshComponent>(
      this, FName(*(ZoneComponentName(Style.Key) + TEXT("_Glyph"))));
  Component->SetupAttachment(RootComponent);
  Component->SetStaticMesh(*Mesh);
  Component->SetCollisionEnabled(ECollisionEnabled::NoCollision);
  S08ApplyGameLayerPrimitive(Component);
  Component->RegisterComponent();
  ArtZoneGlyphMeshes.Add(Style.Key, Component);
  return Component;
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
  const FString Sha = AppliedRender.ProfilesSha256;
  const FString Source = AppliedRender.ProfilesSource;
  AppliedRender = FS08AppliedRender();
  AppliedRender.ProfilesSha256 = Sha;
  AppliedRender.ProfilesSource = Source;
}

void AS08BoardActor::ApplyArtLights(const FS08LightProfile& Light, bool bLegacyCobbleTrace) {
  if (ActiveLightProfileId == Light.Id && !ArtLights.IsEmpty()) return;
  ClearArtLights();
  // S08Arena has no scene lights, so a PBR board would be black. Profile data:
  // 1 directional with shadow + <= 6 point lights without shadow (budget
  // validated on load). Measured probe candidates, not lighting norms.
  // W4-A (G01): a UPointLightComponent spawned at runtime starts Unitless
  // (LocalLightComponent.cpp: IntensityUnits = Unitless, 1 = 16 internal)
  // while the editor probes the profiles came from were CANDELAS
  // (1 = 10000 internal): the same number was 625x (9.3 EV) darker in every
  // pre-W4 packaged frame. Units are set BEFORE the intensity. A profile
  // without "units" (pre-W4 data) or -S08LegacyRender keeps Unitless.
  const bool bLegacy = S08LegacyRender();
  const bool bCandelas = Light.HasPhysicalUnits() && !bLegacy;
  const TArray<FS08PlacedLight> Placed = S08PlaceLights(Light, BoardModel);
  bool bOk = true;
  float Key = 0.0f, Fill = 0.0f, Warm = 0.0f;
  int32 Points = 0, PointShadows = 0, ShadowCasters = 0;
  FString KeyShadow = TEXT("csm-default");
  for (const FS08PlacedLight& P : Placed) {
    if (P.Spec.bDirectional) {
      ADirectionalLight* Dir = GetWorld()->SpawnActor<ADirectionalLight>(P.Position, P.Spec.Rotation);
      if (!Dir) {
        bOk = false;
        break;
      }
      UDirectionalLightComponent* DirComponent = CastChecked<UDirectionalLightComponent>(Dir->GetLightComponent());
      DirComponent->SetMobility(EComponentMobility::Movable);
      DirComponent->SetIntensity(P.Spec.Intensity);  // lux (the only directional unit)
      DirComponent->SetCastShadows(P.Spec.bCastShadows);
      if (P.Spec.bHasColor) DirComponent->SetLightColor(P.Spec.Color);
      if (Light.KeyShadow.bSet && !bLegacy) {
        // CSM fitted to the fixed diorama camera instead of the 40000 uu /
        // 4 cascade default (the K1 board sat in the 2nd cascade).
        DirComponent->SetDynamicShadowDistanceMovableLight(Light.KeyShadow.DistanceUU);
        DirComponent->SetDynamicShadowCascades(Light.KeyShadow.Cascades);
        DirComponent->ContactShadowLength = Light.KeyShadow.ContactShadowLength;
        DirComponent->MarkRenderStateDirty();
        KeyShadow = FString::Printf(TEXT("csm-%.0fuu-%dc-contact%.3f"), Light.KeyShadow.DistanceUU,
                                    Light.KeyShadow.Cascades, Light.KeyShadow.ContactShadowLength);
      }
      ArtLights.Add(Dir);
      Key = P.Spec.Intensity;
      ShadowCasters += P.Spec.bCastShadows ? 1 : 0;
    } else {
      APointLight* Point = GetWorld()->SpawnActor<APointLight>(P.Position, FRotator::ZeroRotator);
      if (!Point) {
        bOk = false;
        break;
      }
      UPointLightComponent* Component = CastChecked<UPointLightComponent>(Point->GetLightComponent());
      Component->SetMobility(EComponentMobility::Movable);
      if (bCandelas) Component->SetIntensityUnits(ELightUnits::Candelas);
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
        TEXT("ARTPREVIEW light profile=%s name=%s role=%s kind=%s at=(%.0f,%.0f,%.0f) intensity=%g units=%s radius=%g color=(%.2f,%.2f,%.2f) shadow=%d"),
        *Light.Id, *P.Spec.Name, *P.Spec.Role, P.Spec.bDirectional ? TEXT("directional") : TEXT("point"),
        P.Position.X, P.Position.Y, P.Position.Z, P.Spec.Intensity,
        P.Spec.bDirectional ? TEXT("lux") : (bCandelas ? TEXT("candelas") : TEXT("unitless-legacy")), P.Spec.RadiusUU,
        P.Spec.Color.R, P.Spec.Color.G, P.Spec.Color.B, P.Spec.bCastShadows ? 1 : 0));
  }
  // W4-A (memo §1 item 3): a Movable SkyLight from the profile replaces the
  // point "ambient"; Lumen traces its visibility (SSAO/DFAO-free on SM6), the
  // SM5 fallback shades it with SSAO. Deferred spawn: mobility and source
  // are set before the component registers.
  if (bOk && Light.Sky.bSet && !bLegacy) {
    UTextureCube* Cube = LoadObject<UTextureCube>(nullptr, *Light.Sky.CubemapPath);
    ASkyLight* Sky = Cube ? GetWorld()->SpawnActorDeferred<ASkyLight>(ASkyLight::StaticClass(), FTransform::Identity)
                          : nullptr;
    if (Sky) {
      USkyLightComponent* SkyComponent = Sky->GetLightComponent();
      SkyComponent->SetMobility(EComponentMobility::Movable);
      SkyComponent->SourceType = SLS_SpecifiedCubemap;
      SkyComponent->Cubemap = Cube;
      SkyComponent->Intensity = Light.Sky.Intensity;
      SkyComponent->LightColor = Light.Sky.Color.ToFColor(true);
      SkyComponent->bLowerHemisphereIsBlack = Light.Sky.bLowerHemisphereIsBlack;
      SkyComponent->LowerHemisphereColor = Light.Sky.LowerHemisphereColor;
      SkyComponent->bRealTimeCapture = false;
      Sky->FinishSpawning(FTransform::Identity);
      SkyComponent->SetLightColor(Light.Sky.Color);
      SkyComponent->RecaptureSky();
      ArtLights.Add(Sky);
      AppliedRender.bSky = true;
      AppliedRender.SkyIntensity = Light.Sky.Intensity;
    }
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW sky profile=%s cubemap=%s loaded=%d spawned=%d intensity=%g color=(%.2f,%.2f,%.2f) lowerBlack=%d"),
        *Light.Id, *Light.Sky.CubemapPath, Cube ? 1 : 0, Sky ? 1 : 0, Light.Sky.Intensity, Light.Sky.Color.R,
        Light.Sky.Color.G, Light.Sky.Color.B, Light.Sky.bLowerHemisphereIsBlack ? 1 : 0));
  }
  // W4-A (memo §1 item 1): the exposure of the profile, identical in packaged
  // runs and the editor control scene: an unbound volume, histogram with
  // min == max brightness (a fixed exposure) + bias. Without it the engine
  // default r.DefaultFeature.AutoExposure=0 gives min=max=1, bias 1.
  if (bOk && Light.Exposure.bSet && !bLegacy) {
    APostProcessVolume* Volume = GetWorld()->SpawnActor<APostProcessVolume>(FVector::ZeroVector, FRotator::ZeroRotator);
    if (Volume) {
      Volume->bUnbound = true;
      Volume->Priority = 100.0f;
      Volume->BlendWeight = 1.0f;
      FPostProcessSettings& S = Volume->Settings;
      S.bOverride_AutoExposureMethod = true;
      S.AutoExposureMethod = AEM_Histogram;
      S.bOverride_AutoExposureMinBrightness = true;
      S.AutoExposureMinBrightness = Light.Exposure.MinBrightness;
      S.bOverride_AutoExposureMaxBrightness = true;
      S.AutoExposureMaxBrightness = Light.Exposure.MaxBrightness;
      S.bOverride_AutoExposureBias = true;
      S.AutoExposureBias = Light.Exposure.Bias;
      ArtLights.Add(Volume);
      AppliedRender.bExposure = true;
      AppliedRender.ExposureMin = Light.Exposure.MinBrightness;
      AppliedRender.ExposureMax = Light.Exposure.MaxBrightness;
      AppliedRender.ExposureBias = Light.Exposure.Bias;
      AppliedRender.Ev100 = Light.Exposure.Ev100;
    }
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW exposure profile=%s method=histogram-fixed min=%.5f max=%.5f bias=%.3f ev100=%.2f volume=%d"),
        *Light.Id, Light.Exposure.MinBrightness, Light.Exposure.MaxBrightness, Light.Exposure.Bias,
        Light.Exposure.Ev100, Volume ? 1 : 0));
  }
  if (!bOk) {
    ClearArtLights();
    FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW lights profile=%s failed"), *Light.Id));
    if (bLegacyCobbleTrace) FS08Trace::Write(TEXT("ARTPREVIEW Cobble probe lights failed"));
    return;
  }
  ActiveLightProfileId = Light.Id;
  AppliedRender.bArt = true;
  AppliedRender.ProfileId = Light.Id;
  AppliedRender.PointUnits = bCandelas ? TEXT("candelas") : TEXT("unitless-legacy");
  AppliedRender.ShadowCasters = ShadowCasters;
  AppliedRender.KeyShadow = KeyShadow;
  FString Budget;
  const bool bBudget = Light.BudgetOk(Budget);
  FS08Trace::Write(FString::Printf(
      TEXT("ARTPREVIEW lights applied profile=%s directional=%d shadow=%d points=%d pointShadows=%d budgetOk=%d"),
      *Light.Id, Light.bHasDirectional ? 1 : 0, Light.Directional.bCastShadows ? 1 : 0, Points, PointShadows,
      bBudget ? 1 : 0));
  FS08Trace::Write(FString::Printf(
      TEXT("ARTPREVIEW render profile=%s units=%s sky=%d exposure=%d keyShadow=%s shadowCasters=%d legacyRender=%d"),
      *Light.Id, *AppliedRender.PointUnits, AppliedRender.bSky ? 1 : 0, AppliedRender.bExposure ? 1 : 0,
      *KeyShadow, ShadowCasters, bLegacy ? 1 : 0));
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

bool AS08BoardActor::EnsureDioramaTray(bool bArtPreview) {
  if (DioramaTray) return true;
  if (!S08Diorama::Enabled(bArtPreview)) return false;
  UStaticMesh* TrayMesh = LoadObject<UStaticMesh>(nullptr, S08Diorama::MeshPath);
  UMaterialInterface* TrayMi = LoadObject<UMaterialInterface>(nullptr, S08Diorama::MaterialPath);
  if (!TrayMesh) {
    FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW diorama tray missing mesh=%s mi=%d (no tray)"),
                                     S08Diorama::MeshPath, TrayMi ? 1 : 0));
    return false;
  }
  DioramaTray = NewObject<UStaticMeshComponent>(this, TEXT("ArtDioramaTray"));
  DioramaTray->SetupAttachment(RootComponent);
  DioramaTray->SetCollisionEnabled(ECollisionEnabled::NoCollision);
  DioramaTray->SetCollisionProfileName(UCollisionProfile::NoCollision_ProfileName);
  DioramaTray->SetGenerateOverlapEvents(false);
  DioramaTray->SetCanEverAffectNavigation(false);
  DioramaTray->SetStaticMesh(TrayMesh);
  if (TrayMi) DioramaTray->SetMaterial(0, TrayMi);
  DioramaTray->SetRelativeLocation(FVector::ZeroVector);
  DioramaTray->SetVisibility(false);
  DioramaTray->RegisterComponent();
  FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW diorama requested mesh=%s mi=%s"), *TrayMesh->GetPathName(),
                                   TrayMi ? *TrayMi->GetName() : TEXT("missing(mesh default)")));
  return true;
}

void AS08BoardActor::PlaceDioramaTray(bool bVisible, const FVector2D& BoardHalf, const TCHAR* Surface) {
  if (!DioramaTray) return;
  if (!bVisible) {
    DioramaTray->SetVisibility(false);
    FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW diorama tray hidden surface=%s (no art board)"), Surface));
    return;
  }
  const S08Diorama::FTrayFit Fit = S08Diorama::FitTray(BoardHalf);
  DioramaTray->SetRelativeLocationAndRotation(FVector::ZeroVector, FRotator(0.0f, Fit.YawDeg, 0.0f));
  DioramaTray->SetRelativeScale3D(Fit.Scale);
  DioramaTray->SetVisibility(true);
  const UStaticMesh* Mesh = DioramaTray->GetStaticMesh();
  const FBox Box = Mesh ? Mesh->GetBoundingBox().TransformBy(DioramaTray->GetComponentTransform()) : FBox(ForceInit);
  const UMaterialInterface* Mi = DioramaTray->GetMaterial(0);
  const FVector Size = Box.GetSize();
  FS08Trace::Write(FString::Printf(
      TEXT("ARTPREVIEW diorama tray=%s mi=%s surface=%s yaw=%.1f scale=%.3fx%.3fx%.3f bounds=(%.1f,%.1f,%.1f)..(%.1f,%.1f,%.1f) size=%.1fx%.1fx%.1f topZ=%.1f boardHalf=%.1fx%.1f rimUU=%.1f collision=none"),
      Mesh ? *Mesh->GetPathName() : TEXT("-"), Mi ? *Mi->GetName() : TEXT("-"), Surface, Fit.YawDeg, Fit.Scale.X,
      Fit.Scale.Y, Fit.Scale.Z, Box.Min.X, Box.Min.Y, Box.Min.Z, Box.Max.X, Box.Max.Y, Box.Max.Z, Size.X, Size.Y,
      Size.Z, Box.Max.Z, BoardHalf.X, BoardHalf.Y, S08Diorama::RimUU));
}

void AS08BoardActor::UpdateDioramaTray(const FS08BoardModel& Board) {
  if (!DioramaTray) return;
  if (!bArtActive) {
    PlaceDioramaTray(false, FVector2D::ZeroVector, TEXT("grey"));
    return;
  }
  FVector2D Half = S08Diorama::TilesFrameHalf(Board.Width, Board.Height, FS08BoardModel::CellSizeUU, ArtFrameUU);
  if (!bArtTiles && ArtBoard->GetStaticMesh()) {
    // cobble-5x6-mesh: the frame of the ART-005 slab itself (world +-278 x +-328 at yaw -90).
    const FBox B = ArtBoard->GetStaticMesh()->GetBoundingBox().TransformBy(ArtBoard->GetRelativeTransform());
    Half = FVector2D(FMath::Max(-B.Min.X, B.Max.X), FMath::Max(-B.Min.Y, B.Max.Y));
  }
  PlaceDioramaTray(true, Half, S08BoardSurfaceName(ActiveProfile.Surface));
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
  ArtZoneKeylines->ClearInstances();
  for (TPair<FString, TObjectPtr<UInstancedStaticMeshComponent>>& Key : ArtZoneGlyphKeylines) {
    if (Key.Value) {
      Key.Value->ClearInstances();
      Key.Value->SetVisibility(bArtActive);
    }
  }
  for (TPair<FString, TObjectPtr<UInstancedStaticMeshComponent>>& Stroke : ArtZoneStrokes) {
    if (Stroke.Value) {
      Stroke.Value->ClearInstances();
      Stroke.Value->SetVisibility(bArtActive);
    }
  }
  for (TPair<FString, TObjectPtr<UInstancedStaticMeshComponent>>& Glyph : ArtZoneGlyphMeshes) {
    if (Glyph.Value) {
      Glyph.Value->ClearInstances();
      Glyph.Value->SetVisibility(bArtActive);
    }
  }
  ApplySurfaceMaterials();
  NormalTiles->SetVisibility(!bArtActive);
  BlockerTiles->SetVisibility(!bArtActive);
  UnderlayTiles->SetVisibility(!bCobbleMesh);
  ArtBoard->SetVisibility(bCobbleMesh);
  ArtCorners->SetVisibility(bArtActive);
  ArtZoneGlyphs->SetVisibility(bArtActive);
  const bool bKeylines = bArtActive && ArtData.Keyline.bSet && ArtKeylineMaterial && !S08LegacyRender();
  ArtZoneKeylines->SetVisibility(bKeylines);
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
    const bool bZoneColorGlyphs = ActiveProfile.bZoneColorGlyphs || !S08LegacyRender();
    // T4.2: a key whose glyph has a mesh gets one instance per zone slot (GlyphAnchors) instead of its cube
    // pieces; same geometry, same MI as its strokes.
    TMap<FString, int32> GlyphMeshInstances;
    if (bZoneColorGlyphs) {
      for (const FS08ZoneMarkPiece& Anchor : Marks.GlyphAnchors) {
        const FS08ZoneStyle Style = ArtData.StyleFor(Anchor.Key);
        if (UInstancedStaticMeshComponent* Component = ZoneGlyphMeshComponent(Style)) {
          bool bAuthored = false, bIsm = false;
          Component->SetMaterial(0, ZoneMaterialFor(Style, bAuthored, bIsm));
          Component->SetVisibility(true);
          Component->AddInstance(Anchor.Transform, true);
          GlyphMeshInstances.FindOrAdd(Anchor.Key) += 1;
        }
      }
    }
    int32 CubeGlyphPieces = 0;
    for (const FS08ZoneMarkPiece& Piece : Marks.Glyphs) {
      if (GlyphMeshInstances.Contains(Piece.Key)) continue;
      UInstancedStaticMeshComponent* Target = bZoneColorGlyphs
          ? ZoneStrokeComponent(ArtData.StyleFor(Piece.Key)) : ArtZoneGlyphs.Get();
      if (Target) {
        Target->AddInstance(Piece.Transform, true);
        ++CubeGlyphPieces;
      }
    }
    int32 GlyphMeshTotal = 0;
    for (const TPair<FString, int32>& Count : GlyphMeshInstances) GlyphMeshTotal += Count.Value;
    // W5b-R D-4 keylines under every stroke and glyph (never part of the zone counts above).
    if (bKeylines) {
      int32 StrokeKeyPieces = 0, GlyphKeyInstances = 0, GlyphKeyCubePieces = 0;
      for (const FS08ZoneMarkPiece& Piece : Marks.StrokeKeylines) {
        ArtZoneKeylines->AddInstance(Piece.Transform, true);
        ++StrokeKeyPieces;
      }
      TSet<FString> MeshKeys;
      for (const FS08ZoneMarkPiece& Anchor : Marks.GlyphAnchors) {
        const FS08ZoneStyle Style = ArtData.StyleFor(Anchor.Key);
        const FString GlyphName = S08ZoneGlyphName(Style.Glyph);
        const TObjectPtr<UStaticMesh>* Mesh = ArtGlyphKeylineMeshes.Find(GlyphName);
        if (!Mesh || !*Mesh) continue;
        TObjectPtr<UInstancedStaticMeshComponent>& Component = ArtZoneGlyphKeylines.FindOrAdd(GlyphName);
        if (!Component) {
          Component = NewObject<UInstancedStaticMeshComponent>(this, FName(*(TEXT("ArtZoneGlyphKey_") + GlyphName)));
          Component->SetupAttachment(RootComponent);
          Component->SetStaticMesh(*Mesh);
          Component->SetCollisionEnabled(ECollisionEnabled::NoCollision);
          S08ApplyGameLayerPrimitive(Component);
          Component->RegisterComponent();
        }
        Component->SetMaterial(0, ArtKeylineMaterial);
        Component->SetVisibility(true);
        Component->AddInstance(Anchor.Transform, true);
        MeshKeys.Add(Anchor.Key);
        ++GlyphKeyInstances;
      }
      for (const FS08ZoneMarkPiece& Piece : Marks.GlyphKeylines) {
        if (MeshKeys.Contains(Piece.Key)) continue;
        ArtZoneKeylines->AddInstance(Piece.Transform, true);
        ++GlyphKeyCubePieces;
      }
      FS08Trace::Write(FString::Printf(
          TEXT("ARTPREVIEW board zone keylines pieces=%d glyphKeys=%d glyphKeyCubePieces=%d mi=%s growUU=%.1f edgeUU=%.1f maxOuterUU=%.1f"),
          StrokeKeyPieces, GlyphKeyInstances, GlyphKeyCubePieces, *ArtKeylineMaterialName, ArtData.Keyline.GrowUU,
          S08ZoneMarkSpec::EdgeUU, S08ZoneMarkSpec::MaxOuterUU));
    } else if (bArtActive) {
      FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW board zone keylines none (data=%d material=%d legacyRender=%d)"),
                                       ArtData.Keyline.bSet ? 1 : 0, ArtKeylineMaterial ? 1 : 0, S08LegacyRender() ? 1 : 0));
    }
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW board glyph meshes instances=%d keys=%d/%d cubePieces=%d anchors=%d"), GlyphMeshTotal,
        GlyphMeshInstances.Num(), Summary.ZoneKeys.Num(), CubeGlyphPieces, Marks.GlyphAnchors.Num()));
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
        (ActiveProfile.bZoneColorGlyphs || !S08LegacyRender()) ? TEXT("zone") : TEXT("review"), Mismatch.IsEmpty() ? 1 : 0,
        Mismatch.IsEmpty() ? TEXT("") : *(TEXT(" mismatch=") + Mismatch)));
    for (const FString& Key : Summary.ZoneKeys) {
      const FS08ZoneStyle Style = ArtData.StyleFor(Key);
      bool bAuthored = false, bIsm = false;
      ZoneMaterialFor(Style, bAuthored, bIsm);
      const UMaterialInterface* Instance = bAuthored ? nullptr : ZoneInstanceFor(Style);
      const TObjectPtr<UInstancedStaticMeshComponent>* GlyphMesh = ArtZoneGlyphMeshes.Find(Key);
      const UStaticMesh* GlyphAsset = GlyphMesh && *GlyphMesh ? (*GlyphMesh)->GetStaticMesh().Get() : nullptr;
      FS08Trace::Write(FString::Printf(
          TEXT("ARTPREVIEW board zone key=%s cells=%d stroke=%s glyph=%s %s=%s ismUsage=%d strokePieces=%d glyphPieces=%d mi=%s glyphMesh=%s glyphInstances=%d fallback=%d"),
          *Key, Marks.CellsByKey.FindRef(Key), S08ZoneStrokeName(Style.Stroke), S08ZoneGlyphName(Style.Glyph),
          bAuthored ? TEXT("material") : TEXT("color"),
          bAuthored ? *FPaths::GetBaseFilename(Style.MaterialPath) : *Style.ColorHex(),
          bAuthored ? (bIsm ? 1 : 0) : (Instance ? (bIsm ? 1 : 0) : 1), Marks.StrokePiecesByKey.FindRef(Key),
          Marks.GlyphPiecesByKey.FindRef(Key), Instance ? *Instance->GetName() : TEXT("-"),
          GlyphAsset ? *GlyphAsset->GetName() : TEXT("-"), GlyphMeshInstances.FindRef(Key),
          Style.bFallback ? 1 : 0));
    }
    FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW board multizone cells=%d zonesListed=%d zonesMarked=%d"),
                                     Marks.MultizoneCells, Marks.MultizoneZonesListed, Marks.MultizoneZonesMarked));
    for (const FString& Line : Marks.MultizoneLines) {
      FS08Trace::Write(TEXT("ARTPREVIEW board multizone cell=") + Line);
    }
  }
  UpdateDioramaTray(Board);
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
      Actor->SetWorldLabelsSuppressed(bScreenLabelMode);
      const bool bOwn = Fighter.OwnerId == OwnOwnerId;
      const ES08TeamSlot Team = TeamOfFighter(Fighter);
      Actor->SetTeam(Team, S08TeamLook(Team, bOwn, TeamColorMode), TeamColorMode);
      Actor->ApplyFighter(Fighter, Board.CellToWorld(Fighter.X, Fighter.Y), bOwn, bArtActive);
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
  // Wave 5c-B: one summary per change of the v2 roster (-ArtPreviewHeroesV2 only).
  if (bArtActive && S08HeroesV2::FlagEnabled() && FighterActors.Num() > 0) {
    int32 Mapped = 0, V2 = 0;
    for (const AS08FighterActor* Actor : FighterActors) {
      if (!Actor) continue;
      if (S08HeroesV2::Find(true, true, Actor->GetFighter().Name)) ++Mapped;
      if (Actor->IsHeroV2()) ++V2;
    }
    const FString Key = FString::Printf(TEXT("fighters=%d mapped=%d v2=%d"), FighterActors.Num(), Mapped, V2);
    if (Key != HeroesV2SummaryKey) {
      HeroesV2SummaryKey = Key;
      FS08Trace::Write(TEXT("ARTPREVIEW heroesV2 summary ") + Key);
    }
  }
}

void AS08BoardActor::NotifyFighterAnimEvent(const FString& FighterId, S08HeroesV2::EEvent Event,
                                            int32 SequenceNumber) {
  if (!bArtActive || !S08HeroesV2::FlagEnabled()) return;
  AS08FighterActor* Actor = FindFighterActor(FighterId);
  if (!Actor || !Actor->IsHeroV2()) return;
  if (!AnimEventDedupe.Accept(FString(S08HeroesV2::EventName(Event)) + TEXT(":") + FighterId, SequenceNumber)) {
    return;
  }
  Actor->NotifyHeroAnimEvent(Event, SequenceNumber);
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

  UMaterialInterface* Solid = S08GameLayerMaterial();  // W4-A game layer
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
      S08ApplyGameLayerPrimitive(Mesh);
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
  UMaterialInterface* Solid = S08GameLayerMaterial();  // W4-A game layer
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
  S08ApplyGameLayerPrimitive(Mesh);
  Mesh->RegisterComponent();
}

void AS08BoardActor::HideIllegalCell() {
  if (IllegalCell) {
    IllegalCell->Destroy();
    IllegalCell = nullptr;
  }
}
