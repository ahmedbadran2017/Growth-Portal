"""Microsoft Clarity adapter — the CRO signals no other source carries.

⚠️ **Written against the documented Data Export API, not verified against the
live project.** Every other adapter in this package was checked against real
responses before it was written; this one could not be — Clarity returned an
error on three separate queries on 4 Aug 2026, most likely the daily request
quota. It is registered in `tasks.SOURCES` only once it returns rows, so an
unverified adapter cannot make the health strip lie green.

Two hard limits shape everything here, and both come from the API rather than
from choice:

* **Three days of history, maximum.** `numOfDays` accepts 1-3. There is no way
  to backfill. A metric nobody pulled on the day is gone.
* **Ten requests per day.** One dimension per call, so the dimension list is a
  budget, not a wish list.

Together those mean Clarity is the one source that must be pulled on schedule
or not at all — which is exactly why `maturity_hours` is short and the sync
must not silently skip it.
"""

from __future__ import annotations

from datetime import date, timedelta

import frappe
import requests

from growth_portal.sources.base import EntityRow, MetricRow, SourceAdapter

API = "https://www.clarity.ms/export-data/api/v1/project-live-insights"

#: One request each, and the quota is ten a day. URL is the one that answers
#: "which page is hurting"; the rest are for segmenting it.
DIMENSIONS = ("URL", "Device", "Source")

#: Clarity returns these as separate metric blocks in one response. The
#: behavioural four are the reason to use Clarity at all — no other source in
#: this stack can see a user rage-clicking a broken button.
FRICTION = {
    "RageClickCount": "rage_clicks",
    "DeadClickCount": "dead_clicks",
    "ExcessiveScroll": "excessive_scroll",
    "QuickbackClick": "quick_backs",
    "ScriptErrorCount": "script_errors",
    "ErrorClickCount": "error_clicks",
}


class ClaritySource(SourceAdapter):
    name = "clarity"
    timezone = "UTC"
    maturity_hours = 24

    def __init__(self):
        self.token = frappe.conf.get("clarity_api_token")

    def _get(self, num_days, dimension):
        if not self.token:
            frappe.throw("Clarity is not configured — missing clarity_api_token")
        r = requests.get(
            API,
            headers={"Authorization": f"Bearer {self.token}"},
            params={"numOfDays": num_days, "dimension1": dimension},
            timeout=60,
        )
        if r.status_code == 429:
            # Named rather than retried. Ten requests a day is the whole budget,
            # and a retry loop spends tomorrow's as well.
            raise RuntimeError("Clarity daily request quota exhausted (10/day)")
        if not r.ok:
            raise RuntimeError(f"{r.status_code} {r.text[:300]}")
        return r.json()

    @staticmethod
    def _num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0

    # ---- adapter ---------------------------------------------------------

    def entities(self):
        """Pages seen in the last three days.

        Keyed on the URL as Clarity reports it. There is no stable page id in
        this stack, so the URL is the key — and it will churn when the theme
        changes, which is itself worth seeing on the timeline.
        """
        try:
            blocks = self._get(3, "URL")
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Growth Portal: clarity entities")
            return []

        seen, out = set(), []
        for block in blocks or []:
            for row in block.get("information") or []:
                url = row.get("URL")
                if not url or url in seen:
                    continue
                seen.add(url)
                out.append(EntityRow(
                    entity_type="Page",
                    key=f"clarity:{url}",
                    label=url,
                    meta={"platform": "clarity"},
                ))
        return out

    def metrics(self, date_from: date, date_to: date):
        """Friction per page, for whatever slice of the window Clarity still has.

        The requested window is honoured only as far as three days back. A
        longer request is not an error — it is silently impossible — so the
        actual coverage is written onto every row instead of being assumed.
        """
        today = date.today()
        earliest = today - timedelta(days=3)
        effective_from = max(date_from, earliest)
        num_days = max(1, min(3, (today - effective_from).days))

        try:
            blocks = self._get(num_days, "URL")
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Growth Portal: clarity metrics")
            return []

        # Clarity aggregates over numOfDays rather than returning a series, so
        # the whole pull lands on one day. Stated in `extra` — a reader must not
        # mistake a three-day total for a daily figure.
        day = today - timedelta(days=1)
        pages = {}
        for block in blocks or []:
            metric = block.get("metricName")
            for row in block.get("information") or []:
                url = row.get("URL")
                if not url:
                    continue
                m = pages.setdefault(url, MetricRow(
                    entity_type="Page", key=f"clarity:{url}", day=day,
                    extra={"platform": "clarity", "covers_days": num_days,
                           "is_period_total": True, "friction": {}},
                ))
                if metric == "Traffic":
                    m.sessions += self._num(row.get("totalSessionCount"))
                    m.extra["users"] = self._num(row.get("distinctUserCount"))
                    m.extra["bot_sessions"] = self._num(row.get("botSessionCount"))
                    m.extra["pages_per_session"] = self._num(row.get("pagesPerSessionPercentage"))
                elif metric == "EngagementTime":
                    m.extra["active_time"] = self._num(row.get("activeTime"))
                    m.extra["total_time"] = self._num(row.get("totalTime"))
                elif metric == "ScrollDepth":
                    m.extra["scroll_depth"] = self._num(row.get("averageScrollDepth"))
                elif metric in FRICTION:
                    m.extra["friction"][FRICTION[metric]] = self._num(
                        row.get("subTotal") or row.get("sessionsCount")
                    )

        # A friction count means nothing without its denominator — 40 rage
        # clicks on 20,000 sessions is noise and on 200 it is an emergency.
        for m in pages.values():
            if m.sessions:
                m.extra["friction_per_1k_sessions"] = {
                    k: round(1000.0 * v / m.sessions, 2)
                    for k, v in m.extra["friction"].items()
                }
        return list(pages.values())

    def health(self):
        if not self.token:
            return {"source": self.name, "ok": False, "detail": "clarity_api_token not set"}
        try:
            blocks = self._get(1, "Device")
            rows = sum(len(b.get("information") or []) for b in blocks or [])
            return {"source": self.name, "ok": rows > 0, "metric_blocks": len(blocks or []),
                    "rows": rows,
                    "note": "3-day history limit, 10 requests/day"}
        except Exception as e:
            return {"source": self.name, "ok": False, "detail": str(e)[:400]}
