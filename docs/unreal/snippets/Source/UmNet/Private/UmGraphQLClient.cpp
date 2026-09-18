// UmNet/Private/UmGraphQLClient.cpp
//
// GraphQL-over-HTTP: сборка тела, заголовки, разбор data/errors (R1 §2.3, §2.10, §3 п.24-25).

#include "UmGraphQLClient.h"

#include "Misc/CoreMisc.h"
#include "Policies/CondensedJsonPrintPolicy.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

// ---------------------------------------------------------------------------------------------------------------------
// FUmGraphQLResult
// ---------------------------------------------------------------------------------------------------------------------

EUmErrorClass FUmGraphQLResult::Class() const
{
	if (!bTransportOk)
	{
		return EUmErrorClass::Network;
	}
	if (Errors.Num() > 0)
	{
		return Errors[0].Class;
	}
	return EUmErrorClass::Unknown;
}

// ---------------------------------------------------------------------------------------------------------------------
// FUmGraphQLClient
// ---------------------------------------------------------------------------------------------------------------------

FUmGraphQLClient::FUmGraphQLClient(TSharedRef<IUmHttpTransport> InTransport, const FString& InEndpointUrl)
	: Transport(MoveTemp(InTransport))
	, EndpointUrl(InEndpointUrl)
{
}

FUmHttpRequestId FUmGraphQLClient::Execute(const FUmGraphQLRequest& Request, FUmOnGraphQLResult OnResult)
{
	check(IsInGameThread());

	const FString AccessToken = AccessTokenProvider ? AccessTokenProvider() : FString();

	if (Request.Auth == EUmAuthMode::Required && AccessToken.IsEmpty())
	{
		// Без токена защищённая операция гарантированно даст UNAUTHENTICATED (R1 §2.14) — не тратим запрос.
		// UUmNetSubsystem при классе Auth запустит refresh и повторит (ADR §4.1, §5.3).
		FUmGraphQLResult Result;
		Result.bTransportOk = true; // сервер тут ни при чём; для классификатора это Auth, не Network
		Result.HttpCode = 0;
		FUmGraphQLError Error;
		// Код UNAUTHENTICATED достаточен для класса Auth (ADR §5.3); текст — ASCII, чтобы не зависеть от кодировки исходника.
		Error.Message = TEXT("No access token for guarded operation");
		Error.Code = TEXT("UNAUTHENTICATED");
		Error.Class = EUmErrorClass::Auth;
		Result.Errors.Add(MoveTemp(Error));
		Result.FailureReason = TEXT("NoAccessToken");
		UE_LOG(LogUmNet, Verbose, TEXT("[GQL] %s skipped: no access token"), *Request.OperationName);
		OnResult.ExecuteIfBound(Result);
		return 0;
	}

	FUmHttpRequest Http;
	Http.Url = EndpointUrl;
	Http.Verb = TEXT("POST");
	Http.Body = BuildBody(Request);
	Http.TimeoutSec = Request.TimeoutSec;
	Http.Headers.Add(TEXT("Content-Type"), TEXT("application/json"));   // R1 §3 п.3
	Http.Headers.Add(TEXT("Accept"), TEXT("application/json"));
	if (Request.Auth != EUmAuthMode::None && !AccessToken.IsEmpty())
	{
		Http.Headers.Add(TEXT("Authorization"), TEXT("Bearer ") + AccessToken); // jwt.strategy.ts:16 (R8 §2.2)
	}
	// `Origin` намеренно не шлём — CORS для нативных клиентов не применяется (R1 §2.3);
	// `X-Idempotency-Key` сервер не читает (R1 §2.12; ADR §5.4).

	const FString OperationName = Request.OperationName;
	TWeakPtr<FUmGraphQLClient> WeakSelf = AsShared();
	return Transport->Send(Http, FUmOnHttpResponse::CreateLambda(
		[WeakSelf, OperationName, OnResult](const FUmHttpResponse& Response)
		{
			FUmGraphQLResult Result = ParseResponse(Response);
			if (!Result.IsOk())
			{
				UE_LOG(LogUmNet, Log, TEXT("[GQL] %s → http=%d transportOk=%d errors=%d (%s)"),
					*OperationName, Result.HttpCode, Result.bTransportOk ? 1 : 0, Result.Errors.Num(),
					Result.Errors.Num() > 0 ? *Result.Errors[0].Message : *Result.FailureReason);
			}
			// Клиент мог быть уничтожен, пока запрос летел; колбэк владельца всё равно доставляем —
			// он сам защищён weak-ссылками на субсистему.
			(void)WeakSelf;
			OnResult.ExecuteIfBound(Result);
		}));
}

FString FUmGraphQLClient::BuildBody(const FUmGraphQLRequest& Request)
{
	TSharedRef<FJsonObject> Body = MakeShared<FJsonObject>();
	Body->SetStringField(TEXT("query"), Request.Document);
	if (Request.Variables.IsValid())
	{
		Body->SetObjectField(TEXT("variables"), Request.Variables);
	}
	if (!Request.OperationName.IsEmpty())
	{
		Body->SetStringField(TEXT("operationName"), Request.OperationName);
	}
	return JsonToString(Body);
}

FString FUmGraphQLClient::JsonToString(const TSharedRef<FJsonObject>& Object)
{
	FString Out;
	// TJsonWriterFactory<CharType, PrintPolicy>::Create(FString*) — JsonWriter.h:786-791; компактная политика без пробелов.
	TSharedRef<TJsonWriter<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>> Writer =
		TJsonWriterFactory<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>::Create(&Out);
	// FJsonSerializer::Serialize(const TSharedPtr<FJsonObject>&, const TSharedRef<TJsonWriter<…>>&, bool bCloseWriter) — JsonSerializer.h:467.
	FJsonSerializer::Serialize(Object, Writer);
	return Out;
}

TSharedPtr<FJsonObject> FUmGraphQLClient::JsonFromString(const FString& Text)
{
	TSharedPtr<FJsonObject> Root;
	// TJsonReaderFactory<>::Create(const FString&) — JsonReader.h:1088; FJsonSerializer::Deserialize(Reader, TSharedPtr<FJsonObject>&) — JsonSerializer.h:337.
	TSharedRef<TJsonReader<TCHAR>> Reader = TJsonReaderFactory<TCHAR>::Create(Text);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		return nullptr;
	}
	return Root;
}

FUmGraphQLResult FUmGraphQLClient::ParseResponse(const FUmHttpResponse& Http)
{
	FUmGraphQLResult Result;
	Result.bTransportOk = Http.bTransportOk;
	Result.HttpCode = Http.HttpCode;
	Result.FailureReason = Http.FailureReason;

	if (!Http.bTransportOk)
	{
		// Сеть/таймаут/отмена → класс Network (ADR §5.3, первая строка таблицы).
		FUmGraphQLError Error;
		Error.Message = Http.FailureReason.IsEmpty() ? TEXT("Network error") : Http.FailureReason;
		Error.Code = TEXT("NETWORK_ERROR");
		Error.Class = EUmErrorClass::Network;
		Result.Errors.Add(MoveTemp(Error));
		return Result;
	}

	TSharedPtr<FJsonObject> Root = JsonFromString(Http.Body);
	if (!Root.IsValid())
	{
		// Тело не JSON (HTML Playground на GET, прокси-страница 502/504 и т.п.) → Network (ADR §5.3 «тело не JSON»).
		Result.bTransportOk = false;
		Result.FailureReason = FString::Printf(TEXT("NonJsonBody(http=%d, contentType=%s)"), Http.HttpCode, *Http.ContentType);
		FUmGraphQLError Error;
		Error.Message = Result.FailureReason;
		Error.Code = TEXT("NETWORK_ERROR");
		Error.Class = EUmErrorClass::Network;
		Result.Errors.Add(MoveTemp(Error));
		return Result;
	}

	// `data`: объект, null (non-null корневое поле) или отсутствует (HTTP 400 — R1 §2.3).
	if (Root->HasField(TEXT("data")))
	{
		Result.bHasDataField = true;
		const TSharedPtr<FJsonObject>* DataObject = nullptr;
		if (Root->TryGetObjectField(TEXT("data"), DataObject) && DataObject != nullptr)
		{
			Result.Data = *DataObject;
		}
	}

	const TArray<TSharedPtr<FJsonValue>>* ErrorsArray = nullptr;
	if (Root->TryGetArrayField(TEXT("errors"), ErrorsArray) && ErrorsArray != nullptr)
	{
		ParseErrorsArray(*ErrorsArray, Result.Errors);
	}

	if (!Result.bHasDataField && Result.Errors.Num() == 0)
	{
		// JSON есть, но ни data, ни errors — не GraphQL-ответ (например, JSON от reverse-proxy).
		FUmGraphQLError Error;
		Error.Message = FString::Printf(TEXT("Malformed GraphQL response (http=%d)"), Http.HttpCode);
		Error.Code = TEXT("MALFORMED_RESPONSE");
		Error.Class = EUmErrorClass::Unknown;
		Result.Errors.Add(MoveTemp(Error));
	}

	return Result;
}

void FUmGraphQLClient::ParseErrorsArray(const TArray<TSharedPtr<FJsonValue>>& ErrorsArray, TArray<FUmGraphQLError>& OutErrors)
{
	for (const TSharedPtr<FJsonValue>& Value : ErrorsArray)
	{
		if (!Value.IsValid())
		{
			continue;
		}
		if (Value->Type == EJson::Object)
		{
			OutErrors.Add(ParseError(Value->AsObject()));
		}
		else if (Value->Type == EJson::String)
		{
			// Защита от нестандартных серверов: строка вместо объекта.
			FUmGraphQLError Error;
			Error.Message = Value->AsString();
			OutErrors.Add(MoveTemp(Error));
		}
	}
}

FUmGraphQLError FUmGraphQLClient::ParseError(const TSharedPtr<FJsonObject>& ErrorObject)
{
	FUmGraphQLError Error;
	if (!ErrorObject.IsValid())
	{
		Error.Message = TEXT("<null error>");
		return Error;
	}

	ErrorObject->TryGetStringField(TEXT("message"), Error.Message);

	// Верхнеуровневый `code` — prod-формат без extensions (graphql.module.ts:68-102; R1 §2.10).
	ErrorObject->TryGetStringField(TEXT("code"), Error.Code);

	const TSharedPtr<FJsonObject>* Extensions = nullptr;
	if (ErrorObject->TryGetObjectField(TEXT("extensions"), Extensions) && Extensions != nullptr && Extensions->IsValid())
	{
		// `extensions.code` имеет приоритет (dev-формат дублирует код в обоих местах).
		FString ExtCode;
		if ((*Extensions)->TryGetStringField(TEXT("code"), ExtCode) && !ExtCode.IsEmpty())
		{
			Error.Code = ExtCode;
		}
		(*Extensions)->TryGetNumberField(TEXT("status"), Error.Status);

		const TSharedPtr<FJsonObject>* OriginalError = nullptr;
		if ((*Extensions)->TryGetObjectField(TEXT("originalError"), OriginalError) && OriginalError != nullptr && OriginalError->IsValid())
		{
			(*OriginalError)->TryGetNumberField(TEXT("statusCode"), Error.OriginalStatusCode);

			// `originalError.message` — строка (UnauthorizedException) или массив строк class-validator (BAD_REQUEST).
			FString SingleMessage;
			if ((*OriginalError)->TryGetStringField(TEXT("message"), SingleMessage))
			{
				Error.OriginalMessages.Add(SingleMessage);
			}
			else
			{
				(*OriginalError)->TryGetStringArrayField(TEXT("message"), Error.OriginalMessages);
			}
		}
	}

	const TArray<TSharedPtr<FJsonValue>>* PathArray = nullptr;
	if (ErrorObject->TryGetArrayField(TEXT("path"), PathArray) && PathArray != nullptr)
	{
		for (const TSharedPtr<FJsonValue>& Segment : *PathArray)
		{
			if (!Segment.IsValid())
			{
				continue;
			}
			if (Segment->Type == EJson::Number)
			{
				Error.Path.Add(FString::FromInt(static_cast<int32>(Segment->AsNumber())));
			}
			else
			{
				Error.Path.Add(Segment->AsString());
			}
		}
	}

	// Класс не определяем: это работа FUmErrorClassifier (ADR §5.3), которому нужен контекст операции
	// (login/changePassword vs защищённые операции, exp токена для Opaque).
	return Error;
}
