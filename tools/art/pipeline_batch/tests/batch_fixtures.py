"""Общие фикстуры тестов pipeline_batch: минимальный GLB, синтетический фрагмент скилла."""
from __future__ import annotations

import json
import struct

import numpy as np


def make_glb(parts: dict, stride: int = 12, dbl_min_y: bool = True, tail: bytes = b"") -> bytes:
    """GLB c узлом-мешем на каждую часть {name: [[x,y,z], …]}; accessor.min[1] = DBL_MIN, как пишет Tripo (F10)."""
    nodes, meshes, accessors, views, blob = [], [], [], [], b""
    for i, (name, verts) in enumerate(parts.items()):
        v = np.asarray(verts, np.float32)
        if stride > 12:
            raw = np.zeros((len(v), stride), np.uint8)
            raw[:, :12] = v.view(np.uint8).reshape(len(v), 12)
            data = raw.tobytes()
        else:
            data = v.tobytes()
        views.append({"buffer": 0, "byteOffset": len(blob), "byteLength": len(data), **({"byteStride": stride}
                                                                                       if stride > 12 else {})})
        blob += data
        mn = v.min(0).tolist()
        if dbl_min_y:
            mn[1] = 2.2e-308
        accessors.append({"bufferView": i, "componentType": 5126, "count": len(v), "type": "VEC3", "min": mn,
                          "max": v.max(0).tolist()})
        meshes.append({"name": f"meshes[{i}]", "primitives": [{"attributes": {"POSITION": i}}]})
        nodes.append({"name": name, "mesh": i})
    nodes.append({"name": "root", "children": list(range(len(parts)))})
    doc = {"asset": {"version": "2.0"}, "nodes": nodes, "meshes": meshes, "accessors": accessors, "bufferViews": views,
           "buffers": [{"byteLength": len(blob)}]}
    js = json.dumps(doc).encode()
    js += b" " * (-len(js) % 4)
    blob += b"\0" * (-len(blob) % 4)
    body = struct.pack("<I4s", len(js), b"JSON") + js + struct.pack("<I4s", len(blob), b"BIN\0") + blob
    return struct.pack("<4sII", b"glTF", 2, 12 + len(body)) + body + tail


SKILL_MD = """# concept-sheet

### 5.4 Блок B-CONCEPT-PACKAGE

```text
PACKAGE {{ASSET_ID}} at art/imagegen/concept-{{CONTENT_KEY}}-codex
```

### 6.1 Файл задания `<ASSET_ID>-concept.codex.md`

````markdown
# {{ASSET_ID}} 1a ({{DATE}}), card {{ASSET_CARD_SHA256}}, generations {{GENERATIONS_ALLOWED}}
{{B_CONCEPT_PACKAGE}}
```text
{{CORE_1A}}
```
````

### 6.2 Ядро CORE-1A (отправлять в image_gen дословно; менять только плейсхолдеры)

```text
{{DESCRIPTION_EN}} {{ANCHORS_EN}} {{PALETTE_EN}} {{POSE_EN}} {{WEAPON_SIDE_EN}} {{PEDESTAL_EN}} {{ASPECT_EN}}
{{ROLE_ARG}} {{POSE_CHECK_EN}} {{ONE_BASE_EN}}{{AND_PEDESTAL_EN}} {{EDGE_ON_CHECK_EN}} {{QUALITY_REFERENCE}}
{{QUALITY_REFERENCE_SHA256}} {{PALETTE_SHA256}} {{ASSET_DIR}}
```

### 8.1 Файл задания `<ASSET_ID>-concept-views.codex.md`

```text
1C {{ASSET_ID}} views {{VIEWS}} side {{SIDE_VIEW}} orthos {{ORTHO_DIR}}
{{B_CONCEPT_PACKAGE}}
FRONT: {{CORE_1C_FRONT}}
SIDE: {{CORE_1C_SIDE}}
BACK: {{CORE_1C_BACK}}
```

### 8.2 Ядро CORE-1C (одно для трёх видов; менять только плейсхолдеры)

```text
{{VIEW_NAME_EN}} | {{VIEW_BLOCK_EN}} | {{FRAMING_BASE_EN}} | top y{{TOP_Y}}%

{{IMAGE3_EN}}
{{WEAPON_SIDE_EN}} {{DESCRIPTION_EN}} {{ANCHORS_EN}} {{PALETTE_EN}} {{ASPECT_EN}} {{KEEP_EN}} {{WHOLE_EN}}
{{ROLE_ARG}} {{FRAME_CHECK_EN}} {{CONTENT_KEY}} {{ASSET_DIR}}
```

## 11. Рубрика

RUBRIC 1C TEXT

## 12. Дальше
"""
