// Temp helper: run UBT Build.bat hidden, print tail + real exit status.
const { spawnSync } = require('child_process');
const path = require('path');
const ueRoot = process.env.UE_ROOT || 'C:\\Program Files\\Epic Games\\UE_5.8';
const bat = path.join(ueRoot, 'Engine', 'Build', 'BatchFiles', 'Build.bat');
const cmdLine = `"${bat}" ${process.argv.slice(2).join(' ')}`;
const r = spawnSync('cmd.exe', ['/d', '/c', cmdLine], {
  windowsHide: true,
  windowsVerbatimArguments: true,
  encoding: 'utf8',
  timeout: 570000,
  env: process.env,
});
const out = (r.stdout || '') + (r.stderr || '');
const lines = out.split(/\r?\n/).filter((l) => l.trim().length > 0);
console.log(lines.slice(-60).join('\n'));
console.log('EXIT=' + r.status);
if (r.status !== 0) process.exitCode = 1;
