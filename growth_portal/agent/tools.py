"""Tool contracts.

Read tools plus two that write into review tables. There is no tool that
touches an ad platform — the agent proposes, a human executes.

Each tool returns its own denominator and window alongside the number, so a
finding can be re-checked without going back to the code. `ratio` refuses a
cross-source denominator outright rather than returning something the agent
would then have to be trusted not to misuse.
"""

import json

import frappe
from anthropic import beta_tool

from growth_portal.engine import guard


@beta_tool
def erp_orders(date_from: str, date_to: str, group_by: str = "day") -> str:
    """Real orders and delivery outcomes from ERPNext (Europe/Istanbul).

    Args:
        date_from: YYYY-MM-DD inclusive.
        date_to: YYYY-MM-DD exclusive.
        group_by: day | item | outcome | reason_owner
    """
    col = {"day": "DATE(o.order_date)", "item": "o.entity_id",
           "outcome": "o.outcome", "reason_owner": "o.reason_category"}.get(group_by, "DATE(o.order_date)")
    rows = frappe.db.sql(
        f"""SELECT {col} AS k, COUNT(*) n,
                   SUM(CASE WHEN o.outcome='Delivered' THEN 1 ELSE 0 END) delivered,
                   SUM(o.amount) amount
            FROM `tabDelivery Outcome` o
            WHERE o.order_date >= %(f)s AND o.order_date < %(t)s AND o.is_terminal=1
            GROUP BY k ORDER BY n DESC LIMIT 200""",
        {"f": date_from, "t": date_to}, as_dict=True,
    )
    return json.dumps({"rows": rows, "denominator_source": "erpnext",
                       "note": "resolved orders only; in-transit excluded",
                       "window": [date_from, date_to]}, ensure_ascii=False, default=str)


@beta_tool
def entity_metrics(entity_type: str, date_from: str, date_to: str, source: str = "") -> str:
    """Daily series for one entity type, optionally from one source only.

    Args:
        entity_type: Product | Supplier | Campaign | Creative | Page | Media Buyer | Source Market
        date_from: YYYY-MM-DD inclusive.
        date_to: YYYY-MM-DD exclusive.
        source: erpnext | meta | google_ads | tiktok | shopify | clarity | semrush | ga4
    """
    cond = "AND m.source=%(s)s" if source else ""
    rows = frappe.db.sql(
        f"""SELECT m.day, m.entity_id, m.source, m.spend, m.revenue, m.orders,
                   m.delivered, m.clicks, m.impressions
            FROM `tabEntity Metric` m
            WHERE m.entity_type=%(e)s AND m.day >= %(f)s AND m.day < %(t)s {cond}
            ORDER BY m.day DESC LIMIT 1000""",
        {"e": entity_type, "f": date_from, "t": date_to, "s": source}, as_dict=True,
    )
    return json.dumps({"rows": rows, "window": [date_from, date_to],
                       "source_filter": source or "all"}, ensure_ascii=False, default=str)


@beta_tool
def ratio(metric: str, date_from: str, date_to: str) -> str:
    """A control ratio against its own baseline — the integrity check.

    Both sides come from one system by construction; a cross-source request is
    refused rather than answered.

    Args:
        metric: server_events_per_order | delivery_rate | atc_to_purchase | items_per_order
        date_from: YYYY-MM-DD inclusive.
        date_to: YYYY-MM-DD exclusive.
    """
    try:
        rows = frappe.db.sql(
            """SELECT c.day, c.numerator, c.denominator, c.ratio, c.baseline,
                      c.deviation_pct, c.denominator_source
               FROM `tabControl Ratio` c
               WHERE c.metric=%(m)s AND c.day >= %(f)s AND c.day < %(t)s
               ORDER BY c.day DESC LIMIT 120""",
            {"m": metric, "f": date_from, "t": date_to}, as_dict=True,
        )
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    return json.dumps({"metric": metric, "rows": rows}, ensure_ascii=False, default=str)


@beta_tool
def timeline_changes(date_from: str, date_to: str, entity_type: str = "") -> str:
    """What changed, and who changed it — deploys, budget edits, config edits.

    This is the overlay that makes a break diagnosable: four systems once broke
    on one day and only a shared timeline showed it.

    Args:
        date_from: YYYY-MM-DD inclusive.
        date_to: YYYY-MM-DD exclusive.
        entity_type: optional filter.
    """
    cond = "AND entity_type=%(e)s" if entity_type else ""
    rows = frappe.db.sql(
        f"""SELECT day, entity_type, entity_id, actor, surface, field_changed, before_value, after_value
            FROM `tabTimeline Change`
            WHERE day >= %(f)s AND day < %(t)s {cond}
            ORDER BY day DESC LIMIT 300""",
        {"f": date_from, "t": date_to, "e": entity_type}, as_dict=True,
    )
    return json.dumps({"rows": rows}, ensure_ascii=False, default=str)


@beta_tool
def open_verdicts(entity_type: str = "", limit: int = 20) -> str:
    """Open verdicts, ranked by monthly money impact.

    Args:
        entity_type: optional filter.
        limit: max rows.
    """
    cond = "AND entity_type=%(e)s" if entity_type else ""
    rows = frappe.db.sql(
        f"""SELECT name, entity_type, entity_id, entity_label, verdict, impact_mad,
                   headline, recommended_action, numerator, denominator,
                   denominator_source, window_start, window_end, sample_size, evidence
            FROM `tabGrowth Verdict`
            WHERE status='Open' {cond}
            ORDER BY impact_mad DESC LIMIT %(l)s""",
        {"e": entity_type, "l": int(limit)}, as_dict=True,
    )
    return json.dumps({"rows": rows}, ensure_ascii=False, default=str)


@beta_tool
def write_finding(title: str, severity: str, body: str, evidence_json: str,
                  entity_type: str = "", entity_id: str = "") -> str:
    """Record an investigation result. Requires evidence; rejected without it.

    Args:
        title: one sentence with the number in it.
        severity: Critical | High | Medium | Low
        body: what was found and what to do.
        evidence_json: must contain numerator, denominator, denominator_source, window_start, window_end, query_ref.
        entity_type: optional.
        entity_id: optional stable key.
    """
    try:
        ev = json.loads(evidence_json)
        guard.assert_evidence(ev)
    except Exception as e:
        return json.dumps({"rejected": str(e)}, ensure_ascii=False)

    doc = frappe.get_doc({
        "doctype": "Growth Finding", "title": title[:140], "severity": severity,
        "body": body, "evidence": evidence_json,
        "entity_type": entity_type or None, "entity_id": entity_id or None,
        "status": "Open",
    }).insert(ignore_permissions=True)
    frappe.db.commit()
    return json.dumps({"created": doc.name}, ensure_ascii=False)


TOOLS = [erp_orders, entity_metrics, ratio, timeline_changes, open_verdicts, write_finding]
