import psutil
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

try:
    import wmi
    WMI_AVAILABLE = True
except ImportError:
    WMI_AVAILABLE = False


@dataclass
class BatteryInfo:
    """Data class to hold battery information."""
    percent: float
    power_plugged: bool
    time_left_seconds: Optional[int]
    time_left_formatted: Optional[str]
    status: str


class BatteryMonitor:
    """
    A class to monitor and retrieve system battery information.
    """
    
    def __init__(self):
        """Initialize the BatteryMonitor."""
        pass
    
    def get_battery_level(self) -> Optional[BatteryInfo]:
        """
        Check the current system battery level and status.
        
        Returns:
            Optional[BatteryInfo]: BatteryInfo object containing battery information,
            or None if no battery is detected.
        """
        try:
            battery = psutil.sensors_battery()
            
            if battery is None:
                return None
            
            # Calculate time left in a more readable format
            time_left_formatted = None
            time_left_seconds = None
            
            if (battery.secsleft != psutil.POWER_TIME_UNLIMITED and 
                battery.secsleft != psutil.POWER_TIME_UNKNOWN):
                time_left_seconds = battery.secsleft
                hours = battery.secsleft // 3600
                minutes = (battery.secsleft % 3600) // 60
                time_left_formatted = f"{hours}h {minutes}m"
            
            # Determine battery status
            status = self._determine_battery_status(battery.percent, battery.power_plugged)
            
            return BatteryInfo(
                percent=battery.percent,
                power_plugged=battery.power_plugged,
                time_left_seconds=time_left_seconds,
                time_left_formatted=time_left_formatted,
                status=status
            )
            
        except Exception as e:
            print(f"Error retrieving battery information: {e}")
            return None
    
    def _determine_battery_status(self, percent: float, power_plugged: bool) -> str:
        """
        Determine the battery status based on percentage and power state.
        
        Args:
            percent: Battery percentage (0-100)
            power_plugged: Whether the power adapter is connected
            
        Returns:
            str: Battery status description
        """
        if power_plugged:
            if percent == 100:
                return "Fully charged"
            else:
                return "Charging"
        else:
            if percent <= 10:
                return "Critical"
            elif percent <= 20:
                return "Low"
            else:
                return "Discharging"
    
    def is_battery_available(self) -> bool:
        """
        Check if a battery is available on the system.
        
        Returns:
            bool: True if battery is detected, False otherwise
        """
        try:
            battery = psutil.sensors_battery()
            return battery is not None
        except Exception:
            return False
    
    def is_battery_critical(self, threshold: float = 10.0) -> bool:
        """
        Check if battery level is critical.
        
        Args:
            threshold: Battery percentage threshold for critical level (default: 10%)
            
        Returns:
            bool: True if battery is critical, False otherwise
        """
        battery_info = self.get_battery_level()
        if battery_info is None:
            return False
        return battery_info.percent <= threshold and not battery_info.power_plugged
    
    def print_battery_info(self) -> None:
        """
        Print formatted battery information to the console.
        """
        if not self.is_battery_available():
            print("No battery detected on this system.")
            return
        
        battery_info = self.get_battery_level()
        
        if battery_info is None:
            print("Unable to retrieve battery information.")
            return
        
        print("=== Battery Information ===")
        print(f"Battery Level: {battery_info.percent}%")
        print(f"Status: {battery_info.status}")
        print(f"Power Adapter: {'Connected' if battery_info.power_plugged else 'Disconnected'}")
        
        if battery_info.time_left_formatted:
            print(f"Estimated Time Left: {battery_info.time_left_formatted}")
        elif battery_info.power_plugged:
            print("Estimated Time Left: N/A (Charging)")
        else:
            print("Estimated Time Left: Unknown")
    
    def get_battery_percentage(self) -> Optional[float]:
        """
        Get just the battery percentage.
        
        Returns:
            Optional[float]: Battery percentage or None if no battery
        """
        battery_info = self.get_battery_level()
        return battery_info.percent if battery_info else None
    
    def is_charging(self) -> Optional[bool]:
        """
        Check if the battery is currently charging.
        
        Returns:
            Optional[bool]: True if charging, False if not, None if no battery
        """
        battery_info = self.get_battery_level()
        if battery_info is None:
            return None
        return battery_info.power_plugged and battery_info.percent < 100

    def get_remote_battery_level(self, computer_name: str, username: Optional[str] = None,
                                password: Optional[str] = None) -> Optional[List[BatteryInfo]]:
        """
        Check battery level on a remote Windows computer using WMI.

        Args:
            computer_name: Name or IP address of the remote computer
            username: Username for authentication (optional, uses current user if None)
            password: Password for authentication (optional, uses current user if None)

        Returns:
            Optional[List[BatteryInfo]]: List of BatteryInfo objects for each battery found,
            or None if connection fails or no batteries detected.

        Note:
            Requires pywin32 package and WMI access to the remote computer.
            The remote computer must have WMI service running and accessible.
        """
        if not WMI_AVAILABLE:
            print("WMI module not available. Install pywin32 package: pip install pywin32")
            return None

        try:
            # Connect to remote WMI
            if username and password:
                connection = wmi.WMI(computer=computer_name, user=username, password=password)
            else:
                connection = wmi.WMI(computer=computer_name)

            # Query battery information
            batteries = connection.Win32_Battery()

            if not batteries:
                print(f"No batteries found on remote computer: {computer_name}")
                return None

            battery_list = []

            for battery in batteries:
                try:
                    # Get battery percentage
                    percent = float(battery.EstimatedChargeRemaining or 0)

                    # Initialize power status
                    power_plugged = False

                    # Try to get power adapter status
                    try:
                        power_supplies = connection.Win32_PowerSupply()
                        for ps in power_supplies:
                            if ps.PowerSupplyType == 3:  # AC Adapter
                                power_plugged = True
                                break
                    except:
                        # Fallback: assume plugged if battery status indicates charging
                        battery_status = getattr(battery, 'BatteryStatus', None)
                        if battery_status == 2:  # Charging
                            power_plugged = True

                    # Calculate time left
                    time_left_seconds = None
                    time_left_formatted = None

                    if hasattr(battery, 'EstimatedRunTime') and battery.EstimatedRunTime:
                        try:
                            time_left_minutes = int(battery.EstimatedRunTime)
                            if time_left_minutes != 71582788:  # WMI unknown value
                                time_left_seconds = time_left_minutes * 60
                                hours = time_left_minutes // 60
                                minutes = time_left_minutes % 60
                                time_left_formatted = f"{hours}h {minutes}m"
                        except (ValueError, TypeError):
                            pass

                    # Determine status
                    status = self._determine_battery_status(percent, power_plugged)

                    battery_info = BatteryInfo(
                        percent=percent,
                        power_plugged=power_plugged,
                        time_left_seconds=time_left_seconds,
                        time_left_formatted=time_left_formatted,
                        status=status
                    )

                    battery_list.append(battery_info)

                except Exception as e:
                    print(f"Error processing battery data: {e}")
                    continue

            return battery_list if battery_list else None

        except Exception as e:
            print(f"Error connecting to remote computer {computer_name}: {e}")
            return None

    def print_remote_battery_info(self, computer_name: str, username: Optional[str] = None,
                                 password: Optional[str] = None) -> None:
        """
        Print formatted battery information for a remote computer.

        Args:
            computer_name: Name or IP address of the remote computer
            username: Username for authentication (optional)
            password: Password for authentication (optional)
        """
        print(f"=== Remote Battery Information ({computer_name}) ===")

        battery_list = self.get_remote_battery_level(computer_name, username, password)

        if battery_list is None:
            print("Unable to retrieve remote battery information.")
            return

        for i, battery_info in enumerate(battery_list, 1):
            if len(battery_list) > 1:
                print(f"\nBattery {i}:")

            print(f"Battery Level: {battery_info.percent}%")
            print(f"Status: {battery_info.status}")
            print(f"Power Adapter: {'Connected' if battery_info.power_plugged else 'Disconnected'}")

            if battery_info.time_left_formatted:
                print(f"Estimated Time Left: {battery_info.time_left_formatted}")
            elif battery_info.power_plugged:
                print("Estimated Time Left: N/A (Charging)")
            else:
                print("Estimated Time Left: Unknown")
