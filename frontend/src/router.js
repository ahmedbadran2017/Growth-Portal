import { createRouter, createWebHistory } from "vue-router";

const routes = [
  { path: "/", redirect: "/overview" },
  { path: "/overview", component: () => import("./pages/Overview.vue") },
  { path: "/segments", component: () => import("./pages/Segments.vue") },
  { path: "/buyers", component: () => import("./pages/Buyers.vue") },
  { path: "/verdicts", component: () => import("./pages/Verdicts.vue") },
  { path: "/findings", component: () => import("./pages/Findings.vue") },
  { path: "/integrity", component: () => import("./pages/Integrity.vue") },
  { path: "/ask", component: () => import("./pages/Ask.vue") },
  { path: "/connections", component: () => import("./pages/Connections.vue") },
  { path: "/settings", component: () => import("./pages/Settings.vue") },
];

// Frappe serves the SPA under one route; everything below it is client-side.
export default createRouter({
  history: createWebHistory(import.meta.env.DEV ? "/" : "/growth/"),
  routes,
});
