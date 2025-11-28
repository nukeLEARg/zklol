#!/usr/bin/env bash
# Updated script with corrected paths and logic

# Use sudo to install system packages
sudo apt-get update && sudo apt-get install -y \
tk \
&& sudo rm -rf /var/lib/apt/lists/*

# The following line is removed as it's harmful for modern Python and unnecessary.
# pip3 install --force-reinstall pip==18.1

# Install pyinstaller
pip3 install pyinstaller

# --- CORRECTED PATHS ---
# Prepare the build directory by copying in runtime files
cp /app/config.ini /app/Insight
cp /app/Database.db /app/Insight
mv /app/sqlite-latest.sqlite /app/Insight

# --- CORRECTED PATH ---
# Change to the source code directory to run the build
cd /app/Insight

# Run the pyinstaller build
pyinstaller scripts/PyInstaller.spec --clean

# --- CORRECTED PATHS ---
# Copy the build artifacts back to the main /app volume
cp /app/Insight/dist /app -R
cp /app/Insight/distTest /app -R

cd /app

# The old /InsightDocker directory doesn't exist, so the 'rm' command is removed.

# Use sudo to clean up system packages
sudo apt-get purge -y tk && sudo apt-get autoremove -y

ldd --version
echo "Successfully created the Linux binary archive for Insight. You will find the archive in the dist folder. Your Database and config file have been copied into the distTest folder for testing to ensure the binary is working. Note: This application will not work on Linux distros with a glibc version below the listed version above."