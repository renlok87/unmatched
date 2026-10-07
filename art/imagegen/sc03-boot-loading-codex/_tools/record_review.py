#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Record the operator's completed visual inspection, then refresh hashes.

Run only AFTER opening every final PNG through review_contact.py/native views.
This command itself does not perform or claim automatic visual inspection.
"""
import json
import sys
from pathlib import Path
sys.dont_write_bytecode=True
import sc03_boot_loading as b
package=Path(__file__).resolve().parents[1]
derived=b.ROOT/('scraped-data/derived/'+package.name)
card={'sc03-boot-loading-codex':'SC-03','sc04-boot-error-codex':'SC-04','sc05-boot-resume-codex':'SC-05'}[package.name]
files=[{'path':b.rel(p),'sha256':b.sha(p),'opened':True}
       for folder in (package,derived) for p in sorted(folder.rglob('*.png'))]
review={'status':'предложено','reviewer':'Codex','files':files,
        'method':'Every final PNG opened in Pillow and displayed in contact pages in the tool transcript; native-size selected finals and overlay also viewed with view_image.',
        'findings':['Layout within canvas; text, caption capsule and build label present.',
                    'Color and grayscale states remain distinguishable by stage text/fill or reason/spinner and button form.',
                    'Historical source frame and its six figures retained; caption identifies placeholder; not a claim of current environment acceptance.',
                    'Thin HB-08 boundaries can be weak against the scene; numerical failures kept in verification.json.']}
b.dump(package/'visual-review.json',review,package,derived)
readme=package/'README.md'
text=readme.read_text(encoding='utf-8')
text+='\nВизуально открыты все '+str(len(files))+' финальных PNG: цвет/серый, отдельные кадры, сравнения и оверлеи. Обзор — контактными страницами в памяти, выбранные кадры дополнительно в родном размере. Хеш каждого просмотренного файла — в visual-review.json.\n'
b.allow(readme,package,derived).write_text(text,encoding='utf-8')
b.refresh_manifest(package,derived,card)
print(json.dumps({'card':card,'reviewed_pngs':len(files)}))
