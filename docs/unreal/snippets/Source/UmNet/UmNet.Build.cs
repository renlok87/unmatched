// Источник: ADR §3.2 (строка UmNet: PublicDependencyModuleNames), §4.1 (классы и их движковые зависимости).
// Правило ADR §3.2/§4.0: модуль ничего не знает об игре (ни GameState, ни экранов) и не зависит от UmModel.
// Все заголовки модуля экспортируются макросом UMNET_API (генерируется UBT из имени модуля).
//
// Проверка модулей по движку (UE 5.8.2):
//   HTTP          — $UE/Source/Runtime/Online/HTTP/HTTP.Build.cs                (R8 §2.2: FHttpModule, IHttpRequest)
//   WebSockets    — $UE/Source/Runtime/Online/WebSockets/WebSockets.Build.cs    (R8 §2.3: IWebSocket, FLwsWebSocket)
//   Json          — $UE/Source/Runtime/Json/Json.Build.cs                       (FJsonObject, FJsonSerializer)
//   JsonUtilities — $UE/Source/Runtime/JsonUtilities/JsonUtilities.Build.cs     (FJsonObjectConverter — R8 §2.4)
//   DeveloperSettings — $UE/Source/Runtime/DeveloperSettings/DeveloperSettings.Build.cs (UUmNetSettings : UDeveloperSettings)
//   PlatformCrypto — $UE/Plugins/Experimental/PlatformCrypto/Source/PlatformCrypto/PlatformCrypto.Build.cs
//                    (публично тянет PlatformCryptoTypes + PlatformCryptoContext; R8 §2.10)
//   PlatformCryptoContext — FEncryptionContextOpenSSL::Encrypt_AES_256_GCM
//                    ($UE/Plugins/Experimental/PlatformCrypto/Source/PlatformCryptoContext/Public/EncryptionContextOpenSSL.h:189)

using UnrealBuildTool;

public class UmNet : ModuleRules
{
	public UmNet(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",            // UGameInstanceSubsystem (UUmNetSubsystem, UUmAuthSubsystem), FTSTicker
			"HTTP",              // IUmHttpTransport / FUmHttpTransport
			"WebSockets",        // IUmWebSocket / FUmLwsWebSocket
			"Json",              // FUmGraphQLRequest::Variables (TSharedPtr<FJsonObject>)
			"JsonUtilities",     // разбор {data, errors} GraphQL-ответа
			"PlatformCrypto",    // FUmSecureStore_Generic (AES-256-GCM)
			"DeveloperSettings"  // UUmNetSettings
		});

		PrivateDependencyModuleNames.AddRange(new string[]
		{
			// (уточнение к ADR §3.2) ADR указывает «PlatformCryptoOpenSSL в Private», но в 5.8 этот модуль
			// помечен [Obsolete("Deprecated in UE5.6 - Use PlatformCryptoContext instead.")]
			// ($UE/Plugins/Experimental/PlatformCrypto/Source/PlatformCryptoOpenSSL/PlatformCryptoOpenSSL.Build.cs:8).
			// Используем PlatformCryptoContext — он и есть реализация FEncryptionContext (typedef, EncryptionContextOpenSSL.h:379).
			"PlatformCryptoContext"
		});

		if (Target.Platform == UnrealTargetPlatform.Win64)
		{
			// FUmSecureStore_Windows: DPAPI CryptProtectData/CryptUnprotectData (ADR §4.1) — crypt32.lib.
			// PublicSystemLibraries — ModuleRules.cs:1348.
			PublicSystemLibraries.Add("crypt32.lib");
		}

		// Тесты ADR §4.8 (Private/Tests/*.spec.cpp под WITH_DEV_AUTOMATION_TESTS) — отдельного модуля не требуют.
		// TODO(C2-net): включить bEnableExceptions только если базовая реализация JWT/base64url этого потребует (сейчас — нет).
	}
}
