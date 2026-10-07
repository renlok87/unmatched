// VS-4 H12 (HB-45, HB-46): the world layer on the HUD tokens - see UmWorldLayer.h.
#include "UmWorldLayer.h"

#include "../S08ArtHudText.h"
#include "../S08ArtHudWidgets.h"
#include "../S08ArtLook.h"
#include "../S08BoardModel.h"
#include "../S08HeroesV2.h"
#include "../S08IconMotion.h"
#include "../../S09/S09ManeuverUi.h"
#include "Misc/CommandLine.h"
#include "UmCardMedia.h"
#include "UmHudScale.h"
#include "UmTeamChip.h"
#include "UmHudTheme.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Components/Border.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/Image.h"
#include "Components/Overlay.h"
#include "Components/OverlaySlot.h"
#include "Components/SizeBox.h"
#include "Components/SizeBoxSlot.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "Dom/JsonObject.h"
#include "Engine/Texture2D.h"
#include "HAL/PlatformTime.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace {
template <typename T>
T* UmWlMake(UWidgetTree& Tree, const TCHAR* Name) {
  return Tree.ConstructWidget<T>(T::StaticClass(), FName(Name));
}

UTextBlock* UmWlText(UWidgetTree& Tree, const TCHAR* Name, FName Type, FName Color) {
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  UTextBlock* T = UmWlMake<UTextBlock>(Tree, Name);
  T->SetFont(Theme.Font(Type));
  T->SetColorAndOpacity(FSlateColor(Theme.Color(Color)));
  T->SetShadowOffset(FVector2D::ZeroVector);
  return T;
}

void UmWlH(UWidget* W, float Left, EVerticalAlignment V = VAlign_Center) {
  if (UHorizontalBoxSlot* S = W ? Cast<UHorizontalBoxSlot>(W->Slot) : nullptr) {
    S->SetSize(FSlateChildSize(ESlateSizeRule::Automatic));
    S->SetPadding(FMargin(Left, 0.0f, 0.0f, 0.0f));
    S->SetHorizontalAlignment(HAlign_Left);
    S->SetVerticalAlignment(V);
  }
}

void UmWlV(UWidget* W, float Top) {
  if (UVerticalBoxSlot* S = W ? Cast<UVerticalBoxSlot>(W->Slot) : nullptr) {
    S->SetSize(FSlateChildSize(ESlateSizeRule::Automatic));
    S->SetPadding(FMargin(0.0f, Top, 0.0f, 0.0f));
    S->SetHorizontalAlignment(HAlign_Left);
  }
}

FSlateBrush UmWlPlain() {
  FSlateBrush B;
  B.DrawAs = ESlateBrushDrawType::Image;
  B.TintColor = FSlateColor(FLinearColor::White);
  return B;
}

/** Config/Cards/S08FighterNames.json (loaded once). */
const TSharedPtr<FJsonObject>& UmWlNames() {
  static TSharedPtr<FJsonObject> Root;
  static bool bTried = false;
  if (!bTried) {
    bTried = true;
    FString Text;
    const FString Path = FPaths::Combine(FPaths::ProjectConfigDir(), TEXT("Cards"), TEXT("S08FighterNames.json"));
    if (FFileHelper::LoadFileToString(Text, *Path)) FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root);
    if (!Root.IsValid()) UE_LOG(LogTemp, Warning, TEXT("UMWORLD fighter names missing: %s (the server labels)"), *Path);
  }
  return Root;
}
}  // namespace

namespace UmWorldLayer {
bool TagV2() { return !S08ArtLook::SlateHudBlocks().IsSlate(FName(TEXT("tag"))); }
bool PlateV2() { return !S08ArtLook::SlateHudBlocks().IsSlate(FName(TEXT("plate"))); }

FText DisplayName(const FS08BoardFighter& Fighter) {
  const FString Fallback = Fighter.Label.IsEmpty() ? Fighter.Name : Fighter.Label;
  const TSharedPtr<FJsonObject>& Root = UmWlNames();
  const TSharedPtr<FJsonObject>* Heroes = nullptr;
  const TSharedPtr<FJsonObject>* Hero = nullptr;
  const TSharedPtr<FJsonObject>* Entry = nullptr;
  if (!Root.IsValid() || !Root->TryGetObjectField(TEXT("heroes"), Heroes) || !(*Heroes)->TryGetObjectField(Fighter.HeroSlug, Hero) ||
      !(*Hero)->TryGetObjectField(Fighter.bIsHero ? TEXT("hero") : TEXT("sidekick"), Entry)) {
    return FText::FromString(Fallback);
  }
  bool bNumbered = false;
  if ((*Entry)->TryGetBoolField(TEXT("numbered"), bNumbered) && bNumbered) {
    FFormatNamedArguments Args;
    Args.Add(TEXT("number"), FText::AsNumber(S08HeroesV2::HarpyNumber(Fighter)));
    return UmText::Format(EUmTable::Hud, TEXT("hud.plate.harpy_name"), Args);
  }
  FString Name;
  const bool bRu = UmCardMedia::PreferredLang() != TEXT("en");
  if ((*Entry)->TryGetStringField(bRu ? TEXT("ru") : TEXT("en"), Name) && !Name.IsEmpty()) return FText::FromString(Name);
  return FText::FromString(Fallback);
}

FText RoleText(bool bHero, bool bRanged) {
  const TCHAR* Key = bHero ? (bRanged ? TEXT("hud.plate.role.hero_ranged") : TEXT("hud.plate.role.hero_melee"))
                           : (bRanged ? TEXT("hud.plate.role.sidekick_ranged") : TEXT("hud.plate.role.sidekick_melee"));
  return UmText::Get(EUmTable::Hud, Key);
}

FText SideText(bool bOwn) {
  return UmText::Get(EUmTable::Hud, bOwn ? TEXT("hud.plate.side.own") : TEXT("hud.plate.side.opponent"));
}

FText TargetText() { return UmText::Get(EUmTable::Hud, TEXT("hud.plate.target")); }

FText HpText(int32 Hp, int32 MaxHp) { return S08ArtHudText::HpLabel(Hp, MaxHp); }

bool NumberedSidekick(const FS08BoardFighter& Fighter) {
  const TSharedPtr<FJsonObject>& Root = UmWlNames();
  const TSharedPtr<FJsonObject>* Heroes = nullptr;
  const TSharedPtr<FJsonObject>* Hero = nullptr;
  const TSharedPtr<FJsonObject>* Entry = nullptr;
  bool bNumbered = false;
  return !Fighter.bIsHero && Root.IsValid() && Root->TryGetObjectField(TEXT("heroes"), Heroes) &&
         (*Heroes)->TryGetObjectField(Fighter.HeroSlug, Hero) && (*Hero)->TryGetObjectField(TEXT("sidekick"), Entry) &&
         (*Entry)->TryGetBoolField(TEXT("numbered"), bNumbered) && bNumbered;
}

int32 TagDigit(const FS08BoardFighter& Fighter) { return NumberedSidekick(Fighter) ? S08HeroesV2::HarpyNumber(Fighter) : 0; }

namespace {
UmTeamChip::FUmTeamChipBrushes WorldChips() {
  return UmTeamChip::Load(ChipSu, UmHudScale::Current().PxPerSu(), FCommandLine::Get());
}
}  // namespace

void SetupTag(US08ArtTagWidget& Tag) {
  if (!TagV2()) return;
  Tag.SetV2(true);
  const UmTeamChip::FUmTeamChipBrushes Chips = WorldChips();
  if (Chips.bReady && Tag.GetV2()) Tag.GetV2()->SetChipBrushes(Chips.Brushes[0], Chips.Brushes[1], Chips.Textures);
}

void SetupPlate(US08ArtPlateWidget& Plate) {
  if (!PlateV2()) return;
  Plate.SetV2(true);
  const UmTeamChip::FUmTeamChipBrushes Chips = WorldChips();
  if (Chips.bReady && Plate.GetV2()) Plate.GetV2()->SetChipBrushes(Chips.Brushes[0], Chips.Brushes[1], Chips.Textures);
}

void FillTagTexts(FS08TagTexts& Texts, const FS08BoardFighter& Fighter) {
  Texts.HpValue = Fighter.Health;
  Texts.HpMax = Fighter.MaxHealth;
  Texts.HarpyDigit = TagDigit(Fighter);
}

void FillPlateTexts(FS08PlateTexts& Texts, const FS08BoardFighter& Fighter, bool bOwn, bool bTarget) {
  if (!PlateV2()) return;
  Texts.Name = DisplayName(Fighter);
  Texts.Role = RoleText(Fighter.bIsHero, FS09CommandUi::IsRangedAttacker(Fighter));
  Texts.Side = SideText(bOwn);
  Texts.Hp = HpText(Fighter.Health, Fighter.MaxHealth);
  Texts.bTarget = bTarget;
}

FString LookField() {
  return FString::Printf(TEXT("worldTag=%s worldPlate=%s"), TagV2() ? TEXT("v2") : TEXT("legacy(-S08SlateHud=tag)"),
                         PlateV2() ? TEXT("v2") : TEXT("legacy(-S08SlateHud=plate)"));
}
}  // namespace UmWorldLayer

// ------------------------------------------------------------------------------------------------ tag (HB-45)

bool UUmWorldTag::Initialize() {
  const bool bFirst = Super::Initialize();
  if (!bFirst || !WidgetTree || WidgetTree->RootWidget) return bFirst;
  using namespace UmWorldLayer;
  UWidgetTree& Tree = *WidgetTree;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  USizeBox* Box = UmWlMake<USizeBox>(Tree, TEXT("Box"));
  Box->SetHeightOverride(TagHeightSu);
  Tree.RootWidget = Box;
  Capsule = UmWlMake<UBorder>(Tree, TEXT("Capsule"));
  Capsule->SetBrush(FSlateRoundedBoxBrush(Theme.Color(TEXT("card.navy")), TagRadiusSu, Theme.Color(TEXT("panel.edge")), 1.0f));
  Capsule->SetPadding(FMargin(TagPadSu, 0.0f));
  Capsule->SetHorizontalAlignment(HAlign_Left);
  Capsule->SetVerticalAlignment(VAlign_Center);
  Box->AddChild(Capsule);
  UHorizontalBox* Row = UmWlMake<UHorizontalBox>(Tree, TEXT("Row"));
  Capsule->SetContent(Row);
  ChipBox = UmWlMake<USizeBox>(Tree, TEXT("ChipBox"));
  ChipBox->SetWidthOverride(ChipSu);
  ChipBox->SetHeightOverride(ChipSu);
  Row->AddChild(ChipBox);
  UmWlH(ChipBox, 0.0f);
  Chip = UmWlMake<UImage>(Tree, TEXT("Chip"));
  ChipBox->AddChild(Chip);
  DigitBox = UmWlMake<USizeBox>(Tree, TEXT("DigitBox"));
  DigitBox->SetWidthOverride(DigitSu);
  DigitBox->SetHeightOverride(DigitSu);
  Row->AddChild(DigitBox);
  UmWlH(DigitBox, GapSu);
  DigitDisc = UmWlMake<UBorder>(Tree, TEXT("DigitDisc"));
  DigitDisc->SetBrush(FSlateRoundedBoxBrush(Theme.Color(TEXT("card.navy")), 0.5f * DigitSu, Theme.Color(TEXT("card.cream")), 1.0f));
  DigitDisc->SetPadding(FMargin(0.0f));
  DigitDisc->SetHorizontalAlignment(HAlign_Center);
  DigitDisc->SetVerticalAlignment(VAlign_Center);
  DigitBox->AddChild(DigitDisc);
  DigitText = UmWlText(Tree, TEXT("DigitText"), TEXT("type.tag"), TEXT("card.cream"));  // font.card, cap 10 su
  DigitText->SetJustification(ETextJustify::Center);
  DigitDisc->SetContent(DigitText);
  BarBox = UmWlMake<USizeBox>(Tree, TEXT("BarBox"));
  BarBox->SetWidthOverride(BarWSu);
  BarBox->SetHeightOverride(BarHSu);
  Row->AddChild(BarBox);
  UmWlH(BarBox, GapSu);
  UOverlay* Layers = UmWlMake<UOverlay>(Tree, TEXT("BarLayers"));
  BarBox->AddChild(Layers);
  BarBack = UmWlMake<UImage>(Tree, TEXT("BarBack"));
  BarBack->SetBrush(UmWlPlain());
  BarBack->SetColorAndOpacity(Theme.Color(TEXT("hp.back")));
  Layers->AddChild(BarBack);
  if (UOverlaySlot* S = Cast<UOverlaySlot>(BarBack->Slot)) {
    S->SetHorizontalAlignment(HAlign_Fill);
    S->SetVerticalAlignment(VAlign_Fill);
  }
  BarFill = UmWlMake<USizeBox>(Tree, TEXT("BarFill"));
  Layers->AddChild(BarFill);
  if (UOverlaySlot* S = Cast<UOverlaySlot>(BarFill->Slot)) {
    S->SetHorizontalAlignment(HAlign_Left);
    S->SetVerticalAlignment(VAlign_Fill);
  }
  BarFillImage = UmWlMake<UImage>(Tree, TEXT("BarFillImage"));
  BarFillImage->SetBrush(UmWlPlain());
  BarFillImage->SetColorAndOpacity(Theme.Color(TEXT("hp.fill")));
  BarFill->AddChild(BarFillImage);
  HpLabel = UmWlText(Tree, TEXT("HpLabel"), TEXT("type.tag"), TEXT("text.primary"));
  Row->AddChild(HpLabel);
  UmWlH(HpLabel, BarGapSu);
  SetVisibility(ESlateVisibility::HitTestInvisible);
  return bFirst;
}

void UUmWorldTag::SetChipBrushes(const FSlateBrush& P1, const FSlateBrush& P2, const TArray<UTexture2D*>& Keep) {
  ChipBrushes[0] = P1;
  ChipBrushes[1] = P2;
  bChips = true;
  ChipTextures.Reset();
  for (UTexture2D* T : Keep) ChipTextures.Add(T);
  Restyle();
}

void UUmWorldTag::ApplyModel(const FUmWorldTagModel& InModel) {
  if (bHasModel && Model == InModel) return;
  Model = InModel;
  bHasModel = true;
  Restyle();
}

void UUmWorldTag::Restyle() {
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  if (Chip) {
    if (bChips) Chip->SetBrush(ChipBrushes[Model.TeamSlot ? 1 : 0]);
    Chip->SetColorAndOpacity(Theme.Color(Model.TeamSlot ? TEXT("team.p2.screen") : TEXT("team.p1.screen")));
  }
  if (DigitBox) DigitBox->SetVisibility(Model.Digit > 0 ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
  if (DigitText) DigitText->SetText(Model.Digit > 0 ? FText::AsNumber(Model.Digit) : FText::GetEmpty());
  // the bar's slot sits 6 su after the chip, or after the digit (HB-44 row)
  const float Fraction = Model.MaxHp > 0 ? FMath::Clamp(static_cast<float>(Model.Hp) / Model.MaxHp, 0.0f, 1.0f) : 0.0f;
  if (BarFill) BarFill->SetWidthOverride(Fraction > 0.0f ? FMath::Max(1.0f, UmWorldLayer::BarWSu * Fraction) : 0.0f);
  if (HpLabel) HpLabel->SetText(UmWorldLayer::HpText(Model.Hp, Model.MaxHp));
}

int32 UUmWorldTag::HpFontSize() const {
  return HpLabel ? FMath::RoundToInt(HpLabel->GetFont().Size / UmHudTheme::PointsPerSu) : 0;
}

void UUmWorldTag::CollectParts(TArray<FS08WidgetPart>& Out) const {
  if (HpLabel) Out.Add({S08ArtHudIds::TagHp, HpLabel->GetCachedWidget()});
  if (BarBox) Out.Add({S08ArtHudIds::TagBar, BarBox->GetCachedWidget()});
  if (ChipBox) Out.Add({S08ArtHudIds::TagChip, ChipBox->GetCachedWidget()});
}

// ------------------------------------------------------------------------------------------------ plate (HB-46)

bool UUmWorldPlate::Initialize() {
  const bool bFirst = Super::Initialize();
  if (!bFirst || !WidgetTree || WidgetTree->RootWidget) return bFirst;
  using namespace UmWorldLayer;
  UWidgetTree& Tree = *WidgetTree;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  USizeBox* Box = UmWlMake<USizeBox>(Tree, TEXT("Box"));
  Box->SetWidthOverride(PlateWSu);
  Box->SetHeightOverride(PlateHSu);
  Tree.RootWidget = Box;
  Panel = UmWlMake<UBorder>(Tree, TEXT("Panel"));
  Panel->SetBrush(FSlateRoundedBoxBrush(Theme.Color(TEXT("panel.bg")), Theme.RadiusSu(TEXT("radius.m")), Theme.Color(TEXT("panel.edge")), 1.0f));
  Panel->SetPadding(FMargin(PlatePadSu, 10.0f));
  Panel->SetHorizontalAlignment(HAlign_Fill);
  Panel->SetVerticalAlignment(VAlign_Top);
  Box->AddChild(Panel);
  UVerticalBox* Col = UmWlMake<UVerticalBox>(Tree, TEXT("Col"));
  Panel->SetContent(Col);
  NameLabel = UmWlText(Tree, TEXT("NameLabel"), TEXT("type.heading"), TEXT("text.primary"));
  Col->AddChild(NameLabel);
  UmWlV(NameLabel, 0.0f);
  RoleLabel = UmWlText(Tree, TEXT("RoleLabel"), TEXT("type.tag"), TEXT("text.secondary"));
  Col->AddChild(RoleLabel);
  UmWlV(RoleLabel, 6.0f);
  UHorizontalBox* Row = UmWlMake<UHorizontalBox>(Tree, TEXT("Row"));
  Col->AddChild(Row);
  UmWlV(Row, 8.0f);
  HpLabel = UmWlText(Tree, TEXT("HpLabel"), TEXT("type.tag"), TEXT("text.primary"));
  Row->AddChild(HpLabel);
  UmWlH(HpLabel, 0.0f);
  ChipBox = UmWlMake<USizeBox>(Tree, TEXT("ChipBox"));
  ChipBox->SetWidthOverride(ChipSu);
  ChipBox->SetHeightOverride(ChipSu);
  Row->AddChild(ChipBox);
  UmWlH(ChipBox, 24.0f);
  Chip = UmWlMake<UImage>(Tree, TEXT("Chip"));
  ChipBox->AddChild(Chip);
  SideLabel = UmWlText(Tree, TEXT("SideLabel"), TEXT("type.tag"), TEXT("text.primary"));
  Row->AddChild(SideLabel);
  UmWlH(SideLabel, GapSu);
  TargetChip = UmWlMake<UBorder>(Tree, TEXT("TargetChip"));
  TargetChip->SetBrush(FSlateRoundedBoxBrush(Theme.Color(TEXT("state.pending")), Theme.RadiusSu(TEXT("radius.s"))));
  TargetChip->SetPadding(FMargin(Theme.SpaceSu(TEXT("space.s")), Theme.SpaceSu(TEXT("tag.padding.y"))));
  Col->AddChild(TargetChip);
  UmWlV(TargetChip, 8.0f);
  TargetLabel = UmWlText(Tree, TEXT("TargetLabel"), TEXT("type.tag"), TEXT("card.glyph"));
  TargetChip->SetContent(TargetLabel);
  TargetChip->SetVisibility(ESlateVisibility::Collapsed);
  SetVisibility(ESlateVisibility::HitTestInvisible);
  SetRenderOpacity(0.0f);
  return bFirst;
}

void UUmWorldPlate::SetChipBrushes(const FSlateBrush& P1, const FSlateBrush& P2, const TArray<UTexture2D*>& Keep) {
  ChipBrushes[0] = P1;
  ChipBrushes[1] = P2;
  bChips = true;
  ChipTextures.Reset();
  for (UTexture2D* T : Keep) ChipTextures.Add(T);
  if (Chip) Chip->SetBrush(ChipBrushes[Model.TeamSlot ? 1 : 0]);
}

void UUmWorldPlate::ApplyModel(const FUmWorldPlateModel& InModel) {
  Model = InModel;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  if (NameLabel) NameLabel->SetText(Model.Name);
  if (RoleLabel) RoleLabel->SetText(Model.Role);
  if (HpLabel) HpLabel->SetText(Model.Hp);
  if (SideLabel) SideLabel->SetText(Model.Side);
  if (TargetLabel) TargetLabel->SetText(UmWorldLayer::TargetText());
  if (TargetChip) TargetChip->SetVisibility(Model.bTarget ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
  if (Chip) {
    if (bChips) Chip->SetBrush(ChipBrushes[Model.TeamSlot ? 1 : 0]);
    Chip->SetColorAndOpacity(Theme.Color(Model.TeamSlot ? TEXT("team.p2.screen") : TEXT("team.p1.screen")));
  }
}

bool UUmWorldPlate::IsTargetShown() const {
  return TargetChip && TargetChip->GetVisibility() != ESlateVisibility::Collapsed;
}

double UUmWorldPlate::Now() const { return Clock ? Clock() : FPlatformTime::Seconds(); }

void UUmWorldPlate::SetShownAnimated(UWidget* Host, bool bShown) {
  FadeHost = Host;
  if (bShown && Host) Host->SetVisibility(ESlateVisibility::HitTestInvisible);
  if (bShown == bWantShown) {
    if (FadeStart >= 0.0) return;  // already fading there: the views call this every frame, the fade keeps its timing
    if (bShown && OpacityNow >= 1.0f) return;
    if (!bShown && OpacityNow <= 0.0f) return;
  }
  bWantShown = bShown;
  const bool bReduced = ReducedOverride >= 0 ? ReducedOverride == 1 : S08IconMotion::IsReducedMotion();
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  const float Ms = Theme.Ms(bShown ? TEXT("hover.ms") : TEXT("icon.leave.ms"));
  FadeMs = bReduced ? FMath::Min(Ms, Theme.Ms(TEXT("reduced.max_ms"))) : Ms;
  OpacityFrom = OpacityNow;
  FadeStart = Now();
  StepFade();
}

void UUmWorldPlate::FinishFade() {
  if (FadeStart < 0.0) return;
  FadeStart = Now() - FadeMs / 1000.0 - 1.0;
  StepFade();
}

void UUmWorldPlate::StepFade() {
  if (FadeStart < 0.0) return;
  const float A = FadeMs > 0.0 ? FMath::Clamp(static_cast<float>((Now() - FadeStart) * 1000.0 / FadeMs), 0.0f, 1.0f) : 1.0f;
  OpacityNow = FMath::Lerp(OpacityFrom, bWantShown ? 1.0f : 0.0f, A);
  SetRenderOpacity(OpacityNow);
  if (A >= 1.0f) {
    FadeStart = -1.0;
    if (!bWantShown) {
      if (UWidget* Host = FadeHost.Get()) Host->SetVisibility(ESlateVisibility::Collapsed);
    }
  }
}

void UUmWorldPlate::NativeTick(const FGeometry& MyGeometry, float InDeltaTime) {
  Super::NativeTick(MyGeometry, InDeltaTime);
  StepFade();
}

void UUmWorldPlate::CollectParts(TArray<FS08WidgetPart>& Out) const {
  if (NameLabel) Out.Add({S08ArtHudIds::PlateName, NameLabel->GetCachedWidget()});
  if (SideLabel) Out.Add({S08ArtHudIds::PlateTeam, SideLabel->GetCachedWidget()});
  if (HpLabel) Out.Add({S08ArtHudIds::PlateHp, HpLabel->GetCachedWidget()});
  if (RoleLabel) Out.Add({S08ArtHudIds::PlateStatus, RoleLabel->GetCachedWidget()});
  if (ChipBox) Out.Add({S08ArtHudIds::PlateTeamShape, ChipBox->GetCachedWidget()});
}
