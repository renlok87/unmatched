#include "S08TurnPortraitWidget.h"

#include "S08AnimatedIconWidget.h"
#include "S08ArtHudStyle.h"
#include "S08ArtLook.h"
#include "S08HudTokens.generated.h"
#include "S08IconMotion.h"
#include "S08TraceLog.h"
#include "UI/UmCardMedia.h"
#include "UI/UmHudScale.h"
#include "UI/UmHudTheme.h"
#include "../S09/S09TurnHud.h"
#include "Blueprint/WidgetTree.h"
#include "Engine/Texture2D.h"
#include "Engine/World.h"
#include "HAL/PlatformTime.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/PackageName.h"
#include "Components/Border.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/Image.h"
#include "Components/Overlay.h"
#include "Components/OverlaySlot.h"
#include "Components/SizeBox.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "Misc/Parse.h"

namespace {
FLinearColor S08PortraitSrgb(uint8 R, uint8 G, uint8 B, float A = 1.0f) {
  FLinearColor C = FLinearColor::FromSRGBColor(FColor(R, G, B));
  C.A = A;
  return C;
}
/** tag.background #161A28 (the HUD panel of the gallery and the tags), a little transparent over the backdrop. */
const FLinearColor GPortraitPanel = S08PortraitSrgb(0x16, 0x1A, 0x28, 0.88f);
/** tag.text #F2ECDE. */
const FLinearColor GPortraitText = S08PortraitSrgb(0xF2, 0xEC, 0xDE);
/** turn.flash.yellow #F2C14E (STYLE-v3 §11) - the "your turn" accent; dim grey for "waiting". */
const FLinearColor GPortraitActive = S08PortraitSrgb(0xF2, 0xC1, 0x4E);
const FLinearColor GPortraitIdle = S08PortraitSrgb(0x9A, 0x9E, 0xAC);
/** Ring / tracker / heart texture sizes: exact-size v3 textures (24 / 32 / 48 / 64 px only). */
constexpr int32 GRingTexturePx = 64;
constexpr int32 GSmallTexturePx = 24;
constexpr int32 GTrackerTexturePx = 32;  // the action diamond reads small at 24 (gallery preview, DE-023)

FSlateFontInfo PortraitFont(const TCHAR* Typeface, int32 Size) { return FS08ArtHudFontToken(Typeface, Size).Resolve(); }
}  // namespace

// ------------------------------------------------------------------------------------------------- look

namespace {
/** A contract record the ring can play: appear + leave. */
bool RingRecordOk(const FString& Id) {
  const FS08IconMotionDef* Def = FS08IconMotionLibrary::Get().Find(FName(*Id));
  return Def && Def->FindAnim(TEXT("appear")) && Def->FindAnim(TEXT("leave"));
}
}  // namespace

FS08TurnHudLook FS08TurnHudLook::FromCommandLine(const TCHAR* CommandLine) {
  FS08TurnHudLook Out;
  const TCHAR* Cmd = CommandLine ? CommandLine : TEXT("");
  FString Ring = DefaultRingIcon;
  FString Chosen;
  if (FParse::Value(Cmd, TEXT("S08TurnRingIcon="), Chosen) && !Chosen.IsEmpty()) Ring = Chosen;
  if (FParse::Param(Cmd, RingLegacyFlag) || Ring.Equals(TEXT("none"), ESearchCase::IgnoreCase)) {
    Out.RingIcon = NAME_None;
  } else if (RingRecordOk(Ring)) {
    // the accepted ring, or a review choice of the A/B sheet (the team candidate comes from the command line only -
    // no candidate id is built into the client, test_candidates_are_gallery_only)
    Out.RingIcon = FName(*Ring);
  } else {
    Out.RingIcon = NAME_None;
    Out.Issues = FString::Printf(TEXT("ring '%s' refused (no such contract record with appear + leave)"), *Ring);
  }
  Out.bHeartGlow = !FParse::Param(Cmd, HeartGlowLegacyFlag);
  Out.bTrackerDe = !FParse::Param(Cmd, TrackerLegacyFlag);
  Out.bCrossGlyphs = !FParse::Param(Cmd, CrossLegacyFlag);
  return Out;
}

FString FS08TurnHudLook::Describe() const {
  return FString::Printf(TEXT("ring=%s heartGlow=%d tracker=%s cross=%d%s%s"),
                         RingIcon.IsNone() ? TEXT("none") : *RingIcon.ToString(), bHeartGlow ? 1 : 0,
                         bTrackerDe ? TEXT("de") : TEXT("v3"), bCrossGlyphs ? 1 : 0,
                         Issues.IsEmpty() ? TEXT("") : TEXT(" issues="),
                         Issues.IsEmpty() ? TEXT("") : *Issues.Replace(TEXT(" "), TEXT("_")));
}

FString FS08TurnHudLook::ArtLookField(const TCHAR* CommandLine) {
  const TCHAR* Cmd = CommandLine ? CommandLine : TEXT("");
  const FS08TurnHudLook Look = FromCommandLine(Cmd);
  auto Legacy = [](const TCHAR* Flag) { return FString::Printf(TEXT("legacy(-%s)"), Flag); };
  FString Ring;
  if (FParse::Param(Cmd, RingLegacyFlag)) {
    Ring = Legacy(RingLegacyFlag);
  } else if (Look.RingIcon.IsNone()) {
    Ring = Look.Issues.IsEmpty() ? FString(TEXT("none(-S08TurnRingIcon)")) : FString(TEXT("none(refused)"));
  } else {
    Ring = Look.RingIcon.ToString();
  }
  return FString::Printf(TEXT("hud=ring:%s,glow:%s,tracker:%s,cross:%s"), *Ring,
                         Look.bHeartGlow ? TEXT("on") : *Legacy(HeartGlowLegacyFlag),
                         Look.bTrackerDe ? TEXT("de") : *Legacy(TrackerLegacyFlag),
                         Look.bCrossGlyphs ? TEXT("on") : *Legacy(CrossLegacyFlag));
}

// ------------------------------------------------------------------------------------------------- widget

namespace {
template <typename T>
T* PortraitMake(UWidgetTree& Tree, const TCHAR* Name) {
  return Tree.ConstructWidget<T>(T::StaticClass(), FName(Name));
}

template <typename T>
T* PortraitFind(UWidgetTree* Tree, const TCHAR* Name) {
  return Tree ? Cast<T>(Tree->FindWidget(FName(Name))) : nullptr;
}

void PortraitAlign(UWidget* Widget, EHorizontalAlignment H, EVerticalAlignment V) {
  if (UOverlaySlot* OSlot = Cast<UOverlaySlot>(Widget->Slot)) {
    OSlot->SetHorizontalAlignment(H);
    OSlot->SetVerticalAlignment(V);
  }
}
}  // namespace

bool US08TurnPortraitWidget::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  auto Fail = [OutError](const TCHAR* What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), What);
    return false;
  };
  UBorder* PanelW = PortraitMake<UBorder>(Tree, TEXT("Panel"));
  PanelW->SetBrushColor(GPortraitPanel);
  PanelW->SetPadding(FMargin(8.0f, 6.0f, 12.0f, 6.0f));
  PanelW->SetVisibility(ESlateVisibility::HitTestInvisible);  // never takes a click from the board or the HUD
  if (!Attach(PanelW, nullptr)) return Fail(TEXT("Panel"));
  UHorizontalBox* Row = PortraitMake<UHorizontalBox>(Tree, TEXT("Row"));
  if (!Attach(Row, PanelW)) return Fail(TEXT("Row"));

  // avatar: the ring canvas (64 su), the round circle (window 21 u of 32) centred under it
  USizeBox* AvatarBox = PortraitMake<USizeBox>(Tree, TEXT("AvatarBox"));
  AvatarBox->SetWidthOverride(RingSu);
  AvatarBox->SetHeightOverride(RingSu);
  if (!Attach(AvatarBox, Row)) return Fail(TEXT("AvatarBox"));
  if (UHorizontalBoxSlot* AvatarSlot = Cast<UHorizontalBoxSlot>(AvatarBox->Slot)) {
    AvatarSlot->SetVerticalAlignment(VAlign_Center);
    AvatarSlot->SetPadding(FMargin(0.0f, 0.0f, 8.0f, 0.0f));
  }
  UOverlay* AvatarW = PortraitMake<UOverlay>(Tree, TEXT("Avatar"));
  if (!Attach(AvatarW, AvatarBox)) return Fail(TEXT("Avatar"));
  USizeBox* DiscBoxW = PortraitMake<USizeBox>(Tree, TEXT("DiscBox"));
  DiscBoxW->SetWidthOverride(DiscSu);
  DiscBoxW->SetHeightOverride(DiscSu);
  if (!Attach(DiscBoxW, AvatarW)) return Fail(TEXT("DiscBox"));
  PortraitAlign(DiscBoxW, HAlign_Center, VAlign_Center);
  UOverlay* Stack = PortraitMake<UOverlay>(Tree, TEXT("DiscStack"));
  if (!Attach(Stack, DiscBoxW)) return Fail(TEXT("DiscStack"));
  UImage* DiscW = PortraitMake<UImage>(Tree, TEXT("Disc"));
  FSlateBrush Round;
  Round.DrawAs = ESlateBrushDrawType::RoundedBox;  // default outline settings: half-height radius = a circle
  Round.ImageSize = FVector2D(DiscSu, DiscSu);
  DiscW->SetBrush(Round);
  if (!Attach(DiscW, Stack)) return Fail(TEXT("Disc"));
  PortraitAlign(DiscW, HAlign_Fill, VAlign_Fill);
  UImage* AvatarImageW = PortraitMake<UImage>(Tree, TEXT("AvatarImage"));
  AvatarImageW->SetVisibility(ESlateVisibility::Collapsed);  // until a registry PNG is applied (CP-08)
  if (!Attach(AvatarImageW, Stack)) return Fail(TEXT("AvatarImage"));
  PortraitAlign(AvatarImageW, HAlign_Fill, VAlign_Fill);
  UTextBlock* Mono = PortraitMake<UTextBlock>(Tree, TEXT("MonogramText"));
  Mono->SetFont(PortraitFont(S08ArtHudFonts::CardTypeface, 18));
  Mono->SetColorAndOpacity(FSlateColor(GPortraitPanel.CopyWithNewOpacity(1.0f)));
  Mono->SetJustification(ETextJustify::Center);
  if (!Attach(Mono, AvatarW)) return Fail(TEXT("MonogramText"));
  PortraitAlign(Mono, HAlign_Center, VAlign_Center);

  UVerticalBox* Column = PortraitMake<UVerticalBox>(Tree, TEXT("Column"));
  if (!Attach(Column, Row)) return Fail(TEXT("Column"));
  if (UHorizontalBoxSlot* ColumnSlot = Cast<UHorizontalBoxSlot>(Column->Slot)) ColumnSlot->SetVerticalAlignment(VAlign_Center);
  UTextBlock* Name = PortraitMake<UTextBlock>(Tree, TEXT("NameText"));
  Name->SetFont(PortraitFont(TEXT("Bold"), 15));
  Name->SetColorAndOpacity(FSlateColor(GPortraitText));
  if (!Attach(Name, Column)) return Fail(TEXT("NameText"));
  UTextBlock* Status = PortraitMake<UTextBlock>(Tree, TEXT("StatusText"));
  Status->SetFont(PortraitFont(S08ArtHudFonts::CardTypeface, 12));
  Status->SetColorAndOpacity(FSlateColor(GPortraitIdle));
  if (!Attach(Status, Column)) return Fail(TEXT("StatusText"));
  UHorizontalBox* StatsW = PortraitMake<UHorizontalBox>(Tree, TEXT("Stats"));
  if (!Attach(StatsW, Column)) return Fail(TEXT("Stats"));
  if (UVerticalBoxSlot* StatsSlot = Cast<UVerticalBoxSlot>(StatsW->Slot)) StatsSlot->SetPadding(FMargin(0.0f, 2.0f, 0.0f, 0.0f));
  UTextBlock* Hp = PortraitMake<UTextBlock>(Tree, TEXT("HpText"));
  Hp->SetFont(PortraitFont(S08ArtHudFonts::CardTypeface, 14));
  Hp->SetColorAndOpacity(FSlateColor(GPortraitText));
  if (!Attach(Hp, StatsW)) return Fail(TEXT("HpText"));
  if (UHorizontalBoxSlot* HpSlot = Cast<UHorizontalBoxSlot>(Hp->Slot)) {
    HpSlot->SetVerticalAlignment(VAlign_Center);
    HpSlot->SetPadding(FMargin(3.0f, 0.0f, 12.0f, 0.0f));
  }
  UHorizontalBox* Tracker = PortraitMake<UHorizontalBox>(Tree, TEXT("TrackerRow"));
  if (!Attach(Tracker, StatsW)) return Fail(TEXT("TrackerRow"));
  if (UHorizontalBoxSlot* TrackerSlot = Cast<UHorizontalBoxSlot>(Tracker->Slot)) TrackerSlot->SetVerticalAlignment(VAlign_Center);
  return true;
}

void US08TurnPortraitWidget::BindParts() {
  UWidgetTree* Tree = WidgetTree;
  if (!Panel) Panel = PortraitFind<UBorder>(Tree, TEXT("Panel"));
  if (!Avatar) Avatar = PortraitFind<UOverlay>(Tree, TEXT("Avatar"));
  if (!DiscBox) DiscBox = PortraitFind<USizeBox>(Tree, TEXT("DiscBox"));
  if (!Disc) Disc = PortraitFind<UImage>(Tree, TEXT("Disc"));
  if (!AvatarImage) AvatarImage = PortraitFind<UImage>(Tree, TEXT("AvatarImage"));
  if (!MonogramText) MonogramText = PortraitFind<UTextBlock>(Tree, TEXT("MonogramText"));
  if (!NameText) NameText = PortraitFind<UTextBlock>(Tree, TEXT("NameText"));
  if (!StatusText) StatusText = PortraitFind<UTextBlock>(Tree, TEXT("StatusText"));
  if (!Stats) Stats = PortraitFind<UHorizontalBox>(Tree, TEXT("Stats"));
  if (!HpText) HpText = PortraitFind<UTextBlock>(Tree, TEXT("HpText"));
  if (!TrackerRow) TrackerRow = PortraitFind<UHorizontalBox>(Tree, TEXT("TrackerRow"));
}

bool US08TurnPortraitWidget::Initialize() {
  const bool bFirst = Super::Initialize();
  if (!bFirst || !WidgetTree) return bFirst;
  if (!WidgetTree->RootWidget) {
    FString Error;
    UWidgetTree* Tree = WidgetTree;
    bCodeDefaultTree = BuildDefaultTree(*Tree, [Tree](UWidget* Child, UPanelWidget* Parent) {
      if (!Parent) {
        Tree->RootWidget = Child;
        return true;
      }
      return Parent->AddChild(Child) != nullptr;
    }, &Error);
    if (!bCodeDefaultTree) UE_LOG(LogTemp, Error, TEXT("PORTRAIT default tree: %s"), *Error);
  }
  BindParts();
  if (Panel) Panel->SetVisibility(ESlateVisibility::HitTestInvisible);
  // the fonts again at runtime: an FCoreStyle font (a composite font held in code) does not survive the WBP's
  // serialization - WBP_UmPortrait would draw tofu otherwise
  if (NameText) NameText->SetFont(PortraitFont(TEXT("Bold"), 15));
  if (StatusText) StatusText->SetFont(PortraitFont(S08ArtHudFonts::CardTypeface, 12));
  if (HpText) HpText->SetFont(PortraitFont(S08ArtHudFonts::CardTypeface, 14));
  // the heart: an animated v3 icon added in code, before the hp text
  if (Stats && !HeartIcon) {
    HeartIcon = CreateWidget<US08AnimatedIconWidget>(this, US08AnimatedIconWidget::StaticClass());
    if (HeartIcon && HeartIcon->SetIcon(TEXT("resource-hp-full"), SmallIconSu, GSmallTexturePx)) {
      HeartIcon->ShowAtRest();
      Stats->InsertChildAt(0, HeartIcon);
      if (UHorizontalBoxSlot* HeartSlot = Cast<UHorizontalBoxSlot>(HeartIcon->Slot)) HeartSlot->SetVerticalAlignment(VAlign_Center);
    } else {
      HeartIcon = nullptr;
    }
  }
  ApplyPortraitLook();
  return bFirst;
}

US08TurnPortraitWidget* US08TurnPortraitWidget::Create(UWorld* World, FString* OutSource) {
  if (!World) return nullptr;
  UClass* Class = US08TurnPortraitWidget::StaticClass();
  FString Source = TEXT("code-default");
  const FString Package = UmPortrait::WidgetBlueprintPath;
  if (FPackageName::DoesPackageExist(Package)) {
    const FString ClassPath = Package + TEXT(".") + FPackageName::GetShortName(Package) + TEXT("_C");
    if (UClass* Wbp = LoadClass<US08TurnPortraitWidget>(nullptr, *ClassPath, nullptr, LOAD_NoWarn | LOAD_Quiet)) {
      Class = Wbp;
      Source = Package;
    }
  }
  if (OutSource) *OutSource = Source;
  return CreateWidget<US08TurnPortraitWidget>(World, Class);
}

bool US08TurnPortraitWidget::HasAllParts(FString* OutMissing) const {
  TArray<FString> Missing;
  if (!Panel) Missing.Add(TEXT("Panel"));
  if (!Avatar) Missing.Add(TEXT("Avatar"));
  if (!DiscBox) Missing.Add(TEXT("DiscBox"));
  if (!Disc) Missing.Add(TEXT("Disc"));
  if (!AvatarImage) Missing.Add(TEXT("AvatarImage"));
  if (!MonogramText) Missing.Add(TEXT("MonogramText"));
  if (!NameText) Missing.Add(TEXT("NameText"));
  if (!StatusText) Missing.Add(TEXT("StatusText"));
  if (!Stats) Missing.Add(TEXT("Stats"));
  if (!HpText) Missing.Add(TEXT("HpText"));
  if (!TrackerRow) Missing.Add(TEXT("TrackerRow"));
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

// ------------------------------------------------------------------------------------------------- portrait (CP-08)

bool US08TurnPortraitWidget::PortraitLegacy() const {
  return LegacyOverride >= 0 ? LegacyOverride == 1 : !S08ArtLook::PortraitAvatars();
}

float US08TurnPortraitWidget::PxPerSuNow() const {
  if (PxPerSuOverride > 0.0f) return PxPerSuOverride;
  const FUmHudScaleState& Scale = UmHudScale::Current();
  return Scale.Window.X > 0 ? Scale.PxPerSu() : 1.0f;
}

FString US08TurnPortraitWidget::GetMonogram() const { return UmPortrait::FallbackText(PortraitKey, HeroName, PortraitSidekick); }

void US08TurnPortraitWidget::SetPortrait(FName Key, int32 SidekickNumber) {
  bPortraitKeyExplicit = true;
  if (bPortraitApplied && Key == PortraitKey && SidekickNumber == PortraitSidekick) return;
  PortraitKey = Key;
  PortraitSidekick = SidekickNumber;
  ApplyPortraitLook();
}

void US08TurnPortraitWidget::ApplyPortraitLook() {
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  const bool bLegacy = PortraitLegacy();
  const FUmCardMediaEntry* Entry = bLegacy ? nullptr : UmPortrait::Find(PortraitKey);
  UTexture2D* Tex = Entry ? UmCardMedia::LoadTexture(*Entry) : nullptr;
  UMaterialInterface* Mat =
      Tex ? LoadObject<UMaterialInterface>(nullptr, UmPortrait::MaterialPath, nullptr, LOAD_NoWarn | LOAD_Quiet) : nullptr;
  bAvatarShown = Tex && Mat && AvatarImage;
  if (!bLegacy && !bAvatarShown && !PortraitKey.IsNone() && !WarnedKeys.Contains(PortraitKey)) {
    // 02 §6.4: the monogram is only the fallback, and it says so in the log
    WarnedKeys.Add(PortraitKey);
    UE_LOG(LogTemp, Warning, TEXT("PORTRAIT fallback id=%s reason=%s"), *PortraitKey.ToString(),
           !Entry ? TEXT("no-registry-entry") : !Tex ? TEXT("texture-missing") : !Mat ? TEXT("material-missing") : TEXT("no-image"));
  }
  AppliedPxPerSu = PxPerSuNow();
  SrcCirclePx = Entry ? UmPortrait::SourceCirclePx(*Entry) : 0.0f;
  CircleSu = bAvatarShown ? UmPortrait::CappedSu(DiscSu, SrcCirclePx, AppliedPxPerSu) : DiscSu;
  if (DiscBox) {
    DiscBox->SetWidthOverride(CircleSu);
    DiscBox->SetHeightOverride(CircleSu);
  }
  if (bAvatarShown) {
    if (!AvatarMid || AvatarMid->Parent != Mat) AvatarMid = UMaterialInstanceDynamic::Create(Mat, this);
    AvatarMid->SetTextureParameterValue(UmPortrait::ParamAvatar, Tex);
    const FVector4 R = UmPortrait::UvRect(*Entry);
    AvatarMid->SetVectorParameterValue(UmPortrait::ParamUvRect, FLinearColor(R.X, R.Y, R.Z, R.W));
    FLinearColor Edge = Theme.Color(TEXT("panel.edge"));
    Edge.A = S08HudTokens::Alpha_PanelEdge;  // the rim keeps the token's alpha over panel.bg (4.0 : 1)
    AvatarMid->SetVectorParameterValue(UmPortrait::ParamEdgeColor, Edge);
    AvatarMid->SetVectorParameterValue(UmPortrait::ParamKeylineColor, Theme.Color(TEXT("mark.keyline")));
    AvatarMid->SetVectorParameterValue(UmPortrait::ParamFillColor, Theme.Color(TEXT("card.navy")));
    AvatarMid->SetScalarParameterValue(UmPortrait::ParamEdgeFrac, UmPortrait::EdgeSu / FMath::Max(CircleSu, 1.0f));
    AvatarMid->SetScalarParameterValue(UmPortrait::ParamKeylineFrac, UmPortrait::KeylineSu / FMath::Max(CircleSu, 1.0f));
    FSlateBrush Brush;
    Brush.SetResourceObject(AvatarMid);
    Brush.ImageSize = FVector2D(CircleSu, CircleSu);
    AvatarImage->SetBrush(Brush);
    AvatarImage->SetVisibility(ESlateVisibility::HitTestInvisible);
    AvatarTexture = Tex;
    AvatarPath = Entry->ObjectPath;
    if (Disc) Disc->SetVisibility(ESlateVisibility::Collapsed);
    if (MonogramText) MonogramText->SetVisibility(ESlateVisibility::Collapsed);
  } else {
    if (AvatarImage) AvatarImage->SetVisibility(ESlateVisibility::Collapsed);
    AvatarTexture = nullptr;
    AvatarPath.Reset();
    if (Disc) {
      Disc->SetVisibility(ESlateVisibility::HitTestInvisible);
      // the fallback disc is card.navy (no team colour on a portrait, 02 §6.4); the rollback keeps the team disc
      Disc->SetColorAndOpacity(bLegacy ? LastTeamColor : Theme.Color(TEXT("card.navy")));
    }
    if (MonogramText) {
      MonogramText->SetVisibility(ESlateVisibility::HitTestInvisible);
      MonogramText->SetText(FText::FromString(GetMonogram()));
      if (bLegacy) {
        MonogramText->SetFont(PortraitFont(S08ArtHudFonts::CardTypeface, 18));
        MonogramText->SetColorAndOpacity(FSlateColor(GPortraitPanel.CopyWithNewOpacity(1.0f)));
      } else {
        MonogramText->SetFont(Theme.Font(TEXT("type.heading")));
        MonogramText->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("text.primary"))));
      }
    }
  }
  ApplyStateParams();
  const bool bChanged = !bPortraitApplied || PortraitShotLine() != LastPortraitLine;
  bPortraitApplied = true;
  if (bChanged) {
    LastPortraitLine = PortraitShotLine();
    if (FS08Trace::IsOpen()) FS08Trace::Write(LastPortraitLine);
  }
}

void US08TurnPortraitWidget::SetPortraitState(EUmPortraitState State, bool bAnimate) {
  if (State == PortraitState) return;
  const bool bFade = bAnimate && State == EUmPortraitState::Loser && !S08IconMotion::IsReducedMotion();
  PortraitState = State;
  StateStart = bFade ? FPlatformTime::Seconds() : -1.0;
  ApplyStateParams();
}

void US08TurnPortraitWidget::ApplyStateParams() {
  float Desat = UmPortrait::Desaturation(PortraitState);
  float Op = UmPortrait::Opacity(PortraitState);
  if (StateStart >= 0.0) {
    // 04 §1.10: saturation 1 -> 0 and opacity 1 -> 0.6 over 400 ms, with the modal's entry
    const float T = static_cast<float>((FPlatformTime::Seconds() - StateStart) * 1000.0 / UmPortrait::LoserMs);
    if (T < 1.0f) {
      Desat = FMath::Lerp(0.0f, Desat, T);
      Op = FMath::Lerp(1.0f, Op, T);
    } else {
      StateStart = -1.0;
    }
  }
  if (AvatarMid) {
    AvatarMid->SetScalarParameterValue(UmPortrait::ParamDesaturation, Desat);
    AvatarMid->SetScalarParameterValue(UmPortrait::ParamOpacity, Op);
  }
  if (Disc) Disc->SetRenderOpacity(Op);
  if (MonogramText) MonogramText->SetRenderOpacity(Op);
}

void US08TurnPortraitWidget::NativeTick(const FGeometry& MyGeometry, float InDeltaTime) {
  Super::NativeTick(MyGeometry, InDeltaTime);
  if (StateStart >= 0.0) ApplyStateParams();
  // the ВР-CP04 cap follows a window / UI-scale change (no work otherwise)
  if (bPortraitApplied && bAvatarShown && !FMath::IsNearlyEqual(PxPerSuNow(), AppliedPxPerSu, 1.0e-3f)) ApplyPortraitLook();
}

FString US08TurnPortraitWidget::PortraitShotLine(const TCHAR* Show) const {
  const FString Tex = bAvatarShown ? AvatarPath : (PortraitLegacy() ? FString(TEXT("legacy")) : FString(TEXT("monogram")));
  return UmPortrait::TraceLine(PortraitKey, Tex, CircleSu, AppliedPxPerSu, SrcCirclePx, Show,
                               bOpponent ? TEXT("opp") : TEXT("own"), PortraitState);
}

void US08TurnPortraitWidget::Setup(bool bInOpponent, const FS08TurnHudLook& InLook, const FLinearColor& TeamColor) {
  bOpponent = bInOpponent;
  Look = InLook;
  if (HeartIcon) HeartIcon->SetLayerHidden(TEXT("glow"), !Look.bHeartGlow);
  if (!Look.RingIcon.IsNone() && Avatar && !RingIcon) {
    RingIcon = CreateWidget<US08AnimatedIconWidget>(this, US08AnimatedIconWidget::StaticClass());
    if (RingIcon && RingIcon->SetIcon(Look.RingIcon, RingSu, GRingTexturePx)) {
      UOverlaySlot* RingSlot = Avatar->AddChildToOverlay(RingIcon);
      RingSlot->SetHorizontalAlignment(HAlign_Center);
      RingSlot->SetVerticalAlignment(VAlign_Center);
    } else {
      RingIcon = nullptr;
    }
  }
  SetTeamColor(TeamColor);
  SetActive(false);
}

void US08TurnPortraitWidget::SetTeamColor(const FLinearColor& TeamColor) {
  // fed every frame by the game mode: touch the widgets only on a change (no per-frame invalidation)
  if (bTeamColorSet && TeamColor.Equals(LastTeamColor)) return;
  bTeamColorSet = true;
  LastTeamColor = TeamColor;
  // CP-08: the team colour is the rollback's disc only (-S08PortraitLegacy); the avatar and the fallback have none
  if (Disc && PortraitLegacy()) Disc->SetColorAndOpacity(TeamColor);
  if (RingIcon) RingIcon->SetTeamTint(TeamColor);  // the team variant of the ring (tint: team layers only)
}

void US08TurnPortraitWidget::SetHeroName(const FString& Name) {
  if (Name == HeroName) return;
  HeroName = Name;
  if (NameText) NameText->SetText(FText::FromString(Name));  // hero name: server data
  // CP-08: without an explicit key (SetPortrait from the hero slug) the name's slug picks the portrait
  if (!bPortraitKeyExplicit) {
    const FString Slug = UmPortrait::SlugOf(Name);
    PortraitKey = Slug.IsEmpty() ? FName(NAME_None) : FName(*Slug);
  }
  ApplyPortraitLook();
}

void US08TurnPortraitWidget::SetHealth(int32 Health, int32 MaxHealth) {
  if (!HpText || (Health == LastHealth && MaxHealth == LastMaxHealth)) return;
  LastHealth = Health;
  LastMaxHealth = MaxHealth;
  HpText->SetText(FText::FromString(MaxHealth > 0 ? FString::Printf(TEXT("%d/%d"), FMath::Max(Health, 0), MaxHealth)
                                                  : FString::Printf(TEXT("%d"), FMath::Max(Health, 0))));
}

void US08TurnPortraitWidget::SetActive(bool bInActive) {
  bActive = bInActive;
  if (!StatusText) return;
  // 02-ux-ui-spec §4.3: the accent "your turn" / "opponent's turn" - the text carries it, not the colour alone
  const TCHAR* Text = bActive ? (bOpponent ? TEXT("THEIR TURN") : TEXT("YOUR TURN")) : TEXT("waiting");
  StatusText->SetText(FText::FromString(Text));
  StatusText->SetColorAndOpacity(FSlateColor(bActive ? GPortraitActive : GPortraitIdle));
}

bool US08TurnPortraitWidget::PlayHeart(FName Anim) { return HeartIcon && !Anim.IsNone() && HeartIcon->PlayAnim(Anim); }

void US08TurnPortraitWidget::PlayRing(bool bAtRest) {
  if (!RingIcon) return;
  bRingShown = true;
  if (bAtRest) {
    RingIcon->ShowAtRest();
  } else {
    // a fresh animator: the previous turn's leave must not linger under the new flash
    RingIcon->SetReducedMotion(RingIcon->IsReducedMotion());
    RingIcon->PlayAnim(TEXT("appear"));
  }
}

void US08TurnPortraitWidget::StopRing() {
  if (!RingIcon || !bRingShown) return;
  bRingShown = false;
  RingIcon->PlayAnim(TEXT("leave"));
}

namespace {
/** The DE slot's fill: body / glyph layers from the accepted action-<type> icon. */
bool FillSlot(US08AnimatedIconWidget& Icon, FName Type) {
  if (Type.IsNone()) return false;
  const FString Base = FString::Printf(TEXT("action-%s"), *Type.ToString());
  if (!FS08IconMotionLibrary::Get().Find(FName(*Base))) return false;
  const bool bBody = Icon.SetLayerSource(TEXT("body"), Base + TEXT("_body"));
  const bool bGlyph = Icon.SetLayerSource(TEXT("glyph"), Base + TEXT("_glyph"));
  return bBody && bGlyph;
}
}  // namespace

FString US08TurnPortraitWidget::ApplyTracker(int32 Slots, int32 Shown, bool bReset, const TArray<FName>& Types) {
  Slots = FMath::Clamp(Slots, 0, 6);
  Shown = FMath::Clamp(Shown, 0, Slots);
  const bool bDe = Look.bTrackerDe;
  // AB-7: the DE slot plays fill / unfill (held) where the v3 slot plays spend / gain; the game events are the same
  const FName SpendAnim(bDe ? TEXT("fill") : TEXT("spend"));
  const FName GainAnim(bDe ? TEXT("unfill") : TEXT("gain"));
  auto TypeOf = [&Types](int32 I) { return Types.IsValidIndex(I) ? Types[I] : FName(NAME_None); };
  auto Fill = [&](int32 I) {
    if (!bDe || !TrackerIcons.IsValidIndex(I)) return;
    const FName Type = TypeOf(I);
    if (!Type.IsNone() && TrackerFill.IsValidIndex(I) && TrackerFill[I] != Type && FillSlot(*TrackerIcons[I], Type)) {
      TrackerFill[I] = Type;
    }
  };
  bool bRebuilt = false;
  if (TrackerRow && Slots != TrackerIcons.Num()) {
    // a GAIN_ACTION adds a slot (FS09ActionTracker), a new turn goes back to two: rebuild, poses snap below
    while (TrackerIcons.Num() > Slots) {
      TrackerIcons.Last()->RemoveFromParent();
      TrackerIcons.Pop();
      TrackerFill.Pop();
    }
    while (TrackerIcons.Num() < Slots) {
      US08AnimatedIconWidget* Icon = CreateWidget<US08AnimatedIconWidget>(this, US08AnimatedIconWidget::StaticClass());
      if (!Icon || !Icon->SetIcon(Look.TrackerIcon(), TrackerIconSu, GTrackerTexturePx)) break;
      UHorizontalBoxSlot* IconSlot = TrackerRow->AddChildToHorizontalBox(Icon);
      IconSlot->SetVerticalAlignment(VAlign_Center);
      IconSlot->SetPadding(FMargin(1.0f, 0.0f));
      TrackerIcons.Add(Icon);
      TrackerFill.Add(NAME_None);
      const int32 I = TrackerIcons.Num() - 1;
      if (I < TrackerShown) Fill(I);
      Icon->ShowAtRest(I < TrackerShown ? SpendAnim : FName(NAME_None));
    }
    bRebuilt = true;
  }
  Shown = FMath::Min(Shown, TrackerIcons.Num());
  if (bReset) {
    for (int32 I = 0; I < TrackerIcons.Num(); ++I) {
      if (I < Shown) Fill(I);
      TrackerIcons[I]->ShowAtRest(I < Shown ? SpendAnim : FName(NAME_None));
    }
    TrackerShown = Shown;
    return TEXT("reset");
  }
  if (Shown == TrackerShown) return bRebuilt ? TEXT("slots") : TEXT("");
  const bool bSpend = Shown > TrackerShown;
  // 01 F-12: the slot of the action being chosen is marked now (spend, 150 ms, held; DE: filled with its type,
  // 300 ms); a cancel gives it back (gain / unfill)
  for (int32 I = FMath::Min(Shown, TrackerShown); I < FMath::Max(Shown, TrackerShown); ++I) {
    if (!TrackerIcons.IsValidIndex(I)) continue;
    if (bSpend) Fill(I);
    TrackerIcons[I]->PlayAnim(bSpend ? SpendAnim : GainAnim);
  }
  TrackerShown = Shown;
  return bSpend ? TEXT("spend") : TEXT("gain");
}

FString US08TurnPortraitWidget::GetTrackerFill(int32 Index) const {
  if (!Look.bTrackerDe || !TrackerFill.IsValidIndex(Index) || TrackerFill[Index].IsNone()) return FString();
  return TrackerFill[Index].ToString();
}

bool US08TurnPortraitWidget::SetHeartFallen(bool bFallen, bool bAtRest) {
  if (!HeartIcon || !Look.bCrossGlyphs || bFallen == bHeartFallen) return false;
  bHeartFallen = bFallen;
  SetPortraitState(bFallen ? EUmPortraitState::Fallen : EUmPortraitState::Avatar, false);  // CP-08: saturation 0
  if (bFallen) {
    // AB-8 (SD-38, the Codex form): the blackened heart, the small cross stamps in (appear 200 ms)
    if (!HeartIcon->SetIcon(FS08TurnHudLook::FallenHeartIcon, SmallIconSu, GSmallTexturePx)) {
      bHeartFallen = false;
      return false;
    }
    if (bAtRest) {
      HeartIcon->ShowAtRest();
    } else {
      HeartIcon->PlayAnim(TEXT("appear"));
    }
  } else {
    HeartIcon->SetIcon(TEXT("resource-hp-full"), SmallIconSu, GSmallTexturePx);
    HeartIcon->ShowAtRest();
  }
  return true;
}

void US08TurnPortraitWidget::SetClockOverrideMs(float Ms) {
  if (RingIcon) RingIcon->SetClockOverrideMs(Ms);
  if (HeartIcon) HeartIcon->SetClockOverrideMs(Ms);
  for (US08AnimatedIconWidget* Icon : TrackerIcons) {
    if (Icon) Icon->SetClockOverrideMs(Ms);
  }
}

void US08TurnPortraitWidget::SetTrackerOpacity(float Alpha) {
  if (!TrackerRow) return;
  const float A = FMath::Clamp(Alpha, 0.0f, 1.0f);
  if (!FMath::IsNearlyEqual(TrackerRow->GetRenderOpacity(), A, 1.0e-3f)) TrackerRow->SetRenderOpacity(A);
  const ESlateVisibility Vis = A > 0.0f ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Hidden;
  if (TrackerRow->GetVisibility() != Vis) TrackerRow->SetVisibility(Vis);
}
