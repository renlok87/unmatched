"""Read a remote zip archive through HTTP range requests: list its members and extract only chosen files.

The Sonniss GDC bundle ships as multi-gigabyte zip parts; we need a few dozen ambience and foley files out of them.
Reading the central directory and the chosen members with `Range` requests avoids downloading whole parts.

    python tools/audio/remote_zip.py list <url> [--out catalog.tsv]
    python tools/audio/remote_zip.py get <url> <member> [<member> ...] --dest <dir>

The audio itself never goes into git (00-AUDIO-BRIEF §5); the destination is under C:/tmp/audio-src/.
"""
from __future__ import annotations

import argparse
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
BLOCK = 1 << 20  # read-ahead block for the central directory and member data


class HttpRangeFile(io.RawIOBase):
    """A read-only seekable file over HTTP range requests with a small block cache."""

    def __init__(self, url: str, referer: str = "") -> None:
        self.url = url
        self.headers = {"User-Agent": UA}
        if referer:
            self.headers["Referer"] = referer
        req = urllib.request.Request(url, method="HEAD", headers=self.headers)
        with urllib.request.urlopen(req) as resp:
            self.size = int(resp.headers["Content-Length"])
            if resp.headers.get("Accept-Ranges", "") != "bytes":
                raise OSError(f"{url}: server does not accept byte ranges")
        self.pos = 0
        self.cache: dict[int, bytes] = {}
        self.fetched = 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.pos

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self.pos, io.SEEK_END: self.size}[whence]
        self.pos = max(0, base + offset)
        return self.pos

    def _block(self, index: int) -> bytes:
        if index not in self.cache:
            start = index * BLOCK
            end = min(self.size, start + BLOCK) - 1
            req = urllib.request.Request(self.url, headers={**self.headers, "Range": f"bytes={start}-{end}"})
            with urllib.request.urlopen(req) as resp:
                data = resp.read()
            self.fetched += len(data)
            if len(self.cache) > 64:  # keep memory bounded
                self.cache.pop(next(iter(self.cache)))
            self.cache[index] = data
        return self.cache[index]

    def read(self, n: int = -1) -> bytes:
        if n < 0:
            n = self.size - self.pos
        n = min(n, self.size - self.pos)
        out = bytearray()
        while n > 0:
            index, off = divmod(self.pos, BLOCK)
            chunk = self._block(index)[off: off + n]
            if not chunk:
                break
            out += chunk
            self.pos += len(chunk)
            n -= len(chunk)
        return bytes(out)

    def readinto(self, b) -> int:
        data = self.read(len(b))
        b[: len(data)] = data
        return len(data)


def open_zip(url: str, referer: str) -> tuple[zipfile.ZipFile, HttpRangeFile]:
    fh = HttpRangeFile(url, referer)
    return zipfile.ZipFile(fh), fh


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    ls = sub.add_parser("list")
    ls.add_argument("url")
    ls.add_argument("--out")
    ls.add_argument("--referer", default="https://sonniss.com/gameaudiogdc")
    get = sub.add_parser("get")
    get.add_argument("url")
    get.add_argument("members", nargs="+")
    get.add_argument("--dest", required=True)
    get.add_argument("--referer", default="https://sonniss.com/gameaudiogdc")
    args = ap.parse_args(argv)

    zf, fh = open_zip(args.url, args.referer)
    if args.cmd == "list":
        lines = [f"{i.file_size}\t{i.filename}" for i in zf.infolist() if not i.is_dir()]
        text = "\n".join(lines) + "\n"
        if args.out:
            Path(args.out).write_text(text, encoding="utf-8")
        else:
            sys.stdout.write(text)
        print(f"{len(lines)} members, {fh.fetched} bytes fetched", file=sys.stderr)
        return 0
    dest = Path(args.dest)
    for name in args.members:
        target = dest / Path(name).name
        target.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(name) as src, open(target, "wb") as dst:
            while chunk := src.read(BLOCK):
                dst.write(chunk)
        print(f"{target} {target.stat().st_size}", file=sys.stderr)
    print(f"{fh.fetched} bytes fetched", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
