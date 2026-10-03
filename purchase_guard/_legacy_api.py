"""
Backward-compatible API aliases.

Older Purchase Guard code may import these functions from
purchase_guard._legacy_api. Keep them available while the
canonical implementation lives in purchase_guard.api.
"""

from purchase_guard.api import (
    get_dashboard_data,
    scan_invoice,
    get_supplier_guard,
    get_price_intelligence,
    get_invoice_guard,
    run_scan,
)

__all__ = [
    "get_dashboard_data",
    "scan_invoice",
    "get_supplier_guard",
    "get_price_intelligence",
    "get_invoice_guard",
    "run_scan",
]
