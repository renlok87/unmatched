"""Keep the task's exact concept prompt; each variant has its own key."""
import hashlib
import json
import re
from pathlib import Path
from zone_icons import PACKAGE,KEYS

ROOT=PACKAGE.parents[2]
task=(ROOT/'docs/game-design/visual/06-tasks/prompts/IC-37.codex.md').read_text(encoding='utf-8')
base=re.search(r'"(Original small HUD glyph concept\..*?)"\s+Values:',task,re.S).group(1)
glyphs={
    'gray':['a solid square block','a square block with one notched corner'],
    'green':['a leaf with a midrib cut, tilted 45 degrees','a sprout with two leaves'],
    'blue':['two stacked wave strokes','one wave stroke over a flat line'],
    'violet':['a crescent moon opening to the right','a crescent with a small dot inside'],
    'purple':['an arch (gate) with a square-cut opening','a two-step arch'],
    'red':['an upright flame with one inner tongue cut','a flame with two tongues'],
    'brown':['a hill: trapezoid with a wide base and a narrow flat top','two rounded hills'],
    'yellow':['three dots in a triangle','three dots in a row'],
}
prompts={}
for key in KEYS:
    for v,glyph in zip('AB',glyphs[key]):
        text=base.replace('<key>',key).replace('<glyph>',glyph)
        text+='\nForbidden shapes for the whole glyph silhouette: star, shield, diamond, X, exclamation mark, heart, hexagon, plus sign, triangle, plain circle or ring. The coloured disc is the common badge carrier. Separate dots are allowed for the three-dot glyph.'
        assert not re.search(r'Unmatched|Digital Edition',text,re.I)
        prompts[f'zone-{key}-{v}']=text
(PACKAGE/'prompts/zone-icons-prompts.json').write_text(json.dumps(prompts,ensure_ascii=False,indent=2),encoding='utf-8')
print('16 exact prompt keys saved')
