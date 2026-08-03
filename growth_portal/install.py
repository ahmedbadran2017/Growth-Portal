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
    """Pull history once, then judge. Run manually after install."""
    from growth_portal import tasks

    out = {}
    for key in tasks.SOURCES:
        out[key] = tasks.sync_source(key, days=int(days))
    out["ratios"] = tasks.control_ratios()
    out["verdicts"] = tasks.judge_all()
    return out
