#!/bin/bash

# ============================================
# CLEAN OLLAMA MODELS SCRIPT
# Removes all Ollama models to free up space
# ============================================

echo "============================================"
echo "CLEANING OLLAMA MODELS"
echo "============================================"

# Check if Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo "Ollama is not installed. Exiting."
    exit 1
fi

# Stop Ollama service
echo "[1/5] Stopping Ollama service..."
sudo systemctl stop ollama 2>/dev/null || true

# List current models
echo "[2/5] Current models:"
ollama list

# Get disk space before cleanup
echo ""
echo "Disk space before cleanup:"
df -h / | tail -1

# Remove all models
echo ""
echo "[3/5] Removing all Ollama models..."
MODELS=$(ollama list | awk 'NR>1 {print $1}')

if [ -z "$MODELS" ]; then
    echo "No models found to remove."
else
    for model in $MODELS; do
        echo "  Removing: $model"
        ollama rm "$model" 2>/dev/null || true
    done
fi

# Clean Ollama cache directories
echo "[4/5] Cleaning Ollama cache..."
sudo rm -rf ~/.ollama/models/* 2>/dev/null || true
sudo rm -rf /usr/share/ollama/models/* 2>/dev/null || true
sudo rm -rf /var/lib/ollama/models/* 2>/dev/null || true

# Get disk space after cleanup
echo ""
echo "[5/5] Disk space after cleanup:"
df -h / | tail -1

# Verify cleanup
echo ""
echo "============================================"
echo "VERIFICATION"
echo "============================================"
echo "Remaining models:"
ollama list

# Calculate freed space
echo ""
echo "============================================"
echo "CLEANUP COMPLETE!"
echo "============================================"
echo ""
echo "You can now download fresh models using:"
echo "  ollama pull qwen2.5:14b-instruct-q4_K_M"
echo "  ollama pull qwen2.5:7b-instruct-q4_K_M"
echo "  ollama pull qwen2.5-coder:7b-instruct-q4_K_M"
echo ""
