// Temp helper: packaged launch WITHOUT a map argument - the default map
// (S08Arena, GameDefaultMap in DefaultEngine.ini) must load and the game
// mode must boot, then self-exit via -S08ExitAfter.
const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');
const exe = path.resolve(__dirname, '../../unreal/Unmatched/Saved/StagedBuilds/Windows/Unmatched.exe');
const log = path.join(os.tmpdir(), `s08-nomap-probe-${process.pid}.log`);
const r = spawnSync(exe, [
  '-windowed', '-resx=1920', '-resy=1080', '-RenderOffScreen',
  '-unattended', '-nosplash', '-nullrhi',
  '-S08Api=http://localhost:3100/graphql',
  '-S08ExitAfter=12',
  `-abslog=${log}`,
], { windowsHide: true, encoding: 'utf8', timeout: 120000 });
console.log('EXIT=' + r.status);
if (r.status !== 0) process.exitCode = 1;
if (fs.existsSync(log)) {
  const text = fs.readFileSync(log, 'utf8');
  const lines = text.split(/\r?\n/).filter((l) =>
    /MAP LOAD|S08_FLOW_READY|S08Arena|GameMode|Fatal|Error/i.test(l));
  console.log(lines.slice(-40).join('\n'));
} else {
  console.log('NO LOG FILE');
  console.log(((r.stdout || '') + (r.stderr || '')).slice(-1500));
}
