// GD-028: dump live SDL from the running S08 worktree backend (port 3100).
import { writeFileSync } from 'node:fs';
import { buildClientSchema, printSchema, getIntrospectionQuery } from 'graphql';

const res = await fetch('http://localhost:3100/graphql', {
  method: 'POST',
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify({ query: getIntrospectionQuery() }),
});
const body = await res.json();
if (body.errors) {
  console.error('introspection failed:', body.errors);
  process.exit(1);
}
const schema = buildClientSchema(body.data);
const sdl = printSchema(schema);
const out = process.argv[2];
writeFileSync(out, sdl + '\n');
console.log(`wrote ${out}: ${sdl.split('\n').length} lines`);
