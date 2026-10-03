/**
 * Database guards shared by the board seeds (prisma/seed-env-map-boards.ts).
 *
 * A board seed writes only to the isolated S09 test database (127.0.0.1/localhost:55434), or, with the explicit
 * `--allow-main-dev-db` flag, to the canonical dev DB localhost:5433/unmatched that every dev stand is cloned from
 * by tools/db/sync-dev-stands.cjs (user decision 2026-10-03, docs/backend-api/db-divergence-2026-10-03.md).
 *
 * Moved here from prisma/seed-art-fixture-boards.ts, retired with the synthetic boards on 2026-10-04
 * (docs/game-design/decisions/2026-10-04-real-boards-only.md).
 */
export const ISOLATED_DB_PORTS = ['55434'];
export const ISOLATED_DB_HOSTS = ['127.0.0.1', 'localhost'];
/** Canonical dev DB: allowed only with the explicit `--allow-main-dev-db` flag. */
export const MAIN_DEV_DB = { port: '5433', database: 'unmatched' };

export interface DbGuardOptions {
  allowMainDevDb?: boolean;
}

/** True for the local main dev DB (localhost/127.0.0.1:5433/unmatched). */
export function isMainDevDatabase(parsed: URL): boolean {
  return (
    ISOLATED_DB_HOSTS.includes(parsed.hostname) &&
    parsed.port === MAIN_DEV_DB.port &&
    parsed.pathname.replace(/^\//, '') === MAIN_DEV_DB.database
  );
}
