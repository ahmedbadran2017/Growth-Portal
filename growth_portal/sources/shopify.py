"""Shopify adapter.

Product, price, inventory and page identity. Order attribution has been null since the July theme deploy, so do not read customer journey from here until that is fixed.
"""

from growth_portal.sources.base import SourceAdapter


class ShopifySource(SourceAdapter):
    name = "shopify"
    timezone = "UTC"
    maturity_hours = 6

    def entities(self):
        raise NotImplementedError("Shopify: entities() — products, variants, collections, page urls")

    def metrics(self, date_from, date_to):
        raise NotImplementedError("Shopify: metrics() — sessions and page-level conversion where available")
