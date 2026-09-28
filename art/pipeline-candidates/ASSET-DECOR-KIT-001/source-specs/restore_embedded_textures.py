"""Restore source/textures/* of a Tripo source spec from the images embedded in its GLB files.

The extracted textures are byte copies of the GLB images (no re-encoding), so they are not kept in git
(~13.5 MB of duplicates). Each spec file entry with origin "extracted from the GLB without re-encoding"
is rebuilt from the GLB image of the same name and checked against its expected_sha256.

  python art/pipeline-candidates/ASSET-DECOR-KIT-001/source-specs/restore_embedded_textures.py \
      [art/pipeline-candidates/ASSET-DECOR-KIT-001/source-specs/tripo-3f7a258f.json]

Existing files with the expected hash are left untouched (read-only originals stay read-only).
Exit code 1 if an image is missing in the GLBs or a hash differs.
"""
import hashlib
import json
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ORIGIN = "extracted from the GLB without re-encoding"


def glb_images(path):
    data = path.read_bytes()
    magic, _version, total = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF" or total != len(data):
        raise SystemExit("not a complete GLB: %s" % path)
    jlen = struct.unpack_from("<I", data, 12)[0]
    doc = json.loads(data[20:20 + jlen])
    bin_start = 20 + jlen + 8
    out = {}
    for image in doc.get("images", []):
        view = doc["bufferViews"][image["bufferView"]]
        start = bin_start + view.get("byteOffset", 0)
        out[image["name"]] = data[start:start + view["byteLength"]]
    return out


def main():
    spec_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("tripo-3f7a258f.json")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    embedded = {}
    for entry in spec["files"]:
        if entry["path"].endswith(".glb"):
            embedded.update(glb_images(REPO / entry["path"]))
    failed = 0
    for entry in spec["files"]:
        if entry.get("origin") != ORIGIN:
            continue
        target = REPO / entry["path"]
        blob = embedded.get(target.name)
        if blob is None:
            print("MISSING in GLBs: %s" % entry["path"])
            failed += 1
            continue
        digest = hashlib.sha256(blob).hexdigest()
        if digest != entry["expected_sha256"]:
            print("HASH MISMATCH: %s %s != %s" % (entry["path"], digest, entry["expected_sha256"]))
            failed += 1
            continue
        if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == digest:
            print("ok (present)  %s" % entry["path"])
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blob)
        print("restored      %s" % entry["path"])
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
