# 00. Проверка Unreal MCP (2026-09-02)

## Итог

Unreal MCP работает. Это **встроенный экспериментальный плагин UE 5.8** `ModelContextProtocol` (Engine/Plugins/Experimental/ModelContextProtocol) + плагин `AllToolsets`. Сервер живёт **внутри процесса UnrealEditor** и доступен только пока редактор запущен с проектом, где плагин включён.

| Параметр | Значение |
|---|---|
| Проект-хост | `C:\Users\ren\Documents\Unreal Projects\MCPProject\MCPProject.uproject` (EngineAssociation 5.8) |
| Engine | UE 5.8.2 (`C:\Program Files\Epic Games\UE_5.8`), также установлен UE 5.7 |
| Транспорт | Streamable HTTP, `http://127.0.0.1:8123/mcp` |
| Конфиг | `MCPProject/Config/DefaultEditorPerProjectUserSettings.ini` → `[/Script/ModelContextProtocolEngine.ModelContextProtocolSettings]` `ServerPortNumber=8123`, `ServerUrlPath=/mcp`, `bAutoStartServer=True`, `bEnableToolSearch=True` |
| Claude Code | `~/.claude.json` → `mcpServers.unreal-mcp = { type: http, url: http://127.0.0.1:8123/mcp }` |
| protocolVersion сервера | `2025-11-25` |

## Как запускать

```
"C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe" "C:\Users\ren\Documents\Unreal Projects\MCPProject\MCPProject.uproject" -log
```

Через ~40 с порт 8123 начинает слушать. Если сессия Claude Code стартовала до запуска редактора, MCP-клиент показывает `ConnectionRefused` — нужно переподключить (`/mcp` → reconnect) или перезапустить сессию.

## Протокол (проверено curl/python)

1. `POST /mcp` `initialize` → ответ с заголовком `Mcp-Session-Id`; дальше слать его в каждом запросе.
2. `notifications/initialized` → HTTP 202.
3. `tools/list` → в режиме `bEnableToolSearch=True` только 3 мета-тула: `list_toolsets`, `describe_toolset`, `call_tool`.
4. `tools/call name=call_tool arguments={toolset_name, tool_name, arguments}` — реальный вызов инструмента тулсета.
5. `resources/list` → пусто.

Проверенные вызовы: `EditorToolset.EditorAppToolset.IsPIERunning` → `{"returnValue":false}`; `PluginToolset.PluginToolset.ListEnabledPlugins` → список плагинов. Описания схем приходят на русском (локаль редактора).

## Тулсеты (55), релевантные для разработки игры

| Область | Тулсет | Ключевые инструменты |
|---|---|---|
| Blueprints | `editor_toolset.toolsets.blueprint.BlueprintTools` (53) | `read_graph_dsl` / `write_graph_dsl` (S-expression DSL графов, компиляция), variables, components, event dispatchers, `set_parent`, pins |
| Ассеты | `editor_toolset.toolsets.asset.AssetTools` (21) | `find_assets`, `create_folder`, `read_file`/`write_file`, `save_assets`, `load_asset`, `move`/`duplicate`/`delete`, deps/referencers |
| Сцена/акторы | `SceneTools` (20), `ActorTools` (17), `PrimitiveTools` (4) | `add_to_scene_from_class/asset`, `find_actors`, `load_level`, `trace_world`, transform/components/tags |
| UI (UMG) | `UMGToolSet.UMGToolSet` (24) | `CreateWidgetBlueprint`, `CompileWidgetBlueprint`, дерево виджетов, `BindToEventProperty`, named slots |
| UI автоматизация | `SlateInspectorToolset` (15) | `Snapshot`, `Screenshot`, `Click`, `Type`, `FillForm`, `WaitFor` (Playwright-стиль для редактора) |
| Данные | `DataTableTools` (10), `DataAssetTools` (1), `CurveTableTools` (9), `StringTableTools` (8), `DataRegistryTools` (8) | `create`, `import_file`, `add_rows`/`set_rows`, `get_schema`, `search_row_structs` |
| Импорт | `TextureTools.import_file`, `StaticMeshTools.import_file`, `SkeletalMeshTools.import_file` | импорт png/webp?/fbx |
| Материалы | `MaterialTools` (22), `MaterialInstanceTools` (13) | создание материалов/инстансов, параметры |
| Редактор | `EditorToolset.EditorAppToolset` (22) | `StartPIE`/`StopPIE`/`IsPIERunning`, `OpenEditorForAsset`, камера, выбор акторов/ассетов |
| Логи | `EditorToolset.LogsToolset` (5) | `GetLogEntries(category, pattern, maxEntries)` |
| Тесты | `AutomationTestToolset` (8) | `DiscoverTests`, `ListTests`, `RunTests`, `GetTestResults` |
| Плагины | `PluginToolset` (18) | `CreatePlugin`, `SetPluginEnabled`, зависимости |
| Game Features | `GameFeaturesToolset` (8) | активация/деактивация GF-плагинов |
| GAS / теги | `GASToolsets.*`, `GameplayTagsToolset` | ability inspector, cues, теги |
| Объекты | `ObjectTools` (6) | `get_properties`/`set_properties`, `search_subclasses` |
| Скрипты | `ProgrammaticToolset` (2) | `execute_tool_script`, `get_execution_environment` |
| Прочее | Niagara (5 тулсетов), PCG, Sequencer/ControlRig, StateTree, BehaviorTree, Physics, SemanticSearch, ConfigSettings, AgentSkills, Conversation, Dataflow | по необходимости |

## Ограничения

- Нет инструмента «создать C++ класс». C++ пишется в файлы напрямую; сборка — через UBT/`Build.bat` вне MCP **или** через плагин `LiveCodingToolset` («Live Coding compile toolset», `Engine/Plugins/Experimental/Toolsets/LiveCodingToolset`, Experimental, EditorOnly). Он **не входит в `AllToolsets`** и в `MCPProject` не включён (проверено: `ListDiscoveredPlugins` его видит, `list_toolsets` — нет). Для игрового проекта включить явно в `.uproject`. Не входят в `AllToolsets` также `MVVMToolset`, `ChaosClothAssetToolset`, `MetaHumanGenerator`, `SequencerAnimMixerToolset`, `LiveCodingToolset`.
- `write_graph_dsl` компилирует Blueprint; сложную логику всё равно лучше держать в C++ (сеть, парсинг JSON, state sync).
- Сервер привязан к одному открытому проекту: для игры нужен **свой .uproject** с включёнными `ModelContextProtocol` + `AllToolsets` и тем же ini-блоком.
