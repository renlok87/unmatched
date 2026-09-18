// UmErrorClassifier.h — классификатор ошибок GraphQL/HTTP/WS → EUmErrorClass.
// Источник правил: ADR §5.3 (таблица классов), §4.1 (FUmErrorClassifier); R1 §2.10 (формат errors[] dev/prod,
// маппинг Nest-исключений → extensions.code), R1 §2.4 (WS close-коды, next{errors} без extensions.code),
// R1 §3 п.16, п.24; R2 §3.21 (Concurrent modification); R7 §2.2 (error-link веба — коды AUTH_TOKEN_EXPIRED/AUTH_INVALID_TOKEN «на вырост»).
#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Misc/DateTime.h"

// Общие типы UmNet (группа C1, ADR §3.3: UmGraphQLTypes.h). Классификатор опирается ровно на такой контракт:
//   UENUM enum class EUmAuthMode  : uint8 { Required, Optional, None };
//   UENUM enum class EUmErrorClass: uint8 { Network, Auth, Validation, Conflict, Concurrent, NotFound, Forbidden, RateLimited, Opaque, Unknown };
//   struct FUmGraphQLError  { FString Message; FString Code; int32 Status; int32 OriginalStatusCode; TArray<FString> OriginalMessages; TArray<FString> Path; EUmErrorClass Class; };
//   struct FUmGraphQLResult { bool bTransportOk; int32 HttpCode; TSharedPtr<FJsonObject> Data; TArray<FUmGraphQLError> Errors; };
#include "UmGraphQLTypes.h"

/**
 * Контекст классификации: без него нельзя отличить UNAUTHENTICATED от Login («Неверный email или пароль» — ошибка ввода)
 * от UNAUTHENTICATED защищённой операции (истёкший токен) — R1 §3 п.16; и нельзя применить правило Opaque (ADR §5.3).
 */
struct UMNET_API FUmClassifyContext
{
	/** Имя операции (PascalCase, как в unreal/Ops/*.graphql — ADR §3.6): "Login", "ChangePassword", "RefreshTokens", "Attack"… */
	FString OperationName;

	/** Требование аутентификации операции. Opaque→Auth применяется только при Required. */
	EUmAuthMode Auth = EUmAuthMode::Required;

	/** exp текущего access-JWT (UTC), если известен — для правила Opaque (±OpaqueAuthWindowSec вокруг exp). */
	bool bHasAccessExp = false;
	FDateTime AccessExpUtc;

	/** Окно правила Opaque, с (UUmNetSettings::OpaqueAuthWindowSec, по умолчанию 120). */
	int32 OpaqueAuthWindowSec = 120;

	/** true — запрос уже повторялся после refresh; Opaque второй раз не трактуется как Auth («один раз» — ADR §5.3). */
	bool bAlreadyRetriedAuth = false;

	/** «Сейчас» (UTC) — параметр ради детерминированных тестов Unmatched.Net.ErrorClassifier (ADR §4.8). */
	FDateTime NowUtc = FDateTime::UtcNow();
};

/** Результат классификации одного ответа (агрегат по всем errors[]). */
struct UMNET_API FUmClassifiedError
{
	/** false — ответ без ошибок (errors[] пуст и транспорт в порядке). */
	bool bIsError = false;

	EUmErrorClass Class = EUmErrorClass::Unknown;

	/** Код первичной ошибки: extensions.code ИЛИ верхнеуровневый code (prod-формат без extensions — R1 §2.10). */
	FString Code;

	/** extensions.status или originalError.statusCode (409/404 — R1 §2.10); 0 — не задан. */
	int32 Status = 0;

	/** Сырой message первичной ошибки (смесь RU/EN — R1 §2.10). Для UI — через DT_ServerErrorMap (ADR §4.6). */
	FString RawMessage;

	/** Сообщение для пользователя: RawMessage либо обобщённый текст для Opaque/Unknown/Network. */
	FText UserMessage;

	/** originalError.message[] class-validator (BAD_REQUEST) — только в лог (ADR §5.3). */
	TArray<FString> OriginalMessages;

	/** true — класс Opaque был переквалифицирован в Auth по правилу exp ±окно (ADR §5.3); UUmNetSubsystem делает это не более одного раза. */
	bool bOpaqueTreatedAsAuth = false;

	/** true — сообщение «Refresh token has been revoked» (вход с другого устройства — R1 §2.6). */
	bool bRefreshRevoked = false;

	/** Все ошибки ответа с проставленным Class (для логов/тестов). */
	TArray<FUmGraphQLError> Errors;

	static FUmClassifiedError None()
	{
		return FUmClassifiedError();
	}
};

/** Действие при закрытии WS (R1 §2.4 таблица close-кодов; ADR §4.1 строка FUmGraphQLWsClient). */
enum class EUmWsCloseAction : uint8
{
	/** 1000 — штатное закрытие по инициативе клиента. */
	Normal,
	/** 1001/1006/4408/4500 и прочие — реконнект с backoff. */
	ReconnectBackoff,
	/** 4400/4401/4409/4429 — баг клиента: лог Error, один реконнект без цикла. */
	ClientBug,
	/** 4406 — неверный субпротокол (нужен graphql-transport-ws): конфигурация, без ретрая. */
	Configuration,
};

struct UMNET_API FUmWsCloseClassification
{
	int32 Code = 0;
	EUmWsCloseAction Action = EUmWsCloseAction::ReconnectBackoff;
	/** Всегда Network для реконнектов; Unknown для ClientBug/Configuration. */
	EUmErrorClass Class = EUmErrorClass::Network;
	FString Note;
};

/**
 * Чистые функции без состояния. Все правила — таблица ADR §5.3 (включая Opaque).
 * Тестируется в Unmatched.Net.ErrorClassifier на dev/prod-форматах (ADR §4.8).
 */
class UMNET_API FUmErrorClassifier
{
public:
	/**
	 * Разбор массива errors[] тела HTTP-ответа или payload WS-сообщений next/error в FUmGraphQLError.
	 * Читает: message; extensions.code | code; extensions.status; extensions.originalError.{statusCode, message(string|array)}; path[].
	 * (R1 §2.10, §3 п.24). Class у элементов не проставляется — см. Classify*.
	 */
	static void ParseErrorArray(const TArray<TSharedPtr<FJsonValue>>& JsonErrors, TArray<FUmGraphQLError>& OutErrors);

	/** Разбор одного элемента errors[]. Возвращает false, если элемент — не объект. */
	static bool ParseError(const TSharedPtr<FJsonObject>& JsonError, FUmGraphQLError& OutError);

	/** HTTP-ответ целиком: транспорт → Network; иначе агрегат по errors[]; пустой errors[] → bIsError=false. */
	static FUmClassifiedError Classify(const FUmGraphQLResult& Result, const FUmClassifyContext& Context);

	/**
	 * Список ошибок без транспорта — для WS: `error{payload:[...]}` и `next{payload:{errors:[...]}}` (R1 §2.4).
	 * В WS-пути extensions.code, как правило, отсутствует (formatError не применяется) — работают подстроки сообщения.
	 */
	static FUmClassifiedError ClassifyErrors(const TArray<FUmGraphQLError>& Errors, const FUmClassifyContext& Context);

	/** Одна ошибка → класс (без агрегации и без Opaque→Auth; Opaque возвращается как есть). */
	static EUmErrorClass ClassifyOne(const FUmGraphQLError& Error, const FUmClassifyContext& Context);

	/** Close-код WS → действие (R1 §2.4; ADR §4.1). */
	static FUmWsCloseClassification ClassifyWsClose(int32 CloseCode, const FString& Reason);

	/** Сообщения guard'а/стратегии, означающие «нужен refresh» (R1 §2.5, §2.10; ADR §5.3). */
	static bool IsAuthMessage(const FString& Message);

	/** «Concurrent modification detected. Expected sequence X, got Y…» (R2 §2.5 saveState, §3.21). */
	static bool IsConcurrentMessage(const FString& Message);

	/** Операции, у которых UNAUTHENTICATED — ошибка ввода, а не истёкший токен (R1 §3 п.16). */
	static bool IsCredentialOperation(const FString& OperationName);

private:
	/** Приоритет при агрегации нескольких ошибок: чем меньше, тем важнее. */
	static int32 ClassPriority(EUmErrorClass Class);

	static FText MakeUserMessage(EUmErrorClass Class, const FString& RawMessage);
};
