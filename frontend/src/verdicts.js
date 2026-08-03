/* Verdict vocabulary — colour, label key, icon, in one place.

   Five verdicts and nothing else on the page borrows their colours, so a red
   here always means money is leaving. The palette sits alongside the shared
   ink/brand scales rather than inside them: brand is identity, these carry
   meaning.

   Labels are English source strings, passed through t() at render time. */

export const VERDICT = {
  Grow: {
    label: "Grow",
    color: "#0d9488",
    bg: "#ccfbf1",
    ring: "rgba(13,148,136,.28)",
    icon: "trend-up",
    hint: "Above baseline — the same spend buys a better result",
  },
  Fix: {
    label: "Fix",
    // Yellow, not orange. The first pass used amber-700, which on the rust
    // canvas was nearly indistinguishable from the brand accent — the verdict
    // colour has to mean something the brand colour doesn't.
    color: "#a16207",
    bg: "#fef9c3",
    ring: "rgba(161,98,7,.24)",
    icon: "warning",
    hint: "Below baseline by a costly margin",
  },
  Kill: {
    label: "Kill",
    color: "#be123c",
    bg: "#ffe4e6",
    ring: "rgba(190,18,60,.24)",
    icon: "ban",
    hint: "Below the point of viability",
  },
  Dormant: {
    label: "Dormant",
    color: "#6d28d9",
    bg: "#ede9fe",
    ring: "rgba(109,40,217,.24)",
    icon: "hourglass",
    hint: "No activity for a while",
  },
  Watch: {
    label: "Watch",
    color: "#57534e",
    bg: "#f5f5f4",
    ring: "rgba(87,83,78,.22)",
    icon: "circle-dashed",
    hint: "Sample too small for a verdict",
  },
};

export const ORDER = ["Fix", "Kill", "Grow", "Dormant", "Watch"];

/* Who can actually fix the failure. Without this column every failure reads as
   "returns" and lands on nobody's desk. */
export const OWNER = {
  Product: "Product page",
  "Lead Quality": "Lead quality",
  Confirmation: "Confirmation",
  Duplicate: "Duplicate orders",
  Logistics: "Logistics",
  Customer: "Customer",
};

/* The seven entity types the portal segments on. Only Product is implemented;
   the rest are declared so the interface shows what is coming rather than
   pretending the catalogue is the whole business. */
export const ENTITY_TYPES = [
  { key: "Product", label: "Products", icon: "inbox", ready: true },
  { key: "Campaign", label: "Campaigns", icon: "gauge", ready: false },
  { key: "Creative", label: "Creatives", icon: "eye", ready: false },
  { key: "Supplier", label: "Suppliers", icon: "users", ready: false },
  { key: "Source Market", label: "Source markets", icon: "globe", ready: false },
  { key: "Page", label: "Pages", icon: "file", ready: false },
  { key: "Media Buyer", label: "Media buyers", icon: "user", ready: false },
];
