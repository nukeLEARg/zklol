#!/usr/bin/env bash
# Updated script with corrected paths

# It's good practice to add pytest to a requirements-dev.txt file,
# but installing it here is also fine for a simple setup.
pip3 install pytest

# --- CORRECTED PATH ---
# Change directory to where the source code and tests are located.
cd /app/Insight

# Run the tests
pytest .