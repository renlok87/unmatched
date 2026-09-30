"""UE editor Python task (live editor, ue_live.run_task): read-back of a hero's H2LD import after look-dev C (group A).
Read only: nothing is created, changed or saved.

ARGS: {"out", "heroes": [{"hero", "mesh", "base", "skeleton", "folder", "hero_root", "clips_folder",
                          "textures": {key: package}, "instances": {key: package}}]}

Per hero: mesh skeleton (bone 0, bone names and reference-pose positions), LOD count, LOD0 triangles and UV
sets (GeometryScript), material slots and their MI, base UV channels and lightmap-UV build flag; texture settings
(sRGB, compression, filter, mip generation, never-stream, size, LOD group); MI parent / texture / scalar / vector /
static-switch values; package names under the hero root (duplicates, numbered copies); H2Anim clips: skeleton equal to
the mesh skeleton.
"""
import json
import re

import unreal as u

args = ARGS  # noqa: F821 - injected by ue_py/_run.py
MEL = u.MaterialEditingLibrary
EAL = u.EditorAssetLibrary
PE, SP = u.AnimPoseExtensions, u.AnimPoseSpaces
SCALARS = ("TeamDye", "TeamDyeGain", "TeamDyeCeiling", "DebugView", "DebugBakeFromLUT")
VECTORS = ("TeamColor",)
TEX_PARAMS = ("BaseColorTexture", "NormalTexture", "ORMTexture", "TeamMaskTexture", "TeamAccentTexture",
              "MatIDTexture", "MatLUT", "EdgeMaskTexture")
SWITCHES = ("UseTeamAccent", "UseUV1Metres")


def enum_name(v):
    return getattr(v, "name", str(v))


def pkg(obj):
    return obj.get_path_name().split(".")[0] if obj else None


def v3(v):
    return [round(v.x, 4), round(v.y, 4), round(v.z, 4)]


out = {"heroes": {}}
for h in args["heroes"]:
    rec = {}
    mesh = u.load_asset(h["mesh"])
    skel = mesh.get_editor_property("skeleton")
    rec["mesh_skeleton"] = pkg(skel)
    ref = PE.get_reference_pose(skel)
    names = [str(n) for n in PE.get_bone_names(ref)]
    rec["skeleton_bones"] = names
    rec["bone0"] = names[0] if names else None
    try:
        sms = u.get_editor_subsystem(u.SkeletalMeshEditorSubsystem)
        rec["lod_count_subsystem"] = int(sms.get_lod_count(mesh))
    except Exception as exc:  # noqa: BLE001
        rec["lod_count_error"] = str(exc)
    rec["ref_world"] = {n: v3(PE.get_ref_bone_pose(ref, n, SP.WORLD).translation) for n in names}
    lods = []
    try:
        n_lods = int(rec.get("lod_count_subsystem") or 1)
    except Exception:  # noqa: BLE001
        n_lods = 1
    for lod in range(n_lods):
        dm = u.DynamicMesh()
        read = u.GeometryScriptMeshReadLOD()
        read.set_editor_property("lod_index", lod)
        _dm, outcome = u.GeometryScript_AssetUtils.copy_mesh_from_skeletal_mesh(
            mesh, dm, u.GeometryScriptCopyMeshFromAssetOptions(), read)
        item = {"lod": lod, "outcome": str(outcome)}
        if "SUCCESS" in str(outcome):
            item["triangles"] = int(u.GeometryScript_MeshQueries.get_num_triangle_i_ds(dm))
            item["vertices"] = int(u.GeometryScript_MeshQueries.get_vertex_count(dm))
            item["uv_sets"] = int(u.GeometryScript_MeshQueries.get_num_uv_sets(dm))
            box = u.GeometryScript_MeshQueries.get_mesh_bounding_box(dm)
            item["bounds"] = {"min": v3(box.min), "max": v3(box.max)}
        lods.append(item)
    rec["lods"] = lods
    rec["materials"] = [{"slot": str(m.get_editor_property("material_slot_name")),
                         "mi": pkg(m.get_editor_property("material_interface"))}
                        for m in mesh.get_editor_property("materials")]
    sockets = []
    for i in range(mesh.num_sockets()):
        s = mesh.get_socket_by_index(i)
        sockets.append({"name": str(s.get_editor_property("socket_name")), "bone": str(s.get_editor_property("bone_name")),
                        "location": v3(s.get_editor_property("relative_location"))})
    rec["sockets"] = sockets
    base = u.load_asset(h["base"])
    smes = u.get_editor_subsystem(u.StaticMeshEditorSubsystem)
    rec["base"] = {"uv_channels_lod0": int(smes.get_num_uv_channels(base, 0)),
                   "generate_lightmap_uvs": bool(smes.get_lod_build_settings(base, 0).get_editor_property("generate_lightmap_u_vs")),
                   "materials": [pkg(base.get_material(i)) for i in range(base.get_num_sections(0))]}
    # textures
    tex = {}
    for key, path in sorted(h["textures"].items()):
        t = u.load_asset(path)
        if t is None:
            tex[key] = {"asset": path, "missing": True}
            continue
        item = {"asset": path, "class": t.get_class().get_name()}
        for prop in ("srgb", "compression_settings", "filter", "mip_gen_settings", "never_stream", "lod_group"):
            try:
                item[prop] = enum_name(t.get_editor_property(prop))
            except Exception as exc:  # noqa: BLE001
                item[prop] = "n/a (%s)" % type(exc).__name__
        try:
            item["size"] = [int(t.blueprint_get_size_x()), int(t.blueprint_get_size_y())]
        except Exception:  # noqa: BLE001
            pass
        tex[key] = item
    rec["textures"] = tex
    # instances
    inst = {}
    for key, path in sorted(h["instances"].items()):
        mi = u.load_asset(path)
        if mi is None:
            inst[key] = {"asset": path, "missing": True}
            continue
        item = {"asset": path, "parent": pkg(mi.get_editor_property("parent")), "textures": {}, "scalars": {},
                "vectors": {}, "switches": {}}
        for p in TEX_PARAMS:
            try:
                item["textures"][p] = pkg(MEL.get_material_instance_texture_parameter_value(mi, p))
            except Exception:  # noqa: BLE001
                pass
        for p in SCALARS:
            try:
                item["scalars"][p] = round(float(MEL.get_material_instance_scalar_parameter_value(mi, p)), 5)
            except Exception:  # noqa: BLE001
                pass
        for p in VECTORS:
            try:
                c = MEL.get_material_instance_vector_parameter_value(mi, p)
                item["vectors"][p] = [round(c.r, 5), round(c.g, 5), round(c.b, 5), round(c.a, 5)]
            except Exception:  # noqa: BLE001
                pass
        for p in SWITCHES:
            try:
                item["switches"][p] = bool(MEL.get_material_instance_static_switch_parameter_value(mi, p))
            except Exception as exc:  # noqa: BLE001
                item["switches"][p] = "n/a (%s)" % exc
        inst[key] = item
    rec["instances"] = inst
    # packages under the hero root: duplicates / numbered copies
    listed = sorted(str(p).split(".")[0] for p in EAL.list_assets(h["hero_root"], recursive=True, include_folder=False))
    rec["packages_under_hero_root"] = len(listed)
    base_names = {}
    for p in listed:
        base_names.setdefault(p.rsplit("/", 1)[1], []).append(p)
    rec["same_name_in_two_folders"] = {n: ps for n, ps in base_names.items() if len(ps) > 1}
    folder = h["folder"].rstrip("/") + "/"
    rec["numbered_copies_in_folder"] = [p for p in listed if p.startswith(folder) and re.search(r"_\d+$", p)]
    rec["folder_packages"] = [p for p in listed if p.startswith(folder)]
    rec["skeletons_under_hero_root"] = [p for p in listed
                                        if (u.load_asset(p) is not None and u.load_asset(p).get_class().get_name() == "Skeleton")]
    # clips
    clips = []
    for p in sorted(str(x).split(".")[0] for x in EAL.list_assets(h["clips_folder"], recursive=False, include_folder=False)):
        a = u.load_asset(p)
        if a is None or a.get_class().get_name() != "AnimSequence":
            continue
        clips.append({"anim": p, "skeleton": pkg(a.get_editor_property("skeleton")),
                      "same_skeleton_as_mesh": pkg(a.get_editor_property("skeleton")) == rec["mesh_skeleton"],
                      "length_s": round(u.AnimationLibrary.get_sequence_length(a), 5)})
    rec["clips"] = clips
    out["heroes"][h["hero"]] = rec

with open(args["out"], "w", encoding="utf-8", newline="\n") as handle:
    handle.write(json.dumps(out, indent=1, sort_keys=True, default=str) + "\n")
