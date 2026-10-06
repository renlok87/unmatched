import csv, hashlib, json, shutil
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
ROOT = PKG.parents[2]
V3 = ROOT / 'art/imagegen/hud-icons-v3'
INPUTS = [
 'docs/game-design/visual/06-tasks/prompts/IC-36.codex.md',
 'docs/game-design/visual/06-tasks/icons.csv',
 'docs/game-design/visual/02-visual-design.md',
 'docs/game-design/visual/07-prompt-templates.md',
 'art/imagegen/hud-icons-de012-codex/README.md',
]

def sha(path):
 return hashlib.sha256(path.read_bytes()).hexdigest()

def dump(name, obj):
 (PKG/name).write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n',encoding='utf-8')

def main():
 for d in ['prompts','concepts','comparison','vector','_tools']:
  (PKG/d).mkdir(parents=True,exist_ok=True)
 files = sorted(set([ROOT/p for p in INPUTS]+[p for p in V3.rglob('*') if p.is_file()]))
 before=PKG/'source-hashes-before.json'
 if before.exists():
  raise RuntimeError('Baseline already exists; do not overwrite it')
 dump('source-hashes-before.json',{'algorithm':'sha256','inputs_and_v3':{p.relative_to(ROOT).as_posix():sha(p) for p in files}})
 shutil.copyfile(V3/'_tools/draw_icons.py',PKG/'_tools/draw_icons_v3_snapshot.py')
 rows=[r for r in csv.DictReader((ROOT/INPUTS[1]).open(encoding='utf-8-sig',newline='')) if r['id'] in ['IC-36','IC-46','IC-48','IC-55','IC-59']]
 dump('prompts/task-rows.json',rows)
 task=(ROOT/INPUTS[0]).read_text(encoding='utf-8')
 block=task.split('Image prompt for each:\n')[1].split('\n   Values:')[0].strip()
 template=block[1:block.rfind('"')]
 variants={
 'end-turn':('round action pip (dark disc with a cream ring)','end the turn now',
 'body card.navy #061623, ring card.cream #F9EBDB, glyph card.glyph #FAF8F2, keyline mark.keyline #111317',
 ['a straight right-pointing arrow that stops at a vertical bar','a bold right chevron that stops at a vertical bar']),
 'card-drop':('square state badge (dark body, cream edge)','this card will go to the discard pile',
 'body card.navy #061623, ring card.cream #F9EBDB, glyph card.glyph #FAF8F2, keyline mark.keyline #111317',
 ['a short down arrow landing on a pile of two flat slanted plates','one card outline tilted 12 degrees sliding down behind a short horizontal pile edge']),
 'log':('bare white glyph on a dark button','open the log of game events','glyph #FAF8F2, keyline #111317',
 ['three short horizontal lines, each with a small square bullet on its left','a small rolled scroll with two text lines']),
 'pointer':('mouse cursor, 32 px','this element is clickable','body #FAF8F2, keyline #111317 (2 px at 32 px), ring #F9EBDB',
 ['a flat pointing hand, index finger up and to the left, the fingertip is the hot spot','the standard arrow cursor with a small cream ring around its tip (the selection ring of the board)']),
 }
 for name,(family,meaning,colours,glyphs) in variants.items():
  prompts={}
  for v,glyph in zip('AB',glyphs):
   p=template.replace('<family>',family).replace('<meaning>',meaning).replace('<glyph>',glyph).replace('<colours>',colours)
   assert 'Unmatched' not in p and 'Digital Edition' not in p
   prompts[v]=p
  dump('prompts/'+name+'-prompts.json',prompts)
 dump('generation-records.json',[])
 print('Baseline saved:',len(files),'files; prompts prepared')

if __name__=='__main__': main()
