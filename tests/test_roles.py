import unittest

import testutil


class RoleLinkingTests(unittest.TestCase):
    def setUp(self):
        testutil.reset_db()
        self.patient_token, self.patient = testutil.register_user(username="patient1")

    def test_patient_has_invite_code(self):
        status, res = testutil.dispatch("GET", "/api/auth/me", token=self.patient_token)
        self.assertEqual(status, 200)
        self.assertTrue(res["user"]["invite_code"])

    def test_register_non_patient_requires_invite_code(self):
        status, res = testutil.dispatch(
            "POST", "/api/auth/register",
            {"username": "caretaker1", "password": "password123", "role": "CARETAKER"},
        )
        self.assertEqual(status, 400)

    def test_register_non_patient_with_invalid_code_rejected(self):
        status, res = testutil.dispatch(
            "POST", "/api/auth/register",
            {"username": "caretaker1", "password": "password123", "role": "CARETAKER", "invite_code": "BADCODE1"},
        )
        self.assertEqual(status, 400)

    def test_caretaker_links_and_sees_patient_data(self):
        _, medicine = testutil.dispatch(
            "POST", "/api/medicines", {"name": "Tablet A", "initial_stock": 10}, token=self.patient_token
        )
        caretaker_token, caretaker_user = testutil.register_linked_user(self.patient_token, "CARETAKER")
        self.assertEqual(caretaker_user["linked_patient_id"], self.patient["id"])
        self.assertTrue(caretaker_user["setup_completed"])  # no wizard for linked accounts

        status, res = testutil.dispatch("GET", "/api/medicines", token=caretaker_token)
        self.assertEqual(status, 200)
        self.assertEqual(len(res["medicines"]), 1)
        self.assertEqual(res["medicines"][0]["name"], "Tablet A")

    def test_caretaker_is_read_only_medicine_log_with_no_camera_or_device_access(self):
        _, medicine = testutil.dispatch(
            "POST", "/api/medicines", {"name": "Tablet A", "initial_stock": 10}, token=self.patient_token
        )
        testutil.dispatch(
            "POST", "/api/schedules",
            {"medicine_id": medicine["medicine"]["id"], "scheduled_time": testutil.current_hhmm(), "dosage": 1},
            token=self.patient_token,
        )
        testutil.dispatch("POST", "/api/cameras", {"name": "Cam"}, token=self.patient_token)
        caretaker_token, _ = testutil.register_linked_user(self.patient_token, "CARETAKER")

        # Can view the medicine log / today's records / notifications.
        status, today = testutil.dispatch("GET", "/api/medications/today", token=caretaker_token)
        self.assertEqual(status, 200)
        status, _ = testutil.dispatch("GET", "/api/medication-history", token=caretaker_token)
        self.assertEqual(status, 200)
        status, _ = testutil.dispatch("GET", "/api/notifications", token=caretaker_token)
        self.assertEqual(status, 200)

        # Cannot mark a dose taken.
        record_id = today["records"][0]["id"]
        status, _ = testutil.dispatch("POST", f"/api/medications/{record_id}/taken", token=caretaker_token)
        self.assertEqual(status, 403)

        # Cannot manage medicines/schedule/stock.
        status, _ = testutil.dispatch(
            "POST", "/api/medicines", {"name": "Tablet B", "initial_stock": 5}, token=caretaker_token
        )
        self.assertEqual(status, 403)

        # No camera or smart-home access at all, not even to view.
        status, _ = testutil.dispatch("GET", "/api/cameras", token=caretaker_token)
        self.assertEqual(status, 403)
        status, _ = testutil.dispatch("GET", "/api/devices", token=caretaker_token)
        self.assertEqual(status, 403)

        # Stock is untouched since the taken attempt was rejected.
        _, stock = testutil.dispatch("GET", "/api/stock", token=self.patient_token)
        self.assertEqual(stock["stock"][0]["current_stock"], 10)

    def test_family_member_can_manage_medicines_and_schedules(self):
        _, medicine = testutil.dispatch(
            "POST", "/api/medicines", {"name": "Tablet A", "initial_stock": 10}, token=self.patient_token
        )
        family_token, _ = testutil.register_linked_user(self.patient_token, "FAMILY")

        status, res = testutil.dispatch(
            "POST", "/api/medicines", {"name": "Tablet B", "initial_stock": 5}, token=family_token
        )
        self.assertEqual(status, 201)

        status, schedule = testutil.dispatch(
            "POST", "/api/schedules",
            {"medicine_id": res["medicine"]["id"], "scheduled_time": testutil.current_hhmm(), "dosage": 1},
            token=family_token,
        )
        self.assertEqual(status, 201)
        self.assertEqual(schedule["schedule"]["medicine_id"], res["medicine"]["id"])

        status, _ = testutil.dispatch(
            "POST", f"/api/stock/{medicine['medicine']['id']}/add", {"amount": 5}, token=family_token
        )
        self.assertEqual(status, 403)

        # But can still view.
        status, res = testutil.dispatch("GET", "/api/medicines", token=family_token)
        self.assertEqual(status, 200)
        self.assertEqual(len(res["medicines"]), 2)

    def test_family_member_has_full_camera_and_device_control(self):
        family_token, _ = testutil.register_linked_user(self.patient_token, "FAMILY")

        # Cameras: can add, view, and connect/disconnect - full control.
        status, res = testutil.dispatch("POST", "/api/cameras", {"name": "Cam"}, token=family_token)
        self.assertEqual(status, 201)
        camera_id = res["camera"]["id"]
        status, res = testutil.dispatch("POST", f"/api/cameras/{camera_id}/connect", token=family_token)
        self.assertEqual(status, 200)
        self.assertEqual(res["camera"]["status"], "STREAMING")

        # Smart-home devices: can add and command - full control.
        status, res = testutil.dispatch(
            "POST", "/api/devices", {"name": "Light", "device_type": "light"}, token=family_token
        )
        self.assertEqual(status, 201)
        device_id = res["device"]["id"]
        status, res = testutil.dispatch(
            "POST", f"/api/devices/{device_id}/command", {"command": "ON"}, token=family_token
        )
        self.assertEqual(status, 200)
        self.assertEqual(res["state"], "ON")

    def test_doctor_has_no_camera_or_device_access(self):
        testutil.dispatch("POST", "/api/cameras", {"name": "Cam"}, token=self.patient_token)
        doctor_token, _ = testutil.register_linked_user(self.patient_token, "DOCTOR")

        status, _ = testutil.dispatch("GET", "/api/cameras", token=doctor_token)
        self.assertEqual(status, 403)

        status, _ = testutil.dispatch("GET", "/api/devices", token=doctor_token)
        self.assertEqual(status, 403)

        # But history/medicines remain viewable.
        status, _ = testutil.dispatch("GET", "/api/medicines", token=doctor_token)
        self.assertEqual(status, 200)
        status, _ = testutil.dispatch("GET", "/api/medication-history", token=doctor_token)
        self.assertEqual(status, 200)

    def test_doctor_cannot_write_medicines(self):
        doctor_token, _ = testutil.register_linked_user(self.patient_token, "DOCTOR")
        status, _ = testutil.dispatch(
            "POST", "/api/medicines", {"name": "Tablet A", "initial_stock": 10}, token=doctor_token
        )
        self.assertEqual(status, 403)

    def test_patient_can_list_and_revoke_linked_accounts(self):
        caretaker_token, caretaker_user = testutil.register_linked_user(self.patient_token, "CARETAKER")

        status, res = testutil.dispatch("GET", "/api/auth/linked-accounts", token=self.patient_token)
        self.assertEqual(status, 200)
        self.assertEqual(len(res["accounts"]), 1)
        self.assertEqual(res["accounts"][0]["role"], "CARETAKER")

        status, _ = testutil.dispatch(
            "POST", f"/api/auth/linked-accounts/{caretaker_user['id']}/revoke", token=self.patient_token
        )
        self.assertEqual(status, 200)

        # Revoked account's existing session is dead immediately.
        status, _ = testutil.dispatch("GET", "/api/medicines", token=caretaker_token)
        self.assertEqual(status, 401)

    def test_unlinked_caretaker_cannot_be_registered_without_valid_code_but_once_revoked_needs_relink(self):
        caretaker_token, caretaker_user = testutil.register_linked_user(self.patient_token, "CARETAKER")
        testutil.dispatch(
            "POST", f"/api/auth/linked-accounts/{caretaker_user['id']}/revoke", token=self.patient_token
        )
        # Log back in (new session) as the now-unlinked caretaker.
        status, res = testutil.dispatch(
            "POST", "/api/auth/login", {"username": caretaker_user["username"], "password": "testpass123"}
        )
        self.assertEqual(status, 200)
        new_token = res["token"]
        status, res = testutil.dispatch("GET", "/api/medicines", token=new_token)
        self.assertEqual(status, 409)

    def test_non_patient_roles_do_not_get_setup_wizard(self):
        _, family_user = testutil.register_linked_user(self.patient_token, "FAMILY")
        self.assertTrue(family_user["setup_completed"])

    def test_linked_accounts_only_visible_to_the_right_patient(self):
        testutil.register_linked_user(self.patient_token, "CARETAKER")
        other_patient_token, _ = testutil.register_user(username="patient2")
        status, res = testutil.dispatch("GET", "/api/auth/linked-accounts", token=other_patient_token)
        self.assertEqual(status, 200)
        self.assertEqual(res["accounts"], [])


if __name__ == "__main__":
    unittest.main()
