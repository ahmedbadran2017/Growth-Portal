/* API layer.

   Talks to the Frappe whitelisted methods. When no bench answers — which is the
   case on a laptop — it falls back to `sample.js` so the interface can be
   reviewed before it is deployed.

   The fallback distinguishes "no server" from "server said no". A 500 shown as
   "not connected" is the same class of lie this whole portal exists to prevent,
   so `state.reason` carries the real cause and the banner reads it. */

import { SAMPLE } from "./sample.js";

export const state = { live: null, reason: "", status: 0 };

async function call(method, params = {}, options = {}) {
  const isWrite = !!options.write;
  const url = `/api/method/growth_portal.api.${method}`;
  const res = await fetch(isWrite ? url : `${url}?${new URLSearchParams(params)}`, {
    method: isWrite ? "POST" : "GET",
    headers: {
      Accept: "application/json",
      ...(isWrite ? { "Content-Type": "application/json" } : {}),
      ...(window.csrf_token ? { "X-Frappe-CSRF-Token": window.csrf_token } : {}),
    },
    ...(isWrite ? { body: JSON.stringify(params) } : {}),
  });
  if (!res.ok) {
    const err = new Error(`HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return (await res.json()).message;
}

async function withFallback(method, params, sampleKey) {
  try {
    const out = await call(method, params);
    state.live = true;
    state.status = 200;
    return out;
  } catch (e) {
    state.live = false;
    state.status = e.status || 0;
    // A network failure means no bench. Anything with a status code means the
    // bench answered and refused — a different problem with a different fix.
    state.reason = e.status
      ? e.status === 403
        ? "forbidden"
        : "error"
      : "offline";
    return SAMPLE[sampleKey];
  }
}

export const api = {
  integrity: () => withFallback("dashboard.integrity", {}, "integrity"),
  verdicts: (p = {}) => withFallback("dashboard.verdicts", p, "verdicts"),
  findings: () => withFallback("dashboard.findings", {}, "findings"),
  entity: (entity_id) => withFallback("dashboard.entity", { entity_id }, "entity"),
  overview: () => withFallback("overview.kpis", {}, "overview"),
  daily: () => withFallback("overview.daily", {}, "daily"),
  suppliers: (p = {}) => withFallback("overview.suppliers", p, "suppliers"),
  products: (p = {}) => withFallback("overview.products", p, "products"),
  buyers: () => withFallback("buyers.performance", {}, "buyers"),
  buyerActivity: () => withFallback("buyers.activity", {}, "buyerActivity"),
  capacity: () => withFallback("capacity.campaigns", {}, "capacity"),
  connections: () => withFallback("config.connections", {}, "connections"),
  settings: () => withFallback("config.settings", {}, "settings"),
  rules: () => withFallback("config.rules", {}, "rules"),
  alerts: () => withFallback("config.alerts", {}, "alerts"),
  agentRuns: () => withFallback("config.agent_runs", {}, "agentRuns"),

  act: (verdict, status) => call("dashboard.act", { verdict, status }, { write: true }),
  ask: (question) => call("dashboard.ask", { question }, { write: true }),
  testConnection: (source) => call("config.test_connection", { source }, { write: true }),
  saveSettings: (payload) => call("config.save_settings", payload, { write: true }),
  saveRule: (payload) => call("config.save_rule", payload, { write: true }),
};

export function money(n) {
  if (n === null || n === undefined) return "—";
  return Math.round(n).toLocaleString("en-US");
}

export function pct(n, d = 1) {
  if (n === null || n === undefined) return "—";
  return Number(n).toFixed(d);
}
