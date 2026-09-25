using UnrealBuildTool;
public class Unmatched : ModuleRules {
  public Unmatched(ReadOnlyTargetRules Target) : base(Target) {
    PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
    PublicDependencyModuleNames.AddRange(new string[] {
      "Core", "CoreUObject", "Engine", "InputCore",
      // S08 (GD-028/GD-029): HTTP + graphql-transport-ws + JSON contracts + grey-flow Slate UI
      "HTTP", "WebSockets", "Json", "Slate", "SlateCore",
    });
  }
}
