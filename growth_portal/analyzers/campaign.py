"""Campaign analyzer — judged on platform ROAS, one platform at a time.

Two deliberate restrictions, both of which narrow the answer on purpose:

**One platform per baseline.** Meta at ROAS 8.5 and TikTok at 14.7 are not two
points on one scale. They buy different inventory at different CPMs — TikTok's
reach here has run 4-6x cheaper — so a single blended baseline would mark every
Meta campaign as failing and every TikTok campaign as excellent. That is a
statement about the channels, not about the campaigns.

**Platform revenue, not ERPNext revenue.** A platform only ever claims the
orders it believes it drove. Dividing its spend by total ERPNext orders measures
market share, not performance, and `guard.assert_same_source` refuses it. So the
rate judged here is the platform's own ROAS, and its honest ceiling is "this
campaign is weak *by the platform's own accounting*".

What that leaves unanswered is the real question — cost per **delivered** order,
where about a quarter of orders never complete and the delivery rate swings
twenty points between products. That needs COGS and an order-level join which
does not exist yet. It is not approximated here: an approximation of the north
star is worse than its absence.
"""

from __future__ import annotations

import json
from dataclasses import replace

import frappe

from growth_portal.analyzers.base import AnalysisResult, Analyzer
from growth_portal.engine import verdict as engine

#: Judged separately, never pooled. The key is the source name the adapter
#: writes, so a new platform becomes a new baseline just by existing.
PLATFORMS = ("meta", "google_ads", "tiktok")


class CampaignAnalyzer(Analyzer):
    entity_type = "Campaign"

    #: Thresholds are in ROAS points, not percentage points, so they are an
    #: order of magnitude smaller than the delivery-rate rule's. `min_weight`
    #: is spend: a campaign that spent 300 over four weeks cannot carry a
    #: verdict no matter how its ratio looks.
    rule = engine.Rule(
        entity_type="Campaign",
        metric="roas",
        source="meta",          # replaced per platform in run()
        higher_is_better=True,
        min_sample=25,          # platform-attributed purchases
        min_weight=3000.0,      # account currency spent in the window
        min_days=14,
        gap_act=4.0,
        gap_material=1.5,
        impact_floor=4000.0,
        kill_at=1.5,            # below this the spend is structurally underwater
    )

    def collect(self, window_start, window_end, source="meta"):
        rows = frappe.db.sql(
            """
            SELECT m.entity_id,
                   SUM(m.spend)   AS spend,
                   SUM(m.revenue) AS revenue,
                   SUM(m.orders)  AS orders,
                   SUM(m.clicks)  AS clicks,
                   SUM(m.impressions) AS impressions,
                   SUBSTRING_INDEX(GROUP_CONCAT(m.extra ORDER BY m.day DESC SEPARATOR '\\n'), '\\n', 1) AS any_extra,
                   MAX(e.entity_label) AS label,
                   MIN(m.day) AS first_day, MAX(m.day) AS last_day,
                   SUM(m.maturity = 'Provisional') AS provisional_days
            FROM `tabEntity Metric` m
            LEFT JOIN `tabGrowth Entity` e ON e.entity_key = m.entity_id
            WHERE m.entity_type = 'Campaign'
              AND m.source = %(src)s
              AND m.day >= %(f)s AND m.day <= %(t)s
            GROUP BY m.entity_id
            """,
            {"src": source, "f": window_start, "t": window_end},
            as_dict=True,
        )

        out = []
        for r in rows:
            spend = float(r.spend or 0)
            if spend <= 0:
                # Zero spend is not zero performance — it is no observation at
                # all, and 0/0 would rank as the worst campaign in the account.
                # Dormancy is a separate question from efficiency.
                continue
            revenue = float(r.revenue or 0)
            orders = float(r.orders or 0)
            try:
                extra = json.loads(r.any_extra or "{}")
            except Exception:
                extra = {}

            out.append(engine.Row(
                key=r.entity_id,
                label=r.label or r.entity_id,
                value=revenue / spend,
                # Weight is spend, so ranking answers "where is the money"
                # rather than "which ratio looks prettiest".
                weight=spend,
                sample=int(orders),
                extra={
                    "numerator": round(revenue, 2),
                    "denominator": round(spend, 2),
                    "orders": orders,
                    "clicks": int(r.clicks or 0),
                    "impressions": int(r.impressions or 0),
                    "cpa": round(spend / orders, 2) if orders else None,
                    "cpm": round(1000 * spend / r.impressions, 2) if r.impressions else None,
                    "platform": source,
                    # The account's own currency, carried untouched. ERPNext is
                    # MAD and every ad account here is TRY; nothing converts
                    # silently, so a reader always knows which unit they hold.
                    "currency": extra.get("currency"),
                    "revenue_basis": extra.get("revenue_basis", "platform_reported"),
                    "attribution": extra.get("attribution"),
                    "first_day": str(r.first_day),
                    "last_day": str(r.last_day),
                    # Named rather than quietly folded in: TikTok moves for up
                    # to 48h and PMAX for 72h, so a window containing
                    # provisional days is understated by an unknown amount.
                    "provisional_days": int(r.provisional_days or 0),
                },
            ))
        return out

    def query_ref(self, source="meta"):
        return (
            f"growth_portal.analyzers.campaign.CampaignAnalyzer.collect — "
            f"Entity Metric where source={source}, summed per campaign over the window; "
            f"value = platform-reported revenue ÷ platform-reported spend, both from {source}"
        )

    def run(self, window_start, window_end, persist=True):
        """One pass per platform, each with its own baseline and its own rule.

        The platforms are merged for display, but they were never compared.
        """
        all_verdicts, considered, notes = [], 0, []

        for platform in PLATFORMS:
            rows = self.collect(window_start, window_end, source=platform)
            considered += len(rows)
            if not rows:
                notes.append(f"{platform}: no spend in window")
                continue

            rule = replace(self.rule, source=platform)
            eligible = [r for r in rows if r.weight >= rule.min_weight]
            if not eligible:
                notes.append(f"{platform}: {len(rows)} campaigns, none above the spend floor")
                continue

            try:
                verdicts = engine.judge(rows, rule, window_start, window_end,
                                        self.query_ref(platform))
            except Exception as e:
                # A platform whose window is still maturing must not stop the
                # others from being judged.
                notes.append(f"{platform}: {e}")
                continue

            all_verdicts.extend(verdicts)
            notes.append(
                f"{platform}: {len(rows)} campaigns, baseline ROAS "
                f"{engine.baseline(eligible):.2f}"
            )

        all_verdicts.sort(key=lambda v: v["impact_mad"], reverse=True)

        # Persisted once, after every platform has been judged. `persist`
        # supersedes all Open verdicts for the entity type, so calling it per
        # platform would have each pass wipe the one before it.
        if persist and all_verdicts:
            engine.persist(all_verdicts, self.entity_type)

        return AnalysisResult(
            entity_type=self.entity_type,
            rows_considered=considered,
            verdicts=all_verdicts,
            baseline=None,   # deliberately absent: there are three, not one
            notes=notes,
        )
