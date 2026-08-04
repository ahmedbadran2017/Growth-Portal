"""Shopify adapter — the site funnel, and the deploy events nothing else records.

**Two of Shopify's own funnel metrics are unusable here and are deliberately
not imported.** Checkout on this store runs through a COD form, not Shopify's
native checkout, so `sessions_that_reached_checkout` and `conversion_rate`
never fire. Measured 21 Jul – 4 Aug 2026: 3-9 sessions "reached checkout" per
day and a conversion rate of 0.0%, on days the store took 200-415 orders.

Importing those would put an authoritative-looking 0.0% CVR on a screen. So the
adapter reads sessions, cart additions, orders and sales — all of which are
real — and computes CVR from Shopify's own order count. Same source on both
sides of the ratio, which is the only kind this portal accepts.

Shopify is also the only system that knows when the storefront changed. A theme
publish on 9 July took down the Google tag, the Meta pixel's context and the
Shopify journey at once, and the break was only diagnosable because someone
remembered the deploy. `changes()` puts it on the timeline so nobody has to.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import frappe
import requests

from growth_portal.sources.base import ChangeRow, EntityRow, MetricRow, SourceAdapter

API_VERSION = "2026-07"

#: Verified against the live store. `conversion_rate`,
#: `sessions_that_reached_checkout` and `sessions_that_completed_checkout` are
#: absent on purpose — see the module docstring.
SESSIONS_QL = (
    "FROM sessions SHOW sessions, sessions_with_cart_additions "
    "TIMESERIES day SINCE {since} UNTIL {until}"
)
SALES_QL = (
    "FROM sales SHOW orders, gross_sales, average_order_value "
    "TIMESERIES day SINCE {since} UNTIL {until}"
)

GQL_QUERY = """
query Ql($q: String!) {
  shopifyqlQuery(query: $q) {
    __typename
    ... on TableResponse {
      tableData { rowData columns { name dataType } }
      parseErrors { code message }
    }
  }
}
"""

THEMES_GQL = """
query Themes {
  themes(first: 25) { nodes { id name role createdAt updatedAt } }
}
"""


class ShopifySource(SourceAdapter):
    name = "shopify"
    timezone = "Africa/Casablanca"
    #: Sessions settle fast, but the last hours of a day keep arriving.
    maturity_hours = 12

    def __init__(self):
        self.domain = frappe.conf.get("shopify_domain")          # xxx.myshopify.com
        self.token = frappe.conf.get("shopify_access_token")
        self.currency = "MAD"

    def _gql(self, query, variables=None):
        if not (self.domain and self.token):
            frappe.throw("Shopify is not configured — missing shopify_domain / shopify_access_token")
        r = requests.post(
            f"https://{self.domain}/admin/api/{API_VERSION}/graphql.json",
            headers={"X-Shopify-Access-Token": self.token,
                     "Content-Type": "application/json"},
            json={"query": query, "variables": variables or {}},
            timeout=90,
        )
        if not r.ok:
            raise RuntimeError(f"{r.status_code} {r.text[:300]}")
        body = r.json()
        if body.get("errors"):
            raise RuntimeError(json.dumps(body["errors"])[:400])
        return body["data"]

    def _ql(self, template, date_from, date_to):
        """Run one ShopifyQL query and return rows keyed by day."""
        q = template.format(since=date_from.isoformat(), until=date_to.isoformat())
        data = self._gql(GQL_QUERY, {"q": q})["shopifyqlQuery"]
        errs = data.get("parseErrors")
        if errs:
            raise RuntimeError(f"ShopifyQL rejected the query: {json.dumps(errs)[:300]}")
        table = data.get("tableData") or {}
        cols = [c["name"] for c in table.get("columns", [])]
        out = {}
        for row in table.get("rowData", []):
            rec = dict(zip(cols, row))
            out[str(rec.get("day"))[:10]] = rec
        return out

    @staticmethod
    def _num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0

    # ---- adapter ---------------------------------------------------------

    def entities(self):
        # One entity: the storefront. Per-product page sessions are not exposed
        # by ShopifyQL, so claiming a Page entity per product would create rows
        # that can never be filled.
        return [EntityRow(
            entity_type="Page",
            key=f"shopify:{self.domain}",
            label="Storefront",
            meta={"platform": "shopify", "domain": self.domain},
        )]

    def metrics(self, date_from: date, date_to: date):
        last = date_to - timedelta(days=1)
        sessions = self._ql(SESSIONS_QL, date_from, last)
        sales = self._ql(SALES_QL, date_from, last)

        rows = []
        for day in sorted(set(sessions) | set(sales)):
            s = sessions.get(day, {})
            o = sales.get(day, {})
            n_sessions = self._num(s.get("sessions"))
            n_orders = self._num(o.get("orders"))
            rows.append(MetricRow(
                entity_type="Page",
                key=f"shopify:{self.domain}",
                day=frappe.utils.getdate(day),
                sessions=n_sessions,
                orders=n_orders,
                revenue=self._num(o.get("gross_sales")),
                extra={
                    "platform": "shopify",
                    "currency": self.currency,
                    "cart_addition_sessions": self._num(s.get("sessions_with_cart_additions")),
                    # Both sides from Shopify, so this is a real conversion rate
                    # rather than one system's numerator over another's total.
                    "cvr_pct": round(100.0 * n_orders / n_sessions, 3) if n_sessions else None,
                    "atc_rate_pct": (
                        round(100.0 * self._num(s.get("sessions_with_cart_additions")) / n_sessions, 3)
                        if n_sessions else None
                    ),
                    "aov": self._num(o.get("average_order_value")),
                    # Stated on every row so nobody goes looking for the
                    # checkout funnel and concludes it is broken rather than
                    # bypassed.
                    "checkout_metrics": "not collected — COD form bypasses Shopify checkout",
                },
            ))
        return rows

    def changes(self, date_from: date, date_to: date):
        """Theme publishes — the deploy events nothing else on the timeline has.

        Detected from the theme list rather than the event feed. The events feed
        on this store is dominated by the COD app creating draft orders and
        customers (thousands a day), and a theme publish is a needle in it.
        """
        out = []
        try:
            themes = self._gql(THEMES_GQL)["themes"]["nodes"]
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Growth Portal: shopify themes")
            return []

        for t in themes:
            updated = frappe.utils.getdate(str(t.get("updatedAt"))[:10])
            if not (date_from <= updated < date_to):
                continue
            live = (t.get("role") or "").upper() == "MAIN"
            out.append(ChangeRow(
                day=updated,
                entity_type="Page",
                key=f"shopify:{self.domain}",
                actor="storefront",
                surface="deploy",
                field_changed="theme.published" if live else "theme.updated",
                before=None,
                after=f"{t.get('name')} ({t.get('role')})",
            ))
        return out

    def health(self):
        if not (self.domain and self.token):
            return {"source": self.name, "ok": False,
                    "detail": "shopify_domain / shopify_access_token not set"}
        try:
            yesterday = date.today() - timedelta(days=1)
            rows = self._ql(SALES_QL, yesterday - timedelta(days=1), yesterday)
            return {"source": self.name, "ok": bool(rows), "domain": self.domain,
                    "days_returned": len(rows), "currency": self.currency}
        except Exception as e:
            return {"source": self.name, "ok": False, "detail": str(e)[:400]}
