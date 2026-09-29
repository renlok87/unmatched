"""H2.1 review frames: the same cameras for the H2 baseline (harpy-h2-bake/2) and the H2.1 candidate (headless only).

    blender -b --factory-startup --python review_h21.py -- <profile.json> <run_dir> <h2_baseline_run_dir>

Both candidates are rendered from their work/h2-candidate.blend (rest pose, their own textures: the baseline keeps
the flat preview base of candidate_build.base, H2.1 the metal base of base_gold.preview_material). EEVEE, neutral
preview light of review.py (sun 3.0 + 1.3, grey world 0.55, Standard), back faces culled as in UE; every frame is a
Blender frame ("blender" on every sheet), not the game lighting and not an UE frame.

Frames (<run>/work/h21-frames/<who>_<name>.png, who = h2 | h21; JSON record <run>/preview/h21/review-frames-h21.json):
  concept_{front,side,back}   ortho, framed like the H2 concepts (as review_h2.py concept mode), transparent film
  k2_5x_az{000,040,140,180}   game camera (horizontal FOV 35, pitch -55) at 3.86 m = the live-client K2 5x (ART-004:
  k2_1p6x_az{...}             overview 1931 uu, 5x 386 uu, 1.6x 1207 uu) and 12.07 m = 1.6x, figure alone on a 1 m cell,
                              team Gold, instance 3, 1920x1080
  nape_game_az{140,180,220}   ortho 0.2 m close-ups of the nape at the game pitch
  face_game_az000             ortho close-up of the face at the game pitch (what K2 sees, magnified)
  talons_3q, base_band        close-ups of claws / ankle band / base
  team_{gold,silver}_k2_5x    H2.1 only, base team band Gold / Silver at 5x
"""

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import review as RV  # noqa: E402

C.require_background("review_h21.py")
a = C.script_args()
PROFILE_PATH, RUN, BASE_RUN = Path(a[0]).resolve(), Path(a[1]).resolve(), Path(a[2]).resolve()
P = C.load_profile(PROFILE_PATH)
RIG = json.loads((RUN / "reports" / "h2-rig-report.json").read_text(encoding="utf-8"))
OUT = RUN / "work" / "h21-frames"
OUT.mkdir(parents=True, exist_ok=True)
REC = RUN / "preview" / "h21"
REC.mkdir(parents=True, exist_ok=True)
team_lin = {"Gold": (0.807, 0.527, 0.144), "Silver": (0.347, 0.539, 0.686)}
K2 = P["review"].get("k2_live", {}).get("distances_m", {"5x": 3.86, "1.6x": 12.07})
GC = P["review"]["game_camera"]
frames = {}


def load(run_dir):
    bpy.ops.wm.open_mainfile(filepath=str(run_dir / "work" / "h2-candidate.blend"))
    scene = bpy.context.scene
    N_ = P["names"]
    body = bpy.data.objects[N_["body_object"]]
    base = bpy.data.objects[N_["base_object"]]
    arm = next(o for o in scene.objects if o.type == "ARMATURE")
    for o in (body, base):
        mw = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = mw
        for m in list(o.modifiers):
            o.modifiers.remove(m)
    arm.hide_render = True
    for o in list(scene.objects):
        if o.type in ("CAMERA", "LIGHT"):
            bpy.data.objects.remove(o)
    for m in bpy.data.materials:
        m.use_backface_culling = True
    # stage_rig loads the atlas by absolute path: re-point every image under .../textures/ to THIS run's textures
    # (a copied baseline run would otherwise show the current run's atlas on its own UVs)
    rebased = []
    for img in bpy.data.images:
        parts = Path(bpy.path.abspath(img.filepath)).parts if img.filepath else ()
        if "textures" in parts:
            new = run_dir.joinpath(*parts[parts.index("textures"):])
            if new.exists():
                img.filepath = str(new)
                img.reload()
                rebased.append(C.rel(new) if run_dir == RUN else "baseline:" + "/".join(new.parts[-3:]))
    frames.setdefault("_images", {})["baseline" if run_dir != RUN else "run"] = rebased
    cam = RV.setup_scene(scene, samples=64)
    base["um_instance_index"] = 3.0
    base["um_team_color"] = team_lin["Gold"] + (1.0,)
    return scene, cam, body, base


def render_set(who, run_dir):
    scene, cam, body, base = load(run_dir)

    def shoot(name, d, t, **kw):
        rec = RV.shoot(scene, cam, OUT / ("%s_%s.png" % (who, name)), d, t, **kw)
        rec["label"] = "blender"
        frames["%s_%s" % (who, name)] = rec

    span = RIG["measure"]["bounds_body_m"]["max"][0] - RIG["measure"]["bounds_body_m"]["min"][0]
    ortho = span / 0.89
    zc = 0.42 - (0.5 - 0.10) * 1070 * ortho / 1470
    scene.render.film_transparent = True
    for tag, d in (("front", (0, -1, 0)), ("side", (1, 0, 0)), ("back", (0, 1, 0))):
        shoot("concept_%s" % tag, d, (0, 0, zc), ortho=ortho, res=(1470, 1070))
    scene.render.film_transparent = False
    fc = Vector(RIG["measure"]["face_centroid_m"])
    for name, d, t, o_ in (("nape_game_az140", RV.game_dir(140), (0, 0.02, 0.29), 0.2),
                           ("nape_game_az180", RV.game_dir(180), (0, 0.02, 0.29), 0.2),
                           ("nape_game_az220", RV.game_dir(220), (0, 0.02, 0.29), 0.2),
                           ("face_game_az000", RV.game_dir(0), (fc.x, fc.y, fc.z + 0.005), 0.09),
                           ("talons_3q", (0.7, -0.7, 0.3), (0.035, -0.03, 0.085), 0.14),
                           ("base_band", (0.35, -1, 0.35), (0.0, -0.06, 0.04), 0.2)):
        shoot(name, d, t, ortho=o_, res=(1000, 1000))
    cells = RV.ground(scene, [(0.0, 0.0)])
    for zoom, dist in sorted(K2.items()):
        tagz = zoom.replace(".", "p")
        for az in (0, 40, 140, 180):
            shoot("k2_%s_az%03d" % (tagz, az), RV.game_dir(az, GC["pitch_deg"]), (0, 0, 0.12),
                  fov_h=GC["horizontal_fov_deg"], distance=float(dist), res=(1920, 1080))
    if who == "h21":
        for team in ("Gold", "Silver"):
            base["um_team_color"] = team_lin[team] + (1.0,)
            shoot("team_%s_k2_5x" % team.lower(), RV.game_dir(40, GC["pitch_deg"]), (0, 0, 0.12),
                  fov_h=GC["horizontal_fov_deg"], distance=float(K2["5x"]), res=(1920, 1080))
        base["um_team_color"] = team_lin["Gold"] + (1.0,)
    for o in cells:
        bpy.data.objects.remove(o)


def head_pitch_probe(run_dir, degrees=(0.0, 12.0)):
    """Face read at K2 5x with the head bone pitched up (pose only, armature deform kept): a follow-up probe for the
    Idle pose, not a change of the mesh. Positive = chin up (rotation about the bone head, world X)."""
    from mathutils import Matrix
    bpy.ops.wm.open_mainfile(filepath=str(run_dir / "work" / "h2-candidate.blend"))
    scene = bpy.context.scene
    N_ = P["names"]
    base = bpy.data.objects[N_["base_object"]]
    arm = next(o for o in scene.objects if o.type == "ARMATURE")
    arm.hide_render = True
    for o in list(scene.objects):
        if o.type in ("CAMERA", "LIGHT"):
            bpy.data.objects.remove(o)
    for m in bpy.data.materials:
        m.use_backface_culling = True
    cam = RV.setup_scene(scene, samples=64)
    base["um_instance_index"] = 3.0
    base["um_team_color"] = team_lin["Gold"] + (1.0,)
    cells = RV.ground(scene, [(0.0, 0.0)])
    for deg in degrees:
        pb = arm.pose.bones["head"]
        for pbb in arm.pose.bones:
            pbb.matrix_basis = Matrix.Identity(4)
        bpy.context.view_layer.update()
        head = arm.matrix_world @ arm.data.bones["head"].head_local
        rot = Matrix.Translation(head) @ Matrix.Rotation(math.radians(-deg), 4, "X") @ Matrix.Translation(-head)
        pb.matrix = arm.matrix_world.inverted() @ rot @ arm.matrix_world @ pb.matrix
        bpy.context.view_layer.update()
        name = "headpitch%02d_k2_5x_az000" % int(round(deg))
        rec = RV.shoot(scene, cam, OUT / ("h21_%s.png" % name), RV.game_dir(0, GC["pitch_deg"]), (0, 0, 0.12),
                       fov_h=GC["horizontal_fov_deg"], distance=float(K2["5x"]), res=(1920, 1080))
        rec["label"] = "blender, pose probe (head bone pitched %g deg up), not a mesh change" % deg
        frames["h21_" + name] = rec
    for o in cells:
        bpy.data.objects.remove(o)


render_set("h21", RUN)
head_pitch_probe(RUN)
render_set("h2", BASE_RUN)
C.write_json(REC / "review-frames-h21.json", {
    "label": "blender EEVEE preview light, back faces culled; not an UE frame", "baseline_run": "harpy-h2-bake/2 (local copy)",
    "k2_distances_m": K2, "frames": frames})
print(C.STAGE_MARKER, "review_h21", len(frames), flush=True)
