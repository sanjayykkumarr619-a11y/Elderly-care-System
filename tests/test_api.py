import unittest

import testutil


class AuthTests(unittest.TestCase):
    def setUp(self):
        testutil.reset_db()

    def test_register_requires_caregiver_email(self):
        status, res = testutil.dispatch(
            "POST", "/api/auth/register",
            {"username": "alice", "password": "password123", "caregiver_email": ""},
        )
        self.assertEqual(status, 400)

    def test_register_then_login(self):
        token, user = testutil.register_user(username="alice1")
        self.assertTrue(token)
        self.assertEqual(user["caregiver_email"], "caregiver@example.com")
        self.assertFalse(user["setup_completed"])

        status, res = testutil.dispatch(
            "POST", "/api/auth/login", {"username": "alice1", "password": "testpass123"}
        )
        self.assertEqual(status, 200)
        self.assertTrue(res["token"])

    def test_login_wrong_password_rejected(self):
        testutil.register_user(username="bob1")
        status, res = testutil.dispatch(
            "POST", "/api/auth/login", {"username": "bob1", "password": "wrongpassword"}
        )
        self.assertEqual(status, 401)

    def test_duplicate_username_rejected(self):
        testutil.register_user(username="carol1")
        status, res = testutil.dispatch(
            "POST", "/api/auth/register",
            {"username": "carol1", "password": "password123", "caregiver_email": "carol.caregiver@example.com"},
        )
        self.assertEqual(status, 409)

    def test_me_requires_valid_token(self):
        status, res = testutil.dispatch("GET", "/api/auth/me")
        self.assertEqual(status, 401)

        token, _ = testutil.register_user(username="dave1")
        status, res = testutil.dispatch("GET", "/api/auth/me", token=token)
        self.assertEqual(status, 200)
        self.assertEqual(res["user"]["username"], "dave1")

    def test_setup_completed_can_be_marked(self):
        token, user = testutil.register_user(username="erin1")
        self.assertFalse(user["setup_completed"])
        status, res = testutil.dispatch("PUT", "/api/auth/me", {"setup_completed": True}, token=token)
        self.assertEqual(status, 200)
        self.assertTrue(res["user"]["setup_completed"])

    def test_logout_invalidates_token(self):
        token, _ = testutil.register_user(username="frank1")
        status, _ = testutil.dispatch("POST", "/api/auth/logout", token=token)
        self.assertEqual(status, 200)
        status, _ = testutil.dispatch("GET", "/api/auth/me", token=token)
        self.assertEqual(status, 401)


class GeneralApiTests(unittest.TestCase):
    def setUp(self):
        testutil.reset_db()
        self.token, self.user = testutil.register_user()

    def test_unknown_route_returns_404(self):
        status, res = testutil.dispatch("GET", "/api/does-not-exist", token=self.token)
        self.assertEqual(status, 404)

    def test_camera_crud_and_connect_flow(self):
        status, res = testutil.dispatch(
            "POST", "/api/cameras", {"name": "Bedroom Camera", "location": "Bedroom"}, token=self.token
        )
        self.assertEqual(status, 201)
        camera_id = res["camera"]["id"]
        self.assertEqual(res["camera"]["status"], "OFFLINE")

        status, res = testutil.dispatch("GET", f"/api/cameras/{camera_id}/stream", token=self.token)
        self.assertEqual(status, 409)  # offline, cannot stream yet

        status, res = testutil.dispatch("POST", f"/api/cameras/{camera_id}/connect", token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(res["camera"]["status"], "STREAMING")

        status, res = testutil.dispatch("GET", f"/api/cameras/{camera_id}/stream", token=self.token)
        self.assertEqual(status, 200)
        self.assertTrue(res["simulated"])

        status, res = testutil.dispatch("POST", f"/api/cameras/{camera_id}/disconnect", token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(res["camera"]["status"], "OFFLINE")

    def test_camera_invalid_id_returns_404(self):
        status, res = testutil.dispatch("GET", "/api/cameras/9999/status", token=self.token)
        self.assertEqual(status, 404)

    def test_camera_not_visible_to_other_user(self):
        _, res = testutil.dispatch("POST", "/api/cameras", {"name": "Cam"}, token=self.token)
        camera_id = res["camera"]["id"]
        other_token, _ = testutil.register_user(username="otherviewer1")
        status, res = testutil.dispatch("GET", f"/api/cameras/{camera_id}/status", token=other_token)
        self.assertEqual(status, 404)

    def test_device_create_and_command_flow(self):
        status, res = testutil.dispatch(
            "POST", "/api/devices", {"name": "Bedroom Light", "device_type": "light", "location": "Bedroom"},
            token=self.token,
        )
        self.assertEqual(status, 201)
        device_id = res["device"]["id"]

        status, res = testutil.dispatch(
            "POST", f"/api/devices/{device_id}/command", {"command": "ON"}, token=self.token
        )
        self.assertEqual(status, 200)
        self.assertEqual(res["state"], "ON")

        status, res = testutil.dispatch("GET", f"/api/devices/{device_id}/status", token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(res["state"], "ON")

    def test_device_invalid_command_returns_400(self):
        _, res = testutil.dispatch("POST", "/api/devices", {"name": "Fan"}, token=self.token)
        device_id = res["device"]["id"]
        status, res = testutil.dispatch(
            "POST", f"/api/devices/{device_id}/command", {"command": "EXPLODE"}, token=self.token
        )
        self.assertEqual(status, 400)

    def test_device_command_invalid_device_returns_404(self):
        status, res = testutil.dispatch(
            "POST", "/api/devices/9999/command", {"command": "ON"}, token=self.token
        )
        self.assertEqual(status, 404)

    def test_robot_endpoints(self):
        status, res = testutil.dispatch("GET", "/api/robot/status", token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(res["robot"]["status"], "IDLE")

        status, res = testutil.dispatch("POST", "/api/robot/dispense", {}, token=self.token)
        self.assertEqual(status, 200)

        status, res = testutil.dispatch("POST", "/api/robot/alarm", {}, token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(res["robot"]["status"], "ALARM")

        status, res = testutil.dispatch("POST", "/api/robot/stop", {}, token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(res["robot"]["status"], "IDLE")

    def test_sensor_endpoints_seeded_on_registration(self):
        status, res = testutil.dispatch("GET", "/api/sensors", token=self.token)
        self.assertEqual(status, 200)
        self.assertTrue(len(res["sensors"]) > 0)
        sensor_id = res["sensors"][0]["id"]

        status, res = testutil.dispatch(
            "POST", f"/api/sensors/{sensor_id}/data", {"value": "MOTION_DETECTED"}, token=self.token
        )
        self.assertEqual(status, 200)
        self.assertEqual(res["sensor"]["last_value"], "MOTION_DETECTED")

    def test_notification_mark_read(self):
        _, res = testutil.dispatch(
            "POST", "/api/medicines", {"name": "Tablet A", "initial_stock": 3, "low_stock_threshold": 5},
            token=self.token,
        )
        medicine_id = res["medicine"]["id"]
        # Adding stock always creates a REFILL notification.
        testutil.dispatch("POST", f"/api/stock/{medicine_id}/add", {"amount": 5}, token=self.token)

        _, notif = testutil.dispatch("GET", "/api/notifications", token=self.token)
        self.assertTrue(len(notif["notifications"]) > 0)
        notification_id = notif["notifications"][0]["id"]
        self.assertFalse(notif["notifications"][0]["is_read"])

        status, res = testutil.dispatch(
            "POST", f"/api/notifications/{notification_id}/read", token=self.token
        )
        self.assertEqual(status, 200)
        self.assertTrue(res["notification"]["is_read"])

    def test_notification_has_email_status_when_gateway_not_configured(self):
        _, res = testutil.dispatch(
            "POST", "/api/medicines", {"name": "Tablet A", "initial_stock": 3, "low_stock_threshold": 5},
            token=self.token,
        )
        medicine_id = res["medicine"]["id"]
        testutil.dispatch("POST", f"/api/stock/{medicine_id}/add", {"amount": 5}, token=self.token)
        _, notif = testutil.dispatch("GET", "/api/notifications", token=self.token)
        refill = next(n for n in notif["notifications"] if n["type"] == "REFILL")
        # testutil forces config.GMAIL_SENDER_EMAIL/GMAIL_APP_PASSWORD empty
        # for every test run, so delivery must deterministically fail closed
        # rather than silently pretend to send or depend on real network access.
        self.assertEqual(refill["email_status"], "FAILED")
        self.assertEqual(refill["email_to"], "caregiver@example.com")

    def test_medicine_delete_removes_it(self):
        _, res = testutil.dispatch("POST", "/api/medicines", {"name": "Temp", "initial_stock": 1}, token=self.token)
        medicine_id = res["medicine"]["id"]
        status, res = testutil.dispatch("DELETE", f"/api/medicines/{medicine_id}", token=self.token)
        self.assertEqual(status, 200)
        status, res = testutil.dispatch("GET", f"/api/medicines/{medicine_id}", token=self.token)
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
