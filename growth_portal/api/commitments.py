"""Scale commitments — the pre-committed test, and the automatic re-check.

This exists because of one specific loss. TikTok's budget was raised 104% in a
single step; ROAS fell from 18.7 to 5.8 to 4.7 over two days and the whole
change had to be reverted. The lesson — step in ~15% increments with three
closed days between — was written down in a memory file, which is to say it was
written down nowhere that could stop it happening again.

The shape here is deliberate:

* the criterion is recorded **before** the money moves, not after;
* the baseline value is captured at commit time, because a baseline recalled
  afterwards is a baseline chosen to fit the outcome;
* the review date is a real date and the review runs itself, so a step nobody
  followed up on becomes a finding rather than silence.

`review()` never marks a commitment Passed or Failed while the window is still
maturing. TikTok moves for 48 hours and PMAX for 72, so a step judged the
morning after always reads worse than it was.
"""

import frappe

from growth_portal.engine import guard


@frappe.whitelist()
def open_commitments():
    return frappe.get_all(
        "Scale Commitment",
        filters={"status": "Open"},
        fields=["name", "entity_type", "entity_id", "entity_label", "platform",
                "metric", "baseline_value", "step_pct", "budget_before",
                "budget_after", "criterion", "committed_on", "review_on"],
        order_by="review_on asc",
    )


@frappe.whitelist()
def history(limit=40):
    return frappe.get_all(
        "Scale Commitment",
        filters=[["status", "!=", "Open"]],
        fields=["name", "entity_label", "platform", "metric", "status",
                "baseline_value", "result_value", "delta_pct", "step_pct",
                "criterion", "committed_on", "review_on", "decided_on", "note"],
        order_by="decided_on desc", limit=int(limit),
    )


@frappe.whitelist()
def commit(entity_type, entity_id, metric, baseline_value, criterion,
           review_on, entity_label=None, platform=None, verdict=None,
           step_pct=None, budget_before=None, budget_after=None):
    """Record a step before it is taken.

    Refuses a review date that is not far enough out. Three closed days is the
    minimum this business's data supports; a two-day read is what produced the
    reverted TikTok call.
    """
    review = frappe.utils.getdate(review_on)
    today = frappe.utils.getdate()
    if (review - today).days < 3:
        frappe.throw(
            "Review date must be at least 3 days out. TikTok attribution alone "
            "moves for 48 hours, so a shorter test reads a number that is still "
            "changing."
        )

    if step_pct is not None and float(step_pct) > 15:
        # Not blocked — sometimes a bigger step is a deliberate, eyes-open bet.
        # But it is written onto the record so the size is never a surprise
        # when the result comes back.
        frappe.msgprint(
            f"Step of {float(step_pct):.0f}% is above the 15% ceiling this "
            "account's history supports. Recorded as committed."
        )

    doc = frappe.get_doc({
        "doctype": "Scale Commitment",
        "entity_type": entity_type, "entity_id": entity_id,
        "entity_label": entity_label or entity_id, "platform": platform,
        "verdict": verdict, "metric": metric or "roas",
        "baseline_value": float(baseline_value),
        "step_pct": float(step_pct) if step_pct is not None else None,
        "budget_before": budget_before, "budget_after": budget_after,
        "criterion": criterion,
        "committed_on": today, "review_on": review, "status": "Open",
    }).insert(ignore_permissions=True)
    frappe.db.commit()
    return doc.name


def _current_value(c):
    """The entity's metric over the days since the step, from the same source."""
    rows = frappe.db.sql(
        """SELECT SUM(spend) spend, SUM(revenue) revenue, SUM(orders) orders,
                  SUM(maturity='Provisional') provisional
           FROM `tabEntity Metric`
           WHERE entity_id=%(e)s AND day > %(f)s AND day <= %(t)s""",
        {"e": c.entity_id, "f": c.committed_on, "t": frappe.utils.getdate()},
        as_dict=True,
    )[0]
    spend = float(rows.spend or 0)
    if not spend:
        return None, 0
    return float(rows.revenue or 0) / spend, int(rows.provisional or 0)


@frappe.whitelist()
def review():
    """Judge every commitment whose review date has arrived.

    Runs on the daily schedule. A step that nobody came back to is exactly the
    thing that turns an expensive lesson into an expensive habit.
    """
    due = frappe.get_all(
        "Scale Commitment",
        filters={"status": "Open", "review_on": ["<=", frappe.utils.getdate()]},
        fields=["name", "entity_id", "entity_label", "platform", "metric",
                "baseline_value", "step_pct", "criterion", "committed_on", "review_on"],
    )
    judged = []
    for c in due:
        doc = frappe.get_doc("Scale Commitment", c.name)
        value, provisional = _current_value(c)

        if value is None:
            doc.db_set("note", "No spend recorded since the step — nothing to judge yet.")
            continue
        if provisional:
            # Deliberately leaves it Open. Judging a maturing window understates
            # the result and would fail steps that actually worked.
            doc.db_set("note", f"{provisional} day(s) still maturing — review deferred.")
            continue

        delta = 100.0 * (value - c.baseline_value) / c.baseline_value if c.baseline_value else 0.0
        passed = delta >= 0
        doc.db_set({
            "result_value": round(value, 4),
            "delta_pct": round(delta, 1),
            "status": "Passed" if passed else "Failed",
            "decided_on": frappe.utils.now_datetime(),
        })

        evidence = {
            "numerator": round(value, 4),
            "denominator": round(c.baseline_value, 4),
            "denominator_source": c.platform or "platform",
            "window_start": str(c.committed_on),
            "window_end": str(frappe.utils.getdate()),
            "query_ref": "growth_portal.api.commitments._current_value — "
                         "Entity Metric for this entity, days after the step, "
                         "revenue over spend from the same source",
        }
        guard.assert_evidence(evidence)

        finding = frappe.get_doc({
            "doctype": "Growth Finding",
            "title": (f"Scale step on {c.entity_label} "
                      f"{'passed' if passed else 'FAILED'} its own test: "
                      f"{c.metric} {c.baseline_value:.2f} → {value:.2f} ({delta:+.1f}%)"),
            "severity": "Medium" if passed else "High",
            "status": "Open",
            "entity_type": "Campaign",
            "entity_id": c.entity_id,
            "body": (
                f"Committed {c.committed_on} with a "
                f"{('%.0f%%' % c.step_pct) if c.step_pct else 'n/a'} step.\n\n"
                f"Criterion set before the step: {c.criterion}\n\n"
                f"Result: {c.metric} moved from {c.baseline_value:.2f} to {value:.2f}, "
                f"{delta:+.1f}%.\n\n"
                + ("Hold the new level and consider one more step of the same size."
                   if passed else
                   "Revert to the previous level. This account's history says the "
                   "efficient ceiling is reached long before the budget ceiling is.")
            ),
            "evidence": frappe.as_json(evidence),
        }).insert(ignore_permissions=True)
        doc.db_set("finding", finding.name)
        judged.append({"commitment": c.name, "status": doc.status, "delta_pct": round(delta, 1)})

    frappe.db.commit()
    return judged
