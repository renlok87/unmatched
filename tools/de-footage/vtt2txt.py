"""YouTube auto-caption VTT -> clean timestamped transcript, one file per chapter.

usage: python tools/de-footage/vtt2txt.py SRC.vtt
writes C:/tmp/de-footage/work/transcript/<chapter>.txt and all.txt
"""
import json
import os
import re
import sys

WORK = "C:/tmp/de-footage/work/transcript"
CHAPTERS = json.load(open(os.path.join(os.path.dirname(__file__), "chapters.json"), encoding="utf-8"))
TS = re.compile(r"(\d+):(\d+):(\d+)\.(\d+) --> ")


def sec(h, m, s, ms):
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def hms(t):
    t = int(t)
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}"


def parse(path):
    lines = open(path, encoding="utf-8").read().splitlines()
    out = []  # (t, text)
    seen_tail = ""
    i = 0
    while i < len(lines):
        m = TS.match(lines[i])
        if not m:
            i += 1
            continue
        t = sec(*m.groups())
        i += 1
        body = []
        while i < len(lines) and lines[i].strip():
            body.append(lines[i])
            i += 1
        # rolling captions: the line carrying <c> word tags is the new text
        new = [b for b in body if "<c>" in b or re.search(r"<\d+:\d+", b)]
        if not new:
            continue
        text = re.sub(r"<[^>]+>", "", " ".join(new)).strip()
        text = re.sub(r"\s+", " ", text)
        if text and text != seen_tail:
            out.append((t, text))
            seen_tail = text
    return out


def main(src):
    os.makedirs(WORK, exist_ok=True)
    rows = parse(src)
    # merge into ~15 s paragraphs
    paras = []
    for t, text in rows:
        if paras and t - paras[-1][0] < 15:
            paras[-1][1].append(text)
        else:
            paras.append((t, [text]))
    bounds = [c["start"] for c in CHAPTERS] + [10 ** 9]
    files = {c["id"]: [] for c in CHAPTERS}
    allf = []
    for t, texts in paras:
        line = f"[{hms(t)} | {t:.0f}s] " + " ".join(texts)
        allf.append(line)
        for k, c in enumerate(CHAPTERS):
            if bounds[k] <= t < bounds[k + 1]:
                files[c["id"]].append(line)
    for cid, ls in files.items():
        open(f"{WORK}/{cid}.txt", "w", encoding="utf-8").write("\n".join(ls) + "\n")
    open(f"{WORK}/all.txt", "w", encoding="utf-8").write("\n".join(allf) + "\n")
    print("caption lines", len(rows), "paragraphs", len(paras),
          {cid: len(v) for cid, v in files.items()})


if __name__ == "__main__":
    main(sys.argv[1])
