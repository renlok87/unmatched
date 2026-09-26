import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

// Read-only audit of original D-09 art. Does not sync, download, redraw, or modify it.
const root = process.cwd();
const packageRoot = path.join(root, 'art/imagegen/mvp-v1');
const declared = fs.readFileSync('docs/game-design/06-asset-manifest.csv', 'utf8')
  .split(/\r?\n/).filter(l => l.startsWith('ASSET-CARDART-'))
  .map(l => { const [assetKey, , stableContentKey] = l.split(','); return {assetKey, stableContentKey}; });
const slug = v => String(v).normalize('NFKD').replace(/[\u0300-\u036f]/g, '')
  .replace(/['’]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
function inspect(ref) {
  if (!ref || typeof ref !== 'string') return {status:'no-source-reference'};
  const name = ref.split(/[?#]/)[0].split(/[\\/]/).filter(Boolean).pop();
  for (const dir of ['scraped-data/images/decks', 'docs/figma/figma-ready/decks']) {
    const candidate = path.join(root, dir, name);
    if (!fs.existsSync(candidate)) continue;
    const data = fs.readFileSync(candidate);
    return {status:'local-source-present', path:path.relative(root,candidate).replaceAll('\\','/'),
      bytes:data.length, sha256:crypto.createHash('sha256').update(data).digest('hex')};
  }
  return {status:'local-source-missing', fileName:name};
}
const cards = new Map();
for (const hero of ['medusa','king-arthur']) {
  const source = 'scraped-data/api/heroes/'+hero+'.json';
  const data = JSON.parse(fs.readFileSync(source,'utf8')).nodes[2].data;
  const resolve = i => typeof i === 'number' ? data[i] : i;
  for (const item of data) {
    if (!item || typeof item !== 'object' || ![1,2].includes(item.hero)) continue;
    const schema = resolve(item.card);
    const title = schema && resolve(schema.title);
    if (typeof title !== 'string') continue;
    const key = hero+':'+slug(title);
    if (cards.has(key)) continue;
    const translated = resolve(item.i18n);
    const ru = translated && resolve(translated.ru);
    cards.set(key, {stableContentKey:key,title,source, en:inspect(resolve(item.image)),
      ru:inspect(ru && resolve(ru.image))});
  }
}
const rows=declared.map(d=>({...d,...(cards.get(d.stableContentKey)||{status:'missing-card-record'})}));
const report={date:'2026-09-26',decision:'D-09: reuse original art; do not redraw with imagegen',
  sourceManifest:'docs/game-design/06-asset-manifest.csv', count:rows.length,
  localEn:rows.filter(r=>r.en?.status==='local-source-present').length,
  localRu:rows.filter(r=>r.ru?.status==='local-source-present').length,
  note:'Presence and hashes only. No runtime conversion, public sync, licensing or RU acceptance is implied.',cards:rows};
fs.writeFileSync(path.join(packageRoot,'reused-cardart.json'), JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({count:report.count,localEn:report.localEn,localRu:report.localRu}));
