"""references/ue-import-package.md §4.4 step 2 for Achilles: delete the UE assets of the previous import run
(manifest stages.ue-import.ue_owned_assets, only under /Game/PipelineCandidates/Achilles/H2LD/; MI, then meshes, then
textures), then list what is left in the folder (expected: nothing).

    python delete_prev.py <previous run dir>      (under ue_lock.py, UE_CONSOLE_DROP set)
"""
import json
import sys

sys.path.insert(0, "tools/tripo-pipeline/review")
from ue_live import Ue  # noqa: E402

root = "/Game/PipelineCandidates/Achilles/H2LD/"
own = json.load(open(sys.argv[1] + "/manifest.json", encoding="utf-8"))["stages"]["ue-import"]["ue_owned_assets"]
own = [a for a in own if a.startswith(root)]


def rank(a):
    return (0 if "/Materials/" in a else 1 if "/Meshes/" in a else 2, -len(a))


ue = Ue()
for a in sorted(own, key=rank):
    if not ue.call("asset", "delete", {"path": a}):
        sys.exit("UE refused to delete " + a)
    print("deleted", a)
print("left", ue.call("asset", "find_assets", {"folder_path": root.rstrip("/"), "name": "", "recursive": True}))
