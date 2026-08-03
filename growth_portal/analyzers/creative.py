"""Creative analyzer — fatigue shows as CTR decay before CPP moves"""

from growth_portal.analyzers.base import Analyzer
from growth_portal.engine import verdict as engine


class CreativeAnalyzer(Analyzer):
    entity_type = "Creative"

    rule = engine.Rule(
        entity_type="Creative",
        metric="cost_per_purchase",
        source="meta",
        min_sample=30,
        min_weight=3000,
    )

    def collect(self, window_start, window_end):
        raise NotImplementedError("Creative: collect() — ad-level spend and purchases grouped by creative asset id")

    def query_ref(self):
        return "growth_portal.analyzers.creative"
