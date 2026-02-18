#!/bin/bash

# ============================================
# COMPLETE SERVER CLEANUP SCRIPT
# This will DELETE ALL data related to the project
# ============================================

echo "============================================"
echo "STARTING COMPLETE SERVER CLEANUP"
echo "============================================"

# Stop and disable services
echo "[1/10] Stopping services..."
sudo systemctl stop ollama-api 2>/dev/null || true
sudo systemctl disable ollama-api 2>/dev/null || true
sudo systemctl stop fastapi-ollama 2>/dev/null || true
sudo systemctl disable fastapi-ollama 2>/dev/null || true

# Kill processes on port 8000
echo "[2/10] Killing processes on port 8000..."
sudo lsof -ti:8000 | xargs sudo kill -9 2>/dev/null || true
sudo fuser -k 8000/tcp 2>/dev/null || true
sudo pkill -f "uvicorn main:app" 2>/dev/null || true
sudo pkill -f "fastapi" 2>/dev/null || true

# Remove systemd service files
echo "[3/10] Removing systemd service files..."
sudo rm -f /etc/systemd/system/ollama-api.service
sudo rm -f /etc/systemd/system/fastapi-ollama.service
sudo systemctl daemon-reload

# Remove all project directories
echo "[4/10] Removing project directories..."
sudo rm -rf /opt/ollama-api
sudo rm -rf /opt/Fast_API_Ollama
sudo rm -rf /opt/ltx-2
sudo rm -rf /home/ubuntu/ollama-api
sudo rm -rf /home/ubuntu/Fast_API_Ollama
sudo rm -rf ~/ollama-api
sudo rm -rf ~/Fast_API_Ollama
sudo rm -rf /var/www/ollama-api
sudo rm -rf /var/www/Fast_API_Ollama

# Remove Python virtual environments
echo "[5/10] Removing Python virtual environments..."
sudo find /opt -type d -name "venv" -exec rm -rf {} + 2>/dev/null || true
sudo find /home -type d -name "venv" -exec rm -rf {} + 2>/dev/null || true
sudo find ~ -type d -name "venv" -exec rm -rf {} + 2>/dev/null || true

# Remove Python cache files
echo "[6/10] Removing Python cache files..."
sudo find /opt -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
sudo find /home -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
sudo find ~ -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
sudo find /opt -name "*.pyc" -delete 2>/dev/null || true
sudo find /home -name "*.pyc" -delete 2>/dev/null || true

# Remove log files
echo "[7/10] Removing log files..."
sudo rm -f /opt/*.log
sudo rm -f /home/ubuntu/*.log
sudo rm -f ~/*.log
sudo rm -f /var/log/ollama-api.log
sudo rm -f /var/log/fastapi-ollama.log
sudo journalctl --vacuum-time=1d 2>/dev/null || true

# Remove temporary files
echo "[8/10] Removing temporary files..."
sudo rm -rf /tmp/videos
sudo rm -rf /tmp/ollama*
sudo rm -rf /tmp/fastapi*
sudo rm -rf /tmp/*.mp4
sudo rm -rf /tmp/*.avi
sudo rm -rf /tmp/*.mov

# Remove any remaining process files
echo "[9/10] Cleaning up process files..."
sudo rm -f /opt/nohup.out
sudo rm -f /home/ubuntu/nohup.out
sudo rm -f ~/nohup.out
sudo rm -f /opt/app.log
sudo rm -f /home/ubuntu/app.log

# Final cleanup - remove any hidden files
echo "[10/10] Final cleanup..."
sudo find /opt -name ".env" -type f -delete 2>/dev/null || true
sudo find /home -name ".env" -type f -delete 2>/dev/null || true
sudo find ~ -name ".env" -type f -delete 2>/dev/null || true

# Verify cleanup
echo ""
echo "============================================"
echo "CLEANUP COMPLETE!"
echo "============================================"
echo ""
echo "Checking for remaining files..."
echo ""

# Check if anything remains
if [ -d "/opt/ollama-api" ] || [ -d "/opt/Fast_API_Ollama" ] || [ -d "/opt/ltx-2" ]; then
    echo "WARNING: Some directories still exist:"
    ls -la /opt/ | grep -E "ollama|Fast_API|ltx"
else
    echo "✓ All project directories removed"
fi

# Check for running processes
if pgrep -f "uvicorn" > /dev/null; then
    echo "WARNING: Some uvicorn processes still running:"
    ps aux | grep uvicorn
else
    echo "✓ No uvicorn processes running"
fi

# Check port 8000
if sudo lsof -i:8000 > /dev/null 2>&1; then
    echo "WARNING: Port 8000 still in use:"
    sudo lsof -i:8000
else
    echo "✓ Port 8000 is free"
fi

echo ""
echo "============================================"
echo "Server is now clean and ready for fresh deployment!"
echo "============================================"
