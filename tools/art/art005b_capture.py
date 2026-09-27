"""Capture the B-atlas Cobble City editor probe at the ART-005 K1 camera."""

from pathlib import Path
import traceback

import unreal as u


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "blender/ASSET-BOARD-COBBLE-001/variants/B-atlas-v1/ue-art005b-k1-toned.png"
LEVEL = "/Game/ArtTests/ART005B/L_ART005_BAtlasProbe"


class CaptureJob:
    def __init__(self):
        self.frame = 0
        self.handle = None

    def finish(self):
        if self.handle is not None:
            u.unregister_slate_post_tick_callback(self.handle)
            self.handle = None
        u.EditorPythonScripting.set_keep_python_script_alive(False)

    def tick(self, _delta_seconds):
        try:
            self.frame += 1
            if self.frame == 90:
                self.component.capture_scene()
                u.log("ART005B_CAPTURE_FRAME 90")
            elif self.frame == 96:
                u.RenderingLibrary.export_render_target(self.world, self.target, str(OUTPUT.parent), OUTPUT.name)
                if not OUTPUT.is_file() or OUTPUT.stat().st_size == 0:
                    raise RuntimeError("ART005B capture not written: " + str(OUTPUT))
                u.log("ART005B_CAPTURE_COMPLETE " + str(OUTPUT))
                self.finish()
        except Exception:
            u.log_error("ART005B_CAPTURE_FAILED\n" + traceback.format_exc())
            self.finish()

    def start(self):
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        levels = u.get_editor_subsystem(u.LevelEditorSubsystem)
        if not levels.load_level(LEVEL):
            raise RuntimeError("Cannot load " + LEVEL)
        self.world = u.EditorLevelLibrary.get_editor_world()
        u.SystemLibrary.execute_console_command(self.world, "t.MaxFPS 30")
        u.SystemLibrary.execute_console_command(self.world, "r.DefaultFeature.AutoExposure 0")
        u.SystemLibrary.execute_console_command(self.world, "r.EyeAdaptationQuality 0")
        camera_location = u.Vector(0, -1032.4, 1474.4)
        rotation = u.MathLibrary.find_look_at_rotation(camera_location, u.Vector(0, 0, 0))
        actor = u.EditorLevelLibrary.spawn_actor_from_class(u.SceneCapture2D, camera_location, rotation)
        actor.set_actor_label("ART005B Temporary Capture K1")
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
        u.log("ART005B_CAPTURE_WAITING_FOR_RENDER_RESOURCES")


JOB = CaptureJob()
JOB.start()
