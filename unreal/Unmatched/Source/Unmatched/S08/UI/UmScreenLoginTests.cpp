// VS-7 S1 automation tests (docs/game-design/visual/06-tasks/screens.csv SC-06, SC-07; 04-hud-spec.md §1.2, §3.1, §3.4):
//   Unmatched.S08.Hud.Screens.Login.Tree   LOGIN's parts from the code tree and from WBP_UI_SCR_LOGIN; the RU texts;
//                                          empty («Войти» disabled with why.login.fields) -> input (one primary, the
//                                          password as 8 dots whatever its length, ВР-SC09) -> busy («Вход…», disabled,
//                                          fields locked) -> error.credentials (badge-refuse text, the password cleared and
//                                          focused) / error.server («Повторить» in the submit slot); the backend codes; the
//                                          Tab order; no field value in the SHOT line.
//   Unmatched.S08.Hud.Screens.Login.Enter  «Enter — одна отправка»: Enter, Enter again, a key repeat and a click while
//                                          busy send exactly one login; an empty field sends none.
// Headless: node tools/s08/run-ue-tests.cjs "Unmatched.S08.Hud.Screens" <abs log>
#if WITH_AUTOMATION_TESTS

#include "Components/EditableTextBox.h"
#include "Components/TextBlock.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "InputCoreTypes.h"
#include "Internationalization/Internationalization.h"
#include "Internationalization/TextLocalizationManager.h"
#include "Misc/AutomationTest.h"
#include "UmButton.h"
#include "UmScreenLogin.h"

namespace UmLoginTest {
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

struct FRu {
  FInternationalization::FCultureStateSnapshot Snapshot;
  FRu() {
    FInternationalization::Get().BackupCultureState(Snapshot);
    FInternationalization::Get().SetCurrentLanguageAndLocale(TEXT("ru"));
#if WITH_EDITOR
    FTextLocalizationManager::Get().EnableGameLocalizationPreview(TEXT("ru"));
#endif
    FTextLocalizationManager::Get().WaitForAsyncTasks();
  }
  ~FRu() { FInternationalization::Get().RestoreCultureState(Snapshot); }
};

// test values only (never a real account's password)
const TCHAR* const TestEmail = TEXT("tester@example.test");
const TCHAR* const TestSecret = TEXT("q");
}  // namespace UmLoginTest

using namespace UmLoginTest;

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmScreensLoginTreeTest, "Unmatched.S08.Hud.Screens.Login.Tree",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FUmScreensLoginTreeTest::RunTest(const FString& Parameters) {
  FRu Ru;
  FWorld W(TEXT("UmLoginTree"));
  if (!TestNotNull(TEXT("world"), W.World)) return false;
  // the backend codes (AuthService.login: UNAUTHENTICATED; no answer: PARSE)
  TestTrue(TEXT("UNAUTHENTICATED -> credentials"), UmLogin::ClassifyError(TEXT("UNAUTHENTICATED")) == EUmLoginError::Credentials);
  TestTrue(TEXT("BAD_USER_INPUT -> credentials"), UmLogin::ClassifyError(TEXT("BAD_USER_INPUT")) == EUmLoginError::Credentials);
  TestTrue(TEXT("PARSE (no answer) -> server"), UmLogin::ClassifyError(TEXT("PARSE")) == EUmLoginError::Server);
  TestTrue(TEXT("INTERNAL_SERVER_ERROR -> server"), UmLogin::ClassifyError(TEXT("INTERNAL_SERVER_ERROR")) == EUmLoginError::Server);
  TestTrue(TEXT("Tab: email -> password -> submit -> ru -> en -> email"),
           UmLogin::NextFocus(EUmLoginFocus::Email, false) == EUmLoginFocus::Password &&
               UmLogin::NextFocus(EUmLoginFocus::Password, false) == EUmLoginFocus::Submit &&
               UmLogin::NextFocus(EUmLoginFocus::Submit, false) == EUmLoginFocus::LangRu &&
               UmLogin::NextFocus(EUmLoginFocus::LangEn, false) == EUmLoginFocus::Email &&
               UmLogin::NextFocus(EUmLoginFocus::Email, true) == EUmLoginFocus::LangEn);
  for (int32 Pass = 0; Pass < 2; ++Pass) {
    UClass* Class = Pass == 0 ? UUmScreenLogin::StaticClass() : UUmScreenLogin::WidgetClass();
    if (Pass == 1 && Class == UUmScreenLogin::StaticClass()) {
      AddInfo(TEXT("WBP_UI_SCR_LOGIN not authored yet - the code tree only"));
      continue;
    }
    UUmScreenLogin* L = CreateWidget<UUmScreenLogin>(W.World, Class);
    FString Missing;
    TestTrue(FString::Printf(TEXT("pass %d: every part (%s)"), Pass, *Missing), L && L->HasAllParts(&Missing));
    if (!L) continue;
    L->ApplyCanvas(FVector2D(1920.0, 1080.0), false, 1.0f);
    L->PlayShow();
    L->SetFieldsForTest(FString(), FString());
    TestEqual(TEXT("«Вход»"), L->Title->GetText().ToString(), FString(TEXT("Вход")));
    TestEqual(TEXT("empty"), L->GetScreenState(), FName(TEXT("empty")));
    TestTrue(TEXT("empty: «Войти» disabled with why.login.fields"),
             !L->IsSubmitEnabled() && L->SubmitButton->GetModel().Reason.Key == FName(TEXT("why.login.fields")));
    TestEqual(TEXT("«Войти»"), L->GetSubmitLabel(), FString(TEXT("Войти")));
    TestEqual(TEXT("the why line"), L->WhyText->GetText().ToString(), FString(TEXT("Заполните email и пароль")));
    TestTrue(TEXT("RU selected, EN normal"), L->LangRu->GetModel().bSelected && !L->LangEn->GetModel().bSelected);
    TestTrue(TEXT("no sign-up link; the reveal slot empty (ВР-VS4-SC06-03)"),
             L->RevealButton->GetVisibility() == ESlateVisibility::Collapsed);
    // input: the mask is 8 dots for a 1-character password (ВР-SC09)
    L->SetFieldsForTest(TestEmail, TestSecret);
    TestEqual(TEXT("input"), L->GetScreenState(), FName(TEXT("input")));
    TestTrue(TEXT("input: «Войти» primary, enabled"),
             L->IsSubmitEnabled() && L->SubmitButton->GetModel().Variant == EUmButtonVariant::Primary);
    TestEqual(TEXT("8 dots whatever the length"), L->GetMaskText(), UmLogin::Mask(true));
    TestEqual(TEXT("8 characters"), L->GetMaskText().Len(), 8);
    // the SHOT line never carries a value
    TArray<FString> Lines;
    L->CollectShotLines(Lines);
    TestTrue(TEXT("SHOT line UI-SCR-LOGIN state=input"), Lines.Num() == 1 && Lines[0].Contains(TEXT("id=UI-SCR-LOGIN")) &&
                                                            Lines[0].Contains(TEXT("state=input")) && Lines[0].Contains(TEXT("filled=11")));
    TestTrue(TEXT("no email, no password in the line"),
             Lines.Num() == 1 && !Lines[0].Contains(TestEmail) && !Lines[0].Contains(TEXT("password=")));
    // busy
    int32 Sent = 0;
    UUmScreenLogin::FInput In;
    In.OnSubmit = [&Sent](const FString&, const FString&) { ++Sent; };
    L->SetInput(MakeShared<FS09HudPressArbiter>(), MoveTemp(In));
    TestTrue(TEXT("submit"), L->Submit(TEXT("test")));
    TestEqual(TEXT("busy"), L->GetScreenState(), FName(TEXT("busy")));
    TestEqual(TEXT("«Вход…»"), L->GetSubmitLabel(), FString(TEXT("Вход…")));
    TestTrue(TEXT("busy: disabled with why.syncing"), !L->IsSubmitEnabled() && L->SubmitButton->GetModel().Reason.Key == FName(TEXT("why.syncing")));
    TestTrue(TEXT("busy: the fields locked"), L->EmailBox->GetIsReadOnly() && L->PasswordBox->GetIsReadOnly());
    // error.credentials: never which field; the password cleared and focused
    L->ShowError(EUmLoginError::Credentials);
    TestEqual(TEXT("error"), L->GetScreenState(), FName(TEXT("error")));
    TestEqual(TEXT("«Неверный email или пароль»"), L->GetErrorText(), FString(TEXT("Неверный email или пароль")));
    TestTrue(TEXT("the email kept, the password cleared"), L->HasEmail() && !L->HasPassword() && L->GetMaskText().IsEmpty());
    TestTrue(TEXT("the focus in the password"), L->GetFocus() == EUmLoginFocus::Password);
    TestTrue(TEXT("«Войти» disabled again (why.login.fields)"), !L->IsSubmitEnabled());
    // error.server: «Повторить» in the submit slot
    L->SetFieldsForTest(TestEmail, TestSecret);
    L->Submit(TEXT("test"));
    L->ShowError(EUmLoginError::Server);
    TestEqual(TEXT("«Сервер недоступен»"), L->GetErrorText(), FString(TEXT("Сервер недоступен")));
    TestEqual(TEXT("«Повторить»"), L->GetSubmitLabel(), FString(TEXT("Повторить")));
    TestTrue(TEXT("the password kept (not rejected)"), L->HasPassword());
    TestTrue(TEXT("«Повторить» primary, enabled, ring"), L->IsSubmitEnabled() && L->SubmitButton->GetModel().bFocused);
    TestEqual(TEXT("two submits sent"), Sent, 2);
    L->ResetAfterLogin();
    TestFalse(TEXT("after the login the password is forgotten"), L->HasPassword());
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmScreensLoginEnterTest, "Unmatched.S08.Hud.Screens.Login.Enter",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FUmScreensLoginEnterTest::RunTest(const FString& Parameters) {
  FRu Ru;
  FWorld W(TEXT("UmLoginEnter"));
  if (!TestNotNull(TEXT("world"), W.World)) return false;
  UUmScreenLogin* L = CreateWidget<UUmScreenLogin>(W.World, UUmScreenLogin::StaticClass());
  if (!TestNotNull(TEXT("login"), L)) return false;
  L->ApplyCanvas(FVector2D(1920.0, 1080.0), false, 1.0f);
  L->PlayShow();
  int32 Sent = 0;
  UUmScreenLogin::FInput In;
  In.OnSubmit = [&Sent](const FString&, const FString&) { ++Sent; };
  L->SetInput(MakeShared<FS09HudPressArbiter>(), MoveTemp(In));
  L->SetFieldsForTest(TestEmail, FString());
  L->SetFocusTo(EUmLoginFocus::Password);
  L->HandleKey(EKeys::Enter, false, false);
  TestEqual(TEXT("an empty password: nothing sent"), Sent, 0);
  L->SetFieldsForTest(TestEmail, TestSecret);
  L->SetFocusTo(EUmLoginFocus::Email);
  L->HandleKey(EKeys::Enter, false, false);
  TestEqual(TEXT("Enter in Email goes to the password"), Sent, 0);
  TestTrue(TEXT("the focus moved"), L->GetFocus() == EUmLoginFocus::Password);
  L->HandleKey(EKeys::Enter, false, false);
  L->HandleKey(EKeys::Enter, false, false);
  L->HandleKey(EKeys::Enter, false, true);
  L->SimulatePress(FName(TEXT("screens.login.submit")));
  TestEqual(TEXT("Enter, Enter, a repeat and a click while busy: one login"), Sent, 1);
  TestEqual(TEXT("one submit counted"), L->GetSubmitCount(), 1);
  return true;
}

#endif
