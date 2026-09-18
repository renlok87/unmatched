"""Freeze only non-secret title/copy-count facts needed by the package validator."""
import datetime, hashlib, json, pathlib
root=pathlib.Path(__file__).resolve().parents[2]
source=pathlib.Path(r'C:\Users\ren\WebstormProjects\unmached\unmached\scraped-data\api\heroes')
result={'capturedUtc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'origin':'existing RSC scrape in original workspace; extract, not a new web scrape','decks':{}}
for slug in ['medusa','king-arthur']:
    p=source/f'{slug}.json'
    data=json.loads(p.read_text(encoding='utf-8-sig'))['nodes'][2]['data']
    def value(ref):return data[ref] if isinstance(ref,int) else ref
    cards={}
    for item in data:
        if isinstance(item,dict) and item.get('hero') in (1,2) and 'card' in item:
            card=value(item['card']);cards[value(card['title'])]=value(item['copies'])
    result['decks'][slug]={'sourceSha256':hashlib.sha256(p.read_bytes()).hexdigest(),'cards':[{'title':t,'copies':n} for t,n in sorted(cards.items())]}
dest=root/'docs/game-design/_validation/deck-counts-reference.json'
dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Froze 27 title/count facts; full scraped content was not copied.')
