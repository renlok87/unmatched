"""Opt-in textures.clone_repaint (F15, Dr. Watson model acceptance r2: T 1.0 — a patternless Tripo smear on the coat
behind the bag and under the arm, which band_repaint and color_repaint only average): the selected texels (boxes, optional
match_hsv) copy, texel by texel with k = 1, the value of the nearest unselected texel of the same parts to rest position
+ offset_m or to the mirror across x = mirror_x. Without the key the textures stage writes the same bytes as before (the
sha256 pinned in test_color_repaint_roughness_remap.py before the F12 keys).

Plain Python (numpy, scipy, Pillow), no Blender.
Run: python -m pytest tools/tripo-pipeline/blender/h2_bake/tests -q -k clone_repaint"""

import copy
import importlib.util
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

HERE = Path(__file__).resolve().parent
PKG = HERE.parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CR = load("h2cl_crtest", HERE / "test_color_repaint_roughness_remap.py")  # synthetic atlas, profiles, pinned sha256
SIZE, PITCH = CR.SIZE, CR.PITCH


def textures():
    return load("h2cl_textures", PKG / "textures.py")


def pattern_run(tmp_path):
    """The synthetic atlas of the colour tests with a pattern on part 0 (columns 4..27, x = column * 2 mm, z = row * 2 mm):
    BC rows cycle through four greys (row % 4), columns 4..15 green-tinted, 16..27 red-tinted (so a mirror is visible), and
    a patternless smear (rows 40..47, columns 6..9) of one flat colour."""
    CR.synthetic_run(tmp_path)
    bc = np.load(tmp_path / "work" / "bake" / "BC.npy")
    g = np.repeat((0.25 + 0.15 * (np.arange(SIZE) % 4))[:, None], 12, 1)
    bc[:, 4:16] = np.stack([g * 0.8, g, g * 0.6], -1)
    cols = (np.arange(16, 28) - 15) / 40.0
    bc[:, 16:28] = np.stack([g + cols[None, :], g * 0.7, g * 0.5], -1)
    bc[40:48, 6:10] = (0.5, 0.45, 0.4)
    np.save(tmp_path / "work" / "bake" / "BC.npy", bc.astype(np.float32))
    return bc


def bc_png(tmp_path):
    """BC of the 4K master as written, rows back in the npy order (the stage writes the PNG rows flipped or not: the
    row of every texel is found by matching an untouched column)."""
    return np.asarray(Image.open(tmp_path / "textures" / "T_Synth_H2_BC.png").convert("RGB")).astype(int)


def ref8(bc):
    """8-bit values the stage writes (its own to8)."""
    return textures().to8(bc).astype(int)


def rows_as_npy(png, bc):
    """PNG rows in npy order: the stage may flip; decided on column 20 (never cloned in these tests)."""
    r = ref8(bc)
    if np.array_equal(png[:, 20], r[:, 20]):
        return png
    assert np.array_equal(png[::-1, 20], r[:, 20])
    return png[::-1]


BOX = [{"min_m": [5.5 * PITCH, -1.0, 39.5 * PITCH], "max_m": [9.5 * PITCH, 1.0, 47.5 * PITCH]}]
OFFSET = {"name": "smear", "parts": ["tripo_part_0"], "include_boxes_m": copy.deepcopy(BOX),
          "source": {"offset_m": [0.0, 0.0, -12 * PITCH]}, "max_dist_m": 0.001}


@pytest.mark.parametrize("fixture", sorted(CR.FIXTURES))
def test_without_the_key_the_bytes_are_unchanged(tmp_path, fixture):
    tx = textures()
    CR.synthetic_run(tmp_path)
    rep = tx.run(tmp_path, CR.FIXTURES[fixture]())
    assert rep["passed"] and "clone_repaint" not in rep
    assert CR.outputs_sha(tmp_path) == CR.EXPECTED[fixture]


def test_offset_copies_the_pattern_texel_by_texel(tmp_path):
    tx = textures()
    bc = pattern_run(tmp_path)
    rep = tx.run(tmp_path, CR.tex_profile(clone_repaint=[copy.deepcopy(OFFSET)]))
    row = rep["clone_repaint"]["rows"][0]
    assert row["selected_texels"] == 32 and row["repainted_texels"] == 32 and row["without_source"] == 0
    assert row["distance_mm_p50_max"] == [0.0, 0.0]
    png = rows_as_npy(bc_png(tmp_path), bc)
    r = ref8(bc)
    assert np.array_equal(png[40:48, 6:10], r[28:36, 6:10])  # the rows 12 lower, exactly: k = 1, no averaging
    assert len({tuple(v) for v in png[40:48, 6].tolist()}) == 4  # the four greys of the pattern, not one mean
    assert np.array_equal(png[:, 10:16], r[:, 10:16])  # outside the box untouched


def test_mirror_x_copies_the_other_side(tmp_path):
    tx = textures()
    bc = pattern_run(tmp_path)
    cl = dict(copy.deepcopy(OFFSET), source={"mirror_x": 15.5 * PITCH})  # column c -> 31 - c: 6..9 -> 25..22
    rep = tx.run(tmp_path, CR.tex_profile(clone_repaint=[cl]))
    assert rep["clone_repaint"]["rows"][0]["repainted_texels"] == 32
    png = rows_as_npy(bc_png(tmp_path), bc)
    r = ref8(bc)
    assert np.array_equal(png[40:48, 6:10], r[40:48, 25:21:-1])  # red-tinted columns of the other half, mirrored


def test_source_farther_than_max_dist_keeps_the_texel(tmp_path):
    tx = textures()
    bc = pattern_run(tmp_path)
    cl = dict(copy.deepcopy(OFFSET), source={"offset_m": [0.0, 0.02, 0.0]})  # 2 cm off the plane: no source in reach
    rep = tx.run(tmp_path, CR.tex_profile(clone_repaint=[cl]))
    row = rep["clone_repaint"]["rows"][0]
    assert row["repainted_texels"] == 0 and row["without_source"] == 32 and row["distance_mm_p50_max"] is None
    png = rows_as_npy(bc_png(tmp_path), bc)
    assert np.array_equal(png[40:48, 6:10], ref8(bc)[40:48, 6:10])


def test_selected_texels_are_never_sources(tmp_path):
    tx = textures()
    bc = pattern_run(tmp_path)
    # offset of 2 rows inside an 8-row box: rows 42..47 would land on selected texels; their nearest unselected texel is
    # beyond 1 mm (the box edge rows 38/39 are 4..18 mm away): only rows 40, 41 copy rows 38, 39
    cl = dict(copy.deepcopy(OFFSET), source={"offset_m": [0.0, 0.0, -2 * PITCH]})
    rep = tx.run(tmp_path, CR.tex_profile(clone_repaint=[cl]))
    row = rep["clone_repaint"]["rows"][0]
    assert row["repainted_texels"] == 8 and row["without_source"] == 24
    png = rows_as_npy(bc_png(tmp_path), bc)
    r = ref8(bc)
    assert np.array_equal(png[40:42, 6:10], r[38:40, 6:10]) and np.array_equal(png[42:48, 6:10], r[42:48, 6:10])


def test_match_hsv_limits_the_box(tmp_path):
    tx = textures()
    bc = pattern_run(tmp_path)
    big = [{"min_m": [3.5 * PITCH, -1.0, 37.5 * PITCH], "max_m": [12.5 * PITCH, 1.0, 50.5 * PITCH]}]
    # the smear is brownish (r > g), the pattern of columns 4..15 green-tinted (g > r): hue 20..40 picks the smear only
    cl = dict(copy.deepcopy(OFFSET), include_boxes_m=big, match_hsv={"hue_deg": [20, 40], "s_min": 0.1})
    rep = tx.run(tmp_path, CR.tex_profile(clone_repaint=[cl]))
    row = rep["clone_repaint"]["rows"][0]
    assert row["box_texels"] == 9 * 13 and row["selected_texels"] == 32 and row["repainted_texels"] == 32
    png = rows_as_npy(bc_png(tmp_path), bc)
    r = ref8(bc)
    assert np.array_equal(png[40:48, 6:10], r[28:36, 6:10])
    assert np.array_equal(png[38:40, 4:13], r[38:40, 4:13]) and np.array_equal(png[40:48, 10:13], r[40:48, 10:13])


def test_feather_blends_at_the_box_edge(tmp_path):
    tx = textures()
    bc = pattern_run(tmp_path)
    cl = dict(copy.deepcopy(OFFSET), feather_m=2 * PITCH)  # edge texels 0.5 texel deep: 1/4 of the feather
    rep = tx.run(tmp_path, CR.tex_profile(clone_repaint=[cl]))
    row = rep["clone_repaint"]["rows"][0]
    assert row["repainted_texels"] == 32 and row["feathered_texels"] == 32  # 4 columns: every texel within 2 px of a face
    png = rows_as_npy(bc_png(tmp_path), bc)
    r = ref8(bc)
    f = 0.25 * 0.25 * (3 - 2 * 0.25)  # depth 0.5 texel of 2: smoothstep(0.25)
    expect = np.round((bc[40, 6] * (1 - f) + bc[28, 6] * f) * 255).astype(int)
    assert np.abs(png[40, 6] - expect).max() <= 1
    assert not np.array_equal(png[40, 6], r[28, 6]) and not np.array_equal(png[40, 6], r[40, 6])


def test_runs_after_color_repaint_and_entries_in_order(tmp_path):
    tx = textures()
    bc = pattern_run(tmp_path)
    bc[28:36, 6:10] = (0.04, 0.05, 0.13)  # navy in the clone source: color_repaint must clean it first
    np.save(tmp_path / "work" / "bake" / "BC.npy", bc)
    cr = [{"name": "navy", "parts": ["tripo_part_0"], "match_hsv": {"hue_deg": [190, 270], "s_min": 0.3},
           "keep_hsv": {"hue_deg": [60, 180]}, "radius_m": 0.03, "k": 1}]
    second = dict(copy.deepcopy(OFFSET), name="again", include_boxes_m=[
        {"min_m": [5.5 * PITCH, -1.0, 51.5 * PITCH], "max_m": [9.5 * PITCH, 1.0, 59.5 * PITCH]}])  # copies rows 40..47
    rep = tx.run(tmp_path, CR.tex_profile(color_repaint=cr, clone_repaint=[copy.deepcopy(OFFSET), second]))
    png = rows_as_npy(bc_png(tmp_path), bc)
    h, s, v = tx.rgb_to_hsv(png[40:48, 6:10].astype(np.float32) / 255.0)
    assert not ((h > 190) & (h < 270) & (s > 0.3)).any()  # the clone copied the colour-repaired source
    assert np.array_equal(png[52:60, 6:10], png[40:48, 6:10])  # the second entry copied what the first one cloned
    assert [r["name"] for r in rep["clone_repaint"]["rows"]] == ["smear", "again"]


def cap_run(tmp_path):
    """pattern_run plus a contact cap on part 0 (rows 50..53, columns 6..9; not baked, as caps are): work/uv/cap_ids.npy
    and caps.npz of two triangles whose four corner vertices take one rim sample each (the caps fill paints the square
    flat from the corners)."""
    bc = pattern_run(tmp_path)
    w = tmp_path / "work"
    cap = np.zeros((SIZE, SIZE), np.int64)
    cap[50:54, 6:10] = 1
    np.save(w / "uv" / "cap_ids.npy", cap)
    for k in ("NORMAL", "AO", "BC", "RM", "HIT"):
        a = np.load(w / "bake" / ("%s_alpha.npy" % k))
        a[50:54, 6:10] = False
        np.save(w / "bake" / ("%s_alpha.npy" % k), a)
    corners = np.array([[6.0, 50.0], [10.0, 50.0], [10.0, 54.0], [6.0, 54.0]])
    tri_v = np.array([[0, 1, 2], [0, 2, 3]], np.int64)
    samp = np.array([[5.5, 49.5], [10.5, 49.5], [10.5, 54.5], [5.5, 54.5]])  # rim texel centres just outside
    np.savez(w / "uv" / "caps.npz", tri_px=corners[tri_v], tri_v=tri_v, tri_cap=np.zeros(2, np.int64), samp_px=samp,
             w_rows=np.arange(4), w_cols=np.arange(4), w_vals=np.ones(4), n_vertices=np.array(4))
    return bc


CAP_BOX = [{"min_m": [5.5 * PITCH, -1.0, 49.5 * PITCH], "max_m": [9.5 * PITCH, 1.0, 53.5 * PITCH]}]


def test_caps_true_clones_the_cap_after_the_caps_fill(tmp_path):
    tx = textures()
    bc = cap_run(tmp_path)
    cl = dict(copy.deepcopy(OFFSET), name="cap", include_boxes_m=copy.deepcopy(CAP_BOX), caps=True)
    rep = tx.run(tmp_path, CR.tex_profile(clone_repaint=[cl]))
    main, caps = rep["clone_repaint"]["rows"]
    assert (main["pass"], main["selected_texels"]) == ("main", 0)  # the cap is left out of the first pass
    assert (caps["pass"], caps["selected_texels"], caps["repainted_texels"], caps["without_source"]) == ("caps", 16, 16, 0)
    assert rep["stats"]["caps"]["painted_texels"] == 16
    png = rows_as_npy(bc_png(tmp_path), bc)
    assert np.array_equal(png[50:54, 6:10], ref8(bc)[38:42, 6:10])  # the pattern 12 rows lower, over the flat fill


def test_without_caps_the_cap_keeps_its_rim_fill(tmp_path):
    tx = textures()
    bc = cap_run(tmp_path)
    cl = dict(copy.deepcopy(OFFSET), name="cap", include_boxes_m=copy.deepcopy(CAP_BOX))
    rep = tx.run(tmp_path, CR.tex_profile(clone_repaint=[cl]))
    assert [r["pass"] for r in rep["clone_repaint"]["rows"]] == ["main"]
    assert rep["clone_repaint"]["rows"][0]["selected_texels"] == 0
    png = rows_as_npy(bc_png(tmp_path), bc)
    assert not np.array_equal(png[50:54, 6:10], ref8(bc)[38:42, 6:10])  # the caps fill from the four corners


@pytest.mark.parametrize("bad, message", [
    ({"caps": "yes"}, "caps"),
    ({"include_boxes_m": None}, "include_boxes_m"),
    ({"include_boxes_m": [{"min_m": [0, 0, 0], "max_m": [0, 1, 1]}]}, "include_boxes_m"),
    ({"source": {"offset_m": [0, 0, 0]}}, "offset_m"),
    ({"source": {"offset_m": [0, 0.01]}}, "offset_m"),
    ({"source": {"offset_m": [0, 0, 0.01], "mirror_x": 0}}, "source"),
    ({"source": {"mirror_y": 0.0}}, "source"),
    ({"source": {"mirror_x": "0"}}, "mirror_x"),
    ({"max_dist_m": 0.02}, "max_dist_m"),
    ({"max_dist_m": None}, "max_dist_m"),
    ({"match_hsv": {}}, "match_hsv"),
    ({"keys": ["N"]}, "keys"),
    ({"feather_m": -0.001}, "feather_m"),
    ({"parts": ["tripo_part_9"]}, "parts"),
    ({"k": 4}, "unknown key"),
])
def test_clone_repaint_validation(tmp_path, bad, message):
    tx = textures()
    CR.synthetic_run(tmp_path)
    cl = copy.deepcopy(OFFSET)
    cl.update(bad)
    cl = {k: v for k, v in cl.items() if v is not None}
    with pytest.raises(ValueError, match=message):
        tx.run(tmp_path, CR.tex_profile(clone_repaint=[cl]))
    assert not (tmp_path / "textures").exists()  # validated before any work


def test_clone_repaint_names_unique(tmp_path):
    tx = textures()
    CR.synthetic_run(tmp_path)
    with pytest.raises(ValueError, match="name"):
        tx.run(tmp_path, CR.tex_profile(clone_repaint=[copy.deepcopy(OFFSET), copy.deepcopy(OFFSET)]))
