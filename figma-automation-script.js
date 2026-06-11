/**
 * Unmatched Design System - Figma Automation Script
 *
 * Этот скрипт автоматически создаёт структуру Design System в Figma
 * Запустите его в Figma Console (Ctrl+Alt+I → Run)
 */

// ============================================
// CONFIGURATION
// ============================================

const CONFIG = {
  fileName: "Unmatched Design System",

  // Color Palette
  colors: {
    primary: {
      yellow: "#FFD700",
      purple: "#6B4C9A",
      red: "#DC143C",
      blue: "#1E3A8A"
    },
    neutral: {
      black: "#000000",
      darkGray: "#1F1F1F",
      gray: "#808080",
      lightGray: "#D3D3D3",
      white: "#FFFFFF"
    },
    semantic: {
      energy: "#FF6B35",
      speed: "#4ECDC4",
      defense: "#95E1D3",
      magic: "#A8DADC"
    }
  },

  // Typography
  typography: {
    headings: {
      "3XL": { size: 40, weight: 900 },
      "2XL": { size: 32, weight: 700 },
      "XL": { size: 24, weight: 700 }
    },
    body: {
      "LG": { size: 18, weight: 500 },
      "MD": { size: 16, weight: 500 },
      "Base": { size: 14, weight: 400 },
      "SM": { size: 12, weight: 400 },
      "XS": { size: 10, weight: 400 }
    }
  },

  // Card Dimensions
  cardSize: {
    width: 300,
    height: 420
  },

  // Spacing
  spacing: {
    xs: 4,
    sm: 8,
    md: 16,
    lg: 24,
    xl: 32
  }
};

// ============================================
// MAIN FUNCTIONS
// ============================================

/**
 * Main function to create the entire Design System
 */
async function createDesignSystem() {
  console.log("🎨 Creating Unmatched Design System...");

  try {
    // Create main page structure
    const colorsPage = createPage("Colors");
    const typographyPage = createPage("Typography");
    const componentsPage = createPage("Components");
    const iconsPage = createPage("Icons");
    const assetsPage = createPage("Assets");
    const examplesPage = createPage("Examples");

    // Create Colors
    console.log("📋 Creating Color Styles...");
    await createColorStyles(colorsPage);

    // Create Typography
    console.log("✏️ Creating Typography Styles...");
    await createTypographyStyles(typographyPage);

    // Create Components
    console.log("🧩 Creating Card Components...");
    await createCardComponents(componentsPage);

    // Create Icons
    console.log("🔷 Creating Icon Components...");
    await createIconComponents(iconsPage);

    // Create Examples
    console.log("🎴 Creating Example Cards...");
    await createExampleCards(examplesPage);

    console.log("✅ Design System created successfully!");
    console.log("📁 Check your Figma file for all components");

  } catch (error) {
    console.error("❌ Error creating Design System:", error);
  }
}

// ============================================
// PAGE CREATION
// ============================================

function createPage(name) {
  const page = figma.createPage();
  page.name = name;
  return page;
}

// ============================================
// COLOR STYLES
// ============================================

async function createColorStyles(page) {
  const startX = 100;
  const startY = 100;
  const swatchSize = 200;
  const gap = 20;
  const cols = 4;

  let x = startX;
  let y = startY;
  let col = 0;

  // Primary Colors
  for (const [name, hex] of Object.entries(CONFIG.colors.primary)) {
    createSwatch(page, x, y, swatchSize, hex, `Colors/Primary/${capitalize(name)}`);
    col++;
    x += swatchSize + gap;
    if (col >= cols) {
      col = 0;
      x = startX;
      y += swatchSize + gap + 40;
    }
  }

  // Neutral Colors
  for (const [name, hex] of Object.entries(CONFIG.colors.neutral)) {
    const label = name.replace(/([A-Z])/g, ' $1').trim();
    createSwatch(page, x, y, swatchSize, hex, `Colors/Neutral/${capitalize(label)}`);
    col++;
    x += swatchSize + gap;
    if (col >= cols) {
      col = 0;
      x = startX;
      y += swatchSize + gap + 40;
    }
  }

  // Semantic Colors
  for (const [name, hex] of Object.entries(CONFIG.colors.semantic)) {
    createSwatch(page, x, y, swatchSize, hex, `Colors/Semantic/${capitalize(name)}`);
    col++;
    x += swatchSize + gap;
  }
}

function createSwatch(page, x, y, size, hex, styleName) {
  const swatch = figma.createRectangle();
  swatch.resize(size, size);
  swatch.x = x;
  swatch.y = y;

  const paint = {
    type: 'SOLID',
    color: hexToRgb(hex)
  };
  swatch.fills = [paint];

  // Create style
  const style = figma.createPaintStyle();
  style.name = styleName;
  style.setPaints([paint]);

  // Add label
  const label = figma.createText();
  label.characters = styleName.split('/').pop();
  label.fontSize = 14;
  label.fontWeight = 600;
  label.x = x;
  label.y = y + size + 8;

  page.appendChild(swatch);
  page.appendChild(label);
}

// ============================================
// TYPOGRAPHY STYLES
// ============================================

async function createTypographyStyles(page) {
  const startX = 100;
  const startY = 100;
  const lineHeight = 80;

  let y = startY;

  // Headings
  for (const [size, config] of Object.entries(CONFIG.typography.headings)) {
    createTextStyle(
      page,
      startX,
      y,
      `Text/${size}/Bold`,
      config.size,
      config.weight,
      "UNMATCHED"
    );
    y += lineHeight;
  }

  y += 40;

  // Body Text
  for (const [size, config] of Object.entries(CONFIG.typography.body)) {
    createTextStyle(
      page,
      startX,
      y,
      `Text/${size}/Regular`,
      config.size,
      config.weight,
      "Описание эффекта карты..."
    );
    y += lineHeight;
  }
}

function createTextStyle(page, x, y, styleName, size, weight, text) {
  const textLayer = figma.createText();
  textLayer.characters = text;
  textLayer.fontSize = size;
  textLayer.fontWeight = weight;
  textLayer.x = x;
  textLayer.y = y;

  // Create style
  const style = figma.createTextStyle();
  style.name = styleName;
  style.setFontSize(size);
  style.setFontWeight(weight);

  page.appendChild(textLayer);
}

// ============================================
// CARD COMPONENTS
// ============================================

async function createCardComponents(page) {
  const startX = 100;
  const startY = 100;
  const gap = 500;

  // Action Card
  const actionCard = createActionCard(startX, startY);
  page.appendChild(actionCard);

  // Hero Card
  const heroCard = createHeroCard(startX + gap, startY);
  page.appendChild(heroCard);
}

function createActionCard(x, y) {
  const frame = figma.createFrame();
  frame.name = "Card/Action";
  frame.resize(CONFIG.cardSize.width, CONFIG.cardSize.height);
  frame.x = x;
  frame.y = y;

  // Background gradient
  const background = figma.createRectangle();
  background.resize(CONFIG.cardSize.width, CONFIG.cardSize.height);
  background.fills = [{
    type: 'GRADIENT_LINEAR',
    gradientStops: [
      {position: 0, color: hexToRgb(CONFIG.colors.primary.yellow)},
      {position: 1, color: hexToRgb("#FFED4E")}
    ]
  }];
  frame.appendChild(background);

  // Top zone (illustration)
  const topZone = figma.createFrame();
  topZone.name = "Top Zone";
  topZone.resize(CONFIG.cardSize.width, CONFIG.cardSize.height * 0.6);
  topZone.y = 0;

  // Faction badge
  const factionBadge = figma.createFrame();
  factionBadge.name = "Faction Badge";
  factionBadge.resize(40, 40);
  factionBadge.cornerRadius = 20;
  factionBadge.x = 10;
  factionBadge.y = 10;
  factionBadge.fills = [{type: 'SOLID', color: hexToRgb(CONFIG.colors.primary.purple)}];
  topZone.appendChild(factionBadge);

  frame.appendChild(topZone);

  // Bottom zone (description)
  const bottomZone = figma.createFrame();
  bottomZone.name = "Bottom Zone";
  bottomZone.resize(CONFIG.cardSize.width, CONFIG.cardSize.height * 0.4);
  bottomZone.y = CONFIG.cardSize.height * 0.6;
  bottomZone.fills = [{type: 'SOLID', color: hexToRgb(CONFIG.colors.neutral.darkGray)}];

  frame.appendChild(bottomZone);

  // Create component
  frame.setPluginData("type", "action");

  return frame;
}

function createHeroCard(x, y) {
  const frame = figma.createFrame();
  frame.name = "Card/Hero";
  frame.resize(CONFIG.cardSize.width, CONFIG.cardSize.height);
  frame.x = x;
  frame.y = y;

  // Background
  const background = figma.createRectangle();
  background.resize(CONFIG.cardSize.width, CONFIG.cardSize.height);
  background.fills = [{
    type: 'GRADIENT_LINEAR',
    gradientStops: [
      {position: 0, color: hexToRgb("#D2B48C")},
      {position: 1, color: hexToRgb("#E8DCC8")}
    ]
  }];
  frame.appendChild(background);

  // Top zone (logo + name)
  const topZone = figma.createFrame();
  topZone.name = "Top Zone";
  topZone.resize(CONFIG.cardSize.width, CONFIG.cardSize.height * 0.15);
  topZone.fills = [{type: 'SOLID', color: {r: 0, g: 0, b: 0, a: 0.05}}];
  frame.appendChild(topZone);

  // Center zone (emblem)
  const centerZone = figma.createFrame();
  centerZone.name = "Center Zone";
  centerZone.resize(CONFIG.cardSize.width, CONFIG.cardSize.height * 0.6);
  centerZone.y = CONFIG.cardSize.height * 0.15;

  // Emblem
  const emblem = figma.createFrame();
  emblem.name = "Emblem";
  emblem.resize(120, 120);
  emblem.cornerRadius = 60;
  emblem.x = (CONFIG.cardSize.width - 120) / 2;
  emblem.y = (CONFIG.cardSize.height * 0.6 - 120) / 2;
  emblem.fills = [{type: 'SOLID', color: hexToRgb(CONFIG.colors.neutral.white)}];
  emblem.strokes = [{type: 'SOLID', color: hexToRgb(CONFIG.colors.primary.red), strokeWeight: 4}];
  centerZone.appendChild(emblem);

  frame.appendChild(centerZone);

  // Bottom zone (name + role)
  const bottomZone = figma.createFrame();
  bottomZone.name = "Bottom Zone";
  bottomZone.resize(CONFIG.cardSize.width, CONFIG.cardSize.height * 0.25);
  bottomZone.y = CONFIG.cardSize.height * 0.75;
  bottomZone.fills = [{
    type: 'GRADIENT_LINEAR',
    gradientStops: [
      {position: 0, color: {r: 0, g: 0, b: 0, a: 0.1}},
      {position: 1, color: {r: 0, g: 0, b: 0, a: 0}}
    ]
  }];
  frame.appendChild(bottomZone);

  // Create component
  frame.setPluginData("type", "hero");

  return frame;
}

// ============================================
// ICON COMPONENTS
// ============================================

async function createIconComponents(page) {
  const startX = 100;
  const startY = 100;
  const iconSize = 40;
  const gap = 20;
  const cols = 6;

  let x = startX;
  let y = startY;
  let col = 0;

  const icons = [
    {name: "Faction/Star", emoji: "⭐"},
    {name: "Attack/Sword", emoji: "⚔️"},
    {name: "Defense/Shield", emoji: "🛡️"},
    {name: "Energy/Lightning", emoji: "⚡"},
    {name: "Fire", emoji: "🔥"},
    {name: "Speed", emoji: "💨"},
    {name: "Magic", emoji: "✨"},
    {name: "Health", emoji: "❤️"}
  ];

  for (const icon of icons) {
    createIcon(page, x, y, iconSize, icon.name, icon.emoji);
    col++;
    x += iconSize + gap;
    if (col >= cols) {
      col = 0;
      x = startX;
      y += iconSize + gap + 30;
    }
  }
}

function createIcon(page, x, y, size, name, emoji) {
  const frame = figma.createFrame();
  frame.name = `Icon/${name}`;
  frame.resize(size, size);
  frame.x = x;
  frame.y = y;

  // Background
  const background = figma.createRectangle();
  background.resize(size, size);
  background.cornerRadius = 8;
  background.fills = [{type: 'SOLID', color: hexToRgb("#F8F9FA")}];
  frame.appendChild(background);

  // Emoji icon
  const text = figma.createText();
  text.characters = emoji;
  text.fontSize = size * 0.6;
  text.x = (size - text.width) / 2;
  text.y = (size - text.height) / 2;
  frame.appendChild(text);

  page.appendChild(frame);
}

// ============================================
// EXAMPLE CARDS
// ============================================

async function createExampleCards(page) {
  const startX = 100;
  const startY = 100;
  const gap = 500;

  // Ms. Marvel Action Card
  const msMarvelCard = createMsMarvelCard(startX, startY);
  page.appendChild(msMarvelCard);

  // Oda Nobunaga Hero Card
  const odaCard = createOdaNobunagaCard(startX + gap, startY);
  page.appendChild(odaCard);
}

function createMsMarvelCard(x, y) {
  const frame = figma.createFrame();
  frame.name = "Example/Ms Marvel Card";
  frame.resize(CONFIG.cardSize.width, CONFIG.cardSize.height);
  frame.x = x;
  frame.y = y;

  // ... (similar to action card but with Ms. Marvel branding)

  return frame;
}

function createOdaNobunagaCard(x, y) {
  const frame = figma.createFrame();
  frame.name = "Example/Oda Nobunaga Card";
  frame.resize(CONFIG.cardSize.width, CONFIG.cardSize.height);
  frame.x = x;
  frame.y = y;

  // ... (similar to hero card but with Oda Nobunaga branding)

  return frame;
}

// ============================================
// UTILITY FUNCTIONS
// ============================================

function hexToRgb(hex) {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result ? {
    r: parseInt(result[1], 16) / 255,
    g: parseInt(result[2], 16) / 255,
    b: parseInt(result[3], 16) / 255
  } : null;
}

function capitalize(str) {
  return str.replace(/\b\w/g, l => l.toUpperCase());
}

// ============================================
// RUN
// ============================================

// Run the main function
createDesignSystem();
