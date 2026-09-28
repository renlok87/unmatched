import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # qa010 dir, any discovery root

import json
import tempfile
import unittest
from pathlib import Path

from tests._util import run_cli
from qa010lib.checklist import build_checklist, provenance_hint, render_markdown


def write(d: Path, name: str, data: dict) -> str:
    p = d / name
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return name


K1_LIVE = "docs/game-design/evidence/ART-003/live-selection-run/run-20260928-061853/phase2-board-host-1920x1080.png"
K2_LIVE = "docs/game-design/evidence/ART-004/live-k2-label-probe-1p6/run-20260928-064001/phase2-board-host-1920x1080.png"
K3_LIVE = ("docs/game-design/evidence/ART-003/live-combat-icon-damage-run/combat-20260928-073145/joiner/"
           "s09-combat-resolve-revealed.png")
K1_EDITOR = "docs/game-design/evidence/ART-005/combined-k1-editor-2026-09-27.png"


def c9_result(frame, decor_spec="l3=mask:decor-l3.png", decor_kind="mask", proxy=False, new_format=True):
    """c9 JSON as written by qa010.py c9 (new_format) or by tool 1.0.0 (no layer_basis)."""
    r = {"command": "c9", "status": "measured", "delta_ev": {"used": 0.89},
         "verdicts": {"more_saturated": {"value": -4.1}}, "frame": {"path": frame},
         "game_region": [{"spec": "board=trace-cells:all", "proxy": False}],
         "decor_region": {"spec": decor_spec, "proxy": proxy}}
    if not new_format:
        r.update(result_normative="pass", result_proposed="fail")
        return r
    r["game_region"][0]["kind"] = "trace-cells"
    r["decor_region"]["kinds"] = [decor_kind]
    if proxy:
        r.update(result_normative="proxy", result_proposed="proxy",
                 result_on_proxy={"normative": "pass", "proposed": "fail"},
                 layer_basis={"proxy": True, "normative": False, "proxy_regions": [
                     {"layer": "decor", "spec": decor_spec, "kind": decor_kind, "why": "поднос L4"}]})
    else:
        r.update(result_normative="pass", result_proposed="fail", layer_basis={"proxy": False, "normative": True})
    return r


class ChecklistTests(unittest.TestCase):
    def make_config(self, d: Path, viewer_kind="agent", k2_path=None):
        k1 = K1_LIVE
        k2 = k2_path or "docs/game-design/evidence/ART-004/medusa-k2-ue-editor-2026-09-28.png"
        k3 = K3_LIVE
        derive = write(d, "derive.json", {"command": "derive", "entries": [
            {"input": k1}, {"input": k3}]})
        luma = write(d, "luma.json", {"command": "luma", "frames": [
            {"path": k1, "stats": {"luma_p50": 61.0, "luma_p90": 204.1}}]})
        c9 = write(d, "c9.json", c9_result(k1))
        plate = write(d, "plate.json", {"command": "plate", "status": "requires_new_trace",
                                        "reason": "trace has no plate / reachable",
                                        "frame": {"path": k2, "matches_shot": True}, "shot": Path(k2).name,
                                        "trace": Path(k2).parent.as_posix() + "/phase2-client-host.trace.log"})
        icon = write(d, "icon.json", {"command": "icon", "status": "measured", "result": "fail",
                                      "frame": {"path": k3},
                                      "sizes": [{"size_px": 24, "contrast_ratio": 2.1, "upscaled": False}]})
        return {
            "title": "QA-010 test",
            "generated_utc": "2026-09-28T00:00:00Z",
            "run": {"exe_sha256": "abc"},
            "viewer": {"kind": viewer_kind, "note": "fresh read-only agent"},
            "frames": {"K1": {"path": k1, "provenance": "packaged-live"},
                       "K2": {"path": k2},
                       "K3": {"path": k3}},
            "results": [{"k": "K1..K3", "path": derive}, {"k": "K1", "path": luma},
                        {"k": "K1", "path": c9}, {"k": "K2", "path": plate}, {"k": "K3", "path": icon}],
            "manual": {"K1.hero_helper": {"status": "да", "note": "4 типа силуэтов"},
                       "K2.face_weapon": {"status": "нет", "note": "1,6× не раскрывает лицо"}},
            "elements": [{"frame": "K1", "id": "lantern", "status": "отложено", "reason": "нет ассета",
                          "norm": "03 С-6"},
                         {"frame": "K3", "id": "custom_extra", "element": "Доп. элемент", "status": "есть"}],
        }

    def rows(self, cl):
        return {r["id"]: r for r in cl["rows"]}

    def test_statuses(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            cl = build_checklist(self.make_config(d), d)
            r = self.rows(cl)
            self.assertTrue(r["K1.c9"]["status"].startswith("измерено: pass (норматив) / fail (предложено)"))
            self.assertIn("ΔEV=+0.890", r["K1.c9"]["detail"])
            self.assertEqual(r["K2.plate"]["status"], "нет данных: требуется новая трасса")
            self.assertTrue(r["K3.icon_sizes"]["status"].startswith("измерено: fail"))
            self.assertEqual(r["K1.hero_helper"]["status"], "ручная: да")
            self.assertEqual(r["K2.face_weapon"]["status"], "ручная: нет")
            self.assertEqual(r["K1.multizone"]["status"], "открыто (ручная проверка)")
            self.assertEqual(r["ALL.viewer"]["status"], "суррогат (агент) — до ответа пользователя")
            self.assertIn("K2", r["ALL.derived_evidence"]["detail"])   # K2 derivative missing
            self.assertEqual(r["ALL.derived_evidence"]["status"], "измерено: неполно")
            self.assertIn("p50 61.0", r["ALL.luma_recorded"]["detail"])
            prov = r["ALL.provenance"]["status"]
            self.assertIn("K2", prov)                     # editor frame is not acceptance evidence
            self.assertIn("K3 (только подсказка по пути)", prov)
            self.assertIn("авто:", r["K1.teams_gray"]["detail"])

    def test_elements_table(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            cl = build_checklist(self.make_config(d), d)
            el = {(e["frame"], e["id"]): e for e in cl["elements"]}
            self.assertEqual(el[("K1", "lantern")]["status"], "отложено")
            self.assertEqual(el[("K1", "fog")]["status"], "не указано")
            self.assertEqual(el[("K3", "custom_extra")]["status"], "есть")
            self.assertIn(("K3", "poses"), el)
            self.assertIn(("K3", "inspector_2d"), el)

    def test_never_declares_acceptance(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            cl = build_checklist(self.make_config(d, viewer_kind="human"), d)
            md = render_markdown(cl)
            for r in cl["rows"]:
                self.assertNotIn("принят", r["status"].lower())
            self.assertIn("Не является приёмкой", md)
            self.assertIn("| K2.plate |", md)
            self.assertIn("## Элементы кадра: есть / отложено", md)
            self.assertEqual(self.rows(cl)["ALL.viewer"]["status"], "указан: человек")

    def test_cli_writes_md_and_json(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            cfg = d / "cfg.json"
            cfg.write_text(json.dumps(self.make_config(d), ensure_ascii=False), encoding="utf-8")
            code, res, err = run_cli("checklist", "--config", cfg, "--out-md", d / "c.md", "--out-json", d / "c.json")
            self.assertEqual(code, 0, err)
            self.assertTrue((d / "c.md").read_text(encoding="utf-8").startswith("# QA-010 test"))
            self.assertEqual(json.loads((d / "c.json").read_text(encoding="utf-8"))["rows"], res["rows"])

    def test_same_basename_frames_are_not_confused(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            k1 = "ev/run-1/phase2-board-host-1920x1080.png"
            k2 = "ev/run-2/phase2-board-host-1920x1080.png"
            derive = write(d, "derive.json", {"command": "derive", "entries": [{"input": "./" + k1}]})
            luma = write(d, "luma.json", {"command": "luma", "frames": [
                {"path": "C:/repo/" + k1, "stats": {"luma_p50": 1.0, "luma_p90": 2.0}},
                {"path": k2, "stats": {"luma_p50": 3.0, "luma_p90": 4.0}}]})
            name = "phase2-board-host-1920x1080.png"
            proj = write(d, "proj.json", {"command": "project", "trace": "ev/run-1/phase2-client-host.trace.log",
                                          "shots": [
                {"shot": name, "projection": {"ok": False}},
                {"shot": name, "projection": {"ok": True, "residual_max_px_used_camera": 1.3},
                 "cells_in_frame": {"total": 30, "full": 30, "partial": 0, "offscreen": 0}}]})
            cfg = {"frames": {"K1": {"path": k1}, "K2": {"path": k2}},
                   "results": [{"k": "K1..K3", "path": derive}, {"k": "K1..K3", "path": luma},
                               {"k": "K1", "path": proj}]}
            r = self.rows(build_checklist(cfg, d))
            self.assertEqual(r["ALL.derived_evidence"]["status"], "измерено: неполно")
            self.assertIn("K2", r["ALL.derived_evidence"]["detail"])
            self.assertIn("K1: p50 1.0", r["ALL.luma_recorded"]["detail"])
            self.assertIn("K2: p50 3.0", r["ALL.luma_recorded"]["detail"])
            self.assertEqual(r["ALL.luma_recorded"]["status"], "измерено: неполно")   # no K3 frame
            self.assertIn("30/30", r["K1.cells_all"]["detail"])
            self.assertEqual(r["K1.cells_all"]["status"], "открыто (ручная проверка)")
            # the same SHOT name from the run-2 trace is K2's frame, not K1's
            proj2 = write(d, "proj2.json", {"command": "project", "trace": "ev/run-2/phase2-client-host.trace.log",
                                            "shots": [{"shot": name, "projection": {"ok": True,
                                                       "residual_max_px_used_camera": 0.5},
                                                       "cells_in_frame": {"total": 30, "full": 1, "partial": 0,
                                                                          "offscreen": 29}}]})
            cfg["results"][2] = {"k": "K1", "path": proj2}
            r = self.rows(build_checklist(cfg, d))
            self.assertIn("нет данных: результат по другому кадру", r["K1.cells_all"]["detail"])
            self.assertIn("трасса ev/run-2/phase2-client-host.trace.log не из каталога кадра",
                          r["K1.cells_all"]["detail"])

    def test_c9_on_proxy_is_never_normative(self):
        """A tray ring (L4) measured as decor must not close the С-9 row, whatever
        the region is called and whichever tool version wrote the JSON."""
        variants = {
            "new": c9_result(K1_LIVE, "decor=trace-ring:0.05,0.35", "trace-ring", proxy=True),
            "1.0.0 flag": c9_result(K1_LIVE, "decor=trace-ring:0.05,0.35", proxy=True, new_format=False),
            "1.0.0 spec only": c9_result(K1_LIVE, "decor=trace-ring:0.05,0.35", proxy=False, new_format=False),
            "board as decor": c9_result(K1_LIVE, "d=trace-cells:3,2", proxy=False, new_format=False),
        }
        for label, res in variants.items():
            with tempfile.TemporaryDirectory() as td:
                d = Path(td)
                cfg = {"frames": {"K1": {"path": K1_LIVE}}, "results": [{"k": "K1", "path": write(d, "c9.json", res)}]}
                row = self.rows(build_checklist(cfg, d))["K1.c9"]
                self.assertTrue(row["status"].startswith("нет данных: декор — прокси"), (label, row["status"]))
                self.assertIn("stencil- или ручная маска L3", row["status"])
                self.assertNotIn("норматив)", row["status"])
                self.assertIn("измерено на прокси (не норматив)", row["detail"])
                self.assertIn("ΔEV=+0.890", row["detail"])

    def test_c9_proxy_end_to_end_from_cli(self):
        """c9 JSON produced by the real command -> checklist row."""
        from tests._util import save_png, solid, topdown_trace
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            t = d / "run-20260928-000000" / "phase2-client-host.trace.log"
            t.parent.mkdir()
            t.write_text(topdown_trace(name="k1.png", cam_z=2000), encoding="utf-8")
            img = solid(1920, 1080, (30, 30, 30))
            img[300:780, 500:1420] = (140, 140, 140)
            f = save_png(t.parent / "k1.png", img)
            code, _, err = run_cli("c9", f, "--trace", t, "--game", "board=trace-cells:all",
                                   "--decor", "decor=trace-ring:0.05,0.35", "--json", d / "c9.json")
            self.assertEqual(code, 3, err)
            cfg = {"frames": {"K1": {"path": str(f), "provenance": "packaged-live"}},
                   "results": [{"k": "K1", "path": "c9.json"}]}
            row = self.rows(build_checklist(cfg, d))["K1.c9"]
            self.assertTrue(row["status"].startswith("нет данных: декор — прокси"), row["status"])
            self.assertIn("decor=trace-ring:0.05,0.35", row["detail"])

    def test_result_on_editor_frame_is_not_k1_evidence(self):
        """c9 measured on an editor frame but labelled k=K1: the K1 row gets no
        value and ALL.provenance is not «ок» even though K1..K3 are packaged-live."""
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            frames = {"K1": {"path": K1_LIVE, "provenance": "packaged-live"},
                      "K2": {"path": K2_LIVE, "provenance": "packaged-live"},
                      "K3": {"path": K3_LIVE, "provenance": "packaged-live"}}
            good = {"frames": frames, "results": [{"k": "K1", "path": write(d, "c9-live.json", c9_result(K1_LIVE))}]}
            r = self.rows(build_checklist(good, d))
            self.assertEqual(r["K1.c9"]["status"], "измерено: pass (норматив) / fail (предложено)")
            self.assertEqual(r["ALL.provenance"]["status"], "ок")
            bad = {"frames": frames, "results": [{"k": "K1", "path": write(d, "c9-k1.json", c9_result(K1_EDITOR))}]}
            r = self.rows(build_checklist(bad, d))
            self.assertEqual(r["K1.c9"]["status"], "нет данных: результат по другому кадру")
            self.assertIn("combined-k1-editor-2026-09-27.png", r["K1.c9"]["detail"])
            prov = r["ALL.provenance"]
            self.assertTrue(prov["status"].startswith("не годится для приёмки"), prov["status"])
            self.assertIn("результаты по другим кадрам", prov["status"])
            self.assertIn("c9-k1.json (K1)", prov["detail"])
            self.assertIn("editor-or-blender (hint)", prov["detail"])

    def test_same_basename_other_run_is_not_bound(self):
        """Evidence basenames repeat per run: K2's frame is not K1's frame."""
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            cfg = {"frames": {"K1": {"path": K1_LIVE}},
                   "results": [{"k": "K1", "path": write(d, "c9.json", c9_result(K2_LIVE))}]}
            r = self.rows(build_checklist(cfg, d))
            self.assertEqual(r["K1.c9"]["status"], "нет данных: результат по другому кадру")

    def test_trace_mask_from_another_shot_is_not_bound(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            res = c9_result(K1_LIVE)
            res["trace"] = {"shot": "phase2-board-joiner-1920x1080.png", "shot_matches_frame": False}
            cfg = {"frames": {"K1": {"path": K1_LIVE}}, "results": [{"k": "K1", "path": write(d, "c9.json", res)}]}
            row = self.rows(build_checklist(cfg, d))["K1.c9"]
            self.assertEqual(row["status"], "нет данных: результат по другому кадру")
            self.assertIn("SHOT-блок трассы phase2-board-joiner-1920x1080.png", row["detail"])

    def test_plate_and_icon_binding(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            run_dir = Path(K2_LIVE).parent.as_posix()
            measured = {"command": "plate", "status": "measured", "result": "pass",
                        "checked_cells": {"count": 14}, "violations": [],
                        "shot": "phase2-board-host-1920x1080.png"}
            by_trace = {**measured, "trace": run_dir + "/phase2-client-host.trace.log"}
            other_run = {**measured, "trace": "docs/game-design/evidence/ART-004/live-k2-label-probe-5x/"
                                              "run-20260928-063853/phase2-client-host.trace.log"}
            by_frame = {**measured, "trace": "C:/elsewhere/t.log",
                        "frame": {"path": K2_LIVE, "matches_shot": True}}
            wrong_shot = {**by_frame, "frame": {"path": K2_LIVE, "matches_shot": False}}
            no_frame = {k: v for k, v in measured.items() if k != "shot"}
            icon_other = {"command": "icon", "status": "measured", "result": "pass", "frame": {"path": K1_LIVE},
                          "sizes": [{"size_px": 24, "contrast_ratio": 4.0, "upscaled": False}]}
            expect = [(by_trace, "измерено: pass (предложенный порог)"),
                      (by_frame, "измерено: pass (предложенный порог)"),
                      (other_run, "нет данных: результат по другому кадру"),
                      (wrong_shot, "нет данных: результат по другому кадру"),
                      (no_frame, "нет данных: результат по другому кадру")]
            for i, (res, want) in enumerate(expect):
                cfg = {"frames": {"K2": {"path": K2_LIVE}, "K3": {"path": K3_LIVE}},
                       "results": [{"k": "K2", "path": write(d, f"plate{i}.json", res)},
                                   {"k": "K3", "path": write(d, "icon.json", icon_other)}]}
                r = self.rows(build_checklist(cfg, d))
                self.assertEqual(r["K2.plate"]["status"], want, (i, r["K2.plate"]["detail"]))
                self.assertEqual(r["K3.icon_sizes"]["status"], "нет данных: результат по другому кадру")

    def test_luma_on_other_frames_only(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            luma = write(d, "luma.json", {"command": "luma", "frames": [
                {"path": K1_EDITOR, "stats": {"luma_p50": 1.0, "luma_p90": 2.0}}]})
            cfg = {"frames": {"K1": {"path": K1_LIVE}}, "results": [{"k": "K1..K3", "path": luma}]}
            r = self.rows(build_checklist(cfg, d))
            self.assertEqual(r["ALL.luma_recorded"]["status"], "нет данных: результат по другому кадру")
            self.assertIn("результаты по другим кадрам", r["ALL.provenance"]["status"])

    def test_layer_rules(self):
        from qa010lib.layers import proxy_regions, spec_kind
        self.assertEqual(spec_kind("decor=trace-ring:0.05,0.35"), "trace-ring")
        self.assertEqual(spec_kind("g=frame"), "frame")
        got = proxy_regions([("decor", "a=trace-ring:0,1", "trace-ring", False, ""),
                             ("decor", "b=trace-cells:1,1", "trace-cells", False, ""),
                             ("decor", "c=mask:l3.png", "mask", False, ""),
                             ("decor", "e=poly:0,0;9,0;9,9", "poly", False, ""),
                             ("game", "f=trace-cells:all", "trace-cells", False, ""),
                             ("game", "g=frame", "frame", False, ""),
                             ("game", "h=mask:x.png", "mask", True, "flagged")])
        self.assertEqual([(x["layer"], x["spec"]) for x in got],
                         [("decor", "a=trace-ring:0,1"), ("decor", "b=trace-cells:1,1"),
                          ("game", "g=frame"), ("game", "h=mask:x.png")])

    def test_provenance_hint(self):
        self.assertEqual(provenance_hint("a/ART-004/x-ue-editor-2026.png"), "editor-or-blender (hint)")
        self.assertEqual(provenance_hint("e/ART-005/combined-k1-editor-2026-09-27.png"), "editor-or-blender (hint)")
        self.assertEqual(provenance_hint("e/ART-004/x-blender-review.png"), "editor-or-blender (hint)")
        self.assertEqual(provenance_hint("e/ART-004/live-k2/run-20260928-063853/p.png"), "packaged-live (hint)")
        self.assertEqual(provenance_hint("e/ART-003/live-x/combat-20260928-073145/joiner/p.png"), "packaged-live (hint)")
        self.assertEqual(provenance_hint("e/S05/frames/frame-K1.png"), "unknown")
        self.assertEqual(provenance_hint(None), "unknown")


if __name__ == "__main__":
    unittest.main()
