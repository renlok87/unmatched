// Источник: ADR §3.2 (строка UmEditor: «Коммандлет импорта контента (Import/ → DA_*/DT_*/T_*), редакторские
// валидаторы»; PublicDependencyModuleNames = UnrealEd, AssetTools, EditorSubsystem, UmModel, UmClient), §3.3, §3.7.
// Только редактор (Type=Editor в .uproject); в cooked-сборку не попадает. Экспорт — UMEDITOR_API.
//
// Проверка модулей по движку (UE 5.8.2):
//   UnrealEd        — $UE/Source/Editor/UnrealEd/UnrealEd.Build.cs (UCommandlet, UTextureFactory, UProjectPackagingSettings)
//   AssetTools      — $UE/Source/Developer/AssetTools/AssetTools.Build.cs (IAssetTools::CreateAsset)
//   EditorSubsystem — $UE/Source/Editor/EditorSubsystem/EditorSubsystem.Build.cs
//   AssetRegistry   — $UE/Source/Runtime/AssetRegistry (поиск существующих DA_Hero_*/DT_* при повторном импорте)
//   DataTableEditor — $UE/Source/Editor/DataTableEditor (FDataTableEditorUtils — уведомления после CreateTableFromCSVString,
//                     $UE/Source/Runtime/Engine/Classes/Engine/DataTable.h:351,358)
//   ImageWrapper    — декодирование PNG из Import/<set>/*.png (ADR §3.7 export-content.mjs даёт только PNG; R8 §2.9)

using UnrealBuildTool;

public class UmEditor : ModuleRules
{
	public UmEditor(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
			"UnrealEd",
			"AssetTools",
			"EditorSubsystem",
			"UmModel",
			"UmClient"
		});

		PrivateDependencyModuleNames.AddRange(new string[]
		{
			"AssetRegistry",
			"DataTableEditor",
			"ImageWrapper",
			"Json",
			"JsonUtilities",
			"GameplayTags"
		});

		// TODO(C6-editor): UUmContentImportCommandlet (Public/UmContentImportCommandlet.h) читает
		// Import/<set>/{heroes,cards,boards}.json + PNG и Import/DT_AttackRange.csv, DT_HeroStances.csv (ADR §3.7),
		// создаёт DA_Hero_<heroSlug> (UUmHeroDefinition), DA_Board_<boardSlug>, DT_CardArt/DT_HeroArt/DT_BoardArt/DT_AttackRange,
		// T_Card_<heroSlug>_<cardSlug>_EN|RU (512×716), PAL_<Set>. Запуск:
		//   UnrealEditor-Cmd.exe <uproject> -run=UmContentImport -set=<Set> -NullRHI
	}
}
