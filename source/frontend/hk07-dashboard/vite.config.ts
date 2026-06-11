import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// Hardware optimization: single-threaded build for 1.6GHz CPU
// Set NODE_OPTIONS="--max-old-space-size=1024" before running npm run build

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 3000,
    host: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8888',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8888',
        ws: true,
      },
    },
  },
  build: {
    // Single chunk limit warning threshold
    chunkSizeWarningLimit: 500,
    rollupOptions: {
      output: {
        // Manual chunking to optimize caching
        manualChunks: {
          'vue-vendor': ['vue', 'vue-router', 'pinia'],
          'chart-vendor': ['chart.js'],
          'mqtt-vendor': ['@stomp/stompjs', 'sockjs-client'],
        },
      },
    },
  },
})
