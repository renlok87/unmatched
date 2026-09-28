"""Which region kinds may stand for a С-9 layer mask. Stdlib only (shared by
the c9 command and the checklist).

03 §4.1 layers: L1 clickable areas, L2 game plane (cobble, zone tint, cell
borders), L3 decorative geometry (lantern, facades, crates/barrels), L4
background (darkness, fog, vignette, torn tray edge). С-9 compares the game
layer with the decor layer L3 ("фасады, декор"); 17 §11.10 measures it on
custom-stencil layer masks.

A region is a *proxy* when its kind cannot be that layer by construction:
  decor: trace-ring (tray/frame ring around the board = L4), trace-cells
         (board cells = L2), frame (whole frame);
  game:  trace-ring (L4), frame.
mask:/bbox:/poly: are caller masks (stencil or hand-drawn): the caller
asserts the layer, the tool cannot verify it and records the kind.
A proxy never yields a normative С-9 result.
"""

from __future__ import annotations

from typing import Iterable, Optional

PROXY_KINDS = {
    "decor": {
        "trace-ring": "кольцо вокруг доски = поднос/рамка (L4 фон по 03 §4.1), не декор L3",
        "trace-cells": "клетки доски = игровая плоскость L2, не декор L3",
        "frame": "весь кадр, не маска слоя L3",
    },
    "game": {
        "trace-ring": "кольцо вокруг доски = поднос (L4), не игровой слой",
        "frame": "весь кадр, не маска игрового слоя",
    },
}
LAYER_NEED = {"decor": "stencil- или ручная маска L3", "game": "маска игрового слоя L1/L2"}
LAYER_NAME = {"decor": "декор", "game": "игровой слой"}


def spec_kind(spec: str) -> str:
    """'NAME=KIND:ARGS' -> KIND ('' if unparsable)."""
    if "=" not in spec:
        return ""
    return spec.split("=", 1)[1].partition(":")[0].strip()


def region_proxy_reason(layer: str, kind: str, flagged: bool = False, note: str = "") -> Optional[str]:
    why = PROXY_KINDS.get(layer, {}).get(kind)
    if why:
        return why
    if flagged:
        return note or "регион помечен как прокси"
    return None


def proxy_regions(layer_regions: Iterable[tuple[str, str, str, bool, str]]) -> list[dict]:
    """layer_regions: (layer, spec, kind, flagged_proxy, note) -> proxy list."""
    out = []
    for layer, spec, kind, flagged, note in layer_regions:
        why = region_proxy_reason(layer, kind, flagged, note)
        if why:
            out.append({"layer": layer, "spec": spec, "kind": kind, "why": why})
    return out


def proxy_status(proxies: list[dict]) -> str:
    """Checklist status for a С-9 result measured on proxy masks."""
    layers = [lay for lay in ("decor", "game") if any(p["layer"] == lay for p in proxies)]
    who = " и ".join(LAYER_NAME[lay] for lay in layers)
    need = "; ".join(LAYER_NEED[lay] for lay in layers)
    return f"нет данных: {who} — прокси (нужна {need})"
