# Geralt of Rivia — CP-31 portrait source

Статус: **blocked by image generation service; no image produced**.

Портрет Geralt of Rivia не создан: встроенный image_gen вернул HTTP400 moderation_blocked на этапе output (category other). Сохранены точный промпт, reference SHA, preflight, фактическая ошибка и request ID. PNG отсутствует; неуспешный вызов учитывается как один вызов, не как готовый ассет.

Reference status: **user override to proceed; formal card remains return_to_stage_1**. Формальная карточка остаётся `return_to_stage_1`, score 6.3; пользовательский override не превращён в formal pass.

Готового изображения и review-растра нет. `attempts.json`/`tool-error-g1.json` содержат фактический отказ; промпт для обхода отказа не менялся.

Ограничения:

- HTTP400 moderation_blocked at output, category other; exact error and request ID in tool-error-g1.json.
- No generated image, source candidate, dimensions or crop proof can be supplied for this call.
- Current source uses a user override; formal card score6.3/return_to_stage_1 is unchanged.
- No prompt workaround, alternate generator or paid fallback was attempted.

Подтверждены live owner и raw slug; проверено отсутствие исходного портретного key. Это только предложение исходника: runtime, Unreal, канонический design-front, formal acceptance, общие registry/ledger/git не менялись. Источники и SHA — в preflight/source-hashes-before/verification; точный запрос — prompt-g1.txt.
