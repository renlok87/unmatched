import {gql, loginPair, alias, save, state, scrub, out} from './capture.mjs';
import {clearCaptureArtifacts} from './cleanup.mjs';
clearCaptureArtifacts(out, 'live');
const users = await loginPair();
const [p1,p2] = users;
const created = [];
const resultFields = 'sequenceNumber phase turnCount currentTurnPlayerId timestamp state';
const cardFields = 'id name nameEn nameRu cardType count attackValue defenseValue boostValue bannerName textEn textRu effects effectImmediately effectDuring effectAfter effectBoost effectOngoing';
async function create(heroes, boardId, label) {
  const g = (await gql('mutation($b:String!){createGame(input:{mode:ONE_V_ONE,boardId:$b}){id code}}', {b:boardId}, p1.accessToken)).createGame;
  created.push(g.id); alias(g.id,label); alias(g.code,`${label}-code`);
  await gql('mutation($g:String!){joinGame(input:{gameId:$g}){id}}', {g:g.id},p2.accessToken);
  for (let i=0;i<2;i++) await gql('mutation($g:String!,$h:String!){selectHero(gameId:$g,heroId:$h){id}}', {g:g.id,h:heroes[i]},users[i].accessToken);
  for (const p of users) await gql('mutation($g:String!){toggleReady(gameId:$g){id}}',{g:g.id},p.accessToken);
  const start = await gql('mutation($g:String!){startGame(gameId:$g){id status players{id userId heroId seatOrder isReady}}}',{g:g.id},p1.accessToken);
  start.startGame.players.forEach((p,i)=>alias(p.id,`${label}-seat-${i}`));
  save(`${label}-lobby.json`,start);
  return g.id;
}
try {
  const medusa = (await gql('query{heroList(search:"Medusa",limit:5){items{id name}}}',{},p1.accessToken)).heroList.items.find(h=>h.name==='Medusa');
  const arthur = (await gql('query{heroList(search:"King Arthur",limit:5){items{id name}}}',{},p1.accessToken)).heroList.items.find(h=>h.name==='King Arthur');
  const board = (await gql('query{boardList(search:"Cobble City",limit:5){items{id name width height}}}',{},p1.accessToken)).boardList.items.find(h=>h.name==='Cobble City');
  for (const [label,h] of [['medusa',medusa],['king-arthur',arthur]]) {
    const admin = (await gql(`query($h:String!){adminHero(id:$h){id name health movement fighterType ability sidekicks updatedAt cards{${cardFields}}}}`,{h:h.id},p1.accessToken)).adminHero;
    save(`content-${label}.json`,admin);
    try {
      save(`catalog-${label}.json`,await gql('query($h:String!){hero(id:$h){id name health movement sidekickCount sidekickHealth abilities{id name text trigger} cards{id title type value boost quantity characterName effects{id timing text}}}}',{h:h.id},p1.accessToken));
    } catch(e) {
      save(`catalog-${label}-error.json`, {error:e.message});
      save(`catalog-${label}.json`,await gql('query($h:String!){hero(id:$h){id name health movement sidekickCount sidekickHealth cards{id title type value boost quantity characterName}}}',{h:h.id},p1.accessToken));
    }
    console.log(`${label}: ${admin.cards.length} records / ${admin.cards.reduce((n,c)=>n+c.count,0)} copies`);
  }
  save('content-board.json',await gql('query($b:String!){adminBoard(id:$b){id name width height cells features updatedAt}}',{b:board.id},p1.accessToken));
  const gameId = await create([medusa.id,arthur.id],board.id,'duel');
  const start = await state(gameId,p1.accessToken);
  save('duel-start-p1.json',start); save('duel-start-p2.json',await state(gameId,p2.accessToken));
  console.log(JSON.stringify(scrub({board:start.boardState,fighters:start.fighters,players:start.players,turn:start.currentTurnPlayerId,metadata:start.metadata}),null,2));
  for (let n=1;n<=2;n++) {
    const response=await gql(`mutation($g:String!){pass(input:{gameId:$g}){${resultFields}}}`,{g:gameId},p1.accessToken);
    save(`duel-pass-${n}.json`,response);
  }
  save('duel-after-pass-p2.json',await state(gameId,p2.accessToken));
  try {
    const dup = await create([medusa.id,medusa.id],board.id,'duplicate');
    save('duplicate-start.json',await state(dup,p1.accessToken));
    console.log('Duplicate hero selection AND start accepted.');
  } catch(e) { save('duplicate-error.json',{error:e.message}); console.log('Duplicate scenario rejected; saved response.'); }
} catch(e) { save('live-error.json',{error:e.message}); console.error(scrub(e.message)); process.exitCode=1; }
finally {
  for(const gameId of created) {
    try {await gql('mutation($g:String!){abortGame(gameId:$g){id status}}',{g:gameId},p1.accessToken); console.log('Closed only harness-created room.');}
    catch(e){save('cleanup-error.json',{gameId,error:e.message});}
  }
}
