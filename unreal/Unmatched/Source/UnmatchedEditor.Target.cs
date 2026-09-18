using UnrealBuildTool;
public class UnmatchedEditorTarget : TargetRules { public UnmatchedEditorTarget(TargetInfo Target) : base(Target) { Type = TargetType.Editor; DefaultBuildSettings = BuildSettingsVersion.V7; IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_8; ExtraModuleNames.Add("Unmatched"); } }
