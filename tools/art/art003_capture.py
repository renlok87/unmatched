"""Capture an ART-003 K1 editor frame with six imported gray static probes."""

from pathlib import Path
import traceback

import unreal as u


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "blender" / "A01" / "preview" / "ue-art003-k1-gray.png"
LEVEL = "/Game/ArtTests/ART003/L_ART003_SilhouetteScale"


class CaptureJob:
    def __init__(self) -> None:
        self.frame = 0
        self.handle = None

    def finish(self) -> None:
        if self.handle is not None:
            u.unregister_slate_post_tick_callback(self.handle)
            self.handle = None
        u.EditorPythonScripting.set_keep_python_script_alive(False)

    def tick(self, _delta_seconds: float) -> None:
        try:
            self.frame += 1
            if self.frame == 90:
                self.component.capture_scene()
                u.log("ART003_CAPTURE_FRAME 90")
            elif self.frame == 96:
                u.RenderingLibrary.export_render_target(
                    self.world, self.target, str(OUTPUT.parent), OUTPUT.name
                )
                if not OUTPUT.is_file() or OUTPUT.stat().st_size == 0:
                    raise RuntimeError(f"ART003 capture was not written: {OUTPUT}")
                u.log("ART003_CAPTURE_COMPLETE " + str(OUTPUT))
                self.finish()
        except Exception:
            u.log_error("ART003_CAPTURE_FAILED\n" + traceback.format_exc())
            self.finish()

    def start(self) -> None:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.unlink(missing_ok=True)
        levels = u.get_editor_subsystem(u.LevelEditorSubsystem)
        if not levels.load_level(LEVEL):
            raise RuntimeError(f"Cannot load {LEVEL}")
        self.world = u.EditorLevelLibrary.get_editor_world()
        u.SystemLibrary.execute_console_command(self.world, "t.MaxFPS 30")
        u.SystemLibrary.execute_console_command(self.world, "r.DefaultFeature.AutoExposure 0")
        u.SystemLibrary.execute_console_command(self.world, "r.EyeAdaptationQuality 0")
        for actor in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors():
            if actor.get_actor_label() == "ART003 Neutral Capture Fill":
                actor.light_component.set_editor_property("intensity", 700.0)
        camera_location = u.Vector(0, -1032.4, 1474.4)
        rotation = u.MathLibrary.find_look_at_rotation(camera_location, u.Vector(0, 0, 0))
        actor = u.EditorLevelLibrary.spawn_actor_from_class(u.SceneCapture2D, camera_location, rotation)
        actor.set_actor_label("ART003 Temporary Capture K1")
        self.target = u.TextureRenderTarget2D()
        self.target.set_editor_property("render_target_format", u.TextureRenderTargetFormat.RTF_RGBA8)
        self.target.set_editor_property("size_x", 1920)
        self.target.set_editor_property("size_y", 1080)
        self.component = actor.capture_component2d
        self.component.set_editor_property("texture_target", self.target)
        self.component.set_editor_property("capture_source", u.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
        self.component.set_editor_property("fov_angle", 35.0)
        self.component.set_editor_property("capture_every_frame", False)
        self.component.set_editor_property("capture_on_movement", False)
        u.EditorPythonScripting.set_keep_python_script_alive(True)
        self.handle = u.register_slate_post_tick_callback(self.tick)
        u.log("ART003_CAPTURE_WAITING_FOR_RENDER_RESOURCES")


JOB = CaptureJob()
JOB.start()
