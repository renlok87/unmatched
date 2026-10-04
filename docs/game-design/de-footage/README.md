# Разбор видео Unmatched: Digital Edition — что взять в реализацию

Дата: 2026-10-04. Статус: исследование (материал для решений, не норматив). Сводка семи аналитиков A1–A7.
Перенос выводов в спецификации и код — пакет задач [task/](task/00-TASK.md).
Таблица таймингов — [timings.csv](timings.csv). Исходные результаты аналитиков без изменений — [findings/A1.json](findings/A1.json) …
[findings/A7.json](findings/A7.json).

Как читать ссылки:
- **Таймкод** вида [0:17:58](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1078s) ведёт на секунду ролика на YouTube.
- **Путь вида** `A1/s18_draw_fly_1078.jpg` — это лента или кадр-доказательство. Пути считаются от `C:/tmp/de-footage/findings/`. Файлы лежат только локально: кадры чужого видео в репозиторий не кладём.

## 0. Источник, метод, точность, ограничения

**Источник.** YouTube `G6wJgtcOjVA`, длина 3:26:45, 1080p30. Это русскоязычный стрим (ник ведущего — BERENGETTA). Ссылка на момент: `https://www.youtube.com/watch?v=G6wJgtcOjVA&t=<сек>s`.

| Глава | Начало | Содержание | Аналитик |
|---|---|---|---|
| ch00 | [0:00:00](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=0s) | Приветствие, меню, настройки, магазин | A1 |
| ch01 | [0:02:03](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=123s) | Обучение: Alice + Jabberwock против Medusa + 3 Harpies | A1 |
| ch02 | [0:23:49](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1429s) | Соло против ИИ (Hard), карта Heorot: Sinbad против Alice | A2 |
| ch03 | [0:38:34](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=2314s) | Испытание Endless Voyage (Normal) | A2 |
| ch04 | [0:50:24](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=3024s) | Онлайн, партия 1: Bigfoot против Dracula (Zzzzaal) | A3, A4 |
| ch05 | [1:32:45](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=5565s) | Онлайн, партия 2: Little Red против Dracula | A4, A5 |
| ch06 | [2:13:42](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=8022s) | Онлайн против Montaj, партия 1: Robin Hood против King Arthur, Heorot | A6 |
| ch07 | [2:34:30](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=9270s) | Montaj, партия 2: Sherlock Holmes против Sinbad, Marmoreal | A6, A7 |
| ch08 | [3:02:48](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=10968s) | Montaj, партия 3: Jekyll & Hyde против Invisible Man, Heorot | A7 |
| ch09 | [3:22:57](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=12177s) | Статистика, история, достижения, итоговое мнение | A7 |

Ролик кончается на [3:26:45](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=12405s).

**Метод.** Ролик разбит на 7 отрезков, по одному на аналитика. Каждый аналитик работал в три прохода:
1. Листы-раскадровки, 1 кадр на 2 с. По ним намечены события.
2. Ленты кадров 30 fps вокруг каждого события. Местами брались 15, 10, 7,5 или 5 fps — это помечено в `timings.csv` и в result.json.
3. Сегменты движения и автосубтитры — для реплик ведущего.

Длительность считается по номерам кадров ленты.

**Точность:**
- лента 30 fps — ±33 мс, то есть один кадр;
- лента 15 fps — ±67 мс, 10 fps — ±100 мс, 5 fps — ±200 мс;
- значения «по листам» — ±2 с; в таблице такие помечены `low` или вынесены в примечания.

Число клеток в пути местами оценено по кадру. Поэтому «мс на клетку» в замерах A1, A5 и A6 приблизительны: это отмечено в их `open_questions`.

**Ограничения:**
- **Звук игры не анализировался.** Колонка `sound` CUE и задача MS-T-18 этим разбором не покрыты.
- **Один ракурс.** Это запись экрана стримера. Правый нижний угол закрыт вебкой, поэтому кнопки Maneuver, Confirm, End turn и Pass не видны ни у одного аналитика.
- **Это стрим.** Ведущий снизил графику до Medium из-за лагов ([0:16:06](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=966s)), а в онлайне были сетевые подвисания ([1:51:15](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=6675s)).
- **Версия игры:** клиент DE 2.1.0.372, сервер 2.1.0.113 ([0:00:18](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=18s)). Партии датированы 07.08.2026 по GAME HISTORY ([3:24:04](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=12244s)).
- **Скорость анимаций в настройках — 1x** ([0:16:08](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=968s), кадр `A1/f_settings_968.png`). Все замеры сделаны на 1x.

**Партии.** Всего 7: обучение, соло, испытание и четыре онлайн-партии. Итоги:
- обучение — победа: Medusa 7 → 0 на [0:22:46](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1366s);
- соло — победа, экран результата на [0:38:21](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=2301s);
- испытание — победа, экран VICTORY на [0:49:32](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=2972s);
- онлайн-партия 1 — поражение от истощения на [1:30:14](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=5414s);
- онлайн-партия 2 — победа на [2:05:57](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=7557s);
- Montaj, партия 1 — поражение на [2:33:55](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=9235s);
- Montaj, партия 2 — победа на [3:00:40](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=10840s);
- Montaj, партия 3 — поражение на [3:21:20](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=12080s).

## 1. Карта экранов и потоков DE

```
Заставка ─► ГЛАВНОЕ МЕНЮ: TUTORIAL(!) · LOCAL PLAY · ONLINE PLAY · SHOP(!) · EXIT   [⚙ и ещё 3 значка справа сверху]
   │            ├─ ⚙ Настройки: GENERAL · GAMEPLAY (ANIMATION SPEED 0.75x–4x, DISABLE COMBAT CAMERA, LOWER HAND…) · VIDEO · AUDIO
   │            ├─ SHOP ▸ EXPANSIONS (дополнения за рубли)        ├─ Play History ▸ STATISTICS · GAME HISTORY · ACHIEVEMENTS
   ├─ TUTORIAL ─► доска обучения ─► TUTORIAL COMPLETE ─► меню
   ├─ LOCAL PLAY ─► две карты-плитки: CHALLENGES | SOLO PLAY
   │     ├─ SOLO PLAY: GAME TYPE · AI DIFFICULTY · MAP · слоты You/AI ─► выбор героя ─► CREATE GAME ─► загрузка ─► партия
   │     └─ CHALLENGES: список (Normal ─► Heroic под замком) ─► PLAY ─► загрузка ─► партия ─► VICTORY ─► список
   └─ ONLINE PLAY (нужен LOG IN) ─► спиннер ─► ЛОББИ (ACTIVE, SHOW PASSWORD GAMES, таблица столов, чат, CREATE GAME)
         ├─ CREATE GAME: 1v1/2v2 · AI DIFFICULTY · MAP · TIMER · PASSWORD · RANDOM HEROES (+ MECHANIC DOORS) ─► комната
         └─ стол ─► выбор героя ─► PASSWORD ─► JOIN ─► спиннер на слоте ─► арт-заставка ─► партия
Партия ─► экран результата («<ИГРОК> WINS!» / «VICTORY»), с переключением на доску ─► спиннер ─► лобби/меню (кнопки реванша нет)
```

| Экран или переход | Таймкод | Что важно | Доказательство |
|---|---|---|---|
| Главное меню | [0:00:14](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=14s) | Пункты на мазках кисти; наведение — белый мазок под пунктом без задержки | A1 timeline; `A3/s18_menu_to_lobby_3088.jpg` |
| Настройки | [0:00:18](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=18s), [0:16:08](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=968s) | ANIMATION SPEED 0.75x/1x/2x/3x/4x, DISABLE COMBAT CAMERA, LOWER HAND, DISABLE WARNINGS | `A1/f_settings_968.png` |
| LOCAL PLAY | [0:23:48](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1428s) | Затемнение ~130 мс, затем плитки разворачиваются по оси Y ~530 мс; наведение увеличивает плитку за 1–2 кадра | `A2/s01_localplay_flip.jpg` |
| SOLO PLAY | [0:23:52](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1432s) | 3 параметра + 2 слота героя; сетка героев с замками и карточкой (3D-модель, статы) | A2 timeline |
| Загрузка соло | [0:24:40](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1480s) | 4,6 с: загрузочный арт без прогресса; доска появляется без интро; рука раздаётся каскадом | `A2/s02_create_game_load.jpg` |
| Испытания | [0:38:39](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=2319s), [0:49:40](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=2980s) | Модификаторы правил (маяки, пустая рука); кубок-цели справа сверху; после победы открывается Heroic | `A2/s18_challenge_start.jpg`, `A2/f_challenge_victory.png` |
| Онлайн-лобби | [0:50:54](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=3054s) | Столы с паролем скрыты, пока не включён флажок; ведущий это пропустил ([0:51:38](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=3098s)) | A3 timeline |
| Вход в онлайн-партию | [0:52:02](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=3122s) | ~16 с до первой подсказки, только спиннеры и арт, без текста статуса | `A3/s14_join_load_3122.jpg` |
| Экран результата | [0:38:21](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=2301s), [1:30:18](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=5418s), [3:00:40](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=10840s) | Подробно — §3.8 | `A2/s16_victory_screen.jpg`, `A4/f_5419_5.png`, `A7/strip_g2_end_cut.jpg` |
| После партии | [1:30:26](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=5426s)–[1:33:27](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=5607s) | Реванша нет: новая комната, снова пароль; до новой доски ~3 мин | A4 events[15] |
| Лобби, клик по нику | [2:06:34](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=7594s) | Всплывающее меню BLOCK / ADD FRIEND | A5 timeline |
| Статистика | [3:23:00](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=12180s)–[3:24:18](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=12258s) | Подробно — ниже | `A7/f_12182_statistics.png`, `A7/f_herostats_grid.png` |

Экран результата ([0:38:21](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=2301s), [1:30:18](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=5418s), [3:00:40](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=10840s)):
- победитель — цветная 3D-модель в idle на пятне цвета игрока;
- проигравший — чёрный силуэт своего героя в своём цвете;
- зелёная кнопка переключает на доску со свободной камерой;
- статистики, наград и кнопок «реванш» или «в лобби» нет.

Статистика ([3:23:00](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=12180s)–[3:24:18](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=12258s)):
- любимый герой и карта;
- Wins / Games / Win Rate по режимам;
- побеждено героев и помощников, сыграно карт;
- история: Hero / Date / Mode / Finish / Map / Rounds / Played With;
- достижения плитками.

## 2. HUD DE: что есть, где стоит, сравнение с нашим 02 §4

Ниже — инвентарь по кадрам `A1/f_end_turn_1090.png`, `A3/f_4460_opp_waiting.png`, `A5/f_7150_choose_def.png`, `A4/f_5413_9.png`.

| Элемент DE | Где | Поведение | Наш аналог (02 §4, значки) | Вывод |
|---|---|---|---|---|
| Своя панель | слева снизу | Портрет в рваной рамке. На ней: сердце HP, колода (число), движение (значок следов), имя на ленте цвета стороны, бейдж 1st/2nd, значок размера Big/Small (у Alice). Клик открывает экран героя | UI-HUD-PANEL-LOC, слева снизу | совпадает |
| Панель соперника | **справа сверху** | Зеркальная своей; веер рубашек = число карт в руке. Наведение показывает ник ([2:37:26](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=9446s)) | UI-HUD-PANEL-OPP слева сверху + UI-HUD-OPP-HAND сверху по центру | у DE соперник стоит по диагонали от своей панели; у нас — тот же левый край |
| **Трекер действий** | под портретом, 2 кружка | Потраченное действие заполняет кружок значком типа: следы — манёвр, вспышка — атака или схема. Сбрасывается в конце хода ([0:18:11](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1091s)). У соперника такой же трекер, поэтому видно, что он уже сделал ([1:09:40](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4180s)) | статус-бар «действия ●●○»; ICON-MOTION `resource-action-full/empty` (spend/gain), `action-*` spend = opacity 0,4 | **взять** заполнение значком типа, в том числе у соперника (§9, H-1) |
| **Кольцо у портрета** | вокруг портрета активного игрока | В начале хода ~0,9 с: прорисовывается по кругу жёлтым → оранжевым → красным и гаснет ([0:19:02](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1142s), [0:26:55](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1615s)) | CUE-015 «кромка стороны»; в ICON-MOTION нет | **взять** (§9, H-2) |
| **Строка-подсказка** | сверху по центру, одна строка | В свой ход — что делать сейчас: «Maneuver, attack, or scheme.», «You may move your fighters or discard to BOOST.», «Confirm your move.», «End your turn.», «Choose a defender.», «Play a card to defend?», «Discard 2 card(s).», «Move Sinbad?». В онлайне в ход соперника — «<ник> is <глагол>» (§5). В соло в ход ИИ пустеет ([0:35:05](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=2105s)) | UI-HUD-TOP «фаза: МАНЁВР», 02 §6, `why.*` | **взять** формулировку «что делать сейчас», а в ход соперника — «что он делает» |
| Значки справа сверху | 3 круглые кнопки | Чат, Action Log и настройки (A5 [1:51:12](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=6672s)). Журнал группирует строки по ходу и по действию ([0:05:24](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=324s)). На экране результата остаётся только чат | UI-HUD-LOG — постоянный блок слева; лента MS — 3 строки над рукой (03 §7) | у DE журнал скрыт за кнопкой; наша постоянная лента полезнее (§5) |
| Слот активной карты | слева сверху | Мини-карта с лентой SCHEME, DISCARDED, BOOSTED!, GUESSED 2! или карта «after combat». Висит, пока идёт эффект ([2:26:10](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=8770s)) | UI-HUD-PENDING (центр); ICON-MOTION `marker-status` (appear 220 мс) | **взять** как источник эффекта (§9, H-6) |
| Рука | снизу по центру, веер внахлёст | Рамки: циан — можно сыграть, оранжевая — можно сбросить на буст, красная — выбрана к сбросу. На картах кружок со значением буста ([1:52:22](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=6742s)). Крупное превью появляется за 1 кадр ([0:19:07](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1147s)) и работает в любой фазе, в том числе поверх баннеров | UI-HUD-HAND: hover 150 мс, приглушение неиграбельных с причиной | у DE нет причины неиграбельности; превью **перекрывает доску** (жалобы §8) |
| Плашка бойца | над фигуркой | Сердце с HP + имя на ленте цвета стороны + маленький значок melee/ranged. Едет вместе с фигуркой. При уроне сердце вспыхивает, при смерти — крест | 02 §4.4 «HP-мини-бары над фигурками»; `resource-hp-full` damage/deplete | **взять** «перечёркнутое сердце» (§7) |
| Подсветка поля | доска | Свои бойцы, которые могут ходить, — синие кольца. Выбранный — жёлтый диск. Достижимые клетки — бирюзовые кольца по контуру. Цели атаки — синие кольца, под наведённой — жёлтое с прицелом. Двери Heorot — скобки на рёбрах графа | 02 §4.4 и 03 §4.1–4.2 (V-01…V-16, глифы) | §6 |
| Экран героя | полноэкранный оверлей | Арт, HP x/max, MELEE/RANGED, движение, способность. Вкладки DECK / HAND / DISCARD, у соперника тоже. Доступен в чужой ход. Сам закрывается, когда начинается бой ([2:02:36](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=7356s)) | UI-SCR-INSPECT, UI-HUD-DECKS | **взять** автозакрытие; делать панелью, а не на весь экран (§8) |
| Модальные выборы | сверху по центру, тёмно-красная панель | Заголовок карты, кнопки вариантов, CONFIRM / SKIP / CONTINUE, кнопка «назад» (отмена розыгрыша), кнопка «свернуть окно», чтобы посмотреть доску ([0:19:52](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1192s)) | UI-HUD-PENDING (CHOOSE_ONE) | **взять** «свернуть» и «назад» |
| Тосты | под строкой-подсказкой | Шестиугольный портрет + текст + галочка. Появляются по месту: двери, лимит руки 7, истощение ([0:24:44](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1484s), [0:33:22](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=2002s)) | — | контекстные подсказки при первом появлении механики |
| Таймер | над счётчиками своей панели | Скрыт до последних ~28 с хода: тогда появляется жёлтая полоса и огненное кольцо у портрета ([1:43:58](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=6238s)). Таймера защиты не видел ни один аналитик | UI-HUD-COMBAT: видимый таймер 30 с | наш видимый таймер защиты **оставить** |
| Кнопки Maneuver / Confirm / End turn / Pass | справа снизу | Закрыты вебкой, видны только тултипы ([0:17:58](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1078s)): «Draw a card then move your fighters», правило Exhaustion ([2:54:14](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=10454s)) | 02 §3.3: ПАС / КОНЕЦ ХОДА слева снизу | у стримеров правый нижний угол занят вебкой — наше место для кнопок удачнее |

**Значки HUD (связь с HUD-ICONS / ICON-MOTION).** Разница между значками DE и нашими — в механике:
- **Трекер действий.** Кружок в DE *заполняется* значком типа действия. У нас значок действия при трате *гаснет* (opacity 0,4).
- **Сердце.** В DE у сердца три состояния: число, вспышка с брызгами, крест. У нас есть `damage` 200 мс и `deplete`.
- **Красный крест-штамп.** В DE он единый для «нет защиты» и «эффект отменён». Ближайший у нас — штамп X в `resource-connection-lost` (удар 110 мс).

## 3. Ход по шагам

### 3.1 Начало хода

1. Своё кольцо у портрета, ~0,9 с.
2. Чернильная клякса и баннер YOUR TURN с портретом героя, ~2,0 с (`A4/s15_your_turn_banner.jpg`, [1:37:28](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=5848s)).
3. Ещё во время баннера строка меняется на «Maneuver, attack, or scheme.».

Баннер ввод **не блокирует**: превью карт и тултипы работают поверх ([2:25:03](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=8703s)).

На ход соперника баннера нет — только кольцо у его портрета и строка статуса ([1:09:32](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4172s)).

### 3.2 Манёвр

1. **Начало.** Кнопка Maneuver (тултип: «добери карту, затем двигай бойцов»). Карта добирается сразу, ~333 мс (`A1/s18_draw_fly_1078.jpg`, [0:17:58](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1078s)). Выбор бойца доступен, не дожидаясь конца добора ([0:53:36](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=3216s)).
2. **Бойцы-кандидаты.** Под всеми своими бойцами, которые могут ходить, — синие кольца; клетки ещё не подсвечены. Если боец один, клетки видны сразу ([1:43:00](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=6180s), [1:51:58](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=6718s)).
3. **Выбор бойца.** Жёлтый диск под бойцом. Все достижимые клетки мгновенно получают бирюзовые кольца по контуру (`A2/s22_player_move_select.jpg`, [0:27:12](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1632s)). **Пути и счётчика шагов нет.**
4. **Буст.** Пока строка говорит «…or discard to BOOST», можно сбросить карту:
   - карта летит из руки к доске ~1,2 с;
   - через ~0,73 с появляется расширенная сетка клеток (`A5/s11_boost_move_7138.jpg`, [1:58:58](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=7138s));
   - после первого шага буст больше не предлагается: строка теряет «or discard to BOOST» ([1:43:00](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=6180s));
   - ошибочный буст отменить нельзя — ведущий просил вернуть ([0:30:24](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1824s)).
5. **Клик по клетке.** Кольца гаснут в кадр клика, и фигурка сразу едет:
   - скольжение или бег, **без подскока**;
   - свой боец — медиана ~368 мс на клетку, соперник — ~325 мс; разброс в §4;
   - второй боец ждёт клика игрока;
   - после хода может автоматически подсветиться следующий свой боец ([1:35:24](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=5724s)).
6. **Подтверждение.** «Confirm your move.» — **одно** подтверждение на весь манёвр, после всех бойцов ([1:44:24](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=6264s)):
   - до подтверждения ход можно откатить ([0:37:31](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=2251s));
   - подтверждение доступно только после того, как фигурка дошла ([1:14:06](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4446s));
   - неподтверждённый ход может висеть ~40 с, пока игрок смотрит колоды ([2:52:50](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=10370s)).
7. **Сайдкики-жетоны** (Huntsman, Outlaw, Watson, Porter) — плоские диски с портретом. Они скользят, ~440 мс на клетку ([1:44:22](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=6262s)).

### 3.3 Атака

1. Выбрать карту в руке. Строка — «Choose a defender.». От карты к курсору тянется синяя дуга-стрела с прицелом. Допустимые цели — синие кольца, наведённая — жёлтое кольцо с перекрестием (`A5/f_7150_choose_def.png`, [1:59:10](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=7150s)). Выбор можно отменить ([2:04:00](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=7440s)).
2. В обучении карту можно перетащить на цель ([0:05:56](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=356s)) или сыграть двойным кликом ([0:09:36](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=576s)). Если атакующих несколько — «Choose a fighter to attack with.» ([0:22:28](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1348s)).
3. После клика по цели камера **сама** наезжает на пару бойцов (~660 мс). Карта атаки встаёт слева, справа — серый слот-щит. Ярлыки ATTACKER (красный) и DEFENDER (голубой). От клика до готовой сцены — 1,6–2,4 с ([1:12:19](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4339s), [1:16:33](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4593s)).
4. На атаку соперника сначала выходит клякса «COMBAT!», затем наезд камеры; всего ~1,47 с. Строка «Play a card to defend?» появляется через ~2 с ([3:13:07](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=11587s)).

### 3.4 Защита

Строка — «Play a card to defend?». Годные карты обведены циан-рамкой, остальные — без рамки ([1:08:33](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4113s)). Таймера не видно.

Свой слот **всегда слева**, соперника — справа, независимо от роли ([1:12:57](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4377s)). Роль подписана ярлыком.

Три состояния слота:
- серый щит — карта ещё не выбрана;
- рубашка — выбрана, но закрыта;
- красный крест мазками, ~200 мс — защиты нет ([1:12:26](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4346s)).

Если карт нет — «Unable to defend! Press continue.» ([3:21:03](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=12063s)).

Время решения: ИИ ~3,5 с без индикатора «думает» ([0:20:42](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1242s)); живой соперник 4–7 с, в длинных случаях до 26 с.

### 3.5 Раскрытие и урон

Порядок: переворот → эффекты → пауза → счёт → удар → урон → победитель → отъезд камеры. Каждый шаг отделён паузой 1–2 с.

1. **Переворот** на месте, ~130 мс. Карты не встречаются в центре ([1:13:02](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4382s)).
2. **Эффекты по одному:**
   - сработавшая строка текста подсвечивается белой полосой, ~400 мс;
   - отменённая карта получает красный крест-штамп или красную заливку ([1:13:05](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4385s), [3:13:15](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=11595s));
   - изменённое значение показано цифрой другого цвета ([0:25:56](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1556s));
   - при бусте карты-веером выезжают позади карты боя, слева — плашка BOOSTED! ([1:40:52](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=6052s)).
3. **Пауза** до счёта: медиана ~2,9 с.
4. **Счёт.** «N vs M» влетает крупно и за ~180 мс сжимается в красную ленту.
5. **Удар.** Через ~1,6 с после счёта атакующий делает выпад или замах на месте, ~425 мс до контакта ([2:24:49](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=8689s)).
6. **Урон:**
   - в кадр контакта карта победителя вспыхивает, у сердца цели — брызги;
   - модель цели заливается красным и вздрагивает, ~430 мс;
   - число HP меняется мгновенно, через ~167 мс после контакта;
   - сердце светится и пульсирует ~1 с ([3:13:18](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=11598s)).
7. **Победитель.** «ИМЯ WINS!» сжимается в ту же ленту и держится ~2,5 с. Баннер показывается и без урона: при ничьей побеждает защитник ([1:16:44](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4604s), [3:19:54](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=11994s)).
8. **Выход.** Карты улетают, камера ~1,35 с отъезжает к общему виду.

Весь бой без времени решения длится **~12,7 с** (10–14 с). Наша цепочка CUE-008…011 — 2,3 с.

### 3.6 Схема и отложенные выборы

**Своя схема.** Карта уходит в левый верхний угол с лентой SCHEME. Многошаговую схему строка ведёт по шагам: «Move The Jackalope?» → «Deal 2 damage to an adjacent fighter.» ([0:54:24](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=3264s)).

**Чужая схема:**
- карта вылетает от портрета соперника, ~200 мс;
- висит ~1,9 с, потом играется эффект ([1:12:51](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4371s));
- при длинном эффекте висит всё время, Command the Storms — ~20 с ([2:26:10](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=8770s)).

Виды отложенных выборов:

| Вид | Пример | Таймкод | Доказательство |
|---|---|---|---|
| «Choose two» + CONFIRM + свернуть окно | LOOKING GLASS | [0:19:52](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1192s) | `A1/f_modal_choose_1192.png` |
| Yes/No + «назад» | Loner by Nature — каждый конец хода, даже когда выбор бессмыслен | [0:54:34](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=3274s) | A3 events[17] |
| Choose one, 3 кнопки + «назад» | NEVER LEAVE THE PATH | [1:38:20](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=5900s) | `A4/f_5906_9.png` |
| Вернуть карту в руку + SKIP + CONFIRM | WHAT LARGE HANDS | [1:35:52](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=5752s) | A4 events[22] |
| Confirm / Decline внутри боя | DEDUCE STRATEGY | [2:39:36](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=9576s) | `A6/f_dialogs_quad.jpg` |
| Спиннер числа ▲▼ + CONFIRM + отмена, результат — плашка «GUESSED 2!» | CONFIRM SUSPICION, ELEMENTARY | [2:51:44](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=10304s), [2:55:04](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=10504s) | A7 events[17] |
| Рука соперника + CONTINUE / выбор к сбросу | Voyage, Study Methods, Eliminate the Impossible | [0:35:00](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=2100s), [2:37:26](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=9446s), [2:42:54](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=9774s) | `A6/f_dialogs_quad.jpg` |
| PLACE: кольца на всех допустимых клетках | «Place Alice anywhere.» | [0:19:52](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1192s) | A1 events[15] |
| MOVE своего или **вражеского** бойца своим эффектом, с Confirm и откатом | «Move The Jabberwock?», «Move Sinbad?» | [0:28:02](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1682s), [0:37:20](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=2240s) | `A2/f_confirm_move.png` |
| Выбор **игрока в ход соперника**: сначала объект, потом цель | «Move fog?» → «Move fog up to 3 space(s)?» | [3:09:22](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=11362s) | A7 events[16] |
| Подсказка без единой допустимой цели висит ~24 с | «Deal 2 damage.» — участник решил, что это первый баг | [3:05:34](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=11134s) | `A7/f_11146_deal2_wait.png` |
| Обязательный модал каждый ход, закрывает верх доски | THE SERUM | [3:14:02](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=11642s) | `A7/strip_g3_yourturn_serum_11642.jpg` |

### 3.7 Лимит руки и истощение

**Лимит руки.** Строка «Discard N card(s).»:
- вся рука в циан-рамке, выбранные к сбросу — в красной и приподняты ([1:58:08](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=7088s), `A5/f_7088_discard.png`);
- ведущему неясно, какая из выбранных уйдёт первой ([1:58:09](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=7089s));
- лимит руки 7 объясняется тостом ([0:25:40](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1540s)).

**Истощение:**
- правило написано только в тултипе Maneuver ([2:54:14](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=10454s));
- о скором истощении предупреждает тост ([0:33:22](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=2002s));
- подтверждения нет: манёвр при пустой колоде сразу снимает 2 HP, без баннера ([1:27:04](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=5224s): 10 → 8, далее [1:28:48](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=5328s), [1:30:08](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=5408s));
- последний такой манёвр убил Bigfoot ([1:30:13](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=5413s), `A4/s08_exhaustion_death_crop.jpg`);
- на экране результата причина поражения не названа.

Это довод за наше подтверждение MS-S-04 / MS-R-03.

### 3.8 Смерть и конец партии

**Помощник-жетон** подлетает и переворачивается рубашкой вверх, ~850 мс; на сердце — крест (`A6/s02_outlaw_death_crop_8272.jpg`, [2:17:52](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=8272s)).

**Sister и Jackalope** исчезают за 1 кадр без анимации ([1:12:34](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4354s), [1:08:39](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4119s)). Противоречие — §4.1.

**Герой:**
1. Удар.
2. Пауза ~1–2 с, фигурка стоит.
3. Растворение цветом героя или игрока, ~550 мс ([2:33:44](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=9224s)).
4. Только после этого — баннер победителя боя.

От удара до исчезновения фигурки — ~2,6 с.

**Конец партии.** От смертельного удара до экрана результата — **3,95–12,5 с**, медиана 8,6 с ([2:33:42](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=9222s)–[2:33:55](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=9235s)). В это время идут баннер победителя боя, отъезд или панорама камеры и затемнение в тёмно-красный.

## 4. Тайминги: DE против наших CUE

Полная таблица на 45 строк, со всеми значениями и таймкодами, — [timings.csv](timings.csv). Ниже — строки, по которым нужно решение.

Обозначения:
- «Наше» — значение из `07-animation-vfx-audio.csv` или 03 §5. Где написано «сумма», это оценка редактора;
- n — число замеров;
- Δ — медиана DE минус наше значение.

| Событие | DE: медиана, мс (n; мин–макс) | Наш CUE, мс | Δ | Рекомендация | Примеры |
|---|---|---|---|---|---|
| Добор одной карты | 333 (4; 283–400) | CUE-005: 350 | −17 | оставить | [0:17:58](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1078s) `A1/s18_draw_fly_1078.jpg` |
| Шаг каскада стартовой руки | 175 (3; 150–250) | CUE-005: каскад без очереди, шаг не задан | — | задать шаг 150–200 | [0:52:17](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=3137s) `A3/s15_deal_hand_3137.jpg` |
| Шаг по клетке, свой боец | 368 (8; 185–440) | CUE-007: 280 | +88 | 280 оставить, разброс DE шире нашего (§4.1) | [0:27:16](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1636s), [1:14:03](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4443s), [3:20:33](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=12033s) |
| Шаг по клетке, соперник или ИИ | 325 (4; 290–450) | CUE-007: 280 | +45 | близко; 280 оставить | [0:26:52](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1612s) `A2/s05_ai_jabberwock_step.jpg` |
| От клика до начала движения | 350 (6; 33–580) | MS-R-22: по снапшоту, числа нет | — | стартовать сразу по снапшоту; задержка DE заметна | [1:59:00](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=7140s) `A5/s12_LR_boostmove_7140.jpg` |
| Дальний ход одного бойца | 1800 (3; 1400–2270) | потолок бойца: 1400 | +400 | потолок оставить | [1:14:03](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4443s) `A3/s09_move_hoax_4444.jpg` |
| Кольцо у портрета в начале хода | 885 (12; 400–1170) | CUE-015: «кромка», длительности нет; в ICON-MOTION нет | — | новая анимация ~900 мс | [0:19:02](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1142s) `A1/s14_ability_icon_1143.jpg` |
| Баннер YOUR TURN | 2030 (8; 833–2200) | CUE-015: 600 | +1430 | 600 оставить, ввод не блокировать (как в DE) | [0:25:25](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1525s) `A2/s03_your_turn_banner.jpg` |
| Смена хода целиком (кольцо + баннер) | 3200 (4; 3000–3230) | CUE-015: 600 | +2600 | не копировать | [1:55:56](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=6956s) `A5/s14_yourturn_6956.jpg` |
| Анонс атаки соперника COMBAT! | 1470 (5; 1200–1530) | CUE-008: 600 | +870 | 600 оставить | [3:13:07](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=11587s) `A7/strip_g3_combat_intro_11586.jpg` |
| Своя атака: клик по цели → сцена боя | 2000 (2; 1600–2400) | сумма CUE-003 + CUE-008: 850 | +1150 | оставить | [1:12:19](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4339s) `A3/s02_combat_zoom_4339.jpg` |
| Карта защиты летит в слот | 500 (3; 200–900) | CUE-009: 500 | 0 | совпадает | [2:24:42](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=8682s) `A6/s13_defend_reveal_8682.jpg` |
| Крест «нет защиты» | 200 (5; 70–500) | нет | — | ввести штамп 200 мс (в CUE-009 или CUE-010) | [1:12:26](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4346s) `A3/s03_defslot_X_4342.jpg` |
| Переворот карты | 130 (9; 70–270) | CUE-010: 800 на всё | — | переворот внутри CUE-010 держать ~130–200 | [1:13:02](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4382s) `A3/s08_reveal_cancel_4382.jpg` |
| Раскрытие → счёт «N vs M» | 2930 (11; 1700–4600) | CUE-010: 800 | +2130 | **не копировать**; паузу сделать пропускаемой (03 §5 MS-E-70 по духу) | [0:19:35](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1175s) `A1/s16_defense_reveal_1174.jpg` |
| Подсветка сработавшей строки | 400 (5; 400–500) | нет | — | ввести в CUE-010 | [3:13:13](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=11593s) `A7/strip_g3_combat_resolve_11590.jpg` |
| Счёт → удар | 1600 (13; 1300–2170) | нет (CUE-010 → CUE-011) | — | у нас без паузы | [2:24:47](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=8687s) `A6/s13_defend_reveal_8682.jpg` |
| Замах до контакта | 425 (4; 300–500) | CUE-008: 600 (LungeAttack; блокаут Medusa 583) | −175 | кадр контакта ~400–450 мс; к нему привязать HitReact и смену HP | [2:24:49](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=8689s) `A6/s20_arthur_lunge_8689.jpg` |
| Удар → смена числа HP | 167 (5; 130–200) | 02 §4.3: плавно ≤ 400 | — | менять число через ~150–200 мс после контакта | [3:13:18](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=11598s) `A7/strip_g3_damage_hp_11598.jpg` |
| Красная заливка цели (HitReact) | 430 (3; 400–470) | блокаут HitReact Medusa: 375 | +55 | совпадает | [1:25:46](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=5146s) `A4/s06_hit_heart_crop.jpg` |
| Всплывающая «−N» | 850 (6; 430–1070), low | CUE-011: 900 | −50 | 900 оставить (противоречие — §4.1) | [0:20:50](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1250s) `A1/s06_hit_damage_1250.jpg` |
| Свечение сердца HP | 1030 (5; 830–1170) | ICON-MOTION `resource-hp-full.damage`: 200 | +830 | удлинить пульс сердца до ~600–1000 | [1:12:33](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4353s) `A3/s05_hit_sister_4353.jpg` |
| «ИМЯ WINS!»: влёт + удержание | 200 + 2540 (5; 2000–2600) | нет | — | влёт 200, держать ≤ 1–1,5 с (A7) | [3:13:18](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=11598s) |
| Возврат камеры после боя | 1350 (10; 430–1530) | D-10: камера стоит | — | не нужно | [3:13:21](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=11601s) |
| **Бой целиком, без решения защиты** | **12 700 (3; 9900–13 700)** | сумма CUE-008 + 010 + 011: 2300 | **+10 400** | **наш темп — преимущество, не замедлять** | [0:20:41](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1241s), [1:12:19](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4339s), [3:13:07](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=11587s) |
| Смерть помощника-жетона | 850 (4; 770–1170) | CUE-013: 950 | −100 | вариант «переворот жетона» для бойцов без рига | [2:17:52](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=8272s) `A6/s02_outlaw_death_crop_8272.jpg` |
| Растворение героя | 550 (7; 400–870) | CUE-013: 950 | −400 | 950 оставить; дым цвета команды | [2:33:44](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=9224s) `A6/s05_robin_death_crop_9224.jpg` |
| Удар → исчезновение героя | 2600 (7; 1400–3370) | сумма CUE-011 + 013: 1850 | +750 | паузу после удара держать ≤ 1 с | [2:05:53](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=7553s) `A5/s19_dracula_death_crop.jpg` |
| Смертельный удар → экран результата | 8600 (7; 3950–12 530) | сумма CUE-011 + 013 + 016: 3350 | +5250 | переход ≤ 2 с после смерти (A7) | [3:21:11](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=12071s) `A7/strip_g3_final_combat_end.jpg` |
| Показ карты чужой схемы | 1940 (7; 1600–2330) | CUE-006: 500 | +1440 | для **чужих** схем держать карту ~1,5–2 с (A2, A3) | [1:12:51](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4371s) `A3/s06_opp_scheme_mistform_4371.jpg` |
| Появление при PLACE | 270 (3; 0–400) | MS-E-88: 240 | +30 | совпадает; можно добавить «пуф» на старом месте | [2:02:29](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=7349s) `A5/s17_mistform_place_7347.jpg` |
| Лечение | 1100 (3; 900–2000) | CUE-012: 700 | +400 | 700 оставить | [1:39:28](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=5968s) `A4/s17_opp_scheme_heal_place.jpg` |

### 4.1 Противоречия между аналитиками (не сглажены)

1. **Скорость шага.** Аналитики сходятся в цифрах DE, но расходятся в выводе:
   - A1: DE быстрее, 170–200 мс на клетку без подскока; предлагает умолчание 200–220 мс ([0:17:22](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1042s));
   - A3: DE медленнее, ~450 мс на клетку; наши 280 «лучше» ([1:14:03](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4443s)). Перемер ревью: из 2,3 с от клика ~0,4 с Bigfoot разворачивается на месте, само движение по 5 клеткам — ~1,97 с, ~395 мс на клетку;
   - A2 и A4: 280 подтверждаются, 270–315 мс ([0:26:52](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1612s), [1:35:24](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=5724s)). Перемер ревью: в 1612 Jabberwock прошёл 2 клетки, а не 3, за ~0,7 с — ~350 мс на клетку;
   - A5 мерил одну партию и получил 190 мс у героя и 440 мс у жетона.

   Вероятные причины — разные бойцы (жетон или 3D, шаг или бег) и оценка числа клеток по кадру. Медиана своих бойцов — 368 мс, соперника — 325 мс (после перемера ревью, см. «Ревью»).
2. **Всплывающая «−N».** Видна у A1 ([0:20:50](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1250s)), A2 ([0:27:34](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1654s)), A6 ([2:33:42](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=9222s)) и вне боя у A4 ([1:40:04](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=6004s)). Не видна у A3 (урон способностью, [1:09:35](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4175s)), у A7 (урон в бою, [3:13:18](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=11598s)) и у A4 в бою ([1:25:46](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=5146s)). Правило показа не установлено.
3. **Известные карты в руке соперника:**
   - A1 ([0:22:00](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1320s)) и A7 ([2:51:38](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=10298s)): вкладка HAND соперника показывает известные карты лицом;
   - A3 ([1:05:38](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=3938s)): только рубашки; игроки ждали отметки и, по их словам, игра этого не умеет.

   Возможно, это зависит от того, как карта стала известна: эффектом «посмотри руку» или иначе. Не установлено.
4. **Длина баннера YOUR TURN.** У A1–A6 — 1,9–2,2 с. У A7 — 833 мс, но баннер оборвал обязательный модал THE SERUM ([3:14:02](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=11642s)).
5. **Камера в ход соперника:**
   - A1: в обучении и соло камера сама наезжает на действия ИИ ([0:18:25](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1105s));
   - A2: при манёвре ИИ камера не двигается ([0:26:52](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1612s));
   - A3: наезды во время расстановки соперника — авто или колесо ведущего, не определено ([0:53:14](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=3194s));
   - A3, A4, A6: в онлайне камеру двигает только сам игрок;
   - A5 (по листам, low): при Bloodthirsty камера приближается к цели ([1:51:04](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=6664s)).

   Во **всех** боях камера наезжает сама.
6. **Индикатор «соперник думает».** A1 и A2 (обучение и соло): индикатора нет, строка пустеет. A3–A7 (онлайн): строка «<ник> is <глагол>». Это различие режимов, а не ошибка, но для ИИ у DE ожидание не видно совсем.
7. **Смерть помощника.** Жетоны (Jabberwock-подставка, Huntsman, Outlaw, Watson) переворачиваются, 770–1170 мс. Sister и Jackalope исчезают за кадр (A3, A4).
8. **Рекомендации по паузе перед резолвом расходятся:**
   - A2: добавить ~1–1,5 с «на чтение карты соперника» ([0:25:56](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1556s));
   - A5 и A7: избегать длинных пауз и обрывать фазы следующим событием;
   - A3: пошаговость перенять, но паузы ужать и дать пропуск кликом.

   Предложение редактора: вопрос к пользователю (§10).
9. **Таймер.** A1–A4 и A6 таймера не видят совсем. A5 нашёл таймер хода, который появляется только в последние ~28 с ([1:43:58](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=6238s)). Ведущий вслух говорит о «минуте» ([1:22:40](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4960s)). Таймер защиты не нашёл никто.

## 5. Что видит игрок в ход соперника → MS-T-17

| Момент | Что показывает DE | Таймкод, доказательство | Наш план (03 §7, MS-R-24) | Вывод для MS-T-17 |
|---|---|---|---|---|
| Начало хода соперника | Кольцо у **его** портрета ~850 мс; баннера нет | [1:09:32](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4172s) `A3/s11_opp_turnstart_bloodthirsty_4170.jpg` | CUE-015 кромка | кольцо у портрета активного — общий сигнал для обоих |
| Пока думает | Онлайн — строка «Zzzzaal is taking an action / thinking / maneuvering / moving / defending / choosing a card / discarding / dealing damage / using Bloodthirsty / returning a defeated sidekick / placing sidekicks / moving fog». В соло строка пустая | [1:14:20](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4460s) `A3/f_4460_opp_waiting.png`; [2:58:42](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=10722s); [0:35:05](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=2105s) | индикатор «Соперник выбирает манёвр», пульс 1 Гц (MS-S-11) | **добавить глагол фазы** из pending-состояния сервера к пульсу (A3, A6, A7) |
| Длинное ожидание | Ходы по 28–90 с: [1:05:06](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=3906s)–[1:06:38](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=3998s), «using Bloodthirsty» 66 с ([1:21:36](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4896s)), лаг ~70 с ([1:49:52](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=6592s)). Со стороны похоже на зависание (A7) | A3, A4, A5 timeline | 02 §4.9: «ИИ думает» + эвристика 30 с | глагол + пульс; для онлайна — таймер хода |
| Манёвр соперника | Фигурка идёт вживую, ~325 мс на клетку. Подсветки, пути и следа нет, камера стоит. Фигурки мелкие, ход легко пропустить | [1:09:40](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4180s) `A3/s10_opp_move_4178.jpg`; [1:38:40](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=5920s) `A4/s11_opp_maneuver_4fps.jpg` | MS-P-02 анимация по следу + MS-P-03 подсветка последнего хода 300 мс + строка ленты | **наш план полнее DE**: подсветка последнего хода и лента закрывают пробел, который у DE виден |
| Трекер соперника | Его кружок действия заполняется значком типа | [1:09:40](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4180s) `A3/f_4180_7_oppmove.png` | статус-бар «действия ●●○» только для себя | показывать трекер и у соперника |
| Чужая схема | Карта висит ~1,9 с перед эффектом | [1:12:51](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4371s) | строка ленты | карта-источник в углу на время эффекта |
| Эффект соперника двигает **моего** бойца | Видна только карта и итог; пути нет, отметки «это ваш боец» нет | [1:57:27](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=7047s) `A5/s16_ravening_7047.jpg`; [2:26:10](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=8770s) `A6/s16_scheme_storms_8768.jpg` | MS-R-25: подписано, чей это выбор и чей боец (MS-T-12) | **путь движения моего бойца + карта-источник**, камера стоит (A5, A6) |
| Схема соперника передаёт выбор мне | «Move fog?» — объект, затем «Move fog up to 3 space(s)?» — цель | [3:09:22](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=11362s) | MS-S-12 | та же двухшаговая подача, текст «до N» |
| Что делает игрок | Смотрит превью руки, открывает полноэкранные DECK / HAND / DISCARD обоих игроков. Экран сам закрывается, когда начинается бой | [1:05:42](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=3942s), [2:43:26](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=9806s), [2:02:36](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=7356s) | UI-SCR-INSPECT | просмотр — боковой панелью, автозакрытие при событии, требующем ввода |
| Камера | Онлайн — неподвижна. В обучении ИИ — наезжает (противоречие №5) | [0:18:25](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1105s), [1:39:14](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=5954s) | MS-R-31: камера сама не двигается + стрелка у края | MS-R-31 оставить |

Итог для MS-T-17. В DE сопернику видны только строка, кольцо и живое движение фигурок; следа, подсветки последнего хода и ленты нет. Ведущий заполнял паузы просмотром колод. По нашему плану поверх DE остаются:
- глагол действия соперника рядом с пульсом;
- трекер действий соперника;
- путь, когда эффект соперника двигает моего бойца.

## 6. Подбор хода DE против нашей спецификации → MS-T-08…12, 16

| Аспект | DE | Наша спецификация | Задача и вывод |
|---|---|---|---|
| Начало манёвра | Кнопка Maneuver — добор сразу; кандидатам можно назначать ходы во время добора ([0:53:36](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=3216s)) | предвыбор + чип + Enter (MS-R-01, MS-S-03) | расхождение сознательное; DE доводов против не даёт |
| Кто может ходить | Синие кольца под всеми, кто может ходить; единственный боец выбирается сам ([1:43:02](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=6182s), [1:51:58](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=6718s)) | MS-S-06, Tab | **MS-T-08:** кольца-кандидаты; авто-выбор единственного бойца |
| Достижимые клетки | Бирюзовые кольца по контуру, без заливки и глифа, появляются мгновенно ([0:27:12](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1632s)) | V-01 / V-02: кольцо с кромкой и глиф, ярусы базы и буста (03 §4.1–4.2) | **MS-T-08:** кольцо по контуру DE подтверждает форму. Наблюдение редактора: бирюзовый DE близок к нашему запасному `#4CD2DC` (RK-01) — довод для MS-T-13 |
| Путь и бейдж при наведении | **Нет.** Игроки считают клетки вслух ([1:10:49](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4249s), [1:43:17](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=6197s)) | MS-R-07 / 08 / 12: линия по связям + «шаги/допуск» | **MS-T-09 — самый подтверждённый пункт разбора**, не урезать |
| Порядок и призраки | Клик сразу двигает фигурку; бойцы по одному; после хода сам подсвечивается следующий ([1:35:24](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=5724s)) | черновик: призраки, номера порядка, отправка одной командой | **MS-T-10:** призраки лучше: DE заставляет ждать анимацию перед Confirm ([1:14:06](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4446s)) |
| Подтверждение | Одно «Confirm your move.» на весь манёвр, откат до него ([1:44:24](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=6264s), [0:37:31](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=2251s)) | MS-R-19: одна команда, кнопка с итогом | **MS-T-11:** совпадает. Неподтверждённый ход висит, пока игрок смотрит колоды ([2:52:50](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=10370s)) — это нормально, не торопить |
| Буст | Карты помечены оранжевой рамкой и кружком значения; сброс улетает к доске; после первого шага буст недоступен; ошибочный буст не отменить ([0:30:24](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1824s)) | MS-R-15: смена буста в любой момент, пересчёт в тот же кадр; строка «Буст: … (сброс)» | **MS-T-11:** наш вариант закрывает жалобу ведущего |
| Отказ хода | «Нельзя», причина не объяснена ([0:37:18](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=2238s), в обучении [0:04:56](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=296s)) | `why.*` (MS-T-06 сделано), CUE-004 | подтверждает P2 |
| Pending MOVE / PLACE | «Move X?» — кольца, затем Confirm с откатом; PLACE — кольца на всех допустимых клетках ([0:19:52](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1192s)); Hit and Run «Move Outlaw? / Move Robin Hood?» ([2:19:24](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=8364s)); MOVE вражеского бойца своим эффектом ([0:28:02](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1682s)) | V-11 / V-12, «чей выбор», «Оставить на месте», «Отказаться» | **MS-T-12:** взять двухшаговый «объект → цель (до N)». **Никогда не ждать ввода без подсвеченной цели** ([3:05:34](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=11134s)) — авто-пропуск с причиной (CUE-004) |
| Истощение | Только тултип; урон без подтверждения ([1:27:04](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=5224s)) | MS-S-04 / MS-R-03 | подтверждение оправдано |
| Анимация хода (MS-T-16) | Скольжение или бег **без подскока**; свои 185–440 мс на клетку, соперник ~325; от клика до старта 33–580 мс; 5 клеток — 2,3 с от клика, из них движение ~1,97 с | 280 мс + подскок; потолки 1400 / 2400; перекрытие бойцов 30 %; старт по снапшоту | 280 оставить. Подскок — решение пользователя (05 §7, RK-05): в DE его нет. Старт без паузы. Перекрытие у нас компактнее строгой очерёдности DE ([0:18:18](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1098s)) |
| Скорость и пропуск | Настройка 0.75x–4x; пропуска кликом никто не пробовал | «Нет / Быстро / Обычно / Медленно», пропуск любой клавишей (MS-R-23) | совпадает по духу |

## 7. Анимации фигурок, карт и эффектов → бриф 18 и ICON-MOTION

Ниже — фигурки и персонажи, затем карты и значки.

**Удар (LungeAttack, CUE-008):**
- замах или выпад на месте, без root-смещения; контакт через ~425 мс:
  - Alice — клинок ([0:20:49](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1249s));
  - Sinbad — слэш ([0:27:33](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1653s));
  - Bigfoot — бревно со шлейфом ([1:12:32](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4352s));
  - Arthur — меч с плащом ([2:24:49](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=8689s));
- в DE выпад играет **в резолве**, у нас — в объявлении (CUE-008);
- для брифа 18 цифры DE подтверждают клип ~0,4–0,6 с без root motion (Т2 LungeAttack, AD-OPEN-46).

**Реакция на урон (HitReact, CUE-011).** Красная заливка модели ~430 мс + вздрагивание ([1:25:46](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=5146s), [2:24:50](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=8690s), [3:13:18](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=11598s)). Сверху реакция почти не читается (A1, A2) — поэтому в DE её дублирует сердце HP.

**Смерть героя (DeathSettle, CUE-013).** Пауза, затем растворение ~550 мс цветом героя или игрока. У Sinbad сначала оседание ~670 мс, затем облако ([3:00:35](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=10835s)). Цвет растворения совпадает с ореолом силуэта на экране итогов (A7). Для брифа: DeathSettle 950 мс + «дым цвета команды» (С-11).

**Помощники-жетоны.** Huntsman, Outlaw, Watson и Porter в DE — плоские диски с портретом, не 3D. A1 называет гарпий «жетон-фигуркой» ([0:18:18](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1098s)). Перемещение — скольжение. Смерть — подлёт и переворот рубашкой вверх ~850 мс. Гибель жетона кувырком ведущие смешно обсуждали ([1:47:31](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=6451s)).

Предложение для брифа 18, Т2№4 HAR-DeathSettle и AD-CNF-30. Для помощников с 1 HP без рига CUE-013 можно подать переворотом подставки или жетона ~800 мс. Это решение автора брифа, данных против нет.

**Перемещение.** 3D-герои бегут или идут: плащ у Little Red ([1:35:24](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=5724s)), Bigfoot шагает ([1:14:03](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4443s)), Robin бежит скелетной анимацией ([2:22:57](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=8577s)). Жетоны скользят. Подскока нет нигде. Наше скольжение по D-11 этому не противоречит.

**Большие атаки** без особых анимаций — замечание ведущих ([1:48:59](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=6539s)).

**Карты:**
- переворот ~130 мс;
- карта защиты летит в слот ~500 мс;
- слэмы «N vs M» и «ИМЯ WINS!» ~180–200 мс;
- лучи у карты победителя ~270–500 мс;
- сброс буста улетает к доске;
- чужая схема влетает в угол ~200 мс, уходит ~200–400 мс.

**Значки (ICON-MOTION), кандидаты:**

| Наблюдение DE | Таймкод | Кандидат у нас |
|---|---|---|
| Кольцо вокруг портрета активного игрока, ~900 мс, жёлтое → красное (у A2 с искрами и осколками) | [0:26:55](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1615s) `A2/s06_turn_handoff_portrait.jpg` | новая анимация портрета или кромки для CUE-015 |
| Сердце HP: вспышка → брызги → пульс ~1 с; при смерти — трещина и крест | [0:30:44](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1844s) `A2/s13_death_zoom.jpg` | `resource-hp-full.damage` (сейчас 200 мс) — удлинить пульс; состояние «перечёркнутое сердце» для павшего (рядом с `resource-hp-empty`) |
| Кружок трекера заполняется значком типа действия | [0:19:03](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1143s) | `action-*` / `resource-action-*`: вариант «потрачено = заполнено типом» вместо opacity 0,4 |
| Красный крест-штамп: нет защиты или эффект отменён, ~200–500 мс | [1:12:26](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4346s), [3:13:15](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=11595s) | общий знак «отменено» — по образцу штампа X в `resource-connection-lost` |
| Плашки SCHEME / DISCARDED / BOOSTED! / GUESSED N! слева сверху | [2:55:04](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=10504s) | `marker-status` appear 220 мс |

## 8. Боли и похвалы ведущего и соперников

Ниже — пересказ по `commentary` аналитиков.

**Жалобы:**
- **Нет муллигана** — трижды за стрим ([1:14:43](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4483s), [1:30:15](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=5415s), [3:25:16](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=12316s)).
- **Рука и превью закрывают доску.** Ведущий промахивался кликами и не видел, куда двигает ([1:06:49](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4009s), [1:13:57](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4437s)). Чтобы смотреть руку, приходится водить мышью туда-сюда ([3:25:16](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=12316s)).
- **Нельзя посмотреть состав колоды** ([1:19:51](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4791s)). **Сброс смотреть тяжело**: экран показал одну корзинку вместо всех, карты разложены странно ([1:54:52](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=6892s), [2:12:47](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=7967s)).
- **Таймер мал, бот доигрывает ход.** Вместо бота лучше манёвр на месте; в финале не хватает времени подумать ([1:44:26](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=6266s), [2:07:23](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=7643s), [2:12:47](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=7967s)).
- **Не поставить бойца на нужную клетку**, ведущий назвал это косяком ([0:37:18](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=2238s)). Ошибочный буст не отменить ([0:30:24](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1824s)).
- **Считают клетки вслух**, чтобы понять досягаемость ([1:10:49](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4249s), [1:43:17](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=6197s)).
- **Не понимают порядок эффектов «во время боя»** ([1:41:03](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=6063s)).
- **Подсказка без целей** выглядела как зависание. Реплика участника: «первый баг» ([3:05:50](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=11150s)).
- **Лобби:** столы с паролем скрыты ([0:51:38](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=3098s)); где смотреть достижения — не нашли ([0:59:53](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=3593s)).
- **Известные карты соперника** не помечены, ведущий ждал отметки ([1:05:38](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=3938s)).
- **Диалог Loner by Nature** выскакивает каждый ход ([0:54:34](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=3274s)). Тосты про двери пришлось пролистывать ([0:24:51](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1491s)).
- **У больших атак нет особых анимаций** ([1:48:59](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=6539s)). Туман, похожий на настоящий, выглядит странно: привычнее печатный вид ([3:07:19](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=11239s)).
- **Главные кнопки под вебкой** в правом нижнем углу ([0:15:09](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=909s)). Что-то не закрылось ([0:13:51](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=831s)).

**Похвалы:**
- можно сыграть карту двойным кликом ([0:09:36](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=576s));
- видны колода и сброс соперника ([0:17:01](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1021s));
- буст при манёвре понравился ([0:17:36](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1056s));
- работает зум доски ([0:18:27](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1107s));
- после эффекта известна карта в руке соперника ([0:22:00](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1320s));
- нефункциональная карта помечена ([0:32:27](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1947s));
- эффектный удар понравился ([1:40:21](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=6021s));
- всё автоматизировано и понятно ([2:07:23](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=7643s));
- управление очень удобное; персонажи, звук и анимации приятные ([3:25:10](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=12310s), [3:25:28](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=12328s));
- редкое достижение за победу над Дракулой ([2:06:06](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=7566s)).

**Итог ведущего** ([3:24:48](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=12288s)–[3:25:35](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=12335s)):
- игра будет развиваться;
- героев пока меньше, чем в настольном симуляторе (по автосубтитрам — неуверенно);
- баги, например с дверями, некритичны.

## 9. Рекомендации по следующим этапам (по приоритету)

### P1 — входит в текущие вехи M2–M3

1. **MS-T-09: путь и бейдж «шаги/допуск» не урезать.** Игроки DE считают клетки вслух ([1:10:49](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4249s), [1:43:17](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=6197s)), а DE путь не рисует нигде. Позже стоит добавить слой досягаемости соперника (A3) — это MS-T-22, V-16.
2. **MS-T-17: индикатор соперника с глаголом фазы.** Рядом с пульсом 1 Гц — «Соперник: манёвр / атакует / защищается / выбирает карту / использует <способность>». Ещё:
   - трекер действий соперника;
   - подсветка последнего хода (MS-P-03) и строка ленты — то, чего нет в DE;
   - путь и карта-источник, когда эффект соперника двигает моего бойца ([1:57:27](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=7047s), [2:26:10](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=8770s));
   - камера стоит (MS-R-31).
3. **MS-T-12 + CUE-004: выбор без допустимых целей не ждёт ввода.** Нужен авто-пропуск с причиной ([3:05:34](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=11134s)). Кроме того:
   - текст «Защититься нечем» по образцу «Unable to defend» ([3:21:03](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=12063s));
   - выбор игрока в чужой ход — в два шага, «объект → цель (до N)» ([3:09:22](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=11362s));
   - кнопка «свернуть окно» у модального выбора ([0:19:52](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1192s));
   - для необязательных повторяющихся триггеров — неблокирующий тост вместо модала ([0:54:34](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=3274s));
   - обязательный выбор в начале каждого хода — компактно, с запоминанием прошлого варианта и не закрывая доску (THE SERUM, [3:14:02](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=11642s), A7).
4. **CUE-010 / CUE-011: раскадровка боя DE при нашем темпе.** Порядок: переворот ~130–200 мс → подсветка сработавшей строки эффекта ~400 мс и красный крест-штамп на отменённом → слэм «A vs D» → кадр контакта LungeAttack (~400–450 мс) → HitReact (красная заливка ~430 мс) и смена HP через ~150–200 мс → метка «победил …», в том числе «защита держит» при ничьей.
   - Сумму держать около наших 2,3 с: у DE 12,7 с, и это самая длинная часть хода.
   - Три состояния слота защиты: щит, рубашка, крест.
   - Пропуск кликом.
5. **CUE-015 + ICON-MOTION: кольцо у портрета активного игрока (~900 мс)** — для себя и для соперника, как у DE ([0:19:02](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1142s)). Баннер — только на свой ход, 600 мс, ввод не блокирует. Двухсекундный баннер DE не копировать.
6. **CUE-013 + бриф 18:**
   - помощникам-жетонам (1 HP) — переворот подставки ~800 мс вместо скелетного DeathSettle ([2:17:52](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=8272s));
   - героям — DeathSettle 950 мс с дымом цвета команды; пауза после удара ≤ 1 с (DE — 1–2 с);
   - на HP-плашке павшего — перечёркнутое сердце.
7. **MS-T-16: 280 мс на клетку оставить.** Медиана DE: свои ~368 мс, соперник ~325 мс; противоречие — §4.1. Ещё:
   - стартовать сразу по снапшоту: в DE 0,3–0,6 с задержки от клика заметны;
   - потолок бойца 1400 мс оставить;
   - подскока в DE нет — это вопрос к пользователю (05 §7);
   - авто-выбор единственного бойца и переход к следующему после назначения хода — по желанию в MS-T-07 / MS-T-10.

### P2 — следующая волна HUD и экранов

8. **CUE-016 / UI-SCR-GAMEOVER:**
   - взять у DE 3D-победителя, силуэт проигравшего в цвете игрока и переключатель «посмотреть доску»;
   - добавить то, чего у DE нет: «Сыграть ещё» (02 §2.9 ВОПРОС №5 — в DE реванш занял ~3 мин, [1:30:26](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=5426s)), причину исхода («истощение» — [1:30:13](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=5413s)), краткий итог (раунды, урон, сыгранные карты);
   - переход к экрану ≤ 2 с после смерти (в DE 3,95–12,5 с).
9. **HUD (02 §4):**
   - трекер двух действий со значком типа, в том числе у соперника;
   - главные кнопки — не в правый нижний угол: наш 02 §3.3 уже ставит ПАС и КОНЕЦ ХОДА слева снизу;
   - опускать руку и превью, пока выбирается клетка (UI-INP-001: [1:06:49](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4009s), [1:13:57](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4437s));
   - известные карты руки соперника — лицом (после разбора противоречия №3);
   - просмотр колоды и сброса — боковой панелью, с группировкой копий; автозакрытие при событии, требующем ввода ([2:02:36](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=7356s));
   - одна строка «что делать сейчас» (02 §6).
10. **Таймеры:**
    - таймер защиты оставить видимым (CUE-009, 30 с): в DE его не видно, таймер хода скрыт до последних ~28 с, и ведущий жаловался на нехватку времени ([2:07:23](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=7643s));
    - если появится таймер хода в онлайне — показывать заранее и мягко; по истечении — пас или манёвр на месте, а не ИИ ([1:44:26](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=6266s)).
11. **Карточные мелочи:**
    - карта **чужой** схемы видна ~1,5–2 с перед эффектом (CUE-006 для соперника; в DE ~1,9 с);
    - плашки SCHEME / DISCARDED / BOOSTED! на время эффекта (`marker-status`);
    - единый виджет «выбор числа» (▲▼ + подтвердить + отмена) с плашкой результата ([2:51:44](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=10304s));
    - пульс сердца HP удлинить с 200 до ~600–1000 мс (ICON-MOTION `resource-hp-full.damage`).

### P3 — вне подбора хода

12. **Лобби и вход.** Статусы шагов «подключение / загрузка доски / раздача» вместо немых спиннеров (DE — ~16 с, [0:52:02](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=3122s)). Все столы видны по умолчанию ([0:51:38](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=3098s)). Контекстные подсказки при первом появлении механики ([0:24:44](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1484s)).
13. **История и статистика.** Экран «История»: герой, соперник, карта, исход, раунды, дата + 3 агрегата ([3:23:00](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=12180s)). Данные — из бэкенда.

## 10. Открытые вопросы и таймкоды-эталоны

### 10.1 Открытые вопросы

1. **Кнопки DE в правом нижнем углу** (Maneuver, Confirm, End turn, Pass, «без защиты») закрыты вебкой: их вид и анимации неизвестны (A1–A4).
2. **Пропуск постановки боя и баннеров кликом** — никто не пробовал. Неизвестно, блокирует ли YOUR TURN клики; наведение он точно не блокирует (A1–A5, A7).
3. **Где таймер TIMER Live.** Видна только полоса хода в последние ~28 с; лимит ~85 с — оценка (A5). Таймер защиты не найден.
4. **Пауза 2,6–2,9 с между раскрытием и счётом** — фиксированная или это сеть и порядок эффектов (A1, A4)?
5. **Когда DE показывает «−N»** — противоречие №2.
6. **Когда известные карты соперника показываются лицом** — противоречие №3.
7. **Почему одни помощники переворачиваются, а другие исчезают за кадр** (противоречие №7). Зависит ли это от типа фигурки?
8. **Авто-камера в ход ИИ** ([0:18:25](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1105s)) против неподвижной ([0:26:52](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1612s)) — режим или настройка?
9. **Экраны HERO и HAND перед результатом** ([2:33:52](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=9232s)) — показ игры или клик игрока (A6)?
10. **«Deal 2 damage» без целей** ([3:05:34](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=11134s)) — зависание или ведущий не нашёл цель (A7)?
11. **Ромб с числом у портрета и бейдж 1st/2nd.** Назначение ромба не установлено. В соло у Alice стоит «1st», хотя первым ходил игрок (A2).
12. **Звук не разбирался.** Для колонки `sound` CUE и MS-T-18 нужен отдельный аудиоразбор (A6, A7).
13. **VFX взгляда Медузы** (CUE-014) на листах не замечен; нужна лента [0:12:30](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=750s)–770 с (A1).
14. **Чем закрывается экран результата** — авто или клик (A4)?
15. **Вопрос пользователю (редактор).**
    - Наш бой (2,3 с) против DE (~12,7 с): оставить быстрый темп с пропуском или добавить паузу «прочитать карту соперника» ~1–1,5 с (A2)?
    - Подскок при шаге: в DE его нет.

### 10.2 Таймкоды-эталоны для просмотра человеком

Ниже 36 таймкодов.

| # | Таймкод | Что смотреть | Лента или кадр |
|---|---|---|---|
| 1 | [0:16:08](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=968s) | Настройки GAMEPLAY: скорость 1x, выключение боевой камеры | `A1/f_settings_968.png` |
| 2 | [0:16:49](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1009s) | Выбор бойца и бирюзовые кольца клеток | `A1/f_move_select_1009.png` |
| 3 | [0:17:22](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1042s) | Свой ход Jabberwock без подскока, затем «Confirm your move.» | `A1/s02b_move_jab_crop.jpg` |
| 4 | [0:17:58](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1078s) | Добор карты при манёвре, 333 мс | `A1/s18_draw_fly_1078.jpg` |
| 5 | [0:18:18](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1098s) | Гарпии ИИ ходят строго по очереди | `A1/s12_ai_harpy_move_1098.jpg` |
| 6 | [0:19:02](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1142s) | Кольцо у портрета соперника + трекер действий | `A1/s14_ability_icon_1143.jpg` |
| 7 | [0:19:14](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1154s) | COMBAT! — атака ИИ | `A1/s17_combat_intro_ai_1153.jpg` |
| 8 | [0:19:35](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1175s) | Раскрытие и пауза ~2,9 с до «3 vs 1» | `A1/s16_defense_reveal_1174.jpg` |
| 9 | [0:19:52](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1192s) | Модал «Choose two» + свернуть окно, затем PLACE | `A1/f_modal_choose_1192.png` |
| 10 | [0:20:48](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1248s) | «5 vs 0», выпад, «−5» у сердца, ALICE WINS | `A1/s06_hit_damage_1250.jpg` |
| 11 | [0:22:46](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1366s) | Смерть героя: зелёное растворение, потом баннер | `A1/s20_medusa_death_1363.jpg` |
| 12 | [0:25:25](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1525s) | YOUR TURN, наведение работает поверх | `A2/s03_your_turn_banner.jpg` |
| 13 | [0:26:55](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1615s) | Кольцо у портрета с искрами и осколками | `A2/s06_turn_handoff_portrait.jpg` |
| 14 | [0:27:16](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1636s) | Porter: 3 клетки за 1,13 с | `A2/s23_porter_slide.jpg` |
| 15 | [0:30:43](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1843s) | Смерть помощника: подставка кувыркается, сердце перечёркнуто | `A2/s13_death_zoom.jpg` |
| 16 | [0:37:20](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=2240s) | «Move Sinbad?» → «Confirm your move.» → откат; ругань ведущего | `A2/s27_move_restriction_complaint.jpg` |
| 17 | [0:38:11](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=2291s) | Смертельный удар → экран SINBAD WINS через ~9,9 с | `A2/s16_victory_screen.jpg` |
| 18 | [0:52:02](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=3122s) | Вход в онлайн-партию, ~16 с одних спиннеров | `A3/s14_join_load_3122.jpg` |
| 19 | [1:09:32](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4172s) | Начало хода соперника и урон способностью без «−N» | `A3/s12_bloodthirsty_dmg_4173.jpg` |
| 20 | [1:10:49](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4249s) | Ведущий считает клетки вслух, нет пути | A3 commentary[8] |
| 21 | [1:12:19](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4339s) | Дуга к цели → наезд → ожидание → крест → «5 vs 0» → смерть Sister | `A3/s02_combat_zoom_4339.jpg`, `A3/s04_resolve_4348.jpg` |
| 22 | [1:12:57](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4377s) | Своя защита: свой слот слева, рамки годных карт, отмена Feeding Frenzy | `A3/s07_me_defend_4377.jpg`, `A3/s08_reveal_cancel_4382.jpg` |
| 23 | [1:14:03](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4443s) | Bigfoot: 2,3 с от клика (~0,4 с разворот, ~1,97 с на 5 клеток), «Confirm» только после прихода | `A3/s09_move_hoax_4444.jpg` |
| 24 | [1:25:46](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=5146s) | Урон в бою: красная заливка, HP 12 → 10 мгновенно | `A4/s06_hit_heart_crop.jpg` |
| 25 | [1:30:13](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=5413s) | Смерть от истощения → сгорание → ZZZZAAI WINS | `A4/s08_exhaustion_death_crop.jpg` |
| 26 | [1:35:24](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=5724s) | Little Red бежит; следующий боец подсвечивается сам | `A4/s10_LR_step_30fps.jpg` |
| 27 | [1:43:58](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=6238s) | Таймер хода (последние ~28 с) и тост «ход доиграл ИИ» | `A5/s05_turn_timer_6180.jpg`, `A5/f_6267_ai_toast.png` |
| 28 | [1:48:58](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=6538s) | Смерть жетона Huntsman | `A5/s07_huntsman_death_crop.jpg` |
| 29 | [1:57:27](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=7047s) | Схема соперника двигает **мою** Little Red, пути нет | `A5/s16_ravening_7047.jpg` |
| 30 | [1:58:58](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=7138s) | Сброс на буст: карта к доске, расширенная сетка | `A5/s11_boost_move_7138.jpg` |
| 31 | [2:17:52](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=8272s) | Outlaw: переворот жетона рубашкой вверх | `A6/s02_outlaw_death_crop_8272.jpg` |
| 32 | [2:24:49](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=8689s) | Замах Артура и реакция Robin, «−6» | `A6/s20_arthur_lunge_8689.jpg`, `A6/s19_robin_hit_8689.jpg` |
| 33 | [2:33:42](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=9222s) | Смерть Robin → экран MONTAJ WINS через ~12,5 с | `A6/s05_robin_death_crop_9224.jpg`, `A6/s06_gameover_9226.jpg` |
| 34 | [3:05:34](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=11134s) | «Deal 2 damage.» без целей ~24 с | `A7/f_11146_deal2_wait.png` |
| 35 | [3:13:07](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=11587s) | Бой целиком ~15,3 с, урон без «−N» | `A7/strip_g3_combat_intro_11586.jpg`, `A7/strip_g3_damage_hp_11598.jpg` |
| 36 | [3:21:03](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=12063s) | «Unable to defend!», смерть Hyde, экран итогов | `A7/strip_g3_final_combat_end.jpg` |

## Ревью

Один проход, 2026-10-04. Ревьюер перемерил ключевые числа своими лентами (`burst.py strip` 30 fps, местами 10–15 fps, и `burst.py motion` / `segs`). Ленты лежат локально в `C:/tmp/de-footage/findings/review/` (`r01…r14`), в репозиторий не кладутся.

### Что проверено

Перемер лентами — 14 чисел:

| Число | Таймкод | DE в разборе | Перемер ревью | Итог |
|---|---|---|---|---|
| Добор карты | [0:17:58](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1078s) | 333 | 1078.95 → 1079.28, ~333 | подтверждено |
| Шаг своего бойца, Bigfoot (A3) | [1:14:03](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4443s) | 454 на клетку | клик 4443.70; разворот на месте до 4444.07; движение 4444.10–4446.07 = ~1,97 с на 5 клеток, ~395 на клетку | **исправлено** |
| Шаг соперника, Jabberwock ИИ (A2) | [0:26:52](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1612s) | 267 (3 клетки, 800 мс) | 2 клетки (кадры до и после), 1612.10–1612.80 = ~700 мс, ~350 на клетку | **исправлено** |
| Шаг соперника, Dracula (A3) | [1:09:40](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4180s) | 500 (1 клетка) | 2 клетки; начало закрыто превью карты ведущего до 4180.43, остановка ~4181.33; ~0,9 с, ~450 на клетку (±70) | **исправлено** |
| Кольцо у портрета | [0:19:02](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1142s) | 933 | 1142.85 → 1143.80, ~950 | подтверждено |
| Баннер YOUR TURN | [0:25:25](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1525s) | 2030 | клякса 1525.20 → исчезла 1527.20, ~2000 (лента 15 fps) | подтверждено |
| Анонс COMBAT! | [3:13:07](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=11587s) | 1470 | облако 11587.6, надпись 11588.33, тает к 11589.07 | подтверждено |
| До «Play a card to defend?» | [3:13:07](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=11587s) | 1930 | строка видна с 11589.53 | подтверждено |
| Переворот карты | [0:19:35](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1175s) | 100 | рубашка 1174.98 → лицо 1175.02, выровнена к 1175.12; 100–130 | подтверждено |
| Раскрытие → счёт | [0:19:35](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1175s) | 2870 | 1175.0 → «3 vs 1» 1177.98, ~2980 | в пределах точности |
| Слэм «N vs M» | [0:19:38](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=1178s) | 130 | 1177.98 → лента 1178.15–1178.18, 170–200 | в пределах медианы 180 |
| Счёт → удар | [2:24:47](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=8687s) | 2170 | «3 vs 9» 8687.93 → вспышка 8690.07, ~2130 | подтверждено |
| Удар → смена HP | [3:13:18](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=11598s) | 167 | контакт 11598.13, 7 → 6 в 11598.30, 167; «−N» нет | подтверждено |
| Красная заливка цели | [3:13:18](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=11598s) | 400 | 11598.17 → 11598.63, ~467 | не правлено: разница 2 кадра, медиана 430 в коридоре 400–470 |
| Показ чужой схемы | [1:12:51](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=4371s) | 2330 | влёт 4371.2–4371.4, уход 4373.7–4373.8, ~2300–2400 (лента 10 fps) | подтверждено |

Ещё проверено:
- **timings.csv.** Для всех 45 строк n, медиана, минимум, максимум и Δ пересчитаны из списка «значения» в примечании; число примеров совпадает с n. Расхождений не было, кроме двух строк, исправленных ниже. Все пути-доказательства из CSV и README существуют в `C:/tmp/de-footage/findings/`.
- **Ссылки.** Все ссылки на YouTube (363 до ревью, 379 с этим разделом): текст ч:мм:сс совпадает с `t=…s`.
- **Копии аналитиков.** `findings/A1.json` … `A7.json` побайтно совпадают с `C:/tmp/de-footage/findings/A*/result.json`.
- **Полнота.** Сверены `ux`, `open_questions` и события всех семи result.json с §2–§10. Рекомендации P1–P3 привязаны к MS-T, CUE, HUD и ICON-MOTION и опираются на замеры; противоречия аналитиков вынесены в §4.1, а не сглажены. Выборочно сверены факты: версия клиента и сервера, Medium в настройках графики, Hard в соло, дата 07.08.2026, ник на экране результата «ZZZZAAI» (так в кадре [1:30:20](https://www.youtube.com/watch?v=G6wJgtcOjVA&t=5420s)).
- **Границы.** `git status --porcelain -- docs/game-design/de-footage` показывает только новые файлы этой папки: README.md, timings.csv и findings/A1–A7.json. Картинок в папке нет. Длинных цитат ведущего нет; фрагменты в «» длиннее 15 слов — это перечни строк интерфейса игры (статусы соперника, тултип Exhaustion в A7.json), а не речь ведущего.

### Что исправлено

1. `timings.csv`, `move_step_own`: значение A3 454 → 395. Максимум 454 → 440. Медиана 368 и Δ +88 не изменились.
2. `timings.csv`, `move_step_opponent`: A2 267 → 350, A3 500 → 450. Медиана 295 → 325, диапазон 267–500 → 290–450, Δ +15 → +45. Обоснование дописано в примечание строки.
3. README §3.2, §4 (таблица и противоречие №1), §5, §6 (MS-T-16), §9 п. 7 и §10.2 №23 приведены к новым числам. Для Bigfoot указано: 2,3 с от клика, из них ~0,4 с — разворот на месте.
4. README §9 п. 3: добавлена рекомендация A7 из `ux` (11088), которая была потеряна. Обязательный выбор в начале хода (THE SERUM) делать компактно, с запоминанием прошлого варианта.

Выводы разбора от этого не меняются: 280 мс на клетку остаются в коридоре DE (свои 368, соперник 325).

### Что не проверено

- Остальные ~30 строк `timings.csv` перемером не проверялись — только арифметикой по значениям аналитиков. В частности: смерть героя и жетона, путь «смертельный удар → экран результата», «−N», лечение, PLACE, каскад раздачи, загрузки.
- Число клеток в замерах A1 (Jabberwock, ~4), A5 (Little Red и Huntsman, ~3) и A6 (Robin, 3 или 4) не пересчитывалось. Мс на клетку там остаются приблизительными.
- Противоречия №2, №3, №5 и №7 (§4.1) и открытые вопросы §10.1 ревью не разрешало.
- Пересказы реплик ведущего (§8) с автосубтитрами не сверялись.
- Звук не анализировался — как и во всём разборе.
- Документы проекта, на которые ссылаются рекомендации (02, 03, 07-csv, ICON-MOTION, MS-T), на актуальность значений «Наш CUE» не сверялись.
