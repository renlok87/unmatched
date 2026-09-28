"""List a /Game/PipelineCandidates folder in the live UnrealEditor (evidence for "no duplicates").

    python tools/tripo-pipeline/review/ue_listing.py <folder> <out.json>

Read only: find_assets, list_folders, get_current_level and, for the candidate skeletal
mesh, get_socket_names / get_material_slots through unreal_mcp.py.
"""

import json
import subprocess
import sys

CLIENT = "C:/Users/ren/.claude/mcp-servers/clients/unreal_mcp.py"
TS = {"asset": "editor_toolset.toolsets.asset.AssetTools", "skm": "editor_toolset.toolsets.skeletal_mesh.SkeletalMeshTools",
      "scene": "editor_toolset.toolsets.scene.SceneTools"}


def call(ts, tool, args):
    out = subprocess.run([sys.executable, CLIENT, "call", TS[ts], tool, json.dumps(args)],
                         capture_output=True).stdout.decode("utf-8", "replace")
    res = json.loads(out)
    result = res["result"]
    if result.get("isError"):
        raise RuntimeError(result["content"][0]["text"])
    payload = result.get("structuredContent") or json.loads(result["content"][0]["text"])
    return payload.get("returnValue")


def main(folder, out_path):
    assets = sorted(call("asset", "find_assets", {"folder_path": folder, "name": "", "recursive": True}))
    out = {"folder": folder, "assets": assets, "count": len(assets)}
    for sk in (a for a in assets if a.rsplit("/", 1)[-1].startswith("SK_") and not a.endswith("_Skeleton")):
        ref = {"refPath": "%s.%s" % (sk, sk.rsplit("/", 1)[-1])}
        out.setdefault("skeletal", {})[sk] = {"sockets": call("skm", "get_socket_names", {"mesh": ref}),
                                              "material_slots": call("skm", "get_material_slots", {"mesh": ref})}
    out["subfolders_of_parent"] = sorted(call("asset", "list_folders", {"root_path": folder.rsplit("/", 1)[0],
                                                                        "recursive": False}))
    out["current_level"] = call("scene", "get_current_level", {})
    with open(out_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"count": out["count"], "skeletal": out.get("skeletal")}))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
