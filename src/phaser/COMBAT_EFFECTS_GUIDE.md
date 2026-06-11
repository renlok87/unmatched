# Combat & Effects - Руководство по использованию

## Обзор

Фаза 3 добавляет в Phaser фронтенд систему боевых анимаций, визуальных эффектов и UI для отображения боя.

## Структура

```
src/phaser/
├── animations/
│   ├── FighterAnimations.ts    # Базовые анимации бойца
│   ├── CombatAnimations.ts     # Боевые анимации
│   └── index.ts
├── effects/
│   ├── ParticleSystem.ts       # Система частиц
│   ├── ScreenEffects.ts        # Эффекты экрана
│   └── index.ts
├── sprites/
│   ├── FighterSprite.ts        # Расширенный спрайт бойца
│   └── index.ts
├── ui/
│   ├── CombatUI.ts             # UI боя
│   └── index.ts
└── scenes/
    ├── BootScene.ts            # Предзагрузка
    └── GameScene.ts            # Основная сцена
```

## Использование

### Инициализация систем в GameScene

```typescript
import { FighterAnimations, CombatAnimations, ParticleSystem, ScreenEffects, CombatUI } from '@/phaser';

class GameScene extends Phaser.Scene {
  private fighterAnimations: FighterAnimations;
  private combatAnimations: CombatAnimations;
  private particles: ParticleSystem;
  private screenEffects: ScreenEffects;
  private combatUI: CombatUI;

  create() {
    // Инициализация систем
    this.screenEffects = new ScreenEffects(this, this.cameras.main);
    this.particles = new ParticleSystem(this);
    this.combatUI = new CombatUI(this);
    this.fighterAnimations = new FighterAnimations(this);
    this.combatAnimations = new CombatAnimations(this, this.screenEffects, this.particles);
  }
}
```

### Анимация атаки

```typescript
// Простая атака
await this.combatAnimations.playAttack(
  attackerSprite,
  targetSprite,
  AttackType.MELEE,
  { wasBlocked: false, damageDealt: 5, wasCritical: false }
);

// Критическая атака
await this.combatAnimations.playAttack(
  attackerSprite,
  targetSprite,
  AttackType.CRITICAL,
  { wasBlocked: false, damageDealt: 10, wasCritical: true }
);

// Дальнобойная атака
await this.combatAnimations.playAttack(
  attackerSprite,
  targetSprite,
  AttackType.RANGED
);
```

### Эффекты частиц

```typescript
// Частицы урона
this.particles.emitDamage(x, y, damageAmount);

// Частицы лечения
this.particles.emitHeal(x, y, healAmount);

// Розыгрыш карты
this.particles.emitCardPlay(x, y);

// Вытягивание карты
this.particles.emitCardDraw(x, y);

// Активация зоны
this.particles.emitZoneActivation(x, y, 'blue');

// Произвольный всплеск
this.particles.emitBurst(x, y, 0xff0000, 20);

// Статусные эффекты
this.particles.emitStatusEffect(x, y, 'poison');  // poison, burn, shield, stun, buff
```

### Эффекты экрана

```typescript
// Тряска экрана
this.screenEffects.shake(0.02, 300);  // intensity, duration

// Вспышка
this.screenEffects.flash(0xff0000, 150);  // color, duration

// Множественные вспышки (молнии)
this.screenEffects.multiFlash(3, 80, 0xffffff);

// Затемнение
await this.screenEffects.fadeOut(500);
await this.screenEffects.fadeIn(500);

// Переход
await this.screenEffects.fadeTransition(500, 200);

// Замедление времени
this.screenEffects.setSlowMotion(true, 0.5);  // enabled, factor
this.screenEffects.setSlowMotion(false);

// Bullet time эффект
await this.screenEffects.bulletTime(0.2, 500, 1000);

// Zoom эффекты
await this.screenEffects.zoom(1.5, 500);
this.screenEffects.impactZoom(1.2);

// Комбо эффекты
this.screenEffects.heavyHit(0.5);
this.screenEffects.criticalHit();
this.screenEffects.victoryEffect();
await this.screenEffects.defeatEffect();
```

### Combat UI

```typescript
// Всплывающие числа
this.combatUI.showFloatingNumber({
  x: sprite.x,
  y: sprite.y - 40,
  value: 5,
  isHeal: false,
  isCritical: true,
});

// Полоски здоровья
this.combatUI.createHealthBar(fighterId, x, y, width, maxHealth);
this.combatUI.updateHealth(fighterId, currentHealth, maxHealth, true);

// Лог боя
this.combatUI.logAttack(attackerName, targetName, damage);
this.combatUI.logBlock(defenderName, blockedAmount);
this.combatUI.logHeal(targetName, healAmount);
this.combatUI.logDeath(fighterName);
this.combatUI.logEffect('Активирована способность', '⭐');

// Индикаторы
this.combatUI.showTurnIndicator(playerName);
this.combatUI.showActionPrompt('Выберите цель для атаки', 0);

// Иконки статусов
this.combatUI.addStatusIcon(fighterId, 'poison', '☠️', 3);
this.combatUI.updateStatusDuration(fighterId, 'poison', 2);
this.combatUI.clearStatusIcons(fighterId);
```

### FighterSprite

```typescript
import { FighterSprite, FighterAnimationState } from '@/phaser';

// Создание спрайта
const sprite = new FighterSprite(this.scene, {
  fighter: fighterData,
  x: worldX,
  y: worldY,
  scale: 1,
});

// Обновление здоровья
sprite.updateHealth(newHealth, true);

// Выделение
sprite.setSelected(true, 0x4ecca3);

// Анимации
sprite.playAnimation(FighterAnimationState.ATTACK);
sprite.playAnimation(FighterAnimationState.HIT);
sprite.playAnimation(FighterAnimationState.DEATH);

// Модификаторы
sprite.addDamageBoost(2);
sprite.addDamageReduction(1);
sprite.clearModifiers();
```

## Типы атак

| Тип | Описание |
|-----|----------|
| `AttackType.MELEE` | Ближний бой - выпад вперёд |
| `AttackType.RANGED` | Дальний бой - снаряд |
| `AttackType.MAGIC` | Магическая атака - магический снаряд |
| `AttackType.EXPLOSIVE` | Взрывная атака - волна огня |
| `AttackType.HEAVY` | Тяжёлая атака - медленный мощный удар |
| `AttackType.CRITICAL` | Критический удар - быстрый с эффектами |

## Статусные эффекты для частиц

| Тип | Описание |
|-----|----------|
| `poison` | Зелёные пузыри, поднимающиеся вверх |
| `burn` | Огненные частицы |
| `shield` | Синее свечение щита |
| `stun` | Жёлтые звёздочки |
| `buff` | Золотое свечение |

## Константы

```typescript
// Цвета подсветки
HighlightColors.VALID_MOVE = 0x4ecca3    // Зелёный
HighlightColors.ATTACK_TARGET = 0xff6b6b // Красный
HighlightColors.SELECTED = 0xffd93d      // Жёлтый
HighlightColors.HOVER = 0x6c5ce7         // Фиолетовый
```

## Интеграция с React

События для коммуникации между React и Phaser:

```typescript
// От Phaser к React
PhaserGameEvent:
  - { type: 'COMBAT_ANIMATION_COMPLETE'; combatId: string }
  - { type: 'DAMAGE_APPLIED'; fighterId: string; damage: number }
  - { type: 'FIGHTER_DEFEATED'; fighterId: string }
  - { type: 'ZONE_ACTIVATED'; zoneId: string }

// От React к Phaser
ReactToPhaserEvent:
  - { type: 'PLAY_ATTACK_ANIMATION'; attackerId: string; targetId: string; attackType?: string; result?: CombatResult }
  - { type: 'PLAY_DEFEND_ANIMATION'; defenderId: string; blocked: boolean }
  - { type: 'PLAY_DEATH_ANIMATION'; fighterId: string }
  - { type: 'SHOW_FLOATING_NUMBER'; fighterId: string; value: number; isHeal?: boolean; isCritical?: boolean }
```
