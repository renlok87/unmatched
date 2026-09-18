using UnrealBuildTool;
public class UnmatchedTarget : TargetRules { public UnmatchedTarget(TargetInfo Target) : base(Target) { Type = TargetType.Game; DefaultBuildSettings = BuildSettingsVersion.V7; IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_8; ExtraModuleNames.Add("Unmatched"); } }
