"""Google Analytics 4 adapter.

Funnel and traffic source. API access still unconfirmed — health() must fail loudly rather than return zeros.
"""

from growth_portal.sources.base import SourceAdapter


class GA4Source(SourceAdapter):
    name = "ga4"
    timezone = "Europe/Istanbul"
    maturity_hours = 24

    def entities(self):
        raise NotImplementedError("Google Analytics 4: entities() — landing pages and traffic sources")

    def metrics(self, date_from, date_to):
        raise NotImplementedError("Google Analytics 4: metrics() — sessions, engaged sessions, item views per day")
