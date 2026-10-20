#!/usr/bin/env python3
"""Профили приёмщиков и побочные модели после отмены подписки ChatGPT (AGENTS.md «AI tools and side models», 2026-10-20).

Codex, `codex exec`, приёмщик Sol (`gpt-6.1-sol`) и GPT Astra отключены 2026-10-20. Полосы, которые их звали,
падают с ошибкой CODEX_GONE / SOL_GONE до любого запуска процесса. Карточки с профилем «Sol 6.1 xhigh» от
2026-10-20 и раньше остаются валидными: это история, а не новый запуск.

Приёмщик по умолчанию (первый) — «Opus xhigh»: Workflow `.claude/workflows/second-acceptor.js` с effort xhigh по
аргументам, которые готовят `sheet_acceptance.py prepare` (лист 1c), `run_clip_acceptors.py` (клипы 7a.2) и
`_output_schema.py --workflow-args --first` (модель). Второй приёмщик «другим профилем» — «Opus high»: тот же
workflow с effort high в свежем контексте (решение пользователя 2026-10-21: «Хорошо, использую Opus High вместо Z-код
для приемщика.»); аргументы — `sheet_acceptance.py prepare-second`, `run_clip_acceptors.py --second`,
`_output_schema.py --workflow-args` без `--first`. Пара «Opus xhigh» + «Opus high» — два профиля, `validate_card.py
--second` принимает её без `--same-profile-ok`.

«Z-Code GLM-5.3-Flash» снят с приёмки 2026-10-21: калибровку визуального приёмщика не прошёл
(docs/art-pipeline/evidence/skill-batch-2026-10-20/zcode-calibration/RESULT.md). Карточки с ним, датированные позже,
— ошибка; `--acceptor zcode` полос приёмки — код 2 (ZCODE_GONE). Z-Code остаётся побочной моделью для текста через
Computer Use; его скриптовая полоса — заглушка `zcode_headless()`: headless `resources\\glm\\zcode.cjs -p … --attach …
--json` останавливается на «Select a model before sending a message», пока пользователь сам не выполнит
`zcode login zai` (вход через браузер — шаг пользователя, агент не логинится).

    python tools/art/acceptance/side_models.py zcode-probe   # код 2 и причина, пока headless-полосы нет
"""
from __future__ import annotations

import argparse
import sys

RETIRED_ON = "2026-10-20"
RULE = "AGENTS.md «AI tools and side models»"
ZCODE_CALIBRATION = "docs/art-pipeline/evidence/skill-batch-2026-10-20/zcode-calibration/RESULT.md"

OPUS = "Opus xhigh"                            # первый приёмщик (по умолчанию)
OPUS_HIGH = "Opus high"                        # второй приёмщик «другим профилем» (с 2026-10-21)
SOL = "Sol 6.1 xhigh"
ZCODE_FLASH = "Z-Code GLM-5.3-Flash"
PROFILES = (OPUS, OPUS_HIGH, SOL, ZCODE_FLASH)  # enum acceptor.profile полной схемы карточки
RETIRED_PROFILES = {SOL: RETIRED_ON,           # профиль → последний день, которым датируется его карточка
                    ZCODE_FLASH: "2026-10-21"}
FIRST = OPUS
SECOND = OPUS_HIGH
EFFORT = {OPUS: "xhigh", OPUS_HIGH: "high"}    # профиль → effort агента Workflow second-acceptor

CODEX_GONE = (f"Codex отключён {RETIRED_ON} (подписка ChatGPT отменена), см. {RULE}: `codex exec`, приложение "
              "ChatGPT и полосы Codex не запускаются. Изображения — приложение Gemini через Computer Use, побочная "
              "модель — Z-Code GLM-5.3")
SOL_GONE = (f"Sol отключён {RETIRED_ON} (подписка ChatGPT отменена), см. {RULE}: приёмщик «{SOL}» больше не "
            f"запускается. Приёмщик по умолчанию — «{OPUS}» (Workflow second-acceptor, effort xhigh), второй профиль — "
            f"«{OPUS_HIGH}» (тот же workflow, effort high)")
ZCODE_GONE = (f"«{ZCODE_FLASH}» снят с приёмки 2026-10-21: калибровку визуального приёмщика не прошёл "
              f"({ZCODE_CALIBRATION}), см. {RULE}. Баллы он не ставит; второй приёмщик — «{OPUS_HIGH}» "
              "(Workflow second-acceptor, effort high, свежий контекст)")
ZCODE_HEADLESS = ("Полоса Z-Code (headless `zcode.cjs -p … --attach …`) пока не работает: CLI без входа в Z.AI "
                  "отвечает «Select a model before sending a message». Нужен разовый `zcode login zai` пользователя "
                  "(вход через браузер, агент его не делает), затем проба. До этого: Z-Code через Computer Use — "
                  f"текст и описание кадров без баллов ({RULE})")


class SideModelUnavailable(RuntimeError):
    """Внешняя модель отключена или её полоса ещё не работает."""


def zcode_headless(*_args, **_kwargs):
    """Заглушка скриптовой полосы Z-Code (побочная модель для текста): всегда SideModelUnavailable."""
    raise SideModelUnavailable(ZCODE_HEADLESS)


def effort_of(profile: str) -> str:
    """effort агента Workflow second-acceptor для профиля «Opus xhigh» / «Opus high»; иначе ValueError."""
    try:
        return EFFORT[profile]
    except KeyError:
        raise ValueError("профиль %r не запускается workflow second-acceptor: %s" % (profile, sorted(EFFORT))) from None


def retired_profile_error(profile: str | None, date: str | None) -> str | None:
    """Ошибка карточки отключённого профиля, датированной позже дня отключения; старые карточки — None."""
    last = RETIRED_PROFILES.get(profile or "")
    if last and isinstance(date, str) and date[:10] > last:
        reason = {SOL: SOL_GONE, ZCODE_FLASH: ZCODE_GONE}.get(profile, "профиль отключён %s" % last)
        return "acceptor.profile «%s» на карточке от %s: %s" % (profile, date[:10], reason)
    return None


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):  # UTF-8 и в пайпе cp1251
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("command", choices=("zcode-probe",))
    ap.parse_args(argv)
    try:
        zcode_headless()
    except SideModelUnavailable as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
