import {gql, loginPair, alias, save, state, scrub, requireSource, endpoint, stateFields, decoded, out} from './capture.mjs';
import {clearCaptureArtifacts} from './cleanup.mjs';
clearCaptureArtifacts(out, 'combat');
const users = await loginPair();
const [p1,p2] = users;
const WebSocket = requireSource('ws');
const created = [];
const sockets = [];
const resultFields = 'sequenceNumber phase turnCount currentTurnPlayerId timestamp state';
const delay = ms => new Promise(r=>setTimeout(r,ms));
const findings = {capturedUtc:new Date().toISOString(),endpoint,scenarios:{}};
async function mutate(name,type,input,p) {
  return (await gql(`mutation($i:${type}!){${name}(input:$i){${resultFields}}}`,{i:input},p.accessToken))[name];
}
async function create(label) {
  const find = async (search,field) => (await gql(`query($s:String!){${field}(search:$s,limit:5){items{id name}}}`,{s:search},p1.accessToken))[field].items.find(h=>h.name===search).id;
  const m=await find('Medusa','heroList'), a=await find('King Arthur','heroList'), b=await find('Cobble City','boardList');
  const g=(await gql('mutation($b:String!){createGame(input:{mode:ONE_V_ONE,boardId:$b}){id code}}',{b},p1.accessToken)).createGame;
  created.push(g.id); alias(g.id,label); alias(g.code,`${label}-code`);
  await gql('mutation($g:String!){joinGame(input:{gameId:$g}){id}}',{g:g.id},p2.accessToken);
  for (let i=0;i<2;i++) {
    await gql('mutation($g:String!,$h:String!){selectHero(gameId:$g,heroId:$h){id}}',{g:g.id,h:[m,a][i]},users[i].accessToken);
    await gql('mutation($g:String!){toggleReady(gameId:$g){id}}',{g:g.id},users[i].accessToken);
  }
  await gql('mutation($g:String!){startGame(gameId:$g){id}}',{g:g.id},p1.accessToken);
  save(`${label}-start.json`,await state(g.id,p1.accessToken));
  return g.id;
}
async function subscribe(gameId,p,label) {
  const events=[];
  const socket = new WebSocket(endpoint.replace(/^http/,'ws'),'graphql-transport-ws'); sockets.push(socket);
  await new Promise((resolve,reject)=>{
    const timer=setTimeout(()=>reject(new Error('WS ack timeout')),5000);
    socket.on('open',()=>socket.send(JSON.stringify({type:'connection_init',payload:{authorization:`Bearer ${p.accessToken}`}})));
    socket.on('error',reject);
    socket.on('message',data=>{
      const message=JSON.parse(data.toString());
      if(message.type==='connection_ack') {
        socket.send(JSON.stringify({id:'s01',type:'subscribe',payload:{query:`subscription($g:String!){gameStateUpdated(gameId:$g){${stateFields}}}`,variables:{g:gameId}}}));
        clearTimeout(timer);resolve();
      } else if(message.type==='ping') socket.send(JSON.stringify({type:'pong'}));
      else {events.push({receivedUtc:new Date().toISOString(),...message});save(`${label}-ws.json`,events);}
    });
    socket.on('close',(code)=>{clearTimeout(timer);if(code!==1000)reject(new Error(`WS closed ${code}`));});
  });
  return {events,close:()=>socket.close(1000)};
}
function attackCard(s,p) {
  const cards=s.handZones[p.user.id].cards.filter(c=>['ATTACK','VERSATILE','UNIVERSAL'].includes(c.cardType) && ['Any','Medusa'].includes(c.bannerName));
  return cards.find(c=>c.name==='Feint') || cards.find(c=>c.name==='Regroup') || cards[0];
}
async function ensureCard(gameId,p) {
  let s=await state(gameId,p.accessToken);
  if(!attackCard(s,p)) throw new Error('No attack usable by Medusa in current random hand; rerun isolated scenario.');
  return s;
}
try {
  const g=await create('combat');
  const w1=await subscribe(g,p1,'combat-p1'), w2=await subscribe(g,p2,'combat-p2');
  try {await mutate('maneuver','ManeuverDto',{gameId:g,moves:[]},p1);findings.scenarios.zeroMove='accepted';}
  catch(e){save('combat-zero-move-error.json',{error:e.message});findings.scenarios.zeroMove='rejected';}
  const moved=await mutate('maneuver','ManeuverDto',{gameId:g,fighterId:'f-0-hero',path:[{x:1,y:2},{x:0,y:2},{x:0,y:3}]},p1);
  save('combat-maneuver.json',moved);
  await mutate('pass','PassDto',{gameId:g},p1);
  await mutate('pass','PassDto',{gameId:g},p2);
  const beforeGaze=await state(g,p1.accessToken);save('combat-before-gaze.json',beforeGaze);
  await mutate('pass','PassDto',{gameId:g},p2);
  const afterGaze=await state(g,p1.accessToken);save('combat-after-gaze.json',afterGaze);
  findings.scenarios.gaze = {before:beforeGaze.fighters.map(f=>({id:f.id,hp:f.health})),after:afterGaze.fighters.map(f=>({id:f.id,hp:f.health})),pending:afterGaze.metadata.pendingEffects};
  const s=await ensureCard(g,p1), card=attackCard(s,p1);
  const target=s.fighters.find(f=>f.id==='f-1-sk0');
  const attack=await mutate('attack','AttackDto',{gameId:g,attackerId:'f-0-hero',targetId:target.id,cardId:card.id},p1);
  save('combat-attack.json',{selectedInstance:card.id,selectedCatalogId:card.cardId,beforeHand:s.handZones[p1.user.id],response:attack});
  await delay(350);
  save('combat-attack-p2.json',await state(g,p2.accessToken));
  findings.scenarios.sameZoneRanged={from:s.fighters.find(f=>f.id==='f-0-hero').position,to:target.position,accepted:true};
  findings.scenarios.wsAttack={p1Events:w1.events.length,p2Events:w2.events.length,p1Attack:w1.events.find(e=>e.payload?.data?.gameStateUpdated?.sequenceNumber===attack.sequenceNumber),p2Attack:w2.events.find(e=>e.payload?.data?.gameStateUpdated?.sequenceNumber===attack.sequenceNumber)};
  const defenseState=await state(g,p2.accessToken);
  const defense=defenseState.handZones[p2.user.id].cards.find(c=>['DEFENSE','VERSATILE','UNIVERSAL'].includes(c.cardType) && ['Any','Merlin'].includes(c.bannerName));
  if(defense) save('combat-defense.json',{selectedInstance:defense.id,response:await mutate('playDefense','PlayDefenseDto',{gameId:g,cardId:defense.id},p2)});
  else findings.scenarios.defense='blocked: random hand has no eligible Merlin defense';
  save('combat-resolve.json',await mutate('resolveCombat','ResolveCombatDto',{gameId:g},p1));
  save('combat-after-resolve.json',await state(g,p1.accessToken));
  save('combat-events-since.json',await gql('query($g:String!){eventsSince(gameId:$g,sinceSequence:0){gameId lastSequence hasMore events{type gameId sequenceNumber payload timestamp}}}',{g},p1.accessToken));
  w1.close();w2.close();
  console.log('Maneuver, start-of-turn gaze, ranged attack, instance ID, WS and explicit combat captured.');
  const timeoutGame=await create('timeout');
  const tw=await subscribe(timeoutGame,p1,'timeout');
  await mutate('maneuver','ManeuverDto',{gameId:timeoutGame,fighterId:'f-0-hero',path:[{x:1,y:2}]},p1);
  const ts=await ensureCard(timeoutGame,p1), tc=attackCard(ts,p1);
  const timeoutAttack=await mutate('attack','AttackDto',{gameId:timeoutGame,attackerId:'f-0-hero',targetId:'f-1-hero',cardId:tc.id},p1);
  save('timeout-attack.json',timeoutAttack); await delay(350);tw.close();
  console.log('Waiting 32 seconds with WebSocket clients closed; no defense or resolve commands.');
  const started=Date.now();await delay(32000);
  const afterTimeout=await state(timeoutGame,p1.accessToken);save('timeout-after.json',afterTimeout);
  findings.scenarios.timeout={elapsedMs:Date.now()-started,attackSequence:timeoutAttack.sequenceNumber,afterSequence:afterTimeout.sequenceNumber,phase:afterTimeout.phase,hp:afterTimeout.fighters.map(f=>({id:f.id,hp:f.health})),clientsClosed:true};
} catch(e) {findings.error=e.message; console.error(scrub(e.message));process.exitCode=1;}
finally {
  for (const socket of sockets) if(socket.readyState===WebSocket.OPEN)socket.close(1000);
  for(const gameId of created) {
    try {await gql('mutation($g:String!){abortGame(gameId:$g){id status}}',{g:gameId},p1.accessToken);}
    catch(e){findings.cleanupError=e.message;}
  }
  save('combat-findings.json',findings);
  console.log('Combat evidence saved; only harness-created rooms closed.');
}
