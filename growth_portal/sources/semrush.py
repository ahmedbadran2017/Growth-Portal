"""Semrush adapter.

Rankings, keywords and competitors. Weekly crawl — a daily read is the same number seven times.
"""

from growth_portal.sources.base import SourceAdapter


class SemrushSource(SourceAdapter):
    name = "semrush"
    timezone = "UTC"
    maturity_hours = 168

    def entities(self):
        raise NotImplementedError("Semrush: entities() — tracked urls and keywords")

    def metrics(self, date_from, date_to):
        raise NotImplementedError("Semrush: metrics() — position, volume, estimated traffic per url")
