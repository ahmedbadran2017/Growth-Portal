"""Page analyzer — traffic that does not convert is a page problem"""

from growth_portal.analyzers.base import Analyzer
from growth_portal.engine import verdict as engine


class PageAnalyzer(Analyzer):
    entity_type = "Page"

    rule = engine.Rule(
        entity_type="Page",
        metric="conversion_rate",
        source="shopify",
        min_sample=200,
        min_weight=0,
    )

    def collect(self, window_start, window_end):
        raise NotImplementedError("Page: collect() — sessions from GA4/Shopify against ERPNext orders for the same product url")

    def query_ref(self):
        return "growth_portal.analyzers.page"
