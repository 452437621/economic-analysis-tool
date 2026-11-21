import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vitest/config";
import vue from "@vitejs/plugin-vue";

// 单元测试配置：与 vite.config.ts 保持同一 `@` 别名，使用 happy-dom 提供 DOM。
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  test: {
    environment: "happy-dom",
    include: ["src/**/*.spec.ts"],
    setupFiles: ["./src/test/setup.ts"],
  },
});
