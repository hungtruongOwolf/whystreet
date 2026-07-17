import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Load env vars (VITE_*) from the repo root .env (whystreet/.env),
// so we don't duplicate keys into frontend/.env.
export default defineConfig({
  plugins: [react()],
  envDir: '..',
  server: {
    port: 5173,
    proxy: { '/api': 'http://localhost:8000' },
  },
})
