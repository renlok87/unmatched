import json
import sys

T = "art/material-library/v1/tiles"


def tile(c, px, tpm, wsize, feature, nstr=1.0):
    return {"DetailN": f"{T}/{c}/{c}_DetailN.png", "DetailRMH": f"{T}/{c}/{c}_DetailRMH.png", "tileSizePx": px,
            "tilesPerMeter": tpm, "tileWorldSizeM": wsize, "feature": feature, "normalStrength": nstr}


IRON = [0.560, 0.570, 0.580]
refs = {
    "UE-PBM": "Epic Games, документация Unreal Engine, «Physically Based Materials»: Base Color металлов (линейный sRGB): Iron (0.560, 0.570, 0.580), Silver (0.972, 0.960, 0.915), Aluminum (0.913, 0.922, 0.924), Gold (1.000, 0.766, 0.336), Copper (0.955, 0.637, 0.538), Chromium (0.550, 0.556, 0.554); Specular 0.5 = 4 % отражения, F0 = 0.08 × Specular.",
    "RTR4-T9.1": "Akenine-Möller, Haines, Hoffman et al., Real-Time Rendering, 4th ed. (2018), табл. 9.1 — F0 диэлектриков: вода 0.02, кожа (skin) 0.028, волосы 0.046, ткань 0.04–0.056, камень 0.035–0.056, пластики/стекло 0.04–0.05.",
    "RTR4-T9.2": "Там же, табл. 9.2 — F0 металлов (линейный): железо (0.562, 0.565, 0.578), серебро (0.972, 0.960, 0.915), золото (1.000, 0.782, 0.344), медь (0.955, 0.638, 0.538), латунь (0.910, 0.778, 0.423), хром (0.549, 0.556, 0.554). Первоисточник таблиц — N. Hoffman, «Physics and Math of Shading», SIGGRAPH 2015 PBS course.",
    "IOR-F0": "F0 = ((n − 1)/(n + 1))² при нормальном падении: кератин n ≈ 1.55 → 0.046 (совпадает с «волосы» RTR4-T9.1); целлюлоза n ≈ 1.53 → 0.044; коллаген/кожа снаряжения n ≈ 1.5 → 0.040; фиброин шёлка n ≈ 1.54 → 0.045.",
    "QDF-magnetite": "Criddle & Stanley (eds.), Quantitative Data File for Ore Minerals, 3rd ed. (1993): отражательная способность магнетита Fe3O4 в воздухе ≈ 20–21 % (546 нм). Воронение — плёнка магнетита на стали. ПРОВЕРИТЬ по первоисточнику перед приёмкой H2.2.",
    "ALBEDO": "Правило проекта (задача библиотеки v1): BC диэлектриков в линейном 0.02–0.9 (по яркости Y, каждый канал ≤ 0.9); согласуется со справочными альбедо «уголь ≈ 0.04, свежий снег ≈ 0.8–0.9» (напр. Lagarde & de Rousiers, «Moving Frostbite to PBR», SIGGRAPH 2014 course notes).",
    "UE-Cloth": "Epic Games, документация UE, «Shading Models» → Cloth: входы Fuzz Color и Cloth (0..1, доля тканевого лепестка); «From Material Expression» — модель затенения попиксельно.",
    "EK2017": "A. Estevez, C. Kulla, «Production Friendly Microfacet Sheen BRDF», SIGGRAPH 2017 (Sony Imageworks): семантика sheen color / sheen roughness (Substrate Fuzz, Blender Principled Sheen).",
    "UM-H21": "Наблюдение проекта: tools/tripo-pipeline/blender/h2_bake/materials.py (H2.1) — в M_UM_Figure нет sheen, полностью шероховатый диэлектрик размазывает 4 % зеркального отражения по тёмной ткани серой вуалью.",
    "CC0-measured": "Измерено скриптом tools/art/material_library/build_library.py на CC0-наборе класса (docs/art-pipeline/material-library/sources.json → measured, art/material-library/v1/textures-report.json → build): перцентили p5/p50/p95 и амплитуда вариации шероховатости.",
    "ART-DIR": "Решение проекта (арт-направление), обоснование в поле note; калибруется в UE look-dev следующей волны. Не справочное значение.",
}


def metal(**k):
    return {"family": "metal", "metallic": 1, "shadingModel": "DefaultLit", "specular": None, **k}


def diel(**k):
    return {"family": "dielectric", "metallic": 0, **k}


def cloth_spec(note=None):
    d = {"value": 0.40, "f0": 0.032, "sourceKind": "art", "source": ["RTR4-T9.1", "UM-H21", "ART-DIR"]}
    if note:
        d["note"] = note
    return d


classes = [
    {"index": 0, "id": "legacy_bake", "nameRu": "запечённое как есть (резерв)", "family": "passthrough",
     "note": "MatID 0: пиксель берёт запечённые BC/ORM героя без пресета (волосы, бороды, глаза, всё, что ещё не размечено). Позволяет мигрировать героя частями."},
    metal(index=1, id="steel_blued", nameRu="воронёная / тёмная сталь",
          baseColor={"mode": "preset-f0", "typicalLinear": [0.18, 0.19, 0.22], "luminanceRange": [0.10, 0.26],
                     "bakeLuminanceModulation": 0.15, "oxideFilm": True, "sourceKind": "reference+measured",
                     "source": ["QDF-magnetite", "CC0-measured"],
                     "note": "Воронение — плёнка магнетита: F0 ≈ 0.20 (QDF), синий сдвиг — тонкоплёночная интерференция (арт). Нижняя граница — измерено Metal038 p5 (Y ≈ 0.107), верхняя — Metal032 p50 (Y ≈ 0.24). Моделируется как металл с низким F0, НЕ как светлое железо (дефект Arthur H2.1)."},
          roughness={"typical": 0.37, "range": [0.30, 0.45], "variation": 0.048, "sourceKind": "measured", "source": ["CC0-measured"],
                     "note": "Metal038: median 0.367, p5–p95 0.341–0.388, амплитуда 0.048; диапазон расширен на ±0.05 под переопределения героев (ART-DIR)."},
          detail=tile("steel_blued", 1024, 5.0, 0.2, "пятна оксида, редкие риски и раковины"),
          edgeWear={"enabled": True, "strength": 0.35, "wornBaseColorLinear": IRON, "wornRoughness": 0.30,
                    "source": ["UE-PBM", "ART-DIR"], "note": "на рёбрах плёнка стёрта до железа (F0 железа)"},
          ageing={"cavityDarken": 0.3}, teamDyeAllowed=False),
    metal(index=2, id="steel_polished", nameRu="полированная сталь (клинки)",
          baseColor={"mode": "preset-f0", "typicalLinear": IRON, "referenceF0": "iron", "bakeLuminanceModulation": 0.05,
                     "sourceKind": "reference", "source": ["UE-PBM", "RTR4-T9.2"]},
          roughness={"typical": 0.15, "range": [0.12, 0.25], "variation": 0.128, "sourceKind": "measured+art",
                     "source": ["CC0-measured", "ART-DIR"],
                     "note": "Metal012: median 0.082, p95 0.153, амплитуда 0.128. Нижняя граница 0.12 — против зеркального алиасинга узкого клинка (фигура 0.55 м, несколько пикселей ширины в кадре K1)."},
          detail=tile("steel_polished", 1024, 4.0, 0.25, "мягкие разводы полировки, рельефа почти нет", 0.5),
          edgeWear={"enabled": False}, ageing={"cavityDarken": 0.0}, teamDyeAllowed=False),
    metal(index=3, id="metal_forged", nameRu="шлифованный / кованый металл с рисками",
          baseColor={"mode": "preset-f0", "typicalLinear": IRON, "referenceF0": "iron", "bakeLuminanceModulation": 0.15,
                     "sourceKind": "reference", "source": ["UE-PBM", "RTR4-T9.2"]},
          roughness={"typical": 0.47, "range": [0.39, 0.56], "variation": 0.128, "sourceKind": "measured", "source": ["CC0-measured"],
                     "note": "Metal009: median 0.468, p5–p95 0.388–0.557, амплитуда 0.128."},
          detail=tile("metal_forged", 1024, 5.0, 0.2, "направленные риски шлифовки (вдоль U тайла)"),
          edgeWear={"enabled": True, "strength": 0.2, "wornBaseColorLinear": IRON, "wornRoughness": 0.30, "source": ["ART-DIR"]},
          ageing={"cavityDarken": 0.25}, teamDyeAllowed=False),
    metal(index=4, id="gold_antique", nameRu="античное золото",
          baseColor={"mode": "preset-f0", "typicalLinear": [1.000, 0.766, 0.336], "referenceF0": "gold", "bakeLuminanceModulation": 0.12,
                     "sourceKind": "reference", "source": ["UE-PBM", "RTR4-T9.2"],
                     "note": "UE-PBM (1.000, 0.766, 0.336); RTR4 (1.000, 0.782, 0.344) — расхождение 0.016 в G. Измерено: Metal048A p50 (0.991, 0.768, 0.332)."},
          roughness={"typical": 0.30, "range": [0.20, 0.42], "variation": 0.08, "sourceKind": "art", "source": ["ART-DIR", "CC0-measured"],
                     "note": "Metal042A (новое кованое золото) даёт 0.114–0.125; «античное» — затёртая позолота, шероховатее. Амплитуда источника ниже порога 0.04, поэтому вариация задана вручную."},
          detail=tile("gold_antique", 1024, 5.0, 0.2, "низкочастотный рельеф ручной ковки"),
          edgeWear={"enabled": True, "strength": 0.3, "wornBaseColorLinear": [1.000, 0.766, 0.336], "wornRoughness": 0.15,
                    "source": ["ART-DIR"], "note": "затёртые выступы глаже"},
          ageing={"cavityDarken": 0.5}, teamDyeAllowed=False),
    metal(index=5, id="brass", nameRu="латунь",
          baseColor={"mode": "preset-f0", "typicalLinear": [0.910, 0.778, 0.423], "referenceF0": "brass", "bakeLuminanceModulation": 0.12,
                     "sourceKind": "reference", "source": ["RTR4-T9.2"]},
          roughness={"typical": 0.25, "range": [0.15, 0.35], "variation": 0.06, "sourceKind": "art", "source": ["ART-DIR", "CC0-measured"],
                     "note": "Metal048A — полированная латунь 0.082–0.098; для снаряжения берём состаренную (захватанную) латунь."},
          detail=tile("brass", 1024, 5.0, 0.2, "почти чистая поверхность: слабая вариация шероховатости, высоты нет", 0.5),
          edgeWear={"enabled": True, "strength": 0.3, "wornBaseColorLinear": [0.910, 0.778, 0.423], "wornRoughness": 0.15, "source": ["ART-DIR"]},
          ageing={"cavityDarken": 0.35}, teamDyeAllowed=False),
    metal(index=6, id="bronze", nameRu="бронза",
          baseColor={"mode": "preset-f0", "typicalLinear": [0.93, 0.71, 0.48], "referenceF0": "bronze-derived", "bakeLuminanceModulation": 0.15,
                     "sourceKind": "derived", "source": ["UE-PBM", "RTR4-T9.2"],
                     "note": "Табличного F0 оловянной бронзы в UE-PBM/RTR4 нет. Производное: среднее меди (0.955, 0.637, 0.538) и латуни (0.910, 0.778, 0.423). Проверить по спектральным данным перед художественной приёмкой."},
          roughness={"typical": 0.23, "range": [0.16, 0.40], "variation": 0.184, "sourceKind": "measured", "source": ["CC0-measured"],
                     "note": "Metal008: median 0.230, p5–p95 0.161–0.329, амплитуда 0.184; верх расширен до 0.40 под патину (ART-DIR)."},
          detail=tile("bronze", 1024, 5.0, 0.2, "пятна патины, точечные раковины, риски"),
          edgeWear={"enabled": True, "strength": 0.4, "wornBaseColorLinear": [0.93, 0.71, 0.48], "wornRoughness": 0.20, "source": ["ART-DIR"]},
          ageing={"cavityDarken": 0.55}, teamDyeAllowed=False),
    diel(index=7, id="leather_smooth", nameRu="кожа гладкая", shadingModel="DefaultLit",
         baseColor={"mode": "bake-clamped", "typicalLinear": [0.020, 0.020, 0.020], "luminanceRange": [0.02, 0.45], "maxChannel": 0.9,
                    "sourceKind": "measured+rule", "source": ["CC0-measured", "ALBEDO"],
                    "note": "Leather026 p50 0.010 (чёрная кожа) ниже пола 0.02 — поднята до пола. В рантайме цвет — из запечённого альбедо героя, зажатый в диапазон."},
         roughness={"typical": 0.37, "range": [0.33, 0.41], "variation": 0.053, "sourceKind": "measured", "source": ["CC0-measured"],
                    "note": "Leather026: median 0.371, p5–p95 0.333–0.408."},
         specular={"value": 0.5, "f0": 0.040, "sourceKind": "derived", "source": ["IOR-F0", "UE-PBM"]},
         detail=tile("leather_smooth", 1024, 8.0, 0.125, "мелкая зернистость, потёртости"),
         edgeWear={"enabled": True, "strength": 0.2, "wornBaseColorScale": 1.3, "wornRoughnessDelta": 0.10, "source": ["ART-DIR"]},
         teamDyeAllowed=True),
    diel(index=8, id="leather_worn", nameRu="кожа потёртая", shadingModel="DefaultLit",
         baseColor={"mode": "bake-clamped", "typicalLinear": [0.041, 0.020, 0.014], "luminanceRange": [0.02, 0.45], "maxChannel": 0.9,
                    "sourceKind": "measured", "source": ["CC0-measured", "ALBEDO"], "note": "Leather030 p50 (Y ≈ 0.024)."},
         roughness={"typical": 0.47, "range": [0.22, 0.77], "variation": 0.297, "sourceKind": "measured", "source": ["CC0-measured"],
                    "note": "Leather030: median 0.473, p5–p95 0.220–0.773."},
         specular={"value": 0.5, "f0": 0.040, "sourceKind": "derived", "source": ["IOR-F0", "UE-PBM"]},
         detail=tile("leather_worn", 1024, 8.0, 0.125, "крупная мерея, затёртые гладкие места"),
         edgeWear={"enabled": True, "strength": 0.5, "wornBaseColorScale": 1.4, "wornRoughnessDelta": -0.10, "source": ["ART-DIR"],
                   "note": "затёртая кожа светлее и глаже (залощена)"},
         teamDyeAllowed=True),
    diel(index=9, id="wool_coarse", nameRu="шерсть, грубое плетение", shadingModel="Cloth",
         baseColor={"mode": "bake-clamped", "typicalLinear": [0.095, 0.095, 0.098], "luminanceRange": [0.02, 0.8], "maxChannel": 0.9,
                    "sourceKind": "measured", "source": ["CC0-measured", "ALBEDO"], "note": "Fabric030 p50."},
         roughness={"typical": 0.72, "range": [0.53, 0.92], "variation": 0.214, "sourceKind": "measured", "source": ["CC0-measured"],
                    "note": "Fabric030: median 0.721, p5–p95 0.525–0.918."},
         specular=cloth_spec("Волокно само по себе F0 0.04–0.056 (RTR4), но у тканого полотна часть отражения уходит в fuzz-лепесток Cloth и в самозатенение нитей; 0.4 убирает «серую вуаль» UM-H21 при Cloth < 1."),
         cloth={"clothAmount": 1.0, "sheenColor": {"mode": "tinted", "intensity": 0.35, "tint": 0.5, "typicalLinear": [0.066, 0.066, 0.068]},
                "sheenRoughness": 0.6, "sourceKind": "art", "source": ["UE-Cloth", "EK2017", "ART-DIR"],
                "note": "FuzzColor = intensity × lerp(1, BC / Y(BC), tint) × sqrt(Y(BC)) (README §6). sheenRoughness — для Substrate Fuzz / Blender Sheen; legacy Cloth UE берёт общий Roughness."},
         detail=tile("wool_coarse", 1024, 3.7, 0.27, "~180 нитей на тайл → шаг 1.5 мм на фигуре"),
         edgeWear={"enabled": False}, teamDyeAllowed=True),
    diel(index=10, id="linen", nameRu="лён / хлопок, мелкое плетение", shadingModel="Cloth",
         baseColor={"mode": "bake-clamped", "typicalLinear": [0.227, 0.212, 0.198], "luminanceRange": [0.02, 0.85], "maxChannel": 0.9,
                    "sourceKind": "measured", "source": ["CC0-measured", "ALBEDO"], "note": "Fabric061 p50."},
         roughness={"typical": 0.84, "range": [0.77, 0.89], "variation": 0.086, "sourceKind": "measured", "source": ["CC0-measured"],
                    "note": "Fabric061: median 0.843, p5–p95 0.773–0.890."},
         specular=cloth_spec(),
         cloth={"clothAmount": 0.7, "sheenColor": {"mode": "tinted", "intensity": 0.2, "tint": 0.3, "typicalLinear": [0.098, 0.096, 0.094]},
                "sheenRoughness": 0.5, "sourceKind": "art", "source": ["UE-Cloth", "EK2017", "ART-DIR"]},
         detail=tile("linen", 512, 9.8, 0.102, "128 нитей на тайл 512 (4 px/нить) → шаг 0.8 мм"),
         edgeWear={"enabled": False}, teamDyeAllowed=True),
    diel(index=11, id="silk", nameRu="шёлк (процедурный атлас)", shadingModel="Cloth",
         baseColor={"mode": "bake-clamped", "typicalLinear": [0.25, 0.25, 0.25], "luminanceRange": [0.02, 0.85], "maxChannel": 0.9,
                    "sourceKind": "rule", "source": ["ALBEDO"], "note": "нейтральный превью-цвет; в рантайме — альбедо героя"},
         roughness={"typical": 0.35, "range": [0.25, 0.50], "variation": 0.08, "sourceKind": "art", "source": ["ART-DIR"],
                    "note": "CC0-измерения нет; шёлк заметно глянцевый (гладкие трёхгранные волокна фиброина). Перекрытия основы глаже, точки переплетения шероховатее (R тайла)."},
         specular={"value": 0.5, "f0": 0.040, "sourceKind": "derived", "source": ["IOR-F0"],
                   "note": "фиброин n ≈ 1.54 → 0.045; блик шёлка реален, не понижаем, как у шерсти"},
         cloth={"clothAmount": 0.6, "sheenColor": {"mode": "tinted", "intensity": 0.5, "tint": 0.8, "typicalLinear": [0.125, 0.125, 0.125]},
                "sheenRoughness": 0.3, "sourceKind": "art", "source": ["UE-Cloth", "EK2017", "ART-DIR"],
                "note": "Анизотропного блика шёлка legacy Cloth не даёт; в v1 не делаем (Anisotropy — вход DefaultLit, не Cloth)."},
         detail=tile("silk", 512, 31.0, 0.032, "атлас 5/2: 80 нитей основы на тайл → шаг 0.4 мм", 0.6),
         edgeWear={"enabled": False}, teamDyeAllowed=True),
    diel(index=12, id="feathers", nameRu="перья (процедурные)", shadingModel="DefaultLit",
         baseColor={"mode": "bake-clamped", "typicalLinear": [0.06, 0.05, 0.045], "luminanceRange": [0.02, 0.7], "maxChannel": 0.9,
                    "sourceKind": "art", "source": ["ALBEDO", "ART-DIR"], "note": "превью-цвет тёмного пера Harpy; в рантайме — альбедо героя"},
         roughness={"typical": 0.55, "range": [0.40, 0.75], "variation": 0.10, "sourceKind": "art", "source": ["ART-DIR"],
                    "note": "стержень глаже опахала (R тайла)"},
         specular={"value": 0.575, "f0": 0.046, "sourceKind": "reference", "source": ["RTR4-T9.1", "IOR-F0"], "note": "кератин = F0 волос 0.046"},
         detail=tile("feathers", 1024, 21.0, 0.048, "4 × 8 контурных перьев на тайл → перо ~12 мм шириной"),
         edgeWear={"enabled": False}, teamDyeAllowed=True),
    diel(index=13, id="skin", nameRu="кожа персонажа (процедурная)", shadingModel="DefaultLit",
         baseColor={"mode": "bake-clamped", "typicalLinear": [0.45, 0.30, 0.24], "luminanceRange": [0.03, 0.60], "maxChannel": 0.9,
                    "sourceKind": "art", "source": ["ALBEDO", "ART-DIR"],
                    "note": "превью-цвет; в рантайме — альбедо героя (у Medusa зеленоватая кожа — диапазон тот же, оттенок из запечённого BC)"},
         roughness={"typical": 0.50, "range": [0.40, 0.65], "variation": 0.06, "sourceKind": "art", "source": ["ART-DIR"],
                    "note": "поры шероховатее, плато чуть «жирнее»"},
         specular={"value": 0.35, "f0": 0.028, "sourceKind": "reference", "source": ["RTR4-T9.1", "IOR-F0"]},
         subsurfaceApprox={"model": "DefaultLit, без Subsurface/SubsurfaceProfile",
                           "cavityTintLinear": [0.60, 0.22, 0.16], "strength": 0.35,
                           "formula": "AO_color = lerp(cavityTint, 1, AO_hero × lerp(1, G, 0.5)); BC_final = BC × lerp(1, AO_color, strength)",
                           "recommendations": ["Полости и складки тонировать красным, а не серым (дешёвая имитация рассеяния в тени).",
                                               "Насыщенность альбедо кожи не поднимать > 1.1 и не опускать BC ниже Y 0.03.",
                                               "Не использовать SubsurfaceProfile: отдельный проход и CustomData GBuffer; на фигуре 0.55 м в кадре K1 эффект меньше пикселя.",
                                               "Губы/нос/уши: roughness −0.05 относительно лба и щёк через переопределение героя, не новым классом."],
                           "sourceKind": "art", "source": ["ART-DIR"]},
         detail=tile("skin", 512, 25.0, 0.04, "~1100 пор на тайл → шаг ~1.2 мм", 0.5),
         edgeWear={"enabled": False}, teamDyeAllowed=False),
    diel(index=14, id="stone_base", nameRu="камень подставки (тёмный, шлифованный)", shadingModel="DefaultLit",
         baseColor={"mode": "bake-clamped", "typicalLinear": [0.040, 0.040, 0.042], "luminanceRange": [0.02, 0.12], "maxChannel": 0.9,
                    "sourceKind": "art", "source": ["ALBEDO", "ART-DIR"], "note": "тёмный камень; нижняя граница — пол диэлектриков"},
         roughness={"typical": 0.45, "range": [0.35, 0.60], "variation": 0.128, "sourceKind": "art+measured", "source": ["ART-DIR", "CC0-measured"],
                    "note": "Marble012 — полированный мрамор 0.031–0.129; на подставке полировка даёт зеркальные блики, спорящие с фигурой и полосой TeamColor → шлифовка (honed). Вариация по прожилкам — измеренная амплитуда 0.128."},
         specular={"value": 0.5, "f0": 0.040, "sourceKind": "reference", "source": ["RTR4-T9.1"], "note": "камень 0.035–0.056"},
         detail=tile("stone_base", 1024, 4.0, 0.25, "прожилки: вариация шероховатости и слабый рельеф"),
         edgeWear={"enabled": True, "strength": 0.15, "wornBaseColorScale": 1.5, "wornRoughnessDelta": 0.10, "source": ["ART-DIR"], "note": "сколы рёбер светлее"},
         teamDyeAllowed=False),
    diel(index=15, id="wood", nameRu="дерево (посох, лук, древки)", shadingModel="DefaultLit",
         baseColor={"mode": "bake-clamped", "typicalLinear": [0.053, 0.034, 0.028], "luminanceRange": [0.02, 0.45], "maxChannel": 0.9,
                    "sourceKind": "measured", "source": ["CC0-measured", "ALBEDO"], "note": "Wood051 p50."},
         roughness={"typical": 0.55, "range": [0.43, 0.65], "variation": 0.141, "sourceKind": "measured", "source": ["CC0-measured"],
                    "note": "Wood051: median 0.543, p5–p95 0.431–0.655."},
         specular={"value": 0.55, "f0": 0.044, "sourceKind": "derived", "source": ["IOR-F0"]},
         detail=tile("wood", 1024, 3.3, 0.3, "волокна вдоль U тайла: UV1 древка выкладывать вдоль U"),
         edgeWear={"enabled": True, "strength": 0.25, "wornBaseColorScale": 1.3, "wornRoughnessDelta": -0.10, "source": ["ART-DIR"],
                   "note": "захватанные места светлее и глаже"},
         teamDyeAllowed=False),
]

# Extension classes (2026-09-29, look-dev v2 Harpy): the 4-bit MatID has no free global index (README §10), so a class
# added after v1 has no global column. A hero that uses it puts it into the LUT column of a library class it does not
# use (hero slot, README §3a); its detail slice is the slice of an existing class (tileFrom) until the arrays get
# their own slice. Physics numbers are validated like the classes above (validate_library.py preset_physics).
extension_classes = [
    diel(index=16, id="horn_claw", nameRu="рог / коготь (кератин)", shadingModel="DefaultLit",
         baseColor={"mode": "bake-clamped", "typicalLinear": [0.030, 0.026, 0.024], "luminanceRange": [0.02, 0.55], "maxChannel": 0.9,
                    "sourceKind": "art", "source": ["ALBEDO", "ART-DIR"],
                    "note": "превью-цвет — тёмный коготь хищной птицы (концепт Harpy: чёрный рог); в рантайме — альбедо героя. "
                            "Верх диапазона 0.55 — светлый рог/кость (роговой чехол козы, слоновая кость), низ — пол диэлектриков"},
         roughness={"typical": 0.33, "range": [0.22, 0.50], "variation": 0.06, "sourceKind": "art", "source": ["ART-DIR", "CC0-measured"],
                    "note": "Кератиновый чехол когтя/рога гладкий, полируется износом (у концепта на когтях узкие яркие блики): глаже "
                            "гладкой кожи (Leather026, measured median 0.371) и пера (0.55). Пол 0.22 — против спекулярного алиасинга "
                            "на мелких формах. Справочного значения шероховатости кератина нет — арт-решение, калибруется в look-dev."},
         specular={"value": 0.575, "f0": 0.046, "sourceKind": "reference", "source": ["RTR4-T9.1", "IOR-F0"],
                   "note": "кератин n ≈ 1.55 → F0 0.046 = «волосы» RTR4 (как перья)"},
         detail=dict(tile("stone_base", 1024, 12.0, 0.0833, "слабые продольные прожилки и пятна (тайл камня подставки на мелком "
                                                              "масштабе; свой процедурный тайл «годичные полосы рога» — v1.1)", 0.3),
                     tileFrom="stone_base"),
         edgeWear={"enabled": True, "strength": 0.25, "wornBaseColorScale": 1.4, "wornRoughnessDelta": -0.08, "source": ["ART-DIR"],
                   "note": "стёртые кончики когтя светлее (открытый слой кератина) и глаже"},
         teamDyeAllowed=False,
         extension={"libraryIndex": 16, "globalMatId": False,
                    "heroSlot": "столбец LUT класса, которого у героя нет (у Harpy — brass, индекс 5); MatID героя = слот × 16 + 8",
                    "arraySlice": 14, "arraySliceNote": "срез массива деталей класса tileFrom (stone_base = 14)",
                    "why": "4-битный MatID занят классами 0–15 (README §10); отдельный класс нужен, чтобы коготь не делил "
                           "шероховатость/износ с пером или кожей. Физика кератина — как у перьев (F0 0.046), отличие — гладкость и износ"}),
    # 2026-10-04 (ART-016, Harpy look-dev r3.3): the flight feathers get their own LUT column, so a hero can tune their
    # specular apart from the coverts (Harpy r3.1: one shared feathers specular darkened the rufous body feathers)
    diel(index=17, id="feathers_flight", nameRu="маховые перья (кератин)", shadingModel="DefaultLit",
         baseColor={"mode": "bake-clamped", "typicalLinear": [0.06, 0.05, 0.045], "luminanceRange": [0.02, 0.7], "maxChannel": 0.9,
                    "sourceKind": "art", "source": ["ALBEDO", "ART-DIR"],
                    "note": "как feathers: превью-цвет тёмного пера Harpy; в рантайме — альбедо героя"},
         roughness={"typical": 0.55, "range": [0.40, 0.75], "variation": 0.10, "sourceKind": "art", "source": ["ART-DIR"],
                    "note": "как feathers: стержень глаже опахала (R тайла)"},
         specular={"value": 0.575, "f0": 0.046, "sourceKind": "reference", "source": ["RTR4-T9.1", "IOR-F0"],
                   "note": "кератин = F0 волос 0.046, как feathers. Блик маховых герой меняет в своей LUT отдельно от кроющих "
                           "(Harpy: specular 0.35 — арт-решение по кадрам UE look-dev r3, не справочное значение)"},
         detail=dict(tile("feathers", 1024, 21.0, 0.048, "тайл feathers: 4 × 8 контурных перьев на тайл → перо ~12 мм шириной"),
                     tileFrom="feathers"),
         edgeWear={"enabled": False}, teamDyeAllowed=True,
         extension={"libraryIndex": 17, "globalMatId": False,
                    "heroSlot": "столбец LUT класса, которого у героя нет (у Harpy — metal_forged, индекс 3); MatID героя = слот × 16 + 8",
                    "arraySlice": 12, "arraySliceNote": "срез массива деталей класса tileFrom (feathers = 12)",
                    "why": "Маховые и кроющие перья — один материал (кератин), но крупные плоские опахала маховых ловят блик "
                           "купола иначе, чем мелкие кроющие: при общем столбце LUT правка блика маховых меняет и рыжие перья "
                           "тела (Harpy look-dev r3, ART-016). Физика — как у feathers; отличие только в том, что у класса свой столбец"}),
]


def fuzz(bc, intensity, tint):
    y = 0.2126 * bc[0] + 0.7152 * bc[1] + 0.0722 * bc[2]
    return [round(intensity * ((1 - tint) + tint * c / y) * y ** 0.5, 4) for c in bc]


for c in classes:
    if "cloth" in c:
        sc = c["cloth"]["sheenColor"]
        sc["typicalLinear"] = fuzz(c["baseColor"]["typicalLinear"], sc["intensity"], sc["tint"])

data = {
    "schema": "um-material-presets/1", "version": "v1", "date": "2026-09-29",
    "status": "предложено (проект для UE look-dev следующей волны; в UE ничего не создано)",
    "conventions": {
        "colorSpace": "baseColor, sheenColor — линейный sRGB (Rec.709 primaries); Y = 0.2126 R + 0.7152 G + 0.0722 B",
        "specular": "UE Specular: F0 = 0.08 × Specular (0.5 = 0.04); для metallic = 1 не используется (null)",
        "metallic": "только 0 или 1 на класс; промежуточные значения — только на переходах (граница классов при фильтрации, см. README §3); износ внутри металла metallic не меняет",
        "roughness": "перцептивная UE roughness (α = r²); range — жёсткий зажим после вариации; variation — Δr при R тайла 0/1 (R = 0.5 — без изменения)",
        "detailRMH": "R вариация шероховатости вокруг 0.5, G полость/AO (1 = открыто), B высота 0..1 и источник маски износа",
        "detailNormal": "DirectX (UE): G = −dh/drow; смешивать с нормалью героя BlendAngleCorrectedNormals",
        "tilesPerMeter": "в метрах объекта при высоте фигуры ~0.55 м; требует UV1 «в метрах» (README §5)",
        "sourceKind": "reference — справочник; measured — измерено на CC0-наборе; derived — вычислено из справочного; rule — правило проекта; art — арт-решение (калибруется в look-dev)",
    },
    "figureHeightM": 0.55,
    "matId": {"encoding": "R8 unorm, value = index × 16 + 8, decode floor(v × 255 / 16)", "maxClasses": 16,
              "reserved": {"0": "legacy_bake"},
              "extension": "extensionClasses (libraryIndex ≥ 16) не имеют глобального индекса MatID: герой кладёт такой класс в "
                           "столбец LUT неиспользуемого им класса (heroSlot), срез деталей — extension.arraySlice (README §3a)"},
    "referenceF0": {
        "iron": {"linear": [0.560, 0.570, 0.580], "source": "UE-PBM"},
        "chromium": {"linear": [0.550, 0.556, 0.554], "source": "UE-PBM"},
        "silver": {"linear": [0.972, 0.960, 0.915], "source": "UE-PBM"},
        "aluminum": {"linear": [0.913, 0.922, 0.924], "source": "UE-PBM"},
        "gold": {"linear": [1.000, 0.766, 0.336], "source": "UE-PBM", "alt": {"linear": [1.000, 0.782, 0.344], "source": "RTR4-T9.2"}},
        "copper": {"linear": [0.955, 0.637, 0.538], "source": "UE-PBM"},
        "brass": {"linear": [0.910, 0.778, 0.423], "source": "RTR4-T9.2"},
        "bronze-derived": {"linear": [0.93, 0.71, 0.48], "source": "derived: mean(copper UE-PBM, brass RTR4-T9.2)"},
        "magnetite-film": {"luminance": 0.20, "source": "QDF-magnetite"},
    },
    "references": refs,
    "classes": classes,
    "extensionClasses": extension_classes,
}
sys.path.insert(0, "tools/art/material_library")
from build_library import dump_json  # noqa: E402
open(sys.argv[1], "w", encoding="utf-8", newline="\n").write(dump_json(data))
