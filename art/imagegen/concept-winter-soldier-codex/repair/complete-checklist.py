"""Complete the selected design's visual CHECKLIST; no image writes or checker calls."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import shutil

P = Path("art/imagegen/concept-winter-soldier-codex")
EXPECTED = "742d0d500316a0a2bea57583d55590d3a8a232b57973269084d379da4c65444a"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, data):
    path.resolve().relative_to(P.resolve())
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


v = json.loads((P / "verification.json").read_text(encoding="utf-8"))
assert sha(P / "design/winter-soldier-front.png") == EXPECTED
assert v["record_count"] == 2 and v["image_generations_this_run"] == 0
assert v["final_checker_exit_code"] == 0
now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
archive = P / "archive" / f"before-visual-checklist-{stamp}"
archive.mkdir(parents=True, exist_ok=False)
snapshots = []
for name in ("verification.json", "README.md", "prompts.md", "manifest-sha256.json"):
    source, target = P / name, archive / name
    assert not target.exists()
    shutil.copyfile(source, target)
    assert source.read_bytes() == target.read_bytes()
    snapshots.append({"path": source.as_posix(), "archive_path": target.as_posix(),
                      "sha256": sha(source), "bytes": source.stat().st_size})
write_json(archive / "snapshot-index.json", {"date": now, "files": snapshots})

notes = [
    (False, "Одна фигура и одна подставка, без коллажа и второго вида. Однако на рукаве справа для зрителя виден шеврон с белыми буквами/эмблемой; на подставке есть белая графическая отметка. Требование отсутствия текста/логотипов не соблюдено."),
    (False, "Фигура смотрит вперёд, но верхняя поверхность подставки отчётливо видна как широкий эллипс. Строгое ребро подставки без видимого верха и ортографичность не подтверждаются."),
    (True, "Вся фигура, оружие и подставка находятся внутри кадра; фон тёмно-серый и плоский. Checker: border_uniform PASS, top/bottom/side_margin PASS. WARN frame_top=2,875% отдельно сохранён."),
    (False, "Винтовка удерживается поперёк торса двумя руками; кисть справа для фигуры (слева для зрителя) находится у спусковой зоны. Предплечья проходят перед торсом: требуемая нейтральная поза со слегка отведёнными руками и видимыми зазорами не соблюдена."),
    (False, "Винтовка, чёрная тактическая экипировка, маска и красная звезда видны. Серебряная рука расположена слева для зрителя, то есть это ПРАВАЯ рука фигуры; требование металлической ЛЕВОЙ руки нарушено."),
    (True, "Видны чёрный, серебряный, серый и красная звезда. Командная окраска, цветное кольцо или металлическая полоса подставки не видны. Белые буквы/отметка учтены как нарушение первого пункта."),
]
assert len(v["checklist"]) == len(notes)
for entry, (passed, note) in zip(v["checklist"], notes):
    entry.update({"passed": passed, "status": "PASS" if passed else "FAIL", "note": note,
                  "assessment": "visual checklist only; no art acceptance"})
failed_items = [entry["item"] for entry in v["checklist"] if not entry["passed"]]
v["checklist_completed"] = True
v["visual_check"] = {"date": now, "source": (P / "design/winter-soldier-front.png").as_posix(),
                     "sha256": EXPECTED, "method": "view_image original; read-only visual checklist",
                     "art_acceptance_performed": False, "failed_item_count": len(failed_items)}
v["limit_reached"] = [{"view": "design-front", "failed_items": failed_items,
                       "generations_allowed": 0, "generations_used_this_run": 0,
                       "reason": "Генерации и изменения PNG запрещены; существующий дизайн выбран пользователем. Неудачи CHECKLIST сохранены для приёмщика."}]
v["limitations"][0] = "CHECKLIST проверен визуально: четыре пункта FAIL, два PASS. Это фиксация ограничений, а не художественная приёмка. Изображение не исправлялось."
v["checklist_finalization_archive"] = {"path": archive.as_posix(), "files": snapshots}
v["status"] = "proposed"
v["status_ru"] = "предложено"
v["blocker"] = None
write_json(P / "verification.json", v)

readme_path = P / "README.md"
readme = readme_path.read_text(encoding="utf-8")
old = "- CHECKLIST визуально не переоценивался: passed=null означает непроверенный пункт, а не положительный вердикт. Историческая заметка Claude сохранена отдельно."
new = "- CHECKLIST выбранного дизайна проверен визуально, без художественной приёмки: 4 FAIL, 2 PASS. FAIL: буквы/эмблема на шевроне и белая отметка на базе; видимая верхняя поверхность подставки; оружие поперёк торса и не требуемая нейтральная поза рук; металлическая рука справа для фигуры вместо слева. Каждый пункт описан в verification.json.\n- limit_reached фиксирует эти четыре пункта при разрешённых 0 генераций. Они оставлены приёмщику; PNG не исправлялись."
assert old in readme
readme = readme.replace(old, new)
readme += f"\nПеред заполнением визуального CHECKLIST промежуточные метаданные сохранены в `{archive.relative_to(P).as_posix()}/`.\n"
readme_path.write_text(readme, encoding="utf-8")

prompts_path = P / "prompts.md"
prompts = prompts_path.read_text(encoding="utf-8")
old = "Визуальная приёмка и визуальная переоценка CHECKLIST не выполнены. Статус — предложено."
new = "CHECKLIST выбранного PNG проверен визуально: четыре пункта FAIL, два PASS; подробности и limit_reached находятся в verification.json. Художественная приёмка не выполнялась. Статус — предложено."
assert old in prompts
prompts_path.write_text(prompts.replace(old, new), encoding="utf-8")

for row in v["png_hash_preservation"]:
    path = Path(row["path"])
    assert sha(path) == row["before"]["sha256"] and path.stat().st_size == row["before"]["bytes"]
selected = Path(v["selected"]["candidate"])
assert selected.read_bytes() == (P / "design/winter-soldier-front.png").read_bytes()
for row in snapshots:
    assert sha(Path(row["archive_path"])) == row["sha256"]
manifest_path = P / "manifest-sha256.json"
files = [{"path": path.relative_to(P).as_posix(), "sha256": sha(path), "bytes": path.stat().st_size}
         for path in sorted(P.rglob("*")) if path.is_file() and path != manifest_path]
write_json(manifest_path, {"schema": "unmatched.concept-manifest/1", "generated_at": now,
                           "path_base": P.as_posix(), "files": files})
for row in files:
    path = P / row["path"]
    assert sha(path) == row["sha256"] and path.stat().st_size == row["bytes"]
print(json.dumps({"checklist_failed": len(failed_items), "manifest_verified_files": len(files),
                  "image_generations_this_run": 0, "status": "proposed"}, ensure_ascii=False))
