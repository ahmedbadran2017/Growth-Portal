app_name = "growth_portal"
app_title = "Growth Portal"
app_publisher = "Justyol"
app_description = "Performance and growth intelligence for a COD business — one source of truth, verdicts with evidence, and an analyst on top."
app_email = "ahmedbadran2017@gmail.com"
app_license = "MIT"

required_apps = ["frappe"]

after_install = "growth_portal.install.after_install"
after_migrate = "growth_portal.install.after_migrate"

# The SPA is served from one route; everything under it is client-side.
website_route_rules = [
    {"from_route": "/growth/<path:app_path>", "to_route": "growth"},
    {"from_route": "/growth", "to_route": "growth"},
]

# Sync runs hourly because the numbers keep moving after a day closes.
# Judging and the agent run once, after the day is mature enough to judge —
# a verdict written at 08:00 is a verdict on an unfinished day.
scheduler_events = {
    "cron": {
        "0 * * * *": ["growth_portal.tasks.hourly"],
        "0 9 * * *": ["growth_portal.tasks.daily"],
    },
}

fixtures = [
    {"dt": "Role", "filters": [["role_name", "in", ["Growth Portal Admin", "Growth Portal Analyst"]]]},
]
