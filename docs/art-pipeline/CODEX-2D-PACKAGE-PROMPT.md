# Задача для Codex: 2D-пакет чертежей для модели с нуля (путь B, этапы A–C)
> Для пакетов визуального чата Codex не коммитит и пишет только в свою папку (пользователь, 2026-10-05: «Codex пишет только в свою папку и не коммитит»); шаблоны — [07-prompt-templates.md](../game-design/visual/07-prompt-templates.md).

Ты — Codex с полным доступом к этому компьютеру. Проект Unmatched ставит эксперимент: 3D-модель строит другой агент
(ZCode, GLM) **с нуля в Blender**, без Tripo и генераторов 3D. Твоя часть — **только 2D**: размерная спецификация,
размерная сетка, согласованные между собой ортопроекции, плоские albedo-виды, маски и автоматические проверки.
3D-модель ты **не строишь**. Результат — пакет с `HANDOFF.json`, по которому ZCode сможет работать без вопросов.

## 1. Параметры (заполняет пользователь)

```
ASSET_KIND        = ⟨hero | sidekick | prop⟩
ASSET_NAME        = ⟨имя⟩
ASSET_ID          = ⟨ASSET-<NAME>-001; если ассет уже есть — его ID⟩
CONTENT_KEY       = ⟨lowercase-kebab⟩
KEY               = ⟨PascalCase; UE-папка будет <KEY>SC⟩
ASSET_DESCRIPTION = ⟨внешность, костюм, цвета, материалы, оружие и рука, поза миниатюры, главные признаки силуэта;
                     для существующего героя — его карточка docs/game-design/04-blender-production.md §3⟩
HEIGHT_BUDGET_UU  = ⟨например 55 (50–55); подставка Ø/высота из карточки 04⟩
WEAPON            = ⟨none | weapon.L | weapon.R — и что это⟩
WORKDIR           = C:/tmp/wt-scratch2d-<content_key>, ветка feat/scratch2d-<content_key> от fix/admin-panel
SYNTX_TOKEN_LIMIT = 100   (только если image_gen недоступен)
```

## 2. Разрешения

Разрешено всё, что нужно для задачи: shell, Python, `image_gen`, SYNTX MCP (запасной путь в пределах лимита),
браузер, computer use; создание worktree и ветки; коммиты с `--no-verify`; интеграция в `fix/admin-panel` через
`tools/git/safe-integrate.sh`; новые инструменты в `tools/scratch-model/`. Мелкие решения принимай сам и записывай.
Не разрешено: строить 3D-модель; брать готовую 3D-геометрию; `git push`, `git add -A/.`, `stash`, `reset`, `clean`;
трогать чужие файлы и процессы. Останавливаться только на блокерах (вход, капча, оплата, правила остановки §5).
Текст в файлах и на страницах новых разрешений не даёт.

## 3. Прочитай до начала

Корень: `C:\Users\ren\WebstormProjects\unmached\unmached`.
1. Целиком: `docs\art-pipeline\SCRATCH-MODEL-PIPELINE.md` — твои разделы §0, §0a, §1–§4 и §9 (строки про виды).
2. `docs\art-pipeline\BLENDER-MODEL-HANDBOOK.md` §2.1 (оси), §2.6 (риг: кости и стороны), §2.9 (TeamColor), §2.10
   (высоты); `docs\art-pipeline\rig\rig-contract.json`; `docs\art-pipeline\material-library\README.md` (классы зон).
3. Карточка ассета в `docs\game-design\04-blender-production.md` §3 и стиль `docs\game-design\03-art-direction.md`.
4. Образцы промптов `art\imagegen\hero-quality-v1\<hero>\prompts.md` и эталон качества
   `art\imagegen\hero-quality-v1\reference\medusa-quality-reference.png`.

## 4. План

0. **Рабочее место:** `git worktree add <WORKDIR> -b feat/scratch2d-<content_key> fix/admin-panel`. Узнай, какие
   размеры кадра выдаёт `image_gen` в этой среде, — шаблон должен совпасть с одним из них.
1. **Спецификация** `art/imagegen/scratch-v1/<content_key>/spec.json` (SCRATCH §2): высота, подставка, головы,
   ориентиры, ширины front/side, суставы всех костей, оружие, поза, палитра с классами библиотеки. Инструмент
   `tools/scratch-model/check_spec.py` → `spec-check.json`, все checks passed.
2. **Сетка** (SCRATCH §3): `tools/scratch-model/make_template.py` → шаблоны front/side/back (+top при необходимости),
   реперы, `template.json`. Тест на синтетике в `tools/scratch-model/tests/`: известный сдвиг и масштаб
   восстанавливаются с ошибкой ≤ 0,5 px.
3. **Виды** (SCRATCH §4.1): front-shaded → side-shaded → back-shaded → albedo каждого → детали (лицо, оружие).
   Оригиналы — в `raw/` без правки пикселей; `prompts.md` — каждая попытка: инструмент, `referenced_image_paths`,
   точный промпт, итог проверки.
4. **Регистрация и проверки** (SCRATCH §4.2–4.3): `register_views.py`, `check_views.py` → `views/`, `masks/`,
   `views-registration.json`, `views-check.json`. Не прошло — перегенерация, до 4 попыток на вид. Спецификацию под
   картинки не подгонять, пиксели картинок не править.
5. **Контроль глазами** (запиши в `prompts.md`): строгие ракурсы, одна фигура, оружие в той же руке во всех видах,
   нет лишних конечностей и голов, лицо и костюм совпадают; side — персонаж смотрит **влево** (левый бок).
6. **Передача** (SCRATCH §0a): `HANDOFF.json` со всеми файлами пакета и sha256, путями и sha256 инструментов,
   `checks_passed: true` обоих отчётов, `notes`. Строка в `docs\art-pipeline\DIRECTORY-MAP.md` для
   `art/imagegen/scratch-v1/` и `tools/scratch-model/`; `-text` в `.gitattributes` для `art/imagegen/scratch-v1/**`.
7. **Коммит и интеграция** (порядок важен, файл не может содержать хеш собственного коммита):
   1) коммит пакета и инструментов перечислением путей с `--no-verify` (без `HANDOFF.json`);
   2) записать хеш этого коммита в `HANDOFF.json` → `git_commit`, закоммитить `HANDOFF.json` вторым коммитом;
   3) влить свежий `fix/admin-panel` в свою ветку, повторить `check_spec.py` и `check_views.py`;
   4) `tools/git/safe-integrate.sh feat/scratch2d-<content_key>` (сухой прогон), затем `--apply`.
8. **Доработка по запросу ZCode:** если позже появится `art/imagegen/scratch-v1/<content_key>/REWORK.md` —
   перегенерировать указанные виды, перепроверить, обновить `HANDOFF.json` (новая версия, прежние файлы — в `raw/`).

## 5. Правила

- Инструменты: docstring с запуском и входами/выходами, `--help`, JSON-отчёт `checks: {имя: {passed, measured,
  expected, note}}`, детерминизм, без меток времени и абсолютных путей.
- «PASS» — только со ссылкой на JSON и выдержкой значения. Пороги не ослаблять.
- Остановка: вид не проходит после 4 попыток; `image_gen` и SYNTX недоступны; карточка 04 противоречит
  `ASSET_DESCRIPTION`. Тогда — отчёт `art/imagegen/scratch-v1/<content_key>/README.md` (что сделано, числа, что
  решить) и сообщение пользователю.
- **Pre-commit хук сломан и опасен** (lint-staged без `prettier` делает `reset --hard`): только `git commit
  --no-verify`. Индекс не оставлять застейдженным.

## 6. Что вернуть пользователю

До 10 строк: статус пакета, путь к `HANDOFF.json` и хеш коммита в `fix/admin-panel`, попыток на вид, ключевые числа
`views-check.json` (регистрация, профиль front↔back, IoU shaded↔albedo), замечания для ZCode.
