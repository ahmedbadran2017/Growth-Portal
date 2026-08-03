"""Source market analyzer — sourcing cost per delivered order, by origin country"""

from growth_portal.analyzers.base import Analyzer
from growth_portal.engine import verdict as engine


class MarketAnalyzer(Analyzer):
    entity_type = "Source Market"

    rule = engine.Rule(
        entity_type="Source Market",
        metric="margin_per_delivered",
        source="erpnext",
        min_sample=150,
        min_weight=50000,
    )

    def collect(self, window_start, window_end):
        raise NotImplementedError("Source market: collect() — group suppliers by country, weight by landed cost")

    def query_ref(self):
        return "growth_portal.analyzers.market"
