# Музыка-кандидаты: SYNTX · Suno v6 (2026-10-05)

Сгенерировано по просьбе пользователя («Музыку нужно генерить с помощью Syntex AI»). Сами MP3 лежат вне git, в
`C:/tmp/audio-src/syntx-suno-2026-10-05/`, по правилу импорта звука ([CREDITS-audio.md](../../../docs/art-pipeline/CREDITS-audio.md),
«Порядок импорта» п. 1). Здесь — [manifest.json](manifest.json): исходные URL, sha256, длительность, громкость.

| Файл | Назначение | Длина |
|---|---|---|
| `marmoreal-loop-a/b` | фон партии на Marmoreal | 157 / 153 с |
| `sarpedon-loop-a/b` | фон партии на Sarpedon | 157 / 157 с |
| `menu-theme-a/b` | меню и лобби | 88 / 67 с |
| `sting-victory-a/b` | CUE-016, `SND-STING-WIN` | 8 / 10 с, нужна обрезка до 2–3 с |
| `sting-defeat-a/b` | CUE-016, `SND-STING-LOSE` | 12 / 13 с, нужна обрезка до 2–3 с |

Громкость −13,8…−15,8 LUFS, true peak до −0,4 dBFS. На слух не проверено: вокал, швы петли и выбор — за пользователем.

## Промпты (режим «Свой», инструментал, исключено: vocals, singing, choir, voice, rap, EDM, drops, electric guitar, synth lead)

- **Marmoreal:** instrumental, background music for a turn-based fantasy tabletop strategy game, night garden of a white
  marble palace, cherry blossoms, warm lanterns, calm but tense, thoughtful, harp, pizzicato strings, soft french horn,
  celesta, low frame drum, 90 bpm, D dorian, steady dynamics, no build-ups, seamless loop, cinematic chamber orchestra.
- **Sarpedon:** instrumental, background music for a turn-based fantasy tabletop strategy game, sunlit pirate island with
  a waterfall, old cannons, sea breeze, adventurous but restrained, strategic focus, acoustic guitar, fiddle, accordion,
  low strings ostinato, hand drums, light tin whistle, 96 bpm, A minor, steady dynamics, no build-ups, seamless loop,
  cinematic folk orchestra.
- **Меню:** instrumental, main menu theme for a fantasy tabletop dueling game where legendary heroes from myth and
  history clash, heroic and inviting, warm board-game night mood, full orchestra with french horns melody, strings, harp
  arpeggios, timpani, light snare, celesta sparkle, 100 bpm, C major to A minor, memorable short motif, moderate
  dynamics, loopable ending that returns to the opening.
- **Победа:** very short victory fanfare jingle … triumphant brass fanfare, french horns and trumpets, timpani roll, harp
  glissando, cymbal swell, bright major key, final sustained major chord, under 10 seconds.
- **Поражение:** very short defeat jingle … somber but dignified, low strings and muted horn descending phrase, soft
  timpani hit, harp, minor key, final sustained minor chord, under 10 seconds, not comedic.

## Права

Коммерческое использование не решено — см. [RESEARCH-2026-10-05.md](../../../docs/game-design/de-footage/task/runs/RESEARCH-2026-10-05.md):
оферта SYNTX передаёт права заказчику, но права Suno на коммерцию даются за скачивание через сам Suno (Pro/Premier);
п. 9.3 оферты SYNTX запрещает автоматизированный доступ.
