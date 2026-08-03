"""Alert delivery.

Every alert is recorded as a Growth Alert row before anything is sent, so a
delivery failure is visible rather than silent. A portal that stops alerting
looks exactly like a portal with nothing to report — the row is what tells the
two apart.

Nothing is sent unless a recipient is configured. There is deliberately no
default recipient: guessing an address is worse than not sending.
"""

import frappe
from frappe.utils import now_datetime

#: Only these reach WhatsApp. Everything else is email, because a phone that
#: buzzes for routine findings stops being read within a week.
URGENT = ("Critical", "High")


def _conf(key, default=None):
    return frappe.conf.get(key, default)


def _record(subject, body, channel, recipient, agent_run=None):
    return frappe.get_doc({
        "doctype": "Growth Alert", "subject": subject[:180], "body": body,
        "channel": channel, "recipient": recipient, "status": "Queued",
        "agent_run": agent_run,
    }).insert(ignore_permissions=True)


def _mark(doc, ok, error=None):
    doc.db_set({"status": "Sent" if ok else "Failed",
                "sent_at": now_datetime() if ok else None,
                "error": (error or "")[:500]})
    frappe.db.commit()


def send_email(subject, body, agent_run=None):
    to = _conf("growth_alert_email")
    if not to:
        return None
    doc = _record(subject, body, "Email", to, agent_run)
    try:
        frappe.sendmail(recipients=[to], subject=subject, message=body, now=True)
        _mark(doc, True)
    except Exception:
        _mark(doc, False, frappe.get_traceback())
    return doc.name


def send_whatsapp(subject, body, agent_run=None):
    """Posts to whatever webhook is configured — n8n handles the provider."""
    url = _conf("growth_alert_whatsapp_webhook")
    to = _conf("growth_alert_whatsapp_to")
    if not (url and to):
        return None
    doc = _record(subject, body, "WhatsApp", to, agent_run)
    try:
        import requests

        r = requests.post(url, json={"to": to, "subject": subject, "body": body}, timeout=20)
        r.raise_for_status()
        _mark(doc, True)
    except Exception:
        _mark(doc, False, frappe.get_traceback())
    return doc.name


def send_finding(agent_run, task, finding):
    """Route one agent finding. Email always; WhatsApp only when urgent."""
    subject = f"[Growth] {task} — {frappe.utils.nowdate()}"
    send_email(subject, finding.replace("\n", "<br>"), agent_run)

    sev = frappe.db.get_value("Growth Finding", {"agent_run": agent_run}, "severity")
    if sev in URGENT:
        # Truncated on purpose. WhatsApp is the signal that something needs
        # attention; the detail lives in the portal and the email.
        send_whatsapp(subject, finding[:900], agent_run)


def send_sync_failure(source, detail):
    send_email(
        f"[Growth] {source} failed to sync",
        f"<b>{source}</b> returned zero rows or raised.<br><br><pre>{frappe.utils.escape_html(str(detail))[:2000]}</pre>"
        "<br>Verdicts built on this source are not trustworthy until it is back.",
    )
