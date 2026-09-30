"""Tests for tools/art/board_topology.py (ENV-MAPS track D: original-map topology fixtures).

Pure tests and the committed-fixture tests (backend/prisma/fixtures/boards/*.topology.json
against the committed research evidence) run everywhere; the rebuild tests additionally need
the gitignored scraped-data/api/maps.json of the main checkout and skip cleanly without it.

  python -m pytest tools/art/tests/test_board_topology.py -q
"""
from __future__ import annotations

import copy
import json
import math
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import art_board_fixtures as ABF  # noqa: E402
import board_topology as T  # noqa: E402

FIXTURE_FILES = {k: T.DEFAULT_OUT / f"{k}.topology.json" for k in T.MAPS}


def load(key: str) -> dict:
    return json.loads(FIXTURE_FILES[key].read_text(encoding="utf-8"))


def evidence(key: str) -> tuple[dict, dict]:
    return T.load_evidence(T.DEFAULT_EVIDENCE, key)


def maps_or_skip(test: unittest.TestCase):
    if not T.MAIN_CHECKOUT_MAPS.is_file():
        test.skipTest(f"maps.json not present at {T.MAIN_CHECKOUT_MAPS} (gitignored, main checkout only)")
    return ABF.load_maps(T.MAIN_CHECKOUT_MAPS)


def drop_edge(fx: dict, a: str, b: str) -> None:
    """Remove edge a-b consistently from edges, spaces and cells (a valid-looking mutation)."""
    a, b = T.edge_key(a, b)
    fx["edges"] = [e for e in fx["edges"] if tuple(e) != (a, b)]
    sp = {s["id"]: s for s in fx["spaces"]}
    sp[a]["links"].remove(b)
    sp[b]["links"].remove(a)
    for sid, other in ((a, b), (b, a)):
        o = sp[other]
        cell = next(c for c in fx["cells"] if c.get("spaceId") == sid)
        cell["links"] = [p for p in cell["links"] if (p["x"], p["y"]) != (o["x"], o["y"])]


class Pure(unittest.TestCase):
    def test_board_id_deterministic_cuid_shaped_and_own_namespace(self):
        a = T.topology_board_id("marmoreal")
        self.assertEqual(a, T.topology_board_id("marmoreal"))
        self.assertRegex(a, T.ID_RE)
        self.assertNotEqual(a, T.topology_board_id("sarpedon"))
        self.assertNotEqual(a, T.topology_board_id("marmoreal", 2))
        # cannot collide with the art-fixture ids of the same key
        self.assertNotEqual(a, ABF.fixture_board_id("marmoreal"))

    def test_segments_cross(self):
        self.assertTrue(T.segments_cross((0, 0), (2, 2), (0, 2), (2, 0)))
        self.assertFalse(T.segments_cross((0, 0), (1, 1), (2, 0), (3, 1)))
        self.assertFalse(T.segments_cross((0, 0), (2, 2), (2, 2), (3, 0)))  # shared end point

    def test_chord_crossings_ignore_edges_sharing_a_space(self):
        centres = {"A": (0, 0), "B": (2, 2), "C": (0, 2), "D": (2, 0)}
        self.assertEqual(T.chord_crossings(centres, [["A", "B"], ["C", "D"], ["A", "C"]]),
                         [[["A", "B"], ["C", "D"]]])

    def test_lattice_neighbour_stats(self):
        spaces = [{"id": "A", "x": 0, "y": 0}, {"id": "B", "x": 1, "y": 0}, {"id": "C", "x": 0, "y": 1},
                  {"id": "D", "x": 3, "y": 3}]
        st = T.lattice_neighbour_stats(spaces, [["A", "B"], ["C", "D"]])
        self.assertEqual(st["latticeNeighbourPairs"], 2)
        self.assertEqual(st["latticeNeighbourPairsLinked"], 1)
        self.assertEqual(st["latticeNeighboursNotLinked"], [["A", "C"]])
        self.assertEqual(st["linksBetweenNonLatticeNeighbours"], 1)

    def test_dump_is_valid_lf_json(self):
        doc = {"a": [1, 2], "b": {"c": [["x", "y"]], "d": {}}, "cells": [{"x": 0}, {"x": 1}], "s": "ё"}
        text = T.dump(doc)
        self.assertEqual(json.loads(text), doc)
        self.assertNotIn("\r", text)
        self.assertTrue(text.endswith("}\n"))

    def test_votes_must_be_unanimous(self):
        topo, votes = evidence("marmoreal")
        self.assertEqual(T.check_votes("marmoreal", topo, votes)["edgesUnanimous"], "42/42")
        bad = copy.deepcopy(votes)
        bad["votes"]["M22-M29"] = ["passA", "passB"]
        with self.assertRaisesRegex(ValueError, "not unanimous"):
            T.check_votes("marmoreal", topo, bad)
        bad = copy.deepcopy(votes)
        bad["starts"]["2"]["passC"] = "M30"
        with self.assertRaisesRegex(ValueError, "start"):
            T.check_votes("marmoreal", topo, bad)
        bad = copy.deepcopy(votes)
        del bad["votes"]["M01-M02"]
        with self.assertRaisesRegex(ValueError, "edges"):
            T.check_votes("marmoreal", topo, bad)

    def test_votes_sarpedon(self):
        topo, votes = evidence("sarpedon")
        c = T.check_votes("sarpedon", topo, votes)
        self.assertEqual((c["edgesUnanimous"], c["startsUnanimous"]), ("61/61", "4/4"))


class CommittedFixtures(unittest.TestCase):
    def test_both_fixtures_exist(self):
        self.assertEqual(sorted(p.name for p in T.DEFAULT_OUT.glob("*.topology.json")),
                         ["marmoreal.topology.json", "sarpedon.topology.json"])

    def test_validate_and_evidence_pass(self):
        for key in T.MAPS:
            with self.subTest(key):
                fx = load(key)
                self.assertEqual(T.validate_fixture(fx), [])
                self.assertEqual(T.validate_against_evidence(fx, evidence(key)[0]), [])

    def test_bytes_are_the_canonical_dump(self):
        # the committed bytes are LF and exactly dump(content): `check` can compare byte-for-byte
        for key in T.MAPS:
            with self.subTest(key):
                raw = FIXTURE_FILES[key].read_bytes()
                self.assertNotIn(b"\r", raw)
                self.assertEqual(T.dump(json.loads(raw.decode("utf-8"))).encode("utf-8"), raw)

    def test_counts_lattice_and_ids(self):
        want = {"marmoreal": (31, 42, 7, 6, "c121b47f8d6eb28daccb76d05"),
                "sarpedon": (38, 61, 9, 6, "c7fa64a26c29a0835f2383e63")}
        for key, (n, e, w, h, board_id) in want.items():
            fx = load(key)
            with self.subTest(key):
                self.assertEqual(len(fx["spaces"]), n)
                self.assertEqual(len(fx["edges"]), e)
                self.assertEqual((fx["lattice"]["width"], fx["lattice"]["height"]), (w, h))
                self.assertEqual(len(fx["cells"]), w * h)
                self.assertEqual(sum(1 for c in fx["cells"] if c.get("isObstacle")), w * h - n)
                self.assertEqual(fx["boardId"], board_id)
                self.assertEqual(fx["set"], "battle-of-legends-volume-one")
                self.assertEqual(fx["uuPerPx"], 0.6666667)
                self.assertEqual(fx["spaceRadiusPx"], 63)
                self.assertEqual(fx["source"]["size"], [1337, 866])

    def test_links_symmetric_edges_consistent_graph_connected(self):
        for key in T.MAPS:
            fx = load(key)
            with self.subTest(key):
                sp = {s["id"]: s for s in fx["spaces"]}
                for a, s in sp.items():
                    for b in s["links"]:
                        self.assertIn(a, sp[b]["links"])
                self.assertEqual({T.edge_key(a, b) for a, s in sp.items() for b in s["links"]},
                                 {tuple(e) for e in fx["edges"]})
                adj = {a: set(s["links"]) for a, s in sp.items()}
                self.assertTrue(T.graph_connected(sorted(sp), adj))
                # cell links are the lattice positions of the edge partners
                pos = {a: (s["x"], s["y"]) for a, s in sp.items()}
                for c in fx["cells"]:
                    if c.get("spaceId"):
                        self.assertEqual({(p["x"], p["y"]) for p in c["links"]},
                                         {pos[b] for b in sp[c["spaceId"]]["links"]})

    def test_every_lattice_position_once_holes_are_bare_obstacles(self):
        for key in T.MAPS:
            fx = load(key)
            with self.subTest(key):
                w, h = fx["lattice"]["width"], fx["lattice"]["height"]
                xy = [(c["x"], c["y"]) for c in fx["cells"]]
                self.assertEqual(sorted(xy), sorted((x, y) for y in range(h) for x in range(w)))
                self.assertEqual(len(set(xy)), len(xy))
                for c in fx["cells"]:
                    if "spaceId" not in c:
                        self.assertEqual(c, {"x": c["x"], "y": c["y"], "isObstacle": True})
                    else:
                        self.assertNotIn("isObstacle", c)
                        self.assertTrue(c["links"])

    def test_starts(self):
        for key in T.MAPS:
            fx = load(key)
            with self.subTest(key):
                got = {c["start"]: c["spaceId"] for c in fx["cells"] if "start" in c}
                self.assertEqual(got, T.MAPS[key]["starts"])
        self.assertEqual(T.MAPS["marmoreal"]["starts"], {1: "M13", 2: "M31", 3: "M03", 4: "M11"})
        self.assertEqual(T.MAPS["sarpedon"]["starts"], {1: "S20", 2: "S32", 3: "S03", 4: "S14"})

    def test_marmoreal_violet_and_purple_are_different_zones(self):
        fx = load("marmoreal")
        colours = {z["key"]: z["color"] for z in fx["zones"]}
        self.assertIn("violet", colours)
        self.assertIn("purple", colours)
        self.assertNotEqual(colours["violet"], colours["purple"])
        sp = {s["id"]: s for s in fx["spaces"]}
        self.assertEqual(sp["M16"]["zones"], ["blue", "violet"])
        self.assertEqual(sp["M17"]["zones"], ["green", "blue", "purple"])
        self.assertEqual(sp["M31"]["zones"], ["violet", "brown"])
        self.assertEqual(fx["summary"]["zoneSpaceCounts"]["violet"], 4)
        self.assertEqual(fx["summary"]["zoneSpaceCounts"]["purple"], 5)
        self.assertFalse(set(sp["M16"]["zones"]) & set(sp["M17"]["zones"]) - {"blue"})

    def test_marmoreal_bridge_crossings_have_no_junction(self):
        fx = load("marmoreal")
        self.assertEqual(fx["crossings"], [{"edges": [["M22", "M29"], ["M25", "M26"]], "junction": False},
                                           {"edges": [["M22", "M30"], ["M25", "M26"]], "junction": False}])
        sp = {s["id"]: s for s in fx["spaces"]}
        for e in (["M22", "M29"], ["M22", "M30"], ["M25", "M26"]):
            self.assertIn(e, fx["edges"])
        # the crossing points are not spaces: no centre within a space radius of them
        c = {k: (v["layout"]["x"], v["layout"]["y"]) for k, v in sp.items()}
        for (a, b), (p, q) in ((("M22", "M29"), ("M25", "M26")), (("M22", "M30"), ("M25", "M26"))):
            (x1, y1), (x2, y2), (x3, y3), (x4, y4) = c[a], c[b], c[p], c[q]
            den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
            t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
            ix, iy = x1 + t * (x2 - x1), y1 + t * (y2 - y1)
            self.assertTrue(all(math.dist((ix, iy), cc) > T.SPACE_RADIUS_PX for cc in c.values()))
        # and no edge joins the crossing edges' ends across the bridge
        self.assertNotIn("M29", sp["M25"]["links"])
        self.assertNotIn("M30", sp["M26"]["links"])
        self.assertEqual(load("sarpedon")["crossings"], [])

    def test_lattice_neighbours_without_link_exist_and_research_non_edges_absent(self):
        want = {"marmoreal": 14, "sarpedon": 5}
        close_non_edges = {  # research README "близкие пары без связи"
            "marmoreal": ["M26-M31", "M25-M29", "M15-M17", "M26-M30", "M15-M18", "M25-M28", "M14-M21"],
            "sarpedon": ["S19-S29", "S32-S35"],
        }
        for key in T.MAPS:
            fx = load(key)
            with self.subTest(key):
                s = fx["summary"]
                self.assertEqual(s["latticeNeighbourPairsNotLinked"], want[key])
                self.assertEqual(len(s["latticeNeighboursNotLinked"]), want[key])
                edges = {tuple(e) for e in fx["edges"]}
                for a, b in s["latticeNeighboursNotLinked"]:
                    self.assertNotIn((a, b), edges)
                for pair in close_non_edges[key]:
                    self.assertNotIn(tuple(pair.split("-")), edges)
                self.assertGreater(s["linksBetweenNonLatticeNeighbours"], 0)

    def test_matches_research_checks(self):
        checks = json.loads((T.DEFAULT_EVIDENCE / "checks.json").read_text(encoding="utf-8"))
        for key in T.MAPS:
            fx = load(key)
            with self.subTest(key):
                self.assertEqual(fx["summary"]["degreeHistogram"], checks[key]["degree_hist"])
                self.assertEqual(fx["summary"]["edgesWithoutSharedZone"], checks[key]["n_nozone"])
                self.assertEqual(len(fx["edges"]), checks[key]["edges"])
        self.assertEqual(load("marmoreal")["summary"]["multizoneSpaces"], 21)
        self.assertEqual(load("sarpedon")["summary"]["multizoneSpaces"], 4)

    def test_no_svg_image_or_url_data(self):
        for key in T.MAPS:
            text = FIXTURE_FILES[key].read_text(encoding="utf-8")
            with self.subTest(key):
                for bad in ("<", "http", "data:", "base64", "svgGroup", "supabase"):
                    self.assertNotIn(bad, text)
                self.assertLess(len(text), 64_000)


class ValidatorCatchesMutations(unittest.TestCase):
    def assertFails(self, fx: dict, fragment: str):
        errs = T.validate_fixture(fx)
        self.assertTrue(any(fragment in e for e in errs), f"{fragment!r} not in {errs}")

    def test_asymmetric_link(self):
        fx = load("marmoreal")
        next(s for s in fx["spaces"] if s["id"] == "M01")["links"].remove("M02")
        self.assertFails(fx, "asymmetric link M02->M01")

    def test_link_on_obstacle_cell(self):
        fx = load("marmoreal")
        hole = next(c for c in fx["cells"] if c.get("isObstacle"))
        hole["links"] = [{"x": 0, "y": 0}]
        self.assertFails(fx, "isObstacle: true")

    def test_hole_filled_as_normal_cell(self):
        fx = load("sarpedon")
        hole = next(c for c in fx["cells"] if c.get("isObstacle"))
        del hole["isObstacle"]
        self.assertFails(fx, "non-space cell")

    def test_missing_or_duplicate_cell(self):
        fx = load("sarpedon")
        fx["cells"].pop()
        self.assertFails(fx, "W x H lattice")
        fx = load("sarpedon")
        fx["cells"][1] = dict(fx["cells"][0])
        self.assertFails(fx, "W x H lattice")

    def test_unknown_zone_and_merged_violet_purple(self):
        fx = load("marmoreal")
        next(s for s in fx["spaces"] if s["id"] == "M16")["zones"] = ["blue", "lilac"]
        self.assertFails(fx, "not map zone keys")
        fx = load("marmoreal")
        for z in fx["zones"]:
            if z["key"] == "violet":
                z["key"] = "purple"
        self.assertFails(fx, "duplicate zone key")

    def test_duplicate_or_wrong_start(self):
        fx = load("marmoreal")
        next(s for s in fx["spaces"] if s["id"] == "M03")["start"] = 1
        self.assertFails(fx, "start 1 on")
        fx = load("sarpedon")
        next(s for s in fx["spaces"] if s["id"] == "S14")["start"] = 5
        self.assertFails(fx, "not in 1..4")

    def test_edge_to_unknown_space_and_wrong_count(self):
        fx = load("marmoreal")
        fx["edges"].append(["M01", "M99"])
        self.assertFails(fx, "endpoints not two spaces")
        fx = load("marmoreal")
        drop_edge(fx, "M22", "M29")
        self.assertFails(fx, "41 edges != 42")

    def test_disconnected_graph(self):
        fx = load("sarpedon")
        drop_edge(fx, "S13", "S16")  # the two gangplanks are the only island-ship links
        drop_edge(fx, "S31", "S35")
        self.assertFails(fx, "not connected")

    def test_all_links_removed_means_no_topology(self):
        fx = load("sarpedon")
        for c in fx["cells"]:
            c.pop("links", None)
        self.assertFails(fx, "no cell carries links")

    def test_board_id_summary_and_embedded_data(self):
        fx = load("marmoreal")
        fx["boardId"] = ABF.fixture_board_id("marmoreal")
        self.assertFails(fx, "boardId")
        fx = load("marmoreal")
        fx["summary"]["latticeNeighbourPairsNotLinked"] = 0
        self.assertFails(fx, "summary.latticeNeighbourPairsNotLinked")
        fx = load("marmoreal")
        fx["source"]["provenance"]["svg"] = '<path d="M0 0L1 1Z"/>'
        self.assertFails(fx, "embedded SVG")

    def test_lattice_not_reproducible_from_layout(self):
        fx = load("marmoreal")
        a = next(s for s in fx["spaces"] if s["id"] == "M01")
        b = next(s for s in fx["spaces"] if s["id"] == "M02")
        a["layout"], b["layout"] = b["layout"], a["layout"]
        for c in fx["cells"]:
            if c.get("spaceId") in ("M01", "M02"):
                c["layout"] = next(s for s in fx["spaces"] if s["id"] == c["spaceId"])["layout"]
        self.assertFails(fx, "choose_grid")

    def test_evidence_mismatch(self):
        fx = load("sarpedon")
        next(s for s in fx["spaces"] if s["id"] == "S01")["zones"] = ["blue"]
        errs = T.validate_against_evidence(fx, evidence("sarpedon")[0])
        self.assertTrue(any("S01: zones" in e for e in errs))


class RebuildFromMapsJson(unittest.TestCase):
    def test_check_is_byte_identical(self):
        maps_or_skip(self)
        built = T.build_all(T.MAIN_CHECKOUT_MAPS, T.DEFAULT_EVIDENCE, list(T.MAPS))
        for key, fx in built.items():
            with self.subTest(key):
                self.assertEqual(T.dump(fx).encode("utf-8"), FIXTURE_FILES[key].read_bytes())

    def test_svg_crosscheck_detects_zone_and_centre_drift(self):
        maps, _ = maps_or_skip(self)
        m = next(x for x in maps if x["key"] == "sarpedon")
        topo, _ = evidence("sarpedon")
        self.assertEqual(T.svg_crosscheck("sarpedon", m, topo)["zonesEqual"], "38/38")
        bad = copy.deepcopy(topo)
        bad["spaces"][0]["zones"] = ["blue"]
        with self.assertRaisesRegex(ValueError, "zones"):
            T.svg_crosscheck("sarpedon", m, bad)
        bad = copy.deepcopy(topo)
        bad["spaces"][0]["px"] = [bad["spaces"][0]["px"][0] + 2.0, bad["spaces"][0]["px"][1]]
        with self.assertRaisesRegex(ValueError, "SVG centre"):
            T.svg_crosscheck("sarpedon", m, bad)

    def test_build_refuses_a_different_zone_list(self):
        maps, sha = maps_or_skip(self)
        m = copy.deepcopy(next(x for x in maps if x["key"] == "marmoreal"))
        m["zones"] = [z for z in m["zones"] if z["key"] != "violet"]
        topo, votes = evidence("marmoreal")
        with self.assertRaisesRegex(ValueError, "zone keys"):
            T.build_topology("marmoreal", m, sha, topo, votes)

    def test_cli_check_and_validate(self):
        maps_or_skip(self)
        self.assertEqual(T.main(["check"]), 0)
        self.assertEqual(T.main(["validate"]), 0)


if __name__ == "__main__":
    unittest.main()
