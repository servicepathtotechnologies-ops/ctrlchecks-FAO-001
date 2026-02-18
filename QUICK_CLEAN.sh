#!/bin/bash
# Quick cleanup - copy and paste these commands on your server

sudo systemctl stop ollama-api 2>/dev/null || true
sudo systemctl disable ollama-api 2>/dev/null || true
sudo pkill -f uvicorn 2>/dev/null || true
sudo lsof -ti:8000 | xargs sudo kill -9 2>/dev/null || true
sudo rm -rf /opt/ltx-2
sudo rm -rf /opt/ollama-api
sudo rm -rf /opt/Fast_API_Ollama
sudo rm -rf /home/ubuntu/ollama-api
sudo rm -rf /home/ubuntu/Fast_API_Ollama
sudo rm -f /etc/systemd/system/ollama-api.service
sudo systemctl daemon-reload
sudo rm -rf /tmp/videos
sudo rm -rf /tmp/*.mp4
echo "Cleanup complete! Check with: ls -la /opt/"
