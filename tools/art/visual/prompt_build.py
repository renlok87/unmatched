"""Build the Codex (or SYNTX) task file of one task card: step 1 of the visual cycle (05-production-plan.md section 1.2).

  python tools/art/visual/prompt_build.py HB-07 [--out DIR] [--date YYYY-MM-DD] [--strict-inputs]

Reads the card row by id from docs/game-design/visual/06-tasks/*.csv and writes
docs/game-design/visual/06-tasks/prompts/<id>.codex.md (<id>.syntx.txt for T-SYNTX-* templates, ВР-PR09):
  - header: id, date, template id, set, card and template fingerprints, inputs named in 'references' with sha256;
  - the prompt: column 'prompt' without its template tag and without the preamble addressed to Claude
    (the text before "Task <id>"), with the shared blocks [[B-STYLE]], [[B-PALETTE-CORE]], [[B-FORBID]],
    [[B-PACKAGE]] expanded verbatim from 07-prompt-templates.md (sections 0.3 and 1.1; parsed from the markdown,
    never hardcoded) and {{set}} filled from the 'deliverable' column (art/imagegen/<set>-codex/).
Fails loudly (exit 2) on an unknown id, a card without a template tag, an unknown block, a set that cannot be
derived or contradicts the card, and on any {{...}} left unfilled.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from visual_common import (  # noqa: E402
    PROMPTS_REL,
    TEMPLATES_REL,
    VisualError,
    get_card,
    rel_or_abs,
    repo_root,
    sha256_file,
    sha256_tree,
    templates_text,
    utf8_console,
)

REQUIRED_BLOCKS = ("B-STYLE", "B-PALETTE-CORE", "B-FORBID", "B-PACKAGE")
BLOCK_REF_RE = re.compile(r"\[\[(B-[A-Z0-9][A-Z0-9-]*)\]\]")
BLOCK_LABEL_RE = re.compile(r"^\*\*\[\[(B-[A-Z0-9][A-Z0-9-]*)\]\]\*\*")
FENCE_RE = re.compile(r"^(`{3,})([A-Za-z0-9_-]*)\s*$")
VAR_RE = re.compile(r"\{\{\s*([^{}]*?)\s*\}\}")
TAG_RE = re.compile(r"^\s*\[(T-[A-Z0-9][A-Z0-9-]*)\]\s*")
SET_RE = re.compile(r"(?:art/imagegen|scraped-data/derived)/([A-Za-z0-9][A-Za-z0-9._-]*?)-codex/")
STATED_SET_RE = re.compile(r"(?:\{\{set\}\}\s*=|\bset\s*=|\bSet:)\s*([A-Za-z0-9][A-Za-z0-9._-]*[A-Za-z0-9])")
PATH_RE = re.compile(r"(?<![\w/.\-])((?:[A-Za-z]:/)?(?:[\w.\-]+/)+[\w.\-]*)")
BRACE_RE = re.compile(r"(?<!\{)\{([\w.\-]+(?:,[\w.\-]+)+)\}(?!\})")
STATED_HASH_RE = re.compile(r"\s*\(([0-9a-f]{8,64})\b")
FORBIDDEN_NAMES = ("Unmatched", "Digital Edition")  # ВР-PR07: never in generation prompts
READY_STATUS = "готово к работе"
MAX_TREE_FILES = 5000


# ---------------------------------------------------------------- 07 blocks

def parse_blocks(md_text: str) -> dict[str, str]:
    """Shared blocks of 07: a bold label **[[B-NAME]]** followed (before the next label or heading) by a fenced block.

    A label without a fence (07 section 0.3 announces B-PACKAGE and defines it in section 1.1) is skipped.
    The block text is the fence content, verbatim, lines joined by \\n. Two different definitions are an error.
    """
    lines = md_text.splitlines()
    blocks: dict[str, str] = {}
    i = 0
    while i < len(lines):
        m = BLOCK_LABEL_RE.match(lines[i])
        if not m:
            i += 1
            continue
        name = m.group(1)
        j = i + 1
        next_i = None
        while j < len(lines):
            line = lines[j]
            if line.startswith("#") or BLOCK_LABEL_RE.match(line):
                next_i = j  # label without a fence: continue the scan at this line
                break
            fm = FENCE_RE.match(line)
            if fm:
                fence = fm.group(1)
                k = j + 1
                buf = []
                while k < len(lines) and lines[k].strip() != fence:
                    buf.append(lines[k])
                    k += 1
                if k >= len(lines):
                    raise VisualError(f"{TEMPLATES_REL}: unterminated code fence of block [[{name}]]")
                text = "\n".join(buf)
                if name in blocks and blocks[name] != text:
                    raise VisualError(f"{TEMPLATES_REL}: block [[{name}]] is defined twice with different text")
                blocks[name] = text
                next_i = k + 1
                break
            j += 1
        i = next_i if next_i is not None else j
    missing = [b for b in REQUIRED_BLOCKS if b not in blocks]
    if missing:
        raise VisualError(f"{TEMPLATES_REL}: shared blocks not found: {', '.join('[[' + b + ']]' for b in missing)}")
    return blocks


# ---------------------------------------------------------------- card

def split_prompt(card: dict) -> tuple[str, str, str]:
    """(template id, preamble addressed to Claude, prompt body starting at 'Task <id>')."""
    cid = card["id"]
    text = (card.get("prompt") or "").replace("\r\n", "\n").strip()
    m = TAG_RE.match(text)
    if not m:
        raise VisualError(
            f"{cid}: column 'prompt' has no template tag [T-...] (tool {card.get('tool') or '-'!r}); "
            "this card is not a Codex or SYNTX generation card")
    rest = text[m.end():]
    t = re.search(r"(?:^|(?<=[\s.;)]))Task " + re.escape(cid) + r"\b", rest, re.M)
    if t:
        return m.group(1), rest[:t.start()].strip(), rest[t.start():].strip()
    return m.group(1), "", rest.strip()


def derive_set(card: dict, preamble: str, body: str) -> str:
    cid = card["id"]
    sets = sorted(set(SET_RE.findall(card.get("deliverable") or "")))
    if not sets:
        raise VisualError(f"{cid}: cannot derive {{{{set}}}}: column 'deliverable' names no art/imagegen/<set>-codex/ "
                          "or scraped-data/derived/<set>-codex/ folder")
    if len(sets) > 1:
        raise VisualError(f"{cid}: column 'deliverable' names several sets: {', '.join(sets)}")
    value = sets[0]
    stated = sorted(set(STATED_SET_RE.findall(preamble + "\n" + body)))
    wrong = [s for s in stated if s != value]
    if wrong:
        raise VisualError(f"{cid}: set {value!r} from 'deliverable' contradicts the card text (set = {', '.join(wrong)})")
    return value


def expand(body: str, blocks: dict[str, str], values: dict[str, str], cid: str) -> str:
    out = body
    for _ in range(4):  # a block may name another block; stop when stable
        unknown = sorted({n for n in BLOCK_REF_RE.findall(out) if n not in blocks})
        if unknown:
            raise VisualError(f"{cid}: unknown shared block(s) {', '.join('[[' + n + ']]' for n in unknown)} "
                              f"(not defined in {TEMPLATES_REL})")
        new = BLOCK_REF_RE.sub(lambda m: blocks[m.group(1)], out)
        if new == out:
            break
        out = new
    out = VAR_RE.sub(lambda m: values.get(m.group(1), m.group(0)), out)
    left = sorted(set(VAR_RE.findall(out)))
    if left:
        raise VisualError(f"{cid}: unfilled variable(s) {', '.join('{{' + v + '}}' for v in left)} in the prompt; "
                          "fill the card column 'prompt' (07 section 0.2: an empty field is never invented)")
    return out


# ---------------------------------------------------------------- inputs

def _expand_braces(text: str) -> str:
    """'boards/{a,b}.json' -> 'boards/a.json boards/b.json' (single braces with a comma only)."""
    def token(tok: str) -> str:
        m = BRACE_RE.search(tok)
        if not m:
            return tok
        head, tail = tok[:m.start()], tok[m.end():]
        return " ".join(token(head + alt + tail) for alt in m.group(1).split(","))
    return " ".join(token(t) for t in text.split())


def _looks_like_path(p: str) -> bool:
    first = p.split("/", 1)[0]
    if not re.search(r"[A-Za-z]", first):
        return False
    return p.endswith("/") or bool(re.search(r"\.[A-Za-z0-9]{1,6}$", p))


def extract_paths(text: str) -> list[str]:
    seen: list[str] = []
    for m in PATH_RE.finditer(_expand_braces(text or "")):
        p = m.group(1).rstrip(".")
        if p and p not in seen:
            seen.append(p)
    return seen


def describe_input(root: Path, p: str) -> dict | None:
    path = Path(p) if re.match(r"^[A-Za-z]:/", p) else root / p
    if path.is_file():
        return {"path": p, "kind": "file", "size": path.stat().st_size, "sha256": sha256_file(path)}
    if path.is_dir():
        n = sum(1 for f in path.rglob("*") if f.is_file())
        if n > MAX_TREE_FILES:
            return {"path": p, "kind": f"directory, {n} files (too many to hash)", "size": None, "sha256": None}
        digest, count = sha256_tree(path)
        return {"path": p, "kind": f"directory, {count} files (tree digest)", "size": None, "sha256": digest}
    if _looks_like_path(p):
        return {"path": p, "kind": "missing", "size": None, "sha256": None}
    return None


def collect_inputs(root: Path, text: str) -> list[dict]:
    out = []
    for p in extract_paths(text):
        d = describe_input(root, p)
        if d:
            out.append(d)
    return out


def stated_hashes(text: str) -> dict[str, str]:
    """'<path> (<hex prefix>' in the prompt -> {path: prefix}: hashes the card recorded when it was written."""
    found = {}
    for m in PATH_RE.finditer(text or ""):
        p = m.group(1).rstrip(".")
        h = STATED_HASH_RE.match(text, m.end())
        if h:
            found[p] = h.group(1)
    return found


# ---------------------------------------------------------------- output

def _fence_for(text: str) -> str:
    longest = max((len(r) for r in re.findall(r"`+", text)), default=0)
    return "`" * max(3, longest + 1)


def _input_table(rows: list[dict], stated: dict[str, str] | None = None) -> list[str]:
    out = ["| path | what | bytes | sha256 |" + (" stated in card |" if stated is not None else ""),
           "|---|---|---|---|" + ("---|" if stated is not None else "")]
    for r in rows:
        line = f"| `{r['path']}` | {r['kind']} | {r['size'] if r['size'] is not None else '-'} | " \
               f"{r['sha256'] or '-'} |"
        if stated is not None:
            s = stated.get(r["path"])
            if not s:
                note = "-"
            elif r["sha256"] and r["sha256"].startswith(s):
                note = f"{s} (match)"
            else:
                note = f"{s} (MISMATCH: the input changed since the card was written)"
            line += f" {note} |"
        out.append(line)
    return out


def build(root: Path, cid: str, out_dir: Path | None = None, date: str | None = None,
          strict_inputs: bool = False) -> tuple[Path, list[str]]:
    """Write the task file; returns (path, warnings)."""
    card = get_card(root, cid)
    md = templates_text(root)
    blocks = parse_blocks(md)
    template, preamble, body = split_prompt(card)
    if not re.search(r"(?<![A-Z0-9-])" + re.escape(template) + r"(?![A-Z0-9-])", md):
        raise VisualError(f"{cid}: template {template} is not described in {TEMPLATES_REL}")
    set_name = derive_set(card, preamble, body)
    date = date or dt.date.today().isoformat()
    syntx = template.startswith("T-SYNTX")
    ext = ".syntx.txt" if syntx else ".codex.md"
    out_dir = Path(out_dir) if out_dir else root / PROMPTS_REL
    out_path = out_dir / f"{cid}{ext}"
    used_blocks = [b for b in dict.fromkeys(BLOCK_REF_RE.findall(body)) if b in blocks]
    prompt = expand(body, blocks, {"set": set_name, "id": cid, "date": date}, cid)

    warnings: list[str] = []
    status = (card.get("status") or "").strip()
    if status != READY_STATUS:
        warnings.append(f"card status is {status!r}, not {READY_STATUS!r}: check depends_on before the run")
    for name in FORBIDDEN_NAMES:
        if re.search(r"\b" + re.escape(name) + r"\b", prompt):
            warnings.append(f"the prompt mentions {name!r}: allowed only as a prohibition, never in an image prompt "
                            "(ВР-PR07) - read the file")

    refs = collect_inputs(root, card.get("references") or "")
    missing = [r["path"] for r in refs if r["kind"] == "missing"]
    if missing:
        warnings.append("inputs named in 'references' not found: " + ", ".join(missing))
        if strict_inputs:
            raise VisualError(f"{cid}: inputs not found (--strict-inputs): {', '.join(missing)}")
    ref_paths = {r["path"] for r in refs}
    stated = stated_hashes(prompt)
    in_prompt = []
    for r in collect_inputs(root, prompt):
        if r["path"] in ref_paths:
            continue
        if r["sha256"] is None and r["path"] not in stated:
            continue  # outputs not made yet, package-relative names (_tools/, concepts/), unhashable trees
        in_prompt.append(r)
    for r in in_prompt:
        s = stated.get(r["path"])
        if s and not (r["sha256"] or "").startswith(s):
            warnings.append(f"{r['path']}: sha256 {(r['sha256'] or 'missing')[:16]} differs from the card's {s}")

    lines = [
        f"# {cid} - {'SYNTX' if syntx else 'Codex'} task",
        "",
        "Generated by `tools/art/visual/prompt_build.py` from the task card; do not edit by hand, rebuild instead.",
        "The task to execute is the text in the section **Task** below. The header is provenance only.",
        "",
        "| field | value |",
        "|---|---|",
        f"| id | {cid} |",
        f"| title | {card.get('title', '').strip()} |",
        f"| date | {date} |",
        f"| template | {template} |",
        f"| set | {set_name} (package folder `art/imagegen/{set_name}-codex/`) |",
        f"| priority | {card.get('priority', '').strip() or '-'} |",
        f"| depends_on | {card.get('depends_on', '').strip() or '-'} |",
        f"| card | `{card['_file']}`, status «{status or '-'}» |",
        f"| card prompt sha256 | {hashlib.sha256((card.get('prompt') or '').encode('utf-8')).hexdigest()} |",
        f"| blocks | {', '.join('[[' + b + ']]' for b in used_blocks) or 'none'} from `{TEMPLATES_REL}` "
        f"(sha256 {sha256_file(root / TEMPLATES_REL)}) |",
        f"| preamble | {'omitted (instructions for Claude, not part of the task)' if preamble else 'none'} |",
        "",
        "## Inputs named in the card (`references`)",
        "",
    ]
    lines += _input_table(refs) if refs else ["(no file paths in `references`)"]
    if in_prompt:
        lines += ["", "## Other paths named in the task text", ""]
        lines += _input_table(in_prompt, stated)
    if warnings:
        lines += ["", "## Warnings", ""] + [f"- {w}" for w in warnings]
    fence = _fence_for(prompt)
    lines += ["", "## Task", "", fence + "text", prompt, fence, ""]
    text = "\n".join(lines)
    leftover = VAR_RE.findall(text)
    if leftover:  # the header copies card fields; never ship a file with a placeholder in it
        raise VisualError(f"{cid}: unfilled variable(s) in the output: {', '.join(sorted(set(leftover)))}")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8", newline="\n")
    return out_path, warnings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("card_id", help="card id, e.g. HB-07")
    ap.add_argument("--out", type=Path, help=f"output folder (default {PROMPTS_REL})")
    ap.add_argument("--date", help="ISO date for the header (default today)")
    ap.add_argument("--strict-inputs", action="store_true", help="fail when a path named in 'references' is missing")
    ap.add_argument("--root", type=Path, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    utf8_console()
    root = (a.root or repo_root()).resolve()
    try:
        path, warnings = build(root, a.card_id.strip(), a.out, a.date, a.strict_inputs)
    except VisualError as e:
        print(f"prompt_build: ERROR: {e}", file=sys.stderr)
        return 2
    for w in warnings:
        print(f"prompt_build: WARNING: {w}", file=sys.stderr)
    print(rel_or_abs(root, path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
