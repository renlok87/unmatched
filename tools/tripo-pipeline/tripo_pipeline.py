#!/usr/bin/env python3
"""tripo-pipeline: local, resumable, idempotent pipeline scaffold for Tripo results.

This tool NEVER talks to Tripo (no Studio automation, no API client, no network
imports at all). It registers Tripo results that already exist on disk, runs
local stages (Blender headless for import/export) and keeps a run manifest with
hashes, tool versions, costs and a stage journal. Documentation (Russian):
docs/art-pipeline/PIPELINE.md.

Commands:
  init               create/confirm a run directory and its config
  register-source    register an existing Tripo result from a source-spec JSON
  preflight          check tools, paths and hashes (also stage 0 of `run`)
  import             Blender: read the primary GLB into work/<basename>.blend
  verify             check the import against GLB structure and spec expectations
  export             Blender: deterministic FBX (preset UM_FBX_v1) + round-trip re-import check
                     (profile passthrough)
  atlas              Python/Pillow: pack part textures into BC/N/ORM atlas (profile skeletal-candidate)
  build              Blender: skeletal candidate + separate base from a build profile, deterministic
                     FBX with the profile's preset (UM_FBX_v1: face -Y -> +X), round-trip and
                     reference checks (profile skeletal-candidate)
  ue-import          UE (only --backend mcp): import into /Game/PipelineCandidates/... without
                     duplicates and measure the import contracts
  run                all stages of the run's profile (skips up-to-date stages):
                       passthrough:        preflight -> import -> verify -> export [-> ue-import]
                       skeletal-candidate: preflight -> import -> verify -> atlas -> build [-> ue-import]
  resume             continue an interrupted run from the first unfinished stage
  status             print the manifest summary
  snapshot           hash every run file (proof of "no duplicates" between runs)
  prepare-generation dry-run package of generation inputs; never submits; refuses inputs + mode +
                     service that were already generated (any model label) unless
                     --allow-duplicate --duplicate-reason "..."

Backends (--backend, default headless):
  headless  Blender stages in a fresh `blender -b` process; UE stage refused
  mcp       Blender stages in the running Blender GUI through blender_mcp.py
            (addon socket 127.0.0.1:9876, execute_code, isolated temp scenes);
            UE stage in the running UnrealEditor through unreal_mcp.py
            (127.0.0.1:8123/mcp: AssetTools / StaticMeshTools / SkeletalMeshTools).
  MCP traffic goes through those external client scripts (subprocess); this
  file itself has no network code and never contacts Tripo.

FBX axes: every FBX this tool writes follows the verified preset UM_FBX_v1
(blender/_tools/presets/UM_FBX_v1.json, ART-001 PASS; 04-blender-production.md §1/§1.1):
authored front -Y is rotated to +X before export, so UE shows the front along +X.

Statuses written by this tool are only "measured" / "technically imported"; it
never marks anything as art-accepted and declares no budgets.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import platform
import re
import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path

TOOL_NAME = "tripo-pipeline"
TOOL_VERSION = "0.4.0"
RUN_SCHEMA = "unmatched.tripo-pipeline.run/1"
SPEC_SCHEMA = "unmatched.tripo-pipeline.source-spec/1"
REQUEST_SCHEMA = "unmatched.tripo-pipeline.generation-request/1"
BUILD_PROFILE_SCHEMA = "unmatched.tripo-pipeline.build-profile/1"
VERIFY_LOGIC_VERSION = "verify/1"
PREFLIGHT_LOGIC_VERSION = "preflight/4"
UE_IMPORT_LOGIC_VERSION = "ue-import/2"
UE_CANDIDATE_LOGIC_VERSION = "ue-candidate/2"

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2
EXIT_CONFLICT = 3
EXIT_LOCKED = 4
EXIT_NEEDS_RESUME = 5
EXIT_INTERRUPTED = 75

TOOL_DIR = Path(__file__).resolve().parent
BLENDER_SCRIPTS = {
    "import": TOOL_DIR / "blender" / "import_source.py",
    "export": TOOL_DIR / "blender" / "export_fbx.py",
    "build": TOOL_DIR / "blender" / "build_candidate.py",
}
ATLAS_SCRIPT = TOOL_DIR / "candidate" / "atlas.py"
DEFAULT_FBX_PRESET = "blender/_tools/presets/UM_FBX_v1.json"  # repo-relative; ART-001 PASS 2026-09-27
FBX_PRESET_NAME = "UM_FBX_v1"
FBX_PRESET_KEYS = ("name", "axis_forward", "axis_up", "export_space_rotation_z_degrees", "temporary_data_scale",
                   "patch_fbx_unit_scale_to", "apply_unit_scale", "apply_scale_options", "use_triangles",
                   "mesh_smooth_type", "add_leaf_bones", "primary_bone_axis", "secondary_bone_axis", "path_mode")
DEFAULT_BLENDER = "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"
DEFAULT_UE_ROOT = "C:/Program Files/Epic Games/UE_5.8"
DEFAULT_MCP_CLIENTS = Path("C:/Users/ren/.claude/mcp-servers/clients")
BACKENDS = ("headless", "mcp")
PASSTHROUGH = "passthrough"
CANDIDATE = "skeletal-candidate"
PROFILES = (PASSTHROUGH, CANDIDATE)
STAGES = ("preflight", "import", "verify", "export")  # passthrough profile (T3)
CANDIDATE_STAGES = ("preflight", "import", "verify", "atlas", "build")
UE_STAGE = "ue-import"
ALL_STAGES = STAGES + (UE_STAGE,)
KNOWN_STAGES = ("preflight", "import", "verify", "export", "atlas", "build", UE_STAGE)
UE_ALLOWED_ROOT = "/Game/PipelineCandidates/"
UE_TOOLSETS = {
    "asset": "editor_toolset.toolsets.asset.AssetTools",
    "static": "editor_toolset.toolsets.static_mesh.StaticMeshTools",
    "skeletal": "editor_toolset.toolsets.skeletal_mesh.SkeletalMeshTools",
    "texture": "editor_toolset.toolsets.texture.TextureTools",
    "material": "editor_toolset.toolsets.material.MaterialTools",
    "instance": "editor_toolset.toolsets.material_instance.MaterialInstanceTools",
    "object": "editor_toolset.toolsets.object.ObjectTools",
    "logs": "EditorToolset.LogsToolset",
}
ATLAS_TIMEOUT_S = 600
DEFAULT_UE_DIMENSION_TOLERANCE = 0.01  # fraction of the Blender-measured size
SERVICES = {"tripo-studio": "studio-credits", "tripo-api": "api-credits"}
GENERATION_MODES = ("multi-view", "single-image", "text")
MAX_TRIPO_IMAGE_BYTES = 20_000_000
DEFAULT_TRIANGLE_LOSS_TOLERANCE = 0.001  # fraction; Blender's glTF importer may drop degenerate tris
BLENDER_TIMEOUT_S = 1800

STATUS_LEGEND = {
    "proposed": "предложено — план или норматив без проверки",
    "measured": "измерено — число получено инструментом из файла",
    "technically_imported": "технически импортировано — файл прочитан/записан без ошибок, контракты проверены",
    "art_accepted": "художественно принято — только решением арт-трека; этот инструмент его не ставит",
}


class PipelineError(Exception):
    def __init__(self, message: str, code: int = EXIT_FAILED):
        super().__init__(message)
        self.code = code


# --------------------------------------------------------------------------- utils

def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical(data) -> str:
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256_json(data) -> str:
    return hashlib.sha256(canonical(data).encode("utf-8")).hexdigest()


def dump_json(data) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp-%d" % os.getpid())
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    for attempt in range(20):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:  # Windows: a reader (AV, indexer) briefly holds the file
            time.sleep(0.05 * (attempt + 1))
    os.replace(tmp, path)


def rel_posix(path: Path, base: Path) -> str:
    return Path(os.path.relpath(path, base)).as_posix()


def is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return ctypes.get_last_error() == 5  # access denied => process exists
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return True
            return code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


# --------------------------------------------------------------- file inspectors

def inspect_glb(path: Path) -> dict:
    """Stdlib-only structural read of a binary glTF (JSON chunk only)."""
    with open(path, "rb") as handle:
        header = handle.read(20)
        if len(header) < 20:
            raise PipelineError("GLB too short: %s" % path)
        magic, version, _length = struct.unpack_from("<4sII", header, 0)
        chunk_length, chunk_type = struct.unpack_from("<I4s", header, 12)
        if magic != b"glTF" or chunk_type != b"JSON":
            raise PipelineError("not a binary glTF: %s" % path)
        doc = json.loads(handle.read(chunk_length).decode("utf-8"))
    accessors = doc.get("accessors", [])
    meshes = []
    modes = set()
    for mesh in doc.get("meshes", []):
        tris = 0
        for prim in mesh.get("primitives", []):
            mode = prim.get("mode", 4)
            modes.add(mode)
            if "indices" in prim:
                count = accessors[prim["indices"]]["count"]
            else:
                count = accessors[prim["attributes"]["POSITION"]]["count"]
            if mode == 4:
                tris += count // 3
        meshes.append({"name": mesh.get("name"), "triangles": tris})
    return {
        "format": "glb",
        "gltf_version": version,
        "generator": doc.get("asset", {}).get("generator"),
        "mesh_count": len(meshes),
        "triangles": sum(m["triangles"] for m in meshes),
        "materials": len(doc.get("materials", [])),
        "images": len(doc.get("images", [])),
        "skins": len(doc.get("skins", [])),
        "animations": len(doc.get("animations", [])),
        "primitive_modes": sorted(modes),
        "meshes": sorted(meshes, key=lambda m: str(m["name"])),
    }


def inspect_png(path: Path) -> dict:
    with open(path, "rb") as handle:
        head = handle.read(33)
    if head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        return {"format": "unknown"}
    width, height, depth, color = struct.unpack(">IIBB", head[16:26])
    return {"format": "png", "pixels": [width, height], "bit_depth": depth, "color_type": color}


def inspect_jpeg(path: Path) -> dict:
    with open(path, "rb") as handle:
        data = handle.read(1 << 20)
    if data[:2] != b"\xff\xd8":
        return {"format": "unknown"}
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2):
            height, width = struct.unpack(">HH", data[i + 5:i + 9])
            return {"format": "jpeg", "pixels": [width, height]}
        seg = struct.unpack(">H", data[i + 2:i + 4])[0]
        i += 2 + seg
    return {"format": "jpeg", "pixels": None}


def inspect_file(path: Path) -> dict:
    suffix = path.suffix.lower()
    if suffix == ".glb":
        return inspect_glb(path)
    if suffix == ".png":
        return inspect_png(path)
    if suffix in (".jpg", ".jpeg"):
        return inspect_jpeg(path)
    return {"format": suffix.lstrip(".") or "unknown"}


# ------------------------------------------------------------------------ context

class Context:
    def __init__(self, run_dir: Path, repo_root: Path, blender: str | None, interrupt_at: str | None = None,
                 backend: str | None = None, blender_mcp_client: str | None = None,
                 unreal_mcp_client: str | None = None):
        self.run_dir = run_dir.resolve()
        self.repo_root = repo_root.resolve()
        self.interrupt_at = interrupt_at
        self.manifest_path = self.run_dir / "manifest.json"
        self.journal_path = self.run_dir / "journal.jsonl"
        self.lock_path = self.run_dir / "run.lock"
        self.staging_root = self.run_dir / ".staging"
        self.backend = backend or os.environ.get("TRIPO_PIPELINE_BACKEND") or "headless"
        if self.backend not in BACKENDS:
            raise PipelineError("--backend must be one of %s" % (BACKENDS,), EXIT_USAGE)
        env_cmd = os.environ.get("TRIPO_PIPELINE_BLENDER_CMD")
        if env_cmd:
            self.blender_cmd = json.loads(env_cmd)
        else:
            self.blender_cmd = [blender or os.environ.get("TRIPO_PIPELINE_BLENDER") or DEFAULT_BLENDER]
        self.blender_mcp_cmd = client_command("TRIPO_PIPELINE_BLENDER_MCP_CMD", blender_mcp_client,
                                              DEFAULT_MCP_CLIENTS / "blender_mcp.py")
        self.unreal_mcp_cmd = client_command("TRIPO_PIPELINE_UNREAL_MCP_CMD", unreal_mcp_client,
                                             DEFAULT_MCP_CLIENTS / "unreal_mcp.py")
        if self.backend == "mcp":
            self.blender = McpBlender(self.blender_mcp_cmd)
        else:
            self.blender = HeadlessBlender(self.blender_cmd)
        self._unreal = None
        self.manifest = None
        self._manifest_text = None
        self._locked = False

    # -- manifest
    def load(self) -> dict:
        if not self.manifest_path.exists():
            raise PipelineError("run is not initialised (no manifest.json): %s; use init" % self.run_dir, EXIT_USAGE)
        self._manifest_text = self.manifest_path.read_text(encoding="utf-8")
        self.manifest = json.loads(self._manifest_text)
        if self.manifest.get("schema") != RUN_SCHEMA:
            raise PipelineError("unsupported manifest schema: %s" % self.manifest.get("schema"))
        return self.manifest

    def save(self) -> bool:
        """Write the manifest only if its content changed. Returns True when written."""
        text = dump_json(self.manifest)
        if text == self._manifest_text:
            return False
        atomic_write_text(self.manifest_path, text)
        self._manifest_text = text
        return True

    def journal(self, event: str, **fields) -> None:
        record = {"ts": now_iso(), "pid": os.getpid(), "event": event}
        record.update(fields)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        with open(self.journal_path, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    # -- lock
    def acquire_lock(self, command: str) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"pid": os.getpid(), "command": command, "started_at": now_iso(),
                              "host": platform.node()})
        for _ in range(2):
            try:
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                try:
                    held = json.loads(self.lock_path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    held = {"pid": -1}
                if pid_alive(int(held.get("pid", -1))) and int(held.get("pid", -1)) != os.getpid():
                    raise PipelineError("run is locked by live pid %s (%s)" % (held.get("pid"), held.get("command")),
                                        EXIT_LOCKED)
                self.journal("stale_lock_recovered", previous=held, command=command)
                os.remove(self.lock_path)
                continue
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            self._locked = True
            return
        raise PipelineError("could not acquire run lock", EXIT_LOCKED)

    def release_lock(self) -> None:
        try:
            self.staging_root.rmdir()  # only succeeds when empty
        except OSError:
            pass
        if self._locked and self.lock_path.exists():
            os.remove(self.lock_path)
        self._locked = False

    # -- paths
    def repo_path(self, rel: str) -> Path:
        return (self.repo_root / rel).resolve()

    def run_path(self, rel: str) -> Path:
        return (self.run_dir / rel).resolve()

    # -- tools
    def blender_version(self) -> str:
        return self.blender.version()

    def unreal(self) -> "McpUnreal":
        if self.backend != "mcp":
            raise PipelineError("stage ue-import needs --backend mcp (live UnrealEditor via unreal_mcp.py). "
                                "Headless UE import is not part of this scaffold: UnrealEditor-Cmd must not "
                                "run on the project while the user's editor has it open.", EXIT_USAGE)
        if self._unreal is None:
            self._unreal = McpUnreal(self.unreal_mcp_cmd)
        return self._unreal


def _no_window() -> dict:
    if os.name == "nt":
        return {"creationflags": 0x08000000}  # CREATE_NO_WINDOW
    return {}


def client_command(env_name: str, override: str | None, default: Path) -> list:
    env_cmd = os.environ.get(env_name)
    if env_cmd:
        return json.loads(env_cmd)
    return [sys.executable, str(Path(override) if override else default)]


def client_script(cmd: list) -> Path:
    """The .py client inside an MCP client command line (last *.py argument)."""
    return Path(next((c for c in reversed(cmd) if str(c).lower().endswith(".py")), cmd[-1]))


# ---------------------------------------------------------------------- backends

class HeadlessBlender:
    """Fresh `blender -b` process per stage (isolation mode "process")."""

    kind = "headless"
    isolation = "process"

    def __init__(self, cmd: list):
        self.cmd = cmd
        self._version = None

    def describe(self) -> dict:
        return {"backend": self.kind, "isolation": self.isolation, "command": [Path(c).name for c in self.cmd]}

    def version(self) -> str:
        if self._version is None:
            try:
                proc = subprocess.run(self.cmd + ["--version"], capture_output=True, timeout=120, **_no_window())
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise PipelineError("Blender is not runnable (%s): %s" % (self.cmd, exc))
            text = proc.stdout.decode("utf-8", "replace")
            match = re.search(r"Blender\s+(\S+(?:\s+LTS)?)", text)
            if proc.returncode != 0 or not match:
                raise PipelineError("cannot parse Blender version from: %r" % text[:200])
            self._version = match.group(1)
        return self._version

    def run_stage(self, stage: str, params_path: Path, staging: Path) -> tuple:
        cmd = self.cmd + ["-b", "--factory-startup", "--python-exit-code", "1",
                          "--python", str(BLENDER_SCRIPTS[stage]), "--", str(params_path)]
        try:
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  timeout=BLENDER_TIMEOUT_S, **_no_window())
            return proc.returncode, proc.stdout.decode("utf-8", "replace")
        except subprocess.TimeoutExpired as exc:
            return -1, (exc.stdout or b"").decode("utf-8", "replace") + "\n[tripo-pipeline] TIMEOUT\n"


def run_client(cmd: list, args: list, timeout: int, what: str) -> dict:
    """Run an MCP CLI client (blender_mcp.py / unreal_mcp.py) and parse its JSON stdout."""
    try:
        proc = subprocess.run(cmd + args, capture_output=True, timeout=timeout, **_no_window())
    except (FileNotFoundError, PermissionError) as exc:
        raise PipelineError("%s client not runnable (%s): %s" % (what, cmd, exc))
    except subprocess.TimeoutExpired:
        raise PipelineError("%s client timed out after %ss: %s" % (what, timeout, args[:2]))
    out = proc.stdout.decode("utf-8", "replace")
    err = proc.stderr.decode("utf-8", "replace")
    try:
        data = json.loads(out) if out.strip() else None
    except ValueError:
        data = None
    if data is None:
        raise PipelineError("%s client gave no JSON (exit %s): %s" % (what, proc.returncode,
                                                                     (err or out).strip()[-600:]))
    return {"exit": proc.returncode, "response": data, "stderr": err}


class McpBlender:
    """Running Blender GUI through blender_mcp.py (isolation mode "live").

    The stage script is sent verbatim via execute_code with two injected globals
    (params path, isolation mode). The scripts never reset, open or save the
    user's file; they work in temporary scenes and delete what they created.
    """

    kind = "mcp"
    isolation = "live"

    def __init__(self, cmd: list):
        self.cmd = cmd
        self._version = None

    def describe(self) -> dict:
        return {"backend": self.kind, "isolation": self.isolation, "client": client_script(self.cmd).name,
                "endpoint": "127.0.0.1:9876 (blender-mcp addon)"}

    def version(self) -> str:
        if self._version is None:
            code = "print('TRIPO_PIPELINE_BLENDER_VERSION', bpy.app.version_string)"
            res = run_client(self.cmd, ["exec-str", code], 120, "blender-mcp")["response"]
            text = ((res.get("result") or {}).get("result") or "") if isinstance(res, dict) else ""
            match = re.search(r"TRIPO_PIPELINE_BLENDER_VERSION\s+(\S+(?:\s+LTS)?)", text)
            if not isinstance(res, dict) or res.get("status") == "error" or not match:
                raise PipelineError("live Blender (MCP) did not report its version: %s"
                                    % json.dumps(res, ensure_ascii=False)[:400])
            self._version = match.group(1)
        return self._version

    def run_stage(self, stage: str, params_path: Path, staging: Path) -> tuple:
        header = ("# tripo-pipeline %s: stage %s via blender-mcp execute_code\n"
                  "TRIPO_PIPELINE_PARAMS = %r\nTRIPO_PIPELINE_ISOLATION = \"live\"\n"
                  % (TOOL_VERSION, stage, str(params_path)))
        wrapper = staging / ("%s.mcp.py" % stage)
        wrapper.write_text(header + BLENDER_SCRIPTS[stage].read_text(encoding="utf-8"), encoding="utf-8")
        try:
            call = run_client(self.cmd, ["exec", str(wrapper)], BLENDER_TIMEOUT_S, "blender-mcp")
        except PipelineError as exc:
            return -1, "[tripo-pipeline] %s\n" % exc
        res = call["response"]
        stdout = ((res.get("result") or {}).get("result") or "") if isinstance(res, dict) else ""
        text = "[tripo-pipeline] blender-mcp exec %s (client exit %s)\n%s\n[response]\n%s\n" % (
            wrapper.name, call["exit"], stdout, json.dumps(res, ensure_ascii=False, indent=1)[:20000])
        failed = call["exit"] != 0 or not isinstance(res, dict) or res.get("status") == "error"
        return (1 if failed else 0), text


class McpUnreal:
    """Running UnrealEditor through unreal_mcp.py (ModelContextProtocol plugin, call_tool)."""

    def __init__(self, cmd: list):
        self.cmd = cmd
        self.calls = []
        self.tool_name_style = None  # "short" or "qualified", detected on first call

    def describe(self) -> dict:
        return {"backend": "mcp", "client": client_script(self.cmd).name, "endpoint": "127.0.0.1:8123/mcp"}

    def _once(self, toolset: str, tool: str, args: dict):
        call = run_client(self.cmd, ["call", toolset, tool, json.dumps(args, ensure_ascii=False)], 900,
                          "unreal-mcp")
        res = call["response"] or {}
        if res.get("error"):
            return False, json.dumps(res["error"], ensure_ascii=False)
        result = res.get("result") or {}
        texts = [c.get("text", "") for c in result.get("content", []) if isinstance(c, dict)]
        if result.get("isError") or call["exit"] != 0:
            return False, " ".join(texts) or json.dumps(res, ensure_ascii=False)[:600]
        payload = result.get("structuredContent")
        if payload is None:
            try:
                payload = json.loads(texts[0]) if texts else {}
            except ValueError:
                payload = {"text": texts[0]}
        return True, payload

    def call(self, toolset_key: str, tool: str, args: dict):
        toolset = UE_TOOLSETS[toolset_key]
        styles = [self.tool_name_style] if self.tool_name_style else ["short", "qualified"]
        error = None
        for style in styles:
            name = tool if style == "short" else "%s.%s" % (toolset, tool)
            ok, payload = self._once(toolset, name, args)
            self.calls.append({"toolset": toolset, "tool": name, "args": args, "ok": ok,
                               "result": payload if ok else None, "error": None if ok else payload})
            if ok:
                self.tool_name_style = style
                return payload.get("returnValue") if isinstance(payload, dict) else payload
            error = payload
            if not re.search(r"not found|unknown tool|no tool|invalid tool", str(payload), re.I):
                break
        raise PipelineError("UE MCP %s.%s failed: %s" % (toolset, tool, str(error)[:600]))


# ------------------------------------------------------------------ source specs

def validate_spec(spec: dict) -> None:
    def fail(msg):
        raise PipelineError("source spec invalid: " + msg, EXIT_USAGE)

    if spec.get("schema") != SPEC_SCHEMA:
        fail("schema must be %s" % SPEC_SCHEMA)
    for key in ("source_id", "asset_id", "service", "task_id", "operations", "files"):
        if not spec.get(key):
            fail("missing %s" % key)
    if spec["service"] not in SERVICES:
        fail("service must be one of %s (Studio and API are tracked separately)" % sorted(SERVICES))
    unit = SERVICES[spec["service"]]
    gen = spec.get("generation")
    if gen is not None:
        mode = gen.get("mode")
        if mode == "batch":
            fail("'batch' is several independent tasks; register each Tripo task as its own source")
        if mode not in GENERATION_MODES:
            fail("generation.mode must be one of %s" % (GENERATION_MODES,))
        views = {k: v for k, v in (gen.get("views") or {}).items() if v}
        if mode == "multi-view" and len(views) < 2:
            fail("multi-view means one model from >=2 views of the same object")
        if mode != "multi-view" and len(views) > 1:
            fail("several views given for mode %s" % mode)
    for op in spec["operations"]:
        if not op.get("op"):
            fail("operation without 'op'")
        credits = op.get("credits") or {}
        if credits and credits.get("unit") != unit:
            fail("operation %s: credits.unit must be %s for %s (never mix Studio credits, API credits and USD)"
                 % (op["op"], unit, spec["service"]))
    roles = [f.get("role") for f in spec["files"]]
    if len(roles) != len(set(roles)) or not all(roles):
        fail("file roles must be unique and non-empty")


def build_source_record(ctx: Context, spec: dict) -> dict:
    files = []
    for entry in spec["files"]:
        path = ctx.repo_path(entry["path"])
        if not path.is_file():
            raise PipelineError("source file missing: %s" % entry["path"])
        if is_within(path, ctx.run_dir):
            raise PipelineError("Tripo originals must live outside the run directory: %s" % entry["path"])
        digest = sha256_file(path)
        size = path.stat().st_size
        expected = entry.get("expected_sha256")
        if expected and expected != digest:
            raise PipelineError("hash mismatch for %s: evidence %s, file %s" % (entry["path"], expected, digest))
        if entry.get("expected_bytes") is not None and entry["expected_bytes"] != size:
            raise PipelineError("size mismatch for %s: evidence %s, file %s" % (entry["path"], entry["expected_bytes"], size))
        record = {
            "role": entry["role"],
            "path": Path(entry["path"]).as_posix(),
            "sha256": digest,
            "bytes": size,
            "hash_check": "matches_evidence" if expected else "measured_at_registration_no_evidence_hash",
            "structure": inspect_file(path),
        }
        for key in ("produced_by", "origin"):
            if entry.get(key):
                record[key] = entry[key]
        files.append(record)
    evidence = []
    for rel in spec.get("evidence", []):
        path = ctx.repo_path(rel)
        if not path.is_file():
            raise PipelineError("evidence file missing: %s" % rel)
        evidence.append({"path": Path(rel).as_posix(), "sha256": sha256_file(path)})
    inputs = []
    for view, item in sorted(((spec.get("generation") or {}).get("views") or {}).items()):
        if not item:
            continue
        path = ctx.repo_path(item["path"])
        present = path.is_file()
        measured = sha256_file(path) if present else None
        if present and item.get("sha256") and measured != item["sha256"]:
            raise PipelineError("generation input %s changed since the Tripo task: %s" % (view, item["path"]))
        inputs.append({"view": view, "path": Path(item["path"]).as_posix(), "sha256": item.get("sha256"),
                       "present": present})
    credits_by_unit = {}
    for op in spec["operations"]:
        credits = op.get("credits") or {}
        if credits.get("observed_debit") is not None:
            credits_by_unit[credits["unit"]] = credits_by_unit.get(credits["unit"], 0) + credits["observed_debit"]
    return {
        "spec_sha256": sha256_json(spec),
        "spec": spec,
        "files": sorted(files, key=lambda f: f["role"]),
        "evidence": evidence,
        "generation_inputs": inputs,
        "historical_credits_observed": credits_by_unit,
        "registered_by": "%s %s" % (TOOL_NAME, TOOL_VERSION),
    }


def source_file(manifest: dict, source_id: str, role: str) -> dict:
    source = manifest["sources"].get(source_id)
    if not source:
        raise PipelineError("source %s is not registered" % source_id, EXIT_USAGE)
    for entry in source["files"]:
        if entry["role"] == role:
            return entry
    raise PipelineError("source %s has no file with role %s" % (source_id, role), EXIT_USAGE)


# ---------------------------------------------------------------------- profiles

def run_profile(manifest: dict) -> str:
    return manifest["config"].get("profile", PASSTHROUGH)


def base_stages(manifest: dict) -> tuple:
    return CANDIDATE_STAGES if run_profile(manifest) == CANDIDATE else STAGES


def stage_order(manifest: dict) -> tuple:
    return base_stages(manifest) + (UE_STAGE,)


def load_build_profile(ctx: "Context") -> tuple:
    rel = ctx.manifest["config"].get("build_profile")
    if not rel:
        raise PipelineError("run has no build profile (init --profile %s --build-profile ...)" % CANDIDATE, EXIT_USAGE)
    path = ctx.repo_path(rel)
    if not path.is_file():
        raise PipelineError("build profile missing: %s" % rel)
    profile = json.loads(path.read_text(encoding="utf-8"))
    if profile.get("schema") != BUILD_PROFILE_SCHEMA:
        raise PipelineError("build profile schema must be %s: %s" % (BUILD_PROFILE_SCHEMA, rel), EXIT_USAGE)
    if profile.get("asset_id") != ctx.manifest["asset_id"]:
        raise PipelineError("build profile asset %s != run asset %s" % (profile.get("asset_id"), ctx.manifest["asset_id"]),
                            EXIT_USAGE)
    return profile, path


def profile_reference_hashes(ctx: "Context", profile: dict, keys) -> dict:
    """SHA-256 of the read-only reference files a profile compares against (None if absent)."""
    out = {}
    for rel in keys:
        path = ctx.repo_path(rel)
        out[rel] = sha256_file(path) if path.is_file() else None
    return out


def candidate_export_rels(profile: dict) -> dict:
    return {"skeletal": "export/%s" % profile["exports"]["skeletal_fbx"],
            "base": "export/%s" % profile["exports"]["base_fbx"]}


def fbx_preset(ctx: "Context") -> dict:
    """The FBX preset of this run: build profile `fbx_preset` (skeletal-candidate) or UM_FBX_v1 (passthrough).

    Returns {"rel", "path", "sha256", "name", "rotation_z"}; raises when missing or not UM_FBX_v1-shaped.
    """
    if run_profile(ctx.manifest) == CANDIDATE:
        profile, _ = load_build_profile(ctx)
        rel = profile.get("fbx_preset")
        if not rel:
            raise PipelineError("build profile %s has no fbx_preset; since tool 0.4.0 every candidate FBX follows "
                                "%s (04-blender-production.md §1.1, ART-001)" % (ctx.manifest["config"]["build_profile"],
                                                                                 DEFAULT_FBX_PRESET), EXIT_USAGE)
    else:
        rel = DEFAULT_FBX_PRESET
    path = ctx.repo_path(rel)
    if not path.is_file():
        raise PipelineError("FBX preset missing: %s" % rel)
    data = json.loads(path.read_text(encoding="utf-8"))
    missing = [k for k in FBX_PRESET_KEYS if k not in data]
    if missing:
        raise PipelineError("FBX preset %s lacks %s" % (rel, missing))
    return {"rel": Path(rel).as_posix(), "path": path, "sha256": sha256_file(path), "name": data["name"],
            "rotation_z": data["export_space_rotation_z_degrees"], "use_triangles": data["use_triangles"]}


# ------------------------------------------------------------------------ stages

class StageResult:
    def __init__(self, outputs: dict, summary: dict, passed: bool, error: str | None = None):
        self.outputs = outputs  # final relpath -> staging Path
        self.summary = summary
        self.passed = passed
        self.error = error


def run_blender(ctx: Context, stage: str, params: dict, staging: Path, marker: str) -> None:
    params_path = staging / "params.json"
    params_path.write_text(dump_json(params), encoding="utf-8")
    log_path = staging / ("%s.log" % stage)
    code, text = ctx.blender.run_stage(stage, params_path, staging)
    log_path.write_text(text, encoding="utf-8")
    # Blender can exit 0 after a Python error; require the marker and no traceback.
    if code != 0 or marker not in text or re.search(r"Traceback|Error: script failed", text):
        raise PipelineError("Blender stage %s failed (%s backend, exit %s); see %s"
                            % (stage, ctx.backend, code, log_path))


def blend_rel(manifest: dict) -> str:
    return "work/%s.blend" % manifest["config"]["export_basename"]


def fbx_rel(manifest: dict) -> str:
    return "export/%s.fbx" % manifest["config"]["export_basename"]


def stage_output_sha(manifest: dict, stage: str, rel: str) -> str | None:
    rec = manifest["stages"].get(stage) or {}
    out = (rec.get("outputs") or {}).get(rel)
    return out["sha256"] if out else None


_ATLAS_DEPS = {}


def atlas_python_deps() -> dict:
    """Pillow/numpy of the Python that runs the atlas stage (checked in a subprocess; this tool stays stdlib-only)."""
    if not _ATLAS_DEPS:
        code = ("import json, platform, PIL, numpy; print(json.dumps({'python': platform.python_version(), "
                "'pillow': PIL.__version__, 'numpy': numpy.__version__}))")
        try:
            proc = subprocess.run([sys.executable, "-c", code], capture_output=True, timeout=120, **_no_window())
            data = json.loads(proc.stdout.decode("utf-8").strip() or "{}")
            _ATLAS_DEPS.update(data, ok=proc.returncode == 0 and bool(data))
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            _ATLAS_DEPS.update(ok=False, error=str(exc))
    return dict(_ATLAS_DEPS)


def fp_preflight(ctx: Context) -> dict:
    m = ctx.manifest
    try:
        blender = ctx.blender_version()
    except PipelineError:
        blender = None  # reported as a failed check by exec_preflight
    return {
        "logic": PREFLIGHT_LOGIC_VERSION,
        "tool": TOOL_VERSION,
        "blender": blender,
        "backend": ctx.backend,
        "scripts": {k: sha256_file(v) for k, v in sorted(BLENDER_SCRIPTS.items())},
        "sources": {sid: {f["role"]: f["sha256"] for f in s["files"]} for sid, s in sorted(m["sources"].items())},
        "config": m["config"],
    }


def fp_import(ctx: Context) -> dict:
    m = ctx.manifest
    primary = source_file(m, m["config"]["primary_source"], m["config"]["primary_role"])
    return {"script": sha256_file(BLENDER_SCRIPTS["import"]), "blender": ctx.blender_version(),
            "backend": ctx.backend, "source_sha256": primary["sha256"], "blend": blend_rel(m)}


def fp_verify(ctx: Context) -> dict:
    m = ctx.manifest
    primary = source_file(m, m["config"]["primary_source"], m["config"]["primary_role"])
    spec = m["sources"][m["config"]["primary_source"]]["spec"]
    return {"logic": VERIFY_LOGIC_VERSION, "source_sha256": primary["sha256"],
            "import_report": stage_output_sha(m, "import", "reports/import-report.json"),
            "expectations": (spec.get("expectations") or {}).get(m["config"]["primary_role"]),
            "tolerance": m["config"]["triangle_loss_tolerance"]}


def fp_export(ctx: Context) -> dict:
    m = ctx.manifest
    preset = fbx_preset(ctx)
    return {"script": sha256_file(BLENDER_SCRIPTS["export"]), "blender": ctx.blender_version(),
            "backend": ctx.backend, "blend": stage_output_sha(m, "import", blend_rel(m)),
            "verify_report": stage_output_sha(m, "verify", "reports/verify-report.json"),
            "fbx": fbx_rel(m), "fbx_preset": {"path": preset["rel"], "sha256": preset["sha256"]}}


def exec_preflight(ctx: Context, staging: Path) -> StageResult:
    m = ctx.manifest
    checks = {}

    def check(name, passed, **detail):
        checks[name] = dict(passed=bool(passed), **detail)

    check("python_version", sys.version_info >= (3, 10), measured=platform.python_version().rsplit(".", 1)[0])
    check("backend_known", ctx.backend in BACKENDS, measured=ctx.blender.describe())
    if ctx.backend == "mcp":
        check("blender_mcp_client_present", client_script(ctx.blender_mcp_cmd).is_file(),
              measured=client_script(ctx.blender_mcp_cmd).name)
    try:
        version = ctx.blender_version()
        check("blender_runnable", True, measured=version, backend=ctx.backend)
    except PipelineError as exc:
        check("blender_runnable", False, error=str(exc), backend=ctx.backend)
    ue_cfg = m["config"].get("ue")
    if ue_cfg:
        checks["ue_stage_runnable_with_backend"] = {
            "passed": True, "required": False, "measured": ctx.backend == "mcp",
            "note": "informational; ue-import runs only with --backend mcp (live editor via unreal_mcp.py)"}
        check("ue_folder_is_pipeline_candidate", ue_cfg["folder"].startswith(UE_ALLOWED_ROOT),
              measured=ue_cfg["folder"])
        if ctx.backend == "mcp":
            check("unreal_mcp_client_present", client_script(ctx.unreal_mcp_cmd).is_file(),
                  measured=client_script(ctx.unreal_mcp_cmd).name)
    checks["profile"] = {"passed": True, "required": False, "measured": run_profile(m)}
    if run_profile(m) == CANDIDATE:
        try:
            profile, ppath = load_build_profile(ctx)
            check("build_profile_valid", True, measured={"path": m["config"]["build_profile"],
                                                         "id": profile["profile_id"], "sha256": sha256_file(ppath)})
            check("build_profile_role_is_primary", profile["source_role"] == m["config"]["primary_role"],
                  measured=profile["source_role"], expected=m["config"]["primary_role"])
        except PipelineError as exc:
            check("build_profile_valid", False, error=str(exc))
        deps = atlas_python_deps()
        check("atlas_python_deps", deps.get("ok"), measured=deps)
        check("candidate_scripts_present", ATLAS_SCRIPT.is_file() and BLENDER_SCRIPTS["build"].is_file(),
              scripts={"atlas": sha256_file(ATLAS_SCRIPT) if ATLAS_SCRIPT.is_file() else None})
    try:
        preset = fbx_preset(ctx)
        check("fbx_preset_is_um_fbx_v1", preset["name"] == FBX_PRESET_NAME and float(preset["rotation_z"]) == 90.0
              and preset["use_triangles"] is True,
              measured={k: preset[k] for k in ("rel", "sha256", "name", "rotation_z", "use_triangles")},
              expected={"name": FBX_PRESET_NAME, "rotation_z": 90.0, "use_triangles": True},
              note="axes standard 04-blender-production.md §1 (authored -Y -> UE +X), verified by ART-001")
    except PipelineError as exc:
        check("fbx_preset_is_um_fbx_v1", False, error=str(exc))
    ue_cmd = Path(os.environ.get("TRIPO_PIPELINE_UE_ROOT", DEFAULT_UE_ROOT)) / "Engine/Binaries/Win64/UnrealEditor-Cmd.exe"
    checks["unreal_editor_cmd_present"] = {"passed": True, "required": False, "measured": ue_cmd.is_file(),
                                           "note": "informational; this scaffold never launches UnrealEditor-Cmd"}
    check("repo_root_is_git_checkout", (ctx.repo_root / ".git").exists())
    check("blender_stage_scripts_present", all(p.is_file() for p in BLENDER_SCRIPTS.values()),
          scripts={k: sha256_file(v) if v.is_file() else None for k, v in sorted(BLENDER_SCRIPTS.items())})
    check("sources_registered", bool(m["sources"]), measured=sorted(m["sources"]))
    try:
        source_file(m, m["config"]["primary_source"], m["config"]["primary_role"])
        check("primary_source_registered", True, measured="%s:%s" % (m["config"]["primary_source"], m["config"]["primary_role"]))
    except PipelineError as exc:
        check("primary_source_registered", False, error=str(exc))
    unchanged, missing, changed, inside = [], [], [], []
    for sid, src in sorted(m["sources"].items()):
        for entry in src["files"]:
            path = ctx.repo_path(entry["path"])
            tag = "%s:%s" % (sid, entry["role"])
            if not path.is_file():
                missing.append(tag)
            elif sha256_file(path) != entry["sha256"]:
                changed.append(tag)
            else:
                unchanged.append(tag)
            if is_within(path, ctx.run_dir):
                inside.append(tag)
    check("source_files_present", not missing, missing=missing)
    check("source_files_unchanged_since_registration", not changed and not missing, changed=changed,
          verified=len(unchanged))
    check("originals_outside_run_dir", not inside, offenders=inside)
    own = Path(__file__).read_text(encoding="utf-8")
    net = re.findall(r"^\s*(?:import|from)\s+(urllib|http|socket|requests|ssl|ftplib|asyncio)\b", own, re.M)
    check("tool_has_no_network_imports", not net, measured=sorted(set(net)))
    passed = all(c["passed"] for c in checks.values())
    report = {"stage": "preflight", "tool": {"name": TOOL_NAME, "version": TOOL_VERSION},
              "backend": ctx.backend, "checks": checks, "passed": passed,
              "network": {"tripo_calls": 0, "paid_tasks_created": 0}}
    out = staging / "preflight.json"
    out.write_text(dump_json(report), encoding="utf-8")
    try:
        usage = shutil.disk_usage(ctx.run_dir)
        ctx.journal("preflight_disk", free_gb=round(usage.free / 1e9, 1))
    except OSError:
        pass
    failed = sorted(k for k, c in checks.items() if not c["passed"])
    return StageResult({"reports/preflight.json": out},
                       {"passed": passed, "failed_checks": failed, "sources_verified": len(unchanged)},
                       passed, None if passed else "preflight failed: %s" % ", ".join(failed))


def exec_import(ctx: Context, staging: Path) -> StageResult:
    m = ctx.manifest
    primary = source_file(m, m["config"]["primary_source"], m["config"]["primary_role"])
    source = ctx.repo_path(primary["path"])
    if sha256_file(source) != primary["sha256"]:
        raise PipelineError("primary source changed since registration: %s" % primary["path"])
    blend = staging / "work.blend"
    report = staging / "import-report.json"
    run_blender(ctx, "import", {"source": str(source), "blend_out": str(blend), "report_out": str(report)},
                staging, "TRIPO_PIPELINE_STAGE_OK import")
    data = json.loads(report.read_text(encoding="utf-8"))
    if data["source"]["sha256"] != primary["sha256"]:
        raise PipelineError("import report refers to a different source hash")
    return StageResult({blend_rel(m): blend, "reports/import-report.json": report},
                       {"mesh_count": data["mesh_count"], "triangles_total": data["triangles_total"],
                        "materials": data["material_count"], "images": data["image_count"]}, True)


def exec_verify(ctx: Context, staging: Path) -> StageResult:
    m = ctx.manifest
    sid, role = m["config"]["primary_source"], m["config"]["primary_role"]
    primary = source_file(m, sid, role)
    spec = m["sources"][sid]["spec"]
    expect = (spec.get("expectations") or {}).get(role) or {}
    imp = json.loads(ctx.run_path("reports/import-report.json").read_text(encoding="utf-8"))
    source_path = ctx.repo_path(primary["path"])
    glb = inspect_glb(source_path)
    checks, warnings = {}, []

    def check(name, passed, measured=None, expected=None, note=None):
        item = {"passed": bool(passed), "measured": measured}
        if expected is not None:
            item["expected"] = expected
        if note:
            item["note"] = note
        checks[name] = item

    check("source_unchanged", sha256_file(source_path) == primary["sha256"], primary["sha256"])
    check("import_report_matches_source", imp["source"]["sha256"] == primary["sha256"], imp["source"]["sha256"])
    for key, measured in (("glb_mesh_count", glb["mesh_count"]), ("glb_triangles", glb["triangles"]),
                          ("glb_materials", glb["materials"]), ("glb_images", glb["images"]),
                          ("glb_skins", glb["skins"])):
        if key in expect:
            check("evidence_" + key, measured == expect[key], measured, expect[key],
                  "expected value copied from Tripo evidence JSON")
    check("blender_mesh_count_equals_glb", imp["mesh_count"] == glb["mesh_count"], imp["mesh_count"], glb["mesh_count"])
    lost = glb["triangles"] - imp["triangles_total"]
    tolerance = m["config"]["triangle_loss_tolerance"]
    per_mesh = {mesh["name"]: mesh["triangles"] for mesh in glb["meshes"]}
    deltas = {e["name"]: e["triangles"] - per_mesh.get(e["name"], 0) for e in imp["meshes"]
              if e["name"] in per_mesh and e["triangles"] != per_mesh[e["name"]]}
    check("blender_triangle_loss_within_tolerance",
          0 <= lost <= glb["triangles"] * tolerance,
          {"glb": glb["triangles"], "blender": imp["triangles_total"], "lost": lost, "per_mesh_delta": deltas},
          "<= %.3f%% of GLB triangles" % (tolerance * 100),
          "Blender glTF importer can drop degenerate/duplicate triangles; listed per mesh")
    if lost:
        warnings.append("Blender imported %d fewer triangles than the GLB declares: %s" % (lost, deltas))
    no_uv = [e["name"] for e in imp["meshes"] if not e["uv_layers"]]
    check("uv0_on_every_mesh", not no_uv, {"meshes_without_uv": no_uv})
    expected_arm = expect.get("armatures", 0)
    check("armatures_as_expected", imp["armatures"] == expected_arm, imp["armatures"], expected_arm)
    dims = imp["bounds"]["dimensions"]
    check("bounds_non_degenerate", all(d > 0 for d in dims), dims)
    diag = {e["name"]: e["diagnostic_weld_1e-7"] for e in imp["meshes"]}
    open_meshes = sorted(n for n, d in diag.items() if d["boundary_edges"] or d["non_manifold_edges"])
    if open_meshes:
        warnings.append("open/non-manifold edges after diagnostic weld in %d mesh(es); informational" % len(open_meshes))
    passed = all(c["passed"] for c in checks.values())
    report = {
        "stage": "verify",
        "logic": VERIFY_LOGIC_VERSION,
        "status": "measured" if passed else "failed",
        "source": {"source_id": sid, "role": role, "path": primary["path"], "sha256": primary["sha256"]},
        "glb_structure": {k: glb[k] for k in ("generator", "mesh_count", "triangles", "materials", "images",
                                              "skins", "animations", "primitive_modes")},
        "checks": checks,
        "passed": passed,
        "warnings": warnings,
        "diagnostics": {"bounds_source_units": imp["bounds"], "weld_1e-7_per_mesh": diag,
                        "degenerate_faces_total": sum(e["degenerate_faces"] for e in imp["meshes"])},
        "not_checked": [
            "budgets: numbers are measured only; budgets stay proposals until GD-058 is decided",
            "art acceptance, silhouette, lighting: art track",
            "rig, sockets, animation, UE import: later candidate stages",
        ],
    }
    out = staging / "verify-report.json"
    out.write_text(dump_json(report), encoding="utf-8")
    failed = sorted(k for k, c in checks.items() if not c["passed"])
    return StageResult({"reports/verify-report.json": out},
                       {"passed": passed, "failed_checks": failed, "warnings": len(warnings)},
                       passed, None if passed else "verify failed: %s" % ", ".join(failed))


def exec_export(ctx: Context, staging: Path) -> StageResult:
    m = ctx.manifest
    blend = ctx.run_path(blend_rel(m))
    fbx = staging / Path(fbx_rel(m)).name  # same file name as the final export (FBX stores it)
    report = staging / "export-report.json"
    run_blender(ctx, "export", {"blend": str(blend), "fbx_out": str(fbx), "report_out": str(report),
                                "fbx_preset": str(fbx_preset(ctx)["path"])},
                staging, "TRIPO_PIPELINE_STAGE_OK export")
    data = json.loads(report.read_text(encoding="utf-8"))
    return StageResult({fbx_rel(m): fbx, "reports/export-report.json": report},
                       {"passed": data["passed"], "fbx_sha256": sha256_file(fbx), "fbx_bytes": fbx.stat().st_size,
                        "roundtrip_triangles": data["roundtrip_reimport"]["triangles_total"]},
                       data["passed"], None if data["passed"] else "export round-trip failed")


# ------------------------------------------------- skeletal-candidate: atlas, build

def fp_atlas(ctx: Context) -> dict:
    m = ctx.manifest
    profile, ppath = load_build_profile(ctx)
    primary = source_file(m, m["config"]["primary_source"], m["config"]["primary_role"])
    refs = (profile["atlas"].get("reference_textures") or {}).values()
    deps = atlas_python_deps()
    return {"script": sha256_file(ATLAS_SCRIPT), "deps": {k: deps.get(k) for k in ("python", "pillow", "numpy")},
            "source_sha256": primary["sha256"], "profile_sha256": sha256_file(ppath),
            "references": profile_reference_hashes(ctx, profile, sorted(refs))}


def exec_atlas(ctx: Context, staging: Path) -> StageResult:
    m = ctx.manifest
    profile, ppath = load_build_profile(ctx)
    primary = source_file(m, m["config"]["primary_source"], m["config"]["primary_role"])
    source = ctx.repo_path(primary["path"])
    if sha256_file(source) != primary["sha256"]:
        raise PipelineError("primary source changed since registration: %s" % primary["path"])
    out_dir = staging / "textures"
    report = staging / "atlas-report.json"
    params = {"source": str(source), "profile": str(ppath), "out_dir": str(out_dir), "report_out": str(report),
              "repo_root": str(ctx.repo_root)}
    params_path = staging / "params.json"
    params_path.write_text(dump_json(params), encoding="utf-8")
    log_path = staging / "atlas.log"
    try:
        proc = subprocess.run([sys.executable, str(ATLAS_SCRIPT), str(params_path)], stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, timeout=ATLAS_TIMEOUT_S, **_no_window())
        code, text = proc.returncode, proc.stdout.decode("utf-8", "replace")
    except subprocess.TimeoutExpired as exc:
        code, text = -1, (exc.stdout or b"").decode("utf-8", "replace") + "\n[tripo-pipeline] TIMEOUT\n"
    log_path.write_text(text, encoding="utf-8")
    if code != 0 or "TRIPO_PIPELINE_STAGE_OK atlas" not in text or "Traceback" in text:
        raise PipelineError("atlas stage failed (exit %s); see %s" % (code, log_path))
    data = json.loads(report.read_text(encoding="utf-8"))
    outputs = {"reports/atlas-report.json": report}
    for key, info in sorted(data["files"].items()):
        path = out_dir / info["file"]
        if sha256_file(path) != info["sha256"]:
            raise PipelineError("atlas report hash mismatch for %s" % info["file"])
        outputs["textures/%s" % info["file"]] = path
    refs = {k: v.get("bytes_identical") for k, v in (data.get("reference_comparison") or {}).items()}
    return StageResult(outputs, {"passed": data["passed"], "files": {k: v["sha256"][:12] for k, v in data["files"].items()},
                                 "reference_bytes_identical": refs},
                       data["passed"], None if data["passed"] else "atlas checks failed")


def candidate_blend_rel(manifest: dict) -> str:
    return "work/%s-candidate.blend" % manifest["config"]["export_basename"]


def fp_build(ctx: Context) -> dict:
    m = ctx.manifest
    profile, ppath = load_build_profile(ctx)
    primary = source_file(m, m["config"]["primary_source"], m["config"]["primary_role"])
    atlas_outputs = (m["stages"].get("atlas") or {}).get("outputs") or {}
    ref = profile.get("reference") or {}
    return {"script": sha256_file(BLENDER_SCRIPTS["build"]), "blender": ctx.blender_version(), "backend": ctx.backend,
            "source_sha256": primary["sha256"], "profile_sha256": sha256_file(ppath),
            "atlas_outputs": {k: v["sha256"] for k, v in sorted(atlas_outputs.items())},
            "references": profile_reference_hashes(ctx, profile, sorted(v for k, v in ref.items()
                                                                        if k in ("skeletal_fbx", "base_fbx"))),
            "exports": candidate_export_rels(profile), "blend": candidate_blend_rel(m),
            "fbx_preset": {k: v for k, v in fbx_preset(ctx).items() if k in ("rel", "sha256")}}


def exec_build(ctx: Context, staging: Path) -> StageResult:
    m = ctx.manifest
    profile, ppath = load_build_profile(ctx)
    primary = source_file(m, m["config"]["primary_source"], m["config"]["primary_role"])
    source = ctx.repo_path(primary["path"])
    if sha256_file(source) != primary["sha256"]:
        raise PipelineError("primary source changed since registration: %s" % primary["path"])
    atlas_rec = m["stages"].get("atlas") or {}
    for rel, info in (atlas_rec.get("outputs") or {}).items():
        path = ctx.run_path(rel)
        if not path.is_file() or sha256_file(path) != info["sha256"]:
            raise PipelineError("atlas output missing or changed since the atlas stage: %s" % rel)
    rels = candidate_export_rels(profile)
    sk = staging / Path(rels["skeletal"]).name  # same file name as the final export
    base = staging / Path(rels["base"]).name
    blend = staging / "work.blend"
    report = staging / "build-report.json"
    params = {"source": str(source), "profile": str(ppath), "atlas_report": str(ctx.run_path("reports/atlas-report.json")),
              "textures_dir": str(ctx.run_path("textures")), "repo_root": str(ctx.repo_root),
              "blend_out": str(blend), "sk_fbx_out": str(sk), "base_fbx_out": str(base), "report_out": str(report),
              "fbx_preset": str(fbx_preset(ctx)["path"])}
    run_blender(ctx, "build", params, staging, "TRIPO_PIPELINE_STAGE_OK build")
    data = json.loads(report.read_text(encoding="utf-8"))
    for key, path in (("skeletal", sk), ("base", base)):
        if sha256_file(path) != data["exports"][key]["sha256"]:
            raise PipelineError("build report hash mismatch for %s" % path.name)
    failed = sorted(k for k, c in data["checks"].items() if not c["passed"])
    return StageResult({rels["skeletal"]: sk, rels["base"]: base, candidate_blend_rel(m): blend,
                        "reports/build-report.json": report},
                       {"passed": data["passed"], "failed_checks": failed,
                        "skeletal_fbx_sha256": data["exports"]["skeletal"]["sha256"],
                        "base_fbx_sha256": data["exports"]["base"]["sha256"],
                        "flipped_parts": data["orientation"]["flipped_parts"],
                        "export_front_axis": ((data.get("axes") or {}).get("export_frame") or {}).get("front_axis"),
                        "live_name_collisions": data.get("live_name_collisions")},
                       data["passed"], None if data["passed"] else "build checks failed: %s" % ", ".join(failed))


# ----------------------------------------------------------------- UE (MCP only)

def ue_safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", name)


def ue_package(ref) -> str:
    """'/Game/A/B.B', "StaticMesh'/Game/A/B.B'", {'refPath': ...} -> '/Game/A/B'."""
    if isinstance(ref, dict):
        ref = ref.get("refPath", "")
    ref = str(ref).strip()
    quoted = re.search(r"'(/[^']+)'", ref)
    if quoted:
        ref = quoted.group(1)
    return ref.split(":")[0].split(".")[0]


def ue_object_path(package: str) -> str:
    return "%s.%s" % (package, package.rsplit("/", 1)[-1])


def default_ue_folder(manifest: dict) -> str:
    parts = manifest["asset_id"].split("-")
    short = parts[1].title() if len(parts) >= 3 else ue_safe(manifest["asset_id"])
    return "%s%s/%s" % (UE_ALLOWED_ROOT, ue_safe(short), ue_safe(manifest["run_id"]))


def ue_listing(ue, folder: str) -> list:
    found = ue.call("asset", "find_assets", {"folder_path": folder, "name": "", "recursive": True}) or []
    return sorted(ue_package(a) for a in found)


def ue_plan(ctx: Context) -> dict:
    m = ctx.manifest
    cfg = m["config"].get("ue")
    if not cfg:
        raise PipelineError("UE stage is not configured; run `ue-import` once with --ue-folder", EXIT_USAGE)
    folder = cfg["folder"].rstrip("/")
    if not (folder + "/").startswith(UE_ALLOWED_ROOT) or ".." in folder:
        raise PipelineError("UE folder must be inside %s (never /Game/ART004 or /Game/ArtPreview): %s"
                            % (UE_ALLOWED_ROOT, folder), EXIT_USAGE)
    if run_profile(m) == CANDIDATE:
        profile, _ = load_build_profile(ctx)
        u = profile["ue"]
        names = {"skeletal": "%s/Meshes/%s" % (folder, u["skeletal_asset"]),
                 "skeleton": "%s/Meshes/%s_Skeleton" % (folder, u["skeletal_asset"]),
                 "base": "%s/Meshes/%s" % (folder, u["base_asset"]),
                 "material": "%s/Materials/%s" % (folder, u["material"])}
        for name in u["instances"]:
            names["instance:" + name] = "%s/Materials/%s" % (folder, name)
        for key, tex in u["textures"].items():
            names["texture:" + key] = "%s/Textures/%s" % (folder, tex["asset"])
        return {"folder": folder, "name": u["skeletal_asset"], "kind": "skeletal", "primary": names["skeletal"],
                "names": names, "profile": profile}
    export_report = json.loads(ctx.run_path("reports/export-report.json").read_text(encoding="utf-8"))
    kind = "skeletal" if export_report["roundtrip_reimport"]["armatures"] else "static"
    name = cfg.get("asset_name") or "%s_%s" % ("SK" if kind == "skeletal" else "SM",
                                               ue_safe(m["config"]["export_basename"]))
    return {"folder": folder, "name": name, "kind": kind, "primary": "%s/%s" % (folder, name),
            "export_report": export_report}


def fp_ue_import(ctx: Context) -> dict:
    m = ctx.manifest
    if run_profile(m) == CANDIDATE:
        profile, ppath = load_build_profile(ctx)
        outs = {}
        for stage in ("atlas", "build"):
            outs.update({k: v["sha256"] for k, v in ((m["stages"].get(stage) or {}).get("outputs") or {}).items()
                         if not k.startswith("work/")})
        return {"logic": UE_CANDIDATE_LOGIC_VERSION, "backend": ctx.backend, "ue": m["config"].get("ue"),
                "profile_sha256": sha256_file(ppath), "inputs": dict(sorted(outs.items()))}
    return {"logic": UE_IMPORT_LOGIC_VERSION, "backend": ctx.backend, "ue": m["config"].get("ue"),
            "fbx": stage_output_sha(m, "export", fbx_rel(m)),
            "export_report": stage_output_sha(m, "export", "reports/export-report.json")}


def probe_ue_import(ctx: Context, rec: dict) -> bool:
    """A completed UE stage is only up to date if the editor still has exactly our assets."""
    ue = ctx.unreal()
    plan = ue_plan(ctx)
    owned = sorted(rec.get("ue_owned_assets") or [])
    listing = ue_listing(ue, plan["folder"])
    intact = bool(ue.call("asset", "exists", {"path": plan["primary"]})) and listing == owned
    if not intact:
        ctx.journal("ue_probe_mismatch", expected=owned, found=listing)
    return intact


def within(measured, expected, tolerance) -> bool:
    return expected is not None and measured is not None and abs(measured - expected) <= abs(expected) * tolerance


UE_DELETE_RANK = {"MaterialInstanceConstant": 0, "SkeletalMesh": 1, "StaticMesh": 1, "PhysicsAsset": 1,
                  "Skeleton": 2, "Material": 3, "Texture2D": 4}


def ue_delete_owned(ue, assets) -> list:
    """Delete this run's previous assets, referencers first (UE 5.8 MCP `delete` force-deletes and
    nulls references, so the order only avoids transient dangling references)."""
    ranked = []
    for asset in assets:
        try:
            cls = str(ue.call("asset", "get_asset_class", {"asset_path": asset})).rsplit(".", 1)[-1]
        except PipelineError:
            cls = "?"
        ranked.append((UE_DELETE_RANK.get(cls, 1), asset))
    deleted = []
    for _rank, asset in sorted(ranked):
        if not ue.call("asset", "delete", {"path": asset}):
            raise PipelineError("UE refused to delete our previous asset %s" % asset)
        deleted.append(asset)
    return deleted


def exec_ue_import(ctx: Context, staging: Path) -> StageResult:
    m = ctx.manifest
    if run_profile(m) == CANDIDATE:
        return exec_ue_candidate(ctx, staging)
    ue = ctx.unreal()
    cfg = m["config"]["ue"]
    rec = m["stages"][UE_STAGE]
    fbx = ctx.run_path(fbx_rel(m))
    fbx_sha = stage_output_sha(m, "export", fbx_rel(m))
    if not fbx.is_file() or sha256_file(fbx) != fbx_sha:
        raise PipelineError("exported FBX missing or changed since the export stage: %s" % fbx)
    plan = ue_plan(ctx)
    folder, primary, kind = plan["folder"], plan["primary"], plan["kind"]
    roundtrip = plan["export_report"]["roundtrip_reimport"]
    owned = set(rec.get("ue_owned_assets") or [])
    before = ue_listing(ue, folder)
    foreign = [a for a in before if a not in owned]
    if foreign:
        raise PipelineError("UE folder %s holds assets this run did not create: %s; refusing to delete or "
                            "import next to them (use another --ue-folder)" % (folder, foreign[:10]), EXIT_CONFLICT)
    # All ours: remove so the re-import cannot collide (UE 5.8 MCP import_file refuses an existing
    # name; other importers create *_1 duplicates) or leave stale leftovers.
    deleted = ue_delete_owned(ue, before)
    rec["ue_owned_assets"] = []
    ctx.save()
    args = {"folder_path": folder, "asset_name": plan["name"], "source_file": str(fbx),
            "import_materials": bool(cfg.get("import_materials", True)),
            "import_textures": bool(cfg.get("import_textures", True))}
    if kind == "static":
        args["combine_meshes"] = True
    else:
        args.update(import_animations=False, create_physics_asset=False)
    created = sorted({ue_package(r) for r in (ue.call(kind, "import_file", args) or [])})
    after = ue_listing(ue, folder)
    # Persist ownership immediately: a crash after this point is cleaned up by the next attempt.
    rec["ue_owned_assets"] = sorted(set(after) | set(created))
    ctx.save()
    ctx.journal("ue_assets_owned", assets=rec["ue_owned_assets"], deleted_previous=deleted)

    checks = {}

    def check(name, passed, measured=None, expected=None, note=None):
        item = {"passed": bool(passed), "measured": measured}
        if expected is not None:
            item["expected"] = expected
        if note:
            item["note"] = note
        checks[name] = item

    check("primary_asset_created", primary in after, primary)
    dupes = [a for a in after if re.fullmatch(re.escape(primary) + r"_\d+", a)]
    check("no_numbered_duplicates", not dupes, dupes)
    check("folder_contains_only_this_import", set(after) == set(created), {"folder": after, "import": created},
          note="no stale assets from earlier attempts")
    asset_class = ue.call("asset", "get_asset_class", {"asset_path": primary})
    expected_class = "SkeletalMesh" if kind == "skeletal" else "StaticMesh"
    check("asset_class", str(asset_class).rsplit(".", 1)[-1] == expected_class, asset_class, expected_class)
    mesh_ref = {"mesh": {"refPath": ue_object_path(primary)}}
    measured = {"kind": kind}
    slots = ue.call(kind, "get_material_slots", mesh_ref) or []
    measured["material_slots"] = slots
    check("material_slots_equal_blender_materials", len(slots) == roundtrip["material_count"], len(slots),
          roundtrip["material_count"])
    bounds = ue.call(kind, "get_bounds", mesh_ref) or {}
    if "boxExtent" in bounds:
        size = [2.0 * bounds["boxExtent"][k] for k in ("x", "y", "z")]
    else:
        size = [bounds["max"][k] - bounds["min"][k] for k in ("x", "y", "z")] if bounds else None
    measured["bounds"] = bounds
    measured["size_uu"] = [round(v, 3) for v in size] if size else None
    expected_size = plan["export_report"]["expected_ue_dimensions_uu_at_import_scale_1"]
    tol = cfg.get("dimension_tolerance", DEFAULT_UE_DIMENSION_TOLERANCE)
    if size:
        # The export report gives the size per UE axis (UM_FBX_v1 export frame; UE only flips the sign of Y).
        check("dimensions_match_blender_at_import_scale_1", all(within(a, b, tol) for a, b in zip(size, expected_size)),
              measured["size_uu"], expected_size, "tolerance %.1f%%; per axis X, Y, Z (UM_FBX_v1 export frame)"
              % (tol * 100))
    else:
        check("dimensions_match_blender_at_import_scale_1", False, None, expected_size, "no bounds returned")
    if kind == "static":
        tris = ue.call("static", "get_triangle_count", dict(mesh_ref, lod_index=0))
        measured["triangles_lod0"] = tris
        measured["vertices_lod0"] = ue.call("static", "get_vertex_count", dict(mesh_ref, lod_index=0))
        check("triangles_equal_blender_roundtrip", within(tris, roundtrip["triangles_total"],
                                                          m["config"]["triangle_loss_tolerance"]),
              tris, roundtrip["triangles_total"])
    else:
        measured["bones"] = ue.call("skeletal", "get_bone_names", mesh_ref)
        measured["sockets"] = ue.call("skeletal", "get_socket_names", mesh_ref)
        measured["vertices_lod0"] = ue.call("skeletal", "get_vertex_count", dict(mesh_ref, lod_index=0))
    saved = ue.call("asset", "save_assets", {"asset_paths": after})
    check("assets_saved", saved is True or saved == [True] or bool(saved), saved)
    passed = all(c["passed"] for c in checks.values())
    report = {
        "stage": UE_STAGE,
        "logic": UE_IMPORT_LOGIC_VERSION,
        "backend": ue.describe(),
        "status": "technically_imported" if passed else "failed",
        "fbx": {"path": fbx_rel(m), "sha256": fbx_sha},
        "destination": {"folder": folder, "primary_asset": primary, "kind": kind},
        "previous_assets_deleted": deleted,
        "assets": after,
        "import_args": args,
        "measured": measured,
        "checks": checks,
        "passed": passed,
        "tool_name_style": ue.tool_name_style,
        "not_checked": [
            "art acceptance, silhouette, lighting (art track)",
            "budgets: measured numbers are not budgets until GD-058 is decided",
            "BC/N/ORM material contract: this passthrough imports Tripo materials as-is",
            "facing: this passthrough path has not been imported into the live UE yet (T3/T4 ran only the "
            "skeletal-candidate profile live); the per-axis size check relies on the ART-001 axis mapping",
        ],
    }
    out = staging / "ue-import-report.json"
    out.write_text(dump_json(report), encoding="utf-8")
    calls = staging / "ue-mcp-calls.json"
    calls.write_text(dump_json(ue.calls), encoding="utf-8")
    failed = sorted(k for k, c in checks.items() if not c["passed"])
    return StageResult({"reports/ue-import-report.json": out, "reports/ue-mcp-calls.json": calls},
                       {"passed": passed, "failed_checks": failed, "primary_asset": primary, "kind": kind,
                        "assets": len(after)},
                       passed, None if passed else "ue-import failed: %s" % ", ".join(failed))


def ue_obj(package: str) -> dict:
    return {"refPath": ue_object_path(package)}


def ue_minmax(bounds: dict):
    if not bounds:
        return None, None
    if "boxExtent" in bounds:
        o, e = bounds["origin"], bounds["boxExtent"]
        return [o[k] - e[k] for k in "xyz"], [o[k] + e[k] for k in "xyz"]
    return [bounds["min"][k] for k in "xyz"], [bounds["max"][k] for k in "xyz"]


# 2x2 maps of Blender (x, y) onto UE (x, y); z is up in both. Named by where Blender -Y (front) lands.
AXIS_MAPS = [((1, 0), (0, 1)), ((1, 0), (0, -1)), ((-1, 0), (0, 1)), ((-1, 0), (0, -1)),
             ((0, 1), (1, 0)), ((0, 1), (-1, 0)), ((0, -1), (1, 0)), ((0, -1), (-1, 0))]


def map_xy(mat, x, y):
    return (mat[0][0] * x + mat[0][1] * y, mat[1][0] * x + mat[1][1] * y)


def match_axis_map(lo_b, hi_b, lo_u, hi_u, tol):
    """Which axis map turns the Blender bounds (cm) into the UE bounds (uu)?"""
    found = []
    for mat in AXIS_MAPS:
        pts = [map_xy(mat, x, y) for x in (lo_b[0], hi_b[0]) for y in (lo_b[1], hi_b[1])]
        pred_lo = [min(p[0] for p in pts), min(p[1] for p in pts), lo_b[2]]
        pred_hi = [max(p[0] for p in pts), max(p[1] for p in pts), hi_b[2]]
        err = max(max(abs(a - b) for a, b in zip(pred_lo, lo_u)), max(abs(a - b) for a, b in zip(pred_hi, hi_u)))
        if err <= tol:
            front = map_xy(mat, 0, -1)
            axis = {(1, 0): "+X", (-1, 0): "-X", (0, 1): "+Y", (0, -1): "-Y"}[front]
            found.append({"map": "ue(x,y)=(%+dx%+dy, %+dx%+dy)" % (mat[0][0], mat[0][1], mat[1][0], mat[1][1]),
                          "blender_front_minus_y_becomes": axis, "max_error_uu": round(err, 4)})
    return found


AXIS_NAMES = {(1, 0): "+X", (-1, 0): "-X", (0, 1): "+Y", (0, -1): "-Y"}
AXIS_VECTORS = {v: k for k, v in AXIS_NAMES.items()}


def match_xy_map(lo_a, hi_a, lo_b, hi_b, tol):
    """Which of the 8 axis maps turns bounds A (x, y) into bounds B (both UE, z unchanged)?"""
    found = []
    for mat in AXIS_MAPS:
        pts = [map_xy(mat, x, y) for x in (lo_a[0], hi_a[0]) for y in (lo_a[1], hi_a[1])]
        pred_lo = [min(p[0] for p in pts), min(p[1] for p in pts), lo_a[2]]
        pred_hi = [max(p[0] for p in pts), max(p[1] for p in pts), hi_a[2]]
        err = max(max(abs(a - b) for a, b in zip(pred_lo, lo_b)), max(abs(a - b) for a, b in zip(pred_hi, hi_b)))
        if err <= tol:
            found.append({"map": "b(x,y)=(%+dx%+dy, %+dx%+dy)" % (mat[0][0], mat[0][1], mat[1][0], mat[1][1]),
                          "maps_axis": {name: AXIS_NAMES[map_xy(mat, *vec)] for vec, name in AXIS_NAMES.items()},
                          "max_error_uu": round(err, 4)})
    return found


def exec_ue_candidate(ctx: Context, staging: Path) -> StageResult:
    m = ctx.manifest
    ue = ctx.unreal()
    rec = m["stages"][UE_STAGE]
    plan = ue_plan(ctx)
    profile, names, folder = plan["profile"], plan["names"], plan["folder"]
    u = profile["ue"]
    build = json.loads(ctx.run_path("reports/build-report.json").read_text(encoding="utf-8"))
    atlas = json.loads(ctx.run_path("reports/atlas-report.json").read_text(encoding="utf-8"))
    rels = candidate_export_rels(profile)
    inputs = {}
    for stage in ("atlas", "build"):
        for rel, info in ((m["stages"].get(stage) or {}).get("outputs") or {}).items():
            if rel.startswith("work/"):
                continue
            path = ctx.run_path(rel)
            if not path.is_file() or sha256_file(path) != info["sha256"]:
                raise PipelineError("%s output missing or changed since the %s stage: %s" % (stage, stage, rel))
            inputs[rel] = info["sha256"]

    owned = set(rec.get("ue_owned_assets") or [])
    before = ue_listing(ue, folder)
    foreign = [a for a in before if a not in owned]
    if foreign:
        raise PipelineError("UE folder %s holds assets this run did not create: %s; refusing to delete or "
                            "import next to them (use another --ue-folder)" % (folder, foreign[:10]), EXIT_CONFLICT)
    deleted = ue_delete_owned(ue, before)
    rec["ue_owned_assets"] = []
    ctx.save()
    try:
        log_before = len(ue.call("logs", "GetLogEntries", {"category": "LogFbx", "pattern": "", "maxEntries": 0}) or [])
    except PipelineError:
        log_before = None
    created = []

    def track(result):
        items = result if isinstance(result, list) else [result]
        created.extend(ue_package(x) for x in items if x)

    def setp(ref, props):
        return ue.call("object", "set_properties", {"instance": ref, "values": json.dumps(props)})

    def getp(ref, props):
        raw = ue.call("object", "get_properties", {"instance": ref, "properties": props})
        return json.loads(raw) if isinstance(raw, str) else raw

    # textures (the DirectX normal and linear ORM are imported from the atlas stage files)
    tex_files = {k: v["file"] for k, v in atlas["files"].items()}
    for key, tcfg in sorted(u["textures"].items()):
        pkg = names["texture:" + key]
        track(ue.call("texture", "import_file", {"folder_path": pkg.rsplit("/", 1)[0], "asset_name": tcfg["asset"],
                                                 "source_file": str(ctx.run_path("textures/" + tex_files[tcfg["file_key"]]))}))
        props = {"SRGB": tcfg["srgb"], "CompressionSettings": tcfg["compression"]}
        if "flip_green" in tcfg:
            props["bFlipGreenChannel"] = tcfg["flip_green"]
        setp(ue_obj(pkg), props)
    # material: BC x TeamColor, DirectX normal, ORM (R AO, G roughness, B metallic)
    mat_pkg = names["material"]
    track(ue.call("material", "create_material", {"folder_path": mat_pkg.rsplit("/", 1)[0], "asset_name": u["material"]}))
    mat = ue_obj(mat_pkg)

    def expr(cls, x, y, props=None):
        ref = ue.call("material", "add_expression", {"material_or_function": mat, "x": x, "y": y,
                                                     "expression_class": {"refPath": "/Script/Engine." + cls}})
        if props:
            setp(ref, props)
        return ref

    tex_path = {k: ue_object_path(names["texture:" + k]) for k in u["textures"]}
    bc = expr("MaterialExpressionTextureSampleParameter2D", -800, 0,
              {"ParameterName": "BaseColorTexture", "Texture": tex_path["BC"], "SamplerType": "SAMPLERTYPE_Color"})
    team = expr("MaterialExpressionVectorParameter", -800, 220,
                {"ParameterName": "TeamColor", "DefaultValue": {"R": 1, "G": 1, "B": 1, "A": 1}})
    mul = expr("MaterialExpressionMultiply", -480, 60)
    nrm = expr("MaterialExpressionTextureSampleParameter2D", -800, 420,
               {"ParameterName": "NormalTexture", "Texture": tex_path["N"], "SamplerType": "SAMPLERTYPE_Normal"})
    orm = expr("MaterialExpressionTextureSampleParameter2D", -800, 680,
               {"ParameterName": "ORMTexture", "Texture": tex_path["ORM"], "SamplerType": "SAMPLERTYPE_Masks"})
    ue.call("material", "connect_expressions", {"from_expression": bc, "from_output_name": "RGB",
                                                "to_expression": mul, "to_input_name": "A"})
    ue.call("material", "connect_expressions", {"from_expression": team, "from_output_name": "",
                                                "to_expression": mul, "to_input_name": "B"})
    wiring = {"MP_BaseColor": (mul, ""), "MP_Normal": (nrm, "RGB"), "MP_AmbientOcclusion": (orm, "R"),
              "MP_Roughness": (orm, "G"), "MP_Metallic": (orm, "B")}
    for prop, (ref, out) in wiring.items():
        ue.call("material", "connect_to_output", {"expression": ref, "output_name": out, "material_property": prop})
    setp(mat, {"bUsedWithSkeletalMesh": True})
    ue.call("material", "recompile", {"material_or_function": mat})
    for name, color in sorted(u["instances"].items()):
        pkg = names["instance:" + name]
        track(ue.call("instance", "create", {"folder_path": pkg.rsplit("/", 1)[0], "asset_name": name, "parent": mat}))
        ue.call("instance", "set_vector_parameter", {"instance": ue_obj(pkg), "name": "TeamColor",
                                                     "value": dict(zip("rgba", color))})
    # meshes
    sk_pkg, base_pkg = names["skeletal"], names["base"]
    track(ue.call("skeletal", "import_file", {"folder_path": sk_pkg.rsplit("/", 1)[0], "asset_name": u["skeletal_asset"],
                                              "source_file": str(ctx.run_path(rels["skeletal"])),
                                              "import_materials": False, "import_textures": False,
                                              "import_animations": False, "create_physics_asset": False}))
    track(ue.call("static", "import_file", {"folder_path": base_pkg.rsplit("/", 1)[0], "asset_name": u["base_asset"],
                                            "source_file": str(ctx.run_path(rels["base"])),
                                            "import_materials": False, "import_textures": False, "combine_meshes": True}))
    after = ue_listing(ue, folder)
    rec["ue_owned_assets"] = sorted(set(after) | set(created))
    ctx.save()
    ctx.journal("ue_assets_owned", assets=rec["ue_owned_assets"], deleted_previous=deleted)
    fbx_log = []
    if log_before is not None:
        try:
            entries = ue.call("logs", "GetLogEntries", {"category": "LogFbx", "pattern": "", "maxEntries": 0}) or []
            fbx_log = [re.sub(r"^\[[^\]]*\]\[[^\]]*\]", "", e) for e in entries[log_before:]]
        except PipelineError:
            fbx_log = None
    sk, base = ue_obj(sk_pkg), ue_obj(base_pkg)
    default_mi = ue_obj(names["instance:" + u["default_instance"]])
    sk_slots = ue.call("skeletal", "get_material_slots", {"mesh": sk}) or []
    for slot in sk_slots:
        ue.call("skeletal", "set_material", {"mesh": sk, "slot_name": slot, "material": default_mi})
    base_slots = ue.call("static", "get_material_slots", {"mesh": base}) or []
    for slot in base_slots:
        ue.call("static", "set_material", {"mesh": base, "slot_name": slot, "material": default_mi})
    for sock in ue.call("skeletal", "get_socket_names", {"mesh": sk}) or []:
        ue.call("skeletal", "remove_socket", {"mesh": sk, "socket_name": sock})
    for sock in profile["sockets"]:
        ue.call("skeletal", "add_socket", {"mesh": sk, "socket_name": sock["name"], "bone_name": sock["bone"]})
        x, y, z = sock["location_uu"]
        ue.call("skeletal", "set_socket_transform", {"mesh": sk, "socket_name": sock["name"], "transform": {
            "location": {"x": x, "y": y, "z": z}, "rotation": {"pitch": 0, "yaw": 0, "roll": 0},
            "scale": {"x": 1, "y": 1, "z": 1}}})
    saved = ue.call("asset", "save_assets", {"asset_paths": after})

    # ---------------------------------------------------------------- measurements
    checks, measured, proposals = {}, {}, {}

    def check(name, passed, value=None, expected=None, note=None):
        item = {"passed": bool(passed), "measured": value}
        if expected is not None:
            item["expected"] = expected
        if note:
            item["note"] = note
        checks[name] = item

    expected_assets = sorted(names.values())
    check("assets_exactly_as_planned", sorted(after) == expected_assets, after, expected_assets,
          "no stale assets, no extra imports")
    dupes = [a for a in after if re.search(r"_\d+$", a) and re.sub(r"_\d+$", "", a) in expected_assets]
    check("no_numbered_duplicates", not dupes, dupes)
    classes = {}
    for key, pkg in sorted(names.items()):
        classes[key] = str(ue.call("asset", "get_asset_class", {"asset_path": pkg})).rsplit(".", 1)[-1]
    want = {"skeletal": "SkeletalMesh", "skeleton": "Skeleton", "base": "StaticMesh", "material": "Material"}
    want.update({k: "MaterialInstanceConstant" for k in names if k.startswith("instance:")})
    want.update({k: "Texture2D" for k in names if k.startswith("texture:")})
    check("asset_classes", classes == want, classes, want)
    tex = {}
    for key, tcfg in sorted(u["textures"].items()):
        ref = ue_obj(names["texture:" + key])
        size = ue.call("texture", "get_size", {"texture": ref}) or {}
        props = getp(ref, ["SRGB", "CompressionSettings", "bFlipGreenChannel"])
        tex[key] = {"size": [size.get("x"), size.get("y")], "properties": props}
        want_p = {"SRGB": tcfg["srgb"], "CompressionSettings": tcfg["compression"]}
        if "flip_green" in tcfg:
            want_p["bFlipGreenChannel"] = tcfg["flip_green"]
        tex[key]["ok"] = (tex[key]["size"] == [atlas["size"]] * 2 and
                          all(props.get(k) == v for k, v in want_p.items()))
    measured["textures"] = tex
    check("textures_size_colour_space_compression", all(t["ok"] for t in tex.values()), tex,
          {k: {"size": [atlas["size"]] * 2, "SRGB": c["srgb"], "CompressionSettings": c["compression"]}
           for k, c in u["textures"].items()})
    graph = {}
    for prop, (ref, out) in wiring.items():
        src = ue.call("material", "get_property_input", {"material": mat, "material_property": prop}) or {}
        graph[prop] = {"expression": (src.get("expression") or {}).get("refPath", "").rsplit(":", 1)[-1],
                       "output": src.get("output_name"),
                       "ok": (src.get("expression") or {}).get("refPath") == ref.get("refPath") and
                             (src.get("output_name") or "") == out}
    samplers = {k: getp(v, ["ParameterName", "Texture", "SamplerType"]) for k, v in
                (("BC", bc), ("N", nrm), ("ORM", orm))}
    mat_props = getp(mat, ["bUsedWithSkeletalMesh", "TwoSided", "BlendMode", "ShadingModel"])
    measured["material"] = {"outputs": graph, "samplers": samplers, "properties": mat_props}
    check("material_graph_bc_teamcolor_normal_orm", all(g["ok"] for g in graph.values()) and
          mat_props.get("bUsedWithSkeletalMesh") is True and mat_props.get("BlendMode") == "BLEND_Opaque",
          measured["material"])
    inst = {}
    for name, color in sorted(u["instances"].items()):
        ref = ue_obj(names["instance:" + name])
        value = ue.call("instance", "get_vector_parameter", {"instance": ref, "name": "TeamColor"}) or {}
        parent = getp(ref, ["Parent"]).get("Parent")
        parent = parent.get("refPath") if isinstance(parent, dict) else parent
        inst[name] = {"TeamColor": {k: round(float(value.get(k, -1)), 4) for k in "rgba"},
                      "parent": parent, "ok": all(abs(float(value.get(k, -1)) - c) < 1e-3 for k, c in zip("rgba", color))
                      and ue_package(parent or "") == mat_pkg}
    check("team_color_instances", all(i["ok"] for i in inst.values()), inst)

    bones = ue.call("skeletal", "get_bone_names", {"mesh": sk}) or []
    want_bones = [b[0].replace(".", "_") for b in profile["armature"]["bones"]]
    extra = [b for b in bones if b not in want_bones]
    parents = {b: ue.call("skeletal", "get_bone_parent", {"mesh": sk, "bone_name": b}) for b in bones}
    want_parent = {b[0].replace(".", "_"): (b[1] or "").replace(".", "_") for b in profile["armature"]["bones"]}
    armature_node = profile["armature"]["object"]
    root = profile["armature"]["bones"][0][0]
    hierarchy_ok = all(parents.get(b) == p for b, p in want_parent.items() if b != root)
    root_parent = parents.get(root)
    measured["skeleton"] = {"bones_in_order": bones, "count": len(bones), "bone0": bones[0] if bones else None,
                            "root_parent": root_parent, "extra_bones": extra}
    check("bones_profile_17_present_with_hierarchy", all(b in bones for b in want_bones) and hierarchy_ok,
          {"profile_bones_found": sum(b in bones for b in want_bones), "hierarchy_ok": hierarchy_ok},
          len(want_bones))
    check("bone0_is_armature_object_node", bones[:1] == [armature_node] and extra == [armature_node]
          and root_parent == armature_node, measured["skeleton"],
          {"bone0": armature_node, "total": len(want_bones) + 1},
          "legacy FBX importer turns the Blender armature object into bone 0 (same as /Game/ART004 and v2 imports); "
          "root motion is read from this bone (ue-pipeline-traps)")
    sk_bounds = ue.call("skeletal", "get_bounds", {"mesh": sk}) or {}
    lo_u, hi_u = ue_minmax(sk_bounds)
    exp_b = build["expected_ue_bounds_uu_at_import_scale_1"]["skeletal_blender_axes"]
    tol = m["config"]["ue"].get("dimension_tolerance") or DEFAULT_UE_DIMENSION_TOLERANCE
    tol_uu = max(0.05, tol)  # absolute uu; bounds are exact copies of the FBX data
    maps = match_axis_map(exp_b["min"], exp_b["max"], lo_u, hi_u, tol_uu) if lo_u else []
    measured["skeletal_bounds_uu"] = {"min": [round(v, 4) for v in lo_u], "max": [round(v, 4) for v in hi_u]} if lo_u else None
    measured["axis_mapping"] = maps
    check("skeletal_bounds_match_build_under_one_axis_map", len(maps) == 1, maps,
          note="authored Blender bounds from the build report (cm, front -Y) mapped onto UE bounds, "
               "tolerance %.2f uu" % tol_uu)
    front = maps[0]["blender_front_minus_y_becomes"] if len(maps) == 1 else None
    axes_cfg = profile.get("axes") or {}
    want_front = axes_cfg.get("expected_ue_front")
    check("front_axis_as_fbx_preset", want_front is not None and front == want_front,
          {"authored_front_minus_y_becomes": front}, want_front,
          axes_cfg.get("expected_ue_front_source") or "profile axes.expected_ue_front")
    predicted = build["expected_ue_bounds_uu_at_import_scale_1"].get("skeletal_ue_predicted")
    check("skeletal_bounds_equal_um_fbx_v1_prediction", bool(predicted and lo_u) and
          all(abs(a - b) <= tol_uu for a, b in zip(predicted["min"] + predicted["max"], lo_u + hi_u)),
          measured["skeletal_bounds_uu"], predicted,
          "build report: export-frame bounds mapped as UE (x, -y, z) (ART-001); tolerance %.2f uu" % tol_uu)
    height_uu = profile["scale"]["figure_height_m"] * 100.0
    check("skeletal_top_at_figure_height", hi_u is not None and abs(hi_u[2] - height_uu) <= tol_uu,
          round(hi_u[2], 4) if hi_u else None, height_uu)
    ref_cfg = u.get("reference_skeletal_for_axes")
    if isinstance(ref_cfg, str):
        ref_cfg = {"asset": ref_cfg}
    if ref_cfg:
        ref_asset = ref_cfg["asset"]
        try:
            present = bool(ue.call("asset", "exists", {"path": ref_asset}))
            r_lo, r_hi = ue_minmax(ue.call("skeletal", "get_bounds", {"mesh": ue_obj(ref_asset)}) or {}) \
                if present else (None, None)
            relation = match_xy_map(r_lo, r_hi, lo_u, hi_u, tol_uu) if (r_lo and lo_u) else []
            ref_front = ref_cfg.get("ue_front")
            ref_front_in_candidate = [rel["maps_axis"].get(ref_front) for rel in relation] if ref_front else []
            measured["reference"] = {"asset": ref_asset, "present": present,
                                     "min": [round(v, 4) for v in r_lo] if r_lo else None,
                                     "max": [round(v, 4) for v in r_hi] if r_hi else None,
                                     "reference_ue_front": ref_front, "maps_reference_onto_candidate": relation,
                                     "reference_front_lands_on": ref_front_in_candidate}
            check("reference_front_lands_on_candidate_front",
                  present and len(relation) == 1 and ref_front_in_candidate == [want_front], measured["reference"],
                  {"unique_map": True, "reference_front_lands_on": want_front},
                  "read-only get_bounds of %s (same Tripo geometry; its front %s is %s)"
                  % (ref_asset, ref_front, ref_cfg.get("ue_front_status") or "measured"))
        except PipelineError as exc:
            measured["reference"] = {"asset": ref_asset, "error": str(exc)[:300]}
            check("reference_front_lands_on_candidate_front", False, measured["reference"])
    slot_mats = {s: ue_package(ue.call("skeletal", "get_material", {"mesh": sk, "slot_name": s}) or "")
                 for s in sk_slots}
    want_slots = build["checks"]["roundtrip_material_slots"]["measured"]["skeletal_unique"]
    check("skeletal_material_slots", sorted(sk_slots) == sorted(want_slots) and
          all(v == names["instance:" + u["default_instance"]] for v in slot_mats.values()),
          {"slots": sk_slots, "assigned": slot_mats}, want_slots)
    measured["skeletal_lod0"] = {"sections": ue.call("skeletal", "get_section_count", {"mesh": sk, "lod_index": 0}),
                                 "vertices": ue.call("skeletal", "get_vertex_count", {"mesh": sk, "lod_index": 0}),
                                 "lods": ue.call("skeletal", "get_lod_count", {"mesh": sk}),
                                 "triangles": "not measured: SkeletalMeshTools has no triangle count"}
    sockets = ue.call("skeletal", "get_socket_names", {"mesh": sk}) or []
    sock_detail = {}
    for s in sockets:
        sock_detail[s] = {"bone": ue.call("skeletal", "get_socket_bone", {"mesh": sk, "socket_name": s}),
                          "transform": ue.call("skeletal", "get_socket_transform", {"mesh": sk, "socket_name": s})}
    sock_ok = sockets == [s["name"] for s in profile["sockets"]] and all(
        sock_detail[s["name"]]["bone"] == s["bone"] and
        all(abs(sock_detail[s["name"]]["transform"]["location"][k] - v) < 1e-4
            for k, v in zip("xyz", s["location_uu"])) for s in profile["sockets"])
    check("sockets_weapon_head", sock_ok, sock_detail, {s["name"]: s for s in profile["sockets"]})
    base_tris = ue.call("static", "get_triangle_count", {"mesh": base, "lod_index": 0})
    base_bounds = ue.call("static", "get_bounds", {"mesh": base}) or {}
    b_lo, b_hi = ue_minmax(base_bounds)
    fx, fy, fz = [v * 100.0 for v in profile["meshes"]["base"]["footprint_m"]]
    base_name = profile["meshes"]["base"]["object"]
    base_pre = build["meshes_pre_export_m"][base_name]
    want_base_tris = base_pre["triangles"] - base_pre.get("near_degenerate_triangles", 0)
    base_mat = {s: ue_package(ue.call("static", "get_material", {"mesh": base, "slot_name": s}) or "") for s in base_slots}
    measured["base"] = {"triangles_lod0": base_tris, "min": [round(v, 4) for v in b_lo] if b_lo else None,
                        "max": [round(v, 4) for v in b_hi] if b_hi else None, "slots": base_mat,
                        "vertices_lod0": ue.call("static", "get_vertex_count", {"mesh": base, "lod_index": 0})}
    check("base_triangles", base_tris == want_base_tris, base_tris, want_base_tris,
          "Blender %d minus %d near-degenerate slivers (area < %s cm2) that UE's mesh build removes"
          % (base_pre["triangles"], base_pre.get("near_degenerate_triangles", 0),
             base_pre.get("near_degenerate_area_cm2_below")))
    check("base_footprint_pivot", b_lo is not None and
          all(abs(a - b) <= tol_uu for a, b in zip(b_lo + b_hi, [-fx / 2, -fy / 2, 0, fx / 2, fy / 2, fz])),
          measured["base"], {"min": [-fx / 2, -fy / 2, 0], "max": [fx / 2, fy / 2, fz]})
    check("base_material_slot", len(base_slots) == profile["expectations"]["base_material_slots"] and
          all(v == names["instance:" + u["default_instance"]] for v in base_mat.values()), base_mat)
    dirty = {a: ue.call("asset", "is_dirty", {"asset_path": a}) for a in after}
    check("assets_saved", bool(saved) and not any(dirty.values()), {"save_assets": saved, "dirty": dirty})
    measured["fbx_import_log"] = fbx_log

    # comparisons with proposals (never pass/fail the stage; GD-058 is open)
    lim = profile.get("proposed_limits_for_comparison_only") or {}
    sk_tris = sum(build["roundtrip"]["skeletal"]["meshes"][n]["triangles"] for n in build["roundtrip"]["skeletal"]["meshes"])
    all_tris = sk_tris + (base_tris or 0)
    proposals = {
        "source": lim.get("source"),
        "hero_triangles": {"measured_skeletal": sk_tris, "measured_with_base": all_tris,
                           "proposed": lim.get("hero_triangles"),
                           "within": bool(lim.get("hero_triangles")) and lim["hero_triangles"][0] <= all_tris <= lim["hero_triangles"][1]},
        "material_slots": {"measured_skeletal": len(sk_slots), "measured_base": len(base_slots),
                           "proposed_max": lim.get("material_slots_max"),
                           "within": len(sk_slots) <= lim.get("material_slots_max", 99)},
        "texture_px": {"measured": atlas["size"], "proposed": lim.get("texture_px")},
        "height_uu": {"measured": round(hi_u[2], 3) if hi_u else None, "proposed": lim.get("height_uu"),
                      "within": bool(hi_u) and lim.get("height_uu", [0, 0])[0] <= hi_u[2] <= lim.get("height_uu", [0, 0])[1]},
        "base_uu": {"measured": [round(fx, 3), round(fy, 3), round(fz, 3)],
                    "proposed_diameter": lim.get("base_diameter_uu"), "proposed_height": lim.get("base_height_uu")},
    }
    passed = all(c["passed"] for c in checks.values())
    report = {
        "stage": UE_STAGE, "logic": UE_CANDIDATE_LOGIC_VERSION, "profile": profile["profile_id"],
        "backend": ue.describe(), "status": "technically_imported" if passed else "failed",
        "inputs": dict(sorted(inputs.items())),
        "destination": {"folder": folder, "assets": names},
        "previous_assets_deleted": deleted, "assets": after,
        "measured": measured, "checks": checks, "passed": passed,
        "comparison_with_proposals_not_budgets": proposals,
        "tool_name_style": ue.tool_name_style,
        "not_checked": [
            "art acceptance, silhouette, lighting, K1/K2/K3 with HUD and boardState (art track)",
            "animation clips and deformation (no clips are imported by this stage)",
            "skeletal triangle count inside UE (no MCP tool); Blender round trip is authoritative",
            "packaged build / cook of the candidate folder",
            "selection collision capsule (04 §3.1 proposal)",
            "shared master material M_DioramaMaster (04 §1): the candidate keeps its own %s, like the production "
            "import; deviation recorded, not checked" % u["material"],
        ],
    }
    out = staging / "ue-import-report.json"
    out.write_text(dump_json(report), encoding="utf-8")
    calls = staging / "ue-mcp-calls.json"
    calls.write_text(dump_json(ue.calls), encoding="utf-8")
    failed = sorted(k for k, c in checks.items() if not c["passed"])
    return StageResult({"reports/ue-import-report.json": out, "reports/ue-mcp-calls.json": calls},
                       {"passed": passed, "failed_checks": failed, "primary_asset": plan["primary"],
                        "kind": "skeletal-candidate", "assets": len(after)},
                       passed, None if passed else "ue-import failed: %s" % ", ".join(failed))


STAGE_IMPL = {
    "preflight": (fp_preflight, exec_preflight, True),
    "import": (fp_import, exec_import, False),
    "verify": (fp_verify, exec_verify, False),
    "export": (fp_export, exec_export, False),
    "atlas": (fp_atlas, exec_atlas, False),
    "build": (fp_build, exec_build, False),
    UE_STAGE: (fp_ue_import, exec_ue_import, False),
}
STAGE_PROBES = {UE_STAGE: probe_ue_import}
EXPORT_OUTPUT_PREFIX = "export/"


def outputs_intact(ctx: Context, rec: dict) -> bool:
    outputs = rec.get("outputs") or {}
    if not outputs:
        return False
    for rel, info in outputs.items():
        path = ctx.run_path(rel)
        if not path.is_file() or path.stat().st_size != info["bytes"] or sha256_file(path) != info["sha256"]:
            return False
    return True


def promote(ctx: Context, stage: str, result: StageResult) -> tuple:
    """Move staged files into place; identical files are not rewritten (hash dedupe)."""
    recorded, changes = {}, {}
    for rel, staged in sorted(result.outputs.items()):
        final = ctx.run_path(rel)
        digest = sha256_file(staged)
        size = staged.stat().st_size
        if final.is_file() and sha256_file(final) == digest:
            staged.unlink()
            changes[rel] = "unchanged"
        else:
            changes[rel] = "replaced" if final.exists() else "new"
            final.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staged, final)
        recorded[rel] = {"sha256": digest, "bytes": size}
    log = ctx.staging_root / stage / ("%s.log" % stage)
    if log.is_file():
        (ctx.run_dir / "logs").mkdir(exist_ok=True)
        os.replace(log, ctx.run_dir / "logs" / ("%s.log" % stage))
    return recorded, changes


def register_exports(ctx: Context, stage: str, recorded: dict, fingerprint: str) -> list:
    index = ctx.manifest.setdefault("exports", [])
    added = []
    for rel, info in recorded.items():
        if not rel.startswith(EXPORT_OUTPUT_PREFIX):
            continue
        if any(e["sha256"] == info["sha256"] for e in index):
            continue  # identical bytes already exported once: no duplicate entry
        for entry in index:
            if entry["path"] == rel and not entry.get("superseded_by"):
                entry["superseded_by"] = info["sha256"]
        entry = {"path": rel, "sha256": info["sha256"], "bytes": info["bytes"], "stage": stage,
                 "stage_fingerprint": fingerprint, "written_at": now_iso(),
                 "status": "technically_exported_not_art_accepted"}
        index.append(entry)
        added.append(rel)
    return added


def execute_stage(ctx: Context, name: str, force: bool = False) -> str:
    fp_fn, exec_fn, always = STAGE_IMPL[name]
    m = ctx.manifest
    rec = m["stages"].setdefault(name, {"status": "pending", "attempts": 0})
    fingerprint = sha256_json(fp_fn(ctx))
    up_to_date = (rec.get("status") == "completed" and rec.get("fingerprint") == fingerprint
                  and outputs_intact(ctx, rec))
    if up_to_date and name in STAGE_PROBES and not force:
        up_to_date = STAGE_PROBES[name](ctx, rec)
    if up_to_date and not force and not always:
        ctx.journal("stage_skipped", stage=name, reason="completed; fingerprint and output hashes unchanged",
                    fingerprint=fingerprint)
        return "skipped"
    staging = ctx.staging_root / name
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    if not always:
        rec.update(status="running", started_at=now_iso(), pending_fingerprint=fingerprint,
                   attempts=rec.get("attempts", 0) + 1)
        rec.pop("error", None)
        ctx.save()
    ctx.journal("stage_started", stage=name, fingerprint=fingerprint, forced=force)
    try:
        result = exec_fn(ctx, staging)
    except PipelineError as exc:
        log = staging / ("%s.log" % name)
        if log.is_file():
            (ctx.run_dir / "logs").mkdir(exist_ok=True)
            shutil.copyfile(log, ctx.run_dir / "logs" / ("%s.failed.log" % name))
        rec.update(status="failed", error=str(exc), finished_at=now_iso())
        rec.pop("pending_fingerprint", None)
        ctx.save()
        ctx.journal("stage_failed", stage=name, error=str(exc))
        raise
    if ctx.interrupt_at == name:
        # Diagnostic hook: die after the work, before anything is committed (lock and
        # "running" state are left behind exactly like a crash or a killed process).
        ctx.journal("simulated_interrupt", stage=name)
        sys.stdout.flush()
        os._exit(EXIT_INTERRUPTED)
    recorded, changes = promote(ctx, name, result)
    if always and up_to_date and all(v == "unchanged" for v in changes.values()) and result.passed:
        ctx.journal("stage_revalidated", stage=name, fingerprint=fingerprint, summary=result.summary)
        shutil.rmtree(staging, ignore_errors=True)
        return "revalidated"
    rec.pop("pending_fingerprint", None)
    if not result.passed:
        rec.update(status="failed", error=result.error, finished_at=now_iso(), outputs=recorded,
                   summary=result.summary, fingerprint=None)
        ctx.save()
        ctx.journal("stage_failed", stage=name, error=result.error, outputs=changes)
        shutil.rmtree(staging, ignore_errors=True)
        raise PipelineError(result.error or "%s failed" % name)
    if always:
        rec["attempts"] = rec.get("attempts", 0) + 1
        rec.setdefault("started_at", now_iso())
    rec.update(status="completed", fingerprint=fingerprint, finished_at=now_iso(), outputs=recorded,
               tool_version=TOOL_VERSION, backend=ctx.backend,
               summary=result.summary)
    added = register_exports(ctx, name, recorded, fingerprint)
    ctx.save()
    ctx.journal("stage_completed", stage=name, fingerprint=fingerprint, outputs=changes, exports_added=added)
    shutil.rmtree(staging, ignore_errors=True)
    return "executed"


def interrupted_stages(manifest: dict) -> list:
    return [n for n in KNOWN_STAGES if (manifest["stages"].get(n) or {}).get("status") == "running"]


def active_stages(ctx: Context) -> tuple:
    """Local stages of the run's profile always; the UE stage once configured (it then needs --backend mcp)."""
    return stage_order(ctx.manifest) if ctx.manifest["config"].get("ue") else base_stages(ctx.manifest)


def run_stages(ctx: Context, stages, force=()) -> dict:
    outcome = {}
    for name in stages:
        if name == UE_STAGE and ctx.backend != "mcp":
            ctx.journal("stage_not_run", stage=name, reason="needs --backend mcp")
            outcome[name] = "not-run (needs --backend mcp)"
            continue
        outcome[name] = execute_stage(ctx, name, force=name in force)
    return outcome


def require_upstream(ctx: Context, name: str) -> None:
    order = list(stage_order(ctx.manifest))
    if name not in order:
        raise PipelineError("stage %s is not part of profile %s (stages: %s)"
                            % (name, run_profile(ctx.manifest), ", ".join(order)), EXIT_USAGE)
    for up in order[1:order.index(name)]:
        rec = ctx.manifest["stages"].get(up) or {}
        if rec.get("status") != "completed":
            raise PipelineError("stage %s needs %s completed first (status: %s)" % (name, up, rec.get("status")),
                                EXIT_USAGE)


# ---------------------------------------------------------------------- commands

def new_manifest(args) -> dict:
    manifest = {
        "schema": RUN_SCHEMA,
        "run_id": args.run_id or Path(args.run_dir).resolve().name,
        "asset_id": args.asset_id,
        "created_at": now_iso(),
        "tool": {"name": TOOL_NAME, "version": TOOL_VERSION},
        "status_legend": STATUS_LEGEND,
        "claims": {"art_accepted": False, "game_ready": False, "budgets_declared": False,
                   "note": "technical pipeline evidence only"},
        "network": {"tripo_calls": 0, "paid_tasks_created": 0,
                    "policy": "no network code; Tripo results are registered from existing local files"},
        "config": {
            "primary_source": args.primary_source,
            "primary_role": args.primary_role,
            "export_basename": args.export_basename or "%s_%s" % (args.asset_id, args.primary_role),
            "triangle_loss_tolerance": args.triangle_loss_tolerance,
        },
        "sources": {},
        "stages": {},
        "exports": [],
        "generation_requests": [],
    }
    profile = getattr(args, "profile", None) or PASSTHROUGH
    if profile == CANDIDATE:
        if not args.build_profile:
            raise PipelineError("--profile %s needs --build-profile <repo-relative JSON>" % CANDIDATE, EXIT_USAGE)
        manifest["config"]["profile"] = CANDIDATE
        manifest["config"]["build_profile"] = Path(args.build_profile).as_posix()
    elif getattr(args, "build_profile", None):
        raise PipelineError("--build-profile is only used with --profile %s" % CANDIDATE, EXIT_USAGE)
    return manifest


def cmd_init(ctx: Context, args) -> int:
    fresh = new_manifest(args)
    if ctx.manifest_path.exists():
        ctx.load()
        existing_cfg = {k: v for k, v in ctx.manifest.get("config", {}).items() if k != "ue"}
        same = ctx.manifest.get("asset_id") == fresh["asset_id"] and existing_cfg == fresh["config"]
        if not same:
            raise PipelineError("run already initialised with a different asset/config; use a new --run-dir",
                                EXIT_CONFLICT)
        ctx.journal("init_noop", reason="already initialised with identical config")
        print("init: already initialised, no change")
        return EXIT_OK
    ctx.manifest, ctx._manifest_text = fresh, None
    ctx.save()
    ctx.journal("init", config=fresh["config"], asset_id=fresh["asset_id"])
    print("init: created %s" % ctx.manifest_path)
    return EXIT_OK


def cmd_register(ctx: Context, args) -> int:
    ctx.load()
    spec_path = Path(args.spec).resolve()
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    validate_spec(spec)
    if spec["asset_id"] != ctx.manifest["asset_id"]:
        raise PipelineError("spec asset %s != run asset %s" % (spec["asset_id"], ctx.manifest["asset_id"]), EXIT_USAGE)
    record = build_source_record(ctx, spec)
    sid = spec["source_id"]
    existing = ctx.manifest["sources"].get(sid)
    if existing:
        volatile = ("registered_at", "registered_by")
        comparable = {k: v for k, v in existing.items() if k not in volatile}
        if canonical(comparable) == canonical({k: v for k, v in record.items() if k not in volatile}):
            ctx.journal("register_noop", source_id=sid, reason="identical spec and file hashes already registered")
            print("register-source: %s already registered with identical content; no change" % sid)
            return EXIT_OK
        raise PipelineError("source %s already registered with different content; refusing to overwrite "
                            "(register under a new source_id or use a new run dir)" % sid, EXIT_CONFLICT)
    record["registered_at"] = now_iso()
    ctx.manifest["sources"][sid] = record
    ctx.save()
    ctx.journal("source_registered", source_id=sid, task_id=spec["task_id"], service=spec["service"],
                files={f["role"]: f["sha256"] for f in record["files"]},
                historical_credits_observed=record["historical_credits_observed"])
    print("register-source: registered %s (%d files, historical spend %s; this command spent 0)"
          % (sid, len(record["files"]), record["historical_credits_observed"]))
    return EXIT_OK


def print_outcome(outcome: dict) -> None:
    for name, state in outcome.items():
        print("  %-9s %s" % (name, state))


def cmd_stage(ctx: Context, args) -> int:
    ctx.load()
    if interrupted_stages(ctx.manifest):
        raise PipelineError("interrupted stage(s) %s; use resume" % interrupted_stages(ctx.manifest), EXIT_NEEDS_RESUME)
    name = args.command
    if name != "preflight":
        require_upstream(ctx, name)
    outcome = {name: execute_stage(ctx, name, force=args.force)}
    print_outcome(outcome)
    return EXIT_OK


def cmd_ue_import(ctx: Context, args) -> int:
    ctx.load()
    ctx.unreal()  # refuses early (before touching the manifest) for --backend headless
    if interrupted_stages(ctx.manifest):
        raise PipelineError("interrupted stage(s) %s; use resume" % interrupted_stages(ctx.manifest), EXIT_NEEDS_RESUME)
    require_upstream(ctx, UE_STAGE)
    wanted = {"folder": (args.ue_folder or "").rstrip("/") or None, "asset_name": args.asset_name,
              "import_materials": not args.no_materials, "import_textures": not args.no_materials,
              "dimension_tolerance": args.dimension_tolerance}
    if run_profile(ctx.manifest) == CANDIDATE:
        # The candidate path never lets the FBX importer create materials/textures: it imports the atlas
        # PNGs and builds its own material. Record the flags that are really used (T4 wrote true here).
        wanted.update(import_materials=False, import_textures=False,
                      import_note="skeletal-candidate: meshes imported with import_materials=false, "
                                  "import_textures=false; textures come from the atlas stage")
    cfg = ctx.manifest["config"].get("ue")
    if cfg is None:
        wanted["folder"] = wanted["folder"] or default_ue_folder(ctx.manifest)
        if not (wanted["folder"] + "/").startswith(UE_ALLOWED_ROOT) or ".." in wanted["folder"]:
            raise PipelineError("UE folder must be inside %s (never /Game/ART004 or /Game/ArtPreview): %s"
                                % (UE_ALLOWED_ROOT, wanted["folder"]), EXIT_USAGE)
        ctx.manifest["config"]["ue"] = wanted
        ctx.save()
        ctx.journal("ue_configured", ue=wanted)
    else:
        explicit = {k: v for k, v in wanted.items() if v is not None and k in ("folder", "asset_name")}
        if any(cfg.get(k) != v for k, v in explicit.items()):
            raise PipelineError("UE target already configured as %s; use a new run dir for another target"
                                % {k: cfg.get(k) for k in ("folder", "asset_name")}, EXIT_CONFLICT)
    print_outcome({UE_STAGE: execute_stage(ctx, UE_STAGE, force=args.force)})
    return EXIT_OK


def cmd_run(ctx: Context, args) -> int:
    ctx.load()
    stuck = interrupted_stages(ctx.manifest)
    if stuck:
        raise PipelineError("interrupted stage(s) %s from a previous process; use resume" % stuck, EXIT_NEEDS_RESUME)
    ctx.journal("run_started", force=args.force or [], backend=ctx.backend)
    outcome = run_stages(ctx, active_stages(ctx), force=set(args.force or []))
    ctx.journal("run_finished", outcome=outcome)
    print_outcome(outcome)
    return EXIT_OK


def cmd_resume(ctx: Context, args) -> int:
    ctx.load()
    m = ctx.manifest
    unfinished = [n for n in active_stages(ctx) if (m["stages"].get(n) or {}).get("status") != "completed"]
    for name in interrupted_stages(m):
        rec = m["stages"][name]
        rec.setdefault("interruptions", []).append({"started_at": rec.get("started_at"), "detected_at": now_iso()})
        rec["status"] = "interrupted"
        rec.pop("pending_fingerprint", None)
    shutil.rmtree(ctx.staging_root, ignore_errors=True)
    ctx.save()
    resume_from = unfinished[0] if unfinished else None
    ctx.journal("resume_started", resume_from=resume_from, unfinished=unfinished, backend=ctx.backend)
    print("resume: first unfinished stage = %s" % resume_from)
    outcome = run_stages(ctx, active_stages(ctx))
    ctx.journal("resume_finished", outcome=outcome)
    print_outcome(outcome)
    return EXIT_OK


def cmd_status(ctx: Context, args) -> int:
    m = ctx.load()
    print("run %s  asset %s  created by tool %s  (this tool %s, backend %s)"
          % (m["run_id"], m["asset_id"], m["tool"]["version"], TOOL_VERSION, ctx.backend))
    for sid, src in sorted(m["sources"].items()):
        s = src["spec"]
        print("source %s  task %s  %s  credits(historical) %s" % (sid, s["task_id"], s["service"],
                                                                  src["historical_credits_observed"]))
    print("profile %s%s" % (run_profile(m), "  build profile %s" % m["config"]["build_profile"]
                                 if m["config"].get("build_profile") else ""))
    for name in stage_order(m):
        rec = m["stages"].get(name) or {}
        if name == UE_STAGE and not m["config"].get("ue"):
            continue
        print("stage %-9s %-11s attempts=%s%s" % (name, rec.get("status", "pending"), rec.get("attempts", 0),
                                                 "  by %s/%s" % (rec["tool_version"], rec.get("backend")) if rec.get("tool_version") else ""))
    for e in m.get("exports", []):
        print("export %s %s%s" % (e["path"], e["sha256"][:12], " (superseded)" if e.get("superseded_by") else ""))
    print("network: tripo_calls=%s paid_tasks_created=%s" % (m["network"]["tripo_calls"], m["network"]["paid_tasks_created"]))
    return EXIT_OK


SNAPSHOT_EXCLUDE = {"journal.jsonl", "run.lock"}


def snapshot(run_dir: Path) -> dict:
    files = {}
    for path in sorted(run_dir.rglob("*")):
        rel = rel_posix(path, run_dir)
        if not path.is_file() or rel in SNAPSHOT_EXCLUDE or rel.startswith(".staging/"):
            continue
        st = path.stat()
        files[rel] = {"sha256": sha256_file(path), "bytes": st.st_size, "mtime_ns": st.st_mtime_ns}
    return files


def cmd_snapshot(ctx: Context, args) -> int:
    data = {"run_dir": str(ctx.run_dir), "taken_at": now_iso(), "files": snapshot(ctx.run_dir)}
    text = dump_json(data)
    if args.out:
        out = Path(args.out).resolve()
        if is_within(out, ctx.run_dir):
            raise PipelineError("snapshot --out must be outside the run dir", EXIT_USAGE)
        atomic_write_text(out, text)
        print("snapshot: %d files -> %s" % (len(data["files"]), out))
    else:
        sys.stdout.write(text)
    return EXIT_OK


def cmd_prepare_generation(ctx: Context, args) -> int:
    if not args.dry_run:
        raise PipelineError("submission is not implemented: this scaffold never calls Tripo. "
                            "Re-run with --dry-run to prepare an input package only.", EXIT_USAGE)
    ctx.load()
    if args.service not in SERVICES:
        raise PipelineError("--service must be one of %s" % sorted(SERVICES), EXIT_USAGE)
    if args.mode == "batch":
        raise PipelineError("batch = several independent tasks; prepare one request per task", EXIT_USAGE)
    views = {}
    for item in args.view or []:
        if "=" not in item:
            raise PipelineError("--view expects name=path", EXIT_USAGE)
        view, rel = item.split("=", 1)
        if view in views:
            raise PipelineError("duplicate view %s" % view, EXIT_USAGE)
        views[view] = rel
    if args.mode == "multi-view" and len(views) < 2:
        raise PipelineError("multi-view needs >=2 views of the same object", EXIT_USAGE)
    if args.mode != "multi-view" and len(views) > 1:
        raise PipelineError("only one view for mode %s" % args.mode, EXIT_USAGE)
    reason = (args.duplicate_reason or "").strip()
    if args.allow_duplicate and not reason:
        raise PipelineError("--allow-duplicate needs --duplicate-reason \"...\" (why a second paid task with the "
                            "same inputs is wanted); it is recorded in the package and the journal", EXIT_USAGE)
    if reason and not args.allow_duplicate:
        raise PipelineError("--duplicate-reason is only used together with --allow-duplicate", EXIT_USAGE)
    inputs, problems = {}, []
    for view, rel in sorted(views.items()):
        path = ctx.repo_path(rel)
        if not path.is_file():
            raise PipelineError("input missing: %s" % rel)
        info = inspect_file(path)
        size = path.stat().st_size
        if info.get("format") not in ("png", "jpeg"):
            problems.append("%s: unsupported format %s" % (view, info.get("format")))
        if size > MAX_TRIPO_IMAGE_BYTES:
            problems.append("%s: %d bytes > %d" % (view, size, MAX_TRIPO_IMAGE_BYTES))
        inputs[view] = {"path": Path(rel).as_posix(), "sha256": sha256_file(path), "bytes": size,
                        "pixels": info.get("pixels")}
    core = {"service": args.service, "mode": args.mode, "model_label": args.model_label,
            "views": {v: i["sha256"] for v, i in inputs.items()}}
    key = sha256_json(core)
    # A duplicate is the same input hashes + mode + service. The model label is free UI text
    # ("H3.1" vs "H3.1 - Макс.кач. ..."), so it never decides; it is only reported.
    duplicates = []
    for sid, src in sorted(ctx.manifest["sources"].items()):
        gen = src["spec"].get("generation") or {}
        registered = {v: (i or {}).get("sha256") for v, i in (gen.get("views") or {}).items() if i}
        if registered == core["views"] and gen.get("mode") == args.mode and src["spec"]["service"] == args.service:
            same_model = src["spec"].get("model_version", {}).get("ui_label") == args.model_label
            duplicates.append({"source_id": sid, "task_id": src["spec"]["task_id"], "same_model_label": same_model,
                               "registered_model_label": src["spec"].get("model_version", {}).get("ui_label")})
    if duplicates and not args.allow_duplicate:
        ctx.journal("generation_request_refused_duplicate", key=key, duplicate_of=duplicates)
        raise PipelineError("the same inputs (SHA-256), mode and service were already generated as %s (model label "
                            "is not compared); a new paid task would duplicate it. Only --allow-duplicate "
                            "--duplicate-reason \"...\" bypasses this" % [d["task_id"] for d in duplicates],
                            EXIT_CONFLICT)
    request = {
        "schema": REQUEST_SCHEMA, "request_key": key, "asset_id": ctx.manifest["asset_id"],
        "dry_run": True, "submitted": False, "network_calls": 0, "paid_tasks_created": 0,
        "service": args.service, "mode": args.mode, "model_label": args.model_label, "inputs": inputs,
        "input_problems": problems, "same_inputs_as_registered": duplicates,
        "duplicate_allowed": {"reason": reason, "duplicate_of": [d["task_id"] for d in duplicates]}
        if duplicates else None,
        "cost": {"unit": SERVICES[args.service], "quoted": None,
                 "note": "price is read from the Studio form / API pricing at submission time, not estimated here"},
        "note": "automatic checks only; geometric consistency of views needs a separate manual review",
    }
    rel = "generation-requests/%s.json" % key[:16]
    path = ctx.run_path(rel)
    text = dump_json(request)
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        ctx.journal("generation_request_noop", key=key)
        print("prepare-generation: identical dry-run package already exists: %s" % rel)
        return EXIT_OK
    atomic_write_text(path, text)
    reqs = ctx.manifest.setdefault("generation_requests", [])
    if not any(r["request_key"] == key for r in reqs):
        reqs.append({"request_key": key, "path": rel, "sha256": sha256_file(path), "dry_run": True, "submitted": False})
    ctx.save()
    ctx.journal("generation_request_prepared", key=key, path=rel, problems=problems,
                duplicate_allowed=request["duplicate_allowed"])
    print("prepare-generation: dry-run package %s (problems: %d; nothing submitted)" % (rel, len(problems)))
    return EXIT_OK if not problems else EXIT_FAILED


# --------------------------------------------------------------------------- main

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tripo_pipeline", description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo-root", default=str(TOOL_DIR.parents[1]))
    parser.add_argument("--blender", default=None, help="Blender executable (default: Blender 5.2 path)")
    parser.add_argument("--backend", choices=BACKENDS, default=None,
                        help="headless: blender -b per stage (default); mcp: live Blender/UE via MCP clients")
    parser.add_argument("--blender-mcp-client", default=None, help="path to blender_mcp.py")
    parser.add_argument("--unreal-mcp-client", default=None, help="path to unreal_mcp.py")
    sub = parser.add_subparsers(dest="command", required=True)

    def with_run(p):
        p.add_argument("--run-dir", required=True)
        return p

    p = with_run(sub.add_parser("init"))
    p.add_argument("--asset-id", required=True)
    p.add_argument("--primary-source", required=True)
    p.add_argument("--primary-role", required=True)
    p.add_argument("--export-basename")
    p.add_argument("--run-id")
    p.add_argument("--triangle-loss-tolerance", type=float, default=DEFAULT_TRIANGLE_LOSS_TOLERANCE)
    p.add_argument("--profile", choices=PROFILES, default=PASSTHROUGH,
                   help="passthrough (T3 static FBX) or skeletal-candidate (atlas + build from --build-profile)")
    p.add_argument("--build-profile", help="repo-relative build profile JSON (skeletal-candidate)")
    p = with_run(sub.add_parser("register-source"))
    p.add_argument("--spec", required=True)
    for name in [s for s in KNOWN_STAGES if s != UE_STAGE]:
        p = with_run(sub.add_parser(name))
        p.add_argument("--force", action="store_true", help="re-execute even if up to date (output dedupe still applies)")
        p.add_argument("--interrupt-at", choices=KNOWN_STAGES, help=argparse.SUPPRESS)
    p = with_run(sub.add_parser(UE_STAGE))
    p.add_argument("--ue-folder", help="content folder under %s (default: %s<Asset>/<run_id>)"
                   % (UE_ALLOWED_ROOT, UE_ALLOWED_ROOT))
    p.add_argument("--asset-name", default=None)
    p.add_argument("--no-materials", action="store_true")
    p.add_argument("--dimension-tolerance", type=float, default=DEFAULT_UE_DIMENSION_TOLERANCE)
    p.add_argument("--force", action="store_true")
    p.add_argument("--interrupt-at", choices=KNOWN_STAGES, help=argparse.SUPPRESS)
    p = with_run(sub.add_parser("run"))
    p.add_argument("--force", action="append", choices=KNOWN_STAGES)
    p.add_argument("--interrupt-at", choices=KNOWN_STAGES,
                   help="diagnostic: exit 75 after this stage's work, before committing it")
    p = with_run(sub.add_parser("resume"))
    p.add_argument("--interrupt-at", choices=KNOWN_STAGES, help=argparse.SUPPRESS)
    with_run(sub.add_parser("status"))
    p = with_run(sub.add_parser("snapshot"))
    p.add_argument("--out")
    p = with_run(sub.add_parser("prepare-generation"))
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--service", required=True)
    p.add_argument("--mode", required=True)
    p.add_argument("--model-label", required=True)
    p.add_argument("--view", action="append", help="name=repo-relative path; repeat per view")
    p.add_argument("--allow-duplicate", action="store_true",
                   help="prepare a package even though the same inputs/mode/service were generated (needs a reason)")
    p.add_argument("--duplicate-reason", default=None, help="why a duplicate paid task is wanted (recorded)")
    return parser


COMMANDS = {
    "init": cmd_init, "register-source": cmd_register, "preflight": cmd_stage, "import": cmd_stage,
    "verify": cmd_stage, "export": cmd_stage, "atlas": cmd_stage, "build": cmd_stage, UE_STAGE: cmd_ue_import, "run": cmd_run, "resume": cmd_resume, "status": cmd_status,
    "snapshot": cmd_snapshot, "prepare-generation": cmd_prepare_generation,
}
READ_ONLY = {"status", "snapshot"}


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        ctx = Context(Path(args.run_dir), Path(args.repo_root), args.blender, getattr(args, "interrupt_at", None),
                      backend=args.backend, blender_mcp_client=args.blender_mcp_client,
                      unreal_mcp_client=args.unreal_mcp_client)
    except PipelineError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return exc.code
    try:
        if args.command not in READ_ONLY:
            ctx.acquire_lock(args.command)
        try:
            return COMMANDS[args.command](ctx, args)
        finally:
            ctx.release_lock()
    except PipelineError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
