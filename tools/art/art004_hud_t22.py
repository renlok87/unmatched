#!/usr/bin/env python3
"""ART-004 stage 3 T2.2 (HUD/input code) harness for the art worktree.

  editor-build  Build.bat UnmatchedEditor Win64 Development with -NoHotReloadFromIDE.
                The live editor of the MAIN checkout holds the Live Coding mutex
                Global\\LiveCoding_<UnrealEditor.exe path>; UBT refuses every editor
                target of the installed engine while it exists (HotReload.cs
                CheckForLiveCodingSessionActive). -NoHotReloadFromIDE skips only
                that check (bAllowHotReloadFromIDE=false) and keeps WITH_LIVE_CODING 1,
                unlike -NoLiveCoding (R3). The art worktree has its own
                Binaries/Win64/UnrealEditor-Unmatched.dll, so nothing the live
                editor loaded is overwritten. Result from the UTF-16 log
                (Select-String 'Result: (Succeeded|Failed)'), WITH_LIVE_CODING of
                every editor SharedDefinitions, sha256 of the editor DLL.
  tests         UnrealEditor-Cmd (art worktree project, -nullrhi, MCP auto-start
                off) "Automation RunTests <filter>; Quit"; parses the log for
                per-test results and writes tests-<label>.json.
  icons         Pre-filtered 24/32/48 px combat icons from the ART-003 concept
                (linear-light area filter, premultiplied alpha) + manifest.
  import-icons  UnrealEditor-Cmd -run=pythonscript tools/art/art004_hud_icon_import.py.

Statuses stay honest: a green run is "измерено / технически", never "принято".
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
UE_ROOT = Path(os.environ.get("UE_ROOT", r"C:\Program Files\Epic Games\UE_5.8"))
PROJECT_DIR = REPO / "unreal" / "Unmatched"
UPROJECT = PROJECT_DIR / "Unmatched.uproject"
EDITOR_DLL = PROJECT_DIR / "Binaries" / "Win64" / "UnrealEditor-Unmatched.dll"
EDITOR_DEFS = PROJECT_DIR / "Intermediate" / "Build" / "Win64" / "x64" / "UnmatchedEditor" / "Development"
EDITOR_CMD = UE_ROOT / "Engine" / "Binaries" / "Win64" / "UnrealEditor-Cmd.exe"
BUILD_BAT = UE_ROOT / "Engine" / "Build" / "BatchFiles" / "Build.bat"
ICON_SOURCE = REPO / "art" / "imagegen" / "mvp-v1" / "ui" / "actions" / "ui-action-attack-normal.png"
ICON_DIR = REPO / "art" / "imagegen" / "mvp-v1" / "ui" / "actions" / "sized"
MCP_OFF = ("-ini:EditorPerProjectUserSettings:[/Script/ModelContextProtocolEngine."
           "ModelContextProtocolSettings]:bAutoStartServer=False")
NO_WINDOW = 0x08000000


def now_local() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(p: Path, doc) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def rel(p: Path) -> str:
    try:
        return p.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return p.resolve().as_posix()


def ps(command: str, timeout: int | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=timeout, creationflags=NO_WINDOW)


def ps_quote(s) -> str:
    return "'" + str(s).replace("'", "''") + "'"


def select_string(path: Path, pattern: str, simple: bool = False) -> list[str]:
    sm = " -SimpleMatch" if simple else ""
    r = ps(f"Select-String -LiteralPath {ps_quote(path)}{sm} -Pattern {ps_quote(pattern)} | "
           "ForEach-Object { $_.Line }")
    return [ln for ln in r.stdout.splitlines() if ln.strip()]


def free_commit_gb() -> float:
    r = ps("$os=Get-CimInstance Win32_OperatingSystem; $os.FreeVirtualMemory")
    try:
        return round(int(r.stdout.strip()) / 2**20, 1)
    except ValueError:
        return 0.0


def live_coding_mutex() -> dict:
    exe = str(UE_ROOT / "Engine" / "Binaries" / "Win64" / "UnrealEditor.exe")
    name = "Global\\LiveCoding_" + "".join("+" if c in "/\\:" else c for c in exe)
    r = ps(f"$m=$null; $ok=[System.Threading.Mutex]::TryOpenExisting({ps_quote(name)},[ref]$m); "
           "if($m){$m.Dispose()}; $ok")
    return {"name": name, "exists": r.stdout.strip().lower() == "true"}


def editor_defs() -> dict:
    out = {}
    for p in sorted(EDITOR_DEFS.rglob("SharedDefinitions.*.h")) if EDITOR_DEFS.is_dir() else []:
        m = re.search(rb"#define WITH_LIVE_CODING (\d)", p.read_bytes())
        out[p.relative_to(PROJECT_DIR).as_posix()] = int(m.group(1)) if m else None
    return out


def cmd_editor_build(a) -> int:
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    commit = free_commit_gb()
    par = a.max_parallel or (4 if commit >= 20 else 2)
    flags = ["-WaitMutex", "-NoXGE", "-NoUBA", f"-MaxParallelActions={par}", "-NoHotReloadFromIDE"] + a.extra
    log = out / f"{a.label}-editor-build.log"
    rec = {"schema": "unmatched.t22-editor-build/1", "label": a.label, "target": "UnmatchedEditor Win64 Development",
           "startedLocal": now_local(), "flags": flags, "freeCommitGB": commit,
           "liveCodingMutexBefore": live_coding_mutex(),
           "command": f"Build.bat UnmatchedEditor Win64 Development <uproject> {' '.join(flags)}",
           "launcher": "powershell Start-Process -WindowStyle Hidden -Wait (no console window)",
           "why": "the live main-checkout editor holds the Live Coding mutex of the shared UnrealEditor.exe; "
                  "-NoHotReloadFromIDE skips that UBT check only and keeps WITH_LIVE_CODING 1 (not -NoLiveCoding, R3)",
           "log": rel(log), "sharedDefinitionsBefore": editor_defs(),
           "dllBefore": {"sha256": sha256_file(EDITOR_DLL) if EDITOR_DLL.is_file() else None,
                         "mtime": dt.datetime.fromtimestamp(EDITOR_DLL.stat().st_mtime).astimezone().isoformat(
                             timespec="seconds") if EDITOR_DLL.is_file() else None}}
    started = time.time()
    arglist = ",".join(ps_quote(x) for x in ["UnmatchedEditor", "Win64", "Development", str(UPROJECT)] + flags)
    r = ps(f"$p = Start-Process -FilePath {ps_quote(BUILD_BAT)} -ArgumentList @({arglist}) -WindowStyle Hidden "
           f"-PassThru -Wait -RedirectStandardOutput {ps_quote(log)} -RedirectStandardError {ps_quote(str(log) + '.err')}; "
           "Write-Output \"EXIT=$($p.ExitCode)\"")
    m = re.search(r"EXIT=(-?\d+)", r.stdout)
    rec["exitCode"] = int(m.group(1)) if m else None
    rec["durationS"] = round(time.time() - started, 1)
    rec["finishedLocal"] = now_local()
    rec["resultLines"] = select_string(log, r"Result: (Succeeded|Failed)")
    rec["errorLines"] = select_string(log, r"error C\d+|error LNK\d+|fatal error|Live Coding is active|1455")[:30]
    rec["warningLines"] = select_string(log, r"warning C\d+")[:40]
    rec["result"] = ("Succeeded" if any("Result: Succeeded" in x for x in rec["resultLines"])
                     and not any("Result: Failed" in x for x in rec["resultLines"]) else "Failed")
    rec["sharedDefinitionsAfter"] = editor_defs()
    rec["withLiveCodingValues"] = sorted({v for v in rec["sharedDefinitionsAfter"].values() if v is not None})
    rec["dll"] = {"path": rel(EDITOR_DLL), "sha256": sha256_file(EDITOR_DLL) if EDITOR_DLL.is_file() else None,
                  "mtime": dt.datetime.fromtimestamp(EDITOR_DLL.stat().st_mtime).astimezone().isoformat(
                      timespec="seconds") if EDITOR_DLL.is_file() else None}
    rec["liveCodingMutexAfter"] = live_coding_mutex()
    write_json(out / f"{a.label}-editor-build.json", rec)
    print(json.dumps({k: rec[k] for k in ("label", "result", "exitCode", "durationS", "withLiveCodingValues")},
                     ensure_ascii=False))
    for ln in rec["errorLines"][:15]:
        print("  ERR |", ln[:300])
    for ln in rec["warningLines"][:15]:
        print("  WRN |", ln[:300])
    return 0 if rec["result"] == "Succeeded" else 1


TEST_RESULT = re.compile(r"Test Completed\. Result=\{(\w+)\} Name=\{([^}]*)\} Path=\{([^}]*)\}")


def cmd_tests(a) -> int:
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    log = out / f"tests-{a.label}.log"
    fixtures = REPO / "docs" / "game-design" / "evidence" / "S08" / "fixtures"
    s09 = REPO / "docs" / "game-design" / "evidence" / "S09" / "fixtures"
    args = [str(UPROJECT), f"-ExecCmds=Automation RunTests {a.filter}; Quit", "-unattended", "-nosplash",
            "-nullrhi", "-nullaudio", "-NoSound", f"-S08Fixtures={fixtures}", f"-S09Fixtures={s09}",
            MCP_OFF, "-log", f"-abslog={log}"]
    started = time.time()
    r = subprocess.run([str(EDITOR_CMD)] + args, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=a.timeout, creationflags=NO_WINDOW)
    text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
    results = [{"result": m.group(1), "name": m.group(2), "path": m.group(3)} for m in TEST_RESULT.finditer(text)]
    found = re.findall(r"Found (\d+) automation tests", text)
    # Engine start-up self-test noise ("LogAutomationTest: Error: Condition failed" x17 before any test,
    # also in the 2026-09-27 S09 logs) is kept apart from errors raised while tests run.
    lines = text.splitlines()
    first_test = next((i for i, ln in enumerate(lines) if "Test Started." in ln), len(lines))
    startup_noise = [ln for ln in lines[:first_test] if re.search(r"Error: |Fatal error", ln)]
    errors = [ln for ln in lines[first_test:] if re.search(r"Error: |Fatal error|Unhandled Exception", ln)][:60]
    rec = {"schema": "unmatched.t22-ue-tests/1", "label": a.label, "filter": a.filter, "startedLocal": now_local(),
           "durationS": round(time.time() - started, 1), "exitCode": r.returncode, "log": rel(log),
           "editorDll": {"sha256": sha256_file(EDITOR_DLL) if EDITOR_DLL.is_file() else None},
           "found": [int(x) for x in found], "results": results,
           "passed": sum(1 for x in results if x["result"] == "Success"),
           "failed": [x for x in results if x["result"] != "Success"], "errorLines": errors,
           "startupNoiseErrorLines": len(startup_noise),
           "command": "UnrealEditor-Cmd <art uproject> -ExecCmds=\"Automation RunTests <filter>; Quit\" -unattended "
                      "-nosplash -nullrhi -nullaudio (MCP auto-start off)"}
    write_json(out / f"tests-{a.label}.json", rec)
    print(json.dumps({"label": a.label, "exit": r.returncode, "found": rec["found"], "passed": rec["passed"],
                      "failed": len(rec["failed"])}, ensure_ascii=False))
    for x in rec["failed"]:
        print("  FAIL |", x["path"])
    for ln in errors[:20]:
        print("  |", ln[:300])
    ok = r.returncode == 0 and results and not rec["failed"]
    return 0 if ok else 1


def srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb(c: float) -> float:
    c = min(max(c, 0.0), 1.0)
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def cmd_icons(a) -> int:
    import numpy as np
    from PIL import Image
    src = Image.open(ICON_SOURCE).convert("RGBA")
    arr = np.asarray(src, dtype=np.float64) / 255.0
    c = arr[..., :3]
    rgb_lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    alpha = arr[..., 3:4]
    premul = np.concatenate([rgb_lin * alpha, alpha], axis=2)
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {"schema": "unmatched.t22-icon-sizes/1", "status": "предложено (производные для проверки 24/32/48 px)",
                "source": rel(ICON_SOURCE), "sourceSha256": sha256_file(ICON_SOURCE),
                "sourceSize": list(src.size),
                "method": "линейный свет (sRGB IEC 61966-2-1), премультиплицированная альфа, "
                          "усреднение по площади (PIL BOX на float32 каналах), обратно в sRGB 8 бит",
                "outputs": []}
    h, w = premul.shape[:2]
    for size in (24, 32, 48):
        chans = []
        for c in range(4):
            im = Image.fromarray(premul[..., c].astype(np.float32), mode="F")
            chans.append(np.asarray(im.resize((size, size), Image.BOX), dtype=np.float64))
        a_ = np.clip(chans[3], 0.0, 1.0)
        rgb = np.zeros((size, size, 3))
        nz = a_ > 1e-6
        for c in range(3):
            rgb[..., c] = np.where(nz, chans[c] / np.maximum(a_, 1e-6), 0.0)
        lin = np.clip(rgb, 0.0, 1.0)
        srgb = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(lin, 1 / 2.4) - 0.055)
        out = np.concatenate([srgb, a_[..., None]], axis=2)
        img = Image.fromarray(np.clip(np.round(out * 255.0), 0, 255).astype(np.uint8), mode="RGBA")
        dst = ICON_DIR / f"ui-action-attack-normal-{size}.png"
        img.save(dst, optimize=False)
        manifest["outputs"].append({"size": size, "path": rel(dst), "sha256": sha256_file(dst),
                                    "ueAsset": f"/Game/ArtTests/ARTMarkers/Textures/T_UI_Action_Attack_{size}"})
        print(dst, sha256_file(dst))
    write_json(ICON_DIR / "sized-manifest.json", manifest)
    return 0


TOKEN_BODY = (22, 26, 40)      # hud-style-tokens icon.token.body = tag.background (#161A28)
TOKEN_RIM = (242, 236, 222)    # icon.token.rim (#F2ECDE)
TOKEN_OUTLINE = (17, 19, 23)   # mark.keyline (#111317): 1 px glyph outline
TOKEN_MIN_REL_LUM = 0.16       # D-5: hilts lightened to Y >= 0.16 (>= 3:1 against the body Y 0.0107, p10 of the filtered glyph incl.)
TEAM_SHAPE_DIR = REPO / "art" / "imagegen" / "mvp-v1" / "ui" / "team"


def _rel_lum(lin):
    return 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]


def _srgb8_to_lin(c):
    import numpy as np
    c = np.asarray(c, dtype=np.float64) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _lin_to_srgb8(lin):
    import numpy as np
    lin = np.clip(lin, 0.0, 1.0)
    s = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(lin, 1 / 2.4) - 0.055)
    return np.clip(np.round(s * 255.0), 0, 255).astype(np.uint8)


def _wcag(y1, y2):
    hi, lo = max(y1, y2), min(y1, y2)
    return (hi + 0.05) / (lo + 0.05)


def _area_resize_premul(premul, size_xy):
    """Linear-light area filter (PIL BOX on float channels) of a premultiplied RGBA float image."""
    import numpy as np
    from PIL import Image
    chans = [np.asarray(Image.fromarray(premul[..., c].astype(np.float32), mode="F").resize(size_xy, Image.BOX),
                        dtype=np.float64) for c in range(4)]
    return np.stack(chans, axis=-1)


def cmd_tokens(a) -> int:
    """W5b-R decision D-5: the attack icon as an opaque TOKEN at 24/32/48 px - a dark rounded square (body #161A28,
    radius N/4), a 1 px light rim (#F2ECDE), the ART-003 glyph fitted into N-4 px (linear-light area filter, same as
    `icons`) with a 1 px dark outline (#111317) and the dark hilts lifted to relative luminance >= 0.16 in linear
    light with the chromaticity kept (>= 3:1 against the body). Also writes the glyph mask (alpha = glyph coverage)
    that qa010 `icon --mask-texture` reads (alpha >= 0.5 = glyph), and the team shape chips (D-3): 12x12 white
    circle (P1) / pointy-left-right hexagon (P2) with anti-aliased alpha, tinted in the UI. Status: предложено (a
    concept style, not artistically accepted; the source concept stays unchanged)."""
    import numpy as np
    from PIL import Image
    src = Image.open(ICON_SOURCE).convert("RGBA")
    arr = np.asarray(src, dtype=np.float64) / 255.0
    ys, xs = np.where(arr[..., 3] > 0.05)
    crop = arr[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    lin = np.where(crop[..., :3] <= 0.04045, crop[..., :3] / 12.92, ((crop[..., :3] + 0.055) / 1.055) ** 2.4)
    alpha = crop[..., 3:4]
    premul = np.concatenate([lin * alpha, alpha], axis=2)
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    SS = 8
    manifest = {"schema": "unmatched.w5br-attack-token/1",
                "status": "предложено (жетон иконки цели, решение советника D-5; художественно не принят)",
                "source": rel(ICON_SOURCE), "sourceSha256": sha256_file(ICON_SOURCE),
                "sourceGlyphBox": [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1],
                "colors": {"body": "#%02X%02X%02X" % TOKEN_BODY, "rim": "#%02X%02X%02X" % TOKEN_RIM,
                           "outline": "#%02X%02X%02X" % TOKEN_OUTLINE},
                "rule": {"shape": "rounded square N x N, corner radius N/4, coverage by 8x8 supersampling",
                         "rimPx": 1, "glyphBoxPx": "N-4 (1 px rim + 1 px margin each side), aspect kept, centred",
                         "glyphFilter": "linear light, premultiplied alpha, area average (PIL BOX)",
                         "outline": "1 px: glyph alpha dilated 3x3 (max), painted #111317 under the glyph",
                         "hilts": f"glyph pixels with relative luminance < {TOKEN_MIN_REL_LUM} scaled up in linear light "
                                  "(all channels x k, k = Ymin / Y, capped so no channel exceeds 1) - hue kept",
                         "maskTexture": "alpha = glyph coverage after the filter (qa010 icon --mask-texture ... "
                                        "--mask-alpha 0.5); body = token shape minus glyph minus the outer 1 px rim"},
                "outputs": []}
    for size in (24, 32, 48):
        n = size
        # token shape coverage and rim coverage (supersampled distance to the rounded-square border)
        g = (np.arange(n * SS) + 0.5) / SS
        X, Y = np.meshgrid(g, g)
        r = n / 4.0
        cx = np.clip(X, r, n - r)
        cy = np.clip(Y, r, n - r)
        d_out = np.hypot(X - cx, Y - cy) - r  # <= 0 inside
        inside = d_out <= 0
        depth = np.minimum.reduce([X, Y, n - X, n - Y])  # distance to the square border
        corner = (np.hypot(X - cx, Y - cy) > 0)
        dist_in = np.where(corner, -d_out, depth)
        rim = inside & (dist_in <= 1.0)

        def pool(m):
            return m.reshape(n, SS, n, SS).mean(axis=(1, 3))
        cov_shape, cov_rim = pool(inside.astype(np.float64)), pool(rim.astype(np.float64))
        # glyph fitted into n-4
        box = n - 4
        h0, w0 = crop.shape[:2]
        scale = box / max(h0, w0)
        gw, gh = max(1, round(w0 * scale)), max(1, round(h0 * scale))
        small = _area_resize_premul(premul, (gw, gh))
        ga = np.clip(small[..., 3], 0.0, 1.0)
        glin = np.where(ga[..., None] > 1e-6, small[..., :3] / np.maximum(ga[..., None], 1e-6), 0.0)
        glyph_a = np.zeros((n, n))
        glyph_lin = np.zeros((n, n, 3))
        ox, oy = (n - gw) // 2, (n - gh) // 2
        glyph_a[oy:oy + gh, ox:ox + gw] = ga
        glyph_lin[oy:oy + gh, ox:ox + gw] = glin
        y_before = _rel_lum(glyph_lin)
        lift = (glyph_a > 0.05) & (y_before < TOKEN_MIN_REL_LUM)
        k = np.where(lift, TOKEN_MIN_REL_LUM / np.maximum(y_before, 1e-4), 1.0)
        k = np.minimum(k, 1.0 / np.maximum(glyph_lin.max(axis=-1), 1e-4))
        glyph_lin = np.clip(glyph_lin * k[..., None], 0.0, 1.0)
        y_after = _rel_lum(glyph_lin)
        # outline = glyph alpha dilated by 1 px
        pad = np.pad(glyph_a, 1)
        dil = np.max(np.stack([pad[1 + dy:1 + dy + n, 1 + dx:1 + dx + n] for dy in (-1, 0, 1) for dx in (-1, 0, 1)]),
                     axis=0)
        body, rimc, outl = _srgb8_to_lin(TOKEN_BODY), _srgb8_to_lin(TOKEN_RIM), _srgb8_to_lin(TOKEN_OUTLINE)
        # layers (linear, over): body -> rim -> outline -> glyph, all within the token shape
        rgb = np.broadcast_to(body, (n, n, 3)).copy()
        rim_w = np.clip(cov_rim / np.maximum(cov_shape, 1e-6), 0.0, 1.0)[..., None]
        rgb = rgb * (1 - rim_w) + rimc * rim_w
        ow = np.clip(dil - glyph_a, 0.0, 1.0)[..., None]
        rgb = rgb * (1 - ow) + outl * ow
        rgb = rgb * (1 - glyph_a[..., None]) + glyph_lin * glyph_a[..., None]
        out = np.concatenate([_lin_to_srgb8(rgb), np.clip(np.round(cov_shape * 255.0), 0, 255).astype(np.uint8)[..., None]],
                             axis=2)
        dst = ICON_DIR / f"ui-action-attack-token-{size}.png"
        Image.fromarray(out, mode="RGBA").save(dst, optimize=False)
        mask = np.zeros((n, n, 4), dtype=np.uint8)
        mask[..., :3] = 255
        mask[..., 3] = np.clip(np.round(glyph_a * 255.0), 0, 255).astype(np.uint8)
        mdst = ICON_DIR / f"ui-action-attack-token-{size}-glyphmask.png"
        Image.fromarray(mask, mode="RGBA").save(mdst, optimize=False)
        # predicted contrasts on the texture itself (not a frame measurement)
        final_lin = _srgb8_to_lin(out[..., :3])
        yf = _rel_lum(final_lin)
        gm = glyph_a >= 0.5
        shape = cov_shape >= 0.5
        ring1 = shape & ~np.pad(shape, 1)[2:, 1:-1] | shape & ~np.pad(shape, 1)[:-2, 1:-1] | \
            shape & ~np.pad(shape, 1)[1:-1, 2:] | shape & ~np.pad(shape, 1)[1:-1, :-2]
        bodym = shape & ~gm & ~ring1
        yb = float(np.median(yf[bodym]))
        manifest["outputs"].append({
            "size": size, "path": rel(dst), "sha256": sha256_file(dst), "glyphMask": rel(mdst),
            "glyphMaskSha256": sha256_file(mdst),
            "ueAsset": f"/Game/ArtTests/ARTMarkers/Textures/T_UI_Action_AttackToken_{size}",
            "glyphBoxPx": [int(ox), int(oy), int(ox + gw), int(oy + gh)],
            "glyphPixelsAlpha05": int(gm.sum()), "bodyPixels": int(bodym.sum()), "rimPixels": int(ring1.sum()),
            "hiltsLifted": int(lift.sum()),
            "glyphRelLumBefore": {"p10": round(float(np.percentile(y_before[glyph_a > 0.5], 10)), 4),
                                  "median": round(float(np.median(y_before[glyph_a > 0.5])), 4)},
            "glyphRelLumAfter": {"p10": round(float(np.percentile(y_after[glyph_a > 0.5], 10)), 4),
                                 "median": round(float(np.median(y_after[glyph_a > 0.5])), 4)},
            "predictedOnTexture": {
                "glyphMedianVsBody": round(_wcag(float(np.median(yf[gm])), yb), 2),
                "glyphP10VsBody": round(_wcag(float(np.percentile(yf[gm], 10)), yb), 2),
                "rimVsBody": round(_wcag(float(np.median(yf[ring1])), yb), 2)}})
        print(dst, manifest["outputs"][-1]["predictedOnTexture"])
    write_json(ICON_DIR / "token-manifest.json", manifest)
    # team shape chips (D-3)
    TEAM_SHAPE_DIR.mkdir(parents=True, exist_ok=True)
    shapes = {"schema": "unmatched.w5br-team-shapes/1",
              "status": "предложено (значок команды ● P1 / ⬡ P2, решение советника D-3)", "outputs": []}
    n = 12
    g = (np.arange(n * SS) + 0.5) / SS
    X, Y = np.meshgrid(g, g)
    cxy = n / 2.0
    for name in ("circle", "hex"):
        if name == "circle":
            m = np.hypot(X - cxy, Y - cxy) <= 5.5
        else:
            # pointy left/right (corners at 0/60/.../300 deg like SM_Marker_TeamRing_P2), circumradius 6
            ang = np.arctan2(-(Y - cxy), X - cxy)
            rr = np.hypot(X - cxy, Y - cxy)
            a6 = np.mod(ang, np.pi / 3) - np.pi / 6
            m = rr * np.cos(a6) <= 6.0 * np.cos(np.pi / 6)
        cov = m.reshape(n, SS, n, SS).mean(axis=(1, 3))
        img = np.zeros((n, n, 4), dtype=np.uint8)
        img[..., :3] = 255
        img[..., 3] = np.clip(np.round(cov * 255.0), 0, 255).astype(np.uint8)
        dst = TEAM_SHAPE_DIR / f"team-shape-{name}-{n}.png"
        Image.fromarray(img, mode="RGBA").save(dst, optimize=False)
        shapes["outputs"].append({"shape": name, "team": "P1" if name == "circle" else "P2", "size": n,
                                  "path": rel(dst), "sha256": sha256_file(dst),
                                  "ueAsset": f"/Game/ArtTests/ARTMarkers/Textures/T_UI_TeamShape_{name.capitalize()}_{n}",
                                  "coverageSum": round(float(cov.sum()), 2)})
        print(dst)
    write_json(TEAM_SHAPE_DIR / "team-shapes-manifest.json", shapes)
    return 0


def cmd_import_icons(a) -> int:
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    log = out / "import-icons.log"
    script = REPO / "tools" / "art" / "art004_hud_icon_import.py"
    args = [str(UPROJECT), "-run=pythonscript", f"-script={script}", "-unattended", "-nosplash", "-nullrhi",
            "-nullaudio", MCP_OFF, "-log", f"-abslog={log}"]
    started = time.time()
    r = subprocess.run([str(EDITOR_CMD)] + args, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=a.timeout, creationflags=NO_WINDOW)
    text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
    passes = re.findall(r"ART004_HUD_ICON_IMPORT_PASS .*", text)
    rec = {"schema": "unmatched.t22-icon-import/1", "startedLocal": now_local(), "exitCode": r.returncode,
           "durationS": round(time.time() - started, 1), "log": rel(log), "pass": passes,
           "errors": [ln for ln in text.splitlines() if "Error" in ln and "LogPython" in ln][:30]}
    write_json(out / "import-icons.json", rec)
    print(json.dumps({k: rec[k] for k in ("exitCode", "durationS", "pass")}, ensure_ascii=False))
    for ln in rec["errors"]:
        print("  |", ln[:300])
    return 0 if r.returncode == 0 and len(passes) == 1 else 1


PLATE_MARKER = (200, 160, 255)  # #C8A0FF, FLinearColor(FColor(200,160,255)) in S08FlowGameMode.cpp
SHOT_PLATE = re.compile(r"SHOT plate fighter=(\S+) bbox=\((-?\d+),(-?\d+),(-?\d+),(-?\d+)\) overlapReachable=(\d+)")


def cmd_qa(a) -> int:
    """QA-010 plate + icon on a published run (host frame) and the plate marker pixel gate:
    the #C8A0FF strip must fill the top rows of the traced plate bbox and appear nowhere else."""
    from PIL import Image
    run = Path(a.run_dir).resolve()
    qa = run / "qa010"
    qa.mkdir(exist_ok=True)
    host_trace = run / "phase2-client-host.trace.log"
    host_png = run / "phase2-board-host-1920x1080.png"
    tool = REPO / "tools" / "art" / "qa010" / "qa010.py"
    out = {"schema": "unmatched.t22-qa/1", "run": rel(run), "checkedLocal": now_local(), "commands": {}}
    for name, args in (("plate", ["plate", "--trace", str(host_trace), "--frame", str(host_png),
                                  "--overlay", str(qa / "plate-overlay.png"), "--json", str(qa / "plate.json")]),
                       ("icon", ["icon", str(host_png), "--trace", str(host_trace), "--json", str(qa / "icon.json")])):
        r = subprocess.run([sys.executable, str(tool)] + args, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", creationflags=NO_WINDOW)
        doc = json.loads((qa / f"{name}.json").read_text(encoding="utf-8")) if (qa / f"{name}.json").is_file() else {}
        out["commands"][name] = {"exit": r.returncode, "status": doc.get("status"), "result": doc.get("result"),
                                 "argv": ["python", "tools/art/qa010/qa010.py"] + [
                                     rel(Path(x)) if (":" in x or "/" in x or "\\" in x) and Path(x).is_absolute() else x
                                     for x in args]}
        if name == "plate":
            out["commands"][name]["clientCrossCheck"] = doc.get("client_cross_check")
            out["commands"][name]["checkedCells"] = doc.get("checked_cells")
        if name == "icon":
            out["commands"][name]["sizes"] = [{k: s.get(k) for k in ("size_px", "contrast_ratio", "pass", "upscaled")}
                                              for s in doc.get("sizes", [])]
    text = host_trace.read_text(encoding="utf-8", errors="replace")
    m = None
    for m in SHOT_PLATE.finditer(text):
        pass
    gate = {"marker": "#C8A0FF", "tolerance": 16}
    if m:
        x0, y0, x1, y1 = (int(m.group(i)) for i in range(2, 6))
        im = Image.open(host_png).convert("RGB")
        px = im.load()
        w, h = im.size

        def hit(c):
            return all(abs(u - v) <= 16 for u, v in zip(c, PLATE_MARKER))
        inside = sum(1 for x in range(max(0, x0), min(w, x1)) for y in range(max(0, y0), min(h, y0 + 3)) if hit(px[x, y]))
        expected = max(0, min(w, x1) - max(0, x0)) * 3
        outside = sum(1 for y in range(h) for x in range(w)
                      if not (x0 <= x < x1 and y0 <= y < y1) and hit(px[x, y]))
        gate.update(bbox=[x0, y0, x1, y1], stripInside=inside, stripExpected=expected, outside=outside,
                    passed=bool(expected and inside >= 0.9 * expected and outside == 0))
    else:
        gate.update(passed=False, reason="no SHOT plate line in the host trace")
    out["plateMarkerGate"] = gate
    write_json(qa / "qa-summary.json", out)
    # The run manifest lists every published byte: append the QA outputs.
    man = run / "manifest.json"
    if man.is_file():
        doc = json.loads(man.read_text(encoding="utf-8-sig"))
        listed = {e["name"]: e for e in doc["files"]}
        for f in sorted(qa.rglob("*")):
            if f.is_file():
                name = f.relative_to(run).as_posix()
                entry = {"name": name, "bytes": f.stat().st_size, "sha256": sha256_file(f)}
                if name in listed:
                    listed[name].update(entry)
                else:
                    doc["files"].append(entry)
        doc["qa010By"] = "tools/art/art004_hud_t22.py qa (qa010 plate/icon + #C8A0FF plate marker gate)"
        man.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"run": run.name, "plate": out["commands"]["plate"]["result"],
                      "icon": out["commands"]["icon"]["result"], "markerGate": gate.get("passed"),
                      "strip": [gate.get("stripInside"), gate.get("stripExpected"), gate.get("outside")]},
                     ensure_ascii=False))
    ok = (out["commands"]["plate"]["result"] == "pass" and out["commands"]["icon"]["result"] == "pass"
          and gate.get("passed"))
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("editor-build")
    b.add_argument("--label", required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--max-parallel", type=int, default=0)
    b.add_argument("--extra", action="append", default=[])
    t = sub.add_parser("tests")
    t.add_argument("--label", required=True)
    t.add_argument("--out", required=True)
    t.add_argument("--filter", default="Unmatched.S08.ArtHud")
    t.add_argument("--timeout", type=int, default=1500)
    sub.add_parser("icons")
    sub.add_parser("tokens", help="W5b-R D-5 attack token 24/32/48 + glyph masks, D-3 team shape chips")
    i = sub.add_parser("import-icons")
    i.add_argument("--out", required=True)
    i.add_argument("--timeout", type=int, default=900)
    q = sub.add_parser("qa")
    q.add_argument("run_dir")
    a = ap.parse_args(argv)
    return {"editor-build": cmd_editor_build, "tests": cmd_tests, "icons": cmd_icons, "tokens": cmd_tokens,
            "import-icons": cmd_import_icons, "qa": cmd_qa}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
