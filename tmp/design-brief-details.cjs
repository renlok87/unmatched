const { chromium } = require('../backend/node_modules/playwright');
const fs = require('node:fs');
const path = require('node:path');
(async () => {
  const out = path.resolve(__dirname, 'design-brief-inspection');
  const report = JSON.parse(fs.readFileSync(path.join(out, 'report.json')));
  const browser = await chromium.launch({ headless: true, channel: 'msedge' });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  await page.goto('http://localhost:5480/login');
  await page.getByRole('button', { name: 'Sign In', exact: true }).click();
  await page.waitForURL('http://localhost:5480/');
  await page.waitForLoadState('networkidle');
  for (const section of ['/heroes', '/boards']) {
    await page.goto('http://localhost:5480' + section);
    await page.waitForLoadState('networkidle');
    await page.getByRole('button', { name: 'Edit', exact: true }).first().click();
    await page.waitForLoadState('networkidle');
    const body = await page.locator('body').innerText();
    console.log(section, body.slice(0, 3300));
    await page.screenshot({ path: path.join(out, section.slice(1) + '-edit.png'), fullPage: true });
  }
  const token = await page.evaluate(() => localStorage.getItem('accessToken'));
  async function query(query, variables={}) {
    const r = await fetch('http://localhost:3000/graphql', {method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+token},body:JSON.stringify({query,variables})});
    const j = await r.json(); if (j.errors) throw Error(JSON.stringify(j.errors.map(e=>e.message))); return j.data;
  }
  const catalog = await query('{ heroList(limit:100,page:1) { total items { id name } } boardList(limit:100,page:1) { total items { id name width height } } }');
  const heroes = [];
  for (const name of ['Medusa', 'King Arthur']) {
    const id = catalog.heroList.items.find(h=>h.name===name)?.id;
    if (!id) continue;
    const {adminHero:h} = await query('query($id:String!){adminHero(id:$id){id name health movement miniModelUrl characterCardUrl sidekicks cards {id name}}}',{id});
    heroes.push({id:h.id,name:h.name,health:h.health,movement:h.movement,hasMiniModel:!!h.miniModelUrl,hasCharacterArt:!!h.characterCardUrl,sidekicks:h.sidekicks,cardDefinitions:h.cards.length});
  }
  const b = catalog.boardList.items.find(b=>b.name==='Cobble City');
  let board;
  if(b){ const {adminBoard:v}=await query('query($id:String!){adminBoard(id:$id){id name width height cells features}}',{id:b.id}); const cells=JSON.parse(v.cells); board={id:v.id,name:v.name,width:v.width,height:v.height,cellCount:cells.length,sampleCells:cells.slice(0,2),features:v.features}; }
  const details={heroes,board}; fs.writeFileSync(path.join(out,'content-sample.json'),JSON.stringify(details,null,2));
  console.log('CONTENT_SAMPLE',JSON.stringify(details));
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
