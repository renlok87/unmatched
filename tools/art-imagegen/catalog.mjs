import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

// Metadata inspection only. Image pixels are never transformed by this script.
const root = path.resolve('art/imagegen/mvp-v1');
const manifestPath = path.join(root, 'manifest.json');
const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8').replace(/^\uFEFF/, ''));
const signature = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
let checked = 0;
for (const asset of manifest.assets) {
  if (!asset.status.startsWith('generated')) continue;
  const file = path.resolve(root, asset.path);
  if (!file.startsWith(root + path.sep)) throw new Error(`Path outside catalog: ${asset.id}`);
  const data = fs.readFileSync(file);
  if (!data.subarray(0, 8).equals(signature)) throw new Error(`Invalid PNG: ${asset.id}`);
  if (data.readUInt32BE(16) !== asset.width || data.readUInt32BE(20) !== asset.height) {
    throw new Error(`Dimension mismatch: ${asset.id}`);
  }
  const hash = crypto.createHash('sha256').update(data).digest('hex');
  if (hash !== asset.sha256) throw new Error(`Hash mismatch: ${asset.id}`);
  if (!fs.existsSync(path.join(root, asset.promptPath))) throw new Error(`Missing prompt: ${asset.id}`);
  checked++;
}
const generated = manifest.assets.filter(a => a.status.startsWith('generated'));
const reviewed = generated.filter(a => a.status === 'generated-reviewed');
if (manifest.progress.generated !== generated.length || manifest.progress.reviewed !== reviewed.length || manifest.progress.total !== manifest.assets.length) {
  throw new Error('Progress counters do not match assets');
}
const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const cards = generated.map(a => `<article data-search="${esc(`${a.id} ${a.name} ${a.group}`.toLowerCase())}"><a href="${esc(a.path)}"><img loading="lazy" src="${esc(a.path)}" alt="${esc(a.name)}"></a><div class="copy"><small>${esc(a.group)} · ${a.width} × ${a.height} · ${a.alpha ? 'alpha' : 'RGB'}</small><h2>${esc(a.id)}</h2><p>${esc(a.name)}</p><p class="review">${esc(a.review?.notes ?? 'Ожидает визуальной проверки')}</p><a href="${esc(a.promptPath)}">Промпт</a> · <a href="${esc(a.path)}" download>PNG</a></div></article>`).join('\n');
const html = `<!doctype html>
<html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MVP · Imagegen</title>
<style>body{margin:0;background:#161b21;color:#e5e3dc;font:16px/1.5 system-ui,sans-serif}header,main{max-width:1500px;margin:auto;padding:32px}header{border-bottom:1px solid #39414a}h1{font-size:38px;margin:0 0 12px}p{margin:8px 0}.sub{max-width:960px;color:#b8c1c9}.count{color:#e8c06a;font-weight:650}input{box-sizing:border-box;margin-top:20px;max-width:560px;width:100%;padding:12px;background:#252c34;border:1px solid #515c69;color:white;font:inherit;border-radius:6px}input:focus{outline:2px solid #e8c06a;outline-offset:2px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));gap:24px}article{border:1px solid #3c454e;background:#20262e;border-radius:8px;overflow:hidden}img{width:100%;display:block;aspect-ratio:2/1;object-fit:contain;background:repeating-conic-gradient(#363c44 0% 25%,#41474f 0% 50%) 50%/24px 24px}.copy{padding:20px}h2{font-size:18px;margin:8px 0}small,.review{font-size:13px;color:#b2bec9}a{color:#e8c06a}[hidden]{display:none}footer{padding:28px 0;color:#aeb9c4}</style>
<header><p class="count">${generated.length} / ${manifest.assets.length} изображений · просмотрено ${reviewed.length}</p><h1>MVP — визуальные исходники</h1><p class="sub">Предложения по спецификации 17: модели, диорама, HUD, маркеры, VFX. PNG-референсы не заменяют модели, риг и материалы UE. Приёмка GD-058 открыта.</p><p><a href="README.md">Описание поставки</a> · <a href="manifest.json">Полный реестр</a></p><label for="filter">Найти ассет</label><br><input id="filter" type="search" placeholder="Medusa, UI, environment…"></header>
<main><div class="grid">${cards}</div><footer>Все показанные файлы созданы встроенным imagegen. Размеры и SHA-256 сверены с реестром. Тексты интерфейса не запекаются в изображения.</footer></main>
<script>document.querySelector('#filter').addEventListener('input',e=>{const q=e.target.value.trim().toLowerCase();document.querySelectorAll('article').forEach(a=>a.hidden=!a.dataset.search.includes(q))})</script></html>`;
fs.writeFileSync(path.join(root, 'index.html'), html);
console.log(JSON.stringify({checkedPngs: checked, reviewed: reviewed.length, planned: manifest.assets.length-generated.length, gallery: path.join(root, 'index.html')}));
