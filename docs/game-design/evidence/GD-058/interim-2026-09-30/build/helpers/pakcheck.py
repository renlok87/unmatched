import json, os, sys, hashlib, datetime
proj = r"C:/Users/ren/WebstormProjects/unmached/unmached/unreal/Unmatched"
content = os.path.join(proj, "Content")
cooked = os.path.join(proj, "Saved/Cooked/Windows/Unmatched/Content")
utoc = open(os.path.join(proj, "Saved/StagedBuilds/Windows/Unmatched/Content/Paks/Unmatched-Windows.utoc"), "rb").read()
refset = set(l.strip() for l in open(os.path.join(proj, "Saved/Cooked/Windows/Unmatched/Metadata/ReferencedSet.txt"), encoding="utf-8") if l.startswith("/"))
import re
listed = {}
for l in open("C:/tmp/gd058-interim/utoc-list.txt", encoding="utf-8", errors="replace"):
    m = re.search(r'"\.\./\.\./\.\./Unmatched/Content/([^"]+)" offset: \d+, size: (\d+) bytes, hash: ([0-9a-f]+)', l)
    if m: listed[m.group(1)] = {"size": int(m.group(2)), "chunkHash": m.group(3)}
cook_start = datetime.datetime.fromisoformat(sys.argv[1]).timestamp()
dirs = ["PipelineCandidates/KingArthur/H2LD", "PipelineCandidates/KingArthur/Rig", "PipelineCandidates/KingArthur/H2Anim",
        "PipelineCandidates/Merlin/H2LD", "PipelineCandidates/Merlin/Rig", "PipelineCandidates/Merlin/H2Anim",
        "PipelineCandidates/Medusa/H2LD", "PipelineCandidates/Medusa/Rig", "PipelineCandidates/Medusa/H2Anim",
        "PipelineCandidates/Harpy/H3LD", "PipelineCandidates/Harpy/Rig", "PipelineCandidates/Harpy/H2Anim",
        "PipelineCandidates/TableBase/20260928-table-base-tripo-h31", "UM/Materials/v2"]
def assets(d, skip_sub=None):
    out = []
    for root, ds, fs in os.walk(os.path.join(content, d)):
        if skip_sub and os.path.normpath(root).startswith(os.path.normpath(os.path.join(content, skip_sub))):
            continue
        for f in fs:
            if f.endswith((".uasset", ".umap")):
                out.append(os.path.relpath(os.path.join(root, f), content).replace("\\", "/"))
    return sorted(out)
res = {}
for d in dirs:
    src = assets(d, "UM/Materials/v2/Test" if d == "UM/Materials/v2" else None)
    miss_ref, miss_utoc, miss_cooked, stale = [], [], [], []
    for a in src:
        pkg = "/game/" + os.path.splitext(a)[0].lower()
        if pkg not in refset: miss_ref.append(a)
        if a not in listed: miss_utoc.append(a)
    res[d] = {"source": len(src), "inReferencedSet": len(src) - len(miss_ref), "missingInUtoc": len(miss_utoc),
              "missingReferencedSet": miss_ref, "missingUtocNames": miss_utoc}
test = assets("UM/Materials/v2/Test")
res["UM/Materials/v2/Test"] = {"sourceAssets": len(test), "inReferencedSet": sum(1 for a in test if "/game/" + os.path.splitext(a)[0].lower() in refset),
"pathsInUtoc": sum(1 for a in test if a in listed)}
# look-dev r2/r3 changed assets: sha of source, cooked mtime
changed = sys.argv[2:]
ld = {}
for a in changed:
    p = os.path.join(content, a)
    c = os.path.join(cooked, a)
    ld[a] = {"sourceSha256": hashlib.sha256(open(p, "rb").read()).hexdigest(),
             "inUtoc": a in listed, "utocChunk": listed.get(a),
             "inReferencedSet": "/game/" + os.path.splitext(a)[0].lower() in refset}
print(json.dumps({"utocListedFiles": len(listed), "dirs": res, "lookdevChanged": ld}, ensure_ascii=False, indent=1))
