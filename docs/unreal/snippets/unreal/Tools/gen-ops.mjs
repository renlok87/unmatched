#!/usr/bin/env node
/**
 * unreal/Tools/gen-ops.mjs — генерация `Source/UmModel/Public/UmOps.gen.h` из `unreal/Ops/*.graphql`
 * (ADR §3.3 «UmOps.gen.h — СГЕНЕРИРОВАННЫЕ документы операций (не править руками)», §4.2, §5.9).
 *
 * Выход — заголовок C++ (UE 5.8, модуль UmModel) с:
 *   - `namespace UmOps` и вложенным `namespace <OperationName>` на каждую операцию:
 *       `inline constexpr TCHAR Name[]`, `Document[]` (TEXT(R"GQL(...)GQL") — canonical print(ast)
 *       без комментариев, с фрагментами), `Kind`, `Auth`;
 *   - таблицей `inline const FDescriptor All[]` (имя → документ → auth → kind → бакет/лимит)
 *     и хелперами `GetAll()` / `Find(FStringView)`;
 *   - `DocumentSetSha256` — SHA-256 набора Ops/*.graphql; спека `Unmatched.Model.OpsGenerated`
 *     (ADR §4.8) сверяет его с файлами на диске, защищая от устаревшего заголовка.
 *
 * Метаданные операции берутся из служебного заголовка над определением (формат — Ops/auth.graphql):
 *   `# auth: none|optional|required`, `# throttle: <limit>/<windowSec>`, `# bucket: <name>`.
 *
 * Уточнение к ADR: `EUmAuthMode` объявлен в UmNet (UmGraphQLTypes.h, ADR §4.1), а UmModel от UmNet
 * не зависит (ADR §4.0). Поэтому сгенерированный заголовок объявляет собственный
 * `UmOps::EAuth { None, Optional, Required }` с теми же значениями; преобразование в `EUmAuthMode`
 * выполняет `UUmStateSubsystem` (UmClient) при сборке `FUmGraphQLRequest`.
 *
 * Использование:
 *   node Tools/gen-ops.mjs                              # Ops/ → Unmatched/Source/UmModel/Public/UmOps.gen.h
 *   node Tools/gen-ops.mjs --ops <dir> --out <file.h>
 *   node Tools/gen-ops.mjs --check                      # exit 1, если заголовок на диске устарел
 * Обычно вызывается через `node Tools/ops-check.mjs --gen` (сначала валидация по схеме).
 *
 * Проверенные факты UE 5.8 (заголовки движка): TEXT(x) → L##x / u8##x (`Runtime/Core/Public/HAL/Platform.h:1317-1332`),
 * поэтому `TEXT(R"GQL(...)GQL")` даёт корректный raw-литерал (прецедент в движке —
 * `GenericPlatformCrashContext.cpp:2072`); `MakeArrayView` — `Containers/ArrayView.h:934`;
 * `TStringView::Equals(const CharType*, ESearchCase)` — `Containers/StringView.h:389`.
 * Ограничение MSVC: один строковый литерал ≤ 16 380 байт (C2026) — генератор падает при документе > 12 000 символов.
 */

import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { print } from 'graphql';
import { loadOps } from './ops-check.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const UNREAL_ROOT = path.resolve(__dirname, '..');
const DEFAULT_OUT = path.join(UNREAL_ROOT, 'Unmatched', 'Source', 'UmModel', 'Public', 'UmOps.gen.h');
const RAW_DELIM = 'GQL';
const MAX_LITERAL = 12000;

/**
 * SHA-256 набора файлов: имена по алфавиту, для каждого — `<basename>\n<contents с LF>\n`.
 * Тот же порядок и нормализация воспроизводятся в спеке OpsGenerated (см. hashOpsFilesSha1).
 */
export function hashOpsFiles(files) {
  const h = crypto.createHash('sha256');
  for (const full of [...files].sort((a, b) => path.basename(a).localeCompare(path.basename(b)))) {
    h.update(path.basename(full) + '\n');
    h.update(fs.readFileSync(full, 'utf8').replace(/\r\n/g, '\n'));
    h.update('\n');
  }
  return h.digest('hex');
}
/**
 * SHA-1 того же набора. В Core UE 5.8 нет SHA-256 для буферов (есть FSHA1 и FMD5 в
 * `Runtime/Core/Public/Misc/SecureHash.h`; SHA-256 живёт в PlatformCrypto — зависимость UmNet,
 * недоступная UmModel по ADR §4.0). Поэтому заголовок несёт ОБА хеша: SHA-256 — для CI/людей,
 * SHA-1 — для спеки `Unmatched.Model.OpsGenerated`, которая считает `FSHA1::HashBuffer` над той же
 * LF-нормализованной конкатенацией (UTF-8 байты) и сравнивает hex-строку с DocumentSetSha1.
 */
export function hashOpsFilesSha1(files) {
  const h = crypto.createHash('sha1');
  for (const full of [...files].sort((a, b) => path.basename(a).localeCompare(path.basename(b)))) {
    h.update(path.basename(full) + '\n');
    h.update(fs.readFileSync(full, 'utf8').replace(/\r\n/g, '\n'));
    h.update('\n');
  }
  return h.digest('hex');
}

function cppIdent(name) {
  if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(name)) throw new Error(`Имя операции ${name} не является идентификатором C++`);
  const reserved = new Set(['Kind', 'Auth', 'Name', 'Document', 'All', 'Find', 'GetAll', 'FDescriptor', 'EAuth', 'EKind']);
  if (reserved.has(name)) throw new Error(`Имя операции ${name} конфликтует с идентификатором генератора`);
  return name;
}

function kindEnum(op) {
  return { query: 'EKind::Query', mutation: 'EKind::Mutation', subscription: 'EKind::Subscription' }[op.kind];
}
function authEnum(header) {
  return { none: 'EAuth::None', optional: 'EAuth::Optional', required: 'EAuth::Required' }[header.auth ?? 'required'];
}

/** Документ в каноническом виде: print(ast) операции + фрагментов (без комментариев, ASCII). */
function canonicalDocument(op) {
  const text = print(op.document).replace(/\r\n/g, '\n').trimEnd();
  if (text.includes(`)${RAW_DELIM}"`)) throw new Error(`${op.name}: документ содержит терминатор raw-литерала )${RAW_DELIM}"`);
  if (text.length > MAX_LITERAL) throw new Error(`${op.name}: документ ${text.length} символов > ${MAX_LITERAL} (лимит MSVC C2026)`);
  if (/[^\x09\x0A\x20-\x7E]/.test(text)) throw new Error(`${op.name}: документ содержит не-ASCII символы`);
  return text;
}

export function renderHeader({ operations, files }) {
  const sha256 = hashOpsFiles(files);
  const sha1 = hashOpsFilesSha1(files);
  const L = [];
  const p = (s = '') => L.push(s);

  p('// UmOps.gen.h — СГЕНЕРИРОВАНО unreal/Tools/gen-ops.mjs из unreal/Ops/*.graphql. НЕ ПРАВИТЬ РУКАМИ.');
  p('// Регенерация: `npm run ops:gen` в unreal/Tools (ADR §3.7, §5.9). Модуль: UmModel (ADR §3.3).');
  p(`// Набор документов: ${files.map((f) => path.basename(f)).sort().join(', ')}`);
  p('// Комментарии/источники к каждой операции — в исходных .graphql (здесь только canonical print).');
  p('#pragma once');
  p();
  p('#include "CoreMinimal.h"');
  p('#include "Containers/ArrayView.h"');
  p('#include "Containers/StringView.h"');
  p();
  p('namespace UmOps');
  p('{');
  p('\t/** Режим авторизации операции (R1 §2.14). Значения совпадают с EUmAuthMode (UmNet, ADR §4.1);');
  p('\t *  собственный enum — потому что UmModel не зависит от UmNet (ADR §4.0). Уточнение к ADR. */');
  p('\tenum class EAuth : uint8');
  p('\t{');
  p('\t\tNone = 0,      // токен не отправляется');
  p('\t\tOptional = 1,  // токен отправляется, если есть (публичные query)');
  p('\t\tRequired = 2   // GqlAuthGuard; при классе Auth — refresh + один повтор (ADR §5.3)');
  p('\t};');
  p();
  p('\tenum class EKind : uint8');
  p('\t{');
  p('\t\tQuery = 0,');
  p('\t\tMutation = 1,');
  p('\t\tSubscription = 2');
  p('\t};');
  p();
  p('\t/** Строка реестра операций: FUmOpsRegistry (UmOps.h) строит по ней FUmGraphQLRequest (ADR §4.2). */');
  p('\tstruct FDescriptor');
  p('\t{');
  p('\t\tconst TCHAR* Name;             // operationName (PascalCase, ADR §3.6)');
  p('\t\tconst TCHAR* Document;         // canonical GraphQL-документ с фрагментами');
  p('\t\tEKind Kind;');
  p('\t\tEAuth Auth;');
  p('\t\tconst TCHAR* RateLimitBucket;  // бакет FUmRateLimiter (ADR §4.1); пусто — без лимита');
  p('\t\tint32 ThrottleLimit;           // объявленный @Throttle (R1 §2.11); 0 — не объявлен');
  p('\t\tint32 ThrottleWindowSec;');
  p();
  p('\t\tbool IsMutation() const { return Kind == EKind::Mutation; }');
  p('\t\tbool IsSubscription() const { return Kind == EKind::Subscription; }');
  p('\t};');
  p();
  p(`\t/** SHA-256 набора Ops/*.graphql (имена по алфавиту, LF): защита от устаревшего заголовка (ADR §4.8 OpsGenerated). */`);
  p(`\tinline constexpr TCHAR DocumentSetSha256[] = TEXT("${sha256}");`);
  p(`\t/** SHA-1 того же набора — для сверки в спеке через FSHA1 (Misc/SecureHash.h), т.к. SHA-256 в Core нет. */`);
  p(`\tinline constexpr TCHAR DocumentSetSha1[] = TEXT("${sha1}");`);
  p(`\tinline constexpr int32 DocumentSetCount = ${operations.length};`);
  p('\t// Дата генерации намеренно не пишется: заголовок должен быть воспроизводимым (чистый git diff).');
  p();

  for (const op of operations) {
    const id = cppIdent(op.name);
    const doc = canonicalDocument(op);
    p(`\t// ---- ${op.name} (${op.kind}, ${op.file}:${op.line}) ----`);
    p(`\tnamespace ${id}`);
    p('\t{');
    p(`\t\tinline constexpr TCHAR Name[] = TEXT("${op.name}");`);
    p(`\t\tinline constexpr EKind Kind = ${kindEnum(op)};`);
    p(`\t\tinline constexpr EAuth Auth = ${authEnum(op.header)};`);
    p(`\t\tinline constexpr TCHAR Document[] = TEXT(R"${RAW_DELIM}(`);
    for (const line of doc.split('\n')) p(line);
    p(`)${RAW_DELIM}");`);
    p('\t}');
    p();
  }

  p('\t/** Таблица всех операций в порядке файлов Ops/*.graphql. */');
  p('\tinline const FDescriptor All[] =');
  p('\t{');
  for (const op of operations) {
    const id = cppIdent(op.name);
    const bucket = op.header.bucket ?? '';
    const limit = op.header.throttle?.limit ?? 0;
    const win = op.header.throttle?.windowSec ?? 0;
    p(`\t\t{ ${id}::Name, ${id}::Document, ${id}::Kind, ${id}::Auth, TEXT("${bucket}"), ${limit}, ${win} },`);
  }
  p('\t};');
  p();
  p('\tinline TArrayView<const FDescriptor> GetAll()');
  p('\t{');
  p('\t\treturn MakeArrayView(All);');
  p('\t}');
  p();
  p('\t/** Поиск по operationName (чувствителен к регистру); nullptr, если нет. */');
  p('\tinline const FDescriptor* Find(FStringView OperationName)');
  p('\t{');
  p('\t\tfor (const FDescriptor& D : All)');
  p('\t\t{');
  p('\t\t\tif (OperationName.Equals(D.Name, ESearchCase::CaseSensitive))');
  p('\t\t\t{');
  p('\t\t\t\treturn &D;');
  p('\t\t\t}');
  p('\t\t}');
  p('\t\treturn nullptr;');
  p('\t}');
  p('}');
  p();
  return { text: L.join('\n'), sha256, sha1 };
}

export function generate({ opsDir = path.join(UNREAL_ROOT, 'Ops'), outPath = DEFAULT_OUT, check = false } = {}) {
  const loaded = loadOps(opsDir);
  if (loaded.errors.length) {
    throw new Error(`Ops/*.graphql содержат ошибки (запустите ops-check.mjs):\n  - ${loaded.errors.join('\n  - ')}`);
  }
  const { text, sha256, sha1 } = renderHeader(loaded);
  if (check) {
    const existing = fs.existsSync(outPath) ? fs.readFileSync(outPath, 'utf8') : '';
    const m = /DocumentSetSha256\[\] = TEXT\("([0-9a-f]{64})"\)/.exec(existing);
    if (!m || m[1] !== sha256) {
      throw new Error(`UmOps.gen.h устарел: sha256 в заголовке ${m ? m[1].slice(0, 12) : '<нет>'} ≠ ${sha256.slice(0, 12)} набора Ops/. Запустите npm run ops:gen`);
    }
    return { outPath, sha256, sha1, upToDate: true };
  }
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  fs.writeFileSync(outPath, text, 'utf8');
  return { outPath, sha256, sha1, upToDate: false };
}

// ---------------------------------------------------------------------------
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const argv = process.argv.slice(2);
  const opts = {};
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--ops') opts.opsDir = path.resolve(argv[++i]);
    else if (argv[i] === '--out') opts.outPath = path.resolve(argv[++i]);
    else if (argv[i] === '--check') opts.check = true;
    else { console.error(`Неизвестный аргумент: ${argv[i]}`); process.exit(2); }
  }
  try {
    const r = generate(opts);
    console.log(r.upToDate ? `UmOps.gen.h актуален (${r.sha256.slice(0, 12)}…)` : `UmOps.gen.h записан: ${r.outPath} (sha256 ${r.sha256.slice(0, 12)}…)`);
  } catch (e) {
    console.error(e.message);
    process.exit(1);
  }
}
