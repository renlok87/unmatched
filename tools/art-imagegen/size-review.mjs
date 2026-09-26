import fs from 'node:fs';
import path from 'node:path';

// HTML presentation only. Original PNG pixels and metadata are unchanged.
const root=path.resolve('art/imagegen/mvp-v1');
const m=JSON.parse(fs.readFileSync(path.join(root,'manifest.json'),'utf8'));
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const glyphs=m.assets.filter(a=>a.status.startsWith('generated') && ['ui/actions','ui/resources','ui/zones','ui/cursors','markers'].includes(a.group) && a.kind!=='modeling-reference');
const rows=glyphs.map(a=>`<tr><th scope="row">${esc(a.id)}</th>${[24,32,48,96].map(size=>`<td><div class="samples"><span class="dark"><img width="${size}" height="${size}" src="${esc(a.path)}" alt="${esc(a.id)}"></span><span class="light"><img width="${size}" height="${size}" src="${esc(a.path)}" alt=""></span><span class="grey"><img width="${size}" height="${size}" src="${esc(a.path)}" alt=""></span></div></td>`).join('')}</tr>`).join('\n');
const html=`<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Проверка размеров UI</title>
<style>body{margin:28px;background:#20262e;color:#e7e5df;font:14px/1.5 system-ui}a{color:#e8c06a}h1{font-size:26px}table{border-collapse:collapse}th,td{text-align:left;border-bottom:1px solid #56606b;padding:8px}th{font-size:12px}.samples{display:flex;gap:6px;align-items:center}.samples span{padding:6px;display:inline-flex}.dark,.grey{background:#161b21}.light{background:#e6e2d9}.grey img{filter:grayscale(1)}img{object-fit:contain;display:block}p{max-width:1000px}</style>
<h1>Иконки: 24 / 32 / 48 / 96 CSS px</h1><p><a href="index.html">Каталог</a> · <a href="SPEC-COVERAGE.md">Покрытие спецификации</a></p>
<p>Для ручной проверки при масштабе браузера 100%. Каждый размер показан на тёмном, светлом и тёмном фоне с обесцвечиванием. Это CSS-представление неизменённых PNG, не готовый экспорт. Скриншот и приёмка 24 px пока не подтверждены.</p>
<table><thead><tr><th>Ассет</th><th>24</th><th>32</th><th>48</th><th>96</th></tr></thead><tbody>${rows}</tbody></table></html>`;
fs.writeFileSync(path.join(root,'size-review.html'),html);
console.log(JSON.stringify({glyphs:glyphs.length,path:path.join(root,'size-review.html')}));
