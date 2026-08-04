"""AppsFlyer adapter — the only bridge between app revenue and ad campaigns.

Nothing else in this stack can say *which campaign* produced an app order.
Shopify tags app orders `via:app`, which says they came from the app and
nothing more. Google reports in-app purchases only for its own campaigns and
undercounts them — on 29 Jul – 3 Aug it recorded 24 where AppsFlyer saw 50.

**Cost is deliberately not imported.** Measured 29 Jul – 3 Aug 2026: AppsFlyer
reported $475.81 of Google spend for a window in which Google's own API
reported 1,409 TRY, about $47 — off by a factor of ten. The same account's
AppsFlyer dashboard has previously shown a ROAS of 42.37 against a real 1.88.
So this adapter pulls **events and attribution only**, and spend keeps coming
from each platform's own API. Any ROAS is therefore computed from two sources
on purpose, by an analyzer that says so, never assembled silently here.

Campaign ids are the platforms' own — verified: `23776204545` is the same id
Google reports, `120246750200010686` is a Meta campaign id. So rows are keyed
`google:{id}` / `meta:{id}`, matching exactly what the Google and Meta adapters
write, and the two join without a mapping table.

Two things about the numbers that are easy to misread and are recorded on every
row instead:

* **Revenue is cohort revenue, not daily revenue.** A row dated 1 August carries
  what users who *installed* on 1 August have spent since — it keeps growing for
  weeks. It is the right numerator for cohort ROAS against that day's spend, and
  the wrong one for "what did we earn on Monday".
* **Currency is USD and the timezone is UTC** — a third currency and a fourth
  timezone in a stack that already has MAD/TRY and Istanbul/Casablanca.
"""

from __future__ import annotations

from datetime import date, timedelta

import frappe
import requests

from growth_portal.sources.base import EntityRow, MetricRow, SourceAdapter

API = "https://hq1.appsflyer.com/api/master-agg-data/v4/app"

#: AppsFlyer's media-source names, mapped to the key prefix the ad adapters use.
#: Anything unmapped keeps its own name rather than being forced into a
#: platform — an unknown source is information, not noise.
PLATFORM = {
    "googleadwords_int": "google",
    "facebook ads": "meta",
    "restricted": "meta",          # Meta's SKAN/limited-data bucket
    "tiktokglobal_int": "tiktok",
    "bytedanceglobal_int": "tiktok",
}

#: Attribution and events only. `cost`, `roi` and `arpu` are omitted by design —
#: see the module docstring.
KPIS = [
    "installs",
    "af_purchase_unique_users",
    "af_purchase_event_counter",
    "af_purchase_sales_in_usd",
    "sessions",
    "uninstalls",
]

GROUPINGS = ["pid", "af_c_id", "c", "date"]


class AppsFlyerSource(SourceAdapter):
    name = "appsflyer"
    #: AppsFlyer reports UTC regardless of what the ad accounts use.
    timezone = "UTC"
    #: Deliberately long. Cohort revenue accrues for weeks after the install,
    #: so a row is never really final — 168h is the point past which it moves
    #: slowly enough to judge, not the point at which it stops.
    maturity_hours = 168

    def __init__(self):
        self.token = frappe.conf.get("appsflyer_api_token")
        raw = frappe.conf.get("appsflyer_app_ids") or []
        if isinstance(raw, str):
            raw = [x.strip() for x in raw.split(",") if x.strip()]
        self.app_ids = [str(a) for a in raw]
        self.currency = "USD"

    def _get(self, app_id, date_from, date_to):
        if not self.token:
            frappe.throw("AppsFlyer is not configured — missing appsflyer_api_token")
        r = requests.get(
            f"{API}/{app_id}",
            headers={"Authorization": f"Bearer {self.token}", "Accept": "text/csv"},
            params={
                "from": date_from.isoformat(),
                "to": (date_to - timedelta(days=1)).isoformat(),
                "groupings": ",".join(GROUPINGS),
                "kpis": ",".join(KPIS),
            },
            timeout=120,
        )
        if r.status_code == 429:
            # The Master API is rate limited per account, not per app. Retrying
            # in a loop spends the whole account's budget.
            raise RuntimeError("AppsFlyer rate limit reached")
        if not r.ok:
            raise RuntimeError(f"{r.status_code} {r.text[:300]}")
        return self._csv(r.text)

    @staticmethod
    def _csv(text):
        """The Master API answers CSV. Parsed here rather than trusting order."""
        import csv
        import io

        return list(csv.DictReader(io.StringIO(text)))

    @staticmethod
    def _num(v):
        try:
            return float(str(v).replace(",", ""))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _key(media_source, campaign_id):
        """The ad platforms' own campaign key, so the rows join without a map."""
        pid = (media_source or "").strip().lower()
        platform = PLATFORM.get(pid)
        cid = (campaign_id or "").strip()
        if platform and cid and cid.lower() not in ("none", "null", ""):
            return f"{platform}:{cid}", platform
        # Organic and unattributed traffic is real and worth carrying, but it
        # is not a campaign and must never be keyed as though it were.
        return f"appsflyer:{pid or 'unknown'}", pid or "unknown"

    # ---- adapter ---------------------------------------------------------

    def entities(self):
        """Campaigns as AppsFlyer sees them, plus the non-campaign sources.

        No new Campaign entities are minted for platforms that already report
        their own — the key collides on purpose, so the Google adapter's label
        wins and this adapter only adds app data to it.
        """
        out, seen = [], set()
        window_from = date.today() - timedelta(days=30)
        for app_id in self.app_ids:
            try:
                rows = self._get(app_id, window_from, date.today() + timedelta(days=1))
            except Exception:
                frappe.log_error(frappe.get_traceback(), f"Growth Portal: appsflyer entities {app_id}")
                continue
            for r in rows:
                key, platform = self._key(r.get("pid"), r.get("af_c_id"))
                if key in seen:
                    continue
                seen.add(key)
                out.append(EntityRow(
                    entity_type="Campaign",
                    key=key,
                    label=(r.get("c") or "").strip() or key,
                    meta={"platform": platform, "app_id": app_id, "via": "appsflyer"},
                ))
        return out

    def metrics(self, date_from: date, date_to: date):
        rows = []
        for app_id in self.app_ids:
            try:
                raw = self._get(app_id, date_from, date_to)
            except Exception:
                frappe.log_error(frappe.get_traceback(), f"Growth Portal: appsflyer metrics {app_id}")
                continue

            for r in raw:
                day = str(r.get("date") or "")[:10]
                if not day:
                    continue
                key, platform = self._key(r.get("pid"), r.get("af_c_id"))
                purchases = self._num(r.get("af_purchase_event_counter"))
                revenue = self._num(r.get("af_purchase_sales_in_usd"))
                installs = self._num(r.get("installs"))

                rows.append(MetricRow(
                    entity_type="Campaign",
                    key=key,
                    day=frappe.utils.getdate(day),
                    # Spend stays zero here on purpose. It comes from each
                    # platform's own API, which is the only place it is right.
                    spend=0.0,
                    orders=purchases,
                    revenue=revenue,
                    sessions=self._num(r.get("sessions")),
                    extra={
                        "platform": platform,
                        "source": "appsflyer",
                        "app_id": app_id,
                        "media_source": r.get("pid"),
                        "campaign_name": r.get("c"),
                        "currency": self.currency,
                        "installs": installs,
                        "purchasers": self._num(r.get("af_purchase_unique_users")),
                        "uninstalls": self._num(r.get("uninstalls")),
                        "install_to_purchase_pct": (
                            round(100.0 * purchases / installs, 2) if installs else None
                        ),
                        # Both flags exist so an analyzer cannot use these
                        # numbers without acknowledging what they are.
                        "revenue_basis": "cohort_ltv_by_install_date",
                        "cost_excluded": (
                            "AppsFlyer cost is not imported — it read 10x Google's own "
                            "spend on 29 Jul – 3 Aug 2026. Use the platform's spend."
                        ),
                    },
                ))
        return rows

    def health(self):
        if not self.token:
            return {"source": self.name, "ok": False, "detail": "appsflyer_api_token not set"}
        if not self.app_ids:
            return {"source": self.name, "ok": False, "detail": "appsflyer_app_ids not set"}
        try:
            yesterday = date.today() - timedelta(days=1)
            rows = self._get(self.app_ids[0], yesterday - timedelta(days=2), yesterday)
            sources = sorted({(r.get("pid") or "").strip() for r in rows if r.get("pid")})
            return {"source": self.name, "ok": bool(rows), "rows": len(rows),
                    "apps": self.app_ids, "media_sources": sources[:12],
                    "currency": self.currency, "timezone": self.timezone}
        except Exception as e:
            return {"source": self.name, "ok": False, "detail": str(e)[:400]}
