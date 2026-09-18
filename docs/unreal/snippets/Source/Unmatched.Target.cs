// Источник: ADR §3.1 («Таргеты»), §3.2 (модули). Образец сигнатур —
// $UE/Templates/TP_ThirdPerson/Source/TP_ThirdPerson.Target.cs;
// значения enum — $UE/Engine/Source/Programs/UnrealBuildTool/Configuration/Rules/TargetRules.cs:123-242
// (BuildSettingsVersion.Latest = V7, EngineIncludeOrderVersion.Latest = Unreal5_8).
//
// Сборка (R8 §2.14, ADR §3.1):
//   "C:\Program Files\Epic Games\UE_5.8\Engine\Build\BatchFiles\Build.bat" Unmatched Win64 Development
//       -Project="<repo>\unreal\Unmatched\Unmatched.uproject" -WaitMutex

using UnrealBuildTool;
using System.Collections.Generic;

public class UnmatchedTarget : TargetRules
{
	public UnmatchedTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;

		// Явные версии вместо Latest: Latest «comes with a high risk of introducing compile errors
		// on newer Unreal versions» (TargetRules.cs:32). V7 == BuildSettingsVersion.Latest в 5.8,
		// Unreal5_8 == EngineIncludeOrderVersion.Latest в 5.8 — фиксируем их поимённо.
		DefaultBuildSettings = BuildSettingsVersion.V7;
		IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_8;

		// ADR §3.1: Game-таргет — три runtime-модуля; UmClient — primary game module
		// (IMPLEMENT_PRIMARY_GAME_MODULE в UmClient/Private/UmClientModule.cpp).
		ExtraModuleNames.AddRange(new string[] { "UmNet", "UmModel", "UmClient" });
	}
}
