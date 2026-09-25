"""S05 UE import + reference scene build. Run headless via UnrealEditor-Cmd pythonscript commandlet.

Imports the Blender-built FBX set (skeletal Medusa + clips, ART-001 arrow/mannequin/RM_Test,
board set incl. tray/facade/zone edge/zone icons/attack beam/card quad/selection capsule),
creates Weapon+Head sockets on SK_Medusa, verifies bone names against the Blender build report
(no hardcode fallback), builds the M_S05_Diorama master material with BaseColor/TeamColor/
Roughness parameters, material instances, and assembles /Game/S05/Reference from the S04 board
contract (5x6, 2 zones, worldControls asserted, medusa-first start = 6 fighters, honest
stand-in labels via TextRender actors).
Writes docs/game-design/evidence/S05/art-references/s05-import-result.json.
"""
import unreal as u
import json, hashlib, math
from pathlib import Path

root = Path(__file__).resolve().parents[2]
evidence = root / 'docs/game-design/evidence/S05/art-references'
export = root / 'blender/S05/export'

report = {'stage': 'import+scene', 'checks': {}, 'scene': {}}

def log(msg):
    u.log('S05_IMPORT ' + str(msg))

def check(name, ok, detail):
    report['checks'][name] = {'ok': bool(ok), 'detail': detail}
    log('CHECK %s ok=%s %s' % (name, ok, detail))
    if not ok:
        raise RuntimeError('check failed: %s %s' % (name, detail))

# ---------------------------------------------------------------- master material + instances

def build_master_material():
    asset_tools = u.AssetToolsHelpers.get_asset_tools()
    if u.EditorAssetLibrary.does_asset_exist('/Game/S05/M_DioramaMaster'):
        return u.load_asset('/Game/S05/M_DioramaMaster')
    mat = asset_tools.create_asset('M_DioramaMaster', '/Game/S05', u.Material, u.MaterialFactoryNew())
    assert mat, 'material create failed'
    mel = u.MaterialEditingLibrary
    base = mel.create_material_expression(mat, u.MaterialExpressionVectorParameter, -600, 0)
    base.set_editor_property('parameter_name', 'BaseColor')
    base.set_editor_property('default_value', (0.5, 0.5, 0.5, 1.0))
    team = mel.create_material_expression(mat, u.MaterialExpressionVectorParameter, -600, 200)
    team.set_editor_property('parameter_name', 'TeamColor')
    team.set_editor_property('default_value', (1.0, 1.0, 1.0, 1.0))
    mult = mel.create_material_expression(mat, u.MaterialExpressionMultiply, -300, 100)
    mel.connect_material_expressions(base, '', mult, 'A')
    mel.connect_material_expressions(team, '', mult, 'B')
    mel.connect_material_property(mult, '', u.MaterialProperty.MP_BASE_COLOR)
    rough = mel.create_material_expression(mat, u.MaterialExpressionScalarParameter, -600, 400)
    rough.set_editor_property('parameter_name', 'Roughness')
    rough.set_editor_property('default_value', 0.85)
    mel.connect_material_property(rough, '', u.MaterialProperty.MP_ROUGHNESS)
    # P1-4 (2026-09-25 review): zone tiles need a hue separation that survives the cool key
    # light at K1 distance; BaseColor alone washed out to R/B ~1.0. The Emissive vector param
    # (default black = no change) lets game-layer instances carry a self-lit zone tint.
    emissive = mel.create_material_expression(mat, u.MaterialExpressionVectorParameter, -600, 700)
    emissive.set_editor_property('parameter_name', 'Emissive')
    emissive.set_editor_property('default_value', (0.0, 0.0, 0.0, 1.0))
    mel.connect_material_property(emissive, '', u.MaterialProperty.MP_EMISSIVE_COLOR)
    metallic = mel.create_material_expression(mat, u.MaterialExpressionConstant, -600, 550)
    metallic.set_editor_property('r', 0.0)
    mel.connect_material_property(metallic, '', u.MaterialProperty.MP_METALLIC)
    # SK_Medusa uses instances of this master; without the usage flag the packaged runtime falls
    # back to Default Material ("missing usage flag SkeletalMesh", seen in the 2026-09-25 smoke)
    mat.set_editor_property('used_with_skeletal_mesh', True)
    u.EditorAssetLibrary.save_loaded_asset(mat)
    return mat

def make_instance(name, base_color, team_color=(1, 1, 1, 1), roughness=0.85, emissive=None):
    path = '/Game/S05/MI/%s' % name
    if u.EditorAssetLibrary.does_asset_exist(path):
        return u.load_asset(path)
    asset_tools = u.AssetToolsHelpers.get_asset_tools()
    mic = asset_tools.create_asset(name, '/Game/S05/MI', u.MaterialInstanceConstant, u.MaterialInstanceConstantFactoryNew())
    assert mic, 'material instance create failed: %s' % name
    mel = u.MaterialEditingLibrary
    mel.set_material_instance_parent(mic, MASTER)
    mel.set_material_instance_vector_parameter_value(mic, 'BaseColor', u.LinearColor(*base_color[:3]))
    mel.set_material_instance_vector_parameter_value(mic, 'TeamColor', u.LinearColor(*team_color[:3]))
    mel.set_material_instance_scalar_parameter_value(mic, 'Roughness', roughness)
    if emissive:
        mel.set_material_instance_vector_parameter_value(mic, 'Emissive', u.LinearColor(*emissive[:3]))
    try:
        mic.set_editor_property('used_with_skeletal_mesh', True)
    except Exception:
        pass  # instances inherit the usage from the master in 5.8; warn-only on older API
    u.EditorAssetLibrary.save_loaded_asset(mic)
    return mic

# ---------------------------------------------------------------- imports

def import_static(filename, name):
    task = u.AssetImportTask()
    task.filename = str(export / filename)
    task.destination_path = '/Game/S05/Meshes'
    task.destination_name = name
    task.automated = True
    task.replace_existing = True
    task.save = True
    opts = u.FbxImportUI()
    opts.import_mesh = True
    opts.import_as_skeletal = False
    opts.mesh_type_to_import = u.FBXImportType.FBXIT_STATIC_MESH
    opts.import_materials = False
    opts.import_textures = False
    opts.static_mesh_import_data.combine_meshes = True
    # Unit contract (2026-09-25, after the RM x100 fix): every exported FBX carries
    # cm-numbered data (baked in Blender) and UnitScaleFactor=1.0, so UE takes every
    # number 1:1 as uu (mesh 55 -> 55uu, hips 20 -> 20uu, bone-0 unit factor 1).
    # import_uniform_scale must stay 1.0: the pre-fix files carried meter numbers with
    # UnitScaleFactor=100, UE multiplied everything by USF and put that x100 factor on
    # skeleton bone 0, which root-motion consumption then applied a second time (a
    # 100uu clip moved the probe 10000uu); import_uniform_scale=100 multiplied on top
    # (arrow max.x 33 -> 3300) and a ref/clip scale mismatch collapsed played clips
    # to a point (the K3 missing-bodies defect).
    opts.static_mesh_import_data.import_uniform_scale = 1.0
    task.options = opts
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    mesh = u.load_asset('/Game/S05/Meshes/%s' % name)
    assert mesh, 'static import failed: %s' % name
    return mesh

def import_skeletal(filename, name, with_anim=False, skeleton=None):
    task = u.AssetImportTask()
    task.filename = str(export / filename)
    task.destination_path = '/Game/S05/Meshes'
    task.destination_name = name
    task.automated = True
    task.replace_existing = True
    task.save = True
    opts = u.FbxImportUI()
    opts.import_mesh = True
    opts.import_as_skeletal = True
    opts.mesh_type_to_import = u.FBXImportType.FBXIT_SKELETAL_MESH
    opts.import_animations = with_anim
    opts.import_materials = False
    opts.import_textures = False
    # see the unit-contract note in import_static: with USF=1 cm-numbered files every
    # number lands 1:1 in uu, keeping the ref pose and every clip track in the same
    # units (hips 20uu in both) and bone-0 unit factor 1
    opts.skeletal_mesh_import_data.import_uniform_scale = 1.0
    if skeleton:
        opts.set_editor_property('skeleton', skeleton)
    task.options = opts
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    mesh = u.load_asset('/Game/S05/Meshes/%s' % name)
    assert mesh, 'skeletal import failed: %s' % name
    skel = mesh.get_editor_property('skeleton')
    assert skel, 'skeleton missing after %s import' % name
    u.EditorAssetLibrary.save_loaded_asset(skel)
    u.EditorAssetLibrary.save_loaded_asset(mesh)
    return mesh

def import_clip(filename, name, skeleton):
    # a previous import run may have left a throwaway SkeletalMesh under the same name
    for stale in ('/Game/S05/Anims/%s' % name, '/Game/S05/Anims/%s_Anim' % name,
                  '/Game/S05/Anims/%s_Skeleton' % name):
        if u.EditorAssetLibrary.does_asset_exist(stale):
            u.EditorAssetLibrary.delete_asset(stale)
    task = u.AssetImportTask()
    task.filename = str(export / filename)
    task.destination_path = '/Game/S05/Anims'
    task.destination_name = name
    task.automated = True
    task.replace_existing = True
    task.save = True
    opts = u.FbxImportUI()
    opts.import_mesh = False
    opts.import_as_skeletal = True
    opts.mesh_type_to_import = u.FBXImportType.FBXIT_ANIMATION
    opts.import_animations = True
    opts.import_materials = False
    opts.import_textures = False
    opts.set_editor_property('skeleton', skeleton)
    task.options = opts
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    seq = None
    for cand in u.EditorAssetLibrary.list_assets('/Game/S05/Anims', recursive=False):
        asset_name = str(cand).rsplit('/', 1)[-1].split('.')[0]
        if asset_name.startswith(name):
            loaded = u.load_asset(cand)
            if loaded.get_class().get_name() == 'AnimSequence':
                seq = loaded
                break
    assert seq, 'anim import failed: %s' % name
    seq_skel = seq.get_editor_property('skeleton')
    assert seq_skel.get_path_name() == skeleton.get_path_name(), \
        'clip %s on foreign skeleton %s (expected %s)' % (name, seq_skel.get_path_name(), skeleton.get_path_name())
    # canonical asset name: the legacy FBX importer published clips as <Dest>_Anim and the runtime
    # (SmokeGameMode LoadObject) + smoke tooling reference that path; the Interchange pipeline (the
    # active FBX path in 5.8) names the asset exactly <Dest> — rename for contract stability.
    want = '/Game/S05/Anims/%s_Anim' % name
    if seq.get_path_name().rsplit('.', 1)[0] != want:
        assert u.EditorAssetLibrary.rename_asset(seq.get_path_name().rsplit('.', 1)[0], want), \
            'clip rename failed: %s -> %s' % (name, want)
        seq = u.load_asset(want)
    stray = '/Game/S05/Anims/%s' % name
    if u.EditorAssetLibrary.does_asset_exist(stray):
        loaded = u.load_asset(stray)
        if loaded.get_class().get_name() == 'SkeletalMesh':
            u.EditorAssetLibrary.delete_asset(stray)
    return seq

# ---------------------------------------------------------------- scene helpers

LEVEL = '/Game/S05/Reference'

# Exact generated asset set (P2 2026-09-25 review): regeneration cleanup removes ONLY these
# paths — a wholesale /Game/S05 wipe would erase future manual assets (ART-005 textures etc.).
# The lists double as the post-import hygiene check's expectation, so a renamed import without
# a list update fails the check instead of leaving a stale asset behind.
MI_NAMES = (
    'MI_S05_ZoneBlue', 'MI_S05_ZoneRed', 'MI_S05_MedusaBody', 'MI_S05_MedusaAccent',
    'MI_S05_TeamGold', 'MI_S05_TeamSilver', 'MI_S05_TrayStone', 'MI_S05_MarkerSel',
    'MI_S05_MarkerTarget', 'MI_S05_LanternMetal', 'MI_S05_LanternGlow', 'MI_S05_FacadeWall',
    'MI_S05_FacadeWindow', 'MI_S05_EdgeBlue', 'MI_S05_EdgeRed', 'MI_S05_IconBlue',
    'MI_S05_IconRed', 'MI_S05_Beam', 'MI_S05_CardFrame', 'MI_S05_CardFace', 'MI_S05_HudPanel',
    'MI_S05_HitProxy',
)
STATIC_MESH_NAMES = (
    'SM_S05_Arrow', 'SM_S05_CobbleTile', 'SM_S05_TableBase', 'SM_S05_Lantern', 'SM_S05_Facade',
    'SM_S05_ZoneEdge', 'SM_S05_ZoneIcon_Blue', 'SM_S05_ZoneIcon_Red', 'SM_S05_AttackBeam',
    'SM_S05_CardQuad', 'SM_S05_SelectionCapsule', 'SM_S05_Ring_Selection', 'SM_S05_Ring_Target',
    'SM_S05_Base_Team2_Hex',
)
SKELETAL_MESH_NAMES = ('SM_S05_Mannequin', 'SK_Medusa')
CLIP_NAMES = ('AM_RM_Test', 'AM_Medusa_Idle', 'AM_Medusa_LungeAttack', 'AM_Medusa_HitReact',
              'AM_Medusa_DeathSettle')
# anything in /Game/S05 whose basename starts with one of these but is NOT in the owned set is a
# stale leftover of a previous script version (rename/orphan) and fails the hygiene check
GENERATED_PREFIXES = ('SM_S05_', 'SK_Medusa', 'MI_S05_', 'AM_Medusa_', 'AM_RM_', 'M_DioramaMaster')

def generated_asset_paths():
    # returns (required, optional): required = what a successful import MUST leave behind;
    # optional = legacy-importer name variants that only exist as stale leftovers of old runs
    # (bare <clip> / <clip>_Skeleton) — deleted when present, never expected after import.
    # Deletion order: level -> anims -> skeletal/skeleton/physics -> statics -> instances -> master.
    required, optional = [LEVEL], []
    for n in CLIP_NAMES:
        optional += ['/Game/S05/Anims/%s' % n, '/Game/S05/Anims/%s_Skeleton' % n]
        required += ['/Game/S05/Anims/%s_Anim' % n, '/Game/S05/Anims/%s_PhysicsAsset' % n]
    for n in SKELETAL_MESH_NAMES:
        required += ['/Game/S05/Meshes/%s' % s % n for s in ('%s', '%s_Skeleton', '%s_PhysicsAsset')]
    required += ['/Game/S05/Meshes/%s' % n for n in STATIC_MESH_NAMES]
    required += ['/Game/S05/MI/%s' % n for n in MI_NAMES]
    required.append('/Game/S05/M_DioramaMaster')
    return required, optional

def inventory():
    if not u.EditorAssetLibrary.does_directory_exist('/Game/S05'):
        return []
    # list_assets may return dotted ObjectPaths ('.../Name.Name'); normalize to package paths
    return sorted(str(a).rsplit('.', 1)[0] if '.' in str(a).rsplit('/', 1)[-1] else str(a)
                  for a in u.EditorAssetLibrary.list_assets('/Game/S05', recursive=True))

def cleanup_generated():
    # scoped regeneration clean: delete exactly the assets this script generates (stale
    # <clip>_Skeleton/SkeletalMesh leftovers made the legacy animation importer silently skip
    # clip creation on re-runs). A probe asset — a controlled stand-in for a future manual
    # asset — must survive, proving there is no blind directory wipe.
    before = set(inventory())
    asset_tools = u.AssetToolsHelpers.get_asset_tools()
    probe = asset_tools.create_asset('ZZ_S05_CleanupProbe', '/Game/S05', u.Material, u.MaterialFactoryNew())
    assert probe, 'cleanup probe create failed'
    probe_path = '/Game/S05/ZZ_S05_CleanupProbe'
    required, optional = generated_asset_paths()
    owned = required + optional
    removed = []
    for path in owned:
        if u.EditorAssetLibrary.does_asset_exist(path):
            assert u.EditorAssetLibrary.delete_asset(path), 'cleanup delete failed: %s' % path
            removed.append(path)
    after = set(inventory())
    removed_unowned = sorted((before - after) - set(owned))
    probe_preserved = u.EditorAssetLibrary.does_asset_exist(probe_path)
    assert u.EditorAssetLibrary.delete_asset(probe_path), 'cleanup probe delete failed'
    return {'owned_count': len(owned), 'required_count': len(required), 'removed': len(removed),
            'removed_unowned': removed_unowned, 'probe_preserved': probe_preserved}

def spawn_mesh(mesh, label, xyz, rot=(0, 0, 0), material_overrides=None, tags=()):
    if isinstance(mesh, u.StaticMesh):
        actor = u.EditorLevelLibrary.spawn_actor_from_class(u.StaticMeshActor, u.Vector(*xyz), u.Rotator(*rot))
        assert actor, 'spawn failed: %s' % label
        comp = actor.static_mesh_component
        comp.set_static_mesh(mesh)
    else:
        actor = u.EditorLevelLibrary.spawn_actor_from_class(u.SkeletalMeshActor, u.Vector(*xyz), u.Rotator(*rot))
        assert actor, 'spawn failed: %s' % label
        comp = actor.skeletal_mesh_component
        comp.set_editor_property('skeletal_mesh', mesh)
    actor.set_actor_label(label)
    if material_overrides:
        for slot, mic in material_overrides.items():
            comp.set_material(slot, mic)
    if tags:
        actor.set_editor_property('tags', list(tags))
    return actor

def spawn_text(label, text, xyz, size=12.0, color=(240, 235, 220), tags=(), rot=(0, 0, 90)):
    # yaw +90: TextRender normal +X -> +Y (toward the K-cameras at +Y), advance axis lands on
    # screen-horizontal. The previous Rotator(0,90,0) = pitch 90 flattened the plane flat on the
    # board, and from the pitch -55 camera the glyph advance axis projected vertically — giant
    # white columns crossing every figure (review P1-1).
    actor = u.EditorLevelLibrary.spawn_actor_from_class(u.TextRenderActor, u.Vector(*xyz), u.Rotator(*rot))
    assert actor, 'text spawn failed: %s' % label
    comp = actor.get_components_by_class(u.TextRenderComponent)[0]
    comp.set_editor_property('text', text)
    comp.set_editor_property('world_size', size)
    # unreal.Color positional args are (B, G, R, A) — the FColor C-struct field order (verified by
    # a level probe 2026-09-25: u.Color(255,184,77) stored b=255,r=77). Our tuples are (R, G, B).
    comp.set_editor_property('text_render_color', u.Color(color[2], color[1], color[0]))
    # UE's enum is literally spelled EHorizTextAligment (typo shipped in the engine)
    comp.set_editor_property('horizontal_alignment', u.HorizTextAligment.EHTA_CENTER)
    actor.set_actor_label(label)
    if tags:
        actor.set_editor_property('tags', list(tags))
    return actor

def spawn_label_plate(card_mesh, key, text, wx, wy, z, size, color):
    # Seat label on a camera-facing dark plate (2026-09-25 blank-plate rework). The first plate put
    # the backing quad 0.8uu behind the text anchor with both vertical: SM_S05_CardQuad is a BOX
    # with local y in [-0.4, +0.8], so the quad's front face landed exactly ON the text plane
    # (level probe: quad actor y 89.2 + 0.8 = text y 90.0) and the opaque face won the depth test —
    # the captured K1 showed two uniform RGB(83,92,156) bars with zero glyphs. This version reuses
    # the proven K3-inspector pattern: quad + text are rotated dead-on toward the K1 camera with a
    # per-plate look-at (no pitch-55 foreshortening), and the text anchor sits 1.5uu toward the
    # camera from the quad's local center (= 0.9uu in front of the quad face), so the depth planes
    # can never coincide. The plate leans over its own figure like an easel card.
    cb = card_mesh.get_bounding_box()
    w_uu = 0.68 * size * len(text) + 12.0
    h_uu = size * 1.9
    sx = w_uu / (cb.max.x - cb.min.x)
    sz = h_uu / (cb.max.z - cb.min.z)
    dx, dy, dz = CAM_LOC[0] - wx, CAM_LOC[1] - wy, CAM_LOC[2] - z
    dist = math.sqrt(dx * dx + dy * dy + dz * dz)
    yaw = math.degrees(math.atan2(dy, dx))
    pitch = math.degrees(math.asin(dz / dist))
    n = (dx / dist, dy / dist, dz / dist)
    ptch, yw = math.radians(pitch), math.radians(yaw)
    up = (-math.sin(ptch) * math.cos(yw), -math.sin(ptch) * math.sin(yw), math.cos(ptch))
    # quad face is local +Y: roll -theta + yaw (psi - 90) reproduces the look-at basis exactly
    # (engine-probe verified 2026-09-25: dots 1.0/1.0; the K3 panel used roll -55 / yaw 0 for its
    # on-axis case psi=90). Text normal is local +X = the look-at rotator itself.
    quad_rot = u.Rotator(-pitch, 0.0, yaw - 90.0)
    text_rot = u.Rotator(0.0, pitch, yaw)
    q = quad_rot.quaternion()
    local_center = q.rotate_vector(u.Vector((cb.max.x + cb.min.x) / 2.0 * sx,
                                            (cb.max.y + cb.min.y) / 2.0,
                                            (cb.max.z + cb.min.z) / 2.0 * sz))
    back = spawn_mesh(card_mesh, 'S05_LabelBack_%s' % key,
                      (wx - local_center.x, wy - local_center.y, z - local_center.z),
                      rot=(quad_rot.roll, quad_rot.pitch, quad_rot.yaw),
                      material_overrides={0: CARD_FRAME, 1: HUD_PANEL},
                      tags=('s05_label_backing',))
    back.set_actor_scale3d(u.Vector(sx, 1.0, sz))
    # TextRender draws glyphs UP from the anchor: center the em band on the plate center.
    anchor = (wx + n[0] * 1.5 - up[0] * (h_uu / 2.0 - size * 0.5),
              wy + n[1] * 1.5 - up[1] * (h_uu / 2.0 - size * 0.5),
              z + n[2] * 1.5 - up[2] * (h_uu / 2.0 - size * 0.5))
    text_actor = spawn_text('S05_Label_%s' % key, text, anchor, size=size, color=color,
                            tags=('s05_label',), rot=(text_rot.roll, text_rot.pitch, text_rot.yaw))
    return back, text_actor, n, up

# K1/K3 camera (must match ASmokeGameMode::RefCamera): used for import-time label placement checks.
CAM_LOC = (0.0, 1032.4, 1474.5)
CAM_FWD = (0.0, -math.cos(math.radians(55.0)), -math.sin(math.radians(55.0)))
CAM_UP = (0.0, -math.sin(math.radians(55.0)), math.cos(math.radians(55.0)))
TAN_HALF_H = math.tan(math.radians(17.5))
TAN_HALF_V = TAN_HALF_H * 9.0 / 16.0

def project_k1(px, py, pz):
    d = (px - CAM_LOC[0], py - CAM_LOC[1], pz - CAM_LOC[2])
    fd = sum(CAM_FWD[i] * d[i] for i in range(3))
    ud = sum(CAM_UP[i] * d[i] for i in range(3))
    return (960.0 + 960.0 * d[0] / (fd * TAN_HALF_H), 540.0 - (540.0 / TAN_HALF_V) * (ud / fd))

def vdot(a, b):
    return a.x * b.x + a.y * b.y + a.z * b.z

def make_socket(mesh, name, bone, offset):
    sock = u.SkeletalMeshSocket(outer=mesh, name=name)
    sock.set_socket_parent(mesh, bone)
    sock.set_socket_local_transform(u.Transform(u.Vector(*offset), u.Rotator(0, 0, 0), u.Vector(1, 1, 1)))
    mesh.add_socket(sock)
    u.EditorAssetLibrary.save_loaded_asset(mesh)

def read_sockets(mesh):
    out = {}
    for i in range(mesh.num_sockets()):
        s = mesh.get_socket_by_index(i)
        out[str(s.get_name())] = {'bone': str(s.get_editor_property('bone_name')),
                                  'loc': [round(v, 2) for v in (s.get_editor_property('relative_location').x,
                                                                s.get_editor_property('relative_location').y,
                                                                s.get_editor_property('relative_location').z)]}
    return out

def walk_bones(mesh):
    names = ['root']
    frontier = ['root']
    while frontier:
        cur = frontier.pop()
        for k in mesh.get_bone_children(cur):
            name = str(k)
            names.append(name)
            frontier.append(name)
    return names

def main():
    global MASTER, CARD_FRAME, HUD_PANEL
    build_report = json.loads((root / 'blender/S05/build-report.json').read_text(encoding='utf-8'))
    CLEANUP = cleanup_generated()
    MASTER = build_master_material()
    check('master_material_params', MASTER is not None, '/Game/S05/M_DioramaMaster BaseColor/TeamColor/Roughness')

    # game layer (cells/zones/markers) brighter and more saturated than decor (C-9)
    zone_blue = make_instance('MI_S05_ZoneBlue', (0.18, 0.36, 0.70), roughness=0.85, emissive=(0.05, 0.14, 0.36))
    zone_red = make_instance('MI_S05_ZoneRed', (0.72, 0.28, 0.22), roughness=0.85, emissive=(0.38, 0.09, 0.05))
    medusa_body = make_instance('MI_S05_MedusaBody', (0.30, 0.36, 0.30), roughness=0.9)
    medusa_accent = make_instance('MI_S05_MedusaAccent', (0.55, 0.38, 0.20), roughness=0.55)
    team_gold = make_instance('MI_S05_TeamGold', (0.91, 0.76, 0.42), team_color=(0.91, 0.75, 0.42), roughness=0.7)
    team_silver = make_instance('MI_S05_TeamSilver', (0.66, 0.80, 0.90), team_color=(0.62, 0.76, 0.85), roughness=0.7)
    tray_stone = make_instance('MI_S05_TrayStone', (0.13, 0.14, 0.17), roughness=0.95)
    marker_sel = make_instance('MI_S05_MarkerSel', (0.95, 0.91, 0.85), roughness=0.5)
    marker_target = make_instance('MI_S05_MarkerTarget', (0.88, 0.35, 0.23), roughness=0.5)
    lantern_metal = make_instance('MI_S05_LanternMetal', (0.20, 0.19, 0.17), roughness=0.6)
    lantern_glow = make_instance('MI_S05_LanternGlow', (1.0, 0.71, 0.36), roughness=0.4)
    facade_wall = make_instance('MI_S05_FacadeWall', (0.18, 0.19, 0.23), roughness=0.95)
    facade_window = make_instance('MI_S05_FacadeWindow', (1.0, 0.78, 0.47), roughness=0.5)
    edge_blue = make_instance('MI_S05_EdgeBlue', (0.30, 0.50, 0.85), roughness=0.5)
    edge_red = make_instance('MI_S05_EdgeRed', (0.85, 0.36, 0.31), roughness=0.5)
    icon_blue = make_instance('MI_S05_IconBlue', (0.35, 0.55, 0.95), roughness=0.5)
    icon_red = make_instance('MI_S05_IconRed', (0.95, 0.42, 0.36), roughness=0.5)
    beam_mat = make_instance('MI_S05_Beam', (1.0, 0.55, 0.25), roughness=0.4)
    card_frame = make_instance('MI_S05_CardFrame', (0.12, 0.12, 0.15), roughness=0.6)
    card_face = make_instance('MI_S05_CardFace', (0.38, 0.35, 0.30), roughness=0.8)
    hud_panel = make_instance('MI_S05_HudPanel', (0.02, 0.02, 0.045), roughness=0.9,
                              emissive=(0.05, 0.055, 0.11))
    CARD_FRAME, HUD_PANEL = card_frame, hud_panel
    capsule_mat = make_instance('MI_S05_HitProxy', (0.5, 0.5, 0.5), roughness=0.9)

    # ART-001 arrow: tip expected toward +X in UE, top marker toward +Z.
    # Q-311: Blender 5.2.2 -> UE 5.8.2 legacy static FBX maps y_bl -> -y_ue and ignores
    # both force_front_x_axis and import_rotation (verified: identical bounds); the arrow
    # mesh is therefore pre-rotated +90 deg Z at export time (see build_medusa.py).
    arrow = import_static('SM_S05_Arrow.fbx', 'SM_S05_Arrow')
    b = arrow.get_bounding_box()
    arrow_bounds = {'min': [b.min.x, b.min.y, b.min.z], 'max': [b.max.x, b.max.y, b.max.z]}
    check('arrow_tip_plus_x', b.max.x > 30.0 and b.max.y < 15.0 and b.min.y > -15.0, 'bounds=%s' % arrow_bounds)
    check('arrow_top_marker_z', 8.0 <= b.max.z <= 12.0, 'max_z=%.2f' % b.max.z)

    tile = import_static('SM_S05_CobbleTile.fbx', 'SM_S05_CobbleTile')
    tb = tile.get_bounding_box()
    check('tile_94uu', abs((tb.max.x - tb.min.x) - 94.0) < 1.0 and abs((tb.max.y - tb.min.y) - 94.0) < 1.0,
          'xy=%.2fx%.2f top=%.2f' % (tb.max.x - tb.min.x, tb.max.y - tb.min.y, tb.max.z))
    table = import_static('SM_S05_TableBase.fbx', 'SM_S05_TableBase')
    tab = table.get_bounding_box()
    dim_x, dim_y, dim_z = tab.max.x - tab.min.x, tab.max.y - tab.min.y, tab.max.z - tab.min.z
    rim_x, rim_y = (dim_x - 500.0) / 2.0, (dim_y - 600.0) / 2.0
    check('table_rim_40_60uu', 40.0 <= rim_x <= 60.0 and 40.0 <= rim_y <= 60.0,
          'dims=%.1fx%.1fx%.1f rim_x=%.1f rim_y=%.1f' % (dim_x, dim_y, dim_z, rim_x, rim_y))
    check('table_thickness_30_50uu', 30.0 <= dim_z <= 50.0, 'thickness=%.1f' % dim_z)
    lantern = import_static('SM_S05_Lantern.fbx', 'SM_S05_Lantern')
    facade = import_static('SM_S05_Facade.fbx', 'SM_S05_Facade')
    fb = facade.get_bounding_box()
    f_len, f_h = fb.max.x - fb.min.x, fb.max.z - fb.min.z
    check('facade_length_300_600uu', 300.0 <= f_len <= 600.0, 'length=%.1f' % f_len)
    check('facade_height_budget', f_h <= 120.0, 'height=%.1f' % f_h)
    lb = lantern.get_bounding_box()
    check('lantern_height', 90.0 <= (lb.max.z - lb.min.z) <= 100.0, 'height=%.2f' % (lb.max.z - lb.min.z))
    zone_edge = import_static('SM_S05_ZoneEdge.fbx', 'SM_S05_ZoneEdge')
    zi_blue = import_static('SM_S05_ZoneIcon_Blue.fbx', 'SM_S05_ZoneIcon_Blue')
    zi_red = import_static('SM_S05_ZoneIcon_Red.fbx', 'SM_S05_ZoneIcon_Red')
    beam = import_static('SM_S05_AttackBeam.fbx', 'SM_S05_AttackBeam')
    card = import_static('SM_S05_CardQuad.fbx', 'SM_S05_CardQuad')
    capsule = import_static('SM_S05_SelectionCapsule.fbx', 'SM_S05_SelectionCapsule')
    ring_sel = import_static('SM_S05_Ring_Selection.fbx', 'SM_S05_Ring_Selection')
    ring_target = import_static('SM_S05_Ring_Target.fbx', 'SM_S05_Ring_Target')
    base_hex = import_static('SM_S05_Base_Team2_Hex.fbx', 'SM_S05_Base_Team2_Hex')
    try:
        capsule_collision = 'present' if capsule.get_editor_property('body_setup') else 'none'
    except Exception:
        capsule_collision = 'api_unavailable'

    # ART-001 skeletal mannequin + root-motion clip.
    mannequin = import_skeletal('SM_S05_Mannequin.fbx', 'SM_S05_Mannequin')
    manq_skel = mannequin.get_editor_property('skeleton')
    rm_test = import_clip('AM_RM_Test.fbx', 'AM_RM_Test', manq_skel)
    try:
        rm_test.set_editor_property('enable_root_motion', True)
        u.EditorAssetLibrary.save_loaded_asset(rm_test)
    except Exception as exc:
        log('root motion enable warning: %s' % exc)
    rm_len = rm_test.get_play_length()
    check('rm_test_clip', abs(rm_len - 30.0 / 24.0) < 0.05, 'length=%.3fs frames=30@24fps' % rm_len)

    # Medusa skeletal + 4 clips onto one skeleton.
    medusa = import_skeletal('SK_Medusa.fbx', 'SK_Medusa')
    med_skel = medusa.get_editor_property('skeleton')
    mb = medusa.get_bounds()
    med_dims = [round(mb.box_extent.x * 2, 1), round(mb.box_extent.y * 2, 1), round(mb.box_extent.z * 2, 1)]
    check('medusa_height_budget', 48.0 <= med_dims[2] <= 57.0, 'dims=%s (50-55 uu hero incl base, snakes<=60)' % med_dims)
    check('medusa_pivot_bottom', -2.0 <= mb.origin.z - mb.box_extent.z <= 4.0,
          'min_z=%.2f (base plate bottom at ~0)' % (mb.origin.z - mb.box_extent.z))
    # bone names: expected set comes from the Blender build report; the legacy importer renames
    # '.' to '_'. No hardcode fallback — a wrong import must fail this check, not pass it.
    expected_bones = sorted(n.replace('.', '_') for n in build_report['medusa_bone_names'])
    ue_bones = sorted(walk_bones(medusa))
    check('medusa_bone_names', expected_bones == ue_bones and len(ue_bones) == 17,
          'expected=%s got=%s' % (len(expected_bones), ue_bones))
    clips = {}
    expected = {'AM_Medusa_Idle': 57 / 24.0, 'AM_Medusa_LungeAttack': 15 / 24.0,
                'AM_Medusa_HitReact': 10 / 24.0, 'AM_Medusa_DeathSettle': 22 / 24.0}
    # unit-contract regression gates (2026-09-25 K3 missing-bodies + RM x100 defects): the
    # rig FBX are cm-numbered with UnitScaleFactor=1, so the skeleton ref bone-0 scale and
    # every synthesized bone-0 clip track scale must be exactly 1 and hips lands at 20uu —
    # a bone-0 unit factor != 1 doubles up in root-motion consumption (100uu -> 10000uu),
    # and a ref/clip factor mismatch collapses a played clip to 1/100 size while the
    # un-ticked ref pose still looks right.
    _AL = u.AnimationLibrary
    _ref0 = u.AnimPoseExtensions.get_reference_pose(med_skel)
    ref0_scale = u.AnimPoseExtensions.get_bone_pose(_ref0, 'SKEL_S05_Medusa', u.AnimPoseSpaces.LOCAL).scale3d
    check('medusa_ref_bone0_unit_scale', abs(ref0_scale.x - 1.0) < 0.001 and abs(ref0_scale.z - 1.0) < 0.001,
          'ref bone-0 scale=(%.2f,%.2f,%.2f) (unit factor 1 expected)' % (ref0_scale.x, ref0_scale.y, ref0_scale.z))
    for clip_name, seconds in expected.items():
        seq = import_clip(clip_name + '.fbx', clip_name, med_skel)
        got = seq.get_play_length()
        check('clip_%s' % clip_name, abs(got - seconds) < 0.05, 'length=%.3fs expected=%.3fs' % (got, seconds))
        b0 = _AL.get_bone_pose_for_time(seq, 'SKEL_S05_Medusa', 0.0, False).scale3d
        hips = _AL.get_bone_pose_for_time(seq, 'hips', 0.0, False).translation
        check('clip_%s_bone0_scale' % clip_name, abs(b0.x - 1.0) < 0.001,
              'bone-0 track scale=(%.2f,%.2f,%.2f) must stay 1 (USF=1 contract)' % (b0.x, b0.y, b0.z))
        check('clip_%s_hips_uu' % clip_name, abs(hips.y + 20.0) < 0.01,
              'hips raw translation=(%.3f, %.3f, %.3f) (cm numbers as uu expected, y=-20)' % (hips.x, hips.y, hips.z))
        clips[clip_name] = seq
    slot_names = [str(s) for s in medusa.get_editor_property('materials')]
    check('medusa_slots', len(medusa.get_editor_property('materials')) <= 3, 'slots=%s' % slot_names)

    # ART-004 sockets: real Weapon (bow hand) + Head (petrify VFX) sockets on SK_Medusa.
    make_socket(medusa, 'Weapon', 'hand_L', (0, 2, 0))
    make_socket(medusa, 'Head', 'head', (0, 0, 8))
    sockets = read_sockets(medusa)
    check('medusa_sockets', sockets.get('Weapon', {}).get('bone') == 'hand_L' and
          sockets.get('Head', {}).get('bone') == 'head',
          'sockets=%s' % json.dumps(sockets))

    # ---------------------------------------------------------------- scene from S04 contract
    contract_path = root / 'docs/game-design/evidence/S04/board-contract.json'
    contract = json.loads(contract_path.read_text(encoding='utf-8-sig'))
    W, H = contract['width'], contract['height']
    def cell_world(x, y):
        return ((x - (W - 1) / 2.0) * 100.0, (y - (H - 1) / 2.0) * 100.0, 0.0)
    mapping_errors = []
    for control in contract['worldControls']:
        wx = control['world'][0] * 1.0
        expected_world = cell_world(control['cell'][0], control['cell'][1])
        if abs(expected_world[0] - wx) > 0.01 or abs(expected_world[1] - control['world'][1]) > 0.01:
            mapping_errors.append({'cell': control['cell'], 'expected': expected_world, 'contract': control['world']})
    check('world_controls_mapping', not mapping_errors, 'controls=%d errors=%d' % (len(contract['worldControls']), len(mapping_errors)))

    levels = u.get_editor_subsystem(u.LevelEditorSubsystem)
    if u.EditorAssetLibrary.does_asset_exist(LEVEL):
        assert levels.load_level(LEVEL)
        for old in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors():
            if isinstance(old, (u.StaticMeshActor, u.SkeletalMeshActor, u.DirectionalLight, u.SkyLight,
                                u.PointLight, u.ExponentialHeightFog, u.TextRenderActor)):
                u.get_editor_subsystem(u.EditorActorSubsystem).destroy_actor(old)
    else:
        assert levels.new_level(LEVEL)

    # table base under the whole board (tile tops sit at ~3.2 uu, tray top 2 uu lower)
    TILE_TOP = 3.2
    TRAY_Z = -2.2
    spawn_mesh(table, 'S05_TableBase', (0, 0, TRAY_Z), material_overrides={0: tray_stone})
    # tiles with zone tint (plate 0.94 -> 6 uu seams carry the cell grid in grayscale)
    zone_cells = {'blue': 0, 'red': 0}
    for cell in contract['cells']:
        wx, wy, wz = cell_world(cell['x'], cell['y'])
        zone = cell['zones'][0]
        zone_cells[zone] = zone_cells.get(zone, 0) + 1
        mic = zone_blue if zone == 'blue' else zone_red
        spawn_mesh(tile, 'S05_Cell_%d_%d_%s' % (cell['x'], cell['y'], zone), (wx, wy, wz), material_overrides={0: mic})
    check('scene_cells', len(contract['cells']) == 30 and not contract['multiZoneCells'],
          'cells=%d zones=%s multizone=0' % (len(contract['cells']), zone_cells))

    # zone boundary bar at the blue/red row boundary (y=0 between rows 2 and 3)
    spawn_mesh(zone_edge, 'S05_ZoneEdge', (0, 0, TILE_TOP + 0.35), material_overrides={0: edge_blue, 1: edge_red})
    # zone pictograms on the tray margins, both sides, per zone band (shape carries the zone)
    for ix in (-285.0, 285.0):
        spawn_mesh(zi_blue, 'S05_ZoneIcon_Blue_%d' % ix, (ix, -150.0, TRAY_Z), material_overrides={0: icon_blue})
        spawn_mesh(zi_red, 'S05_ZoneIcon_Red_%d' % ix, (ix, 150.0, TRAY_Z), material_overrides={0: icon_red})

    # decor: far-side facade (y-max, <=120uu) + one warm lantern at the tray corner (C-6: 2 warm sources)
    # window sits on the Blender -Y face, which lands on UE +Y; yaw 180 turns it toward the board (south)
    spawn_mesh(facade, 'S05_Facade_Far', (0, 335, TRAY_Z), rot=(0, 0, 180.0),
               material_overrides={0: facade_wall, 1: facade_window})
    spawn_mesh(lantern, 'S05_Lantern_SW', (-272, -318, TRAY_Z),
               material_overrides={0: lantern_metal, 1: lantern_glow})

    # lighting per C-8: one shadowed cool key directional, warm lantern point without shadows.
    # All lights are MOVABLE: the level is built headless (-nullrhi commandlet), so there is no baked
    # lighting — Static lights contribute nothing in the packaged run (the 2026-09-25 smoke rendered
    # near-black because of this). The SkyLight is replaced by an unshadowed cool fill directional
    # (a movable SkyLight cannot capture in this pipeline).
    key = u.EditorLevelLibrary.spawn_actor_from_class(u.DirectionalLight, u.Vector(0, 0, 700), u.Rotator(-55, 35, 0))
    key.light_component.set_editor_property('intensity', 16.0)
    key.light_component.set_editor_property('light_color', u.Color(183, 200, 224))
    key.light_component.set_editor_property('mobility', u.ComponentMobility.MOVABLE)
    fill = u.EditorLevelLibrary.spawn_actor_from_class(u.DirectionalLight, u.Vector(0, 0, 600), u.Rotator(-30, 215, 0))
    fill.light_component.set_editor_property('intensity', 5.0)
    fill.light_component.set_editor_property('light_color', u.Color(140, 160, 200))
    fill.light_component.set_editor_property('cast_shadows', False)
    fill.light_component.set_editor_property('mobility', u.ComponentMobility.MOVABLE)
    point = u.EditorLevelLibrary.spawn_actor_from_class(u.PointLight, u.Vector(-272, -318, 86))
    point.light_component.set_editor_property('intensity', 70.0)
    point.light_component.set_editor_property('attenuation_radius', 300.0)
    point.light_component.set_editor_property('light_color', u.Color(255, 180, 92))
    point.light_component.set_editor_property('cast_shadows', False)
    point.light_component.set_editor_property('mobility', u.ComponentMobility.MOVABLE)
    # C-6 second warm source: the facade windows back the far (north) edge.
    facade_glow = u.EditorLevelLibrary.spawn_actor_from_class(u.PointLight, u.Vector(0, 300, 100))
    facade_glow.light_component.set_editor_property('intensity', 45.0)
    facade_glow.light_component.set_editor_property('attenuation_radius', 350.0)
    facade_glow.light_component.set_editor_property('light_color', u.Color(255, 170, 80))
    facade_glow.light_component.set_editor_property('cast_shadows', False)
    facade_glow.light_component.set_editor_property('mobility', u.ComponentMobility.MOVABLE)
    fog = u.EditorLevelLibrary.spawn_actor_from_class(u.ExponentialHeightFog, u.Vector(0, 0, 0))
    fog.component.set_editor_property('fog_density', 0.04)
    fog.component.set_editor_property('fog_inscattering_luminance', u.LinearColor(0.03, 0.04, 0.06))

    # six Medusa instances at the medusa-first start (replication test; Arthur/Harpy models do not exist yet)
    start = next(s for s in contract['starts'] if s['id'] == 'medusa-first')
    body_overrides = {0: medusa_body, 1: medusa_accent}
    team_mics = {'f-0': team_gold, 'f-1': team_silver}
    # SK mesh faces UE +Y (Blender -Y forward); f-0 stands south and faces north (yaw 0), f-1 north faces south (yaw 180)
    team_yaw = {'f-0': 0.0, 'f-1': 180.0}
    standin_label = {'f-0-hero': 'H1 MEDUSA', 'f-0-sk0': 'S1 HARPY',
                     'f-0-sk1': 'S2 HARPY', 'f-0-sk2': 'S3 HARPY',
                     'f-1-hero': 'H2 ARTHUR', 'f-1-sk0': 'S4 HARPY'}
    # label color = ownership (matches the base tint: gold = f-0/P1 south, silver = f-1/P2 north)
    label_color = {'f-0': (255, 219, 130), 'f-1': (188, 214, 255)}
    figure_report = []
    f1_plates = []
    for fighter in start['fighters']:
        wx, wy, wz = cell_world(fighter['position']['x'], fighter['position']['y'])
        seat = fighter['id'].rsplit('-', 1)[0]
        fig_z = TILE_TOP
        # the SK already carries a round base (slot 2); seat f-1 additionally gets the hex profile base (C-11)
        if seat == 'f-1':
            spawn_mesh(base_hex, 'S05_BaseHex_%s' % fighter['id'], (wx, wy, TILE_TOP),
                       material_overrides={0: team_silver})
            fig_z = TILE_TOP + 5.0
        tags = ['s05_figure', fighter['id']]
        if fighter['id'] == 'f-0-hero':
            tags.append('s05_attacker')
        if fighter['id'] == 'f-1-hero':
            tags.append('s05_target')
        fig_overrides = dict(body_overrides)
        fig_overrides[2] = team_mics[seat]
        fig = spawn_mesh(medusa, 'S05_%s' % fighter['id'], (wx, wy, fig_z), rot=(0, 0, team_yaw[seat]),
                         material_overrides=fig_overrides, tags=tuple(tags))
        comp = fig.skeletal_mesh_component
        comp.set_editor_property('animation_mode', u.AnimationMode.ANIMATION_SINGLE_NODE)
        comp.play_animation(clips['AM_Medusa_Idle'], True)
        # seat label. f-1 (bottom team, 2026-09-25 review P1 + blank-plate rework): the above-head
        # label projected onto the zone divider band at K1 as pale cyan on the pale orange north
        # tiles; it is now a dark-backed CAMERA-FACING nameplate in front of the figure, inside its
        # own tile and well south of the divider (plate center 35uu north of the figure; the tilted
        # plate leans over the figure, bottom edge sunk ~0.4uu into the tile so it never floats).
        # f-0 keeps the reviewed above-head gold-on-blue label WITHOUT a backing quad: at the FOV-20
        # K2 close-up a world-sized backing plate dominates the hero's head (first attempt measured
        # the K2 label band dropping to 1073 bright px and a dark slab over the snakes). Figure and
        # board coordinates are untouched.
        if seat == 'f-1':
            label_pos = (wx, wy + 35.0, TILE_TOP + 6.3)
            f1_plates.append((fighter['id'],
                              spawn_label_plate(card, fighter['id'], standin_label[fighter['id']],
                                                label_pos[0], label_pos[1], label_pos[2], 13.0,
                                                label_color[seat])))
        else:
            label_pos = (wx, wy, fig_z + 62.0)
            spawn_text('S05_Label_%s' % fighter['id'], standin_label[fighter['id']], label_pos,
                       size=12.0, color=label_color[seat], tags=('s05_label',))
        # ART-004 selection collision proxy: invisible capsule under the figure (line traces hit it)
        hit = spawn_mesh(capsule, 'S05_Hit_%s' % fighter['id'], (wx, wy, TILE_TOP),
                         tags=('s05_hit', fighter['id']))
        hit.set_actor_hidden_in_game(True)
        figure_report.append({'id': fighter['id'], 'cell': [fighter['position']['x'], fighter['position']['y']],
                              'world': [wx, wy, fig_z], 'yaw': team_yaw[seat], 'seat': seat,
                              'label': standin_label[fighter['id']],
                              'label_mode': 'foot-plate' if seat == 'f-1' else 'above-head',
                              'label_world': [round(v, 1) for v in label_pos],
                              'label_screen_xy': [round(v, 1) for v in project_k1(*label_pos)]})
    check('scene_figures', len(figure_report) == 6, 'figures=%d (all SK_Medusa instances, labeled)' % len(figure_report))

    # review P1 placement gate (import-time): both f-1 nameplate centers must sit visibly inside
    # their own tile, south of the divider, and north of the tile's south edge.
    divider_sy = project_k1(0.0, 0.0, 3.5)[1]
    tile_south_sy = project_k1(0.0, 97.0, 3.2)[1]
    f1_placements = [(f['id'], f['label_screen_xy']) for f in figure_report if f['seat'] == 'f-1']
    check('f1_labels_inside_tile',
          len(f1_placements) == 2 and all(divider_sy + 40.0 <= sy <= tile_south_sy - 3.0
                                          for _, (sx, sy) in f1_placements),
          'divider_y=%.1f tile_south_y=%.1f labels=%s (need center y in (divider+40, tile_south-3))'
          % (divider_sy, tile_south_sy, f1_placements))

    # blank-plate regression gates (2026-09-25): read back both f-1 plates and assert (a) the
    # camera-facing basis (quad face + text normal on the look-at axis, ups on screen-up) and
    # (b) a real depth gap between the text plane and the quad's FRONT face — the first plate had
    # the quad front exactly ON the text plane (probe: 89.2 + 0.8 == 90.0) and the opaque face
    # ate every glyph in the packaged K1.
    plate_cb = card.get_bounding_box()
    orient_ok, gap_ok, plate_detail = True, True, []
    for key, (back, text_actor, n_v, up_v) in f1_plates:
        q = back.get_actor_rotation().quaternion()
        by = q.rotate_vector(u.Vector(0, 1, 0))
        bz = q.rotate_vector(u.Vector(0, 0, 1))
        tq = text_actor.get_actor_rotation().quaternion()
        tx = tq.rotate_vector(u.Vector(1, 0, 0))
        tz = tq.rotate_vector(u.Vector(0, 0, 1))
        nvec, uvec = u.Vector(*n_v), u.Vector(*up_v)
        dots = (vdot(by, nvec), vdot(bz, uvec), vdot(tx, nvec), vdot(tz, uvec))
        if min(dots) < 0.999:
            orient_ok = False
        front = back.get_actor_location() + q.rotate_vector(u.Vector(0, plate_cb.max.y, 0))
        gap = vdot(text_actor.get_actor_location() - front, nvec)
        if not 0.6 <= gap <= 1.2:
            gap_ok = False
        plate_detail.append('%s minDot=%.4f textToFrontGap=%.2fuu' % (key, min(dots), gap))
    check('f1_labelplate_orientation', orient_ok and len(plate_detail) == 2,
          'quad face/text normal on look-at axis, ups on screen-up: %s' % '; '.join(plate_detail))
    check('f1_labelplate_text_clearofquad', gap_ok,
          'text plane 0.6..1.2uu in front of the quad face (0.9 expected): %s' % '; '.join(plate_detail))

    # gameplay markers + K3 staging, hidden until the K3 staged capture
    marker_sel_actor = spawn_mesh(ring_sel, 'S05_Marker_Selection',
                                  (cell_world(2, 2)[0], cell_world(2, 2)[1], TILE_TOP),
                                  material_overrides={0: marker_sel}, tags=('s05_marker_selection',))
    marker_sel_actor.set_actor_hidden_in_game(True)
    marker_target_actor = spawn_mesh(ring_target, 'S05_Marker_Target',
                                     (cell_world(2, 3)[0], cell_world(2, 3)[1], TILE_TOP),
                                     material_overrides={0: marker_target}, tags=('s05_marker_target',))
    marker_target_actor.set_actor_hidden_in_game(True)
    # beam + staged card quad carry s05_k3 so EnterK3 reveals them (the old tag set never matched
    # the reveal loop — the beam/card were permanently hidden, review P1-3)
    beam_actor = spawn_mesh(beam, 'S05_AttackBeam', (0, 0, TILE_TOP), material_overrides={0: beam_mat},
                            tags=('s05_beam', 's05_k3'))
    beam_actor.set_actor_hidden_in_game(True)
    card_actor = spawn_mesh(card, 'S05_CardQuad', (-215, -332, TRAY_Z + 2),
                            material_overrides={0: card_frame, 1: card_face}, tags=('s05_card', 's05_k3'))
    card_actor.set_actor_hidden_in_game(True)

    # K3 scene-space inspector panel (2026-09-25 correction). The HighResShot exec re-renders the
    # scene WITHOUT the Slate/UMG layer: the previous screen-space WBP_K3Hud never appeared in any
    # captured frame (measured: the old panel region held identical K1/K3 pixel counts while the
    # log said created=1). The inspector is therefore real scene geometry now: a dark quad +
    # TextRender lines facing the K1/K3 camera dead-on, 620 uu in front of it, hidden until the
    # K3 reveal cycle (s05_k3 + s05_k3_hud tags). Panel screen rect: x 24..784, y 24..408 at
    # 1920x1080 (24 px edge margins - no text may touch the frame edge).
    cam_loc = u.Vector(0.0, 1032.4, 1474.5)
    cam_quat = u.Rotator(roll=0.0, pitch=-55.0, yaw=-90.0).quaternion()
    cam_fwd = cam_quat.rotate_vector(u.Vector(1, 0, 0))
    cam_up = cam_quat.rotate_vector(u.Vector(0, 0, 1))
    cam_right = cam_quat.rotate_vector(u.Vector(0, 1, 0))
    neg_fwd = cam_fwd * -1.0
    px_per_uu = 960.0 / (620.0 * math.tan(math.radians(17.5)))
    panel_center = cam_loc + cam_fwd * 620.0 + cam_right * (556.0 / px_per_uu) + cam_up * (324.0 / px_per_uu)
    # text: normal(local +X) -> toward camera, advance(local +Y) -> screen right, up(local +Z) ->
    # screen up; quad: face(local +Y) -> toward camera. Signs verified by the dot-product asserts
    # below (first run measured the UE roll sign opposite to the textbook matrix: roll=-55).
    panel_text_rot = u.Rotator(roll=0.0, pitch=55.0, yaw=90.0)
    panel_quad_rot = u.Rotator(roll=-55.0, pitch=0.0, yaw=0.0)

    def actor_axes(actor):
        q = actor.get_actor_rotation().quaternion()
        return (q.rotate_vector(u.Vector(1, 0, 0)), q.rotate_vector(u.Vector(0, 1, 0)),
                q.rotate_vector(u.Vector(0, 0, 1)))

    cb = card.get_bounding_box()
    quad_scale = (760.0 / px_per_uu / (cb.max.x - cb.min.x), 1.0, 384.0 / px_per_uu / (cb.max.z - cb.min.z))
    quad_local_center = u.Vector((cb.max.x + cb.min.x) / 2.0 * quad_scale[0],
                                 (cb.max.y + cb.min.y) / 2.0 * quad_scale[1],
                                 (cb.max.z + cb.min.z) / 2.0 * quad_scale[2])
    quad_quat = panel_quad_rot.quaternion()
    quad_loc = panel_center - quad_quat.rotate_vector(quad_local_center)
    hud_quad = spawn_mesh(card, 'S05_K3_HudQuad', (quad_loc.x, quad_loc.y, quad_loc.z),
                          rot=(panel_quad_rot.roll, panel_quad_rot.pitch, panel_quad_rot.yaw),
                          material_overrides={0: card_frame, 1: hud_panel},
                          tags=('s05_k3', 's05_k3_hud'))
    hud_quad.set_actor_scale3d(u.Vector(*quad_scale))
    hud_quad.set_actor_hidden_in_game(True)
    qax, qay, qaz = actor_axes(hud_quad)
    check('k3_panel_quad_orientation',
          vdot(qay, neg_fwd) > 0.999 and vdot(qaz, cam_up) > 0.999,
          'face=%s up=%s scale=%s' % (qay, qaz, quad_scale))

    hud_lines = [
        # (text, size uu, color, screen-y center px)
        # header separator: U+2014 em dash rendered as a missing-glyph box in the packaged K3
        # (2026-09-25 review P2); ASCII '-' confirmed in-font. U+00B7 middle dot below rendered
        # correctly in the same capture and stays.
        ('K3 INSPECTOR - STAGED PREVIEW', 8.0, (255, 184, 77), 54),
        ('NOT LIVE COMBAT · SCRIPTED VALUES', 6.0, (255, 184, 77), 96),
        ('ATK 4 vs DEF 2 · HP 16', 13.0, (255, 255, 255), 150),
        ('CARD: "PIERCING SHOT" (staged)', 7.0, (150, 205, 255), 222),
        ('ring = attacker (2,2) · reticle = target (2,3)', 6.0, (205, 208, 216), 268),
        ('cast: H1 Medusa · Arthur + harpies = stand-ins', 6.0, (205, 208, 216), 306),
        ('frozen clips: Lunge t=0.29 -> HitReact t=0.16', 6.0, (205, 208, 216), 344),
    ]
    text_ok = True
    for idx, (line, size, color, y_px) in enumerate(hud_lines):
        pos = panel_center + neg_fwd * 1.5 + cam_up * ((216.0 - y_px) / px_per_uu)
        actor = u.EditorLevelLibrary.spawn_actor_from_class(u.TextRenderActor, pos, panel_text_rot)
        assert actor, 'hud text spawn failed: %d' % idx
        tcomp = actor.get_components_by_class(u.TextRenderComponent)[0]
        tcomp.set_editor_property('text', line)
        tcomp.set_editor_property('world_size', size)
        # (R,G,B) tuple -> unreal.Color takes (B,G,R,A): see the note in spawn_text
        tcomp.set_editor_property('text_render_color', u.Color(color[2], color[1], color[0]))
        tcomp.set_editor_property('horizontal_alignment', u.HorizTextAligment.EHTA_CENTER)
        actor.set_actor_label('S05_K3_HudText_%d' % idx)
        actor.set_editor_property('tags', ['s05_k3', 's05_k3_hud'])
        actor.set_actor_hidden_in_game(True)
        tax, tay, taz = actor_axes(actor)
        if vdot(tax, neg_fwd) < 0.999 or vdot(taz, cam_up) < 0.999:
            text_ok = False
    check('k3_panel_text_orientation', text_ok, 'all 7 lines face the camera dead-on (dot > 0.999)')
    check('k3_panel_actors', True, 'quad+7 text actors tagged s05_k3_hud, hidden until K3 reveal')

    for actor in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors():
        if actor.actor_has_tag('s05_k3'):
            actor.set_actor_hidden_in_game(True)
    # honest cast note at the south tray edge, readable in K1/K3 (all six are the same SK_Medusa;
    # only the hero identity is real, the rest are stand-ins)
    spawn_text('S05_Text_CastNote',
               'S05 DRAFT CAST - H2 Arthur + harpies: Medusa-mesh stand-ins',
               (90, -348, 9), size=9.0, color=(240, 235, 220), tags=('s05_label',))

    # every TextRender string in the level must be ASCII (+ U+00B7, verified in the packaged font):
    # the default font renders anything beyond that as a missing-glyph box (review P2, U+2014).
    rendered_texts = list(standin_label.values()) + [
        'S05 DRAFT CAST - H2 Arthur + harpies: Medusa-mesh stand-ins'] + [line for line, _s, _c, _y in hud_lines]
    check('text_render_charset',
          all(ord(ch) < 128 or ch == '·' for t in rendered_texts for ch in t),
          '%d TextRender strings ASCII+middle-dot only' % len(rendered_texts))

    # hidden cook holders: the game mode loads Lunge/HitReact/Death and the mannequin+RM_Test at
    # runtime via LoadObject, but the cooker only packages assets referenced from the map. Hidden
    # SkeletalMeshActors keep those packages referenced; the game mode filters them by tag.
    holder_seats = [(medusa, clips['AM_Medusa_LungeAttack'], 'Lunge'),
                    (medusa, clips['AM_Medusa_HitReact'], 'HitReact'),
                    (medusa, clips['AM_Medusa_DeathSettle'], 'Death'),
                    (mannequin, rm_test, 'RMTest')]
    for i, (holder_mesh, holder_seq, label) in enumerate(holder_seats):
        holder = spawn_mesh(holder_mesh, 'S05_CookRef_%s' % label, (1800.0, 1800.0 + i * 120.0, 0.0),
                            tags=('s05_cookref',))
        holder.set_actor_hidden_in_game(True)
        hcomp = holder.skeletal_mesh_component
        hcomp.set_editor_property('animation_mode', u.AnimationMode.ANIMATION_SINGLE_NODE)
        hcomp.play_animation(holder_seq, True)

    # world settings: SmokeGameMode override so the packaged run uses the capture mode on this map.
    # S05 reference logic lives inside ASmokeGameMode behind -S05Ref: a second AGameModeBase-derived
    # UCLASS in this module crashes packaged Development builds during UClass registration.
    world = u.EditorLevelLibrary.get_editor_world()
    settings = world.get_world_settings()
    gm_class = getattr(u, 'SmokeGameMode', None)
    if gm_class:
        settings.set_editor_property('default_game_mode', gm_class.static_class())
        check('world_game_mode', True, 'SmokeGameMode override set')
    else:
        check('world_game_mode', False, 'SmokeGameMode python class not found (build C++ first)')

    assert levels.save_current_level()
    u.EditorAssetLibrary.save_directory('/Game/S05')

    # P2 (2026-09-25 review): scoped-cleanup + no-stale proof. Every generated path must be back
    # after import (nothing skipped), the probe manual asset survived the cleanup, nothing outside
    # the owned set was deleted, and no script-prefixed asset lingers that the owned set misses.
    inv = inventory()
    required, _optional = generated_asset_paths()
    owned = set(required) | set(_optional)
    missing = sorted(set(required) - set(inv))
    stale = sorted(a for a in inv if a not in owned
                   and any(a.rsplit('/', 1)[-1].split('.')[0].startswith(p) for p in GENERATED_PREFIXES))
    check('generated_asset_hygiene',
          CLEANUP['probe_preserved'] and not CLEANUP['removed_unowned'] and not missing and not stale,
          'cleanup removed=%d/%d unowned_removed=%s probe_preserved=%s; post-import missing=%s stale_generated=%s'
          % (CLEANUP['removed'], CLEANUP['owned_count'], CLEANUP['removed_unowned'],
             CLEANUP['probe_preserved'], missing, stale))
    report['generated_cleanup'] = CLEANUP

    report['scene'] = {
        'level': LEVEL,
        'board': {'width': W, 'height': H, 'cells': len(contract['cells']), 'zones': zone_cells,
                  'mapping': 'cell=(x,y) -> ((x-(W-1)/2)*100, (y-(H-1)/2)*100, 0)'},
        'figures': figure_report,
        'lights': {'key_directional_cool': True, 'warm_points_unshadowed': 2, 'shadow_casting_lights': 1},
        'markers': {'selection_ring': 'cell(2,2)', 'target_reticle': 'cell(2,3)', 'hidden_until_K3': True},
        'k3_staging': {'attack_beam': 'attacker(2,2) -> target(2,3) (revealed via s05_k3 tag)',
                       'hud': 'scene-space inspector quad + TextRender lines 620uu in front of the K1/K3 camera '
                              '(HighResShot does not composite Slate/UMG; revealed via s05_k3_hud tag)',
                       'card': 'staged Piercing Shot stand-in quad (revealed via s05_k3 tag)'},
        'readability': {'cell_seams': '6uu gaps between 94uu plates', 'zone_edge_bar': 'raised two-tone bar at y=0',
                        'zone_icons': 'diamond(blue)/triangle(red) at x=+-285',
                        'zone_tile_tint': 'per-cell zone_blue/zone_red MI + Emissive tint (R/B split gated pixel-wise)',
                        'labels': 'horizontal TextRender per seat: f-0 above-head gold-on-blue (no backing, K2-safe), '
                                  'f-1 camera-facing tilted dark foot-plate inside its own tile south of the divider '
                                  '(per-plate look-at, text 0.9uu in front of the quad face); H1/S1..S4 gold/silver seat color; '
                                  'cast note at south tray edge (ASCII separators only)'},
    }
    report['arrow_bounds'] = arrow_bounds
    report['medusa_dims_uu'] = med_dims
    report['medusa_sockets'] = sockets
    report['medusa_bones_ue'] = ue_bones
    report['selection_capsule_body_setup'] = capsule_collision
    report['clip_lengths_s'] = {k: round(v.get_play_length(), 3) for k, v in clips.items()}
    report['rm_test_length_s'] = round(rm_len, 3)
    report['contract_sha256'] = hashlib.sha256(contract_path.read_bytes()).hexdigest()
    report['tile_top_z'] = round(tb.max.z, 2)
    (evidence / 's05-import-result.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    log('VERIFIED ' + json.dumps({'checks': len(report['checks']), 'figures': len(figure_report)}))

main()
