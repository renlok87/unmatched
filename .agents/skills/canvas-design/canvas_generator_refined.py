import svgwrite
from svgwrite import cm, mm
from svgwrite.shapes import Circle, Line, Rect
from svgwrite.text import Text
import math

# Canvas dimensions - high quality museum print size
WIDTH = 800
HEIGHT = 1100
MARGIN = 70

# Refined color palette - warmer, more sophisticated
BG_COLOR = "#f5f3ed"  # Warm cream, like fine paper
PRIMARY_COLOR = "#1c1c1a"  # Rich near-black
ACCENT_1 = "#c9b49a"  # Refined taupe
ACCENT_2 = "#8b7d68"  # Muted bronze
ACCENT_3 = "#3d3a35"  # Deep charcoal
ACCENT_4 = "#6a5f52"  # Medium taupe
HIGHLIGHT = "#c9a86c"  # Muted gold
SUBTLE_1 = "#e0d9cd"  # Light sand
SUBTLE_2 = "#d4ccc0"  # Medium sand

dwg = svgwrite.Drawing('ordinal_precision_refined.svg', size=(WIDTH, HEIGHT))
dwg.add(dwg.rect(insert=(0, 0), size=(WIDTH, HEIGHT), fill=BG_COLOR))

# ===== TOP SECTION: Refined Ordinal Grid =====
grid_start_y = MARGIN
grid_cell_size = 16
grid_cols = 40
grid_rows = 14

# Create a sophisticated ordinal pattern
for row in range(grid_rows):
    for col in range(grid_cols):
        x = MARGIN + col * grid_cell_size
        y = grid_start_y + row * grid_cell_size

        # Each cell's identity based on ordinal mathematics
        ordinal = row * grid_cols + col
        is_prime = ordinal in {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47}
        is_fibonacci = ordinal in {1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144}
        is_perfect_square = int(math.sqrt(ordinal))**2 == ordinal

        cx = x + grid_cell_size/2
        cy = y + grid_cell_size/2

        if is_fibonacci:
            # Golden positions - special treatment
            radius = grid_cell_size * 0.4
            dwg.add(Circle(center=(cx, cy), r=radius, fill='none',
                          stroke=HIGHLIGHT, stroke_width=1.5))
            dwg.add(Circle(center=(cx, cy), r=radius * 0.4, fill=HIGHLIGHT))

        elif is_prime:
            # Prime positions - solid accent
            radius = grid_cell_size * 0.28
            shade_factor = (row + col) % 3
            color = [ACCENT_1, ACCENT_2, ACCENT_4][shade_factor]
            dwg.add(Circle(center=(cx, cy), r=radius, fill=color))

        elif is_perfect_square:
            # Perfect squares - outlined
            radius = grid_cell_size * 0.32
            dwg.add(Circle(center=(cx, cy), r=radius, fill='none',
                          stroke=PRIMARY_COLOR, stroke_width=1.2))

        else:
            # Regular positions - minimal marks based on modulo
            mod = ordinal % 11
            if mod in {0, 5}:
                radius = grid_cell_size * 0.12
                dwg.add(Circle(center=(cx, cy), r=radius, fill=ACCENT_3))
            elif mod in {2, 7}:
                radius = grid_cell_size * 0.2
                dwg.add(Circle(center=(cx, cy), r=radius, fill='none',
                              stroke=SUBTLE_1, stroke_width=0.8))
            elif mod == 9:
                # Tiny accent marks
                dwg.add(Circle(center=(cx, cy), r=grid_cell_size * 0.06, fill=HIGHLIGHT))

# ===== SECTION DIVIDER =====
divider_y = grid_start_y + grid_rows * grid_cell_size + 50
dwg.add(Line(start=(MARGIN, divider_y), end=(WIDTH - MARGIN, divider_y),
             stroke=ACCENT_3, stroke_width=0.8))

# Small tick marks on divider
for i in range(9):
    x = MARGIN + (WIDTH - 2*MARGIN) * (i + 1) / 10
    dwg.add(Line(start=(x, divider_y - 4), end=(x, divider_y + 4),
                 stroke=ACCENT_3, stroke_width=0.8))

# ===== CENTRAL SECTION: Refined Concentric System =====
center_x = WIDTH / 2
center_y = divider_y + 200

# Concentric ordinal layers with precision
for i in range(16):
    radius = 15 + i * 11.5

    if i % 4 == 0:
        # Cardinal layers - bold solid
        dwg.add(Circle(center=(center_x, center_y), r=radius,
                      fill='none', stroke=PRIMARY_COLOR, stroke_width=2))
    elif i % 2 == 0:
        # Even layers - thin solid
        dwg.add(Circle(center=(center_x, center_y), r=radius,
                      fill='none', stroke=ACCENT_2, stroke_width=1))
    else:
        # Odd layers - varying dashed patterns
        dash = "3,6" if i % 3 == 1 else "1.5,4.5"
        dwg.add(Circle(center=(center_x, center_y), r=radius,
                      fill='none', stroke=ACCENT_3, stroke_width=0.6,
                      stroke_dasharray=dash))

# Central singular point - refined
dwg.add(Circle(center=(center_x, center_y), r=5, fill=HIGHLIGHT))
dwg.add(Circle(center=(center_x, center_y), r=10,
              fill='none', stroke=PRIMARY_COLOR, stroke_width=1.2))
dwg.add(Circle(center=(center_x, center_y), r=18,
              fill='none', stroke=HIGHLIGHT, stroke_width=0.8, stroke_dasharray="2,3"))

# Precise orbital markers
for angle in range(0, 360, 45):
    rad = math.radians(angle)
    for r in [50, 85, 130, 175]:
        mx = center_x + math.cos(rad) * r
        my = center_y + math.sin(rad) * r
        dwg.add(Circle(center=(mx, my), r=2.5, fill=ACCENT_2))

# ===== LEFT ANNOTATION - Refined =====
label_x = MARGIN + 25
label_y = center_y - 50

# Thin precise lines connecting to center
dwg.add(Line(start=(label_x + 45, label_y + 7), end=(center_x - 195, center_y),
             stroke=SUBTLE_1, stroke_width=0.5, stroke_dasharray="2,2"))

dwg.add(Text("ORDINAL", insert=(label_x, label_y),
             fill=ACCENT_2, font_size=9, font_family='sans-serif',
             font_weight='normal', letter_spacing=2.5))
dwg.add(Text("POSITION", insert=(label_x, label_y + 13),
             fill=ACCENT_2, font_size=9, font_family='sans-serif',
             font_weight='normal', letter_spacing=2.5))

# ===== RIGHT ANNOTATION - Refined =====
label_x = WIDTH - MARGIN - 90
label_y = center_y - 50

dwg.add(Line(start=(label_x, label_y + 7), end=(center_x + 195, center_y),
             stroke=SUBTLE_1, stroke_width=0.5, stroke_dasharray="2,2"))

dwg.add(Text("SINGULAR", insert=(label_x, label_y),
             fill=ACCENT_2, font_size=9, font_family='sans-serif',
             font_weight='normal', letter_spacing=2.5))
dwg.add(Text("IDENTITY", insert=(label_x, label_y + 13),
             fill=ACCENT_2, font_size=9, font_family='sans-serif',
             font_weight='normal', letter_spacing=2.5))

# ===== SECTION DIVIDER 2 =====
divider_y2 = center_y + 240
dwg.add(Line(start=(MARGIN, divider_y2), end=(WIDTH - MARGIN, divider_y2),
             stroke=ACCENT_3, stroke_width=0.8))

# ===== BOTTOM SECTION: Sophisticated Density Pattern =====
pattern_start_y = divider_y2 + 60
pattern_width = WIDTH - 2 * MARGIN
pattern_height = 280

# Refined density mapping
cols = 52
rows = 20
cell_w = pattern_width / cols
cell_h = pattern_height / rows

for row in range(rows):
    for col in range(cols):
        x = MARGIN + col * cell_w
        y = pattern_start_y + row * cell_h

        # Sophisticated density calculation
        density = (col / cols + row / rows) / 2
        ordinal = row * cols + col
        mod_7 = ordinal % 7
        mod_13 = ordinal % 13

        cx = x + cell_w/2
        cy = y + cell_h/2

        if density > 0.88:
            # Maximum density - filled rectangles with slight inset
            inset = 1.5 if (row + col) % 3 == 0 else 1
            dwg.add(Rect(insert=(x + inset, y + inset),
                        size=(cell_w - inset*2, cell_h - inset*2),
                        fill=PRIMARY_COLOR))

        elif density > 0.75:
            # High density - medium filled
            size = cell_h * 0.6
            offset = (cell_h - size) / 2
            dwg.add(Rect(insert=(x + offset, y + offset),
                        size=(size, size), fill=ACCENT_3))

        elif density > 0.62:
            # Medium-high - circles
            radius = cell_h * 0.28
            dwg.add(Circle(center=(cx, cy), r=radius, fill=ACCENT_2))

        elif density > 0.48:
            # Medium - smaller circles
            radius = cell_h * 0.18
            color = ACCENT_4 if mod_7 in {0, 3} else ACCENT_2
            dwg.add(Circle(center=(cx, cy), r=radius, fill=color))

        elif density > 0.35:
            # Medium-low - dots
            radius = cell_h * 0.1
            dwg.add(Circle(center=(cx, cy), r=radius, fill=ACCENT_1))

        elif density > 0.22:
            # Low - tiny dots
            radius = cell_h * 0.05
            dwg.add(Circle(center=(cx, cy), r=radius, fill=SUBTLE_2))

        else:
            # Sparse - occasional highlights
            if mod_13 == 0 or (mod_7 == 0 and col % 5 == 0):
                dwg.add(Circle(center=(cx, cy), r=cell_h * 0.08, fill=HIGHLIGHT))

# ===== SUBTLE GRID OVERLAY - Refined =====
# Very light technical grid
for i in range(1, 8):
    y = pattern_start_y + (pattern_height / 8) * i
    dwg.add(Line(start=(MARGIN, y), end=(WIDTH - MARGIN, y),
                 stroke=SUBTLE_1, stroke_width=0.25, stroke_opacity=0.6))

# Vertical grid lines (subtle)
for i in range(1, 7):
    x = MARGIN + (pattern_width / 7) * i
    dwg.add(Line(start=(x, pattern_start_y), end=(x, pattern_start_y + pattern_height),
                 stroke=SUBTLE_1, stroke_width=0.25, stroke_opacity=0.6))

# ===== BOTTOM ANNOTATIONS - Refined =====
annotation_y = pattern_start_y + pattern_height + 35

# Left figure reference
dwg.add(Text("FIG 1.", insert=(MARGIN, annotation_y),
             fill=ACCENT_3, font_size=8, font_family='sans-serif',
             font_weight='normal', letter_spacing=1))
dwg.add(Text("ORDINAL DENSITY DISTRIBUTION",
             insert=(MARGIN, annotation_y + 13),
             fill=ACCENT_2, font_size=7, font_family='sans-serif',
             font_weight='normal', letter_spacing=1.5))

# Center annotation
center_text_x = WIDTH / 2 - 110
dwg.add(Text("SYSTEMATIC PRECISION",
             insert=(center_text_x, annotation_y + 5),
             fill=PRIMARY_COLOR, font_size=8, font_family='sans-serif',
             font_weight='normal', letter_spacing=3))

# Right signature
right_label_x = WIDTH - MARGIN - 130
dwg.add(Text("UNMATCHED", insert=(right_label_x, annotation_y),
             fill=PRIMARY_COLOR, font_size=10, font_family='sans-serif',
             font_weight='normal', letter_spacing=4))
dwg.add(Text("ORDINAL SYSTEM",
             insert=(right_label_x + 18, annotation_y + 13),
             fill=ACCENT_2, font_size=6, font_family='sans-serif',
             font_weight='normal', letter_spacing=2))

# ===== CORNER MARKERS - Technical precision =====
corner_size = 15
# Top-left
dwg.add(Line(start=(MARGIN, MARGIN + corner_size), end=(MARGIN, MARGIN),
             stroke=ACCENT_3, stroke_width=1))
dwg.add(Line(start=(MARGIN, MARGIN), end=(MARGIN + corner_size, MARGIN),
             stroke=ACCENT_3, stroke_width=1))

# Top-right
dwg.add(Line(start=(WIDTH - MARGIN - corner_size, MARGIN), end=(WIDTH - MARGIN, MARGIN),
             stroke=ACCENT_3, stroke_width=1))
dwg.add(Line(start=(WIDTH - MARGIN, MARGIN), end=(WIDTH - MARGIN, MARGIN + corner_size),
             stroke=ACCENT_3, stroke_width=1))

# Bottom-left
dwg.add(Line(start=(MARGIN, HEIGHT - MARGIN - corner_size), end=(MARGIN, HEIGHT - MARGIN),
             stroke=ACCENT_3, stroke_width=1))
dwg.add(Line(start=(MARGIN, HEIGHT - MARGIN), end=(MARGIN + corner_size, HEIGHT - MARGIN),
             stroke=ACCENT_3, stroke_width=1))

# Bottom-right
dwg.add(Line(start=(WIDTH - MARGIN - corner_size, HEIGHT - MARGIN), end=(WIDTH - MARGIN, HEIGHT - MARGIN),
             stroke=ACCENT_3, stroke_width=1))
dwg.add(Line(start=(WIDTH - MARGIN, HEIGHT - MARGIN), end=(WIDTH - MARGIN, HEIGHT - MARGIN - corner_size),
             stroke=ACCENT_3, stroke_width=1))

# Save SVG
dwg.save()

print("Refined SVG created successfully")
