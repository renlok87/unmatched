"""Capture the ART-001 Unreal evidence frame after render resources are ready."""

from pathlib import Path
import traceback

import unreal as u


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "blender" / "_shared" / "check_set" / "preview"
OVERVIEW_FILE = OUTPUT / "ue-art001-overview.png"
NORMAL_FILE = OUTPUT / "ue-art001-normal-probe.png"
LEVEL = "/Game/ArtTests/ART001/L_ART001_Check"
OVERVIEW_CAPTURE_FRAME = 90
OVERVIEW_EXPORT_FRAME = 96
NORMAL_SETUP_FRAME = 100
NORMAL_CAPTURE_FRAME = 120
NORMAL_EXPORT_FRAME = 126


class CaptureJob:
    def __init__(self) -> None:
        self.frame = 0
        self.handle = None
        self.world = None
        self.target = None
        self.component = None
        self.capture_actor = None
        self.temporary_actors = []

    def spawn_mesh(self, mesh, location, scale):
        actor = u.EditorLevelLibrary.spawn_actor_from_class(u.StaticMeshActor, location)
        actor.set_actor_location(location, False, False)
        actor.static_mesh_component.set_static_mesh(mesh)
        actor.set_actor_scale3d(scale)
        self.temporary_actors.append(actor)
        return actor

    def setup(self) -> None:
        OUTPUT.mkdir(parents=True, exist_ok=True)
        OVERVIEW_FILE.unlink(missing_ok=True)
        NORMAL_FILE.unlink(missing_ok=True)

        levels = u.get_editor_subsystem(u.LevelEditorSubsystem)
        if not levels.load_level(LEVEL):
            raise RuntimeError(f"Could not load {LEVEL}")
        self.world = u.EditorLevelLibrary.get_editor_world()

        plane = u.load_asset("/Engine/BasicShapes/Plane.Plane")
        cube = u.load_asset("/Engine/BasicShapes/Cube.Cube")
        floor = self.spawn_mesh(
            plane, u.Vector(100, 0, -1), u.Vector(8.5, 4.0, 1.0)
        )
        floor.set_actor_label("ART001 Capture Floor")

        for x in range(-300, 501, 100):
            line = self.spawn_mesh(
                cube, u.Vector(x, 0, 0), u.Vector(0.008, 4.0, 0.008)
            )
            line.set_actor_label(f"ART001 Grid X {x}")
        for y in range(-200, 201, 100):
            line = self.spawn_mesh(
                cube, u.Vector(100, y, 0), u.Vector(8.5, 0.008, 0.008)
            )
            line.set_actor_label(f"ART001 Grid Y {y}")

        point = u.EditorLevelLibrary.spawn_actor_from_class(
            u.PointLight, u.Vector(100, -100, 500)
        )
        point.set_actor_label("ART001 Capture Fill")
        point.light_component.set_editor_property("intensity", 3000.0)
        point.light_component.set_editor_property("attenuation_radius", 1800.0)
        point.light_component.set_editor_property("cast_shadows", False)
        point.light_component.set_editor_property(
            "mobility", u.ComponentMobility.MOVABLE
        )
        self.temporary_actors.append(point)

        camera_location = u.Vector(100, -750, 450)
        camera_target = u.Vector(100, 0, 35)
        camera_rotation = u.MathLibrary.find_look_at_rotation(
            camera_location, camera_target
        )
        capture = u.EditorLevelLibrary.spawn_actor_from_class(
            u.SceneCapture2D, camera_location, camera_rotation
        )
        capture.set_actor_label("ART001 Evidence Camera")
        capture.set_actor_location(camera_location, False, False)
        capture.set_actor_rotation(camera_rotation, False)
        self.temporary_actors.append(capture)
        self.capture_actor = capture

        self.target = u.TextureRenderTarget2D()
        self.target.set_editor_property(
            "render_target_format", u.TextureRenderTargetFormat.RTF_RGBA8
        )
        self.target.set_editor_property("size_x", 1600)
        self.target.set_editor_property("size_y", 900)
        self.component = capture.capture_component2d
        self.component.set_editor_property("texture_target", self.target)
        self.component.set_editor_property(
            "capture_source", u.SceneCaptureSource.SCS_FINAL_COLOR_LDR
        )
        self.component.set_editor_property("fov_angle", 45.0)
        self.component.set_editor_property("capture_every_frame", False)
        self.component.set_editor_property("capture_on_movement", False)

    def finish(self) -> None:
        if self.handle is not None:
            u.unregister_slate_post_tick_callback(self.handle)
            self.handle = None
        u.EditorPythonScripting.set_keep_python_script_alive(False)

    def fail(self) -> None:
        u.log_error("ART001_CAPTURE_FAILED\n" + traceback.format_exc())
        self.finish()

    def tick(self, _delta_seconds: float) -> None:
        try:
            self.frame += 1
            if self.frame == OVERVIEW_CAPTURE_FRAME:
                self.component.capture_scene()
                u.log(f"ART001_OVERVIEW_CAPTURE_FRAME {self.frame}")
            elif self.frame == OVERVIEW_EXPORT_FRAME:
                u.RenderingLibrary.export_render_target(
                    self.world, self.target, str(OUTPUT), OVERVIEW_FILE.name
                )
                if not OVERVIEW_FILE.exists() or OVERVIEW_FILE.stat().st_size == 0:
                    raise RuntimeError(
                        f"Overview capture was not written: {OVERVIEW_FILE}"
                    )
            elif self.frame == NORMAL_SETUP_FRAME:
                camera_location = u.Vector(260, -120, 90)
                camera_target = u.Vector(260, 0, 5)
                camera_rotation = u.MathLibrary.find_look_at_rotation(
                    camera_location, camera_target
                )
                self.capture_actor.set_actor_location(camera_location, False, False)
                self.capture_actor.set_actor_rotation(camera_rotation, False)
                self.component.set_editor_property("fov_angle", 30.0)
                self.component.set_editor_property(
                    "capture_source", u.SceneCaptureSource.SCS_NORMAL
                )
            elif self.frame == NORMAL_CAPTURE_FRAME:
                self.component.capture_scene()
                u.log(f"ART001_NORMAL_CAPTURE_FRAME {self.frame}")
            elif self.frame == NORMAL_EXPORT_FRAME:
                u.RenderingLibrary.export_render_target(
                    self.world, self.target, str(OUTPUT), NORMAL_FILE.name
                )
                if not NORMAL_FILE.exists() or NORMAL_FILE.stat().st_size == 0:
                    raise RuntimeError(
                        f"Normal-probe capture was not written: {NORMAL_FILE}"
                    )
                u.log(
                    f"ART001_CAPTURE_COMPLETE {OVERVIEW_FILE}; {NORMAL_FILE}"
                )
                self.finish()
        except Exception:
            self.fail()

    def start(self) -> None:
        self.setup()
        u.EditorPythonScripting.set_keep_python_script_alive(True)
        self.handle = u.register_slate_post_tick_callback(self.tick)
        u.log("ART001_CAPTURE_WAITING_FOR_RENDER_RESOURCES")


JOB = CaptureJob()
JOB.start()
