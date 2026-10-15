"""Read input/artifact integrity; write only this prep folder's final hash manifest."""
import hashlib
import json
from pathlib import Path
import struct
from PIL import Image

OUT=Path(__file__).resolve().parent
REPO=OUT.parents[3]

def read(p):
    return json.loads(p.read_text(encoding="utf-8"))

def digest(p):
    with p.open("rb") as f:
        return hashlib.file_digest(f,"sha256").hexdigest()

inv=read(OUT/"source-inventory.json")
src=REPO/inv["source"]["path"]
assert src.stat().st_size==inv["source"]["bytes"]
assert digest(src)==inv["source"]["sha256_before"]==inv["source"]["sha256_after"]
with src.open("rb") as f:
    magic,version,length=struct.unpack("<4sII",f.read(12))
    assert magic==b"glTF" and version==2 and length==src.stat().st_size
    n,kind=struct.unpack("<II",f.read(8)); assert kind==0x4E4F534A
    gltf=json.loads(f.read(n))
    while f.tell()<length:
        n,kind=struct.unpack("<II",f.read(8));f.seek(n,1)
    assert f.tell()==length
assert len(gltf["meshes"])==24
tris=sum(gltf["accessors"][p["indices"]]["count"]//3 for m in gltf["meshes"] for p in m["primitives"] if p.get("mode",4)==4)
assert tris==inv["total_triangles"]==1967447
roles=read(OUT/"part-role-map.json")
proposal=read(OUT/"stage3-config.proposed.json")
assert proposal["ready_for_h2_runner"] is False
partial=proposal["h2_profile_partial"]
assert set(roles["parts"])==set(inv["parts"])==set(partial["parts"])
assert sum(r["mesh"]=="base" for r in roles["parts"].values())==1
assert sum(r["mesh"]=="weapon" for r in roles["parts"].values())==1
assert partial["parts"]["tripo_part_8"]["mesh"]=="weapon"
assert partial["textures"]["team_mask"]["base_band"]["part"]=="tripo_part_1"
assert partial["uv"]["density_reference_part"]=="tripo_part_3"
assert partial["preview"]["frame"]["side"]=="right"
assert "tex_glb" not in partial["sources"] and "bones" not in partial["rig"]
for part in roles["parts"].values():
    for ref in part["visual_evidence"]:
        assert (OUT/ref).is_file(),ref
images=list(OUT.rglob("*.png"))
for p in images:
    with Image.open(p) as im: im.verify()
assert len(list((OUT/"renders").glob("tripo_part_*.png")))==48
assert len(list((OUT/"details").glob("*.png")))==5
assert not list(OUT.rglob("*.blend")) and not list(OUT.rglob("*.fbx")) and not list(OUT.rglob("*.glb"))
card=read(REPO/inv["acceptance_card"]["path"])
assert digest(REPO/inv["acceptance_card"]["path"])==inv["acceptance_card"]["sha256"]
for x in card["accepted_object"]:
    assert digest(REPO/x["path"])==x["sha256"]
for name,script in [("process-record.json","scout_parts.py"),("details-process-record.json","scout_details.py")]:
    proc=read(OUT/name)
    assert proc["exit_code"]==0 and proc["child_reaped"]
    assert digest(OUT/script)==proc["script_sha256"]
inputs={str(src.relative_to(REPO)).replace("\\","/"), inv["acceptance_card"]["path"],
        ".agents/skills/3d-model-pipeline/SKILL.md", "AGENTS.md", "docs/art-pipeline/BLENDER-MODEL-HANDBOOK.md", "docs/art-pipeline/rig/rig-contract.json",
        ".agents/skills/3d-model-pipeline/references/acceptance-and-blender.md",
        ".agents/skills/3d-model-pipeline/references/new-character-registration.md",
        "art/pipeline-candidates/ASSET-PATROCLUS-001/asset-card.yaml"}
inputs.update(x["path"] for x in card["accepted_object"])
reuse=read(OUT/"recipe-reuse.json")
inputs.update(x["path"] for x in reuse["donors"]+reuse["current_generic_tools"])
files=[{"path":p.relative_to(OUT).as_posix(),"bytes":p.stat().st_size,"sha256":digest(p)} for p in sorted(OUT.rglob("*")) if p.is_file() and p.name!="hash-manifest.json"]
manifest={"schema":"patroclus.h2-prep-hash-manifest/1","status":"prep integrity verified; NOT model acceptance", "verification":{"source_glb_header_and_chunks":True,"source_hash_unchanged":True,"source_mesh_count":24,"source_triangle_count":tris,"accepted_concept_hashes":3,"verified_png_files":len(images),"isolated_part_renders":48,"details":5,"source_scripts_match_executed_hashes":True,"both_owned_blender_processes_exited_and_reaped":True,"no_model_exports_in_prep":True},
          "input_pins":[{"path":p,"bytes":(REPO/p).stat().st_size,"sha256":digest(REPO/p)} for p in sorted(inputs)],"files":files,"manifest_note":"This file excludes its own hash. Logs and process records pin the original commands; measurements.json was compacted by prepare_handoff.py without recalculating scalar measurements."}
(OUT/"hash-manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
print(f"PASS prep integrity: {len(files)} artifacts, {len(images)} PNGs, 24 parts / {tris} tris; source + 3 concept hashes match; 2 owned Blender children exited 0 and reaped; no bake/rig/exports.")
