"""TikTok Ads adapter.

Attribution here lags harder than anywhere else in the stack. Re-querying the
same closed days nine hours apart moved 30 Jul from 6 to 7 payments and 31 Jul
from 2 to 5 — so a TikTok day read in the morning is understated by a wide
margin, and `maturity_hours` is set to 48 rather than the usual 24.

Revenue is derived, not read: the report returns `complete_payment` as a count
and `total_complete_payment_rate` as a ROAS. Which path produced the number is
recorded on the row, because a silently-derived figure that nobody can trace is
the thing this portal exists to prevent.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import frappe
import requests

from growth_portal.sources.base import ChangeRow, EntityRow, MetricRow, SourceAdapter

API = "https://business-api.tiktok.com/open_api/v1.3"

METRICS = [
    "spend", "impressions", "clicks", "conversion", "cost_per_conversion",
    "complete_payment", "value_per_complete_payment", "total_complete_payment_rate",
    "campaign_name",
]


class TikTokSource(SourceAdapter):
    name = "tiktok"
    timezone = "Europe/Istanbul"
    #: Measured, not assumed — see the module docstring.
    maturity_hours = 48

    def __init__(self):
        self.token = frappe.conf.get("tiktok_access_token")
        raw = frappe.conf.get("tiktok_advertiser_ids") or []
        if isinstance(raw, str):
            raw = [x.strip() for x in raw.split(",") if x.strip()]
        self.advertisers = [str(a) for a in raw]

    def _get(self, path, params):
        if not self.token:
            frappe.throw("TikTok is not configured — missing tiktok_access_token")
        r = requests.get(f"{API}/{path}", params=params,
                         headers={"Access-Token": self.token}, timeout=90)
        body = r.json()
        # TikTok answers HTTP 200 with an error code in the body. Checking only
        # the status code is how a dead token reads as an empty account — which
        # is exactly how this channel was once written off as having no spend.
        if body.get("code") != 0:
            raise RuntimeError(f"code={body.get('code')} {str(body.get('message'))[:200]}")
        return body.get("data") or {}

    def _report(self, advertiser_id, data_level, dimensions, date_from, date_to):
        page, out = 1, []
        while True:
            data = self._get("report/integrated/get/", {
                "advertiser_id": advertiser_id,
                "report_type": "BASIC",
                "data_level": data_level,
                "dimensions": json.dumps(dimensions),
                "metrics": json.dumps(METRICS),
                "start_date": date_from.isoformat(),
                "end_date": (date_to - timedelta(days=1)).isoformat(),
                "page": page,
                "page_size": 1000,
            })
            out.extend(data.get("list") or [])
            info = data.get("page_info") or {}
            if page >= (info.get("total_page") or 1):
                return out
            page += 1

    # ---- adapter ---------------------------------------------------------

    def entities(self):
        out = []
        for adv in self.advertisers:
            page = 1
            while True:
                data = self._get("campaign/get/", {
                    "advertiser_id": adv, "page": page, "page_size": 1000,
                })
                for c in data.get("list") or []:
                    out.append(EntityRow(
                        entity_type="Campaign",
                        key=f"tiktok:{c['campaign_id']}",
                        label=c.get("campaign_name") or c["campaign_id"],
                        meta={"platform": "tiktok", "advertiser_id": adv,
                              "status": c.get("operation_status"),
                              "objective": c.get("objective_type")},
                    ))
                info = data.get("page_info") or {}
                if page >= (info.get("total_page") or 1):
                    break
                page += 1
        return out

    def _budgets(self, advertiser_id):
        """Campaign budgets and delivery state.

        This account's campaigns are Upgraded Smart+, where budget can sit at
        either level; `budget` here is what the campaign itself authorises, and
        a zero means the ad group holds it.
        """
        out, page = {}, 1
        while True:
            data = self._get("campaign/get/", {
                "advertiser_id": advertiser_id, "page": page, "page_size": 1000,
            })
            for c in data.get("list") or []:
                out[str(c["campaign_id"])] = {
                    "budget": float(c.get("budget") or 0),
                    "budget_type": (c.get("budget_mode") or "").replace("BUDGET_MODE_", "").lower(),
                    "delivery_status": c.get("secondary_status") or c.get("operation_status") or "",
                }
            info = data.get("page_info") or {}
            if page >= (info.get("total_page") or 1):
                return out
            page += 1

    def metrics(self, date_from: date, date_to: date):
        rows = []
        for adv in self.advertisers:
            budgets = self._budgets(adv)
            for r in self._report(adv, "AUCTION_CAMPAIGN",
                                  ["campaign_id", "stat_time_day"], date_from, date_to):
                dim, met = r.get("dimensions") or {}, r.get("metrics") or {}
                spend = float(met.get("spend") or 0)
                payments = float(met.get("complete_payment") or 0)
                per_payment = float(met.get("value_per_complete_payment") or 0)
                roas = float(met.get("total_complete_payment_rate") or 0)

                # Prefer count × value. Fall back to spend × ROAS, and say which
                # one was used rather than leaving the number unattributable.
                if payments and per_payment:
                    revenue, basis = payments * per_payment, "count_x_value"
                elif spend and roas:
                    revenue, basis = spend * roas, "spend_x_roas"
                else:
                    revenue, basis = 0.0, "none"

                rows.append(MetricRow(
                    entity_type="Campaign",
                    key=f"tiktok:{dim.get('campaign_id')}",
                    day=frappe.utils.getdate(str(dim.get("stat_time_day"))[:10]),
                    spend=spend,
                    impressions=int(float(met.get("impressions") or 0)),
                    clicks=int(float(met.get("clicks") or 0)),
                    orders=payments,
                    revenue=revenue,
                    budget=budgets.get(str(dim.get("campaign_id")), {}).get("budget", 0.0),
                    budget_type=budgets.get(str(dim.get("campaign_id")), {}).get("budget_type", ""),
                    delivery_status=budgets.get(str(dim.get("campaign_id")), {}).get("delivery_status", ""),
                    extra={
                        "platform": "tiktok",
                        "advertiser_id": adv,
                        "currency": "TRY",
                        "revenue_basis": basis,
                        "reported_roas": roas,
                        "conversions_all": float(met.get("conversion") or 0),
                    },
                ))
        return rows

    def changes(self, date_from: date, date_to: date):
        out = []
        for adv in self.advertisers:
            try:
                data = self._get("changelog/get/", {
                    "advertiser_id": adv,
                    "start_time": int(frappe.utils.get_datetime(
                        f"{date_from} 00:00:00").timestamp()),
                    "end_time": int(frappe.utils.get_datetime(
                        f"{date_to - timedelta(days=1)} 23:59:59").timestamp()),
                    "page": 1, "page_size": 500,
                })
                for c in data.get("list") or []:
                    out.append(ChangeRow(
                        day=frappe.utils.getdate(str(c.get("create_time"))[:10]),
                        entity_type="Campaign",
                        key=f"tiktok:{c.get('object_id')}",
                        actor=c.get("operator") or "automation",
                        surface="api" if (c.get("source") or "").upper() == "API" else "web",
                        field_changed=c.get("operation_type") or "",
                        before=str(c.get("before"))[:120] if c.get("before") is not None else None,
                        after=str(c.get("after"))[:120] if c.get("after") is not None else None,
                    ))
            except Exception:
                frappe.log_error(frappe.get_traceback(), f"Growth Portal: tiktok changelog {adv}")
        return out

    def health(self):
        if not self.token:
            return {"source": self.name, "ok": False, "detail": "tiktok_access_token not set"}
        if not self.advertisers:
            return {"source": self.name, "ok": False, "detail": "tiktok_advertiser_ids not set"}
        try:
            data = self._get("advertiser/info/", {
                "advertiser_ids": json.dumps(self.advertisers),
                "fields": json.dumps(["advertiser_id", "advertiser_name", "currency", "timezone", "status"]),
            })
            return {"source": self.name, "ok": bool(data.get("list")),
                    "advertisers": data.get("list") or []}
        except Exception as e:
            return {"source": self.name, "ok": False, "detail": str(e)[:400]}
