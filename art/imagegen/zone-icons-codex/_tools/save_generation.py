"""Copy an authorized ImageGen original unchanged and append its exact prompt record."""
import hashlib
import json
import shutil
import sys
from datetime import datetime,timezone
from pathlib import Path
from PIL import Image

PACKAGE=Path(__file__).resolve().parents[1]
CACHE=Path('C:/Users/ren/.codex/generated_images').resolve()

def main():
    key,source=sys.argv[1:]
    prompts=json.loads((PACKAGE/'prompts/zone-icons-prompts.json').read_text(encoding='utf-8'))
    assert key in prompts
    source=Path(source).resolve()
    assert source.is_relative_to(CACHE) and source.suffix.lower()=='.png'
    target=PACKAGE/'concepts'/f'{key}.png'
    assert not target.exists(), 'Never overwrite an original generation'
    records=json.loads((PACKAGE/'generation-records.json').read_text(encoding='utf-8'))
    assert not any(r['id']==key for r in records)
    source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
    shutil.copyfile(source,target)
    assert hashlib.sha256(target.read_bytes()).hexdigest()==source_hash
    prompt=prompts[key]
    records.append({'id':key,'card_id':'IC-37','tool':'image_gen.imagegen','mode':'generate','prompt_key':key,'prompt':prompt,'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest(),'references':[],'original_path':source.as_posix(),'saved_path':target.relative_to(PACKAGE).as_posix(),'date':datetime.now(timezone.utc).isoformat(),'sha256':source_hash,'dimensions':list(Image.open(target).size),'unretouched':True,'local_service_cache_outside_package':True,'imagegen_service_cache_authorized':True})
    order=list(prompts)
    records.sort(key=lambda r:order.index(r['prompt_key']))
    (PACKAGE/'generation-records.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'saved':key,'dimensions':list(Image.open(target).size),'sha256':source_hash}))

if __name__=='__main__':
    main()
