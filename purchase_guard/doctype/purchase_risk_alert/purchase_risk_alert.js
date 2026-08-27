frappe.ui.form.on("Purchase Risk Alert", {
    refresh(frm) {
        // References are populated by the Purchase Guard engine and are intentionally
        // hidden/read-only so users never have to configure them.
        if (frm.doc.reference_doctype && frm.doc.reference_name) {
            frm.add_custom_button(__("Open Source Transaction"), () => {
                frappe.set_route("Form", frm.doc.reference_doctype, frm.doc.reference_name);
            }, __("Actions"));
        }
        if (!frm.is_new() && frm.doc.status === "Open") {
            frm.add_custom_button(__("Start Review"), () => {
                frm.set_value("status", "Under Review");
                frm.set_value("reviewed_by", frappe.session.user);
                frm.save();
            }, __("Actions"));
        }
    }
});
