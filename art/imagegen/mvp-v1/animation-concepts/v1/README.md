# Animation concepts v1

Дата: 2026-09-27. Источник постановки: [`docs/game-design/18-animation-production-brief.md`](../../../../../docs/game-design/18-animation-production-brief.md), разделы 5–8.

Пакет содержит 16 растровых key-pose-листов: по `Idle`, `LungeAttack`, `HitReact` и `DeathSettle` для Medusa, Harpy, King Arthur и Merlin. Изображения созданы встроенным imagegen по исправленным ортографическим референсам из `art/imagegen/mvp-v1/characters/`.

## Статус

- Это **концепты постановки движения**, а не готовые skeletal-анимации.
- Листы не доказывают rig, skinning, retarget, root motion, loop seam, длительность, FPS или импорт в UE.
- `HAR-HitReact` имеет статус `CONDITIONAL_AD_CNF_30`: решение о клипе для помощника с 1 HP остаётся за автором.
- Остальные 15 листов покрывают безусловные производственные позиции текущего брифа.
- Ни один файл не предназначен для image-to-3D вместо ортографических видов из `generation-inputs.json`.

## Навигация

- [Общий превью-лист](animation-concepts-v1-preview.png)
- [Medusa](medusa/overview-v1.png)
- [Harpy](harpy/overview-v1.png)
- [King Arthur](king-arthur/overview-v1.png)
- [Merlin](merlin/overview-v1.png)
- [Промпты](PROMPTS.md)
- [Манифест](manifest.json)

## Покрытие

| Персонаж | Idle | LungeAttack | HitReact | DeathSettle |
|---|---|---|---|---|
| Medusa | concept | concept | concept | concept |
| Harpy | concept | concept | **conditional** | concept |
| King Arthur | concept | concept | concept | concept |
| Merlin | concept | concept | concept | concept |

## Проверка изображений

Проверено вручную:

- на каждом листе четыре последовательные позы одного персонажа;
- силуэт и основная цветовая схема соответствуют входным референсам;
- Medusa сохраняет лук в левой руке, Arthur — меч в правой, Merlin — посох в правой;
- Harpy сохраняет две ноги и два крыла;
- death-позы остаются внутри подставки;
- отсутствуют текст, VFX, противники и декоративная сцена.

Ограничения imagegen, которые должен исправить 3D-аниматор:

- позы не являются геометрически идентичными экземплярами одного mesh;
- глубина оружия, складки одежды, отдельные змеи и перья могут меняться между фазами;
- на `HAR-LungeAttack` в акцентной фазе одна лапа визуально отрывается от базы; итоговый клип всё равно должен иметь нулевой root translation и контролируемые контакты;
- subtle idle-листы передают направление движения, но не амплитуды и timing;
- позы нельзя трассировать буквально как финальные ключи без проверки силуэта из игровой камеры.

## Передача внешнему сервису или аниматору

Для каждого заказа передавать отдельно:

1. производственный FBX/GLB с утверждённым rig;
2. ортографические виды из `generation-inputs.json` как источник формы;
3. соответствующий key-pose-лист из этого каталога как источник движения;
4. карточку клипа из документа 18;
5. требования: in-place, отсутствие нежелательного root motion, оружие в правильной руке, отдельный клип на действие, сохранение skeleton hierarchy.

Не использовать этот пакет как доказательство закрытия ART-004…ART-008 или GD-058.

## Результат ревью аудита 4ce5822

Аудит в целом пригоден для производства, но его итог следует читать так:

- 16 — количество производственных позиций при консервативном следовании D-11;
- 15 позиций безусловны, `HAR-HitReact` условен до решения AD-CNF-30;
- «16 уникальных движений» пока не доказано: Idle/HitReact/DeathSettle могут частично переиспользоваться после retarget-gate;
- ссылки на материалы аудита должны вести в `docs/research/2026-09-27-animation-audit/`, а не в старую scratch-папку `.zcode/workflow-drafts/anim-audit-18/`.

Превью пересобираются командой:

```powershell
& art/imagegen/mvp-v1/animation-concepts/v1/build-previews.ps1
```
