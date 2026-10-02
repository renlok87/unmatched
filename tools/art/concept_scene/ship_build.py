"""ENV-MAPS P9 F1 ship (ASSET-ENV-S-SHIP-001 / SM_Env_S_Ship): the painted red-walled gun deck next to the board,
built at its C0 pixels.

  python -B tools/art/concept_scene/ship_build.py      # -> <work>/SM_Env_S_Ship.pre.npz + reports/ship-build.json

P8 fitted the Poly Haven CC0 dutch_ship_large_01 hull to the painted ship by C0 silhouette IoU with the waterline pinned
at the sea plane: its deck landed at the dock level (-4.7), its near bulwark ~70 uu high and far behind the painted
one, the cannons / rail lantern ended below the dock (z -40 .. -108) - a dark, far mass. The painting has a tall red
hull side right next to the dock: rail cap, gun ports with the three cannons, the deck behind the rail with the main
mast, rigging and a furled sail, and the hull going down into the sea past the island's SE corner.

P9 builds that side procedurally on the painted pixels (no Poly Haven hull: P8's model is no longer exported):
  * the wall plane: a vertical plane through the painted foot line of the red wall on the dock (params footPx, the C0
    rays on Z footZ, least squares); the rail cap's top = the painted rail pixels (railPx) cast onto that plane (the
    heights come out constant within a few uu, ~290 uu: the plane is consistent with the painting);
  * the near hull side: clinker strakes (each strake's lower edge out by clinkUU) from the bilge up to the rail cap,
    with three gun ports cut at the painted cannons (the cannon centre pixel on the plane portOutUU outside the wall
    = the barrel axis point; port box portDepthUU deep, a frame around it), two wales split around the ports;
  * the hull: a loft of one cross-section (near side, bilge quarter-ellipse to the keel, far side, far bulwark, the
    deck deckDropUU under the rail, near bulwark inner face) from the stern transom (north, kept clear of the frame
    band) to the bow (south, beyond the extended canvas; the last bowUU narrow to a stem); rail caps on both bulwarks,
    stanchions on the near rail, a tall post for the rail lantern;
  * the rig: the painted masts (foot = C0 ray on the deck, top on the painted top row, radius from the painted width)
    with rope bands, a yard with a furled sail on the main mast and shrouds from the rails.
Faces are CCW outward (cs_common.Mesh); UVs come from the Smart UV atlas of cs_blender.py 'export'; the albedo is
baked from the plate like every scene mesh (bake_albedo.py). The ports (centre, axis) and the deck plane go to the
build report: scene_layout.py puts the cannons into the ports and the deck props on the deck.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import cs_common as CS  # noqa: E402
import cs_geom as G  # noqa: E402

NAME = "SM_Env_S_Ship"
SLOT = "MI_Env_S_Ship"


# ------------------------------------------------------------------ the painted wall
class Wall:
    """Ship frame from the painted wall: P(s, d, z) = F0 + u s + n_in d + z; d = 0 the outer face of the near hull
    side, d > 0 into the ship; u runs north -> south along the wall."""

    def __init__(self, P: dict):
        cam = CS.cam0()
        F = np.array([CS.ray_z(x, y, P["footZ"]) for x, y in P["footPx"]])
        A = np.c_[F[:, 1], np.ones(len(F))]
        (k, b), *_ = np.linalg.lstsq(A, F[:, 0], rcond=None)
        self.k, self.b = float(k), float(b)
        self.foot_res = [round(float(v), 2) for v in (F[:, 0] - (k * F[:, 1] + b))]
        u = np.array([k, 1.0])
        self.u2 = u / np.linalg.norm(u)
        n_out = np.array([-1.0, k])
        self.out2 = n_out / np.linalg.norm(n_out)  # towards the board (west)
        self.in2 = -self.out2
        self.F0 = np.array([b, 0.0])
        self.cam = cam
        rail = np.array([self.on_plane(x, y, 0.0) for x, y in P["railPx"]])
        s = np.array([self.sdz(p)[0] for p in rail])
        z = rail[:, 2]
        (ra, rb), *_ = np.linalg.lstsq(np.c_[np.ones(len(s)), s], z, rcond=None)
        self.rail_a, self.rail_b = float(ra), float(rb)
        self.rail_pts = rail
        self.rail_res = [round(float(v), 2) for v in z - (ra + rb * s)]

    def P(self, s, d, z):
        s, d, z = np.broadcast_arrays(np.asarray(s, float), np.asarray(d, float), np.asarray(z, float))
        xy = self.F0 + s[..., None] * self.u2 + d[..., None] * self.in2
        return np.concatenate([xy, z[..., None]], -1)

    def sdz(self, p):
        q = np.asarray(p[:2], float) - self.F0
        return float(q @ self.u2), float(q @ self.in2), float(p[2])

    def on_plane(self, px, py, d=0.0):
        """The C0 ray of pixel (px, py) on the plane parallel to the wall at inward distance d."""
        r = self.cam.rays(np.array(float(px)), np.array(float(py)))
        r = r / np.linalg.norm(r)
        n3 = np.r_[self.in2, 0.0]
        p0 = np.r_[self.F0 + self.in2 * d, 0.0]
        t = ((p0 - self.cam.pos) @ n3) / (r @ n3)
        return self.cam.pos + t * r

    def on_z(self, px, py, z):
        return CS.ray_z(px, py, z)

    def rail_z(self, s):
        return self.rail_a + self.rail_b * np.asarray(s, float)

    def yaw_deg(self) -> float:
        return math.degrees(math.atan2(self.u2[1], self.u2[0]))

    def out_yaw_deg(self) -> float:
        return math.degrees(math.atan2(self.out2[1], self.out2[0]))


# ------------------------------------------------------------------ mesh helpers
def orient_out(V, F, centre_fn):
    P = V[F]
    n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    c = P.mean(1)
    bad = np.einsum("ij,ij->i", n, c - centre_fn(c)) < 0
    F = F.copy()
    F[bad] = F[bad][:, ::-1]
    return F


def oriented_box(parts, W: Wall, s0, s1, d0, d1, z0, z1, bevel, tag="hull"):
    """A chamfered box aligned with the wall frame."""
    c = W.P((s0 + s1) / 2, (d0 + d1) / 2, (z0 + z1) / 2)
    V, F = G.chamfer_box(c, (abs(s1 - s0), abs(d1 - d0), abs(z1 - z0)), W.yaw_deg(), bevel)
    parts.add(V, F, tag)


def kit_metrics() -> dict:
    """The P7c concept-paste kit measurements (cannon: length / muzzle / barrel axis; lantern head: height / glow)."""
    import cp_layout as CPL  # tools/art/concept_paste (on the path through cs_common)
    p7 = CPL.load(CPL.BUILD_REPORT)
    can = p7["kitMeasurements"]["SM_Env_Cannon"]
    lant = CPL.export_of(p7, "SM_EnvCP_LanternHead")
    return {"canLen": float(can["boundsUU"]["max"][0]) - float(can["boundsUU"]["min"][0]),
            "muzzleX": float(can["muzzleXUU"]),
            "axis": [0.0, float(can["barrelAxisYUU"]), float(can["barrelAxisZUU"])],
            "headH": float(lant["boundsUeLocalUU"]["size"][2]), "glow": [float(v) for v in lant["glowOffsetUU"]]}


def ports_of(P: dict, W: Wall, D: dict) -> list[dict]:
    """Gun ports at the painted cannons. The kit cannon sits on a carriage; only its last barrelOnlyUU (x scale) are
    bare barrel, so only that part may leave the hull: the painted MUZZLE pixel on the plane `protrusion` outside the
    hull side = the muzzle, the barrel horizontal along the outward normal, the port centre = the muzzle's (s, z) on
    the hull side; the carriage stays inside (port box + hull interior). Scale from the painted size as P8."""
    spec = CS.spec()
    det = {d["id"]: d for d in spec["details"]}
    km = kit_metrics()
    cam = W.cam
    Pp = P["ports"]
    out = []
    for cid in Pp["cannons"]:
        mz = Pp["muzzlePx"][cid]
        M0 = W.on_plane(mz[0], mz[1], 0.0)
        depth = float((M0 - cam.pos) @ cam.fwd)
        sc = min(max(det[cid]["sizePx"][0] * depth / cam.f_px * D["cannonSizeMul"] / km["canLen"], 1.2), 3.0)
        protr = Pp["barrelOnlyUU"] * sc + Pp["muzzleClearUU"]
        M = W.on_plane(mz[0], mz[1], -protr)
        s, d, z = W.sdz(M)
        A = W.P(s, -protr + km["muzzleX"] * sc, z)  # the kit's barrel axis point (x 0)
        out.append({"cannon": cid, "muzzlePx": mz, "muzzle": [round(float(v), 2) for v in M],
                    "axisPoint": [round(float(v), 2) for v in A], "scale": round(sc, 3), "protrusionUU": round(protr, 2),
                    "s": round(s, 2), "z": round(z, 2), "w": Pp["widthUU"], "h": Pp["heightUU"],
                    "centre": [round(float(v), 2) for v in W.P(s, 0.0, z)],
                    "outward": [round(float(v), 4) for v in W.out2], "yawDeg": round(W.out_yaw_deg(), 3)})
    return out


def lantern_rail(P: dict, W: Wall, D: dict) -> dict:
    """The rail lantern hangs from its post's arm: the painted lantern pixel on the plane armUU outside the hull side
    = the glow point; the lantern head (P8 size rule) below the arm; the post stands on the rail cap at that s."""
    spec = CS.spec()
    d = next(x for x in spec["details"] if x["id"] == "lantern-rail")
    km = kit_metrics()
    lp = P["rig"]["lanternPost"]
    G_ = W.on_plane(d["px"][0], d["px"][1], -lp["armUU"])
    depth = float((G_ - W.cam.pos) @ W.cam.fwd)
    sc = d["sizePx"][1] * depth / W.cam.f_px * D["lanternSizeMul"] / km["headH"]
    bottom = G_[2] - km["glow"][2] * sc
    top = bottom + km["headH"] * sc
    s_g = W.sdz(G_)[0]
    return {"glow": [round(float(v), 2) for v in G_], "scale": round(sc, 3), "s": round(s_g, 2),
            "topZ": round(float(top), 1), "armZ": round(float(top) + lp["hookUU"], 1)}


def near_wall(parts, P: dict, W: Wall, s0: float, s1: float, z0: float, z1: float, ports: list[dict]):
    """The near hull side d = 0 (clinker strakes, lower edge clinkUU out) from z0 to z1 with the port openings, the
    port boxes (reveal + back) and frames."""
    H = P["hull"]
    clink = float(H["clinkUU"])
    strake = float(H["strakeUU"])
    holes = [(p["s"] - p["w"] / 2, p["s"] + p["w"] / 2, p["z"] - p["h"] / 2, p["z"] + p["h"] / 2) for p in ports]
    s_nodes = set(np.arange(s0, s1, H["wallStepUU"]).tolist() + [s1])
    z_bands = list(np.arange(z0, z1, strake)) + [z1]
    for a, b, c, d in holes:
        s_nodes.update([a, b])
    s_nodes = np.array(sorted(x for x in s_nodes if s0 <= x <= s1))
    for bi in range(len(z_bands) - 1):
        za, zb = z_bands[bi], z_bands[bi + 1]
        z_nodes = {za, zb}
        for a, b, c, d in holes:
            for zz in (c, d):
                if za < zz < zb:
                    z_nodes.add(zz)
        z_nodes = np.array(sorted(z_nodes))
        off = clink * (zb - z_nodes) / max(zb - za, 1e-6)  # lower edge out
        S, Z = np.meshgrid(s_nodes, z_nodes, indexing="ij")
        D = np.broadcast_to(-off[None, :], S.shape)
        V = W.P(S, D, Z).reshape(-1, 3)
        nz = len(z_nodes)
        F = []
        for i in range(len(s_nodes) - 1):
            for j in range(nz - 1):
                sm, zm = (s_nodes[i] + s_nodes[i + 1]) / 2, (z_nodes[j] + z_nodes[j + 1]) / 2
                if any(a < sm < b and c < zm < d for a, b, c, d in holes):
                    continue
                q = [i * nz + j, (i + 1) * nz + j, (i + 1) * nz + j + 1, i * nz + j + 1]
                F += [[q[0], q[1], q[2]], [q[0], q[2], q[3]]]
        F = np.array(F, np.int64)
        F = orient_out(V, F, lambda c: c - np.r_[W.out2, 0.0][None] * 10.0)
        parts.add(V, F, "wall")
    # port boxes: reveal (4 sides) and back, into the hull; frames around the opening
    depth = float(P["ports"]["depthUU"])
    fr = float(P["ports"]["frameUU"])
    for a, b, c, d in holes:
        cs_, cz = (a + b) / 2, (c + d) / 2
        ring = [(a, c), (b, c), (b, d), (a, d)]
        V, F = [], []
        for i in range(4):
            (sa, za), (sb, zb) = ring[i], ring[(i + 1) % 4]
            base = len(V)
            V += [W.P(sa, 0.0, za), W.P(sb, 0.0, zb), W.P(sb, depth, zb), W.P(sa, depth, za)]
            F += [[base, base + 1, base + 2], [base, base + 2, base + 3]]
        base = len(V)
        V += [W.P(a, depth, c), W.P(b, depth, c), W.P(b, depth, d), W.P(a, depth, d)]
        F += [[base, base + 1, base + 2], [base, base + 2, base + 3]]
        V, F = np.array(V), np.array(F, np.int64)
        centre = W.P(cs_, depth * 0.5, cz)
        # inward-facing (towards the opening's axis and the outside)
        F = orient_out(V, F, lambda q: q + (q - centre[None]) * 2.0)
        parts.add(V, F, "port")
        for (s_a, s_b, z_a, z_b) in ((a - fr, b + fr, d, d + fr), (a - fr, b + fr, c - fr, c), (a - fr, a, c, d),
                                     (b, b + fr, c, d)):
            oriented_box(parts, W, s_a, s_b, -fr * 0.8, 0.5, z_a, z_b, 0.6, "portframe")


def section(P: dict, z_rail: float, f: float = 1.0):
    """The hull cross-section (d, z), closed loop starting at the near outer face top under the rail cap and going
    down the near side: [(d, z)], index of the near outer face's bottom (the straight part has its own wall there)."""
    H = P["hull"]
    B, t = float(H["beamUU"]), float(H["wallThickUU"])
    zc = z_rail - float(H["capHUU"])
    zd = z_rail - float(H["deckDropUU"])
    zb, zk = float(H["bilgeZ"]), float(H["keelZ"])
    n_b = int(H["bilgeSegments"])
    loop = [(0.0, zc), (0.0, zb)]
    for i in range(1, n_b + 1):
        th = math.pi / 2 * i / n_b
        loop.append((B / 2 - B / 2 * math.cos(th), zb - (zb - zk) * math.sin(th)))
    for i in range(1, n_b + 1):
        th = math.pi / 2 + math.pi / 2 * i / n_b
        loop.append((B / 2 - B / 2 * math.cos(th), zb - (zb - zk) * math.sin(th)))
    loop += [(B, zc), (B - t, zc), (B - t, zd), (t, zd), (t, zc)]
    loop = [(B / 2 + (d - B / 2) * f, z) for d, z in loop]
    return loop


def hull(parts, P: dict, W: Wall, s_n: float, s_s: float):
    """Loft of the cross-section from the stern transom to the bow stem; the near outer face of the straight part is
    left out (near_wall builds it with the ports)."""
    H = P["hull"]
    nb = int(H["bowStations"])
    bow = float(H["bowUU"])
    stations = [(s_n, 1.0), (s_s, 1.0)] + [(s_s + bow * i / nb, max(math.cos(math.pi / 2 * i / nb) ** 0.7, H["stemFrac"]))
                                           for i in range(1, nb + 1)]
    secs = []
    for s, f in stations:
        zr = float(W.rail_z(s))
        loop = section(P, zr, f)
        secs.append(W.P(np.full(len(loop), s), np.array([d for d, _ in loop]), np.array([z for _, z in loop])))
    m = len(secs[0])
    V = np.vstack(secs)
    F = []
    for i in range(len(secs) - 1):
        straight = i == 0
        for j in range(m):
            if straight and j == 0:
                continue  # (0, zc) -> (0, zb): the near_wall with the ports
            jn = (j + 1) % m
            a, b, c, d = i * m + j, i * m + jn, (i + 1) * m + jn, (i + 1) * m + j
            F += [[a, b, c], [a, c, d]]
    F = np.array(F, np.int64)
    # orientation: the cross-section loop encloses the hull's solid (below the deck + the bulwarks), so its outward
    # 2D normal is the visible side everywhere (near / far faces, bilge, deck up, bulwark inner faces into the well)
    loop = np.array(section(P, float(W.rail_z(s_n))))
    area = 0.5 * float(np.sum(loop[:, 0] * np.roll(loop[:, 1], -1) - np.roll(loop[:, 0], -1) * loop[:, 1]))
    tang = np.roll(loop, -1, 0) - loop
    out2 = np.c_[tang[:, 1], -tang[:, 0]] * (1.0 if area > 0 else -1.0)  # (d, z) outward of a CCW loop
    seg_j = np.array([j for i in range(len(secs) - 1) for j in range(m) if not (i == 0 and j == 0) for _ in (0, 1)])
    want = np.c_[np.outer(out2[seg_j, 0], W.in2), out2[seg_j, 1]]
    Pv = V[F]
    n = np.cross(Pv[:, 1] - Pv[:, 0], Pv[:, 2] - Pv[:, 0])
    flip = np.einsum("ij,ij->i", n, want) < 0
    F[flip] = F[flip][:, ::-1]
    parts.add(V, F, "hull")
    # end caps: the stern transom (station 0) and the stem (last station)
    for idx, sgn in ((0, -1.0), (len(secs) - 1, 1.0)):
        s, f = stations[idx]
        loop = section(P, float(W.rail_z(s)), f)
        poly = np.array(loop)
        Q, T = CS.triangulate_polygon(poly, 25.0, boundary=poly)
        Vc = W.P(np.full(len(Q), s), Q[:, 0], Q[:, 1])
        Tn = orient_out(Vc, T, lambda q: q - np.r_[W.u2, 0.0][None] * sgn * 10.0)
        parts.add(Vc, Tn, "cap")
    return stations


def rail_and_rig(parts, P: dict, W: Wall, s_n: float, s_s: float, rng):
    H = P["hull"]
    B, t = float(H["beamUU"]), float(H["wallThickUU"])
    capH, over = float(H["capHUU"]), float(H["capOverUU"])
    info = {}
    # rail caps (near / far) as wall-aligned boxes following the rail line (pieces: the rail may slope)
    n_pc = 6
    for d0, d1 in ((-over, t + over), (B - t - over, B + over)):
        for i in range(n_pc):
            a, b = s_n + (s_s - s_n) * i / n_pc, s_n + (s_s - s_n) * (i + 1) / n_pc
            zr = float(W.rail_z((a + b) / 2))
            oriented_box(parts, W, a, b + (0.4 if i < n_pc - 1 else 0.0), d0, d1, zr - capH, zr, 1.2, "rail")
    # wales on the near side, split around the ports
    ports = P["_ports"]
    for wz in H["walesZ"]:
        z0, z1 = (float(W.rail_z((s_n + s_s) / 2)) - capH - 9.0, float(W.rail_z((s_n + s_s) / 2)) - capH) \
            if wz == "rail" else (float(wz) - 4.5, float(wz) + 4.5)
        cuts = [(s_n, s_s)]
        for p in ports:
            if p["z"] - p["h"] / 2 - 2 < z1 and p["z"] + p["h"] / 2 + 2 > z0:
                nc = []
                for a, b in cuts:
                    pa, pb = p["s"] - p["w"] / 2 - 4, p["s"] + p["w"] / 2 + 4
                    if pb <= a or pa >= b:
                        nc.append((a, b))
                    else:
                        if pa > a:
                            nc.append((a, pa))
                        if pb < b:
                            nc.append((pb, b))
                cuts = nc
        for a, b in cuts:
            if b - a > 8:
                oriented_box(parts, W, a, b, -float(H["waleOutUU"]), 1.0, z0, z1, 1.2, "wale")
    # stanchions on the near rail cap
    R = P["rig"]
    s_post = np.arange(s_n + R["postStartUU"], s_s, R["postStepUU"])
    lp = R["lanternPost"]
    lr = P["_lanternRail"]
    s_l = float(lr["s"])
    for s in s_post:
        if abs(s - s_l) < R["postStepUU"] * 0.4:
            continue
        zr = float(W.rail_z(s))
        oriented_box(parts, W, s - R["postUU"] / 2, s + R["postUU"] / 2, t / 2 - R["postUU"] / 2, t / 2 + R["postUU"] / 2,
                     zr - 2.0, zr + R["postHUU"], 0.8, "post")
    zr = float(W.rail_z(s_l))
    za = float(lr["armZ"])
    h_l = za + lp["aboveArmUU"] - zr
    oriented_box(parts, W, s_l - lp["sizeUU"] / 2, s_l + lp["sizeUU"] / 2, t / 2 - lp["sizeUU"] / 2, t / 2 + lp["sizeUU"] / 2,
                 zr - 2.0, zr + h_l, 1.0, "post")
    # the lantern's arm: out of the post over the hull side; the lantern hangs under its tip
    oriented_box(parts, W, s_l - 2.5, s_l + 2.5, -lp["armUU"] - 3.0, t / 2, za - 2.5, za + 2.5, 0.6, "post")
    info["lanternPost"] = {"s": round(s_l, 2), "heightUU": round(h_l, 1),
                           "top": [round(float(v), 1) for v in W.P(s_l, t / 2, zr + h_l)],
                           "armTip": [round(float(v), 1) for v in W.P(s_l, -lp["armUU"], za)]}
    # masts on the deck at their painted pixels
    masts = []
    for m in R["masts"]:
        zd = float(W.rail_z(0.0)) - float(H["deckDropUU"])
        foot = W.on_z(m["footPx"][0], m["footPx"][1], zd)
        s_m, d_m, _ = W.sdz(foot)
        zd = float(W.rail_z(s_m)) - float(H["deckDropUU"])
        foot = W.on_z(m["footPx"][0], m["footPx"][1], zd)
        s_m, d_m, _ = W.sdz(foot)
        # the painted mast is a vertical line in the picture; under C0 (pitch -55) a 3D vertical would fan out from
        # the nadir and leave the painted pixels (75 px at the canvas top): the mast axis runs from the foot to the
        # point of the top pixel's ray nearest to the foot's vertical (it rakes towards the picture's up)
        r_t = W.cam.rays(np.array(float(m["topPx"][0])), np.array(float(m["topPx"][1])))
        r_t = r_t / np.linalg.norm(r_t)
        o = W.cam.pos
        tt = -float((o[:2] - foot[:2]) @ r_t[:2]) / float(r_t[:2] @ r_t[:2])
        topp = o + tt * r_t
        hgt = float(topp[2] - foot[2])
        rake = math.degrees(math.atan2(float(np.linalg.norm(topp[:2] - foot[:2])), hgt))
        r = G.px_radius(foot, m["widthPx"])
        if not (t + r <= d_m <= B - t - r):
            raise SystemExit(f"ship: mast {m['id']} at d {d_m:.1f} is off the deck (t {t} .. B - t {B - t}, r {r:.1f})")
        ax = (topp - foot) / np.linalg.norm(topp - foot)
        base = foot - ax * m.get("sinkUU", 6.0)
        V, F = G.log(base, topp, r, 14, 5, 0.0, rng, taper=0.75, wobble=0.0)
        parts.add(V, F, "mast")
        for fr in m.get("bandsAt", []):
            cb = foot + (topp - foot) * fr
            V, F = G.band(cb[:2], r * (1 - 0.25 * fr) + 1.6, float(cb[2]), 2.2)
            parts.add(V, F, "rope")
        mi = {"id": m["id"], "foot": [round(float(v), 1) for v in foot], "top": [round(float(v), 1) for v in topp],
              "heightUU": round(hgt, 1), "rakeDeg": round(rake, 2), "radiusUU": round(r, 1), "dInUU": round(d_m, 1)}
        y = m.get("yard")
        if y:
            c = foot + (topp - foot) * y["atFrac"]
            zy = float(c[2])
            L = float(y["lengthUU"])
            a, b = c[:2] - W.in2 * L * y["nearFrac"], c[:2] + W.in2 * L * (1 - y["nearFrac"])
            V, F = G.log(np.r_[a, zy], np.r_[b, zy], y["radiusUU"], 10, 3, 0.0, rng, taper=0.7, wobble=0.0)
            parts.add(V, F, "yard")
            # the furled sail: a lumpy roll under the yard
            sa = a + (b - a) * 0.1
            sb = a + (b - a) * 0.9
            V, F = G.log(np.r_[sa, zy - y["sailRadiusUU"] * 0.9], np.r_[sb, zy - y["sailRadiusUU"] * 0.9],
                         y["sailRadiusUU"], 12, 6, 0.0, rng, taper=0.6, wobble=0.18)
            parts.add(V, F, "sail")
            mi["yard"] = {"z": round(zy, 1), "lengthUU": L}
        # shrouds: from both rails (s +- shroudSpreadUU) to the mast at shroudAtFrac
        tip = foot + (topp - foot) * R["shroudAtFrac"]
        for d_r in (t / 2, B - t / 2):
            for ds in (-R["shroudSpreadUU"], R["shroudSpreadUU"]):
                s_r = s_m + ds
                a = W.P(s_r, d_r, float(W.rail_z(s_r)))
                V, F = G.rope(a, tip, 1.5, R["ropeUU"])
                parts.add(V, F, "rope")
        masts.append(mi)
    info["masts"] = masts
    return info


def build(P: dict, frame_band_east: float):
    W = Wall(P)
    rng = np.random.default_rng(P["seed"])
    H = P["hull"]
    # ends: the stern at the painted rail start, kept clear of the frame band's east beam; the straight part to the
    # rail pixel at the extended canvas edge, the bow beyond
    s_rail0 = W.sdz(W.on_plane(*P["railStartPx"]))[0]
    y_clear = (frame_band_east + H["bandClearUU"] - W.b) / W.k  # foot X = band east + clearance
    s_clear = float((np.array([W.k * y_clear + W.b, y_clear]) - W.F0) @ W.u2)
    s_n = max(s_rail0, s_clear)
    s_s = W.sdz(W.on_plane(*P["railEndPx"]))[0]
    D = CS.params()["layout"]["details"]
    ports = ports_of(P, W, D)
    lrail = lantern_rail(P, W, D)
    P = dict(P, _ports=ports, _lanternRail=lrail)
    parts = G.Parts()
    # the near side up to under the rail cap (the higher end; the lower end tucks into the cap box)
    z_top_wall = float(max(W.rail_z(s_n), W.rail_z(s_s))) - float(H["capHUU"])
    if abs(float(W.rail_z(s_n) - W.rail_z(s_s))) > float(H["capHUU"]) * 0.8:
        raise SystemExit("ship: the rail slopes more than the cap height - the wall top would show")
    near_wall(parts, P, W, s_n, s_s, float(H["bilgeZ"]), z_top_wall, ports)
    stations = hull(parts, P, W, s_n, s_s)
    rig = rail_and_rig(parts, P, W, s_n, s_s, rng)
    pivot = np.r_[W.P(0.5 * (s_n + s_s), float(H["beamUU"]) / 2, 0.0)[:2], 0.0]
    pivot = np.round(pivot, 3)
    mesh = parts.mesh(NAME, SLOT, pivot)
    zr = float(W.rail_z((s_n + s_s) / 2))
    info = {"wall": {"footLine": f"X = {W.k:.5f} Y + {W.b:.3f} (Z {P['footZ']})", "footResidualsUU": W.foot_res,
                     "railZ": f"{W.rail_a:.2f} + {W.rail_b:.5f} s", "railResidualsUU": W.rail_res,
                     "along": [round(float(v), 5) for v in W.u2], "outward": [round(float(v), 5) for v in W.out2],
                     "yawDeg": round(W.yaw_deg(), 3), "F0": [round(float(v), 3) for v in W.F0]},
            "sNorth": round(s_n, 2), "sSouth": round(s_s, 2), "bowUU": H["bowUU"],
            "northEnd": [round(float(v), 1) for v in W.P(s_n, 0.0, 0.0)],
            "southEnd": [round(float(v), 1) for v in W.P(s_s, 0.0, 0.0)],
            "railZMid": round(zr, 1), "deckZMid": round(zr - float(H["deckDropUU"]), 1),
            "beamUU": H["beamUU"], "ports": ports, "lanternRail": lrail, "rig": rig, "triangles": mesh.tris}
    return mesh, info, W


# ------------------------------------------------------------------ self-check at C0
def c0_fit(mesh: CS.Mesh, W: Wall, P: dict, out_png: Path | None = None) -> dict:
    """Visible silhouette (depth-tested against the island + frame band) vs the painted ship region inside the C0
    frame (params targetC0Px), the rail / foot line pixel residuals (projected model line vs the painted pixels)."""
    from PIL import Image, ImageDraw
    cam = CS.cam0()
    rect = (0.0, 0.0, 1920.0, 1080.0)
    w, h = 1920, 1080
    d, _ = CS.raster_tris(cam, mesh.board(), mesh.F, w, h, rect=rect, cull_back=True)
    occ = np.full((h, w), np.inf)
    for n in ("SM_Env_S_Island", "SM_Env_S_FrameBand"):
        f = CS.WORK / f"{n}.pre.npz"
        if f.is_file():
            o = CS.Mesh.load(f)
            do, _ = CS.raster_tris(cam, o.board(), o.F, w, h, rect=rect, cull_back=True)
            occ = np.minimum(occ, do)
    m = np.isfinite(d) & (d <= occ + 0.5)  # the visible ship (the hull below the dock is inside the island)
    tgt = CS.poly_mask(P["targetC0Px"], w, h, rect)
    res = {"iouC0": round(float((m & tgt).sum() / max((m | tgt).sum(), 1)), 4),
           "targetCoveredC0": round(float((m & tgt).sum() / max(tgt.sum(), 1)), 4),
           "outsideTargetC0": round(float((m & ~tgt).sum() / max(tgt.sum(), 1)), 4)}

    def px_err(points_px, z_of):
        errs = []
        for x, y in points_px:
            A = W.on_plane(x, y, 0.0)
            s = W.sdz(A)[0]
            q = cam.project(W.P(s, 0.0, z_of(s))[None])[0][0]
            errs.append(float(np.hypot(q[0] - x, q[1] - y)))
        return round(float(np.sqrt(np.mean(np.square(errs)))), 2)
    res["railRmsPx"] = px_err(P["railPx"], lambda s: float(W.rail_z(s)))
    res["footRmsPx"] = px_err(P["footPx"], lambda s: float(P["footZ"]))
    if out_png:
        img = CS.plate_c0(rect, w, h, CS.DELIT_EXT)
        o = img.copy()
        o[m] = o[m] * 0.5 + np.array([1.0, 0.25, 0.2]) * 0.5
        im = Image.fromarray(np.clip(o * 255, 0, 255).astype(np.uint8))
        dr = ImageDraw.Draw(im)
        t = [tuple(p) for p in P["targetC0Px"]]
        dr.line(t + t[:1], fill=(0, 255, 255), width=2)
        for x, y in P["railPx"] + P["footPx"]:
            dr.ellipse((x - 5, y - 5, x + 5, y + 5), outline=(255, 255, 0), width=2)
        im.crop((1250, 0, 1920, 1080)).save(out_png, quality=88)
    return res


def main(argv=None) -> int:
    allp = CS.params()
    P = allp["ship"]
    sys.path.insert(0, str(HERE))
    import frame_band_build as FBB  # noqa: E402
    east = FBB.outer_extents(allp["frameBand"])["eastX"]
    mesh, info, W = build(P, east)
    mesh.save(CS.WORK / f"{NAME}.pre.npz")
    fit = c0_fit(mesh, W, P, CS.WORK / "overlays" / "ship-c0.jpg")
    chk = {"maxTris": P["maxTris"], "trianglesOk": mesh.tris <= P["maxTris"]}
    B = mesh.board()
    rep = {"schema": "unmatched.env-s-ship.build/1",
           "status": "предложено (procedural geometry on the painted C0 pixels, CREATE stage; measured at C0)",
           "mesh": NAME, "pivotBoard": [round(float(v), 3) for v in mesh.pivot], "info": info, "checks": chk,
           "c0Fit": fit, "overlay": (CS.WORK / "overlays" / "ship-c0.jpg").as_posix(),
           "boundsBoard": {"min": [round(float(v), 1) for v in B.min(0)], "max": [round(float(v), 1) for v in B.max(0)]},
           "meshDigest": mesh.digest()}
    CS.dump_json(CS.RUNS["ship"] / "reports" / "ship-build.json", rep)
    print("SHIP", mesh.tris, "tris", json.dumps(fit), "ports", [(p["cannon"], p["z"]) for p in info["ports"]],
          "masts", [(m["id"], m["dInUU"], m["heightUU"]) for m in info["rig"]["masts"]])
    return 0 if chk["trianglesOk"] else 1


if __name__ == "__main__":
    sys.exit(main())
