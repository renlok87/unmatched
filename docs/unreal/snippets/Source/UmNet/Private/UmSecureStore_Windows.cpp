// UmSecureStore_Windows.cpp — DPAPI (CryptProtectData / CryptUnprotectData) для refresh-токена.
// Источник: ADR §4.1 («Windows — DPAPI CryptProtectData (#if PLATFORM_WINDOWS)»), R8 §2.10 («обёрток DPAPI в Engine/Source/Runtime нет»),
// R8 §3.5 п.2. Образец подключения Windows-заголовков — $UE/Source/Runtime/Online/SSL/Private/Windows/WindowsPlatformSslCertificateManager.cpp:9-20
// (Windows/AllowWindowsPlatformTypes.h → THIRD_PARTY_INCLUDES_START → <wincrypt.h> → THIRD_PARTY_INCLUDES_END → HideWindowsPlatformTypes.h).
#include "UmSecureStore.h"

#if PLATFORM_WINDOWS

#include "HAL/UnrealMemory.h"
#include "Logging/LogMacros.h"

#include "Windows/WindowsHWrapper.h"
#include "Windows/AllowWindowsPlatformTypes.h"
THIRD_PARTY_INCLUDES_START
#include <wincrypt.h>
THIRD_PARTY_INCLUDES_END
#include "Windows/HideWindowsPlatformTypes.h"

// Линковка crypt32.lib. (уточнение к ADR) В UmNet.Build.cs для Win64 добавить PublicSystemLibraries.Add("crypt32.lib");
// pragma ниже — страховка для MSVC, чтобы сниппет собирался и без правки Build.cs.
#if defined(_MSC_VER)
#pragma comment(lib, "crypt32.lib")
#endif

DEFINE_LOG_CATEGORY_STATIC(LogUmSecureStoreWin, Log, All);

namespace UmSecureStoreWindowsPrivate
{
	// Дополнительная энтропия DPAPI: не секрет, но не даёт расшифровать файл произвольным процессом того же пользователя
	// простым вызовом CryptUnprotectData без знания константы (ограниченная защита, честно).
	static const uint8 Entropy[] = { 'U','m','S','e','c','u','r','e','S','t','o','r','e','.','v','1' };

	static const WCHAR* Description = L"Unmatched session";
}

FUmSecureStore_Windows::FUmSecureStore_Windows(const FString& InSlotName)
	: FilePath(FUmSecureStoreCommon::MakeFilePath(InSlotName, TEXT(".dpapi")))
{
}

bool FUmSecureStore_Windows::Save(const FUmStoredSession& Session)
{
	using namespace UmSecureStoreWindowsPrivate;

	TArray<uint8> Plain;
	if (!FUmSecureStoreCommon::SerializeSession(Session, Plain))
	{
		return false;
	}

	DATA_BLOB In;
	In.pbData = Plain.GetData();
	In.cbData = static_cast<DWORD>(Plain.Num());

	DATA_BLOB EntropyBlob;
	EntropyBlob.pbData = const_cast<BYTE*>(Entropy);
	EntropyBlob.cbData = static_cast<DWORD>(sizeof(Entropy));

	DATA_BLOB Out;
	FMemory::Memzero(&Out, sizeof(Out));

	// CRYPTPROTECT_UI_FORBIDDEN — никаких диалогов; область по умолчанию — текущий пользователь (без CRYPTPROTECT_LOCAL_MACHINE).
	const BOOL bOk = ::CryptProtectData(&In, Description, &EntropyBlob, nullptr, nullptr, CRYPTPROTECT_UI_FORBIDDEN, &Out);
	FUmSecureStoreCommon::SecureZero(Plain);

	if (!bOk || Out.pbData == nullptr)
	{
		UE_LOG(LogUmSecureStoreWin, Error, TEXT("CryptProtectData failed: 0x%08X"), static_cast<uint32>(::GetLastError()));
		return false;
	}

	TArray<uint8> File;
	File.Append(Out.pbData, static_cast<int32>(Out.cbData));
	::LocalFree(Out.pbData);

	const bool bWritten = FUmSecureStoreCommon::WriteFile(FilePath, File);
	UE_LOG(LogUmSecureStoreWin, Log, TEXT("DPAPI store: save %s -> %s"), *FilePath, bWritten ? TEXT("ok") : TEXT("FAILED"));
	return bWritten;
}

bool FUmSecureStore_Windows::Load(FUmStoredSession& OutSession)
{
	using namespace UmSecureStoreWindowsPrivate;

	TArray<uint8> File;
	if (!FUmSecureStoreCommon::ReadFile(FilePath, File) || File.Num() == 0)
	{
		return false;
	}

	DATA_BLOB In;
	In.pbData = File.GetData();
	In.cbData = static_cast<DWORD>(File.Num());

	DATA_BLOB EntropyBlob;
	EntropyBlob.pbData = const_cast<BYTE*>(Entropy);
	EntropyBlob.cbData = static_cast<DWORD>(sizeof(Entropy));

	DATA_BLOB Out;
	FMemory::Memzero(&Out, sizeof(Out));

	const BOOL bOk = ::CryptUnprotectData(&In, nullptr, &EntropyBlob, nullptr, nullptr, CRYPTPROTECT_UI_FORBIDDEN, &Out);
	if (!bOk || Out.pbData == nullptr)
	{
		// Другой пользователь ОС / другая машина / повреждение — файл бесполезен.
		UE_LOG(LogUmSecureStoreWin, Warning, TEXT("CryptUnprotectData failed: 0x%08X; discarding %s"),
			static_cast<uint32>(::GetLastError()), *FilePath);
		Clear();
		return false;
	}

	TArray<uint8> Plain;
	Plain.Append(Out.pbData, static_cast<int32>(Out.cbData));
	FMemory::Memzero(Out.pbData, Out.cbData);
	::LocalFree(Out.pbData);

	const bool bParsed = FUmSecureStoreCommon::DeserializeSession(Plain, OutSession);
	FUmSecureStoreCommon::SecureZero(Plain);
	return bParsed;
}

void FUmSecureStore_Windows::Clear()
{
	FUmSecureStoreCommon::DeleteFile(FilePath);
}

#endif // PLATFORM_WINDOWS
