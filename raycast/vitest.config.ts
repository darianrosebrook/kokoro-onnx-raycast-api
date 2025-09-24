import { defineConfig } from "vitest/config";
import path from "path";

export default defineConfig({
  test: {
    globals: true,
    environment: "node",
    watch: false,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
      "@raycast/api": path.resolve(__dirname, "./src/mocks/raycast-api.ts"),
    },
  },
});
