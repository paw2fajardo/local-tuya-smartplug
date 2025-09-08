import tinytuya
import sys

class TinyTuyaController:
    def __init__(self, device_id, device_ip, local_key, dp_id=1):
        self.device_id = device_id
        self.device_ip = device_ip
        self.local_key = local_key
        self.dp_id = dp_id
        try:
            self.device = tinytuya.OutletDevice(device_id, device_ip, local_key)
            self.device.set_version(3.3)
        except Exception as e:
            print(f"Error initializing device: {e}")
            sys.exit(1)

    def set_state(self, action):
        """
        Turn the smart plug on or off.
        action: "on" or "off"
        """
        try:
            print(f"Attempting to turn the smart plug {action}...")
            if action == "on":
                result = self.device.turn_on()
            else:
                result = self.device.turn_off()
            return result

            # Check if the command was successful
            if result and "dps" in result:
                state = "on" if result["dps"][self.dp_id] else "off"
                print(f"Success! The smart plug is now {state}.")
                return True
            else:
                print("Failed to control the smart plug. Please check your configuration.")
                return False
        except tinytuya.error.CommandTimeout as e:
            print(f"Error: Connection to the device timed out. Is the IP address correct and the device reachable? {e}")
            return False
        except Exception as e:
            print(f"An unexpected error occurred: {e}")