import * as Phaser from 'phaser';
import type {
  BoardDefinition,
  BoardSpace,
  CardInstance,
  Fighter,
  GameState,
  Player,
  Position,
  Zone,
} from '../../core/models/types';
import type { PhaserGameEvent, PhaserGameState, ReactToPhaserEvent } from '../types';
import { ReplaySystem, type GameReplay } from '../systems';
import { getBoardArtAsset, getCardArtAsset } from '../assets/gameAssetManifest';

interface HeroVisual {
  id: string;
  name: string;
  miniKey: string;
  avatarKey: string;
  coverKey: string;
  accent: number;
}

const HERO_VISUALS: Record<string, HeroVisual> = {
  'ms-marvel': {
    id: 'ms-marvel',
    name: 'Ms. Marvel',
    miniKey: 'hero-mini-ms-marvel',
    avatarKey: 'hero-avatar-ms-marvel',
    coverKey: 'hero-cover-ms-marvel',
    accent: 0xd7b84b,
  },
  daredevil: {
    id: 'daredevil',
    name: 'Daredevil',
    miniKey: 'hero-mini-daredevil',
    avatarKey: 'hero-avatar-daredevil',
    coverKey: 'hero-cover-daredevil',
    accent: 0xb23a48,
  },
};

const FALLBACK_HERO: HeroVisual = {
  id: 'fallback',
  name: 'Hero',
  miniKey: 'hero-mini-ms-marvel',
  avatarKey: 'hero-avatar-ms-marvel',
  coverKey: 'hero-cover-ms-marvel',
  accent: 0x4ecca3,
};

const ZONE_COLORS: Record<Zone, number> = {
  blue: 0x3286d9,
  green: 0x48a76a,
  yellow: 0xd7b84b,
  red: 0xb23a48,
  purple: 0x7b5ac8,
  brown: 0x92400e,
  gray: 0x6b7280,
  orange: 0xf97316,
  pink: 0xec4899,
  white: 0xe5e7eb,
  gold: 0xd4af37,
  beige: 0xd6c8a8,
};

const HUD = {
  ink: 0x040711,
  surface: 0x08101d,
  surfaceRaised: 0x111827,
  line: 0xf2b84b,
  lineDim: 0x4b5875,
  cyan: 0x00d4ff,
  gold: 0xffc84a,
  red: 0xff3f4f,
  purple: 0x9c55ff,
  text: '#fff4c7',
  mutedText: '#9fb0ca',
};

interface ComicPanelOptions {
  fill?: number;
  alpha?: number;
  cut?: number;
  lineAlpha?: number;
  inner?: boolean;
}

export class GameScene extends Phaser.Scene {
  private gameState: PhaserGameState;

  private boardContainer: Phaser.GameObjects.Container | null = null;
  private fightersContainer: Phaser.GameObjects.Container | null = null;
  private cardsContainer: Phaser.GameObjects.Container | null = null;
  private highlightsContainer: Phaser.GameObjects.Container | null = null;
  private effectsContainer: Phaser.GameObjects.Container | null = null;
  private hudContainer: Phaser.GameObjects.Container | null = null;

  private fighterSprites: Map<string, Phaser.GameObjects.Container> = new Map();
  private spaceHighlights: Map<string, Phaser.GameObjects.GameObject> = new Map();
  private cardSprites: Map<string, Phaser.GameObjects.Container> = new Map();
  private pendingRuntimeTextures: Set<string> = new Set();

  private readonly SPACE_SIZE = 72;
  private readonly BOARD_TOP = 130;
  private readonly BOARD_PADDING = 16;
  private readonly CARD_WIDTH = 58;
  private readonly CARD_HEIGHT = 84;

  private onGameEvent: (event: PhaserGameEvent) => void;

  private replaySystem: ReplaySystem | null = null;

  constructor(onGameEvent: (event: PhaserGameEvent) => void) {
    super({ key: 'GameScene', active: true });
    this.onGameEvent = onGameEvent;
    this.gameState = {
      gameState: null,
      selectedFighterId: null,
      selectedCardId: null,
      highlightedSpaces: [],
      showGrid: true,
      showZones: true,
      debugMode: false,
    };
  }

  create(): void {
    this.setupCamera();
    this.createContainers();
    this.createBoard();
    this.renderHUD();
    this.setupEvents();
    this.setupReplaySystem();
    this.onGameEvent({ type: 'PHASER_READY' });
  }

  update(): void {
    // Animations are driven by tweens and React state updates.
  }

  private setupCamera(): void {
    this.cameras.main.setBackgroundColor(0x111522);
    this.cameras.main.centerOn(400, 300);
  }

  private createContainers(): void {
    this.boardContainer = this.add.container(0, 0).setDepth(0);
    this.highlightsContainer = this.add.container(0, 0).setDepth(1);
    this.fightersContainer = this.add.container(0, 0).setDepth(2);
    this.cardsContainer = this.add.container(0, 0).setDepth(3);
    this.effectsContainer = this.add.container(0, 0).setDepth(4);
    this.hudContainer = this.add.container(0, 0).setDepth(10);
  }

  private setupEvents(): void {
    this.input.on('pointerdown', this.handleSceneClick, this);
    this.game.events.on('react-to-phaser', this.handleReactEvent, this);
    this.events.once(Phaser.Scenes.Events.SHUTDOWN, () => {
      this.game.events.off('react-to-phaser', this.handleReactEvent, this);
    });
  }

  private drawComicPanel(
    target: Phaser.GameObjects.Container,
    x: number,
    y: number,
    width: number,
    height: number,
    accent: number,
    options: ComicPanelOptions = {}
  ): Phaser.GameObjects.Graphics {
    const cut = options.cut ?? 16;
    const fill = options.fill ?? HUD.surface;
    const alpha = options.alpha ?? 0.94;
    const points = [
      new Phaser.Math.Vector2(x + cut, y),
      new Phaser.Math.Vector2(x + width - cut, y),
      new Phaser.Math.Vector2(x + width, y + cut),
      new Phaser.Math.Vector2(x + width, y + height - cut),
      new Phaser.Math.Vector2(x + width - cut, y + height),
      new Phaser.Math.Vector2(x + cut, y + height),
      new Phaser.Math.Vector2(x, y + height - cut),
      new Phaser.Math.Vector2(x, y + cut),
    ];

    const shadow = points.map(point => new Phaser.Math.Vector2(point.x + 4, point.y + 5));
    const graphics = this.add.graphics();

    graphics.fillStyle(HUD.ink, 0.72);
    graphics.fillPoints(shadow, true, true);
    graphics.fillGradientStyle(fill, fill, HUD.ink, HUD.ink, alpha, alpha, alpha, alpha);
    graphics.fillPoints(points, true, true);
    graphics.lineStyle(5, HUD.ink, 0.95);
    graphics.strokePoints(points, true, true);
    graphics.lineStyle(2, accent, options.lineAlpha ?? 0.92);
    graphics.strokePoints(points, true, true);

    if (options.inner !== false) {
      const inset = 7;
      const innerPoints = [
        new Phaser.Math.Vector2(x + cut, y + inset),
        new Phaser.Math.Vector2(x + width - cut, y + inset),
        new Phaser.Math.Vector2(x + width - inset, y + cut),
        new Phaser.Math.Vector2(x + width - inset, y + height - cut),
        new Phaser.Math.Vector2(x + width - cut, y + height - inset),
        new Phaser.Math.Vector2(x + cut, y + height - inset),
        new Phaser.Math.Vector2(x + inset, y + height - cut),
        new Phaser.Math.Vector2(x + inset, y + cut),
      ];
      graphics.lineStyle(1, HUD.line, 0.48);
      graphics.strokePoints(innerPoints, true, true);
    }

    graphics.lineStyle(3, accent, 0.78);
    graphics.lineBetween(x + cut + 8, y + 6, x + Math.min(width * 0.44, width - cut - 12), y + 6);
    graphics.lineStyle(2, HUD.gold, 0.6);
    graphics.lineBetween(x + width - Math.min(width * 0.22, 90), y + height - 6, x + width - cut - 10, y + height - 6);

    target.add(graphics);
    return graphics;
  }

  private drawHudBar(
    target: Phaser.GameObjects.Container,
    x: number,
    y: number,
    width: number,
    height: number,
    ratio: number,
    color: number,
    stroke = HUD.lineDim
  ): void {
    const clamped = Phaser.Math.Clamp(ratio, 0, 1);
    const bg = this.add.rectangle(x, y, width, height, HUD.ink, 0.88).setOrigin(0, 0.5);
    bg.setStrokeStyle(1, stroke, 0.72);
    const fill = this.add.rectangle(x + 2, y, Math.max((width - 4) * clamped, 2), height - 4, color, 0.96).setOrigin(0, 0.5);
    const shine = this.add.rectangle(x + 2, y - height * 0.22, Math.max((width - 4) * clamped, 2), 1, 0xffffff, 0.28).setOrigin(0, 0.5);
    target.add([bg, fill, shine]);
  }

  private drawCardSlot(
    target: Phaser.GameObjects.Container,
    x: number,
    y: number,
    width: number,
    height: number,
    accent: number,
    filled = false
  ): void {
    this.drawComicPanel(target, x - width / 2, y - height / 2, width, height, accent, {
      fill: filled ? 0x101827 : 0x20242d,
      alpha: filled ? 0.95 : 0.58,
      cut: 8,
      inner: true,
      lineAlpha: filled ? 0.9 : 0.45,
    });
  }

  private drawMiniCardBack(
    target: Phaser.GameObjects.Container,
    x: number,
    y: number,
    width: number,
    height: number,
    accent: number,
    rotation = 0
  ): Phaser.GameObjects.Container {
    const card = this.add.container(x, y);
    card.setRotation(rotation);
    this.drawComicPanel(card, -width / 2, -height / 2, width, height, accent, {
      fill: 0x090d17,
      alpha: 0.98,
      cut: 7,
    });

    const star = this.add.star(0, -2, 4, width * 0.08, width * 0.24, accent, 0.92);
    star.setStrokeStyle(1, 0xffffff, 0.35);
    const mesh = this.add.rectangle(0, 0, width - 12, height - 12, 0x000000, 0);
    mesh.setStrokeStyle(1, HUD.lineDim, 0.45);
    card.add([mesh, star]);
    target.add(card);
    return card;
  }

  createBoard(): void {
    if (!this.boardContainer) return;

    this.boardContainer.removeAll(true);

    const board = this.getBoardDefinition();
    const metrics = this.getBoardMetrics();
    const boardW = metrics.width * metrics.cell;
    const boardH = metrics.height * metrics.cell;

    const table = this.add.rectangle(400, 300, 800, 600, HUD.ink, 1);
    this.boardContainer.add(table);

    if (this.textures.exists('hud-board-vignette')) {
      const vignette = this.add.image(400, 300, 'hud-board-vignette');
      vignette.setDisplaySize(800, 600);
      vignette.setAlpha(0.5);
      this.boardContainer.add(vignette);
    }

    this.drawComicPanel(
      this.boardContainer,
      metrics.x - this.BOARD_PADDING - 4,
      metrics.y - this.BOARD_PADDING - 4,
      boardW + this.BOARD_PADDING * 2 + 8,
      boardH + this.BOARD_PADDING * 2 + 8,
      HUD.cyan,
      { fill: 0x0a111d, alpha: 0.96, cut: 22 }
    );

    const boardArtKey = this.getBoardTextureKey(board);
    if (boardArtKey) {
      const art = this.add.image(metrics.x + boardW / 2, metrics.y + boardH / 2, boardArtKey);
      art.setDisplaySize(boardW + this.BOARD_PADDING * 2, boardH + this.BOARD_PADDING * 2);
      art.setAlpha(0.72);
      this.boardContainer.add(art);
    }

    if (this.textures.exists('hud-board-frame-6x4')) {
      const frame = this.add.image(metrics.x + boardW / 2, metrics.y + boardH / 2, 'hud-board-frame-6x4');
      frame.setDisplaySize(boardW + 44, boardH + 44);
      frame.setAlpha(0.9);
      this.boardContainer.add(frame);
    }

    for (let y = 0; y < metrics.height; y++) {
      for (let x = 0; x < metrics.width; x++) {
        this.createSpace(x, y, board?.spaces.find(space => space.position.x === x && space.position.y === y));
      }
    }

    const boardName = this.add.text(metrics.x, metrics.y - 32, board?.name || 'Cobble City', {
      fontFamily: 'Arial, sans-serif',
      fontSize: '16px',
      color: HUD.text,
      fontStyle: 'bold',
      stroke: '#05070d',
      strokeThickness: 3,
    });
    this.boardContainer.add(boardName);
  }

  private createSpace(x: number, y: number, space?: BoardSpace): void {
    if (!this.boardContainer) return;

    const metrics = this.getBoardMetrics();
    const pos = this.gridToWorld({ x, y });
    const zones = space?.zones?.length ? space.zones : this.getFallbackZones(x, y);
    const fill = ZONE_COLORS[zones[0]] ?? 0x2f3a54;

    const rect = this.add.rectangle(pos.x, pos.y, metrics.cell - 4, metrics.cell - 4, 0x000000, 0.04);
    rect.setStrokeStyle(2, 0xffffff, 0.52);
    rect.setInteractive({ useHandCursor: true });
    rect.on('pointerdown', () => {
      this.onGameEvent({ type: 'SPACE_CLICKED', position: { x, y } });
    });
    this.boardContainer.add(rect);

    const node = this.add.circle(pos.x, pos.y, metrics.cell * 0.31, fill, 0.22);
    node.setStrokeStyle(2, fill, 0.82);
    this.boardContainer.add(node);

    if (this.gameState.showZones) {
      zones.slice(0, 2).forEach((zone, index) => {
        const swatch = this.add.circle(
          pos.x - metrics.cell / 2 + 12 + index * 13,
          pos.y - metrics.cell / 2 + 12,
          5,
          ZONE_COLORS[zone],
          0.95
        );
        swatch.setStrokeStyle(1, 0xffffff, 0.5);
        this.boardContainer?.add(swatch);
      });
    }

    if (space?.isObstacle) {
      const obstacle = this.add.rectangle(pos.x, pos.y, 28, 28, 0x0d101a, 0.7);
      obstacle.setRotation(Math.PI / 4);
      obstacle.setStrokeStyle(1, 0x9aa4bd, 0.8);
      this.boardContainer.add(obstacle);
    }
  }

  createFighters(fighters: Fighter[]): void {
    this.fighterSprites.forEach(sprite => sprite.destroy());
    this.fighterSprites.clear();

    fighters.forEach(fighter => {
      if (!fighter.isDefeated) {
        this.createFighter(fighter);
      }
    });
  }

  private createFighter(fighter: Fighter): void {
    if (!this.fightersContainer) return;

    const pos = this.gridToWorld(fighter.position);
    const visual = this.getHeroVisual(fighter.definitionId);
    const size = fighter.type === 'sidekick' ? 48 : 62;
    const container = this.add.container(pos.x, pos.y);

    const shadow = this.add.ellipse(2, 24, size * 0.9, 16, 0x05070d, 0.45);
    const ring = this.add.graphics();
    ring.lineStyle(5, visual.accent, 0.95);
    ring.strokeCircle(0, -2, size / 2 + 10);
    ring.lineStyle(2, 0xffffff, 0.55);
    ring.strokeCircle(0, -2, size / 2 + 15);
    ring.fillStyle(visual.accent, 0.28);
    ring.fillCircle(0, -2, size / 2 + 6);
    ring.setVisible(this.gameState.selectedFighterId === fighter.id);

    const base = this.add.circle(0, 0, size / 2 + 3, 0x10131d, 0.94);
    base.setStrokeStyle(3, visual.accent, 0.78);

    const mini = this.add.image(0, -2, this.textureKeyOrFallback(visual.miniKey));
    mini.setDisplaySize(size, size);

    const hpRatio = Phaser.Math.Clamp(fighter.health / Math.max(fighter.maxHealth, 1), 0, 1);
    const hpBg = this.add.rectangle(0, -size / 2 - 10, size, 7, 0x080a0f, 0.9);
    const hpBar = this.add.rectangle(-size / 2, -size / 2 - 10, size * hpRatio, 5, this.getHpColor(hpRatio), 1);
    hpBar.setOrigin(0, 0.5);

    container.add([shadow, ring, base, mini, hpBg, hpBar]);
    container.setSize(size + 18, size + 22);
    container.setInteractive(new Phaser.Geom.Circle(0, 0, size / 2 + 10), Phaser.Geom.Circle.Contains);
    container.on('pointerdown', () => {
      this.handleFighterClick(fighter.id);
    });
    container.setData('selectionRing', ring);
    container.setData('fighterId', fighter.id);

    this.fightersContainer.add(container);
    this.fighterSprites.set(fighter.id, container);
  }

  createCards(cards: CardInstance[]): void {
    this.cardsContainer?.removeAll(true);
    this.cardSprites.clear();

    this.drawCardArea();

    cards.slice(0, 7).forEach((card, index) => {
      this.createCard(card, index, Math.min(cards.length, 7));
    });
  }

  private drawCardArea(): void {
    if (!this.cardsContainer) return;

    const state = this.gameState.gameState;
    const currentPlayer = this.getCurrentPlayer(state);

    this.drawComicPanel(this.cardsContainer, 40, 488, 720, 96, HUD.cyan, {
      fill: 0x080d17,
      alpha: 0.96,
      cut: 18,
    });

    const actionRail = this.add.rectangle(232, 489, 310, 3, HUD.cyan, 0.82).setOrigin(0, 0.5);
    const hotEdge = this.add.rectangle(536, 489, 170, 3, HUD.gold, 0.62).setOrigin(0, 0.5);
    this.cardsContainer.add([actionRail, hotEdge]);

    if (!currentPlayer) return;

    for (let i = 0; i < 7; i++) {
      this.drawCardSlot(this.cardsContainer, 196 + i * 68, 536, 48, 72, i % 2 === 0 ? HUD.cyan : HUD.gold);
    }

    this.drawMiniCardBack(this.cardsContainer, 696, 536, 48, 72, HUD.cyan);
    this.drawMiniCardBack(this.cardsContainer, 750, 536, 48, 72, HUD.red);

    const deckCount = this.add.text(696, 579, String(currentPlayer.deck.length), {
      fontFamily: 'Arial, sans-serif',
      fontSize: '14px',
      color: HUD.text,
      fontStyle: 'bold',
      stroke: '#070a12',
      strokeThickness: 3,
    });
    deckCount.setOrigin(0.5);

    const discardCount = this.add.text(750, 579, String(currentPlayer.discardPile.length), {
      fontFamily: 'Arial, sans-serif',
      fontSize: '14px',
      color: HUD.text,
      fontStyle: 'bold',
      stroke: '#070a12',
      strokeThickness: 3,
    });
    discardCount.setOrigin(0.5);

    this.cardsContainer.add([deckCount, discardCount]);
  }

  private createCard(card: CardInstance, index: number, visibleCount: number): void {
    if (!this.cardsContainer) return;

    const state = this.gameState.gameState;
    const currentPlayer = this.getCurrentPlayer(state);
    const hero = currentPlayer ? this.getHeroFighter(currentPlayer) : undefined;
    const visual = this.getHeroVisual(hero?.definitionId);
    const totalWidth = visibleCount * this.CARD_WIDTH + Math.max(visibleCount - 1, 0) * 10;
    const x = 400 - totalWidth / 2 + this.CARD_WIDTH / 2 + index * (this.CARD_WIDTH + 10);
    const y = 532;
    const container = this.add.container(x, y);
    const artKey = this.getCardTextureKey(card, hero?.definitionId);
    const isSelected = this.gameState.selectedCardId === card.id;

    this.drawComicPanel(container, -this.CARD_WIDTH / 2 - 4, -this.CARD_HEIGHT / 2 - 5, this.CARD_WIDTH + 8, this.CARD_HEIGHT + 10, visual.accent, {
      fill: 0x090d17,
      alpha: 0.98,
      cut: 7,
      lineAlpha: isSelected ? 1 : 0.78,
    });

    const back = this.add.rectangle(0, 0, this.CARD_WIDTH + 8, this.CARD_HEIGHT + 10, 0x000000, 0);
    back.setStrokeStyle(isSelected ? 3 : 1, isSelected ? HUD.gold : visual.accent, isSelected ? 1 : 0.72);
    container.add(back);

    if (artKey) {
      const art = this.add.image(0, 0, artKey);
      art.setDisplaySize(this.CARD_WIDTH - 4, this.CARD_HEIGHT - 4);
      container.add(art);
    } else {
      const cover = this.add.image(0, -4, this.textureKeyOrFallback(visual.coverKey));
      cover.setDisplaySize(48, 68);
      cover.setAlpha(0.76);

      const value = this.add.text(0, -24, String(card.definition.value), {
        fontFamily: 'Arial, sans-serif',
        fontSize: '18px',
        color: '#ffffff',
        fontStyle: 'bold',
        stroke: '#070a12',
        strokeThickness: 3,
      });
      value.setOrigin(0.5);

      const title = this.add.text(0, 24, card.definition.title, {
        fontFamily: 'Arial, sans-serif',
        fontSize: '8px',
        color: HUD.text,
        align: 'center',
        fixedWidth: this.CARD_WIDTH - 8,
      });
      title.setOrigin(0.5);
      container.add([cover, value, title]);
    }

    container.setSize(this.CARD_WIDTH, this.CARD_HEIGHT);
    container.setScale(isSelected ? 1.08 : 1);
    container.setInteractive({ useHandCursor: true });
    container.on('pointerdown', () => this.handleCardClick(card.id));
    container.setData('cardFrame', back);

    this.cardsContainer.add(container);
    this.cardSprites.set(card.id, container);
  }

  private renderHUD(): void {
    if (!this.hudContainer) return;

    this.hudContainer.removeAll(true);

    const state = this.gameState.gameState;
    if (!state) {
      this.drawEmptyHud();
      return;
    }

    state.players.slice(0, 2).forEach((player, index) => {
      this.drawPlayerPanel(player, index, state.currentTurn.currentPlayerId === player.id);
    });

    this.drawOpponentHand(state);
    this.drawTurnChip(state);
    this.drawSelectedCardInspector(state);
  }

  private drawPlayerPanel(player: Player, index: number, isCurrent: boolean): void {
    if (!this.hudContainer) return;

    const isLocal = index === 0;
    const x = 14;
    const y = isLocal ? 424 : 12;
    const w = isLocal ? 292 : 292;
    const h = isLocal ? 62 : 76;
    const hero = this.getHeroFighter(player);
    const visual = this.getHeroVisual(hero?.definitionId);
    const hpRatio = hero ? Phaser.Math.Clamp(hero.health / Math.max(hero.maxHealth, 1), 0, 1) : 0;
    const accent = isLocal ? HUD.cyan : HUD.red;

    this.drawComicPanel(this.hudContainer, x, y, w, h, isCurrent ? accent : visual.accent, {
      fill: isLocal ? 0x071624 : 0x170b10,
      alpha: isCurrent ? 0.98 : 0.9,
      cut: 16,
      lineAlpha: isCurrent ? 1 : 0.72,
    });

    if (isCurrent) {
      const currentGlow = this.add.rectangle(x + w - 23, y + h / 2, 28, 28, 0x000000, 0);
      currentGlow.setStrokeStyle(4, accent, 0.92);
      this.hudContainer.add(currentGlow);
    }

    const cover = this.add.image(x + 24, y + h / 2, this.textureKeyOrFallback(visual.coverKey));
    cover.setDisplaySize(46, h - 12);
    cover.setAlpha(0.7);
    this.hudContainer.add(cover);

    const avatarX = x + 62;
    const avatarFrame = this.add.circle(avatarX, y + h / 2 - 2, isLocal ? 24 : 27, HUD.ink, 0.94);
    avatarFrame.setStrokeStyle(2, accent, 0.92);
    this.hudContainer.add(avatarFrame);

    const avatar = this.add.image(avatarX, y + h / 2 - 3, this.textureKeyOrFallback(visual.avatarKey));
    const avatarSize = isLocal ? 44 : 50;
    avatar.setDisplaySize(avatarSize, avatarSize);
    this.hudContainer.add(avatar);

    const mini = this.add.image(avatarX, y + h - 14, this.textureKeyOrFallback(visual.miniKey));
    mini.setDisplaySize(isLocal ? 22 : 28, isLocal ? 22 : 28);
    this.hudContainer.add(mini);

    const textX = x + 98;
    const name = this.add.text(textX, y + (isLocal ? 8 : 14), player.name || visual.name, {
      fontFamily: 'Arial, sans-serif',
      fontSize: isLocal ? '16px' : '14px',
      color: HUD.text,
      fontStyle: 'bold',
      fixedWidth: 160,
      stroke: '#05070d',
      strokeThickness: 3,
    });
    this.hudContainer.add(name);

    const hpBgX = x + 98;
    this.drawHudBar(this.hudContainer, hpBgX, y + (isLocal ? 33 : 42), 150, 12, hpRatio, this.getHpColor(hpRatio), accent);

    const pips = Math.max(player.actionsRemaining, 0);
    for (let i = 0; i < 4; i++) {
      const pip = this.add.rectangle(x + 204 + i * 13, y + h - 14, 8, 8, i < pips ? accent : HUD.ink, i < pips ? 0.95 : 0.65);
      pip.setRotation(Math.PI / 4);
      pip.setStrokeStyle(1, i < pips ? 0xffffff : HUD.lineDim, i < pips ? 0.42 : 0.6);
      this.hudContainer.add(pip);
    }

    const statLine = this.add.text(textX, y + (isLocal ? 43 : 52), this.getPlayerStats(player, hero), {
      fontFamily: 'Arial, sans-serif',
      fontSize: isLocal ? '12px' : '11px',
      color: HUD.mutedText,
      fixedWidth: 178,
    });
    this.hudContainer.add(statLine);
  }

  private drawTurnChip(state: GameState): void {
    if (!this.hudContainer) return;

    this.drawComicPanel(this.hudContainer, 308, 20, 184, 44, HUD.gold, {
      fill: 0x060b14,
      alpha: 0.97,
      cut: 18,
    });

    const phases = [HUD.cyan, 0x39d98a, HUD.gold, HUD.red, HUD.purple];
    phases.forEach((color, index) => {
      const node = this.add.circle(340 + index * 30, 42, index === state.turnCount % phases.length ? 8 : 6, color, index === state.turnCount % phases.length ? 0.98 : 0.32);
      node.setStrokeStyle(2, index === state.turnCount % phases.length ? 0xffffff : HUD.lineDim, 0.7);
      this.hudContainer?.add(node);
    });

    const text = this.add.text(400, 36, `Turn ${state.turnCount}`, {
      fontFamily: 'Arial, sans-serif',
      fontSize: '15px',
      color: HUD.text,
      fontStyle: 'bold',
      stroke: '#05070d',
      strokeThickness: 3,
    });
    text.setOrigin(0.5);
    this.hudContainer.add(text);

    const phase = this.add.text(400, 55, state.phase.replace(/_/g, ' '), {
      fontFamily: 'Arial, sans-serif',
      fontSize: '11px',
      color: HUD.mutedText,
    });
    phase.setOrigin(0.5);
    this.hudContainer.add(phase);
  }

  private drawOpponentHand(state: GameState): void {
    if (!this.hudContainer) return;

    const opponent = state.players[1];
    if (!opponent) return;

    const handCount = Math.min(opponent.hand.length, 7);
    this.drawComicPanel(this.hudContainer, 528, 14, 242, 76, HUD.gold, {
      fill: 0x080d17,
      alpha: 0.84,
      cut: 14,
      lineAlpha: 0.62,
    });

    for (let i = 0; i < handCount; i++) {
      this.drawMiniCardBack(
        this.hudContainer,
        560 + i * 28,
        52,
        40,
        58,
        i === handCount - 1 ? HUD.red : HUD.gold,
        Phaser.Math.DegToRad(-5 + i * 1.5)
      );
    }

    const count = this.add.text(744, 92, `Hand ${opponent.hand.length}`, {
      fontFamily: 'Arial, sans-serif',
      fontSize: '12px',
      color: HUD.text,
      fontStyle: 'bold',
      stroke: '#070a12',
      strokeThickness: 3,
    });
    count.setOrigin(0.5);
    this.hudContainer.add(count);
  }

  private drawSelectedCardInspector(state: GameState): void {
    if (!this.hudContainer || !this.gameState.selectedCardId) return;

    const selected = this.getSelectedCard(state);
    if (!selected) return;

    const owner = state.players.find(player => player.id === selected.ownerId);
    const hero = owner ? this.getHeroFighter(owner) : undefined;
    const artKey = this.getCardTextureKey(selected, hero?.definitionId);

    this.drawComicPanel(this.hudContainer, 565, 132, 224, 322, HUD.purple, {
      fill: 0x080d17,
      alpha: 0.97,
      cut: 18,
    });
    const header = this.add.rectangle(594, 150, 160, 4, HUD.purple, 0.88).setOrigin(0, 0.5);
    this.hudContainer.add(header);

    if (artKey) {
      const art = this.add.image(680, 264, artKey);
      art.setDisplaySize(122, 176);
      this.hudContainer.add(art);
    } else {
      const fallback = this.add.rectangle(680, 264, 122, 176, 0x111827, 0.94);
      fallback.setStrokeStyle(2, 0xd7b84b, 0.8);
      const title = this.add.text(680, 238, selected.definition.title, {
        fontFamily: 'Arial, sans-serif',
        fontSize: '14px',
        color: HUD.text,
        fontStyle: 'bold',
        align: 'center',
        fixedWidth: 104,
      });
      title.setOrigin(0.5);
      const value = this.add.text(680, 285, String(selected.definition.value), {
        fontFamily: 'Arial, sans-serif',
        fontSize: '40px',
        color: '#ffffff',
        fontStyle: 'bold',
      });
      value.setOrigin(0.5);
      this.hudContainer.add([fallback, title, value]);
    }

    const meta = this.add.text(680, 370, `${selected.definition.title}\n${selected.definition.type.toUpperCase()}  ${selected.definition.value}/${selected.definition.boost}`, {
      fontFamily: 'Arial, sans-serif',
      fontSize: '13px',
      color: HUD.text,
      align: 'center',
      fixedWidth: 176,
      lineSpacing: 5,
    });
    meta.setOrigin(0.5);
    this.hudContainer.add(meta);
  }

  private drawEmptyHud(): void {
    if (!this.hudContainer) return;

    this.drawComicPanel(this.hudContainer, 260, 22, 280, 48, HUD.gold, {
      fill: 0x080d17,
      alpha: 0.95,
      cut: 16,
    });
    const text = this.add.text(400, 46, 'Waiting for game state', {
      fontFamily: 'Arial, sans-serif',
      fontSize: '15px',
      color: HUD.mutedText,
    });
    text.setOrigin(0.5);
    this.hudContainer.add(text);
  }

  private handleSceneClick(
    pointer: Phaser.Input.Pointer,
    currentlyOver: Phaser.GameObjects.GameObject[] = []
  ): void {
    if (currentlyOver.length > 0) return;

    const worldPoint = this.cameras.main.getWorldPoint(pointer.x, pointer.y);
    const metrics = this.getBoardMetrics();
    const gridX = Math.floor((worldPoint.x - metrics.x) / metrics.cell);
    const gridY = Math.floor((worldPoint.y - metrics.y) / metrics.cell);

    if (gridX >= 0 && gridX < metrics.width && gridY >= 0 && gridY < metrics.height) {
      this.onGameEvent({
        type: 'SPACE_CLICKED',
        position: { x: gridX, y: gridY },
      });
    }
  }

  private handleFighterClick(fighterId: string): void {
    this.gameState.selectedFighterId = fighterId;
    this.updateSelectedFighter();

    this.onGameEvent({
      type: 'FIGHTER_CLICKED',
      fighterId,
    });
  }

  private handleCardClick(cardId: string): void {
    this.gameState.selectedCardId = cardId;
    this.updateSelectedCard();
    this.renderHUD();

    this.onGameEvent({
      type: 'CARD_CLICKED',
      cardId,
    });
  }

  private handleReactEvent(event: ReactToPhaserEvent): void {
    switch (event.type) {
      case 'UPDATE_STATE':
        this.updateGameState(event.state);
        break;
      case 'HIGHLIGHT_SPACES':
        this.gameState.highlightedSpaces = event.spaces;
        this.highlightSpaces(event.spaces);
        break;
      case 'SELECT_FIGHTER':
        this.gameState.selectedFighterId = event.fighterId;
        this.updateSelectedFighter();
        break;
      case 'SELECT_CARD':
        this.gameState.selectedCardId = event.cardId;
        this.updateSelectedCard();
        this.renderHUD();
        break;
      case 'MOVE_FIGHTER':
        void this.moveFighter(event.fighterId, event.position);
        break;
      case 'SHOW_DAMAGE':
        this.showDamage(event.fighterId, event.amount);
        break;
      default:
        break;
    }
  }

  highlightSpaces(positions: Position[]): void {
    this.spaceHighlights.forEach(highlight => highlight.destroy());
    this.spaceHighlights.clear();

    positions.forEach(pos => {
      if (!this.isInsideBoard(pos)) return;

      const world = this.gridToWorld(pos);
      const metrics = this.getBoardMetrics();
      const highlight = this.add.graphics();
      highlight.fillStyle(HUD.cyan, 0.16);
      highlight.fillCircle(world.x, world.y, metrics.cell * 0.32);
      highlight.lineStyle(4, HUD.cyan, 0.96);
      highlight.strokeCircle(world.x, world.y, metrics.cell * 0.36);
      highlight.lineStyle(2, 0xffffff, 0.5);
      highlight.strokeRoundedRect(world.x - metrics.cell / 2 + 5, world.y - metrics.cell / 2 + 5, metrics.cell - 10, metrics.cell - 10, 8);

      this.highlightsContainer?.add(highlight);
      this.spaceHighlights.set(`${pos.x},${pos.y}`, highlight);
    });
  }

  clearHighlights(): void {
    this.spaceHighlights.forEach(rect => rect.destroy());
    this.spaceHighlights.clear();
  }

  showDamage(fighterId: string, amount: number): void {
    const fighter = this.fighterSprites.get(fighterId);
    if (!fighter) return;

    const damageText = this.add.text(fighter.x, fighter.y - 56, `-${amount}`, {
      fontFamily: 'Arial, sans-serif',
      fontSize: '30px',
      color: '#ff4d5f',
      fontStyle: 'bold',
      stroke: '#0b0d14',
      strokeThickness: 4,
    });
    damageText.setOrigin(0.5);
    this.effectsContainer?.add(damageText);

    this.tweens.add({
      targets: damageText,
      y: fighter.y - 108,
      alpha: 0,
      duration: 900,
      ease: 'Cubic.easeOut',
      onComplete: () => damageText.destroy(),
    });
  }

  updateGameState(state: GameState): void {
    this.gameState.gameState = state;

    this.createBoard();
    this.createFighters(state.players.flatMap(player => player.fighters));
    this.createCards(this.getCurrentPlayer(state)?.hand ?? []);
    this.renderHUD();
    this.highlightSpaces(this.gameState.highlightedSpaces);
    this.updateSelectedFighter();
  }

  moveFighter(fighterId: string, position: Position): Promise<void> {
    return new Promise(resolve => {
      const fighter = this.fighterSprites.get(fighterId);
      if (!fighter) {
        resolve();
        return;
      }

      const target = this.gridToWorld(position);

      this.tweens.add({
        targets: fighter,
        x: target.x,
        y: target.y,
        duration: 280,
        ease: 'Sine.easeInOut',
        onComplete: () => resolve(),
      });
    });
  }

  private updateSelectedFighter(): void {
    this.fighterSprites.forEach((container, id) => {
      const ring = container.getData('selectionRing') as { setVisible: (visible: boolean) => void } | undefined;
      ring?.setVisible(id === this.gameState.selectedFighterId);
    });
  }

  private updateSelectedCard(): void {
    this.cardSprites.forEach((container, id) => {
      const isSelected = id === this.gameState.selectedCardId;
      container.setScale(isSelected ? 1.08 : 1);
      container.y = isSelected ? 522 : 532;

      const frame = container.getData('cardFrame') as Phaser.GameObjects.Rectangle | undefined;
      frame?.setStrokeStyle(isSelected ? 3 : 1, isSelected ? 0xf7f0d2 : 0x65708a, isSelected ? 1 : 0.72);
    });
  }

  private getBoardDefinition(): BoardDefinition | undefined {
    return this.gameState.gameState?.board.definition;
  }

  private getBoardMetrics(): { x: number; y: number; width: number; height: number; cell: number } {
    const board = this.getBoardDefinition();
    const width = board?.width ?? 6;
    const height = board?.height ?? 4;
    const cell = this.SPACE_SIZE;
    const x = Math.round((this.cameras.main.width - width * cell) / 2);
    return { x, y: this.BOARD_TOP, width, height, cell };
  }

  private gridToWorld(position: Position): Position {
    const metrics = this.getBoardMetrics();
    return {
      x: metrics.x + position.x * metrics.cell + metrics.cell / 2,
      y: metrics.y + position.y * metrics.cell + metrics.cell / 2,
    };
  }

  private isInsideBoard(position: Position): boolean {
    const metrics = this.getBoardMetrics();
    return position.x >= 0 && position.x < metrics.width && position.y >= 0 && position.y < metrics.height;
  }

  private getFallbackZones(x: number, y: number): Zone[] {
    const zones = Object.keys(ZONE_COLORS) as Zone[];
    const first = zones[(x + y) % zones.length];
    const second = (x + y) % 3 === 0 ? zones[(x + y + 2) % zones.length] : undefined;
    return second ? [first, second] : [first];
  }

  private getHeroVisual(heroId?: string): HeroVisual {
    if (!heroId) return FALLBACK_HERO;
    return HERO_VISUALS[heroId] ?? FALLBACK_HERO;
  }

  private textureKeyOrFallback(key: string | undefined, fallbackKey = FALLBACK_HERO.avatarKey): string {
    if (key && this.textures.exists(key)) return key;
    return this.textures.exists(fallbackKey) ? fallbackKey : FALLBACK_HERO.avatarKey;
  }

  private getCardTextureKey(card: CardInstance, heroId?: string): string | undefined {
    const art = getCardArtAsset(heroId, card.definition.id);
    if (art && this.textures.exists(art.key)) return art.key;

    if (card.definition.imageUrl) {
      const runtimeKey = this.getRuntimeTextureKey(card.definition.imageUrl);
      if (this.textures.exists(runtimeKey)) return runtimeKey;
      this.queueRuntimeTexture(runtimeKey, card.definition.imageUrl, 'cards');
    }

    return undefined;
  }

  private getBoardTextureKey(board?: BoardDefinition): string | undefined {
    const art = getBoardArtAsset(board?.id);
    if (art && this.textures.exists(art.key)) return art.key;

    if (board?.imageUrl) {
      const runtimeKey = this.getRuntimeTextureKey(board.imageUrl);
      if (this.textures.exists(runtimeKey)) return runtimeKey;
      this.queueRuntimeTexture(runtimeKey, board.imageUrl, 'board');
    }

    return undefined;
  }

  private getRuntimeTextureKey(url: string): string {
    let hash = 0;
    for (let i = 0; i < url.length; i++) {
      hash = ((hash << 5) - hash + url.charCodeAt(i)) | 0;
    }
    return `runtime-image-${Math.abs(hash)}`;
  }

  private queueRuntimeTexture(key: string, url: string, target: 'board' | 'cards'): void {
    if (this.pendingRuntimeTextures.has(key) || this.textures.exists(key)) return;

    this.pendingRuntimeTextures.add(key);
    this.load.image(key, url);
    this.load.once(`filecomplete-image-${key}`, () => {
      this.pendingRuntimeTextures.delete(key);
      if (target === 'board') {
        this.createBoard();
        this.highlightSpaces(this.gameState.highlightedSpaces);
      } else {
        this.createCards(this.getCurrentPlayer(this.gameState.gameState)?.hand ?? []);
        this.renderHUD();
      }
    });
    this.load.once(`loaderror`, () => {
      this.pendingRuntimeTextures.delete(key);
    });
    if (!this.load.isLoading()) {
      this.load.start();
    }
  }

  private getSelectedCard(state: GameState): CardInstance | undefined {
    const selectedCardId = this.gameState.selectedCardId;
    if (!selectedCardId) return undefined;

    return state.players
      .flatMap(player => [...player.hand, ...player.discardPile, ...player.deck])
      .find(card => card.id === selectedCardId);
  }

  private getCurrentPlayer(state: GameState | null): Player | undefined {
    // КОНТРАКТ адаптера (B2): players[0] — ЛОКАЛЬНЫЙ игрок. Рука/счётчики
    // в HUD всегда его, а не того, чей сейчас ход (в мультиплеере при ходе
    // соперника показывалась бы его панель).
    if (!state) return undefined;
    return state.players[0];
  }

  private getHeroFighter(player: Player): Fighter | undefined {
    return player.fighters.find(fighter => fighter.type === 'hero') ?? player.fighters[0];
  }

  private getPlayerStats(player: Player, hero?: Fighter): string {
    const hp = hero ? `${hero.health}/${hero.maxHealth}` : '0/0';
    return `HP ${hp}   Hand ${player.hand.length}   Deck ${player.deck.length}   Actions ${player.actionsRemaining}`;
  }

  private getHpColor(ratio: number): number {
    if (ratio > 0.6) return 0x4ecca3;
    if (ratio > 0.3) return 0xd7b84b;
    return 0xff4d5f;
  }

  private setupReplaySystem(): void {
    this.replaySystem = new ReplaySystem(this, {
      autoRecord: true,
      maxEvents: 1000,
    });

    this.events.on('replay:event', this.handleReplayEvent, this);
    this.events.on('replay:state', this.handleReplayState, this);
    this.events.on('replay:revert', this.handleReplayRevert, this);

    console.log('[GameScene] ReplaySystem initialized');
  }

  startRecording(players: Array<{ userId: string; userName?: string; heroId: string; heroName?: string }>, gameId: string): void {
    if (!this.replaySystem) return;

    this.replaySystem.startRecording(players, gameId, {
      boardId: 'default',
      gameMode: 'standard',
    });
  }

  stopRecording(winnerId?: string): GameReplay | null {
    if (!this.replaySystem) return null;
    return this.replaySystem.stopRecording(winnerId);
  }

  loadReplay(replay: GameReplay): void {
    if (!this.replaySystem) return;

    this.replaySystem.loadReplay(replay);
  }

  playReplay(): void {
    if (!this.replaySystem) return;
    this.replaySystem.play();
  }

  pauseReplay(): void {
    if (!this.replaySystem) return;
    this.replaySystem.pause();
  }

  stopReplay(): void {
    if (!this.replaySystem) return;
    this.replaySystem.stop();
  }

  seekReplay(time: number): void {
    if (!this.replaySystem) return;
    this.replaySystem.seekTo(time);
  }

  setReplaySpeed(speed: number): void {
    if (!this.replaySystem) return;
    this.replaySystem.setPlaybackSpeed(speed);
  }

  private handleReplayEvent(event: unknown): void {
    console.log('[GameScene] replay event', event);
  }

  private handleReplayState(state: Partial<GameState>): void {
    this.updateGameState(state as GameState);
  }

  private handleReplayRevert(event: unknown): void {
    console.log('[GameScene] replay revert', event);
  }

  getReplaySystem(): ReplaySystem | null {
    return this.replaySystem;
  }
}
