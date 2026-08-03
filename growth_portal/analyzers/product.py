"""Product analyzer — the reference implementation.

Answers "which product is bleeding" from ERPNext alone. No ad-platform data is
needed and none is used: a product with a 73% delivery rate is losing money
regardless of which campaign sold it, and waiting on campaign-to-product
attribution before answering that question is waiting for nothing.

Thresholds below were set against July 2026 and are declared before any data is
read. Two of them exist because of specific wrong answers:

* `impact_floor` — gating on the gap percentage alone hid the largest problem
  in the catalogue. A 6.6-point gap on 972 orders cost 13,198 MAD/month while a
  10.7-point gap on 195 orders cost 3,034. Ranking by money and gating by
  percentage reports the small one and stays silent on the big one.
* `min_weight` — order count alone promoted a packaging line (101 orders,
  54 MAD of revenue) to a Grow verdict on its 94% delivery rate.
"""

import frappe

from growth_portal.analyzers.base import Analyzer
from growth_portal.engine import verdict as engine
from growth_portal.sources.erpnext import TRACKING, classify


class ProductAnalyzer(Analyzer):
    entity_type = "Product"

    rule = engine.Rule(
        entity_type="Product",
        metric="delivery_rate",
        source="erpnext",
        higher_is_better=True,
        min_sample=60,        # resolved orders
        min_weight=5000.0,    # MAD placed — filters packaging, gifts, samples
        min_days=14,
        gap_act=8.0,
        gap_material=3.0,
        impact_floor=5000.0,
        kill_at=60.0,
    )

    def collect(self, window_start, window_end):
        rows = frappe.db.sql(
            f"""
            SELECT soi.item_code, t.status_name, t.amt,
                   SUBSTRING_INDEX(GROUP_CONCAT(soi.item_name ORDER BY soi.creation DESC), ',', 1) AS label
            FROM (
                SELECT sales_order, delivery_status_name AS status_name, custom_amount AS amt,
                       ROW_NUMBER() OVER (PARTITION BY sales_order
                                          ORDER BY creation DESC, modified DESC) rn
                FROM `{TRACKING}`
                WHERE sales_order IS NOT NULL
                  AND creation >= %(f)s
                  AND creation < DATE_ADD(%(t)s, INTERVAL 1 DAY)
            ) t
            JOIN `tabSales Order Item` soi ON soi.parent = t.sales_order
            WHERE t.rn = 1
            GROUP BY soi.item_code, t.status_name, t.amt
            """,
            {"f": window_start, "t": window_end},
            as_dict=True,
        )

        agg = {}
        for r in rows:
            outcome, owner, terminal = classify(r.status_name)
            a = agg.setdefault(r.item_code, {
                "label": r.label, "placed": 0, "resolved": 0, "delivered": 0,
                "refused_product": 0, "unreachable": 0, "cancelled_confirm": 0,
                "duplicate": 0, "revenue": 0.0, "lost": 0.0,
            })
            a["placed"] += 1
            a["revenue"] += r.amt or 0
            if not terminal:
                continue
            a["resolved"] += 1
            if outcome == "Delivered":
                a["delivered"] += 1
            else:
                a["lost"] += r.amt or 0
                if owner == "Product":
                    a["refused_product"] += 1
                elif outcome == "Unreachable":
                    a["unreachable"] += 1
                elif owner == "Confirmation":
                    a["cancelled_confirm"] += 1
                elif owner == "Duplicate":
                    a["duplicate"] += 1

        out = []
        for key, a in agg.items():
            # Rate over *resolved* orders. Dividing by placed orders would make
            # every recent product look like it fails.
            if not a["resolved"]:
                continue
            rate = 100.0 * a["delivered"] / a["resolved"]
            out.append(engine.Row(
                key=key,
                label=a["label"] or key,
                value=rate,
                weight=a["revenue"],
                sample=a["resolved"],
                extra={
                    "numerator": a["delivered"],
                    "denominator": a["resolved"],
                    "orders_placed": a["placed"],
                    "refused_product": a["refused_product"],
                    "unreachable": a["unreachable"],
                    "cancelled_confirm": a["cancelled_confirm"],
                    "duplicate_or_denied": a["duplicate"],
                    "lost_amount": round(a["lost"]),
                    # The failure mix is what turns a verdict into an assignment:
                    # product refusals go to the page, unreachable goes to lead
                    # quality, phone cancellations go to the confirmation desk.
                    "dominant_failure": max(
                        (("Product", a["refused_product"]),
                         ("Lead Quality", a["unreachable"]),
                         ("Confirmation", a["cancelled_confirm"]),
                         ("Duplicate", a["duplicate"])),
                        key=lambda x: x[1],
                    )[0] if a["resolved"] > a["delivered"] else None,
                },
            ))
        return out

    def query_ref(self):
        return (
            "growth_portal.analyzers.product.ProductAnalyzer.collect — "
            "latest Shipment Tracking row per sales_order, joined to Sales Order Item, "
            "grouped on item_code, rates over resolved orders only"
        )
