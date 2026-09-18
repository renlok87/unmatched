// UmNet/Public/UmHttpTransport.h
//
// HTTP-транспорт GraphQL-клиента (ADR §4.1: IUmHttpTransport / FUmHttpTransport / FUmFakeHttpTransport).
// Слой не знает про GraphQL: он отправляет POST с телом-строкой и отдаёт статус + тело ответа.
// Разбор `data`/`errors` — в FUmGraphQLClient (UmGraphQLClient.h).
//
// Факты, на которые опирается реализация:
//  - FHttpModule::Get().CreateRequest() → TSharedRef<IHttpRequest, ESPMode::ThreadSafe>
//    ($UE/Source/Runtime/Online/HTTP/Public/HttpModule.h:71; R8 §2.2).
//  - Делегат завершения по умолчанию приходит на game thread (EHttpRequestDelegateThreadPolicy::CompleteOnGameThread,
//    IHttpRequest.h:14-18; HttpRequestCommon.h:142; R8 §2.2) — мы задаём политику явно.
//  - bProcessedSuccessfully == true не означает 2xx: проверять Response->GetResponseCode() (IHttpRequest.h:43-56; R8 §2.2).
//  - Тотального таймаута по умолчанию нет (HttpTotalTimeout=0) — задаём IHttpRequest::SetTimeout (IHttpRequest.h:318; R8 §3.1 п.2).
//  - Бэкенд ждёт `Content-Type: application/json` и `Authorization: Bearer <token>` (R1 §2.3; jwt.strategy.ts:16).
//
// Расположение файла: ADR §3.3 указывает `Transport/IUmHttpTransport.h`; в сниппетах группы C2 файл называется
// `UmHttpTransport.h` (уточнение к ADR: имена классов сохранены, путь — плоский).

#pragma once

#include "CoreMinimal.h"
#include "Containers/Array.h"
#include "Containers/Map.h"
#include "Containers/UnrealString.h"
#include "Delegates/Delegate.h"
#include "Logging/LogMacros.h"
#include "Templates/Function.h"
#include "Templates/SharedPointer.h"

#include "Interfaces/IHttpRequest.h" // FHttpRequestPtr / FHttpResponsePtr (HttpFwd.h:12-13)

// Единая категория логов сетевого модуля (ADR §3.6 «Логи»: LogUmNet).
// DEFINE_LOG_CATEGORY(LogUmNet) живёт в UmHttpTransport.cpp (см. TODO там: перенести в UmNetModule.cpp при сборке модуля).
UMNET_API DECLARE_LOG_CATEGORY_EXTERN(LogUmNet, Log, All);

/** Идентификатор запроса в транспорте; 0 — «запрос не создан». */
using FUmHttpRequestId = uint64;

/** Низкоуровневый HTTP-запрос (уже сериализованное тело). */
struct UMNET_API FUmHttpRequest
{
	/** Полный URL, например `http://localhost:3000/graphql` (R1 §2.1). */
	FString Url;

	/** Метод; для GraphQL всегда POST (R1 §2.3). */
	FString Verb = TEXT("POST");

	/** Заголовки запроса (Content-Type, Authorization, …). */
	TMap<FString, FString> Headers;

	/** Тело запроса (UTF-8-строка JSON). */
	FString Body;

	/** Тотальный таймаут запроса, с; <= 0 — использовать дефолт модуля (R8 §2.2: по умолчанию 0 = без таймаута). */
	float TimeoutSec = 15.0f;
};

/** Низкоуровневый HTTP-ответ. */
struct UMNET_API FUmHttpResponse
{
	/** true — ответ сервера получен (любой статус); false — сеть/таймаут/отмена (Response == nullptr). */
	bool bTransportOk = false;

	/** HTTP-статус (0, если ответа нет). */
	int32 HttpCode = 0;

	/** Тело ответа как строка (пусто при отсутствии ответа). */
	FString Body;

	/** Текстовая причина сбоя транспорта (LexToString(EHttpFailureReason) — IHttpBase.h:58-90). */
	FString FailureReason;

	/** Заголовок Content-Type ответа (для диагностики: HTML-страница Playground на GET, R1 §2.1). */
	FString ContentType;

	/** Длительность запроса, с (для логов и FUmServerClock — не используется здесь). */
	double ElapsedSec = 0.0;
};

/** Колбэк завершения запроса. Вызывается строго на game thread. */
DECLARE_DELEGATE_OneParam(FUmOnHttpResponse, const FUmHttpResponse& /*Response*/);

/**
 * Абстракция HTTP-транспорта (ADR §4.1). Реализации:
 *  - FUmHttpTransport — поверх FHttpModule (production);
 *  - FUmFakeHttpTransport — скриптованные ответы для spec-тестов (ADR §4.8: Unmatched.Net.Auth и др.).
 *
 * Контракт: все методы вызываются на game thread; колбэк тоже приходит на game thread.
 */
class UMNET_API IUmHttpTransport
{
public:
	virtual ~IUmHttpTransport() = default;

	/**
	 * Отправить запрос. Возвращает идентификатор (для Cancel) или 0, если запрос не удалось даже начать
	 * (в этом случае OnResponse уже вызван с bTransportOk == false).
	 */
	virtual FUmHttpRequestId Send(const FUmHttpRequest& Request, FUmOnHttpResponse OnResponse) = 0;

	/** Отменить запрос; колбэк придёт с bTransportOk == false и FailureReason == "Cancelled". */
	virtual void Cancel(FUmHttpRequestId RequestId) = 0;

	/** Отменить все активные запросы (вызывается при Deinitialize субсистемы). */
	virtual void CancelAll() = 0;

	/** Число активных запросов (для тестов/диагностики). */
	virtual int32 NumInFlight() const = 0;
};

/**
 * Production-транспорт поверх FHttpModule / IHttpRequest (R8 §2.2, §3.1 п.2).
 * Создавать только через MakeShared<FUmHttpTransport>() — используется TSharedFromThis для безопасного
 * захвата self в делегате завершения.
 */
class UMNET_API FUmHttpTransport final
	: public IUmHttpTransport
	, public TSharedFromThis<FUmHttpTransport>
{
public:
	FUmHttpTransport();
	virtual ~FUmHttpTransport() override;

	// IUmHttpTransport
	virtual FUmHttpRequestId Send(const FUmHttpRequest& Request, FUmOnHttpResponse OnResponse) override;
	virtual void Cancel(FUmHttpRequestId RequestId) override;
	virtual void CancelAll() override;
	virtual int32 NumInFlight() const override { return InFlight.Num(); }

private:
	/** Собрать FUmHttpResponse из результата IHttpRequest. */
	static FUmHttpResponse BuildResponse(const FHttpRequestPtr& Request, const FHttpResponsePtr& Response, bool bProcessedSuccessfully, double StartedAtSec);

	/** Доставить ответ на game thread (страховка на случай CompleteOnHttpThread — R8 §2.2, IHttpRequest.h:410-419). */
	static void DispatchOnGameThread(FUmOnHttpResponse OnResponse, FUmHttpResponse Response);

	FUmHttpRequestId NextRequestId = 0;

	/** Активные запросы: держим ссылку, чтобы иметь возможность CancelRequest(). */
	TMap<FUmHttpRequestId, FHttpRequestPtr> InFlight;
};

/**
 * Тестовый транспорт: очередь заранее заданных ответов + журнал отправленных запросов (ADR §4.1, §4.8).
 * По умолчанию ответы доставляются отложенно — вызовом Flush() (имитирует асинхронность реального модуля);
 * bDeliverSynchronously = true — доставлять прямо из Send().
 */
class UMNET_API FUmFakeHttpTransport final : public IUmHttpTransport
{
public:
	/** Ответ, привязанный к запросу; Matcher == nullptr — подходит для любого запроса. */
	struct FScripted
	{
		TFunction<bool(const FUmHttpRequest&)> Matcher;
		FUmHttpResponse Response;
	};

	/** Добавить ответ в очередь (FIFO среди подходящих по Matcher). */
	void Enqueue(FUmHttpResponse Response, TFunction<bool(const FUmHttpRequest&)> Matcher = nullptr);

	/** Удобная форма: JSON-тело + статус, bTransportOk = true. */
	void EnqueueJson(int32 HttpCode, const FString& Body, TFunction<bool(const FUmHttpRequest&)> Matcher = nullptr);

	/** Удобная форма: сетевой сбой (bTransportOk = false, HttpCode = 0). */
	void EnqueueNetworkFailure(const FString& Reason = TEXT("ConnectionError"), TFunction<bool(const FUmHttpRequest&)> Matcher = nullptr);

	/** Доставить все отложенные колбэки (в порядке Send). Возвращает число доставленных. */
	int32 Flush();

	/** Все запросы, прошедшие через Send (для проверок заголовков/тела в тестах). */
	const TArray<FUmHttpRequest>& GetSentRequests() const { return SentRequests; }

	bool bDeliverSynchronously = false;

	// IUmHttpTransport
	virtual FUmHttpRequestId Send(const FUmHttpRequest& Request, FUmOnHttpResponse OnResponse) override;
	virtual void Cancel(FUmHttpRequestId RequestId) override;
	virtual void CancelAll() override;
	virtual int32 NumInFlight() const override { return Pending.Num(); }

private:
	struct FPending
	{
		FUmHttpRequestId Id = 0;
		FUmOnHttpResponse OnResponse;
		FUmHttpResponse Response;
	};

	/** Найти и извлечь первый подходящий скриптованный ответ; если нет — сетевой сбой «NoScriptedResponse». */
	FUmHttpResponse TakeResponseFor(const FUmHttpRequest& Request);

	FUmHttpRequestId NextRequestId = 0;
	TArray<FScripted> Scripted;
	TArray<FPending> Pending;
	TArray<FUmHttpRequest> SentRequests;
};
