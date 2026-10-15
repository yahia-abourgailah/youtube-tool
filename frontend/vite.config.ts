import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: (process.env.VITE_ALLOWED_HOSTS ?? '').split(',').map((host) => host.trim()).filter(Boolean),
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:7080',
        changeOrigin: true,
      }
    }
  }
})
