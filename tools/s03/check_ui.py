"""Playwright controls check. Start Vite on 5193 before running.
Real GameView/store; captured HTTP responses and a labeled board-event adapter.
This checks browser interactions, not Phaser rendering or deployed networking.
"""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

root = Path(__file__).resolve().parents[2]
out = root / 'docs/game-design/evidence/S03'
board = """export const PhaserGame = ({onGameEvent}) => window.React.createElement(
  'div', {style:{padding:24}}, 'S03: board-event test adapter ',
  ...[1,2,3,4,5].map(x => window.React.createElement('button', {
    key:x, onClick:()=>onGameEvent({type:'SPACE_CLICKED',position:{x,y:0}})
  }, 'Cell '+x)));
"""

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, channel='msedge')
    page = browser.new_page(viewport={'width':1440,'height':900})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.route('**/src/phaser/PhaserGame.tsx*', lambda route: route.fulfill(content_type='text/javascript', body=board))
    page.goto('http://127.0.0.1:5193/tools/s03/ui-smoke.html')
    page.wait_for_load_state('networkidle')
    expect(page.get_by_role('button', name='Начать манёвр')).to_be_visible()
    expect(page.get_by_role('button', name='Конец хода')).to_have_count(0)
    expect(page.get_by_role('button', name='Pass', exact=True)).to_have_count(0)
    page.get_by_role('button', name='Начать манёвр').click()
    expect(page.get_by_label('Выбор манёвра', exact=True)).to_be_visible()
    expect(page.get_by_label('Усиление манёвра')).to_contain_text('a-new')
    page.get_by_role('button', name='Завершить без движения').click()
    expect(page.get_by_role('button', name='Начать манёвр')).to_be_visible()
    calls = page.evaluate('window.s03.calls')
    assert len(calls) == 2 and calls[0]['variables']['input']['expectedSequenceNumber'] == 10
    assert calls[1]['variables']['input']['moves'] == []
    assert calls[1]['variables']['input']['maneuverId'] == 'maneuver:1:10'

    # Load a persisted pending stage, just as snapshot recovery does.
    page.evaluate("window.s03.load('begin-boost')")
    expect(page.get_by_label('Выбор манёвра', exact=True)).to_be_visible()
    page.get_by_label('Усиление манёвра').select_option('a-new')
    page.get_by_label('Боец для движения').select_option('a')
    for x in range(1, 6):
        page.get_by_role('button', name=f'Cell {x}', exact=True).click()
    page.screenshot(path=str(out / 'ui-maneuver.png'), full_page=True)
    page.get_by_role('button', name='Подтвердить манёвр').click()
    expect(page.get_by_label('Выбор манёвра', exact=True)).to_have_count(0)
    boosted = page.evaluate('window.s03.calls.at(-1).variables.input')
    assert boosted['boostCardId'] == 'a-new'
    assert boosted['moves'] == [{'fighterId':'a','path':[{'x':x,'y':0} for x in range(1,6)]}]

    page.evaluate("window.s03.load('discard-db-snapshot')")
    expect(page.get_by_label('Сброс в конце хода', exact=True)).to_be_visible()
    submit = page.get_by_role('button', name='Сбросить выбранные карты')
    expect(submit).to_be_disabled()
    page.locator('input[type=checkbox][value="h1"]').check()
    expect(submit).to_be_enabled()
    page.screenshot(path=str(out / 'ui-discard.png'), full_page=True)
    submit.click()
    expect(page.get_by_label('Сброс в конце хода', exact=True)).to_have_count(0)
    discarded = page.evaluate('window.s03.calls.at(-1).variables.input')
    assert discarded['cardIds'] == ['h1']
    assert not errors, errors
    (out / 'ui-verification.json').write_text(json.dumps({
        'scope':'Production GameView/store in Edge; captured transport responses; Phaser replaced by board-event adapter',
        'checks':['begin then zero movement','persisted pending then fresh-card boost and five path steps','persisted excess discard by instance'],
        'requests':page.evaluate('window.s03.calls'), 'pageErrors':errors,
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    browser.close()
print('S03 browser controls: 3 scenarios passed')
