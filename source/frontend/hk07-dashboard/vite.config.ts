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
        timeout: 60000,
        proxyTimeout: 60000,
        // Forward cookies correctly: rewrite domain so browser cookies pass through
        cookieDomainRewrite: 'localhost',
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq, req) => {
            // Explicitly forward Cookie header — required for HttpOnly refresh token
            if (req.headers.cookie) {
              proxyReq.setHeader('Cookie', req.headers.cookie)
            }
          })
        }
      },
      '/ws': {
        target: 'ws://localhost:8888',
        ws: true,
        timeout: 60000,
        proxyTimeout: 60000,
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
