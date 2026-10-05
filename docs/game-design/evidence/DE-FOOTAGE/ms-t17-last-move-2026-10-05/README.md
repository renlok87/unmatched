# MS-T-17: последний ход соперника на реальных досках (2026-10-05)

Кадры самопроверки задачи MS-T-17 (прогон D). Это не приёмка: G-LIVE делает агент приёмки в конце прогона, арт-приёмку
вида подложек (MS-Q-04, MS-T-27) делает пользователь.

**Как снято.** Свежий `-Bench` в editor `-game`, командой `live_tune.py bench`:
- флаги `-S08MovePlates -BenchMoveDraft=tools/s08/fixtures/move-draft/<доска>-4-last-move-opponent.json`;
- Marmoreal снят с `-ConceptPaste` (IMPL п. 3, ENV-U16 open), Sarpedon — без оговорок;
- командные строки — `*.cmdline.txt`, выдержки трассы — `*.trace.txt`.

**Сцена.** MS-S-00, наблюдение после манёвра соперника. Он восстановлен без анимации (MS-E-102): фикстура синтезирует
`metadata.lastMovement` с seq бенч-снапшота.
- Marmoreal: King Arthur M22 → M30 → M31, Merlin M24 → M23.
- Sarpedon: King Arthur S35 → S36 → S32, Merlin S26 → S25.

| Кадр | Что видно |
|---|---|
| `marmoreal-K1.jpg`, `marmoreal-K1-crop-M31-M23.jpg` | V-15: сплошной тонкий контур P2 (с разрывами шестигранника) на M31 и M23 вокруг Arthur и Merlin. V-14 на M22 и M24 — тот же контур при 60 %, на K1 едва различим |
| `marmoreal-K2x1p6-edge-arrow.jpg` | K2 на Medusa: концы пути за правым краем, у края экрана стрелка «→» (MS-E-73). Камера не двигалась |
| `sarpedon-K1.jpg` | V-15 на S32 и S25, V-14 на S35 и S26 |

**Трасса** (`marmoreal.trace.txt`):
- `MS-BENCH last … moves=2`;
- `MS-LAST enter seq=1`, затем `MS-LAST show seq=1 mode=restore from=3,3>6,3 to=5,5>5,3`;
- `MS-LOG … text="King Arthur: maneuver: King Arthur M22→M31, Merlin M24→M23"`;
- `MS-HL view source=bench … outline=4`;
- `MS-OPP arrow=1 cell=M31 …`.

**Проверено по кадрам:**
- доски реальные;
- задник Marmoreal нарисованный (`-ConceptPaste`), Sarpedon — lit3d;
- все шесть фигур — v2 (`ARTLOOK heroes=v2`).

**Замечание для MS-T-13 / MS-T-27.** Контур V-14/V-15 — это полоса 39,6–41,0 uu, у V-14 ещё и альфа 0,6. На K1 он
читается слабо, особенно V-14 на пёстрых зонах Marmoreal. Его толщину и альфу подбирают в MS-T-13, принимает
пользователь. Точки пути V-15 (M30, S36) в данных вида есть, но рисует их линия пути MS-T-09: материал подложки центральных
точек не рисует.
