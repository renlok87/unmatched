---
name: 3d-model-pipeline
description: Сквозной пайплайн новой 3D-фигуры Unmatched (герой, помощник, крылатое существо-бипед, проп). Этапы — концепт-лист в Gemini, генерация в Tripo3D Studio, сборка H2 в Blender, приёмка с коэффициентом и доработкой, анимация с VFX/SFX и упаковка с подключением в Unreal. Триггеры — «сгенерируй 3D-модель», «новый герой / помощник / существо / проп», «новая фигура», «3D model pipeline», «модель через Tripo», «концепт-лист героя». Статический проп (бочка, фонарь, ящик) — да, до импорта в UE; его размещение в раскладке доски — нет. НЕ для окружения, задников и сцен досок и размещения пропов в EnvLayouts (Marmoreal/Sarpedon — трек ENV-MAPS) и НЕ для разовых правок существующих ассетов.
---

# 3d-model-pipeline (указатель)

Каноническая копия скилла — `.agents/skills/3d-model-pipeline/` (её же читают другие агенты). Здесь только указатель, чтобы
скилл находил Claude Code; содержимое не дублируется, чтобы не расходилось.

Порядок работы:

1. Прочитай целиком `.agents/skills/3d-model-pipeline/SKILL.md` и следуй ему.
2. Справочники этапов открывай из `.agents/skills/3d-model-pipeline/references/` по ссылкам SKILL.md:
   `intake-and-evidence.md`, `concept-sheet.md`, `tripo3d-stages.md`, `acceptance-and-blender.md`,
   `animation-vfx-sfx.md`, `ue-import-package.md`, `new-character-registration.md`.
3. Правишь скилл — правь только каноническую копию; при смене `description` обнови его и здесь.
