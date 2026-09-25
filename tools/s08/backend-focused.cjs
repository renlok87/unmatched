// Temp helper: run the four S08 backend specs with Jest runInBand+runTestsByPath.
const { spawnSync } = require('child_process');
const path = require('path');
const backend = path.resolve(__dirname, '../../backend');
const specs = [
  'src/games/resolvers/game-by-code-throttle.spec.ts',
  'src/games/resolvers/game-subscription-barrier.spec.ts',
  'src/games/resolvers/game-subscription-delivery-auth.spec.ts',
  'src/games/resolvers/s08-lobby-contract.spec.ts',
];
const r = spawnSync(process.execPath, [path.join(backend, 'node_modules', 'jest', 'bin', 'jest.js'), '--runInBand', '--runTestsByPath', ...specs], {
  cwd: backend,
  windowsHide: true,
  encoding: 'utf8',
  timeout: 570000,
});
const out = (r.stdout || '') + (r.stderr || '');
const lines = out.split(/\r?\n/).filter((l) =>
  /PASS|FAIL|Tests:|Suites:|Snapshots:|Time:|●|error/i.test(l));
console.log(lines.join('\n'));
console.log('JEST_EXIT=' + r.status);
if (r.status !== 0) process.exitCode = 1;
