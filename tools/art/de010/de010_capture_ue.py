"""UE editor task (UnrealEditor-Cmd -ExecutePythonScript, -RenderOffScreen), run by tools/art/de010/de010.py capture.

ARGS: JSON file named by the environment variable DE010_ARGS:
  {"out": <report.json>, "frames": <dir>, "tag": "before"|"after", "figures": [{"key", "mesh", "mi", "lunge"}],
   "contact": bool}
A blank map in memory (nothing is saved): the four v2 figures (body MI P1) in their reference pose side by side,
a key and a fill light, fixed manual exposure, no Lumen GI / reflections, no temporal AA, no bloom (one capture is
a deterministic frame); a SceneCapture2D takes
  * <tag>-final-hit0[-b].png  final colour (LDR), CPD_HitTint 0 (twice: the noise floor of one session)
  * <tag>-base-hit0.png       unlit (show flag Lighting off: base colour + emissive), CPD_HitTint 0
  * <tag>-final-hit1.png / <tag>-base-hit1.png   CPD_HitTint 1 (before the material has the slot: must equal hit0)
  * <tag>-final-contact.png   (contact: true) every figure posed at the "Contact" notify of its LungeAttack
Then the editor quits. Errors are written to the report as {"error", "traceback"}.
"""
import json
import os
import traceback

import unreal as u

ARGS = json.load(open(os.environ["DE010_ARGS"], encoding="utf-8"))
OUT = ARGS["out"]
FRAMES = ARGS["frames"]
HIT_SLOT = 12
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


def contact_time(seq):
    for ev in u.AnimationLibrary.get_animation_notify_events(seq):
        if str(ev.get_editor_property("notify_name")) == "Contact":
            return float(u.AnimationLibrary.get_anim_notify_event_trigger_time(ev))
    return None


class Job:
    def __init__(self):
        self.frame = 0
        self.handle = None
        self.shots = []
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

    def set_hit(self, value):
        for comp in self.comps:
            comp.set_custom_primitive_data_float(HIT_SLOT, float(value))

    def pose_contact(self):
        for comp, fig in zip(self.comps, ARGS["figures"]):
            seq = load(fig["lunge"])
            t = contact_time(seq)
            if t is None:
                raise RuntimeError("no Contact notify in %s" % fig["lunge"])
            comp.set_update_animation_in_editor(True)
            comp.override_animation_data(seq, False, False, t, 0.0)
            self.report["figures_contact"] = self.report.get("figures_contact", {})
            self.report["figures_contact"][fig["key"]] = round(t, 5)

    def start(self):
        os.makedirs(FRAMES, exist_ok=True)
        world = u.EditorLoadingAndSavingUtils.new_blank_map(False)
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
        self.comps = []
        for i, fig in enumerate(ARGS["figures"]):
            y = -105.0 + 70.0 * i
            a = sub.spawn_actor_from_class(u.SkeletalMeshActor, u.Vector(0, y, 0), u.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
            comp = a.skeletal_mesh_component
            comp.set_skinned_asset_and_update(load(fig["mesh"]))
            comp.set_material(0, load(fig["mi"]))
            comp.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
            a.set_actor_label("DE010 " + fig["key"])
            self.comps.append(comp)
            self.report["figures"].append({"key": fig["key"], "mesh": fig["mesh"], "mi": fig["mi"], "y": y,
                                           "materials": [m.get_path_name() if m else None for m in comp.get_materials()]})
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
        final, base = "lit", "unlit"
        # (frame to capture on, state, source, file); the state is set a few frames before the capture
        plan = [("hit0", final, "final-hit0"), ("hit0", final, "final-hit0-b"), ("hit0", base, "base-hit0"),
                ("hit1", final, "final-hit1"), ("hit1", base, "base-hit1")]
        if ARGS.get("contact"):
            plan.append(("contact", final, "final-contact"))
        self.plan = plan
        self.step = 0
        self.wait_until = 240
        u.EditorPythonScripting.set_keep_python_script_alive(True)
        self.handle = u.register_slate_post_tick_callback(self.tick)
        u.log("DE010_CAPTURE_WAITING")

    def tick(self, _dt):
        try:
            self.frame += 1
            if self.frame < self.wait_until:
                return
            if self.step >= len(self.plan):
                u.log("DE010_CAPTURE_COMPLETE")
                self.finish()
                return
            state, source, name = self.plan[self.step]
            phase = getattr(self, "phase", "set")
            if phase == "set":
                if state == "hit0":
                    self.set_hit(0.0)
                elif state == "hit1":
                    self.set_hit(1.0)
                else:
                    self.set_hit(0.0)
                    self.pose_contact()
                flags = [u.EngineShowFlagsSetting(show_flag_name=n, enabled=False)
                         for n in ("TemporalAA", "Bloom", "MotionBlur", "LensFlares", "EyeAdaptation")]
                if source == "unlit":
                    flags.append(u.EngineShowFlagsSetting(show_flag_name="Lighting", enabled=False))
                self.cap.set_editor_property("show_flag_settings", flags)
                self.cap.set_editor_property("capture_source", u.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
                u.AutomationLibrary.finish_loading_before_screenshot()
                self.phase = "capture"
                self.wait_until = self.frame + 30
            elif phase == "capture":
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
            u.log_error("DE010_CAPTURE_FAILED\n" + traceback.format_exc())
            self.finish(traceback.format_exc())


JOB = Job()
try:
    JOB.start()
except Exception:  # noqa: BLE001
    u.log_error("DE010_CAPTURE_FAILED\n" + traceback.format_exc())
    JOB.finish(traceback.format_exc())
