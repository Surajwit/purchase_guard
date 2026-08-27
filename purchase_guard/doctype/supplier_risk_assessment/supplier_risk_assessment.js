frappe.ui.form.on("Supplier Risk Assessment", {
    refresh(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__("Recalculate"), () => {
                frappe.call({
                    method: "purchase_guard.purchase_guard.services.scanner.update_supplier_risk",
                    args: {
                        supplier: frm.doc.supplier,
                        company: frm.doc.company,
                        from_date: frappe.datetime.add_days(frm.doc.assessment_date, -365)
                    },
                    callback: () => frm.reload_doc()
                });
            }, __("Actions"));
        }
    }
});
