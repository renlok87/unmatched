"""Контракт движения значков v3 (docs/unreal/contracts/hud/icon-motion.json): схема, копия для UE, текстуры слоёв,
детерминизм эталонных поз. Генераторы — art/imagegen/hud-icons-v3/_tools/{motion_contract,icon_motion}.py."""
import json
import os
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TOOLS = REPO / "art" / "imagegen" / "hud-icons-v3" / "_tools"
sys.path.insert(0, str(TOOLS))
import icon_motion as M  # noqa: E402

CONTRACT = REPO / "docs" / "unreal" / "contracts" / "hud" / "icon-motion.json"
CONFIG = REPO / "unreal" / "Unmatched" / "Config" / "S08IconMotion.json"
GOLDEN = REPO / "docs" / "unreal" / "contracts" / "hud" / "icon-motion-golden.json"
ICONS_V3 = REPO / "art" / "imagegen" / "hud-icons-v3"
UE_SIZES = (24, 32, 48, 64)


class IconMotionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = M.load_contract(str(CONTRACT))

    def test_config_copy_is_identical(self):
        self.assertEqual(CONTRACT.read_bytes(), CONFIG.read_bytes(), "запустить motion_contract.py: копия в Config/ устарела")

    def test_all_23_icons_with_appear_and_leave(self):
        """23 принятых значка v3, 4 принятых DE-012 (`accepted_de012`, 2026-10-05), кандидат DE-012 (`candidates`) и
        принятые VR44 (`accepted_vr44`, VS-2 A2)."""
        self.assertEqual(len(self.c["order"]) - len(self.c.get("candidates", [])) - len(self.c.get("accepted_de012", []))
                         - len(self.c.get("accepted_vr44", [])), 23)
        self.assertEqual(set(self.c["order"]), set(self.c["icons"]))
        for icon, d in self.c["icons"].items():
            self.assertIn("appear", d["anims"], icon)
            self.assertIn("leave", d["anims"], icon)
            self.assertEqual(d["anims"]["appear"]["kind"], "enter", icon)
            self.assertEqual(d["anims"]["leave"]["kind"], "exit", icon)

    def test_tracks_are_well_formed(self):
        eases = set(self.c["eases"])
        props = set(self.c["props"])
        for icon, d in self.c["icons"].items():
            targets = {"all"} | {l["id"] for l in d["layers"]}
            for name, a in d["anims"].items():
                for branch in (a, a.get("reduced") or {"tracks": [], "duration_ms": 0}):
                    self.assertGreaterEqual(branch["duration_ms"], 0, (icon, name))
                    for tr in branch["tracks"]:
                        self.assertIn(tr["target"], targets, (icon, name))
                        self.assertIn(tr["prop"], props, (icon, name))
                        ts = [k[0] for k in tr["keys"]]
                        self.assertEqual(ts, sorted(ts), (icon, name, tr["prop"]))
                        self.assertLessEqual(ts[-1], branch["duration_ms"] + 1e-6, (icon, name, tr["prop"]))
                        for k in tr["keys"]:
                            self.assertIn(k[2], eases, (icon, name))
                # null = «значение на старте команды»: имеет смысл у событий и ухода; у появления и цикла начального
                # состояния нет — там только числа
                if a["kind"] in ("enter", "loop"):
                    for tr in a["tracks"]:
                        self.assertNotIn(None, [k[1] for k in tr["keys"]], (icon, name))

    def test_reduced_motion_is_opacity_only_and_short(self):
        """UI-ACC-005/006: в ветке reduced только opacity ≤ 100 мс (спиннер — ступени поворота, индикатор прогресса)."""
        for icon, d in self.c["icons"].items():
            for name, a in d["anims"].items():
                red = a.get("reduced")
                self.assertIsNotNone(red, (icon, name))
                if icon == "loader-spinner" and name == "cycle":
                    continue
                for tr in red["tracks"]:
                    self.assertEqual(tr["prop"], "opacity", (icon, name))
                self.assertLessEqual(red["duration_ms"], 100, (icon, name))

    def test_layer_textures_exist_for_ue_sizes(self):
        for icon, d in self.c["icons"].items():
            for l in d["layers"]:
                names = [l["src"]]
                if l["src"].endswith("#"):
                    names = [f"{l['src'][:-1]}_f{i:02d}" for i in range(l["frames"])]
                for n in names:
                    sub = "layers" if "_" in n else "sizes"
                    for s in UE_SIZES:
                        self.assertTrue((ICONS_V3 / sub / f"{n}-{s}.png").exists(), f"{sub}/{n}-{s}.png")

    def test_accepted_vr44_have_appear_and_leave(self):
        """IC-33: принятые значки VR44 (`accepted_vr44`) — записи контракта в `order` с appear (enter) и leave (exit);
        не пересекаются с DE-012 и кандидатами."""
        self.assertIn("accepted_vr44", self.c)
        vr44 = self.c["accepted_vr44"]
        self.assertEqual(len(vr44), len(set(vr44)))
        self.assertFalse(set(vr44) & (set(self.c.get("candidates", [])) | set(self.c.get("accepted_de012", []))))
        for icon in vr44:
            self.assertIn(icon, self.c["order"], icon)
            anims = self.c["icons"][icon]["anims"]
            self.assertEqual(anims["appear"]["kind"], "enter", icon)
            self.assertEqual(anims["leave"]["kind"], "exit", icon)

    def test_ue_sizes_textures_exist(self):
        """IC-33 (02 §3.2 ВР-62, §5.3): у каждой записи `ue_sizes` с 18 и 36 (24 su при DPI 0,75 и при 150 %); PNG
        значка, его слоёв и вариантов есть на каждом размере и нарисованы этим размером (из вектора, не даунскейл)."""
        from PIL import Image
        variants_of = {}
        for v, base in self.c.get("variants", {}).items():
            variants_of.setdefault(base, []).append(v)
        for icon, d in self.c["icons"].items():
            sizes = d.get("ue_sizes")
            self.assertIsNotNone(sizes, icon)
            self.assertEqual(sizes, sorted(set(sizes)), icon)
            # VS-4 V3: the zone icons only from 24 px (below 24 the L6 channel stays without them, IC-62...IC-69)
            need = {24, 32, 36, 48, 64} if icon.startswith("zone-") else {18, 24, 32, 36, 48, 64}
            self.assertTrue(need <= set(sizes), (icon, sizes))
            names = [icon] + variants_of.get(icon, [])
            for l in d["layers"]:
                names += [f"{l['src'][:-1]}_f{i:02d}" for i in range(l["frames"])] if l["src"].endswith("#") else [l["src"]]
            for n in sorted(set(names)):
                sub = "layers" if "_" in n else "sizes"
                for s in sizes:
                    p = ICONS_V3 / sub / f"{n}-{s}.png"
                    self.assertTrue(p.exists(), f"{sub}/{n}-{s}.png")
                    with Image.open(p) as im:
                        self.assertEqual(im.height, s, p.name)
                        self.assertIn(im.width, (s, 2 * s), p.name)

    def test_scale_exports_and_new_roles(self):
        """IC-33: движок пишет 18 / 36 / 72 у всех id набора (manifest — sha1 каждого файла); роли warning и heal — токены
        hud-style-tokens.json (ВР-66 алиас turn.flash.orange, ВР-67 fx.heal)."""
        try:
            import draw_icons as D  # noqa: E402  (pycairo)
        except ImportError as e:  # pragma: no cover
            self.skipTest(f"draw_icons.py: {e}")
        self.assertTrue({18, 36, 72} <= set(D.SIZES))
        manifest = json.loads((ICONS_V3 / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["sizes"], list(D.SIZES))
        for n in D.ALL:
            for s in D.sizes_of(n):
                self.assertIn(f"sizes/{n}-{s}.png", manifest["files"], (n, s))
        tokens = json.loads((REPO / "docs" / "unreal" / "contracts" / "hud" / "hud-style-tokens.json").read_text(encoding="utf-8"))
        for role, token in (("warning", "state.warning"), ("heal", "fx.heal")):
            self.assertEqual(D.ROLE[role], token)
            self.assertEqual(D.TOKENS[token].upper(), tokens["colors"][token]["hex"].upper(), token)
        self.assertEqual(tokens["colors"]["state.warning"].get("alias"), "turn.flash.orange")
        self.assertEqual(D.ORDER_ACCEPTED[:27], D.ORDER23 + list(D.DE_ACCEPTED))     # VR44 — только после DE-012
        self.assertFalse(set(D.CANDIDATES_VR44) & set(D.ORDER_ACCEPTED))              # кандидаты — не на листах принятых

    def test_golden_is_current_and_deterministic(self):
        stored = json.loads(GOLDEN.read_text(encoding="utf-8"))
        fresh = json.loads(json.dumps(M.golden(self.c), separators=(",", ":")))
        self.assertEqual(stored["contract_revision"], self.c["revision"])
        self.assertEqual(stored, fresh, "запустить icon_motion.py --golden: эталонные позы устарели")

    def test_appear_ends_at_master_pose(self):
        """Последний кадр появления = мастер (поза покоя), первый кадр не пустой (opacity > 0)."""
        for icon in self.c["order"]:
            a = M.Animator(self.c, icon)
            a.play("appear", 0)
            dur = self.c["icons"][icon]["anims"]["appear"]["duration_ms"]
            pp, vis = a.pose(0)
            self.assertTrue(vis, icon)
            self.assertGreater(pp["pose"]["all"]["opacity"], 0.0, icon)
            end, _ = a.pose(dur + 1)
            for tgt, pose in end["pose"].items():
                for p in ("scale", "scale_x", "scale_y", "tx", "ty", "rotate"):
                    if icon in ("loader-spinner",) and p == "rotate":
                        continue
                    if "cycle" in self.c["icons"][icon]["anims"]:
                        continue
                    self.assertAlmostEqual(pose[p], M.REST[p] if tgt == "all" else a.rest[tgt][p], 6, (icon, tgt, p))


SOURCE = REPO / "unreal" / "Unmatched" / "Source"
# DE-012: арт-приёмка пользователя 2026-10-05 (01-decisions, «Лист A/B DE-028 — ответ пользователя»): тёплое кольцо,
# сердце павшего, штамп и трекер DE — принятый набор; кольцо цвета команды — кандидат (AB-5 выбрал тёплое).
ACCEPTED_DE012 = ["marker-turn-ring", "resource-hp-fallen", "marker-x-stamp", "marker-action-slot-de"]
CANDIDATES = ["marker-turn-ring-team"]
DE012 = ["marker-turn-ring", "marker-turn-ring-team", "resource-hp-fallen", "marker-x-stamp", "marker-action-slot-de"]


class IconMotionCandidatesTests(unittest.TestCase):
    """DE-012 (W-15 арт): записи набора DE по ICON-MOTION.md и 01 F-07, F-09, F-12; принятые — по умолчанию, кандидат —
    только галерея."""

    @classmethod
    def setUpClass(cls):
        cls.c = M.load_contract(str(CONTRACT))
        cls.icons = cls.c["icons"]

    def keys(self, icon, anim, target, prop, reduced=False):
        a = self.icons[icon]["anims"][anim]
        br = a["reduced"] if reduced else a
        return [tr["keys"] for tr in br["tracks"] if tr["target"] == target and tr["prop"] == prop][0]

    def test_candidates_listed_in_order(self):
        self.assertEqual(self.c["candidates"], CANDIDATES)
        self.assertEqual(self.c["accepted_de012"], ACCEPTED_DE012)
        self.assertEqual(self.c["order"][23:23 + len(DE012)], DE012)          # после 23 v3, до принятых VR44
        self.assertEqual(self.c["order"][23 + len(DE012):], self.c.get("accepted_vr44", []))
        self.assertFalse(set(CANDIDATES) & set(ACCEPTED_DE012))

    def test_candidates_are_gallery_only(self):
        """Принятый арт — по умолчанию: ни один id кандидата не упоминается в коде UE вне автотестов (галерея берёт их из
        контракта)."""
        hits = []
        for path in SOURCE.rglob("*"):
            if path.suffix not in (".cpp", ".h") or path.name.endswith("Tests.cpp"):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            hits += [f"{path.name}: {cid}" for cid in CANDIDATES if f'"{cid}"' in text]
        self.assertEqual(hits, [])

    def test_accepted_de012_are_client_defaults(self):
        """Прогон I (AB-5…AB-8, ответ пользователя 2026-10-05): принятые id DE-012 рисует клиент без флагов — каждый
        назван в коде UE вне автотестов (FS08TurnHudLook), а прежний вид — только флагом отката `-S08…Legacy`."""
        text = ""
        for path in SOURCE.rglob("*"):
            if path.suffix in (".cpp", ".h") and not path.name.endswith("Tests.cpp"):
                text += path.read_text(encoding="utf-8", errors="ignore")
        self.assertEqual([cid for cid in ACCEPTED_DE012 if f'"{cid}"' not in text], [])
        for flag in ("S08TurnRingLegacy", "S08HeartGlowLegacy", "S08TrackerLegacy", "S08CrossLegacy"):
            self.assertIn(f'"{flag}"', text, flag)

    def test_accepted_forms_match_codex_proposal(self):
        """Принятые 2026-10-05 формы — те, что видел пользователь: PNG набора v3 совпадают с экспортом Codex
        (art/imagegen/hud-icons-de012-codex/vector-codex) по альфе и цвету (с учётом альфы) на 1024 / 32 / 24 / 16."""
        import numpy as np
        from PIL import Image
        codex = REPO / "art" / "imagegen" / "hud-icons-de012-codex" / "vector-codex"
        for name in ("marker-turn-ring", "resource-hp-fallen", "resource-hp-fallen_heart", "resource-hp-fallen_cross",
                     "marker-x-stamp", "marker-action-slot-de"):
            for size in (1024, 32, 24, 16):
                sub = "layers" if "_" in name else ("masters" if size == 1024 else "sizes")
                ours = ICONS_V3 / sub / (f"{name}.png" if size == 1024 else f"{name}-{size}.png")
                a = np.asarray(Image.open(ours).convert("RGBA")).astype(float)
                b = np.asarray(Image.open(codex / str(size) / f"{name}.png").convert("RGBA")).astype(float)
                self.assertEqual(a.shape, b.shape, (name, size))
                self.assertEqual(np.abs(a[..., 3] - b[..., 3]).max(), 0, (name, size))
                pa, pb = a[..., :3] * a[..., 3:] / 255, b[..., :3] * b[..., 3:] / 255
                self.assertLess(np.abs(pa - pb).max(), 1.0, (name, size))

    def test_vr44_forms_match_codex_proposal(self):
        """VS-2 A3 (IC-46, IC-48, IC-55, IC-59): формы Codex IC-36, вектор A (art/imagegen/hud-icons-vr44-codex/vector,
        принят по делегированию; log и pointer — fix1) перенесены один в один: альфа экспорта v3 побайтно равна альфе
        Codex на 1024 / 16 / 21 / 24 / 32 / 48 / 64 / 96, а цвет совпадает после назначения ближайшего токена (этап
        «точной палитры» Codex не переносится — ВР-VS2-23: внутренние AA-стыки как у остальных значков v3). Горячая точка
        указателя — та же, что в verification.json пакета."""
        import numpy as np
        from PIL import Image
        codex = REPO / "art" / "imagegen" / "hud-icons-vr44-codex" / "vector"
        tokens = {"#061623": "navy", "#F9EBDB": "cream", "#FAF8F2": "glyph", "#111317": "keyline"}
        pal = np.array([[int(h[i:i + 2], 16) for i in (1, 3, 5)] for h in tokens])
        for ours, theirs, roles in (("action-end-turn", "end-turn", pal), ("card-drop", "card-drop", pal),
                                    ("ui-log", "log", pal), ("cursor-pointer", "pointer", pal[[3, 2]])):
            for size in (1024, 16, 21, 24, 32, 48, 64, 96):
                path = ICONS_V3 / ("masters" if size == 1024 else "sizes") / (
                    f"{ours}.png" if size == 1024 else f"{ours}-{size}.png")
                a = np.asarray(Image.open(path).convert("RGBA")).astype(int)
                b = np.asarray(Image.open(codex / str(size) / f"{theirs}.png").convert("RGBA")).astype(int)
                self.assertEqual(a.shape, b.shape, (ours, size))
                self.assertEqual(np.abs(a[..., 3] - b[..., 3]).max(), 0, (ours, size))
                near = roles[((a[..., None, :3] - roles[None, None]) ** 2).sum(-1).argmin(-1)]
                seen = a[..., 3] > 0
                self.assertEqual(np.abs(near - b[..., :3])[seen].max(), 0, (ours, size))
        hot = json.loads((ICONS_V3 / "cursor-hotspots.json").read_text(encoding="utf-8"))["cursors"]["cursor-pointer"]
        self.assertEqual({k: hot[k] for k in ("24", "32", "48", "64")},
                         {"24": [8, 2], "32": [11, 2], "48": [17, 3], "64": [22, 4]})

    def test_zone_forms_match_codex_proposal(self):
        """VS-4 V3 (IC-62…IC-69): формы Codex IC-37, вариант A (art/imagegen/zone-icons-codex/vector, принят по
        делегированию) перенесены один в один: бинарная альфа (≥ 128) экспорта v3 и слоя _glyph равна альфе пакета на
        1024 / 16 / 21 / 24 / 32 / 48 / 64 / 96 (пакет рисовал без сглаживания, движок — со сглаживанием набора v3,
        ВР-VS4-50); цвет глифа цельного значка — правило контраста к замеренному диску (navy / card.glyph), как в пакете;
        слои _disc и _body общие (zone-gray), диск заходит под ободок (ВР-VS4-51)."""
        import numpy as np
        from PIL import Image
        from scipy import ndimage
        codex = REPO / "art" / "imagegen" / "zone-icons-codex" / "vector"
        keys = ("gray", "green", "blue", "violet", "purple", "red", "brown", "yellow")
        for key in keys:
            for size in (1024, 16, 21, 24, 32, 48, 64, 96):
                full = ICONS_V3 / ("masters" if size == 1024 else "sizes") / (
                    f"zone-{key}.png" if size == 1024 else f"zone-{key}-{size}.png")
                a = np.asarray(Image.open(full).convert("RGBA")).astype(int)
                b = np.asarray(Image.open(codex / str(size) / f"zone-{key}.png").convert("RGBA")).astype(int)
                self.assertEqual(a.shape, b.shape, (key, size))
                self.assertEqual(((a[..., 3] >= 128) != (b[..., 3] >= 128)).sum(), 0, (key, size))
                glyph = ICONS_V3 / "layers" / (f"zone-{key}_glyph.png" if size == 1024 else f"zone-{key}_glyph-{size}.png")
                ga = np.asarray(Image.open(glyph).convert("RGBA")).astype(int)[..., 3] >= 128
                gb = np.asarray(Image.open(codex / str(size) / f"zone-{key}_glyph.png").convert("RGBA")).astype(int)[..., 3] >= 128
                # the glyph mask alone: AA vs the aliased package differ only on the 1 px boundary band (16 px is a
                # boundary export, not a HUD size - ВР-42: the violet crescent's horn moves by a pixel there)
                band = ndimage.binary_dilation(gb) & ~ndimage.binary_erosion(gb)
                if size != 16:
                    self.assertEqual(((ga != gb) & ~band).sum(), 0, (key, size, "glyph"))
                # the ink of the full icon: the glyph pixels inside the keyline are the contrast-rule colour
                ink = {"gray": "#061623", "green": "#061623", "blue": "#061623", "violet": "#061623", "purple": "#FAF8F2",
                       "red": "#061623", "brown": "#FAF8F2", "yellow": "#061623"}[key]
                want = np.array([int(ink[i:i + 2], 16) for i in (1, 3, 5)])
                core = ndimage.binary_erosion((b[..., 3] == 255) & (np.abs(b[..., :3] - want).sum(-1) == 0), iterations=2)
                if size >= 24 and core.any():
                    self.assertLessEqual(np.abs(a[..., :3][core] - want).max(), 2, (key, size, "ink"))
        layers = ICONS_V3 / "layers"
        for f in ("zone-gray_body.png", "zone-gray_disc.png", "zone-gray_body-24.png", "zone-gray_disc-24.png"):
            self.assertTrue((layers / f).exists(), f)
        self.assertFalse((layers / "zone-green_body.png").exists(), "plate and disc are shared (zone-gray)")
        zone = {k: self.icons[f"zone-{k}"] for k in keys}
        for k, d in zone.items():
            src = {l["id"]: (l["src"], l.get("tint")) for l in d["layers"]}
            self.assertEqual(src, {"body": ("zone-gray_body", None), "disc": ("zone-gray_disc", "zone"),
                                   "glyph": (f"zone-{k}_glyph", "ink")}, k)
            self.assertEqual(d["ue_sizes"], [24, 32, 36, 48, 64], k)
            self.assertEqual((d["anims"]["appear"]["duration_ms"], d["anims"]["leave"]["duration_ms"]), (180, 120), k)

    def test_turn_ring_flash_1000_then_smoulder(self):
        for icon in ("marker-turn-ring", "marker-turn-ring-team"):
            a = self.icons[icon]["anims"]["appear"]
            self.assertEqual(a["duration_ms"], 1000, icon)
            rim = {l["id"]: l for l in self.icons[icon]["layers"]}["rim"]
            self.assertEqual(rim["rest"]["opacity"], 0.35, icon)
            self.assertEqual(self.keys(icon, "appear", "rim", "opacity")[-1][:2], [1000, 0.35], icon)
            self.assertEqual(self.keys(icon, "appear", "flash", "opacity")[-1][:2], [1000, 0.0], icon)
            self.assertEqual(self.keys(icon, "appear", "rim", "opacity", reduced=True)[-1][:2], [100, 0.35], icon)
            self.assertNotIn("cycle", self.icons[icon]["anims"], icon)          # кольцо не циклится (бюджет)
            self.assertEqual(self.icons[icon]["anims"]["leave"]["duration_ms"], 120, icon)
        frames = self.keys("marker-turn-ring", "appear", "flash", "frame")
        self.assertEqual([k[1] for k in frames], [0, 1, 2, 3, 4, 5, 6, 6])
        team = {l["id"]: l.get("tint") for l in self.icons["marker-turn-ring-team"]["layers"]}
        self.assertEqual(team, {"rim": "team", "flash": "team"})

    def test_heart_damage_1000_with_glow_pulse(self):
        a = self.icons["resource-hp-full"]["anims"]["damage"]
        self.assertEqual((a["duration_ms"], a["beat_ms"], a.get("hold", False)), (1000, 60, False))
        self.assertEqual([k[:2] for k in self.keys("resource-hp-full", "damage", "glow", "opacity")],
                         [[0, 0.0], [200, 0.0], [320, 1.0], [560, 0.45], [760, 0.85], [1000, 0.0]])
        self.assertEqual(a["reduced"]["tracks"], [])

    def test_stamps_200_beat_120(self):
        for icon, target in (("resource-hp-fallen", "cross"), ("marker-x-stamp", "sign")):
            a = self.icons[icon]["anims"]["appear"]
            self.assertEqual((a["duration_ms"], a["beat_ms"]), (200, 120), icon)
            self.assertEqual([k[:2] for k in self.keys(icon, "appear", target, "scale")], [[0, 0.0], [120, 1.08], [200, 1.0]])
        # форма Codex (2026-10-05): почерневшее сердце — свой слой, не текстура пустого сердца
        heart = {l["id"]: l["src"] for l in self.icons["resource-hp-fallen"]["layers"]}["heart"]
        self.assertEqual(heart, "resource-hp-fallen_heart")

    def test_tracker_de_variant(self):
        d = self.icons["marker-action-slot-de"]["anims"]
        self.assertEqual((d["slot_pulse"]["kind"], d["slot_pulse"]["duration_ms"]), ("loop", 770))
        self.assertEqual((d["fill"]["duration_ms"], d["fill"]["hold"]), (300, True))
        self.assertEqual(self.keys("marker-action-slot-de", "fill", "body", "opacity")[0][:2], [0, 0.4])
        self.assertTrue(d["unfill"]["hold"])
        # v3 по умолчанию не тронут: spend = opacity 0,4 за 150 мс
        for icon in ("action-attack", "action-defense", "action-maneuver", "action-scheme"):
            sp = self.icons[icon]["anims"]["spend"]
            self.assertEqual((sp["duration_ms"], sp["tracks"][0]["keys"][-1][1]), (150, 0.4), icon)
            self.assertNotIn("fill", self.icons[icon]["anims"], icon)

    def test_candidate_demo_plays(self):
        """Сценарий галереи: заполненный слот виден, кольцо после заливки погасло; крест павшего встал в покой."""
        a = M.Animator(self.c, "marker-action-slot-de")
        sched, _ = M.demo_schedule(self.c, "marker-action-slot-de")
        t_fill = [t for t, op in sched if op == "fill"][0]
        for t, op in sched:
            if t <= t_fill + 300:
                a.play(op, t)
        p = a.pose(t_fill + 300)[0]["pose"]
        self.assertAlmostEqual(p["body"]["opacity"], 1.0, 6)
        self.assertAlmostEqual(p["ring"]["opacity"], 0.0, 6)


class IconMotionSemanticsTests(unittest.TestCase):
    """Ревью 2026-10-03: события поверх базы. Те же случаи проверяет UE-тест Unmatched.S08.IconMotion.Semantics."""

    @classmethod
    def setUpClass(cls):
        cls.c = M.load_contract(str(CONTRACT))

    def pose(self, a, t):
        pp, vis = a.pose(t)
        return pp["pose"], vis

    def test_leave_after_hold_fades(self):
        a = M.Animator(self.c, "action-attack")
        a.play("appear", 0)
        a.play("hover_in", 300)
        a.play("spend", 500)
        a.play("leave", 1000)
        p, vis = self.pose(a, 1060)
        self.assertTrue(vis)
        self.assertLess(p["all"]["opacity"], 0.4)       # от 0,4 (spend) к 0
        self.assertLess(p["all"]["scale"], 1.06)        # от 1,06 (hover) к 0,92
        self.assertFalse(self.pose(a, 1121)[1])

    def test_tap_after_hover_returns_to_hover(self):
        a = M.Animator(self.c, "action-attack")
        a.play("appear", 0)
        a.play("hover_in", 300)
        a.play("tap", 600)
        self.assertAlmostEqual(self.pose(a, 600)[0]["all"]["scale"], 1.06, 4)   # без скачка в первый кадр
        self.assertAlmostEqual(self.pose(a, 650)[0]["all"]["scale"], 0.94, 4)
        self.assertAlmostEqual(self.pose(a, 800)[0]["all"]["scale"], 1.06, 4)

    def test_future_appear_is_invisible(self):
        a = M.Animator(self.c, "state-hint")
        a.play("appear", 120)
        self.assertFalse(self.pose(a, 60)[1])
        self.assertTrue(self.pose(a, 120)[1])

    def test_equal_time_later_command_wins(self):
        a = M.Animator(self.c, "action-attack")
        a.play("appear", 0)
        a.play("release", 500)
        a.play("hover_out", 500)
        self.assertAlmostEqual(self.pose(a, 700)[0]["all"]["scale"], 1.0, 4)


class GalleryRasterTests(unittest.TestCase):
    """VS-2 IC-70 (ВР-VS2-37): эталон G-ICON растрируется как Slate (raster="ue": углы осевого квада на целых
    пикселях, выборка sRGB-текстуры в линейном свете); на покое он совпадает с растром листов (raster="ref")."""

    @classmethod
    def setUpClass(cls):
        try:
            import motion as MO  # noqa: F401  (draw_icons: pycairo)
        except ImportError as e:  # pragma: no cover
            raise unittest.SkipTest(f"motion.py: {e}")
        cls.MO = MO
        cls.c = M.load_contract(str(CONTRACT))

    def pose_at(self, icon, anim, t_ms):
        a = M.Animator(self.c, icon)
        a.play("appear", 0)
        a.play(anim, 400)
        pp, vis = a.pose(400 + t_ms)
        self.assertTrue(vis)
        return a, pp

    def test_rest_pose_is_the_same_in_both_rasters(self):
        import numpy as np
        a = M.Animator(self.c, "action-end-turn")
        a.play("appear", 0)
        pp, _ = a.pose(400)
        self.assertAlmostEqual(pp["pose"]["all"]["scale"], 1.0, 6)
        ref = np.asarray(self.MO.compose(a, pp, 64, raster="ref"))
        ue = np.asarray(self.MO.compose(a, pp, 64, raster="ue"))
        self.assertTrue(np.array_equal(ref, ue))

    def test_ue_raster_snaps_the_scaled_quad_to_pixels(self):
        import numpy as np
        a, pp = self.pose_at("action-attack", "hover_in", 250)  # hover 1,06: квад 64 px -> 67,8 px
        self.assertGreater(pp["pose"]["all"]["scale"], 1.03)
        ue = np.asarray(self.MO.compose(a, pp, 64, raster="ue")).astype(int)
        ref = np.asarray(self.MO.compose(a, pp, 64, raster="ref")).astype(int)
        self.assertGreater(np.abs(ue - ref).sum(), 0)
        k = pp["pose"]["all"]["scale"]
        Mx = self.MO._snap_quad(np.array([[k, 0, 16 + 32 * (1 - k)], [0, k, 16 + 32 * (1 - k)], [0, 0, 1.0]]), 64, 64)
        for v in (Mx[0, 2], Mx[0, 0] * 64 + Mx[0, 2]):
            self.assertEqual(v, round(v))

    def test_linear_light_filter_brightens_a_dark_to_light_edge(self):
        import numpy as np
        from PIL import Image
        tex = Image.new("RGBA", (2, 1), (0, 0, 0, 255))
        tex.putpixel((1, 0), (255, 255, 255, 255))
        inv = (0.5, 0, -0.25, 0, 1, 0)  # 4 px из 2 текселей: середина — смесь 50/50
        lin = np.asarray(self.MO._transform_linear(tex, (4, 1), inv))[0, :, 0].tolist()
        gam = np.asarray(tex.transform((4, 1), Image.AFFINE, data=inv, resample=Image.BILINEAR))[0, :, 0].tolist()
        self.assertGreater(lin[1] + lin[2], gam[1] + gam[2])


class GalleryCompareSummaryTests(unittest.TestCase):
    """compare_ue_gallery.summarize: средние по новым id и сверка трассы ICONGALLERY ids со списками контракта."""

    def test_trace_lists_every_contract_id(self):
        import tempfile
        try:
            import compare_ue_gallery as G
        except ImportError as e:  # pragma: no cover
            raise unittest.SkipTest(f"compare_ue_gallery.py: {e}")
        c = M.load_contract(str(CONTRACT))
        metrics = {i: {"0": {"mean": 0.1, "p99": 1, "max": 2, "local_ms": 0.0}} for i in c["order"]}
        with tempfile.TemporaryDirectory() as d:
            ids = ",".join(c["order"])
            with open(os.path.join(d, "gallery.trace.log"), "w", encoding="utf-8") as fh:
                fh.write(f"2026.10.06-15.17.43 ICONGALLERY ids n={len(c['order'])} columns=7 list={ids}\n")
            s = G.summarize(c, metrics, d)
            self.assertTrue(s["trace_ok"])
            self.assertEqual(s["new_pairs"], len(c["accepted_vr44"]))
            self.assertAlmostEqual(s["new_mean"], 0.1, 6)
            with open(os.path.join(d, "gallery.trace.log"), "w", encoding="utf-8") as fh:
                fh.write("ICONGALLERY ids n=1 columns=7 list=state-boost\n")
            s = G.summarize(c, metrics, d)
            self.assertFalse(s["trace_ok"])
            self.assertIn("ui-log", s["trace_missing"])


if __name__ == "__main__":
    unittest.main()
