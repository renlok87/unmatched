# Unreal Engine 5.9 Preview 2 для Unmatched

Исследование от 27 ноября 2026 года. Установленный в Windows редактор — **5.9.0 Preview 2, changelist 60738873**. Версия совпала в манифесте Launcher, в `Engine/Build/Build.version` и в свойствах `UnrealEditor.exe`. Именно этот changelist Epic опубликовала 19 ноября с тегом `5.9.0-preview-2`. Обозначение `Release-5.9` в имени ветки встречается и у этой предварительной сборки. Epic выпустила её к AI MegaJam с укороченным циклом QA, а полный выпуск ожидает в 2027 году. [Объявление Epic][announce] · [Номер сборки и известные дефекты][issues]

**Главный результат для проекта.** Штатный MCP уже был в 5.8 и уже включён в Unmatched. В 5.9 наиболее интересны адресные операции над Blueprint, сценой, HUD, анимацией и тестами. На пустом проекте я получил **106 наборов и 1 872 уникальные операции**. Из 12 идентификаторов в адаптере проверки арта `ue_live.py` редактор распознал два. Будущий переход затрагивает контракт автоматизации даже в случае успешной сборки C++. [Анонс 5.8][ue58] · [Адаптер проекта][adapter] · [Каталог, полученный от редактора][inventory]

## Что проверено на установленной сборке

Для эксперимента использовался пустой временный `EngineResearch59.uproject` вне репозитория, со штатным набором плагинов. Ответ `initialize` подтвердил имя временного проекта, путь, PID редактора и CL. Первый запуск с `-NullRHI` и `-NoShaderCompile` завершился ошибкой `Null assigned to TNotNull` при старте. Конкретную причину этого сбоя установить по стеку не удалось. Проверка MCP прошла в повторном запуске с D3D11 и скрытым рендером. Редактор штатно закрылся. Unmatched использовался только как источник текстовых настроек и кода для сравнения.

| Проверка | Что вернул редактор |
|---|---|
| Инициализация с версией протокола из адаптера 5.8 | На запрос `2025-03-26` сервер вернул `2025-11-25`. Обмен запросами после инициализации прошёл. Клиенту со строгой проверкой версии важно учитывать ответ сервера. |
| Обнаружение инструментов | `tools/list` вернул четыре имени — `list_toolsets`, `describe_toolsets`, `describe_tools`, `call_tool`. Так работает включённый поиск инструментов. Через `describe_toolsets` получены описания всех 106 наборов в этой сессии. |
| Выполнение операции | Через `call_tool` выполнен `EditorToolset.AssetToolset.GetAssetContentRoots`. Сервер вернул список, включая `/Game/`. Для этой проверки хватило локального HTTP-клиента без учётной записи LLM. |
| Совместимость старых имён | Распознаны `EditorToolset.EditorAppToolset` и `SlateInspectorToolset.SlateInspectorToolset`. Для остальных десяти имён `describe_toolsets` вернул ошибки внутри поля `errors`. Одной проверки успешного HTTP-ответа здесь недостаточно. |

В JSON сохранены полные имена операций по наборам и результат сверки каждого из 12 старых имён. Числа относятся к этой конфигурации редактора. Исполнение проверено для чтения корней контента. Для остальных операций подтверждена регистрация. [Каталог MCP][inventory]

| Область адаптера 5.8 | Что видно в 5.9 Preview 2 |
|---|---|
| Поиск и чтение ассетов | Старое `editor_toolset.toolsets.asset.AssetTools` отсутствует. У `EditorToolset.AssetToolset` есть `FindAssets`, `GetDependencies`, `ValidateAssets` и `GetAssetContentRoots`. |
| Меши, текстуры, материалы и UObject | В каталоге есть `EditorToolset.StaticMeshToolset`, `SkeletalMeshToolset`, `TextureToolset`, `MaterialToolset`, `MaterialInstanceToolset` и `ObjectToolset` с тем же префиксом. Старые Python-имена этих шести наборов отсутствуют. Сигнатуры конкретных операций требуют отдельной сверки. |
| Сцена и акторы | Старые `SceneTools` и `ActorTools` отсутствуют. У `EditorToolset.LevelToolset` есть `GetCurrentLevel` и `FindActors`. Для действий над актором доступен `EditorToolset.ActorToolset`. |
| Журнал | Старое `EditorToolset.LogsToolset` отсутствует. В `ConsoleToolset.LogsToolset` доступны `GetLogEntries`, `GetLogCategories` и управление подробностью журнала. |

## Как устроена работа с LLM

**Unreal MCP** предоставляет операции редактора локальному клиенту. По умолчанию интерактивный редактор поднимает HTTP-сервер на `127.0.0.1:8000/mcp`. Наборы регистрируются через Toolset Registry. Клиент запрашивает схемы по мере необходимости. Вызовы исполняются последовательно на игровом потоке каждого экземпляра редактора. Для нескольких редакторов предусмотрены отдельные порты и идентификация экземпляра в ответе `initialize`. У инструментов есть аннотации доступа `Read`, `Write` и `Execute`. Клиент может использовать их для запроса подтверждения. У сервера нет встроенной аутентификации. Упакованный клиент может отдельно запустить MCP с операциями, помеченными `AIRuntimeCallable`. Полученные здесь цифры относятся к редактору. [Архитектура и ограничения Unreal MCP][mcp]

**Unreal Assistant** — панель, где можно выбрать сервис Epic или внешний агент. Для внешнего агента редактор запускает локальный процесс через **ACP** (Agent Client Protocol), передаёт ему переписку и подключает его к Unreal MCP. У самого Assistant есть режимы `Ask`, `Read`, `Edit`, `Auto` и `Full`. При выборе внешнего агента панель показывает его модель и собственные режимы подтверждения. Epic документирует готовые варианты для Claude Code, Cursor и других клиентов, а также пользовательскую команду с поддержкой ACP. Для используемого в проекте **Z-Code / GLM-5.3** встроенный профиль и совместимость ACP не подтверждены. Способность клиента работать с MCP извне и наличие ACP-адаптера для панели — две отдельные проверки. [Внешние агенты в Unreal Assistant][assistant] · [Режимы Assistant][notes]

**Контекст для поиска.** Knowledge Base даёт агенту доступ к справочной информации из состояния движка и Markdown. Semantic Search позволяет искать ассеты по смыслу через Content Browser. Индексация обращается к провайдеру описаний и эмбеддингов. Для визуальных ассетов провайдеру обычно отправляются миниатюра, путь, класс и часть метаданных. Успешный локальный вызов MCP сам по себе такого обращения не требует. Для PCG Epic поставляет навык `Skill_PCGGraphGeneration` с описанием узлов и примерами графов. [Knowledge Base в обзоре 5.9][notes] · [Semantic Search и передаваемые данные][semantic] · [PCG и LLM][pcg]

**Unreal Canvas** — экспериментальное рабочее пространство для референсов, кадров сцены и результатов генерации. Пространственные аннотации привязывают замечание к месту в сцене. Canvas Bridge передаёт рендер из Movie Render Graph, а подключённый провайдер генерирует изображение, видео, текст или меш. Доступные модели и оплата зависят от выбранного провайдера и его API-ключа. Для наших досок практичный сценарий — сохранить ракурс, указать проблемную область и получить варианты с той же композицией. Доступ через пользовательские приложения Gemini и Tripo остаётся отдельным способом работы. [Устройство и настройка Unreal Canvas][canvas] · [Анонс Epic][announce]

**Машинное обучение внутри движка.** Neural Network Engine получил экспериментальный runtime LiteRT для инференса моделей. У анимации есть собственные генеративные плагины. Это отдельные возможности для авторинга или исполнения модели. Для диалогового NPC по-прежнему потребовались бы выбранная модель и игровая интеграция. [Обзор AI и ML][notes]

## Что это даёт команде игры

| Задача | Подтверждённая возможность | Практический смысл |
|---|---|---|
| Работать с Blueprint | В проверенной сборке у `BlueprintToolsets.BlueprintToolset` 74 операции, у `BlueprintDslToolset` ещё семь, включая `Read`, `Schema`, `Diff` и `Edit`. | Агент может прочесть граф и показать разницу перед применением правки. Epic исправила в Preview 2 исчезновение размещённых акторов при отказе от AI-правки или её отмене. [Каталог][inventory] · [Исправления Preview 2][notes] |
| Разобрать проблему в HUD | Slate Inspector публикует `Snapshot`, `GetUMGInfo`, `HitTest`, `Screenshot`. В наличии также Widget Static Analysis, Widget Animation и Input. | Снимок дерева помогает выяснить, какой виджет получает ввод. Видимость и итог на экране стоит проверять независимо из-за известных ошибок WidgetFinder и Slate Inspector. [Каталог][inventory] · [Дефекты UI][issues] |
| Автоматизировать тесты и захват кадров | Доступны `DiscoverTests`, `RunTestsByFilter`, `GetTestResults`, `IsLiveCodingReady`, `CaptureGameViewport`, CSV Profiler и GPU Profiler. | Можно связать проверку, лог и кадр в пределах одного редактора. Для приёмочных кадров Unmatched по-прежнему значимы среда packaged `-Bench` и записанный профиль рендера. [Каталог][inventory] · [Эталон проекта][renderref] |
| Сократить ручную работу с арт-пайплайном | Python редактора получил больше API для графов, включая Blueprint, Chooser и StateTree. В локальной сборке используется Python **3.11.8**. Toolset Python публикует поиск символов и `execute_python`. Плагин Python Foundation Packages удалён. | Для повторяемого действия можно подготовить один проверяемый скрипт и возвращать результат. Старые импорты, имена функций и схемы результатов стоит сверять по установленной сборке. [Python и AI-агенты][python] · [Изменения Python][notes] |
| Анимировать фигуры разного сложения | IK Retargeter получил Proximity IK, Pelvis Volume и Limb Twist. AnimGenOffline и интеграция NVIDIA Kimodo поддерживают черновую анимацию в Sequencer по описанию, траектории и ключевым позам. | IK особенно интересен для контакта рук с корпусом и переноса поз между фигурками разного роста. Kimodo обучена на человеческом движении. Пригодность для крыльев и нечеловеческих скелетов требует отдельных примеров. [IK Retargeter][retarget] · [Изменения анимации][notes] · [Исследование NVIDIA][kimodo] |
| Работать над освещением доски и VFX | Обновлены отсечение геометрии Nanite и виртуальные карты теней. AVBOIT помогает корректно совмещать полупрозрачные поверхности и дым, требует настольного SM6, включается отдельно. Для обычных частиц вне Nanite предусмотрен отдельный параметр. | Эталон Unmatched — DX12/SM6, Lumen, **каскадные тени CSM**, High, масштаб 100%. Улучшения VSM сами по себе этому профилю выигрыша не дают. Производительность на досках в исследовании не измерялась. [Рендеринг 5.9][notes] · [AVBOIT][oit] · [Эталон проекта][renderref] |

### Другие изменения движка

- **Геймплей и окружение.** StateTree можно редактировать из скриптов, NavMesh умеет распределять построение по тикам. PCG получил операции для программного редактирования графов. Mass Characters ориентирован на массовое представление персонажей. Для пошаговой доски самый прямой сценарий — подготовка и валидация контента. [Обзор движка][notes] · [Руководство по PCG][pcg]
- **Звук и синематики.** В локальном каталоге есть три отдельных набора MetaSounds для поиска, инспекции и авторинга, а также инструменты Niagara и Sequencer. Для фигур это даёт возможность проверять, как клип связан со звуком и визуальным эффектом. В UAF появились обработчики уведомлений для звука и Niagara. [Каталог][inventory] · [Изменения UAF][notes]
- **Тесты и графовые ассеты.** В поставке есть Modular Test Framework для тестов отдельных плагинов и GraphDsl для текстового представления и редактирования графов. Первый интересен при выделении собственных плагинов. Второй даёт инструментам формат, в котором можно сравнивать структуру графа. [Обзор изменений движка][notes]
- **Браузерная версия.** Появилась экспериментальная цель WebAssembly/WebGPU. Preview 2 поддерживает wasm64 и упаковку Blueprint-only проектов. Для этой версии Epic указывает точную версию emsdk **6.0.10**, отдельную упаковку и проверку в браузере. Это потенциальная платформа для демо Unmatched. Возможность работы существующего сетевого клиента и качество картинки требуют собственного испытания. [Руководство по WebAssembly][wasm]

## Что учитывать при будущем переходе с 5.8

1. **Выбор движка и C++.** В дескрипторе игры указана 5.8. Как минимум `devexec.py`, сборка редактора, упаковка и слоты по умолчанию указывают на `UE_5.8`. В обеих целях игры зафиксированы `BuildSettingsVersion.V7` и `Unreal5_8`. В установленном UBT новейшие значения — `V8` и `Unreal5_9`. У V8 меняется включение каталогов `Tests` при компиляции. Состав обнаруженных automation-тестов имеет смысл сравнить отдельно от результата сборки. [Дескриптор][project] · [Цель редактора][target] · [Скрипт сборки][build] · [Слоты редактора][slots]
2. **Компилятор Windows.** В поставляемом с CL 60738873 файле `Engine/Config/Windows/Windows_SDK.json` основной Windows SDK — `10.0.26100.0`, минимальный — `10.0.22621.0`. Оба найдены на машине. У установленного VS 2022 Build Tools версия продукта `cl.exe` — `14.44.35228`, она попадает в предпочтительный диапазон. Компилятор Insiders из семейства `14.51` попадает в список запрещённых этой сборкой UBT. Фактический выбор компилятора и совместимость игрового модуля остаются открытыми до пробной сборки.
3. **Порты, слоты и cook.** Проект выдаёт слотам порты `8123 + N` и передаёт старое имя секции `/Script/ModelContextProtocolEngine.ModelContextProtocolSettings`. В Preview 2 класс находится в `/Script/ModelContextProtocol.ModelContextProtocolSettings`, а плагин содержит `ClassRedirects`. Действие старого строкового переопределения `-ini:` отдельно не проверялось. В исходниках 5.9 у commandlet автозапуск MCP по конфигурации пропускается, если нет явного флага запуска. При будущей проверке слотов сервер уже позволяет сверить проект, PID и CL в одном ответе. [Слоты][slots] · [Параметры упаковки][pack] · [Официальная справка MCP][mcp]
4. **Известные дефекты именно этого Preview.** При включённом AllToolsets cook может завершиться ошибкой, если в `DirectoriesToNeverCook` указан корень контента плагина (UE-413659). Обе найденные записи Unmatched лежат под `/Game/`, поэтому опубликованное условие само по себе не даёт основания менять упаковку. Для HUD существенны UE-411119 (WidgetFinder может сохранить старый enabled-state), UE-411120 (ложное попадание по скрытой строке списка) и UE-412427 (удаление MVVM-привязки через старый API может молча пропускаться). Для последнего Epic указывает `MVVMToolset.RemoveWidgetViewBinding`. [Дефекты и обходные пути Epic][issues] · [Настройки cook игры][gameini]

Первым кандидатом для отдельной проверки совместимости я бы выбрал **одну операцию чтения ассета через адаптер 7a**. Неизвестные редактору имена уже воспроизведены, а у нового набора есть подтверждённый рабочий вызов. Следующие отдельные вопросы — сборка C++, запуск тестов, cook и изображение обеих досок в эталонном профиле. Исследование не даёт измерений времени кадра, оценки визуальной регрессии или заключения о готовности игры к переходу.

[announce]: https://forums.unrealengine.com/t/preview-2-unreal-engine-5-9-preview/2852840
[issues]: https://forums.unrealengine.com/t/preview-2-unreal-engine-5-9-preview/2852840?page=3
[notes]: https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-5-9-release-notes
[ue58]: https://www.unrealengine.com/news/unreal-engine-5-8-is-now-available
[mcp]: https://dev.epicgames.com/documentation/unreal-engine/unreal-mcp-in-unreal-editor
[assistant]: https://dev.epicgames.com/documentation/unreal-engine/run-external-ai-agents-in-the-unreal-assistant-panel-in-unreal-engine
[semantic]: https://dev.epicgames.com/documentation/unreal-engine/semantic-search-in-unreal-engine
[canvas]: https://dev.epicgames.com/documentation/en-us/unreal-engine/getting-started-with-unreal-canvas-in-unreal-engine
[pcg]: https://dev.epicgames.com/documentation/unreal-engine/working-with-pcg-and-llms-using-unreal-mcp-in-unreal-engine?lang=en-US
[python]: https://dev.epicgames.com/documentation/unreal-engine/using-python-with-ai-agents-in-unreal-engine
[retarget]: https://dev.epicgames.com/documentation/en-us/unreal-engine/ik-rig-animation-retargeting-in-unreal-engine
[kimodo]: https://research.nvidia.com/labs/sil/projects/kimodo/
[oit]: https://dev.epicgames.com/documentation/unreal-engine/adaptive-voxelbased-order-independent-transparency-in-unreal-engine
[wasm]: https://dev.epicgames.com/documentation/unreal-engine/packaging-your-project-for-webassembly
[inventory]: 2026-11-27-ue59-mcp-inventory.json
[adapter]: ../../tools/tripo-pipeline/review/ue_live.py
[project]: ../../unreal/Unmatched/Unmatched.uproject
[target]: ../../unreal/Unmatched/Source/UnmatchedEditor.Target.cs
[build]: ../../tools/s08/build-editor.cjs
[slots]: ../../tools/tripo-pipeline/ue7a/editor_slot.py
[pack]: ../../tools/s08/package-client.ps1
[gameini]: ../../unreal/Unmatched/Config/DefaultGame.ini
[renderref]: ../art-pipeline/render-reference.json
