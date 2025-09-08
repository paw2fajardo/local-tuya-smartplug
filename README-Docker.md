# Docker Deployment Guide

This guide explains how to run the Local Tuya Smart Plug application in a Docker container.

## Prerequisites

- Docker and Docker Compose installed
- Access to your Tuya smart plug device details
- Remote Windows computer for battery monitoring (optional)

## Quick Start

1. **Copy the environment file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit the `.env` file with your configuration:**
   ```bash
   # Remote computer credentials for battery monitoring
   REMOTE_COMPUTER=192.168.1.100
   REMOTE_USERNAME=your-username
   REMOTE_PASSWORD=your-password

   # Tuya smart plug configuration
   DEVICE_ID=your-device-id
   DEVICE_IP=192.168.1.50
   LOCAL_KEY=your-local-key
   DP_ID=1
   ```

3. **Build and run with Docker Compose:**
   ```bash
   docker-compose up -d
   ```

## Alternative Docker Commands

### Build the image manually:
```bash
docker build -t local-tuya-smartplug .
```

### Run with environment variables:
```bash
docker run -d \
  --name tuya-smartplug \
  --restart unless-stopped \
  -e REMOTE_COMPUTER=192.168.1.100 \
  -e REMOTE_USERNAME=your-username \
  -e REMOTE_PASSWORD=your-password \
  -e DEVICE_ID=your-device-id \
  -e DEVICE_IP=192.168.1.50 \
  -e LOCAL_KEY=your-local-key \
  -e DP_ID=1 \
  -v $(pwd)/logs:/app/logs \
  local-tuya-smartplug
```

## Important Notes

### Windows-Specific Dependencies
The application uses Windows-specific libraries (`pywin32`, `WMI`) for remote battery monitoring. These are conditionally installed only on Windows systems. In the Linux container:

- Remote battery monitoring via WMI will not work
- The app will gracefully handle the missing WMI functionality
- You can use the mock battery function for testing by uncommenting line 50 in `main.py`

### Network Requirements
- The container needs network access to communicate with your Tuya smart plug
- If monitoring a remote computer, ensure network connectivity to that machine
- Consider using `--network host` if you encounter connectivity issues

### Logs
- Logs are persisted in the `./logs` directory
- The container creates a non-root user for security
- Log files are created with appropriate permissions

## Monitoring and Troubleshooting

### View logs:
```bash
docker-compose logs -f tuya-smartplug
```

### Check container status:
```bash
docker-compose ps
```

### Access container shell:
```bash
docker-compose exec tuya-smartplug bash
```

### Stop the service:
```bash
docker-compose down
```

## Configuration Options

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `REMOTE_COMPUTER` | IP or hostname of remote computer | - |
| `REMOTE_USERNAME` | Username for remote access | - |
| `REMOTE_PASSWORD` | Password for remote access | - |
| `DEVICE_ID` | Tuya device ID | - |
| `DEVICE_IP` | Tuya device IP address | - |
| `LOCAL_KEY` | Tuya device local key | - |
| `DP_ID` | Tuya device data point ID | 1 |
| `LOGS_FOLDER` | Directory for log files | /app/logs |
