import fs from 'node:fs';
import path from 'node:path';

const ownedNames = {
  combat: /^(?:combat-|timeout-).*\.json$/,
  live: /^(?:(?:catalog-|content-|duel-|duplicate-).*|live-error|cleanup-error)\.json$/,
  accounts: /^accounts\.json$/,
};

// Only direct, regular JSON files belonging to this capture are removed.
// Never recurse into directories or follow links to external files.
export function clearCaptureArtifacts(directory, capture) {
  const pattern = ownedNames[capture];
  if (!pattern) throw new Error(`Unknown capture: ${capture}`);
  const removed = [];
  for (const entry of fs.readdirSync(directory, {withFileTypes:true})) {
    if (!entry.isFile() || !pattern.test(entry.name)) continue;
    fs.unlinkSync(path.join(directory, entry.name));
    removed.push(entry.name);
  }
  return removed;
}
