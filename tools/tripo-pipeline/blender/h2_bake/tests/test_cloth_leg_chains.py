"""F11 (2026-10-20 batch, Bruce Lee): optional cloth-rule key leg_chains of st_rig.rule_weights.

Blender (skipped without it, st_rig imports bpy): without the key the cloth rule returns exactly the old four weights;
with it the trouser hem gets the weights of the shoe chain, the shin follows leg_lower, the waist is unchanged;
leg_chains_problems rejects malformed keys. Run: python -m pytest tools/tripo-pipeline/blender/h2_bake/tests -q"""

import json
import os
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO = Path(os.environ.get("H2_BAKE_REPO") or HERE.parents[4])
PKG_PARENT = HERE.parents[1]
BRUCE = REPO / "art/pipeline-candidates/ASSET-BRUCE-LEE-001/build-profiles/bruce-lee-h2-bake-h2-t2.json"
BLENDER = os.environ.get("H2_BAKE_BLENDER", "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe")
CHAINS = {"L": ["leg_upper.L", "leg_lower.L", "foot.L"], "R": ["leg_upper.R", "leg_lower.R", "foot.R"],
          "bands_m": [0.015, 0.012, 0.02]}
BAD = {
    "short": ({"L": ["leg_upper.L", "leg_lower.L"], "R": CHAINS["R"], "bands_m": [0.01] * 3}, "leg_chains.L must list 3"),
    "start": ({"L": ["leg_lower.L", "leg_upper.L", "foot.L"], "R": CHAINS["R"], "bands_m": [0.01] * 3},
              "must start with legs.L"),
    "bone": ({"L": ["leg_upper.L", "shin.L", "foot.L"], "R": CHAINS["R"], "bands_m": [0.01] * 3}, "unknown bone shin.L"),
    "bands": ({"L": CHAINS["L"], "R": CHAINS["R"], "bands_m": [0.01, 0, 0.01]}, "bands_m must be 3 positive"),
    "type": ([1, 2], "leg_chains must be an object"),
}

BLENDER_SCRIPT = r'''
import json, sys
sys.path.insert(0, sys.argv[-4])
from mathutils import Vector
import bpy
from h2_bake import st_rig as R
p = json.load(open(sys.argv[-3], encoding="utf-8"))
chains, bad = json.loads(sys.argv[-2]), json.loads(sys.argv[-1])
arm = R.make_armature(bpy.context.scene, p["rig"])
bones = [b[0] for b in p["rig"]["bones"]]
rule = p["rig"]["weights"]["tripo_part_0"]
shoe = {"L": p["rig"]["weights"]["tripo_part_6"], "R": p["rig"]["weights"]["tripo_part_7"]}
b = arm.data.bones
knee = Vector(b["leg_lower.L"].head_local)
ankle = Vector(b["foot.L"].head_local)
ankle_r = Vector(b["foot.R"].head_local)
pts = {"waist": Vector((0.03, 0.0, 0.33)), "crotch": Vector((0.0, 0.0, 0.27)),
       "thigh": Vector((knee.x, knee.y, knee.z + 0.06)), "knee": knee, "shin": (knee + ankle) / 2,
       "hem": Vector((ankle.x, ankle.y, ankle.z + 0.004)),
       "hem_r": Vector((ankle_r.x, ankle_r.y, ankle_r.z + 0.004))}
out = {"old": {}, "new": {}, "shoe": {}, "problems": {}}
for name, pt in pts.items():
    z0, z1 = rule["top_blend_z"]
    top = R.smoothstep((pt.z - z0) / (z1 - z0))
    legs = rule["leg_max"] * R.smoothstep((rule["leg_start_z"] - pt.z) / (rule["leg_start_z"] - rule["leg_full_z"]))
    side_l = R.smoothstep((pt.x + rule["side_band_m"]) / (2 * rule["side_band_m"]))
    rest = 1.0 - legs
    ref = {rule["top_bone"]: rest * top, rule["base_bone"]: rest * (1.0 - top),
           rule["legs"]["L"]: legs * side_l, rule["legs"]["R"]: legs * (1.0 - side_l)}
    got = R.rule_weights(rule, pt, arm, {})
    out["old"][name] = [list(got.items()) == list(ref.items()), list(got.items())]
    out["new"][name] = R.rule_weights(dict(rule, leg_chains=chains), pt, arm, {})
    out["shoe"][name] = R.rule_weights(shoe["R" if name == "hem_r" else "L"], pt, arm, {})
out["problems"]["none"] = R.leg_chains_problems("p0", rule, bones)
out["problems"]["valid"] = R.leg_chains_problems("p0", dict(rule, leg_chains=chains), bones)
for k, (lc, _m) in bad.items():
    out["problems"][k] = R.leg_chains_problems("p0", dict(rule, leg_chains=lc), bones)
print("RESULT " + json.dumps(out))
'''


@pytest.fixture(scope="module")
def res(tmp_path_factory):
    if not Path(BLENDER).is_file():
        pytest.skip("Blender is missing")
    if not BRUCE.is_file():
        pytest.skip("Bruce Lee t2 profile is missing")
    script = tmp_path_factory.mktemp("lc") / "lc.py"
    script.write_text(BLENDER_SCRIPT, encoding="utf-8")
    r = subprocess.run([BLENDER, "-b", "--factory-startup", "--python", str(script), "--", str(PKG_PARENT), str(BRUCE),
                        json.dumps(CHAINS), json.dumps(BAD)], capture_output=True, text=True, timeout=300)
    line = next((s for s in r.stdout.splitlines() if s.startswith("RESULT ")), None)
    assert line, r.stdout[-2000:] + r.stderr[-2000:]
    return json.loads(line[len("RESULT "):])


def test_without_the_key_the_old_four_weights(res):
    for name, (same, _items) in res["old"].items():
        assert same, name


@pytest.mark.parametrize("point", ["hem", "hem_r"])
def test_hem_matches_the_shoe_chain(res, point):
    new, shoe = res["new"][point], res["shoe"][point]  # hem_r: the right shoe rule (tripo_part_7)
    for bone in set(new) | set(shoe):
        assert abs(new.get(bone, 0.0) - shoe.get(bone, 0.0)) < 1e-9, (bone, new, shoe)


def test_shin_and_knee_follow_the_chain(res):
    assert res["new"]["shin"].get("leg_lower.L", 0.0) > 0.99, res["new"]["shin"]
    assert res["new"]["knee"].get("leg_lower.L", 0.0) > 0.2, res["new"]["knee"]
    assert res["new"]["thigh"].get("leg_upper.L", 0.0) > 0.99, res["new"]["thigh"]


def test_waist_unchanged(res):
    old = dict(res["old"]["waist"][1])
    new = res["new"]["waist"]
    for bone in set(old) | set(new):
        assert abs(old.get(bone, 0.0) - new.get(bone, 0.0)) < 1e-9, (bone, old, new)


def test_weights_sum_to_one(res):
    for name, ws in res["new"].items():
        assert abs(sum(ws.values()) - 1.0) < 1e-9, (name, ws)


def test_problems_none_for_absent_or_valid_key(res):
    assert res["problems"]["none"] == []
    assert res["problems"]["valid"] == []


@pytest.mark.parametrize("case", sorted(BAD))
def test_problems_for_malformed_keys(res, case):
    assert any(BAD[case][1] in s for s in res["problems"][case]), res["problems"][case]
