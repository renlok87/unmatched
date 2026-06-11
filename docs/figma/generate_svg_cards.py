"""
Создаёт SVG карточки для импорта в Figma
SVG файлы отображаются идеально в Figma
"""

import os
import sys
from pathlib import Path

# Настройка кодировки
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

OUTPUT_DIR = Path("./figma-generated/svg-cards")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def create_action_card_svg(title: str, effect: str, value: str, faction: str) -> str:
    """Создаёт SVG Action Card"""
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="300" height="420" viewBox="0 0 300 420">
  <defs>
    <clipPath id="card-clip">
      <rect width="300" height="420" rx="16" ry="16"/>
    </clipPath>
  </defs>

  <!-- Background -->
  <rect width="300" height="420" fill="#1F1F1F" clip-path="url(#card-clip)"/>

  <!-- Illustration Area (60%) -->
  <rect width="300" height="252" fill="#FFD700" clip-path="url(#card-clip)"/>

  <!-- Faction Badge -->
  <circle cx="30" cy="30" r="20" fill="#6B4C9A"/>

  <!-- Value Badge -->
  <circle cx="270" cy="25" r="15" fill="#000000"/>
  <text x="270" y="30" text-anchor="middle" fill="#FFD700" font-family="Arial" font-size="18" font-weight="bold">{value}</text>

  <!-- Card Title -->
  <text x="16" y="276" fill="#FFFFFF" font-family="Arial" font-size="16" font-weight="bold">{title}</text>

  <!-- Card Effect -->
  <text x="16" y="300" fill="#808080" font-family="Arial" font-size="12" width="268">
    <tspan x="16" dy="0">{effect[:35]}</tspan>
    <tspan x="16" dy="18">{effect[35:70] if len(effect) > 35 else ""}</tspan>
    <tspan x="16" dy="18">{effect[70:105] if len(effect) > 70 else ""}</tspan>
  </text>

  <!-- Card Footer -->
  <text x="16" y="400" fill="#808080" font-family="Arial" font-size="10">{faction}</text>
</svg>'''
    return svg


def create_hero_card_svg(name: str, native: str, role: str, faction_colors: dict) -> str:
    """Создаёт SVG Hero Card"""
    bg_color = faction_colors.get('bg', '#D2B48C')
    border_color = faction_colors.get('border', '#DC143C')

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="300" height="420" viewBox="0 0 300 420">
  <defs>
    <clipPath id="hero-clip">
      <rect width="300" height="420" rx="16" ry="16"/>
    </clipPath>
  </defs>

  <!-- Background -->
  <rect width="300" height="420" fill="{bg_color}" clip-path="url(#hero-clip)"/>

  <!-- Top Zone (15%) -->
  <rect width="300" height="63" fill="rgba(0,0,0,0.1)" clip-path="url(#hero-clip)"/>

  <!-- Logo -->
  <text x="16" y="20" fill="#FFFFFF" font-family="Arial" font-size="12" font-weight="900" letter-spacing="1">UNMATCHED</text>

  <!-- Native Name (vertical) -->
  <text x="280" y="15" fill="#FFFFFF" font-family="Arial" font-size="14" writing-mode="tb" glyph-orientation-vertical="0">{native}</text>

  <!-- Emblem -->
  <circle cx="150" cy="210" r="60" fill="#FFFFFF" stroke="{border_color}" stroke-width="4"/>
  <text x="150" y="225" text-anchor="middle" fill="{border_color}" font-family="Arial" font-size="48">⚔</text>

  <!-- Hero Name -->
  <text x="16" y="350" fill="#FFFFFF" font-family="Arial" font-size="24" font-weight="bold" text-shadow="0px 2px 4px rgba(0,0,0,0.3)">{name.upper()}</text>

  <!-- Hero Role -->
  <text x="16" y="380" fill="#1E3A8A" font-family="Arial" font-size="14">{role}</text>
</svg>'''
    return svg


def create_color_palette_svg() -> str:
    """Создаёт SVG палитру цветов"""
    colors = [
        ("Primary Yellow", "#FFD700"),
        ("Primary Purple", "#6B4C9A"),
        ("Primary Red", "#DC143C"),
        ("Primary Blue", "#1E3A8A"),
        ("Black", "#000000"),
        ("Dark Gray", "#1F1F1F"),
        ("Gray", "#808080"),
        ("Light Gray", "#D3D3D3"),
        ("White", "#FFFFFF"),
        ("Energy", "#FF6B35"),
        ("Speed", "#4ECDC4"),
        ("Defense", "#95E1D3"),
        ("Marvel", "#DC143C"),
        ("Witcher", "#1E3A8A"),
        ("Historical", "#D2B48C"),
        ("Jurassic", "#228B22"),
        ("TMNT", "#00A86B"),
    ]

    swatches = []
    for i, (name, color) in enumerate(colors):
        row = i // 6
        col = i % 6
        x = 20 + col * 120
        y = 60 + row * 120

        swatches.append(f'''
  <!-- Color {i}: {name} -->
  <rect x="{x}" y="{y}" width="100" height="100" fill="{color}" rx="8"/>
  <text x="{x + 50}" y="{y + 120}" text-anchor="middle" fill="#FFFFFF" font-family="Arial" font-size="12">{name}</text>
  <text x="{x + 50}" y="{y + 138}" text-anchor="middle" fill="#808080" font-family="monospace" font-size="10">{color}</text>
''')

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="760" height="500" viewBox="0 0 760 500">
  <rect width="760" height="500" fill="#1a1a2e"/>

  <!-- Title -->
  <text x="20" y="35" fill="#FFD700" font-family="Arial" font-size="24" font-weight="bold">🎨 Color Palette</text>
{''.join(swatches)}
</svg>'''
    return svg


# Генерируем SVG файлы
print("[STEP 1] Creating SVG cards...")

# Action Card
action_svg = create_action_card_svg(
    "BREAKTHROUGH",
    "DURING FIGHT: If MS. MARVEL started her turn on a different space, this card is worth 5.",
    "2",
    "MS.MARVEL • x3"
)
with open(OUTPUT_DIR / "action-card.svg", 'w', encoding='utf-8') as f:
    f.write(action_svg)
print("[OK] Created: action-card.svg")

# Hero Cards
heroes = [
    {"name": "Oda Nobunaga", "native": "織田信長", "role": "Honor Guard", "colors": {"bg": "#D2B48C", "border": "#DC143C"}},
    {"name": "Ms. Marvel", "native": "", "role": "Energy Absorber", "colors": {"bg": "#DC143C", "border": "#FFD700"}},
    {"name": "Geralt", "native": "Wiedźmin", "role": "Witcher", "colors": {"bg": "#1E3A8A", "border": "#C0C0C0"}},
    {"name": "Sun Wukong", "native": "孫悟空", "role": "Monkey King", "colors": {"bg": "#D2B48C", "border": "#FF6B35"}},
    {"name": "Dracula", "native": "", "role": "Dark Lord", "colors": {"bg": "#2C2C2C", "border": "#DC143C"}},
]

for hero in heroes:
    filename = f"hero-{hero['name'].lower().replace(' ', '-')}.svg"
    hero_svg = create_hero_card_svg(hero['name'], hero['native'], hero['role'], hero['colors'])
    with open(OUTPUT_DIR / filename, 'w', encoding='utf-8') as f:
        f.write(hero_svg)
    print(f"[OK] Created: {filename}")

# Color Palette
palette_svg = create_color_palette_svg()
with open(OUTPUT_DIR / "color-palette.svg", 'w', encoding='utf-8') as f:
    f.write(palette_svg)
print("[OK] Created: color-palette.svg")

print()
print("[DONE] All SVG files created!")
print(f"[DIR] Output: {OUTPUT_DIR.absolute()}")
print()
print("[IMPORT] Drag & Drop these files to Figma:")
print(f"   - {OUTPUT_DIR / 'action-card.svg'}")
print(f"   - {OUTPUT_DIR / 'hero-*.svg'}")
print(f"   - {OUTPUT_DIR / 'color-palette.svg'}")
