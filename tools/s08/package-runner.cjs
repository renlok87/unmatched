// Temp helper: run package-client.ps1 hidden, stream result.
const { spawnSync } = require('child_process');
const script = require('path').join(__dirname, 'package-client.ps1');
const r = spawnSync('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', script], {
  windowsHide: true,
  encoding: 'utf8',
  timeout: 3000000,
});
console.log(((r.stdout || '') + (r.stderr || '')).slice(-4000));
console.log('PS_EXIT=' + r.status);
if (r.status !== 0) process.exitCode = 1;
