"""Live UnrealEditor helper for review/evidence scripts (MCP 127.0.0.1:8123/mcp + editor console).

    from ue_live import Ue
    ue = Ue()
    ue.call("asset", "find_assets", {"folder_path": "/Game/ART004", "name": "", "recursive": True})
    ue.console("Interchange.FeatureFlags.Import.FBX 0")      # typed into the editor "Cmd" box
    data = ue.py_file("C:/tmp/x.py", "C:/tmp/x.json")        # `py "<file>"` in the editor, waits for JSON

Why the console: the MCP toolsets of UE 5.8 have no console-command or Python tool (the
ProgrammaticToolset sandbox only allows json/math/re/...); FBX animation import options,
console variables and AnimSequence queries need the editor's own Python. The console text box
is found through SlateInspectorToolset.Snapshot (text "Cmd" + following textbox) and filled
with SlateInspectorToolset.Type (submit=True), as in tools/art/art004_head_tilt_v3_mcp_review.
The UE-side script writes its result JSON itself; py_file() deletes a stale file first and
polls for the new one, so a failed script is a timeout with the tail of LogPython attached.

Never used with UnrealEditor-Cmd; only the one GUI editor that owns :8123.
"""

import json
import os
import re
import time
import urllib.request

URL = "http://127.0.0.1:8123/mcp"
TOOLSETS = {
    "asset": "editor_toolset.toolsets.asset.AssetTools",
    "static": "editor_toolset.toolsets.static_mesh.StaticMeshTools",
    "skeletal": "editor_toolset.toolsets.skeletal_mesh.SkeletalMeshTools",
    "texture": "editor_toolset.toolsets.texture.TextureTools",
    "material": "editor_toolset.toolsets.material.MaterialTools",
    "instance": "editor_toolset.toolsets.material_instance.MaterialInstanceTools",
    "object": "editor_toolset.toolsets.object.ObjectTools",
    "scene": "editor_toolset.toolsets.scene.SceneTools",
    "actor": "editor_toolset.toolsets.actor.ActorTools",
    "app": "EditorToolset.EditorAppToolset",
    "logs": "EditorToolset.LogsToolset",
    "slate": "SlateInspectorToolset.SlateInspectorToolset",
}


class UeError(RuntimeError):
    pass


class Ue:
    def __init__(self, url=URL):
        self.url, self.session, self.next_id = url, None, 0
        self.calls = []
        self._rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                                 "clientInfo": {"name": "tripo-pipeline-ue-live", "version": "1"}})
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _post(self, body, timeout=900):
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        req = urllib.request.Request(self.url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
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

    def call(self, toolset, tool, args=None, record=True):
        ts = TOOLSETS.get(toolset, toolset)
        res = self._rpc("tools/call", {"name": "call_tool",
                                       "arguments": {"toolset_name": ts, "tool_name": tool, "arguments": args or {}}})
        if res is None:
            raise UeError("no response for %s.%s" % (ts, tool))
        if "error" in res:
            raise UeError("%s.%s: %s" % (ts, tool, json.dumps(res["error"], ensure_ascii=False)[:1500]))
        result = res["result"]
        texts = [c.get("text", "") for c in result.get("content", []) if c.get("type") == "text"]
        images = [c for c in result.get("content", []) if c.get("type") == "image"]
        if result.get("isError"):
            if record:
                self.calls.append({"toolset": ts, "tool": tool, "args": args, "ok": False, "error": " ".join(texts)[:1500]})
            raise UeError("%s.%s: %s" % (ts, tool, " ".join(texts)[:1500]))
        payload = result.get("structuredContent")
        if payload is None:
            try:
                payload = json.loads(texts[0]) if texts else {}
            except ValueError:
                payload = {"returnValue": texts[0]}
        value = payload.get("returnValue") if isinstance(payload, dict) and "returnValue" in payload else payload
        if isinstance(value, str) and value[:1] in "[{":
            try:
                value = json.loads(value)
            except ValueError:
                pass
        if record:
            self.calls.append({"toolset": ts, "tool": tool, "args": args, "ok": True,
                               "result": value if not images else "<image>"})
        if images:
            return {"value": value, "images": images}
        return value

    # ------------------------------------------------------------------ console
    def _console_box(self, wait_s=120):
        # The Slate tree comes back empty while the editor window is not shown on the current desktop (measured
        # 2026-09-29: another session switched the desktop); wait for it instead of failing the whole run.
        deadline = time.time() + wait_s
        while True:
            snap = self.call("slate", "Snapshot", {"ref": "", "maxDepth": 60, "bIncludeSourceLocations": False},
                             record=False)
            text = snap if isinstance(snap, str) else json.dumps(snap)
            i = text.find('text "Cmd"')
            if i >= 0 or time.time() > deadline:
                break
            time.sleep(5)
        if i < 0:
            raise UeError("editor console (Cmd box) not found in the Slate tree")
        m = re.search(r"textbox [^\n]*\[ref=(\w+)\]", text[i:i + 600])
        if not m:
            raise UeError("editor console textbox not found after the Cmd selector")
        return m.group(1)

    def console(self, command, started=None, attempts=5, grace_s=20.0):
        """Type `command` into the editor console.

        SlateInspector's Type only warns ("Could not focus widget for typing") while another application holds the
        keyboard focus, and the command is then lost (measured 2026-09-29, a parallel session on the same desktop).
        The editor log is no proof either way: typed `py` commands are not always echoed as `Cmd:` lines (a command
        that ran was missing from LogsToolset.GetLogEntries, 2026-09-29). So a command that can prove it started
        passes `started` (a file its script writes first, see ue_py/_run.py): no file within grace_s -> typed again,
        at most `attempts` times. Without `started` the command is typed once."""
        for attempt in range(attempts):
            ref = self._console_box()
            self.call("slate", "Type", {"ref": ref, "text": command, "submit": True}, record=False)
            time.sleep(0.4)
            if started is None:
                break
            deadline = time.time() + grace_s
            while time.time() < deadline and not os.path.exists(started):
                time.sleep(0.25)
            if os.path.exists(started):
                break
        else:
            raise UeError("console command did not start after %d attempts (editor focus?): %s" % (attempts, command))
        self.calls.append({"console": command, "attempts": attempt + 1})

    def run_task(self, script, out_json, timeout=600, **args):
        """Run a UE-side task script through ue_py/_run.py (errors come back as {"error": ...})."""
        here = os.path.dirname(os.path.abspath(__file__))
        payload = dict(args, script=os.path.abspath(script).replace("\\", "/"),
                       out=os.path.abspath(out_json).replace("\\", "/"))
        args_path = os.path.abspath(out_json) + ".args.json"
        with open(args_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=1)
        try:
            data = self.py_file(os.path.join(here, "ue_py", "_run.py"), payload["out"], timeout=timeout,
                                args=args_path.replace("\\", "/"), started=payload["out"] + ".started")
        finally:
            os.remove(args_path)
            if os.path.exists(payload["out"] + ".started"):
                os.remove(payload["out"] + ".started")
        if isinstance(data, dict) and data.get("error"):
            raise UeError("UE task %s failed: %s\n%s" % (script, data["error"], data.get("traceback", "")[-2000:]))
        return data

    def py_file(self, script, out_json, timeout=600, args="", started=None):
        for stale in (out_json, started):
            if stale and os.path.exists(stale):
                os.remove(stale)
        self.console('py "%s"%s' % (script.replace("\\", "/"), (" " + args) if args else ""), started=started)
        deadline = time.time() + timeout
        while time.time() < deadline:
            if os.path.exists(out_json):
                time.sleep(0.3)
                try:
                    with open(out_json, encoding="utf-8") as handle:
                        return json.load(handle)
                except ValueError:
                    pass
            time.sleep(0.5)
        tail = self.call("logs", "GetLogEntries", {"category": "LogPython", "pattern": "", "maxEntries": 30},
                         record=False)
        raise UeError("py %s: no %s after %ss; LogPython tail: %s" % (script, out_json, timeout,
                                                                    json.dumps(tail, ensure_ascii=False)[-2500:]))
