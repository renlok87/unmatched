# S10 Unreal MCP editor check — 2026-09-27

One Unreal Editor 5.8 instance was opened for the S10 client worktree with
`-ModelContextProtocolStartServer`, then closed after the check. The local MCP
server listened on `127.0.0.1:8123`; MCP `initialize` negotiated protocol
`2025-11-25`. Calls were made through the server's `tools/call` endpoint.

| MCP tool | Observed result |
| --- | --- |
| `SceneTools.get_current_level` | `/Game/S08/S08Arena` |
| `EditorAppToolset.GetVisibleActors` | Seven editor-visible engine/world actors before PIE; no claim about packaged game actors |
| `SlateInspectorToolset.Observe` / `Snapshot` | Editor and Message Log top-level windows present; hidden window yielded image nodes only, so this is not a detailed HUD inspection |
| `EditorAppToolset.StartPIE` / `IsPIERunning` | In-viewport PIE started; `IsPIERunning=true` |
| `EditorAppToolset.StopPIE` | PIE stopped successfully |
| `SlateInspectorToolset.Unobserve` | Observer removed |

No level or asset was modified through MCP. The hidden editor was closed after
the check to avoid competing with the client rebuild. Packaged HUD and fault
recovery are verified separately by the two-client run, not by this editor
snapshot.
