"""Read endpoints for the frontend.

Everything the UI can show comes back with its evidence attached — the
denominator, its source, and the window. The interface should never be able to
display a number the user can't trace, because the whole failure mode this
portal exists to prevent is a confident chart built on a broken feed.
"""

import json
from datetime import date, timedelta

import frappe


@frappe.whitelist()
def integrity():
    """The health strip. Rendered first, above everything else.

    Deliberately at the top: a green verdict list sitting over a dead feed is
    worse than no portal at all.
    """
    syncs = frappe.db.sql(
        """SELECT source, run_day, ok, rows_written, duration_ms
           FROM `tabSource Sync`
           WHERE run_day >= DATE_SUB(CURDATE(), INTERVAL 2 DAY)
           ORDER BY run_day DESC, source""",
        as_dict=True,
    )
    anomalies = frappe.db.sql(
        """SELECT metric, day, ratio, baseline, deviation_pct
           FROM `tabControl Ratio`
           WHERE is_anomaly = 1 AND day >= DATE_SUB(CURDATE(), INTERVAL 14 DAY)
           ORDER BY day DESC LIMIT 20""",
        as_dict=True,
    )
    stale = frappe.db.sql(
        """SELECT source, MAX(day) AS latest FROM `tabEntity Metric`
           GROUP BY source""",
        as_dict=True,
    )
    return {"syncs": syncs, "anomalies": anomalies, "freshness": stale,
            "checked_at": frappe.utils.now()}


@frappe.whitelist()
def verdicts(entity_type=None, status="Open", limit=50):
    """Verdicts ranked by money, not by percentage.

    Ranking by gap size reports the loudest problem; ranking by impact reports
    the biggest one. They are frequently not the same entity.
    """
    cond, params = ["status = %(status)s"], {"status": status, "limit": int(limit)}
    if entity_type:
        cond.append("entity_type = %(et)s")
        params["et"] = entity_type

    rows = frappe.db.sql(
        f"""SELECT name, entity_type, entity_id, entity_label, verdict, metric,
                   impact_mad, headline, recommended_action, numerator, denominator,
                   denominator_source, window_start, window_end, sample_size,
                   evidence, query_ref, modified
            FROM `tabGrowth Verdict`
            WHERE {' AND '.join(cond)}
            ORDER BY impact_mad DESC
            LIMIT %(limit)s""",
        params, as_dict=True,
    )
    for r in rows:
        try:
            r["evidence"] = json.loads(r["evidence"]) if r["evidence"] else {}
        except Exception:
            r["evidence"] = {}
    return rows


@frappe.whitelist()
def entity(entity_id, days=60):
    """One entity: its series, its verdicts, and what changed underneath it.

    The changes are the point. A rate that moved is a question; a rate that
    moved the same week the price did is an answer.
    """
    start = date.today() - timedelta(days=int(days))
    return {
        "entity": frappe.db.get_value(
            "Growth Entity", {"entity_key": entity_id},
            ["entity_key", "entity_type", "entity_label", "source"], as_dict=True),
        "series": frappe.db.sql(
            """SELECT day, source, spend, revenue, orders, delivered, maturity, extra
               FROM `tabEntity Metric`
               WHERE entity_id = %(e)s AND day >= %(s)s ORDER BY day""",
            {"e": entity_id, "s": start}, as_dict=True),
        "verdicts": frappe.db.sql(
            """SELECT name, verdict, metric, impact_mad, headline, status,
                      window_start, window_end, sample_size, recommended_action
               FROM `tabGrowth Verdict`
               WHERE entity_id = %(e)s ORDER BY modified DESC LIMIT 20""",
            {"e": entity_id}, as_dict=True),
        "changes": frappe.db.sql(
            """SELECT day, actor, surface, field_changed, before_value, after_value
               FROM `tabTimeline Change`
               WHERE entity_id = %(e)s AND day >= %(s)s ORDER BY day DESC""",
            {"e": entity_id, "s": start}, as_dict=True),
    }


@frappe.whitelist()
def findings(limit=20):
    return frappe.db.sql(
        """SELECT name, title, severity, status, entity_type, entity_id,
                  body, evidence, agent_run, creation
           FROM `tabGrowth Finding`
           WHERE status IN ('Open', 'Acknowledged')
           ORDER BY FIELD(severity,'Critical','High','Medium','Low'), creation DESC
           LIMIT %(l)s""",
        {"l": int(limit)}, as_dict=True,
    )


@frappe.whitelist()
def act(verdict, status, note=None):
    """Record a human decision on a verdict.

    Human-touched verdicts are never overwritten by the next run — the engine
    only supersedes ones still marked Open. A tool that silently reopens a
    decision the operator already made stops being trusted.
    """
    if status not in ("Acknowledged", "Actioned", "Dismissed"):
        frappe.throw("status must be Acknowledged, Actioned or Dismissed")
    doc = frappe.get_doc("Growth Verdict", verdict)
    doc.db_set("status", status)
    if note:
        doc.add_comment("Comment", note)
    frappe.db.commit()
    return {"ok": True, "verdict": verdict, "status": status}


@frappe.whitelist()
def ask(question):
    """Ad-hoc investigation. Runs the agent with the question as its task."""
    from growth_portal.agent import runtime

    run = runtime.run(task="investigate", context=question, notify=False)
    return frappe.db.get_value("Agent Run", run,
                               ["name", "status", "finding", "tool_call_count"],
                               as_dict=True)
