# 🚀 FastAPI Ollama Service

FastAPI service for CtrlChecks AI Workflow Platform, providing AI model access via Ollama.

## 📋 Overview

This service provides a REST API interface to Ollama models, enabling:
- Chat completions
- Text generation
- Model management
- Health monitoring
- Circuit breaker pattern for reliability

## 🏗️ Architecture

```
┌─────────────────┐
│   Nginx (80/443)│  →  Reverse Proxy
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  FastAPI (8000) │  →  API Service
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Ollama (11434) │  →  AI Models
└─────────────────┘
```

## 🚀 Quick Start

### Local Development

```bash
# Clone repository
git clone https://github.com/servicepathtotechnologies-ops/ctrlchecks-FAO-001.git
cd ctrlchecks-FAO-001

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp env.example .env
# Edit .env with your settings

# Run service
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Production Deployment

See comprehensive deployment guide:
- **[AWS Fresh Deployment Guide](../Guide/Fast_API_Ollama/AWS_FRESH_DEPLOYMENT_COMPLETE.md)**

## 📁 Project Structure

```
Fast_API_Ollama/
├── main.py                 # FastAPI application
├── circuit_breaker.py      # Circuit breaker implementation
├── metrics.py              # Metrics collection
├── json_validator.py       # JSON validation utilities
├── gpu_monitor.py          # GPU monitoring
├── retry_utils.py          # Retry logic
├── requirements.txt        # Python dependencies
├── env.example             # Environment variables template
├── .gitignore             # Git ignore rules
├── Dockerfile             # Docker configuration
├── nginx-ollama-complete.conf  # Nginx configuration
├── CLEAN_SERVER.sh        # Server cleanup script
├── CLEAN_OLLAMA_MODELS.sh # Ollama models cleanup
├── DEPLOY_TO_AWS.sh       # Automated deployment script
└── README.md              # This file
```

## 🔧 Configuration

### Environment Variables

Create `.env` file from `env.example`:

```env
# Ollama Configuration
OLLAMA_URL=http://localhost:11434
PORT=8000

# Worker Service URL
WORKER_URL=http://localhost:3001

# CORS Configuration
ALLOWED_ORIGINS=*

# Model Configuration
MODEL_PRIMARY=qwen2.5:14b-instruct-q4_K_M
MODEL_FALLBACK=qwen2.5:7b-instruct-q4_K_M
MODEL_CODER=qwen2.5-coder:7b-instruct-q4_K_M
MODEL_TIMEOUT=60
MODEL_MAX_RETRIES=3

# Circuit Breaker
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_RECOVERY_TIMEOUT=60.0

# Request Limits
MAX_REQUEST_SIZE_MB=10
RATE_LIMIT_PER_MINUTE=100
TIMEOUT_SECONDS=60.0
```

## 📡 API Endpoints

### Health Check
```bash
GET /health
```

### List Models
```bash
GET /api/models
```

### Chat Completion
```bash
POST /api/chat
Content-Type: application/json

{
  "model": "qwen2.5:14b-instruct-q4_K_M",
  "messages": [
    {"role": "user", "content": "Hello!"}
  ]
}
```

### Generate Text
```bash
POST /api/generate
Content-Type: application/json

{
  "model": "qwen2.5:14b-instruct-q4_K_M",
  "prompt": "Write a Python function to..."
}
```

### API Documentation
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## 🐳 Docker Deployment

```bash
# Build image
docker build -t fastapi-ollama .

# Run container
docker run -d \
  -p 8000:8000 \
  --env-file .env \
  --name fastapi-ollama \
  fastapi-ollama
```

## 🔒 Security

- CORS configuration for allowed origins
- Request size limits
- Rate limiting
- Circuit breaker for fault tolerance
- Environment variable protection

## 📊 Monitoring

### Health Checks
```bash
curl http://localhost:8000/health
```

### Service Logs
```bash
# Systemd service
sudo journalctl -u ollama-api -f

# Docker
docker logs -f fastapi-ollama
```

### Metrics
- Request count
- Error rate
- Response time
- Circuit breaker state

## 🛠️ Development

### Running Tests
```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest
```

### Code Quality
```bash
# Format code
black .

# Lint code
flake8 .

# Type checking
mypy .
```

## 📚 Documentation

- **[Complete Deployment Guide](../Guide/Fast_API_Ollama/AWS_FRESH_DEPLOYMENT_COMPLETE.md)** - Step-by-step AWS deployment
- **[Quick Start Guide](../Guide/Fast_API_Ollama/QUICK_START.md)** - Quick setup instructions
- **[Troubleshooting Guide](../Guide/Fast_API_Ollama/TROUBLESHOOT_SERVICE.md)** - Common issues and solutions

## 🔄 Updates

### Update Code
```bash
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart ollama-api
```

### Update Models
```bash
# Pull new model
ollama pull qwen2.5:14b-instruct-q4_K_M

# Update .env with new model name
nano .env
sudo systemctl restart ollama-api
```

## 🐛 Troubleshooting

### Service Won't Start
```bash
# Check logs
sudo journalctl -u ollama-api -n 50

# Test manual start
cd /opt/ollama-api
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Ollama Connection Issues
```bash
# Check Ollama service
sudo systemctl status ollama

# Test Ollama API
curl http://localhost:11434/api/tags
```

### Port Already in Use
```bash
# Find process
sudo lsof -i:8000

# Kill process
sudo kill -9 <PID>
```

## 📝 License

[Your License Here]

## 🤝 Contributing

[Contributing Guidelines]

---

**Version:** 1.0.0  
**Last Updated:** 2024
