#!/bin/bash

# ============================================
# DISK SPACE ANALYSIS SCRIPT
# Identifies what's using disk space
# ============================================

echo "============================================"
echo "DISK SPACE ANALYSIS"
echo "============================================"
echo ""

# Current disk usage
echo "Current Disk Usage:"
df -h / | tail -1
echo ""

# Find largest directories in root
echo "============================================"
echo "LARGEST DIRECTORIES IN ROOT (/):"
echo "============================================"
sudo du -h --max-depth=1 / 2>/dev/null | sort -hr | head -20
echo ""

# Check home directory
echo "============================================"
echo "LARGEST DIRECTORIES IN HOME (~):"
echo "============================================"
du -h --max-depth=1 ~ 2>/dev/null | sort -hr | head -20
echo ""

# Check Ollama locations
echo "============================================"
echo "OLLAMA STORAGE LOCATIONS:"
echo "============================================"
if [ -d ~/.ollama ]; then
    echo "~/.ollama:"
    du -sh ~/.ollama
    du -sh ~/.ollama/models 2>/dev/null || echo "  No models directory"
    du -sh ~/.ollama/blobs 2>/dev/null || echo "  No blobs directory"
    echo ""
fi

if [ -d /usr/share/ollama ]; then
    echo "/usr/share/ollama:"
    sudo du -sh /usr/share/ollama
    echo ""
fi

if [ -d /var/lib/ollama ]; then
    echo "/var/lib/ollama:"
    sudo du -sh /var/lib/ollama
    echo ""
fi

# List Ollama models
echo "============================================"
echo "OLLAMA MODELS:"
echo "============================================"
if command -v ollama &> /dev/null; then
    ollama list
else
    echo "Ollama not installed"
fi
echo ""

# Check Docker
echo "============================================"
echo "DOCKER DISK USAGE:"
echo "============================================"
if command -v docker &> /dev/null; then
    sudo docker system df 2>/dev/null || echo "Docker not running"
else
    echo "Docker not installed"
fi
echo ""

# Check for large log files
echo "============================================"
echo "LARGE LOG FILES (>100MB):"
echo "============================================"
sudo find /var/log -type f -size +100M 2>/dev/null | head -10
if [ $? -ne 0 ]; then
    echo "No large log files found"
fi
echo ""

# Check for large files in common locations
echo "============================================"
echo "LARGE FILES IN /opt (>100MB):"
echo "============================================"
sudo find /opt -type f -size +100M 2>/dev/null | head -10
if [ $? -ne 0 ]; then
    echo "No large files found in /opt"
fi
echo ""

echo "============================================"
echo "LARGE FILES IN /home (>100MB):"
echo "============================================"
sudo find /home -type f -size +100M 2>/dev/null | head -10
if [ $? -ne 0 ]; then
    echo "No large files found in /home"
fi
echo ""

# Check snap packages
echo "============================================"
echo "SNAP PACKAGES:"
echo "============================================"
if command -v snap &> /dev/null; then
    snap list --all 2>/dev/null | head -10
    echo ""
    echo "Snap disk usage:"
    sudo du -sh /var/lib/snapd 2>/dev/null || echo "Cannot access snapd directory"
else
    echo "Snap not installed"
fi
echo ""

# Summary
echo "============================================"
echo "SUMMARY"
echo "============================================"
echo "To free up space, check the largest directories above."
echo ""
echo "Common cleanup commands:"
echo "  # Clean Ollama models:"
echo "  ollama list | awk 'NR>1 {print \$1}' | xargs -I {} ollama rm {}"
echo "  sudo rm -rf ~/.ollama/models/*"
echo ""
echo "  # Clean Docker:"
echo "  sudo docker system prune -a --volumes -f"
echo ""
echo "  # Clean apt cache:"
echo "  sudo apt clean && sudo apt autoremove -y"
echo ""
echo "  # Clean journal logs:"
echo "  sudo journalctl --vacuum-time=3d"
echo ""
