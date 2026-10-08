# SC-07 — LOGIN: вход и ошибки (состояния `busy` и `error` в `UUmScreenLogin`)

VS-7, шаг S1, 2026-10-08, ветка `feat/visual-vs7`. Карточка — `screens.csv` SC-07; 04 §1.2, §3.1, §3.3, §3.7; принятый макет CX-28
`art/imagegen/sc07-login-errors-codex/` (ВР-VS4-SC07-01…05). Экран — [SC-06](../SC-06/README.md); сборки, тесты, гейты —
[SC-03](../SC-03/README.md).

**Статус:** UE-состояния готовы, живая проверка editor-build с реальными кодами бэкенда, по делегированию. Набор G packaged и
листы — шаг «Кадры». **Откат:** `-S08SlateHud=login`.

## Что сделано

- busy: «ВХОД…» (`screens.login.busy`) в главной кнопке в disabled-скине, причина `why.syncing` — подсказка; спиннер `UUmSpinner`
  32 su слева от подписи после 300 мс (HB-47); поля заблокированы (значения в `text.secondary`); курсор «занято» (HB-12);
  повторная отправка до ответа отбрасывается.
- error.credentials: `badge-refuse` 24 su (IC-40) + «Неверный email или пароль»; email сохранён, пароль очищен, фокус в пароле;
  ни одно поле не помечено (не сказано, что неверно); «Войти» снова disabled с `why.login.fields` второй строкой.
- error.server: `resource-connection-lost` 24 su + «Сервер недоступен»; пароль сохранён; «Повторить» (`common.btn.retry`) в слоте
  «Войти» — главная с кольцом фокуса. Красный — только X двух значков.
- Коды бэкенда (`FS08FlowController::Login` → `OnFlowError`), ВР-VS7-09: `UNAUTHENTICATED` (ответ `AuthService.login` на неверную
  пару), `BAD_USER_INPUT`, `BAD_REQUEST`, `FORBIDDEN` → учётные данные; остальное (`PARSE` — нет ответа, 5xx, лимит) → сервер.
  Ввод в поле снимает показанную ошибку.

## Проверка

- Тест `Unmatched.S08.Hud.Screens.Login.Tree` (busy: подпись, disabled + `why.syncing`, поля заблокированы; credentials: текст,
  пароль очищен, фокус; server: «Повторить», пароль сохранён, кольцо; коды) — PASS.
- Живые прогоны:
  - `a2` (основной бэкенд через прокси, ответ `login` задержан 3 с): неверный пароль аккаунта демо-хоста → busy 3 с →
    `LOGIN failed: Неверный email или пароль`, `LOGIN error code=UNAUTHENTICATED shown=credentials`, звук `UI-LOGIN-ERR` → верный →
    `LOGIN ok`;
  - `b1` (720p 150 %, `-S08Api` на закрытый порт :3199): `LOGIN error code=PARSE shown=server`.
- Открыты (Read): busy 1080p (`a1` без спиннера — кадр раньше 300 мс; `a2` — спиннер налезал на подпись, исправлено: слева от
  подписи), busy 720p 150 %, error.credentials 1080p, error.server 720p 150 %.

## Кадры в git (editor-build, не приёмка)

`login-busy-720p-150.jpg`, `login-error-credentials-1080p-100.jpg`, `login-error-server-720p-150.jpg`.

## Не сделано в этом шаге

- Ошибка учётных данных на стенде S09 (проверена на основном бэкенде тем же кодом `UNAUTHENTICATED`), набор G packaged и
  листы — шаг «Кадры». Курсор «занято» в кадры не попадает (программный курсор не снимается).
