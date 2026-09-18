"""Check captured observations, not conformance of the server to Unmatched rules."""
import collections, hashlib, json, pathlib
root = pathlib.Path(__file__).resolve().parents[2]
evidence = root / 'docs/game-design/evidence/S01'
def read(name):
    return json.loads((evidence / name).read_text(encoding='utf-8-sig'))
def summary(state):
    return {
        'sequence': state['sequenceNumber'], 'turn': state['currentTurnPlayerId'],
        'actions': state['metadata']['actionsRemaining'],
        'hands': {p: len(h['cards']) for p,h in state['handZones'].items()},
        'drawPiles': {p: len(h.get('drawPile', [])) for p,h in state['decks'].items()},
        'discardPiles': {p: len(h) for p,h in state['discardPiles'].items()},
        'hp': {f['id']: f['health'] for f in state['fighters']},
    }
start = read('duel-start-p1.json')
board = start['boardState']
cells = [c for row in board['cells'] for c in row]
assert len(cells) == board['width'] * board['height'] == 30
assert len({(c['x'],c['y']) for c in cells}) == 30
assert len(start['fighters']) == 6
assert len({(f['position']['x'], f['position']['y']) for f in start['fighters']}) == 6
counts = {}
for slug, player, records in [('medusa','player-1',11),('king-arthur','player-2',16)]:
    catalog = read(f'content-{slug}.json')['cards']
    assert len(catalog) == records and sum(c['count'] for c in catalog) == 30
    private_start = read(f'duel-start-p{1 if player == "player-1" else 2}.json')
    instances = private_start['handZones'][player]['cards'] + private_start['decks'][player]['drawPile']
    assert len(instances) == len({c['id'] for c in instances}) == 30
    assert collections.Counter(c['cardId'] for c in instances) == {c['id']:c['count'] for c in catalog}
    counts[slug] = {'records':records,'instances':len(instances),'hand':len(private_start['handZones'][player]['cards'])}
pass1 = read('duel-pass-1.json')['pass']['state']
pass2 = read('duel-pass-2.json')['pass']['state']
combat = read('combat-findings.json')
attack = read('combat-attack.json')
selected = attack['selectedInstance']
assert any(c['id'] == selected for c in attack['beforeHand']['cards'])
after_attack = attack['response']['state']
assert not any(c['id'] == selected for c in after_attack['handZones']['player-1']['cards'])
assert any(c['id'] == selected for c in after_attack['discardPiles']['player-1'])
ws = combat['scenarios']['wsAttack']
assert ws.get('p1Attack') and ws.get('p2Attack'), 'Need both live WS attack projections'
ws_metadata = ws['p2Attack']['payload']['data']['gameStateUpdated']['metadata']
points = []
for x,y in [(0,0),(4,5),(2,2),(2,3)]:
    world = [(x-(board['width']-1)/2)*100,(y-(board['height']-1)/2)*100,0]
    assert (round(world[0]/100+(board['width']-1)/2),round(world[1]/100+(board['height']-1)/2)) == (x,y)
    points.append({'cell':[x,y],'world':world})
result = {
    'kind':'observed-baseline-not-rules-conformance',
    'content':counts,
    'board':{'width':board['width'],'height':board['height'],'cells':len(cells),
        'zones':sorted({z for c in cells for z in c.get('zones',[])}),
        'multizoneCells':sum(len(c.get('zones',[]))>1 for c in cells),
        'explicitAdjacencyInPayload':any('neighbors' in c or 'adjacent' in c for c in cells),
        'startingMarkersInPayload':any('startingPositions' in c or 'startingPositionsJson' in c for c in cells),
        'controlPoints':points,'finalArtGate':'OPEN: grid confirmed; tactical graph and start regions not approved'},
    'states':{name:summary(s) for name,s in [('start',start),('pass1',pass1),('pass2',pass2)]},
    'handMaxSize':{p:h['maxSize'] for p,h in start['handZones'].items()},
    'cardTypes':sorted({c['cardType'] for h in start['handZones'].values() for c in h['cards']}),
    'instanceMutation':{'selectedInstance':selected,'removedFromHand':True,'foundInDiscard':True},
    'gaze':combat['scenarios']['gaze'],
    'timeoutAtInWsMetadata':'timeoutAt' in ws_metadata,
    'timeoutAtInCombatInfo':'timeoutAt' in ws_metadata.get('combatInfo',{}),
    'wsCombatInfo':ws_metadata.get('combatInfo'),
    'timeout':combat['scenarios']['timeout'],
    'arthurMovement':{'catalog':read('catalog-king-arthur.json')['hero']['movement'],
        'content':read('content-king-arthur.json')['movement'],
        'fighter':next(f['movement'] for f in start['fighters'] if f['name']=='King Arthur')},
    'schemaSha256':hashlib.sha256((evidence/'schema.graphql').read_bytes()).hexdigest(),
    'checksPassed':['30 unique coordinates','6 non-overlapping fighters','27 records / 60 unique deck instances',
        'instance counts match live content','selected attack instance moved from hand to discard','both WS attack projections',
        '4 world-cell round trips'],
}
(evidence/'observations.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2,ensure_ascii=False))
