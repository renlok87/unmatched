# ART-003 / ASSET-MARKERS-001 · самоприёмка игрового прицела в K3

**Следующий шаг:** [позднейшая техническая самоприёмка пиктограммы и числа урона](live-combat-icon-damage-acceptance-2026-09-28.md). Изложенный ниже статус относится к исходному прогону прицела.

**Решение 2026-09-28:** принять техническую привязку `SM_Marker_TargetRing` к цели боя и отдельного `SM_Marker_SelectionRing` к атакующему в режиме `-ArtPreview`. **Полный K3, ART-003, QA-010 и GD-058 не принимать.** Маркеры следуют `fighterId`: локальному законному выбору в `AttackDraft`, затем авторитетному `metadata.combatInfo` в `COMBAT`/`COMBAT_RESOLVE`. После закрытия боя они снимаются. Меш прицела не участвует в `Visibility`-трассировке игрового клика (`NoCollision`). Это не новая модель персонажа и не проверка анимации.

Два packaged Development клиента сыграли реальную автоматизированную партию на Cobble 5×6 с `-ArtPreview` и 1920×1080. [Кадр защитника после раскрытия](live-combat-target-run/combat-20260928-065907/joiner/s09-combat-resolve-revealed.png) показывает Medusa с золотым сплошным кольцом как атакующего и Arthur с четырьмя коралловыми дугами как цель. Форма дуг читается отдельно от синего командного основания. На [кадре результата](live-combat-target-run/combat-20260928-065907/joiner/s09-combat-result.png) прицела уже нет; HUD сообщает, что Arthur получил 2 урона. Начальный [кадр окна защиты](live-combat-target-run/combat-20260928-065907/joiner/s09-combat-defense-open.png) попал на краткое переподключение WS: баннер `RECONNECTING` виден поверх HUD, поэтому для оценки композиции использовать кадр после раскрытия, а не скрывать этот дефект съёмки.

[Манифест прогона](live-combat-target-run/combat-20260928-065907/manifest.json) содержит 7 опубликованных файлов и SHA-256; все 7 хешей сверены. Существующие state-marker gates для защиты, разрешения и результата прошли вместе с отрицательными проверками, pre-reveal privacy gate и `seq=113` на обоих клиентах. В каждой опубликованной трассе по 10 включений целевого прицела и 10 включений кольца атакующего; выключение после боя также присутствует. Секреты демонстрационных аккаунтов в опубликованных трассах не найдены. Партия завершилась `FINISHED`. Сборка `Unmatched Win64 Development` и `BuildCookRun -skipbuild` завершились успешно. Процессам передан лимит `t.MaxFPS 30`; фактический FPS, GPU frame time и совместная загрузка GPU этим актом **не измерялись**.

Первая попытка снимала 888×500: оконный режим уменьшил viewport вопреки сохранённым 1920×1080. В повторном прогоне флаг `-ForceRes` дал проверенные 1920×1080. Непрошедшая попытка не использована как приёмочный кадр и не публиковалась в репозитории.

**Открыто для полного K3:** отдельная пиктограмма над целью (сейчас лишь форма четырёх дуг), заметный эффект результата/урона на фигурке, не перекрывающие друг друга имена и HP на центральных клетках, инспектор карты рядом с целью, grayscale/deuteranopia, альтернативные световые секции и сценарий 1280×720/UI 150 %. Финальные Arthur/Merlin/Harpy ещё серые блок-ауты; подготовка новых анимаций приостановлена по решению пользователя. Ни экранная яркость прицела, ни 30 FPS-прогон не утверждают финальную палитру или бюджет D-07.

Абсолютные пути для следующего агента:

- `C:/Users/ren/WebstormProjects/unmached/unmached/docs/game-design/evidence/ART-003/live-combat-target-run/combat-20260928-065907/joiner/s09-combat-resolve-revealed.png`
- `C:/Users/ren/WebstormProjects/unmached/unmached/docs/game-design/evidence/ART-003/live-combat-target-run/combat-20260928-065907/joiner/s09-combat-result.png`
- `C:/Users/ren/WebstormProjects/unmached/unmached/docs/game-design/evidence/ART-003/live-combat-target-run/combat-20260928-065907/manifest.json`
- `C:/Users/ren/WebstormProjects/unmached/unmached/tools/s09/run-combat-demo.ps1`
- `C:/Users/ren/WebstormProjects/unmached/unmached/docs/game-design/03-art-direction.md`
