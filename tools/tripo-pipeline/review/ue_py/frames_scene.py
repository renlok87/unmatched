"""UE editor Python task (LIVE editor via review/ue_live.py run_task): temporary review actors for editor frames.

ARGS: {"out": ..., "op": "setup" | "pose" | "sockets" | "camera" | "cleanup", ...}
  setup:   {"actors": [{"label", "kind": "static"|"skeletal"|"camera", "asset", "location", "yaw", "fov"}]}
  pose:    {"label", "anim", "time"}          respawns the skeletal actor with a single-node animation at `time`
  sockets: {"label"}                          read back position and Weapon/Head sockets (actor space)
  camera:  {"label", "location", "rotation"}  moves the camera actor and pilots the level viewport with it
  cleanup: {"labels": [...]}                  ejects the pilot and destroys the listed actors
Nothing is saved; the caller reloads the previous level afterwards (the review level stays unsaved).
"""
import json

import unreal as u

args = ARGS  # noqa: F821 - injected by ue_py/_run.py
actors_sub = u.get_editor_subsystem(u.EditorActorSubsystem)
level_sub = u.get_editor_subsystem(u.LevelEditorSubsystem)


def find(label):
    hits = [a for a in actors_sub.get_all_level_actors() if a.get_actor_label() == label]
    if len(hits) != 1:
        raise RuntimeError("actor %r: %d matches" % (label, len(hits)))
    return hits[0]


def vec(v):
    return u.Vector(float(v[0]), float(v[1]), float(v[2]))


out = {"op": args["op"]}
if args["op"] == "setup":
    out["actors"] = {}
    for spec in args["actors"]:
        rot = u.Rotator(0.0, float(spec.get("yaw", 0.0)), 0.0)
        if spec["kind"] == "static":
            a = actors_sub.spawn_actor_from_class(u.StaticMeshActor, vec(spec["location"]), rot)
            a.static_mesh_component.set_static_mesh(u.load_asset(spec["asset"]))
        elif spec["kind"] == "skeletal":
            a = actors_sub.spawn_actor_from_class(u.SkeletalMeshActor, vec(spec["location"]), rot)
            a.skeletal_mesh_component.set_skinned_asset_and_update(u.load_asset(spec["asset"]))
        else:
            a = actors_sub.spawn_actor_from_class(u.CameraActor, vec(spec["location"]), rot)
            cam = a.camera_component
            cam.set_editor_property("field_of_view", float(spec.get("fov", 35.0)))
            cam.set_editor_property("constrain_aspect_ratio", False)
        a.set_actor_label(spec["label"])
        out["actors"][spec["label"]] = a.get_path_name()
elif args["op"] == "pose":
    # A fresh actor per pose: re-posing an existing single-node actor showed the PREVIOUS pose
    # (measured 2026-09-28: sockets and frames lagged one call behind); a new actor poses at once.
    old = find(args["label"])
    loc, rot, mesh = old.get_actor_location(), old.get_actor_rotation(), old.skeletal_mesh_component.get_skinned_asset()
    actors_sub.destroy_actor(old)
    a = actors_sub.spawn_actor_from_class(u.SkeletalMeshActor, loc, rot)
    a.skeletal_mesh_component.set_skinned_asset_and_update(mesh)
    a.set_actor_label(args["label"])
    comp = a.skeletal_mesh_component
    comp.set_update_animation_in_editor(True)
    comp.override_animation_data(u.load_asset(args["anim"]), False, False, float(args["time"]), 0.0)
    out["pose"] = {"anim": args["anim"], "time": float(args["time"]), "actor": a.get_path_name()}
elif args["op"] == "sockets":
    a = find(args["label"])
    comp = a.skeletal_mesh_component
    loc = a.get_actor_location()
    out["pose"] = {"position_read_back": round(comp.get_position(), 5),
                   "animation_mode": str(comp.get_animation_mode())}
    for s in ("Weapon", "Head"):
        p = comp.get_socket_location(s)
        out["pose"]["socket_%s_actor_space" % s] = [round(p.x - loc.x, 3), round(p.y - loc.y, 3), round(p.z - loc.z, 3)]
elif args["op"] == "camera":
    a = find(args["label"])
    r = args["rotation"]
    a.set_actor_location_and_rotation(vec(args["location"]), u.Rotator(float(r[0]), float(r[1]), float(r[2])), False, False)
    level_sub.pilot_level_actor(a)
    out["camera"] = {"label": args["label"], "fov": a.camera_component.get_editor_property("field_of_view"),
                     "location": args["location"], "rotation": r}
elif args["op"] == "cleanup":
    level_sub.eject_pilot_level_actor()
    out["destroyed"] = []
    for label in args["labels"]:
        for a in [x for x in actors_sub.get_all_level_actors() if x.get_actor_label() == label]:
            actors_sub.destroy_actor(a)
            out["destroyed"].append(label)
with open(args["out"], "w", encoding="utf-8", newline="\n") as handle:
    handle.write(json.dumps(out, indent=1, sort_keys=True) + "\n")
