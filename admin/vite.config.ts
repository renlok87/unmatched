import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { artHubPlugin } from './art-hub/vite-plugin';

// https://vite.dev/config/
export default defineConfig({
  // artHubPlugin: dev-only endpoints /__art-hub/* for the «Арт-хаб» page (apply: 'serve').
  plugins: [react(), artHubPlugin()],
server: {
    port: 5480,
    strictPort: true,
    proxy: {
      '/graphql': {
        target: 'http://localhost:3000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
  resolve: {
    alias: {
      '@': '/src',
    },
  },
});
