"""Host driver: editor review frames of a pipeline candidate in the LIVE UnrealEditor via unreal_mcp.py.

    python tools/tripo-pipeline/review/capture_ue_review.py --run-dir <run> --out <dir>
        [--level /Game/ArtTests/ART004/L_ART004_MedusaAnimationReview]
        [--compare-skeletal /Game/ArtPreview/Medusa/Meshes/SK_Medusa_FaceNeck_v2Candidate]
        [--compare-base /Game/ArtPreview/Medusa/Meshes/SM_Medusa_Base_v2Candidate]

What it does (only in memory, nothing is saved):
  1. refuses if the currently open level has unsaved changes;
  2. loads the review level, places the candidate (skeletal + base, its default
     team MI) and, for comparison, an existing asset (read only) on two free board
     cells, and captures editor viewport frames with EditorAppToolset.CaptureViewport;
  3. removes the temporary actors and re-opens the level that was open before.
Frames are EDITOR frames (level-editor viewport, editor FOV, review-level light):
not the packaged game, no HUD, no boardState, not art acceptance.

Camera layout: front views look from +Y, i.e. it assumes meshes that face +Y (the T4 candidate,
production and v2). A UM_FBX_v1 candidate faces +X: pass --candidate-yaw 90 so that it turns to +Y
for these views (the actor is rotated, the asset is not). For the facing measurement itself use
capture_ue_axes.py.
"""

import argparse
import base64
import json
import math
import sys
import time
import urllib.request
from pathlib import Path

URL = "http://127.0.0.1:8123/mcp"
TS = {"asset": "editor_toolset.toolsets.asset.AssetTools", "scene": "editor_toolset.toolsets.scene.SceneTools",
      "actor": "editor_toolset.toolsets.actor.ActorTools", "app": "EditorToolset.EditorAppToolset"}
NOANN = {"gridSpacing": 0, "gridExtent": 0, "gridHeight": 0, "maxLabelDistance": 0, "classFilter": None, "maxLabels": 0}


class Mcp:
    """Minimal MCP HTTP client (same protocol as unreal_mcp.py, which truncates stdout at 200k chars and
    therefore cannot carry CaptureViewport images). One session for the whole review."""

    def __init__(self):
        self.session, self.next_id = None, 0
        self._rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                                 "clientInfo": {"name": "tripo-pipeline-review", "version": "1"}})
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _post(self, body):
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        req = urllib.request.Request(URL, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=900) as resp:
            self.session = resp.headers.get("Mcp-Session-Id") or self.session
            raw = resp.read().decode("utf-8")
        if not raw.strip():
            return None
        if raw.lstrip().startswith("{"):
            return json.loads(raw)
        data = [line[5:].strip() for line in raw.splitlines() if line.startswith("data:")]
        return json.loads(data[-1]) if data else None

    def _rpc(self, method, params):
        self.next_id += 1
        return self._post({"jsonrpc": "2.0", "id": self.next_id, "method": method, "params": params})

    def call(self, toolset, tool, args=None):
        res = self._rpc("tools/call", {"name": "call_tool", "arguments": {
            "toolset_name": TS[toolset], "tool_name": tool, "arguments": args or {}}}) or {}
        if res.get("error"):
            raise RuntimeError("%s.%s: %s" % (toolset, tool, res["error"]))
        result = res.get("result") or {}
        texts = [c.get("text", "") for c in result.get("content", [])]
        if result.get("isError"):
            raise RuntimeError("%s.%s: %s" % (toolset, tool, " ".join(texts)[:800]))
        payload = result.get("structuredContent")
        if payload is None:
            payload = json.loads(texts[0]) if texts and texts[0].strip().startswith("{") else {"returnValue": None}
        return payload.get("returnValue") if isinstance(payload, dict) else payload


_MCP = None


def call(toolset, tool, args=None):
    global _MCP
    if _MCP is None:
        _MCP = Mcp()
    return _MCP.call(toolset, tool, args)


def xf(x, y, z, yaw=0.0):
    return {"location": {"x": x, "y": y, "z": z}, "rotation": {"pitch": 0, "yaw": yaw, "roll": 0},
            "scale": {"x": 1, "y": 1, "z": 1}}


def look(eye, target):
    dx, dy, dz = (target[i] - eye[i] for i in range(3))
    return {"location": {"x": eye[0], "y": eye[1], "z": eye[2]},
            "rotation": {"pitch": math.degrees(math.atan2(dz, math.hypot(dx, dy))),
                         "yaw": math.degrees(math.atan2(dy, dx)), "roll": 0}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--level", default="/Game/ArtTests/ART004/L_ART004_MedusaAnimationReview")
    ap.add_argument("--compare-skeletal", default="/Game/ArtPreview/Medusa/Meshes/SK_Medusa_FaceNeck_v2Candidate")
    ap.add_argument("--compare-base", default="/Game/ArtPreview/Medusa/Meshes/SM_Medusa_Base_v2Candidate")
    ap.add_argument("--candidate-yaw", type=float, default=0.0,
                    help="actor yaw of the candidate; 90 turns a +X-facing (UM_FBX_v1) mesh to +Y for this layout")
    ap.add_argument("--compare-yaw", type=float, default=0.0)
    args = ap.parse_args()
    run = Path(args.run_dir).resolve()
    report = json.loads((run / "reports/ue-import-report.json").read_text(encoding="utf-8"))
    names = report["destination"]["assets"]
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    original_level = call("scene", "get_current_level")
    if call("asset", "is_dirty", {"asset_path": original_level}):
        raise SystemExit("open level %s has unsaved changes; refusing to switch levels" % original_level)
    y0 = 250.0  # free board row of the review level (no figures between the camera and this row)
    slots = {"compare": -200.0, "candidate": -100.0}
    placed = []
    meta = {"kind": "editor viewport frames (live UnrealEditor via unreal-mcp CaptureViewport); not packaged, "
                    "no HUD/boardState, not art acceptance",
            "level": args.level, "original_level": original_level,
            "candidate": {"skeletal": names["skeletal"], "base": names["base"]},
            "compare": {"skeletal": args.compare_skeletal, "base": args.compare_base},
            "layout": "front views: compare (left, x=%g) / candidate (right, x=%g), row y=%g, actor yaw in "
                      "actor_yaw (layout expects mesh front +Y); rear views mirror left/right" % (slots["compare"], slots["candidate"], y0),
            "frames": {}}
    try:
        call("scene", "load_level", {"level_path": args.level})
        time.sleep(2.0)
        yaws = {"candidate": args.candidate_yaw, "compare": args.compare_yaw}
        meta["actor_yaw"] = yaws
        for tag, sk, base in (("candidate", names["skeletal"], names["base"]),
                              ("compare", args.compare_skeletal, args.compare_base)):
            x = slots[tag]
            for kind, asset in (("skeletal", sk), ("base", base)):
                label = "T4 pipeline review %s %s - temporary" % (tag, kind)
                actor = call("scene", "add_to_scene_from_asset", {"asset_path": asset, "name": label,
                                                                  "xform": xf(x, y0, 0, yaws[tag]), "parent": None,
                                                                  "snap_to_ground": False})
                call("actor", "set_label", {"actor": actor, "label": label})
                placed.append(actor)
        time.sleep(3.0)  # shader/texture streaming
        cx = sum(slots.values()) / 2
        views = {
            "ue-front-pair": look((cx, y0 + 95, 34), (cx, y0, 28)),
            "ue-rear-pair": look((cx, y0 - 95, 34), (cx, y0, 28)),
        }
        for tag, x in slots.items():
            views["ue-front-face-%s" % tag] = look((x - 1, y0 + 24, 45), (x - 1, y0, 44))
            views["ue-front-arms-%s" % tag] = look((x, y0 + 38, 31), (x, y0, 30))
            views["ue-rear-bow-arm-%s" % tag] = look((x + 9, y0 - 26, 31), (x + 9, y0, 30))
            views["ue-rear-neck-%s" % tag] = look((x - 1, y0 - 26, 41), (x - 1, y0, 41))
        for name, cam in views.items():
            call("app", "CaptureViewport", {"captureTransform": cam, "annotations": NOANN, "bShowUI": False})
            time.sleep(0.4)  # first capture after a camera jump can be stale; keep the second
            res = call("app", "CaptureViewport", {"captureTransform": cam, "annotations": NOANN, "bShowUI": False})
            raw = base64.b64decode(res["image"]["data"])
            path = out / ("%s.png" % name)
            path.write_bytes(raw)
            meta["frames"][path.name] = {"camera": cam, **{k: v for k, v in res.items() if k != "image"}}
            print(path.name, len(raw))
    finally:
        for actor in placed:
            try:
                call("scene", "remove_from_scene", {"actor": actor})
            except RuntimeError as exc:
                print("remove failed:", exc)
        call("scene", "load_level", {"level_path": original_level})
        time.sleep(2.0)
        meta["restored_level"] = call("scene", "get_current_level")
        meta["restored_level_dirty"] = call("asset", "is_dirty", {"asset_path": meta["restored_level"]})
        meta["review_level_dirty_after_reload"] = call("asset", "is_dirty", {"asset_path": args.level})
        (out / "ue-frames.json").write_text(json.dumps(meta, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print("restored:", meta["restored_level"], "dirty:", meta["restored_level_dirty"],
              "review level dirty:", meta["review_level_dirty_after_reload"])


if __name__ == "__main__":
    main()
