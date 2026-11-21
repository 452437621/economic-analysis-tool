import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

// 产物直接输出到仓库根 web/，由 FastAPI（backend/app/main.py）托管；web/ 是构建产物，不入版本库。
const backend = `http://127.0.0.1:${process.env.EPIC_PORT || "8765"}`;

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: { "/api": backend, "/healthz": backend },
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
