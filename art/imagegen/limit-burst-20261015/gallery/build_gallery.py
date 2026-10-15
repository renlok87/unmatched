"""Build a self-contained, read-only gallery from frozen reviews and real concept cards.

Run from any directory: python <repo>/art/imagegen/limit-burst-20261015/gallery/build_gallery.py
Only this script's gallery directory is written. No service, network or source mutation.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
from html import escape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys

GALLERY = Path(__file__).resolve().parent
ROOT = GALLERY.parents[3]
BURST = GALLERY.parent
INPUTS: dict[str, str] = {}
ERRORS: list[str] = []
PENDING: list[dict] = []
NAMES = {
    "achilles": "Ахиллес", "wolf": "Волк", "wiglaf": "Виглаф", "robin-hood": "Робин Гуд",
    "sherlock-holmes": "Шерлок Холмс", "nikola-tesla": "Никола Тесла", "faith": "Фейт",
    "beowulf": "Беовульф", "giles": "Джайлз", "daisy": "Дейзи", "angel": "Ангел",
    "ancient-leshen": "Древний Леший", "dr-jill-trent": "Доктор Джилл Трент", "dr-watson": "Доктор Ватсон",
    "yennenga": "Йенненга", "sinbad": "Синдбад", "little-red": "Красная Шапочка", "dracula": "Дракула",
    "annie-christmas": "Энни Кристмас", "outlaws": "Разбойники", "dr-malcolm": "Доктор Малкольм",
    "charlie": "Чарли", "yennenga-archer": "Лучник Йенненги", "patroclus": "Патрокл", "buffy": "Баффи",
    "dr-sattler": "Доктор Сэттлер", "xander": "Ксандер", "drusilla": "Друзилла", "tara": "Тара",
    "blackbeard": "Чёрная Борода", "harry-houdini": "Гарри Гудини", "oda-nobunaga": "Ода Нобунага",
    "bruce-lee": "Брюс Ли", "shuri": "Шури", "maria-hill": "Мария Хилл", "wong": "Вонг",
    "dandelion": "Лютик", "bess-houdini": "Бесс", "huntsman": "Охотник", "rosencrantz": "Розенкранц и Гильденстерн",
    "ashigaru": "Почётный страж · Асигару", "spike": "Спайк", "willow": "Уиллоу",
    "geralt-of-rivia": "Геральт из Ривии", "philippa": "Филиппа", "ingen-worker": "Работник InGen",
    "actor": "Актёр", "metalhead": "Металхед", "misty-knight": "Мисти Найт", "splinter": "Сплинтер",
    "april-oneil": "Эйприл О’Нил", "april-o-neil": "Эйприл О’Нил", "casey-jones": "Кейси Джонс",
    "dijkstra": "Дийкстра", "mariahill": "Мария Хилл",
    "black-panther": "Чёрная Пантера", "black-widow": "Чёрная Вдова",
    "doctor-strange": "Доктор Стрэндж", "elektra": "Электра",
    "titania": "Титания", "shakespeare": "Шекспир", "william-shakespeare": "Шекспир", "oberon": "Оберон",
}
TYPE_LABELS = {"portraits": "Портрет", "helper-ref": "Референс помощника", "formalconcept": "Формальный концепт 1c"}
STATUS_LABELS = {"proposed": "Предложен исходник", "alternative": "Архивный вариант", "pass": "Концепт 1c принят", "rejected": "Возвращён на этап 1", "blocked": "PNG не создан"}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def repo_path(value: str) -> Path:
    candidate = ROOT / value.replace("\\", "/")
    resolved = candidate.resolve()
    if not resolved.is_relative_to(ROOT) or Path(value).is_absolute():
        raise ValueError("Path escapes repository: " + value)
    return resolved


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def read_json(path: Path):
    INPUTS[rel(path)] = sha(path)
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(name: str, text: str):
    target = GALLERY / name
    assert target.parent.resolve() == GALLERY
    target.write_text(text, encoding="utf-8")


def json_text(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2) + "\n"


def png(value: str, expected: str | None, label: str) -> dict:
    path = repo_path(value)
    if not path.is_file() or path.suffix.lower() != ".png":
        raise ValueError("Actual PNG missing: " + value)
    actual = sha(path)
    if expected is not None and (not re.fullmatch(r"[a-fA-F0-9]{64}", expected) or actual != expected.lower()):
        raise ValueError("PNG SHA differs from review/card: " + value)
    with path.open("rb") as stream:
        header = stream.read(24)
    if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError("Invalid PNG header: " + value)
    width, height = struct.unpack(">II", header[16:24])
    INPUTS[rel(path)] = actual
    return {"path": rel(path), "sha256": actual, "width": width, "height": height, "label": label}


def nearest_readme(path: Path) -> str | None:
    for parent in [path.parent, *path.parents]:
        candidate = parent / "README.md"
        if candidate.is_file():
            return rel(candidate)
        if parent == BURST or parent == ROOT:
            break
    return None


def optional_link(value: str | None) -> str | None:
    if not value:
        return None
    try:
        path = repo_path(value)
        return rel(path) if path.is_file() else None
    except (ValueError, OSError):
        return None


def slug_for(row: dict) -> str:
    if row.get("visual_asset_key"):
        return row["visual_asset_key"]
    path = Path(row["file"])
    parts = path.parts
    for bucket in ["design", "concepts"]:
        if bucket in parts:
            return parts[parts.index(bucket) - 1]
    return path.parent.name


def source_entry(row: dict, index: Path, wave: int) -> dict:
    asset = str(row.get("asset", row.get("file", "")))
    path = repo_path(row["file"])
    slug = slug_for(row)
    is_portrait = asset.startswith("portrait:") or "portrait" in path.name
    kind = "portraits" if is_portrait else "helper-ref"
    status = "alternative" if "alternative" in str(row.get("disposition", "")) else "proposed"
    if any(word in str(row.get("disposition", "")).lower() for word in ["reject", "do_not_use"]):
        status = "rejected"
    image = png(row["file"], row.get("sha256") or "missing", "Исходный PNG")
    readme = nearest_readme(path)
    review_readme = index.parent / "README.md"
    owner = row.get("actual_sidekick_name") or row.get("game_name")
    return {
        "id": "source:" + image["path"], "asset": asset, "slug": slug,
        "label": NAMES.get(slug, owner or slug.replace("-", " ").title()), "type": kind,
        "type_label": TYPE_LABELS[kind], "status": status, "status_label": STATUS_LABELS[status],
        "batch": str(wave), "batch_label": "Волна " + str(wave),
        "description": row.get("visual_review") or row.get("identity") or row.get("recommendation") or "",
        "limits": row.get("limits", []), "recommendation": row.get("recommendation", ""),
        "crop_review": row.get("crop_review", ""), "native_review": row.get("native_review", ""),
        "disposition": row.get("disposition", ""), "images": [image], "producer_readme": readme,
        "independent_review": rel(review_readme) if review_readme.is_file() else rel(index),
        "review_index": rel(index), "diagnostic": optional_link(row.get("diagnostic")),
        "formal_card": None, "score": None, "runtime_accepted": False, "pipeline_stage_accepted": False,
        "reference": str(row.get("reference", "")),
    }


def formal_entry(key: str, card_path: Path) -> dict:
    card = read_json(card_path)
    images = []
    for obj in card.get("accepted_object", []):
        name = Path(obj["path"]).stem
        view = "Спереди" if name.endswith("-front") else "Сбоку" if name.endswith("-side") else "Сзади" if name.endswith("-back") else name
        images.append(png(obj["path"], obj.get("sha256") or "missing", view))
    if len(images) != 3:
        raise ValueError("Formal card must bind actual front/side/back PNGs: " + rel(card_path))
    limits = [i.get("note", "") for i in card.get("known_issues", []) if i.get("note")]
    limits += [(i.get("item", "") + ": " + i.get("fix", "")) for i in card.get("rework_fix_list", [])]
    limits.append("Оценка относится только к перечисленным 2D-видам концепта 1c; это не приёмка модели, рига, анимации или runtime.")
    if key == "wiglaf":
        verification_path = ROOT / "art/imagegen/concept-wiglaf-codex/verification.json"
        if verification_path.is_file():
            verification = read_json(verification_path)
            if verification.get("corrective_goal_achieved") is False:
                limits.append("Коррекция S в design-front g3/g4 не достигнута, лимит 4/4 исчерпан; canonical принятый 1a g2 сохранён. Новый draft по g3/g4 не разрешён.")
    status = "pass" if card["verdict"] == "pass" else "rejected"
    first = repo_path(images[0]["path"])
    return {
        "id": "formal:" + card["asset_id"], "asset": card["asset_id"], "slug": key, "label": NAMES[key],
        "type": "formalconcept", "type_label": TYPE_LABELS["formalconcept"], "status": status,
        "status_label": STATUS_LABELS[status], "batch": "formal", "batch_label": "Приёмка 1c",
        "description": card.get("status_note") or card.get("verdict_reason") or "Формальная карточка приёмки концепта 1c.",
        "limits": limits, "recommendation": "", "crop_review": "", "native_review": "", "images": images,
        "producer_readme": nearest_readme(first), "independent_review": rel(card_path), "review_index": None,
        "formal_card": rel(card_path), "diagnostic": optional_link(rel(first.parent / ("sheet-" + key + ".png"))),
        "score": card["score"], "formal_verdict": card["verdict"], "runtime_accepted": False,
        "pipeline_stage_accepted": card["verdict"] == "pass", "accepted_stage": "1c" if status == "pass" else None,
        "reference": "SHA каждого вида совпадает с accepted_object реальной карточки.",
    }


def review_paths(burst: Path) -> list[tuple[int, Path]]:
    """Existing numeric review directories, ordered numerically; no future waves invented."""
    directories = {1: burst / "review"}
    for path in burst.iterdir():
        match = re.fullmatch(r"review-wave([1-9][0-9]*)", path.name)
        if path.is_dir() and match and int(match[1]) >= 2:
            directories[int(match[1])] = path
    return [(wave, path / "independent-review-index.json") for wave, path in sorted(directories.items())]


def blocked_entry(row: dict, index: Path, wave: int) -> dict:
    asset = row["asset"]
    if not isinstance(asset, str) or not asset or row.get("candidate_exists") or row.get("reviewed_as_image"):
        raise ValueError("Blocked review must describe an absent image: " + rel(index))
    error_path = repo_path(row["error_evidence"])
    error = read_json(error_path)
    expected = row.get("error_evidence_sha256")
    if expected is not None and INPUTS[rel(error_path)] != expected:
        raise ValueError("Blocked error SHA differs from frozen review: " + rel(error_path))
    package = error_path.parent
    if row.get("file") or any((package / name).exists() for name in ("portrait-source-candidate.png", "portrait-source.png", "design-front.png")):
        raise ValueError("Blocked review has an output image; inspect source state: " + asset)
    slug = asset.rsplit(":", 1)[-1]
    kind = "portraits" if asset.startswith("portrait:") else "helper-ref"
    review_readme = index.parent / "README.md"
    request = row.get("request_id") or error.get("request_id")
    return {"id": "blocked:" + asset, "asset": asset, "slug": slug, "label": NAMES.get(slug, slug.replace("-", " ").title()),
        "type": kind, "type_label": TYPE_LABELS[kind], "status": "blocked", "status_label": STATUS_LABELS["blocked"],
        "batch": str(wave), "batch_label": "Волна " + str(wave),
        "description": row.get("reason") or "Неуспешный вызов генератора. Изображение не создано.",
        "limits": ["PNG отсутствует; здесь нет превью, SHA изображения или синтетической замены.", "Отказ относится к вызову инструмента, а не к художественной приёмке."],
        "images": [], "producer_readme": optional_link(rel(package / "README.md")),
        "independent_review": rel(review_readme) if review_readme.is_file() else rel(index), "review_index": rel(index),
        "formal_card": None, "diagnostic": rel(error_path), "score": None, "runtime_accepted": False,
        "pipeline_stage_accepted": False, "reference": "request ID " + str(request) if request else "",
    }


def card_html(entry: dict, position: int) -> str:
    e = escape
    image = entry["images"][0] if entry["images"] else None
    if image:
        visual = '<img loading="lazy" decoding="async" data-image="' + e(image["path"], quote=True) + '" width="' + str(image["width"]) + '" height="' + str(image["height"]) + '" alt="' + e(entry["label"], quote=True) + ' — весь исходный кадр">'
    else:
        visual = '<div class="blocked-message"><span class="blocked-sign" aria-hidden="true">×</span><strong>Изображение не создано</strong><span>Отказ сервиса · без PNG</span></div>'
    score = '<span class="score">' + e(str(entry["score"]).replace(".", ",")) + '<small>/10 · 1c</small></span>' if entry.get("score") is not None else ""
    direct = ('<a class="direct" data-repo="' + e(image["path"], quote=True) + '" href="../../../../' + e(image["path"], quote=True) + '" target="_blank" rel="noopener">Открыть PNG ↗</a>') if image else '<span class="no-png">Нет PNG</span>'
    subtitle = entry["asset"]
    return '<article class="asset-card" data-id="' + e(entry["id"], quote=True) + '"><div class="card-top"><span>' + str(position).zfill(2) + ' / ' + e(entry["type_label"]) + '</span>' + score + '</div><button class="preview" data-open="' + e(entry["id"], quote=True) + '" aria-label="' + e("Подробнее: " + entry["label"], quote=True) + '">' + visual + '</button><div class="card-body"><span class="status status-' + e(entry["status"]) + '">' + e(entry["status_label"]) + '</span><h2>' + e(entry["label"]) + '</h2><p class="asset-key">' + e(subtitle) + '</p><div class="card-foot"><button class="text-button" data-open="' + e(entry["id"], quote=True) + '">Ревью и файлы <span aria-hidden="true">→</span></button>' + direct + '</div></div></article>'


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.ids = set()
        self.scripts = {}
        self.script_id = None
        self.cards = 0
        self.card_images = {}
        self.card_png_links = {}
        self.current_card = None

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        if attr.get("id"):
            if attr["id"] in self.ids:
                raise ValueError("Duplicate HTML id: " + attr["id"])
            self.ids.add(attr["id"])
        if tag == "article" and attr.get("data-id"):
            self.cards += 1
            self.current_card = attr["data-id"]
            self.card_images[self.current_card] = []
            self.card_png_links[self.current_card] = []
        if tag == "img":
            if any(key in attr and not attr[key] for key in ("src", "data-image")):
                raise ValueError("Empty HTML image source")
            if self.current_card and attr.get("data-image"):
                self.card_images[self.current_card].append(attr["data-image"])
        if tag == "a" and self.current_card and str(attr.get("data-repo", "")).lower().endswith(".png"):
            self.card_png_links[self.current_card].append(attr["data-repo"])
        if tag == "script":
            self.script_id = attr.get("id")
            self.scripts[self.script_id] = ""
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag:
            raise ValueError("HTML tags not balanced at </" + tag + ">")
        if tag == "script":
            self.script_id = None
        if tag == "article":
            self.current_card = None

    def handle_data(self, text):
        if self.script_id is not None:
            self.scripts[self.script_id] += text


def main() -> int:
    INPUTS.clear()
    ERRORS.clear()
    PENDING.clear()
    sources = {}
    blocked = {}
    indexes = []
    for wave, index in review_paths(BURST):
        if not index.is_file():
            PENDING.append({"wave": wave, "reason": "Индекс пока отсутствует"})
            continue
        data = read_json(index)
        if not data.get("frozen"):
            PENDING.append({"wave": wave, "reason": "Индекс ещё не заморожен"})
            continue
        indexes.append({"path": rel(index), "sha256": INPUTS[rel(index)], "wave": wave, "frozen_at_utc": data.get("frozen_at_utc")})
        for row in data.get("reviewed_outputs", []):
            try:
                entry = source_entry(row, index, wave)
                sources[entry["images"][0]["path"]] = entry
            except (ValueError, KeyError, OSError) as exc:
                ERRORS.append(str(exc))
        for row in data.get("blocked_outputs", []):
            try:
                entry = blocked_entry(row, index, wave)
                blocked[entry["asset"]] = entry  # Later frozen evidence replaces the same blocked asset, without duplicates.
            except (ValueError, KeyError, OSError) as exc:
                ERRORS.append(str(exc))
    entries = list(sources.values()) + list(blocked.values())
    for key in ["patroclus", "wiglaf", "sherlock-holmes", "dr-watson"]:
        directory = ROOT / ("art/pipeline-candidates/ASSET-" + key.upper() + "-001/evidence/acceptance-concept")
        candidates = sorted(directory.glob("*-sheet-*/card.json"))
        if not candidates:
            PENDING.append({"asset": key, "reason": "Формальная карточка 1c пока отсутствует"})
            continue
        try:
            entries.append(formal_entry(key, candidates[-1]))
        except (ValueError, KeyError, OSError) as exc:
            ERRORS.append(str(exc))
    entries.sort(key=lambda i: ({"portraits": 0, "helper-ref": 1, "formalconcept": 2}[i["type"]], i["label"].casefold()))
    counts = {"entries": len(entries), "png_views": sum(len(e["images"]) for e in entries), "types": dict(Counter(e["type"] for e in entries)), "statuses": dict(Counter(e["status"] for e in entries))}
    data = {"schema": "unmatched.local-gallery/1", "built_at_utc": datetime.now(timezone.utc).isoformat(), "scope": "Frozen independent source reviews plus actual formal 1c cards. No runtime acceptance inferred.", "counts": counts, "review_indexes": indexes, "pending_reviews": PENDING, "entries": entries}
    template_path = GALLERY / "gallery.template.html"
    template = template_path.read_text(encoding="utf-8")
    embedded = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c").replace("&", "\\u0026")
    html = template.replace("__GALLERY_DATA__", embedded).replace("__GALLERY_CARDS__", "\n".join(card_html(e, i + 1) for i, e in enumerate(entries))).replace("__TOTAL__", str(len(entries))).replace("__BUILT_AT__", escape(data["built_at_utc"][:16].replace("T", " ") + " UTC"))
    if "__GALLERY_" in html:
        raise ValueError("Unexpanded gallery template token")
    parser = PageParser()
    parser.feed(html)
    parser.close()
    assert not parser.stack and parser.cards == len(entries)
    assert len({entry["id"] for entry in entries}) == len(entries), "Duplicate gallery entry id"
    for entry in entries:
        expected = [entry["images"][0]["path"]] if entry["images"] else []
        assert parser.card_images[entry["id"]] == expected
        if entry["status"] == "blocked":
            assert not entry["images"] and not parser.card_png_links[entry["id"]]
            assert entry.get("sha256") is None and entry["score"] is None
        if entry["type"] != "formalconcept":
            assert entry["pipeline_stage_accepted"] is False and entry["runtime_accepted"] is False
    assert json.loads(parser.scripts["gallery-data"]) == data
    assert 'object-fit: contain' in html and 'object-fit: cover' not in html
    js_check = "node unavailable; JSON/HTML/path/hash validation performed"
    if shutil.which("node"):
        check = subprocess.run(["node", "--check"], input=parser.scripts["gallery-ui"], text=True, encoding="utf-8", capture_output=True)
        if check.returncode:
            raise ValueError("Inline JavaScript syntax error: " + check.stderr)
        js_check = "node --check stdin: pass"
    for entry in entries:
        for field in ["producer_readme", "independent_review", "review_index", "diagnostic", "formal_card"]:
            if entry.get(field) and not repo_path(entry[field]).is_file():
                ERRORS.append("Gallery link missing: " + entry[field])
    changed = [p for p, before in INPUTS.items() if sha(repo_path(p)) != before]
    if changed:
        ERRORS.extend("Input changed during build: " + p for p in changed)
    verification = {"counts": counts, "json_parsed": True, "html_parsed_balanced": True, "embedded_json_matches_data": True, "javascript_syntax": js_check, "uncropped_thumbnails": "object-fit: contain; original width/height; only actual PNG paths", "numeric_review_waves": [item["wave"] for item in indexes], "blocked_entries_text_only": all(not entry["images"] for entry in blocked.values()), "blocked_asset_ids_unique": len(blocked) == len({entry["asset"] for entry in blocked.values()}), "html_images_match_actual_entries": True, "empty_image_sources": 0, "source_entries_inherit_no_formal_acceptance": True, "geralt_has_no_image": not blocked.get("portrait:geralt-of-rivia", {}).get("images"), "input_content_files_verified": len(INPUTS), "source_content_unchanged_during_build": not changed, "pending_reviews": PENDING, "errors": ERRORS, "network_gui_server_framework_build_used": False, "source_writes": [], "output_directory_only": rel(GALLERY)}
    write("gallery-data.json", json_text(data))
    write("index.html", html)
    write("verification.json", json_text(verification))
    write("input-hashes.json", json_text(INPUTS))
    manifest = {"files": [{"path": rel(p), "sha256": sha(p), "bytes": p.stat().st_size} for p in sorted(GALLERY.iterdir()) if p.is_file() and p.name != "manifest-sha256.json"]}
    write("manifest-sha256.json", json_text(manifest))
    assert all(sha(repo_path(r["path"])) == r["sha256"] for r in manifest["files"])
    print(json.dumps({"gallery": rel(GALLERY / "index.html"), **counts, "review_indexes": len(indexes), "pending_reviews": PENDING, "manifest_files": len(manifest["files"]), "errors": ERRORS}, ensure_ascii=False))
    return 1 if ERRORS else 0


if __name__ == "__main__":
    sys.exit(main())
