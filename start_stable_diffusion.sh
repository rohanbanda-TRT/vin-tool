#!/bin/bash

# Change to the project directory
cd "$(dirname "$0")"

# Activate virtual environment if it exists, otherwise use system Python
if [ -d "venv/bin" ]; then
    source venv/bin/activate
fi

# Install required dependencies if needed
pip install -q selenium webdriver-manager fastmcp

# Start the MCP server
python3 stable_diffusion_generator.py
