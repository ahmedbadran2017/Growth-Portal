"""The framing rules — enforced in code, not in a prompt.

Every rule here was written from a specific wrong conclusion reached while
analysing this business by hand. The data was correct each time; the frame
around it was not. A prompt can be ignored; a raised exception cannot.

Import this from every analyzer. Nothing writes a verdict without passing it.
"""

from datetime import date, timedelta

import frappe
from frappe import _


class FramingError(frappe.ValidationError):
    """A measurement was framed in a way that has produced a wrong answer before."""


# Sources whose "today" is not the same instant. Every comparison across two of
# these has to be aligned first — a two-hour offset silently shifted a whole
# day's orders into the wrong bucket once and nobody noticed for a week.
SOURCE_TZ = {
    "erpnext": "Europe/Istanbul",       # NOT Africa/Casablanca — verified against the DB clock
    "meta_insights": "Europe/Istanbul",
    "meta_morocco": "Africa/Casablanca",  # this one account differs
    "meta_dataset": "America/Los_Angeles",  # dataset_stats reports in Pacific
    "google_ads": "Europe/Istanbul",
    "tiktok": "Europe/Istanbul",
    "shopify": "UTC",
    "appsflyer": "Africa/Casablanca",
}

# How long a source's numbers keep moving after the day closes. Judging inside
# this window is judging an unfinished number.
MATURITY_HOURS = {
    "erpnext": 6,          # backfill
    "meta_insights": 24,
    "google_ads": 72,      # PMAX conversion value lags hardest
    "tiktok": 48,          # measured: a closed day moved 2 -> 5 payments overnight
    "appsflyer": 48,
    "shopify": 6,
    "clarity": 24,
    "semrush": 168,        # weekly crawl
}


def assert_same_source(numerator_source, denominator_source):
    """A ratio needs both sides from one system.

    Platform conversions over total ERPNext orders is the error that costs the
    most: the platform only ever claims the orders it drove, so the ratio
    measures market share, not performance — and reads as catastrophe.
    """
    if numerator_source != denominator_source:
        raise FramingError(
            _("Cross-source ratio: {0} ÷ {1}. Use a denominator from the same system.")
            .format(numerator_source, denominator_source)
        )


def site_today():
    """Today on the SITE's clock, never the database's.

    Verified on this bench: MySQL `NOW()` returns UTC — it equals
    `UTC_TIMESTAMP()` — while Frappe writes `creation` in the site timezone,
    Europe/Istanbul. Three hours apart. So `WHERE DATE(creation) = CURDATE()`
    silently files every order placed between 00:00 and 03:00 local under the
    previous day, and `_maturity` reads those rows as a day older than they are
    — which is the direction that lets an unfinished day be judged.

    Frappe's own clock is the single authority here: it follows System Settings
    and handles DST, which a hard-coded offset would not.
    """
    return frappe.utils.getdate(frappe.utils.nowdate())


def site_now():
    """Now on the site's clock. See `site_today`."""
    return frappe.utils.now_datetime()


def clock():
    """Bind the site's clock into a query's parameters.

    Merge into every params dict whose SQL references %(gp_today)s or
    %(gp_now)s: `frappe.db.sql(q, {**guard.clock(), "d": days})`.
    """
    return {"gp_today": site_today(), "gp_now": site_now()}


def assert_mature(source, window_end, now=None):
    """Refuse to judge a window whose numbers are still moving."""
    now = now or site_now()
    hours = MATURITY_HOURS.get(source, 24)
    closed_at = frappe.utils.get_datetime(f"{window_end} 23:59:59")
    if (now - closed_at).total_seconds() < hours * 3600:
        raise FramingError(
            _("{0} data for {1} is still maturing ({2}h). Judging now reads an unfinished number.")
            .format(source, window_end, hours)
        )


def assert_sample(n, minimum, label="sample"):
    if n is None or n < minimum:
        raise FramingError(
            _("{0} is {1}, below the declared minimum of {2}.").format(label, n, minimum)
        )


def assert_window(window_start, window_end, min_days):
    """One anomalous day is not a pattern.

    A single outlier day was once taken as proof a channel had collapsed; ten
    days of the same channel showed the opposite.
    """
    span = (frappe.utils.getdate(window_end) - frappe.utils.getdate(window_start)).days + 1
    if span < min_days:
        raise FramingError(
            _("Window is {0} day(s); this rule needs at least {1}.").format(span, min_days)
        )


def assert_evidence(payload):
    """No verdict without a re-checkable trail."""
    for field in ("numerator", "denominator", "denominator_source", "window_start", "window_end", "query_ref"):
        if payload.get(field) in (None, ""):
            raise FramingError(_("Verdict is missing mandatory evidence field: {0}").format(field))


def assert_pulled_performance(entity_key, seen_keys):
    """Never propose stopping something whose numbers were not read.

    An entity that looks dormant in one report can be the best performer in
    another. This came within one approval of pausing the highest-ROAS campaign
    in an account because it looked idle in the wrong view.
    """
    if entity_key not in seen_keys:
        raise FramingError(
            _("Refusing to judge {0}: its performance was never pulled in this run.").format(entity_key)
        )


def raw_events_are_not_duplicates(note=""):
    """Marker for a mistake worth not repeating.

    Raw ingestion counts show browser and server events separately; the platform
    de-duplicates at the attribution layer. A raw ratio above 1 is normal, not a
    duplication bug. Measure de-duplication from the attribution side.
    """
    return f"raw-ingestion counts are pre-dedup; not a duplication signal. {note}".strip()


def closed_day(source, today=None):
    """The most recent day this source can be judged on."""
    today = today or date.today()
    return today - timedelta(days=1 + (MATURITY_HOURS.get(source, 24) // 24))
