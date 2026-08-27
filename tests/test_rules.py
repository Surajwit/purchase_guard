import unittest
from purchase_guard.purchase_guard.services.rules import price_variance_pct, quantity_variance_pct, duplicate_key

class TestPurchaseGuardRules(unittest.TestCase):
    def test_price_variance(self):
        self.assertAlmostEqual(float(price_variance_pct(110, 100)), 10.0)

    def test_quantity_variance(self):
        self.assertAlmostEqual(float(quantity_variance_pct(105, 100)), 5.0)

    def test_duplicate_key(self):
        self.assertEqual(duplicate_key("Supplier A", "INV-1"), "Supplier A::inv-1")
