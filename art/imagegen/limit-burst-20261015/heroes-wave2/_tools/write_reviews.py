from pathlib import Path
import json

WAVE = Path(__file__).resolve().parents[1]
ORIGINAL_DIR = "C:/Users/ren/.codex/generated_images/01a13e0e-695c-71e2-9124-c660b061b646/"
SPECS = {
    "charlie": {
        "title": "Charlie — original ranged riverboat-helper reference",
        "files": ["exec-1d0d566f-f7e2-424d-9bfb-e3ed309a3c80.png", "exec-e6a37c85-c536-4fbc-afa5-914082d4c55a.png"],
        "summary": "Charlie подтверждён у Annie Christmas живым read-only запросом Hero.sidekicks и сырым scraped owner JSON: range, health 8, movement 2. Отдельных Charlie-пакетов или remap в hero-links не найдено. Создан оригинальный взрослый речной помощник с одним компактным старинным пистолетом: это делегированная интерпретация ranged-роли, не скопированный аватар. Выбран g2: лицо обращено к зрителю, подставка стала ребром.",
        "anchors": "navy cap/waistcoat, rolled cream shirt, turquoise neckerchief, one pistol in own right hand, empty left hand",
        "extras": [
            "g1 заметно поворачивал голову; g2 это исправил. Нос, взгляд и плечи фронтальны.",
            "Возраст, телосложение, одежда и пистолет выбраны оригинально по делегированию. Источник подтверждает имя и ranged-механику, но не эти визуальные детали."
        ],
    },
    "dr-malcolm": {
        "title": "Dr. Malcolm — original scientific-adviser reference",
        "files": ["exec-3f4c6df8-1e72-4bf2-9446-d6143c33d13e.png", "exec-5b560a5b-a03b-4a85-9923-21231c11623f.png"],
        "summary": "Dr. Malcolm подтверждён у Dr. Sattler живым read-only запросом Hero.sidekicks и сырым scraped owner JSON: melee, health 7, movement 2. В игровом поле имя именно Dr. Malcolm; пользователь назвал Dr. Ian Malcolm. Создан оригинальный научный советник в чёрной рубашке и очках, с пустыми руками. Actor likeness и фотографии людей не использовались. Выбран g2 с исправленной проекцией базы.",
        "anchors": "clear spectacles, short wavy dark hair, black rolled-sleeve open-collar shirt, charcoal trousers, empty hands",
        "extras": [
            "g2 улучшил подставку, но также изменил лицо, ворот и складки одежды; это два альтернативных front, не согласованные виды одной модели.",
            "Точная внешность и одежда — оригинальное решение по делегированию. Исходные данные не задают лицо или костюм; актёрский портрет не подавался и не запрашивался."
        ],
    },
    "yennenga-archer": {
        "title": "Yennenga Archers — one original representative reference",
        "files": ["exec-a5129437-3224-40ee-91bb-8476e9fab8c6.png", "exec-eec24409-1d5a-4e35-900c-419a4c25e5f1.png"],
        "summary": "У Yennenga живой Hero.sidekicks и сырой owner JSON содержат двух одинаковых Archers: range, health 2, movement 2 каждый. GameInitializationService разбирает этот список, создаёт бойцов с их именами и нормализованными attack types. Готового пакета или remap в hero-links не обнаружено. Создан один оригинальный репрезентативный лучник для будущего использования двумя равноценными фишками; не две разные фигуры. Выбран g2 с проекцией базы ребром, лук слева у персонажа, колчан справа.",
        "anchors": "one bow in own LEFT hand, quiver at own RIGHT hip, ochre wrap, leather tunic/sandals, red headband, empty right hand",
        "extras": [
            "Один archetype для двух runtime Archers; командные кольца, нумерация или baked-in team colours не добавлены.",
            "Пол, одежда и декоративные полосы — оригинальное решение; историческая точность конкретной одежды или совпадение со сканом жетона не заявляются.",
            "Тетива тонкая: масштабирование будущей модели требует отдельного контроля; референс не доказывает её пригодность после image-to-3D."
        ],
    },
}

for key, spec in SPECS.items():
    out = WAVE / key
    provenance = json.loads((out / "provenance.json").read_text(encoding="utf-8"))
    checks = [json.loads((out / ("checks/design-front-g" + str(i) + "/checks-report.json")).read_text(encoding="utf-8")) for i in [1, 2]]
    mask = checks[1]["measurements"]["front"]["mask"]
    review = {
        "asset_id": provenance["proposed_asset_id"], "title": spec["title"],
        "stage": "production-reference-only; formal pipeline not started", "view": "design-front", "selected": True,
        "status": "proposed-production-reference-only",
        "generations": [{"attempt": i, "selected": i == 2, "original_path": ORIGINAL_DIR + spec["files"][i - 1], "image": "concepts/" + key + "-design-front-g" + str(i) + ".png", "prompt_file": "prompts/design-front-g" + str(i) + ".txt"} for i in [1, 2]],
        "summary_ru": spec["summary"],
        "checklist": [
            {"item": "one complete human figure, one base, no text or extra limbs", "passed": True},
            {"item": spec["anchors"], "passed": True},
            {"item": "frontal body with visible arm/background gaps", "passed": True},
            {"item": "g2 base visually edge-on with no large top ellipse", "passed": True, "note": "Visual observation only; camera parameters cannot be recovered from this raster."},
            {"item": "exact CORE top/bottom framing", "passed": False, "note": "Selected top " + str(mask["top_pct"]) + "% (required >=4), bottom " + str(mask["bottom_pct"]) + "% (target93)."},
        ],
        "limitations": [
            "Оба кандидата: 12 PASS / 1 WARN / 0 FAIL; WARN view.frame_top сохранён. Выбранный g2: верх " + str(mask["top_pct"]) + "%, низ " + str(mask["bottom_pct"]) + "% вместо целевых >=4% / 93%.",
            "g1 показывает верх подставки; g2 убирает явный верхний эллипс, но строгая ортография камеры математически не подтверждена. Фон визуально почти ровный, полное равенство каждого пикселя не заявлено.",
            "Два front-кандидата не являются набором 1c. Нужны отдельные intake, независимая design acceptance и следующие гейты; 3D, риг, Tripo, анимация и UE не выполнялись.",
        ] + spec["extras"],
    }
    (out / "review.json").write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
