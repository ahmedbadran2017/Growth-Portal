"""Overview KPIs and the two segment leaderboards.

Two rules this file will not break, because breaking either produces a number
that looks authoritative and is wrong:

**Currency is never silently mixed.** Orders are MAD; every ad account is TRY.
Spend is returned as TRY with the figure labelled, plus a converted MAD value
*only* when a rate is configured — and the rate travels with the response so a
reader can check it. There is no default rate.

**Blended is labelled blended.** Total spend ÷ total orders is a real operating
number and it is not attribution. It is returned under a key that says so, so
nobody reads it as "this campaign drove those orders".

Confirmation and delivery are two different funnels measured in two different
systems: confirmation is `custom_sales_status` in ERPNext, delivery is the
courier's last word in Shipment Tracking. They are never multiplied together.
"""

import frappe

from growth_portal.sources.erpnext import TRACKING

#: The call-centre outcome. Verified against July 2026: 7,131 Confirmed out of
#: 8,818 orders. Everything not Confirmed is a confirmation failure of some
#: kind, but the reasons are kept separate — "Did not Answer" is a lead-quality
#: problem and "Duplicated" is a site problem.
CONFIRMED = "Confirmed"


def _rate():
    """TRY→MAD. Returned with every converted figure, never applied silently."""
    return frappe.conf.get("try_to_mad_rate")


@frappe.whitelist()
def kpis(days=30):
    """Today, plus the current month, from ERPNext and the ad platforms."""
    days = int(days)

    today = frappe.db.sql(
        """SELECT COUNT(*) orders, COALESCE(SUM(grand_total),0) revenue,
                  SUM(custom_sales_status=%(c)s) confirmed
           FROM `tabSales Order`
           WHERE DATE(creation) = CURDATE()""",
        {"c": CONFIRMED}, as_dict=True,
    )[0]

    month = frappe.db.sql(
        """SELECT COUNT(*) orders, COALESCE(SUM(grand_total),0) revenue,
                  SUM(custom_sales_status=%(c)s) confirmed
           FROM `tabSales Order`
           WHERE creation >= DATE_FORMAT(CURDATE(), '%%Y-%%m-01')""",
        {"c": CONFIRMED}, as_dict=True,
    )[0]

    # Delivery is the courier's last word per order, not a status on the order.
    # `custom_delivered_at` exists on Sales Order and is empty on every row, so
    # using it would report zero deliveries for the whole month.
    delivery = frappe.db.sql(
        f"""SELECT COUNT(*) resolved,
                   SUM(t.status_name LIKE 'Livr%%') delivered
            FROM (
                SELECT sales_order, delivery_status_name AS status_name,
                       ROW_NUMBER() OVER (PARTITION BY sales_order
                                          ORDER BY creation DESC, modified DESC) rn
                FROM `{TRACKING}`
                WHERE sales_order IS NOT NULL
                  AND creation >= DATE_FORMAT(CURDATE(), '%Y-%m-01')
            ) t
            WHERE t.rn = 1
              AND t.status_name NOT LIKE 'Hub%%'
              AND t.status_name NOT LIKE 'En Attente%%'
              AND t.status_name NOT LIKE 'Mise En Distribution%%'
              AND t.status_name NOT LIKE 'Confirm%%RDV%%'
              AND t.status_name NOT LIKE 'Exp%%di%% vers hub%%'
              AND t.status_name NOT LIKE 'D%%pos%% au hub%%'""",
        as_dict=True,
    )[0]

    spend = frappe.db.sql(
        """SELECT source, COALESCE(SUM(spend),0) spend, COALESCE(SUM(revenue),0) revenue
           FROM `tabEntity Metric`
           WHERE entity_type='Campaign'
             AND day >= DATE_FORMAT(CURDATE(), '%Y-%m-01')
           GROUP BY source""",
        as_dict=True,
    )
    spend_today = frappe.db.sql(
        """SELECT COALESCE(SUM(spend),0) spend FROM `tabEntity Metric`
           WHERE entity_type='Campaign' AND day = CURDATE()""",
    )[0][0]

    try_total = sum(float(s.spend or 0) for s in spend)
    rate = _rate()

    def pct(num, den):
        return round(100.0 * num / den, 1) if den else None

    return {
        "today": {
            "orders": today.orders or 0,
            "revenue_mad": round(float(today.revenue or 0)),
            "confirmed": int(today.confirmed or 0),
            "confirmation_pct": pct(int(today.confirmed or 0), today.orders or 0),
            "ad_spend_try": round(float(spend_today or 0)),
        },
        "month": {
            "orders": month.orders or 0,
            "revenue_mad": round(float(month.revenue or 0)),
            "confirmed": int(month.confirmed or 0),
            "confirmation_pct": pct(int(month.confirmed or 0), month.orders or 0),
            "resolved": delivery.resolved or 0,
            "delivered": int(delivery.delivered or 0),
            # Over RESOLVED orders, never over placed orders. Dividing by placed
            # would count every parcel still in transit as a failure and make
            # the last week of any month look like a collapse.
            "delivery_pct": pct(int(delivery.delivered or 0), delivery.resolved or 0),
            "in_transit": (month.orders or 0) - (delivery.resolved or 0),
        },
        "spend": {
            "by_source": [
                {"source": s.source, "spend_try": round(float(s.spend or 0)),
                 "platform_revenue_try": round(float(s.revenue or 0))}
                for s in spend
            ],
            "total_try": round(try_total),
            # Converted only when a rate exists, and the rate ships with it.
            "total_mad": round(try_total * rate) if rate else None,
            "try_to_mad_rate": rate,
            "sources_reporting": len(spend),
        },
        # Named `blended_` on purpose. This is spend ÷ orders across everything,
        # which is how the business actually runs — and is not attribution.
        "blended": {
            "cost_per_order_try": round(try_total / month.orders, 2) if month.orders else None,
            "cost_per_delivered_try": (
                round(try_total / delivery.delivered, 2)
                if delivery.delivered else None
            ),
            "note": "spend ÷ all orders, across every platform — not attributed",
        },
        "as_of": frappe.utils.now(),
    }


@frappe.whitelist()
def daily(days=30):
    """The series behind the KPIs, for the sparklines."""
    days = int(days)
    orders = frappe.db.sql(
        """SELECT DATE(creation) day, COUNT(*) orders,
                  COALESCE(SUM(grand_total),0) revenue,
                  SUM(custom_sales_status=%(c)s) confirmed
           FROM `tabSales Order`
           WHERE creation >= DATE_SUB(CURDATE(), INTERVAL %(d)s DAY)
           GROUP BY DATE(creation) ORDER BY day""",
        {"c": CONFIRMED, "d": days}, as_dict=True,
    )
    spend = frappe.db.sql(
        """SELECT day, COALESCE(SUM(spend),0) spend FROM `tabEntity Metric`
           WHERE entity_type='Campaign' AND day >= DATE_SUB(CURDATE(), INTERVAL %(d)s DAY)
           GROUP BY day ORDER BY day""",
        {"d": days}, as_dict=True,
    )
    by_day = {str(s.day): float(s.spend or 0) for s in spend}
    return [
        {"day": str(o.day), "orders": o.orders,
         "revenue_mad": round(float(o.revenue or 0)),
         "confirmation_pct": round(100.0 * (o.confirmed or 0) / o.orders, 1) if o.orders else None,
         "ad_spend_try": round(by_day.get(str(o.day), 0))}
        for o in orders
    ]


@frappe.whitelist()
def suppliers(days=30, limit=25):
    """Who sells most, what they sell, and how much of the business they are.

    Supplier comes from `tabItem.default_supplier`, which covers 173,056 of
    173,775 items. The `Item Supplier` child table holds 191 rows across three
    suppliers and is not the source of truth here.
    """
    days, limit = int(days), int(limit)
    rows = frappe.db.sql(
        f"""
        SELECT i.default_supplier AS supplier,
               COUNT(DISTINCT so.name) orders,
               COUNT(DISTINCT soi.item_code) skus,
               SUM(soi.amount) revenue,
               SUM(so.custom_sales_status = %(c)s) confirmed_lines,
               COUNT(*) lines,
               SUM(d.delivered) delivered,
               SUM(d.resolved) resolved
        FROM `tabSales Order Item` soi
        JOIN `tabSales Order` so ON so.name = soi.parent
        JOIN `tabItem` i ON i.name = soi.item_code
        LEFT JOIN (
            SELECT t.sales_order,
                   MAX(t.status_name LIKE 'Livr%%') delivered,
                   1 AS resolved
            FROM (
                SELECT sales_order, delivery_status_name AS status_name,
                       ROW_NUMBER() OVER (PARTITION BY sales_order
                                          ORDER BY creation DESC, modified DESC) rn
                FROM `{TRACKING}` WHERE sales_order IS NOT NULL
            ) t
            WHERE t.rn = 1
              AND t.status_name NOT LIKE 'Hub%%'
              AND t.status_name NOT LIKE 'En Attente%%'
              AND t.status_name NOT LIKE 'Mise En Distribution%%'
            GROUP BY t.sales_order
        ) d ON d.sales_order = so.name
        WHERE so.creation >= DATE_SUB(CURDATE(), INTERVAL %(d)s DAY)
          AND i.default_supplier IS NOT NULL AND i.default_supplier != ''
        GROUP BY i.default_supplier
        ORDER BY revenue DESC
        LIMIT %(l)s
        """,
        {"c": CONFIRMED, "d": days, "l": limit}, as_dict=True,
    )
    total = sum(float(r.revenue or 0) for r in rows) or 1
    out = []
    for r in rows:
        out.append({
            "supplier": r.supplier,
            "orders": r.orders,
            "skus": r.skus,
            "revenue_mad": round(float(r.revenue or 0)),
            "share_pct": round(100.0 * float(r.revenue or 0) / total, 2),
            "confirmation_pct": round(100.0 * (r.confirmed_lines or 0) / r.lines, 1) if r.lines else None,
            "delivery_pct": round(100.0 * (r.delivered or 0) / r.resolved, 1) if r.resolved else None,
            "aov_mad": round(float(r.revenue or 0) / r.orders) if r.orders else None,
        })
    return {"rows": out, "window_days": days, "denominator_source": "erpnext",
            "share_basis": "revenue of the suppliers listed"}


@frappe.whitelist()
def products(days=30, limit=25, supplier=None):
    """Same shape, one level down. Keyed on item_code, never on name."""
    days, limit = int(days), int(limit)
    cond = "AND i.default_supplier = %(s)s" if supplier else ""
    rows = frappe.db.sql(
        f"""
        SELECT soi.item_code,
               SUBSTRING_INDEX(GROUP_CONCAT(soi.item_name ORDER BY soi.creation DESC SEPARATOR '||'), '||', 1) AS label,
               MAX(i.default_supplier) supplier,
               COUNT(DISTINCT so.name) orders,
               SUM(soi.qty) qty,
               SUM(soi.amount) revenue,
               SUM(so.custom_sales_status = %(c)s) confirmed_lines,
               COUNT(*) lines
        FROM `tabSales Order Item` soi
        JOIN `tabSales Order` so ON so.name = soi.parent
        JOIN `tabItem` i ON i.name = soi.item_code
        WHERE so.creation >= DATE_SUB(CURDATE(), INTERVAL %(d)s DAY) {cond}
        GROUP BY soi.item_code
        ORDER BY revenue DESC
        LIMIT %(l)s
        """,
        {"c": CONFIRMED, "d": days, "l": limit, "s": supplier}, as_dict=True,
    )
    total = sum(float(r.revenue or 0) for r in rows) or 1
    return {
        "rows": [{
            "item_code": r.item_code,
            # The latest name. A Sales Order Item's name is a snapshot from
            # order time, and this catalogue renamed products Turkish→French
            # mid-life, which splits one product into two ghosts.
            "label": r.label or r.item_code,
            "supplier": r.supplier,
            "orders": r.orders,
            "qty": float(r.qty or 0),
            "revenue_mad": round(float(r.revenue or 0)),
            "share_pct": round(100.0 * float(r.revenue or 0) / total, 2),
            "confirmation_pct": round(100.0 * (r.confirmed_lines or 0) / r.lines, 1) if r.lines else None,
        } for r in rows],
        "window_days": days,
        "supplier": supplier,
        "denominator_source": "erpnext",
    }
