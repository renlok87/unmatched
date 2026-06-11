"""
Unmatched Design System - Figma Asset Exporter

Этот скрипт подготавливает ассеты для импорта в Figma:
- Конвертирует изображения в PNG
- Создаёт структуру для импорта
- Генерирует CSV-манифест для Figma

Использование:
    python figma_exporter.py --input "../../scraped-data/images" --output "./figma-ready"
"""

import os
import sys
import json
import csv
import shutil
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict

# Настройка кодировки для Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')


@dataclass
class HeroAsset:
    """Данные об ассете героя"""
    hero_id: str
    hero_name: str
    asset_type: str  # avatar, card-cover, mini, deck
    source_path: str
    target_path: str
    width: int
    height: int


@dataclass
class ColorToken:
    """Цветовой токен для Design System"""
    name: str
    hex: str
    rgb: List[int]
    category: str
    description: str


class FigmaAssetExporter:
    """Экспортёр ассетов для Figma"""

    def __init__(self, input_dir: str, output_dir: str):
        self.input_dir = Path(input_dir).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.assets: List[HeroAsset] = []
        self.heroes_map: Dict[str, dict] = {}

        # Цветовая палитра
        self.colors = self._load_colors()

        # Создаём директорию вывода
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _load_colors(self) -> List[ColorToken]:
        """Загружает цвета из DESIGN_SYSTEM.md или JSON"""
        return [
            ColorToken("Primary Yellow", "#FFD700", [255, 215, 0], "primary", "Energetic"),
            ColorToken("Primary Purple", "#6B4C9A", [107, 76, 154], "primary", "Mystical"),
            ColorToken("Primary Red", "#DC143C", [220, 20, 60], "primary", "Combat"),
            ColorToken("Primary Blue", "#1E3A8A", [30, 58, 138], "primary", "Tactical"),
            ColorToken("Neutral Black", "#000000", [0, 0, 0], "neutral", "Black"),
            ColorToken("Dark Gray", "#1F1F1F", [31, 31, 31], "neutral", "Dark Gray"),
            ColorToken("Gray", "#808080", [128, 128, 128], "neutral", "Gray"),
            ColorToken("Light Gray", "#D3D3D3", [211, 211, 211], "neutral", "Light Gray"),
            ColorToken("White", "#FFFFFF", [255, 255, 255], "neutral", "White"),
            ColorToken("Energy", "#FF6B35", [255, 107, 53], "semantic", "Energy"),
            ColorToken("Speed", "#4ECDC4", [78, 205, 196], "semantic", "Speed"),
            ColorToken("Defense", "#95E1D3", [149, 225, 211], "semantic", "Defense"),
            ColorToken("Magic", "#A8DADC", [168, 218, 220], "semantic", "Magic"),
            ColorToken("Marvel", "#DC143C", [220, 20, 60], "faction", "Marvel"),
            ColorToken("Witcher", "#1E3A8A", [30, 58, 138], "faction", "The Witcher"),
            ColorToken("Historical", "#D2B48C", [210, 180, 140], "faction", "Historical"),
            ColorToken("Jurassic", "#228B22", [34, 139, 34], "faction", "Jurassic Park"),
            ColorToken("TMNT", "#00A86B", [0, 168, 107], "faction", "Ninja Turtles"),
        ]

    def scan_assets(self) -> None:
        """Сканирует директорию с ассетами"""
        print(f"[SCAN] Scanning: {self.input_dir}")

        heroes_dir = self.input_dir / "heroes"
        decks_dir = self.input_dir / "decks"

        if not heroes_dir.exists():
            print(f"[WARN] Directory heroes не найдена: {heroes_dir}")
            return

        # Сканируем героев
        for asset_type in ["avatars", "card-covers", "minis"]:
            type_dir = heroes_dir / asset_type
            if not type_dir.exists():
                continue

            for file_path in type_dir.glob("*"):
                if file_path.is_file() and file_path.suffix.lower() in [".png", ".jpg", ".jpeg", ".webp", ".gif"]:
                    hero_id = self._extract_hero_id(file_path.stem)
                    hero_name = self._format_hero_name(hero_id)

                    asset = HeroAsset(
                        hero_id=hero_id,
                        hero_name=hero_name,
                        asset_type=asset_type.replace("-", ""),
                        source_path=str(file_path),
                        target_path=f"heroes/{asset_type}/{file_path.name}",
                        width=self._get_asset_width(asset_type),
                        height=self._get_asset_height(asset_type)
                    )
                    self.assets.append(asset)

        # Сканируем колоды
        if decks_dir.exists():
            for file_path in decks_dir.glob("*"):
                if file_path.is_file() and file_path.suffix.lower() in [".png", ".jpg", ".jpeg", ".webp", ".gif"]:
                    hero_id = self._extract_hero_id(file_path.stem)
                    hero_name = self._format_hero_name(hero_id)

                    asset = HeroAsset(
                        hero_id=hero_id,
                        hero_name=hero_name,
                        asset_type="deck",
                        source_path=str(file_path),
                        target_path=f"decks/{file_path.name}",
                        width=300,
                        height=420
                    )
                    self.assets.append(asset)

        print(f"[OK] Found {len(self.assets)} ассетов")

    def _extract_hero_id(self, filename: str) -> str:
        """Извлекает ID героя из имени файла"""
        # Удаляем хеш и расширение
        name = filename.split("-")[0].split("_")[0]
        return name.lower().replace(" ", "-")

    def _format_hero_name(self, hero_id: str) -> str:
        """Форматирует имя героя из ID"""
        return " ".join(word.capitalize() for word in hero_id.replace("-", " ").split())

    def _get_asset_width(self, asset_type: str) -> int:
        """Возвращает ширину ассета по типу"""
        sizes = {
            "avatars": 150,
            "cardcovers": 300,
            "minis": 100
        }
        return sizes.get(asset_type.replace("-", ""), 150)

    def _get_asset_height(self, asset_type: str) -> int:
        """Возвращает высоту ассета по типу"""
        sizes = {
            "avatars": 150,
            "cardcovers": 420,
            "minis": 100
        }
        return sizes.get(asset_type.replace("-", ""), 150)

    def copy_assets(self) -> None:
        """Копирует ассеты в структуру для Figma"""
        print(f"[COPY] Copying ассетов в: {self.output_dir}")

        for asset in self.assets:
            target_path = self.output_dir / asset.target_path
            target_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                shutil.copy2(asset.source_path, target_path)
            except Exception as e:
                print(f"[ERROR] Copy error {asset.source_path}: {e}")

        print(f"[OK] Copied {len(self.assets)} файлов")

    def generate_figma_csv(self) -> None:
        """Генерирует CSV-манифест для импорта в Figma"""
        csv_path = self.output_dir / "figma-import.csv"

        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Type", "Name", "Source Path", "Target Frame", "Width", "Height", "Tags"])

            for asset in self.assets:
                writer.writerow([
                    asset.asset_type.capitalize(),
                    asset.hero_name,
                    asset.target_path,
                    f"{asset.hero_name}/{asset.asset_type}",
                    asset.width,
                    asset.height,
                    self._get_faction_tag(asset.hero_name)
                ])

        print(f"[CSV] Created CSV manifest: {csv_path}")

    def _get_faction_tag(self, hero_name: str) -> str:
        """Определяет фракцию героя по имени"""
        marvel_heroes = ["ms marvel", "spider man", "black panther", "deadpool",
                        "black widow", "she hulk", "moon knight", "ghost rider",
                        "cloak", "dagger", "bruce lee", "invisible man"]
        witcher_heroes = ["geralt", "ciri", "yennefer", "triss", "eredin", "philippa"]
        jurassic_heroes = ["raptor", "trex", "muldoon"]
        tmnt_heroes = ["leonardo", "raphael", "donatello", "michelangelo", "shredder", "krang"]

        name_lower = hero_name.lower()

        if any(h in name_lower for h in marvel_heroes):
            return "Marvel"
        elif any(h in name_lower for h in witcher_heroes):
            return "Witcher"
        elif any(h in name_lower for h in jurassic_heroes):
            return "Jurassic"
        elif any(h in name_lower for h in tmnt_heroes):
            return "TMNT"
        else:
            return "Historical"

    def generate_design_system_json(self) -> None:
        """Генерирует JSON-файл Design System"""
        ds_path = self.output_dir / "design-system.json"

        data = {
            "version": "1.0.0",
            "name": "Unmatched Design System",
            "colors": [
                {
                    "name": c.name,
                    "hex": c.hex,
                    "rgb": c.rgb,
                    "category": c.category,
                    "description": c.description
                }
                for c in self.colors
            ],
            "typography": {
                "fontFamily": "Inter, Arial, sans-serif",
                "sizes": [
                    {"name": "3XL", "size": 40, "weight": 900},
                    {"name": "2XL", "size": 32, "weight": 700},
                    {"name": "XL", "size": 24, "weight": 700},
                    {"name": "LG", "size": 18, "weight": 500},
                    {"name": "Base", "size": 14, "weight": 400},
                    {"name": "SM", "size": 12, "weight": 400},
                    {"name": "XS", "size": 10, "weight": 400}
                ]
            },
            "spacing": {
                "xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 32
            },
            "card": {
                "width": 300,
                "height": 420
            },
            "heroes": self._get_unique_heroes(),
            "assetsCount": len(self.assets)
        }

        with open(ds_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"[JSON] Created Design System JSON: {ds_path}")

    def _get_unique_heroes(self) -> List[dict]:
        """Возвращает список уникальных героев"""
        heroes = defaultdict(lambda: {"name": "", "assets": [], "faction": ""})

        for asset in self.assets:
            hero_id = asset.hero_id
            heroes[hero_id]["name"] = asset.hero_name
            heroes[hero_id]["assets"].append(asset.asset_type)
            heroes[hero_id]["faction"] = self._get_faction_tag(asset.hero_name)

        return [
            {
                "id": hero_id,
                "name": data["name"],
                "faction": data["faction"],
                "assetTypes": list(set(data["assets"]))
            }
            for hero_id, data in sorted(heroes.items())
        ]

    def generate_import_instructions(self) -> None:
        """Генерирует инструкции по импорту в Figma"""
        readme_path = self.output_dir / "README.md"

        content = """# Unmatched Design System - Figma Import Assets

> Подготовленные ассеты для импорта в Figma
>
> Дата создания: {date}

## 📁 Структура директорий

```
figma-ready/
├── design-system.json      # Design System токены
├── figma-import.csv        # Манифест для импорта
├── README.md               # Этот файл
├── heroes/                 # Ассеты героев
│   ├── avatars/           # 150×150px
│   ├── card-covers/       # 300×420px
│   └── minis/             # 100×100px
└── decks/                  # Игровые карты
```

## 🚀 Импорт в Figma

### Вариант 1: Drag & Drop (Простой)

1. Откройте Figma
2. Создайте новый файл "Unmatched Design System"
3. Создайте страницу "Assets"
4. Откройте папку `figma-ready/heroes` в проводнике
5. Перетащите файлы на холст Figma

### Вариант 2: Place Image с CSV

1. В Figma создайте структуру Frame'ов по героям
2. Используйте `figma-import.csv` как референс
3. Импортируйте файлы через `Place Image` (Ctrl+Shift+K)

### Вариант 3: Figma API (Автоматический)

Используйте `design-system.json` с Figma REST API для автоматического создания.

## 🎨 Design System Токены

### Цвета

{colors}

### Типографика

| Размер | px | Вес | Применение |
|--------|----|-----|------------|
| 3XL    | 40 | 900 | Основные заголовки |
| 2XL    | 32 | 700 | Имена героев |
| XL     | 24 | 700 | Заголовки карточек |
| LG     | 18 | 500 | Подзаголовки |
| Base   | 14 | 400 | Основной текст |
| SM     | 12 | 400 | Второстепенный текст |
| XS     | 10 | 400 | Мелкие метки |

### Размеры карточек

- **Игровая карта**: 300 × 420 px
- **Аватар героя**: 150 × 150 px
- **Миниатюра**: 100 × 100 px

## 📊 Статистика

- **Всего ассетов**: {count}
- **Уникальных героев**: {heroes}

## 🔗 Следующие шаги

1. Создайте Local Styles в Figma на основе `design-system.json`
2. Импортируйте ассеты
3. Создайте компоненты карточек (Card/Action, Card/Hero)
4. Свяжите ассеты с компонентами

---
""".format(
            date="2026-01-31",
            colors="\\n".join([f"- **{c.name}**: `{c.hex}` ({c.category})" for c in self.colors[:10]]),
            count=len(self.assets),
            heroes=len(self._get_unique_heroes())
        )

        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"[README] Created README: {readme_path}")

    def export_all(self) -> None:
        """Выполняет полный экспорт"""
        sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None
        print("[START] Exporting assets for Figma...")
        print()

        self.scan_assets()
        self.copy_assets()
        self.generate_figma_csv()
        self.generate_design_system_json()
        self.generate_import_instructions()

        print()
        print("[DONE] Export completed!")
        print(f"[DIR] Output directory: {self.output_dir}")
        print()
        print("[FILES] Import files:")
        print(f"   - {self.output_dir / 'figma-import.csv'}")
        print(f"   - {self.output_dir / 'design-system.json'}")
        print(f"   - {self.output_dir / 'README.md'}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Экспорт ассетов Unmatched для Figma")
    parser.add_argument(
        "--input",
        default="../../scraped-data/images",
        help="Директория с исходными ассетами"
    )
    parser.add_argument(
        "--output",
        default="./figma-ready",
        help="Директория для экспорта"
    )

    args = parser.parse_args()

    exporter = FigmaAssetExporter(args.input, args.output)
    exporter.export_all()


if __name__ == "__main__":
    main()
