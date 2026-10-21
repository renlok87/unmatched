"""Opt-in textures keys of the 2026-10-20 batch, F12 (Bruce Lee model acceptance r1: T 0.5): textures.color_repaint
(texels of the listed parts whose BaseColor passes match_hsv take the colour of the nearest texels of the same parts that
pass keep_hsv; Tripo navy on the stripe edges, a dark band on the inner thighs) and textures.roughness_remap (ORM.G of the
listed parts by its Tripo rank into [lo, hi], with or without metal). Without the keys the textures stage writes the same
bytes as before (pinned sha256 of a synthetic atlas, computed with the code before the keys).

Plain Python (numpy, scipy, Pillow), no Blender.
Run: python -m pytest tools/tripo-pipeline/blender/h2_bake/tests -q -k color_repaint"""

import copy
import hashlib
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
sys.path.insert(0, str(PKG.parent))


def load_local(name):
    spec = importlib.util.spec_from_file_location("h2cr_" + name, PKG / (name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SIZE = 64
PITCH = 0.002  # metres per texel of the synthetic rest-position map
YELLOW = (0.85, 0.65, 0.10)
NAVY = (0.04, 0.05, 0.13)
BLACK = (0.08, 0.08, 0.08)


def synthetic_run(root):
    """work/uv + work/bake of a three-part figure on a 64 px atlas, rest positions on a plane (2 mm per texel):
    tripo_part_0 (columns 4..27) yellow cloth (22..27 brighter) with a stripe (black core 14..15, navy edges 13 and 16) and a dark patch
    (rows 40..47, columns 6..9); tripo_part_1 (28..43) grey (metal for the metal fixture); tripo_part_2 (44..59) base."""
    w = root / "work"
    (w / "uv").mkdir(parents=True)
    (w / "bake").mkdir(parents=True)
    (root / "reports").mkdir()
    pid = np.full((SIZE, SIZE), -1, np.int64)
    pid[:, 4:28] = 0
    pid[:, 28:44] = 1
    pid[:, 44:60] = 2
    cov = pid >= 0
    np.save(w / "uv" / "part_ids.npy", pid)
    np.save(w / "uv" / "base_band.npy", np.zeros((SIZE, SIZE), bool))
    yy, xx = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32)
    pos = np.stack([xx * PITCH, np.zeros_like(xx), yy * PITCH], -1).astype(np.float32)
    np.save(w / "uv" / "position.npy", pos)
    np.save(w / "uv" / "position_alpha.npy", cov.astype(np.uint8))
    bc = np.zeros((SIZE, SIZE, 3), np.float32)
    bc[:, 4:28] = YELLOW
    bc[:, 22:28] = (0.95, 0.75, 0.12)  # brighter yellow: outside the cloth_hsv of the metal fixture
    bc[:, 26:28] = (0.50, 0.50, 0.55)  # a smear of the neighbour's grey at the contact (band_repaint fixture)
    bc[:, 14:16] = BLACK
    bc[:, 13] = NAVY
    bc[:, 16] = NAVY
    bc[40:48, 6:10] = (0.15, 0.15, 0.2)
    bc[:, 28:44] = (0.60, 0.60, 0.62)
    bc[:, 44:60] = 0.3
    ao = np.repeat(np.linspace(0.3, 1.0, SIZE, dtype=np.float32)[None, :, None], SIZE, 0).repeat(3, 2)
    rough = np.repeat(np.linspace(0.3, 0.6, SIZE, dtype=np.float32)[:, None], SIZE, 1)
    rm = np.stack([np.zeros_like(rough), rough, np.zeros_like(rough)], -1)
    maps = {"NORMAL": np.broadcast_to(np.array([0.5, 0.5, 1.0], np.float32), (SIZE, SIZE, 3)).copy(), "AO": ao,
            "BC": bc, "RM": rm}
    for k, v in maps.items():
        np.save(w / "bake" / ("%s.npy" % k), v)
    for k in ("NORMAL", "AO", "BC", "RM", "HIT"):
        np.save(w / "bake" / ("%s_alpha.npy" % k), cov)
    return pid


def tex_profile(**extra):
    t = {"prefix": "T_Synth_H2", "ao_gate": {"min_range_p1_p99": 0, "min_occluded_fraction": 0, "occluded_below": 250},
         "team_mask": {"cloth_parts": [], "base_band": {"part": "tripo_part_2", "normal_z_abs_max": 0.35}, "blur": 0},
         "edge_extend_px": 4}
    t.update(extra)
    return {"parts": {"tripo_part_0": {"mesh": "body"}, "tripo_part_1": {"mesh": "body"}, "tripo_part_2": {"mesh": "base"}},
            "textures": t}


BAND = [{"name": "edge", "part": "tripo_part_0", "near": ["tripo_part_1"], "band_m": 0.006, "ring_m": 0.006}]
METAL = {"metal": {"hue_deg": [-10, 370], "hue_ramp_deg": 1, "ramp": 0.04, "blur": 1,
                   "parts": {"tripo_part_1": {"terms": [{"kind": "texel", "hue_deg": [-10, 370], "s_min": -1.0, "s_max": 0.2,
                                                         "v_min": 0.3}]}},
                   "basecolor": {"target_srgb": "#B8BEC4", "detail_gamma": 1.0, "detail_clip": [0.25, 1.4]},
                   "metallic": {"min": 0.9, "max": 1.0}, "roughness": {"min": 0.32, "max": 0.45, "detail_weight": 0.6}},
         "cloth_roughness": {"apply": True, "lo": 0.8, "hi": 0.9}}
METAL_CLOTH = {"cloth_parts": ["tripo_part_0"], "cloth_hsv": {"v_max": 0.9, "s_max": 0.9, "ramp": 0.01},
               "base_band": {"part": "tripo_part_2", "normal_z_abs_max": 0.35}, "blur": 0}

FIXTURES = {
    "plain": lambda: tex_profile(),
    "band_repaint": lambda: tex_profile(band_repaint=copy.deepcopy(BAND)),
    "metal_cloth_roughness": lambda: tex_profile(materials=copy.deepcopy(METAL), team_mask=copy.deepcopy(METAL_CLOTH)),
}

# sha256 of every written file (textures/*.png, work/uv/metal_mask.npy) by the textures stage BEFORE the F12 keys
# (h2-bake 0.9.0 code of 2026-10-21, computed once on this fixture and pinned)
EXPECTED = {
    "band_repaint": {
        "T_Synth_H2_2K_BC.png": "988a81e44ffb80e472205de44abe050cff095c4411fb2c3a61fe4c333fab4075",
        "T_Synth_H2_2K_N.png": "f6af388e1ac6299db21fe94b2efe7626a00c8ae5bdecc8c6e0db59ef5ae415f9",
        "T_Synth_H2_2K_N_OpenGL.png": "57e65954db64fb1990fbbb744be92983a6b71f9abadb443b2e01e9eb75eafb21",
        "T_Synth_H2_2K_ORM.png": "8a31cc99d12796a839f21a628da8087108ade46a1ef4ea24b2ac37d92e4da928",
        "T_Synth_H2_2K_TeamMask.png": "8a8b0524c38a3c6dec0e4543bc7a882f5f331cee85fa12ecc0e0510574d9139a",
        "T_Synth_H2_BC.png": "bc34a070c0289acf3406b41537ecfa0d3b433e5f899213a816529b1cf8513b4f",
        "T_Synth_H2_N.png": "6dd4a31954cff53048f39ba79d2ab4e79f6a7812d937bc4c632c788e6c804754",
        "T_Synth_H2_N_OpenGL.png": "05ab8f18a74566086ff67380d6284bcda971a9a6d5c4529270673d84b999c0bf",
        "T_Synth_H2_ORM.png": "a69f8c4e921d28a8b0f9074c3d1823197f8c2a6fb5abc8b9762298b6065311b9",
        "T_Synth_H2_TeamMask.png": "e0a600268e4e838cbb2d645ad9b64530a4ccac386ae25907aad6d9f68271b733",
        "metal_mask.npy": "1972a63acccc3f17aabd99890058561be7595408dc3426f0c9f027b674ecf96f",
    },
    "metal_cloth_roughness": {
        "T_Synth_H2_2K_BC.png": "8b74d6c5646f0549b3d2079f8e06a61f29d28a07bd5a3e1de8736aedaff7418d",
        "T_Synth_H2_2K_N.png": "f6af388e1ac6299db21fe94b2efe7626a00c8ae5bdecc8c6e0db59ef5ae415f9",
        "T_Synth_H2_2K_N_OpenGL.png": "57e65954db64fb1990fbbb744be92983a6b71f9abadb443b2e01e9eb75eafb21",
        "T_Synth_H2_2K_ORM.png": "34059cb0e01d21fa32bb7874e99f36f899af892ebf871f294ed09f9f1b5c754c",
        "T_Synth_H2_2K_TeamMask.png": "4e201b95c75b403e812801076e33fd6da21c00bbc9f385324d217a1b979a18f9",
        "T_Synth_H2_BC.png": "3d5fcdafeb877f4a4c61e166b4a92e321c98935dad86c6f3469125977f363245",
        "T_Synth_H2_N.png": "6dd4a31954cff53048f39ba79d2ab4e79f6a7812d937bc4c632c788e6c804754",
        "T_Synth_H2_N_OpenGL.png": "05ab8f18a74566086ff67380d6284bcda971a9a6d5c4529270673d84b999c0bf",
        "T_Synth_H2_ORM.png": "aa5deb7ae0a454ea361bbbf89f1445e3fb24ac72da849a7fa7d670e8869314ae",
        "T_Synth_H2_TeamMask.png": "04a0b2f62014468843bddb777922c5807a5018a6154ad71c7103af989ef07935",
        "metal_mask.npy": "2b461cb6c3d99a3c212c8eca410611c050b9526eb61abd28993485cfcc2001ab",
    },
    "plain": {
        "T_Synth_H2_2K_BC.png": "d26874be67ae35f700cc8940fa2d039a0567e6af395c69af6e8927611b7588da",
        "T_Synth_H2_2K_N.png": "f6af388e1ac6299db21fe94b2efe7626a00c8ae5bdecc8c6e0db59ef5ae415f9",
        "T_Synth_H2_2K_N_OpenGL.png": "57e65954db64fb1990fbbb744be92983a6b71f9abadb443b2e01e9eb75eafb21",
        "T_Synth_H2_2K_ORM.png": "8a31cc99d12796a839f21a628da8087108ade46a1ef4ea24b2ac37d92e4da928",
        "T_Synth_H2_2K_TeamMask.png": "8a8b0524c38a3c6dec0e4543bc7a882f5f331cee85fa12ecc0e0510574d9139a",
        "T_Synth_H2_BC.png": "3c3783844399b07b3ef6414faa05a63b81c600fd8ce269fbe648875172f63a38",
        "T_Synth_H2_N.png": "6dd4a31954cff53048f39ba79d2ab4e79f6a7812d937bc4c632c788e6c804754",
        "T_Synth_H2_N_OpenGL.png": "05ab8f18a74566086ff67380d6284bcda971a9a6d5c4529270673d84b999c0bf",
        "T_Synth_H2_ORM.png": "a69f8c4e921d28a8b0f9074c3d1823197f8c2a6fb5abc8b9762298b6065311b9",
        "T_Synth_H2_TeamMask.png": "e0a600268e4e838cbb2d645ad9b64530a4ccac386ae25907aad6d9f68271b733",
        "metal_mask.npy": "1972a63acccc3f17aabd99890058561be7595408dc3426f0c9f027b674ecf96f",
    },
}


def outputs_sha(root):
    files = sorted((root / "textures").glob("*.png")) + [root / "work" / "uv" / "metal_mask.npy"]
    return {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}


@pytest.mark.parametrize("fixture", sorted(FIXTURES))
def test_without_the_keys_the_bytes_are_unchanged(tmp_path, fixture):
    tx = load_local("textures")
    synthetic_run(tmp_path)
    rep = tx.run(tmp_path, FIXTURES[fixture]())
    assert rep["passed"]
    assert "color_repaint" not in rep and "roughness_remap" not in rep
    assert outputs_sha(tmp_path) == EXPECTED[fixture]


# ------------------------------------------------------------------ helpers of the keys (materials.py)
TX = None


def helpers():
    global TX
    if TX is None:
        t = load_local("textures")
        TX = SimpleNamespace(rgb_to_hsv=t.rgb_to_hsv, bilinear=t.bilinear, dilate=t.dilate, blur3=t.blur3)
    return TX


def test_hsv_select_hue_window_and_wrap():
    mat = load_local("materials")
    rgb = np.array([[0.9, 0.1, 0.1], [0.1, 0.1, 0.9], [0.9, 0.7, 0.1], [0.2, 0.2, 0.2]], np.float32)
    assert mat.hsv_select(rgb, {"hue_deg": [190, 270], "s_min": 0.3}, helpers()).tolist() == [False, True, False, False]
    assert mat.hsv_select(rgb, {"hue_deg": [330, 30]}, helpers()).tolist() == [True, False, False, True]  # wrap; grey h=0
    assert mat.hsv_select(rgb, {"v_max": 0.3}, helpers()).tolist() == [False, False, False, True]
    assert mat.hsv_select(rgb, {}, helpers()).all()


def test_color_repaint_replaces_matched_texels_from_kept_neighbours(tmp_path):
    tx = load_local("textures")
    synthetic_run(tmp_path)
    cr = [{"name": "navy_edges", "parts": ["tripo_part_0"], "match_hsv": {"hue_deg": [190, 270], "s_min": 0.3},
           "radius_m": 0.01, "k": 6}]
    rep = tx.run(tmp_path, tex_profile(color_repaint=cr))
    row = rep["color_repaint"]["rows"][0]
    assert row["matched_texels"] == 2 * SIZE and row["repainted_texels"] == 2 * SIZE and row["without_source"] == 0
    from PIL import Image
    bc = np.asarray(Image.open(tmp_path / "textures" / "T_Synth_H2_BC.png")).astype(int)
    h, s, v = tx.rgb_to_hsv(bc[:, [13, 16]].astype(np.float32) / 255.0)
    assert not ((h > 190) & (h < 270) & (s > 0.3)).any()  # no navy left on the stripe edges
    assert (bc[:, 20] == bc[0, 20]).all() and (bc[:, 14] == bc[0, 14]).all()  # yellow and black core untouched


def test_color_repaint_boxes_and_keep(tmp_path):
    tx = load_local("textures")
    synthetic_run(tmp_path)
    box = [{"min_m": [5 * PITCH, -1.0, 39 * PITCH], "max_m": [10 * PITCH, 1.0, 48 * PITCH]}]
    cr = [{"name": "dark_patch", "parts": ["tripo_part_0"], "match_hsv": {"v_max": 0.45}, "keep_hsv": {"s_min": 0.5, "v_min": 0.5},
           "include_boxes_m": box, "radius_m": 0.012}]
    rep = tx.run(tmp_path, tex_profile(color_repaint=cr))
    row = rep["color_repaint"]["rows"][0]
    assert row["matched_texels"] == 32 and row["repainted_texels"] == 32  # the patch only: the stripe is outside the box
    from PIL import Image
    bc = np.asarray(Image.open(tmp_path / "textures" / "T_Synth_H2_BC.png")).astype(int)
    assert np.abs(bc[40:48, 6:10] - bc[10, 6]).max() <= 1  # yellow now
    assert (bc[40:48, 14] == bc[0, 14]).all()  # the black stripe core outside the box keeps its colour


def test_color_repaint_without_source_keeps_the_texel(tmp_path):
    tx = load_local("textures")
    synthetic_run(tmp_path)
    cr = [{"name": "far", "parts": ["tripo_part_0"], "match_hsv": {"v_max": 0.45},
           "keep_hsv": {"s_max": 0.05, "v_min": 0.9}, "radius_m": 0.004}]  # no white texel anywhere: nothing to copy
    rep = tx.run(tmp_path, tex_profile(color_repaint=cr))
    row = rep["color_repaint"]["rows"][0]
    assert row["repainted_texels"] == 0 and row["without_source"] == row["matched_texels"] > 0


@pytest.mark.parametrize("bad, message", [
    ({"radius_m": 0.05}, "radius_m"),
    ({"match_hsv": {}}, "match_hsv"),
    ({"match_hsv": {"hue": [1, 2]}}, "match_hsv"),
    ({"parts": ["tripo_part_9"]}, "parts"),
    ({"keys": ["N"]}, "keys"),
    ({"include_boxes_m": [{"min_m": [0, 0, 0], "max_m": [0, 1, 1]}]}, "include_boxes_m"),
    ({"detail": [1.2, 1.5]}, "detail"),
    ({"surprise": 1}, "unknown key"),
])
def test_color_repaint_validation(tmp_path, bad, message):
    tx = load_local("textures")
    synthetic_run(tmp_path)
    cr = {"name": "x", "parts": ["tripo_part_0"], "match_hsv": {"v_max": 0.45}}
    cr.update(bad)
    with pytest.raises(ValueError, match=message):
        tx.run(tmp_path, tex_profile(color_repaint=[cr]))


def test_roughness_remap_without_metal(tmp_path):
    tx = load_local("textures")
    synthetic_run(tmp_path)
    rr = [{"name": "suit", "parts": ["tripo_part_0"], "lo": 0.78, "hi": 0.92}]
    rep = tx.run(tmp_path, tex_profile(roughness_remap=rr))
    row = rep["roughness_remap"]["rows"][0]
    assert row["texels"] == SIZE * 24 and row["metal_excluded_texels"] == 0
    from PIL import Image
    orm = np.asarray(Image.open(tmp_path / "textures" / "T_Synth_H2_ORM.png")).astype(int)
    g0 = orm[..., 1][:, 4:28] / 255.0
    g1 = orm[..., 1][:, 30] / 255.0  # part 1 keeps the Tripo ramp 0.3 .. 0.6 (PNG rows may run either way)
    assert np.array_equal(orm[..., 1][:, 28:44], np.repeat(orm[:, 28:29, 1], 16, 1))
    assert abs(min(g1[0], g1[-1]) - 0.3) < 0.01 and abs(max(g1[0], g1[-1]) - 0.6) < 0.01
    assert 0.775 <= g0.min() and g0.max() <= 0.925  # into [lo, hi]
    assert (g0[-1, 0] - g0[0, 0]) * (g1[-1] - g1[0]) > 0  # by rank: the same order as the Tripo roughness
    assert rep["metal_mask"]["value"] == 0.0


def test_roughness_remap_skips_metal_and_hsv(tmp_path):
    tx = load_local("textures")
    synthetic_run(tmp_path)
    rr = [{"name": "grey", "parts": ["tripo_part_0", "tripo_part_1"], "lo": 0.7, "hi": 0.8, "hsv": {"s_max": 0.2}}]
    rep = tx.run(tmp_path, tex_profile(materials=copy.deepcopy(METAL), team_mask=copy.deepcopy(METAL_CLOTH),
                                       roughness_remap=rr))
    row = rep["roughness_remap"]["rows"][0]
    assert row["metal_excluded_texels"] > 0  # the metal core of part 1 keeps the metal roughness
    assert rep["checks"]["h21_metal_core_roughness"]["passed"]


@pytest.mark.parametrize("bad, message", [
    ({"lo": 0.9, "hi": 0.8}, "lo"),
    ({"hi": 1.2}, "hi"),
    ({"parts": []}, "parts"),
    ({"hsv": {"hue_deg": [0]}}, "hsv"),
])
def test_roughness_remap_validation(tmp_path, bad, message):
    tx = load_local("textures")
    synthetic_run(tmp_path)
    rr = {"name": "x", "parts": ["tripo_part_0"], "lo": 0.7, "hi": 0.8}
    rr.update(bad)
    with pytest.raises(ValueError, match=message):
        tx.run(tmp_path, tex_profile(roughness_remap=[rr]))
