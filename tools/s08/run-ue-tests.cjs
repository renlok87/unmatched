// Temp helper: run UE automation tests headless+hidden, dump log tail.
// Usage: node run-ue-tests.cjs <TestFilter> <abs log file>
const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const filter = process.argv[2] || 'Unmatched.S08';
const logPath = process.argv[3];
const repeat = process.argv[4] ? parseInt(process.argv[4], 10) : 1;
const root = path.resolve(__dirname, '../..');
const uproject = path.join(root, 'unreal', 'Unmatched', 'Unmatched.uproject');
const fixtures = path.join(root, 'docs', 'game-design', 'evidence', 'S08', 'fixtures');
const s09Fixtures = path.join(root, 'docs', 'game-design', 'evidence', 'S09', 'fixtures');
const ueRoot = process.env.UE_ROOT || 'C:\\Program Files\\Epic Games\\UE_5.8';
const exe = path.join(ueRoot, 'Engine', 'Binaries', 'Win64', 'UnrealEditor-Cmd.exe');
for (let run = 1; run <= repeat; run++) {
  const args = [
    uproject,
    `-ExecCmds=Automation RunTests ${filter}; Quit`,
    '-unattended', '-nosplash', '-nullrhi', '-nullaudio',
    `-S08Fixtures=${fixtures}`,
    `-S09Fixtures=${s09Fixtures}`,
    '-log',
  ];
  if (logPath) args.push(`-abslog=${logPath}`);
  const r = spawnSync(exe, args, { windowsHide: true, encoding: 'utf8', timeout: 570000 });
  const tag = `[run ${run}/${repeat}]`;
  console.log(`${tag} EXIT=${r.status}`);
  if (r.status !== 0) process.exitCode = 1;
  const logFile = logPath || '';
  let text = '';
  if (logFile && fs.existsSync(logFile)) {
    text = fs.readFileSync(logFile, 'utf8');
    if (repeat > 1) {
      try { fs.renameSync(logFile, logFile.replace(/\.log$/, `-${run}.log`)); } catch {}
    }
  }
  text += (r.stdout || '') + (r.stderr || '');
  const lines = text.split(/\r?\n/).filter((l) =>
    /Found \d+ automation tests|Test Completed\.|TEST COMPLETE|Fatal|Warning: dropped/i.test(l));
  console.log(lines.map((l) => `${tag} ${l}`).join('\n'));
}
