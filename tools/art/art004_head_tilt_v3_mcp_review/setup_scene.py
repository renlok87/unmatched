import ue, json, sys
FAR = {"x": 20000, "y": 20000, "z": 0}
def xf(x, y, z):
    return {"location": {"x": x, "y": y, "z": z}, "rotation": {"pitch": 0, "yaw": 0, "roll": 0}, "scale": {"x": 1, "y": 1, "z": 1}}
def find(label):
    r = ue.call(ue.SCENE, "find_actors", {"root": None, "name": label, "actor_type": None, "tag": "", "bounds": None, "collision_channels": []})["returnValue"]
    return [a for a in r if ue.call(ue.ACTOR, "get_label", {"actor": a})["returnValue"] == label]
def setup():
    state = {}
    fill = find("ART005 neutral readability fill - review only")
    med = find("ART004 Medusa - animation review")
    assert len(fill) == 1 and len(med) == 1, (fill, med)
    state["fill_original"] = ue.call(ue.ACTOR, "get_actor_transform", {"actor": fill[0]})["returnValue"]
    state["medusa_original"] = ue.call(ue.ACTOR, "get_actor_transform", {"actor": med[0]})["returnValue"]
    loc = state["medusa_original"]["location"]
    ue.call(ue.ACTOR, "set_actor_transform", {"actor": fill[0], "xform": xf(0, 100, 500), "worldspace": True})
    ue.call(ue.ACTOR, "set_actor_transform", {"actor": med[0], "xform": xf(10000, 10000, 0), "worldspace": True})
    out = {}
    for key, path, label in (("base", "/Game/ArtTests/ART004_V3Review/Meshes/SM_Medusa_BaseReview", "A1V3 base - temporary"),
                             ("v2", "/Game/ArtTests/ART004_V3Review/Meshes/SK_Medusa_V2Review", "A1V3 v2 - temporary"),
                             ("v3", "/Game/ArtTests/ART004_V3Review/Meshes/SK_Medusa_V3Review", "A1V3 v3 - temporary")):
        existing = find(label)
        if existing:
            out[key] = existing[0]
            continue
        a = ue.call(ue.SCENE, "add_to_scene_from_asset", {"asset_path": path, "name": label, "xform": xf(loc["x"], loc["y"], loc["z"]) if key != "v3" else xf(**FAR), "parent": None, "snap_to_ground": False})["returnValue"]
        ue.call(ue.ACTOR, "set_label", {"actor": a, "label": label})
        out[key] = a
    state["actors"] = out
    state["fill"] = fill[0]; state["medusa"] = med[0]; state["loc"] = loc
    return state
if __name__ == "__main__":
    s = setup()
    json.dump(s, open(sys.argv[1], "w"), indent=1)
    print(json.dumps(s, indent=1))
