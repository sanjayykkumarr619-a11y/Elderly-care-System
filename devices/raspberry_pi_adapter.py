"""
RaspberryPiDevice: placeholder adapter for a real, physically wired device.

This is intentionally NOT wired up or used anywhere in the prototype - no
GPIO libraries, no serial/network drivers, nothing hardware-specific is
imported here. It exists purely to document the extension point: when
real hardware is available, this class implements the exact same
interface as VirtualDevice (execute_command / get_status), so
DeviceManager can switch a device from "virtual" to "raspberry_pi" in the
database and nothing above this layer - not the API, not the frontend -
needs to change.
"""


class RaspberryPiDevice:
    def __init__(self, device_row):
        self.id = device_row["id"]
        self.hardware_id = device_row["hardware_id"]
        self.state = device_row["state"]

    def execute_command(self, command):
        # FUTURE IMPLEMENTATION SKETCH:
        #   import RPi.GPIO as GPIO
        #   pin = int(self.hardware_id)
        #   GPIO.output(pin, GPIO.HIGH if command == "ON" else GPIO.LOW)
        # or, for a networked relay board:
        #   requests.post(f"http://{self.hardware_id}/relay", json={"state": command})
        raise NotImplementedError(
            "Raspberry Pi hardware is not connected in this software-only prototype."
        )

    def get_status(self):
        raise NotImplementedError(
            "Raspberry Pi hardware is not connected in this software-only prototype."
        )
