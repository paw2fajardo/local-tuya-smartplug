import logging
import os
from src.battery_monitor import BatteryMonitor
from src.tiny_tuya_controller import TinyTuyaController
from dotenv import load_dotenv

load_dotenv()

logs_folder = os.getenv("LOGS_FOLDER", "./logs")
if not os.path.exists(logs_folder):
    os.makedirs(logs_folder)

# Set up logging
logging.basicConfig(
    filename=os.path.join(logs_folder, "app.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def check_remote_battery(remote_computer, username, password):
    battery_monitor = BatteryMonitor()
    battery_info = battery_monitor.get_remote_battery_level(
        remote_computer, username, password
    )[0]
    return battery_info if battery_info else None


# Mock function for testing
def mock_battery_level():
    class MockBatteryInfo:
        percent = 60
        power_plugged = True
        time_left_seconds = 7740
        time_left_formatted = "2:09:00"
        status = "Charging"  # Discharging, Full

    return MockBatteryInfo()


def main():
    try:
        battery_info = check_remote_battery(
            os.getenv("REMOTE_COMPUTER"),
            os.getenv("REMOTE_USERNAME"),
            os.getenv("REMOTE_PASSWORD"),
        )

        # mocked for local testing without remote access
        # battery_info = mock_battery_level()

        logging.info("Battery info retrieved successfully")
        logging.info(f"Battery %: {battery_info.percent}")
        logging.info(f"Plugged In: {battery_info.power_plugged}")

        smart_plug = TinyTuyaController(
            device_id=os.getenv("DEVICE_ID"),
            device_ip=os.getenv("DEVICE_IP"),
            local_key=os.getenv("LOCAL_KEY"),
            dp_id=int(os.getenv("DP_ID", 1)),
        )

        if battery_info:
            if battery_info.percent < 20:
                smart_plug.set_state("on")
                logging.info("Smart plug turned on")
            elif battery_info.percent >= 80 and battery_info.power_plugged:
                smart_plug.set_state("off")
                logging.info("Smart plug turned off")
            else:
                logging.info("No action taken on smart plug")
        else:
            smart_plug.set_state("off")
            logging.info("Smart plug turned off due to no battery info")

    except Exception as e:
        logging.error(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
