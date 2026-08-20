import unittest

import testutil


class LowStockAcceptanceTests(unittest.TestCase):
    """Exact acceptance scenario from the Automatic Low-Stock Caregiver
    Notification spec: Tablet A, initial stock 6, threshold 5, dosage 1."""

    def setUp(self):
        testutil.reset_db()
        self.token, self.user = testutil.register_user(caregiver_email="caregiver@example.com")
        _, res = testutil.dispatch(
            "POST", "/api/medicines",
            {"name": "Tablet A", "initial_stock": 6, "low_stock_threshold": 5},
            token=self.token,
        )
        self.medicine_id = res["medicine"]["id"]
        _, sched = testutil.dispatch(
            "POST", "/api/schedules",
            {"medicine_id": self.medicine_id, "scheduled_time": testutil.current_hhmm(), "dosage": 1},
            token=self.token,
        )

    def _low_stock_notifications(self):
        _, res = testutil.dispatch("GET", "/api/notifications", token=self.token)
        return [n for n in res["notifications"] if n["type"] == "LOW_STOCK"]

    def test_taken_drops_stock_to_threshold_and_fires_alert(self):
        _, today = testutil.dispatch("GET", "/api/medications/today", token=self.token)
        record_id = today["records"][0]["id"]

        status, res = testutil.dispatch("POST", f"/api/medications/{record_id}/taken", token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(res["medicine"]["current_stock"], 5)
        self.assertEqual(res["medicine"]["stock_status"], "LOW_STOCK")

        alerts = self._low_stock_notifications()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["title"], "LOW MEDICINE STOCK")
        self.assertIn("Tablet A", alerts[0]["message"])
        self.assertIn("5", alerts[0]["message"])
        self.assertFalse(alerts[0]["is_read"])
        # Delivery was attempted to the caregiver seeded at registration.
        self.assertEqual(alerts[0]["email_to"], "caregiver@example.com")

    def test_page_refresh_does_not_resend_duplicate_alert(self):
        _, today = testutil.dispatch("GET", "/api/medications/today", token=self.token)
        record_id = today["records"][0]["id"]
        testutil.dispatch("POST", f"/api/medications/{record_id}/taken", token=self.token)
        self.assertEqual(len(self._low_stock_notifications()), 1)

        # Simulate the user refreshing the page a few times - these are all
        # read-only GETs, not stock-changing operations, so none of them
        # should ever re-trigger the alert.
        for _ in range(3):
            testutil.dispatch("GET", "/api/medications/today", token=self.token)
            testutil.dispatch("GET", "/api/stock", token=self.token)
            testutil.dispatch("GET", "/api/stock/alerts", token=self.token)

        self.assertEqual(len(self._low_stock_notifications()), 1)

    def test_refill_resets_alert_state_and_a_later_dip_realerts(self):
        _, today = testutil.dispatch("GET", "/api/medications/today", token=self.token)
        record_id = today["records"][0]["id"]
        testutil.dispatch("POST", f"/api/medications/{record_id}/taken", token=self.token)
        self.assertEqual(len(self._low_stock_notifications()), 1)

        # Refill well above threshold - resets low-stock state, no new alert.
        status, res = testutil.dispatch(
            "POST", f"/api/stock/{self.medicine_id}/add", {"amount": 20}, token=self.token
        )
        self.assertEqual(status, 200)
        self.assertEqual(res["medicine"]["current_stock"], 25)
        self.assertEqual(len(self._low_stock_notifications()), 1)  # still just the first one

        # Manual adjustment back down to the threshold - a fresh dip, so it
        # must alert again (this is the "new low-stock email" the spec's
        # acceptance test requires).
        status, res = testutil.dispatch(
            "PUT", f"/api/stock/{self.medicine_id}", {"current_stock": 5}, token=self.token
        )
        self.assertEqual(status, 200)
        alerts = self._low_stock_notifications()
        self.assertEqual(len(alerts), 2)

    def test_missed_dose_never_triggers_low_stock_check(self):
        # Force the pending record to be overdue so the sweep marks it
        # MISSED without ever touching stock.
        conn = testutil.database.get_connection()
        try:
            conn.execute(
                "UPDATE medication_schedules SET scheduled_time = '00:00' WHERE medicine_id = ?",
                (self.medicine_id,),
            )
            conn.execute("DELETE FROM medication_records")
            conn.commit()
        finally:
            conn.close()

        status, res = testutil.dispatch("GET", "/api/medications/today", token=self.token)
        self.assertEqual(res["records"][0]["status"], "MISSED")

        _, stock = testutil.dispatch("GET", "/api/stock", token=self.token)
        self.assertEqual(stock["stock"][0]["current_stock"], 6)  # untouched
        self.assertEqual(len(self._low_stock_notifications()), 0)

    def test_only_active_caregivers_receive_the_alert(self):
        # Add a second, inactive recipient.
        testutil.dispatch(
            "POST", "/api/caregivers",
            {"name": "Inactive One", "email": "inactive@example.com", "active": False},
            token=self.token,
        )
        _, today = testutil.dispatch("GET", "/api/medications/today", token=self.token)
        record_id = today["records"][0]["id"]
        testutil.dispatch("POST", f"/api/medications/{record_id}/taken", token=self.token)

        alerts = self._low_stock_notifications()
        self.assertEqual(len(alerts), 1)
        self.assertNotIn("inactive@example.com", alerts[0]["email_to"])
        self.assertIn("caregiver@example.com", alerts[0]["email_to"])

    def test_manual_stock_adjustment_below_threshold_triggers_alert(self):
        status, res = testutil.dispatch(
            "PUT", f"/api/stock/{self.medicine_id}", {"current_stock": 3}, token=self.token
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(self._low_stock_notifications()), 1)


class CaregiverApiTests(unittest.TestCase):
    def setUp(self):
        testutil.reset_db()
        self.token, self.user = testutil.register_user(caregiver_email="caregiver@example.com")

    def test_registration_seeds_first_caregiver(self):
        status, res = testutil.dispatch("GET", "/api/caregivers", token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(len(res["caregivers"]), 1)
        self.assertEqual(res["caregivers"][0]["email"], "caregiver@example.com")
        self.assertTrue(res["caregivers"][0]["active"])

    def test_create_update_delete_caregiver(self):
        status, res = testutil.dispatch(
            "POST", "/api/caregivers", {"name": "Family Member", "email": "familymember@gmail.com"},
            token=self.token,
        )
        self.assertEqual(status, 201)
        caregiver_id = res["caregiver"]["id"]

        status, res = testutil.dispatch(
            "PUT", f"/api/caregivers/{caregiver_id}", {"active": False}, token=self.token
        )
        self.assertEqual(status, 200)
        self.assertFalse(res["caregiver"]["active"])

        status, res = testutil.dispatch("DELETE", f"/api/caregivers/{caregiver_id}", token=self.token)
        self.assertEqual(status, 200)

        status, res = testutil.dispatch("GET", "/api/caregivers", token=self.token)
        ids = [c["id"] for c in res["caregivers"]]
        self.assertNotIn(caregiver_id, ids)

    def test_create_rejects_invalid_email(self):
        status, res = testutil.dispatch(
            "POST", "/api/caregivers", {"name": "Bad", "email": "not-an-email"}, token=self.token
        )
        self.assertEqual(status, 400)

    def test_caretaker_cannot_manage_caregivers(self):
        caretaker_token, _ = testutil.register_linked_user(self.token, "CARETAKER")
        status, res = testutil.dispatch("GET", "/api/caregivers", token=caretaker_token)
        self.assertEqual(status, 403)


if __name__ == "__main__":
    unittest.main()
