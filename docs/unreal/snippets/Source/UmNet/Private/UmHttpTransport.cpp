// UmNet/Private/UmHttpTransport.cpp
//
// Реализация IUmHttpTransport поверх FHttpModule (R8 §2.2, §3.1 п.2) и тестового фейка.

#include "UmHttpTransport.h"

#include "Async/Async.h"
#include "HAL/PlatformTime.h"
#include "HttpModule.h"
#include "Interfaces/IHttpRequest.h"
#include "Interfaces/IHttpResponse.h"
#include "Misc/CoreMisc.h"

// TODO(UmNet): при сборке модуля перенести DEFINE_LOG_CATEGORY(LogUmNet) в Private/UmNetModule.cpp
// (единственное определение на модуль); здесь — чтобы сниппет группы C2 был самодостаточен.
DEFINE_LOG_CATEGORY(LogUmNet);

// ---------------------------------------------------------------------------------------------------------------------
// FUmHttpTransport
// ---------------------------------------------------------------------------------------------------------------------

FUmHttpTransport::FUmHttpTransport()
{
	// FHttpModule::Get() подгружает модуль по требованию (HttpModule.h:59); ничего не делаем.
}

FUmHttpTransport::~FUmHttpTransport()
{
	CancelAll();
}

FUmHttpRequestId FUmHttpTransport::Send(const FUmHttpRequest& Request, FUmOnHttpResponse OnResponse)
{
	check(IsInGameThread());

	const FUmHttpRequestId Id = ++NextRequestId;
	const double StartedAt = FPlatformTime::Seconds();

	// HttpModule.h:71 — TSharedRef<IHttpRequest, ESPMode::ThreadSafe>.
	TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Http = FHttpModule::Get().CreateRequest();
	Http->SetVerb(Request.Verb);                          // IHttpRequest.h:190
	Http->SetURL(Request.Url);                            // IHttpRequest.h:199
	for (const TPair<FString, FString>& Header : Request.Headers)
	{
		Http->SetHeader(Header.Key, Header.Value);        // IHttpRequest.h:297
	}
	Http->SetContentAsString(Request.Body);               // IHttpRequest.h:240
	if (Request.TimeoutSec > 0.0f)
	{
		Http->SetTimeout(Request.TimeoutSec);             // IHttpRequest.h:318 — тотальный таймаут, т.к. HttpTotalTimeout=0 по умолчанию
	}
	// Явно требуем доставку делегата на game thread (IHttpRequest.h:14-18, 419).
	Http->SetDelegateThreadPolicy(EHttpRequestDelegateThreadPolicy::CompleteOnGameThread);

	TWeakPtr<FUmHttpTransport> WeakSelf = AsShared();
	// FHttpRequestCompleteDelegate = TTSDelegate<void(FHttpRequestPtr, FHttpResponsePtr, bool)> (IHttpRequest.h:55).
	Http->OnProcessRequestComplete().BindLambda(
		[WeakSelf, Id, OnResponse, StartedAt](FHttpRequestPtr CompletedRequest, FHttpResponsePtr Response, bool bProcessedSuccessfully)
		{
			if (TSharedPtr<FUmHttpTransport> Self = WeakSelf.Pin())
			{
				Self->InFlight.Remove(Id);
			}
			FUmHttpResponse Out = BuildResponse(CompletedRequest, Response, bProcessedSuccessfully, StartedAt);
			DispatchOnGameThread(OnResponse, MoveTemp(Out));
		});

	InFlight.Add(Id, Http);

	if (!Http->ProcessRequest())                          // IHttpRequest.h:356
	{
		// Запрос не стартовал (например, домен запрещён allowlist'ом — HttpManager.h:256). Делегат завершения при этом
		// может и не прийти — отвечаем сами.
		InFlight.Remove(Id);
		Http->OnProcessRequestComplete().Unbind();
		FUmHttpResponse Failure;
		Failure.bTransportOk = false;
		Failure.FailureReason = TEXT("ProcessRequestFailed");
		UE_LOG(LogUmNet, Warning, TEXT("[HTTP] ProcessRequest() failed for %s"), *Request.Url);
		OnResponse.ExecuteIfBound(Failure);
		return 0;
	}

	UE_LOG(LogUmNet, Verbose, TEXT("[HTTP] #%llu %s %s (%d bytes)"), Id, *Request.Verb, *Request.Url, Request.Body.Len());
	return Id;
}

void FUmHttpTransport::Cancel(FUmHttpRequestId RequestId)
{
	check(IsInGameThread());
	if (FHttpRequestPtr* Found = InFlight.Find(RequestId))
	{
		if (Found->IsValid())
		{
			// После CancelRequest() делегат завершения приходит с GetFailureReason() == Cancelled (IHttpBase.h:63).
			(*Found)->CancelRequest();                    // IHttpRequest.h:386
		}
	}
}

void FUmHttpTransport::CancelAll()
{
	// Копия ключей: CancelRequest() может синхронно вызвать делегат и изменить InFlight.
	TArray<FUmHttpRequestId> Ids;
	InFlight.GetKeys(Ids);
	for (const FUmHttpRequestId Id : Ids)
	{
		Cancel(Id);
	}
}

FUmHttpResponse FUmHttpTransport::BuildResponse(const FHttpRequestPtr& Request, const FHttpResponsePtr& Response, bool bProcessedSuccessfully, double StartedAtSec)
{
	FUmHttpResponse Out;
	Out.ElapsedSec = FPlatformTime::Seconds() - StartedAtSec;

	// R8 §2.2: bProcessedSuccessfully не гарантирует 2xx; наличие Response — признак, что сервер ответил.
	if (Response.IsValid())
	{
		Out.bTransportOk = true;
		Out.HttpCode = Response->GetResponseCode();          // IHttpResponse.h:126
		Out.Body = Response->GetContentAsString();           // IHttpResponse.h:133
		Out.ContentType = Response->GetContentType();        // IHttpBase.h:152
	}
	else
	{
		Out.bTransportOk = false;
		Out.HttpCode = 0;
	}

	if (!bProcessedSuccessfully || !Response.IsValid())
	{
		const EHttpFailureReason Reason = Request.IsValid() ? Request->GetFailureReason() : EHttpFailureReason::Other; // IHttpBase.h:121
		Out.FailureReason = LexToString(Reason);
		if (!Response.IsValid())
		{
			UE_LOG(LogUmNet, Warning, TEXT("[HTTP] transport failure: %s (%.2fs)"), *Out.FailureReason, Out.ElapsedSec);
		}
	}
	return Out;
}

void FUmHttpTransport::DispatchOnGameThread(FUmOnHttpResponse OnResponse, FUmHttpResponse Response)
{
	if (IsInGameThread())
	{
		OnResponse.ExecuteIfBound(Response);
		return;
	}
	// Страховка: при CompleteOnHttpThread делегат может прийти из любого потока (IHttpRequest.h:410-419).
	AsyncTask(ENamedThreads::GameThread, [OnResponse, Response = MoveTemp(Response)]()
	{
		OnResponse.ExecuteIfBound(Response);
	});
}

// ---------------------------------------------------------------------------------------------------------------------
// FUmFakeHttpTransport
// ---------------------------------------------------------------------------------------------------------------------

void FUmFakeHttpTransport::Enqueue(FUmHttpResponse Response, TFunction<bool(const FUmHttpRequest&)> Matcher)
{
	Scripted.Add(FScripted{ MoveTemp(Matcher), MoveTemp(Response) });
}

void FUmFakeHttpTransport::EnqueueJson(int32 HttpCode, const FString& Body, TFunction<bool(const FUmHttpRequest&)> Matcher)
{
	FUmHttpResponse Response;
	Response.bTransportOk = true;
	Response.HttpCode = HttpCode;
	Response.Body = Body;
	Response.ContentType = TEXT("application/json; charset=utf-8");
	Enqueue(MoveTemp(Response), MoveTemp(Matcher));
}

void FUmFakeHttpTransport::EnqueueNetworkFailure(const FString& Reason, TFunction<bool(const FUmHttpRequest&)> Matcher)
{
	FUmHttpResponse Response;
	Response.bTransportOk = false;
	Response.HttpCode = 0;
	Response.FailureReason = Reason;
	Enqueue(MoveTemp(Response), MoveTemp(Matcher));
}

FUmHttpResponse FUmFakeHttpTransport::TakeResponseFor(const FUmHttpRequest& Request)
{
	for (int32 Index = 0; Index < Scripted.Num(); ++Index)
	{
		const FScripted& Candidate = Scripted[Index];
		if (!Candidate.Matcher || Candidate.Matcher(Request))
		{
			FUmHttpResponse Response = Candidate.Response;
			Scripted.RemoveAt(Index);
			return Response;
		}
	}
	FUmHttpResponse Missing;
	Missing.bTransportOk = false;
	Missing.FailureReason = TEXT("NoScriptedResponse");
	UE_LOG(LogUmNet, Warning, TEXT("[FakeHTTP] no scripted response for %s"), *Request.Url);
	return Missing;
}

FUmHttpRequestId FUmFakeHttpTransport::Send(const FUmHttpRequest& Request, FUmOnHttpResponse OnResponse)
{
	const FUmHttpRequestId Id = ++NextRequestId;
	SentRequests.Add(Request);

	FPending Entry;
	Entry.Id = Id;
	Entry.OnResponse = MoveTemp(OnResponse);
	Entry.Response = TakeResponseFor(Request);

	if (bDeliverSynchronously)
	{
		Entry.OnResponse.ExecuteIfBound(Entry.Response);
	}
	else
	{
		Pending.Add(MoveTemp(Entry));
	}
	return Id;
}

void FUmFakeHttpTransport::Cancel(FUmHttpRequestId RequestId)
{
	const int32 Index = Pending.IndexOfByPredicate([RequestId](const FPending& P) { return P.Id == RequestId; });
	if (Index != INDEX_NONE)
	{
		FPending Entry = MoveTemp(Pending[Index]);
		Pending.RemoveAt(Index);
		Entry.Response.bTransportOk = false;
		Entry.Response.HttpCode = 0;
		Entry.Response.Body.Reset();
		Entry.Response.FailureReason = TEXT("Cancelled");
		Entry.OnResponse.ExecuteIfBound(Entry.Response);
	}
}

void FUmFakeHttpTransport::CancelAll()
{
	while (Pending.Num() > 0)
	{
		Cancel(Pending[0].Id);
	}
}

int32 FUmFakeHttpTransport::Flush()
{
	int32 Delivered = 0;
	// Колбэк может добавить новые запросы (ретрай) — обрабатываем снимок.
	TArray<FPending> Batch = MoveTemp(Pending);
	Pending.Reset();
	for (FPending& Entry : Batch)
	{
		Entry.OnResponse.ExecuteIfBound(Entry.Response);
		++Delivered;
	}
	return Delivered;
}
