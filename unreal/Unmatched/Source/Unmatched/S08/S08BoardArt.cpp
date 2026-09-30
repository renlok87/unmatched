#include "S08BoardArt.h"
#include "S08Contracts.h"
#include "S08Render.h"
#include "Dom/JsonObject.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"

namespace {
using namespace S08ZoneMarkSpec;
constexpr int32 MaxPointLights = 6;

struct FStrokeSeg {
  float Along;   // offset along the side (uu)
  float Length;  // cube scale along the side (1 = 100 uu)
  float Across;  // extra offset away from the cell centre (uu)
  float Thick;   // cube scale across the side
};

void StrokeSegments(ES08ZoneStroke Stroke, TArray<FStrokeSeg>& Out) {
  switch (Stroke) {
    case ES08ZoneStroke::Solid:  // ART-005 blue edge (exact legacy geometry)
      Out.Add({0.0f, 0.96f, 0.0f, 0.04f});
      break;
    case ES08ZoneStroke::Dash3:  // ART-005 three red strokes (exact legacy geometry)
      for (const float A : {-32.0f, 0.0f, 32.0f}) Out.Add({A, 0.28f, 0.0f, 0.045f});
      break;
    case ES08ZoneStroke::Dash2:
      for (const float A : {-24.0f, 24.0f}) Out.Add({A, 0.40f, 0.0f, 0.04f});
      break;
    case ES08ZoneStroke::Dash4:
      for (const float A : {-36.0f, -12.0f, 12.0f, 36.0f}) Out.Add({A, 0.18f, 0.0f, 0.04f});
      break;
    case ES08ZoneStroke::Dots5:
      for (const float A : {-40.0f, -20.0f, 0.0f, 20.0f, 40.0f}) Out.Add({A, 0.08f, 0.0f, 0.05f});
      break;
    case ES08ZoneStroke::Double:
      // W5b-R D-4: two 3-uu lines with a 3-uu gap (was 2 uu each) - the 1.5-uu keylines of the two lines meet in
      // the gap and fill it dark.
      for (const float C : {-3.0f, 3.0f}) Out.Add({0.0f, 0.96f, C, 0.03f});
      break;
    case ES08ZoneStroke::DashDot:
      Out.Add({-24.0f, 0.44f, 0.0f, 0.04f});
      Out.Add({14.0f, 0.08f, 0.0f, 0.04f});
      Out.Add({34.0f, 0.16f, 0.0f, 0.04f});
      break;
  }
}

FVector2D GlyphSlot(int32 Slot) {
  switch (Slot % 4) {
    case 0: return FVector2D(-32.0f, 32.0f);   // near-left (ART-005 legacy)
    case 1: return FVector2D(32.0f, -32.0f);   // far-right
    case 2: return FVector2D(-32.0f, -32.0f);  // far-left
    default: return FVector2D(32.0f, 32.0f);   // near-right
  }
}

bool ReadNumberArray(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, int32 Count,
                     TArray<double>& Out) {
  const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
  if (!Object->TryGetArrayField(Field, Values) || !Values || Values->Num() != Count) return false;
  Out.Reset();
  for (const TSharedPtr<FJsonValue>& V : *Values) {
    double D = 0.0;
    if (!V.IsValid() || !V->TryGetNumber(D)) return false;
    Out.Add(D);
  }
  return true;
}

bool ParseHexColor(const FString& Hex, FColor& Out) {
  if (Hex.Len() != 7 || Hex[0] != TEXT('#')) return false;
  for (int32 I = 1; I < 7; ++I) {
    if (!FChar::IsHexDigit(Hex[I])) return false;
  }
  Out = FColor::FromHex(Hex);
  Out.A = 255;
  return true;
}

bool ParseStyle(const FString& Key, const TSharedPtr<FJsonObject>& Object, FS08ZoneStyle& Out,
                TArray<FString>& Errors) {
  Out = FS08ZoneStyle();
  Out.Key = Key;
  FString Stroke, Glyph, Color;
  if (!Object->TryGetStringField(TEXT("stroke"), Stroke) || !S08ParseZoneStroke(Stroke, Out.Stroke)) {
    Errors.Add(FString::Printf(TEXT("zoneStyle %s: unknown stroke '%s'"), *Key, *Stroke));
    return false;
  }
  if (!Object->TryGetStringField(TEXT("glyph"), Glyph) || !S08ParseZoneGlyph(Glyph, Out.Glyph)) {
    Errors.Add(FString::Printf(TEXT("zoneStyle %s: unknown glyph '%s'"), *Key, *Glyph));
    return false;
  }
  if (!Object->TryGetStringField(TEXT("color"), Color) || !ParseHexColor(Color, Out.Color)) {
    Errors.Add(FString::Printf(TEXT("zoneStyle %s: color '%s' is not #RRGGBB"), *Key, *Color));
    return false;
  }
  Object->TryGetStringField(TEXT("material"), Out.MaterialPath);
  // T4.2 zone MI (optional): a /Game/ package path, checked here so a typo fails the document, not the frame.
  if (Object->TryGetStringField(TEXT("materialInstance"), Out.MaterialInstancePath) &&
      (!Out.MaterialInstancePath.StartsWith(TEXT("/Game/")) || Out.MaterialInstancePath.Contains(TEXT(" ")))) {
    Errors.Add(FString::Printf(TEXT("zoneStyle %s: materialInstance '%s' is not a /Game/ package path"), *Key,
                               *Out.MaterialInstancePath));
    return false;
  }
  return true;
}

bool ParseLight(const FString& ProfileId, const TSharedPtr<FJsonObject>& Object, bool bDirectional,
                FS08LightSpec& Out, TArray<FString>& Errors) {
  Out = FS08LightSpec();
  Out.bDirectional = bDirectional;
  Object->TryGetStringField(TEXT("name"), Out.Name);
  Object->TryGetStringField(TEXT("role"), Out.Role);
  if (bDirectional && Out.Role.IsEmpty()) Out.Role = TEXT("key");
  TArray<double> N;
  if (ReadNumberArray(Object, TEXT("posUU"), 3, N)) {
    Out.bHasPosUU = true;
    Out.PosUU = FVector(N[0], N[1], N[2]);
  } else if (ReadNumberArray(Object, TEXT("at"), 3, N)) {
    Out.At = FVector2D(N[0], N[1]);
    Out.AtZ = static_cast<float>(N[2]);
  } else {
    Errors.Add(FString::Printf(TEXT("light %s/%s: needs posUU [x,y,z] or at [u,v,z]"), *ProfileId, *Out.Name));
    return false;
  }
  if (ReadNumberArray(Object, TEXT("rotation"), 3, N)) {
    Out.Rotation = FRotator(N[0], N[1], N[2]);
  }
  double Value = 0.0;
  if (!Object->TryGetNumberField(TEXT("intensity"), Value) || Value <= 0.0) {
    Errors.Add(FString::Printf(TEXT("light %s/%s: intensity missing"), *ProfileId, *Out.Name));
    return false;
  }
  Out.Intensity = static_cast<float>(Value);
  if (!bDirectional) {
    if (!Object->TryGetNumberField(TEXT("radiusUU"), Value) || Value <= 0.0) {
      Errors.Add(FString::Printf(TEXT("light %s/%s: radiusUU missing"), *ProfileId, *Out.Name));
      return false;
    }
    Out.RadiusUU = static_cast<float>(Value);
  }
  if (ReadNumberArray(Object, TEXT("colorLinear"), 3, N)) {
    Out.bHasColor = true;
    Out.Color = FLinearColor(N[0], N[1], N[2]);
  }
  Out.bCastShadows = bDirectional;  // default: directional casts, points do not
  Object->TryGetBoolField(TEXT("castShadows"), Out.bCastShadows);
  return true;
}

// W4-A (engine gate memo §1 items 1 and 3): units, SkyLight, fixed exposure
// and the key CSM of a light profile. Every block is validated; a broken
// block makes the whole profile invalid (never a silent default).
bool ParseRenderBlocks(const FString& ProfileId, const TSharedPtr<FJsonObject>& Obj, FS08LightProfile& Profile,
                       TArray<FString>& Errors) {
  bool bOk = true;
  const TSharedPtr<FJsonObject>* Units = nullptr;
  if (Obj->TryGetObjectField(TEXT("units"), Units) && Units) {
    (*Units)->TryGetStringField(TEXT("point"), Profile.PointUnits);
    (*Units)->TryGetStringField(TEXT("directional"), Profile.DirectionalUnits);
    if (Profile.PointUnits != TEXT("candelas") || Profile.DirectionalUnits != TEXT("lux")) {
      Errors.Add(FString::Printf(TEXT("light profile %s: units must be {point: candelas, directional: lux}, got %s/%s"),
                                 *ProfileId, *Profile.PointUnits, *Profile.DirectionalUnits));
      bOk = false;
    }
  }
  const TSharedPtr<FJsonObject>* Sky = nullptr;
  if (Obj->TryGetObjectField(TEXT("sky"), Sky) && Sky) {
    FS08SkySpec& S = Profile.Sky;
    FString Source;
    (*Sky)->TryGetStringField(TEXT("source"), Source);
    (*Sky)->TryGetStringField(TEXT("cubemap"), S.CubemapPath);
    double Value = 0.0;
    if (Source != TEXT("cubemap") || !S.CubemapPath.StartsWith(TEXT("/Game/")) ||
        !(*Sky)->TryGetNumberField(TEXT("intensity"), Value) || Value <= 0.0) {
      Errors.Add(FString::Printf(TEXT("light profile %s: sky needs source=cubemap, a /Game/ cubemap and intensity > 0"),
                                 *ProfileId));
      bOk = false;
    } else {
      S.bSet = true;
      S.Intensity = static_cast<float>(Value);
      TArray<double> N;
      if (ReadNumberArray(*Sky, TEXT("colorLinear"), 3, N)) S.Color = FLinearColor(N[0], N[1], N[2]);
      (*Sky)->TryGetBoolField(TEXT("lowerHemisphereIsBlack"), S.bLowerHemisphereIsBlack);
      if (ReadNumberArray(*Sky, TEXT("lowerHemisphereColorLinear"), 3, N)) {
        S.LowerHemisphereColor = FLinearColor(N[0], N[1], N[2]);
      }
    }
  }
  const TSharedPtr<FJsonObject>* Exposure = nullptr;
  if (Obj->TryGetObjectField(TEXT("exposure"), Exposure) && Exposure) {
    FS08ExposureSpec& E = Profile.Exposure;
    FString Method;
    double Min = 0.0, Max = 0.0, Bias = 0.0, Ev = 0.0;
    (*Exposure)->TryGetStringField(TEXT("method"), Method);
    const bool bNumbers = (*Exposure)->TryGetNumberField(TEXT("minBrightness"), Min) &&
                          (*Exposure)->TryGetNumberField(TEXT("maxBrightness"), Max) &&
                          (*Exposure)->TryGetNumberField(TEXT("bias"), Bias);
    (*Exposure)->TryGetNumberField(TEXT("ev100"), Ev);
    if (Method != TEXT("histogram-fixed") || !bNumbers || Min <= 0.0 || !FMath::IsNearlyEqual(Min, Max)) {
      Errors.Add(FString::Printf(TEXT("light profile %s: exposure needs method=histogram-fixed and minBrightness == maxBrightness > 0 plus bias"),
                                 *ProfileId));
      bOk = false;
    } else {
      E.bSet = true;
      E.MinBrightness = static_cast<float>(Min);
      E.MaxBrightness = static_cast<float>(Max);
      E.Bias = static_cast<float>(Bias);
      E.Ev100 = static_cast<float>(Ev);
    }
  }
  const TSharedPtr<FJsonObject>* Dir = nullptr;
  const TSharedPtr<FJsonObject>* Shadow = nullptr;
  if (Obj->TryGetObjectField(TEXT("directional"), Dir) && Dir &&
      (*Dir)->TryGetObjectField(TEXT("shadow"), Shadow) && Shadow) {
    FS08KeyShadowSpec& K = Profile.KeyShadow;
    double Distance = 0.0, Cascades = 0.0, Contact = 0.0;
    (*Shadow)->TryGetNumberField(TEXT("contactShadowLength"), Contact);
    if (!(*Shadow)->TryGetNumberField(TEXT("distanceUU"), Distance) || Distance <= 0.0 ||
        !(*Shadow)->TryGetNumberField(TEXT("cascades"), Cascades) || Cascades < 1.0 || Cascades > 4.0 ||
        Contact < 0.0 || Contact > 0.1) {
      Errors.Add(FString::Printf(TEXT("light profile %s: directional.shadow needs distanceUU > 0, cascades 1..4, contactShadowLength 0..0.1"),
                                 *ProfileId));
      bOk = false;
    } else {
      K.bSet = true;
      K.DistanceUU = static_cast<float>(Distance);
      K.Cascades = static_cast<int32>(Cascades);
      K.ContactShadowLength = static_cast<float>(Contact);
    }
  }
  return bOk;
}

// ENV-MAPS track S: the "mapImage" block of a 'map-image' board. Asset paths are soft /Game/EnvMaps/ packages
// (checked here so a typo fails the document, not the frame); the assets themselves are out of git and may be
// missing in a checkout without the import (the actor falls back, traced).
bool ParseMapImage(const FString& BoardId, const TSharedPtr<FJsonObject>& Object, FS08MapImageSpec& Out,
                   TArray<FString>& Errors) {
  Out = FS08MapImageSpec();
  bool bOk = true;
  if (!Object->TryGetStringField(TEXT("name"), Out.Name) || Out.Name.IsEmpty()) {
    Errors.Add(FString::Printf(TEXT("board %s: mapImage.name missing"), *BoardId));
    bOk = false;
  }
  for (const TCHAR C : Out.Name) {
    if (!FChar::IsAlnum(C)) {
      Errors.Add(FString::Printf(TEXT("board %s: mapImage.name '%s' is not alphanumeric"), *BoardId, *Out.Name));
      bOk = false;
      break;
    }
  }
  auto ReadPath = [&](const TCHAR* Field, FString& Path) {
    if (!Object->TryGetStringField(Field, Path) || !Path.StartsWith(S08MapSurfaceSpec::AssetRoot) ||
        Path.Contains(TEXT(" ")) || Path.Contains(TEXT("."))) {
      Errors.Add(FString::Printf(TEXT("board %s: mapImage.%s '%s' is not a %s package path"), *BoardId, Field,
                                 *Path, S08MapSurfaceSpec::AssetRoot));
      bOk = false;
    }
  };
  ReadPath(TEXT("bc"), Out.BaseColorPath);
  ReadPath(TEXT("mask"), Out.MaskPath);
  ReadPath(TEXT("sdf"), Out.SdfPath);
  ReadPath(TEXT("id"), Out.SpaceIdPath);
  ReadPath(TEXT("materialInstance"), Out.MaterialInstancePath);
  Object->TryGetStringField(TEXT("manifest"), Out.ManifestPath);
  TArray<double> N;
  if (!ReadNumberArray(Object, TEXT("srcSize"), 2, N) || N[0] < 1.0 || N[1] < 1.0 ||
      N[0] != FMath::RoundToDouble(N[0]) || N[1] != FMath::RoundToDouble(N[1])) {
    Errors.Add(FString::Printf(TEXT("board %s: mapImage.srcSize needs [width, height] in whole px > 0"), *BoardId));
    bOk = false;
  } else {
    Out.SrcSizePx = FIntPoint(static_cast<int32>(N[0]), static_cast<int32>(N[1]));
  }
  double Value = 0.0;
  if (!Object->TryGetNumberField(TEXT("uuPerPx"), Value) || Value <= 0.0) {
    Errors.Add(FString::Printf(TEXT("board %s: mapImage.uuPerPx must be > 0"), *BoardId));
    bOk = false;
  } else {
    Out.UuPerPx = static_cast<float>(Value);
  }
  if (Object->TryGetNumberField(TEXT("frameUU"), Value)) {
    if (Value < 0.0) {
      Errors.Add(FString::Printf(TEXT("board %s: mapImage.frameUU must be >= 0"), *BoardId));
      bOk = false;
    } else {
      Out.FrameUU = static_cast<float>(Value);
    }
  }
  if (Object->HasField(TEXT("trayOffsetUU"))) {
    if (!ReadNumberArray(Object, TEXT("trayOffsetUU"), 2, N)) {
      Errors.Add(FString::Printf(TEXT("board %s: mapImage.trayOffsetUU needs [x, y]"), *BoardId));
      bOk = false;
    } else {
      Out.TrayOffsetUU = FVector2D(N[0], N[1]);
    }
  }
  Out.bSet = bOk;
  return bOk;
}
}  // namespace

FVector FS08MapImageSpec::PxToWorld(const FVector2D& Px) const {
  const double W = SrcSizePx.X, H = SrcSizePx.Y;
  return FVector((Px.X / W - 0.5) * W * UuPerPx, (Px.Y / H - 0.5) * H * UuPerPx, 0.0);
}

TArray<FString> FS08MapImageSpec::AssetPaths() const {
  return {BaseColorPath, MaskPath, SdfPath, SpaceIdPath, MaterialInstancePath};
}

bool FS08MapImageSpec::MatchesLayoutFrame(const FS08LayoutFrame& Frame) const {
  return FMath::IsNearlyEqual(static_cast<double>(SrcSizePx.X), Frame.SrcSize.X, 1e-3) &&
         FMath::IsNearlyEqual(static_cast<double>(SrcSizePx.Y), Frame.SrcSize.Y, 1e-3) &&
         FMath::IsNearlyEqual(UuPerPx, Frame.UuPerPx, 1e-6f);
}

bool FS08MapImageSpec::MatchesDefaultLayoutFrame() const {
  return MatchesLayoutFrame(FS08LayoutFrame());
}

const TCHAR* S08ZoneStrokeName(ES08ZoneStroke Stroke) {
  switch (Stroke) {
    case ES08ZoneStroke::Solid: return TEXT("solid");
    case ES08ZoneStroke::Dash2: return TEXT("dash2");
    case ES08ZoneStroke::Dash3: return TEXT("dash3");
    case ES08ZoneStroke::Dash4: return TEXT("dash4");
    case ES08ZoneStroke::Dots5: return TEXT("dots5");
    case ES08ZoneStroke::Double: return TEXT("double");
    case ES08ZoneStroke::DashDot: return TEXT("dashdot");
  }
  return TEXT("?");
}

const TCHAR* S08ZoneGlyphName(ES08ZoneGlyph Glyph) {
  switch (Glyph) {
    case ES08ZoneGlyph::Diamond: return TEXT("diamond");
    case ES08ZoneGlyph::Bar1: return TEXT("bar1");
    case ES08ZoneGlyph::Bars2: return TEXT("bars2");
    case ES08ZoneGlyph::Bars3: return TEXT("bars3");
    case ES08ZoneGlyph::HBars2: return TEXT("hbars2");
    case ES08ZoneGlyph::Square: return TEXT("square");
    case ES08ZoneGlyph::Cross: return TEXT("cross");
    case ES08ZoneGlyph::X: return TEXT("x");
    case ES08ZoneGlyph::Tee: return TEXT("tee");
    case ES08ZoneGlyph::Chevron: return TEXT("chevron");
    case ES08ZoneGlyph::Ring: return TEXT("ring");
  }
  return TEXT("?");
}

const TCHAR* S08BoardSurfaceName(ES08BoardSurface Surface) {
  switch (Surface) {
    case ES08BoardSurface::Cobble5x6Mesh: return TEXT("cobble-5x6-mesh");
    case ES08BoardSurface::MapImage: return TEXT("map-image");
    default: return TEXT("tiles");
  }
}

const TCHAR* S08ProfileMatchName(ES08ProfileMatch Match) {
  switch (Match) {
    case ES08ProfileMatch::BoardId: return TEXT("boardId");
    case ES08ProfileMatch::Signature: return TEXT("signature");
    default: return TEXT("none");
  }
}

bool S08ParseZoneStroke(const FString& Name, ES08ZoneStroke& Out) {
  for (const ES08ZoneStroke S : {ES08ZoneStroke::Solid, ES08ZoneStroke::Dash2, ES08ZoneStroke::Dash3,
                                 ES08ZoneStroke::Dash4, ES08ZoneStroke::Dots5, ES08ZoneStroke::Double,
                                 ES08ZoneStroke::DashDot}) {
    if (Name == S08ZoneStrokeName(S)) {
      Out = S;
      return true;
    }
  }
  return false;
}

bool S08ParseZoneGlyph(const FString& Name, ES08ZoneGlyph& Out) {
  for (const ES08ZoneGlyph G : {ES08ZoneGlyph::Diamond, ES08ZoneGlyph::Bar1, ES08ZoneGlyph::Bars2,
                                ES08ZoneGlyph::Bars3, ES08ZoneGlyph::HBars2, ES08ZoneGlyph::Square,
                                ES08ZoneGlyph::Cross, ES08ZoneGlyph::X, ES08ZoneGlyph::Tee,
                                ES08ZoneGlyph::Chevron, ES08ZoneGlyph::Ring}) {
    if (Name == S08ZoneGlyphName(G)) {
      Out = G;
      return true;
    }
  }
  return false;
}

FString FS08ZoneStyle::ColorHex() const {
  return FString::Printf(TEXT("#%02X%02X%02X"), Color.R, Color.G, Color.B);
}

bool FS08LightProfile::BudgetOk(FString& OutReason) const {
  if (!bHasDirectional || !Directional.bDirectional) {
    OutReason = TEXT("no directional light");
    return false;
  }
  if (!Directional.bCastShadows) {
    OutReason = TEXT("directional light without shadow");
    return false;
  }
  if (Points.Num() > MaxPointLights) {
    OutReason = FString::Printf(TEXT("%d point lights > %d"), Points.Num(), MaxPointLights);
    return false;
  }
  for (const FS08LightSpec& P : Points) {
    if (P.bCastShadows) {
      OutReason = FString::Printf(TEXT("point light %s casts shadows"), *P.Name);
      return false;
    }
  }
  OutReason.Reset();
  return true;
}

FS08BoardSummary S08SummarizeBoard(const FS08BoardModel& Board) {
  FS08BoardSummary S;
  S.Width = Board.Width;
  S.Height = Board.Height;
  S.Cells = Board.Width * Board.Height;
  for (int32 Y = 0; Y < Board.Height; ++Y) {
    for (int32 X = 0; X < Board.Width; ++X) {
      const FS08Cell* Cell = Board.CellAt(X, Y);
      if (!Cell || !Cell->IsPassable()) ++S.Obstacles;
      if (!Cell || Cell->Zones.Num() == 0) continue;
      ++S.ZoneCells;
      if (Cell->Zones.Num() >= 2) ++S.MultizoneCells;
      if (Cell->Zones.Num() >= 3) ++S.TripleZoneCells;
      TSet<FString> Unique;
      for (const FString& Zone : Cell->Zones) {
        if (Unique.Contains(Zone)) continue;
        Unique.Add(Zone);
        S.ZoneCellCounts.FindOrAdd(Zone) += 1;
      }
    }
  }
  S.ZoneCellCounts.GenerateKeyArray(S.ZoneKeys);
  S.ZoneKeys.Sort();
  // ENV-MAPS: the topology view of the board (track U model: bHasTopology, bHasLayout, StartSlot, Neighbours).
  S.bTopology = Board.bHasTopology;
  if (S.bTopology) {
    for (const FS08Cell& Cell : Board.Cells) {
      if (!Cell.bHasLayout) continue;
      ++S.Spaces;
      if (Cell.StartSlot > 0) ++S.Starts;
    }
    S.Links = S08BoardLinkPairs(Board).Num();
  }
  return S;
}

FString FS08BoardArtData::DefaultPath() {
  return FPaths::Combine(FPaths::ProjectConfigDir(), TEXT("ArtBoards"), TEXT("S08ArtBoardProfiles.json"));
}

FString FS08BoardArtData::ResolvePath(bool& bOutOverride) {
  FString Override;
  bOutOverride = FParse::Value(FCommandLine::Get(), TEXT("ArtBoardProfiles="), Override) && !Override.IsEmpty();
  return bOutOverride ? Override : DefaultPath();
}

bool FS08BoardArtData::LoadFile(const FString& Path, TArray<FString>& OutErrors) {
  TArray<uint8> Bytes;
  if (!FFileHelper::LoadFileToArray(Bytes, *Path)) {
    OutErrors.Add(FString::Printf(TEXT("cannot read %s"), *Path));
    return false;
  }
  FString Text;
  FFileHelper::BufferToString(Text, Bytes.GetData(), Bytes.Num());
  const bool bOk = ParseJson(Text, OutErrors);
  SourceSha256 = S08Sha256Hex(Bytes.GetData(), Bytes.Num());
  return bOk;
}

bool FS08BoardArtData::ParseJson(const FString& Text, TArray<FString>& OutErrors) {
  ZoneStyles.Reset();
  Lights.Reset();
  Boards.Reset();
  Revision = 0;
  SourceSha256.Reset();
  const int32 ErrorsBefore = OutErrors.Num();
  TSharedPtr<FJsonObject> Root;
  FString Problem;
  if (!FS08Contracts::TryParseJsonObject(Text, Root, Problem) || !Root.IsValid()) {
    OutErrors.Add(TEXT("invalid JSON: ") + Problem);
    return false;
  }
  FString Schema;
  if (!Root->TryGetStringField(TEXT("schema"), Schema) || Schema != TEXT("unmatched.s08-art-board-profiles/1")) {
    OutErrors.Add(FString::Printf(TEXT("schema '%s' is not unmatched.s08-art-board-profiles/1"), *Schema));
    return false;
  }
  double Rev = 0.0;
  Root->TryGetNumberField(TEXT("revision"), Rev);
  Revision = static_cast<int32>(Rev);
  Root->TryGetStringField(TEXT("status"), Status);

  const TSharedPtr<FJsonObject>* Styles = nullptr;
  if (Root->TryGetObjectField(TEXT("zoneStyles"), Styles) && Styles && Styles->IsValid()) {
    for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : (*Styles)->Values) {
      const TSharedPtr<FJsonObject>* Obj = nullptr;
      FS08ZoneStyle Style;
      if (Pair.Value.IsValid() && Pair.Value->TryGetObject(Obj) && Obj &&
          ParseStyle(Pair.Key, *Obj, Style, OutErrors)) {
        ZoneStyles.Add(Pair.Key, Style);
      }
    }
  }
  FallbackStyle = FS08ZoneStyle();
  const TSharedPtr<FJsonObject>* Fallback = nullptr;
  if (Root->TryGetObjectField(TEXT("fallbackZoneStyle"), Fallback) && Fallback) {
    ParseStyle(TEXT("(fallback)"), *Fallback, FallbackStyle, OutErrors);
  }
  FallbackStyle.bFallback = true;

  // W5b-R D-4: the dark keyline under zone strokes and glyphs (optional block; absent = no keylines, rev <= 3).
  Keyline = FS08ZoneKeyline();
  const TSharedPtr<FJsonObject>* KeylineObj = nullptr;
  if (Root->TryGetObjectField(TEXT("zoneKeyline"), KeylineObj) && KeylineObj && KeylineObj->IsValid()) {
    FString Color;
    double Grow = 0.0;
    if (!(*KeylineObj)->TryGetStringField(TEXT("color"), Color) || !ParseHexColor(Color, Keyline.Color)) {
      OutErrors.Add(FString::Printf(TEXT("zoneKeyline: color '%s' is not #RRGGBB"), *Color));
    } else if (!(*KeylineObj)->TryGetNumberField(TEXT("growUU"), Grow) ||
               !FMath::IsNearlyEqual(Grow, static_cast<double>(KeylineGrowUU), 1e-3)) {
      OutErrors.Add(FString::Printf(TEXT("zoneKeyline: growUU %.3f != %.1f (the C++ geometry, S08ZoneMarkSpec)"), Grow,
                                    KeylineGrowUU));
    } else {
      Keyline.bSet = true;
      Keyline.GrowUU = static_cast<float>(Grow);
      (*KeylineObj)->TryGetStringField(TEXT("materialInstance"), Keyline.MaterialInstancePath);
      if (!Keyline.MaterialInstancePath.IsEmpty() && !Keyline.MaterialInstancePath.StartsWith(TEXT("/Game/"))) {
        OutErrors.Add(FString::Printf(TEXT("zoneKeyline: materialInstance '%s' is not a /Game/ path"),
                                      *Keyline.MaterialInstancePath));
        Keyline.bSet = false;
      }
      const TSharedPtr<FJsonObject>* KeyMeshes = nullptr;
      if ((*KeylineObj)->TryGetObjectField(TEXT("glyphMeshes"), KeyMeshes) && KeyMeshes && KeyMeshes->IsValid()) {
        for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : (*KeyMeshes)->Values) {
          ES08ZoneGlyph Glyph;
          FString Path;
          if (!S08ParseZoneGlyph(Pair.Key, Glyph) || !Pair.Value.IsValid() || !Pair.Value->TryGetString(Path) ||
              !Path.StartsWith(TEXT("/Game/")) || Path.Contains(TEXT(" "))) {
            OutErrors.Add(FString::Printf(TEXT("zoneKeyline.glyphMeshes %s: bad entry"), *Pair.Key));
            continue;
          }
          Keyline.GlyphMeshPaths.Add(Pair.Key, Path);
        }
      }
    }
  }

  // T4.2 glyph meshes: glyph name -> /Game/ static mesh package (one per glyph shape).
  GlyphMeshPaths.Reset();
  const TSharedPtr<FJsonObject>* GlyphMeshes = nullptr;
  if (Root->TryGetObjectField(TEXT("glyphMeshes"), GlyphMeshes) && GlyphMeshes && GlyphMeshes->IsValid()) {
    for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : (*GlyphMeshes)->Values) {
      ES08ZoneGlyph Glyph;
      FString Path;
      if (!S08ParseZoneGlyph(Pair.Key, Glyph)) {
        OutErrors.Add(FString::Printf(TEXT("glyphMeshes: unknown glyph '%s'"), *Pair.Key));
        continue;
      }
      if (!Pair.Value.IsValid() || !Pair.Value->TryGetString(Path) || !Path.StartsWith(TEXT("/Game/")) ||
          Path.Contains(TEXT(" "))) {
        OutErrors.Add(FString::Printf(TEXT("glyphMeshes %s: '%s' is not a /Game/ package path"), *Pair.Key, *Path));
        continue;
      }
      GlyphMeshPaths.Add(Pair.Key, Path);
    }
  }

  const TSharedPtr<FJsonObject>* LightObjects = nullptr;
  if (Root->TryGetObjectField(TEXT("lightProfiles"), LightObjects) && LightObjects) {
    for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : (*LightObjects)->Values) {
      const TSharedPtr<FJsonObject>* Obj = nullptr;
      if (!Pair.Value.IsValid() || !Pair.Value->TryGetObject(Obj) || !Obj) continue;
      FS08LightProfile Profile;
      Profile.Id = Pair.Key;
      const TSharedPtr<FJsonObject>* Dir = nullptr;
      if ((*Obj)->TryGetObjectField(TEXT("directional"), Dir) && Dir) {
        Profile.bHasDirectional = ParseLight(Pair.Key, *Dir, true, Profile.Directional, OutErrors);
      }
      const TArray<TSharedPtr<FJsonValue>>* Points = nullptr;
      if ((*Obj)->TryGetArrayField(TEXT("points"), Points) && Points) {
        for (const TSharedPtr<FJsonValue>& V : *Points) {
          const TSharedPtr<FJsonObject>* P = nullptr;
          FS08LightSpec Spec;
          if (V.IsValid() && V->TryGetObject(P) && P && ParseLight(Pair.Key, *P, false, Spec, OutErrors)) {
            Profile.Points.Add(Spec);
          }
        }
      }
      if (!ParseRenderBlocks(Pair.Key, *Obj, Profile, OutErrors)) continue;
      FString Reason;
      if (!Profile.BudgetOk(Reason)) {
        OutErrors.Add(FString::Printf(TEXT("light profile %s over budget: %s"), *Pair.Key, *Reason));
        continue;
      }
      Lights.Add(Pair.Key, Profile);
    }
  }

  const TArray<TSharedPtr<FJsonValue>>* BoardValues = nullptr;
  if (Root->TryGetArrayField(TEXT("boards"), BoardValues) && BoardValues) {
    TSet<FString> Ids;
    for (const TSharedPtr<FJsonValue>& V : *BoardValues) {
      const TSharedPtr<FJsonObject>* Obj = nullptr;
      if (!V.IsValid() || !V->TryGetObject(Obj) || !Obj) continue;
      FS08BoardArtProfile B;
      (*Obj)->TryGetStringField(TEXT("id"), B.Id);
      if (B.Id.IsEmpty() || Ids.Contains(B.Id)) {
        OutErrors.Add(FString::Printf(TEXT("board profile id '%s' empty or duplicate"), *B.Id));
        continue;
      }
      Ids.Add(B.Id);
      const TSharedPtr<FJsonObject>* Match = nullptr;
      if (!(*Obj)->TryGetObjectField(TEXT("match"), Match) || !Match) {
        OutErrors.Add(FString::Printf(TEXT("board %s: match missing"), *B.Id));
        continue;
      }
      (*Match)->TryGetStringArrayField(TEXT("boardIds"), B.MatchBoardIds);
      double D = 0.0;
      if ((*Match)->TryGetNumberField(TEXT("width"), D)) B.MatchWidth = static_cast<int32>(D);
      if ((*Match)->TryGetNumberField(TEXT("height"), D)) B.MatchHeight = static_cast<int32>(D);
      (*Match)->TryGetStringArrayField(TEXT("zoneKeys"), B.MatchZoneKeys);
      B.MatchZoneKeys.Sort();
      FString Surface;
      (*Obj)->TryGetStringField(TEXT("surface"), Surface);
      if (Surface == TEXT("cobble-5x6-mesh")) {
        B.Surface = ES08BoardSurface::Cobble5x6Mesh;
      } else if (Surface == TEXT("tiles")) {
        B.Surface = ES08BoardSurface::Tiles;
      } else if (Surface == TEXT("map-image")) {
        B.Surface = ES08BoardSurface::MapImage;
      } else {
        OutErrors.Add(FString::Printf(TEXT("board %s: unknown surface '%s'"), *B.Id, *Surface));
        continue;
      }
      if (B.Surface == ES08BoardSurface::MapImage) {
        // ENV-MAPS: a map-image board is selected by its Board row id only (a W x H signature would also catch
        // any grid of the same lattice size) and needs the "mapImage" block.
        const TSharedPtr<FJsonObject>* MapObj = nullptr;
        if (!(*Obj)->TryGetObjectField(TEXT("mapImage"), MapObj) || !MapObj || !MapObj->IsValid()) {
          OutErrors.Add(FString::Printf(TEXT("board %s: surface map-image needs a mapImage block"), *B.Id));
          continue;
        }
        if (!ParseMapImage(B.Id, *MapObj, B.Map, OutErrors)) continue;
        if (B.MatchBoardIds.Num() == 0) {
          OutErrors.Add(FString::Printf(TEXT("board %s: map-image needs match.boardIds (selected by id only)"), *B.Id));
          continue;
        }
        if (B.MatchWidth > 0 || B.MatchHeight > 0 || B.MatchZoneKeys.Num() > 0) {
          OutErrors.Add(FString::Printf(TEXT("board %s: map-image match takes no width/height/zoneKeys signature"),
                                        *B.Id));
          continue;
        }
      }
      (*Obj)->TryGetStringField(TEXT("light"), B.LightId);
      if (!Lights.Contains(B.LightId)) {
        OutErrors.Add(FString::Printf(TEXT("board %s: light profile '%s' missing or invalid"), *B.Id, *B.LightId));
        continue;
      }
      (*Obj)->TryGetBoolField(TEXT("legacyCobbleTrace"), B.bLegacyCobbleTrace);
      (*Obj)->TryGetBoolField(TEXT("artFixture"), B.bArtFixture);
      FString Glyphs;
      if ((*Obj)->TryGetStringField(TEXT("glyphs"), Glyphs)) {
        if (Glyphs == TEXT("review")) {
          B.bZoneColorGlyphs = false;
        } else if (Glyphs != TEXT("zone")) {
          OutErrors.Add(FString::Printf(TEXT("board %s: glyphs '%s' is not zone|review"), *B.Id, *Glyphs));
          continue;
        }
      }
      const TSharedPtr<FJsonObject>* Expect = nullptr;
      if ((*Obj)->TryGetObjectField(TEXT("expect"), Expect) && Expect) {
        auto ReadInt = [&](const TCHAR* Field, int32& Out) {
          double N = 0.0;
          if ((*Expect)->TryGetNumberField(Field, N)) Out = static_cast<int32>(N);
        };
        ReadInt(TEXT("cells"), B.Expect.Cells);
        ReadInt(TEXT("zoneCells"), B.Expect.ZoneCells);
        ReadInt(TEXT("multizoneCells"), B.Expect.MultizoneCells);
        ReadInt(TEXT("obstacles"), B.Expect.Obstacles);
        ReadInt(TEXT("spaces"), B.Expect.Spaces);
        ReadInt(TEXT("links"), B.Expect.Links);
        (*Expect)->TryGetStringArrayField(TEXT("zones"), B.Expect.Zones);
        B.Expect.Zones.Sort();
        const TSharedPtr<FJsonObject>* Counts = nullptr;
        if ((*Expect)->TryGetObjectField(TEXT("zoneCellCounts"), Counts) && Counts) {
          for (const TPair<FString, TSharedPtr<FJsonValue>>& C : (*Counts)->Values) {
            double N = 0.0;
            if (C.Value.IsValid() && C.Value->TryGetNumber(N)) B.Expect.ZoneCellCounts.Add(C.Key, static_cast<int32>(N));
          }
        }
      }
      Boards.Add(B);
    }
  }
  if (Boards.Num() == 0) OutErrors.Add(TEXT("no board profiles"));
  return OutErrors.Num() == ErrorsBefore;
}

FS08ZoneStyle FS08BoardArtData::StyleFor(const FString& Key) const {
  if (const FS08ZoneStyle* Style = ZoneStyles.Find(Key)) return *Style;
  FS08ZoneStyle Fallback = FallbackStyle;
  Fallback.Key = Key;
  Fallback.bFallback = true;
  return Fallback;
}

const FS08LightProfile* FS08BoardArtData::LightFor(const FS08BoardArtProfile& Profile) const {
  return Lights.Find(Profile.LightId);
}

const FS08BoardArtProfile* FS08BoardArtData::Select(const FS08BoardModel& Board, const FString& BoardId,
                                                    ES08ProfileMatch& OutMatch) const {
  OutMatch = ES08ProfileMatch::None;
  if (!BoardId.IsEmpty()) {
    for (const FS08BoardArtProfile& B : Boards) {
      if (B.MatchBoardIds.Contains(BoardId)) {
        OutMatch = ES08ProfileMatch::BoardId;
        return &B;
      }
    }
  }
  // ENV-MAPS: a topology board is matched by its Board row id only - a W x H + zone-key signature describes a
  // grid and would dress the space graph with lattice tiles.
  if (Board.bHasTopology) return nullptr;
  const FS08BoardSummary Summary = S08SummarizeBoard(Board);
  for (const FS08BoardArtProfile& B : Boards) {
    if (B.MatchWidth > 0 && B.MatchHeight > 0 && B.MatchZoneKeys.Num() > 0 &&
        B.MatchWidth == Board.Width && B.MatchHeight == Board.Height &&
        B.MatchZoneKeys == Summary.ZoneKeys) {
      OutMatch = ES08ProfileMatch::Signature;
      return &B;
    }
  }
  return nullptr;
}

FString S08ExpectMismatch(const FS08BoardArtProfile& Profile, const FS08BoardSummary& Summary) {
  TArray<FString> Out;
  const FS08BoardExpect& E = Profile.Expect;
  if (Profile.MatchWidth > 0 && (Profile.MatchWidth != Summary.Width || Profile.MatchHeight != Summary.Height)) {
    Out.Add(FString::Printf(TEXT("size %dx%d!=%dx%d"), Summary.Width, Summary.Height,
                            Profile.MatchWidth, Profile.MatchHeight));
  }
  auto Check = [&](const TCHAR* Name, int32 Expected, int32 Actual) {
    if (Expected >= 0 && Expected != Actual) Out.Add(FString::Printf(TEXT("%s %d!=%d"), Name, Actual, Expected));
  };
  Check(TEXT("cells"), E.Cells, Summary.Cells);
  Check(TEXT("zoneCells"), E.ZoneCells, Summary.ZoneCells);
  Check(TEXT("multizone"), E.MultizoneCells, Summary.MultizoneCells);
  Check(TEXT("obstacles"), E.Obstacles, Summary.Obstacles);
  // ENV-MAPS map-image expect: the space graph instead of the W x H lattice.
  if ((E.Spaces >= 0 || E.Links >= 0) && !Summary.bTopology) Out.Add(TEXT("topology 0!=1"));
  Check(TEXT("spaces"), E.Spaces, Summary.Spaces);
  Check(TEXT("links"), E.Links, Summary.Links);
  if (E.Zones.Num() > 0 && E.Zones != Summary.ZoneKeys) {
    Out.Add(FString::Printf(TEXT("zones %s!=%s"), *FString::Join(Summary.ZoneKeys, TEXT("+")),
                            *FString::Join(E.Zones, TEXT("+"))));
  }
  if (E.ZoneCellCounts.Num() > 0) {
    TArray<FString> Keys;
    E.ZoneCellCounts.GenerateKeyArray(Keys);
    for (const FString& K : Summary.ZoneKeys) Keys.AddUnique(K);
    Keys.Sort();
    for (const FString& K : Keys) {
      const int32 Expected = E.ZoneCellCounts.FindRef(K);
      const int32 Actual = Summary.ZoneCellCounts.FindRef(K);
      if (Expected != Actual) Out.Add(FString::Printf(TEXT("%s %d!=%d"), *K, Actual, Expected));
    }
  }
  return FString::Join(Out, TEXT(","));
}

float S08ZoneStrokeHalfExtentUU(ES08ZoneStroke Stroke) {
  TArray<FStrokeSeg> Segs;
  StrokeSegments(Stroke, Segs);
  float Half = 0.0f;
  for (const FStrokeSeg& S : Segs) Half = FMath::Max(Half, FMath::Abs(S.Across) + S.Thick * 50.0f);
  return Half;
}

float S08ZoneStrokeCenterUU(ES08ZoneStroke Stroke) {
  // D-4: the nominal 42-uu centre line, pulled further in so that the fill plus the keyline of every stroke type
  // stays <= MaxOuterUU (1 uu inside the 46-uu slab edge; the T5.2 strokes at 46 were half in the dark groove).
  return FMath::Min(EdgeUU, MaxOuterUU - KeylineGrowUU - S08ZoneStrokeHalfExtentUU(Stroke));
}

float S08ZoneStrokeOuterUU(ES08ZoneStroke Stroke, bool bKeyline) {
  return S08ZoneStrokeCenterUU(Stroke) + S08ZoneStrokeHalfExtentUU(Stroke) + (bKeyline ? KeylineGrowUU : 0.0f);
}

namespace {
void StrokePiecesAt(ES08ZoneStroke Stroke, int32 Side, float GrowUU, float Z, float Depth, TArray<FTransform>& Out) {
  TArray<FStrokeSeg> Segs;
  StrokeSegments(Stroke, Segs);
  const float Edge = S08ZoneStrokeCenterUU(Stroke);
  const float G = 2.0f * GrowUU / 100.0f;
  for (const FStrokeSeg& S : Segs) {
    FVector Pos;
    FVector Scale;
    switch (Side % 4) {
      case 0: Pos = FVector(S.Along, Edge + S.Across, Z); Scale = FVector(S.Length + G, S.Thick + G, Depth); break;
      case 1: Pos = FVector(-Edge - S.Across, S.Along, Z); Scale = FVector(S.Thick + G, S.Length + G, Depth); break;
      case 2: Pos = FVector(S.Along, -Edge - S.Across, Z); Scale = FVector(S.Length + G, S.Thick + G, Depth); break;
      default: Pos = FVector(Edge + S.Across, S.Along, Z); Scale = FVector(S.Thick + G, S.Length + G, Depth); break;
    }
    Out.Add(FTransform(FRotator::ZeroRotator, Pos, Scale));
  }
}

void GlyphPiecesAt(ES08ZoneGlyph Glyph, int32 Slot, float GrowUU, float Z, float Depth, TArray<FTransform>& Out) {
  const FVector2D P2 = GlyphSlot(Slot);
  const FVector P(P2.X, P2.Y, Z);
  const float G = 2.0f * GrowUU / 100.0f;
  auto Add = [&](float Yaw, const FVector& Offset, float SX, float SY) {
    Out.Add(FTransform(FRotator(0.0f, Yaw, 0.0f), P + Offset, FVector(SX + G, SY + G, Depth)));
  };
  switch (Glyph) {
    case ES08ZoneGlyph::Diamond: Add(45.0f, FVector::ZeroVector, 0.18f, 0.18f); break;  // ART-005 blue
    case ES08ZoneGlyph::Bar1: Add(0.0f, FVector::ZeroVector, 0.05f, 0.20f); break;
    case ES08ZoneGlyph::Bars2:  // ART-005 red
      for (const float O : {-6.0f, 6.0f}) Add(0.0f, FVector(O, 0, 0), 0.05f, 0.20f);
      break;
    case ES08ZoneGlyph::Bars3:
      for (const float O : {-10.0f, 0.0f, 10.0f}) Add(0.0f, FVector(O, 0, 0), 0.04f, 0.20f);
      break;
    case ES08ZoneGlyph::HBars2:
      for (const float O : {-6.0f, 6.0f}) Add(0.0f, FVector(0, O, 0), 0.20f, 0.05f);
      break;
    case ES08ZoneGlyph::Square: Add(0.0f, FVector::ZeroVector, 0.14f, 0.14f); break;
    case ES08ZoneGlyph::Cross:
      Add(0.0f, FVector::ZeroVector, 0.20f, 0.05f);
      Add(0.0f, FVector::ZeroVector, 0.05f, 0.20f);
      break;
    case ES08ZoneGlyph::X:
      Add(45.0f, FVector::ZeroVector, 0.22f, 0.05f);
      Add(-45.0f, FVector::ZeroVector, 0.22f, 0.05f);
      break;
    case ES08ZoneGlyph::Tee:
      Add(0.0f, FVector(0, -8, 0), 0.20f, 0.05f);
      Add(0.0f, FVector(0, 2, 0), 0.05f, 0.16f);
      break;
    case ES08ZoneGlyph::Chevron:  // '^' pointing to the far side; never an L (the reachable ticks are Ls)
      Add(-53.0f, FVector(-4.5f, 0, 0), 0.15f, 0.045f);
      Add(53.0f, FVector(4.5f, 0, 0), 0.15f, 0.045f);
      break;
    case ES08ZoneGlyph::Ring:
      Add(0.0f, FVector(0, -8, 0), 0.20f, 0.04f);
      Add(0.0f, FVector(0, 8, 0), 0.20f, 0.04f);
      Add(0.0f, FVector(-8, 0, 0), 0.04f, 0.20f);
      Add(0.0f, FVector(8, 0, 0), 0.04f, 0.20f);
      break;
  }
}
}  // namespace

void S08StrokePieces(ES08ZoneStroke Stroke, int32 Side, TArray<FTransform>& Out) {
  StrokePiecesAt(Stroke, Side, 0.0f, StrokeZ, StrokeDepth, Out);
}

void S08StrokeKeylinePieces(ES08ZoneStroke Stroke, int32 Side, TArray<FTransform>& Out) {
  StrokePiecesAt(Stroke, Side, KeylineGrowUU, StrokeKeylineZ, KeylineDepth, Out);
}

void S08GlyphPieces(ES08ZoneGlyph Glyph, int32 Slot, TArray<FTransform>& Out) {
  GlyphPiecesAt(Glyph, Slot, 0.0f, GlyphZ, GlyphDepth, Out);
}

void S08GlyphKeylinePieces(ES08ZoneGlyph Glyph, int32 Slot, TArray<FTransform>& Out) {
  GlyphPiecesAt(Glyph, Slot, KeylineGrowUU, GlyphZ, KeylineDepth, Out);
}

FVector S08GlyphAnchor(int32 Slot) {
  const FVector2D P2 = GlyphSlot(Slot);
  return FVector(P2.X, P2.Y, GlyphZ);
}

FS08ZoneMarkLayout S08BuildZoneMarks(const FS08BoardModel& Board, const FS08BoardArtData& Data) {
  FS08ZoneMarkLayout L;
  for (int32 Y = 0; Y < Board.Height; ++Y) {
    for (int32 X = 0; X < Board.Width; ++X) {
      const FS08Cell* Cell = Board.CellAt(X, Y);
      if (!Cell || Cell->Zones.Num() == 0) continue;
      const FVector World = Board.CellToWorld(X, Y);
      const bool bMulti = Cell->Zones.Num() >= 2;
      TArray<FString> Sides, Slots;
      int32 Marked = 0;
      for (int32 I = 0; I < Cell->Zones.Num(); ++I) {
        const FString& Key = Cell->Zones[I];
        const FS08ZoneStyle Style = Data.StyleFor(Key);
        if (Style.bFallback) L.FallbackKeys.AddUnique(Key);
        L.CellsByKey.FindOrAdd(Key) += 1;
        TArray<FTransform> Strokes, Glyphs, StrokeKeys, GlyphKeys;
        S08StrokePieces(Style.Stroke, I, Strokes);
        S08GlyphPieces(Style.Glyph, I, Glyphs);
        // W5b-R D-4 keylines (never counted in *PiecesByKey: the legacy Cobble trace stays byte-compatible)
        S08StrokeKeylinePieces(Style.Stroke, I, StrokeKeys);
        S08GlyphKeylinePieces(Style.Glyph, I, GlyphKeys);
        for (const FTransform& T : StrokeKeys) {
          FTransform W = T;
          W.SetTranslation(World + T.GetTranslation());
          L.StrokeKeylines.Add({Key, FIntPoint(X, Y), I, W});
        }
        for (const FTransform& T : GlyphKeys) {
          FTransform W = T;
          W.SetTranslation(World + T.GetTranslation());
          L.GlyphKeylines.Add({Key, FIntPoint(X, Y), I, W});
        }
        for (const FTransform& T : Strokes) {
          FTransform W = T;
          W.SetTranslation(World + T.GetTranslation());
          L.Strokes.Add({Key, FIntPoint(X, Y), I, W});
        }
        for (const FTransform& T : Glyphs) {
          FTransform W = T;
          W.SetTranslation(World + T.GetTranslation());
          L.Glyphs.Add({Key, FIntPoint(X, Y), I, W});
        }
        L.GlyphAnchors.Add({Key, FIntPoint(X, Y), I, FTransform(World + S08GlyphAnchor(I))});
        L.StrokePiecesByKey.FindOrAdd(Key) += Strokes.Num();
        L.GlyphPiecesByKey.FindOrAdd(Key) += Glyphs.Num();
        if (Strokes.Num() > 0 && Glyphs.Num() > 0) ++Marked;
        Sides.Add(FString::FromInt(I % 4));
        Slots.Add(FString::FromInt(I % 4));
      }
      if (bMulti) {
        ++L.MultizoneCells;
        L.MultizoneZonesListed += Cell->Zones.Num();
        L.MultizoneZonesMarked += Marked;
        L.MultizoneLines.Add(FString::Printf(TEXT("(%d,%d) %s strokeSides=%s glyphSlots=%s marked=%d/%d"),
                                             X, Y, *FString::Join(Cell->Zones, TEXT("+")),
                                             *FString::Join(Sides, TEXT("+")), *FString::Join(Slots, TEXT("+")),
                                             Marked, Cell->Zones.Num()));
      }
    }
  }
  return L;
}

TArray<FS08PlacedLight> S08PlaceLights(const FS08LightProfile& Profile, const FS08BoardModel& Board) {
  TArray<FS08PlacedLight> Out;
  auto Place = [&](const FS08LightSpec& Spec) {
    FS08PlacedLight P;
    P.Spec = Spec;
    P.Position = Spec.bHasPosUU
        ? Spec.PosUU
        : FVector(Spec.At.X * Board.Width * FS08BoardModel::CellSizeUU,
                  Spec.At.Y * Board.Height * FS08BoardModel::CellSizeUU, Spec.AtZ);
    Out.Add(P);
  };
  if (Profile.bHasDirectional) Place(Profile.Directional);
  for (const FS08LightSpec& Spec : Profile.Points) Place(Spec);
  return Out;
}

TArray<FS08PlacedLight> S08PlaceLights(const FS08LightProfile& Profile, const FVector2D& BoardSizeUU) {
  TArray<FS08PlacedLight> Out;
  auto Place = [&](const FS08LightSpec& Spec) {
    FS08PlacedLight P;
    P.Spec = Spec;
    P.Position = Spec.bHasPosUU ? Spec.PosUU
                                : FVector(Spec.At.X * BoardSizeUU.X, Spec.At.Y * BoardSizeUU.Y, Spec.AtZ);
    Out.Add(P);
  };
  if (Profile.bHasDirectional) Place(Profile.Directional);
  for (const FS08LightSpec& Spec : Profile.Points) Place(Spec);
  return Out;
}

// ---- ENV-MAPS track S --------------------------------------------------------------------------------------

FVector2D S08BoardHalfExtentUU(const FS08BoardModel& Board) {
  if (Board.bHasTopology) return Board.LayoutFrame.ExtentUU() * 0.5;
  // The grid value exactly as SetupCameraForBoard computed it before ENV-MAPS (float, same operation order).
  const float ExtentX = Board.Width * FS08BoardModel::CellSizeUU * 0.5f;
  const float ExtentY = Board.Height * FS08BoardModel::CellSizeUU * 0.5f;
  return FVector2D(ExtentX, ExtentY);
}

float S08K1FitDistanceUU(const FVector2D& HalfExtentUU) {
  // UE's FOVAngle is the HORIZONTAL fov: the vertical half-tan is the horizontal one divided by the aspect.
  const float Hfov = 35.0f;
  const float Aspect = 16.0f / 9.0f;
  const float HalfH = FMath::Tan(FMath::DegreesToRadians(Hfov * 0.5f));
  const float HalfV = HalfH / Aspect;
  const float ExtentY = static_cast<float>(HalfExtentUU.Y);
  const float ExtentX = static_cast<float>(HalfExtentUU.X);
  // Vertical screen span covers the board's Y extent tilted by the pitch.
  const float SinPitch = FMath::Sin(FMath::DegreesToRadians(55.0f));
  const float NeedV = (ExtentY * SinPitch + 60.0f) / HalfV;
  const float NeedH = (ExtentX + 60.0f) / HalfH;
  return FMath::Max(NeedV, NeedH) * 1.12f;
}

TArray<TPair<FIntPoint, FIntPoint>> S08BoardLinkPairs(const FS08BoardModel& Board) {
  TArray<TPair<FIntPoint, FIntPoint>> Out;
  if (!Board.bHasTopology) return Out;
  for (int32 Y = 0; Y < Board.Height; ++Y) {
    for (int32 X = 0; X < Board.Width; ++X) {
      const int32 Index = Y * Board.Width + X;
      for (const FIntPoint& N : Board.Neighbours(FIntPoint(X, Y))) {
        // each undirected link once: from the row-major smaller cell (Neighbours is symmetrised)
        if (N.Y * Board.Width + N.X > Index) Out.Add(TPair<FIntPoint, FIntPoint>(FIntPoint(X, Y), N));
      }
    }
  }
  Out.Sort([W = Board.Width](const TPair<FIntPoint, FIntPoint>& A, const TPair<FIntPoint, FIntPoint>& B) {
    const int32 A0 = A.Key.Y * W + A.Key.X, B0 = B.Key.Y * W + B.Key.X;
    if (A0 != B0) return A0 < B0;
    return A.Value.Y * W + A.Value.X < B.Value.Y * W + B.Value.X;
  });
  return Out;
}

FTransform S08MapPlaneTransform(const FVector2D& SizeUU, float Z) {
  // /Engine/BasicShapes/Plane spans +-50 uu in X and Y; scale 1 = 100 uu. Yaw 0: its X / Y axes are the world
  // X / Y (the MapPlaneUV test checks that UV (0,0) lands on (-X, -Y) and u runs along +X). Read from the UE 5.8
  // Plane.uasset LOD0 mesh description (2026-09-30, Oodle-decoded offline): local (-50,-50) -> uv (0,0),
  // (50,-50) -> (1,0), (-50,50) -> (0,1), (50,50) -> (1,1), normal +Z - u along +X, v along +Y, no rotation.
  return FTransform(FRotator::ZeroRotator, FVector(0.0, 0.0, Z), FVector(SizeUU.X / 100.0, SizeUU.Y / 100.0, 1.0));
}

FString S08MapImageMissingLine(const FString& Path) {
  return TEXT("ARTPREVIEW map-image missing ") + Path;
}

void S08RingPieces(float RadiusUU, float WidthUU, int32 Segments, float Z, float DepthScale, TArray<FTransform>& Out) {
  if (Segments < 3 || RadiusUU <= 0.0f || WidthUU <= 0.0f) return;
  const float Step = 360.0f / Segments;
  // Tangent pieces of the circumscribed polygon of the OUTER edge: adjacent pieces overlap at the inner edge
  // and meet at the outer corners, so the ring shows no gaps.
  const float Outer = RadiusUU + WidthUU * 0.5f;
  const float Length = 2.0f * Outer * FMath::Tan(FMath::DegreesToRadians(Step * 0.5f));
  for (int32 I = 0; I < Segments; ++I) {
    const float Angle = Step * I;
    const float Rad = FMath::DegreesToRadians(Angle);
    const FVector Centre(RadiusUU * FMath::Cos(Rad), RadiusUU * FMath::Sin(Rad), Z);
    // piece X = along the tangent (yaw Angle + 90), piece Y = radial width
    Out.Add(FTransform(FRotator(0.0f, Angle + 90.0f, 0.0f), Centre,
                       FVector(Length / 100.0f, WidthUU / 100.0f, DepthScale)));
  }
}

bool S08LinkBarTransform(const FVector& A, const FVector& B, float TrimUU, float WidthUU, float Z, float DepthScale,
                         FTransform& Out) {
  const FVector2D D(B.X - A.X, B.Y - A.Y);
  const double Dist = D.Size();
  const double Length = Dist - 2.0 * TrimUU;
  if (Length <= 1.0) return false;
  const FVector Mid((A.X + B.X) * 0.5, (A.Y + B.Y) * 0.5, Z);
  const double Yaw = FMath::RadiansToDegrees(FMath::Atan2(D.Y, D.X));
  Out = FTransform(FRotator(0.0, Yaw, 0.0), Mid, FVector(Length / 100.0, WidthUU / 100.0, DepthScale));
  return true;
}
