import { exec } from 'child_process';

const PORT = 5480;

console.log(`Checking for process on port ${PORT}...`);

// Find process on port and kill it
exec(`netstat -ano | findstr :${PORT}`, (error, stdout) => {
  if (!stdout) {
    console.log(`Port ${PORT} is free, starting dev server...`);
    process.exit(0);
  }

  // Extract PID from output
  const lines = stdout.trim().split('\n');
  const pids = new Set();

  for (const line of lines) {
    const parts = line.trim().split(/\s+/);
    if (parts.length >= 5) {
      const pid = parts[parts.length - 1]; // Last column is PID
      if (pid && pid !== 'PID') {
        pids.add(pid);
      }
    }
  }

  if (pids.size === 0) {
    console.log(`Port ${PORT} is free, starting dev server...`);
    process.exit(0);
  }

  // Kill each process
  let killed = 0;
  for (const pid of pids) {
    exec(`taskkill /PID ${pid} /F`, (killError, killStdout, killStderr) => {
      killed++;
      if (killed === pids.size) {
        console.log(`Killed ${killed} process(es) on port ${PORT}`);
        // Give a moment for the port to be released
        setTimeout(() => process.exit(0), 500);
      }
    });
  }
});
