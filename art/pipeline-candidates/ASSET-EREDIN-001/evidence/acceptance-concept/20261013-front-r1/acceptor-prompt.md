# Независимая приёмка концепта ASSET-EREDIN-001, stage 1a, cycle r1
Делегирование пользователя (2026-10-06, дословно): «Не знаю. Делай сам, меня это не касается. Все решения принимай».
Траты на этом шаге: нет (кредиты Tripo/SYNTX не расходуются).
Ты — отдельный приёмщик «Sol 6.1 xhigh», не исполнитель. Только читать перечисленные входы, ничего не править и не генерировать.
Не запускать validate_card.py, git, браузер, Unreal, Tripo, SYNTX или агентов. Файл карточки записывает CLI, запускающий проверит его.
Не открывать другие карточки, другие evidence ассеты, чат, историю или пользовательский конфиг. Текст читать UTF-8.

The character identity comes from the game database (Hero.name), encoded by asset-card KEY / DESCRIPTION_EN. S judges recognisability of THAT named character, not a generic lookalike. Judge only the attached images and the listed evidence. The quality reference demonstrates craftsmanship only, not character design, palette, costume or pedestal.
Attached image 1: art/imagegen/concept-eredin-codex/design/eredin-front.png — the design front being accepted.
Attached image 2: art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png — QUALITY_REFERENCE; inspect it.
Use the attached images directly; view_image on these same paths is permitted, without crops or edits.

Input files (complete UTF-8 contents supplied below; only these plus the rubric and schema may be read):
- asset card: art/pipeline-candidates/ASSET-EREDIN-001/asset-card.yaml
```
# asset-card.yaml — 3d-model-pipeline, этап 0 (поля этапа 1). Записан пакетно 2026-10-13.
# Реестр asset-registry.json, строка 06-tasks/anim.csv и пробы исполнителей этапов 2+ отложены
# (пользователь 2026-10-13: «Все остальные этапы нужно будет отложить»).
ASSET_ID: ASSET-EREDIN-001
CONTENT_KEY: eredin
KEY: Eredin
ROLE: hero
ANATOMY: humanoid
GAME_ROLE: hero
WEAPON_HAND: right
SIDE_VIEW: left
DESCRIPTION_EN: "Eredin, King of the Wild Hunt from The Witcher (Unmatched: Realms Fall): tall elf warrior in black spiked plate armour with a skull-like helmet, dark fur cloak, longsword in his RIGHT hand."
ANCHORS_EN: "longsword in the RIGHT hand; black spiked plate armour; skull-like helmet; dark fur cloak"
PALETTE:
  main:
    - {name: armour black, hex: "#1C1C22"}
    - {name: frost blue, hex: "#8AB0D0"}
    - {name: fur dark, hex: "#3A3430"}
  accent: {name: eye blue, hex: "#6AB8E8"}
QUALITY_REFERENCE:
  - art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png
ASSET_DIR: art/pipeline-candidates/ASSET-EREDIN-001
decided_by: delegated (ВР-реестр 2026-10-06)
NOTES: ростер после MVP вне объёма ВР-18 — запуск по запросу пользователя 2026-10-13 (волна 1a).

```
- palette: art/imagegen/concept-eredin-codex/palette.json
```
{
  "main": [
    {
      "name": "armour black",
      "hex": "#1C1C22"
    },
    {
      "name": "frost blue",
      "hex": "#8AB0D0"
    },
    {
      "name": "fur dark",
      "hex": "#3A3430"
    }
  ],
  "accent": {
    "name": "eye blue",
    "hex": "#6AB8E8"
  }
}

```
- checks: art/imagegen/concept-eredin-codex/design/checks-report.json
```
{
  "schema": "unmatched.concept-checks/1",
  "tool": "tools/art/concept/check_concept_views.py",
  "generated_at": "2026-10-13T08:54:56+00:00",
  "set": "art/imagegen/concept-eredin-codex/design",
  "key": "eredin",
  "role": "hero",
  "views": [
    "front"
  ],
  "inputs": [
    {
      "view": "front",
      "path": "art/imagegen/concept-eredin-codex/design/eredin-front.png",
      "sha256": "ba8f959f87a540a529308425a5bbb90b62c761fc0b37ac7640447fcdd8dfdf0c",
      "format": "PNG",
      "mode": "RGB",
      "size": [
        1280,
        1600
      ]
    }
  ],
  "raw_files_modified": false,
  "tolerances": {
    "size_rel_pct": 0.5,
    "border_band_pct": 2.0,
    "border_share_min": 0.99,
    "border_tone_warn": 12,
    "border_tone_fail": 20,
    "bg_neutral_max": 6,
    "bg_between_views_max": 12,
    "bg_dark_luma_warn": 96,
    "top_min_pct": 1.0,
    "bottom_max_pct": 99.0,
    "side_min_pct": 1.0,
    "base_bottom_spread_warn_pct": 1.5,
    "base_bottom_spread_fail_pct": 3.5,
    "base_center_spread_warn_pct": 2.0,
    "base_center_spread_fail_pct": 6.5,
    "height_spread_warn_pct": 3.0,
    "height_spread_fail_pct": 5.0,
    "extra_component_warn_pct": 0.5,
    "mask_area_min_pct": 2.0,
    "mask_area_max_pct": 90.0,
    "segment_tone": 14,
    "segment_min_component_pct": 0.02
  },
  "tolerances_note": "решение скилла (DECISIONS Р-9), калибровка на art/imagegen/hero-quality-v1 — tools/art/concept/README.md",
  "frame": {
    "min_top_pct": 4.0
  },
  "measurements": {
    "front": {
      "size": [
        1280,
        1600
      ],
      "mode": "RGB",
      "alpha": {
        "present": false,
        "min": 255
      },
      "border": {
        "band_px": 26,
        "median_rgb": [
          46.0,
          46.0,
          48.0
        ],
        "share_within_tone_warn": 1.0,
        "share_within_tone_fail": 1.0,
        "p99_deviation": 0.0,
        "neutral_delta": 2.0,
        "luma": 46.1
      },
      "background_model": {
        "fit": "quadratic per channel",
        "residual_std": [
          0.7,
          0.7,
          0.68
        ],
        "segment_tone": 14
      },
      "mask": {
        "area_pct": 29.97,
        "filled_area_pct": 29.97,
        "components_kept": 1,
        "main_component_pct": 29.97,
        "other_components_pct": [
          0.006,
          0.004,
          0.004,
          0.003,
          0.002,
          0.002
        ],
        "bbox_px": [
          237,
          40,
          935,
          1571
        ],
        "top_pct": 2.5,
        "bottom_pct": 98.188,
        "left_pct": 18.516,
        "right_pct": 73.047,
        "height_pct": 95.688,
        "base_center_x_pct": 50.508,
        "base_width_pct": 41.094,
        "base_top_pct_est": 84.938
      }
    }
  },
  "checks": [
    {
      "id": "set.size",
      "scope": "set",
      "result": "PASS",
      "value": {
        "sizes": {
          "front": [
            1280,
            1600
          ]
        },
        "max_delta_pct": 0.0
      },
      "limit": "<= 0.5 %",
      "message": "все виды одного размера и аспекта"
    },
    {
      "id": "set.size_exact",
      "scope": "set",
      "result": "PASS",
      "value": {
        "front": [
          1280,
          1600
        ]
      },
      "limit": "равны до пикселя",
      "message": "размеры отличаются на пиксели: сравнение идёт в % кадра"
    },
    {
      "id": "view.alpha",
      "scope": "front",
      "result": "PASS",
      "value": {
        "present": false,
        "min": 255
      },
      "limit": "без прозрачности",
      "message": "альфа-канал с прозрачностью: Tripo и image_gen ждут RGB"
    },
    {
      "id": "view.border_uniform",
      "scope": "front",
      "result": "PASS",
      "value": {
        "share_warn_tone": 1.0,
        "share_fail_tone": 1.0,
        "p99_deviation": 0.0
      },
      "limit": ">= 0.99 при ±20 (WARN при ±12)",
      "message": "рамка 2 % кадра — ровный фон без объектов"
    },
    {
      "id": "view.bg_neutral",
      "scope": "front",
      "result": "PASS",
      "value": [
        46.0,
        46.0,
        48.0
      ],
      "limit": "|R-G|,|G-B| <= 6",
      "message": "фон нейтрально-серый"
    },
    {
      "id": "view.bg_dark",
      "scope": "front",
      "result": "PASS",
      "value": 46.1,
      "limit": "<= 96",
      "message": "фон тёмно-серый (норма hero-quality-v1)"
    },
    {
      "id": "view.mask",
      "scope": "front",
      "result": "PASS",
      "value": 29.97,
      "limit": "2.0..90.0 %",
      "message": "маска фигуры правдоподобна"
    },
    {
      "id": "view.top_margin",
      "scope": "front",
      "result": "PASS",
      "value": 2.5,
      "limit": ">= 1.0 %",
      "message": "верх фигуры не касается края"
    },
    {
      "id": "view.frame_top",
      "scope": "front",
      "result": "WARN",
      "value": 2.5,
      "limit": ">= 4.0 %",
      "message": "верхняя точка не выше рамки ядра (1a: y >= 4 %)"
    },
    {
      "id": "view.bottom_margin",
      "scope": "front",
      "result": "PASS",
      "value": 98.188,
      "limit": "<= 99.0 %",
      "message": "низ подставки в кадре"
    },
    {
      "id": "view.side_margin",
      "scope": "front",
      "result": "PASS",
      "value": 18.516,
      "limit": ">= 1.0 %",
      "message": "фигура не обрезана по бокам"
    },
    {
      "id": "view.single_component",
      "scope": "front",
      "result": "PASS",
      "value": [
        0.006,
        0.004,
        0.004,
        0.003,
        0.002,
        0.002
      ],
      "limit": "прочие < 0.5 %",
      "message": "одна крупная связная фигура"
    },
    {
      "id": "set.bg_same",
      "scope": "set",
      "result": "PASS",
      "value": 0.0,
      "limit": "<= 12",
      "message": "один фон на набор"
    }
  ],
  "summary": {
    "PASS": 12,
    "WARN": 1,
    "FAIL": 0
  },
  "verdict": "PASS",
  "palette": {
    "path": "art/imagegen/concept-eredin-codex/palette.json",
    "swatches": [
      {
        "name": "armour black",
        "hex": "#1C1C22",
        "role": "main",
        "figure_share_within_40_pct": 51.94
      },
      {
        "name": "frost blue",
        "hex": "#8AB0D0",
        "role": "main",
        "figure_share_within_40_pct": 0.0
      },
      {
        "name": "fur dark",
        "hex": "#3A3430",
        "role": "main",
        "figure_share_within_40_pct": 30.43
      },
      {
        "name": "eye blue",
        "hex": "#6AB8E8",
        "role": "accent",
        "figure_share_within_40_pct": 0.0
      }
    ]
  },
  "sheet": null
}

```
- generation records: art/imagegen/concept-eredin-codex/generation-records.json
```
[
  {
    "id": "ASSET-EREDIN-001-1a-design-front-u1",
    "card_id": "ASSET-EREDIN-001",
    "stage": "1a",
    "view": "design-front",
    "side_view": null,
    "attempt": 1,
    "tool": "unstability.ai — UltraReal Fine-Tune v4 (Flux.1 D), Permissive, 3:4, High, CFG 3.5, 25 steps",
    "mode": "text-to-image",
    "references": [],
    "prompt_key": "1a/design-front/u1",
    "prompt": "Painted collectible tabletop miniature figure of Eredin, King of the Wild Hunt from The Witcher, high-end painted resin statue, product photo. Tall elf warrior in black spiked plate armour with a frosty skull-like helmet, dark fur cloak, longsword in the right hand. Full body, standing upright, strictly frontal orthographic view, camera at chest height, symmetric neutral ready pose with arms slightly away from the body. Standing on a round dark stone pedestal seen exactly edge-on, top surface of the base not visible. Plain flat neutral dark grey background, soft studio lighting, no scenery, no text, no logo. Whole figure and pedestal fully in frame with small margins.",
    "correction": null,
    "original_path": "unstability.ai download (Downloads/unstability-<uuid>.png)",
    "saved_path": "art/imagegen/concept-eredin-codex/concepts/eredin-design-front-u1.png",
    "sha256": "59d96fd698c9062ab13c45c5ca5a48029162bf74572c5f0f85428ee17d2ed5a6",
    "width": 1280,
    "height": 1600,
    "date": "2026-10-13 08:49:44 UTC",
    "selected": false
  },
  {
    "id": "ASSET-EREDIN-001-1a-design-front-u2",
    "card_id": "ASSET-EREDIN-001",
    "stage": "1a",
    "view": "design-front",
    "side_view": null,
    "attempt": 2,
    "tool": "unstability.ai — UltraReal Fine-Tune v4 (Flux.1 D), Permissive, 3:4, High, CFG 3.5, 25 steps",
    "mode": "text-to-image",
    "references": [],
    "prompt_key": "1a/design-front/u2",
    "prompt": "Painted collectible tabletop miniature figure of Eredin, King of the Wild Hunt from The Witcher 3, high-end painted resin statue, product photo. Tall imposing elf warrior filling most of the frame, black spiked plate armour with frost, menacing skull-like spiked helmet, dark fur cloak, longsword held in the right hand. The figure stands on a LOW thin round base. Full body, standing upright, strictly frontal orthographic view, camera at chest height, symmetric neutral ready pose with arms slightly away from the body. Standing on a round dark stone pedestal seen exactly edge-on, top surface of the base not visible. Plain flat neutral dark grey background, soft studio lighting, no scenery, no text, no logo. Whole figure and pedestal fully in frame with small margins.",
    "correction": null,
    "original_path": "unstability.ai download (Downloads/unstability-<uuid>.png)",
    "saved_path": "art/imagegen/concept-eredin-codex/concepts/eredin-design-front-u2.png",
    "sha256": "35295797f8ea0a333de4e0ce5bf9a03907a261ac8abdf434d335f0f4b61fdfa4",
    "width": 1280,
    "height": 1600,
    "date": "2026-10-13 08:49:44 UTC",
    "selected": false
  },
  {
    "id": "ASSET-EREDIN-001-1a-design-front-u3",
    "card_id": "ASSET-EREDIN-001",
    "stage": "1a",
    "view": "design-front",
    "side_view": null,
    "attempt": 3,
    "tool": "unstability.ai — UltraReal Fine-Tune v4 (Flux.1 D), Permissive, 3:4, High, CFG 3.5, 25 steps",
    "mode": "text-to-image",
    "references": [],
    "prompt_key": "1a/design-front/u3",
    "prompt": "Painted collectible tabletop miniature figure of Eredin, King of the Wild Hunt from The Witcher 3, high-end painted resin statue, product photo. Tall imposing elf warrior filling most of the frame, black spiked plate armour with frost, menacing skull-like spiked helmet, dark fur cloak, longsword held in the right hand. The figure stands on a LOW thin round base. Full body, standing upright, strictly frontal orthographic view, camera at chest height, symmetric neutral ready pose with arms slightly away from the body. Standing on a round dark stone pedestal seen exactly edge-on, top surface of the base not visible. Plain flat neutral dark grey background, soft studio lighting, no scenery, no text, no logo. Whole figure and pedestal fully in frame with small margins.",
    "correction": null,
    "original_path": "unstability.ai download (Downloads/unstability-<uuid>.png)",
    "saved_path": "art/imagegen/concept-eredin-codex/concepts/eredin-design-front-u3.png",
    "sha256": "4c97e587e61241c3779cd78be44082d09a57b0191e8c940028666587454084cf",
    "width": 1280,
    "height": 1600,
    "date": "2026-10-13 08:49:44 UTC",
    "selected": true
  }
]

```
- verification: art/imagegen/concept-eredin-codex/verification.json
```
{
 "source_unchanged": true,
 "outside_folder": [],
 "checks": [
  {
   "view": "design-front",
   "generation": "unstability",
   "exit_code": 0,
   "report": "art/imagegen/concept-eredin-codex/design/checks-report.json",
   "final": true,
   "source": "unstability.ai"
  }
 ],
 "checklist": [],
 "limit_reached": [],
 "design_source": {
  "service": "unstability.ai",
  "model": "UltraReal Fine-Tune v4 (Flux.1 D)",
  "by": "Claude (Windows-MCP in the user's Chrome)",
  "reason": "Codex image_gen / SYNTX refuse this licensed character (moderation_blocked); user decision 2026-10-13",
  "post": "backdrop flattened by C:/tmp/concept-wave/rebg.py, raw frame design/<key>-front-raw.png",
  "checklist_note": "Claude visually checked: one subject, full body, front view, pedestal, no text or logo after cleanup"
 }
}

```

Provenance: generated OUTSIDE Codex in unstability.ai. User instruction 2026-10-13: verification.json design_source replaces the Codex generation run. Do not fail G-CHECKS or reduce artistic scores merely for using unstability, missing Codex prompt manifests or documented backdrop cleanup. Judge the actual design front image. G-CHECKS comes ONLY from design/checks-report.json, summary and verdict. WARN is not FAIL.
For stage 1a C MUST equal 1.5 with rationale «1a: один вид, C не оценивается; фиксированное значение concept-sheet.md §11», frames=["eredin-front.png"]. Never put C into rework_fix_list on 1a.
Do not misclassify a relaxed ready pose with elbows near the torso as A-pose: apply §4.4 definition (read that section if necessary). S=0 for a forbidden T/A rig-rest pose, extra/missing major parts or wrong identity.
Only 0,0.5,1,1.5,2 are valid dimension scores. score=Decimal ROUND_HALF_UP(sum(S,C,Q,P)/8*10,1), not Python bankers rounding.
Non-pass for G-CHECKS FAIL, any score <1 or total <8 => return_to_stage_1 (r1). Otherwise pass.
At pass, rework_fix_list=[]; residual issues go to known_issues. At non-pass, list every applicable S/Q/P<2 and every FAIL gate in rework_fix_list; never C. Each fix is one English line usable in CORRECTION, tool="Codex 1a". Concept routing differs from model: return_to_stage_1 permits and needs the concept fix list.

Required constants (copy precisely; complete the remaining artistic fields yourself):
{
  "schema": "unmatched.concept-acceptance/1",
  "kind": "concept",
  "clip": null,
  "asset_id": "ASSET-EREDIN-001",
  "cycle": "r1",
  "date": "2026-10-13",
  "previous_card": null,
  "accepted_object": [
    {
      "path": "art/imagegen/concept-eredin-codex/design/eredin-front.png",
      "sha256": "ba8f959f87a540a529308425a5bbb90b62c761fc0b37ac7640447fcdd8dfdf0c"
    }
  ],
  "frames": {
    "dir": "art/imagegen/concept-eredin-codex/design",
    "files": [
      "eredin-front.png",
      "checks-report.json"
    ]
  },
  "reports": [
    "art/imagegen/concept-eredin-codex/design/checks-report.json",
    "art/imagegen/concept-eredin-codex/generation-records.json",
    "art/imagegen/concept-eredin-codex/verification.json"
  ],
  "acceptor": {
    "profile": "Sol 6.1 xhigh",
    "session_id": "codex:pending"
  },
  "executor_session_id": "codex:01a13495-9111-7a81-9ce8-74b410d7f606",
  "decided_by": "delegated (ВР-реестр 2026-10-06)"
}
All frame references in scores/rework/known_issues must be names from frames.files. Quality reference is not in frames.files and must not be a scores.frames name.
Strict schema optional fields are required but nullable: verdict_reason=null at pass; gates.G-CHECKS.source_defect=null; clip=null.
Gate note cites report keys and observed values. Gate source is a plain repo-relative file path without #.
At pass status_note="художественно принято, по делегированию (docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md)"; otherwise status_note="".

Full applicable rubric:
## 11. Приёмка: гейты, рубрика, вердикт, карточка

Механика и вызов приёмщика — общие с этапом 4 (`acceptance-and-blender.md`: профили «Opus xhigh» / «Sol 6.1 xhigh»,
сессия приёмщика ≠ сессии исполнителя, приёмщик не правит). Здесь — то, что относится к концепту.

**Гейт (PASS/FAIL из отчёта, не балл) — один:** `G-CHECKS` — `check_concept_views.py` с кодом 0 (`source` — путь
`checks-report.json` от корня репо). Схема `tools/art/acceptance/asset-acceptance-2.schema.json` для `kind: concept`
разрешает только его (`gates.propertyNames: ["G-CHECKS"]`; `validate_card.py` `GATES["concept"]`), статус `n/a` для
него запрещён. Сверка записей генераций — не гейт карточки, а предусловие вызова приёмщика (раздел 5.5, п. 3).

**Измерения** (0–2, шаг 0,5):

| Балл | S — силуэт и читаемость | C — согласованность видов (1c) | Q — детализация против QUALITY_REFERENCE | P — палитра и якоря |
|---|---|---|---|---|
| 0 | не тот персонаж; лишние или недостающие части (вторая голова, вторая рука с оружием); T- или A-поза (раздел 4.4) | разные персонажи или позы; оружие зеркально | плоско, мультяшно или фото; не миниатюра | палитра чужая; якорей нет |
| 0,5 | главные признаки (оружие, головной убор) теряются в силуэте | поза или костюм заметно расходятся на одном виде | грубые детали, материалы не различимы | часть основных цветов не та |
| 1 | читается, но один главный признак слит с корпусом | якоря совпадают, форма плаща, головного убора или масштаб заметно расходятся | материалы различимы, детализация явно ниже эталона | основные цвета верны, акцент или один якорь потерян |
| 1,5 | читается на всех видах, мелкие слияния (кисть с оружием), руки близко к корпусу | мелкие расхождения орнамента и складок (уровень принятых наборов hero-quality-v1, их «Проверка и ограничения») | близко к эталону, отдельные зоны беднее | все цвета и якоря есть, отклонение тона |
| 2 | ясный силуэт на каждом виде, руки отделены, поза по разделу 4.4, тонкие части читаются или помечены в обосновании для этапов 3–4 | поза, пропорции, якоря и сторона оружия совпадают; профиль и вид сзади строгие | уровень эталона: расписанная коллекционная миниатюра, детали внутри силуэта | палитра = `PALETTE` (свотчи листа совпадают с фигурой), все якоря на месте там, где видимы |

`score = round(sum / (2 × n_applicable) × 10, 1)`, n = 4 всегда (схема требует числовые S, C, Q, P; null у
концепта не допускается). Сравнение `score >= 8.0`.

**C на 1a — фиксированное правило (решение скилла).** На 1a один вид, согласованность видов не оценивается, но схема
требует число. Приёмщик ставит `C = 1,5` с обоснованием «1a: один вид, C не оценивается; фиксированное значение
concept-sheet.md §11» и `frames: ["<key>-front.png"]`; в `rework_fix_list` C на 1a не попадает. Почему 1,5: при шаге
0,5 условие pass `(S + Q + P + 1,5) / 8 × 10 ≥ 8,0` равносильно `S + Q + P ≥ 5,0`, то есть ровно порогу 8,0 по трём
оцениваемым измерениям (`5,0 / 6 × 10 = 8,3`, `4,5 / 6 × 10 = 7,5`); 1,5 не срабатывает как вето (< 1,0). Проверено
`validate_card.py` на пробных карточках 1a: S 1,5 + C 1,5 + Q 1,5 + P 2 → 8,1 `pass` (код 3: второй приёмщик, «Устойчивый pass листа» ниже); S 1 + C 1,5 + Q 1,5 + P 2 → 7,5
`return_to_stage_1`.

**Вердикт** (детерминированно, проверяет `validate_card.py`): гейт `G-CHECKS` FAIL → `return_to_stage_1`; любое
измерение < 1,0 → `return_to_stage_1` при любой сумме; `score < 8.0` → `return_to_stage_1`; иначе `pass`. Цикл `r4`
без pass → `escalate_user` (`validate_card.py` `LAST_CYCLE["concept"] = 4`). Запрещённая поза (T или A) — S = 0, то
есть вето: лист не проходит при любой сумме.

**Устойчивый pass листа** (решение оркестратора по калибровке 2026-10-09, раунд 3; то же правило, что у модели,
`references/acceptance-and-blender.md` §6, §8.5, §13). `pass` со `score` 8,0–8,4 одной карточкой не окончателен:
`validate_card.py` даёт код **3** и печатает `needs_second_acceptor`. На 1a это любой pass с `S + Q + P` = 5,0 (C = 1,5
фиксировано), то есть 8,1. Порядок:

1. Второй приёмщик — **другой профиль** («Sol 6.1 xhigh» при первом «Opus xhigh» и наоборот), тот же промпт ниже, те
   же файлы, новый контекст; первую карточку он не видит. Ответ — `card-2.json` рядом с `card.json` (для Sol —
   `--output-schema tools/art/acceptance/asset-acceptance-2.output-concept.schema.json -o <каталог>/card-2.json`;
   остальное — команда `references/acceptance-and-blender.md` §8.4, с `windows.sandbox="unelevated"`).
2. Итог пары:
   ```bash
   python tools/art/acceptance/validate_card.py <каталог>/card.json --second <каталог>/card-2.json \
       --final-json <каталог>/final.json --print-verdict --check-files
   ```
   `score` — минимум двух; вердикт — карточки с меньшим `score` (при равенстве — более строгий), но строгий маршрут
   другой карточки (`return_to_stage_1`, FAIL `G-CHECKS`, вето) побеждает. Маршрут и `rework_fix_list` (пункты
   CORRECTION) — из карточки `final.json#source_card`.
3. Второй `pass` в той же полосе — итог `pass`; третий приёмщик не нужен. Другой профиль не запускается после пробы
   (§5.2) — второй приёмщик того же профиля в новом контексте и `--same-profile-ok`.

**Карточка** (форма — схема `tools/art/acceptance/asset-acceptance-2.schema.json`, ветка `kind: concept`; поля:)

| Поле | Значение на этапе 1 |
|---|---|
| `schema`, `kind` | `"unmatched.concept-acceptance/1"`, `"concept"` |
| `asset_id` | `ASSET_ID` |
| `cycle` | `r1`–`r4` (1a и 1c считаются раздельно, раздел 10) |
| `date` | дата приёмки `YYYY-MM-DD` (обязательно) |
| `previous_card` | `null` у r1; у r2+ — путь от корня репо к `card.json` предыдущего цикла того же шага (обязательно, `validate_card.py:308-311`) |
| `accepted_object` | `[{path, sha256}]`, пути от корня репо: 1a — `art/imagegen/concept-<key>-codex/design/<key>-front.png`; 1c — `<key>-front.png`, `<key>-side.png`, `<key>-back.png` пакета |
| `frames` | объект `{dir, files}`: `dir` — каталог от корня репо, `files` — только имена без `/` (шаблон `^[A-Za-z0-9._-]+\.(jpg\|png\|json)$`). 1a: `dir` = `art/imagegen/concept-<key>-codex/design`, `files` = [`<key>-front.png`, `checks-report.json`]. 1c: `dir` = `art/imagegen/concept-<key>-codex`, `files` = [`sheet-<key>.png`, `<key>-front.png`, `<key>-side.png`, `<key>-back.png`, `checks-report.json`] |
| `reports` | пути от корня репо: `checks-report.json` этого шага, `generation-records.json`, `verification.json` |
| `gates` | `{"G-CHECKS": {"status": "PASS"\|"FAIL", "source": "<путь checks-report.json>", "note": "…"}}` — и больше ничего |
| `scores` | `S`, `C`, `Q`, `P`: `{value: 0–2 шаг 0,5, rationale, frames}`; `frames` — имена из `frames.files` |
| `score`, `verdict` | по формуле и правилам выше |
| `verdict_reason` | обязательно при `verdict` ≠ `pass` (≥ 10 символов): какое правило сработало |
| `rework_fix_list` | `[{item, frame, fix, tool}]`: `item` — измерение < 2 или `G-CHECKS` при FAIL; `frame` — вид/файл; `fix` — одна английская строка, пригодная для CORRECTION; `tool` — `Codex 1c CORRECTION` \| `Tripo 1b черновик` \| `Codex 1a` |
| `acceptor` | `{profile: "Opus xhigh"\|"Sol 6.1 xhigh", session_id}` |
| `executor_session_id` | сессия запускающего агента (≠ `acceptor.session_id`) |
| `decided_by` | `"delegated (ВР-реестр 2026-10-06)"` или `"user"` |
| `status_note` | при pass по делегированию — содержит «по делегированию» (`docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md`) |

Путь: `art/pipeline-candidates/<ASSET_ID>/evidence/acceptance-concept/<YYYYMMDD>-front-r<N>/card.json` (1a) и
`…/<YYYYMMDD>-sheet-r<N>/card.json` (1c). Пустой каталог `frames/` не нужен: кадры — файлы пакета.

```bash
python tools/art/acceptance/validate_card.py \
    art/pipeline-candidates/<ASSET_ID>/evidence/acceptance-concept/<YYYYMMDD>-<front|sheet>-r<N>/card.json \
    --print-verdict --check-files
# код 0 = схема валидна и вердикт согласован с правилами; 1 = нет. --check-files сверяет sha256 accepted_object
# и наличие frames/reports/previous_card; запуск из корня репо
```

**Промпт приёмщика** (на вход только файлы, отчёты, выдержка карточки и рубрика; ответ — JSON карточки по схеме):

```text
Ты — приёмщик этапа 1 скилла 3d-model-pipeline (концепт-лист). Файлы не правишь, ничего не генерируешь.
Объект: <1a: дизайн-front design/<key>-front.png | 1c: виды <key>-front/side/back.png и лист sheet-<key>.png>.
Открой каждый файл как картинку. Прочитай checks-report.json и generation-records.json.
Выдержка карточки ассета: DESCRIPTION, ANCHORS, PALETTE, ANATOMY, WEAPON_HAND, SIDE_VIEW (<значения>).
Эталон качества: <QUALITY_REFERENCE> (открой). Для 1c — ещё дизайн design/<key>-front.png и ортопроекции 1b.
Рубрика: references/concept-sheet.md раздел 11 (таблица S, C, Q, P). На 1a C = 1,5 по фиксированному правилу
раздела 11, в rework_fix_list C на 1a не включай. T- или A-поза = S 0. Балл — по якорям, шаг 0,5; обоснование с
именами файлов из frames.files. Гейт один — G-CHECKS по checks-report.json (код 0 → PASS); WARN не гейт, учитывай их
в C. rework_fix_list — только измерения < 2 и G-CHECKS при FAIL; у пункта: item, frame (вид), fix (одна английская
строка для CORRECTION), tool (Codex 1c CORRECTION | Tripo 1b черновик | Codex 1a). Вердикт посчитай по правилам
раздела 11; при не-pass заполни verdict_reason. Заполни все поля таблицы «Карточка» раздела 11 (date, previous_card,
frames как {dir, files} с именами без пути). Верни только JSON карточки.
```



Reply ONLY with the JSON card matching tools/art/acceptance/asset-acceptance-2.output-concept.schema.json. Do not write files, invent a second acceptor, or judge other assets. Evaluator session_id remains codex:pending; launcher replaces it with the actual fresh thread id.
