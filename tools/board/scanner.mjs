// Сканер источников доски задач: docs/game-design -> плоский список задач.
// Никаких зависимостей, только node:fs/node:path. Все паттерны выверены по
// фактическому содержимому файлов на момент написания (см. README.md).

import { existsSync, readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { parseCsvTable } from "./sources/csv.mjs";

export const STATUSES = ["done", "in_progress", "planned", "blocked"];
export const TYPES = [
  "feature",
  "art",
  "acceptance",
  "task",
  "test",
  "question",
  "risk",
  "decision",
  "asset",
  "cue",
];

/** Имена файлов-источников в docs/game-design (evidence/ — каталогом). */
const SOURCE_FILES = [
  "00-vision-and-scope.md",
  "06-asset-manifest.csv",
  "07-animation-vfx-audio.csv",
  "08-integration-decisions.md",
  "09-vertical-slice-and-backlog.md",
  "10-acceptance-tests.md",
  "11-open-questions-and-risks.md",
  "14-sprint-backlog.csv",
  "15-rules-and-release-acceptance.md",
];

function readUtf8(file) {
  return readFileSync(file, "utf8");
}

function readLines(file) {
  return readUtf8(file).split(/\r?\n/);
}

function makeTask(partial) {
  return {
    id: partial.id,
    title: partial.title || partial.id,
    status: STATUSES.includes(partial.status) ? partial.status : "planned",
    type: partial.type,
    milestone: partial.milestone || "",
    source: partial.source,
    statusSource: partial.statusSource,
    flags: [],
  };
}

/** 14-sprint-backlog.csv: GD/ART, статус из CSV, sprint -> milestone, owner -> type. */
function scanSprintBacklog(file, source) {
  const { records } = parseCsvTable(readUtf8(file));
  const tasks = [];
  for (const rec of records) {
    const id = (rec.id || "").trim();
    if (!/^(GD|ART)-\d+$/.test(id)) continue;
    tasks.push(
      makeTask({
        id,
        title: rec.title || id,
        status: rec.status,
        type: rec.owner === "ART" ? "art" : "feature",
        milestone: rec.sprint,
        source,
        statusSource: "csv",
      }),
    );
  }
  return tasks;
}

/** 06-asset-manifest.csv: id = assetKey целиком, verificationStatus -> status 1:1. */
function scanAssetManifest(file, source) {
  const { records } = parseCsvTable(readUtf8(file));
  const tasks = [];
  for (const rec of records) {
    const id = (rec.assetKey || "").trim();
    if (!id) continue;
    const entityType = (rec.entityType || "").trim();
    const stableKey = (rec.stableContentKey || "").trim();
    const title = [entityType, stableKey].filter(Boolean).join(" · ") || id;
    tasks.push(
      makeTask({
        id,
        title,
        status: rec.verificationStatus,
        type: "asset",
        milestone: "",
        source,
        statusSource: "manifest",
      }),
    );
  }
  return tasks;
}

/** 07-animation-vfx-audio.csv: cueId -> CUE-задачи, title = event. */
function scanCues(file, source) {
  const { records } = parseCsvTable(readUtf8(file));
  const tasks = [];
  for (const rec of records) {
    const id = (rec.cueId || "").trim();
    if (!/^CUE-\d+$/.test(id)) continue;
    tasks.push(
      makeTask({
        id,
        title: (rec.event || "").trim() || id,
        type: "cue",
        milestone: "",
        source,
        statusSource: "scan",
      }),
    );
  }
  return tasks;
}

/** 09-vertical-slice-and-backlog.md: TASK в двух форматах, milestone = секция «Этап N». */
function scanBacklogTasks(file, source) {
  const tasks = [];
  let milestone = "";
  for (const raw of readLines(file)) {
    const line = raw.trimEnd();
    const section = /^(#{2}) (.+)$/.exec(line);
    if (section) {
      const stage = /^Этап (\d+)\./.exec(section[2]);
      milestone = stage ? `Этап ${stage[1]}` : "";
      continue;
    }
    let m = /^### (TASK-\d+) \/ (.+)$/.exec(line);
    if (m) {
      tasks.push(
        makeTask({
          id: m[1],
          title: m[2].trim(),
          type: "task",
          milestone,
          source,
          statusSource: "scan",
        }),
      );
      continue;
    }
    m = /^- \*\*(TASK-\d{3}) \/ (.+?)\*\*/.exec(line);
    if (m) {
      tasks.push(
        makeTask({
          id: m[1],
          title: m[2].replace(/\.$/, "").trim(),
          type: "task",
          milestone,
          source,
          statusSource: "scan",
        }),
      );
    }
  }
  return tasks;
}

/** 15-rules-and-release-acceptance.md: '^## ACC-###' -> acceptance. */
function scanAcceptance(file, source) {
  const tasks = [];
  for (const line of readLines(file)) {
    const m = /^## (ACC-\d{3})(?: — (.+))?$/.exec(line.trimEnd());
    if (m) {
      tasks.push(
        makeTask({
          id: m[1],
          title: (m[2] || m[1]).trim(),
          type: "acceptance",
          milestone: "",
          source,
          statusSource: "scan",
        }),
      );
    }
  }
  return tasks;
}

/** 10-acceptance-tests.md: '^#{2,3} QA-###.' -> test. */
function scanQa(file, source) {
  const tasks = [];
  for (const line of readLines(file)) {
    const m = /^#{2,3} (QA-\d{3})\. (.+)$/.exec(line.trimEnd());
    if (m) {
      tasks.push(
        makeTask({
          id: m[1],
          title: m[2].trim(),
          type: "test",
          milestone: "",
          source,
          statusSource: "scan",
        }),
      );
    }
  }
  return tasks;
}

/** 00-vision-and-scope.md §8: строки таблицы '| D-## | решение |'. */
function scanDecisions(file, source) {
  const lines = readLines(file);
  const tasks = [];
  let inSection = false;
  for (const line of lines) {
    if (/^## 8\./.test(line)) {
      inSection = true;
      continue;
    }
    if (inSection && /^## /.test(line)) break;
    if (!inSection) continue;
    const m = /^\| (D-\d+) +\| (.+) \|$/.exec(line.trimEnd());
    if (m) {
      tasks.push(
        makeTask({
          id: m[1],
          title: m[2].replace(/\*\*/g, "").trim(),
          type: "decision",
          milestone: "",
          source,
          statusSource: "scan",
        }),
      );
    }
  }
  return tasks;
}

/** Разбить строку markdown-таблицы на ячейки. */
function tableCells(line) {
  return line.split("|").map((c) => c.trim());
}

/** 11-open-questions-and-risks.md: Q из жирных строк, RISK из таблицы. */
function scanQuestionsAndRisks(file, source) {
  const lines = readLines(file);
  // Сводная таблица статусов (в начале файла): '| Q-### | Закрыт…/Факт установлен… | … |'
  const closed = new Set();
  for (const line of lines) {
    const cells = tableCells(line);
    if (!/^Q-\d{3}$/.test(cells[1] || "")) continue;
    const verdict = (cells[2] || "").replace(/\*\*/g, "").trim();
    if (/^Закрыт/.test(verdict) || /^Факт установлен/.test(verdict)) {
      closed.add(cells[1]);
    }
  }
  const tasks = [];
  for (const line of lines) {
    // Групповые заголовки '### Q-0xx' игнорируются: ищем только жирные строки.
    const m = /^\*\*(Q-\d+)\b(.*)$/.exec(line);
    if (m) {
      const isClosed = closed.has(m[1]) || /\[ЗАКРЫТ/.test(line);
      tasks.push(
        makeTask({
          id: m[1],
          title: cleanQTitle(m[2]),
          status: isClosed ? "done" : "planned",
          type: "question",
          milestone: "",
          source,
          statusSource: "scan",
        }),
      );
      continue;
    }
    const risk = tableCells(line);
    if (/^RISK-\d{3}$/.test(risk[1] || "")) {
      tasks.push(
        makeTask({
          id: risk[1],
          title: (risk[2] || "").replace(/\*\*/g, "").trim(),
          type: "risk",
          milestone: "",
          source,
          statusSource: "scan",
        }),
      );
    }
  }
  return tasks;
}

/** Убирает markdown-мусор из заголовка вопроса: **, `, маркеры [БЛОК …]/[ЗАКРЫТ …]. */
function cleanQTitle(rest) {
  let t = rest.replace(/\*\*/g, "").replace(/`/g, "");
  t = t.replace(/\[(?:БЛОК|ЗАКРЫТ)[^\]]*\]/g, "");
  return t.replace(/^[\s.]+/, "").replace(/\s+$/, "");
}

/** 08-integration-decisions.md: GAP из обеих таблиц (поправки S01 = first-win),
 *  INT из заголовков '^#{2,3} … INT-###'. */
function scanIntegration(file, source) {
  const tasks = [];
  const seenGap = new Set();
  for (const raw of readLines(file)) {
    const line = raw.trimEnd();
    const cells = tableCells(line);
    const first = cells[1] || "";
    if (first.startsWith("GAP-")) {
      // 'GAP-008/017' разворачивается в два id; шапка 'GAP-ID' не матчится.
      const ids = [...first.matchAll(/GAP-\d{3}/g)].map((mm) => mm[0]);
      const title = (cells[2] || "").replace(/\*\*/g, "").trim();
      for (const id of ids) {
        if (seenGap.has(id)) continue; // «Поправки S01» перебивают §5: первое вхождение выигрывает
        seenGap.add(id);
        tasks.push(
          makeTask({
            id,
            title,
            type: "task",
            milestone: "",
            source,
            statusSource: "scan",
          }),
        );
      }
      continue;
    }
    const int = /^#{2,3} .*\b(INT-\d{3})\b/.exec(line);
    if (int) {
      tasks.push(
        makeTask({
          id: int[1],
          title: line.replace(/^#+\s*/, "").trim(),
          type: "decision",
          milestone: "",
          source,
          statusSource: "scan",
        }),
      );
    }
  }
  return tasks;
}

// ---------------------------------------------------------------------------
// Evidence: доказательный слой для GD/ART-задач из 14-sprint-backlog.csv.
// Три формы JSON (tasks.json / server-tasks.json в evidence/<sprint>/):
//   1) { "GD-001": { "status": "done", … } }
//   2) { …, "tasks": { "GD-025": { "status": "done", … } } }
//   3) { …, "tasks": [ { "id": "GD-017", "status": "DONE", … } ] }
// Для спринтов без JSON (S08–S10) доказательство = упоминание id в README.md.
// ---------------------------------------------------------------------------

/** @returns {Map<string,string>|null} id -> нормализованный статус, либо null если файл не одной из трёх форм. */
function parseEvidenceJson(text) {
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    return null;
  }
  if (data === null || typeof data !== "object" || Array.isArray(data))
    return null;
  const asStatusMap = (obj) => {
    const entries = Object.entries(obj);
    if (entries.length === 0) return null;
    const map = new Map();
    for (const [id, val] of entries) {
      if (
        val === null ||
        typeof val !== "object" ||
        Array.isArray(val) ||
        typeof val.status !== "string"
      ) {
        return null;
      }
      map.set(id, val.status.toLowerCase());
    }
    return map;
  };
  // Формы 2 и 3: обёртка с ключом tasks.
  if (data.tasks !== undefined) {
    if (Array.isArray(data.tasks)) {
      const map = new Map();
      let matched = false;
      for (const item of data.tasks) {
        if (
          item === null ||
          typeof item !== "object" ||
          typeof item.id !== "string" ||
          typeof item.status !== "string"
        ) {
          continue; // нестандартные записи (GD-017b, GD-017/020-adapters) молча пропускаются
        }
        matched = true;
        map.set(item.id, item.status.toLowerCase());
      }
      return matched ? map : null;
    }
    if (data.tasks !== null && typeof data.tasks === "object") {
      return asStatusMap(data.tasks);
    }
    return null;
  }
  // Форма 1: плоская карта.
  return asStatusMap(data);
}

/** @returns {Map<string, {jsonDone:Set<string>, readme:string|null}>} sprint -> доказательства */
export function collectEvidence(docsRoot) {
  const evidenceRoot = path.join(docsRoot, "evidence");
  const result = new Map();
  if (!existsSync(evidenceRoot)) return result;
  for (const entry of readdirSync(evidenceRoot, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const dir = path.join(evidenceRoot, entry.name);
    const jsonDone = new Set();
    let jsonSeen = false;
    for (const name of readdirSync(dir)) {
      if (name !== "tasks.json" && name !== "server-tasks.json") continue;
      const parsed = parseEvidenceJson(readUtf8(path.join(dir, name)));
      if (!parsed) continue;
      jsonSeen = true;
      for (const [id, status] of parsed) {
        if (status === "done") jsonDone.add(id);
      }
    }
    const readmePath = path.join(dir, "README.md");
    const readme = existsSync(readmePath) ? readUtf8(readmePath) : null;
    result.set(entry.name, { jsonDone, jsonSeen, readme });
  }
  return result;
}

/** Есть ли доказательство готовности для задачи (по её спринту = milestone). */
function hasEvidenceProof(task, evidence) {
  const perSprint = evidence.get(task.milestone);
  if (!perSprint) return false;
  if (perSprint.jsonSeen) return perSprint.jsonDone.has(task.id);
  if (perSprint.readme) return perSprint.readme.includes(task.id);
  return false;
}

// ---------------------------------------------------------------------------
// Overrides и слияние.
// ---------------------------------------------------------------------------

/**
 * Читает overrides.json. Битый JSON — предупреждение в stderr и пустой набор
 * (PATCH перезапишет файл заново).
 */
export function loadOverrides(overridesPath) {
  if (!existsSync(overridesPath)) return {};
  try {
    const data = JSON.parse(readUtf8(overridesPath));
    if (data === null || typeof data !== "object" || Array.isArray(data))
      return {};
    return data;
  } catch (err) {
    console.error(
      `[board] overrides.json не читается (${err.message}); игнорирую`,
    );
    return {};
  }
}

/**
 * Сканирует документы без учёта overrides.
 * @returns {Map<string, object>} id -> задача (первое вхождение id побеждает).
 */
export function scanDocuments(docsRoot) {
  const tasks = new Map();
  const put = (list) => {
    for (const t of list) {
      if (!tasks.has(t.id)) tasks.set(t.id, t);
    }
  };
  for (const name of SOURCE_FILES) {
    const file = path.join(docsRoot, name);
    if (!existsSync(file)) continue;
    const rel = sourceLabel(name);
    switch (name) {
      case "14-sprint-backlog.csv":
        put(scanSprintBacklog(file, rel));
        break;
      case "06-asset-manifest.csv":
        put(scanAssetManifest(file, rel));
        break;
      case "07-animation-vfx-audio.csv":
        put(scanCues(file, rel));
        break;
      case "09-vertical-slice-and-backlog.md":
        put(scanBacklogTasks(file, rel));
        break;
      case "15-rules-and-release-acceptance.md":
        put(scanAcceptance(file, rel));
        break;
      case "10-acceptance-tests.md":
        put(scanQa(file, rel));
        break;
      case "00-vision-and-scope.md":
        put(scanDecisions(file, rel));
        break;
      case "11-open-questions-and-risks.md":
        put(scanQuestionsAndRisks(file, rel));
        break;
      case "08-integration-decisions.md":
        put(scanIntegration(file, rel));
        break;
      default:
        break;
    }
  }
  return tasks;
}

function sourceLabel(fileName) {
  return `docs/game-design/${fileName}`;
}

function compareIds(a, b) {
  return a.id.localeCompare(b.id, "en", { numeric: true });
}

/**
 * Полный проход: скан источников + evidence + overrides.
 * @returns {{ tasks: object[], scanStatuses: Map<string,string> }}
 */
export function buildBoard(docsRoot, overridesPath) {
  const scanned = scanDocuments(docsRoot);
  const evidence = collectEvidence(docsRoot);
  const overrides = loadOverrides(overridesPath);
  const scanStatuses = new Map();
  for (const [id, t] of scanned) scanStatuses.set(id, t.status);

  const tasks = [];
  for (const t of scanned.values()) {
    const task = { ...t, flags: [] };
    // Доказательный слой: CSV-статус done без доказательства -> флаг, статус не трогаем.
    if (
      task.status === "done" &&
      task.statusSource === "csv" &&
      !hasEvidenceProof(t, evidence)
    ) {
      task.flags.push("no-evidence");
    }
    const ov = overrides[t.id];
    if (ov && typeof ov === "object" && STATUSES.includes(ov.status)) {
      task.status = ov.status;
      task.statusSource = "override";
      task.flags.push("overridden");
      if (typeof ov.note === "string") task.note = ov.note;
      if (typeof ov.updatedAt === "string") task.updatedAt = ov.updatedAt;
      // Скан изменился после ручного решения — не молча, а флагом.
      if (typeof ov.baseStatus === "string") {
        const current = scanStatuses.get(t.id);
        if (current !== undefined && current !== ov.baseStatus) {
          task.flags.push("diverged");
        }
      }
    }
    tasks.push(task);
  }
  // Задачи, существующие только в overrides (статус есть только здесь).
  for (const [id, ov] of Object.entries(overrides)) {
    if (scanned.has(id)) continue;
    if (!ov || typeof ov !== "object" || !STATUSES.includes(ov.status))
      continue;
    tasks.push({
      id,
      title:
        typeof ov.title === "string" && ov.title
          ? ov.title
          : "(только в overrides)",
      status: ov.status,
      type: "task",
      milestone: "",
      source: "(overrides)",
      statusSource: "override",
      flags: ["overridden"],
      ...(typeof ov.note === "string" ? { note: ov.note } : {}),
      ...(typeof ov.updatedAt === "string" ? { updatedAt: ov.updatedAt } : {}),
    });
    scanStatuses.set(id, ov.status);
  }
  tasks.sort(compareIds);
  return { tasks, scanStatuses };
}
