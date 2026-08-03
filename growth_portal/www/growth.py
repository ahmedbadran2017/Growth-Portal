import frappe

no_cache = 1

#: Verdicts name products, spend and margins. Read access is not open to any
#: signed-in staff member the way a ticket board is.
ALLOWED = {"Growth Portal Admin", "Growth Portal Analyst", "System Manager"}


def get_context(context):
    """Render the SPA shell. Shell globals are pre-computed as plain values so
    the Jinja sandbox never calls a restricted helper."""
    context.no_cache = 1

    if frappe.session.user == "Guest":
        try:
            path = frappe.request.path or "/growth"
            qs = frappe.request.query_string.decode() if frappe.request.query_string else ""
            target = path + ("?" + qs if qs else "")
        except Exception:
            target = "/growth"
        frappe.local.flags.redirect_location = "/login?redirect-to=" + frappe.utils.quote(target)
        raise frappe.Redirect

    user = frappe.session.user
    try:
        roles = list(frappe.get_roles(user))
    except Exception:
        roles = []
    if not (ALLOWED & set(roles)):
        raise frappe.PermissionError

    def safe(fn, default=""):
        try:
            return fn() or default
        except Exception:
            return default

    context.portal_shell = {
        "csrf_token": safe(frappe.sessions.get_csrf_token),
        "site_name": safe(lambda: frappe.local.site),
        "user_id": user,
        "full_name": safe(lambda: frappe.utils.get_fullname(user)),
        "user_roles": roles,
        "time_zone": safe(
            lambda: frappe.db.get_single_value("System Settings", "time_zone")
        ),
    }
