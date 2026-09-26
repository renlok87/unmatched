import Phaser from 'phaser';
import { GAME_IMAGE_ASSETS } from '../assets/gameAssetManifest';

export class BootScene extends Phaser.Scene {
  constructor() {
    super({ key: 'BootScene' });
  }

  preload(): void {
    this.createLoadScreen();
    this.loadHeroAssets();

    this.load.on('progress', this.updateLoadProgress, this);
    this.load.on('complete', this.onLoadComplete, this);
  }

  create(): void {
    this.setupGlobalEvents();
    this.scene.start('GameScene');
  }

  private createLoadScreen(): void {
    const { width, height } = this.cameras.main;

    this.add.rectangle(width / 2, height / 2, width, height, 0x121522);

    const loadingText = this.add.text(width / 2, height / 2 - 48, 'Loading...', {
      fontSize: '28px',
      color: '#f7f0d2',
      fontStyle: 'bold',
    });
    loadingText.setOrigin(0.5);

    const progressBarBg = this.add.rectangle(width / 2, height / 2, 360, 18, 0x252a3a);
    progressBarBg.setOrigin(0.5);

    const progressBar = this.add.rectangle(width / 2 - 180, height / 2, 0, 18, 0xd7b84b);
    progressBar.setOrigin(0, 0.5);
    this.registry.set('progressBar', progressBar);
  }

  private updateLoadProgress(progress: number): void {
    const progressBar = this.registry.get('progressBar') as Phaser.GameObjects.Rectangle | undefined;
    if (progressBar) {
      progressBar.width = 360 * progress;
    }
  }

  private onLoadComplete(): void {
    console.log('Phaser assets loaded');
  }

  private loadHeroAssets(): void {
    GAME_IMAGE_ASSETS.forEach(asset => {
      this.load.image(asset.key, asset.path);
    });
  }

  private setupGlobalEvents(): void {
    this.game.events.on('react-to-phaser', (event: unknown) => {
      console.log('BootScene: react-to-phaser', event);
    });
  }
}
