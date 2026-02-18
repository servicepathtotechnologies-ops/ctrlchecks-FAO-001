#!/bin/bash

# ============================================
# AUTOMATED AWS DEPLOYMENT SCRIPT
# FastAPI Ollama Service - Fresh Deployment
# ============================================

set -e  # Exit on error

echo "============================================"
echo "FASTAPI OLLAMA - AWS DEPLOYMENT"
echo "============================================"

# Configuration
PROJECT_DIR="/opt/ollama-api"
GIT_REPO="https://github.com/servicepathtotechnologies-ops/ctrlchecks-FAO-001.git"
SERVICE_NAME="ollama-api"
DOMAIN="ollama.ctrlchecks.ai"
PORT=8000

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root (we'll use sudo where needed)
if [ "$EUID" -eq 0 ]; then
    print_error "Please run as regular user (not root). Script will use sudo where needed."
    exit 1
fi

# Step 1: Cleanup
print_status "Step 1: Cleaning up old installation..."

# Stop services
sudo systemctl stop $SERVICE_NAME 2>/dev/null || true
sudo systemctl disable $SERVICE_NAME 2>/dev/null || true

# Kill processes on port 8000
sudo lsof -ti:$PORT | xargs sudo kill -9 2>/dev/null || true
sudo fuser -k $PORT/tcp 2>/dev/null || true
sudo pkill -f "uvicorn main:app" 2>/dev/null || true

# Remove old directories
sudo rm -rf /opt/ollama-api
sudo rm -rf /opt/Fast_API_Ollama
sudo rm -rf /home/ubuntu/ollama-api
sudo rm -rf /home/ubuntu/Fast_API_Ollama

# Remove old service files
sudo rm -f /etc/systemd/system/$SERVICE_NAME.service
sudo systemctl daemon-reload

print_status "Cleanup complete!"

# Step 2: Update system
print_status "Step 2: Updating system packages..."
sudo apt update
sudo apt upgrade -y

# Step 3: Install dependencies
print_status "Step 3: Installing system dependencies..."
sudo apt install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    git \
    curl \
    nginx \
    certbot \
    python3-certbot-nginx \
    build-essential

# Step 4: Clone repository
print_status "Step 4: Cloning repository..."
cd /opt
sudo git clone $GIT_REPO ollama-api
sudo chown -R $USER:$USER /opt/ollama-api
cd $PROJECT_DIR

# Step 5: Setup Python environment
print_status "Step 5: Setting up Python virtual environment..."
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Step 6: Create environment file
print_status "Step 6: Creating environment file..."
if [ ! -f .env ]; then
    cp env.example .env
    print_warning "Please edit .env file with your configuration:"
    print_warning "  nano $PROJECT_DIR/.env"
    read -p "Press Enter after editing .env file..."
fi

# Step 7: Install Ollama (if not installed)
print_status "Step 7: Checking Ollama installation..."
if ! command -v ollama &> /dev/null; then
    print_status "Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
    sudo systemctl start ollama
    sudo systemctl enable ollama
else
    print_status "Ollama is already installed"
fi

# Step 8: Create systemd service
print_status "Step 8: Creating systemd service..."
sudo tee /etc/systemd/system/$SERVICE_NAME.service > /dev/null <<EOF
[Unit]
Description=CtrlChecks FastAPI Ollama Service
After=network.target ollama.service
Requires=ollama.service

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/venv/bin"
EnvironmentFile=$PROJECT_DIR/.env
ExecStart=$PROJECT_DIR/venv/bin/uvicorn main:app --host 0.0.0.0 --port $PORT
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Security settings
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

# Step 9: Enable and start service
print_status "Step 9: Enabling and starting service..."
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
sudo systemctl start $SERVICE_NAME

# Wait a moment for service to start
sleep 3

# Check service status
if sudo systemctl is-active --quiet $SERVICE_NAME; then
    print_status "Service is running!"
else
    print_error "Service failed to start. Check logs:"
    print_error "  sudo journalctl -u $SERVICE_NAME -n 50"
    exit 1
fi

# Step 10: Setup Nginx
print_status "Step 10: Configuring Nginx..."
sudo tee /etc/nginx/sites-available/$DOMAIN > /dev/null <<EOF
server {
    listen 80;
    server_name $DOMAIN;

    access_log /var/log/nginx/ollama-access.log;
    error_log /var/log/nginx/ollama-error.log;

    location / {
        proxy_pass http://localhost:$PORT;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Host \$host;
        proxy_set_header X-Forwarded-Port \$server_port;
        
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        send_timeout 300s;
        
        client_max_body_size 100M;
        proxy_cache_bypass \$http_upgrade;
        proxy_buffering off;
        proxy_request_buffering off;
    }

    location /health {
        proxy_pass http://localhost:$PORT/health;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        access_log off;
    }
}
EOF

# Enable site
sudo ln -sf /etc/nginx/sites-available/$DOMAIN /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test and reload nginx
if sudo nginx -t; then
    sudo systemctl reload nginx
    print_status "Nginx configured successfully!"
else
    print_error "Nginx configuration test failed!"
    exit 1
fi

# Step 11: Test endpoints
print_status "Step 11: Testing endpoints..."
sleep 2

if curl -f http://localhost:$PORT/health > /dev/null 2>&1; then
    print_status "✓ Health endpoint is working"
else
    print_warning "Health endpoint test failed"
fi

# Final summary
echo ""
echo "============================================"
echo "DEPLOYMENT COMPLETE!"
echo "============================================"
echo ""
print_status "Service Status:"
sudo systemctl status $SERVICE_NAME --no-pager -l

echo ""
print_status "Next Steps:"
echo "  1. Download required Ollama models:"
echo "     ollama pull qwen2.5:14b-instruct-q4_K_M"
echo "     ollama pull qwen2.5:7b-instruct-q4_K_M"
echo "     ollama pull qwen2.5-coder:7b-instruct-q4_K_M"
echo ""
echo "  2. Setup SSL certificate:"
echo "     sudo certbot --nginx -d $DOMAIN"
echo ""
echo "  3. Test endpoints:"
echo "     curl http://localhost:$PORT/health"
echo "     curl http://$DOMAIN/health"
echo ""
echo "  4. View logs:"
echo "     sudo journalctl -u $SERVICE_NAME -f"
echo ""
echo "============================================"
