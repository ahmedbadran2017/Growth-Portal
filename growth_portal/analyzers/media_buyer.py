"""Media buyer analyzer — changes tied to the outcome they produced"""

from growth_portal.analyzers.base import Analyzer
from growth_portal.engine import verdict as engine


class MediaBuyerAnalyzer(Analyzer):
    entity_type = "Media Buyer"

    rule = engine.Rule(
        entity_type="Media Buyer",
        metric="cost_per_delivered_order",
        source="meta",
        min_sample=100,
        min_weight=20000,
    )

    def collect(self, window_start, window_end):
        raise NotImplementedError("Media buyer: collect() — account-to-buyer map, plus change events joined to the 3 days after each edit")

    def query_ref(self):
        return "growth_portal.analyzers.media_buyer"
