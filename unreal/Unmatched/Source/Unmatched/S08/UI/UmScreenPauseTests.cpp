// VS-7 S4 automation tests (docs/game-design/visual/06-tasks/screens.csv SC-24...SC-30; 04-hud-spec.md §1.8):
//   Unmatched.S08.Hud.Screens.Pause.Tree   PAUSE's parts from the code tree and from WBP_UI_SCR_PAUSE; RU texts; game (the running
//                                          line, «Покинуть партию» with the X, «Продолжить» the one primary), game.defense
//                                          («До конца окна защиты 30 с»), syncing (leave disabled, why.syncing, the press
//                                          refused), menu from LOBBY (no leave), ROOM («Выйти из комнаты»); the four tabs with
//                                          their rows and the S08UserSettings.h defaults (no shake row); the commits of a slider
//                                          (on the release, UI-SLIDER-TICK per 10 %), a mute, a check and a chip; Esc =
//                                          «Продолжить»; the canvases 1080p 100 / 150 %, 720p 100 / 150 % (the rows scroll,
//                                          the footer stays visible); EN and the pseudo-locale +30 % at 720p 150 % (nothing
//                                          past its row).
//   Unmatched.S08.Hud.Screens.Pause.Model  the pure rules: UmPause::Rows defaults, the 720p scale minimum and its note,
//                                          MaxModalHSu, the slider snap, UmText::Pseudo, US08UserSettings language
//                                          (ApplySetting / ResolveLanguage / NormalizeLanguage; Describe unchanged).
// Headless: node tools/s08/run-ue-tests.cjs "Unmatched.S08.Hud.Screens" <abs log>
#if WITH_AUTOMATION_TESTS

#include "../S08UserSettings.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Internationalization/Internationalization.h"
#include "Internationalization/TextLocalizationManager.h"
#include "Misc/AutomationTest.h"
#include "UmButton.h"
#include "UmScreenPause.h"
#include "UmSettingRow.h"
#include "UmText.h"
#include "UObject/Package.h"

namespace UmPauseTest {
struct FWorld {
  UWorld* World = nullptr;
  explicit FWorld(const TCHAR* Name) {
    World = UWorld::CreateWorld(EWorldType::Game, false, FName(Name));
    if (World) GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
  }
  ~FWorld() {
    if (!World) return;
    GEngine->DestroyWorldContext(World);
    World->DestroyWorld(false);
  }
};

struct FPauseCulture {
  FInternationalization::FCultureStateSnapshot Snapshot;
  explicit FPauseCulture(const TCHAR* Culture) {
    FInternationalization::Get().BackupCultureState(Snapshot);
    Set(Culture);
  }
  static void Set(const TCHAR* Culture) {
    FInternationalization::Get().SetCurrentLanguageAndLocale(Culture);
#if WITH_EDITOR
    FTextLocalizationManager::Get().EnableGameLocalizationPreview(Culture);
#endif
    FTextLocalizationManager::Get().WaitForAsyncTasks();
  }
  ~FPauseCulture() {
#if WITH_EDITOR
    FTextLocalizationManager::Get().DisableGameLocalizationPreview();
#endif
    FInternationalization::Get().RestoreCultureState(Snapshot);
  }
};

FString Pct(int32 N) { return UmSettingRow::Percent(N).ToString(); }
}  // namespace UmPauseTest

using namespace UmPauseTest;

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmScreensPauseModelTest, "Unmatched.S08.Hud.Screens.Pause.Model",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FUmScreensPauseModelTest::RunTest(const FString& Parameters) {
  UmPauseTest::FPauseCulture Ru(TEXT("ru"));
  // ---- the rows of the defaults (S08UserSettings.h; ВР-VS5-SC25-01, -SC26-01, -SC28-01, -SC30-01)
  const FUmPauseModel M;
  const TArray<FUmSettingRowModel> Sound = UmPause::Rows(M, EUmPauseTab::Sound);
  TestEqual(TEXT("sound: 8 rows"), Sound.Num(), 8);
  if (Sound.Num() == 8) {
    const TCHAR* Keys[] = {TEXT("master"), TEXT("music"), TEXT("sfx"), TEXT("ui"), TEXT("vo"), TEXT("ambience"), TEXT("subtitles"), TEXT("describeSounds")};
    const int32 Values[] = {100, 60, 80, 80, 80, 60};
    for (int32 I = 0; I < 8; ++I) TestEqual(FString::Printf(TEXT("sound row %d key"), I), Sound[I].Key, FName(Keys[I]));
    for (int32 I = 0; I < 6; ++I) TestEqual(FString::Printf(TEXT("sound row %d default"), I), Sound[I].Value, Values[I]);
    TestEqual(TEXT("master + mute"), Sound[0].MuteKey, FName(TEXT("masterMute")));
    TestEqual(TEXT("ambience + mute"), Sound[5].MuteKey, FName(TEXT("ambienceMute")));
    TestTrue(TEXT("the other buses have no mute"), Sound[1].MuteKey.IsNone() && Sound[4].MuteKey.IsNone());
    TestTrue(TEXT("subtitles on, describe off"), Sound[6].bOn && !Sound[7].bOn);
  }
  const US08UserSettings* Cdo = GetDefault<US08UserSettings>();
  const FS08AudioSettings D;
  TestTrue(TEXT("the model defaults are the settings defaults"),
           M.Master == D.MasterPercent && M.Music == D.MusicPercent && M.Sfx == D.SfxPercent && M.Ui == D.UiPercent && M.Vo == D.VoPercent &&
               M.Ambience == D.AmbiencePercent && M.bSubtitles == D.bSubtitles && M.bDescribeSounds == D.bDescribeSounds &&
               M.AnimSpeed == TEXT("normal") && !M.bReducedMotion && M.bRuleHints && M.KeyHints == TEXT("auto") && M.UiScale == 100);
  TestTrue(TEXT("the class defaults (UI-ACC-010 ru)"), Cdo && US08UserSettings::NormalizeLanguage(Cdo->Language) == TEXT("ru"));
  const TArray<FUmSettingRowModel> Ui = UmPause::Rows(M, EUmPauseTab::Interface);
  TestEqual(TEXT("interface: 4 rows"), Ui.Num(), 4);
  if (Ui.Num() == 4) {
    TestEqual(TEXT("language chips"), Ui[0].Chips.Num(), 2);
    TestEqual(TEXT("«Русский» selected"), Ui[0].Selected, 0);
    TestEqual(TEXT("«Русский»"), Ui[0].Chips[0].ToString(), FString(TEXT("Русский")));
    TestEqual(TEXT("«English»"), Ui[0].Chips[1].ToString(), FString(TEXT("English")));
    TestTrue(TEXT("scale 75..150 step 5"), Ui[1].Min == 75 && Ui[1].Max == 150 && Ui[1].Step == 5 && Ui[1].Value == 100);
    TestEqual(TEXT("scale note «75–150 %»"), Ui[1].Note.ToString(), FString(TEXT("75–150 %")));
    TestTrue(TEXT("rule hints on"), Ui[2].Kind == EUmSettingKind::Check && Ui[2].bOn);
    TestTrue(TEXT("key hints Авто + note + sample"), Ui[3].Selected == 0 && Ui[3].bSample && Ui[3].bSampleChip &&
                                                        Ui[3].Note.ToString() == TEXT("Авто — только в первой партии"));
  }
  FUmPauseModel M720 = M;
  M720.UiScaleMin = 100;
  M720.UiScale = 75;
  const TArray<FUmSettingRowModel> Ui720 = UmPause::Rows(M720, EUmPauseTab::Interface);
  if (Ui720.Num() == 4) {
    TestTrue(TEXT("720p: the slider starts at 100 (ВР-62)"), Ui720[1].Min == 100 && Ui720[1].Value == 100);
    TestEqual(TEXT("720p note «100–150 %»"), Ui720[1].Note.ToString(), FString(TEXT("100–150 %")));
  }
  const TArray<FUmSettingRowModel> Game = UmPause::Rows(M, EUmPauseTab::Game);
  TestEqual(TEXT("game: 2 rows (no shake, ВР-SC06)"), Game.Num(), 2);
  if (Game.Num() == 2) {
    TestEqual(TEXT("4 speed chips"), Game[0].Chips.Num(), 4);
    TestEqual(TEXT("«Обычно» selected"), Game[0].Chips.IsValidIndex(Game[0].Selected) ? Game[0].Chips[Game[0].Selected].ToString() : FString(),
              FString(TEXT("Обычно")));
    TestTrue(TEXT("reduced motion off"), !Game[1].bOn);
  }
  for (const FUmSettingRowModel& R : Game) TestFalse(TEXT("no shake row"), R.Key == FName(TEXT("shake")));
  const TArray<FUmSettingRowModel> Gfx = UmPause::Rows(M, EUmPauseTab::Graphics);
  TestEqual(TEXT("graphics: 1 row"), Gfx.Num(), 1);
  if (Gfx.Num() == 1) {
    TestEqual(TEXT("«Высокое» selected"), Gfx[0].Selected, 0);
    TestEqual(TEXT("the values 2 / 1 / 0"), FString::Join(Gfx[0].ChipValues, TEXT(",")), FString(TEXT("2,1,0")));
    TestEqual(TEXT("the note"), Gfx[0].Note.ToString(), FString(TEXT("Масштаб экрана 100 % и лимит 60 кадров/с не меняются")));
  }
  // ---- the modal cap of 04 §1.8
  TestEqual(TEXT("1080p cap 800"), UmPause::MaxModalHSu(FVector2D(1920.0, 1080.0), false), 800.0f);
  TestEqual(TEXT("720p cap 864"), UmPause::MaxModalHSu(FVector2D(1707.0, 960.0), false), 864.0f);
  TestEqual(TEXT("720p 150 % (S) 608"), UmPause::MaxModalHSu(FVector2D(1138.0, 640.0), true), 608.0f);
  TestEqual(TEXT("1080p 150 % (S) 688"), UmPause::MaxModalHSu(FVector2D(1280.0, 720.0), true), 688.0f);
  // ---- the slider snap
  FUmSettingRowModel S;
  S.Min = 0;
  S.Max = 100;
  S.Step = 5;
  TestEqual(TEXT("left end = min"), UmSettingRow::ValueAtX(S, 148.0f), 0);
  TestEqual(TEXT("right end = max"), UmSettingRow::ValueAtX(S, 348.0f), 100);
  TestEqual(TEXT("snap to 5"), UmSettingRow::ValueAtX(S, 148.0f + 200.0f * 0.43f), 45);
  TestEqual(TEXT("past the track clamps"), UmSettingRow::ValueAtX(S, 900.0f), 100);
  TestEqual(TEXT("tick band"), UmSettingRow::TickBand(55), 5);
  // ---- the pseudo-locale (ВР-VS5-SC26-03, ВР-VS7-45)
  TestEqual(TEXT("pseudo «Пауза»"), UmText::Pseudo(TEXT("Пауза")), FString(TEXT("[Пауза~~]")));
  TestTrue(TEXT("pseudo >= +30 %"), UmText::Pseudo(TEXT("Скорость анимации")).Len() >= FMath::CeilToInt(1.3f * 17));
  // ---- the language field (UI-ACC-010)
  US08UserSettings* Probe = NewObject<US08UserSettings>(GetTransientPackage());
  FString Error;
  TestTrue(TEXT("language=en"), Probe->ApplySetting(TEXT("language"), TEXT("EN"), Error) && Probe->Language == TEXT("en"));
  TestFalse(TEXT("language=de refused"), Probe->ApplySetting(TEXT("language"), TEXT("de"), Error));
  TestFalse(TEXT("language=pseudo refused (a run flag only)"), Probe->ApplySetting(TEXT("language"), TEXT("pseudo"), Error));
  TestEqual(TEXT("describe"), Probe->DescribeLanguage(), FString(TEXT("language=en")));
  TestFalse(TEXT("Describe keeps its text"), Probe->Describe().Contains(TEXT("language")));
  Probe->SetToDefaults();
  TestEqual(TEXT("defaults: ru"), Probe->Language, FString(TEXT("ru")));
  TestEqual(TEXT("flag en wins"), US08UserSettings::ResolveLanguage(TEXT("ru"), TEXT("-game -S08Lang=en")), FString(TEXT("en")));
  TestEqual(TEXT("flag pseudo"), US08UserSettings::ResolveLanguage(TEXT("en"), TEXT("-S08Lang=pseudo")), FString(TEXT("pseudo")));
  TestEqual(TEXT("bad flag keeps the saved"), US08UserSettings::ResolveLanguage(TEXT("en"), TEXT("-S08Lang=xx")), FString(TEXT("en")));
  TestEqual(TEXT("unknown saved -> ru"), US08UserSettings::NormalizeLanguage(TEXT("fr")), FString(TEXT("ru")));
  // no MarkAsGarbage: in the full S08+S09+S10 run it raced an engine writer thread (MTAccessDetector ensure); the GC
  // takes the transient probe
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmScreensPauseTreeTest, "Unmatched.S08.Hud.Screens.Pause.Tree",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FUmScreensPauseTreeTest::RunTest(const FString& Parameters) {
  UmPauseTest::FPauseCulture Ru(TEXT("ru"));
  FWorld W(TEXT("UmPauseTree"));
  if (!TestNotNull(TEXT("world"), W.World)) return false;
  for (int32 Pass = 0; Pass < 2; ++Pass) {
    UClass* Class = Pass == 0 ? UUmScreenPause::StaticClass() : UUmScreenPause::WidgetClass();
    if (Pass == 1 && Class == UUmScreenPause::StaticClass()) {
      AddInfo(TEXT("WBP_UI_SCR_PAUSE not authored yet - the code tree only"));
      continue;
    }
    UUmScreenPause* P = CreateWidget<UUmScreenPause>(W.World, Class);
    FString Missing;
    TestTrue(FString::Printf(TEXT("pass %d: every part (%s)"), Pass, *Missing), P && P->HasAllParts(&Missing));
    if (!P) continue;
    int32 Continues = 0, Leaves = 0, Ticks = 0, Toggles = 0;
    TArray<FString> Commits;
    UUmScreenPause::FInput In;
    In.OnContinue = [&]() { ++Continues; };
    In.OnLeave = [&]() { ++Leaves; };
    In.OnCommit = [&](FName K, const FString& V) { Commits.Add(K.ToString() + TEXT("=") + V); };
    In.OnSound = [&](FName B) {
      Ticks += B == FName(TEXT("UI-SLIDER-TICK")) ? 1 : 0;
      Toggles += B == FName(TEXT("UI-TOGGLE")) ? 1 : 0;
    };
    P->SetInput(MakeShared<FS09HudPressArbiter>(), MoveTemp(In));
    P->ApplyCanvas(FVector2D(1920.0, 1080.0), false, 1.0f);
    FUmPauseModel M;
    P->ApplyModel(M);
    P->PlayShow();
    // ---- game
    TestEqual(TEXT("state = the open tab"), P->GetScreenState(), FName(TEXT("sound")));
    TestEqual(TEXT("«Пауза»"), P->GetTitleText(), FString(TEXT("Пауза")));
    TestTrue(TEXT("«Партия продолжается»"), P->IsRunningShown() && P->GetRunningText() == TEXT("Партия продолжается"));
    TestFalse(TEXT("no defense line"), P->IsDefenseShown());
    TestTrue(TEXT("«Покинуть партию» enabled"), P->IsLeaveShown() && P->IsLeaveEnabled() && P->GetLeaveText() == TEXT("Покинуть партию"));
    TestEqual(TEXT("the X of leave"), P->LeaveButton->GetModel().IconName, FName(TEXT("badge-refuse")));
    TestEqual(TEXT("one primary («Продолжить»)"), P->PrimaryCount(), 1);
    TestTrue(TEXT("the open tab selected"), P->GetTabButton(EUmPauseTab::Sound)->GetModel().bSelected &&
                                                !P->GetTabButton(EUmPauseTab::Game)->GetModel().bSelected);
    TestEqual(TEXT("8 sound rows"), P->RowCount(), 8);
    TestFalse(TEXT("1080p: no scroll"), P->IsScrolling());
    TestTrue(TEXT("1080p: <= 800 su"), P->GetModalHeightSu() <= 800.0f);
    if (UUmSettingRow* R = P->FindRow(FName(TEXT("master")))) {
      TestEqual(TEXT("«Общая громкость»"), R->GetLabelText(), FString(TEXT("Общая громкость")));
      TestEqual(TEXT("«100 %»"), R->GetValueText(), Pct(100));
      R->SimulateDrag(50);
      TestEqual(TEXT("slider commit on the release"), Commits.Num() > 0 ? Commits.Last() : FString(), FString(TEXT("master=50")));
      TestEqual(TEXT("a tick per 10 % (100 -> 50)"), Ticks, 5);
      R->SimulateToggle(true);
      TestEqual(TEXT("mute"), Commits.Last(), FString(TEXT("masterMute=1")));
    }
    if (UUmSettingRow* R = P->FindRow(FName(TEXT("music")))) TestEqual(TEXT("music 60 %"), R->GetValueText(), Pct(60));
    if (UUmSettingRow* R = P->FindRow(FName(TEXT("ambience")))) TestEqual(TEXT("ambience 60 %"), R->GetValueText(), Pct(60));
    if (UUmSettingRow* R = P->FindRow(FName(TEXT("subtitles")))) {
      TestEqual(TEXT("subtitles «вкл»"), R->GetValueText(), FString(TEXT("вкл")));
      R->SimulateToggle(false);
      TestEqual(TEXT("check commit"), Commits.Last(), FString(TEXT("subtitles=0")));
    }
    if (UUmSettingRow* R = P->FindRow(FName(TEXT("describeSounds")))) TestEqual(TEXT("describe «выкл»"), R->GetValueText(), FString(TEXT("выкл")));
    TestTrue(TEXT("toggles sound UI-TOGGLE"), Toggles >= 2);
    TestTrue(TEXT("shot: context, primary"), P->ShotExtra().Contains(TEXT("context=game")) && P->ShotExtra().Contains(TEXT("primary=continue")) &&
                                                 P->ShotExtra().Contains(TEXT("leave=enabled")));
    // ---- game.defense
    M.DefenseSeconds = 30;
    P->ApplyModel(M);
    TestTrue(TEXT("«До конца окна защиты 30 с»"), P->IsDefenseShown() && P->GetDefenseText() == TEXT("До конца окна защиты 30 с"));
    // ---- syncing
    M.bSyncing = true;
    P->ApplyModel(M);
    TestTrue(TEXT("syncing: leave disabled + why"), P->IsLeaveShown() && !P->IsLeaveEnabled() && P->GetLeaveWhy() == TEXT("Синхронизация…"));
    P->SimulatePress(FName(TEXT("screens.pause.leave")));
    TestEqual(TEXT("a disabled leave sends nothing"), Leaves, 0);
    M.bSyncing = false;
    M.DefenseSeconds = -1;
    P->ApplyModel(M);
    P->SimulatePress(FName(TEXT("screens.pause.leave")));
    TestEqual(TEXT("leave pressed"), Leaves, 1);
    // ---- menu (LOBBY) and ROOM
    M.Context = EUmPauseContext::Lobby;
    P->ApplyModel(M);
    TestTrue(TEXT("menu: no leave, no running line"), !P->IsLeaveShown() && !P->IsRunningShown());
    TestEqual(TEXT("menu: one primary"), P->PrimaryCount(), 1);
    M.Context = EUmPauseContext::Room;
    P->ApplyModel(M);
    TestEqual(TEXT("ROOM: «Выйти из комнаты»"), P->GetLeaveText(), FString(TEXT("Выйти из комнаты")));
    M.Context = EUmPauseContext::Game;
    P->ApplyModel(M);
    // ---- the tabs
    P->SimulatePress(FName(TEXT("screens.pause.tab.interface")));
    TestEqual(TEXT("interface"), P->GetScreenState(), FName(TEXT("interface")));
    TestEqual(TEXT("4 interface rows"), P->RowCount(), 4);
    if (UUmSettingRow* R = P->FindRow(FName(TEXT("language")))) {
      TestEqual(TEXT("«Русский» chosen"), R->GetValueText(), FString(TEXT("Русский")));
      R->SimulateChip(1);
      TestEqual(TEXT("chip commit"), Commits.Last(), FString(TEXT("language=en")));
    }
    if (UUmSettingRow* R = P->FindRow(FName(TEXT("uiScale")))) {
      TestEqual(TEXT("scale 100 %"), R->GetValueText(), Pct(100));
      TestEqual(TEXT("scale note"), R->GetNoteText(), FString(TEXT("75–150 %")));
    }
    if (UUmSettingRow* R = P->FindRow(FName(TEXT("keyHints")))) {
      TestTrue(TEXT("the END TURN sample with its chip"), R->IsSampleShown() && R->IsSampleChipShown());
      TestEqual(TEXT("note"), R->GetNoteText(), FString(TEXT("Авто — только в первой партии")));
    }
    P->SimulatePress(FName(TEXT("screens.pause.tab.game")));
    TestEqual(TEXT("game tab"), P->GetScreenState(), FName(TEXT("game")));
    TestTrue(TEXT("no shake row"), P->FindRow(FName(TEXT("shake"))) == nullptr && P->RowCount() == 2);
    if (UUmSettingRow* R = P->FindRow(FName(TEXT("speed")))) {
      TestEqual(TEXT("«Обычно»"), R->GetValueText(), FString(TEXT("Обычно")));
      if (UUmButton* C = R->GetChip(2)) TestTrue(TEXT("the selected chip btn.selected"), C->GetModel().bSelected);
      R->SimulateChip(0);
      TestEqual(TEXT("speed commit"), Commits.Last(), FString(TEXT("speed=none")));
    }
    P->SimulatePress(FName(TEXT("screens.pause.tab.graphics")));
    if (UUmSettingRow* R = P->FindRow(FName(TEXT("graphics")))) {
      TestEqual(TEXT("«Высокое»"), R->GetValueText(), FString(TEXT("Высокое")));
      R->SimulateChip(2);
      TestEqual(TEXT("graphics commit"), Commits.Last(), FString(TEXT("graphics=0")));
    }
    TestTrue(TEXT("Esc = «Продолжить»"), P->HandleEscape() && Continues == 1);
    // ---- the canvases: every row fits, the footer stays visible, the rows scroll where they must
    struct FCanvas {
      FVector2D Su;
      bool bS;
      float Px;
      bool bScrollSound;
    };
    const FCanvas Canvases[] = {{FVector2D(1920.0, 1080.0), false, 1.0f, false},
                                {FVector2D(1280.0, 720.0), true, 1.5f, true},
                                {FVector2D(1707.0, 960.0), false, 0.75f, false},
                                {FVector2D(1138.0, 640.0), true, 1.125f, true}};
    auto CheckAll = [&](const TCHAR* Lang) {
      for (const FCanvas& C : Canvases) {
        P->ApplyCanvas(C.Su, C.bS, C.Px);
        for (int32 T = 0; T < 4; ++T) {
          P->SetTab(static_cast<EUmPauseTab>(T));
          const FString Where = FString::Printf(TEXT("%s %.0fx%.0f tab %s"), Lang, C.Su.X, C.Su.Y, UmPause::TabName(static_cast<EUmPauseTab>(T)));
          TestTrue(FString::Printf(TEXT("%s: footer visible"), *Where), P->FooterVisible());
          for (int32 I = 0; I < P->RowCount(); ++I) {
            FString Why;
            if (UUmSettingRow* R = P->GetRow(I)) TestTrue(FString::Printf(TEXT("%s row %d fits (%s)"), *Where, I, *Why), R->LayoutFits(&Why));
          }
          if (T == 0 && FCString::Strcmp(Lang, TEXT("ru")) == 0) {
            TestEqual(FString::Printf(TEXT("%s: scroll"), *Where), P->IsScrolling(), C.bScrollSound);
            if (P->IsScrolling()) {
              P->ScrollBy(10000.0f);
              TestTrue(FString::Printf(TEXT("%s: scrolled to the end"), *Where),
                       FMath::IsNearlyEqual(P->GetScrollSu(), P->GetTotalRowsSu() - P->GetVisibleRowsSu(), 0.5f));
              P->ScrollTo(0.0f);
            }
          }
        }
      }
      P->SetTab(EUmPauseTab::Sound);
    };
    CheckAll(TEXT("ru"));
    // ---- EN (SourceString)
    UmPauseTest::FPauseCulture::Set(TEXT("en"));
    M.Language = TEXT("en");  // the owner feeds the current culture: a new language re-lays the modal out
    P->ApplyModel(M);
    TestEqual(TEXT("EN title"), P->GetTitleText(), FString(TEXT("Pause")));
    if (UUmSettingRow* R = P->FindRow(FName(TEXT("master")))) TestEqual(TEXT("EN master"), R->GetLabelText(), FString(TEXT("Master volume")));
    CheckAll(TEXT("en"));
    UmPauseTest::FPauseCulture::Set(TEXT("ru"));
    M.Language = TEXT("ru");
    // ---- the pseudo-locale +30 % (set I, 720p 150 %)
    UmText::SetPseudoForTest(true);
    UUmScreenPause* Q = CreateWidget<UUmScreenPause>(W.World, Class);
    if (Q) {
      Q->SetInput(MakeShared<FS09HudPressArbiter>(), UUmScreenPause::FInput());
      Q->ApplyCanvas(FVector2D(1138.0, 640.0), true, 1.125f);
      Q->ApplyModel(M);
      TestTrue(TEXT("pseudo title"), Q->GetTitleText().StartsWith(TEXT("[Пауза~")));
      for (int32 T = 0; T < 4; ++T) {
        Q->SetTab(static_cast<EUmPauseTab>(T));
        TestTrue(TEXT("pseudo footer visible"), Q->FooterVisible());
        for (int32 I = 0; I < Q->RowCount(); ++I) {
          FString Why;
          if (UUmSettingRow* R = Q->GetRow(I)) TestTrue(FString::Printf(TEXT("pseudo tab %d row %d fits (%s)"), T, I, *Why), R->LayoutFits(&Why));
        }
      }
    }
    UmText::SetPseudoForTest(false);
  }
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
