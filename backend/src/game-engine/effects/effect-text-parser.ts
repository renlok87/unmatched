/**
 * Effect Text Parser
 *
 * Текстовые поля карт (effectImmediately/During/After) → структурированные
 * CardEffect[]. Чистый модуль без Nest DI — импортируется из prisma-скрипта
 * (backfill-card-effects.ts) и тестов.
 *
 * Принципы:
 * - Тайминг задаётся полем-источником: immediately → ON_REVEAL,
 *   during → DURING_COMBAT, after → AFTER_COMBAT; boost/ongoing → UNSUPPORTED.
 * - Сначала компаунд-матчеры по полному тексту, затем разбивка на предложения
 *   и по-предложенный матчинг.
 * - Нераспознанное предложение → UNSUPPORTED с исходным текстом: игра не
 *   блокируется, текст едет в manualEffects.
 * - Каждый эффект несёт text (исходное предложение), source: 'parser',
 *   parserVersion — повторный backfill не трогает source: 'manual'.
 */

import {
  CardEffect,
  EffectCondition,
  EffectTiming,
  EffectType,
  EffectTarget,
} from '../models/card.model';

export const PARSER_VERSION = 8;

export interface CardEffectTexts {
  readonly immediately?: string | null;
  readonly during?: string | null;
  readonly after?: string | null;
  readonly boost?: string | null;
  readonly ongoing?: string | null;
  /** S05 (GD-019): ПОЛНЫЙ печатный текст SCHEME-карты (Prisma Card.text) —
   *  fallback для карт, у которых ВСЕ effect*-поля пусты, а эффект напечатан
   *  только общим текстом (A Momentary Glance, Winged Frenzy, …). Парсится
   *  с AFTER_COMBAT («после розыгрыша») — тот же тайминг, что effectAfter:
   *  executeOnPlayEffects исполняет его при playScheme. Игнорируется, если
   *  хоть один effect*-слот непуст (защита от дублей эффектов). */
  readonly fullText?: string | null;
}

export interface ParseResult {
  readonly effects: CardEffect[];
  /** Предложения, не распознанные ни одним матчером (для отчёта покрытия) */
  readonly unsupported: string[];
}

/** Опция CHOOSE_ONE на стадии драфта (effects ещё не финализированы) */
type OptionDraft = { label: string; drafts: Draft[] };

/** Промежуточный эффект без id/text/source — их доклеивает finalize */
type Draft = Omit<CardEffect, 'id' | 'timing' | 'options'> & {
  timing?: EffectTiming;
  /** Внутреннее поле парсера: опции CHOOSE_ONE до finalize (→ options) */
  optionDrafts?: OptionDraft[];
};

// ---------------------------------------------------------------------------
// Публичный API
// ---------------------------------------------------------------------------

export function parseCardEffectTexts(texts: CardEffectTexts, cardId: string): ParseResult {
  const effects: CardEffect[] = [];
  const unsupported: string[] = [];

  const fields: Array<[keyof CardEffectTexts, EffectTiming | null]> = [
    ['immediately', EffectTiming.ON_REVEAL],
    ['during', EffectTiming.DURING_COMBAT],
    ['after', EffectTiming.AFTER_COMBAT],
    // BOOST-значение печатается на карте, отдельный текст редок (6 карт) — отложено
    ['boost', null],
    // постоянные эффекты (7 карт) — отложено
    ['ongoing', null],
  ];

  for (const [field, timing] of fields) {
    const raw = texts[field];
    if (!raw || !raw.trim()) continue;

    const seq = effects.length;
    if (timing === null) {
      const text = clean(raw);
      effects.push(finalize({ type: EffectType.UNSUPPORTED }, EffectTiming.AFTER_COMBAT, text, cardId, field, seq));
      unsupported.push(text);
      continue;
    }

    const parsed = parseFieldText(raw, timing);
    parsed.drafts.forEach((d, i) =>
      effects.push(finalize(d.draft, timing, d.text, cardId, field, seq + i)),
    );
    unsupported.push(...parsed.unsupported);
  }

  // S05 (GD-019): SCHEME fullText-fallback — только если ВСЕ effect*-слоты
  // пусты (никаких эффектов не собрано). Тайминг AFTER_COMBAT = «после
  // розыгрыша», его исполняет executeOnPlayEffects при playScheme.
  if (effects.length === 0 && texts.fullText && texts.fullText.trim()) {
    const seq = 0;
    const parsed = parseFieldText(texts.fullText, EffectTiming.AFTER_COMBAT);
    parsed.drafts.forEach((d, i) =>
      effects.push(finalize(d.draft, EffectTiming.AFTER_COMBAT, d.text, cardId, 'fullText', seq + i)),
    );
    unsupported.push(...parsed.unsupported);
  }

  return { effects, unsupported };
}

/** Разобрать текст одного поля (с известным таймингом) */
export function parseFieldText(
  raw: string,
  timing: EffectTiming,
): { drafts: Array<{ draft: Draft; text: string }>; unsupported: string[] } {
  const text = clean(raw);
  const drafts: Array<{ draft: Draft; text: string }> = [];
  const unsupported: string[] = [];

  // --- Lurking-форма: заголовок CHOOSE_ONE НЕ в начале —
  //     «Draw N cards and choose 1 effect: - … - …». Отщепляем DRAW,
  //     остаток («choose …») отдаём matchChooseOne. ---
  const lurking = /^draw (\d+|one|two|three) cards? and (choose .+)$/i.exec(text);
  if (lurking) {
    const chooseTail = matchChooseOne(lurking[2]);
    if (chooseTail) {
      drafts.push({ draft: { type: EffectType.DRAW_CARD, value: toNumber(lurking[1]) }, text });
      drafts.push({ draft: chooseTail, text });
      for (const opt of chooseTail.optionDrafts ?? []) {
        if (opt.drafts.some((d) => d.type === EffectType.UNSUPPORTED)) unsupported.push(opt.label);
      }
      return { drafts, unsupported };
    }
    // choose не распознан — продолжаем обычным путём
  }

  // --- CHOOSE_ONE: «Choose one: …» со списком альтернатив (раньше compound,
  //     т.к. опции пересекают границы предложений) ---
  const choose = matchChooseOne(text);
  if (choose) {
    drafts.push({ draft: choose, text });
    // нераспознанные опции — в отчёт покрытия (помогает докручивать под-матчеры)
    for (const opt of choose.optionDrafts ?? []) {
      if (opt.drafts.some((d) => d.type === EffectType.UNSUPPORTED)) unsupported.push(opt.label);
    }
    return { drafts, unsupported };
  }

  // --- «Do both: - … - …» — плоская последовательность под-эффектов (НЕ выбор).
  //     Список буллетов пересекает границы предложений → раньше splitSentences. ---
  const both = matchDoBoth(text);
  if (both) {
    both.drafts.forEach((draft) => drafts.push({ draft, text }));
    unsupported.push(...both.unsupported);
    return { drafts, unsupported };
  }

  // --- Компаунд-матчеры по полному тексту (несколько предложений = один смысл) ---
  const compound = matchCompound(text);
  if (compound) {
    compound.forEach((draft) => drafts.push({ draft, text }));
    return { drafts, unsupported };
  }

  // --- По предложениям ---
  for (const sentence of splitSentences(text)) {
    const parsed = parseSentence(sentence);
    if (parsed) {
      parsed.forEach((draft) => drafts.push({ draft, text: sentence }));
    } else {
      drafts.push({ draft: { type: EffectType.UNSUPPORTED }, text: sentence });
      unsupported.push(sentence);
    }
  }

  return { drafts, unsupported };
}

// ---------------------------------------------------------------------------
// Компаунд-матчеры (полный текст)
// ---------------------------------------------------------------------------

function matchCompound(text: string): Draft[] | null {
  // «Draw 1 card. If you won the combat, draw 2 cards instead.»
  // Семантика: выиграл → 2, иначе → 1 (ничья — победа защитника)
  if (/^draw 1 card\.\s*if you won the combat,? draw 2 cards instead\.?$/i.test(text)) {
    return [
      { type: EffectType.DRAW_CARD, value: 1, when: { kind: 'LOST_COMBAT' } },
      { type: EffectType.DRAW_CARD, value: 2, when: { kind: 'WON_COMBAT' } },
    ];
  }

  // Winged Frenzy (S05): «Move each of your fighters up to 3 spaces. You may
  // move them through spaces containing opposing fighters. Then, return a
  // defeated Harpy (if any) to any space in Medusa's zone.»
  // (скобочные пояснения — включая «(if any)» — уже вырезаны clean())
  const frenzy =
    /^move each of your fighters up to (\d+) spaces?\.\s*you may move them through spaces containing opposing fighters\.\s*then, return a defeated ([\w.' ]+?) to any space in ([\w.' ]+?)'s zone\.?$/i.exec(
      text,
    );
  if (frenzy) {
    return [
      {
        type: EffectType.MOVE,
        value: Number(frenzy[1]),
        target: EffectTarget.EACH_OWN_FIGHTER,
        canPassThroughEnemies: true,
      },
      {
        type: EffectType.RETURN_DEFEATED,
        fighterName: frenzy[2].trim(),
        zoneFighterName: frenzy[3].trim(),
        optional: true,
      },
    ];
  }

  // «Discard the top card of your deck. Add its BOOST value to this card's value.»
  if (
    /^discard the top card of your deck\.\s*add its BOOST value to this card'?s(?: attack)? value\.?$/i.test(
      text,
    )
  ) {
    return [{ type: EffectType.BOOST, boostSource: 'SELF_DECK_TOP' }];
  }

  // «Your opponent discards 1 random card. Add its BOOST value to this card's value.»
  if (
    /^your opponent discards 1 random card\.\s*add its BOOST value to this card'?s value\.?$/i.test(
      text,
    )
  ) {
    return [{ type: EffectType.BOOST, boostSource: 'OPPONENT_RANDOM_HAND' }];
  }

  // «...value of this card is equal to the number of cards in your hand...»
  if (/value of this card is equal to the number of cards in your hand/i.test(text)) {
    return [
      { type: EffectType.SET_VALUE, value: 0 },
      { type: EffectType.VALUE_PER_COUNT, count: { source: 'CARDS_IN_HAND', per: 1 } },
    ];
  }

  return null;
}

// ---------------------------------------------------------------------------
// CHOOSE_ONE — «Choose one[ effect][:|.] - опция - опция …»
// ---------------------------------------------------------------------------

/**
 * Распознаёт карты-«Choose one» с маркированным списком альтернативных
 * эффектов (Utility Belt, Technodrome, Riposte, Shapershifter, Looking Glass).
 * Каждая опция разбирается рекурсивно через parseSentence; нераспознанная →
 * UNSUPPORTED (label сохраняется для UI/лога).
 *
 * НЕ матчит: «Choose one of the fighters …» (выбор ЦЕЛИ, не альтернатив) и
 * «… do both: …» (Shrink — оба эффекта, не выбор).
 */
function matchChooseOne(text: string): Draft | null {
  if (/\bdo both\b/i.test(text)) return null;
  // «Choose one:» | «Choose one effect:» | «Choose 2 different effects:»
  const m =
    /^choose (?:(one|two|three|\d+) (?:different )?effects?|(one))\s*[:.]\s*(.+)$/i.exec(text);
  if (!m) return null;

  const count = m[1] ? toNumber(m[1]) : 1;
  const remainder = m[3];

  // Опции разделены буллетами «-» / «•» (после clean переносы строк → пробелы);
  // у некоторых карт перед дефисом стоит запятая (Utility Belt).
  const labels = remainder
    .split(/\s*[-•]\s*/)
    .map((s) => s.replace(/,\s*$/, '').trim())
    .filter((s) => s.length > 0);

  // Меньше двух опций — это не список выбора, отдаём на обычный разбор.
  if (labels.length < 2) return null;

  const optionDrafts: OptionDraft[] = labels.map((label) => ({
    label,
    drafts: parseSentence(label) ?? [{ type: EffectType.UNSUPPORTED }],
  }));

  return { type: EffectType.CHOOSE_ONE, chooseCount: count, optionDrafts };
}

// ---------------------------------------------------------------------------
// «Do both: - … - …» — плоская последовательность (НЕ выбор)
// ---------------------------------------------------------------------------

/**
 * Распознаёт «Do both: -опция -опция» — оба под-эффекта применяются (в отличие
 * от CHOOSE_ONE). Каждый буллет разбирается рекурсивно через parseSentence;
 * нераспознанный → UNSUPPORTED-draft (плюс в отчёт покрытия).
 *
 * Допустимы префиксы перед «do both» («Choose one effect. If …, do both: …»):
 * берём хвост после «do both:» — список под-эффектов.
 */
function matchDoBoth(
  text: string,
): { drafts: Draft[]; unsupported: string[] } | null {
  const m = /\bdo both\s*:\s*(.+)$/i.exec(text);
  if (!m) return null;

  const labels = m[1]
    .split(/\s*[-•]\s*/)
    .map((s) => s.replace(/,\s*$/, '').trim())
    .filter((s) => s.length > 0);
  if (labels.length < 2) return null;

  const drafts: Draft[] = [];
  const unsupported: string[] = [];
  for (const label of labels) {
    const parsed = parseSentence(label);
    if (parsed) {
      drafts.push(...parsed);
    } else {
      drafts.push({ type: EffectType.UNSUPPORTED });
      unsupported.push(label);
    }
  }
  return { drafts, unsupported };
}

// ---------------------------------------------------------------------------
// По-предложенные матчеры
// ---------------------------------------------------------------------------

/** null — не распознано */
function parseSentence(sentence: string): Draft[] | null {
  const s = sentence.trim().replace(/\.+$/, '');

  // «… unless 🪙[ 🪙]» (Blackbeard): эффект происходит, ЕСЛИ оппонент НЕ платит
  // дублоны. Платёжной механики нет → базовый эффект как optional (оппонент
  // может негировать). Отщепляем хвост «unless …», базу разбираем рекурсивно.
  const unless = /^(.+?)\s+unless\b.*$/i.exec(s);
  if (unless) {
    const base = parseSentence(unless[1]);
    if (!base) return null; // незнакомая база — UNSUPPORTED целиком (не регресс)
    return base.map((d) => ({ ...d, optional: true }));
  }

  // Именованный боец смежен с врагом → лечение: «If <Name> is adjacent to an
  // opposing fighter, <he|she|they> recovers N health.» / «… your fighter …».
  const adjHeal =
    /^if ([\w.' ]+?) is adjacent to an opposing fighter,?\s*(?:he|she|they|it|your fighter)?\s*recovers? (\d+) health$/i.exec(
      s,
    );
  if (adjHeal) {
    const who = adjHeal[1].trim();
    const when: EffectCondition = { kind: 'ADJACENT_TO_OPPONENT' };
    if (/^your fighter$/i.test(who)) {
      return [{ type: EffectType.HEAL, value: Number(adjHeal[2]), target: EffectTarget.SELF, when }];
    }
    return [
      {
        type: EffectType.HEAL,
        value: Number(adjHeal[2]),
        target: EffectTarget.NAMED_FIGHTER,
        fighterName: who,
        when,
      },
    ];
  }

  // Обёртки-условия: рекурсивный разбор остатка
  const won = /^if you won the combat,?\s*(.+)$/i.exec(s);
  if (won) return wrapWhen(won[1], { kind: 'WON_COMBAT' });

  const lost = /^if you lost (?:the |a )?combat,?\s*(.+)$/i.exec(s);
  if (lost) return wrapWhen(lost[1], { kind: 'LOST_COMBAT' });

  // Зонные условия (C1, мультизонность): «If Ms. Marvel's space shares no
  // zones with the opposing fighter, draw 2 cards.»
  const noZones =
    /^if (?:[\w.' ]+?'s space|your fighter'?s? space) shares no zones? with the opposing fighter,?\s*(.+)$/i.exec(s);
  if (noZones) return wrapWhen(noZones[1], { kind: 'NOT_SHARES_ZONE_WITH_OPPONENT' });

  const sharesZone =
    /^if (?:[\w.' ]+?'s space|your fighter'?s? space) shares (?:a|any) zones? with the opposing fighter,?\s*(.+)$/i.exec(s);
  if (sharesZone) return wrapWhen(sharesZone[1], { kind: 'SHARES_ZONE_WITH_OPPONENT' });

  // «X and Y» — плоская последовательность двух под-эффектов в одном
  // предложении («draw 1 card and gain 1 action»). Дробим по ПЕРВОМУ « and »;
  // принимаем ТОЛЬКО если ОБА куска распознаны как самостоятельные эффекты,
  // иначе откатываемся к одиночным матчерам (не ломаем «… up to N spaces»,
  // «… and choose …» и пр., где вторая половина не парсится сама по себе).
  const andSeq = parseAndSequence(s);
  if (andSeq) return andSeq;

  // CANCEL_EFFECTS
  if (/^cancel all effects on your opponent'?s card$/i.test(s)) {
    return [{ type: EffectType.CANCEL_EFFECTS }];
  }

  // DRAW
  const draw = /^draw (\d+|one|two|three) cards?$/i.exec(s);
  if (draw) return [{ type: EffectType.DRAW_CARD, value: toNumber(draw[1]) }];

  // DAMAGE
  const dmg = /^deal (\d+) damage to (.+)$/i.exec(s);
  if (dmg) {
    const target = parseDamageTarget(dmg[2]);
    if (!target) return null;
    return [{ type: EffectType.DAMAGE, value: Number(dmg[1]), ...target }];
  }

  // MOVE (исполнение в MVP — manualEffects: требует выбора игрока)
  const move = /^(you may )?move (.+?) up to (\d+) spaces?\b.*$/i.exec(s);
  if (move) {
    return [
      {
        type: EffectType.MOVE,
        value: Number(move[3]),
        optional: true,
        ...parseFighterRef(move[2]),
      },
    ];
  }

  // MOVE без «up to» — точное число клеток («Move Jill Trent 1 space»).
  // ВАЖНО: проверяется ПОСЛЕ «up to»-матчера, иначе «up to 3 spaces»
  // ложно срабатывает здесь как «3 spaces».
  const moveExact = /^(you may )?move (.+?) (\d+) spaces?\b.*$/i.exec(s);
  if (moveExact) {
    return [
      {
        type: EffectType.MOVE,
        value: Number(moveExact[3]),
        optional: Boolean(moveExact[1]),
        ...parseFighterRef(moveExact[2]),
      },
    ];
  }

  // «Choose one of the fighters in the combat and move them up to N spaces»
  // (Skirmish ~20 копий, Into Darkness, Leap Away, Infinity Mirror) — выбор
  // ЦЕЛИ + перемещение, не буллет-список → matchChooseOne его не ловит.
  // MVP: target SELF (двигается свой боец, не любой из боя). Опц. префикс
  // «if you won the combat» → when WON_COMBAT.
  const chooseFighterMove =
    /^(if you won the combat,?\s*)?choose one of the fighters in the combat and move (?:them|it) up to (\d+) spaces?$/i.exec(
      s,
    );
  if (chooseFighterMove) {
    const draft: Draft = {
      type: EffectType.MOVE,
      value: Number(chooseFighterMove[2]),
      optional: false,
      target: EffectTarget.SELF,
      ...(chooseFighterMove[1] ? { when: { kind: 'WON_COMBAT' } as EffectCondition } : {}),
    };
    return [draft];
  }

  // PLACE (manualEffects) — «in any space» и «in any other space» (Looking Glass)
  const place = /^(you may )?place (.+?) in any( other)? spaces?\b.*$/i.exec(s);
  if (place) {
    return [{ type: EffectType.PLACE, optional: Boolean(place[1]), ...parseFighterRef(place[2]) }];
  }

  // SET_VALUE (+ опциональное условие в префиксе)
  const setVal =
    /^(?:if (.+?),\s*)?(?:the value of this card|this card'?s value) is (?:a )?(\d+)(?: instead)?$/i.exec(
      s,
    );
  if (setVal) {
    const draft: Draft = { type: EffectType.SET_VALUE, value: Number(setVal[2]) };
    if (setVal[1]) {
      const when = parseInlineCondition(setVal[1]);
      if (!when) return null; // незнакомое условие — UNSUPPORTED целиком
      return [{ ...draft, when }];
    }
    return [draft];
  }

  // VALUE_PER_COUNT
  const perCount = /^add \+?(\d+) to this card'?s value for each (.+)$/i.exec(s);
  if (perCount) {
    const per = Number(perCount[1]);
    const what = perCount[2];
    if (/^other friendly fighter adjacent to the opposing fighter$/i.test(what)) {
      return [
        {
          type: EffectType.VALUE_PER_COUNT,
          count: { source: 'FRIENDLY_ADJACENT_TO_OPPONENT', per },
        },
      ];
    }
    const discardPrefix = /^other ([\w-]+) cards? in your discard pile$/i.exec(what);
    if (discardPrefix) {
      return [
        {
          type: EffectType.VALUE_PER_COUNT,
          count: { source: 'DISCARD_NAME_PREFIX', namePrefix: discardPrefix[1], per },
        },
      ];
    }
    return null;
  }

  // BOOST / BLIND BOOST
  if (/^you may BLIND BOOST this (?:attack|card|defense)$/i.test(s) || /^BLIND BOOST this card$/i.test(s)) {
    return [{ type: EffectType.BOOST, boostSource: 'SELF_DECK_TOP', blind: true, optional: true }];
  }
  if (/^you may BOOST this (?:attack|card|defense)(?: up to (\d+) times)?$/i.test(s)) {
    return [{ type: EffectType.BOOST, boostSource: 'PLAYER_CHOICE_HAND', optional: true }];
  }

  // OPPONENT_DISCARD — только БЕЗ «random»: сбрасывающий оппонент выбирает
  // карту сам (persisted DISCARD_CARDS, выбор владельца руки). Вариант «random»
  // с добором значения («…Add its BOOST value…») — отдельный компаунд BOOST
  // (OPPONENT_RANDOM_HAND) выше; чистый «discards N random cards» без второй
  // фразы движком не исполняется → честный UNSUPPORTED, а не выбор игрока.
  const oppDiscard = /^your opponent discards (\d+) cards?$/i.exec(s);
  if (oppDiscard) {
    return [
      {
        type: EffectType.OPPONENT_DISCARD,
        value: Number(oppDiscard[1]),
        target: EffectTarget.OPPONENT_PLAYER,
      },
    ];
  }

  // HEAL: «Recover 2 health» (self) / «Daredevil recovers 2 health» (named)
  const heal = /^(?:([A-Z][\w.' ]*?) )?recovers? (\d+) health$/i.exec(s);
  if (heal) {
    if (heal[1] && !/^you$/i.test(heal[1])) {
      return [
        {
          type: EffectType.HEAL,
          value: Number(heal[2]),
          target: EffectTarget.NAMED_FIGHTER,
          fighterName: heal[1].trim(),
        },
      ];
    }
    return [{ type: EffectType.HEAL, value: Number(heal[2]), target: EffectTarget.SELF }];
  }

  // GAIN_ACTION (с «unless …» — не распознаём)
  const gain = /^gain (\d+) actions?$/i.exec(s);
  if (gain) return [{ type: EffectType.GAIN_ACTION, value: Number(gain[1]) }];

  // RETURN_TO_HAND
  if (/^return this card to your hand$/i.test(s)) {
    return [{ type: EffectType.RETURN_TO_HAND }];
  }

  // IMMOBILIZE
  if (/^the opposing fighter cannot leave (?:their|her|his|its) space (?:this turn|for the rest of the turn)$/i.test(s)) {
    return [{ type: EffectType.IMMOBILIZE, target: EffectTarget.OPPOSING_FIGHTER }];
  }

  // PREVENT_DAMAGE
  if (/^prevent all damage$/i.test(s)) {
    return [{ type: EffectType.PREVENT_DAMAGE }];
  }

  // END_TURN
  if (/^end the turn$/i.test(s)) {
    return [{ type: EffectType.END_TURN }];
  }

  return null;
}

/**
 * «X and Y» → [X-эффекты, Y-эффекты] при условии, что ОБА куска парсятся.
 * Перебираем все позиции « and » (слева направо), берём первую, где обе
 * половины распознаны. Это «do both»-семантика внутри одного предложения.
 * Без « and » или если ни одно разбиение не даёт двух валидных частей → null.
 */
function parseAndSequence(s: string): Draft[] | null {
  // быстрый выход: нет « and » — нечего дробить
  if (!/\band\b/i.test(s)) return null;
  const parts = s.split(/\s+and\s+/i);
  if (parts.length < 2) return null;

  // перебираем точки разреза: левая = первые k частей, правая = остаток
  for (let k = 1; k < parts.length; k++) {
    const left = parts.slice(0, k).join(' and ');
    const right = parts.slice(k).join(' and ');
    const l = parseSentence(left);
    if (!l) continue;
    const r = parseSentence(right);
    if (!r) continue;
    return [...l, ...r];
  }
  return null;
}

/** Рекурсивная обёртка условия на все эффекты остатка предложения */
function wrapWhen(rest: string, when: EffectCondition): Draft[] | null {
  const inner = parseSentence(rest);
  if (!inner) return null;
  return inner.map((d) => ({ ...d, when }));
}

function parseDamageTarget(
  phrase: string,
): Pick<Draft, 'target' | 'fighterName'> | null {
  const p = phrase.trim();
  if (/^the opposing fighter$/i.test(p)) return { target: EffectTarget.OPPOSING_FIGHTER };
  if (/^an adjacent opposing fighter$/i.test(p)) return { target: EffectTarget.ADJACENT_ENEMY };
  if (/^each opposing fighter adjacent to your fighter$/i.test(p)) {
    return { target: EffectTarget.ENEMIES_ADJACENT_TO_SELF };
  }
  // A Momentary Glance (S05): «any one fighter in Medusa's zone» — все живые
  // бойцы (включая своих) в зоне именованного бойца; цель выбирает владелец.
  const inZone = /^any one fighter in ([\w.' ]+?)'s zone$/i.exec(p);
  if (inZone) {
    return { target: EffectTarget.ANY_FIGHTER_IN_ZONE, fighterName: inZone[1].trim() };
  }
  // «a fighter adjacent to Daredevil» — смежный с именованным бойцом;
  // MVP: трактуем как ADJACENT_ENEMY (выбор цели — manualEffects/warn)
  const adjNamed = /^an? fighter adjacent to ([A-Z][\w.' ]*)$/i.exec(p);
  if (adjNamed) {
    return { target: EffectTarget.ADJACENT_ENEMY, fighterName: adjNamed[1].trim() };
  }
  return null;
}

/** «your fighter» / «Daredevil» / «each Harpy» / «one of your fighters» */
function parseFighterRef(phrase: string): Pick<Draft, 'target' | 'fighterName'> {
  const p = phrase.trim();
  if (/^(your fighter|one of your fighters|this fighter)$/i.test(p)) {
    return { target: EffectTarget.SELF };
  }
  if (/^the opposing fighter$/i.test(p)) return { target: EffectTarget.OPPOSING_FIGHTER };
  // «each of your fighters» (Winged Frenzy) — не NAMED_FIGHTER-мусор
  if (/^each of your fighters$/i.test(p)) return { target: EffectTarget.EACH_OWN_FIGHTER };
  const each = /^each ([A-Z][\w.' ]*)$/i.exec(p);
  if (each) return { target: EffectTarget.NAMED_FIGHTER, fighterName: each[1].trim() };
  return { target: EffectTarget.NAMED_FIGHTER, fighterName: p };
}

function parseInlineCondition(cond: string): EffectCondition | null {
  const c = cond.trim().toLowerCase();
  if (/started this turn in a different space/.test(c)) return { kind: 'MOVED_THIS_TURN' };
  if (/no cards? in your deck/.test(c)) return { kind: 'DECK_EMPTY' };
  if (/opposing fighter is a hero/.test(c)) return { kind: 'OPPONENT_IS_HERO' };
  if (/you are attacking/.test(c)) return { kind: 'IS_ATTACKING' };
  if (/you are defending/.test(c)) return { kind: 'IS_DEFENDING' };
  const handAtMost = /you have (\d+) or fewer cards? in (?:your )?hand/.exec(c);
  if (handAtMost) return { kind: 'HAND_COUNT_AT_MOST', value: Number(handAtMost[1]) };
  // «is not adjacent» без зонной семантики
  if (/is not adjacent/.test(c)) return { kind: 'NOT_ADJACENT_TO_OPPONENT' };
  return null;
}

// ---------------------------------------------------------------------------
// Утилиты
// ---------------------------------------------------------------------------

/** Скобочные пояснения «(This is in addition…)» режем, пробелы схлопываем */
function clean(raw: string): string {
  return raw
    .replace(/\([^)]*\)/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

/** Разбивка на предложения с защитой аббревиатур (Dr. Watson) */
function splitSentences(text: string): string[] {
  const protectedText = text.replace(/\b(Dr|Mr|Mrs|Ms|St)\./g, '$1§');
  return protectedText
    .split(/(?<=\.)\s+/)
    .map((s) => s.replace(/§/g, '.').trim())
    .filter((s) => s.length > 0);
}

function toNumber(word: string): number {
  const map: Record<string, number> = { one: 1, two: 2, three: 3 };
  return map[word.toLowerCase()] ?? Number(word);
}

function finalize(
  draft: Draft,
  timing: EffectTiming,
  text: string,
  cardId: string,
  field: string,
  index: number,
): CardEffect {
  const { optionDrafts, ...rest } = draft;
  const resolvedTiming = draft.timing ?? timing;
  const base: CardEffect = {
    ...rest,
    id: `${cardId}-${field}-${index}`,
    timing: resolvedTiming,
    text,
    source: 'parser',
    parserVersion: PARSER_VERSION,
  };

  // CHOOSE_ONE: финализируем опции (наследуют тайминг родителя)
  if (optionDrafts) {
    return {
      ...base,
      options: optionDrafts.map((opt, o) => ({
        label: opt.label,
        effects: opt.drafts.map((d, i) =>
          finalize(d, resolvedTiming, opt.label, cardId, `${field}-${index}-opt${o}`, i),
        ),
      })),
    };
  }

  return base;
}
