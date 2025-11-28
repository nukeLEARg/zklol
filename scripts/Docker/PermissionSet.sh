#!/usr/bin/env bash
# Updated script with corrected source paths for all copied files.

# This sets permissions on the main volume mount point
sudo chown -R insight:insight /app || exit 1
sudo chmod 750 /app || exit 1

# --- CORRECTED SOURCE PATHS ---
# All of these files were copied to /app/ in the Dockerfile, not /app/Insight/
cp -n /app/README.md /app || exit 1
cp -n /app/LICENSE.md /app || exit 1
cp -n /app/ChangeLog.md /app || exit 1
cp -n /app/CCP.md /app || exit 1

# This path was already correct, as scripts are copied into /app/scripts
cp -n /app/scripts/Docker/README.md /app/Installation.md || exit 1

# Set final, more restrictive permissions on the newly created config file
sudo chown -R insight:insight /app || exit 1