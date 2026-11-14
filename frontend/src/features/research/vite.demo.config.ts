import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: { port: 5174, strictPort: true },
  build: {
    outDir: 'dist/research-independent',
    rollupOptions: { input: 'research-demo/index.html' },
  },
});
