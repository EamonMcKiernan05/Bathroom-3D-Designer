import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// QA / test config: run the editor against the NEW plans.backend (8001) which has
// the OCR reconstruction. Start with:  npx vite --config vite.test.config.ts
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5175,
    proxy: {
      '/api': 'http://127.0.0.1:8001',
      '/models': 'http://127.0.0.1:8001',
      '/textures': 'http://127.0.0.1:8001',
      '/thumbnails': 'http://127.0.0.1:8001',
    },
  },
});
