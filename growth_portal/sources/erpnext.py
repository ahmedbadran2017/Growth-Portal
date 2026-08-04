"""ERPNext adapter — the only source that reports what actually happened.

Every other system reports what happened *inside itself*: an ad platform knows
the orders it believes it drove, a site analytics tool knows sessions. ERPNext
knows which orders were delivered, refused, or never reached the customer, and
what each one cost. When two systems disagree, this one wins.

The delivery outcome is the load-bearing part. In a COD business a placed order
is a claim, not revenue: about a quarter of them never complete, and the rate
swings more than twenty points between products. Platform ROAS is therefore
overstated by the delivery gap — by a different amount for every product.
"""


from __future__ import annotations
from datetime import date

import frappe

from growth_portal.engine import guard

from growth_portal.sources.base import ChangeRow, EntityRow, MetricRow, SourceAdapter

# `tabShipment Tracking` is a status *history* — roughly 3.6 rows per order — so
# every read reduces to the latest row per order before anything is counted.
# Counting the raw table inflates every failure category several-fold.
TRACKING = "tabShipment Tracking"

# Courier status -> (outcome, who can fix it). Matched longest-prefix-first so
# "Annulé Sur Place : Taille" resolves to Product before the bare
# "Annulé Sur Place" fallback claims it.
#
# The owner column is the useful one: an order lost to a wrong size is a product
# page problem, one lost to an unreachable customer is a lead quality problem,
# and they need different people. Without it every failure looks like "returns".
STATUS_MAP = {
    "Livré confirmé": ("Delivered", None),
    "Livré": ("Delivered", None),

    "Annulé Sur Place : Article Diff": ("Refused", "Product"),
    "Annulé Sur Place : Taille": ("Refused", "Product"),
    "Annulé Sur Place : Couleur": ("Refused", "Product"),
    "Annulé Sur Place : Prix Différent": ("Refused", "Product"),
    "Annulé Sur Place : Ouverture Colis": ("Refused", "Product"),
    "Annulé sur place : Échantillon Nn conforme": ("Refused", "Product"),
    "Annulé Sur Place": ("Refused", "Confirmation"),

    "Annulé Au Téléphone": ("Cancelled", "Confirmation"),
    "Annulé par le client": ("Cancelled", "Customer"),
    "Annulé par destinataire": ("Cancelled", "Customer"),

    "Client Injoignable": ("Unreachable", "Lead Quality"),
    "Injoignable": ("Unreachable", "Lead Quality"),
    "Récupération injoignable": ("Unreachable", "Lead Quality"),
    "Client En Voyage": ("Unreachable", "Customer"),

    # The order was never real. Worth separating: a duplicate submission is a
    # site bug, and a denied order is a checkout or lead-quality problem.
    "Aucune commande passée": ("Cancelled", "Duplicate"),
    "Commande En Double": ("Cancelled", "Duplicate"),

    "Destination Erronée": ("Cancelled", "Logistics"),
    "Déstination non Couverte": ("Cancelled", "Logistics"),
    "Numéro Erroné": ("Cancelled", "Logistics"),
    "Colis Endommagé": ("Cancelled", "Logistics"),

    "Demande retour client": ("Returned", "Customer"),
    "Récupéré": ("Returned", "Customer"),
}

# Still moving. Excluded from every rate — a product judged while half its
# orders are mid-transit reads as failing when it is merely recent.
IN_TRANSIT = (
    "Hub CATHEDIS", "HUB CATHEDIS", "En Attente Ramassage", "Mise En Distribution",
    "Confirmée Sous RDV", "Expédié vers hub destination", "Déposé au hub destinataire",
)

TERMINAL = {"Delivered", "Cancelled", "Unreachable", "Refused", "Returned"}


def classify(status):
    """(outcome, owner, is_terminal) for a raw courier status.

    An unrecognised status resolves to non-terminal, never to Delivered. The
    courier adds statuses without telling anyone; counting an unknown one as a
    failure invents a problem, counting it as a success hides one. Excluding it
    does neither — and the unmapped list is worth reading.
    """
    if not status:
        return "In Transit", None, False
    s = status.strip()
    if any(s.startswith(p) for p in IN_TRANSIT):
        return "In Transit", None, False
    for key in sorted(STATUS_MAP, key=len, reverse=True):
        if s.startswith(key):
            outcome, owner = STATUS_MAP[key]
            return outcome, owner, outcome in TERMINAL
    return "Other", "Unknown", False


class ERPNextSource(SourceAdapter):
    name = "erpnext"
    timezone = "Europe/Istanbul"   # verified against the DB clock, not assumed
    maturity_hours = 6

    def entities(self):
        rows = frappe.db.sql(
            """
            SELECT soi.item_code AS `key`,
                   SUBSTRING_INDEX(GROUP_CONCAT(soi.item_name ORDER BY soi.creation DESC), ',', 1) AS label
            FROM `tabSales Order Item` soi
            WHERE soi.creation >= DATE_SUB(%(gp_today)s, INTERVAL 120 DAY)
            GROUP BY soi.item_code
            """,
            guard.clock(), as_dict=True,
        )
        # Keyed on item_code, labelled with the *latest* name. The name on a
        # Sales Order Item is a snapshot taken at order time, and this catalogue
        # renamed products mid-life (Turkish -> French), which splits one
        # product into two ghosts with different volumes and different prices.
        return [EntityRow(entity_type="Product", key=r.key, label=r.label) for r in rows]

    def metrics(self, date_from: date, date_to: date):
        rows = frappe.db.sql(
            f"""
            SELECT soi.item_code, DATE(so.creation) AS day, t.status_name, t.amt, soi.rate
            FROM (
                SELECT sales_order, delivery_status_name AS status_name, custom_amount AS amt,
                       ROW_NUMBER() OVER (PARTITION BY sales_order
                                          ORDER BY creation DESC, modified DESC) rn
                FROM `{TRACKING}`
                WHERE sales_order IS NOT NULL
                  AND creation >= %(f)s AND creation < %(t)s
            ) t
            JOIN `tabSales Order` so       ON so.name = t.sales_order
            JOIN `tabSales Order Item` soi ON soi.parent = t.sales_order
            WHERE t.rn = 1
            """,
            {"f": date_from, "t": date_to},
            as_dict=True,
        )

        bucket, unmapped = {}, set()
        for r in rows:
            outcome, owner, terminal = classify(r.status_name)
            if outcome == "Other":
                unmapped.add(r.status_name)
            m = bucket.setdefault(
                (r.item_code, r.day),
                MetricRow(entity_type="Product", key=r.item_code, day=r.day,
                          extra={"resolved": 0, "refused_product": 0, "unreachable": 0,
                                 "cancelled_confirm": 0, "duplicate": 0, "returned": 0,
                                 "lost_amount": 0.0, "unmapped": 0}),
            )
            m.orders += 1
            m.revenue += r.amt or 0
            if not terminal:
                if outcome == "Other":
                    m.extra["unmapped"] += 1
                continue
            m.extra["resolved"] += 1
            if outcome == "Delivered":
                m.delivered += 1
            else:
                m.extra["lost_amount"] += r.amt or 0
                if owner == "Product":
                    m.extra["refused_product"] += 1
                elif outcome == "Unreachable":
                    m.extra["unreachable"] += 1
                elif owner == "Confirmation":
                    m.extra["cancelled_confirm"] += 1
                elif owner == "Duplicate":
                    m.extra["duplicate"] += 1
                elif outcome == "Returned":
                    m.extra["returned"] += 1

        if unmapped:
            frappe.log_error("\n".join(sorted(unmapped)),
                             "Growth Portal: unmapped courier statuses")
        return list(bucket.values())

    def changes(self, date_from: date, date_to: date):
        """Price changes read as deploy-style events on the timeline.

        A product whose sold rate moved is a different product commercially, and
        a delivery-rate shift on the same week is more likely a price objection
        than a courier problem.
        """
        rows = frappe.db.sql(
            """
            SELECT soi.item_code, DATE(soi.creation) AS day, AVG(soi.rate) AS rate
            FROM `tabSales Order Item` soi
            WHERE soi.creation >= %(f)s AND soi.creation < %(t)s
            GROUP BY soi.item_code, DATE(soi.creation)
            ORDER BY soi.item_code, day
            """,
            {"f": date_from, "t": date_to},
            as_dict=True,
        )
        out, last = [], {}
        for r in rows:
            prev = last.get(r.item_code)
            if prev and prev > 0 and abs(r.rate - prev) / prev >= 0.05:
                out.append(ChangeRow(day=r.day, entity_type="Product", key=r.item_code,
                                     actor="pricing", surface="deploy",
                                     field_changed="rate",
                                     before=f"{prev:.0f}", after=f"{r.rate:.0f}"))
            last[r.item_code] = r.rate
        return out

    def health(self):
        # The site's clock, not the database's. `creation` is written in the
        # site timezone and MySQL here runs UTC — the three-hour gap made this
        # probe read a 21-hour window and call it 24.
        n = frappe.db.sql(
            f"SELECT COUNT(*) FROM `{TRACKING}` "
            "WHERE creation >= DATE_SUB(%(gp_now)s, INTERVAL 24 HOUR)",
            guard.clock(),
        )[0][0]
        return {"source": self.name, "ok": n > 0, "tracking_rows_24h": n}
