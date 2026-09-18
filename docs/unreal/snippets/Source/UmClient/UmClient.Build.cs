// Источник: ADR §3.2 (строка UmClient — primary game module), §4.4-§4.8 (State/Content/UI/Presentation/Dev).
// Правило ADR §4.0: единственное место, где транспорт (UmNet) встречается с моделью (UmModel).
// Экспорт — UMCLIENT_API. Blueprint видит только BlueprintCallable/BlueprintReadOnly API этого модуля.
//
// Проверка модулей по движку (UE 5.8.2):
//   InputCore, EnhancedInput — AUmPlayerController (ADR §4.6; R8 §2.7: EnhancedInputComponent.h:482)
//   UMG, Slate, SlateCore    — C++-базы виджетов (R8 §2.6)
//   CommonUI, CommonInput    — $UE/Plugins/Runtime/CommonUI/Source/{CommonUI,CommonInput};
//                              UUmGameViewportClient : UCommonGameViewportClient (CommonGameViewportClient.h:24)
//   GameplayTags             — FGameplayTagContainer/FGameplayTagQuery в HUD-модели и аффордансах (ADR §5.6)
//   FieldNotification        — $UE/Source/Runtime/FieldNotification/FieldNotification.Build.cs;
//                              INotifyFieldValueChanged для UUmGameHudModel (ADR §4.6)
//   ImageWrapper             — $UE/Source/Runtime/ImageWrapper/ImageWrapper.Build.cs; PNG/JPEG → UTexture2D (ADR §4.5)
//   DeveloperSettings        — UUmClientSettings

using UnrealBuildTool;

public class UmClient : ModuleRules
{
	public UmClient(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
			"InputCore",
			"EnhancedInput",
			"UMG",
			"Slate",
			"SlateCore",
			"CommonUI",
			"CommonInput",
			"GameplayTags",
			"FieldNotification",
			"ImageWrapper",
			"DeveloperSettings",
			"UmNet",
			"UmModel"
		});

		PrivateDependencyModuleNames.AddRange(new string[]
		{
			"Json",          // UUmMockBackend: сценарии из фикстур Tests/Fixtures/*.json (ADR §4.8)
			"JsonUtilities", // FUmContentCache: Saved/UmContent/*.json (ADR §4.5)
			"HTTP",          // UUmImageCacheSubsystem: HTTP GET картинок (ADR §4.5) — напрямую, минуя GraphQL-клиент
			"RenderCore",    // UTexture2D::CreateTransient + UpdateResource (ADR §4.5)
			"RHI"
		});

		// Тесты ADR §4.8: Private/Tests/{UmSnapshotStore,UmInputFsm,UmPlayback,UmMockBackend,UmE2E}.spec.cpp
		// под WITH_DEV_AUTOMATION_TESTS; functional tests в L_Test_Game — плагин FunctionalTestingEditor (.uproject).
		// TODO(C4-client): если консольные команды um.* (Dev/UmDevConsole.h) вынесут в отдельный dev-модуль,
		// исключить их из Shipping через Target.Configuration == UnrealTargetConfiguration.Shipping.
	}
}
