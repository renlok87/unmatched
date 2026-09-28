"""Colorimetry used by every QA-010 image check.

Conventions (recorded in docs/art-pipeline/qa010/README.md):
- Input pixels are 8-bit sRGB-encoded R'G'B' (what a PNG screenshot stores
  after UE's tonemapper and back-buffer sRGB encode). Alpha is ignored, not
  composited: UE screenshots may carry alpha=0 on opaque pixels.
- "luma" = Rec.709 luma Y' = 0.2126 R' + 0.7152 G' + 0.0722 B' on the encoded
  0..255 values (same formula as tools/s05/s05_frame_measure.ps1 and
  tools/art/check_art_preview_shot.py, so numbers stay comparable).
- "relative luminance" Y = same coefficients on *linear* RGB (IEC 61966-2-1
  sRGB decode, threshold 0.04045); used for EV differences and WCAG contrast.
- Deuteranopia = Machado, Oliveira & Fernandes 2009, severity 1.0 matrix,
  applied to linear RGB, clipped to [0, 1], re-encoded to sRGB.
- UE trap: FLinearColor components are linear. A Slate/HUD colour written as
  FLinearColor(1, .25, .25) lands on screen as sRGB bytes ~(255, 137, 137),
  not #FF4040; FLinearColor(FColor(255, 64, 64)) lands as (255, 64, 64).
  Compare screenshot bytes with expected_srgb_bytes_from_linear(), never with
  the raw FLinearColor components.
"""

from __future__ import annotations

import numpy as np

REC709 = np.array([0.2126, 0.7152, 0.0722], dtype=np.float64)

# Machado et al. 2009, "A Physiologically-based Model for Simulation of Color
# Vision Deficiency", Table for deuteranomaly, severity 1.0 (= deuteranopia).
MACHADO_DEUTERANOPIA_1_0 = np.array([
    [0.367322, 0.860646, -0.227968],
    [0.280085, 0.672501, 0.047413],
    [-0.011820, 0.042940, 0.968881],
], dtype=np.float64)

# sRGB (D65) linear RGB -> CIE XYZ, IEC 61966-2-1.
_RGB_TO_XYZ = np.array([
    [0.4124564, 0.3575761, 0.1804375],
    [0.2126729, 0.7151522, 0.0721750],
    [0.0193339, 0.1191920, 0.9503041],
], dtype=np.float64)
_D65_WHITE = np.array([0.95047, 1.0, 1.08883], dtype=np.float64)

_LUT_U8_TO_LINEAR = None


def _lut() -> np.ndarray:
    global _LUT_U8_TO_LINEAR
    if _LUT_U8_TO_LINEAR is None:
        _LUT_U8_TO_LINEAR = srgb_to_linear(np.arange(256, dtype=np.float64) / 255.0)
    return _LUT_U8_TO_LINEAR


def srgb_to_linear(encoded01) -> np.ndarray:
    """IEC 61966-2-1 decode of values in [0, 1]."""
    c = np.asarray(encoded01, dtype=np.float64)
    return np.where(c <= 0.04045, c / 12.92, np.power((c + 0.055) / 1.055, 2.4))


def linear_to_srgb(linear01) -> np.ndarray:
    """IEC 61966-2-1 encode; input is clipped to [0, 1] first."""
    c = np.clip(np.asarray(linear01, dtype=np.float64), 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1.0 / 2.4) - 0.055)


def quantize_u8(values01) -> np.ndarray:
    """Round half up to 8-bit (deterministic, platform independent)."""
    v = np.clip(np.asarray(values01, dtype=np.float64), 0.0, 1.0) * 255.0
    return np.floor(v + 0.5).astype(np.uint8)


def u8_to_linear(rgb_u8) -> np.ndarray:
    """uint8 sRGB array (..., 3) -> float64 linear RGB via exact 256-entry LUT."""
    a = np.asarray(rgb_u8)
    if a.dtype != np.uint8:
        raise TypeError("u8_to_linear expects uint8 input")
    return _lut()[a]


def luma_u8(rgb_u8) -> np.ndarray:
    """Rec.709 luma Y' (0..255 float) of encoded 8-bit pixels."""
    a = np.asarray(rgb_u8, dtype=np.float64)
    return a[..., 0] * REC709[0] + a[..., 1] * REC709[1] + a[..., 2] * REC709[2]


def relative_luminance_linear(rgb_linear) -> np.ndarray:
    a = np.asarray(rgb_linear, dtype=np.float64)
    return a[..., 0] * REC709[0] + a[..., 1] * REC709[1] + a[..., 2] * REC709[2]


def relative_luminance(rgb_u8) -> np.ndarray:
    """Relative luminance Y in [0, 1] of 8-bit sRGB pixels (WCAG / EV basis)."""
    return relative_luminance_linear(u8_to_linear(rgb_u8))


def grayscale(rgb_u8) -> np.ndarray:
    """Grayscale derivative: Y' replicated to three channels, uint8."""
    y = luma_u8(rgb_u8)
    g = np.floor(np.clip(y, 0.0, 255.0) + 0.5).astype(np.uint8)
    return np.repeat(g[..., None], 3, axis=-1)


def simulate_deuteranopia_linear(rgb_linear, severity: float = 1.0) -> np.ndarray:
    if severity != 1.0:
        raise ValueError("only Machado 2009 severity 1.0 (deuteranopia) is implemented")
    a = np.asarray(rgb_linear, dtype=np.float64)
    return np.clip(a @ MACHADO_DEUTERANOPIA_1_0.T, 0.0, 1.0)


def deuteranopia(rgb_u8, severity: float = 1.0) -> np.ndarray:
    """Deuteranopia derivative of an 8-bit sRGB image (uint8 out)."""
    lin = simulate_deuteranopia_linear(u8_to_linear(rgb_u8), severity)
    return quantize_u8(linear_to_srgb(lin))


def wcag_contrast_ratio(l1, l2):
    """WCAG 2.x contrast ratio of two relative luminances (order-free)."""
    a = np.maximum(l1, l2)
    b = np.minimum(l1, l2)
    return (a + 0.05) / (b + 0.05)


def linear_to_lab(rgb_linear) -> np.ndarray:
    xyz = np.asarray(rgb_linear, dtype=np.float64) @ _RGB_TO_XYZ.T
    t = xyz / _D65_WHITE
    delta = 6.0 / 29.0
    f = np.where(t > delta ** 3, np.cbrt(t), t / (3 * delta * delta) + 4.0 / 29.0)
    L = 116.0 * f[..., 1] - 16.0
    a = 500.0 * (f[..., 0] - f[..., 1])
    b = 200.0 * (f[..., 1] - f[..., 2])
    return np.stack([L, a, b], axis=-1)


def lab_chroma(rgb_u8) -> tuple[np.ndarray, np.ndarray]:
    """CIE L*a*b* (D65) chroma C*ab and b* of 8-bit sRGB pixels."""
    lab = linear_to_lab(u8_to_linear(rgb_u8))
    return np.hypot(lab[..., 1], lab[..., 2]), lab[..., 2]


def expected_srgb_bytes_from_linear(r: float, g: float, b: float) -> tuple[int, int, int]:
    """Bytes a UE FLinearColor(r, g, b) produces on an sRGB back buffer."""
    out = quantize_u8(linear_to_srgb(np.array([r, g, b], dtype=np.float64)))
    return int(out[0]), int(out[1]), int(out[2])


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.strip().lstrip("#")
    if len(h) != 6:
        raise ValueError(f"bad hex colour {hex_color!r}")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
