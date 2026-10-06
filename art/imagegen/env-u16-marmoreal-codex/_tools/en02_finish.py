"""Finish EN-02 blocked preparation; no generation, git or Unreal calls."""
import hashlib
import json
from pathlib import Path

from PIL import Image
import en02 as task


README = """# EN-02 — расширение плиты Marmoreal

Статус: **предложено; генерация заблокирована**. Задача **не выполнена полностью**: `marmoreal-clean-ext.png` и `marmoreal-lit-ext.png` отсутствуют. Приёмка не пройдена. Новых генераций **0 из 6**; две отклонённые служебные проверки сервиса не являются генерациями.

## Блокировка

Подключённый сервис SYNTX отклонил оба предварительных вызова (`whoami`, `list_models`): `MCP tool call requires approval, but approval policy is never`. Авторизация и доступность модели не проверены; генерация не запускалась, списаний по генерациям не было.

Встроенный imagegen не вызван: он автоматически сохраняет PNG вне двух разрешённых корней. Это задокументировано в [imagegen/SKILL.md](C:/Users/ren/.codex/skills/.system/imagegen/SKILL.md): «Codex saves generated images under `$CODEX_HOME/*` by default». В EN-01 такие записи уже обнаруживались. Новое задание прямо запрещает любые записи вне пакета и его derived-папки; сохранять там копию и затем перемещать её тоже нельзя. Обход ограничений среды или получение платной генерации другим путём не выполнялись.

**Рекомендация для будущего результата — clean-ext**: он оставит фонари под управлением накладок игры. Lit-ext предусмотрен для сравнения и восстановления исходной живописной засветки. Выбрать между реальными расширенными вариантами сейчас невозможно: их ещё нет.

## Что подготовлено и проверено

Вход EN-01 принят Claude по делегированию (ВР-60, 2026-10-06); состояние перед EN-02 сохранено в [history/en02-before-README.md](history/en02-before-README.md) и [history/en02-before-verification.json](history/en02-before-verification.json). Новая блокировка EN-02 не отменяет приёмку EN-01.

- [Холст для outpaint](../../../scraped-data/derived/env-u16-marmoreal-codex/concepts/EN-02-outpaint-input.png): RGBA 2340×1317, оригинал в `[334,188,1672,941]`, края прозрачны. Центральные RGB-байты совпадают с EN-01: SHA-256 `2306d4661309c4d0f7855457d21fff09c32bea9bda3cfe75e7936fd05a0d48bd` у обоих кропов.
- [Маска outpaint](../../../scraped-data/derived/env-u16-marmoreal-codex/concepts/EN-02-outpaint-mask.png): 8-bit L, 255 только снаружи оригинала; 0 внутри. Прозрачность входа проверена отдельно.
- [Сдвинутая маска фонарей](../../../scraped-data/derived/env-u16-marmoreal-codex/concepts/EN-02-lantern-mask-offset.png): 2340×1317, смещение +334,+188.
- [Lit-превью оригинала](../../../scraped-data/derived/env-u16-marmoreal-codex/concepts/EN-02-lit-original-preview.png): 1672×941, скриптовое восстановление C0 с растушёвкой внутрь support на 6 px и сохранением исходной альфы маски. Отличий вне маски **0 px**, поле целиком **#808080**. Это не `lit-ext` и не расширенная плита.
- [Точный промпт EN-02-OUTPAINT-01](prompts/EN-02-OUTPAINT-01.txt), [_tools/en02-spec.json](_tools/en02-spec.json), скрипт [_tools/en02.py](_tools/en02.py): paste-back, lit, листы, независимое чтение PNG и численная проверка шва. Оригинальный C0 используется только для lit, не является входом outpaint.
- В [source-hashes-before.json](source-hashes-before.json), секция `EN-02`, зафиксированы **1079** исходных файлов, включая весь текущий `hud-icons-v3/**`. После работы изменённых исходников **0**. Прежняя секция EN-01 сохранена без изменений.
- Снимок `_tools/draw_icons_v3_snapshot.py` теперь побайтно равен текущему генератору. Старый снимок отличался; он сохранён без изменений в [history/en02-before-draw_icons_v3_snapshot.py](history/en02-before-draw_icons_v3_snapshot.py). Оригинальный генератор не редактировался и не исполнялся. Код EN-02 находится в отдельных модулях.
- **123** прежних файлов пакета и derived, которые не являются обновляемыми сводными отчётами или снимком генератора, остались неизменны. Все старые записи `generation-records.json` сохранены; добавлена только секция EN-02 с блокировкой.

## Листы подготовки

Все изображения находятся только в `scraped-data/derived/env-u16-marmoreal-codex/`. Шахматная сетка обозначает **отсутствующий outpaint**, а не принятую текстуру; листы явно подписаны `PREPARATION ONLY`. Слева clean EN-01, справа скриптовый lit-превью. Просмотрены цветные и серые листы: восстановлены четыре фонаря и бра, поле остаётся серым; новые края не нарисованы.

| Размер | Цвет | Rec.709 gray |
|---|---|---|
| Мастер, две панели 2340×1317 | [цвет](../../../scraped-data/derived/env-u16-marmoreal-codex/comparison/ext-preparation-only-colour.png) | [серый](../../../scraped-data/derived/env-u16-marmoreal-codex/comparison/ext-preparation-only-gray.png) |
| Рабочий, панели 1521×856 | [цвет](../../../scraped-data/derived/env-u16-marmoreal-codex/comparison/ext-preparation-working-1521x856-colour.png) | [серый](../../../scraped-data/derived/env-u16-marmoreal-codex/comparison/ext-preparation-working-1521x856-gray.png) |
| Рабочий, панели 1170×659 | [цвет](../../../scraped-data/derived/env-u16-marmoreal-codex/comparison/ext-preparation-working-1170x659-colour.png) | [серый](../../../scraped-data/derived/env-u16-marmoreal-codex/comparison/ext-preparation-working-1170x659-gray.png) |

Серый: sRGB → linear RGB → Rec.709 Y (0.2126, 0.7152, 0.0722) → sRGB. Декоративные подписи есть только на листах, не в плите или входной текстуре.

## Решения и ограничения

Размеры и положение оригинала из карточки сохранены точно: 334+1672+334=2340; 188+941+188=1317. Цвета живописи не приводились к токенам: исключение для плит применено буквально. Вместо недоступной генерации не использованы растяжение, отражение, edge-clamp или дорисовка декораций скриптом.

При **номинальном** переводе 1672×941 в C0 1920×1080 холст соответствует `[-383.5407,-215.7705]..[2303.5407,1295.7705]`. До rect B не хватает примерно 0.4593 C0 px по горизонтальным и 0.2295 C0 px по вертикальным краям из-за округления отступов. Это расчёт по доступной paste-спецификации; новый размер холста самовольно не назначался.

K1 ×0.65 доступен только как условная рамка в плоскости изображения. Если понимать его как расширение охвата исходного кадра в 1/0.65, требуется 2572.31×1447.69, больше заданного холста. Это **не утверждение о реальной камере Unreal**. Её матрицы и проекцию не читали, проверку отсутствия edge-clamp в игре не заявляем. Скрипт будущих листов маркирует такую рамку `IMAGE-SPACE K1 proxy` и показывает недостающее покрытие.

Порог шва пока не измерен: расширения нет. В скрипте он задан как максимум абсолютного перепада **линейной Rec.709 Y** поперёк старой границы против 1.5× медианы таких перепадов в соседних полосах по 64 px с обеих сторон; сама граница исключена, нули сохранены. Предусмотрены общий результат и результаты четырёх сторон. Карту полной величины градиента, четыре края при 2× nearest, оба финальных варианта в мастере/рабочих размерах и цвете/gray скрипт создаст после получения настоящего outpaint.

Не выполнены: художественное продолжение краёв, визуальная проверка швов и перспективы, финальные `clean-ext`/`lit-ext`, листы финальных краёв и градиента, приёмка. Сборка с реальной генерацией не испытана. Две неудачи перспективы/швов не происходили; переход Claude к banana3/2K не запрашивается по этому условию. Блокировка относится к доступу к инструменту.

## Продолжение без повторной подготовки

`prepare` однократный: он намеренно отказывается перезаписывать baseline. После устранения блокировки нужно получить outpaint с указанным входом и точным промптом, сохранить **неизменённый** результат в `concepts/`, добавить запись в `generation-records.json` → `EN-02.generations` с `prompt_key`, `prompt_file`, `prompt_sha256`, `input`, `input_sha256`, `raw_file`, `raw_sha256`, `retouched: false` и фактическим провайдером. Лимит — 6 генераций; все неудачные тоже сохраняются. Скрипт ожидает зарегистрированный полноразмерный RGB/RGBA-результат 2340×1317. Для тайлов нужен отдельный явно зарегистрированный проход: ≤1536 px, overlap ≥64 px, возврат оригинала после каждого прохода. Этот путь пока не реализован и не выдаётся за выполненный.

```powershell
python -B art/imagegen/env-u16-marmoreal-codex/_tools/en02.py build --raw scraped-data/derived/env-u16-marmoreal-codex/concepts/EN-02-OUTPAINT-01-raw.png
python -B art/imagegen/env-u16-marmoreal-codex/_tools/en02.py verify
python -B art/imagegen/env-u16-marmoreal-codex/_tools/en02.py manifest
```

`verify` не объявляет художественную приёмку автоматически; после сборки требуется открыть настоящие листы и записать результат. Проверка подготовки и [verification.json](verification.json) воспроизводятся сейчас без генерации. [manifest-sha256.json](manifest-sha256.json) покрывает оба разрешённых корня, исключая себя.

Git не запускался; `unreal/` не открывался, не менялся и не собирался. Записи выполнялись только в двух разрешённых корнях. Фоновые сервисы, редакторы и постоянные процессы не запускались.
"""


def finish():
    if (task.IMG / "marmoreal-clean-ext.png").exists():
        raise RuntimeError("This finish script describes blocked preparation only.")
    master=Image.open(task.IMG / "comparison/ext-preparation-only-colour.png").convert("RGB")
    panels=[master.crop((0,40,2340,1357)),master.crop((2340,40,4680,1357))]
    for size in ((1521,856),(1170,659)):
        task.save_pair(f"ext-preparation-working-{size[0]}x{size[1]}",
                       [p.resize(size,Image.Resampling.LANCZOS) for p in panels],
                       ["PREPARATION ONLY: no outpaint", "PREPARATION ONLY: lit centre; no outpaint"])
    (task.PKG / "README.md").write_text(README,encoding="utf-8")
    task.verify()
    task.manifest()
    v=task.read_json(task.PKG / "verification.json")
    assert v["source_unchanged"]["pass"] and v["en01_files_frozen"]["pass"]
    assert v["generation_records_append_only"] and v["generator_snapshot_matches_current_hud"]
    assert v["previous_generator_snapshot_backed_up"]
    p=v["preparation_readback"]
    assert p["input_original_crop_byte_identical"] and p["lit_preview_changes_outside_mask"]==0
    assert p["lit_preview_field_808080"] and not v["deliverables_present"]
    for name in ("README.md","verification.json","source-hashes-before.json","generation-records.json","manifest-sha256.json"):
        expected=task.read_json(task.BASELINE)["package_before"][task.rel(task.PKG/name)]["sha256"]
        assert task.sha(task.PKG / "history" / ("en02-before-"+name))==expected
    m=task.read_json(task.PKG / "manifest-sha256.json")
    assert all(task.sha(task.ROOT/path)==info["sha256"] for path,info in m["files"].items())
    print(json.dumps({"preparation_checks_pass":True,"final_task_complete":False,"blocked":True}))


if __name__=="__main__":
    finish()
