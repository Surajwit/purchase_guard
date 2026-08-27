import frappe
from frappe.utils import add_days, today
from purchase_guard.purchase_guard.services.scanner import scan_all_companies, analyze_purchase_invoice

@frappe.whitelist()
def run_scan(company=None, days=None):
    frappe.only_for(["Purchase Guard Manager", "System Manager"])
    return scan_all_companies(company=company, days=days)

@frappe.whitelist()
def scan_invoice(invoice):
    frappe.only_for(["Purchase Guard Analyst", "Purchase Guard Manager", "Accounts User", "System Manager"])
    return analyze_purchase_invoice(invoice)


def _date_from(days=365):
    return add_days(today(), -int(days or 365))


@frappe.whitelist()
def get_dashboard_data(company=None, days=365):
    frappe.only_for(["Purchase Guard Analyst", "Purchase Guard Manager", "System Manager"])
    from_date = _date_from(days)
    company = company or frappe.defaults.get_user_default("Company")
    company_filter = "AND pi.company=%(company)s" if company else ""
    params = {"from_date": from_date, "company": company}

    spend = frappe.db.sql(f"""
        SELECT COALESCE(SUM(pi.base_grand_total),0)
        FROM `tabPurchase Invoice` pi
        WHERE pi.docstatus=1 AND IFNULL(pi.is_return,0)=0
          AND pi.posting_date >= %(from_date)s {company_filter}
    """, params)[0][0] or 0
    if not spend:
        benchmark_company_filter = "AND company=%(company)s" if company else ""
        spend = frappe.db.sql(f"SELECT COALESCE(SUM(total_spend),0) FROM `tabSupplier Price Benchmark` WHERE period_start >= %(from_date)s {benchmark_company_filter}", params)[0][0] or 0

    open_alerts = frappe.db.count("Purchase Risk Alert", {"status": ["in", ["Open", "Under Review"]], **({"company": company} if company else {})})
    high_filters = {"status": ["in", ["Open", "Under Review"]], "risk_score": [">=", 50]}
    if company: high_filters["company"] = company
    high_rows = frappe.get_all("Purchase Risk Alert", filters=high_filters, fields=["risk_score", "amount"], limit_page_length=5000)
    high_risk_amount = sum(float(x.amount or 0) for x in high_rows)

    alert_filters = {"status": ["in", ["Open", "Under Review"]]}
    if company: alert_filters["company"] = company
    alerts = frappe.get_all("Purchase Risk Alert", filters=alert_filters,
        fields=["name","supplier","reference_doctype","reference_name","risk_type","severity","risk_score","amount","title","status"],
        order_by="risk_score desc, modified desc", limit_page_length=8)

    anomalies = _price_anomalies(company, from_date, 8)
    suppliers = frappe.get_all("Supplier Risk Assessment", filters={"company": company} if company else {},
        fields=["supplier","risk_score","risk_level","purchase_spend","price_competitiveness_score","supplier_concentration_pct"],
        order_by="risk_score desc", limit_page_length=6)

    mix = frappe.db.sql("""
        SELECT severity label, COUNT(*) count
        FROM `tabPurchase Risk Alert`
        WHERE status IN ('Open','Under Review')
        {company_filter}
        GROUP BY severity ORDER BY count DESC
    """.format(company_filter="AND company=%(company)s" if company else ""), {"company": company}, as_dict=True)

    savings_risk = sum(max(0, float(x.get("amount") or 0)) for x in anomalies)
    return {
        "company": company, "from_date": from_date, "total_spend": spend,
        "open_alerts": open_alerts, "high_risk_count": len(high_rows),
        "high_risk_amount": high_risk_amount, "savings_risk": savings_risk,
        "alerts": alerts, "anomalies": anomalies, "suppliers": suppliers,
        "risk_mix": mix,
    }


def _price_anomalies(company, from_date, limit=20):
    params = {"from_date": from_date, "company": company}
    company_filter = "AND pi.company=%(company)s" if company else ""
    rows = frappe.db.sql(f"""
        SELECT pii.item_code, pi.supplier,
               MAX(pii.rate) current_rate,
               MIN(pii.rate) best_rate,
               AVG(pii.rate) avg_rate,
               SUM(pii.base_amount) spend
        FROM `tabPurchase Invoice Item` pii
        INNER JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
        WHERE pi.docstatus=1 AND IFNULL(pi.is_return,0)=0
          AND pi.posting_date >= %(from_date)s
          AND pii.item_code IS NOT NULL {company_filter}
        GROUP BY pii.item_code, pi.supplier
        HAVING MIN(pii.rate) > 0
        ORDER BY ((MAX(pii.rate)-MIN(pii.rate))/MIN(pii.rate)) DESC
        LIMIT {int(limit)}
    """, params, as_dict=True)
    # Compare each supplier's average to the best average for the same item.
    best = {}
    for r in rows:
        key = r.item_code
        avg = float(r.avg_rate or 0)
        if key not in best or avg < best[key]: best[key] = avg
    out=[]
    for r in rows:
        current=float(r.avg_rate or r.current_rate or 0); b=float(best.get(r.item_code) or 0)
        variance=((current-b)/b*100) if b else 0
        if variance >= 5:
            out.append({"item_code":r.item_code,"supplier":r.supplier,"current_rate":current,"best_rate":b,"variance_pct":variance,"spend":r.spend})
    if not out:
        filters={"period_end":[">=",from_date]}
        if company: filters["company"]=company
        brows=frappe.get_all("Supplier Price Benchmark",filters=filters,fields=["item_code","supplier","average_rate","total_spend"],order_by="period_end desc",limit_page_length=5000)
        latest={} ; best={}
        for r in brows:
            key=(r.item_code,r.supplier)
            if key not in latest: latest[key]=r
            rate=float(r.average_rate or 0)
            if r.item_code not in best or rate<best[r.item_code]: best[r.item_code]=rate
        for (ic,sp),r in latest.items():
            cur=float(r.average_rate or 0); b=float(best.get(ic) or 0); var=((cur-b)/b*100) if b else 0
            if var>=5: out.append({"item_code":ic,"supplier":sp,"current_rate":cur,"best_rate":b,"variance_pct":var,"spend":r.total_spend})
        out=sorted(out,key=lambda x:x["variance_pct"],reverse=True)
    return out[:limit]


@frappe.whitelist()
def get_price_intelligence(item_code=None, supplier=None, company=None, days=365):
    frappe.only_for(["Purchase Guard Analyst", "Purchase Guard Manager", "System Manager"])
    from_date = _date_from(days)
    params={"from_date":from_date,"company":company,"item_code":item_code,"supplier":supplier}
    clauses=["pi.docstatus=1","IFNULL(pi.is_return,0)=0","pi.posting_date >= %(from_date)s"]
    if company: clauses.append("pi.company=%(company)s")
    if item_code: clauses.append("pii.item_code=%(item_code)s")
    if supplier: clauses.append("pi.supplier=%(supplier)s")
    where=" AND ".join(clauses)
    rows=frappe.db.sql(f"""
      SELECT pii.item_code, pi.supplier, DATE_FORMAT(pi.posting_date,'%%Y-%%m') period,
             AVG(pii.rate) rate, SUM(pii.qty) qty, SUM(pii.base_amount) spend
      FROM `tabPurchase Invoice Item` pii INNER JOIN `tabPurchase Invoice` pi ON pi.name=pii.parent
      WHERE {where} GROUP BY pii.item_code, pi.supplier, DATE_FORMAT(pi.posting_date,'%%Y-%%m')
      ORDER BY period ASC
    """,params,as_dict=True)
    latest={}; best={}
    for r in rows:
      latest[(r.item_code,r.supplier)]=r
      key=r.item_code; rate=float(r.rate or 0)
      if key not in best or rate<best[key]: best[key]=rate
    items=[]
    for key,r in latest.items():
      b=best.get(r.item_code,0); cur=float(r.rate or 0); var=((cur-b)/b*100) if b else 0
      items.append({"item_code":r.item_code,"supplier":r.supplier,"current_rate":cur,"best_rate":b,"variance_pct":var,"spend":r.spend})
    items=sorted(items,key=lambda x:x["variance_pct"],reverse=True)[:50]
    history=[{"period":r.period,"rate":r.rate,"supplier":r.supplier,"item_code":r.item_code} for r in rows]
    if not history:
        bclauses=["period_end >= %(from_date)s"]
        if company: bclauses.append("company=%(company)s")
        if item_code: bclauses.append("item_code=%(item_code)s")
        if supplier: bclauses.append("supplier=%(supplier)s")
        brows=frappe.get_all("Supplier Price Benchmark", filters={"period_end":[">=",from_date], **({"company":company} if company else {}), **({"item_code":item_code} if item_code else {}), **({"supplier":supplier} if supplier else {})}, fields=["item_code","supplier","period_start","average_rate","total_spend"], order_by="period_start asc", limit_page_length=5000)
        latest={} ; best={}
        for r in brows:
            latest[(r.item_code,r.supplier)]=r
            key=r.item_code; rate=float(r.average_rate or 0)
            if key not in best or rate < best[key]: best[key]=rate
            history.append({"period":str(r.period_start)[:7],"rate":r.average_rate,"supplier":r.supplier,"item_code":r.item_code})
        items=[]
        for (ic,sp),r in latest.items():
            cur=float(r.average_rate or 0); b=float(best.get(ic) or 0); var=((cur-b)/b*100) if b else 0
            items.append({"item_code":ic,"supplier":sp,"current_rate":cur,"best_rate":b,"variance_pct":var,"spend":r.total_spend})
        items=sorted(items,key=lambda x:x["variance_pct"],reverse=True)[:50]
    return {"items":items,"history":history,"from_date":from_date}


@frappe.whitelist()
def get_invoice_guard(invoice):
    frappe.only_for(["Purchase Guard Analyst", "Purchase Guard Manager", "Accounts User", "System Manager"])
    return frappe.get_all("Purchase Risk Alert", filters={"reference_doctype":"Purchase Invoice","reference_name":invoice},
        fields=["name","risk_type","severity","risk_score","amount","title","evidence","recommended_action","status"], order_by="risk_score desc", limit_page_length=50)


@frappe.whitelist()
def get_supplier_guard(supplier, company=None):
    frappe.only_for(["Purchase Guard Analyst", "Purchase Guard Manager", "Buying User", "System Manager"])
    filters={"supplier":supplier}
    if company: filters["company"]=company
    assessment=frappe.get_all("Supplier Risk Assessment",filters=filters,fields=["*"],order_by="assessment_date desc",limit_page_length=1)
    alerts=frappe.get_all("Purchase Risk Alert",filters={"supplier":supplier,"status":["in",["Open","Under Review"]]},fields=["risk_type","severity","risk_score","title","reference_name"],order_by="risk_score desc",limit_page_length=10)
    return {"assessment":assessment[0] if assessment else None,"alerts":alerts}
