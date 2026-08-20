import unittest

import testutil


class StockTests(unittest.TestCase):
    def setUp(self):
        testutil.reset_db()
        self.token, self.user = testutil.register_user()

    def _add_medicine(self, initial_stock=10, threshold=5):
        status, res = testutil.dispatch(
            "POST",
            "/api/medicines",
            {"name": "Tablet A", "initial_stock": initial_stock, "low_stock_threshold": threshold},
            token=self.token,
        )
        self.assertEqual(status, 201)
        return res["medicine"]

    def test_add_stock_increases_current_stock(self):
        medicine = self._add_medicine(initial_stock=4)
        status, res = testutil.dispatch("POST", f"/api/stock/{medicine['id']}/add", {"amount": 20}, token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(res["medicine"]["current_stock"], 24)

    def test_add_stock_creates_refill_notification(self):
        medicine = self._add_medicine(initial_stock=4)
        testutil.dispatch("POST", f"/api/stock/{medicine['id']}/add", {"amount": 20}, token=self.token)
        status, res = testutil.dispatch("GET", "/api/notifications", token=self.token)
        self.assertEqual(status, 200)
        self.assertTrue(any(n["type"] == "REFILL" for n in res["notifications"]))

    def test_low_stock_alert_appears_when_at_or_below_threshold(self):
        medicine = self._add_medicine(initial_stock=5, threshold=5)
        status, res = testutil.dispatch("GET", "/api/stock/alerts", token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(len(res["alerts"]), 1)
        self.assertEqual(res["alerts"][0]["id"], medicine["id"])

    def test_low_stock_notification_created_when_taken_dose_crosses_threshold(self):
        medicine = self._add_medicine(initial_stock=6, threshold=5)
        testutil.dispatch(
            "POST", "/api/schedules",
            {"medicine_id": medicine["id"], "scheduled_time": testutil.current_hhmm(), "dosage": 1},
            token=self.token,
        )
        _, today = testutil.dispatch("GET", "/api/medications/today", token=self.token)
        record_id = today["records"][0]["id"]
        testutil.dispatch("POST", f"/api/medications/{record_id}/taken", token=self.token)

        status, res = testutil.dispatch("GET", "/api/notifications", token=self.token)
        self.assertEqual(status, 200)
        self.assertTrue(any(n["type"] == "LOW_STOCK" for n in res["notifications"]))

    def test_stock_cannot_go_negative_via_set_stock(self):
        medicine = self._add_medicine(initial_stock=10)
        status, res = testutil.dispatch("PUT", f"/api/stock/{medicine['id']}", {"current_stock": -5}, token=self.token)
        self.assertEqual(status, 400)

    def test_stock_add_requires_positive_amount(self):
        medicine = self._add_medicine(initial_stock=10)
        status, res = testutil.dispatch("POST", f"/api/stock/{medicine['id']}/add", {"amount": -3}, token=self.token)
        self.assertEqual(status, 400)

    def test_add_stock_invalid_medicine_returns_404(self):
        status, res = testutil.dispatch("POST", "/api/stock/9999/add", {"amount": 5}, token=self.token)
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
