import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

// 产物直接输出到仓库根 web/，由 FastAPI（backend/app/main.py）托管。
// 旧版入口保留在 web-legacy/index.html，通过 /legacy 访问。
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: { "/api": "http://127.0.0.1:8765", "/healthz": "http://127.0.0.1:8765" },
  },
  build: {
    outDir: "../web",
    emptyOutDir: true,
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        manualChunks: {
          echarts: ["echarts", "vue-echarts"],
          vendor: ["vue", "vue-router", "pinia", "@vueuse/core"],
        },
      },
    },
  },
});
