#!/usr/bin/env python3
"""HUD string tables RU/EN (VS-1 HB-05; 04-hud-spec.md §6, ВР-37, ВР-H13, HUD-RULES П5).

Sources (docs/unreal/contracts/hud/): st-hud.csv (hud.*), st-screens.csv (screens.*, settings.*, common.*),
st-ms.csv (ms.*: move-selection/03-ux-spec.md §9 with the ВР-H09 delta), why-reasons.json (why.*).
Targets: /Game/UI/Localization/ST_Hud, ST_Screens, ST_Ms, ST_Why (UStringTable, EN source, namespaces hud / screens /
ms / why) and the localization target Game (Content/Localization/Game: en native, ru), compiled by the GatherText
commandlet with Config/Localization/Game.ini (gather -> import ru/Game.po -> locres -> export).

  python tools/s08/hud_contract/hud_strings_build.py check        every key of 04 is in its table, no duplicates,
                                                                  RU and EN per key, same {args}, RU plural forms
  python tools/s08/hud_contract/hud_strings_build.py extract-ms   (re)write st-ms.csv from 03 §9 + ВР-H09 delta
  python tools/s08/hud_contract/hud_strings_build.py po           write Content/Localization/Game/ru/Game.po
  python tools/s08/hud_contract/hud_strings_build.py build        check, po, assets (UE Python), GatherText; verify
  UnrealEditor-Cmd <uproject> -run=pythonscript -script=<this file>   (inside UE) create / refresh the 4 assets

Stdlib only outside UE. Exit 0 = PASS.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
HUD = REPO / "docs/unreal/contracts/hud"
SPEC04 = REPO / "docs/game-design/visual/04-hud-spec.md"
SPEC_MS = REPO / "docs/game-design/move-selection/03-ux-spec.md"
WHY = HUD / "why-reasons.json"
PROJECT = REPO / "unreal/Unmatched"
UPROJECT = PROJECT / "Unmatched.uproject"
LOC_DIR = PROJECT / "Content/Localization/Game"
GATHER_INI = PROJECT / "Config/Localization/Game.ini"
UE_ROOT = Path(os.environ.get("UE_ROOT", r"C:\Program Files\Epic Games\UE_5.8"))
UE_CMD = UE_ROOT / "Engine/Binaries/Win64/UnrealEditor-Cmd.exe"
ASSET_DIR = "/Game/UI/Localization"
CLARIFY = "уточнить"
BUDGET_BYTES = 200 * 1024

# table -> asset, namespace, source, key prefixes (04 §6.1, ВР-H13)
TABLES = {
    "ST_Hud": {"namespace": "hud", "csv": HUD / "st-hud.csv", "prefixes": ("hud.",)},
    "ST_Screens": {"namespace": "screens", "csv": HUD / "st-screens.csv", "prefixes": ("screens.", "settings.", "common.")},
    "ST_Ms": {"namespace": "ms", "csv": HUD / "st-ms.csv", "prefixes": ("ms.",)},
    "ST_Why": {"namespace": "why", "json": WHY, "prefixes": ("why.",)},
}
NS_RE = r"(?:hud|screens|settings|common|ms|why)"
FULL_KEY_RE = re.compile(r"^%s\.[a-z0-9_.|]+[a-z0-9_]$" % NS_RE)
WILDCARD_RE = re.compile(r"^(%s(?:\.[a-z0-9_]+)*)\.(?:\*|<[^>]+>)$" % NS_RE)
SHORT_RE = re.compile(r"^\.[a-z0-9_.|]+[a-z0-9_]$")
ARG_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}(?:\|plural\(([^)]*)\))?")
PLURAL_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}\|plural\(([^)]*)\)")
RU_PLURAL = {"one", "few", "many", "other"}
EN_PLURAL = {"one", "other"}
# ВР-H09: in ms.status.* the key leaves the text for a chip (hud.key.<action>)
KEY_HINT_RE = re.compile(r"\s*\((?:[MAGENRBCXKV]|Enter|Esc|Backspace|Delete|1–9)\)")
ENTER_TAIL_RE = re.compile(r";\s*Enter\b.*$")
MS_PLURAL = {  # 03 §9: "Плюрализация «бойц(а/ов)» — через форматирование StringTable с числом"
    "ru": ("{n} бойц(а/ов)", "{n} {n}|plural(one=боец,few=бойца,many=бойцов,other=бойца)"),
    "en": ("{n} fighter(s)", "{n} {n}|plural(one=fighter,other=fighters)"),
}


# ---------------------------------------------------------------------------------------------------- sources
def read_csv(path: Path) -> list[dict]:
    text = Path(path).read_bytes().decode("utf-8-sig").replace("\r\n", "\n")
    return list(csv.DictReader(io.StringIO(text)))


def why_rows(path: Path = WHY) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [{"Key": r["key"], "SourceString": r["en"], "ru": r["ru"], "ref": r.get("source", "why-reasons.json")}
            for r in data["reasons"]]


def table_rows(name: str) -> list[dict]:
    t = TABLES[name]
    return why_rows(t["json"]) if "json" in t else read_csv(t["csv"])


def all_rows() -> dict[str, list[dict]]:
    return {name: table_rows(name) for name in TABLES}


def table_for(key: str) -> str | None:
    for name, t in TABLES.items():
        if key.startswith(t["prefixes"]):
            return name
    return None


def keys_from_04(text: str) -> tuple[dict[str, int], dict[str, int]]:
    """Every string key 04 names: full keys, shorthand ".x" (base = the first two segments of the last full key on the
    same line: `screens.login.title`, `.error.credentials` -> screens.login.error.credentials), alternation
    `.type.attack|defense` and wildcards (`settings.*`, `hud.key.<действие>`) -> {key: line}, {prefix: line}."""
    exact: dict[str, int] = {}
    wild: dict[str, int] = {}
    for n, line in enumerate(text.splitlines(), 1):
        base = None
        for tok in re.findall(r"`([^`]+)`", line):
            tok = tok.strip()
            m = WILDCARD_RE.match(tok)
            if m:
                wild.setdefault(m.group(1) + ".", n)
                continue
            if FULL_KEY_RE.match(tok):
                full = tok
                base = ".".join(tok.split(".")[:2])
            elif SHORT_RE.match(tok) and base:
                full = base + tok
            else:
                continue
            head, _, last = full.rpartition(".")
            for alt in last.split("|"):
                exact.setdefault(head + "." + alt, n)
    return exact, wild


def ms_rows_from_03(text: str) -> list[tuple[str, str, str]]:
    """Rows of the 03 §9 table: (key, ru, en); "`ms.settings.anim.none` / `.fast` …" expands to one row per key."""
    sec = text.split("## 9.", 1)[1].split("\n## ", 1)[0]
    out = []
    for line in sec.splitlines():
        if not line.startswith("| `ms."):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        keys = re.findall(r"`([^`]+)`", cells[0])
        if len(keys) == 1:
            out.append((keys[0], cells[1], cells[2]))
            continue
        base = keys[0].rsplit(".", 1)[0]
        full = [keys[0]] + [base + k for k in keys[1:]]
        ru = [s.strip() for s in cells[1].split("/")]
        en = [s.strip() for s in cells[2].split("/")]
        if not (len(full) == len(ru) == len(en)):
            raise ValueError("03 §9: не разобрать строку %s" % cells[0])
        out.extend(zip(full, ru, en))
    return out


def ms_delta(key: str, text: str, lang: str) -> str:
    """ВР-H09 (04 §2.5, §6.1): ms.status.* lose the key hints - the key moves to a hud.key.* chip; the «бойц(а/ов)»
    shorthand of 03 §9 becomes a real plural."""
    if key.startswith("ms.status."):
        text = ENTER_TAIL_RE.sub("", KEY_HINT_RE.sub("", text)).strip()
    old, new = MS_PLURAL[lang]
    return text.replace(old, new)


def expected_ms_rows(spec_text: str | None = None) -> list[dict]:
    spec_text = spec_text if spec_text is not None else SPEC_MS.read_text(encoding="utf-8")
    out = []
    for k, ru, en in ms_rows_from_03(spec_text):
        ru2, en2 = ms_delta(k, ru, "ru"), ms_delta(k, en, "en")
        ref = "03 §9"
        if MS_PLURAL["ru"][0] in ru:
            ref += " · plural RU one/few/many/other"
        elif (ru2, en2) != (ru, en):
            ref += " · ВР-H09: клавиша — чип hud.key.*"
        out.append({"Key": k, "SourceString": en2, "ru": ru2, "ref": ref})
    return out


def write_csv(path: Path, rows: list[dict]) -> None:
    buf = io.StringIO(newline="")
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["Key", "SourceString", "ru", "ref"])
    for r in rows:
        w.writerow([r["Key"], r["SourceString"], r["ru"], r.get("ref", "")])
    Path(path).write_bytes(buf.getvalue().encode("utf-8"))


# ---------------------------------------------------------------------------------------------------- checks
def args_of(text: str) -> set[str]:
    return {m.group(1) for m in ARG_RE.finditer(text)}


def plural_errors(key: str, text: str, lang: str) -> list[str]:
    errs = []
    need = RU_PLURAL if lang == "ru" else EN_PLURAL
    for m in PLURAL_RE.finditer(text):
        forms = {p.split("=", 1)[0].strip() for p in m.group(2).split(",") if "=" in p}
        if not need <= forms:
            errs.append("%s/%s: plural {%s} без форм %s" % (key, lang, m.group(1), sorted(need - forms)))
    if "|plural(" in text and not PLURAL_RE.search(text):
        errs.append("%s/%s: plural не разобран" % (key, lang))
    return errs


def check(rows: dict[str, list[dict]] | None = None, spec04: str | None = None, spec_ms: str | None = None) -> tuple[list[str], dict]:
    rows = rows if rows is not None else all_rows()
    spec04 = spec04 if spec04 is not None else SPEC04.read_text(encoding="utf-8")
    errors: list[str] = []
    stats = {"tables": {}, "clarify": 0, "missing04": 0, "dup": 0}
    seen: dict[str, str] = {}
    for name, rs in rows.items():
        stats["tables"][name] = len(rs)
        for r in rs:
            key = r.get("Key", "")
            if not key:
                errors.append("%s: пустой ключ" % name)
                continue
            if key in seen:
                errors.append("дубль ключа %s (%s и %s)" % (key, seen[key], name))
                stats["dup"] += 1
            seen[key] = name
            if table_for(key) != name:
                errors.append("%s: ключ %s не своего пространства (%s)" % (name, key, "/".join(TABLES[name]["prefixes"])))
            en, ru = r.get("SourceString", ""), r.get("ru", "")
            if not en.strip():
                errors.append("%s: нет EN" % key)
            if not ru.strip():
                errors.append("%s: пустой RU — нужен перевод или «%s» (EN молча не подставляется)" % (key, CLARIFY))
            elif ru.strip() == CLARIFY:
                stats["clarify"] += 1
                continue
            if args_of(en) != args_of(ru):
                errors.append("%s: аргументы EN %s и RU %s" % (key, sorted(args_of(en)), sorted(args_of(ru))))
            errors += plural_errors(key, ru, "ru") + plural_errors(key, en, "en")
    exact, wild = keys_from_04(spec04)
    for key, line in sorted(exact.items()):
        table = table_for(key)
        if table is None or seen.get(key) != table:
            errors.append("ключ 04 (строка %d) нет в таблице: %s" % (line, key))
            stats["missing04"] += 1
    for prefix, line in sorted(wild.items()):
        if not any(k.startswith(prefix) for k in seen):
            errors.append("шаблон 04 (строка %d) без единого ключа: %s*" % (line, prefix))
            stats["missing04"] += 1
    if "ST_Ms" in rows:
        want = {r["Key"]: r for r in expected_ms_rows(spec_ms)}
        have = {r["Key"]: r for r in rows["ST_Ms"]}
        for k in sorted(set(want) - set(have)):
            errors.append("st-ms.csv: нет ключа 03 §9 %s" % k)
        for k in sorted(set(have) - set(want)):
            errors.append("st-ms.csv: ключа %s нет в 03 §9" % k)
        for k in sorted(set(want) & set(have)):
            for col in ("SourceString", "ru"):
                if want[k][col] != have[k][col]:
                    errors.append("st-ms.csv: %s/%s расходится с 03 §9 (+ВР-H09): %r против %r"
                                  % (k, col, have[k][col], want[k][col]))
    size = sum(len((r["Key"] + r["SourceString"] + r["ru"]).encode("utf-8")) for rs in rows.values() for r in rs)
    stats["bytes"] = size
    if size > BUDGET_BYTES:
        errors.append("таблицы %d байт > бюджета %d" % (size, BUDGET_BYTES))
    stats["keys04"] = len(exact)
    stats["wild04"] = len(wild)
    return errors, stats


# ---------------------------------------------------------------------------------------------------- PO / UE CSV
def po_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t").replace("\r", "\\r")


def ctxt_escape(s: str) -> str:
    return s.replace(",", "\\,")


def render_po(rows: dict[str, list[dict]], culture: str = "ru") -> str:
    """Game.po in the Unreal PO format (msgctxt "Namespace,Key", msgid = EN source, msgstr = translation)."""
    plural_forms = ("nplurals=4; plural=(n%1==0 && n%10==1 && n%100!=11 ? 0 : n%1==0 && n%10>=2 && n%10<=4 && "
                    "(n%100<12 || n%100>14) ? 1 : n%1==0 && (n%10==0 || (n%10>=5 && n%10<=9) || (n%100>=11 && "
                    "n%100<=14)) ? 2 : 3);")
    L = ["# Game %s translation (generated by tools/s08/hud_contract/hud_strings_build.py from the st-*.csv and" % culture,
         "# why-reasons.json; edit the sources, not this file).",
         'msgid ""', 'msgstr ""',
         '"Project-Id-Version: Game\\n"', '"Language-Team: \\n"', '"Language: %s\\n"' % culture,
         '"MIME-Version: 1.0\\n"', '"Content-Type: text/plain; charset=UTF-8\\n"', '"Content-Transfer-Encoding: 8bit\\n"',
         '"Plural-Forms: %s\\n"' % plural_forms, ""]
    for name in sorted(rows):
        ns = TABLES[name]["namespace"]
        for r in sorted(rows[name], key=lambda x: x["Key"]):
            translation = r["SourceString"] if culture == "en" else r["ru"]
            L += ["#. Key:\t%s" % r["Key"], "#. SourceLocation:\t%s/%s.%s" % (ASSET_DIR, name, name),
                  "#: %s/%s.%s" % (ASSET_DIR, name, name),
                  'msgctxt "%s"' % po_escape("%s,%s" % (ctxt_escape(ns), ctxt_escape(r["Key"]))),
                  'msgid "%s"' % po_escape(r["SourceString"]), 'msgstr "%s"' % po_escape(translation), ""]
    return "\n".join(L)


def write_po(rows: dict[str, list[dict]] | None = None) -> Path:
    rows = rows if rows is not None else all_rows()
    path = LOC_DIR / "ru" / "Game.po"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(render_po(rows, "ru").encode("utf-8"))
    return path


def ue_csv(rows: list[dict]) -> str:
    """The CSV UStringTable imports (Key, SourceString; no namespace)."""
    buf = io.StringIO(newline="")
    w = csv.writer(buf, lineterminator="\n", quoting=csv.QUOTE_ALL)
    w.writerow(["Key", "SourceString"])
    for r in rows:
        w.writerow([r["Key"], r["SourceString"]])
    return buf.getvalue()


# ---------------------------------------------------------------------------------------------------- UE side
def ue_build_assets() -> None:
    import unreal as u  # noqa: PLC0415 - inside the editor only

    tools = u.AssetToolsHelpers.get_asset_tools()
    rows = all_rows()
    for name, t in TABLES.items():
        path = "%s/%s" % (ASSET_DIR, name)
        if u.EditorAssetLibrary.does_asset_exist(path):
            asset = u.EditorAssetLibrary.load_asset(path)
        else:
            asset = tools.create_asset(name, ASSET_DIR, u.StringTable, u.StringTableFactory())
        if asset is None:
            raise RuntimeError("cannot create %s" % path)
        if not u.UmTextLibrary.author_string_table(asset, t["namespace"], ue_csv(rows[name])):
            raise RuntimeError("cannot fill %s" % path)
        if not u.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False):
            raise RuntimeError("cannot save %s" % path)
        u.log("HUD_STRINGS asset %s namespace=%s keys=%d" % (path, t["namespace"], len(rows[name])))


def run_ue(args: list[str], log: Path) -> int:
    cmd = [str(UE_CMD), str(UPROJECT)] + args + ["-unattended", "-nullrhi", "-nosplash", "-nullaudio", "-abslog=%s" % log]
    print("RUN", " ".join(cmd))
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.run(cmd, creationflags=flags, timeout=900).returncode


def build(logdir: Path) -> int:
    errors, stats = check()
    if errors:
        for e in errors:
            print("ERROR", e)
        return 1
    print("HUD_STRINGS check PASS", json.dumps(stats, ensure_ascii=False))
    logdir.mkdir(parents=True, exist_ok=True)
    rc = run_ue(["-run=pythonscript", "-script=%s" % Path(__file__).resolve()], logdir / "strings-assets.log")
    if rc != 0:
        print("ERROR assets commandlet exit", rc)
        return 1
    print("PO", write_po())
    rc = run_ue(["-run=GatherText", "-config=%s" % GATHER_INI], logdir / "strings-gather.log")
    if rc != 0:
        print("ERROR GatherText exit", rc)
        return 1
    missing = [p for p in (LOC_DIR / "Game.locmeta", LOC_DIR / "Game.manifest", LOC_DIR / "en/Game.locres",
                           LOC_DIR / "ru/Game.locres", LOC_DIR / "ru/Game.archive") if not p.exists()]
    if missing:
        print("ERROR missing", [str(p) for p in missing])
        return 1
    print("HUD_STRINGS build PASS", LOC_DIR)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    sub.add_parser("extract-ms")
    sub.add_parser("po")
    b = sub.add_parser("build")
    b.add_argument("--logdir", type=Path, default=Path(os.environ.get("TEMP", "/tmp")) / "hud-strings")
    a = ap.parse_args(argv)
    if a.cmd == "check":
        errors, stats = check()
        for e in errors:
            print("ERROR", e)
        print("HUD_STRINGS", "PASS" if not errors else "FAIL", json.dumps(stats, ensure_ascii=False))
        return 0 if not errors else 1
    if a.cmd == "extract-ms":
        rows = expected_ms_rows()
        write_csv(TABLES["ST_Ms"]["csv"], rows)
        print("st-ms.csv", len(rows))
        return 0
    if a.cmd == "po":
        print("PO", write_po())
        return 0
    return build(a.logdir)


def _running_in_unreal() -> bool:
    try:
        import unreal  # noqa: F401, PLC0415
    except ImportError:
        return False
    return True


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if _running_in_unreal():
        ue_build_assets()
    else:
        sys.exit(main())
