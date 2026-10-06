/**
 * Art-hub snapshot CLI.
 *
 *   npm run art-hub:snapshot                 → docs/art-pipeline/art-hub-snapshot.json
 *   npm run art-hub:snapshot -- --out <file> → custom path (repo-relative or absolute)
 *   npm run art-hub:snapshot -- --summary    → print a short summary, write nothing
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { aggregate } from './aggregate';

export const DEFAULT_SNAPSHOT = 'docs/art-pipeline/art-hub-snapshot.json';

function repoRootFromHere(): string {
  const here = path.dirname(fileURLToPath(import.meta.url));
  return path.resolve(here, '..', '..');
}

function main(argv: string[]) {
  const repoRoot = repoRootFromHere();
  const outIdx = argv.indexOf('--out');
  const summaryOnly = argv.includes('--summary');
  const data = aggregate(repoRoot);

  const lines = [
    `art-hub: ${data.characters.length} персонажей, ${data.props.length} пропсов/окружения, ${data.pipelineHealth.runs.length} прогонов, ${data.warnings.length} предупреждений (${data.durationMs} мс)`,
    ...data.characters.map(
      (c) =>
        `  ${c.id.padEnd(24)} ${String(c.status ?? '—').padEnd(26)} моделей ${c.models.models.length}, превью ${c.models.previews.length}, видео ${
          c.videoRefs?.cues.reduce((n, q) => n + q.takes.filter((t) => t.video).length, 0) ?? 0
        }, слотов ${c.clips?.slots.length ?? 0}`,
    ),
    `  звук: ${data.audio.registry.units.length} единиц реестра (${data.audio.registry.byStatus.map((s) => `${s.status} ${s.count}`).join(', ') || '—'}), реплик ${
      data.audio.vo.total
    }, SoundWave в UE ${data.audio.ue.soundWaves}, микс ${data.audio.mix.latest ? `${data.audio.mix.latest.date} (${data.audio.mix.latest.rows.length} замера)` : '—'}, AUC-* ${
      data.audio.spends.spent
    } ${data.audio.spends.unit}`,
  ];
  console.log(lines.join('\n'));
  if (data.warnings.length) console.log(`предупреждения:\n  ${data.warnings.join('\n  ')}`);
  if (summaryOnly) return;

  const outArg = outIdx >= 0 ? argv[outIdx + 1] : undefined;
  const out = path.resolve(repoRoot, outArg ?? DEFAULT_SNAPSHOT);
  fs.mkdirSync(path.dirname(out), { recursive: true });
  const tmp = `${out}.tmp-${process.pid}`;
  fs.writeFileSync(tmp, `${JSON.stringify(data, null, 2)}\n`, 'utf8');
  fs.renameSync(tmp, out);
  console.log(`снимок записан: ${path.relative(repoRoot, out).split(path.sep).join('/')}`);
}

main(process.argv.slice(2));
