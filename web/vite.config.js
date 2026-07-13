import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3020,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8020',
        changeOrigin: true,
      },
    },
  },
})
