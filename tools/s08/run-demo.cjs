// Temp helper: run the hidden two-client demo script with parameters.
// Usage: node run-demo.cjs <EvidenceDir> <RunSeconds>
const { spawnSync } = require('child_process');
const evidenceDir = process.argv[2];
const runSeconds = process.argv[3] ? parseInt(process.argv[3], 10) : 120;
const repeat = process.argv[4] ? parseInt(process.argv[4], 10) : 1;
const script = require('path').join(__dirname, 'run-phase2-demo.ps1');
for (let i = 1; i <= repeat; i++) {
  const r = spawnSync('powershell.exe', [
    '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', script,
    '-EvidenceDir', evidenceDir,
    '-RunSeconds', String(runSeconds),
  ], {
    windowsHide: true,
    encoding: 'utf8',
    timeout: 3000000,
  });
  const out = ((r.stdout || '') + (r.stderr || ''));
  const lines = out.split(/\r?\n/).filter((l) =>
    /published evidence|TRACES OK|cleanup: aborted|cleanup: FAILED|missing|throw|Exception|convergence|room created|heroA/i.test(l));
  console.log(`[repeat ${i}/${repeat}] DEMO_EXIT=${r.status}`);
  if (r.status !== 0) process.exitCode = 1;
  console.log(lines.map((l) => `[repeat ${i}] ${l.trim()}`).join('\n'));
  if (r.status !== 0 && repeat === 1) console.log(out.slice(-3000));
}
