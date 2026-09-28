import json
import unreal as u
out = {}
actors = u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
for a in actors:
    label = a.get_actor_label()
    if label in ("A1V3 v2 - temporary", "A1V3 v3 - temporary"):
        c = a.skeletal_mesh_component
        base = a.get_actor_location()
        d = {"actor_location": [base.x, base.y, base.z], "mesh": c.get_skeletal_mesh_asset().get_path_name()}
        for s in ("Head", "Weapon"):
            p = c.get_socket_location(s)
            r = c.get_socket_rotation(s)
            d["socket_" + s] = {"component_space_cm": [round(p.x - base.x, 4), round(p.y - base.y, 4), round(p.z - base.z, 4)],
                                "world_rotation": [round(r.pitch, 3), round(r.yaw, 3), round(r.roll, 3)]}
        for b in ("head", "weapon", "hand_L", "spine", "root", "SKEL_Medusa"):
            p = c.get_socket_location(b)
            d["bone_" + b + "_cm"] = [round(p.x - base.x, 4), round(p.y - base.y, 4), round(p.z - base.z, 4)]
        d["num_sockets_on_asset"] = c.get_skeletal_mesh_asset().num_sockets()
        out[label] = d
open("C:/tmp/a1v3/ue_sockets.json", "w").write(json.dumps(out, indent=1))
u.log("A1V3_SOCKETS_OK " + json.dumps(out))
