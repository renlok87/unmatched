"""Write honest self-reviews for the six completed wave-three image generations."""
from pathlib import Path
import json

WAVE = Path(__file__).resolve().parents[1]
ORIGINAL_DIR = "C:/Users/ren/.codex/generated_images/01a13e0e-695c-71e2-9124-c660b061b646/"
SPECS = {
    "xander": {
        "title": "Xander — original practical-companion reference",
        "files": ["exec-a8ec484a-c4ee-4d79-bd8d-dc48b05dae20.png", "exec-c87c97dc-394d-4fd2-9532-eaafdda5df35.png"],
        "summary": "Xander подтверждён у Buffy свежим read-only запросом живого Hero.sidekicks и сырым owner JSON: melee, health 6, movement 3. Во всём текущем инвентаре не было отдельного concept/card или известного alias. Создан оригинальный взрослый повседневный помощник в синей клетчатой рубашке с одним деревянным колом в правой руке. Выбран g2 с подставкой ребром; лицо не задано по актёрскому портрету.",
        "anchors": "short dark-brown hair; muted-blue checked overshirt; charcoal T-shirt; tan work trousers; one wooden stake in own RIGHT hand; empty left hand",
        "arm_gap_pass": True,
        "extras": [
            "Возраст, лицо, одежда и кол — делегированная оригинальная интерпретация роли; данные подтверждают имя, владельца и механику, но не эти визуальные детали.",
            "g2 сохранил основные anchors, но поменял лицо, складки и детали рабочих брюк. Это два варианта front, не согласованные виды одной модели."
        ],
    },
    "drusilla": {
        "title": "Drusilla — original vampire-companion reference",
        "files": ["exec-95ed73c7-ddd8-44f7-8500-b66b5ceafa7c.png", "exec-2bcc91c0-7a21-4556-b189-d4f2b6b16d99.png"],
        "summary": "Drusilla подтверждена у Spike свежим read-only запросом живого Hero.sidekicks и сырым owner JSON: melee, health 7, movement 2. Точного concept/card или alias не найдено. Создана оригинальная взрослая вампирша в закрытом старинном платье цвета слоновой кости с бордовым поясом и пустыми руками. Выбран g2: база стала ребром, волосы перенесены назад частично; остаточные пряди ещё занимают часть зазоров у локтей.",
        "anchors": "long centrally parted dark hair; pale original adult face; high-neck ivory antique gown; burgundy sash with small brass buckle; empty hands",
        "arm_gap_pass": False,
        "extras": [
            "Открытые кисти читаются, но длинные волосы всё ещё пересекают части промежутков локоть–корпус. Пункт чистых зазоров не выполнен полностью; это сохранённое ограничение после единственной коррекции.",
            "Костюм, лицо и причёска — оригинальная интерпретация по делегированию. Фотографии, actor likeness, кукла, кровь и baked-in FX не запрашивались и не подавались."
        ],
    },
    "tara": {
        "title": "Tara — original scholarly-caster reference",
        "files": ["exec-5092425d-cced-460e-8180-02983dd34cda.png", "exec-7e1f8eaf-b88a-48e9-8b71-11aa1450f4c0.png"],
        "summary": "Tara подтверждена у Willow свежим read-only запросом живого Hero.sidekicks и сырым owner JSON: range, health 6, movement 2. Точного concept/card или alias не найдено. Создана оригинальная взрослая спокойная заклинательница с медово-светлыми волосами, синим кардиганом, кремовой блузой, коричневой юбкой и пустыми руками. Выбран g2 с подставкой ребром; ranged-роль оставлена для будущих эффектов, без нарисованного заклинания на исходнике.",
        "anchors": "honey-blonde loosely half-tied hair; indigo hip-length cardigan; cream blouse; brown ankle-length skirt; plain small silver pendant; empty relaxed hands",
        "arm_gap_pass": True,
        "extras": [
            "Возраст, лицо, волосы, костюм и украшение — делегированная оригинальная интерпретация, не канонический портрет и не копия актрисы.",
            "g2 изменил причёску и мелкие детали кардигана, сохранив основные anchors. Ладони пустые, без книги, посоха и baked-in magic FX."
        ],
    },
}

for key, spec in SPECS.items():
    out = WAVE / key
    provenance = json.loads((out / "provenance.json").read_text(encoding="utf-8"))
    checks = [json.loads((out / ("checks/design-front-g" + str(i) + "/checks-report.json")).read_text(encoding="utf-8")) for i in [1, 2]]
    mask = checks[1]["measurements"]["front"]["mask"]
    review = {
        "asset_id": provenance["proposed_asset_id"], "visual_card_id": "AN-151", "title": spec["title"],
        "stage": "production-reference-only; formal pipeline not started", "view": "design-front", "selected": True,
        "status": "proposed-production-reference-only",
        "generations": [{"attempt": i, "selected": i == 2, "original_path": ORIGINAL_DIR + spec["files"][i - 1], "image": "concepts/" + key + "-design-front-g" + str(i) + ".png", "prompt_file": "prompts/design-front-g" + str(i) + ".txt"} for i in [1, 2]],
        "summary_ru": spec["summary"],
        "checklist": [
            {"item": "one complete adult humanoid figure, one base, no text or extra limbs", "passed": True},
            {"item": spec["anchors"], "passed": True},
            {"item": "frontal body with clear arm/background gaps", "passed": spec["arm_gap_pass"], "note": "Hair still occupies portions of the elbow/body spaces." if not spec["arm_gap_pass"] else "Visible gaps on visual self-review."},
            {"item": "g2 base visually edge-on with no large top ellipse", "passed": True, "note": "Visual observation only; camera parameters cannot be recovered from this raster."},
            {"item": "exact CORE top/bottom framing", "passed": False, "note": "Selected top " + str(mask["top_pct"]) + "% (required >=4), bottom " + str(mask["bottom_pct"]) + "% (target93)."},
        ],
        "limitations": [
            "Оба кандидата: 12 PASS / 1 WARN / 0 FAIL; WARN view.frame_top сохранён. Выбранный g2: верх " + str(mask["top_pct"]) + "%, низ " + str(mask["bottom_pct"]) + "% вместо целевых >=4% / 93%.",
            "g1 показывает верх подставки; g2 убирает явный верхний эллипс, но строгая ортография камеры математически не подтверждена. Фон визуально почти ровный; полное равенство каждого пикселя не заявлено.",
            "На ассет выполнено ровно два вызова: исходный и одна коррекция фактического дефекта базы; у Drusilla той же коррекцией улучшались зазоры у рук. Дополнительных генераций не требуется в этом scope.",
            "Два front-кандидата не являются набором 1c. Нужны отдельные intake, независимая design acceptance и следующие гейты; 3D, риг, Tripo, анимация и UE не выполнялись.",
        ] + spec["extras"],
    }
    (out / "review.json").write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
