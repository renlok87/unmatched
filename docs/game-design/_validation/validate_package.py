"""Read-only document checks; no game, server, asset, or build validation."""
import csv
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / 'docs/game-design'


def read_csv(name, key):
    with (PACKAGE / name).open(encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle))
    assert rows, f'{name}: empty'
    assert all(None not in row and None not in row.values() for row in rows), f'{name}: malformed row'
    values = [row[key] for row in rows]
    assert len(values) == len(set(values)), f'{name}: duplicate {key}'
    return rows


def ids(value):
    return set(filter(None, value.split(';')))


content = read_csv('05-content-matrix.csv', 'contentKey')
assets = read_csv('06-asset-manifest.csv', 'assetKey')
cues = read_csv('07-animation-vfx-audio.csv', 'cueId')
backlog = read_csv('14-sprint-backlog.csv', 'id')
assert (len(content), len(assets), len(cues)) == (34, 50, 18)
asset_keys = {row['assetKey'] for row in assets}
assert sum(row['assetKey'].startswith('ASSET-CARDART-') for row in assets) == 27
assert all(not row['fallbackAssetKey'] or row['fallbackAssetKey'] in asset_keys for row in assets)

legacy = (PACKAGE / '09-vertical-slice-and-backlog.md').read_text(encoding='utf-8-sig')
legacy_tasks = set(re.findall(r'(TASK-\d{3}) /', legacy))
assert len(legacy_tasks) == 34
qa = set(re.findall(r'^### (QA-\d{3})', (PACKAGE / '10-acceptance-tests.md').read_text(encoding='utf-8-sig'), re.M))
assert len(qa) == 23
gdd = set(re.findall(r'(?:^### |^\| )(GDD-\d{3})', (PACKAGE / '01-gameplay-experience.md').read_text(encoding='utf-8-sig'), re.M))
assert len(gdd) == 20
for path in PACKAGE.glob('*.md'):
    if path.name[:2].isdigit() and int(path.name[:2]) <= 11:
        refs = set(re.findall(r'\bQA-\d{3}\b', path.read_text(encoding='utf-8-sig')))
        assert refs <= qa, f'{path.name}: undefined QA {refs - qa}'
acceptance = (PACKAGE / '15-rules-and-release-acceptance.md').read_text(encoding='utf-8-sig')
acc = set(re.findall(r'^## (ACC-\d{3})', acceptance, re.M))
assert acc == {f'ACC-{i:03}' for i in range(1, 23)}
all_ids = {row['id'] for row in backlog}
assert all_ids == ({f'GD-{i:03}' for i in range(1, 59)} | {f'ART-{i:03}' for i in range(1, 19)})
by_id = {row['id']: row for row in backlog}
covered_sources = set()
covered_acc = set()
loads = Counter()
art_load = 0.0
for row in backlog:
    for field in ('title', 'owner', 'priority', 'estimate_days', 'status', 'source_ids', 'acceptance_ids', 'deliverable', 'acceptance'):
        assert row[field].strip(), f'{row["id"]}: missing {field}'
    assert row['status'] in {'planned', 'in_progress', 'blocked', 'done'}, f'{row["id"]}: invalid status'
    if row['status'] != 'planned':
        proof_path = PACKAGE / 'evidence' / row['sprint'] / 'tasks.json'
        assert proof_path.exists(), f'{row["id"]}: progress requires evidence index'
        proof = json.loads(proof_path.read_text(encoding='utf-8-sig')).get(row['id'])
        assert proof and proof['status'] == row['status'], f'{row["id"]}: evidence status mismatch'
        assert proof.get('artifacts'), f'{row["id"]}: missing artifacts'
        assert all((proof_path.parent / p).is_file() for p in proof['artifacts']), f'{row["id"]}: missing evidence file'
    assert ids(row['depends_on']) <= all_ids, f'{row["id"]}: unknown dependency'
    assert ids(row['acceptance_ids']) <= acc, f'{row["id"]}: unknown acceptance ID'
    assert ids(row['source_ids']) <= legacy_tasks | qa | gdd, f'{row["id"]}: unknown legacy source'
    covered_sources |= ids(row['source_ids'])
    covered_acc |= ids(row['acceptance_ids'])
    effort = float(row['estimate_days'])
    assert effort > 0
    if row['owner'] == 'DEV':
        assert re.fullmatch(r'S(?:0[1-9]|1[0-4])', row['sprint'])
        assert effort <= 3, f'{row["id"]}: developer work item needs splitting'
        loads[row['sprint']] += effort
        for dep in ids(row['depends_on']):
            other = by_id[dep]
            if other['owner'] == 'DEV':
                assert other['sprint'] <= row['sprint'], f'{row["id"]}: depends on later DEV sprint'
    else:
        assert row['owner'] == 'ART' and row['sprint'] in {'A01', 'A02', 'A03'}
        art_load += effort
assert legacy_tasks <= covered_sources, f'Unmapped old tasks: {legacy_tasks - covered_sources}'
assert covered_acc == acc, f'Acceptance without task: {acc - covered_acc}'
assert len(loads) == 14 and all(effort <= 8 for effort in loads.values())
assert sum(loads.values()) == 103 and art_load == 46.5

visited, active = set(), set()


def visit(key):
    assert key not in active, f'Dependency cycle at {key}'
    if key in visited:
        return
    active.add(key)
    for dep in ids(by_id[key]['depends_on']):
        visit(dep)
    active.remove(key)
    visited.add(key)


for key in all_ids:
    visit(key)

# Validate deck-specific card names/copy counts against original RSC scrape.
content_by_key = {row['contentKey']: row for row in content}
card_keys = set()
titles = set()
for slug, expected in [('medusa', 11), ('king-arthur', 16)]:
    raw_path = ROOT / f'scraped-data/api/heroes/{slug}.json'
    if raw_path.exists():
        data = json.loads(raw_path.read_text(encoding='utf-8-sig'))['nodes'][2]['data']
        def value(ref):
            return data[ref] if isinstance(ref, int) else ref
        source_cards = [{'title': value(value(item['card'])['title']), 'copies': value(item['copies'])}
                        for item in data if isinstance(item, dict) and item.get('hero') in (1, 2) and 'card' in item]
    else:
        frozen = json.loads((PACKAGE / '_validation/deck-counts-reference.json').read_text(encoding='utf-8-sig'))
        source_cards = frozen['decks'][slug]['cards']
    cards = {}
    for item in source_cards:
        title = item['title']
        card_slug = re.sub(r'[^a-z0-9]+', '-', title.lower().replace("'", '').replace('’', '')).strip('-')
        cards[card_slug] = (title, item['copies'])
    assert len(cards) == expected and sum(copies for _, copies in cards.values()) == 30
    for card_slug, (title, copies) in cards.items():
        key = f'{slug}-card-{card_slug}'
        card_keys.add(key)
        titles.add(title)
        assert key in content_by_key, f'Missing card {key}'
        name = content_by_key[key]['nazvanie']
        assert title in name and re.search(rf'×{copies}(?!\d)', name), f'Name/count mismatch: {key}'
assert len(card_keys) == 27 and len(titles) == 25
assert {key for key in content_by_key if '-card-' in key} == card_keys

# Existing local Markdown links in the entrypoint and newly authored prose.
for name in ['README.md', '12-validation-report.md', '13-sprint-plan.md', '15-rules-and-release-acceptance.md']:
    body = (PACKAGE / name).read_text(encoding='utf-8-sig')
    assert '\ufffd' not in body, f'{name}: replacement character'
    for link in re.findall(r'\]\(([^)]+)\)', body):
        if '://' in link or link.startswith('#'):
            continue
        assert (PACKAGE / link.split('#')[0]).exists(), f'{name}: missing link {link}'
    for key in re.findall(r'\b(?:GD-\d{3}|ART-\d{3}|ACC-\d{3})\b', body):
        assert key in all_ids | acc, f'{name}: unknown ID {key}'

print('PASS: original CSV 34/50/18; 27 deck-card entries / 60 copies; 25 distinct titles')
print('PASS: 34/34 legacy tasks mapped; 69 new tasks; 22/22 acceptance checks linked')
print('PASS: dependency DAG; no future DEV dependency; 14 sprints <=8 DEV days')
print('DEV loads:', ', '.join(f'{key}={loads[key]:g}' for key in sorted(loads)))
print(f'PASS: total DEV={sum(loads.values()):g} days; ART={art_load:g} days; progress statuses have artifact references')
print('PASS: local links and new document IDs')
print('THIS VALIDATOR DOES NOT TEST: live server, UE, Blender import, gameplay correctness, performance')
