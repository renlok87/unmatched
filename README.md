# Unmatched Digital Edition

> Цифровая версия настольной карточной игры Unmatched

![TypeScript](https://img.shields.io/badge/TypeScript-5.6-blue)
![React](https://img.shields.io/badge/React-18-blue)
![Vite](https://img.shields.io/badge/Vite-6.0-purple)

## 🎮 О игре

**Unmatched** — это настольная карточная игра с асимметричными героями, уникальными колодами и тактическим боем. Каждый герой имеет свои способности и стиль игры.

### Особенности реализации

- **Zone-based движение** — бойцы перемещаются по цветным зонам
- **Система боя** — атака и защита с одновременным вскрытием карт
- **Уникальные герои** — Ms. Marvel, Daredevil и другие
- **Hot-seat режим** — игра вдвоём на одном устройстве

## 🚀 Быстрый старт

```bash
# Установка зависимостей
npm install

# Запуск dev сервера
npm run dev

# Сборка для продакшн
npm run build
```

Откройте [http://localhost:5173](http://localhost:5173) в браузере.

## 📁 Структура проекта

```
unmached/
├── src/
│   ├── core/                    # Игровой движок (чистая логика)
│   │   ├── models/              # TypeScript типы и модели
│   │   ├── engine/              # Игровая логика
│   │   └── data/                # Данные героев и досок
│   ├── store/                   # Zustand state management
│   ├── components/              # React компоненты UI
│   └── hooks/                   # Custom React hooks
```

## 🎯 Реализованные механики

- ✅ 2 действия за ход (Maneuver, Scheme, Attack)
- ✅ Zone-based перемещение по доске
- ✅ Система боя с атакой и защитой
- ✅ 2 героя: Ms. Marvel и Daredevil
- ✅ 1 доска: Cobble City

## 📋 TODO

См. [TODO.md](TODO.md) для полного списка задач.

## 🛠️ Технологии

- **React 18** — UI библиотека
- **TypeScript** — типизация
- **Vite** — сборщик
- **Zustand** — state management
- **CSS Modules** — стилизация

## 📄 Лицензия

MIT

## 👏 Acknowledgments

- [Restoration Games](https://restorationgames.com/) — создатели Unmatched
- [Unmatched Cards](https://unmatched.cards/) — база данных карт
