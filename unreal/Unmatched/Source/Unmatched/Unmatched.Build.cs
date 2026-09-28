using UnrealBuildTool;
public class Unmatched : ModuleRules {
  public Unmatched(ReadOnlyTargetRules Target) : base(Target) {
    PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
    PublicDependencyModuleNames.AddRange(new string[] {
      "Core", "CoreUObject", "Engine", "InputCore",
      // S08 (GD-028/GD-029): HTTP + graphql-transport-ws + JSON contracts + grey-flow Slate UI
      "HTTP", "WebSockets", "Json", "Slate", "SlateCore",
    });
    // ART-004 T1.1 -S08Perf reads RHIGetGPUFrameCycles/GDynamicRHI (RHI) and
    // GGameThreadTime/GRenderThreadTime (RenderCore). The monolithic game
    // target links them implicitly; the modular UnmatchedEditor target (T2.2
    // automation tests) needs the explicit private dependencies.
    PrivateDependencyModuleNames.AddRange(new string[] { "RHI", "RenderCore" });
  }
}
