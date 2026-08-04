"""The verdict engine — one implementation, seven entity types.

Every entity in the business gets the same four questions:

    Grow      this one deserves more
    Fix       something is wrong and it is worth money to repair
    Dormant   nobody is working on it
    Kill      it is losing money structurally

The engine is entity-agnostic. An analyzer hands it comparable rows and a rule;
the engine ranks by money, enforces the framing rules, and writes the verdict.
Adding suppliers or creatives means writing an analyzer, not another engine.

Ranking is always by monthly money impact. A verdict without a money number is
not a verdict — it is an observation, and observations do not get screen space.
"""


from __future__ import annotations
import json
from dataclasses import dataclass, field

import frappe

from growth_portal.engine import guard

GROW, FIX, DORMANT, KILL, WATCH = "Grow", "Fix", "Dormant", "Kill", "Watch"


@dataclass
class Row:
    """One comparable unit — a product, a supplier, a campaign, a page."""
    key: str                      # stable id: item_code, supplier, campaign_id
    label: str
    value: float                  # the rate being judged (delivery %, ROAS, CVR…)
    weight: float                 # money the rate applies to — sets the impact
    sample: int                   # observations behind `value`
    extra: dict = field(default_factory=dict)


@dataclass
class Rule:
    """Thresholds, declared before the data is read.

    A threshold chosen after seeing the result is not a threshold; it is a
    rationalisation of a conclusion already reached.
    """
    entity_type: str
    metric: str
    source: str                   # both sides of the ratio come from here
    higher_is_better: bool = True
    min_sample: int = 60
    min_weight: float = 5000.0    # filters packaging lines, free gifts, test SKUs
    min_days: int = 14
    gap_act: float = 8.0          # points from baseline -> act
    gap_material: float = 3.0     # points below which nothing is material
    impact_floor: float = 5000.0  # money that makes a small gap worth acting on
    kill_at: float | None = None  # absolute floor for structural loss
    dormant_after_days: int | None = None

    #: A Grow verdict says "put more money here". That is not an action if the
    #: entity is already free to spend more and isn't — Google's account runs at
    #: 11% of authorised budget, so "scale this" would recommend pulling a lever
    #: that is not connected to anything. Rows carrying `utilization` below this
    #: are reported as Dormant-capacity instead: the constraint is delivery, not
    #: budget. Rows with no utilization at all are unaffected.
    min_utilization_to_grow: float = 60.0

    #: Written from the most expensive lesson so far: a 104% budget increase on
    #: TikTok took ROAS from 18.7 to 4.7 in two days and had to be reverted. A
    #: Grow verdict now carries its own step ceiling rather than saying "scale"
    #: and leaving the size to whoever reads it.
    max_step_pct: float = 15.0


def baseline(rows):
    """Peer baseline, computed from the same rows being judged.

    Deliberately not a constant: a courier-wide or seasonal dip should move the
    bar with it, so an entity is always compared against its peers in the same
    period rather than a number typed last quarter.
    """
    tot_w = sum(r.weight for r in rows) or 0
    if not tot_w:
        return None
    return sum(r.value * r.weight for r in rows) / tot_w


def judge(rows, rule, window_start, window_end, query_ref, now=None):
    """Return verdict dicts, ranked by money. Writes nothing."""
    guard.assert_window(window_start, window_end, rule.min_days)
    guard.assert_mature(rule.source, window_end, now=now)

    # Impact is always quoted per month, so it stays comparable between rules
    # that judge over different spans. Without this, a 14-day rule and a 28-day
    # rule rank against each other on numbers that mean different things.
    span = (frappe.utils.getdate(window_end) - frappe.utils.getdate(window_start)).days + 1
    to_month = 30.0 / span

    judgeable = [r for r in rows if r.weight >= rule.min_weight]
    base = baseline(judgeable)
    if base is None:
        return []

    seen = {r.key for r in judgeable}
    out = []

    for r in judgeable:
        guard.assert_pulled_performance(r.key, seen)

        # gap is always "how far below good", whichever direction good is
        gap = (base - r.value) if rule.higher_is_better else (r.value - base)
        impact = abs(gap) / 100.0 * r.weight * to_month

        if r.sample < rule.min_sample:
            # Not a verdict — an admission the sample cannot carry one. Said out
            # loud, because silence here reads as "nothing wrong".
            if abs(gap) >= rule.gap_act:
                out.append(_mk(WATCH, r, rule, base, 0, window_start, window_end, query_ref,
                               f"Sample {r.sample} — below the minimum of {rule.min_sample}",
                               "Wait for a longer window before judging"))
            continue

        if rule.kill_at is not None and (
            (rule.higher_is_better and r.value < rule.kill_at)
            or (not rule.higher_is_better and r.value > rule.kill_at)
        ):
            out.append(_mk(KILL, r, rule, base, impact, window_start, window_end, query_ref,
                           f"{r.value:.1f} — below the viability floor of {rule.kill_at}",
                           f"Stop the spend — the gap costs ~{impact:,.0f} MAD/month"))

        elif gap >= rule.gap_act or (gap >= rule.gap_material and impact >= rule.impact_floor):
            # The second clause exists because gating on the percentage alone
            # hides the biggest problems: a 6.6-point gap on high volume cost
            # four times more than a 10.7-point gap on a small product, and a
            # percentage threshold would have reported only the small one.
            out.append(_mk(FIX, r, rule, base, impact, window_start, window_end, query_ref,
                           f"{r.value:.1f} vs {base:.1f} baseline",
                           f"A {gap:.1f} point gap on {r.sample} orders costs ~{impact:,.0f} MAD/month"))

        elif rule.dormant_after_days and r.extra.get("days_since_activity") is not None \
                and r.extra["days_since_activity"] >= rule.dormant_after_days:
            # Declared and never issued until now. An entity nobody has touched
            # is a different problem from one performing badly, and folding it
            # into Fix hides that nothing is being worked on at all.
            out.append(_mk(DORMANT, r, rule, base, impact, window_start, window_end, query_ref,
                           f"no activity for {r.extra['days_since_activity']} days",
                           "Decide: restart it or retire it — it is neither running nor closed"))

        elif -gap >= rule.gap_act / 2 or (-gap >= rule.gap_material and impact >= rule.impact_floor):
            # Mirrors the Fix gate on purpose. Without the money clause the
            # single strongest scaling candidate in the catalogue — 3.1 points
            # above baseline on 127k of revenue — produces no verdict at all,
            # while a small product 4 points up produces one. Opportunities go
            # missing the same way problems do.
            util = r.extra.get("utilization")
            if util is not None and util < rule.min_utilization_to_grow:
                # It is performing well AND already free to spend more. Raising
                # the budget changes nothing; the constraint is elsewhere.
                out.append(_mk(WATCH, r, rule, base, impact, window_start, window_end, query_ref,
                               f"{r.value:.1f} — above baseline but only {util:.0f}% of budget used",
                               "Do not raise the budget — it is delivery-limited, not budget-limited. "
                               f"Fix delivery first ({r.extra.get('delivery_status') or 'reason not reported'})."))
            else:
                step = f" Step no more than +{rule.max_step_pct:.0f}%." if rule.max_step_pct else ""
                out.append(_mk(GROW, r, rule, base, impact, window_start, window_end, query_ref,
                               f"{r.value:.1f} — {-gap:.1f} points above baseline",
                               "The same spend buys a better result here — a candidate to scale." + step))

    out.sort(key=lambda v: v["impact_mad"], reverse=True)
    return out


def _mk(verdict, r, rule, base, impact, ws, we, query_ref, headline, action):
    payload = {
        "doctype": "Growth Verdict",
        "entity_type": rule.entity_type,
        "entity_id": r.key,
        "entity_label": (r.label or r.key)[:500],
        "metric": rule.metric,
        "verdict": verdict,
        "impact_mad": round(impact or 0),
        # Data field, 140 chars. The label is already on the row in full.
        "headline": f"{r.label}: {headline}"[:140],
        "recommended_action": action,
        "numerator": r.extra.get("numerator", r.value),
        "denominator": r.extra.get("denominator", r.sample),
        # Same system on both sides. The engine cannot see the query, so the
        # analyzer must name its source and guard checks it matches.
        "denominator_source": rule.source,
        "window_start": ws,
        "window_end": we,
        "sample_size": r.sample,
        "query_ref": query_ref,
        "evidence": json.dumps({"value": r.value, "baseline": round(base, 2), **r.extra},
                               ensure_ascii=False, default=str),
    }
    guard.assert_evidence(payload)
    return payload


def persist(verdicts, entity_type):
    """Supersede the last run; leave anything a human already touched alone.

    A person's decision outranks the engine's — re-raising a verdict they
    dismissed yesterday is how a tool teaches people to stop reading it.
    """
    frappe.db.sql(
        """UPDATE `tabGrowth Verdict` SET status='Superseded'
           WHERE entity_type=%(t)s AND status='Open'""",
        {"t": entity_type},
    )
    for v in verdicts:
        frappe.get_doc(v).insert(ignore_permissions=True)
    frappe.db.commit()
    return len(verdicts)
