import frappe
from frappe.model.document import Document


class PurchaseRiskAlert(Document):
    def before_insert(self):
        # Purchase Risk Alerts are findings produced by the Purchase Guard engine.
        # Do not allow users to manufacture alerts manually. Internal scanner/demo
        # code can still insert with ignore_permissions=True.
        if not self.flags.ignore_permissions and not self.flags.in_migrate:
            frappe.throw(__("Purchase Risk Alerts are generated automatically by Purchase Guard. Run an analysis from the relevant purchase transaction or dashboard."))
