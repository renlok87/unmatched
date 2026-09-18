import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import {clearCaptureArtifacts} from './cleanup.mjs';
export const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
export const source = process.env.S01_SOURCE_ROOT || 'C:/Users/ren/WebstormProjects/unmached/unmached';
export const requireSource = createRequire(path.join(source, 'backend/package.json'));
export const out = path.join(root, 'docs/game-design/evidence/S01');
export const endpoint = process.env.S01_HTTP || 'http://localhost:3000/graphql';
const url = new URL(endpoint);
if (!['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)) throw new Error('S01 harness is local-only.');
fs.mkdirSync(out, { recursive: true });
const aliases = new Map();
const secrets = new Set();
export function alias(value, name) { if (value) aliases.set(value, name); }
export function scrub(value) {
  if (Array.isArray(value)) return value.map(scrub);
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([k,v]) => [aliases.get(k) || k, /password|accessToken|refreshToken|authorization|email/i.test(k) ? '[REDACTED]' : scrub(v)]));
  if (typeof value !== 'string') return value;
  if (secrets.has(value)) return '[REDACTED]';
  try { if (/^[\[{]/.test(value)) return scrub(JSON.parse(value)); } catch {}
  let safe = value;
  for (const secret of secrets) safe = safe.replaceAll(secret, '[REDACTED]');
  for (const [raw, name] of aliases) safe = safe.replaceAll(raw, name);
  return safe.replace(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g, '[REDACTED-JWT]');
}
export function save(name, value) { fs.writeFileSync(path.join(out, name), JSON.stringify(scrub(value), null, 2) + '\n'); }
export async function gql(query, variables = {}, token) {
  const r = await fetch(endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) }, body: JSON.stringify({query, variables}), signal: AbortSignal.timeout(15000) });
  const j = await r.json();
  if (j.errors?.length) throw new Error(JSON.stringify(j.errors.map(e => ({message:e.message, code:e.extensions?.code || e.code}))));
  return j.data;
}
export async function loginPair() {
  // Read existing LOCAL fixture credentials without echoing or persisting them.
  // Do not execute the old script: it aborts unrelated games and prints tokens.
  const needsFixture = [1,2].some(i => !process.env[`S01_P${i}_EMAIL`] || !process.env[`S01_P${i}_PASSWORD`]);
  const text = needsFixture ? fs.readFileSync(path.join(source, 'backend/scripts/setup-test-game.mjs'), 'utf8') : '';
  const fixtures = [...text.matchAll(/e: '([^']+)', p: '([^']+)'/g)];
  const result = [];
  for (let i = 0; i < 2; i++) {
    const email = process.env[`S01_P${i+1}_EMAIL`] || fixtures[i]?.[1];
    const password = process.env[`S01_P${i+1}_PASSWORD`] || fixtures[i]?.[2];
    if (!email || !password) throw new Error(`Missing P${i+1} credentials; set S01_P${i+1}_EMAIL/PASSWORD`);
    secrets.add(email); secrets.add(password);
    const data = (await gql('mutation($e:String!,$p:String!){login(input:{email:$e,password:$p}){accessToken user{id username}}}', {e:email,p:password})).login;
    secrets.add(data.accessToken); alias(data.user.id, `player-${i+1}`); alias(data.user.username, `tester-${i+1}`);
    result.push(data);
  }
  return result;
}
export const stateFields = 'gameId sequenceNumber phase turnCount currentTurnPlayerId players fighters handZones boardState metadata';
export async function state(gameId, token) {
  const result = (await gql('query($g:String!){gameState(gameId:$g){gameId sequenceNumber phase turnCount currentTurnPlayerId state}}', {g:gameId}, token)).gameState;
  return {...JSON.parse(result.state), sequenceNumber:result.sequenceNumber};
}
export function decoded(s) { return Object.fromEntries(Object.entries(s).map(([k,v]) => {try {return [k,typeof v==='string' && /^[\[{]/.test(v) ? JSON.parse(v):v]} catch {return [k,v]}})); }
async function schema() {
  const {getIntrospectionQuery, buildClientSchema, printSchema} = requireSource('graphql');
  const data = await gql(getIntrospectionQuery({descriptions:true}));
  save('schema-introspection.json', data);
  fs.writeFileSync(path.join(out, 'schema.graphql'), printSchema(buildClientSchema(data))+'\n');
  const health = await (await fetch(new URL('/health',endpoint), {signal:AbortSignal.timeout(10000)})).json();
  save('health.json', {capturedUtc:new Date().toISOString(), endpoint, health});
  console.log('Fresh schema and health captured.');
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    clearCaptureArtifacts(out, 'accounts');
    await schema();
    const users = await loginPair();
    save('accounts.json', {capturedUtc:new Date().toISOString(), users:users.map(u=>({id:u.user.id, username:u.user.username, authenticated:true})), credentialSource:'existing local fixture; values never written'});
    console.log('Both existing test accounts authenticated; credentials omitted.');
  } catch(e) { console.error(scrub(e.message)); process.exitCode = 1; }
}
