"""Google Ads adapter.

Two passes, not one, and the reason is visible in the account: on 28 Jul the
App Install campaign reported 1,681 conversions worth 2,011, while PMAX
reported 10.5 conversions worth 10,387. One column, two entirely different
events. Summing them produces a ROAS that means nothing.

So spend/impressions/clicks come from the campaign report, and revenue comes
from a second pass segmented by `segments.conversion_action_name`, filtered to
the actions that actually represent a purchase. Everything else is carried in
`extra` and never enters revenue.

Currency here is TRY while orders in ERPNext are MAD. Nothing in this file
converts between them — the currency travels with the row, and conversion
happens once at the point of comparison, never silently inside a source.
"""

from __future__ import annotations

from datetime import date, timedelta

import frappe

from growth_portal.sources.base import ChangeRow, EntityRow, MetricRow, SourceAdapter

#: Conversion actions counted as revenue. Matched case-insensitively as a
#: substring so a renamed action keeps working. Anything not listed is recorded
#: in `extra` and excluded — an app install is a real event, just not a sale.
PURCHASE_ACTIONS = ("purchase", "cod purchase", "easysellpurchase")

CAMPAIGN_GAQL = """
    SELECT campaign.id, campaign.name, campaign.status,
           campaign.advertising_channel_type, segments.date,
           metrics.cost_micros, metrics.impressions, metrics.clicks
    FROM campaign
    WHERE segments.date BETWEEN '{f}' AND '{t}'
"""

CONVERSION_GAQL = """
    SELECT campaign.id, segments.date, segments.conversion_action_name,
           metrics.conversions, metrics.conversions_value
    FROM campaign
    WHERE segments.date BETWEEN '{f}' AND '{t}'
      AND metrics.conversions > 0
"""

CHANGE_GAQL = """
    SELECT change_event.change_date_time, change_event.user_email,
           change_event.client_type, change_event.change_resource_type,
           change_event.changed_fields, change_event.campaign
    FROM change_event
    WHERE change_event.change_date_time >= '{f}'
      AND change_event.change_date_time <= '{t}'
    ORDER BY change_event.change_date_time DESC
    LIMIT 5000
"""


def _is_purchase(action_name):
    n = (action_name or "").lower()
    return any(p in n for p in PURCHASE_ACTIONS)


def _surface(client_type):
    c = (client_type or "").upper()
    if "RECOMMENDATION" in c or "AUTOMATED" in c:
        return "recommendation"
    if "API" in c or "SCRIPT" in c:
        return "api"
    if "MOBILE" in c:
        return "mobile"
    return "web"


class GoogleAdsSource(SourceAdapter):
    name = "google_ads"
    timezone = "Europe/Istanbul"
    #: PMAX conversion value keeps landing for up to three days. Judging a
    #: Google day on the morning read understates it every single time.
    maturity_hours = 72

    def __init__(self):
        self.customer_id = str(frappe.conf.get("google_ads_customer_id") or "").replace("-", "")
        self.login_customer_id = str(frappe.conf.get("google_ads_login_customer_id") or "").replace("-", "")
        self._client = None
        self.currency = "TRY"

    # ---- transport -------------------------------------------------------

    def client(self):
        if self._client:
            return self._client
        from google.ads.googleads.client import GoogleAdsClient

        cfg = {
            "developer_token": frappe.conf.get("google_ads_developer_token"),
            "client_id": frappe.conf.get("google_ads_client_id"),
            "client_secret": frappe.conf.get("google_ads_client_secret"),
            "refresh_token": frappe.conf.get("google_ads_refresh_token"),
            "use_proto_plus": True,
        }
        missing = [k for k, v in cfg.items() if not v]
        if missing or not self.customer_id:
            frappe.throw(
                "Google Ads is not configured — missing "
                + ", ".join(missing or ["google_ads_customer_id"])
            )
        if self.login_customer_id:
            cfg["login_customer_id"] = self.login_customer_id
        self._client = GoogleAdsClient.load_from_dict(cfg)
        return self._client

    def _search(self, gaql):
        svc = self.client().get_service("GoogleAdsService")
        # search_stream, not search: a 90-day pull at campaign × date × action
        # granularity runs to tens of thousands of rows, and paging that with
        # search() is several times slower for an identical result.
        for batch in svc.search_stream(customer_id=self.customer_id, query=gaql):
            for row in batch.results:
                yield row

    # ---- adapter ---------------------------------------------------------

    def entities(self):
        gaql = """
            SELECT campaign.id, campaign.name, campaign.status,
                   campaign.advertising_channel_type
            FROM campaign
            WHERE campaign.status != 'REMOVED'
        """
        return [
            EntityRow(
                entity_type="Campaign",
                key=f"google:{r.campaign.id}",
                label=r.campaign.name,
                meta={"platform": "google_ads",
                      "channel": r.campaign.advertising_channel_type.name,
                      "status": r.campaign.status.name},
            )
            for r in self._search(gaql)
        ]

    def metrics(self, date_from: date, date_to: date):
        f, t = date_from.isoformat(), (date_to - timedelta(days=1)).isoformat()
        bucket = {}

        def row_for(campaign_id, day):
            key = (f"google:{campaign_id}", day)
            return bucket.setdefault(
                key,
                MetricRow(entity_type="Campaign", key=key[0], day=key[1],
                          extra={"currency": self.currency, "platform": "google_ads",
                                 "conversions_by_action": {},
                                 "non_purchase_conversions": 0.0}),
            )

        for r in self._search(CAMPAIGN_GAQL.format(f=f, t=t)):
            m = row_for(r.campaign.id, r.segments.date)
            m.spend += r.metrics.cost_micros / 1_000_000
            m.impressions += r.metrics.impressions
            m.clicks += r.metrics.clicks
            m.extra["channel"] = r.campaign.advertising_channel_type.name

        for r in self._search(CONVERSION_GAQL.format(f=f, t=t)):
            # Conversions land on days a campaign spent nothing. Skipping those
            # would understate a campaign paused after it drove orders.
            m = row_for(r.campaign.id, r.segments.date)
            action = r.segments.conversion_action_name
            n, val = r.metrics.conversions, r.metrics.conversions_value
            by = m.extra["conversions_by_action"]
            by[action] = round(by.get(action, 0.0) + n, 2)
            if _is_purchase(action):
                m.orders += n
                m.revenue += val
            else:
                m.extra["non_purchase_conversions"] += n

        return list(bucket.values())

    def changes(self, date_from: date, date_to: date):
        """Who changed what, and from which surface.

        `client_type` is the load-bearing field: a budget that moved from
        GOOGLE_ADS_RECOMMENDATIONS was the platform's own automation, not the
        media buyer, and that decides who you talk to about it.
        """
        f = f"{date_from.isoformat()} 00:00:00"
        t = f"{(date_to - timedelta(days=1)).isoformat()} 23:59:59"
        try:
            rows = list(self._search(CHANGE_GAQL.format(f=f, t=t)))
        except Exception:
            # Google caps change_event at 30 days and throws outside the window.
            # A failed timeline pull must not take the whole sync down with it.
            frappe.log_error(frappe.get_traceback(), "Growth Portal: google change_event")
            return []

        out = []
        for r in rows:
            ce = r.change_event
            campaign_id = (ce.campaign or "").rsplit("/", 1)[-1]
            for fieldname in ce.changed_fields.paths:
                out.append(ChangeRow(
                    day=frappe.utils.getdate(str(ce.change_date_time)[:10]),
                    entity_type="Campaign",
                    key=f"google:{campaign_id}" if campaign_id else "google:account",
                    actor=ce.user_email or "automation",
                    surface=_surface(ce.client_type.name),
                    field_changed=f"{ce.change_resource_type.name}.{fieldname}",
                ))
        return out

    def health(self):
        try:
            rows = list(self._search(
                "SELECT customer.id, customer.currency_code, customer.time_zone "
                "FROM customer LIMIT 1"
            ))
            if not rows:
                return {"source": self.name, "ok": False, "detail": "no customer row returned"}
            c = rows[0].customer
            self.currency = c.currency_code
            return {"source": self.name, "ok": True, "customer_id": c.id,
                    "currency": c.currency_code, "account_timezone": c.time_zone}
        except Exception as e:
            return {"source": self.name, "ok": False, "detail": str(e)[:400]}
