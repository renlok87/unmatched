"""registry_writer.py (C59): одна запись asset-registry.json и строки 03-asset-registry.csv по таблице статусов §10,
остальные строки файлов — байт в байт. Работает на копиях реестров чекаута (если они есть) и на синтетике.

    python -m pytest tools/art/tests/test_registry_writer.py -q
"""
from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE.parent))

import registry_writer as W  # noqa: E402

AID = "ASSET-BEOWULF-001"


def copy_of(rel: str, tmp_path: Path) -> Path:
    src = REPO / rel
    if not src.is_file():
        pytest.skip(f"{rel} нет в этом чекауте")
    dst = tmp_path / Path(rel).name
    dst.write_bytes(src.read_bytes())
    return dst


def entry_of(path: Path, aid: str) -> dict:
    return next(a for a in json.loads(path.read_text(encoding="utf-8"))["assets"] if a["id"] == aid)


def changed_lines(a: bytes, b: bytes) -> list:
    la, lb = a.split(b"\n"), b.split(b"\n")
    return [i for i, (x, y) in enumerate(zip(la, lb)) if x != y] + ([len(la)] if len(la) != len(lb) else [])


# ------------------------------------------------------------------------------------------------ asset-registry.json
def test_entry_rewrite_is_idempotent_on_the_committed_registry(tmp_path):
    reg = copy_of(W.REGISTRY, tmp_path)
    before = reg.read_bytes()
    e = entry_of(reg, AID)
    assert W.write_entry(REPO, e, "7b-probe", reg)["action"] == "replaced"
    assert reg.read_bytes() == before                                    # стиль файла воспроизведён байт в байт


def test_entry_replace_touches_only_its_lines(tmp_path):
    reg = copy_of(W.REGISTRY, tmp_path)
    before = reg.read_bytes()
    e = entry_of(reg, AID)
    e["nextStep"] = "новый шаг"
    del e["status"], e["stage"]                                          # из таблицы §10
    W.write_entry(REPO, e, "7b-frames", reg)
    after = reg.read_bytes()
    assert len(changed_lines(before, after)) == 2                       # stage (7b-frames) и nextStep
    got = entry_of(reg, AID)
    assert (got["status"], got["stage"], got["nextStep"]) == (W.TECH, "ue-editor-frames", "новый шаг")
    others = [a for a in json.loads(before)["assets"] if a["id"] != AID]
    assert others == [a for a in json.loads(after)["assets"] if a["id"] != AID]


def test_entry_append_and_status_table(tmp_path):
    reg = tmp_path / "reg.json"
    reg.write_text('{\n  "schemaVersion": 1,\n  "assets": [\n    {\n      "id": "ASSET-A-001",\n'
                   '      "status": "предложено"\n    }\n  ]\n}\n', encoding="utf-8")
    (tmp_path / "unreal/Unmatched/Content/PipelineCandidates/X").mkdir(parents=True)
    (tmp_path / "unreal/Unmatched/Content/PipelineCandidates/X/SK_X.uasset").write_bytes(b"u")
    (tmp_path / "card.yaml").write_bytes(b"c")
    e = {"id": "ASSET-X-001", "name": "X", "layers": [{"layer": "ue", "status": W.TECH, "paths": [
        {"path": "/Game/PipelineCandidates/X/SK_X", "kind": "ue-asset", "sha256": "auto"}]}],
        "evidence": [{"path": "card.yaml", "sha256": "auto"}], "plannedPaths": []}
    res = W.write_entry(tmp_path, json.loads(json.dumps(e)), "7b-probe", reg)
    assert (res["action"], res["sha256_filled"]) == ("appended", 2)
    data = json.loads(reg.read_text(encoding="utf-8"))
    assert [a["id"] for a in data["assets"]] == ["ASSET-A-001", "ASSET-X-001"]
    x = data["assets"][1]
    assert x["stage"] == "live-packaged-probe" and len(x["layers"][0]["paths"][0]["sha256"]) == 64
    text = reg.read_text(encoding="utf-8")
    assert '    },\n    {\n      "id": "ASSET-X-001",' in text and text.endswith("    }\n  ]\n}\n")
    for bad, phase, msg in (({"status": W.ART}, "7b-probe", "акт"), ({"stage": "planned"}, "7b-probe", "таблице"),
                            ({}, "4", "только на фазах"), ({"id": "Beowulf"}, "0", "ASSET-")):
        with pytest.raises(W.WriterError, match=msg):
            W.write_entry(tmp_path, dict(e, **bad), phase, reg)
    with pytest.raises(W.WriterError, match="нет файла"):
        W.write_entry(tmp_path, dict(e, evidence=[{"path": "missing.txt", "sha256": "auto"}]), "0", reg)


def test_entry_cli_dry_run(tmp_path, capsys):
    reg = copy_of(W.REGISTRY, tmp_path)
    before = reg.read_bytes()
    ef = tmp_path / "entry.json"
    ef.write_text(json.dumps(entry_of(reg, AID), ensure_ascii=False), encoding="utf-8")
    assert W.main(["entry", "--entry", str(ef), "--phase", "7b-probe", "--registry", str(reg), "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["dry_run"] is True and reg.read_bytes() == before
    assert W.main(["entry", "--entry", str(ef), "--phase", "7b-frames", "--registry", str(reg)]) == 2  # stage другой
    assert W.main(["entry", "--entry", str(ef), "--phase", "5", "--registry", str(reg)]) == 2


# ---------------------------------------------------------------------------------------- 03-asset-registry.csv
def rows_of(path: Path, prefix: str) -> list:
    return [r for r in csv.DictReader(io.StringIO(path.read_bytes().decode("utf-8-sig"))) if r["id"].startswith(prefix)]


def test_rows_upsert_keeps_crlf_and_other_lines(tmp_path):
    p = copy_of(W.CSV_03, tmp_path)
    before = p.read_bytes()
    rows = rows_of(p, "AM_Beowulf_") + rows_of(p, "SK_Beowulf_")
    assert rows, "строки Beowulf в 03"
    assert W.write_rows(REPO, [dict(r) for r in rows], "7b-art", p)["rows"][0]["action"] == "replaced"
    assert p.read_bytes() == before                                      # та же строка — тот же байт
    r0 = dict(rows[0], status="", acceptance="")
    W.write_rows(REPO, [r0], "7b-tech", p)
    after = p.read_bytes()
    assert after.count(b"\r\n") == before.count(b"\r\n") and len(changed_lines(before, after)) == 1
    got = rows_of(p, r0["id"])[0]
    assert (got["status"], got["acceptance"]) == (W.TECH, "нет")
    new = dict(rows[0], id="AM_Testo_Idle", status="", acceptance="по делегированию 2026-10-14 (ВР-17): лист")
    assert W.write_rows(REPO, [new], "7b-art", p)["rows"][0]["action"] == "appended"
    tail = p.read_bytes().split(b"\r\n")[-2]
    assert tail.startswith(b"AM_Testo_Idle,") and p.read_bytes().endswith(b"\r\n")


def test_rows_refusals(tmp_path):
    p = tmp_path / "03.csv"
    p.write_bytes("id,status,acceptance,note\r\nA,технически импортировано,нет,x\r\n".encode("utf-8"))
    with pytest.raises(W.WriterError, match="по делегированию"):
        W.write_rows(tmp_path, [{"id": "A", "acceptance": "лист осмотрен", "note": "x"}], "7b-art", p)
    with pytest.raises(W.WriterError, match="колонки"):
        W.write_rows(tmp_path, [{"id": "A", "note": "x", "extra": 1}], "7b-tech", p)
    with pytest.raises(W.WriterError, match="не по таблице"):
        W.write_rows(tmp_path, [{"id": "A", "status": W.ART, "acceptance": "по делегированию", "note": "x"}],
                     "7b-tech", p)
    W.write_rows(tmp_path, [{"id": "A", "acceptance": "GD-058 акт", "note": "y"}], "7b-art", p)
    assert p.read_bytes() == "id,status,acceptance,note\r\nA,художественно принято,GD-058 акт,y\r\n".encode("utf-8")
    rows = tmp_path / "rows.json"
    rows.write_text(json.dumps({"rows": [{"id": "B", "note": "z"}]}), encoding="utf-8")
    assert W.main(["rows", "--rows", str(rows), "--phase", "7b-tech", "--csv", str(p)]) == 0
    assert p.read_bytes().endswith("B,технически импортировано,нет,z\r\n".encode("utf-8"))
