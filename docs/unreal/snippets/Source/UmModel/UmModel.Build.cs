// Источник: ADR §3.2 (строка UmModel), §4.2-§4.3 (DTO, парсер, диф, правила, теги, строки DataTable).
// Правило ADR §3.2/§4.0: UmModel НЕ зависит от UmNet; никаких субсистем, акторов, виджетов.
// Экспорт — UMMODEL_API.
//
// Проверка модулей по движку (UE 5.8.2):
//   Engine       — FTableRowBase ($UE/Source/Runtime/Engine/Classes/Engine/DataTable.h) для FUm*Row (ADR §4.3 UmTableRows.h)
//   Json         — DOM-«ремонт» состояния в FUmGameStateParser (ADR §4.2)
//   JsonUtilities— FJsonObjectConverter::JsonObjectToUStruct(bStrictMode=false), FJsonObjectWrapper (FUmCardEffect::RawJson)
//   GameplayTags — $UE/Source/Runtime/GameplayTags/GameplayTags.Build.cs; нативные теги
//                  UE_DECLARE_GAMEPLAY_TAG_EXTERN / UE_DEFINE_GAMEPLAY_TAG ($UE/Source/Runtime/GameplayTags/Public/NativeGameplayTags.h)

using UnrealBuildTool;

public class UmModel : ModuleRules
{
	public UmModel(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
			"Json",
			"JsonUtilities",
			"GameplayTags"
		});

		PrivateDependencyModuleNames.AddRange(new string[]
		{
			// пусто: модуль чистый, всё покрывается spec-тестами на фикстурах (ADR §3.2)
		});

		// UmOps.gen.h генерируется unreal/Tools/ops-check.mjs (ADR §3.7, §5.9) — руками не править.
	}
}
