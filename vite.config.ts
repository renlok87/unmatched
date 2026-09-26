import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { fileURLToPath } from 'url'

const rootDir = path.dirname(fileURLToPath(import.meta.url))

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(rootDir, './src'),
    },
  },
  server: {
    port: 5174,
    strictPort: true,
  },
  publicDir: 'public',
  // Добавляем статические папки для изображений
  assetsInclude: ['**/*.png', '**/*.jpg', '**/*.jpeg', '**/*.webp'],
})
