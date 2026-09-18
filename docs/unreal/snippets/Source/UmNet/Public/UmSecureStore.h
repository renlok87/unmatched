// UmSecureStore.h — защищённое хранение refresh-токена и идентификации пользователя.
// Источник: ADR §4.1 (строка IUmSecureStore / FUmSecureStore_Windows / FUmSecureStore_Generic), §5.3 («access — только в памяти;
// refresh — IUmSecureStore»); R8 §2.10 (USaveGame пишет .sav без шифрования; FAES — ECB, не использовать; PlatformCrypto AES-256-GCM;
// обёрток DPAPI/Keychain в движке нет), R8 §3.5; R1 §3 п.13.
// (уточнение к ADR) В ADR файл называется Auth/IUmSecureStore.h; в сниппетах группы — UmSecureStore.h (без подпапки).
#pragma once

#include "CoreMinimal.h"
#include "Templates/SharedPointer.h"

/**
 * Что сохраняется между запусками. Access-токен НЕ сохраняется (живёт 1 ч, R1 §2.5; при старте всегда делается refresh).
 * UserId — из AuthResponseDto.user.id / me.id (единственный источник userId — R7 §3 п.6, ADR §4.1).
 */
struct UMNET_API FUmStoredSession
{
	FString RefreshToken;
	FString UserId;
	FString Email;
	FString Username;

	bool IsValid() const { return !RefreshToken.IsEmpty(); }
};

/**
 * Интерфейс хранилища. Все вызовы — синхронные, на game thread (объём — сотни байт).
 * Реализации выбираются FUmSecureStoreFactory::CreateForPlatform().
 */
class UMNET_API IUmSecureStore
{
public:
	virtual ~IUmSecureStore() = default;

	/** Сохранить сессию; false — ошибка шифрования/записи (сессия останется только в памяти). */
	virtual bool Save(const FUmStoredSession& Session) = 0;

	/** Загрузить; false — файла нет, повреждён, не расшифровывается (другой пользователь ОС/устройство). */
	virtual bool Load(FUmStoredSession& OutSession) = 0;

	/** Удалить файл сессии (logout, SessionLost). */
	virtual void Clear() = 0;

	/** Для логов: "DPAPI", "AES-256-GCM(DeviceId)". */
	virtual FString GetBackendName() const = 0;
};

/** Общие для реализаций утилиты: путь к файлу и (де)сериализация FUmStoredSession в JSON UTF-8. */
class UMNET_API FUmSecureStoreCommon
{
public:
	/** <ProjectSavedDir>/UmAuth/<SlotName>.<Ext> — рядом с SaveGames, но своим форматом (R8 §2.10: путь FGenericSaveGameSystem). */
	static FString MakeFilePath(const FString& SlotName, const TCHAR* Extension);

	/** FUmStoredSession → UTF-8 JSON {refreshToken,userId,email,username}. */
	static bool SerializeSession(const FUmStoredSession& Session, TArray<uint8>& OutBytes);

	/** UTF-8 JSON → FUmStoredSession. */
	static bool DeserializeSession(const TArray<uint8>& Bytes, FUmStoredSession& OutSession);

	static bool WriteFile(const FString& Path, const TArray<uint8>& Bytes);
	static bool ReadFile(const FString& Path, TArray<uint8>& OutBytes);
	static void DeleteFile(const FString& Path);

	/** Затирание буфера с секретом перед освобождением. */
	static void SecureZero(TArray<uint8>& Bytes);
};

#if PLATFORM_WINDOWS
/**
 * Windows: DPAPI CryptProtectData/CryptUnprotectData с флагом CRYPTPROTECT_UI_FORBIDDEN и фиксированной энтропией приложения.
 * Ключ привязан к учётной записи Windows — файл не читается другим пользователем/на другой машине (что и требуется).
 * Реализация — UmSecureStore_Windows.cpp (Windows/AllowWindowsPlatformTypes.h + <wincrypt.h>, линковка crypt32.lib).
 */
class UMNET_API FUmSecureStore_Windows final : public IUmSecureStore
{
public:
	explicit FUmSecureStore_Windows(const FString& InSlotName);

	virtual bool Save(const FUmStoredSession& Session) override;
	virtual bool Load(FUmStoredSession& OutSession) override;
	virtual void Clear() override;
	virtual FString GetBackendName() const override { return TEXT("DPAPI"); }

private:
	FString FilePath;
};
#endif // PLATFORM_WINDOWS

/**
 * Прочие платформы (и fallback): PlatformCrypto FEncryptionContext::Encrypt_AES_256_GCM с случайным 12-байтным nonce
 * на каждую запись; ключ = SHA-256(Salt ‖ FPlatformMisc::GetDeviceId() [‖ GetLoginId()]) (R8 §2.10, §3.5).
 * Честно: это обфускация с привязкой к устройству, а не платформенное хранилище (ADR §4.1). TODO: Keychain (iOS/macOS),
 * Keystore (Android) — в отдельных cpp под #if PLATFORM_* при выходе на эти платформы (ADR §9.2 — v2).
 */
class UMNET_API FUmSecureStore_Generic final : public IUmSecureStore
{
public:
	explicit FUmSecureStore_Generic(const FString& InSlotName);

	virtual bool Save(const FUmStoredSession& Session) override;
	virtual bool Load(FUmStoredSession& OutSession) override;
	virtual void Clear() override;
	virtual FString GetBackendName() const override { return TEXT("AES-256-GCM(DeviceId)"); }

private:
	/** 32 байта из SHA-256 (PlatformCrypto FSHA256Hasher). false — нет ни DeviceId, ни LoginId. */
	bool DeriveKey(TArray<uint8>& OutKey) const;

	FString FilePath;
};

/** Фабрика: Windows → DPAPI, иначе Generic. Слот — UUmNetSettings::SecureStoreSlotName. */
class UMNET_API FUmSecureStoreFactory
{
public:
	static TSharedPtr<IUmSecureStore> CreateForPlatform(const FString& SlotName);
};
