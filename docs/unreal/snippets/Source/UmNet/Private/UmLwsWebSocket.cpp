// UmNet/Private/UmLwsWebSocket.cpp
//
// FUmLwsWebSocket — обёртка IWebSocket (модуль WebSockets, R8 §2.3) и FUmFakeWebSocket для тестов.

#include "UmWebSocket.h"

#include "IWebSocket.h"
#include "Misc/CoreMisc.h"
#include "UmHttpTransport.h" // LogUmNet
#include "WebSocketsModule.h"

// ---------------------------------------------------------------------------------------------------------------------
// FUmLwsWebSocket
// ---------------------------------------------------------------------------------------------------------------------

FUmLwsWebSocket::FUmLwsWebSocket(const FString& InUrl, const FString& InProtocol, const TMap<FString, FString>& InUpgradeHeaders)
	: Url(InUrl)
	, Protocol(InProtocol)
	, UpgradeHeaders(InUpgradeHeaders)
{
}

FUmLwsWebSocket::~FUmLwsWebSocket()
{
	if (Inner.IsValid())
	{
		UnbindEvents(Inner.ToSharedRef());
		if (Inner->IsConnected())
		{
			Inner->Close(1000, TEXT("client-destroyed"));
		}
		Inner.Reset();
	}
}

void FUmLwsWebSocket::BindEvents(const TSharedRef<IWebSocket>& Socket)
{
	// Биндим ДО Connect(): иначе OnMessage никогда не сработает (LwsWebSocket.h:327-341; R8 §3.1 п.4).
	// AddSP — делегат сам отвяжется, если обёртка уничтожена (события LWS приходят асинхронно из GameThreadTick).
	Socket->OnConnected().AddSP(this, &FUmLwsWebSocket::HandleConnected);
	Socket->OnConnectionError().AddSP(this, &FUmLwsWebSocket::HandleConnectionError);
	Socket->OnClosed().AddSP(this, &FUmLwsWebSocket::HandleClosed);
	Socket->OnMessage().AddSP(this, &FUmLwsWebSocket::HandleMessage);
}

void FUmLwsWebSocket::UnbindEvents(const TSharedRef<IWebSocket>& Socket)
{
	Socket->OnConnected().RemoveAll(this);
	Socket->OnConnectionError().RemoveAll(this);
	Socket->OnClosed().RemoveAll(this);
	Socket->OnMessage().RemoveAll(this);
}

void FUmLwsWebSocket::Connect()
{
	check(IsInGameThread()); // FWebSocketsModule::Get() — check(IsInGameThread()) (WebSocketsModule.cpp:77-86)

	if (Inner.IsValid())
	{
		if (Inner->IsConnected())
		{
			UE_LOG(LogUmNet, Warning, TEXT("[WS] Connect() while already connected — ignored (%s)"), *Url);
			return;
		}
		// Старый сокет (закрытый или ещё финализирующийся) отвязываем (RemoveAll → его запоздавшие события до нас
		// не дойдут) и отпускаем: менеджер LWS доведёт его до конца сам (LwsWebSocket.cpp:625-648).
		// Generation — только для логов.
		UnbindEvents(Inner.ToSharedRef());
		Inner.Reset();
	}

	++Generation;

	// WebSocketsModule.h:72 — CreateWebSocket(const FString& Url, const FString& Protocol, const TMap<FString,FString>& UpgradeHeaders).
	TSharedRef<IWebSocket> Socket = FWebSocketsModule::Get().CreateWebSocket(Url, Protocol, UpgradeHeaders);
	if (TextMessageMemoryLimitOverride > 0)
	{
		Socket->SetTextMessageMemoryLimit(TextMessageMemoryLimitOverride); // IWebSocket.h:49
	}
	Inner = Socket;
	BindEvents(Socket);

	UE_LOG(LogUmNet, Log, TEXT("[WS] connecting to %s (protocol=%s, gen=%u)"), *Url, *Protocol, Generation);
	Socket->Connect(); // IWebSocket.h:16
}

void FUmLwsWebSocket::Close(int32 Code, const FString& Reason)
{
	check(IsInGameThread());
	if (!Inner.IsValid())
	{
		return;
	}
	UE_LOG(LogUmNet, Log, TEXT("[WS] close(%d, %s)"), Code, *Reason);
	// IWebSocket.h:23. Для ещё не подключённого сокета LWS тоже отработает закрытие и пришлёт OnClosed/OnConnectionError.
	Inner->Close(Code, Reason);
}

bool FUmLwsWebSocket::IsConnected() const
{
	// IWebSocket::IsConnected() не const в интерфейсе (IWebSocket.h:28); TSharedPtr::operator-> const возвращает
	// неконстантный указатель, поэтому вызов из const-метода обёртки корректен.
	return Inner.IsValid() && Inner->IsConnected();
}

bool FUmLwsWebSocket::Send(const FString& Text)
{
	if (!IsConnected())
	{
		UE_LOG(LogUmNet, Verbose, TEXT("[WS] Send() dropped — not connected"));
		return false;
	}
	Inner->Send(Text); // IWebSocket.h:34 — UTF-8 текстовый фрейм
	return true;
}

void FUmLwsWebSocket::HandleConnected()
{
	UE_LOG(LogUmNet, Log, TEXT("[WS] connected (gen=%u)"), Generation);
	OnConnected.Broadcast();
}

void FUmLwsWebSocket::HandleConnectionError(const FString& Error)
{
	// «Invalid Domain» — отказ allowlist'а [Online.HttpManager] (LwsWebSocket.cpp:112-125); «Bad protocol» — схема URL.
	UE_LOG(LogUmNet, Warning, TEXT("[WS] connection error: %s (gen=%u)"), *Error, Generation);
	OnConnectionError.Broadcast(Error);
}

void FUmLwsWebSocket::HandleClosed(int32 StatusCode, const FString& Reason, bool bWasClean)
{
	UE_LOG(LogUmNet, Log, TEXT("[WS] closed code=%d clean=%d reason=%s (gen=%u)"), StatusCode, bWasClean ? 1 : 0, *Reason, Generation);
	OnClosed.Broadcast(StatusCode, Reason, bWasClean);
}

void FUmLwsWebSocket::HandleMessage(const FString& Message)
{
	OnMessage.Broadcast(Message);
}

// ---------------------------------------------------------------------------------------------------------------------
// FUmFakeWebSocket
// ---------------------------------------------------------------------------------------------------------------------

void FUmFakeWebSocket::Connect()
{
	++ConnectCount;
	bConnecting = true;
	if (bAutoConnect)
	{
		SimulateConnected();
	}
}

void FUmFakeWebSocket::Close(int32 Code, const FString& Reason)
{
	LastCloseCode = Code;
	LastCloseReason = Reason;
	const bool bWasOpen = bConnected || bConnecting;
	bConnected = false;
	bConnecting = false;
	if (bAutoEmitClosedOnClose && bWasOpen)
	{
		OnClosed.Broadcast(Code, Reason, true);
	}
}

bool FUmFakeWebSocket::Send(const FString& Text)
{
	if (!bConnected)
	{
		return false;
	}
	SentMessages.Add(Text);
	return true;
}

void FUmFakeWebSocket::SimulateConnected()
{
	bConnecting = false;
	bConnected = true;
	OnConnected.Broadcast();
}

void FUmFakeWebSocket::SimulateConnectionError(const FString& Error)
{
	bConnecting = false;
	bConnected = false;
	OnConnectionError.Broadcast(Error);
}

void FUmFakeWebSocket::SimulateClosed(int32 Code, const FString& Reason, bool bWasClean)
{
	bConnecting = false;
	bConnected = false;
	OnClosed.Broadcast(Code, Reason, bWasClean);
}

void FUmFakeWebSocket::SimulateMessage(const FString& Message)
{
	OnMessage.Broadcast(Message);
}

void FUmFakeWebSocket::ResetLog()
{
	ConnectCount = 0;
	LastCloseCode = 0;
	LastCloseReason.Reset();
	SentMessages.Reset();
}
