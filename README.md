# Smart Plug Controller

A lightweight FastAPI service that controls Tuya-compatible smart plugs locally based on battery status and gaming activity.

## What changed
- Device mappings moved to `config/device_mapping.json` (JSON file preferred). The server still falls back to legacy `DEVICE_MAPPING` env var if needed.
- The controller now reads device state before sending commands and prefers `turn_on`/`turn_off` calls to avoid toggles.
- Improved handling of different tinytuya status payloads (`Payload` and `dps`).

## Prerequisites
- Python 3.8+
- Network access from the server host to your Tuya devices (same LAN)

## Install
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Configuration
Preferred: edit `config/device_mapping.json` and add one object per computer name. Example:

```json
{
   "GAMING-PC": {
      "device_id": "eb03814051c8508cdbhtal",
      "device_ip": "192.168.10.157",
      "local_key": "<device-local-key>"
   },
   "WORK-ROOM": {
      "device_id": "eb105e201fb9ddf39cme88",
      "device_ip": "192.168.10.125",
      "local_key": "<device-local-key-2>"
   }
}
```

Security note: avoid committing `local_key` values to source control. You can create `config/device_mapping.local.json` (gitignored) with sensitive keys.

Fallback: the legacy `DEVICE_MAPPING` environment variable is still supported but not recommended.

Other settings live in `.env`:
- `SERVER_HOST` (default: 0.0.0.0)
- `SERVER_PORT` (default: 8000)
- `LOW_BATTERY_THRESHOLD` (default: 20)
- `HIGH_BATTERY_THRESHOLD` (default: 80)
- `PING_TIMEOUT` (seconds, default: 300)

## Run
```powershell
python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

## API
POST /update
- Headers: `X-Computer-Name: <COMPUTER_NAME>` (required; must match mapping)
- Body (application/json):
```json
{
   "battery_percent": 85.0,
   "is_charging": false,
   "is_gaming": true
}
```
Response: JSON with status and message.

GET /status
- Returns mappings, plug status, last ping, and battery status for each computer.

## Client example (PowerShell)
```powershell
$body = @{ battery_percent = 85; is_charging = $false; is_gaming = $false } | ConvertTo-Json
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/update' -Method Post -Headers @{ 'X-Computer-Name' = 'GAMING-PC' } -Body $body -ContentType 'application/json'
```

## Logs
- Stored in `logs/smartplug.log` (rotated)

## Troubleshooting
- If devices fail to initialize, verify:
   - Device IP is correct and reachable from the server (ping, Test-NetConnection)
   - `local_key` and `device_id` are correct
   - No AP/client isolation on your Wi-Fi network
- Use the `/status` endpoint to inspect runtime state.

## Next steps
- Optionally move `local_key` into an encrypted store or `.local.json` file and keep it out of git.

MIT

# Smart Plug Controller

A Python-based server application that controls a Tuya smart plug based on battery status and gaming activity. The server listens for status updates from a remote client and automatically turns the plug on/off based on configured thresholds.

## Features

- 🖥️ Web server with REST API (FastAPI)
- 🔌 Control Tuya smart plugs
- 🔋 Automatic power management based on battery level
- 🎮 Special handling for gaming sessions
- ⏱️ Automatic shutoff after inactivity
- 📊 Status monitoring endpoint
- 📝 Comprehensive logging

## Prerequisites

- Python 3.8+
- Tuya IoT Platform account
- Tuya smart plug (tested with Tuya/Smart Life compatible devices)
- Network access between the server and smart plug

## Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/local-tuya-smartplug.git
   cd local-tuya-smartplug
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   - Copy `.env.example` to `.env`
   - Update the values in `.env` with your Tuya API credentials and device ID

## Tuya IoT Platform Setup

1. Log in to the [Tuya IoT Platform](https://iot.tuya.com/)
2. Create a new cloud project
3. Note down the following from the project settings:
   - Access ID/Client ID
   - Access Secret/Client Secret
4. Link your Tuya smart device to the project
5. Get the Device ID of your smart plug

## Running the Server

```bash
uvicorn app:app --reload
```

The server will be available at `http://localhost:8000`

## API Endpoints

- `POST /update` - Update battery status
  ```json
  {
    "battery_percent": 75.5,
    "is_charging": false,
    "is_gaming": true
  }
  ```

- `GET /status` - Get current system status
  ```json
  {
    "is_on": true,
    "last_updated": "2023-01-01T12:00:00.000000",
    "last_ping": "2023-01-01T12:01:30.000000",
    "battery_status": {
      "battery_percent": 75.5,
      "is_charging": false,
      "is_gaming": true,
      "last_updated": "2023-01-01T12:01:30.000000",
      "client_ip": "192.168.1.100"
    }
  }
  ```

## Client Implementation

You'll need to create a client that periodically sends battery and gaming status to the server. Here's a simple Python example:

```python
import requests
import psutil
import time

def is_gaming():
    # Implement your game detection logic here
    # Return True if a game is running, False otherwise
    return False

def get_battery_status():
    battery = psutil.sensors_battery()
    return {
        'battery_percent': battery.percent,
        'is_charging': battery.power_plugged,
        'is_gaming': is_gaming()
    }

SERVER_URL = "http://your-server-ip:8000/update"

while True:
    try:
        status = get_battery_status()
        response = requests.post(SERVER_URL, json=status)
        print(f"Status updated: {status}")
    except Exception as e:
        print(f"Error updating status: {e}")
    
    time.sleep(60)  # Update every minute
```

## Docker Deployment

1. Build the Docker image:
   ```bash
   docker build -t smartplug-controller .
   ```

2. Run the container:
   ```bash
   docker run -d --name smartplug \
     -p 8000:8000 \
     --env-file .env \
     -v ./logs:/app/logs \
     smartplug-controller
   ```

## Configuration

Edit the `.env` file to customize the following settings:

- `TUYA_ACCESS_ID`: Tuya API Access ID
- `TUYA_ACCESS_KEY`: Tuya API Access Key
- `TUYA_DEVICE_ID`: Your Tuya device ID
- `SERVER_HOST`: Host to bind to (default: 0.0.0.0)
- `SERVER_PORT`: Port to listen on (default: 8000)
- `LOW_BATTERY_THRESHOLD`: Turn on plug when battery is below this percentage (default: 20)
- `HIGH_BATTERY_THRESHOLD`: Turn off plug when battery is above this percentage (default: 80)
- `PING_TIMEOUT`: Turn off plug after this many seconds of no pings (default: 300)

## Logs

Logs are stored in the `logs/` directory with rotation (10MB per file, 1 month retention).

## License

MIT