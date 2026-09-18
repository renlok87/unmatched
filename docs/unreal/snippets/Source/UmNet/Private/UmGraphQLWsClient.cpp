// UmNet/Private/UmGraphQLWsClient.cpp
//
// Машина состояний graphql-transport-ws (R1 §2.4, §3 п.7-12; R8 §2.3, §3.1 п.4-6; ADR §4.1, §5.3).

#include "UmGraphQLWsClient.h"

#include "Dom/JsonValue.h"
#include "HAL/PlatformTime.h"
#include "Math/UnrealMathUtility.h"
#include "Misc/CoreMisc.h"

namespace UmWsProtocol
{
	// Типы сообщений graphql-transport-ws (common-CGW11Fyb.js:45-52 — R1 §2.4).
	static const TCHAR* ConnectionInit = TEXT("connection_init");
	static const TCHAR* ConnectionAck  = TEXT("connection_ack");
	static const TCHAR* Ping           = TEXT("ping");
	static const TCHAR* Pong           = TEXT("pong");
	static const TCHAR* Subscribe      = TEXT("subscribe");
	static const TCHAR* Next           = TEXT("next");
	static const TCHAR* Error          = TEXT("error");
	static const TCHAR* Complete       = TEXT("complete");

	// Close-коды (common-CGW11Fyb.js:30-43; R1 §2.4).
	constexpr int32 CloseNormal                 = 1000;
	constexpr int32 CloseGoingAway              = 1001;
	constexpr int32 CloseAbnormal               = 1006;
	constexpr int32 CloseBadRequest             = 4400;
	constexpr int32 CloseUnauthorized           = 4401;
	constexpr int32 CloseForbidden              = 4403;
	constexpr int32 CloseSubprotocolNotAccepted = 4406;
	constexpr int32 CloseInitTimeout            = 4408;
	constexpr int32 CloseSubscriberExists       = 4409;
	constexpr int32 CloseTooManyInit            = 4429;
	constexpr int32 CloseInternalError          = 4500;
	constexpr int32 CloseAckTimeout             = 4504; // клиентский код «Connection acknowledgement timeout»
}

// ---------------------------------------------------------------------------------------------------------------------
// Конструктор / деструктор / утилиты
// ---------------------------------------------------------------------------------------------------------------------

FUmGraphQLWsClient::FUmGraphQLWsClient(TSharedRef<IUmWebSocket> InSocket, const FUmWsClientConfig& InConfig, bool bInAutoTick)
	: Socket(MoveTemp(InSocket))
	, Config(InConfig)
	, bAutoTick(bInAutoTick)
{
	// Биндим события ДО первого Connect() (R8 §2.3: LwsWebSocket.h:327-341). AddRaw + RemoveAll в деструкторе:
	// клиент владеет сокетом (TSharedRef), поэтому сокет не переживёт клиента.
	Socket->OnConnected.AddRaw(this, &FUmGraphQLWsClient::HandleSocketConnected);
	Socket->OnConnectionError.AddRaw(this, &FUmGraphQLWsClient::HandleSocketConnectionError);
	Socket->OnClosed.AddRaw(this, &FUmGraphQLWsClient::HandleSocketClosed);
	Socket->OnMessage.AddRaw(this, &FUmGraphQLWsClient::HandleSocketMessage);

	if (bAutoTick)
	{
		// Containers/Ticker.h:21,45 — FTickerDelegate = bool(float); тикер живёт на game thread.
		TickerHandle = FTSTicker::GetCoreTicker().AddTicker(
			FTickerDelegate::CreateRaw(this, &FUmGraphQLWsClient::Tick), 0.0f);
	}
}

FUmGraphQLWsClient::~FUmGraphQLWsClient()
{
	if (bAutoTick)
	{
		FTSTicker::RemoveTicker(TickerHandle); // Ticker.h:66
	}
	Socket->OnConnected.RemoveAll(this);
	Socket->OnConnectionError.RemoveAll(this);
	Socket->OnClosed.RemoveAll(this);
	Socket->OnMessage.RemoveAll(this);
	if (Socket->IsConnected())
	{
		Socket->Close(UmWsProtocol::CloseNormal, TEXT("client-destroyed"));
	}
}

double FUmGraphQLWsClient::Now() const
{
	return NowProvider ? NowProvider() : FPlatformTime::Seconds();
}

FString FUmGraphQLWsClient::NextSubscriptionId()
{
	// Уникальность требуется среди активных операций одного соединения (R1 §2.4, 4409); монотонный счётчик
	// уникален и между сессиями — переиспользования id нет вовсе.
	return FString::Printf(TEXT("s%llu"), ++SubscriptionCounter);
}

const TCHAR* FUmGraphQLWsClient::ToString(EUmWsState InState)
{
	switch (InState)
	{
	case EUmWsState::Idle:        return TEXT("Idle");
	case EUmWsState::Connecting:  return TEXT("Connecting");
	case EUmWsState::AwaitingAck: return TEXT("AwaitingAck");
	case EUmWsState::Ready:       return TEXT("Ready");
	case EUmWsState::Backoff:     return TEXT("Backoff");
	case EUmWsState::Closing:     return TEXT("Closing");
	case EUmWsState::Failed:      return TEXT("Failed");
	}
	return TEXT("?");
}

const TCHAR* FUmGraphQLWsClient::ToNetStateTagName(EUmWsState InState)
{
	// Таксономия ADR §5.6: Net.State.{Disconnected,Connecting,Connected,Reconnecting,Error}.
	switch (InState)
	{
	case EUmWsState::Idle:        return TEXT("Net.State.Disconnected");
	case EUmWsState::Connecting:  return TEXT("Net.State.Connecting");
	case EUmWsState::AwaitingAck: return TEXT("Net.State.Connecting");
	case EUmWsState::Ready:       return TEXT("Net.State.Connected");
	case EUmWsState::Backoff:     return TEXT("Net.State.Reconnecting");
	case EUmWsState::Closing:     return TEXT("Net.State.Reconnecting");
	case EUmWsState::Failed:      return TEXT("Net.State.Error");
	}
	return TEXT("Net.State.Error");
}

void FUmGraphQLWsClient::SetState(EUmWsState NewState)
{
	if (State == NewState)
	{
		return;
	}
	const EUmWsState Old = State;
	State = NewState;
	UE_LOG(LogUmNet, Log, TEXT("[GQL-WS] %s → %s (attempt=%d, subs=%d)"), ToString(Old), ToString(NewState), ReconnectAttempt, Subscriptions.Num());
	OnStateChanged.Broadcast(Old, NewState, LastDisconnect);
}

void FUmGraphQLWsClient::ClearSessionTimers()
{
	ConnectDeadline = -1.0;
	AckDeadline = -1.0;
	NextPingAt = -1.0;
	PongDeadline = -1.0;
}

// ---------------------------------------------------------------------------------------------------------------------
// Сборка сообщений
// ---------------------------------------------------------------------------------------------------------------------

FString FUmGraphQLWsClient::BuildConnectionInit(const FString& AccessToken)
{
	// graphql.module.ts:23-33 читает payload.authorization / Authorization / token; веб шлёт `authorization: "Bearer <t>"`
	// либо "" без токена (apolloClient.ts:16-36 — R1 §2.15). Ack придёт в любом случае (R1 §2.4 шаг 2).
	TSharedRef<FJsonObject> Payload = MakeShared<FJsonObject>();
	Payload->SetStringField(TEXT("authorization"), AccessToken.IsEmpty() ? FString() : (TEXT("Bearer ") + AccessToken));

	TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetStringField(TEXT("type"), UmWsProtocol::ConnectionInit);
	Root->SetObjectField(TEXT("payload"), Payload);
	return FUmGraphQLClient::JsonToString(Root);
}

FString FUmGraphQLWsClient::BuildSubscribe(const FString& Id, const FUmSubscriptionSpec& Spec)
{
	TSharedRef<FJsonObject> Payload = MakeShared<FJsonObject>();
	if (!Spec.OperationName.IsEmpty())
	{
		Payload->SetStringField(TEXT("operationName"), Spec.OperationName);
	}
	Payload->SetStringField(TEXT("query"), Spec.Document);
	if (Spec.Variables.IsValid())
	{
		Payload->SetObjectField(TEXT("variables"), Spec.Variables);
	}

	TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetStringField(TEXT("id"), Id);
	Root->SetStringField(TEXT("type"), UmWsProtocol::Subscribe);
	Root->SetObjectField(TEXT("payload"), Payload);
	return FUmGraphQLClient::JsonToString(Root);
}

FString FUmGraphQLWsClient::BuildComplete(const FString& Id)
{
	TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetStringField(TEXT("id"), Id);
	Root->SetStringField(TEXT("type"), UmWsProtocol::Complete);
	return FUmGraphQLClient::JsonToString(Root);
}

FString FUmGraphQLWsClient::BuildPing()
{
	TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetStringField(TEXT("type"), UmWsProtocol::Ping);
	return FUmGraphQLClient::JsonToString(Root);
}

FString FUmGraphQLWsClient::BuildPong(const TSharedPtr<FJsonObject>& EchoPayload)
{
	// Спецификация: payload у ping опционален и эхом возвращается в pong (R1 §2.4).
	TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetStringField(TEXT("type"), UmWsProtocol::Pong);
	if (EchoPayload.IsValid())
	{
		Root->SetObjectField(TEXT("payload"), EchoPayload);
	}
	return FUmGraphQLClient::JsonToString(Root);
}

// ---------------------------------------------------------------------------------------------------------------------
// Управление соединением
// ---------------------------------------------------------------------------------------------------------------------

void FUmGraphQLWsClient::Connect()
{
	check(IsInGameThread());
	if (State != EUmWsState::Idle && State != EUmWsState::Failed)
	{
		UE_LOG(LogUmNet, Verbose, TEXT("[GQL-WS] Connect() ignored in state %s"), ToString(State));
		return;
	}
	ReconnectAttempt = 0;
	bClientBugRetryUsed = false;
	StartConnectAttempt();
}

void FUmGraphQLWsClient::StartConnectAttempt()
{
	ClearSessionTimers();
	BackoffDeadline = -1.0;
	for (TPair<FString, FSubscription>& Pair : Subscriptions)
	{
		Pair.Value.bActiveInSession = false;
	}
	AfterClose = EAfterClose::Stay;
	SetState(EUmWsState::Connecting);
	ConnectDeadline = Now() + Config.ConnectTimeoutSec;
	Socket->Connect();
}

void FUmGraphQLWsClient::Reconnect(const FString& Reason, bool bForce)
{
	check(IsInGameThread());
	UE_LOG(LogUmNet, Log, TEXT("[GQL-WS] Reconnect(%s, force=%d) in state %s"), *Reason, bForce ? 1 : 0, ToString(State));

	ReconnectAttempt = 0;
	bClientBugRetryUsed = false;

	switch (State)
	{
	case EUmWsState::Idle:
	case EUmWsState::Failed:
		StartConnectAttempt();
		break;

	case EUmWsState::Backoff:
		StartConnectAttempt();
		break;

	case EUmWsState::Connecting:
	case EUmWsState::AwaitingAck:
	case EUmWsState::Ready:
		if (!bForce && State == EUmWsState::Ready && Subscriptions.Num() == 0)
		{
			// Токен фиксируется в connection_init на всё время сокета (R1 §2.4 «Аутентификация по WS»): без активных
			// подписок пересоздавать нечего — новые подписки всё равно уйдут после следующего connection_init…
			// но только если сокет пересоздать. Поэтому без force просто закрываемся в Idle: следующий Subscribe()
			// откроет сессию с актуальным токеном.
			RequestClose(UmWsProtocol::CloseNormal, Reason, EAfterClose::Stay);
		}
		else
		{
			RequestClose(UmWsProtocol::CloseNormal, Reason, EAfterClose::ReconnectNow);
		}
		break;

	case EUmWsState::Closing:
		// Уже закрываемся: усиливаем намерение до «переподключиться».
		AfterClose = EAfterClose::ReconnectNow;
		break;
	}
}

void FUmGraphQLWsClient::Terminate(const FString& Reason)
{
	check(IsInGameThread());
	Subscriptions.Empty();
	ReconnectAttempt = 0;
	bClientBugRetryUsed = false;
	BackoffDeadline = -1.0;

	switch (State)
	{
	case EUmWsState::Idle:
	case EUmWsState::Failed:
		ClearSessionTimers();
		SetState(EUmWsState::Idle);
		break;
	case EUmWsState::Backoff:
		ClearSessionTimers();
		SetState(EUmWsState::Idle);
		break;
	case EUmWsState::Closing:
		AfterClose = EAfterClose::Stay;
		break;
	default:
		RequestClose(UmWsProtocol::CloseNormal, Reason, EAfterClose::Stay);
		break;
	}
}

void FUmGraphQLWsClient::RequestClose(int32 Code, const FString& Reason, EAfterClose InAfterClose)
{
	ClearSessionTimers();
	AfterClose = InAfterClose;
	SetState(EUmWsState::Closing);
	// OnClosed придёт асинхронно (LWS — из GameThreadTick; фейк — синхронно при bAutoEmitClosedOnClose) → HandleDisconnect.
	Socket->Close(Code, Reason);
}

void FUmGraphQLWsClient::ScheduleBackoff()
{
	++ReconnectAttempt;
	if (ReconnectAttempt > Config.ReconnectMaxAttempts)
	{
		FailPermanently(TEXT("reconnect attempts exhausted"));
		return;
	}

	// 1 с × 2^(n−1): 1, 2, 4, 8, 16 с (SubscriptionHandler.ts:98-101 — R1 §2.15) + jitter ±ReconnectJitterFraction.
	const int32 Exponent = FMath::Clamp(ReconnectAttempt - 1, 0, 30);
	const double BaseMs = static_cast<double>(Config.ReconnectBaseDelayMs) * static_cast<double>(1LL << Exponent);
	const double CappedMs = FMath::Min(BaseMs, static_cast<double>(Config.ReconnectMaxDelayMs));
	const double Jitter = 1.0 + FMath::FRandRange(-Config.ReconnectJitterFraction, Config.ReconnectJitterFraction);
	const double DelaySec = FMath::Max(0.0, CappedMs * Jitter / 1000.0);

	UE_LOG(LogUmNet, Log, TEXT("[GQL-WS] backoff attempt %d/%d in %.2fs (last close %d %s)"),
		ReconnectAttempt, Config.ReconnectMaxAttempts, DelaySec, LastDisconnect.Code, *LastDisconnect.Reason);

	ClearSessionTimers();
	BackoffDeadline = Now() + DelaySec;
	SetState(EUmWsState::Backoff);
}

void FUmGraphQLWsClient::FailPermanently(const TCHAR* Why)
{
	UE_LOG(LogUmNet, Error, TEXT("[GQL-WS] failed: %s (last close %d %s)"), Why, LastDisconnect.Code, *LastDisconnect.Reason);
	ClearSessionTimers();
	BackoffDeadline = -1.0;
	SetState(EUmWsState::Failed);
}

// ---------------------------------------------------------------------------------------------------------------------
// События сокета
// ---------------------------------------------------------------------------------------------------------------------

void FUmGraphQLWsClient::HandleSocketConnected()
{
	if (State != EUmWsState::Connecting)
	{
		UE_LOG(LogUmNet, Warning, TEXT("[GQL-WS] OnConnected in state %s — ignored"), ToString(State));
		return;
	}
	ConnectDeadline = -1.0;

	// connection_init НЕМЕДЛЕННО: окно сервера 3 с, иначе 4408 (server-3ewaJSjp.js:12,42-48 — R1 §2.4; R1 §3 п.7).
	const FString Token = AccessTokenProvider ? AccessTokenProvider() : FString();
	if (Token.IsEmpty())
	{
		UE_LOG(LogUmNet, Warning, TEXT("[GQL-WS] connection_init without access token — guarded subscriptions will fail on subscribe"));
	}
	SetState(EUmWsState::AwaitingAck);
	AckDeadline = Now() + Config.AckTimeoutSec;
	Socket->Send(BuildConnectionInit(Token));
}

void FUmGraphQLWsClient::HandleSocketConnectionError(const FString& Error)
{
	FUmWsDisconnectInfo Info;
	Info.Code = 0;
	Info.Reason = Error;
	Info.bWasClean = false;
	Info.bRequestedByClient = (State == EUmWsState::Closing);
	HandleDisconnect(Info);
}

void FUmGraphQLWsClient::HandleSocketClosed(int32 StatusCode, const FString& Reason, bool bWasClean)
{
	FUmWsDisconnectInfo Info;
	Info.Code = StatusCode;
	Info.Reason = Reason;
	Info.bWasClean = bWasClean;
	Info.bRequestedByClient = (State == EUmWsState::Closing);
	HandleDisconnect(Info);
}

void FUmGraphQLWsClient::HandleDisconnect(const FUmWsDisconnectInfo& Info)
{
	using namespace UmWsProtocol;

	if (State == EUmWsState::Idle || State == EUmWsState::Failed || State == EUmWsState::Backoff)
	{
		// Запоздавшее событие уже отпущенного сокета.
		UE_LOG(LogUmNet, Verbose, TEXT("[GQL-WS] disconnect(%d) in state %s — ignored"), Info.Code, ToString(State));
		return;
	}

	LastDisconnect = Info;
	ClearSessionTimers();
	for (TPair<FString, FSubscription>& Pair : Subscriptions)
	{
		Pair.Value.bActiveInSession = false;
	}

	// 1) Закрытие по нашей инициативе.
	if (State == EUmWsState::Closing)
	{
		switch (AfterClose)
		{
		case EAfterClose::Stay:
			SetState(EUmWsState::Idle);
			break;
		case EAfterClose::ReconnectNow:
			StartConnectAttempt();
			break;
		case EAfterClose::Backoff:
			ScheduleBackoff();
			break;
		}
		return;
	}

	// 2) Закрытие сервером / обрыв — классификация по коду (R1 §2.4 «Close-коды»; R1 §3 п.12; ADR §4.1).
	switch (Info.Code)
	{
	case CloseSubprotocolNotAccepted: // 4406 — конфигурация клиента (не тот сабпротокол), ретрай бессмысленен
		FailPermanently(TEXT("4406 Subprotocol not acceptable — check IUmWebSocket protocol = graphql-transport-ws"));
		return;

	case CloseForbidden: // 4403 — по спецификации отказ auth на init; наш сервер не выдаёт (onConnect не задан), но обрабатываем
		UE_LOG(LogUmNet, Warning, TEXT("[GQL-WS] 4403 Forbidden — token refresh required, then Reconnect()"));
		SetState(EUmWsState::Failed);
		OnAuthRejected.Broadcast(Info);
		return;

	case CloseBadRequest:       // 4400
	case CloseUnauthorized:     // 4401 — subscribe до ack
	case CloseSubscriberExists: // 4409 — дубль id
	case CloseTooManyInit:      // 4429 — второй connection_init
		// Это баг клиента (ADR §4.1): лог Error, один реконнект, при повторе — Failed.
		UE_LOG(LogUmNet, Error, TEXT("[GQL-WS] protocol violation by client: close %d %s"), Info.Code, *Info.Reason);
		if (bClientBugRetryUsed)
		{
			FailPermanently(TEXT("repeated protocol violation"));
			return;
		}
		bClientBugRetryUsed = true;
		ScheduleBackoff();
		return;

	case CloseInitTimeout:  // 4408 — не успели с connection_init (лаг game thread) → обычный backoff
	case CloseInternalError: // 4500
	case CloseGoingAway:    // 1001 — остановка сервера (use/ws.js:98-101)
	case CloseAbnormal:     // 1006 — обрыв без close-frame (в т.ч. terminate() сервера при потере pong-фреймов)
	case CloseNormal:       // 1000 не по нашей инициативе — считаем сетевым событием
	case 0:                 // OnConnectionError
	default:
		ScheduleBackoff();
		return;
	}
}

// ---------------------------------------------------------------------------------------------------------------------
// Входящие сообщения
// ---------------------------------------------------------------------------------------------------------------------

void FUmGraphQLWsClient::HandleSocketMessage(const FString& Message)
{
	using namespace UmWsProtocol;

	TSharedPtr<FJsonObject> Root = FUmGraphQLClient::JsonFromString(Message);
	if (!Root.IsValid())
	{
		UE_LOG(LogUmNet, Warning, TEXT("[GQL-WS] non-JSON message dropped (%d chars)"), Message.Len());
		return;
	}

	FString Type;
	if (!Root->TryGetStringField(TEXT("type"), Type))
	{
		UE_LOG(LogUmNet, Warning, TEXT("[GQL-WS] message without type dropped"));
		return;
	}
	FString Id;
	Root->TryGetStringField(TEXT("id"), Id);

	if (Type == ConnectionAck)
	{
		OnConnectionAck();
	}
	else if (Type == Ping)
	{
		OnPing(Root);
	}
	else if (Type == Pong)
	{
		OnPong();
	}
	else if (Type == Next)
	{
		const TSharedPtr<FJsonObject>* Payload = nullptr;
		Root->TryGetObjectField(TEXT("payload"), Payload);
		OnNext(Id, Payload ? *Payload : TSharedPtr<FJsonObject>());
	}
	else if (Type == Error)
	{
		OnError(Id, Root);
	}
	else if (Type == Complete)
	{
		OnComplete(Id);
	}
	else
	{
		// `ka` — legacy subscriptions-transport-ws, в graphql-ws не существует (R1 §4 п.2). Незнакомое — игнорируем.
		UE_LOG(LogUmNet, Warning, TEXT("[GQL-WS] unknown message type '%s' ignored"), *Type);
	}
}

void FUmGraphQLWsClient::OnConnectionAck()
{
	if (State != EUmWsState::AwaitingAck)
	{
		UE_LOG(LogUmNet, Warning, TEXT("[GQL-WS] connection_ack in state %s — ignored"), ToString(State));
		return;
	}
	AckDeadline = -1.0;
	ReconnectAttempt = 0;
	bClientBugRetryUsed = false;
	SetState(EUmWsState::Ready);

	// Прикладной ping (ADR §4.1: каждые 10 с). WS-ping-фреймы сервера (12 с) libwebsockets отбивает сам; наш JSON-ping —
	// клиентский liveness (R1 §3 п.9; R8 §3.1 п.6). Ack не означает валидность токена (R1 §3 п.10) —
	// это выяснится на первом subscribe.
	if (Config.AppPingIntervalSec > 0.0f)
	{
		NextPingAt = Now() + Config.AppPingIntervalSec;
	}

	ResubscribeAll();
}

void FUmGraphQLWsClient::OnPing(const TSharedPtr<FJsonObject>& Root)
{
	// «A Pong must be sent in response … as soon as possible» — отвечаем в любом состоянии, где сокет открыт.
	const TSharedPtr<FJsonObject>* Payload = nullptr;
	Root->TryGetObjectField(TEXT("payload"), Payload);
	Socket->Send(BuildPong(Payload ? *Payload : TSharedPtr<FJsonObject>()));
}

void FUmGraphQLWsClient::OnPong()
{
	// Pong может быть и unsolicited heartbeat — просто сбрасываем дедлайн.
	PongDeadline = -1.0;
}

void FUmGraphQLWsClient::OnNext(const FString& Id, const TSharedPtr<FJsonObject>& Payload)
{
	FSubscription* Sub = Subscriptions.Find(Id);
	if (!Sub)
	{
		// Спецификация: «be prepared to receive (and ignore) messages for operations … already completed».
		UE_LOG(LogUmNet, Verbose, TEXT("[GQL-WS] next for unknown id %s ignored"), *Id);
		return;
	}

	TSharedPtr<FJsonObject> Data;
	TArray<FUmGraphQLError> Errors;
	if (Payload.IsValid())
	{
		const TSharedPtr<FJsonObject>* DataObject = nullptr;
		if (Payload->TryGetObjectField(TEXT("data"), DataObject) && DataObject)
		{
			Data = *DataObject;
		}
		const TArray<TSharedPtr<FJsonValue>>* ErrorsArray = nullptr;
		if (Payload->TryGetArrayField(TEXT("errors"), ErrorsArray) && ErrorsArray)
		{
			// Ошибка guard'а на subscribe приходит как next{errors} + complete, без extensions.code (R1 §2.4);
			// классификация — по подстрокам сообщения в FUmErrorClassifier (ADR §5.3). Подписка при этом остаётся
			// зарегистрированной: complete от сервера удалит её, а next{errors} на живой подписке — не терминален (F24).
			FUmGraphQLClient::ParseErrorsArray(*ErrorsArray, Errors);
			UE_LOG(LogUmNet, Warning, TEXT("[GQL-WS] next{errors} on %s (%s): %s"), *Id, *Sub->Spec.OperationName,
				Errors.Num() > 0 ? *Errors[0].Message : TEXT(""));
		}
	}

	// Копия колбэка: обработчик может вызвать Unsubscribe(Id) и инвалидировать Sub.
	const TFunction<void(const TSharedPtr<FJsonObject>&, const TArray<FUmGraphQLError>&)> Callback = Sub->Callbacks.OnNext;
	OnSubscriptionNext.Broadcast(Id, Data, Errors);
	if (Callback)
	{
		Callback(Data, Errors);
	}
}

void FUmGraphQLWsClient::OnError(const FString& Id, const TSharedPtr<FJsonObject>& Root)
{
	FSubscription* Found = Subscriptions.Find(Id);
	if (!Found)
	{
		UE_LOG(LogUmNet, Verbose, TEXT("[GQL-WS] error for unknown id %s ignored"), *Id);
		return;
	}
	FSubscription Removed = MoveTemp(*Found);
	Subscriptions.Remove(Id);

	// payload — массив GraphQLFormattedError (валидация документа подписки, «Unable to identify operation» — R1 §2.4).
	TArray<FUmGraphQLError> Errors;
	const TArray<TSharedPtr<FJsonValue>>* ErrorsArray = nullptr;
	if (Root->TryGetArrayField(TEXT("payload"), ErrorsArray) && ErrorsArray)
	{
		FUmGraphQLClient::ParseErrorsArray(*ErrorsArray, Errors);
	}
	else
	{
		const TSharedPtr<FJsonObject>* Single = nullptr;
		if (Root->TryGetObjectField(TEXT("payload"), Single) && Single)
		{
			Errors.Add(FUmGraphQLClient::ParseError(*Single));
		}
	}
	UE_LOG(LogUmNet, Warning, TEXT("[GQL-WS] error on %s (%s): %s"), *Id, *Removed.Spec.OperationName,
		Errors.Num() > 0 ? *Errors[0].Message : TEXT("<empty>"));

	OnSubscriptionError.Broadcast(Id, Errors);
	if (Removed.Callbacks.OnError)
	{
		Removed.Callbacks.OnError(Errors);
	}
}

void FUmGraphQLWsClient::OnComplete(const FString& Id)
{
	FSubscription* Found = Subscriptions.Find(Id);
	if (!Found)
	{
		UE_LOG(LogUmNet, Verbose, TEXT("[GQL-WS] complete for unknown id %s ignored"), *Id);
		return;
	}
	FSubscription Removed = MoveTemp(*Found);
	Subscriptions.Remove(Id);
	UE_LOG(LogUmNet, Log, TEXT("[GQL-WS] complete on %s (%s)"), *Id, *Removed.Spec.OperationName);
	OnSubscriptionComplete.Broadcast(Id);
	if (Removed.Callbacks.OnComplete)
	{
		Removed.Callbacks.OnComplete();
	}
}

// ---------------------------------------------------------------------------------------------------------------------
// Подписки
// ---------------------------------------------------------------------------------------------------------------------

FString FUmGraphQLWsClient::Subscribe(const FUmSubscriptionSpec& Spec, FUmSubscriptionCallbacks Callbacks)
{
	check(IsInGameThread());
	const FString Id = NextSubscriptionId();

	FSubscription& Sub = Subscriptions.Add(Id);
	Sub.Spec = Spec;
	Sub.Callbacks = MoveTemp(Callbacks);

	if (State == EUmWsState::Ready)
	{
		SendSubscribe(Id, Sub);
	}
	else if (State == EUmWsState::Idle || State == EUmWsState::Failed)
	{
		// lazy: true в веб-клиенте (R1 §2.15) — сокет открывается первой подпиской.
		Connect();
	}
	// Connecting/AwaitingAck/Backoff/Closing — subscribe уйдёт в ResubscribeAll() после ack (4401 при subscribe до ack).
	return Id;
}

void FUmGraphQLWsClient::Unsubscribe(const FString& Id)
{
	check(IsInGameThread());
	FSubscription* Found = Subscriptions.Find(Id);
	if (!Found)
	{
		return;
	}
	FSubscription Removed = MoveTemp(*Found);
	Subscriptions.Remove(Id);
	if (State == EUmWsState::Ready && Removed.bActiveInSession)
	{
		Socket->Send(BuildComplete(Id)); // клиент → сервер complete = отписка (R1 §2.4 шаг 6)
	}
}

void FUmGraphQLWsClient::UpdateVariables(const FString& Id, const TSharedPtr<FJsonObject>& NewVariables)
{
	if (FSubscription* Sub = Subscriptions.Find(Id))
	{
		Sub->Spec.Variables = NewVariables;
	}
}

void FUmGraphQLWsClient::SendSubscribe(const FString& Id, FSubscription& Sub)
{
	if (Sub.bSentOnce && Sub.Spec.BuildVariablesForResubscribe)
	{
		// Переподписка с актуальными переменными (since = LastSeq) — ADR §4.1, §5.2; R1 §3 п.11.
		Sub.Spec.Variables = Sub.Spec.BuildVariablesForResubscribe(Sub.Spec.Variables);
	}
	Sub.bSentOnce = true;
	Sub.bActiveInSession = true;
	UE_LOG(LogUmNet, Log, TEXT("[GQL-WS] subscribe %s (%s)"), *Id, *Sub.Spec.OperationName);
	Socket->Send(BuildSubscribe(Id, Sub.Spec));
}

void FUmGraphQLWsClient::ResubscribeAll()
{
	// Колбэк BuildVariablesForResubscribe может обратиться к владельцу, но не должен менять набор подписок;
	// на всякий случай итерируем по снимку ключей.
	TArray<FString> Ids;
	Subscriptions.GetKeys(Ids);
	for (const FString& Id : Ids)
	{
		if (FSubscription* Sub = Subscriptions.Find(Id))
		{
			if (!Sub->bActiveInSession)
			{
				SendSubscribe(Id, *Sub);
			}
		}
	}
}

// ---------------------------------------------------------------------------------------------------------------------
// Тик: таймауты
// ---------------------------------------------------------------------------------------------------------------------

bool FUmGraphQLWsClient::Tick(float /*DeltaSeconds*/)
{
	using namespace UmWsProtocol;
	const double T = Now();

	switch (State)
	{
	case EUmWsState::Connecting:
		if (ConnectDeadline >= 0.0 && T >= ConnectDeadline)
		{
			UE_LOG(LogUmNet, Warning, TEXT("[GQL-WS] connect timeout (%.1fs)"), Config.ConnectTimeoutSec);
			LastDisconnect = FUmWsDisconnectInfo{ 0, TEXT("connect-timeout"), false, true };
			RequestClose(CloseNormal, TEXT("connect-timeout"), EAfterClose::Backoff);
		}
		break;

	case EUmWsState::AwaitingAck:
		if (AckDeadline >= 0.0 && T >= AckDeadline)
		{
			// Клиентский код 4504 «Connection acknowledgement timeout» (R1 §2.4).
			UE_LOG(LogUmNet, Warning, TEXT("[GQL-WS] connection_ack timeout (%.1fs)"), Config.AckTimeoutSec);
			LastDisconnect = FUmWsDisconnectInfo{ CloseAckTimeout, TEXT("ack-timeout"), false, true };
			RequestClose(CloseAckTimeout, TEXT("Connection acknowledgement timeout"), EAfterClose::Backoff);
		}
		break;

	case EUmWsState::Ready:
		if (PongDeadline >= 0.0 && T >= PongDeadline)
		{
			// Ответа на прикладной ping нет — соединение считаем мёртвым (сервер тоже terminate()-ит через ~24 с без pong-фрейма, R1 §2.4).
			UE_LOG(LogUmNet, Warning, TEXT("[GQL-WS] pong timeout (%.1fs)"), Config.AppPongTimeoutSec);
			LastDisconnect = FUmWsDisconnectInfo{ 0, TEXT("pong-timeout"), false, true };
			RequestClose(CloseNormal, TEXT("pong-timeout"), EAfterClose::Backoff);
		}
		else if (NextPingAt >= 0.0 && T >= NextPingAt)
		{
			Socket->Send(BuildPing());
			NextPingAt = T + Config.AppPingIntervalSec;
			if (PongDeadline < 0.0)
			{
				PongDeadline = T + Config.AppPongTimeoutSec;
			}
		}
		break;

	case EUmWsState::Backoff:
		if (BackoffDeadline >= 0.0 && T >= BackoffDeadline)
		{
			BackoffDeadline = -1.0;
			StartConnectAttempt();
		}
		break;

	case EUmWsState::Idle:
	case EUmWsState::Closing:
	case EUmWsState::Failed:
		break;
	}
	return true; // тикер продолжает
}
