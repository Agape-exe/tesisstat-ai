import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true },
  build: {
    rollupOptions: {
      input: {
        app: 'index.html',
        researchDemo: 'research-demo/index.html',
        descriptiveDemo: 'statistics-demo.html',
      },
    },
  },
  test: {
    // Bound jsdom contention on Windows without extending test timeouts.
    maxWorkers: 2,
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
    restoreMocks: true,
  },
});
