"""Meta Ads adapter.

Several accounts, not one, and they do not share a timezone: Justyol-Morocco
reports on Africa/Casablanca while the rest report on Europe/Istanbul. Insights
are always returned in each account's own timezone, so the account id is kept
on every row and no day is ever compared across accounts without it.

Revenue comes from the `purchase` action only. `actions` returns a dozen event
types in one array — landing page views, add-to-carts, initiate-checkouts — and
summing the array is how a 3x ROAS becomes a 30x one.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import frappe
import requests

from growth_portal.sources.base import ChangeRow, EntityRow, MetricRow, SourceAdapter

API = "https://graph.facebook.com/v23.0"

#: The purchase event, under the names Meta reports it by. `omni_purchase`
#: double-counts against the other two, so it is deliberately not here.
PURCHASE_TYPES = ("offsite_conversion.fb_pixel_purchase", "purchase")

#: Carried but never counted as revenue — this is the funnel, and a collapse in
#: one of these is an early warning that the pixel broke, not that sales did.
FUNNEL_TYPES = (
    "offsite_conversion.fb_pixel_view_content",
    "offsite_conversion.fb_pixel_add_to_cart",
    "offsite_conversion.fb_pixel_initiate_checkout",
    "landing_page_view",
    "link_click",
)


def _sum_actions(rows, wanted):
    """Sum one action type out of Meta's mixed `actions`/`action_values` array."""
    total = 0.0
    for a in rows or []:
        if a.get("action_type") in wanted:
            total += float(a.get("value") or 0)
    return total


class MetaSource(SourceAdapter):
    name = "meta"
    #: The majority of accounts. Justyol-Morocco overrides this per row, which
    #: is why `account_timezone` travels in `extra` rather than living here.
    timezone = "Europe/Istanbul"
    maturity_hours = 24

    def __init__(self):
        self.token = frappe.conf.get("meta_access_token")
        raw = frappe.conf.get("meta_ad_accounts") or []
        if isinstance(raw, str):
            raw = [x.strip() for x in raw.split(",") if x.strip()]
        self.accounts = [a if str(a).startswith("act_") else f"act_{a}" for a in raw]
        self._meta = {}

    def _get(self, path, params=None):
        if not self.token:
            frappe.throw("Meta is not configured — missing meta_access_token")
        p = {"access_token": self.token, **(params or {})}
        r = requests.get(f"{API}/{path}", params=p, timeout=90)
        if not r.ok:
            raise RuntimeError(f"{r.status_code} {r.text[:300]}")
        return r.json()

    def _paged(self, path, params=None):
        """Follow Meta's cursor pagination.

        Insights for a 90-day window at ad level page well past the first
        response, and stopping at page one silently truncates the account.
        """
        data = self._get(path, params)
        while True:
            for row in data.get("data", []):
                yield row
            nxt = (data.get("paging") or {}).get("next")
            if not nxt:
                return
            r = requests.get(nxt, timeout=90)
            if not r.ok:
                return
            data = r.json()

    def _budgets(self, act):
        """Campaign budgets, fetched once per account and joined onto insights.

        Meta reports budget on the campaign object and spend on insights, so a
        single call cannot give both. Budgets are in minor units — 1500 means
        15.00 — and dividing by 100 in the wrong place is a 100x error in the
        one number scaling decisions rest on.
        """
        out = {}
        for c in self._paged(f"{act}/campaigns", {
            "fields": "id,daily_budget,lifetime_budget,effective_status,"
                      "issues_info,budget_remaining",
            "limit": 500,
        }):
            daily = c.get("daily_budget")
            lifetime = c.get("lifetime_budget")
            out[c["id"]] = {
                "budget": (float(daily) / 100.0) if daily else
                          (float(lifetime) / 100.0 if lifetime else 0.0),
                "budget_type": "daily" if daily else ("lifetime" if lifetime else ""),
                # Empty when the budget sits on the ad set rather than the
                # campaign (Meta's ABO). Recorded as "adset" rather than 0 so a
                # capacity view does not report "no budget" for a campaign that
                # simply holds it one level down.
                "delivery_status": c.get("effective_status") or "",
                "issues": [i.get("error_summary") for i in (c.get("issues_info") or [])],
            }
        return out

    def _account_meta(self, act):
        if act not in self._meta:
            info = self._get(act, {"fields": "name,currency,timezone_name,account_status"})
            self._meta[act] = info
        return self._meta[act]

    # ---- adapter ---------------------------------------------------------

    def entities(self):
        out = []
        for act in self.accounts:
            for c in self._paged(f"{act}/campaigns",
                                 {"fields": "id,name,status,objective", "limit": 200}):
                out.append(EntityRow(
                    entity_type="Campaign",
                    key=f"meta:{c['id']}",
                    label=c.get("name") or c["id"],
                    meta={"platform": "meta", "account": act,
                          "status": c.get("status"), "objective": c.get("objective")},
                ))
        return out

    def metrics(self, date_from: date, date_to: date):
        rows = []
        for act in self.accounts:
            info = self._account_meta(act)
            budgets = self._budgets(act)
            params = {
                "level": "campaign",
                "time_increment": 1,
                "time_range": json.dumps({
                    "since": date_from.isoformat(),
                    "until": (date_to - timedelta(days=1)).isoformat(),
                }),
                "fields": "campaign_id,campaign_name,spend,impressions,clicks,"
                          "actions,action_values,date_start",
                "limit": 500,
                # Without this Meta silently applies the account's attribution
                # window, which differs between accounts and makes two accounts
                # non-comparable for reasons nothing on the row explains.
                "action_attribution_windows": json.dumps(["7d_click", "1d_view"]),
            }
            for r in self._paged(f"{act}/insights", params):
                actions, values = r.get("actions"), r.get("action_values")
                m = MetricRow(
                    entity_type="Campaign",
                    key=f"meta:{r['campaign_id']}",
                    day=frappe.utils.getdate(r["date_start"]),
                    spend=float(r.get("spend") or 0),
                    impressions=int(float(r.get("impressions") or 0)),
                    clicks=int(float(r.get("clicks") or 0)),
                    orders=_sum_actions(actions, PURCHASE_TYPES),
                    revenue=_sum_actions(values, PURCHASE_TYPES),
                    budget=budgets.get(r["campaign_id"], {}).get("budget", 0.0),
                    budget_type=budgets.get(r["campaign_id"], {}).get("budget_type") or "adset",
                    delivery_status=budgets.get(r["campaign_id"], {}).get("delivery_status", ""),
                    extra={
                        "platform": "meta",
                        "account": act,
                        "currency": info.get("currency"),
                        # Kept per row on purpose: Justyol-Morocco reports on
                        # Casablanca and the others on Istanbul, so a day here
                        # is not the same day there.
                        "account_timezone": info.get("timezone_name"),
                        "attribution": "7d_click,1d_view",
                        "issues": budgets.get(r["campaign_id"], {}).get("issues") or [],
                        "funnel": {
                            a.get("action_type"): float(a.get("value") or 0)
                            for a in (actions or [])
                            if a.get("action_type") in FUNNEL_TYPES
                        },
                    },
                )
                rows.append(m)
        return rows

    def changes(self, date_from: date, date_to: date):
        """Budget and status edits from the account activity log."""
        out = []
        for act in self.accounts:
            try:
                params = {
                    "fields": "event_type,event_time,actor_name,actor_id,object_id,"
                              "object_name,extra_data,translated_event_type",
                    "since": date_from.isoformat(),
                    "until": (date_to - timedelta(days=1)).isoformat(),
                    "limit": 500,
                }
                for a in self._paged(f"{act}/activities", params):
                    extra = a.get("extra_data") or "{}"
                    try:
                        extra = json.loads(extra) if isinstance(extra, str) else extra
                    except Exception:
                        extra = {}
                    out.append(ChangeRow(
                        day=frappe.utils.getdate(str(a.get("event_time"))[:10]),
                        entity_type="Campaign",
                        key=f"meta:{a.get('object_id')}",
                        actor=a.get("actor_name") or "automation",
                        # Meta does not report the surface, and guessing one
                        # would put a fabricated value next to Google's real
                        # `client_type` on the same timeline.
                        surface="unknown",
                        field_changed=a.get("event_type") or "",
                        before=str(extra.get("old_value"))[:120] if extra.get("old_value") is not None else None,
                        after=str(extra.get("new_value"))[:120] if extra.get("new_value") is not None else None,
                    ))
            except Exception:
                frappe.log_error(frappe.get_traceback(), f"Growth Portal: meta activities {act}")
        return out

    def health(self):
        if not self.token:
            return {"source": self.name, "ok": False, "detail": "meta_access_token not set"}
        if not self.accounts:
            return {"source": self.name, "ok": False, "detail": "meta_ad_accounts not set"}
        try:
            seen = []
            for act in self.accounts:
                info = self._account_meta(act)
                seen.append({"id": act, "name": info.get("name"),
                             "currency": info.get("currency"),
                             "timezone": info.get("timezone_name"),
                             "status": info.get("account_status")})
            return {"source": self.name, "ok": True, "accounts": seen}
        except Exception as e:
            return {"source": self.name, "ok": False, "detail": str(e)[:400]}
