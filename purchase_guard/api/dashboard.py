import frappe


@frappe.whitelist()
def get_dashboard_data():
    company = frappe.form_dict.get("company")

    filters = {}

    if company:
        filters["company"] = company

    open_filters = {
        **filters,
        "status": "Open",
    }

    critical_filters = {
        **filters,
        "status": "Open",
        "severity": "Critical",
    }

    high_filters = {
        **filters,
        "status": "Open",
        "severity": "High",
    }

    medium_filters = {
        **filters,
        "status": "Open",
        "severity": "Medium",
    }

    low_filters = {
        **filters,
        "status": "Open",
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
