# Звук: кандидаты, лицензии и происхождение (DE-013)

Задача DE-013 (W-25, арт; прогон A04, 2026-10-04). Это список лицензируемых звуков под точки синхронизации CUE
(SD-51). Он дополняет ART-010 (звук и VFX всех 18 CUE) и не заменяет его.

- Машиночитаемый список — [`audio/de013-sound-list.json`](audio/de013-sound-list.json).
- Проверка — `python tools/art/de013/de013.py check`.
- Тесты — `python -m pytest tools/art/tests/test_de013_sound_list.py`.

**Состояние на 2026-10-04.**
- Ни один звук не скачан и не импортирован, покупок нет.
- У всех CUE в `docs/unreal/contracts/cue-dispatcher/cue-table.json` остаётся `sfx.status = missing`.
- Скачивание, конвертация и импорт — ART-010 и DE-032 (в счёт GD-049).
- Выбор на слух под атмосферу D-02 — за пользователем (G-ART). Имена файлов в таблице — подсказки по листингам паков.
  Сами паки не скачивались, поэтому имена сверяются при скачивании (`file_hint_verified: false`).

## Правила

1. **Звуков DE нет.** Звуки Unmatched: Digital Edition не берутся и не записываются. Они не служат образцом для
   ресинтеза (EULA; SD-51; APPROXIMATION §13). Из DE взяты только моменты: кадр события, ±17 мс.
2. **Покупки делает только пользователь.** Платные источники и источники Fab (через аккаунт Epic пользователя) стоят в
   списке как альтернатива с `acquisition: user`. Основной источник каждого звука — бесплатное скачивание CC0, поэтому
   DE-013 и DE-032 ничего не ждут от пользователя, кроме прослушивания.
3. **Атрибуция.** Источник с `attribution_required: true` при импорте получает строку в
   `unreal/Unmatched/Licenses/THIRD_PARTY_NOTICES.txt` и в титрах (общие условия
   [18-third-party](../game-design/18-third-party-tools-and-assets-decisions.md)). У CC0 атрибуция не требуется, но
   строка Kenney всё равно пишется — так автор просит, и так учёт полнее.
4. **ИИ.** Файлы источника с `no_ai_training: true` (Sonniss) не загружаются в ИИ-сервисы.
5. **Моменты.** Моменты звуков — по SD-51 и колонке `sound` в `07-animation-vfx-audio.csv`. Длительность от скорости
   игры не зависит.

## Звуки по ролям

| Звук | CUE | Момент | Длина, мс | Основной источник | Лицензия | Файлы (подсказка) | Альтернативы |
|---|---|---|---|---|---|---|---|
| `SND-UI-CLICK` — клик выбора | CUE-002 (UI) | кадр визуального отклика нажатия (SD-51 п. 1, SD-46) | 30–150 | Interface Sounds (Kenney) | CC0 1.0 | `click_001…005` / `select_001…008` | Free UI Soundpack (Fab, только пользователь); Tabletop SFX (JDSherbert, только пользователь) |
| `SND-UI-CONFIRM` — подтверждение клетки или цели | CUE-003 (UI) | кадр визуального отклика нажатия | 60–250 | Interface Sounds (Kenney) | CC0 1.0 | `confirmation_001…004` | Free UI Soundpack; RPG Audio `metalClick` |
| `SND-HIT` — удар | CUE-011 (SFX, ≤ 2 одновременно) | кадр контакта: AnimNotify `Contact` (DE-010), фолбэк — кадр профиля (SD-51 п. 2) | 250–1000 | Impact Sounds (Kenney) | CC0 1.0 | `impactPunch_heavy_000…004` / `impactPlate_heavy_000…004` | Sonniss GDC Bundle; RPG Audio `knifeSlice` / `chop` |
| `SND-STEP` — шаг | CUE-007 (SFX, ≤ 1, StopOldest) | начало каждого ребра, 280 мс на ребро (F-02); один звук на ребро, без касания на прибытии (APPROXIMATION §15 п. 15) | 60–250 | Impact Sounds (Kenney) | CC0 1.0 | `footstep_wood_000…004` / `footstep_carpet_000…004`, без повтора подряд | Tabletop SFX (только пользователь); RPG Audio `footstep00…09` |
| `SND-TURN-CHIME` — перезвон своего хода | CUE-015 (UI) | кадр старта кольца, только свой ход; ход соперника беззвучен (SD-51 п. 4) | 300–1700 | Interface Sounds (Kenney) | CC0 1.0 | `bong_001` | Music Jingles, короткий `jingles_PIZZI*`; Free UI Soundpack |
| `SND-STING-WIN` — стинг победы | CUE-016 (Music) | появление экрана результата (SD-51 п. 5) | 2000–3000 | Music Jingles (Kenney) | CC0 1.0 | `jingles_PIZZI*` / `jingles_HIT*`, мажорные | Incompetech (CC BY 4.0, обрезка 2–3 с); Sonniss |
| `SND-STING-LOSE` — стинг поражения | CUE-016 (Music) | появление экрана результата | 2000–3000 | Music Jingles (Kenney) | CC0 1.0 | `jingles_PIZZI*` / `jingles_HIT*`, минорные | Incompetech; Sonniss |

Характер звуков описан в поле `character` списка. Коротко:
- клики — сухое дерево или кость, без синтетики;
- шаг — мягкое касание подставки о поле, а не сапог по камню;
- удар — плотный, с коротким хвостом;
- стинги — струнные или ударные, без электроники.

Наборы NES и SAX из Music Jingles под атмосферу D-02 не подходят и в кандидаты не включены.

## Источники и лицензии

| id | Источник | Автор | Лицензия | Атрибуция | Цена / как получить | ИИ | Проверено |
|---|---|---|---|---|---|---|---|
| `kenney-interface-sounds` | [Interface Sounds](https://kenney.nl/assets/interface-sounds) | Kenney | [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) | не требуется | бесплатно, скачивание | можно | 2026-10-04, страница пака: CC0, 100 файлов OGG |
| `kenney-impact-sounds` | [Impact Sounds](https://kenney.nl/assets/impact-sounds) | Kenney | CC0 1.0 | не требуется | бесплатно, скачивание | можно | 2026-10-04: CC0, 130 файлов (impact, foley) |
| `kenney-rpg-audio` | [RPG Audio](https://kenney.nl/assets/rpg-audio) | Kenney | CC0 1.0 | не требуется | бесплатно, скачивание | можно | 2026-10-04: CC0, 50 файлов (foley, footstep, weapon) |
| `kenney-music-jingles` | [Music Jingles](https://kenney.nl/assets/music-jingles) | Kenney | CC0 1.0 | не требуется | бесплатно, скачивание | можно | 2026-10-04: CC0, 85 джинглов OGG на 5 инструментах |
| `jdsherbert-tabletop-sfx` | [Tabletop Games SFX Pack](https://jdsherbert.itch.io/tabletop-games-sfx-pack) | JDSherbert | royalty-free, LICENSE.pdf в паке; видимый кредит обязателен, перепродажа и публичные репозитории с файлами запрещены | **обязательна** | £4.99+ (есть урезанная бесплатная) — **только пользователь** | можно | 2026-10-04, страница itch.io; кредит — ревью 2026-09-27; решение «Позже» — 18-third-party |
| `sonniss-gdc-bundle` | [GDC Game Audio Bundle](https://sonniss.com/gameaudiogdc) | Sonniss и авторы | [лицензия бандла](https://sonniss.com/gdc-bundle-license/): коммерческое использование без атрибуции, без перепродажи файлов | не требуется | бесплатно, скачивание (гигабайты) | **нельзя** (обучение ИИ запрещено) | 2026-10-04, страница бандла |
| `incompetech-cc-by` | [Incompetech](https://incompetech.com) | Kevin MacLeod | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | **обязательна** | бесплатно, скачивание | можно | ресёрч 2026-09-27 (каталог §7.4); на 2026-10-04 не перепроверялся |
| `fab-cyrex-free-ui` | [Free UI Soundpack](https://www.fab.com/listings/4fe9dac3-1db6-4825-ad97-20f121032738) | Cyrex Studios | Fab Standard License | не требуется | бесплатно, но через аккаунт Epic — **только пользователь** | можно | ресёрч Fab 2026-10-01 §4.6 |

## Строки атрибуции (черновик для THIRD_PARTY_NOTICES и титров)

Вносятся при импорте только для реально взятых источников.

- Interface Sounds, Impact Sounds, RPG Audio, Music Jingles by Kenney (kenney.nl), CC0.
- Tabletop Games SFX Pack by JDSherbert (jdsherbert.itch.io) — если пользователь купит пак.
- "<Название трека>" Kevin MacLeod (incompetech.com), Licensed under Creative Commons: By Attribution 4.0 License — если
  стинг возьмут из Incompetech.

## Порядок импорта (ART-010 / DE-032)

1. Скачать основной пак (CC0) вне git, например в `C:/tmp/audio-src/<id>/`. Положить рядом `manifest.json` с URL, датой
   и sha256 архива и файлов.
2. Прослушать варианты. Выбор на слух — за пользователем (G-ART). Отметить выбранный файл в
   `de013-sound-list.json`: `file_hint` → точное имя, `file_hint_verified: true`, `acquired: true`.
3. Конвертировать в WAV 48 кГц / 16 бит и обрезать тишину. Длина должна попасть в `length_ms`. Стинг, который не
   укладывается в 2–3 с, заменяется следующим кандидатом; не растягивать.
4. Импортировать в `/Game/Audio/Cue/` и задать класс звука по `sound_class`. Пути удерживать в cook
   (`asset_path_rule` в `cue-table.json`).
5. В `cue-table.json` указать `sfx.sound` и сменить `status` на `present`. Гейт G-CUE.
6. Строку атрибуции внести в `THIRD_PARTY_NOTICES.txt`, а в этом файле сменить статус источника на «импортирован».
