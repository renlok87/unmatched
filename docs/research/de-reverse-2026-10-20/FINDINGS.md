MISSING READERS: []

######## DIM rules-engine — Движок правил: система эффектов и способностей
SUMMARY: Вердикт: на DSL оригинала (C#, «контент как код», сериализуемые корутины) не переходить, каталог лямбд DuelEngine не брать. Наша модель остаётся: эффекты карт как данные CardEffect, ABILITY_CONFIGS и очередь боя с продолжением в виде данных.

**Что уже совпадает с оригиналом:**
- окна Immediate/During/After с защитником первым;
- проверка конца игры;
- Cancel с сохранением печатного значения и сгоранием буста Артура;
- хуки героев после after-эффектов карт.

**Где мы отстаём — в композиции, не в окнах:**
- Парсер полностью распознаёт 264 из 880 карт (мой прогон; в документе 271 из 855).
- На 188 общих с DE картах: 65 из 78 карт с общими способностями DE, но только 18 из 110 «уникальных».
- Способности есть у 29 из примерно 84 героев. У 6 из 14 базовых героев DE их нет совсем: Sinbad, Sherlock, Jekyll&Hyde, Invisible Man, Little Red, Beowulf.

Даже у Dire Wolf 111 из 189 карт имеют отдельный скрипт. Но эти скрипты собраны из маленькой грамматики: примерно 15 глаголов, квантификаторы Selected/First/All/Random с предикатами, Then/If, «may» через CustomChoice, а также открытые события с предикатами Source/Target/Owner.

**Что взять как идеи, в TS:**
- **P1:** единый словарь эффектов для карт и способностей; выбор цели и «may» как параметры эффекта (R1).
- **P1:** точечные исправления правил (R2): Sherlock не отменяется; Dracula выбирает цель и может отказаться; доборы со словом «may» у Bigfoot/Philippa/Chupacabra (сейчас на пустой колоде они дают истощение); Achilles; Michelangelo.
- **P2:**
  - открытая шина событий с записями «до тех пор, пока» в GameState (R3);
  - составной IR эффектов, JSON в БД и редактирование в админке, с выходом в именованный TS-скрипт для уникальных карт (R4) — по шагам, под конкретных героев;
  - эталонный тест парсера по классам способностей DE (R8);
  - удалить мёртвый ValueModifierService, временные моды хранить в состоянии (R9).

P0 в этом измерении нет: основную пару Medusa/Arthur расхождения не затрагивают, их карты распознаются полностью.

Не проверял:
- правильно ли «полностью распознанные» карты исполняются, а не только находятся парсером;
- живую БД (Docker остановлен);
- поведение DuelEngine для Dracula и Bigfoot, кроме того, что пассивок у них там нет.
OURS: У нас два независимых словаря: один для карт, другой для героев. Исполнение боя уже устроено как данные, но масштабирование упирается в композицию эффектов.

(1) Карты.
- effect-text-parser.ts (PARSER_VERSION 9, около 59 regex-шаблонов по английским полям effectImmediately/During/After) превращает текст в CardEffect[] (backend/src/game-engine/effects/effect-text-parser.ts:1-27).
- EffectType — 24 значения, включая UNSUPPORTED (models/card.model.ts:170-218). Тайминги — ON_REVEAL / DURING_COMBAT / AFTER_COMBAT / ON_PLAY (:224).
- Тексты boost/ongoing всегда UNSUPPORTED. Нераспознанное уходит в manualEffects и не исполняется.
- Прогон парсера по 880 картам scraped-data (мой скрипт scratchpad/effects-judge/run.ts, результат в coverage.json):

| Статус | Карт | Копий (из 2094) |
|---|---|---|
| распознано полностью | 264 | 653 |
| частично | 175 | 406 |
| ничего | 416 | 981 |
| без текста | 25 | 54 |

  Это согласуется с «271 из 855» в docs/backend-api/db-divergence-2026-10-03.md:370.
- На 188 картах, общих с DE:
  - карты DE только с общими (параметризованными) способностями: полностью 60 и ещё 5 без текста, итого 65 из 78;
  - карты DE с уникальным скриптом: полностью 17 и ещё 1 без текста, итого 18 из 110, при этом у 60 не распознано ничего.
- Исполнение боя в CardEffectExecutor — сериализуемая очередь CombatEffectContinuation, то есть продолжение хранится как данные, а не как генератор (card-effect-executor.service.ts:172-240):
  - защитник ходит первым на каждой стадии;
  - D
- [R1] P1 | adapt | src=original | Один словарь эффектов для карт и способностей героев, плюс выбор цели и «may» как параметры эффекта
   why: В оригинале у карт и пассивок бойцов один и тот же язык (DuelGrammar.Damage/Draw/Move в scripts/actions и в scripts/fighters). Способ выбора цели задаётся квантификатором: Selected.From (выбирает игрок), First.From (первая подходящая), All.From. «May» — это CustomChoice с вариантом Noop. У нас AbilityEffect (11 видов) — отдельный словарь, и generic-hero-ability.handler сам повторяет урон, добор и движение. Каждая вариация печатного текста требует нового kind: turn-damage и pending-target-damage различаются только областью целей и тем, можно ли отказаться. Из-за этого Dracula бьёт сам без выбора, а Bigfoot, Philippa и Chupacabra добирают принудительно.
   benefit: Способности новых героев начнут использовать 24 уже исполняемых EffectType вместе с общим протоколом pendingEffects (TARGET_FIGHTER, MOVE, CHOOSE_ONE, optional), и новые kind на каждого героя станут не нужны. Ошибки Dracula и Bigfoot/Philippa/Chupacabra исправляются одним механизмом. Это прямой путь
   cost: M. В ability-config.ts добавить kind 'card-effect' с полем effect: CardEffect, плюс поля pick: 'player'|'auto' и optional. В card-effect-executor.service.ts открыть applyOneEffect для контекста способности (playerId, sourceFighterId). Перевести turn-effect, turn-damage и pending-move в generic-hero- | risk: Средний: можно сломать поведение 26 уже настроенных героев. Его снимают существующие спеки, около 4,5 тыс. строк (ability-configs.e2e/integration, generic-hero-ability.handler.spec). Переписывать всё 
   VERIFY=weakened: Направление верное, но дублирование и выгода преувеличены. Добор у способностей и у карт идёт через один и тот же DeckManagementService.drawCards, а не реализован дважды. Движение у способностей уже создаёт общий MOVE PendingEffect, который разрешает тот же C2-резолвер. «May» с выбором цели уже есть: у Medusa это optional TARGET_FIGHTER с отказом. То есть общий протокол pendingEffects способности уже используют, выгода «начнут использовать общий протокол» уже получена. Реально продублированы два места: применение урона (applyTurnDamage против applyDamage карт) и сброс (у способностей детермини
   ev: backend/src/game-engine/abilities/ability-config.ts:353;backend/src/game-engine/abilities/generic-hero-ability.handler.ts:20-43;backend/src/game-engine/abilities/generic-hero-ability.handler.ts:775;backend/src/game-engine/models/card.model.ts:170-218;DuelEngine-transfer/test-targets/cpp2il-isil/Isil
- [R2] P1 | adopt | src=original | Точечные исправления правил способностей: Sherlock, Dracula, необязательные доборы, Achilles, Michelangelo
   why: Это расхождения с поведением оригинала и печатным текстом, они есть уже сейчас (список в ruleDiscrepancies D1-D5). Каждое закрывается небольшим изменением даже без R1: у Шерлока нет неотменяемости, Дракула не даёт выбрать цель и отказаться, доборы со словом «may» принудительные (на пустой колоде это истощение 2 каждому своему бойцу), «discard 2 random» у Ахиллеса детерминирован, а его реакция на гибель Патрокла работает только после боя.
   benefit: Правильная игра за Шерлока: Feint/Cancel — самая частая общая способность в DE, 16 карт. Также за Дракулу, Bigfoot, Philippa, Chupacabra, Achilles и Michelangelo. Основную пару Medusa/Arthur эти правки не затрагивают.
   cost: S на каждую. Шерлок: флаг неотменяемости для карт с баннером Holmes/Dr. Watson и проверка в updateCombatProgress (card-effect-executor.service.ts:246) и в пути R-16. Дракула: в pending-target-damage добавить область 'any-adjacent' и thenDraw. Bigfoot/Philippa/Chupacabra: optional через CHOOSE_ONE да | risk: Низкий: изменения локальные. Случайный сброс Ахиллеса честно не сделать, пока нет seeded RNG (другое измерение).
   VERIFY=weakened: Все пять расхождений подтверждены, но оценка риска для Achilles неверна. Случайный сброс уже есть и используется картами: DISCARD → discardRandomCards → DeckManagementService.discardRandomCard на Math.random. Способность получает тот же DeckManagementService через deps.deck, так что сброс «2 random» можно сделать сейчас; seeded RNG нужен только для воспроизводимости реплеев, а не для честной случайности. Поправка к фиксу Dracula: в оригинале цель берётся из FromPhraseGrammar.AllActiveFighters с фильтром IsAdjacentToThisFighter, то есть в число целей входят и свои бойцы. Область 'any-adjacent' 
   ev: backend/src/game-engine/abilities/ability-config.ts:544;backend/src/game-engine/abilities/ability-config.ts:702-712;backend/src/game-engine/abilities/ability-config.ts:824-850;backend/src/game-engine/services/game-action-executor.service.ts:2781;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/
- [R3] P2 | adapt | src=original | Открытая шина событий для способностей: событие с предикатами вместо отдельных точек вызова
   why: В оригинале 36 событий и подписка When(EventPredicate по Source/Target/Owner) для любой способности любого героя. Событие PostDefeat отправляет само действие урона, где бы оно ни произошло. У нас 7 триггеров, и каждый — отдельная точка вызова в executor, причём только для своего героя. onFighterDefeated вызывается только после боя, и поэтому Achilles не реагирует на гибель Патрокла от схемы или истощения. Для очередных героев нужны PreDamage (Yennenga, точное «takes 2 less damage» у Luke Cage), PostManeuver (Jekyll&Hyde, Sinbad, Houdini), PostScheme (Michelangelo) и отложенные эффекты «в начале следующего хода» (Leshen, Invisible Man).
   benefit: Новый триггер — это данные и одна строка emit в примитиве, а не правка executor. Межгеройные реакции перестают быть особыми случаями, как сейчас aura и on-move у Tomoe.
   cost: M. Добавить emitAbilityEvent(state, {name, sourceFighterId, targetFighterId, ownerId}), который обходит все зарегистрированные конфиги. Вызывать его из примитивов урона, перемещения, добора и розыгрыша схемы. Добавить в GameState.metadata записи «до тех пор, пока» вида {trigger, predicate, effect, e | risk: Средний: появится порядок срабатывания нескольких реакций (у оригинала есть RunEventBatch). Нужно правило: активный игрок первым, затем по очереди. Делать вместе с очередной партией героев, не заранее
   VERIFY=confirmed: Суть верна. Триггеры — отдельные точки вызова, а onFighterDefeated вызывается ровно в одном месте, после резолва боя. Сам оригинал рассылает PostDefeat из действия Defeat, которое вызывается из очистки Damage. Две поправки. Первая: фраза «точки вызова только для своего героя» неточна — triggerOnFighterMoved обходит всех зарегистрированных героев (Tomoe), и судья сам это упоминает. Вторая: события PostScheme в оригинале нет; «после схемы» у Michelangelo в языке оригинала соответствует PostPlayCard или PostAction с предикатом. Номера строк: :273 — это TurnEnd, а TurnStart вызывается на :365.
   ev: DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/events/Events.cs;DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/scripts/fighters/HitAndRunScriptV2.txt:392-433;backend/src/game-engine/abilities/ability-config.ts:45;backend/src/game-engine/servi
- [R4] P2 | adapt | src=original | Составной IR эффектов (TS-тип, JSON в БД), парсер как загрузчик, именованный TS-скрипт для уникальных карт
   why: Нераспознанный хвост — это вопрос композиции, а не новых глаголов. В 849 нераспознанных предложениях те же глаголы: value 169, discard 116, deal 113, draw 70, choose 63, move 53. 210 предложений начинаются с условия, 70 содержат «instead», 36 — «this turn» (мой разбор coverage.json). Оригинал выражает уникальные карты комбинацией примерно 15 глаголов, 4 квантификаторов, предикатов и Then/If. Но даже там 111 из 189 карт имеют отдельный скрипт. Значит, нужен не DSL на 100%, а IR плюс запасной выход.
   benefit: Карты, которые сейчас частично или вовсе не распознаются (591 из 880), можно описывать в админке как source:'manual' JSON без кода. Парсер выдаёт тот же IR. Узнаваемость текста перестаёт быть условием того, что эффект исполняется.
   cost: L, но по шагам. В CardEffect добавить select {from, where[], quantifier: chosen|all|first|random, min, max}, if / ifYouDo / instead и then[]. Добавить тип SCRIPT с id, который ссылается на зарегистрированную TS-функцию. Расширять executor по одному глаголу. Редактор IR в админке — отдельной задачей. | risk: Высокий риск раздувания задачи и «работы ради красоты». Включать только для героев, которых реально готовят к игре, и мерить каждой картой из coverage.json.
   VERIFY=weakened: Канал «описать карту JSON-ом в админке без кода» уже существует. Admin createCard и updateCard принимают effects JSON, а парсер не трогает эффекты с source:'manual'. Новое в R4 — только выразительность IR: select, квантификаторы, if/instead/then. Поэтому выгода «591 из 880 можно описать» — верхняя граница, и она достижима только после расширения executor под новые формы. Статистика нераспознанного подтверждена: 849 предложений, около 70 с «instead», около 200 начинаются с условия. Риск раздувания задачи оценён верно.
   ev: backend/src/game-engine/effects/effect-text-parser.ts:1-17;backend/src/game-engine/models/card.model.ts:170-218;docs/backend-api/db-divergence-2026-10-03.md:370;C:/Users/ren/AppData/Local/Temp/claude/C--Users-ren-WebstormProjects-unmached-unmached/2b6a7e70-a9a9-4f0e-bd48-9f26a5894d1b/scratchpad/effe
- [R5] P3 | skip | src=original | Не переносить C#-DSL «контент как код» и сериализуемые корутины оригинала
   why: В оригинале 558 классов Archetype и 285 ScriptBuilderFactory. Правка карты там требует новой сборки, а продолжение после паузы держится на параллельной иерархии Serialized* и на ContinueFromState. У нас контент лежит в БД и правится через админку, герои подключаются по слагу, а JS-генераторы не сериализуются. Нужную часть, продолжение как данные, мы уже имеем: CombatEffectContinuation.
   benefit: Не тратить время на переписывание и не терять редактирование контента из админки.
   cost: 0 | risk: Нет
   VERIFY=confirmed: Цифры подтверждены. Archetype и AbilityArchetype вместе дают 269+289=558 классов, файлов с [ScriptBuilderFactory] — 285. ContinueFromState существует в Canis ScriptBuilder. Наш CombatEffectContinuation — сериализуемая очередь данных.
   ev: DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Canis/canis/DSL/ScriptBuilders/ScriptBuilder.cs:250;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/data/Heroes/KingArthur/Cards/TheHolyGrail.cs;backend/src/game-engine/effects/card-effect-executor.service.ts:209-240;b
- [R6] P3 | keep-ours | src=both | Окна боя, порядок «защитник первым», Cancel, буст Артура и пауза боя — оставить наши
   why: Наш порядок совпадает с CombatScript оригинала: Immediate → During → урон → After, защитник первым, после урона проверка конца игры. Хуки after-attack героев идут после after-эффектов карт, как подписка на PostCombat (Robin Hood HitAndRunV2, поле 0xC0). Cancel сохраняет печатное значение и сжигает буст Артура — так и сказано в тексте fighter.kingarthur. В DuelEngine Immediate и After идут с атаки, это ошибка.
   benefit: Уже верно, менять не нужно.
   cost: 0 | risk: Нет
   VERIFY=confirmed: Подтверждено по ISIL. В CombatScript порядок такой: FireDefenderCombatEvent, затем FireAttackCombatEvent (Immediate), ещё раз защитник и атака (During), DealCombatDamage, ещё раз защитник и атака (After), CleanupCombat, AfterCombat. Robin Hood подписан на Events+0xC0, это PostCombat. У нас after-эффекты карт (:2695) идут раньше хуков героев (:2766-2771). Cancel берёт печатное значение и сбрасывает boostValue Артура — это совпадает с fighter.kingarthur.abilitydescription.
   ev: backend/src/game-engine/effects/card-effect-executor.service.ts:180;backend/src/game-engine/services/game-action-executor.service.ts:2572-2610;backend/src/game-engine/services/game-action-executor.service.ts:2689-2771;DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/script
- [R7] P3 | skip | src=duel-engine | Не брать каталог лямбд DuelEngine, PendingAbilityTask и закрытый enum окон
   why: Каталог — словарь примерно из 150 лямбд, по сути код под каждую карту. Ключи — имена классов DE, а они есть только для 14 героев. Незарегистрированные способности (12 штук) молча игнорируются. Новый вид отложенного эффекта требует правок в enum, двух switch (37 веток), StateClone, MatchReport, NetMessages и ИИ. Наши CardEffect, PendingEffect и ABILITY_CONFIGS масштабируются лучше.
   benefit: Не вносить в проект худшую модель.
   cost: 0 | risk: Нет
   VERIFY=confirmed: Подтверждено. В словаре AbilityCatalog ровно 150 записей вида ["…"] =. В Engine.cs 37 веток case PendingAbilityKind. Комментарий каталога прямо говорит, что незарегистрированное имя молча игнорируется. GameEvent — закрытый enum из 6 значений. Число «12 игнорируемых» взято из отчёта duel-run, сам я его не пересчитывал.
   ev: DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Core/Events.cs:16-37;DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Core/Events.cs:121;DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Core/GameState.cs:119;DuelEngine-transfer/duel-engine/UnityProject/Asse
- [R8] P2 | adapt | src=original | Эталонный тест парсера: классы способностей DE на 188 общих картах
   why: «Полностью распознано» сейчас значит только, что все предложения нашлись. Правильность это не проверяет. Общие способности DE служат готовой разметкой: CancelAbility → ON_REVEAL CANCEL_EFFECTS, Draw1AfterAbility → AFTER_COMBAT DRAW_CARD 1, Gain1ActionSchemeAbility → GAIN_ACTION 1, MoveFighterNAfter → MOVE N и т.д. По моему прогону наш парсер полностью распознаёт 65 из 78 таких карт; совпадают ли типы и числа, не проверено.
   benefit: Найдёт неверно разобранные карты у 14 базовых героев и защитит парсер от регрессий при росте PARSER_VERSION.
   cost: S. Спека, которая сверяет имя карты с ожидаемыми (timing, type, value). Ожидания записать своими словами и числами, без текстов и кода DE; исходные выгрузки DE в репозиторий не класть. | risk: Низкий. Юридически — только факты (имена и числа); при сомнениях держать сопоставление вне репозитория.
   VERIFY=confirmed: Подсчёт по cards-full.json воспроизводится: 73 карты только с общими способностями, 5 без способностей (итого 78), 111 с уникальными, 122 из 123 уникальных способностей встречаются один раз. CancelAbility — на 16 картах, это самая частая способность. Цифру «65 из 78 полностью» я не перепроверял: она получена по скрипту судьи. Оговорку о том, что нужно хранить только факты, разделяю.
   ev: DuelEngine-transfer/test-targets/unmatched-data/cards-full.json;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/data/Heroes/Shared/Abilities;backend/src/game-engine/effects/effect-text-parser.spec.ts;C:/Users/ren/AppData/Local/Temp/claude/C--Users-ren-WebstormProjects-unm
- [R9] P2 | adapt | src=original | Модификаторы значений: удалить мёртвый ValueModifierService, временные моды хранить в GameState, когда понадобятся
   why: ValueModifierService внедрён в два сервиса, но не вызывается. Состояние он держит в Map процесса по fighterId: если его начать использовать, моды не переживут рестарт, разойдутся между инстансами и могут протечь между партиями. В оригинале моды лежат в состоянии (MutableAttribute: BaseValue и стек Mod с ModID и SortOrder). Наши вычисляемые пассивки из конфига — правильная форма для постоянных способностей, их оставить.
   benefit: Убирается ловушка. Появляется понятное место для эффектов «до конца хода»: в нераспознанных предложениях 36 таких формулировок.
   cost: S на удаление. M позже: metadata.valueMods[{id, stat, op, value, source, expires}] с порядком set → add, снимаемые там же, где fighter.effects с duration 'turn' (game-action-executor.service.ts:317). | risk: Низкий
   VERIFY=weakened: Часть про удаление подтверждена. ValueModifierService внедрён в CardEffectExecutor (:120) и GameActionExecutor (:163), но вызовов нет; он держит Map в памяти процесса, а applyCardEffects уже удалили как мёртвый стаб. Предложенная схема хранения модов при этом лишняя: в состоянии уже есть контейнер FighterEffect {type, value, duration, expiresAt, source}, и записи с duration 'turn' снимаются при передаче хода. Временные моды «до конца хода» естественно класть туда, а не заводить новый metadata.valueMods. Порядок set → add можно задать в месте, где они читаются.
   ev: backend/src/game-engine/engine/value-modifier.service.ts:29-35;backend/src/game-engine/services/game-action-executor.service.ts:163;backend/src/game-engine/effects/card-effect-executor.service.ts:120;backend/src/game-engine/models/fighter.model.ts:31-37;DuelEngine-transfer/test-targets/cpp2il-cs/Dif
- [R10] P3 | adapt | src=original | Предупреждения у необязательных эффектов: истощение при доборе, «схема ничего не сделает»
   why: В оригинале у кнопки «Draw» в выборе стоит DuelQueries.DrawWarning (предупреждение об истощении), а у карты есть ключ SchemeWarningKey (например, NoAdjacentEnemyFightersToHero). У нас есть skippedEffects и снятие выбора без целей, но предупреждения до розыгрыша нет.
   benefit: Меньше ошибок игрока на пустой колоде и при бесполезной схеме. Окупается только после R1/R2, когда «may»-доборы станут выбором.
   cost: S. Флаг warning в pending и расчёт «схема без целей» в валидаторе, плюс текст в UE. | risk: Низкий
   VERIFY=weakened: Утверждение «предупреждения до розыгрыша нет» неточно. В UE-клиенте уже есть предупреждение об истощении перед манёвром на пустой колоде: ms.begin.exhaustion с кнопками «Begin anyway» и «Cancel». Паттерн готов и переносится на «may»-доборы. Действительно нет предупреждения для доборов из способностей и карт и для «схема ничего не сделает»: у SchemeWarningKey в DE 20 карт с ключами вроде NoAdjacentEnemyFightersToHero, у нас аналога нет. Ещё одно: авто-резолв по таймауту для обязательного CHOOSE_ONE выбирает опцию 0. Если делать «may draw» через CHOOSE_ONE, отказ надо ставить первым или делать p
   ev: DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/scripts/fighters/LonerByNatureScript.txt:716;DuelEngine-transfer/test-targets/unmatched-data/cards-full.json;backend/src/game-engine/effects/pending-targets.ts
- [R11] P3 | adapt | src=none | Свести три интерфейса обработчиков героев и перевести ручных героев на конфиг
   why: Параллельно живут три интерфейса: HeroAbilityHandler, ExtendedHeroAbilityHandler и IHeroAbilityHandler. Ручные обработчики портятся: у Ms. Marvel зашита доска 6×6, executeBlindBoost (Daredevil) и executeTurnStartMove (Ms. Marvel) не подключены к мутациям. В оригинале у пассивок бойцов тот же механизм, что у карт (scripts/fighters на той же грамматике).
   benefit: Один путь вызова способностей; удаление кода, который не работает на картах-графах.
   cost: M. Делать после R1: Daredevil и Ms. Marvel выразить через конфиг (условие на размер руки + BOOST из SELF_DECK_TOP; attackRange + pending-move на старте хода), legacy-интерфейс удалить. | risk: Низкий-средний: у этих героев есть свои спеки.
   VERIFY=confirmed: Подтверждено. Интерфейсы HeroAbilityHandler (:70), ExtendedHeroAbilityHandler (:155) и IHeroAbilityHandler (:55) живут параллельно. У Ms. Marvel BOARD_SIZE = 6 зашит в isValidPosition. executeBlindBoost и executeTurnStartMove нигде вне своих файлов не вызываются. При этом BLIND BOOST у карт Daredevil парсер уже выдаёт как BOOST SELF_DECK_TOP blind, поэтому мёртвым оказывается только путь через обработчик.
   ev: backend/src/game-engine/abilities/hero-ability-registry.ts:70;backend/src/game-engine/abilities/hero-ability-registry.ts:155;backend/src/game-engine/abilities/hero-ability.interface.ts:55;backend/src/game-engine/abilities/heroes/ms-marvel.handler.ts:240-242;docs/backend-api/08-heroes-abilities.md
- [R12] P3 | adapt | src=original | Пауза эффектов схемы после созданного выбора (семантика Then)
   why: В оригинале Then ждёт ответа на выбор. У нас executeOnPlayEffects после MOVE/PLACE-выбора сразу исполняет следующие эффекты, а очередь с продолжением есть только у боя. Сейчас среди распознанных схем это затрагивает только эффекты, не зависящие от позиции (Answer the Bell, One With The Land: MOVE, затем HEAL), поэтому риск сегодня низкий. Но с ростом покрытия (R4) появятся «move, then deal damage adjacent».
   benefit: Правильный порядок для будущих составных схем; та же модель продолжения, что у боя.
   cost: S-M. Обобщить CombatEffectContinuation на стадию ON_PLAY и вызывать resume из drainAfterChoice. | risk: Низкий
   VERIFY=confirmed: Подтверждено: executeOnPlayEffects исполняет эффекты циклом без паузы, очередь с продолжением есть только у боя. К примерам судьи стоит добавить Winged Frenzy (Medusa, основная пара): MOVE, затем RETURN_DEFEATED, два pending в одной схеме. Сегодня это безопасно: кандидаты для возврата не зависят от движения, а клетки проверяются, когда pending становится головой очереди. Ещё деталь: контекст fighterId у схемы — первый живой боец игрока, а не боец, разыгравший карту. Для будущих эффектов относительно «этого бойца» это отдельный риск (confidence medium).
   ev: backend/src/game-engine/effects/card-effect-executor.service.ts:266-293;backend/src/game-engine/effects/card-effect-executor.service.ts:162-168;backend/src/game-engine/services/game-action-executor.service.ts:230-251;C:/Users/ren/AppData/Local/Temp/claude/C--Users-ren-WebstormProjects-unmached-unmac
- RULE [D1] medium | Sherlock Holmes: эффекты карт HOLMES и DR. WATSON нельзя отменить (карты с баннером ANY отменить можно)
   orig: Атрибут карты Uncancellable (DuelAttributes.cs:40), пассивка UncancellableScript и общая способность UncancellableAbility. Текст fighter.sherlockholmes.abilitydescription.
   ours: Не реализовано: grep 'uncancel' по backend/src пуст. CANCEL_EFFECTS (Feint и др.) гасит и карты Холмса/Ватсона. Sherlock в ростере есть (scraped-data/api/heroes/sherlock-holmes.json).
   duel: Флаг игрока UncancelableEffects защищает ВСЕ карты игрока, включая ANY. Это шире правила (Core/Events.cs:1470-1493).
   VERIFY=confirmed: Подтверждено. grep 'uncancel' по backend/src пуст; CANCEL_EFFECTS ставит флаг без проверки баннера. В оригинале атрибут Uncancellable стоит на строке 40 файла DuelAttributes.cs (смещение 0xF8). Флаг DuelEngine проверяет только игрока, без баннера карты, так что защищены и карты ANY. Для фикса у нас есть Card.bannerName.
   ev: DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/data/DuelAttributes.cs:40;DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/scripts/fighters/UncancellableScript.txt;DuelEngine-transfer/test-targets/unmatched-data/localization.txt:3197;backend/src
- RULE [D2] medium | Dracula: в начале хода МОЖНО нанести 1 урон бойцу, смежному с Дракулой; если урон нанесён — добрать карту
   orig: Damage по цели, выбранной игроком (Selected.From) среди бойцов IsAdjacentToThisFighter, затем условный Draw. Выбор и отказ есть.
   ours: turn-damage с targetScope 'enemy-adjacent': автоматически бьёт ПЕРВОГО смежного врага в порядке state.fighters, без выбора цели и без отказа (ability-config.ts:702-712). Приближение задокументировано в 08-heroes-abilities.md §3 п.1.
   duel: Пассивки Дракулы нет: из пассивок героев есть только Rage/Fog/uncancelable в Content/Heroes/real/*.json.
   VERIFY=confirmed: Расхождение реально, но шире описанного. У нас 'enemy-adjacent' автоматически бьёт первого врага и при этом не может выбрать своего бойца. В оригинале цель берётся из AllActiveFighters, смежных с Дракулой, то есть свои бойцы тоже допустимы — так и в печатном тексте: «a fighter adjacent». Отказ в ISIL Bloodthirsty прямо не виден: нет CustomChoice/Noop, как у Bigfoot. «Можно отказаться» держится на печатном «you may» и на семантике Selected. Добор условный: Then Draw при Exists(...).
   ev: DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/scripts/fighters/BloodthirstyScript.txt:705-728;DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/scripts/fighters/BloodthirstyScript.txt:816;DuelEngine-transfer/test-targets/unmatched-data/localiza
- RULE [D3] medium | Необязательный добор способностью («you may draw»): Bigfoot, а по печатному тексту также Philippa и Chupacabra
   orig: Bigfoot LonerByNature: выбор между кнопкой «Draw» с предупреждением DrawWarning об истощении и Noop.
   ours: turn-effect/after-attack draw принудительный (ability-config.ts:515-568). На пустой колоде drawCards наносит каждому своему бойцу истощение 2 без возможности отказаться (generic-hero-ability.handler.ts:731-745).
   duel: Пассивки Bigfoot нет. Philippa и Chupacabra отсутствуют.
   VERIFY=confirmed: Подтверждено. LonerByNature: CustomChoice.Choose, затем Button с DuelQueries.DrawWarning и Draw, затем Button с Noop. Печатный «you may» есть у Bigfoot, Philippa («Two Steps Ahead: you may draw until you have a hand of 4») и Chupacabra («you may draw a card»). У нас draw и drawToHandSize принудительные; на пустой колоде drawCards наносит 2 урона каждому своему бойцу за каждую недостающую карту.
   ev: DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/scripts/fighters/LonerByNatureScript.txt:673-775;DuelEngine-transfer/test-targets/unmatched-data/localization.txt:3193;backend/src/game-engine/abilities/ability-config.ts:515-568;backend/src/game-engine/abilities/generic-her
- RULE [D4] low | Achilles: «When Patroclus is defeated, discard 2 random cards. While Patroclus is defeated… If Achilles wins combat, draw 1 card»
   orig: В DE кода Ахиллеса нет (DLC), есть только текст. По тексту сброс случайный, реакция идёт на любую гибель Патрокла (в ядре — событие PostDefeat), а добор — при ЛЮБОЙ победе в бою, в том числе в защите.
   ours: Сбрасываются первые 2 карты руки, детерминированно. onFighterDefeated вызывается только после резолва боя (game-action-executor.service.ts:2781), так что гибель от схемы, урона на старте хода или истощения сброс не вызывает. Добор только при after-attack (won-combat-and-all-sidekicks-defeated).
   duel: Ахиллеса нет.
   VERIFY=confirmed: Подтверждено. В оригинале у Achilles есть только архетипы Achilles.cs и Patroclus.cs, без способностей. У нас сброс — первые N карт, onFighterDefeated вызывается только из резолва боя, добор только через after-attack. Инфраструктура after-defense есть (doc §3 п.6), но условие won-combat вычисляется только для after-attack, так что для добора в защите нужна маленькая доработка условия. Для «random» поправка: случайный сброс уже есть (см. R2).
   ev: DuelEngine-transfer/test-targets/unmatched-data/localization.txt:3205;backend/src/game-engine/abilities/ability-config.ts:824-850;backend/src/game-engine/services/game-action-executor.service.ts:2775-2782;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/events/Events.cs
- RULE [D5] medium | Michelangelo: «After you attack or scheme, draw 1 card. Your starting and maximum hand size is 3»
   orig: В DE героя нет. Проверено только по печатному тексту scraped-data.
   ours: Добор только после атаки, после схемы — нет. Стартовая и максимальная рука 3 не смоделированы: действуют общие 5 и 7 (ability-config.ts:584-596). Пропуск лимита руки задокументирован, пропуск «or scheme» — нет.
   duel: Героя нет.
   VERIFY=confirmed: Подтверждено. В печатном тексте: «After you attack or scheme, draw 1 card. Your starting and maximum hand size is 3». В конфиге только after-attack. В документации отмечен лимит руки (§3 п.5), а пропуск «or scheme» не отмечен.
   ev: scraped-data/api/heroes/michelangelo.json;backend/src/game-engine/abilities/ability-config.ts:584-596;docs/backend-api/08-heroes-abilities.md
- RULE [D6] high | Способности героев базового набора DE: Sinbad (Voyage +1 к движению манёвра), Beowulf (Rage), Invisible Man (туман: +1 к защите, проход между клетками с туманом), Jekyll & Hyde (превращение; Hyde получает 1 урон после манёвра), Little Red (корзинка и символы)
   orig: Реализованы скриптами SevenVoyagesScript/SevenVoyagesBoostScript, Raging1/2Script, InTheMist*Script, StartTurnChooseBecomeScript; корзинка — через DuelQueries.HasBasketItem (14 вызовов). Тексты — localization.txt:3191-3202.
   ours: Способностей нет: grep beowulf/sinbad/invisible/jekyll/hyde/basket по backend/src пуст; boardState.fog объявлен, но не используется. Эти герои в ростере есть (scraped-data/api/heroes/*.json) и играют без своей механики, а эффекты карт, завязанные на корзинку или туман, не распознаются.
   duel: Частично: Rage, Fog, IsBig и HydeForm в виде флагов, причём IsBig в бою не применяется. Корзинки и Voyage нет (отчёт duel-code F8).
   VERIFY=confirmed: Подтверждено. В backend/src нет ни одного упоминания beowulf, sinbad, invisible, jekyll, sherlock или basket — совпадение «hyde» нашлось только в URL. boardState.fog объявлен и инициализируется пустым объектом. В оригинале у этих шести героев 13–25 файлов способностей на каждого. Деталь: текст Little Red в DE («символ верхней карты сброса») отличается от нашего scraped-текста, значит при реализации надо выбрать редакцию.
   ev: DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/scripts/fighters;DuelEngine-transfer/test-targets/unmatched-data/localization.txt:3191-3202;backend/src/game-engine/abilities/ability-config.ts:458;backend/src/game-engine/models/board.model.ts:17;scraped-data/api/heroes/sin
- RULE [D7] low | Порядок эффектов внутри окон Immediate и After: защитник первым
   orig: В CombatScript в каждом окне сначала шаг защитника, потом атакующего (шаги 20/30, 40/50, 70/80).
   ours: Совпадает: createCombatQueue проходит по ['defender', 'attacker'] на каждой стадии.
   duel: В окнах Immediate и AfterCombat первой идёт карта атаки, потом защиты (Core/Events.cs:1848-1918). Это ошибка DuelEngine, переносить её нельзя.
   VERIFY=confirmed: Подтверждено, причём у DuelEngine ошибка шире порядка. В окне ImmediateCombat обе карты исполняются без подавления: Cancel только ставит флаги на следующие окна, так что Immediate-эффекты отменённой карты всё равно срабатывают. В AfterCombat порядок атака → защита. У нас createCombatQueue идёт по ['defender','attacker'] на каждой стадии, а пропуск отменённой карты действует уже внутри ON_REVEAL.
   ev: DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/scripts/phases/CombatScript.txt:1603;backend/src/game-engine/effects/card-effect-executor.service.ts:180-200;DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Core/Events.cs:1848-1918
MISSED: Цель Dracula в оригинале — любой активный боец, смежный с Дракулой, свои тоже (FromPhraseGrammar.AllActiveFighters, FromPhraseGrammar.cs:569, используется в BloodthirstyScript.txt:127-143). Наша 'enemy-adjacent' своих отбрасывает (generic-hero-ability.handler.ts:786). || Случайный сброс уже реализован и используется картами: DeckManagementService.discardRandomCard (deck-management.service.ts:192) и discardRandomCards (card-effect-executor.service.ts:1347-1359). Детерминированный сброс у Achilles — не вынужденное ограничение, а дубль примитива в generic-hero-ability.handler.ts:446-475. || Способности уже пользуются общим протоколом pendingEffects: MOVE (handler :822-886) и optional TARGET_FIGHTER с отказом (Medusa, ability-config.ts:727-744). Пункт 1 §3 в docs/backend-api/08-heroes-abilities.md:244 устарел: Medusa там всё ещё числится «без you may». || Не учтено расхождение у Luke Cage. Печатное «takes 2 less combat damage from attacks» смоделировано как +2 к защите (ability-config.ts:461-471), а это меняет исход боя и срабатывание «if you won/lost» у обеих сторон. Это не только вопрос события PreDamage, а отдельное расхождение правил. || Не учтён Leonardo: «move any fighter up to 1 space», а у нас двигаются только свои бойцы (docs/backend-api/08-heroes-abilities.md:246, §3 п.3). || В DuelEngine Immediate-эффекты отменённой карты не подавляются вообще (Events.cs:1841-1846). Это вторая ошибка окон помимо порядка, и при сравнении её тоже нельзя переносить. || UE-клиент уже умеет предупреждать об истощении перед действием: ms.begin.exhaustion, «Begin anyway»/«Cancel» в S08WhyText.cpp:71-74. Это готовый образец для R10. || Сервер при таймауте для обязательного CHOOSE_ONE выбирает опцию 0 (game-action-executor.service.ts:882,908-911). Если «may draw» сделать через CHOOSE_ONE, отказ нужно ставить первым или делать pending optional с отказом, иначе таймаут на пустой колоде принудит к истощению. || У схем контекст fighterId — первый живой боец игрока, а не боец, разыгравший карту (card-effect-executor.service.ts:280). Для будущих составных схем «относительно этого бойца» это риск; насколько он реален сегодня, не проверял (confidence medium). || В оригинале нет события PostScheme. «После схемы» у Michelangelo выражается через PostPlayCard или PostAction с предикатом (DiffableCs/duel-canis/duel/canis/events/Events.cs:19-20). || Неточности в ourState. В EffectType 26 значений, а не 24. В EffectTiming 8 значений: ещё BEFORE_COMBAT, ON_DISCARD, TURN_START, TURN_END (card.model.ts:224-234). Строка game-action-executor.service.ts:273 — это вызов triggerHeroTurnEnd, а triggerHeroTurnStart вызывается на :365. || CardEffect уже имеет поле optional (card.model.ts:64-65), но DRAW_CARD его игнорирует (card-effect-executor.service.ts:569-571). Парсер «you may draw» не распознаёт: регулярка в effect-text-parser.ts:476 ловит только «draw N cards». Поэтому «may»-добор отсутствует и у карт, не только у способностей.

######## DIM state-determinism — Состояние, действия, детерминизм, реплеи
SUMMARY: Вердикт по измерению: свою модель сохраняем, переносим четыре идеи и ни одной строки кода. Оригинал нашей модели не превосходит.

Неизменяемый GameState, движок без I/O и хранение в Postgres надёжнее обоих образцов. В Postgres есть optimistic seq-1 и условный updateMany в одной транзакции, а Redis-кеш сверяется с version. У оригинала Canis изменяемое дерево сущностей, снимок на каждой паузе и состояние RNG не сохраняется. У DuelEngine хранения нет, StateClone ручной, а «партия = seed + ActionLog» на запуске не воспроизвелась (0/120).

Брать стоит следующее:
- **(P1) Seeded RNG.** Состояние генератора хранить в GameState и сериализовать. Нужно два потока (игра и ИИ, как Random и SelectionRandom у оригинала) и подстановка значений для тестов. Сейчас 5 игровых Math.random. Обязательно убрать поле из filterPrivateData: metadata копируется чёрным списком, и иначе seed уйдёт клиенту.
- **(P1) Воспроизведение партии по входам** (урок DuelEngine: по SelectionResponse 120/120). Наш журнал GameAction уже пишет входы человека, ИИ и таймаутов. Не хватает трёх вещей: запись в транзакции saveState, а не через BullMQ после коммита; поле ActionContext.now, потому что Date.now() используется в правилах; снимок старта в неиспользуемой GameStateSnapshot.
- **(P1) Self-play фазз с инвариантами на Marmoreal и Sarpedon.** Инварианты: карты не теряются, нет команд после GAME_OVER, у кого-то всегда есть ход, round-trip serialize, нет утечек скрытого, глубокий freeze. Такой фазз нашёл баг Б1 у DuelEngine. Все части у нас уже есть (s03Engine, real-board, AiAction и dispatchAiAction).
- **(P2) Монотонный счётчик выбора**, как Counter у оригинала. Наши id pending собираются из id карты и длины очереди, поэтому могут повториться, а восстановление в UE опирается на исчезновение id.
- **(P2) Канонический хеш состояния** после каждой команды. В расчёт не включать поля часов.

Не брать: сериализуемый корутинный стек с двойниками Serialized*, журнал внутренних действий как запись партии, ручной StateClone, отмену и подготовку хода, проигрыватель архивных реплеев. Расхождений правил в этом измерении нет. P0-багов не найдено. Два места надо закрыть фаззом: молча проглоченная ошибка возобновления боя (executor :243) и класс багов «поле живёт только в Redis-кеше».
OURS: Ключевые утверждения я перепроверил сам по исходникам.

1) МОДЕЛЬ СОСТОЯНИЯ. Состояние — один неизменяемый (readonly) документ GameState (backend/src/game-engine/models/game-state.model.ts:40-65) с большим metadata (:323-378). Все поля metadata сейчас типизированы. Паузы хранятся как данные: pendingEffects из 8 типов (:385-456), pendingManeuver, pendingHandDiscard, pendingTurnEnd, а также combatResolutionProgress/combatEffectContinuation — это сериализуемое продолжение боя.

В движке нет I/O: grep PrismaService/RedisService по backend/src/game-engine пуст. Поэтому «клон» для симуляции — просто ссылка на неизменяемый объект.

2) ТРИ ПРЕДСТАВЛЕНИЯ СОСТОЯНИЯ:
- GameState в памяти;
- SerializedGameState в Postgres. Это белый список коротких ключей (games/game-state.service.ts:49-160, serialize :560). Комментарии на :63-64 говорят, что поля раньше «ТЕРЯЛИСЬ при save/load»;
- «сырой» GameState в Redis (cacheState :503-506, TTL 600 с :172), с оживлением дат в getCachedState (:517-549).

Я сверил поля Fighter, BoardState и GameStateMetadata с serialize: сейчас все замаплены. Но каждое новое поле нужно руками добавить в serialize. Если забыть, поле живёт только в Redis-кеше до TTL или рестарта.

3) ХРАНЕНИЕ И КОНКУРЕНТНОСТЬ сделаны надёжно. Есть Redis-лок game:${id} (games/resolvers/game-actions.resolver.ts:270). В транзакции saveState сначала условный updateMany по status IN_PROGRESS, который берёт строковую блокировку Game, затем проверка existing.sequenceNumber === new-1 (game-stat
- [DET-1] P1 | adapt | src=both | Seeded RNG в состоянии игры: сериализуемое состояние генератора, два потока, подстановка значений для тестов
   why: Без seed партию нельзя воспроизвести, и фазз-падение не повторить. Обе реализации-образца не доведены до конца: оригинал берёт seed из MatchInitData, но не сохраняет состояние RNG в SaveData, а у DuelEngine System.Random нельзя сериализовать. Нам стоит сделать лучше обоих. Нужен генератор с явным маленьким состоянием (например, sfc32 или xoshiro128 — четыре uint32), это состояние хранится в GameState и проходит через serialize/deserialize. У оригинала берём ещё две идеи: (а) отдельный поток для ИИ и случайных ответов по умолчанию (Random и SelectionRandom), чтобы шум ИИ не менял раздачу; (б) стек подстановки значений вместо глобальной подмены Math.random в тестах (s06-full-games.spec.ts:195-
   benefit: Партию можно воспроизвести по (стартовое состояние, команды). Падения фазза и бои с багами из плейтестов повторяются. Тесты больше не патчат глобальный Math.random. Это основа для DET-2 и DET-3.
   cost: S–M, 1–1,5 дня.
1) Новый модуль rng: next, int и shuffle возвращают значение и новое состояние.
2) Заменить ровно 5 игровых вызовов: deck-management.service.ts:33, :192; card-effect-executor.service.ts:1383, :1446; game-initialization.service.ts:51. Тасовка и случайный сброс должны возвращать обновл | risk: 1) Утечка: если seed или состояние RNG попадёт в проекцию, модифицированный клиент предскажет колоду. Нужен тест на filterPrivateData. 2) Изменятся раздачи в спеках, которые зависят от LCG-патча; тран
   VERIFY=weakened: Ядро рекомендации верно: seed нет, игровых Math.random ровно 5, клиент получает почти сырой GameState, поэтому seed в metadata уйдёт клиенту. Неверна часть (а) про «отдельный поток для ИИ». (1) У нашего ИИ и у системных фолбэков случайности нет вообще: в ai-decision.service.ts Math.random нет, buildSystemPendingFallback по контракту детерминирован. Второму потоку сейчас некого обслуживать. (2) У оригинала два генератора НЕ независимы по seed. Configure при mid.randomSeed != 0 создаёт оба из одного и того же значения, а при 0 — оба без seed, через конструктор без параметров. Для чего нужен Sele
   ev: backend/src/game-engine/services/deck-management.service.ts:33;backend/src/game-engine/services/deck-management.service.ts:192;backend/src/game-engine/effects/card-effect-executor.service.ts:1383;backend/src/game-engine/effects/card-effect-executor.service.ts:1446;backend/src/games/services/game-ini
- [DET-2] P1 | adapt | src=duel-engine | Воспроизведение партии по (стартовый снимок, журнал команд): транзакционный журнал, инъекция часов, снимок старта
   why: Запуск DuelEngine показал, что воспроизводит партию журнал ВХОДОВ (SelectionResponse, 120/120), а журнал внутренних действий не воспроизводит (0/120). Наш GameAction уже пишет входы: человек — resolver :223, ИИ — ai-turn :309 (AiAction), таймауты — combat-timeout :601, :643. Модель журнала верная, не хватает трёх вещей.
(а) Журнал пишется после коммита, best-effort, через BullMQ (game-actions.resolver.ts:106-130, game-action.service.ts:18-48) и может терять записи. Строку команды нужно вставлять в той же транзакции saveState (game-state.service.ts:189-247).
(б) Правила читают Date.now() (executor :2243, :2529). Нужно поле now в ActionContext (:117-124), записанное в команду.
(в) Стартовое со
   benefit: Любую живую партию (плейтест, VS_AI, Game Tester) можно воспроизвести локально до шага с багом. Реальные партии на Marmoreal/Sarpedon становятся регрессионными фикстурами. Ничего не переписывается, используются существующие таблицы.
   cost: M, 2–3 дня.
1) В saveState добавить необязательный параметр команды и insert GameAction в транзакции; BullMQ-путь оставить для аудита или убрать.
2) Поле ActionContext.now, заменить два Date.now() в правилах.
3) Снимок старта в GameStateSnapshot плюс версия движка (commit или PARSER_VERSION).
4) Оди | risk: 1) После правок движка или ABILITY_CONFIGS старые журналы расходятся; это решается версией в снимке и сверкой хешей (DET-5). 2) Транзакция saveState станет длиннее на один insert, это допустимо. 3) В 
   VERIFY=weakened: Подтверждено: журнал пишется после коммита через BullMQ, best-effort. Правила читают Date.now(): :2243 и :2530, а не :2529. Стартовый снимок нигде не хранится. Неточность в обосновании: журнал «системных таймаутов» — это аудит, а не входы на каждый шаг. processAutoResolve сохраняет состояние на каждом раунде executeResolveCombat (+1 seq за раунд), но recordAudit пишет один раз в конце, с финальным seq. Если упёрлись в потолок раундов, аудита нет вовсе. Авто-выборы пишутся по шагам, но без конкретных параметров фолбэка («без id карт»). В журнале есть дыры по seq, поэтому проигрыватель должен во
   ev: backend/src/games/resolvers/game-actions.resolver.ts:106-130;backend/src/games/resolvers/game-actions.resolver.ts:223;backend/src/games/services/game-action.service.ts:18-48;backend/src/games/services/ai-turn.service.ts:29;backend/src/games/services/ai-turn.service.ts:309;backend/src/games/services/
- [DET-3] P1 | adapt | src=duel-engine | Self-play фазз со случайными легальными ходами и инвариантами на реальных картах
   why: Фазз-прогон по DuelEngine за секунды нашёл баг Б1 (GameOver затирался очередью отложенных эффектов), который 25 их тестов пропустили. У нас уже есть все части: s03Engine собирает executor без сервисов (test/fixtures/s03-engine.fixture.ts), real-board.ts загружает Marmoreal, есть AiAction и dispatchAiAction, а s06 гоняет полные матчи (пока на выведенной Cobble City). Не хватает случайной политики по перечню легальных команд и набора инвариантов на каждом шаге:
- сохранение и владение карт (колода + рука + сброс);
- HP в границах;
- никаких команд после GAME_OVER, seq ровно +1;
- живость: если нет GAME_OVER, у кого-то есть легальная команда. Это ловит зависания вроде молча проглоченного возобн
   benefit: Дешёвый страховочный гейт для каждого нового героя и эффекта. Упавший seed воспроизводится (вместе с DET-1). Сразу проверяется, нет ли у нас аналога Б1.
   cost: M, 2–3 дня.
1) Перечислитель легальных команд для головы очереди, манёвра, атаки, схемы и защиты; переиспользовать ai-decision и validator.
2) Spec-раннер на Marmoreal и Sarpedon, N пар героев × K сидов, с лимитом шагов.
3) Инварианты из обоснования.
В CI держать небольшой N, а ночной прогон делать  | risk: 1) Без DET-1 падения невоспроизводимы, поэтому делать после него. 2) Перечислитель может разойтись с validator; это и есть полезная проверка: каждая команда из перечня должна приниматься executor. 3) 
   VERIFY=confirmed: Рекомендация обоснована: фазз со случайными ходами у DuelEngine действительно нашёл Б1 (DeadHeroNoGameOver и WinnerPhaseMismatch в 6 из 960 матчей). Фразу «все части у нас уже есть» стоит смягчить. Перечислителя легальных команд нет: ai-decision возвращает одно действие. В real-board.ts есть только marmorealBoardRow, хелпер для Sarpedon нужно добавить. Политика ИИ никогда не играет scheme, setStance и toggleDoor, поэтому фазз через AiAction эти ветки не покроет. Round-trip serialize и проекция приватного уже покрыты точечными спеками, их можно переиспользовать как основу инвариантов. Но это пр
   ev: backend/src/test/fixtures/s03-engine.fixture.ts;backend/src/test/fixtures/real-board.ts;backend/src/games/services/ai-turn.service.ts:29;backend/src/games/services/s06-full-games.spec.ts:1-9;backend/src/games/game-state.service.ts:63-64;backend/src/games/game-state.service.ts:503-506;backend/src/gam
- [DET-4] P2 | adapt | src=original | Монотонный счётчик выбора (choice counter) и защита от устаревших ответов на всех мутациях
   why: В оригинале у каждого вопроса есть монотонный Counter (SelectionMessage.cs:9-10). Сервер отбрасывает ответ со старым счётчиком (Match.HasPendingResponse, Match.cs:2262; строки «attempted stale selection», metadata_strings.txt:93, :195). У нас id pending вида `${effect.id}-p${длина очереди}`, где effect.id берётся от определения карты (effect-text-parser.ts:791). Поэтому тот же id может появиться снова: та же карта в другом ходу или тот же эффект при той же длине очереди. Восстановление клиента UE считает выбор закрытым по отсутствию id (S08FlowController.cpp:1732-1775), а запоздавший повтор может закрыть новый выбор с тем же id. expectedSequenceNumber есть только у beginManeuver (gameplay.dt
   benefit: Id выборов уникальны за всю партию. Повтор команды идемпотентен на сервере, а не только из-за блокировки на клиенте. Журнал для DET-2 становится однозначным.
   cost: S, полдня – день.
1) metadata.choiceSeq плюс суффикс #n в id всех pending (около 12 мест в card-effect-executor и generic-hero-ability.handler.ts:871, :923); поле добавить в serialize.
2) Необязательный expectedSequenceNumber в остальных DTO с отказом при несовпадении.
3) Тесты: UE на восстановление | risk: Если какие-то тесты или клиент разбирают id как строку с форматом, их придётся поправить. Реальная коллизия в игре не воспроизведена: уверенность в вреде средняя, в возможности — высокая.
   VERIFY=weakened: Подтверждено: id pending строятся из effect.id, а тот — из id ОПРЕДЕЛЕНИЯ карты (card.id из БД, общий для всех копий). expectedSequenceNumber есть только у beginManeuver. Механизм вреда описан неверно. UE-клиент после потерянного ответа ничего не переотправляет: он читает свежее состояние, и выбор считается закрытым только при seq > baseline и отсутствии id. Сценарий «запоздавший повтор закрывает новый выбор» на практике маловероятен. Реальный и проверяемый по коду вред обратный. Многошаговые pending сохраняют прежний id: CHOOSE_SPACE на stage 2 копирует pending вместе с id, то же при chooseCo
   ev: backend/src/game-engine/effects/card-effect-executor.service.ts:531;backend/src/game-engine/effects/card-effect-executor.service.ts:678;backend/src/game-engine/effects/effect-text-parser.ts:791;backend/src/games/dto/gameplay.dto.ts:98-108;backend/src/game-engine/services/game-action-executor.service
- [DET-5] P2 | adapt | src=none | Канонический хеш состояния после каждой команды
   why: Хешей нет ни у оригинала (найден только checksum локализации), ни у DuelEngine (его тесты сравнивают счётчики), ни у нас (grep createHash/checksum пуст). Для DET-2 и DET-3 нужен способ сказать, что воспроизведение разошлось на шаге N. Хеш считается по стабильной сериализации serialize(state) без полей часов: lastActionAt, performedAt, combatInfo.startedAt/timeoutAt. Он кладётся в payload строки GameAction, без миграции схемы.
   benefit: Точная локализация расхождения при воспроизведении после правок движка. Проверка детерминизма в фаззе. Задел на будущий протокол (сверка клиента), если понадобится.
   cost: S, около 0,5 дня: функция stableHash, запись в payload команды, использование в проигрывателе. | risk: Цена хеша на каждую мутацию: стоимость stringify всего состояния, включая граф доски. Если окажется заметной, хешировать без boardState.cells (он статичен). Мерить только по факту, без оптимизаций све
   VERIFY=confirmed: Подтверждено: хешей состояния нет. В игровом коде games и game-engine нет createHash; единственное вхождение — в спеке контракта доски. В Canis и Networking оригинала нет desync, checksum или stateHash. Уточнение: если класть хеш в payload GameAction, пока журнал идёт через BullMQ после коммита, хеш теряется вместе со строкой журнала. Поэтому DET-5 имеет смысл только после DET-2(а). Помимо названных полей часов, из хеша надо исключить все performedAt и lastActionAt, которые executor ставит через new Date() на каждом шаге.
   ev: backend/src/games/game-state.service.ts:560;backend/prisma/schema.prisma:368-393;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Utils/Canis/utils/localization/ILocalizer.cs:154;DuelEngine-transfer/duel-engine/UnityProject/Assets/Editor/TournamentTests.cs:105-109
- [DET-6] P2 | adapt | src=original | Хвост показанных событий на каждого игрока (displayActions) для догоняния после реконнекта
   why: В оригинале на каждого игрока хранятся lastState и хвост показанных событий (PlayerSaveData.cs:32-36), и клиент проигрывает его ускоренно. Это реплей для живой партии, а не для архива. У нас один снапшот на seq, а eventsSince отдаёт журнал команд без исходов (game-state.service.ts:1280-1340). Решение в основном относится к измерению протокола и презентации; здесь фиксирую только связь: после DET-2 такой хвост строится из журнала команд и снимков, без отдельного хранилища.
   benefit: Ход ИИ или соперника, пропущенный при реконнекте, можно показать, а не просто перескочить снапшотом.
   cost: M; в рамках измерения протокола, после DET-2. | risk: Дублирует работу судьи по протоколу; не делать независимо от него.
   VERIFY=weakened: Подтверждено: у оригинала на каждого игрока хранятся lastState и displayActions. Утверждение «клиент проигрывает хвост ускоренно» я по коду не проверил. Неточность про нас: снапшот несёт не только состояние, но и публичные записи последнего исхода — lastCombat (R-01, примененные эффекты боя), lastMovement (MS-T-14) и skippedEffects (DE-016). Это частичная замена displayActions для последнего события. Сетевой контракт прямо говорит, что replay не обещается и свежесть обеспечивает барьер-снапшот. P2 и привязка к измерению протокола уместны.
   ev: DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Canis/canis/PlayerSaveData.cs:32-36;backend/src/games/game-state.service.ts:1280-1340;docs/game-design/16-network-contract.md:46
- [DET-7] P3 | keep-ours | src=both | Модель состояния: оставить неизменяемый документ GameState вместо дерева сущностей Canis или изменяемых классов DuelEngine
   why: Наш readonly-документ со спредами и движок без I/O дают бесплатное ветвление состояния для симуляций и тестов. У оригинала изменяемое дерево Entity с ConcurrentDictionary и блокировкой матча (Match.cs:1458), клонирования нет. У DuelEngine изменяемые классы и ручной StateClone, где каждое новое поле легко забыть (StateClone.cs:16-25); вдобавок клон копирует скрытую руку соперника. Переносить нечего.
   benefit: Не тратим силы на переписывание; клон для будущего ИИ на симуляции уже есть даром.
   cost: Нет. Если делать ИИ на симуляции, детерминизировать скрытые карты соперника при ветвлении: это вопрос измерения ИИ. | risk: readonly в TypeScript проверяется только при компиляции; мутации через `as any` ловит deep-freeze в DET-3.
   VERIFY=confirmed: Подтверждено: GameState — readonly-интерфейс, движок без I/O. PrismaService и RedisService в не-spec файлах game-engine отсутствуют; единственное вхождение — last-movement.spec.ts. Ручной StateClone у DuelEngine подтверждён. Оговорка: неизменяемость проверяется только компилятором, а сервисы движка асинхронные и внедряются через DI. «Клон даром» верен для состояния, но симуляции нужен собранный executor, например s03Engine.
   ev: backend/src/game-engine/models/game-state.model.ts:40-65;backend/src/game-engine/services/game-action-executor.service.ts:150-152;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Canis/canis/entities/Entity.cs;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Canis/canis/Match.cs:1458;DuelE
- [DET-8] P3 | keep-ours | src=original | Хранение и конкурентность: оставить Postgres JSONB + Redis-кеш с версией + Redis-лок + optimistic seq в транзакции
   why: Наша схема строже оригинала и DuelEngine. У оригинала снимок на паузе (SaveOnPause, Match.cs:2376) и блокировка в памяти процесса. У DuelEngine хранения нет совсем. У нас условный updateMany по статусу, проверка seq-1 и ELO в одной транзакции (game-state.service.ts:189-247), а кеш принимается только при совпадении version (:540-545). Единственная системная слабость — три представления состояния (GameState, белый список SerializedGameState, сырой JSON в Redis). Её закрывает инвариант round-trip из DET-3, переписывание не нужно.
   benefit: Не трогаем работающий и покрытый тестами механизм.
   cost: Нет, кроме инварианта в DET-3. По желанию — кешировать в Redis результат serialize() вместо сырого GameState, тогда пути через кеш и через БД совпадут (S). | risk: Без инварианта следующее новое поле metadata снова будет жить только в кеше до TTL.
   VERIFY=confirmed: Подтверждено: условный updateMany по IN_PROGRESS, проверка seq-1 и ELO в одной транзакции; кеш принимается только при совпадении status и version; TTL 600. Поправки к ссылкам: ключ лока game:${id} стоит в resolver на :162-163, а не на :270 (там опции лока ttl=10000). Не упомянуто: в GameStateService есть мёртвый updateWithLock с другим ключом лока gamestate:lock: — если его когда-нибудь вызовут, он не будет сериализован с мутациями. Round-trip покрыт точечными спеками, но не инвариантом на каждом шаге.
   ev: backend/src/games/game-state.service.ts:172;backend/src/games/game-state.service.ts:189-247;backend/src/games/game-state.service.ts:503-549;backend/src/games/resolvers/game-actions.resolver.ts:270;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Canis/canis/Match.cs:2376;DuelEngine-transfer/tes
- [DET-9] P3 | skip | src=both | Сериализуемый корутинный стек действий (ExecuteStack + Serialized*-двойники) и журнал внутренних действий как запись партии
   why: У оригинала такой стек — цена встроенного C#-DSL: на каждое действие нужен двойник Serialized*. В TS генераторы не сериализуются, и аналог потребовал бы того же двойника на каждый шаг (оценка XL). Наши паузы — уже данные (combatResolutionProgress/combatEffectContinuation, pendingEffects), и они переживают рестарт. Журнал внутренних действий DuelEngine (ActionLog) при запуске не воспроизвёл партию (0/120), поэтому как запись партии он не годится. Объединение pending-полей в одну сущность «ожидаемое решение» — вопрос измерения эффектов и протокола, а не детерминизма.
   benefit: Экономия XL-переписывания.
   cost: Нет. | risk: Россыпь pending-полей растёт с каждым героем. Это следить в измерении эффектов.
   VERIFY=confirmed: Вывод «skip» верен: в DuelEngine повтор по ActionLog дал 0/120 по полному состоянию, а по SelectionResponse — 120/120. Наши паузы хранятся как данные. Мелкая поправка: «почти у каждого действия есть Serialized*-двойник» — преувеличение. В Canis/canis/actions 56 файлов Serialized* при 273 файлах действий, ещё 77 — в duel-canis. Двойники есть у заметной части действий, а не у почти всех. На вывод это не влияет.
   ev: DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Canis/canis/actions/continuations/ExecuteStackContainer.cs:58-60;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Canis/canis/data/PendingSelection.cs:16-31;backend/src/game-engine/models/game-state.model.ts:144-153;DuelEngine-transfer/duel-
- [DET-10] P3 | skip | src=original | Отмена (UndoNode) и подготовка-фиксация хода (IStagedAction)
   why: Отмена и подготовка хода нужны для UX (предпросмотр хода с откатом), а не для детерминизма. В нашем дизайне и плейтестах такой запрос не зафиксирован. Доступна ли отмена онлайн в DE, не проверено. Неизменяемое состояние позволяет добавить предпросмотр позже без изменений в ядре.
   benefit: Не тратим время.
   cost: Нет. | risk: Нет.
   VERIFY=confirmed: Типы UndoNode и IStagedAction существуют. У PendingSelection есть поля CreateUndo и CreateUndoCriteria. Доступна ли отмена онлайн в DE, не проверено, это судья и сам указал. Для детерминизма это не нужно, skip верен.
   ev: DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Canis/canis/entities/UndoNode.cs;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Canis/canis/actions/staged/IStagedAction.cs
- [DET-11] P3 | adapt | src=original | Модификаторы только в состоянии: убрать ValueModifierService с памятью процесса
   why: В оригинале модификаторы (Mod с ModID и SortOrder) лежат в атрибутах сущностей, то есть в сохраняемом состоянии. Наш ValueModifierService держит модификаторы в Map в памяти процесса (value-modifier.service.ts:33). Сейчас он не вызывается, но внедрён в executor (:162). Первое же его использование сломает сохранение, работу нескольких инстансов и воспроизведение партии. Правило: игровое состояние только в GameState.
   benefit: Закрывает будущий источник недетерминизма и потери состояния.
   cost: S: удалить сервис и зависимости или пометить запрещённым; если модификаторы понадобятся, хранить их в GameState. | risk: Минимальный: сервис не вызывается (grep `valueModifier.` пуст).
   VERIFY=confirmed: Подтверждено: Map в памяти процесса, ни один метод сервиса не вызывается (grep addModifier/applyModifiers/valueModifier. пуст). Уточнения. Сервис внедрён в двух местах: executor :163, а не :162, и card-effect-executor :120; ещё его создаёт s03-фикстура :39. При удалении это три правки. Типы ValueModifierType и ValueModifier живут и используются generic-hero-ability.handler, где модификаторы считаются на лету с timestamp: Date.now(). Типы надо сохранить, удалять только сервис с Map. Того же класса, но безвредный: в CombatResolverService есть процессный cardValueCache с TTL по Date.now(), ключ —
   ev: backend/src/game-engine/engine/value-modifier.service.ts:33;backend/src/game-engine/services/game-action-executor.service.ts:162;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Attributes/Canis/attributes/MutableAttribute`1.cs:19-32
- [DET-12] P3 | skip | src=none | Проигрыватель архивных реплеев для игрока (ReplayService, GameReplay)
   why: У оригинала проигрывателя сыгранных партий нет, есть только живой хвост (orig-net-client). Наш ReplayService нигде не вызывается и собирает только журнал без исходов. Делать продуктовую функцию не нужно. Если понадобится, она строится поверх DET-2.
   benefit: Не тратим время на фичу без запроса.
   cost: Нет; по желанию удалить мёртвый ReplayService и GameStateHistory (S). | risk: Нет.
   VERIFY=confirmed: Подтверждено: ReplayService нигде не вызывается. buildReplay вне файла не используется, GameReplay в коде не упоминается, GameStateHistory, GameStateSnapshot, previousStateId и newStateId не используются (grep пуст). ReplayService собирает только журнал без исходов. Skip верен, удаление мёртвого кода — по желанию.
   ev: backend/src/games/services/replay.service.ts;backend/src/games/games.module.ts:114;backend/prisma/schema.prisma:294-313;backend/prisma/schema.prisma:579-603
MISSED: Журнал системных шагов имеет дыры по seq. processAutoResolve сохраняет состояние на каждом раунде executeResolveCombat (combat-timeout.service.ts:451), а recordAudit пишет один раз в конце, с финальным seq (:486). При выходе по потолку раундов (:471-483) записи нет вовсе. Аудит авто-выбора (:595-612) сознательно не хранит параметры фолбэка. «Один вход на один seq» не выполняется, и DET-2 должен во || Многошаговые pending сохраняют id: CHOOSE_SPACE stage 2 (game-action-executor.service.ts:1399-1404) и chooseCount>1. Восстановление UE после потерянного ответа на stage 1 найдёт тот же id и останется в «RECOVERY held: still open» (S08FlowController.cpp:1783-1787), хотя seq ушёл вперёд. Это конкретный, проверяемый случай для DET-4, сильнее гипотетической коллизии. Последствия на ретраях не проверен || Язык команд неполон: в AiAction и dispatchAiAction нет playScheme, setStance и toggleDoor (ai-decision.service.ts:19-34; ai-turn.service.ts:29-150). ИИ никогда не играет scheme. Для DET-2 нужен отдельный маппинг этих DTO, а фазз через политику ИИ (DET-3) не покроет схемы, стойки и двери. || У оригинала Random и SelectionRandom получают ОДИН И ТОТ ЖЕ mid.randomSeed, а при seed == 0 оба создаются без seed (Match.txt:4143-4225). Это два генератора с одинаковым стартом, а не независимые потоки. Тезис «оригинал детерминирован по seed» верен только при ненулевом seed. || В CombatTimeoutService уже есть инъекция часов (поле now, combat-timeout.service.ts:69-71), но executor читает Date.now() напрямую (:2243, :2530) и пишет timeoutAt из Date.now() в состояние (:2158, :2301). В тестах это два разных источника времени. Готовый образец снижает цену DET-2(б). || Round-trip serialize/deserialize и приватная проекция уже покрыты точечными спеками: game-state.service.spec.ts:426, :1087, :1146; s05-boost-timing.spec.ts:389; last-movement.spec.ts:386; s07-privacy-projection.spec.ts. Инварианты DET-3 строятся на них, их не надо писать с нуля. Проверки на каждом шаге партии пока нет. || Клиент получает не SerializedGameState, а JSON.stringify(filterPrivateData(rawGameState)) (game.resolver.ts:92-97, game-actions.resolver.ts:253). Это четвёртое представление состояния, и именно оно делает утечку seed реальной: белый список serialize здесь не защищает. || Мёртвый GameStateService.updateWithLock (game-state.service.ts:1116-1147) берёт другой лок, gamestate:lock:, а не game:${id}, как мутации. При случайном использовании он не будет сериализован с executeMutation. || Мелкие неточности ссылок у судьи: лок game:${id} — resolver :162-163, а не :270; системный Date.now — executor :2530, а не :2529; внедрение ValueModifierService — :163 и ещё card-effect-executor :120; executeMutation вызывается ровно 14 раз, и все eventType отображаются в GameActionType, то есть все человеческие мутации журналируются.

######## DIM decision-protocol — Протокол выборов игрока (Selection/Prompt)
SUMMARY: Вердикт по измерению: свой протокол выборов оставляем, ни на Canis, ни на DuelEngine не переписываемся. По сути он уже близок к оригиналу:
- сервер авторитетен;
- человек, ИИ и таймаут отвечают через одни и те же методы executor;
- вопросы и продолжение боя хранятся как данные и переживают рестарт;
- в каждом окне защитник идёт первым;
- для «may» есть optional и decline;
- скрытое редактируется для каждого зрителя;
- клиент собирает черновик и отправляет один атомарный ответ, без переотправки.

Из оригинала стоит взять три идеи (в DuelEngine они реализованы хуже):
1. **P0, S.** Монотонный счётчик на каждый вопрос и шаг. Сейчас id не уникален, а многошаговые выборы сохраняют его. Это даёт латентное залипание UE-клиента на Restless Spirits (схема Артура) после потерянного ответа: подтверждено чтением кода, живьём не воспроизведено.
2. **P1, M.** Один серверный перечислитель допустимых ответов, который публикуется как offer. Он заменит пять расходящихся копий: резолвер, pending-targets, фолбэк, ИИ и C++-зеркало. Это главная защита при росте ростера с 4 до ~84 героев.
3. **P1, M.** Дедлайны и фолбэк для любого открытого вопроса, а не только для боя. Нужно решение пользователя по таймеру хода и подмене ИИ, как в DE.

Мелкие доработки:
- ИИ при null или отказе executor уходит в системный фолбэк (P1, S);
- серверное время для таймеров (P2);
- ИИ работает на проекции filterPrivateData (P2);
- общий конвейер commit/publish (P2);
- случайный легальный ответчик и фазз на реальных картах, надёжный журнал ответов для реплея (P2, после seeded RNG).

Из DuelEngine брать нечего. Его протокол к тому же несёт ошибки правил: бесплатная схема, общий буст в бою, авторешение «may».
OURS: Как устроено у нас (проверено по коду):

1. **Вопрос не передаётся отдельным сообщением.** Его выводят из состояния. В `GameState.metadata` лежат:
   - глобальная FIFO-очередь `pendingEffects`: 8 типов, у каждого `id`, `playerId` и флаг `optional` (`backend/src/game-engine/models/game-state.model.ts:385-456`);
   - отдельные «ресурсные» выборы `pendingManeuver` и `pendingHandDiscard`, у них id содержит turnCount и seq (`:326`, `:334`; `game-action-executor.service.ts:292`, `:1755`);
   - отложенная передача хода `pendingTurnEnd` (`:377`);
   - бой на паузе — `CombatEffectContinuation` в виде данных (`:144-153`).

   Продолжение тоже хранится как данные: у CHOOSE_ONE есть `optionEffects`, у боя есть `remaining`. Поэтому пауза переживает рестарт.

2. **Ответ.** Мутации `resolvePendingEffect` и `declinePendingEffect` с обязательным `effectId`; поля счётчика (counter) нет (`backend/src/games/dto/gameplay.dto.ts:287-343`). Резолвер проверяет четыре вещи (`game-action-executor.service.ts:566-591`):
   - нет открытого ресурсного выбора;
   - id существует;
   - это голова очереди;
   - отвечает владелец выбора.

   После ответа `drainAfterChoice` снимает головы без легальной цели (`effects/pending-targets.ts:66-77`), затем продолжает бой или передачу хода (`:230-251`).

3. **Человек, ИИ и таймаут применяют ответ через одни и те же методы executor.** Но конвейер «сохранить → разослать → журнал» скопирован трижды:
   - резолвер `games/resolvers/game-actions.resolver.ts:154-281`;
   - 
- [SEL-01] P0 | adopt | src=original | Счётчик вопроса (Counter) на каждый шаг выбора; ответ несёт счётчик
   why: У оригинала монотонный счётчик на матч, ответ с устаревшим счётчиком отбрасывается. У нас id вопроса не уникален. Причины:
- id строится от каталожного id эффекта и длины очереди;
- CHOOSE_SPACE stage 2 и остаток CHOOSE_ONE при chooseCount>1 сохраняют прежний id, причём у CHOOSE_ONE опции ещё и переиндексируются.

Конкретный дефект — Restless Spirits, схема Артура из основного ростера:
1. Ответ на stage 1 теряется (исход неизвестен).
2. UE-клиент блокирует ввод, пока id не исчезнет из очереди (S08FlowController.cpp:1773-1787).
3. Сервер уже выставил stage 2 с тем же id.
4. Вне боя таймаута нет, закрыть выбор некому, и клиент залипает до перезапуска.

По той же причине таймауту боя нужна эври
   benefit: - Закрывает латентное залипание клиента на многошаговых выборах.
- Упрощает проверку прогресса в combat-timeout и логику восстановления в UE.
- Устаревший или повторный ответ (Game Tester, будущий ретрай) отбивается кодом STATE_CHANGED, а не применяется к новому вопросу с тем же id.
   cost: S. Что менять:
- в metadata — монотонный `choiceCounter`, +1 при каждом новом вопросе или шаге: pendingEffects, stage 2, остаток chooseCount, pendingManeuver, pendingHandDiscard;
- поле `counter` в PendingEffect;
- необязательный `counter` в ResolvePendingEffectDto и DeclinePendingEffectDto, при рас | risk: Низкий. Поле добавляется, старые клиенты без counter продолжают работать. Нужно не сломать презентер S09PendingPresenter: он считает «то же открытие» по id, поэтому id оставить стабильным, а менять то
   VERIFY=weakened: Дефект реален. Restless Spirits — схема King Arthur, Copies:1. Stage 2 и остаток CHOOSE_ONE сохраняют id, UE держит блокировку, пока этот id есть в очереди, а вне боя дедлайна нет. Это подтверждено чтением кода.

Механизм судья завысил:
1. Монотонный счётчик у нас уже есть — GameState.sequenceNumber. Паттерн «ответ несёт счётчик» тоже уже применяется: BeginManeuverDto.expectedSequenceNumber, проверка в executor. Новый choiceCounter не нужен. Достаточно добавить необязательный expectedSequenceNumber в ResolvePendingEffectDto и DeclinePendingEffectDto.
2. Самый дешёвый фикс залипания — новый id 
   ev: backend/src/game-engine/services/game-action-executor.service.ts:1399-1401;backend/src/game-engine/services/game-action-executor.service.ts:1050-1077;backend/src/game-engine/effects/card-effect-executor.service.ts:531;backend/src/game-engine/effects/effect-text-parser.ts:791;backend/src/games/servic
- [SEL-02] P1 | adapt | src=both | Один серверный перечислитель допустимых ответов и публикация «предложения» (offer) в проекции
   why: В оригинале сервер сам перечисляет цели (TargetMap, MovableSpacesFor), и человек, ИИ и сеть выбирают из этого перечня. В DuelEngine то же самое: явные списки вариантов и проверка «ответ ∈ список».

У нас одно и то же множество допустимого независимо считают пять мест: резолвер, pending-targets, системный фолбэк, ИИ и зеркало в UE. Они уже расходятся:
- CHOOSE_SPACE: фолбэк требует свободную клетку, резолвер и ИИ — нет;
- UE не зеркалирует canAttackAtRange.

Каждый новый герой из ~84 в БД увеличивает число таких зеркал. Расхождение ИИ и валидатора вешает VS_AI-матч. Расхождение клиента и сервера даёт неверную подсветку целей. Переписывать хранение не нужно: достаточно чистой TS-функции `legal
   benefit: - Новая механика карты сразу доступна ИИ, таймауту, Game Tester и подсветке UE; ИИ физически не может сделать нелегальный ход.
- Паритет-тесты C++ сводятся к сверке с offer.
- Становится возможным случайный ответчик и фазз (SEL-08).
- Структурно закрывает вопросы без выполнимого ответа: сейчас DISCA
   cost: M для этапа 1: pendingEffects (fighterIds, cellsByFighter, cells, cardIds, optionIndices, min/max):
- модуль game-engine/decisions/legal-answers.ts;
- резолвер, фолбэк, pruneHeadPendingsWithoutTargets и ai-decision.decidePending переводятся на него;
- поле offer в проекции только для владельца голов | risk: Средний:
- переходный период с двумя источниками истины;
- объём снапшота растёт, но умеренно: десятки клеток на реальных картах;
- нужен тест «offer ⊆ принимаемое резолвером» на Marmoreal и Sarpedon.
   VERIFY=weakened: Подтверждено, что допустимое множество независимо считают пять мест:
- валидатор резолвера;
- pendingHasValidTarget;
- buildSystemPendingFallback вместе со своим pickFallbackFighter (дубль pendingCandidates);
- эвристика ИИ;
- C++-зеркало.

Серверного перечислителя или запроса допустимых ответов нет.

Поправки:
1. Приведённое «расхождение» по CHOOSE_SPACE — не противоречие. Фолбэк берёт свободную клетку, а это легальное подмножество того, что принимает резолвер (тот проверяет только проходимость и зону). Фолбэк просто наносит 0 урона.
2. Отсутствие canAttackAtRange в UE — задокументированное о
   ev: backend/src/game-engine/effects/pending-targets.ts:89-153;backend/src/game-engine/services/game-action-executor.service.ts:897-978;backend/src/game-engine/services/game-action-executor.service.ts:1001-1018;backend/src/game-engine/services/game-action-executor.service.ts:1379-1397;backend/src/game-en
- [SEL-03] P1 | adapt | src=original | Серверный дедлайн и фолбэк для любого открытого вопроса, не только для боя (+ решение пользователя по таймеру хода и подмене ИИ)
   why: В оригинале все таймеры серверные (90/60/30). В Live при таймауте ход доигрывает ИИ, после двух таймаутов подряд игрока снимают.

У нас таймаут есть только у боя. Выбор вне боя (схема, способность начала хода, pendingManeuver, pendingHandDiscard), как и сам ход, может висеть бесконечно. В PvP соперник ждёт без выхода. Механизм фолбэка уже есть: drainTimedOutPendingChoices и buildSystemPendingFallback. Его надо распространить на все вопросы, а не изобретать заново.
   benefit: PvP-партия не может зависнуть из-за AFK. Вместе с SEL-01 закрывается сценарий залипания Restless Spirits.
   cost: M:
- `deadlineAt` на каждом вопросе (pendingEffects, pendingManeuver, pendingHandDiscard) и `offeredAt`;
- BullMQ-джоба с ключом (game, counter) — обобщение очереди combat-timeout с recovery sweep;
- фолбэк: decline для optional, buildSystemPendingFallback, манёвр без движения, сброс первых N.

Тайм | risk: Средний:
- нужно согласовать длительности: DE даёт 60 с на защиту против наших 30;
- нельзя отнимать окно у «думающего» игрока;
- придётся переписать часть приёмочных сценариев GD-026.
   VERIFY=weakened: Вне боя дедлайнов нет: планируются только DEFENSE и RESOLVE, вне COMBAT процессор отвечает no-op. Это подтверждено.

Поправки:
1. «В PvP соперник ждёт без выхода» — неверно. Любой участник может вызвать мутацию abortGame; есть и путь player_left. Выход есть, хотя без результата и штрафа AFK-игроку.
2. Длительности в оригинале противоречивы. TimerLengths даёт 90/60/30, а текст локализации для Live говорит «3 minutes to complete a turn» (:2935). Строка про Async (3 дня) — :2893, а не :2935.
3. В пользу рекомендации: у оригинала таймер привязан к каждому вопросу — Match.GetTimerForSelection, GetT
   ev: backend/src/game-engine/models/game-state.model.ts:19-20;backend/src/games/services/combat-timeout.service.ts:376-382;backend/src/games/services/combat-timeout.service.ts:525-590;backend/src/game-engine/services/game-action-executor.service.ts:897-978;DuelEngine-transfer/test-targets/cpp2il-cs/Diffa
- [SEL-04] P1 | adapt | src=original | ИИ не может «застрять»: при null на своём mandatory или отказе executor — системный фолбэк
   why: В оригинале есть DefaultRandomChoice — запасной ответ на любой вопрос.

У нас ИИ на свой mandatory-выбор без решения возвращает null, а при отказе executor шаг заканчивается return false. Матч VS_AI ждёт до следующего триггера, а у человека в чужой фазе легальных мутаций нет. Фолбэк для таких случаев уже написан (buildSystemPendingFallback), но ИИ его не использует.
   benefit: VS_AI-матчи не висят при любом расхождении эвристики ИИ и валидатора, в том числе на новых героях.
   cost: S. Что менять:
- в AiDecisionService/AiTurnService: если decide вернул null на собственной mandatory-голове или executor отверг ответ, один раз вызвать buildSystemPendingFallback и затем decline/skip;
- писать предупреждение в журнал;
- spec на каждый тип pending. | risk: Низкий. Фолбэк легален по построению. Ходы ИИ в этих редких случаях будут слабыми, но игра пойдёт дальше.
   VERIFY=weakened: Подтверждено:
- ИИ возвращает null на своей mandatory-голове;
- при отказе executor шаг останавливается.

Поправки:
1. В бою зависания нет. drainTimedOutPendingChoices резолвит голову очереди любого владельца, в том числе ИИ. Проблема остаётся только вне боя.
2. Почти во всех ветках, где decidePending возвращает null, buildSystemPendingFallback тоже возвращает null: CHOOSE_ONE без options, TARGET_FIGHTER без живых целей, CHOOSE_SPACE без якоря, DECK_TOP_PICK без карт, BOOST_CHOICE всегда. Поэтому «один раз вызвать фолбэк» спасает в основном случай «executor отверг ответ ИИ», а не null.
3. Реал
   ev: backend/src/game-engine/services/ai-decision.service.ts:62-70;backend/src/game-engine/services/ai-decision.service.ts:218;backend/src/games/services/ai-turn.service.ts:204-213;backend/src/game-engine/services/game-action-executor.service.ts:897-978;DuelEngine-transfer/test-targets/cpp2il-cs/Diffable
- [SEL-05] P2 | adopt | src=original | Серверное время в снапшоте для отсчёта дедлайнов на клиенте
   why: В оригинале клиент получает DisplayTimer{startedAt, endsAt} и ServerTimeSync и считает поправку часов. Наш UE считает остаток как разницу timeoutAt и FDateTime::UtcNow() без поправки. Если часы клиента расходятся с сервером, таймер защиты показывается неверно.
   benefit: Честный отсчёт 30/10 с и будущих дедлайнов SEL-03 при любом расхождении часов клиента.
   cost: S. Что менять:
- поле `serverNow` в ответе мутации и gameStateUpdated (или остаток в секундах);
- в UE — сохранять смещение и использовать его в FS08CombatInfo::SecondsUntilDeadline. | risk: Низкий.
   VERIFY=confirmed: Подтверждено: UE считает остаток как TimeoutAt минус UtcNow без поправки часов.

Уточнения:
1. В оригинальном DisplayTimer кроме startedAt и endsAt есть WaitTime и TotalTime (длительности). Поэтому вариант «прислать остаток в секундах» — тоже из оригинала.
2. Польза мала: дедлайн авторитетен на сервере, и это влияет только на отображение. Целевой сервер локальный (INT-006).
   ev: unreal/Unmatched/Source/Unmatched/S08/S08Contracts.cpp:634-637;unreal/Unmatched/Source/Unmatched/S08/S08Contracts.h:126-129;docs/game-design/08-integration-decisions.md:104-108
- [SEL-06] P2 | adapt | src=both | ИИ получает ту же проекцию filterPrivateData, что и человек
   why: «Единый интерфейс» должен означать и одинаковую видимость. Сейчас AiTurnService передаёт в decide полное состояние, с рукой и колодой соперника. Нынешняя эвристика туда не смотрит, но ничто этого не запрещает. Пример того, к чему это приводит: L2-ИИ в DuelEngine играет на открытых картах.
   benefit: ИИ структурно не может подглядывать. Это важно до перехода на ИИ с симуляцией: её стоит строить только на проекции с детерминизацией неизвестных карт.
   cost: S. В ai-turn.service.runOneStep вызывать decide(filterPrivateData(state, aiUserId), …), а исполнять по полному состоянию. Плюс spec «решение не меняется от содержимого чужой руки». | risk: Низкий. Нужно проверить, что decide не читает удаляемые поля (combatEffectContinuation): сейчас он использует только combatInfo.
   VERIFY=confirmed: Подтверждено:
- decide получает полное состояние;
- нынешний ИИ читает только свою руку и публичный combatInfo: защиту выбирает без чтения значения атаки, BOOST_CHOICE — только после reveal;
- filterPrivateData синхронная и прячет колоды даже от владельца, но decide колоды не читает.

Стоимость S реальна. В DuelEngine L2-ИИ действительно учитывает содержимое руки соперника и клонирует колоду с рукой.
   ev: backend/src/games/services/ai-turn.service.ts:202-204;backend/src/games/game-state.service.ts:828-893;backend/src/game-engine/services/ai-decision.service.ts:302-324;DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/AI/ScoringPlayer.cs:288-295;DuelEngine-transfer/duel-engine/UnityProjec
- [SEL-07] P2 | adapt | src=original | Одна точка «применить ответ → сохранить → разослать → журнал» для человека, ИИ и таймаута
   why: В оригинале все источники ответа пишут через один ISessionWriter, затем Match.Write и MessageRouter. У нас ответ применяется общим executor, но конвейер commit/publish/journal скопирован в резолвере, ai-turn и combat-timeout. При добавлении SEL-03 (новые дедлайны) и SEL-01 появится уже четвёртая копия с риском разъехаться.
   benefit: Дедлайны, публикация CUE и журнал одинаковы при любом источнике ответа. Меньше дублированного кода.
   cost: M. Выделить сервис commitDecision(gameId, prev, next, eventType, actor) и перевести на него три вызывающих места; e2e-проверка VS_AI и таймаута. | risk: Средний: трогает горячий путь всех мутаций. Нужны существующие spec s04/s10 и прогон VS_AI.
   VERIFY=confirmed: Подтверждено, причём польза больше, чем пишет судья: три копии уже разошлись.

В резолвере executeMutation вызовы publishGameUpdate и scheduleAutoResolve после saveState не защищены try/catch. Если упадёт Redis publish, уже закоммиченная мутация вернётся клиенту ошибкой «Unexpected error during …» (BadRequest). UE считает любой errors[] окончательным отказом, сбрасывает черновик и разрешает повтор. Вместе с повторным использованием id из SEL-01 повтор может примениться к новому шагу.

В AI-пути и в таймауте публикация сделана best-effort. Общий commitDecision с best-effort публикацией устраняе
   ev: backend/src/games/resolvers/game-actions.resolver.ts:154-281;backend/src/games/services/ai-turn.service.ts:196-249;backend/src/games/services/combat-timeout.service.ts:360-450
- [SEL-08] P2 | adapt | src=both | Случайный легальный ответчик + фазз-самоигра на реальных картах
   why: В оригинале есть DefaultRandomChoice. Фазз DuelEngine со случайными ходами за секунды нашёл баг затирания победы (Б1), который его 25 зелёных маркеров пропустили. Если у нас будет offer (SEL-02), случайный ответчик займёт около 30 строк. Фазз по Marmoreal и Sarpedon с инвариантами (seq растёт, нет вечных pending, GAME_OVER не перезаписывается, у каждого вопроса есть легальный ответ) проверит протокол выборов целиком.
   benefit: Дешёвое массовое тестирование протокола на всех героях из БД, а не только на четырёх с артом.
   cost: M. Headless-раннер поверх GameActionExecutorService без Postgres, со снапшотом контента. Зависит от SEL-02 и от seeded RNG (другое измерение). | risk: Низкий. Только тесты. Без seed найденные падения труднее воспроизводить.
   VERIFY=weakened: Идея здравая, но стоимость завышена, а зависимость указана неверно.
- Headless-движок без Postgres уже есть: s03Engine собирает реальный GameActionExecutorService на чистых сервисах.
- Полные детерминированные партии уже идут через реальный executor с seeded LCG вместо Math.random и проходят resolvePendingEffect для каждого типа pending (s06-full-games.spec).
- Значит, фазз не ждёт продакшен-seeded RNG.
- В DuelEngine уже есть RandomPlayer.cs.

Стоимость S-M. Утверждения про «Б1» и «25 маркеров» я не проверил.
   ev: DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Canis/canis/entities/PlayerEntity.cs:289;backend/src/games/services/s06-full-games.spec.ts:7;backend/src/game-engine/effects/pending-targets.ts:66-77
- [SEL-09] P2 | adapt | src=duel-engine | Журнал ответов как запись партии (надёжный GameAction с seq/counter)
   why: В DuelEngine повтор партии по паре (seed, список SelectionResponse) сходится 120/120, а по журналу действий не работает. У нас GameAction уже хранит имя мутации и входной DTO, то есть ответы. Но пишется он асинхронно через BullMQ и может теряться, а seq и counter не фиксирует.
   benefit: Вместе с seeded RNG появляется реплей и воспроизведение багов по журналу ответов, без нового формата записи.
   cost: M. Писать GameAction в транзакции saveState с seq и counter; replay-раннер. Зависит от seeded RNG (другое измерение). | risk: Средний: растёт нагрузка на транзакцию. Реплей ломается при смене версии парсера эффектов, поэтому нужно хранить PARSER_VERSION.
   VERIFY=weakened: «seq не фиксирует» — неверно. У GameAction есть колонка sequenceNumber с индексом, и резолвер её передаёт.

Подтверждено:
- запись асинхронная через BullMQ, best-effort.

Настоящие пробелы:
- нет seed: в продакшене Math.random в тасовке;
- журнал разнородный: ИИ пишет AiAction (`ai:<kind>`), таймаут пишет только метод (decline или deterministic-fallback) без самого ответа (фолбэк детерминирован, его можно пересчитать).

Про 120/120 в DuelEngine подтверждений в логах я не нашёл: unverifiable.
   ev: backend/src/games/resolvers/game-actions.resolver.ts:106-130;backend/src/games/services/game-action.service.ts:18-48;backend/src/games/services/replay.service.ts
- [SEL-10] P3 | adapt | src=original | Приватная часть вопроса по общему правилу вместо поштучной редакции
   why: В оригинале видимость задаётся декларативно (Visibility/obfuscator), а Selection уходит только выбирающему. У нас очередь видят оба игрока, а filterPrivateData вручную вырезает только revealedCards у DECK_TOP_PICK. Будущие выборы вроде «посмотри руку соперника и выбери» потребуют помнить о новой редакции.
   benefit: Новые типы выборов не утекают сопернику по забывчивости.
   cost: S. Поле `private?` в PendingEffect, которое filterPrivateData всегда снимает у не-владельца; revealedCards перенести туда. | risk: Низкий.
   VERIFY=confirmed: Подтверждено:
- редакция поштучная, вырезается только revealedCards;
- в оригинале есть Visibility и MessageObfuscator.

Уточнение: оба игрока видят и card, optionEffects, effectContext у pending. Сейчас это публичные (сыгранные или вскрытые) карты, утечки я не нашёл. Ценность низкая, P3 уместен.
   ev: backend/src/games/game-state.service.ts:886-893;backend/src/game-engine/models/game-state.model.ts:435-438;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Canis/canis/obfuscation/Visibility.cs
- [SEL-11] P3 | adapt | src=original | Подсказки к целям (TargetStrength, optimalPlayMap, CanAutoSelect)
   why: Оригинал помечает цели как сильные или слабые и разрешает автовыбор единственной цели. У нас автовыбор уже частично есть: при единственном легальном ответе MOVE сервер применяет нулевой шаг, клиент сам подставляет единственного бойца. Подсказки имеют смысл только после SEL-02.
   benefit: UX и туториал; может пригодиться для лёгкого уровня ИИ.
   cost: S-M поверх SEL-02. | risk: Низкий.
   VERIFY=confirmed: В оригинале TargetStrength подтверждён: Strong, Weak, Negative, Forced, … CanAutoSelect, Any. У нас «единственный ответ» обрабатывается так: голова без другой цели снимается prune'ом, нулевой шаг подразумевается. Имеет смысл только после SEL-02.
   ev: DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Networking/Networking/selection/messages/SelectionWithTargetsRequired.cs:34-35;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Networking/Networking/selection/TargetStrength.cs;backend/src/game-engine/effects/pending-targets.ts:79-88
- [SEL-12] P3 | keep-ours | src=original | Хранение вопросов как данных: очередь pendingEffects, CombatEffectContinuation, pendingTurnEnd
   why: Оригинал сериализует остаток стека корутин: у каждого действия есть двойник Serialized*. У нас продолжение уже хранится как данные: optionEffects, remaining, флаги отмены. Пауза переживает рестарт, recovery sweep это подтверждает.

Переносить генераторы JS нельзя, а миграция в единую сущность PendingDecision стоит L при низкой отдаче. Единый взгляд дают дешевле производная функция `currentDecision(state)` и offer из SEL-02.
   benefit: Нет переписывания executor (3172 строки), AI, таймаута и контракта UE.
   cost: 0 | risk: Остаются отдельные поля pendingManeuver и pendingHandDiscard; их сглаживает производный слой SEL-02.
   VERIFY=confirmed: Подтверждено: продолжение хранится как данные — CombatEffectContinuation.remaining, optionEffects, pendingTurnEnd. drainAfterChoice возобновляет бой и передачу хода.
   ev: backend/src/game-engine/models/game-state.model.ts:144-153;backend/src/game-engine/models/game-state.model.ts:324-378;backend/src/game-engine/services/game-action-executor.service.ts:230-251;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Canis/canis/data/PendingSelection.cs:16-31
- [SEL-13] P3 | keep-ours | src=original | Клиентский черновик и атомарный ответ, подача modal/compact/toast, без переотправки при неизвестном исходе
   why: Это та же модель, что RootSelection/Advance/Cancel в оригинале: шаги проходятся локально, отправляется один ответ. Наш UE вдобавок надёжнее DuelEngine: при неизвестном исходе команда не переотправляется, а исход сверяется с авторитетным состоянием. Презентер S09PendingPresenter — собственное UX-решение, принятое пользователем.
   benefit: Ничего не ломаем.
   cost: 0, кроме доработки по SEL-01. | risk: нет
   VERIFY=confirmed: Подтверждено:
- при неизвестном исходе UE не переотправляет команду, а переходит в recovery с refetch;
- презентер решает modal/compact/toast по новому id головы.

Оговорка: после «still open» лестница refetch повторно не взводится, и блокировку снимает только WS-снапшот без этого id. Отсюда зависимость от SEL-01.
   ev: unreal/Unmatched/Source/Unmatched/S09/S09PendingPresent.h:62-110;unreal/Unmatched/Source/Unmatched/S08/S08FlowController.cpp:2585-2593;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/core-canis/dwd/core/match/selection/RootSelection`1.cs
- [SEL-14] P3 | skip | src=original | Одновременные выборы и отмена выбора (SimultaneousSelection, Slapjack, ParallelResponse, CreateUndo, IStagedAction)
   why: В дуэли Unmatched выборы последовательные, в каждом окне защитник идёт первым. Строгая FIFO-очередь с одной головой это правильно моделирует. Отмена выбора в онлайн-PvP с авторитетным сервером не нужна: черновики и так локальные.
   benefit: —
   cost: 0 | risk: нет
   VERIFY=confirmed: Подтверждено:
- SimultaneousSelection и Slapjack есть только в общих Canis и core-canis; grep по duel-canis использований не нашёл;
- наш резолвер принимает ответ только на голову очереди.
   ev: backend/src/game-engine/services/game-action-executor.service.ts:584-588;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/core-canis/dwd/core/match/selection/SimultaneousSelection.cs
- [SEL-15] P3 | skip | src=duel-engine | Протокол DuelEngine целиком: синхронный TCP, форфейт за 30 с и за нелегальный ответ, индексы руки, GetSelection с побочными эффектами, авторешение «may»
   why: Его единственная хорошая идея — явный список вариантов в запросе — уже покрыта SEL-02, и в оригинале она реализована лучше. Остальное хуже нашего:
- форфейт за таймаут и за ошибку клиента вместо фолбэка;
- индексы руки вместо instance id;
- у запроса есть побочные эффекты;
- необязательные выборы решаются за игрока.
   benefit: —
   cost: 0 | risk: нет
   VERIFY=confirmed: Подтверждено:
- форфейт за таймаут 30 с и за нелегальный ответ;
- ответы по индексам руки;
- авторешение «may».

Нюанс: при разрыве соединения у DuelEngine есть grace-переподключение, то есть разрыв — не мгновенный форфейт.
   ev: DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Networking/MatchServer.cs:35;DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Networking/MatchServer.cs:334;DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Networking/MatchServer.cs:481;DuelEngine-transfer/du
- RULE [RD-SEL-01] high | Схема — одно из двух действий хода, выбирается в том же вопросе, что манёвр и атака
   orig: Схема — третий вид действия. InitiateAction увеличивает ActionsTaken и для схемы (по отчёту orig-rules: ISIL InitiateAction :1461, :1895; localization.txt:4752).
   ours: Схема тратит действие (по отчётам orig-rules и ours: game-action-executor.service.ts:2439; game-state.model.ts:458-462).
   duel: В протоколе основной выбор — только MainOption{Attack, Maneuver}. Схема вынесена в отдельный ChooseSchemeRequest с CanPass до или после действия, то есть она бесплатная, одна за ход.
   VERIFY=confirmed: Подтверждено:
- у нас схема тратит действие (consumeAction);
- в локализации оригинала схема — третий тип действия;
- в DuelEngine SchemePhase бесплатна, 1 за ход, до или после действия.

Из ISIL я видел только вызовы ActionsTaken и IsSchemeCard в InitiateAction. Что инкремент идёт именно для схемы, оттуда напрямую не доказано, основание — локализация и правила настолки.
   ev: DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Core/Selection.cs:16-21;DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Core/Selection.cs:55;DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Core/Engine.cs:236;DuelEngine-transfer/test-targets/cpp2il-isil/Is
- RULE [RD-SEL-02] high | Вопрос «буст в бою»
   orig: Общего шага бустов в бою нет. Буст атаки предлагается только по тексту карты (BoostAttackAbility: Second Shot, Noble Sacrifice) или пассивкой Артура (по отчёту orig-rules).
   ours: BOOST_CHOICE появляется только от эффекта карты («You may BOOST…»), optional, одна своя карта после reveal.
   duel: ChooseBoostRequest для обеих сторон боя: любая карта, сколько угодно, с CanPass (фазы DefenderBoostPhase и AttackerBoostPhase).
   VERIFY=confirmed: Подтверждено:
- в CombatStates оригинала нет шага буста, только окна Immediate, During и After;
- BoostAttackAbility лежит в Heroes/Shared/Abilities, то есть буст бывает только по тексту карты.

Собственный docs/rules-diff.md DuelEngine считает буст в бою «Совпадает». Это ошибка их документа.
   ev: DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Core/Selection.cs:89-95;backend/src/game-engine/models/game-state.model.ts:396-398;backend/src/game-engine/services/game-action-executor.service.ts:611-616;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/scrip
- RULE [RD-SEL-03] medium | Необязательные эффекты «may» и выбор «any fighter» спрашиваются у игрока
   orig: У вопроса есть флаг Forced; необязательный выбор задаётся игроку как не-Forced selection (SelectionWithTargetsRequired.Forced; по отчёту orig-core — SelectedTargetBuilder.WithForced).
   ours: Флаг PendingEffect.optional и мутация declinePendingEffect; mandatory отклонить нельзя.
   duel: «may» решается автоматически (Hot for Battle, Short Lead Hook — авто-свап). «any fighter» сужено до враждебных бойцов (Stick and Move, Jaws That Bite).
   VERIFY=weakened: Про DuelEngine — подтверждено: Hot for Battle и Short Lead Hook свапаются автоматически, «any fighter» сужено до врагов.

Но наша сторона описана неполно. Карточные «may» действительно идут через optional и decline. Однако data-driven фреймворк способностей героев сам упрощает печатное «you may»: автоцель — первый подходящий враг, отказа нет (общее правило и, например, Dracula «Children of the Night»). Это то же упрощение, за которое судья критикует DuelEngine, на части из ~70 героев фреймворка. Честный optional-выбор сделан только для отдельных способностей, например Medusa.
   ev: DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Core/Events.cs:153-156;DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Core/Events.cs:1215-1216;DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Core/Events.cs:1414-1415;DuelEngine-transfer/test-targets/cpp2i
- RULE [RD-SEL-04] low | Таймауты выбора и хода (правило цифрового издания, не настольной игры)
   orig: Таймеры серверные, константы TimerLengths 90/60/30 (ход, защита, добавка ИИ). В Live при истечении ход делает ИИ, после двух таймаутов подряд игрока снимают. В Async на ход 3 дня, затем замена ИИ.
   ours: Только окна боя 30 с (защита) и 10 с (резолв). По истечении optional-выборы отклоняются, mandatory получают детерминированный первый легальный ответ. Таймера хода, таймаутов выборов вне боя и снятия игрока нет.
   duel: 30 с на каждый ответ, затем форфейт матча. Нелегальный ответ тоже даёт форфейт.
   VERIFY=weakened: Суть верна:
- в оригинале таймеры серверные;
- в Live при таймауте ход играет ИИ, после двух подряд игрока снимают;
- у нас только окна боя;
- в DuelEngine — форфейт.

Поправки:
1. Строка про Async (3 дня) — localization.txt:2893.
2. Строка :2935 говорит о Live «3 minutes to complete a turn». Это противоречит константе StartingTurnLength=90, так что фактическая длительность хода в Live не установлена.
3. На нашей стороне есть ручной выход abortGame.
   ev: DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/data/enums/TimerLengths.cs:5-7;DuelEngine-transfer/test-targets/unmatched-data/localization.txt:2719;DuelEngine-transfer/test-targets/unmatched-data/localization.txt:2754;DuelEngine-transfer/test-targets/unmatched-data/local
MISSED: Ложный окончательный отказ после коммита.
- Где: executeMutation в game-actions.resolver.ts:183-268.
- Что происходит: state сохраняется, затем падает publishGameUpdate (Redis) или scheduleAutoResolve. Клиенту уходит errors[] «Unexpected error during …».
- Как реагирует UE: такой ответ — окончательный отказ (S08FlowController.cpp:740-752). Черновик сбрасывается, игрок может повторить ответ. Повтор || Счётчик и прецеденты уже есть в коде.
- GameState.sequenceNumber плюс expectedSequenceNumber у BeginManeuverDto (gameplay.dto.ts:97-109; executor:1746).
- Новый id на шаге у DECK_TOP_PICK (`-order`, executor:1558); seq в id у DISCARD_CARDS (card-effect-executor.service.ts:598).
- SEL-01 закрывается без новой сущности choiceCounter: новый id для stage 2 и для остатка CHOOSE_ONE, плюс необязательный || Выборы способностей героев идут в обход протокола.
- Фреймворк ABILITY_CONFIGS для части героев автоматически выбирает первого врага и не даёт отказаться от печатного «you may» (ability-config.ts:278-280, :697-701, Dracula).
- Такие решения вообще не становятся pendingEffects: их не видит ни человек, ни ИИ, ни таймаут.
- При росте ростера с 4 до ~84 героев это более крупный пробел протокола, чем п || ИИ вообще не играет схемы: в AiAction нет kind для playScheme, а в decide на своём ходу есть только атака, манёвр и конец хода (ai-decision.service.ts:91-112). «Единый интерфейс человек/ИИ» неполон уже по набору действий. Схемные выборы (Restless Spirits и др.) ИИ никогда не порождает, поэтому VS_AI их не тестирует. || Остаток CHOOSE_ONE при chooseCount>1 ставится в ХВОСТ очереди, после вложенных pending из выбранной опции и после уже ждущих чужих выборов (executor:1066-1077). Вторая опция той же карты может оказаться позади чужих выборов. Это расхождение порядка выборов, судья его не разобрал. || У оригинала таймер привязан к каждому вопросу:
- Match.GetTimerForSelection, GetTimerPaddingForSelection, GetTotalTimerTime (Match.cs:2236-2240);
- счётчик подряд идущих таймаутов в PlayerEntity: ConsecutiveAITimeouts, IncrementConsecutiveTimeout, ConsecutiveTimeoutThreshold (ISIL PlayerEntity.txt:26, :3073-3119).

Это прямой образец для SEL-03: deadlineAt на вопросе и правило «два таймаута подряд || Инфраструктура фазза уже есть: s03Engine — headless executor без БД (test/fixtures/s03-engine.fixture.ts:35-47); seeded LCG и полные партии через реальный executor — s06-full-games.spec.ts:1-9; RandomPlayer.cs есть в DuelEngine. SEL-08 стоит S-M и не ждёт продакшен-seed. || Восстановление в UE не взводит повторный refetch после ответа «pending choice still open» (S08FlowController.cpp:1768-1792, :806-816). Блокировку снимает только следующий снапшот без этого id. Значит, любой многошаговый выбор с сохранённым id, а не только Restless Spirits, блокирует клиента до рестарта, если ответ на первый шаг потерян.

######## DIM net-client — Сеть и клиентская презентация
SUMMARY: **Вердикт по сети и клиентской презентации: сетевую модель оставить, взять три-четыре идеи оригинала про протокол и показ событий, у DuelEngine брать нечего.**

**Модель совпадает с оригиналом.** Онлайн Unmatched DE — авторитетный сервер, не lockstep (CanisOnlineMatch.cs:70, 109-113). Скрытое там прячется на сервере отдельно для каждого получателя — у нас то же самое (filterPrivateData, game-state.service.ts:828). Свой надёжный канал оригинала (ack, повторная отправка, буфер, пачки, CanisNetworkState.cs:153-189) нам не нужен: самодостаточный снапшот, барьер по since и правило «не отправлять повторно» решают ту же задачу проще.

**Идеи, которые стоит адаптировать:**
- **P1, NET-1. Поток типизированных событий для показа** (по образцу StartSequence/StopSequence и реестра SequenceCommandConstructor). Делать как список событий за каждый seq в снапшоте, по образцу уже работающего lastCombat.appliedEffects, с проекцией на зрителя. На клиенте — реестр «вид события → стейджинг». Сейчас там, где записей нет, клиент угадывает причину:
  - звук истощения по признаку «удары по 2» (S08FlowGameModeAudio.cpp:192-198);
  - карту-источник по запомненному тексту pending (S09OpponentView.h:214);
  - взгляд Медузы по id pending (S09AbilityStage.h:1-5).

  Способности есть у 29 из ~84 героев, и каждой новой без событий понадобится своя эвристика.
- **P1, NET-2. Счётчик шага у многошаговых выборов** (идея Counter). У CHOOSE_ONE×N, CHOOSE_SPACE и DECK_TOP_PICK id между шагами не меняется (executor :1055, :1400, :1557). Восстановление клиента держит лок, пока id не исчезнет (FlowController.cpp:1783). Если потерялся ответ на шаг 1, ввод вне боя блокируется навсегда. Это вывод по коду, сценарий не воспроизводил: уверенность средняя.
- **P2:**
  - NET-3 — серверное время в снапшоте. Сейчас локальный UtcNow плюс якорь lastActionAt, который после перезапуска клиента в окне защиты показывает полные 30 с.
  - NET-4 — хвост событий для показа пропущенного после реконнекта (displayActions, SkipLiveReplay).
  - NET-5 — сервер сам передаёт допустимые клетки и цели для pending (TargetMap).
  - NET-6 — таймер хода с «ИИ доигрывает»; это решение пользователя.

**Не брать:**
- надёжный канал оригинала;
- GameLift и API Gateway;
- движок оригинала в клиенте для офлайна;
- всю сеть DuelEngine: TCP только на loopback, ответ индексом руки, техническое поражение за 30 с (MatchServer.cs:129, 481, 544).

**Оставить как есть:** локализацию (у нас тоже коды и ключи с шаблонами), многошаговый черновик с одним атомарным ответом, политику догоняния hurry/cut.

**Расхождения правил в этом измерении касаются только сетевой политики:**
- в оригинале таймер хода 3 минуты с заменой на ИИ, у нас таймера хода нет;
- окно защиты 60 с против наших 30 с;
- при таймауте у нас детерминированный фолбэк, а в оригинале решает ИИ.
OURS: **Сетевая модель.** Сервер авторитетный, состояние уходит клиенту полным снапшотом с проекцией на каждого зрителя (`filterPrivateData`, backend/src/games/game-state.service.ts:828). Счётчик `sequenceNumber` растёт строго на +1 за мутацию. Подписка `gameStateUpdated(since)` отдаёт барьер-снапшот (docs/game-design/16-network-contract.md:7-20, 44-96). Повтор пропущенных событий контракт прямо не обещает (16-network-contract.md:44-48). Именованные CUE-подписки — вспомогательные, без барьера, клиент UE на них не подписан (unreal/Unmatched/Source/Unmatched/S08/S08GraphqlWs.h:5; S08GraphqlWs.cpp:10-13). Транспорт — graphql-transport-ws и HTTP GraphQL. Матчмейкинг (очередь, расширяющееся окно, подтверждение, штрафы) и presence есть свои: backend/src/matchmaking/services/*, backend/src/presence/*.

**Клиент S08/S09.**
- Защита по seq: меньший seq игнорируется, равный сливается, больший применяется. Анимации строятся только на непрерывном переходе local+1; на разрыве и на барьере CUE подавляются (S08/S08FlowController.cpp:1692-1721; S08FlowController.h:846-856).
- Презентацию собирают четыре вещи:
  - дифф соседних снапшотов;
  - структурированные записи сервера в metadata: `lastCombat` с `appliedEffects`, `parent` и `source` карты; `lastMovement`; `skippedEffects` (backend/src/game-engine/models/game-state.model.ts:324-378);
  - диспетчер CUE (S08/S08CueDispatcher.h);
  - стейджинги боя, способности и смерти плюс политика догоняния hurry/cut (S09/S09CombatStage.h, S09AbilityStage.h, S
- [NET-1] P1 | adapt | src=original | Типизированный список событий презентации за каждую мутацию в снапшоте; на клиенте реестр «вид события → стейджинг / строка журнала / звук»
   why: У оригинала презентация идёт из потока событий с именованными скобками (StartCombat, CombatDamage, Reveal) и реестра обработчиков. У нас хороший образец уже есть: lastCombat.appliedEffects несёт source карты и parent. Но для остального (истощение, урон и движение от схем и способностей, добор, сброс) записей нет. Поэтому клиент угадывает причину эвристиками:
- звук истощения выбирается по признаку «несколько ударов по 2» и ошибается, если боец один или если схема наносит 2+2;
- карту-источник ищет по запомненному тексту pending, а после разрыва остаётся пустая строка;
- взгляд Медузы опознаёт по id pending.
Способности есть у 29 из ~84 героев. Каждой новой способности сейчас нужна новая эври
   benefit: Один источник для анимаций, журнала HUD, звука и Game Tester. Пропадают эвристики. Новые способности героев показываются без нового кода угадывания. Это основа для NET-4 (повтор хвоста).
   cost: L.
- Бэкенд M: помощник withEvent(state, ev) по образцу withSkippedEffect (pending-targets.ts:36); поле metadata.events{seq, kind, source{cardId, catalogId, name}, targets, value, parent, key+vars}; вызовы в executor примерно в 15–25 точках (draw, exhaustion, damage, move/place, scheme, discard, tur | risk: Утечка скрытой информации через события: нужна проекция и тест приватности. Схема metadata разрастается. Есть соблазн вести состояние по событиям — запретить в контракте (16-network-contract.md §4: ис
   VERIFY=confirmed: По сути вывод верен. Поправки и дополнения:
- Опознание взгляда Медузы — это не «просто id». Префикс `ability-medusa-target` зашит в коде, и к нему добавлено условие «pending исчез, а один из targetFighterIds потерял HP в том же переходе». При этом бэкенд даёт id общего вида `ability-<heroId>-target|move-p<n>`, так что эвристика привязана к одному герою.
- Судья пропустил ещё одну эвристику: клиент разбирает id pending, чтобы найти карту-источник. Префикс `ability-` означает героя, префикс `<catalogId>-<field>-<i>` — карту (UmHudPending.cpp SourceName).
- Пробел уже известен: в контракте §5.1 
   ev: DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/core-commands/dwd/core/match/sequence/SequenceParser.cs;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-client/duel/sequences/DuelStartCombatSequence.cs:49;DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/act
- [NET-2] P1 | adapt | src=original | Счётчик шага у многошаговых выборов (аналог SelectionMessage.Counter): иначе после потери ответа лок ввода не снимается
   why: В оригинале у каждого вопроса свой Counter, и ответ со старым счётчиком отбрасывается. У нас CHOOSE_ONE с chooseCount>1, CHOOSE_SPACE (стадия 1→2) и DECK_TOP_PICK (PICK→ORDER) сохраняют тот же id между шагами (`...pending`, executor :1055, :1400, :1557).

Восстановление клиента после потерянного ответа ничего не отправляет повторно. Оно держит лок, пока id не исчезнет из pendingEffects (FlowController.cpp:1783-1787). Если потерялся ответ на шаг 1, свежий снапшот показывает тот же id уже на шаге 2: лок держится, а ответить на шаг 2 нельзя.
- В бою выручает серверный таймаут резолва.
- Вне боя (схемы Restless Spirits, Prophecy) таймаута нет, и ввод игрока блокируется навсегда.

Сам сценарий не
   benefit: Нет вечного лока. Сервер отбрасывает дубль или старый ответ на шаг, а не принимает его как ответ на следующий шаг.
   cost: S: поле PendingEffect.step (+1 на каждом шаге, в тех же трёх местах executor); необязательное expectedStep в ResolvePendingEffectDto и DeclinePendingEffectDto; клиент запоминает при входе в восстановление (id, step) и считает выбор закрытым, когда пара сменилась; спека на каждый из трёх видов. | risk: Минимальный: поле необязательное, старые сейвы без него читаются как step 0.
   VERIFY=weakened: Корень найден верно: CHOOSE_ONE с chooseCount>1 и CHOOSE_SPACE на переходе 1→2 сохраняют id, а восстановление держит лок, пока id есть в очереди. Поправки:
1. **DECK_TOP_PICK назван неверно.** Шаг ORDER получает новый id `${pending.id}-order`, так что Prophecy этой проблемы не имеет.
2. **Баг шире, чем описано.** Лок держится, пока id в очереди, даже после свежего HTTP-чтения: bStillOpen обнуляет bFreshResult. Значит, любой resolve или decline любого типа, запрос которого не дошёл до сервера (HttpStatus 0), вне боя держит лок бессрочно. Предложенная пара (id, step) этот случай не лечит. Нужно 
   ev: backend/src/game-engine/services/game-action-executor.service.ts:1055;backend/src/game-engine/services/game-action-executor.service.ts:1400;backend/src/game-engine/services/game-action-executor.service.ts:1557;unreal/Unmatched/Source/Unmatched/S08/S08FlowController.cpp:1783;unreal/Unmatched/Source/U
- [NET-3] P2 | adapt | src=original | Серверное время в каждом снапшоте и смещение часов на клиенте (ServerTimeSync + DisplayTimer{StartedAt, EndsAt})
   why: Сейчас две разные опоры времени:
- проверка команд и экран паузы считают по локальному UtcNow (S08Contracts.cpp:634-636; S08FlowGameMode.cpp:2711; UmPause.cpp:349);
- таймер HUD считает от metadata.lastActionAt (UmHud.cpp:2121-2129), то есть от времени последней мутации, а не от времени отправки.

Если клиент перезапущен в окне защиты, барьер-снапшот несёт lastActionAt момента атаки, и HUD покажет полные 30 с вместо остатка. Если часы ПК сбиты, кнопки разрешаются или запрещаются не в тот момент. В оригинале этим занимаются ServerTimeSync и ServerTimeOffset.
   benefit: Честный обратный отсчёт после реконнекта и при сбитых часах. Одна опора времени для HUD, гейтов и звука DeadlineBeeper. Задел под таймер хода (NET-6).
   cost: S: поле serverTime (резолвится в момент отправки) в DTO GameState для query, mutation и subscription; клиент хранит смещение, SecondsUntilDeadline берёт UtcNow+offset; якорь lastActionAt убрать; тест S09CombatTests на просроченное окно со смещением. | risk: Низкий. Задержку сети не учитывает, ошибка на её величину: для окон 10–30 с это допустимо.
   VERIFY=confirmed: Подтверждено:
- `SecondsUntilDeadline` считает по локальному UtcNow;
- HUD опирается на `metadata.lastActionAt`, а это время мутации (`new Date()` в executor);
- серверного времени нет нигде, ни в бэкенде, ни в клиенте.

Якорь lastActionAt выбран сознательно, чтобы не зависеть от сбитых часов. Цена — неверный остаток после перезапуска клиента в окне защиты. Сценарий не воспроизводил, вывод по коду.

Последствие сбитых часов — только UX (тост и гейт кнопки). Сервер дедлайн проверяет сам: в контракте §6 «Ранний системный резолв запрещён».
   ev: unreal/Unmatched/Source/Unmatched/S08/S08Contracts.cpp:634;unreal/Unmatched/Source/Unmatched/S08/S08FlowGameModeUmHud.cpp:2116;unreal/Unmatched/Source/Unmatched/S08/S08FlowGameMode.cpp:2711;unreal/Unmatched/Source/Unmatched/S08/S08FlowGameModeUmPause.cpp:349;unreal/Unmatched/Source/Unmatched/S08/S08
- [NET-4] P2 | adapt | src=original | Ограниченный хвост событий для показа пропущенного после реконнекта (аналог displayActions + SkipLiveReplay)
   why: Сейчас на разрыве и на барьер-снапшоте клиент гасит все CUE (FlowController.cpp:1692-1721), а контракт повтор не обещает (16-network-contract.md:44-48). Если игрок переподключился во время хода ИИ или соперника, он видит только итоговое состояние и подсветку последнего хода. Оригинал хранит хвост показанных событий для каждого игрока и проигрывает его ускоренно, с кнопкой пропуска. Это опирается на NET-1.
   benefit: Видно, что сделал соперник или ИИ, пока игрок был офлайн. Задел под async-режим.
   cost: M после NET-1: кольцевой буфер последних N событий в state (как SKIPPED_EFFECTS_KEPT) или в Redis рядом со state; на барьере клиент проигрывает события с seq>local в режиме hurry из S09PresentationCatchup с пропуском; в контракте §3 описать ограниченный повтор. | risk: Размер снапшота растёт: N ограничить, например событиями текущего и прошлого хода. Двойной показ на равном seq: дедупликация по seq в FS08CueDispatcher уже есть (D2/D3).
   VERIFY=weakened: Идея оригинала подтверждена: `PlayerSaveData{lastState, displayActions}`, `SkipLiveReplay`, `ClearDisplayActionsForPlayer`. Но судья упустил три вещи.
1. **Предложение идёт против принятого критерия релиза ACC-012.** Там прямо сказано «конечное состояние совпадает с сервером… без старых CUE». То же в приёмке GD-044 «старые события после reconnect не играют» (статус done). Значит, NET-4 — это пересмотр критерия, и без слова пользователя его не делать.
2. **Журнал для хвоста уже есть.** Запрос `eventsSince` отдаёт журнал GameAction с проекцией на зрителя и пагинацией complete-boundary. Новый кол
   ev: DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Canis/canis/PlayerSaveData.cs:37;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Canis/canis/Match.cs:1842;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Canis/canis/Match.cs:1991;unreal/Unmatched/Source/Unmatched/S08/S08FlowControll
- [NET-5] P2 | adapt | src=both | Сервер передаёт в проекции допустимые цели и клетки для своей головы очереди (аналог TargetMap и Options-списков)
   why: Оригинал присылает TargetMap, DuelEngine — списки Options, HandIndices и Zones; и человек, и ИИ отвечают только из списка. У нас список есть только у TARGET_FIGHTER. Для MOVE, PLACE и CHOOSE_SPACE клиент повторяет правила (достижимость, зоны, баннеры) и держит паритет-тесты, хотя сервер то же самое уже считает (computeReach в pending-targets.ts). Каждая новая способность движения требует правки клиентских правил.
   benefit: Для pending клиент больше не дублирует правила: подсветка совпадает с сервером по построению. Game Tester и ИИ получают тот же перечень.
   cost: M: legalCells и legalFighterIds в проекции владельца головы (из pendingHasValidTarget/computeReach), для pendingManeuver — достижимость по бойцам. Клиент берёт подсветку из списка, свой расчёт оставляет для пути и превью. Паритет-тест сравнивает со списком. | risk: Снапшот растёт на десятки клеток, это терпимо. Пути для отрисовки клиент всё равно считает сам. Бэкенд и клиент можно обновлять в любом порядке: поле необязательное.
   VERIFY=weakened: Верно, что сервер уже считает достижимость (computeReach и reachableEndpoints) и что готового списка клеток в проекции нет. Поправки:
- **«Передаются лишь ограничения» — не совсем.** Для MOVE и PLACE в бою передаются `fighterIds` допустимых бойцов, для PLACE — `zoneFighterName`.
- **Польза завышена.** Клиентский движок достижимости (ComputeReachMap, ReachEndpoints, BuildCanonicalPath) нужен всё равно, для черновика манёвра с BOOST. Паритет уже держится на общих golden-фикстурах бэкенда (backend/prisma/fixtures/movement). Уйдут только правила подсветки pending: зоны, баннеры, revive, свободная 
   ev: DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Networking/Networking/selection/messages/SelectionWithTargetsRequired.cs:32;DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Core/Selection.cs:10;DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Networking/MatchServer.
- [NET-6] P2 | adapt | src=original | Таймер хода и таймаут выборов вне боя: ИИ доигрывает за игрока, после двух подряд — снятие (нужно решение пользователя)
   why: Таймауты у нас есть только у боя. Если игрок молчит в чужом ходе или на выборе вне боя, PvP-партия висит до abortGame. Матчмейкинг у нас есть, так что риск реален для PvP; для VS_AI он не важен. В оригинале Live: 3 минуты, ход за игрока делает ИИ, после двух таймаутов подряд игрока снимают. Инфраструктура для этого у нас готова: BullMQ combat-timeout, recovery sweep, buildSystemPendingFallback, ai-decision.service.
   benefit: PvP-партия не зависает. Используются готовые механизмы.
   cost: M: дедлайн turnTimeoutAt в metadata; задача в той же очереди; по таймауту ход делает ai-decision.service через те же мутации; счётчик strikes → abortGame/resign; HUD-таймер на NET-3. | risk: Это продуктовое решение: длительности и что считать снятием. Неверный таймаут хуже его отсутствия. Без слова пользователя не делать.
   VERIFY=weakened: Подтверждено:
- таймеров вне боя у нас нет;
- у оригинала есть HandleIdleTurn и тексты о захвате хода ИИ и о снятии игрока.

Судья упустил три вещи:
1. **В проекте уже есть своя рекомендация по таймеру хода**, по разбору DE: «если появится таймер хода в онлайне — показывать заранее и мягко; по истечении — пас или манёвр на месте, а не ИИ». Предложение «ИИ доигрывает» ей противоречит.
2. **По видео DE лимит хода около 85 с**, это сходится со StartingTurnLength=90. Цифра «3 минуты» есть только в подсказке первой live-игры.
3. **За таймаут первого хода оригинал снимает игрока сразу, без ИИ** (`di
   ev: DuelEngine-transfer/test-targets/unmatched-data/localization.txt:2719;DuelEngine-transfer/test-targets/unmatched-data/localization.txt:2754;DuelEngine-transfer/test-targets/unmatched-data/localization.txt:2935;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/data/enums/Tim
- [NET-7] P3 | keep-ours | src=none | Модель «авторитетный сервер + полный снапшот с проекцией на зрителя + seq-guard + барьер» оставить
   why: По сути это та же модель, что у оригинала: сервер — истина, скрытое прячется на сервере отдельно для каждого получателя. Полный снапшот самодостаточен, и восстановление проще, чем в схеме «снапшот + дельты + ack». Монотонный seq с двойной защитой (лок + оптимистическая проверка) и барьер закрывают окно реконнекта. Переход на дельты или lockstep — переписывание без выигрыша.
   benefit: Ноль работы, корректность по построению.
   cost: нет | risk: Каждый кадр несёт весь снапшот вместе с графом доски. Это не мерили; оптимизировать только при превышении бюджета (правило проекта).
   VERIFY=confirmed: Модель подтверждена:
- filterPrivateData работает на каждого зрителя;
- seq монотонный, под локом с оптимистической проверкой;
- есть барьер-снапшот.

Риск подтверждён: в каждом WS-кадре идёт boardState (поле есть в запросе подписки клиента).
   ev: backend/src/games/game-state.service.ts:828;backend/src/games/game-state.service.ts:189;docs/game-design/16-network-contract.md:7;docs/game-design/16-network-contract.md:52;unreal/Unmatched/Source/Unmatched/S08/S08FlowController.cpp:1685;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/boardgam
- [NET-8] P3 | skip | src=original | Свой надёжный канал (ack, повторная отправка, буфер не по порядку, пачки, deflate+base64) — не брать
   why: Это нужно оригиналу, потому что его модель — снапшот плюс дельты, где потерянная дельта ломает состояние. У нас WS поверх TCP, а самодостаточный снапшот, барьер по since и правило «никогда не отправлять повторно, восстанавливаться перечитыванием» (GD-037, FlowController.cpp:2588) решают ту же задачу проще и без риска двойной траты.
   benefit: —
   cost: нет | risk: —
   VERIFY=confirmed: У оригинала есть счётчик сообщений, буфер сообщений не по порядку, ack и GetUnackedMessages (повторная отправка неподтверждённых), ping 2 с, порог реконнекта 18 с и ReJoinGameSession.AckClientMessages. Отказ брать это обоснован: у нас самодостаточный снапшот и правило «no resend».
   ev: DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/boardgames/boardgames/match/CanisNetworkState.cs:153;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/boardgames/boardgames/match/CanisNetworkState.cs:186;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Networking/Networking/service/Re
- [NET-9] P3 | skip | src=original | Процесс на матч (GameLift), лобби через API Gateway, отдельный platform-WS, Steam-сессии — не брать
   why: Это масштаб и платформа издателя. Наш один NestJS с Redis pub/sub между инстансами, матчмейкинг и presence закрывают нужды проекта.
   benefit: —
   cost: нет | risk: —
   VERIFY=confirmed: Строки gamelift и execute-api в metadata_strings.txt есть (строки 287 и 290, сильно склеенные). Matchmaking и presence у нас свои. Поправок нет.
   ev: DuelEngine-transfer/test-targets/unmatched-data/metadata_strings.txt:287;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Networking/Networking/game/DWDGameSession.cs:13;backend/src/games/services/game-subscription.service.ts:158;backend/src/matchmaking/matchmaking.module.ts
- [NET-10] P3 | skip | src=original | Тот же движок в клиенте для офлайна (CanisOfflineMatch) — не брать
   why: В UE это был бы второй движок правил на C++ рядом с TS-бэкендом: два источника правды. Для офлайна достаточно локального бэкенда.
   benefit: —
   cost: нет | risk: —
   VERIFY=confirmed: Верно. Ссылка на доказательство неточна: DBGCanisOfflineMatch лежит в общей dbg-библиотеке. Офлайн-матч самого Unmatched — duel-client/duel/client/match/DuelCanisOfflineMatch.cs.
   ev: DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/dbg-client/boardgames/match/canis/DBGCanisOfflineMatch.cs;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/boardgames/Canis/boardgames/CanisMatch.cs
- [NET-11] P3 | skip | src=duel-engine | Сеть DuelEngine (TCP на loopback, JSON вручную, ответ индексом руки, техническое поражение за 30 с) — не брать
   why: Работает только на одной машине, без авторизации и хранения, публичное состояние урезано. Ответ по индексу в руке хрупок против наших id экземпляров. Хорошие мелочи — токен места и окно переподключения — у нас уже есть на уровне JWT, refresh, барьера и штрафов матчмейкинга. Переотправка висящего запроса у нас неявная: очередь pendingEffects сама входит в снапшот.
   benefit: —
   cost: нет | risk: —
   VERIFY=confirmed: Верно: TcpListener на Loopback, таймаут ответа 30 с, Forfeit, окно переподключения 15 с, токены мест. Поправка к цитате: MatchServer.cs:21 говорит «без reconnect, авторизации и очереди матчей», а не «нет хранения». Этот комментарий устарел: reconnect в том же файле есть (строки 61, 457).
   ev: DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Networking/MatchServer.cs:21;DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Networking/MatchServer.cs:129;DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Networking/MatchServer.cs:457;DuelEngine-transfer/du
- [NET-12] P3 | keep-ours | src=original | Локализация «сервер шлёт ключ и переменные, клиент подставляет текст» — у нас тот же принцип, оставить; новые записи событий отдавать ключами
   why: Сервер отдаёт code ошибок и коды причин (NO_VALID_TARGETS), у клиента таблица ключей с {var} (S08WhyText.cpp) — это аналог LocalizableTextVariables. Пробел — английские pending.text и options.label для CHOOSE_ONE. Но это задача контента (ru-тексты карт), а не архитектуры; DE русских текстов карт тоже не даёт. В NET-1 события сразу делать ключами с переменными.
   benefit: Русский UI без новых механизмов.
   cost: S внутри NET-1; переводы карт — отдельная работа по контенту. | risk: —
   VERIFY=weakened: Принцип «код ошибки плюс клиентская таблица ключей» у нас есть, но частично. Поправки:
- **Тексты не только английские.** Сервер сам собирает прозу: стадия 2 CHOOSE_SPACE дописывает к тексту по-русски «— теперь выберите смежную клетку», шаг ORDER у DECK_TOP_PICK пишет «Верните N карты на верх колоды…». Ошибки валидаторов идут вперемешку: английская 'Fighter not found' и русские «Клетка вне доски».
- **Клиент показывает этот текст как есть** (Printed в UmHudPending) и разбирает id, чтобы найти карту или героя. Так что «тот же принцип, что LocalizableTextVariables», — преувеличение.
- **У DE ест
   ev: unreal/Unmatched/Source/Unmatched/S08/S08WhyText.cpp:1;backend/src/game-engine/validators/game-rules.validator.ts:47;backend/src/game-engine/models/game-state.model.ts:438;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Canis/canis/gameLogs/SerializedGameLog.cs:10;DuelEngine-transfer/test-targ
- [NET-13] P3 | keep-ours | src=original | Многошаговый выбор локально, наружу один атомарный ответ (аналог RootSelection) — у нас уже так, оставить
   why: Черновик манёвра собирается локально и уходит одной мутацией maneuver со списком перемещений (ManeuverMoveInput), атака — черновиком. Это и есть идея дерева узлов оригинала.
   benefit: —
   cost: нет | risk: —
   VERIFY=weakened: Это верно только для черновиков манёвра и атаки. Поправки:
- **Манёвр — две мутации, не одна:** beginManeuver (добор и трата действия, `expectedSequenceNumber`), затем maneuver с `maneuverId` и списком moves.
- **Многошаговые pending-выборы устроены обратно идее RootSelection.** CHOOSE_ONE×N, две стадии CHOOSE_SPACE и PICK→ORDER у DECK_TOP_PICK уходят на сервер по одному шагу, каждый шаг даёт +1 seq. Это и есть корень NET-2. Так что «у нас уже так» верно наполовину.
   ev: backend/src/games/dto/gameplay.dto.ts:84;unreal/Unmatched/Source/Unmatched/S09/S09MoveDraftView.h;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/core-canis/dwd/core/match/selection/RootSelection`1.cs
- [NET-14] P3 | keep-ours | src=original | Политика догоняния презентации (hurry/cut) вместо блокирующих очередей Delorean — оставить; после NET-1 можно ставить события в очередь, а не обрезать
   why: Решение R-03 принято осознанно: состояние никогда не ждёт презентацию, отставание ограничено. В оригинале очередь вопросов, видимо, ждёт блокирующую последовательность (уверенность средняя: виртуальные вызовы Delorean в ISIL не разрешены). Когда появятся события (NET-1), можно мягче: события одного хода показывать подряд и обрезать только очень длинный хвост.
   benefit: —
   cost: нет; после NET-1 — S | risk: —
   VERIFY=confirmed: R-03 подтверждён: состояние не ждёт презентацию, hurry и cut настраиваются CVar'ами K=3 и T=1500 мс. Про блокировку в Delorean судья сам честно поставил среднюю уверенность. ISequenceBlockage и SequenceQueue существуют, но поведение по ISIL я не проверял.
   ev: unreal/Unmatched/Source/Unmatched/S09/S09PresentationCatchup.h:9;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/boardgames/dwd/core/match/delorean/SequenceQueue.cs:13;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/boardgames/dwd/core/match/delorean/ISequenceBlockage.cs
- [NET-15] P3 | skip | src=original | Наблюдатели, async-режим (PBM) с push-уведомлениями — позже, не сейчас
   why: Наблюдатели запрещены GD-025 (16-network-contract.md §5), async не заявлен. Модель с авторитетным сервером позволяет добавить и то и другое потом. Async без NET-4 и сериализуемых пауз — дорогой.
   benefit: —
   cost: нет | risk: —
   VERIFY=confirmed: Вердикт «skip» обоснован: в контракте §5 режима наблюдателя нет, PBMTurnReady и PBMMatchFound у оригинала есть. Одно доказательство не по делу: TCGameOptions.cs:8 — это константа IsOptimization, ни к наблюдателям, ни к async она отношения не имеет. Про async лучше ссылаться на localization.txt:2893 («3 days to complete a turn»).
   ev: docs/game-design/16-network-contract.md:104;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Networking/canis/messages/PBMTurnReady.cs;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Canis/canis/data/TCGameOptions.cs:8
- RULE [NRD-1] medium | Таймер хода и таймаут выборов вне боя
   orig: Live: 3 минуты на ход; по таймауту ход делает ИИ; два таймаута подряд — игрока снимают. Async: 3 дня на ход, затем замена ИИ. Константы StartingTurnLength=90, AITurnPadding=30.
   ours: Таймера хода нет. Выбор вне боя (pendingEffects, pendingHandDiscard, pendingManeuver) может ждать бесконечно. Выход только через abortGame.
   duel: Любой ответ ждётся 30 с; таймаут или нелегальный ответ — техническое поражение.
   VERIFY=weakened: Наша сторона верна: таймера хода нет. Из игры выводят abortGame и leaveGame, причём leaveGame тоже вызывает abort с reason 'player_left'. Поправки к стороне оригинала:
- **Лимит хода в Live, скорее всего, около 90 с, а не 3 минуты.** StartingTurnLength=90, и наш разбор видео DE намерил около 85 с. «3 минуты» — только в подсказке первой live-игры.
- **За таймаут первого хода игрока снимают сразу, без ИИ** (`disconnect.idleTimeout.firstTurn`).
- **Async подтверждён:** 3 дня на ход, потом снятие и замена ИИ.
- **В ISIL** BeginPlayerTurn вызывает ResetPlayerTurnTime, а EndPlayerTurnScript — Timer.
   ev: DuelEngine-transfer/test-targets/unmatched-data/localization.txt:2719;DuelEngine-transfer/test-targets/unmatched-data/localization.txt:2754;DuelEngine-transfer/test-targets/unmatched-data/localization.txt:2935;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/data/enums/Tim
- RULE [NRD-2] low | Длительность окна защиты
   orig: Константа DefenseTime = 60 с. Как именно она применяется в Live (банк времени или фиксированное окно), не проверено; уверенность средняя.
   ours: DEFENSE_TIMEOUT_SECONDS = 30, плюс отдельное окно ручного резолва RESOLVE_TIMEOUT_SECONDS = 10.
   duel: Общий таймаут ответа 30 с, отдельного окна защиты нет.
   VERIFY=confirmed: Числа верны: DefenseTime=60 против наших 30+10. Судья не отметил, что это расхождение уже зафиксировано как собственное решение проекта: «Наш видимый таймер защиты 30 с — собственное решение. DE здесь не эталон» (SD-27). В DE обратного отсчёта в окне защиты на видео не видно. Как DefenseTime применяется в Live, по-прежнему не проверено.
   ev: DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/data/enums/TimerLengths.cs:6;backend/src/game-engine/models/game-state.model.ts:19;backend/src/game-engine/models/game-state.model.ts:20;DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Networking/MatchServer.c
- RULE [NRD-3] low | Что происходит с решением, на которое истёк таймаут
   orig: Решение принимает ИИ: «your turn was taken by an AI». Применяется ли это к выбору карты защиты, не проверено; уверенность низкая.
   ours: Системный детерминированный фолбэк: защиты нет; optional отклоняется; mandatory — первая опция, первая цель или первые N карт. Mandatory BOOST_CHOICE блокирует.
   duel: Техническое поражение игрока, который не ответил.
   VERIFY=confirmed: Наша сторона подтверждена: buildSystemPendingFallback, mandatory BOOST_CHOICE возвращает null, по таймауту защиты защиты нет. DuelEngine подтверждён: Forfeit. По оригиналу уверенность остаётся низкой. Есть TimedOutSelectionEffectMessage{AccountID} и Match.HandleIdleTurn, но доказательства, что ИИ выбирает карту защиты, нет.
   ev: DuelEngine-transfer/test-targets/unmatched-data/localization.txt:2719;docs/game-design/16-network-contract.md:178;backend/src/game-engine/services/game-action-executor.service.ts:897;DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Networking/MatchServer.cs:481
MISSED: Лок восстановления GD-037 для pending (S08FlowController.cpp:1746-1795) держится, пока id есть в очереди, даже после свежего HTTP-чтения. Значит, любой resolve или decline, чей запрос не дошёл до сервера, вне боя блокирует ввод до выхода или перезапуска клиента, а не только многошаговые выборы. Это противоречит духу ACC-012: «не могут оставить клиента навсегда на устаревшем состоянии». Пара (id, s || В протоколе уже есть родной аналог SelectionMessage.Counter: `expectedSequenceNumber` у beginManeuver (gameplay.dto.ts:103-108, executor:1746). Для NET-2 естественно распространить его на resolvePendingEffect и declinePendingEffect, либо менять id на каждом шаге по образцу `${id}-order` (executor:1559). || Уже есть серверный журнал событий: запрос `eventsSince` по таблице GameAction с проекцией на зрителя и пагинацией complete-boundary (game-state.service.ts:1228-1335). Его стоит учесть в NET-1 и NET-4 как готовый носитель хвоста. Ограничение: запись асинхронная, после коммита. || NET-4 расходится с принятым критерием релиза ACC-012 «без старых CUE» (15-rules-and-release-acceptance.md:53) и с приёмкой GD-044 «старые события после reconnect не играют» (14-sprint-backlog.csv:46). Нужно решение пользователя, а не просто адаптация. || У оригинала для презентации есть типизированные события-эффекты: AbilityUseEffectMessage{entityID, abilityID, causeEntityID}, PlayFX, EffectPlayed, TimedOutSelectionEffectMessage, а также IdleResignFromGame (Networking/canis/messages/effect/*, messages/IdleResignFromGame.cs). Это прямой образец для NET-1 (событие способности вместо эвристики Медузы) и для уведомлений NET-6. || Ещё одна клиентская эвристика: UmHudPending.cpp:474-490 ищет карту-источник и героя, разбирая формат id pending (`ability-<hero>-…`, `<catalogId>-<field>-<i>`). Кроме того, у PendingEffect поле-источник `card` есть только у CHOOSE_ONE (game-state.model.ts:447), у MOVE и PLACE его нет. || Сервер присылает прозу на смеси языков: русские вставки в pending.text (executor:1404, 1562), русские тексты ошибок рядом с английскими и кодами (executor:1032-1035 и game-rules.validator.ts:47-53). Клиент показывает этот текст как есть. Это пробел локализации, и NET-12 его не учитывает. || В проекте уже есть разбор таймеров DE и рекомендация. Лимит хода около 85 с, таймер виден только последние около 28 с. По истечении предлагается «пас или манёвр на месте, а не ИИ» (de-footage/README.md:509, 527; findings/A5.json:158-167). NET-6 и NRD-1 должны на это опираться. || Серверная проверка счётчика у оригинала видна в ISIL: HasExecutionStack.IsValidSelection(counter, player, pendingSelection), ConsumeCounter, HasPendingResponse(selectionCounter), CancelPendingResponse. Там же есть MakeUndo(selectingPlayer) — отмена шага выбора, которой у нас нет (cpp2il-isil/IsilDump/Canis/Canis/hasExecutionStack/HasExecutionStack.txt:2624, 4140, 4526, 6407, 6793).

######## DIM ai-tooling — ИИ, headless-харнес, тесты, телеметрия, баланс
SUMMARY: Вердикт по измерению: архитектуру ИИ и тестов не переписываем, код DuelEngine не берём (AI-12 skip). Берём четыре приёма.

1. **(P1) Headless self-play и фазз** со случайными легальными ходами, на реальном executor и реальных картах, с инвариантами на каждом шаге (AI-01). Наш executor собирается без БД, и прогон ИИ против ИИ «без зависаний» уже есть, но на синтетике 12×2. Тот же приём на DuelEngine за секунды нашёл баг «победа затирается», который их 25 зелёных маркеров пропустили.
2. **(P1) RNG с сидом и сериализуемым состоянием** в GameState вместо 5 вызовов Math.random (AI-02). Это лучше, чем у оригинала и у DuelEngine. Состояние RNG обязательно скрывать в проекции, иначе раскрывается порядок колоды.
3. **(P1) Бот не должен молча вставать** (AI-03). Сейчас decide на своём обязательном выборе отдаёт null, отказ executor тихо глушит цикл, а таймера хода вне боя нет. Нужен запасной легальный ответ, как DefaultRandomChoice в оригинале, плюс громкое логирование.
4. **(P2) Перестройка ИИ по образцу оригинала** (AI-05, AI-06): оценщики по типам решений, объяснимые оценки «значение плюс причина» (AIValueSummer/ValueReason), веса в JSON, уровни сложности с мультипликативным шумом. Ценность карт выводить из нашего CardEffect, а не из 210 рукописных классов. Быстрый шаг до этого: схемы, буст манёвра, сайдкики, сброс худших карт.

**Чего в оригинале нет, хотя DuelEngine это ему приписывает:** клонов и симуляции в ИИ (SimulationEntity не используется) и headless-клиента (dbg-client — UI-фреймворк из 783 файлов). ИИ DE — жадный, и для продукта этого достаточно. ИИ на симуляции (AI-07) — только P3 и только честный, по проекции: L2 DuelEngine подглядывает в руку и колоду соперника.

**Турниры и телеметрия** (AI-09) полезны в первую очередь как карта неисполненных эффектов (manualEffects) и метрика стабильности. Винрейты героев станут значимыми, только когда способности будут у большинства героев (сейчас у 29 из примерно 84). Цифры DuelEngine для баланса не годятся: в 5 правилах он расходится с оригиналом (истощение, бусты в бою, добор 2, бесплатная схема, линейное поле), а в телеметрии ошибки подсчёта. Наш бэкенд по этим правилам совпадает с оригиналом.

**Что не проверено:**
- скорость нашего executor в self-play (нет node_modules);
- есть ли у нас реальные зависания VS_AI на реальном контенте — их и должен выявить AI-01;
- точное распределение шума GetNoiseValue в оригинале (уверенность средняя);
- полнота модели известных карт KnownHand (уверенность средняя).
OURS: **ИИ.** `backend/src/game-engine/services/ai-decision.service.ts` (460 строк) — детерминированная жадная эвристика без весов, без шума и без уровней сложности.
- В union `AiAction` (`:19-34`) нет вида «схема», поэтому бот никогда не играет схемы.
- Атакует только героем лучшей картой, если цель досягаема, иначе манёвр (`:99-113`).
- В манёвре двигает только героя и никогда не бустит: `boostCardId` не задаётся (`:49-57`).
- При лимите руки сбрасывает первые N карт, а не худшие (`:43-47`).
- Защищается лучшей картой, атаку соперника не смотрит (`:302-324`). Это честно, но держится на дисциплине: `decide` получает полное состояние, а не проекцию.
- Если для своего обязательного выбора решения нет, возвращает `null` (`:64-70`). Комментарий в `:246-248` прямо говорит, что раньше матч из-за этого «вис».

**Оркестрация.** `backend/src/games/services/ai-turn.service.ts`: до 40 шагов (`:158,186-189`). Если ИИ промолчал или executor отверг ход, цикл тихо останавливается (`:204,209-212`). Запасного хода нет, а таймера хода вне боя тоже нет (`game-state.model.ts:19-20` — только бой). ИИ ходит теми же мутациями executor, что и человек (`dispatchAiAction`, `:29-153`), и эта функция уже вынесена для тест-харнессов.

**Харнесс и тесты.** Executor не делает I/O, и его можно собрать без Nest DI (`backend/src/games/s10-vs-ai-full-match.spec.ts:47-67`). Значит, headless-прогон в процессе дешёвый. Что есть сейчас:
- (a) `s06-full-games.spec.ts` — 2 полных скриптовых матча Medusa/Arthur. Детермини
- [AI-01] P1 | adapt | src=both | Headless self-play и фазз на реальном executor, на картах Marmoreal и Sarpedon, с инвариантами на каждом шаге
   why: В оригинале есть headless-режим ИИ против ИИ (Headless, IsOptimization, StartAIvsAI). Запуск DuelEngine показал, что фазз со случайными ходами и проверкой инвариантов за секунды находит баг Б1 «победа затирается в очереди эффектов», который тесты на маркерах пропустили. У нас уже есть зародыш: матч ИИ против ИИ с критерием «нет зависаний» (ai-turn.service.spec.ts:268-340). Но доска там 12×2, колоды без эффектов, а executor собирается без БД (s10 buildStack). Это нужно масштабировать, а не изобретать заново.
   benefit: Ловит повисшие очереди выборов, ошибки GAME_OVER, потерю и дублирование карт, бесконечные партии на реальном контенте 29 героев со способностями. Каждая находка приходит с репро (seed плюс список команд). Заодно это гейт против регрессий при добавлении героев.
   cost: M. Новый opt-in прогон (jest-spec за env-флагом или node-скрипт) в backend/src/games/selfplay/. Стек собирается как в s10-vs-ai-full-match.spec.ts:47-67, без Postgres и Redis. Контент берётся из фикстур: prisma/fixtures/boards/*.topology.json и колоды через парсер seed-scraped.ts:61-173 или выгрузку | risk: Контент в фикстурах может разойтись с живой БД (правки в админке, fix-card-gaps.ts). Поэтому выгрузку фикстур из эталона :5433 надо делать периодически. Скорость одного матча на нашем async executor н
   VERIFY=weakened: Сама рекомендация верна, но судья неверно описал, от чего отталкиваться. Готовая основа уже есть. Это s09-card-instance-dup.spec.ts: 60 сидированных полных дуэлей Medusa/Arthur на реальных колодах из 30 карт, через продакшн-executor (s03Engine). После КАЖДОЙ успешной мутации там вызывается checkInvariants: сохранение мультимножества instance id, уникальность внутри зоны и одна зона на карту. Масштабировать надо её, а не матч 12×2 из ai-turn.service.spec.ts. Помеха: доска в s09 — Cobble. При этом фикстура реальной доски marmorealBoardRow() уже есть, и s09 сам её импортирует. Стоимость поэтому с
   ev: backend/src/games/services/ai-turn.service.spec.ts:268-340;backend/src/games/s10-vs-ai-full-match.spec.ts:47-67;backend/src/games/services/s06-full-games.spec.ts:22-24;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Canis/canis/data/TCGameOptions.cs:7-10;DuelEngine-transfer/test-targets/cpp2il
- [AI-02] P1 | adopt | src=both | RNG с сидом и сериализуемым состоянием в GameState вместо Math.random
   why: Харнесс, золотые партии и воспроизведение багов требуют детерминизма. Запуск DuelEngine показал, что (seed, список ответов) воспроизводит партию 120/120. Оригинал хранит только seed, состояние RNG в SaveData не входит. У DuelEngine состояние спрятано внутри System.Random. Поэтому нам стоит хранить именно состояние PRNG: так будет лучше, чем у обоих.
   benefit: Партию и баг можно воспроизвести по seed и журналу команд. Тесты задают seed, а не подменяют глобальный Math.random (s06:194-196). Основа для AI-01, AI-09 и AI-11.
   cost: S. Утилита PRNG (mulberry32 или xoshiro128) с состоянием в metadata.rng. Заменить 5 вызовов: deck-management.service.ts:33,192; card-effect-executor.service.ts:1383,1446; game-initialization.service.ts:51. Seed выдаётся при создании игры через crypto. Добавить ключ в короткую сериализацию game-state | risk: Состояние RNG раскрывает будущие перетасовки, то есть скрытый порядок колоды. Его обязательно вырезать в filterPrivateData (game-state.service.ts:828) и в журнале для клиентов. Меняется формат снапшот
   VERIFY=confirmed: Все пять вызовов Math.random в движке подтверждены; game.service.ts:228 — это код приглашения, к движку он не относится. ID карт, pending и сайдкиков детерминированы, недетерминизм дают только Math.random и Date. Две поправки к доказательствам. (1) Seed оригинала лежит в MatchInitData.randomSeed (MatchInitData.cs:93), а не в SaveData: в SaveData нет ни seed, ни состояния RNG, поэтому ссылка SaveData.cs:32-54 подтверждает только отсутствие. (2) Пропущено разделение потоков. У Match оригинала две отдельные RNG: Random (CanisRandom, игровые перетасовки) и SelectionRandom (System.Random). Шум ИИ с
   ev: backend/src/game-engine/services/deck-management.service.ts:33;backend/src/game-engine/services/deck-management.service.ts:192;backend/src/game-engine/effects/card-effect-executor.service.ts:1383;backend/src/game-engine/effects/card-effect-executor.service.ts:1446;backend/src/games/services/game-ini
- [AI-03] P1 | adapt | src=original | ИИ не должен молча вставать: запасной легальный ответ и сторож прогресса
   why: В оригинале у каждого выбора есть запасной случайный ответ PlayerEntity.DefaultRandomChoice. У нас decide возвращает null на своём обязательном выборе (ai-decision.service.ts:64-70). Если executor отверг ход ИИ, runOneStep тихо останавливается (ai-turn.service.ts:204,209-212). Таймера хода вне боя нет, поэтому матч VS_AI повисает навсегда. Комментарии ai-decision.service.ts:246-248 и ai-decision.service.spec.ts:208 показывают, что такие зависания уже случались.
   benefit: Партия VS_AI всегда доходит до конца. Каждый откат к запасному ходу логируется (строка AI_FALLBACK в трейсе) и считается в AI-01 как дефект политики.
   cost: S–M. В ai-turn.service.ts: если decide вернул null, а голова очереди, pendingManeuver или ход принадлежат боту, либо executor вернул отказ, — перебрать кандидатов (сначала простые для каждого типа PendingEffect, потом перечислитель из AI-04) и принять первого, которого executor исполнит успешно. Кан | risk: Запасной ход маскирует ошибки политики. Поэтому нужно громкое логирование и счётчик в харнессе, а в CI отказ разрешать только при нулевом числе откатов на эталонных seed.
   VERIFY=weakened: Дыра есть: если decide возвращает null или executor отверг ход, runOneStep просто возвращает false. Таймера вне боя нет, а GameSanityService чистит только PENDING-игры. Но судья не учёл три уже работающих механизма, которые сужают зону зависаний. (1) Сервер сам выкидывает из головы очереди выборы без легальной цели (pruneHeadPendingsWithoutTargets) и применяет нулевой шаг, когда «остаться на месте» — единственный ответ. (2) Переподключение (подписка gameStateUpdated) заново запускает дрейн бота, и CombatTimeoutService после авторезолва — тоже. (3) Зависание в бою ограничено таймером защиты/рез
   ev: backend/src/game-engine/services/ai-decision.service.ts:64-70;backend/src/game-engine/services/ai-decision.service.ts:246-248;backend/src/game-engine/services/ai-decision.service.spec.ts:208;backend/src/games/services/ai-turn.service.ts:186-189;backend/src/games/services/ai-turn.service.ts:204-212;b
- [AI-04] P2 | adapt | src=both | Общий перечислитель легальных команд для ИИ, фазза и Game Tester
   why: В оригинале движок сам выдаёт дерево допустимых целей (SelectionWithTargetsRequired.TargetMap), и на него одинаково отвечают человек, ИИ и сеть. В DuelEngine перечень кандидатов общий для сервера и ИИ (ScoringPlayer.EnumerateCandidates). У нас ИИ сам перебирает варианты по своей логике, частично импортируя помощники валидатора (bannerAllows, isCellPassable). Общий перечислитель есть только для очереди выборов (pendingHasValidTarget).
   benefit: Случайная политика для фазза, запасной ход для AI-03 и кандидаты для оценщиков AI-05 берутся из одного источника. Новый тип выбора сразу становится доступен ИИ. ИИ физически не может предложить незаконный ход, потому что каждого кандидата проверяет валидатор.
   cost: L. Функция enumerateLegalCommands(state, playerId) в game-engine. Её ветки: голова pendingEffects по 8 типам, attack (боец × цель × карта с проверкой баннера), beginManeuver, maneuver (буст × клетки назначения каждого бойца через AdjacencyService.getReachableCells и canonical-path.ts), playScheme, d | risk: Комбинаторный взрыв в манёвре: перечислять клетки назначения, а не пути, и ограничивать выборку. Логика может задвоиться с валидатором: кандидаты должны проходить через валидатор, а не дублировать пра
   VERIFY=weakened: Общего перечислителя легальных команд действительно нет, и у сервера нет API легальных целей. Но многие блоки уже есть и разделены с валидатором, поэтому оценка L завышена, реалистично M. Для движения есть computeReach, reachableEndpoints, canonicalPath и reachTiers; property-тест доказывает, что они эквивалентны validateManeuver на Marmoreal и Sarpedon. Для MOVE/PLACE есть pendingCandidates и hasDestination, для атаки — bannerAllows. Риск комбинаторного взрыва в манёвре уже снят: reachableEndpoints перечисляет конечные клетки, а не пути. Поправка про оригинал: SelectionWithTargetsRequired нес
   ev: backend/src/game-engine/effects/pending-targets.ts:64;backend/src/game-engine/effects/pending-targets.ts:89;backend/src/game-engine/services/ai-decision.service.ts:7;backend/src/game-engine/engine/adjacency.service.ts:117;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Networking/Networking/se
- [AI-05] P2 | adapt | src=original | Оценщики по типам решений, объяснимые оценки, веса в JSON, уровни сложности с мультипликативным шумом
   why: ИИ оригинала — промышленная проверенная схема:
- оценщик на каждый тип выбора;
- функции GetValueFor* суммируются в AIValueSummer с причинами;
- константы уровня берутся из JSON, к ним добавляется шум InjectNoise;
- «часы гонки» учитывают истощение (ExhaustDamagePerTurn=2).
В DE есть выбор AI DIFFICULTY. Наш ИИ не играет схемы, не двигает сайдкиков, не бустит манёвр, а уровней у него нет. 210 рукописных классов под конкретные карты оригинала не масштабируются на 84 героя. Поэтому ценность карты надо выводить из нашего разобранного CardEffect (типы и значения), а не писать вручную.
   benefit: Бот заметно сильнее и разнообразнее. В соло появляется выбор сложности, как в DE. В Game Tester и трейсе видно, почему бот выбрал ход (разбор по причинам). Баги ИИ можно отлаживать без отладчика.
   cost: L. Разбить ai-decision.service.ts на оценщики по решениям: ход, атака (карта и цель), защита, манёвр (клетка и буст), схема, каждый тип pending. Каждый возвращает {total, reasons[]}. Веса хранить в backend/src/game-engine/ai/constants-{0,1,2}.json со своими именами и значениями; DuelAIConstants служ | risk: Большой рефакторинг рабочего ИИ: возможны регрессии, их ловят AI-01 и AI-09. Нужно время на подбор весов. Брать числа DuelAIConstants как есть сомнительно с точки зрения IP: лучше подобрать свои self-
   VERIFY=weakened: Направление верное, но стоимость упакована неверно, и два довода стоит уточнить. (1) Уровни сложности DE дешёвые: DuelAIConstants-0 и -1 переопределяют только 6 ключей (AverageCardValue, DamageHeroValue, DamageSidekickValue, HeroDefeatValue, LowHealthFactor, SelectionNoiseMin), а полный набор из 180 есть только у уровня 2. Значит, выбор сложности (шум плюс 5 весов) можно добавить в текущую жадную политику за S, отдельно от рефакторинга оценщиков (L). (2) Довод «210 рукописных классов не масштабируются» подтверждает сам оригинал. Эти 210 файлов есть только у 14 героев (+ Shared), то есть у тех 
   ev: backend/src/game-engine/services/ai-decision.service.ts:19-34;backend/src/game-engine/services/ai-decision.service.ts:49-57;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/ai/evaluators;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/ai/valuati
- [AI-06] P2 | adapt | src=original | Быстрые доработки текущей жадной политики (до AI-05 или вместо него)
   why: Оценщики оригинала (ManeuverEvaluator, BoostAttackEvaluator, ChooseWorstCardEvaluator, DiscardEvaluator, ChooseFighterToMoveEvaluator) показывают, какие решения ИИ обязан принимать. У нас нет схем (в core-наборе DE это 40 из 189 карт), буста манёвра, хода и атак сайдкиков, а при лимите руки сбрасываются первые N карт.
   benefit: Заметно сильнее бот VS_AI за небольшую цену, без переписывания архитектуры. Эффект можно измерить винрейтом против старой политики в AI-01.
   cost: S. Добавить в AiAction вид playScheme; выставлять boostCardId в манёвре, если клетка-цель недостижима без буста; двигать и атаковать сайдкиками; в discardToLimit выбирать карты с минимальной ценностью вместо slice(0, count). | risk: Эвристики на глаз могут ухудшить игру, поэтому нужен замер в AI-01. Схемы с эффектами UNSUPPORTED сыграются впустую.
   VERIFY=confirmed: Всё подтверждено. В AiAction нет playScheme, хотя executor поддерживает схему. boostCardId не задаётся. Манёвр и атака идут только героем. discardToLimit делает slice(0, count). Стоимость S реальна: эвристика «сбросить худшую карту» уже написана внутри decidePending для DISCARD_CARDS (сортировка по boostValue), её можно переиспользовать. Уточнение: 40 из 189 — это уникальные карты 14 извлечённых героев DE, а не «core-набор» и не число копий в колодах.
   ev: backend/src/game-engine/services/ai-decision.service.ts:19-34;backend/src/game-engine/services/ai-decision.service.ts:43-57;backend/src/game-engine/services/ai-decision.service.ts:99-113;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/ai/evaluators;DuelEngine-transfer/tes
- [AI-07] P3 | adapt | src=duel-engine | ИИ на симуляции (клон → доигрывание → оценка, общие случайные числа)
   why: В DuelEngine L2 на симуляции разносит жадную политику (364:0). Но доска там из 8 клеток, правила неверные, и ИИ подглядывает в руку соперника. Оригинал выпустил только жадный ИИ (SimulationEntity не используется), и этого DE хватило. Наше состояние неизменяемое, executor не делает I/O, так что клон бесплатный. Но доигрывание идёт через async executor (56 await), а честный вариант требует детерминизации скрытых карт из проекции.
   benefit: Потенциально самый сильный уровень сложности. Он понадобится, только если после AI-05 бот окажется слишком слабым.
   cost: L–XL. Нужны AI-02, AI-04 и AI-05 (политика доигрывания). Детерминизация руки и колоды соперника из неизвестного пула через filterPrivateData; бюджет времени на решение (аналог BestRankTimeout; в DE около 3,5 с на решение). | risk: Нагрузка CPU на однопоточный Node при нескольких матчах VS_AI. Задержка ходов бота. Если сделать нечестную реализацию, бот получит доступ к руке и колоде соперника.
   VERIFY=weakened: Отсутствие симуляции в оригинале подтверждено: SimulationEntity и SimulationLookup не встречаются в ISIL нигде, кроме собственных файлов и EntityHierarchyExtensions. OnClearUndo в DuelAIStrategy только чистит кэши. Неверно другое: «около 3,5 с на решение» нельзя считать бюджетом вычислений. В оригинале есть отдельное сообщение AIDelayEffect (и Delay(AIDelayEffect)), то есть пауза бота — это намеренная подача, а при жадной оценке вычисления дешёвые. Ориентир бюджета вычислений — BestRankTimeout с timeout=1000 по умолчанию. Остальное (await в executor 56 раз, нужна детерминизация скрытых карт) п
   ev: DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/AI/ScoringPlayer.cs:6-33;DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Core/StateClone.cs:74-75;C:/Users/ren/AppData/Local/Temp/claude/C--Users-ren-WebstormProjects-unmached-unmached/2b6a7e70-a9a9-4f0e-bd48-9f26a5894d1b/
- [AI-08] P2 | adapt | src=original | Честность ИИ на уровне структуры: решать по проекции filterPrivateData
   why: Оригинал ведёт модель известных карт (UpdateKnownHand, KnownHandArchetypesOf) и вероятностные оценки руки соперника (ChanceInHandMatches). DuelEngine — антипример: L2 оценивает позицию по открытым картам. Наш ИИ сейчас честен только по дисциплине: decide получает полное состояние (ai-turn.service.ts:200-203). Как только ИИ станет умнее (AI-05, AI-07), утечку будет легко внести незаметно.
   benefit: Гарантия, что бот не видит руку и колоду человека. Её проверяет тест, а не код-ревью.
   cost: S. В runOneStep передавать в decide stateService.filterPrivateData(state, aiUserId), а executor продолжает работать с полным состоянием. Плюс тест: изменение скрытых карт соперника не меняет решение. | risk: Проекция может срезать поля, нужные ИИ (pending.revealedCards для DECK_TOP_PICK и т. п.), — это проверяется существующими 42 спеками decide.
   VERIFY=confirmed: Подтверждено: decide получает полное состояние, полученное из loadState. Проекция filterPrivateData оставляет боту всё, что он использует: свою руку, revealedCards своего DECK_TOP_PICK, optionEffects, combatInfo. Удаляет она только серверные очереди (combatEffectContinuation, combatResolutionProgress), которые decide не читает. Нынешний жадный ИИ руку соперника и так не смотрит, поэтому польза профилактическая, как судья и пишет.
   ev: backend/src/games/services/ai-turn.service.ts:200-203;backend/src/games/game-state.service.ts:828;backend/src/game-engine/services/ai-decision.service.ts:277-279;DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/ai/DuelAICombatExtensions.txt:4041;DuelEngine-transfer/test-ta
- [AI-09] P2 | adapt | src=duel-engine | Турниры self-play и телеметрия баланса и покрытия: метрики по снимкам, а не по журналу
   why: Сама идея DuelEngine — round-robin героев с винрейтами и средней длиной партии — полезна. Исполнение неудачное: 13 матчей на пару дают шум; урон по сайдкику записан как урон по герою (Telemetry.cs:66); бусты считаются по стороне (Telemetry.cs:81); вложенные доборы теряются; JSON невалидный. Способности реализованы у 29 из примерно 84 героев, поэтому наши винрейты сначала будут мерить полноту реализации, а не баланс. Главная практическая ценность — карта покрытия.
   benefit: Автоматическая карта неисполненных эффектов (manualEffects и UNSUPPORTED) по героям и картам. Это отвечает на открытый вопрос о покрытии парсера по 880 картам. Плюс преимущество первого хода (у нас всегда начинает seat 0), длина партий, доля урона от истощения, частота откатов к запасному ходу и зав
   cost: M поверх AI-01. Обе рассадки, не меньше 200 матчей на пару (95% интервал около ±7%). Метрики считать по разнице соседних снимков (HP по бойцу и владельцу, размеры колоды и руки) и по manualEffects из результатов executor. Отчёт JSON с доверительными интервалами в docs/game-design/evidence/. | risk: Цифры легко принять за реальный баланс, хотя ИИ слабый, а способности неполные: в отчёте нужна явная пометка. Прогон долгий, поэтому его не стоит включать в обязательные гейты.
   VERIFY=weakened: Ошибки телеметрии DuelEngine подтверждены (Telemetry.cs:66 — весь урон записан как урон по герою; :81 — бусты по роли AttackerSide, а не по игроку; JSON отчёта невалиден из-за культуры в ToString). ±7% при 200 матчах на пару верно (1,96·√(0,25/200)≈6,9%). Но завышена польза «карты покрытия». (1) Статическое покрытие парсера по героям уже меряет prisma/backfill-card-effects.ts --dry-run (отчёт unsupportedCards по героям); нужна только БД или сид. Self-play покажет лишь карты, которые реально сыграли. (2) UNSUPPORTED уже пишется warn-логом с cardId, и по нему растёт метрика unsupported-effect. У
   ev: DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Core/Telemetry.cs:66;DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Core/Telemetry.cs:81;DuelEngine-transfer/duel-engine/UnityProject/Assets/Editor/TournamentTests.cs:145;DuelEngine-transfer/duel-engine/docs/tournament-re
- [AI-10] P3 | skip | src=original | Офлайн-подбор весов ИИ на self-play (по образцу AIConstantsVector и IsOptimization)
   why: В оригинале есть заготовка (CloneWithReplacementAt, DiffString, опции IsOptimization и Headless), но раннера подбора в клиенте нет. У нас пока нет ни таблицы весов (AI-05), ни харнесса (AI-01). Без них подбор — работа ради красоты.
   benefit: Свои, а не заимствованные значения весов, подобранные под наш контент.
   cost: M, но только после AI-01 и AI-05: покоординатный подбор с оценкой винрейтом против эталона. | risk: Переобучение под слабого соперника. Долгие прогоны.
   VERIFY=confirmed: Подтверждено: в Canis/ai_sim лежит только AIConstantsVector (CloneWithReplacementAt, CloneWithReplacements, DiffString), раннера подбора в клиенте нет. Skip до AI-01 и AI-05 обоснован.
   ev: DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Canis/ai_sim/AIConstantsVector`1.cs:32-36;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Canis/canis/data/TCGameOptions.cs:8-10
- [AI-11] P2 | adapt | src=duel-engine | Золотые детерминированные партии на реальных картах (seed, команды, хеш состояния) вместо s06 на Cobble
   why: Запуск DuelEngine показал: повтор по (seed, ответы) надёжен, а повтор по журналу эффектов (ActionLog) — нет (0/120), потому что фазы меняются в обход журнала. Наш s06 проходит на выведенной Cobble, что нарушает правило «только реальные доски», и детерминизм там держится на подмене Math.random.
   benefit: Дешёвый быстрый регрессионный гейт: любое непреднамеренное изменение правил видно по хешу. Соответствует правилу проекта о реальных картах.
   cost: S после AI-02. 4–6 seed на Marmoreal и Sarpedon, пары Medusa/Arthur и ещё 2–3 героя; хранить список команд и хеш итогового состояния без временных меток (lastActionAt и timestamp — около 79 мест с Date в game-engine). Повтор строить по журналу команд, а не по эффектам. | risk: Каждое намеренное изменение правил меняет хеш, поэтому нужен удобный режим перезаписи эталона с выводом диффа.
   VERIFY=weakened: Суть верна: s06 идёт на Cobble с подменой Math.random, Date в game-engine встречается 79 раз, повтор по журналу эффектов в DuelEngine не работает (0/120). Упущено, что журнал команд у нас уже есть. GameAction с metadata.input пишется и для человека, и для бота, а ReplayService собирает повтор из этого журнала. После AI-02 (seed) золотые партии и воспроизведение реальных продакшн-игр строятся на существующем журнале — новый формат команд не нужен. Перенос на реальные доски дёшев: marmorealBoardRow() уже есть, а s09 его импортирует.
   ev: backend/src/games/services/s06-full-games.spec.ts:7;backend/src/games/services/s06-full-games.spec.ts:22-24;C:/Users/ren/AppData/Local/Temp/claude/C--Users-ren-WebstormProjects-unmached-unmached/2b6a7e70-a9a9-4f0e-bd48-9f26a5894d1b/scratchpad/duel-run/out/harness-all.log;DuelEngine-transfer/duel-eng
- [AI-12] P3 | skip | src=duel-engine | Перенос кода DuelEngine (ScoringPlayer, ValuationPlayer, Telemetry, TournamentTests, MatchReport, SmokeTest)
   why: Код на C#/Unity под линейную доску из 8 клеток и ошибочные правила. ИИ подглядывает в скрытые карты. Из 180 констант используются 5. В телеметрии ошибки подсчёта. «Детерминизм» в тестах — сверка счётчиков. Брать стоит только приёмы: AI-01, AI-02, AI-09, AI-11.
   benefit: Нет.
   cost: — | risk: При переносе перенеслись бы ошибочные правила и подглядывание.
   VERIFY=confirmed: Подтверждено: доска — линия из 8 зон (AreAdjacent как |a−b|=1, ZoneGroup=zone/3). Клон копирует руку и колоду соперника. В LevelProfile 5 полей из 180 констант. Тест «детерминизма» сверяет только ActionLog.Count и Winner.
   ev: DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/AI/ScoringPlayer.cs:97-102;DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Core/Board.cs:19-38;DuelEngine-transfer/duel-engine/UnityProject/Assets/Editor/TournamentTests.cs:105-108;DuelEngine-transfer/duel-engine/UnityProj
- [AI-13] P3 | keep-ours | src=both | Оставить: ИИ ходит теми же мутациями executor и тем же протоколом выборов, что и человек
   why: Это совпадает с принципом оригинала, где MakeChoice возвращает тот же тип ответа, что и человек. У нас dispatchAiAction зовёт продакшн-executor и журналирует так же, как ручной путь. Менять нечего, работа сводится к AI-03, AI-04 и AI-08.
   benefit: Нет отдельного «пути бота» с собственными правилами. Харнесс переиспользует dispatchAiAction.
   cost: — | risk: Нет.
   VERIFY=confirmed: Подтверждено: dispatchAiAction вызывает те же методы executor и журналирует в той же форме, что ручной путь. Это соответствует MakeChoice(SelectionMessage) в оригинале.
   ev: backend/src/games/services/ai-turn.service.ts:24-153;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/Canis/canis/entities/ai/AIProfileAbs.cs:154
- [AI-14] P3 | adapt | src=none | Game Tester: «бот за P2», автоигра N шагов с seed, экспорт репро
   why: Сейчас Game Tester — ручная консоль для двух аккаунтов. При отладке ИИ и зависаний полезно в один клик запустить бота и выгрузить seed и команды, чтобы воспроизвести в AI-01 или AI-11. После AI-05 можно показывать разбор оценок.
   benefit: Ручное репро багов ИИ быстрее. Одна и та же репро-цепочка работает в админке и в харнессе.
   cost: S–M. Админ-мутация шага ИИ за выбранный слот (через AiDecisionService и dispatchAiAction) и кнопка экспорта. | risk: Админ-мутация, которая ходит за игрока, должна быть закрыта ролью admin.
   VERIFY=confirmed: Подтверждено: Game Tester — ручная консоль на два аккаунта с актором auto или P1/P2. Бота, автоигры и экспорта нет, режим VS_AI в Game Tester не используется. Стоимость S–M реальна, потому что dispatchAiAction уже вынесен.
   ev: admin/src/pages/game-tester/GameTester.tsx:1-7;admin/src/pages/game-tester/GameTester.tsx:426-431;backend/src/games/services/ai-turn.service.ts:29-33
- [AI-15] P3 | adapt | src=original | Живая статистика героев из реальных партий: SQL-представление, а не своя аналитика
   why: В оригинале собственная аналитика (HTTP пачками), но нам такой конвейер не нужен. У нас updateHeroStats мёртв (зарегистрирован, но не вызывается), при финише пишутся только ELO и победы пользователя. Данные для винрейта героев уже есть: Game.winnerId и GamePlayer.heroId.
   benefit: Реальные винрейты и пики героев в админке без нового кода сбора.
   cost: S. Запрос или вью в админке по FINISHED-играм. Мёртвый StatsAggregatorService.updateHeroStats либо удалить, либо подключить в applyFinishStats. | risk: Мало реальных партий, поэтому статистика долго остаётся шумной.
   VERIFY=confirmed: Подтверждено и даже сильнее. Мёртвых updateHeroStats два: StatsAggregatorService.updateHeroStats и UserStatsService.updateHeroStats (JSONB heroStats); ни один не вызывается. Для SQL-винрейтов есть Game.winnerId, Game.mode и GamePlayer.heroId.
   ev: backend/src/games/games.module.ts:117;backend/src/games/services/stats-aggregator.service.ts:135;backend/src/games/game-state.service.ts:236-246;backend/prisma/schema.prisma:214;backend/prisma/schema.prisma:251
- RULE [RD-AI-1] high | Пустая колода (истощение)
   orig: За каждую недобранную карту каждый активный боец получает 2 урона. Сброс в колоду не замешивается. ИИ учитывает это в часах гонки (ExhaustDamagePerTurn=2).
   ours: Совпадает с оригиналом: 2 урона каждому живому бойцу за недобор, без замешивания.
   duel: Урона нет, сброс замешивается. Отсюда бесконечные партии: Jekyll против Ashka — 788 ходов и 0 атак. Данные о длине партий и балансе недостоверны.
   VERIFY=confirmed: Подтверждено. У нас за каждый недобор 2 урона каждому живому бойцу владельца, сброс не замешивается. В оригинале на недобор пишется счётчик exhausted_draw и создаётся Damage, а ExhaustDamagePerTurn=2. В DuelEngine сброс замешивается обратно, урона нет.
   ev: DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/actions/Draw_NestedType__execute_d__10.txt:1552;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/DuelAIClockExtensions.cs:21;backend/src/game-engine/services/deck-management.service.ts:73-85;DuelEngine-transf
- RULE [RD-AI-2] high | Буст в бою
   orig: Общего шага бустов в бою нет. Буст атаки бывает только по тексту карты (BoostAttackAbility у Second Shot и Noble Sacrifice) и у пассивки Артура (Conviction). Любой картой бустится только манёвр.
   ours: Совпадает: BOOST_CHOICE возникает только от эффекта карты, буст манёвра — одной картой.
   duel: Обе стороны бустят бой любым числом любых карт. В образце телеметрии 11 бустов за 5 ходов. Сила ИИ и винрейты получены на другой игре.
   VERIFY=confirmed: Подтверждено. У нас BOOST_CHOICE создаётся только эффектом карты, плюс отдельное разрешение буста атаки по способности Артура. В DuelEngine BoostOptions предлагает любые некоммитнутые карты руки обеим сторонам.
   ev: DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/scripts/fighters/ConvictionBoostScript.txt;backend/src/game-engine/services/game-action-executor.service.ts:611-616;DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Core/Engine.cs:1447-1466;DuelEngine-transfer/
- RULE [RD-AI-3] high | Добор в начале хода
   orig: Добора нет. В InitializeTurn по ISIL #198 стоит TotalActions=2, вызовов Draw нет. Карты приходят из манёвра и эффектов.
   ours: Совпадает: передача хода карт не добирает.
   duel: Добирает 2 карты в начале каждого хода. Поток карт и ценность манёвра искажены, а вместе с ними и оценки ИИ и баланс.
   VERIFY=confirmed: Подтверждено с оговоркой. В ISIL InitializeTurn нет ни одного вызова Draw (grep даёт 0); атрибут DuelAttributes ставится в 2 через ChangeAttribute. То, что это именно TotalActions, выведено по смещению, уверенность средняя. Наш переход хода карт не добирает. DuelEngine вызывает DrawCardsAction(Player, 2) в начале хода.
   ev: DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/actions/phase/BeginPlayerTurn_NestedType__InitializeTurn_d__5.txt:1694-1703;backend/src/game-engine/services/game-action-executor.service.ts:312;DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Core/Actions.cs:
- RULE [RD-AI-4] medium | Схема как действие
   orig: Схема — одно из 2 действий хода, ActionsTaken для неё растёт так же, как для манёвра и атаки.
   ours: Совпадает: схема тратит действие.
   duel: Схема бесплатная, одна за ход, до или после действия. Экономика действий в self-play иная.
   VERIFY=confirmed: Подтверждено. У нас playScheme вызывает consumeAction. В DuelEngine SchemePhase отдельна от действий и ограничена флагом SchemePlayedThisTurn. В InitiateAction оригинала рядом стоят ActionsTaken и IsSchemeCard (уверенность средняя).
   ev: DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/actions/phase/InitiateAction_NestedType__execute_d__1.txt:1895;backend/src/game-engine/services/game-action-executor.service.ts:2439;DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Core/Engine.cs:236
- RULE [RD-AI-5] medium | Поле и движение
   orig: Поле — граф клеток с зонами-цветами. На клетке один боец, враги блокируют путь. Около 40 позиционных констант ИИ (ManeuverSurround*, RangedCoverage*, Position*) рассчитаны на такой граф.
   ours: Совпадает: реальные графы Marmoreal и Sarpedon, через врага пройти нельзя, клетка назначения свободна.
   duel: Линия из 8 зон, в одной зоне стоят до 7 бойцов, проход сквозь врагов свободен. Позиционная часть ИИ на таком поле не проверяется.
   VERIFY=confirmed: Подтверждено. В traversal.ts живой враг блокирует промежуточную клетку, а конечная клетка должна быть свободна. В DuelEngine 8 зон на линии, и в зоне до 7 бойцов (maxZoneOccupancy=7 в summary.txt).
   ev: DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/entities/DuelSpaceExtensions.cs:23;backend/src/game-engine/movement/traversal.ts:1-10;DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Core/Board.cs:19-38;C:/Users/ren/AppData/Local/Temp/claude/C--Users-ren-Web
- VERIFY-EXTRA [OS-tests] refuted: Пункты ourState «Чего нет: проверки инвариантов на каждом шаге» и «property-тест движения, 500 состояний на Cobble» неверны. В s09-card-instance-dup.spec.ts 60 полных сидированных дуэлей, и инварианты (сохранение карт, уникальность instance id, одна зона на карту) проверяются после каждой мутации. Property-тест движения идёт на Cobble 5×6, Marmoreal, Sarpedon и сетке 7×7 со стенами. Верно только т
- VERIFY-EXTRA [OS-telemetry] weakened: Фраза «manualEffects никто не собирает» неточна: каждое исполнение UNSUPPORTED пишет warn с effectId и cardId и увеличивает метрику CardEffectExecutor/unsupported-effect. Верно, что нет агрегации по картам и героям. «Покрытие парсера не измерено» тоже неточно: инструмент есть (backfill-card-effects.ts --dry-run выдаёт отчёт по героям), его просто не запускали без БД.
- VERIFY-EXTRA [OS-replay] weakened: «Seed нет, поэтому партию воспроизвести нельзя» верно только для повторной симуляции. Журнал команд (GameAction с metadata.input) и ReplayService уже есть: просмотр повтора по журналу работает. Без seed невозможно лишь переисполнение перетасовок.
MISSED: Готовый харнесс с инвариантами на каждом шаге уже есть: s09-card-instance-dup.spec.ts (60 сидов, реальные колоды Medusa/Arthur, продакшн-executor через s03Engine). Это лучшая стартовая точка для AI-01, а не ai-turn.service.spec.ts с доской 12×2. || Проводка способностей в харнессах: HeroAbilityRegistry по умолчанию пуст, а s03Engine и buildStack из s10 не регистрируют ABILITY_CONFIGS и обработчики arthur, daredevil, ms-marvel (это делает только GameEngineModule.onModuleInit). Self-play без повторения этой проводки проверит игру без способностей героев (backend/src/test/fixtures/s03-engine.fixture.ts:36-46; ai-turn.service.spec.ts:72-77). || Сервер уже страхует очередь выборов: pruneHeadPendingsWithoutTargets выкидывает выборы без легальной цели, нулевой шаг применяется автоматически, переподключение (gameStateUpdated) и авторезолв боя заново запускают дрейн бота. AI-03 нужен только для детерминированного null или отказа executor вне боя (pending-targets.ts:60-75; game-subscription.resolver.ts:346-350; combat-timeout.service.ts:504-51 || Оригинал разделяет игровой RNG (Match.Random, CanisRandom) и RNG выбора (Match.SelectionRandom, System.Random). Шум ИИ не должен сдвигать перетасовки, иначе смена уровня или политики ломает золотые seed (Match.cs:1463-1465). Seed оригинала лежит в MatchInitData.randomSeed (MatchInitData.cs:93), а не в SaveData. || Уровни сложности DE дешёвые: уровни 0 и 1 переопределяют лишь 6 констант (шум плюс 5 весов) поверх полного набора уровня 2. Выбор сложности можно добавить к нынешнему жадному боту за S, не дожидаясь рефакторинга AI-05 (docs/original-ai/DuelAIConstants-0/1/2.json). || В оригинале есть общий запасной путь оценки (FallbackCombatEffectValue, FallbackModifyPositionValue, FallbackAIStrategy, FallbackAIValuationFunction). Рукописные AI-классы есть только у 14 из 30 папок героев. Это прямой аналог предложения выводить ценность из CardEffect (уверенность средняя). || Телеметрия матча в оригинале — счётчики прямо в действиях движка (UpsertAdditionalReports: combat_damage_dealt/received, exhausted_draw, SpacesMoved, unmoved_maneuver, unmoved_boosted_maneuver, could_attack, not_attacked_choice). Вместе с AbilityUsage, AILevel, StartedAsAI и ReplacedByAI они уходят в DBGGameResultsEntry. Это дешёвый и точный по атрибуции способ для AI-09 и AI-15, а пары could_atta || DE заменяет ушедшего игрока ИИ (DBGGameResultsEntry.ReplacedByAI) и даёт выбрать TIMER при создании игры (DBGGameOptions.Timers; docs/game-design/de-footage/README.md:73). Отсутствие таймера хода вне боя — проблема и для PvP, не только для VS_AI. || Пауза бота в DE — отдельный эффект AIDelayEffect, то есть подача, а не вычисления. Наш бот ходит мгновенно; есть ли темп ходов бота в UE-клиенте, я не проверял (уверенность низкая). || Журнал команд с metadata.input и ReplayService уже есть. Вместе с AI-02 это даёт воспроизведение любых продакшн-партий и экспорт репро для AI-14 без нового формата. || Инструмент статического покрытия парсера (prisma/backfill-card-effects.ts --dry-run) и метрика unsupported-effect уже есть. Карта покрытия не требует self-play; self-play добавит только покрытие сыгранных карт. || В оригинале есть AIInfiniteLoopException и RandomPromptCounts — защита от зацикливания ИИ и счёт откатов к запасному ходу по типам выбора. Это готовый образец для логирования AI_FALLBACK в AI-03 и AI-01.

######## DIM data-rules — Данные карт/героев и корректность правил
SUMMARY: **Вердикт по измерению:** импортёр данных из DE не нужен, движок и правила оставляем наши. Из оригинала берём точечные исправления данных и тексты как эталон для сверки.

**Данные.** Числа DE извлечены точно, но покрывают только 14 базовых героев (~17% ростера). Русских текстов карт в DE нет, параметров уникальных эффектов тоже. По этим 14 героям наши HP, Move, типы атаки, сайдкики, типы, копии и бусты карт совпадают с DE почти на 100%. Я сам перепроверил, что топология и стартовые клетки Marmoreal и Sarpedon совпадают с оригиналом.

**Подтверждённые ошибки данных:**
- **P0:** What Big Eyes = 2 вместо 3;
- **P0:** баннеры «Allice» и «The Potter». Из-за них validateBanner (warn и разрешить) снимает ограничение по бойцу, и Jabberwock может играть карты Алисы, а Sinbad — карту Porter. Лечится одноразовым идемпотентным fix в fix-card-gaps.ts;
- **P2:** каталожный DTO героя отдаёт movement: 3 жёстко.

Живую БД я не проверял (Docker остановлен), поэтому fix нужен с dry-run.

**Правила.** Базовые правила нашего движка совпадают с оригиналом (ISIL и локализация): 2 действия, добора в начале хода нет, схема — действие, манёвр с добором и бустом, лимит 7, истощение 2, в боевых окнах защитник первый, урон и победитель боя, отмена сбрасывает буст Артура, дальний бой по зонам, блокировка врагами, ничья. DuelEngine в 7 базовых пунктах противоречит оригиналу (RD-12…RD-18), поэтому как эталон он непригоден.

**Расхождения нашего движка, которые нашлись при сверке с текстами DE:**
- **P1:** стойки Alice и Ali. Alice всегда BIG, «Change size» не исполняется, а setStance — бесплатный переключатель без ограничений;
- **P1:** нет «нельзя отменить» (Holmes, Ciri, Winter Soldier, ~8 карт);
- **P1:** Bigfoot и Dracula исполняются принудительно, хотя в тексте «you may». У Дракулы ещё и авто-цель. При пустой колоде это наносит самоурон от истощения;
- **P2/P3:** сброс Ахилла не случайный, сайдкиков нельзя расставить самому, первым всегда ходит seat 0, карты боя уходят в сброс раньше, чем в оригинале;
- **P2:** у 6 из 14 героев DE нет способностей: Beowulf, Invisible Man, Jekyll&Hyde, Little Red, Sinbad, Sherlock.

**Что ещё дёшево взять из DE:**
- тексты abilitydescription примерно 30 героев — для разовой сверки ABILITY_CONFIGS;
- списки AbilityID на карту — как разметку для измерения покрытия effect-text-parser;
- числовой тест-эталон на 14 героев и обе доски, только числа, без кода и текстов DE.
OURS: Контент берётся из скрейпа the-unmatched.club. Цепочка: scraped-data/api/heroes/*.json (88 файлов вместе с наборами) → backend/prisma/seed-scraped.ts → Postgres. Ручные правки лежат в backend/prisma/fix-card-gaps.ts (список VALUE_FIXES, :41-49) и fix-roster-ru.ts.

**Баннер карты.** Это строка Card.bannerName. Сравнение нечёткое: bannerAllows в backend/src/game-engine/validators/game-rules.validator.ts:603-613. Если баннер неизвестен, validateBanner пишет warn и разрешает карту (там же, :569-587). Если в источнике баннера нет, seed подставляет имя героя (seed-scraped.ts:143). В nameRu seed пишет английское имя (seed-scraped.ts:296-297, :341-342).

**Эффекты и способности.** Эффекты карт получаются regex-разбором английского текста (effect-text-parser.ts). Способности героев: 26 слагов в ABILITY_CONFIGS (abilities/ability-config.ts:458+) и 3 ручных обработчика (arthur, daredevil, ms-marvel).

**Доски.** Фикстуры backend/prisma/fixtures/boards/{marmoreal,sarpedon}.topology.json. Я перепроверил их сам скриптом scratchpad/judge/starts.py. Графы изоморфны оригиналу с учётом зон. Стартовые клетки совпадают поштучно:
- Marmoreal: DE 8/14/4/22 = наши M13/M31/M03/M11 для игроков 1/2/3/4;
- Sarpedon: DE 11/29/3/30 = наши S20/S32/S03/S14.

**Базовые правила совпадают с оригиналом (проверено по ISIL и нашему коду):**
- 2 действия за ход (game-state.model.ts:462);
- добора в начале хода нет (game-action-executor.service.ts:312);
- схема тратит действие;
- манёвр: сначала добор 1, затем бу
- [DATA-01] P0 | adopt | src=original | Одноразовый идемпотентный fix трёх подтверждённых ошибок данных
   why: Сверка 14 общих героев с DE дала ~99% совпадения. Реальных ошибок, которые влияют на игру, три:
- What Big Eyes You Have: значение у нас 2, а DE (поле confidence exact; в cards.json `lea edx,[rdi+3]`) и независимый UmDb дают 3;
- баннер «Allice» у 8 карт Alice: bannerAllows его не узнаёт, validateBanner пишет warn и разрешает карту, поэтому Jabberwock может играть карты Алисы;
- «The Potter» у By Fortune and Fate вместо The Porter: Sinbad может играть карту помощника.
   benefit: Восстанавливается правило «карту играет только свой боец» в каждой партии с Alice и Sinbad. У карты Little Red становится верное значение.
   cost: S. Что сделать:
- в fix-card-gaps.ts добавить в VALUE_FIXES запись What Big Eyes = 3;
- добавить новый список BANNER_FIXES: Allice → Alice, The Potter → The Porter. Правка по name+heroName, идемпотентная;
- по желанию — Voyage boost null → 0. На игру это не влияет, движок и так делает `?? 0`. | risk: Живую БД (:5433) не проверял, Docker остановлен: ошибки могли уже поправить через админку. Поэтому скрипт нужен идемпотентный, с dry-run. Стенды клонировать из эталона (tools/db/sync-dev-stands.cjs).
   VERIFY=weakened: Все три ошибки подтверждаются. Но масштаб занижен, а приоритет P0 завышен.
- **Масштаб.** Я проверил весь скрейп тем же правилом bannerAllows. Баннер не совпадает ни с одним бойцом в 47 строках карт у 8 героев, а не у двух:
  - Allice ×8 (Alice);
  - The Potter (Sinbad);
  - Djkstra вместо Dijkstra (Philippa, Spymaster's ruse);
  - «Sea dog» при сайдкике «Seadog» (Blackbeard, Light the fuse);
  - «Jill Trent» при герое «Dr. Jill Trent» (3 карты; играть их может Daisy);
  - «T-Rex» при «T. Rex» (11 карт);
  - «Spider Man» при «Spiderman» (12 карт);
  - Mr. Hyde / Dr. Jekyll (10 карт).
- **Друго
   ev: DuelEngine-transfer/test-targets/unmatched-data/cards-full.json:23296-23313;DuelEngine-transfer/test-targets/unmatched-data/cards.json;.playwright-mcp/cards_database_snapshot.md:2173;scraped-data/api/heroes/little-red.json:306;scraped-data/api/heroes/alice.json:150;scraped-data/api/heroes/sinbad.jso
- [DATA-02] P1 | adapt | src=original | Баннер как проверяемая ссылка на бойца: падать на неизвестном баннере при seed и в тесте
   why: В DE баннер — типизированная ссылка Fighter: ArchetypeID, поэтому опечатка невозможна. У нас баннер — строка с нечётким сравнением и правилом «неизвестное разрешить». Из-за этого опечатки молча снимают правило. Это же происходит с «Dr. Jekyll»/«Mr. Hyde» у героя «Jekyll & Hyde».
   benefit: Ошибки данных такого класса ловятся при сидировании и в CI, а не в партии.
   cost: S. Что сделать:
- в seed-scraped.ts и в отдельном spec пройти все карты и проверить, что bannerAllows(banner) совпадает с героем или одним из его сайдкиков;
- для Jekyll & Hyde завести явный allowlist форм, пока нет трансформации;
- runtime-поведение warn+allow можно оставить как страховку. | risk: На ~880 картах могут найтись ещё опечатки. Это польза, но потребуется разовый разбор.
   VERIFY=confirmed: Рекомендация верна, и моя проверка её усиливает. Предложенная проверка всех карт на этапе seed уже сейчас находит 47 строк у 8 героев (список в DATA-01).

CI-спек стоит разделить на два:
- нормализация bannerAllows: пунктуация, пробелы, суффикс из нескольких слов;
- allowlist реальных опечаток.

ИИ тоже должен пользоваться общей функцией валидации, а не голым bannerAllows. Иначе после исправления данных расхождение человек/ИИ сохранится для «неизвестных» баннеров.

Ранний выход по null-баннеру в seed-scraped.ts:143 в скрейпе ни разу не срабатывает: пустых баннеров нет.
   ev: DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/data/DuelAttributes.cs:39;backend/src/game-engine/validators/game-rules.validator.ts:603-613;backend/prisma/seed-scraped.ts:143;scraped-data/api/heroes/jekyll-hyde.json
- [RULE-01] P1 | adapt | src=original | Поддержать «нельзя отменить»: способность Holmes, Ciri, Winter Soldier и карты «This card's effects cannot be canceled»
   why: В DE есть атрибут карты Uncancellable (DuelAttributes.cs:40) и отдельный скрипт пассивки UncancellableScript для Holmes и Watson. У нас CANCEL_EFFECTS безусловный, а grep по uncancel/cannot be cancel в backend/src пуст. Такие тексты есть в скрейпе 20 файлов: Sherlock, Ciri, Winter Soldier, The Ancient Heirloom, а также карты Blackbeard, Eredin, Loki, Sun Wukong, Houdini, Cloak&Dagger и Jill Trent. Сейчас Feint и подобные карты неверно гасят эти эффекты.
   benefit: Исправляется правило у нескольких героев, которые уже есть в БД.
   cost: M. Что сделать:
- в парсере добавить флаг карты uncancellable: фраза «This card's effects cannot be canceled» и скобочная форма;
- в ABILITY_CONFIGS добавить правило уровня героя: карты своих бойцов нельзя отменить;
- в card-effect-executor при cancelOpposingCard проверять оба условия;
- для Holmes  | risk: Нужно учесть «(This effect cannot be canceled)» внутри одного эффекта (Eredin/Philippa): это частичная неотменяемость. Её можно отложить и пометить UNSUPPORTED.
   VERIFY=weakened: Суть подтверждается: CANCEL_EFFECTS безусловный, проверки на неотменяемость нигде нет. Поправки к деталям:
- **Атрибуция.** «(This effect cannot be canceled)» относится к способности героя Yennefer & Triss (Sorceress of Vengerberg), а не к Eredin или Philippa. В eredin.json и philippa.json этот текст лежит только среди otherSetHeroes.
- **Пропуск.** Не названа карта Yennefer & Triss с текстом «This card's effect cannot be canceled.».
- **Число файлов.** «20 файлов» — это 21 файл, но многие содержат текст героев своего набора. Например, dracula.json, invisible-man.json и jekyll-hyde.json несут 
   ev: DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/data/DuelAttributes.cs:40;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/scripts/fighters/UncancellableScript.cs;DuelEngine-transfer/test-targets/unmatched-data/localization.txt:3197;DuelEngine-t
- [RULE-02] P1 | adapt | src=original | Сделать «you may» и выбор цели у Bigfoot и Dracula
   why: По DE и физическим правилам обе способности необязательные.
- Bigfoot: «you may draw 1 card». В DE у LonerByNatureScript есть кнопка выбора CustomChoice.Button.
- Dracula: «you may deal 1 damage to a fighter adjacent», цель выбирает игрок, подходит любой боец, включая своих Sisters.

У нас обе исполняются принудительно. У Dracula авто-цель — первый враг в порядке state.fighters, и никакой опции. При пустой колоде принудительный добор наносит 2 урона истощения всем своим бойцам: это реальная потеря HP по нашей вине.
   benefit: Правила совпадают с текстом. Исчезает самоурон от истощения, который игрок не выбирал.
   cost: S-M. Что сделать:
- переиспользовать уже работающий шаблон Medusa: optional pending TARGET_FIGHTER (ability-config.ts:727-736);
- для Bigfoot — optional CHOOSE_ONE «добрать или нет»;
- для Dracula — targetScope «any-adjacent» вместо enemy-adjacent, добор только после попадания;
- ИИ: отказываться от | risk: Пауза хода на выборе в начале или конце хода. Механизм deferTurnEnd/pendingEffects это уже поддерживает (executor :259-283).
   VERIFY=confirmed: Дефекты подтверждаются. Поправка к «source: original»: оба расхождения видны из нашего же скрейпа, DE их только подтверждает. specialAbility Bigfoot и Dracula содержат «you may», у Dracula цель — «a fighter adjacent».

Для Dracula это ещё и задокументированное приближение MVP, прямо в описании конфига. Это не находка из DE.

Мелочь: у Bigfoot abilityName — «It's Just Your Imagination», это название карты из его колоды.

Оценка стоимости S-M и путь через optional pending правдоподобны: шаблон Medusa optional TARGET_FIGHTER уже есть.
   ev: DuelEngine-transfer/test-targets/unmatched-data/localization.txt:3193;DuelEngine-transfer/test-targets/unmatched-data/localization.txt:3196;DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/scripts/fighters/LonerByNatureScript.txt;DuelEngine-transfer/test-targets/cpp2il-isi
- [RULE-03] P1 | adapt | src=original | Стойки Alice и Ali: убрать свободный setStance, ввести выбор на старте и эффект «Change size»
   why: Что сейчас:
- мутация setStance разрешена текущему игроку в любой его action-фазе, бесплатно и без ограничений (resolver :589-615; executor :3058-3108). Через API можно переключить Ali в Sting (+2) перед атакой, а Alice — в BIG перед атакой и в SMALL перед концом хода;
- UE и админка setStance не вызывают (grep пуст). На практике Alice всегда BIG (default) и в начале игры не выбирает размер;
- «Change size» на её картах (Drink Me, Eat Me, Mad as a Hatter и др.) парсер не распознаёт, эти тексты не исполняются.

Как по DE и правилам: размер выбирается в начале игры и меняется только эффектами карт (AliceSetupScript, AliceBig/SmallScript, событие PostChangeSize). Ali меняет стойку только после 
   benefit: Alice начинает играть по правилам: теряет постоянные +2 и обретает тактику размера. Закрывается дыра в API.
   cost: M. Что сделать:
- setStance разрешить только в окне «выбор на старте», для героев с флагом startChoice;
- в effect-text-parser добавить тип CHANGE_SIZE (toggle stance);
- в UE — выбор размера при старте Alice. | risk: Затрагивает клиент UE: нужен выбор на старте. Пока его нет, можно оставить default BIG и только закрыть свободное переключение и добавить Change size.
   VERIFY=confirmed: Подтверждается полностью. Поправка только к весу: Alice и Ali нет в UE-ростере (там Arthur и Medusa), поэтому до игрока в UE проблема не доходит. Остаётся API-эксплойт для GraphQL-клиента, который играет Ali или Alice, плюс Game Tester.

Важный нюанс плана: сейчас setStance — единственная задуманная замена «Change size». Закрывать свободное переключение нужно одновременно с CHANGE_SIZE в парсере, иначе Alice лишится смены размера совсем.
   ev: DuelEngine-transfer/test-targets/unmatched-data/localization.txt:3192;DuelEngine-transfer/test-targets/unmatched-data/localization.txt:3219;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/scripts/fighters/AliceSetupScript.cs;backend/src/game-engine/abilities/ability-confi
- [DATA-03] P2 | adapt | src=original | Использовать abilitydescription из DE как одноразовый эталон для сверки ABILITY_CONFIGS
   why: В DE localization.txt:3189-3230 есть английские тексты способностей примерно 30 героев, включая DLC (Achilles, Bloody Mary, Oda, Tomoe, Annie, Golden Bat, Houdini, Tesla и др.).

Выборочная сверка с нашими конфигами:
- совпадают Medusa, Robin Hood, Bruce Lee, Ali, Bloody Mary, Oda, Tomoe, Annie, Golden Bat. Пометку «provisional» у Medusa можно снять;
- расходятся Bigfoot, Dracula (см. RULE-02), Alice (RULE-03) и Achilles: «discard 2 random cards» у нас детерминирован.
   benefit: Дешёвая независимая проверка 26 декларативных конфигов. Список приближений в docs/backend-api/08-heroes-abilities.md получает эталон.
   cost: S. Ручная сверка по чек-листу. Ахиллу дать настоящий random через RNG; после введения seed-RNG (другое измерение) это детерминировано для тестов. | risk: Тексты DE переписаны под цифровую версию, но по смыслу совпадают с печатными. Тексты DE в репозиторий не копировать (IP), только ссылки на ключи.
   VERIFY=weakened: Польза завышена.
- Наши ABILITY_CONFIGS уже написаны по печатному тексту из скрейпа и цитируют его дословно в комментариях. Тексты DE abilitydescription почти совпадают со scraped specialAbility.
- Найденные расхождения уже задокументированы в самих конфигах как «приближение MVP»: Dracula, Achilles, Leonardo. Новой информации DE здесь не даёт.
- Снять «provisional» у Medusa по DE нельзя. Пометка касается имени способности, а в DE есть только ключи abilitydescription: 238 ключей, ни одного ключа имени способности.
- Выборочные совпадения (Robin Hood, Bruce Lee, Bloody Mary, Oda, Tomoe, Annie, G
   ev: DuelEngine-transfer/test-targets/unmatched-data/localization.txt:3189-3230;backend/src/game-engine/abilities/ability-config.ts:458;backend/src/game-engine/abilities/ability-config.ts:824-845;docs/backend-api/08-heroes-abilities.md:242-250
- [DATA-04] P2 | adapt | src=original | Тест-сверка только по числам для 14 героев DE и эталон досок
   why: Тест-оракул из чисел без текстов:
- HP, Move и AttackType героев и сайдкиков;
- value, boost, copies и баннер 189 карт;
- графы и стартовые клетки Marmoreal и Sarpedon.

Он защитит от регрессий при пересидировании и правках в админке. Доски и стартовые клетки я сверил: совпадение полное.
   benefit: Регрессии данных ловятся автоматически. Факт изоморфизма досок фиксируется в тесте, а не в памяти.
   cost: S:
- небольшой JSON-фикстур только с числами (без текстов и кода DE);
- spec, который сверяет его с seed-источником и топологиями;
- Crash Through the Trees исключить: в DE она не извлечена. | risk: IP: в репозиторий кладём только игровые факты-числа, без декомпилированного кода и локализации. Если есть сомнение — держать фикстур вне git.
   VERIFY=confirmed: Я перезапустил scratchpad/judge/starts.py, стартовые клетки совпадают.

Оговорки:
- изоморфизм iso.py получен с подстановкой одной DE-клетки с индексом None;
- в DE есть ещё клетки со StartPlayer=101 и 100, которым у нас соответствуют M15 и S37 без старта. Их смысл не разобран, в фикстур стоит внести с пометкой;
- у Bigfoot в DE 28 копий вместо наших 30 — из-за оборванной Crash Through the Trees.
   ev: DuelEngine-transfer/test-targets/unmatched-data/heroes-stats.json;DuelEngine-transfer/test-targets/unmatched-data/cards-full.json;DuelEngine-transfer/test-targets/unmatched-data/cards-full-summary.txt:17-18;backend/prisma/fixtures/boards/marmoreal.topology.json;backend/prisma/fixtures/boards/sarpedo
- [DATA-05] P2 | adapt | src=original | Списки AbilityID на карту из DE как размеченный набор для регрессии effect-text-parser
   why: В cards-full.json у каждой карты есть список классов способностей. Всего 156 разных, 36 общих: CancelAbility×16, Draw1AfterAbility×10, Gain1Action… Это готовая разметка «что делает карта» для 189 карт. По ней можно измерить, насколько наш парсер распознаёт эти 14 колод: CANCEL_EFFECTS, DRAW AFTER, GAIN_ACTION. Сейчас покрытие парсера не измерено.
   benefit: Появляется цифра покрытия и список нераспознанных карт базовых героев.
   cost: M. Скрипт сопоставления «семейство способности DE ↔ тип CardEffect» для общих семейств. Уникальные способности оставить ручными. | risk: Сопоставление неточное: числа часто зашиты в имя класса, параметры уникальных способностей в данных отсутствуют.
   VERIFY=weakened: Утверждение «покрытие парсера сейчас не измерено» неверно.
- backfill-card-effects.ts --dry-run выдаёт по каждому герою parsed, unsupportedCards и unsupportedTexts.
- В плане зафиксирована метрика «Поднять 240/712» со спекой, которая меряет покрытие до и после.

DE даёт не покрытие, а семантическую разметку: какой тип эффекта у карты. Это проверка правильности, а не полноты распознавания.

Общих семейств немного:
- в Shared/Abilities 36 классов (число верное);
- больше чем на одной карте используется 27 классов из 156;
- больше чем у одного героя — 21.
Выигрыш ограничен 14 колодами.
   ev: DuelEngine-transfer/test-targets/unmatched-data/cards-full.json;DuelEngine-transfer/test-targets/unmatched-data/cards_from_code.txt;backend/src/game-engine/effects/effect-text-parser.ts:1-27
- [RULE-04] P2 | adapt | src=original | Доделать способности героев из ростера DE: Beowulf, Invisible Man, Jekyll&Hyde, Little Red, Sinbad
   why: У 6 из 14 героев DE способностей у нас нет: grep по beowulf/invisible/jekyll/hyde/basket/sinbad в backend/src пуст. boardState.fog и tokens объявлены, но не используются. Sherlock закрывается RULE-01.

В DE для каждого есть отдельный скрипт с понятной семантикой:
- Raging1/2 (ярость Беовульфа, максимум 3);
- InTheMistSetup/1/2 (3 тумана в зоне, +1 к защите, ход между туманами);
- StartTurnChooseBecome и два архетипа DrJekyll/MrHyde;
- корзинка: символ верхней карты сброса, у копий разные символы (BasketItems);
- SevenVoyages (+1 к движению за каждую Voyage в сбросе).
   benefit: Эти герои начинают играть по правилам. Из DE берём только поведение граничных случаев как справку, код не берём.
   cost: L, по герою отдельно. Для Little Red нужна модель символа копии: у нас 3 копии Into the Woods склеены в одну строку с эмодзи. Для Jekyll&Hyde — две формы и баннеры форм. | risk: Продуктовое решение: какие герои нужны и в каком порядке. Не делать «ради полноты».
   VERIFY=confirmed: Подтверждается. Уточнение по Sinbad: в эффектах карт уже есть счётчик VOYAGE по сбросу (CountSource DISCARD_NAME_PREFIX). Не хватает только способности героя: +1 к движению на манёвре за каждую Voyage в сбросе.

У Little Red три копии Into the Woods действительно лежат одной строкой «Into the Woods 🐺🌹⚔️» ×3. В DE это IntotheWoods_A/B/C плюс enum BasketItems (Wolfsbane/Blade/Pelt).

Ни одного из этих героев нет в UE-ростере, так что это вопрос продукта.
   ev: DuelEngine-transfer/test-targets/unmatched-data/localization.txt:3191;DuelEngine-transfer/test-targets/unmatched-data/localization.txt:3199-3202;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/scripts/fighters;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-can
- [DATA-06] P2 | adopt | src=original | Исправить movement: 3 в каталожном DTO героя
   why: prismaHeroToHeroDto и prismaHeroToHeroDefinition жёстко отдают movement 3. DE подтверждает Move 2 у 10 из 14 героев. Партия берёт Move из БД (game-initialization.service.ts:209), экраны UE — из adminHero, поэтому неверное значение видят только потребители content-API.
   benefit: Каталог перестаёт показывать неверное число.
   cost: S: `movement: prismaHero.movement ?? 2` в двух местах. | risk: Нет.
   VERIFY=confirmed: Подтверждается. Поправка к стоимости: Hero.movement — не-nullable Int @default(2), поэтому `?? 2` не нужен, достаточно `prismaHero.movement`.

Партия читает Move из Prisma напрямую, UE — из adminHero. Неверное число видят только content-резолверы (heroes, heroesPaginated, heroBySlug).
   ev: backend/src/content/mappers/content.mapper.ts:94;backend/src/content/mappers/content.mapper.ts:230;backend/src/games/services/game-initialization.service.ts:209;unreal/Unmatched/Source/Unmatched/S08/S08FlowControllerRoom.cpp:22
- [DATA-07] P3 | skip | src=original | Постоянный импортёр unmatched-data в БД
   why: Почему не нужен:
- охват — 14 героев из ~84;
- по ним совпадение и так ~99%;
- у DLC-героев 0 карт;
- нет параметров уникальных эффектов, нет русских текстов карт (ru_RU — 415 строк UI);
- в самом извлечении есть дыра: Crash Through the Trees.

Точечный fix (DATA-01) и тест-эталон (DATA-04) дают ту же пользу дешевле.
   benefit: Не тратим время на импортёр, который почти ничего не добавит.
   cost: 0 | risk: Нет.
   VERIFY=confirmed: Подтверждается:
- в 16 из 30 папок героев DE нет ни одной карты;
- ru_RU.txt — 415 строк интерфейса;
- в localization.txt не-английские строки карт пустые.
   ev: DuelEngine-transfer/test-targets/unmatched-data/cards-full-summary.txt:3-18;DuelEngine-transfer/test-targets/unmatched-data/textassets/ru_RU.txt;DuelEngine-transfer/test-targets/unmatched-data/cards_from_code.txt
- [DATA-08] P3 | skip | src=duel-engine | Генератор контента и правила DuelEngine
   why: Почему не брать:
- generate_real_content.py теряет баннер, пропускает карту, не создаёт MrHyde и анонимизирует имена;
- правила DuelEngine противоречат оригиналу минимум в 8 пунктах (см. ruleDiscrepancies);
- наш движок по этим пунктам уже совпадает с оригиналом.
   benefit: Не вносим ошибки.
   cost: 0 | risk: Нет.
   VERIFY=confirmed: Подтверждается: «Дуэлянт», handLimit 7 и startingHand 5 прошиты в генераторе, ограничения по бойцу нет.
   ev: DuelEngine-transfer/duel-engine/generate_real_content.py:35;DuelEngine-transfer/duel-engine/generate_real_content.py:80;DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Core/Actions.cs:30-41;DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Core/Actions.cs:587;DuelEngine-t
- [RULE-05] P3 | keep-ours | src=both | Базовые правила хода, боя, добора и доски оставить как есть
   why: Проверены по ISIL и локализации DE и совпадают с оригиналом:
- 2 действия, добора в начале хода нет, схема — действие;
- манёвр с добором 1 и бустом;
- лимит 7 в конце хода после end-of-turn хуков;
- стартовая рука 5;
- истощение 2 без замешивания;
- в боевых окнах защитник первый;
- урон и победитель боя;
- отмена сбрасывает буст Артура;
- дальний бой по пересечению зон;
- враги блокируют, на клетке один боец;
- одновременная гибель — ничья;
- топология и стартовые клетки обеих досок.
   benefit: Переписывать ничего не нужно.
   cost: 0 | risk: Нет.
   VERIFY=confirmed: Проверил выборочно, всё совпадает. Порядок окон в DE виден прямо по enum CombatStates: защитник идёт раньше атакующего в Immediate, During и After.
   ev: DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/actions/phase/BeginPlayerTurn_NestedType__InitializeTurn_d__5.txt:1694-1706;DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/actions/Draw_NestedType__execute_d__10.txt:1545-1566;DuelEngine-transfer
- [RULE-06] P3 | adapt | src=original | Расстановка сайдкиков игроком и выбор первого игрока
   why: В DE игрок сам ставит сайдкиков: SetupStates.Setup_Sidekick_SpaceText, «Place [archetype].», а ИИ — через PlaceFighterEvaluator. У нас автоматическая легальная расстановка (GD-016), и первым всегда ходит seat 0. Логику StartingPlayerOrder в DE я не разбирал, уверенность низкая.
   benefit: Тактический выбор на старте как в оригинале. Человек в VS_AI не получает постоянного преимущества первого хода.
   cost: M: шаг SETUP с pending CHOOSE_SPACE для сайдкиков и UI в UE. Первого игрока выбирать через seed-RNG. | risk: Новая фаза затрагивает клиент UE и ИИ. Это дизайн-решение, его стоит вынести пользователю.
   VERIFY=confirmed: Наша сторона подтверждается. В VS_AI бот всегда сидит в seat 1, поэтому человек ходит первым всегда.

В DE есть SetupStates.Setup_Sidekick_SpaceText и подсказка «Place [archetype].». Как выбирается первый игрок (StartingPlayerOrder), не разобрано, уверенность низкая, как и сказал судья.
   ev: DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/scripts/phases/SetupStates.cs;DuelEngine-transfer/test-targets/unmatched-data/localization.txt:4318-4320;backend/src/games/services/game-initialization.service.ts:140-194;backend/src/games/services/game-initialization.servic
- [RULE-07] P3 | keep-ours | src=original | Карты боя уходят в сброс при розыгрыше, а не после боя
   why: В DE карты боя лежат в активной зоне до CleanupCombat, то есть до конца after-окон. У нас они в сбросе с момента розыгрыша (executor :2134-2140, :2287-2290). Код это компенсирует: DISCARD_NAME_PREFIX исключает саму карту (card-effect-executor.service.ts:1175), возврат карты в руку ищет её в сбросе. Разница проявится только при реализации корзинки Little Red (символ верхней карты сброса) и эффектов «посмотри в сброс».
   benefit: Без работы сейчас.
   cost: 0 сейчас. При реализации корзинки (RULE-04) — M: ввести активную зону боя. | risk: Пограничные эффекты, которые читают сброс посреди боя, могут ошибаться.
   VERIFY=confirmed: Подтверждается. В DE у CleanupCombat есть поля attackerDiscards и defenderDiscards, а состояние Cleanup=22 идёт после After-окон.

Утечки информации из раннего сброса нет: проекция состояния скрывает committed-карты боя в discardPiles.
   ev: DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/scripts/phases/CombatScript.txt:1779;backend/src/game-engine/services/game-action-executor.service.ts:2134-2140;backend/src/game-engine/services/game-action-executor.service.ts:2555;backend/src/game-engine/effects/card-effec
- RULE [RD-01] high | Карту играет только боец с её баннером
   orig: Fighter — типизированная ссылка на архетип бойца. Нарушить нельзя.
   ours: Строковый баннер. Опечатки «Allice» (8 карт Alice) и «The Potter» (By Fortune and Fate) не матчат ни одного бойца, validateBanner пишет warn и разрешает карту. Jabberwock играет карты Алисы, Sinbad — карту Porter.
   duel: Ограничения нет вообще: любой боец играет любую карту.
   VERIFY=weakened: Суть верна, но:
- **Severity high завышена.** Alice и Sinbad не в UE-ростере, до UE это не доходит.
- **Масштаб шире.** Ограничение по бойцу снято ещё у Philippa (Djkstra), Blackbeard (Sea dog) и Dr. Jill Trent («Jill Trent», Daisy может играть карты Jill).
- **ИИ.** Там эффект обратный: ИИ за Alice вообще не играет 8 её карт.
   ev: DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/data/DuelAttributes.cs:39;scraped-data/api/heroes/alice.json:150;scraped-data/api/heroes/sinbad.json:521;backend/src/game-engine/validators/game-rules.validator.ts:569-587;DuelEngine-transfer/duel-engine/UnityProject/Assets/
- RULE [RD-02] high | Размер Alice (BIG/SMALL) и стойки Ali
   orig: Размер Alice выбирается в начале игры и меняется только эффектами «Change size» (AliceSetup/AliceBig/AliceSmall, событие PostChangeSize). Ali стартует во Float и меняет стойку только после выигранного боя.
   ours: Alice всегда BIG по умолчанию: выбора на старте нет, «Change size» не парсится и не исполняется. Мутация setStance — бесплатный переключатель без ограничений в своей action-фазе: через API можно включить Sting у Ali перед атакой. UE её не вызывает.
   duel: IsBig переключается, но в бою не применяется.
   VERIFY=confirmed: Подтверждается. Severity high уместнее понизить до medium: в UE-ростере этих героев нет, остаётся API-эксплойт.
   ev: DuelEngine-transfer/test-targets/unmatched-data/localization.txt:3192;DuelEngine-transfer/test-targets/unmatched-data/localization.txt:3219;backend/src/game-engine/abilities/ability-config.ts:873-897;backend/src/game-engine/services/game-action-executor.service.ts:3058-3108;backend/src/games/resolve
- RULE [RD-03] medium | Неотменяемые эффекты (Holmes/Watson, Ciri, Winter Soldier, «This card's effects cannot be canceled»)
   orig: Есть атрибут карты Uncancellable (TheAncientHeirloom) и скрипт пассивки UncancellableScript для Holmes.
   ours: Не поддержано: CANCEL_EFFECTS безусловный, grep uncancel пуст. Feint гасит эффекты, которые гасить нельзя.
   duel: Есть только неотменяемость Шерлока.
   VERIFY=weakened: Поправки те же, что в RULE-01:
- частичная неотменяемость относится к Yennefer & Triss, а не к Eredin или Philippa;
- пропущена карта Yennefer & Triss;
- у Ciri есть квалификатор «🔵 x7».
В DuelEngine флаг действует на игрока целиком, на все карты включая Any, а не только на карты Holmes/Watson.
   ev: DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/data/DuelAttributes.cs:40;DuelEngine-transfer/test-targets/unmatched-data/localization.txt:3197;DuelEngine-transfer/test-targets/unmatched-data/localization.txt:3339;backend/src/game-engine/effects/card-effect-executor.servi
- RULE [RD-04] medium | Значение карты What Big Eyes You Have (Little Red)
   orig: Versatile 3, boost 2, ×2 (поле exact; UmDb тоже 3).
   ours: Значение 2.
   duel: 3 (взято из DE).
   VERIFY=confirmed: Подтверждено напрямую по ISIL. Расклад констант (copies, type, value, boost) сверен на соседних картах Little Red, которые совпадают со скрейпом.
   ev: DuelEngine-transfer/test-targets/unmatched-data/cards-full.json:23296-23313;scraped-data/api/heroes/little-red.json:306;.playwright-mcp/cards_database_snapshot.md:2173;docs/backend-api/09-cards-and-effects.md:916
- RULE [RD-05] medium | Dracula (Bloodthirsty): в начале хода можно нанести 1 урон смежному бойцу и тогда добрать
   orig: «You may», игрок выбирает цель — любого смежного бойца, в том числе своего. Добор только при попадании.
   ours: Принудительно, авто-цель — первый смежный враг, отказаться нельзя. Добор при пустой колоде наносит 2 урона истощения своим бойцам.
   duel: Не проверял.
   VERIFY=confirmed: Подтверждается. Приближение задокументировано в самом конфиге.
   ev: DuelEngine-transfer/test-targets/unmatched-data/localization.txt:3196;DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/scripts/fighters/BloodthirstyScript.txt;backend/src/game-engine/abilities/ability-config.ts:702-714;backend/src/game-engine/abilities/generic-hero-ability
- RULE [RD-06] medium | Bigfoot (Loner by Nature): в конце хода, если в его зоне нет врагов, можно добрать 1 карту
   orig: «You may draw». В скрипте есть кнопка выбора (CustomChoice).
   ours: Добор принудительный. При пустой колоде каждый свой боец получает 2 урона истощения.
   duel: Не проверял.
   VERIFY=confirmed: Подтверждается.
   ev: DuelEngine-transfer/test-targets/unmatched-data/localization.txt:3193;DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/scripts/fighters/LonerByNatureScript.txt;backend/src/game-engine/abilities/ability-config.ts:544-553;backend/src/game-engine/abilities/generic-hero-abilit
- RULE [RD-07] medium | Способности героев из ростера DE: Beowulf (Rage), Invisible Man (Fog), Jekyll&Hyde (трансформация и баннеры форм), Little Red (корзинка), Sinbad (Voyages)
   orig: Реализованы отдельными скриптами: Raging, InTheMist, StartTurnChooseBecome плюс архетипы DrJekyll и MrHyde, корзинка с BasketItems, SevenVoyages.
   ours: Не реализованы: grep пуст, boardState.fog и tokens не используются. Баннеры «Dr. Jekyll» и «Mr. Hyde» неизвестны и разрешаются любой форме.
   duel: Есть Rage и Fog. Нет корзинки, трансформации и Voyages; MrHyde не создан.
   VERIFY=confirmed: Подтверждается, с дополнением. Баннеры Dr. Jekyll и Mr. Hyde человеку разрешаются как неизвестные, а ИИ (bannerOk без запасного правила) эти 10 карт не играет вообще.
   ev: DuelEngine-transfer/test-targets/unmatched-data/localization.txt:3191;DuelEngine-transfer/test-targets/unmatched-data/localization.txt:3199-3202;DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/scripts/fighters;backend/src/game-engine/models/board.model.ts:17-18;scraped-da
- RULE [RD-08] low | Achilles: когда Patroclus повержен, сбросить 2 случайные карты
   orig: «Discard 2 random cards».
   ours: Сброс детерминирован: первые 2 карты руки (приближение MVP).
   duel: Героя нет.
   VERIFY=confirmed: Подтверждается. Приближение задокументировано: сбрасываются первые count карт руки.
   ev: DuelEngine-transfer/test-targets/unmatched-data/localization.txt:3205;backend/src/game-engine/abilities/ability-config.ts:824-845
- RULE [RD-09] low | Расстановка сайдкиков
   orig: Игрок сам ставит каждого сайдкика (Setup_Sidekick_SpaceText, prompt «Place [archetype].»).
   ours: Автоматическая легальная расстановка на сервере: клетка в общей зоне с героем (GD-016).
   duel: Все сайдкики в одной клетке со стартом героя.
   VERIFY=confirmed: Подтверждается.
   ev: DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/scripts/phases/SetupStates.cs;DuelEngine-transfer/test-targets/unmatched-data/localization.txt:4318;backend/src/games/services/game-initialization.service.ts:140-194;DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEn
- RULE [RD-10] low | Когда карты боя уходят в сброс
   orig: На CleanupCombat, после after-окон обеих сторон.
   ours: Сразу при розыгрыше атаки или защиты. Подсчёт и возврат в руку это компенсируют, но корзинка и «верх сброса» посреди боя будут неверны.
   duel: Сброс после боя, но бой хранит индексы руки (костыль CombatHandSync).
   VERIFY=confirmed: Подтверждается: в DE сброс идёт в CleanupCombat. Проекция у нас скрывает committed-карты, так что раннее попадание в сброс заметно только для эффектов, которые читают сброс.
   ev: DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/scripts/phases/CombatScript.txt:1779;backend/src/game-engine/services/game-action-executor.service.ts:2134-2140;backend/src/game-engine/services/game-action-executor.service.ts:2287-2290;backend/src/game-engine/effects/card-
- RULE [RD-11] low | Выбор первого игрока
   orig: SetupScript.StartingPlayerOrder / SetCurrentPlayer. Источник порядка не разобран, уверенность низкая.
   ours: Всегда seat 0.
   duel: P0 всегда первый; на игрушечной доске первый ход выигрывает 59% в L2 vs L2.
   VERIFY=confirmed: Наша часть подтверждается: в VS_AI человек всегда в seat 0. Источник порядка в DE не разобран, уверенность низкая. Цифру «59%» по DuelEngine я не проверял.
   ev: DuelEngine-transfer/test-targets/cpp2il-cs/DiffableCs/duel-canis/duel/canis/scripts/phases/SetupScript.cs:102;backend/src/games/services/game-initialization.service.ts:275
- RULE [RD-12] low | Добор в начале хода
   orig: Нет: в InitializeTurn только TotalActions=2, вызовов Draw нет.
   ours: Нет (совпадает).
   duel: Добор 2 карты в начале каждого хода.
   VERIFY=confirmed: Подтверждается.
   ev: DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/actions/phase/BeginPlayerTurn_NestedType__InitializeTurn_d__5.txt:1694-1706;backend/src/game-engine/services/game-action-executor.service.ts:312;DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Core/Actions.cs:
- RULE [RD-13] low | Пустая колода (истощение)
   orig: За каждую недобранную карту каждый свой активный боец получает 2 урона. Сброс не замешивается.
   ours: Совпадает; добор останавливается, если герой погиб.
   duel: Сброс замешивается в колоду; если пусто и там, урона нет. Отсюда бесконечные партии.
   VERIFY=confirmed: Подтверждается. В Draw оригинала есть флаг WithPreDrawShuffle и вызов ShuffleWithLogs, но это перемешивание колоды по запросу эффекта, а не возврат сброса в колоду. Вывод судьи остаётся в силе.
   ev: DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/actions/Draw_NestedType__execute_d__10.txt:1545-1566;DuelEngine-transfer/test-targets/unmatched-data/localization.txt:4804;backend/src/game-engine/services/deck-management.service.ts:73-85;DuelEngine-transfer/duel-engine/Uni
- RULE [RD-14] low | Схема — одно из двух действий хода
   orig: Да: InitiateAction наращивает ActionsTaken для схемы, лимита «1 схема за ход» нет.
   ours: Совпадает.
   duel: Схема бесплатна, одна за ход, до или после действия.
   VERIFY=confirmed: Подтверждается: смещение 496 = 0x1F0 = ActionsTaken. Схема как действие подтверждается и туториалом.
   ev: DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/actions/phase/InitiateAction_NestedType__execute_d__1.txt:1755-1904;DuelEngine-transfer/test-targets/unmatched-data/localization.txt:4752;backend/src/game-engine/models/game-state.model.ts:458-462;DuelEngine-transfer/duel-en
- RULE [RD-15] low | Буст в бою и буст манёвра
   orig: Общего буста в бою нет: только текст карты или пассивка Артура (Conviction). Манёвр можно бустить сбросом любой карты, +BOOST к движению.
   ours: Совпадает: в бою BOOST_CHOICE только от эффекта или Артура; буст манёвра одной картой ко всем бойцам.
   duel: Обе стороны бустят бой любыми картами (DefenderBoostPhase/AttackerBoostPhase); буста манёвра нет.
   VERIFY=confirmed: Подтверждается.
   ev: DuelEngine-transfer/test-targets/unmatched-data/localization.txt:4772;DuelEngine-transfer/test-targets/unmatched-data/localization.txt:3189;backend/src/game-engine/validators/game-rules.validator.ts:318-345;DuelEngine-transfer/duel-engine/UnityProject/Assets/DuelEngine/Core/Engine.cs:1447-1466
- RULE [RD-16] low | Порядок одновременных эффектов в бою
   orig: В каждом окне (Immediate/During/After) первым защитник, после Immediate проверяется IsGameOver.
   ours: Совпадает: защитник первый на каждой стадии, after пропускается при GAME_OVER.
   duel: В Immediate и After первой идёт карта атаки.
   VERIFY=confirmed: Подтверждается. Самое прямое доказательство для DE — enum CombatStates: Defender* идёт раньше Attacker* в каждом окне.
   ev: DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/scripts/phases/CombatScript.txt:1603-1779;DuelEngine-transfer/test-targets/unmatched-data/localization.txt:4738;backend/src/game-engine/effects/card-effect-executor.service.ts:180-183;DuelEngine-transfer/duel-engine/UnityPro
- RULE [RD-17] low | Доска: граф, зоны, блокировка и занятость клеток
   orig: Граф клеток с несколькими цветами-зонами. Враги блокируют путь, на клетке один боец. Дальний бой — смежная клетка или общая зона.
   ours: Совпадает; топология и стартовые клетки Marmoreal и Sarpedon поштучно равны DE.
   duel: Линия из 8 клеток, зона = zone/3, сквозь врагов можно, несколько бойцов в клетке. Плюс баг: Невидимка с Zone=-1 атакуем из клетки 0.
   VERIFY=confirmed: Подтверждается. Я перезапустил сравнение стартов, совпадение полное. Баг DuelEngine с Невидимкой не проверял.
   ev: DuelEngine-transfer/test-targets/unmatched-data/localization.txt:4790;DuelEngine-transfer/test-targets/unmatched-data/localization.txt:4834;backend/src/game-engine/movement/traversal.ts:1-10;backend/src/game-engine/engine/adjacency.service.ts:282-286;DuelEngine-transfer/duel-engine/UnityProject/Asse
- RULE [RD-18] low | Конец партии
   orig: Игрок выбывает, если его герой не в игре или у него нет активных бойцов; ничья возможна.
   ours: Совпадает: гибель HERO/HUGE, одновременная гибель — ничья.
   duel: GameOver затирается веткой SchemePhase→MainPhase после урона из отложенных эффектов, и позже может быть объявлен другой победитель.
   VERIFY=confirmed: Наша часть подтверждается. Баг DuelEngine правдоподобен уже по коду: после очереди отложенных эффектов else-ветка ставит Phase=SchemePhase и затирает GameOver.
   ev: DuelEngine-transfer/test-targets/cpp2il-isil/IsilDump/duel-canis/duel/canis/data/enums/EliminationConditionsExtensions.txt;DuelEngine-transfer/test-targets/unmatched-data/localization.txt:4365;backend/src/game-engine/engine/terminal-state.ts:4-29;DuelEngine-transfer/duel-engine/UnityProject/Assets/D
MISSED: Проблема с баннерами шире двух опечаток. Я прогнал bannerAllows по всему скрейпу против героя и его сайдкиков (scratchpad/skeptic/banners.py). Баннер не совпадает ни с одним бойцом в 47 строках карт у 8 героев:
- Allice ×8;
- The Potter;
- Djkstra (Philippa);
- «Sea dog» при сайдкике «Seadog» (Blackbeard);
- «Jill Trent» при «Dr. Jill Trent» (Daisy может играть 3 карты Jill);
- «T-Rex» при «T. Rex || Асимметрия ИИ и человека. ai-decision.service.ts:281-284 (bannerOk) вызывает bannerAllows без запасного правила «неизвестный баннер → разрешить», которое есть у validateBanner (game-rules.validator.ts:580-586). Последствия:
- ИИ за Alice никогда не играет её 8 именных карт;
- ИИ за Jekyll & Hyde не играет 10 карт форм;
- ИИ за T. Rex и Spiderman не может сыграть ни одной карты колоды: у них все ка || Контекст приоритетов. В UE комната предлагает только King Arthur и Medusa (S08FlowGameModeUmRoom.cpp:10-11, :101). Для них данные совпадают с DE: в cmp.txt только написание имён, а баннер «Arthur» и сайдкик «Harpies» bannerAllows покрывает. Ни один найденный дефект данных или правил сейчас не доходит до игрока в UE. Значит, P0/P1 касаются API, Game Tester, ИИ и будущего расширения ростера. || Покрытие парсера уже измеряется. backfill-card-effects.ts --dry-run выдаёт отчёт parsed/unsupported по героям, а в docs/plans/engine-gaps-batch-2026-06-14.md:18-19 зафиксирована метрика 240/712. DE даёт только семантическую разметку для 14 колод. || Большинство найденных расхождений способностей (Dracula, Achilles) уже задокументированы в ability-config.ts как «приближение MVP» и видны по нашим scraped specialAbility. DE их подтверждает, но не открывает. || Неотменяемость у Yennefer & Triss: способность героя с частичной неотменяемостью и отдельная карта «This card's effect cannot be canceled.». Судья приписал первое Eredin и Philippa: в их файлах этот текст лежит только как otherSetHeroes. || В DE у Marmoreal и Sarpedon есть по одной клетке со служебным StartPlayer 101 и 100 (наши M15 и S37). Если в числовой эталон досок (DATA-04) войдут только старты 1–4, эти клетки стоит упомянуть, пока их смысл не разобран.

######## CRITIC
# Критика полноты: сводка по шести измерениям

## 0. Коротко

Шесть измерений хорошо разобрали ядро: правила, состояние и детерминизм, протокол выборов, сеть, ИИ и тесты, данные. Остались четыре пробела, которые влияют на вердикт:

1. **Режимы оригинала никто не открывал.** Это испытания (Challenges), обучение, Pass&Play до 4 игроков и команды. Они устроены как данные плюс модификаторы правил, оформленные как способности. Я этот пробел закрыл, см. §4.1.
2. **Разобраны 2 поля из 11.** Топология остальных 9 тоже есть в дампе. Заодно выяснилось, что открытый вопрос про «StartPlayer 101/100» — артефакт разбора, см. §4.2.
3. **Не заданы два вопроса: юридический и про гигиену репозитория.** В корне репо лежит 808 МБ проприетарного дампа, и `.gitignore` его не исключает.
4. **Нет общей перепроверки приоритетов по текущему продукту.** В UE доступны только Arthur и Medusa. Большинство P0/P1 по правилам и данным до игрока в UE не доходят. Доходит в первую очередь залипание на Restless Spirits (§2.1).

Важная оговорка о доказательствах: поведение нашего движка ни одно измерение не проверяло запуском. Каталог `backend/node_modules` пуст (0 записей), `.bin/jest` в нём нет. Все выводы о залипании UE, ложном отказе после коммита и «ИИ встаёт» сделаны по чтению кода, уверенность средняя. Запускались только копия парсера (`scratchpad/effects-judge/run.ts`) и харнесс DuelEngine (`scratchpad/duel-run/out/*`).

---

## 1. Что не изучено или изучено поверхностно

### DuelEngine-transfer

| Часть | Состояние | Почему важно |
|---|---|---|
| `test-targets/unmatched-data/textassets/*.json`: 44 испытания (22 × Normal/Heroic), `TutorialGame1`, `StandardSolo`, `PassAndPlay` | Не разбирал никто, использованы только `DuelAIConstants-*` | Это формат «матч как данные» и модификаторы правил как способности. **Закрыто в §4.1** |
| ISIL `duel-canis/duel/canis/data/Battlefields/*/` (11 полей) | Разобраны только Marmoreal и Sarpedon | **Закрыто в §4.2** |
| `localization.txt`, блок en_US | Измерение data-rules пишет, что «DE покрывает 14 героев». Это верно для чисел, но не для текстов | **Закрыто в §4.3** |
| `DiffableCs/duel-canis/duel/canis/data/DuelAttributes.cs`: 154 типизированных `AttributeDefinition<T>` | Брались отдельные смещения (Uncancellable, ActionsTaken). Как модель хранения не рассмотрен | Там лежат `Team`, `Eliminated`, `EliminationCondition`, `RageAmount`, `Big`, `MovesBetweenFog`, `TransformCount`, `DoorDefinitions`, `SecretPassage`, `Tokens` и счётчики достижений. Это прямой образец для нашего известного пробела «жетоны, стойки, ресурсы» (см. §3.5) |
| `data/Tutorials` (21 класс: `DoorsFTT`, `ExhaustFTT`, `HandLimitFTT`, `SecretPassageFTT`, `TutorialSetupScript`), `achievements` (74), `*/Challenges` (238) | Не открывали | Подсказки «при первом разе» привязаны к событиям движка. У нас похожая логика — `S08WhyText.cpp` |
| Презентация `duel-client` (Delorean `SequenceQueue`, `ISequenceBlockage`) | Посчитано 5 имён последовательностей, поведение блокировок не проверено (NET-14 это оговаривает) | Нужно для NET-1 и NET-14 |
| `inventory.json` (6,9 МБ) | Не открывали | Я проверил: это опись 220 Addressables-бандлов (спрайты, MonoBehaviour), а не инвентарь игрока. Для вердикта не нужен |
| Мета-поля `MatchInitData`: `Ranked`, `RequireOwnership`, `OwnedSets`, `validAvatars`, `SkirmishScoringMethods` | Не сравнивались с нашими matchmaking, ELO и users | Низкий приоритет |
| Il2CppDumper, `cpp2il-il`, `cpp2il-out`, `unmatched.ghidra-snapshot`, `opentracks.apk` | Не изучены | Первые четыре дублируют DiffableCs/ISIL. `opentracks.apk` по имени к Unmatched не относится, не открывал |
| DuelEngine Runtime/UI (`HumanShell`, `BoardView`), `LobbyServer`, `.wf-backups`, `.zcode` | Exe запускали только до стартового экрана (`scratchpad/duel-run/exe-start.png`), UX не оценивали | Для вердикта неважно: клиент у нас UE |

### Наш проект

- **Живая БД не проверялась** (Docker остановлен). Выводы о баннерах и покрытии парсера сделаны по скрейпу и сидам. Три числа покрытия между собой не сводятся: 264/880 (прогон судьи), 271/855 (документ), 240/712 (`docs/plans/engine-gaps-batch-2026-06-14.md:18-19`).
- **`admin/`** — смотрели только Game Tester и редактор карт.
- **`backend/src/matchmaking`, `presence`, `users` (ELO), `content`** — почти не смотрели. В частности, никто не проверил, как устроены режимы 2v2 и FFA (§3.4).
- **UE** — C++-зеркало правил (`S09ManeuverUi`, `S08MoveParityTests.cpp`) прочитано частично. UE-тесты (`S10RecoveryTests.cpp`) не запускались.

---

## 2. Утверждения без доказательств и противоречия между измерениями

1. **Одна и та же проблема получила три приоритета и три оценки стоимости.** Речь о повторном id выбора и счётчике: SEL-01 (P0, S), NET-2 (P1, M), DET-4 (P2, «день и больше»). Проверка NET-2 расширила проблему: лок держится при любом resolve/decline со статусом HttpStatus 0 (`S08FlowController.cpp:1732-1795`). Это надо свести в одну рекомендацию.
   - **Моя проверка.** Restless Spirits — карта Merlin в колоде Артура. Её текст: «Choose any space in Merlin's zone… and in one adjacent space» (`scraped-data/api/heroes/king-arthur.json:679-680`). Это двухстадийный CHOOSE_SPACE, а Артур есть в UE-ростере. Вместе с SEL-07 (ложный `errors[]` после коммита) это **единственные найденные дефекты, которые достают игрока в нынешнем UE**.
2. **«Проверки на каждом шаге партии пока нет»** (DET-3, missed) — неверно. `backend/src/games/services/s09-card-instance-dup.spec.ts` вызывает `checkInvariants` после каждой мутации (`:159`, `:261-509`), так что прав ai-tooling (OS-tests). Точнее сказать так: основная партия s09 идёт на Cobble (`:30` → `docs/game-design/evidence/S01/content-board.json`), Marmoreal есть только в отдельном тесте (`:540-541`), случайных ходов нет.
3. **Второй поток RNG.** DET-1 считает, что «обслуживать некого», AI-02 — что поток нужен, чтобы шум ИИ не сдвигал перетасовки. Оба правы, но для разных моментов: поток понадобится, когда появится шум ИИ (AI-05). Сейчас достаточно одного seed.
4. **SEL-09 объявил «120/120» непроверяемым — это неверно.** Строка есть: `scratchpad/duel-run/out/harness-all.log:58`, повтор по (seed, SelectionResponse) дал 120/120. В той же строке `:56` есть цифра, которой нет в итоге: в DuelEngine 49 из 156 объявленных способностей не сработали ни разу. Это ослабляет заявление HANDOFF.md о «94% карт полным эффектом».
5. **Таймер хода: решения противоречат друг другу.** SEL-03 и NET-6 предлагают «ИИ доигрывает», а собственная рекомендация проекта — «пас или манёвр на месте, а не ИИ» (`docs/game-design/de-footage/README.md:509,527`). Длительность в источниках разная: 90 с, около 85 с, 3 мин. Это решение пользователя, и до него приоритет P1 не обоснован.
6. **Фазз описан трижды** (DET-3, SEL-08, AI-01), с разными стартовыми точками и стоимостью. Риск, который отметил только AI-01: `HeroAbilityRegistry` в `s03Engine` пуст (`backend/src/test/fixtures/s03-engine.fixture.ts:36-46`). Без явной проводки фазз будет гонять партии без способностей героев.
7. **R9 и DET-11 дублируют друг друга** (удаление ValueModifierService). Правильный вариант дан в DET-11: типы `ValueModifier*` нужно сохранить.
8. **Приоритеты P0/P1 по правилам и данным** (DATA-01, RULE-01…03, R2, D1–D6) не учитывают, что в UE-ростере только Arthur и Medusa (`S08FlowGameModeUmRoom.cpp:10-11`, это проверил скептик data-rules). Измерение rules-engine свои приоритеты не пересчитало. Для текущего продукта это P2: они касаются API, Game Tester, ИИ и будущего ростера.
9. **«DE покрывает 14 героев (~17%)»** — верно для чисел и AbilityID, неверно для текстов (§4.3).
10. **«StartPlayer 101/100 — смысл не разобран»** (DATA-04) — закрыто в §4.2: это артефакт разбора.

---

## 3. Вопросы для вердикта, которые никто не задал

1. **Юридическая граница и гигиена репозитория.**
   - Факты: в `test-targets/dump-work/` лежат `GameAssembly.dll` и `global-metadata.dat`. Вся папка (808 МБ) находится в корне репо со статусом `?? DuelEngine-transfer/`, `git check-ignore` для неё ничего не выдаёт. В git пока ничего из DE не попало: `git ls-files` по маскам duelengine, test-targets, cards-full, DuelAIConstants пуст.
   - Прецедент в проекте уже есть — D-06: скрейп используется только как референс (`docs/game-design/00-vision-and-scope.md:100,118`).
   - Что предлагают измерения, по уровню риска:
     - идеи архитектуры — безопасно;
     - числа как эталон в тестах (DATA-04: HP, Move, топология) — низкий риск, но решает пользователь;
     - тексты карт и `abilitydescription` — только для разовой сверки, в БД и фикстуры не класть;
     - значения `DuelAIConstants` — это результат чужого тюнинга, значения не переносить, переносить только структуру;
     - тела ISIL — никогда.
   - Рекомендация пользователю: вынести папку из репо или добавить её в `.git/info/exclude`. Сам я в git ничего не менял.
2. **Явный вердикт про стек.** Остаёмся на NestJS+UE или переходим на Unity/C# и ядро DuelEngine? Все измерения подразумевают «остаться», но цифрами это никто не сказал. Цифры:
   - DuelEngine `Assets/DuelEngine/Core` — 7 063 строки C#, всего 19 009 вместе с UI и тестами. Доска — линия из 8 зон (`Core/Board.cs:19-38`), хранения нет, 7 базовых расхождений правил (RD-12…18).
   - Наш `backend/src/game-engine` — 15 308 строк без спек и 19 786 строк спек, `backend/src/games` — 9 075; всего 101 spec-файл. Клиент на UE5 с принятым артом.
   - Как основа DuelEngine непригоден.
3. **Сценарии, испытания и обучение.** Обучение стоит в плане после MVP (`00-vision-and-scope.md:26,81`). Архитектура оригинала (§4.1) показывает, что всё это делается теми же способностями, что и у героев. Это аргумент сделать R1/R3 так, чтобы способности подключались не только к герою, но и к игроку и к матчу.
4. **Режимы 2v2 и FFA объявлены, но не реализованы.**
   - Есть `GameMode.TWO_V_TWO` и `FREE_FOR_ALL` (`backend/prisma/schema.prisma:168-173`) и очереди матчмейкинга (`backend/src/matchmaking/services/queue-manager.service.ts:122`).
   - Но модель рассчитана на 2 места: одно поле `Game.opponentId`, вход в лобби отклоняется, если `opponentId` занят (`backend/src/games/game.service.ts:194`).
   - Понятия команды в движке нет (grep `team` по `game-engine/models|engine|validators` пуст). `terminal-state.ts:16-17` считает победителем «последнего живого», а для 2v2 это неверно.
   - У DE есть `Teams` A–D (`duel-canis/duel/canis/data/enums/Teams.cs`), `TeamSizes` (`DuelMatchInitData.cs:56`), атрибуты `Team`, `Eliminated`, `EliminationCondition`, а у Solo и PassAndPlay `maxPlayers: 4`.
   - Вопрос пользователю: 2v2 и FFA в планах? Если нет — убрать мёртвые режимы. Если да — это решение на уровне GameState, и DE здесь образец.
5. **Где хранить ресурсы героев: ярость, размер, жетоны тумана, улики, маяки.** Это ключевой вопрос для шести «пустых» героев DE (D6, RULE-04). У DE для этого типизированный реестр атрибутов на сущности. У нас разрозненные места: `FighterEffect`, `metadata`, `boardState.fog/tokens` (`board.model.ts:17-18`). Вопрос «единый типизированный реестр атрибутов в GameState или поштучные поля» никто не задал.
6. **Что из найденного затрагивает текущий продукт** (UE, Arthur против Medusa, Marmoreal и Sarpedon)? Предлагаю такой список:
   - SEL-01, NET-2 и DET-4 вместе, плюс SEL-07;
   - AI-03 и SEL-04 вне боя для VS_AI;
   - seed и реплей (DET-1, DET-2) как фундамент.
   Остальное относится к API и росту ростера.

---

## 4. Пробелы, которые я закрыл сам

### 4.1 Матч как данные: испытания, обучение, Pass&Play

**Файлы сценариев:**
- `textassets/` содержит 44 файла с `gameType: "Challenge"`, а также `TutorialGame1.json` (`Tutorial`, Alice-человек против Medusa с `aiLevel 0`, Sarpedon), `StandardSolo.json` и `PassAndPlay.json` (`maxPlayers: 4`).
- Пример `ExcalibursWrathHeroic.json`: Marmoreal, Arthur-человек против Alice с `aiLevel 2`. Игроку добавлена способность `ChaExcaliburArthurBoostSweepDamageAbility`, сопернику — `ChaExcaliburOppSidekickHealthHeroicAbility` и `ChaExcaliburOppMinHealthAbility`. Есть поля `prereqScenarios` (Heroic открывается после Normal) и `GamesToWin`.

**Схема данных:**
- `Canis/canis/MatchInitData.cs`: `randomSeed` (:93), `GlobalAbilityArchetypes` (:92), `SkirmishRuleMods` (:75), `Ranked` (:88), `gameState` типа `SerializedGameState` (:53).
- `duel-canis/duel/canis/match/DuelMatchInitData.cs`: `DuelPlayers`, `GamesToWin`, `Battlefield`, `ExcludedDecks`, `TeamSizes`, `OverrideSetupScript`, `OverrideTurnScript`, `OverrideEndTurnScript` (:45-65).
- `Canis/canis/PlayerMatchInitData.cs`: `isHuman`, `aiLevel`, `AbilityArchetypes` (:6-19).
- `DuelPlayerMatchInitData.cs`: `Deck`, `Team`, `TurnOrder`, `DeckSelectionMode` (:9-20).

**Модификаторы.** Модификаторы испытаний — это классы `AbilityArchetype`, той же иерархии, что способности героев. Например, `Heroes/Shared/Challenges/Abilities/ChaExtra1SidekickAbility.cs:5` и `ChaSuppressInitialDrawAbility.cs:5`; всего в папках `*/Challenges` 238 классов. Где именно Match подключает `AbilityArchetypes` из init-данных, в ISIL я не нашёл (`SetupScript.txt` смотрел). Уверенность в механизме подключения средняя, в формате данных — высокая.

**У нас.** `CreateGameDto` содержит только `mode` и `boardId` (`backend/src/games/dto/create-game.dto.ts:44-55`). Сценариев и обучения в backend нет: grep `scenario|challenge|tutorial` по `backend/src` без спек пуст. Первого игрока задаёт `seatOrder 0` (`game-initialization.service.ts:275`).

**Вывод: adapt, P3, после R1/R3.** Формат JSON сценария матча: доска, колоды, места и порядок хода, уровень ИИ, seed, список способностей-модификаторов на игрока и на матч. Он сразу даёт пользу:
- это «стартовый снимок» для DET-2 и AI-11;
- он заменяет ручные моки в фикстурах фазза (`s09-card-instance-dup.spec.ts:98-113`);
- выбор первого игрока (RULE-06) решается полем, а не кодом.

`Override*Script` (скрипты фаз в коде) не брать.

### 4.2 Топология всех 11 полей DE и «StartPlayer 101/100»

Я прогнал парсер судьи (`scratchpad/board.py`) по всем полям; моя копия — `scratchpad/critic/all_boards.py`.

| Поле | Клетки | Рёбра |
|---|---|---|
| Marmoreal | 31 | 42 |
| Sarpedon | 38 | 61 |
| BaskervilleManor | 32 | 52 |
| Heorot | 30 | 51 |
| SherwoodForest | 30 | 39 |
| Soho | 29 | 36 |
| SplashPaddock | 28 | 46 |
| TWrecks | 26 | 37 |
| ThrillaInManila | 30 | 52 |
| TsingShanMonastery | 30 | 50 |
| Yukon | 31 | 39 |

**Парсер надёжен.** Для Marmoreal он даёт 31 клетку, 42 ребра, 21 клетку в нескольких зонах и 7 в трёх. Для Sarpedon — 38, 61, 4 и 2. Это точно совпадает со `summary` в `backend/prisma/fixtures/boards/marmoreal.topology.json` и `sarpedon.topology.json`. В каждом поле у одной клетки не распознан индекс, как и у судьи.

**Чего этот разбор не даёт.** Координат клеток для UE он не даёт (не проверял). Отдельно вопрос из §3.1. Сейчас это не рекомендация: по `AGENTS.md` в scope только две реальные карты. Это запас, если пользователь захочет третью доску.

**«StartPlayer 101/100» — артефакт разбора** (уверенность высокая). В конструкторе Marmoreal последние два вызова `0x181591A70` (`Battlefields/Marmoreal/Marmoreal.txt:5166` и `:5232`) берут атрибуты `DuelAttributes` по смещениям 0x0 и 0x10. Это `EntityType` и `Set` (`DuelAttributes.cs:7,9`), значения 1 и 101. В `Sets.cs` `Marmoreal = 101`, `Sarpedon = 100`. Скрипт `scratchpad/judge/starts.py` приписывает эти вызовы последней созданной клетке. Значит, M15 и S37 не особые клетки, и в числовой эталон досок их вносить не нужно.

### 4.3 Тексты героев DLC в DE есть, правил нет

**Тексты.** В блоке en_US (`localization.txt:2646-4873`) непустые: 406 `action.*.title`, 33 `deck.*.title` и 35 `fighter.*.abilitydescription`. Среди колод есть Achilles, Annie Christmas, Bloody Mary, Golden Bat, Hamlet, Houdini, Nikola Tesla, Oda Nobunaga, Sun Wukong, The Genie, Wayward Sisters, Titania&Oberon, Tomoe Gozen, Shakespeare, Yennenga и Jill Trent. Пример: `action.achillesheel.combatafter`, `localization.txt:3268`.

**Правила.** У этих героев в сборке только заглушки бойцов. В `Heroes/Achilles` два файла, `Achilles.cs` и `Patroclus.cs`; у `KingArthur` — 47. Карт, колод и способностей у них нет. Отсутствуют ли они в этом билде или приходят другим путём, не проверял.

**Следствие для DATA-03 и DATA-05.** Эталон текстов для разовой сверки покрывает около 30 колод, а не 14. Числа и AbilityID по-прежнему есть только для 14 героев: в `cards-full.json` 189 карт, у всех `confidence: exact`. Русских текстов карт нет: блок ru_RU — только UI (415 строк).

---

Временные файлы: `C:/Users/ren/AppData/Local/Temp/claude/C--Users-ren-WebstormProjects-unmached-unmached/2b6a7e70-a9a9-4f0e-bd48-9f26a5894d1b/scratchpad/critic/all_boards.py` и `.../scratchpad/critic/en_US.txt`. В репозитории и в DuelEngine-transfer ничего не менял, git-операций не делал.