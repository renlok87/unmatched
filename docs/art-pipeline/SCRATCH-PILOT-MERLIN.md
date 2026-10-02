# Пилот пути B: Merlin — параметры задачи

Параметры для промптов [CODEX-2D-PACKAGE-PROMPT.md](CODEX-2D-PACKAGE-PROMPT.md) (§1) и
[ZCODE-BLENDER-PROMPT.md](ZCODE-BLENDER-PROMPT.md) (§1). Путь — [SCRATCH-MODEL-PIPELINE.md](SCRATCH-MODEL-PIPELINE.md).
Выбор Merlin: у героя есть Tripo-версия H2LD для сравнения «концепт | scratch | H2» и видео-референсы всех четырёх
клипов.

## Для Codex (2D-пакет)

```
ASSET_KIND        = sidekick
ASSET_NAME        = Merlin (помощник King Arthur), пилот эксперимента пути B
ASSET_ID          = ASSET-MERLIN-001
CONTENT_KEY       = merlin
KEY               = Merlin            (UE-папка MerlinSC; существующие /Game/PipelineCandidates/Merlin/* не трогать)
HEIGHT_BUDGET_UU  = 45 (допустимо 40–48); верх фигуры = верх капюшона 45,0 см от низа подставки;
                    посох с кристаллом выше головы — около 49,5 см
WEAPON            = weapon.R — посох в ПРАВОЙ руке персонажа (на виде спереди — слева для зрителя)
BASE              = круглая, Ø 24 см, высота 5–6 см, тёмный камень
WORKDIR           = C:/tmp/wt-scratch2d-merlin, ветка feat/scratch2d-merlin от fix/admin-panel
SYNTX_TOKEN_LIMIT = 100   (только если image_gen недоступен)
```

### ASSET_DESCRIPTION

База — карточка [04-blender-production.md](../game-design/04-blender-production.md) §3.4; внешний вид — концепт
`art/imagegen/hero-quality-v1/merlin/merlin-front.png` (+ `merlin-side.png`, `merlin-back.png`, `prompts.md`).

- Пожилой маг, чуть сутулый, «старческая лёгкость», 5–5,5 голов (С-1). Силуэт с игровой камеры «капюшон + посох»:
  вертикаль со смещённой диагональю посоха.
- Глубокий тёмно-синий шерстяной капюшон и мантия до земли, широкие рукава.
- Две вертикальные столы; кайма капюшона, манжет и подола с античной золотой вышивкой (руноподобные знаки, звёзды).
- Длинная белая борода, перехваченная коричневой кожаной обмоткой; морщинистое мудрое лицо.
- Правая рука держит кривой тёмный деревянный посох с резьбой; навершие — когтистая деревянная оправа с гранёным
  сапфирово-синим кристаллом. Без магических эффектов.
- Левая рука у пояса. Потёртый коричневый кожаный пояс с бронзовой пряжкой и свисающим концом. Коричневые кожаные
  сапоги, носки видны из-под подола.
- Поза миниатюры: стоит, вес чуть на посохе, взгляд вперёд (−Y в Blender). Двуручного хвата нет.

### Палитра зон

Классы библиотеки материалов, как в [merlin-lookdev-v2.md](merlin-lookdev-v2.md) §3:

| Зона | Класс |
|---|---|
| мантия, капюшон, рукава | `wool_coarse` |
| золотая вышивка, звёзды, кайма | `silk` (без цвета команды) |
| пояс, сапоги, обмотка бороды | `leather_worn` |
| пряжка | `bronze` |
| посох и оправа кристалла | `wood` |
| кристалл, борода, брови | `legacy_bake` (roughness/metallic явно: кристалл — гладкий диэлектрик, борода — матовая) |
| лицо, кисти | `skin` |
| подставка | `stone_base` |

**TeamAccent** (цвет команды) — только пояс, подкладка капюшона, узкая кайма манжет и кромка подола; 5–12 % фигуры.

**Отличия от концепта hero-quality-v1:** силуэт, позу и пропорции не копировать с Tripo-рендеров — все размеры задаёт
`spec.json`. Концепт — только эталон внешности, костюма и цветов.

## Для ZCode (модель в Blender)

```
CONTENT_KEY       = merlin
ASSET_ID          = ASSET-MERLIN-001
KEY               = Merlin            (UE-папка MerlinSC)
CLOSEST_REFERENCE = Merlin            (клипы H2Anim Merlin: посох-опора hand_pin в Idle, HitReact, DeathSettle)
ANIM_REFS         = art/animation-refs/ASSET-MERLIN-001/  (MER-Idle, MER-LungeAttack, MER-HitReact, MER-DeathSettle)
SCOPE             = to_ue_check
WORKDIR           = C:/tmp/wt-scratch-merlin, ветка feat/scratch-merlin от fix/admin-panel
```

Запускать после того, как пакет Codex влит в `fix/admin-panel` (`art/imagegen/scratch-v1/merlin/HANDOFF.json`).
