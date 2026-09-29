"""bpy-free helpers of the H2 bake (used by the Blender stages, the system-python stages and the driver)."""

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def r(value, nd=6):
    return round(float(value), nd)


def rv(vec, nd=6):
    return [r(c, nd) for c in vec]


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, data):
    """Deterministic JSON (sorted keys, LF, UTF-8)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"))


def rel(path):
    """Repo-relative POSIX path (reports never carry host paths)."""
    p = Path(path).resolve()
    try:
        return p.relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return p.as_posix()


def repo_path(relpath):
    return (REPO / relpath).resolve()


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PNG_METADATA_CHUNKS = (b"tEXt", b"zTXt", b"iTXt", b"tIME")


def strip_png_metadata(path):
    """Drop the text/time chunks of a PNG in place (Blender render stamps: File = the open .blend path, Date, Time,
    RenderTime...). Pixel chunks are copied byte for byte, so the image is unchanged. Returns the dropped chunk types."""
    path = Path(path)
    data = path.read_bytes()
    if data[:8] != PNG_SIGNATURE:
        raise ValueError("%s: not a PNG" % path)
    out = [data[:8]]
    dropped = []
    i = 8
    while i < len(data):
        n = int.from_bytes(data[i:i + 4], "big")
        kind = data[i + 4:i + 8]
        chunk = data[i:i + 12 + n]
        if len(chunk) != 12 + n:
            raise ValueError("%s: truncated chunk at %d" % (path, i))
        if kind in PNG_METADATA_CHUNKS:
            dropped.append(kind.decode("ascii"))
        else:
            out.append(chunk)
        i += 12 + n
    if dropped:
        path.write_bytes(b"".join(out))
    return dropped


def host_path_hits(path):
    """Absolute host paths inside a binary/text file: the repo root and the user home in both slash styles, plus any
    drive-letter path into a Users folder. Empty list = clean."""
    data = Path(path).read_bytes()
    needles = set()
    for root in (REPO.resolve(), Path.home()):
        s = str(root)
        needles.update({s, s.replace("\\", "/"), s.replace("/", "\\")})
    hits = sorted(n for n in needles if n.encode("utf-8") in data)
    for m in re.finditer(rb"[A-Za-z]:[\\/]+Users[\\/]", data):
        hits.append("offset %d: %s" % (m.start(), data[m.start():m.start() + 40].decode("latin-1")))
    return hits


class Profile:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.data = load_json(self.path)
        self.run_dir = repo_path(self.data["run_dir"])
        self.work = self.run_dir / "work"
        self.reports = self.run_dir / "reports"
        self.textures = self.run_dir / "textures"
        self.export = self.run_dir / "export"
        self.preview = self.run_dir / "preview"

    def __getitem__(self, key):
        return self.data[key]

    def get(self, key, default=None):
        return self.data.get(key, default)

    def part_names(self, obj_key=None):
        parts = self.data["parts"]
        names = sorted(parts, key=lambda n: int(n.rsplit("_", 1)[1]))
        if obj_key is None:
            return names
        return [n for n in self.data["objects"][obj_key]["parts"]]

    def object_of_part(self, part):
        return self.data["parts"][part]["object"]


def part_index(name):
    return int(name.rsplit("_", 1)[1])


def check(checks, name, passed, measured=None, expected=None, note=None):
    item = {"passed": bool(passed), "measured": measured}
    if expected is not None:
        item["expected"] = expected
    if note:
        item["note"] = note
    checks[name] = item
    return bool(passed)
