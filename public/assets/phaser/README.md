# Phaser Assets

Эта директория содержит активы для Phaser движка.

## Структура

```
assets/phaser/
├── board-placeholder.png      # Placeholder для игрового поля
├── fighter-placeholder.png    # Placeholder для бойцов
├── card-placeholder.png       # Placeholder для лицевой стороны карт
├── card-back-placeholder.png  # Placeholder для обратной стороны карт
└── zones/
    ├── blue.png               # Синяя зона
    ├── green.png              # Зелёная зона
    ├── yellow.png             # Жёлтая зона
    ├── red.png                # Красная зона
    └── purple.png             # Фиолетовая зона
```

## Требования к изображениям

### Игровое поле
- Размер: 1024x768 px
- Формат: PNG с прозрачностью
- Сетка: 8x8 клеток

### Бойцы
- Размер спрайта: 64x64 px на кадр
- Формат: Spritesheet PNG
- Кадры: idle (4), walk (4), attack (4), hit (2), defeat (4)

### Карты
- Размер: 120x180 px
- Формат: PNG
- Рубашка: единая для всех карт

## TODO

Создать placeholder изображения с помощью Canvas или SVG генератора.
