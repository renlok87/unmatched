# Бармаглот H2 на Marmoreal и Sarpedon

Бармаглот собран из нового GLB Tripo, перенесён на утверждённый риг из 24 костей и окрашен в сатиновое серебро. На обеих досках виден золотой ободок P1. Повторный импорт Unreal Engine 5.9 подтвердил 44 410 треугольников, материалы обеих команд и те же 18 контрольных поз. [Концепт](../../../../../../art/imagegen/concept-the-jabberwock-codex-1c-r3/sheet-the-jabberwock.png) · [Карточки приёмки 8,1](../../../../../../art/pipeline-candidates/ASSET-THE-JABBERWOCK-001/evidence/acceptance-concept/20261128-sheet-r2/final.json) · [Исходник Tripo и хэши](tripo-source.json) · [Повторный импорт](ue-reimport.json).

| Доска | Общий план | Бармаглот | Волк |
| --- | --- | --- | --- |
| Marmoreal | [K1](marmoreal/K1.png) | [K2](marmoreal/K2-TheJabberwock-f-0-sk0.png) | [K2](marmoreal/K2-Wolf-f-1-sk0.png) |
| Sarpedon | [K1](sarpedon/K1.png) | [K2](sarpedon/K2-TheJabberwock-f-0-sk0.png) | [K2](sarpedon/K2-Wolf-f-1-sk0.png) |

В положении покоя Бармаглот занимает 78,36% диаметра клетки, подставка — 75,44%. Предельный габарит в измеренных позах достигает 80%. Локальная правка нижнего ребра правого крыла убрала единственное пересечение с хвостом. Минимальный зазор до подставки в Blender составил 0,377 единицы Unreal, дрейф опор — менее 0,000008. [Замеры геометрии и движения](initial-h2-transfer.json) · [Сборка рига](build.json) · [Сравнение досок](comparison.jpg).

Пакеты Unreal расположены по путям относительно `Content`. Материалы опираются на общие мастер-ассеты предыдущего архива. Кадры сняты в нейтральной позе. Рабочее назначение ArtHub остаётся на стадии предпросмотра до проверки игровых клипов. [Манифест H2](ue-content/manifest.json) · [Общие материалы](../ue-preview-content/manifest.json) · [Отдельная проверка Волка](../motion-repair/README.md).
