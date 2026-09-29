# Контракт рига v2: пробные сборки профилей `/4` (2026-09-29)

Волна 4, задача W4-D. Статус: **измерено** (техническая проверка профилей). Художественно ничего не принимается, новые run героев этим не создаются.

## Что проверялось

Профили `/4` Arthur и Merlin отличаются от `/2` только именем кости оружия (`weapon` → `weapon.R` в `armature.bones`, `meshes.weapon.bone`, `sockets[Weapon].bone`) — по [контракту рига v2](../../rig/RIG-CONTRACT.md) §0 п.3. Вопрос: собирает ли CLI героя по `/4` без правки кода и проходит ли результат `validate_clip.py` против `UM_HUMANOID_17_v2`.

## Метод

1. Копия run `20260928-cli-um-fbx-v1` героя в `C:/tmp/w4d-fix/<hero>-rigv2-run` (вне репозитория); в `manifest.json` `config.build_profile` → профиль `/4`.
2. `python tools/tripo-pipeline/tripo_pipeline.py --repo-root . build --run-dir <копия> --force` (headless Blender 5.2.2).
3. `validate_clip.py --kind=skeletal-mesh --character=<герой>` на новом SK и на SK из репозитория.

Артефакты сборки не коммитятся: это проверка профиля, а не новый run. Пересборка героев с `weapon.R` — отдельная задача ([RIG-CONTRACT §12](../../rig/RIG-CONTRACT.md)).

Номер профиля. Сначала профили W4-D получили номер `/3`, но его же независимо получили профили `/3` ветки W4-B (`*-um-master.json`); обе ветки идут от `/2`. Профили W4-D перенумерованы в `/4`: это ветка от `/2` только с `weapon.R`, маршрут um-master, `atlas.ao_bake` и TeamMask из `/3` в неё не входят. Для новых run нужен профиль «`/3` + `weapon.R`» под следующим номером — после коммита обеих веток. Пересборка по `/4` дала те же байты SK, что и по прежнему номеру: номер профиля в FBX не записывается, только в `build-report.json` (`profile.id`).

## Результат

| Герой | Проверок сборки | Провалено | Сокет Weapon | SK из `/4` против v2 | SK из репозитория (`/2`) против v2 |
| --- | --- | --- | --- | --- | --- |
| Arthur | 44 | 0 | `weapon.R` | PASS | FAIL `skeleton_contract`, `weapon_side` |
| Merlin | 41 | 0 | `weapon.R` | PASS | FAIL `skeleton_contract`, `weapon_side` |

Размер SK Arthur не изменился (968 972 байт), меняется только имя кости. sha256 пробных SK, профилей и отчёты — [scratch-builds.json](scratch-builds.json); отчёты валидатора пробных SK — `scratch-*-rigv2-SK.validation.json` (путь клипа в них указывает на `C:/tmp`).

Кость 0 (`SKEL_UM_Humanoid`) и ref-поза (+X, ось X `root` = +Y) у CLI-кандидатов уже соответствуют v2; FAIL у SK из репозитория — только из-за одного имени `weapon`.
