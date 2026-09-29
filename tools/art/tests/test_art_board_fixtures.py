"""Tests for tools/art/art_board_fixtures.py (stage 3 T3.2 art-board fixtures).

Pure-function tests run everywhere; the committed-fixture tests read
backend/prisma/fixtures/art-boards/*.art-fixture.json and the UE board profiles;
the reproducibility test additionally needs the gitignored scraped-data/api/maps.json
of the main checkout and is skipped (reported) when it is absent.

  python -m unittest discover -s tools/art/tests -v
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import art_board_fixtures as F  # noqa: E402

FIXTURES = sorted(F.DEFAULT_OUT.glob("*.art-fixture.json"))


def load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def mini_map() -> dict:
    """A 3-space map: one single-zone circle, one half/half two-zone space and one
    three-wedge space (the shapes maps.json uses)."""
    half_a = '<path d="M100 200C90 190 90 170 100 160L100 240C90 230 90 210 100 200Z" fill="#111"/>'
    half_b = '<path d="M100 200C110 190 110 170 100 160L100 240C110 230 110 210 100 200Z" fill="#222"/>'
    wedge = '<path d="M300 150C310 160 320 170 320 170L300 200L280 170C290 160 300 150 300 150Z" fill="#{c}"/>'
    return {
        "key": "mini", "name": "Mini", "spacesCount": 3, "zonesCount": 3,
        "zones": [
            {"key": "a", "color": "#111", "svgGroup": '<circle cx="500" cy="200" r="63" fill="#111"/>' + half_a
             + wedge.format(c="111")},
            {"key": "b", "color": "#222", "svgGroup": half_b + wedge.format(c="222")},
            {"key": "c", "color": "#333", "svgGroup": wedge.format(c="333")},
        ],
    }


class PurePieces(unittest.TestCase):
    def test_half_disk_centre_is_diameter_midpoint(self):
        (x, y), kind = F.path_center("M100 160C90 190 90 170 100 160L100 240C90 230 90 210 100 200Z")
        self.assertEqual(kind, "half")
        self.assertAlmostEqual(x, 100.0)
        self.assertAlmostEqual(y, 200.0)

    def test_wedge_centre_is_vertex_between_straight_segments(self):
        (x, y), kind = F.path_center("M822.107 399.396C826.746 404.052 831.974 412.842 831.974 412.842"
                                     "L778.168 443.382L724.458 412.253C724.458 412.253 727.541 402.204 822.107 399.396Z")
        self.assertEqual(kind, "wedge")
        self.assertAlmostEqual(x, 778.168)
        self.assertAlmostEqual(y, 443.382)

    def test_path_without_straight_segment_is_refused(self):
        with self.assertRaises(ValueError):
            F.path_center("M0 0C1 1 2 2 3 3Z")

    def test_extract_spaces_keeps_every_zone_of_a_multizone_space(self):
        spaces = F.extract_spaces(mini_map())
        self.assertEqual(len(spaces), 3)
        zones = sorted(tuple(s["zones"]) for s in spaces)
        self.assertEqual(zones, [("a",), ("a", "b"), ("a", "b", "c")])

    def test_devalue_decoding(self):
        doc = {"nodes": [{}, None, {"data": [{"maps": 1}, [2], {"key": 3, "name": 4, "zones": 5}, "k", "N", []]}]}
        maps = F.decode_devalue_maps(doc)
        self.assertEqual(maps, [{"key": "k", "name": "N", "zones": []}])

    def test_devalue_rejects_other_payloads(self):
        with self.assertRaises(ValueError):
            F.decode_devalue_maps({"nodes": [{}]})

    def test_hungarian_is_optimal_on_a_small_case(self):
        cost = [[4, 1, 3], [2, 0, 5], [3, 2, 2]]
        cols = F.hungarian(cost)
        self.assertEqual(sorted(cols), [0, 1, 2])
        self.assertEqual(sum(cost[r][c] for r, c in enumerate(cols)), 5)

    def test_hungarian_rectangular(self):
        cols = F.hungarian([[5, 1, 9, 9], [1, 5, 9, 9]])
        self.assertEqual(cols, [1, 0])

    def test_connected4(self):
        self.assertTrue(F.connected4({(0, 0), (1, 0), (1, 1)}))
        self.assertFalse(F.connected4({(0, 0), (1, 1)}))

    def test_board_id_is_deterministic_and_cuid_shaped(self):
        a = F.fixture_board_id("sherwood-forest")
        self.assertEqual(a, F.fixture_board_id("sherwood-forest"))
        self.assertRegex(a, F.ID_RE)
        self.assertNotEqual(a, F.fixture_board_id("t-rex-paddock"))
        self.assertNotEqual(a, F.fixture_board_id("sherwood-forest", 2))

    def test_int019_cell_world(self):
        self.assertEqual(F.cell_world(0, 0, 5, 6), (-200.0, -250.0))
        self.assertEqual(F.cell_world(4, 5, 5, 6), (200.0, 250.0))


class CommittedFixtures(unittest.TestCase):
    def test_two_fixtures_exist(self):
        self.assertEqual([p.name for p in FIXTURES],
                         ["sherwood-forest.art-fixture.json", "t-rex-paddock.art-fixture.json"])

    def test_each_fixture_passes_its_invariants(self):
        for p in FIXTURES:
            with self.subTest(p.name):
                self.assertEqual(F.check_fixture(load(p)), [])

    def test_art_fixture_mark_and_image_hash_only(self):
        for p in FIXTURES:
            fx = load(p)
            with self.subTest(p.name):
                self.assertTrue(fx["artFixture"])
                self.assertEqual(fx["label"], "art fixture, не правила")
                img = fx["source"]["image"]
                self.assertRegex(img["sha256"], r"^[0-9a-f]{64}$")
                self.assertNotIn("url", json.dumps(img).lower())

    def test_multizone_cells_keep_all_zones(self):
        for p in FIXTURES:
            fx = load(p)
            with self.subTest(p.name):
                by_cell = {tuple(s["cell"]): s["zones"] for s in fx["spaces"]}
                for c in fx["cells"]:
                    if c.get("zones"):
                        self.assertEqual(c["zones"], by_cell[(c["x"], c["y"])])
                self.assertGreaterEqual(fx["summary"]["multizoneCells"], 2)

    def test_real_zone_keys_are_the_map_keys(self):
        expected = {
            "sherwood-forest": ["gray", "light-gray", "green", "brown", "light-green", "orange", "yellow"],
            "t-rex-paddock": ["blue", "gray", "green", "blue-green", "purple", "yellow"],
        }
        for p in FIXTURES:
            fx = load(p)
            self.assertEqual(fx["source"]["zoneKeys"], expected[fx["key"]])

    def test_profiles_consistent(self):
        profiles = json.loads(F.DEFAULT_PROFILES.read_text(encoding="utf-8"))
        self.assertEqual(F.check_profiles([load(p) for p in FIXTURES], profiles), [])

    def test_profile_budget_rule_detects_violations(self):
        profiles = json.loads(F.DEFAULT_PROFILES.read_text(encoding="utf-8"))
        bad = json.loads(json.dumps(profiles))
        lp = bad["lightProfiles"]["forest-probe"]
        lp["points"] = lp["points"] * 3  # 9 points (W4-A: the forest profile has 3 points, the fill became the sky)
        lp["points"][0] = dict(lp["points"][0], castShadows=True)
        lp["directional"]["castShadows"] = False
        errs = F.check_profiles([load(p) for p in FIXTURES], bad)
        self.assertTrue(any("> 6" in e for e in errs))
        self.assertTrue(any("must not cast shadows" in e for e in errs))
        self.assertTrue(any("directional light with a shadow" in e for e in errs))

    def test_profile_render_rules_detect_violations(self):
        # W4-A: units in candelas/lux, SkyLight instead of a point fill, fixed exposure.
        profiles = json.loads(F.DEFAULT_PROFILES.read_text(encoding="utf-8"))
        bad = json.loads(json.dumps(profiles))
        lp = bad["lightProfiles"]["cobble-probe"]
        del lp["units"]
        lp["sky"]["cubemap"] = "/Engine/MapTemplates/Sky/DaylightAmbientCubemap"
        lp["points"].append({"name": "fill", "role": "fill", "posUU": [0, -100, 550], "intensity": 700,
                             "radiusUU": 1800})
        lp["exposure"]["maxBrightness"] = 4.0
        errs = F.check_render_blocks("cobble-probe", lp)
        self.assertTrue(any("units must be" in e for e in errs))
        self.assertTrue(any("sky needs" in e for e in errs))
        self.assertTrue(any("'fill' ambient" in e for e in errs))
        self.assertTrue(any("exposure needs" in e for e in errs))
        self.assertEqual(F.check_render_blocks("cobble-probe", profiles["lightProfiles"]["cobble-probe"]), [])

    def test_light_section_on_a_zone_is_rejected(self):
        fx = load(F.DEFAULT_OUT / "t-rex-paddock.art-fixture.json")
        # a warm spot centred on the blue column (x=0) covers exactly blue cells
        r = F.light_sections_vs_zones(fx, {"points": [
            {"name": "on-blue", "role": "warm", "at": [-3.0 / 7.0, 0.0, 250], "radiusUU": 420}]})
        self.assertGreaterEqual(r["on-blue"]["maxJaccard"], 0.5)
        self.assertEqual(r["on-blue"]["zone"], "blue")

    def test_reproducible_from_maps_json(self):
        maps_path = F.MAIN_CHECKOUT_MAPS
        if not maps_path.is_file():
            self.skipTest(f"maps.json not present at {maps_path} (gitignored, main checkout only)")
        maps, sha = F.load_maps(maps_path)
        for p in FIXTURES:
            fx = load(p)
            m = next(x for x in maps if x["key"] == fx["key"])
            with self.subTest(p.name):
                self.assertEqual(F.dump(F.build_fixture(m, sha)), p.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
