# T4.3 runner window 2026-10-04 04:01–05:41 — not run

The runner waited 100 minutes on package `606e7ec0` (Marmoreal · original map) and never saw 10 minutes of idle:
`maxIdleSeconds` = 51.9.

## Cause

The cause is not the user. Probes after the window found the source with read-only low-level hooks and polling of
`GetLastInputInfo`:

- another program injects an **F15** key press (`vk=0x7e`, injected flag set, `dwExtraInfo=0`) every 60 s;
- each press resets `GetLastInputInfo`, so the old idle check could never reach 600 s;
- the same cause explains the windows `t43-20261003-190410` (max 51.6 s) and `t43-20261003-205427` (max 52.3 s).

F15 key presses like this are the usual trick of keep-awake tools.

## Fix

`tools/s08/t43_real_input.py`, class `PhysicalIdle`, measures idle as the time since the last **physical** input.
It applies the same rule as the abort guard:

- input injected by other programs does not count;
- a change of `GetLastInputInfo` that no injected event explains counts as the user.

The live check (140 s) gave physical idle 121 s against plain idle 0.9 s. It recorded 10 foreign F15 events and
0 changes counted as the user.
