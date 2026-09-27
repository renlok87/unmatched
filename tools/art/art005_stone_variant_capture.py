"""Capture stone variants with the same K1 camera and settings as ART005C."""

import os
from pathlib import Path
import traceback

import unreal as u


ROOT = Path(__file__).resolve().parents[2]
VARIANT = os.environ.get("ART005_STONE_VARIANT", "v3")
if VARIANT not in ("v3", "v4", "woodUV", "woodPaint", "corner", "forestProbe", "paddockProbe"):
    raise RuntimeError(f"Unsupported ART005_STONE_VARIANT: {VARIANT}")
SUFFIX = {"v3": "D", "v4": "E", "woodUV": "F", "woodPaint": "G", "corner": "H",
          "forestProbe": "I", "paddockProbe": "I"}[VARIANT]
VIEW = os.environ.get("ART005_CAPTURE_VIEW", "k1")
if VIEW not in ("k1", "wood-detail"):
    raise RuntimeError(f"Unsupported ART005_CAPTURE_VIEW: {VIEW}")
OUTPUT = ROOT / f"docs/game-design/evidence/ART-005/stone-{VARIANT}-combined-{VIEW}-editor-2026-09-28.png"
LEVEL = {
    "v3": "/Game/ArtTests/ART005D/L_ART005D_StoneV3Review",
    "v4": "/Game/ArtTests/ART005E/L_ART005E_StoneV4Review",
    "woodUV": "/Game/ArtTests/ART005F/L_ART005F_WoodUVReview",
    "woodPaint": "/Game/ArtTests/ART005G/L_ART005G_WoodPaintReview",
    "corner": "/Game/ArtTests/ART005H/L_ART005H_CornerReview",
    "forestProbe": "/Game/ArtTests/ART005I/L_ART005I_ForestReferenceLight",
    "paddockProbe": "/Game/ArtTests/ART005I/L_ART005I_PaddockReferenceLight",
}[VARIANT]


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
            elif self.frame == 96:
                u.RenderingLibrary.export_render_target(self.world, self.target, str(OUTPUT.parent), OUTPUT.name)
                if not OUTPUT.is_file() or OUTPUT.stat().st_size == 0:
                    raise RuntimeError("ART005 stone capture not written: " + str(OUTPUT))
                u.log(f"ART005_STONE_VARIANT_CAPTURE_COMPLETE {VARIANT} " + str(OUTPUT))
                self.finish()
        except Exception:
            u.log_error("ART005_STONE_VARIANT_CAPTURE_FAILED\n" + traceback.format_exc())
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
        if VIEW == "k1":
            camera_location = u.Vector(0, -1032.4, 1474.4)
            camera_target = u.Vector(0, 0, 0)
        else:
            camera_target = u.Vector(-250, -300, 0)
            camera_location = camera_target + u.Vector(0, -1032.4, 1474.4) * 0.35
        rotation = u.MathLibrary.find_look_at_rotation(camera_location, camera_target)
        actor = u.EditorLevelLibrary.spawn_actor_from_class(u.SceneCapture2D, camera_location, rotation)
        actor.set_actor_label(f"ART005{SUFFIX} Temporary Capture K1")
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
        u.log(f"ART005_STONE_VARIANT_CAPTURE_WAITING_FOR_RENDER_RESOURCES {VARIANT}")


JOB = CaptureJob()
JOB.start()
