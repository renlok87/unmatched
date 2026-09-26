import svgwrite
from svgwrite import cm, mm
from svgwrite.shapes import Circle, Line, Rect
from svgwrite.text import Text
import math

# Canvas dimensions
WIDTH = 800
HEIGHT = 1000
MARGIN = 60

# Color palette - constrained and intentional
BG_COLOR = "#f7f5f0"  # Warm off-white, like aged paper
PRIMARY_COLOR = "#1a1a18"  # Nearly black
ACCENT_1 = "#c8b0a0"  # Warm taupe
ACCENT_2 = "#8a7a6a"  # Muted brown
ACCENT_3 = "#3a3a38"  # Deep gray
HIGHLIGHT = "#d4a574"  # Muted gold

dwg = svgwrite.Drawing('ordinal_precision.svg', size=(WIDTH, HEIGHT))
dwg.add(dwg.rect(insert=(0, 0), size=(WIDTH, HEIGHT), fill=BG_COLOR))

# ===== TOP SECTION: Ordinal Grid =====
# A systematic grid showing singular states
grid_start_y = MARGIN
grid_cell_size = 18
grid_cols = 32
grid_rows = 12

for row in range(grid_rows):
    for col in range(grid_cols):
        x = MARGIN + col * grid_cell_size
        y = grid_start_y + row * grid_cell_size

        # Each cell is unique - variations based on ordinal position
        ordinal_sum = row + col
        is_singular = (ordinal_sum % 7 == 0)

        if is_singular:
            # Singular states - filled circles with accent
            radius = grid_cell_size * 0.35
            color = HIGHLIGHT if row < 4 else (ACCENT_1 if row < 8 else ACCENT_2)
            dwg.add(Circle(center=(x + grid_cell_size/2, y + grid_cell_size/2),
                          r=radius, fill=color))
        else:
            # Regular states - outline circles or dots
            if ordinal_sum % 3 == 0:
                radius = grid_cell_size * 0.15
                dwg.add(Circle(center=(x + grid_cell_size/2, y + grid_cell_size/2),
                              r=radius, fill=PRIMARY_COLOR))
            else:
                radius = grid_cell_size * 0.3
                stroke_width = 0.5 if ordinal_sum % 2 == 0 else 1
                dwg.add(Circle(center=(x + grid_cell_size/2, y + grid_cell_size/2),
                              r=radius, fill='none',
                              stroke=ACCENT_3, stroke_width=stroke_width))

# ===== SECTION DIVIDER =====
divider_y = grid_start_y + grid_rows * grid_cell_size + 40
dwg.add(Line(start=(MARGIN, divider_y), end=(WIDTH - MARGIN, divider_y),
             stroke=ACCENT_3, stroke_width=0.5))

# ===== CENTRAL SECTION: Concentric Ordinals =====
center_x = WIDTH / 2
center_y = divider_y + 180

# Concentric circles representing ordinal layers
for i in range(12):
    radius = 20 + i * 14
    is_cardinal = i % 3 == 0

    if is_cardinal:
        dwg.add(Circle(center=(center_x, center_y), r=radius,
                      fill='none', stroke=PRIMARY_COLOR, stroke_width=2))
    else:
        # Dashed circles for ordinal positions
        dwg.add(Circle(center=(center_x, center_y), r=radius,
                      fill='none', stroke=ACCENT_2, stroke_width=0.5,
                      stroke_dasharray="2,4"))

# Central singular point
dwg.add(Circle(center=(center_x, center_y), r=6, fill=HIGHLIGHT))
dwg.add(Circle(center=(center_x, center_y), r=12,
              fill='none', stroke=PRIMARY_COLOR, stroke_width=1))

# ===== LEFT ANNOTATION =====
label_x = MARGIN + 20
label_y = center_y - 40
dwg.add(Text("ORDINAL", insert=(label_x, label_y),
             fill=ACCENT_2, font_size=10, font_family='sans-serif',
             font_weight='normal', letter_spacing=2))
dwg.add(Text("STATE", insert=(label_x, label_y + 14),
             fill=ACCENT_2, font_size=10, font_family='sans-serif',
             font_weight='normal', letter_spacing=2))

# ===== RIGHT ANNOTATION =====
label_x = WIDTH - MARGIN - 80
label_y = center_y - 40
dwg.add(Text("SINGULAR", insert=(label_x, label_y),
             fill=ACCENT_2, font_size=10, font_family='sans-serif',
             font_weight='normal', letter_spacing=2))
dwg.add(Text("VALUE", insert=(label_x, label_y + 14),
             fill=ACCENT_2, font_size=10, font_family='sans-serif',
             font_weight='normal', letter_spacing=2))

# ===== SECTION DIVIDER 2 =====
divider_y2 = center_y + 200
dwg.add(Line(start=(MARGIN, divider_y2), end=(WIDTH - MARGIN, divider_y2),
             stroke=ACCENT_3, stroke_width=0.5))

# ===== BOTTOM SECTION: Density Pattern =====
pattern_start_y = divider_y2 + 50
pattern_width = WIDTH - 2 * MARGIN
pattern_height = 280

# Create a density gradient through mark accumulation
cols = 60
rows = 24
cell_w = pattern_width / cols
cell_h = pattern_height / rows

for row in range(rows):
    for col in range(cols):
        x = MARGIN + col * cell_w
        y = pattern_start_y + row * cell_h

        # Density based on position - creates subtle gradient
        density = (col / cols + row / rows) / 2

        if density > 0.85:
            # Dense regions - filled
            dwg.add(Rect(insert=(x + 1, y + 1),
                        size=(cell_w - 2, cell_h - 2),
                        fill=PRIMARY_COLOR))
        elif density > 0.7:
            # Medium-high - small filled rects
            size = cell_h * 0.4
            dwg.add(Rect(insert=(x + cell_w/2 - size/2, y + cell_h/2 - size/2),
                        size=(size, size), fill=ACCENT_3))
        elif density > 0.5:
            # Medium - dots
            radius = cell_h * 0.15
            dwg.add(Circle(center=(x + cell_w/2, y + cell_h/2),
                          r=radius, fill=ACCENT_2))
        elif density > 0.3:
            # Light - small dots
            radius = cell_h * 0.08
            dwg.add(Circle(center=(x + cell_w/2, y + cell_h/2),
                          r=radius, fill=ACCENT_1))
        else:
            # Sparse - minimal marks
            if row % 3 == 0 and col % 4 == 0:
                dwg.add(Circle(center=(x + cell_w/2, y + cell_h/2),
                              r=cell_h * 0.05, fill=HIGHLIGHT))

# ===== BOTTOM ANNOTATIONS =====
annotation_y = pattern_start_y + pattern_height + 30

# Left annotation
dwg.add(Text("FIG 1.", insert=(MARGIN, annotation_y),
             fill=ACCENT_3, font_size=8, font_family='sans-serif',
             font_weight='normal'))
dwg.add(Text("DENSITY MAPPING",
             insert=(MARGIN, annotation_y + 12),
             fill=ACCENT_2, font_size=7, font_family='sans-serif',
             font_weight='normal', letter_spacing=1))

# Right annotation
right_label_x = WIDTH - MARGIN - 100
dwg.add(Text("UNMATCHED", insert=(right_label_x, annotation_y),
             fill=PRIMARY_COLOR, font_size=9, font_family='sans-serif',
             font_weight='normal', letter_spacing=3))
dwg.add(Text("ORDINAL SYSTEM",
             insert=(right_label_x + 5, annotation_y + 12),
             fill=ACCENT_2, font_size=6, font_family='sans-serif',
             font_weight='normal', letter_spacing=2))

# ===== SUBTLE GRID OVERLAY =====
# Very light grid for technical diagram feel
for i in range(1, 10):
    y = pattern_start_y + (pattern_height / 10) * i
    dwg.add(Line(start=(MARGIN, y), end=(WIDTH - MARGIN, y),
                 stroke=ACCENT_1, stroke_width=0.3, stroke_opacity=0.5))

# Save SVG
dwg.save()

print("SVG created successfully")
