"""
Purchase Guard public API.

All public API endpoints are exposed from this package so that
both frontend calls and existing integrations using
purchase_guard.api.<method> continue to work.
"""

import frappe
from frappe.utils import add_days, today

from purchase_guard.services.scanner import (
    scan_all_companies,
    analyze_purchase_invoice,
)


@frappe.whitelist()
def scan_invoice(invoice):
    """Analyze a Purchase Invoice and create/update Purchase Guard alerts."""
    return analyze_purchase_invoice(invoice)


@frappe.whitelist()
def get_dashboard_data(company=None, days=365):
    """Return Purchase Guard dashboard summary data."""

    filters = {}

    if company:
        filters["company"] = company

    open_filters = {
        **filters,
        "status": "Open",
    }

    critical_filters = {
        **open_filters,
        "severity": "Critical",
    }

    high_filters = {
        **open_filters,
        "severity": "High",
    }

    medium_filters = {
        **open_filters,
        "severity": "Medium",
    }

    low_filters = {
        **open_filters,
        "severity": "Low",
    }

    return {
        "success": True,
        "summary": {
            "total_alerts": frappe.db.count(
                "Purchase Risk Alert",
                filters=filters,
            ),
            "open_alerts": frappe.db.count(
                "Purchase Risk Alert",
                filters=open_filters,
            ),
            "critical_alerts": frappe.db.count(
                "Purchase Risk Alert",
                filters=critical_filters,
            ),
            "high_alerts": frappe.db.count(
                "Purchase Risk Alert",
                filters=high_filters,
            ),
            "medium_alerts": frappe.db.count(
                "Purchase Risk Alert",
                filters=medium_filters,
            ),
            "low_alerts": frappe.db.count(
                "Purchase Risk Alert",
                filters=low_filters,
            ),
        },
    }


@frappe.whitelist()
def get_supplier_guard(supplier=None, company=None, days=365):
    """Return supplier risk information."""

    filters = {}

    if supplier:
        filters["supplier"] = supplier

    if company:
        filters["company"] = company

    if not filters:
        return []

    return frappe.get_all(
        "Supplier Risk Assessment",
        filters=filters,
        fields="*",
        order_by="creation desc",
    )


@frappe.whitelist()
def get_price_intelligence(
    item_code=None,
    supplier=None,
    company=None,
    days=365,
):
    """Return supplier price benchmark information."""

    filters = {}

    if item_code:
        filters["item_code"] = item_code

    if supplier:
        filters["supplier"] = supplier

    if company:
        filters["company"] = company

    return frappe.get_all(
        "Supplier Price Benchmark",
        filters=filters,
        fields="*",
        order_by="creation desc",
    )


@frappe.whitelist()
def get_invoice_guard(invoice):
    """Return Purchase Guard alerts for a Purchase Invoice."""

    return frappe.get_all(
        "Purchase Risk Alert",
        filters={
            "reference_doctype": "Purchase Invoice",
            "reference_name": invoice,
        },
        fields=[
            "name",
            "severity",
            "status",
            "risk_score",
            "risk_type",
            "title",
            "evidence",
            "recommended_action",
            "reference_doctype",
            "reference_name",
            "creation",
        ],
        order_by="creation desc",
    )


@frappe.whitelist()
def run_scan(company=None):
    """Run Purchase Guard purchase-risk scan."""

    return scan_all_companies(company=company)
