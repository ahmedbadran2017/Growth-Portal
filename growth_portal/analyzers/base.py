"""Analyzer contract — one per entity type, seven in total.

An analyzer turns metric rows into comparable `Row`s and hands them to the
verdict engine with a declared `Rule`. It owns the domain knowledge; the engine
owns the ranking and the guardrails.

The split matters: analyzers are where the business logic lives and therefore
where mistakes are made, so none of them is allowed to write a verdict
directly. Everything goes through the engine, which refuses anything without a
same-source denominator, a mature window, and a re-checkable query reference.
"""


from __future__ import annotations
from dataclasses import dataclass

from growth_portal.engine import verdict as engine


@dataclass
class AnalysisResult:
    entity_type: str
    rows_considered: int
    verdicts: list
    baseline: float | None
    notes: list


class Analyzer:
    entity_type: str = "base"

    #: Set by each subclass. Declared here, before any data is read.
    rule: engine.Rule = None

    def collect(self, window_start, window_end) -> list[engine.Row]:
        """Return comparable rows. One row per entity, already de-duplicated.

        Both bounds are **inclusive** days, matching how the guard reads them
        and how a human reads "6 Jul – 2 Aug". Sync uses exclusive bounds; the
        two conventions must not be mixed, or the guard passes a window a day
        younger than the one actually queried.
        """
        raise NotImplementedError

    def query_ref(self) -> str:
        """Where these numbers came from, precisely enough to re-run."""
        raise NotImplementedError

    def run(self, window_start, window_end, persist=True) -> AnalysisResult:
        rows = self.collect(window_start, window_end)
        verdicts = engine.judge(rows, self.rule, window_start, window_end, self.query_ref())
        if persist and verdicts:
            engine.persist(verdicts, self.entity_type)
        return AnalysisResult(
            entity_type=self.entity_type,
            rows_considered=len(rows),
            verdicts=verdicts,
            baseline=engine.baseline([r for r in rows if r.weight >= self.rule.min_weight]),
            notes=[],
        )
