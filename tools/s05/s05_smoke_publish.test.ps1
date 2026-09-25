$ErrorActionPreference = 'Stop'
# Proof for the atomic S05 evidence publication in s05_smoke.ps1 (P2 2026-09-25).
# Runs the in-script fault-injection self-test: deterministic injected failures after
# the 1st/2nd/3rd frame copy and after the summary write, each checked against SHA256 +
# existence snapshots of all four prior files plus an unrelated evidence file; also a
# prior-absent rollback (newly created files removed), a clean success publication, and
# the rollback containment guard. All scenarios run on a sandboxed temp evidence copy -
# the real evidence directory is never opened for writing.
& "$PSScriptRoot/s05_smoke.ps1" -SelfTest
