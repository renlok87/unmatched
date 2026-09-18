// UmNetSettings.h — UDeveloperSettings сетевого слоя UmNet.
// Источник: ADR §3.3 (UmNet/Public/UmNetSettings.h), §3.5 (секция [/Script/UmNet.UmNetSettings] в DefaultGame.ini),
// §4.1 (строка UUmNetSettings). Контракт адресов — R1 §2.1, §3 п.2; лимиты/тайминги — R1 §2.4, §2.6, §2.11; R8 §2.2, §2.3.
#pragma once

#include "CoreMinimal.h"
#include "Engine/DeveloperSettings.h"
#include "UmNetSettings.generated.h"

/**
 * Настройки сети (Project Settings → Game → Unmatched Net). Значения по умолчанию совпадают с ADR §3.5.
 * Имя секции ini выводится из имени класса и модуля: [/Script/UmNet.UmNetSettings].
 */
UCLASS(Config = Game, DefaultConfig, meta = (DisplayName = "Unmatched Net"))
class UMNET_API UUmNetSettings : public UDeveloperSettings
{
	GENERATED_BODY()

public:
	/** Удобный доступ: CDO с настройками из ini. */
	static const UUmNetSettings& Get()
	{
		const UUmNetSettings* Settings = GetDefault<UUmNetSettings>();
		check(Settings);
		return *Settings;
	}

	//~ UDeveloperSettings
	virtual FName GetCategoryName() const override { return TEXT("Game"); }

	// ---------------------------------------------------------------- Адреса (R1 §2.1; R8 §3.1 п.2)

	/** Базовый URL бэкенда без пути: http://localhost:3000 (R1 §2.1: порт PORT=3000, глобального префикса нет). */
	UPROPERTY(Config, EditAnywhere, Category = "Endpoints")
	FString ApiBaseUrl = TEXT("http://localhost:3000");

	/** Путь GraphQL; общий для HTTP и WS (R1 §2.1: GRAPHQL_PATH кодом не читается, дефолт @nestjs/apollo — /graphql). */
	UPROPERTY(Config, EditAnywhere, Category = "Endpoints")
	FString GraphQLPath = TEXT("/graphql");

	/** http(s)://host:port/graphql для queries/mutations. */
	FString GetHttpUrl() const
	{
		FString Base = ApiBaseUrl;
		Base.RemoveFromEnd(TEXT("/"));
		FString Path = GraphQLPath;
		if (!Path.StartsWith(TEXT("/")))
		{
			Path = TEXT("/") + Path;
		}
		return Base + Path;
	}

	/**
	 * ws(s)://host:port/graphql для подписок: схема выводится из ApiBaseUrl (http→ws, https→wss).
	 * R8 §2.3 (LwsWebSocket.cpp:736-759): допустимы ws, wss, wss+insecure (self-signed dev — B20); заголовок Authorization
	 * на handshake сервером не читается (R1 §2.4) — токен уходит в connection_init.
	 */
	FString GetWsUrl() const
	{
		FString Url = GetHttpUrl();
		if (Url.StartsWith(TEXT("https://"), ESearchCase::IgnoreCase))
		{
			Url = TEXT("wss://") + Url.RightChop(8);
		}
		else if (Url.StartsWith(TEXT("http://"), ESearchCase::IgnoreCase))
		{
			Url = TEXT("ws://") + Url.RightChop(7);
		}
		return Url;
	}

	// ---------------------------------------------------------------- HTTP (R8 §2.2: HttpTotalTimeout по умолчанию 0 → задаём SetTimeout в коде)

	/** Тотальный таймаут одного HTTP-запроса; используется как FUmGraphQLRequest::TimeoutSec по умолчанию. */
	UPROPERTY(Config, EditAnywhere, Category = "HTTP", meta = (ClampMin = "1.0", ClampMax = "120.0"))
	float HttpTimeoutSec = 15.f;

	/** FUmRetryPolicy: число попыток для query при классе Network (R7 §2.2 retry-link: attempts.max 3). */
	UPROPERTY(Config, EditAnywhere, Category = "HTTP", meta = (ClampMin = "1", ClampMax = "10"))
	int32 RetryMaxAttempts = 3;

	/** FUmRetryPolicy: базовая задержка, мс (R7 §2.2: delay.initial 300). */
	UPROPERTY(Config, EditAnywhere, Category = "HTTP", meta = (ClampMin = "0"))
	int32 RetryBaseDelayMs = 300;

	/** FUmRetryPolicy: потолок задержки, мс (R7 §2.2: delay.max 10000). */
	UPROPERTY(Config, EditAnywhere, Category = "HTTP", meta = (ClampMin = "0"))
	int32 RetryMaxDelayMs = 10000;

	// ---------------------------------------------------------------- WebSocket (R1 §2.4; R8 §2.3; К1 §3.3.4)

	/** Ожидание connection_ack после connection_init (сервер ждёт init 3 с → 4408; ack приходит всегда — R1 §2.4). */
	UPROPERTY(Config, EditAnywhere, Category = "WebSocket", meta = (ClampMin = "1.0"))
	float WsConnectionAckTimeoutSec = 5.f;

	/** Максимум попыток реконнекта с backoff (веб-эталон 5 — R7 §2.7). */
	UPROPERTY(Config, EditAnywhere, Category = "WebSocket", meta = (ClampMin = "0"))
	int32 WsReconnectMaxAttempts = 5;

	/** Базовая задержка backoff: BaseDelay × 2^(n−1) (R7 §2.7 SubscriptionHandler). */
	UPROPERTY(Config, EditAnywhere, Category = "WebSocket", meta = (ClampMin = "100"))
	int32 WsReconnectBaseDelayMs = 1000;

	/** Прикладной {"type":"ping"} graphql-transport-ws (LWS ping/pong по умолчанию выключен — R8 §2.3). */
	UPROPERTY(Config, EditAnywhere, Category = "WebSocket", meta = (ClampMin = "0"))
	int32 WsAppPingIntervalSec = 10;

	/** IWebSocket::SetTextMessageMemoryLimit; дефолт движка 1 МБ (R8 §2.3), ADR §3.5 — 8 МБ. */
	UPROPERTY(Config, EditAnywhere, Category = "WebSocket", meta = (ClampMin = "1048576"))
	int64 WsTextMessageMemoryLimit = 8 * 1024 * 1024;

	// ---------------------------------------------------------------- Auth (R1 §2.6, §3 п.14; ADR §5.3)

	/** Проактивный refresh за N секунд до exp access-JWT (единственный надёжный путь в production — R1 §4.6). */
	UPROPERTY(Config, EditAnywhere, Category = "Auth", meta = (ClampMin = "30"))
	int32 ProactiveRefreshLeadSec = 300;

	/** Период проверки exp тикером FTSTicker (ADR §4.1: раз в 15 с). */
	UPROPERTY(Config, EditAnywhere, Category = "Auth", meta = (ClampMin = "1"))
	int32 ProactiveRefreshCheckIntervalSec = 15;

	/** Окно ±N секунд вокруг exp, в котором класс Opaque трактуется как Auth один раз (ADR §5.3: ±2 мин). */
	UPROPERTY(Config, EditAnywhere, Category = "Auth", meta = (ClampMin = "0"))
	int32 OpaqueAuthWindowSec = 120;

	/** Имя слота IUmSecureStore (файл в Saved/UmAuth/). */
	UPROPERTY(Config, EditAnywhere, Category = "Auth")
	FString SecureStoreSlotName = TEXT("session");

	// ---------------------------------------------------------------- Лимиты (R1 §2.11; ADR §5.4)

	/** Клиентский token bucket по объявленным @Throttle; сервер лимиты сейчас не применяет (ThrottlerGuard не привязан — R1 §4.7), но проектируем «как будто включены». */
	UPROPERTY(Config, EditAnywhere, Category = "Limits")
	bool bEnableClientRateLimits = true;
};
