# Tripo DCC Bridge — локальная конфигурация

Проверено 2026-09-27. Это инструкция рабочего места; vendor-файлы мостов намеренно исключены из Git.

## Установлено

| DCC | Версия моста | Локальный путь | Порт |
|---|---|---|---:|
| Blender 5.2 | 1.0.34 (`bl_info`) | `C:/Users/ren/AppData/Roaming/Blender Foundation/Blender/5.2/scripts/addons/Tripo3d_Blender_Bridge` | 60600 |
| Unreal Engine 5.8 | 1.0.5 (`Tripo3DUEBridge.uplugin`) | `C:/Users/ren/WebstormProjects/unmached/unmached/unreal/Unmatched/Plugins/Tripo3DUEBridge` | 60620 |

Оба локальных handshake проверены в Tripo Studio. В браузере выбирается одна активная DCC-цель за раз; установленный второй мост при этом не удаляется. Для переключения выключить текущий toggle DCC Bridge и включить Blender либо Unreal.

UE-мост имеет тип `Editor`, поэтому используется в редакторе и не входит в packaged client. Плагин не требуется постоянно добавлять в `Unmatched.uproject`: для разового запуска допустим ключ `-EnablePlugins=Tripo3DUEBridge`. Один порт обслуживает один активный экземпляр соответствующего DCC.

## Рабочий порядок

1. Открыть Tripo Studio и DCC Bridge.
2. Запустить нужный DCC и убедиться, что локальный сервер поднят.
3. Включить только нужную цель в панели Tripo.
4. Передать выбранный Tripo asset через Bridge.
5. Сохранить полученный исходник в каталоге конкретного `ASSET-*`; затем прогнать проектные ретопологию, UV, материалы, риг и UM_FBX_v1. Импорт из Tripo не считается готовым игровым ассетом.

Официальные материалы: [export/import to DCC](https://www.tripo3d.ai/help/features/how-to-export-and-import-to-dcc-tools), [UE Bridge](https://www.tripo3d.ai/blog/tripo-dcc-bridge-for-ue), [Blender integration](https://www.tripo3d.ai/integrations/blender).
