// Runs a command with backend/.env exported into the environment (secrets
// stay OUT of argv). Usage (from backend/):
//   node ../tools/s09/run-with-env.cjs <command> [args...]
const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const env = { ...process.env };
const envPath = path.resolve(__dirname, '..', '..', 'backend', '.env');
for (const line of fs.readFileSync(envPath, 'utf8').split(/\r?\n/)) {
  const m = line.match(/^([A-Za-z][A-Za-z0-9_]*)=(.*)$/);
  if (m && !(m[1] in env)) env[m[1]] = m[2];
}
const [cmd, ...args] = process.argv.slice(2);
if (!cmd) {
  console.error('usage: run-with-env.cjs <command> [args...]');
  process.exit(2);
}
const r = spawnSync(cmd, args, { env, stdio: 'inherit', windowsHide: true });
process.exit(r.status === null ? 1 : r.status);
