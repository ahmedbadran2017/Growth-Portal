"""Media buyer performance and activity.

Two separate questions that get confused with each other:

**Performance** — what the money a buyer controls returned. Attributed by ad
account, because that is the only ownership boundary the platforms actually
record. A campaign has no owner field; an account does.

**Activity** — what they changed, when, and from which surface. This comes from
the platforms' own audit logs, and the surface matters more than the count: a
budget that moved from `recommendation` was the platform's automation, not the
buyer, and counting it as their work credits them for a decision they did not
make.

Neither number is a verdict. Buyers run different accounts with different
products at different maturities, so ROAS across buyers is not a ranking — it is
a starting point for a conversation. The API says so in its own payload rather
than leaving the reader to assume otherwise.
"""

import frappe

#: account id -> buyer. Configured in site_config.json under
#: `media_buyer_accounts`; the shape is {"act_123": "name@justyol.com"}.
#: Nothing is inferred — an unmapped account reports as Unassigned rather than
#: being silently attached to whoever runs the most accounts.
def _mapping():
    return frappe.conf.get("media_buyer_accounts") or {}


def _buyer_for(account_id):
    m = _mapping()
    if not account_id:
        return "Unassigned"
    a = str(account_id)
    return m.get(a) or m.get(a.replace("act_", "")) or m.get(f"act_{a}") or "Unassigned"


@frappe.whitelist()
def performance(days=30):
    """Spend and platform-reported return per buyer, per platform.

    Kept split by platform on purpose. Meta at ROAS 8.5 and TikTok at 14.7 buy
    different inventory at very different CPMs, so a blended per-buyer ROAS
    mostly measures which platforms that buyer happens to run.
    """
    days = int(days)
    rows = frappe.db.sql(
        """SELECT m.source, m.extra, m.entity_id,
                  SUM(m.spend) spend, SUM(m.revenue) revenue,
                  SUM(m.orders) orders, SUM(m.impressions) impressions
           FROM `tabEntity Metric` m
           WHERE m.entity_type='Campaign'
             AND m.day >= DATE_SUB(CURDATE(), INTERVAL %(d)s DAY)
           GROUP BY m.source, m.entity_id""",
        {"d": days}, as_dict=True,
    )

    agg = {}
    for r in rows:
        try:
            extra = frappe.parse_json(r.extra or "{}")
        except Exception:
            extra = {}
        account = extra.get("account") or extra.get("advertiser_id") or extra.get("customer_id")
        buyer = _buyer_for(account)
        k = (buyer, r.source)
        a = agg.setdefault(k, {"buyer": buyer, "platform": r.source, "spend": 0.0,
                               "revenue": 0.0, "orders": 0.0, "impressions": 0,
                               "campaigns": 0, "accounts": set(),
                               "currency": extra.get("currency")})
        a["spend"] += float(r.spend or 0)
        a["revenue"] += float(r.revenue or 0)
        a["orders"] += float(r.orders or 0)
        a["impressions"] += int(r.impressions or 0)
        a["campaigns"] += 1
        if account:
            a["accounts"].add(str(account))

    out = []
    for a in agg.values():
        spend = a["spend"]
        out.append({
            "buyer": a["buyer"],
            "platform": a["platform"],
            "accounts": sorted(a["accounts"]),
            "campaigns": a["campaigns"],
            "spend": round(spend),
            "platform_revenue": round(a["revenue"]),
            "roas": round(a["revenue"] / spend, 2) if spend else None,
            "orders": round(a["orders"]),
            "cpa": round(spend / a["orders"], 2) if a["orders"] else None,
            "cpm": round(1000 * spend / a["impressions"], 2) if a["impressions"] else None,
            "currency": a["currency"],
        })
    out.sort(key=lambda x: x["spend"], reverse=True)
    return {
        "rows": out,
        "window_days": days,
        "unmapped_accounts": sum(1 for r in out if r["buyer"] == "Unassigned"),
        "note": "Platform-reported ROAS, per platform. Buyers run different "
                "accounts and products — this is not a ranking.",
    }


@frappe.whitelist()
def activity(days=30, buyer=None):
    """What each buyer changed, split by surface.

    `by_surface` is the point. Two buyers with 40 changes each are not
    comparable if one of them is 35 platform recommendations auto-applied.
    """
    days = int(days)
    cond = ""
    if buyer:
        cond = "AND actor = %(b)s"
    rows = frappe.db.sql(
        f"""SELECT actor, surface, entity_type, field_changed, entity_id,
                   day, before_value, after_value, source
            FROM `tabTimeline Change`
            WHERE day >= DATE_SUB(CURDATE(), INTERVAL %(d)s DAY) {cond}
            ORDER BY day DESC
            LIMIT 2000""",
        {"d": days, "b": buyer}, as_dict=True,
    )

    per = {}
    for r in rows:
        a = per.setdefault(r.actor or "unknown", {
            "actor": r.actor or "unknown", "total": 0, "by_surface": {},
            "by_field": {}, "active_days": set(), "last_change": None,
        })
        a["total"] += 1
        a["by_surface"][r.surface or "unknown"] = a["by_surface"].get(r.surface or "unknown", 0) + 1
        f = (r.field_changed or "").split(".")[-1]
        a["by_field"][f] = a["by_field"].get(f, 0) + 1
        a["active_days"].add(str(r.day))
        if not a["last_change"] or str(r.day) > a["last_change"]:
            a["last_change"] = str(r.day)

    summary = []
    for a in per.values():
        human = a["total"] - a["by_surface"].get("recommendation", 0)
        summary.append({
            "actor": a["actor"],
            "total_changes": a["total"],
            # The number that means "work done by a person".
            "human_changes": human,
            "automation_changes": a["by_surface"].get("recommendation", 0),
            "by_surface": a["by_surface"],
            "top_fields": sorted(a["by_field"].items(), key=lambda x: -x[1])[:5],
            "active_days": len(a["active_days"]),
            "last_change": a["last_change"],
        })
    summary.sort(key=lambda x: x["human_changes"], reverse=True)

    return {
        "summary": summary,
        "recent": rows[:120],
        "window_days": days,
        # Said plainly: a buyer whose platform exposes no audit log looks idle
        # here, and that is a gap in the feed, not in their work.
        "coverage": _coverage(),
    }


def _coverage():
    """Which platforms are actually contributing changes.

    Google reports `client_type`, so its rows carry a real surface. Meta's
    activity log does not report one and its rows say `unknown` — that is
    recorded rather than guessed, so nobody reads a fabricated value as fact.
    """
    rows = frappe.db.sql(
        """SELECT source, COUNT(*) n, SUM(surface='unknown') unknown_surface
           FROM `tabTimeline Change`
           WHERE day >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
           GROUP BY source""",
        as_dict=True,
    )
    return [{"source": r.source, "changes": r.n,
             "surface_unknown": int(r.unknown_surface or 0)} for r in rows]
