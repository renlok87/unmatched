"""VS-3 CP-03 / CP-04 (docs/game-design/visual/06-tasks/cards-portraits.csv; decision ВР-CP16 by delegation): the RU names
of the 27 MVP cards for the import report art/cards-v1/ue-import-report.json ("ruNames").

The client shows the name of the DATA only (Card.nameRu / nameEn, 02 §3.4): the RU text printed on a scan never goes into
the client, a StringTable or the data. This module compares, per card key heroSlug:cardSlug,
  data     the backend content of the S01 capture (docs/game-design/evidence/S01/content-<hero>.json: name, nameRu, count)
           and the reference DB snapshot art/cards-v1/card-names-db.json (Card.nameRu in the :5433 reference DB, written
           by --db through `docker exec unmatched-postgres psql`, read-only);
  scrape   i18n.ru.title of the scrape (scraped-data/api/heroes/<hero>.json, fetchedDeck[].card) - the source the admin
           can take a translation from;
  scan     what the RU scan prints - reference only, typed from the CP-03 / CP-04 rows (never shipped);
and lists the discrepancies: nameRu-is-en (the data's nameRu is the EN text), no-ru-in-scrape, scan-differs (the RU of
the data / scrape is not what the scan prints). The fix belongs to the admin :5480 (the reference DB), never to the
client (ВР-CP16).

  python tools/art/cards/card_deck_names.py            print the section
  python tools/art/cards/card_deck_names.py --db       refresh art/cards-v1/card-names-db.json from the reference DB
Stdlib only (runs inside the editor too: ue_import_card_media.py writes this section into its report).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
HEROES = {"king-arthur": "King Arthur", "medusa": "Medusa"}
S01 = REPO / "docs/game-design/evidence/S01"
DB_SNAPSHOT = REPO / "art/cards-v1/card-names-db.json"
# What the RU scan prints (CP-03 / CP-04 rows, «на RU-скане») - reference for the admin, never data, never shipped.
SCAN_RU = {
    "king-arthur:the-lady-of-the-lake": "Хозяйка озера",
    "king-arthur:the-aid-of-morgana": "Помощь Морганы",
    "king-arthur:prophecy": "Пророчество",
    "king-arthur:excalibur": "Экскалибур",
    "king-arthur:momentous-shift": "Переломный момент",
    "king-arthur:bewilderment": "Смятение",
    "king-arthur:command-the-storms": "Управляя штормом",
    "king-arthur:swift-strike": "Стремительный удар",
    "king-arthur:aid-the-chosen-one": "Помощь избранному",
    "king-arthur:divine-intervention": "Божественное вмешательство",
    "king-arthur:noble-sacrifice": "Благородная жертва",
    "king-arthur:restless-spirits": "Беспокойные духи",
    "king-arthur:skirmish": "Стычка",
    "king-arthur:the-holy-grail": "Святой Грааль",
    "medusa:second-shot": "Второй выстрел",
}


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def s01_cards(hero: str) -> list[dict]:
    doc = json.loads((S01 / f"content-{hero}.json").read_text(encoding="utf-8"))
    return [{"key": f"{hero}:{slug(c['name'])}", "name": c["name"], "nameRu": c.get("nameRu") or "",
             "count": int(c.get("count") or 1), "cardType": c.get("cardType")} for c in doc["cards"]]


MAIN_CHECKOUT = Path("C:/Users/ren/WebstormProjects/unmached/unmached")


def scraped_root() -> Path:
    """The scrape of this checkout, else the main checkout's (a worktree has none; scraped-data/ is gitignored)."""
    local = REPO / "scraped-data"
    return local if (local / "api" / "heroes").is_dir() else MAIN_CHECKOUT / "scraped-data"


def decode_devalue(doc: dict) -> dict:
    """SvelteKit devalue payload: nodes[2].data is a flat array of indices (the decoder of convert_card_media.py, kept
    stdlib-only here: the editor's Python has no numpy)."""
    data = doc["nodes"][2]["data"]

    def hydrate(index, depth=0):
        if depth > 64 or not isinstance(index, int) or index < 0:
            return None
        value = data[index]
        if isinstance(value, dict):
            return {k: hydrate(v, depth + 1) for k, v in value.items()}
        if isinstance(value, list):
            return [hydrate(v, depth + 1) for v in value]
        return value

    return hydrate(0)


def scrape_ru(hero: str) -> dict[str, str | None] | None:
    """{key: RU title or None} from the scrape; None when the scrape is not reachable from this checkout."""
    path = scraped_root() / "api" / "heroes" / f"{hero}.json"
    if not path.is_file():
        return None
    data = decode_devalue(json.loads(path.read_text(encoding="utf-8")))
    out = {}
    for entry in data.get("fetchedDeck") or []:
        card = entry.get("card") or {}
        title = card.get("title") or ""
        ru = ((card.get("i18n") or {}).get("ru") or {}).get("title")
        out[f"{hero}:{slug(title)}"] = ru or None
    return out


def db_snapshot(path: Path = DB_SNAPSHOT) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def read_db() -> dict:
    """Read-only query of the reference DB (:5433) through the postgres container (no password in a file or URL)."""
    sql = ('select h.name, c.name, coalesce(c."nameEn", \'\'), coalesce(c."nameRu", \'\'), c.count from "Card" c '
           'join "Hero" h on h.id = c."heroId" where h.name in (\'King Arthur\', \'Medusa\') order by h.name, c.name')
    out = subprocess.run(["docker", "exec", "unmatched-postgres", "psql", "-U", "unmatched", "-d", "unmatched", "-At",
                          "-F", "|", "-c", sql], capture_output=True, text=True, encoding="utf-8", check=True).stdout
    by_name = {v: k for k, v in HEROES.items()}
    cards = []
    for line in out.splitlines():
        hero, name, name_en, name_ru, count = line.split("|")
        cards.append({"key": f"{by_name[hero]}:{slug(name)}", "name": name, "nameEn": name_en, "nameRu": name_ru,
                      "count": int(count)})
    return {"schema": "unmatched.card-names-db/1", "source": "reference DB :5433 (docker exec unmatched-postgres psql, "
            "read-only)", "checkedAt": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "cards": cards}


def names_section() -> dict:
    db = db_snapshot()
    db_by_key = {c["key"]: c for c in (db or {}).get("cards", [])}
    cards, issues = [], []
    copies = {}
    for hero in HEROES:
        scrape = scrape_ru(hero)
        deck = s01_cards(hero)
        copies[hero] = sum(c["count"] for c in deck)
        for c in deck:
            key = c["key"]
            row = {"key": key, "nameEn": c["name"], "nameRuS01": c["nameRu"]}
            if key in db_by_key:
                row["nameRuDb"] = db_by_key[key]["nameRu"]
            if scrape is not None:
                row["nameRuScrape"] = scrape.get(key)
            if key in SCAN_RU:
                row["nameRuScan"] = SCAN_RU[key]
            data_ru = row.get("nameRuDb", c["nameRu"])
            if not data_ru or data_ru == c["name"]:
                issues.append({"key": key, "kind": "nameRu-is-en", "data": data_ru,
                               "note": "Card.nameRu holds the EN text: the RU build shows the EN name with the EN tag "
                                       "(INT-018 p. 3) until the admin fills it"})
            if scrape is not None and not row.get("nameRuScrape"):
                issues.append({"key": key, "kind": "no-ru-in-scrape", "note": "no RU title in the scrape (GAP-016)"})
            ru = row.get("nameRuScrape") or (data_ru if data_ru != c["name"] else None)
            if ru and key in SCAN_RU and ru != SCAN_RU[key]:
                issues.append({"key": key, "kind": "scan-differs", "data": ru, "scan": SCAN_RU[key],
                               "note": "the scan prints another RU name - reference for the admin (ВР-CP16)"})
            cards.append(row)
    return {
        "rule": "ВР-CP16: the client shows Card.nameRu / nameEn of the data only; scan text never goes into the client; "
                "fixes in the admin (reference DB), not in the client",
        "dbSnapshot": "art/cards-v1/card-names-db.json" if db else None,
        "dbCheckedAt": (db or {}).get("checkedAt"),
        "count": len(cards),
        "copies": copies,
        "cards": cards,
        "discrepancies": issues,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", action="store_true", help="refresh the reference DB snapshot (read-only query)")
    a = ap.parse_args(argv)
    if a.db:
        snap = read_db()
        DB_SNAPSHOT.write_text(json.dumps(snap, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
        print(f"CARD-NAMES-DB cards={len(snap['cards'])} {DB_SNAPSHOT}")
    sec = names_section()
    kinds: dict[str, int] = {}
    for i in sec["discrepancies"]:
        kinds[i["kind"]] = kinds.get(i["kind"], 0) + 1
    print(json.dumps({"count": sec["count"], "copies": sec["copies"], "discrepancies": kinds}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
