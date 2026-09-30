import sys, json
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0, 'C:/tmp/wt-envmaps/tools/art/map_surface')
import build_map_textures as bmt, k1_mock
Image.MAX_IMAGE_PIXELS = None
DER = Path('C:/Users/ren/WebstormProjects/unmached/unmached/scraped-data/derived/maps')
EV = Path('C:/tmp/wt-envmaps/docs/game-design/evidence/ENV-MAPS/2026-09-30-research')
OUT = Path('C:/tmp/envmaps-research/concept-base')
for key, name in (('marmoreal', 'Marmoreal'), ('sarpedon', 'Sarpedon')):
    vec = json.load(open(f'C:/tmp/wt-envmaps/tools/art/map_surface/{key}.vector-layer.json', encoding='utf-8'))
    topo = json.load(open(EV / f'{key}.topology.json', encoding='utf-8'))
    bc = np.asarray(Image.open(DER / key / f'T_{name}_Map_BC_4K.png').convert('RGB'))
    mask = np.asarray(Image.open(DER / key / f'T_{name}_Map_GameMask_4K.png'))
    layout = bmt.k1_layout(vec, topo)
    layout['tray_rim_uu'] = 170.0
    mx, my = layout['map_half_uu']
    d0 = k1_mock.s08_fit_distance(mx, my)
    maps = {'mips': k1_mock.build_mips(k1_mock.srgb_to_lin(bc.astype(np.float32) / 255.0)),
            'mask_mips': k1_mock.build_mips(mask.astype(np.float32) / 255.0)}
    for tag, mul in (('k1', 1.0), ('wide', 1.45)):
        cam = k1_mock.Camera(d0 * mul, 1920, 1080)
        fr = k1_mock.render(cam, maps, layout, 'c', ss=2)
        Image.fromarray(fr, 'RGB').save(OUT / f'{key}-{tag}-base.png')
        print(key, tag, round(d0 * mul, 1), flush=True)
