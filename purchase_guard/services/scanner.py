import frappe
from frappe.utils import add_days, today, getdate

from purchase_guard.purchase_guard.services.rules import (
    price_variance_pct,
    quantity_variance_pct,
    is_maverick_purchase,
    high_value,
)
from purchase_guard.purchase_guard.services.scoring import weighted_score, severity_from_score

def get_settings():
    return frappe.get_single("Purchase Guard Settings")

def run_scheduled_scan():
    if not frappe.db.exists("Purchase Guard Settings"):
        return
    settings = get_settings()
    if not settings.automatic_scans:
        return
    scan_all_companies()

@frappe.whitelist()
def scan_all_companies(company=None, days=None):
    settings = get_settings()
    days = int(days or settings.scan_days or 365)
    companies = [company] if company else frappe.get_all("Company", pluck="name")
    results = {"companies": companies, "invoices": 0, "alerts": 0, "suppliers": 0}
    for comp in companies:
        data = scan_company(comp, days)
        results["invoices"] += data["invoices"]
        results["alerts"] += data["alerts"]
        results["suppliers"] += data["suppliers"]
    return results

def scan_company(company, days=365):
    settings = get_settings()
    from_date = add_days(today(), -int(days))
    invoices = frappe.get_all(
        "Purchase Invoice",
        filters={"company": company, "docstatus": 1, "posting_date": [">=", from_date]},
        fields=["name", "supplier", "bill_no", "posting_date", "grand_total", "currency", "base_grand_total", "is_return"],
        order_by="posting_date desc",
        limit_page_length=5000,
    )
    alert_count = 0
    suppliers = set()
    for row in invoices:
        suppliers.add(row.supplier)
        alert_count += analyze_purchase_invoice(row.name, settings)
    for supplier in suppliers:
        try:
            update_supplier_risk(supplier, company, from_date)
            build_supplier_price_benchmarks(supplier, company, from_date)
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Purchase Guard Supplier Intelligence")
    detect_po_splitting(company, from_date, settings)
    return {"invoices": len(invoices), "alerts": alert_count, "suppliers": len(suppliers)}

def analyze_purchase_invoice(invoice_name, settings=None):
    settings = settings or get_settings()
    inv = frappe.get_doc("Purchase Invoice", invoice_name)
    findings = []

    if settings.duplicate_invoice_check and inv.bill_no:
        duplicates = frappe.db.count(
            "Purchase Invoice",
            {
                "supplier": inv.supplier,
                "bill_no": inv.bill_no,
                "docstatus": 1,
                "name": ["!=", inv.name],
            },
        )
        if duplicates:
            findings.append({
                "type": "Duplicate Invoice",
                "score": 90,
                "title": f"Duplicate supplier invoice number: {inv.bill_no}",
                "evidence": f"{duplicates} other submitted invoice(s) use the same supplier and bill number.",
                "recommended_action": "Hold payment and verify the supplier invoice before proceeding.",
            })

    if settings.maverick_purchase_check:
        for item in inv.items:
            if not item.purchase_order:
                findings.append({
                    "type": "Maverick Purchase",
                    "score": 45,
                    "title": f"Invoice item without Purchase Order: {item.item_code}",
                    "evidence": f"{item.item_code} has no linked Purchase Order on {inv.name}.",
                    "recommended_action": "Verify approval and commercial terms before payment.",
                })
                break

    for item in inv.items:
        if item.purchase_order and item.purchase_order_item:
            po_rate = frappe.db.get_value(
                "Purchase Order Item", item.purchase_order_item, "rate"
            )
            variance = price_variance_pct(item.rate, po_rate)
            if variance is not None and variance >= float(settings.price_variance_warning_pct):
                score = 85 if variance >= float(settings.price_variance_critical_pct) else 55
                findings.append({
                    "type": "PO Price Variance",
                    "score": score,
                    "title": f"Purchase price {float(variance):.2f}% above PO",
                    "evidence": f"Item {item.item_code}: invoice rate {item.rate}, PO rate {po_rate}.",
                    "recommended_action": "Verify the supplier price and approved change before payment.",
                    "item_code": item.item_code,
                    "amount": abs((item.rate or 0) - (po_rate or 0)) * (item.qty or 0),
                })

        if item.purchase_receipt and item.purchase_receipt_item:
            received_qty = frappe.db.get_value(
                "Purchase Receipt Item", item.purchase_receipt_item, "qty"
            )
            variance = quantity_variance_pct(item.qty, received_qty)
            if variance is not None and variance >= float(settings.quantity_variance_warning_pct):
                findings.append({
                    "type": "Receipt Quantity Variance",
                    "score": 60,
                    "title": f"Invoice quantity differs from receipt by {float(variance):.2f}%",
                    "evidence": f"Item {item.item_code}: invoice qty {item.qty}, receipt qty {received_qty}.",
                    "recommended_action": "Confirm receipt quantity before releasing payment.",
                    "item_code": item.item_code,
                })

    if high_value(inv.base_grand_total, settings.high_value_purchase_threshold):
        findings.append({
            "type": "High Value Purchase",
            "score": 25,
            "title": "High-value purchase requires review",
            "evidence": f"Base invoice total is {inv.base_grand_total}.",
            "recommended_action": "Confirm approvals, commercial terms and supplier details.",
        })

    for finding in findings:
        create_alert(inv, finding)

    return len(findings)

def create_alert(invoice, finding):
    existing = frappe.db.exists(
        "Purchase Risk Alert",
        {
            "reference_doctype": "Purchase Invoice",
            "reference_name": invoice.name,
            "risk_type": finding["type"],
            "status": ["in", ["Open", "Under Review"]],
        },
    )
    if existing:
        return existing
    if not frappe.get_single("Purchase Guard Settings").auto_create_alerts:
        return None
    doc = frappe.get_doc({
        "doctype": "Purchase Risk Alert",
        "company": invoice.company,
        "supplier": invoice.supplier,
        "reference_doctype": "Purchase Invoice",
        "reference_name": invoice.name,
        "risk_type": finding["type"],
        "severity": severity_from_score(finding["score"]),
        "risk_score": finding["score"],
        "amount": finding.get("amount") or invoice.base_grand_total or invoice.grand_total,
        "item_code": finding.get("item_code"),
        "title": finding["title"],
        "evidence": finding["evidence"],
        "recommended_action": finding["recommended_action"],
        "status": "Open",
    })
    doc.insert(ignore_permissions=True)
    return doc.name

def update_supplier_risk(supplier, company, from_date):
    rows = frappe.db.sql("""
        SELECT
            pii.item_code,
            AVG(pii.rate) AS avg_rate,
            MAX(pii.rate) AS max_rate,
            MIN(pii.rate) AS min_rate,
            SUM(pii.base_amount) AS spend
        FROM `tabPurchase Invoice Item` pii
        INNER JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
        WHERE pi.docstatus = 1
          AND pi.company = %(company)s
          AND pi.supplier = %(supplier)s
          AND pi.posting_date >= %(from_date)s
          AND IFNULL(pi.is_return, 0) = 0
        GROUP BY pii.item_code
    """, {"company": company, "supplier": supplier, "from_date": from_date}, as_dict=True)

    total_spend = sum(float(r.spend or 0) for r in rows)
    high_variance_items = 0
    for r in rows:
        if r.min_rate and float(r.min_rate) > 0 and (float(r.max_rate) / float(r.min_rate) - 1) * 100 >= 15:
            high_variance_items += 1

    score = min(100, 30 + high_variance_items * 5)
    if total_spend > 0:
        score = min(100, score + 10)

    company_spend = frappe.db.sql("""
        SELECT COALESCE(SUM(base_grand_total), 0)
        FROM `tabPurchase Invoice`
        WHERE company=%(company)s AND docstatus=1
          AND posting_date >= %(from_date)s AND IFNULL(is_return,0)=0
    """, {"company": company, "from_date": from_date})[0][0] or 0
    concentration = (float(total_spend) / float(company_spend) * 100) if company_spend else 0
    price_score = max(0, 100 - high_variance_items * 10)
    invoice_accuracy = 100
    delivery_score = 100
    payment_behavior = 100

    existing = frappe.db.exists(
        "Supplier Risk Assessment",
        {"supplier": supplier, "company": company},
    )
    values = {
        "supplier": supplier,
        "company": company,
        "assessment_date": today(),
        "risk_score": score,
        "risk_level": severity_from_score(score),
        "purchase_spend": total_spend,
        "price_variance_items": high_variance_items,
        "price_competitiveness_score": price_score,
        "invoice_accuracy_score": invoice_accuracy,
        "delivery_performance_score": delivery_score,
        "payment_behavior_score": payment_behavior,
        "supplier_concentration_pct": concentration,
        "notes": f"Calculated from submitted Purchase Invoices from {from_date} to {today()}.",
    }
    if existing:
        doc = frappe.get_doc("Supplier Risk Assessment", existing)
        doc.update(values)
        doc.save(ignore_permissions=True)
    else:
        frappe.get_doc({"doctype": "Supplier Risk Assessment", **values}).insert(ignore_permissions=True)


def detect_po_splitting(company, from_date, settings):
    """Find clusters of POs to the same supplier that may be split around the approval threshold."""
    threshold = float(settings.high_value_purchase_threshold or 0)
    if threshold <= 0:
        return
    rows = frappe.db.sql("""
        SELECT supplier, transaction_date, SUM(base_grand_total) total_amount,
               COUNT(*) po_count, GROUP_CONCAT(name) po_names
        FROM `tabPurchase Order`
        WHERE company = %(company)s
          AND docstatus = 1
          AND transaction_date >= %(from_date)s
        GROUP BY supplier, transaction_date
        HAVING COUNT(*) >= 2
           AND SUM(base_grand_total) >= %(threshold)s
    """, {
        "company": company,
        "from_date": from_date,
        "threshold": threshold,
    }, as_dict=True)
    for row in rows:
        score = 70 if row.total_amount >= threshold * 2 else 55
        existing = frappe.db.exists("Purchase Risk Alert", {
            "company": company,
            "supplier": row.supplier,
            "risk_type": "PO Split Risk",
            "status": ["in", ["Open", "Under Review"]],
        })
        if existing:
            continue
        frappe.get_doc({
            "doctype": "Purchase Risk Alert",
            "company": company,
            "supplier": row.supplier,
            "reference_doctype": "Purchase Order",
            "reference_name": (row.po_names or "").split(",")[0],
            "risk_type": "PO Split Risk",
            "severity": severity_from_score(score),
            "risk_score": score,
            "amount": row.total_amount,
            "title": f"Multiple POs to supplier on {row.transaction_date}",
            "evidence": f"{row.po_count} submitted POs total {row.total_amount}. References: {row.po_names}.",
            "recommended_action": "Review whether the purchases were intentionally split to bypass approval thresholds.",
            "status": "Open",
        }).insert(ignore_permissions=True)

def build_supplier_price_benchmarks(supplier, company, from_date):
    rows = frappe.db.sql("""
        SELECT pii.item_code,
               AVG(pii.rate) average_rate,
               MIN(pii.rate) minimum_rate,
               MAX(pii.rate) maximum_rate,
               SUM(pii.qty) quantity_purchased,
               SUM(pii.base_amount) total_spend
        FROM `tabPurchase Invoice Item` pii
        INNER JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
        WHERE pi.docstatus = 1
          AND pi.company = %(company)s
          AND pi.supplier = %(supplier)s
          AND pi.posting_date >= %(from_date)s
          AND IFNULL(pi.is_return, 0) = 0
        GROUP BY pii.item_code
    """, {"company": company, "supplier": supplier, "from_date": from_date}, as_dict=True)
    for row in rows:
        if not row.item_code:
            continue
        name = frappe.db.exists("Supplier Price Benchmark", {
            "company": company,
            "supplier": supplier,
            "item_code": row.item_code,
            "period_start": from_date,
            "period_end": today(),
        })
        values = {
            "company": company,
            "supplier": supplier,
            "item_code": row.item_code,
            "period_start": from_date,
            "period_end": today(),
            "average_rate": row.average_rate,
            "minimum_rate": row.minimum_rate,
            "maximum_rate": row.maximum_rate,
            "quantity_purchased": row.quantity_purchased,
            "total_spend": row.total_spend,
        }
        if name:
            doc = frappe.get_doc("Supplier Price Benchmark", name)
            doc.update(values)
            doc.save(ignore_permissions=True)
        else:
            frappe.get_doc({"doctype": "Supplier Price Benchmark", **values}).insert(ignore_permissions=True)
