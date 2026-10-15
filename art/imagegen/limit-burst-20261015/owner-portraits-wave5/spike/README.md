# Spike — CP-31 portrait source

Статус: **source-candidate-only**.

Оригинальный портретный исходник Spike создан одним вызовом встроенного image_gen по собственному current design-front. Голова/волосы и ворот помещаются в full100 circle; цветной и серый обзор 80/160 и native40/80 осмотрены. Дополнительный вызов не использован: обрезки головы или потери основных признаков не обнаружено.

Reference status: **formal 1a pass**. Формальная карточка остаётся `pass`, score 8.8; пользовательский override не превращён в formal pass.

Размер: 1254×1254. `original-g1.png` и `portrait-source-candidate.png` — точные побайтные копии автоматического оригинала, без ретуши/ресайза/обрезки/пересохранения. Только review/ содержит отдельно обозначенные производные для проверки.

Ограничения:

- About 6% above the hair, visibly less than the requested 18%; full head remains inside the full100 circle.
- Fine skin/hair and leather detail disappears at 40 px; the portrait does not prove exact facial identity to an unfamiliar viewer.
- Outer shoulder/chest corners are cut by the circular mask; keep full100 without tighter zoom.
- No runtime widget, DPI, interaction state, UE import or independent acceptance tested by this producing agent.

Подтверждены live owner и raw slug; проверено отсутствие исходного портретного key. Это только предложение исходника: runtime, Unreal, канонический design-front, formal acceptance, общие registry/ledger/git не менялись. Источники и SHA — в preflight/source-hashes-before/verification; точный запрос — prompt-g1.txt.
