"""Part roles of a segmented figure (pure Python: no bpy, used by the build and the unit tests).

The build profile names the roles (profile "anatomy"); every role the profile leaves out is detected from the
part geometry, and the detection always runs so the report shows where the profile and the geometry disagree.
Part summaries are measured in the final (candidate) frame, front -Y, .L = +X, z up:
    {part: {"min": [x, y, z], "max": [x, y, z], "centroid": [x, y, z], "polygons": int}}

Detection rules (heuristics, reported as "auto"):
  head         the part with the highest vertex (the figure top part; weapon and base parts excluded)
  face         the head part (Tripo keeps face, hair and headgear in one part on the heroes of 2026-09-28;
               Medusa's open face part is named by the profile)
  feet L / R   per side, among the parts lying on that side of the figure axis (bbox within `side_margin_m`
               of the axis at most), the part with the lowest vertex (ties: the smaller bbox)
  weapon_hand  the smallest body part whose bbox contains the weapon bone head (when there is a weapon)
  neck         a part whose bbox overlaps the lower half of the head and lies inside the head's horizontal
               extent, the smallest such part; none when nothing qualifies
"""

SIDES = {"L": 1.0, "R": -1.0}


def _volume(summary):
    size = [max(summary["max"][i] - summary["min"][i], 0.0) for i in range(3)]
    return size[0] * size[1] * size[2]


def detect_head(summaries):
    if not summaries:
        return None
    return max(sorted(summaries), key=lambda p: summaries[p]["max"][2])


def detect_feet(summaries, side_margin_m=0.01):
    """{"L": part, "R": part} (a side is missing when no part lies on it)."""
    out = {}
    for side, sign in SIDES.items():
        cands = []
        for part in sorted(summaries):
            s = summaries[part]
            inner = s["min"][0] if sign > 0 else -s["max"][0]  # the edge nearest to the axis, positive outward
            if inner >= -side_margin_m and sign * s["centroid"][0] > 0:
                cands.append(part)
        if cands:
            out[side] = min(cands, key=lambda p: (summaries[p]["min"][2], _volume(summaries[p]), p))
    return out


def detect_weapon_hand(summaries, point):
    if point is None:
        return None
    inside = [p for p in sorted(summaries)
              if all(summaries[p]["min"][i] <= point[i] <= summaries[p]["max"][i] for i in range(3))]
    return min(inside, key=lambda p: (_volume(summaries[p]), p)) if inside else None


def detect_neck(summaries, head):
    if head is None or head not in summaries:
        return None
    h = summaries[head]
    mid = (h["min"][2] + h["max"][2]) / 2.0
    cands = []
    for part in sorted(summaries):
        if part == head:
            continue
        s = summaries[part]
        overlaps = s["max"][2] > h["min"][2] and s["min"][2] < mid
        inside = all(h["min"][i] <= s["centroid"][i] <= h["max"][i] for i in (0, 1))
        if overlaps and inside:
            cands.append(part)
    return min(cands, key=lambda p: (_volume(summaries[p]), p)) if cands else None


def detect(summaries, weapon_bone_head=None, side_margin_m=0.01):
    head = detect_head(summaries)
    return {"head": head, "face": head, "feet": detect_feet(summaries, side_margin_m),
            "weapon_hand": detect_weapon_hand(summaries, weapon_bone_head),
            "neck": detect_neck(summaries, head)}


def resolve(profile_anatomy, summaries, top_part=None, weapon_bone_head=None):
    """Roles used by the build: the profile's where given (head defaults to scale.top_part), the detected
    value otherwise. Returns {"used": {...}, "source": {role: "profile"|"auto"}, "auto": {...},
    "disagreements": {role: {"profile": .., "auto": ..}}}."""
    cfg = dict(profile_anatomy or {})
    auto = detect(summaries, weapon_bone_head, cfg.get("side_margin_m", 0.01))
    given = {"head": cfg.get("head") or top_part, "face": cfg.get("face"), "neck": cfg.get("neck"),
             "weapon_hand": cfg.get("weapon_hand"), "feet": cfg.get("feet")}
    used, source, disagree = {}, {}, {}
    for role in ("head", "face", "neck", "weapon_hand", "feet"):
        if given[role]:
            used[role], source[role] = given[role], "profile"
            if auto[role] and auto[role] != given[role]:
                disagree[role] = {"profile": given[role], "auto": auto[role]}
        else:
            value = auto[role] if role != "face" else (used.get("head") or auto["face"])
            used[role], source[role] = value, "auto"
    return {"used": used, "source": source, "auto": auto, "disagreements": disagree}
