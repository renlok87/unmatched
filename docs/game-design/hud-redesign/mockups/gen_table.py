"""Generate direction "Стол" mockup pages into src/ (v3 after the Opus/Astra reviews). Then run render.py.

Every page is built from the same shared blocks, so the mockups stay one system. Layout classes follow the real UMG
classes (UmHudLayout / UmHudScale): L for a 1920x1080 su canvas, S for the 1280x720 su canvas (1920x1080 at UI 150 %)
and the 1280x720 window (canvas 1706x960 su, DPI 0.75). Pages declare viewport and device scale in src/_meta.json,
which render.py reads.

Real data only: hero art, card faces and backs come from scraped-data/derived/ue-media-v1 (backend media), card values
are the backend values (Snipe 3/BOOST 1, Regroup 1, Gaze of Stone 2/BOOST 4, Aid the Chosen One 4, Dash 3 ...), action
discs are the user-accepted DE-012 glyphs, the boards are the clean Marmoreal / Sarpedon bench frames (camera K1).

One consistent match snapshot runs through the states (Medusa is the local player P1, King Arthur is P2):
  turn 3: Medusa 16 HP, harpies 1-3 alive; Arthur 18, Merlin 5 (two hits of Medusa's start-of-turn ability earlier).
  A1 action 1 of 2 -> A2 attack with Snipe (3): the attack leaves on the target click (SD-56), no confirm button
  -> A3 reveal Snipe 3 vs Regroup 1: Arthur 18 -> 16 -> the turn passes by itself after the second action
  -> A4 turn 4: Merlin (ranged) attacks Medusa, she defends with Dash (3) -> B3 Aid the Chosen One 4 vs Dash 3:
  Medusa 16 -> 15, combat parks at the edges, Dash's "after combat: move up to 3" asks for a cell
  -> B1 turn 5 start: Medusa's ability has no target, auto-skip -> B2 turn 6 Arthur plays a scheme
  -> A5 turn 7 end with 9 cards: discard down to 7.
Known limit: the bench camera K1 puts every figure on fixed cells, so ranged targets in A2/A4 do not share a zone with
the attacker; the rings show the visual language, legality comes from the live snapshot (06 §4).
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = "../../../../.."
MEDIA = f"{ROOT}/scraped-data/derived/ue-media-v1"
ICON = f"{ROOT}/art/imagegen/hud-icons-de012-codex/vector-codex/1024"
BOARD = f"{ROOT}/docs/art-pipeline/evidence/beowulf-20261014/bench-marmoreal/bench-K1-1920x1080.jpg"
SARPEDON = f"{ROOT}/docs/art-pipeline/evidence/beowulf-20261014/bench-sarpedon/bench-K1-1920x1080.jpg"

FONTS = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cormorant+SC:wght@600;700'
         '&family=Forum&display=block">')

# Board anchor points of the Marmoreal bench frame, in px of a 1920x1080 frame
ARTHUR = (1225, 745)
MERLIN = (1297, 630)
MEDUSA = (515, 490)
HAND5 = ["gaze-of-stone", "snipe", "the-hounds-of-mighty-zeus", "a-momentary-glance", "regroup"]
FEED3 = ["<b>Медуза</b>: способность — 1 урон Мерлину", "<b>Артур</b> — манёвр, +1 карта", "<b>Мерлин</b> → 2 клетки"]


class L:
    """Layout class sizes in su (CSS px of the canvas)."""
    name = "L"
    hero_w, hero_h, art_w = 420, 184, 150
    opp_w, opp_h, opp_art = 404, 140, 120
    card_w, card_h = 200, 278
    pile_w, pile_h = 112, 156
    cmd_w = 220
    disc = 60
    feed = True
    piles_above_cmd = False
    name_px = 32


class S(L):
    name = "S"
    hero_w, hero_h, art_w = 312, 142, 96
    opp_w, opp_h, opp_art = 360, 104, 84
    card_w, card_h = 150, 208
    pile_w, pile_h = 64, 90
    cmd_w = 200
    disc = 48
    feed = False
    piles_above_cmd = True
    name_px = 26


class Page:
    def __init__(self, W=1920, H=1080, lay=L, board=BOARD, cls="m-dark f-cormorant", out=(1920, 1080)):
        self.W, self.H, self.lay, self.board, self.cls, self.out = W, H, lay, board, cls, out
        self.k = max(W / 1920, H / 1080)  # background-size: cover scale

    def at(self, xy):
        """Map a 1920x1080 board anchor into this canvas (background cover, centred)."""
        x, y = xy
        ox = (self.W - 1920 * self.k) / 2
        oy = (self.H - 1080 * self.k) / 2
        return int(x * self.k + ox), int(y * self.k + oy)

    # ---------- blocks ----------
    def top_left(self, turn="Ход 3"):
        return (f'<div class="abs iconbtn" style="left:24px;top:22px">≡</div>'
                f'<div class="abs ghost" style="left:82px;top:31px;font-size:18px">{turn}</div>')

    @staticmethod
    def disc_img(kind, size):
        src = f"{ICON}/slot-filled-{kind}.png" if kind else f"{ICON}/marker-action-slot-de.png"
        return f'<img src="{src}" style="width:{size}px;height:{size}px;display:block">'

    def opponent(self, hp=18, merlin=5, glow=False, filled=(), hand=5, deck=24, discard=1,
                 status="движение 2 · ближний бой", active=None):
        a = self.lay
        ring = "box-shadow:0 0 0 3px var(--team-p2),0 0 22px 4px rgba(90,127,159,.6),var(--shadow);" if glow else ""
        bw = 52 if a.name == "L" else 40
        st = int(bw * .42)
        backs = "".join(
            f'<div class="back" style="width:{bw}px;height:{int(bw*1.38)}px;left:{i*st}px;top:0;'
            f'transform:rotate({(i-(hand-1)/2)*4}deg);background-image:url(\'{MEDIA}/backs/king-arthur.png\')"></div>'
            for i in range(hand))
        count = f'<div class="abs countchip" style="left:{(hand-1)*st+bw-14}px;top:{int(bw*1.38)-24}px">{hand}</div>'
        slots = "".join(self.disc_img(filled[i] if i < len(filled) else None, 28) for i in range(2))
        name_px = 26 if a.name == "L" else 22
        act = ""
        if active:
            card, label = active
            act = (f'<div class="abs activeslot" style="right:24px;top:{a.opp_h+64}px">'
                   f'<div class="mini" style="background-image:url(\'{MEDIA}/cards/king-arthur/{card}.ru.png\')"></div>'
                   f'<div class="ghost" style="font-size:18px;text-align:right">{label}</div></div>')
        return f"""<div class="abs stock hero tint-arthur" style="right:24px;top:20px;width:{a.opp_w}px;height:{a.opp_h}px;{ring}">
  <div class="art" style="width:{a.opp_art}px;background-image:url('{MEDIA}/avatars/king-arthur.png')"></div>
  <div class="band" style="left:{a.opp_art}px;background:var(--hero-arthur)"></div>
  <div class="txt" style="left:{a.opp_art+18}px;top:8px">
    <div class="name" style="font-size:{name_px}px;line-height:{name_px+2}px">Король Артур</div>
    {'' if a.name == 'S' else f'<div class="meta body" style="font-size:18px">{status}</div>'}
  </div>
  <div style="position:absolute;right:10px;{'bottom:12px' if a.name == 'S' else 'top:10px'};display:flex;gap:4px">{slots}</div>
  <div class="side" style="left:{a.opp_art+18}px;bottom:10px">
    <div class="dial mid team-p2"><b>{hp}</b></div>
    <div class="body" style="font-size:18px;color:var(--ink-2);margin-left:4px">Мерлин</div>
    <div class="dial small team-p2{' hurt' if merlin < 7 else ''}"><b>{merlin}</b></div>
  </div>
  <div class="inner"></div>
</div>
<div class="abs" style="right:{a.opp_w+44}px;top:28px;width:{hand*st+bw+10}px;height:{int(bw*1.38)+8}px">{backs}{count}</div>
<div class="abs ghost" style="right:30px;top:{a.opp_h+28}px;font-size:18px;opacity:.9">колода {deck} · сброс {discard}</div>{act}"""

    def strip(self, filled=(), stage="выбор действия", discard_node="off"):
        a = self.lay
        size = 34 if a.name == "L" else 30
        nodes = self.disc_img(filled[0] if len(filled) > 0 else None, size) + '<span class="sep"></span>' + \
            self.disc_img(filled[1] if len(filled) > 1 else None, size)
        dn = {"off": "node-off", "next": "node-next", "now": "node-now"}[discard_node]
        nodes += f'<span class="sep"></span><span class="node {dn}">≤7</span>'
        top = self.H - 24 - a.hero_h - 46
        return (f'<div class="abs strip" style="left:24px;top:{top}px;width:{a.hero_w}px">{nodes}'
                f'<span class="stage">{stage}</span></div>')

    def player(self, hp=16, harpies=("alive", "alive", "alive"), glow=False, status="движение 3 · дальний бой",
               ability=True):
        a = self.lay
        ring = "box-shadow:0 0 0 3px var(--team-p1),0 0 22px 4px rgba(232,192,106,.55),var(--shadow);" if glow else ""
        hs = "".join(f'<div class="dial small team-p1{" dead" if s == "dead" else ""}"><b>{i+1}</b></div>'
                     for i, s in enumerate(harpies))
        big = "big" if a.name == "L" else "mid"
        abil = ('<div class="abil">Начало хода: 1 урон бойцу соперника в зоне Медузы</div>'
                if ability and a.name == "L" else "")
        return f"""<div class="abs stock hero tint-medusa" style="left:24px;bottom:24px;width:{a.hero_w}px;height:{a.hero_h}px;{ring}">
  <div class="art" style="width:{a.art_w}px;background-image:url('{MEDIA}/avatars/medusa.png')"></div>
  <div class="band" style="left:{a.art_w}px;background:var(--hero-medusa)"></div>
  <div class="txt" style="left:{a.art_w+20}px"><div class="name" style="font-size:{a.name_px}px;line-height:{a.name_px+2}px">Медуза</div>
    {'' if a.name == 'S' else f'<div class="meta body" style="font-size:18px">{status}</div>'}{abil}</div>
  <div class="side" style="left:{a.art_w+20}px">
    <div class="dial {big} team-p1"><b>{hp}</b></div>
    <div style="display:flex;flex-direction:column;gap:4px;margin-left:10px">
      <div class="body" style="font-size:18px;color:var(--ink-2)">Гарпии</div>
      <div style="display:flex;gap:5px">{hs}</div>
    </div>
  </div>
  <div class="inner"></div>
</div>"""

    def corridor(self):
        a = self.lay
        x0 = 24 + a.hero_w + 24
        right_block = a.cmd_w + 28 + 16 if a.piles_above_cmd else a.cmd_w + 28 + 2 * a.pile_w + 40
        return x0, self.W - right_block

    def hand(self, cards=HAND5, sel=(), dim=(), mark=(), low=False, hover=None):
        a = self.lay
        n = len(cards)
        x0, x1 = self.corridor()
        w, h = a.card_w, a.card_h
        step = min(w * .86, (x1 - x0 - w) / max(n - 1, 1))
        left0 = (x0 + x1 - w - step * (n - 1)) / 2
        base = self.H - int(h * (0.62 if low else 0.80))
        out = []
        for i, c in enumerate(cards):
            k = i - (n - 1) / 2
            left = left0 + step * i
            rot = k * (8 / max(n - 1, 1))
            top = base + abs(k) * 4
            cls = "card"
            style = f"transform:rotate({rot:.1f}deg);"
            if i in dim:
                cls += " dim"
            if i in sel:
                cls += " picked"
                top = base - 28
                style = ""
            if i in mark:
                cls += " marked"
                top = base - 24
            if i == hover:
                cls += " hovered"
                top = base - 18
                style = ""
            deck = "king-arthur" if c.startswith("ka:") else "medusa"
            c = c.replace("ka:", "")
            out.append(f'<div class="{cls}" style="left:{left:.0f}px;top:{top:.0f}px;width:{w}px;height:{h}px;{style}'
                       f'background-image:url(\'{MEDIA}/cards/{deck}/{c}.ru.png\')"></div>')
        return "\n".join(out)

    def preview(self, card, deck="medusa"):
        """Hover preview to the side of the hand, never over the field: left column, 270x376 (>= VR-70 225x312)."""
        top = self.H - 24 - self.lay.hero_h - 46 - 16 - 376
        return (f'<div class="abs card big" style="left:40px;top:{top}px;width:270px;height:376px;'
                f'background-image:url(\'{MEDIA}/cards/{deck}/{card}.ru.png\')"></div>')

    def piles(self, deck=23, top_discard="dash", discard=1, bottom=None):
        a = self.lay
        if a.piles_above_cmd:
            r0, b = 28 + a.cmd_w - a.pile_w, (bottom if bottom is not None else 24 + a.disc + 70)
        else:
            r0, b = 28 + a.cmd_w + 24, 24
        r1 = r0 + a.pile_w + 16
        d = f"""<div class="pile" style="right:{r1}px;bottom:{b+12}px;width:{a.pile_w}px;height:{a.pile_h}px">
  <div class="c" style="transform:translate(3px,3px);background-image:url('{MEDIA}/backs/medusa.png');filter:brightness(.55)"></div>
  <div class="c" style="background-image:url('{MEDIA}/backs/medusa.png')"></div>
  <div class="slip">{deck}{'' if a.name == 'S' else '<i>колода</i>'}</div>
</div>"""
        d += f"""<div class="pile" style="right:{r0}px;bottom:{b+12}px;width:{a.pile_w}px;height:{a.pile_h}px">
  <div class="c" style="background-image:url('{MEDIA}/cards/medusa/{top_discard}.ru.png')"></div>
  <div class="slip">{discard}{'' if a.name == 'S' else '<i>сброс</i>'}</div>
</div>"""
        return d

    def question(self, text, bottom=None):
        """The one prompt: in the decision column (Z8), right of FIELD, next to its answer."""
        a = self.lay
        b = bottom if bottom is not None else ((24 + a.disc + 40 + a.pile_h + 50) if a.piles_above_cmd else 212)
        w = 420 if a.name == "L" else 300
        return f'<div class="abs question" style="right:24px;bottom:{b}px;width:{w}px">{text}</div>'

    def action_discs(self):
        a = self.lay
        items = [("maneuver", "Манёвр"), ("attack", "Атака"), ("scheme", "Схема")]
        cells = "".join(f'<div class="act" style="width:{max(a.disc+16, 78)}px">{self.disc_img(k, a.disc)}'
                        f'<div class="ghost" style="font-size:18px">{t}</div></div>' for k, t in items)
        return f'<div class="abs" style="right:20px;bottom:24px;display:flex;gap:2px">{cells}</div>'

    def command(self, primary=None, secondary=None, primary_off=False, timer=None):
        a = self.lay
        off = "opacity:.45;filter:saturate(.3);" if primary_off else ""
        out = ""
        if timer:
            sec, frac = timer
            out += (f'<div class="abs" style="right:28px;bottom:{150 if secondary else 110}px;width:{a.cmd_w}px;display:flex;'
                    f'align-items:center;gap:10px"><div style="flex:1;height:5px;background:rgba(236,227,207,.25);'
                    f'border-radius:3px"><div style="width:{frac*100:.0f}%;height:5px;background:var(--team-p1);'
                    f'border-radius:3px"></div></div><div class="ghost" style="font-size:18px">{sec} с</div></div>')
        if primary:
            out += (f'<div class="abs btn primary" style="right:28px;bottom:{86 if secondary else 30}px;'
                    f'width:{a.cmd_w}px;{off}">{primary}</div>')
        if secondary:
            out += (f'<div class="abs btn secondary" style="right:28px;bottom:{24 if primary else 30}px;'
                    f'width:{a.cmd_w}px">{secondary}</div>')
        return out

    def choice(self, card, deck, title, text, bottom=150):
        """Pending choice panel (MOVE / PLACE / CHOOSE_ONE / TARGET_FIGHTER ...) in Z8 with its source card."""
        return (f'<div class="abs stock choicep" style="right:24px;bottom:{bottom}px;width:430px">'
                f'<div class="mini" style="background-image:url(\'{MEDIA}/cards/{deck}/{card}.ru.png\')"></div>'
                f'<div class="ct"><div class="cn">{title}</div><div class="cx">{text}</div></div><div class="inner"></div></div>')

    def feed(self, lines):
        if not self.lay.feed:
            return '<div class="abs ghost" style="left:24px;top:76px;font-size:18px;opacity:.85">Журнал · J</div>'
        return ('<div class="abs feed" style="left:22px;top:300px;width:440px;white-space:nowrap">'
                '<div class="fh">Журнал · J</div>' + "".join(f"<div>{l}</div>" for l in lines) + "</div>")

    def ring(self, xy, label=None, kind="target"):
        x, y = self.at(xy)
        color = {"target": "var(--choice)", "attacker": "var(--team-p1)", "threat": "var(--team-p2)",
                 "reach": "var(--choice)"}[kind]
        style = "dashed" if kind == "reach" else "solid"
        lab = f'<div class="abs tag" style="left:{x+56}px;top:{y-60}px">{label}</div>' if label else ""
        return (f'<div class="abs" style="left:{x-62}px;top:{y-38}px;width:124px;height:76px;border-radius:50%;'
                f'border:3px {style} {color};box-shadow:0 0 14px {color}"></div>{lab}')

    def board_dial(self, xy, value, team="p2"):
        x, y = self.at(xy)
        return (f'<div class="abs dial small team-{team} hurt" style="left:{x+40}px;top:{y-64}px;width:40px;height:40px">'
                f'<b style="font-size:22px">{value}</b></div>')

    def arc(self, src, dst, ranged=True, color="#a9c6e0"):
        dash = 'stroke-dasharray="14 10"' if ranged else ""
        sx, sy = self.at(src)
        dx, dy = self.at(dst)
        path = f"M{sx},{sy-40} Q{(sx+dx)//2},{min(sy, dy)-240} {dx+40},{dy-30}"
        return (f'<svg class="abs" style="left:0;top:0" width="{self.W}" height="{self.H}">'
                f'<defs><marker id="ah" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto">'
                f'<path d="M0,0 L8,4 L0,8 z" fill="{color}" stroke="#0b0d12" stroke-width=".8"/></marker></defs>'
                f'<path d="{path}" stroke="#0b0d12" stroke-width="10" fill="none" {dash} opacity=".75"/>'
                f'<path d="{path}" stroke="{color}" stroke-width="5" fill="none" {dash} marker-end="url(#ah)"/></svg>')

    def event(self, text, top=160):
        return f'<div class="abs event" style="top:{top}px">{text}</div>'

    def html(self, body, extra_css=""):
        return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8">{FONTS}<link rel="stylesheet" href="_table.css"><style>{extra_css}
html,body{{width:{self.W}px;height:{self.H}px}}</style></head>
<body class="{self.cls}">
<div class="scene" style="background-image:url('{self.board}')"></div>
{body}
</body></html>
"""


COMBAT_CSS = """
.vs { position:absolute; left:50%; top:250px; transform:translateX(-50%); width:900px; height:420px; }
.vs .c { position:absolute; top:0; width:270px; height:376px; border-radius:12px; background-size:cover; box-shadow:0 18px 40px rgba(0,0,0,.7); }
.vs .score { position:absolute; left:50%; top:110px; transform:translateX(-50%); text-align:center; color:#f3ecdc; white-space:nowrap; }
.vs .score .n { font:700 96px "Cormorant SC"; line-height:1; text-shadow:0 4px 18px #000; }
.vs .score .n span { color:var(--team-p1); }
.vs .score .v { margin-top:12px; line-height:1.25; font:700 20px RobotoC; letter-spacing:.06em; text-transform:uppercase; text-shadow:0 2px 8px #000; }
.vs .tag2 { position:absolute; top:388px; font:700 18px RobotoC; letter-spacing:.06em; text-transform:uppercase; color:#efe6d2; text-shadow:0 2px 6px #000; }
.steps { position:absolute; left:50%; top:700px; transform:translateX(-50%); display:flex; gap:10px; }
.steps div { font:700 18px RobotoC; letter-spacing:.05em; text-transform:uppercase; color:#efe6d2; padding:6px 14px; border-radius:18px; background:rgba(10,11,14,.8); box-shadow: inset 0 0 0 1px rgba(236,227,207,.35); white-space:nowrap; }
.steps div.now { background:var(--paper); color:var(--ink); box-shadow:none; }
.steps div.done { opacity:.55; }
.parked { position:absolute; width:170px; height:236px; border-radius:9px; background-size:cover; box-shadow:var(--shadow); }
"""

PAGES, META = {}, {}


def add(name, page, body, css=""):
    PAGES[name] = page.html(body, css)
    META[name] = {"w": page.W, "h": page.H, "scale": page.out[0] / page.W}


def a1_body(p, hover=None):
    return "\n".join([
        p.top_left(), p.opponent(), p.feed(FEED3), p.board_dial(MERLIN, 5),
        p.strip(stage="выбор действия"), p.player(glow=True), p.hand(hover=hover), p.piles(),
        p.question("Действие 1 из 2 — манёвр, атака или схема"), p.action_discs(),
        p.preview("the-hounds-of-mighty-zeus") if hover is not None else "",
    ])


P = Page()
add("A1-table-turn-start", P, a1_body(P))
add("A1b-table-hover-preview", P, a1_body(P, hover=2))

# A2 · attack: Medusa selected, Snipe (3) chosen, candidates ringed; the attack leaves on the target click (SD-56)
add("A2-table-attack-target", P, "\n".join([
    P.top_left(), P.opponent(), P.feed(FEED3),
    '<div class="abs" style="inset:0;background:rgba(5,6,9,.28)"></div>',
    P.ring(MEDUSA, None, "attacker"),
    P.ring(ARTHUR, "Король Артур · 18 · без защиты −3"), P.ring(MERLIN, "Мерлин · 5"),
    P.strip(stage="атака: цель → защита → вскрытие"), P.player(glow=True),
    P.hand(sel=(1,), dim=(0, 2, 3, 4)), P.piles(),
    P.question("Медуза атакует «Метким выстрелом» (3). Щёлкните цель"),
    P.command(secondary="Отмена · Esc"),
]))

# A3 · reveal Snipe 3 vs Regroup 1; the hand stays visible (lowered)
add("A3-table-combat-reveal", P, "\n".join([
    P.top_left("Ход 3 · бой"), P.opponent(hp=16, glow=True),
    '<div class="abs" style="inset:0;background:rgba(5,6,9,.62)"></div>',
    f"""<div class="vs">
  <div class="c" style="left:0;background-image:url('{MEDIA}/cards/medusa/snipe.ru.png')"></div>
  <div class="tag2" style="left:0">Атака · Медуза</div>
  <div class="c" style="right:0;background-image:url('{MEDIA}/cards/king-arthur/regroup.ru.png')"></div>
  <div class="tag2" style="right:0;text-align:right">Защита · Король Артур</div>
  <div class="score"><div class="n"><span>3</span> : 1</div><div class="v">Артур получает<br>2 урона</div></div>
</div>
<div class="steps"><div class="done">Немедленно</div><div class="done">Во время боя</div><div class="now">Урон −2</div><div>После боя: оба берут карту</div></div>""",
    P.strip(filled=("attack",), stage="атака: вскрытие"), P.player(),
    P.hand(cards=["gaze-of-stone", "the-hounds-of-mighty-zeus", "a-momentary-glance", "regroup"], low=True),
    P.piles(),
]), COMBAT_CSS)

# A4 · defense on the opponent's turn: Merlin (ranged) attacks Medusa; only Medusa/Any cards are playable
H4 = ["gaze-of-stone", "the-hounds-of-mighty-zeus", "a-momentary-glance", "regroup", "dash", "second-shot"]
add("A4-table-defense", P, "\n".join([
    P.top_left("Ход 4 · ход соперника"),
    P.opponent(hp=16, glow=True, filled=("maneuver",), hand=4, deck=22, discard=2, status="Мерлин атакует Медузу"),
    P.feed(["<b>Артур</b> — манёвр, +1 карта", "<b>Мерлин</b> → 2 клетки",
            "<b>Мерлин</b> атакует <b>Медузу</b> · дальний бой"]),
    P.arc(MERLIN, MEDUSA, ranged=True), P.ring(MEDUSA, None, "threat"),
    P.event("Мерлин атакует Медузу · дальний бой"),
    P.strip(stage="защита: выберите карту"), P.player(status="движение 3 · дальний бой"),
    P.hand(cards=H4, sel=(4,), dim=(0, 1, 2, 5)), P.piles(deck=21, top_discard="snipe", discard=3),
    P.question("Защититесь картой — или без защиты", bottom=190),
    P.command("Защититься", "Без защиты", timer=(21, .62)),
]))

# B3 · parked combat: Aid the Chosen One 4 vs Dash 3, Medusa 16 -> 15; Dash after combat asks for a cell (MOVE)
add("B3-table-parked-combat-choice", P, "\n".join([
    P.top_left("Ход 4 · ход соперника"),
    P.opponent(hp=16, filled=("maneuver", "attack"), hand=3, deck=22, discard=2, status="ждёт ваш выбор"),
    f'<div class="parked" style="left:40px;top:300px;background-image:url(\'{MEDIA}/cards/medusa/dash.ru.png\');'
    f'box-shadow:0 0 0 3px var(--team-p1),var(--shadow)"></div>'
    f'<div class="abs ghost" style="left:40px;top:546px;font-size:18px">Защита · 3</div>'
    f'<div class="parked" style="right:40px;top:{P.lay.opp_h+80}px;background-image:url(\'{MEDIA}/cards/king-arthur/aid-the-chosen-one.ru.png\')"></div>'
    f'<div class="abs ghost" style="right:40px;top:{P.lay.opp_h+326}px;font-size:18px">Атака · 4</div>',
    P.ring(MEDUSA, "Медуза", "attacker"),
    P.ring((640, 610), None, "reach"), P.ring((560, 380), None, "reach"), P.ring((660, 420), None, "reach"),
    P.event("Бой: 4 : 3 · Медуза получает 1 урон", top=150),
    P.strip(stage="после боя: «Рывок»"), P.player(hp=15),
    P.hand(cards=["gaze-of-stone", "the-hounds-of-mighty-zeus", "a-momentary-glance", "regroup", "second-shot"],
           dim=(0, 1, 2, 3, 4)),
    P.piles(deck=21, top_discard="snipe", discard=3),
    P.choice("dash", "medusa", "Рывок · после боя", "Переместите Медузу на расстояние до 3 клеток. Щёлкните клетку",
             bottom=190),
    P.command("Готово", "Остаться на месте"),
]), COMBAT_CSS)

# B1 · start of Medusa's turn: her optional ability has no legal target -> auto-skip with the reason (no modal)
add("B1-table-ability-skip", P, "\n".join([
    P.top_left("Ход 5"), P.opponent(hp=16, merlin=5, hand=5, deck=21, discard=4), P.feed(FEED3),
    P.event("Ваш ход", top=150),
    '<div class="abs note2" style="left:24px;top:{}px">Способность Медузы пропущена: в её зоне нет бойцов соперника</div>'
    .format(P.H - 24 - P.lay.hero_h - 46 - 64),
    P.strip(stage="выбор действия"), P.player(hp=15, glow=True), P.hand(), P.piles(deck=20, discard=4),
    P.question("Действие 1 из 2 — манёвр, атака или схема"), P.action_discs(),
]))

# B2 · opponent turn: Arthur plays the scheme "Command the Storms"; active-card slot under his card; AI thinking
add("B2-table-opponent-scheme", P, "\n".join([
    P.top_left("Ход 6 · ход соперника"),
    P.opponent(hp=16, glow=True, filled=("scheme",), hand=4, deck=20, discard=4,
               status="Артур думает…", active=("command-the-storms", "Схема · Управляя штормом")),
    P.feed(["<b>Медуза</b> атакует <b>Мерлина</b>: −2", "<b>Медуза</b> — манёвр, +1 карта",
            "<b>Артур</b> играет схему «Управляя штормом»"]),
    P.event("Артур играет схему"),
    P.strip(stage="ход соперника"), P.player(hp=15), P.hand(dim=(0, 1, 2, 3, 4), low=True),
    P.piles(deck=19, discard=5),
]))

# A5 · discard down to 7 at the end of a later turn (9 cards, two marked)
H9 = ["gaze-of-stone", "snipe", "the-hounds-of-mighty-zeus", "a-momentary-glance", "regroup", "dash",
      "second-shot", "clutching-claws", "hiss-and-slither"]
add("A5-table-discard", P, "\n".join([
    P.top_left("Ход 7"), P.opponent(hp=11, merlin=3, hand=6, deck=15, discard=8),
    P.feed(["<b>Медуза</b> — манёвр, +1 карта", "<b>Медуза</b> — манёвр, +1 карта", "Предел руки: 7 карт"]),
    P.strip(filled=("maneuver", "maneuver"), stage="сброс до 7", discard_node="now"),
    P.player(hp=12, harpies=("alive", "dead", "alive")),
    P.hand(cards=H9, mark=(1, 5)), P.piles(deck=14, top_discard="regroup", discard=6),
    P.question("Сбросьте 2 карты: в руке 9, предел 7"),
    P.command("Сбросить (2)"),
]))

# Boards and layout classes
PS = Page(board=SARPEDON)
add("A6-sarpedon-turn-start", PS, a1_body(PS))
P720 = Page(W=1280, H=720, lay=S, out=(1280, 720))        # 1280x720 window: proposed class S at DPI 1.0 (not 0.75)
add("C1-720p-turn-start", P720, a1_body(P720))
P150 = Page(W=1280, H=720, lay=S, out=(1920, 1080))       # 1920x1080 at UI 150 % -> canvas 1280x720 su
add("C2-ui150-turn-start", P150, a1_body(P150))
add("C3-ui150-defense", P150, "\n".join([
    P150.top_left("Ход 4"), P150.opponent(hp=16, glow=True, filled=("maneuver",), hand=4, status="Мерлин атакует"),
    P150.feed([]), P150.arc(MERLIN, MEDUSA, ranged=True), P150.ring(MEDUSA, None, "threat"),
    P150.strip(stage="защита"), P150.player(status="движение 3 · дальний бой"),
    P150.hand(cards=H4, sel=(4,), dim=(0, 1, 2, 5)), P150.piles(deck=21, top_discard="snipe", discard=3, bottom=196),
    P150.question("Защититесь картой — или без защиты", bottom=330),
    P150.command("Защититься", "Без защиты", timer=(21, .62)),
]))

# Materials (CSS fills are placeholders; real samples: art/imagegen/hud-table-materials-codex) and fonts
for name, cls in [("M1-light-stock", "f-cormorant"), ("M2-dark-stock", "m-dark f-cormorant"),
                  ("M3-marble-bronze", "m-bronze f-forum"), ("F0-philosopher", "m-dark"),
                  ("F1-cormorant", "m-dark f-cormorant"), ("F2-forum", "m-dark f-forum")]:
    pg = Page(cls=cls)
    add(name, pg, a1_body(pg))


for name, cls in [("T1-plates-r3-canon", "t-R3 f-cormorant"), ("T2-plates-m2", "t-M2 f-cormorant"),
                  ("T3-plates-m3", "t-M3 f-forum")]:
    pg = Page(cls=cls)
    add(name, pg, a1_body(pg))


def main():
    src = HERE / "src"
    (src / "A5-table-end-turn.html").unlink(missing_ok=True)
    for name, html in PAGES.items():
        (src / f"{name}.html").write_text(html, encoding="utf-8")
    (src / "_meta.json").write_text(json.dumps(META, indent=1), encoding="utf-8")
    print("wrote", len(PAGES), "pages")


if __name__ == "__main__":
    main()
