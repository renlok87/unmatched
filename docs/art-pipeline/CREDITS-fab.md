# Сторонние ассеты Fab: реестр и атрибуция

Проект используется лично и локально, без публикации (решение пользователя 2026-10-01: «И все только для
личного и локального использования в локальной сети. Нигде это не будет публиковаться.»). Паки лежат в
gitignored `unreal/Unmatched/Content/<Pack>/` и в git не попадают. Добавление — через Epic Games Launcher
(аккаунт пользователя) в проект-посредник `Documents/Unreal Projects/FabStaging`, затем копия в Unmatched.
Выбор — ENV-U13/U14 (`docs/game-design/decisions/2026-09-30-env-original-maps-decisions.md`), ресёрч —
`fab-free-assets-research-2026-10-01.md`.

Звук ведётся отдельно: [CREDITS-audio.md](CREDITS-audio.md) (DE-013, кандидаты с лицензиями, ничего не импортировано).

| Пак | Издатель | Лицензия | ИИ | Папка Content | Версия при добавлении | Назначение |
|---|---|---|---|---|---|---|
| [Stylized Environment - Forest](https://www.fab.com/listings/7b06f300-f295-40fe-9972-b9de3a0abe03) | SilverSet Studios | Fab Standard, уровень «Личное» | разрешён | `StylizedForest` | 5.7 → проект 5.8 | розовые деревья (сакура Marmoreal), дубы, кусты, заборы, камни |
| [Megaplants: Yoshino Cherry](https://www.fab.com/listings/97f6cdb0-810d-470d-9e3a-3c9f059e6763) | Quixel Megaplants | Fab Standard | **NoAI** | `Megaplant_Library` | 5.8 | вариант сакуры только для пользователя; кадры с ним не подаются ИИ |
| [Fantasy_Forest](https://www.fab.com/listings/ece3a551-6c18-47db-8fc3-d3d12698265f) | Gairisa | Fab Standard, «Личное» | разрешён | `Fantasy_Forest` | 5.8 | тёмный лес по кромке Sarpedon |
| [Vine_Plants](https://www.fab.com/listings/23286ced-250a-4720-bb61-9017fbdc2446) | Gairisa | Fab Standard, «Личное» | разрешён | `Vine_Plants` | 5.8 | плющ/лианы: колоннада, задняя стена, руины форта |
| [Stylized Flowers Pots](https://www.fab.com/listings/4615cf5f-d95d-4e92-b815-65575488d4be) | Gairisa | Fab Standard, «Личное» | разрешён | `Flowers_Pots` | 5.5 → проект 5.8 | цветы в вазонах/клумбы Marmoreal |
| [Stylish Fire VFX (Free asset)](https://www.fab.com/listings/01e8534c-5877-4ce2-8948-9a696100de11) | VfxSTOCK | Fab Standard, «Личное» | разрешён | `Stylish_Fire_VFX` | 5.6 → проект 5.8 | огонь костров, фонарей, факелов; P9: слоистый огонь жаровни и форта (ядро `NS_Stylish_Fire_4`, языки `_1`, дым `_2`) |
| [Particles and Wind Control System](https://www.fab.com/listings/f673ef70-1c66-4c7f-8751-9f84ddb8b083) | Dragon Motion | бесплатно (Permanent Collection) | разрешён | `Particles_Wind_Control_System` | 5.8 | скачан, в игре **не используется**: его светлячки и свеча добавляют PointLight (бюджет света); огоньки взяты из Free Niagara Particles (P5c) |
| [Free Niagara Particles (CC BY 4.0)](https://www.fab.com/listings/183732bc-c2fb-465c-9453-f70a1ce7ba2c) | SoftTofuVFX | **CC BY 4.0** | разрешён | `FreeParticle_SoftTofu` | 5.8 | лепестки, перья, искры |
| [Water Materials](https://www.fab.com/listings/063155ea-d9d2-4f29-b09f-33270b0bc861) | tharlevfx | **CC BY 4.0** | разрешён | `WaterMaterials` (по факту папки) | 5.8 | вода реки/прибоя/водопада Sarpedon |
| FREE Stylized Rocks Pack - Stylized Stones & Boulders | StyleHex Studio | Fab Standard | **NoAI** | `StyleHex_Studio` | 5.8 | добавил пользователь 2026-10-01; только вариант раскладки для пользователя, кадры не подаются ИИ |

## Poly Haven CC0

ENV-MAPS P8 (Sarpedon, путь 1: настоящая 3D-подложка под живопись концепта). Модели [Poly Haven](https://polyhaven.com)
(лицензия **CC0**, атрибуция не требуется — перечислены для учёта), glTF, текстуры 1K; это CC0-содержимое пака
Smuggler's Cove. Скачал оркестратор 2026-10-02 в `C:/tmp/envmaps-research/p8/polyhaven/<id>/` (вне git, sha256 в
`manifest.json` той же папки). В git — только производная геометрия (FBX) и скрипты; текстуры Poly Haven в игре не
используются (альбедо — из de-lit плиты концепта, задание §2, риск R2).

| Ассет | Лицензия | Использование в P8.1 |
|---|---|---|
| [dutch_ship_large_01](https://polyhaven.com/a/dutch_ship_large_01) | CC0 | корпус → `SM_Env_S_Ship` (`tools/art/concept_scene/ship_build.py`: децимация, совмещение с нарисованным бортом по пикселям C0, срез невидимой дальней части; мачты собраны заново по пикселям рисунка) |
| [modular_fort_01](https://polyhaven.com/a/modular_fort_01) | CC0 | справочно (модули 8,5 м — не подошли к нарисованной руине; `SM_Env_S_Fort` собран из блоков по силуэту рисунка, `fort_build.py`) |
| dutch_ship_medium, modular_wooden_pier, wooden_barrels_01, wooden_crate_01, wooden_crate_02, wooden_lantern_01, cannon_01, stone_fire_pit, rock_moss_set_01, rock_moss_set_02, rock_07, rock_09, rock_face_01, rock_face_02, moon_rock_02, moon_rock_03, boulder_01, namaqualand_boulders_01, namaqualand_cliff_01, coastal_cliff_01, tree_stump_01, dead_tree_trunk, fern_02 | CC0 | скачаны про запас (P8.0), в P8.1 не экспортируются; бочки / ящики / камни / деревья сцены — из паков, уже лежащих в Content (EnvKit, StylizedForest, Fantasy_Forest) |

## Атрибуция CC BY 4.0

- «Free Niagara Particles» © SoftTofuVFX, CC BY 4.0, https://www.fab.com/listings/183732bc-c2fb-465c-9453-f70a1ce7ba2c — используется с изменениями (цвет/масштаб под ночную сцену): листья-лепестки `NS_leaf` и огоньки `NS_Sparkling_Animate_2` (P5c); `NS_Sparkling_Noise` (ENV-MAPS P9: угольки слоистого огня жаровни и форта `NS_Env_FireEmbers`, брызги каскада `NS_Env_FallsSpray`; цвет, размер, число частиц, CPU).
- «Water Materials» © tharlevfx, CC BY 4.0, https://www.fab.com/listings/063155ea-d9d2-4f29-b09f-33270b0bc861 — используются текстуры пака (T_Ocean_Foam, T_Water_Normal, T_Water_Normal_Large) в собственных материалах моря и водопада Sarpedon (`M_EnvSea`, `M_EnvWaterfall`, P5c).

## Состояние загрузок

Все паки из таблицы скачаны и лежат в `unreal/Unmatched/Content/<Папка>/` worktree и основной копии (2026-10-01 ~14:00).

## Отложено

- «Stylized Rocks» (Gerardo Justel, CC BY, только FBX) — прямое скачивание с fab.com требует входа в Epic в
  браузере; взять при следующем входе пользователя или заменить камнями из Forest.
