// UmNet/Public/UmGraphQLClient.h
//
// GraphQL-over-HTTP клиент (queries / mutations) поверх IUmHttpTransport.
//
// Контракт бэкенда (R1 §2.3, §2.10; R8 §3.1 п.2):
//  - POST /graphql, тело `{ "query", "variables", "operationName" }`, заголовки `Content-Type: application/json`,
//    `Authorization: Bearer <accessToken>` (для защищённых операций).
//  - HTTP 200 — успех **и** любая ошибка резолвера/guard'а (`data` есть — null или объект, `errors[]` заполнен);
//    HTTP 400 — ошибки до исполнения (GRAPHQL_PARSE_FAILED / GRAPHQL_VALIDATION_FAILED / BAD_USER_INPUT);
//    401/409 в коде не найдены → клиент ОБЯЗАН разбирать тело независимо от статуса (R1 §2.3, §3 п.6).
//  - Элемент errors[]: dev — `{ message, code, path, locations, extensions: { code, originalError?, status? } }`;
//    prod «бизнес-ошибка» — `{ message, code, path }` без extensions; prod остальное —
//    `{ message: "Internal server error", code: "INTERNAL_SERVER_ERROR" }` (R1 §2.10). Отсюда правило R1 §3 п.24:
//    код читать из `extensions.code` ИЛИ верхнеуровневого `code`; `extensions.status`; `extensions.originalError.{statusCode,message[]}`.
//
// Уточнение к ADR: ADR §3.3 размещает FUmGraphQLRequest / FUmGraphQLError / FUmGraphQLResult / EUmErrorClass / EUmAuthMode
// в `UmGraphQLTypes.h` (группа C1). Если этот заголовок есть — он включается; иначе (самодостаточная компиляция
// сниппета C2) используется идентичный fallback-блок ниже (`__has_include`, C++17; UE 5.8 собирается C++20).
// FUmGraphQLClient в ADR §4.1 не выделен как класс — Execute описан у UUmNetSubsystem; здесь он вынесен в отдельный
// не-UObject класс (уточнение к ADR), чтобы его можно было тестировать на FUmFakeHttpTransport без GameInstance.

#pragma once

#include "CoreMinimal.h"
#include "Containers/Array.h"
#include "Containers/UnrealString.h"
#include "Delegates/Delegate.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Templates/Function.h"
#include "Templates/SharedPointer.h"
#include "UObject/NameTypes.h"

#include "UmHttpTransport.h"

#if __has_include("UmGraphQLTypes.h")
// Канонические определения из группы C1 (ADR §3.3) — используем их.
#include "UmGraphQLTypes.h"
#else
// Fallback для самодостаточной компиляции сниппета C2; содержимое идентично контракту ADR §4.1.

/** Требование токена для операции (ADR §4.1; таблица guard'ов — R1 §2.14). */
enum class EUmAuthMode : uint8
{
	/** Операция под GqlAuthGuard: без access-токена запрос не отправляется, сразу класс Auth. */
	Required,
	/** Заголовок ставится, если токен есть (публичные операции, которым токен не мешает). */
	Optional,
	/** Заголовок не ставится никогда (login/register/refreshTokens). */
	None,
};

/** Классы ошибок (ADR §4.1, §5.3). Заполняет FUmErrorClassifier (группа C1); транспорт выставляет только Network. */
enum class EUmErrorClass : uint8
{
	Network,
	Auth,
	Validation,
	Conflict,
	Concurrent,
	NotFound,
	Forbidden,
	RateLimited,
	Opaque,
	Unknown,
};

/** Запрос GraphQL (ADR §4.1). */
struct UMNET_API FUmGraphQLRequest
{
	/** Имя операции из документа (обязательно, если в документе несколько операций — R1 §2.3). */
	FString OperationName;

	/** Текст документа (из UmOps.gen.h — ADR §4.2). */
	FString Document;

	/** Переменные операции; nullptr — переменных нет. */
	TSharedPtr<FJsonObject> Variables;

	EUmAuthMode Auth = EUmAuthMode::Required;

	/** Мутации не ретраятся (ADR §4.1 FUmRetryPolicy; R7 §3 п.7). */
	bool bIsMutation = false;

	/** Тотальный таймаут HTTP, с (DefaultGame.ini HttpTimeoutSec=15 — ADR §3.5). */
	float TimeoutSec = 15.0f;

	/** Бакет FUmRateLimiter (ADR §4.1); здесь не используется, прокидывается выше. */
	FName RateLimitBucket;
};

/** Один элемент errors[] (ADR §4.1; R1 §2.10). */
struct UMNET_API FUmGraphQLError
{
	FString Message;

	/** `extensions.code` либо верхнеуровневый `code` (prod-формат без extensions) — R1 §3 п.24. */
	FString Code;

	/** `extensions.status` (409 у ConflictException, 404 у NotFoundException — R1 §2.10); 0 — нет. */
	int32 Status = 0;

	/** `extensions.originalError.statusCode`; 0 — нет. */
	int32 OriginalStatusCode = 0;

	/** `extensions.originalError.message` — строка или массив строк class-validator (BAD_REQUEST). */
	TArray<FString> OriginalMessages;

	/** `path` — сегменты как строки (числа-индексы тоже строками). */
	TArray<FString> Path;

	/** Класс ошибки; выставляется FUmErrorClassifier, транспорт задаёт только Network. */
	EUmErrorClass Class = EUmErrorClass::Unknown;
};

/** Результат операции (ADR §4.1). */
struct UMNET_API FUmGraphQLResult
{
	/** false — ответа от сервера нет (сеть/таймаут/отмена) либо тело не JSON. */
	bool bTransportOk = false;

	/** HTTP-статус; 0 при отсутствии ответа. ADR §4.1 называет поле HttpCode (в ТЗ группы — HttpStatus). */
	int32 HttpCode = 0;

	/** Присутствует ли ключ `data` в теле (при 400 его нет — R1 §2.3). */
	bool bHasDataField = false;

	/** `data`; nullptr — `data: null` (non-null корневое поле) либо ключа нет. */
	TSharedPtr<FJsonObject> Data;

	TArray<FUmGraphQLError> Errors;

	/** Причина транспортного сбоя (FUmHttpResponse::FailureReason) либо текст ошибки парсинга. */
	FString FailureReason;

	bool HasErrors() const { return Errors.Num() > 0; }

	/** Успех: ответ есть, ошибок нет, ключ `data` присутствует (даже если поле внутри null — `{ "me": null }`). */
	bool IsOk() const { return bTransportOk && Errors.Num() == 0 && bHasDataField; }

	/** Класс первой ошибки; Network при транспортном сбое; Unknown, если ошибок нет (смысл имеет только при !IsOk()). */
	EUmErrorClass Class() const;
};

#endif // __has_include("UmGraphQLTypes.h")

/** Колбэк результата; всегда на game thread. */
DECLARE_DELEGATE_OneParam(FUmOnGraphQLResult, const FUmGraphQLResult& /*Result*/);

/**
 * GraphQL HTTP-клиент. Не знает про refresh/ретраи/лимиты — это UUmNetSubsystem (ADR §4.1).
 * Создавать через MakeShared (TSharedFromThis нужен для безопасного колбэка транспорта).
 */
class UMNET_API FUmGraphQLClient final : public TSharedFromThis<FUmGraphQLClient>
{
public:
	/** Провайдер access-токена; пустая строка — токена нет. Вызывается на game thread в момент Execute. */
	using FAccessTokenProvider = TFunction<FString()>;

	/**
	 * @param InTransport   HTTP-транспорт (реальный или фейк).
	 * @param InEndpointUrl Полный URL, например `http://localhost:3000/graphql` (ApiBaseUrl + GraphQLPath — ADR §3.5, R1 §3 п.2).
	 */
	FUmGraphQLClient(TSharedRef<IUmHttpTransport> InTransport, const FString& InEndpointUrl);

	void SetAccessTokenProvider(FAccessTokenProvider InProvider) { AccessTokenProvider = MoveTemp(InProvider); }
	void SetEndpointUrl(const FString& InEndpointUrl) { EndpointUrl = InEndpointUrl; }
	const FString& GetEndpointUrl() const { return EndpointUrl; }

	/**
	 * Выполнить операцию. Возвращает идентификатор HTTP-запроса (0 — запрос не отправлен, колбэк уже вызван:
	 * например Auth == Required без токена).
	 */
	FUmHttpRequestId Execute(const FUmGraphQLRequest& Request, FUmOnGraphQLResult OnResult);

	void Cancel(FUmHttpRequestId RequestId) { Transport->Cancel(RequestId); }
	void CancelAll() { Transport->CancelAll(); }

	// --- Чистые функции (используются также FUmGraphQLWsClient и тестами) ---

	/** Тело POST: `{"query":…,"variables":…,"operationName":…}` (R1 §2.3). Variables == nullptr → ключ опускается. */
	static FString BuildBody(const FUmGraphQLRequest& Request);

	/** Разбор HTTP-ответа в FUmGraphQLResult: data + errors при 200 и 400, транспортные сбои, не-JSON тела. */
	static FUmGraphQLResult ParseResponse(const FUmHttpResponse& Http);

	/** Разбор массива errors[] (HTTP-ответ, WS `error.payload`, WS `next.payload.errors`). */
	static void ParseErrorsArray(const TArray<TSharedPtr<FJsonValue>>& ErrorsArray, TArray<FUmGraphQLError>& OutErrors);

	/** Разбор одного GraphQLFormattedError (R1 §2.10, §3 п.24). */
	static FUmGraphQLError ParseError(const TSharedPtr<FJsonObject>& ErrorObject);

	/** Сериализация FJsonObject в компактную строку (без переводов строк). */
	static FString JsonToString(const TSharedRef<FJsonObject>& Object);

	/** Разбор строки в FJsonObject; nullptr при ошибке или если корень — не объект. */
	static TSharedPtr<FJsonObject> JsonFromString(const FString& Text);

private:
	TSharedRef<IUmHttpTransport> Transport;
	FString EndpointUrl;
	FAccessTokenProvider AccessTokenProvider;
};
