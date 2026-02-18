#!/bin/bash

# ============================================
# CLEAN /usr DIRECTORY - Find Ollama Models
# ============================================

echo "============================================"
echo "FINDING OLLAMA MODELS IN /usr"
echo "============================================"
echo ""

# Check common Ollama locations in /usr
echo "1. Checking /usr/share/ollama:"
if [ -d /usr/share/ollama ]; then
    sudo du -sh /usr/share/ollama
    echo "   Contents:"
    sudo ls -lh /usr/share/ollama/ 2>/dev/null | head -20
else
    echo "   Directory does not exist"
fi
echo ""

echo "2. Checking /usr/lib/ollama:"
if [ -d /usr/lib/ollama ]; then
    sudo du -sh /usr/lib/ollama
    echo "   Contents:"
    sudo ls -lh /usr/lib/ollama/ 2>/dev/null | head -20
else
    echo "   Directory does not exist"
fi
echo ""

echo "3. Finding all 'ollama' directories in /usr:"
sudo find /usr -type d -name "*ollama*" 2>/dev/null
echo ""

echo "4. Finding large files in /usr/share:"
sudo du -h --max-depth=2 /usr/share 2>/dev/null | sort -hr | head -20
echo ""

echo "5. Finding large files in /usr/lib:"
sudo du -h --max-depth=2 /usr/lib 2>/dev/null | sort -hr | head -20
echo ""

echo "============================================"
echo "CLEANUP COMMANDS"
echo "============================================"
echo ""
echo "If you found Ollama models, run:"
echo "  sudo rm -rf /usr/share/ollama/models/*"
echo "  sudo rm -rf /usr/lib/ollama/models/*"
echo "  sudo rm -rf /usr/local/share/ollama/models/*"
echo ""
