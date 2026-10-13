import json, sys
sys.path.insert(0, 'tools/tripo-pipeline/review')
from ue_live import Ue
root = '/Game/PipelineCandidates/AncientLeshen/H2LD/'
own = json.load(open(sys.argv[1] + '/manifest.json', encoding='utf-8'))['stages']['ue-import']['ue_owned_assets']
own = [a for a in own if a.startswith(root)]
rank = lambda a: (0 if '/Materials/' in a else 1 if '/Meshes/' in a else 2, -len(a))
ue = Ue()
for a in sorted(own, key=rank):
    if not ue.call('asset', 'delete', {'path': a}):
        sys.exit('UE refused to delete ' + a)
    print('deleted', a)
print('left', ue.call('asset', 'find_assets', {'folder_path': root.rstrip('/'), 'name': '', 'recursive': True}))
