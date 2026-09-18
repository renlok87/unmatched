# R8 — Возможности UE 5.8 для UE-клиента Unmatched

Дата: 2026-09-02. Ридер: R8-ue58-capabilities.

Обозначения источников:
- `$UE` = `C:\Program Files\Epic Games\UE_5.8\Engine` (локально установленный UE 5.8.2; все `file:line` ниже — из этой установки, прочитаны напрямую).
- `$REPO` = `C:\Users\ren\WebstormProjects\unmached\unmached`.
- Пометка **[неверифицировано]** — факт взят из вторичного источника (поисковая сводка, форум, блог) и не подтверждён исходниками/официальной документацией. Пометка **[по докам]** — из официальной страницы dev.epicgames.com (URL указан).

---

## 1. Краткое резюме

1. **Версия движка.** Установлен UE 5.8.2 (`$UE/Build/Build.version`: MajorVersion 5, MinorVersion 8, PatchVersion 2, Changelist 56702186, BranchName `++UE5+Release-5.8`). По заявлению Epic, «UE 5.8 is the last planned major Unreal Engine 5 release on our roadmap as we ramp up work on UE6» (цитата из анонса Epic, воспроизведена агрегаторами; сама страница анонса вернула 403 при загрузке — см. §4). Хотфиксы: 5.8.1 (28.07.2026), 5.8.2 (конец августа 2026) — форум Epic.
2. **Сеть.** Всё необходимое для GraphQL-клиента есть в движке без сторонних плагинов: модуль `HTTP` (`FHttpModule::CreateRequest`, libcurl на Windows, делегаты по умолчанию на game thread) и модуль `WebSockets` (`IWebSocket`, libwebsockets на Windows/Mac/Linux/Android/iOS, отдельный поток, события на game thread). **Сабпротокол передаётся штатно**: `FWebSocketsModule::CreateWebSocket(Url, Protocol /*"graphql-transport-ws"*/, UpgradeHeaders)` → `lws_client_connect_info.protocol` → заголовок `Sec-WebSocket-Protocol`. Автореконнекта нет — нужен свой state machine (backoff + повторный `Connect()`, объект переиспользуем после финализации).
3. **JSON.** `FJsonObjectConverter` покрывает вложенные USTRUCT, `TArray`, `TSet`, `TMap` (ключи — только через строку), `FText`, `FDateTime` (ISO 8601), `FGuid`, `FInstancedStruct`, `FJsonObjectWrapper` (произвольный JSON). **int64**: числа JSON хранятся как `double` (`FJsonValueNumber`) → потеря точности выше 2^53; безопасный путь — передавать int64 строкой (конвертер парсит `FCString::Atoi64`) либо парсить с флагом `FJsonSerializer::EFlags::StoreNumbersAsStrings`. Для нашего API это некритично (GraphQL `Int` 32-битный; кастомные скаляры — `DateTime`, `JSON`).
4. **GraphQL-плагины для UE.** Честный вердикт: пригодного open-source клиента с `graphql-transport-ws` не найдено. `badumbat/UEGraphQL` — репозиторий не существует (`gh repo view` → «Could not resolve»), у Mountea-Framework GraphQL-репозиториев нет. Единственный коммерческий вариант — «GraphQL with Blueprints (AWS)» (547 Game Studio / ex-Multiplayscape, ориентирован на AppSync, subscriptions по graphql-ws). **Решение: писать свой тонкий слой** (HTTP POST JSON + state machine graphql-transport-ws поверх `IWebSocket`), это ~несколько сотен строк C++.
5. **UI.** UMG (на Slate) — базовый инструмент; **CommonUI** (плагин в комплекте, не beta, выключен по умолчанию) даёт стек экранов (`UCommonActivatableWidgetStack`/`Queue`), input routing (`ECommonInputMode` Menu/Game/All, `FUIInputConfig`), back-action и требует `UCommonGameViewportClient`. В 5.8 Epic объявил «Unified Input System: Common UI and Enhanced Input» (Input Mode на GameplayTag-контейнерах, Input Debugger), но страница «Using CommonUI with Enhanced Input» всё ещё помечена Experimental с фразой «We do not recommend attempting to ship titles with this feature at this time» (текст времён 5.2). **Enhanced Input** — включён по умолчанию, стандарт.
6. **Paper2D** — в 5.8 присутствует, `EnabledByDefault: true`, без флагов Beta/Experimental/Deprecated, документация 5.8 есть; в release notes 5.8 не упомянут. Для доски-карточек рациональнее **3D-сцена из плоскостей/мешей + UMG-оверлей** или `UWidgetComponent` (World/Screen space), Paper2D — необязателен.
7. **webp нативно НЕ импортируется** (`EImageFormat` без WebP; ImageWrapper/Interchange поддерживают png/jpg/bmp/tga/exr/hdr/tif/dds/psd/uejpeg; libwebp в ThirdParty нет). При этом **в проекте 276 `.webp` против 112 `.png`**, а `scripts/sync-card-assets.mjs` пишет карты в `.webp` → нужен конвейер конвертации в PNG (или сторонний плагин для рантайм-загрузки).
8. **Токены.** `USaveGame` пишет незашифрованный `.sav` (`FFileHelper::SaveArrayToFile`). В движке нет обёрток DPAPI/Keychain. Для шифрования есть плагин `PlatformCrypto` (включён по умолчанию): `Encrypt_AES_256_GCM/Decrypt_AES_256_GCM`. `FAES` (ECB) — Epic: «DO NOT USE … for any new place».
9. **Тесты.** Automation Spec (`DEFINE_SPEC`, `Describe/It/LatentIt`), Functional Tests (`AFunctionalTest`), AutomationDriver; запуск из CLI `UnrealEditor-Cmd … -ExecCmds="Automation RunTests …;Quit" -testexit="Automation Test Queue Empty" -ReportOutputPath=…` (в коде парсится `ReportOutputPath=`, в доках написано `-ReportExportPath` — расхождение). MCP-тулсет `AutomationTestToolset` умеет DiscoverTests/ListTests/RunTests/GetTestResults.
10. **Локализация.** `FText` + `LOCTEXT/NSLOCTEXT`, String Tables (C++ `LOCTABLE_*`, CSV, ассет), Localization Dashboard (помечен experimental, но «stable and used internally»), `-CULTURE=` из командной строки, `+CulturesToStage`. MCP-тулсет `StringTableTools` есть.
11. **GameplayTags / DataRegistry / Game Features / Lyra.** GameplayTags — runtime-модуль движка; DataRegistry, GameFeatures, ModularGameplay, MVVM — плагины со статусом **Beta** (`IsBetaVersion: true`). Lyra-плагины `CommonGame`/`CommonUser` в движке отсутствуют (только в сэмпле Lyra с Fab).
12. **Сборка без VS GUI.** UBT/`Build.bat` и Live Coding (`LiveCodingConsole.exe`, консольные команды `LiveCoding.Compile`/`CompileSync`) не требуют IDE, требуют только MSVC-тулчейн: `Windows_SDK.json` — минимум MSVC 14.38.33130, предпочтительно 14.50 (VS2026 18.0) / 14.44 (VS2022 17.14), забанены 14.39.x, 14.40–14.43, ранние 14.44/14.50; Windows SDK 10.0.22621.0 (min 10.0.19041.0). Build Tools for Visual Studio 2022 — официально описаны в контексте VS Code **[по докам, через поисковую сводку]**.
13. **Платформы.** В установленной сборке: бинарники Win64 + Mac (`$UE/Binaries/Mac`), платформенные папки Android/IOS/VisionOS/Windows (`$UE/Platforms`), конфиги Android/IOS/Linux/Mac/Windows; папки `Binaries/Linux` нет — Linux только кросс-компиляцией с отдельным тулчейном (release notes 5.8: v26 clang-20.1.8). Packaging — `RunUAT.bat BuildCookRun …`.
14. **Unreal MCP** — встроенный экспериментальный плагин (`IsExperimentalVersion: true`, `NoRedist: true`), транспорт только HTTP/SSE, loopback, без аутентификации, вызовы инструментов сериализованы на game thread. Есть тулсеты для Blueprints (S-expression DSL), UMG (24 инструмента), DataTable/StringTable/DataRegistry, текстур (импорт через `TextureFactory`), автотестов, Slate-инспектора (Playwright-подобные Click/Type/FillForm/WaitFor/Screenshot), **и `LiveCodingToolset` («Live Coding compile toolset»)** — это противоречит утверждению локального документа «нет инструмента … собрать проект» (нужно проверить `describe_toolset`).

---

## 2. Факты по фокусу

### 2.1. Установка движка и версия

| Факт | Источник |
|---|---|
| UE 5.8.2, CL 56702186, ветка `++UE5+Release-5.8`, `IsPromotedBuild: 1` | `$UE/Build/Build.version` |
| Хост-проект MCP: `C:\Users\ren\Documents\Unreal Projects\MCPProject\MCPProject.uproject` (EngineAssociation 5.8, плагины `ModelContextProtocol`, `AllToolsets`) | `$REPO/docs/unreal/00-mcp-verification.md:9`; сам `.uproject` (прочитан) |
| Установлен также UE 5.7 | `$REPO/docs/unreal/00-mcp-verification.md:10` |
| «UE 5.8 is the last planned major Unreal Engine 5 release on our roadmap as we ramp up work on UE6. We will continue to support UE5 for bug fixes and regressions, and may add another official release if circumstances warrant it.» | цитата анонса Epic (https://www.unrealengine.com/news/unreal-engine-5-8-is-now-available — при прямой загрузке HTTP 403; текст воспроизведён в поисковой сводке и в GamesBeat/VGTimes) **[неверифицировано напрямую]**; Tom Looman: «The release of UE 5.8 marks the final release before Epic Games is moving development efforts to Unreal Engine 6» (https://tomlooman.com/unreal-engine-5-8-performance-highlights/) |
| Форумный анонс 5.8 упоминает «accelerate workflows with the integrated MCP plugin for LLMs» | https://forums.unrealengine.com/t/unreal-engine-5-8-released/2729274 |
| Release notes 5.8: разделы «Unified Input System: Common UI and Enhanced Input», «MCP Server (Experimental)», Zenserver как cooked output store по умолчанию, WASAPI-аудио по умолчанию на Windows, iOS keyboard/mouse | https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-5-8-release-notes |
| Хотфиксы 5.8.1 (>260 фиксов) и 5.8.2 | https://forums.unrealengine.com/t/5-8-1-hotfix-released/2738864 , https://forums.unrealengine.com/t/5-8-2-hotfix-released/2746335 |

### 2.2. Модуль HTTP (`FHttpModule`, `IHttpRequest`)

**API (заголовки):**

| Элемент | Источник |
|---|---|
| `static FHttpModule& Get()` — singleton, подгружает модуль | `$UE/Source/Runtime/Online/HTTP/Public/HttpModule.h:59` |
| `TSharedRef<IHttpRequest, ESPMode::ThreadSafe> CreateRequest()` | `HttpModule.h:71` |
| Таймауты модуля: `GetHttpTotalTimeout()`, `GetHttpConnectionTimeout()`, `GetHttpActivityTimeout()`, `GetHttpMaxConnectionsPerServer()` | `HttpModule.h:87-113` |
| Дефолты ini: `[HTTP] HttpConnectionTimeout=30`, `HttpActivityTimeout=30`; total timeout по умолчанию 0 («0 is no timeout») | `$UE/Config/BaseEngine.ini:39-41`; `HttpModule.h:321-322`; `$UE/Source/Runtime/Online/HTTP/Private/HttpModule.cpp:96` |
| `EHttpRequestDelegateThreadPolicy { CompleteOnGameThread = 0, CompleteOnHttpThread }` | `Interfaces/IHttpRequest.h:14-18` |
| По умолчанию `DelegateThreadPolicy = CompleteOnGameThread` | `$UE/Source/Runtime/Online/HTTP/Private/GenericPlatform/HttpRequestCommon.h:142` |
| `EHttpRequestPriority { Lowest, Low, Normal, High, Highest }` | `IHttpRequest.h:24-32` |
| `FHttpRequestCompleteDelegate = TTSDelegate<void(FHttpRequestPtr, FHttpResponsePtr, bool bProcessedSuccessfully)>`; комментарий: `bProcessedSuccessfully == true` не означает 2xx — проверять `Response->GetStatus()`, `GetFailureReason()`, `GetResponseCode()` | `IHttpRequest.h:43-56` |
| `SetVerb`, `SetURL`, `SetOption`, `SetContent(TArray<uint8>)`, `SetContentAsString`, `SetContentAsStreamedFile`, `SetContentFromStream`, `SetResponseBodyReceiveStream` | `IHttpRequest.h:190-271` |
| `SetHeader(Name, Value)`, `AppendToHeader` | `IHttpRequest.h:297,310` |
| `SetTimeout(float)`, `SetActivityTimeout(float)`, `ClearTimeout()`, `ResetTimeoutStatus()`, `GetTimeout()` | `IHttpRequest.h:318-347` |
| `ProcessRequest()`, `OnProcessRequestComplete()`, `OnRequestProgress64()`, `OnRequestWillRetry()`, `OnHeaderReceived()`, `OnStatusCodeReceived()`, `CancelRequest()`, `GetResponse()` | `IHttpRequest.h:356-393` |
| `SetDelegateThreadPolicy` — при `CompleteOnHttpThread` делегат может прийти из любого потока, код должен быть thread-safe | `IHttpRequest.h:410-419` |
| `ProcessRequestUntilComplete()` — блокирующий вариант (принудительно `CompleteOnHttpThread`) | `IHttpRequest.h:435-439` |
| `SetPriority/GetPriority` | `IHttpRequest.h:446-453` |
| Ответ: `GetResponseCode()`, `GetContentAsString()`, `GetContentAsUtf8StringView()`, `TakeContent()` | `Interfaces/IHttpResponse.h:118-141` |
| База: `GetURL()`, `GetEffectiveURL()`, `GetStatus()`, `GetFailureReason()`, `GetHeader()`, `GetAllHeaders()`, `GetContentType()`, `GetContentLength()`, `GetContent()` | `Interfaces/IHttpBase.h:100-167` |
| Retry: `FHttpRetrySystem::FManager::CreateRequest(RetryLimitCountOverride, RetryTimeoutRelativeSecondsOverride, RetryResponseCodes, RetryVerbs, …, RetryLimitCountForConnectionErrorOverride)`, `SetDefaultRetryLimit` | `HttpRetrySystem.h:197-223`; типы `FRetryResponseCodes = TSet<int32>`, `FRetryVerbs = TSet<FName>` — `:43-44` |
| Domain allowlist: `FHttpManager::IsDomainAllowed(Url)` | `HttpManager.h:256` |
| Реализация на Windows: libcurl (`FCurlHttpManager`, `FCurlHttpRequest`), WinHttp доступен как альтернатива для Windows-группы; XCurl — для GDK | `$UE/Source/Runtime/Online/HTTP/HTTP.Build.cs:22-36,47`; `Private/Windows/WindowsPlatformHttp.cpp:80-97` |
| Проверка сертификатов curl: `FCurlHttpManager::CurlRequestOptions.bVerifyPeer` (переключается в `WindowsPlatformHttp.cpp:202-203`) | там же |

**Замечания:**
- HTTP-запросы асинхронны: обработка в отдельном HTTP-потоке (`Private/HttpThread.cpp`, `EventLoopHttpThread.cpp`), делегаты по умолчанию — на game thread (`HttpRequestCommon.h:142`).
- Заголовки задаются `SetHeader` — для GraphQL: `Content-Type: application/json`, `Authorization: Bearer <token>`. Бэкенд ждёт именно Bearer в `Authorization` (`$REPO/backend/src/auth/strategies/jwt.strategy.ts:16`: `ExtractJwt.fromAuthHeaderAsBearerToken()`).
- Веб-клиент шлёт HTTP на `http://localhost:3000/graphql` (`$REPO/src/env.ts:7`).

### 2.3. Модуль WebSockets (`IWebSocket`) и `graphql-transport-ws`

**API интерфейса:**

| Элемент | Источник |
|---|---|
| `virtual void Connect()` — «Use this after setting up event handlers or **to reconnect after connection errors**» | `$UE/Source/Runtime/Online/WebSockets/Public/IWebSocket.h:12-16` |
| `Close(int32 Code = 1000, const FString& Reason)` | `IWebSocket.h:23` |
| `IsConnected()` | `IWebSocket.h:28` |
| `Send(const FString&)` (UTF-8 текст), `Send(const void*, SIZE_T, bool bIsBinary)` | `IWebSocket.h:34,42` |
| `SetTextMessageMemoryLimit(uint64)` — «Default from config TextMessageMemoryLimit under [WebSockets] or 1MB» | `IWebSocket.h:45-49` |
| События: `OnConnected()`, `OnConnectionError(const FString&)`, `OnClosed(int32 StatusCode, const FString& Reason, bool bWasClean)`, `OnMessage(const FString&)`, `OnBinaryMessage(Data,Size,bIsLastFragment)`, `OnRawMessage(Data,Size,BytesRemaining)`, `OnMessageSent(const FString&)` | `IWebSocket.h:55-101` |

**Фабрика и сабпротокол:**

| Факт | Источник |
|---|---|
| `CreateWebSocket(const FString& Url, const TArray<FString>& Protocols, const TMap<FString,FString>& UpgradeHeaders = {})` | `Public/WebSocketsModule.h:62` |
| `CreateWebSocket(const FString& Url, const FString& Protocol = FString(), const TMap<FString,FString>& UpgradeHeaders = {})` — «Protocol an optional sub-protocol» | `WebSocketsModule.h:72` |
| Пустые протоколы отфильтровываются; событие `OnWebSocketCreated` | `Private/WebSocketsModule.cpp:89-99` |
| `FWebSocketsModule::Get()` сам грузит модуль (`LoadModuleChecked`), но `check(IsInGameThread())` | `WebSocketsModule.cpp:77-86` |
| Список «известных» протоколов берётся из ini `[WebSockets] +WebSocketsProtocols=` (по умолчанию ws, wss, v10/v11/v12.stomp, xmpp) и передаётся в `InitWebSockets(Protocols)`; это внутренние lws-протоколы, **не** ограничение на сабпротокол клиента | `WebSocketsModule.cpp:33-44`; `$UE/Config/BaseEngine.ini:73-79` |
| В LWS-реализации список `Protocols` склеивается запятой и кладётся в `lws_client_connect_info.protocol` → заголовок `Sec-WebSocket-Protocol` | `Private/Lws/LwsWebSocket.cpp:787-795, 805` |
| Доп. заголовки апгрейда добавляются в `LWS_CALLBACK_CLIENT_APPEND_HANDSHAKE_HEADER` (строка вида `Name: Value\r\n`) | `LwsWebSocket.cpp:537-544`; `WebSocketsModule.cpp:19-27` |
| Схемы URL: `ws`, `wss` (SSL), `wss+insecure` (SSL + self-signed) — иначе ошибка «Bad protocol … Use either 'ws', 'wss', or 'wss+insecure'» | `LwsWebSocket.cpp:736-759` |
| `Connect()` допустим только из состояния `None`; иначе Warning «State is not None … unable to start connecting!» | `LwsWebSocket.cpp:105-109` |
| После закрытия/ошибки `GameThreadFinalize()` сбрасывает `State = None` («Will be re-usable on final delegate triggering») и **затем** бродкастит `OnConnectionError` либо `OnClosed` → тот же объект можно переподключать повторным `Connect()` | `LwsWebSocket.cpp:625-648` |
| Все события (`OnConnected/OnMessage/OnRawMessage/OnBinaryMessage`) бродкастятся из `GameThreadTick()` — т.е. на game thread | `LwsWebSocket.cpp:595-618` |
| Оптимизация: если на момент `Connect()` не было биндинга на `OnMessage`/`OnRawMessage`/`OnBinaryMessage`, соответствующие события никогда не вызываются («For performance reasons if nothing was bound at Connect() time») | `Private/Lws/LwsWebSocket.h:327-341` |
| Лимит текстового сообщения: при превышении `MaxTextMessageBufferSize` соединение закрывается с причиной «Received text message exceeded memory limit of N bytes» | `LwsWebSocket.cpp:313-318`; дефолт `TextMessageMemoryLimit=1048576` — `BaseEngine.ini:80`, `LwsWebSocketsManager.cpp:528-529` |
| WS-уровень ping/pong: `PingPongInterval` из `[WebSockets.LibWebSockets]` (по умолчанию 0 = выключено) → `ws_ping_pong_interval`; входящий PONG игнорируется (`case LWS_CALLBACK_RECEIVE_PONG: break;`). API для ручного WS-ping нет | `Private/Lws/LwsWebSocketsManager.cpp:192-194`; `LwsWebSocket.cpp:510-511` |
| Отдельный поток `LibwebsocketsThread` (128 KB стек, приоритет BelowNormal по умолчанию), тик по `ThreadTargetFrameTimeInSeconds=0.0333` | `LwsWebSocketsManager.cpp:239-257`; `BaseEngine.ini:82-85` |
| Конфиг-ключи: `[WebSockets.LibWebSockets] bPollService, ServiceTimeoutMs, ThreadTargetFrameTimeInSeconds, ThreadMinimumSleepTimeInSeconds, MaxHttpHeaderData (32 KB), PingPongInterval, ThreadStackSize, ThreadPriority`; `[LwsWebSocket] bDisableDomainAllowlist, bDisableCertValidation` | `LwsWebSocketsManager.cpp:86-93,188-194,239-243` |
| **Domain allowlist**: перед `Connect()` URL проверяется `FURLRequestFilter(TEXT("Online.HttpManager"), GEngineIni)`; при отказе — `OnConnectionError("Invalid Domain")`. Фильтр пуст → «no filtering is performed and any URL is allowed»; в `BaseEngine.ini` секции `[Online.HttpManager]` нет → по умолчанию всё разрешено | `LwsWebSocket.cpp:112-125`; `$UE/Source/Runtime/Core/Public/Misc/URLRequestFilter.h:15,39-46`; grep `BaseEngine.ini` — секция отсутствует |
| SSL: контекст из модуля `SSL`, доп. сертификаты через `FSslModule::GetCertificateManager()`; HTTP-прокси читается как у `FHttpModule` (`FPlatformHttp::GetConfiguredProxyAddress`) | `LwsWebSocketsManager.cpp:205-224, 441-451, 196-200` |
| Выбор реализации: LWS для Windows/Android/Mac/Unix/iOS; WinHttp — только если LWS недоступен и Windows ≥ 8.1; зависимости OpenSSL + libWebSockets + zlib | `WebSockets.Build.cs:7-17, 25-31, 52-69, 118` |

**Сверка с бэкендом и веб-клиентом (что именно должен воспроизвести UE-клиент):**

| Факт | Источник |
|---|---|
| Бэкенд: `subscriptions: { 'graphql-ws': true }` (библиотека `graphql-ws` ^6.0.6) → сервер говорит на сабпротоколе `graphql-transport-ws` | `$REPO/backend/src/graphql/graphql.module.ts:19-21`; `$REPO/backend/package.json:70` |
| Аутентификация подписок: контекст берёт `connectionParams.authorization` / `Authorization` / `token`, дописывает `Bearer ` при необходимости, и отдаёт как `req.headers.authorization` для `GqlAuthGuard` | `graphql.module.ts:23-33` |
| Веб-клиент: `createClient({ url: ws://localhost:3000/graphql, connectionParams: () => ({ authorization: 'Bearer <token>' }), lazy: true, retryAttempts: 5 })` | `$REPO/src/lib/apolloClient.ts:16-36`; `$REPO/src/env.ts:8` |
| Кастомные скаляры: `DateTimeScalar`, `JSONScalar` | `graphql.module.ts:5` |
| HTTP-путь `/graphql`, порт 3000 (по умолчанию) | `$REPO/src/env.ts:7-8` |

**Протокол `graphql-transport-ws` (спецификация https://github.com/enisdenjo/graphql-ws/blob/master/PROTOCOL.md):**
- Сабпротокол: «The WebSocket sub-protocol for this specification is: `graphql-transport-ws`».
- Сообщения: `connection_init {type, payload?}` → `connection_ack`; `ping`/`pong` (двунаправленно; «A Pong must be sent in response … as soon as possible», pong может быть unsolicited heartbeat); `subscribe {id, type, payload:{operationName?, query, variables?, extensions?}}`; `next {id, payload: ExecutionResult}`; `error {id, payload: GraphQLError[]}` (терминальное, `complete` после него не приходит); `complete {id}` (двунаправленно).
- Коды закрытия: `4400` invalid message, `4401` subscribe до ack (Unauthorized), `4403` Forbidden (рекомендуется при отказе в auth), `4408` Connection initialisation timeout, `4409` Subscriber for <id> already exists, `4429` Too many initialisation requests; клиент закрывает `1000`.
- Уникальность `id` только среди активных операций; после `complete` id можно переиспользовать. Обе стороны «must … be prepared to receive (and ignore) messages for operations that they consider already completed».
- Query/mutation по WS тоже допустимы («at most one Next»), но у нас HTTP для них (как в веб-клиенте: `split` по `operation === 'subscription'`, `apolloClient.ts:52-62`).

### 2.4. Json / JsonUtilities

**DOM и сериализация:**

| Факт | Источник |
|---|---|
| `FJsonValueNumber` хранит `double Value` | `$UE/Source/Runtime/Json/Public/Dom/JsonValue.h:199-212` |
| `TJsonValueNumberString` — «A Json Number Value, stored internally as a string so as not to lose precision»; `TryGetNumber(int64&)` парсит строку (`LexTryParseString`) | `JsonValue.h:219-244, 587-641` |
| `FJsonSerializer::EFlags { None = 0, StoreNumbersAsStrings = 1 }`; `Deserialize(Reader, OutValue, EFlags)`; при флаге числа читаются через `ReadNumberAsString` | `$UE/Source/Runtime/Json/Public/Serialization/JsonSerializer.h:294-301, 572-580, 97-101` |
| `TryGetNumber` перегрузки для double/float/int8..int64/uint8..uint64 на базовом `FJsonValue` | `JsonValue.h:44-71` |
| `FJsonObjectWrapper` — `USTRUCT(BlueprintType)`, поля `FString JsonString`, `TSharedPtr<FJsonObject> JsonObject`, методы `JsonObjectToString/JsonObjectFromString`; в конвертере проходит «как есть» (escape hatch для произвольного JSON, например скаляра `JSON` нашего API) | `$UE/Source/Runtime/JsonUtilities/Public/JsonObjectWrapper.h:21-41`; `Private/JsonObjectConverter.cpp:412-415, 1307-1310` |

**`FJsonObjectConverter` (сигнатуры):**

| Метод | Источник |
|---|---|
| `UStructToJsonObject<T>(InStruct, CheckFlags, SkipFlags, ExportCb)` | `Public/JsonObjectConverter.h:100-109` |
| `UStructToJsonObject(StructDef, Struct, OutJsonObject, CheckFlags, SkipFlags, ExportCb, EJsonObjectConversionFlags)` | `:124` |
| `UStructToJsonObjectString(...)` (+ шаблон, `bPrettyPrint`) | `:140-166` |
| `JsonObjectToUStruct(JsonObject, StructDef, OutStruct, CheckFlags, SkipFlags, bStrictMode=false, FText* OutFailReason, ImportCb)` (+ шаблон) | `:239-265` |
| `JsonObjectStringToUStruct<T>(JsonString, OutStruct, …)`, `JsonArrayStringToUStruct<T>`, `JsonArrayToUStruct<T>` | `:313, 352, 391` |
| `JsonValueToUProperty(...)`, `UPropertyToJsonValue(...)` | `:297, 221` |
| Колбэки: `CustomExportCallback = TDelegate<TSharedPtr<FJsonValue>(FProperty*, const void*)>`, `CustomImportCallback = TDelegate<bool(const TSharedPtr<FJsonValue>&, FProperty*, void*)>`; готовый `ExportCallback_WriteISO8601Dates` | `:80-89`; `.cpp:1479-1488` |
| `EJsonObjectConversionFlags { SkipStandardizeCase, WriteTextAsComplexString, SuppressClassNameForPersistentObject }` | `:30-47` |

**Поведение по типам (реализация `JsonObjectConverter.cpp`):**

| Тип | Поведение | Источник |
|---|---|---|
| Имена полей при экспорте | `StandardizeCase`: первая буква в нижний регистр, `ID`→`Id` (если не `SkipStandardizeCase`) | `.cpp:33-42, 450-452` |
| Целые (`int32/int64/uint…`) из JSON **строки** | `FCString::Atoi64` — «so we don't lose any precision going through AsNumber (aka double)» | `.cpp:646-650` |
| Целые из JSON **числа** | `(int64)JsonValue->AsNumber()` — через double | `.cpp:652-655` |
| float/double | `AsNumber()` | `.cpp:639-643` |
| enum | из строки по имени или из числа | `.cpp:593-616` |
| `TArray`, `TSet` | рекурсивно по элементам | `.cpp:680-700, 775-802` |
| `TMap` импорт | только из JSON-объекта; ключ формируется как `FJsonValueString(Entry.Key)` и импортируется в `KeyProp` (т.е. ключ должен парситься из строки: `FString`, `FName`, enum, число…); `null`-значения пропускаются | `.cpp:716-760` |
| `TMap` экспорт | ключ через `TryGetString` либо `ExportTextItem_Direct`; enum/FName-ключи camelCase-ятся (если не `SkipStandardizeCase`) | `.cpp:190-218` |
| Вложенные USTRUCT | рекурсивно `JsonAttributesToUStructWithContainer` | `.cpp:861, 966` |
| Структуры с `ImportTextItem` из строки | пробуется `ImportTextItem`, затем `ImportText_Direct` | `.cpp:1054-1063` |
| `FDateTime` | из строки: `min/max/now`, затем `ParseIso8601`, затем `Parse` | `.cpp:997-1017` |
| `FGuid` | `FGuid::Parse`, fallback `ImportText_Direct` | `.cpp:1039-1040` |
| `FText` | из строки или объекта `{culture: text}` | `.cpp:819-856, 541` |
| `FInstancedStruct` | плоский объект + `_structType` для round-trip | `.cpp:265-268, 908-942` |
| `UObject*` | по значению (с `_ClassName`) или строкой-ссылкой | `.cpp:320, 1098-1189` |
| `TOptional` | разворачивается | `.cpp:358, 1203` |
| `bStrictMode` | ошибки на лишние атрибуты / несоответствие размера C-массива | `.cpp:1252-1257, 1278-1283, 1343` |
| Custom import callback имеет приоритет над дефолтом («fall through to default cases») | `.cpp:586-590` |

### 2.5. GraphQL-плагины для UE — вердикт

| Кандидат | Результат проверки | Источник |
|---|---|---|
| `badumbat/UEGraphQL` | **Репозиторий не существует**: `gh repo view badumbat/UEGraphQL` → «Could not resolve to a Repository with the name 'badumbat/UEGraphQL'» | `gh` (аккаунт залогинен), 2026-09-02 |
| Mountea (Mountea-Framework) | В списке репозиториев организации (`gh repo list Mountea-Framework`) GraphQL/HTTP-плагинов нет (Dialogue, Quest, Inventory, Interaction, Builder, ToolsLibrary…); веб-поиск «Mountea GraphQL» — ничего | `gh`; WebSearch |
| `gh search repos "graphql unreal"`, `"graphql ue5"`, `"graphql-ws unreal"` | вернули пустые массивы `[]` (возможна особенность поиска — трактовать как «не найдено», а не «не существует») | `gh` |
| «GraphQL with Blueprints (AWS)» — Marketplace/Fab, 547 Game Studio (ex-Multiplayscape), коммерческий, с исходниками; заявлены subscriptions по graphql-ws (ссылка на PROTOCOL.md), ориентация на AWS AppSync; «you can use this plugin with Apollo or hasura by changing some of its code» | https://www.unrealengine.com/marketplace/en-US/product/graphql-plugin **[неверифицировано, по описанию листинга]** |
| `cman-dev-ue/EnjAPIQueryPlugin` — только query/mutation к Enjin API, без подписок | https://github.com/cman-dev-ue/EnjAPIQueryPlugin **[неверифицировано]** |
| Community wiki «WebSocket Client - C++» — пример `FWebSocketsModule::Get().CreateWebSocket(ServerURL, ServerProtocol)` | https://unrealcommunity.wiki/websocket-client-cpp-5vk7hp9e |

**Вердикт:** готового поддерживаемого open-source GraphQL-клиента с `graphql-transport-ws` для UE 5.8 нет; коммерческий AWS-плагин избыточен и заточен под AppSync. Свой слой поверх `FHttpModule` + `IWebSocket` — единственный надёжный путь; вся нужная инфраструктура (сабпротокол, заголовки, JSON) есть в движке (§2.2–2.4).

### 2.6. UI: UMG, Slate, CommonUI, MVVM

| Факт | Источник |
|---|---|
| Модули `Slate`, `SlateCore`, `UMG` — runtime-модули движка | `$UE/Source/Runtime/Slate`, `SlateCore`, `UMG` (каталоги присутствуют); `SlateCore/Public/Widgets/DeclarativeSyntaxSupport.h` |
| `UWidgetComponent : UMeshComponent`, `EWidgetSpace { World, Screen }` — UMG-виджет в 3D-сцене | `$UE/Source/Runtime/UMG/Public/Components/WidgetComponent.h:25-28, 95` |
| CommonUI: `EnabledByDefault: false`, `IsBetaVersion: false`; модули `CommonUI`, `CommonUIEditor`, `CommonInput`; зависит от `EnhancedInput`, `GameplayTagsEditor`, `EngineAssetDefinitions` | `$UE/Plugins/Runtime/CommonUI/CommonUI.uplugin` |
| Описание CommonUI **[по докам]**: «toolbox for creating rich, multi-layered user interfaces with cross-platform support»; библиотека виджетов, style data assets, «Input Routing system that can give UI widgets selective interactivity», console-specific icons, cardinal navigation для геймпадов | https://dev.epicgames.com/documentation/en-us/unreal-engine/common-ui-plugin-for-advanced-user-interfaces-in-unreal-engine |
| `UCommonActivatableWidgetContainerBase : UWidget` — `AddWidget<T>(Class)`, `AddWidget<T>(Class, InitFunc)`, `AddWidgetInstance` (legacy), `RemoveWidget`, `GetActiveWidget`, `TransitionCurveType`, BP: `BP_AddWidget` | `$UE/Plugins/Runtime/CommonUI/Source/CommonUI/Public/Widgets/CommonActivatableWidgetContainer.h:24-73, 112, 157` |
| `UCommonActivatableWidgetStack` (:202), `UCommonActivatableWidgetQueue` (:235) | там же |
| `UCommonActivatableWidget`: `ActivateWidget/DeactivateWidget`, `GetDesiredInputConfig() → TOptional<FUIInputConfig>`, `BP_OnHandleBackAction`, `bIsBackHandler`, `bAutoActivate`, `bSupportsActivationFocus`, `bIsModal`, `bAutoRestoreFocus` | `Public/CommonActivatableWidget.h:52-55, 108, 165, 182-224` |
| `ECommonInputMode { Menu («Input is received by the UI only»), Game («…by the Game only»), All («…by UI and the Game») }` | `Source/CommonInput/Public/CommonInputModeTypes.h:11-18` |
| `FUIInputConfig(InputMode, MouseCaptureMode[, MouseLockMode], bHideCursorDuringViewportCapture)`; `bIgnoreMoveInput`, `bIgnoreLookInput` | `Source/CommonUI/Public/Input/UIActionBindingHandle.h:98-138` |
| `UCommonUIActionRouterBase::ProcessInput(FKey, EInputEvent) → ERouteUIInputResult`, `SetActiveUIInputConfig`, `ApplyUIInputConfig`, `OnActiveInputModeChanged`, `GetActiveInputMode`, `GetGameplayTagsForInputMode` | `Public/Input/CommonUIActionRouterBase.h:92-94, 112, 132, 158, 209` |
| Input routing **[по докам]**: `UCommonGameViewportClient::InputKey` → `HandleRerouteInput` → `UCommonUIActionRouterBase::ProcessInput`; «the game viewport class must be set to CommonViewportClient for CommonUI to function properly»; «Deactivated widgets are not added to the list of nodes, and therefore are never considered for Input Routing»; `IInputProcessor` (в т.ч. `FCommonAnalogCursor`) обрабатывают ввод до роутинга | https://dev.epicgames.com/documentation/en-us/unreal-engine/commonui-input-technical-guide-for-unreal-engine |
| 5.8 в CommonUI **[по докам]**: `UCommonButtonGroupBase::OnSelectedButtonLostSelection`, `UCommonUILibrary::RequestRefreshFocusIfLeafmostDescendant`, `GetLeafmostActivatableWidget`, команда `CommonUI.DumpActivatableTree` показывает `SupportsActivationFocus`, VeryVerbose-лог `LogUIActionRouter` | release notes 5.8 (сниппет context7) |
| Debug **[по докам]**: Widget Reflector, conditional breakpoints; проблема фокуса при breakpoint | https://dev.epicgames.com/documentation/unreal-engine/input-debugging-and-troubleshooting-for-commonui-in-unreal-engine |
| MVVM: плагин «UMG Viewmodel» (`ModelViewViewModel`), `IsBetaVersion: true`, `EnabledByDefault: false` | `$UE/Plugins/Runtime/ModelViewViewModel/ModelViewViewModel.uplugin` |
| Обзорные страницы Slate/UMG на dev.epicgames.com при загрузке отдали только оглавление (без содержимого) | https://dev.epicgames.com/documentation/en-us/unreal-engine/slate-user-interface-programming-framework-for-unreal-engine ; https://dev.epicgames.com/documentation/en-us/unreal-engine/umg-ui-designer-for-unreal-engine |

### 2.7. Enhanced Input (и унификация с CommonUI в 5.8)

| Факт | Источник |
|---|---|
| Плагин `EnhancedInput`: `EnabledByDefault: true`; модули `EnhancedInput` (Runtime), `InputBlueprintNodes`, `InputEditor` | `$UE/Plugins/EnhancedInput/EnhancedInput.uplugin` |
| «Enhanced Input is enabled by default»; четыре концепции: Input Actions, Input Mapping Contexts, Input Modifiers, Input Triggers; типы значений Boolean/Axis1D/Axis2D/Axis3D; trigger states Triggered/Started/Ongoing/Completed/Canceled; `showdebug enhancedinput` | https://dev.epicgames.com/documentation/en-us/unreal-engine/enhanced-input-in-unreal-engine **[по докам]** |
| `AddMappingContext(const UInputMappingContext*, int32 Priority, const FModifyContextOptions&)` | `$UE/Plugins/EnhancedInput/Source/EnhancedInput/Public/EnhancedInputSubsystemInterface.h:265` |
| `UEnhancedInputComponent::BindAction(const UInputAction*, ETriggerEvent, Object, Func…)`; вариант по `FName` функции; legacy `BindAction(FName…) = delete` | `Public/EnhancedInputComponent.h:482, 497, 613` |
| Input Mode на GameplayTag-контейнерах: `GetInputMode()`, `SetInputMode(const FGameplayTagContainer&, Options)`, `AppendTagsToInputMode`, `AddTagToInputMode`, `RemoveTagsFromInputMode`, `RemoveTagFromInputMode` (subsystem interface); `UEnhancedPlayerInput::GetCurrentInputMode/SetCurrentInputMode`, тег `InputMode_Default`; у IMC есть `InputModeQuery` | `EnhancedInputSubsystemInterface.h:278-327`; `Public/EnhancedPlayerInput.h:32, 131, 155, 260` |
| Дефолтные классы: редакторский модуль EI выставляет `DefaultInputComponentClass = UEnhancedInputComponent`, `DefaultPlayerInputClass = UEnhancedPlayerInput` | `Source/InputEditor/Private/EnhancedInputEditorModule.cpp:348, 357`; `$UE/Source/Runtime/Engine/Private/UserInterface/InputSettings.cpp:560-575` |
| CommonUI ↔ EI: `UCommonInputSettings::bEnableEnhancedInputSupport = false` («Controls if Enhanced Input Support plugin-wide. Requires restart due to caching»), `GetEnhancedInputBackAction()`, `InputData` (`UCommonUIInputData`), `ActionDomainTable`; `CommonUITypes::IsEnhancedInputSupportEnabled()` | `$UE/Plugins/Runtime/CommonUI/Source/CommonInput/Public/CommonInputSettings.h:49, 82, 112-114, 125`; `CommonUI/Public/CommonUITypes.h:311` |
| Release notes 5.8: «Unified Input System: Common UI and Enhanced Input» — «unifies Enhanced Input and Common Input/UI to simplify cross-platform input handling and debugging … more reliable event processing, better widget binding, expanded virtual key support, and new tooling like an Input Debugger for Enhanced Input UI» | https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-5-8-release-notes |
| Страница «Using CommonUI with Enhanced Input» (в разделе 5.8) по-прежнему: **Experimental**, «provides limited support for Enhanced Input actions», «As of UE 5.2, Enhanced Input support has not been tested as thoroughly…», «We do not recommend attempting to ship titles with this feature at this time»; включение: Project Settings > Game > Common Input Settings > Enable Enhanced Input Support; UI-действия как `UInputAction` с `UCommonMappingContextMetadata` (Is Generic Input Action, Nav Bar Priority); IMC добавляются/снимаются при активации Activatable Widget | https://dev.epicgames.com/documentation/en-us/unreal-engine/using-commonui-with-enhnaced-input-in-unreal-engine |
| Форум: коммит «[EI + Common UI] Input Mode updates and changes» — набор изменений 5.8 | https://forums.unrealengine.com/t/cherry-picking-5-8-input-system-changes/2729847 **[неверифицировано]** |

### 2.8. Paper2D в 5.8 vs 3D-доска

| Факт | Источник |
|---|---|
| `Paper2D.uplugin`: `EnabledByDefault: true`, `IsBetaVersion: false`, флагов `Deprecated`/`IsExperimentalVersion` нет; описание: «animated sprite assets, tilesets (experimental), 2D level editing tools»; модули Paper2D, Paper2DEditor, PaperSpriteSheetImporter, PaperTiledImporter, SmartSnapping | `$UE/Plugins/2D/Paper2D/Paper2D.uplugin` |
| Документация 5.8 «Paper 2D Overview»: «sprite-based system for creating 2D and 2D/3D hybrid games»; ассеты Sprite, Sprite Sheet, TileSet, TileMap, Flipbook; без слов experimental/legacy/maintenance | https://dev.epicgames.com/documentation/en-us/unreal-engine/paper-2d-overview-in-unreal-engine |
| В release notes 5.8 Paper2D не упоминается | WebFetch release notes (раздел не найден) |
| Официальной deprecation-заметки не найдено; «maintenance mode» — мнение сообщества | WebSearch **[неверифицировано]** |
| Альтернатива для доски: `UWidgetComponent` (World/Screen space) или обычные StaticMesh-плоскости с материалами; UMG-оверлей для HUD | `WidgetComponent.h:25-28,95` |
| Тулсеты MCP: `StaticMeshTools.import_file`, `MaterialTools` (22), `MaterialInstanceTools` (13), `SceneTools`/`ActorTools` | `$REPO/docs/unreal/00-mcp-verification.md:40-45` |

### 2.9. Импорт текстур и webp

| Факт | Источник |
|---|---|
| `EImageFormat { Invalid, PNG, JPEG, GrayscaleJPEG, BMP, ICO, EXR, ICNS, TGA, HDR, TIFF, DDS, UEJPEG }` — **WebP отсутствует** | `$UE/Source/Runtime/ImageWrapper/Public/IImageWrapper.h:26-66` |
| Реализации: Bmp, Dds, Exr, Hdr, Icns, Ico, Jpeg, Png, Tga, Tiff, UEJpeg | `$UE/Source/Runtime/ImageWrapper/Private/Formats/` (листинг) |
| ThirdParty: libPNG, libJPG, libjpeg-turbo; **libwebp нет** | `$UE/Source/ThirdParty/` (листинг) |
| Interchange (импорт в редакторе): png, bmp, exr, hdr, tif/tiff/tx, tga + отдельные переводчики JPG, PSD, DDS, UEJPEG, IES | `$UE/Plugins/Interchange/Runtime/Source/Import/Private/Texture/InterchangeImageWrapperTranslator.cpp:108-140`; листинг каталога `Texture/` |
| `grep -ri webp` по ImageWrapper/ImageCore/Interchange — совпадений нет (кроме Draco) | локальный grep |
| MCP `TextureTools.import_file(folder_path, asset_name, source_file)` валидирует файл через `unreal.TextureFactory()` («require_factory_supports») → те же форматы, webp не пройдёт | `$UE/Plugins/Experimental/Toolsets/EditorToolset/Content/Python/editor_toolset/toolsets/texture.py:15-31` |
| Проект: `public/assets` содержит **276 `.webp`** и 112 `.png`; `sync-card-assets.mjs` пишет карты в `<hero>/<card.id>.webp` и `ru/<card.id>-ru.webp` | `find $REPO/public/assets`; `$REPO/scripts/sync-card-assets.mjs:15, 138-139` |
| Сторонние решения: `neil3d/UAnimatedTexture5` (GIF/WebP как ассет, runtime из файла/URL; протестирован 5.3–5.7, Win64), `RaiaN/RuntimeImageLoader` (runtime webp; Windows/Linux/Mac/Android) | https://github.com/neil3d/UAnimatedTexture5 ; https://github.com/RaiaN/RuntimeImageLoader **[неверифицировано, по README из поиска]** |
| Официальная страница форматов текстур webp не перечисляет | https://dev.epicgames.com/documentation/unreal-engine/texture-format-support-and-settings-in-unreal-engine **[по поисковой сводке]** |

### 2.10. USaveGame и хранение токенов

| Факт | Источник |
|---|---|
| `USaveGame : UObject`; `UGameplayStatics::SaveGameToSlot`, `AsyncSaveGameToSlot`, `SaveGameToMemory`, `DoesSaveGameExist`, `LoadGameFromSlot`, `AsyncLoadGameFromSlot`, `DeleteGameInSlot` | `$UE/Source/Runtime/Engine/Classes/GameFramework/SaveGame.h:17-30, 23`; `Classes/Kismet/GameplayStatics.h:1134-1175` |
| `FGenericSaveGameSystem`: путь `<ProjectSavedDir>/SaveGames/<Name>.sav`, запись `FFileHelper::SaveArrayToFile` — **без шифрования**; в `SaveGameSystem.h` слова «encrypt» нет | `$UE/Source/Runtime/Engine/Public/SaveGameSystem.h:140, 153, 158, 171` |
| Документация: файлы `.sav` в `Saved\SaveGames`; рекомендован `AsyncSaveGameToSlot`; о шифровании — ни слова | https://dev.epicgames.com/documentation/en-us/unreal-engine/saving-and-loading-your-game-in-unreal-engine |
| `FAES` (AES-256, блок 16, ключ 32 байта) | `$UE/Source/Runtime/Core/Public/Misc/AES.h:21-28` |
| Доки `FAES`: режим ECB — «DO NOT USE this functionality for any new place where you might need encryption» | https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/Core/FAES **[по поисковой сводке]** |
| Плагин `PlatformCrypto` (`EnabledByDefault: true`, `IsBetaVersion: false`, каталог Experimental; «Exposes a unified API for cryptography … Otherwise, interfaces with OpenSSL»): `Encrypt_AES_256_GCM(Plaintext, Key, Nonce, OutAuthTag, OutResult)`, `Decrypt_AES_256_GCM(...)`, `CreateEncryptor_AES_256_GCM/CBC/ECB`, `CreateDecryptor_AES_256_GCM/...` | `$UE/Plugins/Experimental/PlatformCrypto/PlatformCrypto.uplugin`; `Source/PlatformCryptoContext/Public/EncryptionContextOpenSSL.h:189-201` |
| Обёрток DPAPI (`CryptProtectData`) и Keychain (`SecItemAdd`) в `Engine/Source/Runtime` нет; плагинов «secure storage/keychain/credential» — нет | локальный grep `$UE/Source/Runtime`, `$UE/Plugins` |
| Практика сообщества: DPAPI на Windows, Keychain на iOS/macOS, Keystore на Android через платформенный C++; ключ в бинарнике извлекаем (UnrealKey) | WebSearch **[неверифицировано]** |

### 2.11. Тестирование: Automation Spec / Functional tests / CLI

| Факт | Источник |
|---|---|
| Флаги контекста: `EditorContext=0x1, ClientContext=0x2, ServerContext=0x4, CommandletContext=0x8`; фильтры `SmokeFilter=0x01000000, EngineFilter=0x02000000, ProductFilter=0x04000000`; `EAutomationTestFlags_ApplicationContextMask` | `$UE/Source/Runtime/Core/Public/Misc/AutomationTest.h:93-99, 129-133, 144-149` |
| Spec: `Describe`, `It`, `BeforeEach`, `AfterEach`, `xLatentIt`, `It(..., EAsyncExecution, ...)`, класс `FAutomationSpecBase` | `AutomationTest.h:2757-2828, 2899, 3370-3399` |
| `TestEqual` перегрузки (int32/int64/float/double/FVector/FString/FText/FName…) | `AutomationTest.h:1985-2044` |
| Доки Automation Spec: `DEFINE_SPEC(ClassName, "Path.Name", Flags)` / `BEGIN_DEFINE_SPEC … END_DEFINE_SPEC`; реализовать `Define()`; `LatentIt/LatentBeforeEach/LatentAfterEach` с `FDoneDelegate`; `xDescribe/xIt`; рекомендация файлов `.spec.cpp`; пример `AutomationDriver.spec.cpp` | https://dev.epicgames.com/documentation/en-us/unreal-engine/automation-spec-in-unreal-engine |
| Functional tests: `AFunctionalTest` — `OnTestPrepare/OnTestStart/OnTestFinished`, `AssertTrue`, `AssertEqual_Float/Double/Bool/Int/Name/Object/Rotator/Vector/Vector2D/Transform`; редакторский плагин `FunctionalTestingEditor` | `$UE/Source/Developer/FunctionalTesting/Classes/FunctionalTest.h:380-555`; `$UE/Plugins/Tests/FunctionalTestingEditor/FunctionalTestingEditor.uplugin` |
| AutomationDriver (UI-driven тесты Slate) — модуль есть | `$UE/Source/Developer/AutomationDriver/` |
| CLI **[по докам]**: `-ExecCmds="Automation RunTest Test1+Test2;Quit"`, `... RunTest MySet.MySubSet;Quit`, `... RunTest Group:MyGroup;Quit`; `-ReportExportPath="<path>"` («JSON format with related HTML files»); `-ResumeRunTest`; в UI — Tools > Test Automation (нужен плагин Functional Testing Editor) | https://dev.epicgames.com/documentation/en-us/unreal-engine/run-automation-tests-in-unreal-engine |
| В коде контроллер парсит `ReportOutputPath=` (а также `DisplayReportOutputPath=`, `DeveloperReportOutputPath=`) — **не** `ReportExportPath` | `$UE/Source/Developer/AutomationController/Private/AutomationControllerManager.cpp:213-217` |
| Команды `Automation`: `RunAll`, `RunFilter`, `RunTests`; лог «…Automation Test Queue Empty %d tests performed.»; финал «**** TEST COMPLETE. EXIT CODE: %d ****» | `AutomationController/Private/AutomationCommandline.cpp:37-38, 122, 329-404, 503` |
| `-testexit="<phrase>"`: `FOutputDeviceTestExit` завершает процесс при появлении фразы в логе | `$UE/Source/Runtime/Launch/Private/LaunchEngineLoop.cpp:397-421` |
| Практика CI: `UnrealEditor-Cmd.exe "<proj>.uproject" -unattended -nopause -NullRHI -ExecCmds="Automation RunTests <Filter>;Quit" -testexit="Automation Test Queue Empty" -log -ReportOutputPath="<dir>"` | https://www.emidee.net/ue4/2018/11/13/UE4-Unit-Tests-in-Jenkins.html ; https://forums.unrealengine.com/t/ue5-3-does-not-find-automation-tests-through-command-line/1747873 **[неверифицировано]** |
| MCP `AutomationTestToolset`: `DiscoverTests`, `ListTests`, `RunTests`, `GetTestResults`, `GetTestStatus`, `StopTests` | `$UE/Plugins/Experimental/Toolsets/AutomationTestToolset/Source/AutomationTestToolset/Public/AutomationTestToolset.h` (grep); `$REPO/docs/unreal/00-mcp-verification.md:48` |

### 2.12. Локализация (FText, StringTable, Localization Dashboard)

| Факт | Источник |
|---|---|
| `LOCTEXT(Key, Literal)`, `NSLOCTEXT(Namespace, Key, Literal)` | `$UE/Source/Runtime/Core/Public/Internationalization/Internationalization.h:281, 286` |
| String tables в C++: `LOCTABLE_NEW(ID, NAMESPACE)`, `LOCTABLE_FROMFILE_ENGINE/GAME(ID, NAMESPACE, FILEPATH)`, `LOCTABLE_SETSTRING(ID, KEY, SRC)`, `LOCTABLE_SETMETA`, `LOCTABLE(ID, KEY)` | `Internationalization/StringTableRegistry.h:109-137` |
| Переключение культуры: `FInternationalization::SetCurrentCulture`, `SetCurrentLanguage`, `SetCurrentLanguageAndLocale`, `SetCurrentAssetGroupCulture` | `Internationalization.h:51, 66, 93, 98` |
| Командная строка `-CULTURE=<code>` | `$UE/Source/Runtime/Core/Private/Internationalization/TextLocalizationManager.cpp:254` |
| Packaging: `[/Script/UnrealEd.ProjectPackagingSettings] InternationalizationPreset=English`, `+CulturesToStage=en` (дефолт) | `$UE/Config/BaseGame.ini:111-112` |
| Редакторские модули: `LocalizationDashboard`, `Localization` | `$UE/Source/Editor/LocalizationDashboard/`, `$UE/Source/Developer/Localization/` |
| Доки Dashboard: «still classed as experimental» но «stable and is used internally for all of our projects»; цикл Gather → Export → Import → Compile; PO-пайплайн с внешним инструментом (Poedit/OneSky/XLOC) предпочтительнее встроенного Translation Editor; UAT `Localize -UEProjectDirectory=... -UEProjectName=... -LocalizationProjectNames=...` («hard-coded for a Win64 Development Editor build») | https://dev.epicgames.com/documentation/en-us/unreal-engine/localization-tools-in-unreal-engine |
| Доки String Tables: три способа (C++ макросы, CSV `Key,SourceString[,meta]`, ассет); `FText::FromStringTable`; «CSV string tables aren't staged automatically» (добавлять папку в Additional Non-Asset Directories to Package); ассет-таблицы бинарные (конфликты слияния); редиректы `[Core.StringTable] +StringTableRedirects=` | https://dev.epicgames.com/documentation/en-us/unreal-engine/using-string-tables-for-text-in-unreal-engine |
| MCP `StringTableTools` (8 инструментов), python `string_table.py` | `$REPO/docs/unreal/00-mcp-verification.md:43`; `$UE/Plugins/Experimental/Toolsets/EditorToolset/Content/Python/editor_toolset/toolsets/string_table.py` |
| Локализация карт в проекте уже есть: `scripts/localize-deadpool-ru.py`, `ru/<card>-ru.webp` | `git status`; `sync-card-assets.mjs:139` |

### 2.13. GameplayTags / DataRegistry / Game Features / Lyra-паттерны

| Факт | Источник |
|---|---|
| GameplayTags — runtime-модуль движка; `FGameplayTag::RequestGameplayTag(FName, bool ErrorIfNotFound=true)`; источники тегов: `UGameplayTagsSettings::GameplayTagList` (ini), `GameplayTagTableList` (DataTable) | `$UE/Source/Runtime/GameplayTags/Classes/GameplayTagContainer.h:57`; `GameplayTagsSettings.h:48, 145` |
| `DataRegistry.uplugin`: «generic interface for acquiring structure data from multiple sources at runtime», `IsBetaVersion: true`, `EnabledByDefault: false` | `$UE/Plugins/Runtime/DataRegistry/DataRegistry.uplugin` |
| Доки Data Registry: «efficient global storage space for USTRUCT-tagged data structures», «general read-only data» (state — в Save Game); источники `UDataRegistrySource` (DataTable/CurveTable, «web database» как пример), `UMetaDataRegistrySource`; `FDataRegistryType`/`FDataRegistryId`; `UDataRegistrySubsystem::Get`, `GetRegistryForType`, `GetCachedItem`, `AcquireItem` (async), `EvaluateCachedCurve`; указатели на элементы держать нельзя («can be unsafe») | https://dev.epicgames.com/documentation/en-us/unreal-engine/data-registries-in-unreal-engine |
| `GameFeatures.uplugin`: «Support for modular Game Feature Plugins», `IsBetaVersion: true`, `EnabledByDefault: false`; зависит от ModularGameplay, DataRegistry, AssetReferenceRestrictions, PluginUtils (Editor), DataValidation (Editor) | `$UE/Plugins/Runtime/GameFeatures/GameFeatures.uplugin` |
| `ModularGameplay.uplugin`: `IsBetaVersion: true`, `EnabledByDefault: false` | `$UE/Plugins/Runtime/ModularGameplay/ModularGameplay.uplugin` |
| Доки Game Features: плагины в `/Plugins/GameFeatures/`, ассет `GameFeatureData` с именем плагина; Actions: Add Cheats, **Add Components** («the most common way…», базовый `Actor` не поддерживается), Add Data Registry, Add Data Registry Source, Add World Partition Content; акторы регистрируются `UGameFrameworkComponentManager::AddReceiver(this)` | https://dev.epicgames.com/documentation/en-us/unreal-engine/game-features-and-modular-gameplay-in-unreal-engine |
| Lyra: Experiences (`LyraExperienceDefinition`, «a much more advanced version of a GameMode»), GF-плагины `ShooterCore`, `ShooterMaps`, `TopDownArena`, `LyraExampleContent`; `Common User plugin` как интерфейс к OSS; получение через Fab → Launcher → Fab Library | https://dev.epicgames.com/documentation/en-us/unreal-engine/lyra-sample-game-in-unreal-engine |
| В движке нет плагинов `CommonGame`, `CommonUser`, `UIExtension` (они — часть сэмпла Lyra) | `find $UE/Plugins -iname "CommonGame.uplugin" …` — пусто |
| MCP: `GameplayTagsToolset`, `DataRegistryToolset`, `GameFeaturesToolset` (8) | `$UE/Plugins/Experimental/Toolsets/` (листинг); `00-mcp-verification.md:50-51` |

### 2.14. Live Coding / UBT без Visual Studio GUI / тулчейн

| Факт | Источник |
|---|---|
| Live Coding — модуль `$UE/Source/Developer/Windows/LiveCoding` (+ `LiveCodingServer`); бинарники `LiveCodingConsole.exe`, `UnrealEditor-LiveCoding.dll` | листинг `$UE/Binaries/Win64/` |
| Настройки: `bEnabled` («Enable Live Coding», без рестарта), `Startup` (`ELiveCodingStartupMode`, рестарт), `bEnableReinstancing`, `bAutomaticallyCompileNewClasses`, `bPreloadEngineModules/EnginePluginModules/ProjectModules/ProjectPluginModules`, список модулей для preload | `LiveCoding/Private/LiveCodingSettings.h:10, 23-47` |
| Консольные команды: `LiveCoding.Compile`, `LiveCoding.CompileSync`; CVar `LiveCoding.ConsolePath`; при отсутствии `LiveCodingConsole.exe` — ошибка «Unable to start live coding session. Missing executable…» | `LiveCoding/Private/LiveCodingModule.cpp:423-450, 340-342, 1065-1077` |
| Доки: интеграция Live++; «rebuild your application's C++ code and patch its binaries while the engine is running»; «enabled by default for all new Unreal Engine installations»; Ctrl+Alt+F11; Object Reinstancing для UCLASS/USTRUCT/UFUNCTION/UENUM/UDELEGATE; отключать реинстансинг «not recommended»; при отключённом реинстансинге новые функции/переменные «will usually result in crashes»; риск краша при shutdown из-за одного деструктора; «not available when launching on consoles and mobile devices»; Hot Reload «still available as an alternative» | https://dev.epicgames.com/documentation/en-us/unreal-engine/using-live-coding-to-recompile-unreal-engine-applications-at-runtime |
| Доки Unreal MCP: «Adding a new UFUNCTION requires a full editor restart (Live Coding only updates existing bodies)» — для тулсетов | https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-mcp-in-unreal-editor |
| Скрипты сборки: `$UE/Build/BatchFiles/Build.bat`, `Rebuild.bat`, `Clean.bat`, `RunUAT.bat`, `GetMSBuildPath.bat`, `GetDotnetPath.bat`, `RunUBT.sh`; исходники UBT в `$UE/Source/Programs/UnrealBuildTool` | листинг |
| По логам сообщества Live Coding вызывает `Build.bat -Target="<Proj>Editor Win64 Development -Project=..."` | https://community.gamedev.tv/t/unreal-engine-5-4-error-when-live-compiling/246163 **[неверифицировано; в `LiveCodingModule.cpp` найдены только вызовы `LiveCodingConsole.exe`, компиляцию делает консоль]** |
| Требования MSVC (UBT читает из JSON): `MinimumVisualCppVersion: 14.38.33130`; `PreferredVisualCppVersions: 14.50.35717-14.50.99999 (VS2026 18.0), 14.44.35207-14.44.99999 (VS2022 17.14)`; `BannedVisualCppVersions: 14.50.0-14.50.35722, 14.44.0-14.44.35210, 14.40.0-14.43.99999, 14.39.0-14.39.99999`; `MinimumVisualStudio2022Version: 17.8`, `MinimumVisualStudio2026Version: 18.0`; Windows SDK `MainVersion 10.0.22621.0`, `MinVersion 10.0.19041.0`; Clang min 18.1.8, preferred 20.1.8; `VisualStudioSuggestedComponents` включает `Microsoft.VisualStudio.Component.VC.Tools.x86.x64`, `Windows11SDK.22621`, `VC.Llvm.Clang`, `Component.Unreal.Ide` | `$UE/Config/Windows/Windows_SDK.json` |
| Доки «Setting Up Visual Studio» (5.8): VS2022 «17.14 or later», VS2026 «18.0 or later»; MSVC min 14.38 / рекоменд. 14.50; Windows SDK 10.0.22621.0 / 10.0.26100+; LLVM 18.1.8 / 20.1.8; «.NET 10.0 for VS 2026»; workloads: .NET desktop, Desktop development with C++, Game development with C++ (+ Unreal Engine installer, Windows 10/11 SDK) | https://dev.epicgames.com/documentation/en-us/unreal-engine/setting-up-visual-studio-development-environment-for-cplusplus-projects-in-unreal-engine |
| Release notes 5.8 (Platform SDK): «Visual Studio 2022 v17.14 or newer and Windows SDK 10.0.22621.0 or newer are required … .NET 8.0 is supported»; build farm — VS2022 17.14, Win SDK 10.0.22621.0, Xcode 15.4; Linux: Ubuntu 22.04 / Rocky 8 / RHEL 8+, clang 20.1.8, кросс-тулчейн v26 clang-20.1.8 | release notes (сниппеты context7) |
| Hardware & Software Specs 5.8: «Use Visual Studio 2026 for general development. Use Visual Studio 2022 for Nintendo development…»; «Unreal Engine also supports VS Code and Rider» | https://dev.epicgames.com/documentation/en-us/unreal-engine/hardware-and-software-specifications-for-unreal-engine |
| Build Tools без IDE: доки VS Code: «Click the Download button next to Build Tools for Visual Studio 2022 and install it»; `-vscode` при генерации проектных файлов | https://dev.epicgames.com/documentation/unreal-engine/setting-up-visual-studio-code-for-unreal-engine **[по поисковой сводке]**; JetBrains: «downloading the Microsoft Build Tools launcher (you will not get Visual Studio, but the required components only)» https://rider-support.jetbrains.com/hc/en-us/community/posts/5290088619026-Rider-for-Unreal-Engine-without-installing-Visual-Studio **[неверифицировано]** |
| Локальный документ: «C++ пишется в файлы напрямую, сборка через UBT/Build.bat/Live Coding вне MCP» | `$REPO/docs/unreal/00-mcp-verification.md:58` |

### 2.15. Целевые платформы и packaging

| Факт | Источник |
|---|---|
| Установленная сборка: `$UE/Platforms/{Android, IOS, VisionOS, Windows}`; `$UE/Binaries/{DotNET, Mac, ThirdParty, Win64}`; `$UE/Config/{Android, IOS, Linux, Mac, Windows}`; `$UE/Intermediate/Build/Win64` (только); `Binaries/Linux` **нет** | листинги |
| SDK-дескрипторы: `Android_SDK.json`, `Apple_SDK.json`, `IOS_SDK.json`, `Linux_SDK.json`, `Windows_SDK.json` | `$UE/Config/*/` |
| Packaging из CLI: `RunUAT.bat BuildCookRun -project=MyProject.uproject -clientconfig=Development` (+ `-platform=… -cook -stage -pak -archive`) | https://dev.epicgames.com/documentation/unreal-engine/build-operations-cooking-packaging-deploying-and-running-projects-in-unreal-engine (сниппет context7) |
| 5.8: «Zenserver as Cooked Output Store is now enabled by default»; pak/iostore остаются; `AllowRemoteNetworkService` → `RemoteNetworkService` (None/Unsecured/GeneratedStaticKey) | release notes 5.8 |
| 5.8 Windows: аудио-бэкенд по умолчанию WASAPI (`AudioMixerWasapi`), fallback `[Audio] AudioMixerModuleName=AudioMixerXAudio2` | release notes 5.8 |
| 5.8 iOS: «full keyboard and mouse support for iOS and iPadOS»; App Extensions `.uappex`; экспериментальный SM6 (A15+) | release notes 5.8 |
| Live Coding не работает на консолях/мобильных | доки Live Coding (см. §2.14) |
| WebSockets поддерживаются на Windows/Android/Mac/Unix/iOS (LWS) | `WebSockets.Build.cs:7-17` |

### 2.16. Unreal MCP в агентном dev-loop

**Плагин и сервер:**

| Факт | Источник |
|---|---|
| `ModelContextProtocol.uplugin`: «Anthropic MCP (Model Context Protocol) server implementation for Unreal Engine», `IsExperimentalVersion: true`, `EnabledByDefault: false`, `NoRedist: true`; модули `ModelContextProtocol`, `ModelContextProtocolEngine` (Runtime), `ModelContextProtocolEditor`, тестовые; зависит от `ToolsetRegistry`, `EngineAssetDefinitions` | `$UE/Plugins/Experimental/ModelContextProtocol/ModelContextProtocol.uplugin` |
| Настройки: `ServerUrlPath` (дефолт из `UE::ModelContextProtocol::DefaultServerUrlPath`), `ServerPortNumber = 8000`, `bAutoStartServer = false`, `bEnableToolSearch = true` | `Source/ModelContextProtocolEngine/Public/ModelContextProtocolSettings.h:24-46` |
| В нашем хосте: порт 8123, путь `/mcp`, автостарт, tool search; Claude Code `mcpServers.unreal-mcp = { type: http, url: http://127.0.0.1:8123/mcp }`; protocolVersion `2025-11-25` | `$REPO/docs/unreal/00-mcp-verification.md:11-14` |
| Старт редактора ~40 с до открытия порта; при `ConnectionRefused` — `/mcp` reconnect | `00-mcp-verification.md:22` |
| В этой сессии `unreal-mcp` не подключился (`ConnectionRefused`) — редактор не был запущен | системное сообщение сессии |
| Доки: «Supports HTTP and Server-Sent Events only. The stdio and WebSocket transports are not supported»; «Tool calls run serially on the game thread; clients should not issue overlapping Tool calls»; «Loopback only by default … There is no authentication layer; the plugin is not safe to expose beyond the local machine»; консоль `ModelContextProtocol.StartServer [port]`, `.StopServer`, `.RefreshTools`, `.GenerateClientConfig <ClaudeCode|Cursor|VSCode|Gemini|Codex|All>`; флаги `-ModelContextProtocolStartServer`, `-ModelContextProtocolPort=N`; CVars `PaginationPageSize`, `ProgressIntervalSeconds`, `EnableAnalytics`; Tool Search → мета-инструменты `list_toolsets`, `describe_toolset`, `call_tool`; «Toolsets and tools are not implemented by Unreal MCP itself; instead, the AllToolsets plugin must be used»; Resources/Prompts не публикуются; cooked-сборки могут поднять сервер через `IModelContextProtocolModule::StartServer()` с ручной регистрацией инструментов | https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-mcp-in-unreal-editor |
| Авторинг тулсетов: Python (`Content/Python`, `@unreal.uclass()`, `@toolset_registry.tool_call`, докстринги → схема) или C++ (`UToolsetDefinition`, `UFUNCTION(meta=(AICallable))`); `RefreshTools` после правок; новая `UFUNCTION` требует рестарта редактора | там же |

**Тулсеты (в движке `$UE/Plugins/Experimental/Toolsets/`):** AIModuleToolset, AllToolsets, AnimationAssistantToolset, AutomationTestToolset, ChaosClothAssetToolset, ConfigSettingsToolset, ConversationToolset, DataflowAgent, DataRegistryToolset, EditorToolset, GameFeaturesToolset, GameplayTagsToolset, GASToolsets, **LiveCodingToolset**, MCPClientToolset, MetaHumanGenerator, MVVMToolset, NiagaraToolsets, PCGToolset, PhysicsToolsets, PluginToolset, SemanticSearchToolset, SequencerAnimMixerToolset, SlateInspectorToolset, StateTreeToolset, UMGToolSet, WorldConditionsToolset (листинг каталога).

| Тулсет / инструмент | Детали | Источник |
|---|---|---|
| `EditorToolset` (Python): actor, asset, blueprint, blueprint_dsl, blueprint_layout, blueprint_node, curve_table, data_asset, data_table, material, material_instance, object, primitive, programmatic, scene, skeletal_mesh, static_mesh, string_table, texture | | `$UE/Plugins/Experimental/Toolsets/EditorToolset/Content/Python/editor_toolset/toolsets/` |
| Blueprint DSL: «S-expression IDL for Blueprint graphs: transpile DSL text → nodes, decompile nodes → DSL text»; формы `(event Name (Params) stmt…)`, `(fn Name (Params) stmt…)`, `bind`, `if/elif/else`, `for/range`, `while`, `switch`, `break`, `return`, multi-exec континуации `(:ExecOut stmt…)`, авто-переменные `_return_value`, операторы `+ - * / % == != < <= > >= and or xor not neg select`, аксессоры `.x .y .z .pitch .yaw .roll .location .rotation .scale`, вызовы `(NodeType|Id args… :PinName val)`, переменные BP `(Variables|Default|GetMyVar)`; строки/пути/энумы обязательно в кавычках | | `editor_toolset/toolsets/blueprint_dsl.py:3, 23-140` |
| `BlueprintTools` (53): `read_graph_dsl`/`write_graph_dsl` (компиляция), variables, components, dispatchers, `set_parent`, pins | | `00-mcp-verification.md:38` |
| `UMGToolSet` (C++): `AddWidget`, `SetNamedSlotContent`, `GetWidgets`, `GetNamedSlots`, `ListWidgetBlueprints`, `ListWidgetClasses`, `GetWidgetClassInfo`, `MoveWidget`, `RemoveWidget`, `RenameWidget`, `ToggleWidgetAsVariable`, `BindToEventProperty`, `WrapWidgets`, `GetWidgetDescription`, `GetWidgetTreeDepth`, `AddUIComponent`, `RemoveUIComponent`, `MoveUIComponent`, `ReplaceWidgetWithTemplate`, `ReplaceWidgetWithNamedSlot`, `ReplaceWidgetWithChild`, `CompileWidgetBlueprint` (+ `CreateWidgetBlueprint` по локальному документу) | | grep `UMGToolSet/Source` (`AICallable`); `00-mcp-verification.md:41` |
| `SlateInspectorToolset` (C++): `Snapshot`, `Observe`, `Unobserve`, `ListObservers`, `Screenshot` (→ `FToolsetImage`), `Click`, `Hover`, `Type`, `PressKey`, `SelectOption`, `Drag`, `Windows`, `WaitFor`, `FillForm` | Playwright-подобная автоматизация UI редактора/PIE | grep `SlateInspectorToolset/Source`; `00-mcp-verification.md:42` |
| `AutomationTestToolset`: `DiscoverTests`, `ListTests`, `RunTests`, `GetTestResults`, `GetTestStatus`, `StopTests` | | см. §2.11 |
| `DataTableTools` (10), `DataAssetTools`, `CurveTableTools` (9), `StringTableTools` (8), `DataRegistryTools` (8): `create`, `import_file`, `add_rows/set_rows`, `get_schema`, `search_row_structs` | | `00-mcp-verification.md:43` |
| `TextureTools.import_file` → через `TextureFactory` (webp нет), `get_size` | | `texture.py:15-40` |
| `EditorToolset.EditorAppToolset` (22): `StartPIE/StopPIE/IsPIERunning`, `OpenEditorForAsset`, камера, выбор; `LogsToolset.GetLogEntries(category, pattern, maxEntries)` | | `00-mcp-verification.md:46-47` |
| `LiveCodingToolset` — «Live Coding compile toolset» (заголовки `LiveCodingToolset.h`, `LiveCodingToolsetSubsystem.h`); имена инструментов grep-ом не извлечены | означает возможность запускать Live Coding compile из агента | `$UE/Plugins/Experimental/Toolsets/LiveCodingToolset/LiveCodingToolset.uplugin:6`; листинг `Source/LiveCodingToolset/Public/` |
| `PluginToolset` (18): `CreatePlugin`, `SetPluginEnabled`; `ProgrammaticToolset`: `execute_tool_script`, `get_execution_environment`; `ConfigSettings`, `SemanticSearch`, `AgentSkills`, `MCPClientToolset` | | `00-mcp-verification.md:49-54`; листинг тулсетов |
| Ограничения по локальному документу: нет инструмента «создать C++ класс / собрать проект» (**противоречит наличию `LiveCodingToolset`** — проверить `describe_toolset`); сервер привязан к одному открытому проекту — для игры нужен свой `.uproject` с `ModelContextProtocol` + `AllToolsets` и тем же ini-блоком | | `00-mcp-verification.md:58-60` |

---

## 3. Следствия для UE-клиента

### 3.1. Сетевой слой (обязательные требования)
1. **Свой GraphQL-слой, без плагинов.** Модули в `.Build.cs`: `HTTP`, `WebSockets`, `Json`, `JsonUtilities` (+ `SSL` подтягивается транзитивно). Не полагаться на несуществующие `UEGraphQL`/Mountea (§2.5).
2. **HTTP (query/mutation):** `FHttpModule::Get().CreateRequest()`, `SetVerb("POST")`, `SetURL(<http://host:3000/graphql>)`, `SetHeader("Content-Type","application/json")`, `SetHeader("Authorization","Bearer <accessToken>")`, тело `{"query":…, "variables":…, "operationName":…}`; в `OnProcessRequestComplete` проверять `bProcessedSuccessfully`, `Response->GetResponseCode()`, затем разбирать `data`/`errors`. Делегаты по умолчанию на game thread — UI можно трогать напрямую. Для повторов — `FHttpRetrySystem::FManager` (коды 5xx/сеть) либо своя логика, т.к. тотального таймаута по умолчанию нет (`HttpTotalTimeout=0`) — задавать `SetTimeout`.
3. **WS (subscriptions):** `FWebSocketsModule::Get().CreateWebSocket(TEXT("ws://host:3000/graphql"), TEXT("graphql-transport-ws"))` — сабпротокол обязателен, иначе `graphql-ws` v6 на бэкенде отвергнет соединение (§2.3, спецификация). Заголовок `Authorization` в апгрейд-хендшейк класть **не нужно**: бэкенд читает токен из `connection_init.payload.authorization` (`graphql.module.ts:23-33`), как делает веб-клиент. Вызывать `Get()`/`CreateWebSocket` только на game thread (`check(IsInGameThread())`).
4. **State machine клиента graphql-transport-ws** (реализовать самим): `Connect()` → `OnConnected` → отправить `{"type":"connection_init","payload":{"authorization":"Bearer …"}}` → ждать `connection_ack` (таймаут) → `subscribe {id, payload:{query, variables}}` → маршрутизировать `next/error/complete` по `id`; отвечать `pong` на `ping`; закрывать `complete {id}` при отписке; обрабатывать коды 4400/4401/4403/4408/4409/4429 (4403 → рефреш токена и переподключение). Биндить `OnMessage` **до** `Connect()` (иначе события не придут — `LwsWebSocket.h:327-341`).
5. **Реконнект:** автореконнекта в `IWebSocket` нет; после `OnClosed`/`OnConnectionError` объект возвращается в `None` и допускает повторный `Connect()` (`LwsWebSocket.cpp:625-648`). Реализовать экспоненциальный backoff (веб-клиент: 5 попыток), пере-подписку всех активных операций после `connection_ack`, и «resync» состояния игры запросом по HTTP (так же, как `useGameSync` в вебе — не проверялось, открытый вопрос).
6. **Keep-alive:** WS-ping на уровне libwebsockets выключен (`PingPongInterval=0`); использовать протокольные `ping`/`pong` graphql-transport-ws (таймер на клиенте) и/или включить `[WebSockets.LibWebSockets] PingPongInterval=<сек>` в `DefaultEngine.ini`.
7. **Размер сообщений:** дефолт 1 MB на текстовое сообщение; при больших снапшотах игры поднять `[WebSockets] TextMessageMemoryLimit` или `SetTextMessageMemoryLimit`.
8. **TLS в проде:** `wss://`; для self-signed dev-серверов — `wss+insecure://` или `[LwsWebSocket] bDisableCertValidation=true` (только dev). Домены по умолчанию не фильтруются (секции `[Online.HttpManager]` нет) — при желании включить allowlist.

### 3.2. Модель данных / JSON
1. Описывать ответы API как `USTRUCT` с `UPROPERTY` и десериализовать `FJsonObjectConverter::JsonObjectToUStruct` (с `bStrictMode=false`, `OutFailReason` для логов). Имена полей GraphQL (camelCase) совпадают со `StandardizeCase`-схемой конвертера (первая буква строчная) — при именовании UPROPERTY в PascalCase маппинг работает на экспорт; на импорт проверить регистр (открытый вопрос §4).
2. `int64`: наш API не использует 64-битные целые (GraphQL `Int` 32-бит; кастомные скаляры `DateTime`, `JSON`), поэтому риск потери точности минимален. Если появятся `BigInt`/timestamp-ы в мс — передавать строкой (конвертер парсит `Atoi64`) или парсить DOM с `EFlags::StoreNumbersAsStrings`.
3. Скаляр `JSON` (произвольная структура, например `abilityConfig`) — принимать в `FJsonObjectWrapper`. `DateTime` (ISO 8601) — в `FDateTime` (парсится `ParseIso8601`).
4. `TMap` в USTRUCT допустим только с ключами, парсящимися из строки (`FString`, `FName`, enum, число). Вложенные `TMap<FString, TArray<FStruct>>` — работают через рекурсию (`.cpp:716-760`), но проверить тестом.
5. Для больших/изменчивых payload (состояние игры) рассмотреть ручной разбор DOM (`FJsonObject`) или `CustomImportCallback` для отдельных полей.

### 3.3. UI
1. **Базовый стек: UMG + CommonUI** (стек экранов `UCommonActivatableWidgetStack`, модалки `bIsModal`, back-action, `FUIInputConfig` Menu/Game/All). Требуется `GameViewportClientClass = CommonGameViewportClient` и настройка `CommonInputSettings.InputData`.
2. **Enhanced Input** — использовать для игровых действий (выбор клетки/карты, зум, отмена). Интеграцию CommonUI↔EI (`bEnableEnhancedInputSupport`) включать осознанно: в 5.8 она объявлена унифицированной, но страница доков всё ещё «Experimental / not recommended to ship» (текст от 5.2). Для 2D-карточной игры с мышью/тачем можно обойтись CommonUI без EI-интеграции (кнопки UMG) и EI только для сцены.
3. **Доска:** 3D-сцена (StaticMesh-плоскости/декали + материалы, камера сверху) + UMG-HUD; либо `UWidgetComponent` для карточек в мире. Paper2D допустим, но не даёт преимуществ и не упомянут в 5.8 (§2.8).
4. **MVVM** («UMG Viewmodel», Beta) — опционально для реактивного связывания состояния игры с виджетами; безопаснее — собственные делегаты/`FieldNotify`. Не критично.
5. Для отладки фокуса/ввода: `CommonUI.DumpActivatableTree`, `LogUIActionRouter VeryVerbose`, Widget Reflector; `showdebug enhancedinput`.

### 3.4. Ассеты
1. **Обязателен конвейер webp → png** (или tga) перед импортом: 276 `.webp` в `public/assets`, `sync-card-assets.mjs` генерирует `.webp`. Варианты: (а) расширить `sync-card-assets.mjs`/новый скрипт (sharp/ImageMagick) с выводом PNG в папку для UE-импорта; (б) плагин `RuntimeImageLoader`/`UAnimatedTexture5` для рантайм-загрузки webp (сторонний код, поддержка версий не гарантирована).
2. Импорт через MCP `TextureTools.import_file` работает только для форматов `TextureFactory` (png/jpg/tga/bmp/exr/hdr/tif/dds/psd).
3. Метаданные карт (DataTable/DataAsset/DataRegistry) можно заливать `DataTableTools.import_file`/`add_rows` из JSON/CSV, сгенерированного из бэкенд-контента (`backend/src/content/data/heroes/*.ts`) — но источник истины остаётся API (открытый вопрос: оффлайн-кэш vs запросы).

### 3.5. Токены и сохранения
1. Не хранить `accessToken`/`refreshToken` в `USaveGame` в открытом виде.
2. Минимально: шифровать через `PlatformCrypto` `Encrypt_AES_256_GCM` (случайный nonce на запись, ключ — на устройстве); лучше: платформенные хранилища (DPAPI `CryptProtectData` на Windows, Keychain на macOS/iOS, Keystore на Android) в своём модуле с `#if PLATFORM_*` — в движке обёрток нет. Не использовать `FAES` (ECB).
3. Хранить только refresh-token (access — в памяти), реализовать refresh по 401/4403 (аналог `error-link.ts` в вебе).

### 3.6. Тестирование
1. Логика GraphQL-слоя (парсинг сообщений, state machine, десериализация) — Automation Spec (`DEFINE_SPEC`, флаги `ProductFilter | ApplicationContextMask`), файлы `*.spec.cpp`; сетевые сценарии — `LatentIt` с `FDoneDelegate` против локального бэкенда (порт 3000).
2. UI-сценарии — Functional Tests (`AFunctionalTest`) в тестовой карте и/или `SlateInspectorToolset` (`Click/Type/FillForm/WaitFor/Screenshot`) из агента.
3. CI: `UnrealEditor-Cmd.exe <proj>.uproject -unattended -nopause -NullRHI -ExecCmds="Automation RunTests <Filter>;Quit" -testexit="Automation Test Queue Empty" -log -ReportOutputPath=<dir>` (имя параметра — как в коде, `ReportOutputPath`).

### 3.7. Локализация
1. Все строки UI — `FText` (`LOCTEXT`/`NSLOCTEXT`) или String Table (ассет либо CSV `Key,SourceString`); культуры в `+CulturesToStage=en`, `ru`; переключение `SetCurrentLanguageAndLocale("ru")`; для тестов `-CULTURE=ru`.
2. Тексты карт/героев приходят с бэкенда (уже локализованы там, есть `ru`-изображения) — в клиенте локализовать только «хром» интерфейса.

### 3.8. Архитектура проекта / Lyra-паттерны
1. **GameplayTags** — использовать для идентификаторов состояний UI/ввода (`UI.Layer.*`, `Input.Mode.*`), это runtime-модуль без зависимостей.
2. **Game Features / ModularGameplay / DataRegistry** — все Beta; для клиента одной игры избыточны. Допустимо взять из Lyra идею слоёв UI (стек `Game/GameMenu/Menu/Modal`) без самих плагинов `CommonGame`/`CommonUser` (их нет в движке).
3. Структура: C++ для сети/данных/state sync (`UGameInstanceSubsystem` для GraphQL-клиента), Blueprint/UMG для визуала; Blueprint-графы генерировать через MCP `write_graph_dsl` (S-expression DSL).

### 3.9. Сборка, dev-loop, платформы
1. Требуется MSVC ≥ 14.38 (рекомендовано 14.44 VS2022 17.14 или 14.50 VS2026), Windows SDK ≥ 10.0.22621.0, .NET; IDE не нужен — достаточно Build Tools + `Build.bat <Proj>Editor Win64 Development -Project=<path>.uproject -WaitMutex`; в редакторе — Live Coding (Ctrl+Alt+F11 / `LiveCoding.Compile`), новые `UCLASS`/`UFUNCTION` — через реинстансинг, для тулсетов MCP — рестарт.
2. Свой `.uproject` для игры с включёнными `ModelContextProtocol`, `AllToolsets` и ini-блоком (`ServerPortNumber`, `ServerUrlPath`, `bAutoStartServer`, `bEnableToolSearch`); один редактор = один MCP-сервер (§2.16).
3. Целевые платформы: Win64 (основная; всё есть локально), Mac/iOS/Android (папки платформ есть; нужны SDK/Xcode), Linux — только кросс-компиляция (тулчейн v26 clang-20.1.8, `Binaries/Linux` отсутствует). Packaging — `RunUAT.bat BuildCookRun …`; учесть Zen-store по умолчанию.

---

## 4. Открытые вопросы / несоответствия

1. **`LiveCodingToolset` vs локальный документ.** `00-mcp-verification.md:58` утверждает, что нет инструмента «собрать проект», но в движке есть `LiveCodingToolset` («Live Coding compile toolset»). Нужно вызвать `describe_toolset` и проверить, запускает ли он `LiveCoding.Compile` — это меняет агентный dev-loop (компиляция из MCP).
2. **`-ReportExportPath` vs `ReportOutputPath`.** Официальная страница «Run Automation Tests» документирует `-ReportExportPath`, а `AutomationControllerManager.cpp:213` парсит `ReportOutputPath=`. Использовать `ReportOutputPath` (по коду); возможно, `ReportExportPath` обрабатывается где-то ещё — не найдено.
3. **CommonUI + Enhanced Input в 5.8.** Release notes объявляют унификацию, но страница интеграции по-прежнему «Experimental / not recommended to ship» (текст «As of UE 5.2»). Реальная зрелость в 5.8 не подтверждена — требуется прототип.
4. **Поведение LWS при отсутствии эха сабпротокола сервером** (если сервер не вернёт `Sec-WebSocket-Protocol`) — в исходниках UE не обрабатывается явно, поведение определяется libwebsockets; не проверено. Для нашего бэкенда (graphql-ws v6) эхо будет.
5. **Регистр имён полей при импорте JSON → USTRUCT.** Экспорт использует `StandardizeCase` (`.cpp:33-42, 450-452`); точная логика сопоставления ключей при импорте (`.cpp:1305-1360`) в этой сессии не прочитана построчно — проверить тестом с PascalCase-UPROPERTY и camelCase-JSON.
6. **Формат секции allowlist.** `URLRequestFilter.h:39-46` показывает ключи `!AllowedDomains=ClearArray`, `+AllowedDomains=…` под корнем `Online.HttpManager`; точный вид секций (по схемам) не проверен. По умолчанию фильтр пуст → всё разрешено.
7. **Цитата «last planned major UE5 release».** Страница анонса Epic вернула 403; цитата взята из поисковой сводки/агрегаторов. В форумной версии анонса этой фразы нет (там только «integrated MCP plugin for LLMs»).
8. **Build Tools без IDE** — подтверждено только доками VS Code (через поисковую сводку) и JetBrains; прямой текст страницы Epic не загружался.
9. **Дефолт `bEnabled` Live Coding** в `LiveCodingSettings.cpp` grep-ом не найден (доки: «enabled by default for all new … installations»).
10. **Схема GraphQL** (`schema.gql`) в репозитории отсутствует (генерируется `autoSchemaFile: true` в рантайме) — нужно снять интроспекцию с работающего бэкенда, чтобы сгенерировать USTRUCT-ы и убедиться в отсутствии 64-битных чисел.
11. **`gh search repos` вернул пустые массивы** для всех GraphQL-запросов — возможна особенность CLI/квоты; вывод «не найдено» стоит перепроверить веб-поиском по GitHub при необходимости.
12. **UEGraphQL / Mountea** — в задании указаны как кандидаты; `badumbat/UEGraphQL` не существует на GitHub (проверено `gh`), у Mountea нет GraphQL-репозитория. Источник этих названий неизвестен.
13. **Локальный документ говорит «импорт png/webp?»** (`00-mcp-verification.md:44`) — по исходникам webp не поддерживается (§2.9).
14. **Реконнект-политика веб-клиента** (`lazy: true`, `retryAttempts: 5`) и повторная синхронизация состояния (`useGameSync.ts`) в этой сессии не анализировались — при проектировании UE-клиента нужно повторить ту же семантику.
15. Страницы обзора **Slate** и **UMG** на dev.epicgames.com отдали пустое содержимое — детали (declarative syntax, рекомендации Slate vs UMG) не зафиксированы; для клиента это не блокер (UMG/CommonUI достаточно).

---

## 5. Источники

### Локальные файлы (репозиторий)
- `$REPO/docs/unreal/00-mcp-verification.md` (полностью)
- `$REPO/backend/src/graphql/graphql.module.ts:1-60`; `$REPO/backend/package.json:43-70`; `$REPO/backend/src/auth/strategies/jwt.strategy.ts:16`
- `$REPO/src/lib/apolloClient.ts:1-70`; `$REPO/src/env.ts`
- `$REPO/scripts/sync-card-assets.mjs:15, 138-139`; `find $REPO/public/assets` (276 webp / 112 png)

### Исходники UE 5.8.2 (`$UE`)
- `Build/Build.version`
- `Source/Runtime/Online/WebSockets/Public/IWebSocket.h`, `WebSocketsModule.h`; `Private/WebSocketsModule.cpp`; `WebSockets.Build.cs`; `Private/Lws/LwsWebSocket.h`, `LwsWebSocket.cpp`, `LwsWebSocketsManager.cpp`; `Private/WinHttp/WinHttpWebSocket.h`
- `Source/Runtime/Online/HTTP/Public/HttpModule.h`, `HttpRetrySystem.h`, `HttpManager.h`, `Interfaces/IHttpRequest.h`, `IHttpResponse.h`, `IHttpBase.h`; `HTTP.Build.cs`; `Private/Windows/WindowsPlatformHttp.cpp`; `Private/GenericPlatform/HttpRequestCommon.h`; `Private/HttpModule.cpp`
- `Source/Runtime/Core/Public/Misc/URLRequestFilter.h`, `AES.h`, `AutomationTest.h`; `Core/Public/Internationalization/Internationalization.h`, `StringTableRegistry.h`; `Core/Private/Internationalization/TextLocalizationManager.cpp`
- `Source/Runtime/Json/Public/Dom/JsonValue.h`, `Serialization/JsonSerializer.h`; `Source/Runtime/JsonUtilities/Public/JsonObjectConverter.h`, `JsonObjectWrapper.h`; `Private/JsonObjectConverter.cpp`
- `Source/Runtime/ImageWrapper/Public/IImageWrapper.h`; `Private/Formats/`; `Source/ThirdParty/`
- `Source/Runtime/Engine/Classes/GameFramework/SaveGame.h`, `Classes/Kismet/GameplayStatics.h`, `Public/SaveGameSystem.h`, `Private/UserInterface/InputSettings.cpp`
- `Source/Runtime/UMG/Public/Components/WidgetComponent.h`
- `Source/Runtime/GameplayTags/Classes/GameplayTagContainer.h`, `GameplayTagsSettings.h`
- `Source/Developer/FunctionalTesting/Classes/FunctionalTest.h`; `Source/Developer/AutomationController/Private/AutomationCommandline.cpp`, `AutomationControllerManager.cpp`; `Source/Runtime/Launch/Private/LaunchEngineLoop.cpp`
- `Source/Developer/Windows/LiveCoding/Private/LiveCodingSettings.h`, `LiveCodingModule.cpp`
- `Source/Programs/UnrealBuildTool/Platform/Windows/MicrosoftPlatformSDK.Versions.cs`; `Config/Windows/Windows_SDK.json`; `Config/BaseEngine.ini`; `Config/BaseGame.ini`
- Плагины: `Plugins/2D/Paper2D/Paper2D.uplugin`; `Plugins/Runtime/CommonUI/CommonUI.uplugin` + `Source/CommonUI/Public/{CommonActivatableWidget.h, CommonUITypes.h, Widgets/CommonActivatableWidgetContainer.h, Input/CommonUIActionRouterBase.h, Input/UIActionBindingHandle.h}`, `Source/CommonInput/Public/{CommonInputSettings.h, CommonInputModeTypes.h}`; `Plugins/EnhancedInput/EnhancedInput.uplugin` + `Source/EnhancedInput/Public/{EnhancedInputSubsystemInterface.h, EnhancedInputComponent.h, EnhancedPlayerInput.h}`, `Source/InputEditor/Private/EnhancedInputEditorModule.cpp`; `Plugins/Runtime/GameFeatures/GameFeatures.uplugin`; `Plugins/Runtime/DataRegistry/DataRegistry.uplugin`; `Plugins/Runtime/ModularGameplay/ModularGameplay.uplugin`; `Plugins/Runtime/ModelViewViewModel/ModelViewViewModel.uplugin`; `Plugins/Experimental/PlatformCrypto/PlatformCrypto.uplugin` + `Source/PlatformCryptoContext/Public/EncryptionContextOpenSSL.h`; `Plugins/Experimental/ModelContextProtocol/ModelContextProtocol.uplugin` + `Source/ModelContextProtocolEngine/Public/ModelContextProtocolSettings.h`; `Plugins/Experimental/Toolsets/*` (uplugin-ы, `EditorToolset/Content/Python/editor_toolset/toolsets/{blueprint_dsl.py, texture.py}`, заголовки `UMGToolSet`, `SlateInspectorToolset`, `AutomationTestToolset`, `LiveCodingToolset`); `Plugins/Interchange/Runtime/Source/Import/Private/Texture/InterchangeImageWrapperTranslator.cpp`; `Plugins/Tests/FunctionalTestingEditor/FunctionalTestingEditor.uplugin`
- `C:\Users\ren\Documents\Unreal Projects\MCPProject\MCPProject.uproject`

### Официальная документация Epic (dev.epicgames.com)
- https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-5-8-release-notes
- https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-mcp-in-unreal-editor
- https://dev.epicgames.com/documentation/en-us/unreal-engine/common-ui-plugin-for-advanced-user-interfaces-in-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/commonui-input-technical-guide-for-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/using-commonui-with-enhnaced-input-in-unreal-engine
- https://dev.epicgames.com/documentation/unreal-engine/input-debugging-and-troubleshooting-for-commonui-in-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/enhanced-input-in-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/automation-spec-in-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/run-automation-tests-in-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/localization-tools-in-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/using-string-tables-for-text-in-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/game-features-and-modular-gameplay-in-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/data-registries-in-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/lyra-sample-game-in-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/using-live-coding-to-recompile-unreal-engine-applications-at-runtime
- https://dev.epicgames.com/documentation/en-us/unreal-engine/hardware-and-software-specifications-for-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/setting-up-visual-studio-development-environment-for-cplusplus-projects-in-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/paper-2d-overview-in-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/saving-and-loading-your-game-in-unreal-engine
- https://dev.epicgames.com/documentation/unreal-engine/build-operations-cooking-packaging-deploying-and-running-projects-in-unreal-engine (через context7)
- https://dev.epicgames.com/documentation/unreal-engine/setting-up-visual-studio-code-for-unreal-engine (через поисковую сводку)
- https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/Core/FAES (через поисковую сводку)
- https://dev.epicgames.com/documentation/unreal-engine/texture-format-support-and-settings-in-unreal-engine (через поисковую сводку)

### Прочие
- https://github.com/enisdenjo/graphql-ws/blob/master/PROTOCOL.md — спецификация graphql-transport-ws
- https://www.unrealengine.com/news/unreal-engine-5-8-is-now-available (HTTP 403 при загрузке); https://forums.unrealengine.com/t/unreal-engine-5-8-released/2729274; https://forums.unrealengine.com/t/5-8-1-hotfix-released/2738864; https://forums.unrealengine.com/t/5-8-2-hotfix-released/2746335
- https://tomlooman.com/unreal-engine-5-8-performance-highlights/
- https://forums.unrealengine.com/t/cherry-picking-5-8-input-system-changes/2729847
- https://www.unrealengine.com/marketplace/en-US/product/graphql-plugin ; https://github.com/cman-dev-ue/EnjAPIQueryPlugin ; https://unrealcommunity.wiki/websocket-client-cpp-5vk7hp9e
- https://github.com/neil3d/UAnimatedTexture5 ; https://github.com/RaiaN/RuntimeImageLoader
- https://rider-support.jetbrains.com/hc/en-us/community/posts/5290088619026-Rider-for-Unreal-Engine-without-installing-Visual-Studio ; https://community.gamedev.tv/t/unreal-engine-5-4-error-when-live-compiling/246163
- https://www.emidee.net/ue4/2018/11/13/UE4-Unit-Tests-in-Jenkins.html ; https://forums.unrealengine.com/t/ue5-3-does-not-find-automation-tests-through-command-line/1747873
- `gh repo view badumbat/UEGraphQL`, `gh search repos …`, `gh repo list Mountea-Framework` (2026-09-02)
