# Покрытие спецификации 17

Этот файл сопоставляет визуальные исходники с требованиями. Актуальное наличие каждого PNG, промпт, размеры и SHA-256 — в `manifest.json`. Счётчик PNG не является приёмкой игровых ассетов.

## Реестр 06 и требования 02/17

| Требование | Источники пакета | Что нужно после imagegen |
|---|---|---|
| Medusa, Arthur, Merlin, Harpy, fallback | `characters/`, 5 листов | Меши, UV, риг, 4 основных клипа, сокеты, FBX; одна Harpy для 3 экземпляров |
| Cobble City | `environment/ref-board-cobble.png` | Геометрия по S04: 5×6, 30 клеток, blue/red, 49 связей; PNG не задаёт коллизии |
| Поднос и набор декора | `environment/`, 7 листов кроме доски | Blender/UE, размещение и проверка перекрытия поля |
| Подставки и маркеры | `markers/`, 6 графических источников и 4 листа подставок | Геометрия/декали, командные параметры, мировой текст и номера гарпий |
| Плоскости карт | `ui/cards/` и оригинальные cardArt | Меш CardFace/CardBack и материал с параметром изображения |
| 27 cardArt, D-09 | `reused-cardart.json`: EN 27/27, RU 27/27 локально | Проверка содержимого RU, синхронизация, формат/импорт; imagegen их не перерисовывает |
| M_DioramaMaster | `materials/`, 6 цветовых источников | UV-зависимые BC/N/ORM, shader graph, DirectX normals, повторяемость текстур |
| M_HighlightGameLayer | `markers/`, `vfx/` | Материал, пульс и параметры; формы/цвета не являются серверной логикой |
| M_CardPlane | рамки, рубашки, исходные cardArt | Двусторонний материал, параметры, динамический текст |
| UI-FONT | PNG не подходит | Лицензированный RU/EN TTF/OTF regular/bold, UFont и fallback |
| UI-ICON-ACTION | 5 действий × 3 состояния + отказ | Экспорт 128², проверка 24 px; свободный pass/endTurn исключены по 12/15 |
| UI-ICON-RESOURCE | HP full/empty, action full/empty, boost, card, 3 состояния связи | Экспорт 96²; одинаковые точки привязки состояний |
| UI-ICON-ZONE | blue diamond / red circle × normal/selected | Буквенные подписи отдельным runtime-текстом; 12 зон не утверждены |
| UI-CARD-FRAME | 4 типа × 5 состояний | Точные размеры, nine-slice и layout значений/текста; не запекать RU/EN |
| UI-CARD-BACK | Общая рубашка и вариант с пломбой | Экспорт 180×252, nine-slice |
| UI-PANEL | normal, active-turn, error, hand-tray | Nine-slice, содержание 11 блоков HUD |
| UI-BUTTON | Все 6 состояний | Nine-slice, подписи, фокус и интерактивные области |
| UI-CURSOR | default, pointer, unavailable, busy | Экспорт 64², hotspot; busy требует анимации |
| UI-LOADER | spinner, progress, skeleton × normal/error | Анимация и заполнение прогресса, атлас/растяжение |
| Портреты HUD, AD-OPEN-35/37 | `ui/portraits/`, 4 собственных персонажа | Размеры, рамки и привязки к бойцам; не заменяют D-09 |

## 18 CUE

| CUE | Визуальный источник / представление |
|---|---|
| 001 | Курсор; тонкий rim-контур фигурки/клетки материалом |
| 002 | Selection P1/P2 и подставки |
| 003 | Move/target marker; сжатие кольца/заливки при подтверждении |
| 004 | Refusal и unavailable cursor; текст причины отдельно |
| 005 | Card trail |
| 006 | Card glow, рамки и рубашки |
| 007 | Dust и перемещение акторов |
| 008 | Attack direction, target; клип LungeAttack |
| 009 | Shield и рамка DEFENSE |
| 010 | Combat impact, значения отдельным текстом |
| 011 | Damage flash; HitReact и число −N отдельно |
| 012 | Heal motes; число +N отдельно |
| 013 | Death ash; DeathSettle/fade отдельно |
| 014 | Medusa cracks / Arthur sword glow; луч, сокеты и шейдер отдельно |
| 015 | Active-turn panel; пульс кромки параметрами материала |
| 016 | Result panel; тёплый/холодный постпроцесс отдельно |
| 017 | Connection lost/reconnecting; десатурация сцены отдельно |
| 018 | Connection online и panel для тоста |

Ни один PNG не содержит тайминги, серверные события, дедупликацию, interrupt/reconnect-поведение или звук. Эти части 07 остаются реализацией UE.

## Приёмка

Открыты: редактируемые мастера; точный runtime-экспорт; выравнивание вариантов; альфа-композитинг и читаемость 24 px; 720p/150%; 9 экранов / 11 HUD-блоков; материал и VFX на минимальных настройках; GD-058, ART/GD/ACC и авторское утверждение стиля. Сгенерированные референсы не выдаются за контрольные кадры из UE.
