"""Analysis-only portrait previews; does not edit or reencode source outputs."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps
import hashlib
import json

ROOT = Path(__file__).resolve().parents[5]
PACKAGE = Path(__file__).resolve().parents[1]
KEYS = ["faith","giles","daisy","yennenga-archer"]
NAVY, CREAM = (6,22,35),(249,235,219)
FONT_PATH = Path("C:/Windows/Fonts/arial.ttf")
FONT, SMALL = ImageFont.truetype(str(FONT_PATH),16),ImageFont.truetype(str(FONT_PATH),12)

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def save_json(path,obj):
    Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

def disc(image,size):
    reduced=image.convert("RGB").resize((size,size),Image.Resampling.LANCZOS)
    mask=Image.new("L",(size,size),0)
    ImageDraw.Draw(mask).ellipse((0,0,size-1,size-1),fill=255)
    result=Image.new("RGB",(size,size),NAVY)
    result.paste(reduced,(0,0),mask)
    return result

def refresh_manifest():
    save_json(PACKAGE/"manifest-sha256.json",{p.relative_to(PACKAGE).as_posix():digest(p)
        for p in sorted(PACKAGE.rglob("*")) if p.is_file() and p.name!="manifest-sha256.json"})

def main():
    sources_before=json.loads((PACKAGE/"source-hashes-before.json").read_text(encoding="utf-8-sig"))
    sources=[{**s,"after_sha256":digest(ROOT/s["path"]),"unchanged":s["sha256"]==digest(ROOT/s["path"])}
        for s in sources_before]
    records=json.loads((PACKAGE/"generation-records.json").read_text(encoding="utf-8"))
    by_key={r["asset_key"]:r for r in records}
    review_path=PACKAGE/"visual-review.json"
    visual=json.loads(review_path.read_text(encoding="utf-8")) if review_path.exists() else None
    preview_dir=PACKAGE/"review"
    preview_dir.mkdir(exist_ok=True)
    sheet=Image.new("RGB",(1260,1010),NAVY)
    draw=ImageDraw.Draw(sheet)
    draw.text((20,10),"WAVE7 CP-33 PORTRAIT SOURCES - proposed, not runtime-ready",font=FONT,fill=CREAM)
    for x,label in [(20,"Proposed reference"),(228,"Square source"),(436,"Full circle100 /160px"),
                    (670,"Gray160px"),(870,"Native80px /x2 nearest"),(1080,"Native40px"),(1180,"Native80px")]:
        draw.text((x,40),label,font=SMALL,fill=CREAM)
    exports=[]
    for idx,key in enumerate(KEYS):
        card=json.loads((PACKAGE/key/"task-card.json").read_text(encoding="utf-8"))
        record=by_key[key]
        path=PACKAGE/key/"portrait-source.png"
        image=Image.open(path)
        ref=Image.open(ROOT/card["reference"])
        y=70+idx*230
        ref_thumb=ImageOps.contain(ref.convert("RGB"),(176,186))
        sheet.paste(ref_thumb,(20+(176-ref_thumb.width)//2,y))
        sheet.paste(image.resize((186,186),Image.Resampling.LANCZOS),(228,y))
        circle160,circle80=disc(image,160),disc(image,80)
        gray=ImageOps.grayscale(circle160).convert("RGB")
        sheet.paste(circle160,(436,y+12))
        sheet.paste(gray,(670,y+12))
        sheet.paste(circle80.resize((160,160),Image.Resampling.NEAREST),(870,y+12))
        target=card.get("targetSize",80)
        circle_target=disc(image,target)
        sheet.paste(circle_target,(1080,y+12))
        sheet.paste(circle80,(1180,y+12))
        draw.text((1080,y+105),"native"+str(target)+"px",font=SMALL,fill=CREAM)
        circle_target.save(preview_dir/f"{key}-circle100-target{target}.png")
        draw.text((20,y+193),key,font=FONT,fill=CREAM)
        draw.text((228,y+193),"selected g1; original PNG",font=SMALL,fill=CREAM)
        draw.text((670,y+193),"full100 crop, no tight-crop claim",font=SMALL,fill=CREAM)
        circle80.save(preview_dir/f"{key}-circle100-80.png")
        circle160.save(preview_dir/f"{key}-circle100-160.png")
        gray.save(preview_dir/f"{key}-circle100-160-gray.png")
        metadata={"key":card["key"],"name":card["name"],"date":"2026-10-15","status":"proposed-source-candidate",
            "stage":"original-raster-source-candidate","runtime_ready":False,"runtime_imported":False,
            "hero_link_confirmed":card["heroLinkConfirmed"],"roster_evidence":card["rosterEvidence"],
            "selected_generation":record["id"],"source_file":"portrait-source.png",
            "dimensions":list(image.size),"mode":image.mode,"sha256":digest(path),
            "untouched_tool_output":digest(path)==digest(record["original_path"]),
            "saved_generation_copy_equal":digest(path)==digest(PACKAGE/record["saved_path"]),
            "reference":{"path":card["reference"],"sha256":digest(ROOT/card["reference"]),"status":card["reference_status"],"stage":card["reference_stage"],"selected_id":card["reference_selected_id"],"formal_accepted":False},
            "tool":"image_gen.imagegen (built-in)","prompt_file":"prompt.txt",
            "proposed_crop":{"cx":.5,"cy":.5,"d":1.0,"status":"analysis recommendation; runtime acceptance pending"},
            "limitations":["Actual generated square dimensions retained unchanged; no size or exact-palette guarantee.",
                "Full-circle head fit is the framing acceptance priority; exact head-height fractions are not a pixel lock.",
                "An original project-owned source gap was checked; this is a new candidate, not replacement of accepted MVP art.",
                "Fine ornament interpretation may differ; no pixel-identical identity claim.",
                "Registry, runtime media key, import, crop acceptance and screenshots remain outside this package."],
            "source_visual_review":visual["portraits"][key] if visual else {"state":"pending review-sheet inspection"}}
        if not card["heroLinkConfirmed"]:
            metadata["limitations"].append("Helper heroLink is absent in art-hub; live owner and sidekick verified by fresh DB evidence and raw owner JSON. See CP33-live-owner-evidence.json.")
        metadata["target_size"]=card.get("targetSize",80)
        metadata["card_id"]="CP-33"
        metadata["actual_sidekick_name"]=card["actualSidekickName"]
        metadata["owner"]=card["owner"]
        metadata["normalized_alias"]=card["normalizedAlias"]
        metadata["live_owner_confirmed"]=card["liveOwnerConfirmed"]
        metadata["formal_accepted"]=False
        metadata["limitations"].extend(card.get("limitations",[]))
        save_json(PACKAGE/key/"metadata.json",metadata)
        exports.append({"key":card["key"],"dimensions":list(image.size),"source_sha256":metadata["sha256"],
            "copy_equal":metadata["untouched_tool_output"]})
    sheet.save(PACKAGE/"review-sheet.png")
    for record in records:
        record["reference_sha256"]=digest(ROOT/record["reference_image"])
        record["saved_sha256"]=digest(PACKAGE/record["saved_path"])
        record["original_sha256"]=digest(record["original_path"])
        record["copy_equal"]=record["saved_sha256"]==record["original_sha256"]
    save_json(PACKAGE/"generation-records.json",records)
    verification={"schema":"portrait-source-wave7-review/1","date":"2026-10-15","status":"proposed-source-candidates",
        "generations":len(records),"source_unchanged":all(s["unchanged"] for s in sources),"sources":sources,
        "tool_original_copies_equal":all(r["copy_equal"] for r in records),"exports":exports,
        "review_sheet":"review-sheet.png","visual_review":visual,"font_reference":{"path":str(FONT_PATH),"sha256":digest(FONT_PATH)},
        "review_previews_only":True,"production_sources_reencoded":False,"runtime_ready":False,
        "exact_palette_verified":False,"proposed_crop":[.5,.5,1.0],"missing_hero_links":KEYS,"references_formal_accepted":False,"archer_representative_for_count":2,
        "remaining":["Integrating owner decides link/registry/import and runtime crop acceptance."]}
    reference_paths={r["reference_image"] for r in records}
    reference_checks=[s for s in sources if s["path"] in reference_paths]
    verification["reference_check_count"]=len(reference_checks)
    verification["image_references_unchanged"]=len(reference_checks)==4 and all(s["unchanged"] for s in reference_checks)
    verification["changed_context_sources"]=[s for s in sources if not s["unchanged"]]
    verification["context_mutation_explanation"]="Shared context documents may be updated concurrently by coordinator. Before hashes are retained; changed paths are reported separately from image references."
    verification["json_utf8_without_replacement_characters"]=all(chr(0xfffd) not in p.read_text(encoding="utf-8-sig") for p in PACKAGE.rglob("*.json"))
    save_json(PACKAGE/"verification.json",verification)
    save_json(PACKAGE/"ledger-handoff.json",{
        "card_id":"CP-33","date":"2026-10-15","tool":"image_gen.imagegen built-in",
        "calls":len(records),"selected":len(records),"corrections":0,
        "external_paid_SYNTX_Tripo_calls":0,"known_credit_cost":None,"credits_ledger_written":False,
        "coordinator_records_ledger":True,"runtime_ready":False,
        "records":[{"id":r["id"],"asset_key":r["asset_key"],"portrait_key":r["portrait_key"],
            "prompt_path":r["exact_prompt"],"prompt_sha256":digest(PACKAGE/r["exact_prompt"]),
            "source_sha256":r["saved_sha256"],"original_path":r["original_path"]} for r in records]})
    refresh_manifest()
    print(json.dumps({"source_unchanged":verification["source_unchanged"],"generations":len(records),
        "exports":len(exports),"sheet":str(PACKAGE/"review-sheet.png")}))

if __name__=="__main__":
    main()
