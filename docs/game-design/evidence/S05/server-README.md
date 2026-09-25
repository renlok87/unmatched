# S05 Server/Cards Track — GD-017 / GD-019 / GD-020

Исполнитель: GLM-5.3 (server). Ветка `codex/s05-abilities-medusa`, base `1ca2231`.
Полные данные: `server-tasks.json` (задачи/код/тесты), `server-verification.json` (прогоны),
`s05-card-registry.json` (машиночитаемый реестр GD-019, генерируется тестом).

## GD-017 — способности героев

**Medusa** («At the start of your turn, you may deal 1 damage to an opposing fighter
in Medusa's zone»; в захвате у способности НЕТ поля name — внутренний
provisional-лейбл «Medusa turn-start damage», игроку предъявляется только
печатный текст):
- старт хода владельца создаёт `TARGET_FIGHTER` pending (`optional: true`,
  `damage: 1`, цели = живые бойцы противника в зоне Medusa по реальному
  `AdjacencyService.isInSameZone`); авто-урона нет;
- resolve — `resolvePendingEffect(effectId, fighterId)` без клетки; revalidation
  цели (поверженная цель отклоняется); pending строго owner-bound («принадлежит
  другому игроку»); decline — `declinePendingEffect`, урон не наносится;
- нет целей в зоне → pending не создаётся (no-op).

**King Arthur** (R-15/R-16; internal provisional label «King Arthur attack
boost» — в захвате `content-king-arthur.json` у способности НЕТ поля name,
канонического имени не существует, игроку имя не предъявляется):
- `attack(…, abilityBoostCardId)`: вторая карта руки уходит face-down вместе с
  атакующей — способность коммитится при объявлении, КАК НАПЕЧАТАНО (R-15).
  `combatInfo.attackValue` — ТОЛЬКО печатное значение; ability-буст —
  отдельное поле `boostValue` (+`abilityBoostCardId`); обе карты в сброс.
  Карточный BOOST-эффект (Noble Sacrifice) — отдельный слот ПОСЛЕ reveal
  (см. секцию тайминга ниже);
- бустятся только атаки самого King Arthur: Merlin с `abilityBoostCardId` →
  отказ; ability-boost той же картой, что атака → отказ; защита (playDefense)
  ability-слота не имеет;
- R-16: защитный Feint (CANCEL_EFFECTS, ON_REVEAL) отменяет эффекты атакующей
  карты → boost сбрасывается без эффекта, урон считается от печатного значения;
  эффекты атакующей карты (напр. Swift Strike MOVE) при отмене не исполняются;
- видимость (rulebook p.12-13: обе карты вскрываются ОДНОВРЕМЕННО до
  DURING_COMBAT-выборов): ДО reveal — `filterPrivateData` вырезает
  `boostValue`/`cardBoostCardId`/`abilityBoostCardId` у всех, кроме атакатора,
  И скрывает личины committed-карт в `discardPiles` от другого игрока
  (фазы COMBAT и COMBAT_RESOLVE-без-прогресса; длина сохранена — факт коммита
  виден, как face-down карта на столе). Reveal = запуск `executeResolveCombat`
  (серверный маркер — живой `combatResolutionProgress`): с этого момента,
  ВКЛЮЧАЯ паузы BOOST_CHOICE / defender DURING-выборов и окно после выбора
  boost-карты, личины атакующей, защитной и committed-boost карт +
  `boostValue`/`cardBoostCardId`/`abilityBoostCardId` открыты ОБОИМ игрокам;
  руки и невыбранная boost-кандидат по-прежнему скрыты. Канал доставки
  единый: query/mutation/WS — все через `filterPrivateData`; WS-payload
  сохраняет `combatResolutionProgress` до per-player фильтра (это и есть
  reveal-флаг) и несёт `discardPiles` (S05-поле подписки GameStateGQL).
  GameView рендерит reveal-личины в панели боя lookup'ом по instance id в
  discardPiles (до reveal чужая карта = плейсхолдер → `???`).
  Известный остаточный канал (пре-существующий, вне S05-скоупа):
  числовое `combatInfo.defenseValue` защитника остаётся видимо атакатору до
  reveal — S07-privacy; serialize/deserialize переносит bv/cbc/abc
  (легаси-сейвы без boost полей корректны: `boostValue ?? 0`).

### Тайминг карточного BOOST (Second Shot / Noble Sacrifice) — исправлено

Официальный источник: Restoration Games, Battle of Legends Vol.1 rulebook,
стр. 12-13 (https://restorationgames.com/wp-content/uploads/2019/07/UM-Battle_of_Legends_vol1_Rules-two-page.pdf):
после того как ОБА игрока выбрали карты, они вскрываются ОДНОВРЕМЕННО; после
reveal исполняются IMMEDIATELY-эффекты, затем DURING_COMBAT-эффекты, эффекты
защитника первыми. Печатный текст Second Shot (Medusa) и Noble Sacrifice
(Arthur) — «DURING COMBAT: You may BOOST this attack.» — значит ВЫБОР карты
происходит на стадии DURING_COMBAT ПОСЛЕ reveal и проверки отмены Feint,
а НЕ при объявлении атаки.

Прежняя реализация коммитила карту-буст в `executeAttack` — это была ошибка:
цитата «along with your attack card» (линия R-15) относится ТОЛЬКО к
специальной способности King Arthur, а не к карточным BOOST-эффектам.

Текущее поведение:
- `executeAttack`/`playDefense` больше НЕ принимают `boostCardId`: карта
  эффекта BOOST не покидает руку при объявлении, защитник до reveal не видит
  даже факта второй карты;
- на стадии DURING_COMBAT (после reveal-отмен, эффекты защитника первыми)
  эффект BOOST `PLAYER_CHOICE_HAND` создаёт persisted `BOOST_CHOICE` pending
  (owner-bound, `optional: true`); пустая рука → легальный no-op без pending;
- пауза боевой цепочки: урон и after-combat НЕ считаются, пока владелец не
  выберет карту (`resolvePendingEffect(cardIds)` — ровно ОДНА своя карта,
  ревалидация атомарна: чужая/не из руки/не голова/replay — отказ) или не
  откажется (`declinePendingEffect`); выбранная карта идёт в сброс, её
  boostValue — в `combatEffectContinuation` (finalAttack/finalDefense по
  стороне) и в `combatInfo` (boostValue + cardBoostCardId);
- защитный Feint (CANCEL_EFFECTS, ON_REVEAL) отменяет карточный BOOST-эффект
  целиком: выбора нет, карта не тратится; ability-карта Arthur, напротив,
  уже в сбросе при объявлении (R-15) и при отмене теряется без ценности
  (R-16), урон — от печатного значения;
- способность Arthur и Noble Sacrifice — ДВА независимых буста («in addition
  » в печатном тексте): ability при объявлении, карта после reveal;
- сериализация: BOOST_CHOICE pending + continuation переносится
  serialize/deserialize, пауза переживает ресторт (spec: roundtrip);
- ИИ: бустит МИНИмальной достаточной картой (меняет исход), иначе decline.

## GD-019 — реестр 27 записей / 60 копий

Источник — замороженные захваты каталога (`evidence/S01/content-medusa.json`,
`content-king-arthur.json`), ingest идентичен production
(`normalizeCardEffects` → если пусто и SCHEME с текстом →
`parseCardEffectTexts({ fullText })`, тайминг AFTER_COMBAT) и зеркален в
`prisma/backfill-card-effects.ts`.

Итог (parser v8): 20 SUPPORTED · 1 PARTIAL (Skirmish — выбор бойца боя не
моделируется) · 5 UNSUPPORTED (The Holy Grail, The Lady of the Lake, Prophecy,
Command the Storms, Restless Spirits — честные пробелы, НЕ silent no-op) ·
1 BLANK (Excalibur — доказано: пустые text/effects/effect*-поля + паранойный
парс всех полей даёт []).

Пустые effects при непустом печатном тексте устранены: 6 схем с текстом только
в textEn (Glance, Winged Frenzy — Medusa; Lady of the Lake, Prophecy,
Command the Storms, Restless Spirits — Arthur) теперь проходят fullText-слот.
Shared titles (Feint, Regroup) — ОТДЕЛЬНЫЕ записи по content key/владельцу,
не нормализуются (Medusa Feint boost 2 ≠ Arthur Feint boost 1).

## GD-020 — все 11 карт Medusa через реальный executor

- **A Momentary Glance**: цели = ВСЕ живые бойцы в зоне Medusa (включая своих и
  саму Medusa — «any one fighter»); 2 урона по выбранной; вне списка /
  поверженная / обязательный decline — отклоняются; враг, покинувший зону до
  выбора, выпадает из списка, свои остаются легальными.
- **Winged Frenzy**: последовательные MOVE каждого живого своего бойца
  (`canPassThroughEnemies: true` — проход СКВОЗЬ врага разрешён, посадка на
  занятую клетку запрещена), затем optional revive-PLACE: ровно та же
  повержённая Harpy (`fighterIds`), полное здоровье (`restoreFullHealth`),
  клетка только в зоне Medusa (`zoneFighterName`); «(if any)»: нет поверженных
  → revive-pending не создаётся.
- **The Hounds of Mighty Zeus**: после боя по одному pending на КАЖДУЮ живую
  Harpy (поверженные исключены; 0 живых → карта неиграбельна по баннеру).
- **Gaze of Stone** (WON → +8 урона; LOST → нет) и **Second Shot** (BOOST ПОСЛЕ
  reveal через `BOOST_CHOICE` pending — см. секцию тайминга выше; карта не
  покидает руку при объявлении атаки, выбранная после reveal идёт в сброс,
  её значение — в `combatInfo.boostValue`) — реальные бои в спеках.
- **Feint** (Medusa): реальный бой — защитный Feint ОТМЕНЯЕТ эффекты атакующей
  карты (печатное значение сохранено, эффекты Snipe не исполнились).
- **Dash**: реальный бой → optional MOVE 3 pending, резолв клеткой или decline.
- **Regroup**: реальный бой → WON draw 2 / LOST draw 1 (оба прогона, seeded
  drawPile).
- **Snipe**: реальный бой → безусловный draw 1.
- **Hiss and Slither / Clutching Claws** («Your opponent discards 1 card.» —
  БЕЗ «random»): сбрасывающий ОППОНЕНТ выбирает карту САМ — persisted
  `DISCARD_CARDS` pending (owner-bound, боевая цепочка паузится и продолжается
  после выбора; пустая рука → no-op; replay/foreign/не-голова/decline —
  отклоняются; pending не содержит содержимого руки). Random-варианты текста
  парсятся в другие типы (BOOST/OPPONENT_RANDOM_HAND) и сюда не попадают.

## Адаптеры (матчи не зависают)

- AI: `decidePending` TARGET_FIGHTER → слабейшая живая цель; все цели мертвы →
  decline. Revive-PLACE → свободная клетка зоны anchor; зона полна → decline.
  DISCARD_CARDS → сбрасывает наименее ценную карту (min boostValue).
  BOOST_CHOICE → МИНИмальная достаточная карта (меняет исход боя), иначе
  decline. Dispatch `resolveTarget`/`resolveDiscard`/`resolveBoost` →
  `resolvePendingEffect`.
- Web: WirePendingEffect/WireCombatInfo расширены (см. `gameStateAdapter.ts`);
  `attack(…, abilityBoostCardId)` (карточного boost-параметра больше НЕТ —
  выбор после reveal), `resolvePendingEffect` без x/y + `cardIds`
  (DISCARD_CARDS/BOOST_CHOICE); GameView: клик по цели TARGET_FIGHTER одним
  кликом, revive (повержённый боец → клетка зоны), выбор ability-BOOST карты
  у Arthur + подсказка, DISCARD_CARDS — клик по своей карте (value > 1 —
  мультивыбор + кнопка «Сбросить»), BOOST_CHOICE — клик по ОДНОЙ своей карте
  или кнопка «Отказаться» (generic optional-decline).
- Admin GameTester: `peffect <id> <f>` (без клетки),
  `peffect <id> card <c0> [<c1> ...]` (DISCARD_CARDS — сколько требует
  pending.value; BOOST_CHOICE — ровно одна), `pdecline <id>`,
  `attack <f1> <f2> <c> [abilityBoost]`, `defense <c>`.

## Прогоны

Backend: full regression 1048 pass / 3 known auth fails
(`auth.service.spec`, базлайн пре-существующий; базлайн спринта 966/3, +82);
tsc чист, build OK. Admin: tsc -b чист. Frontend: vitest src 13/13 (базлайн
сохранён). Root vite build заблокирован пре-существующим отсутствующим
`src/phaser/assets/gameAssetManifest` (не трекается этим траком).
