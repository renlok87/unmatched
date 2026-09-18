import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {alias, scrub, out, source, requireSource} from './capture.mjs';
const {buildClientSchema, parse, validate} = requireSource('graphql');
alias('opaque-user-a', 'player-1');
assert.deepEqual(scrub({accessToken:'do-not-write',password:'do-not-write',email:'do-not-write'}),{accessToken:'[REDACTED]',password:'[REDACTED]',email:'[REDACTED]'});
assert.deepEqual(scrub('{"opaque-user-a":{"ownerId":"opaque-user-a"}}'),{'player-1':{ownerId:'player-1'}});
assert.equal(scrub('Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhIn0.signature'), 'Bearer [REDACTED-JWT]');
const schema = buildClientSchema(JSON.parse(fs.readFileSync(path.join(out,'schema-introspection.json'),'utf8')));
const query = 'query($g:String!){gameState(gameId:$g){gameId sequenceNumber phase turnCount currentTurnPlayerId state}}';
assert.deepEqual(validate(schema,parse(query)), []);
const referencePath = path.join(source,'backend/scripts/setup-test-game.mjs');
const reference = fs.existsSync(referencePath) ? fs.readFileSync(referencePath,'utf8') : '';
const credentials=[...reference.matchAll(/e: '([^']+)', p: '([^']+)'/g)].flatMap(m=>[m[1],m[2]]);
credentials.push(...['S01_P1_EMAIL','S01_P1_PASSWORD','S01_P2_EMAIL','S01_P2_PASSWORD'].map(k=>process.env[k]).filter(Boolean));
let checked=0;
for(const file of fs.readdirSync(out,{recursive:true})) {
  if(!/\.(json|txt|md|graphql)$/.test(file))continue;
  const text=fs.readFileSync(path.join(out,file),'utf8');
  for(const credential of credentials)assert(!text.includes(credential),`Credential found in ${file}`);
  assert(!/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/.test(text),`JWT found in ${file}`);
  if(file.endsWith('.json'))JSON.parse(text.replace(/^\uFEFF/,''));
  checked++;
}
console.log(`PASS: nested JSON anonymization, credential redaction, JWT scrubbing, query against captured schema; ${checked} evidence files parsed/scanned.`);
