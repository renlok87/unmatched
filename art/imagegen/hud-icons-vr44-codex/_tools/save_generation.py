import argparse,datetime,hashlib,json,shutil
from pathlib import Path
PKG=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('glyph');p.add_argument('variant');p.add_argument('original');a=p.parse_args()
 prompt=json.loads((PKG/'prompts'/f'{a.glyph}-prompts.json').read_text(encoding='utf-8'))[a.variant]
 src=Path(a.original); dest=PKG/'concepts'/f'{a.glyph}-{a.variant}.png'
 if dest.exists(): raise RuntimeError('Refusing to replace an existing generation')
 shutil.copyfile(src,dest)
 h=hashlib.sha256(src.read_bytes()).hexdigest()
 assert h==hashlib.sha256(dest.read_bytes()).hexdigest()
 path=PKG/'generation-records.json'; records=json.loads(path.read_text(encoding='utf-8'))
 records.append({'id':f'IC-36/{a.glyph}/{a.variant}','card_id':'IC-36','tool':'image_gen.imagegen','mode':'generate',
 'prompt_file':f'prompts/{a.glyph}-prompts.json','prompt_key':a.variant,'exact_prompt':prompt,
 'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest(),'references':[],
 'original_path':str(src),'saved_path':dest.relative_to(PKG).as_posix(),'sha256':h,
 'date':datetime.datetime.now(datetime.timezone.utc).isoformat(),'unretouched':True})
 path.write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('Saved unchanged:',dest.name)
if __name__=='__main__':main()
