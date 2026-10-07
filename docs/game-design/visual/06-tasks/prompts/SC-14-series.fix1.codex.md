# CX-30 fix1 - corrective run of the ROOM series SC-14 ... SC-18

Written by Claude after the single review pass of run 1 (07 §5, 05 §1.4: one corrective run, never a second).
Decisions ВР-VS4-SC14-13…15, ВР-VS4-SC17-03 and ВР-VS4-SC18-02 by delegation, 2026-10-07.

## Task

```text
Corrective run fix1 of series CX-30 (packages art/imagegen/sc14-room-hero-codex/, sc15-room-board-codex/,
sc16-room-deck-codex/, sc17-room-ready-codex/, sc18-room-countdown-codex/). Read
docs/game-design/visual/06-tasks/prompts/SC-14-series.codex.md again: every rule and decision there still holds.
Fix exactly the points below and nothing else; keep everything that is not named here. Same limits as run 1: write
only into the five package folders and their scraped-data/derived/<set>-codex/ folders, never change inputs/, no
git, no MCP, no network, nothing under unreal/, no image generation.

1. ВР-VS4-SC14-13 (deck row without a hero, sc14_room_hero.py): when the viewer's seat has no hero, DeckCount is not
   drawn; the row shows only «ПРОСМОТР КОЛОДЫ» disabled with why.room.no.hero «Выберите героя». Run 1 printed
   «Колода: 30 карт» in SC-14 waiting and taken although the viewer had no hero. Frames with a hero keep the count.
2. ВР-VS4-SC14-14 (sc14_room_hero.py): the attack phrase «ближний бой» / «дальний бой» never breaks across lines
   (treat it as one unit). If a sidekick line must wrap, it wraps before the phrase: «Harpies ×3 · HP 1 ·» /
   «ближний бой». Run 1 split it as «… ближний» / «бой» on the L canvases.
3. ВР-VS4-SC18-02 (sc18_room_countdown.py): the countdown text sits on a centred plate: panel.bg 1.0 body,
   panel.edge 1 su, radius 8 su (library kind "modal" look), hugging the text with 32 su horizontal and 24 su
   vertical padding, at least 160 su wide; centred on the canvas. Nothing of the ROOM shows through the plate; the
   second 0.8 veil stays over the rest of the screen. The plate is reported as kind "modal" in verification.json;
   measure the text contrast against the plate. Run 1 drew «3» and «Партия начинается…» bare over the dimmed ROOM,
   where they collided with ROOM text at 720p 100 % and 150 % («Выбран соперником», «ВЫБРАНО»).
4. ВР-VS4-SC17-03 (sc17_room_ready.py, leave frame): the confirmation dialog hugs its content: the SC-01 base modal
   width for the canvas class (640 su on L), height = 24 su padding + title (type.title) + 24 su gap + 48 su
   button row + 24 su padding, centred on the canvas; «ОТМЕНА» normal left, «ДА» primary right as in SC-01. Extend
   in your module; the library copy stays unchanged. Run 1 left about 200 su of empty modal body under the title.
5. ВР-VS4-SC14-15 (overlays of all five packages): every rectangle carries its x, y, w, h in su (label at the
   frame or a legend keyed to the frame), and each card's overlay also shows its own inner elements:
   SC-14 — for both hero cards Portrait, NameText, StatsText, AttackText, SidekickRow, AbilityText, PickButton,
   and for both slots Avatar, NameText, HostChip, ReadyText, HeroLine, SidekickLine;
   SC-15 — UUmBoardCard[0..1] with thumbnail, name, check chip, and the locked reason text;
   SC-16 — DeckCount, DeckButton and the deck modal named UUmScreenInspect (deck mode), not UUmConfirmDialog;
   SC-17 — LeaveButton, StatusText, ReadyButton, StartButton with its why text, and UUmConfirmDialog (title,
   two buttons) after point 4;
   SC-18 — CountText and its plate.
   Overlays stay outlines and labels on plain card.navy: no frame, avatar, map or scan pixels (ВР-VS4-01).

Chain: after points 1-2 the FINAL sc14_room_hero.py changes, so copy it again unchanged into SC-15, SC-16, SC-17 and
SC-18, and the FINAL sc17_room_ready.py into SC-18; re-render every frame of all five packages on all four canvases
in colour and grey. Record a "fix1" block in each verification.json (what changed, sha256 before and after of every
changed file, copy hashes) and keep acceptance honest. Rebuild manifest-sha256.json of each package. Add a short
section «fix1» to each card README (Russian). Open and look at every final PNG again before you finish (colour and
grey, all four canvases) and record that in visual-review.json.
```
