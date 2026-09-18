// UmNet/Public/UmGraphQLWsClient.h
//
// FUmGraphQLWsClient — клиентская машина состояний протокола graphql-transport-ws (ADR §4.1, §5.3; R1 §2.4, §3 п.7-12;
// R8 §2.3, §3.1 п.3-6). Работает поверх IUmWebSocket (реальный FUmLwsWebSocket или FUmFakeWebSocket).
//
// Протокол (R1 §2.4; спецификация graphql-ws PROTOCOL.md):
//   C→S  {"type":"connection_init","payload":{"authorization":"Bearer <accessToken>"}}   — ≤ 3 с после открытия (иначе 4408)
//   S→C  {"type":"connection_ack"}                                                        — приходит всегда (onConnect не задан)
//   C→S  {"id":"<уникальный>","type":"subscribe","payload":{"operationName","query","variables"}}
//   S→C  {"id","type":"next","payload":{"data","errors"?}} | {"id","type":"error","payload":[GraphQLError]} | {"id","type":"complete"}
//   C→S  {"id","type":"complete"}                                                         — отписка
//   C↔S  {"type":"ping","payload"?} ↔ {"type":"pong","payload"?}
// Close-коды: 4400 bad request, 4401 subscribe до ack, 4403 forbidden (наш сервер не выдаёт), 4406 сабпротокол,
// 4408 таймаут init, 4409 дубль id, 4429 второй init, 4500 internal, 1001 going away, 1006 обрыв без close-frame.
//
// Состояния (ADR §4.1): Idle → Connecting → AwaitingAck → Ready → Backoff / Failed / Closing.
// Backoff: 1 с × 2^(n−1), 5 попыток (эталон веб-клиента: SubscriptionHandler.ts:98-101 — R1 §2.15), с jitter.
// Все вызовы и делегаты — game thread.

#pragma once

#include "CoreMinimal.h"
#include "Containers/Array.h"
#include "Containers/Map.h"
#include "Containers/Ticker.h"
#include "Containers/UnrealString.h"
#include "Delegates/Delegate.h"
#include "Dom/JsonObject.h"
#include "Templates/Function.h"
#include "Templates/SharedPointer.h"

#include "UmGraphQLClient.h" // FUmGraphQLError, FUmGraphQLClient::ParseErrorsArray/JsonToString
#include "UmWebSocket.h"

/** Состояние соединения (ADR §4.1). Соответствие тегам Net.State.* — ToNetStateTagName(). */
enum class EUmWsState : uint8
{
	/** Сокета нет; подписки (если есть) ждут Connect(). */
	Idle,
	/** IUmWebSocket::Connect() вызван, ждём OnConnected. */
	Connecting,
	/** connection_init отправлен, ждём connection_ack (таймаут — Config.AckTimeoutSec). */
	AwaitingAck,
	/** Сессия готова: подписки отправлены, прикладной ping активен. */
	Ready,
	/** Ждём истечения задержки перед следующей попыткой (Attempt ≤ MaxAttempts). */
	Backoff,
	/** Клиент сам закрывает сокет (Terminate/Reconnect/таймаут ack/pong); ждём OnClosed. */
	Closing,
	/** Попытки исчерпаны либо ошибка без ретрая (4406, 4403, повторный баг клиента). Выход — Reconnect()/Connect(). */
	Failed,
};

/** Почему соединение упало/закрыто — для OnStateChanged и логов. */
struct UMNET_API FUmWsDisconnectInfo
{
	/** WS close-код; 0 — OnConnectionError (соединение не установилось). */
	int32 Code = 0;
	FString Reason;
	bool bWasClean = false;
	/** true — закрытие инициировано клиентом (Terminate/Reconnect/таймауты). */
	bool bRequestedByClient = false;
};

/** Параметры клиента (значения по умолчанию — из DefaultGame.ini [/Script/UmNet.UmNetSettings], ADR §3.5). */
struct UMNET_API FUmWsClientConfig
{
	/** Таймаут ожидания OnConnected после Connect(), с (у LWS собственного нет — страховка). */
	float ConnectTimeoutSec = 10.0f;

	/** WsConnectionAckTimeoutSec=5 (ADR §3.5). При истечении — Close(4504 «Connection acknowledgement timeout») + backoff. */
	float AckTimeoutSec = 5.0f;

	/** WsReconnectMaxAttempts=5 (ADR §3.5; R1 §2.15 retryAttempts: 5). */
	int32 ReconnectMaxAttempts = 5;

	/** WsReconnectBaseDelayMs=1000 (ADR §3.5): задержка n-й попытки = Base × 2^(n−1). */
	int32 ReconnectBaseDelayMs = 1000;

	/** Доля случайного разброса задержки (0.2 → ±20 %). */
	float ReconnectJitterFraction = 0.2f;

	/** Потолок задержки, мс (при 5 попытках не достигается: 1,2,4,8,16 с). */
	int32 ReconnectMaxDelayMs = 30000;

	/** WsAppPingIntervalSec=10 (ADR §3.5): прикладной JSON-ping в Ready. 0 — выключить. */
	float AppPingIntervalSec = 10.0f;

	/** Если pong не пришёл за это время после ping — считаем соединение мёртвым: Close(1000, "pong-timeout") + backoff. */
	float AppPongTimeoutSec = 10.0f;
};

/** Описание подписки. */
struct UMNET_API FUmSubscriptionSpec
{
	/** Имя операции (например `GameStateUpdated`, ADR §3.6). */
	FString OperationName;

	/** Документ подписки (UmOps.gen.h). */
	FString Document;

	/** Текущие переменные (например `{ gameId, since }`). */
	TSharedPtr<FJsonObject> Variables;

	/**
	 * Колбэк переподписки: вызывается перед повторным `subscribe` после реконнекта и получает последние переменные;
	 * возвращает новые (владелец подставляет `since = LastSeq` — ADR §5.2, R1 §3 п.11). nullptr — переменные без изменений.
	 */
	TFunction<TSharedPtr<FJsonObject>(const TSharedPtr<FJsonObject>& /*LastVariables*/)> BuildVariablesForResubscribe;
};

/** Колбэки одной подписки (дополняют общие делегаты клиента). */
struct UMNET_API FUmSubscriptionCallbacks
{
	/** `next`: Data — payload.data (может быть nullptr), Errors — payload.errors (подписка остаётся живой — ADR §5.3, F24). */
	TFunction<void(const TSharedPtr<FJsonObject>& /*Data*/, const TArray<FUmGraphQLError>& /*Errors*/)> OnNext;
	/** `error`: терминально, подписка удалена. */
	TFunction<void(const TArray<FUmGraphQLError>& /*Errors*/)> OnError;
	/** `complete` от сервера: подписка удалена. При Unsubscribe() клиентом не вызывается. */
	TFunction<void()> OnComplete;
};

DECLARE_MULTICAST_DELEGATE_ThreeParams(FUmOnWsStateChanged, EUmWsState /*Old*/, EUmWsState /*New*/, const FUmWsDisconnectInfo& /*LastDisconnect*/);
DECLARE_MULTICAST_DELEGATE_ThreeParams(FUmOnSubscriptionNext, const FString& /*Id*/, const TSharedPtr<FJsonObject>& /*Data*/, const TArray<FUmGraphQLError>& /*Errors*/);
DECLARE_MULTICAST_DELEGATE_TwoParams(FUmOnSubscriptionError, const FString& /*Id*/, const TArray<FUmGraphQLError>& /*Errors*/);
DECLARE_MULTICAST_DELEGATE_OneParam(FUmOnSubscriptionComplete, const FString& /*Id*/);
/** Сервер отверг соединение по auth (close 4403 по спецификации). Владелец должен выполнить refresh и вызвать Reconnect(). */
DECLARE_MULTICAST_DELEGATE_OneParam(FUmOnWsAuthRejected, const FUmWsDisconnectInfo& /*Info*/);

/**
 * Машина состояний graphql-transport-ws. Владелец — UUmNetSubsystem (ADR §4.1): он даёт провайдер токена,
 * вызывает Reconnect("token-refreshed") после refresh (ADR §5.3) и маппит EUmWsState → Net.State.*.
 * Создавать через MakeShared (TSharedFromThis нужен для тикера и биндингов на сокет).
 */
class UMNET_API FUmGraphQLWsClient final : public TSharedFromThis<FUmGraphQLWsClient>
{
public:
	using FAccessTokenProvider = TFunction<FString()>;
	using FNowProvider = TFunction<double()>;

	/**
	 * @param InSocket    Сокет (уже сконфигурирован URL/сабпротоколом). События биндятся в конструкторе — до Connect().
	 * @param InConfig    Параметры.
	 * @param bInAutoTick true — регистрируется в FTSTicker::GetCoreTicker(); false — владелец/тест вызывает Tick() сам.
	 */
	FUmGraphQLWsClient(TSharedRef<IUmWebSocket> InSocket, const FUmWsClientConfig& InConfig, bool bInAutoTick = true);
	~FUmGraphQLWsClient();

	// --- Конфигурация ---

	/** Провайдер access-токена; читается при каждом connection_init (R1 §2.15: connectionParams — функция). */
	void SetAccessTokenProvider(FAccessTokenProvider InProvider) { AccessTokenProvider = MoveTemp(InProvider); }

	/** Источник времени (секунды, монотонные); по умолчанию FPlatformTime::Seconds(). Для тестов. */
	void SetNowProvider(FNowProvider InProvider) { NowProvider = MoveTemp(InProvider); }

	const FUmWsClientConfig& GetConfig() const { return Config; }

	// --- Управление соединением ---

	/** Начать подключение из Idle/Failed (сброс счётчика попыток). В остальных состояниях — no-op. */
	void Connect();

	/**
	 * Пересоздать сессию с новым токеном (после refresh — ADR §5.3, R1 §3 п.11) либо по требованию владельца.
	 * Ready/AwaitingAck/Connecting → Close(1000, Reason) → после OnClosed немедленный Connect;
	 * Backoff → немедленная попытка; Idle/Failed → Connect(). Счётчик попыток сбрасывается.
	 * @param bForce false — в Ready без активных подписок ничего не делать (нечего переподписывать).
	 */
	void Reconnect(const FString& Reason, bool bForce = true);

	/** Закрыть сокет (1000), забыть все подписки, перейти в Idle. Колбэки подписок не вызываются. */
	void Terminate(const FString& Reason = TEXT("client-terminate"));

	EUmWsState GetState() const { return State; }
	bool IsReady() const { return State == EUmWsState::Ready; }
	int32 GetReconnectAttempt() const { return ReconnectAttempt; }
	const FUmWsDisconnectInfo& GetLastDisconnect() const { return LastDisconnect; }

	/** Имя тега Net.State.* для состояния (сами теги — в UmModel/UmTags.h; UmNet от GameplayTags не зависит — ADR §3.2). */
	static const TCHAR* ToNetStateTagName(EUmWsState InState);
	static const TCHAR* ToString(EUmWsState InState);

	// --- Подписки ---

	/**
	 * Зарегистрировать подписку. Возвращает id (уникальный в рамках клиента). Если сессия Ready — `subscribe` уходит сразу;
	 * иначе — после connection_ack. Из Idle/Failed автоматически вызывает Connect() (lazy, как в веб-клиенте — R1 §2.15).
	 */
	FString Subscribe(const FUmSubscriptionSpec& Spec, FUmSubscriptionCallbacks Callbacks);

	/** Отписаться: в Ready отправляется `complete {id}`; подписка удаляется; колбэки не вызываются. */
	void Unsubscribe(const FString& Id);

	/** Обновить переменные подписки (например новый `since`) без переотправки; применятся при следующей переподписке. */
	void UpdateVariables(const FString& Id, const TSharedPtr<FJsonObject>& NewVariables);

	bool HasSubscription(const FString& Id) const { return Subscriptions.Contains(Id); }
	int32 NumSubscriptions() const { return Subscriptions.Num(); }

	// --- Делегаты ---

	FUmOnWsStateChanged OnStateChanged;
	FUmOnSubscriptionNext OnSubscriptionNext;
	FUmOnSubscriptionError OnSubscriptionError;
	FUmOnSubscriptionComplete OnSubscriptionComplete;
	FUmOnWsAuthRejected OnAuthRejected;

	// --- Тик (публичный для тестов; при bAutoTick вызывается тикером) ---

	/** Обрабатывает таймауты: Connecting, AwaitingAck, Backoff, ping/pong. Возвращает true (тикер продолжает). */
	bool Tick(float DeltaSeconds);

	// --- Сборка сообщений (публично для тестов) ---

	static FString BuildConnectionInit(const FString& AccessToken);
	static FString BuildSubscribe(const FString& Id, const FUmSubscriptionSpec& Spec);
	static FString BuildComplete(const FString& Id);
	static FString BuildPing();
	static FString BuildPong(const TSharedPtr<FJsonObject>& EchoPayload);

private:
	struct FSubscription
	{
		FUmSubscriptionSpec Spec;
		FUmSubscriptionCallbacks Callbacks;
		/** true — `subscribe` с этим id уже уходил хотя бы раз (для BuildVariablesForResubscribe). */
		bool bSentOnce = false;
		/** true — `subscribe` отправлен в текущей сессии (после последнего ack). */
		bool bActiveInSession = false;
	};

	/** Что делать после OnClosed, если закрытие инициировали мы. */
	enum class EAfterClose : uint8
	{
		Stay,          // Terminate → Idle
		ReconnectNow,  // Reconnect → Connecting без задержки
		Backoff,       // таймауты ack/pong → ScheduleBackoff
	};

	// Переходы
	void SetState(EUmWsState NewState);
	void StartConnectAttempt();
	void ScheduleBackoff();
	void RequestClose(int32 Code, const FString& Reason, EAfterClose InAfterClose);
	void HandleDisconnect(const FUmWsDisconnectInfo& Info);
	void FailPermanently(const TCHAR* Why);

	// События сокета
	void HandleSocketConnected();
	void HandleSocketConnectionError(const FString& Error);
	void HandleSocketClosed(int32 StatusCode, const FString& Reason, bool bWasClean);
	void HandleSocketMessage(const FString& Message);

	// Сообщения протокола
	void OnConnectionAck();
	void OnPing(const TSharedPtr<FJsonObject>& Root);
	void OnPong();
	void OnNext(const FString& Id, const TSharedPtr<FJsonObject>& Payload);
	void OnError(const FString& Id, const TSharedPtr<FJsonObject>& Root);
	void OnComplete(const FString& Id);

	void SendSubscribe(const FString& Id, FSubscription& Sub);
	void ResubscribeAll();
	void ClearSessionTimers();

	double Now() const;
	FString NextSubscriptionId();

	TSharedRef<IUmWebSocket> Socket;
	FUmWsClientConfig Config;
	FAccessTokenProvider AccessTokenProvider;
	FNowProvider NowProvider;

	EUmWsState State = EUmWsState::Idle;
	FUmWsDisconnectInfo LastDisconnect;

	/** Порядок важен для детерминированной переподписки — TMap с сохранением порядка вставки. */
	TMap<FString, FSubscription> Subscriptions;
	uint64 SubscriptionCounter = 0;

	// Реконнект
	int32 ReconnectAttempt = 0;
	bool bClientBugRetryUsed = false;
	EAfterClose AfterClose = EAfterClose::Stay;

	// Дедлайны (секунды по Now()); < 0 — не активен
	double ConnectDeadline = -1.0;
	double AckDeadline = -1.0;
	double BackoffDeadline = -1.0;
	double NextPingAt = -1.0;
	double PongDeadline = -1.0;

	// Тикер
	bool bAutoTick = false;
	FTSTicker::FDelegateHandle TickerHandle;
};
