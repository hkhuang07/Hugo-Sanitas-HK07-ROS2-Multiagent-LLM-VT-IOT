// vite.config.ts
import { defineConfig } from "file:///D:/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/source/frontend/hk07-dashboard/node_modules/vite/dist/node/index.js";
import vue from "file:///D:/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/source/frontend/hk07-dashboard/node_modules/@vitejs/plugin-vue/dist/index.mjs";
import { resolve } from "path";
var __vite_injected_original_dirname = "D:\\Study\\HK.Huang_Lab\\hugo-sanitas-hk-07\\hk-07\\source\\frontend\\hk07-dashboard";
var vite_config_default = defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      "@": resolve(__vite_injected_original_dirname, "src")
    }
  },
  server: {
    port: 3010,
    host: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8888",
        changeOrigin: true,
        timeout: 6e4,
        proxyTimeout: 6e4,
        // Forward cookies correctly: rewrite domain so browser cookies pass through
        cookieDomainRewrite: "localhost",
        configure: (proxy) => {
          proxy.on("proxyReq", (proxyReq, req) => {
            if (req.headers.cookie) {
              proxyReq.setHeader("Cookie", req.headers.cookie);
            }
          });
        }
      },
      "/ws": {
        target: "http://127.0.0.1:8888",
        ws: true,
        changeOrigin: true,
        timeout: 6e4,
        proxyTimeout: 6e4
      }
    }
  },
  build: {
    // Single chunk limit warning threshold
    chunkSizeWarningLimit: 500,
    rollupOptions: {
      output: {
        // Manual chunking to optimize caching
        manualChunks: {
          "vue-vendor": ["vue", "vue-router", "pinia"],
          "chart-vendor": ["chart.js"],
          "mqtt-vendor": ["@stomp/stompjs", "sockjs-client"]
        }
      }
    }
  }
});
export {
  vite_config_default as default
};
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsidml0ZS5jb25maWcudHMiXSwKICAic291cmNlc0NvbnRlbnQiOiBbImNvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9kaXJuYW1lID0gXCJEOlxcXFxTdHVkeVxcXFxISy5IdWFuZ19MYWJcXFxcaHVnby1zYW5pdGFzLWhrLTA3XFxcXGhrLTA3XFxcXHNvdXJjZVxcXFxmcm9udGVuZFxcXFxoazA3LWRhc2hib2FyZFwiO2NvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9maWxlbmFtZSA9IFwiRDpcXFxcU3R1ZHlcXFxcSEsuSHVhbmdfTGFiXFxcXGh1Z28tc2FuaXRhcy1oay0wN1xcXFxoay0wN1xcXFxzb3VyY2VcXFxcZnJvbnRlbmRcXFxcaGswNy1kYXNoYm9hcmRcXFxcdml0ZS5jb25maWcudHNcIjtjb25zdCBfX3ZpdGVfaW5qZWN0ZWRfb3JpZ2luYWxfaW1wb3J0X21ldGFfdXJsID0gXCJmaWxlOi8vL0Q6L1N0dWR5L0hLLkh1YW5nX0xhYi9odWdvLXNhbml0YXMtaGstMDcvaGstMDcvc291cmNlL2Zyb250ZW5kL2hrMDctZGFzaGJvYXJkL3ZpdGUuY29uZmlnLnRzXCI7aW1wb3J0IHsgZGVmaW5lQ29uZmlnIH0gZnJvbSAndml0ZSdcbmltcG9ydCB2dWUgZnJvbSAnQHZpdGVqcy9wbHVnaW4tdnVlJ1xuaW1wb3J0IHsgcmVzb2x2ZSB9IGZyb20gJ3BhdGgnXG5cbi8vIEhhcmR3YXJlIG9wdGltaXphdGlvbjogc2luZ2xlLXRocmVhZGVkIGJ1aWxkIGZvciAxLjZHSHogQ1BVXG4vLyBTZXQgTk9ERV9PUFRJT05TPVwiLS1tYXgtb2xkLXNwYWNlLXNpemU9MTAyNFwiIGJlZm9yZSBydW5uaW5nIG5wbSBydW4gYnVpbGRcblxuZXhwb3J0IGRlZmF1bHQgZGVmaW5lQ29uZmlnKHtcbiAgcGx1Z2luczogW3Z1ZSgpXSxcbiAgcmVzb2x2ZToge1xuICAgIGFsaWFzOiB7XG4gICAgICAnQCc6IHJlc29sdmUoX19kaXJuYW1lLCAnc3JjJyksXG4gICAgfSxcbiAgfSxcbiAgc2VydmVyOiB7XG4gICAgcG9ydDogMzAxMCxcbiAgICBob3N0OiB0cnVlLFxuICAgIHByb3h5OiB7XG4gICAgICAnL2FwaSc6IHtcbiAgICAgICAgdGFyZ2V0OiAnaHR0cDovLzEyNy4wLjAuMTo4ODg4JyxcbiAgICAgICAgY2hhbmdlT3JpZ2luOiB0cnVlLFxuICAgICAgICB0aW1lb3V0OiA2MDAwMCxcbiAgICAgICAgcHJveHlUaW1lb3V0OiA2MDAwMCxcbiAgICAgICAgLy8gRm9yd2FyZCBjb29raWVzIGNvcnJlY3RseTogcmV3cml0ZSBkb21haW4gc28gYnJvd3NlciBjb29raWVzIHBhc3MgdGhyb3VnaFxuICAgICAgICBjb29raWVEb21haW5SZXdyaXRlOiAnbG9jYWxob3N0JyxcbiAgICAgICAgY29uZmlndXJlOiAocHJveHkpID0+IHtcbiAgICAgICAgICBwcm94eS5vbigncHJveHlSZXEnLCAocHJveHlSZXEsIHJlcSkgPT4ge1xuICAgICAgICAgICAgLy8gRXhwbGljaXRseSBmb3J3YXJkIENvb2tpZSBoZWFkZXIgXHUyMDE0IHJlcXVpcmVkIGZvciBIdHRwT25seSByZWZyZXNoIHRva2VuXG4gICAgICAgICAgICBpZiAocmVxLmhlYWRlcnMuY29va2llKSB7XG4gICAgICAgICAgICAgIHByb3h5UmVxLnNldEhlYWRlcignQ29va2llJywgcmVxLmhlYWRlcnMuY29va2llKVxuICAgICAgICAgICAgfVxuICAgICAgICAgIH0pXG4gICAgICAgIH1cbiAgICAgIH0sXG4gICAgICAnL3dzJzoge1xuICAgICAgICB0YXJnZXQ6ICdodHRwOi8vMTI3LjAuMC4xOjg4ODgnLFxuICAgICAgICB3czogdHJ1ZSxcbiAgICAgICAgY2hhbmdlT3JpZ2luOiB0cnVlLFxuICAgICAgICB0aW1lb3V0OiA2MDAwMCxcbiAgICAgICAgcHJveHlUaW1lb3V0OiA2MDAwMCxcbiAgICAgIH0sXG4gICAgfSxcbiAgfSxcbiAgYnVpbGQ6IHtcbiAgICAvLyBTaW5nbGUgY2h1bmsgbGltaXQgd2FybmluZyB0aHJlc2hvbGRcbiAgICBjaHVua1NpemVXYXJuaW5nTGltaXQ6IDUwMCxcbiAgICByb2xsdXBPcHRpb25zOiB7XG4gICAgICBvdXRwdXQ6IHtcbiAgICAgICAgLy8gTWFudWFsIGNodW5raW5nIHRvIG9wdGltaXplIGNhY2hpbmdcbiAgICAgICAgbWFudWFsQ2h1bmtzOiB7XG4gICAgICAgICAgJ3Z1ZS12ZW5kb3InOiBbJ3Z1ZScsICd2dWUtcm91dGVyJywgJ3BpbmlhJ10sXG4gICAgICAgICAgJ2NoYXJ0LXZlbmRvcic6IFsnY2hhcnQuanMnXSxcbiAgICAgICAgICAnbXF0dC12ZW5kb3InOiBbJ0BzdG9tcC9zdG9tcGpzJywgJ3NvY2tqcy1jbGllbnQnXSxcbiAgICAgICAgfSxcbiAgICAgIH0sXG4gICAgfSxcbiAgfSxcbn0pXG4iXSwKICAibWFwcGluZ3MiOiAiO0FBQXlhLFNBQVMsb0JBQW9CO0FBQ3RjLE9BQU8sU0FBUztBQUNoQixTQUFTLGVBQWU7QUFGeEIsSUFBTSxtQ0FBbUM7QUFPekMsSUFBTyxzQkFBUSxhQUFhO0FBQUEsRUFDMUIsU0FBUyxDQUFDLElBQUksQ0FBQztBQUFBLEVBQ2YsU0FBUztBQUFBLElBQ1AsT0FBTztBQUFBLE1BQ0wsS0FBSyxRQUFRLGtDQUFXLEtBQUs7QUFBQSxJQUMvQjtBQUFBLEVBQ0Y7QUFBQSxFQUNBLFFBQVE7QUFBQSxJQUNOLE1BQU07QUFBQSxJQUNOLE1BQU07QUFBQSxJQUNOLE9BQU87QUFBQSxNQUNMLFFBQVE7QUFBQSxRQUNOLFFBQVE7QUFBQSxRQUNSLGNBQWM7QUFBQSxRQUNkLFNBQVM7QUFBQSxRQUNULGNBQWM7QUFBQTtBQUFBLFFBRWQscUJBQXFCO0FBQUEsUUFDckIsV0FBVyxDQUFDLFVBQVU7QUFDcEIsZ0JBQU0sR0FBRyxZQUFZLENBQUMsVUFBVSxRQUFRO0FBRXRDLGdCQUFJLElBQUksUUFBUSxRQUFRO0FBQ3RCLHVCQUFTLFVBQVUsVUFBVSxJQUFJLFFBQVEsTUFBTTtBQUFBLFlBQ2pEO0FBQUEsVUFDRixDQUFDO0FBQUEsUUFDSDtBQUFBLE1BQ0Y7QUFBQSxNQUNBLE9BQU87QUFBQSxRQUNMLFFBQVE7QUFBQSxRQUNSLElBQUk7QUFBQSxRQUNKLGNBQWM7QUFBQSxRQUNkLFNBQVM7QUFBQSxRQUNULGNBQWM7QUFBQSxNQUNoQjtBQUFBLElBQ0Y7QUFBQSxFQUNGO0FBQUEsRUFDQSxPQUFPO0FBQUE7QUFBQSxJQUVMLHVCQUF1QjtBQUFBLElBQ3ZCLGVBQWU7QUFBQSxNQUNiLFFBQVE7QUFBQTtBQUFBLFFBRU4sY0FBYztBQUFBLFVBQ1osY0FBYyxDQUFDLE9BQU8sY0FBYyxPQUFPO0FBQUEsVUFDM0MsZ0JBQWdCLENBQUMsVUFBVTtBQUFBLFVBQzNCLGVBQWUsQ0FBQyxrQkFBa0IsZUFBZTtBQUFBLFFBQ25EO0FBQUEsTUFDRjtBQUFBLElBQ0Y7QUFBQSxFQUNGO0FBQ0YsQ0FBQzsiLAogICJuYW1lcyI6IFtdCn0K
