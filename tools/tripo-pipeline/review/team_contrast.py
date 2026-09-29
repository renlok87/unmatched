"""Team colour in grey and in deuteranopia on the P1.7 control scene (W4-B, offline, no editor).

    python tools/tripo-pipeline/review/team_contrast.py --run <cs dir>/<tag> [--run ...] --out <json>
        [--noise <runA> <runB>] [--split-from <run>] [--inputs-dir <dir>] [--derive-dir <dir>]
    python tools/tripo-pipeline/review/team_contrast.py --from-inputs <dir> --out <json>

For every subject that has a team-swap frame (control_scene.py: p17-team-alt-k2-1p6-<name>, and in the w4b asset set
p17-team-prop-k2-1p6-<name> with the value-split palette proposal) the two team frames of the subject are compared
inside its silhouette at K2 1.6x (mask-k2-1p6-<name> against mask-k2-1p6-empty-<name>, per-pixel mean |dRGB| > 12, the
threshold of control_scene_analyze.py; isolated noise pixels outside the 1..99th percentile box of the silhouette + 16 px
are dropped). The derivatives are the fixed ones of QA-010 (tools/art/qa010/qa010lib/color.py,
the same code as `qa010.py derive`): grey = Rec.709 Y' of the sRGB frame, deuteranopia = Machado 2009 severity 1.0 in
linear light. Metrics per pair: mean and p90 of |dY'| over the silhouette, the share of silhouette pixels with
|dY'| >= 8 (a visible step in grey, proposal), dY' of the means; in deuteranopia the mean CIE76 dE (D65 Lab) and the same
|dY'| statistics; with normal vision the mean dE for reference.

Regions (W4-B review fix, 2026-09-29): the silhouette is split into "figure" (pixels where the figure itself is visible:
mask-k2-1p6-<name> against the base-only frame mask-k2-1p6-base-<name>, mean |dRGB| > 12) and "base" (the rest of the
silhouette: the base and its team band). Without that split a big change of the base band hides an unchanged figure
(Merlin before the fix: 88 % of the deuteranopia dE sum came from the base band). A run without base-only frames (shot
before the split existed) takes the figure pixels of --split-from (same meshes, cells and camera), named in the output.
--noise <A> <B>: the same metrics between the same-team frames of two repeated runs (main vs main, team-alt vs team-alt)
= the run-to-run floor of the live viewport (temporal AA); a team difference is only read as one when it is well above.

--inputs-dir writes what the numbers are computed from, lossless and small enough for git: per run and subject the
frames cropped to one box per subject (the union of the silhouette boxes of all runs + 24 px) and the ROI masks
(silhouette, figure, base) as 0/255 PNGs, plus inputs.json (crop box, teams, source frame names and SHA-256).
--from-inputs recomputes team-contrast.json from such a directory alone (the per-pixel colour transforms do not depend
on the crop, so the numbers are identical). --derive-dir writes colour / grey / deuteranopia crops for the evidence.
Numbers are measurements of EDITOR frames, not K1 acceptance (QA-010 needs packaged frames).
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools" / "art" / "qa010"))
from qa010lib import color  # noqa: E402

MASK_T = 12.0
VISIBLE_DY = 8.0
MARGIN = 24
FRAME_SETS = ("main", "team-alt", "team-prop")
REGIONS = ("figure", "base")


def load_u8(path):
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.uint8)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def diff_mask(a_path, b_path):
    return np.abs(load_u8(a_path).astype(np.int16) - load_u8(b_path).astype(np.int16)).mean(axis=2) > MASK_T


def silhouette(run, name):
    fig = run / ("p17-mask-k2-1p6-%s-ue-editor.png" % name)
    empty = run / ("p17-mask-k2-1p6-empty-%s-ue-editor.png" % name)
    if not (fig.exists() and empty.exists()):
        return None
    m = diff_mask(fig, empty)
    if m.any():
        # a few isolated pixels elsewhere differ between the two captures (temporal AA noise of the live viewport,
        # ~1.5 % of the silhouette): keep the pixels inside the 1st..99th percentile box of the silhouette + 16 px
        ys, xs = np.nonzero(m)
        x0, x1 = np.percentile(xs, [1, 99])
        y0, y1 = np.percentile(ys, [1, 99])
        box = np.zeros_like(m)
        box[max(int(y0) - 16, 0):int(y1) + 17, max(int(x0) - 16, 0):int(x1) + 17] = True
        m &= box
    return m


def figure_pixels(run, name):
    """Pixels where the figure is visible (figure + base frame vs base-only frame), None without a base-only frame."""
    fig = run / ("p17-mask-k2-1p6-%s-ue-editor.png" % name)
    base = run / ("p17-mask-k2-1p6-base-%s-ue-editor.png" % name)
    if not (fig.exists() and base.exists()):
        return None
    return diff_mask(fig, base)


def pair_planes(a, b):
    """Per-pixel planes of a frame pair, computed once for every region: grey Y', deuteranopia Y', CIE Lab (normal
    vision and deuteranopia)."""
    da, db = color.deuteranopia(a), color.deuteranopia(b)
    lab = lambda img: color.linear_to_lab(color.u8_to_linear(img))  # noqa: E731
    return {"dy": np.abs(color.luma_u8(a) - color.luma_u8(b)), "ga": color.luma_u8(a), "gb": color.luma_u8(b),
            "ddy": np.abs(color.luma_u8(da) - color.luma_u8(db)),
            "de_deut": np.linalg.norm(lab(da) - lab(db), axis=-1), "de_norm": np.linalg.norm(lab(a) - lab(b), axis=-1)}


def pair_metrics(a, b, roi, planes=None):
    if not roi.any():
        return {"silhouette_px": 0}
    pl = planes or pair_planes(a, b)
    dy, ga, gb, ddy = pl["dy"][roi], pl["ga"][roi], pl["gb"][roi], pl["ddy"][roi]
    de_deut, de_norm = pl["de_deut"][roi], pl["de_norm"][roi]
    return {"silhouette_px": int(roi.sum()),
            "grey": {"mean_abs_dY": round(float(dy.mean()), 3), "p90_abs_dY": round(float(np.percentile(dy, 90)), 3),
                     "share_abs_dY_ge_8": round(float((dy >= VISIBLE_DY).mean()), 4),
                     "sum_abs_dY": round(float(dy.sum()), 1),
                     "dY_of_means": round(float(ga.mean() - gb.mean()), 3)},
            "deuteranopia": {"mean_dE76": round(float(de_deut.mean()), 3),
                             "p90_dE76": round(float(np.percentile(de_deut, 90)), 3),
                             "sum_dE76": round(float(de_deut.sum()), 1),
                             "mean_abs_dY": round(float(ddy.mean()), 3),
                             "share_abs_dY_ge_8": round(float((ddy >= VISIBLE_DY).mean()), 4)},
            "normal_vision": {"mean_dE76": round(float(de_norm.mean()), 3)}}


def region_metrics(a, b, rois):
    """pair_metrics over the silhouette plus its figure / base regions (when the split exists) and the share of the
    summed differences that falls on the base."""
    planes = pair_planes(a, b)
    out = pair_metrics(a, b, rois["silhouette"], planes)
    if "figure" in rois:
        out["regions"] = {r: pair_metrics(a, b, rois[r], planes) for r in REGIONS}
        tot_de = sum(out["regions"][r].get("deuteranopia", {}).get("sum_dE76", 0.0) for r in REGIONS)
        tot_dy = sum(out["regions"][r].get("grey", {}).get("sum_abs_dY", 0.0) for r in REGIONS)
        out["base_share_of_sum"] = {
            "deuteranopia_dE76": round(out["regions"]["base"].get("deuteranopia", {}).get("sum_dE76", 0.0) / tot_de, 4)
            if tot_de else None,
            "grey_abs_dY": round(out["regions"]["base"].get("grey", {}).get("sum_abs_dY", 0.0) / tot_dy, 4)
            if tot_dy else None}
    return out


def crop_box(roi):
    ys, xs = np.nonzero(roi)
    h, w = roi.shape
    return (max(int(xs.min()) - MARGIN, 0), max(int(ys.min()) - MARGIN, 0), min(int(xs.max()) + MARGIN + 1, w),
            min(int(ys.max()) + MARGIN + 1, h))


def union_box(boxes):
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def team_of(report, name, frame_set):
    """Team shown in a frame set (main / team-alt / team-prop) of a subject."""
    default = (report.get("subject_teams") or {}).get(name)
    if default is None:  # reports without subject_teams: the defaults of control_scene.py per asset set
        if report.get("asset_set") == "w4b":
            default = {"medusa": "Silver", "harpy2": "Silver", "arthur": "Gold", "merlin": "Gold"}.get(name)
        else:  # t31: the team is named by the MI of the main and the swapped frames
            default = {"medusa": "Blue", "harpy2": "Silver", "arthur": "Gold", "merlin": "Gold"}.get(name)
    other = {"Gold": "Silver", "Silver": "Gold", "Blue": "Red", "Red": "Blue"}.get(default)
    return {"main": default, "team-alt": other, "team-prop": "Silver (value-split proposal)"}[frame_set]


# ------------------------------------------------------------------ loading (full frames or committed inputs)

def load_run(run, split_from=None):
    """{"meta": {...}, "subjects": {name: {"img", "rois", "teams", "source", "split_source"}}} of a control scene run."""
    run = Path(run)
    report = json.loads((run / "control-scene-report.json").read_text(encoding="utf-8"))
    meta = {"run": run.as_posix(), "tag": report.get("tag"), "asset_set": report.get("asset_set", "t31"),
            "team_proposal": report.get("team_proposal")}
    subjects = {}
    for alt in sorted(run.glob("p17-team-alt-k2-1p6-*-ue-editor.png")):
        name = alt.name[len("p17-team-alt-k2-1p6-"):-len("-ue-editor.png")]
        roi = silhouette(run, name)
        if roi is None or not roi.any():
            continue
        paths = {"main": run / ("p17-k2-1p6-%s-ue-editor.png" % name), "team-alt": alt}
        prop = run / ("p17-team-prop-k2-1p6-%s-ue-editor.png" % name)
        if prop.exists():
            paths["team-prop"] = prop
        fig_px, split_src = figure_pixels(run, name), run
        if fig_px is None and split_from is not None:
            fig_px, split_src = figure_pixels(Path(split_from), name), Path(split_from)
        rois = {"silhouette": roi}
        if fig_px is not None:
            rois["figure"] = roi & fig_px
            rois["base"] = roi & ~fig_px
        masks = {k: run / ("p17-mask-k2-1p6-%s%s-ue-editor.png" % (p, name))
                 for k, p in (("mask", ""), ("mask-empty", "empty-"), ("mask-base", "base-"))}
        source = {k: {"file": p.name, "sha256": sha256(p)} for k, p in list(paths.items()) + list(masks.items())
                  if p.exists()}
        subjects[name] = {"img": {k: load_u8(p) for k, p in paths.items()}, "rois": rois,
                          "teams": {k: team_of(report, name, k) for k in paths}, "source": source,
                          "split_source": (None if fig_px is None else
                                           ("own base-only frame" if split_src == run else
                                            "figure pixels of run %s (same meshes, cells, camera)" % Path(split_src).name))}
    return {"meta": meta, "subjects": subjects}


def load_inputs(directory):
    """The same structure from a --inputs-dir directory (crops + ROI masks)."""
    directory = Path(directory)
    index = json.loads((directory / "inputs.json").read_text(encoding="utf-8"))
    runs = []
    for tag in index["runs"]:
        r = index["run_meta"][tag]
        subjects = {}
        for name, sub in sorted(index["subjects"][tag].items()):
            d = directory / tag / name
            rois = {k: np.asarray(Image.open(d / ("roi-%s.png" % k)).convert("L")) > 127
                    for k in ("silhouette",) + (REGIONS if sub["split_source"] else ())}
            subjects[name] = {"img": {k: load_u8(d / ("%s.png" % k)) for k in sub["teams"]}, "rois": rois,
                              "teams": sub["teams"], "source": sub["source"], "split_source": sub["split_source"],
                              "crop_box_px": sub["crop_box_px"]}
        runs.append({"meta": dict(r, inputs=(Path(directory.name) / tag).as_posix()), "subjects": subjects})
    noise = index.get("noise")
    return runs, noise


def write_inputs(directory, runs, noise_tags):
    """Crops (one box per subject across all runs) and ROI masks of every run; inputs.json."""
    directory = Path(directory)
    boxes = {}
    for run in runs:
        for name, sub in run["subjects"].items():
            boxes.setdefault(name, []).append(crop_box(sub["rois"]["silhouette"]))
    boxes = {n: union_box(b) for n, b in boxes.items()}
    index = {"schema": "unmatched.w4b-team-contrast-inputs/1", "runs": [], "run_meta": {}, "subjects": {},
             "noise": list(noise_tags) if noise_tags else None,
             "note": "lossless crops of the EDITOR frames (P1.7 control scene) and the ROI masks team_contrast.py "
                     "computed on the full frames; `team_contrast.py --from-inputs <this dir>` recomputes the numbers"}
    for run in runs:
        tag = run["meta"]["tag"]
        index["runs"].append(tag)
        index["run_meta"][tag] = {k: v for k, v in run["meta"].items() if k != "run"}
        index["subjects"][tag] = {}
        for name, sub in sorted(run["subjects"].items()):
            box = boxes[name]
            d = directory / tag / name
            d.mkdir(parents=True, exist_ok=True)
            for k, img in sub["img"].items():
                Image.fromarray(img).crop(box).save(d / ("%s.png" % k), optimize=True)
            for k, m in sub["rois"].items():
                Image.fromarray((m * 255).astype(np.uint8), "L").crop(box).save(d / ("roi-%s.png" % k), optimize=True)
            index["subjects"][tag][name] = {"crop_box_px": list(box), "teams": sub["teams"], "source": sub["source"],
                                            "split_source": sub["split_source"]}
    (directory / "inputs.json").write_text(json.dumps(index, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
                                           encoding="utf-8", newline="\n")
    return boxes


# ------------------------------------------------------------------ analysis

def analyse(run, derive_dir=None, box=None):
    out = dict(run["meta"], subjects={})
    for name, sub in sorted(run["subjects"].items()):
        img, rois, teams = sub["img"], sub["rois"], sub["teams"]
        entry = {"frames": {k: sub["source"][k]["file"] for k in img}, "teams": teams, "split_source": sub["split_source"],
                 "source_frames_sha256": {k: v["sha256"] for k, v in sorted(sub["source"].items())},
                 "c11_pair": dict(region_metrics(img["main"], img["team-alt"], rois),
                                  compared=[teams["main"], teams["team-alt"]])}
        if "team-prop" in img:
            gold = "main" if teams["main"] == "Gold" else "team-alt"
            entry["proposal_pair"] = dict(region_metrics(img[gold], img["team-prop"], rois),
                                          compared=["Gold", teams["team-prop"]])
        if "crop_box_px" in sub:
            entry["crop_box_px"] = sub["crop_box_px"]
        elif box and name in box:
            entry["crop_box_px"] = list(box[name])
        if derive_dir:
            # from inputs: already cropped; from full frames: the subject box of --inputs-dir or the silhouette box
            b = None if "crop_box_px" in sub else (tuple(box[name]) if box and name in box else crop_box(rois["silhouette"]))
            d = Path(derive_dir)
            d.mkdir(parents=True, exist_ok=True)
            for k, a in img.items():
                stem = "%s-%s-%s" % (out["tag"], name, k)
                im = Image.fromarray(a) if b is None else Image.fromarray(a).crop(b)
                im.save(d / (stem + ".png"))
                g = Image.fromarray(color.grayscale(a))
                (g if b is None else g.crop(b)).save(d / (stem + ".gray.png"))
                t = Image.fromarray(color.deuteranopia(a))
                (t if b is None else t.crop(b)).save(d / (stem + ".deuteranopia.png"))
        out["subjects"][name] = entry
    return out


def noise_floor(run_a, run_b):
    """Same-team frames of two repeated runs (main vs main, team-alt vs team-alt) inside run A's regions."""
    out = {"runs": [run_a["meta"]["tag"], run_b["meta"]["tag"]], "subjects": {}}
    for name, sa in sorted(run_a["subjects"].items()):
        sb = run_b["subjects"].get(name)
        if sb is None:
            continue
        out["subjects"][name] = {k: region_metrics(sa["img"][k], sb["img"][k], sa["rois"])
                                 for k in ("main", "team-alt") if k in sa["img"] and k in sb["img"]}
    return out


def summary_line(tag, name, e):
    c = e["c11_pair"]
    line = "%-9s %-7s %s: grey %5.2f (fig %s) deut dE %5.2f (fig %s)" % (
        tag, name, "/".join(c["compared"]), c["grey"]["mean_abs_dY"],
        "%5.2f" % c["regions"]["figure"]["grey"]["mean_abs_dY"] if "regions" in c else "  -  ",
        c["deuteranopia"]["mean_dE76"],
        "%5.2f" % c["regions"]["figure"]["deuteranopia"]["mean_dE76"] if "regions" in c else "  -  ")
    if "proposal_pair" in e:
        p = e["proposal_pair"]
        line += " | prop grey %5.2f (fig %s)" % (p["grey"]["mean_abs_dY"], "%5.2f" % p["regions"]["figure"]["grey"][
            "mean_abs_dY"] if "regions" in p else "-")
    return line


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="append", default=[], help="control scene run dir (…/<tag>); repeatable")
    ap.add_argument("--from-inputs", default=None, help="recompute from an --inputs-dir directory")
    ap.add_argument("--out", required=True)
    ap.add_argument("--noise", nargs=2, default=None, metavar=("RUN_A", "RUN_B"),
                    help="two repeated runs (dirs, or tags with --from-inputs) for the same-team noise floor")
    ap.add_argument("--split-from", default=None, help="run whose base-only frames split runs that have none")
    ap.add_argument("--inputs-dir", default=None)
    ap.add_argument("--derive-dir", default=None)
    a = ap.parse_args()
    boxes = None
    if a.from_inputs:
        runs, noise_tags = load_inputs(a.from_inputs)
        noise_tags = a.noise or noise_tags
    else:
        if not a.run:
            ap.error("--run or --from-inputs is required")
        runs = [load_run(r, a.split_from) for r in a.run]
        noise_tags = None
        if a.noise:
            by_dir = {Path(r["meta"]["run"]).resolve(): r for r in runs}
            for n in a.noise:
                if Path(n).resolve() not in by_dir:
                    runs.append(load_run(n, a.split_from))
                    by_dir[Path(n).resolve()] = runs[-1]
            noise_tags = [by_dir[Path(n).resolve()]["meta"]["tag"] for n in a.noise]
        if a.inputs_dir:
            boxes = write_inputs(a.inputs_dir, runs, noise_tags)
    by_tag = {r["meta"]["tag"]: r for r in runs}
    result = {"schema": "unmatched.w4b-team-contrast/2",
              "method": {"roi": "silhouette at K2 1.6x: mask frame vs empty frame, mean |dRGB| > %.0f" % MASK_T,
                         "regions": "figure = silhouette pixels where the figure is visible (mask frame vs base-only "
                                    "frame, mean |dRGB| > %.0f); base = the rest of the silhouette" % MASK_T,
                         "grey": "Rec.709 Y' of the sRGB frame (qa010lib.color.luma_u8 / grayscale)",
                         "deuteranopia": "Machado 2009 severity 1.0 in linear light (qa010lib.color.deuteranopia)",
                         "visible_step": "|dY'| >= %.0f (proposal)" % VISIBLE_DY,
                         "noise": "same-team frames of two repeated runs (--noise)",
                         "status": "measured on EDITOR frames; not K1 acceptance (QA-010 needs packaged frames)"},
              "inputs": (Path(a.from_inputs).name if a.from_inputs else
                         (Path(a.inputs_dir).name if a.inputs_dir else None)),
              "runs": [analyse(r, a.derive_dir, boxes) for r in runs],
              "noise": noise_floor(by_tag[noise_tags[0]], by_tag[noise_tags[1]]) if noise_tags else None}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(result, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8",
                           newline="\n")
    for run in result["runs"]:
        for name, e in sorted(run["subjects"].items()):
            print(summary_line(run["tag"], name, e))
    if result["noise"]:
        for name, n in sorted(result["noise"]["subjects"].items()):
            m = n["main"]
            print("noise %s %-7s grey %5.2f deut dE %5.2f%s" % (
                "/".join(result["noise"]["runs"]), name, m["grey"]["mean_abs_dY"], m["deuteranopia"]["mean_dE76"],
                " | fig grey %5.2f dE %5.2f" % (m["regions"]["figure"]["grey"]["mean_abs_dY"],
                                                m["regions"]["figure"]["deuteranopia"]["mean_dE76"])
                if "regions" in m else ""))


if __name__ == "__main__":
    main()
