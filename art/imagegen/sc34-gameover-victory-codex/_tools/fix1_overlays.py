"""CX-34 fix1: keyed, asset-free overlays without changing the run-1 library."""
import itertools
from PIL import Image, ImageDraw, ImageFont
from screen_mockup_base import luma709


def intersection(a, b):
    return max(0, min(a[0]+a[2], b[0]+b[2])-max(a[0], b[0])) * max(0, min(a[1]+a[3], b[1]+b[3])-max(a[1], b[1]))


def render_overlay(widgets, vp, theme, path, guard):
    """Keep the schema at its native pixel scale; append a separate legend gutter."""
    elements = [(n, r) for n, r in widgets.items()
                if not any(s in n for s in ['.Label', '.RoleHP', '.Status'])]
    font_px = max(14, round(14*vp.factor))
    font = ImageFont.truetype(theme.regular_font, font_px)
    navy, ink = theme.color('card.navy'), theme.color('text.primary')
    edge = tuple(round(a*theme.alpha('panel.edge')+b*(1-theme.alpha('panel.edge')))
                 for a, b in zip(theme.color('panel.edge'), navy))
    texts = [f'{i:02} {n}: {r["rect_su"][0]:.2f}, {r["rect_su"][1]:.2f}, '
             f'{r["rect_su"][2]:.2f}, {r["rect_su"][3]:.2f} su'
             for i, (n, r) in enumerate(elements, 1)]
    line_h = font_px+12
    legend_x = vp.width+24
    width = legend_x+max(round(font.getlength(t)) for t in texts)+24
    height = max(vp.height, 48+line_h*len(elements))
    image = Image.new('RGBA', (width, height), navy+(255,))
    draw = ImageDraw.Draw(image)
    draw.line([(vp.width+8, 16), (vp.width+8, height-16)], fill=edge, width=1)
    rects = []
    for name, rec in elements:
        x, y, w, h = rec['rect_su']
        rect = [round(x*vp.factor), round(y*vp.factor), round(w*vp.factor), round(h*vp.factor)]
        rects.append(rect)
        rx, ry, rw, rh = rect
        draw.rectangle((rx, ry, rx+rw-1, ry+rh-1), outline=edge, width=1)
    labels = []
    for i, text in enumerate(texts):
        xy = (legend_x, 24+i*line_h)
        draw.text(xy, text, font=font, fill=ink, anchor='lt')
        b = draw.textbbox(xy, text, font=font, anchor='lt')
        labels.append([b[0], b[1], b[2]-b[0], b[3]-b[1]])
    tags = []
    for i, ((name, rec), rect) in enumerate(zip(elements, rects), 1):
        rx, ry, rw, rh = rect
        number = f'{i:02}'
        bbox = font.getbbox(number, anchor='lt')
        tw, th = bbox[2]-bbox[0]+8, bbox[3]-bbox[1]+8
        def free(box):
            return (box[0] >= 0 and box[1] >= 0 and box[0]+tw <= vp.width
                    and box[1]+th <= height and all(not intersection(box, t['box_px']) for t in tags)
                    and all(not intersection(box, b) for b in labels))
        box = [rx+2, ry+2, tw, th]
        inside = tw+4 <= rw and th+4 <= rh and free(box)
        if not inside:
            # Stay near the top-left anchor; try immediately above or to its left.
            candidates = []
            for distance in range(2, 193, 4):
                candidates.extend([[rx, ry-th-distance, tw, th],
                                   [rx-tw-distance, ry, tw, th],
                                   [rx+distance, ry-th-2, tw, th],
                                   [rx-tw-2, ry+distance, tw, th]])
            box = next((b for b in candidates if free(b)), None)
            if box is None:
                raise ValueError('Cannot place non-overlapping tag: '+name)
            end = [min(max(rx, box[0]), box[0]+tw-1), min(max(ry, box[1]), box[1]+th-1)]
            draw.line([(rx, ry), tuple(end)], fill=edge, width=1)
        tags.append({'number': number, 'widget': name, 'box_px': box,
                     'placement': 'inside top-left' if inside else 'outside with 1px leader',
                     'anchor_px': [rx, ry]})
    # Tags are painted after leaders so a leader cannot obscure another number.
    for t in tags:
        x, y, w, h = t['box_px']
        draw.rectangle((x, y, x+w-1, y+h-1), fill=navy, outline=edge, width=1)
        draw.text((x+4, y+4), t['number'], font=font, fill=ink, anchor='lt')
    label_pairs = sum(intersection(a, b)>0 for a, b in itertools.combinations(labels, 2))
    tag_pairs = sum(intersection(a['box_px'], b['box_px'])>0 for a, b in itertools.combinations(tags, 2))
    tag_legend = sum(intersection(t['box_px'], b)>0 for t in tags for b in labels)
    assert label_pairs == tag_pairs == tag_legend == 0
    image.save(guard(path))
    gray_path = path.with_name(path.stem+'-gray.png')
    luma709(image).convert('RGBA').save(guard(gray_path))
    return {'path': path.as_posix(), 'canvas_px': list(image.size),
            'schema_canvas_px': [vp.width, vp.height], 'schema_scale': 1,
            'contains_asset_pixels': False, 'label_overlap_px2': 0,
            'label_overlap_count': label_pairs, 'label_boxes_px': labels,
            'tag_overlap_count': tag_pairs+tag_legend, 'tag_tag_overlap_count': tag_pairs,
            'tag_legend_overlap_count': tag_legend, 'tag_overlap_px2': 0,
            'tag_count': len(tags), 'rectangle_count': len(elements), 'tags': tags,
            'tag_font': 'Roboto Regular', 'tag_font_px': font_px,
            'tag_text': 'text.primary', 'tag_box': 'card.navy',
            'tag_keyline': {'role': 'panel.edge', 'width_px': 1},
            'leader_width_px': 1,
            'labels_include': ['number', 'BindWidget', 'x_su', 'y_su', 'w_su', 'h_su']}
