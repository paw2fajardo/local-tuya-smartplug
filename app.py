import asyncio
import os
from datetime import datetime
from typing import Dict, Optional, List, Any

from dotenv import load_dotenv, dotenv_values
import pathlib

current_dir = pathlib.Path(__file__).parent.absolute()
env_path = current_dir / '.env'

_ = load_dotenv(env_path, override=True, verbose=True, encoding='utf-8')
values = dotenv_values(dotenv_path=env_path, encoding='utf-8')
for k, v in values.items():
    os.environ[k] = v if v is not None else ''

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel, Field
import tinytuya


def _is_on_value(v) -> bool:
    """Normalize various DPS value types to a boolean 'on' indicator.

    Handles bool, numeric, and common string representations.
    """
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        return v.strip().lower() in ('1', 'true', 'on', 'yes')
    return False

class DeviceConfig(BaseModel):
    device_id: str
    device_ip: str
    local_key: str
    last_ping: datetime = Field(default_factory=datetime.now)
    battery_status: Dict = Field(default_factory=dict)
    plug_status: bool = False

class Settings(BaseModel):
    SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")
    SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8000"))
    PING_TIMEOUT: int = int(os.getenv("PING_TIMEOUT", "300"))
    LOW_BATTERY_THRESHOLD: int = int(os.getenv("LOW_BATTERY_THRESHOLD", "20"))
    HIGH_BATTERY_THRESHOLD: int = int(os.getenv("HIGH_BATTERY_THRESHOLD", "80"))
    device_mapping: Dict[str, Any] = {}
    
    def __init__(self, **data):
        super().__init__(**data)
        self.device_mapping = self._parse_device_mapping()
    
    def _parse_device_mapping(self) -> Dict[str, DeviceConfig]:
        # First, attempt to load mappings from JSON file in config/ (preferred)
        json_mappings = self._load_device_mapping_from_json()
        if json_mappings:
            return json_mappings

        # Fallback to legacy DEVICE_MAPPING env var parsing
        mapping_str = os.getenv("DEVICE_MAPPING", "")
        mappings = {}
        if not mapping_str:
            logger.warning("No device mappings found in environment variables or config file")
            return mappings

        for mapping in mapping_str.split(','):
            mapping = mapping.strip()
            if not mapping:
                continue

            parts = mapping.split('=', 1)
            if len(parts) != 2:
                logger.warning(f"Invalid device mapping format (missing '=' separator): {mapping}. Expected format: COMPUTER_NAME=DEVICE_ID:DEVICE_IP:LOCAL_KEY")
                continue

            computer_name, device_info = parts[0].strip(), parts[1].strip()

            # device_info may contain ':' inside the local_key, so split at most 2 times
            device_parts = device_info.split(':', 2)
            if len(device_parts) != 3:
                logger.warning(f"Invalid device mapping format (expected 3 parts separated by ':'): {mapping}. Expected format: COMPUTER_NAME=DEVICE_ID:DEVICE_IP:LOCAL_KEY")
                continue

            device_id, device_ip, local_key = (p.strip() for p in device_parts)

            try:
                mappings[computer_name.upper()] = DeviceConfig(
                    device_id=device_id,
                    device_ip=device_ip,
                    local_key=local_key
                )
                # Do not log the local_key (secret); log only non-sensitive parts
                logger.info(f"Mapped computer '{computer_name}' to device: {device_id}@{device_ip}")
            except Exception as e:
                logger.warning(f"Failed to create DeviceConfig for mapping: {computer_name} -> {device_id}@{device_ip}: {e}")
        return mappings

    def _load_device_mapping_from_json(self) -> Dict[str, DeviceConfig]:
        """Load device mappings from config/device_mapping.json if present."""
        config_path = pathlib.Path(__file__).parent / 'config' / 'device_mapping.json'
        if not config_path.exists():
            return {}

        try:
            import json
            raw = json.loads(config_path.read_text(encoding='utf-8'))
            mappings: Dict[str, DeviceConfig] = {}
            for comp_name, cfg in raw.items():
                try:
                    mappings[comp_name.upper()] = DeviceConfig(
                        device_id=str(cfg.get('device_id', '')).strip(),
                        device_ip=str(cfg.get('device_ip', '')).strip(),
                        local_key=str(cfg.get('local_key', '')).strip()
                    )
                    logger.info(f"Mapped computer '{comp_name}' from JSON to device: {cfg.get('device_id')}@{cfg.get('device_ip')}")
                except Exception as e:
                    logger.warning(f"Invalid entry in device_mapping.json for '{comp_name}': {e}")
            return mappings
        except Exception as e:
            logger.error(f"Failed to load device_mapping.json: {e}")
            return {}

# Initialize settings
settings = Settings()

# Configure logging
logger.add("logs/smartplug.log", rotation="10 MB", retention="1 month", level="INFO")
logger.info("Starting Smart Plug Controller")

app = FastAPI(title="Smart Plug Controller")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

settings = Settings()

# Log loaded configuration
logger.info(f"Server will run on {settings.SERVER_HOST}:{settings.SERVER_PORT}")
logger.info(f"Loaded {len(settings.device_mapping)} device(s)")
for name, config in settings.device_mapping.items():
    logger.info(f"  - {name}: {config.device_id} @ {config.device_ip}")

devices: Dict[str, Any] = {}  # device_id -> TuyaDevice

class BatteryUpdate(BaseModel):
    battery_percent: float = Field(..., ge=0, le=100, description="Current battery percentage (0-100)")
    is_charging: bool = Field(..., description="Whether the device is currently charging")
    is_gaming: bool = Field(..., description="Whether a game is currently running")

class PlugStatus(BaseModel):
    is_on: bool
    last_updated: str
    last_ping: str
    battery_status: Optional[Dict]

async def init_devices():
    """Initialize local device connections"""
    global devices
    
    for computer_name, config in settings.device_mapping.items():
        try:
            # Create device instance with local key
            device = tinytuya.OutletDevice(
                dev_id=config.device_id,
                address=config.device_ip,
                local_key=config.local_key,
                version=3.3
            )
            
            device.set_socketPersistent(True)
            status = device.status()

            # Consider the device successfully connected if status indicates no Error and contains
            # either a 'Payload' or a 'dps' dict.
            status_has_error = isinstance(status, dict) and (status.get('Error') is not None or status.get('Err') is not None)
            status_has_payload = isinstance(status, dict) and status.get('Payload') not in (None, '')
            status_has_dps = isinstance(status, dict) and isinstance(status.get('dps'), dict)

            status_valid = isinstance(status, dict) and not status_has_error and (status_has_payload or status_has_dps)

            if status_valid:
                devices[config.device_id] = device
                logger.info(f"Successfully connected to device {computer_name} ({config.device_id}@{config.device_ip})")
            else:
                # Log detailed status for debugging (device may be unreachable or local_key wrong)
                logger.error(f"Failed to get valid status from device {computer_name}; status={status}")
                
        except Exception as e:
            logger.error(f"Failed to initialize device {computer_name}: {e}")
    
    if not devices:
        logger.warning("No devices were successfully initialized")
    else:
        logger.info(f"Successfully initialized {len(devices)} device(s)")

async def set_plug_state(device_id: str, turn_on: bool) -> bool:
    """Turn the smart plug on or off for a specific device"""
    if not device_id or device_id not in devices:
        logger.warning(f"Device {device_id} not found or not initialized")
        return False
    
    device = devices[device_id]
    
    try:
        logger.info(f"Setting plug state for {device_id}: turn_on={turn_on}")

        # Read current DPS/state and avoid changing if already in desired state
        try:
            status = device.status()
            current_on = None
            if isinstance(status, dict):
                dps = status.get('dps') or status.get('Payload') or {}
                if isinstance(dps, dict):
                        # Prefer key '1' if present, otherwise take first key
                    if '1' in dps:
                        current_val = dps.get('1')
                    else:
                        keys = list(dps.keys())
                        current_val = dps.get(keys[0]) if keys else None
                    # Some DPS values might be numeric (0/1) or boolean
                    if current_val is not None:
                        current_on = _is_on_value(current_val)
            if current_on is not None and current_on == turn_on:
                logger.info(f"Device {device_id} already {'on' if turn_on else 'off'}; no action needed")
                # Update mapping state
                for mapping in settings.device_mapping.values():
                    if mapping.device_id == device_id:
                        mapping.plug_status = turn_on
                return True
        except Exception as e:
            logger.warning(f"Failed to read current status for {device_id} before control: {e}")

    # Execute control: prefer turn_on/turn_off and stop on success
        if hasattr(device, 'turn_on') and hasattr(device, 'turn_off'):
            try:
                res = device.turn_on() if turn_on else device.turn_off()
                
                success = False
                if isinstance(res, dict):
                    dps = res.get('dps') or {}
                    try:
                        success = any((v is True) == (turn_on is True) for v in dps.values()) if isinstance(dps, dict) else False
                    except Exception:
                        success = False
                else:
                    success = bool(res)

                if success:
                    for mapping in settings.device_mapping.values():
                        if mapping.device_id == device_id:
                            mapping.plug_status = turn_on
                            logger.info(f"Successfully turned plug {'on' if turn_on else 'off'} for device {device_id}")
                            return True
                    logger.warning(f"Device {device_id} controlled but no mapping found for status update")
                    return True
            except Exception as e:
                logger.warning(f"turn_on/turn_off call failed for {device_id}: {e}")

    # Fallback: try set_status with the common payload shape {1: bool}
        if hasattr(device, 'set_status'):
            try:
                res = device.set_status({1: turn_on})
                # set_status result
                if isinstance(res, dict):
                    dps = res.get('dps') or {}
                    if isinstance(dps, dict):
                        # If the device reports the requested state, success
                        if any((v is True) == (turn_on is True) for v in dps.values()):
                            for mapping in settings.device_mapping.values():
                                if mapping.device_id == device_id:
                                    mapping.plug_status = turn_on
                                    logger.info(f"Successfully turned plug {'on' if turn_on else 'off'} for device {device_id}")
                                    return True
                            logger.warning(f"Device {device_id} controlled but no mapping found for status update")
                            return True
                elif isinstance(res, bool) and res:
                    for mapping in settings.device_mapping.values():
                        if mapping.device_id == device_id:
                            mapping.plug_status = turn_on
                            logger.info(f"Successfully turned plug {'on' if turn_on else 'off'} for device {device_id}")
                            return True
            except Exception as e:
                logger.warning(f"set_status call failed for {device_id}: {e}")

        logger.error(f"Failed to control plug {device_id}; no control method reported success")
        return False
            
    except Exception as e:
        logger.error(f"Error controlling plug {device_id}: {e}")
        return False

async def check_battery_status(computer_name: str, battery_data: Dict) -> None:
    """Check battery status and control plug accordingly for a specific computer"""
    if computer_name.upper() not in settings.device_mapping:
        logger.warning(f"No device mapping found for computer: {computer_name}")
        return
    
    mapping = settings.device_mapping[computer_name.upper()]
    mapping.last_ping = datetime.now()
    mapping.battery_status = battery_data
    
    battery_percent = battery_data.get("battery_percent", 100)
    is_charging = battery_data.get("is_charging", False)
    is_gaming = battery_data.get("is_gaming", False)
    
    # If gaming, turn on the plug regardless of battery level
    if is_gaming and not mapping.plug_status:
        logger.info(f"Game detected on {computer_name}, turning on plug")
        await set_plug_state(mapping.device_id, True)
        return
    
    # If not gaming, manage based on battery level
    if not is_charging and battery_percent <= settings.LOW_BATTERY_THRESHOLD and not mapping.plug_status:
        logger.info(f"Battery low on {computer_name} ({battery_percent}%), turning on plug")
        await set_plug_state(mapping.device_id, True)
    elif is_charging and battery_percent >= settings.HIGH_BATTERY_THRESHOLD and mapping.plug_status:
        logger.info(f"Battery charged on {computer_name} ({battery_percent}%), turning off plug")
        await set_plug_state(mapping.device_id, False)

async def check_last_ping():
    """Check when we last received pings from all clients"""
    while True:
        current_time = datetime.now()
        for computer_name, mapping in settings.device_mapping.items():
            time_since_last_ping = (current_time - mapping.last_ping).total_seconds()
            if time_since_last_ping > settings.PING_TIMEOUT and mapping.plug_status:
                logger.warning(f"No ping from {computer_name} in {int(time_since_last_ping)}s, turning off plug")
                try:
                    await set_plug_state(mapping.device_id, False)
                except Exception as e:
                    logger.error(f"Failed to turn off plug for {computer_name} after timeout: {e}")
        await asyncio.sleep(60)

@app.on_event("startup")
async def startup_event():
    """Initialize the application"""
    # By default skip device initialization to avoid network checks at startup.
    # Set environment variable SKIP_DEVICE_INIT to '0' or 'false' to enable initialization again.
    skip_init = os.getenv("SKIP_DEVICE_INIT", "true").strip().lower()
    if skip_init in ("0", "false", "no"):
        logger.info("Device initialization enabled on startup (SKIP_DEVICE_INIT=%s)", skip_init)
        await init_devices()
    else:
        logger.info("Device initialization skipped on startup (set SKIP_DEVICE_INIT=0 to enable)")

    asyncio.create_task(check_last_ping())

@app.post("/update")
async def update_battery_status(update: BatteryUpdate, request: Request):
    """Update battery status from client"""
    # Get computer name from headers or use IP as fallback
    computer_name = request.headers.get("X-Computer-Name") or request.client.host

    logger.info(f"Received update from {computer_name} (IP: {request.client.host}): {update.dict()}")

    # If there's no mapping for this computer, return a helpful error so the client can correct the header
    if str(computer_name).upper() not in settings.device_mapping:
        available = list(settings.device_mapping.keys())
        logger.warning(f"No device mapping found for incoming update from {computer_name}; available mappings: {available}")
        return JSONResponse(
            status_code=404,
            content={
                "status": "error",
                "message": f"No device mapping found for '{computer_name}'. Please send header 'X-Computer-Name' that matches one of: {available}",
                "available_mappings": available,
            },
        )

    # Update battery status and control plug if needed
    battery_data = {
        **update.dict(),
        "last_updated": datetime.now().isoformat(),
        "client_ip": request.client.host,
    }

    await check_battery_status(computer_name, battery_data)

    return {"status": "success", "message": f"Battery status updated for {computer_name}"}

@app.get("/status", response_model=Dict[str, Any])
async def get_status():
    """Get current system status for all devices"""
    status = {}
    
    for computer_name, config in settings.device_mapping.items():
        device_info = {
            "device_id": config.device_id,
            "device_ip": config.device_ip,
            "plug_status": config.plug_status,
            "last_ping": config.last_ping.isoformat(),
            "battery_status": config.battery_status or None
        }
        
        # Add device connection status if available in `devices`
        if config.device_id in devices:
            device = devices[config.device_id]
            # Some tinytuya device objects expose 'available' or 'online' attributes; guard access
            connected = getattr(device, 'available', None)
            if connected is None:
                connected = getattr(device, 'online', None)
            # Fall back to True if we can't determine availability but have an object
            device_info["connected"] = bool(connected) if connected is not None else True
            
        status[computer_name] = device_info
    
    return status

if __name__ == "__main__":
    import uvicorn

    os.makedirs("logs", exist_ok=True)
    
    uvicorn.run(
        "app:app",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        reload=True,
        log_level="info"
    )
