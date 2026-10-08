# SC-06 — LOGIN: пустая форма и ввод (`UUmScreenLogin`)

VS-7, шаг S1, 2026-10-08, ветка `feat/visual-vs7` (worktree `C:/tmp/wt-visual`). Карточка — `screens.csv` SC-06; 04 §1.2, §3.1,
§3.4; принятый макет CX-28 `art/imagegen/sc06-login-form-codex/` (ВР-VS4-SC06-01…09). Тот же экран несёт
[SC-07](../SC-07/README.md); сборки, общие тесты и гейты — [SC-03](../SC-03/README.md); фон — [SC-02](../SC-02/README.md).

**Статус:** UE-часть готова, живая проверка editor-build на основном бэкенде, по делегированию. Набор G packaged, листы цвет /
серый / дейтеранопия, G-READ / G-GRAY / G-LOOK — шаг «Кадры». **Откат:** `-S08SlateHud=login` — прежняя серая форма.

## Что сделано (`do`)

| Пункт | Где и как |
|---|---|
| Экран | `UUmScreenLogin : UUmScreenBase` (`S08/UI/UmScreenLogin.h/.cpp`), WBP `/Game/S08/UI/Screens/WBP_UI_SCR_LOGIN`, в `Screens` корня. Карточка = рамка 480×420 su по центру (скин `modal`). |
| BindWidget | `Title` «Вход», `EmailLabel` / `PasswordLabel` над полями во всех состояниях (шаг 88 su, ВР-VS4-SC06-02), `EmailBox` / `PasswordBox` (`UEditableTextBox`, скины `input.normal` / `input.focus`, `type.body`), `PasswordMask`, `RevealButton` (слот 24 su пуст, свёрнут — глифа нет в v3, ВР-VS4-SC06-03), `SubmitButton` 432×48 главная, `SubmitSpinner`, `ErrorIcon`, `ErrorText`, `WhyText`; `LangRu` / `LangEn` — чипы 48×32 справа внизу экрана (выбран — `state.pending`). |
| Состояния | empty — «Войти» disabled с `why.login.fields` («Заполните email и пароль») под кнопкой, фокус в Email при показе; input — оба поля, «Войти» главная (с клавиатурой — кольцо фокуса). Ссылки регистрации нет (Q-005). |
| Фокус | Tab / Shift+Tab: Email → Пароль → «Войти» → RU → EN; Enter в Email — к паролю, иначе отправка ровно один раз (повтор клавиши и Enter во время отправки отбрасываются). Экран фокусируемый: кольцо рисуется на кнопке. |
| Пароль | никогда не в трассе и логе (проверено: 0 вхождений в 21 трассе / логе прогонов); поле рисует маску 8 точек фиксированной длины, свои глифы прозрачны (ВР-VS7-05). |
| Язык | чипы RU / EN — `UmText::SetUiLanguage`, тексты экрана в той же кадре; звук `UI-TOGGLE`. |
| Звук | `UI-BTN-CLICK` на отправку; `UI-LOGIN-OK` / `UI-LOGIN-ERR` звучат сами (аудио-чат). |
| Трасса | `SHOT widget id=UI-SCR-LOGIN impl=umg state=empty|input|busy|error … error=-|credentials|server focus=<…> filled=<email><password> lang=ru|en primary=1` — без значений полей; `LOGIN submit source=umg`, `LOGIN error code=<код> shown=<…>`. |
| Строки | `screens.login.lang.ru` / `.en` (новые); остальные `screens.login.*` уже были. |
| Корень | Slate-панель потока скрыта, пока экран UMG маршрута открыт (`UpdateLegacyRootVisibility`, 1 строка); курсор «занято» во время входа (`TickCursors`, 1 строка в `S08FlowGameModeUmHud.cpp`). |

## Решения по делегированию

| № | Решение | Почему |
|---|---|---|
| ВР-VS7-05 | В игре поле пароля тоже всегда показывает 8 точек фиксированной длины, пока в нём что-то есть | ВР-SC09: длина не раскрывается ни в одном кадре; иначе каждый кадр доказательств её показывал бы |

## Проверка

- Тесты `Unmatched.S08.Hud.Screens.Login.Tree` (части кодом и из WBP, тексты RU, empty / input / busy / error, маска 8 точек
  у пароля длины 1, в строке SHOT нет email и пароля, Tab-порядок) и `.Login.Enter` («Enter — одна отправка»: Enter, Enter, повтор
  клавиши и клик во время отправки — один вход; пустое поле — ни одного) — PASS.
- Живые прогоны: `a2` 1080p (empty → input с кольцом на «ВОЙТИ» → отправка), `b1` 720p 150 % (класс S).
- Открыты (Read): empty 1080p (`a1` — размытые мипы первого кадра, `a2` — чистый), input 1080p (`a1` без кольца, `a2` с кольцом),
  empty 720p 150 %, откат `menubg`.

## Кадры в git (editor-build, не приёмка; email — тестовый аккаунт демо-хоста, пароль — маска)

`login-empty-1080p-100.jpg`, `login-input-1080p-100.jpg`, `login-empty-720p-150.jpg`.

## Не сделано в этом шаге

- Глиф «показать пароль» — нужна карточка IC; до неё `RevealButton` свёрнут.
- Набор G packaged и листы, статус в реестре 03 и `screens.csv` — шаг «Кадры». Бюджет экрана ≤ 0,5 мс GT / 0,3 мс GPU не мерился.
