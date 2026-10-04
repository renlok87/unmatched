# T4.3 runner window 2026-10-04 05:54–06:04 — started, no input sent

This was the first window with the physical-idle check (`ee51e825`).

- **Idle check.** The user was idle 600 s at 06:03:44. Plain `GetLastInputInfo` idle was 0.5 s at that moment, because a
  keep-awake tool injected F15 40 times; the check counted 0 changes as the user.
- **Demo.** The demo started on Marmoreal · original map (package `fd585184`). The host shot was taken and the own-hero
  target was found.
- **Result.** The runner stopped with «окно хоста не найдено». No input was sent.
- **Cause.** The demo prints the pid of the staged `Unmatched.exe` stub. The client window belongs to the real client,
  which the stub starts as a child process.
- **Fix.** `find_window` now searches the stub's whole process tree (`process_tree`, Toolhelp32).
