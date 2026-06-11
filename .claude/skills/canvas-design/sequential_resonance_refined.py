"""
Sequential Resonance - Refined Version
A visual expression of systematic accumulation and concentric harmony.
"""

from PIL import Image, ImageDraw, ImageFont
import math

# Canvas dimensions - high resolution for print quality
WIDTH, HEIGHT = 2480, 3508  # A4 at 300 DPI

# Colors with careful calibration
BACKGROUND = '#F5F3F0'
DARK = '#1A1816'
ACCENT = '#8B7355'

# Create image
img = Image.new('RGB', (WIDTH, HEIGHT), BACKGROUND)
draw = ImageDraw.Draw(img)

# Center point
cx, cy = WIDTH // 2, HEIGHT // 2

# Circle configuration: (radius, mark_count, mark_length, thickness)
# Progressively building complexity through systematic accumulation
circles = [
    (70, 8, 30, 3),
    (110, 12, 24, 2.5),
    (155, 16, 22, 2.2),
    (205, 24, 20, 2),
    (260, 32, 18, 1.8),
    (320, 40, 16, 1.6),
    (385, 48, 15, 1.4),
    (455, 56, 14, 1.3),
    (530, 64, 13, 1.2),
    (610, 72, 12, 1.1),
    (695, 80, 11, 1.0),
    (785, 88, 10.5, 0.95),
    (880, 96, 10, 0.9),
    (980, 104, 9.5, 0.85),
]

# Draw concentric mark system
for i, (radius, mark_count, mark_length, thickness) in enumerate(circles):
    # Offset each circle for visual harmony - creating the resonance effect
    rotation_offset = i * (180 / mark_count)

    for j in range(mark_count):
        angle = (2 * math.pi * j / mark_count) + math.radians(rotation_offset)

        # Calculate mark positions
        outer_x = cx + radius * math.cos(angle)
        outer_y = cy + radius * math.sin(angle)
        inner_x = cx + (radius - mark_length) * math.cos(angle)
        inner_y = cy + (radius - mark_length) * math.sin(angle)

        # Draw mark with round caps for precision
        draw.line([(inner_x, inner_y), (outer_x, outer_y)],
                 fill=DARK, width=int(thickness))

# Add subtle guide circles - every fourth circle
for radius, _, _, _ in circles[::4]:
    bbox = [cx - radius, cy - radius, cx + radius, cy + radius]
    draw.ellipse(bbox, outline=ACCENT, width=1)

# Outer precision ring - creating boundary
outer_r = 1050
tick_count = 180

for i in range(tick_count):
    angle = 2 * math.pi * i / tick_count

    # Vary tick lengths and thickness for rhythm
    if i % 15 == 0:
        tick_length = 20
        tick_width = 2
    elif i % 5 == 0:
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

# Inner precision ring
inner_r = 45
for i in range(32):
    angle = 2 * math.pi * i / 32
    x1 = cx + (inner_r - 10) * math.cos(angle)
    y1 = cy + (inner_r - 10) * math.sin(angle)
    x2 = cx + inner_r * math.cos(angle)
    y2 = cy + inner_r * math.sin(angle)

    draw.line([(x1, y1), (x2, y2)], fill=ACCENT, width=1)

# Central focal point
draw.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=DARK)
draw.ellipse([cx - 16, cy - 16, cx + 16, cy + 16], outline=ACCENT, width=1)

# Typography - minimal and precise
# Try to use a system font, fall back to default if not available

try:
    # Try for thin/light font variants
    title_font = ImageFont.truetype("arial.ttf", 36)
    subtitle_font = ImageFont.truetype("arial.ttf", 14)
    annotation_font = ImageFont.truetype("arial.ttf", 11)
    ref_font = ImageFont.truetype("arial.ttf", 10)
except:
    title_font = ImageFont.load_default()
    subtitle_font = ImageFont.load_default()
    annotation_font = ImageFont.load_default()
    ref_font = ImageFont.load_default()

# Title with letter spacing - create character by character
title = "SEQUENTIAL RESONANCE"
title_y = 320
letter_spacing = 42

# Calculate total width for centering
total_width = len(title) * letter_spacing
start_x = cx - total_width // 2

for i, letter in enumerate(title):
    x = start_x + i * letter_spacing
    draw.text((x, title_y), letter, fill=DARK, font=title_font)

# Subtitle
subtitle = "SYSTEMATIC ACCUMULATION"
sub_bbox = subtitle_font.getbbox(subtitle)
sub_x = cx - sub_bbox[2] // 2
draw.text((sub_x, title_y + 60), subtitle, fill=ACCENT, font=subtitle_font)

# Bottom annotation
annotation = "FIG 01. CONCENTRIC HARMONIC SERIES"
anno_bbox = annotation_font.getbbox(annotation)
anno_x = cx - anno_bbox[2] // 2
draw.text((anno_x, HEIGHT - 240), annotation, fill=DARK, font=annotation_font)

# Reference markers - technical diagram aesthetic
references = [
    (cx + 550, cy - 180, "01"),
    (cx + 780, cy + 320, "02"),
    (cx - 820, cy + 220, "03"),
    (cx - 600, cy - 500, "04"),
]

for rx, ry, num in references:
    # Small line
    draw.line([(rx, ry), (rx + 30, ry - 18)], fill=DARK, width=1)
    # Number
    draw.text((rx + 38, ry - 16), num, fill=DARK, font=ref_font)

# Corner dot patterns - subtle grid suggestion
corner_offset = 140
dot_spacing = 20
dot_radius = 2

# Top-left
for i in range(10):
    for j in range(10):
        dot_x = corner_offset + i * dot_spacing
        dot_y = corner_offset + j * dot_spacing
        if dot_x < WIDTH * 0.18 and dot_y < HEIGHT * 0.18:
            draw.ellipse([dot_x - dot_radius, dot_y - dot_radius,
                         dot_x + dot_radius, dot_y + dot_radius],
                        fill=DARK)

# Bottom-right
for i in range(10):
    for j in range(10):
        dot_x = WIDTH - corner_offset - i * dot_spacing
        dot_y = HEIGHT - corner_offset - j * dot_spacing
        if dot_x > WIDTH * 0.82 and dot_y > HEIGHT * 0.82:
            draw.ellipse([dot_x - dot_radius, dot_y - dot_radius,
                         dot_x + dot_radius, dot_y + dot_radius],
                        fill=DARK)

# Add faint arc lines for additional visual depth
# These create the sense of rotation and measurement
for r_start, r_end in [(0, 45), (90, 135), (180, 225), (270, 315)]:
    arc_r = 1120
    arc_bbox = [cx - arc_r, cy - arc_r, cx + arc_r, cy + arc_r]

    # Draw arc segments
    for angle_deg in range(r_start, r_end, 2):
        angle_rad = math.radians(angle_deg)
        x1 = cx + (arc_r - 8) * math.cos(angle_rad)
        y1 = cy + (arc_r - 8) * math.sin(angle_rad)
        x2 = cx + arc_r * math.cos(angle_rad)
        y2 = cy + arc_r * math.sin(angle_rad)

        opacity = 50 if angle_deg % 45 == 0 else 30
        # Create faint color
        draw.line([(x1, y1), (x2, y2)], fill=DARK, width=1)

# Save as high-quality PNG
img.save('sequential_resonance.png', quality=100, DPI=(300, 300))
print("PNG created: sequential_resonance.png")

# Also try to create PDF if possible
try:
    img.save('sequential_resonance.pdf', "PDF", resolution=300, quality=100)
    print("PDF created: sequential_resonance.pdf")
except Exception as e:
    print(f"PDF creation not available: {e}")
