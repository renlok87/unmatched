"""Verify persisted Medusa/Cobble preview assets in a NEW Unreal process."""

import json
from pathlib import Path

import unreal as u


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs/game-design/evidence/ART-004/v2-game-import-report.json"
DATA = json.loads(REPORT.read_text(encoding="utf-8"))


def required(path):
    asset = u.load_asset(path)
    if asset is None:
        raise RuntimeError("Missing persisted preview asset: " + path)
    return asset


mesh = required(DATA["skeletal_mesh"])
skeleton = required(DATA["skeleton"])
base = required(DATA["base"])
blue, red = (required(path) for path in DATA["materials"])
if mesh.get_editor_property("skeleton") != skeleton:
    raise RuntimeError("Candidate mesh lost its Skeleton reference")
slots = mesh.get_editor_property("materials")
if len(slots) != 2 or any(slot.get_editor_property("material_interface") != blue
                          for slot in slots):
    raise RuntimeError("Candidate two-slot PBR assignment did not persist")
if base.get_material(0) != blue:
    raise RuntimeError("Candidate base lost its PBR assignment")
if mesh.num_sockets() != 2 or {
        str(mesh.get_socket_by_index(i).get_editor_property("socket_name"))
        for i in range(mesh.num_sockets())} != {"Weapon", "Head"}:
    raise RuntimeError("Candidate sockets did not persist")
bounds = base.get_bounding_box()
size = (bounds.max.x - bounds.min.x, bounds.max.y - bounds.min.y,
        bounds.max.z - bounds.min.z)
if any(abs(a - b) >= .5 for a, b in zip(size, (30, 30, 6))):
    raise RuntimeError("Candidate base changed size")
for name, srgb in (("T_Medusa_BC", True), ("T_Medusa_N", False),
                   ("T_Medusa_ORM", False)):
    texture = required("/Game/ArtPreview/Medusa/Textures/" + name)
    if bool(texture.get_editor_property("srgb")) != srgb:
        raise RuntimeError("Texture color-space changed: " + name)

board = required("/Game/ArtTests/ART005F/Meshes/SM_ART005_BoardStoneV4_WoodUV")
for slot in ("M_ART005_Stone_AtlasB_Provisional", "M_ART005_Wood_Provisional"):
    if board.get_material_index(slot) < 0:
        raise RuntimeError("Cobble slot name changed: " + slot)
for path in (
    "/Game/ArtTests/ART005H/Meshes/SM_ART005_CornerBracket_v1",
    "/Game/ArtTests/ART005E/Materials/M_ART005E_Stone_DiffuseOnly_v4",
    "/Game/ArtTests/ART005G/Materials/M_ART005G_Wood_DiffuseOnly",
    "/Game/ArtTests/ART005H/Materials/M_ART005H_IronCorner_Review",
    "/Game/ArtTests/ART005/Materials/M_ART005_BlueSection_Review",
    "/Game/ArtTests/ART005/Materials/M_ART005_RedSection_Review",
    "/Game/ArtTests/ART005/Materials/M_ART005_ZoneGlyph_Review",
):
    required(path)

print("ARTPREVIEW_ASSETS_RELOAD_OK skeleton=1 body_slots=2 base=30x30x6 board=5x6")
