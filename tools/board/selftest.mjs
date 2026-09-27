// Самопроверка доски: поднимает сервер на эфемерном порте с временным
// overrides-файлом, прогоняет API/SSE/PATCH-сценарий и гасит сервер.
// Запуск из корня проекта: node tools/board/selftest.mjs
// Выход: 0 — SELFTEST OK, 1 — провал (с причиной).

import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SERVER = path.join(__dirname, "server.mjs");
const TOTAL_TIMEOUT_MS = 30_000;
const READY_TIMEOUT_MS = 10_000;
const STEP_TIMEOUT_MS = 5_000;

class Fail extends Error {}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function withTimeout(promise, ms, label) {
  return Promise.race([
    promise,
    sleep(ms).then(() => {
      throw new Fail(`таймаут ${ms} мс: ${label}`);
    }),
  ]);
}

function request(port, method, reqPath, body) {
  return new Promise((resolve, reject) => {
    const req = http.request(
      {
        host: "127.0.0.1",
        port,
        method,
        path: reqPath,
        headers: body
          ? { "Content-Type": "application/json; charset=utf-8" }
          : undefined,
      },
      (res) => {
        const chunks = [];
        res.on("data", (c) => chunks.push(c));
        res.on("end", () =>
          resolve({
            status: res.statusCode,
            headers: res.headers,
            body: Buffer.concat(chunks).toString("utf8"),
          }),
        );
      },
    );
    req.on("error", reject);
    if (body) req.write(body);
    req.end();
  });
}

/** Открывает SSE-поток и резолвится с объектом-«монитором» накопленных событий. */
function openEventStream(port) {
  return new Promise((resolve, reject) => {
    const req = http.get(
      { host: "127.0.0.1", port, path: "/api/events" },
      (res) => {
        const state = {
          status: res.statusCode,
          headers: res.headers,
          text: "",
          sawEvent(name) {
            // именованное событие = строка 'event: <name>'; ': ping' сюда не попадает
            return new RegExp(`^event: ${name}$`, "m").test(state.text);
          },
          destroy: () => req.destroy(),
        };
        res.on("data", (chunk) => {
          state.text += chunk.toString("utf8");
        });
        resolve(state);
      },
    );
    req.on("error", reject);
  });
}

function waitFor(predicate, ms, label) {
  const started = Date.now();
  return (function tick() {
    if (predicate()) return Promise.resolve();
    if (Date.now() - started > ms) {
      return Promise.reject(new Fail(`таймаут ${ms} мс: ${label}`));
    }
    return sleep(100).then(tick);
  })();
}

async function run() {
  const tmp = mkdtempSync(path.join(os.tmpdir(), "board-selftest-"));
  const overridesPath = path.join(tmp, "overrides.json");
  const child = spawn(
    process.execPath,
    [SERVER, "--port", "0", "--overrides", overridesPath],
    { stdio: ["ignore", "pipe", "pipe"] },
  );

  let stderrTail = "";
  child.stderr.on("data", (c) => {
    stderrTail = (stderrTail + c.toString("utf8")).slice(-2000);
  });

  try {
    // Старт: ждём 'BOARD_READY <port>' в stdout.
    const port = await withTimeout(
      new Promise((resolve, reject) => {
        let acc = "";
        child.stdout.on("data", (c) => {
          acc += c.toString("utf8");
          const m = /BOARD_READY (\d+)/.exec(acc);
          if (m) resolve(Number(m[1]));
        });
        child.on("exit", (code) =>
          reject(new Fail(`сервер завершился до готовности (код ${code})`)),
        );
      }),
      READY_TIMEOUT_MS,
      "ожидание BOARD_READY в stdout",
    );

    // (1) GET / -> 200, charset=utf-8, есть <title
    const index = await request(port, "GET", "/");
    if (index.status !== 200)
      throw new Fail(`GET / => ${index.status}, ожидался 200`);
    const ctype = index.headers["content-type"] || "";
    if (!ctype.includes("charset=utf-8")) {
      throw new Fail(`GET / Content-Type без charset=utf-8: ${ctype}`);
    }
    if (!index.body.includes("<title")) {
      throw new Fail("GET /: в теле нет <title>");
    }

    // (2) GET /api/tasks -> непустой JSON-массив с id/status/type и >=1 GD-задачей
    const tasksRes = await request(port, "GET", "/api/tasks");
    if (tasksRes.status !== 200)
      throw new Fail(`GET /api/tasks => ${tasksRes.status}`);
    let tasks;
    try {
      tasks = JSON.parse(tasksRes.body);
    } catch (err) {
      throw new Fail(`GET /api/tasks: невалидный JSON (${err.message})`);
    }
    if (!Array.isArray(tasks) || tasks.length === 0) {
      throw new Fail("GET /api/tasks: ожидался непустой массив");
    }
    for (const t of tasks) {
      if (!t.id || !t.status || !t.type) {
        throw new Fail(
          `GET /api/tasks: у задачи нет id/status/type: ${JSON.stringify(t)}`,
        );
      }
    }
    if (!tasks.some((t) => t.id.startsWith("GD-"))) {
      throw new Fail("GET /api/tasks: нет ни одной GD-задачи");
    }

    // (3) GET /api/events -> text/event-stream и именованное событие init <= 5 c
    const stream = await openEventStream(port);
    try {
      if (stream.status !== 200)
        throw new Fail(`GET /api/events => ${stream.status}`);
      const sseType = stream.headers["content-type"] || "";
      if (!sseType.includes("text/event-stream")) {
        throw new Fail(`GET /api/events Content-Type: ${sseType}`);
      }
      await waitFor(
        () => stream.sawEvent("init"),
        STEP_TIMEOUT_MS,
        "событие init в SSE",
      );
    } catch (err) {
      stream.destroy();
      throw err;
    }

    // (4) PATCH planned-задачи {status:'in_progress'} -> 200; статус виден в
    //     GET /api/tasks; в SSE-потоке после PATCH приходит 'event: tasks'.
    const target = tasks.find((t) => t.status === "planned");
    if (!target)
      throw new Fail("нет ни одной задачи со статусом planned для PATCH");
    const patch = await request(
      port,
      "PATCH",
      `/api/tasks/${encodeURIComponent(target.id)}`,
      JSON.stringify({ status: "in_progress" }),
    );
    if (patch.status !== 200) {
      throw new Fail(
        `PATCH /api/tasks/${target.id} => ${patch.status}: ${patch.body}`,
      );
    }
    await waitFor(
      () => stream.sawEvent("tasks"),
      STEP_TIMEOUT_MS,
      "событие 'tasks' в SSE после PATCH",
    );
    const after = await request(port, "GET", "/api/tasks");
    const afterTasks = JSON.parse(after.body);
    const moved = afterTasks.find((t) => t.id === target.id);
    if (!moved || moved.status !== "in_progress") {
      throw new Fail(
        `после PATCH статус задачи ${target.id} не in_progress: ${JSON.stringify(moved)}`,
      );
    }
    stream.destroy();

    // (5) Завершение: kill -> exit, чистка tmp.
    const exited = new Promise((resolve) =>
      child.once("exit", (code) => resolve(code)),
    );
    child.kill();
    const code = await withTimeout(
      exited,
      READY_TIMEOUT_MS,
      "завершение сервера после kill",
    );
    if (code !== 0 && code !== null && code !== 1) {
      // SIGTERM на Windows даёт код 1; node с обработчиком — 0; допускаем оба.
      throw new Fail(`сервер завершился с неожиданным кодом ${code}`);
    }
  } finally {
    if (!child.killed) child.kill();
    rmSync(tmp, { recursive: true, force: true });
    if (stderrTail.trim()) {
      console.error("[selftest] stderr сервера (хвост):\n" + stderrTail.trim());
    }
  }

  console.log("SELFTEST OK");
}

const hardTimer = setTimeout(() => {
  console.error("SELFTEST FAIL: общий таймаут 30 с");
  process.exit(1);
}, TOTAL_TIMEOUT_MS);

run()
  .then(() => {
    clearTimeout(hardTimer);
    process.exit(0);
  })
  .catch((err) => {
    clearTimeout(hardTimer);
    console.error(
      `SELFTEST FAIL: ${err instanceof Fail ? err.message : (err && err.stack) || err}`,
    );
    process.exit(1);
  });
