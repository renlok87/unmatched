from pathlib import Path
import hashlib,json,sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[4]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rel(p):
 p=Path(p).resolve()
 return p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else p.as_posix()
def inventory(path):return {rel(p):sha(p) for p in sorted(Path(path).rglob('*')) if p.is_file()}
def digest(files):return hashlib.sha256(''.join(k+'\t'+v+'\n' for k,v in sorted(files.items())).encode('utf-8')).hexdigest()
def prepare(card,package):
 package=ROOT/package;derived=ROOT/'scraped-data/derived'/package.name
 paths=['AGENTS.md','docs/game-design/visual/02-visual-design.md','docs/game-design/visual/04-hud-spec.md','docs/game-design/visual/07-prompt-templates.md','docs/game-design/visual/06-tasks/screens.csv','docs/game-design/visual/06-tasks/prompts/SC-19-series.codex.md',f'docs/game-design/visual/06-tasks/prompts/{card}.codex.md','docs/unreal/contracts/hud/st-screens.csv','docs/unreal/contracts/hud/hud-style-tokens.json','docs/game-design/decisions/2026-10-04-real-boards-only.md','backend/prisma/seed.ts','docs/game-design/evidence/DE-FOOTAGE/2026-10-05/I/README.md','docs/game-design/evidence/ENV-MAPS/p7-concept-paste-2026-10-01/marmoreal-concept-flag/bench-K1-1920x1080.png','scraped-data/images/heroes/avatars/dgwIAej9v-Omrn0sSVs5i.webp','scraped-data/images/heroes/avatars/bI206lUtJUQru-FOD8A74.webp','scraped-data/derived/ue-media-v1/avatars/medusa.png','scraped-data/derived/ue-media-v1/avatars/king-arthur.png','.agents/skills/frontend-design/SKILL.md']
 for name in ('sc01-screen-base-codex','sc03-boot-loading-codex','sc04-boot-error-codex'):
  base=ROOT/'art/imagegen'/name;paths +=[rel(base/'README.md')]
  paths +=[rel(p) for p in (base/'_tools').glob('*.py')]
 paths +=['art/imagegen/sc01-screen-base-codex/manifest-sha256.json','art/imagegen/sc14-room-hero-codex/_tools/sc14_room_hero.py']
 skins=ROOT/'art/imagegen/hud-skins-v1-codex'
 paths +=[rel(skins/p) for p in ('README.md','runtime-style.json','slice-margins.json')];paths +=list(inventory(skins/'vector'))
 portraits=ROOT/'art/imagegen/portrait-crop-v1-codex'
 paths +=[rel(portraits/p) for p in ('README.md','portrait-crops.json')]
 paths +=[rel(p) for p in (portraits/'vector').glob('portrait-*-160*')]
 paths +=[rel(p) for p in (derived/'inputs').glob('*.json')]
 paths +=[f'C:/Program Files/Epic Games/UE_5.8/Engine/Content/Slate/Fonts/{f}.ttf' for f in ('Roboto-BoldCondensed','Roboto-Regular')]
 copies=[('art/imagegen/sc01-screen-base-codex/_tools/screen_mockup_base.py','screen_mockup_base.py'),('art/imagegen/hud-icons-v3/_tools/draw_icons.py','draw_icons_v3_snapshot.py')]
 if card=='SC-20':
  base=ROOT/'art/imagegen/sc19-loading-codex';paths +=[rel(base/p) for p in ('README.md','manifest-sha256.json')];paths +=[rel(p) for p in (base/'_tools').glob('*.py')]
  paths +=['tools/s10/drop-graphql-reply-proxy.cjs']
  copies += [('art/imagegen/sc19-loading-codex/_tools/sc19_loading.py','sc19_loading.py'),('art/imagegen/sc19-loading-codex/_tools/package_inputs.py','package_inputs.py'),('art/imagegen/sc19-loading-codex/_tools/finalize_review.py','finalize_review.py')]
 icons=inventory(ROOT/'art/imagegen/hud-icons-v3');paths +=['art/imagegen/hud-icons-v3/_tools/draw_icons.py']
 for name in ('loader-spinner','resource-connection-lost') if card=='SC-20' else ('loader-spinner',):
  paths +=[rel(p) for p in (ROOT/'art/imagegen/hud-icons-v3/sizes').glob(name+'-*.png')]
 before={'schema':'CX-31.sources.v1','inputs':{p:sha(ROOT/p) for p in sorted(set(paths))},'hud_icons_v3':{'count':len(icons),'tree_digest':digest(icons),'algorithm':'SHA256(sorted UTF-8 repo path TAB hash LF)','files':icons}}
 (package/'source-hashes-before.json').write_text(json.dumps(before,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 provenance=[]
 for source,target in copies:
  out=package/'_tools'/target;out.write_bytes((ROOT/source).read_bytes());provenance.append({'source':source,'copy':rel(out),'sha256_source':sha(ROOT/source),'sha256_copy':sha(out),'unchanged':sha(ROOT/source)==sha(out)})
 (package/'copy-provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 for p in ['docs/game-design/visual/06-tasks/prompts/SC-19-series.codex.md',f'docs/game-design/visual/06-tasks/prompts/{card}.codex.md']:
  (package/'prompts'/Path(p).name).write_bytes((ROOT/p).read_bytes())
 (package/'generation-records.json').write_text('[]\n',encoding='utf-8')
 print(card,'sources',len(before['inputs']),'icons',len(icons),'copies',len(copies))
if __name__=='__main__':prepare('SC-19','art/imagegen/sc19-loading-codex')
