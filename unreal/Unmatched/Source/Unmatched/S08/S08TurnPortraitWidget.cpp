#include "S08TurnPortraitWidget.h"

#include "S08AnimatedIconWidget.h"
#include "S08ArtHudStyle.h"
#include "S08IconMotion.h"
#include "../S09/S09TurnHud.h"
#include "Blueprint/WidgetTree.h"
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

bool US08TurnPortraitWidget::Initialize() {
  const bool bFirst = Super::Initialize();
  if (!bFirst || !WidgetTree || WidgetTree->RootWidget) return bFirst;
  Panel = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(), TEXT("Panel"));
  Panel->SetBrushColor(GPortraitPanel);
  Panel->SetPadding(FMargin(8.0f, 6.0f, 12.0f, 6.0f));
  Panel->SetVisibility(ESlateVisibility::HitTestInvisible);  // never takes a click from the board or the HUD
  WidgetTree->RootWidget = Panel;

  UHorizontalBox* Row = WidgetTree->ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass(), TEXT("Row"));
  Panel->SetContent(Row);

  // avatar: the ring canvas (64 su), the round disc (window 21 u of 32) centred under it
  USizeBox* AvatarBox = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass(), TEXT("AvatarBox"));
  AvatarBox->SetWidthOverride(RingSu);
  AvatarBox->SetHeightOverride(RingSu);
  Avatar = WidgetTree->ConstructWidget<UOverlay>(UOverlay::StaticClass(), TEXT("Avatar"));
  AvatarBox->AddChild(Avatar);
  USizeBox* DiscBox = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass(), TEXT("DiscBox"));
  DiscBox->SetWidthOverride(DiscSu);
  DiscBox->SetHeightOverride(DiscSu);
  Disc = WidgetTree->ConstructWidget<UImage>(UImage::StaticClass(), TEXT("Disc"));
  FSlateBrush Round;
  Round.DrawAs = ESlateBrushDrawType::RoundedBox;  // default outline settings: half-height radius = a circle
  Round.ImageSize = FVector2D(DiscSu, DiscSu);
  Disc->SetBrush(Round);
  DiscBox->AddChild(Disc);
  UOverlaySlot* DiscSlot = Avatar->AddChildToOverlay(DiscBox);
  DiscSlot->SetHorizontalAlignment(HAlign_Center);
  DiscSlot->SetVerticalAlignment(VAlign_Center);
  MonogramText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("Monogram"));
  MonogramText->SetFont(PortraitFont(S08ArtHudFonts::CardTypeface, 18));
  MonogramText->SetColorAndOpacity(FSlateColor(GPortraitPanel.CopyWithNewOpacity(1.0f)));
  MonogramText->SetJustification(ETextJustify::Center);
  UOverlaySlot* MonoSlot = Avatar->AddChildToOverlay(MonogramText);
  MonoSlot->SetHorizontalAlignment(HAlign_Center);
  MonoSlot->SetVerticalAlignment(VAlign_Center);
  UHorizontalBoxSlot* AvatarSlot = Row->AddChildToHorizontalBox(AvatarBox);
  AvatarSlot->SetVerticalAlignment(VAlign_Center);
  AvatarSlot->SetPadding(FMargin(0.0f, 0.0f, 8.0f, 0.0f));

  UVerticalBox* Column = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), TEXT("Column"));
  UHorizontalBoxSlot* ColumnSlot = Row->AddChildToHorizontalBox(Column);
  ColumnSlot->SetVerticalAlignment(VAlign_Center);
  NameText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("Name"));
  NameText->SetFont(PortraitFont(TEXT("Bold"), 15));
  NameText->SetColorAndOpacity(FSlateColor(GPortraitText));
  Column->AddChildToVerticalBox(NameText);
  StatusText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("Status"));
  StatusText->SetFont(PortraitFont(S08ArtHudFonts::CardTypeface, 12));
  StatusText->SetColorAndOpacity(FSlateColor(GPortraitIdle));
  Column->AddChildToVerticalBox(StatusText);

  UHorizontalBox* Stats = WidgetTree->ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass(), TEXT("Stats"));
  UVerticalBoxSlot* StatsSlot = Column->AddChildToVerticalBox(Stats);
  StatsSlot->SetPadding(FMargin(0.0f, 2.0f, 0.0f, 0.0f));
  HeartIcon = CreateWidget<US08AnimatedIconWidget>(this, US08AnimatedIconWidget::StaticClass());
  if (HeartIcon && HeartIcon->SetIcon(TEXT("resource-hp-full"), SmallIconSu, GSmallTexturePx)) {
    HeartIcon->ShowAtRest();
    UHorizontalBoxSlot* HeartSlot = Stats->AddChildToHorizontalBox(HeartIcon);
    HeartSlot->SetVerticalAlignment(VAlign_Center);
  }
  HpText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("Hp"));
  HpText->SetFont(PortraitFont(S08ArtHudFonts::CardTypeface, 14));
  HpText->SetColorAndOpacity(FSlateColor(GPortraitText));
  UHorizontalBoxSlot* HpSlot = Stats->AddChildToHorizontalBox(HpText);
  HpSlot->SetVerticalAlignment(VAlign_Center);
  HpSlot->SetPadding(FMargin(3.0f, 0.0f, 12.0f, 0.0f));
  TrackerRow = WidgetTree->ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass(), TEXT("Tracker"));
  UHorizontalBoxSlot* TrackerSlot = Stats->AddChildToHorizontalBox(TrackerRow);
  TrackerSlot->SetVerticalAlignment(VAlign_Center);
  return bFirst;
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
  if (Disc) Disc->SetColorAndOpacity(TeamColor);
  if (RingIcon) RingIcon->SetTeamTint(TeamColor);  // the team variant of the ring (tint: team layers only)
}

void US08TurnPortraitWidget::SetHeroName(const FString& Name) {
  if (Name == HeroName) return;
  HeroName = Name;
  if (NameText) NameText->SetText(FText::FromString(Name));  // hero name: server data
  if (MonogramText) MonogramText->SetText(FText::FromString(S09TurnHud::Monogram(Name)));
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
