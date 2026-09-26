"""
Sequential Resonance - Masterpiece Edition
Second pass refinement for museum-quality execution.
Every detail meticulously crafted and painstakingly refined.
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math

# Canvas dimensions - print quality
WIDTH, HEIGHT = 2480, 3508  # A4 at 300 DPI

# Refined color palette - meticulously calibrated
BACKGROUND = (245, 243, 240)      # #F5F3F0 - warm off-white
DARK = (26, 24, 22)              # #1A1816 - nearly black
ACCENT = (139, 115, 85)          # #8B7355 - warm taupe
FAINT = (26, 24, 22, 25)         # Dark with low opacity

# Create image with anti-aliasing
img = Image.new('RGBA', (WIDTH, HEIGHT), BACKGROUND)
draw = ImageDraw.Draw(img, 'RGBA')

# Center point
cx, cy = WIDTH // 2, HEIGHT // 2

# Refined circle configuration - carefully tuned proportions
# (radius, mark_count, mark_length, thickness)
circles = [
    (75, 8, 32, 3.5),
    (118, 12, 26, 2.8),
    (165, 16, 24, 2.4),
    (218, 24, 22, 2.1),
    (276, 32, 20, 1.9),
    (340, 40, 18, 1.7),
    (410, 48, 17, 1.5),
    (485, 56, 16, 1.4),
    (565, 64, 15, 1.3),
    (650, 72, 14, 1.2),
    (740, 80, 13.5, 1.1),
    (835, 88, 13, 1.0),
    (935, 96, 12.5, 0.95),
    (1040, 104, 12, 0.9),
]

# Draw concentric mark system with precise anti-aliasing
for i, (radius, mark_count, mark_length, thickness) in enumerate(circles):
    rotation_offset = i * (180 / mark_count) + 7  # Added offset for organic feel

    for j in range(mark_count):
        angle = (2 * math.pi * j / mark_count) + math.radians(rotation_offset)

        outer_x = cx + radius * math.cos(angle)
        outer_y = cy + radius * math.sin(angle)
        inner_x = cx + (radius - mark_length) * math.cos(angle)
        inner_y = cy + (radius - mark_length) * math.sin(angle)

        # Draw with slight transparency for subtle depth
        draw.line([(inner_x, inner_y), (outer_x, outer_y)],
                 fill=DARK + (255,), width=int(thickness))

# Ultra-subtle guide circles - barely visible
for idx, radius in enumerate([c[0] for c in circles[::5]]):
    alpha = 40 if idx == 0 else 25
    bbox = [cx - radius, cy - radius, cx + radius, cy + radius]
    for offset in range(-1, 2):
        draw.ellipse([cx - radius + offset, cy - radius + offset,
                     cx + radius + offset, cy + radius + offset],
                    outline=ACCENT + (alpha,), width=1)

# Outer precision ring - refined proportions
outer_r = 1120
tick_count = 200

for i in range(tick_count):
    angle = 2 * math.pi * i / tick_count

    # Three-tier system for visual rhythm
    if i % 20 == 0:
        tick_length = 24
        tick_width = 2
    elif i % 5 == 0:
        tick_length = 16
        tick_width = 1
    else:
        tick_length = 9
        tick_width = 1

    x1 = cx + (outer_r - tick_length) * math.cos(angle)
    y1 = cy + (outer_r - tick_length) * math.sin(angle)
    x2 = cx + outer_r * math.cos(angle)
    y2 = cy + outer_r * math.sin(angle)

    draw.line([(x1, y1), (x2, y2)], fill=DARK + (255,), width=tick_width)

# Inner precision ring - more refined
inner_r = 48
for i in range(40):
    angle = 2 * math.pi * i / 40
    x1 = cx + (inner_r - 12) * math.cos(angle)
    y1 = cy + (inner_r - 12) * math.sin(angle)
    x2 = cx + inner_r * math.cos(angle)
    y2 = cy + inner_r * math.sin(angle)

    # Vary opacity for subtle rhythm
    alpha = 180 if i % 10 == 0 else 120
    draw.line([(x1, y1), (x2, y2)], fill=ACCENT + (alpha,), width=1)

# Central focal point - refined
draw.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=DARK + (255,))
draw.ellipse([cx - 20, cy - 20, cx + 20, cy + 20], outline=ACCENT + (180,), width=1)
draw.ellipse([cx - 24, cy - 24, cx + 24, cy + 24], outline=DARK + (40,), width=1)

# Typography with precise letter-spacing
# Load fonts with fallback
try:
    title_font = ImageFont.truetype("arial.ttf", 32)
    subtitle_font = ImageFont.truetype("arial.ttf", 13)
    annotation_font = ImageFont.truetype("arial.ttf", 10)
    ref_font = ImageFont.truetype("arial.ttf", 9)
except:
    title_font = ImageFont.load_default()
    subtitle_font = ImageFont.load_default()
    annotation_font = ImageFont.load_default()
    ref_font = ImageFont.load_default()

# Title - precisely spaced
title = "SEQUENTIAL RESONANCE"
title_y = 340
letter_spacing = 46

total_width = len(title.replace(" ", "")) * letter_spacing
start_x = cx - total_width // 2

for i, letter in enumerate(title):
    if letter != " ":
        x = start_x + i * letter_spacing
        draw.text((x, title_y), letter, fill=DARK + (255,), font=title_font)

# Subtitle - refined positioning
subtitle = "SYSTEMATIC ACCUMULATION"
sub_bbox = subtitle_font.getbbox(subtitle)
sub_x = cx - sub_bbox[2] // 2 + 20
draw.text((sub_x, title_y + 55), subtitle, fill=ACCENT + (200,), font=subtitle_font)

# Small divider line below subtitle
div_width = 120
draw.line([(cx - div_width//2, title_y + 78), (cx + div_width//2, title_y + 78)],
         fill=ACCENT + (100,), width=1)

# Bottom annotation - refined
annotation = "FIG 01 — CONCENTRIC HARMONIC SERIES"
anno_bbox = annotation_font.getbbox(annotation)
anno_x = cx - anno_bbox[2] // 2 + 25
draw.text((anno_x, HEIGHT - 260), annotation, fill=DARK + (120,), font=annotation_font)

# Reference markers - technical precision
references = [
    (cx + 580, cy - 200, "I"),
    (cx + 840, cy + 360, "II"),
    (cx - 880, cy + 260, "III"),
    (cx - 640, cy - 540, "IV"),
]

for rx, ry, num in references:
    # Fine line
    draw.line([(rx, ry), (rx + 35, ry - 20)], fill=DARK + (80,), width=1)
    # Small dot at endpoint
    draw.ellipse([rx + 33, ry - 22, rx + 37, ry - 18], fill=DARK + (80,))
    # Number
    draw.text((rx + 45, ry - 18), num, fill=DARK + (100,), font=ref_font)

# Corner dot patterns - refined grid
corner_offset = 160
dot_spacing = 22
dot_radius = 1.5

def draw_corner_grid(start_x, start_y, dir_x, dir_y):
    for i in range(12):
        for j in range(12):
            dot_x = start_x + i * dot_spacing * dir_x
            dot_y = start_y + j * dot_spacing * dir_y

            # Check bounds
            if ((dir_x == 1 and dot_x > WIDTH * 0.2) or
                (dir_x == -1 and dot_x < WIDTH * 0.8) or
                (dir_y == 1 and dot_y > HEIGHT * 0.2) or
                (dir_y == -1 and dot_y < HEIGHT * 0.8)):
                continue

            # Vary opacity for depth
            dist_from_corner = math.sqrt(i*i + j*j)
            alpha = max(20, 60 - dist_from_corner * 3)
            draw.ellipse([dot_x - dot_radius, dot_y - dot_radius,
                         dot_x + dot_radius, dot_y + dot_radius],
                        fill=DARK + (int(alpha),))

draw_corner_grid(corner_offset, corner_offset, 1, 1)  # Top-left
draw_corner_grid(WIDTH - corner_offset, HEIGHT - corner_offset, -1, -1)  # Bottom-right

# Add subtle arc segments at cardinal positions
# These create the sense of precise measurement
arc_positions = [
    (0, 30, -1),      # Top
    (90, 120, 1),     # Right
    (180, 210, -1),   # Bottom
    (270, 300, 1),    # Left
]

arc_r = 1200
for start, end, direction in arc_positions:
    for angle_deg in range(start, end, 3):
        angle_rad = math.radians(angle_deg)
        x1 = cx + (arc_r - 10) * math.cos(angle_rad)
        y1 = cy + (arc_r - 10) * math.sin(angle_rad)
        x2 = cx + arc_r * math.cos(angle_rad)
        y2 = cy + arc_r * math.sin(angle_rad)

        alpha = 50 if angle_deg % 15 == 0 else 25
        draw.line([(x1, y1), (x2, y2)], fill=DARK + (alpha,), width=1)

# Convert to RGB for saving
img_rgb = Image.new('RGB', img.size, BACKGROUND)
img_rgb.paste(img, mask=img.split()[3] if img.mode == 'RGBA' else None)

# Apply very subtle blur for smooth edges (simulating print quality)
img_final = img_rgb.filter(ImageFilter.SMOOTH)

# Save as high-quality PNG
img_final.save('sequential_resonance_masterpiece.png', quality=100, optimize=True, DPI=(300, 300))
print("Masterpiece PNG created: sequential_resonance_masterpiece.png")

# Save PDF
try:
    img_final.save('sequential_resonance_masterpiece.pdf', "PDF", resolution=300, quality=100)
    print("Masterpiece PDF created: sequential_resonance_masterpiece.pdf")
except Exception as e:
    print(f"PDF creation: {e}")

# Also create a version with the philosophy embedded as metadata
from PIL import PngImagePlugin
pnginfo = PngImagePlugin.PngInfo()
pnginfo.add_text("Description", "Sequential Resonance - A visual philosophy of systematic accumulation expressed through concentric mark systems. Each element exists as both individual entity and part of greater whole, creating visual resonance through patient layering and meticulous craftsmanship.")
img_final.save('sequential_resonance_masterpiece.png', "PNG", pnginfo=pnginfo, quality=100, optimize=True, DPI=(300, 300))
print("PNG with metadata saved.")
