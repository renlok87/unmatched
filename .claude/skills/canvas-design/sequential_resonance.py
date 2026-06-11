import svgwrite
from svgwrite import cm, mm
import math

# Canvas dimensions
WIDTH, HEIGHT = 2480, 3508  # A4 at 300 DPI

dwg = svgwrite.Drawing('sequential_resonance.svg', size=(WIDTH, HEIGHT), profile='full')
dwg.add(dwg.rect(insert=(0, 0), size=(WIDTH, HEIGHT), fill='#F5F3F0'))  # Warm off-white background

# Center point
cx, cy = WIDTH // 2, HEIGHT // 2

# Create concentric circle system with accumulated marks
# Each circle has specific number of marks - building resonance through repetition

# Configuration: circles from center outward
# (radius, mark_count, mark_length, thickness)
circles = [
    (60, 8, 25, 2.5),
    (95, 12, 20, 2),
    (135, 16, 18, 1.8),
    (180, 24, 16, 1.5),
    (230, 32, 14, 1.3),
    (285, 40, 12, 1.2),
    (345, 48, 11, 1.1),
    (410, 56, 10, 1.0),
    (480, 64, 9, 0.9),
    (555, 72, 8, 0.8),
    (635, 80, 7, 0.75),
    (720, 88, 6.5, 0.7),
    (810, 96, 6, 0.65),
]

# Color palette - restrained, monochromatic with subtle shift
dark_color = '#1A1816'
accent_color = '#8B7355'

# Draw the concentric system
for i, (radius, mark_count, mark_length, thickness) in enumerate(circles):
    rotation_offset = i * (180 / mark_count)  # Offset each circle for visual harmony

    for j in range(mark_count):
        angle = (2 * math.pi * j / mark_count) + math.radians(rotation_offset)

        # Mark position
        mark_x = cx + radius * math.cos(angle)
        mark_y = cy + radius * math.sin(angle)

        # Draw mark as line perpendicular to radius
        inner_x = cx + (radius - mark_length) * math.cos(angle)
        inner_y = cy + (radius - mark_length) * math.sin(angle)

        line = dwg.line(start=(inner_x, inner_y), end=(mark_x, mark_y))
        line.stroke(dark_color, width=thickness)
        line.style = f"stroke-linecap: round;"
        dwg.add(line)

# Add subtle guide circles (very thin, minimal)
for radius, _, _, _ in circles[::3]:  # Every third circle gets a guide
    circle = dwg.circle(center=(cx, cy), r=radius)
    circle.fill = 'none'
    circle.stroke(accent_color, width=0.3, opacity=0.3)
    dwg.add(circle)

# Add precision tick marks on outer ring
outer_r = 900
tick_count = 144
for i in range(tick_count):
    angle = 2 * math.pi * i / tick_count
    tick_length = 15 if i % 12 == 0 else 8
    tick_thickness = 1.2 if i % 12 == 0 else 0.6

    x1 = cx + (outer_r - tick_length) * math.cos(angle)
    y1 = cy + (outer_r - tick_length) * math.sin(angle)
    x2 = cx + outer_r * math.cos(angle)
    y2 = cy + outer_r * math.sin(angle)

    tick = dwg.line(start=(x1, y1), end=(x2, y2))
    tick.stroke(dark_color, width=tick_thickness)
    tick.style = "stroke-linecap: round;"
    dwg.add(tick)

# Add small inner precision ring
inner_precision_r = 30
for i in range(24):
    angle = 2 * math.pi * i / 24
    x1 = cx + (inner_precision_r - 8) * math.cos(angle)
    y1 = cy + (inner_precision_r - 8) * math.sin(angle)
    x2 = cx + inner_precision_r * math.cos(angle)
    y2 = cy + inner_precision_r * math.sin(angle)

    tick = dwg.line(start=(x1, y1), end=(x2, y2))
    tick.stroke(accent_color, width=0.8, opacity=0.6)
    tick.style = "stroke-linecap: round;"
    dwg.add(tick)

# Typography - minimal, positioned with exacting precision
# Using very thin sans-serif aesthetic via SVG

# Title at top - large tracking (letter spacing)
title_y = 280
title_size = 28

# Create letter-spaced text manually for precision
title = "SEQUENTIAL RESONANCE"
letter_spacing = 35
current_x = cx - (len(title) * letter_spacing) / 2

for letter in title:
    text = dwg.text(letter, insert=(current_x, title_y),
                   font_size=title_size, font_family='sans-serif',
                   font_weight='300', letter_spacing='0',
                   fill=dark_color)
    text.style = "font-weight: 200;"
    dwg.add(text)
    current_x += letter_spacing if letter != " " else letter_spacing / 2

# Subtitle below title
subtitle = "SYSTEMATIC ACCUMULATION"
sub_y = title_y + 50
sub_size = 11
sub_x = cx - (len(subtitle) * sub_size * 0.55) / 2

subtitle_text = dwg.text(subtitle, insert=(sub_x, sub_y),
                         font_size=sub_size, font_family='sans-serif',
                         font_weight='300', letter_spacing='6px',
                         fill=accent_color)
subtitle_text.style = "opacity: 0.7;"
dwg.add(subtitle_text)

# Bottom annotation - very small, precise
annotation = "FIG 01. CONCENTRIC HARMONIC SERIES"
anno_y = HEIGHT - 200
anno_size = 9
anno_x = cx - (len(annotation) * anno_size * 0.6) / 2

anno_text = dwg.text(annotation, insert=(anno_x, anno_y),
                    font_size=anno_size, font_family='sans-serif',
                    font_weight='300', letter_spacing='3px',
                    fill=dark_color)
anno_text.style = "opacity: 0.4;"
dwg.add(anno_text)

# Add small reference numbers like technical diagram
# Position at specific intervals around the composition
references = [
    (cx + 480, cy - 150, "01"),
    (cx + 680, cy + 280, "02"),
    (cx - 720, cy + 180, "03"),
    (cx - 520, cy - 420, "04"),
]

for rx, ry, num in references:
    # Small line extending from mark
    ref_line = dwg.line(start=(rx, ry), end=(rx + 25, ry - 15))
    ref_line.stroke(dark_color, width=0.4)
    ref_line.style = "opacity: 0.3;"
    dwg.add(ref_line)

    # Number
    ref_text = dwg.text(num, insert=(rx + 32, ry - 12),
                       font_size=8, font_family='sans-serif',
                       font_weight='200', letter_spacing='1px',
                       fill=dark_color)
    ref_text.style = "opacity: 0.35;"
    dwg.add(ref_text)

# Add very subtle dot pattern in corners - suggesting grid
corner_offset = 120
dot_spacing = 18
dot_size = 1.2

# Top-left corner
for i in range(8):
    for j in range(8):
        dot_x = corner_offset + i * dot_spacing
        dot_y = corner_offset + j * dot_spacing
        if dot_x < WIDTH * 0.15 and dot_y < HEIGHT * 0.15:
            dot = dwg.circle(center=(dot_x, dot_y), r=dot_size/2)
            dot.fill(dark_color, opacity=0.15)
            dwg.add(dot)

# Bottom-right corner
for i in range(8):
    for j in range(8):
        dot_x = WIDTH - corner_offset - i * dot_spacing
        dot_y = HEIGHT - corner_offset - j * dot_spacing
        if dot_x > WIDTH * 0.85 and dot_y > HEIGHT * 0.85:
            dot = dwg.circle(center=(dot_x, dot_y), r=dot_size/2)
            dot.fill(dark_color, opacity=0.15)
            dwg.add(dot)

# Add central focal point - tiny, precise
center_dot = dwg.circle(center=(cx, cy), r=4)
center_dot.fill(dark_color)
dwg.add(center_dot)

# Add faint ring around center dot
center_ring = dwg.circle(center=(cx, cy), r=12)
center_ring.fill = 'none'
center_ring.stroke(accent_color, width=0.5, opacity=0.4)
dwg.add(center_ring)

# Save SVG
dwg.save()

print("SVG created: sequential_resonance.svg")

# Now convert to PDF using cairosvg if available, otherwise save as PNG
try:
    import cairosvg

    # Convert SVG to PDF
    cairosvg.svg2pdf(url='sequential_resonance.svg', write_to='sequential_resonance.pdf')
    print("PDF created: sequential_resonance.pdf")
except ImportError:
    print("cairosvg not available. Install with: pip install cairosvg")
    print("SVG file created successfully and can be converted manually.")
