import { defineConfig, loadEnv } from "vite";
import vue from "@vitejs/plugin-vue";
import path from "path";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  // Per-machine proxy target, matching Task Hub. With no bench reachable the
  // API layer falls back to sample data and says so on screen.
  const target = env.FRAPPE_DEV_URL || process.env.FRAPPE_DEV_URL || "http://localhost:8000";

  return {
    plugins: [vue()],
    // Only the build lives under the asset path. In dev the app is served
    // from "/" — the proxy rule below claims /assets for the bench, so a dev
    // base under /assets would have the proxy swallow the app's own files.
    base: mode === "production" ? "/assets/growth_portal/" : "/",
    resolve: {
      alias: { "@": path.resolve(__dirname, "./src") },
    },
    build: {
      outDir: "../growth_portal/public",
      emptyOutDir: false,
      target: "es2015",
      // The Jinja shell hard-codes one JS and one CSS filename — keep the whole
      // SPA in a single bundle so those two names are always right.
      cssCodeSplit: false,
      rollupOptions: {
        input: path.resolve(__dirname, "src/main.js"),
        output: {
          entryFileNames: "growth_portal.bundle.js",
          assetFileNames: "growth_portal.bundle.css",
          inlineDynamicImports: true,
        },
      },
    },
    server: {
      port: 8770,
      proxy: {
        "^/(api|login|app|assets|socket\\.io)": {
          target,
          changeOrigin: true,
          secure: false,
          cookieDomainRewrite: { "*": "" },
          followRedirects: true,
        },
      },
    },
  };
});
