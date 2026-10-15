# Willow — CP-31 portrait source

Статус: **source-candidate-only**.

Оригинальный портретный исходник Willow создан одним вызовом встроенного image_gen по собственному current design-front. Голова/волосы и ворот помещаются в full100 circle; цветной и серый обзор 80/160 и native40/80 осмотрены. Дополнительный вызов не использован: обрезки головы или потери основных признаков не обнаружено.

Reference status: **unaccepted / return_to_stage_1; specifically authorized as portrait source only**. Формальная карточка остаётся `return_to_stage_1`, score 6.3; пользовательский override не превращён в formal pass.

Размер: 1254×1254. `original-g1.png` и `portrait-source-candidate.png` — точные побайтные копии автоматического оригинала, без ретуши/ресайза/обрезки/пересохранения. Только review/ содержит отдельно обозначенные производные для проверки.

Ограничения:

- About 6% above the hair instead of the requested 18%; whole head and main hair tips remain inside the full100 circle.
- The referenced figure is formally unaccepted (r2 score6.3) with no adjacent user override. Root specifically authorized this independent source-only portrait; this is not acceptance of that figure.
- Outer shoulder/chest corners are cut by the circular mask; keep full100 without tighter zoom.
- No runtime widget, DPI, interaction state, UE import or independent acceptance tested by this producing agent.

Подтверждены live owner и raw slug; проверено отсутствие исходного портретного key. Это только предложение исходника: runtime, Unreal, канонический design-front, formal acceptance, общие registry/ledger/git не менялись. Источники и SHA — в preflight/source-hashes-before/verification; точный запрос — prompt-g1.txt.
