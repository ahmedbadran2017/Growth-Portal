"""Connections and settings.

Two things the interface could not do before: see whether a source is actually
authorised, and change a threshold without editing Python.

Credentials are never returned. `configured` says whether the key exists in
site_config.json and nothing more — a portal that can display a token is a
portal that can leak one.
"""

import frappe

from growth_portal import tasks

#: Every source the portal knows about, whether or not it is wired yet. The
#: interface shows the unwired ones on purpose: a Connections page listing only
#: the one working source reads as "everything is connected".
CATALOGUE = [
    {"source": "erpnext", "label": "ERPNext", "timezone": "Europe/Istanbul",
     "maturity_hours": 6, "credential_key": None, "covers": "Orders, delivery outcomes, revenue"},
    {"source": "meta", "label": "Meta Ads", "timezone": "Africa/Casablanca",
     "maturity_hours": 24, "credential_key": "meta_access_token", "covers": "Spend, creative, pixel events"},
    {"source": "google_ads", "label": "Google Ads", "timezone": "Europe/Istanbul",
     "maturity_hours": 72, "credential_key": "google_ads_refresh_token", "covers": "Spend, PMAX value, conversion actions"},
    {"source": "tiktok", "label": "TikTok Ads", "timezone": "Europe/Istanbul",
     "maturity_hours": 48, "credential_key": "tiktok_access_token", "covers": "Spend, creative, changelog"},
    {"source": "shopify", "label": "Shopify", "timezone": "Africa/Casablanca",
     "maturity_hours": 12, "credential_key": "shopify_access_token",
     "covers": "Sessions, add-to-cart, orders, site CVR, theme deploys"},
    {"source": "ga4", "label": "Google Analytics 4", "timezone": "Africa/Casablanca",
     "maturity_hours": 48, "credential_key": "ga4_credentials", "covers": "Landing-page CVR, channel mix"},
    {"source": "clarity", "label": "Microsoft Clarity", "timezone": "UTC",
     "maturity_hours": 24, "credential_key": "clarity_api_token",
     "covers": "Rage clicks, dead clicks, scroll depth (3-day history, 10 req/day)"},
    {"source": "semrush", "label": "SEMrush", "timezone": "UTC",
     "maturity_hours": 168, "credential_key": "semrush_api_key", "covers": "Positions, organic traffic"},
    {"source": "appsflyer", "label": "AppsFlyer", "timezone": "UTC",
     "maturity_hours": 48, "credential_key": "appsflyer_api_token", "covers": "Installs, in-app events, mobile ROAS"},
]


@frappe.whitelist()
def connections():
    """One row per source: is it wired, is it authorised, did it last pull."""
    rows = []
    syncs = {
        r.source: r
        for r in frappe.db.sql(
            """SELECT source, run_day, ok, rows_written, duration_ms
               FROM `tabSource Sync`
               WHERE run_day >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
               ORDER BY run_day DESC""",
            as_dict=True,
        )
    }
    overrides = {
        r.source: r
        for r in frappe.get_all(
            "Source Connection",
            fields=["source", "enabled", "account_id", "last_ok", "last_error",
                    "last_rows", "consecutive_failures"],
        )
    }

    for c in CATALOGUE:
        o = overrides.get(c["source"], {})
        s = syncs.get(c["source"], {})
        implemented = c["source"] in tasks.SOURCES
        rows.append({
            **c,
            # Deliberately three separate booleans. "Implemented but not
            # authorised" and "authorised but not implemented" are different
            # problems, and collapsing them into one status light hides which.
            "implemented": implemented,
            "configured": bool(c["credential_key"] is None or frappe.conf.get(c["credential_key"])),
            "enabled": bool(o.get("enabled")) if o else implemented,
            "account_id": o.get("account_id"),
            "last_ok": o.get("last_ok") or (s.get("run_day") if s.get("ok") else None),
            "last_error": o.get("last_error"),
            "last_rows": s.get("rows_written", o.get("last_rows") or 0),
            "consecutive_failures": o.get("consecutive_failures") or 0,
            "healthy": bool(s.get("ok")),
        })
    return rows


@frappe.whitelist()
def test_connection(source):
    """Probe one source now and record the outcome.

    A source that has never been probed and a source that is failing look the
    same on a dashboard until someone presses this.
    """
    if source not in tasks.SOURCES:
        return {"ok": False, "detail": f"{source} has no adapter yet — nothing to probe."}
    try:
        adapter = frappe.get_attr(tasks.SOURCES[source])()
        health = adapter.health()
        _record(source, bool(health.get("ok")), health)
        return {"ok": bool(health.get("ok")), "detail": health}
    except Exception:
        tb = frappe.get_traceback()
        _record(source, False, {"error": tb[:1000]})
        return {"ok": False, "detail": tb[:1000]}


def _record(source, ok, detail):
    name = frappe.db.exists("Source Connection", {"source": source})
    payload = {
        "last_error": "" if ok else str(detail)[:500],
        "consecutive_failures": 0 if ok else (
            (frappe.db.get_value("Source Connection", name, "consecutive_failures") or 0) + 1
            if name else 1
        ),
    }
    if ok:
        payload["last_ok"] = frappe.utils.now_datetime()
    if name:
        frappe.db.set_value("Source Connection", name, payload)
    else:
        frappe.get_doc({"doctype": "Source Connection", "source": source,
                        "enabled": 1, **payload}).insert(ignore_permissions=True)
    frappe.db.commit()


@frappe.whitelist()
def settings():
    doc = frappe.get_single("Growth Settings")
    return {
        "alert_email": doc.alert_email or frappe.conf.get("growth_alert_email") or "",
        "whatsapp_to": doc.whatsapp_to or "",
        "whatsapp_webhook": bool(doc.whatsapp_webhook or frappe.conf.get("growth_alert_whatsapp_webhook")),
        "whatsapp_min_severity": doc.whatsapp_min_severity or "High",
        "window_days": doc.window_days or 28,
        "judge_hour": doc.judge_hour or 9,
        "agent_enabled": bool(doc.agent_enabled),
        "agent_effort": doc.agent_effort or "high",
        "agent_model": doc.agent_model or "claude-opus-5",
        "agent_can_execute": bool(doc.agent_can_execute),
        "api_key_configured": bool(frappe.conf.get("anthropic_api_key")),
    }


@frappe.whitelist()
def save_settings(**kwargs):
    """Write the editable fields. `agent_can_execute` is not one of them."""
    doc = frappe.get_single("Growth Settings")
    allowed = ("alert_email", "whatsapp_to", "whatsapp_webhook", "whatsapp_min_severity",
               "window_days", "judge_hour", "agent_enabled", "agent_effort", "agent_model")
    for k in allowed:
        if k in kwargs:
            doc.set(k, kwargs[k])
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return settings()


@frappe.whitelist()
def rules():
    """Thresholds, as rows rather than as constants in Python.

    Each default below was set from a specific wrong answer, so the seeded
    values are the ones that were verified — not round numbers.
    """
    existing = frappe.get_all(
        "Growth Rule",
        fields=["name", "entity_type", "metric", "source", "enabled", "higher_is_better",
                "min_sample", "min_weight", "min_days", "gap_act", "gap_material",
                "impact_floor", "kill_at", "dormant_after_days"],
    )
    if existing:
        return existing
    from growth_portal.analyzers.product import ProductAnalyzer

    r = ProductAnalyzer.rule
    return [{
        "name": None, "entity_type": r.entity_type, "metric": r.metric, "source": r.source,
        "enabled": 1, "higher_is_better": int(r.higher_is_better), "min_sample": r.min_sample,
        "min_weight": r.min_weight, "min_days": r.min_days, "gap_act": r.gap_act,
        "gap_material": r.gap_material, "impact_floor": r.impact_floor,
        "kill_at": r.kill_at, "dormant_after_days": r.dormant_after_days,
    }]


@frappe.whitelist()
def save_rule(**kwargs):
    name = kwargs.pop("name", None)
    if name and frappe.db.exists("Growth Rule", name):
        doc = frappe.get_doc("Growth Rule", name)
        doc.update(kwargs)
    else:
        doc = frappe.get_doc({"doctype": "Growth Rule", **kwargs})
    doc.save(ignore_permissions=True) if doc.get("name") else doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc.name


@frappe.whitelist()
def alerts(limit=30):
    return frappe.get_all(
        "Growth Alert",
        fields=["name", "subject", "channel", "recipient", "status", "sent_at", "error", "agent_run"],
        order_by="creation desc", limit=int(limit),
    )


@frappe.whitelist()
def agent_runs(limit=20):
    return frappe.get_all(
        "Agent Run",
        fields=["name", "task", "status", "model", "effort", "tool_call_count", "creation", "finding"],
        order_by="creation desc", limit=int(limit),
    )
