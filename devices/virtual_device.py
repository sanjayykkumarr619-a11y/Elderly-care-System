"""
VirtualDevice: the software-only stand-in for a physical smart-home device.

It implements the same tiny interface a future RaspberryPiDevice adapter
will implement (execute_command / get_status), so DeviceManager and every
layer above it (the API, the frontend) never need to know or care which
one is actually backing a given device row.
"""

VALID_COMMANDS = ("ON", "OFF")


class VirtualDevice:
    def __init__(self, device_row):
        self.id = device_row["id"]
        self.name = device_row["name"]
        self.state = device_row["state"]

    def execute_command(self, command):
        if command not in VALID_COMMANDS:
            raise ValueError(f"Invalid command '{command}'. Expected one of {VALID_COMMANDS}.")
        # A real device would take time and could fail; the virtual one
        # simply flips its state instantly and always succeeds.
        self.state = command
        return self.state

    def get_status(self):
        return {"state": self.state, "online": True, "simulated": True}
