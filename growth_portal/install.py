"""Install and migrate hooks.

Creates the two roles and backfills enough history for the engine to have a
baseline. Without a backfill the first run has nothing to compare against and
issues Watch on everything — which reads as "the portal found nothing".
"""

import frappe

ROLES = ["Growth Portal Admin", "Growth Portal Analyst"]


def after_install():
    _roles()
    frappe.db.commit()


def after_migrate():
    _roles()
    frappe.db.commit()


def _roles():
    for r in ROLES:
        if not frappe.db.exists("Role", r):
            frappe.get_doc({"doctype": "Role", "role_name": r,
                            "desk_access": 1}).insert(ignore_permissions=True)


@frappe.whitelist()
def backfill(days=90):
    """Pull history once, then judge. Run manually after install.

    A source that is not configured yet must not abort the whole backfill.
    On a fresh install only ERPNext has credentials, and the first run has to
    survive that — an install that dies on the first unconfigured platform
    leaves the portal with no baseline at all, which is the one state where it
    reports nothing and looks broken.
    """
    from growth_portal import tasks

    out = {"sources": {}, "skipped": {}}
    for key in tasks.SOURCES:
        try:
            out["sources"][key] = tasks.sync_source(key, days=int(days))
        except Exception as e:
            # Recorded, not swallowed: Source Sync already has the failure row,
            # and the Connections screen will show this source as down.
            out["skipped"][key] = str(e)[:300]
            frappe.log_error(frappe.get_traceback(), f"Growth Portal: backfill {key}")

    try:
        out["ratios"] = tasks.control_ratios()
    except Exception as e:
        out["ratios"] = f"failed: {str(e)[:200]}"

    try:
        out["verdicts"] = tasks.judge_all()
    except Exception as e:
        out["verdicts"] = f"failed: {str(e)[:200]}"

    frappe.db.commit()
    return out
