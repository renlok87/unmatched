import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {execFileSync} from 'node:child_process';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const repo=path.resolve(root,'../../..');
execFileSync(process.execPath,[path.join(repo,'tools/art-imagegen/catalog.mjs')],{cwd:repo,stdio:'inherit'});
const manifest=JSON.parse(fs.readFileSync(path.join(root,'manifest.json'),'utf8'));
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let html=fs.readFileSync(path.join(root,'index.html'),'utf8');
const labels={front:'Спереди',left:'Слева',back:'Сзади',right:'Справа',side:'Сбоку',top:'Сверху','three-quarter':'3/4 сверху'};
html=html.replace(/<article data-search="([^"]*)">[\s\S]*?<\/article>/g,(article,search)=>{
  const a=manifest.assets.find(a=>search.startsWith(a.id.toLowerCase()+' '));
  let extra='';
  if(a?.views){
    extra+=`<div class="view-strip">${a.views.map(v=>`<a href="${esc(v.path)}"><img loading="lazy" src="${esc(v.path)}" alt="${esc(labels[v.role])}"><span>${esc(labels[v.role])}</span></a>`).join('')}</div>`;
    article=article.replace('<article ','<article class="corrected" ');
  }
  if(a?.generationInputs)extra+='<p><a href="generation-inputs.json">Набор из трёх видов для 3D</a> · исправленный четвёртый вид остаётся кандидатом.</p>';
  if(a?.exports)extra+=`<details><summary>D / DirectX N / ORM</summary>${[2048,1024].map(size=>`<p>${size}: ${a.exports.filter(e=>e.width===size).map(e=>`<a href="${esc(e.path)}">${esc(e.kind)}</a>`).join(' · ')}</p>`).join('')}<p><a href="materials/export/previews/T_${esc(a.id.slice(4).toLowerCase().replaceAll('-','_'))}_D_tile2x2.png">Плитка2×2</a></p></details>`;
  if(a?.flipbooks)extra+=a.flipbooks.map(f=>`<p><a href="${esc(f.path)}">Flipbook4×4,2048² — кандидат</a></p><p class="review">Согласованность движения не принята; требуется Niagara.</p>`).join('');
  if(extra)article=article.replace('</div></article>',extra+'</div></article>');
  return article;
});
html=html.replace('</style>','.view-strip{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin-top:14px}.view-strip img{aspect-ratio:1/1}.view-strip span{font-size:11px}.corrected>a>img{aspect-ratio:1/1}.correction-note{border:1px solid #8b7745;padding:16px;margin:18px 0;max-width:1000px}details{margin-top:12px}</style>');
const current=manifest.correctionV3;
const heading=current?'Коррекция v3 · предложение':'Коррекция v2 · предложение';
const description=current?'Четыре боковых вида перерисованы; Harpy выровнена до 479–480 px. Положение меча и посоха между видами ещё требует согласования. Для 3D используйте указанные наборы из трёх видов. Оригиналы сохранены.':'29 отдельных видов 1024², 36 карт материалов, 5 flipbook-кандидатов 2048². Оригиналы сохранены.';
html=html.replace('<label for="filter">',`<section class="correction-note"><strong>${heading}</strong><p>${description}</p><p><a href="PRODUCTION-NOTES.md#коррекция-${current?'v3':'v2'}">Приёмка и ограничения</a> · <a href="${current?'correction-v3-verification.json':'correction-verification.json'}">Измерения</a> · <a href="${current?'normalized-views-v3-preview.png':'normalized-views-preview.png'}">Все персонажи</a> · ${current?'<a href="generation-inputs.json">Виды для 3D</a> · ':''}<a href="normalized-environment-preview.png">Окружение</a> · <a href="materials/export/previews/overview.png">Материалы 2×2</a></p></section><label for="filter">`);
html=html.replace('Все показанные файлы созданы встроенным imagegen.','Художественные исходники созданы встроенным imagegen; выбранные виды и карты технически обработаны с разрешения пользователя.');
fs.writeFileSync(path.join(root,'index.html'),html);
console.log(JSON.stringify({views:manifest.correction.normalizedModelViews,materials:manifest.correction.materialMaps,flipbooks:manifest.correction.flipbookCandidates}));
