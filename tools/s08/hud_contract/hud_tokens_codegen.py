#!/usr/bin/env python3
"""HUD style tokens -> C++ header (VS-1 HB-03, ВР-45, ВР-77; 02-visual-design.md §2.8, 04-hud-spec.md §4.4).

  python tools/s08/hud_contract/hud_tokens_codegen.py            write unreal/.../S08/S08HudTokens.generated.h
  python tools/s08/hud_contract/hud_tokens_codegen.py --check    exit 1 when the header on disk is not what the JSON gives

One source: docs/unreal/contracts/hud/hud-style-tokens.json. The generator resolves the aliases (field "alias", by
chain), keeps the opacity as a separate float, and writes namespace S08HudTokens:
  constexpr FColor Color_<Name>      sRGB bytes; the code converts them only with FLinearColor::FromSRGBColor
  constexpr float  Alpha_<Name>      tokens with "alpha" and the "opacity" group
  constexpr int32  TypeSu_<Name>     type.* scale (02 §3.3) + TypeFace_<Name> / TypeCaps_<Name>
  constexpr float  Space_* Radius_* MotionMs_*, int32 IconPx_*
  kColors / kAlphas / kTypes / kSpace / kRadius / kMotionMs / kSkins   name tables (theme fallback, tests)
  kTokensJsonSha256                  sha256 of the JSON (CRLF -> LF); hud_contract.py validate compares it

Order is stable (names sorted inside each group), the output is LF and byte-identical on a re-run. Stdlib only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TOKENS = REPO / "docs/unreal/contracts/hud/hud-style-tokens.json"
HEADER = REPO / "unreal/Unmatched/Source/Unmatched/S08/S08HudTokens.generated.h"
SHA_RE = re.compile(r'kTokensJsonSha256\s*=\s*TEXT\("([0-9a-f]{64})"\)')
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
FACES = ("BoldCondensed", "Bold", "Regular")


class TokenError(ValueError):
    pass


def normalized_bytes(path: Path) -> bytes:
    """JSON bytes with CRLF -> LF: the hash must not depend on core.autocrlf of the checkout."""
    return Path(path).read_bytes().replace(b"\r\n", b"\n")


def json_sha256(path: Path = TOKENS) -> str:
    return hashlib.sha256(normalized_bytes(path)).hexdigest()


def load(path: Path = TOKENS) -> dict:
    return json.loads(normalized_bytes(path).decode("utf-8"))


def camel(name: str) -> str:
    return "".join(p[:1].upper() + p[1:] for p in re.split(r"[.\-_]", name) if p)


def strip_prefix(name: str, prefix: str) -> str:
    return name[len(prefix):] if name.startswith(prefix) else name


def hex_bytes(hexstr: str) -> tuple[int, int, int]:
    h = hexstr.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def resolve_color(colors: dict, name: str, seen: tuple = ()) -> tuple[str, float]:
    """(hex of the end of the alias chain, alpha of the token itself) - an alias takes the colour, never the alpha."""
    if name not in colors:
        raise TokenError("colors.%s: нет такого токена" % name)
    if name in seen:
        raise TokenError("colors: цикл алиасов %s" % " -> ".join(seen + (name,)))
    tok = colors[name]
    alpha = tok.get("alpha", 1.0)
    if not isinstance(alpha, (int, float)) or not 0.0 <= float(alpha) <= 1.0:
        raise TokenError("colors.%s: alpha %r" % (name, alpha))
    if "alias" in tok:
        hexstr, _ = resolve_color(colors, tok["alias"], seen + (name,))
        if "hex" in tok and tok["hex"].upper() != hexstr.upper():
            raise TokenError("colors.%s: hex %s не равен раскрытому алиасу %s (%s)" % (name, tok["hex"], tok["alias"], hexstr))
        return hexstr.upper(), float(alpha)
    hexstr = tok.get("hex", "")
    if not HEX_RE.match(hexstr):
        raise TokenError("colors.%s: hex %r" % (name, hexstr))
    return hexstr.upper(), float(alpha)


def mix(a: tuple, b: tuple, t: float) -> tuple:
    return tuple(int(round(x + (y - x) * t)) for x, y in zip(a, b))


def scale(a: tuple, k: float) -> tuple:
    return tuple(max(0, min(255, int(round(x * k)))) for x in a)


def resolve_skin(tokens: dict, name: str) -> dict:
    """A rounded-box fallback skin (ВР-HB06): fill / edge colours by token name, sizes by token name or number."""
    colors = tokens["colors"]
    spec = tokens["skins"][name]

    def color(key: str, default_alpha_key: str | None = None):
        ref = spec.get(key)
        if ref is None:
            return (0, 0, 0), 0.0
        hexstr, alpha = resolve_color(colors, ref)
        rgb = hex_bytes(hexstr)
        if key + "_mix" in spec:
            m = spec[key + "_mix"]
            rgb = mix(rgb, hex_bytes(resolve_color(colors, m["with"])[0]), float(m["t"]))
        if key + "_scale" in spec:
            rgb = scale(rgb, float(spec[key + "_scale"]))
        if key + "_alpha" in spec:
            alpha = float(spec[key + "_alpha"])
        return rgb, alpha

    def number(key: str, group: str) -> float:
        v = spec.get(key, 0)
        if isinstance(v, str):
            if v not in tokens[group]:
                raise TokenError("skins.%s.%s: нет токена %s" % (name, key, v))
            return float(tokens[group][v]["px"])
        return float(v)

    fill, fill_a = color("fill")
    edge, edge_a = color("edge")
    radius = number("radius", "radii") + float(spec.get("radius_add", 0))
    return {"name": name, "fill": fill, "fill_alpha": fill_a, "edge": edge, "edge_alpha": edge_a,
            "edge_su": float(spec.get("edge_su", 0)), "radius": radius, "half_height": bool(spec.get("half_height", False))}


def collect(tokens: dict) -> dict:
    """Everything the header and the theme import need, already resolved and sorted."""
    colors = tokens["colors"]
    out = {"colors": [], "alphas": [], "types": [], "space": [], "radius": [], "motion": [], "icons": [], "skins": []}
    for name in sorted(colors):
        hexstr, alpha = resolve_color(colors, name)
        out["colors"].append({"name": name, "hex": hexstr, "rgb": hex_bytes(hexstr), "alpha": alpha})
        if "alpha" in colors[name]:
            out["alphas"].append({"name": name, "value": alpha})
    for name in sorted(tokens.get("opacity", {})):
        v = tokens["opacity"][name].get("value")
        if not isinstance(v, (int, float)) or not 0.0 <= float(v) <= 1.0:
            raise TokenError("opacity.%s: value %r" % (name, v))
        out["alphas"].append({"name": name, "value": float(v)})
    out["alphas"].sort(key=lambda a: a["name"])
    for name in sorted(tokens["typography"]):
        tok = tokens["typography"][name]
        if not name.startswith("type."):
            continue
        if not isinstance(tok.get("su"), int) or tok["su"] <= 0:
            raise TokenError("typography.%s: su %r" % (name, tok.get("su")))
        if tok.get("face") not in FACES:
            raise TokenError("typography.%s: face %r (нужно одно из %s)" % (name, tok.get("face"), ", ".join(FACES)))
        out["types"].append({"name": name, "su": tok["su"], "face": tok["face"], "caps": bool(tok.get("caps", False))})
    for group, key in (("spacing", "space"), ("radii", "radius"), ("icons", "icons")):
        for name in sorted(tokens[group]):
            px = tokens[group][name].get("px")
            if not isinstance(px, (int, float)) or px <= 0:
                raise TokenError("%s.%s: px %r" % (group, name, px))
            out[key].append({"name": name, "value": px})
    for name in sorted(tokens["motion"]):
        v = tokens["motion"][name].get("value")
        if not isinstance(v, (int, float)) or v <= 0:
            raise TokenError("motion.%s: value %r" % (name, v))
        out["motion"].append({"name": name, "value": v})
    for name in sorted(tokens.get("skins", {})):
        out["skins"].append(resolve_skin(tokens, name))
    return out


def ident_for(kind: str, name: str) -> str:
    if kind == "Color" or kind == "Alpha":
        return "%s_%s" % (kind, camel(name))
    if kind == "Type":
        return camel(strip_prefix(name, "type."))
    if kind == "Space":
        return "Space_" + camel(strip_prefix(name, "space."))
    if kind == "Radius":
        return "Radius_" + camel(strip_prefix(name, "radius."))
    if kind == "MotionMs":
        base = name[:-3] if name.endswith(".ms") else name
        return "MotionMs_" + camel(base)
    if kind == "IconPx":
        return "IconPx_" + camel(strip_prefix(name, "icon."))
    raise ValueError(kind)


def fnum(v: float) -> str:
    s = repr(float(v))
    return s + "f" if "e" not in s else s


def color_lit(rgb: tuple, a: int = 255) -> str:
    return "FColor(0x%02X, 0x%02X, 0x%02X, 0x%02X)" % (rgb[0], rgb[1], rgb[2], a)


def render(tokens: dict, sha: str) -> str:
    c = collect(tokens)
    seen: dict[str, str] = {}

    def claim(ident: str, name: str) -> str:
        if ident in seen:
            raise TokenError("имя %s у двух токенов: %s и %s" % (ident, seen[ident], name))
        seen[ident] = name
        return ident

    L = []
    w = L.append
    w("// GENERATED by tools/s08/hud_contract/hud_tokens_codegen.py from docs/unreal/contracts/hud/hud-style-tokens.json.")
    w("// Do not edit: change the JSON and run the generator; hud_contract.py validate fails on a stale header (ВР-77).")
    w("// Colours are sRGB bytes: convert them ONLY with FLinearColor::FromSRGBColor (AD-OPEN-39, HUD-RULES П3).")
    w("// Alpha is a separate float; an alias takes the colour of its target, never its alpha.")
    w("#pragma once")
    w("")
    w('#include "CoreMinimal.h"')
    w("")
    w("namespace S08HudTokens {")
    w("")
    w("/** sha256 of hud-style-tokens.json (CRLF -> LF) this header was generated from. */")
    w('inline constexpr const TCHAR* kTokensJsonSha256 = TEXT("%s");' % sha)
    w("")
    w("// ---- colours (%d) ----" % len(c["colors"]))
    for t in c["colors"]:
        w("inline constexpr FColor %s = %s;  // %s %s" % (claim(ident_for("Color", t["name"]), t["name"]),
                                                        color_lit(t["rgb"]), t["name"], t["hex"]))
    w("")
    w("// ---- alpha (%d): colour tokens with an alpha field + the opacity group ----" % len(c["alphas"]))
    for t in c["alphas"]:
        w("inline constexpr float %s = %s;  // %s" % (claim(ident_for("Alpha", t["name"]), t["name"]), fnum(t["value"]), t["name"]))
    w("")
    w("// ---- type scale (%d), su at 1080p / 100 %%; face = typeface of the default Slate composite font ----" % len(c["types"]))
    for t in c["types"]:
        base = ident_for("Type", t["name"])
        w("inline constexpr int32 %s = %d;  // %s" % (claim("TypeSu_" + base, t["name"]), t["su"], t["name"]))
        w('inline constexpr const TCHAR* %s = TEXT("%s");' % (claim("TypeFace_" + base, t["name"] + ".face"), t["face"]))
        w("inline constexpr bool %s = %s;" % (claim("TypeCaps_" + base, t["name"] + ".caps"), "true" if t["caps"] else "false"))
    w("")
    for kind, key, ctype in (("Space", "space", "float"), ("Radius", "radius", "float"), ("MotionMs", "motion", "float"),
                             ("IconPx", "icons", "int32")):
        w("// ---- %s (%d) ----" % (kind, len(c[key])))
        for t in c[key]:
            v = fnum(t["value"]) if ctype == "float" else str(int(t["value"]))
            w("inline constexpr %s %s = %s;  // %s" % (ctype, claim(ident_for(kind, t["name"]), t["name"]), v, t["name"]))
        w("")
    w("// ---- name tables (theme fallback UUmHudTheme::BuildFromHeader, tests) ----")
    w("struct FColorToken { const TCHAR* Name; FColor Srgb; float Alpha; };")
    w("struct FScalarToken { const TCHAR* Name; float Value; };")
    w("struct FTypeToken { const TCHAR* Name; int32 Su; const TCHAR* Face; bool bCaps; };")
    w("struct FSkinToken { const TCHAR* Name; FColor Fill; float FillAlpha; FColor Edge; float EdgeAlpha; float EdgeSu;"
      " float RadiusSu; bool bHalfHeight; };")
    w("")
    w("inline constexpr FColorToken kColors[] = {")
    for t in c["colors"]:
        w('    {TEXT("%s"), %s, %s},' % (t["name"], color_lit(t["rgb"]), fnum(t["alpha"])))
    w("};")
    w("inline constexpr FScalarToken kAlphas[] = {")
    for t in c["alphas"]:
        w('    {TEXT("%s"), %s},' % (t["name"], fnum(t["value"])))
    w("};")
    w("inline constexpr FTypeToken kTypes[] = {")
    for t in c["types"]:
        w('    {TEXT("%s"), %d, TEXT("%s"), %s},' % (t["name"], t["su"], t["face"], "true" if t["caps"] else "false"))
    w("};")
    for table, key in (("kSpace", "space"), ("kRadius", "radius"), ("kMotionMs", "motion"), ("kIconPx", "icons")):
        w("inline constexpr FScalarToken %s[] = {" % table)
        for t in c[key]:
            w('    {TEXT("%s"), %s},' % (t["name"], fnum(t["value"])))
        w("};")
    if c["skins"]:
        w("/** Rounded-box fallback skins (ВР-HB06): HB-10 replaces them with 9-slice PNG under the same names. */")
        w("inline constexpr FSkinToken kSkins[] = {")
        for s in c["skins"]:
            w('    {TEXT("%s"), %s, %s, %s, %s, %s, %s, %s},' % (
                s["name"], color_lit(s["fill"]), fnum(s["fill_alpha"]), color_lit(s["edge"]), fnum(s["edge_alpha"]),
                fnum(s["edge_su"]), fnum(s["radius"]), "true" if s["half_height"] else "false"))
        w("};")
    else:
        w("inline constexpr FSkinToken kSkins[] = {{nullptr, FColor(0, 0, 0, 0), 0.0f, FColor(0, 0, 0, 0), 0.0f, 0.0f, 0.0f, false}};")
    w("inline constexpr int32 kNumSkins = %d;" % len(c["skins"]))
    w("")
    w("}  // namespace S08HudTokens")
    return "\n".join(L) + "\n"


def generate(tokens_path: Path = TOKENS, header_path: Path = HEADER, write: bool = True) -> str:
    text = render(load(tokens_path), json_sha256(tokens_path))
    if write:
        Path(header_path).parent.mkdir(parents=True, exist_ok=True)
        Path(header_path).write_bytes(text.encode("utf-8"))
    return text


def header_sha(header_path: Path = HEADER) -> str | None:
    if not Path(header_path).exists():
        return None
    m = SHA_RE.search(Path(header_path).read_text(encoding="utf-8"))
    return m.group(1) if m else None


def header_errors(tokens_path: Path = TOKENS, header_path: Path = HEADER) -> list[str]:
    """G-TOKENS: the header exists and was generated from this exact JSON."""
    have = header_sha(header_path)
    if have is None:
        return ["header stale: %s нет или в нём нет kTokensJsonSha256 — запустите hud_tokens_codegen.py" % Path(header_path).name]
    want = json_sha256(tokens_path)
    if have != want:
        return ["header stale: %s собран из JSON sha256 %s…, а hud-style-tokens.json сейчас %s… — запустите"
                " python tools/s08/hud_contract/hud_tokens_codegen.py" % (Path(header_path).name, have[:12], want[:12])]
    return []


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="do not write; exit 1 when the header differs")
    ap.add_argument("--tokens", type=Path, default=TOKENS)
    ap.add_argument("--header", type=Path, default=HEADER)
    a = ap.parse_args(argv)
    try:
        text = generate(a.tokens, a.header, write=False)
    except TokenError as e:
        print("ERROR", e)
        return 1
    if a.check:
        on_disk = a.header.read_bytes().replace(b"\r\n", b"\n").decode("utf-8") if a.header.exists() else ""
        ok = on_disk == text
        print("HUD_TOKENS_HEADER", "FRESH" if ok else "STALE", a.header)
        return 0 if ok else 1
    a.header.parent.mkdir(parents=True, exist_ok=True)
    a.header.write_bytes(text.encode("utf-8"))
    print("HUD_TOKENS_HEADER written", a.header, "%d bytes" % len(text.encode("utf-8")), "sha256", json_sha256(a.tokens)[:12])
    return 0


if __name__ == "__main__":
    sys.exit(main())
