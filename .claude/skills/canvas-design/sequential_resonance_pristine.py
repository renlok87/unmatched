"""
Sequential Resonance - Pristine Edition
The ultimate refinement. Museum quality. Master craftsmanship.
Every mark placed with painstaking precision. Every space intentional.
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math

# Canvas dimensions
WIDTH, HEIGHT = 2480, 3508

# Painstakingly calibrated color palette
BACKGROUND = (247, 245, 242)      # Even warmer, more refined off-white
DARK = (23, 21, 19)              # Deeper, richer near-black
ACCENT = (125, 102, 75)          # More refined warm taupe

# Create image
img = Image.new('RGB', (WIDTH, HEIGHT), BACKGROUND)
draw = ImageDraw.Draw(img)

cx, cy = WIDTH // 2, HEIGHT // 2

# Refined circle system - every number calculated for visual harmony
circles = [
    (80, 8, 28, 3),
    (125, 12, 23, 2.5),
    (175, 16, 21, 2.2),
    (230, 24, 19, 2),
    (290, 32, 17, 1.8),
    (355, 40, 16, 1.6),
    (425, 48, 15, 1.5),
    (500, 56, 14, 1.4),
    (580, 64, 13, 1.3),
    (665, 72, 12.5, 1.2),
    (755, 80, 12, 1.1),
    (850, 88, 11.5, 1.05),
    (950, 96, 11, 1),
    (1055, 104, 10.5, 0.95),
]

# Draw with exacting precision
for i, (radius, mark_count, mark_length, thickness) in enumerate(circles):
    rotation_offset = i * (180 / mark_count) + 11.25

    for j in range(mark_count):
        angle = (2 * math.pi * j / mark_count) + math.radians(rotation_offset)

        outer_x = cx + radius * math.cos(angle)
        outer_y = cy + radius * math.sin(angle)
        inner_x = cx + (radius - mark_length) * math.cos(angle)
        inner_y = cy + (radius - mark_length) * math.sin(angle)

        draw.line([(inner_x, inner_y), (outer_x, outer_y)],
                 fill=DARK, width=int(thickness))

# Single ultra-subtle guide circle - restraint
guide_radius = circles[6][0]  # Seventh circle
bbox = [cx - guide_radius, cy - guide_radius, cx + guide_radius, cy + guide_radius]
draw.ellipse(bbox, outline=ACCENT, width=1)

# Outer precision ring - refined
outer_r = 1150
tick_count = 216  # Divisible by many numbers for harmony

for i in range(tick_count):
    angle = 2 * math.pi * i / tick_count

    if i % 18 == 0:
        tick_length = 22
        tick_width = 2
    elif i % 6 == 0:
        tick_length = 14
        tick_width = 1
    else:
        tick_length = 8
        tick_width = 1

    x1 = cx + (outer_r - tick_length) * math.cos(angle)
    y1 = cy + (outer_r - tick_length) * math.sin(angle)
    x2 = cx + outer_r * math.cos(angle)
    y2 = cy + outer_r * math.sin(angle)

    draw.line([(x1, y1), (x2, y2)], fill=DARK, width=tick_width)

# Inner ring - more refined
inner_r = 42
for i in range(36):
    angle = 2 * math.pi * i / 36
    x1 = cx + (inner_r - 11) * math.cos(angle)
    y1 = cy + (inner_r - 11) * math.sin(angle)
    x2 = cx + inner_r * math.cos(angle)
    y2 = cy + inner_r * math.sin(angle)

    width = 2 if i % 9 == 0 else 1
    color = DARK if i % 9 == 0 else ACCENT
    draw.line([(x1, y1), (x2, y2)], fill=color, width=width)

# Center point - pristine
draw.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=DARK)

# Single thin ring around center
draw.ellipse([cx - 18, cy - 18, cx + 18, cy + 18], outline=ACCENT, width=1)

# Typography - load refined fonts
try:
    # Try different font options for best result
    font_options = ["arial.ttf", "Helvetica.ttc", "SFNSDisplay.ttf"]
    title_font = None
    for font in font_options:
        try:
            title_font = ImageFont.truetype(font, 28)
            break
        except:
            continue
    if title_font is None:
        title_font = ImageFont.truetype("arial.ttf", 28)

    subtitle_font = ImageFont.truetype("arial.ttf", 11)
    annotation_font = ImageFont.truetype("arial.ttf", 9)
except:
    title_font = ImageFont.load_default()
    subtitle_font = ImageFont.load_default()
    annotation_font = ImageFont.load_default()

# Title - ultra-refined letter spacing
title = "SEQUENTIAL RESONANCE"
title_y = 360
letter_spacing = 50

# Calculate precise centering
char_count = len(title.replace(" ", ""))
total_width = char_count * letter_spacing + (len(title) - char_count) * (letter_spacing // 3)
start_x = cx - total_width // 2

current_x = start_x
for letter in title:
    if letter == " ":
        current_x += letter_spacing // 3
    else:
        draw.text((current_x, title_y), letter, fill=DARK, font=title_font)
        current_x += letter_spacing

# Subtitle - positioned with exacting precision
subtitle = "SYSTEMATIC ACCUMULATION"
sub_bbox = subtitle_font.getbbox(subtitle)
sub_x = cx - sub_bbox[2] // 2 + 12
draw.text((sub_x, title_y + 50), subtitle, fill=ACCENT, font=subtitle_font)

# Refined divider - very subtle
draw.line([(cx - 50, title_y + 72), (cx + 50, title_y + 72)],
         fill=DARK, width=1)

# Bottom annotation - refined
annotation = "FIG 01 — CONCENTRIC HARMONIC SERIES"
anno_bbox = annotation_font.getbbox(annotation)
anno_x = cx - anno_bbox[2] // 2 + 15
draw.text((anno_x, HEIGHT - 240), annotation, fill=DARK, font=annotation_font)

# Small reference markers - minimal
# Just two for balance
references = [
    (cx + 620, cy - 220, "01"),
    (cx - 720, cy + 300, "02"),
]

for rx, ry, num in references:
    draw.line([(rx, ry), (rx + 40, ry - 24)], fill=DARK, width=1)
    draw.text((rx + 48, ry - 20), num, fill=DARK, font=annotation_font)

# Corner elements - single dots at precise positions
# Just four per corner - absolute restraint
corner_dots = [
    (120, 120), (160, 120), (120, 160), (160, 160),  # Top-left
    (WIDTH - 120, HEIGHT - 120), (WIDTH - 160, HEIGHT - 120),
    (WIDTH - 120, HEIGHT - 160), (WIDTH - 160, HEIGHT - 160),  # Bottom-right
]

for dx, dy in corner_dots:
    draw.ellipse([dx - 2, dy - 2, dx + 2, dy + 2], fill=DARK)

# Apply subtle sharpen for crispness
img_final = img.filter(ImageFilter.SHARPEN)

# Save pristine version
img_final.save('sequential_resonance_pristine.png', quality=100, optimize=True, DPI=(300, 300))
print("Pristine PNG created: sequential_resonance_pristine.png")

img_final.save('sequential_resonance_pristine.pdf', "PDF", resolution=300, quality=100)
print("Pristine PDF created: sequential_resonance_pristine.pdf")

print("\n=== MASTERPIECE COMPLETE ===")
print("Three versions created:")
print("  1. sequential_resonance_masterpiece.png/pdf - Full elaborate version")
print("  2. sequential_resonance_pristine.png/pdf     - Minimal refined version")
print("  3. sequential_resonance.md                    - Design philosophy")
