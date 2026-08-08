"""Exchange rates, with their provenance attached.

Ad accounts report TRY. Orders are MAD. AppsFlyer reports USD. Any figure that
crosses those boundaries needs a rate, and the rest of this app has one rule
about that: **a converted number always travels with the rate that produced
it**, so a reader can check the arithmetic instead of trusting it.

This module exists because the rate used to be a constant in `site_config.json`.
That is wrong in a specific way rather than a general one: the lira has been
losing value fast enough that a hand-entered rate is materially wrong within
weeks, and nothing about a stale constant looks stale. The dashboard would keep
printing a confident MAD figure long after it stopped being true.

Two decisions shape the code:

**Reads never touch the network.** `rate()` only looks at the cache and the
config. The fetch happens in the hourly job, where a slow or dead provider costs
a log line instead of a hanging dashboard. A cold cache falls back to the
configured value rather than blocking.

**A stale rate is returned, and labelled stale.** When the provider is down for
a day the honest answer is the old number plus its age — not `None`, which would
blank the MAD column and tell the reader nothing, and not a silent old number,
which would tell them something false.

Precedence is live cache → configured constant → nothing. The constant is the
floor, not the default: an operator who pins `try_to_mad_rate` is providing the
value used when the network cannot be reached, not overriding the live one.
"""

from __future__ import annotations

import time

import frappe
import requests

#: exchangerate-api's open endpoint: no key, no registration, one call per base
#: currency. Chosen over the keyed providers because a credential that only this
#: one function needs is a credential that will rot unnoticed.
PROVIDER = "https://open.er-api.com/v6/latest/{base}"

CACHE_KEY = "growth_portal:fx"

#: Kept far longer than the refresh interval on purpose. The TTL is not how
#: fresh the rate is — `age_hours` is — it is how long a value survives the
#: provider being unreachable before the app has nothing left to fall back to.
CACHE_TTL_SEC = 7 * 24 * 3600

#: Past this the rate is still returned, still used, and marked stale so the
#: interface can say so. Two days is roughly where lira drift stops being
#: rounding and starts being a wrong answer.
STALE_AFTER_HOURS = 48

#: base -> the quotes this app actually needs from it.
WANTED = {"TRY": ("MAD",), "USD": ("TRY",)}

#: Config key holding the fallback for each pair.
CONFIG_KEY = {("TRY", "MAD"): "try_to_mad_rate", ("USD", "TRY"): "usd_to_try_rate"}


def _cache():
    return frappe.cache().get_value(CACHE_KEY) or {}


def refresh():
    """Fetch every pair this app needs. Called hourly; safe to call by hand.

    Returns what it wrote so an operator running it from `bench execute` can see
    the rates rather than a bare success.
    """
    rates, errors = {}, []
    for base, quotes in WANTED.items():
        try:
            r = requests.get(PROVIDER.format(base=base), timeout=8)
            r.raise_for_status()
            body = r.json()
            if body.get("result") != "success":
                raise ValueError(f"provider returned result={body.get('result')!r}")
            table = body.get("rates") or {}
            for q in quotes:
                if q not in table:
                    raise ValueError(f"{base}->{q} missing from provider response")
                rates[f"{base}_{q}"] = float(table[q])
        except Exception as e:
            # One base failing must not discard the other. A partial refresh is
            # merged over the previous cache below rather than replacing it.
            errors.append(f"{base}: {e}")

    if not rates:
        frappe.log_error("\n".join(errors), "Growth Portal: FX refresh failed")
        return {"ok": False, "errors": errors}

    merged = dict(_cache().get("rates") or {})
    merged.update(rates)
    frappe.cache().set_value(
        CACHE_KEY,
        {"rates": merged, "fetched_at": time.time(), "provider": "open.er-api.com"},
        expires_in_sec=CACHE_TTL_SEC,
    )
    if errors:
        frappe.log_error("\n".join(errors), "Growth Portal: FX refresh partial")
    return {"ok": True, "rates": merged, "errors": errors}


def rate(base: str, quote: str) -> dict:
    """The rate for one pair, with where it came from and how old it is.

    Never raises and never returns a bare float — the caller is expected to ship
    `source` and `age_hours` alongside any figure it converts, which is only
    possible if they arrive together.
    """
    pair = f"{base}_{quote}"
    cached = _cache()
    value = (cached.get("rates") or {}).get(pair)

    if value:
        age_h = (time.time() - float(cached.get("fetched_at") or 0)) / 3600.0
        return {
            "value": round(float(value), 6),
            "source": "live",
            "provider": cached.get("provider"),
            "age_hours": round(age_h, 1),
            "stale": age_h > STALE_AFTER_HOURS,
        }

    fallback = frappe.conf.get(CONFIG_KEY.get((base, quote), ""))
    if fallback:
        return {
            "value": float(fallback),
            "source": "config",
            "provider": None,
            "age_hours": None,
            # A pinned constant has no age, so it cannot be shown as fresh.
            # Treating it as stale is the honest default: nothing here knows
            # when a human last looked at it.
            "stale": True,
        }

    return {"value": None, "source": None, "provider": None,
            "age_hours": None, "stale": False}
