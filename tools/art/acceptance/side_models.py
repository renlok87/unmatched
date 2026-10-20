#!/usr/bin/env python3
"""Профили приёмщиков и побочные модели после отмены подписки ChatGPT (AGENTS.md «AI tools and side models», 2026-10-20).

Codex, `codex exec`, приёмщик Sol (`gpt-6.1-sol`) и GPT Astra отключены 2026-10-20. Полосы, которые их звали,
падают с ошибкой CODEX_GONE / SOL_GONE до любого запуска процесса. Карточки с профилем «Sol 6.1 xhigh» от
2026-10-20 и раньше остаются валидными: это история, а не новый запуск.

Приёмщик по умолчанию — «Opus xhigh»: Workflow `.claude/workflows/second-acceptor.js` по аргументам, которые готовят
`sheet_acceptance.py prepare` (лист 1c), `run_clip_acceptors.py` (клипы 7a.2) и `_output_schema.py --workflow-args`
(модель). Второй профиль — «Z-Code GLM-5.3-Flash» (видит кадры; GLM-5.3 в тарифе пользователя только текст): его
GUI-путь — приложение Z-Code через Computer Use. Скриптовая полоса Z-Code — заглушка `zcode_headless()`: headless
`resources\\glm\\zcode.cjs -p … --attach … --json` останавливается на «Select a model before sending a message», пока
пользователь сам не выполнит `zcode login zai` (вход через браузер — шаг пользователя, агент не логинится). Пока
полосы нет, второй приёмщик — Opus `second-acceptor` в свежем контексте (пара — `validate_card.py --same-profile-ok`).

    python tools/art/acceptance/side_models.py zcode-probe   # код 2 и причина, пока headless-полосы нет
"""
from __future__ import annotations

import argparse
import sys

RETIRED_ON = "2026-10-20"
RULE = "AGENTS.md «AI tools and side models»"

OPUS = "Opus xhigh"
SOL = "Sol 6.1 xhigh"
ZCODE_FLASH = "Z-Code GLM-5.3-Flash"
PROFILES = (OPUS, SOL, ZCODE_FLASH)           # enum acceptor.profile полной схемы карточки
RETIRED_PROFILES = {SOL: RETIRED_ON}           # профиль → последний день, которым датируется его карточка

CODEX_GONE = (f"Codex отключён {RETIRED_ON} (подписка ChatGPT отменена), см. {RULE}: `codex exec`, приложение "
              "ChatGPT и полосы Codex не запускаются. Изображения — приложение Gemini через Computer Use, побочная "
              "модель — Z-Code GLM-5.3")
SOL_GONE = (f"Sol отключён {RETIRED_ON} (подписка ChatGPT отменена), см. {RULE}: приёмщик «{SOL}» больше не "
            f"запускается. Приёмщик по умолчанию — «{OPUS}» (Workflow second-acceptor), второй профиль — "
            f"«{ZCODE_FLASH}»")
ZCODE_HEADLESS = ("Полоса Z-Code (headless `zcode.cjs -p … --attach …`) пока не работает: CLI без входа в Z.AI "
                  "отвечает «Select a model before sending a message». Нужен разовый `zcode login zai` пользователя "
                  "(вход через браузер, агент его не делает), затем проба. До этого: Z-Code GLM-5.3-Flash через "
                  f"Computer Use или Opus `second-acceptor` в свежем контексте ({RULE})")


class SideModelUnavailable(RuntimeError):
    """Внешняя модель отключена или её полоса ещё не работает."""


def zcode_headless(*_args, **_kwargs):
    """Заглушка скриптовой полосы Z-Code (приёмщик «Z-Code GLM-5.3-Flash»): всегда SideModelUnavailable."""
    raise SideModelUnavailable(ZCODE_HEADLESS)


def retired_profile_error(profile: str | None, date: str | None) -> str | None:
    """Ошибка карточки отключённого профиля, датированной позже дня отключения; старые карточки — None."""
    last = RETIRED_PROFILES.get(profile or "")
    if last and isinstance(date, str) and date[:10] > last:
        return ("acceptor.profile «%s» на карточке от %s: %s" % (profile, date[:10], SOL_GONE if profile == SOL
                                                                  else "профиль отключён %s" % last))
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
