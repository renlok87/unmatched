// UmErrorClassifier.cpp — реализация таблицы ADR §5.3 поверх фактов R1 §2.10 / §2.4.
#include "UmErrorClassifier.h"

#include "Logging/LogMacros.h"
#include "Misc/CoreMiscDefines.h"

DEFINE_LOG_CATEGORY_STATIC(LogUmNetClassifier, Log, All);

#define LOCTEXT_NAMESPACE "UmNet"

namespace UmErrorClassifierPrivate
{
	// Сообщения UnauthorizedException, которые на dev-стенде идут с code=UNAUTHENTICATED, а в production маскируются
	// («Неавторизованный доступ» не содержит `unauthorized` → «Internal server error», R1 §2.10, §4.6):
	//   gql-auth.guard.ts:32-37 — «Неавторизованный доступ»; jwt.strategy.ts:29-31,55-57 — «Token revoked», «Пользователь не найден».
	static const TCHAR* AuthMessages[] =
	{
		TEXT("Неавторизованный доступ"),
		TEXT("Token revoked"),
		TEXT("Пользователь не найден"),
	};

	// Подстроки веб-клиента error-link.ts:9-23 («на вырост», R1 §2.6 п.4).
	static const TCHAR* AuthSubstrings[] =
	{
		TEXT("unauthenticated"),
		TEXT("token expired"),
		TEXT("invalid token"),
	};

	// Ошибки refreshTokens (auth.service.ts:224-233, 281) — любая из них означает потерю сессии (ADR §5.3).
	static const TCHAR* RefreshRevokedMessage = TEXT("Refresh token has been revoked");

	static bool EqualsAnyCI(const FString& Value, const TCHAR* const* Candidates, int32 Num)
	{
		for (int32 i = 0; i < Num; ++i)
		{
			if (Value.Equals(Candidates[i], ESearchCase::IgnoreCase))
			{
				return true;
			}
		}
		return false;
	}

	static bool ContainsAnyCI(const FString& Value, const TCHAR* const* Candidates, int32 Num)
	{
		for (int32 i = 0; i < Num; ++i)
		{
			if (Value.Contains(Candidates[i], ESearchCase::IgnoreCase))
			{
				return true;
			}
		}
		return false;
	}
}

// ------------------------------------------------------------------------------------------------ Parse

bool FUmErrorClassifier::ParseError(const TSharedPtr<FJsonObject>& JsonError, FUmGraphQLError& OutError)
{
	if (!JsonError.IsValid())
	{
		return false;
	}

	OutError = FUmGraphQLError();
	JsonError->TryGetStringField(TEXT("message"), OutError.Message);

	// prod-формат бизнес-ошибок: { message, code, path } без extensions (graphql.module.ts:68-102 — R1 §2.10).
	JsonError->TryGetStringField(TEXT("code"), OutError.Code);

	const TSharedPtr<FJsonObject>* Extensions = nullptr;
	if (JsonError->TryGetObjectField(TEXT("extensions"), Extensions) && Extensions && Extensions->IsValid())
	{
		FString ExtCode;
		if ((*Extensions)->TryGetStringField(TEXT("code"), ExtCode) && !ExtCode.IsEmpty())
		{
			OutError.Code = ExtCode; // dev-формат: код продублирован; extensions.code приоритетнее.
		}

		// extensions.status — 409 у ConflictException, 404 у NotFoundException при code=INTERNAL_SERVER_ERROR (apollo-base.driver.js:170-190).
		int32 Status = 0;
		if ((*Extensions)->TryGetNumberField(TEXT("status"), Status))
		{
			OutError.Status = Status;
		}

		const TSharedPtr<FJsonObject>* OriginalError = nullptr;
		if ((*Extensions)->TryGetObjectField(TEXT("originalError"), OriginalError) && OriginalError && OriginalError->IsValid())
		{
			int32 OriginalStatus = 0;
			if ((*OriginalError)->TryGetNumberField(TEXT("statusCode"), OriginalStatus))
			{
				OutError.OriginalStatusCode = OriginalStatus;
			}

			// originalError.message — строка ИЛИ массив строк class-validator (BAD_REQUEST, R1 §2.10).
			const TArray<TSharedPtr<FJsonValue>>* Messages = nullptr;
			FString SingleMessage;
			if ((*OriginalError)->TryGetArrayField(TEXT("message"), Messages) && Messages)
			{
				for (const TSharedPtr<FJsonValue>& Value : *Messages)
				{
					FString Text;
					if (Value.IsValid() && Value->TryGetString(Text))
					{
						OutError.OriginalMessages.Add(Text);
					}
				}
			}
			else if ((*OriginalError)->TryGetStringField(TEXT("message"), SingleMessage))
			{
				OutError.OriginalMessages.Add(SingleMessage);
			}
		}
	}

	const TArray<TSharedPtr<FJsonValue>>* Path = nullptr;
	if (JsonError->TryGetArrayField(TEXT("path"), Path) && Path)
	{
		for (const TSharedPtr<FJsonValue>& Segment : *Path)
		{
			if (Segment.IsValid())
			{
				OutError.Path.Add(Segment->AsString()); // числовые индексы тоже сериализуются строкой
			}
		}
	}

	OutError.Class = EUmErrorClass::Unknown;
	return true;
}

void FUmErrorClassifier::ParseErrorArray(const TArray<TSharedPtr<FJsonValue>>& JsonErrors, TArray<FUmGraphQLError>& OutErrors)
{
	for (const TSharedPtr<FJsonValue>& Value : JsonErrors)
	{
		if (!Value.IsValid() || Value->Type != EJson::Object)
		{
			continue;
		}
		FUmGraphQLError Error;
		if (ParseError(Value->AsObject(), Error))
		{
			OutErrors.Add(MoveTemp(Error));
		}
	}
}

// ------------------------------------------------------------------------------------------------ Predicates

bool FUmErrorClassifier::IsAuthMessage(const FString& Message)
{
	using namespace UmErrorClassifierPrivate;
	return EqualsAnyCI(Message, AuthMessages, UE_ARRAY_COUNT(AuthMessages))
		|| ContainsAnyCI(Message, AuthSubstrings, UE_ARRAY_COUNT(AuthSubstrings));
}

bool FUmErrorClassifier::IsConcurrentMessage(const FString& Message)
{
	// ADR §5.3: /Concurrent modification|sequence/i; текст сервера — game.exceptions.ts:7-15 (R2 §2.5).
	return Message.Contains(TEXT("Concurrent modification"), ESearchCase::IgnoreCase)
		|| Message.Contains(TEXT("sequence"), ESearchCase::IgnoreCase);
}

bool FUmErrorClassifier::IsCredentialOperation(const FString& OperationName)
{
	// login → «Неверный email или пароль» (auth.service.ts:148); changePassword → «Неверный текущий пароль» (R1 §2.10 таблица реакций).
	return OperationName.Equals(TEXT("Login"), ESearchCase::IgnoreCase)
		|| OperationName.Equals(TEXT("ChangePassword"), ESearchCase::IgnoreCase);
}

// ------------------------------------------------------------------------------------------------ Classify

EUmErrorClass FUmErrorClassifier::ClassifyOne(const FUmGraphQLError& Error, const FUmClassifyContext& Context)
{
	const FString Code = Error.Code.ToUpper();
	const int32 Status = Error.Status != 0 ? Error.Status : Error.OriginalStatusCode;
	const FString& Message = Error.Message;

	// 1. Auth / credential (ADR §5.3 строки 2-3; R1 §3 п.16).
	const bool bAuthCode = Code == TEXT("UNAUTHENTICATED")
		|| Code == TEXT("AUTH_TOKEN_EXPIRED")   // не выдаётся сервером (R1 §2.6 п.4), оставлено для совместимости с error-link.ts
		|| Code == TEXT("AUTH_INVALID_TOKEN");
	if (bAuthCode || Status == 401 || IsAuthMessage(Message))
	{
		return IsCredentialOperation(Context.OperationName) ? EUmErrorClass::Validation : EUmErrorClass::Auth;
	}

	// 2. RateLimited — код не подтверждён (R2 §4.15), проверяем все варианты.
	if (Status == 429 || Code == TEXT("THROTTLED") || Code == TEXT("TOO_MANY_REQUESTS"))
	{
		return EUmErrorClass::RateLimited;
	}

	// 3. Forbidden — ForbiddenException: MatchmakingGuard, AdminGuard, «не участник», статус игры (R1 §2.10).
	if (Code == TEXT("FORBIDDEN") || Status == 403)
	{
		return EUmErrorClass::Forbidden;
	}

	// 4. Validation — ValidationPipe (BAD_REQUEST), приведение переменных, валидация/парсинг документа (HTTP 400).
	if (Code == TEXT("BAD_REQUEST") || Code == TEXT("BAD_USER_INPUT")
		|| Code == TEXT("GRAPHQL_VALIDATION_FAILED") || Code == TEXT("GRAPHQL_PARSE_FAILED"))
	{
		return EUmErrorClass::Validation;
	}

	// 5. 409: ConflictException приходит как INTERNAL_SERVER_ERROR + extensions.status 409 (R1 §2.10);
	//    код CONFLICT — по документации D07 (R3 §4), в коде не найден, учитываем на всякий случай.
	if (Status == 409 || Code == TEXT("CONFLICT"))
	{
		return IsConcurrentMessage(Message) ? EUmErrorClass::Concurrent : EUmErrorClass::Conflict;
	}

	// 6. NotFound — NotFoundException: INTERNAL_SERVER_ERROR + status 404; prod-формат сохраняет message с `not found`.
	if (Status == 404 || Code == TEXT("NOT_FOUND")
		|| Message.Contains(TEXT("not found"), ESearchCase::IgnoreCase)
		|| Message.Contains(TEXT("не найден"), ESearchCase::IgnoreCase)) // «не найден», «не найдена», «не найдено»
	{
		return EUmErrorClass::NotFound;
	}

	// 7. Concurrent без статуса (WS-путь без extensions или prod-маскирование не сработало).
	if (IsConcurrentMessage(Message) && Code == TEXT("INTERNAL_SERVER_ERROR"))
	{
		return EUmErrorClass::Concurrent;
	}

	// 8. Opaque — production-маскирование: { message: "Internal server error", code: "INTERNAL_SERVER_ERROR" } (graphql.module.ts:71-92).
	if (Code == TEXT("INTERNAL_SERVER_ERROR") && Status == 0
		&& Message.Equals(TEXT("Internal server error"), ESearchCase::IgnoreCase))
	{
		return EUmErrorClass::Opaque;
	}

	return EUmErrorClass::Unknown;
}

int32 FUmErrorClassifier::ClassPriority(EUmErrorClass Class)
{
	switch (Class)
	{
	case EUmErrorClass::Network:     return 0;
	case EUmErrorClass::Auth:        return 1;
	case EUmErrorClass::Concurrent:  return 2;
	case EUmErrorClass::RateLimited: return 3;
	case EUmErrorClass::Forbidden:   return 4;
	case EUmErrorClass::NotFound:    return 5;
	case EUmErrorClass::Conflict:    return 6;
	case EUmErrorClass::Validation:  return 7;
	case EUmErrorClass::Opaque:      return 8;
	case EUmErrorClass::Unknown:
	default:                         return 9;
	}
}

FText FUmErrorClassifier::MakeUserMessage(EUmErrorClass Class, const FString& RawMessage)
{
	// Локализация серверных текстов — DT_ServerErrorMap по подстроке в UmClient (ADR §4.6); здесь только фолбэки ADR §5.3.
	switch (Class)
	{
	case EUmErrorClass::Network:
		return LOCTEXT("Err.Network", "Нет связи с сервером");
	case EUmErrorClass::Opaque:
		return LOCTEXT("Err.Opaque", "Действие отклонено сервером");
	case EUmErrorClass::Unknown:
		return LOCTEXT("Err.Unknown", "Ошибка сервера");
	case EUmErrorClass::RateLimited:
		return LOCTEXT("Err.RateLimited", "Слишком много запросов, подождите");
	default:
		return RawMessage.IsEmpty() ? LOCTEXT("Err.Rejected", "Действие отклонено") : FText::FromString(RawMessage);
	}
}

FUmClassifiedError FUmErrorClassifier::ClassifyErrors(const TArray<FUmGraphQLError>& Errors, const FUmClassifyContext& Context)
{
	FUmClassifiedError Out;
	if (Errors.Num() == 0)
	{
		return Out;
	}

	Out.bIsError = true;
	Out.Errors = Errors;

	int32 PrimaryIndex = 0;
	int32 BestPriority = MAX_int32;
	for (int32 i = 0; i < Out.Errors.Num(); ++i)
	{
		FUmGraphQLError& E = Out.Errors[i];
		E.Class = ClassifyOne(E, Context);
		const int32 Priority = ClassPriority(E.Class);
		if (Priority < BestPriority)
		{
			BestPriority = Priority;
			PrimaryIndex = i;
		}
	}

	const FUmGraphQLError& Primary = Out.Errors[PrimaryIndex];
	Out.Class = Primary.Class;
	Out.Code = Primary.Code;
	Out.Status = Primary.Status != 0 ? Primary.Status : Primary.OriginalStatusCode;
	Out.RawMessage = Primary.Message;
	Out.OriginalMessages = Primary.OriginalMessages;
	Out.bRefreshRevoked = Primary.Message.Contains(UmErrorClassifierPrivate::RefreshRevokedMessage, ESearchCase::IgnoreCase);

	// Правило Opaque (ADR §5.3, §5.5 «Prod-маскирование UNAUTHENTICATED»): INTERNAL_SERVER_ERROR + "Internal server error"
	// + операция с Auth=Required + exp access-JWT в пределах ±окна → один раз как Auth.
	if (Out.Class == EUmErrorClass::Opaque
		&& Context.Auth == EUmAuthMode::Required
		&& Context.bHasAccessExp
		&& !Context.bAlreadyRetriedAuth)
	{
		const double DeltaSec = FMath::Abs((Context.AccessExpUtc - Context.NowUtc).GetTotalSeconds());
		if (DeltaSec <= static_cast<double>(Context.OpaqueAuthWindowSec))
		{
			Out.Class = EUmErrorClass::Auth;
			Out.bOpaqueTreatedAsAuth = true;
			UE_LOG(LogUmNetClassifier, Log, TEXT("[%s] Opaque error within %.0fs of access exp -> treated as Auth once"),
				*Context.OperationName, DeltaSec);
		}
	}

	if (Out.Class == EUmErrorClass::Validation && Out.OriginalMessages.Num() > 0)
	{
		// ADR §5.3: OriginalMessages[] — в лог (class-validator, forbidNonWhitelisted — R1 §2.3).
		UE_LOG(LogUmNetClassifier, Warning, TEXT("[%s] Validation: %s"),
			*Context.OperationName, *FString::Join(Out.OriginalMessages, TEXT("; ")));
	}

	if (Out.Class == EUmErrorClass::Validation && Out.RawMessage.Contains(TEXT("Query is too complex"), ESearchCase::IgnoreCase))
	{
		// complexity 1000 (graphql.module.ts:48-52, R1 §2.11) — дефект документа операции, а не пользователя.
		ensureMsgf(false, TEXT("[UmNet] Operation %s exceeds complexity limit: %s"), *Context.OperationName, *Out.RawMessage);
	}

	Out.UserMessage = MakeUserMessage(Out.Class, Out.RawMessage);
	return Out;
}

FUmClassifiedError FUmErrorClassifier::Classify(const FUmGraphQLResult& Result, const FUmClassifyContext& Context)
{
	// ADR §5.3 строка 1: !bTransportOk, таймаут, HttpCode == 0, тело не JSON → Network.
	// HttpCode 200 при ошибках резолверов и 400 при ошибках валидации — статус сам по себе класс не определяет (R1 §2.3).
	if (!Result.bTransportOk || Result.HttpCode == 0)
	{
		FUmClassifiedError Out;
		Out.bIsError = true;
		Out.Class = EUmErrorClass::Network;
		Out.RawMessage = FString::Printf(TEXT("transport failure (http=%d)"), Result.HttpCode);
		Out.UserMessage = MakeUserMessage(EUmErrorClass::Network, Out.RawMessage);
		return Out;
	}

	if (Result.Errors.Num() == 0)
	{
		// Успех; Data может быть null при non-null корневом поле только вместе с errors[] (R1 §2.3), так что здесь Data валиден.
		if (Result.HttpCode >= 500)
		{
			// 500 без errors[] — внутренняя ошибка пайплайна Apollo (requestPipeline.js:343-344): тело могло быть не-GraphQL.
			FUmClassifiedError Out;
			Out.bIsError = true;
			Out.Class = EUmErrorClass::Unknown;
			Out.RawMessage = FString::Printf(TEXT("HTTP %d without errors[]"), Result.HttpCode);
			Out.UserMessage = MakeUserMessage(EUmErrorClass::Unknown, Out.RawMessage);
			return Out;
		}
		return FUmClassifiedError::None();
	}

	return ClassifyErrors(Result.Errors, Context);
}

FUmWsCloseClassification FUmErrorClassifier::ClassifyWsClose(int32 CloseCode, const FString& Reason)
{
	// R1 §2.4 (common-CGW11Fyb.js:30-43, server-3ewaJSjp.js, use/ws.js:98-101); ADR §4.1.
	FUmWsCloseClassification Out;
	Out.Code = CloseCode;
	Out.Note = Reason;

	switch (CloseCode)
	{
	case 1000:
		Out.Action = EUmWsCloseAction::Normal;
		Out.Class = EUmErrorClass::Network;
		break;

	case 4406: // Subprotocol not acceptable — клиент не прислал graphql-transport-ws (R1 §4.1)
		Out.Action = EUmWsCloseAction::Configuration;
		Out.Class = EUmErrorClass::Unknown;
		break;

	case 4400: // Bad Request — невалидное сообщение
	case 4401: // Unauthorized — subscribe до connection_ack
	case 4409: // Subscriber for <id> already exists
	case 4429: // Too many initialisation requests — второй connection_init
		Out.Action = EUmWsCloseAction::ClientBug;
		Out.Class = EUmErrorClass::Unknown;
		break;

	case 4403: // Forbidden — onConnect не сконфигурирован, сервером не выдаётся (R1 §4.3); на всякий случай — как backoff
	case 4408: // Connection initialisation timeout (3 с)
	case 4500: // Internal server error в обработчике сокета
	case 4504: // Connection acknowledgement timeout — клиентский код
	case 1001: // Going away — остановка сервера
	case 1006: // Abnormal closure — обрыв без close-фрейма (terminate() при отсутствии pong-фрейма)
	case 1011: // Internal error
	default:
		Out.Action = EUmWsCloseAction::ReconnectBackoff;
		Out.Class = EUmErrorClass::Network;
		break;
	}
	return Out;
}

#undef LOCTEXT_NAMESPACE
