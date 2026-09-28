import { defineConfig } from 'vitest/config';

// Separate from vite.config.ts so tests never load the dev-server plugins.
export default defineConfig({
  test: {
    environment: 'node',
    include: ['art-hub/**/*.test.ts', 'src/**/*.test.{ts,tsx}'],
    testTimeout: 60000,
  },
});
