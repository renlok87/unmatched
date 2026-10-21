"""Шаг 7a: агентские скрытые редакторы по слотам — свой редактор на героя (ДС-3a, 2026-10-21; заменяет правило
«7a строго по одному герою» ДС-3, `docs/game-design/decisions/2026-10-21-parallel-7a-editor-slots.md`).

Слот N — отдельный скрытый UnrealEditor проекта этого checkout:
  MCP          127.0.0.1:<8123+N>/mcp (-ModelContextProtocolPort + `ModelContextProtocol.StartServer <порт>`; автостарт
               сервера из ini выключен — тот же ключ, что package-client.ps1 передаёт кукеру);
  блокировка   C:/tmp/ue-editor-slot<N>.lock (ue_lock.lock_path_for_slot; слот 0 — прежний C:/tmp/ue-editor.lock);
  консоль      <workdir>/drop (review/ue_py/console_drop.py, UE_CONSOLE_DROP), лог <workdir>/editor.log,
               PID <workdir>/editor.pid; реестр слотов C:/tmp/ue7a-slots.json (слот -> герой, PID, порт, каталоги).
Слот 0 — прежний одиночный режим (порт 8123, C:/tmp/ue-editor.lock): без UE_EDITOR_SLOT и прочих переменных инструменты
этапа работают как раньше.

    python tools/tripo-pipeline/ue7a/editor_slot.py start <N> [--hero <Key>] [--workdir DIR] [--wait 900] [--dry-run]
    eval "$(python tools/tripo-pipeline/ue7a/editor_slot.py env <N>)"   # UE_MCP_URL, UE_EDITOR_LOCK, UE_CONSOLE_DROP,
                                                                       # UE_LOCK_OWNER, UE_EDITOR_SLOT (bash; --format ps|json)
    python tools/tripo-pipeline/ue7a/editor_slot.py list
    python tools/tripo-pipeline/ue7a/editor_slot.py stop <N> [--timeout 180] [--force-dirty]
    python tools/tripo-pipeline/ue7a/editor_slot.py check-shared-write "<действие>"   # код 3, если редакторов проекта > 1

start отказывает (код 3), если слот уже занят живым редактором, порт уже слушает, свободной ОЗУ меньше --min-free-gb,
или открыт интерактивный редактор этого проекта (без -unattended -RenderOffScreen: гейт SKILL.md §5 п.7). Между стартами
слотов — не меньше --stagger с (всплеск компиляции шейдеров при одновременном старте). Готовность — порт слушает и есть
<drop>/ready.json (код 0); не дождались за --wait — код 4, процесс не гасится (решает оркестратор).
stop закрывает только свой процесс (в командной строке -abslog=<workdir>/editor.log и -ModelContextProtocolPort=<порт>);
отказ (код 3), пока блокировка слота занята живым шагом или в редакторе есть грязные пакеты (--force-dirty — закрыть без
сохранения). `quit-editor` через drop, затем `taskkill /PID` без /F; процесс проверяется по PID. Закрывать слоты по
одному: кэш AssetRegistry пишется при выходе.

Общие записи (`um_masters.py build`, `control_scene.py`): shared_write_guard() отказывает, пока у проекта больше одного
UnrealEditor (UE7A_SHARED_WRITE_OK=1 — осознанный обход).
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

# в редакторе (ue_py/_run.py) у модуля нет __file__: путь берётся из ARGS["script"]
_SELF = Path(globals()["__file__"] if "__file__" in globals() else globals()["ARGS"]["script"]).resolve()
REPO = _SELF.parents[3]
MATLIB = REPO / "tools" / "art" / "material_library"
REVIEW = REPO / "tools" / "tripo-pipeline" / "review"
UPROJECT = REPO / "unreal" / "Unmatched" / "Unmatched.uproject"
UE_ROOT = Path(os.environ.get("UE_ROOT", r"C:\Program Files\Epic Games\UE_5.8"))
UE_EDITOR = UE_ROOT / "Engine" / "Binaries" / "Win64" / "UnrealEditor.exe"
CONSOLE_DROP_PY = REVIEW / "ue_py" / "console_drop.py"
RUN_PY = REVIEW / "ue_py" / "_run.py"
TMP = Path(os.environ.get("UE7A_SLOT_ROOT", "C:/tmp"))
REGISTRY = TMP / "ue7a-slots.json"
PORT_BASE = 8123
MAX_SLOT = 9
RES = (2033, 1216)  # рецепт пилота (ue-import-package.md §1 п.1)
NO_AUTOSTART = ("-ini:EditorPerProjectUserSettings:[/Script/ModelContextProtocolEngine.ModelContextProtocolSettings]:"
                "bAutoStartServer=False")
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000
EXIT_OK, EXIT_FAIL, EXIT_USAGE, EXIT_REFUSED, EXIT_TIMEOUT = 0, 1, 2, 3, 4

if str(MATLIB) not in sys.path:
    sys.path.insert(0, str(MATLIB))
import ue_lock  # noqa: E402


class SlotError(Exception):
    def __init__(self, message: str, code: int = EXIT_REFUSED):
        super().__init__(message)
        self.code = code


class SharedWriteRefused(SlotError):
    pass


# ---------------------------------------------------------------------------------------------- адреса слота
def check_slot(n) -> int:
    n = int(n)
    if n < 0 or n > MAX_SLOT:
        raise SlotError("слот %r: допустимо 0..%d" % (n, MAX_SLOT), EXIT_USAGE)
    return n


def port_of(n: int) -> int:
    return PORT_BASE + check_slot(n)


def default_workdir(n: int) -> Path:
    return TMP / ("ue7a-slot%d" % check_slot(n))


def slot_paths(n: int, workdir: Path | None = None) -> dict:
    w = Path(workdir) if workdir else default_workdir(n)
    return {"slot": check_slot(n), "port": port_of(n), "url": "http://127.0.0.1:%d/mcp" % port_of(n),
            "lock": ue_lock.lock_path_for_slot(n).as_posix(), "workdir": w.as_posix(), "drop": (w / "drop").as_posix(),
            "log": (w / "editor.log").as_posix(), "pid_file": (w / "editor.pid").as_posix()}


def slot_env(n: int, workdir: Path | None = None, hero: str | None = None) -> dict:
    p = slot_paths(n, workdir)
    owner = "7a-slot%d" % p["slot"] + ("-" + hero if hero else "")
    return {"UE_EDITOR_SLOT": str(p["slot"]), "UE_MCP_URL": p["url"], "UE_EDITOR_LOCK": p["lock"],
            "UE_CONSOLE_DROP": p["drop"], "UE_LOCK_OWNER": owner}


def format_env(env: dict, fmt: str = "bash") -> str:
    if fmt == "json":
        return json.dumps(env, ensure_ascii=False, indent=1)
    if fmt == "ps":
        return "\n".join("$env:%s = '%s'" % (k, v.replace("'", "''")) for k, v in env.items())
    return "\n".join("export %s='%s'" % (k, v.replace("'", "'\\''")) for k, v in env.items())


def editor_command(n: int, workdir: Path | None = None, res=RES, exe: Path = UE_EDITOR,
                   uproject: Path = UPROJECT) -> str:
    """Командная строка слота (строкой: -ExecCmds="…" в форме рецепта пилота). Пути без пробелов, кроме exe."""
    p = slot_paths(n, workdir)
    for label, val in (("uproject", uproject.as_posix()), ("console_drop.py", CONSOLE_DROP_PY.as_posix()),
                       ("workdir", p["workdir"])):
        if " " in val:
            raise SlotError("%s с пробелом не доходит до -ExecCmds: %s" % (label, val), EXIT_USAGE)
    exec_cmds = "ModelContextProtocol.StartServer %d,py %s %s" % (p["port"], CONSOLE_DROP_PY.as_posix(), p["drop"])
    parts = ['"%s"' % Path(exe), uproject.as_posix(), "-ModelContextProtocolPort=%d" % p["port"], NO_AUTOSTART,
             '-ExecCmds="%s"' % exec_cmds, "-RenderOffScreen", "-ForceRes", "-ResX=%d" % res[0], "-ResY=%d" % res[1],
             "-unattended", "-nosplash", "-NoSound", "-abslog=%s" % p["log"]]
    return " ".join(parts)


# ---------------------------------------------------------------------------------------------- процессы и порты
def port_listening(port: int, host: str = "127.0.0.1", timeout: float = 0.5) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        return s.connect_ex((host, port)) == 0
    finally:
        s.close()


def _norm(text: str) -> str:
    return (text or "").replace("\\", "/").lower()


def editor_processes(uproject: Path = UPROJECT, procs=None) -> list[dict]:
    """UnrealEditor.exe этого проекта: [{pid, cmdline, agent, port}]. procs — для тестов: [(pid, name, cmdline)]."""
    if procs is None:
        try:
            import psutil  # noqa: PLC0415
        except ImportError:
            print("WARNING: editor_slot: нет psutil, редакторы проекта не перечислены", file=sys.stderr)
            return []
        procs = []
        for pr in psutil.process_iter(["pid", "name"]):
            try:
                if (pr.info["name"] or "").lower() != "unrealeditor.exe":
                    continue
                procs.append((pr.info["pid"], pr.info["name"], " ".join(pr.cmdline())))
            except Exception:  # noqa: BLE001 - исчез или нет доступа
                continue
    want = _norm(uproject.as_posix())
    out = []
    for pid, name, cmd in procs:
        if (name or "").lower() != "unrealeditor.exe" or want not in _norm(cmd):
            continue
        low = _norm(cmd)
        port = None
        if "-modelcontextprotocolport=" in low:
            tail = low.split("-modelcontextprotocolport=", 1)[1]
            digits = "".join(ch for ch in tail[:6] if ch.isdigit())
            port = int(digits) if digits else None
        out.append({"pid": int(pid), "cmdline": cmd, "port": port,
                    "agent": "-unattended" in low and "-renderoffscreen" in low})
    return out


def pid_cmdline(pid: int) -> str:
    try:
        import psutil  # noqa: PLC0415

        return " ".join(psutil.Process(int(pid)).cmdline())
    except Exception:  # noqa: BLE001
        return ""


def is_our_editor(pid: int, paths: dict, cmdline: str | None = None) -> bool:
    cmd = _norm(pid_cmdline(pid) if cmdline is None else cmdline)
    return bool(cmd) and _norm("-abslog=" + paths["log"]) in cmd and ("-modelcontextprotocolport=%d" % paths["port"]) in cmd


def free_ram_gb() -> float | None:
    try:
        import psutil  # noqa: PLC0415

        return psutil.virtual_memory().available / 2 ** 30
    except Exception:  # noqa: BLE001
        return None


def shared_write_guard(action: str, procs=None, environ=None) -> list[dict]:
    """Отказ общей записи (мастер-материалы, контрольный уровень), пока у проекта больше одного UnrealEditor:
    другой слот держит те же пакеты в памяти. UE7A_SHARED_WRITE_OK=1 — обход."""
    env = os.environ if environ is None else environ
    eds = editor_processes(procs=procs)
    if len(eds) > 1 and env.get("UE7A_SHARED_WRITE_OK", "").strip() != "1":
        raise SharedWriteRefused(
            "%s: открыто %d редактора проекта (PID %s); общие ассеты пишет только один редактор (ДС-3a). Закройте "
            "слоты (editor_slot.py stop) или задайте UE7A_SHARED_WRITE_OK=1" % (
                action, len(eds), ", ".join(str(e["pid"]) for e in eds)))
    return eds


# ---------------------------------------------------------------------------------------------- реестр
def load_registry(path: Path = REGISTRY) -> dict:
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        doc = {}
    if not isinstance(doc, dict):
        doc = {}
    doc.setdefault("schema", "unmatched.ue7a-slots/1")
    doc.setdefault("slots", {})
    return doc


def save_registry(doc: dict, path: Path = REGISTRY) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp.%d" % os.getpid())
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def update_registry(fn, path: Path = REGISTRY):
    """fn(doc) под короткой блокировкой реестра (два start одновременно не теряют записи)."""
    with ue_lock.ue_lock("ue7a-slots registry", owner="editor_slot", poll_s=0.5, heartbeat_s=0,
                         lock=Path(str(path) + ".lock"), max_hold_s=120, wait_timeout_s=120):
        doc = load_registry(path)
        out = fn(doc)
        save_registry(doc, path)
        return out


def live_entries(doc: dict) -> dict:
    return {k: v for k, v in doc.get("slots", {}).items() if ue_lock.pid_alive(int(v.get("pid") or 0))}


# ---------------------------------------------------------------------------------------------- консоль drop
def drop_command(drop: str, command: str, wait_s: float = 60.0, wait_done: bool = True) -> dict | None:
    """Протокол console_drop.py: cmd-<seq>.json -> done-<seq>.json."""
    d = Path(drop)
    if not (d / "ready.json").is_file():
        raise SlotError("%s: нет ready.json (console_drop.py не запущен в редакторе)" % d, EXIT_FAIL)
    seq = int(time.time() * 1000)
    while (d / ("cmd-%d.json" % seq)).exists() or (d / ("done-%d.json" % seq)).exists():
        seq += 1
    path = d / ("cmd-%d.json" % seq)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps({"seq": seq, "command": command}), encoding="utf-8")
    os.replace(tmp, path)
    if not wait_done:
        return None
    done = d / ("done-%d.json" % seq)
    deadline = time.time() + wait_s
    while time.time() < deadline:
        if done.is_file():
            try:
                return json.loads(done.read_text(encoding="utf-8"))
            except ValueError:
                pass
        time.sleep(0.2)
    raise SlotError("drop %s: команда %r не выполнена за %.0f с" % (d, command, wait_s), EXIT_TIMEOUT)


def dirty_packages(paths: dict, timeout: float = 120.0) -> dict:
    """Грязные пакеты слота: эта же задача в редакторе через ue_py/_run.py (как discard_master.py)."""
    w = Path(paths["workdir"])
    out = w / ("dirty-%d.json" % int(time.time() * 1000))
    args = out.with_suffix(".args.json")
    args.write_text(json.dumps({"script": _SELF.as_posix(), "out": out.as_posix(),
                                "task": "dirty"}), encoding="utf-8")
    try:
        drop_command(paths["drop"], 'py "%s" %s' % (RUN_PY.as_posix(), args.as_posix()), wait_s=timeout)
        deadline = time.time() + timeout
        while time.time() < deadline and not out.is_file():
            time.sleep(0.2)
        if not out.is_file():
            raise SlotError("нет %s после проверки грязных пакетов" % out, EXIT_TIMEOUT)
        res = json.loads(out.read_text(encoding="utf-8"))
        if res.get("error"):
            raise SlotError("проверка грязных пакетов: %s" % res["error"], EXIT_FAIL)
        return res
    finally:
        for f in (args, out, Path(str(out) + ".started")):
            try:
                f.unlink()
            except OSError:
                pass


def _ue_main(args, u):  # выполняется в редакторе (ue_py/_run.py)
    res = {"task": args.get("task")}
    res["dirty_content"] = [str(p.get_name()) for p in u.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    res["dirty_maps"] = [str(p.get_name()) for p in u.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    with open(args["out"], "w", encoding="utf-8", newline="\n") as h:
        json.dump(res, h, indent=1)


# ---------------------------------------------------------------------------------------------- команды
def cmd_start(a) -> int:
    n = check_slot(a.slot)
    paths = slot_paths(n, a.workdir)
    cmd = editor_command(n, a.workdir)
    if a.dry_run:
        print(json.dumps({"dry_run": True, **paths, "cmdline": cmd, "env": slot_env(n, a.workdir, a.hero)},
                         ensure_ascii=False, indent=1))
        return EXIT_OK
    doc = load_registry()
    old = doc["slots"].get(str(n))
    if old and ue_lock.pid_alive(int(old.get("pid") or 0)):
        raise SlotError("слот %d занят: PID %s (герой %s)" % (n, old.get("pid"), old.get("hero")))
    if port_listening(paths["port"]):
        raise SlotError("порт %d уже слушает (другой редактор или процесс): выберите другой слот" % paths["port"])
    eds = editor_processes()
    inter = [e for e in eds if not e["agent"]]
    if inter and not a.allow_interactive:
        raise SlotError("открыт интерактивный редактор проекта (PID %s): гейт SKILL.md §5 п.7, слот не поднимаю"
                        % ", ".join(str(e["pid"]) for e in inter))
    ram = free_ram_gb()
    if ram is not None and ram < a.min_free_gb:
        raise SlotError("свободно ОЗУ %.1f ГБ < %.1f ГБ (--min-free-gb): ещё один редактор не поднимаю" % (ram, a.min_free_gb))
    live = live_entries(doc)
    last = max((float(v.get("started_epoch") or 0) for v in live.values()), default=0.0)
    wait = a.stagger - (time.time() - last)
    if live and wait > 0:
        print("STAGGER: слот стартовал %.0f с назад, жду %.0f с" % (time.time() - last, wait), flush=True)
        time.sleep(wait)
    w = Path(paths["workdir"])
    (w / "drop").mkdir(parents=True, exist_ok=True)
    for stale in [w / "drop" / "ready.json"] + list((w / "drop").glob("cmd-*.json")):
        try:
            stale.unlink()
        except OSError:
            pass
    t0 = time.time()
    proc = subprocess.Popen(cmd, cwd=str(REPO), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            creationflags=(DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP) if os.name == "nt" else 0)
    Path(paths["pid_file"]).write_text("%d\n" % proc.pid, encoding="utf-8")
    entry = dict(paths, pid=proc.pid, hero=a.hero, cmdline=cmd, started=time.strftime("%Y-%m-%dT%H:%M:%S"),
                 started_epoch=round(t0, 3), ram_free_gb_before=round(ram, 1) if ram is not None else None)
    update_registry(lambda d: d["slots"].__setitem__(str(n), entry))
    print("START slot=%d pid=%d port=%d hero=%s" % (n, proc.pid, paths["port"], a.hero or "-"), flush=True)
    deadline = t0 + a.wait
    ready = (w / "drop" / "ready.json")
    while time.time() < deadline:
        if proc.poll() is not None:
            raise SlotError("редактор слота %d вышел с кодом %s при старте; см. %s" % (n, proc.returncode, paths["log"]),
                            EXIT_FAIL)
        if port_listening(paths["port"]) and ready.is_file():
            secs = round(time.time() - t0, 1)
            update_registry(lambda d: d["slots"].get(str(n), {}).__setitem__("ready_s", secs))
            print("READY slot=%d pid=%d port=%d in %.1f s" % (n, proc.pid, paths["port"], secs), flush=True)
            print(format_env(slot_env(n, a.workdir, a.hero), "bash"))
            return EXIT_OK
        time.sleep(2.0)
    print("TIMEOUT: слот %d (PID %d) не готов за %.0f с (порт %s, ready.json %s); процесс не гашу, см. %s"
          % (n, proc.pid, a.wait, port_listening(paths["port"]), ready.is_file(), paths["log"]), file=sys.stderr)
    return EXIT_TIMEOUT


def cmd_env(a) -> int:
    n = check_slot(a.slot)
    entry = load_registry()["slots"].get(str(n)) or {}
    workdir = a.workdir or entry.get("workdir")
    print(format_env(slot_env(n, Path(workdir) if workdir else None, a.hero or entry.get("hero")), a.format))
    return EXIT_OK


def cmd_list(_a) -> int:
    doc = load_registry()
    rows = []
    for k, v in sorted(doc["slots"].items(), key=lambda kv: int(kv[0])):
        lock = Path(v.get("lock") or ue_lock.lock_path_for_slot(int(k)))
        holder = ue_lock.parse_lock(lock.read_text(encoding="utf-8", errors="replace")) if lock.is_file() else None
        rows.append({"slot": int(k), "hero": v.get("hero"), "pid": v.get("pid"),
                     "alive": ue_lock.pid_alive(int(v.get("pid") or 0)), "port": v.get("port"),
                     "listening": port_listening(int(v.get("port") or 0)) if v.get("port") else False,
                     "lock": lock.as_posix(), "lock_step": holder.get("step") if holder else None,
                     "started": v.get("started"), "ready_s": v.get("ready_s")})
    known = {int(r["pid"] or 0) for r in rows}
    other = [{"pid": e["pid"], "port": e["port"], "agent": e["agent"]} for e in editor_processes() if e["pid"] not in known]
    print(json.dumps({"slots": rows, "unregistered_editors": other}, ensure_ascii=False, indent=1))
    return EXIT_OK


def cmd_stop(a) -> int:
    n = check_slot(a.slot)
    doc = load_registry()
    entry = doc["slots"].get(str(n))
    if not entry:
        raise SlotError("слот %d не в реестре %s" % (n, REGISTRY), EXIT_USAGE)
    paths = slot_paths(n, Path(entry["workdir"]))
    pid = int(entry.get("pid") or 0)
    if not ue_lock.pid_alive(pid):
        update_registry(lambda d: d["slots"].pop(str(n), None))
        print("STOP slot=%d: PID %d уже завершён; запись реестра снята" % (n, pid))
        return EXIT_OK
    if not is_our_editor(pid, paths):
        raise SlotError("PID %d — не редактор слота %d (нет -abslog=%s / -ModelContextProtocolPort=%d в командной "
                        "строке): не закрываю" % (pid, n, paths["log"], paths["port"]))
    lock = Path(paths["lock"])
    if lock.is_file() and not a.force_lock:
        holder = ue_lock.parse_lock(lock.read_text(encoding="utf-8", errors="replace"))
        if holder.get("pid") and ue_lock.pid_alive(holder["pid"]):
            raise SlotError("блокировка слота занята живым шагом (%s): не закрываю" % ue_lock.describe(holder))
    if not a.skip_dirty_check:
        dirty = dirty_packages(paths)
        left = (dirty.get("dirty_content") or []) + (dirty.get("dirty_maps") or [])
        if left and not a.force_dirty:
            raise SlotError("в редакторе слота %d грязные пакеты %s: сохраните результат или сбросьте "
                            "(discard_master.py), либо --force-dirty (закрыть без сохранения)" % (n, left))
        if left:
            print("FORCE-DIRTY: закрываю без сохранения %s" % left, flush=True)
    t0 = time.time()
    how = "quit-editor"
    try:
        drop_command(paths["drop"], "quit-editor", wait_done=False)
    except SlotError as exc:
        print("drop: %s; taskkill /PID %d" % (exc, pid), flush=True)
        how = "taskkill"
        subprocess.run(["taskkill", "/PID", str(pid)], capture_output=True,
                       creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0)
    deadline = t0 + a.timeout
    while time.time() < deadline and ue_lock.pid_alive(pid):
        time.sleep(1.0)
    if ue_lock.pid_alive(pid) and how == "quit-editor":
        how = "quit-editor+taskkill"
        subprocess.run(["taskkill", "/PID", str(pid)], capture_output=True,
                       creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0)
        end = time.time() + 60
        while time.time() < end and ue_lock.pid_alive(pid):
            time.sleep(1.0)
    if ue_lock.pid_alive(pid):
        print("STOP slot=%d: PID %d жив после %s (%.0f с); /F — решение оркестратора" % (n, pid, how, time.time() - t0),
              file=sys.stderr)
        return EXIT_FAIL
    update_registry(lambda d: d["slots"].pop(str(n), None))
    print("STOP slot=%d pid=%d closed by %s in %.1f s" % (n, pid, how, time.time() - t0))
    return EXIT_OK


def cmd_check_shared_write(a) -> int:
    eds = shared_write_guard(a.action)
    print("SHARED-WRITE OK: %s (редакторов проекта: %d)" % (a.action, len(eds)))
    return EXIT_OK


def main(argv=None) -> int:
    import argparse

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("start")
    p.add_argument("slot", type=int)
    p.add_argument("--hero", default=None, help="KEY героя (в реестр и UE_LOCK_OWNER)")
    p.add_argument("--workdir", type=Path, default=None, help="каталог слота (drop/, editor.log, editor.pid); "
                                                              "по умолчанию C:/tmp/ue7a-slot<N>")
    p.add_argument("--wait", type=float, default=900.0, help="ждать готовности, с")
    p.add_argument("--stagger", type=float, default=60.0, help="минимум секунд после старта другого живого слота")
    p.add_argument("--min-free-gb", type=float, default=8.0)
    p.add_argument("--allow-interactive", action="store_true", help="поднять рядом с интерактивным редактором проекта")
    p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("env")
    p.add_argument("slot", type=int)
    p.add_argument("--workdir", type=Path, default=None)
    p.add_argument("--hero", default=None)
    p.add_argument("--format", choices=["bash", "ps", "json"], default="bash")
    sub.add_parser("list")
    p = sub.add_parser("stop")
    p.add_argument("slot", type=int)
    p.add_argument("--timeout", type=float, default=180.0)
    p.add_argument("--force-dirty", action="store_true", help="закрыть с грязными пакетами без сохранения")
    p.add_argument("--force-lock", action="store_true", help="закрыть, хотя блокировка слота занята")
    p.add_argument("--skip-dirty-check", action="store_true")
    p = sub.add_parser("check-shared-write")
    p.add_argument("action")
    a = ap.parse_args(argv)
    try:
        return {"start": cmd_start, "env": cmd_env, "list": cmd_list, "stop": cmd_stop,
                "check-shared-write": cmd_check_shared_write}[a.cmd](a)
    except SlotError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return exc.code


if __name__ == "__ue_task__":
    _ue_main(ARGS, unreal)  # noqa: F821 - ARGS и unreal подставляет ue_py/_run.py
elif __name__ == "__main__":
    sys.exit(main())
