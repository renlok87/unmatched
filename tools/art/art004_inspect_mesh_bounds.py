"""Inspect persisted Medusa asset bounds without altering the UE project."""
import unreal as u

for path in (
    "/Game/ArtPreview/Medusa/Meshes/SK_Medusa_FaceNeck_v2Candidate",
    "/Game/ArtPreview/Medusa/Meshes/SM_Medusa_Base_v2Candidate",
):
    asset = u.load_asset(path)
    if asset is None:
        raise RuntimeError("Missing " + path)
    print("ART004_BOUNDS asset=" + path)
    for key in ("imported_bounds", "extended_bounds", "positive_bounds_extension",
                "negative_bounds_extension"):
        try:
            print("ART004_BOUNDS " + key + "=" + str(asset.get_editor_property(key)))
        except Exception:
            pass
    for key in ("get_bounds", "get_bounding_box", "get_bounding_box_size"):
        method = getattr(asset, key, None)
        if method:
            try:
                print("ART004_BOUNDS " + key + "=" + str(method()))
            except Exception as exc:
                print("ART004_BOUNDS " + key + " failed=" + str(exc))
