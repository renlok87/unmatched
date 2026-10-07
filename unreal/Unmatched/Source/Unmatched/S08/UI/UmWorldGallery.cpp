// VS-4 HB-45 / HB-46 / FX-38 review sheet - see UmWorldGallery.h.
#include "UmWorldGallery.h"

#include "../S08ArtHudViews.h"
#include "../S08ArtHudWidgets.h"
#include "../S08ArtLook.h"
#include "../S08BoardModel.h"
#include "UmHudTheme.h"
#include "UmWorldLayer.h"
#include "UmZoneBadges.h"
#include "Blueprint/WidgetTree.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/Image.h"
#include "Components/TextBlock.h"
#include "Dom/JsonObject.h"
#include "Engine/Texture2D.h"
#include "ImageUtils.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace UmWorldGallery {
const TCHAR* StateName(int32 State) {
  static const TCHAR* Names[StateCount] = {TEXT("tags-start"),   TEXT("tags-run-I"),   TEXT("hover-medusa"), TEXT("hover-harpy1"),
                                           TEXT("hover-arthur"), TEXT("hover-merlin"), TEXT("attack-medusa"), TEXT("zone-1"),
                                           TEXT("zone-2"),       TEXT("zone-3")};
  return State >= 0 && State < StateCount ? Names[State] : TEXT("?");
}
}  // namespace UmWorldGallery

namespace {
TSharedPtr<FJsonValue> UmWgJson(const TCHAR* RepoRel) {
  FString Text;
  TSharedPtr<FJsonValue> Root;
  const FString Path = FPaths::ConvertRelativePathToFull(FPaths::ProjectDir() / TEXT("../..") / RepoRel);
  if (FFileHelper::LoadFileToString(Text, *Path)) FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root);
  return Root;
}

struct FUmWgFigure {
  const TCHAR* Key;
  const TCHAR* Slug;
  bool bHero;
  const TCHAR* Label;
  int32 Start;
  int32 Run;
  int32 Max;
  const TCHAR* Attack;
  uint8 Team;
};
const FUmWgFigure Figures[] = {
    {TEXT("medusa"), TEXT("medusa"), true, TEXT("Medusa"), 16, 14, 16, TEXT("RANGED"), 0},
    {TEXT("harpy1"), TEXT("medusa"), false, TEXT("Harpies 1"), 1, 1, 1, TEXT("MELEE"), 0},
    {TEXT("harpy2"), TEXT("medusa"), false, TEXT("Harpies 2"), 1, 1, 1, TEXT("MELEE"), 0},
    {TEXT("harpy3"), TEXT("medusa"), false, TEXT("Harpies 3"), 1, 1, 1, TEXT("MELEE"), 0},
    {TEXT("arthur"), TEXT("king-arthur"), true, TEXT("King Arthur"), 18, 17, 18, TEXT("MELEE"), 1},
    {TEXT("merlin"), TEXT("king-arthur"), false, TEXT("Merlin"), 7, 7, 7, TEXT("RANGED"), 1}};

FS08BoardFighter UmWgFighter(const FUmWgFigure& F, bool bRun) {
  FS08BoardFighter B;
  B.Id = FString::Printf(TEXT("gallery-%s"), F.Key);
  B.HeroSlug = F.Slug;
  B.bIsHero = F.bHero;
  B.Label = F.Label;
  B.Name = F.Label;
  B.Health = bRun ? F.Run : F.Start;
  B.MaxHealth = F.Max;
  B.AttackType = F.Attack;
  B.X = 1;
  B.Y = 1;
  return B;
}

/** The HB-44 mockup canvas nearest to this one in panel size per window width: 1280x720 150 % (1.125 px/su at 1280) or
 *  1920x1080 100 % (1 px/su at 1920). 1080p 150 % takes the 720p 150 % layout, 720p 100 % the 1080p 100 % one. */
bool UmWgLayout720(const FVector2D& CanvasPx, float PxPerSu) {
  const double R = PxPerSu / FMath::Max(1.0, CanvasPx.X);
  return FMath::Abs(R - 1.125 / 1280.0) < FMath::Abs(R - 1.0 / 1920.0);
}

/** The HB-44 panel boxes of a state (kind -> px box) for the canvas: the boxes of the nearest mockup canvas
 *  (UmWgLayout720) scaled with the window width. */
TMap<FString, FBox2D> UmWgBoxes(const FString& Board, const FString& State, const FVector2D& CanvasPx, float PxPerSu) {
  TMap<FString, FBox2D> Out;
  const TSharedPtr<FJsonValue> Root = UmWgJson(TEXT("art/imagegen/hud-world-v1-codex/layout-measurements.json"));
  const TArray<TSharedPtr<FJsonValue>>* List = nullptr;
  if (!Root.IsValid() || !Root->TryGetArray(List)) return Out;
  const bool b720 = UmWgLayout720(CanvasPx, PxPerSu);
  const double K = CanvasPx.X / (b720 ? 1280.0 : 1920.0);
  for (const TSharedPtr<FJsonValue>& V : *List) {
    const TSharedPtr<FJsonObject> E = V->AsObject();
    const TSharedPtr<FJsonObject>* St = nullptr;
    const TArray<TSharedPtr<FJsonValue>>* Res = nullptr;
    FString Id;
    if (!E.IsValid() || E->GetStringField(TEXT("board")) != Board || !E->TryGetObjectField(TEXT("state"), St) ||
        !(*St)->TryGetStringField(TEXT("id"), Id) || Id != State || !E->TryGetArrayField(TEXT("resolution"), Res) || Res->Num() != 2) {
      continue;
    }
    if (FMath::RoundToInt((*Res)[0]->AsNumber()) != (b720 ? 1280 : 1920)) continue;
    for (const TSharedPtr<FJsonValue>& P : E->GetArrayField(TEXT("panels"))) {
      const TSharedPtr<FJsonObject> PO = P->AsObject();
      const TArray<TSharedPtr<FJsonValue>>& Box = PO->GetArrayField(TEXT("box"));
      if (Box.Num() != 4) continue;
      Out.Add(PO->GetStringField(TEXT("kind")), FBox2D(FVector2D(Box[0]->AsNumber(), Box[1]->AsNumber()) * K,
                                                       FVector2D(Box[2]->AsNumber(), Box[3]->AsNumber()) * K));
    }
    break;
  }
  return Out;
}

/** The space polygon of the HB-07 registration (px of the canvas): its centre and half width. */
bool UmWgSpace(const FString& Board, const FString& SpaceId, const FVector2D& CanvasPx, FVector2D& OutCentre, float& OutRadius) {
  const TSharedPtr<FJsonValue> Root = UmWgJson(TEXT("art/imagegen/hud-composition-v1-codex/masks.json"));
  const TSharedPtr<FJsonObject> Obj = Root.IsValid() ? Root->AsObject() : nullptr;
  const TSharedPtr<FJsonObject>* T = nullptr;
  const TSharedPtr<FJsonObject>* B = nullptr;
  const bool b720 = CanvasPx.X < 1500.0;
  if (!Obj.IsValid() || !Obj->TryGetObjectField(TEXT("topology_transforms"), T) ||
      !(*T)->TryGetObjectField(Board + (b720 ? TEXT("-1280x720") : TEXT("-1920x1080")), B)) {
    return false;
  }
  const double K = CanvasPx.X / (b720 ? 1280.0 : 1920.0);
  for (const TSharedPtr<FJsonValue>& S : (*B)->GetArrayField(TEXT("spaces"))) {
    const TSharedPtr<FJsonObject> SO = S->AsObject();
    if (SO->GetStringField(TEXT("id")) != SpaceId) continue;
    FBox2D Box(ForceInit);
    for (const TSharedPtr<FJsonValue>& P : SO->GetArrayField(TEXT("polygon_px"))) {
      const TArray<TSharedPtr<FJsonValue>>& XY = P->AsArray();
      if (XY.Num() >= 2) Box += FVector2D(XY[0]->AsNumber(), XY[1]->AsNumber()) * K;
    }
    if (!Box.bIsValid) return false;
    OutCentre = Box.GetCenter();
    OutRadius = static_cast<float>(0.5 * Box.GetSize().X);
    return true;
  }
  return false;
}

/** The figure boxes of the frame (HB-07 masks, + 4 px), canvas px. */
TArray<FS08ScreenRect> UmWgFigureRects(const FString& Board, const FVector2D& CanvasPx) {
  TArray<FS08ScreenRect> Out;
  const TSharedPtr<FJsonValue> Root = UmWgJson(TEXT("art/imagegen/hud-composition-v1-codex/masks.json"));
  const TSharedPtr<FJsonObject> Obj = Root.IsValid() ? Root->AsObject() : nullptr;
  const TSharedPtr<FJsonObject>* Polys = nullptr;
  const TArray<TSharedPtr<FJsonValue>>* List = nullptr;
  if (!Obj.IsValid() || !Obj->TryGetObjectField(TEXT("figure_polygons_1080p"), Polys) || !(*Polys)->TryGetArrayField(Board, List)) return Out;
  const double K = CanvasPx.X / 1920.0;
  for (const TSharedPtr<FJsonValue>& P : *List) {
    FBox2D B(ForceInit);
    for (const TSharedPtr<FJsonValue>& Pt : P->AsArray()) {
      const TArray<TSharedPtr<FJsonValue>>& XY = Pt->AsArray();
      if (XY.Num() >= 2) B += FVector2D(XY[0]->AsNumber(), XY[1]->AsNumber()) * K;
    }
    if (B.bIsValid) Out.Add(FS08ScreenRect(B.Min.X - 4.0, B.Min.Y - 4.0, B.Max.X + 4.0, B.Max.Y + 4.0));
  }
  return Out;
}

/** The zone keys of a space from the board topology fixture. */
TArray<FName> UmWgZones(const FString& Board, const FString& SpaceId) {
  TArray<FName> Out;
  const TSharedPtr<FJsonValue> Root = UmWgJson(*FString::Printf(TEXT("backend/prisma/fixtures/boards/%s.topology.json"), *Board));
  const TSharedPtr<FJsonObject> Obj = Root.IsValid() ? Root->AsObject() : nullptr;
  if (!Obj.IsValid()) return Out;
  for (const TSharedPtr<FJsonValue>& S : Obj->GetArrayField(TEXT("spaces"))) {
    const TSharedPtr<FJsonObject> SO = S->AsObject();
    if (SO->GetStringField(TEXT("id")) != SpaceId) continue;
    for (const TSharedPtr<FJsonValue>& Z : SO->GetArrayField(TEXT("zones"))) Out.Add(FName(*Z->AsString()));
  }
  return Out;
}

/** The disc colours of the board profile (Config/ArtBoards/S08ArtBoardProfiles.json boards[].zoneIconSrgb). */
TMap<FName, FColor> UmWgDiscs(const FString& Board) {
  TMap<FName, FColor> Out;
  FString Text;
  TSharedPtr<FJsonObject> Root;
  const FString Path = FPaths::Combine(FPaths::ProjectConfigDir(), TEXT("ArtBoards"), TEXT("S08ArtBoardProfiles.json"));
  if (!FFileHelper::LoadFileToString(Text, *Path) || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) || !Root.IsValid()) {
    return Out;
  }
  for (const TSharedPtr<FJsonValue>& B : Root->GetArrayField(TEXT("boards"))) {
    const TSharedPtr<FJsonObject> BO = B->AsObject();
    const TSharedPtr<FJsonObject>* Z = nullptr;
    if (BO->GetStringField(TEXT("id")) != Board + TEXT("-original") || !BO->TryGetObjectField(TEXT("zoneIconSrgb"), Z)) continue;
    for (const auto& Pair : (*Z)->Values) Out.Add(FName(*Pair.Key), FColor::FromHex(Pair.Value->AsString()));
  }
  return Out;
}
}  // namespace

bool UUmWorldGalleryWidget::Initialize() {
  const bool bFirst = Super::Initialize();
  if (bFirst && WidgetTree && !WidgetTree->RootWidget) {
    Root = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Root")));
    WidgetTree->RootWidget = Root;
  }
  return bFirst;
}

TArray<FString> UUmWorldGalleryWidget::Build(const FString& Board, const FVector2D& CanvasSu, float PxPerSu) {
  TArray<FString> Lines;
  if (!Root) return Lines;
  Root->ClearChildren();
  Tags.Reset();
  BoardNow = Board.ToLower();
  PxNow = PxPerSu > 0.0f ? PxPerSu : 1.0f;
  CanvasPx = CanvasSu * PxNow;
  const bool bSarpedon = BoardNow == TEXT("sarpedon");
  const FString Rel = bSarpedon ? TEXT("docs/game-design/evidence/ENV-MAPS/p10-sarpedon-rework-2026-10-03/sarpedon-packaged/bench-K1-1920x1080.png")
                                : TEXT("docs/game-design/evidence/ENV-MAPS/p7-concept-paste-2026-10-01/marmoreal-concept-flag/bench-K1-1920x1080.png");
  BackgroundTexture = FImageUtils::ImportFileAsTexture2D(FPaths::ConvertRelativePathToFull(FPaths::ProjectDir() / TEXT("../..") / Rel));
  Background = WidgetTree->ConstructWidget<UImage>(UImage::StaticClass(), FName(TEXT("Background")));
  if (BackgroundTexture) Background->SetBrushFromTexture(BackgroundTexture);
  if (UCanvasPanelSlot* S = Root->AddChildToCanvas(Background)) {
    S->SetAnchors(FAnchors(0.0f, 0.0f, 1.0f, 1.0f));
    S->SetOffsets(FMargin(0.0f));
  }
  UClass* TagClass = S08LoadArtHudWidgetClass(US08ArtTagWidget::WidgetBlueprintPath, US08ArtTagWidget::StaticClass());
  for (int32 I = 0; I < UE_ARRAY_COUNT(Figures); ++I) {
    US08ArtTagWidget* Tag = CreateWidget<US08ArtTagWidget>(this, TagClass ? TagClass : US08ArtTagWidget::StaticClass());
    if (!Tag) continue;
    UmWorldLayer::SetupTag(*Tag);
    if (UCanvasPanelSlot* S = Root->AddChildToCanvas(Tag)) {
      S->SetAutoSize(true);
      S->SetZOrder(10);
    }
    Tags.Add(Tag);
  }
  UClass* PlateClass = S08LoadArtHudWidgetClass(US08ArtPlateWidget::WidgetBlueprintPath, US08ArtPlateWidget::StaticClass());
  Plate = CreateWidget<US08ArtPlateWidget>(this, PlateClass ? PlateClass : US08ArtPlateWidget::StaticClass());
  if (Plate) {
    UmWorldLayer::SetupPlate(*Plate);
    if (UCanvasPanelSlot* S = Root->AddChildToCanvas(Plate)) {
      S->SetAutoSize(true);
      S->SetZOrder(30);
    }
    Plate->SetVisibility(ESlateVisibility::Collapsed);
  }
  Zones = CreateWidget<UUmZoneBadges>(this, UUmZoneBadges::StaticClass());
  if (Zones) {
    Zones->SetPxPerUnit(PxNow);
    if (UCanvasPanelSlot* S = Root->AddChildToCanvas(Zones)) {
      S->SetAnchors(FAnchors(0.0f, 0.0f, 1.0f, 1.0f));
      S->SetOffsets(FMargin(0.0f));
      S->SetZOrder(20);
    }
  }
  Label = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("Label")));
  Label->SetFont(UUmHudTheme::Get().Font(TEXT("type.caption")));
  Label->SetColorAndOpacity(FSlateColor(UUmHudTheme::Get().Color(TEXT("text.primary"))));
  if (UCanvasPanelSlot* S = Root->AddChildToCanvas(Label)) {
    S->SetAutoSize(true);
    S->SetPosition(FVector2D(16.0, CanvasSu.Y - 40.0));
  }
  StateNow = -1;
  Lines.Add(FString::Printf(TEXT("UMGALLERY world board=%s canvas=%.0fx%.0f pxPerSu=%.3f background=%s %s"), *BoardNow, CanvasSu.X,
                            CanvasSu.Y, PxPerSu, BackgroundTexture ? TEXT("bench-K1") : TEXT("none"), *UmWorldLayer::LookField()));
  return Lines;
}

void UUmWorldGalleryWidget::ApplyState(int32 State, TArray<FString>& Lines) {
  const FString Name = UmWorldGallery::StateName(State);
  const bool bRun = State >= 1;
  const FString LayoutState = State == 0 ? TEXT("tags-start") : State <= 1 || State >= 7 ? TEXT("tags-run-I") : Name;
  const TMap<FString, FBox2D> Boxes = UmWgBoxes(BoardNow, LayoutState, CanvasPx, PxNow);
  // the six tags at their HB-44 boxes (the left edge, centred on the box height)
  TArray<FS08ScreenRect> TagRects;
  for (int32 I = 0; I < Tags.Num() && I < UE_ARRAY_COUNT(Figures); ++I) {
    US08ArtTagWidget* Tag = Tags[I];
    const FUmWgFigure& F = Figures[I];
    const FS08BoardFighter B = UmWgFighter(F, bRun);
    FS08TagTexts T;
    T.Hp = UmWorldLayer::HpText(B.Health, B.MaxHealth);
    T.HpFraction = B.MaxHealth > 0 ? static_cast<float>(B.Health) / B.MaxHealth : 0.0f;
    T.TeamSlot = F.Team;
    UmWorldLayer::FillTagTexts(T, B);
    Tag->ApplyModel(T);
    const FBox2D* Box = Boxes.Find(FString::Printf(TEXT("tag.%s"), F.Key));
    Tag->SetVisibility(Box ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
    if (!Box) continue;
    // centred on the box: on the two mockup canvases the tag fills it, on the scaled ones it keeps the mockup centre
    Tag->ForceLayoutPrepass();
    const FVector2D Want = Tag->GetDesiredSize();
    const FVector2D D(Want.X > 0.0 ? Want.X : Box->GetSize().X / PxNow, Want.Y > 0.0 ? Want.Y : UmWorldLayer::TagHeightSu);
    const FVector2D Pos = Box->GetCenter() / PxNow - 0.5 * D;
    if (UCanvasPanelSlot* S = Cast<UCanvasPanelSlot>(Tag->Slot)) S->SetPosition(Pos);
    const FVector2D P0 = Pos * PxNow, P1 = (Pos + D) * PxNow;
    TagRects.Add(FS08ScreenRect(P0.X, P0.Y, P1.X, P1.Y));
    Lines.Add(FString::Printf(TEXT("UMGALLERY world tag=%s box=(%.0f,%.0f,%.0f,%.0f) layout=%s digit=%d hp=%d/%d"), F.Key, P0.X, P0.Y,
                              P1.X, P1.Y, UmWgLayout720(CanvasPx, PxNow) ? TEXT("720p150") : TEXT("1080p100"), T.HarpyDigit,
                              B.Health, B.MaxHealth));
  }
  // the plate: hover / attack states at the HB-44 plate box
  if (Plate) {
    const FBox2D* Box = Boxes.Find(State == 6 ? TEXT("plate.attack") : TEXT("plate.hover"));
    const TCHAR* Who = State == 2 ? TEXT("medusa") : State == 3 ? TEXT("harpy1") : State == 4 ? TEXT("arthur")
                     : State == 5 ? TEXT("merlin") : State == 6 ? TEXT("medusa") : nullptr;
    if (Who && Box) {
      for (const FUmWgFigure& F : Figures) {
        if (FCString::Strcmp(F.Key, Who) != 0) continue;
        const FS08BoardFighter B = UmWgFighter(F, bRun);
        FS08PlateTexts T;
        T.bOwn = F.Team == 0;
        T.TeamSlot = F.Team;
        T.Name = FText::FromString(B.Label.IsEmpty() ? B.Name : B.Label);  // the legacy plate (rollback) reads these
        T.Hp = UmWorldLayer::HpText(B.Health, B.MaxHealth);
        T.HpFraction = B.MaxHealth > 0 ? static_cast<float>(B.Health) / B.MaxHealth : 0.0f;
        UmWorldLayer::FillPlateTexts(T, B, T.bOwn, /*bTarget=*/State == 6);
        Plate->ApplyTexts(T);
      }
      const FVector2D D = Plate->IsV2() ? FVector2D(UmWorldLayer::PlateWSu, UmWorldLayer::PlateHSu) : Plate->Style.SizeSu;
      if (UCanvasPanelSlot* S = Cast<UCanvasPanelSlot>(Plate->Slot)) S->SetPosition(Box->GetCenter() / PxNow - 0.5 * D);
      Plate->SetShownAnimated(true);
      Plate->FinishFade();  // the sheet shows the state, not the 150 ms fade (the shot lands 4 frames after the switch)
      Lines.Add(FString::Printf(TEXT("UMGALLERY world plate=%s box=(%.0f,%.0f,%.0f,%.0f) target=%d"), Who, Box->Min.X, Box->Min.Y,
                                Box->Max.X, Box->Max.Y, State == 6 ? 1 : 0));
    } else {
      Plate->SetVisibility(ESlateVisibility::Collapsed);
    }
  }
  // FX-38: the zone icons at a hovered space of one, two and three zones (-S08SlateHud=zone: none, as the client)
  if (Zones) {
    FUmZoneBadgeInput In;
    In.ViewportPx = CanvasPx;
    const bool bZoneRollback = S08ArtLook::SlateHudBlocks().IsSlate(FName(TEXT("zone")));
    if (bZoneRollback && State >= 7) Lines.Add(TEXT("UMGALLERY world zone rollback=-S08SlateHud=zone"));
    if (State >= 7 && !bZoneRollback) {
      const bool bSar = BoardNow == TEXT("sarpedon");
      const TCHAR* Space = State == 7 ? (bSar ? TEXT("S01") : TEXT("M02")) : State == 8 ? (bSar ? TEXT("S21") : TEXT("M01"))
                                                                                         : (bSar ? TEXT("S25") : TEXT("M04"));
      FVector2D Centre;
      float Radius = 0.0f;
      if (UmWgSpace(BoardNow, Space, CanvasPx, Centre, Radius)) {
        In.bShow = true;
        In.SpaceId = Space;
        In.Keys = UmWgZones(BoardNow, Space);
        In.CentrePx = Centre;
        In.RadiusPx = Radius;
        In.AnchorPx = Radius * UmZoneBadges::AnchorUU / 42.0f;  // spaceRadiusPx 63 x uuPerPx 2/3 = 42 uu
        In.Avoid = UmWgFigureRects(BoardNow, CanvasPx);
        In.Avoid.Append(TagRects);
      }
    }
    const TMap<FName, FColor> Discs = UmWgDiscs(BoardNow);
    In.DiscColor = [Discs](FName K, FColor& Out) {
      const FColor* C = Discs.Find(K);
      if (C) Out = *C;
      return C != nullptr;
    };
    Zones->ApplyInput(In);
    Zones->CollectShotLines(Lines);
  }
}

TArray<FString> UUmWorldGalleryWidget::SetClockMs(float TMs) {
  TArray<FString> Lines;
  const int32 State = FMath::Clamp(FMath::FloorToInt(TMs / 1000.0f), 0, UmWorldGallery::StateCount - 1);
  if (State != StateNow) {
    StateNow = State;
    ApplyState(State, Lines);
    if (Label) {
      Label->SetText(FText::FromString(FString::Printf(TEXT("HB-45 / HB-46 / FX-38 sheet · %s · %s (review tooling, not an acceptance frame)"),
                                                       *BoardNow, UmWorldGallery::StateName(State))));
    }
  }
  Lines.Add(FString::Printf(TEXT("UMGALLERY world board=%s state=%d:%s t=%.0f"), *BoardNow, State, UmWorldGallery::StateName(State), TMs));
  return Lines;
}
