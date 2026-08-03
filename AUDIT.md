# Growth Portal — Audit

Against the vision as stated, not against what was built. Written 3 Aug 2026.

> «بتقرا الداتا أول بأول من المصادر … تقسيمات على مستوى المنتجات والموردين
> والأسواق والكريتيف … بيطلع المشاكل وأقوى حاجة والفرص والحاجات الواقعة …
> بيقيس CRO & CVR & SEO … بيقيس الموبايل أب … تراكينج لشغل الميديا بايرز
> وتحليل أداءهم والـ activity بتاعتهم»

---

## 1. The load-bearing gap: there is no spend in this portal

The stated north star is **cost per delivered order**. The portal cannot compute
it, because seven of eight sources are stubs and ERPNext is the only one wired.

| Source | State | What is blocked without it |
|---|---|---|
| `erpnext` | ✅ complete | — |
| `meta` | stub | spend, ROAS, creative performance, buyer activity |
| `google_ads` | stub | spend, PMAX value, conversion actions |
| `tiktok` | stub | spend, creative, changelog |
| `shopify` | stub | sessions, ATC→purchase, checkout drop-off |
| `clarity` | stub | CRO — rage clicks, dead clicks, scroll depth |
| `semrush` | stub | SEO — positions, organic traffic |
| `ga4` | stub | landing-page CVR, channel mix |
| **AppsFlyer** | **not even a stub** | the entire mobile app measurement ask |

Everything else below is downstream of this. A verdict engine judging delivery
rate is answering a real question, but it is one question out of the set.

**Also missing as data, not as code:**

- **COGS per `item_code`** — without it there is no contribution margin, only
  revenue. "مين محتاج يتقتل" cannot be answered honestly on revenue alone.
- **Control ratios**: only `items_per_order` is computed. The three that
  actually catch a broken feed — `server_events_per_order`, `atc_to_purchase`,
  `delivery_rate` — are declared in the agent's tool contract and never written.
- **Timeline changes**: only ERPNext price moves. No deploys, no budget edits,
  no Meta/Google/TikTok audit logs. This is the layer that made the 9 July
  break diagnosable, and it is currently 5% built.
- **Growth Entity** rows exist for products only. Six of seven segments are empty.

---

## 2. Missing screens

| Screen | Why it matters | State |
|---|---|---|
| **Connections** | Which sources are authorised, when each token was last good, a test button. Right now a dead token is invisible until a sync writes zero rows. | ❌ |
| **Settings** | Thresholds (`gap_act`, `impact_floor`, `min_sample`…) are hard-coded in `analyzers/product.py`. Changing a rule means editing Python. Alert recipients live in `site_config.json`. | ❌ |
| **Overview** | The portal opens straight onto a verdict list. No "what happened yesterday", no trend, no spend-vs-delivered. | ❌ |
| **Entity detail** | `api/dashboard.py:entity()` already returns series + verdicts + changes. **No page consumes it.** Cards are not clickable. | ❌ API only |
| **Timeline** | The change overlay has no view at all. | ❌ |
| **Alerts** | `Growth Alert` doctype is written on every send. No inbox, no delivery status, no retry. | ❌ |
| **Agent runs** | `Agent Run` records the full tool trace. Not visible anywhere. | ❌ |
| Segments | Entity-type switcher. The API takes `entity_type`; the UI never sends it. | ❌ |

## 3. UI/UX gaps in what exists

1. **No feedback on action.** `Acknowledge / Actioned / Dismiss` silently remove
   a card. Task Hub has `Toaster.vue`; this does not use it.
2. **No date range.** The window is hard-coded to 28 days in `tasks.py`.
3. **No charts.** Task Hub ships `TrendChart.vue`. Nothing here plots anything,
   so a rate is a number with no history behind it.
4. **No search.** Fine at 2 verdicts, useless at 200.
5. **Cards are dead ends.** Nothing is clickable; there is no way to ask "why".
6. **No error state.** If the API 500s, the page silently shows sample data.
   The banner says "no connection", which would be a lie for a 500.
7. **No skeletons** on Integrity / Findings / Ask — only Verdicts has them.
8. **No agent progress.** `Ask` blocks on a spinner for what can be a 60-second
   investigation, with no indication of which tool it is running.
9. **Language.** Was Arabic-only. Being fixed in this pass → English default
   with an AR toggle, matching Task Hub.

## 4. Missing features against the stated vision

| Ask | State |
|---|---|
| Products segmentation | ✅ |
| Suppliers | ❌ analyzer is a stub |
| Source markets | ❌ stub |
| Creative | ❌ stub |
| Campaigns | ❌ stub |
| Website CRO / CVR | ❌ no Clarity, no GA4, no Shopify |
| SEO | ❌ no SEMrush |
| Mobile app | ❌ no AppsFlyer source at all |
| Media buyer performance | ❌ stub |
| **Media buyer activity** | ❌ nothing — needs each platform's audit log |
| Problems | ✅ Fix / Kill |
| Strongest performers | ⚠️ Grow verdict exists, never fires without spend data |
| Opportunities | ⚠️ same |
| Dormant items | ❌ `Dormant` verdict is defined and never issued — `dormant_after_days` is declared on `Rule` and unused |
| Alerts (email / WhatsApp) | ⚠️ dispatch written, never exercised |
| Agent advises | ✅ |
| Agent executes | ⛔ deliberately not yet |

---

## 5. Order of work

**First — because everything else is downstream:**
1. `sources/meta.py` + `sources/google_ads.py` + `sources/tiktok.py` → real spend
2. COGS per `item_code` → contribution margin
3. Timeline changes from each platform's audit log

**Second — the screens that make the data usable:**
4. Connections · Settings · Overview
5. Entity detail (API already exists) + timeline view
6. Alerts inbox + agent run history

**Third:**
7. Remaining analyzers, in the order the sources land
8. Clarity / GA4 / SEMrush / AppsFlyer
9. Toasts, charts, search, date range

## 6. What is genuinely done

- `engine/` — guard + verdict, both exercised against real ERPNext rows
- `sources/erpnext.py` — 0 unmapped courier statuses across 1,000 real rows
- `analyzers/product.py` — 79 products judged, one verdict at 8,827 MAD/month
- `agent/` — 6 tools, read-only apart from writing findings
- 10 doctypes, the Frappe shell, packaging, and the Task Hub design system

The foundation is sound. The coverage is roughly one-eighth of the vision.
