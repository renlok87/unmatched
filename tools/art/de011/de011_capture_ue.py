"""UE editor task (UnrealEditor-Cmd -ExecutePythonScript, -RenderOffScreen), run by tools/art/de011/de011.py capture.

ARGS: JSON file named by the environment variable DE010_ARGS (the runner of tools/art/de010/de010.py):
  {"out": <report.json>, "frames": <dir>, "tag": "before"|"after", "dissolve": bool,
   "figures": [{"key", "look", "mesh", "mi", "base", "base_mi", "dissolve_mi"}]}
A blank map in memory (nothing is saved): the four v2 figures on their pedestals in the reference pose side by side
(Arthur P1, Merlin P2, Medusa P1, Harpy P2: both team colours), the same lights, fixed manual exposure, no Lumen GI /
reflections, no temporal AA, no bloom as tools/art/de010 (one capture is a deterministic frame); a SceneCapture2D
takes
  * <tag>-final-d0[-b].png  final colour (LDR), body MIs, every CPD 0 (twice: the noise floor of one session)
  * <tag>-base-d0.png       unlit (show flag Lighting off: base colour + emissive)
  * <tag>-final-ignore.png  body MIs with CPD_Dissolve 0.6 and CPD_DissolveStyle 1 set: the default permutation must
                            ignore both slots (= final-d0)
  (dissolve: true, after the apply)
  * <tag>-mic-p0.png        dissolve MICs at progress 0 (the swap at the start of the dissolve must not show)
  * <tag>-fade-p35 / -p70, <tag>-ash-p35 / -p70, <tag>-ash-p35-unlit   the two styles mid-way; the pedestals grey
                            out with CPD_Fade = progress (v1 slot 11)
  * <tag>-fade-p100 / -ash-p100   progress 1: every figure pixel clipped (= <tag>-empty, figures hidden)
  * <tag>-empty.png         bodies hidden, pedestals at CPD_Fade 1
Then the editor quits. Errors are written to the report as {"error", "traceback"}.
"""
import json
import os
import traceback

import unreal as u

ARGS = json.load(open(os.environ["DE010_ARGS"], encoding="utf-8"))
OUT = ARGS["out"]
FRAMES = ARGS["frames"]
DISSOLVE_SLOT, STYLE_SLOT, FADE_SLOT = 13, 14, 11
W, H = 1600, 640


def obj(path):
    return path if "." in path.rsplit("/", 1)[-1] else "%s.%s" % (path, path.rsplit("/", 1)[-1])


def load(path):
    a = u.load_asset(obj(path))
    if a is None:
        raise RuntimeError("asset not found: %s" % path)
    return a


def write(data):
    with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(data, indent=1, sort_keys=True) + "\n")


# state: (material "mi" | "dissolve", progress, style, bodies visible, lit)
PLAN = [("final-d0", ("mi", 0.0, 0.0, True, True)), ("final-d0-b", ("mi", 0.0, 0.0, True, True)),
        ("base-d0", ("mi", 0.0, 0.0, True, False)), ("final-ignore", ("mi", 0.6, 1.0, True, True))]
DISSOLVE_PLAN = [("mic-p0", ("dissolve", 0.0, 0.0, True, True)),
                 ("fade-p35", ("dissolve", 0.35, 0.0, True, True)), ("fade-p70", ("dissolve", 0.7, 0.0, True, True)),
                 ("ash-p35", ("dissolve", 0.35, 1.0, True, True)), ("ash-p70", ("dissolve", 0.7, 1.0, True, True)),
                 ("ash-p35-unlit", ("dissolve", 0.35, 1.0, True, False)),
                 ("fade-p100", ("dissolve", 1.0, 0.0, True, True)), ("ash-p100", ("dissolve", 1.0, 1.0, True, True)),
                 ("empty", ("mi", 1.0, 0.0, False, True))]


class Job:
    def __init__(self):
        self.frame = 0
        self.handle = None
        self.report = {"tag": ARGS["tag"], "frames": {}, "figures": []}

    def finish(self, error=None):
        if self.handle is not None:
            u.unregister_slate_post_tick_callback(self.handle)
            self.handle = None
        if error:
            self.report["error"] = error
        write(self.report)
        u.EditorPythonScripting.set_keep_python_script_alive(False)
        u.SystemLibrary.quit_editor()

    def apply_state(self, state):
        material, progress, style, visible, _ = state
        for comp, base, fig in zip(self.comps, self.bases, ARGS["figures"]):
            mi = self.dissolve_mis[fig["key"]] if material == "dissolve" else self.mis[fig["key"]]
            for slot in range(comp.get_num_materials()):
                comp.set_material(slot, mi)
            comp.set_custom_primitive_data_float(DISSOLVE_SLOT, float(progress))
            comp.set_custom_primitive_data_float(STYLE_SLOT, float(style))
            comp.set_visibility(bool(visible))
            base.set_custom_primitive_data_float(FADE_SLOT, float(progress) if material == "dissolve" or not visible
                                                 else 0.0)

    def start(self):
        os.makedirs(FRAMES, exist_ok=True)
        u.EditorLoadingAndSavingUtils.new_blank_map(False)
        self.world = u.EditorLevelLibrary.get_editor_world()
        sub = u.get_editor_subsystem(u.EditorActorSubsystem)
        for cmd in ("t.MaxFPS 30", "r.DefaultFeature.AutoExposure 0", "r.EyeAdaptationQuality 0"):
            u.SystemLibrary.execute_console_command(self.world, cmd)
        key = sub.spawn_actor_from_class(u.DirectionalLight, u.Vector(0, 0, 500),
                                         u.Rotator(roll=0.0, pitch=-40.0, yaw=200.0))
        key.light_component.set_intensity(6.0)
        fill = sub.spawn_actor_from_class(u.PointLight, u.Vector(300, 150, 120), u.Rotator(0, 0, 0))
        fill.point_light_component.set_intensity(40.0)
        fill.point_light_component.set_attenuation_radius(2000.0)
        self.comps, self.bases, self.mis, self.dissolve_mis = [], [], {}, {}
        for i, fig in enumerate(ARGS["figures"]):
            y = -105.0 + 70.0 * i
            self.mis[fig["key"]] = load(fig["mi"])
            if ARGS.get("dissolve"):
                self.dissolve_mis[fig["key"]] = load(fig["dissolve_mi"])
            a = sub.spawn_actor_from_class(u.SkeletalMeshActor, u.Vector(0, y, 0), u.Rotator(0, 0, 0))
            comp = a.skeletal_mesh_component
            comp.set_skinned_asset_and_update(load(fig["mesh"]))
            comp.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
            a.set_actor_label("DE011 " + fig["key"])
            b = sub.spawn_actor_from_class(u.StaticMeshActor, u.Vector(0, y, 0), u.Rotator(0, 0, 0))
            base = b.static_mesh_component
            base.set_static_mesh(load(fig["base"]))
            base.set_material(0, load(fig["base_mi"]))
            base.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
            self.comps.append(comp)
            self.bases.append(base)
            self.report["figures"].append({k: fig[k] for k in fig})
        cam_loc = u.Vector(600, 0, 28)
        rot = u.MathLibrary.find_look_at_rotation(cam_loc, u.Vector(0, 0, 28))
        cam = sub.spawn_actor_from_class(u.SceneCapture2D, cam_loc, rot)
        self.target = u.TextureRenderTarget2D()
        self.target.set_editor_property("render_target_format", u.TextureRenderTargetFormat.RTF_RGBA8)
        self.target.set_editor_property("size_x", W)
        self.target.set_editor_property("size_y", H)
        self.cap = cam.capture_component2d
        self.cap.set_editor_property("texture_target", self.target)
        self.cap.set_editor_property("fov_angle", 30.0)
        self.cap.set_editor_property("capture_every_frame", False)
        self.cap.set_editor_property("capture_on_movement", False)
        pp = self.cap.get_editor_property("post_process_settings")
        pp.set_editor_property("override_auto_exposure_method", True)
        pp.set_editor_property("auto_exposure_method", u.AutoExposureMethod.AEM_MANUAL)
        pp.set_editor_property("override_auto_exposure_apply_physical_camera_exposure", True)
        pp.set_editor_property("auto_exposure_apply_physical_camera_exposure", False)
        pp.set_editor_property("override_auto_exposure_bias", True)
        pp.set_editor_property("auto_exposure_bias", 0.0)
        pp.set_editor_property("override_dynamic_global_illumination_method", True)
        pp.set_editor_property("dynamic_global_illumination_method", u.DynamicGlobalIlluminationMethod.NONE)
        pp.set_editor_property("override_reflection_method", True)
        pp.set_editor_property("reflection_method", u.ReflectionMethod.NONE)
        self.cap.set_editor_property("post_process_settings", pp)
        self.plan = PLAN + (DISSOLVE_PLAN if ARGS.get("dissolve") else [])
        self.step = 0
        self.phase = "set"
        self.wait_until = 240
        u.EditorPythonScripting.set_keep_python_script_alive(True)
        self.handle = u.register_slate_post_tick_callback(self.tick)
        u.log("DE011_CAPTURE_WAITING")

    def tick(self, _dt):
        try:
            self.frame += 1
            if self.frame < self.wait_until:
                return
            if self.step >= len(self.plan):
                u.log("DE011_CAPTURE_COMPLETE")
                self.finish()
                return
            name, state = self.plan[self.step]
            if self.phase == "set":
                self.apply_state(state)
                flags = [u.EngineShowFlagsSetting(show_flag_name=n, enabled=False)
                         for n in ("TemporalAA", "Bloom", "MotionBlur", "LensFlares", "EyeAdaptation")]
                if not state[4]:
                    flags.append(u.EngineShowFlagsSetting(show_flag_name="Lighting", enabled=False))
                self.cap.set_editor_property("show_flag_settings", flags)
                self.cap.set_editor_property("capture_source", u.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
                u.AutomationLibrary.finish_loading_before_screenshot()
                self.phase = "capture"
                self.wait_until = self.frame + 30
            elif self.phase == "capture":
                self.cap.capture_scene()
                self.phase = "export"
                self.wait_until = self.frame + 6
            else:
                fname = "%s-%s.png" % (ARGS["tag"], name)
                path = os.path.join(FRAMES, fname)
                if os.path.exists(path):
                    os.remove(path)
                u.RenderingLibrary.export_render_target(self.world, self.target, FRAMES, fname)
                if not os.path.isfile(path) or os.path.getsize(path) == 0:
                    raise RuntimeError("capture not written: " + path)
                self.report["frames"][name] = path.replace("\\", "/")
                self.step += 1
                self.phase = "set"
                self.wait_until = self.frame + 2
        except Exception:  # noqa: BLE001 - reported to the host
            u.log_error("DE011_CAPTURE_FAILED\n" + traceback.format_exc())
            self.finish(traceback.format_exc())


JOB = Job()
try:
    JOB.start()
except Exception:  # noqa: BLE001
    u.log_error("DE011_CAPTURE_FAILED\n" + traceback.format_exc())
    JOB.finish(traceback.format_exc())
