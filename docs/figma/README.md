# Figma Design System

Документация и ассеты для создания дизайна в Figma.

## 📁 Структура

```
docs/figma/
├── README.md                    # Этот файл
├── FIGMA_PLUGIN_GUIDE.md        # Инструкция по плагину
├── design-system.json           # Токены Design System
├── design-system-preview.html   # HTML превью
├── UnmatchedDesignSystem.ts     # Код плагина Figma
├── generate_svg_cards.py        # Генератор SVG карточек
├── figma_api_designer.py        # Figma API клиент
├── figma_exporter.py            # Экспортёр ассетов
├── figma-generated/             # Сгенерированные файлы
│   ├── svg-cards/               # SVG карточки для импорта
│   └── cards/                   # PNG карточки
└── figma-ready/                 # Экспортированные ассеты (1791 файл)
```

## 🚀 Быстрый старт

### Вариант 1: SVG карточки (рекомендуется)

1. Откройте папку `figma-generated/svg-cards/`
2. В Figma: **File → Place Image** (Ctrl+Shift+K)
3. Выберите SVG файлы

### Вариант 2: Плагин Figma

1. **Plugins → Development → New plugin**
2. Скопируйте код из `UnmatchedDesignSystem.ts`
3. Запустите плагин

## 📦 Дизайн токены

### Цвета
- Primary: Yellow (#FFD700), Purple (#6B4C9A), Red (#DC143C), Blue (#1E3A8A)
- Фракции: Marvel, Witcher, Historical, Jurassic, TMNT

### Размеры карточек
- Игровая карта: 300 × 420 px
- Аватар: 150 × 150 px
- Миниатюра: 100 × 100 px

## 📝 Скрипты

```bash
# Сгенерировать SVG карточки
python generate_svg_cards.py

# Экспортировать все ассеты
python figma_exporter.py --input "../../scraped-data/images" --output "./figma-ready"
```

## 🔗 Ссылки

- [Figma API](https://www.figma.com/developers/api)
- [Figma Plugins](https://www.figma.com/community/plugin)
