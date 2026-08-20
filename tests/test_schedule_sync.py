import unittest

import testutil


class ScheduleUpdateIsActiveOnlyTests(unittest.TestCase):
    """Schedules can no longer be edited (medicine/time/dosage) - only
    Enable/Disable (the 'active' flag) is a supported update. Delete +
    add a new schedule is the supported way to change the other fields."""

    def setUp(self):
        testutil.reset_db()
        self.token, self.user = testutil.register_user()
        _, med = testutil.dispatch(
            "POST", "/api/medicines", {"name": "Tablet A", "initial_stock": 20}, token=self.token
        )
        self.medicine_id = med["medicine"]["id"]
        _, med_b = testutil.dispatch(
            "POST", "/api/medicines", {"name": "Tablet B", "initial_stock": 20}, token=self.token
        )
        self.medicine_b_id = med_b["medicine"]["id"]
        _, sched = testutil.dispatch(
            "POST", "/api/schedules",
            {"medicine_id": self.medicine_id, "scheduled_time": testutil.current_hhmm(), "dosage": 1},
            token=self.token,
        )
        self.schedule_id = sched["schedule"]["id"]

    def _today_record(self):
        _, res = testutil.dispatch("GET", "/api/medications/today", token=self.token)
        self.assertEqual(len(res["records"]), 1)
        return res["records"][0]

    def test_updating_scheduled_time_is_rejected(self):
        status, res = testutil.dispatch(
            "PUT", f"/api/schedules/{self.schedule_id}", {"scheduled_time": "16:00"}, token=self.token
        )
        self.assertEqual(status, 400)

    def test_updating_dosage_is_rejected(self):
        status, res = testutil.dispatch(
            "PUT", f"/api/schedules/{self.schedule_id}", {"dosage": 2}, token=self.token
        )
        self.assertEqual(status, 400)

    def test_updating_medicine_is_rejected(self):
        status, res = testutil.dispatch(
            "PUT", f"/api/schedules/{self.schedule_id}", {"medicine_id": self.medicine_b_id}, token=self.token
        )
        self.assertEqual(status, 400)

    def test_active_alongside_another_field_is_also_rejected(self):
        status, res = testutil.dispatch(
            "PUT", f"/api/schedules/{self.schedule_id}", {"active": False, "dosage": 2}, token=self.token
        )
        self.assertEqual(status, 400)

    def test_rejected_update_leaves_the_schedule_and_todays_record_untouched(self):
        original = self._today_record()
        testutil.dispatch("PUT", f"/api/schedules/{self.schedule_id}", {"dosage": 99}, token=self.token)

        _, res = testutil.dispatch("GET", "/api/schedules", token=self.token)
        self.assertEqual(res["schedules"][0]["dosage"], 1)
        unchanged = self._today_record()
        self.assertEqual(unchanged["id"], original["id"])
        self.assertEqual(unchanged["dosage"], 1)

    def test_toggling_active_succeeds_and_does_not_create_a_duplicate_schedule(self):
        status, res = testutil.dispatch(
            "PUT", f"/api/schedules/{self.schedule_id}", {"active": False}, token=self.token
        )
        self.assertEqual(status, 200)
        self.assertFalse(res["schedule"]["active"])

        _, res = testutil.dispatch("GET", "/api/schedules", token=self.token)
        self.assertEqual(len(res["schedules"]), 1)
        self.assertEqual(res["schedules"][0]["id"], self.schedule_id)

    def test_disabling_retracts_todays_pending_record(self):
        self._today_record()
        testutil.dispatch("PUT", f"/api/schedules/{self.schedule_id}", {"active": False}, token=self.token)

        _, today = testutil.dispatch("GET", "/api/medications/today", token=self.token)
        self.assertEqual(len(today["records"]), 0)

    def test_disabling_does_not_touch_an_already_taken_record(self):
        record = self._today_record()
        testutil.dispatch("POST", f"/api/medications/{record['id']}/taken", token=self.token)

        testutil.dispatch("PUT", f"/api/schedules/{self.schedule_id}", {"active": False}, token=self.token)

        _, history = testutil.dispatch("GET", "/api/medication-history", token=self.token)
        taken = [r for r in history["records"] if r["id"] == record["id"]][0]
        self.assertEqual(taken["status"], "TAKEN")

    def test_re_enabling_regenerates_a_fresh_pending_record(self):
        self._today_record()
        testutil.dispatch("PUT", f"/api/schedules/{self.schedule_id}", {"active": False}, token=self.token)
        _, today = testutil.dispatch("GET", "/api/medications/today", token=self.token)
        self.assertEqual(len(today["records"]), 0)

        testutil.dispatch("PUT", f"/api/schedules/{self.schedule_id}", {"active": True}, token=self.token)
        record = self._today_record()
        self.assertEqual(record["status"], "PENDING")


if __name__ == "__main__":
    unittest.main()
