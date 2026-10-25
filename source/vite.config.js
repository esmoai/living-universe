import { defineConfig } from 'vite';

export default defineConfig({
  base: './',
  server: { host: '127.0.0.1' },
  preview: { host: '127.0.0.1' },
  build: { assetsInlineLimit: 1048576, chunkSizeWarningLimit: 700 },
});
