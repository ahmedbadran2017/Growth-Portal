"""Supplier analyzer — return rate and cost trend decide who to keep"""

from growth_portal.analyzers.base import Analyzer
from growth_portal.engine import verdict as engine


class SupplierAnalyzer(Analyzer):
    entity_type = "Supplier"

    rule = engine.Rule(
        entity_type="Supplier",
        metric="delivery_rate",
        source="erpnext",
        min_sample=80,
        min_weight=20000,
    )

    def collect(self, window_start, window_end):
        raise NotImplementedError("Supplier: collect() — join Delivery Outcome to Purchase Order supplier, weight by delivered revenue")

    def query_ref(self):
        return "growth_portal.analyzers.supplier"
