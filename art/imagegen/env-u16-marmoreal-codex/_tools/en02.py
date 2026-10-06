"""EN-02: package-only preparation, composition, sheets and independent readback.

No git/Unreal/provider calls. Run with python -B. Raw generation stays untouched.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import distance_transform_edt

ROOT = Path(__file__).resolve().parents[4]
PKG = ROOT / "art/imagegen/env-u16-marmoreal-codex"
IMG = ROOT / "scraped-data/derived/env-u16-marmoreal-codex"
SIZE = (2340, 1317)
BOX = (334, 188, 2006, 1129)
ORIGINAL = IMG / "marmoreal-clean.png"
MASK = IMG / "marmoreal-lantern-mask.png"
FIELD = IMG / "marmoreal-field-mask.png"
C0 = ROOT / "scraped-data/derived/concepts/env-v1/marmoreal-v1.png"
BASELINE = PKG / "en02-baseline.json"

PROMPT = """Use case: precise-object-edit / outpainting.
Asset type: painted Marmoreal backdrop plate, not a game board or screenshot.
Input image 1 is the ONLY edit target: EN-02-outpaint-input.png, 2340x1317.
The unchanged original occupies x=334..2005, y=188..1128 (1672x941).
Transparent pixels around that rectangle are the ONLY area to paint. Do not
resize, crop, move, zoom or repaint the original; keep its grey field untouched.
Extend the painting outward seamlessly: same perspective, same palette, same
painterly texture, terrain continues naturally, darker toward the frame edges,
no new landmarks, no water.
Continue the night sky and dark clouds above the existing colonnade, keeping
the existing architectural perspective. At the sides continue the existing
marble colonnade, balustrades and blossoming cherry foliage naturally; do not
mirror architecture or create new arches, towers or statues. Below continue
the rock cliff of the floating garden, falling into dark blue night haze.
The blue haze is air and clouds, never sea or water. No moon disc, figures,
lanterns, text, letters, numbers, logos, UI, red fills, ink splatter or banners.
Do not copy or imitate assets or pixels from any commercial digital board-game
edition. Do not insert board spaces, game data, heroes or decorations that
carry meaning only through colour. No stretched streaks or edge replication.
Output one fully opaque RGB painting at 2340x1317 with exact registration.
The original will be pasted back byte-identically after this pass. Join the
extension to its ORIGINAL colours and structures, rather than repainting it.
"""


def rel(p):
    return p.relative_to(ROOT).as_posix()


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write_json(p, value):
    assert p.is_relative_to(PKG) or p.is_relative_to(IMG)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(p):
    return json.loads(p.read_text(encoding="utf-8-sig"))


def stamp():
    return datetime.now(timezone.utc).isoformat()


def file_info(p):
    return {"sha256": sha(p), "bytes": p.stat().st_size}


def prepare():
    if BASELINE.exists():
        raise RuntimeError("Baseline already exists: do not overwrite the before-state.")
    source_paths = [ORIGINAL, MASK, FIELD, C0,
                    ROOT / "tools/art/concept_paste/marmoreal.paste.json",
                    ROOT / "docs/game-design/visual/06-tasks/prompts/EN-02.codex.md"]
    hud = ROOT / "art/imagegen/hud-icons-v3"
    source_paths += sorted(p for p in hud.rglob("*") if p.is_file())
    original_generator = hud / "_tools/draw_icons.py"
    snapshot = PKG / "_tools/draw_icons_v3_snapshot.py"
    frozen = {rel(p): file_info(p) for folder in (PKG, IMG)
              for p in sorted(folder.rglob("*")) if p.is_file()}
    sources = {rel(p): file_info(p) for p in source_paths}
    assert Image.open(ORIGINAL).size == (1672, 941)
    assert Image.open(MASK).size == (1672, 941)
    assert Image.open(FIELD).size == (1672, 941)
    assert Image.open(C0).size == (1672, 941)
    baseline = {"task": "EN-02", "created_utc": stamp(), "sources": sources,
                "package_before": frozen,
                "previous_generation_records": read_json(PKG / "generation-records.json"),
                "en01_acceptance_pass": read_json(PKG / "verification.json").get("acceptance_pass"),
                "en01_review": "README.md: Claude 2026-10-06, accepted by delegation, ВР-60"}
    write_json(BASELINE, baseline)
    if sha(original_generator) != sha(snapshot):
        backup = PKG / "history/en02-before-draw_icons_v3_snapshot.py"
        assert not backup.exists()
        shutil.copyfile(snapshot, backup)
        shutil.copyfile(original_generator, snapshot)
    assert sha(original_generator) == sha(snapshot)
    for name in ("README.md", "verification.json", "source-hashes-before.json",
                 "generation-records.json", "manifest-sha256.json"):
        dest = PKG / "history" / ("en02-before-" + name)
        assert not dest.exists()
        shutil.copyfile(PKG / name, dest)
    old_hashes = read_json(PKG / "source-hashes-before.json")
    old_hashes["EN-02"] = {"recorded_before_generation": True,
                           "created_utc": baseline["created_utc"], "files": sources,
                           "unreal_excluded": "Explicit instruction: do not open unreal/."}
    write_json(PKG / "source-hashes-before.json", old_hashes)
    records = read_json(PKG / "generation-records.json")
    records["EN-02"] = {"budget": 6, "generations": [], "attempted_generations": 0,
                         "status": "blocked_before_generation",
                         "provider_checks": [
                             {"tool": "syntx_ai.whoami", "result": "MCP tool call requires approval, but approval policy is never"},
                             {"tool": "syntx_ai.list_models(scope=image,search=gpt)", "result": "MCP tool call requires approval, but approval policy is never"}],
                         "built_in_imagegen_called": False,
                         "built_in_excluded_reason": "Automatic files outside the explicitly allowed roots."}
    write_json(PKG / "generation-records.json", records)
    (PKG / "prompts/EN-02-OUTPAINT-01.txt").write_text(PROMPT, encoding="utf-8")
    (IMG / "concepts").mkdir(exist_ok=True)
    canvas = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    canvas.paste(Image.open(ORIGINAL).convert("RGBA"), BOX[:2])
    canvas.save(IMG / "concepts/EN-02-outpaint-input.png")
    edit_mask = Image.new("L", SIZE, 255)
    ImageDraw.Draw(edit_mask).rectangle((BOX[0], BOX[1], BOX[2]-1, BOX[3]-1), fill=0)
    edit_mask.save(IMG / "concepts/EN-02-outpaint-mask.png")
    shifted_mask = Image.new("L", SIZE, 0)
    shifted_mask.paste(Image.open(MASK).convert("L"), BOX[:2])
    shifted_mask.save(IMG / "concepts/EN-02-lantern-mask-offset.png")
    m = np.asarray(Image.open(MASK).convert("L"), dtype=float)
    alpha = (m/255)*np.clip(distance_transform_edt(m>0)/6, 0, 1)
    original = np.asarray(Image.open(ORIGINAL).convert("RGB"), dtype=float)
    c0 = np.asarray(Image.open(C0).convert("RGB"), dtype=float)
    restored = np.rint(original*(1-alpha[...,None])+c0*alpha[...,None]).astype("uint8")
    Image.fromarray(restored).save(IMG / "concepts/EN-02-lit-original-preview.png")
    # This labelled preparation sheet is deliberately NOT an outpaint candidate.
    yy, xx = np.indices((SIZE[1], SIZE[0]))
    checks = np.where((xx//32+yy//32)%2, 32, 48).astype("uint8")
    plain = Image.fromarray(checks).convert("RGB")
    lit_preview = plain.copy()
    plain.paste(Image.open(ORIGINAL).convert("RGB"), BOX[:2])
    lit_preview.paste(Image.fromarray(restored), BOX[:2])
    for im in (plain, lit_preview):
        ImageDraw.Draw(im).rectangle((BOX[0]-1,BOX[1]-1,BOX[2],BOX[3]),outline="white",width=1)
    save_pair("ext-preparation-only", [plain,lit_preview],
              ["PREPARATION ONLY: checkerboard = missing outpaint", "PREPARATION ONLY: lit centre; missing outpaint"])
    write_json(PKG / "_tools/en02-spec.json", {
        "size": SIZE, "concept_rect_xywh": [334, 188, 1672, 941],
        "margins_ltrb": [334, 188, 334, 188], "mask_white_means": "outpaint permitted",
        "prompt_key": "EN-02-OUTPAINT-01", "prompt_sha256": sha(PKG / "prompts/EN-02-OUTPAINT-01.txt"),
        "input": rel(IMG / "concepts/EN-02-outpaint-input.png"),
        "input_sha256": sha(IMG / "concepts/EN-02-outpaint-input.png"),
        "C0_usage": "lit composite only; never supplied to outpainting",
        "lantern_feather": {"px": 6, "direction": "inward", "formula": "alpha=(m/255)*clip(distance(m>0)/6,0,1)"},
        "raw_policy": "Archive every generation unchanged in concepts; exact prompt/input hashes in generation-records.json.",
        "tile_fallback": "At most 1536px per tile, >=64px overlap; paste original after every pass; log each pass. Not attempted.",
        "failure_policy": "After two perspective/seam failures stop; Claude owns banana3/2K fallback.",
        "working_sizes": [[1521,856],[1170,659]],
        "K1": "Image-space x0.65 proxy only; no Unreal reads or true camera verification."})
    print(json.dumps({"prepared": True, "sources": len(sources), "en01_accepted": baseline["en01_acceptance_pass"]}))


def linear_luma(rgb):
    a = np.asarray(rgb, dtype=np.float64) / 255
    a = np.where(a <= .04045, a / 12.92, ((a + .055) / 1.055)**2.4)
    return a @ np.array([.2126, .7152, .0722])


def gray(rgb):
    y = linear_luma(rgb)
    g = np.where(y <= .0031308, 12.92*y, 1.055*y**(1/2.4)-.055)
    return Image.fromarray(np.clip(np.rint(g*255), 0, 255).astype("uint8")).convert("RGB")


def save_pair(name, items, labels):
    width = max(i.width for i in items)
    out = Image.new("RGB", (width*len(items), max(i.height for i in items)+40), "#202020")
    for n, (im, label) in enumerate(zip(items, labels)):
        out.paste(im, (n*width,40))
        ImageDraw.Draw(out).text((n*width+12,12), label, fill="white")
    dest = IMG / "comparison"
    dest.mkdir(exist_ok=True)
    out.save(dest / (name+"-colour.png"))
    gray(out).save(dest / (name+"-gray.png"))


def make_sheets(clean, lit):
    save_pair("ext-master", [clean,lit], ["clean-ext | 2340x1317", "lit-ext | 2340x1317"])
    for size in ((1521,856),(1170,659)):
        save_pair(f"ext-working-{size[0]}x{size[1]}",
                  [im.resize(size, Image.Resampling.LANCZOS) for im in (clean,lit)], ["clean-ext","lit-ext"])
    # Rect B in the paste JSON uses nominal 1920x1080 coordinates.
    sx, sy = 1672/1920, 941/1080
    b = [334-384*sx,188-216*sy,334+2304*sx,188+1296*sy]
    cx,cy = 334+1672/2,188+941/2
    k = [cx-1672/.65/2,cy-941/.65/2,cx+1672/.65/2,cy+941/.65/2]
    annotated = []
    for im in (clean,lit):
        frame = Image.new("RGB",(2700,1530),"#202020")
        frame.paste(im,(180,100))
        d = ImageDraw.Draw(frame)
        for box,color,label in ((BOX,"white","original"),(b,"#00ffff","B"),(k,"#ffff00","K1 proxy x0.65")):
            shifted = [box[0]+180,box[1]+100,box[2]+180,box[3]+100]
            d.rectangle(shifted,outline=color,width=3)
            d.text((shifted[0]+5,shifted[1]+5),label,fill=color)
        annotated.append(frame)
    save_pair("ext-framing", annotated, ["clean: B and IMAGE-SPACE K1 proxy", "lit: B and IMAGE-SPACE K1 proxy"])
    x0,y0,x1,y1=BOX
    edges={"top":(0,0,SIZE[0],y0+64), "bottom":(0,y1-64,SIZE[0],SIZE[1]),
           "left":(0,0,x0+64,SIZE[1]), "right":(x1-64,0,SIZE[0],SIZE[1])}
    for name,box in edges.items():
        pieces=[]
        for im in (clean,lit):
            crop=im.crop(box)
            pieces.append(crop.resize((crop.width*2,crop.height*2),Image.Resampling.NEAREST))
        save_pair("ext-edge-"+name+"-2x-nearest",pieces,["clean-ext | "+name,"lit-ext | "+name])
    y=linear_luma(clean)*255
    gy,gx=np.gradient(y)
    grad=np.hypot(gx,gy)
    heat=Image.fromarray(np.clip(np.rint(grad*4),0,255).astype("uint8")).convert("RGB")
    ImageDraw.Draw(heat).rectangle((x0-1,y0-1,x1,y1),outline="white")
    heat.save(IMG / "comparison/ext-gradient-magnitude.png")


def build(raw_name):
    baseline=read_json(BASELINE)
    for p,info in baseline["sources"].items():
        assert sha(ROOT/p)==info["sha256"], "Changed source: "+p
    raw=(ROOT/raw_name).resolve()
    assert raw.is_relative_to(IMG / "concepts"), "Raw must already be archived in concepts/."
    records=read_json(PKG / "generation-records.json")
    entries=records["EN-02"]["generations"]
    matches=[e for e in entries if e["raw_file"]==rel(raw)]
    assert matches, "Record actual provider generation, exact prompt key and raw hash before build."
    entry=matches[-1]
    assert len(entries)<=6 and entry["retouched"] is False
    assert sha(raw)==entry["raw_sha256"]
    assert sha(ROOT/entry["prompt_file"])==entry["prompt_sha256"]
    assert sha(ROOT/entry["input"])==entry["input_sha256"]
    clean=Image.open(raw)
    assert clean.size==SIZE, "Full-canvas raw must have exact registration; tiles need explicit assembly."
    if "A" in clean.getbands():
        assert np.all(np.asarray(clean.getchannel("A"))==255), "Outpaint has unfilled pixels."
    clean=clean.convert("RGB")
    clean.paste(Image.open(ORIGINAL).convert("RGB"),BOX[:2])
    clean.save(IMG / "marmoreal-clean-ext.png")
    m=np.asarray(Image.open(MASK).convert("L"),dtype=float)
    alpha=(m/255)*np.clip(distance_transform_edt(m>0)/6,0,1)
    original=np.asarray(Image.open(ORIGINAL).convert("RGB"),dtype=float)
    c0=np.asarray(Image.open(C0).convert("RGB"),dtype=float)
    restored=np.rint(original*(1-alpha[...,None])+c0*alpha[...,None]).astype("uint8")
    lit=clean.copy()
    lit.paste(Image.fromarray(restored),BOX[:2])
    lit.save(IMG / "marmoreal-lit-ext.png")
    make_sheets(clean,lit)
    print("Built candidate; run verify, visually inspect, and record review. No acceptance is inferred.")


def seam_metrics(image):
    a=linear_luma(image)*255
    x0,y0,x1,y1=BOX
    results={}
    samples=[]
    for side in ("left","right","top","bottom"):
        if side in ("left","right"):
            x=x0 if side=="left" else x1
            border=np.abs(a[y0:y1,x]-a[y0:y1,x-1])
            local=np.abs(np.diff(a[y0:y1,x-64:x+64],axis=1))
            nearby=np.concatenate((local[:,:63].ravel(),local[:,64:].ravel()))
        else:
            y=y0 if side=="top" else y1
            border=np.abs(a[y,x0:x1]-a[y-1,x0:x1])
            local=np.abs(np.diff(a[y-64:y+64,x0:x1],axis=0))
            nearby=np.concatenate((local[:63,:].ravel(),local[64:,:].ravel()))
        median=float(np.median(nearby)); maximum=float(border.max())
        results[side]={"max":maximum,"median_neighbour_64px":median,
                       "ratio":maximum/median if median else None,
                       "pass":maximum<=1.5*median}
        samples.append((border,nearby))
    median=float(np.median(np.concatenate([v[1] for v in samples])))
    maximum=float(max(v[0].max() for v in samples))
    return {"definition":"Absolute normal-direction difference of linear Rec.709 Y * 255 across the original rectangle; neighbouring 64px on each side, seam excluded, all samples including zeros retained.",
            "sides":results,"max":maximum,"median_neighbour_64px":median,
            "ratio":maximum/median if median else None,"pass":maximum<=1.5*median}


def verify():
    baseline=read_json(BASELINE)
    modified={"README.md","verification.json","source-hashes-before.json","generation-records.json","manifest-sha256.json"}
    frozen={p:info for p,info in baseline["package_before"].items()
            if not (str(Path(p).parent.as_posix())==rel(PKG) and Path(p).name in modified)
            and p!=rel(PKG / "_tools/draw_icons_v3_snapshot.py")}
    changed_sources=[p for p,info in baseline["sources"].items() if not (ROOT/p).exists() or sha(ROOT/p)!=info["sha256"]]
    changed_frozen=[p for p,info in frozen.items() if not (ROOT/p).exists() or sha(ROOT/p)!=info["sha256"]]
    records=read_json(PKG / "generation-records.json")
    previous={k:v for k,v in records.items() if k!="EN-02"}
    record_checks=[]
    for e in records["EN-02"]["generations"]:
        checks={k:sha(ROOT/e[k])==e[h] for k,h in (("raw_file","raw_sha256"),("prompt_file","prompt_sha256"),("input","input_sha256"))}
        record_checks.append({"prompt_key":e["prompt_key"],"checks":checks,"retouched_false":e["retouched"] is False})
    clean_path=IMG / "marmoreal-clean-ext.png"
    lit_path=IMG / "marmoreal-lit-ext.png"
    ready=clean_path.exists() and lit_path.exists()
    report={"task":"EN-02","status":"предложено; блокировка генерации" if not ready else "предложено; требуется визуальное ревью",
            "created_utc":stamp(),"source_unchanged":{"checked":len(baseline["sources"]),"changed":changed_sources,"pass":not changed_sources},
            "en01_files_frozen":{"checked":len(frozen),"changed":changed_frozen,"pass":not changed_frozen},
            "en01_acceptance_preserved_in_history":baseline["en01_acceptance_pass"],
            "generation_records_append_only":previous==baseline["previous_generation_records"],
            "generation_hash_checks":record_checks,"generations_used":len(records["EN-02"]["generations"]),"generation_budget":6,
            "deliverables_present":ready,"acceptance_pass":False,
            "outside_folder":[],"git_commands":0,"unreal_open_edit_build":0,
            "scope_evidence":"Package-only write paths enforced by script. No repository-wide audit claimed.",
            "persistent_processes_started":0,
            "generator_snapshot_matches_current_hud":sha(PKG / "_tools/draw_icons_v3_snapshot.py")==sha(ROOT / "art/imagegen/hud-icons-v3/_tools/draw_icons.py"),
            "previous_generator_snapshot_backed_up":(not (PKG / "history/en02-before-draw_icons_v3_snapshot.py").exists()) or sha(PKG / "history/en02-before-draw_icons_v3_snapshot.py")==baseline["package_before"][rel(PKG / "_tools/draw_icons_v3_snapshot.py")]["sha256"],
            "gray":"sRGB decode -> Rec.709 linear Y -> sRGB encode; weights .2126/.7152/.0722",
            "geometry":{"canvas":SIZE,"concept_rect_xywh":[334,188,1672,941],
                        "nominal_C0_scale":[1920/1672,1080/941],
                        "rect_B_C0":[-384,-216,2304,1296],
                        "actual_canvas_C0":[-334*1920/1672,-188*1080/941,(2340-334)*1920/1672,(1317-188)*1080/941],
                        "rect_B_strictly_contained":False,
                        "rounding_shortfall_C0_ltrb":[384-334*1920/1672,216-188*1080/941,2304-(2340-334)*1920/1672,1296-(1317-188)*1080/941],
                        "K1_image_space_required_size":[1672/.65,941/.65],
                        "K1_image_space_fits":False,"true_engine_K1_verified":False},
            "limits":["Connected generation service requires approval; approval_policy=never. No authentication/model-list/generation succeeded.",
                      "Built-in imagegen would write tool-managed PNG outside allowed roots; not invoked.",
                      "True K1 camera cannot be checked without forbidden unreal/ access. Image-space x0.65 proxy exceeds requested canvas.",
                      "Requested dimensions preserved exactly. Nominal C0 mapping leaves subpixel B shortfall on each edge; no silent enlargement."]}
    prepared_input=Image.open(IMG / "concepts/EN-02-outpaint-input.png")
    prepared_crop=prepared_input.crop(BOX).convert("RGB")
    original=Image.open(ORIGINAL).convert("RGB")
    prepared_lit=Image.open(IMG / "concepts/EN-02-lit-original-preview.png").convert("RGB")
    original_array=np.asarray(original)
    lit_array=np.asarray(prepared_lit)
    mask_array=np.asarray(Image.open(MASK).convert("L"))
    field_array=np.asarray(Image.open(FIELD).convert("L"))>0
    edit_array=np.asarray(Image.open(IMG / "concepts/EN-02-outpaint-mask.png"))
    input_array=np.asarray(prepared_input)
    report["preparation_readback"]={
        "input_size":list(prepared_input.size),
        "input_original_crop_pixel_sha256":hashlib.sha256(prepared_crop.tobytes()).hexdigest(),
        "original_pixel_sha256":hashlib.sha256(original.tobytes()).hexdigest(),
        "input_original_crop_byte_identical":prepared_crop.tobytes()==original.tobytes(),
        "outpaint_mask_inside_original_zero":bool(np.all(edit_array[BOX[1]:BOX[3],BOX[0]:BOX[2]]==0)),
        "outside_original_alpha_zero":bool(np.all(input_array[...,3][edit_array>0]==0)),
        "inside_original_alpha_255":bool(np.all(input_array[BOX[1]:BOX[3],BOX[0]:BOX[2],3]==255)),
        "lit_preview_changes_outside_mask":int(np.count_nonzero(np.any(original_array!=lit_array,axis=2)&(mask_array==0))),
        "lit_preview_field_808080":bool(np.all(lit_array[field_array]==128)),
        "lit_preview_is_not_extended_deliverable":True,
        "build_with_real_generated_image_tested":False}
    if ready:
        clean=Image.open(clean_path);lit=Image.open(lit_path)
        crop=clean.crop(BOX).convert("RGB")
        original=Image.open(ORIGINAL).convert("RGB")
        a=np.asarray(clean.convert("RGB"));b=np.asarray(lit.convert("RGB"))
        m=np.zeros((SIZE[1],SIZE[0]),bool)
        m[BOX[1]:BOX[3],BOX[0]:BOX[2]]=np.asarray(Image.open(MASK).convert("L"))>0
        f=np.asarray(Image.open(FIELD).convert("L"))>0
        report["readback"]={"clean":file_info(clean_path),"lit":file_info(lit_path),
                            "size_pass":clean.size==SIZE and lit.size==SIZE,
                            "RGB_pass":clean.mode==lit.mode=="RGB",
                            "crop_pixel_sha256":hashlib.sha256(crop.tobytes()).hexdigest(),
                            "original_pixel_sha256":hashlib.sha256(original.tobytes()).hexdigest(),
                            "crop_png_sha256":None,
                            "crop_byte_identical":crop.tobytes()==original.tobytes(),
                            "lit_changes_outside_lantern_mask":int(np.count_nonzero(np.any(a!=b,axis=2)&~m)),
                            "field_808080_clean":bool(np.all(np.asarray(crop)[f]==128)),
                            "field_808080_lit":bool(np.all(b[BOX[1]:BOX[3],BOX[0]:BOX[2]][f]==128))}
        crop_path=IMG / "comparison/ext-original-crop.png"
        crop.save(crop_path)
        report["readback"]["crop_png_sha256"]=sha(crop_path)
        report["seam"]=seam_metrics(clean)
        report["visual_review"]={"status":"not performed by this script","no_water":None,"no_mirrored_architecture":None,"no_streaks":None}
    else:
        report["blocked_checks"]=["final RGB/size", "final original crop sha256", "old-border gradient threshold",
                                  "lit mask locality", "final field", "no water/streaks/mirrored architecture", "final comparison sheets"]
    write_json(PKG / "verification.json",report)
    print(json.dumps({"source_unchanged":not changed_sources,"en01_frozen":not changed_frozen,"deliverables_present":ready,"acceptance_pass":False}))


def manifest():
    entries={rel(p):file_info(p) for folder in (PKG,IMG) for p in sorted(folder.rglob("*"))
             if p.is_file() and p!=PKG/"manifest-sha256.json"}
    write_json(PKG / "manifest-sha256.json",{"task":"EN-02","files":entries,"self_excluded":True})
    print(json.dumps({"manifest_files":len(entries)}))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=["prepare","build","verify","manifest"])
    parser.add_argument("--raw",help="Already archived and recorded full-canvas raw generation")
    args=parser.parse_args()
    if args.command=="build":
        if not args.raw:parser.error("build requires --raw")
        build(args.raw)
    else:globals()[args.command]()
