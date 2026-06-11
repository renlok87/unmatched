# Unmatched Design System - Figma Import Assets

> Подготовленные ассеты для импорта в Figma
>
> Дата создания: 2026-01-31

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

- **Primary Yellow**: `#FFD700` (primary)\n- **Primary Purple**: `#6B4C9A` (primary)\n- **Primary Red**: `#DC143C` (primary)\n- **Primary Blue**: `#1E3A8A` (primary)\n- **Neutral Black**: `#000000` (neutral)\n- **Dark Gray**: `#1F1F1F` (neutral)\n- **Gray**: `#808080` (neutral)\n- **Light Gray**: `#D3D3D3` (neutral)\n- **White**: `#FFFFFF` (neutral)\n- **Energy**: `#FF6B35` (semantic)

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

- **Всего ассетов**: 1791
- **Уникальных героев**: 1691

## 🔗 Следующие шаги

1. Создайте Local Styles в Figma на основе `design-system.json`
2. Импортируйте ассеты
3. Создайте компоненты карточек (Card/Action, Card/Hero)
4. Свяжите ассеты с компонентами

---
