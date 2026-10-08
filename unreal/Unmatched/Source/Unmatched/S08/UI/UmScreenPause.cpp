// VS-7 S4 SC-24...SC-30: the PAUSE modal and the settings - see UmScreenPause.h.
#include "UmScreenPause.h"

#include "UmButton.h"
#include "UmGameHud.h"
#include "UmHeroCard.h"
#include "UmHudTheme.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/CanvasPanel.h"
#include "Components/NamedSlot.h"
#include "Components/TextBlock.h"

using namespace UmPause;
using UmRoomUi::MeasureW;
using UmRoomUi::Place;
using UmRoomUi::S;
using UmRoomUi::Style;
using UmRoomUi::Vis;

const TCHAR* const UUmScreenPause::WidgetBlueprintPath = TEXT("/Game/S08/UI/Screens/WBP_UI_SCR_PAUSE");

UClass* UUmScreenPause::WidgetClass() { return UmGameHudSlots::WbpOrNative(UUmScreenPause::StaticClass(), WidgetBlueprintPath); }

namespace UmPause {
const TCHAR* TabName(EUmPauseTab T) {
  switch (T) {
    case EUmPauseTab::Interface: return TEXT("interface");
    case EUmPauseTab::Game: return TEXT("game");
    case EUmPauseTab::Graphics: return TEXT("graphics");
    default: return TEXT("sound");
  }
}

const TCHAR* TabKey(EUmPauseTab T) {
  switch (T) {
    case EUmPauseTab::Interface: return TEXT("settings.tab.interface");
    case EUmPauseTab::Game: return TEXT("settings.tab.game");
    case EUmPauseTab::Graphics: return TEXT("settings.tab.graphics");
    default: return TEXT("settings.tab.sound");
  }
}

const TCHAR* ContextName(EUmPauseContext C) {
  switch (C) {
    case EUmPauseContext::Lobby: return TEXT("lobby");
    case EUmPauseContext::Room: return TEXT("room");
    default: return TEXT("game");
  }
}

float MaxModalHSu(const FVector2D& CanvasSu, bool bClassS) {
  const float Margin = UmScreens::SafeMarginSu(bClassS);
  const float Cap = CanvasSu.Y >= 1079.0 ? 800.0f : 864.0f;  // 04 §1.8: 720 x <= 800 (720p: <= 864 su)
  return FMath::Min(Cap, static_cast<float>(CanvasSu.Y) - 2.0f * Margin);
}

namespace {
FUmSettingRowModel Slider(const TCHAR* Key, const TCHAR* LabelKey, int32 Value) {
  FUmSettingRowModel R;
  R.Key = FName(Key);
  R.Kind = EUmSettingKind::Slider;
  R.Label = S(LabelKey);
  R.Value = Value;
  return R;
}

FUmSettingRowModel Check(const TCHAR* Key, const TCHAR* LabelKey, bool bOn) {
  FUmSettingRowModel R;
  R.Key = FName(Key);
  R.Kind = EUmSettingKind::Check;
  R.Label = S(LabelKey);
  R.bOn = bOn;
  return R;
}

FUmSettingRowModel Chips(const TCHAR* Key, const TCHAR* LabelKey, std::initializer_list<TPair<const TCHAR*, const TCHAR*>> Items,
                         const FString& Current) {
  FUmSettingRowModel R;
  R.Key = FName(Key);
  R.Kind = EUmSettingKind::Chips;
  R.Label = S(LabelKey);
  for (const TPair<const TCHAR*, const TCHAR*>& I : Items) {
    if (Current == I.Value) R.Selected = R.Chips.Num();
    R.Chips.Add(S(I.Key));
    R.ChipValues.Add(I.Value);
  }
  return R;
}
}  // namespace

TArray<FUmSettingRowModel> Rows(const FUmPauseModel& M, EUmPauseTab Tab) {
  TArray<FUmSettingRowModel> Out;
  switch (Tab) {
    case EUmPauseTab::Sound: {
      // ВР-VS5-SC25-01: the order and the buses of S08UserSettings.h; no other bus
      FUmSettingRowModel Master = Slider(TEXT("master"), TEXT("settings.sound.master"), M.Master);
      Master.MuteKey = FName(TEXT("masterMute"));
      Master.bMuted = M.bMasterMuted;
      Out.Add(Master);
      Out.Add(Slider(TEXT("music"), TEXT("settings.sound.music"), M.Music));
      Out.Add(Slider(TEXT("sfx"), TEXT("settings.sound.effects"), M.Sfx));
      Out.Add(Slider(TEXT("ui"), TEXT("settings.sound.interface"), M.Ui));
      Out.Add(Slider(TEXT("vo"), TEXT("settings.sound.voices"), M.Vo));
      FUmSettingRowModel Amb = Slider(TEXT("ambience"), TEXT("settings.sound.ambience"), M.Ambience);
      Amb.MuteKey = FName(TEXT("ambienceMute"));
      Amb.bMuted = M.bAmbienceMuted;
      Out.Add(Amb);
      Out.Add(Check(TEXT("subtitles"), TEXT("settings.sound.subtitles"), M.bSubtitles));
      Out.Add(Check(TEXT("describeSounds"), TEXT("settings.sound.describe"), M.bDescribeSounds));
      break;
    }
    case EUmPauseTab::Interface: {
      // ВР-VS5-SC26-01: Язык, Масштаб интерфейса, Подсказки правил, Подсказки клавиш (+ the SC-29 sample)
      Out.Add(Chips(TEXT("language"), TEXT("settings.interface.language"),
                    {{TEXT("settings.interface.language.ru"), TEXT("ru")}, {TEXT("settings.interface.language.en"), TEXT("en")}}, M.Language));
      FUmSettingRowModel Scale = Slider(TEXT("uiScale"), TEXT("settings.interface.scale"), FMath::Clamp(M.UiScale, M.UiScaleMin, 150));
      Scale.Min = M.UiScaleMin;
      Scale.Max = 150;
      FFormatNamedArguments Args;
      Args.Add(TEXT("min"), FText::AsNumber(M.UiScaleMin));
      Args.Add(TEXT("max"), FText::AsNumber(150));
      Scale.Note = UmText::Format(EUmTable::Screens, TEXT("settings.interface.scale.range"), Args);  // ВР-VS5-SC27-01
      Out.Add(Scale);
      Out.Add(Check(TEXT("ruleHints"), TEXT("settings.interface.rule_hints"), M.bRuleHints));
      FUmSettingRowModel Keys = Chips(TEXT("keyHints"), TEXT("settings.interface.key_hints"),
                                      {{TEXT("settings.interface.key_hints.auto"), TEXT("auto")},
                                       {TEXT("settings.interface.key_hints.on"), TEXT("on")},
                                       {TEXT("settings.interface.key_hints.off"), TEXT("off")}},
                                      M.KeyHints);
      Keys.Note = S(TEXT("settings.interface.key_hints.note"));
      Keys.bSample = true;  // ВР-VS5-SC29-01: the END TURN cell as HB-42 / HB-43 draw it
      Keys.bSampleChip = M.bKeyChips;
      Keys.bClassS = M.bClassS;
      Out.Add(Keys);
      break;
    }
    case EUmPauseTab::Game:
      // ВР-VS5-SC28-01; ВР-SC06: no shake row (bScreenShake stays in the save)
      Out.Add(Chips(TEXT("speed"), TEXT("settings.game.anim_speed"),
                    {{TEXT("settings.game.anim_speed.none"), TEXT("none")}, {TEXT("settings.game.anim_speed.fast"), TEXT("fast")},
                     {TEXT("settings.game.anim_speed.normal"), TEXT("normal")}, {TEXT("settings.game.anim_speed.slow"), TEXT("slow")}},
                    M.AnimSpeed));
      Out.Add(Check(TEXT("reduced"), TEXT("settings.game.reduced_motion"), M.bReducedMotion));
      break;
    case EUmPauseTab::Graphics: {
      // ВР-VS5-SC30-01: Высокое (sg.* 2, the acceptance reference) / Среднее / Низкое + the note
      FUmSettingRowModel Q = Chips(TEXT("graphics"), TEXT("settings.graphics.quality"),
                                   {{TEXT("settings.graphics.quality.high"), TEXT("2")}, {TEXT("settings.graphics.quality.medium"), TEXT("1")},
                                    {TEXT("settings.graphics.quality.low"), TEXT("0")}},
                                   FString::FromInt(M.Graphics));
      Q.Note = S(TEXT("settings.graphics.note"));
      Out.Add(Q);
      break;
    }
  }
  return Out;
}
}  // namespace UmPause

namespace {
template <typename T>
T* UmPsFind(UWidgetTree* Tree, const TCHAR* Name) {
  return Tree ? Cast<T>(Tree->FindWidget(FName(Name))) : nullptr;
}

const TCHAR* const UmPsTabs[] = {TEXT("TabSound"), TEXT("TabInterface"), TEXT("TabGame"), TEXT("TabGraphics")};
}  // namespace

bool UUmScreenPause::AttachContent(UWidgetTree& Tree, UPanelWidget* Parent, FS08AttachWidget Attach, FString* OutError) {
  auto Fail = [OutError](const TCHAR* What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), What);
    return false;
  };
  UCanvasPanel* ContentW = Tree.ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Content")));
  ContentW->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  if (!Attach(ContentW, Parent)) return Fail(TEXT("Content"));
  for (const TCHAR* Name : {TEXT("TitleText"), TEXT("RunningText"), TEXT("DefenseText"), TEXT("LeaveWhy")}) {
    UTextBlock* T = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(Name));
    T->SetVisibility(ESlateVisibility::HitTestInvisible);
    if (!Attach(T, ContentW)) return Fail(Name);
  }
  for (const TCHAR* Name : {TEXT("HeaderDivider"), TEXT("FooterDivider"), TEXT("ScrollTrack"), TEXT("ScrollThumb")}) {
    UBorder* B = Tree.ConstructWidget<UBorder>(UBorder::StaticClass(), FName(Name));
    B->SetVisibility(ESlateVisibility::HitTestInvisible);
    B->SetPadding(FMargin(0.0f));
    if (!Attach(B, ContentW)) return Fail(Name);
  }
  UCanvasPanel* TabsW = Tree.ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Tabs")));
  TabsW->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  if (!Attach(TabsW, ContentW)) return Fail(TEXT("Tabs"));
  UCanvasPanel* RowsW = Tree.ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Rows")));
  RowsW->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  RowsW->SetClipping(EWidgetClipping::ClipToBounds);  // ВР-VS5-SC24-03: the rows scroll under the header and the footer
  if (!Attach(RowsW, ContentW)) return Fail(TEXT("Rows"));
  UClass* ButtonClass = UmGameHudSlots::WbpOrNative(UUmButton::StaticClass(), UUmButton::WidgetBlueprintPath);
  for (const TCHAR* Name : UmPsTabs) {
    if (!Attach(Tree.ConstructWidget<UUmButton>(ButtonClass, FName(Name)), TabsW)) return Fail(Name);
  }
  for (const TCHAR* Name : {TEXT("LeaveButton"), TEXT("ContinueButton")}) {
    if (!Attach(Tree.ConstructWidget<UUmButton>(ButtonClass, FName(Name)), ContentW)) return Fail(Name);
  }
  return true;
}

bool UUmScreenPause::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  if (!UUmScreenBase::BuildDefaultTree(Tree, Attach, OutError)) return false;
  UNamedSlot* BodyW = Cast<UNamedSlot>(Tree.FindWidget(FName(TEXT("Body"))));
  if (!BodyW) {
    if (OutError) *OutError = TEXT("no Body");
    return false;
  }
  return AttachContent(Tree, BodyW, Attach, OutError);
}

void UUmScreenPause::BuildContent() {
  if (!WidgetTree || !Body || Body->GetContent()) return;
  FString Problem;
  auto AddTo = [](UWidget* Child, UPanelWidget* Parent) { return Parent && Parent->AddChild(Child) != nullptr; };
  if (!AttachContent(*WidgetTree, Body, AddTo, &Problem)) UE_LOG(LogTemp, Error, TEXT("UMHUD pause content: %s"), *Problem);
}

void UUmScreenPause::BindParts() {
  Content = UmPsFind<UCanvasPanel>(WidgetTree, TEXT("Content"));
  TitleText = UmPsFind<UTextBlock>(WidgetTree, TEXT("TitleText"));
  RunningText = UmPsFind<UTextBlock>(WidgetTree, TEXT("RunningText"));
  DefenseText = UmPsFind<UTextBlock>(WidgetTree, TEXT("DefenseText"));
  LeaveWhy = UmPsFind<UTextBlock>(WidgetTree, TEXT("LeaveWhy"));
  HeaderDivider = UmPsFind<UBorder>(WidgetTree, TEXT("HeaderDivider"));
  FooterDivider = UmPsFind<UBorder>(WidgetTree, TEXT("FooterDivider"));
  ScrollTrack = UmPsFind<UBorder>(WidgetTree, TEXT("ScrollTrack"));
  ScrollThumb = UmPsFind<UBorder>(WidgetTree, TEXT("ScrollThumb"));
  Tabs = UmPsFind<UCanvasPanel>(WidgetTree, TEXT("Tabs"));
  Rows = UmPsFind<UCanvasPanel>(WidgetTree, TEXT("Rows"));
  TabSound = UmPsFind<UUmButton>(WidgetTree, TEXT("TabSound"));
  TabInterface = UmPsFind<UUmButton>(WidgetTree, TEXT("TabInterface"));
  TabGame = UmPsFind<UUmButton>(WidgetTree, TEXT("TabGame"));
  TabGraphics = UmPsFind<UUmButton>(WidgetTree, TEXT("TabGraphics"));
  LeaveButton = UmPsFind<UUmButton>(WidgetTree, TEXT("LeaveButton"));
  ContinueButton = UmPsFind<UUmButton>(WidgetTree, TEXT("ContinueButton"));
}

bool UUmScreenPause::Initialize() {
  const bool bFirst = Super::Initialize();
  if (!bFirst || !WidgetTree) return bFirst;
  SetUiId(TEXT("UI-SCR-PAUSE"));
  SetScreenState(FName(TEXT("sound")));
  BindParts();
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  Style(TitleText, TEXT("type.title"), TEXT("text.primary"));
  Style(RunningText, TEXT("type.body"), TEXT("text.secondary"));
  Style(DefenseText, TEXT("type.body"), TEXT("text.primary"));
  Style(LeaveWhy, TEXT("type.caption"), TEXT("text.secondary"));
  for (UBorder* B : {HeaderDivider.Get(), FooterDivider.Get()}) {
    if (B) B->SetBrushColor(Theme.Color(TEXT("panel.divider")));
  }
  if (ScrollTrack) ScrollTrack->SetBrushColor(Theme.Color(TEXT("panel.bg.inset")));
  if (ScrollThumb) ScrollThumb->SetBrushColor(Theme.Color(TEXT("card.cream")));
  if (Rows) Rows->SetClipping(EWidgetClipping::ClipToBounds);
  Refresh();
  return bFirst;
}

bool UUmScreenPause::HasAllParts(FString* OutMissing) const {
  FString Base;
  HasBaseParts(&Base);
  TArray<FString> Missing;
  if (!Base.IsEmpty()) Missing.Add(Base);
  auto Need = [&Missing](const UObject* P, const TCHAR* Name) {
    if (!P) Missing.Add(Name);
  };
  Need(TitleText, TEXT("TitleText"));
  Need(RunningText, TEXT("RunningText"));
  Need(DefenseText, TEXT("DefenseText"));
  Need(HeaderDivider, TEXT("HeaderDivider"));
  Need(Tabs, TEXT("Tabs"));
  Need(TabSound, TEXT("TabSound"));
  Need(TabInterface, TEXT("TabInterface"));
  Need(TabGame, TEXT("TabGame"));
  Need(TabGraphics, TEXT("TabGraphics"));
  Need(Rows, TEXT("Rows"));
  Need(ScrollTrack, TEXT("ScrollTrack"));
  Need(ScrollThumb, TEXT("ScrollThumb"));
  Need(FooterDivider, TEXT("FooterDivider"));
  Need(LeaveButton, TEXT("LeaveButton"));
  Need(LeaveWhy, TEXT("LeaveWhy"));
  Need(ContinueButton, TEXT("ContinueButton"));
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

void UUmScreenPause::ApplyCanvas(const FVector2D& InCanvasSu, bool bInClassS, float InPxPerSu) {
  SetCanvas(InCanvasSu, bInClassS, InPxPerSu);
  Model.bClassS = bInClassS;
  Refresh();
}

void UUmScreenPause::SetInput(const TSharedPtr<FS09HudPressArbiter>& InArbiter, FInput InInput) {
  Arbiter = InArbiter;
  Input = MoveTemp(InInput);
  TWeakObjectPtr<UUmScreenPause> WeakThis(this);
  auto Bind = [this, WeakThis](UUmButton* B, const TCHAR* Id) {
    if (!B) return;
    const FName Name(Id);
    B->SetPress(Name, Arbiter, FS09OnHudPressOutcome::CreateLambda([WeakThis, Name](const FS09HudPressOutcome& O) {
      if (UUmScreenPause* Self = WeakThis.Get()) Self->OnPressOutcome(Name, O);
    }));
  };
  Bind(TabSound, TEXT("screens.pause.tab.sound"));
  Bind(TabInterface, TEXT("screens.pause.tab.interface"));
  Bind(TabGame, TEXT("screens.pause.tab.game"));
  Bind(TabGraphics, TEXT("screens.pause.tab.graphics"));
  Bind(LeaveButton, TEXT("screens.pause.leave"));
  Bind(ContinueButton, TEXT("screens.pause.continue"));
  for (UUmSettingRow* R : Pool) {
    if (R) R->SetInput(FName(TEXT("screens.pause.row")), Arbiter, UUmSettingRow::FInput{Input.OnCommit, Input.OnSound});
  }
}

void UUmScreenPause::ApplyModel(const FUmPauseModel& InModel) {
  FUmPauseModel Next = InModel;
  Next.bClassS = IsClassS();
  if (bHasModel && Next == Model) return;  // the per-frame feed costs nothing while nothing changed (HUD-RULES П8)
  bHasModel = true;
  Model = Next;
  Refresh();
}

void UUmScreenPause::SetTab(EUmPauseTab InTab) {
  if (Tab == InTab) return;
  Tab = InTab;
  ScrollSu = 0.0f;
  Refresh();
}

bool UUmScreenPause::HandleEscape() {
  if (!IsShown()) return false;
  if (Input.OnContinue) Input.OnContinue();
  return true;
}

void UUmScreenPause::Refresh() {
  if (TitleText) TitleText->SetText(S(TEXT("screens.pause.title")));
  if (RunningText) RunningText->SetText(S(TEXT("screens.pause.running")));
  if (DefenseText) {
    FFormatNamedArguments Args;
    Args.Add(TEXT("n"), FText::AsNumber(FMath::Max(0, Model.DefenseSeconds)));
    DefenseText->SetText(UmText::Format(EUmTable::Screens, TEXT("screens.pause.defense.left"), Args));
  }
  const bool bGame = Model.Context == EUmPauseContext::Game;
  Vis(RunningText, bGame);
  Vis(DefenseText, bGame && Model.DefenseSeconds >= 0);
  // the tabs: the open one btn.selected (card.glyph text); the column keeps 160 su unless a label needs more
  TabW = TabWSu;
  for (int32 I = 0; I < 4; ++I) {
    const FText L = S(TabKey(static_cast<EUmPauseTab>(I)));
    TabW = FMath::Max(TabW, FMath::CeilToFloat(MeasureW(FText::FromString(L.ToString().ToUpper()), TEXT("type.button"))) + 2.0f * 16.0f + 2.0f);
  }
  ModalW = PadSu + TabW + GapSu + RowsWSu + PadSu;
  for (int32 I = 0; I < 4; ++I) {
    UUmButton* B = GetTabButton(static_cast<EUmPauseTab>(I));
    if (!B) continue;
    FUmButtonModel M;
    M.Variant = EUmButtonVariant::Normal;
    M.Label = S(TabKey(static_cast<EUmPauseTab>(I)));
    M.bSelected = static_cast<int32>(Tab) == I;
    M.HeightSu = TabHSu;
    M.MinWidthSu = TabW;
    B->ApplyModel(M);
  }
  // the footer
  const bool bLeave = Model.Context != EUmPauseContext::Lobby;
  const FText LeaveLabel = S(Model.Context == EUmPauseContext::Room ? TEXT("screens.room.leave") : TEXT("screens.pause.leave"));
  if (LeaveButton) {
    FUmButtonModel M;
    M.Variant = EUmButtonVariant::Normal;
    M.Label = LeaveLabel;
    M.IconName = FName(TEXT("badge-refuse"));  // ВР-VS5-SC24-05: the only red of the modal - the X 24 su, no red text
    M.bEnabled = !Model.bSyncing;
    if (Model.bSyncing) M.Reason = FS09Reason::Make(TEXT("why.syncing"));
    M.HeightSu = FooterHSu;
    M.MinWidthSu = 168.0f;
    LeaveButton->ApplyModel(M);
  }
  Vis(LeaveButton, bLeave, true);
  if (LeaveWhy) LeaveWhy->SetText(UmText::Get(EUmTable::Why, TEXT("why.syncing")));
  Vis(LeaveWhy, bLeave && Model.bSyncing);
  if (ContinueButton) {
    FUmButtonModel M;
    M.Variant = EUmButtonVariant::Primary;  // the one primary of the window
    M.Label = S(TEXT("screens.pause.continue"));
    M.HeightSu = FooterHSu;
    M.MinWidthSu = 168.0f;
    ContinueButton->ApplyModel(M);
  }
  LeaveWSu = FMath::Max(168.0f, MeasureW(FText::FromString(LeaveLabel.ToString().ToUpper()), TEXT("type.button")) + 48.0f + 32.0f);
  ContinueWSu = FMath::Max(168.0f, MeasureW(FText::FromString(S(TEXT("screens.pause.continue")).ToString().ToUpper()), TEXT("type.button")) + 48.0f);
  // the rows of the open tab
  const TArray<FUmSettingRowModel> Models = UmPause::Rows(Model, Tab);
  while (Pool.Num() < Models.Num() && WidgetTree && Rows) {
    UUmSettingRow* R = CreateWidget<UUmSettingRow>(this, UUmSettingRow::StaticClass());
    if (!R) break;
    Rows->AddChild(R);
    R->SetInput(FName(TEXT("screens.pause.row")), Arbiter, UUmSettingRow::FInput{Input.OnCommit, Input.OnSound});
    Pool.Add(R);
    UBorder* D = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass());
    D->SetVisibility(ESlateVisibility::HitTestInvisible);
    D->SetBrushColor(UUmHudTheme::Get().Color(TEXT("panel.divider")));
    Rows->AddChild(D);
    RowDividers.Add(D);
  }
  RowCountNow = FMath::Min(Models.Num(), Pool.Num());
  RowY.SetNum(RowCountNow + 1);
  float Y = 0.0f;
  for (int32 I = 0; I < Pool.Num(); ++I) {
    UUmSettingRow* R = Pool[I];
    if (!R) continue;
    if (I < RowCountNow) {
      RowY[I] = Y;
      Y += R->Apply(Models[I], PxPerSu) + (I + 1 < RowCountNow ? 1.0f : 0.0f);
    }
  }
  if (RowY.Num() > RowCountNow) RowY[RowCountNow] = Y;
  TotalRowsSu = Y;
  SetScreenState(FName(TabName(Tab)));
  Layout();
}

void UUmScreenPause::Layout() {
  const bool bGame = Model.Context == EUmPauseContext::Game;
  // the header: the title, the running line, the defense line
  float HeaderH = TitleHSu;
  if (bGame) HeaderH += 4.0f + LineHSu;
  if (bGame && Model.DefenseSeconds >= 0) HeaderH += 4.0f + LineHSu;
  const float WhyH = Model.Context != EUmPauseContext::Lobby && Model.bSyncing ? 4.0f + WhyHSu : 0.0f;
  const float Chrome = PadSu + HeaderH + PadSu + 1.0f + PadSu + PadSu + 1.0f + PadSu + FooterHSu + WhyH + PadSu;
  const float TabsH = 4.0f * TabHSu + 3.0f * GapSu;
  const float Want = FMath::Max(TabsH, TotalRowsSu);
  const float MaxH = MaxModalHSu(CanvasSu, bClassS);
  const float BodyH = FMath::Max(TabsH, FMath::Min(Want, MaxH - Chrome));
  VisibleRowsSu = FMath::Min(TotalRowsSu, BodyH);
  ModalHSu = Chrome + BodyH;
  SetFrameSize(FVector2D(ModalW, ModalHSu));
  ScrollSu = FMath::Clamp(ScrollSu, 0.0f, FMath::Max(0.0f, TotalRowsSu - BodyH));
  float Y = PadSu;
  Place(TitleText, FVector2D(PadSu, Y), FVector2D(ModalW - 2.0f * PadSu, TitleHSu));
  Y += TitleHSu;
  if (bGame) {
    Place(RunningText, FVector2D(PadSu, Y + 4.0f), FVector2D(ModalW - 2.0f * PadSu, LineHSu + 2.0f));
    Y += 4.0f + LineHSu;
  }
  if (bGame && Model.DefenseSeconds >= 0) {
    Place(DefenseText, FVector2D(PadSu, Y + 4.0f), FVector2D(ModalW - 2.0f * PadSu, LineHSu + 2.0f));
    Y += 4.0f + LineHSu;
  }
  Y += PadSu;
  Place(HeaderDivider, FVector2D(PadSu, Y), FVector2D(ModalW - 2.0f * PadSu, 1.0f));
  Y += 1.0f + PadSu;
  BodyTopSu = Y;
  Place(Tabs, FVector2D(PadSu, Y), FVector2D(TabW, TabsH));
  for (int32 I = 0; I < 4; ++I) {
    Place(GetTabButton(static_cast<EUmPauseTab>(I)), FVector2D(0.0f, I * (TabHSu + GapSu)), FVector2D(TabW, TabHSu));
  }
  const float RowsX = PadSu + TabW + GapSu;
  Place(Rows, FVector2D(RowsX, Y), FVector2D(RowsWSu, BodyH));
  const bool bScroll = IsScrolling();
  Vis(ScrollTrack, bScroll);
  Vis(ScrollThumb, bScroll);
  if (bScroll) {
    const float TrackX = RowsX + RowsWSu - 4.0f - 4.0f;
    Place(ScrollTrack, FVector2D(TrackX, Y), FVector2D(4.0f, BodyH));
    const float ThumbH = FMath::Max(24.0f, BodyH * VisibleRowsSu / FMath::Max(1.0f, TotalRowsSu));
    const float Room = BodyH - ThumbH;
    const float Span = FMath::Max(1.0f, TotalRowsSu - VisibleRowsSu);
    Place(ScrollThumb, FVector2D(TrackX, Y + Room * ScrollSu / Span), FVector2D(4.0f, ThumbH));
  }
  Y += BodyH + PadSu;
  Place(FooterDivider, FVector2D(PadSu, Y), FVector2D(ModalW - 2.0f * PadSu, 1.0f));
  Y += 1.0f + PadSu;
  FooterTopSu = Y;
  Place(LeaveButton, FVector2D(PadSu, Y), FVector2D(LeaveWSu, FooterHSu));
  Place(LeaveWhy, FVector2D(PadSu, Y + FooterHSu + 4.0f), FVector2D(ModalW - 2.0f * PadSu - ContinueWSu - GapSu, WhyHSu + 2.0f));
  Place(ContinueButton, FVector2D(ModalW - PadSu - ContinueWSu, Y), FVector2D(ContinueWSu, FooterHSu));
  PlaceRows();
}

void UUmScreenPause::PlaceRows() {
  for (int32 I = 0; I < Pool.Num(); ++I) {
    UUmSettingRow* R = Pool[I];
    UBorder* D = RowDividers.IsValidIndex(I) ? RowDividers[I].Get() : nullptr;
    if (!R) continue;
    if (I >= RowCountNow) {
      Vis(R, false);
      Vis(D, false);
      continue;
    }
    const float Top = RowY[I] - ScrollSu;
    const float H = R->GetHeightSu();
    // ВР-VS5-SC24-03: a row not wholly inside the visible band is collapsed (no half rows, no press on a hidden text)
    const bool bIn = Top >= -0.5f && Top + H <= VisibleRowsSu + 0.5f;  // whole rows only: no half letters at the edges
    R->SetVisibility(bIn ? ESlateVisibility::Visible : ESlateVisibility::Collapsed);
    Place(R, FVector2D(0.0f, Top), FVector2D(RowsWSu, H));
    const bool bDivider = bIn && I + 1 < RowCountNow && Top + H < VisibleRowsSu;
    Vis(D, bDivider);
    Place(D, FVector2D(0.0f, Top + H), FVector2D(RowsWSu, 1.0f));
  }
}

void UUmScreenPause::ScrollTo(float OffsetSu) {
  const float Max = FMath::Max(0.0f, TotalRowsSu - VisibleRowsSu);
  const float Next = FMath::Clamp(OffsetSu, 0.0f, Max);
  if (FMath::IsNearlyEqual(Next, ScrollSu)) return;
  ScrollSu = Next;
  Layout();
}

void UUmScreenPause::ScrollBy(float DeltaSu) { ScrollTo(ScrollSu + DeltaSu); }

FReply UUmScreenPause::NativeOnMouseWheel(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) {
  if (IsShown() && IsScrolling()) ScrollBy(-InMouseEvent.GetWheelDelta() * WheelStepSu);
  return FReply::Handled();
}

UUmButton* UUmScreenPause::GetTabButton(EUmPauseTab InTab) const {
  switch (InTab) {
    case EUmPauseTab::Interface: return TabInterface;
    case EUmPauseTab::Game: return TabGame;
    case EUmPauseTab::Graphics: return TabGraphics;
    default: return TabSound;
  }
}

UUmSettingRow* UUmScreenPause::FindRow(FName Key) const {
  for (int32 I = 0; I < RowCountNow && I < Pool.Num(); ++I) {
    if (Pool[I] && Pool[I]->GetModel().Key == Key) return Pool[I];
  }
  return nullptr;
}

FString UUmScreenPause::GetTitleText() const { return TitleText ? TitleText->GetText().ToString() : FString(); }
FString UUmScreenPause::GetRunningText() const { return RunningText ? RunningText->GetText().ToString() : FString(); }
FString UUmScreenPause::GetDefenseText() const { return DefenseText ? DefenseText->GetText().ToString() : FString(); }
bool UUmScreenPause::IsRunningShown() const { return RunningText && RunningText->GetVisibility() != ESlateVisibility::Collapsed; }
bool UUmScreenPause::IsDefenseShown() const { return DefenseText && DefenseText->GetVisibility() != ESlateVisibility::Collapsed; }
bool UUmScreenPause::IsLeaveShown() const { return LeaveButton && LeaveButton->GetVisibility() != ESlateVisibility::Collapsed; }
bool UUmScreenPause::IsLeaveEnabled() const { return IsLeaveShown() && LeaveButton->GetModel().bEnabled; }
FString UUmScreenPause::GetLeaveText() const { return LeaveButton ? LeaveButton->GetModel().Label.ToString() : FString(); }
FString UUmScreenPause::GetLeaveWhy() const {
  return LeaveWhy && LeaveWhy->GetVisibility() != ESlateVisibility::Collapsed ? LeaveWhy->GetText().ToString() : FString();
}

int32 UUmScreenPause::PrimaryCount() const {
  int32 N = 0;
  for (const UUmButton* B : {LeaveButton.Get(), ContinueButton.Get(), TabSound.Get(), TabInterface.Get(), TabGame.Get(), TabGraphics.Get()}) {
    if (B && B->GetVisibility() != ESlateVisibility::Collapsed && B->GetModel().Variant == EUmButtonVariant::Primary) ++N;
  }
  return N;
}

FBox2D UUmScreenPause::ContinueRectSu() const {
  const FBox2D F = FrameRectSu();
  const FVector2D Min = F.Min + FVector2D(ModalW - PadSu - ContinueWSu, FooterTopSu);
  return FBox2D(Min, Min + FVector2D(ContinueWSu, FooterHSu));
}

bool UUmScreenPause::FooterVisible() const {
  const FBox2D F = FrameRectSu();
  const FBox2D C = ContinueRectSu();
  const float M = GetSafeMarginSu();
  const bool bFrameIn = F.Min.Y >= M - 0.5 && F.Max.Y <= CanvasSu.Y - M + 0.5 && F.Min.X >= M - 0.5 && F.Max.X <= CanvasSu.X - M + 0.5;
  const bool bFooterIn = C.Max.Y <= F.Max.Y + 0.5 && C.Min.Y >= F.Min.Y && FMath::IsNearlyEqual(F.GetSize().Y, ModalHSu, 0.5f);
  return bFrameIn && bFooterIn;
}

FString UUmScreenPause::ShotExtra() const {
  const TCHAR* Leave = !IsLeaveShown() ? TEXT("none") : IsLeaveEnabled() ? TEXT("enabled") : TEXT("disabled");
  return FString::Printf(TEXT(" context=%s rows=%d scroll=%d visible=%.0f total=%.0f modalH=%.0f leave=%s why=%s defense=%s primary=%s lang=%s"),
                         ContextName(Model.Context), RowCountNow, IsScrolling() ? 1 : 0, VisibleRowsSu, TotalRowsSu, ModalHSu, Leave,
                         IsLeaveShown() && !IsLeaveEnabled() ? TEXT("why.syncing") : TEXT("-"),
                         IsDefenseShown() ? *FString::FromInt(Model.DefenseSeconds) : TEXT("-"),
                         PrimaryCount() == 1 && ContinueButton && ContinueButton->GetModel().Variant == EUmButtonVariant::Primary ? TEXT("continue")
                                                                                                                                  : TEXT("none"),
                         UmText::IsPseudo() ? TEXT("pseudo") : *Model.Language);
}

void UUmScreenPause::OnPressOutcome(FName Id, const FS09HudPressOutcome& Outcome) {
  if (!IsShown()) return;
  const FString Name = Id.ToString();
  if (Outcome.Result != ES09HudPressResult::Act) {
    if (Outcome.Result == ES09HudPressResult::Refused && Input.OnSound) Input.OnSound(FName(TEXT("UI-REJECT")));
    return;
  }
  if (Name.StartsWith(TEXT("screens.pause.tab."))) {
    const FString T = Name.RightChop(18);
    const EUmPauseTab Next = T == TEXT("interface") ? EUmPauseTab::Interface
                             : T == TEXT("game")    ? EUmPauseTab::Game
                             : T == TEXT("graphics") ? EUmPauseTab::Graphics
                                                     : EUmPauseTab::Sound;
    if (Next != Tab) {
      if (Input.OnSound) Input.OnSound(FName(TEXT("UI-BTN-CLICK")));
      SetTab(Next);
      if (Input.OnTab) Input.OnTab(Next);
    }
    return;
  }
  if (Id == FName(TEXT("screens.pause.continue"))) {
    if (Input.OnContinue) Input.OnContinue();
  } else if (Id == FName(TEXT("screens.pause.leave"))) {
    if (Input.OnLeave) Input.OnLeave();
  }
}

void UUmScreenPause::SimulatePress(FName Id) {
  if (!Arbiter.IsValid()) Arbiter = MakeShared<FS09HudPressArbiter>();
  // the disabled leave button answers Refused with its why (no silently disabled button)
  FS09Reason Why;
  if (Id == FName(TEXT("screens.pause.leave")) && !IsLeaveEnabled()) Why = FS09Reason::Make(TEXT("why.syncing"));
  Arbiter->Press(Id, Arbiter->Now());
  OnPressOutcome(Id, FS09HudPressArbiter::Decide(Arbiter->Release(Id, Arbiter->Now()), Why));
}
