"""Live UnrealEditor helper for review/evidence scripts (MCP 127.0.0.1:8123/mcp + editor console).

    from ue_live import Ue
    ue = Ue()
    ue.call("asset", "find_assets", {"folder_path": "/Game/ART004", "name": "", "recursive": True})
    ue.console("Interchange.FeatureFlags.Import.FBX 0")      # typed into the editor "Cmd" box
    data = ue.py_file("C:/tmp/x.py", "C:/tmp/x.json")        # `py "<file>"` in the editor, waits for JSON

The client selects the toolset dialect from the editor's initialize response. UE_MCP_EXPECT_PROJECT
optionally pins the connection to the exact .uproject reported by the editor.

Why the console: the MCP toolsets of UE 5.8 have no console-command or Python tool (the
ProgrammaticToolset sandbox only allows json/math/re/...); FBX animation import options,
console variables and AnimSequence queries need the editor's own Python. The console text box
is found through SlateInspectorToolset.Snapshot (text "Cmd" + following textbox) and filled
with SlateInspectorToolset.Type (submit=True), as in tools/art/art004_head_tilt_v3_mcp_review.
The UE-side script writes its result JSON itself; py_file() deletes a stale file first and
polls for the new one, so a failed script is a timeout with the tail of LogPython attached.

The endpoint is configurable with UE_MCP_URL.
"""

import json
import os
import re
import time
import urllib.error
import urllib.request

URL = os.environ.get("UE_MCP_URL", "http://127.0.0.1:8123/mcp")  # second editor: set UE_MCP_URL
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


TOOLSETS_59 = {
    "asset": "EditorToolset.AssetToolset", "static": "EditorToolset.StaticMeshToolset",
    "skeletal": "EditorToolset.SkeletalMeshToolset", "texture": "EditorToolset.TextureToolset",
    "material": "EditorToolset.MaterialToolset", "instance": "EditorToolset.MaterialInstanceToolset",
    "object": "EditorToolset.ObjectToolset", "scene": "EditorToolset.LevelToolset",
    "actor": "EditorToolset.ActorToolset", "app": TOOLSETS["app"], "slate": TOOLSETS["slate"],
    "logs": "ConsoleToolset.LogsToolset", "console": "ConsoleToolset.ConsoleToolset",
}


def _key(name):
    return name.replace("_", "").casefold()


def _native_args(args, schema):
    """Match the project's Python argument names to the reflected MCP names."""
    properties = schema.get("properties", {})
    names = {_key(name): name for name in properties}
    for name, prop in properties.items():
        if prop.get("type") == "boolean" and name.startswith("b") and name[1:2].isupper():
            names.setdefault(_key(name[1:]), name)
    result = {}
    for name, val in args.items():
        field = names.get(_key(name))
        if field is None or field in result:
            raise UeError(f"Unexpected or duplicate argument {name!r}; schema fields: {list(properties)}")
        result[field] = val
    return result


def _transform(fields, *, scale_key):
    names = {"location": "translation", "scale": scale_key}
    return {names.get(key, key): val for key, val in fields.items()}


class Ue:
    def __init__(self, url=None, expected_project=None):
        self.url = url or os.environ.get("UE_MCP_URL", URL)
        self.session, self.next_id, self.protocol = None, 0, None
        self.calls = []
        self._schemas = {}
        reply = self._rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                                        "clientInfo": {"name": "tripo-pipeline-ue-live", "version": "2"}})
        info = self._result(reply)
        self.protocol = info["protocolVersion"]
        self.instance = info.get("_meta", {}).get("com.epicgames.unrealengine/instance", {})
        self.engine_version = self.instance.get("engineVersion") or info.get("serverInfo", {}).get("version", "")
        version = re.match(r"(\d+)\.(\d+)\b", self.engine_version)
        self.native_toolsets = bool(version and tuple(map(int, version.groups())) >= (5, 9))
        expected = expected_project or os.environ.get("UE_MCP_EXPECT_PROJECT")
        if expected:
            actual = self.instance.get("projectFile")
            if not actual or os.path.normcase(os.path.realpath(actual)) != os.path.normcase(os.path.realpath(expected)):
                raise UeError(f"MCP project mismatch: expected {expected!s}, got {actual!r}")
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})

    @staticmethod
    def _result(reply):
        if not reply or "result" not in reply:
            raise UeError(f"MCP request failed: {reply}")
        return reply["result"]

    def _post(self, body, timeout=900):
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        if self.protocol:
            headers["MCP-Protocol-Version"] = self.protocol
        req = urllib.request.Request(self.url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                self.session = resp.headers.get("Mcp-Session-Id") or self.session
                raw = resp.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError) as exc:
            raise UeError(f"MCP {self.url}: {exc}") from exc
        if not raw.strip():
            return None
        if raw.lstrip().startswith("{"):
            return json.loads(raw)
        data = [line[5:].strip() for line in raw.splitlines() if line.startswith("data:")]
        return json.loads(data[-1]) if data else None

    def _rpc(self, method, params):
        self.next_id += 1
        return self._post({"jsonrpc": "2.0", "id": self.next_id, "method": method, "params": params})

    def _tool_schemas(self, ts):
        if ts not in self._schemas:
            reply = self._rpc("tools/call", {"name": "describe_toolsets",
                                             "arguments": {"toolset_names": [ts], "include_schemas": True}})
            result = self._result(reply)
            if result.get("isError"):
                raise UeError(f"Cannot describe {ts}: {result.get('content')}")
            data = result.get("structuredContent") or json.loads(result["content"][0]["text"])
            if ts not in data.get("toolsets", {}):
                raise UeError(f"Unknown toolset {ts}: {str(data.get('errors', {}))[:300]}")
            self._schemas[ts] = {_key(t["name"].rsplit(".", 1)[-1]): t for t in data["toolsets"][ts]["tools"]}
        return self._schemas[ts]

    def call(self, toolset, tool, args=None, record=True):
        ts = TOOLSETS.get(toolset, toolset)
        args = dict(args or {})
        if self.native_toolsets:
            ts = TOOLSETS_59.get(toolset, toolset)
            if (toolset, tool) == ("asset", "save_assets"):
                paths = args.get("asset_paths")
                if not isinstance(paths, list):
                    raise UeError("save_assets expects an asset_paths list")
                for path in paths:
                    self.call("asset", "SaveAsset", {"assetPath": path}, record=record)
                return True
            if (toolset, tool) == ("app", "CaptureViewport"):
                ts, tool = "SceneCaptureToolset.SceneCaptureToolset", "CaptureEditorViewport"
            elif (toolset, tool) == ("app", "SearchCVars"):
                ts = TOOLSETS_59["console"]
            elif (toolset, tool) == ("static", "is_nanite_enabled"):
                tool = "IsNaniteMesh"
            elif toolset == "logs" and "category" in args:
                args["logCategory"] = args.pop("category")
            schema = self._tool_schemas(ts).get(_key(tool))
            if not schema:
                raise UeError(f"Tool {tool!r} is not registered in {ts}")
            tool = schema["name"].rsplit(".", 1)[-1]
            input_schema = schema["inputSchema"]
            for operation, field in (("SetActorTransform", "xform"), ("SetSocketTransform", "transform")):
                if tool == operation and field in args:
                    args.update(_transform(args.pop(field), scale_key="scale"))
            for field in ("captureTransform", "xform"):
                if isinstance(args.get(field), dict):
                    args[field] = _transform(args[field], scale_key="scale3D")
            if (ts, tool) == (TOOLSETS_59["asset"], "FindAssets") and "filter" not in args:
                # The 5.8 listing was exhaustive. 5.9 otherwise truncates it to 100.
                args = {"filter": {"maxResults": 0, **_native_args(args, input_schema["properties"]["filter"])}}
            args = _native_args(args, input_schema)
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
        if self.native_toolsets and tool in ("GetSocketTransform", "GetActorTransform") and isinstance(value, dict):
            fields = {"translation": "location", "scale3D": "scale"}
            value = {fields.get(k, k): v for k, v in value.items()}
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
        at most `attempts` times. Without `started` the command is typed once.

        UE_CONSOLE_DROP=<dir> (editor started hidden with ue_py/console_drop.py on that dir, ART-016 2026-10-04): the
        command is handed over as a file instead of typed (a hidden editor cannot focus its console box)."""
        drop = os.environ.get("UE_CONSOLE_DROP")
        if drop:
            return self._console_drop(drop, command, started, grace_s * attempts)
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

    def _console_drop(self, drop, command, started, wait_s):
        """ue_py/console_drop.py protocol: cmd-<seq>.json in, done-<seq>.json out. A `py` task with `started` returns
        once it started (the caller waits for its out file); any other command returns when it is done."""
        if not os.path.exists(os.path.join(drop, "ready.json")):
            raise UeError("UE_CONSOLE_DROP=%s: no ready.json (console_drop.py not running in the editor)" % drop)
        seq = int(time.time() * 1000)
        while os.path.exists(os.path.join(drop, "cmd-%d.json" % seq)) or os.path.exists(os.path.join(drop, "done-%d.json" % seq)):
            seq += 1
        path = os.path.join(drop, "cmd-%d.json" % seq)
        with open(path + ".tmp", "w", encoding="utf-8") as handle:
            json.dump({"seq": seq, "command": command}, handle)
        os.replace(path + ".tmp", path)
        done = os.path.join(drop, "done-%d.json" % seq)
        deadline = time.time() + wait_s
        while time.time() < deadline:
            if started is not None and os.path.exists(started):
                break
            if os.path.exists(done):
                try:
                    with open(done, encoding="utf-8") as handle:
                        res = json.load(handle)
                except ValueError:
                    time.sleep(0.1)
                    continue
                if not res.get("ok"):
                    raise UeError("console (drop) %s failed: %s" % (command, res.get("error")))
                break
            time.sleep(0.1)
        else:
            raise UeError("console (drop) %s: not taken within %.0f s (editor busy or console_drop.py gone)" % (command, wait_s))
        self.calls.append({"console": command, "drop": seq})

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
