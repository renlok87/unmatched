// UmSecureStore_Generic.cpp — общие утилиты, фабрика и реализация AES-256-GCM через PlatformCrypto.
// Источник: ADR §4.1 (IUmSecureStore), R8 §2.10 (Encrypt_AES_256_GCM(Plaintext, Key, Nonce, OutAuthTag, OutResult) —
// EncryptionContextOpenSSL.h:189-201), R8 §3.5 п.2 (случайный nonce на запись, ключ на устройстве, не FAES).
#include "UmSecureStore.h"

#include "Containers/StringConv.h"
#include "Dom/JsonObject.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformMisc.h"
#include "HAL/PlatformProcess.h"
#include "HAL/UnrealMemory.h"
#include "Logging/LogMacros.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Policies/CondensedJsonPrintPolicy.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

// Плагин PlatformCrypto (включён в .uproject — ADR §3.1; зависимость модуля — ADR §3.2).
// IPlatformCrypto::Get().CreateContext() → TUniquePtr<FEncryptionContext> (typedef FEncryptionContextOpenSSL, EncryptionContextOpenSSL.h:379).
#include "IPlatformCrypto.h"
#include "PlatformCryptoIncludes.h"

DEFINE_LOG_CATEGORY_STATIC(LogUmSecureStore, Log, All);

namespace UmSecureStorePrivate
{
	// Формат файла: magic(4) | version(1) | nonce(12) | tag(16) | ciphertext(N).
	static const uint8 Magic[4] = { 'U', 'M', 'S', '1' };
	static constexpr uint8 Version = 1;
	static constexpr int32 NonceLen = 12; // стандартный размер nonce GCM
	static constexpr int32 TagLen = 16;   // размер auth tag, который возвращает OpenSSL EVP GCM
	static constexpr int32 KeyLen = 32;   // AES-256

	// Соль приложения: делает ключ отличным от ключей других проектов на том же устройстве. Не секрет (лежит в бинарнике).
	static const ANSICHAR* KeySalt = "Unmatched.UmSecureStore.v1|";
}

// ------------------------------------------------------------------------------------------------ Common

FString FUmSecureStoreCommon::MakeFilePath(const FString& SlotName, const TCHAR* Extension)
{
	const FString Dir = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("UmAuth"));
	return FPaths::Combine(Dir, SlotName + Extension);
}

bool FUmSecureStoreCommon::SerializeSession(const FUmStoredSession& Session, TArray<uint8>& OutBytes)
{
	TSharedPtr<FJsonObject> Json = MakeShared<FJsonObject>();
	Json->SetStringField(TEXT("refreshToken"), Session.RefreshToken);
	Json->SetStringField(TEXT("userId"), Session.UserId);
	Json->SetStringField(TEXT("email"), Session.Email);
	Json->SetStringField(TEXT("username"), Session.Username);

	FString Text;
	TSharedRef<TJsonWriter<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>> Writer =
		TJsonWriterFactory<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>::Create(&Text);
	if (!FJsonSerializer::Serialize(Json, Writer))
	{
		return false;
	}

	auto Utf8 = StringCast<UTF8CHAR>(*Text, Text.Len());
	OutBytes.SetNumUninitialized(Utf8.Length());
	FMemory::Memcpy(OutBytes.GetData(), Utf8.Get(), Utf8.Length());
	return true;
}

bool FUmSecureStoreCommon::DeserializeSession(const TArray<uint8>& Bytes, FUmStoredSession& OutSession)
{
	if (Bytes.Num() == 0)
	{
		return false;
	}

	auto Conv = StringCast<TCHAR>(reinterpret_cast<const UTF8CHAR*>(Bytes.GetData()), Bytes.Num());
	const FString Text = FString::ConstructFromPtrSize(Conv.Get(), Conv.Length());

	TSharedPtr<FJsonObject> Json;
	TSharedRef<TJsonReader<TCHAR>> Reader = TJsonReaderFactory<TCHAR>::Create(Text);
	if (!FJsonSerializer::Deserialize(Reader, Json) || !Json.IsValid())
	{
		return false;
	}

	OutSession = FUmStoredSession();
	Json->TryGetStringField(TEXT("refreshToken"), OutSession.RefreshToken);
	Json->TryGetStringField(TEXT("userId"), OutSession.UserId);
	Json->TryGetStringField(TEXT("email"), OutSession.Email);
	Json->TryGetStringField(TEXT("username"), OutSession.Username);
	return OutSession.IsValid();
}

bool FUmSecureStoreCommon::WriteFile(const FString& Path, const TArray<uint8>& Bytes)
{
	const FString Dir = FPaths::GetPath(Path);
	IFileManager::Get().MakeDirectory(*Dir, /*Tree*/ true);
	return FFileHelper::SaveArrayToFile(Bytes, *Path);
}

bool FUmSecureStoreCommon::ReadFile(const FString& Path, TArray<uint8>& OutBytes)
{
	if (!IFileManager::Get().FileExists(*Path))
	{
		return false;
	}
	return FFileHelper::LoadFileToArray(OutBytes, *Path);
}

void FUmSecureStoreCommon::DeleteFile(const FString& Path)
{
	if (IFileManager::Get().FileExists(*Path))
	{
		IFileManager::Get().Delete(*Path, /*RequireExists*/ false, /*EvenReadOnly*/ true, /*Quiet*/ true);
	}
}

void FUmSecureStoreCommon::SecureZero(TArray<uint8>& Bytes)
{
	if (Bytes.Num() > 0)
	{
		FMemory::Memzero(Bytes.GetData(), Bytes.Num());
	}
	Bytes.Empty();
}

// ------------------------------------------------------------------------------------------------ Generic (AES-256-GCM)

FUmSecureStore_Generic::FUmSecureStore_Generic(const FString& InSlotName)
	: FilePath(FUmSecureStoreCommon::MakeFilePath(InSlotName, TEXT(".gcm")))
{
}

bool FUmSecureStore_Generic::DeriveKey(TArray<uint8>& OutKey) const
{
	using namespace UmSecureStorePrivate;

	// R8 §3.5: «ключ — на устройстве». GetDeviceId может быть пуст (GET_DEVICE_ID_UNAVAILABLE, GenericPlatformMisc.h:680-690) —
	// тогда LoginId; последний fallback — имя машины + пользователя (слабее, но детерминированно).
	FString Material = FPlatformMisc::GetDeviceId();
	if (Material.IsEmpty())
	{
		Material = FPlatformMisc::GetLoginId();
	}
	if (Material.IsEmpty())
	{
		Material = FString(FPlatformProcess::ComputerName()) + TEXT("|") + FPlatformProcess::UserName();
	}
	if (Material.IsEmpty())
	{
		return false;
	}

	const FString Seed = FString(StringCast<TCHAR>(KeySalt).Get()) + Material;
	auto SeedUtf8 = StringCast<UTF8CHAR>(*Seed, Seed.Len());

	TUniquePtr<FEncryptionContext> Ctx = IPlatformCrypto::Get().CreateContext();
	if (!Ctx.IsValid())
	{
		return false;
	}

	// FSHA256Hasher: Init → Update → Finalize(32 байта) (EncryptionContextOpenSSL.h:16-41, CreateSHA256Hasher :366).
	FSHA256Hasher Hasher = Ctx->CreateSHA256Hasher();
	if (Hasher.Init() != EPlatformCryptoResult::Success)
	{
		return false;
	}
	const TArrayView<const uint8> SeedView(reinterpret_cast<const uint8*>(SeedUtf8.Get()), SeedUtf8.Length());
	if (Hasher.Update(SeedView) != EPlatformCryptoResult::Success)
	{
		return false;
	}
	OutKey.SetNumZeroed(KeyLen);
	return Hasher.Finalize(TArrayView<uint8>(OutKey)) == EPlatformCryptoResult::Success;
}

bool FUmSecureStore_Generic::Save(const FUmStoredSession& Session)
{
	using namespace UmSecureStorePrivate;

	TArray<uint8> Plain;
	if (!FUmSecureStoreCommon::SerializeSession(Session, Plain))
	{
		return false;
	}

	TArray<uint8> Key;
	if (!DeriveKey(Key))
	{
		UE_LOG(LogUmSecureStore, Warning, TEXT("Generic store: no key material on this device; session not persisted"));
		FUmSecureStoreCommon::SecureZero(Plain);
		return false;
	}

	TUniquePtr<FEncryptionContext> Ctx = IPlatformCrypto::Get().CreateContext();
	TArray<uint8> Nonce;
	Nonce.SetNumZeroed(NonceLen);
	if (!Ctx.IsValid() || Ctx->CreateRandomBytes(TArrayView<uint8>(Nonce)) != EPlatformCryptoResult::Success)
	{
		UE_LOG(LogUmSecureStore, Error, TEXT("Generic store: CreateRandomBytes failed"));
		FUmSecureStoreCommon::SecureZero(Plain);
		FUmSecureStoreCommon::SecureZero(Key);
		return false;
	}

	TArray<uint8> Tag;
	EPlatformCryptoResult Result = EPlatformCryptoResult::Failure;
	TArray<uint8> Cipher = Ctx->Encrypt_AES_256_GCM(TArrayView<const uint8>(Plain), TArrayView<const uint8>(Key),
		TArrayView<const uint8>(Nonce), Tag, Result);

	FUmSecureStoreCommon::SecureZero(Plain);
	FUmSecureStoreCommon::SecureZero(Key);

	if (Result != EPlatformCryptoResult::Success || Tag.Num() != TagLen)
	{
		UE_LOG(LogUmSecureStore, Error, TEXT("Generic store: Encrypt_AES_256_GCM failed (tag=%d)"), Tag.Num());
		return false;
	}

	TArray<uint8> File;
	File.Reserve(4 + 1 + NonceLen + TagLen + Cipher.Num());
	File.Append(Magic, UE_ARRAY_COUNT(Magic));
	File.Add(Version);
	File.Append(Nonce);
	File.Append(Tag);
	File.Append(Cipher);

	const bool bOk = FUmSecureStoreCommon::WriteFile(FilePath, File);
	UE_LOG(LogUmSecureStore, Log, TEXT("Generic store: save %s -> %s"), *FilePath, bOk ? TEXT("ok") : TEXT("FAILED"));
	return bOk;
}

bool FUmSecureStore_Generic::Load(FUmStoredSession& OutSession)
{
	using namespace UmSecureStorePrivate;

	TArray<uint8> File;
	if (!FUmSecureStoreCommon::ReadFile(FilePath, File))
	{
		return false;
	}

	const int32 HeaderLen = 4 + 1 + NonceLen + TagLen;
	if (File.Num() < HeaderLen || FMemory::Memcmp(File.GetData(), Magic, 4) != 0 || File[4] != Version)
	{
		UE_LOG(LogUmSecureStore, Warning, TEXT("Generic store: bad header, discarding %s"), *FilePath);
		Clear();
		return false;
	}

	TArray<uint8> Key;
	if (!DeriveKey(Key))
	{
		return false;
	}

	const TArrayView<const uint8> Nonce(File.GetData() + 5, NonceLen);
	const TArrayView<const uint8> Tag(File.GetData() + 5 + NonceLen, TagLen);
	const TArrayView<const uint8> Cipher(File.GetData() + HeaderLen, File.Num() - HeaderLen);

	TUniquePtr<FEncryptionContext> Ctx = IPlatformCrypto::Get().CreateContext();
	EPlatformCryptoResult Result = EPlatformCryptoResult::Failure;
	TArray<uint8> Plain = Ctx.IsValid()
		? Ctx->Decrypt_AES_256_GCM(Cipher, TArrayView<const uint8>(Key), Nonce, Tag, Result)
		: TArray<uint8>();
	FUmSecureStoreCommon::SecureZero(Key);

	if (Result != EPlatformCryptoResult::Success)
	{
		// Другое устройство/пользователь или повреждение: тег не сошёлся. Файл бесполезен — удаляем.
		UE_LOG(LogUmSecureStore, Warning, TEXT("Generic store: decrypt failed (auth tag mismatch), discarding"));
		Clear();
		return false;
	}

	const bool bOk = FUmSecureStoreCommon::DeserializeSession(Plain, OutSession);
	FUmSecureStoreCommon::SecureZero(Plain);
	return bOk;
}

void FUmSecureStore_Generic::Clear()
{
	FUmSecureStoreCommon::DeleteFile(FilePath);
}

// ------------------------------------------------------------------------------------------------ Factory

TSharedPtr<IUmSecureStore> FUmSecureStoreFactory::CreateForPlatform(const FString& SlotName)
{
#if PLATFORM_WINDOWS
	return MakeShared<FUmSecureStore_Windows>(SlotName);
#else
	// TODO(v2): PLATFORM_MAC/PLATFORM_IOS → Keychain (SecItemAdd/SecItemCopyMatching), PLATFORM_ANDROID → Keystore через JNI —
	// отдельные cpp по образцу UmSecureStore_Windows.cpp (R8 §2.10: в движке обёрток нет).
	return MakeShared<FUmSecureStore_Generic>(SlotName);
#endif
}
