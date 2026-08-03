"""Source adapter contract.

Eight systems, one shape. Each adapter answers three questions and nothing
more: what entities exist here, what did they do per day, and what changed.

That third one is the reason this layer exists at all. Four independent
systems broke on the same day once — a Google tag, a Meta pixel's context,
Shopify's attribution, and average basket size — and no single platform could
show it. It only appeared when four timelines were laid side by side with the
deploys marked on them. `changes()` is that overlay.
"""


from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date


@dataclass
class EntityRow:
    """An entity as this source knows it."""
    entity_type: str            # Product | Supplier | Campaign | Creative | Page | Media Buyer | Source Market
    key: str                    # stable id in THIS source
    label: str
    parent_key: str | None = None
    meta: dict = field(default_factory=dict)


@dataclass
class MetricRow:
    """One entity, one day, one source. Never pre-aggregated."""
    entity_type: str
    key: str
    day: date
    spend: float = 0.0
    revenue: float = 0.0
    orders: float = 0.0
    delivered: float = 0.0
    impressions: float = 0.0
    clicks: float = 0.0
    sessions: float = 0.0
    extra: dict = field(default_factory=dict)


@dataclass
class ChangeRow:
    """Something a human or an automation did. The timeline's second layer.

    `actor` and `surface` are what turn an audit log into an answer: a budget
    that moved from GOOGLE_ADS_RECOMMENDATIONS was the platform's own
    automation, not the media buyer, and that distinction changes who you talk
    to about it.
    """
    day: date
    entity_type: str
    key: str
    actor: str                  # user email, or the automation's name
    surface: str                # web | mobile | api | recommendation | deploy
    field_changed: str
    before: str | None = None
    after: str | None = None


class SourceAdapter:
    """Subclass per system. Keep them thin — no judgement lives here.

    An adapter that starts computing rates is an adapter that has begun
    disagreeing with the other seven. Ratios belong in analyzers, where the
    denominator can be checked.
    """

    name: str = "base"
    timezone: str = "UTC"
    maturity_hours: int = 24     # how long its numbers keep moving after a day closes

    def entities(self) -> list[EntityRow]:
        raise NotImplementedError

    def metrics(self, date_from: date, date_to: date) -> list[MetricRow]:
        raise NotImplementedError

    def changes(self, date_from: date, date_to: date) -> list[ChangeRow]:
        """Optional. Return [] for sources with no audit log."""
        return []

    def health(self) -> dict:
        """Cheap liveness probe, written to Source Sync on every run.

        A source that silently stops returning rows looks identical to a source
        reporting zeros, and the second one is a business emergency while the
        first is a broken token.
        """
        return {"source": self.name, "ok": True}
