"""Supplier analyzer — judged on confirmation rate.

Delivery rate is the product analyzer's question. A supplier's distinctive
failure shows up one step earlier: July 2026 has Digitronics at 16%
confirmation and Beauty Mall at 51.7%, against a book that runs around 81%.
An order that never gets confirmed never reaches a courier, so it never appears
in a delivery-rate report at all — the loss is invisible one level down.

Supplier comes from `tabItem.default_supplier`, which covers 173,056 of 173,775
items. The `Item Supplier` child table holds 191 rows across three suppliers
and is not the source of truth.
"""

from __future__ import annotations

import frappe

from growth_portal.analyzers.base import Analyzer
from growth_portal.engine import verdict as engine

CONFIRMED = "Confirmed"


class SupplierAnalyzer(Analyzer):
    entity_type = "Supplier"

    #: `kill_at = 40` is below every supplier currently trading except one.
    #: It is a floor for "this is not a rate problem, this is a broken
    #: relationship", not a target.
    rule = engine.Rule(
        entity_type="Supplier",
        metric="confirmation_rate",
        source="erpnext",
        higher_is_better=True,
        min_sample=50,          # order lines
        min_weight=20000.0,     # MAD placed — a supplier below this is a trial
        min_days=14,
        gap_act=10.0,
        gap_material=4.0,
        impact_floor=8000.0,
        kill_at=40.0,
        # A supplier has no budget to raise. The lever here is catalogue weight
        # and where the confirmation desk spends its calls.
        act_grow=("Confirms above the book — give it more catalogue weight "
                  "and promotion before the ones below it."),
        act_fix=("A {gap:.1f} point confirmation gap on {sample} lines costs "
                 "~{impact:,.0f} MAD/month. Check pricing, the product page and "
                 "the call script before blaming the courier."),
        act_kill=("Confirmation is structurally broken here — ~{impact:,.0f} MAD/month "
                  "of orders never reach a courier. Pause new listings and renegotiate "
                  "or drop the supplier."),
        # Suppliers are a standing relationship, not a budget dial.
        max_step_pct=0.0,
    )

    def collect(self, window_start, window_end):
        rows = frappe.db.sql(
            """
            SELECT i.default_supplier AS supplier,
                   COUNT(*) AS line_count,
                   COUNT(DISTINCT so.name) orders,
                   COUNT(DISTINCT soi.item_code) skus,
                   SUM(soi.amount) revenue,
                   SUM(so.custom_sales_status = %(c)s) confirmed,
                   SUM(so.custom_sales_status = 'Did not Answer') no_answer,
                   SUM(so.custom_sales_status = 'Duplicated') duplicated,
                   SUM(so.custom_sales_status = 'Cancelled') cancelled
            FROM `tabSales Order Item` soi
            JOIN `tabSales Order` so ON so.name = soi.parent
            JOIN `tabItem` i ON i.name = soi.item_code
            WHERE so.creation >= %(f)s
              AND so.creation < DATE_ADD(%(t)s, INTERVAL 1 DAY)
              AND i.default_supplier IS NOT NULL AND i.default_supplier != ''
            GROUP BY i.default_supplier
            """,
            {"c": CONFIRMED, "f": window_start, "t": window_end},
            as_dict=True,
        )

        out = []
        for r in rows:
            if not r.line_count:
                continue
            revenue = float(r.revenue or 0)
            out.append(engine.Row(
                key=r.supplier,
                label=r.supplier,
                value=100.0 * (r.confirmed or 0) / r.line_count,
                weight=revenue,
                sample=int(r.line_count),
                extra={
                    "numerator": int(r.confirmed or 0),
                    "denominator": int(r.line_count),
                    "orders": r.orders,
                    "skus": r.skus,
                    "revenue_mad": round(revenue),
                    "aov_mad": round(revenue / r.orders) if r.orders else None,
                    # The mix is what turns a low rate into an assignment:
                    # unanswered calls are lead quality, duplicates are a site
                    # bug, outright cancellations are price or product.
                    "no_answer": int(r.no_answer or 0),
                    "duplicated": int(r.duplicated or 0),
                    "cancelled": int(r.cancelled or 0),
                    "dominant_failure": max(
                        (("Lead Quality", r.no_answer or 0),
                         ("Duplicate", r.duplicated or 0),
                         ("Customer", r.cancelled or 0)),
                        key=lambda x: x[1],
                    )[0] if r.line_count > (r.confirmed or 0) else None,
                },
            ))
        return out

    def query_ref(self):
        return (
            "growth_portal.analyzers.supplier.SupplierAnalyzer.collect — "
            "Sales Order Item joined to Sales Order and Item, grouped on "
            "tabItem.default_supplier; rate = lines with custom_sales_status='Confirmed' "
            "over all lines in the window"
        )
