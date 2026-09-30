using UnrealBuildTool;
public class Unmatched : ModuleRules {
  public Unmatched(ReadOnlyTargetRules Target) : base(Target) {
    PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
    PublicDependencyModuleNames.AddRange(new string[] {
      "Core", "CoreUObject", "Engine", "InputCore",
      // S08 (GD-028/GD-029): HTTP + graphql-transport-ws + JSON contracts + grey-flow Slate UI
      "HTTP", "WebSockets", "Json", "Slate", "SlateCore",
      // W4-C hybrid HUD (user decision 2026-09-28): the art HUD plate/icon are
      // UMG widget classes (S08ArtHudWidgets.h) with WBP children.
      "UMG",
    });
    // W4-C: editor-only authoring of the art HUD widget blueprints
    // (S08ArtHudAuthoring.cpp, WITH_EDITOR) - UnrealEditor-Cmd of the art
    // worktree builds WBP_S08ArtPlate/WBP_S08ArtIcon from the code default
    // tree. Never linked into the game target.
    if (Target.bBuildEditor) {
      PrivateDependencyModuleNames.AddRange(new string[] { "UnrealEd", "UMGEditor", "Kismet", "AssetRegistry" });
    }
    // ART-004 T1.1 -S08Perf reads RHIGetGPUFrameCycles/GDynamicRHI (RHI) and
    // GGameThreadTime/GRenderThreadTime (RenderCore). The monolithic game
    // target links them implicitly; the modular UnmatchedEditor target (T2.2
    // automation tests) needs the explicit private dependencies.
    PrivateDependencyModuleNames.AddRange(new string[] { "RHI", "RenderCore" });
    // ART-005 / stage 3 T3.2: the -ArtPreview board profiles (zone palette and
    // glyphs per zone key, light profiles, board matches) are data read at
    // runtime from <Project>/Config/ArtBoards; staged into the pak (UFS) so
    // the packaged client reads the same file (S08BoardArt.h).
    RuntimeDependencies.Add("$(ProjectDir)/Config/ArtBoards/S08ArtBoardProfiles.json", StagedFileType.UFS);
    // ENV-MAPS track C: the environment layouts of the original-map boards (S08EnvLayout.h), read at runtime
    // from <Project>/Config/ArtBoards/EnvLayouts/<map>.layout.json. The wildcard is resolved by UBT on every
    // build (FileFilter.ResolveWildcard; an absent folder stages nothing): a layout added later needs a
    // rebuild of the target before packaging.
    RuntimeDependencies.Add("$(ProjectDir)/Config/ArtBoards/EnvLayouts/*.layout.json", StagedFileType.UFS);
    // W4-A -Bench: the captured Cobble 5x6 game state the backend-less render
    // bench replays (S08FlowGameMode.cpp RunRenderBench).
    RuntimeDependencies.Add("$(ProjectDir)/Config/Bench/S08BenchCobble.json", StagedFileType.UFS);
    // ENV-MAPS: the same scene on the original maps (-BenchFixture=<file>; generated from the topology
    // fixtures by tools/art/render/env_bench_fixtures.cts).
    RuntimeDependencies.Add("$(ProjectDir)/Config/Bench/S08BenchMarmoreal.json", StagedFileType.UFS);
    RuntimeDependencies.Add("$(ProjectDir)/Config/Bench/S08BenchSarpedon.json", StagedFileType.UFS);
    // W4-C: the art HUD string table (LOCTABLE_FROMFILE_GAME, Content-relative)
    // is a CSV, not an asset - staged into the pak like the board profiles.
    RuntimeDependencies.Add("$(ProjectDir)/Content/Localization/StringTables/S08ArtHud.csv", StagedFileType.UFS);
  }
}
