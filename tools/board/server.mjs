// Локальная канбан-доска задач: статика + API + SSE + живой rescan по fs.watch.
// Только stdlib Node. Запуск: node tools/board/server.mjs [--port N] [--overrides <путь>]

import { createServer } from "node:http";
import fs, {
  existsSync,
  mkdirSync,
  readFileSync,
  renameSync,
  statSync,
} from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { buildBoard, STATUSES } from "./scanner.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const BOARD_ROOT = __dirname;
const PUBLIC_DIR = path.join(BOARD_ROOT, "public");
const DOCS_ROOT = path.resolve(BOARD_ROOT, "..", "..", "docs", "game-design");
const DEFAULT_PORT = 8787;
const DEBOUNCE_MS = 300;
const HEARTBEAT_MS = 15_000;
const POLL_MS = 5_000;
const MAX_PATCH_BODY = 64 * 1024;

// --- CLI -------------------------------------------------------------------

function parseArgs(argv) {
  const out = {
    port: DEFAULT_PORT,
    overrides: path.join(BOARD_ROOT, "overrides.json"),
  };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === "--port") {
      const value = Number(argv[++i]);
      if (!Number.isInteger(value) || value < 0 || value > 65535) {
        failArg(`--port ожидает целое 0..65535, получено: ${argv[i]}`);
      }
      out.port = value;
    } else if (arg === "--overrides") {
      const value = argv[++i];
      if (!value) failArg("--overrides ожидает путь к файлу");
      out.overrides = path.resolve(value);
    } else if (arg === "--help" || arg === "-h") {
      console.log(
        "Использование: node server.mjs [--port N] [--overrides <файл>]",
      );
      console.log("  --port      порт (0 = эфемерный); по умолчанию 8787");
      console.log(
        "  --overrides путь к файлу ручных переопределений (по умолчанию tools/board/overrides.json)",
      );
      process.exit(0);
    } else {
      failArg(`неизвестный аргумент: ${arg}`);
    }
  }
  return out;
}

function failArg(message) {
  console.error(`[board] ${message}`);
  process.exit(1);
}

const args = parseArgs(process.argv.slice(2));
const OVERRIDES_PATH = args.overrides;

// --- Состояние доски --------------------------------------------------------

let board = buildBoard(DOCS_ROOT, OVERRIDES_PATH);
let rev = 1;
let serialized = JSON.stringify(board.tasks);

const sseClients = new Set();

function snapshotPayload() {
  return JSON.stringify({ rev, tasks: board.tasks });
}

function broadcastTasks() {
  if (sseClients.size === 0) return;
  const frame = `event: tasks\ndata: ${snapshotPayload()}\n\n`;
  for (const res of sseClients) {
    try {
      res.write(frame);
    } catch {
      sseClients.delete(res);
    }
  }
}

function rescan() {
  try {
    const next = buildBoard(DOCS_ROOT, OVERRIDES_PATH);
    const nextSerialized = JSON.stringify(next.tasks);
    if (nextSerialized !== serialized) {
      board = next;
      serialized = nextSerialized;
      rev += 1;
      broadcastTasks();
    }
  } catch (err) {
    console.error(`[board] rescan не удался: ${err.message}`);
  }
}

// --- Overrides: атомарная запись (tmp + rename) -----------------------------

function writeOverrides(data) {
  const dir = path.dirname(OVERRIDES_PATH);
  mkdirSync(dir, { recursive: true });
  const tmp = `${OVERRIDES_PATH}.tmp-${process.pid}`;
  fs.writeFileSync(tmp, `${JSON.stringify(data, null, 2)}\n`, "utf8");
  renameSync(tmp, OVERRIDES_PATH);
}

function readOverridesMap() {
  if (!existsSync(OVERRIDES_PATH)) return {};
  try {
    const parsed = JSON.parse(readFileSync(OVERRIDES_PATH, "utf8"));
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed))
      return parsed;
  } catch {
    // Битый файл перезапишется первым же PATCH; merge тем временем его игнорирует.
  }
  return {};
}

// --- Watchers: recursive -> non-recursive -> mtime/size polling -------------

function walkFiles(rootDir, into) {
  let entries;
  try {
    entries = fs.readdirSync(rootDir, { withFileTypes: true });
  } catch {
    return;
  }
  for (const entry of entries) {
    const full = path.join(rootDir, entry.name);
    if (entry.isDirectory()) {
      walkFiles(full, into);
    } else if (entry.isFile()) {
      into.push(full);
    }
  }
}

function fingerprint(file) {
  try {
    const st = statSync(file);
    return `${st.mtimeMs}:${st.size}`;
  } catch {
    return "gone";
  }
}

class RootWatcher {
  /**
   * @param {string} rootDir каталог для наблюдения (не файл)
   * @param {(relName: string|null) => boolean} accept фильтр по базовому имени
   * @param {() => void} onChange
   * @param {string} label
   */
  constructor(rootDir, accept, onChange, label) {
    this.rootDir = rootDir;
    this.accept = accept;
    this.onChange = onChange;
    this.label = label;
    this.watchers = [];
    this.pollTimer = null;
    this.pollFingerprints = null;
    this.level = "init";
  }

  start() {
    if (!existsSync(this.rootDir)) {
      console.error(
        `[board] каталог наблюдения не найден: ${this.rootDir} — поллинг`,
      );
      this.startPolling();
      return;
    }
    try {
      const w = fs.watch(
        this.rootDir,
        { recursive: true },
        (eventType, filename) => this.handleEvent(eventType, filename),
      );
      w.on("error", (err) => this.fallback(err));
      this.watchers.push(w);
      this.level = "recursive";
      return;
    } catch (err) {
      this.fallback(err);
    }
  }

  handleEvent(eventType, filename) {
    if (filename !== null && filename !== undefined) {
      if (!this.accept(path.basename(filename))) return;
    }
    this.onChange();
  }

  fallback(err) {
    if (this.level === "polling") return;
    console.error(
      `[board] recursive fs.watch недоступен для ${this.label} (${err.code || err.message}) — ` +
        "переходим на нерекурсивные watcher'ы по подкаталогам",
    );
    this.closeWatchers();
    // Нерекурсивные watcher'ы на корне и каждом подкаталоге (обход при старте).
    const dirs = [this.rootDir];
    walkDirs(this.rootDir, dirs);
    try {
      for (const dir of dirs) {
        const w = fs.watch(dir, (eventType, filename) =>
          this.handleEvent(eventType, filename),
        );
        w.on("error", () => this.startPolling());
        this.watchers.push(w);
      }
      this.level = "flat";
      return;
    } catch {
      this.startPolling();
    }
  }

  startPolling() {
    if (this.level === "polling") return;
    this.closeWatchers();
    this.level = "polling";
    console.error(
      `[board] watchers для ${this.label} недоступны — поллинг mtime+size каждые ${POLL_MS / 1000} с`,
    );
    const files = [];
    walkFiles(this.rootDir, files);
    this.pollFingerprints = new Map(files.map((f) => [f, fingerprint(f)]));
    this.pollTimer = setInterval(() => {
      const files2 = [];
      walkFiles(this.rootDir, files2);
      const next = new Map(files2.map((f) => [f, fingerprint(f)]));
      let changed =
        next.size !== this.pollFingerprints.size ||
        [...next].some(([f, fp]) => this.pollFingerprints.get(f) !== fp);
      this.pollFingerprints = next;
      if (changed) this.onChange();
    }, POLL_MS);
    this.pollTimer.unref?.();
  }

  closeWatchers() {
    for (const w of this.watchers) {
      try {
        w.close();
      } catch {
        // уже закрыт
      }
    }
    this.watchers = [];
  }

  stop() {
    this.closeWatchers();
    if (this.pollTimer) clearInterval(this.pollTimer);
    this.pollTimer = null;
  }
}

function walkDirs(rootDir, into) {
  let entries;
  try {
    entries = fs.readdirSync(rootDir, { withFileTypes: true });
  } catch {
    return;
  }
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const full = path.join(rootDir, entry.name);
    into.push(full);
    walkDirs(full, into);
  }
}

let rescanTimer = null;
function scheduleRescan() {
  if (rescanTimer !== null) return;
  rescanTimer = setTimeout(() => {
    rescanTimer = null;
    rescan();
  }, DEBOUNCE_MS);
}

function isInside(childDir, rootDir) {
  const rel = path.relative(rootDir, childDir);
  return rel === "" || (!rel.startsWith("..") && !path.isAbsolute(rel));
}

function startWatchers() {
  const docExt = /\.(md|csv|json)$/i;
  const overridesName = path.basename(OVERRIDES_PATH);
  const watchers = [
    new RootWatcher(
      DOCS_ROOT,
      (base) => docExt.test(base),
      scheduleRescan,
      "docs/game-design",
    ),
    new RootWatcher(
      BOARD_ROOT,
      (base) => base === overridesName,
      scheduleRescan,
      "tools/board",
    ),
  ];
  const overridesDir = path.dirname(OVERRIDES_PATH);
  if (
    !isInside(overridesDir, DOCS_ROOT) &&
    !isInside(overridesDir, BOARD_ROOT)
  ) {
    watchers.push(
      new RootWatcher(
        overridesDir,
        (base) => base === overridesName,
        scheduleRescan,
        `overrides (${overridesDir})`,
      ),
    );
  }
  for (const w of watchers) w.start();
  return watchers;
}

const watchers = startWatchers();

// --- HTTP -------------------------------------------------------------------

const MIME = {
  ".html": "text/html",
  ".htm": "text/html",
  ".css": "text/css",
  ".js": "text/javascript",
  ".mjs": "text/javascript",
  ".json": "application/json",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".ico": "image/x-icon",
  ".txt": "text/plain",
  ".map": "application/json",
  ".webp": "image/webp",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
};

function contentTypeFor(ext) {
  const mime = MIME[ext];
  if (!mime) return "application/octet-stream";
  return mime.startsWith("text/") ? `${mime};charset=utf-8` : mime;
}

function sendJson(res, code, data, extraHeaders) {
  const body = JSON.stringify(data);
  res.writeHead(code, {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
    ...extraHeaders,
  });
  res.end(body);
}

function serveStatic(req, res, pathname) {
  let rel = decodeURIComponent(pathname);
  if (rel === "/" || rel === "") rel = "/index.html";
  const target = path.normalize(path.join(PUBLIC_DIR, rel));
  if (target !== PUBLIC_DIR && !target.startsWith(PUBLIC_DIR + path.sep)) {
    sendJson(res, 404, { error: "not found" });
    return;
  }
  let st;
  try {
    st = statSync(target);
  } catch {
    sendJson(res, 404, { error: "not found" });
    return;
  }
  if (!st.isFile()) {
    sendJson(res, 404, { error: "not found" });
    return;
  }
  const ext = path.extname(target).toLowerCase();
  let body;
  try {
    body = readFileSync(target);
  } catch {
    sendJson(res, 500, { error: "read failed" });
    return;
  }
  res.writeHead(200, {
    "Content-Type": contentTypeFor(ext),
    "Content-Length": body.length,
    "Cache-Control": "no-cache",
  });
  res.end(req.method === "HEAD" ? undefined : body);
}

function serveTasks(req, res) {
  sendJson(res, 200, board.tasks, { "X-Board-Rev": String(rev) });
}

function serveEvents(req, res) {
  res.writeHead(200, {
    "Content-Type": "text/event-stream; charset=utf-8",
    "Cache-Control": "no-cache, no-transform",
    Connection: "keep-alive",
    "X-Accel-Buffering": "no",
  });
  // Немедленный начальный снапшот — часть контракта, а не любезность.
  res.write(`event: init\ndata: ${snapshotPayload()}\n\n`);
  const heartbeat = setInterval(() => {
    try {
      res.write(": ping\n\n"); // комментарий, событием не является
    } catch {
      /* закрытие обработает 'close' */
    }
  }, HEARTBEAT_MS);
  sseClients.add(res);
  const cleanup = () => {
    clearInterval(heartbeat);
    sseClients.delete(res);
  };
  req.on("close", cleanup);
  res.on("error", cleanup);
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    req.on("data", (chunk) => {
      size += chunk.length;
      if (size > MAX_PATCH_BODY) {
        reject(new Error("тело слишком большое"));
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });
    req.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
    req.on("error", reject);
  });
}

async function servePatch(req, res, id) {
  const task = board.tasks.find((t) => t.id === id);
  if (!task) {
    sendJson(res, 404, { error: `задача не найдена: ${id}` });
    return;
  }
  let payload;
  try {
    payload = JSON.parse(await readBody(req));
  } catch {
    sendJson(res, 400, { error: "ожидается корректный JSON в теле" });
    return;
  }
  if (
    payload === null ||
    typeof payload !== "object" ||
    Array.isArray(payload)
  ) {
    sendJson(res, 400, { error: "ожидается объект {status, note?}" });
    return;
  }
  const { status, note } = payload;
  if (!STATUSES.includes(status)) {
    sendJson(res, 400, {
      error: `status должен быть одним из: ${STATUSES.join(", ")}`,
    });
    return;
  }
  if (note !== undefined && typeof note !== "string") {
    sendJson(res, 400, { error: "note должен быть строкой" });
    return;
  }
  const overrides = readOverridesMap();
  const prev =
    overrides[id] && typeof overrides[id] === "object" ? overrides[id] : {};
  // baseStatus фиксирует статус скана на момент ручного решения:
  // изменившийся после этого скан даст флаг diverged.
  const scanStatus = board.scanStatuses.get(id) ?? null;
  const entry = {
    status,
    updatedAt: new Date().toISOString(),
    baseStatus: scanStatus,
  };
  if (note !== undefined) entry.note = note;
  else if (typeof prev.note === "string") entry.note = prev.note;
  if (typeof prev.title === "string" && prev.title) entry.title = prev.title;
  overrides[id] = entry;
  try {
    writeOverrides(overrides);
  } catch (err) {
    sendJson(res, 500, {
      error: `не удалось записать overrides: ${err.message}`,
    });
    return;
  }
  rescan(); // обновит board, поднимет rev и разошлёт 'tasks' всем (включая эту вкладку)
  const updated = board.tasks.find((t) => t.id === id);
  sendJson(res, 200, { ok: true, task: updated });
}

const server = createServer((req, res) => {
  const url = new URL(req.url, "http://localhost");
  const pathname = url.pathname;
  try {
    if (req.method === "GET" && pathname === "/api/tasks") {
      serveTasks(req, res);
    } else if (req.method === "GET" && pathname === "/api/events") {
      serveEvents(req, res);
    } else if (req.method === "PATCH" && pathname.startsWith("/api/tasks/")) {
      const id = decodeURIComponent(pathname.slice("/api/tasks/".length));
      if (!id || id.includes("/")) {
        sendJson(res, 404, { error: "not found" });
        return;
      }
      servePatch(req, res, id).catch((err) => {
        console.error(`[board] ошибка PATCH ${id}: ${err.message}`);
        if (!res.headersSent) sendJson(res, 500, { error: "internal error" });
        else res.end();
      });
    } else if (req.method === "GET" || req.method === "HEAD") {
      serveStatic(req, res, pathname);
    } else {
      sendJson(res, 405, { error: "method not allowed" });
    }
  } catch (err) {
    console.error(
      `[board] ошибка обработки ${req.method} ${pathname}: ${err.message}`,
    );
    if (!res.headersSent) sendJson(res, 500, { error: "internal error" });
    else res.end();
  }
});

server.on("clientError", (err, socket) => {
  if (socket.writable) socket.end("HTTP/1.1 400 Bad Request\r\n\r\n");
});

function shutdown() {
  for (const w of watchers) w.stop();
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(0), 1500).unref();
}
process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);

server.listen(args.port, "127.0.0.1", () => {
  const { port } = server.address();
  console.log(`BOARD_READY ${port}`);
  console.log(`[board] доска: http://127.0.0.1:${port}/`);
  console.log(`[board] источники: ${DOCS_ROOT}`);
  console.log(`[board] overrides: ${OVERRIDES_PATH}`);
  console.log(`[board] задач: ${board.tasks.length}, rev ${rev}`);
});

server.on("error", (err) => {
  if (err.code === "EADDRINUSE") {
    console.error(
      `[board] порт ${args.port} занят; запустите с --port 0 для эфемерного порта`,
    );
  } else {
    console.error(`[board] ошибка сервера: ${err.message}`);
  }
  process.exit(1);
});
