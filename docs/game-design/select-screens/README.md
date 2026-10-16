# SEL — выбор героя и поля в духе файтингов

Задача пользователя (2026-10-16): ресерч экранов выбора бойца и арены в файтингах (ориентир Mortal Kombat, Injustice),
документация, референсы через Codex ImageGen, валидация Opus xhigh, план и реализация в игре.

| Файл | Что |
|---|---|
| `01-research-fighting-games.md`, `refs-urls.md` | Ресерч: MK1, MK11, Injustice 2, SF6, Tekken 8, Smash, GGST, MvC/DBFZ, Unmatched DE; синтез и 20 рекомендаций |
| `02-DESIGN.md` | Дизайн: поток, раскладки, состояния, 3D-витрины, звук; v2 после ревью (§11) |
| `03-PLAN.md` | План реализации, что сделано, что открыто |
| `04-REVIEW-OPUS.md` | Валидация Opus xhigh: PASS-WITH-FIXES, цель — вариант A |
| `../../../art/imagegen/select-screens-codex/` | 8 референсов Codex ImageGen (4 экрана × A/B), README с промптами |
| `frames/` | Кадры живого клиента: WIP до правок и v2 после |

Откат в игре: `-S08SelectLegacy` (прежняя комната SC-14…SC-18 и загрузка SC-19).
