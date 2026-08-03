"""Capacity — where there is room to spend more, and where there is not.

This answers the question every scaling decision actually turned on, and which
no ratio can answer: *is this entity constrained by budget, or by delivery?*

They need opposite actions. A campaign at 95% of its budget with good returns
wants more money. A campaign at 11% with the same returns will not spend the
money you give it — the constraint is demand or eligibility, and raising the
budget is pulling a lever that is not connected to anything.

Live Google numbers while this was written: the account used 11% of authorised
budget across six live campaigns. Every "scale this" recommendation on that
account would have been unexecutable.
"""

import frappe

#: Above this, the budget is the binding constraint.
CAPPED = 85.0
#: Below this, something other than budget is stopping it.
STARVED = 40.0


@frappe.whitelist()
def campaigns(days=14, source=None):
    """Spend against authorised budget, per campaign, with the platform's own
    reason for the delivery level attached."""
    days = int(days)
    cond = "AND m.source = %(s)s" if source else ""
    rows = frappe.db.sql(
        f"""
        SELECT m.entity_id, m.source,
               MAX(e.entity_label) label,
               SUM(m.spend) spend,
               SUM(m.revenue) revenue,
               SUM(m.orders) orders,
               AVG(NULLIF(m.budget,0)) budget,
               MAX(m.budget_type) budget_type,
               SUBSTRING_INDEX(GROUP_CONCAT(m.delivery_status ORDER BY m.day DESC SEPARATOR '\\n'), '\\n', 1) delivery_status,
               COUNT(DISTINCT m.day) active_days,
               MAX(m.day) last_day
        FROM `tabEntity Metric` m
        LEFT JOIN `tabGrowth Entity` e ON e.entity_key = m.entity_id
        WHERE m.entity_type='Campaign'
          AND m.day >= DATE_SUB(CURDATE(), INTERVAL %(d)s DAY) {cond}
        GROUP BY m.entity_id, m.source
        HAVING spend > 0
        ORDER BY spend DESC
        """,
        {"d": days, "s": source}, as_dict=True,
    )

    out = []
    for r in rows:
        spend = float(r.spend or 0)
        budget = float(r.budget or 0)
        active = int(r.active_days or 0) or 1
        per_day = spend / active
        util = (100.0 * per_day / budget) if budget else None
        revenue = float(r.revenue or 0)

        out.append({
            "entity_id": r.entity_id,
            "label": r.label or r.entity_id,
            "platform": r.source,
            "spend": round(spend),
            "spend_per_day": round(per_day),
            "budget": round(budget) if budget else None,
            "budget_type": r.budget_type,
            "utilization": round(util, 1) if util is not None else None,
            # Money authorised and not spent over the window. This is the size
            # of the lever, and it is not the same as "how much to add".
            "unused": round((budget - per_day) * active) if budget else None,
            "roas": round(revenue / spend, 2) if spend else None,
            "orders": round(float(r.orders or 0)),
            "delivery_status": r.delivery_status,
            "constraint": _constraint(util, r.delivery_status),
            "active_days": active,
            "last_day": str(r.last_day),
        })

    capped = [r for r in out if r["constraint"] == "budget"]
    starved = [r for r in out if r["constraint"] == "delivery"]
    total_spend = sum(r["spend"] for r in out)
    total_budget = sum((r["budget"] or 0) * r["active_days"] for r in out)

    return {
        "rows": out,
        "window_days": days,
        "totals": {
            "spend": round(total_spend),
            "authorised": round(total_budget),
            "utilization": round(100.0 * total_spend / total_budget, 1) if total_budget else None,
        },
        "budget_capped": len(capped),
        "delivery_limited": len(starved),
        # The headline sentence, assembled rather than left to the reader:
        # "3 of 4 campaigns budget-capped at 93-95%" was the whole TikTok
        # decision, and it should be one line at the top of a screen.
        "headline": _headline(out, capped, starved),
        "no_budget_data": sum(1 for r in out if r["budget"] is None),
    }


def _constraint(util, delivery_status):
    if util is None:
        return "unknown"
    if util >= CAPPED:
        return "budget"
    if util <= STARVED:
        return "delivery"
    return "none"


def _headline(rows, capped, starved):
    if not rows:
        return "No campaign spend in this window."
    if not any(r["budget"] is not None for r in rows):
        return ("No budgets have been pulled yet — capacity cannot be assessed, "
                "and no Grow verdict should be acted on until it can.")
    parts = []
    if capped:
        top = sorted(capped, key=lambda r: -r["spend"])[:3]
        parts.append(
            f"{len(capped)} campaign(s) budget-capped at "
            f"{min(r['utilization'] for r in capped):.0f}-{max(r['utilization'] for r in capped):.0f}% "
            f"— headroom here is real: " + ", ".join(r["label"][:28] for r in top)
        )
    if starved:
        worst = sorted(starved, key=lambda r: -r["spend"])[:3]
        parts.append(
            f"{len(starved)} campaign(s) below {STARVED:.0f}% of budget — raising these does nothing, "
            f"the constraint is delivery: " + ", ".join(r["label"][:28] for r in worst)
        )
    return " · ".join(parts) or "Every campaign is spending in its normal band."
