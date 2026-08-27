app_name="purchase_guard"
app_title="Purchase Guard"
app_publisher="Purchase Guard"
app_description="Purchase protection and supplier intelligence for ERPNext"
app_email="support@example.com"
app_license="MIT"
app_version="0.2.1"
required_apps=["erpnext"]
after_install="purchase_guard.setup.install.after_install"
after_migrate="purchase_guard.setup.install.after_migrate"
app_include_css="/assets/purchase_guard/css/purchase_guard.css"
scheduler_events={"daily":["purchase_guard.purchase_guard.services.scanner.run_scheduled_scan"]}
doc_events={"Purchase Invoice":{"on_submit":"purchase_guard.purchase_guard.services.events.on_purchase_invoice_submit","on_cancel":"purchase_guard.purchase_guard.services.events.on_purchase_invoice_cancel"},"Purchase Order":{"on_submit":"purchase_guard.purchase_guard.services.events.on_purchase_order_submit","on_cancel":"purchase_guard.purchase_guard.services.events.on_purchase_order_cancel"},"Purchase Receipt":{"on_submit":"purchase_guard.purchase_guard.services.events.on_purchase_receipt_submit","on_cancel":"purchase_guard.purchase_guard.services.events.on_purchase_receipt_cancel"},"Payment Entry":{"on_submit":"purchase_guard.purchase_guard.services.events.on_payment_entry_submit"}}
doctype_js={"Purchase Invoice":"public/js/purchase_invoice.js","Supplier":"public/js/supplier.js"}
fixtures=[{"dt":"Role","filters":[["name","in",["Purchase Guard Manager","Purchase Guard Analyst"]]]},{"dt":"Custom Field","filters":[["module","=","Purchase Guard"]]},{"dt":"Workspace","filters":[["name","=","Purchase Guard"]]}]
