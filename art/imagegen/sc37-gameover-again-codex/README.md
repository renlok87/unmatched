# SC-37 · sc37-gameover-again

Статус: **предложено**. Офлайн-макеты по CX-34; приёмка движка и новая съёмка не выполнялись.

Рекомендую заданную раскладку: плоские принятые скины HB-08, реальные строки и данные. Новых вариантов и генераций нет.

## Источники и решения

Общий SC-34-series.codex.md имеет приоритет над старыми карточками. Шрифты Roboto читаются из установленного движка; папка проекта unreal/ не открывалась даже для чтения по прямому запрету пользователя. Git, MCP и движок не запускались.
Все исходные SHA-256 зафиксированы до построения в source-hashes-before.json; копии библиотек побайтовые, copy-provenance.json. Для hud-icons-v3 — дерево, количество, изменённые файлы и только используемые иконки, без повторения всех хэшей.
Marmoreal — заданный P7 concept-paste K1, Sarpedon — P10 lit3d K1; реальные original maps, шесть v2 фигур. Исторический фон используется без ретуши. Именные плашки bench и стоящий павший герой — артефакты исходника. В игре замороженный HUD лежит под вуалью; на K1 его нет, поэтому он не придуман.
Грейд — приближение S08CuePostProcess: стандартный blackbody Kelvin→sRGB, target/base gains с сохранением Rec.709 яркости среднего серого; victory 6500→5900 K, defeat 6500→7300 K и saturation×0,8; виньетка ×(1−0,25r²), затем вуаль 0,6 без blur. Грейд держится до выхода и остаётся на просмотре доски. Ничья и ABORTED без грейда.
Копия SC-01 задаёт точные su, DPI 1/0,75 и UI 1/1,5. Иконки вставлены в точном native px-размере; отсутствующий размер отрисован render(name, px) локального неизменённого snapshot. main() и библиотечный spinner() не вызываются.
Портреты CP-07 по 120 su, без кольца и цвета команды. Весь диск проигравшего, подложка и край включительно, Rec.709 saturation 0 / opacity 0,6. Имена из данных: Medusa, King Arthur, T. Rex; русские формы «Медуза» / «Король Артур» из 05-content-matrix.csv ждут контентной задачи и здесь не рисуются.
Клавиши — отдельные T_Skin_KeyChip 20×20 su (Enter шире), type.tag; режим подсказок «Вкл». В Auto клиент показывает их при CompletedMatches=0. Ни hover, ни focus ring, ни курсора. Одна главная кнопка — «В ЛОББИ».
Модаль показана в финальном состоянии opacity 1; вход 400 мс — motion. Модаль/вуаль отдельно зарегистрированы как modal и освобождены от запрета перекрывать фигуры/клетки. Постоянная BoardStrip проверяется по FIELD и зарегистрированным маскам HB-07.

## Данные

Партия: Medusa против T. Rex; ход 19, 0:33; HP 14/16 и 0/27. Источник RESULT и HP: `docs/game-design/evidence/DE-FOOTAGE/2026-10-04/F/live/vs-ai/vsai-20261005-165024/vsai-client.trace.txt`, строка 5183; проверенный кадр `docs/game-design/evidence/DE-FOOTAGE/2026-10-04/F/live/vs-ai/vsai-20261005-165024/human/s09-result-screen.jpg` остаётся только входом.

VS_AI: AI Bot, run F, 19 / 0:33 / HP 14/16 и 0/27; числа run I не используются. ROOM и кнопка 1v1 отсутствуют. again.error — toast, не рисуется: реальной ошибки нет.
Дельта CP-07: t-rex, cx=0,56 cy=0,33 d=0,64. Старт cx=0,58 перемещён на −0,02: отмеченный глаз (0,43;0,19) теперь в центральных 60% диска (r/R=0,597). WebP 768×768 конвертирован Pillow без ретуши в derived/avatars/t-rex.png; пиксели PNG сверены с декодированным WebP.
В обеих фазах ширина AgainButton резервируется под более длинную busy-строку плюс spinner 24+8. Разрешённый порядок уплотнения: gaps 16→8, затем chips off, без уменьшения кегля или переноса. По ВР-VS5-SC37-06 модаль класса S расширена до 760 su: ряд с V и Enter и промежутками 16 su помещается в 712 su.

## Дельта строковой таблицы

- `screens.result.again.busy` · RU «Создаём партию…» · EN “Creating a game…”.

## Листы

- again, 1080p/100: [цвет](../../../scraped-data/derived/sc37-gameover-again-codex/SC-37-again-1080p-100.png), [серый](../../../scraped-data/derived/sc37-gameover-again-codex/SC-37-again-1080p-100-gray.png).
- again-busy, 1080p/100: [цвет](../../../scraped-data/derived/sc37-gameover-again-codex/SC-37-again-busy-1080p-100.png), [серый](../../../scraped-data/derived/sc37-gameover-again-codex/SC-37-again-busy-1080p-100-gray.png).
- [Геометрия 1080p/100](comparison/SC-37-overlay-1080p-100.png), [серый](comparison/SC-37-overlay-1080p-100-gray.png).
- again, 1080p/150: [цвет](../../../scraped-data/derived/sc37-gameover-again-codex/SC-37-again-1080p-150.png), [серый](../../../scraped-data/derived/sc37-gameover-again-codex/SC-37-again-1080p-150-gray.png).
- again-busy, 1080p/150: [цвет](../../../scraped-data/derived/sc37-gameover-again-codex/SC-37-again-busy-1080p-150.png), [серый](../../../scraped-data/derived/sc37-gameover-again-codex/SC-37-again-busy-1080p-150-gray.png).
- [Геометрия 1080p/150](comparison/SC-37-overlay-1080p-150.png), [серый](comparison/SC-37-overlay-1080p-150-gray.png).
- again, 720p/100: [цвет](../../../scraped-data/derived/sc37-gameover-again-codex/SC-37-again-720p-100.png), [серый](../../../scraped-data/derived/sc37-gameover-again-codex/SC-37-again-720p-100-gray.png).
- again-busy, 720p/100: [цвет](../../../scraped-data/derived/sc37-gameover-again-codex/SC-37-again-busy-720p-100.png), [серый](../../../scraped-data/derived/sc37-gameover-again-codex/SC-37-again-busy-720p-100-gray.png).
- [Геометрия 720p/100](comparison/SC-37-overlay-720p-100.png), [серый](comparison/SC-37-overlay-720p-100-gray.png).
- again, 720p/150: [цвет](../../../scraped-data/derived/sc37-gameover-again-codex/SC-37-again-720p-150.png), [серый](../../../scraped-data/derived/sc37-gameover-again-codex/SC-37-again-720p-150-gray.png).
- again-busy, 720p/150: [цвет](../../../scraped-data/derived/sc37-gameover-again-codex/SC-37-again-busy-720p-150.png), [серый](../../../scraped-data/derived/sc37-gameover-again-codex/SC-37-again-busy-720p-150-gray.png).
- [Геометрия 720p/150](comparison/SC-37-overlay-720p-150.png), [серый](comparison/SC-37-overlay-720p-150-gray.png).


## Проверки и ограничения

Контраст каждого текстового фрагмента измерен к его собственному телу до рисунка, отдельно цвет/серый; raster cores финального PNG приведены дополнительно. Граница панели — максимум контраста тела и растровой кромки к тому же фоновому пикселю; у primary границей служит жёлтое тело. В verification сохранены минимумы, p05 и доля ≥3. Красные пиксели учитываются в семантическом UI, отдельно красные знаки исходных иконок; пиксели оригинального арта фона/победителя не являются UI-ошибками.
Машинная приёмка: **есть непрохождения**. source_unchanged=True; outside_folder=[].
- Не пройдено: edges and icons >= 3:1; замер `{"boundary_min": 1.691363326693861, "icon_min": 2.549459090715187}`; требование `>=3`. Actual boundary samples; red signs separately measured. Fixed source failures retained.

Все ограничения сохранены честно: принятые скины, иконки и точные цветовые токены не перекрашены для искусственного прохождения. Visual-review.json содержит путь и SHA-256 каждого действительно открытого финального PNG; статус «предложено» не означает художественную приёмку.

## fix1

CX-34 fix1, 2026-10-08. Статус остаётся **предложено**. Каждый контур на схеме снабжён номером своей легенды: Roboto Regular не менее 14 px, text.primary на card.navy, keyline panel.edge 1 px. Тег в левом верхнем углу внутри, а при нехватке места — снаружи с линией 1 px. Легенда вынесена в добавленное поле справа; масштаб схемы сохранён 1:1. Измеренные пересечения тегов друг с другом и с легендой: 0; пересечения подписей: 0.

**ВР-VS5-SC37-06:** VS_AI с тремя кнопками использует в классе S модаль **760×560 su** вместо 680×560; вертикальные координаты класса S и центры портретов ±160 su сохранены. Ряд **705,75 su / бюджет 712 su**, поля **27,125 su**, gaps **16 su**; V и Enter восстановлены. Критерий ButtonRow теперь пройден. Геометрия again-busy отличается дополнительным AgainSpinner, поэтому для каждого холста добавлен отдельный `SC-37-overlay-again-busy-<res>-<scale>.png` и серый. Прямоугольники трёх кнопок совпадают в обеих фазах. Восемь макетов класса L сохранены побайтово.

Перегенерированные PNG (каждый повторно открыт отдельно, цвет и Rec.709 серый):

- [SC-37-again-1080p-150.png](../../../scraped-data/derived/sc37-gameover-again-codex/SC-37-again-1080p-150.png)
- [SC-37-again-1080p-150-gray.png](../../../scraped-data/derived/sc37-gameover-again-codex/SC-37-again-1080p-150-gray.png)
- [SC-37-again-busy-1080p-150.png](../../../scraped-data/derived/sc37-gameover-again-codex/SC-37-again-busy-1080p-150.png)
- [SC-37-again-busy-1080p-150-gray.png](../../../scraped-data/derived/sc37-gameover-again-codex/SC-37-again-busy-1080p-150-gray.png)
- [SC-37-comparison-1080p-150.png](../../../scraped-data/derived/sc37-gameover-again-codex/SC-37-comparison-1080p-150.png)
- [SC-37-comparison-1080p-150-gray.png](../../../scraped-data/derived/sc37-gameover-again-codex/SC-37-comparison-1080p-150-gray.png)
- [SC-37-again-720p-150.png](../../../scraped-data/derived/sc37-gameover-again-codex/SC-37-again-720p-150.png)
- [SC-37-again-720p-150-gray.png](../../../scraped-data/derived/sc37-gameover-again-codex/SC-37-again-720p-150-gray.png)
- [SC-37-again-busy-720p-150.png](../../../scraped-data/derived/sc37-gameover-again-codex/SC-37-again-busy-720p-150.png)
- [SC-37-again-busy-720p-150-gray.png](../../../scraped-data/derived/sc37-gameover-again-codex/SC-37-again-busy-720p-150-gray.png)
- [SC-37-comparison-720p-150.png](../../../scraped-data/derived/sc37-gameover-again-codex/SC-37-comparison-720p-150.png)
- [SC-37-comparison-720p-150-gray.png](../../../scraped-data/derived/sc37-gameover-again-codex/SC-37-comparison-720p-150-gray.png)
- [SC-37-overlay-1080p-100.png](comparison/SC-37-overlay-1080p-100.png)
- [SC-37-overlay-1080p-100-gray.png](comparison/SC-37-overlay-1080p-100-gray.png)
- [SC-37-overlay-again-busy-1080p-100.png](comparison/SC-37-overlay-again-busy-1080p-100.png)
- [SC-37-overlay-again-busy-1080p-100-gray.png](comparison/SC-37-overlay-again-busy-1080p-100-gray.png)
- [SC-37-overlay-1080p-150.png](comparison/SC-37-overlay-1080p-150.png)
- [SC-37-overlay-1080p-150-gray.png](comparison/SC-37-overlay-1080p-150-gray.png)
- [SC-37-overlay-again-busy-1080p-150.png](comparison/SC-37-overlay-again-busy-1080p-150.png)
- [SC-37-overlay-again-busy-1080p-150-gray.png](comparison/SC-37-overlay-again-busy-1080p-150-gray.png)
- [SC-37-overlay-720p-100.png](comparison/SC-37-overlay-720p-100.png)
- [SC-37-overlay-720p-100-gray.png](comparison/SC-37-overlay-720p-100-gray.png)
- [SC-37-overlay-again-busy-720p-100.png](comparison/SC-37-overlay-again-busy-720p-100.png)
- [SC-37-overlay-again-busy-720p-100-gray.png](comparison/SC-37-overlay-again-busy-720p-100-gray.png)
- [SC-37-overlay-720p-150.png](comparison/SC-37-overlay-720p-150.png)
- [SC-37-overlay-720p-150-gray.png](comparison/SC-37-overlay-720p-150-gray.png)
- [SC-37-overlay-again-busy-720p-150.png](comparison/SC-37-overlay-again-busy-720p-150.png)
- [SC-37-overlay-again-busy-720p-150-gray.png](comparison/SC-37-overlay-again-busy-720p-150-gray.png)

SHA-256 до/после каждого mockup и всех derived-файлов: `verification.json` → `mockup_unchanged`; любая незапрошенная разница считается ошибкой. Замеры run 1 сохранены в `fix1.run1_measurements` и `fix1-before.json`. Общий sc34_gameover_victory.py и его SC-35/36/37 копии не менялись; copy-provenance остаётся true. Исходные ограничения контраста скинов/иконок сохранены; они не входят в коррекцию fix1.

Обновлены `README.md`, `verification.json`, `visual-review.json`, `manifest-sha256.json`; добавлен неизменяемый снимок исходных хешей и замеров `fix1-before.json`. Общая коррекция находится в SC-34 `_tools/fix1.py` и `_tools/fix1_overlays.py`. В SC-37 также обновлены собственный `_tools/sc37_gameover_again.py` и `layout-geometry.json`.

## Воспроизведение

`python -B art/imagegen/sc34-gameover-victory-codex/_tools/fix1.py --render` — воспроизвести ровно correction fix1 для пяти пакетов (сбрасывает осмотр изменённых PNG). После прямого открытия каждого перечисленного PNG: `--finalize`. `--check` — полная проверка fix1 без записи. Нужны уже установленные Pillow/NumPy; установки пакетов, сеть, Git, MCP и unreal/ не используются.

Примечания воспроизведения run 1 (архив; для текущих исправлений используется команда выше):

Пересборка: `python -B art/imagegen/sc37-gameover-again-codex/_tools/sc37_gameover_again.py`. После прямого осмотра финалов: `--finalize-review` записывает visual-review.json и обновляет manifest; без осмотра эту команду не использовать.
Сравнительные листы в derived собраны из финалов без изменения пикселей, цвет/серый для каждого холста. Оверлеи содержат только геометрию и измеренные подписи BindWidget/x/y/w/h на card.navy, без аватаров и кадров.

## Ревью 2026-10-08 (Claude, единственный проход 07 §5, по делегированию)

**Вердикт: принято** — художественно, по делегированию (пользователь 2026-10-06: «Все решения принимай»). Серия
CX-34 (SC-34…SC-38 в одном чате Codex) прошла один корректирующий прогон; второго не будет (05 §1.4).

- **Прогон 1** (CX-34, 2026-10-07 23:13–23:59 +05:00, Codex `01a11792-509b-…`, `SC-34-series.codex.md`): fix-needed.
  Схемы `comparison/` не были связаны с легендой (на контурах не было номеров); в SC-37 при классе S ряд из трёх
  кнопок не помещался в модаль 680 su (около 8 su до кромки при минимуме 16 su), чипы клавиш были сняты.
- **Прогон fix1** (2026-10-08 00:01–00:19 +05:00, Codex `01a117bd-aa21-…`, `SC-34-series.fix1.codex.md`): номера на
  каждом контуре (пересечений 0; отдельные схемы draw и busy), SC-37 класса S — модаль 760×560 su (ВР-VS5-SC37-06),
  чипы «V» и «Enter» возвращены, ряд проходит. Изменились только 8 макетов SC-37 класса S и 4 листа сравнения из них
  (sha256 всех 109 файлов derived сверены Claude с прогоном 1).

Что проверено:
- Рамки: `git status --porcelain` основной копии до и после обоих прогонов — Codex создал только пять папок пакетов и
  `scraped-data/derived/sc34…sc38-*-codex/` (`inputs/` положил Claude, Codex их не менял); поиск файлов новее маркера
  запуска вне этих папок — 0; индекс пуст, HEAD `9810a253` не менялся; git, MCP, сеть и `unreal/` не использовались.
- `verification.json`: ключи 07 §1.2, `outside_folder: []`, `source_unchanged: true`; сверка Claude — все sha256
  манифестов совпали, файлов вне манифестов нет; `screen_mockup_base.py` = SC-01 (`d970f881…`),
  `draw_icons_v3_snapshot.py` = `draw_icons.py` (`353da947…`). Манифесты SC-35…SC-37 хранят хэши файлов SC-34 в том
  виде, в каком Codex их читал (до этой записи ревью).
- Данные: run I Marmoreal host (`RESULT summary … turn=11 duration=27`, Medusa 11/16, King Arthur 0/18), run I
  Sarpedon joiner (`DEFEAT … turn=5 duration=13`, Medusa 14/16, King Arthur 0/18), run F vs-ai Marmoreal
  (`… loserHero=T._Rex … turn=19 duration=33`, Medusa 14/16, T. Rex 0/27, соперник AI Bot; строка партии FINISHED,
  33,0 с); ABORTED — настоящая строка ONE_V_ONE на Marmoreal original: Veteran вышел (`GAME_ABORTED`, `player_left`),
  ход 1, зритель ProGamer (чтение эталонной БД в режиме READ ONLY 2026-10-07, новых партий не создавалось). Кадры
  результата run I и run F сверены глазами (HP и время совпали). Имена героев — из данных (Medusa, King Arthur,
  T. Rex; ВР-VS2-02). Строки — RU `st-screens.csv`; «уточнить» нет; в кадре draw числа не рисуются (настоящей ничьей
  нет), это записано.
- Не пройдено буквально и принято как известное: кромки принятых скинов HB-08 на navy ниже 3 : 1 (то же ограничение,
  что у принятых SC-03, SC-19, SC-31…SC-33 и SC-24…SC-30); значки на мелких размерах (красный крест
  `resource-hp-fallen` и X `resource-connection-lost` в сером) 2,4–2,5 : 1. Текст ≥ 8,7 : 1, кроме «ПОРАЖЕНИЕ»
  (`state.error` 48 su — 3,21 : 1; по 04 §3.7 / 02 §3.5 крупному тексту ≥ 24 su Bold достаточно 3 : 1); кегль на
  720p ≥ 10,5 px; одна главная кнопка на окно; красного вне заголовка поражения и знаков значков — 0; портрет
  проигравшего — насыщенность 0, прозрачность 0,6, без красного. Подписи фигур, стоящий павший герой и 3D-окружение
  внутри исходных кадров K1 — артефакт заданного фона.
- Кадры открыты (Read): again и again-busy — все 16 макетов листами 2×2 (цвет и серый) до и после fix1,
  again-busy 720p 150 % отдельно; схемы после fix1 (720p 150 % отдельно).
- Вид: VS_AI, Medusa против T. Rex (AI Bot), «Ход 19 · 0:33», три кнопки: «ПОСМОТРЕТЬ ДОСКУ» + V, «СЫГРАТЬ ЕЩЁ»,
  «В ЛОББИ» + Enter (главная); busy — спиннер 24 su и «СОЗДАЁМ ПАРТИЮ…», ширина кнопки не меняется; кроп T. Rex
  cx 0,56, cy 0,33, d 0,64 (дельта CP-07, глаз в центральных 60 %). Аватар T. Rex — только в derived.

Решения серии: ВР-VS5-SC34-01…09, ВР-VS5-SC35-01…02, ВР-VS5-SC36-01…03, ВР-VS5-SC37-01…06, ВР-VS5-SC38-01…04
(задания `SC-34-series.codex.md`, `SC-34-series.fix1.codex.md`). Предложенные ключи строк (дельта):
`screens.result.board.turn`, `screens.result.again.busy`, `screens.aborted.who.unknown`. UE-часть
(`UUmScreenGameOver`, `UUmScreenAborted`, `WBP_UI_SCR_GAMEOVER`, `WBP_UI_SCR_ABORTED`, постпроцесс CUE-016, строки
`screens.result.*` / `screens.aborted.*`, тесты экранов) — план VS-7.
