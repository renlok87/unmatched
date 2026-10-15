# Philippa — CP-31 portrait source

Статус: **source-candidate-only**.

Оригинальный портретный исходник Philippa создан одним вызовом встроенного image_gen по собственному current design-front. Голова/волосы и ворот помещаются в full100 circle; цветной и серый обзор 80/160 и native40/80 осмотрены. Дополнительный вызов не использован: обрезки головы или потери основных признаков не обнаружено.

Reference status: **user override applied; formal paired result remains return_to_stage_1**. Формальная карточка остаётся `pass`, score 8.1; пользовательский override не превращён в formal pass.

Размер: 1254×1254. `original-g1.png` и `portrait-source-candidate.png` — точные побайтные копии автоматического оригинала, без ретуши/ресайза/обрезки/пересохранения. Только review/ содержит отдельно обозначенные производные для проверки.

Ограничения:

- About 8% above the hair instead of the requested 18%; full hair and high collar fit inside the full100 circle.
- Formal paired result remains return_to_stage_1 at7.5 despite a recorded user override to proceed. Portrait source generation does not change either record or authorize runtime import.
- Outer shoulder/chest corners are cut by the circular mask; keep full100 without tighter zoom.
- No runtime widget, DPI, interaction state, UE import or independent acceptance tested by this producing agent.

Подтверждены live owner и raw slug; проверено отсутствие исходного портретного key. Это только предложение исходника: runtime, Unreal, канонический design-front, formal acceptance, общие registry/ledger/git не менялись. Источники и SHA — в preflight/source-hashes-before/verification; точный запрос — prompt-g1.txt.
