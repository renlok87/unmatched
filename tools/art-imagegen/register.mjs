import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

// Copies an imagegen output unchanged and records a human/model visual review.
// This utility never generates images or transforms their pixels.
const [id, source, review] = process.argv.slice(2);
if (!id || !source || !review) throw new Error('Usage: node tools/art-imagegen/register.mjs ID SOURCE REVIEW');
const root = path.resolve('art/imagegen/mvp-v1');
const manifestPath = path.join(root, 'manifest.json');
const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8').replace(/^\uFEFF/, ''));
const asset = manifest.assets.find(a => a.id === id);
if (!asset) throw new Error(`Unknown asset: ${id}`);
const destination = path.resolve(root, asset.path);
if (!destination.startsWith(root + path.sep)) throw new Error('Destination outside package');
const data = fs.readFileSync(source);
if (!data.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10]))) throw new Error('Input is not PNG');
const hash = crypto.createHash('sha256').update(data).digest('hex');
if (fs.existsSync(destination)) {
  const priorHash = crypto.createHash('sha256').update(fs.readFileSync(destination)).digest('hex');
  if (priorHash !== hash) throw new Error('Existing asset differs; select a new versioned path in the manifest first');
}
if (!fs.existsSync(path.join(root, asset.promptPath))) throw new Error('Save prompt before registering');
fs.mkdirSync(path.dirname(destination), { recursive: true });
fs.copyFileSync(source, destination);
Object.assign(asset, {
  status: 'generated-reviewed', sourcePath: path.resolve(source),
  width: data.readUInt32BE(16), height: data.readUInt32BE(20),
  alpha: [4,6].includes(data[25]), bytes: data.length, sha256: hash,
  review: { result: 'usable visual source proposal', notes: review },
});
manifest.progress.generated = manifest.assets.filter(a => a.status.startsWith('generated')).length;
manifest.progress.reviewed = manifest.assets.filter(a => a.status === 'generated-reviewed').length;
manifest.progress.total = manifest.assets.length;
const temporary = manifestPath + '.new';
fs.writeFileSync(temporary, JSON.stringify(manifest, null, 2) + '\n');
fs.renameSync(temporary, manifestPath);
console.log(JSON.stringify({id, destination, width:asset.width, height:asset.height, alpha:asset.alpha, progress:manifest.progress}));
