#!/usr/bin/env bash
# This script has been updated to work with the new /app directory structure.
# Exit immediately if a command exits with a non-zero status.
set -e

function permissionError() {
    echo "An error occurred when trying to set permissions on existing files in the Docker volume. Exiting..."
    exit 1
}

# --- CORRECTED PATH ---
# All scripts are now located in /app/scripts/Docker/
/app/scripts/Docker/PermissionSet.sh || permissionError

# The WORKDIR is already /app, so this isn't strictly necessary but is safe.
cd /app

# Check for special build/test flags
for a in "$@"
do
    if [ "$a" = "-b" ] || [ "$a" = "--build-binary" ]; then
        # --- CORRECTED PATH ---
        exec /app/scripts/Docker/DockerBinBuild.sh
    fi
    if [ "$a" = "-t" ] || [ "$a" = "--tests" ]; then
        # --- CORRECTED PATH ---
        exec /app/scripts/Docker/DockerTests.sh
    fi
    if [ "$a" = "--export-swagger-client" ]; then
        # --- CORRECTED PATH ---
        cd /app/python-client
        zip -r /app/swagger-client-python.zip .
        exit 0
    fi
done

# Execute the main command passed from the Dockerfile ENTRYPOINT
# (e.g., python3 /app/Insight/Insight ...)
exec "$@"