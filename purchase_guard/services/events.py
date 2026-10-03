import frappe
from purchase_guard.services.scanner import analyze_purchase_invoice

def _run(doc):
    settings = frappe.get_single("Purchase Guard Settings")
    if settings.auto_create_alerts:
        try:
            analyze_purchase_invoice(doc.name, settings)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Purchase Guard scan failed: {doc.name}")

def on_purchase_invoice_submit(doc, method=None):
    _run(doc)

def on_purchase_invoice_cancel(doc, method=None):
    pass

def on_purchase_order_submit(doc, method=None):
    pass

def on_purchase_order_cancel(doc, method=None):
    pass

def on_purchase_receipt_submit(doc, method=None):
    pass

def on_purchase_receipt_cancel(doc, method=None):
    pass

def on_payment_entry_submit(doc, method=None):
    if doc.payment_type != "Pay":
        return
    if not doc.party_type or not doc.party:
        return
    settings = frappe.get_single("Purchase Guard Settings")
    if not settings.auto_create_alerts:
        return
    if doc.paid_amount >= settings.high_value_purchase_threshold:
        existing = frappe.db.exists(
            "Purchase Risk Alert",
            {
                "reference_doctype": "Payment Entry",
                "reference_name": doc.name,
                "risk_type": "High Value Payment",
                "status": ["in", ["Open", "Under Review"]],
            },
        )
        if not existing:
            frappe.get_doc({
                "doctype": "Purchase Risk Alert",
                "company": doc.company,
                "supplier": doc.party if doc.party_type == "Supplier" else None,
                "reference_doctype": "Payment Entry",
                "reference_name": doc.name,
                "risk_type": "High Value Payment",
                "severity": "Medium",
                "risk_score": 25,
                "amount": doc.paid_amount,
                "title": "High-value supplier payment",
                "evidence": f"Payment Entry {doc.name} is for {doc.paid_amount}.",
                "recommended_action": "Confirm supplier, supporting documents and approval before release.",
                "status": "Open",
            }).insert(ignore_permissions=True)
