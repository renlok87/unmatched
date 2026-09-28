"""Evidence: what the LIVE UE 5.8 MCP `import_file` does when the asset name is already taken.

    python tools/tripo-pipeline/review/ue_already_exists_probe.py --fbx <small FBX> --out <transcript.json>
        [--folder /Game/PipelineCandidates/_ImportProbe]

Works only in a scratch folder under /Game/PipelineCandidates/ that must not exist beforehand:
  1. find_assets (expected empty), 2. StaticMeshTools.import_file NAME, 3. the same import again,
  4. find_assets (is there a NAME_1?), 5. delete every asset the probe created and the folder,
  6. exists (folder gone).
Every request and the raw JSON-RPC response of unreal_mcp.py are written to the transcript.
Nothing outside the scratch folder is touched; nothing is saved.
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

CLIENT = "C:/Users/ren/.claude/mcp-servers/clients/unreal_mcp.py"
TS = {"asset": "editor_toolset.toolsets.asset.AssetTools",
      "static": "editor_toolset.toolsets.static_mesh.StaticMeshTools"}
ALLOWED_ROOT = "/Game/PipelineCandidates/"


def call(steps, ts, tool, args):
    proc = subprocess.run([sys.executable, CLIENT, "call", TS[ts], tool, json.dumps(args)], capture_output=True)
    raw = proc.stdout.decode("utf-8", "replace")
    try:
        response = json.loads(raw)
    except ValueError:
        response = {"unparsed_stdout": raw[-2000:]}
    result = response.get("result") or {}
    texts = [c.get("text", "") for c in result.get("content", []) if isinstance(c, dict)]
    payload = result.get("structuredContent")
    if payload is None and texts and texts[0].strip().startswith("{"):
        payload = json.loads(texts[0])
    steps.append({"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  "request": {"toolset": TS[ts], "tool": tool, "arguments": args},
                  "client_exit": proc.returncode, "is_error": bool(result.get("isError") or response.get("error")),
                  "response": response})
    return (payload or {}).get("returnValue") if isinstance(payload, dict) else payload, bool(result.get("isError"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fbx", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--folder", default="/Game/PipelineCandidates/_ImportProbe")
    ap.add_argument("--name", default="SM_ImportProbe")
    a = ap.parse_args()
    folder = a.folder.rstrip("/")
    if not (folder + "/").startswith(ALLOWED_ROOT) or ".." in folder:
        raise SystemExit("scratch folder must be under %s" % ALLOWED_ROOT)
    steps = []
    exists, _ = call(steps, "asset", "exists", {"path": folder})
    if exists:
        raise SystemExit("scratch folder %s already exists; refusing (it may hold someone else's assets)" % folder)
    args = {"folder_path": folder, "asset_name": a.name, "source_file": str(Path(a.fbx).resolve()),
            "import_materials": False, "import_textures": False, "combine_meshes": True}
    created = []
    try:
        first, first_err = call(steps, "static", "import_file", args)
        created += [x.get("refPath") if isinstance(x, dict) else x for x in (first or [])]
        second, second_err = call(steps, "static", "import_file", args)
        created += [x.get("refPath") if isinstance(x, dict) else x for x in (second or [])]
        listing, _ = call(steps, "asset", "find_assets", {"folder_path": folder, "name": "", "recursive": True})
    finally:
        found, _ = call(steps, "asset", "find_assets", {"folder_path": folder, "name": "", "recursive": True})
        for asset in sorted(set(found or [])):
            call(steps, "asset", "delete", {"path": asset})
        call(steps, "asset", "delete", {"path": folder})
        gone, _ = call(steps, "asset", "exists", {"path": folder})
    summary = {"first_import_error": first_err, "second_import_error": second_err,
               "second_import_message": " ".join(c.get("text", "") for c in (steps[2]["response"].get("result") or {})
                                                 .get("content", []) if isinstance(c, dict))[:500],
               "assets_after_second_import": listing, "numbered_duplicate_created": any(
                   str(x).rstrip("/").endswith(a.name + "_1") for x in (listing or [])),
               "scratch_folder_removed": not gone}
    out = {"kind": "live UnrealEditor 5.8 MCP transcript (unreal_mcp.py call); scratch folder only, nothing saved",
           "folder": folder, "fbx": Path(a.fbx).name, "summary": summary, "steps": steps}
    Path(a.out).write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
