# 04 — Реплики героев MVP

Дата: 2026-10-05. Фаза 2 аудио-чата. Правила событий, частоты, приоритетов и субтитров — [02-audio-design.md](02-audio-design.md)
§3; строки реестра — `VO-*` в [03-sound-registry.csv](03-sound-registry.csv). Статус — «предложено»: тексты
утверждает пользователь до генерации.

## 0. Правила текста
- **Все тексты оригинальные.** Написаны для этого проекта. Не взяты из Unmatched: Digital Edition, с карт, из книг
  правил, фильмов или книг. Имена легенд (Excalibur, Camelot, Lady of the Lake, Grail) — общественное достояние.
- Язык — английский, 1–5 слов, до 2 с (победа и поражение — до 3 с). RU — субтитры, EN — субтитры на английском
  интерфейсе и сам текст озвучки.
- **Скрытое не называется.** Реплика защиты — безличная (до раскрытия соперник не знает карту); фирменные реплики
  карт звучат только при раскрытии или резолве.
- Реплика не описывает правило и не обещает эффект, которого нет (никаких «я выберу за тебя»).
- Усилия, крики и стоны (`hurt`, `death`, гарпии) — без слов, без субтитров; при опции «Описывать звуки» —
  `[описание]`.
- Направление для ElevenLabs v3 — звуковыми тегами в квадратных скобках (`[firm]`, `[whispers]`, `[hissing]`,
  `[grunts]`); тег ставится в начало текста генерации и не попадает в субтитры.
- Файл: `VO_<FIGHTER>_<EVENT>_<NN>.wav`, ID строки реестра — `VO-<FIGHTER>-<EVENT>`, номер — суффикс файла.

## 1. Голоса

| Боец | Голос | Подбор (кастинг) |
|---|---|---|
| King Arthur | зрелый баритон, тёплый, твёрдый, британская или нейтральная речь | 3–4 готовых голоса ElevenLabs, пробные строки: `ARTHUR-ATTACK-02`, `ARTHUR-LOW-HP-02`, `ARTHUR-VICTORY-01` |
| Merlin | пожилой, лёгкий, сухой; лукавство и полушёпот | 3–4 голоса; пробы: `MERLIN-CARD-STORMS-01`, `MERLIN-DEFEND-02`, `MERLIN-CARD-PROPHECY-01` |
| Medusa | низкое контральто, холодное, царственное; «s» чуть тянется, без карикатуры | 3–4 голоса; пробы: `MEDUSA-SELECT-01`, `MEDUSA-ABILITY-02`, `MEDUSA-VICTORY-02` |
| Harpy ×3 | крики без слов; три гарпии — сдвиг высоты −2 / 0 / +2 полутона и разный формант | пробы: `HARPY-ATTACK-01..03` |

Голос выбирает пользователь на слух. Выбранный `voice_id`, модель и настройки (stability, style) записываются в
манифест и не меняются между репликами одного бойца.

## 2. King Arthur — 42 реплики

| ID | EN (текст озвучки) | RU (субтитр) | Направление |
|---|---|---|---|
| ARTHUR-SELECT-01 | The crown answers. | Корона отвечает. | [calm] [resolute] |
| ARTHUR-SELECT-02 | Camelot rides with me. | Камелот со мной. | [warm] [proud] |
| ARTHUR-MATCH-START-01 | Stand fast. This ground is ours. | Стоять крепко. Эта земля наша. | [firm] |
| ARTHUR-MATCH-START-02 | For the Table. For the realm. | За Круглый стол. За королевство. | [rousing] |
| ARTHUR-MATCH-START-03 | Let this be settled with honor. | Решим это с честью. | [measured] |
| ARTHUR-MATCHUP-MEDUSA-01 | Keep your gaze, gorgon. I'll keep my sword. | Оставь себе свой взгляд, горгона. Мне хватит меча. | [dry] [firm] |
| ARTHUR-MATCHUP-MEDUSA-02 | Stone or steel. We'll see which breaks. | Камень или сталь — посмотрим, что треснет. | [calm] [confident] |
| ARTHUR-TURN-START-01 | Forward. | Вперёд. | [firm] |
| ARTHUR-TURN-START-02 | My move. | Мой ход. | [calm] |
| ARTHUR-TURN-START-03 | Steady now. | Спокойно. | [quiet] |
| ARTHUR-ATTACK-01 | Have at you! | Защищайся! | [shouting] |
| ARTHUR-ATTACK-02 | For Camelot! | За Камелот! | [battle cry] |
| ARTHUR-ATTACK-03 | Yield! | Сдавайся! | [commanding] |
| ARTHUR-ATTACK-04 | Face me! | Лицом ко мне! | [shouting] |
| ARTHUR-DEFEND-01 | Shields up. | Щит! | [firm] |
| ARTHUR-DEFEND-02 | Let it come. | Пусть бьёт. | [calm] |
| ARTHUR-HURT-01 | — | — | [grunts] |
| ARTHUR-HURT-02 | — | — | [sharp exhale] |
| ARTHUR-HURT-03 | — | — | [pained breath] |
| ARTHUR-HURT-BIG-01 | A fair blow. | Хороший удар. | [through gritted teeth] |
| ARTHUR-HURT-BIG-02 | Still standing! | Я ещё стою! | [defiant] |
| ARTHUR-LOW-HP-01 | Not yet. Not yet. | Ещё рано. Ещё рано. | [breathless] |
| ARTHUR-LOW-HP-02 | The king does not kneel. | Король не преклоняет колен. | [strained] [defiant] |
| ARTHUR-ALLY-DOWN-01 | Merlin! No! | Мерлин! Нет! | [anguished] |
| ARTHUR-ALLY-DOWN-02 | Rest, old friend. | Покойся, старый друг. | [quiet] [grieving] |
| ARTHUR-ENEMY-DOWN-01 | One less. | Одной меньше. | [flat] |
| ARTHUR-ENEMY-DOWN-02 | Back to the storm with you. | Возвращайся в бурю. | [dry] |
| ARTHUR-ABILITY-01 | With all my strength! | Изо всех сил! | [straining] |
| ARTHUR-ABILITY-02 | Blade and heart together. | Клинок и сердце заодно. | [intense] [low] |
| ARTHUR-CARD-EXCALIBUR-01 | Excalibur! | Экскалибур! | [battle cry] |
| ARTHUR-CARD-EXCALIBUR-02 | Shine, Excalibur! | Сияй, Экскалибур! | [triumphant] |
| ARTHUR-CARD-GRAIL-01 | The Grail restores me. | Грааль возвращает мне силы. | [reverent] [relieved] |
| ARTHUR-CARD-LADY-01 | Lady of the Lake, I need the blade. | Владычица Озера, мне нужен клинок. | [earnest] |
| ARTHUR-SCHEME-01 | A king plans ahead. | Король думает наперёд. | [calm] |
| ARTHUR-SCHEME-02 | Every move has purpose. | У каждого шага есть цель. | [measured] |
| ARTHUR-IDLE-01 | Nothing to wait for. | Нечего ждать. | [impatient] |
| ARTHUR-IDLE-02 | The field won't wait forever. | Поле не будет ждать вечно. | [dry] |
| ARTHUR-DEATH-01 | — | — | [defiant cry] [falling] |
| ARTHUR-VICTORY-01 | Camelot stands. | Камелот стоит. | [proud] [warm] |
| ARTHUR-VICTORY-02 | Honor is satisfied. | Честь соблюдена. | [calm] [dignified] |
| ARTHUR-DEFEAT-01 | A worthy end. | Достойный конец. | [quiet] [dignified] |
| ARTHUR-DEFEAT-02 | Remember us. | Помните нас. | [weary] |

## 3. Merlin — 17 реплик

| ID | EN | RU | Направление |
|---|---|---|---|
| MERLIN-MATCH-START-01 | Ah. I've seen how this ends. | А-а. Я видел, чем это кончится. | [amused] [wry] |
| MERLIN-ATTACK-01 | Mind the sparks. | Осторожно, искры. | [playful] |
| MERLIN-ATTACK-02 | A small lesson. | Маленький урок. | [dry] |
| MERLIN-ATTACK-03 | Right between the eyes. | Прямо меж глаз. | [mischievously] |
| MERLIN-DEFEND-01 | Not today. | Не сегодня. | [calm] |
| MERLIN-DEFEND-02 | Tsk. Clumsy. | Ц-ц. Неуклюже. | [disapproving] |
| MERLIN-HURT-01 | — | — | [sharp gasp] |
| MERLIN-HURT-02 | — | — | [annoyed grunt] |
| MERLIN-DEATH-01 | — | — | [long fading breath] |
| MERLIN-ENEMY-DOWN-01 | Feathers everywhere. | Кругом перья. | [dry] |
| MERLIN-ENEMY-DOWN-02 | Shoo. | Кыш. | [dismissive] |
| MERLIN-CARD-PROPHECY-01 | Let me peek at tomorrow. | Загляну-ка в завтра. | [whispers] [curious] |
| MERLIN-CARD-STORMS-01 | Winds, wake up! | Ветра, проснитесь! | [commanding] [rising] |
| MERLIN-CARD-STORMS-02 | Hold on to your hats. | Держите шляпы. | [amused] |
| MERLIN-CARD-SPIRITS-01 | The old dead owe me a favor. | Старые мертвецы мне задолжали. | [low] [ominous] |
| MERLIN-CARD-BEWILDERMENT-01 | Look again. I'm not there. | Присмотрись. Меня там нет. | [whispers] [teasing] |
| MERLIN-ALLY-LOW-01 | Arthur, step back and breathe! | Артур, назад, отдышись! | [urgent] |

## 4. Medusa — 42 реплики

| ID | EN | RU | Направление |
|---|---|---|---|
| MEDUSA-SELECT-01 | They will look. They always do. | Они посмотрят. Они всегда смотрят. | [cold] [slow] |
| MEDUSA-SELECT-02 | Come, little statues. | Идите сюда, мои статуи. | [hissing] [amused] |
| MEDUSA-MATCH-START-01 | Another ornament for my garden. | Ещё одно украшение для сада. | [cold] |
| MEDUSA-MATCH-START-02 | Turn and face me. | Повернись ко мне. | [commanding] |
| MEDUSA-MATCH-START-03 | Stone is patient. So am I. | Камень терпелив. Я тоже. | [slow] [menacing] |
| MEDUSA-MATCHUP-ARTHUR-01 | A king in armor. Armor cracks too. | Король в доспехах. Доспехи тоже трескаются. | [mocking] |
| MEDUSA-MATCHUP-ARTHUR-02 | Keep your sword, king. I'll keep you. | Держи свой меч, король. А тебя оставлю себе. | [cold] [amused] |
| MEDUSA-TURN-START-01 | My turn. | Мой ход. | [cold] |
| MEDUSA-TURN-START-02 | So. | Итак. | [hissing] |
| MEDUSA-TURN-START-03 | Where shall I look? | Куда же мне посмотреть? | [musing] |
| MEDUSA-ATTACK-01 | Hold still. | Замри. | [cold] |
| MEDUSA-ATTACK-02 | Look at me. | Посмотри на меня. | [commanding] |
| MEDUSA-ATTACK-03 | One arrow is enough. | Хватит одной стрелы. | [calm] [menacing] |
| MEDUSA-ATTACK-04 | Run, if you like. | Беги, если хочешь. | [mocking] |
| MEDUSA-DEFEND-01 | Touch me? Try. | Тронуть меня? Попробуй. | [scornful] |
| MEDUSA-DEFEND-02 | Too slow. | Слишком медленно. | [cold] |
| MEDUSA-HURT-01 | — | — | [hiss of pain] |
| MEDUSA-HURT-02 | — | — | [sharp gasp] |
| MEDUSA-HURT-03 | — | — | [snarls] |
| MEDUSA-HURT-BIG-01 | You will pay in stone. | Заплатишь камнем. | [furious] [low] |
| MEDUSA-HURT-BIG-02 | How dare you. | Как ты смеешь. | [outraged] |
| MEDUSA-LOW-HP-01 | Not by your hand. | Не от твоей руки. | [strained] [hissing] |
| MEDUSA-LOW-HP-02 | I have survived worse than you. | Я пережила и худшее. | [strained] [proud] |
| MEDUSA-ALLY-DOWN-01 | My wings, fallen. | Мои крылья пали. | [cold] [bitter] |
| MEDUSA-ALLY-DOWN-02 | You'll answer for her. | Ответишь за неё. | [venomous] |
| MEDUSA-ENEMY-DOWN-01 | The old man sleeps. | Старик уснул. | [amused] |
| MEDUSA-ABILITY-01 | Look. | Смотри. | [whispers] |
| MEDUSA-ABILITY-02 | Become stone. | Стань камнем. | [slow] [hissing] |
| MEDUSA-ABILITY-03 | Meet my eyes. | Встреть мой взгляд. | [seductive] [cold] |
| MEDUSA-CARD-GAZE-OF-STONE-01 | Now be still forever. | Теперь замри навсегда. | [triumphant] [cold] |
| MEDUSA-CARD-GAZE-OF-STONE-02 | Silence, in stone. | Тишина в камне. | [whispers] |
| MEDUSA-CARD-GLANCE-01 | Even a glimpse is enough. | Хватит и мимолётного взгляда. | [amused] |
| MEDUSA-CARD-FRENZY-01 | Wings! Tear them apart! | Крылья! Рвите их! | [shouting] [fierce] |
| MEDUSA-CARD-HISS-01 | Back. | Назад. | [hissing] [sharp] |
| MEDUSA-SCHEME-01 | Patience. Then poison. | Терпение. Потом яд. | [slow] |
| MEDUSA-IDLE-01 | I grow bored. | Мне скучно. | [sighs] [cold] |
| MEDUSA-IDLE-02 | Even stone gets restless. | Даже камню не терпится. | [dry] |
| MEDUSA-DEATH-01 | — | — | [long hiss fading] |
| MEDUSA-VICTORY-01 | My garden grows. | Мой сад растёт. | [satisfied] [slow] |
| MEDUSA-VICTORY-02 | Beautiful. And so still. | Красиво. И так неподвижно. | [whispers] [pleased] |
| MEDUSA-DEFEAT-01 | Look away. Now. | Отвернись. Теперь. | [bitter] [quiet] |
| MEDUSA-DEFEAT-02 | Stone remembers. | Камень помнит. | [cold] [fading] |

## 5. Гарпии — 12 криков × 3 высоты

| ID | Что | Направление |
|---|---|---|
| HARPY-ATTACK-01…03 | пронзительный визг налёта | короткий, атака 0,3–0,6 с; хищная птица + женский крик |
| HARPY-HURT-01…02 | резкий клёкот | 0,2–0,4 с |
| HARPY-DEATH-01…02 | падающий визг | 0,6–1,2 с, высота вниз |
| HARPY-FRENZY-01…02 | хор визгов (три голоса сразу) | 0,8–1,2 с; три слоя со сдвигом −2 / 0 / +2 |
| HARPY-ENEMY-DOWN-01…02 | злорадное стрекотание | 0,5–0,9 с |
| HARPY-RETURN-01 | восходящий визг возвращения | 0,6–0,9 с |

Каждый крик — в трёх версиях (гарпия 1, 2, 3); версия выбирается по ID бойца. Источник — ElevenLabs v3 с тегами;
если крики выходят неубедительно, — обработанные CC0-записи хищных птиц (план производства).

## 6. Матрица событий и счёт

| Событие | Arthur | Merlin | Medusa | Harpy |
|---|---|---|---|---|
| select | 2 | — | 2 | — |
| match_start / matchup | 3 + 2 | 1 | 3 + 2 | — |
| turn_start | 3 | — | 3 | — |
| attack / defend | 4 / 2 | 3 / 2 | 4 / 2 | 3 / — |
| hurt / hurt_big | 3 / 2 | 2 / — | 3 / 2 | 2 / — |
| low_hp / ally_low | 2 | 1 | 2 | — |
| ally_down / enemy_down | 2 / 2 | — / 2 | 2 / 1 | — / 2 |
| ability | 2 | — | 3 | — |
| фирменные карты | 4 (3 карты) | 5 (4 карты) | 5 (4 карты) | 2 (frenzy) |
| scheme | 2 | — | 1 | — |
| idle | 2 | — | 2 | — |
| death | 1 | 1 | 1 | 2 |
| victory / defeat | 2 / 2 | — | 2 / 2 | — |
| return | — | — | — | 1 |
| **Всего** | **42** | **17** | **42** | **12 × 3** |

Ожидаемая плотность: партия ~15 минут, 20–35 реплик с учётом вероятностей и бюджета «≤ 1 на 20 с» (02 §3.2).
