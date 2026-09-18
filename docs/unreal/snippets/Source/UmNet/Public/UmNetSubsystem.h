// UmNetSubsystem.h — фасад сетевого слоя: Execute (HTTP GraphQL) с auto-refresh-and-retry, Subscribe (graphql-transport-ws),
// состояние Net.State.* как GameplayTag, FUmRateLimiter, FUmRetryPolicy, интерфейс IUmAuthProvider.
// Источник: ADR §4.1 (строки UUmNetSubsystem, FUmRateLimiter, FUmRetryPolicy, FUmGraphQLWsClient), §5.3, §5.4, §5.6 (Net.State.*);
// R1 §2.3 (HTTP), §2.4 (WS), §2.11 (лимиты), §2.12 (идемпотентность), §3 п.1-12; R7 §2.2 (retry-link), §3 п.7; R8 §2.2-2.3, §3.1.
//
// (уточнение к ADR) В ADR §3.3 FUmRateLimiter и FUmRetryPolicy живут в UmRateLimiter.h / UmRetryPolicy.h; в этом сниппете они
// размещены здесь, чтобы группа файлов была самодостаточной — при переносе в проект вынести без изменений.
// (уточнение к ADR) Модуль UmNet получает зависимость GameplayTags (ADR §3.2 её не перечисляет): теги Net.State.* объявляются
// здесь нативно (UE_DECLARE_GAMEPLAY_TAG_EXTERN) и определяются в UmNetSubsystem.cpp; UmModel/UmTags.h их НЕ дублирует.
#pragma once

#include "CoreMinimal.h"
#include "Containers/Ticker.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "GameplayTagContainer.h"
#include "Misc/DateTime.h"
#include "NativeGameplayTags.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "Templates/Function.h"
#include "Templates/SharedPointer.h"

#include "UmErrorClassifier.h"
#include "UmGraphQLTypes.h" // EUmAuthMode, EUmErrorClass, FUmGraphQLRequest, FUmGraphQLError, FUmGraphQLResult (группа C1)

#include "UmNetSubsystem.generated.h"

class IUmHttpTransport;   // Transport/IUmHttpTransport.h (группа C1): PostJson(Url, Headers, Body, TimeoutSec, OnDone)
class FUmGraphQLWsClient; // UmGraphQLWsClient.h (группа C2): state machine graphql-transport-ws (К1 §3.3.4)
enum class EUmWsState : uint8;
class UUmNetSettings;

UMNET_API DECLARE_LOG_CATEGORY_EXTERN(LogUmNet, Log, All);

// ------------------------------------------------------------------------------------------------ Net.State.* (ADR §5.6)

UMNET_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(TAG_Net_State_Disconnected);
UMNET_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(TAG_Net_State_Connecting);
UMNET_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(TAG_Net_State_Connected);
UMNET_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(TAG_Net_State_Reconnecting);
UMNET_API UE_DECLARE_GAMEPLAY_TAG_EXTERN(TAG_Net_State_Error);

/** Состояние WS-канала подписок (HTTP-канал состояния не имеет — каждый запрос независим). */
UENUM()
enum class EUmNetState : uint8
{
	Disconnected, // Idle / Closing завершён / Shutdown
	Connecting,   // Connecting / AwaitingAck
	Connected,    // Ready (connection_ack получен; валидность токена проверяется на каждом subscribe — R1 §2.4 п.10)
	Reconnecting, // Backoff
	Error,        // Failed — исчерпаны попытки; WBP_ReconnectOverlay с кнопкой (К1 §3.3.4 п.8)
};

UMNET_API FGameplayTag UmNetStateToTag(EUmNetState State);

// ------------------------------------------------------------------------------------------------ IUmAuthProvider

using FUmOnRefreshDone = TFunction<void(bool bSuccess)>;

/**
 * То, что UUmNetSubsystem знает об auth (реализует UUmAuthSubsystem — ADR §4.1). Регистрируется через SetAuthProvider().
 * Чистый C++-интерфейс (не UInterface): оба класса живут в UmNet, Blueprint его не видит (ADR §4.0).
 */
class UMNET_API IUmAuthProvider
{
public:
	virtual ~IUmAuthProvider() = default;

	/** Текущий access-JWT (только память — ADR §5.3); пусто, если сессии нет. */
	virtual FString GetAccessToken() const = 0;

	/** exp access-JWT (UTC) для правила Opaque (ADR §5.3); false — токена нет. */
	virtual bool GetAccessExpUtc(FDateTime& OutExpUtc) const = 0;

	/** Есть ли refresh-токен, т. е. имеет ли смысл пытаться обновиться. */
	virtual bool CanRefresh() const = 0;

	/**
	 * Single-flight refresh: при уже идущем refresh колбэк встаёт в очередь того же запроса (R1 §2.6 п.5, ADR §4.1).
	 * Вызывается на game thread; колбэк — на game thread. При провале провайдер сам объявляет SessionLost.
	 */
	virtual void RefreshTokens(FUmOnRefreshDone OnDone) = 0;
};

// ------------------------------------------------------------------------------------------------ FUmRateLimiter (ADR §4.1, §5.4; R1 §2.11)

struct UMNET_API FUmRateLimitSpec
{
	/** Максимум запросов за окно. */
	int32 Limit = 0;
	/** Окно, с (60 для всех @Throttle кроме deleteAccount — 3600). */
	double WindowSec = 60.0;
};

/**
 * Token bucket по объявленным @Throttle бэкенда: «мягко» — операция получает локальный RateLimited и UI блокирует кнопку до окна.
 * Сервер лимиты сейчас не применяет (ThrottlerGuard не привязан — R1 §4.7), проектируем «как будто включены» (R1 §3 п.22).
 * Ключ бакета — FUmGraphQLRequest::RateLimitBucket (имя поля мутации в camelCase: "login", "createGame", "attack"…).
 */
class UMNET_API FUmRateLimiter
{
public:
	FUmRateLimiter();

	/** Таблица по R1 §2.11 (auth/users), R3 §2.1 (game/game-actions), R2 §2.4 (joinQueue). */
	static TMap<FName, FUmRateLimitSpec> DefaultSpecs();

	void Configure(const TMap<FName, FUmRateLimitSpec>& Specs);

	/** Списать токен. Неизвестный бакет → всегда true. NowSec — FPlatformTime::Seconds() (параметр ради тестов). */
	bool TryAcquire(FName Bucket, double NowSec);

	/** Сколько ждать до следующего токена; 0 — доступно. */
	double SecondsUntilAvailable(FName Bucket, double NowSec) const;

	void Reset();

private:
	struct FBucket
	{
		FUmRateLimitSpec Spec;
		double Tokens = 0.0;
		double LastRefillSec = 0.0;
	};

	void Refill(FBucket& Bucket, double NowSec) const;

	TMap<FName, FBucket> Buckets;
};

// ------------------------------------------------------------------------------------------------ FUmRetryPolicy (ADR §4.1, §5.4; R7 §2.2, §3 п.7)

class UMNET_API FUmRetryPolicy
{
public:
	/**
	 * Ретраить ли попытку номер AttemptsDone+1 при классе ErrorClass.
	 * Правила: только Network; только bIsMutation == false (gameplay-мутации никогда — bэк защищён optimistic lock,
	 * повтор даст «Concurrent modification», R7 §3 п.7); исключение — CreateGame с тем же idempotencyKey: 1 повтор (R1 §2.12).
	 */
	static bool ShouldRetry(const FUmGraphQLRequest& Request, EUmErrorClass ErrorClass, int32 AttemptsDone, const UUmNetSettings& Settings);

	/** Задержка перед попыткой: Base × 2^AttemptsDone, cap Max, jitter ±25 % (retry-link.ts: 300 мс → 10 с, jitter). */
	static float DelaySec(int32 AttemptsDone, const UUmNetSettings& Settings);
};

// ------------------------------------------------------------------------------------------------ Подписки

struct UMNET_API FUmSubscriptionHandle
{
	FString Id;
	bool IsValid() const { return !Id.IsEmpty(); }
};

/** payload.data сообщения next (без обёртки; поле операции внутри — R7 §2.13 п.2: payload вложен в data). */
using FUmOnSubscriptionNext = TFunction<void(const TSharedPtr<FJsonObject>& Data)>;
/** error{payload} ИЛИ next{errors} (подписка при этом НЕ снимается — F24, ADR §5.3). */
using FUmOnSubscriptionError = TFunction<void(const FUmClassifiedError& Error, bool bSubscriptionEnded)>;
using FUmOnSubscriptionComplete = TFunction<void()>;
using FUmVariablesProvider = TFunction<TSharedPtr<FJsonObject>()>;

/** Результат Execute: Result — сырой ответ; Error.bIsError == false при успехе. */
using FUmOnResult = TFunction<void(const FUmGraphQLResult& Result, const FUmClassifiedError& Error)>;

DECLARE_MULTICAST_DELEGATE_TwoParams(FUmOnNetStateChanged, EUmNetState /*State*/, FGameplayTag /*Tag*/);

// ------------------------------------------------------------------------------------------------ UUmNetSubsystem

/**
 * Единственная точка входа в сеть для UmClient (ADR §4.0). Ничего игрового не знает (ADR §3.2).
 * Все методы — game thread; HTTP-делегаты приходят на game thread по умолчанию (R8 §2.2), события IWebSocket — тоже (R8 §2.3).
 */
UCLASS()
class UMNET_API UUmNetSubsystem : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	//~ USubsystem
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

	// ---------------------------------------------------------------- Композиция (фейки для тестов/UUmMockBackend — ADR §4.8)

	void SetAuthProvider(IUmAuthProvider* InProvider);
	IUmAuthProvider* GetAuthProvider() const { return AuthProvider; }

	void SetHttpTransport(TSharedPtr<IUmHttpTransport> InTransport);
	void SetWsClient(TSharedPtr<FUmGraphQLWsClient> InWsClient);

	FUmRateLimiter& GetRateLimiter() { return RateLimiter; }

	// ---------------------------------------------------------------- HTTP (queries / mutations)

	/**
	 * POST {query, variables, operationName} на GetHttpUrl(). Authorization: Bearer <access> при Auth != None и наличии токена
	 * (пустой заголовок, как в веб-authLink, не шлём). Origin и X-Idempotency-Key не отправляются (R1 §2.3, §2.12).
	 * Тело разбирается независимо от HTTP-кода (R1 §2.3). При классе Auth и Auth != None — single-flight refresh → повтор ОДИН раз;
	 * при Network — FUmRetryPolicy. Локальный RateLimited — без запроса к серверу.
	 */
	void Execute(const FUmGraphQLRequest& Request, FUmOnResult OnResult);

	// ---------------------------------------------------------------- WS (subscriptions)

	/**
	 * Подписка через FUmGraphQLWsClient; VariablesProvider вызывается при каждой (пере)подписке — так `since` берётся актуальный
	 * (К1 §3.3.4 п.4). Сокет создаётся лениво при первой подписке (веб: lazy: true — R1 §2.15).
	 */
	FUmSubscriptionHandle Subscribe(const FString& OperationName, const FString& Document, FUmVariablesProvider VariablesProvider,
		FUmOnSubscriptionNext OnNext, FUmOnSubscriptionError OnError, FUmOnSubscriptionComplete OnComplete);

	/** Шлёт complete{id}; повторный вызов безопасен. */
	void Unsubscribe(const FUmSubscriptionHandle& Handle);

	/**
	 * Пересоздать сокет с новым connection_init: обязательно после refresh — токен фиксируется на всё время сокета (R1 §2.4;
	 * веб этого не делает — R7 §2.13 п.17). Активные подписки переустанавливаются клиентом после connection_ack.
	 */
	void ReconnectWebSocket(const FString& Reason);

	/** Ручной реконнект из WBP_ReconnectOverlay: сбрасывает счётчик попыток. */
	void RetryConnection();

	EUmNetState GetNetState() const { return NetState; }
	FGameplayTag GetNetStateTag() const { return UmNetStateToTag(NetState); }
	FUmOnNetStateChanged OnNetStateChanged;

	/** Контекст классификации для операции (имя, режим auth, exp access). */
	FUmClassifyContext MakeClassifyContext(const FString& OperationName, EUmAuthMode Auth, bool bAlreadyRetriedAuth) const;

private:
	struct FUmExecState
	{
		FUmGraphQLRequest Request;
		FUmOnResult OnResult;
		int32 NetworkAttemptsDone = 0;
		bool bAuthRetried = false;
	};

	void ExecuteInternal(TSharedRef<FUmExecState> State);
	void OnHttpDone(TSharedRef<FUmExecState> State, bool bProcessedOk, int32 StatusCode, const FString& Body);
	void Deliver(const TSharedRef<FUmExecState>& State, const FUmGraphQLResult& Result, const FUmClassifiedError& Error);
	static FString BuildBody(const FUmGraphQLRequest& Request);
	static bool ParseBody(const FString& Body, FUmGraphQLResult& OutResult);

	void EnsureWsClient();
	void HandleWsStateChanged(EUmWsState WsState);
	void HandleWsClosed(int32 Code, const FString& Reason, bool bWasClean);
	void SetNetState(EUmNetState NewState);

	/** next{errors} / error{payload} на подписке: классификация; Auth → refresh → ReconnectWebSocket. */
	void HandleSubscriptionErrors(const FString& OperationName, const TArray<FUmGraphQLError>& Errors, bool bEnded, const FUmOnSubscriptionError& OnError);

	FString GetAccessTokenForWs() const;

	IUmAuthProvider* AuthProvider = nullptr;
	TSharedPtr<IUmHttpTransport> Http;
	TSharedPtr<FUmGraphQLWsClient> Ws;
	FUmRateLimiter RateLimiter;
	EUmNetState NetState = EUmNetState::Disconnected;

	/** Один WS-auth-refresh за раз (несколько подписок могут упасть одновременно). */
	bool bWsAuthRefreshInFlight = false;

	/** Отложенные ретраи — FTSTicker с задержкой; снимаются в Deinitialize. */
	TArray<FTSTicker::FDelegateHandle> PendingRetryTickers;
};
