"""Record the completed native visual review and verify deterministic rebuild."""
import sys,subprocess
sys.dont_write_bytecode=True
from build_kit import *

def main():
    pages=json.loads((PRE/'review/pages.json').read_text('utf-8'))
    assets=json.loads((KIT/'assets.json').read_text('utf-8'))
    reviewed=[]
    for page in pages:
        reviewed.append({'file':page['file'],'sha256':sha(ROOT/page['file']),'scale':page['scale'],
                         'viewed_native':True,'backdrops':[NAVY,'#E2DACD'],'placements':page['placements']})
    comparisons=['own-turn.png','combat.png','compare-own-turn.png','compare-combat.png','compare-b-vs-b2-own-turn.png']
    rim=[]
    for n in ['T_Skin_Panel','T_Skin_Modal','T_Skin_Toast','T_Hud_TurnPlate','T_Hud_StatusBanner','T_Hud_PileFrame','T_Hud_ActionPlate','T_Skin_Btn_Normal']:
        a=np.array(load(n));t=assets[n]['slice_su'][1]
        band=a[:t,a.shape[1]//2]
        width=int(((band[:,:3].mean(axis=1)>105)&(band[:,3]>127)).sum())
        rim.append({'asset':n,'bright_marble_gold_top_band_su':width,'method':'At x1, count top-margin centre-column texels with mean RGB>105 and alpha>127; bevel and gold included.',
                    'fixed_slice_su':assets[n]['slice_su']})
    write_json(ART/'stage-b2-visual-review.json',{'stage':'B2','method':'Manual inspection with view_image original detail. Native PNGs shown on navy and light marble; independent numerical tests in verification.json.stage_b2.',
        'asset_count':len(assets),'native_exports_reviewed':sum(len(p['placements']) for p in pages),'review_pages':reviewed,
        'assembly_and_comparison_review':[{'file':str((PRE/n).relative_to(ROOT)).replace('\\','/'),'sha256':sha(PRE/n),'viewed_full_size':True} for n in comparisons],
        'stretch_sheets_reviewed':['T_Skin_Panel','T_Skin_Modal'],'rim_measurements':rim,
        'findings':['Visible marble/gold rails measure 7 su on the large requested substrates; button bevel 4 su.',
                    'B203 source normalized from 2172x724 before cropping; both acanthus ends retained.',
                    'Large gold laurels remain readable at 80 and 64 su portrait sizes.',
                    'V3 icon sprites and real scan crops remain separate from ornament PNGs.',
                    'Translucent text bodies reveal scene rather than obsolete screenshot UI; clone operations are in the layer provenance.',
                    'No visible green fringe or slicing gap on the reviewed navy/light sheets.'],
        'weak_points':['Constant longitudinal rails are less painterly than the single-image A concept.',
                       'Fine veins and gold foil become a material tone at x1; centre fills deliberately remain flat.',
                       'ActionPlate makes the action block denser than concept A.',
                       'Fixed teal/light and disabled Primary/dark colour pairs fail 4.5:1; exact mandatory colours retained.',
                       'Unreal import, filtering, DPI and live state transitions not verified.'],
        'background_processes_started':0,'git_commands_run':False})
    paths=[p for folder in ['x1','x2','masters'] for p in (KIT/folder).glob('*.png')]+[KIT/'assets.json',KIT/'catalog.png',ART/'slice-margins.json',KIT/'slice-margins.json']
    before={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in paths}
    result=subprocess.run([sys.executable,'-X','utf8',str(ART/'_tools/build_b2.py')],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    after={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in paths}
    changed=[p for p in before if before[p]!=after[p]]
    write_json(ART/'stage-b2-determinism.json',{'status':'pass' if not changed else 'fail','checked_files':len(before),'changed':changed,'sha256':after})
    assert not changed,changed
    print(json.dumps({'manual_review_pages':len(pages),'native_exports':168,'deterministic_files':len(before),'changed_after_rebuild':changed}))

if __name__=='__main__':main()
