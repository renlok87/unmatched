// CSV-парсер без зависимостей: BOM, кавычки с ""-экранированием, CRLF.
// Используется всеми CSV-источниками доски (14-sprint-backlog, 06-asset-manifest,
// 07-animation-vfx-audio). Значения могут содержать ';'-списки — парсер их не дробит.

/** Убирает UTF-8 BOM, если он есть. */
export function stripBom(text) {
  return text.charCodeAt(0) === 0xfeff ? text.slice(1) : text;
}

/**
 * Парсит CSV-текст в массив строк-ячеек.
 * Поддерживает: запятую-разделитель, кавычки с удвоением "" как escape,
 * переводы строк LF/CRLF (CR обрезается), пустые строки пропускаются.
 * @param {string} text
 * @returns {string[][]}
 */
export function parseCsv(text) {
  const src = stripBom(text);
  const rows = [];
  let row = [];
  let cell = "";
  let inQuotes = false;
  for (let i = 0; i < src.length; i++) {
    const c = src[i];
    if (inQuotes) {
      if (c === '"') {
        if (src[i + 1] === '"') {
          cell += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        cell += c;
      }
      continue;
    }
    if (c === '"') {
      inQuotes = true;
    } else if (c === ",") {
      row.push(cell);
      cell = "";
    } else if (c === "\n") {
      if (cell.endsWith("\r")) cell = cell.slice(0, -1);
      row.push(cell);
      cell = "";
      if (row.length > 1 || row[0] !== "") rows.push(row);
      row = [];
    } else {
      cell += c;
    }
  }
  if (cell !== "" || row.length > 0) {
    if (cell.endsWith("\r")) cell = cell.slice(0, -1);
    row.push(cell);
    if (row.length > 1 || row[0] !== "") rows.push(row);
  }
  return rows;
}

/**
 * Парсит CSV в объекты по заголовочной строке.
 * Недостающие колонки становятся '', лишние игнорируются.
 * @param {string} text
 * @returns {{ header: string[], records: Object<string,string>[] }}
 */
export function parseCsvTable(text) {
  const rows = parseCsv(text);
  if (rows.length === 0) return { header: [], records: [] };
  const header = rows[0].map((h) => h.trim());
  const records = rows.slice(1).map((cells) => {
    const rec = {};
    header.forEach((name, i) => {
      rec[name] = cells[i] ?? "";
    });
    return rec;
  });
  return { header, records };
}
