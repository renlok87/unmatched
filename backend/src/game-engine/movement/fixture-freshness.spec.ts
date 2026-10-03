/**
 * MS-AT-08 (MS-R-67): golden move fixtures stay bound to what produced them.
 *  - each fixture on a topology map pins the sha256 (LF) of
 *    backend/prisma/fixtures/boards/<map>.topology.json; a changed topology
 *    fails here with a message that names the generator;
 *  - generated fixtures are byte-identical to a fresh run of
 *    backend/scripts/gen-move-fixtures.ts (no hand edits, no stale files);
 *  - the file name is the fixture name and the schema is unmatched.move-fixture/1.
 */
import { readFileSync } from 'node:fs';
import { basename } from 'node:path';
import {
  currentTopologySha256,
  loadMoveFixtures,
  MOVE_FIXTURE_GENERATOR,
  MOVE_FIXTURE_SCHEMA,
  MOVE_FIXTURE_SUFFIX,
  moveFixtureFiles,
  topologyStaleness,
} from '../../test/fixtures/move-fixture-state';
import { buildFixture, formatFixture, SCENARIOS } from '../../../scripts/gen-move-fixtures';

const FILES = moveFixtureFiles();
const FIXTURES = loadMoveFixtures();

describe('MS-AT-08 golden move fixtures are fresh', () => {
  it('schema, name = file name, known source, exactly one of draft / pending', () => {
    FIXTURES.forEach((fx, i) => {
      expect({
        file: basename(FILES[i]),
        schema: fx.schema,
        source: ['manual', 'generated'].includes(fx.expectSource),
        oneInput: Boolean(fx.draft) !== Boolean(fx.pending),
      }).toEqual({
        file: `${fx.name}${MOVE_FIXTURE_SUFFIX}`,
        schema: MOVE_FIXTURE_SCHEMA,
        source: true,
        oneInput: true,
      });
    });
  });

  it.each(FIXTURES.filter((f) => !f.board.lattice).map((f) => [f.name, f] as const))(
    '%s is pinned to the current topology',
    (_name, fx) => {
      expect(topologyStaleness(fx)).toBeNull();
    },
  );

  it('a stale pin explains itself and names the generator', () => {
    const fx = FIXTURES.find((f) => f.board.key === 'marmoreal');
    const stale = { ...fx, board: { ...fx.board, topologySha256: '0'.repeat(64) } };
    const message = topologyStaleness(stale);
    expect(message).toContain(currentTopologySha256(fx.board));
    expect(message).toContain(MOVE_FIXTURE_GENERATOR);
    expect(message).toContain('marmoreal.topology.json');
  });

  it('generated fixtures equal a fresh generator run; no stale or overwritten files', async () => {
    const scenarioNames = new Set(SCENARIOS.map((s) => s.name));
    expect(scenarioNames.size).toBe(SCENARIOS.length);
    const byName = new Map(FIXTURES.map((f, i) => [f.name, FILES[i]]));
    for (const fx of FIXTURES) {
      if (fx.expectSource === 'manual')
        expect({ manual: fx.name, generated: scenarioNames.has(fx.name) }).toEqual({
          manual: fx.name,
          generated: false,
        });
      else
        expect({ generated: fx.name, hasScenario: scenarioNames.has(fx.name) }).toEqual({
          generated: fx.name,
          hasScenario: true,
        });
    }
    for (const sc of SCENARIOS) {
      const file = byName.get(sc.name);
      expect({ scenario: sc.name, file: Boolean(file) }).toEqual({ scenario: sc.name, file: true });
      const fresh = formatFixture(await buildFixture(sc)) + '\n';
      expect({
        scenario: sc.name,
        text: readFileSync(file, 'utf8').replace(/\r\n/g, '\n'),
      }).toEqual({ scenario: sc.name, text: fresh });
    }
  }, 120_000);
});
