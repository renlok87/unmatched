"""ART-004 A1 head-tilt v3 review through the LIVE editors (2026-09-28).

Thin helper over the live UE MCP HTTP server (127.0.0.1:8123/mcp); the Blender
steps in blender/ are sent to the live Blender MCP socket (127.0.0.1:9876) with
C:/Users/ren/.claude/mcp-servers/clients/blender_mcp.py exec <file>.
Scratch output goes to C:/tmp/a1v3 (run from that directory); assemble.py copies
the selected files into docs/game-design/evidence/ART-004/head-tilt-v3-probe-2026-09-28/.
Order: UE import (SkeletalMeshTools.import_file, see acceptance doc), setup_scene.py,
grid.py/set_ev.py (viewport FOV 35, EV100 1.3, grid off), calib.py, run_light.py per
level, ue_sockets.py (via editor console `py`), blender/b1..b10, analyze_id.py,
junction_enclosed.py, ue_face_metrics.py, ue_frame_diffs.py, assemble.py,
composites.py, build_json.py, blender/b99_cleanup.py. Never saves levels or .blend.
Since the P0 review fixes (2026-09-28): before composites.py/build_json.py run the
headless tools/art/art004_head_tilt_v3_followup.py -- C:/tmp/a1v3/followup (no live
Blender); build_json.py also reads removed_from_probe_dir.json (SHA-256 of the files
pruned from the probe directory) from C:/tmp/a1v3.
Paths: the offline scripts (assemble, composites, build_json, junction_enclosed,
ue_frame_diffs) take their roots from _paths.py and also run from the main checkout;
the live-editor scripts (blender/b*.py, bview.py, calib.py, ue_sockets.py,
ue_dirty_probe.py) keep the absolute paths of the run, see the _paths.py docstring.
"""
import base64, json, sys, urllib.request
URL = "http://127.0.0.1:8123/mcp"
_s = {"sid": None, "id": 0}

def _post(body, timeout=900):
    data = json.dumps(body).encode("utf-8")
    h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    if _s["sid"]:
        h["Mcp-Session-Id"] = _s["sid"]
    req = urllib.request.Request(URL, data=data, headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        sid = r.headers.get("Mcp-Session-Id")
        if sid:
            _s["sid"] = sid
        raw = r.read().decode("utf-8")
    if not raw.strip():
        return None
    if raw.lstrip().startswith("{"):
        return json.loads(raw)
    last = None
    for line in raw.splitlines():
        if line.startswith("data:"):
            last = line[5:].strip()
    return json.loads(last) if last else None

def init():
    if _s["sid"]:
        return
    _s["id"] += 1
    _post({"jsonrpc": "2.0", "id": _s["id"], "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "a1v3", "version": "1"}}})
    _post({"jsonrpc": "2.0", "method": "notifications/initialized"})

def call(toolset, tool, args=None):
    init()
    _s["id"] += 1
    res = _post({"jsonrpc": "2.0", "id": _s["id"], "method": "tools/call", "params": {"name": "call_tool", "arguments": {"toolset_name": toolset, "tool_name": tool, "arguments": args or {}}}})
    if res is None:
        return None
    if "error" in res:
        raise RuntimeError(json.dumps(res["error"], ensure_ascii=False)[:2000])
    result = res["result"]
    text = "".join(c.get("text", "") for c in result.get("content", []) if c.get("type") == "text")
    if result.get("isError"):
        raise RuntimeError(text[:3000])
    try:
        return json.loads(text)
    except ValueError:
        return text

SCENE = "editor_toolset.toolsets.scene.SceneTools"
ASSET = "editor_toolset.toolsets.asset.AssetTools"
APP = "EditorToolset.EditorAppToolset"
ACTOR = "editor_toolset.toolsets.actor.ActorTools"
OBJ = "editor_toolset.toolsets.object.ObjectTools"
SKM = "editor_toolset.toolsets.skeletal_mesh.SkeletalMeshTools"
STM = "editor_toolset.toolsets.static_mesh.StaticMeshTools"
LOGS = "EditorToolset.LogsToolset"
PROG = "editor_toolset.toolsets.programmatic.ProgrammaticToolset"

def save_image(img, path):
    raw = base64.b64decode(img["data"])
    with open(path, "wb") as f:
        f.write(raw)
    return len(raw)

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    args = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
    print(json.dumps(call(sys.argv[1], sys.argv[2], args), ensure_ascii=False, indent=1)[:20000])

SLATE = "SlateInspectorToolset.SlateInspectorToolset"
NOMOD = {"bShift": False, "bCtrl": False, "bAlt": False, "bCmd": False}

def click(ref, button="left", double=False):
    return call(SLATE, "Click", {"ref": ref, "button": button, "doubleClick": double, "modifiers": NOMOD})

def snapshot(ref="", depth=40):
    return call(SLATE, "Snapshot", {"ref": ref, "maxDepth": depth, "bIncludeSourceLocations": False})["returnValue"]
