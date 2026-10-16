from pathlib import Path
import json
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
for name in ('raw', 'refs', '_tools'):
    (ROOT / name).mkdir(exist_ok=True)

COMMON = '''Use case: ui-mockup. Create ONE premium 16:9 landscape ART LAYER for a 1920x1080 game screen, edge-to-edge, no mockup device. This is the digital board game Unmatched, with fighting-game selection drama and museum-plaque elegance. Reference images: King Arthur and Medusa front images are strict CHARACTER LIKENESS references, the green marble plate is the MATERIAL reference, the in-game HUD is PALETTE/FRAME reference only. Keep Arthur's dark engraved steel/gold armour, red cape, crown, beard, upright sword and dark round miniature pedestal. Keep Medusa's pale face, living snake crown, charcoal draped Greek dress, gold greaves and ornaments, golden bow, quiver and dark round pedestal. Turn Arthur three-quarter toward the RIGHT, Medusa three-quarter toward the LEFT, faces visible, never backs to camera. Photoreal polished collectible game figures; only these heroes, NO sidekicks in niches. Palette navy #14161C to #1B2433, cream #ECE3CF, restrained aged bronze #8C6B3F and gold #C9A45C. Player left team GOLD #E8C06A; player right team muted SILVER-BLUE #5A7F9F, never red/blue teams. Thin bronze/cream frames with tiny Greek-meander corners; green-grey polished marble plates. All UI panels and tiles are EMPTY surfaces reserved for later compositing. ABSOLUTELY NO TEXT, NO LETTERS, NO NUMBERS, NO TYPOGRAPHY, NO QUESTION MARKS, NO VS GLYPHS, NO LOGOS, NO WATERMARKS, NO PSEUDO-WRITING. A medallion, if present, has a completely smooth blank bronze centre. Do not draw any board/map; real map photographs will be composited later. No neon, sci-fi, blood, lightning or giant laurel wreaths. Do not draw HUD from input reference or extra menus.'''

VARIANTS = {
    'A': '''Variant A STUDIO: almost black navy gallery, dramatic soft cones of light from above, warm gold on left, muted silver-blue on right, near-black vignette, polished dark marble floor with subtle pedestal reflections. Two tall dark display niches framed in thin aged bronze. Museum materials, MK11-like staging without any MK motifs.''',
    'B': '''Variant B TABLE: lighter green-grey marble and bronze display plaques, soft museum lighting, navy translucent panel inserts. Around plaques leave a very dark smooth low-detail navy backdrop: the REAL blurred Marmoreal game scene will replace this backdrop later. More tactile marble, warmer cream edges, gentler shadows than studio, same exact layout. Do not invent a board.''',
}

SCREENS = {
    'R1-hero-hover': '''Hero HOVER screen. Exact 1920x1080 coordinate layout: a blank top header from y=0 to 96. LEFT niche rectangle x=48..608 y=120..920: Arthur FULL BODY with crown near y=185, boots at y=735 and pedestal at y=790; figure fills the niche, no crop. Blank nameplate at y=820..920. RIGHT niche x=1312..1872 y=120..920: EMPTY pedestal at y=765, no figure, empty space above it; blank nameplate y=820..920. Centre x=640..1280 is clear: a blank framed hero information plaque x=640..1280 y=500..790. Leave centre above plaque atmospheric and empty, NO medallion in hover state. Exactly THREE blank compact roster tiles x=752..880, x=896..1024, x=1040..1168 at y=800..968, first tile has thin gold hover frame. No portraits or marks needed in blank roster tiles. Blank full-width bottom control bar y=980..1060. Emphasize the full-body Arthur and the empty opponent pedestal.''',
    'R2-hero-locked': '''Both heroes LOCKED screen, same grid as hero hover: blank top header y=0..96, LEFT niche x=48..608 y=120..920 with FULL BODY Arthur facing right, RIGHT niche x=1312..1872 y=120..920 with FULL BODY Medusa facing left. Heads at y=180, boots at y=730, dark round pedestals near y=790. Blank lower nameplates y=820..920. Bronze round medallion exactly centred at x=960 y=420, diameter 140, completely BLANK smooth centre, subtle bronze rays only. Blank framed hero information plaque x=640..1280 y=510..790 below medallion. Exactly THREE blank roster tiles x=752..880, x=896..1024, x=1040..1168 y=800..968, first outlined gold, second outlined silver-blue; no badges/glyphs, we add them later. Blank bottom control bar y=980..1060. A confident lock-in pose, no lunging, no flying effects.''',
    'R3-board-select': '''STAGE/BOARD selection screen. Blank top header y=0..96. Niches SHRINK to x=48..448 y=160..760 and x=1472..1872 y=160..760, 400x600 each: FULL BODY Arthur left, Medusa right, heads near y=205, feet and pedestal near y=660; blank nameplates y=680..760. Large EMPTY landscape preview frame exactly x=480..1440 y=130..670, 960x540; fill it flat near-black navy, absolutely NO imagined board, landscape or diagram within it. Thin cream/bronze rim and small meander corners. Empty board name plaque x=480..1440 y=685..750. Exactly THREE EMPTY thumbnail frames 200x120 at x=644..844, x=860..1060, x=1076..1276, y=788..908, first outlined gold. Blank control strip y=980..1060. Centre preview is the focal point, hero niches are narrower at edges. NO medallion on this screen.''',
    'R4-vs': '''VS MATCH LOADING splash. No header, no roster, no menu buttons or information cards. Two monumental FULL BODY fighters in tall 720x960 display areas: Arthur left x=100..820 y=40..1000 facing inward, Medusa right x=1100..1820 y=40..1000 facing inward; crown/snake crown near y=65, boots at y=865, pedestals near y=920, all fully visible. Their inner panel edges form dramatic diagonal cuts towards the central axis, opening a narrow centre gap. Large round aged bronze medallion at x=960 y=420 diameter 220, blank smooth centre; no lettering. Reserve low dark blank nameplates at x=90..780 y=850..965 and x=1140..1830 y=850..965, do not cover faces. Dark blank board-name/loading strip x=510..1410 y=975..1070. Keep the centre gap clear so we can composite an actual board photo behind the medallion. Dramatic but elegant, no sparks/lightning.''',
}

prompts = {f'{screen}-{variant}': COMMON + '\n\n' + VARIANTS[variant] + '\n\n' + layout
           for screen, layout in SCREENS.items() for variant in VARIANTS}
(ROOT / '_tools/prompts.json').write_text(json.dumps(prompts, ensure_ascii=False, indent=2), encoding='utf-8')

# The supplied AN-23 images are three-column diagnostic sheets, not single frames.
# Extract only the colour panel; never composite their captions, grey, or CVD panels.
for board, number in [('marmoreal', '01'), ('sarpedon', '03')]:
    source = REPO / f'docs/game-design/evidence/VISUAL/AN-23/sheet-{number}-{board}-K1-plain.png'
    sheet = Image.open(source)
    # Colour viewport in 2880x610 source: x=12..956, y=66..597 (16:9).
    scale = sheet.width / 2880
    crop = tuple(round(v * scale) for v in (12, 66, 956, 597))
    sheet.crop(crop).convert('RGB').save(ROOT / '_tools' / f'{board}-K1-colour.png')
print(json.dumps({'prompts': list(prompts), 'boards': [(b, Image.open(ROOT / '_tools' / f'{b}-K1-colour.png').size) for b in ('marmoreal','sarpedon')]}, ensure_ascii=False))
