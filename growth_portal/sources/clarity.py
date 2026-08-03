"""Microsoft Clarity adapter.

Behavioural friction per page: dead clicks, JS errors, Core Web Vitals. Blind to Shopify checkout, which blocks third-party scripts.
"""

from growth_portal.sources.base import SourceAdapter


class ClaritySource(SourceAdapter):
    name = "clarity"
    timezone = "UTC"
    maturity_hours = 24

    def entities(self):
        raise NotImplementedError("Microsoft Clarity: entities() — pages carrying meaningful traffic")

    def metrics(self, date_from, date_to):
        raise NotImplementedError("Microsoft Clarity: metrics() — dead clicks, rage clicks, js errors, LCP/CLS per page per day")
