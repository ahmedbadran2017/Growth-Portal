"""Media buyer analyzer — judged on the return of the money they control.

Attribution is by ad account, because that is the only ownership boundary the
platforms record. A campaign has no owner field.

Judged per platform, never blended. A buyer running TikTok and a buyer running
Meta are not comparable on one ROAS scale, and blending them would mostly
measure which platform each was assigned.

Activity is deliberately NOT part of the verdict. Change count is a measure of
how much someone touched an account, not of whether they were right — and a
platform whose audit log the portal cannot read would make a diligent buyer
look idle. Activity is reported beside the verdict, never inside it.
"""

from __future__ import annotations

from dataclasses import replace

import frappe

from growth_portal.analyzers.base import AnalysisResult, Analyzer
from growth_portal.api.buyers import _buyer_for
from growth_portal.engine import verdict as engine

PLATFORMS = ("meta", "google_ads", "tiktok")


class MediaBuyerAnalyzer(Analyzer):
    entity_type = "Media Buyer"

    rule = engine.Rule(
        entity_type="Media Buyer",
        metric="roas",
        source="meta",
        higher_is_better=True,
        min_sample=40,
        min_weight=10000.0,
        min_days=14,
        gap_act=3.0,
        gap_material=1.2,
        impact_floor=10000.0,
        kill_at=None,      # you do not "kill" a person from a dashboard
    )

    def collect(self, window_start, window_end, source="meta"):
        rows = frappe.db.sql(
            """SELECT m.entity_id, m.extra,
                      SUM(m.spend) spend, SUM(m.revenue) revenue, SUM(m.orders) orders
               FROM `tabEntity Metric` m
               WHERE m.entity_type='Campaign' AND m.source=%(s)s
                 AND m.day >= %(f)s AND m.day <= %(t)s
               GROUP BY m.entity_id""",
            {"s": source, "f": window_start, "t": window_end}, as_dict=True,
        )

        agg = {}
        for r in rows:
            try:
                extra = frappe.parse_json(r.extra or "{}")
            except Exception:
                extra = {}
            account = extra.get("account") or extra.get("advertiser_id") or extra.get("customer_id")
            buyer = _buyer_for(account)
            a = agg.setdefault(buyer, {"spend": 0.0, "revenue": 0.0, "orders": 0.0,
                                       "campaigns": 0, "currency": extra.get("currency")})
            a["spend"] += float(r.spend or 0)
            a["revenue"] += float(r.revenue or 0)
            a["orders"] += float(r.orders or 0)
            a["campaigns"] += 1

        out = []
        for buyer, a in agg.items():
            if a["spend"] <= 0 or buyer == "Unassigned":
                # An unmapped account is a configuration gap, not a person.
                # Judging it would put a verdict on nobody.
                continue
            out.append(engine.Row(
                key=f"{buyer}::{source}",
                label=buyer,
                value=a["revenue"] / a["spend"],
                weight=a["spend"],
                sample=int(a["orders"]),
                extra={
                    "numerator": round(a["revenue"], 2),
                    "denominator": round(a["spend"], 2),
                    "platform": source,
                    "campaigns": a["campaigns"],
                    "orders": a["orders"],
                    "cpa": round(a["spend"] / a["orders"], 2) if a["orders"] else None,
                    "currency": a["currency"],
                },
            ))
        return out

    def query_ref(self, source="meta"):
        return (
            f"growth_portal.analyzers.media_buyer.MediaBuyerAnalyzer.collect — "
            f"Entity Metric where source={source}, campaigns grouped to their ad "
            f"account's buyer via site_config media_buyer_accounts; value = "
            f"platform-reported revenue over spend, both from {source}"
        )

    def run(self, window_start, window_end, persist=True):
        all_verdicts, considered, notes = [], 0, []
        for platform in PLATFORMS:
            rows = self.collect(window_start, window_end, source=platform)
            considered += len(rows)
            eligible = [r for r in rows if r.weight >= self.rule.min_weight]
            if not eligible:
                notes.append(f"{platform}: no buyer above the spend floor")
                continue
            # Two buyers is not a peer group. A baseline built from one other
            # person is that person's number, and calling it a baseline turns a
            # coin flip into a judgement about someone's work.
            if len(eligible) < 3:
                notes.append(
                    f"{platform}: only {len(eligible)} buyer(s) above the floor — "
                    "too few for a peer baseline, reported without a verdict"
                )
                continue
            try:
                verdicts = engine.judge(rows, replace(self.rule, source=platform),
                                        window_start, window_end, self.query_ref(platform))
            except Exception as e:
                notes.append(f"{platform}: {e}")
                continue
            all_verdicts.extend(verdicts)
            notes.append(f"{platform}: {len(eligible)} buyers, baseline ROAS "
                         f"{engine.baseline(eligible):.2f}")

        all_verdicts.sort(key=lambda v: v["impact_mad"], reverse=True)
        if persist and all_verdicts:
            engine.persist(all_verdicts, self.entity_type)
        return AnalysisResult(entity_type=self.entity_type, rows_considered=considered,
                              verdicts=all_verdicts, baseline=None, notes=notes)
