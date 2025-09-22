#!/usr/bin/env bash
set -euo pipefail

IMAGE="local_tuya"
CONTAINER="local_tuya"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
error_exit() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $*" >&2; exit 1; }

trap 'error_exit "Interrupted"' INT TERM

log "Starting deploy: image=$IMAGE container=$CONTAINER"

# 1) Stop and remove container if it exists
container_running_id=$(docker ps -q -f "name=${CONTAINER}" || true)
if [ -n "$container_running_id" ]; then
  log "Stopping running container $CONTAINER ($container_running_id)"
  if docker stop "$CONTAINER" >/dev/null 2>&1; then
    log "Stopped container $CONTAINER"
  else
    log "Failed to stop container $CONTAINER; attempting to continue"
  fi
fi

container_all_id=$(docker ps -aq -f "name=${CONTAINER}" || true)
if [ -n "$container_all_id" ]; then
  log "Removing container $CONTAINER ($container_all_id)"
  if docker rm -f "$CONTAINER" >/dev/null 2>&1; then
    log "Removed container $CONTAINER"
  else
    log "Failed to remove container $CONTAINER; attempting to continue"
  fi
else
  log "No container named $CONTAINER found"
fi

# 2) Delete image if present
image_id=$(docker images -q "$IMAGE" || true)
if [ -n "$image_id" ]; then
  log "Removing image $IMAGE ($image_id)"
  if docker rmi -f "$IMAGE" >/dev/null 2>&1; then
    log "Removed image $IMAGE"
  else
    log "Failed to remove image $IMAGE; attempting to continue"
  fi
else
  log "No image named $IMAGE found"
fi

# 3) Build image
log "Building image $IMAGE"
if docker build -t "$IMAGE" .; then
  log "Build succeeded"
else
  error_exit "Image build failed"
fi

# 4) Delete dangling images
log "Pruning dangling images"
if docker image prune -f >/dev/null 2>&1; then
  log "Prune complete"
else
  log "Prune failed or no dangling images"
fi

# 5) Run the container
log "Starting container $CONTAINER from image $IMAGE"
# Use current directory mounts for logs and config, and .env for environment
RUN_CMD=(docker run -d --name "$CONTAINER" -p 8000:8000 --env-file .env -v "$(pwd)/logs":/app/logs -v "$(pwd)/config":/app/config:ro "$IMAGE")
if "${RUN_CMD[@]}" >/dev/null 2>&1; then
  log "Container $CONTAINER started"
else
  error_exit "Failed to start container $CONTAINER"
fi

log "Deploy finished successfully"
exit 0
