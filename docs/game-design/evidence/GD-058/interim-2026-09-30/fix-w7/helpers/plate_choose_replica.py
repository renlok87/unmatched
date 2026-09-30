"""Python-реплика S08ArtHud::ChoosePlateRect на реальных трассах хоста (волна 7, fix-w7).

Без флага — поведение до волны 7 (кольцевой поиск + «наименее плохой»): на 6/6 трассах волны 6B даёт ровно тот bbox
плашки, что записал клиент (проверка реплики). С --fix — плюс проход on-owner (плашка на рамке своей фигуры, ближе
всего к «над головой»), как в S08ArtHud.cpp волны 7. Клетки назначения проецируются qa010 (tools/art/qa010).
Только чтение трасс. Запуск из корня репо:
  python docs/game-design/evidence/GD-058/interim-2026-09-30/fix-w7/helpers/plate_choose_replica.py [--fix]
"""
import glob, math, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "tools", "art", "qa010"))
from qa010lib.trace import parse_trace
from qa010lib.projection import build_projection, project_cell
from qa010lib.geometry import clip_polygon_to_rect, polygon_area

ROOT = os.path.join(HERE, "..", "..", "packaged")
BOX = r"\((-?\d+),(-?\d+),(-?\d+),(-?\d+)\)"


def inter(a, b):
    w = min(a[2], b[2]) - max(a[0], b[0]); h = min(a[3], b[3]) - max(a[1], b[1])
    return w * h if w > 0 and h > 0 else 0.0


def gap(a, b):
    dx = max(b[0] - a[2], a[0] - b[2], 0); dy = max(b[1] - a[3], a[1] - b[3], 0)
    return math.hypot(dx, dy)


def grow(r, m):
    return (r[0] - m, r[1] - m, r[2] + m, r[3] + m)


def load(trace):
    text = open(trace, encoding="utf-8", errors="replace").read()
    t = parse_trace(trace)
    shot = t.shots[-1]
    proj = build_projection(shot, 35.0, 2.0, "auto")
    reach = [tuple(c) for c in shot.reachable.value["cells"]]
    quads = [project_cell(proj.camera, shot.board, x, y)["quad"] for x, y in reach]
    figs, panels, plate = {}, [], None
    for line in text.splitlines():
        m = re.search(r"SHOT figure fighter=(\S+) bbox=" + BOX, line)
        if m: figs[m.group(1)] = tuple(int(v) for v in m.groups()[1:])
        m = re.search(r"SHOT panel id=(\S+) bbox=" + BOX, line)
        if m: panels.append((m.group(1), tuple(int(v) for v in m.groups()[1:])))
        m = re.search(r"SHOT plate fighter=(\S+) bbox=" + BOX, line)
        if m: plate = (m.group(1), tuple(int(v) for v in m.groups()[1:]))
    pan = {}
    for k, v in panels: pan[k] = v
    return quads, figs, list(pan.values()), plate, shot.viewport


def choose(owner, quads, figs, panels, vp, W=172, H=54, fix=False):
    anchor = figs[owner]
    soft = list(figs.values()) + panels
    others = [r for k, r in figs.items() if k != owner]
    view = (6, 6, vp[0] - 6, vp[1] - 6)
    qb = [(min(p[0] for p in q), min(p[1] for p in q), max(p[0] for p in q), max(p[1] for p in q)) for q in quads]

    def ev(x0, y0):
        x0, y0 = round(x0), round(y0)
        r = (x0, y0, x0 + W, y0 + H)
        if not (r[0] >= view[0] and r[1] >= view[1] and r[2] <= view[2] and r[3] <= view[3]): return None
        g = grow(r, 4)
        fc, fa = 0, 0.0
        for q, b in zip(quads, qb):
            if inter(b, g) > 0:
                a = polygon_area(clip_polygon_to_rect(q, g))
                if a > 0.5: fc += 1; fa += a
        sa = sum(inter(grow(r, 2), s) for s in soft)
        d = gap(r, anchor)
        bound = all(gap(r, o) > d for o in others)
        return dict(r=r, fc=fc, fa=fa, sa=sa, bound=bound, clean=fc == 0 and sa <= 0 and bound)

    best = None
    def better(t, b):
        if b is None: return True
        if t["fc"] != b["fc"]: return t["fc"] < b["fc"]
        if t["fa"] < b["fa"] - 0.5: return True
        if abs(t["fa"] - b["fa"]) > 0.5: return False
        if t["bound"] and not b["bound"]: return True
        return t["bound"] == b["bound"] and t["sa"] < b["sa"] - 0.5
    ac = ((anchor[0] + anchor[2]) / 2, (anchor[1] + anchor[3]) / 2)
    for ring in range(60):
        G = 6 + ring * 8
        rb, rbd = None, 1e18
        for side in range(4):
            vert = side in (0, 3)
            lo = anchor[0] - W - G if vert else anchor[1] - H - G
            hi = anchor[2] + G if vert else anchor[3] + G
            s = lo
            while s <= hi + 0.01:
                if side == 0: x0, y0 = s, anchor[3] + G
                elif side == 1: x0, y0 = anchor[2] + G, s
                elif side == 2: x0, y0 = anchor[0] - G - W, s
                else: x0, y0 = s, anchor[1] - G - H
                s += 8
                t = ev(x0, y0)
                if not t: continue
                t["cand"] = ("below", "right", "left", "above")[side]; t["ring"] = ring
                if t["clean"]:
                    c = ((t["r"][0] + t["r"][2]) / 2, (t["r"][1] + t["r"][3]) / 2)
                    d = math.dist(c, ac)
                    if d < rbd - 0.5: rb, rbd = t, d
                    continue
                if better(t, best): best = t
        if rb: return rb
    if fix and not (best and best["fc"] == 0 and best["bound"]):
        # on-owner pass: the plate overlaps the owner's own box (gap 0) -> bound whenever it keeps off the others
        onbest = None
        y = anchor[1] - H + 1
        while y <= anchor[3] - 1:
            x = anchor[0] - W + 1
            while x <= anchor[2] - 1:
                t = ev(x, y)
                x += 4
                if not t or t["fc"] or not t["bound"]: continue
                t["cand"] = "on-owner"; t["ring"] = -1
                c = ((t["r"][0] + t["r"][2]) / 2, (t["r"][1] + t["r"][3]) / 2)
                t["own"] = inter(grow(t["r"], 2), anchor)
                t["d"] = math.dist(((t["r"][0] + t["r"][2]) / 2, t["r"][3]), ((anchor[0] + anchor[2]) / 2, anchor[1]))
                key = (round(t["sa"] - t["own"]), t["d"])
                if onbest is None or key < onbest[0]: onbest = (key, t)
            y += 4
        if onbest: return onbest[1]
    return best


if __name__ == "__main__":
    fix = "--fix" in sys.argv
    pats = ["k1/*/run-*/phase2-client-host.trace.log", "k1-probe32/*/run-*/phase2-client-host.trace.log",
            "k2-zoom-*/*/run-*/phase2-client-host.trace.log", "k3/*/run-*/phase2-client-host.trace.log"]
    for p in pats:
        for tr in sorted(glob.glob(os.path.join(ROOT, p))):
            try:
                quads, figs, panels, plate, vp = load(tr)
            except Exception as e:
                print(os.path.relpath(tr, ROOT), "ERR", e); continue
            if not plate: continue
            r = choose(plate[0], quads, figs, panels, vp, fix=fix)
            gaps = {k: round(gap(r["r"], v), 1) for k, v in figs.items()}
            near = min(gaps, key=gaps.get)
            print(os.path.relpath(os.path.dirname(tr), ROOT).replace("\\", "/"), "traced", plate[1], "sim", r["r"],
                  r["cand"], r["ring"], "fc", r["fc"], "bound", r["bound"], "sa", round(r["sa"]),
                  "own", round(r.get("own", 0)), "near", near, gaps[near], "owner", gaps[plate[0]])
