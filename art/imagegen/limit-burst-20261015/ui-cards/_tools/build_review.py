"""Analysis-only thumbnails and verification; generated source PNGs are never changed."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps
import hashlib
import json

ROOT = Path(__file__).resolve().parents[5]
PACKAGE = Path(__file__).resolve().parents[1]
KEYS = ["achilles", "robin-hood", "sherlock-holmes", "nikola-tesla"]
NAVY, CREAM = (6,22,35), (249,235,219)
FONT_PATH = Path("C:/Windows/Fonts/arial.ttf")
FONT, SMALL = ImageFont.truetype(str(FONT_PATH),16), ImageFont.truetype(str(FONT_PATH),12)

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def save_json(path, obj):
    Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

def disc(image,size,diameter=1.0):
    side=image.width*diameter
    box=((image.width-side)/2,(image.height-side)/2,(image.width+side)/2,(image.height+side)/2)
    small=image.crop(box).resize((size,size),Image.Resampling.LANCZOS).convert("RGB")
    mask=Image.new("L",(size,size),0)
    ImageDraw.Draw(mask).ellipse((0,0,size-1,size-1),fill=255)
    out=Image.new("RGB",(size,size),NAVY)
    out.paste(small,(0,0),mask)
    return out

def main():
    before=json.loads((PACKAGE/"source-hashes-before.json").read_text(encoding="utf-8-sig"))
    sources=[{**s,"after_sha256":digest(ROOT/s["path"]),"unchanged":s["sha256"]==digest(ROOT/s["path"])} for s in before]
    records=json.loads((PACKAGE/"generation-records.json").read_text(encoding="utf-8"))
    review_path=PACKAGE/"visual-review.json"
    visual_review=json.loads(review_path.read_text(encoding="utf-8")) if review_path.exists() else None
    selected={r["portrait_key"].split(":")[-1]:r for r in records if r["selected"]}
    review=PACKAGE/"review"
    review.mkdir(exist_ok=True)
    sheet=Image.new("RGB",(1370,1020),NAVY)
    draw=ImageDraw.Draw(sheet)
    draw.text((20,12),"PORTRAIT SOURCE REVIEW - proposed, not runtime-ready",font=FONT,fill=CREAM)
    cols=[(20,"Project design"),(228,"Square source"),(436,"Full circle100 /160px"),(670,"Gray160px"),(870,"Circle80px / x2 nearest"),(1110,"Diagnostic circle76%")]
    for x,label in cols:
        draw.text((x,40),label,font=SMALL,fill=CREAM)
    exports=[]
    for idx,key in enumerate(KEYS):
        card=json.loads((PACKAGE/key/"task-card.json").read_text(encoding="utf-8"))
        record=selected[key]
        path=PACKAGE/key/"portrait-source.png"
        image=Image.open(path)
        ref=Image.open(ROOT/card["reference"])
        y=70+idx*232
        thumb=ImageOps.contain(ref.convert("RGB"),(176,186))
        sheet.paste(thumb,(20+(176-thumb.width)//2,y))
        sheet.paste(image.resize((186,186),Image.Resampling.LANCZOS),(228,y))
        circle160=disc(image,160)
        gray=ImageOps.grayscale(circle160).convert("RGB")
        circle80=disc(image,80)
        sheet.paste(circle160,(436,y+12))
        sheet.paste(gray,(670,y+12))
        sheet.paste(circle80.resize((160,160),Image.Resampling.NEAREST),(870,y+12))
        sheet.paste(disc(image,160,.76),(1110,y+12))
        draw.text((20,y+194),key,font=FONT,fill=CREAM)
        draw.text((228,y+194),"selected "+record["id"],font=SMALL,fill=CREAM)
        draw.text((670,y+194),"identity clear; crop76 not accepted",font=SMALL,fill=CREAM)
        circle80.save(review/f"{key}-circle100-80.png")
        circle160.save(review/f"{key}-circle100-160.png")
        gray.save(review/f"{key}-circle100-160-gray.png")
        disc(image,160,.76).save(review/f"{key}-circle76-diagnostic.png")
        metadata={"key":card["key"],"name":card["name"],"date":"2026-10-15","status":"предложено",
            "stage":"original-raster-source-candidate","runtime_ready":False,"runtime_imported":False,
            "selected_generation":record["id"],"source_file":"portrait-source.png",
            "dimensions":list(image.size),"mode":image.mode,"sha256":digest(path),
            "untouched_tool_output":digest(path)==digest(record["original_path"]),
            "saved_generation_copy_equal":digest(path)==digest(PACKAGE/record["saved_path"]),
            "reference":{"path":card["reference"],"sha256":digest(ROOT/card["reference"])},
            "tool":"image_gen.imagegen (built-in)","prompt_file":"prompt-g2.txt" if key=="achilles" else "prompt.txt",
            "proposed_crop":{"cx":.5,"cy":.5,"d":1.0,"status":"analysis recommendation; runtime acceptance pending"},
            "limitations":["Requested1024 square was advisory; actual generated dimensions retained unchanged.",
                "Initial prompt central76%-diameter full-head crop is not achieved; use full-source circle and accept before runtime.",
                "Background is visually navy; exact uniform #061623 not claimed or recoloured.",
                "Commercial scraped portrait may exist; this is a new original-source candidate, not replacement of accepted MVP art.",
                "Registry, media key, texture import, crop acceptance and LAN screenshots remain outside package."],
            "source_visual_review":{"identity_matches_project_design":True,"both_eyes_visible":True,"no_text_ui_frame":True,
                "full_source_headwear_complete":True,"central76_headwear_complete":False,
                "crop100_80px_face_readable":"pending inspection of review-sheet.png"}}
        save_json(PACKAGE/key/"metadata.json",metadata)
        if visual_review:
            metadata["source_visual_review"]["crop100_80px_face_readable"]=visual_review["portraits"][key]["circle100_80px_face_readable"]
            metadata["source_visual_review"]["recorded_review"]="../visual-review.json"
            save_json(PACKAGE/key/"metadata.json",metadata)
        exports.append({"key":card["key"],"dimensions":list(image.size),"source_sha256":metadata["sha256"],"copy_equal":metadata["untouched_tool_output"]})
    sheet.save(PACKAGE/"review-sheet.png")
    for record in records:
        if record["id"].endswith("-g1"):
            record["exact_prompt"]=record["id"][:-3]+"/prompt.txt"
        record["reference_sha256"]=digest(ROOT/record["reference_image"])
        record["saved_sha256"]=digest(PACKAGE/record["saved_path"])
        record["original_sha256"]=digest(record["original_path"])
        record["copy_equal"]=record["saved_sha256"]==record["original_sha256"]
    save_json(PACKAGE/"generation-records.json",records)
    verification={"schema":"portrait-source-burst-review/1","date":"2026-10-15","status":"proposed-source-candidates",
        "generations":len(records),"source_unchanged":all(s["unchanged"] for s in sources),"sources":sources,
        "tool_original_copies_equal":all(r["copy_equal"] for r in records),"exports":exports,"review_sheet":"review-sheet.png",
        "font_reference":{"path":str(FONT_PATH),"sha256":digest(FONT_PATH)},"review_previews_only":True,
        "production_sources_reencoded":False,"runtime_ready":False,"exact_palette_verified":False,
        "initial_prompt_central76_safe_crop":False,"proposed_crop":[.5,.5,1.0],
        "remaining":["Inspect review-sheet.png and record visual findings.","Integrating owner decides registry/import/crop acceptance."]}
    save_json(PACKAGE/"verification.json",verification)
    if visual_review:
        verification["visual_review"]=visual_review
        verification["remaining"]=["Integrating owner decides registry/import/crop acceptance."]
        save_json(PACKAGE/"verification.json",verification)
    refresh_manifest()
    print(json.dumps({"source_unchanged":verification["source_unchanged"],"generations":len(records),"exports":len(exports),"sheet":str(PACKAGE/"review-sheet.png")}))

def refresh_manifest():
    manifest={p.relative_to(PACKAGE).as_posix():digest(p) for p in sorted(PACKAGE.rglob("*")) if p.is_file() and p.name!="manifest-sha256.json"}
    save_json(PACKAGE/"manifest-sha256.json",manifest)

if __name__=="__main__":
    main()
