/**
 * Unmatched Design System - Figma Plugin
 *
 * Установка:
 * 1. В Figma: Plugins → Development → New Plugin
 * 2. Выберите "Figma Design"
 * 3. Скопируйте этот код в main.ts
 * 4. Запустите: Plugins → Unmatched Design System
 */

// Color palette
const COLORS = {
  primary: {
    yellow: { r: 1, g: 0.84, b: 0 }, // #FFD700
    purple: { r: 0.42, g: 0.3, b: 0.6 }, // #6B4C9A
    red: { r: 0.86, g: 0.08, b: 0.24 }, // #DC143C
    blue: { r: 0.12, g: 0.23, b: 0.54 }, // #1E3A8A
  },
  neutral: {
    black: { r: 0, g: 0, b: 0 },
    darkGray: { r: 0.12, g: 0.12, b: 0.12 }, // #1F1F1F
    gray: { r: 0.5, g: 0.5, b: 0.5 }, // #808080
    lightGray: { r: 0.83, g: 0.83, b: 0.83 }, // #D3D3D3
    white: { r: 1, g: 1, b: 1 },
  },
  semantic: {
    energy: { r: 1, g: 0.42, b: 0.21 }, // #FF6B35
    speed: { r: 0.31, g: 0.8, b: 0.77 }, // #4ECDC4
    defense: { r: 0.58, g: 0.88, b: 0.83 }, // #95E1D3
    magic: { r: 0.66, g: 0.85, b: 0.86 }, // #A8DADC
  },
  factions: {
    marvel: { r: 0.86, g: 0.08, b: 0.24 }, // #DC143C
    witcher: { r: 0.12, g: 0.23, b: 0.54 }, // #1E3A8A
    historical: { r: 0.82, g: 0.74, b: 0.55 }, // #D2B48C
    jurassic: { r: 0.13, g: 0.55, b: 0.13 }, // #228B22
    tmnt: { r: 0, g: 0.66, b: 0.42 }, // #00A86B
  },
};

// Card dimensions
const CARD_WIDTH = 300;
const CARD_HEIGHT = 420;

// Helpers
function hexToRgb(hex: string): { r: number; g: number; b: number } {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result
    ? {
        r: parseInt(result[1], 16) / 255,
        g: parseInt(result[2], 16) / 255,
        b: parseInt(result[3], 16) / 255,
      }
    : { r: 0, g: 0, b: 0 };
}

function createSolidPaint(color: { r: number; g: number; b: number }): SolidPaint {
  return { type: 'SOLID', color } as SolidPaint;
}

function createFrame(
  name: string,
  x: number,
  y: number,
  width: number,
  height: number
): FrameNode {
  const frame = figma.createFrame();
  frame.name = name;
  frame.resize(width, height);
  frame.x = x;
  frame.y = y;
  return frame;
}

function createRectangle(
  width: number,
  height: number,
  fill?: Paint,
  cornerRadius?: number
): RectangleNode {
  const rect = figma.createRectangle();
  rect.resize(width, height);
  if (fill) rect.fills = [fill];
  if (cornerRadius !== undefined) rect.cornerRadius = cornerRadius;
  return rect;
}

function createEllipse(width: number, height: number, fill?: Paint): EllipseNode {
  const ellipse = figma.createEllipse();
  ellipse.resize(width, height);
  if (fill) ellipse.fills = [fill];
  return ellipse;
}

function createText(
  content: string,
  fontSize: number,
  fontWeight: number,
  fill?: Paint
): TextNode {
  const text = figma.createText();
  text.characters = content;
  text.fontSize = fontSize;
  text.fontName = { family: 'Inter', style: fontWeight >= 700 ? 'Bold' : fontWeight >= 500 ? 'Medium' : 'Regular' };
  if (fill) text.fills = [fill];
  return text;
}

// Create Action Card Template
function createActionCard(): ComponentNode {
  const component = figma.createComponent();
  component.name = 'C/Action Card';
  component.resize(CARD_WIDTH, CARD_HEIGHT);
  component.cornerRadius = 16;

  // Background
  const bg = createRectangle(CARD_WIDTH, CARD_HEIGHT, createSolidPaint(COLORS.neutral.darkGray));
  bg.name = 'Background';
  component.addChild(bg);

  // Illustration Area (60%)
  const topHeight = CARD_HEIGHT * 0.6;
  const illustrationArea = createRectangle(
    CARD_WIDTH,
    topHeight,
    createSolidPaint(COLORS.primary.yellow),
    [16, 16, 0, 0]
  );
  illustrationArea.name = 'Illustration Area';
  illustrationArea.y = 0;
  component.addChild(illustrationArea);

  // Faction Badge
  const factionBadge = createEllipse(40, 40, createSolidPaint(COLORS.primary.purple));
  factionBadge.name = 'Faction Badge';
  factionBadge.x = 10;
  factionBadge.y = 10;
  component.addChild(factionBadge);

  // Value Badge
  const valueBadge = createEllipse(30, 30, createSolidPaint(COLORS.neutral.black));
  valueBadge.name = 'Value Badge';
  valueBadge.x = CARD_WIDTH - 40;
  valueBadge.y = 10;

  const valueText = createText('2', 20, 700, createSolidPaint(COLORS.primary.yellow));
  valueText.name = 'Value';
  valueText.x = 7;
  valueText.y = 2;
  valueBadge.appendChild(valueText);
  component.addChild(valueBadge);

  // Card Title
  const title = createText('BREAKTHROUGH', 16, 700, createSolidPaint(COLORS.neutral.white));
  title.name = 'Card Title';
  title.x = 16;
  title.y = topHeight + 16;
  component.addChild(title);

  // Card Effect
  const effect = createText(
    'DURING FIGHT: If MS. MARVEL started her turn on a different space, this card is worth 5.',
    12,
    400,
    createSolidPaint(COLORS.neutral.gray)
  );
  effect.name = 'Card Effect';
  effect.textAutoResize = 'WIDTH';
  effect.x = 16;
  effect.y = topHeight + 50;
  effect.resize(CARD_WIDTH - 32, 100);
  component.addChild(effect);

  // Card Footer
  const footer = createText('MS.MARVEL • x3', 10, 400, createSolidPaint(COLORS.neutral.gray));
  footer.name = 'Card Footer';
  footer.x = 16;
  footer.y = CARD_HEIGHT - 30;
  component.addChild(footer);

  return component;
}

// Create Hero Card Template
function createHeroCard(): ComponentNode {
  const component = figma.createComponent();
  component.name = 'C/Hero Card';
  component.resize(CARD_WIDTH, CARD_HEIGHT);
  component.cornerRadius = 16;

  // Background
  const bg = createRectangle(
    CARD_WIDTH,
    CARD_HEIGHT,
    createSolidPaint(COLORS.factions.historical),
    16
  );
  bg.name = 'Background';
  component.addChild(bg);

  // Top Zone (15%)
  const topHeight = CARD_HEIGHT * 0.15;
  const topZone = createRectangle(CARD_WIDTH, topHeight, createSolidPaint({ r: 0, g: 0, b: 0, a: 0.1 }));
  topZone.name = 'Top Zone';
  topZone.cornerRadius = [16, 16, 0, 0];
  component.addChild(topZone);

  // Logo
  const logo = createText('UNMATCHED', 12, 900, createSolidPaint(COLORS.neutral.white));
  logo.name = 'Logo';
  logo.x = 16;
  logo.y = 8;
  component.addChild(logo);

  // Native Name
  const nativeName = createText('織田信長', 14, 400, createSolidPaint(COLORS.neutral.white));
  nativeName.name = 'Native Name';
  nativeName.x = CARD_WIDTH - 30;
  nativeName.y = 8;
  nativeName.rotation = 90;
  component.addChild(nativeName);

  // Center Zone - Emblem
  const emblem = createEllipse(120, 120, createSolidPaint(COLORS.neutral.white));
  emblem.name = 'Emblem';
  emblem.strokeWeight = 4;
  emblem.strokes = [createSolidPaint(COLORS.primary.red)];
  emblem.x = (CARD_WIDTH - 120) / 2;
  emblem.y = topHeight + (CARD_HEIGHT * 0.6 - 120) / 2;
  component.addChild(emblem);

  // Bottom Zone
  const bottomY = CARD_HEIGHT * 0.75;

  // Hero Name
  const heroName = createText('ODA NOBUNAGA', 24, 700, createSolidPaint(COLORS.neutral.white));
  heroName.name = 'Hero Name';
  heroName.x = 16;
  heroName.y = bottomY + 20;
  component.addChild(heroName);

  // Hero Role
  const role = createText('HONOR GUARD', 14, 400, createSolidPaint(COLORS.primary.blue));
  role.name = 'Hero Role';
  role.x = 16;
  role.y = bottomY + 60;
  component.addChild(role);

  return component;
}

// Create Color Palette Page
function createColorPalettePage(): PageNode {
  const page = figma.createPage();
  page.name = '01. Colors & Styles';

  let yOffset = 60;

  // Title
  const title = createText('🎨 Color Palette', 32, 900);
  title.name = 'Page Title';
  title.x = 32;
  title.y = 32;
  page.appendChild(title);

  // Create color swatches
  const swatches = [
    ...Object.entries(COLORS.primary).map(([name, color]) => ({ name: `Primary ${name}`, color, category: 'Primary' })),
    ...Object.entries(COLORS.neutral).map(([name, color]) => ({ name, color, category: 'Neutral' })),
    ...Object.entries(COLORS.semantic).map(([name, color]) => ({ name, color, category: 'Semantic' })),
    ...Object.entries(COLORS.factions).map(([name, color]) => ({ name, color, category: 'Faction' })),
  ];

  const cols = 6;
  const swatchSize = 80;
  const gap = 16;

  swatches.forEach((swatch, i) => {
    const col = i % cols;
    const row = Math.floor(i / cols);
    const x = 32 + col * (swatchSize + gap);
    const y = yOffset + row * (swatchSize + 50);

    const colorNode = createRectangle(swatchSize, swatchSize, createSolidPaint(swatch.color), 8);
    colorNode.name = `${swatch.category}/${swatch.name}`;
    colorNode.x = x;
    colorNode.y = y;
    page.appendChild(colorNode);

    const label = createText(`${swatch.name}\n#${Math.round(swatch.color.r * 255).toString(16).padStart(2, '0')}${Math.round(swatch.color.g * 255).toString(16).padStart(2, '0')}${Math.round(swatch.color.b * 255).toString(16).padStart(2, '0')}`, 10, 400);
    label.name = 'Color Label';
    label.x = x;
    label.y = y + swatchSize + 4;
    page.appendChild(label);
  });

  return page;
}

// Main function
async function main() {
  // Clear selection
  figma.currentPage.selection = [];
  figma.viewport.scrollAndZoomIntoView([]);

  // Create Color Palette Page
  const colorPage = createColorPalettePage();

  // Create Card Templates Page
  const templatesPage = figma.createPage();
  templatesPage.name = '02. Card Templates';

  const actionCard = createActionCard();
  actionCard.x = 32;
  actionCard.y = 32;
  templatesPage.appendChild(actionCard);

  const heroCard = createHeroCard();
  heroCard.x = 360;
  heroCard.y = 32;
  templatesPage.appendChild(heroCard);

  // Select the created cards
  templatesPage.selection = [actionCard, heroCard];
  figma.viewport.scrollAndZoomIntoView(templatesPage.selection);

  // Notify user
  figma.notify('✅ Unmatched Design System created successfully!');

  // Show message
  figma.ui.postMessage({
    type: 'done',
    pages: [colorPage.name, templatesPage.name],
    components: [actionCard.name, heroCard.name],
  });
}

// Run main
main().catch((err) => {
  figma.notify(`❌ Error: ${err.message}`);
  console.error(err);
});
