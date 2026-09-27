// Клиент доски: fetch при старте + EventSource; перерисовка только при смене rev.
// DnD-перенос карточки -> PATCH -> SSE 'tasks' -> рендер: один путь данных.

"use strict";

const COLUMNS = [
  { status: "planned", title: "Planned" },
  { status: "in_progress", title: "In Progress" },
  { status: "blocked", title: "Blocked" },
  { status: "done", title: "Done" },
];

const TYPE_LABELS = {
  feature: "фича",
  art: "арт",
  acceptance: "приёмка",
  task: "задача",
  test: "тест",
  question: "вопрос",
  risk: "риск",
  decision: "решение",
  asset: "ассет",
  cue: "CUE",
};

const FLAG_LABELS = {
  overridden: "переопределено",
  "no-evidence": "нет доказательства",
  diverged: "расхождение",
};

const state = {
  tasks: [],
  rev: null,
  query: "",
  type: "",
  milestone: "",
};

const boardEl = document.getElementById("board");
const searchEl = document.getElementById("search");
const typeEl = document.getElementById("type-filter");
const milestoneEl = document.getElementById("milestone-filter");
const totalEl = document.getElementById("total");
const connEl = document.getElementById("conn");
const errorEl = document.getElementById("error");

// --- Экранирование ----------------------------------------------------------

function esc(value) {
  return String(value).replace(/[&<>"']/g, (c) => {
    switch (c) {
      case "&":
        return "&amp;";
      case "<":
        return "&lt;";
      case ">":
        return "&gt;";
      case '"':
        return "&quot;";
      default:
        return "&#39;";
    }
  });
}

// --- Данные -----------------------------------------------------------------

function applyServerData(rev, tasks) {
  if (state.rev !== null && rev === state.rev) return; // без смены rev не перерисовываем
  state.rev = rev;
  state.tasks = Array.isArray(tasks) ? tasks : [];
  render();
}

async function fetchTasks() {
  try {
    const res = await fetch("/api/tasks", { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const rev = Number(res.headers.get("x-board-rev")) || null;
    const tasks = await res.json();
    applyServerData(rev, tasks);
    hideError();
  } catch (err) {
    showError(`не удалось получить задачи: ${err.message}`);
  }
}

function setOnline(online) {
  connEl.classList.toggle("offline", !online);
  connEl.classList.toggle("online", online);
  connEl.textContent = online ? "онлайн" : "офлайн";
}

function showError(message) {
  errorEl.textContent = message;
  errorEl.hidden = false;
}

function hideError() {
  errorEl.hidden = true;
}

const es = new EventSource("/api/events");
es.addEventListener("init", (event) => {
  const data = JSON.parse(event.data);
  applyServerData(data.rev, data.tasks);
  setOnline(true);
});
es.addEventListener("tasks", (event) => {
  const data = JSON.parse(event.data);
  applyServerData(data.rev, data.tasks);
});
es.onopen = () => {
  setOnline(true);
  fetchTasks(); // переподключение могли пропустить — перепроверяем
};
es.onerror = () => setOnline(false);

// --- Фильтры ----------------------------------------------------------------

function passesFilters(task) {
  if (state.type && task.type !== state.type) return false;
  if (state.milestone && (task.milestone || "") !== state.milestone)
    return false;
  if (state.query) {
    const q = state.query.toLowerCase();
    if (
      !task.id.toLowerCase().includes(q) &&
      !String(task.title || "")
        .toLowerCase()
        .includes(q)
    ) {
      return false;
    }
  }
  return true;
}

let searchTimer = null;
searchEl.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    state.query = searchEl.value.trim();
    render();
  }, 150);
});

typeEl.addEventListener("change", () => {
  state.type = typeEl.value;
  render();
});

milestoneEl.addEventListener("change", () => {
  state.milestone = milestoneEl.value;
  render();
});

// --- Рендер -----------------------------------------------------------------

function fillFilters() {
  const types = new Set();
  const milestones = new Set();
  for (const t of state.tasks) {
    if (t.type) types.add(t.type);
    if (t.milestone) milestones.add(t.milestone);
  }
  const typeOptions = ["", ...[...types].sort()];
  if (typeEl.dataset.filled !== String(typeOptions.join("|"))) {
    typeEl.dataset.filled = String(typeOptions.join("|"));
    const prev = state.type;
    typeEl.innerHTML =
      '<option value="">все типы</option>' +
      typeOptions
        .filter(Boolean)
        .map(
          (t) =>
            `<option value="${esc(t)}">${esc(TYPE_LABELS[t] || t)}</option>`,
        )
        .join("");
    typeEl.value = types.has(prev) ? prev : "";
    state.type = typeEl.value;
  }
  const msList = [...milestones].sort((a, b) =>
    a.localeCompare(b, "en", { numeric: true }),
  );
  if (milestoneEl.dataset.filled !== String(msList.join("|"))) {
    milestoneEl.dataset.filled = String(msList.join("|"));
    const prev = state.milestone;
    milestoneEl.innerHTML =
      '<option value="">все этапы</option>' +
      msList
        .map((m) => `<option value="${esc(m)}">${esc(m)}</option>`)
        .join("");
    milestoneEl.value = milestones.has(prev) ? prev : "";
    state.milestone = milestoneEl.value;
  }
}

function cardHtml(task) {
  const flags = (task.flags || [])
    .map(
      (f) =>
        `<span class="flag flag-${esc(f)}" title="${esc(f)}">${esc(FLAG_LABELS[f] || f)}</span>`,
    )
    .join("");
  const milestone = task.milestone
    ? `<span class="badge ms">${esc(task.milestone)}</span>`
    : "";
  const note = task.note
    ? `<div class="note" title="${esc(task.note)}">${esc(task.note)}</div>`
    : "";
  return (
    `<article class="card t-${esc(task.type)}" draggable="true" data-id="${esc(task.id)}">` +
    `<div class="card-head"><code class="id">${esc(task.id)}</code>` +
    `<span class="badge type">${esc(TYPE_LABELS[task.type] || task.type || "?")}</span>` +
    milestone +
    `</div>` +
    `<div class="title">${esc(task.title)}</div>` +
    note +
    (flags ? `<div class="flags">${flags}</div>` : "") +
    `</article>`
  );
}

function render() {
  fillFilters();
  let visible = 0;
  for (const col of COLUMNS) {
    const section = boardEl.querySelector(
      `.column[data-status="${col.status}"]`,
    );
    if (!section) continue;
    const cards = state.tasks.filter(
      (t) => t.status === col.status && passesFilters(t),
    );
    visible += cards.length;
    section.querySelector(".cards").innerHTML = cards.map(cardHtml).join("");
    section.querySelector(".count").textContent = String(cards.length);
  }
  totalEl.textContent = `${visible} / ${state.tasks.length}`;
}

// --- Drag & drop ------------------------------------------------------------

boardEl.addEventListener("dragstart", (event) => {
  const card = event.target.closest(".card");
  if (!card) return;
  event.dataTransfer.setData("text/plain", card.dataset.id);
  event.dataTransfer.effectAllowed = "move";
  card.classList.add("dragging");
});

boardEl.addEventListener("dragend", (event) => {
  const card = event.target.closest(".card");
  if (card) card.classList.remove("dragging");
});

for (const section of boardEl.querySelectorAll(".column")) {
  section.addEventListener("dragover", (event) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    section.classList.add("drop-target");
  });
  section.addEventListener("dragleave", () => {
    section.classList.remove("drop-target");
  });
  section.addEventListener("drop", (event) => {
    event.preventDefault();
    section.classList.remove("drop-target");
    const id = event.dataTransfer.getData("text/plain");
    if (!id) return;
    moveTask(id, section.dataset.status);
  });
}

async function moveTask(id, status) {
  const task = state.tasks.find((t) => t.id === id);
  if (!task || task.status === status) return;
  try {
    const res = await fetch(`/api/tasks/${encodeURIComponent(id)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json; charset=utf-8" },
      body: JSON.stringify({ status }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.error || `HTTP ${res.status}`);
    }
    hideError();
    // Перерисовка придёт событием 'tasks' — тот же путь, что и у других вкладок.
  } catch (err) {
    showError(`не удалось переместить ${id}: ${err.message}`);
  }
}

// --- Старт ------------------------------------------------------------------

render();
fetchTasks();
