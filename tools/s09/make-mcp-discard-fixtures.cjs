// Offline GD-032 Slate-MCP input: public owner/opponent discard and a hidden
// opponent placeholder. Usage: node tools/s09/make-mcp-discard-fixtures.cjs [out-dir]
// Pass the printed hidden/ or public/ directory as -S08Fixtures to UnrealEditor.
const fs = require('fs');
const os = require('os');
const path = require('path');

const root = path.resolve(__dirname, '../..');
const source = path.join(root, 'docs/game-design/evidence/S08/fixtures/04-game-state-query-host.json');
const out = process.argv[2] || fs.mkdtempSync(path.join(os.tmpdir(), 's09-mcp-discards-'));
const original = fs.readFileSync(source, 'utf8');

for (const variant of ['hidden', 'public']) {
  const fixture = JSON.parse(original);
  const state = JSON.parse(fixture.raw.data.gameState.state);
  const [owner, opponent] = Object.keys(state.handZones);
  if (!owner || !opponent) throw new Error('source fixture needs two players');

  const ownerCard = state.handZones[owner].cards.shift();
  if (!ownerCard) throw new Error('source fixture needs an owner hand card');
  ownerCard.isVisible = true;
  ownerCard.text = 'MCP inspection: own public discard card text.';
  state.discardPiles[owner] = [ownerCard];

  if (variant === 'hidden') {
    const placeholder = structuredClone(state.handZones[opponent].cards[0]);
    if (!placeholder || !String(placeholder.id).startsWith('hidden-')) {
      throw new Error('source fixture needs a hidden opponent placeholder');
    }
    state.discardPiles[opponent] = [placeholder];
  } else {
    const publicCard = structuredClone(state.handZones[owner].cards[0]);
    if (!publicCard) throw new Error('source fixture needs another owner card');
    publicCard.id = 'mcp-opponent-public::0';
    publicCard.name = 'Opponent Public Card';
    publicCard.nameRu = 'Открытая карта соперника';
    publicCard.text = 'MCP inspection: opponent public discard card text.';
    publicCard.isVisible = true;
    state.discardPiles[opponent] = [publicCard];
  }

  fixture.raw.data.gameState.state = JSON.stringify(state);
  const dir = path.join(out, variant);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, '04-game-state-query-host.json'), JSON.stringify(fixture));
  process.stdout.write(`${variant}: ${dir}\n`);
}
