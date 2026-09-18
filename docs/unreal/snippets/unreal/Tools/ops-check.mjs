#!/usr/bin/env node
/**
 * unreal/Tools/ops-check.mjs — «схема как контракт» (ADR §3.7, §5.9, §4.8 «OpsGenerated»).
 *
 * Что делает:
 *   1. Загружает снимок introspection живого сервера `unreal/Schema/schema.introspection.json`
 *      и строит клиентскую схему (`buildClientSchema`, graphql-js 16 — та же мажорная версия,
 *      что у бэкенда `backend/package.json:65` и веб-клиента `package.json:23`).
 *   2. Для КАЖДОГО документа операции из `unreal/Ops/*.graphql` (операция + транзитивно
 *      используемые фрагменты) выполняет `validate(schema, doc)` по стандартным правилам
 *      graphql-js (неизвестные поля/аргументы, типы переменных, неиспользуемые переменные,
 *      уникальность имён и т. д.). Именно так ловятся ошибки веб-клиента вида
 *      `idempotencyKey` у `joinGame` и `matchFound(userId: ID!)` (R7 §2.13 п.9-10; R1 §2.12).
 *   3. Дополнительные проверки проекта:
 *        - у каждой операции есть имя (operationName обязателен — ADR §3.6: PascalCase);
 *        - имена уникальны во всём наборе Ops/*.graphql (реестр FUmOpsRegistry — ADR §4.2);
 *        - у каждой операции есть служебный заголовок `# auth: none|optional|required`
 *          (читается gen-ops.mjs; формат — Ops/auth.graphql);
 *        - глубина выборки ≤ 7 (ADR §5.4 «Complexity/depth», R1 §2.11);
 *        - фрагменты не «висят» (каждый используется хотя бы одной операцией).
 *   4. `--snapshot [url]` — получает introspection с живого бэкенда и записывает снимок
 *      (замена отдельного snapshot-introspection.mjs из ADR §3.7 — уточнение к ADR: один файл,
 *      два режима). Требует поднятого бэкенда `http://localhost:3000/graphql` (R6 §2.9);
 *      все контентные/публичные запросы доступны без токена, introspection — тоже
 *      (autoSchemaFile: true, R1 §1 п.11; фактическая доступность introspection в production
 *      требует живой проверки).
 *   5. `--gen` — после успешной валидации вызывает gen-ops.mjs (генерация UmOps.gen.h).
 *
 * Использование:
 *   node Tools/ops-check.mjs                         # валидация Ops/*.graphql против снимка
 *   node Tools/ops-check.mjs --snapshot              # снять снимок с http://localhost:3000/graphql
 *   node Tools/ops-check.mjs --snapshot http://host:3000/graphql --token <JWT>
 *   node Tools/ops-check.mjs --gen                   # валидация + генерация UmOps.gen.h
 *   node Tools/ops-check.mjs --syntax-only           # без схемы: только parse + проектные правила
 *   node Tools/ops-check.mjs --ops <dir> --schema <file> --max-depth 7
 *
 * Коды выхода: 0 — всё валидно; 1 — есть ошибки; 2 — неверные аргументы / нет снимка.
 *
 * Зависимости: `graphql` (package.json в unreal/Tools — см. README.md). Node ≥ 18 (fetch).
 */

import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath, pathToFileURL } from 'node:url';
import {
  buildClientSchema,
  getIntrospectionQuery,
  parse,
  validate,
  Kind,
  visit,
} from 'graphql';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
// Корень unreal/ — Tools/ лежит в нём (ADR §3.7: unreal/Ops, unreal/Schema, unreal/Tools).
const UNREAL_ROOT = path.resolve(__dirname, '..');

// ----------------------------------------------------------------------------
// Аргументы
// ----------------------------------------------------------------------------

function parseArgs(argv) {
  const args = {
    ops: path.join(UNREAL_ROOT, 'Ops'),
    schema: path.join(UNREAL_ROOT, 'Schema', 'schema.introspection.json'),
    snapshot: null, // string url | null
    token: process.env.UM_ACCESS_TOKEN ?? null,
    gen: false,
    syntaxOnly: false,
    maxDepth: 7,
    quiet: false,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    const next = () => argv[++i];
    switch (a) {
      case '--ops': args.ops = path.resolve(next()); break;
      case '--schema': args.schema = path.resolve(next()); break;
      case '--snapshot': {
        const maybeUrl = argv[i + 1];
        args.snapshot = maybeUrl && !maybeUrl.startsWith('--') ? next() : 'http://localhost:3000/graphql';
        break;
      }
      case '--token': args.token = next(); break;
      case '--gen': args.gen = true; break;
      case '--syntax-only': args.syntaxOnly = true; break;
      case '--max-depth': args.maxDepth = Number(next()); break;
      case '--quiet': args.quiet = true; break;
      case '-h': case '--help':
        console.log(fs.readFileSync(fileURLToPath(import.meta.url), 'utf8').split('\n').slice(1, 40).join('\n'));
        process.exit(0);
        break;
      default:
        console.error(`Неизвестный аргумент: ${a}`);
        process.exit(2);
    }
  }
  return args;
}

// ----------------------------------------------------------------------------
// Снимок introspection
// ----------------------------------------------------------------------------

/**
 * Снять introspection с живого сервера и сохранить в `schemaPath`.
 * Формат файла: `{ "data": { "__schema": … } }` — как отдаёт сервер (без обёртки тоже принимается
 * при чтении). Дата/URL — в соседнем `.meta.json`, чтобы diff снимка был чистым.
 */
async function snapshotIntrospection(url, token, schemaPath) {
  const headers = { 'content-type': 'application/json' };
  if (token) headers.authorization = `Bearer ${token}`;
  const body = JSON.stringify({
    operationName: 'IntrospectionQuery',
    query: getIntrospectionQuery({ descriptions: true, specifiedByUrl: true, directiveIsRepeatable: true, schemaDescription: true, inputValueDeprecation: true }),
  });
  const res = await fetch(url, { method: 'POST', headers, body });
  const text = await res.text();
  let json;
  try {
    json = JSON.parse(text);
  } catch {
    throw new Error(`Ответ ${url} не JSON (HTTP ${res.status}): ${text.slice(0, 200)}`);
  }
  if (!json?.data?.__schema) {
    // Ошибки — в теле при HTTP 200/400 (R1 §2.10, ADR §1.3 п.3).
    throw new Error(`Introspection не вернул __schema (HTTP ${res.status}): ${JSON.stringify(json.errors ?? json).slice(0, 500)}`);
  }
  fs.mkdirSync(path.dirname(schemaPath), { recursive: true });
  fs.writeFileSync(schemaPath, JSON.stringify({ data: { __schema: json.data.__schema } }, null, 2) + '\n', 'utf8');
  fs.writeFileSync(
    schemaPath.replace(/\.json$/, '.meta.json'),
    JSON.stringify({ url, fetchedAt: new Date().toISOString(), typesCount: json.data.__schema.types.length }, null, 2) + '\n',
    'utf8',
  );
  return json.data.__schema;
}

function loadSchema(schemaPath) {
  if (!fs.existsSync(schemaPath)) {
    throw new Error(
      `Нет снимка introspection: ${schemaPath}\n` +
      `Снимите его с поднятого бэкенда: node Tools/ops-check.mjs --snapshot [http://localhost:3000/graphql]\n` +
      `(или npm run schema:snapshot — см. Tools/README.md). Снимок коммитится в репозиторий (ADR §5.9).`,
    );
  }
  const raw = JSON.parse(fs.readFileSync(schemaPath, 'utf8'));
  const introspection = raw.data?.__schema ? raw.data : raw.__schema ? raw : null;
  if (!introspection) throw new Error(`Файл ${schemaPath} не похож на introspection (нет __schema)`);
  return buildClientSchema(introspection);
}

// ----------------------------------------------------------------------------
// Разбор Ops/*.graphql
// ----------------------------------------------------------------------------

/**
 * Служебный заголовок операции: подряд идущие строки `# …` непосредственно над определением.
 * Возвращает { auth, throttle: {limit, windowSec}|null, bucket, comment[] }.
 * Формат — Ops/auth.graphql (шапка файла).
 */
export function readOpHeader(lines, startLine /* 1-based */) {
  const header = { auth: null, throttle: null, bucket: null, comment: [] };
  for (let ln = startLine - 2; ln >= 0; ln--) {
    const line = lines[ln];
    if (!/^\s*#/.test(line)) break;
    const text = line.replace(/^\s*#\s?/, '');
    header.comment.unshift(text);
    let m;
    if ((m = /^auth:\s*(none|optional|required)\s*$/i.exec(text))) header.auth = m[1].toLowerCase();
    else if ((m = /^throttle:\s*(\d+)\s*\/\s*(\d+)\s*$/i.exec(text))) header.throttle = { limit: Number(m[1]), windowSec: Number(m[2]) };
    else if ((m = /^bucket:\s*([A-Za-z0-9_-]+)\s*$/i.exec(text))) header.bucket = m[1];
  }
  return header;
}

/** Глубина выборки (вложенность selectionSet), фрагменты раскрываются по месту. */
function selectionDepth(node, fragmentsByName, seen = new Set()) {
  if (!node.selectionSet) return 0;
  let max = 0;
  for (const sel of node.selectionSet.selections) {
    let d = 0;
    if (sel.kind === Kind.FIELD) d = 1 + selectionDepth(sel, fragmentsByName, seen);
    else if (sel.kind === Kind.INLINE_FRAGMENT) d = selectionDepth(sel, fragmentsByName, seen);
    else if (sel.kind === Kind.FRAGMENT_SPREAD) {
      const frag = fragmentsByName.get(sel.name.value);
      if (frag && !seen.has(frag.name.value)) {
        seen.add(frag.name.value);
        d = selectionDepth(frag, fragmentsByName, seen);
        seen.delete(frag.name.value);
      }
    }
    max = Math.max(max, d);
  }
  return max;
}

/** Имена фрагментов, используемых операцией (транзитивно). */
function collectFragmentNames(node, fragmentsByName, out = new Set()) {
  visit(node, {
    FragmentSpread(spread) {
      const name = spread.name.value;
      if (!out.has(name)) {
        out.add(name);
        const frag = fragmentsByName.get(name);
        if (frag) collectFragmentNames(frag, fragmentsByName, out);
      }
    },
  });
  return out;
}

/**
 * Загружает все Ops/*.graphql. Возвращает { operations: [...], fragments: Map, errors: [] }.
 * Каждая операция: { name, kind, file, line, header, ast (OperationDefinition), fragmentNames, document (DocumentNode) }.
 */
export function loadOps(opsDir) {
  const errors = [];
  const files = fs.readdirSync(opsDir).filter((f) => f.endsWith('.graphql')).sort();
  if (files.length === 0) errors.push(`В ${opsDir} нет *.graphql`);

  const fragmentsByName = new Map();
  const perFile = [];
  for (const file of files) {
    const full = path.join(opsDir, file);
    const source = fs.readFileSync(full, 'utf8');
    let ast;
    try {
      ast = parse(source, { noLocation: false });
    } catch (e) {
      errors.push(`${file}: синтаксическая ошибка: ${e.message}`);
      continue;
    }
    for (const def of ast.definitions) {
      if (def.kind === Kind.FRAGMENT_DEFINITION) {
        if (fragmentsByName.has(def.name.value)) errors.push(`${file}: дубликат фрагмента ${def.name.value}`);
        fragmentsByName.set(def.name.value, def);
      }
    }
    perFile.push({ file, full, source, lines: source.split(/\r?\n/), ast });
  }

  const operations = [];
  const seenNames = new Map();
  const usedFragments = new Set();
  for (const { file, lines, ast } of perFile) {
    for (const def of ast.definitions) {
      if (def.kind !== Kind.OPERATION_DEFINITION) continue;
      const line = def.loc?.startToken.line ?? 0;
      if (!def.name) {
        errors.push(`${file}:${line}: анонимная операция — operationName обязателен (ADR §3.6)`);
        continue;
      }
      const name = def.name.value;
      if (!/^[A-Z][A-Za-z0-9]*$/.test(name)) errors.push(`${file}:${line}: имя ${name} не PascalCase (ADR §3.6)`);
      if (seenNames.has(name)) errors.push(`${file}:${line}: дубликат операции ${name} (уже в ${seenNames.get(name)})`);
      seenNames.set(name, `${file}:${line}`);

      const header = readOpHeader(lines, line);
      if (!header.auth) errors.push(`${file}:${line}: у операции ${name} нет заголовка "# auth: none|optional|required"`);

      const fragmentNames = collectFragmentNames(def, fragmentsByName);
      for (const fn of fragmentNames) {
        usedFragments.add(fn);
        if (!fragmentsByName.has(fn)) errors.push(`${file}:${line}: ${name} использует неизвестный фрагмент ${fn}`);
      }
      const document = {
        kind: Kind.DOCUMENT,
        definitions: [def, ...[...fragmentNames].map((fn) => fragmentsByName.get(fn)).filter(Boolean)],
      };
      operations.push({ name, kind: def.operation, file, line, header, ast: def, fragmentNames: [...fragmentNames], document });
    }
  }
  for (const fn of fragmentsByName.keys()) {
    if (!usedFragments.has(fn)) errors.push(`фрагмент ${fn} не используется ни одной операцией`);
  }
  return { operations, fragments: fragmentsByName, errors, files: perFile.map((p) => p.full) };
}

// ----------------------------------------------------------------------------
// main
// ----------------------------------------------------------------------------

async function main() {
  const args = parseArgs(process.argv.slice(2));

  if (args.snapshot) {
    try {
      const s = await snapshotIntrospection(args.snapshot, args.token, args.schema);
      console.log(`Снимок introspection записан: ${path.relative(process.cwd(), args.schema)} (${s.types.length} типов, url ${args.snapshot})`);
    } catch (e) {
      console.error(`Не удалось снять introspection: ${e.message}`);
      process.exit(2);
    }
  }

  const { operations, fragments, errors } = loadOps(args.ops);
  const problems = [...errors];

  let schema = null;
  if (!args.syntaxOnly) {
    try {
      schema = loadSchema(args.schema);
    } catch (e) {
      console.error(e.message);
      process.exit(2);
    }
  }

  const rows = [];
  for (const op of operations) {
    const depth = selectionDepth(op.ast, fragments);
    if (depth > args.maxDepth) problems.push(`${op.file}:${op.line}: ${op.name} — глубина ${depth} > ${args.maxDepth} (ADR §5.4)`);
    let status = 'syntax-ok';
    if (schema) {
      const validationErrors = validate(schema, op.document);
      if (validationErrors.length) {
        status = 'INVALID';
        for (const ve of validationErrors) {
          const loc = ve.locations?.[0] ? `:${ve.locations[0].line}` : '';
          problems.push(`${op.file}${loc}: ${op.name} — ${ve.message}`);
        }
      } else status = 'valid';
    }
    rows.push({ name: op.name, kind: op.kind, auth: op.header.auth ?? '?', depth, status, file: op.file });
  }

  if (!args.quiet) {
    const w = Math.max(...rows.map((r) => r.name.length), 4);
    console.log(`${'Операция'.padEnd(w)}  ${'kind'.padEnd(12)} ${'auth'.padEnd(8)} depth  status      файл`);
    for (const r of rows) console.log(`${r.name.padEnd(w)}  ${r.kind.padEnd(12)} ${r.auth.padEnd(8)} ${String(r.depth).padStart(5)}  ${r.status.padEnd(10)}  ${r.file}`);
    console.log(`Итого: ${rows.length} операций, ${fragments.size} фрагментов, ${problems.length} проблем${schema ? '' : ' (режим --syntax-only: без валидации по схеме)'}`);
  }
  if (problems.length) {
    console.error('\nПроблемы:');
    for (const p of problems) console.error(`  - ${p}`);
    process.exit(1);
  }

  if (args.gen) {
    const gen = await import(pathToFileURL(path.join(__dirname, 'gen-ops.mjs')).href);
    const out = gen.generate({ opsDir: args.ops });
    console.log(`UmOps.gen.h записан: ${out.outPath} (sha256 набора ${out.sha256.slice(0, 12)}…)`);
  }
}

// Точка входа только при прямом запуске (gen-ops.mjs импортирует loadOps/readOpHeader).
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((e) => {
    console.error(e.stack ?? String(e));
    process.exit(1);
  });
}
