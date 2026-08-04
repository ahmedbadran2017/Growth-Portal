"""App channel — where AppsFlyer revenue meets platform spend.

This is deliberately **not** a verdict. The engine refuses a cross-source ratio,
and it is right to: spend comes from Google/Meta/TikTok and app revenue comes
from AppsFlyer, so any ROAS here is assembled from two systems that measure
differently and settle on different schedules.

That does not make the number useless — it makes it a number that has to carry a
label. Every row says which system each side came from, and the payload says so
once more at the top. A reader who wants a same-source figure has one: each
platform's own reported ROAS, on the Campaign verdicts.

Cost is taken from the ad platforms, never from AppsFlyer. AppsFlyer reported
$475.81 of Google spend for a window Google itself put at about $47.
"""

import frappe

from growth_portal.engine import guard

#: AppsFlyer reports USD; ad accounts report TRY. Nothing is converted unless a
#: rate is configured, and the rate ships with the response.
def _rate():
    return frappe.conf.get("usd_to_try_rate")


@frappe.whitelist()
def campaigns(days=30):
    """App installs, purchases and revenue per campaign, beside platform spend."""
    days = int(days)

    app = frappe.db.sql(
        """SELECT m.entity_id, m.extra,
                  SUM(m.orders)  AS purchases,
                  SUM(m.revenue) AS revenue_usd,
                  MAX(e.entity_label) AS label
           FROM `tabEntity Metric` m
           LEFT JOIN `tabGrowth Entity` e ON e.entity_key = m.entity_id
           WHERE m.source = 'appsflyer'
             AND m.day >= DATE_SUB(%(gp_today)s, INTERVAL %(d)s DAY)
           GROUP BY m.entity_id""",
        {**guard.clock(), "d": days}, as_dict=True,
    )

    # Spend from the platforms' own APIs, keyed identically — the AppsFlyer
    # adapter writes `google:{id}` / `meta:{id}` on purpose so this join needs
    # no mapping table.
    spend = {
        r.entity_id: r
        for r in frappe.db.sql(
            """SELECT entity_id, source, SUM(spend) spend, SUM(orders) platform_orders,
                      SUM(revenue) platform_revenue
               FROM `tabEntity Metric`
               WHERE entity_type='Campaign' AND source != 'appsflyer'
                 AND day >= DATE_SUB(%(gp_today)s, INTERVAL %(d)s DAY)
               GROUP BY entity_id, source""",
            {**guard.clock(), "d": days}, as_dict=True,
        )
    }

    rate = _rate()
    rows, installs_total, unattributed = [], 0.0, []

    for a in app:
        try:
            extra = frappe.parse_json(a.extra or "{}")
        except Exception:
            extra = {}
        n_installs = float(extra.get("installs") or 0)
        installs_total += n_installs
        purchases = float(a.purchases or 0)
        revenue_usd = float(a.revenue_usd or 0)
        s = spend.get(a.entity_id)

        row = {
            "entity_id": a.entity_id,
            "label": a.label or extra.get("campaign_name") or a.entity_id,
            "platform": extra.get("platform"),
            "media_source": extra.get("media_source"),
            "installs": round(n_installs),
            "purchases": round(purchases),
            "install_to_purchase_pct": round(100.0 * purchases / n_installs, 2) if n_installs else None,
            "revenue_usd": round(revenue_usd, 2),
            "revenue_per_install_usd": round(revenue_usd / n_installs, 2) if n_installs else None,
            # Named `_cross_source` so nobody can read it off a screen and
            # mistake it for the platform's own figure.
            "spend_platform": s.source if s else None,
            "spend": round(float(s.spend or 0)) if s else None,
            "cross_source_roas": None,
            "cost_per_purchase_cross_source": None,
        }

        if s and float(s.spend or 0) > 0 and rate:
            spend_usd = float(s.spend) / rate
            row["spend_usd"] = round(spend_usd, 2)
            row["cross_source_roas"] = round(revenue_usd / spend_usd, 2)
            if purchases:
                row["cost_per_purchase_cross_source"] = round(spend_usd / purchases, 2)
        elif s and float(s.spend or 0) > 0:
            # Spend exists but no rate is configured. Reporting a ratio across
            # two currencies without one would be an invented number.
            row["spend_usd"] = None

        if not s and (extra.get("platform") not in ("organic", "unknown", None)):
            unattributed.append(a.entity_id)

        rows.append(row)

    rows.sort(key=lambda r: -(r["revenue_usd"] or 0))

    return {
        "rows": rows,
        "window_days": days,
        "totals": {
            "installs": round(installs_total),
            "purchases": round(sum(r["purchases"] for r in rows)),
            "revenue_usd": round(sum(r["revenue_usd"] for r in rows), 2),
        },
        "usd_to_try_rate": rate,
        # Stated once at the top and once per row. This is the whole caveat.
        "framing": (
            "Revenue, installs and purchases come from AppsFlyer (USD, UTC, cohort "
            "revenue by install date). Spend comes from each ad platform's own API "
            "(TRY, account timezone). Any ROAS here spans two systems and is "
            "labelled cross-source. AppsFlyer's own cost figures are not used — "
            "they read 10x the platforms' on 29 Jul – 3 Aug 2026."
        ),
        "campaigns_without_platform_spend": unattributed,
    }


@frappe.whitelist()
def sources(days=30):
    """The same picture one level up — by media source rather than campaign.

    Useful because the largest single row is usually `organic`, which has no
    campaign and no spend, and which a campaign-level view hides.
    """
    days = int(days)
    rows = frappe.db.sql(
        """SELECT m.extra, SUM(m.orders) purchases, SUM(m.revenue) revenue_usd
           FROM `tabEntity Metric` m
           WHERE m.source='appsflyer'
             AND m.day >= DATE_SUB(%(gp_today)s, INTERVAL %(d)s DAY)
           GROUP BY m.entity_id""",
        {**guard.clock(), "d": days}, as_dict=True,
    )
    agg = {}
    for r in rows:
        try:
            extra = frappe.parse_json(r.extra or "{}")
        except Exception:
            extra = {}
        ms = extra.get("media_source") or "unknown"
        a = agg.setdefault(ms, {"media_source": ms, "platform": extra.get("platform"),
                                "installs": 0.0, "purchases": 0.0, "revenue_usd": 0.0})
        a["installs"] += float(extra.get("installs") or 0)
        a["purchases"] += float(r.purchases or 0)
        a["revenue_usd"] += float(r.revenue_usd or 0)

    out = []
    for a in agg.values():
        out.append({
            **a,
            "installs": round(a["installs"]),
            "purchases": round(a["purchases"]),
            "revenue_usd": round(a["revenue_usd"], 2),
            "install_to_purchase_pct": (
                round(100.0 * a["purchases"] / a["installs"], 2) if a["installs"] else None
            ),
            "revenue_per_install_usd": (
                round(a["revenue_usd"] / a["installs"], 2) if a["installs"] else None
            ),
        })
    out.sort(key=lambda r: -r["revenue_usd"])
    return {"rows": out, "window_days": days, "denominator_source": "appsflyer"}
