// Run UBT Build.bat hidden; write full output to log; print tail + exit.
const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const [log, ...args] = process.argv.slice(2);
const bat = path.join(process.env.UE_ROOT || 'C:/Program Files/Epic Games/UE_5.8', 'Engine', 'Build', 'BatchFiles', 'Build.bat');
const cmdLine = `"${bat}" ${args.join(' ')}`;
const t0 = Date.now();
const r = spawnSync('cmd.exe', ['/d', '/s', '/c', `"${cmdLine}"`], { windowsHide: true, windowsVerbatimArguments: true, encoding: 'utf8', maxBuffer: 1 << 30, env: process.env });
const out = (r.stdout || '') + (r.stderr || '');
fs.writeFileSync(log, out);
const lines = out.split(/\r?\n/).filter((l) => l.trim());
console.log(lines.slice(-25).join('\n'));
console.log('CMD=' + cmdLine);
console.log('EXIT=' + r.status + ' DURATION_S=' + ((Date.now() - t0) / 1000).toFixed(1));
