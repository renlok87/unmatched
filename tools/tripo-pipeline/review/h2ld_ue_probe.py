"""LD-<hero>-ue look-dev probe: MI-parameter variants on the same Cobble scene, zone medians with fixed labels.

    python tools/tripo-pipeline/review/h2ld_ue_probe.py --run-dir <H2LD run> --labels-dir <raw dir of a full
        h2ld_ue_lookdev.py pass> --variants <json> --out <dir> --tag p1 [--views front,side,back]

Same scene and setup as review/h2ld_ue_lookdev.py (P1.7 Cobble control level, cobble-probe light, EV100 1.3, High).
Each variant is a transient MaterialInstanceDynamic on the figure ({"name", "parent": <MI asset>, "scalars",
"vectors"}); the frames are measured with the zone labels of an earlier full pass (<view>-labels-ids.npy: same camera,
same geometry, same yaw), against the concept medians and the exposure factor k of that pass. Nothing is saved; the
previous level is re-opened. Diagnostic only (which knob moves which zone); the chosen values go into the hero LUT
config / import profile and are verified by a new full pass.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
import h2_ue_review as R  # noqa: E402
import h2ld_ue_lookdev as L  # noqa: E402
from ue_live import Ue  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--labels-dir", required=True)
    ap.add_argument("--metrics", required=True, help="metrics JSON of the full pass (k, concept via report)")
    ap.add_argument("--report", required=True, help="report JSON of the full pass (concept medians)")
    ap.add_argument("--variants", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tag", default="p1")
    ap.add_argument("--views", default="front")
    ap.add_argument("--lookdev-profile", default=None,
                    help="re-measure the concept with the look-dev profile boxes (+ --extra-concept-boxes) instead of "
                         "taking the concept medians of the full-pass report")
    ap.add_argument("--extra-concept-boxes", default=None, help="JSON list [{view, zone, box, filter}]")
    ap.add_argument("--avg-last", type=int, default=3, help="measure the mean of the last N settle grabs")
    a = ap.parse_args()
    run = Path(a.run_dir).resolve()
    ue_rep = json.loads((run / "reports/ue-import-report.json").read_text(encoding="utf-8"))
    names = ue_rep["destination"]["assets"]
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    profile = json.loads((REPO / manifest["config"]["build_profile"]).read_text(encoding="utf-8"))
    ue_inputs = json.loads((REPO / profile["candidate"]["dir"] / profile["candidate"]["extra_reports"]["ue_inputs"])
                           .read_text(encoding="utf-8"))
    legend = ue_inputs["zone_legend"]
    full = json.loads(Path(a.report).read_text(encoding="utf-8"))
    if a.lookdev_profile:
        extra = json.loads(a.extra_concept_boxes) if a.extra_concept_boxes else []
        full["concept"] = L.concept_medians(json.loads(Path(a.lookdev_profile).read_text(encoding="utf-8")),
                                            REPO / "art/imagegen/hero-quality-v1/merlin", "merlin", extra)
    k = json.loads(Path(a.metrics).read_text(encoding="utf-8"))["k"]
    variants = json.loads(Path(a.variants).read_text(encoding="utf-8"))
    views = [v for v in a.views.split(",") if v]
    labels = {v: np.load(Path(a.labels_dir) / ("%s-labels-ids.npy" % v)) for v in views}
    light = json.loads(R.PROFILES_JSON.read_text(encoding="utf-8"))["lightProfiles"][R.LIGHT_PROFILE]
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    ue = Ue()
    sh = L.Shots(ue, out, out, a.tag, "Merlin")
    vs = L.views()

    def cv(v):  # concept view a UE view is measured against (torso and close-ups -> front)
        return vs[v].get("concept", v)
    original = ue.call("scene", "get_current_level", record=False)
    if ue.call("asset", "is_dirty", {"asset_path": original}, record=False) or original.split(".")[0] == R.LEVEL:
        raise SystemExit("editor level busy or dirty: %s" % original)
    sg_before = {n: R.cvar_value(ue, n) for n in R.SG}
    res = {"k": k, "tag": a.tag, "variants": {}, "concept": full["concept"], "avg_last": a.avg_last}
    try:
        ue.call("scene", "load_level", {"level_path": R.LEVEL})
        time.sleep(3.0)
        sh.task("h2_review_ue.py", "setup", timeout=600, level=R.LEVEL, hide_label_prefixes=["P17 "],
                keep_labels=[R.EXPOSURE_LABEL],
                lights={"off": [R.FILL_LABEL],
                        "key": {"label": R.KEY_LABEL, "intensity_lux": light["directional"]["intensity"],
                                "shadow_distance_uu": light["directional"]["shadow"]["distanceUU"],
                                "cascades": light["directional"]["shadow"]["cascades"],
                                "contact_shadow_length": light["directional"]["shadow"]["contactShadowLength"],
                                "rotation_pitch_yaw_roll": R.KEY_ROTATION}},
                sky={"label": L.L_SKY, "cubemap": light["sky"]["cubemap"], "intensity": light["sky"]["intensity"],
                     "lower_hemisphere_is_black": light["sky"]["lowerHemisphereIsBlack"],
                     "color_linear": light["sky"]["colorLinear"]},
                figure={"label": L.L_FIG, "kind": "skeletal", "asset": names["skeletal"], "location": R.CELL, "yaw": 0.0},
                base={"label": L.L_BASE, "kind": "static", "asset": names["base"], "location": R.CELL, "yaw": 0.0})
        for n in R.SG:
            ue.console("%s 2" % n)
        for flag in R.SHOW_FLAGS_OFF:
            ue.console("ShowFlag.%s 0" % flag)
        sh.task("control_scene_ue.py", "set", changes=[{"label": L.L_BASE, "materials": {"0": names["base_instance"]}},
                                                       {"label": L.L_FIG, "yaw": 90.0}, {"label": L.L_BASE, "yaw": 90.0}])
        time.sleep(10.0)
        for var in variants:
            if var.get("mesh"):
                sh.task("h2ld_lookdev_ue.py", "swap_mesh", label=L.L_FIG, mesh=var["mesh"])
            sh.task("h2ld_lookdev_ue.py", "mid", label=L.L_FIG, slot=0, parent=var["parent"],
                    scalars=var.get("scalars"), vectors=var.get("vectors"))
            for cmd in var.get("console") or []:
                ue.console(cmd)  # e.g. r.ExposureOffset (diagnostic exposure shift, reset by console_after)
            time.sleep(2.5)
            per_view, stats_v = {}, {}
            for v in views:
                name = "%s-%s" % (v, var["name"])
                sh.shot(name, vs[v], {"variant": var}, keep_jpg=bool(var.get("jpg")), avg_last=a.avg_last)
                stats_v[v] = L.zone_stats(sh.images[name], labels[v], legend)
            kv = k
            if var.get("own_k"):
                rr = [full["concept"][cv(v)][z]["luma_Y"] / max(s_["luma_Y"], 1e-6) for v in views
                      for z, s_ in stats_v[v].items() if "luma_Y" in s_ and "luma_Y" in (full["concept"][cv(v)].get(z) or {})
                      and z != "base"]
                kv = float(np.median(rr))
            for v in views:
                per_view[v] = L.compare(stats_v[v], full["concept"][cv(v)], kv)
            for cmd in var.get("console_after") or []:
                ue.console(cmd)
            res["variants"][var["name"]] = {"variant": var, "k": kv, "per_view": per_view,
                                            "summary": L.summarise(per_view)}
            s = res["variants"][var["name"]]["summary"]
            print(var["name"], " ".join("%s:%s/%s/%s" % (z[:6], s[z].get("luma_ratio"), s[z].get("hue_delta_deg"),
                                                         s[z].get("sat_delta")) for z in sorted(s) if s[z].get("views")),
                  flush=True)
            if var.get("mesh"):
                sh.task("h2ld_lookdev_ue.py", "swap_mesh", label=L.L_FIG, mesh=names["skeletal"])
    finally:
        try:
            sh.task("control_scene_ue.py", "cleanup", labels=[L.L_FIG, L.L_BASE, L.L_SKY, L.L_CAM])
        except Exception as exc:  # noqa: BLE001
            res["cleanup_error"] = str(exc)
        for n, v in sg_before.items():
            if v is not None:
                ue.console("%s %s" % (n, v))
        for flag in R.SHOW_FLAGS_OFF:
            ue.console("ShowFlag.%s 2" % flag)
        ue.console("r.ExposureOffset 0")
        ue.call("scene", "load_level", {"level_path": original.split(".")[0]})
        time.sleep(2.0)
        res["restored_level"] = ue.call("scene", "get_current_level", record=False)
        res["restored_level_dirty"] = ue.call("asset", "is_dirty", {"asset_path": res["restored_level"]}, record=False)
        (out / ("probe-%s.json" % a.tag)).write_text(json.dumps(res, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
                                                    encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
