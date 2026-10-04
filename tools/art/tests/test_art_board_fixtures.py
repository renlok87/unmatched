"""Tests for tools/art/art_board_fixtures.py (stage 3 T3.2 board-art helpers).

Pure-function tests run everywhere; the profile tests read the UE board profiles
(unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json); the original-map tests
need the gitignored scraped-data/api/maps.json of the main checkout and are skipped
(reported) when it is absent. The ART FIXTURE output (backend/prisma/fixtures/art-boards)
is retired since 2026-10-04 (real boards only), and its tests went with it.

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


def grid_board(bid: str = "grid-5x6") -> dict:
    """A grid ('tiles') board entry: the map-image-only blocks must be refused on it (no grid board ships since
    2026-10-04, so the test builds one)."""
    return {"id": bid, "match": {"boardIds": ["c" + "0" * 24], "width": 5, "height": 6, "zoneKeys": ["blue", "red"]},
            "surface": "tiles", "light": "marmoreal-night"}


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


def disk_path(cx: float, cy: float, r: float) -> str:
    """A whole disk as a closed path of four cubic arcs (the shape Sarpedon uses once)."""
    k = 0.5523 * r
    return (f"M{cx + r} {cy}C{cx + r} {cy + k} {cx + k} {cy + r} {cx} {cy + r}"
            f"C{cx - k} {cy + r} {cx - r} {cy + k} {cx - r} {cy}"
            f"C{cx - r} {cy - k} {cx - k} {cy - r} {cx} {cy - r}"
            f"C{cx + k} {cy - r} {cx + r} {cy - k} {cx + r} {cy}Z")


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

    def test_curve_only_path_on_a_circle_is_a_whole_space(self):
        # Sarpedon (yellow) draws one whole space as a closed path of four cubic arcs.
        (x, y), kind = F.path_center(disk_path(766.048, 203.164, 62.697))
        self.assertEqual(kind, "circle")
        self.assertAlmostEqual(x, 766.048, places=3)
        self.assertAlmostEqual(y, 203.164, places=3)

    def test_curve_only_path_off_a_circle_is_refused(self):
        with self.assertRaisesRegex(ValueError, "without a straight segment"):
            F.path_center("M0 0C10 0 20 0 30 0C30 10 30 20 30 30C20 30 10 30 5 12C3 8 1 4 0 0Z")
        with self.assertRaisesRegex(ValueError, "without a straight segment"):
            F.path_center(disk_path(0, 0, 10))  # a circle, but far smaller than a space

    def test_ellipse_is_a_whole_space(self):
        m = mini_map()
        m["zones"][2]["svgGroup"] += '<ellipse cx="700.5" cy="80.25" rx="62.6973" ry="62.7133"/>'
        m["spacesCount"] = 4
        spaces = F.extract_spaces(m)
        self.assertEqual(len(spaces), 4)
        s = next(s for s in spaces if s["px"] == [700.5, 80.25])
        self.assertEqual((s["zones"], s["pieces"]), (["c"], ["circle"]))

    def test_disk_path_is_a_whole_space_in_extract_spaces(self):
        m = mini_map()
        m["zones"][1]["svgGroup"] += f'<path d="{disk_path(900, 400, 62.7)}"/>'
        spaces = F.extract_spaces(m)
        self.assertEqual(len(spaces), 4)
        s = next(s for s in spaces if abs(s["px"][0] - 900) < 1e-6)
        self.assertEqual((s["zones"], s["pieces"]), (["b"], ["circle"]))

    def test_identical_pieces_in_one_zone_count_once(self):
        # Sarpedon (brown) repeats two wedge paths verbatim; that is one piece each.
        m = mini_map()
        m["zones"][2]["svgGroup"] *= 2
        m["zones"][0]["svgGroup"] += '<circle cx="500" cy="200" r="63" fill="#111"/>'
        spaces = F.extract_spaces(m)
        self.assertEqual(sorted(tuple(s["zones"]) for s in spaces), [("a",), ("a", "b"), ("a", "b", "c")])
        self.assertTrue(all(len(s["pieces"]) == len(s["zones"]) for s in spaces))

    def test_same_zone_twice_at_one_space_still_refused(self):
        # a genuinely different second piece of the same zone at one space stays an error
        m = mini_map()
        m["zones"][2]["svgGroup"] += '<path d="M300 150C305 160 318 170 320 171L300 200L280 170C290 160 300 150 300 150Z"/>'
        with self.assertRaisesRegex(ValueError, "duplicate zone piece"):
            F.extract_spaces(m)

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



class ShippedProfiles(unittest.TestCase):
    def test_profiles_valid_and_original_maps_only(self):
        profiles = json.loads(F.DEFAULT_PROFILES.read_text(encoding="utf-8"))
        self.assertEqual(F.check_profiles(profiles), [])
        # 2026-10-04 (real boards only): the two original maps, their night lights, no synthetic board / probe light
        self.assertEqual([b["id"] for b in profiles["boards"]], ["marmoreal-original", "sarpedon-original"])
        self.assertEqual(sorted(profiles["lightProfiles"]), ["marmoreal-night", "sarpedon-night"])
        self.assertTrue(all(b["surface"] == "map-image" for b in profiles["boards"]))
        self.assertEqual(F.main(["check"]), 0)

    def test_move_selection_blocks(self):
        # MS-T-08 (04 §4.7): the root block = the code defaults, the two maps override the plate / path colour; the
        # override is legal on a grid too (not part of "readability"); broken geometry, unknown fields are rejected.
        profiles = json.loads(F.DEFAULT_PROFILES.read_text(encoding="utf-8"))
        root, errs = F.merge_move_selection("root", profiles["moveSelection"], F.MOVE_SELECTION_DEFAULTS)
        self.assertEqual(errs, [])
        self.assertEqual(root, F.MOVE_SELECTION_DEFAULTS)
        for b in profiles["boards"]:
            merged, errs = F.merge_move_selection(b["id"], b["moveSelection"], root)
            self.assertEqual(errs, [])
            self.assertEqual(merged[("plate", "colorSrgb")], "#FFC857")
            self.assertEqual(merged[("path", "colorSrgb")], "#FFC857")
            self.assertEqual(merged[("plate", "ringCenterUU")], 36.0)
        bad = json.loads(json.dumps(profiles))
        bad["boards"].append({"id": "grid", "surface": "tiles", "moveSelection": {"plate": {"colorSrgb": "#4CD2DC"}}})
        self.assertEqual(F.check_profiles(bad), [])
        for block, needle in (({"plate": {"ringWidthUU": 8}}, "must stay in [30, 40]"),
                              ({"plate": {"outlineOuterUU": 42}}, "rim 41.6"),
                              ({"plate": {"colour": "#FFFFFF"}}, "not a known field"),
                              ({"plates": {}}, "not a known block"),
                              ({"boostTier": {"dashCount": 12.5}}, "out of range"),
                              ({"anim": {"easeEnds": "yes"}}, "out of range")):
            with self.subTest(block=block):
                errs = F.merge_move_selection("board x", block, root)[1]
                self.assertTrue(any(needle in e for e in errs), errs)

    def test_profile_budget_rule_detects_violations(self):
        profiles = json.loads(F.DEFAULT_PROFILES.read_text(encoding="utf-8"))
        bad = json.loads(json.dumps(profiles))
        lp = bad["lightProfiles"]["marmoreal-night"]
        lp["points"] = lp["points"] * 9  # 9 points (the night profile has one moon pool)
        lp["points"][0] = dict(lp["points"][0], castShadows=True)
        lp["directional"]["castShadows"] = False
        errs = F.check_profiles(bad)
        self.assertTrue(any("> 6" in e for e in errs))
        self.assertTrue(any("must not cast shadows" in e for e in errs))
        self.assertTrue(any("directional light with a shadow" in e for e in errs))

    def test_profile_render_rules_detect_violations(self):
        # W4-A: units in candelas/lux, SkyLight instead of a point fill, fixed exposure.
        profiles = json.loads(F.DEFAULT_PROFILES.read_text(encoding="utf-8"))
        bad = json.loads(json.dumps(profiles))
        lp = bad["lightProfiles"]["marmoreal-night"]
        del lp["units"]
        lp["sky"]["cubemap"] = "/Engine/MapTemplates/Sky/DaylightAmbientCubemap"
        lp["points"].append({"name": "fill", "role": "fill", "posUU": [0, -100, 550], "intensity": 700,
                             "radiusUU": 1800})
        lp["exposure"]["maxBrightness"] = 4.0
        errs = F.check_render_blocks("marmoreal-night", lp)
        self.assertTrue(any("units must be" in e for e in errs))
        self.assertTrue(any("sky needs" in e for e in errs))
        self.assertTrue(any("'fill' ambient" in e for e in errs))
        self.assertTrue(any("exposure needs" in e for e in errs))
        self.assertEqual(F.check_render_blocks("marmoreal-night", profiles["lightProfiles"]["marmoreal-night"]), [])

    def test_profile_night_blocks(self):
        # ENV-MAPS P2 (rev 9): the shipped night profiles carry a valid fog and map grade; broken ones are reported.
        profiles = json.loads(F.DEFAULT_PROFILES.read_text(encoding="utf-8"))
        for lid in ("marmoreal-night", "sarpedon-night"):
            lp = profiles["lightProfiles"][lid]
            self.assertIn("fog", lp)
            self.assertIn("mapGrade", lp)
            self.assertEqual(F.check_night_blocks(lid, lp), [])
        lp = json.loads(json.dumps(profiles["lightProfiles"]["marmoreal-night"]))
        lp["fog"]["density"] = 0
        lp["fog"]["endDistanceUU"] = lp["fog"]["startDistanceUU"] - 1
        lp["mapGrade"]["lift"] = -1
        lp["mapGrade"]["nightTintLinear"] = [1, 1]
        errs = F.check_render_blocks("marmoreal-night", lp)
        self.assertTrue(any("fog needs" in e for e in errs))
        self.assertTrue(any("mapGrade needs" in e for e in errs))
        del lp["fog"], lp["mapGrade"]
        self.assertEqual(F.check_night_blocks("marmoreal-night", lp), [])

    def test_map_grade_mask_terms(self):
        # ENV-MAPS P4 (rev 10): the night grades carry the M_MapBoard graph-v2 mask terms; bad ones are reported.
        profiles = json.loads(F.DEFAULT_PROFILES.read_text(encoding="utf-8"))
        for lid in ("marmoreal-night", "sarpedon-night"):
            g = profiles["lightProfiles"][lid]["mapGrade"]
            self.assertGreater(g["maskSaturation"], 1.0)
            self.assertGreaterEqual(g["liftSaturation"], 1.0)
            self.assertEqual(len(g["maskInverseTintLinear"]), 3)
        lp = json.loads(json.dumps(profiles["lightProfiles"]["sarpedon-night"]))
        for key, bad in (("maskSaturation", 4), ("liftSaturation", -1), ("maskInverseTintLinear", [1, 1]),
                         ("maskSaturation", True)):
            lp2 = json.loads(json.dumps(lp))
            lp2["mapGrade"][key] = bad
            self.assertTrue(any("mapGrade optional" in e for e in F.check_night_blocks("x", lp2)), (key, bad))
        for key in ("maskSaturation", "liftSaturation", "maskInverseTintLinear"):
            del lp["mapGrade"][key]
        self.assertEqual(F.check_night_blocks("x", lp), [])  # identity when absent

    def test_readability_blocks(self):
        # ENV-MAPS P4: the readability block is on the two map-image boards only and passes the C++ parser rules.
        profiles = json.loads(F.DEFAULT_PROFILES.read_text(encoding="utf-8"))
        with_block = sorted(b["id"] for b in profiles["boards"] if "readability" in b)
        self.assertEqual(with_block, ["marmoreal-original", "sarpedon-original"])
        for b in profiles["boards"]:
            self.assertEqual(F.check_readability_block(b["id"], b), [])
            if "readability" in b:
                r = b["readability"]
                self.assertTrue(r["labelPlates"] and r["leaderPip"])
                self.assertGreaterEqual(r["reach"]["segments"], 48)
                rgb = [int(r["reach"]["colorSrgb"][i:i + 2], 16) for i in (1, 3, 5)]
                self.assertTrue(rgb[0] > rgb[1] > rgb[2], "warm reach colour (not the mint green)")
                self.assertAlmostEqual(r["frameWood"]["valueScaleSrgb"], 0.7, delta=0.1)
        grid = grid_board()
        grid["readability"] = {"labelPlates": True}
        self.assertEqual(F.check_readability_block("grid-5x6", grid),
                         ["board grid-5x6: readability is for map-image boards only"])
        mp = json.loads(json.dumps(next(b for b in profiles["boards"] if b["id"] == "marmoreal-original")))
        cases = (
            (("reach", "segments"), 8, "readability.reach"),
            (("reach", "segments"), 47.5, "readability.reach"),
            (("reach", "colorSrgb"), "gold", "readability.reach"),
            (("contactShadow", "diameterUU"), 500, "readability.contactShadow"),
            (("frameWood", "valueScaleSrgb"), 0.1, "readability.frameWood"),
            (("labelPlates",), "yes", "readability.labelPlates"),
        )
        for path, value, part in cases:
            b = json.loads(json.dumps(mp))
            node = b["readability"]
            for k in path[:-1]:
                node = node[k]
            node[path[-1]] = value
            self.assertTrue(any(part in e for e in F.check_readability_block(b["id"], b)), (path, value))
        b = json.loads(json.dumps(mp))
        b["readability"]["reach"].update(widthUU=6, strokeUU=3)
        self.assertTrue(any("between r 30 and r 40" in e for e in F.check_readability_block(b["id"], b)))

    def test_frame_backdrop_blocks(self):
        # ENV-MAPS P5 track C: mapFrame / backdrop on the two map-image boards only, the C++ parser rules mirrored.
        profiles = json.loads(F.DEFAULT_PROFILES.read_text(encoding="utf-8"))
        self.assertEqual(sorted(b["id"] for b in profiles["boards"] if "mapFrame" in b),
                         ["marmoreal-original", "sarpedon-original"])
        # P5b tune: Sarpedon has no backdrop (Track B's opaque sea ring under the island hid the moon card)
        self.assertEqual(sorted(b["id"] for b in profiles["boards"] if "backdrop" in b), ["marmoreal-original"])
        for b in profiles["boards"]:
            self.assertEqual(F.check_frame_backdrop_blocks(b["id"], b), [], b["id"])
        by_id = {b["id"]: b for b in profiles["boards"]}
        self.assertEqual(len(by_id["marmoreal-original"]["backdrop"]["mist"]), 2)
        grid = grid_board()
        grid["mapFrame"] = {"kit": "frame-002"}
        self.assertEqual(F.check_frame_backdrop_blocks("grid-5x6", grid),
                         ["board grid-5x6: mapFrame is for map-image boards only"])
        mp = by_id["marmoreal-original"]
        cases = (
            (lambda b: b["mapFrame"].update(kit="frame-003"), "mapFrame.kit"),
            (lambda b: b["mapFrame"].update(scale=2), "mapFrame.scale is not a field"),
            (lambda b: b["mapImage"].update(frameUU=30), "needs mapImage.frameUU 24"),
            (lambda b: b["backdrop"]["mist"][0].update(zUU=-100), "backdrop.mist[0]"),
            (lambda b: b["backdrop"]["mist"][1].update(zUU=-450), "closer than 100"),
            (lambda b: b["backdrop"]["mist"][0].update(opacity=0), "backdrop.mist[0]"),
            (lambda b: b["backdrop"]["mist"].append({"zUU": -1500}), "at most 2"),
            (lambda b: b["backdrop"]["moon"].update(depthUU=1500), "moon card reaches above"),
            (lambda b: b["backdrop"]["moon"].update(screenAnchor=[-1.5, 0.8]), "backdrop.moon"),
            (lambda b: b.update(backdrop={}), "at least one mist plane or the moon"),
        )
        for patch, part in cases:
            b = json.loads(json.dumps(mp))
            patch(b)
            errs = F.check_frame_backdrop_blocks(b["id"], b)
            self.assertTrue(any(part in e for e in errs), (part, errs))

    def test_profile_content_rules_detect_violations(self):
        # T4.2: zone MI per style (and fallback), one /Game/ glyph mesh per known glyph, every used glyph covered.
        profiles = json.loads(F.DEFAULT_PROFILES.read_text(encoding="utf-8"))
        self.assertEqual(F.check_content_blocks(profiles), [])
        bad = json.loads(json.dumps(profiles))
        del bad["zoneStyles"]["green"]["materialInstance"]
        bad["fallbackZoneStyle"]["materialInstance"] = "/Engine/X"
        bad["glyphMeshes"]["star"] = "/Game/X/SM_Star"
        bad["glyphMeshes"]["ring"] = "SM_Ring"
        del bad["glyphMeshes"]["cross"]
        errs = F.check_content_blocks(bad)
        self.assertTrue(any("zone style green: materialInstance" in e for e in errs))
        self.assertTrue(any("zone style (fallback): materialInstance" in e for e in errs))
        self.assertTrue(any("unknown glyph 'star'" in e for e in errs))
        self.assertTrue(any("glyphMeshes ring" in e for e in errs))
        self.assertTrue(any("glyph 'cross' has no glyph mesh" in e for e in errs))


EVIDENCE = F.REPO / "docs" / "game-design" / "evidence" / "ENV-MAPS" / "2026-09-30-research"


class OriginalMapsFromMapsJson(unittest.TestCase):
    """Battle of Legends Vol. 1 maps (ENV-MAPS): both extract from the zone SVG and agree with
    the committed research numbers. Needs the gitignored maps.json; skipped without it."""

    EXPECT = {"marmoreal": (31, 8, 21, 7, (7, 6)), "sarpedon": (38, 6, 4, 2, (9, 6))}

    @classmethod
    def setUpClass(cls):
        if not F.MAIN_CHECKOUT_MAPS.is_file():
            raise unittest.SkipTest(f"maps.json not present at {F.MAIN_CHECKOUT_MAPS} (gitignored, main checkout only)")
        maps, _ = F.load_maps(F.MAIN_CHECKOUT_MAPS)
        cls.maps = {m["key"]: m for m in maps}

    def test_spaces_zones_and_multizone_counts(self):
        for key, (n, zones, multi, triple, _) in self.EXPECT.items():
            m = self.maps[key]
            with self.subTest(key):
                spaces = F.extract_spaces(m)
                self.assertEqual(len(spaces), n)
                self.assertEqual(m["spacesCount"], n)
                self.assertEqual(len(m["zones"]), zones)
                self.assertEqual(sum(len(s["zones"]) > 1 for s in spaces), multi)
                self.assertEqual(sum(len(s["zones"]) > 2 for s in spaces), triple)

    def test_sarpedon_shapes(self):
        spaces = F.extract_spaces(self.maps["sarpedon"])
        # the curve-only yellow disk path is a single-zone space at its centre
        disk = next(s for s in spaces if abs(s["px"][0] - 766.048) < 0.01)
        self.assertEqual((disk["zones"], disk["pieces"]), (["yellow"], ["circle"]))
        # the brown wedges drawn twice are single pieces of the two triple-zone spaces
        triples = [s for s in spaces if len(s["zones"]) == 3]
        self.assertEqual(len(triples), 2)
        for s in triples:
            self.assertEqual(sorted(s["zones"]), ["brown", "purple", "yellow"])
            self.assertEqual(s["pieces"], ["wedge"] * 3)
        # all 11 ellipses (8 green + 3 yellow) are whole spaces
        green = [s for s in spaces if s["zones"] == ["green"]]
        self.assertEqual(len(green), 8)

    def test_centres_and_zones_match_the_research(self):
        import math
        for key in self.EXPECT:
            ev = json.loads((EVIDENCE / f"{key}.topology.json").read_text(encoding="utf-8"))
            spaces = F.extract_spaces(self.maps[key])
            with self.subTest(key):
                for e in ev["spaces"]:
                    s = min(spaces, key=lambda s: math.dist(s["px"], e["px"]))
                    self.assertLess(math.dist(s["px"], e["px"]), 0.5, e["id"])
                    self.assertEqual(sorted(s["zones"]), sorted(e["zones"]), e["id"])

    def test_grid_choice(self):
        for key, (*_, grid) in self.EXPECT.items():
            with self.subTest(key):
                g, _ = F.choose_grid(F.extract_spaces(self.maps[key]))
                self.assertEqual((g["width"], g["height"]), grid)

    def test_every_other_map_extracts(self):
        for key, m in self.maps.items():
            with self.subTest(key):
                self.assertEqual(len(F.extract_spaces(m)), m["spacesCount"])


if __name__ == "__main__":
    unittest.main()
