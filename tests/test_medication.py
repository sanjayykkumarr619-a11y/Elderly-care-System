import unittest

import testutil


class MedicationTests(unittest.TestCase):
    def setUp(self):
        testutil.reset_db()
        self.token, self.user = testutil.register_user()

    def _add_medicine(self, initial_stock=30, threshold=5):
        status, res = testutil.dispatch(
            "POST",
            "/api/medicines",
            {"name": "Tablet A", "initial_stock": initial_stock, "low_stock_threshold": threshold},
            token=self.token,
        )
        self.assertEqual(status, 201)
        return res["medicine"]

    def test_add_medicine_sets_initial_and_current_stock(self):
        medicine = self._add_medicine(initial_stock=30, threshold=5)
        self.assertEqual(medicine["initial_stock"], 30)
        self.assertEqual(medicine["current_stock"], 30)
        self.assertEqual(medicine["stock_status"], "NORMAL")

    def test_medicines_require_authentication(self):
        status, res = testutil.dispatch("GET", "/api/medicines")
        self.assertEqual(status, 401)

    def test_users_cannot_see_each_others_medicines(self):
        self._add_medicine()
        other_token, _ = testutil.register_user(username="otheruser1")
        status, res = testutil.dispatch("GET", "/api/medicines", token=other_token)
        self.assertEqual(status, 200)
        self.assertEqual(res["medicines"], [])

    def test_invalid_dosage_rejected_on_schedule(self):
        medicine = self._add_medicine()
        status, res = testutil.dispatch(
            "POST", "/api/schedules",
            {"medicine_id": medicine["id"], "scheduled_time": testutil.current_hhmm(), "dosage": -1},
            token=self.token,
        )
        self.assertEqual(status, 400)

    def test_invalid_medicine_returns_404(self):
        status, res = testutil.dispatch("GET", "/api/medicines/9999", token=self.token)
        self.assertEqual(status, 404)

    def test_schedule_generates_pending_record_for_today(self):
        medicine = self._add_medicine()
        status, res = testutil.dispatch(
            "POST", "/api/schedules",
            {"medicine_id": medicine["id"], "scheduled_time": testutil.current_hhmm(), "dosage": 1},
            token=self.token,
        )
        self.assertEqual(status, 201)

        status, res = testutil.dispatch("GET", "/api/medications/today", token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(len(res["records"]), 1)
        self.assertEqual(res["records"][0]["status"], "PENDING")

    def test_mark_taken_decreases_stock_and_records_confirmation(self):
        medicine = self._add_medicine(initial_stock=30)
        testutil.dispatch(
            "POST", "/api/schedules",
            {"medicine_id": medicine["id"], "scheduled_time": testutil.current_hhmm(), "dosage": 1},
            token=self.token,
        )
        _, today = testutil.dispatch("GET", "/api/medications/today", token=self.token)
        record_id = today["records"][0]["id"]

        status, res = testutil.dispatch("POST", f"/api/medications/{record_id}/taken", token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(res["record"]["status"], "TAKEN")
        self.assertIsNotNone(res["record"]["confirmed_at"])
        self.assertEqual(res["medicine"]["current_stock"], 29)
        self.assertEqual(res["record"]["stock_after"], 29)

    def test_duplicate_taken_does_not_double_deduct_stock(self):
        medicine = self._add_medicine(initial_stock=30)
        testutil.dispatch(
            "POST", "/api/schedules",
            {"medicine_id": medicine["id"], "scheduled_time": testutil.current_hhmm(), "dosage": 1},
            token=self.token,
        )
        _, today = testutil.dispatch("GET", "/api/medications/today", token=self.token)
        record_id = today["records"][0]["id"]

        status1, _ = testutil.dispatch("POST", f"/api/medications/{record_id}/taken", token=self.token)
        status2, res2 = testutil.dispatch("POST", f"/api/medications/{record_id}/taken", token=self.token)

        self.assertEqual(status1, 200)
        self.assertEqual(status2, 409)

        _, med = testutil.dispatch("GET", f"/api/medicines/{medicine['id']}", token=self.token)
        self.assertEqual(med["medicine"]["current_stock"], 29)

    def test_mark_missed_does_not_change_stock(self):
        medicine = self._add_medicine(initial_stock=30)
        testutil.dispatch(
            "POST", "/api/schedules",
            {"medicine_id": medicine["id"], "scheduled_time": testutil.current_hhmm(), "dosage": 1},
            token=self.token,
        )
        _, today = testutil.dispatch("GET", "/api/medications/today", token=self.token)
        record_id = today["records"][0]["id"]

        status, res = testutil.dispatch("POST", f"/api/medications/{record_id}/missed", token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(res["record"]["status"], "MISSED")

        _, med = testutil.dispatch("GET", f"/api/medicines/{medicine['id']}", token=self.token)
        self.assertEqual(med["medicine"]["current_stock"], 30)

    def test_missed_record_cannot_later_be_marked_taken(self):
        medicine = self._add_medicine(initial_stock=30)
        testutil.dispatch(
            "POST", "/api/schedules",
            {"medicine_id": medicine["id"], "scheduled_time": testutil.current_hhmm(), "dosage": 1},
            token=self.token,
        )
        _, today = testutil.dispatch("GET", "/api/medications/today", token=self.token)
        record_id = today["records"][0]["id"]

        testutil.dispatch("POST", f"/api/medications/{record_id}/missed", token=self.token)
        status, _ = testutil.dispatch("POST", f"/api/medications/{record_id}/taken", token=self.token)
        self.assertEqual(status, 409)

        _, med = testutil.dispatch("GET", f"/api/medicines/{medicine['id']}", token=self.token)
        self.assertEqual(med["medicine"]["current_stock"], 30)

    def test_insufficient_stock_blocks_confirmation(self):
        medicine = self._add_medicine(initial_stock=0)
        testutil.dispatch(
            "POST", "/api/schedules",
            {"medicine_id": medicine["id"], "scheduled_time": testutil.current_hhmm(), "dosage": 1},
            token=self.token,
        )
        _, today = testutil.dispatch("GET", "/api/medications/today", token=self.token)
        record_id = today["records"][0]["id"]

        status, res = testutil.dispatch("POST", f"/api/medications/{record_id}/taken", token=self.token)
        self.assertEqual(status, 400)

    def test_sweep_marks_overdue_pending_records_as_missed(self):
        from datetime import datetime, timedelta

        medicine = self._add_medicine(initial_stock=30)
        _, schedule_res = testutil.dispatch(
            "POST", "/api/schedules",
            {"medicine_id": medicine["id"], "scheduled_time": testutil.current_hhmm(), "dosage": 1},
            token=self.token,
        )
        conn = testutil.database.get_connection()
        try:
            old_time = (datetime.now() - timedelta(hours=2)).strftime("%H:%M")
            conn.execute(
                "UPDATE medication_schedules SET scheduled_time = ? WHERE id = ?",
                (old_time, schedule_res["schedule"]["id"]),
            )
            conn.execute("DELETE FROM medication_records")
            conn.commit()
        finally:
            conn.close()

        status, res = testutil.dispatch("GET", "/api/medications/today", token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(res["records"][0]["status"], "MISSED")


if __name__ == "__main__":
    unittest.main()
