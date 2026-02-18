#!/bin/bash

# ============================================
# FIND AND CLEAN DISK SPACE
# Identifies and removes large files/directories
# ============================================

echo "============================================"
echo "FINDING LARGE FILES AND DIRECTORIES"
echo "============================================"
echo ""

# Check Ollama storage locations
echo "1. Checking Ollama storage locations..."
if [ -d ~/.ollama ]; then
    echo "   ~/.ollama exists:"
    du -sh ~/.ollama
    if [ -d ~/.ollama/models ]; then
        echo "   ~/.ollama/models:"
        du -sh ~/.ollama/models
        echo "   Contents:"
        ls -lh ~/.ollama/models/ 2>/dev/null | head -10
    fi
    if [ -d ~/.ollama/blobs ]; then
        echo "   ~/.ollama/blobs:"
        du -sh ~/.ollama/blobs
    fi
else
    echo "   ~/.ollama does not exist"
fi
echo ""

# Check other Ollama locations
echo "2. Checking other Ollama locations..."
for dir in /usr/share/ollama /var/lib/ollama /opt/ollama; do
    if [ -d "$dir" ]; then
        echo "   $dir exists:"
        sudo du -sh "$dir"
    fi
done
echo ""

# Find largest directories
echo "3. Top 15 largest directories in root:"
sudo du -h --max-depth=1 / 2>/dev/null | sort -hr | head -15
echo ""

# Find largest directories in home
echo "4. Top 10 largest directories in home:"
du -h --max-depth=1 ~ 2>/dev/null | sort -hr | head -10
echo ""

# Check for large files
echo "5. Large files (>500MB) in common locations:"
echo "   In /opt:"
sudo find /opt -type f -size +500M 2>/dev/null | head -5
echo "   In /home:"
sudo find /home -type f -size +500M 2>/dev/null | head -5
echo "   In /var:"
sudo find /var -type f -size +500M 2>/dev/null | head -5
echo ""

# Check Docker
echo "6. Checking Docker:"
if command -v docker &> /dev/null; then
    sudo docker system df 2>/dev/null || echo "   Docker not running"
else
    echo "   Docker not installed"
fi
echo ""

# Check snap
echo "7. Checking snap packages:"
if command -v snap &> /dev/null; then
    sudo du -sh /var/lib/snapd 2>/dev/null || echo "   Cannot access snapd"
else
    echo "   Snap not installed"
fi
echo ""

echo "============================================"
echo "ANALYSIS COMPLETE"
echo "============================================"
