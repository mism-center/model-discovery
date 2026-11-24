import { reactRouter } from '@react-router/dev/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';
import tsconfigPaths from 'vite-tsconfig-paths';
import svgr from 'vite-plugin-svgr';

export default defineConfig({
  plugins: [tailwindcss(), reactRouter(), tsconfigPaths(), svgr()],
  server: {
    // Browser uses a relative `/api` base; proxy it to the gateway so dev
    // mirrors the prod ingress (same-origin, no CORS). Target carries no
    // `/api` suffix since the request path already includes it.
    proxy: {
      '/api': {
        target: process.env.API_BASE_URL ?? 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
