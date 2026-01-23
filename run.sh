#!/bin/bash

# WheelFlow - Bicycle Wheel CFD Analysis
# Startup script

cd "$(dirname "$0")"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Create necessary directories
mkdir -p uploads cases results

# Source OpenFOAM environment
export OPENFOAM_DIR=/opt/openfoam13
export PATH=$OPENFOAM_DIR/platforms/linux64GccDPInt32Opt/bin:$PATH
export LD_LIBRARY_PATH=$OPENFOAM_DIR/platforms/linux64GccDPInt32Opt/lib:$OPENFOAM_DIR/platforms/linux64GccDPInt32Opt/lib/dummy:$LD_LIBRARY_PATH

echo ""
echo "=================================="
echo "  WheelFlow - CFD Analysis"
echo "=================================="
echo ""
echo "Starting server at http://localhost:8000"
echo ""
echo "To expose via Cloudflare Tunnel:"
echo "  cloudflared tunnel --url http://localhost:8000"
echo ""

# Run the server
uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
