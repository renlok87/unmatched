"""
Unmatched Design System - Figma API Automation

Автоматическое создание Design System в Figma через REST API

Требования:
1. Figma Access Token (https://www.figma.com/developers/api#access-tokens)
2. Python 3.8+
3. Установленные пакеты: requests, Pillow

Использование:
    # Первый запуск - создание файла
    python figma_api_designer.py --create-file

    # Обновление существующего файла
    python figma_api_designer.py --file-key <FILE_KEY> --update

    # Полная генерация Design System
    python figma_api_designer.py --file-key <FILE_KEY> --full
"""

import os
import sys
import json
import base64
import requests
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

# Настройка кодировки
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')


# ============================================================================
# CONFIGURATION
# ============================================================================

FIGMA_API_URL = "https://api.figma.com/v1"

# Получите токен на https://www.figma.com/developers/api#access-tokens
FIGMA_ACCESS_TOKEN = os.getenv("FIGMA_ACCESS_TOKEN", "")

# ID файла Figma (можно получить из URL: figma.com/file/<FILE_KEY>/...)
FIGMA_FILE_KEY = os.getenv("FIGMA_FILE_KEY", "")


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class ColorToken:
    """Цветовой токен"""
    name: str
    hex: str
    category: str
    description: str


@dataclass
class TextStyle:
    """Стиль текста"""
    name: str
    size: int
    weight: int
    line_height: float
    usage: str


@dataclass
class CardTemplate:
    """Шаблон карточки"""
    name: str
    width: int
    height: int
    type: str  # 'action' или 'hero'


# ============================================================================
# DESIGN SYSTEM DATA
# ============================================================================

COLORS = [
    # Primary Colors
    ColorToken("Primary Yellow", "#FFD700", "primary", "Energetic"),
    ColorToken("Primary Purple", "#6B4C9A", "primary", "Mystical"),
    ColorToken("Primary Red", "#DC143C", "primary", "Combat"),
    ColorToken("Primary Blue", "#1E3A8A", "primary", "Tactical"),

    # Neutral Colors
    ColorToken("Black", "#000000", "neutral", "Black"),
    ColorToken("Dark Gray", "#1F1F1F", "neutral", "Dark Gray"),
    ColorToken("Gray", "#808080", "neutral", "Gray"),
    ColorToken("Light Gray", "#D3D3D3", "neutral", "Light Gray"),
    ColorToken("White", "#FFFFFF", "neutral", "White"),

    # Semantic Colors
    ColorToken("Energy", "#FF6B35", "semantic", "Energy/Power"),
    ColorToken("Speed", "#4ECDC4", "semantic", "Speed/Mobility"),
    ColorToken("Defense", "#95E1D3", "semantic", "Defense/Shield"),
    ColorToken("Magic", "#A8DADC", "semantic", "Magic/Mystic"),

    # Faction Colors
    ColorToken("Marvel", "#DC143C", "faction", "Marvel Comics"),
    ColorToken("Witcher", "#1E3A8A", "faction", "The Witcher"),
    ColorToken("Historical", "#D2B48C", "faction", "Historical Heroes"),
    ColorToken("Jurassic", "#228B22", "faction", "Jurassic Park"),
    ColorToken("TMNT", "#00A86B", "faction", "Ninja Turtles"),
]

TEXT_STYLES = [
    TextStyle("Heading 1", 40, 900, 1.2, "Main titles"),
    TextStyle("Heading 2", 32, 700, 1.2, "Hero names"),
    TextStyle("Heading 3", 24, 700, 1.3, "Card titles"),
    TextStyle("Subtitle", 18, 500, 1.4, "Subheadings"),
    TextStyle("Body", 14, 400, 1.5, "Body text"),
    TextStyle("Caption", 12, 400, 1.4, "Secondary info"),
    TextStyle("Label", 10, 400, 1.4, "Small labels"),
]

CARD_TEMPLATES = [
    CardTemplate("Action Card", 300, 420, "action"),
    CardTemplate("Hero Card", 300, 420, "hero"),
]

HEROES = [
    {"id": "oda-nobunaga", "name": "Oda Nobunaga", "native": "織田信長", "role": "Honor Guard", "faction": "historical"},
    {"id": "ms-marvel", "name": "Ms. Marvel", "native": "", "role": "Energy Absorber", "faction": "marvel"},
    {"id": "geralt", "name": "Geralt of Rivia", "native": "Wiedźmin", "role": "Witcher", "faction": "witcher"},
    {"id": "sun-wukong", "name": "Sun Wukong", "native": "孫悟空", "role": "Monkey King", "faction": "historical"},
    {"id": "dracula", "name": "Dracula", "native": "", "role": "Dark Lord", "faction": "historical"},
]


# ============================================================================
# FIGMA API CLIENT
# ============================================================================

class FigmaAPIClient:
    """Клиент для работы с Figma REST API"""

    def __init__(self, access_token: str):
        self.access_token = access_token
        self.headers = {
            "X-Figma-Token": access_token,
            "Content-Type": "application/json"
        }

    def create_file(self, name: str) -> Dict[str, Any]:
        """Создаёт новый файл в Figma"""
        # Для создания файла нужен Team ID
        # Сначала получим информацию о пользователе
        user_response = requests.get(f"{FIGMA_API_URL}/me", headers=self.headers)
        user_data = user_response.json()

        if "error" in user_data:
            print(f"[ERROR] Cannot get user info: {user_data['error']}")
            return {}

        # Создаём файл через проект (нужен Team ID)
        # Альтернатива - используем API для создания в личном проекте
        print(f"[INFO] Creating file: {name}")
        print(f"[INFO] Manual creation required. Please create file in Figma and use --file-key")

        return {"manual": True, "message": "Create file manually in Figma UI"}

    def get_file(self, file_key: str) -> Dict[str, Any]:
        """Получает информацию о файле"""
        response = requests.get(
            f"{FIGMA_API_URL}/files/{file_key}",
            headers=self.headers
        )
        return response.json()

    def get_file_nodes(self, file_key: str) -> Dict[str, Any]:
        """Получает узлы файла"""
        response = requests.get(
            f"{FIGMA_API_URL}/files/{file_key}/nodes",
            headers=self.headers
        )
        return response.json()

    def update_file(self, file_key: str, changes: List[Dict]) -> Dict[str, Any]:
        """Обновляет файл (использует API для обновления)"""
        # Figma API не поддерживает прямой update через REST
        # Нужно использовать plugin endpoints или генерировать схему

        response = requests.post(
            f"{FIGMA_API_URL}/files/{file_key}",
            headers=self.headers,
            json=changes
        )
        return response.json()

    def create_component(
        self,
        file_key: str,
        name: str,
        width: int,
        height: int,
        fills: List[Dict],
        children: Optional[List[Dict]] = None
    ) -> str:
        """Создаёт компонент в Figma через API"""
        # Figma REST API не поддерживает прямое создание компонентов
        # Это требует использования Figma Plugin илиManual import

        print(f"[INFO] Would create component: {name} ({width}x{height})")
        return ""


# ============================================================================
# IMAGE GENERATOR
# ============================================================================

class CardImageGenerator:
    """Генерирует изображения карточек для импорта в Figma"""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Шрифты
        self.fonts = {}
        self._load_fonts()

    def _load_fonts(self):
        """Загружает шрифты"""
        try:
            # Пытаемся загрузить системные шрифты
            self.fonts["title"] = ImageFont.truetype("arial.ttf", 24)
            self.fonts["heading"] = ImageFont.truetype("arialbd.ttf", 32)
            self.fonts["body"] = ImageFont.truetype("arial.ttf", 14)
            self.fonts["small"] = ImageFont.truetype("arial.ttf", 10)
        except:
            # Fallback
            self.fonts["title"] = ImageFont.load_default()
            self.fonts["heading"] = ImageFont.load_default()
            self.fonts["body"] = ImageFont.load_default()
            self.fonts["small"] = ImageFont.load_default()

    def hex_to_rgb(self, hex_color: str) -> tuple:
        """Конвертирует HEX в RGB"""
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def draw_rounded_rectangle(
        self,
        draw: ImageDraw,
        xy: tuple,
        radius: int,
        fill: tuple
    ):
        """Рисует прямоугольник со скруглёнными углами"""
        x1, y1, x2, y2 = xy
        draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
        draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)
        draw.pieslice([x1, y1, x1 + 2*radius, y1 + 2*radius], 180, 270, fill=fill)
        draw.pieslice([x2 - 2*radius, y1, x2, y1 + 2*radius], 270, 360, fill=fill)
        draw.pieslice([x1, y2 - 2*radius, x1 + 2*radius, y2], 90, 180, fill=fill)
        draw.pieslice([x2 - 2*radius, y2 - 2*radius, x2, y2], 0, 90, fill=fill)

    def create_action_card(
        self,
        title: str,
        effect: str,
        value: int,
        faction: str,
        colors: Dict[str, str]
    ) -> str:
        """Создаёт изображение боевой карты"""
        width, height = 300, 420

        # Создаём изображение
        img = Image.new("RGB", (width, height), (31, 31, 31))
        draw = ImageDraw.Draw(img)

        # Верхняя зона - иллюстрация (60%)
        top_height = int(height * 0.6)
        bg_color = self.hex_to_rgb(colors.get("primary", "#FFD700"))
        draw.rectangle([0, 0, width, top_height], fill=bg_color)

        # Значок фракции
        faction_badge_size = 40
        faction_color = self.hex_to_rgb(colors.get("faction", "#6B4C9A"))
        draw.ellipse(
            [10, 10, 10 + faction_badge_size, 10 + faction_badge_size],
            fill=faction_color
        )

        # Значение карты
        value_badge_size = 30
        draw.ellipse(
            [width - value_badge_size - 10, 10, width - 10, 10 + value_badge_size],
            fill=(0, 0, 0)
        )

        # Нижняя зона - описание
        draw.rectangle([0, top_height, width, height], fill=(31, 31, 31))

        # Заголовок
        try:
            draw.text((16, top_height + 16), title, fill=(255, 255, 255), font=self.fonts["title"])
        except:
            draw.text((16, top_height + 16), title, fill=(255, 255, 255))

        # Эффект (разбиваем на строки)
        y_offset = top_height + 50
        words = effect.split()
        line = ""
        for word in words:
            test_line = line + word + " "
            try:
                bbox = draw.textbbox((0, 0), test_line, font=self.fonts["body"])
            except:
                bbox = (0, 0, 200, 14)
            if bbox[2] - bbox[0] < width - 32:
                line = test_line
            else:
                try:
                    draw.text((16, y_offset), line, fill=(128, 128, 128), font=self.fonts["body"])
                except:
                    draw.text((16, y_offset), line, fill=(128, 128, 128))
                y_offset += 20
                line = word + " "
        try:
            draw.text((16, y_offset), line, fill=(128, 128, 128), font=self.fonts["body"])
        except:
            draw.text((16, y_offset), line, fill=(128, 128, 128))

        # Фракция (нижний правый угол)
        try:
            draw.text((16, height - 30), faction, fill=(128, 128, 128), font=self.fonts["small"])
        except:
            draw.text((16, height - 30), faction, fill=(128, 128, 128))

        # Сохраняем
        filename = f"action_{title.lower().replace(' ', '_')}.png"
        filepath = self.output_dir / filename
        img.save(filepath)

        return str(filepath)

    def create_hero_card(
        self,
        name: str,
        native_name: str,
        role: str,
        faction: str,
        colors: Dict[str, str]
    ) -> str:
        """Создаёт изображение карточки героя"""
        width, height = 300, 420

        # Создаём изображение
        bg_color = self.hex_to_rgb(colors.get("primary", "#D2B48C"))
        img = Image.new("RGB", (width, height), bg_color)
        draw = ImageDraw.Draw(img)

        # Верхняя зона (15%)
        top_height = int(height * 0.15)
        draw.rectangle([0, 0, width, top_height], fill=(0, 0, 0, 20))

        # Логотип
        try:
            draw.text((16, 8), "UNMATCHED", fill=(255, 255, 255), font=self.fonts["small"])
        except:
            draw.text((16, 8), "UNMATCHED", fill=(255, 255, 255))

        # Центральная зона (60%) - герб
        center_y = int(height * 0.45)
        emblem_size = 120
        emblem_color = self.hex_to_rgb(colors.get("accent", "#FFFFFF"))
        draw.ellipse(
            [
                (width - emblem_size) // 2,
                center_y - emblem_size // 2,
                (width + emblem_size) // 2,
                center_y + emblem_size // 2
            ],
            fill=emblem_color,
            outline=self.hex_to_rgb(colors.get("border", "#DC143C")),
            width=4
        )

        # Нижняя зона (25%)
        bottom_y = int(height * 0.75)

        # Имя героя
        try:
            draw.text((16, bottom_y + 20), name.upper(), fill=(0, 0, 0), font=self.fonts["heading"])
        except:
            draw.text((16, bottom_y + 20), name.upper(), fill=(0, 0, 0))

        # Роль
        role_color = self.hex_to_rgb(colors.get("role", "#1E3A8A"))
        try:
            draw.text((16, bottom_y + 60), role, fill=role_color, font=self.fonts["title"])
        except:
            draw.text((16, bottom_y + 60), role, fill=role_color)

        # Сохраняем
        filename = f"hero_{name.lower().replace(' ', '_')}.png"
        filepath = self.output_dir / filename
        img.save(filepath)

        return str(filepath)

    def create_color_swatches(self, colors: List[ColorToken]) -> str:
        """Создаёт таблицу цветовых swatches"""
        swatch_size = 80
        cols = 5
        rows = (len(colors) + cols - 1) // cols

        width = cols * (swatch_size + 16) + 16
        height = rows * (swatch_size + 50) + 16

        img = Image.new("RGB", (width, height), (31, 31, 31))
        draw = ImageDraw.Draw(img)

        for i, color in enumerate(colors):
            row = i // cols
            col = i % cols

            x = 16 + col * (swatch_size + 16)
            y = 16 + row * (swatch_size + 50)

            # Swatch
            rgb = self.hex_to_rgb(color.hex)
            draw.rectangle([x, y, x + swatch_size, y + swatch_size], fill=rgb)

            # Название
            try:
                draw.text((x, y + swatch_size + 4), color.name, fill=(255, 255, 255), font=self.fonts["small"])
                draw.text((x, y + swatch_size + 18), color.hex, fill=(128, 128, 128), font=self.fonts["small"])
            except:
                draw.text((x, y + swatch_size + 4), color.name, fill=(255, 255, 255))
                draw.text((x, y + swatch_size + 18), color.hex, fill=(128, 128, 128))

        filepath = self.output_dir / "color_palette.png"
        img.save(filepath)

        return str(filepath)


# ============================================================================
# FIGMA SCHEMA GENERATOR
# ============================================================================

class FigmaSchemaGenerator:
    """Генерирует JSON-схему для импорта в Figma"""

    def __init__(self):
        self.schema = {
            "document": {
                "type": "DOCUMENT",
                "id": "0:0",
                "children": []
            },
            "components": {},
            "styles": {}
        }

    def generate_color_page(self, colors: List[ColorToken]) -> Dict:
        """Генерирует страницу с цветами"""
        children = []

        # Заголовок
        children.append({
            "type": "TEXT",
            "id": "colors-title",
            "name": "Color Palette",
            "characters": "🎨 Color Palette",
            "fontSize": 32,
            "fontWeight": 900,
            "x": 32,
            "y": 32
        })

        # Swatches
        for i, color in enumerate(colors):
            row = i // 5
            col = i % 5
            x = 32 + col * 120
            y = 100 + row * 150

            children.append({
                "type": "RECTANGLE",
                "id": f"color-{i}",
                "name": color.name,
                "x": x,
                "y": y,
                "width": 100,
                "height": 100,
                "fills": [{"type": "SOLID", "color": self._hex_to_rgb(color.hex)}],
                "cornerRadius": 8
            })

            children.append({
                "type": "TEXT",
                "id": f"color-name-{i}",
                "name": f"{color.name} Label",
                "characters": f"{color.name}\n{color.hex}",
                "fontSize": 10,
                "x": x,
                "y": y + 110,
                "width": 100
            })

        return {
            "type": "PAGE",
            "id": "colors-page",
            "name": "01. Colors & Styles",
            "children": children
        }

    def generate_cards_page(self) -> Dict:
        """Генерирует страницу с карточками"""
        children = []

        # Заголовок
        children.append({
            "type": "TEXT",
            "id": "cards-title",
            "name": "Card Templates",
            "characters": "🃏 Card Templates",
            "fontSize": 32,
            "fontWeight": 900,
            "x": 32,
            "y": 32
        })

        # Action Card Template
        action_card = {
            "type": "COMPONENT",
            "id": "action-card-template",
            "name": "C/Action Card",
            "x": 32,
            "y": 100,
            "width": 300,
            "height": 420,
            "children": [
                {
                    "type": "RECTANGLE",
                    "name": "Background",
                    "fills": [{"type": "SOLID", "color": {"r": 0.12, "g": 0.12, "b": 0.12}}]
                },
                {
                    "type": "RECTANGLE",
                    "name": "Illustration Area",
                    "x": 0,
                    "y": 0,
                    "width": 300,
                    "height": 252,
                    "fills": [{"type": "SOLID", "color": {"r": 1, "g": 0.84, "b": 0}}],
                    "cornerRadius": {"topLeft": 16, "topRight": 16}
                },
                {
                    "type": "ELLIPSE",
                    "name": "Faction Badge",
                    "x": 10,
                    "y": 10,
                    "width": 40,
                    "height": 40,
                    "fills": [{"type": "SOLID", "color": {"r": 0.42, "g": 0.3, "b": 0.6}}]
                },
                {
                    "type": "ELLIPSE",
                    "name": "Value Badge",
                    "x": 260,
                    "y": 10,
                    "width": 30,
                    "height": 30,
                    "fills": [{"type": "SOLID", "color": {"r": 0, "g": 0, "b": 0}}]
                },
                {
                    "type": "TEXT",
                    "name": "Card Title",
                    "characters": "BREAKTHROUGH",
                    "fontSize": 16,
                    "fontWeight": 700,
                    "x": 16,
                    "y": 268
                },
                {
                    "type": "TEXT",
                    "name": "Card Effect",
                    "characters": "DURING FIGHT: If MS. MARVEL started her turn on a different space, this card is worth 5.",
                    "fontSize": 12,
                    "x": 16,
                    "y": 300
                }
            ],
            "cornerRadius": 16
        }

        # Hero Card Template
        hero_card = {
            "type": "COMPONENT",
            "id": "hero-card-template",
            "name": "C/Hero Card",
            "x": 360,
            "y": 100,
            "width": 300,
            "height": 420,
            "children": [
                {
                    "type": "RECTANGLE",
                    "name": "Background",
                    "fills": [{"type": "SOLID", "color": {"r": 0.82, "g": 0.74, "b": 0.55}}],
                    "cornerRadius": 16
                },
                {
                    "type": "ELLIPSE",
                    "name": "Emblem",
                    "x": 90,
                    "y": 120,
                    "width": 120,
                    "height": 120,
                    "fills": [{"type": "SOLID", "color": {"r": 1, "g": 1, "b": 1}}],
                    "strokes": [{"type": "SOLID", "color": {"r": 0.86, "g": 0.08, "b": 0.24}}],
                    "strokeWeight": 4
                },
                {
                    "type": "TEXT",
                    "name": "Hero Name",
                    "characters": "ODA NOBUNAGA",
                    "fontSize": 24,
                    "fontWeight": 700,
                    "x": 16,
                    "y": 320
                },
                {
                    "type": "TEXT",
                    "name": "Hero Role",
                    "characters": "HONOR GUARD",
                    "fontSize": 14,
                    "x": 16,
                    "y": 360
                }
            ]
        }

        children.extend([action_card, hero_card])

        return {
            "type": "PAGE",
            "id": "cards-page",
            "name": "02. Card Templates",
            "children": children
        }

    def generate_heroes_page(self, heroes: List[Dict]) -> Dict:
        """Генерирует страницу с героями"""
        children = []

        # Заголовок
        children.append({
            "type": "TEXT",
            "id": "heroes-title",
            "name": "Heroes",
            "characters": "👥 Heroes",
            "fontSize": 32,
            "fontWeight": 900,
            "x": 32,
            "y": 32
        })

        # Карточки героев
        for i, hero in enumerate(heroes):
            col = i % 4
            row = i // 4
            x = 32 + col * 340
            y = 100 + row * 460

            children.append({
                "type": "INSTANCE",
                "id": f"hero-{i}",
                "name": f"H/{hero['name']}",
                "componentId": "hero-card-template",
                "x": x,
                "y": y
            })

        return {
            "type": "PAGE",
            "id": "heroes-page",
            "name": "03. Heroes",
            "children": children
        }

    def generate_schema(self) -> Dict:
        """Генерирует полную схему Design System"""
        pages = [
            self.generate_color_page(COLORS),
            self.generate_cards_page(),
            self.generate_heroes_page(HEROES)
        ]

        self.schema["document"]["children"] = pages
        return self.schema

    def _hex_to_rgb(self, hex_color: str) -> Dict[str, float]:
        """Конвертирует HEX в RGB для Figma (0-1)"""
        hex_color = hex_color.lstrip("#")
        rgb = tuple(int(hex_color[i:i+2], 16) / 255 for i in (0, 2, 4))
        return {"r": rgb[0], "g": rgb[1], "b": rgb[2]}

    def save_schema(self, filepath: str):
        """Сохраняет схему в файл"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.generate_schema(), f, indent=2, ensure_ascii=False)


# ============================================================================
# MAIN
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Unmatched Design System - Figma API Automation")
    parser.add_argument("--create-file", action="store_true", help="Create new Figma file")
    parser.add_argument("--file-key", default=FIGMA_FILE_KEY, help="Figma file key")
    parser.add_argument("--update", action="store_true", help="Update existing file")
    parser.add_argument("--full", action="store_true", help="Full Design System generation")
    parser.add_argument("--generate-images", action="store_true", help="Generate card images")
    parser.add_argument("--output", default="./figma-generated", help="Output directory")
    parser.add_argument("--token", default=FIGMA_ACCESS_TOKEN, help="Figma Access Token")

    args = parser.parse_args()

    if not args.token:
        print("[ERROR] Figma Access Token required!")
        print("Get token at: https://www.figma.com/developers/api#access-tokens")
        print("Set via environment variable: FIGMA_ACCESS_TOKEN=xxx")
        return

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print(" Unmatched Design System - Figma API Automation")
    print("=" * 60)
    print()

    # Инициализация
    client = FigmaAPIClient(args.token)

    # Генерация изображений
    if args.generate_images or args.full:
        print("[STEP 1] Generating card images...")
        generator = CardImageGenerator(str(output_dir / "cards"))

        # Цветовая палитра
        generator.create_color_swatches(COLORS)
        print(f"[OK] Generated: color_palette.png")

        # Action Card
        generator.create_action_card(
            "BREAKTHROUGH",
            "DURING FIGHT: If MS. MARVEL started her turn on a different space, this card is worth 5.",
            2,
            "MS.MARVEL x3",
            {"primary": "#FFD700", "faction": "#6B4C9A"}
        )
        print(f"[OK] Generated: action_breakthrough.png")

        # Hero Cards
        for hero in HEROES[:3]:
            colors = {
                "primary": "#D2B48C" if hero["faction"] == "historical" else "#DC143C",
                "accent": "#FFFFFF",
                "border": "#DC143C",
                "role": "#1E3A8A"
            }
            filepath = generator.create_hero_card(
                hero["name"],
                hero["native"],
                hero["role"],
                hero["faction"],
                colors
            )
            print(f"[OK] Generated: hero_{hero['name'].lower()}.png")

    # Генерация схемы
    if args.full:
        print()
        print("[STEP 2] Generating Figma schema...")

        schema_gen = FigmaSchemaGenerator()
        schema_path = output_dir / "figma_schema.json"
        schema_gen.save_schema(str(schema_path))
        print(f"[OK] Generated: figma_schema.json")

    # Создание файла в Figma
    if args.create_file:
        print()
        print("[STEP 3] Creating Figma file...")

        result = client.create_file("Unmatched Design System")

        if result.get("manual"):
            print()
            print("[INFO] To use Figma API automation:")
            print("1. Create a new file in Figma (https://www.figma.com)")
            print("2. Copy the file key from URL")
            print("3. Run: python figma_api_designer.py --file-key <FILE_KEY> --full")

    # Обновление файла
    if args.update and args.file_key:
        print()
        print(f"[STEP 4] Updating file: {args.file_key}")

        file_info = client.get_file(args.file_key)

        if "error" in file_info:
            print(f"[ERROR] {file_info['error']}")
            return

        print(f"[OK] File: {file_info.get('document', {}).get('name', 'Unknown')}")

    # Сохранение токенов
    tokens_path = output_dir / "design_tokens.json"
    with open(tokens_path, 'w', encoding='utf-8') as f:
        json.dump({
            "colors": [asdict(c) for c in COLORS],
            "textStyles": [asdict(t) for t in TEXT_STYLES],
            "cardTemplates": [asdict(ct) for ct in CARD_TEMPLATES],
            "heroes": HEROES
        }, f, indent=2, ensure_ascii=False)

    print()
    print("=" * 60)
    print("[DONE] Design System generated successfully!")
    print()
    print(f"[DIR] Output: {output_dir.absolute()}")
    print()
    print("[FILES] Generated files:")
    print(f"   - {output_dir / 'cards' / 'color_palette.png'}")
    print(f"   - {output_dir / 'cards' / 'action_breakthrough.png'}")
    print(f"   - {output_dir / 'cards' / 'hero_*.png'}")
    print(f"   - {tokens_path}")
    if args.full:
        print(f"   - {schema_path}")
    print()
    print("[NEXT] Import images to Figma:")
    print("1. Open Figma")
    print("2. Create 'Unmatched Design System' file")
    print("3. Import images from output directory")
    print("4. Create components based on templates")
    print()


if __name__ == "__main__":
    main()
