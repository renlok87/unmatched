// ============================================================
// ASSET LOADER - Управление загрузкой игровых активов
// ============================================================

import type { FighterAssetConfig, CardAssetConfig, BoardAssetConfig } from '../types';

// ------------------------------------------------------------
// Манифесты активов
// ------------------------------------------------------------

/**
 * Реестр всех активов героев
 */
export const FIGHTER_ASSETS: Record<string, FighterAssetConfig> = {
  'ms-marvel': {
    id: 'ms-marvel',
    name: 'Ms. Marvel',
    spriteKey: 'fighter-ms-marvel',
    portraitKey: 'portrait-ms-marvel',
    scale: 1.0,
    frameWidth: 64,
    frameHeight: 64,
  },
  daredevil: {
    id: 'daredevil',
    name: 'Daredevil',
    spriteKey: 'fighter-daredevil',
    portraitKey: 'portrait-daredevil',
    scale: 1.0,
    frameWidth: 64,
    frameHeight: 64,
  },
  // TODO: Добавить остальных героев
};

/**
 * Реестр всех активов карт
 */
export const CARD_ASSETS: Record<string, CardAssetConfig> = {
  'rapid-punch': {
    id: 'rapid-punch',
    name: 'Rapid Punch',
    spriteKey: 'card-rapid-punch',
    backSpriteKey: 'card-back',
    width: 60,
    height: 90,
  },
  'big-strength': {
    id: 'big-strength',
    name: 'Big Strength',
    spriteKey: 'card-big-strength',
    backSpriteKey: 'card-back',
    width: 60,
    height: 90,
  },
  // TODO: Добавить остальные карты
};

/**
 * Реестр всех активов полей
 */
export const BOARD_ASSETS: Record<string, BoardAssetConfig> = {
  'cobalt-city': {
    id: 'cobalt-city',
    name: 'Cobalt City',
    backgroundKey: 'board-cobalt-city',
    spaces: [],
  },
  'festering-grounds': {
    id: 'festering-grounds',
    name: 'Festering Grounds',
    backgroundKey: 'board-festering-grounds',
    spaces: [],
  },
  // TODO: Добавить остальные поля
};

// ------------------------------------------------------------
// Вспомогательные функции
// ------------------------------------------------------------

/**
 * Получает конфигурацию актива для героя
 */
export function getFighterAsset(heroId: string): FighterAssetConfig | null {
  return FIGHTER_ASSETS[heroId] || null;
}

/**
 * Получает конфигурацию актива для карты
 */
export function getCardAsset(cardId: string): CardAssetConfig | null {
  // Извлекаем базовый ID из ID карты (убираем суффиксы типа -1, -2)
  const baseId = cardId.split('-')[0];
  return CARD_ASSETS[baseId] || null;
}

/**
 * Получает конфигурацию актива для поля
 */
export function getBoardAsset(boardId: string): BoardAssetConfig | null {
  return BOARD_ASSETS[boardId] || null;
}

/**
 * Загружает активы для указанного героя в Phaser сцену
 */
export function loadHeroAssets(
  scene: Phaser.Scene,
  heroId: string
): Promise<void> {
  return new Promise((resolve, reject) => {
    const asset = getFighterAsset(heroId);
    if (!asset) {
      reject(new Error(`Актив для героя ${heroId} не найден`));
      return;
    }

    // Проверяем, уже загружен ли актив
    if (scene.textures.exists(asset.spriteKey)) {
      resolve();
      return;
    }

    // Загружаем spritesheet с анимациями
    scene.load.spritesheet(asset.spriteKey, `/assets/fighters/${heroId}.png`, {
      frameWidth: asset.frameWidth,
      frameHeight: asset.frameHeight,
    });

    // Загружаем портрет
    scene.load.image(asset.portraitKey, `/assets/portraits/${heroId}.png`);

    // Ждём завершения загрузки
    scene.load.once('complete', () => resolve());
    scene.load.start();
  });
}

/**
 * Загружает активы для нескольких героев
 */
export function loadMultipleHeroAssets(
  scene: Phaser.Scene,
  heroIds: string[]
): Promise<void[]> {
  return Promise.all(heroIds.map(id => loadHeroAssets(scene, id)));
}

/**
 * Загружает активы для игрового поля
 */
export function loadBoardAssets(
  scene: Phaser.Scene,
  boardId: string
): Promise<void> {
  return new Promise((resolve, reject) => {
    const asset = getBoardAsset(boardId);
    if (!asset) {
      reject(new Error(`Актив для поля ${boardId} не найден`));
      return;
    }

    // Проверяем, уже загружен ли актив
    if (scene.textures.exists(asset.backgroundKey)) {
      resolve();
      return;
    }

    // Загружаем изображение поля
    scene.load.image(asset.backgroundKey, `/assets/boards/${boardId}.png`);

    // Ждём завершения загрузки
    scene.load.once('complete', () => resolve());
    scene.load.start();
  });
}

/**
 * Создаёт анимации для бойца
 */
export function createFighterAnimations(
  scene: Phaser.Scene,
  heroId: string
): void {
  const asset = getFighterAsset(heroId);
  if (!asset) return;

  const frameWidth = asset.frameWidth;
  const frameHeight = asset.frameHeight;

  // Анимация простоя (idle)
  if (!scene.anims.exists(`${heroId}-idle`)) {
    scene.anims.create({
      key: `${heroId}-idle`,
      frames: scene.anims.generateFrameNumbers(asset.spriteKey, {
        start: 0,
        end: 3,
      }),
      frameRate: 8,
      repeat: -1,
    });
  }

  // Анимация ходьбы
  if (!scene.anims.exists(`${heroId}-walk`)) {
    scene.anims.create({
      key: `${heroId}-walk`,
      frames: scene.anims.generateFrameNumbers(asset.spriteKey, {
        start: 4,
        end: 7,
      }),
      frameRate: 12,
      repeat: -1,
    });
  }

  // Анимация атаки
  if (!scene.anims.exists(`${heroId}-attack`)) {
    scene.anims.create({
      key: `${heroId}-attack`,
      frames: scene.anims.generateFrameNumbers(asset.spriteKey, {
        start: 8,
        end: 11,
      }),
      frameRate: 16,
      repeat: 0,
    });
  }

  // Анимация получения удара
  if (!scene.anims.exists(`${heroId}-hit`)) {
    scene.anims.create({
      key: `${heroId}-hit`,
      frames: scene.anims.generateFrameNumbers(asset.spriteKey, {
        start: 12,
        end: 13,
      }),
      frameRate: 8,
      repeat: 0,
    });
  }

  // Анимация поражения
  if (!scene.anims.exists(`${heroId}-defeat`)) {
    scene.anims.create({
      key: `${heroId}-defeat`,
      frames: scene.anims.generateFrameNumbers(asset.spriteKey, {
        start: 14,
        end: 17,
      }),
      frameRate: 8,
      repeat: 0,
    });
  }
}
