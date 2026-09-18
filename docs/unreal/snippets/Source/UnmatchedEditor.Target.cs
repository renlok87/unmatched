// Источник: ADR §3.1 («Таргеты»), §3.2 (UmEditor — Editor-модуль, в cooked-сборку не попадает).
// Образец — $UE/Templates/TP_ThirdPerson/Source/TP_ThirdPersonEditor.Target.cs;
// enum — $UE/Engine/Source/Programs/UnrealBuildTool/Configuration/Rules/TargetRules.cs:123-242.
//
// Сборка редактора (ADR §3.1, R8 §2.14):
//   "C:\Program Files\Epic Games\UE_5.8\Engine\Build\BatchFiles\Build.bat" UnmatchedEditor Win64 Development
//       -Project="<repo>\unreal\Unmatched\Unmatched.uproject" -WaitMutex
// CLI-тесты без GUI (ADR §5.8): UnrealEditor-Cmd.exe <uproject> -NullRHI -ExecCmds="Automation RunTests Unmatched.; Quit"

using UnrealBuildTool;
using System.Collections.Generic;

public class UnmatchedEditorTarget : TargetRules
{
	public UnmatchedEditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;

		DefaultBuildSettings = BuildSettingsVersion.V7;
		IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_8;

		// ADR §3.1: Editor-таргет = Game-модули + UmEditor (коммандлет импорта, валидаторы).
		ExtraModuleNames.AddRange(new string[] { "UmNet", "UmModel", "UmClient", "UmEditor" });
	}
}
