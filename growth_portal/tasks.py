"""Scheduled work — sync, judge, then hand the result to the agent.

Order is fixed and matters. Analyzers read what sync wrote, and the agent reads
what the analyzers wrote; running the agent on a failed sync produces a
confident report about yesterday's data.

Every stage records what it did in Source Sync, including the failures. A run
that wrote nothing is a finding in itself.
"""

import json
import time
from datetime import date, timedelta

import frappe

from growth_portal.notify import dispatch
from growth_portal.sources.erpnext import TRACKING

#: Registered adapters. A source is added here only once it actually returns
#: rows — a registered-but-stubbed source makes the health strip lie green.
SOURCES = {
    "erpnext": "growth_portal.sources.erpnext.ERPNextSource",
    "meta": "growth_portal.sources.meta.MetaSource",
    "google_ads": "growth_portal.sources.google_ads.GoogleAdsSource",
    "tiktok": "growth_portal.sources.tiktok.TikTokSource",
}

ANALYZERS = {
    "Product": "growth_portal.analyzers.product.ProductAnalyzer",
    "Campaign": "growth_portal.analyzers.campaign.CampaignAnalyzer",
    "Supplier": "growth_portal.analyzers.supplier.SupplierAnalyzer",
    "Media Buyer": "growth_portal.analyzers.media_buyer.MediaBuyerAnalyzer",
}

#: The judging window. Two weeks is the shortest span where this catalogue's
#: delivery rates stop swinging on single-day noise.
WINDOW_DAYS = 28


def _load(path):
    return frappe.get_attr(path)()


def _record_sync(source, ok, rows, ms, detail):
    day = frappe.utils.today()
    name = f"{source}::{day}"
    doc = {"doctype": "Source Sync", "source": source, "run_day": day,
           "ok": 1 if ok else 0, "rows_written": rows, "duration_ms": ms,
           "detail": json.dumps(detail, ensure_ascii=False, default=str)[:5000]}
    if frappe.db.exists("Source Sync", name):
        frappe.db.set_value("Source Sync", name, doc)
    else:
        frappe.get_doc(doc).insert(ignore_permissions=True)
    frappe.db.commit()


def sync_source(key, days=3):
    """Pull one source. Re-pulls recent days on purpose — they are still moving.

    ERPNext backfills, TikTok lags a day or two, PMAX value lands up to 72
    hours late. Writing a day once and never revisiting it freezes a number
    that was never final.
    """
    src = _load(SOURCES[key])
    t0 = time.time()
    date_to = date.today() + timedelta(days=1)
    date_from = date_to - timedelta(days=days + 1)
    written = 0
    try:
        for e in src.entities():
            _upsert_entity(e, src.name)
        for m in src.metrics(date_from, date_to):
            _upsert_metric(m, src.name, src.maturity_hours)
            written += 1
        for c in src.changes(date_from, date_to):
            _upsert_change(c, src.name)
        frappe.db.commit()

        health = src.health()
        ok = bool(health.get("ok")) and written > 0
        _record_sync(key, ok, written, int((time.time() - t0) * 1000), health)
        if not ok:
            dispatch.send_sync_failure(key, health)
    except Exception:
        tb = frappe.get_traceback()
        _record_sync(key, False, written, int((time.time() - t0) * 1000), {"error": tb[:2000]})
        dispatch.send_sync_failure(key, tb)
        raise
    return written


def _upsert_entity(e, source):
    if frappe.db.exists("Growth Entity", {"entity_key": e.key}):
        frappe.db.set_value("Growth Entity", {"entity_key": e.key},
                            {"entity_label": e.label, "is_active": 1})
        return
    frappe.get_doc({"doctype": "Growth Entity", "entity_key": e.key,
                    "entity_type": e.entity_type, "entity_label": e.label,
                    "parent_key": e.parent_key, "source": source,
                    "is_active": 1}).insert(ignore_permissions=True)


def _maturity(day, hours):
    age = (date.today() - day).days * 24
    if age < hours:
        return "Provisional"
    return "Maturing" if age < hours * 2 else "Final"


def _upsert_metric(m, source, maturity_hours):
    name = f"{m.entity_type}::{m.key}::{source}::{m.day}"
    payload = {
        "entity_type": m.entity_type, "entity_id": m.key, "source": source,
        "day": m.day, "maturity": _maturity(m.day, maturity_hours),
        "spend": m.spend, "revenue": m.revenue, "orders": m.orders,
        "delivered": m.delivered, "clicks": m.clicks,
        "impressions": m.impressions, "sessions": m.sessions,
        "budget": m.budget, "budget_type": m.budget_type,
        "delivery_status": m.delivery_status,
        "extra": json.dumps(m.extra, ensure_ascii=False, default=str),
    }
    if frappe.db.exists("Entity Metric", name):
        frappe.db.set_value("Entity Metric", name, payload)
    else:
        frappe.get_doc(dict(doctype="Entity Metric", **payload)).insert(ignore_permissions=True)


def _upsert_change(c, source):
    exists = frappe.db.exists("Timeline Change", {
        "day": c.day, "entity_id": c.key, "field_changed": c.field_changed,
        "after_value": c.after,
    })
    if exists:
        return
    frappe.get_doc({
        "doctype": "Timeline Change", "day": c.day, "entity_type": c.entity_type,
        "entity_id": c.key, "actor": c.actor, "surface": c.surface,
        "field_changed": c.field_changed, "before_value": c.before,
        "after_value": c.after, "source": source,
    }).insert(ignore_permissions=True)


def judge_all():
    """Run every analyzer over the standard window."""
    # Yesterday, not today. Both bounds are inclusive, and the guard refuses a
    # window whose last day is still maturing — today never qualifies.
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=WINDOW_DAYS - 1)
    out = {}
    for entity_type, path in ANALYZERS.items():
        try:
            res = _load(path).run(start, end)
            out[entity_type] = {"rows": res.rows_considered,
                                "verdicts": len(res.verdicts),
                                "baseline": res.baseline}
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Growth Portal: {entity_type} analyzer")
            out[entity_type] = {"error": True}
    frappe.db.commit()
    return out


def _write_ratio(metric, day, numerator, denominator, source, baseline, threshold=15.0):
    name = f"{metric}::{day}"
    ratio = (numerator / denominator) if denominator else 0.0
    dev = 100.0 * (ratio - baseline) / baseline if baseline else 0.0
    payload = {"metric": metric, "day": day, "numerator": numerator,
               "denominator": denominator, "denominator_source": source,
               "ratio": ratio, "baseline": baseline, "deviation_pct": dev,
               "is_anomaly": 1 if abs(dev) >= threshold else 0}
    if frappe.db.exists("Control Ratio", name):
        frappe.db.set_value("Control Ratio", name, payload)
    else:
        frappe.get_doc(dict(doctype="Control Ratio", **payload)).insert(ignore_permissions=True)


def control_ratios():
    """Recompute the integrity ratios and flag deviations.

    A ratio only counts when both sides come from one system. Anything measured
    across two systems moves when either one changes, which makes it useless as
    an alarm — it was exactly that kind of comparison that once turned a normal
    pre-dedup event ratio into a phantom bug.

    Four ratios, each catching a different break:

      items_per_order        basket composition — caught the AOV decline
      confirmation_rate      the call centre stopping, or lead quality collapsing
      delivery_rate          the courier, or a product page mismatch
      atc_to_purchase        the site funnel, and the first thing to move when
                             a tag dies

    Each baseline is the trailing mean of the series itself, so a seasonal or
    courier-wide shift moves the bar with it instead of firing every day.
    """
    written = 0

    # 1 & 2 — both sides from ERPNext.
    rows = frappe.db.sql(
        """SELECT DATE(so.creation) AS day,
                  COUNT(DISTINCT so.name) AS orders,
                  SUM(so.custom_sales_status = 'Confirmed') AS confirmed,
                  (SELECT SUM(soi.qty) FROM `tabSales Order Item` soi
                    WHERE soi.parent = so.name) AS x
           FROM `tabSales Order` so
           WHERE so.creation >= DATE_SUB(CURDATE(), INTERVAL 60 DAY)
           GROUP BY DATE(so.creation) ORDER BY day""",
        as_dict=True,
    )
    items = frappe.db.sql(
        """SELECT DATE(so.creation) AS day, SUM(soi.qty) items, COUNT(DISTINCT so.name) orders
           FROM `tabSales Order` so
           JOIN `tabSales Order Item` soi ON soi.parent = so.name
           WHERE so.creation >= DATE_SUB(CURDATE(), INTERVAL 60 DAY)
           GROUP BY DATE(so.creation) ORDER BY day""",
        as_dict=True,
    )

    ipo = [(r.day, r.items or 0, r.orders) for r in items if r.orders]
    if len(ipo) >= 14:
        base = sum(i / o for _, i, o in ipo) / len(ipo)
        for day, i, o in ipo:
            _write_ratio("items_per_order", day, i, o, "erpnext", base)
            written += 1

    conf = [(r.day, r.confirmed or 0, r.orders) for r in rows if r.orders]
    if len(conf) >= 14:
        base = sum(c / o for _, c, o in conf) / len(conf)
        # Tighter threshold than the others. Confirmation moves slowly, so a
        # 15% swing would be a catastrophe rather than an early warning.
        for day, c, o in conf:
            _write_ratio("confirmation_rate", day, c, o, "erpnext", base, threshold=8.0)
            written += 1

    # 3 — the courier's last word per order, resolved orders only.
    deliv = frappe.db.sql(
        f"""SELECT DATE(t.d) day, COUNT(*) resolved,
                   SUM(t.status_name LIKE 'Livr%%') delivered
            FROM (
                SELECT so.creation d, x.delivery_status_name AS status_name,
                       ROW_NUMBER() OVER (PARTITION BY x.sales_order
                                          ORDER BY x.creation DESC, x.modified DESC) rn
                FROM `{TRACKING}` x
                JOIN `tabSales Order` so ON so.name = x.sales_order
                WHERE so.creation >= DATE_SUB(CURDATE(), INTERVAL 60 DAY)
            ) t
            WHERE t.rn = 1
              AND t.status_name NOT LIKE 'Hub%%'
              AND t.status_name NOT LIKE 'En Attente%%'
              AND t.status_name NOT LIKE 'Mise En Distribution%%'
            GROUP BY DATE(t.d) ORDER BY day""",
        as_dict=True,
    )
    dl = [(r.day, r.delivered or 0, r.resolved) for r in deliv if r.resolved]
    if len(dl) >= 14:
        base = sum(d / r for _, d, r in dl) / len(dl)
        for day, d, r in dl:
            _write_ratio("delivery_rate", day, d, r, "erpnext", base, threshold=10.0)
            written += 1

    # 4 — the site funnel. Both sides from the same platform's pixel, never
    # a platform numerator over an ERPNext denominator.
    atc = frappe.db.sql(
        """SELECT day, source, extra FROM `tabEntity Metric`
           WHERE entity_type='Campaign' AND day >= DATE_SUB(CURDATE(), INTERVAL 60 DAY)
             AND extra LIKE '%%add_to_cart%%'""",
        as_dict=True,
    )
    per_day = {}
    for r in atc:
        try:
            funnel = (frappe.parse_json(r.extra or "{}") or {}).get("funnel") or {}
        except Exception:
            continue
        a = per_day.setdefault(r.day, [0.0, 0.0])
        a[0] += float(funnel.get("offsite_conversion.fb_pixel_add_to_cart") or 0)
    purch = frappe.db.sql(
        """SELECT day, SUM(orders) o FROM `tabEntity Metric`
           WHERE entity_type='Campaign' AND source='meta'
             AND day >= DATE_SUB(CURDATE(), INTERVAL 60 DAY)
           GROUP BY day""",
        as_dict=True,
    )
    for r in purch:
        if r.day in per_day:
            per_day[r.day][1] = float(r.o or 0)
    series = [(d, v[1], v[0]) for d, v in sorted(per_day.items()) if v[0]]
    if len(series) >= 14:
        base = sum(p / a for _, p, a in series) / len(series)
        for day, p, a in series:
            _write_ratio("atc_to_purchase", day, p, a, "meta", base)
            written += 1

    frappe.db.commit()
    return written


def hourly():
    for key in SOURCES:
        try:
            sync_source(key)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Growth Portal: sync {key}")


def daily():
    hourly()
    control_ratios()
    judge_all()

    # Before the agent runs, so a step that failed its own test is already a
    # finding by the time the analyst reads the day.
    from growth_portal.api import commitments

    try:
        commitments.review()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Growth Portal: commitment review")
    from growth_portal.agent import runtime

    try:
        runtime.run(task="daily")
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Growth Portal: agent daily")
