import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const read=name=>JSON.parse(fs.readFileSync(path.join(root,name),'utf8').replace(/^\uFEFF/,''));
const manifest=read('manifest.json');
const characters=read('normalized-views.json').outputs;
const environment=read('normalized-environment.json').outputs;
const materials=read('material-exports.json');
const flipbooks=read('flipbook-exports.json').outputs;
const notes={
  'REF-KING-ARTHUR':'Four distinct views, simple badge, smooth armor, crown and upright right-hand sword. Canvas/base/background calibrated; exact cross-view anatomy and thin-part thickness remain review gates.',
  'REF-MEDUSA':'Seven visible snake heads in each view, left-hand bow, consistent quiver concept. Canvas/base/background calibrated. Exact snake root correspondence, bow orientation and final string thickness require 3D reconciliation.',
  'REF-MERLIN':'Indigo hood, short braided beard, Celtic trim, crystal on knotted staff; no broad-brim hat or forked staff. Human identity review and staff thickness remain open.',
  'REF-HARPY':'Crouched, wider than tall, large feather groups, left ankle band. Canvas/base/background calibrated; wing pose and feather correspondence require 3D reconciliation.',
  'REF-BOARD-COBBLE':'Neutral5x6 grid, selected top technically resized to5:6; separate side slab reference. Quantitative cell brightness in correction-verification.json; no zone colors.',
  'REF-BARREL':'Four separate front/side/top/three-quarter references. Front bung distinguishes side. Precise hoop/stave geometry remains a modeling constraint.',
  'REF-LANTERN':'Four separate unlit elevations, dark glass and no flame. Door hardware drifts across views and needs Blender reconciliation.',
  'REF-TABLE-BASE':'Separate3/4,front,side; rocky underside retained. Front/side display widths normalized5:6. Exact3D550x660 footprint and rock correspondence are not proven by the images.'
};
const derived=[...characters,...environment,...materials.outputs,...flipbooks].map(r=>{
  const parent=manifest.assets.find(a=>a.id===r.assetId);
  if(!parent)throw new Error('Unknown parent '+r.assetId);
  const source=manifest.correctionDeliverables.find(d=>d.path===r.source);
  return {...r,promptPath:source?.promptPath??parent.promptPath,status:'generated-reviewed',approval:'proposal',generationTool:'imagegen source; scripted technical derivation',review:{result:r.role==='flipbook'?'candidate; temporal acceptance not passed':'proposal; see acceptance report',notes:notes[r.assetId]??(r.kind?'Lanczos basecolor or luminance-derived DirectX normal/ORM proposal; wood horizontal tiling seam needs correction.':'Sixteen generated frames, technical padding verified separately. Frame shape/anchor drift remains; Niagara/manual animation required.')}};
});
for(const asset of manifest.assets){
  const list=derived.filter(r=>r.assetId===asset.id);
  if(!list.length)continue;
  if(asset.group==='vfx'){
    asset.flipbooks=list;
    continue; // Original single particles remain selected; candidates are additional.
  }
  const primary=list.find(r=>r.role==='front')??list.find(r=>r.role==='top')??list.find(r=>r.role==='three-quarter')??list.find(r=>r.kind==='D'&&r.width===2048);
  if(!primary)throw new Error('No primary '+asset.id);
  if(asset.path!==primary.path){
    const {previousVersions,views,exports,flipbooks,...old}=asset;
    asset.previousVersions??=[];
    if(!asset.previousVersions.some(p=>p.path===old.path))asset.previousVersions.push(old);
  }
  for(const k of ['path','width','height','bytes','sha256','alpha','promptPath','generationTool','status','review'])asset[k]=primary[k];
  asset.sourcePath=path.join(root,primary.source);
  asset.derivation={script:asset.group==='materials'?'_tools/export-materials.py':asset.group==='characters'?'_tools/normalize-views.py':'_tools/normalize-environment.py',source:primary.source,sourceSha256:primary.sourceSha256};
  if(asset.group==='materials')asset.exports=list; else asset.views=list;
}
const previewPaths=[...materials.previews.map(r=>r.path),'materials/export/previews/overview.png','normalized-views-preview.png','normalized-environment-preview.png',...['impact','damage','death-ash','petrify','heal'].map(n=>`vfx/previews/vfx-${n}-flipbook-contact.png`)];
manifest.auditPreviews=previewPaths.map(relative=>{
  const b=fs.readFileSync(path.join(root,relative));
  return {path:relative,width:b.readUInt32BE(16),height:b.readUInt32BE(20),alpha:[4,6].includes(b[25]),bytes:b.length,sha256:crypto.createHash('sha256').update(b).digest('hex'),kind:'technical-review-preview'};
});
manifest.derivedDeliverables=derived;
manifest.correction={brief:'CORRECTION-BRIEF.md',handoffCommit:'571ea46',status:'delivered-with-open-acceptance-gates',generatedFiles:manifest.correctionDeliverables.length,normalizedModelViews:characters.length+environment.length,materialMaps:materials.outputs.length,flipbookCandidates:flipbooks.length,previewFiles:previewPaths.length,originalsPreserved:true,normalizationAuthorization:'User: Да, нормализовать скриптом, оригиналы сохранить',verification:'correction-verification.json',acceptanceReport:'PRODUCTION-NOTES.md#коррекция-v2',openGates:['Exact cross-view3D consistency and thin parts; human Merlin review','Wood horizontal tiling seam; UE material response','Flipbook temporal consistency; death-ash raw crop boundary; Niagara authoring','Rodin/Blender/UE production and GD-058']};
fs.writeFileSync(path.join(root,'manifest.json'),JSON.stringify(manifest,null,2)+'\n');
console.log(JSON.stringify(manifest.correction));
