#!/usr/bin/env python3
"""Проверки правил HUD (docs/unreal/contracts/hud/HUD-RULES.md) без движка.

  python tools/s08/hud_contract/hud_contract.py validate            G-TOKENS: токены стиля, свежесть S08HudTokens.generated.h
                                                                    (ВР-77) и DA_UmHudTheme (sha256 JSON в ассете, HB-04), нет
                                                                    литералов цвета в S08/UI; коды why.* против 02 §4.2
  python tools/s08/hud_contract/hud_contract.py linear              таблица hex sRGB -> linear (как FLinearColor::FromSRGBColor)
  python tools/s08/hud_contract/hud_contract.py check-trace <log> [--width 1920 --height 1080]
                                                                    гейт строк `SHOT widget id=… bbox=… geom=painted`,
                                                                    `HUD-LAYOUT` и `PORTRAIT` (CP-08: scale ≤ 1,6, нет
                                                                    монограммы при ключе из реестра; CP-12: у гарпии в
                                                                    панели номер n=1…3, ВР-72) и `CARD-ART` (VS-3 CP-15:
                                                                    scale ≤ 1,6; lang=fallback при ключе из реестра — ошибка,
                                                                    кроме tex=legacy отката -S08CardArtLegacy); VS-3 HB-30:
                                                                    UI-HUD-COMBAT-EDGE fighter=opp face=1 только в
                                                                    state=reveal (приватность до раскрытия)
  python tools/s08/hud_contract/hud_contract.py check-shots <log> --rule "<file>: need <id> k=v|v2 ...; deny <id> k=v"
                                   [--rule ...] [--privacy]
                                                                    VS-4 HB-48 (04 §5.3): гейт кадра по строкам `SHOT widget`
                                                                    блока этого кадра (строки перед последним `SHOT request
                                                                    file=<file>`): need — видимая нарисованная строка с этим
                                                                    id и полями (`A || B` — любая из двух), deny — видимой
                                                                    такой строки нет; --privacy — правила приватности по всей
                                                                    трассе (лицо карты соперника только в state=reveal,
                                                                    скрытый инспектор без значений)

Только stdlib. Код выхода: 0 — ошибок нет, 1 — есть ошибки.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hud_tokens_codegen as codegen  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
HUD = REPO / "docs/unreal/contracts/hud"
TOKENS = HUD / "hud-style-tokens.json"
WHY = HUD / "why-reasons.json"
SPEC02 = REPO / "docs/game-design/02-ux-ui-spec.md"
# VS-2 HB-14...HB-16 (04 §4.5, §7.1): the new UI-IDs of the HUD spec and the states each may trace
SPEC04 = REPO / "docs/game-design/visual/04-hud-spec.md"
HEADER = codegen.HEADER
UI_SRC = REPO / "unreal/Unmatched/Source/Unmatched/S08/UI"
STATUSES = ("предложено", "измерено", "технически импортировано", "художественно принято")
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
# G-TOKENS (02 §13.5): colour literals in the new HUD code (S08/UI) - the values come from S08HudTokens / UUmHudTheme.
COLOR_LITERAL_RE = re.compile(r"\bFColor(?:\s+\w+)?\s*[({]\s*(?:0x)?\d|\bFLinearColor(?:\s+\w+)?\s*[({]\s*[-\d.]"
                              r"|FromHex\s*\(\s*TEXT\s*\(\s*\"#?[0-9A-Fa-f]{6}")
UI_ID_RE = re.compile(r"\bUI-(?:HUD|SCR)-[A-Z]+(?:-[A-Z]+)*\b")
WHY_02_RE = re.compile(r"`(why\.[a-z.]+)`")
SHOT_RE = re.compile(r"SHOT widget (.*)$")
# VS-2 HB-06 (04 §1.6, §4.5, §7.1): one line per shot frame - persistent blocks x FIELD must be 0 (overlapField)
LAYOUT_RE = re.compile(r"HUD-LAYOUT (.*)$")
ARG_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
# VS-2 CP-08 (ВР-CP10, ВР-CP04): the portrait circle - scale <= 1.6, no monogram for a key the registry has
PORTRAIT_RE = re.compile(r"PORTRAIT (id=.*)$")
PORTRAIT_CAP = 1.6
CARD_MEDIA = REPO / "unreal/Unmatched/Config/Cards/S08CardMedia.json"
# VS-3 CP-15 (ВР-CP10, ВР-CP04): the card art - scale <= 1.6, no fallback face for a key the registry has
CARD_ART_RE = re.compile(r"CARD-ART (key=.*)$")
CARD_ART_FIELDS = ("key", "lang", "tex", "show", "su", "px", "scale", "capped", "state")
CARD_LANGS = ("ru", "en", "back", "fallback")


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def srgb_to_linear(c8):
    """Кусочная кривая sRGB (IEC 61966-2-1), которой пользуется FLinearColor::FromSRGBColor (таблица sRGBToLinearTable)."""
    c = c8 / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_to_linear(hexstr):
    h = hexstr.lstrip("#")
    return tuple(round(srgb_to_linear(int(h[i:i + 2], 16)), 4) for i in (0, 2, 4))


def ui_ids_from_02(text):
    return set(UI_ID_RE.findall(text))


ID_CELL_RE = re.compile(r"^`(UI-(?:HUD|SCR)-[A-Z]+(?:-[A-Z]+)*)`$")


def _table_cells(line):
    """A markdown row -> its cells; a '|' inside backticks (`own|opp`, `mode=<a|b>`) stays in its cell."""
    masked = re.sub(r"`[^`]*`", lambda m: m.group(0).replace("|", "\x00"), line.strip())
    return [c.replace("\x00", "|").strip() for c in masked.strip("|").split("|")]


def _state_rule(token):
    """`idle` -> exact; `count=<n>` -> count=<digits>; `mode=<maneuver|attack|scheme>` -> one of the names."""
    if "<" not in token:
        return re.compile(re.escape(token) + r"$")
    pattern = ""
    for part in re.split(r"(<[^>]*>)", token):
        if part.startswith("<") and part.endswith(">"):
            inner = part[1:-1]
            pattern += r"\d+" if inner == "n" else "(?:" + "|".join(re.escape(x) for x in inner.split("|")) + ")"
        else:
            pattern += re.escape(part)
    return re.compile(pattern + r"$")


def ui_states_from_04(text):
    """04 §7.1 'Гейты SHOT widget': {UI-ID: [state rules]} for the rows that list their states in backticks (the
    screens row 'по §1' and the world layer have none). A token with '|' inside <...> is one pattern."""
    if "### 7.1" not in text:
        return {}
    section = text.split("### 7.1", 1)[1].split("### 7.2", 1)[0]
    out = {}
    for line in section.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = _table_cells(line)
        m = ID_CELL_RE.match(cells[0]) if len(cells) >= 3 else None
        if not m:
            continue
        tokens = re.findall(r"`([^`]+)`", cells[2])
        if tokens:
            out[m.group(1)] = [_state_rule(t) for t in tokens]
    return out


def state_allowed(rules, state):
    return any(r.match(state) for r in rules)


def validate_tokens(tokens):
    errors = []
    if tokens.get("schema") != "unmatched.hud-style-tokens/1":
        errors.append("tokens: schema")
    for group in ("colors", "typography", "spacing", "radii", "icons", "motion", "opacity", "skins"):
        if group not in tokens:
            if group not in ("opacity", "skins"):  # opacity / skins: optional groups (VS-1 HB-03 / HB-04)
                errors.append("tokens: нет группы %s" % group)
            continue
        for name, tok in tokens[group].items():
            if tok.get("status") not in STATUSES:
                errors.append("%s.%s: status" % (group, name))
            if not tok.get("source"):
                errors.append("%s.%s: нет source" % (group, name))
            if group == "colors":
                if "alias" not in tok and not HEX_RE.match(tok.get("hex", "")):
                    errors.append("%s.%s: hex %r" % (group, name, tok.get("hex")))
                try:
                    codegen.resolve_color(tokens["colors"], name)  # alias chain, alpha, hex == resolved alias
                except codegen.TokenError as e:
                    errors.append(str(e))
            if group in ("spacing", "radii", "icons") or (group == "typography" and "px" in tok):
                if not isinstance(tok.get("px"), int) or tok["px"] <= 0:
                    errors.append("%s.%s: px" % (group, name))
            if group == "typography" and name.startswith("type."):
                if not isinstance(tok.get("su"), int) or tok["su"] <= 0:
                    errors.append("%s.%s: su" % (group, name))
                if tok.get("face") not in codegen.FACES:
                    errors.append("%s.%s: face %r" % (group, name, tok.get("face")))
            if group == "opacity" and not (isinstance(tok.get("value"), (int, float)) and 0 <= tok["value"] <= 1):
                errors.append("%s.%s: value" % (group, name))
            if group == "skins":
                try:
                    codegen.resolve_skin(tokens, name)
                except (codegen.TokenError, KeyError, TypeError, ValueError) as e:
                    errors.append("skins.%s: %s" % (name, e))
    if not errors:
        try:
            codegen.collect(tokens)  # the same checks the generator runs (type.*, motion, identifier clashes)
            codegen.render(tokens, "0" * 64)
        except codegen.TokenError as e:
            errors.append(str(e))
    return errors


THEME_ASSET = REPO / "unreal/Unmatched/Content/S08/UI/Theme/DA_UmHudTheme.uasset"
SHA_IN_ASSET_RE = re.compile(rb"[0-9a-f]{64}")


def theme_asset_errors(asset=None, tokens=TOKENS):
    """HB-04: DA_UmHudTheme was imported from this exact JSON. UUmHudTheme::TokensJsonSha256 is an ASCII FString in the
    package export data, so its 64 hex digits are found in the .uasset bytes (no engine needed)."""
    asset = Path(asset or THEME_ASSET)
    want = codegen.json_sha256(tokens)
    if not asset.exists():
        shown = asset.relative_to(REPO).as_posix() if asset.is_relative_to(REPO) else str(asset)
        return ["theme stale: %s нет — запустите tools/s08/hud_contract/hud_theme_import.py (UE Python) и git add -f"
                % shown]
    found = {m.group(0).decode("ascii") for m in SHA_IN_ASSET_RE.finditer(asset.read_bytes())}
    if want not in found:
        return ["theme stale: %s импортирован не из текущего hud-style-tokens.json (sha256 %s… нет в ассете) — запустите"
                " hud_theme_import.py" % (asset.name, want[:12])]
    return []


def literal_errors(src_dir=UI_SRC):
    """G-TOKENS: no colour literal in the new HUD code; values come from S08HudTokens.generated.h / the theme."""
    errors = []
    for path in sorted(Path(src_dir).rglob("*")):
        if path.suffix not in (".h", ".cpp") or path.name.endswith(".generated.h"):
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            code = line.split("//", 1)[0]
            if COLOR_LITERAL_RE.search(code):
                errors.append("литерал цвета %s:%d: %s" % (path.relative_to(REPO).as_posix(), n, line.strip()))
    return errors


PROFILES = REPO / "unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json"
REAL_MAPS = ("marmoreal-original", "sarpedon-original")


def board_profile_errors(path=PROFILES, tokens=TOKENS):
    """ВР-76 (VS-6 F1, FX-08): the field colours of the board profiles equal their tokens - moveSelection.choice.colorSrgb
    = the token it names (board.choice by default) on the root and every board; on the two original maps the choice
    block is present and moveSelection.plate.colorSrgb = board.reach (02 §2.7)."""
    colors = load(tokens)["colors"]
    profiles = load(path)
    errors = []

    def token_hex(name):
        return codegen.resolve_color(colors, name)[0].upper()

    blocks = [("root", profiles.get("moveSelection") or {})]
    blocks += [(b.get("id"), b.get("moveSelection") or {}) for b in profiles.get("boards", [])]
    for bid, ms in blocks:
        choice = ms.get("choice")
        if choice is not None:
            token = choice.get("token", "board.choice")
            if token not in colors:
                errors.append("%s: moveSelection.choice.token %s - нет такого токена" % (bid, token))
            elif str(choice.get("colorSrgb", "")).upper() != token_hex(token):
                errors.append("%s: moveSelection.choice.colorSrgb %s != %s %s" % (bid, choice.get("colorSrgb"), token,
                                                                                 token_hex(token)))
        if bid in REAL_MAPS:
            if choice is None:
                errors.append("%s: нет moveSelection.choice (board.choice, ВР-27)" % bid)
            plate = (ms.get("plate") or {}).get("colorSrgb")
            if plate is not None and plate.upper() != token_hex("board.reach"):
                errors.append("%s: moveSelection.plate.colorSrgb %s != board.reach %s" % (bid, plate,
                                                                                         token_hex("board.reach")))
    return errors


def validate_why(why, spec02_text):
    errors = []
    keys = [r["key"] for r in why["reasons"]]
    if len(keys) != len(set(keys)):
        errors.append("why: повтор ключей")
    want = set(WHY_02_RE.findall(spec02_text))
    if want and set(keys) != want:
        errors.append("why: ключи не совпадают с 02 §4.2: нет %s, лишние %s" % (sorted(want - set(keys)), sorted(set(keys) - want)))
    for r in why["reasons"]:
        for lang in why["string_table"]["cultures"]:
            if not r.get(lang):
                errors.append("%s: нет текста %s" % (r["key"], lang))
        args = set(r.get("args", []))
        for lang in why["string_table"]["cultures"]:
            used = set(ARG_RE.findall(r.get(lang, "")))
            if used != args:
                errors.append("%s/%s: аргументы %s против %s" % (r["key"], lang, sorted(used), sorted(args)))
    return errors


def parse_shot_widget(line):
    m = SHOT_RE.search(line.rstrip("\r\n"))
    if not m:
        return None
    return dict(w.split("=", 1) for w in m.group(1).split() if "=" in w)


# Словарь арт-слоя HUD (W4-C плашка/иконка, W5b-R тег/число урона): в 02 для них UI-ID нет — предложенный diff
# docs/art-pipeline/proposals/w5br-hud-tag-damage-02.diff.md (UI-HUD-TAG / UI-HUD-DAMAGE); до решения автора
# клиент пишет эти id.
ART_HUD_IDS = {"plate", "plate.marker", "plate.name", "plate.team", "plate.hpbar", "plate.hpfill", "plate.hp",
               "plate.status", "plate.teamshape", "icon", "board.tag", "board.tag.name", "board.tag.hp",
               "board.tag.bar", "board.tag.chip", "board.damage", "board.damage.text",
               # VS-4 FX-38 (ВР-VS3-FX38-01): the zone icons at a hovered space, one line of its own
               "zone"}


def parse_layout(line):
    m = LAYOUT_RE.search(line.rstrip("\r\n"))
    if not m:
        return None
    return dict(w.split("=", 1) for w in m.group(1).split() if "=" in w)


def parse_bbox(value):
    """'x,y,w,h' (формат HUD-RULES П4) или '(x0,y0,x1,y1)' (строки арт-слоя) -> (x, y, w, h)."""
    v = value.strip()
    if v.startswith("(") and v.endswith(")"):
        x0, y0, x1, y1 = (float(t) for t in v[1:-1].split(","))
        return x0, y0, x1 - x0, y1 - y0
    x, y, w, h = (float(t) for t in v.split(","))
    return x, y, w, h


def registry_portrait_keys(path=CARD_MEDIA):
    """Portrait keys of the registry as the client names them: 'king-arthur', 'king-arthur/merlin'."""
    try:
        entries = load(path)["entries"]
    except (OSError, ValueError, KeyError):
        return set()
    out = set()
    for e in entries:
        if e.get("kind") == "portrait" and e.get("key", "").startswith("portrait:"):
            out.add("/".join(e["key"].split(":")[1:]))
    return out


def registry_card_keys(path=CARD_MEDIA):
    """Card keys (heroSlug:cardSlug) and back keys (back:<hero>) of the registry."""
    try:
        entries = load(path)["entries"]
    except (OSError, ValueError, KeyError):
        return set()
    return {e["key"] for e in entries if e.get("kind") in ("card", "back") and e.get("key")}


def check_card_art_line(n, line, registry):
    """VS-3 CP-15: one 'CARD-ART key=.. lang=.. tex=.. show=.. su=.. px=.. scale=.. capped=.. state=..' line -> errors
    (None when the line is not a CARD-ART line)."""
    m = CARD_ART_RE.search(line.rstrip("\r\n"))
    if not m:
        return None
    f = dict(w.split("=", 1) for w in m.group(1).split() if "=" in w)
    errors = []
    for k in CARD_ART_FIELDS:
        if k not in f:
            errors.append("строка %d: CARD-ART без поля %s" % (n, k))
    if f.get("lang") not in CARD_LANGS:
        errors.append("строка %d: CARD-ART lang=%s" % (n, f.get("lang")))
    try:
        if float(f.get("scale", "0")) > PORTRAIT_CAP + 1e-6:
            errors.append("строка %d: CARD-ART key=%s scale=%s > %.1f (ВР-CP04)" % (n, f.get("key"), f["scale"], PORTRAIT_CAP))
    except ValueError:
        errors.append("строка %d: CARD-ART scale=%r" % (n, f.get("scale")))
    if f.get("capped") not in ("0", "1"):
        errors.append("строка %d: CARD-ART capped=%s" % (n, f.get("capped")))
    if f.get("lang") == "fallback" and f.get("tex") != "legacy" and f.get("key") in registry:
        errors.append("строка %d: CARD-ART key=%s lang=fallback, а скан есть в реестре (ВР-CP10)" % (n, f["key"]))
    return errors


def check_portrait_line(n, line, registry):
    """VS-2 CP-08: one 'PORTRAIT id=.. tex=.. su=.. px=.. scale=.. show=..' line -> errors."""
    m = PORTRAIT_RE.search(line.rstrip("\r\n"))
    if not m:
        return None
    f = dict(w.split("=", 1) for w in m.group(1).split() if "=" in w)
    errors = []
    for k in ("id", "tex", "su", "px", "scale", "show"):
        if k not in f:
            errors.append("строка %d: PORTRAIT без поля %s" % (n, k))
    try:
        if float(f.get("scale", "0")) > PORTRAIT_CAP + 1e-6:
            errors.append("строка %d: PORTRAIT id=%s scale=%s > %.1f (ВР-CP04)" % (n, f.get("id"), f["scale"], PORTRAIT_CAP))
    except ValueError:
        errors.append("строка %d: PORTRAIT scale=%r" % (n, f.get("scale")))
    if f.get("tex") == "monogram" and f.get("id") in registry:
        errors.append("строка %d: PORTRAIT id=%s tex=monogram, а аватар есть в реестре (ВР-CP10)" % (n, f["id"]))
    if f.get("id", "").endswith("/harpies") and f.get("show") == "panel" and f.get("n") not in ("1", "2", "3"):
        # VS-2 CP-12: the harpy's mini portrait in PANEL carries its number 1..3 (02 §6.5, ВР-72) - no letter, no 4..6
        errors.append("строка %d: PORTRAIT id=%s show=panel без номера n=1…3 (ВР-72), n=%s" % (n, f["id"], f.get("n")))
    return errors


def privacy_line_errors(f):
    """Privacy rules of one parsed `SHOT widget` line (empty list = clean).
    VS-3 HB-30 (04 §2.7, 05 §3 VS-3): the opponent's combat card shows its face only from state=reveal.
    VS-4 HB-49 (SC-22, 04 §1.7): the hidden inspector carries no value of the card - its face is the back, no language
    switch, no copies line, no grid."""
    errors = []
    if f.get("id") == "UI-HUD-COMBAT-EDGE" and f.get("fighter") == "opp" and f.get("face") == "1" and f.get("state") != "reveal":
        errors.append("приватность — лицо карты соперника (face=1) до state=reveal (state=%s)" % f.get("state"))
    if f.get("id") == "UI-SCR-INSPECT" and f.get("state") == "hidden":
        leaks = [k for k, ok in (("face", ("back", "-")), ("lang", ("0",)), ("copies", ("0",)), ("grid", ("0",)))
                 if k in f and f[k] not in ok]
        if leaks:
            errors.append("приватность — скрытый инспектор показывает значения (%s)"
                          % ", ".join("%s=%s" % (k, f[k]) for k in leaks))
    return errors


# VS-4 HB-48 (04 §5.3): the s09 / s10 gates check each evidence shot by the `SHOT widget` lines the client wrote for it,
# not by the debug marker colours (-S09Markers stays the rollback of the old pixel gates).
SHOT_REQUEST_RE = re.compile(r"SHOT request file=(\S+)")
SHOT_BOUNDARY_RE = re.compile(r"SHOT (?:captured|late end) file=")
HUD_IMPL_RE = re.compile(r"ARTLOOK .*?hudImpl=(\S+)")


def shot_block(lines, name):
    """The `SHOT widget` lines (parsed) of one shot: the lines before the LAST 'SHOT request file=<name>' back to the
    end of the previous shot ('SHOT captured' / 'SHOT late end'), then the first late block of the same file ('SHOT late
    begin file=<name>' ... 'SHOT late end file=<name>': the geometry of the captured frame, ВР-VS2-77 - a block first
    shown in the shot frame writes its painted line there). None when the trace never requested the file."""
    at = None
    for i in range(len(lines) - 1, -1, -1):
        m = SHOT_REQUEST_RE.search(lines[i])
        if m and m.group(1) == name:
            at = i
            break
    if at is None:
        return None
    out = []
    for k in range(at - 1, max(-1, at - 3000), -1):
        if SHOT_BOUNDARY_RE.search(lines[k]):
            break
        f = parse_shot_widget(lines[k])
        if f is not None:
            out.append(f)
    out.reverse()
    begin, end = "SHOT late begin file=%s " % name, "SHOT late end file=%s" % name
    k = at + 1
    while k < min(len(lines), at + 6000) and begin not in lines[k]:
        k += 1
    if k >= min(len(lines), at + 6000):
        return out
    for k in range(k + 1, min(len(lines), k + 4000)):
        if end in lines[k]:
            break
        f = parse_shot_widget(lines[k])
        if f is not None:
            f["late"] = "1"
            out.append(f)
    return out


def parse_matcher(text):
    """'UI-HUD-COMBAT-EDGE fighter=opp state=back|shield face=0' -> (id, {field: [values]}); an id ending in '*' is a
    prefix ('UI-HUD-*'). A state value may itself hold '=' ('state=mode=maneuver', 'state=count=3')."""
    tokens = text.split()
    if not tokens:
        raise ValueError("пустое правило")
    fields = {}
    for t in tokens[1:]:
        if "=" not in t:
            raise ValueError("поле без '=': %r" % t)
        k, v = t.split("=", 1)
        fields[k] = v.split("|")
    return tokens[0], fields


def matcher_hits(block, matcher, painted):
    """Lines of the block that match: the id, every field, visible=1 (and geom=painted for a 'need'). A matcher that
    names 'visible' itself (e.g. visible=0|1) reads the block's model whether drawn or not - for a harness that shows
    no live match (the backend-less probe keeps ACTIONS collapsed while its model follows the draft)."""
    want_id, fields = matcher
    hits = []
    for f in block:
        fid = f.get("id", "")
        if not (fid == want_id or (want_id.endswith("*") and fid.startswith(want_id[:-1]))):
            continue
        if "visible" not in fields and (f.get("visible") != "1" or (painted and f.get("geom") != "painted")):
            continue
        if all(f.get(k) in vals for k, vals in fields.items()):
            hits.append(f)
    return hits


def parse_rule(text):
    """'<file>: need A k=v; deny B k=v; need C || D' -> (file, [(kind, [matchers])])."""
    if ":" not in text:
        raise ValueError("правило без '<файл>:' — %r" % text)
    name, body = text.split(":", 1)
    clauses = []
    for part in body.split(";"):
        part = part.strip()
        if not part:
            continue
        kind, _, rest = part.partition(" ")
        if kind not in ("need", "deny"):
            raise ValueError("ожидается need / deny: %r" % part)
        clauses.append((kind, [parse_matcher(alt) for alt in rest.split("||")]))
    if not clauses:
        raise ValueError("правило без условий: %r" % text)
    return name.strip(), clauses


def _describe(matcher):
    want_id, fields = matcher
    return " ".join([want_id] + ["%s=%s" % (k, "|".join(v)) for k, v in fields.items()])


def check_shot_rule(lines, rule, hud_impl=None):
    """One rule against its shot's block -> list of failure reasons (empty = PASS). A missing UMG block is named with
    its likely cause: the -S08SlateHud rollback (the Slate path keeps the old -S09Markers pixel gates)."""
    name, clauses = rule
    block = shot_block(lines, name)
    if block is None:
        return ["нет кадра: в трассе нет 'SHOT request file=%s'" % name]
    reasons = []
    for kind, alts in clauses:
        if kind == "need":
            if any(matcher_hits(block, m, True) for m in alts):
                continue
            seen = [f for f in block if any(f.get("id") == m[0] for m in alts)]
            if not seen:
                why = ("в блоке кадра нет строки SHOT widget id=%s — блок UMG не нарисован"
                       % " / ".join(m[0] for m in alts))
                if hud_impl and hud_impl.startswith("slate"):
                    why += " (ARTLOOK hudImpl=%s: откат -S08SlateHud; путь Slate проверяется гейтом с -S09Markers)" % hud_impl
                reasons.append(why)
            else:
                got = "; ".join("state=%s fighter=%s visible=%s geom=%s" % (f.get("state"), f.get("fighter"),
                                                                           f.get("visible"), f.get("geom")) for f in seen)
                reasons.append("нужно %s — в блоке: %s" % (" || ".join(_describe(m) for m in alts), got))
        else:
            for m in alts:
                for f in matcher_hits(block, m, False):
                    reasons.append("запрещено %s — в блоке: state=%s fighter=%s" % (_describe(m), f.get("state"),
                                                                                    f.get("fighter")))
    return reasons


def check_shots(lines, rules, privacy=False):
    """VS-4 HB-48: every rule of every shot -> (results [(file, reasons)], privacy errors)."""
    hud_impl = None
    for line in lines:
        m = HUD_IMPL_RE.search(line)
        if m:
            hud_impl = m.group(1)
    results = [(rule[0], check_shot_rule(lines, rule, hud_impl)) for rule in rules]
    priv = []
    if privacy:
        for n, line in enumerate(lines, 1):
            f = parse_shot_widget(line)
            if f is not None:
                priv += ["строка %d: %s" % (n, e) for e in privacy_line_errors(f)]
    return results, priv


# VC C4 (ВР-VC-19, CLOSEOUT п. 8): `SHOT plate fighter=<id> ... geom=<g> stableFrames=<n>` - the plate's own line of
# the shot cycle (written before `SHOT request`); a cycle ends at `SHOT late end`.
PLATE_LINE_RE = re.compile(r"SHOT plate (fighter=.*)$")


def plate_settling(f, plates):
    """A visible unpainted `plate*` line is "settling" when this shot cycle's `SHOT plate` line of the same fighter says
    the plate was placed less than 2 frames ago (stableFrames < 2, geom=unpainted), or the line carries its own
    `stable=<n>` < 2: the snapshot frame of `-S09Flow` switched the hover in the requesting frame, the plate's geometry
    is not laid out yet and cannot be measured on the capture. Without either, or with >= 2, the line stays an error."""
    if not str(f.get("id", "")).startswith("plate"):
        return False
    if "stable" in f:  # the late line's own count (VC C4 client): the plate may be shown after `SHOT request`
        try:
            return int(f["stable"]) < 2
        except ValueError:
            return False
    p = plates.get(f.get("fighter"))
    if p is None or p.get("geom") == "painted":
        return False
    try:
        return int(p.get("stableFrames", "")) < 2
    except ValueError:
        return False


def check_widget_trace(lines, known_ids, width=1920, height=1080, registry=None, states=None, card_registry=None,
                       stats=None):
    """Правило 3: гейт по трассе геометрии виджета, не по пикселям. Невидимая часть (visible=0, например
    сравнительный Slate-двойник или скрытая иконка в поздней строке W5b-R) может быть unpainted. states (04 §7.1,
    ui_states_from_04): у блока из таблицы состояние должно быть из её списка. VC C4 (ВР-VC-19): строка `plate*` в
    кадре, где табличка поставлена меньше 2 кадров назад (plate_settling), не ошибка, а `settling` (счёт в stats);
    если табличка в трассе ни разу не нарисована, а такие строки есть, - ошибка."""
    states = states or {}
    errors, seen = [], 0
    plates, settling, plate_painted = {}, 0, 0
    ids = set(known_ids) | ART_HUD_IDS
    registry = registry_portrait_keys() if registry is None else registry
    cards = registry_card_keys() if card_registry is None else card_registry
    for n, line in enumerate(lines, 1):
        art = check_card_art_line(n, line, cards)
        if art is not None:
            errors += art
            continue
        por = check_portrait_line(n, line, registry)
        if por is not None:
            errors += por
            continue
        lay = parse_layout(line)
        if lay is not None:
            # VS-2 HB-06: the persistent blocks keep out of FIELD (04 §1.6, D-10 W5b-R); "crossing" names them
            for k in ("class", "canvas", "field", "overlapField"):
                if k not in lay:
                    errors.append("строка %d: HUD-LAYOUT без поля %s" % (n, k))
            try:
                if float(lay.get("overlapField", "0")) > 0.0:
                    errors.append("строка %d: HUD-LAYOUT overlapField=%s (блоки %s пересекают FIELD)"
                                  % (n, lay["overlapField"], lay.get("crossing", "?")))
            except ValueError:
                errors.append("строка %d: HUD-LAYOUT overlapField=%r" % (n, lay.get("overlapField")))
            if lay.get("class") not in ("L", "S"):
                errors.append("строка %d: HUD-LAYOUT class=%s" % (n, lay.get("class")))
            # VS-3 HB-28 (HB-26 D8, VS-2 open item 3): the deck panel covers no block shown with it (STATUS at two
            # lines included); the class S overlap with OPP-HAND / FIELD is deckpanelTransient - measured, not gated
            if "deckpanelBlocks" in lay:
                try:
                    if float(lay["deckpanelBlocks"]) > 0.0:
                        errors.append("строка %d: HUD-LAYOUT deckpanelBlocks=%s (панель колоды закрывает блок)"
                                      % (n, lay["deckpanelBlocks"]))
                except ValueError:
                    errors.append("строка %d: HUD-LAYOUT deckpanelBlocks=%r" % (n, lay["deckpanelBlocks"]))
            continue
        pm = PLATE_LINE_RE.search(line.rstrip("\r\n"))
        if pm:
            p = dict(w.split("=", 1) for w in pm.group(1).split() if "=" in w)
            plates[p.get("fighter")] = p
            continue
        if "SHOT late end" in line:
            plates = {}
            continue
        f = parse_shot_widget(line)
        if f is None:
            continue
        seen += 1
        for k in ("id", "state", "bbox", "geom", "visible"):
            if k not in f:
                errors.append("строка %d: нет поля %s" % (n, k))
        if "id" in f and f["id"] not in ids:
            errors.append("строка %d: неизвестный UI-ID %s" % (n, f["id"]))
        if f.get("id") in states and "state" in f and not state_allowed(states[f["id"]], f["state"]):
            errors.append("строка %d: %s state=%s не из списка 04 §7.1" % (n, f["id"], f["state"]))
        errors += ["строка %d: %s" % (n, e) for e in privacy_line_errors(f)]
        if f.get("visible") == "0":
            continue
        if f.get("geom") == "painted" and str(f.get("id", "")).startswith("plate"):
            plate_painted += 1
        if f.get("geom") != "painted" and plate_settling(f, plates):
            settling += 1
            continue
        if f.get("geom") != "painted":
            errors.append("строка %d: geom=%s (нужна нарисованная геометрия)" % (n, f.get("geom")))
        try:
            x, y, w, h = parse_bbox(f.get("bbox", ""))
            if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > width + 0.5 or y + h > height + 0.5:
                errors.append("строка %d: bbox %s вне кадра %dx%d" % (n, f["bbox"], width, height))
        except ValueError:
            errors.append("строка %d: bbox %r" % (n, f.get("bbox")))
    if settling and not plate_painted:
        errors.append("табличка plate ни разу не нарисована (%d строк settling, painted 0)" % settling)
    if stats is not None:
        stats["plate_settling"] = settling
        stats["plate_painted"] = plate_painted
    return errors, seen


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate")
    sub.add_parser("linear")
    c = sub.add_parser("check-trace")
    c.add_argument("log")
    c.add_argument("--width", type=int, default=1920)
    c.add_argument("--height", type=int, default=1080)
    s = sub.add_parser("check-shots")
    s.add_argument("log")
    s.add_argument("--rule", action="append", default=[])
    s.add_argument("--privacy", action="store_true")
    s.add_argument("--report", help="also write the SHOTGATE lines to this UTF-8 file (the PowerShell gates read it)")
    a = ap.parse_args(argv)
    if a.cmd == "check-shots":
        try:
            rules = [parse_rule(r) for r in a.rule]
        except ValueError as e:
            print("SHOTGATE ERROR правило:", e)
            return 2
        lines = Path(a.log).read_text(encoding="utf-8", errors="replace").splitlines()
        results, priv = check_shots(lines, rules, a.privacy)
        out = ["SHOTGATE %s %s%s" % (name, "PASS" if not reasons else "FAIL", "" if not reasons else ": " + " | ".join(reasons))
               for name, reasons in results]
        out += ["SHOTGATE privacy FAIL: %s" % e for e in priv]
        ok = all(not r for _, r in results) and not priv and bool(rules or a.privacy)
        out.append("HUD_SHOTS %s rules %d privacy %s" % ("PASS" if ok else "FAIL", len(rules), "on" if a.privacy else "off"))
        for line in out:
            print(line)
        if a.report:
            Path(a.report).write_text("\n".join(out) + "\n", encoding="utf-8")
        return 0 if ok else 1
    spec02 = SPEC02.read_text(encoding="utf-8")
    if a.cmd == "validate":
        errors = (validate_tokens(load(TOKENS)) + codegen.header_errors(TOKENS, HEADER) + theme_asset_errors()
                  + literal_errors() + validate_why(load(WHY), spec02) + board_profile_errors())
        for e in errors:
            print("ERROR", e)
        print("HUD_CONTRACT", "PASS" if not errors else "FAIL")
        return 0 if not errors else 1
    if a.cmd == "linear":
        colors = load(TOKENS)["colors"]
        for name in colors:
            hexstr, alpha = codegen.resolve_color(colors, name)
            print("%-20s %s -> linear %s alpha %.2f" % (name, hexstr, hex_to_linear(hexstr), alpha))
        return 0
    lines = Path(a.log).read_text(encoding="utf-8", errors="replace").splitlines()
    spec04 = SPEC04.read_text(encoding="utf-8") if SPEC04.exists() else ""
    stats = {}
    errors, seen = check_widget_trace(lines, ui_ids_from_02(spec02) | ui_ids_from_02(spec04), a.width, a.height,
                                      states=ui_states_from_04(spec04), stats=stats)
    for e in errors:
        print("GATE", e)
    print("HUD_TRACE", "PASS" if not errors and seen else "FAIL", "widget_lines", seen,
          "plate_settling", stats.get("plate_settling", 0))
    return 0 if not errors and seen else 1


if __name__ == "__main__":
    sys.exit(main())
