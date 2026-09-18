// UmNet/Public/UmWebSocket.h
//
// Абстракция WebSocket (ADR §4.1: IUmWebSocket / FUmLwsWebSocket / FUmFakeWebSocket).
// Тонкая обёртка над IWebSocket из модуля WebSockets, чтобы FUmGraphQLWsClient тестировался без сети
// (ADR §4.8: Unmatched.Net.WsStateMachine на FUmFakeWebSocket).
//
// Факты (R8 §2.3):
//  - FWebSocketsModule::Get().CreateWebSocket(Url, Protocol, UpgradeHeaders) — WebSocketsModule.h:72; check(IsInGameThread())
//    внутри Get() (WebSocketsModule.cpp:77-86) → создавать и Connect() только на game thread.
//  - Список Protocols → заголовок Sec-WebSocket-Protocol (LwsWebSocket.cpp:787-795); нам нужен ровно
//    `graphql-transport-ws`, иначе сервер закрывает 4406 (R1 §2.4).
//  - OnMessage/OnRawMessage/OnBinaryMessage должны быть забинжены ДО Connect(): иначе события никогда не приходят
//    (LwsWebSocket.h:327-341).
//  - Все события IWebSocket бродкастятся на game thread (LwsWebSocket.cpp:595-618, 625-648).
//  - Connect() допустим только из внутреннего состояния None; после OnClosed/OnConnectionError объект снова None
//    (LwsWebSocket.cpp:105-109, 625-648). Чтобы не зависеть от гонки «Close() → Connect() до финализации»,
//    FUmLwsWebSocket пересоздаёт IWebSocket на каждый Connect() (уточнение к ADR: ADR §4.1 говорит «объект
//    переиспользуется» — семантика для клиента та же, но реализация надёжнее).
//  - Схемы URL: ws / wss / wss+insecure (LwsWebSocket.cpp:736-759).
//
// Расположение файла: ADR §3.3 — `Transport/IUmWebSocket.h`; здесь — `UmWebSocket.h` (уточнение к ADR, см. UmHttpTransport.h).

#pragma once

#include "CoreMinimal.h"
#include "Containers/Array.h"
#include "Containers/Map.h"
#include "Containers/UnrealString.h"
#include "Delegates/Delegate.h"
#include "Templates/SharedPointer.h"

class IWebSocket;

/** Соединение установлено (после WS-handshake). */
DECLARE_MULTICAST_DELEGATE(FUmOnWsConnected);
/** Соединение не удалось установить (DNS/TCP/TLS/handshake/«Invalid Domain»); объект готов к новому Connect(). */
DECLARE_MULTICAST_DELEGATE_OneParam(FUmOnWsConnectionError, const FString& /*Error*/);
/** Соединение закрыто: StatusCode — WS close-код (1000/1001/1006/4400…), bWasClean — был ли close-frame. */
DECLARE_MULTICAST_DELEGATE_ThreeParams(FUmOnWsClosed, int32 /*StatusCode*/, const FString& /*Reason*/, bool /*bWasClean*/);
/** Входящее текстовое сообщение (UTF-8 → FString). Бинарные фреймы протоколом graphql-transport-ws не используются. */
DECLARE_MULTICAST_DELEGATE_OneParam(FUmOnWsMessage, const FString& /*Message*/);

/**
 * Минимальный интерфейс WebSocket, достаточный для graphql-transport-ws (текстовые JSON-фреймы, R1 §2.4).
 * Все методы и делегаты — game thread.
 */
class UMNET_API IUmWebSocket
{
public:
	virtual ~IUmWebSocket() = default;

	/** Начать подключение. Повторный вызов после OnClosed/OnConnectionError допустим (переподключение). */
	virtual void Connect() = 0;

	/** Закрыть соединение; OnClosed придёт асинхронно (у LWS — из GameThreadTick). Code — по спецификации WS. */
	virtual void Close(int32 Code = 1000, const FString& Reason = FString()) = 0;

	virtual bool IsConnected() const = 0;

	/** Отправить текстовый фрейм. Возвращает false, если соединения нет (сообщение отброшено). */
	virtual bool Send(const FString& Text) = 0;

	FUmOnWsConnected OnConnected;
	FUmOnWsConnectionError OnConnectionError;
	FUmOnWsClosed OnClosed;
	FUmOnWsMessage OnMessage;
};

/**
 * Production-реализация поверх IWebSocket (libwebsockets на Windows/Android/Mac/Unix/iOS — WebSockets.Build.cs:7-17).
 * Создавать через MakeShared — используется TSharedFromThis для безопасных биндингов на события IWebSocket.
 */
class UMNET_API FUmLwsWebSocket final
	: public IUmWebSocket
	, public TSharedFromThis<FUmLwsWebSocket>
{
public:
	/**
	 * @param InUrl           `ws://host:3000/graphql` (dev) / `wss://…` (prod, предпосылка B20) / `wss+insecure://…` (self-signed dev).
	 * @param InProtocol      Сабпротокол; по умолчанию `graphql-transport-ws` (R1 §2.4, R8 §3.1 п.3).
	 * @param InUpgradeHeaders Доп. заголовки handshake; для нашего бэкенда не нужны — токен уходит в connection_init
	 *                         (graphql.module.ts:23-33; R8 §3.1 п.3).
	 */
	explicit FUmLwsWebSocket(const FString& InUrl, const FString& InProtocol = TEXT("graphql-transport-ws"), const TMap<FString, FString>& InUpgradeHeaders = TMap<FString, FString>());
	virtual ~FUmLwsWebSocket() override;

	// IUmWebSocket
	virtual void Connect() override;
	virtual void Close(int32 Code = 1000, const FString& Reason = FString()) override;
	virtual bool IsConnected() const override;
	virtual bool Send(const FString& Text) override;

	const FString& GetUrl() const { return Url; }
	void SetUrl(const FString& InUrl) { Url = InUrl; }

	/**
	 * Лимит текстового сообщения на этом сокете (IWebSocket.h:45-49); дефолт — [WebSockets] TextMessageMemoryLimit
	 * (ADR §3.5 задаёт 8 МБ в DefaultEngine.ini). 0 — не переопределять.
	 */
	uint64 TextMessageMemoryLimitOverride = 0;

private:
	void BindEvents(const TSharedRef<IWebSocket>& Socket);
	void UnbindEvents(const TSharedRef<IWebSocket>& Socket);

	void HandleConnected();
	void HandleConnectionError(const FString& Error);
	void HandleClosed(int32 StatusCode, const FString& Reason, bool bWasClean);
	void HandleMessage(const FString& Message);

	FString Url;
	FString Protocol;
	TMap<FString, FString> UpgradeHeaders;

	/** Текущий IWebSocket (создаётся на каждый Connect()). */
	TSharedPtr<IWebSocket> Inner;

	/** Порядковый номер соединения — чтобы игнорировать запоздавшие события старого сокета. */
	uint32 Generation = 0;
};

/**
 * Тестовый сокет: не подключается никуда; тест управляет событиями через Simulate*().
 * Все отправленные строки копятся в SentMessages.
 */
class UMNET_API FUmFakeWebSocket final : public IUmWebSocket
{
public:
	// IUmWebSocket
	virtual void Connect() override;
	virtual void Close(int32 Code = 1000, const FString& Reason = FString()) override;
	virtual bool IsConnected() const override { return bConnected; }
	virtual bool Send(const FString& Text) override;

	// --- Управление из теста ---
	void SimulateConnected();
	void SimulateConnectionError(const FString& Error);
	void SimulateClosed(int32 Code, const FString& Reason = FString(), bool bWasClean = true);
	void SimulateMessage(const FString& Message);

	/** Число вызовов Connect() (проверка backoff'а). */
	int32 ConnectCount = 0;
	/** Последний Close() со стороны клиента. */
	int32 LastCloseCode = 0;
	FString LastCloseReason;
	/** Все Send() (JSON-строки). */
	TArray<FString> SentMessages;

	/** Если true — Close() сразу же бродкастит OnClosed(Code, Reason, true), как сделал бы сервер, приняв close-frame. */
	bool bAutoEmitClosedOnClose = true;

	/** Если true — Connect() сразу же бродкастит OnConnected (удобно для «счастливого пути»). */
	bool bAutoConnect = false;

	/** Сбросить журнал между кейсами (состояние соединения не трогает). */
	void ResetLog();

private:
	bool bConnected = false;
	bool bConnecting = false;
};
