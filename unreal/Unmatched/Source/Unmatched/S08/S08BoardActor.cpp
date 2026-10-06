#include "S08BoardActor.h"
#include "S08ArtHudText.h"
#include "S08ArtLook.h"
#include "S08ArtPreviewMedusa.h"
#include "S08Diorama.h"
#include "S08Facing.h"
#include "S08FighterActor.h"
#include "S08LiveTune.h"
#include "S08MapBackdrop.h"
#include "S08Render.h"
#include "S08TraceLog.h"
#include "UI/UmCardMedia.h"
#include "S08Contracts.h"
#include "Camera/PlayerCameraManager.h"
#include "GameFramework/PlayerController.h"
#include "Dom/JsonObject.h"
#include "HAL/FileManager.h"
#include "Misc/FileHelper.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "Components/BoxComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Engine/ExponentialHeightFog.h"
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
#include "Engine/Texture.h"
#include "Materials/Material.h"
#include "Materials/MaterialInterface.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/CommandLine.h"
#include "Misc/PackageName.h"
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

// Live tune: the sections of the profile document only BeginPlay reads (zone materials / instances, glyph meshes,
// keyline content are loaded there once), serialised compactly; a reload that changes them warns (relaunch needed).
FString S08BootSectionsSignature(const FString& Text) {
  TSharedPtr<FJsonObject> Root;
  FString Problem;
  if (!FS08Contracts::TryParseJsonObject(Text, Root, Problem) || !Root.IsValid()) return FString();
  FString Out;
  for (const TCHAR* Field : {TEXT("zoneStyles"), TEXT("fallbackZoneStyle"), TEXT("glyphMeshes"), TEXT("zoneKeyline")}) {
    FString Part = TEXT("-");
    const TSharedPtr<FJsonValue> Value = Root->TryGetField(Field);
    if (Value.IsValid()) {
      Part.Reset();
      const TSharedRef<TJsonWriter<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>> Writer =
          TJsonWriterFactory<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>::Create(&Part);
      FJsonSerializer::Serialize(Value, FString(), Writer);
    }
    Out += FString(Field) + TEXT("=") + Part + TEXT(";");
  }
  return Out;
}
} // namespace

AS08BoardActor::AS08BoardActor() {
  PrimaryActorTick.bCanEverTick = false;
  RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));

  static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeFinder(
      TEXT("/Engine/BasicShapes/Cube.Cube"));
  UStaticMesh* Cube = CubeFinder.Object;
  // ENV-MAPS track S: the map plane / grey canvas and the space discs of topology boards (components are
  // created on demand by the first topology board; a grid board never creates them).
  static ConstructorHelpers::FObjectFinder<UStaticMesh> PlaneFinder(S08MapSurfaceSpec::PlaneMeshPath);
  static ConstructorHelpers::FObjectFinder<UStaticMesh> CylinderFinder(S08MapSurfaceSpec::CylinderMeshPath);
  PlaneMesh = PlaneFinder.Object;
  CylinderMesh = CylinderFinder.Object;

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
  // ART-DEFAULT (2026-10-04, S08ArtLook.h): the accepted art look - the room board's art profile, the map image, the
  // v2 figures, the tray and the light - is the default of every run (it used to need -ArtPreview, which is now the
  // review tooling only); -S08GreyBoard keeps the grey board. One line states the effective look of the run.
  FS08Trace::Write(S08ArtLook::TraceLine());
  // VS-1 CP-02 review tooling: -ArtPreviewCardMediaProbe loads every card / back / portrait texture of the registry once.
  if (UmCardMedia::ProbeRequested(FCommandLine::Get())) FS08Trace::Write(UmCardMedia::ProbeLine());
  if (!S08ArtLook::Enabled()) return;
  // Wave 5c-B: the diorama tray (default; -S08DioramaLegacy: none) - hidden until an art profile is active.
  EnsureDioramaTray(true);
  // ENV-MAPS track C: the environment around map-image boards (same gate; nothing is created here).
  EnsureEnvLayout(true);

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
    TraceProfilesLoaded(bArtDataLoaded, bOverride, ProfilesPath, Errors);
    // live tune: what only BeginPlay reads of the document (a reload warns when it changes)
    if (S08LiveTune::Enabled()) {
      FString Text;
      FFileHelper::LoadFileToString(Text, *ProfilesPath);
      BootSectionsSignature = S08BootSectionsSignature(Text);
    }
    if (!bArtDataLoaded) {
      UE_LOG(LogTemp, Warning, TEXT("ARTPREVIEW board profiles invalid; keeping grey board"));
      FS08Trace::Write(TEXT("ARTPREVIEW board profiles invalid; keeping grey board"));
      return;
    }
  }

  // Shared art assets of every art board (2026-10-04, real boards only: the Cobble 5x6 slab and its stone / wood
  // materials are gone): the ART-005H corner brackets + iron, the ART-005 glyph material and the Medusa preview.
  UStaticMesh* Corner = LoadObject<UStaticMesh>(nullptr,
      TEXT("/Game/ArtTests/ART005H/Meshes/SM_ART005_CornerBracket_v1"));
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
  // Zone colours: optional authored review materials (-S08LegacyRender only) plus the
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
    UE_LOG(LogTemp, Warning, TEXT("ARTPREVIEW board assets missing; keeping grey board"));
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW board assets missing shared=%d medusaVariant=%s requested=%s medusa=%d; keeping grey board"),
        bShared ? 1 : 0, MedusaCandidate.Variant, *MedusaCandidate.Requested, bMedusa ? 1 : 0));
    return;
  }
  // The 'tiles' probe materials gate only the tiles surface (checked per board in Rebuild); a map-image board
  // loads its own assets (LoadMapImageAssets) and never depends on them.
  bTileArtReady = ArtStoneTileMaterial && ArtWoodMaterial && ArtVoidMaterial;
  ArtCorners->SetStaticMesh(Corner);
  ArtCorners->SetMaterial(0, Iron);
  ArtZoneGlyphs->SetMaterial(0, Glyph);
  bArtAssetsReady = true;
  FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW board assets ready tiles=%d zoneMaterials=%d"),
                                   bTileArtReady ? 1 : 0, ArtZoneMaterials.Num()));
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
                                     int32 SequenceNumber, float LifeSeconds) {
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
  // DE-018 (01 F-04): 900 ms at speed x1, scaled by the animation speed (CUE-011 "-N").
  Number->SetLifeSpan(FMath::Max(0.05f, LifeSeconds));
  DamageNumbers.Add(FighterId, Number);
  DamageNumberInfo.Add(FighterId, FIntPoint(Damage, SequenceNumber));
  FS08Trace::Write(FString::Printf(
      TEXT("ARTPREVIEW damage-number fighter=%s amount=%d seq=%d cell=(%d,%d)"),
      *FighterId, Damage, SequenceNumber, Target->X, Target->Y));
}

int32 AS08BoardActor::GetFighterContactMs(const FString& FighterId, FString& OutSource) const {
  OutSource = TEXT("default");
  const AS08FighterActor* Actor = FindFighterActor(FighterId);
  return Actor ? Actor->GetLungeContactMs(OutSource) : -1;
}

void AS08BoardActor::PlayFighterHitTint(const FString& FighterId, float Seconds) {
  if (AS08FighterActor* Actor = FindFighterActor(FighterId)) Actor->PlayHitTint(Seconds);
}

int32 AS08BoardActor::PlayFighterMoves(const TArray<FS08MovePlan>& Plans, const FS08MoveAnimParams& Params,
                                       int64 NowMs) {
  int32 Animated = 0;
  for (const FS08MovePlan& Plan : Plans) {
    AS08FighterActor* Actor = FindFighterActor(Plan.FighterId);
    if (!Actor) continue;
    Actor->PlayMove(Plan, Params, NowMs);
    if (Actor->IsMoving() && !Plan.bSnapped) ++Animated;
  }
  return Animated;
}

void AS08BoardActor::TickFighterMoves(int64 NowMs) {
  for (AS08FighterActor* Actor : FighterActors) {
    if (!Actor || !Actor->IsMoving()) continue;
    Actor->TickMove(NowMs);
    // AN-23 (ВР-06): the move ended - restate the rest angle on the post-move enemies (the plan settled to the
    // pre-move one; the dead band keeps it when nothing changed).
    if (!Actor->IsMoving()) ApplyFighterRestFacing(Actor, TEXT("move"));
  }
}

int32 AS08BoardActor::SkipFighterMoves() {
  int32 Skipped = 0;
  for (AS08FighterActor* Actor : FighterActors) {
    if (!Actor) continue;
    if (Actor->FinishMove()) {
      ++Skipped;
      ApplyFighterRestFacing(Actor, TEXT("move"));  // AN-23 (ВР-06): the skip lands the move
    }
  }
  return Skipped;
}

// ---- AN-23 (ВР-06): the rest facing ---------------------------------------------------------------------------

FVector AS08BoardActor::LocalCameraLocation() const {
  const UWorld* World = GetWorld();
  const APlayerController* PC = World ? World->GetFirstPlayerController() : nullptr;
  const APlayerCameraManager* Cam = PC ? PC->PlayerCameraManager : nullptr;
  return Cam ? Cam->GetCameraLocation() : FVector(0.0, 10000.0, 2000.0);
}

AS08FighterActor* AS08BoardActor::FigureActorAt(const FVector& WorldPos) const {
  AS08FighterActor* Best = nullptr;
  double BestDist = 0.5 * FS08BoardModel::CellSizeUU;
  for (AS08FighterActor* Actor : FighterActors) {
    if (!Actor || !Actor->GetFighter().IsAlive()) continue;
    const double Dist = FVector2D(Actor->GetActorLocation() - WorldPos).Size();
    if (Dist < BestDist) {
      BestDist = Dist;
      Best = Actor;
    }
  }
  return Best;
}

AS08FighterActor* AS08BoardActor::NearestEnemyOf(const AS08FighterActor* Me) const {
  if (!Me) return nullptr;
  AS08FighterActor* Best = nullptr;
  double BestDist = TNumericLimits<double>::Max();
  for (AS08FighterActor* Actor : FighterActors) {
    if (!Actor || Actor == Me) continue;
    const FS08BoardFighter& Other = Actor->GetFighter();
    if (!Other.IsAlive() || Other.OwnerId == Me->GetFighter().OwnerId) continue;
    const double Dist = FVector2D(Actor->GetActorLocation() - Me->GetActorLocation()).Size();
    if (Dist < BestDist) {
      BestDist = Dist;
      Best = Actor;
    }
  }
  return Best;
}

double AS08BoardActor::RestYawAt(const FVector& WorldPos) const {
  if (S08Facing::LegacyRequested()) return FS08MoveAnim::RestYawDeg(WorldPos);
  const FVector Cam = LocalCameraLocation();
  AS08FighterActor* Me = FigureActorAt(WorldPos);
  AS08FighterActor* Enemy = Me ? NearestEnemyOf(Me) : nullptr;
  if (!Me || !Enemy) return S08Facing::YawToward(WorldPos, Cam);  // no figure / no enemy: face the camera
  // A plan has no "current" angle - the dead band compares against the legacy standing angle.
  return S08Facing::RestYaw(WorldPos, Cam, true, Enemy->GetActorLocation(), FS08MoveAnim::RestYawDeg(WorldPos));
}

void AS08BoardActor::ApplyFighterRestFacing(AS08FighterActor* Actor, const TCHAR* Src) {
  if (!Actor) return;
  const bool bLegacy = S08Facing::LegacyRequested();
  const FVector Cam = LocalCameraLocation();
  AS08FighterActor* Enemy = bLegacy ? nullptr : NearestEnemyOf(Actor);
  Actor->ApplyRestFacing(Src, bLegacy, Cam, Enemy != nullptr,
                         Enemy ? Enemy->GetActorLocation() : FVector::ZeroVector,
                         Enemy ? Enemy->GetFighterId() : FString());
}

void AS08BoardActor::FighterReturnToRest(const FString& FighterId) {
  if (S08Facing::LegacyRequested()) return;
  AS08FighterActor* Actor = FindFighterActor(FighterId);
  if (!Actor || !Actor->GetFighter().IsAlive() || Actor->IsInDeathHold() || Actor->IsMoving()) return;
  const FVector Cam = LocalCameraLocation();
  AS08FighterActor* Enemy = NearestEnemyOf(Actor);
  // AN-25: the dead band never holds the return; no living enemy - straight to the camera (ВР-06).
  const double Want = Enemy
      ? S08Facing::RestYaw(Actor->GetActorLocation(), Cam, true, Enemy->GetActorLocation(), /*CurrentYawDeg=*/0.0,
                           /*bApplyDeadBand=*/false)
      : S08Facing::YawToward(Actor->GetActorLocation(), Cam);
  Actor->ReturnToRestFacing(Want, S08Facing::ReturnMs);
}

bool AS08BoardActor::AnyFighterMoving() const {
  for (const AS08FighterActor* Actor : FighterActors) {
    if (Actor && Actor->IsMoving()) return true;
  }
  return false;
}

bool AS08BoardActor::GetFighterDeathPlan(const FString& FighterId, S08HeroesV2::FDeathPlan& OutPlan,
                                         FString& OutStyle) const {
  const AS08FighterActor* Actor = FindFighterActor(FighterId);
  return Actor && Actor->GetDeathPlan(OutPlan, OutStyle);
}

FString AS08BoardActor::GetFighterClipName(const FString& FighterId, S08HeroesV2::EClip Clip) const {
  const AS08FighterActor* Actor = FindFighterActor(FighterId);
  return Actor ? Actor->GetHeroClipAssetName(Clip) : FString();
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
    // fall back to the default material), so only an ISM-capable one is used.
    if (*Authored && bOutIsmUsage) {
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
  ClearMapFrameParts();  // ENV-MAPS P5: the frame modules of a map-image board (always empty on grids)
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

void AS08BoardActor::ApplyArtLights(const FS08LightProfile& Light) {
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
  // ENV-MAPS: board-relative spots of a map-image profile scale by the map (891.333 x 577.333 uu), never by
  // the W x H lattice of the topology contract; grids keep the old placement.
  const TArray<FS08PlacedLight> Placed = bMapImageActive ? S08PlaceLights(Light, ActiveProfile.Map.SizeUU())
                                                         : S08PlaceLights(Light, BoardModel);
  bool bOk = true;
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
  // ENV-MAPS P2 night calibration: an optional ExponentialHeightFog (no volumetric fog) turns the black void
  // around the diorama into the night haze of the concepts; StartDistance keeps the board out of it. A scene
  // actor of the profile like the lights (destroyed with them), never a renderer / scalability setting.
  if (bOk && Light.Fog.bSet && !bLegacy) {
    const FS08FogSpec& F = Light.Fog;
    AExponentialHeightFog* Fog =
        GetWorld()->SpawnActor<AExponentialHeightFog>(FVector(0.0, 0.0, F.HeightZ), FRotator::ZeroRotator);
    UExponentialHeightFogComponent* FogComponent = Fog ? Fog->GetComponent() : nullptr;
    if (FogComponent) {
      FogComponent->SetFogDensity(F.Density);
      FogComponent->SetFogHeightFalloff(F.HeightFalloff);
      FogComponent->SetFogInscatteringColor(F.Color);
      FogComponent->SetStartDistance(F.StartDistanceUU);
      FogComponent->SetEndDistance(F.EndDistanceUU);
      FogComponent->SetFogMaxOpacity(F.MaxOpacity);
      FogComponent->SetVolumetricFog(false);
      ArtLights.Add(Fog);
      AppliedRender.bFog = true;
    }
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW fog profile=%s spawned=%d color=(%.4f,%.4f,%.4f) density=%g falloff=%g heightZ=%.0f start=%.0f end=%.0f maxOpacity=%.2f volumetric=0"),
        *Light.Id, FogComponent ? 1 : 0, F.Color.R, F.Color.G, F.Color.B, F.Density, F.HeightFalloff, F.HeightZ,
        F.StartDistanceUU, F.EndDistanceUU, F.MaxOpacity));
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
}

void AS08BoardActor::ApplyMapGrade(const FS08LightProfile& Light) {
  UMaterialInstanceDynamic* Mid = MapPlaneMaterial.Get();
  if (!Mid) return;
  const FS08MapGradeSpec& G = Light.MapGrade;
  if (G.bSet) {
    Mid->SetScalarParameterValue(FName(S08MapSurfaceSpec::ParamNightEV), G.NightEV);
    Mid->SetScalarParameterValue(FName(S08MapSurfaceSpec::ParamNightSaturation), G.NightSaturation);
    Mid->SetScalarParameterValue(FName(S08MapSurfaceSpec::ParamLift), G.Lift);
    if (G.bHasTint) Mid->SetVectorParameterValue(FName(S08MapSurfaceSpec::ParamNightTint), G.NightTint);
    // ENV-MAPS P4 (M_MapBoard graph v2): the mask-only zone-separation terms (identity unless the profile sets them).
    Mid->SetScalarParameterValue(FName(S08MapSurfaceSpec::ParamMaskSaturation), G.MaskSaturation);
    Mid->SetScalarParameterValue(FName(S08MapSurfaceSpec::ParamLiftSaturation), G.LiftSaturation);
    Mid->SetVectorParameterValue(FName(S08MapSurfaceSpec::ParamMaskInverseTint), G.MaskInverseTint);
  }
  // Read back what the MID renders with (the profile values, or the MI values of the import script).
  float Ev = 0.0f, Saturation = 0.0f, Lift = 0.0f;
  FLinearColor Tint = FLinearColor::White;
  Mid->GetScalarParameterValue(FHashedMaterialParameterInfo(S08MapSurfaceSpec::ParamNightEV), Ev);
  Mid->GetScalarParameterValue(FHashedMaterialParameterInfo(S08MapSurfaceSpec::ParamNightSaturation), Saturation);
  Mid->GetScalarParameterValue(FHashedMaterialParameterInfo(S08MapSurfaceSpec::ParamLift), Lift);
  Mid->GetVectorParameterValue(FHashedMaterialParameterInfo(S08MapSurfaceSpec::ParamNightTint), Tint);
  // Graph v2 parameters: a graph-v1 M_MapBoard (import not re-run) lacks them -> 'graph=v1' (the terms are inert).
  // Existence is asked of the base material (a MID keeps any value it was given, known to the graph or not).
  const UMaterial* BaseMaterial = Mid->GetMaterial();
  float Probe = 0.0f;
  FLinearColor ProbeColor = FLinearColor::White;
  const bool bGraphV2 =
      BaseMaterial &&
      BaseMaterial->GetScalarParameterValue(FHashedMaterialParameterInfo(S08MapSurfaceSpec::ParamMaskSaturation), Probe) &&
      BaseMaterial->GetScalarParameterValue(FHashedMaterialParameterInfo(S08MapSurfaceSpec::ParamLiftSaturation), Probe) &&
      BaseMaterial->GetVectorParameterValue(FHashedMaterialParameterInfo(S08MapSurfaceSpec::ParamMaskInverseTint), ProbeColor);
  float MaskSaturation = 1.0f, LiftSaturation = 1.0f;
  FLinearColor InverseTint = FLinearColor::White;
  if (bGraphV2) {
    Mid->GetScalarParameterValue(FHashedMaterialParameterInfo(S08MapSurfaceSpec::ParamMaskSaturation), MaskSaturation);
    Mid->GetScalarParameterValue(FHashedMaterialParameterInfo(S08MapSurfaceSpec::ParamLiftSaturation), LiftSaturation);
    Mid->GetVectorParameterValue(FHashedMaterialParameterInfo(S08MapSurfaceSpec::ParamMaskInverseTint), InverseTint);
  }
  FS08Trace::Write(FString::Printf(
      TEXT("ARTPREVIEW map grade profile=%s source=%s nightEV=%.2f nightSaturation=%.2f lift=%.2f nightTint=(%.4f,%.4f,%.4f) maskSaturation=%.2f liftSaturation=%.2f maskInverseTint=(%.4f,%.4f,%.4f) graph=%s maskTerms=%d"),
      *Light.Id, G.bSet ? TEXT("profile") : TEXT("mi"), Ev, Saturation, Lift, Tint.R, Tint.G, Tint.B, MaskSaturation,
      LiftSaturation, InverseTint.R, InverseTint.G, InverseTint.B, bGraphV2 ? TEXT("v2") : TEXT("v1"),
      G.bSet && G.HasMaskTerms() ? 1 : 0));
  if (G.bSet && G.HasMaskTerms() && !bGraphV2) {
    FS08Trace::Write(TEXT("ARTPREVIEW map grade mask terms ignored: M_MapBoard graph v1 (re-run tools/art/map_surface/ue_import_map_surface.py)"));
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

bool AS08BoardActor::EnsureDioramaTray(bool bArtLook) {
  if (DioramaTray) return true;
  if (!S08Diorama::Enabled(bArtLook)) return false;
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
  TrayT1Mesh = TrayMesh;  // ENV-U10: PlaceDioramaTray shows T1 again after a map-image board had T2
  TrayT1Mi = TrayMi;
  FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW diorama requested mesh=%s mi=%s"), *TrayMesh->GetPathName(),
                                   TrayMi ? *TrayMi->GetName() : TEXT("missing(mesh default)")));
  return true;
}

void AS08BoardActor::PlaceDioramaTray(bool bVisible, const FVector2D& BoardHalf, const TCHAR* Surface,
                                      const FVector2D& Offset, const TCHAR* Waiver) {
  if (!DioramaTray) return;
  if (!bVisible) {
    DioramaTray->SetVisibility(false);
    FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW diorama tray hidden surface=%s (no art board)"), Surface));
    return;
  }
  // ENV-U10: the component may still carry T2 from a map-image board - every FitTray placement is the T1 mesh.
  if (TrayT1Mesh && DioramaTray->GetStaticMesh() != TrayT1Mesh) {
    DioramaTray->SetStaticMesh(TrayT1Mesh);
    DioramaTray->SetMaterial(0, TrayT1Mi);  // nullptr = the mesh's own material, as EnsureDioramaTray without the MI
  }
  const S08Diorama::FTrayFit Fit = S08Diorama::FitTray(BoardHalf, Offset);
  DioramaTray->SetRelativeLocationAndRotation(FVector(Fit.Location.X, Fit.Location.Y, 0.0),
                                              FRotator(0.0f, Fit.YawDeg, 0.0f));
  DioramaTray->SetRelativeScale3D(Fit.Scale);
  DioramaTray->SetVisibility(true);
  const UStaticMesh* Mesh = DioramaTray->GetStaticMesh();
  const FBox Box = Mesh ? Mesh->GetBoundingBox().TransformBy(DioramaTray->GetComponentTransform()) : FBox(ForceInit);
  const UMaterialInterface* Mi = DioramaTray->GetMaterial(0);
  const FVector Size = Box.GetSize();
  // ENV-MAPS (ENV-O8 T1): the map-image surface appends offset / anisotropy / the waiver it runs under; every
  // other surface writes the 5c-B2 line unchanged.
  const FString Extra = Waiver ? FString::Printf(TEXT(" offset=(%.1f,%.1f) anisotropy=%.3f waiver=%s"), Offset.X,
                                                 Offset.Y, Fit.Anisotropy(), Waiver)
                               : FString();
  FS08Trace::Write(FString::Printf(
      TEXT("ARTPREVIEW diorama tray=%s mi=%s surface=%s yaw=%.1f scale=%.3fx%.3fx%.3f bounds=(%.1f,%.1f,%.1f)..(%.1f,%.1f,%.1f) size=%.1fx%.1fx%.1f topZ=%.1f boardHalf=%.1fx%.1f rimUU=%.1f collision=none%s"),
      Mesh ? *Mesh->GetPathName() : TEXT("-"), Mi ? *Mi->GetName() : TEXT("-"), Surface, Fit.YawDeg, Fit.Scale.X,
      Fit.Scale.Y, Fit.Scale.Z, Box.Min.X, Box.Min.Y, Box.Min.Z, Box.Max.X, Box.Max.Y, Box.Max.Z, Size.X, Size.Y,
      Size.Z, Box.Max.Z, BoardHalf.X, BoardHalf.Y, S08Diorama::RimUU, *Extra));
}

bool AS08BoardActor::PlaceDioramaTrayT2(const FVector2D& FrameHalf, const FVector2D& LayoutHalf, float OffsetY,
                                        const TCHAR* Source) {
  if (!DioramaTray) return false;
  const FString MapName = ActiveProfile.Map.Name;  // "" in a profile-less test world -> the shared MI
  if (!bTrayT2Tried) {
    // Loaded on the first map-image board only: a run that never shows a map loads nothing new. P5 track B: the
    // chunky T2b when it is in the build, else T2 (S08Diorama::LoadTrayT2), else the T1 placeholder below.
    bTrayT2Tried = true;
    const S08Diorama::FTrayT2Assets Assets = S08Diorama::LoadTrayT2(MapName);
    TrayT2Mesh = Assets.Mesh;
    TrayT2Mi = Assets.Material;
    FS08Trace::Write(S08Diorama::TrayT2LoadTraceLine(Assets));
  }
  if (!TrayT2Mesh) return false;
  // T2b: the map's MI (MI_TableBase_T2b_<Map>: Marmoreal moss + petals / Sarpedon damp rock) when imported, else the
  // shared one; T2: MI_TableBase_T2 (nullptr = the mesh's own material)
  UMaterialInterface* MapMi =
      S08Diorama::LoadTrayT2Material(S08Diorama::TrayT2KindOf(TrayT2Mesh), MapName);
  if (!MapMi) MapMi = TrayT2Mi;
  if (DioramaTray->GetStaticMesh() != TrayT2Mesh) DioramaTray->SetStaticMesh(TrayT2Mesh);
  if (DioramaTray->GetMaterial(0) != MapMi) DioramaTray->SetMaterial(0, MapMi);
  float MismatchUU = 0.0f;
  const S08Diorama::FTrayFit Fit = S08Diorama::FitTrayT2(LayoutHalf, OffsetY, MismatchUU);
  DioramaTray->SetRelativeLocationAndRotation(FVector(Fit.Location.X, Fit.Location.Y, 0.0),
                                              FRotator(0.0f, Fit.YawDeg, 0.0f));
  DioramaTray->SetRelativeScale3D(Fit.Scale);
  DioramaTray->SetVisibility(true);
  const FBox Box = TrayT2Mesh->GetBoundingBox().TransformBy(DioramaTray->GetComponentTransform());
  const UMaterialInterface* Mi = DioramaTray->GetMaterial(0);
  const FVector Size = Box.GetSize();
  const int32 bMatch = MismatchUU <= S08Diorama::T2MatchToleranceUU ? 1 : 0;
  // Same leading fields as the T1 line (topZ = the flat top, boardHalf = the map frame, rimUU = the narrowest apron
  // from the frame to the tray edge), then the T2 fields; no waiver: the mesh is placed at scale 1.
  FS08Trace::Write(FString::Printf(
      TEXT("ARTPREVIEW diorama tray=%s mi=%s surface=%s yaw=%.1f scale=%.3fx%.3fx%.3f bounds=(%.1f,%.1f,%.1f)..(%.1f,%.1f,%.1f) size=%.1fx%.1fx%.1f topZ=%.1f boardHalf=%.1fx%.1f rimUU=%.1f collision=none kind=%s topHalf=%.1fx%.1f layoutHalf=%.1fx%.1f offset=(%.1f,%.1f) source=%s mismatchUU=%.1f match=%d anisotropy=%.3f lipTopZ=%.1f lipBandUU=%.1f"),
      *TrayT2Mesh->GetPathName(), Mi ? *Mi->GetName() : TEXT("-"), S08BoardSurfaceName(ES08BoardSurface::MapImage),
      Fit.YawDeg, Fit.Scale.X, Fit.Scale.Y, Fit.Scale.Z, Box.Min.X, Box.Min.Y, Box.Min.Z, Box.Max.X, Box.Max.Y,
      Box.Max.Z, Size.X, Size.Y, Size.Z, S08Diorama::TopZ, FrameHalf.X, FrameHalf.Y,
      S08Diorama::T2MinApronUU(FrameHalf, OffsetY),
      S08Diorama::TrayT2KindName(S08Diorama::TrayT2KindOf(TrayT2Mesh)), Fit.WorldHalf.X, Fit.WorldHalf.Y, LayoutHalf.X, LayoutHalf.Y,
      Fit.Location.X, Fit.Location.Y, Source, MismatchUU, bMatch, Fit.Anisotropy(), Box.Max.Z, S08Diorama::T2RimUU));
  if (!bMatch) {
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW diorama tray-t2 mismatch layoutHalf=%.1fx%.1f t2Top=%.1fx%.1f mismatchUU=%.1f (T2 is never stretched: rebuild T2 or fix the layout tray)"),
        LayoutHalf.X, LayoutHalf.Y, S08Diorama::T2TopHalfX, S08Diorama::T2TopHalfY, MismatchUU));
  }
  return true;
}

void AS08BoardActor::UpdateDioramaTray(const FS08BoardModel& Board) {
  // ENV-MAPS track C: the environment first (it does not need the tray mesh; its layout may carry the tray extents).
  UpdateEnvLayout();
  // ENV-MAPS P5 track C: the night backdrop under the tray (same env gate; a no-op on grid-only runs).
  UpdateBackdrop();
  // ENV-MAPS P7 (ENV-U15): the concept paste after the layout it hides parts of (a no-op on grid-only runs).
  UpdateConceptPaste();
  // ENV-MAPS P8 gate G1: -ArtPreviewLightsOff - a bench frame without the engine's light (S08ConceptPaste::ApplyLightsOff)
  if (bArtActive && ConceptInputs.bLightsOff) {
    const FS08LightsOffStats Off = S08ConceptPaste::ApplyLightsOff(
        ArtLights, EnvLights, ConceptLights, EnvProps, EnvRuntime, ConceptParts,
        IsConceptPasteOn() && ConceptMode.Kind == ES08ConceptKind::Lit3d, GetWorld(), ConceptAssets.SceneCollection,
        ActiveProfile.Id);
    if (Off.bFogHidden) AppliedRender.bFog = false;
  }
  if (!DioramaTray) return;
  if (!bArtActive) {
    PlaceDioramaTray(false, FVector2D::ZeroVector, TEXT("grey"));
    return;
  }
  if (bMapImageActive) {
    // ENV-U10 track TRAY: the shared rocky tray T2 (S08Diorama.h) at scale 1 - no stretch, no waiver - centred on the
    // applied env layout's tray (S08EnvLayout::ApplyTrayT2: its "tray" / apron, traced 'ARTPREVIEW envlayout tray
    // ... mesh=T2'), else on the shared default (-ArtPreviewNoEnv, no / invalid layout).
    const FVector2D Frame = ActiveProfile.Map.FrameHalfUU();
    FVector2D LayoutHalf(S08Diorama::T2TopHalfX, S08Diorama::T2TopHalfY);
    float OffsetY = S08Diorama::T2DefaultOffsetY;
    FString Source = TEXT("default");
    S08EnvLayout::ApplyTrayT2(EnvRuntime, Frame, LayoutHalf, OffsetY, Source);
    if (PlaceDioramaTrayT2(Frame, LayoutHalf, OffsetY, *Source)) {
      HideTrayForConceptPaste();  // ENV-MAPS P7: the painted island replaces the tray in concept mode
      return;
    }
    // T2 not in the build: the ENV-O8 T1 placeholder (explicit waiver, S08Diorama.h) - the Cobble-sized SM_TableBase
    // stretched non-uniformly around the map + wooden frame (or the layout's outer tray, S08EnvLayout::ApplyTray);
    // the <= 5 % non-uniformity rule of the tray is waived for this fallback only, and the trace line says so.
    FVector2D TrayHalf = Frame;
    FVector2D TrayOffset = ActiveProfile.Map.TrayOffsetUU;
    S08EnvLayout::ApplyTray(EnvRuntime, Frame, TrayHalf, TrayOffset);
    PlaceDioramaTray(true, TrayHalf, S08BoardSurfaceName(ES08BoardSurface::MapImage), TrayOffset,
                     S08MapSurfaceSpec::TrayWaiver);
    HideTrayForConceptPaste();
    return;
  }
  const FVector2D Half =
      S08Diorama::TilesFrameHalf(Board.Width, Board.Height, FS08BoardModel::CellSizeUU, ArtFrameUU);
  PlaceDioramaTray(true, Half, S08BoardSurfaceName(ActiveProfile.Surface));
}

bool AS08BoardActor::EnsureEnvLayout(bool bArtLook) {
  bEnvLayoutEnabled = S08EnvLayout::Arm(bArtLook);
  return bEnvLayoutEnabled;
}

void AS08BoardActor::UpdateEnvLayout() {
  // ENV-MAPS P7: the concept-paste mode first - it picks the env-layout variant (the concept overlay, or the base).
  ResolveConceptPasteMode();
  ApplyEnvLayout();
}

void AS08BoardActor::ApplyEnvLayout() {
  // Without the gate nothing was ever created: a grid board (and every -S08DioramaLegacy / -S08GreyBoard run) is untouched.
  if (!bEnvLayoutEnabled && !EnvRuntime.bApplied && EnvProps.IsEmpty() && EnvLights.IsEmpty()) return;
  FS08EnvLayoutRequest Request;
  Request.bEnabled = bEnvLayoutEnabled;
  Request.bMapImageActive = bMapImageActive;  // false on every grid board and on a refused map profile
  Request.ProfileId = ActiveProfile.Id;
  Request.MapKey = S08EnvLayout::MapKeyOf(ActiveProfile.Map.Name);
  Request.RoomBoardId = RoomBoardId;
  Request.ProfileBoardIds = ActiveProfile.MatchBoardIds;
  Request.MapHalf = ActiveProfile.Map.HalfUU();
  Request.FrameHalf = ActiveProfile.Map.FrameHalfUU();
  Request.ProfileTrayOffset = ActiveProfile.Map.TrayOffsetUU;
  const FS08LightProfile* Light = bMapImageActive ? ArtData.LightFor(ActiveProfile) : nullptr;
  Request.ProfilePointLights = Light ? Light->Points.Num() : 0;
  // live tune only (unset in every other run: the command line decides, as before)
  Request.Dir = EnvDirOverride;
  if (FxOptionsOverride.IsSet()) Request.FxOptions = FxOptionsOverride;
  // ENV-MAPS P7: a block on the active profile decides the variant (unset = the command line, as before: Marmoreal's
  // default and every board without the block stay byte for byte).
  if (ConceptMode.bOverrideVariant) Request.Variant = ConceptMode.Variant;
  S08EnvLayout::Update(Request, *this, RootComponent, EnvRuntime, EnvProps, EnvLights);
  // The concept overlay must have applied; else the env layout fell back to the base (the P5c composition): keep it
  // (decided here, before the backdrop and the paste read the mode).
  if (ConceptMode.bOn && EnvRuntime.bLayoutValid && EnvRuntime.Variant.Status != TEXT("ok")) {
    ConceptMode = S08ConceptPaste::FallbackOff(
        ActiveProfile.ConceptPaste, ConceptInputs,
        EnvRuntime.Variant.Status == TEXT("absent") ? TEXT("overlay-absent") : TEXT("overlay-invalid"));
  }
}

void AS08BoardActor::ResolveConceptPasteMode() {
  const FS08ConceptPasteSpec& Spec = ActiveProfile.ConceptPaste;
  ConceptInputs = FS08ConceptPasteInputs::FromCommandLine();
  const bool bGate = bEnvLayoutEnabled && bArtActive && bMapImageActive;
  ConceptMode = S08ConceptPaste::ResolveMode(Spec, ConceptInputs, bGate);
  if (!ConceptMode.bOn) return;
  // ENV-MAPS P8: per profile and kind (paste / lit3d load different packages)
  const FString AssetsKey = ActiveProfile.Id + TEXT("|") + S08ConceptKindName(ConceptMode.Kind);
  if (ConceptAssetsProfileId != AssetsKey) {
    // once per profile: the out-of-git imports (ue_import_concept_paste.py, ue_concept_material.py; lit3d:
    // tools/art/concept_scene/ue_scene_material.py, ue_import_concept_scene.py) are there or not
    ConceptAssets = S08ConceptPaste::LoadAssets(Spec, ConceptMode.Kind);
    ConceptAssetsProfileId = AssetsKey;
    ConceptApplyFailedProfileId.Reset();
    ConceptAssetRefs.Reset();
    for (UObject* Asset : ConceptAssets.AllLoaded()) ConceptAssetRefs.Add(Asset);
    for (const FString& Path : ConceptAssets.Missing) {
      const FString Line = S08ConceptPaste::MissingLine(Path);
      UE_LOG(LogTemp, Display, TEXT("%s"), *Line);  // Display: the trace line is the contract (tests collect warnings)
      FS08Trace::Write(Line);
    }
  }
  if (!ConceptAssets.RequiredOk()) {
    // P5c stays: no paste, no hides, and no concept overlay (its props are removed for the painted surround)
    ConceptMode = S08ConceptPaste::FallbackOff(Spec, ConceptInputs, TEXT("missing-assets"));
  } else if (ConceptApplyFailedProfileId == AssetsKey) {
    // P7c: Apply failed on this profile before (FallBackAfterApplyFailure): straight to the P5c look, no flip-flop of the
    // env layout on every rebuild
    ConceptMode = S08ConceptPaste::FallbackOff(Spec, ConceptInputs, TEXT("apply-failed"));
  }
}

FString AS08BoardActor::ConceptPasteKey() const {
  return FString::Printf(TEXT("%s|%d|%s|%s|%s|calib=%d"), *ActiveProfile.Id, ConceptMode.bOn ? 1 : 0, *ConceptMode.Reason,
                         S08ConceptKindName(ConceptMode.Kind), *EnvRuntime.Key, ConceptInputs.bCalib ? 1 : 0);
}

void AS08BoardActor::FallBackAfterApplyFailure() {
  // ENV-MAPS P7c: the assets loaded but Apply did not end 'ok'. The concept overlay is already applied (it removed the
  // 54 painted-over P5c props) and the backdrop went with the mode: re-run the env layout WITHOUT the overlay (the P5c
  // composition), bring the backdrop back; tray / fog / layout lights were never hidden (ApplyHides runs after an ok).
  const FS08ConceptPasteSpec& Spec = ActiveProfile.ConceptPaste;
  const FString Failed = ConceptRuntime.Status;
  ConceptApplyFailedProfileId = ActiveProfile.Id + TEXT("|") + S08ConceptKindName(ConceptMode.Kind);
  S08ConceptPaste::Clear(ConceptParts, ConceptLights, ConceptRuntime);
  S08ConceptPaste::RestoreHides(ConceptRuntime);
  ConceptMode = S08ConceptPaste::FallbackOff(Spec, ConceptInputs, TEXT("apply-failed"));
  ApplyEnvLayout();
  UpdateBackdrop();
  ConceptRuntime.Mode = ConceptMode;
  ConceptRuntime.Key = ConceptPasteKey();
  ConceptRuntime.bTraced = true;
  FS08Trace::Write(FString::Printf(
      TEXT("ARTPREVIEW concept-paste mode=off profile=%s map=%s reason=apply-failed status=%s fallback=base envVariant=%s:%s props=%d lights=%d backdrop=%s"),
      *ActiveProfile.Id, *S08EnvLayout::MapKeyOf(ActiveProfile.Map.Name), *Failed,
      EnvRuntime.Variant.Name.IsEmpty() ? TEXT("none") : *EnvRuntime.Variant.Name,
      EnvRuntime.Variant.Status.IsEmpty() ? TEXT("-") : *EnvRuntime.Variant.Status, EnvProps.Num(), EnvLights.Num(),
      BackdropRuntime.Status.IsEmpty() ? TEXT("-") : *BackdropRuntime.Status));
}

void AS08BoardActor::UpdateConceptPaste() {
  const FS08ConceptPasteSpec& Spec = ActiveProfile.ConceptPaste;
  UExponentialHeightFogComponent* Fog = nullptr;
  for (AActor* Actor : ArtLights) {
    if (const AExponentialHeightFog* FogActor = Cast<AExponentialHeightFog>(Actor)) Fog = FogActor->GetComponent();
  }
  const FString MapKey = S08EnvLayout::MapKeyOf(ActiveProfile.Map.Name);
  const FString Key = ConceptPasteKey();
  auto StopAnim = [this]() {
    if (ConceptAnim) {
      ConceptAnim->RestoreBase();
      ConceptAnim->DestroyComponent();
      ConceptAnim = nullptr;
    }
  };
  if (!ConceptMode.bOn) {
    // A grid-only run (or a board without the block) that never applied anything writes nothing (grids bit for bit).
    const bool bNothing = !ConceptRuntime.bTraced && ConceptParts.IsEmpty() && ConceptLights.IsEmpty() &&
                          ConceptRuntime.Hidden.IsEmpty();
    if (bNothing && (!Spec.bSet || !bMapImageActive)) return;
    if (ConceptRuntime.Key == Key) return;
    StopAnim();
    const int32 Restored = S08ConceptPaste::RestoreHides(ConceptRuntime);
    const int32 Cleared = ConceptParts.Num() + ConceptLights.Num();
    S08ConceptPaste::Clear(ConceptParts, ConceptLights, ConceptRuntime);
    if (Fog) AppliedRender.bFog = Fog->IsVisible();
    ConceptRuntime.Key = Key;
    ConceptRuntime.ProfileId = ActiveProfile.Id;
    ConceptRuntime.Mode = ConceptMode;
    ConceptRuntime.bTraced = true;
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW concept-paste mode=off profile=%s map=%s reason=%s default=%s flag=%s cmdVariant=%s envVariant=%s:%s cleared=%d restored=%d"),
        ActiveProfile.Id.IsEmpty() ? TEXT("-") : *ActiveProfile.Id, MapKey.IsEmpty() ? TEXT("-") : *MapKey,
        *ConceptMode.Reason, !Spec.bSet ? TEXT("-") : (Spec.bDefaultOn ? TEXT("on") : TEXT("off")),
        ConceptInputs.FlagText.IsEmpty() ? TEXT("-") : *ConceptInputs.FlagText,
        ConceptInputs.Variant.IsEmpty() ? TEXT("-") : *ConceptInputs.Variant,
        EnvRuntime.Variant.Name.IsEmpty() ? TEXT("none") : *EnvRuntime.Variant.Name,
        EnvRuntime.Variant.Status.IsEmpty() ? TEXT("-") : *EnvRuntime.Variant.Status, Cleared, Restored));
    return;
  }
  if (ConceptRuntime.Key == Key && ConceptRuntime.Status == TEXT("ok")) return;  // the same board and layout again
  StopAnim();
  S08ConceptPaste::RestoreHides(ConceptRuntime);  // the previous board's hides (its components may be gone)
  ConceptRuntime.Key = Key;
  ConceptRuntime.ProfileId = ActiveProfile.Id;
  ConceptRuntime.Mode = ConceptMode;
  const ES08ConceptKind Kind = ConceptMode.Kind;
  const bool bLit3d = Kind == ES08ConceptKind::Lit3d;
  const FS08ConceptHide& Hide = Spec.HideFor(Kind);
  FS08Trace::Write(FString::Printf(
      TEXT("ARTPREVIEW concept-paste mode=on profile=%s map=%s reason=%s default=%s flag=%s cmdVariant=%s envVariant=%s:%s overlay=%s overlaySha256=%s spec=%s manifest=%s hide=%s kind=%s"),
      *ActiveProfile.Id, *MapKey, *ConceptMode.Reason, Spec.bDefaultOn ? TEXT("on") : TEXT("off"),
      ConceptInputs.FlagText.IsEmpty() ? TEXT("-") : *ConceptInputs.FlagText,
      ConceptInputs.Variant.IsEmpty() ? TEXT("-") : *ConceptInputs.Variant,
      EnvRuntime.Variant.Name.IsEmpty() ? TEXT("none") : *EnvRuntime.Variant.Name,
      EnvRuntime.Variant.Status.IsEmpty() ? TEXT("-") : *EnvRuntime.Variant.Status,
      EnvRuntime.Layout.OverlayPath.IsEmpty() ? TEXT("-") : *FPaths::GetCleanFilename(EnvRuntime.Layout.OverlayPath),
      EnvRuntime.Layout.OverlaySha256.IsEmpty() ? TEXT("-") : *EnvRuntime.Layout.OverlaySha256,
      Spec.SpecPath.IsEmpty() ? TEXT("-") : *Spec.SpecPath,
      bLit3d ? (Spec.Lit3d.ManifestPath.IsEmpty() ? TEXT("-") : *Spec.Lit3d.ManifestPath)
             : (Spec.ManifestPath.IsEmpty() ? TEXT("-") : *Spec.ManifestPath),
      *Hide.Names(), S08ConceptKindName(Kind)));
  const ES08ConceptGrade Grade = S08ConceptPaste::EffectiveGrade(Spec, ConceptAssets.Lut != nullptr);
  if (Grade != Spec.Grade) {
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW concept-paste grade=%s requested=%s lut=%s (approximate inverse ACES until the bench LUT is imported)"),
        S08ConceptGradeName(Grade), S08ConceptGradeName(Spec.Grade), Spec.LutPath.IsEmpty() ? TEXT("-") : *Spec.LutPath));
  }
  const FS08LightProfile* Light = ArtData.LightFor(ActiveProfile);
  const float EmissiveScale = S08ConceptPaste::EffectiveEmissiveScale(
      Spec, Light && Light->Exposure.bSet, Light ? Light->Exposure.MaxBrightness : 0.0f, ConceptRuntime.EmissiveScaleSource);
  // frozen runs (-Bench without -EnvFxLive, -EnvFxFreeze): no light flicker / prop sway / water flow - reproducible frames
  const FS08EnvFxOptions FxOptions = GetFxOptions();
  if (bLit3d) {
    // ENV-MAPS P8: the lit 3D island is the env layout's scene overlay; the block adds the sky, the lights, the tweaks
    S08ConceptPaste::ApplyLit3d(Spec, ConceptAssets, ActiveProfile.Map.FrameHalfUU(), Grade, EmissiveScale, FxOptions.bFreeze,
                                *this, RootComponent, ConceptParts, ConceptLights, ConceptRuntime);
  } else {
    S08ConceptPaste::Apply(Spec, ConceptAssets, ActiveProfile.Map.FrameHalfUU(), Grade, EmissiveScale, ConceptInputs.bCalib,
                           FxOptions.bFreeze, *this, RootComponent, ConceptParts, ConceptLights, ConceptRuntime);
  }
  if (ConceptRuntime.Status != TEXT("ok")) {
    FallBackAfterApplyFailure();  // P7c: the full P5c look, never a board without props and without the paste
    return;
  }
  // the painted surround replaces the env props / fx / lights / ground parts of the hide list and the fog (the backdrop
  // went with UpdateBackdrop, the tray goes with HideTrayForConceptPaste)
  S08ConceptPaste::ApplyHides(Hide, EnvRuntime, EnvProps, EnvLights, Fog, ConceptRuntime);
  if (ConceptRuntime.bHidFog) AppliedRender.bFog = false;
  ConceptRuntime.bHidBackdrop = Hide.bBackdrop && ActiveProfile.Backdrop.bSet;
  FS08Trace::Write(FString::Printf(
      TEXT("ARTPREVIEW concept-paste hide profile=%s props=%d fx=%d layoutLights=%d ground=%d sea=%d waterfalls=%d fog=%d backdrop=%d overlayProps=%d overlayFx=%d"),
      *ActiveProfile.Id, ConceptRuntime.HiddenProps, ConceptRuntime.HiddenFx, ConceptRuntime.HiddenLights,
      ConceptRuntime.HiddenGround, ConceptRuntime.HiddenSea, ConceptRuntime.HiddenWaterfalls, ConceptRuntime.bHidFog ? 1 : 0,
      ConceptRuntime.bHidBackdrop ? 1 : 0, EnvRuntime.Layout.OverlayPropIds.Num(), EnvRuntime.Layout.OverlayFxIds.Num()));
  if (bLit3d) {
    // shadows / Lumen GI of the island masses, the sea ring under the cliffs (R3); the MPC: wind / flicker live only
    S08ConceptPaste::ApplyScene(Spec.Lit3d, EnvRuntime, EnvProps, ConceptRuntime);
    const bool bLive = !FxOptions.bFreeze;
    const bool bCollection =
        S08ConceptPaste::SetSceneCollection(GetWorld(), ConceptAssets.SceneCollection, bLive, !ConceptInputs.bLightsOff);
    ConceptRuntime.SceneCollection = !ConceptAssets.SceneCollection ? FString(TEXT("missing"))
                                     : !bCollection                 ? FString(TEXT("failed"))
                                                                    : FString(bLive ? TEXT("live") : TEXT("still")) +
                                                                          (ConceptInputs.bLightsOff ? TEXT(",emissive-off") : TEXT(""));
    FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW concept-scene collection=%s path=%s"), *ConceptRuntime.SceneCollection,
                                     S08ConceptPasteSpec::SceneCollectionPath));
    // Art Tuner M4: "materialOverrides" (absent: nothing is created)
    ApplyMaterialOverrides();
  }
  // light budget: 1 key + profile points + this block's lights + the env lights still visible <= 6 points
  int32 VisibleLayoutLights = 0;
  for (const UPointLightComponent* L : EnvLights) VisibleLayoutLights += L && L->IsVisible() ? 1 : 0;
  const int32 ProfilePoints = Light ? Light->Points.Num() : 0;
  const int32 Combined = ProfilePoints + ConceptLights.Num() + VisibleLayoutLights;
  FS08Trace::Write(FString::Printf(
      TEXT("ARTPREVIEW concept-paste budget profile=%s profilePoints=%d conceptLights=%d layoutLightsVisible=%d combinedPoints=%d combinedBudgetOk=%d"),
      *ActiveProfile.Id, ProfilePoints, ConceptLights.Num(), VisibleLayoutLights, Combined,
      Combined <= S08ConceptPasteSpec::CombinedPointBudget ? 1 : 0));
  // animation: flicker of the block's lights, sway of named props; frozen runs keep the base
  ConceptRuntime.bAnimFrozen = FxOptions.bFreeze;
  int32 Flickers = 0, Sways = 0, MissingTargets = 0;
  TArray<USceneComponent*> SwayTargets;
  const TArray<FS08ConceptAnim>& AnimSpecs = Spec.AnimsFor(Kind);
  const TArray<FS08ConceptLight>& LightSpecs = Spec.LightsFor(Kind);
  for (const FS08ConceptAnim& Anim : AnimSpecs) {
    const int32 Index = EnvRuntime.Stats.PropComponentIds.IndexOfByKey(Anim.Prop);
    USceneComponent* Target = Index != INDEX_NONE && EnvProps.IsValidIndex(Index) ? EnvProps[Index].Get() : nullptr;
    SwayTargets.Add(Target);
    if (!Target) {
      ++MissingTargets;
      FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW concept-paste anim prop=%s missing (not a spawned env-layout prop)"),
                                       *Anim.Prop));
    }
  }
  // P7c: the material wind of the "winds" props (the banner cloth): live runs only; frozen ones keep the still MI default
  // (P8 lit3d: ids or "prefix*" patterns)
  TArray<UStaticMeshComponent*> WindTargets;
  TArray<FString> MissingWinds;
  for (const int32 Index : S08ConceptPaste::MatchProps(Spec.WindsFor(Kind), EnvRuntime.Stats.PropComponentIds, &MissingWinds)) {
    if (UStaticMeshComponent* Target = EnvProps.IsValidIndex(Index) ? EnvProps[Index].Get() : nullptr) WindTargets.Add(Target);
  }
  for (const FString& Prop : MissingWinds) {
    ++MissingTargets;
    FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW concept-paste wind prop=%s missing (not a spawned env-layout prop)"), *Prop));
  }
  int32 Winds = 0;
  if (!FxOptions.bFreeze) {
    US08ConceptPasteAnimComponent* Anim = NewObject<US08ConceptPasteAnimComponent>(
        this, MakeUniqueObjectName(this, US08ConceptPasteAnimComponent::StaticClass(), TEXT("ConceptPasteAnim")));
    // P8 gate G1: no flicker over the zeroed lights of -ArtPreviewLightsOff
    for (int32 I = 0; !ConceptInputs.bLightsOff && I < LightSpecs.Num() && I < ConceptLights.Num(); ++I) {
      Anim->AddFlicker(ConceptLights[I], LightSpecs[I]);
    }
    Flickers = Anim->Num();
    for (int32 I = 0; I < AnimSpecs.Num(); ++I) Anim->AddSway(SwayTargets[I], AnimSpecs[I]);
    Sways = Anim->Num() - Flickers;
    for (UStaticMeshComponent* Target : WindTargets) Anim->AddWind(Target);
    Winds = Anim->NumWinds();
    if (Anim->Num() > 0) {
      Anim->RegisterComponent();
      ConceptAnim = Anim;
    } else {
      Anim->MarkAsGarbage();
    }
  }
  ConceptRuntime.Anims = Flickers + Sways + Winds;
  FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW concept-paste anim profile=%s mode=%s flickers=%d sways=%d winds=%d/%d missingProps=%d"),
                                   *ActiveProfile.Id, FxOptions.bFreeze ? TEXT("frozen") : TEXT("live"), Flickers, Sways,
                                   Winds, WindTargets.Num(), MissingTargets));
}

void AS08BoardActor::HideTrayForConceptPaste() {
  ConceptRuntime.bHidTray = false;
  if (!DioramaTray || !IsConceptPasteOn() || !ActiveProfile.ConceptPaste.HideFor(ConceptMode.Kind).bTray) return;
  DioramaTray->SetVisibility(false);
  ConceptRuntime.bHidTray = true;
  FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW concept-paste tray hidden profile=%s mesh=%s (the painted island replaces it)"),
                                   *ActiveProfile.Id,
                                   DioramaTray->GetStaticMesh() ? *DioramaTray->GetStaticMesh()->GetName() : TEXT("-")));
}

bool AS08BoardActor::Rebuild(const FS08BoardModel& Board) {
  if (Board.Width <= 0 || Board.Height <= 0) return false;
  // live tune (ReloadArtData / RequestFullRebuild): the same geometry is rebuilt in full, exactly like the first build
  const bool bForced = bForceRebuild;
  bForceRebuild = false;
  if (!bForced && BoardModel.Width == Board.Width && BoardModel.Height == Board.Height &&
      BoardModel.Cells.Num() == Board.Cells.Num() && BuiltForBoardId == RoomBoardId &&
      BoardModel.bHasTopology == Board.bHasTopology) {
    bool bSameTypes = true;
    for (int32 i = 0; i < BoardModel.Cells.Num(); ++i) {
      if (BoardModel.Cells[i].Type != Board.Cells[i].Type ||
          BoardModel.Cells[i].bIsOpen != Board.Cells[i].bIsOpen ||
          BoardModel.Cells[i].Zones != Board.Cells[i].Zones ||
          // ENV-MAPS: the space graph and the layout are geometry too (always equal on grids)
          BoardModel.Cells[i].Links != Board.Cells[i].Links ||
          BoardModel.Cells[i].bHasLayout != Board.Cells[i].bHasLayout ||
          BoardModel.Cells[i].Layout != Board.Cells[i].Layout) {
        bSameTypes = false;
        break;
      }
    }
    if (bSameTypes) return true; // geometry unchanged: tiles stay as-is
  }
  ++BuildCount;
  BoardModel = Board;
  BuiltForBoardId = RoomBoardId;
  const FS08BoardSummary Summary = S08SummarizeBoard(Board);
  bTopologyBoard = Board.bHasTopology;

  // T3.2 profile selection: board row id, else W x H + exact zone-key set.
  bArtActive = false;
  bArtTiles = false;
  bMapImageActive = false;
  ActiveProfile = FS08BoardArtProfile();
  if (bArtAssetsReady) {
    ES08ProfileMatch Match = ES08ProfileMatch::None;
    const FS08BoardArtProfile* Profile = ArtData.Select(Board, RoomBoardId, Match);
    if (!Profile) {
      FS08Trace::Write(FString::Printf(
          TEXT("ARTPREVIEW board profile=none match=none board=%dx%d boardId=%s zoneKeys=%s; keeping grey board"),
          Board.Width, Board.Height, RoomBoardId.IsEmpty() ? TEXT("-") : *RoomBoardId,
          *FString::Join(Summary.ZoneKeys, TEXT("+"))));
    } else if (Profile->Surface == ES08BoardSurface::MapImage || Board.bHasTopology) {
      // ENV-MAPS track S: a topology board only ever gets the map-image surface (lattice tiles would sit on
      // the lattice while the figures stand on the layout), and a map-image profile needs a topology board
      // whose layout frame is the one the game mode's CellToWorld uses. Missing map assets (a checkout
      // without tools/art/map_surface/ue_import_map_surface.py) -> the grey topology view, traced.
      FString Refused;
      if (Profile->Surface != ES08BoardSurface::MapImage) {
        Refused = FString::Printf(TEXT("surface %s on a topology board"), S08BoardSurfaceName(Profile->Surface));
      } else if (!Board.bHasTopology) {
        Refused = TEXT("map-image needs a topology board (cells with links)");
      } else if (!Profile->Map.MatchesLayoutFrame(Board.LayoutFrame)) {
        // The board model's own frame (defaults, or FS08BoardModel::SetLayoutFrame on the game mode's model):
        // CellToWorld / WorldToCell use it, so the map plane must match it, not the static defaults.
        Refused = FString::Printf(TEXT("map frame %dx%d@%.7f != layout frame %.0fx%.0f@%.7f"),
                                  Profile->Map.SrcSizePx.X, Profile->Map.SrcSizePx.Y, Profile->Map.UuPerPx,
                                  Board.LayoutFrame.SrcSize.X, Board.LayoutFrame.SrcSize.Y,
                                  Board.LayoutFrame.UuPerPx);
      } else if (!LoadMapImageAssets(Profile->Map)) {
        Refused = FString::Printf(TEXT("map-image assets missing=%d (run tools/art/map_surface/ue_import_map_surface.py)"),
                                  MapImageMissing.Num());
      }
      if (!Refused.IsEmpty()) {
        // Display, not Warning: the S08 trace line below is the contract, and the automation fallback test
        // (Unmatched.S08.BoardArt.MapActor) must not collect log warnings.
        UE_LOG(LogTemp, Display, TEXT("ARTPREVIEW board profile=%s refused: %s; grey topology view"), *Profile->Id,
               *Refused);
        FS08Trace::Write(FString::Printf(
            TEXT("ARTPREVIEW board profile=%s match=%s board=%dx%d boardId=%s surface=%s refused=%s; keeping grey %s"),
            *Profile->Id, S08ProfileMatchName(Match), Board.Width, Board.Height,
            RoomBoardId.IsEmpty() ? TEXT("-") : *RoomBoardId, S08BoardSurfaceName(Profile->Surface), *Refused,
            Board.bHasTopology ? TEXT("topology view") : TEXT("board")));
      } else {
        ActiveProfile = *Profile;
        bArtActive = true;
        bMapImageActive = true;
        FS08Trace::Write(FString::Printf(
            TEXT("ARTPREVIEW board profile=%s match=%s board=%dx%d boardId=%s surface=%s light=%s artFixture=%d map=%s"),
            *ActiveProfile.Id, S08ProfileMatchName(Match), Board.Width, Board.Height,
            RoomBoardId.IsEmpty() ? TEXT("-") : *RoomBoardId, S08BoardSurfaceName(ActiveProfile.Surface),
            *ActiveProfile.LightId, ActiveProfile.bArtFixture ? 1 : 0, *ActiveProfile.Map.Name));
      }
    } else {
      const ES08BoardSurface Surface = Profile->Surface;
      if (!bTileArtReady) {
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
    ApplyArtLights(*Light);
    if (bMapImageActive) ApplyMapGrade(*Light);
  }
  // ENV-MAPS P9: a profile change re-rigs the fighters already on the board (SyncFighters does it for new ones)
  if (FighterActors.Num() > 0) UpdateHeroLights();
  // ENV-MAPS: the map-image surface draws no zone marks (the zones are the painted ones); on grids this is
  // bArtActive as before.
  const bool bZoneMarks = bArtActive && !bMapImageActive;
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
      Key.Value->SetVisibility(bZoneMarks);
    }
  }
  for (TPair<FString, TObjectPtr<UInstancedStaticMeshComponent>>& Stroke : ArtZoneStrokes) {
    if (Stroke.Value) {
      Stroke.Value->ClearInstances();
      Stroke.Value->SetVisibility(bZoneMarks);
    }
  }
  for (TPair<FString, TObjectPtr<UInstancedStaticMeshComponent>>& Glyph : ArtZoneGlyphMeshes) {
    if (Glyph.Value) {
      Glyph.Value->ClearInstances();
      Glyph.Value->SetVisibility(bZoneMarks);
    }
  }
  ApplySurfaceMaterials();
  // A topology board draws no lattice at all: the lattice ISMs get no instances, so their QueryOnly collision
  // never catches a cursor trace (the invisible map pick box does, see BuildGreyTopology / BuildMapImageSurface).
  NormalTiles->SetVisibility(!bArtActive && !bTopologyBoard);
  BlockerTiles->SetVisibility(!bArtActive && !bTopologyBoard);
  UnderlayTiles->SetVisibility(!bTopologyBoard);
  ArtCorners->SetVisibility(bArtActive);
  ArtZoneGlyphs->SetVisibility(bZoneMarks);
  const bool bKeylines = bZoneMarks && ArtData.Keyline.bSet && ArtKeylineMaterial && !S08LegacyRender();
  ArtZoneKeylines->SetVisibility(bKeylines);
  if (bTopologyBoard) {
    if (bMapImageActive) {
      BuildMapImageSurface(Board, Summary);
    } else {
      BuildGreyTopology(Board);
    }
    UpdateDioramaTray(Board);
    ClearChildren();
    BuildMoveHighlight();  // MS-T-08: the plates of the map's spaces
    return true;
  }
  HideTopologyComponents();  // a grid after a topology board: the map plane / discs / pick box go away
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
  // MS-T-08: the move plates get one instance per space of the new board (and the style of its profile)
  BuildMoveHighlight();
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
      Actor->ApplyFighter(Fighter, Board.CellToWorld(Fighter.X, Fighter.Y), bOwn, bArtActive,
                          Board.bHasTopology);
      Actor->SetSelected(Fighter.Id == SelectedFighterId);
      Actor->SetCombatMarkers(Fighter.Id == CombatAttackerId,
                              Fighter.Id == CombatTargetId);
      Actor->SetLabelMode(LabelPlateFighterId.IsEmpty() ? ES08FighterLabelMode::Full
                          : Fighter.Id == LabelPlateFighterId ? ES08FighterLabelMode::Hidden
                                                              : ES08FighterLabelMode::Compact);
      // ENV-MAPS P4: contact-shadow blob + leader pip (map-image boards with a readability block only).
      ApplyFighterReadability(Actor, Fighter, S08TeamLook(Team, bOwn, TeamColorMode));
      // AN-23 (ВР-06): the rest facing - three-quarter to the camera, offset to the nearest living enemy (the actor
      // upgrades its first apply to src=spawn; -S08FacingLegacy keeps the half-field rule at once).
      ApplyFighterRestFacing(Actor, TEXT("snapshot"));
    }
  }
  // ENV-MAPS P9: the per-figure hero light of the active light profile (channel 1, figures only), within the board budget
  UpdateHeroLights();
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
  // Wave 5c-B: one summary per change of the v2 roster (default since ART-DEFAULT; none with -S08HeroesLegacy).
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
                                            int32 SequenceNumber, float PlayRate) {
  if (!bArtActive || !S08HeroesV2::FlagEnabled()) return;
  AS08FighterActor* Actor = FindFighterActor(FighterId);
  if (!Actor || !Actor->IsHeroV2()) return;
  if (!AnimEventDedupe.Accept(FString(S08HeroesV2::EventName(Event)) + TEXT(":") + FighterId, SequenceNumber)) {
    return;
  }
  Actor->NotifyHeroAnimEvent(Event, SequenceNumber, PlayRate);
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
  // MS-T-08: the plates replace the spawned highlight actors (MS-R-49: instance data only)
  if (UsesMovePlates()) {
    ApplyMovePlates(FighterId, ReachableCells);
    return;
  }
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
  // ENV-MAPS P4: the map-image readability ring (nullptr on grids / without the profile block: the old rings).
  const FS08BoardReadabilitySpec* ReachSpec = GetActiveReadability();
  for (const uint64 Key : ReachableCells) {
    const int32 X = static_cast<int32>(Key >> 32);
    const int32 Y = static_cast<int32>(Key & 0xFFFFFFFF);
    const bool bOwnCell = Selected && Selected->X == X && Selected->Y == Y;
    // The authored ring already marks the selected unit; avoid covering its
    // sculpt and name with a second cell overlay in the art review.
    if (bArtActive && bOwnCell) continue;
    // ENV-MAPS: only map spaces of a topology board carry a highlight (every cell of a grid).
    if (!BoardModel.IsBoardSpace(X, Y)) continue;
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
    // ENV-MAPS: a highlight piece with its own mesh and rotation (ring pieces, discs of a topology board).
    auto AddHighlightMesh = [&](UStaticMesh* PieceMesh, const FTransform& Relative) {
      UStaticMeshComponent* Mesh = NewObject<UStaticMeshComponent>(Tile);
      Mesh->SetupAttachment(Root);
      Mesh->SetStaticMesh(PieceMesh);
      Mesh->SetRelativeTransform(Relative);
      Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
      if (Mid) Mesh->SetMaterial(0, Mid);
      S08ApplyGameLayerPrimitive(Mesh);
      Mesh->RegisterComponent();
    };
    if (bTopologyBoard) {
      if (bArtActive && ReachSpec && ReachSpec->bReach) {
        // ENV-MAPS P4 readability: a ring in a colour outside the zone palette with a thin dark outer stroke, many
        // segments; fill and stroke are one ISM each per space (not 2 x Segments components).
        TArray<FTransform> Fill, Stroke;
        S08ReachRingPieces(*ReachSpec, Fill, Stroke);
        auto AddRing = [&](const TCHAR* Name, const TArray<FTransform>& Pieces, const FColor& Srgb) {
          if (Pieces.Num() == 0) return;
          UInstancedStaticMeshComponent* Ism = NewObject<UInstancedStaticMeshComponent>(Tile, FName(Name));
          Ism->SetupAttachment(Root);
          Ism->SetStaticMesh(BlockerTiles->GetStaticMesh());
          Ism->SetCollisionEnabled(ECollisionEnabled::NoCollision);
          if (Solid) {
            UMaterialInstanceDynamic* RingMid = UMaterialInstanceDynamic::Create(Solid, Tile);
            RingMid->SetVectorParameterValue(TEXT("Tint"), FLinearColor(Srgb));  // sRGB bytes -> linear (trap 9)
            Ism->SetMaterial(0, RingMid);
          }
          S08ApplyGameLayerPrimitive(Ism);
          Ism->RegisterComponent();
          for (const FTransform& Piece : Pieces) Ism->AddInstance(Piece, false);  // relative to the space centre
        };
        AddRing(TEXT("ReachStroke"), Stroke, ReachSpec->ReachStroke);
        AddRing(TEXT("ReachFill"), Fill, ReachSpec->ReachColor);
      } else if (bArtActive) {
        // A ring inside the painted circle (the map keeps its zone colours readable under it).
        TArray<FTransform> Pieces;
        S08RingPieces(S08MapSurfaceSpec::RingRadiusUU, S08MapSurfaceSpec::RingWidthUU,
                      S08MapSurfaceSpec::RingSegments, S08MapSurfaceSpec::RingZ, S08MapSurfaceSpec::RingDepth,
                      Pieces);
        for (const FTransform& Piece : Pieces) AddHighlightMesh(BlockerTiles->GetStaticMesh(), Piece);
      } else {
        const float Disc = S08MapSurfaceSpec::MarkDiscDiameterUU / 100.0f;
        AddHighlightMesh(CylinderMesh, FTransform(FRotator::ZeroRotator,
                                                  FVector(0, 0, S08MapSurfaceSpec::MarkDiscZ),
                                                  FVector(Disc, Disc, S08MapSurfaceSpec::MarkDiscDepth)));
      }
    } else if (bArtActive) {
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
  if (bArtActive && bTopologyBoard && ReachSpec && ReachSpec->bReach) {
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW reachable rings cells=%d placed=%d radiusUU=%.0f segments=%d style=readability color=%s stroke=%s widthUU=%.2f strokeUU=%.2f"),
        ArtOutlineCells, bArtOutlinePositionsCorrect ? 1 : 0, S08MapSurfaceSpec::RingRadiusUU, ReachSpec->ReachSegments,
        *S08ColorHex(ReachSpec->ReachColor), *S08ColorHex(ReachSpec->ReachStroke), ReachSpec->ReachWidthUU,
        ReachSpec->ReachStrokeUU));
  } else if (bArtActive && bTopologyBoard) {
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW reachable rings cells=%d placed=%d radiusUU=%.0f segments=%d"), ArtOutlineCells,
        bArtOutlinePositionsCorrect ? 1 : 0, S08MapSurfaceSpec::RingRadiusUU, S08MapSurfaceSpec::RingSegments));
  } else if (bArtActive) {
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW reachable corners cells=%d placed=%d"),
        ArtOutlineCells, bArtOutlinePositionsCorrect ? 1 : 0));
  }
}

void AS08BoardActor::ClearSelection() {
  SetSelectedFighter(FString(), TSet<uint64>());
}

// ---- MS-T-08 move plates ----

bool AS08BoardActor::UsesMovePlates() const {
  return S08MoveHighlight::PlatesEnabled() && MoveHighlight && MoveHighlight->IsReady() &&
         MoveHighlight->GetSpaceCount() > 0;
}

FS08MoveSelectionSpec AS08BoardActor::ActiveMoveSelection() const {
  if (bArtActive) return ActiveProfile.MoveSelection;
  if (bArtDataLoaded) return ArtData.MoveSelection;
  return FS08MoveSelectionSpec();
}

void AS08BoardActor::BuildMoveHighlight() {
  if (!S08MoveHighlight::PlatesEnabled() || BoardModel.Width <= 0) return;
  if (!MoveHighlight) {
    MoveHighlight = NewObject<US08MoveHighlightComponent>(this, TEXT("MoveHighlight"));
    MoveHighlight->SetupAttachment(RootComponent);
    MoveHighlight->RegisterComponent();
    MoveHighlight->Initialize(PlaneMesh);
  }
  MoveHighlight->BuildForBoard(BoardModel, ActiveMoveSelection());
}

US08MoveHighlightComponent* AS08BoardActor::EnsureMoveHighlightForTest() {
  BuildMoveHighlight();
  if (MoveHighlight && !MoveHighlight->IsReady()) {
    MoveHighlight->SetReadyForTest();
    MoveHighlight->BuildForBoard(BoardModel, ActiveMoveSelection());
  }
  return MoveHighlight;
}

void AS08BoardActor::ApplyMovePlates(const FString& FighterId, const TSet<uint64>& Reachable) {
  if (!MoveHighlight) return;
  FS08MoveDraftView View;
  if (!(MoveDraftViewProvider && MoveDraftViewProvider(FighterId, Reachable, View))) {
    View = S08MoveHighlight::ViewFromReachable(BoardModel, Fighters, FighterId, Reachable, DrawsLeaderPips());
  }
  MoveHighlight->ApplyView(View);
}

void AS08BoardActor::SetMoveDraftView(const FS08MoveDraftView& View) {
  if (UsesMovePlates()) MoveHighlight->ApplyView(View);
}

void AS08BoardActor::RefreshMoveDraftView() {
  if (UsesMovePlates()) ApplyMovePlates(SelectedFighterId, ReachableCells);
}

void AS08BoardActor::ShowIllegalCell(int32 X, int32 Y) {
  HideIllegalCell();
  UMaterialInterface* Solid = S08GameLayerMaterial();  // W4-A game layer
  IllegalCell = GetWorld()->SpawnActor<AActor>(AActor::StaticClass(),
                                               BoardModel.CellToWorld(X, Y),
                                               FRotator::ZeroRotator);
  if (!IllegalCell) return;
  UStaticMeshComponent* Mesh = NewObject<UStaticMeshComponent>(IllegalCell, TEXT("Illegal"));
  // ENV-MAPS: a topology board marks the illegal space with a disc (its circle), a grid with the square.
  const bool bDisc = bTopologyBoard && CylinderMesh;
  const float Disc = S08MapSurfaceSpec::MarkDiscDiameterUU / 100.0f;
  Mesh->SetStaticMesh(bDisc ? CylinderMesh.Get() : BlockerTiles->GetStaticMesh().Get());
  Mesh->SetWorldScale3D(bDisc ? FVector(Disc, Disc, S08MapSurfaceSpec::MarkDiscDepth) : FVector(0.85f, 0.85f, 0.02f));
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
  // The spawn location of a root-less actor is lost: the mesh root above would sit at (0,0,1.5) - the board
  // centre - whatever cell was illegal. Move the marker onto its cell (INT-019 centre or the space's layout).
  IllegalCell->SetActorLocation(BoardModel.CellToWorld(X, Y) + FVector(0, 0, 1.5f));
}

void AS08BoardActor::HideIllegalCell() {
  if (IllegalCell) {
    IllegalCell->Destroy();
    IllegalCell = nullptr;
  }
}

// ---- ENV-MAPS track S: topology boards ('map-image' surface and the grey topology view) --------------------

FVector2D AS08BoardActor::GetBoardHalfExtentUU() const {
  return bMapImageActive ? ActiveProfile.Map.HalfUU() : S08BoardHalfExtentUU(BoardModel);
}

int32 AS08BoardActor::GetLatticeInstanceCount() const {
  return NormalTiles->GetInstanceCount() + BlockerTiles->GetInstanceCount() + UnderlayTiles->GetInstanceCount();
}

int32 AS08BoardActor::GetArtCornerCount() const {
  return ArtCorners->GetInstanceCount();
}

void AS08BoardActor::SetArtDataForTest(const FS08BoardArtData& Data) {
  ArtData = Data;
  bArtDataLoaded = true;
  bArtAssetsReady = true;
  BoardModel = FS08BoardModel();  // the next Rebuild selects again
  MapPlaneMaterial = nullptr;
  MapImageMissing.Reset();
}

bool AS08BoardActor::LoadMapImageAssets(const FS08MapImageSpec& Spec) {
  MapImageMissing.Reset();
  MapPlaneMaterial = nullptr;
  UMaterialInterface* Mi = LoadObject<UMaterialInterface>(nullptr, *Spec.MaterialInstancePath, nullptr, LOAD_NoWarn);
  UTexture* Bc = LoadObject<UTexture>(nullptr, *Spec.BaseColorPath, nullptr, LOAD_NoWarn);
  UTexture* Mask = LoadObject<UTexture>(nullptr, *Spec.MaskPath, nullptr, LOAD_NoWarn);
  // The SDF (4K RGBA16F) and the space-ID map are not sampled by M_MapBoard yet: existence only, never loaded
  // into memory for nothing. Their absence is traced but does not force the fallback. They live under
  // S08MapSurfaceSpec::DataRoot, which DefaultGame.ini never cooks: a cooked build does not check them (no
  // 'missing' line; the assets trace reports sdf=-1 id=-1).
  const bool bCheckData = !FPlatformProperties::RequiresCookedData();
  const bool bSdf = !bCheckData || FPackageName::DoesPackageExist(Spec.SdfPath);
  const bool bId = !bCheckData || FPackageName::DoesPackageExist(Spec.SpaceIdPath);
  auto Report = [&](bool bFound, const FString& Path) {
    if (bFound) return;
    MapImageMissing.Add(Path);
    const FString Line = S08MapImageMissingLine(Path);
    UE_LOG(LogTemp, Display, TEXT("%s"), *Line);
    FS08Trace::Write(Line);
  };
  Report(Bc != nullptr, Spec.BaseColorPath);
  Report(Mask != nullptr, Spec.MaskPath);
  Report(bSdf, Spec.SdfPath);
  Report(bId, Spec.SpaceIdPath);
  Report(Mi != nullptr, Spec.MaterialInstancePath);
  if (!Mi || !Bc || !Mask) return false;
  // A MID of the map MI with the profile's textures bound explicitly (the MI was saved with them by the import
  // script; binding again keeps the profile the single source of which texture the board shows).
  UMaterialInstanceDynamic* Mid = UMaterialInstanceDynamic::Create(Mi, this);
  Mid->SetTextureParameterValue(FName(S08MapSurfaceSpec::ParamBaseColor), Bc);
  Mid->SetTextureParameterValue(FName(S08MapSurfaceSpec::ParamGameMask), Mask);
  UTexture* BoundBc = nullptr;
  UTexture* BoundMask = nullptr;
  Mid->GetTextureParameterValue(FHashedMaterialParameterInfo(S08MapSurfaceSpec::ParamBaseColor), BoundBc);
  Mid->GetTextureParameterValue(FHashedMaterialParameterInfo(S08MapSurfaceSpec::ParamGameMask), BoundMask);
  const UMaterial* Base = Mi->GetMaterial();
  MapPlaneMaterial = Mid;
  FS08Trace::Write(FString::Printf(
      TEXT("ARTPREVIEW map-image assets map=%s mi=%s material=%s bc=%s mask=%s boundBc=%d boundMask=%d sdf=%d id=%d"),
      *Spec.Name, *Mi->GetName(), Base ? *Base->GetName() : TEXT("-"), *Bc->GetName(), *Mask->GetName(),
      BoundBc == Bc ? 1 : 0, BoundMask == Mask ? 1 : 0, bCheckData ? (bSdf ? 1 : 0) : -1,
      bCheckData ? (bId ? 1 : 0) : -1));
  return true;
}

void AS08BoardActor::EnsureTopologyComponents() {
  if (!MapPlane) {
    MapPlane = NewObject<UStaticMeshComponent>(this, TEXT("MapPlane"));
    MapPlane->SetupAttachment(RootComponent);
    MapPlane->SetStaticMesh(PlaneMesh);
    MapPlane->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    MapPlane->SetCollisionProfileName(UCollisionProfile::NoCollision_ProfileName);
    MapPlane->SetGenerateOverlapEvents(false);
    MapPlane->SetCanEverAffectNavigation(false);
    MapPlane->SetCastShadow(false);  // flat on the tray; it still receives the figures' shadows
    MapPlane->SetVisibility(false);
    MapPlane->RegisterComponent();
  }
  if (!MapPickBox) {
    // The only cursor surface of a topology board: invisible, QueryOnly, blocks Visibility only. The hit point
    // goes through FS08BoardModel::WorldToCell (the space whose painted circle contains it).
    MapPickBox = NewObject<UBoxComponent>(this, TEXT("MapPickBox"));
    MapPickBox->SetupAttachment(RootComponent);
    MapPickBox->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    MapPickBox->SetCollisionResponseToAllChannels(ECR_Ignore);
    MapPickBox->SetCollisionResponseToChannel(ECC_Visibility, ECR_Block);
    MapPickBox->SetGenerateOverlapEvents(false);
    MapPickBox->SetCanEverAffectNavigation(false);
    MapPickBox->SetHiddenInGame(true);
    MapPickBox->RegisterComponent();
  }
  if (!TopologyDiscs) {
    TopologyDiscs = NewObject<UInstancedStaticMeshComponent>(this, TEXT("TopologyDiscs"));
    TopologyDiscs->SetupAttachment(RootComponent);
    TopologyDiscs->SetStaticMesh(CylinderMesh);
    TopologyDiscs->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    TopologyDiscs->SetVisibility(false);
    TopologyDiscs->RegisterComponent();
  }
  if (!TopologyLinkBars) {
    TopologyLinkBars = NewObject<UInstancedStaticMeshComponent>(this, TEXT("TopologyLinkBars"));
    TopologyLinkBars->SetupAttachment(RootComponent);
    TopologyLinkBars->SetStaticMesh(BlockerTiles->GetStaticMesh());
    TopologyLinkBars->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    TopologyLinkBars->SetVisibility(false);
    TopologyLinkBars->RegisterComponent();
  }
}

void AS08BoardActor::HideTopologyComponents() {
  if (MapPlane) MapPlane->SetVisibility(false);
  if (MapPickBox) MapPickBox->SetCollisionEnabled(ECollisionEnabled::NoCollision);
  if (TopologyDiscs) {
    TopologyDiscs->ClearInstances();
    TopologyDiscs->SetVisibility(false);
  }
  if (TopologyLinkBars) {
    TopologyLinkBars->ClearInstances();
    TopologyLinkBars->SetVisibility(false);
  }
}

namespace {
void PlaceMapPickBox(UBoxComponent* Box, const FVector2D& Half) {
  // Top face on the play plane (z = 0) over the whole map canvas; a hit between the circles resolves to
  // "no cell" in WorldToCell (as a click beside the board did on a grid).
  Box->SetBoxExtent(FVector(Half.X, Half.Y, S08MapSurfaceSpec::PickBoxHalfZ), false);
  Box->SetRelativeLocation(FVector(0.0, 0.0, -S08MapSurfaceSpec::PickBoxHalfZ));
  Box->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
  Box->UpdateBounds();
}
}  // namespace

void AS08BoardActor::BuildGreyTopology(const FS08BoardModel& Board) {
  using namespace S08MapSurfaceSpec;
  EnsureTopologyComponents();
  const FVector2D Half = S08BoardHalfExtentUU(Board);  // the map canvas (FS08LayoutFrame)
  // Dark canvas of the map size (the grey board's underlay tint): debug readable, no lattice squares.
  MapPlane->SetStaticMesh(PlaneMesh);
  MapPlane->SetRelativeTransform(S08MapPlaneTransform(Half * 2.0, PlaneZ));
  MapPlane->SetMaterial(0, GreyUnderlayMaterial.Get());
  MapPlane->SetVisibility(true);
  // One disc per space (the painted circle size), one thin bar per link trimmed to the disc edges.
  TopologyDiscs->ClearInstances();
  TopologyDiscs->SetStaticMesh(CylinderMesh);
  if (GreyTileMaterial) TopologyDiscs->SetMaterial(0, GreyTileMaterial);
  const float DiscScale = GreyDiscDiameterUU / 100.0f;
  int32 Spaces = 0;
  for (int32 Y = 0; Y < Board.Height; ++Y) {
    for (int32 X = 0; X < Board.Width; ++X) {
      if (!Board.IsBoardSpace(X, Y)) continue;
      TopologyDiscs->AddInstance(FTransform(FRotator::ZeroRotator,
                                            Board.CellToWorld(X, Y) - FVector(0, 0, GreyDiscDepth * 50.0f),
                                            FVector(DiscScale, DiscScale, GreyDiscDepth)),
                                 true);
      ++Spaces;
    }
  }
  TopologyDiscs->SetVisibility(true);
  TopologyLinkBars->ClearInstances();
  if (GreyBlockerMaterial) TopologyLinkBars->SetMaterial(0, GreyBlockerMaterial);
  const TArray<TPair<FIntPoint, FIntPoint>> Links = S08BoardLinkPairs(Board);
  for (const TPair<FIntPoint, FIntPoint>& Link : Links) {
    FTransform Bar;
    if (S08LinkBarTransform(Board.CellToWorld(Link.Key.X, Link.Key.Y), Board.CellToWorld(Link.Value.X, Link.Value.Y),
                            GreyDiscDiameterUU * 0.5f, GreyLinkWidthUU, GreyLinkZ, GreyLinkDepth, Bar)) {
      TopologyLinkBars->AddInstance(Bar, true);
    }
  }
  TopologyLinkBars->SetVisibility(true);
  PlaceMapPickBox(MapPickBox, Half);
  FS08Trace::Write(FString::Printf(
      TEXT("BOARD topology grey view %dx%d spaces=%d links=%d discs=%d bars=%d canvas=%.1fx%.1f pick=QueryOnly lattice=%d"),
      Board.Width, Board.Height, Spaces, Links.Num(), TopologyDiscs->GetInstanceCount(),
      TopologyLinkBars->GetInstanceCount(), Half.X * 2.0, Half.Y * 2.0, GetLatticeInstanceCount()));
}

void AS08BoardActor::BuildMapImageSurface(const FS08BoardModel& Board, const FS08BoardSummary& Summary) {
  using namespace S08MapSurfaceSpec;
  EnsureTopologyComponents();
  const FS08MapImageSpec& Map = ActiveProfile.Map;
  const FVector2D Size = Map.SizeUU();
  const FVector2D Half = Map.HalfUU();
  // ENV-U1: the whole illustration as one flat plane above the tray top (-3) and under the figures.
  MapPlane->SetStaticMesh(PlaneMesh);
  MapPlane->SetRelativeTransform(S08MapPlaneTransform(Size, PlaneZ));
  MapPlane->SetMaterial(0, MapPlaneMaterial.Get());
  MapPlane->SetVisibility(true);
  TopologyDiscs->ClearInstances();
  TopologyDiscs->SetVisibility(false);
  TopologyLinkBars->ClearInstances();
  TopologyLinkBars->SetVisibility(false);
  // The wooden frame of the 'tiles' surface (ArtFrameUU look: bars centred on z -3, 14 uu deep) around the map
  // and the ART-005 iron corner brackets on the map corners.
  // ENV-MAPS P5 track C (gap 9 full): a profile "mapFrame" block replaces both with the heavy modular frame
  // ASSET-MAP-FRAME-002 (same footprint: wood exactly to FrameHalf); not imported -> the bars + brackets below.
  bool bFrameKit = false;
  if (!ActiveProfile.MapFrame.bSet) MapFrameKitSource = TEXT("bars");
  if (Map.FrameUU > 0.0f) {
    const double F = Map.FrameUU;
    const double SpanX = (Size.X + 2.0 * F) / 100.0;
    const double SpanY = Size.Y / 100.0;
    const double T = F / 100.0;
    // ENV-MAPS P4 (review gap 9, quick): a profile "frameWood" block puts the frame on the darker M_MapFrameWood.
    UMaterialInterface* FrameWood = MapFrameMaterial();
    bFrameKit = ActiveProfile.MapFrame.bSet && BuildMapFrame002(FrameWood);
    if (!bFrameKit) {
      for (const FTransform& Bar : {
               FTransform(FRotator::ZeroRotator, FVector(0, Half.Y + F * 0.5, FrameCentreZ), FVector(SpanX, T, 0.14)),
               FTransform(FRotator::ZeroRotator, FVector(0, -Half.Y - F * 0.5, FrameCentreZ), FVector(SpanX, T, 0.14)),
               FTransform(FRotator::ZeroRotator, FVector(-Half.X - F * 0.5, 0, FrameCentreZ), FVector(T, SpanY, 0.14)),
               FTransform(FRotator::ZeroRotator, FVector(Half.X + F * 0.5, 0, FrameCentreZ), FVector(T, SpanY, 0.14))}) {
        AddArtSurfacePart(FrameWood, Bar);
      }
    }
  }
  if (!bFrameKit) {
    for (const TPair<FVector, float>& Corner : {
             TPair<FVector, float>(FVector(Half.X, Half.Y, 0), 180),
             TPair<FVector, float>(FVector(-Half.X, Half.Y, 0), -90),
             TPair<FVector, float>(FVector(-Half.X, -Half.Y, 0), 0),
             TPair<FVector, float>(FVector(Half.X, -Half.Y, 0), 90)}) {
      ArtCorners->AddInstance(FTransform(FRotator(0, Corner.Value, 0), Corner.Key, FVector::OneVector), true);
    }
  }
  PlaceMapPickBox(MapPickBox, Half);
  const FString Mismatch = S08ExpectMismatch(ActiveProfile, Summary);
  const UMaterialInterface* Mi = MapPlaneMaterial ? MapPlaneMaterial->Parent.Get() : nullptr;
  FS08Trace::Write(FString::Printf(
      TEXT("ARTPREVIEW board active profile=%s %dx%d surface=map-image map=%s spaces=%d links=%d starts=%d zoneKeys=%d multizone=%d triple=%d obstacles=%d size=%.1fx%.1f src=%dx%d uuPerPx=%.7f frameUU=%.0f surfaceParts=%d corners=%d zoneMarks=0 lattice=%d pick=%.1fx%.1f mi=%s wood=%d expectOk=%d%s"),
      *ActiveProfile.Id, Board.Width, Board.Height, *Map.Name, Summary.Spaces, Summary.Links, Summary.Starts,
      Summary.ZoneKeys.Num(), Summary.MultizoneCells, Summary.TripleZoneCells, Summary.Obstacles, Size.X, Size.Y,
      Map.SrcSizePx.X, Map.SrcSizePx.Y, Map.UuPerPx, Map.FrameUU, ArtSurfaceParts.Num(), ArtCorners->GetInstanceCount(),
      GetLatticeInstanceCount(), Half.X, Half.Y, Mi ? *Mi->GetName() : TEXT("-"), ArtWoodMaterial ? 1 : 0,
      Mismatch.IsEmpty() ? 1 : 0, Mismatch.IsEmpty() ? TEXT("") : *(TEXT(" mismatch=") + Mismatch)));
  for (const FString& Key : Summary.ZoneKeys) {
    FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW board map zone key=%s spaces=%d (painted, no zone marks)"), *Key,
                                     Summary.ZoneCellCounts.FindRef(Key)));
  }
}

// ---- ENV-MAPS P4 readability (map-image boards with a profile "readability" block) --------------------------

UMaterialInterface* AS08BoardActor::MapFrameMaterial() {
  const FS08BoardReadabilitySpec* R = GetActiveReadability();
  if (!R || !R->bFrameWood) {
    MapFrameWoodSource = TEXT("probe");
    return ArtWoodMaterial.Get();
  }
  if (!bMapFrameWoodTried) {
    // Loaded on the first map-image board with the block; a run that never shows one loads nothing new.
    bMapFrameWoodTried = true;
    UMaterialInterface* Base =
        LoadObject<UMaterialInterface>(nullptr, S08MapSurfaceSpec::FrameWoodMaterialPath, nullptr, LOAD_NoWarn);
    if (Base) MapFrameWoodMid = UMaterialInstanceDynamic::Create(Base, this);
  }
  if (!MapFrameWoodMid) {
    MapFrameWoodSource = TEXT("missing");
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW map frame wood=missing material=%s (run tools/art/map_surface/ue_import_map_surface.py) -> probe wood"),
        S08MapSurfaceSpec::FrameWoodMaterialPath));
    return ArtWoodMaterial.Get();
  }
  MapFrameWoodMid->SetScalarParameterValue(FName(S08MapSurfaceSpec::ParamFrameValueScale), R->FrameValueScaleLinear());
  MapFrameWoodMid->SetScalarParameterValue(FName(S08MapSurfaceSpec::ParamFrameSaturation), R->FrameSaturation);
  MapFrameWoodSource = TEXT("frame-wood");
  FS08Trace::Write(FString::Printf(
      TEXT("ARTPREVIEW map frame wood=frame-wood material=M_MapFrameWood valueScaleSrgb=%.2f valueScaleLinear=%.4f saturation=%.2f"),
      R->FrameValueScaleSrgb, R->FrameValueScaleLinear(), R->FrameSaturation));
  return MapFrameWoodMid.Get();
}

// ---- ENV-MAPS P5 track C: heavy modular map frame (gap 9 full) and night backdrop (gap 8) ------------------------

void AS08BoardActor::ClearMapFrameParts() {
  for (UStaticMeshComponent* Part : MapFrameParts) {
    if (Part) Part->DestroyComponent();
  }
  MapFrameParts.Reset();
}

bool AS08BoardActor::BuildMapFrame002(UMaterialInterface* Wood) {
  using namespace S08MapSurfaceSpec;
  const ES08FrameModule Modules[] = {ES08FrameModule::Corner, ES08FrameModule::SegA, ES08FrameModule::SegB,
                                     ES08FrameModule::SegMid};
  if (!bFrame002Tried) {
    // Loaded on the first map-image board with the block; a run that never shows one loads nothing new.
    bFrame002Tried = true;
    Frame002Meshes.Reset();
    for (const ES08FrameModule Module : Modules) {
      Frame002Meshes.Add(LoadObject<UStaticMesh>(nullptr, S08FrameModulePath(Module), nullptr, LOAD_NoWarn));
    }
    Frame002Iron = LoadObject<UMaterialInterface>(nullptr, Frame002IronMaterialPath, nullptr, LOAD_NoWarn);
  }
  TArray<FString> Missing;
  for (int32 I = 0; I < static_cast<int32>(UE_ARRAY_COUNT(Modules)); ++I) {
    if (!Frame002Meshes.IsValidIndex(I) || !Frame002Meshes[I]) Missing.Add(S08FrameModulePath(Modules[I]));
  }
  if (!Missing.IsEmpty()) {
    MapFrameKitSource = TEXT("missing");
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW map frame kit=%s missing=%s (run tools/art/env_kit/ue_import_map_frame.py) -> cube bars + ART-005 corners"),
        Frame002Kit, *FString::Join(Missing, TEXT(","))));
    return false;
  }
  const FS08FrameLayout Layout = S08MapFrame002Layout(ActiveProfile.Map.HalfUU());
  int32 Counts[4] = {0, 0, 0, 0};
  int32 WoodByName = 0, IronSlots = 0;
  for (const FS08FramePiece& P : Layout.Pieces) {
    UStaticMesh* Mesh = Frame002Meshes[static_cast<int32>(P.Module)];
    // Unique names: a map-image board shown again after a grid must not reuse a destroyed component's name.
    UStaticMeshComponent* Part = NewObject<UStaticMeshComponent>(
        this, MakeUniqueObjectName(this, UStaticMeshComponent::StaticClass(), FName(*(TEXT("MapFrame_") + P.Id))));
    Part->SetupAttachment(RootComponent);
    Part->SetStaticMesh(Mesh);
    Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Part->SetCollisionProfileName(UCollisionProfile::NoCollision_ProfileName);
    Part->SetGenerateOverlapEvents(false);
    Part->SetCanEverAffectNavigation(false);
    Part->SetRelativeTransform(FTransform(FRotator(0.0f, P.YawDeg, 0.0f), P.Location, FVector(P.ScaleX, 1.0, 1.0)));
    // Slots by name (SegA / SegB carry no iron faces; the FBX may still list the slot): the wood takes the profile's
    // frame wood (the M_MapFrameWood MID of "frameWood", else the probe wood), the iron keeps / gets its MI.
    const int32 WoodIndex = Part->GetMaterialIndex(FName(Frame002WoodSlot));
    WoodByName += WoodIndex != INDEX_NONE ? 1 : 0;
    if (Wood) Part->SetMaterial(WoodIndex != INDEX_NONE ? WoodIndex : 0, Wood);
    const int32 IronIndex = Part->GetMaterialIndex(FName(Frame002IronSlot));
    if (IronIndex != INDEX_NONE) {
      ++IronSlots;
      if (Frame002Iron) Part->SetMaterial(IronIndex, Frame002Iron);
    }
    Part->RegisterComponent();
    MapFrameParts.Add(Part);
    ++Counts[static_cast<int32>(P.Module)];
  }
  MapFrameKitSource = Frame002Kit;
  FS08Trace::Write(FString::Printf(
      TEXT("ARTPREVIEW map frame kit=%s parts=%d corner=%d a=%d b=%d mid=%d segments=%dx%d stretch=%.6fx%.6f exactFit=%d woodSlots=%d/%d ironSlots=%d wood=%s iron=%s ironProudUU=%.1f replaces=bars+corners"),
      Frame002Kit, MapFrameParts.Num(), Counts[0], Counts[1], Counts[2], Counts[3], Layout.SegmentsX, Layout.SegmentsY,
      Layout.StretchX, Layout.StretchY, Layout.bExactFit ? 1 : 0, WoodByName, MapFrameParts.Num(), IronSlots,
      Wood ? *Wood->GetName() : TEXT("-"), Frame002Iron ? *Frame002Iron->GetName() : TEXT("mesh-default"),
      Frame002IronProudUU));
  return true;
}

void AS08BoardActor::UpdateBackdrop() {
  // ENV-MAPS P7: the concept paste's painted sky replaces the backdrop when its hide list says so (two moons otherwise).
  const bool bConceptHides = ConceptMode.bOn && ActiveProfile.ConceptPaste.HideFor(ConceptMode.Kind).bBackdrop;
  S08MapBackdrop::Update(bEnvLayoutEnabled && bArtActive && bMapImageActive && !bConceptHides, ActiveProfile.Id,
                         ActiveProfile.Backdrop,
                         ActiveProfile.Map.HalfUU(), *this, RootComponent, PlaneMesh, BackdropParts, BackdropRuntime);
}

void AS08BoardActor::ApplyFighterReadability(AS08FighterActor* Actor, const FS08BoardFighter& Fighter,
                                             ES08TeamSlot Look) {
  const FS08BoardReadabilitySpec* R = GetActiveReadability();
  if (!Actor || !R || !(R->bContactShadow || R->bLeaderPip)) return;
  USceneComponent* Root = Actor->GetRootComponent();
  if (!Root) return;
  // A sidekick's base and team ring are smaller (ring scale 0.78): blob and pip follow the ring.
  const float RingScale = Actor->HasTeamRing() ? static_cast<float>(Actor->GetTeamRingScale().X) : 1.0f;
  auto FindPart = [Actor](const FName Name) -> UStaticMeshComponent* {
    TInlineComponentArray<UStaticMeshComponent*> Parts(Actor);
    for (UStaticMeshComponent* Part : Parts) {
      if (Part && Part->GetFName() == Name) return Part;
    }
    return nullptr;
  };
  // Components of the FIGHTER actor (they follow it, hide with it when it dies, go with it on a rebuild).
  auto EnsurePart = [&](const FName Name, UStaticMesh* Mesh, UMaterialInterface* Material,
                        const FTransform& Relative) -> UStaticMeshComponent* {
    UStaticMeshComponent* Part = FindPart(Name);
    if (!Part) {
      Part = NewObject<UStaticMeshComponent>(Actor, Name);
      Part->SetupAttachment(Root);
      Part->SetStaticMesh(Mesh);
      Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);
      Part->SetCollisionProfileName(UCollisionProfile::NoCollision_ProfileName);
      Part->SetGenerateOverlapEvents(false);
      Part->SetCanEverAffectNavigation(false);
      S08ApplyGameLayerPrimitive(Part);
      Part->SetCastShadow(false);
      Part->RegisterComponent();
    }
    Part->SetRelativeTransform(Relative);
    if (Material) Part->SetMaterial(0, Material);
    return Part;
  };
  bool bShadow = false, bPip = false;
  if (R->bContactShadow && PlaneMesh) {
    if (!bContactShadowTried) {
      bContactShadowTried = true;
      UMaterialInterface* Base =
          LoadObject<UMaterialInterface>(nullptr, S08MapSurfaceSpec::ContactShadowMaterialPath, nullptr, LOAD_NoWarn);
      if (Base) ContactShadowMid = UMaterialInstanceDynamic::Create(Base, this);
      FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW readability contact shadow material=%s loaded=%d%s"),
                                       S08MapSurfaceSpec::ContactShadowMaterialPath, ContactShadowMid ? 1 : 0,
                                       ContactShadowMid ? TEXT("") : TEXT(" (run tools/art/map_surface/ue_import_map_surface.py) -> no blob")));
    }
    if (ContactShadowMid) {
      ContactShadowMid->SetScalarParameterValue(FName(S08MapSurfaceSpec::ParamShadowStrength), R->ShadowStrength);
      ContactShadowMid->SetScalarParameterValue(FName(S08MapSurfaceSpec::ParamShadowSoftness), R->ShadowSoftness);
      EnsurePart(FName(TEXT("MapContactShadow")), PlaneMesh.Get(), ContactShadowMid.Get(), S08ContactShadowTransform(*R, RingScale));
      bShadow = true;
    }
  }
  if (R->bLeaderPip && Fighter.bIsHero) {
    UMaterialInterface* Solid = S08GameLayerMaterial();
    TObjectPtr<UMaterialInstanceDynamic>& Fill = Look == ES08TeamSlot::P1 ? LeaderPipMidP1 : LeaderPipMidP2;
    if (Solid && !Fill) {
      Fill = UMaterialInstanceDynamic::Create(Solid, this);
      Fill->SetVectorParameterValue(TEXT("Tint"), S08TeamPalette::RingFill(Look));
    }
    if (Solid && !LeaderPipKeylineMid) {
      LeaderPipKeylineMid = UMaterialInstanceDynamic::Create(Solid, this);
      LeaderPipKeylineMid->SetVectorParameterValue(TEXT("Tint"), S08TeamPalette::Keyline());
    }
    FTransform PipFill, PipKey;
    S08LeaderPipTransforms(S08TeamRingSpec::P1RimOut1, RingScale, PipFill, PipKey);
    UStaticMesh* Cube = BlockerTiles->GetStaticMesh();
    EnsurePart(FName(TEXT("MapLeaderPipKeyline")), Cube, LeaderPipKeylineMid.Get(), PipKey);
    EnsurePart(FName(TEXT("MapLeaderPip")), Cube, Fill.Get(), PipFill);
    bPip = true;
  }
  const FString Key = FString::Printf(TEXT("%s|%d|%d|%.2f|%d"), *Fighter.Id, bShadow ? 1 : 0, bPip ? 1 : 0, RingScale,
                                      static_cast<int32>(Look));
  if (!ReadabilityFightersTraceKey.Contains(Key)) {
    ReadabilityFightersTraceKey += Key + TEXT(";");
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW readability fighter=%s hero=%d contactShadow=%d diameterUU=%.1f strength=%.2f leaderPip=%d look=%s ringScale=%.2f"),
        *Fighter.Id, Fighter.bIsHero ? 1 : 0, bShadow ? 1 : 0, R->ShadowDiameterUU * RingScale, R->ShadowStrength,
        bPip ? 1 : 0, S08TeamSlotName(Look), RingScale));
  }
}

// ---- ENV-MAPS P9 hero light (S08HeroLight.h, docs/art-pipeline/ENV-HERO-LIGHT.md) ----------------------------------

namespace {
/** -NoHeroLight; -ArtPreviewLightsOff (gate G1: no engine light at all) and -S08LegacyRender also switch the rig off. */
bool HeroLightCommandLineOff(FString& OutReason) {
  if (S08HeroLight::OptOut()) {
    OutReason = TEXT("flag-NoHeroLight");
    return true;
  }
  if (FParse::Param(FCommandLine::Get(), S08ConceptPasteSpec::LightsOffFlagName)) {
    OutReason = TEXT("flag-ArtPreviewLightsOff");
    return true;
  }
  if (S08LegacyRender()) {  // the pre-W4 emulation leg of render_bench.py stays exactly the old state
    OutReason = TEXT("legacy-render");
    return true;
  }
  return false;
}
}  // namespace

const FS08HeroLightSpec* AS08BoardActor::GetActiveHeroLight() const {
  FString Unused;
  const bool bOptOut = HeroLightOptOutOverride.IsSet() ? HeroLightOptOutOverride.GetValue() : HeroLightCommandLineOff(Unused);
  if (bOptOut) return nullptr;
  const FS08HeroLightSpec* Spec = nullptr;
  if (bHeroLightOverride) {
    Spec = &HeroLightOverride;
  } else if (bArtActive) {
    if (const FS08LightProfile* Light = ArtData.LightFor(ActiveProfile)) Spec = &Light->HeroLight;
  }
  return Spec && Spec->bSet && Spec->bEnabled && Spec->Layers() > 0 ? Spec : nullptr;
}

void AS08BoardActor::UpdateHeroLights() {
  using namespace S08HeroLightSpec;
  FString OffReason = HeroLightOptOutReason;
  const bool bOptOut = HeroLightOptOutOverride.IsSet() ? HeroLightOptOutOverride.GetValue() : HeroLightCommandLineOff(OffReason);
  const FS08HeroLightSpec* Spec = GetActiveHeroLight();
  const FS08LightProfile* Light = bArtActive ? ArtData.LightFor(ActiveProfile) : nullptr;
  const TCHAR* Reason = bOptOut              ? *OffReason
                        : Spec               ? (bHeroLightOverride ? TEXT("test-override") : TEXT("profile"))
                        : !bArtActive        ? TEXT("no-art")
                        : !Light             ? TEXT("no-light-profile")
                        : !Light->HeroLight.bSet ? TEXT("no-block")
                                             : TEXT("disabled");
  // frozen runs (-Bench without -EnvFxLive, -EnvFxFreeze): the active figure holds exactly activeMul (reproducible frames)
  const bool bFrozen = GetFxOptions().bFreeze;
  // lit figures: the living ones and a falling one in its death hold (DefeatedMul); a hidden dead fighter gets no rig
  int32 Figures = 0;
  for (const AS08FighterActor* Actor : FighterActors) {
    Figures += Actor && (Actor->GetFighter().IsAlive() || Actor->IsInDeathHold()) ? 1 : 0;
  }
  const int32 LayerCount = Spec ? S08HeroLight::LayersForBoard(*Spec, Figures) : 0;
  const int32 MaxFigures = LayerCount > 0 ? MaxLightsPerBoard / LayerCount : 0;
  int32 Lit = 0;
  HeroLightCount = 0;
  HeroLightLayersPerFigure = LayerCount;
  for (AS08FighterActor* Actor : FighterActors) {
    if (!Actor) continue;
    const bool bFigure = Actor->GetFighter().IsAlive() || Actor->IsInDeathHold();
    const bool bRig = Spec && bFigure && Lit < MaxFigures;
    Lit += bRig ? 1 : 0;
    Actor->ApplyHeroLight(bRig ? Spec : nullptr, bRig ? LayerCount : 0, bFrozen);
    HeroLightCount += Actor->GetHeroLightCount();
  }
  const FString Key = FString::Printf(TEXT("%s|%s|%d|%d|%d|%d|%d|%s"), *ActiveProfile.Id, Reason, FighterActors.Num(), Lit,
                                      LayerCount, HeroLightCount, bFrozen ? 1 : 0, Spec ? *Spec->Signature() : TEXT("-"));
  if (Key == HeroLightTraceKey) return;
  HeroLightTraceKey = Key;
  FS08Trace::Write(FString::Printf(
      TEXT("ARTPREVIEW hero-light board profile=%s light=%s on=%d reason=%s fighters=%d litFigures=%d layers=%d lightsOn=%d budget=%d/%d perFigure<=%d channel=%d frozen=%d"),
      ActiveProfile.Id.IsEmpty() ? TEXT("-") : *ActiveProfile.Id, Light ? *Light->Id : TEXT("-"), Spec ? 1 : 0, Reason,
      FighterActors.Num(), Lit, LayerCount, HeroLightCount, Lit * LayerCount, MaxLightsPerBoard, MaxLightsPerFigure, Channel,
      bFrozen ? 1 : 0));
}

// ---- ENV-MAPS live tune (S08LiveTune.h, tools/art/render/LIVE-TUNE.md) -------------------------------------------

void AS08BoardActor::TraceProfilesLoaded(bool bLoaded, bool bOverride, const FString& Path, const TArray<FString>& Errors) {
  FS08Trace::Write(FString::Printf(
      TEXT("ARTPREVIEW board profiles loaded=%d revision=%d boards=%d zoneStyles=%d lightProfiles=%d errors=%d path=Config/ArtBoards/S08ArtBoardProfiles.json"),
      bLoaded ? 1 : 0, ArtData.Revision, ArtData.Boards.Num(), ArtData.ZoneStyles.Num(),
      ArtData.Lights.Num(), Errors.Num()));
  FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW board profiles source=%s sha256=%s%s%s"),
                                   *AppliedRender.ProfilesSource,
                                   ArtData.SourceSha256.IsEmpty() ? TEXT("-") : *ArtData.SourceSha256,
                                   bOverride ? TEXT(" overridePath=") : TEXT(""),
                                   bOverride ? *Path : TEXT("")));
  for (int32 I = 0; I < Errors.Num() && I < 8; ++I) {
    FS08Trace::Write(TEXT("ARTPREVIEW board profiles error: ") + Errors[I]);
  }
}

FS08EnvFxOptions AS08BoardActor::GetFxOptions() const {
  return FxOptionsOverride.IsSet() ? FxOptionsOverride.GetValue() : FS08EnvFxOptions::FromCommandLine();
}

void AS08BoardActor::ResetArtRuntimeForReload() {
  // Back to the state right after BeginPlay, so the next (forced) Rebuild walks the first build's path: no runtime key of
  // the previous build may keep a component (env layout key, concept-paste key, backdrop profile, light profile id).
  if (ConceptAnim) {
    ConceptAnim->RestoreBase();
    ConceptAnim->DestroyComponent();
    ConceptAnim = nullptr;
  }
  S08ConceptPaste::RestoreHides(ConceptRuntime);
  S08ConceptPaste::Clear(ConceptParts, ConceptLights, ConceptRuntime);
  ConceptRuntime = FS08ConceptPasteRuntime();
  ConceptMode = FS08ConceptPasteMode();
  ConceptAssets = FS08ConceptPasteAssets();
  ConceptAssetRefs.Reset();
  ConceptAssetsProfileId.Reset();      // the spec's asset paths may have changed: LoadAssets again
  ConceptApplyFailedProfileId.Reset();
  S08EnvLayout::Clear(EnvProps, EnvLights);
  TunedMaterialMids.Reset();  // the env prop components (and their MIDs) are gone
  MaterialOverridesTraceKey.Reset();
  S08EnvGround::Clear(EnvRuntime.Ground);
  S08EnvLayout::ClearFx(EnvRuntime.Fx);
  EnvRuntime = FS08EnvLayoutRuntime();
  S08MapBackdrop::Clear(BackdropParts, BackdropRuntime);
  BackdropRuntime = FS08BackdropRuntime();
  ClearArtLights();
  // trace dedupe keys: the rebuild writes the lines of a first build again (the live-tune shot copies them)
  HeroLightTraceKey.Reset();
  ReadabilityFightersTraceKey.Reset();
  HeroesV2SummaryKey.Reset();
  bAllMedusaSummaryTraced = false;
  bForceRebuild = true;
}

void AS08BoardActor::RequestFullRebuild() { ResetArtRuntimeForReload(); }

bool AS08BoardActor::ReloadArtData(const FString& ProfilesPath, bool bOverride, const FString& EnvDir,
                                   TArray<FString>& OutErrors, TArray<FString>& OutWarnings) {
  const int32 ErrorsBefore = OutErrors.Num();
  if (!bArtDataLoaded || !bArtAssetsReady) {
    // BeginPlay stopped before the art assets (no -ArtPreview, invalid profiles at start, missing assets): a reload cannot
    // load what only BeginPlay loads
    OutErrors.Add(FString::Printf(TEXT("the board started without art (profiles loaded=%d, assets ready=%d): relaunch"),
                                  bArtDataLoaded ? 1 : 0, bArtAssetsReady ? 1 : 0));
    return false;
  }
  // 1) the board profiles, parsed and validated into a separate document (the applied one stays untouched)
  FS08BoardArtData NewData;
  TArray<FString> ProfileErrors;
  const bool bLoaded = NewData.LoadFile(ProfilesPath, ProfileErrors);
  for (const FString& E : ProfileErrors) OutErrors.Add(TEXT("profiles: ") + E);
  if (!bLoaded && ProfileErrors.IsEmpty()) OutErrors.Add(TEXT("profiles: invalid document"));
  // 2) every env layout and overlay of the folder the next build reads (an invalid one would leave the map without its
  // environment: a half-applied board)
  bool bEnvOverride = false;
  const FString Dir = !EnvDir.IsEmpty() ? EnvDir : !EnvDirOverride.IsEmpty() ? EnvDirOverride : S08EnvLayout::ResolveDir(bEnvOverride);
  TArray<FString> Names;
  IFileManager::Get().FindFiles(Names, *FPaths::Combine(Dir, FString(TEXT("*")) + S08EnvLayoutSpec::FileSuffix), true, false);
  Names.Sort();
  int32 Layouts = 0, Overlays = 0;
  for (const FString& Name : Names) {
    if (!S08EnvLayout::IsOverlayFileName(Name)) {
      FS08EnvLayout Layout;
      TArray<FString> Errors;
      ++Layouts;
      if (!Layout.LoadFile(FPaths::Combine(Dir, Name), Errors)) {
        if (Errors.IsEmpty()) Errors.Add(TEXT("invalid document"));
        for (const FString& E : Errors) OutErrors.Add(FString::Printf(TEXT("envlayout %s: %s"), *Name, *E));
      }
      continue;
    }
    ++Overlays;
    const FString Stem = Name.LeftChop(FCString::Strlen(S08EnvLayoutSpec::FileSuffix));
    FString MapKey, Variant;
    Stem.Split(TEXT("."), &MapKey, &Variant);
    FS08EnvLayout Base;
    TArray<FString> BaseErrors;
    if (!Base.LoadFile(S08EnvLayout::FileFor(Dir, MapKey), BaseErrors)) {
      OutErrors.Add(FString::Printf(TEXT("envlayout %s: the base layout %s%s is missing or invalid"), *Name, *MapKey,
                                    S08EnvLayoutSpec::FileSuffix));
      continue;
    }
    const FS08EnvVariantResult R = S08EnvLayout::ApplyVariant(Dir, MapKey, Variant, Base);
    if (R.Status != TEXT("ok")) {
      if (R.Errors.IsEmpty()) OutErrors.Add(FString::Printf(TEXT("envlayout %s: overlay status %s"), *Name, *R.Status));
      for (const FString& E : R.Errors) OutErrors.Add(FString::Printf(TEXT("envlayout %s: %s"), *Name, *E));
    }
  }
  if (!bLoaded || OutErrors.Num() != ErrorsBefore) {
    FS08Trace::Write(FString::Printf(TEXT("LIVETUNE reload refused errors=%d profiles=%s envDir=%s (the board keeps revision %d sha256=%s)"),
                                     OutErrors.Num() - ErrorsBefore, *ProfilesPath, *Dir, ArtData.Revision,
                                     ArtData.SourceSha256.IsEmpty() ? TEXT("-") : *ArtData.SourceSha256));
    for (int32 I = ErrorsBefore; I < OutErrors.Num() && I < ErrorsBefore + 8; ++I) {
      FS08Trace::Write(TEXT("LIVETUNE reload error: ") + OutErrors[I]);
    }
    return false;
  }
  // only BeginPlay reads these sections: they need a relaunch (the rebuild keeps the BeginPlay materials / meshes)
  {
    FString Text;
    FFileHelper::LoadFileToString(Text, *ProfilesPath);
    const FString Signature = S08BootSectionsSignature(Text);
    if (!BootSectionsSignature.IsEmpty() && Signature != BootSectionsSignature) {
      OutWarnings.Add(TEXT("zoneStyles / fallbackZoneStyle / glyphMeshes / zoneKeyline changed: their materials and meshes are "
                           "loaded at BeginPlay only - relaunch to see them"));
    }
  }
  // 3) swap + tear down to the post-BeginPlay state; the caller rebuilds through the normal path
  ResetArtRuntimeForReload();
  ArtData = MoveTemp(NewData);
  AppliedRender.ProfilesSha256 = ArtData.SourceSha256;
  AppliedRender.ProfilesSource = bOverride ? TEXT("override") : TEXT("pak");
  if (!EnvDir.IsEmpty()) EnvDirOverride = EnvDir;
  TraceProfilesLoaded(true, bOverride, ProfilesPath, TArray<FString>());
  FS08Trace::Write(FString::Printf(TEXT("LIVETUNE reload data revision=%d sha256=%s source=%s envDir=%s envSource=%s layouts=%d overlays=%d"),
                                   ArtData.Revision, *ArtData.SourceSha256, *AppliedRender.ProfilesSource, *Dir,
                                   !EnvDirOverride.IsEmpty() ? TEXT("explicit") : (bEnvOverride ? TEXT("override") : TEXT("pak")),
                                   Layouts, Overlays));
  return true;
}
